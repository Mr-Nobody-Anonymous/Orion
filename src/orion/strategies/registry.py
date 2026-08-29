r"""ORION Strategy Registry (Architectural Audit §21).

The registry owns **strategy lineage**: every strategy version is
immutable, records the full chain (dataset -> features -> model ->
prediction -> strategy -> risk -> backtest -> walk-forward -> paper ->
production), and moves through an audited lifecycle:

    EXPERIMENTAL -> VALIDATING -> APPROVED -> PRODUCTION -> RETIRED
                        \-> REJECTED

Versions are never overwritten: registering the same name again creates
a **new** immutable version. Promotion to ``PRODUCTION`` is denied
unless the version is already ``APPROVED``, so nothing silently deploys.
A JSONL snapshot under ``artifacts/strategies/`` makes the registry
durable and replayable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping, Sequence

DEFAULT_ROOT = Path("artifacts/strategies")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StrategyStatus(str, Enum):
    EXPERIMENTAL = "experimental"
    VALIDATING = "validating"
    APPROVED = "approved"
    PRODUCTION = "production"
    RETIRED = "retired"
    REJECTED = "rejected"


_ALLOWED_TRANSITIONS: dict[StrategyStatus, frozenset[StrategyStatus]] = {
    StrategyStatus.EXPERIMENTAL: frozenset({StrategyStatus.VALIDATING, StrategyStatus.REJECTED}),
    StrategyStatus.VALIDATING: frozenset({StrategyStatus.APPROVED, StrategyStatus.RETIRED, StrategyStatus.REJECTED}),
    StrategyStatus.APPROVED: frozenset({StrategyStatus.PRODUCTION, StrategyStatus.RETIRED, StrategyStatus.REJECTED}),
    StrategyStatus.PRODUCTION: frozenset({StrategyStatus.RETIRED}),
    StrategyStatus.RETIRED: frozenset(),
    StrategyStatus.REJECTED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class StrategyVersion:
    """One immutable strategy version with full lineage."""

    name: str
    version: str  # "v1", "v2", ...
    rules: Mapping[str, Any]                 # entry/exit rules
    universe: tuple[str, ...]                # tradable symbols
    risk_params: Mapping[str, Any]           # limits, sizing
    cost_model: str                          # transaction-cost assumption id
    regimes: tuple[str, ...]                 # validated market regimes
    lineage: tuple[str, ...]                 # dataset -> features -> model -> ...
    backtest_ref: str
    walk_forward_ref: str
    status: StrategyStatus = StrategyStatus.EXPERIMENTAL
    version_hash: str = ""
    created_at: datetime = field(default_factory=_utcnow)
    created_by: str = "autonomous"

    def __post_init__(self) -> None:
        # Immutable identity: content hash, computed once at construction.
        if not self.version_hash:
            payload = json.dumps(
                {
                    "name": self.name,
                    "rules": dict(self.rules),
                    "universe": list(self.universe),
                    "risk_params": dict(self.risk_params),
                    "cost_model": self.cost_model,
                    "regimes": list(self.regimes),
                    "lineage": list(self.lineage),
                    "backtest_ref": self.backtest_ref,
                    "walk_forward_ref": self.walk_forward_ref,
                },
                sort_keys=True,
            )
            object.__setattr__(self, "version_hash", sha256(payload.encode("utf-8")).hexdigest()[:16])

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "status": self.status.value,
            "version_hash": self.version_hash,
            "universe": list(self.universe),
            "regimes": list(self.regimes),
            "cost_model": self.cost_model,
            "backtest_ref": self.backtest_ref,
            "walk_forward_ref": self.walk_forward_ref,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
        }

    def lineage_map(self) -> dict[str, Any]:
        """Explicit chain: every promoted object must answer these (§20)."""
        return {
            "dataset": self.lineage[0] if self.lineage else None,
            "features": self.lineage[1] if len(self.lineage) > 1 else None,
            "model": self.lineage[2] if len(self.lineage) > 2 else None,
            "prediction_system": self.lineage[3] if len(self.lineage) > 3 else None,
            "strategy_version": self.version_hash,
            "risk_model": str(dict(self.risk_params).get("risk_model", "")),
            "backtest": self.backtest_ref,
            "walk_forward": self.walk_forward_ref,
            "regimes": list(self.regimes),
            "full_chain": list(self.lineage),
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.describe(), "rules": dict(self.rules), "risk_params": dict(self.risk_params), "lineage": list(self.lineage)}


class StrategyRegistry:
    """Immutable, append-only strategy registry with gated lifecycle."""

    def __init__(self, path: str | Path | None = None, *, created_by: str = "autonomous") -> None:
        self.root = Path(path) if path is not None else DEFAULT_ROOT
        self.root.mkdir(parents=True, exist_ok=True)
        self._log = self.root / "registry.jsonl"
        self._versions: dict[tuple[str, str], StrategyVersion] = {}
        self._latest: dict[str, StrategyVersion] = {}
        self._created_by = created_by
        self._replay()

    # ------------------------------------------------------------- storage

    def _append(self, version: StrategyVersion) -> None:
        with self._log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(version.as_dict(), sort_keys=True) + "\n")

    def _replay(self) -> None:
        if not self._log.exists():
            return
        for line in self._log.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                continue
            version = _version_from_dict(raw)
            self._versions[(version.name, version.version)] = version
            self._latest[version.name] = version

    # ------------------------------------------------------------ register

    def register(
        self,
        name: str,
        *,
        rules: Mapping[str, Any],
        universe: Sequence[str] = (),
        risk_params: Mapping[str, Any] | None = None,
        cost_model: str = "v1",
        regimes: Sequence[str] = (),
        lineage: Sequence[str] = (),
        backtest_ref: str = "",
        walk_forward_ref: str = "",
        created_by: str | None = None,
    ) -> StrategyVersion:
        """Register a new immutable strategy version (append-only)."""
        if not name.strip():
            raise ValueError("strategy name is required")
        if not rules:
            raise ValueError("rules must be non-empty")
        number = self._next_number(name)
        version = StrategyVersion(
            name=name,
            version=f"v{number}",
            rules=dict(rules),
            universe=tuple(universe),
            risk_params=dict(risk_params or {}),
            cost_model=cost_model,
            regimes=tuple(regimes),
            lineage=tuple(lineage),
            backtest_ref=backtest_ref,
            walk_forward_ref=walk_forward_ref,
            created_by=created_by or self._created_by,
        )
        key = (name, version.version)
        if key in self._versions:
            raise ValueError(f"strategy version {name}:{version.version} already registered (identical definition)")
        self._versions[key] = version
        self._latest[name] = version
        self._append(version)
        return version

    def _next_number(self, name: str) -> int:
        existing = [int(version.version[1:]) for (n, _), version in self._versions.items() if n == name]
        return 1 + max(existing, default=0)

    # -------------------------------------------------------------- queries

    def get(self, name: str) -> StrategyVersion | None:
        """Latest version of a strategy (history is never overwritten)."""
        return self._latest.get(name)

    def get_version(self, name: str, version: str) -> StrategyVersion | None:
        return self._versions.get((name, version))

    def history(self, name: str) -> tuple[StrategyVersion, ...]:
        return tuple(sorted((version for (n, _), version in self._versions.items() if n == name), key=lambda v: v.version))

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._latest))

    def lineage(self, name: str) -> dict[str, Any] | None:
        latest = self.get(name)
        return latest.lineage_map() if latest is not None else None

    # ------------------------------------------------------------- lifecycle

    def transition(self, name: str, target: StrategyStatus | str, *, by: str = "operator", reason: str = "") -> StrategyVersion:
        """Advance the latest version along an audited status graph.

        Promotion is deny-by-default: illegal jumps (e.g. straight to
        PRODUCTION from EXPERIMENTAL, or RETIRED to APPROVED) raise.
        Progress is append-only — the previous status record is never
        mutated.
        """
        current = self.get(name)
        if current is None:
            raise ValueError(f"unknown strategy {name}")
        target_status = target if isinstance(target, StrategyStatus) else StrategyStatus(target)
        if target_status not in _ALLOWED_TRANSITIONS[current.status]:
            raise ValueError(f"illegal transition {current.status.value} -> {target_status.value} for {name}")
        promoted = _with_status(current, target_status)
        self._versions[(name, current.version)] = promoted
        self._latest[name] = promoted
        self._append(promoted)
        return promoted

    # ------------------------------------------------------------- summary

    def all_versions(self) -> tuple[StrategyVersion, ...]:
        return tuple(sorted(self._versions.values(), key=lambda v: (v.name, v.version)))

    def summary(self) -> dict[str, Any]:
        by_status: dict[str, int] = {}
        for version in self._versions.values():
            by_status[version.status.value] = by_status.get(version.status.value, 0) + 1
        return {
            "root": str(self.root),
            "strategies": len(self._latest),
            "versions": len(self._versions),
            "names": list(self.names()),
            "by_status": by_status,
        }


def _version_from_dict(raw: dict[str, Any]) -> StrategyVersion:
    """Rehydrate a StrategyVersion from a logged record."""
    return StrategyVersion(
        name=str(raw["name"]),
        version=str(raw["version"]),
        rules=dict(raw.get("rules", {})),
        universe=tuple(raw.get("universe", [])),
        risk_params=dict(raw.get("risk_params", {})),
        cost_model=str(raw.get("cost_model", "v1")),
        regimes=tuple(raw.get("regimes", [])),
        lineage=tuple(raw.get("lineage", [])),
        backtest_ref=str(raw.get("backtest_ref", "")),
        walk_forward_ref=str(raw.get("walk_forward_ref", "")),
        status=StrategyStatus(raw.get("status", "experimental")),
        version_hash=str(raw.get("version_hash", "")),
        created_at=datetime.fromisoformat(str(raw["created_at"])),
        created_by=str(raw.get("created_by", "autonomous")),
    )


def _with_status(version: StrategyVersion, status: StrategyStatus) -> StrategyVersion:
    """Copy a version at a new status (same immutable identity/hash)."""
    from dataclasses import replace

    return replace(version, status=status)