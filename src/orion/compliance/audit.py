"""Append-only audit log with retention policy (P2-3)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class AuditRecord:
    timestamp: datetime
    actor: str
    action: str
    payload: Mapping[str, Any]
    previous_hash: str
    hash: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "actor": self.actor,
            "action": self.action,
            "payload": dict(self.payload),
            "previous_hash": self.previous_hash,
            "hash": self.hash,
        }


class AuditLog:
    """Append-only log where every record references the previous hash.

    The log implements a simple tamper-evident chain: each record's
    ``hash`` is a SHA-256 of the canonical JSON of
    ``(timestamp, actor, action, payload, previous_hash)``. A
    ``verify`` pass walks the chain and flags any inconsistency.
    """

    _GENESIS = "0" * 64

    def __init__(self, *, retention: timedelta | None = None) -> None:
        self._records: list[AuditRecord] = []
        self._retention = retention

    def append(
        self,
        actor: str,
        action: str,
        payload: Mapping[str, Any] | None = None,
    ) -> AuditRecord:
        payload = dict(payload or {})
        previous_hash = self._records[-1].hash if self._records else self._GENESIS
        ts = datetime.now(tz=timezone.utc)
        body = json.dumps(
            [ts.isoformat(), actor, action, payload, previous_hash],
            sort_keys=True,
            separators=(",", ":"),
        )
        h = hashlib.sha256(body.encode("utf-8")).hexdigest()
        record = AuditRecord(
            timestamp=ts,
            actor=actor,
            action=action,
            payload=payload,
            previous_hash=previous_hash,
            hash=h,
        )
        self._records.append(record)
        if self._retention is not None:
            self._enforce_retention(ts)
        return record

    def records(self) -> tuple[AuditRecord, ...]:
        return tuple(self._records)

    def verify(self) -> tuple[bool, str]:
        previous = self._GENESIS
        for record in self._records:
            if record.previous_hash != previous:
                return False, f"broken chain at {record.timestamp.isoformat()}"
            body = json.dumps(
                [
                    record.timestamp.isoformat(),
                    record.actor,
                    record.action,
                    dict(record.payload),
                    record.previous_hash,
                ],
                sort_keys=True,
                separators=(",", ":"),
            )
            h = hashlib.sha256(body.encode("utf-8")).hexdigest()
            if h != record.hash:
                return False, f"hash mismatch at {record.timestamp.isoformat()}"
            previous = record.hash
        return True, "ok"

    def _enforce_retention(self, now: datetime) -> None:
        cutoff = now - self._retention
        # Strict greater-than: anything strictly older than the cutoff
        # is dropped. With a 0-second retention, anything that was
        # appended even a microsecond ago is dropped, which is the
        # expected semantic for "immediate expiry".
        self._records = [r for r in self._records if r.timestamp > cutoff]
