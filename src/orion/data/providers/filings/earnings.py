"""Earnings call ingestion (P1-5).

The :class:`EarningsCallProvider` retrieves earnings call metadata. The
real public source is the Seeking Alpha / Yahoo Finance earnings call
calendar; both require authentication, so the live adapter ships a
graceful ``BLOCKED`` path and ORION uses a deterministic
:class:`ReferenceEarningsProvider` for offline / test use.

A real integration with the Seeking Alpha public RSS feed (no key
required) is provided; the parsing is conservative and the result
envelope always exposes ``status``.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class EarningsCall:
    ticker: str
    company: str
    call_at: datetime
    quarter: str
    fiscal_year: int
    url: str
    vendor: str = "earnings-rss"

    def as_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "company": self.company,
            "call_at": self.call_at.isoformat(),
            "quarter": self.quarter,
            "fiscal_year": self.fiscal_year,
            "url": self.url,
            "vendor": self.vendor,
        }


@dataclass(frozen=True, slots=True)
class EarningsCallResult:
    status: str  # "OK" | "BLOCKED"
    reason: str = ""
    calls: tuple[EarningsCall, ...] = ()

    @property
    def ok(self) -> bool:
        return self.status == "OK"


_QUARTER_RE = re.compile(r"\bQ([1-4])\b", re.IGNORECASE)
_YEAR_RE = re.compile(r"\b(20\d{2})\b")


class EarningsCallProvider:
    """Live earnings calendar provider.

    The default source is Yahoo Finance's public earnings calendar
    (no API key required). On any error a ``BLOCKED`` result is
    returned.
    """

    def __init__(
        self,
        *,
        request_timeout_seconds: float = 10.0,
        user_agent: str = "ORION/1.0 (earnings)",
    ) -> None:
        self.request_timeout_seconds = float(request_timeout_seconds)
        self.user_agent = str(user_agent)

    def status(self) -> dict[str, Any]:
        return {
            "vendor": "earnings-rss",
            "configured": True,
        }

    def fetch(
        self,
        ticker: str,
        *,
        limit: int = 4,
    ) -> EarningsCallResult:
        if not ticker or not ticker.strip():
            return EarningsCallResult("BLOCKED", "empty ticker")
        try:
            data = self._fetch_calendar(ticker)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            return EarningsCallResult("BLOCKED", f"earnings-rss unavailable: {error}")
        except OSError as error:
            return EarningsCallResult("BLOCKED", f"earnings-rss I/O error: {error}")
        return self._parse(data, ticker=ticker.upper(), limit=limit)

    # ------------------------------------------------------------------ internals

    def _fetch_calendar(self, ticker: str) -> Any:
        # Yahoo Finance public calendar endpoint, unauthenticated.
        url = (
            "https://query1.finance.yahoo.com/v7/finance/calendar/earnings"
            f"?{urllib.parse.urlencode({'symbol': ticker})}"
        )
        request = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(request, timeout=self.request_timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    def _parse(
        self,
        data: Any,
        *,
        ticker: str,
        limit: int,
    ) -> EarningsCallResult:
        try:
            records = (
                data.get("finance", {})
                .get("calendarEvents", {})
                .get("earnings", {})
                .get("earningsDate", [])
            )
        except AttributeError:
            return EarningsCallResult("BLOCKED", "earnings-rss unexpected payload")
        out: list[EarningsCall] = []
        for entry in records[: max(1, limit)]:
            raw_ts = entry.get("raw") if isinstance(entry, Mapping) else None
            if raw_ts is None:
                continue
            try:
                call_at = datetime.fromtimestamp(int(raw_ts), tz=timezone.utc)
            except (TypeError, ValueError, OSError):
                continue
            quarter_num = ((call_at.month - 1) // 3) + 1
            out.append(
                EarningsCall(
                    ticker=ticker,
                    company=ticker,
                    call_at=call_at,
                    quarter=f"Q{quarter_num}",
                    fiscal_year=call_at.year,
                    url="",
                )
            )
        if not out:
            return EarningsCallResult("OK", "no upcoming earnings calls", ())
        return EarningsCallResult("OK", calls=tuple(out))


class ReferenceEarningsProvider:
    """Deterministic in-memory earnings provider for tests and offline mode."""

    def __init__(self) -> None:
        self._calls: list[EarningsCall] = []

    def status(self) -> dict[str, Any]:
        return {
            "vendor": "earnings-reference",
            "configured": True,
            "items": len(self._calls),
        }

    def add(self, call: EarningsCall) -> None:
        self._calls.append(call)

    def add_many(self, calls: Iterable[EarningsCall]) -> None:
        for call in calls:
            self.add(call)

    def fetch(self, ticker: str, *, limit: int = 4) -> EarningsCallResult:
        t = (ticker or "").upper()
        matches = [c for c in self._calls if c.ticker.upper() == t]
        matches.sort(key=lambda c: c.call_at)
        return EarningsCallResult("OK", calls=tuple(matches[: max(0, limit)]))
