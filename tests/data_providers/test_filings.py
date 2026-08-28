"""Tests for the P1-5 filings package."""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

from orion.data.contracts import Asset, AssetClass
from orion.data.providers.filings import (
    EarningsCallProvider,
    FilingsManager,
    NewsProvider,
    ReferenceEarningsProvider,
    ReferenceNewsProvider,
    ReferenceSecEdgarProvider,
    SecEdgarConfigError,
    SecEdgarProvider,
    SecFiling,
)
from orion.data.providers.filings.sec_edgar import FilingForm


def _ts(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


# ---------------------------------------------------------------- SecEdgarProvider


def test_sec_edgar_requires_user_agent() -> None:
    """No user-agent → misconfiguration error."""
    env = os.environ.pop("ORION_SEC_USER_AGENT", None)
    try:
        with pytest.raises(SecEdgarConfigError):
            SecEdgarProvider()
    finally:
        if env is not None:
            os.environ["ORION_SEC_USER_AGENT"] = env


def test_sec_edgar_status_includes_redacted_ua() -> None:
    provider = SecEdgarProvider(user_agent="ORION research@example.com")
    status = provider.status()
    assert status["configured"] is True
    assert "<email-redacted>" in status["user_agent_redacted"]
    assert "10-K" in status["supported_forms"]


def test_reference_sec_filings_returns_filings_sorted_by_filed_at() -> None:
    provider = ReferenceSecEdgarProvider()
    provider.add_many([
        SecFiling(
            cik="0000320193",
            ticker="AAPL",
            form=FilingForm.TEN_K,
            filed_at=_ts(2023, 11, 3),
            period_of_report=_ts(2023, 9, 30),
            accession_number="0000320193-23-000106",
            primary_document="aapl-20230930.htm",
            url="https://example/aapl-10k",
        ),
        SecFiling(
            cik="0000320193",
            ticker="AAPL",
            form=FilingForm.EIGHT_K,
            filed_at=_ts(2024, 2, 1),
            period_of_report=None,
            accession_number="0000320193-24-000007",
            primary_document="aapl-8k.htm",
            url="https://example/aapl-8k",
        ),
    ])
    result = provider.fetch_recent_filings("AAPL", limit=5)
    assert result.ok
    assert [f.form for f in result.filings] == [FilingForm.EIGHT_K, FilingForm.TEN_K]
    filtered = provider.fetch_recent_filings("AAPL", limit=5, forms=[FilingForm.TEN_K])
    assert {f.form for f in filtered.filings} == {FilingForm.TEN_K}


def test_reference_sec_filings_blocks_on_empty_inputs() -> None:
    provider = ReferenceSecEdgarProvider()
    assert provider.fetch_recent_filings("").status == "BLOCKED"
    assert provider.fetch_recent_filings("AAPL", limit=0).status == "BLOCKED"


# ---------------------------------------------------------------- NewsProvider


def test_reference_news_filters_by_query() -> None:
    from orion.data.providers.filings.news import NewsItem

    provider = ReferenceNewsProvider()
    aapl = Asset("AAPL", AssetClass.EQUITY)
    provider.add_many([
        NewsItem(
            headline="Apple beats Q4 estimates",
            body="Strong iPhone sales.",
            published_at=_ts(2024, 1, 5),
            asset=aapl,
            source="Example",
            url="https://example/aapl-1",
            topic="apple",
        ),
        NewsItem(
            headline="Microsoft cloud growth",
            body="Azure revenue up 25%.",
            published_at=_ts(2024, 1, 4),
            asset=Asset("MSFT", AssetClass.EQUITY),
            source="Example",
            url="https://example/msft-1",
            topic="microsoft",
        ),
    ])
    result = provider.fetch("apple")
    assert result.ok
    assert len(result.items) == 1
    assert result.items[0].asset.symbol == "AAPL"


def test_news_provider_live_constructor_works() -> None:
    provider = NewsProvider()
    assert provider.status()["configured"] is True


# ---------------------------------------------------------------- EarningsCallProvider


def test_reference_earnings_filters_by_ticker() -> None:
    from orion.data.providers.filings.earnings import EarningsCall

    provider = ReferenceEarningsProvider()
    provider.add_many([
        EarningsCall(
            ticker="AAPL",
            company="Apple",
            call_at=_ts(2024, 2, 1, 21, 0),
            quarter="Q1",
            fiscal_year=2024,
            url="",
        ),
        EarningsCall(
            ticker="MSFT",
            company="Microsoft",
            call_at=_ts(2024, 1, 25, 21, 0),
            quarter="Q2",
            fiscal_year=2024,
            url="",
        ),
    ])
    result = provider.fetch("AAPL")
    assert result.ok
    assert len(result.calls) == 1
    assert result.calls[0].ticker == "AAPL"


# ---------------------------------------------------------------- FilingsManager


def test_filings_manager_aggregates_status() -> None:
    manager = FilingsManager()
    status = manager.status()
    assert status.sec["configured"] is False
    assert status.news["configured"] is False
    assert status.earnings["configured"] is False


def test_filings_manager_blocks_missing_providers() -> None:
    manager = FilingsManager()
    bundle = manager.fetch(Asset("AAPL", AssetClass.EQUITY))
    assert bundle.sec.status == "BLOCKED"
    assert bundle.news.status == "BLOCKED"
    assert bundle.earnings.status == "BLOCKED"


def test_filings_manager_applies_point_in_time_filter() -> None:
    sec = ReferenceSecEdgarProvider()
    sec.add(
        SecFiling(
            cik="0000320193",
            ticker="AAPL",
            form=FilingForm.TEN_K,
            filed_at=_ts(2024, 1, 1),
            period_of_report=_ts(2023, 9, 30),
            accession_number="0000320193-24-000001",
            primary_document="aapl-10k.htm",
            url="https://example/aapl-10k",
        )
    )
    sec.add(
        SecFiling(
            cik="0000320193",
            ticker="AAPL",
            form=FilingForm.EIGHT_K,
            filed_at=_ts(2024, 6, 1),  # future relative to as_of
            period_of_report=None,
            accession_number="0000320193-24-000050",
            primary_document="aapl-8k.htm",
            url="https://example/aapl-8k-future",
        )
    )
    manager = FilingsManager(sec=sec, news=ReferenceNewsProvider(), earnings=ReferenceEarningsProvider())
    bundle = manager.fetch(Asset("AAPL", AssetClass.EQUITY), as_of=_ts(2024, 2, 1))
    assert bundle.sec.status == "OK"
    assert {f.form for f in bundle.sec.filings} == {FilingForm.TEN_K}


def test_filings_manager_emits_news_events() -> None:
    from orion.data.providers.filings.news import NewsItem

    news = ReferenceNewsProvider()
    news.add(
        NewsItem(
            headline="AAPL surges on strong earnings",
            body="Apple beats estimates.",
            published_at=_ts(2024, 1, 5),
            asset=Asset("AAPL", AssetClass.EQUITY),
            source="Example",
            url="https://example/aapl-1",
            topic="AAPL",
        )
    )
    manager = FilingsManager(sec=ReferenceSecEdgarProvider(), news=news, earnings=ReferenceEarningsProvider())
    bundle = manager.fetch(Asset("AAPL", AssetClass.EQUITY))
    assert len(bundle.news_events()) == 1
    assert bundle.news_events()[0].headline == "AAPL surges on strong earnings"
