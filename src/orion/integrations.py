from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class IntegrationStatus:
    name: str
    available: bool
    source_path: str | None
    note: str


def inspect_local_integrations(workspace_root: str | Path | None = None) -> tuple[IntegrationStatus, ...]:
    root = Path(workspace_root) if workspace_root else None
    statuses = []
    for name in ("ollama", "qlib", "vectorbt", "torch", "py_vollib"):
        spec = importlib.util.find_spec(name)
        source_path = str(spec.origin) if spec and spec.origin else None
        note = "available through Python import path" if spec else "not installed"
        if root and (root / name).exists():
            note = "local checkout shadows package; use an isolated environment or subprocess adapter"
        statuses.append(IntegrationStatus(name, spec is not None, source_path, note))
    return tuple(statuses)
