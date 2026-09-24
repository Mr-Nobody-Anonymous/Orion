"""Data lineage.

Every datum that enters ORION gets a :class:`LineageRecord`. A line is
``(vendor, series_id, vendor_release_time, fetch_time, sha256)`` and
nothing else. Lineage is stored alongside the data and reported in audit
and backtest reports.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class LineageRecord:
    vendor: str
    series_id: str
    vendor_release_time: datetime
    fetch_time: datetime
    sha256: str
    n_obs: int = 0
    extra: tuple[tuple[str, str], ...] = ()

    def to_dict(self) -> dict[str, object]:
        d = asdict(self)
        d["vendor_release_time"] = self.vendor_release_time.isoformat()
        d["fetch_time"] = self.fetch_time.isoformat()
        d["extra"] = dict(self.extra)
        return d


def hash_records(records: list[dict[str, object]]) -> str:
    """Deterministic hash of a JSON-serialisable record list."""
    blob = json.dumps(records, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


from enum import Enum


class DataLicenseType(str, Enum):
    COMMERCIAL = "commercial"
    INTERNAL_RESEARCH_ONLY = "internal_research_only"
    OPEN_ACCESS = "open_access"
    RESTRICTED_REDISTRIBUTION = "restricted_redistribution"


@dataclass(frozen=True, slots=True)
class DataEntitlement:
    vendor: str
    license_type: DataLicenseType
    commercial_use_allowed: bool = True
    live_trading_allowed: bool = True
    redistributable: bool = False
    vendor_terms_id: str = "standard_v1"
    expiry_date: datetime | None = None


class EntitlementEnforcer:
    """Enforces data licensing constraints between research and production trading."""

    def __init__(self, entitlements: Sequence[DataEntitlement] | None = None) -> None:
        self._entitlements = {e.vendor: e for e in entitlements or ()}

    def register(self, entitlement: DataEntitlement) -> None:
        self._entitlements[entitlement.vendor] = entitlement

    def can_use_for_live_trading(self, vendor: str) -> bool:
        ent = self._entitlements.get(vendor)
        if ent is None:
            return True  # Unrestricted by default unless explicitly tagged
        if not ent.live_trading_allowed or ent.license_type == DataLicenseType.INTERNAL_RESEARCH_ONLY:
            return False
        if ent.expiry_date and ent.expiry_date < datetime.now(timezone.utc):
            return False
        return True


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
