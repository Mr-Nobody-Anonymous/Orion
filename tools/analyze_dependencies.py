"""Static dependency analysis of `src/orion/`.

Walks the package, parses every Python file with ``ast``, builds a
module-level import graph, and reports:

- modules that no other module imports at the module level ("orphans"),
- circular dependencies (with lazy/function-body imports filtered
  out, since those are intentional in Python),
- modules that import something that does not exist on disk.

Run as::

    python tools/analyze_dependencies.py
"""

from __future__ import annotations

import ast
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src" / "orion"


def _module_name_for(path: Path) -> str:
    rel = path.relative_to(SRC)
    parts = list(rel.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][:-3]  # strip .py
    return "orion." + ".".join(parts)


def _resolve_import(name: str, level: int, current_module: str) -> str | None:
    """Resolve a relative or absolute import to a fully-qualified module name."""
    if level == 0:
        return name
    parts = current_module.split(".")
    if level >= len(parts):
        base_parts: list[str] = parts[:1]  # ["orion"]
    else:
        base_parts = parts[: len(parts) - level]
    base_str = ".".join(base_parts)
    if name:
        if base_str and base_str != parts[0]:
            return f"{base_str}.{name}"
        return f"{parts[0]}.{name}" if name else parts[0]
    return base_str or parts[0]


def _is_resolved(target: str, all_modules: set[str]) -> bool:
    """True if ``target`` resolves to a real orion module (or a parent of one)."""
    if target in all_modules:
        return True
    while "." in target:
        target = target.rsplit(".", 1)[0]
        if target in all_modules:
            return True
    return False


def _collect_imports_at_level(path: Path) -> list[tuple[str, str]]:
    """Return list of (current_module, target_module) pairs from module-level imports.

    Imports inside function bodies are excluded; they are lazy and do
    not create import-time cycles.
    """
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    module_name = _module_name_for(path)
    edges: list[tuple[str, str]] = []

    def _walk(node: ast.AST) -> None:
        if isinstance(node, ast.Import):
            for alias in node.names:
                target = alias.name
                if target == "orion" or target.startswith("orion."):
                    edges.append((module_name, target))
        elif isinstance(node, ast.ImportFrom):
            level = node.level or 0
            if level == 0:
                target = node.module
                if target and (target == "orion" or target.startswith("orion.")):
                    edges.append((module_name, target))
            else:
                target = _resolve_import(node.module or "", level, module_name)
                if target is not None:
                    edges.append((module_name, target))
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue
            if isinstance(child, ast.ClassDef):
                for grandchild in ast.iter_child_nodes(child):
                    if isinstance(grandchild, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue
                    _walk(grandchild)
                continue
            _walk(child)

    _walk(tree)
    return edges


def _collect_unresolved(path: Path, all_modules: set[str]) -> list[tuple[str, str, str]]:
    """Return (module, target, kind) for any unresolved orion import."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    module_name = _module_name_for(path)
    unresolved: list[tuple[str, str, str]] = []

    def _walk(node: ast.AST) -> None:
        if isinstance(node, ast.Import):
            for alias in node.names:
                target = alias.name
                if target == "orion" or target.startswith("orion."):
                    if not _is_resolved(target, all_modules):
                        unresolved.append((module_name, target, "import"))
        elif isinstance(node, ast.ImportFrom):
            level = node.level or 0
            if level == 0:
                target = node.module
                if target and (target == "orion" or target.startswith("orion.")):
                    if not _is_resolved(target, all_modules):
                        unresolved.append((module_name, target, "from"))
            else:
                target = _resolve_import(node.module or "", level, module_name)
                if target is not None and not _is_resolved(target, all_modules):
                    unresolved.append((module_name, target, "from-relative"))
        for child in ast.iter_child_nodes(node):
            _walk(child)

    _walk(tree)
    return unresolved


def main() -> int:
    py_files = sorted(SRC.rglob("*.py"))
    if not py_files:
        print("no python files found under", SRC)
        return 1

    all_modules: set[str] = set()
    for path in py_files:
        mod = _module_name_for(path)
        all_modules.add(mod)
        parts = mod.split(".")
        for i in range(1, len(parts)):
            all_modules.add(".".join(parts[:i]))

    edges: list[tuple[str, str]] = []
    for path in py_files:
        for src, dst in _collect_imports_at_level(path):
            target = dst
            resolved = None
            while target:
                if target in all_modules and target != src:
                    resolved = target
                    break
                if "." in target:
                    target = target.rsplit(".", 1)[0]
                else:
                    break
            if resolved is not None:
                edges.append((src, resolved))

    importers: dict[str, set[str]] = defaultdict(set)
    imported_by: dict[str, set[str]] = defaultdict(set)
    for src, dst in edges:
        importers[src].add(dst)
        imported_by[dst].add(src)

    print("=" * 60)
    print("ORION dependency analysis")
    print("=" * 60)
    print(f"total modules under src/orion/   : {len(all_modules)}")
    print(f"total module-level import edges  : {len(edges)}")
    print(f"modules with at least one importer: {sum(1 for m in all_modules if imported_by[m])}")
    print(f"modules with no importers (orphans): {sum(1 for m in all_modules if not imported_by[m])}")
    print()

    orphan_candidates = []
    for module in sorted(all_modules):
        if not imported_by[module] and module not in ("orion", "orion.__main__"):
            orphan_candidates.append(module)
    print(f"orphan modules (excluding 'orion' and 'orion.__main__'): {len(orphan_candidates)}")
    for module in orphan_candidates:
        print(f"  - {module}")
    print()

    cycle: list[list[str]] = []
    visited: set[str] = set()

    def dfs(node: str, path_stack: list[str], on_path: set[str]) -> None:
        if node in on_path:
            start = path_stack.index(node)
            cycle.append(path_stack[start:] + [node])
            return
        if node in visited:
            return
        visited.add(node)
        on_path.add(node)
        path_stack.append(node)
        for nxt in sorted(importers[node]):
            dfs(nxt, path_stack, on_path)
        path_stack.pop()
        on_path.discard(node)

    for module in sorted(all_modules):
        dfs(module, [], set())
    real_cycles = [c for c in cycle if len(c) > 1]
    print(f"circular dependency chains: {len(real_cycles)}")
    for chain in real_cycles:
        print(f"  {' -> '.join(chain)}")
    print()

    unresolved: list[tuple[str, str, str]] = []
    for path in py_files:
        unresolved.extend(_collect_unresolved(path, all_modules))
    print(f"unresolved orion.* imports: {len(unresolved)}")
    for mod, target, kind in unresolved[:20]:
        print(f"  {mod} -> {target}  [{kind}]")
    print()

    top = sorted(all_modules, key=lambda m: len(imported_by[m]), reverse=True)
    print("most-imported modules (top 15):")
    for module in top[:15]:
        if imported_by[module]:
            print(f"  {len(imported_by[module]):3d} importers  {module}")
    print()

    top_out = sorted(all_modules, key=lambda m: len(importers[m]), reverse=True)
    print("most-importing modules (top 15):")
    for module in top_out[:15]:
        if importers[module]:
            print(f"  {len(importers[module]):3d} imports    {module}")
    print()

    new_modules = {
        "orion.data.providers.filings": "P1-5 news / SEC / earnings",
        "orion.portfolio.factors": "P1-6 factor intelligence",
        "orion.portfolio.optimizer": "P2-5 portfolio optimizer",
        "orion.dashboard": "P2-1 human governance",
        "orion.agents": "P2-2 multi-agent architecture",
        "orion.compliance": "P2-3 compliance / regulatory",
        "orion.distributed": "P2-4 distributed job execution",
    }
    print("new modules added by this audit:")
    for mod, desc in new_modules.items():
        in_count = len(imported_by.get(mod, set()))
        out_count = len(importers.get(mod, set()))
        status = "wired" if in_count > 0 and out_count > 0 else (
            "leaf" if in_count > 0 else "orphan"
        )
        print(f"  {desc:38s}  importers={in_count:2d}  imports={out_count:2d}  [{status}]")

    return 0


if __name__ == "__main__":
    sys.exit(main())
