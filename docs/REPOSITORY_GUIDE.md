# Orion Repository Management Guide

This document establishes the institutional governance, version pinning, licensing audit, and CLI management standards for external financial repositories in Orion.

---

## 1. Core Principle: Never Track "Latest"

In financial computing and institutional quantitative research, reproducibility is paramount. Allowing an automated script or package manager to pull the "latest" floating commit from upstream repositories introduces non-deterministic model drift, untested code paths, and catastrophic production failures.

Every external repository integrated into Orion must have an explicit record in `registry/repositories.yaml`:

```yaml
qlib:
  owner: microsoft
  repo: qlib
  category: quantitative_research
  upstream_url: https://github.com/microsoft/qlib.git
  pinned_commit: "8cb92b4a11f26e5e8e3d321528641473138b1821"
  version: "0.9.3.99"
  import_date: "2026-09-13"
  license: "MIT"
  copyleft: false
  commercial_allowed: true
  integration_mode: adapter
  local_patches:
    - adapters/qlib/qlib_interface.patch
  status: active
```

---

## 2. License Compatibility & Copyleft Isolation

To safeguard Orion against IP contamination and copyright risk:
- **Permissive Licenses (MIT, Apache-2.0, BSD-3-Clause)**: Allowed as direct adapter integrations (`integration_mode: adapter`).
- **Strong Copyleft Licenses (GPL-3.0, AGPL-3.0)**: **NEVER** imported directly into Orion's core package. They must run in isolated subprocesses (`integration_mode: isolated_process_service`) communicating exclusively over standard JSON or IPC sockets.
- **Commercial Restrictions (Commons Clause, Proprietary)**: Used strictly for reference specifications or sandboxed research.

Run the automated license audit anytime dependencies change:
```bash
python tools/license_audit.py
```
This generates:
- `reports/licenses.json` & `reports/licenses.html`
- `reports/license_inventory.json`
- `reports/repository_inventory.json`
- `reports/capability_inventory.json`

---

## 3. Repository Intelligence Manager CLI

Orion provides a unified CLI to audit, benchmark, test, and pin repositories:

```bash
# List all registered repositories and their pinned commits
python -m orion repo list

# Run the license and copyleft compatibility audit
python -m orion repo audit

# Execute health and contract tests for a specific adapter
python -m orion repo test qlib
python -m orion repo test vectorbt
python -m orion repo test ccxt

# Pin an exact commit hash to the registry
python -m orion repo pin qlib 8cb92b4a11f26e5e8e3d321528641473138b1821
```

---

## 4. Upstream Synchronization Workflow

When updating an external engine:
1. Verify the upstream changelog and security advisories.
2. Checkout the upstream repository in a sandbox.
3. Run the adapter test suite: `python -m orion repo test <name>`.
4. Run the 12-Gate Risk Firewall regression tests.
5. If all tests pass, update `pinned_commit` in `registry/repositories.yaml` using `python -m orion repo pin`.
6. Regenerate reports using `python tools/license_audit.py`.
