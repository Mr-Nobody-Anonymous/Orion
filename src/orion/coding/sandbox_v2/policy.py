"""Sandbox policy.

A :class:`SandboxPolicy` declares:

  * the maximum wall-clock budget
  * the maximum output size
  * the set of *allowed* top-level imports (deny-by-default)
  * the set of *allowed* top-level calls in the source (regex-based)
  * whether network access is permitted
  * the working directory (defaults to a per-run temporary directory)

The policy is a *declarative* layer; the actual enforcement happens in
:mod:`.runner` via subprocess + rlimit + filesystem chdir.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SandboxPolicy:
    timeout_seconds: float = 10.0
    max_output_bytes: int = 64 * 1024
    allowed_imports: frozenset[str] = frozenset({
        "math", "statistics", "json", "collections", "itertools", "functools",
        "typing", "dataclasses", "enum", "re", "random", "datetime",
    })
    forbidden_patterns: tuple[str, ...] = (
        r"\bos\.system\b",
        r"\bsubprocess\b",
        r"\b__import__\b",
        r"\beval\(",
        r"\bexec\(",
        r"\bopen\(['\"]",
    )
    allow_network: bool = False
    working_directory: str | None = None  # None -> use a per-run tempdir
    name: str = "default"

    def check_source(self, source: str) -> list[str]:
        """Return a list of policy violations for ``source``.

        The list is empty if the source is admissible.
        """
        violations: list[str] = []
        # import audit
        for match in re.finditer(r"^\s*import\s+([\w.]+)|^\s*from\s+([\w.]+)\s+import", source, re.MULTILINE):
            mod = match.group(1) or match.group(2)
            root = mod.split(".")[0]
            if root not in self.allowed_imports:
                violations.append(f"import_not_allowed:{root}")
        # forbidden patterns
        for pattern in self.forbidden_patterns:
            if re.search(pattern, source):
                violations.append(f"forbidden_pattern:{pattern}")
        return violations
