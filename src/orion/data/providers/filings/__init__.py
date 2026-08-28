"""ORION news / SEC / earnings ingestion (P1-5 of TODO.md).

This package provides real, executable providers for the broader
fundamentals-and-news ingestion story. Providers follow the ORION
principle of admitting ignorance: they never invent evidence, and on
network outage or missing credentials they return an explicit BLOCKED
result.

All providers are implemented in three layers:

1. **Reference implementations** (no I/O, deterministic, used as the
   test back-end and as an offline baseline). These live in
   :mod:`orion.data.providers.filings.reference` and can be instantiated
   out of the box.

2. **Live adapters** that target the real public APIs:

   - :class:`SecEdgarProvider` — SEC EDGAR for 10-K, 10-Q, 8-K, Form 4
     (insider), 13F (institutional holdings), DEF 14A (proxy).
   - :class:`NewsProvider` — public RSS-based news aggregator.
   - :class:`EarningsCallProvider` — earnings call transcript metadata.

3. A **manager** (:class:`FilingsManager`) that aggregates the three
   providers behind a single ``fetch`` entrypoint and applies the
   point-in-time / vendor-release-time discipline the rest of ORION
   expects.

Credentials are not required for the reference implementations; the live
adapters require ``ORION_SEC_USER_AGENT`` (EDGAR requires a real
User-Agent per their fair-access policy) and refuse to construct
otherwise.
"""

from __future__ import annotations

from .reference import (
    ReferenceEarningsProvider,
    ReferenceNewsProvider,
    ReferenceSecEdgarProvider,
)
from .sec_edgar import (
    FilingForm,
    SecEdgarConfigError,
    SecEdgarProvider,
    SecFiling,
    SecFilingFetchResult,
)
from .news import NewsProvider, NewsItem, NewsFetchResult
from .earnings import EarningsCallProvider, EarningsCall, EarningsCallResult
from .manager import FilingsManager, FilingsStatus, FilingsBundle

__all__ = [
    "ReferenceSecEdgarProvider",
    "ReferenceNewsProvider",
    "ReferenceEarningsProvider",
    "SecEdgarProvider",
    "SecEdgarConfigError",
    "SecFiling",
    "FilingForm",
    "SecFilingFetchResult",
    "NewsProvider",
    "NewsItem",
    "NewsFetchResult",
    "EarningsCallProvider",
    "EarningsCall",
    "EarningsCallResult",
    "FilingsManager",
    "FilingsStatus",
    "FilingsBundle",
]
