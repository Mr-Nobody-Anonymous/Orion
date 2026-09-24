from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable
from urllib.parse import quote_plus
from urllib.request import Request, urlopen


@dataclass(frozen=True, slots=True)
class ResearchSource:
    title: str
    url: str
    source: str
    abstract: str = ""
    published_at: str | None = None
    authors: tuple[str, ...] = ()
    cited_by_count: int = 0


class ResearchDiscovery:
    """Public scholarly discovery through OpenAlex; network failures are reported, never hidden."""

    def __init__(self, fetcher: Callable[[str], bytes] | None = None) -> None:
        self._fetcher = fetcher or self._fetch

    @staticmethod
    def _fetch(url: str) -> bytes:
        request = Request(url, headers={"User-Agent": "ORION-research/0.1 (public scholarly metadata)"})
        with urlopen(request, timeout=10) as response:
            return response.read()

    def discover_papers(self, topic: str, *, limit: int = 5) -> tuple[ResearchSource, ...]:
        if not topic.strip():
            raise ValueError("topic is required")
        if not 1 <= limit <= 25:
            raise ValueError("limit must be between 1 and 25")
        url = f"https://api.openalex.org/works?search={quote_plus(topic)}&per-page={limit}"
        payload = json.loads(self._fetcher(url).decode("utf-8"))
        sources: list[ResearchSource] = []
        for work in payload.get("results", []):
            primary = work.get("primary_location") or {}
            landing = primary.get("landing_page_url") or work.get("doi") or ""
            if not landing:
                continue
            authors = tuple(author.get("author", {}).get("display_name", "") for author in work.get("authorships", []))
            sources.append(ResearchSource(
                title=work.get("display_name", "Untitled"), url=landing, source="OpenAlex",
                abstract=self._reconstruct_abstract(work.get("abstract_inverted_index")),
                published_at=work.get("publication_date"), authors=tuple(author for author in authors if author),
                cited_by_count=int(work.get("cited_by_count", 0)),
            ))
        return tuple(sources)

    @staticmethod
    def _reconstruct_abstract(index: dict[str, list[int]] | None) -> str:
        if not index:
            return ""
        words = sorted(((position, word) for word, positions in index.items() for position in positions))
        return " ".join(word for _, word in words)


@dataclass(frozen=True, slots=True)
class ResearchReport:
    question: str
    sources: tuple[ResearchSource, ...]
    evidence_status: str
    generated_at: datetime


def build_research_report(question: str, sources: tuple[ResearchSource, ...]) -> ResearchReport:
    status = "SUFFICIENT_METADATA" if len(sources) >= 2 else "INSUFFICIENT_EVIDENCE"
    return ResearchReport(question, sources, status, datetime.now(timezone.utc))
