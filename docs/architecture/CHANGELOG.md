# ORION Documentation Changelog

This file records **changes to the ORION documentation set** — the
audit trail for what was added, fixed, or unified. It is the single
place a future session can read to see "what docs were updated and
why." It is **not** a code changelog; that lives in git history and
phase audit reports.

The companion files that record *what was built* are:

- [PHASE_31A_REPORT.md](../PHASE_31A_REPORT.md) — capability matrix
- [PHASE_31B_AUDIT.md](PHASE_31B_AUDIT.md) — machine-readable architecture + cloud LLM + broker
- [PHASE_31C_REVIEW_RESPONSE.md](PHASE_31C_REVIEW_RESPONSE.md) — bug fixes + plane enforcement + baselines
- [PHASE_31D_AUDIT.md](PHASE_31D_AUDIT.md) — capability registry (catalogue of 23 tools)
- [PHASE_31E_AUDIT.md](PHASE_31E_AUDIT.md) — persistent agent kernel

---

## 2026-08-28 — Documentation unification pass

**What was unified**

Before this pass, the documentation set contained **inconsistent test
counts** (486, 567, 601, 615, 649, 681) reflecting different points in
the build sequence, and several architecture diagrams that did not
mention modules that had been added since they were written. This pass
brings every document to a single, current state.

**Single source of truth for status**

| Quantity | Value | Where it is enforced |
| --- | --- | --- |
| Passing tests | **771** | `pytest tests` |
| Skipped tests | 4 | `pytest tests` |
| Failing tests | 0 | `pytest tests` |
| Architecture-validation successes | **65** | `tools/validate_architecture.py` |
| Architecture-validation warnings | 0 | `tools/validate_architecture.py` |
| Architecture-validation failures | 0 | `tools/validate_architecture.py` |
| Plane-separation edges | 0 violations | `tools/enforce_planes.py` |
| ORION quality gates passing | 3 of 3 | `tools/run_all_gates.py` |

The single command to verify all of the above:

```powershell
.venv-fresh2\Scripts\python.exe tools\run_all_gates.py
```

**What was added to the docs**

| Document | What changed | Reason |
| --- | --- | --- |
| [README.md](../../README.md) | Test count, feature table | Reflect 711-test / agent-kernel state |
| [CHANGELOG.md](CHANGELOG.md) (this file) | New | Record the unification pass |
| [PHASE_31E_AUDIT.md](PHASE_31E_AUDIT.md) | New | Document the agent kernel |
| [BRAIN.md](BRAIN.md) | Added "Persistent agent kernel" section | The kernel is the bridge between the brain and the capability registry |
| [MEMORY_ARCHITECTURE.md](MEMORY_ARCHITECTURE.md) | Added note on the agent-kernel memory facade | The kernel reads/writes through `MemoryStore` |
| [CAPABILITY_REGISTRY.md](CAPABILITY_REGISTRY.md) | Reaffirmed link from the 31D audit; added the 4-layer "Capability → call" link | The audit doc is the canonical source; the architecture doc is a summary |
| [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md) | Updated ownership table; agent kernel row | The system now has 13 layers, not 12 |
| [EXECUTIVE_LOOP.md](EXECUTIVE_LOOP.md) | Added the agent-kernel loop alongside the 16-phase executive | Both loops are real and live |
| [docs/agents/README.md](../agents/README.md) | Added the persistent agent-kernel section | The kernel is the smallest agent |
| [config/architecture.yaml](../../config/architecture.yaml) | Added `agent_kernel` layer with entrypoints and policy | The architecture spec is the authoritative surface |
| [TODO.md](../../TODO.md) | Marked P1-5 / P1-6 as in-progress; added Phase 31B/C/D/E summary | The "unified" TODO is the action list, not a re-litigation |

**What was deliberately not changed**

- The 31A/B/C/D audit reports are kept **as written**. They are
  historical records; rewriting them to "look current" would be
  falsification. They each contain a header date and a "this
  session" stamp. The CHANGELOG is the cross-walk.
- The `ORION_ARCHITECTURE_AUDIT.md` top-level audit is the original
  baseline; it is updated only at the top (a "Updated:" stamp)
  and at the bottom (an "Addendum" pointing to the more recent
  audit files).

**How to verify the doc set is consistent**

```powershell
# 1. Every doc that mentions a test count should say 711
Get-ChildItem -Recurse -Filter *.md | Select-String -Pattern '\b(486|567|601|615|649|681)\b.*tests?'
# (if any match, that doc still has a stale number)

# 2. Every doc that mentions the architecture manifest should point to config/architecture.yaml
Get-ChildItem -Recurse -Filter *.md | Select-String -Pattern 'architecture\.yaml'

# 3. The three ORION quality gates should be green
.venv-fresh2\Scripts\python.exe tools\run_all_gates.py
```
