"""Institutional API-key vault, key rotation lifecycle, IP whitelist CIDR verification,
TOTP two-factor authentication (RFC 6238), and withdrawal address timelocks.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import secrets
import struct
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Sequence


class KeyStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ROTATING = "ROTATING"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


@dataclass(frozen=True, slots=True)
class APIKeyRecord:
    key_id: str
    owner_id: str
    venue: str
    key_digest: str
    version: int
    status: KeyStatus
    ip_whitelist: tuple[str, ...]
    created_at_epoch: float
    expires_at_epoch: float


@dataclass(frozen=True, slots=True)
class WhitelistedAddress:
    address_id: str
    owner_id: str
    asset: str
    destination_address: str
    tag: str | None
    approved_at_epoch: float
    timelock_until_epoch: float


class InstitutionalKeyVault:
    """Enterprise API key lifecycle manager with rotation, IP CIDR validation, TOTP, and timelocks."""

    def __init__(self, timelock_delay_seconds: float = 86400.0) -> None:
        self._keys: dict[str, APIKeyRecord] = {}
        self._raw_keys: dict[str, str] = {}  # In-memory secure enclave representation
        self._whitelisted_addresses: dict[str, WhitelistedAddress] = {}
        self._timelock_delay_seconds = timelock_delay_seconds

    def register_key(
        self,
        owner_id: str,
        venue: str,
        secret_value: str,
        ip_whitelist: Sequence[str] = (),
        ttl_seconds: float = 30 * 86400.0,
    ) -> APIKeyRecord:
        key_id = f"key_{secrets.token_hex(8)}"
        now = time.time()
        digest = hashlib.sha256(secret_value.encode("utf-8")).hexdigest()

        record = APIKeyRecord(
            key_id=key_id,
            owner_id=owner_id,
            venue=venue,
            key_digest=digest,
            version=1,
            status=KeyStatus.ACTIVE,
            ip_whitelist=tuple(ip_whitelist),
            created_at_epoch=now,
            expires_at_epoch=now + ttl_seconds,
        )
        self._keys[key_id] = record
        self._raw_keys[key_id] = secret_value
        return record

    def rotate_key(
        self,
        key_id: str,
        new_secret_value: str,
        ttl_seconds: float = 30 * 86400.0,
    ) -> APIKeyRecord:
        old_record = self._keys.get(key_id)
        if not old_record:
            raise KeyError(f"Key {key_id} not found")

        now = time.time()
        new_digest = hashlib.sha256(new_secret_value.encode("utf-8")).hexdigest()

        updated_record = APIKeyRecord(
            key_id=old_record.key_id,
            owner_id=old_record.owner_id,
            venue=old_record.venue,
            key_digest=new_digest,
            version=old_record.version + 1,
            status=KeyStatus.ACTIVE,
            ip_whitelist=old_record.ip_whitelist,
            created_at_epoch=now,
            expires_at_epoch=now + ttl_seconds,
        )
        self._keys[key_id] = updated_record
        self._raw_keys[key_id] = new_secret_value
        return updated_record

    def revoke_key(self, key_id: str) -> APIKeyRecord:
        record = self._keys.get(key_id)
        if not record:
            raise KeyError(f"Key {key_id} not found")

        revoked = APIKeyRecord(
            key_id=record.key_id,
            owner_id=record.owner_id,
            venue=record.venue,
            key_digest=record.key_digest,
            version=record.version,
            status=KeyStatus.REVOKED,
            ip_whitelist=record.ip_whitelist,
            created_at_epoch=record.created_at_epoch,
            expires_at_epoch=record.expires_at_epoch,
        )
        self._keys[key_id] = revoked
        self._raw_keys.pop(key_id, None)
        return revoked

    def validate_access(self, key_id: str, client_ip: str) -> tuple[bool, str]:
        record = self._keys.get(key_id)
        if not record:
            return False, f"Key {key_id} does not exist"
        if record.status != KeyStatus.ACTIVE:
            return False, f"Key is {record.status.value}"
        if time.time() > record.expires_at_epoch:
            return False, "Key has expired"

        # Check IP whitelist (CIDR or exact IP match)
        if record.ip_whitelist:
            ip_obj = ipaddress.ip_address(client_ip)
            matched = False
            for allowed in record.ip_whitelist:
                try:
                    if "/" in allowed:
                        network = ipaddress.ip_network(allowed, strict=False)
                        if ip_obj in network:
                            matched = True
                            break
                    else:
                        if ip_obj == ipaddress.ip_address(allowed):
                            matched = True
                            break
                except ValueError:
                    continue
            if not matched:
                return False, f"Client IP {client_ip} is not in authorized whitelist"

        return True, "Valid"

    # --- TOTP (RFC 6238) Pure Python Implementation ---
    @staticmethod
    def generate_totp_secret() -> str:
        """Generates base32 RFC 3548 encoded 20-byte secret."""
        raw = secrets.token_bytes(20)
        return base64.b32encode(raw).decode("utf-8").replace("=", "")

    @staticmethod
    def compute_totp(secret_base32: str, timestamp: float | None = None, interval: int = 30) -> str:
        """Computes current 6-digit TOTP code according to RFC 6238 / RFC 4226."""
        now = time.time() if timestamp is None else timestamp
        counter = int(now // interval)

        # Pad base32 string if needed
        padding = (8 - len(secret_base32) % 8) % 8
        padded_secret = secret_base32 + "=" * padding
        key = base64.b32decode(padded_secret, casefold=True)

        msg = struct.pack(">Q", counter)
        h = hmac.new(key, msg, hashlib.sha1).digest()
        offset = h[-1] & 0x0F
        binary = (
            ((h[offset] & 0x7F) << 24)
            | ((h[offset + 1] & 0xFF) << 16)
            | ((h[offset + 2] & 0xFF) << 8)
            | (h[offset + 3] & 0xFF)
        )
        code = binary % 1_000_000
        return f"{code:06d}"

    @classmethod
    def verify_totp(
        cls,
        secret_base32: str,
        candidate_code: str,
        timestamp: float | None = None,
        window: int = 1,
    ) -> bool:
        """Verifies candidate code with optional +/- window steps for clock drift."""
        now = time.time() if timestamp is None else timestamp
        for step in range(-window, window + 1):
            expected = cls.compute_totp(secret_base32, timestamp=now + (step * 30))
            if hmac.compare_digest(candidate_code, expected):
                return True
        return False

    # --- Withdrawal Whitelisting & Time-Locks ---
    def propose_withdrawal_address(
        self, owner_id: str, asset: str, destination_address: str, tag: str | None = None
    ) -> WhitelistedAddress:
        addr_id = f"addr_{secrets.token_hex(6)}"
        now = time.time()
        record = WhitelistedAddress(
            address_id=addr_id,
            owner_id=owner_id,
            asset=asset.upper(),
            destination_address=destination_address,
            tag=tag,
            approved_at_epoch=now,
            timelock_until_epoch=now + self._timelock_delay_seconds,
        )
        self._whitelisted_addresses[addr_id] = record
        return record

    def check_withdrawal_authorization(self, address_id: str, asset: str, destination_address: str) -> tuple[bool, str]:
        record = self._whitelisted_addresses.get(address_id)
        if not record:
            return False, "Destination address is not whitelisted"
        if record.asset != asset.upper() or record.destination_address != destination_address:
            return False, "Address or asset does not match whitelist record"
        now = time.time()
        if now < record.timelock_until_epoch:
            remaining = int(record.timelock_until_epoch - now)
            return False, f"Address locked under security timelock for {remaining} more seconds"
        return True, "Withdrawal authorized"
