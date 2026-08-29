"""Unified mistake-driven learning surface (P4-3).

`MistakeLearner` is the single entry point every ORION component
must go through to record a closed trade's outcome. It wraps the
existing :class:`MistakeAnalyzer` + persistent :class:`LessonStore`,
adds a rolling "recent bias" (per-kind + per-symbol counts), and
persists an analysis file under ``artifacts/lessons/analysis.json``
so the dashboard has a single, durable source of truth for the
mistake timeline.

The learner is **the** place the simulated broker, the demo
brokers, and the future-live broker all converge.
"""

from __future__ import annotations

import json
import threading
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .experience import ExperienceReplay
from .mistakes import LessonStore, MistakeAnalyzer, TradeOutcome


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MistakeLearner:
    """The unified learning-from-mistakes surface (P4-3)."""

    def __init__(
        self,
        replay: ExperienceReplay | None = None,
        *,
        store: LessonStore | None = None,
        analyzer: MistakeAnalyzer | None = None,
        path: str | Path | None = None,
        bias_window: int = 50,
    ) -> None:
        self.analyzer = analyzer or MistakeAnalyzer(replay=replay, store=store or LessonStore(path))
        self.replay = self.analyzer.replay
        self.store = self.analyzer.store
        self.path = Path(path) if path is not None else self.store.path
        self.bias_window = bias_window
        self._by_kind: Counter[str] = Counter()
        self._by_symbol: Counter[str] = Counter()
        self._recent_kinds: deque[str] = deque(maxlen=bias_window)
        self._recent_symbols: deque[str] = deque(maxlen=bias_window)
        self._lock = threading.Lock()
        self._load_existing()

    # -------------------------------------------------------------- I/O

    def _load_existing(self) -> None:
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = str(record.get("kind", ""))
            symbol = str(record.get("symbol", ""))
            if kind:
                self._by_kind[kind] += 1
                self._recent_kinds.append(kind)
            if symbol:
                self._by_symbol[symbol] += 1
                self._recent_symbols.append(symbol)

    def _append_analysis(self) -> None:
        """Append a per-session analysis snapshot (durable timeline)."""
        out = self.path.parent / "analysis.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        snapshot = self.analysis()
        if out.exists():
            try:
                history = json.loads(out.read_text(encoding="utf-8"))
                if not isinstance(history, list):
                    history = []
            except json.JSONDecodeError:
                history = []
        else:
            history = []
        history.append(snapshot)
        out.write_text(json.dumps(history, default=str, indent=2), encoding="utf-8")

    # -------------------------------------------------------------- API

    def record(self, outcome: TradeOutcome) -> list:
        with self._lock:
            lessons = self.analyzer.analyze(outcome)
            for lesson in lessons:
                self._by_kind[lesson.kind] += 1
                self._by_symbol[lesson.symbol] += 1
                self._recent_kinds.append(lesson.kind)
                self._recent_symbols.append(lesson.symbol)
            self._append_analysis()
        return lessons

    def record_many(self, outcomes: Iterable[TradeOutcome]) -> list:
        all_lessons: list = []
        for outcome in outcomes:
            all_lessons.extend(self.record(outcome))
        return all_lessons

    def analysis(self) -> dict[str, Any]:
        return {
            "as_of": _utcnow().isoformat(),
            "bias_window": self.bias_window,
            "all_time": {
                "by_kind": dict(self._by_kind),
                "by_symbol": dict(self._by_symbol),
            },
            "recent": {
                "by_kind": dict(Counter(self._recent_kinds)),
                "by_symbol": dict(Counter(self._recent_symbols)),
            },
            "store_path": str(self.path),
            "replay_size": len(self.replay),
        }

    def lesson_rate_per_kind(self) -> dict[str, float]:
        total = sum(self._by_kind.values()) or 1
        return {kind: count / total for kind, count in self._by_kind.items()}

    def most_mistaken_symbols(self, top_n: int = 5) -> list[tuple[str, int]]:
        return self._by_symbol.most_common(top_n)
