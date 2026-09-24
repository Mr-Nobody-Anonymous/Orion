"""Company Intelligence and Credit Analytics.

Provides deep corporate relationship tracking (competitors, suppliers, customers),
geographic exposure decomposition, and institutional credit metrics.
Lives in the Intelligence plane.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Mapping, Sequence

from ...data.contracts import Company


@dataclass(frozen=True, slots=True)
class CreditMetrics:
    total_debt: Decimal
    cash_and_equivalents: Decimal
    net_debt: Decimal
    ebitda: Decimal
    interest_expense: Decimal
    net_debt_to_ebitda: Decimal
    interest_coverage: Decimal
    is_investment_grade_estimate: bool


@dataclass(frozen=True, slots=True)
class CompanyIntelligenceProfile:
    company: Company
    executives: tuple[tuple[str, str], ...] = ()  # (Name, Role)
    competitors: tuple[str, ...] = ()  # Ticker symbols
    suppliers: tuple[str, ...] = ()  # Ticker symbols
    key_customers: tuple[str, ...] = ()  # Ticker symbols
    geographic_revenue_pct: Mapping[str, Decimal] = field(default_factory=dict)
    credit_metrics: CreditMetrics | None = None


class CompanyIntelligenceEngine:
    """Manages company profiles and computes balance sheet credit health."""

    @staticmethod
    def calculate_credit_metrics(
        total_debt: Decimal,
        cash: Decimal,
        ebitda: Decimal,
        interest_expense: Decimal,
    ) -> CreditMetrics:
        net_debt = total_debt - cash
        net_debt_to_ebitda = net_debt / ebitda if ebitda != 0 else Decimal("999.0")
        interest_coverage = ebitda / interest_expense if interest_expense != 0 else Decimal("999.0")

        # Basic proxy: Net Debt/EBITDA < 3.0 and Interest Coverage > 4.0 indicates investment grade
        is_ig = (net_debt_to_ebitda < Decimal("3.0")) and (interest_coverage > Decimal("4.0"))

        return CreditMetrics(
            total_debt=total_debt,
            cash_and_equivalents=cash,
            net_debt=net_debt,
            ebitda=ebitda,
            interest_expense=interest_expense,
            net_debt_to_ebitda=net_debt_to_ebitda,
            interest_coverage=interest_coverage,
            is_investment_grade_estimate=is_ig,
        )
