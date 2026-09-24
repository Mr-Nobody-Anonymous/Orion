"""Point-in-time data primitives.

The single most common source of backtest contamination is looking up a
datum that was *not* actually available at the time the simulated decision
was made. A point-in-time (PIT) record pairs a *vendor release time* (when
the data hit the wire) with an *observation time* (what the data refers
to). A PIT bundle is then a sequence of such records; ``as_of(t)`` returns
the latest record whose vendor release time is ``<= t``.

This module is deliberately stdlib-only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Generic, Sequence, TypeVar

T = TypeVar("T")


def _ensure_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class PITRecord(Generic[T]):
    """A single point-in-time observation.

    Attributes:
        value: the datum itself.
        observation_time: the time the data *refers to* (e.g. an earnings
            announcement date, a daily bar's close).
        vendor_release_time: the time the data became available to ORION.
            Lookups must be ``<= as_of`` to be admissible.
        vendor: free-form name of the upstream source.
        series_id: free-form identifier within the vendor.
    """

    value: T
    observation_time: datetime
    vendor_release_time: datetime
    vendor: str = "unknown"
    series_id: str = ""
    fetch_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        ot = _ensure_utc(self.observation_time)
        rt = _ensure_utc(self.vendor_release_time)
        ft = _ensure_utc(self.fetch_time)
        if rt < ot:
            raise ValueError(
                f"vendor_release_time {rt.isoformat()} is before observation_time "
                f"{ot.isoformat()} — vendor would have known the future"
            )
        object.__setattr__(self, "observation_time", ot)
        object.__setattr__(self, "vendor_release_time", rt)
        object.__setattr__(self, "fetch_time", ft)


@dataclass(frozen=True, slots=True)
class PITBundle(Generic[T]):
    """An ordered sequence of PITRecords, indexed by vendor_release_time.

    All operations are O(n) over the underlying tuple; the bundle is
    immutable. Use ``slice_for`` to get a contiguous window.
    """

    records: tuple[PITRecord[T], ...]

    def __post_init__(self) -> None:
        for prev, current in zip(self.records, self.records[1:]):
            if current.vendor_release_time < prev.vendor_release_time:
                raise ValueError(
                    "PITBundle.records must be sorted by vendor_release_time"
                )

    def is_empty(self) -> bool:
        return not self.records

    def __len__(self) -> int:
        return len(self.records)

    def as_of(self, t: datetime) -> PITRecord[T] | None:
        """Return the latest record whose ``vendor_release_time <= t``.

        This is the only safe lookup. A caller that uses ``.records[-1]``
        is asking for the data the vendor had at *fetch time* and may be
        peeking into the future.
        """
        ts = _ensure_utc(t)
        best: PITRecord[T] | None = None
        for r in self.records:
            if r.vendor_release_time <= ts:
                best = r
            else:
                break
        return best

    def slice_for(
        self,
        start: datetime,
        end: datetime,
    ) -> "PITBundle[T]":
        s = _ensure_utc(start)
        e = _ensure_utc(end)
        if e < s:
            raise ValueError("end must be >= start")
        out: list[PITRecord[T]] = []
        for r in self.records:
            if s <= r.vendor_release_time <= e:
                out.append(r)
        return PITBundle(tuple(out))

    @classmethod
    def from_observations(
        cls,
        observations: Sequence[tuple[datetime, T, datetime, str, str]],
    ) -> "PITBundle[T]":
        """Convenience constructor: ``(observation_time, value,
        vendor_release_time, vendor, series_id)`` tuples."""
        records = tuple(
            PITRecord(
                value=value,
                observation_time=ot,
                vendor_release_time=rt,
                vendor=vendor,
                series_id=series_id,
            )
            for ot, value, rt, vendor, series_id in observations
        )
        return cls(records)
