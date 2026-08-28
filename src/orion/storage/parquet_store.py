"""Time-series store with a parquet-or-CSV back end.

When ``pyarrow`` is installed, the store writes real parquet files;
otherwise it falls back to CSV with the same logical API so the
zero-dep story remains intact.  The choice is made at module import
time and is *advisory*: every read uses whichever file is on disk
for the given ``version_id``.

Each frame is keyed by ``(symbol, version_id)``; the version id
makes every snapshot a content-addressed artefact and lets the rest
of ORION reason about provenance without joining tables.

The store is *opt-in*: instantiating this class is the only way to
persist anything.  When the store is not configured, every
component of ORION continues to work in memory.
"""

from __future__ import annotations

import csv
import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence

try:
    import pyarrow as pa  # type: ignore[import-not-found]
    import pyarrow.parquet as pq  # type: ignore[import-not-found]

    _HAS_PARQUET = True
except ImportError:  # pragma: no cover - exercised when pyarrow is absent
    pa = None  # type: ignore[assignment]
    pq = None  # type: ignore[assignment]
    _HAS_PARQUET = False


@dataclass(frozen=True, slots=True)
class TimeSeriesFrame:
    """An in-memory frame of timestamped rows.

    Attributes
    ----------
    symbol:
        Asset symbol this frame belongs to.
    version_id:
        Provenance / version identifier.  Distinct versions of the
        same symbol can be stored side-by-side.
    columns:
        Ordered column names.  ``ts`` is always present.
    rows:
        Sequence of dicts, one per timestamp.  Every row must
        contain the keys listed in ``columns``.
    """

    symbol: str
    version_id: str
    columns: tuple[str, ...]
    rows: tuple[Mapping[str, object], ...]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dicts(self) -> list[dict[str, object]]:
        return [dict(row) for row in self.rows]


def _row_to_csv(rows: Iterable[Mapping[str, object]], columns: Sequence[str]) -> Iterable[list[str]]:
    for row in rows:
        out: list[str] = []
        for col in columns:
            value = row.get(col)
            if value is None:
                out.append("")
            elif isinstance(value, (dict, list)):
                out.append(json.dumps(value, default=str))
            else:
                out.append(str(value))
        yield out


class ParquetStore:
    """Append-only time-series store with parquet-or-CSV back end.

    The store is keyed by ``(symbol, version_id)``; calls to
    :meth:`write_frame` create a new file each time.  This makes
    every snapshot a content-addressed artefact and avoids the
    need for an embedded index.

    Parameters
    ----------
    root:
        Directory under which frame files are written.  Created
        on first write.
    prefer_parquet:
        When ``True`` (the default) and ``pyarrow`` is available,
        write parquet; otherwise fall back to CSV.  When
        ``False``, always write CSV.  Reading is best-effort:
        the reader tries parquet first, then CSV.
    """

    def __init__(self, root: str | Path, *, prefer_parquet: bool = True) -> None:
        self._root = Path(root)
        self._prefer_parquet = prefer_parquet and _HAS_PARQUET
        self._lock = threading.RLock()
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def has_parquet(self) -> bool:
        return _HAS_PARQUET

    @property
    def using_parquet(self) -> bool:
        return self._prefer_parquet

    # ---- writes -------------------------------------------------------

    def write_frame(self, frame: TimeSeriesFrame) -> Path:
        """Persist ``frame`` and return the path on disk."""
        with self._lock:
            if self._prefer_parquet:
                return self._write_parquet(frame)
            return self._write_csv(frame)

    # ---- reads --------------------------------------------------------

    def read_frame(self, symbol: str, version_id: str) -> TimeSeriesFrame | None:
        """Read a previously-written frame.  Returns ``None`` if no
        such frame is on disk in either parquet or CSV form.
        """
        with self._lock:
            for reader in (self._read_parquet, self._read_csv):
                try:
                    frame = reader(symbol, version_id)
                except FileNotFoundError:
                    continue
                if frame is not None:
                    return frame
        return None

    def list_versions(self, symbol: str) -> tuple[str, ...]:
        """List the version ids on disk for ``symbol`` (any back end)."""
        out: set[str] = set()
        prefix = f"{_safe(symbol)}{_VERSION_SEPARATOR}"
        for ext in (".parquet", ".csv"):
            for path in self._root.glob(f"{prefix}*{ext}"):
                stem = path.stem
                if not stem.startswith(prefix):
                    continue
                out.add(stem[len(prefix):])
        return tuple(sorted(out))

    # ---- back ends ----------------------------------------------------

    def _path(self, symbol: str, version_id: str, ext: str) -> Path:
        return self._root / f"{_safe(symbol)}{_VERSION_SEPARATOR}{_safe(version_id)}{ext}"

    def _write_parquet(self, frame: TimeSeriesFrame) -> Path:
        path = self._path(frame.symbol, frame.version_id, ".parquet")
        table = pa.table({col: [row.get(col) for row in frame.rows] for col in frame.columns})
        pq.write_table(table, str(path))
        return path

    def _write_csv(self, frame: TimeSeriesFrame) -> Path:
        path = self._path(frame.symbol, frame.version_id, ".csv")
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(frame.columns)
            for line in _row_to_csv(frame.rows, frame.columns):
                writer.writerow(line)
        return path

    def _read_parquet(self, symbol: str, version_id: str) -> TimeSeriesFrame | None:
        path = self._path(symbol, version_id, ".parquet")
        if not path.exists():
            return None
        table = pq.read_table(str(path))
        columns = tuple(table.column_names)
        rows: list[Mapping[str, object]] = []
        for batch in table.to_batches():
            data = batch.to_pydict()
            n = len(next(iter(data.values()), []))
            for i in range(n):
                rows.append({col: data[col][i] for col in columns})
        return TimeSeriesFrame(
            symbol=symbol,
            version_id=version_id,
            columns=columns,
            rows=tuple(rows),
        )

    def _read_csv(self, symbol: str, version_id: str) -> TimeSeriesFrame | None:
        path = self._path(symbol, version_id, ".csv")
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            columns = tuple(reader.fieldnames or ())
            rows = [dict(row) for row in reader]
        return TimeSeriesFrame(
            symbol=symbol,
            version_id=version_id,
            columns=columns,
            rows=tuple(rows),
        )


_VERSION_SEPARATOR = "__v__"


def _safe(value: str) -> str:
    """Sanitise a string for use as a filename component."""
    return "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in value)


def new_version_id() -> str:
    """Generate a fresh, opaque version id (used as the ``version_id``
    field on every :class:`TimeSeriesFrame` and the
    :class:`orion.storage.SqliteStore`).
    """
    return uuid.uuid4().hex


__all__ = ["ParquetStore", "TimeSeriesFrame", "new_version_id"]
