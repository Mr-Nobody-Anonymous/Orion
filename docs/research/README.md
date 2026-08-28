# Research subsystem

The research subsystem is the knowledge-discovery front of ORION. It forms
questions, discovers scholarly sources via the public OpenAlex metadata API,
extracts structured profiles, synthesizes consensus and conflicts, generates
hypotheses, runs controlled experiments, replicates, and records provenance.

Modules: `research/` — `agent.py`, `discovery.py`, `extraction.py`,
`synthesis.py`, `experiments.py`, `replication.py`.

| Capability | Status | Entry points |
|---|---|---|
| Paper/source discovery | IMPLEMENTED | `ResearchDiscovery.discover_papers` (OpenAlex) |
| Metadata extraction | IMPLEMENTED | `extract_profile`, `extract_all` |
| Synthesis + conflict detection | IMPLEMENTED | `synthesize`, `generate_hypotheses` |
| Experiments (backtest loop) | IMPLEMENTED | `ExperimentPipeline`, `experiment_from_hypothesis` |
| Replication trials | IMPLEMENTED | `replicate` |
| Autonomous agent | IMPLEMENTED | `ResearchAgent` |
| Full-text retrieval | BLOCKED | Only legal/public metadata/abstracts; no paywall bypass |

## Integrities

- On network failure, discovery returns an explicit **BLOCKED** result rather
  than fabricated sources.
- Every claim retains source provenance (`ProvenanceStore`).
- A backtest is never treated as proof of profitability: `backtesting/robustness`
  (`detect_overfit`, `detect_look_ahead_bias`, `detect_survivorship_bias`) gates
  retention.

See also the [research loop](../architecture/RESEARCH_LOOP.md) and
[provenance](../provenance/PROVENANCE.md).