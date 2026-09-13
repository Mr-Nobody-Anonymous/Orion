#!/usr/bin/env python3
"""ORION one-command launcher - start the whole platform on any machine.

One command boots the full stack on Windows, Windows Server, Linux and macOS:

    Windows / Windows Server   :  start.cmd          (any shell, or double-click)
    Linux / macOS              :  ./start.sh         (or: sh start.sh / python3 start.py)
    Any OS with Python >= 3.10 :  python start.py

What it runs, in order:

  1. ``python -m orion doctor``   health + safety gate (aborts unless HEALTHY)
  2. ``python -m orion status``   capability report
  3. ``python -m orion run DEMO`` one full 16-phase executive cycle (smoke test)
  4. ``python -m orion serve``    Mission Control web dashboard, foreground
                                  (Ctrl+C stops everything cleanly)

Design notes
------------
* Stdlib-only and offline-safe: no pip, no venv, no database, no broker
  account, no GPU. The launcher just points ``PYTHONPATH`` at ``src/`` so
  ORION's stdlib-first package runs on any CPython >= 3.10.
* The launcher itself tolerates older interpreters (>= 3.5): if the Python
  running this file is too old it locates a suitable one and delegates.
* Nothing is faked: if the health gate is not ``HEALTHY`` the launcher stops
  and says why instead of starting a half-broken stack (``--force`` overrides).
"""

import argparse
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
MIN_PY = (3, 10)
STEP_TIMEOUT = 600  # seconds; every step is local + offline by design

PYTHON = sys.executable  # replaced by find_python() when needed
ENV = os.environ.copy()

BANNER = """
================================================================
  O R I O N  -  Autonomous Financial Intelligence Platform
  one-command launcher  |  Windows  |  Windows Server  |  Linux  |  macOS
================================================================"""


def say(tag, msg=""):
    """Print one tagged status line (ASCII-only so every console survives)."""
    print("[%s] %s" % (tag, msg))


# --------------------------------------------------------------------------
# Interpreter discovery (works even when start.py runs on an old Python)
# --------------------------------------------------------------------------

def _probe(cmd):
    """Return (executable, version) when ``cmd`` runs a Python >= 3.10."""
    code = (
        "import sys\n"
        "ok = sys.version_info >= (3, 10)\n"
        "print(sys.executable if ok else '')\n"
        "print('%d.%d.%d' % sys.version_info[:3])\n"
    )
    try:
        out = subprocess.run(
            cmd + ["-c", code],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )
    except Exception:  # noqa: BLE001 - a missing candidate is not an error
        return None
    if out.returncode != 0:
        return None
    lines = out.stdout.decode("utf-8", "replace").strip().splitlines()
    if not lines or not lines[0]:
        return None
    return lines[0], (lines[1] if len(lines) > 1 else "?")


def _candidate_commands():
    """Common interpreter locations, best candidates first."""
    minors = (13, 12, 11, 10)
    if os.name == "nt":
        cmds = [["py", "-3"]]
        cmds += [["py", "-3.%d" % m] for m in minors]
        cmds += [["python"], ["python3"]]
        cmds += [["python3.%d" % m] for m in minors]
    else:
        cmds = [["python3"], ["python"]]
        cmds += [["python3.%d" % m] for m in minors]
        cmds += [
            ["/usr/bin/python3"],
            ["/usr/local/bin/python3"],
            ["/opt/homebrew/bin/python3"],
            ["/opt/homebrew/bin/python3.12"],
        ]
    return cmds


def find_python():
    """Locate a CPython >= 3.10. The current interpreter wins if suitable."""
    if sys.version_info >= MIN_PY:
        return sys.executable, platform.python_version()
    for cmd in _candidate_commands():
        found = _probe(cmd)
        if found:
            return found
    say("fail", "no Python >= 3.10 found on this machine.")
    print()
    print("      ORION needs CPython 3.10 or newer. Install one, then re-run:")
    print()
    print("        Windows / Windows Server : winget install Python.Python.3.12")
    print("                                  (or https://www.python.org/downloads/")
    print("                                   - tick 'Add python.exe to PATH')")
    print("        Debian / Ubuntu          : sudo apt-get install python3.11")
    print("        RHEL / Fedora / SUSE     : sudo dnf install python3.12")
    print("        macOS                    : brew install python@3.12")
    print()
    return None


# --------------------------------------------------------------------------
# Child-process plumbing (identical commands to the documented CLI)
# --------------------------------------------------------------------------

def build_env():
    """Environment for child processes: PYTHONPATH -> repo src/ (offline)."""
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "").strip()
    parts = [str(SRC_DIR)] + ([existing] if existing else [])
    env["PYTHONPATH"] = os.pathsep.join(parts)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def orion_cmd(args_list):
    return [PYTHON, "-m", "orion"] + list(args_list)


def run_step(args_list, timeout=STEP_TIMEOUT):
    """Run one orion CLI command; return (exit_code, stdout, stderr)."""
    proc = subprocess.run(
        orion_cmd(args_list),
        cwd=str(ROOT),
        env=ENV,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    return (
        proc.returncode,
        proc.stdout.decode("utf-8", "replace"),
        proc.stderr.decode("utf-8", "replace"),
    )


def run_foreground(args_list):
    """Run a blocking orion command (dashboard) with clean Ctrl+C handling."""
    proc = subprocess.Popen(orion_cmd(args_list), cwd=str(ROOT), env=ENV)
    try:
        return proc.wait()
    except KeyboardInterrupt:
        # The child shares the console, so it received Ctrl+C too; give it a
        # moment to run its own shutdown path, then reap it.
        try:
            proc.wait(timeout=10)
        except Exception:  # noqa: BLE001
            proc.kill()
            proc.wait()
        print()
        say("ok", "ORION stopped cleanly.")
        return 0


# --------------------------------------------------------------------------
# Boot sequence: doctor -> status -> demo cycle -> dashboard
# --------------------------------------------------------------------------

def _parse_json(stdout_text):
    """Best-effort parse of a JSON payload from an orion CLI command."""
    try:
        return json.loads(stdout_text)
    except Exception:  # noqa: BLE001 - doctor output is advisory here
        return None


def _json_field(payload, name, default=None):
    if isinstance(payload, dict):
        return payload.get(name, default)
    return default


def step_doctor(opts):
    """Health + safety gate. Aborts unless HEALTHY (unless --force)."""
    say("step", "1/4 health check  : orion doctor")
    code, out, err = run_step(["doctor"])
    if code != 0:
        detail = err.strip()[:300] if err.strip() else ""
        say("fail", "orion doctor exited %d%s" % (code, (": " + detail) if detail else ""))
        return False
    payload = _parse_json(out)
    status = _json_field(payload, "status", "?")
    say("step", "   health status  : %s" % status)
    if status != "HEALTHY":
        say("warn", "health gate is %s - full report:" % status)
        print(out.rstrip())
        if not opts.force:
            say("info", "fix the gate, or re-run with --force to start anyway.")
            return False
        say("warn", "--force given: continuing with a %s system." % status)
    return True


def step_status(opts):
    """Capability report (advisory; never blocks the boot)."""
    say("step", "2/4 capability    : orion status")
    code, out, err = run_step(["status"])
    if code != 0:
        say("warn", "orion status exited %d (continuing)" % code)
        if err.strip():
            print(err.strip()[:400])
        return
    payload = _parse_json(out)
    caps = _json_field(payload, "capabilities", {})
    if isinstance(caps, dict) and caps:
        blocked = sorted(k for k, v in caps.items() if str(v).upper() == "BLOCKED")
        say("step", "   capabilities   : %d reported (%d BLOCKED by design)" % (len(caps), len(blocked)))
        for name in blocked:
            say("info", "     BLOCKED      : %s" % name)
    else:
        say("step", "   capabilities   : reported")


def step_cycle(opts):
    """One full 16-phase executive cycle (smoke test on a synthetic series)."""
    if opts.no_cycle:
        say("step", "3/4 exec cycle    : skipped (--no-cycle)")
        return True
    symbol = opts.symbol or "DEMO"
    say("step", "3/4 exec cycle    : orion run %s" % symbol)
    code, out, err = run_step(["run", symbol])
    if code != 0:
        say("warn", "orion run %s exited %d (continuing to dashboard)" % (symbol, code))
        if err.strip():
            print(err.strip()[:400])
        return True
    payload = _parse_json(out)
    decision = _json_field(payload, "decision", "?")
    regime = _json_field(payload, "market_regime", "?")
    confidence = _json_field(payload, "state_confidence", "?")
    if decision != "?" or regime != "?":
        say("step", "   decision=%s regime=%s state_conf=%s" % (decision, regime, confidence))
        say("info", "   16-phase loop completed; full auditable trace emitted by the CLI.")
    else:
        say("step", "   cycle completed")
    return True


def step_dashboard(opts):
    """Mission Control web dashboard (foreground; Ctrl+C to stop)."""
    host = opts.host or "127.0.0.1"
    port = int(opts.port or 8787)
    if opts.tui:
        say("step", "4/4 mission ctrl  : orion tui (terminal dashboard, q=quit)")
        return run_foreground(["tui"])
    say("step", "4/4 mission ctrl  : orion serve on http://%s:%d  (Ctrl+C to stop)" % (host, port))
    if not opts.no_browser and sys.stdout.isatty():
        try:
            import webbrowser
            webbrowser.open("http://%s:%d" % (host, port))
        except Exception:  # noqa: BLE001 - headless boxes must not crash boot
            pass
    # ``--no-browser``: the CLI would open a tab itself; the launcher owns
    # that so exactly one tab opens (and none on headless machines).
    return run_foreground(["serve", "--host", host, "--port", str(port), "--no-browser"])


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def build_arg_parser():
    parser = argparse.ArgumentParser(
        prog="start",
        description="Start the whole ORION platform with one command (any OS).",
    )
    parser.add_argument("--check", action="store_true",
                        help="doctor + status only, then exit (CI / monitoring).")
    parser.add_argument("--force", action="store_true",
                        help="continue even if the health gate is not HEALTHY.")
    parser.add_argument("--no-cycle", action="store_true",
                        help="skip the demo executive cycle.")
    parser.add_argument("--symbol", default=None,
                        help="symbol for the demo cycle (default: DEMO).")
    parser.add_argument("--host", default=None,
                        help="dashboard bind host (default: 127.0.0.1).")
    parser.add_argument("--port", type=int, default=None,
                        help="dashboard port (default: 8787).")
    parser.add_argument("--no-browser", action="store_true",
                        help="do not open a browser tab.")
    parser.add_argument("--tui", action="store_true",
                        help="terminal mission control instead of the web dashboard.")
    return parser


def main(argv=None):
    global PYTHON, ENV
    parser = build_arg_parser()
    opts = parser.parse_args(argv)

    print(BANNER)
    say("sys", "python       : %s (%s)" % (sys.executable, platform.python_version()))
    say("sys", "platform     : %s" % platform.platform())
    say("sys", "repository   : %s" % ROOT)
    if not SRC_DIR.is_dir():
        say("fail", "src/ not found next to start.py - are you in the ORION repo?")
        return 2

    # Locate an interpreter and pin the child-process environment.
    found = find_python()
    if not found:
        return 2
    PYTHON, pyver = found
    if pyver != platform.python_version():
        say("sys", "interpreter  : %s (%s)" % (PYTHON, pyver))
    ENV = build_env()

    # --- boot sequence -----------------------------------------------------
    if not step_doctor(opts):
        return 1
    step_status(opts)
    if opts.check:
        say("ok", "--check run complete: system is healthy.")
        return 0
    step_cycle(opts)
    return step_dashboard(opts)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        say("ok", "interrupted - ORION stopped.")
        sys.exit(130)
