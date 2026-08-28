"""ORION storage package (P1-4 of TODO.md).

The storage layer is *opt-in*.  The rest of ORION is in-memory by
default; instantiating an :class:`SqliteStore` or
:class:`ParquetStore` is the only way to persist anything.

The split mirrors the reviewer's recommendation:

  * :mod:`.sqlite_store`  — OLTP-style metadata: experiments,
                            decisions, memory, predictions, orders,
                            fills, portfolio states, model versions,
                            research, provenance, audit events.
  * :mod:`.parquet_store` — Time-series-ish market data.  When
                            ``pyarrow`` is installed, writes real
                            parquet; otherwise it falls back to CSV
                            with the same logical API.

Both stores carry a ``version_id`` on every record so the rest of
ORION can reason about provenance without needing a separate
versioning system.
"""

from .parquet_store import ParquetStore, TimeSeriesFrame, new_version_id
from .sqlite_store import SqliteStore

__all__ = [
    "ParquetStore",
    "SqliteStore",
    "TimeSeriesFrame",
    "new_version_id",
]
