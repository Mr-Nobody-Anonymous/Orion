"""Point-in-time market-data layer.

This subpackage contains:

  * :mod:`.pit`              — point-in-time records and bundles
  * :mod:`.normalization`    — timestamp coercion, bad-tick filter, missing-data policy
  * :mod:`.lineage`          — data lineage records
  * :mod:`.versioning`       — versioned snapshots and a small local store
  * :mod:`.provider`         — :class:`MarketDataProvider` protocol + in-memory ref impl
"""

from .lineage import LineageRecord, hash_records, now_utc
from .normalization import (
    BadTickConfig,
    BadTickResult,
    MissingDataPolicy,
    fill_gaps,
    filter_bad_ticks,
    sort_by_time,
    to_utc,
)
from .pit import PITBundle, PITRecord
from .provider import (
    CorporateAction,
    FundamentalRow,
    InMemoryMarketDataProvider,
    MarketDataProvider,
    NewsItem,
    OHLCVRow,
)
from .versioning import DataVersion, LocalMarketDataStore, make_version

__all__ = [
    "BadTickConfig",
    "BadTickResult",
    "CorporateAction",
    "DataVersion",
    "FundamentalRow",
    "InMemoryMarketDataProvider",
    "LineageRecord",
    "LocalMarketDataStore",
    "MarketDataProvider",
    "MissingDataPolicy",
    "NewsItem",
    "OHLCVRow",
    "PITBundle",
    "PITRecord",
    "fill_gaps",
    "filter_bad_ticks",
    "hash_records",
    "make_version",
    "now_utc",
    "sort_by_time",
    "to_utc",
]
