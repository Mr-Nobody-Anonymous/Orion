"""ORION ``.env`` loading (stdlib-only).

ORION never guesses credentials from the environment implicitly: an
adapter or provider must be *handed* its key. This module is the one
place where a ``.env`` file is parsed into ``os.environ`` so that the
existing ``env_or_none`` helpers in the cloud providers and the broker
registry can then read them explicitly.

Design rules
------------

* Parse-only: :func:`load_env` never touches the network and never
  logs values.
* Existing environment variables always win over ``.env`` values
  unless ``override=True`` is passed explicitly.
* Malformed lines are skipped, never raised: a bad ``.env`` must not
  take down an operator session.
* Values may be single- or double-quoted; ``export `` prefixes are
  stripped; inline comments after a space + ``#`` are removed.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

ENV_CANDIDATES: tuple[str, ...] = (".env",)


def parse_env_line(line: str) -> tuple[str, str] | None:
    """Parse one ``KEY=VALUE`` line. Returns ``None`` for anything else."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped.startswith("export "):
        stripped = stripped[len("export "):].strip()
    if "=" not in stripped:
        return None
    key, _, value = stripped.partition("=")
    key = key.strip()
    if not key or not key.replace("_", "").replace(".", "").isalnum():
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1]
    else:
        # Strip an inline comment only for unquoted values.
        hash_index = value.find(" #")
        if hash_index != -1:
            value = value[:hash_index].strip()
    return key, value


def load_env(
    path: str | Path | None = None,
    *,
    override: bool = False,
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Load a ``.env`` file into the process environment.

    Returns the mapping of keys that were applied. Missing files are
    silently ignored (returning ``{}``) so callers can probe the
    default locations unconditionally.
    """
    target: dict[str, str] = dict(os.environ if environ is None else environ)
    candidates = (Path(path),) if path is not None else (Path(name) for name in ENV_CANDIDATES)
    applied: dict[str, str] = {}
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            text = candidate.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            parsed = parse_env_line(line)
            if parsed is None:
                continue
            key, value = parsed
            if override or key not in target:
                target[key] = value
                applied[key] = value
        if path is not None:
            break
    if environ is None:
        for key, value in applied.items():
            os.environ[key] = value
    return applied


def env_status(keys: Mapping[str, str]) -> dict[str, bool]:
    """Report which of ``keys`` (name -> env var) are configured."""
    return {name: bool(os.environ.get(var, "").strip()) for name, var in keys.items()}