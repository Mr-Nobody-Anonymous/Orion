"""Learning from trading mistakes.

Every closed trade (in simulation, demo, or — once explicitly
unlocked — live) is fed to the :class:`MistakeAnalyzer`, which
classifies *what kind of mistake* was made (if any), turns it into a
persistent :class:`Lesson`, and routes the numeric evidence into the
existing :class:`orion.learning.experience.ExperienceReplay` buffer so
the prediction/decision models train on their worst outcomes first.

Mistake taxonomy (first version)
--------------------------------

* ``oversized``       — position notional above the configured fraction of equity
* ``prediction_miss`` — |actual - predicted| return above the tolerance
* ``slippage``        — fill price materially worse than the intended price
* ``regime_mismatch`` — loss taken in a regime where the strategy underperforms
* ``discipline``      — stop-loss breach / preventable loss
* ``none``            — the trade was fine; recorded but without a lesson

Lessons are appended to a JSONL store under ``artifacts/lessons/`` so
they survive restarts and can be audited.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

from .experience import ExperienceReplay, ReplayItem

MISTAKE_KINDS = ("oversized", "prediction_miss", "slippage", "regime_mismatch", "discipline", "none")


@dataclass(frozen=True, slots=True)
class TradeOutcome:
    symbol: str
    side: str                      # "buy" | "sell"
    quantity: float
    entry_price: float
    exit_price: float
    predicted_return: float        # model expectation at entry
    venue: str = "simulated"
    mode: str = "simulation"       # simulation | demo | live
    regime: str = "unknown"
    equity: float = 0.0            # account equity at entry
    max_notional_fraction: float = 0.10
    prediction_tolerance: float = 0.02
    slippage_bps_tolerance: float = 10.0
    stop_loss_hit: bool = False
    closed_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))

    @property
    def realized_return(self) -> float:
        if self.entry_price == 0:
            return 0.0
        direction = 1.0 if self.side.lower() == "buy" else -1.0
        return direction * (self.exit_price - self.entry_price) / self.entry_price

    @property
    def realized_pnl(self) -> float:
        return self.realized_return * self.quantity * self.entry_price

    @property
    def notional_fraction(self) -> float:
        if self.equity <= 0:
            return 0.0
        return (self.quantity * self.entry_price) / self.equity

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "predicted_return": self.predicted_return,
            "realized_return": self.realized_return,
            "realized_pnl": self.realized_pnl,
            "venue": self.venue,
            "mode": self.mode,
            "regime": self.regime,
            "closed_at": self.closed_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class Lesson:
    kind: str
    symbol: str
    severity: str                  # "low" | "medium" | "high"
    description: str
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "symbol": self.symbol,
            "severity": self.severity,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "metadata": dict(self.metadata),
        }


class LessonStore:
    """Append-only JSONL lesson log (bounded reads via ``recent``)."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else Path("artifacts/lessons/lessons.jsonl")
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, lesson: Lesson) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(lesson.as_dict(), sort_keys=True) + "\n")

    def recent(self, count: int = 20) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        out: list[dict[str, Any]] = []
        for line in reversed(lines):
            if len(out) >= count:
                break
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out

    def by_kind(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        if not self.path.exists():
            return counts
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = record.get("kind", "unknown")
            counts[kind] = counts.get(kind, 0) + 1
        return counts


class MistakeAnalyzer:
    """Classify trade outcomes into lessons and feed the replay buffer."""

    def __init__(
        self,
        replay: ExperienceReplay | None = None,
        *,
        store: LessonStore | None = None,
    ) -> None:
        self.replay = replay if replay is not None else ExperienceReplay()
        self.store = store if store is not None else LessonStore()
        self.lessons: list[Lesson] = []

    # ------------------------------------------------------------- analysis

    def analyze(self, outcome: TradeOutcome) -> list[Lesson]:
        lessons: list[Lesson] = []
        if outcome.notional_fraction > outcome.max_notional_fraction * 1.01:
            lessons.append(
                Lesson(
                    kind="oversized",
                    symbol=outcome.symbol,
                    severity="high" if outcome.realized_return < 0 else "medium",
                    description=(
                        f"Position notional was {outcome.notional_fraction:.1%} of equity, "
                        f"above the {outcome.max_notional_fraction:.1%} cap."
                    ),
                    metadata={"notional_fraction": outcome.notional_fraction},
                )
            )
        prediction_error = outcome.realized_return - outcome.predicted_return
        if abs(prediction_error) > outcome.prediction_tolerance:
            lessons.append(
                Lesson(
                    kind="prediction_miss",
                    symbol=outcome.symbol,
                    severity="high" if abs(prediction_error) > 2 * outcome.prediction_tolerance else "medium",
                    description=(
                        f"Predicted {outcome.predicted_return:+.2%}, realized "
                        f"{outcome.realized_return:+.2%} (error {prediction_error:+.2%})."
                    ),
                    metadata={"prediction_error": prediction_error},
                )
            )
        if outcome.mode in ("demo", "live") and outcome.entry_price > 0:
            slippage_bps = abs(outcome.exit_price - outcome.entry_price) / outcome.entry_price * 10_000
            if slippage_bps > outcome.slippage_bps_tolerance:
                lessons.append(
                    Lesson(
                        kind="slippage",
                        symbol=outcome.symbol,
                        severity="medium",
                        description=(
                            f"Fill slippage {slippage_bps:.1f} bps exceeded the "
                            f"{outcome.slippage_bps_tolerance:.0f} bps tolerance."
                        ),
                        metadata={"slippage_bps": slippage_bps},
                    )
                )
        if outcome.stop_loss_hit:
            lessons.append(
                Lesson(
                    kind="discipline",
                    symbol=outcome.symbol,
                    severity="medium",
                    description=(
                        "Stop-loss was hit; entry sizing or regime filter allowed a preventable loss."
                    ),
                    metadata={"regime": outcome.regime},
                )
            )
        if not lessons and outcome.realized_return >= 0:
            lessons.append(
                Lesson(
                    kind="none",
                    symbol=outcome.symbol,
                    severity="low",
                    description="No mistake detected; trade behaved within tolerance.",
                )
            )
        elif not lessons:
            lessons.append(
                Lesson(
                    kind="regime_mismatch",
                    symbol=outcome.symbol,
                    severity="medium",
                    description=(
                        f"Loss of {outcome.realized_return:+.2%} in regime '{outcome.regime}' "
                        "without a specific rule breach — review regime fit."
                    ),
                    metadata={"regime": outcome.regime},
                )
            )
        for lesson in lessons:
            self.lessons.append(lesson)
            self.store.append(lesson)
        self._feed_replay(outcome)
        return lessons

    def analyze_all(self, outcomes: Iterable[TradeOutcome]) -> list[Lesson]:
        all_lessons: list[Lesson] = []
        for outcome in outcomes:
            all_lessons.extend(self.analyze(outcome))
        return all_lessons

    # ------------------------------------------------------------- replay

    def _feed_replay(self, outcome: TradeOutcome) -> None:
        """Push the outcome into the prioritized replay buffer."""
        self.replay.append(
            ReplayItem(
                asset=outcome.symbol,
                features={
                    "side": outcome.side,
                    "quantity": outcome.quantity,
                    "entry_price": outcome.entry_price,
                    "venue": outcome.venue,
                    "mode": outcome.mode,
                },
                prediction=Decimal(str(outcome.predicted_return)),
                actual_return=Decimal(str(outcome.realized_return)),
                model="mistake_analyzer",
                regime=outcome.regime,
            )
        )

    def summary(self) -> dict[str, Any]:
        return {
            "lessons_recorded": len(self.lessons),
            "kinds": {kind: sum(1 for lesson in self.lessons if lesson.kind == kind) for kind in MISTAKE_KINDS},
            "replay": self.replay.summary() if len(self.replay) else {"size": 0},
            "store_counts": self.store.by_kind(),
        }