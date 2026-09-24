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


def load_provenance_manifest(root: Path | None = None) -> dict[str, RepositoryProvenance]:
    """Parse source_repositories/MANIFEST.yaml without external YAML dependencies."""
    project_root = root or Path(__file__).resolve().parents[3]
    manifest_path = project_root / "source_repositories" / "MANIFEST.yaml"

    provenance_map: dict[str, RepositoryProvenance] = {}
    if not manifest_path.is_file():
        return provenance_map

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
