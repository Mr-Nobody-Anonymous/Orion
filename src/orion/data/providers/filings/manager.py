"""Filings manager: aggregates SEC, news, and earnings providers (P1-5).

The :class:`FilingsManager` is the single entry point that the rest of
ORION uses. It hides the per-vendor choice (live vs reference) and
applies a single point-in-time discipline on top of the three
providers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from ...contracts import Asset, NewsEvent
from .earnings import EarningsCall, EarningsCallProvider, EarningsCallResult
from .news import NewsFetchResult, NewsItem, NewsProvider
from .reference import (
    ReferenceEarningsProvider,
    ReferenceNewsProvider,
    ReferenceSecEdgarProvider,
)
from .sec_edgar import (
    FilingForm,
    SecEdgarProvider,
    SecFiling,
    SecFilingFetchResult,
)


@dataclass(frozen=True, slots=True)
class FilingsStatus:
    sec: dict[str, Any]
    news: dict[str, Any]
    earnings: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {"sec": self.sec, "news": self.news, "earnings": self.earnings}


@dataclass(frozen=True, slots=True)
class FilingsBundle:
    """Combined filings result for a single asset at a single point in time.

    The bundle is intentionally read-only and immutable: downstream
    components reason about evidence in a value-oriented way.
    """

    asset: Asset
    as_of: datetime
    sec: SecFilingFetchResult
    news: NewsFetchResult
    earnings: EarningsCallResult

    def as_dict(self) -> dict[str, Any]:
        return {
            "asset": self.asset.symbol,
            "as_of": self.as_of.isoformat(),
            "sec": {"status": self.sec.status, "filings": [f.as_dict() for f in self.sec.filings]},
            "news": {"status": self.news.status, "items": [i.as_dict() for i in self.news.items]},
            "earnings": {
                "status": self.earnings.status,
                "calls": [c.as_dict() for c in self.earnings.calls],
            },
        }

    def news_events(self) -> list[NewsEvent]:
        return [item.to_event() for item in self.news.items]


class FilingsManager:
    """Aggregator behind which any combination of providers may sit.

    Construct with any subset of providers; absent providers are
    treated as permanently BLOCKED. The point-in-time discipline is
    applied here: callers may pass ``as_of`` and the manager only
    returns records whose ``vendor_release_time`` is at or before
    ``as_of``.
    """

    def __init__(
        self,
        *,
        sec: SecEdgarProvider | ReferenceSecEdgarProvider | None = None,
        news: NewsProvider | ReferenceNewsProvider | None = None,
        earnings: EarningsCallProvider | ReferenceEarningsProvider | None = None,
    ) -> None:
        self._sec = sec
        self._news = news
        self._earnings = earnings

    # ------------------------------------------------------------------ public

    def status(self) -> FilingsStatus:
        return FilingsStatus(
            sec=self._sec.status() if self._sec is not None else {"configured": False},
            news=self._news.status() if self._news is not None else {"configured": False},
            earnings=self._earnings.status() if self._earnings is not None else {"configured": False},
        )

    def fetch(
        self,
        asset: Asset,
        *,
        as_of: datetime | None = None,
        news_query: str | None = None,
        sec_forms: Sequence[FilingForm] = (),
        sec_limit: int = 5,
        news_limit: int = 25,
        earnings_limit: int = 4,
    ) -> FilingsBundle:
        as_of = as_of or datetime.now(tz=timezone.utc)
        sec_result = self._fetch_sec(asset, limit=sec_limit, forms=sec_forms, as_of=as_of)
        news_result = self._fetch_news(
            asset,
            query=news_query or asset.symbol,
            limit=news_limit,
            as_of=as_of,
        )
        earnings_result = self._fetch_earnings(asset, limit=earnings_limit, as_of=as_of)
        return FilingsBundle(
            asset=asset,
            as_of=as_of,
            sec=sec_result,
            news=news_result,
            earnings=earnings_result,
        )

    # ------------------------------------------------------------------ helpers

    def _fetch_sec(
        self,
        asset: Asset,
        *,
        limit: int,
        forms: Sequence[FilingForm],
        as_of: datetime,
    ) -> SecFilingFetchResult:
        if self._sec is None:
            return SecFilingFetchResult("BLOCKED", "sec provider not configured")
        result = self._sec.fetch_recent_filings(asset.symbol, limit=limit, forms=forms)
        if not result.ok:
            return result
        # Point-in-time filter: only keep filings whose release time is
        # at or before ``as_of``. This prevents ORION from "knowing" a
        # filing that was published after the decision timestamp.
        kept = tuple(f for f in result.filings if f.filed_at <= as_of)
        if len(kept) == len(result.filings):
            return result
        return SecFilingFetchResult(
            result.status,
            reason=result.reason,
            filings=kept,
        )

    def _fetch_news(
        self,
        asset: Asset,
        *,
        query: str,
        limit: int,
        as_of: datetime,
    ) -> NewsFetchResult:
        if self._news is None:
            return NewsFetchResult("BLOCKED", "news provider not configured")
        result = self._news.fetch(query, asset=asset, limit=limit)
        if not result.ok:
            return result
        kept = tuple(
            item for item in result.items
            if (item.vendor_release_time or item.published_at) <= as_of
        )
        if len(kept) == len(result.items):
            return result
        return NewsFetchResult(result.status, reason=result.reason, items=kept)

    def _fetch_earnings(
        self,
        asset: Asset,
        *,
        limit: int,
        as_of: datetime,
    ) -> EarningsCallResult:
        if self._earnings is None:
            return EarningsCallResult("BLOCKED", "earnings provider not configured")
        result = self._earnings.fetch(asset.symbol, limit=limit)
        if not result.ok:
            return result
        kept = tuple(c for c in result.calls if c.call_at <= as_of)
        if len(kept) == len(result.calls):
            return result
        return EarningsCallResult(result.status, reason=result.reason, calls=kept)



