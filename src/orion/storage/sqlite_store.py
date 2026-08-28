"""SQLite-backed metadata store.

A small, stdlib-only persistence layer for ORION metadata: experiments,
decisions, memory items, predictions, orders, fills, portfolio
states, model versions, research, provenance, audit events.  The
schema is created on first open; every record carries a
``version_id`` so the rest of ORION can reason about provenance
without needing a separate versioning system.

The store is *opt-in*: instantiating this class is the only way to
persist anything.  When the store is not configured, every
component of ORION continues to work in memory.

The :class:`SqliteStore` is thread-safe for the common write
pattern (single connection, serialized writes via an internal lock).
Heavy concurrent workloads should switch to a connection pool, but
that's not in scope for the zero-dep baseline.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_DEFAULT_SCHEMA: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS experiments (
        id          TEXT PRIMARY KEY,
        version_id  TEXT NOT NULL,
        payload     TEXT NOT NULL,
        created_at  TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS decisions (
        id          TEXT PRIMARY KEY,
        version_id  TEXT NOT NULL,
        payload     TEXT NOT NULL,
        created_at  TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS predictions (
        id          TEXT PRIMARY KEY,
        version_id  TEXT NOT NULL,
        payload     TEXT NOT NULL,
        created_at  TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS orders (
        id          TEXT PRIMARY KEY,
        version_id  TEXT NOT NULL,
        payload     TEXT NOT NULL,
        created_at  TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fills (
        id          TEXT PRIMARY KEY,
        version_id  TEXT NOT NULL,
        payload     TEXT NOT NULL,
        created_at  TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS model_versions (
        id          TEXT PRIMARY KEY,
        version_id  TEXT NOT NULL,
        payload     TEXT NOT NULL,
        created_at  TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_events (
        id          TEXT PRIMARY KEY,
        version_id  TEXT NOT NULL,
        payload     TEXT NOT NULL,
        created_at  TEXT NOT NULL
    )
    """,
)


@dataclass
class Record:
    """A single record returned by a query.

    Attributes
    ----------
    id:
        Stable opaque identifier for the row.
    version_id:
        Provenance / version identifier.  Every record in ORION
        carries one so we can answer "which version of the
        subsystem produced this?" without joining tables.
    data:
        Arbitrary JSON-compatible mapping.  Use this for fields
        that don't have a dedicated column.
    created_at:
        ISO-8601 UTC timestamp.
    """

    id: str
    version_id: str
    data: Mapping[str, Any]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SqliteStore:
    """A small SQLite-backed metadata store.

    The store auto-creates the schema on first open.  Writes are
    serialised by a single re-entrant lock; concurrent readers are
    safe.

    Examples
    --------
    >>> store = SqliteStore(":memory:")
    >>> store.insert("decisions", {"asset": "AAPL", "action": "BUY"})
    '...'
    >>> store.query("decisions")
    [Record(...)]
    """

    def __init__(self, path: str | Path) -> None:
        self._path = str(path)
        # ``check_same_thread=False`` allows the connection to be
        # shared across threads; the lock below serialises writes.
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock:
            for ddl in _DEFAULT_SCHEMA:
                self._conn.execute(ddl)
            self._conn.commit()

    # ---- writes -------------------------------------------------------

    def insert(
        self,
        table: str,
        data: Mapping[str, Any],
        *,
        version_id: str | None = None,
        id: str | None = None,
    ) -> str:
        """Insert one row; returns the row id.

        The mapping may contain any JSON-serialisable keys; the
        full record is stored as a JSON payload column.  Queries
        filter on payload fields via :func:`json_extract`.
        """
        if not _is_valid_table(table):
            raise ValueError(f"unknown table: {table!r}")
        record_id = id or uuid.uuid4().hex
        version = version_id or uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat()
        payload = json.dumps(dict(data), default=str, sort_keys=True)
        sql = (
            f"INSERT INTO {table} (id, version_id, payload, created_at) "
            f"VALUES (?, ?, ?, ?)"
        )
        with self._lock:
            self._conn.execute(sql, (record_id, version, payload, now))
            self._conn.commit()
        return record_id

    # ---- reads --------------------------------------------------------

    def query(
        self,
        table: str,
        *,
        where: Mapping[str, Any] | None = None,
        limit: int | None = None,
    ) -> list[Record]:
        if not _is_valid_table(table):
            raise ValueError(f"unknown table: {table!r}")
        sql = f"SELECT id, version_id, payload, created_at FROM {table}"
        params: list[Any] = []
        if where:
            clauses = []
            for col, val in where.items():
                clauses.append(f"json_extract(payload, '$.{col}') = ?")
                params.append(_coerce(val))
            sql += " WHERE " + " AND ".join(clauses)
        if limit is not None:
            sql += f" LIMIT {int(limit)}"
        with self._lock:
            cur = self._conn.execute(sql, params)
            rows = cur.fetchall()
        return [
            Record(
                id=row["id"],
                version_id=row["version_id"],
                data=json.loads(row["payload"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def count(self, table: str, *, where: Mapping[str, Any] | None = None) -> int:
        if not _is_valid_table(table):
            raise ValueError(f"unknown table: {table!r}")
        sql = f"SELECT COUNT(*) AS n FROM {table}"
        params: list[Any] = []
        if where:
            clauses = []
            for col, val in where.items():
                clauses.append(f"json_extract(payload, '$.{col}') = ?")
                params.append(_coerce(val))
            sql += " WHERE " + " AND ".join(clauses)
        with self._lock:
            cur = self._conn.execute(sql, params)
            return int(cur.fetchone()["n"])

    # ---- maintenance --------------------------------------------------

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> "SqliteStore":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


# ---- helpers ------------------------------------------------------------


_VALID_TABLES: frozenset[str] = frozenset(
    {
        "experiments",
        "decisions",
        "predictions",
        "orders",
        "fills",
        "model_versions",
        "audit_events",
    }
)


def _is_valid_table(table: str) -> bool:
    return table in _VALID_TABLES


def _coerce(value: Any) -> Any:
    """Coerce a Python value into something sqlite can bind.

    Booleans, ``None``, and primitives are passed through.  Other
    objects are serialised as JSON so the ``json_extract`` predicate
    still works for nested values.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return json.dumps(value, default=str)


__all__ = ["Record", "SqliteStore"]
