#!/usr/bin/env python3
"""ORION Repository Synchronization Tool.

Clones, validates, and registers external financial computing engine
repositories into Orion's third_party/ directory structure.

For each repository:
  1. Validate URL
  2. Clone to categorized subdirectory
  3. Detect license
  4. Record commit SHA
  5. Inspect dependencies
  6. Generate manifest
  7. Build adapter scaffold
  8. Register capability

Does NOT allow automatic merging of upstream code into production Orion.
All cloned repos are treated as read-only reference implementations.

Usage:
    python scripts/sync_repositories.py              # preview all planned
    python scripts/sync_repositories.py --repo qlib  # preview one repo
    python scripts/sync_repositories.py --sync       # explicitly sync
"""

from __future__ import annotations

import json
import argparse
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_DIR = ROOT / "registry"
REPOS_FILE = REGISTRY_DIR / "repositories.yaml"
THIRD_PARTY_DIR = ROOT / "third_party"
ADAPTERS_DIR = ROOT / "adapters"
REPORTS_DIR = ROOT / "reports"

# Category → subdirectory mapping
CATEGORY_DIRS: dict[str, str] = {
    "quantitative_research": "research",
    "financial_agent_ai": "research",
    "financial_llm": "research",
    "reinforcement_learning": "reinforcement_learning",
    "rl_environments_datasets": "reinforcement_learning",
    "production_ai_trading": "reinforcement_learning",
    "execution_backtesting": "backtesting",
    "backtesting_parameter_sweeps": "backtesting",
    "event_driven_backtesting": "backtesting",
    "portfolio_optimization": "portfolio",
    "portfolio_optimization_risk": "portfolio",
    "financial_machine_learning": "financial_ml",
    "econometrics_volatility_garch": "financial_ml",
    "financial_data_aggregation": "data",
    "public_market_data": "data",
    "crypto_exchange_connectivity": "execution",
    "broker_market_data": "execution",
}


def _load_repos() -> dict[str, Any]:
    with open(REPOS_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("repositories", {})


def _git_clone(url: str, dest: Path, commit: str | None = None) -> bool:
    """Clone a repository and optionally checkout a specific commit."""
    if dest.exists():
        actual = _get_current_sha(dest)
        if commit and actual != commit:
            print(f"  Existing checkout is not pinned: {actual or 'missing'} != {commit}")
            return False
        print(f"  Already cloned at {dest} ({actual or 'unknown SHA'})")
        return bool(actual)

    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", url, str(dest)],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            print(f"  Clone failed: {result.stderr.strip()}")
            return False

        if commit:
            # Fetch the specific commit for pinning
            fetch = subprocess.run(
                ["git", "fetch", "--depth", "1", "origin", commit],
                capture_output=True, text=True, timeout=120,
                cwd=str(dest),
            )
            if fetch.returncode != 0:
                raise RuntimeError(f"fetch failed: {fetch.stderr.strip()}")
            checkout = subprocess.run(
                ["git", "checkout", commit],
                capture_output=True, text=True, timeout=30,
                cwd=str(dest),
            )
            if checkout.returncode != 0:
                raise RuntimeError(f"checkout failed: {checkout.stderr.strip()}")

        actual = _get_current_sha(dest)
        if commit and actual != commit:
            raise RuntimeError(f"checkout verification failed: {actual or 'missing'} != {commit}")

        return True
    except (subprocess.TimeoutExpired, FileNotFoundError, RuntimeError) as e:
        print(f"  Clone error: {e}")
        if dest.exists():
            shutil.rmtree(dest)
        return False


def _detect_license(repo_path: Path) -> str:
    """Detect license from a cloned repository."""
    license_files = ["LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "COPYING.md"]
    for lf in license_files:
        lp = repo_path / lf
        if lp.exists():
            content = lp.read_text(encoding="utf-8", errors="ignore")[:2000].lower()
            if "apache" in content and "2.0" in content:
                return "Apache-2.0"
            if "mit license" in content or "permission is hereby granted" in content:
                return "MIT"
            if "bsd 3-clause" in content or "bsd-3-clause" in content:
                return "BSD-3-Clause"
            if "bsd 2-clause" in content or "bsd-2-clause" in content:
                return "BSD-2-Clause"
            if "gnu general public license" in content:
                if "version 3" in content or "v3" in content:
                    return "GPL-3.0"
                if "version 2" in content or "v2" in content:
                    return "GPL-2.0"
            if "gnu affero" in content:
                return "AGPL-3.0"
            if "commons clause" in content:
                return "Apache-2.0 with Commons Clause"
            return "DETECTED_UNKNOWN"
    return "NO_LICENSE_FILE"


def _get_current_sha(repo_path: Path) -> str:
    """Get the current commit SHA of a cloned repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
            cwd=str(repo_path),
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def _inspect_dependencies(repo_path: Path) -> list[str]:
    """Inspect Python dependencies from a cloned repo."""
    deps: list[str] = []

    # Check requirements.txt
    req_file = repo_path / "requirements.txt"
    if req_file.exists():
        for line in req_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("-"):
                deps.append(line.split("==")[0].split(">=")[0].split("<=")[0].strip())

    # Check setup.py / pyproject.toml for install_requires
    pyproject = repo_path / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text(encoding="utf-8", errors="ignore")
        if "dependencies" in content:
            deps.append("[see pyproject.toml]")

    return deps[:50]  # cap


def _generate_manifest(name: str, meta: dict[str, Any], repo_path: Path) -> dict[str, Any]:
    """Generate a repository manifest for tracking."""
    sha = _get_current_sha(repo_path) or meta.get("pinned_commit", "")
    detected_license = _detect_license(repo_path) if repo_path.exists() else meta.get("license", "Unknown")
    deps = _inspect_dependencies(repo_path) if repo_path.exists() else []

    return {
        "name": name,
        "owner": meta.get("owner"),
        "repo": meta.get("repo"),
        "upstream_url": meta.get("upstream_url"),
        "pinned_commit": sha,
        "detected_license": detected_license,
        "declared_license": meta.get("license"),
        "import_date": datetime.now(timezone.utc).isoformat(),
        "category": meta.get("category"),
        "integration_mode": meta.get("integration_mode"),
        "capabilities": meta.get("capabilities", []),
        "dependencies": deps,
        "local_path": str(repo_path) if repo_path.exists() else None,
        "cloned": repo_path.exists(),
    }


def sync_repository(name: str, meta: dict[str, Any], *, dry_run: bool = False) -> dict[str, Any]:
    """Sync a single repository: clone, validate, manifest."""
    category = meta.get("category", "uncategorized")
    subdir = CATEGORY_DIRS.get(category, "misc")
    dest = THIRD_PARTY_DIR / subdir / name

    url = meta.get("upstream_url", "")
    commit = meta.get("pinned_commit", "")

    print(f"\n{'─' * 60}")
    print(f"  Repository: {meta.get('owner')}/{meta.get('repo')}")
    print(f"  Category:   {category}")
    print(f"  License:    {meta.get('license')}")
    print(f"  Mode:       {meta.get('integration_mode')}")
    print(f"  Commit:     {commit[:12] if commit else 'UNPINNED'}")
    print(f"  Target:     {dest}")

    if dry_run:
        print(f"  [DRY RUN] Would clone {url}")
        return _generate_manifest(name, meta, dest)

    # Step 1: Validate URL
    if not url:
        print(f"  ❌ No upstream_url defined")
        return {"name": name, "error": "no_url"}

    # Step 2: Clone
    print(f"  Cloning...")
    success = _git_clone(url, dest, commit if commit else None)
    if not success:
        return {"name": name, "error": "clone_failed"}

    # Step 3: Detect license
    detected = _detect_license(dest)
    print(f"  License detected: {detected}")

    # Step 4: Record commit SHA
    actual_sha = _get_current_sha(dest)
    print(f"  Commit SHA: {actual_sha[:12] if actual_sha else 'UNKNOWN'}")

    # Step 5: Inspect dependencies
    deps = _inspect_dependencies(dest)
    if deps:
        print(f"  Dependencies: {len(deps)} found")

    # Step 6: Generate manifest
    manifest = _generate_manifest(name, meta, dest)
    print(f"  ✅ Manifest generated")

    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", help="sync one named repository")
    parser.add_argument(
        "--sync",
        action="store_true",
        help="perform network/filesystem synchronization (default is preview)",
    )
    args = parser.parse_args()
    dry_run = not args.sync
    specific_repo = args.repo

    repos = _load_repos()
    manifests: list[dict[str, Any]] = []

    if specific_repo:
        if specific_repo not in repos:
            print(f"Error: Repository '{specific_repo}' not found in registry.")
            raise SystemExit(1)
        repos_to_sync = {specific_repo: repos[specific_repo]}
    else:
        repos_to_sync = repos

    print(f"ORION Repository Sync — {len(repos_to_sync)} repositories")
    if dry_run:
        print("[DRY RUN MODE]")

    for name, meta in sorted(repos_to_sync.items()):
        manifest = sync_repository(name, meta, dry_run=dry_run)
        manifests.append(manifest)

    # Write inventory
    REPORTS_DIR.mkdir(exist_ok=True)
    inventory_path = REPORTS_DIR / "sync_inventory.json"
    with open(inventory_path, "w", encoding="utf-8") as f:
        json.dump({
            "sync_date": datetime.now(timezone.utc).isoformat(),
            "total": len(manifests),
            "cloned": sum(1 for m in manifests if m.get("cloned")),
            "errors": sum(1 for m in manifests if m.get("error")),
            "repositories": manifests,
        }, f, indent=2)

    print(f"\n{'═' * 60}")
    cloned = sum(1 for m in manifests if m.get("cloned"))
    errors = sum(1 for m in manifests if m.get("error"))
    print(f"  Total: {len(manifests)} | Cloned: {cloned} | Errors: {errors}")
    print(f"  Inventory: {inventory_path}")
    print(f"{'═' * 60}")


if __name__ == "__main__":
    main()
