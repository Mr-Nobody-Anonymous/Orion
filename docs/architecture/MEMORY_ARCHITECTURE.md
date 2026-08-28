# Memory Architecture

ORION uses bounded, layered memory over concise observations — it never hoards
raw data. Retrieval is relevance + recency + importance; overflow compresses
into episodic memory instead of unbounded growth.

Modules: `memory/` — `layered.py`, `working.py`, `store.py`, `short_term/`.

## Layers (`MemoryLayer` in `memory/layered.py`)

| Layer | Purpose |
|---|---|
| `WORKING`   | Current-cycle salient state (bounded to `working_limit=32`). |
| `EPISODIC`  | Alternative events / evicted working items (auto-summarized on eviction). |
| `SEMANTIC`  | General knowledge and lessons learned. |
| `PROCEDURAL`| How-to knowledge from correct actions. |
| `MARKET`    | Market observations and regimes. |
| `RESEARCH`  | Research questions, sources, evidence. |
| `TRADING`   | Trading decisions, actions, outcomes. |

## Flow

```
  OBSERVATION
        │
        ▼
┌───────────────────────┐
│ WorkingMemory         │   working.py  (high-salience, bounded)
└───────────┬───────────┘
            │ overflow (pop oldest)
            ▼
┌───────────────────────┐
│ LayeredMemory.remember│   layered.py  → targeted MemoryLayer
│  (summary, tags,  │   importance)
└───────────┬───────────┘
            │ compression / bound
            ▼
┌───────────────────────┐
│ EPISODIC (compressed) │   auto on working eviction
└───────────────────────┘
```

For retrieval, `LayeredMemory.retrieve(query, layers, limit)` scores items by
term matches ×2 + importance, then recency, returning the top-k across the
requested layers.

## Compression / bounds

- Working memory is bounded by `working_limit`; when exceeded, the oldest item
  is **evicted into episodic memory** (a concise record, not a raw dump).
- Items carry `summary`, `tags`, `importance` (validated in `[0,1]`) so
  retrieval stays semantic and cheap.
- This is a memory *policy*, not raw-data hoarding — the directive's Phase 5
  requirement is met by `LayeredMemory` policies.

## Store layer

`memory/store.py::MemoryStore` is the persistent-friendly append store used by
`SelfImprovementEngine`; `WorkingItem`/`WorkingMemory` in `working.py` capture
the active working set.

## Agent memory facade (added Phase 31E)

The persistent agent kernel does not invent a parallel memory
subsystem. It uses `src/orion/agent/memory.py::AgentMemory`, a
typed facade over the existing `MemoryStore`. The facade
exposes four memory kinds, each a tagged `MemoryRecord`
appended through `MemoryStore.append(category, content)`:

| `AgentMemory` kind | `MemoryStore` category | Record type | Semantics |
| --- | --- | --- | --- |
| `KIND_EPISODIC` | `agent.episodic` | `Episode` (action + observation + summary) | Append-only, one per step. |
| `KIND_SEMANTIC` | `agent.semantic` | `SemanticClaim` (claim + confidence + evidence) | Latest-wins per `claim` string; uses `>=` on `created_at` so same-microsecond writes do not drop. |
| `KIND_PROCEDURAL` | `agent.procedural` | `Procedure` (named action template) | Read-mostly; procedures are written when a policy settles on a new template. |
| `KIND_SELF_MODEL` | `agent.self_model` | `CapabilityScore` (capability + success / failure counts) | Latest-wins per capability; updated by `CapabilityExecutor` after every call. |

The facade is *thin*: it does not re-implement storage, it
gives the kernel a typed read / write surface over the
existing store. The kernel's `MemoryStore.append` /
`MemoryStore.find` calls go through the facade so the
agent can be tested in isolation from the rest of ORION's
memory.

## Consumers

`brain/orchestrator.py` calls `LayeredMemory.remember(MemoryLayer.MARKET /
RESEARCH, ...)` during the REMEMBER phase, and later layers retrieve context.
`SelfImprovementEngine` persists experiences through `MemoryStore`.
`AgentMemory` (kernel) records every step's episode and writes
claims into semantic memory when the policy decides to believe
something. The two surfaces are independent and can coexist
(the kernel does not depend on the brain and vice versa).