"""Public news ingestion for ORION (P1-5).

Two providers ship here:

- :class:`NewsProvider` — a real, public-RSS based news fetcher that
  uses Google News RSS as a free, unauthenticated public source for
  headline-level news with point-in-time timestamps. It is **strictly
  optional**: when the network is unavailable it returns a ``BLOCKED``
  result and never invents evidence.

- :class:`ReferenceNewsProvider` — a deterministic in-memory substitute
  used by the test suite and the offline baseline. It accepts items
  via :meth:`add` and re-orders them by ``vendor_release_time`` on
  every query, exactly like the live adapter.
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
from typing import Any, Iterable, Sequence

from ...contracts import Asset, NewsEvent


@dataclass(frozen=True, slots=True)
class NewsItem:
    """A point-in-time news item ready for the ORION pipeline."""

    headline: str
    body: str
    published_at: datetime
    asset: Asset | None
    source: str
    url: str
    vendor: str = "news-rss"
    vendor_release_time: datetime | None = None
    topic: str = ""

    def __post_init__(self) -> None:
        # When the caller does not give an explicit vendor_release_time,
        # default to the publication timestamp (most public RSS feeds
        # publish *at* release time).
        if self.vendor_release_time is None:
            object.__setattr__(self, "vendor_release_time", self.published_at)

    def as_dict(self) -> dict[str, Any]:
        return {
            "headline": self.headline,
            "body": self.body,
            "published_at": self.published_at.isoformat(),
            "asset": self.asset.symbol if self.asset is not None else None,
            "source": self.source,
            "url": self.url,
            "vendor": self.vendor,
            "vendor_release_time": (self.vendor_release_time or self.published_at).isoformat(),
            "topic": self.topic,
        }

    def to_event(self) -> NewsEvent:
        """Convert to ORION's canonical :class:`NewsEvent` contract."""
        return NewsEvent(
            headline=self.headline,
            body=self.body,
            published_at=self.published_at,
            asset=self.asset,
            source=self.source,
        )


@dataclass(frozen=True, slots=True)
class NewsFetchResult:
    status: str  # "OK" | "BLOCKED"
    reason: str = ""
    items: tuple[NewsItem, ...] = ()

    @property
    def ok(self) -> bool:
        return self.status == "OK"


class NewsProvider:
    """Live public-RSS news provider.

    No API key is required. Google News exposes unauthenticated RSS
    feeds at ``https://news.google.com/rss/search?q=...``; the
    provider parses the XML, extracts title/link/pubDate, and yields
    :class:`NewsItem` records with point-in-time timestamps.
    """

    _BASE = "https://news.google.com/rss/search"

    def __init__(
        self,
        *,
        request_timeout_seconds: float = 10.0,
        user_agent: str = "ORION/1.0 (news)",
    ) -> None:
        self.request_timeout_seconds = float(request_timeout_seconds)
        self.user_agent = str(user_agent)

    def status(self) -> dict[str, Any]:
        return {
            "vendor": "news-rss",
            "configured": True,
            "endpoint": self._BASE,
        }

    def fetch(
        self,
        query: str,
        *,
        asset: Asset | None = None,
        limit: int = 25,
    ) -> NewsFetchResult:
        if not query or not query.strip():
            return NewsFetchResult("BLOCKED", "empty query")
        if limit <= 0:
            return NewsFetchResult("BLOCKED", "limit must be positive")
        try:
            xml_text = self._fetch_rss(query)
        except (urllib.error.URLError, TimeoutError) as error:
            return NewsFetchResult("BLOCKED", f"news-rss unavailable: {error}")
        except OSError as error:
            return NewsFetchResult("BLOCKED", f"news-rss I/O error: {error}")
        except ET.ParseError as error:
            return NewsFetchResult("BLOCKED", f"news-rss parse error: {error}")
        items = self._parse(xml_text, asset=asset, topic=query, limit=limit)
        if not items:
            return NewsFetchResult("OK", "no matching items", ())
        return NewsFetchResult("OK", items=items)

    # ------------------------------------------------------------------ internals

    def _fetch_rss(self, query: str) -> str:
        url = f"{self._BASE}?{urllib.parse.urlencode({'q': query, 'hl': 'en-US', 'gl': 'US', 'ceid': 'US:en'})}"
        request = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(request, timeout=self.request_timeout_seconds) as response:
            return response.read().decode("utf-8", errors="replace")

    @staticmethod
    def _parse(xml_text: str, *, asset: Asset | None, topic: str, limit: int) -> tuple[NewsItem, ...]:
        root = ET.fromstring(xml_text)
        items: list[NewsItem] = []
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub = (item.findtext("pubDate") or "").strip()
            source = (item.findtext("source") or "unknown").strip() or "unknown"
            description = (item.findtext("description") or "").strip()
            # Strip the "<a href=...>source</a>" suffix that Google News
            # appends to descriptions; ORION never uses HTML as data.
            description = re.sub(r"<[^>]+>", "", description).strip()
            if not title or not link or not pub:
                continue
            try:
                published = parsedate_to_datetime(pub)
            except (TypeError, ValueError):
                continue
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            items.append(
                NewsItem(
                    headline=title,
                    body=description or title,
                    published_at=published,
                    asset=asset,
                    source=source,
                    url=link,
                    topic=topic,
                )
            )
        items.sort(key=lambda i: i.published_at, reverse=True)
        return tuple(items[:limit])


class ReferenceNewsProvider:
    """Deterministic in-memory news provider used by tests and offline mode.

    Items are returned in ``vendor_release_time`` order. Adding an item
    is the only way to populate the provider — there is no I/O.
    """

    def __init__(self) -> None:
        self._items: list[NewsItem] = []

    def status(self) -> dict[str, Any]:
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
        asset: Asset | None = None,
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
                or (asset is not None and item.asset is not None and item.asset.symbol.lower() == asset.symbol.lower())
            )
        ]
        matches.sort(key=lambda i: i.vendor_release_time or i.published_at, reverse=True)
        return NewsFetchResult("OK", items=tuple(matches[: max(0, limit)]))
