"""Runtime inventory for the curated source-repository ecosystem.

The repositories under ``source_repositories`` are provenance/reference
material, not an implicit Python dependency.  This module exposes that
distinction to operators so the dashboard cannot overstate integration.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
from typing import Any

from orion.integrations.provenance import load_provenance_manifest


@dataclass(frozen=True, slots=True)
class SourceRepositoryRecord:
    name: str
    category: str
    local_path: str
    canonical_url: str
    purpose: str
    integration_mode: str
    status: str
    path_exists: bool
    checkout_type: str
    directly_imported: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _manifest_records(manifest: Path) -> list[dict[str, str]]:
    """Read the small, generated subset of YAML used by MANIFEST.yaml.

    A full YAML dependency is deliberately avoided: this inventory is
    available in the stdlib-only runtime and only needs scalar fields.
    """
    records: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    category = ""
    for raw_line in manifest.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        category_match = re.fullmatch(r"([a-z][a-z0-9_-]*):", line)
        if category_match and not line.startswith(" "):
            category = category_match.group(1)
            continue
        name_match = re.match(r"  - name:\s*(.+)$", line)
        if name_match:
            if current is not None:
                records.append(current)
            current = {"name": name_match.group(1).strip().strip('"'), "category": category}
            continue
        field_match = re.match(r"    ([a-z_]+):\s*(.*)$", line)
        if field_match and current is not None:
            value = field_match.group(2).strip().strip('"')
            current[field_match.group(1)] = value
    if current is not None:
        records.append(current)
    return records


def source_repository_inventory(root: Path | None = None) -> dict[str, Any]:
    """Return a bounded, operator-facing inventory of all manifest entries."""
    project_root = root or Path(__file__).resolve().parents[3]
    source_root = project_root / "source_repositories"
    manifest = source_root / "MANIFEST.yaml"
    records: list[SourceRepositoryRecord] = []
    if manifest.is_file():
        for item in _manifest_records(manifest):
            relative_path = item.get("local_path", "")
            local_path = project_root / relative_path if relative_path else source_root / item["name"]
            records.append(
                SourceRepositoryRecord(
                    name=item["name"],
                    category=item.get("category", "unknown"),
                    local_path=relative_path,
                    canonical_url=item.get("canonical_url", ""),
                    purpose=item.get("purpose", ""),
                    integration_mode=item.get("integration_mode", "unknown"),
                    status=item.get("status", "unknown"),
                    path_exists=local_path.is_dir(),
                    checkout_type=item.get("checkout_type", "unknown"),
                    directly_imported=False,
                )
            )
    else:
        for item in load_provenance_manifest(project_root).values():
            records.append(
                SourceRepositoryRecord(
                    name=item.name,
                    category=item.category,
                    local_path=item.local_path,
                    canonical_url=item.canonical_url,
                    purpose=item.purpose,
                    integration_mode=item.integration_mode,
                    status=item.status,
                    path_exists=item.exists_locally,
                    checkout_type="snapshot",
                    directly_imported=False,
                )
            )

    by_mode: dict[str, int] = {}
    for record in records:
        by_mode[record.integration_mode] = by_mode.get(record.integration_mode, 0) + 1
    return {
        "manifest": str(manifest.relative_to(project_root)),
        "total": len(records),
        "present": sum(record.path_exists for record in records),
        "missing": sum(not record.path_exists for record in records),
        "direct_runtime_imports": 0,
        "by_integration_mode": by_mode,
        "repositories": [record.as_dict() for record in records],
    }
