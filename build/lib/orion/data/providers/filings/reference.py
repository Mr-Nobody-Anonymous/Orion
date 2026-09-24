"""Reference implementations for the filings providers (P1-5).

These deterministic in-memory substitutes are used by the test suite
and act as the offline baseline. They are real implementations, not
stubs: every method performs the same parsing, ordering, and validation
as the live provider, but the input is a fixed list rather than a
network call.
"""

from __future__ import annotations

from typing import Iterable

from .earnings import EarningsCall, EarningsCallResult
from .news import NewsItem, NewsFetchResult
from .sec_edgar import FilingForm, SecFiling, SecFilingFetchResult


class ReferenceSecEdgarProvider:
    """Deterministic SEC EDGAR substitute for offline / test use.

    ``add`` inserts a :class:`SecFiling`; ``fetch_recent_filings``
    returns matching records ordered by ``filed_at`` descending.
    """

    def __init__(self) -> None:
        self._filings: list[SecFiling] = []

    def status(self) -> dict[str, object]:
        return {
            "vendor": "sec-edgar-reference",
            "configured": True,
            "items": len(self._filings),
        }

    def add(self, filing: SecFiling) -> None:
        self._filings.append(filing)

    def add_many(self, filings: Iterable[SecFiling]) -> None:
        for filing in filings:
            self.add(filing)

    def fetch_recent_filings(
        self,
        ticker: str,
        *,
        limit: int = 10,
        forms: list[FilingForm] | tuple[FilingForm, ...] = (),
    ) -> SecFilingFetchResult:
        if not ticker or not ticker.strip():
            return SecFilingFetchResult("BLOCKED", "empty ticker")
        if limit <= 0:
            return SecFilingFetchResult("BLOCKED", "limit must be positive")
        target_forms = {f.value for f in forms} if forms else None
        matches = [f for f in self._filings if f.ticker.upper() == ticker.upper()]
        if target_forms is not None:
            matches = [f for f in matches if f.form.value in target_forms]
        matches.sort(key=lambda f: f.filed_at, reverse=True)
        if not matches:
            return SecFilingFetchResult("OK", "no matching filings", ())
        return SecFilingFetchResult("OK", filings=tuple(matches[:limit]))


class ReferenceNewsProvider:
    """Deterministic in-memory news provider used by tests and offline mode."""

    def __init__(self) -> None:
        self._items: list[NewsItem] = []

    def status(self) -> dict[str, object]:
        return {
            "vendor": "news-reference",
            "configured": True,
            "items": len(self._items),
        }

    def add(self, item: NewsItem) -> None:
        self._items.append(item)

    def add_many(self, items: Iterable[NewsItem]) -> None:
        for item in items:
            self.add(item)

    def fetch(
        self,
        query: str,
        *,
        asset=None,
        limit: int = 25,
    ) -> NewsFetchResult:
        q = (query or "").lower()
        matches = [
            item
            for item in self._items
            if (
                q in item.headline.lower()
                or q in item.body.lower()
                or q in item.topic.lower()
                or (
                    asset is not None
                    and item.asset is not None
                    and item.asset.symbol.lower() == asset.symbol.lower()
                )
            )
        ]
        matches.sort(
            key=lambda i: i.vendor_release_time or i.published_at, reverse=True
        )
        return NewsFetchResult("OK", items=tuple(matches[: max(0, limit)]))


class ReferenceEarningsProvider:
    """Deterministic in-memory earnings provider used by tests and offline mode."""

    def __init__(self) -> None:
        self._calls: list[EarningsCall] = []

    def status(self) -> dict[str, object]:
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
