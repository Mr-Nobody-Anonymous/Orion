# ORION Migration Map

This map records the filesystem cleanup that moved preserved upstream checkouts out of the project root and retired the old core container in favor of the canonical `src/orion` package.

| Old Path | New Path | Action | Reason | Status |
| --- | --- | --- | --- | --- |
| `C:\Users\hp\Desktop\Orion\homerun` | `C:\Users\hp\Desktop\Orion\source_repositories\markets\homerun` | Moved | Unique provenance checkout preserved under `source_repositories` | Done |
| `C:\Users\hp\Desktop\Orion\AgenticTrading` | `C:\Users\hp\Desktop\Orion\source_repositories\root_checkouts\AgenticTrading` | Moved | Duplicate root checkout archived without deletion | Done |
| `C:\Users\hp\Desktop\Orion\backtrader` | `C:\Users\hp\Desktop\Orion\source_repositories\root_checkouts\backtrader` | Moved | Duplicate root checkout archived without deletion | Done |
| `C:\Users\hp\Desktop\Orion\FinGPT` | `C:\Users\hp\Desktop\Orion\source_repositories\root_checkouts\FinGPT` | Moved | Duplicate root checkout archived without deletion | Done |
| `C:\Users\hp\Desktop\Orion\FinRL-Trading` | `C:\Users\hp\Desktop\Orion\source_repositories\root_checkouts\FinRL-Trading` | Moved | Duplicate root checkout archived without deletion | Done |
| `C:\Users\hp\Desktop\Orion\freqtrade` | `C:\Users\hp\Desktop\Orion\source_repositories\root_checkouts\freqtrade` | Moved | Duplicate root checkout archived without deletion | Done |
| `C:\Users\hp\Desktop\Orion\hermes-agent` | `C:\Users\hp\Desktop\Orion\source_repositories\root_checkouts\hermes-agent` | Moved | Duplicate root checkout archived without deletion | Done |
| `C:\Users\hp\Desktop\Orion\intelligent-trading-bot` | `C:\Users\hp\Desktop\Orion\source_repositories\root_checkouts\intelligent-trading-bot` | Moved | Duplicate root checkout archived without deletion | Done |
| `C:\Users\hp\Desktop\Orion\jesse` | `C:\Users\hp\Desktop\Orion\source_repositories\root_checkouts\jesse` | Moved | Duplicate root checkout archived without deletion | Done |
| `C:\Users\hp\Desktop\Orion\Lean` | `C:\Users\hp\Desktop\Orion\source_repositories\root_checkouts\Lean` | Moved | Duplicate root checkout archived without deletion | Done |
| `C:\Users\hp\Desktop\Orion\py_vollib` | `C:\Users\hp\Desktop\Orion\source_repositories\root_checkouts\py_vollib` | Moved | Duplicate root checkout archived without deletion | Done |
| `C:\Users\hp\Desktop\Orion\QuantLib` | `C:\Users\hp\Desktop\Orion\source_repositories\root_checkouts\QuantLib` | Moved | Duplicate root checkout archived without deletion | Done |
| `C:\Users\hp\Desktop\Orion\Stock-Trading-Environment` | `C:\Users\hp\Desktop\Orion\source_repositories\root_checkouts\Stock-Trading-Environment` | Moved | Duplicate root checkout archived without deletion | Done |
| `C:\Users\hp\Desktop\Orion\vectorbt` | `C:\Users\hp\Desktop\Orion\source_repositories\root_checkouts\vectorbt` | Moved | Duplicate root checkout archived without deletion | Done |
| `C:\Users\hp\Desktop\Orion\Vibe-Trading` | `C:\Users\hp\Desktop\Orion\source_repositories\root_checkouts\Vibe-Trading` | Moved | Duplicate root checkout archived without deletion | Done |
| Legacy Orion project container | `C:\Users\hp\Desktop\Orion\src\orion`, `tests`, `docs`, `pyproject.toml` | Merged/retired | Previous application container retired; canonical package already lives under `src/orion` | Done |
