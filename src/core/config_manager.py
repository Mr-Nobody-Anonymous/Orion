"""
Orion Configuration Manager
Unified YAML and Environment Variable configuration management.
"""

import os
import logging
from pathlib import Path
from typing import Any, Dict, Optional
import yaml

logger = logging.getLogger(__name__)


class ConfigManager:
    """
    Loads, merges, and validates configuration from YAML files and environment variables.
    """

    def __init__(self, config_dir: Optional[str] = None):
        self.config_dir = Path(config_dir or os.getenv("ORION_CONFIG_DIR", "config"))
        self._config: Dict[str, Any] = {}
        self._load_all_configs()

    def _load_all_configs(self):
        """Loads default and active environment config."""
        default_file = self.config_dir / "default.yml"
        if default_file.exists():
            try:
                with open(default_file, "r", encoding="utf-8") as f:
                    self._config = yaml.safe_load(f) or {}
            except Exception as e:
                logger.warning(f"Could not load default.yml: {e}")

        env = os.getenv("ORION_ENV", "development").lower()
        env_file = self.config_dir / f"{env}.yml"
        if env_file.exists():
            try:
                with open(env_file, "r", encoding="utf-8") as f:
                    env_config = yaml.safe_load(f) or {}
                    self._merge_dicts(self._config, env_config)
            except Exception as e:
                logger.warning(f"Could not load {env_file.name}: {e}")

    def _merge_dicts(self, base: Dict[str, Any], update: Dict[str, Any]):
        for k, v in update.items():
            if isinstance(v, dict) and k in base and isinstance(base[k], dict):
                self._merge_dicts(base[k], v)
            else:
                base[k] = v

    def get(self, key_path: str, default: Any = None) -> Any:
        """Access config using dot notation, e.g. 'brokers.interactive_brokers.host'."""
        keys = key_path.split(".")
        val = self._config
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default
        return val

    def set(self, key_path: str, value: Any):
        """Set config item dynamically using dot notation."""
        keys = key_path.split(".")
        curr = self._config
        for k in keys[:-1]:
            if k not in curr or not isinstance(curr[k], dict):
                curr[k] = {}
            curr = curr[k]
        curr[keys[-1]] = value

    @property
    def raw(self) -> Dict[str, Any]:
        return self._config
