"""ORION Mission Control — stdlib-only terminal dashboard.

This is the *read-first* TUI counterpart of :mod:`orion.dashboard.web`.
The HTML dashboard is for browsers; this one is for SSH sessions,
CI logs, ``tmux`` panes, and ``watch`` loops. It is intentionally
small: a pure renderer that turns a :class:`TuiSnapshot` into a
string, plus a tiny run loop that refreshes on a timer.

Design contract
---------------

* **Pure render path.** :class:`TuiRenderer.render` takes a
  :class:`TuiSnapshot` and a :class:`RenderOptions` and returns a
  string. No I/O, no globals, no hidden state. This is the surface
  every test in ``tests/dashboard/test_tui.py`` exercises.
* **Read-only by default.** The run loop is a viewer. It calls
  :class:`orion.dashboard.web.DashboardState` for snapshots. The
  only mutating actions it ever issues are *gated, opt-in* key
  presses (``k`` to engage the kill switch, ``c`` to run one
  decision cycle on the simulated broker). It does not import the
  real-broker adapters, does not call cloud LLM providers, and
  does not write to the filesystem.
* **No new dependencies.** Pure stdlib. ANSI sequences are emitted
  by string concatenation. Windows terminals get VT processing
  enabled in the run loop; if VT processing is unavailable the
  renderer still works — it just emits plain text.

* **Single source of truth.** Snapshots are built from the same
  :class:`DashboardState` the web dashboard uses. There is no
  duplicate business logic. If the web API exposes a new field,
  the snapshot builder can read it; the renderer does not have to
  change.

The renderer is also callable as a one-shot printer for non-TTY
use cases (``orion tui --once`` from :mod:`orion.cli.main`), in
which case the run loop is not used at all.
"""

from __future__ import annotations

import os
import shutil
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Mapping, Sequence

# ---------------------------------------------------------------------------
# ANSI palette. Kept tiny and self-contained. When the terminal does not
# advertise ANSI support, the renderer strips every escape and emits a
# strictly-monospaced plain-text layout.
# ---------------------------------------------------------------------------

_RESET = "\x1b[0m"
_BOLD = "\x1b[1m"
_DIM = "\x1b[2m"
_RED = "\x1b[31m"
_GREEN = "\x1b[32m"
_YELLOW = "\x1b[33m"
_BLUE = "\x1b[34m"
_MAGENTA = "\x1b[35m"
_CYAN = "\x1b[36m"
_BRIGHT_CYAN = "\x1b[96m"
_BRIGHT_MAGENTA = "\x1b[95m"
_BG_DARK = "\x1b[48;5;236m"

_ANSI_TABLE = {
    "reset": _RESET,
    "bold": _BOLD,
    "dim": _DIM,
    "red": _RED,
    "green": _GREEN,
    "yellow": _YELLOW,
    "blue": _BLUE,
    "magenta": _MAGENTA,
    "cyan": _CYAN,
    "bright_cyan": _BRIGHT_CYAN,
    "bright_magenta": _BRIGHT_MAGENTA,
    "bg_dark": _BG_DARK,
}


def _ansi(name: str, text: str, *, enabled: bool) -> str:
    """Wrap ``text`` in an ANSI sequence iff ANSI is enabled."""
    if not enabled:
        return text
    code = _ANSI_TABLE.get(name, "")
    if not code:
        return text
    return f"{code}{text}{_RESET}"


def _strip_ansi(text: str) -> str:
    """Remove every ANSI escape from ``text``. Used for the plain-text
    fallback and for tests that want to assert against the uncoloured
    layout."""
    out: list[str] = []
    i = 0
    while i < len(text):
        if text[i] == "\x1b" and i + 1 < len(text) and text[i + 1] == "[":
            j = text.find("m", i + 2)
            if j == -1:
                break
            i = j + 1
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


# ---------------------------------------------------------------------------
# Snapshot — the input to the renderer.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class VenueSnapshot:
    """One row of the venue table."""

    venue: str
    mode: str
    available: bool
    detail: str = ""

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "VenueSnapshot":
        return cls(
            venue=str(payload.get("venue", "?")),
            mode=str(payload.get("mode", "?")),
            available=bool(payload.get("available", False)),
            detail=str(payload.get("detail", "")),
        )


@dataclass(frozen=True, slots=True)
class LessonSnapshot:
    """One row of the lesson feed."""

    kind: str
    severity: str
    summary: str
    occurred_at: str = ""

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "LessonSnapshot":
        kind = str(payload.get("kind", "unknown"))
        severity = str(payload.get("severity", "info"))
        summary = str(
            payload.get("summary")
            or payload.get("message")
            or payload.get("description")
            or kind
        )
        occurred_at = str(payload.get("occurred_at") or payload.get("timestamp") or "")
        return cls(kind=kind, severity=severity, summary=summary, occurred_at=occurred_at)


@dataclass(frozen=True, slots=True)
class TradeSnapshot:
    """One row of the recent-trades feed."""

    kind: str
    symbol: str
    total_return: float = 0.0
    status: str = ""

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "TradeSnapshot":
        return cls(
            kind=str(payload.get("kind", "?")),
            symbol=str(payload.get("symbol", "?")),
            total_return=float(payload.get("total_return", 0.0) or 0.0),
            status=str(payload.get("status", "")),
        )


@dataclass(frozen=True, slots=True)
class PeerSnapshot:
    """One row of the peer-AI table."""

    provider: str
    model: str
    available: bool
    detail: str = ""

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "PeerSnapshot":
        return cls(
            provider=str(payload.get("provider") or payload.get("name") or "?"),
            model=str(payload.get("model", "")),
            available=bool(payload.get("available", True)),
            detail=str(payload.get("detail") or payload.get("endpoint") or ""),
        )


@dataclass(frozen=True, slots=True)
class KillSwitchSnapshot:
    engaged: bool
    reason: str
    engaged_at: str = ""

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "KillSwitchSnapshot":
        return cls(
            engaged=bool(payload.get("engaged", False)),
            reason=str(payload.get("reason", "")),
            engaged_at=str(payload.get("engaged_at") or ""),
        )


@dataclass(frozen=True, slots=True)
class TuiSnapshot:
    """A flat, renderer-friendly view of the live dashboard state.

    Built from :class:`orion.dashboard.web.DashboardState` so the TUI
    reads the same data the web API serves. Decoupling the renderer
    from the live objects means every test can drive the renderer
    with hand-built snapshots.
    """

    banner: str
    mode: str
    execution_mode: str
    live_trading_enabled: bool
    autonomy_level: str
    max_position_fraction: float
    max_portfolio_exposure: float
    max_daily_loss_fraction: float
    equity_history: tuple[float, ...]
    venues: tuple[VenueSnapshot, ...]
    kill_switch: KillSwitchSnapshot
    lessons: tuple[LessonSnapshot, ...] = ()
    trades: tuple[TradeSnapshot, ...] = ()
    peers: tuple[PeerSnapshot, ...] = ()
    last_updated: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))

    def equity_delta(self) -> float:
        if len(self.equity_history) < 2:
            return 0.0
        first = self.equity_history[0]
        last = self.equity_history[-1]
        if first == 0:
            return 0.0
        return (last - first) / first

    @classmethod
    def from_dashboard_state(cls, state: Any) -> "TuiSnapshot":
        """Build a snapshot from a live :class:`DashboardState`."""
        status = state.api_status()
        brokers = state.api_brokers()
        lessons_payload = state.api_lessons()
        peers_payload = state.api_peers()
        return cls(
            banner=str(status.get("banner", "ORION MISSION CONTROL")),
            mode=str(status.get("mode", "?")),
            execution_mode=str(status.get("execution_mode", "?")),
            live_trading_enabled=bool(status.get("live_trading_enabled", False)),
            autonomy_level=str(status.get("autonomy_level", "?")),
            max_position_fraction=float(status.get("limits", {}).get("max_position_fraction", 0.0) or 0.0),
            max_portfolio_exposure=float(
                status.get("limits", {}).get("max_portfolio_exposure", 0.0) or 0.0
            ),
            max_daily_loss_fraction=float(
                status.get("limits", {}).get("max_daily_loss_fraction", 0.0) or 0.0
            ),
            equity_history=tuple(float(x) for x in status.get("equity_history", ())),
            venues=tuple(
                VenueSnapshot.from_dict(v)
                for v in brokers.get("venues", [])
            ),
            kill_switch=KillSwitchSnapshot.from_dict(brokers.get("kill_switch", {})),
            lessons=tuple(LessonSnapshot.from_dict(l) for l in lessons_payload.get("recent", [])),
            trades=tuple(TradeSnapshot.from_dict(t) for t in status.get("trades", [])),
            peers=tuple(PeerSnapshot.from_dict(p) for p in peers_payload.get("peers", [])),
        )


# ---------------------------------------------------------------------------
# Render options.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RenderOptions:
    """What the renderer is allowed to use.

    ``width`` is the requested column count. The renderer honours it
    or shrinks the layout to fit the smaller of ``width`` and the
    current terminal width.

    ``ansi`` lets callers force a colour mode (useful in tests and
    in the one-shot printer). When ``None`` the run loop decides.
    """

    width: int = 100
    ansi: bool | None = None
    show_legend: bool = True
    compact: bool = False


# ---------------------------------------------------------------------------
# Renderer.
# ---------------------------------------------------------------------------


_SPARK_BLOCKS = "▁▂▃▄▅▆▇█"


def _sparkline(values: Sequence[float], width: int) -> str:
    """Return a unicode-block sparkline of ``values`` truncated/padded to
    ``width`` columns. Empty input returns the empty string."""
    if not values or width <= 0:
        return ""
    if len(values) > width:
        # Resample by averaging buckets so the shape is preserved.
        bucket = len(values) / width
        sampled: list[float] = []
        for i in range(width):
            lo = int(i * bucket)
            hi = int((i + 1) * bucket)
            if hi <= lo:
                hi = lo + 1
            sampled.append(sum(values[lo:hi]) / max(1, hi - lo))
        values = sampled
    elif len(values) < width:
        # Right-pad with the last value so the sparkline is "current state".
        values = list(values) + [values[-1]] * (width - len(values))
    lo = min(values)
    hi = max(values)
    if hi == lo:
        return _SPARK_BLOCKS[0] * width
    out: list[str] = []
    levels = len(_SPARK_BLOCKS) - 1
    for v in values:
        norm = (v - lo) / (hi - lo)
        idx = int(round(norm * levels))
        idx = max(0, min(levels, idx))
        out.append(_SPARK_BLOCKS[idx])
    return "".join(out)


def _truncate(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width <= 1:
        return text[:width]
    return text[: width - 1] + "…"


def _pad(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(text) >= width:
        return text[:width]
    return text + " " * (width - len(text))


def _hr(width: int, char: str = "─") -> str:
    return char * max(0, width)


class TuiRenderer:
    """Pure render path from :class:`TuiSnapshot` to a printable string.

    The renderer never touches the terminal, never opens files, and
    has no globals. Tests construct a snapshot, call
    :meth:`render`, and assert on the returned string. Production
    code (the run loop and the one-shot printer) builds the
    snapshot from a live :class:`DashboardState`.
    """

    def __init__(self, *, options: RenderOptions | None = None) -> None:
        self.options = options or RenderOptions()

    # -------------------------------------------------------------- public

    def render(self, snapshot: TuiSnapshot) -> str:
        """Render a snapshot to a printable string."""
        opts = self.options
        width = max(40, opts.width)
        ansi = bool(opts.ansi)
        out: list[str] = []
        out.extend(self._render_header(snapshot, width, ansi))
        out.append(_hr(width))
        out.extend(self._render_risk(snapshot, width, ansi))
        out.append(_hr(width))
        out.extend(self._render_equity(snapshot, width, ansi))
        out.append(_hr(width))
        out.extend(self._render_venues(snapshot, width, ansi))
        out.append(_hr(width))
        out.extend(self._render_peers(snapshot, width, ansi))
        out.append(_hr(width))
        out.extend(self._render_lessons(snapshot, width, ansi))
        out.append(_hr(width))
        out.extend(self._render_trades(snapshot, width, ansi))
        if opts.show_legend:
            out.append(_hr(width, "·"))
            out.extend(self._render_legend(width, ansi))
        return "\n".join(line for line in out if line is not None) + "\n"

    # ------------------------------------------------------------- sections

    def _render_header(self, snap: TuiSnapshot, width: int, ansi: bool) -> list[str]:
        title = _ansi("bright_cyan", f"  {snap.banner}  ", enabled=ansi)
        title = _ansi("bold", title, enabled=ansi)
        right = []
        if snap.live_trading_enabled:
            right.append(_ansi("red", "● LIVE-ENABLED", enabled=ansi))
        else:
            right.append(_ansi("green", "○ live-blocked", enabled=ansi))
        if snap.kill_switch.engaged:
            right.append(_ansi("red", "⛔ KILL-SWITCH ENGAGED", enabled=ansi))
        else:
            right.append(_ansi("dim", "kill switch: armed", enabled=ansi))
        right_text = "  ".join(right)
        bar_left = _ansi("bright_magenta", "▌", enabled=ansi)
        bar_right = _ansi("bright_magenta", "▐", enabled=ansi)
        sub = _ansi(
            "dim",
            f"mode={snap.mode}  exec={snap.execution_mode}  autonomy={snap.autonomy_level}  "
            f"updated={snap.last_updated.astimezone().strftime('%H:%M:%S')}",
            enabled=ansi,
        )
        # Layout: bar title · · · · · right
        title_len_visible = len(_strip_ansi(title))
        right_len_visible = len(_strip_ansi(right_text))
        gap = max(1, width - title_len_visible - right_len_visible - 4)
        line = f"{bar_left}{title}{' ' * gap}{right_text}{bar_right}"
        return [line, sub]

    def _render_risk(self, snap: TuiSnapshot, width: int, ansi: bool) -> list[str]:
        head = _ansi("bold", "RISK POSTURE", enabled=ansi)
        line = f"{head}  {_ansi('dim', '—', enabled=ansi)}  limits enforced by RiskEngine"
        # Gauges in plain text: name = fraction.
        gauges = [
            ("max pos", snap.max_position_fraction),
            ("max exp", snap.max_portfolio_exposure),
            ("max day", snap.max_daily_loss_fraction),
        ]
        rendered = []
        for label, value in gauges:
            rendered.append(f"{label}={value:.2f}")
        body = "   ".join(rendered)
        return [line, _ansi("cyan", body, enabled=ansi)]

    def _render_equity(self, snap: TuiSnapshot, width: int, ansi: bool) -> list[str]:
        head = _ansi("bold", "EQUITY (session)", enabled=ansi)
        history = snap.equity_history
        spark_width = max(10, width - 2)
        spark = _sparkline(history, spark_width)
        if history:
            last = history[-1]
            first = history[0] if history[0] else 1.0
            delta_pct = (last - first) / first * 100.0 if first else 0.0
            value_str = f"{last:,.2f}"
            if delta_pct >= 0:
                delta_str = _ansi("green", f"+{delta_pct:.2f}%", enabled=ansi)
            else:
                delta_str = _ansi("red", f"{delta_pct:.2f}%", enabled=ansi)
            tail = f"  last={value_str}  Δ={_strip_ansi(delta_str)}"
        else:
            tail = "  (no equity points yet)"
        spark_rendered = _ansi("bright_cyan", spark, enabled=ansi)
        return [head, f" {spark_rendered}{tail}"]

    def _render_venues(self, snap: TuiSnapshot, width: int, ansi: bool) -> list[str]:
        head = _ansi("bold", "BROKER VENUES", enabled=ansi)
        if not snap.venues:
            return [head, _ansi("dim", "  (no venues configured — set API keys in .env)", enabled=ansi)]
        rows: list[str] = []
        # column widths: venue(16) mode(10) available(4) detail(rest)
        vw = 16
        mw = 10
        aw = 4
        for venue in snap.venues:
            mode = venue.mode
            if "live" in mode.lower():
                mode_pill = _ansi("red", f" {mode:<8}", enabled=ansi)
            elif "blocked" in mode.lower():
                mode_pill = _ansi("dim", f" {mode:<8}", enabled=ansi)
            else:
                mode_pill = _ansi("green", f" {mode:<8}", enabled=ansi)
            avail = _ansi("green", " ● ", enabled=ansi) if venue.available else _ansi("dim", " ○ ", enabled=ansi)
            detail_w = max(0, width - vw - mw - aw - 6)
            row = (
                _pad(_truncate(venue.venue, vw), vw)
                + " "
                + mode_pill
                + " "
                + avail
                + " "
                + _ansi("dim", _truncate(venue.detail, detail_w), enabled=ansi)
            )
            rows.append(row)
        return [head, *rows]

    def _render_peers(self, snap: TuiSnapshot, width: int, ansi: bool) -> list[str]:
        head = _ansi("bold", "PEER-AI COUNCIL", enabled=ansi)
        if not snap.peers:
            return [head, _ansi("dim", "  (no cloud peers configured — set API keys in .env)", enabled=ansi)]
        rows: list[str] = []
        for peer in snap.peers:
            status = (
                _ansi("green", "● ready", enabled=ansi) if peer.available else _ansi("dim", "○ n/a", enabled=ansi)
            )
            name = _truncate(f"{peer.provider}/{peer.model}" if peer.model else peer.provider, width - 14)
            rows.append(f"  {name:<{max(0, width - 14)}}{status}")
        return [head, *rows]

    def _render_lessons(self, snap: TuiSnapshot, width: int, ansi: bool) -> list[str]:
        head = _ansi("bold", "MISTAKE-LESSON FEED", enabled=ansi)
        if not snap.lessons:
            return [head, _ansi("dim", "  (no lessons recorded — feed outcomes via /api/reflect)", enabled=ansi)]
        rows: list[str] = []
        for lesson in snap.lessons[:8]:
            sev = lesson.severity.lower()
            if sev in ("high", "bad", "critical"):
                marker = _ansi("red", "▎", enabled=ansi)
            elif sev in ("low", "good", "info"):
                marker = _ansi("green", "▎", enabled=ansi)
            else:
                marker = _ansi("yellow", "▎", enabled=ansi)
            kind = _ansi("bold", _truncate(lesson.kind, 16).upper(), enabled=ansi)
            summary = _truncate(lesson.summary, max(0, width - 22))
            rows.append(f"  {marker} {kind:<16} {summary}")
        return [head, *rows]

    def _render_trades(self, snap: TuiSnapshot, width: int, ansi: bool) -> list[str]:
        head = _ansi("bold", "RECENT TRADES", enabled=ansi)
        if not snap.trades:
            return [head, _ansi("dim", "  (no trades yet)", enabled=ansi)]
        rows: list[str] = []
        for trade in snap.trades[-8:]:
            ret = trade.total_return
            if ret > 0:
                ret_pill = _ansi("green", f"+{ret:.4f}", enabled=ansi)
            elif ret < 0:
                ret_pill = _ansi("red", f"{ret:.4f}", enabled=ansi)
            else:
                ret_pill = _ansi("dim", " 0.0000", enabled=ansi)
            label = f"{trade.kind:<8} {trade.symbol:<8}"
            rows.append(f"  {label}  {_strip_ansi(ret_pill)}  {_ansi('dim', trade.status, enabled=ansi)}")
        return [head, *rows]

    def _render_legend(self, width: int, ansi: bool) -> list[str]:
        items = [
            ("q", "quit"),
            ("r", "refresh"),
            ("c", "run cycle (paper)"),
            ("k", "engage kill switch"),
            ("K", "disengage kill switch"),
            ("?", "help"),
        ]
        line = "  ".join(f"{_ansi('bold', key, enabled=ansi)}={label}" for key, label in items)
        return [_ansi("dim", line, enabled=ansi)]


# ---------------------------------------------------------------------------
# Run loop.
# ---------------------------------------------------------------------------


def _detect_ansi(stream: Any) -> bool:
    """Best-effort detection of whether ``stream`` speaks ANSI.

    ``NO_COLOR`` (any value) wins. ``FORCE_COLOR`` (any value) also
    wins, including on non-tty streams — this matches the behaviour
    of most Unix CLIs (``ls --color``, ``grep --color``) and lets
    tests, CI logs, and ``tee`` pipelines request coloured output
    explicitly. When neither env var is set, the stream must be a
    tty and (on Windows) VT processing must be enabled.
    """
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    if not hasattr(stream, "isatty") or not stream.isatty():
        return False
    # Windows: enable VT processing if we can.
    if sys.platform == "win32":
        try:
            import ctypes  # type: ignore[import-not-found]

            kernel = ctypes.windll.kernel32  # type: ignore[attr-defined]
            handle = kernel.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
            mode = ctypes.c_uint32()
            if kernel.GetConsoleMode(handle, ctypes.byref(mode)):
                # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x4
                if mode.value & 0x4:
                    return True
                if kernel.SetConsoleMode(handle, mode.value | 0x4):
                    return True
            return False
        except Exception:  # noqa: BLE001 - any failure falls back to plain text
            return False
    return True


def _term_width(default: int = 100) -> int:
    try:
        return max(40, shutil.get_terminal_size((default, 20)).columns)
    except Exception:  # noqa: BLE001
        return default


def _read_key(timeout: float) -> str | None:
    """Read a single keypress from stdin, with a timeout.

    On non-tty stdin (CI, pipes) this returns ``None`` immediately.
    Returns the empty string for plain Enter. We use :mod:`msvcrt`
    on Windows and :mod:`select` + :mod:`tty` on POSIX, both stdlib.
    """
    if not sys.stdin or not hasattr(sys.stdin, "fileno"):
        return None
    try:
        fd = sys.stdin.fileno()
    except (OSError, ValueError):
        return None
    try:
        if sys.platform == "win32":
            import msvcrt  # type: ignore[import-not-found]

            # msvcrt is non-blocking only via a polling loop; cap the
            # wait so we never block longer than ``timeout``.
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if msvcrt.kbhit():
                    ch = msvcrt.getwch()
                    return ch
                time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
            return None
        import select
        import termios  # type: ignore[import-not-found]
        import tty  # type: ignore[import-not-found]

        old = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            ready, _, _ = select.select([fd], [], [], timeout)
            if ready:
                return sys.stdin.read(1)
            return None
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
    except Exception:  # noqa: BLE001
        return None


class TuiApp:
    """The TUI run loop.

    Pulls snapshots from a :class:`DashboardState` (or any object
    that exposes a :meth:`snapshot` callable returning a
    :class:`TuiSnapshot`), renders them, and writes to a stream.
    Keyboard input is *opt-in*: pass ``interactive=True`` to read
    key presses. The default (``interactive=False``) is a quiet
    refresh-on-timer loop suitable for ``watch`` or CI logs.
    """

    def __init__(
        self,
        state: Any,
        *,
        renderer: TuiRenderer | None = None,
        stream: Any | None = None,
        refresh_seconds: float = 2.0,
        interactive: bool = False,
        snapshot_factory: Callable[[Any], TuiSnapshot] | None = None,
    ) -> None:
        self.state = state
        self.renderer = renderer
        self.stream = stream or sys.stdout
        self.refresh_seconds = max(0.5, float(refresh_seconds))
        self.interactive = bool(interactive)
        self._snapshot_factory: Callable[[Any], TuiSnapshot] = (
            snapshot_factory if snapshot_factory is not None else TuiSnapshot.from_dashboard_state
        )
        self._stop = threading.Event()

    def snapshot(self) -> TuiSnapshot:
        return self._snapshot_factory(self.state)

    def stop(self) -> None:
        self._stop.set()

    def render_once(self) -> str:
        """Render exactly one frame. Used by ``--once`` and by tests."""
        opts = self.renderer.options if self.renderer else RenderOptions()
        ansi = opts.ansi if opts.ansi is not None else _detect_ansi(self.stream)
        renderer = self.renderer or TuiRenderer(options=RenderOptions(width=_term_width(), ansi=ansi))
        return renderer.render(self.snapshot())

    def run(self, *, max_frames: int | None = None) -> int:
        """Run the loop. Returns the number of frames rendered."""
        opts = self.renderer.options if self.renderer else RenderOptions()
        ansi = opts.ansi if opts.ansi is not None else _detect_ansi(self.stream)
        width = opts.width or _term_width()
        renderer = self.renderer or TuiRenderer(options=RenderOptions(width=width, ansi=ansi))
        frames = 0
        # Hide cursor + clear screen on first frame.
        if ansi:
            self.stream.write("\x1b[?25l\x1b[2J\x1b[H")
            self.stream.flush()
        try:
            while not self._stop.is_set():
                frame = renderer.render(self.snapshot())
                safe_frame = _asciify_for_stream(frame, self.stream)
                if ansi:
                    self.stream.write("\x1b[H")
                self.stream.write(safe_frame)
                self.stream.flush()
                frames += 1
                if max_frames is not None and frames >= max_frames:
                    break
                if self.interactive:
                    key = _read_key(self.refresh_seconds)
                    if key is not None:
                        if not self._handle_key(key):
                            break
                else:
                    # Sleep in small slices so stop() is responsive.
                    self._sleep(self.refresh_seconds)
        finally:
            if ansi:
                self.stream.write("\x1b[?25h")
                self.stream.flush()
        return frames

    # --------------------------------------------------------- interactive

    def _handle_key(self, key: str) -> bool:
        """Return False to stop the loop, True to continue."""
        if key in ("q", "Q", "\x1b"):
            return False
        if key in ("?", "h"):
            # ``?`` and ``h`` redraw with the legend (renderer always shows
            # the legend by default; here we just trigger a refresh).
            return True
        if key in ("r", "R"):
            return True
        if key in ("k",):
            # Engage the kill switch. Read through the registry so the
            # gating is consistent with the web API.
            try:
                registry = getattr(self.state, "registry", None)
                if registry is not None:
                    registry.kill_switch.engage("tui-keypress")
            except Exception:  # noqa: BLE001 - never let a keypress crash the loop
                pass
            return True
        if key in ("K",):
            try:
                registry = getattr(self.state, "registry", None)
                if registry is not None:
                    registry.kill_switch.disengage()
            except Exception:  # noqa: BLE001
                pass
            return True
        if key in ("c",):
            # Run one paper decision cycle. The simulated broker is the
            # canonical safe execution engine; this is the same path the
            # web dashboard uses.
            try:
                from ..data.contracts import Asset, AssetClass

                self.state.run(  # type: ignore[union-attr] - DashboardState exposes run
                    Asset("DEMO", AssetClass.EQUITY),
                    [100, 101, 100.5, 102, 103, 104, 105],
                )
            except Exception:  # noqa: BLE001
                pass
            return True
        return True

    def _sleep(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while not self._stop.is_set() and time.monotonic() < end:
            time.sleep(min(0.1, end - time.monotonic()))


# ---------------------------------------------------------------------------
# Convenience: one-shot printer.
# ---------------------------------------------------------------------------


def print_tui(
    state: Any,
    *,
    stream: Any | None = None,
    width: int | None = None,
    force_ansi: bool | None = None,
) -> str:
    """Render a single TUI frame to ``stream`` and return the text.

    Used by ``orion tui --once`` and by the test suite. Always
    safe to call from non-tty contexts; colours are auto-detected
    from the stream.

    Windows consoles commonly use ``cp1252``, which cannot encode
    the block-drawing characters used by the sparkline and rule
    lines. When encoding would fail, the unicode block characters
    are silently substituted with ASCII equivalents so the TUI
    remains readable on every platform.
    """
    stream = stream or sys.stdout
    ansi = force_ansi if force_ansi is not None else _detect_ansi(stream)
    renderer = TuiRenderer(options=RenderOptions(width=width or _term_width(), ansi=ansi))
    text = renderer.render(TuiSnapshot.from_dashboard_state(state))
    safe_text = _asciify_for_stream(text, stream)
    stream.write(safe_text)
    stream.flush()
    return text


_ASCII_FALLBACK = {
    "▁": "_",
    "▂": "_",
    "▃": "-",
    "▄": "-",
    "▅": "=",
    "▆": "=",
    "▇": "#",
    "█": "#",
    "▎": "|",
    "▌": "|",
    "▐": "|",
    "─": "-",
    "—": "-",
    "·": ".",
    "•": "*",
    "●": "*",
    "○": "o",
    "⛔": "!",
    "×": "x",
    "…": "...",
    "Δ": "delta",
    "→": "->",
    "←": "<-",
}


def _asciify_for_stream(text: str, stream: Any) -> str:
    """Replace any unicode characters the stream cannot encode.

    We try to encode the text with the stream's actual encoding
    (usually UTF-8 on POSIX, cp1252 on Windows). If that fails,
    we substitute each offending character with the closest ASCII
    equivalent so the output is still readable. The original text
    is still returned from the function so the caller can decide
    what to do with the unicode version if it has a better sink.

    Order matters: if the stream can already encode the character
    natively, we keep it. Only if encoding fails do we consult the
    fallback table, then the universal ``?`` placeholder.
    """
    encoding = getattr(stream, "encoding", None) or "utf-8"
    try:
        text.encode(encoding)
        return text
    except UnicodeEncodeError:
        out: list[str] = []
        for ch in text:
            try:
                ch.encode(encoding)
                out.append(ch)
            except UnicodeEncodeError:
                if ch in _ASCII_FALLBACK:
                    out.append(_ASCII_FALLBACK[ch])
                else:
                    out.append("?")
        return "".join(out)


__all__ = [
    "KillSwitchSnapshot",
    "LessonSnapshot",
    "PeerSnapshot",
    "RenderOptions",
    "TradeSnapshot",
    "TuiApp",
    "TuiRenderer",
    "TuiSnapshot",
    "VenueSnapshot",
    "print_tui",
]
