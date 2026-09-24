"""AST-based static analysis for generated candidate code.

Extends the security verification in `verification.py` with structural
metrics: complexity, imports, function inventory. Analysis is a pre-filter,
not a guarantee; the sandbox remains the execution boundary.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CodeAnalysis:
    parses: bool
    lines: int
    function_count: int
    max_complexity: int
    imports: tuple[str, ...]
    issues: tuple[str, ...]

    @property
    def acceptable(self) -> bool:
        return self.parses and not self.issues


ALLOWED_IMPORT_ROOTS = frozenset({
    "math", "statistics", "decimal", "itertools", "functools", "collections",
    "dataclasses", "typing", "random", "orion",
})

FORBIDDEN_CALLS = frozenset({"exec", "eval", "compile", "__import__", "open", "input"})
FORBIDDEN_ATTRIBUTES = frozenset({"system", "popen", "remove", "unlink", "rmtree"})


def _cyclomatic(node: ast.AST) -> int:
    complexity = 1
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.For, ast.While, ast.ExceptHandler, ast.With)):
            complexity += 1
        elif isinstance(child, ast.BoolOp):
            complexity += len(child.values) - 1
    return complexity


def analyze_source(source: str) -> CodeAnalysis:
    """Static analysis: parse, count, and scan for dangerous constructs."""
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        return CodeAnalysis(False, 0, 0, 0, (), (f"syntax error: {error.msg}",))
    lines = len(source.splitlines())
    functions = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    max_complexity = max((_cyclomatic(f) for f in functions), default=1)
    imports: list[str] = []
    issues: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
                if alias.name.split(".")[0] not in ALLOWED_IMPORT_ROOTS:
                    issues.append(f"import outside allowlist: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            imports.append(node.module or "")
            if root not in ALLOWED_IMPORT_ROOTS:
                issues.append(f"import outside allowlist: {node.module}")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
            issues.append(f"forbidden call: {node.func.id}")
        elif (
            isinstance(node, ast.Attribute)
            and node.attr in FORBIDDEN_ATTRIBUTES
        ):
            issues.append(f"forbidden attribute access: {node.attr}")
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            full = f"{node.value.id}.{node.attr}"
            if node.attr == "environ":
                issues.append(f"environment access requires approval: {full}")
    return CodeAnalysis(
        True,
        lines,
        len(functions),
        max_complexity,
        tuple(sorted({name for name in imports if name})),
        tuple(sorted(set(issues))),
    )
