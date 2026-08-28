"""Generated-code sandbox (P1-1 of TODO.md).

Submodules:
  * :mod:`.policy`  — declarative policy with import + pattern audit
  * :mod:`.runner`  — subprocess-based isolated execution
"""

from .policy import SandboxPolicy
from .runner import PolicyViolation, run_isolated

__all__ = ["PolicyViolation", "SandboxPolicy", "run_isolated"]
