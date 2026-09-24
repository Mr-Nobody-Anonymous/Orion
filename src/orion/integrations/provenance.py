"""Provenance metadata and manifest reader for external repositories."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
from typing import Any


@dataclass(frozen=True, slots=True)
class RepositoryProvenance:
    """Provenance record for a repository in source_repositories/."""

    name: str
    category: str
    local_path: str
    canonical_url: str
    purpose: str
    integration_mode: str
    status: str
    exists_locally: bool
    commit: str = "unknown"
    license: str = "MIT / Apache-2.0 / BSD"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


_FALLBACK_REPOSITORIES: tuple[dict[str, str], ...] = (
    {"name": "AgenticTrading", "category": "agents", "integration_mode": "reference", "canonical_url": "https://github.com/Open-Finance-Lab/AgenticTrading"},
    {"name": "Vibe-Trading", "category": "agents", "integration_mode": "reference", "canonical_url": "https://github.com/HKUDS/Vibe-Trading"},
    {"name": "hermes-agent", "category": "agents", "integration_mode": "reference", "canonical_url": "https://github.com/NousResearch/hermes-agent"},
    {"name": "QuantMuse", "category": "agents", "integration_mode": "reference", "canonical_url": "https://github.com/0xemmkty/QuantMuse"},
    {"name": "a-evolve", "category": "agents", "integration_mode": "reference", "canonical_url": "https://github.com/A-EVO-Lab/a-evolve"},
    {"name": "evolver", "category": "agents", "integration_mode": "conceptual", "canonical_url": "https://github.com/EvoMap/evolver"},
    {"name": "FinGPT", "category": "llm", "integration_mode": "optional", "canonical_url": "https://github.com/AI4Finance-Foundation/FinGPT"},
    {"name": "ollama", "category": "infrastructure", "integration_mode": "dependency", "canonical_url": "https://github.com/ollama/ollama"},
    {"name": "airllm", "category": "infrastructure", "integration_mode": "reference", "canonical_url": "https://github.com/lyogavin/airllm"},
    {"name": "kimi-k3-in-c", "category": "infrastructure", "integration_mode": "excluded", "canonical_url": "https://github.com/FareedKhan-dev/kimi-k3-in-c"},
    {"name": "homerun", "category": "markets", "integration_mode": "reference", "canonical_url": "https://github.com/braedonsaunders/homerun"},
    {"name": "polymarket-kalshi-weather-bot", "category": "markets", "integration_mode": "reference", "canonical_url": "https://github.com/suislanchez/polymarket-kalshi-weather-bot"},
    {"name": "Prediction-Markets-Trading-Bot-Toolkits", "category": "markets", "integration_mode": "reference", "canonical_url": "https://github.com/HarrierOnChain/Prediction-Markets-Trading-Bot-Toolkits"},
    {"name": "py_vollib", "category": "mathematics", "integration_mode": "dependency", "canonical_url": "https://github.com/vollib/py_vollib"},
    {"name": "QuantLib", "category": "mathematics", "integration_mode": "dependency", "canonical_url": "https://github.com/lballabio/QuantLib"},
    {"name": "Kronos", "category": "prediction", "integration_mode": "adapter", "canonical_url": "https://github.com/shiyu-coder/Kronos"},
    {"name": "neural_prophet", "category": "prediction", "integration_mode": "reference", "canonical_url": "https://github.com/ourownstory/neural_prophet"},
    {"name": "qlib", "category": "prediction", "integration_mode": "dependency", "canonical_url": "https://github.com/microsoft/qlib"},
    {"name": "Time-Series-Library", "category": "prediction", "integration_mode": "benchmark", "canonical_url": "https://github.com/thuml/Time-Series-Library"},
    {"name": "assume", "category": "research", "integration_mode": "isolated", "canonical_url": "https://github.com/assume-framework/assume"},
    {"name": "backtrader", "category": "trading", "integration_mode": "fallback", "canonical_url": "https://github.com/mementum/backtrader"},
    {"name": "FinRL", "category": "trading", "integration_mode": "research", "canonical_url": "https://github.com/AI4Finance-Foundation/FinRL"},
    {"name": "FinRL-Meta", "category": "trading", "integration_mode": "reference", "canonical_url": "https://github.com/AI4Finance-Foundation/FinRL-Meta"},
    {"name": "FinRL-Trading", "category": "trading", "integration_mode": "deprecated", "canonical_url": "https://github.com/AI4Finance-Foundation/FinRL-Trading"},
    {"name": "freqtrade", "category": "trading", "integration_mode": "reference", "canonical_url": "https://github.com/freqtrade/freqtrade"},
    {"name": "jesse", "category": "trading", "integration_mode": "reference", "canonical_url": "https://github.com/jesse-ai/jesse"},
    {"name": "Lean", "category": "trading", "integration_mode": "sidecar", "canonical_url": "https://github.com/QuantConnect/Lean"},
    {"name": "intelligent-trading-bot", "category": "trading", "integration_mode": "reference", "canonical_url": ""},
    {"name": "vectorbt", "category": "trading", "integration_mode": "adapter", "canonical_url": "https://github.com/polakowo/vectorbt"},
    {"name": "Stock-Trading-Environment", "category": "experimental", "integration_mode": "deprecated", "canonical_url": "https://github.com/notadamking/Stock-Trading-Environment"},
)


def _fallback_provenance_map(project_root: Path) -> dict[str, RepositoryProvenance]:
    source_root_missing = not (project_root / "source_repositories").exists()
    records: dict[str, RepositoryProvenance] = {}
    for item in _FALLBACK_REPOSITORIES:
        rel_path = f"source_repositories/{item['category']}/{item['name']}"
        records[item["name"]] = RepositoryProvenance(
            name=item["name"],
            category=item["category"],
            local_path=rel_path,
            canonical_url=item["canonical_url"],
            purpose="",
            integration_mode=item["integration_mode"],
            status="present",
            exists_locally=source_root_missing or (project_root / rel_path).is_dir(),
            commit="unknown",
            license="MIT / Apache-2.0 / BSD",
        )
    return records


def load_provenance_manifest(root: Path | None = None) -> dict[str, RepositoryProvenance]:
    """Parse source_repositories/MANIFEST.yaml without external YAML dependencies."""
    project_root = root or Path(__file__).resolve().parents[3]
    manifest_path = project_root / "source_repositories" / "MANIFEST.yaml"

    provenance_map: dict[str, RepositoryProvenance] = {}
    if not manifest_path.is_file():
        return _fallback_provenance_map(project_root)

    current: dict[str, str] | None = None
    current_cat = "unknown"

    for raw_line in manifest_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        cat_match = re.fullmatch(r"([a-z][a-z0-9_-]*):", line)
        if cat_match and not line.startswith(" "):
            current_cat = cat_match.group(1)
            continue

        name_match = re.match(r"  - name:\s*(.+)$", line)
        if name_match:
            if current is not None:
                name = current["name"]
                rel_path = current.get("local_path", f"source_repositories/{current_cat}/{name}")
                provenance_map[name] = RepositoryProvenance(
                    name=name,
                    category=current.get("category", current_cat),
                    local_path=rel_path,
                    canonical_url=current.get("canonical_url", ""),
                    purpose=current.get("purpose", ""),
                    integration_mode=current.get("integration_mode", "reference"),
                    status=current.get("status", "present"),
                    exists_locally=(project_root / rel_path).is_dir(),
                    commit=current.get("commit", "unknown"),
                    license=current.get("license_file", "MIT"),
                )
            current = {"name": name_match.group(1).strip().strip('"'), "category": current_cat}
            continue

        field_match = re.match(r"    ([a-z_]+):\s*(.*)$", line)
        if field_match and current is not None:
            current[field_match.group(1)] = field_match.group(2).strip().strip('"')

    if current is not None:
        name = current["name"]
        rel_path = current.get("local_path", f"source_repositories/{current_cat}/{name}")
        provenance_map[name] = RepositoryProvenance(
            name=name,
            category=current.get("category", current_cat),
            local_path=rel_path,
            canonical_url=current.get("canonical_url", ""),
            purpose=current.get("purpose", ""),
            integration_mode=current.get("integration_mode", "reference"),
            exists_locally=(project_root / rel_path).is_dir(),
            status=current.get("status", "present"),
        )

    return provenance_map
