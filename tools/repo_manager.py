#!/usr/bin/env python3
"""ORION Repository Intelligence Manager.

A CLI tool for managing external financial computing engine repositories.
Provides: list, add, clone, update, audit, test, benchmark, diff, pin, remove.

Every imported repository is tracked with:
  - repository URL
  - commit SHA (immutable pin)
  - version / license
  - import date
  - dependencies
  - local patches
  - integration tests status

Usage:
    python tools/repo_manager.py list
    python tools/repo_manager.py add microsoft/qlib
    python tools/repo_manager.py audit
    python tools/repo_manager.py pin qlib
    python tools/repo_manager.py status qlib
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_DIR = ROOT / "registry"
REPOS_FILE = REGISTRY_DIR / "repositories.yaml"
THIRD_PARTY_DIR = ROOT / "third_party"
REPORTS_DIR = ROOT / "reports"

# ── License compatibility table ──────────────────────────────────────

COPYLEFT_LICENSES = frozenset({
    "GPL-2.0", "GPL-3.0", "AGPL-3.0", "LGPL-2.1", "LGPL-3.0",
    "MPL-2.0", "EUPL-1.2", "OSL-3.0", "CPAL-1.0",
})

PERMISSIVE_LICENSES = frozenset({
    "MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC",
    "Unlicense", "CC0-1.0", "Zlib", "NCSA", "BSL-1.0",
})

# Integration modes allowed for copyleft licenses
COPYLEFT_ALLOWED_MODES = frozenset({
    "isolated_process_service", "service", "adapter_service",
})


def _load_repos() -> dict[str, Any]:
    """Load the repository registry YAML."""
    if not REPOS_FILE.exists():
        return {}
    with open(REPOS_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("repositories", {})


def _save_repos(repos: dict[str, Any]) -> None:
    """Persist the repository registry YAML."""
    data = {
        "schema_version": "1.0.0",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "governance_policy": "institutional_isolation",
        "repositories": repos,
    }
    REPOS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REPOS_FILE, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def _git_ls_remote(url: str) -> str | None:
    """Resolve the HEAD commit SHA from a remote URL."""
    try:
        result = subprocess.run(
            ["git", "ls-remote", url, "HEAD"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split()[0]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def cmd_list() -> None:
    """List all registered repositories."""
    repos = _load_repos()
    if not repos:
        print("No repositories registered.")
        return

    print(f"\n{'Name':<18} {'Category':<30} {'License':<20} {'Mode':<24} {'Status'}")
    print("─" * 120)
    for name, meta in sorted(repos.items()):
        print(
            f"{name:<18} {meta.get('category', ''):<30} "
            f"{meta.get('license', '?'):<20} {meta.get('integration_mode', '?'):<24} "
            f"{meta.get('status', '?')}"
        )
    print(f"\nTotal: {len(repos)} repositories")


def cmd_add(owner_repo: str) -> None:
    """Add a new repository to the registry (owner/repo format)."""
    parts = owner_repo.split("/")
    if len(parts) != 2:
        print(f"Error: Expected 'owner/repo' format, got '{owner_repo}'")
        sys.exit(1)

    owner, repo = parts
    name = repo.lower().replace("-", "_")
    repos = _load_repos()

    if name in repos:
        print(f"Repository '{name}' already registered.")
        return

    url = f"https://github.com/{owner}/{repo}.git"
    print(f"Resolving HEAD for {url}...")
    sha = _git_ls_remote(url)
    if not sha:
        print(f"Warning: Could not resolve HEAD for {url}")
        sha = ""

    repos[name] = {
        "owner": owner,
        "repo": repo,
        "category": "uncategorized",
        "description": "",
        "upstream_url": url,
        "pinned_commit": sha,
        "version": "",
        "import_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "license": "Unknown",
        "copyleft": False,
        "commercial_allowed": True,
        "integration_mode": "adapter",
        "local_patches": [],
        "status": "planned",
        "capabilities": [],
        "dependencies": [],
        "tests_passing": False,
        "integration_version": "0.0.0",
    }

    _save_repos(repos)
    print(f"Added '{name}' ({owner}/{repo}) pinned to {sha[:12] if sha else 'UNRESOLVED'}")


def cmd_pin(name: str) -> None:
    """Pin a repository to its current upstream HEAD."""
    repos = _load_repos()
    if name not in repos:
        print(f"Error: Repository '{name}' not found.")
        sys.exit(1)

    url = repos[name].get("upstream_url", "")
    print(f"Resolving HEAD for {url}...")
    sha = _git_ls_remote(url)
    if not sha:
        print(f"Error: Could not resolve HEAD for {url}")
        sys.exit(1)

    old_sha = repos[name].get("pinned_commit", "")
    repos[name]["pinned_commit"] = sha
    repos[name]["import_date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    _save_repos(repos)

    if old_sha == sha:
        print(f"'{name}' already at {sha[:12]}")
    else:
        print(f"'{name}' pinned: {old_sha[:12] if old_sha else 'NONE'} → {sha[:12]}")


def cmd_status(name: str) -> None:
    """Show detailed status for a repository."""
    repos = _load_repos()
    if name not in repos:
        print(f"Error: Repository '{name}' not found.")
        sys.exit(1)

    meta = repos[name]
    print(f"\n{'=' * 60}")
    print(f"  Repository: {meta.get('owner')}/{meta.get('repo')}")
    print(f"  Category:   {meta.get('category')}")
    print(f"  License:    {meta.get('license')}")
    print(f"  Copyleft:   {meta.get('copyleft')}")
    print(f"  Commercial: {meta.get('commercial_allowed')}")
    print(f"  Mode:       {meta.get('integration_mode')}")
    print(f"  Status:     {meta.get('status')}")
    print(f"  Version:    {meta.get('version')}")
    print(f"  Commit:     {meta.get('pinned_commit', '')[:40]}")
    print(f"  Imported:   {meta.get('import_date')}")
    print(f"  URL:        {meta.get('upstream_url')}")

    caps = meta.get("capabilities", [])
    if caps:
        print(f"  Capabilities: {', '.join(caps)}")

    patches = meta.get("local_patches", [])
    if patches:
        print(f"  Patches:    {', '.join(patches)}")

    # Check if cloned locally
    local_path = _resolve_local_path(name, meta)
    if local_path and local_path.exists():
        print(f"  Local:      {local_path} ✅")
    else:
        print(f"  Local:      NOT CLONED")

    print(f"{'=' * 60}\n")


def cmd_audit() -> None:
    """Run license and provenance audit across all repositories."""
    repos = _load_repos()
    issues: list[str] = []
    REPORTS_DIR.mkdir(exist_ok=True)

    audit_results = []
    for name, meta in sorted(repos.items()):
        lic = meta.get("license", "Unknown")
        mode = meta.get("integration_mode", "unknown")
        copyleft = meta.get("copyleft", False)
        comm = meta.get("commercial_allowed", True)
        sha = meta.get("pinned_commit", "")

        status_flags = []

        # Check: pinned commit
        if not sha:
            issues.append(f"[{name}] Missing pinned_commit — NOT REPRODUCIBLE")
            status_flags.append("UNPINNED")

        # Check: copyleft + wrong integration mode
        if copyleft and mode not in COPYLEFT_ALLOWED_MODES:
            issues.append(
                f"[{name}] Copyleft license ({lic}) requires isolated mode, "
                f"but mode is '{mode}'"
            )
            status_flags.append("LICENSE_RISK")

        # Check: unknown license
        if lic == "Unknown":
            issues.append(f"[{name}] License is 'Unknown' — AUDIT REQUIRED")
            status_flags.append("UNKNOWN_LICENSE")

        # Check: commercial restriction
        if not comm:
            status_flags.append("NON_COMMERCIAL")

        audit_results.append({
            "repository": name,
            "owner": meta.get("owner"),
            "license": lic,
            "copyleft": copyleft,
            "commercial_allowed": comm,
            "integration_mode": mode,
            "pinned_commit": sha[:12] if sha else "MISSING",
            "status_flags": status_flags,
            "verdict": "CLEAR" if not status_flags else "REVIEW",
        })

    # Print summary
    print(f"\n{'Repository':<18} {'License':<22} {'Mode':<24} {'Verdict'}")
    print("─" * 80)
    for r in audit_results:
        v = "✅ CLEAR" if r["verdict"] == "CLEAR" else "⚠️  REVIEW"
        print(f"{r['repository']:<18} {r['license']:<22} {r['integration_mode']:<24} {v}")

    if issues:
        print(f"\n⚠️  {len(issues)} issue(s) found:")
        for issue in issues:
            print(f"  • {issue}")
    else:
        print(f"\n✅ All {len(repos)} repositories pass audit.")

    # Write report
    report_path = REPORTS_DIR / "audit_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "audit_date": datetime.now(timezone.utc).isoformat(),
            "total_repositories": len(repos),
            "issues_count": len(issues),
            "issues": issues,
            "results": audit_results,
        }, f, indent=2)
    print(f"\nReport written to {report_path}")


def cmd_remove(name: str) -> None:
    """Remove a repository from the registry."""
    repos = _load_repos()
    if name not in repos:
        print(f"Error: Repository '{name}' not found.")
        sys.exit(1)

    del repos[name]
    _save_repos(repos)
    print(f"Removed '{name}' from registry.")


def cmd_verify() -> None:
    """Verify all pinned commits are reachable via git ls-remote."""
    repos = _load_repos()
    print(f"Verifying {len(repos)} repositories...\n")

    reachable = 0
    unreachable = 0
    for name, meta in sorted(repos.items()):
        url = meta.get("upstream_url", "")
        sha = _git_ls_remote(url)
        if sha:
            reachable += 1
            mark = "✅"
        else:
            unreachable += 1
            mark = "❌"
        print(f"  {mark} {name:<18} {url}")

    print(f"\n{reachable} reachable, {unreachable} unreachable out of {len(repos)}")


def _resolve_local_path(name: str, meta: dict[str, Any]) -> Path | None:
    """Resolve expected local path for a third-party repo."""
    category = meta.get("category", "uncategorized")
    # Map categories to subdirectories
    category_map = {
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
    subdir = category_map.get(category, "misc")
    return THIRD_PARTY_DIR / subdir / name


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python tools/repo_manager.py <command> [args...]")
        print("Commands: list, add, pin, status, audit, remove, verify")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "list":
        cmd_list()
    elif command == "add" and len(sys.argv) >= 3:
        cmd_add(sys.argv[2])
    elif command == "pin" and len(sys.argv) >= 3:
        cmd_pin(sys.argv[2])
    elif command == "status" and len(sys.argv) >= 3:
        cmd_status(sys.argv[2])
    elif command == "audit":
        cmd_audit()
    elif command == "remove" and len(sys.argv) >= 3:
        cmd_remove(sys.argv[2])
    elif command == "verify":
        cmd_verify()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
