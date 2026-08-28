# Research Loop

ORION's research subsystem turns questions into provenance-tracked evidence and
controlled experiments. Everything downstream of a claim carries its source.

Modules: `research/` — `agent.py`, `discovery.py`, `extraction.py`,
`synthesis.py`, `experiments.py`, `replication.py`.

## Pipeline

```
                    ┌──────────────────┐
                    │ RESEARCH QUESTION│   ResearchAgent/question
                    └────────┬─────────┘
                             ▼
                    ┌──────────────────┐
                    │ PAPER DISCOVERY  │   ResearchDiscovery (public OpenAlex metadata)
                    └────────┬─────────┘
                             ▼
                    ┌──────────────────┐
                    │ SOURCE EXTRACTION│   extract_profile / extract_all
                    └────────┬─────────┘
                             ▼
                    ┌──────────────────┐
                    │ SYNTHESIS        │   synthesize, generate_hypotheses, conflicts
                    └────────┬─────────┘
                             ▼
                    ┌──────────────────┐
                    │ EXPERIMENT       │   ExperimentPipeline (needs prices/backtest)
                    └────────┬─────────┘
                             ▼
                    ┌──────────────────┐
                    │ REPLICATION/TEST │   replicate, unit + backtest
                    └────────┬─────────┘
                             ▼
                    ┌──────────────────┐
                    │ RESEARCH REPORT  │   build_research_report
                    └──────────────────┘
```

## Discovery (`research/discovery.py`)

- `ResearchDiscovery.discover_papers(question, limit)` uses the **public
  OpenAlex metadata API**. On any outage it returns an explicit `BLOCKED`
  response — it never invents evidence.
- `build_research_report` returns `ResearchReport` with `evidence_status`.

## Extraction (`research/extraction.py`)

`PaperProfile` and `ExtractedClaim` model metadata, methods, results, and
limitations. `extract_all` preserves order across claims.

## Synthesis (`research/synthesis.py`)

`SynthesisReport` aggregates consensus and `EvidenceConflict` to surface when
multiple papers disagree; `generate_hypotheses` produces candidate hypotheses
for downstream experiments.

## Experiments (`research/experiments.py`)

- `ExperimentSpec` → `ExperimentPipeline` → `ExperimentReport` with `StageResult`
  per stage (hypothesis → implementation → unit test → backtest → walk-forward).
- `experiment_from_hypothesis` scaffolds a pipeline from a hypothesis.

## Experiments & tests (`research/replication.py`, `research/agent.py`)

- `replicate` runs `ReplicationTrial`s and produces a `ReplicationReport`.
- `ResearchAgent` loops question → discover → synthesize → experiment and
  records provenance.

## Provenance

Every discovery records `ProvenanceStore.record(...)` (source URL, title,
provider). No research claim is retained without provenance.

## Integrity

A promising backtest is never proof of profitability. `backtesting/robustness`
(explicitly checks for overfitting, look-ahead bias, and survivorship bias) is
the gate before any research result can be considered for retention.