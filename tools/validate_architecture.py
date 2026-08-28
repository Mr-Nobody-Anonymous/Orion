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


def _parse_simple_yaml(path: Path) -> dict[str, Any]:
    """Tiny YAML reader sufficient for architecture.yaml.

    The architecture spec uses only top-level scalars, mappings, and
    ``- key: value`` list-of-dicts — no anchors, no flow syntax. We
    deliberately avoid pulling in PyYAML to keep the validation tool
    stdlib-only.
    """
    result: dict[str, Any] = {}
    lines = path.read_text(encoding="utf-8").splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i]
        if not raw.strip() or raw.lstrip().startswith("#") or raw.startswith("---") or raw.startswith("..."):
            i += 1
            continue
        # Top-level key (no leading whitespace)
        if not raw.startswith((" ", "\t")) and ":" in raw:
            key, _, value = raw.partition(":")
            key = key.strip()
            value = value.strip()
            if value:
                result[key] = _scalar(value)
                i += 1
                continue
            # Map or list-of-dicts follows at deeper indent
            child: list[Any] = []
            j = i + 1
            while j < len(lines):
                child_raw = lines[j]
                if not child_raw.strip() or child_raw.lstrip().startswith("#"):
                    j += 1
                    continue
                # Blank or outdented: stop
                if not child_raw.startswith((" ", "\t")):
                    break
                # List item: "- key: value" or "- value"
                stripped = child_raw.lstrip(" \t")
                if stripped.startswith("- "):
                    item: dict[str, Any] = {}
                    inner = stripped[2:]
                    if ":" in inner:
                        k, _, v = inner.partition(":")
                        item[k.strip()] = _scalar(v.strip())
                    else:
                        item = _scalar(inner.strip())  # type: ignore[assignment]
                    # Following indented key/value pairs belong to this item
                    k = j + 1
                    while k < len(lines):
                        nxt = lines[k]
                        if not nxt.strip():
                            k += 1; continue
                        if not nxt.startswith((" ", "\t")) or nxt.lstrip(" \t").startswith("- "):
                            break
                        ns = nxt.lstrip(" \t")
                        if ":" in ns:
                            kk, _, vv = ns.partition(":")
                            if isinstance(item, dict):
                                item[kk.strip()] = _scalar(vv.strip())
                        k += 1
                    child.append(item)
                    j = k
                    continue
                # Mapping continuation: "  key: value" or "  key:"
                if ":" in stripped:
                    item_kv: dict[str, Any] = {}
                    kk, _, vv = stripped.partition(":")
                    item_kv[kk.strip()] = _scalar(vv.strip()) if vv.strip() else None
                    child.append(item_kv)
                j += 1
            # Decide: list of dicts (component) -> keep as list; otherwise group
            result[key] = child
            i = j
            continue
        i += 1
    return result


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
    if not isinstance(components, dict):
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
        enabled = ac.get("enabled", [])
        supports = ac.get("architecture_supports", [])
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
        if 0 not in levels:
            failures.append("autonomy_levels: level 0 must be declared")
        if max(levels) < 4:
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
