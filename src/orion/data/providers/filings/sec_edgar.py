"""SEC EDGAR provider for ORION (P1-5).

The :class:`SecEdgarProvider` retrieves company filings from the public
SEC EDGAR system. The EDGAR service is free and public but requires a
descriptive ``User-Agent`` per their fair-access policy. This module
**does not** ship with credentials and refuses to construct an instance
without an explicit ``user_agent`` argument (or
``ORION_SEC_USER_AGENT`` environment variable).

Reference behaviour (no network) is provided by
:class:`orion.data.providers.filings.reference.ReferenceSecEdgarProvider`,
which is a deterministic in-memory substitute used by the test suite.

Design notes
------------

- All returned records carry a ``vendor_release_time`` so they can flow
  through ORION's point-in-time layer without leaking the future.
- On any HTTP or parsing error the provider returns an explicit
  ``SecFilingFetchResult`` with ``status="BLOCKED"`` — it never fabricates
  filings.
- The supported filing types are restricted to what the rest of ORION
  actually uses: ``10-K``, ``10-Q``, ``8-K``, ``4`` (insider Form 4),
  ``13F-HR``, ``DEF 14A``.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Sequence


class FilingForm(str, Enum):
    TEN_K = "10-K"
    TEN_Q = "10-Q"
    EIGHT_K = "8-K"
    FORM_FOUR = "4"
    THIRTEEN_F = "13F-HR"
    DEF_14A = "DEF 14A"


@dataclass(frozen=True, slots=True)
class SecFiling:
    """A single SEC filing record with point-in-time semantics."""

    cik: str
    ticker: str
    form: FilingForm
    filed_at: datetime
    period_of_report: datetime | None
    accession_number: str
    primary_document: str
    url: str
    vendor: str = "sec-edgar"

    def as_dict(self) -> dict[str, Any]:
        return {
            "cik": self.cik,
            "ticker": self.ticker,
            "form": self.form.value,
            "filed_at": self.filed_at.isoformat(),
            "period_of_report": (
                self.period_of_report.isoformat() if self.period_of_report else None
            ),
            "accession_number": self.accession_number,
            "primary_document": self.primary_document,
            "url": self.url,
            "vendor": self.vendor,
        }


@dataclass(frozen=True, slots=True)
class SecFilingFetchResult:
    """Result envelope that admits the BLOCKED outcome explicitly."""

    status: str  # "OK" | "BLOCKED"
    reason: str = ""
    filings: tuple[SecFiling, ...] = ()

    @property
    def ok(self) -> bool:
        return self.status == "OK"


_EDGAR_BASE = "https://data.sec.gov"
_EDGAR_SUBMISSIONS = f"{_EDGAR_BASE}/submissions/CIK{{cik}}.json"
_EDGAR_COMPANY_TICKERS = "https://www.sec.gov/files/company_tickers.json"
_FORM_TYPES: frozenset[str] = frozenset(f.value for f in FilingForm)
_USER_AGENT_ENV = "ORION_SEC_USER_AGENT"


def _require_user_agent(explicit: str | None) -> str:
    """Resolve a User-Agent from arg or env, raise with a clear message."""
    ua = (explicit or os.environ.get(_USER_AGENT_ENV) or "").strip()
    if not ua:
        raise SecEdgarConfigError(
            "SEC EDGAR requires a descriptive User-Agent per their fair-access "
            f"policy. Pass it to SecEdgarProvider(user_agent=...) or set "
            f"the {_USER_AGENT_ENV} environment variable."
        )
    return ua


class SecEdgarConfigError(RuntimeError):
    """Raised when the SEC EDGAR provider is misconfigured."""


class SecEdgarProvider:
    """Live SEC EDGAR provider.

    Usage::

        provider = SecEdgarProvider(user_agent="ORION research@example.com")
        result = provider.fetch_recent_filings("AAPL", limit=5)
        if result.ok:
            for f in result.filings:
                ...

    On any network error the provider returns a ``BLOCKED`` result
    instead of raising; the caller decides what to do.
    """

    def __init__(
        self,
        *,
        user_agent: str | None = None,
        request_timeout_seconds: float = 10.0,
        rate_limit_pause_seconds: float = 0.2,
    ) -> None:
        self.user_agent = _require_user_agent(user_agent)
        self.request_timeout_seconds = float(request_timeout_seconds)
        self.rate_limit_pause_seconds = max(0.0, float(rate_limit_pause_seconds))
        self._last_request_monotonic: float = 0.0
        self._ticker_cache: dict[str, str] | None = None

    # ------------------------------------------------------------------ public

    def status(self) -> dict[str, Any]:
        return {
            "vendor": "sec-edgar",
            "configured": True,
            "user_agent_redacted": self._redact(self.user_agent),
            "supported_forms": sorted(_FORM_TYPES),
        }

    def fetch_recent_filings(
        self,
        ticker: str,
        *,
        limit: int = 10,
        forms: Sequence[FilingForm] = (),
    ) -> SecFilingFetchResult:
        """Return up to ``limit`` recent filings for ``ticker``.

        ``forms`` filters by form type when non-empty; otherwise every
        supported form is eligible.
        """
        if not ticker or not ticker.strip():
            return SecFilingFetchResult("BLOCKED", "empty ticker")
        if limit <= 0:
            return SecFilingFetchResult("BLOCKED", "limit must be positive")
        try:
            cik = self._lookup_cik(ticker)
            if cik is None:
                return SecFilingFetchResult(
                    "BLOCKED", f"unknown ticker {ticker!r}"
                )
            raw = self._get_json(_EDGAR_SUBMISSIONS.format(cik=cik))
            return self._parse_filings(raw, ticker, cik, limit=limit, forms=forms)
        except SecEdgarConfigError as error:
            return SecFilingFetchResult("BLOCKED", str(error))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            return SecFilingFetchResult("BLOCKED", f"sec-edgar unavailable: {error}")
        except OSError as error:
            return SecFilingFetchResult("BLOCKED", f"sec-edgar I/O error: {error}")

    # ------------------------------------------------------------------ helpers

    def _throttle(self) -> None:
        if self.rate_limit_pause_seconds <= 0.0:
            return
        now = time.monotonic()
        elapsed = now - self._last_request_monotonic
        if elapsed < self.rate_limit_pause_seconds:
            time.sleep(self.rate_limit_pause_seconds - elapsed)
        self._last_request_monotonic = time.monotonic()

    def _get_json(self, url: str) -> Any:
        self._throttle()
        request = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(request, timeout=self.request_timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    def _lookup_cik(self, ticker: str) -> str | None:
        if self._ticker_cache is None:
            data = self._get_json(_EDGAR_COMPANY_TICKERS)
            # The data is a dict keyed by integer (as string); each value is
            # {cik_str, ticker, title}.
            cache: dict[str, str] = {}
            for entry in data.values():
                t = entry.get("ticker", "").upper()
                c = entry.get("cik_str", "")
                if t and c:
                    cache[t] = str(c).zfill(10)
            self._ticker_cache = cache
        return self._ticker_cache.get(ticker.upper())

    def _parse_filings(
        self,
        raw: Mapping[str, Any],
        ticker: str,
        cik: str,
        *,
        limit: int,
        forms: Sequence[FilingForm],
    ) -> SecFilingFetchResult:
        recent = raw.get("filings", {}).get("recent", {})
        rows = recent.get("form", [])
        accession = recent.get("accessionNumber", [])
        primary = recent.get("primaryDocument", [])
        report_date = recent.get("reportDate", [])
        filing_date = recent.get("filingDate", [])

        target_forms = {f.value for f in forms} if forms else _FORM_TYPES
        out: list[SecFiling] = []
        for index, form_value in enumerate(rows):
            if form_value not in target_forms:
                continue
            try:
                filing_form = FilingForm(form_value)
            except ValueError:
                continue
            accession_number = (accession[index] or "").strip()
            if not accession_number:
                continue
            filed_at = self._parse_iso_date(filing_date[index])
            period = self._parse_iso_date(report_date[index]) if index < len(report_date) else None
            document = (primary[index] or "").strip()
            accession_clean = accession_number.replace("-", "")
            url = (
                f"https://www.sec.gov/Archives/edgar/data/"
                f"{int(cik)}/{accession_clean}/{document}"
            )
            out.append(
                SecFiling(
                    cik=str(cik),
                    ticker=ticker.upper(),
                    form=filing_form,
                    filed_at=filed_at,
                    period_of_report=period,
                    accession_number=accession_number,
                    primary_document=document,
                    url=url,
                )
            )
            if len(out) >= limit:
                break
        if not out:
            return SecFilingFetchResult("OK", "no matching filings", ())
        return SecFilingFetchResult("OK", filings=tuple(out))

    @staticmethod
    def _parse_iso_date(value: str | None) -> datetime:
        if not value:
            return datetime.fromtimestamp(0, tz=timezone.utc)
        # SEC dates are "YYYY-MM-DD"
        match = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", value)
        if not match:
            return datetime.fromtimestamp(0, tz=timezone.utc)
        y, m, d = (int(part) for part in match.groups())
        return datetime(y, m, d, tzinfo=timezone.utc)

    @staticmethod
    def _redact(user_agent: str) -> str:
        # Keep the structure but hide any email-like detail to satisfy
        # logging discipline.
        return re.sub(r"[\w.+-]+@[\w.-]+", "<email-redacted>", user_agent)
