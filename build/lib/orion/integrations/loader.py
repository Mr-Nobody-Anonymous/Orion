"""Safe dynamic import loader with error trapping and isolation."""

from __future__ import annotations

import importlib
import logging
from typing import Any

logger = logging.getLogger(__name__)


def safe_import_module(module_name: str) -> tuple[Any | None, str | None]:
    """Safely import a Python module without crashing on missing packages."""
    try:
        mod = importlib.import_module(module_name)
        return mod, None
    except ImportError as exc:
        return None, str(exc)
    except Exception as exc:
        logger.warning(f"Error loading module {module_name}: {exc}")
        return None, str(exc)


def is_package_available(package_name: str) -> bool:
    """Check if a package is importable without loading its full tree."""
    mod, err = safe_import_module(package_name)
    return mod is not None and err is None
