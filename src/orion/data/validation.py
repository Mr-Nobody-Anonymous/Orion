from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from .contracts import MarketQuote


@dataclass(frozen=True, slots=True)
class QualityIssue:
    code: str
    message: str


class DataQualityValidator:
    def validate_quote(self, quote: MarketQuote, now: datetime | None = None) -> tuple[QualityIssue, ...]:
        issues: list[QualityIssue] = []
        if quote.bid <= 0 or quote.ask <= 0 or quote.last <= 0:
            issues.append(QualityIssue("NON_POSITIVE_PRICE", "prices must be positive"))
        if quote.bid > quote.ask:
            issues.append(QualityIssue("CROSSED_BOOK", "bid cannot exceed ask"))
        reference = now or datetime.now(timezone.utc)
        if quote.timestamp.tzinfo is None:
            issues.append(QualityIssue("NAIVE_TIMESTAMP", "timestamp must include timezone"))
        elif quote.timestamp > reference:
            issues.append(QualityIssue("FUTURE_TIMESTAMP", "timestamp cannot be in the future"))
        if quote.volume < Decimal("0"):
            issues.append(QualityIssue("NEGATIVE_VOLUME", "volume cannot be negative"))
        return tuple(issues)
