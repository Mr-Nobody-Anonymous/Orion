"""Alpaca paper-trading configuration.

The paper environment is *deliberately* the only supported endpoint. Live
URLs and live credentials are rejected at construction time.
"""

from __future__ import annotations

from dataclasses import dataclass


PAPER_BASE_URL = "https://paper-api.alpaca.markets"
LIVE_BASE_URLS = frozenset({"https://api.alpaca.markets"})


@dataclass(frozen=True, slots=True)
class AlpacaConfig:
    api_key: str
    secret_key: str
    base_url: str = PAPER_BASE_URL
    data_feed: str = "iex"

    def __repr__(self) -> str:
        return (
            f"AlpacaConfig(api_key=***, secret_key=***, "
            f"base_url={self.base_url!r}, data_feed={self.data_feed!r})"
        )

    def __post_init__(self) -> None:
        if not self.api_key:
            raise ValueError("api_key is required")
        if not self.secret_key:
            raise ValueError("secret_key is required")
        if self.base_url.rstrip("/") in LIVE_BASE_URLS:
            raise ValueError(
                "live Alpaca endpoints are not permitted by ORION; only paper-api is allowed"
            )
        if self.base_url.rstrip("/") != PAPER_BASE_URL:
            raise ValueError(
                f"only the paper endpoint {PAPER_BASE_URL!r} is permitted, got {self.base_url!r}"
            )


def is_paper_base_url(url: str) -> bool:
    return url.rstrip("/") == PAPER_BASE_URL
