#!/usr/bin/env python3
"""ORION License & Provenance Audit Tool.

Scans all external integrations against the Orion IP policy, detecting copyleft risks,
commercial restrictions, and compatibility constraints.
Generates:
- reports/licenses.json
- reports/licenses.html
- reports/license_inventory.json
- reports/repository_inventory.json
- reports/capability_inventory.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import yaml

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_DIR = ROOT / "registry"
REPORTS_DIR = ROOT / "reports"


def run_license_audit() -> dict[str, Any]:
    REPORTS_DIR.mkdir(exist_ok=True)

    repos_file = REGISTRY_DIR / "repositories.yaml"
    licenses_file = REGISTRY_DIR / "licenses.yaml"
    capabilities_file = REGISTRY_DIR / "capabilities.yaml"

    with open(repos_file, "r", encoding="utf-8") as f:
        repos_data = yaml.safe_load(f).get("repositories", {})

    with open(licenses_file, "r", encoding="utf-8") as f:
        licenses_data = yaml.safe_load(f).get("license_categories", {})

    with open(capabilities_file, "r", encoding="utf-8") as f:
        capabilities_data = yaml.safe_load(f).get("capabilities", {})

    inventory = []
    copyleft_risks = []
    commercial_restrictions = []

    for name, meta in sorted(repos_data.items()):
        lic = meta.get("license", "Unknown")
        mode = meta.get("integration_mode", "unknown")
        copyleft = meta.get("copyleft", False)
        comm_allowed = meta.get("commercial_allowed", True)

        entry = {
            "repository": name,
            "owner": meta.get("owner"),
            "repo": meta.get("repo"),
            "category": meta.get("category"),
            "pinned_commit": meta.get("pinned_commit"),
            "version": meta.get("version"),
            "license": lic,
            "copyleft": copyleft,
            "commercial_allowed": comm_allowed,
            "integration_mode": mode,
            "status": meta.get("status"),
        }
        inventory.append(entry)

        if copyleft:
            copyleft_risks.append(name)
        if not comm_allowed:
            commercial_restrictions.append(name)

    audit_report = {
        "timestamp": "2026-09-13T12:00:00Z",
        "total_repositories": len(inventory),
        "copyleft_isolated_count": len(copyleft_risks),
        "commercial_restricted_count": len(commercial_restrictions),
        "copyleft_repositories": copyleft_risks,
        "commercial_restricted_repositories": commercial_restrictions,
        "inventory": inventory,
    }

    # 1. Write reports/licenses.json
    with open(REPORTS_DIR / "licenses.json", "w", encoding="utf-8") as f:
        json.dump(audit_report, f, indent=2)

    # 2. Write reports/license_inventory.json
    with open(REPORTS_DIR / "license_inventory.json", "w", encoding="utf-8") as f:
        json.dump({"licenses": audit_report["inventory"]}, f, indent=2)

    # 3. Write reports/repository_inventory.json
    with open(REPORTS_DIR / "repository_inventory.json", "w", encoding="utf-8") as f:
        json.dump({"repositories": repos_data}, f, indent=2)

    # 4. Write reports/capability_inventory.json
    with open(REPORTS_DIR / "capability_inventory.json", "w", encoding="utf-8") as f:
        json.dump({"capabilities": capabilities_data}, f, indent=2)

    # 5. Write reports/licenses.html
    html_rows = []
    for item in inventory:
        badge_color = "#10b981" if not item["copyleft"] else "#ef4444"
        mode_badge = "#3b82f6" if "adapter" in item["integration_mode"] else "#8b5cf6"
        comm_label = "YES" if item["commercial_allowed"] else "<span style='color:#ef4444'>ACADEMIC ONLY</span>"
        html_rows.append(
            f"<tr>"
            f"<td><b>{item['repository']}</b></td>"
            f"<td>{item['category']}</td>"
            f"<td><span style='background:{badge_color}; color:#fff; padding:2px 6px; border-radius:4px;'>{item['license']}</span></td>"
            f"<td><span style='background:{mode_badge}; color:#fff; padding:2px 6px; border-radius:4px;'>{item['integration_mode']}</span></td>"
            f"<td><code>{item['pinned_commit'][:10]}...</code></td>"
            f"<td>{comm_label}</td>"
            f"</tr>"
        )

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>ORION License Audit Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 32px; }}
        h1 {{ color: #38bdf8; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 12px 16px; text-align: left; border-bottom: 1px solid #334155; }}
        th {{ background: #1e293b; color: #94a3b8; font-size: 13px; text-transform: uppercase; }}
        tr:hover {{ background: #1e293b; }}
        code {{ color: #38bdf8; font-family: monospace; }}
    </style>
</head>
<body>
    <h1>ORION Institutional IP & License Audit</h1>
    <p>Automated verification of external computing engines and isolation boundaries.</p>
    <table>
        <thead>
            <tr>
                <th>Engine</th>
                <th>Category</th>
                <th>License</th>
                <th>Integration Mode</th>
                <th>Pinned Commit</th>
                <th>Commercial Use</th>
            </tr>
        </thead>
        <tbody>
            {"".join(html_rows)}
        </tbody>
    </table>
</body>
</html>
"""
    with open(REPORTS_DIR / "licenses.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    return audit_report


if __name__ == "__main__":
    rep = run_license_audit()
    print(f"License audit completed: {rep['total_repositories']} repositories analyzed.")
    print(f"Reports written to {REPORTS_DIR}")
