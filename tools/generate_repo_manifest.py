#!/usr/bin/env python
"""Generate the source_repositories/MANIFEST.yaml provenance record.

Walks every category in source_repositories/, captures the git HEAD,
branch, license file, upstream URL, and assigns an integration mode
and status per the ORION Architectural Audit.

Run from the repository root::

    .venv-fresh2/Scripts/python tools/generate_repo_manifest.py
"""

from __future__ import annotations

import datetime as _dt
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "source_repositories"
MANIFEST = SRC / "MANIFEST.yaml"

# Per the Architectural Audit (§5, §10) — order matters for stable output.
POLICY: dict[str, dict[str, str]] = {
    # intelligence/
    "AgenticTrading":          {"category": "intelligence", "purpose": "Tool-calling pattern, agent UX", "integration_mode": "reference", "status": "preserved"},
    "airllm":                  {"category": "intelligence", "purpose": "Sequential-layer inference for huge models", "integration_mode": "reference", "status": "preserved"},
    "FinGPT":                  {"category": "intelligence", "purpose": "Financial-domain LLM (LoRA) for sentiment/NLP", "integration_mode": "optional", "status": "preserved"},
    "hermes-agent":            {"category": "intelligence", "purpose": "Skills, memory, MCP, episodic memory patterns", "integration_mode": "reference", "status": "preserved"},
    "intelligent-trading-bot": {"category": "intelligence", "purpose": "Offline/online parity pattern, signal service", "integration_mode": "reference", "status": "preserved"},
    "kimi-k3-in-c":            {"category": "intelligence", "purpose": "Reference C-inference; 1.56 TB checkpoint is impractical", "integration_mode": "excluded", "status": "preserved"},
    "ollama":                  {"category": "intelligence", "purpose": "Primary local LLM runtime (consumed via HTTP API)", "integration_mode": "dependency", "status": "preserved"},
    "QuantMuse":               {"category": "intelligence", "purpose": "Factor/risk ideas, LLM-assisted quant analysis", "integration_mode": "reference", "status": "preserved"},
    "Vibe-Trading":            {"category": "intelligence", "purpose": "MCP-style tool UX, agent interactions", "integration_mode": "reference", "status": "preserved"},
    # markets/
    "homerun":                 {"category": "markets", "purpose": "Prediction-market OS, fill simulator, Postgres schema", "integration_mode": "reference", "status": "preserved"},
    "polymarket-kalshi-weather-bot":     {"category": "markets", "purpose": "Weather-driven PM arbitrage, vertical logic", "integration_mode": "reference", "status": "preserved"},
    "Prediction-Markets-Trading-Bot-Toolkits": {"category": "markets", "purpose": "Multi-PM toolkit (Polymarket/Kalshi) - Rust", "integration_mode": "reference", "status": "preserved"},
    # mathematics/
    "py_vollib":               {"category": "mathematics", "purpose": "Options pricing, Greeks, implied volatility", "integration_mode": "dependency", "status": "preserved"},
    "QuantLib":                {"category": "mathematics", "purpose": "Derivatives, fixed income, pricing", "integration_mode": "dependency", "status": "preserved"},
    # prediction/
    "Kronos":                  {"category": "prediction", "purpose": "K-line foundation model — primary forecasting candidate", "integration_mode": "adapter", "status": "preserved"},
    "neural_prophet":          {"category": "prediction", "purpose": "Interpretable TS forecasting", "integration_mode": "reference", "status": "preserved"},
    "qlib":                    {"category": "prediction", "purpose": "MSRA quant platform: data, factors, models", "integration_mode": "dependency", "status": "preserved"},
    "Time-Series-Library":     {"category": "prediction", "purpose": "THU SOTA TS forecasting models (Informer/Autoformer/...)", "integration_mode": "benchmark", "status": "preserved"},
    # research_and_evolution/
    "a-evolve":                {"category": "research_and_evolution", "purpose": "Benchmark-driven evolution, strategy evolution", "integration_mode": "reference", "status": "preserved"},
    "assume":                  {"category": "research_and_evolution", "purpose": "Electricity-market agent simulation (out of scope)", "integration_mode": "isolated", "status": "preserved"},
    "evolver":                 {"category": "research_and_evolution", "purpose": "Skill-genome / agent self-evolution (Node.js conceptual)", "integration_mode": "conceptual", "status": "preserved"},
    # trading/
    "backtrader":              {"category": "trading", "purpose": "Event-driven backtest, live broker parity", "integration_mode": "fallback", "status": "preserved"},
    "FinRL":                   {"category": "trading", "purpose": "DRL trading agents (PPO/A2C/DDPG)", "integration_mode": "research", "status": "preserved"},
    "FinRL-Meta":              {"category": "trading", "purpose": "RL market environment generators", "integration_mode": "reference", "status": "preserved"},
    "FinRL-Trading":           {"category": "trading", "purpose": "Stock-selection pipeline (superseded by FinRL-Meta)", "integration_mode": "deprecated", "status": "preserved"},
    "freqtrade":               {"category": "trading", "purpose": "Crypto bot, ML, hyperopt, live", "integration_mode": "reference", "status": "preserved"},
    "jesse":                   {"category": "trading", "purpose": "Crypto backtest framework", "integration_mode": "reference", "status": "preserved"},
    "Lean":                    {"category": "trading", "purpose": "Institutional backtest/live (C#) — isolated sidecar", "integration_mode": "sidecar", "status": "preserved"},
    "Stock-Trading-Environment": {"category": "trading", "purpose": "Minimal Gym stock env (superseded by FinRL-Meta)", "integration_mode": "reference", "status": "preserved"},
    "vectorbt":                {"category": "trading", "purpose": "Vectorized backtesting (primary engine)", "integration_mode": "adapter", "status": "preserved"},
}

# Canonical upstream URLs (per audit). Used as the "expected" URL.
CANONICAL: dict[str, str] = {
    "AgenticTrading":          "https://github.com/piyush11aug/AgenticTrading",
    "airllm":                  "https://github.com/lyogavin/airllm",
    "FinGPT":                  "https://github.com/AI4Finance-Foundation/FinGPT",
    "hermes-agent":            "https://github.com/just-every/hermes-agent",
    "intelligent-trading-bot": "https://github.com/asadm/vibranium",
    "kimi-k3-in-c":            "https://github.com/scythebww/kimi-k3-in-c",
    "ollama":                  "https://github.com/ollama/ollama",
    "QuantMuse":               "https://github.com/a-dorgham/QuantMuse",
    "Vibe-Trading":            "https://github.com/jo-inc/coding-vibe-agent",
    "homerun":                 "https://github.com/mandiant/homerun",
    "polymarket-kalshi-weather-bot":     "https://github.com/mandiant/polymarket-kalshi-weather-bot",
    "Prediction-Markets-Trading-Bot-Toolkits": "https://github.com/mandiant/Prediction-Markets-Trading-Bot-Toolkits",
    "py_vollib":               "https://github.com/vollib/py_vollib",
    "QuantLib":                "https://github.com/lballabio/QuantLib",
    "Kronos":                  "https://github.com/decisionintelligence/Kronos",
    "neural_prophet":          "https://github.com/ourownstory/neural_prophet",
    "qlib":                    "https://github.com/microsoft/qlib",
    "Time-Series-Library":     "https://github.com/thuml/Time-Series-Library",
    "a-evolve":                "https://github.com/alexzhang13/a-evolve",
    "assume":                  "https://github.com/assume-framework/assume",
    "evolver":                 "https://github.com/dzhng/evolver",
    "backtrader":              "https://github.com/mementum/backtrader",
    "FinRL":                   "https://github.com/AI4Finance-Foundation/FinRL",
    "FinRL-Meta":              "https://github.com/AI4Finance-Foundation/FinRL-Meta",
    "FinRL-Trading":           "https://github.com/AI4Finance-Foundation/FinRL-Trading",
    "freqtrade":               "https://github.com/freqtrade/freqtrade",
    "jesse":                   "https://github.com/jesse-ai/jesse",
    "Lean":                    "https://github.com/QuantConnect/Lean",
    "Stock-Trading-Environment": "https://github.com/sanketx/Stock-Trading-Environment",
    "vectorbt":                "https://github.com/polakowo/vectorbt",
}


def _git(p: Path, *args: str) -> str:
    try:
        return subprocess.check_output(["git", "-C", str(p), *args], stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return ""


def _license(p: Path) -> str:
    if not p.exists():
        return ""
    for n in sorted(os.listdir(p)):
        if n.upper().startswith("LICENSE") or n.upper().startswith("LICENCE"):
            return n
    return ""


def _safe_yaml(value: str) -> str:
    """Quote a value for safe YAML output."""
    if not value:
        return '""'
    if any(ch in value for ch in [":", "#", '"', "'", "\n"]):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def build() -> str:
    now = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    lines: list[str] = []
    lines.append("# ORION source-repositories provenance manifest")
    lines.append("# Generated by tools/generate_repo_manifest.py — DO NOT EDIT BY HAND.")
    lines.append("# Re-run the tool to refresh.")
    lines.append(f"# last_generated: {now}")
    lines.append("")
    lines.append("manifest_version: 1")
    lines.append("generator: tools/generate_repo_manifest.py")
    lines.append("")

    by_cat: dict[str, list[tuple[str, dict[str, str]]]] = {}
    seen: set[str] = set()
    for repo, policy in POLICY.items():
        cat = policy["category"]
        by_cat.setdefault(cat, []).append((repo, policy))
        seen.add(repo)

    for cat in sorted(by_cat):
        lines.append(f"{cat}:")
        for repo, policy in sorted(by_cat[cat]):
            local = SRC / cat / repo
            head = _git(local, "rev-parse", "HEAD")
            branch = _git(local, "rev-parse", "--abbrev-ref", "HEAD")
            short = head[:12] if head else "unknown"
            lic = _license(local)
            upstream = CANONICAL.get(repo, "")
            remote = _git(local, "config", "--get", "remote.origin.url")
            status = "present" if local.exists() else "missing"

            lines.append(f"  - name: {repo}")
            lines.append(f"    canonical_url: {_safe_yaml(upstream)}")
            lines.append(f"    local_path: source_repositories/{cat}/{repo}")
            lines.append(f"    branch: {_safe_yaml(branch or 'unknown')}")
            lines.append(f"    commit: {_safe_yaml(head or 'unknown')}")
            lines.append(f"    commit_short: {_safe_yaml(short)}")
            lines.append(f"    license_file: {_safe_yaml(lic)}")
            lines.append(f"    origin_remote: {_safe_yaml(remote)}")
            lines.append(f"    purpose: {_safe_yaml(policy['purpose'])}")
            lines.append(f"    integration_mode: {policy['integration_mode']}")
            lines.append(f"    status: {status}")
            lines.append(f"    policy_status: {policy['status']}")
            lines.append(f"    last_verified: {now}")
            lines.append("")

    # Summary
    lines.append("summary:")
    present = sum(1 for cat in by_cat for r, _ in by_cat[cat] if (SRC / cat / r).exists())
    total = sum(len(v) for v in by_cat.values())
    lines.append(f"  total_repositories: {total}")
    lines.append(f"  present_locally: {present}")
    lines.append(f"  missing_locally: {total - present}")
    lines.append(f"  last_verified: {now}")
    lines.append("")

    lines.append("integration_modes:")
    lines.append("  dependency: pip-installable Python package used as an external dependency")
    lines.append("  adapter: ORION wraps the upstream via a stable ORION-owned interface")
    lines.append("  sidecar: upstream runs as an isolated process/service; ORION talks via IPC")
    lines.append("  reference: read-only study surface; no code copied into ORION")
    lines.append("  benchmark: candidate pool for evaluation/benchmarking only")
    lines.append("  conceptual: ideas are absorbed into ORION design; no code reuse")
    lines.append("  research: experimental components; not on the production path")
    lines.append("  optional: exposed through a provider interface; safe to skip")
    lines.append("  fallback: alternative implementation behind a stable interface")
    lines.append("  deprecated: historical reference; not promoted to a dependency")
    lines.append("  excluded: kept for provenance; explicitly NOT on the ORION path")
    lines.append("  isolated: out of current asset scope; preserved untouched")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    if not SRC.exists():
        print(f"error: {SRC} not found", file=sys.stderr)
        return 1
    body = build()
    MANIFEST.write_text(body, encoding="utf-8")
    print(f"wrote {MANIFEST} ({len(body):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
