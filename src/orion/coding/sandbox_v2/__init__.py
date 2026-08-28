"""Generated-code sandbox (canonical P1-1 of TODO.md).

Submodules:
  * :mod:`.policy`    — declarative policy with import + pattern audit
  * :mod:`.protocol`  — child-interpreter program and SandboxResult dataclass
  * :mod:`.runner`    — subprocess-based isolated execution

The legacy module :mod:`orion.coding.sandbox` is preserved as a
back-compatibility re-export shim; new code should import from this
package directly.
"""

from .policy import SandboxPolicy
from .protocol import SandboxResult, build_sandbox_program
from .runner import PolicyViolation, run_isolated

__all__ = [
    "PolicyViolation",
    "SandboxPolicy",
    "SandboxResult",
    "build_sandbox_program",
    "run_isolated",
]
