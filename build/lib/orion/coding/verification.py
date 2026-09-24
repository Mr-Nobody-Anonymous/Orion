from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CodeVerification:
    accepted: bool
    issues: tuple[str, ...]


def verify_candidate_source(source: str) -> CodeVerification:
    """Static gate for generated candidate code; execution is intentionally out of process."""
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        return CodeVerification(False, (f"syntax error: {error.msg}",))
    forbidden = {"exec", "eval", "compile", "__import__"}
    issues: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in forbidden:
            issues.append(f"forbidden call: {node.func.id}")
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [alias.name.split(".")[0] for alias in node.names]
            if any(name in {"subprocess", "socket"} for name in names):
                issues.append("network or process import requires sandbox approval")
    return CodeVerification(not issues, tuple(sorted(set(issues))))
