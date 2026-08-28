#!/usr/bin/env python
"""Validate that the ORION implementation matches the architecture spec.

Walks ``config/architecture.yaml`` and confirms:

* every declared ``path`` exists in the source tree
* every ``entrypoints`` module imports cleanly
* every declared provider / asset class / execution mode is wired

Prints a structured report and exits non-zero on any drift.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
ARCH_YAML = ROOT / "config" / "architecture.yaml"


def _indent(raw: str) -> int:
    return len(raw) - len(raw.lstrip(" \t"))


def _parse_simple_yaml(path: Path) -> dict[str, Any]:
    """Tiny YAML reader sufficient for architecture.yaml.

    Supports nested mappings + list-of-dicts at arbitrary depth. Avoids
    pulling PyYAML so the validator stays stdlib-only.
    """
    text_lines = path.read_text(encoding="utf-8").splitlines()
    # Filter comments and blanks but remember original index for indent calc
    tokens: list[tuple[int, str, str]] = []  # (indent, kind, content)
    for raw in text_lines:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.startswith("---") or raw.startswith("..."):
            continue
        ind = _indent(raw)
        stripped = raw.lstrip(" \t")
        if stripped.startswith("- "):
            tokens.append((ind, "list_item", stripped[2:].rstrip()))
        else:
            tokens.append((ind, "key", stripped.rstrip()))

    pos = [0]

    def peek() -> tuple[int, str, str] | None:
        return tokens[pos[0]] if pos[0] < len(tokens) else None

    def consume() -> tuple[int, str, str]:
        t = tokens[pos[0]]
        pos[0] += 1
        return t

    def parse_block(parent_indent: int) -> Any:
        node: Any = None
        while True:
            cur = peek()
            if cur is None or cur[0] < parent_indent:
                return node
            ind, kind, content = consume()
            if kind == "key":
                if ":" not in content:
                    continue
                key, _, value = content.partition(":")
                key = key.strip()
                value = value.strip()
                if value:
                    if node is None:
                        node = {}
                    node[key] = _scalar(value)
                else:
                    # Recurse into child block
                    child_indent = ind + 1
                    if node is None:
                        node = {}
                    node[key] = parse_block(child_indent)
            else:  # list_item
                # List at this indent; if next is a list item at the same indent
                # it's a list of scalars. If next item is a key, it's a list
                # of dicts.
                if node is None:
                    node = []
                # Look ahead: if the list item content has ':' it's the start
                # of a dict; the rest of its body comes from following
                # deeper-indented lines.
                if ":" in content:
                    item: dict[str, Any] = {}
                    k, _, v = content.partition(":")
                    item[k.strip()] = _scalar(v.strip())
                    # Following more-indented keys are part of this item
                    while True:
                        cur2 = peek()
                        if cur2 is None or cur2[0] <= ind:
                            break
                        ind2, kind2, content2 = consume()
                        if kind2 == "key" and ":" in content2:
                            k2, _, v2 = content2.partition(":")
                            item[k2.strip()] = _scalar(v2.strip()) if v2.strip() else None
                        else:
                            # Should not happen; rewind one
                            pos[0] -= 1
                            break
                    node.append(item)
                else:
                    node.append(_scalar(content.strip()))
        # unreachable; parser returns when indent drops

    return parse_block(-1)  # type: ignore[return-value]


def _scalar(value: str) -> Any:
    if not value:
        return ""
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    if value.lower() in {"true", "yes"}:
        return True
    if value.lower() in {"false", "no"}:
        return False
    if value.lower() in {"null", "~"}:
        return None
    if value.startswith("[") and value.endswith("]"):
        return [_scalar(p.strip()) for p in value[1:-1].split(",") if p.strip()]
    return value


def _module_to_path(module: str) -> Path:
    parts = module.split(".")
    return SRC / Path(*parts[:-1]) / (parts[-1] + ".py")


def _module_exists(module: str) -> bool:
    try:
        importlib.import_module(module)
        return True
    except Exception:
        return False


def validate() -> int:
    if not ARCH_YAML.exists():
        print(f"ERROR: {ARCH_YAML} not found", file=sys.stderr)
        return 2
    spec = _parse_simple_yaml(ARCH_YAML)

    failures: list[str] = []
    warnings: list[str] = []
    successes: list[str] = []

    # Check core components and their paths
    components = spec.get("components", {})
    if not isinstance(components, dict) or not components:
        print("ERROR: 'components' missing or malformed in architecture.yaml", file=sys.stderr)
        return 2

    for name, info in components.items():
        if not isinstance(info, dict):
            continue
        path = info.get("path", "")
        full = ROOT / path
        if not full.exists():
            failures.append(f"component {name!r}: path {path!r} missing")
            continue
        successes.append(f"component {name!r}: {path} present")

        # Entrypoints
        for entry in info.get("entrypoints", []):
            if not _module_exists(entry):
                failures.append(f"component {name!r}: entrypoint {entry!r} not importable")
            else:
                successes.append(f"component {name!r}: entrypoint {entry} OK")

        # Sub-integrations
        for integ in info.get("integrations", []):
            if isinstance(integ, dict):
                ipath = ROOT / integ.get("path", "")
                if not ipath.exists():
                    warnings.append(
                        f"component {name!r}: integration path {integ.get('path')!r} not yet present"
                    )

    # Check AI providers
    providers = spec.get("ai_providers", [])
    if isinstance(providers, list):
        for prov in providers:
            if isinstance(prov, dict):
                ppath = ROOT / prov.get("path", "")
                if not ppath.exists():
                    warnings.append(
                        f"provider {prov.get('name')!r}: file {prov.get('path')!r} not yet present"
                    )
                else:
                    successes.append(
                        f"provider {prov.get('name')!r}: {prov.get('path')} present"
                    )

    # Asset classes
    ac = spec.get("asset_classes", {})
    if isinstance(ac, dict):
        enabled = ac.get("enabled", []) or []
        supports = ac.get("architecture_supports", []) or []
        if not enabled:
            failures.append("asset_classes: no enabled classes (at least EQUITY required)")
        if not supports:
            failures.append("asset_classes: architecture_supports list empty")
        successes.append(f"asset_classes: {len(enabled)} enabled, {len(supports)} supported")

    # Execution modes
    em = spec.get("execution_modes", [])
    if isinstance(em, list):
        names = [e.get("name") if isinstance(e, dict) else e for e in em]
        if "simulation" not in names:
            failures.append("execution_modes: 'simulation' must be declared")
        if "live" in names:
            for e in em:
                if isinstance(e, dict) and e.get("name") == "live" and not e.get("blocked_by_default"):
                    failures.append("execution_modes: 'live' must be blocked_by_default")
        successes.append(f"execution_modes: {names}")

    # Autonomy levels
    al = spec.get("autonomy_levels", [])
    if isinstance(al, list):
        levels = [a.get("level") if isinstance(a, dict) else a for a in al]
        levels_int = []
        for lv in levels:
            try:
                levels_int.append(int(lv))
            except (TypeError, ValueError):
                pass
        if 0 not in levels_int:
            failures.append("autonomy_levels: level 0 must be declared")
        if not levels_int or max(levels_int) < 4:
            warnings.append("autonomy_levels: max level below 4")
        successes.append(f"autonomy_levels: {levels}")

    # Repository integration modes
    rim = spec.get("repository_integration_modes", [])
    if isinstance(rim, list) and rim:
        successes.append(f"repository_integration_modes: {len(rim)} modes declared")

    # Report
    print("=" * 78)
    print("ORION architecture validation report")
    print("=" * 78)
    print(f"spec: {ARCH_YAML.relative_to(ROOT)}")
    print(f"successes: {len(successes)}")
    print(f"warnings:  {len(warnings)}")
    print(f"failures:  {len(failures)}")
    print()

    if warnings:
        print("-- warnings (not yet implemented, expected) --")
        for w in warnings:
            print(f"  * {w}")
        print()

    if failures:
        print("-- failures (must fix) --")
        for f in failures:
            print(f"  * {f}")
        print()
        print("VALIDATION FAILED")
        return 1

    print("VALIDATION OK")
    return 0


if __name__ == "__main__":
    sys.exit(validate())
