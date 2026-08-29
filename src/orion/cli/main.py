from __future__ import annotations

import argparse
import json
from decimal import Decimal

from ..data.contracts import Asset, AssetClass
from ..infrastructure.configuration import OrionConfig
from ..intelligence.llm.providers import create_local_llm_provider
from ..orchestration.system import OrionSystem


def _default_prices() -> list[float]:
    return [100, 101, 100.5, 102, 103, 104, 105]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="orion")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("symbol", nargs="?", default="DEMO")
    run_parser.add_argument("--prices", nargs="+", type=float, default=_default_prices())
    run_parser.add_argument("--actual-return", type=Decimal, default=None)

    analyze_parser = subparsers.add_parser("analyze")
    analyze_parser.add_argument("symbol")
    analyze_parser.add_argument("--prices", nargs="+", type=float, default=_default_prices())
    analyze_parser.add_argument("--actual-return", type=Decimal, default=None)

    backtest_parser = subparsers.add_parser("backtest")
    backtest_parser.add_argument("--prices", nargs="+", type=float, default=_default_prices())

    train_parser = subparsers.add_parser("train")
    train_parser.add_argument("--baseline-error", type=Decimal, default=Decimal("0.02"))

    evaluate_parser = subparsers.add_parser("evaluate", help="Run an out-of-sample evaluation (P0-3 ablation lab).")
    evaluate_parser.add_argument("--symbol", default="SPY", help="Asset symbol (default: SPY).")
    evaluate_parser.add_argument(
        "--prices",
        nargs="+",
        type=float,
        default=None,
        help="Bar series in chronological order.  Use --prices-file for long series.",
    )
    evaluate_parser.add_argument(
        "--prices-file",
        type=str,
        default=None,
        help="Path to a one-value-per-line file of prices.  Overrides --prices.",
    )
    evaluate_parser.add_argument(
        "--baseline",
        action="append",
        choices=["naive", "momentum", "mean_reversion", "ridge", "random"],
        help="Baseline to include (repeatable).  Default: all five.",
    )
    evaluate_parser.add_argument(
        "--ablation",
        nargs=2,
        action="append",
        metavar=("NAME", "PREDICTOR"),
        default=[],
        help="Custom ablation: name + dotted-path to a ``predict(prices) -> float`` "
             "callable (e.g. ``my_pkg.predictors.long_horizon``).  Repeatable.",
    )
    evaluate_parser.add_argument("--train-size", type=int, default=60)
    evaluate_parser.add_argument("--test-size", type=int, default=10)
    evaluate_parser.add_argument("--step", type=int, default=5)
    evaluate_parser.add_argument("--embargo", type=int, default=0)
    evaluate_parser.add_argument("--purge", type=int, default=0)
    evaluate_parser.add_argument(
        "--reference",
        type=str,
        default="naive",
        choices=["naive", "momentum", "mean_reversion", "ridge", "random"],
    )
    evaluate_parser.add_argument(
        "--artifact-root",
        type=str,
        default="artifacts/evaluation",
    )
    evaluate_parser.add_argument(
        "--no-walk-forward",
        action="store_true",
        help="Disable the walk-forward harness (forces train+test on the whole series).",
    )
    evaluate_parser.add_argument(
        "--no-ablation",
        action="store_true",
        help="Disable the ablation matrix (only the focal predictor is reported).",
    )
    evaluate_parser.add_argument(
        "--no-stress",
        action="store_true",
        help="Disable the stress-test variant.",
    )
    evaluate_parser.add_argument(
        "--stress-noise",
        type=float,
        default=0.01,
        help="Std-dev of Gaussian noise added during the stress test (default: 0.01).",
    )

    research_parser = subparsers.add_parser("research")
    research_parser.add_argument("question")
    research_parser.add_argument("--limit", type=int, default=5)

    papers_parser = subparsers.add_parser("discover-papers")
    papers_parser.add_argument("topic")
    papers_parser.add_argument("--limit", type=int, default=5)

    evolve_parser = subparsers.add_parser("evolve")
    evolve_parser.add_argument("--prices", nargs="+", type=float, default=_default_prices())
    evolve_parser.add_argument("--population", type=int, default=8)

    simulate_parser = subparsers.add_parser("simulate")
    simulate_parser.add_argument("--prices", nargs="+", type=float, default=_default_prices())
    simulate_parser.add_argument("--paths", type=int, default=100)
    simulate_parser.add_argument("--horizon", type=int, default=20)
    simulate_parser.add_argument("--seed", type=int, default=7)

    subparsers.add_parser("status")
    subparsers.add_parser("doctor")

    benchmark_parser = subparsers.add_parser("benchmark")
    benchmark_parser.add_argument("--prices", nargs="+", type=float, default=_default_prices())
    benchmark_parser.add_argument("--lookbacks", nargs="+", type=int, default=[3, 5, 8])

    # --- Filings (P1-5) ------------------------------------------------
    filings_parser = subparsers.add_parser("filings", help="Fetch SEC / news / earnings (P1-5).")
    filings_parser.add_argument("symbol")
    filings_parser.add_argument("--as-of", type=str, default=None,
                                 help="Point-in-time cutoff (ISO 8601). Default: now.")
    filings_parser.add_argument("--news-query", type=str, default=None)
    filings_parser.add_argument("--news-limit", type=int, default=10)
    filings_parser.add_argument("--sec-limit", type=int, default=5)
    filings_parser.add_argument("--earnings-limit", type=int, default=4)
    filings_parser.add_argument("--use-reference", action="store_true",
                                 help="Use the deterministic in-memory reference provider.")

    # --- Factors (P1-6) ------------------------------------------------
    factors_parser = subparsers.add_parser("factors", help="Factor intelligence (P1-6).")
    factors_parser.add_argument("--prices", nargs="+", type=float, default=_default_prices())
    factors_parser.add_argument("--factor", action="append", default=[],
                                 help="Specific factor to compute (repeatable). Default: all.")

    # --- Agents (P2-2) -------------------------------------------------
    agents_parser = subparsers.add_parser("agents", help="Run the agent hierarchy (P2-2).")
    agents_parser.add_argument("symbol")
    agents_parser.add_argument("--prices", nargs="+", type=float, default=_default_prices())

    # --- Dashboard (P2-1) ----------------------------------------------
    dashboard_parser = subparsers.add_parser("dashboard", help="Render the human governance card (P2-1).")
    dashboard_parser.add_argument("--candidate-id", default="cand-demo")
    dashboard_parser.add_argument("--decision", default="DEFER", choices=["APPROVE", "REJECT", "DEFER"])
    dashboard_parser.add_argument("--summary", default="Pending operator review")
    dashboard_parser.add_argument("--json", action="store_true",
                                    help="Emit the card as JSON instead of plain text.")

    # --- Compliance (P2-3) ---------------------------------------------
    compliance_parser = subparsers.add_parser("compliance", help="Compliance scaffolding (P2-3).")
    compliance_parser.add_argument("--restricted", nargs="+", default=[],
                                     help="Symbols to add to the restricted list.")
    compliance_parser.add_argument("--check-symbol", default=None,
                                     help="Check whether a symbol is restricted.")
    compliance_parser.add_argument("--audit-action", default=None,
                                     help="Append an audit record with this action.")
    compliance_parser.add_argument("--audit-actor", default="cli")

    # --- Distributed (P2-4) --------------------------------------------
    distributed_parser = subparsers.add_parser("distributed", help="Distributed job control (P2-4).")
    distributed_parser.add_argument("--pool", default="research",
                                      help="Pool name (research, backtest, training, evolution, llm, simulation, data).")
    distributed_parser.add_argument("--job", default=None,
                                      help="Job name to enqueue.")
    distributed_parser.add_argument("--payload", type=str, default="{}",
                                      help="JSON payload for the job.")
    distributed_parser.add_argument("--priority", type=int, default=5)
    distributed_parser.add_argument("--drain", action="store_true",
                                      help="Drain the named pool's queue.")

    # --- Portfolio optimizer (P2-5) ------------------------------------
    optimizer_parser = subparsers.add_parser("optimize", help="Portfolio optimiser (P2-5).")
    optimizer_parser.add_argument("--method", default="mvo",
                                    choices=["mvo", "mvp", "risk-parity", "hrp", "vol-target"],
                                    help="Optimisation method.")
    optimizer_parser.add_argument("--symbols", nargs="+", required=True,
                                    help="Symbols to optimise over.")
    optimizer_parser.add_argument("--returns", nargs="+", type=float, default=[],
                                    help="Per-symbol expected return (order matches --symbols).")
    optimizer_parser.add_argument("--volatilities", nargs="+", type=float, default=[],
                                    help="Per-symbol volatility (order matches --symbols).")
    optimizer_parser.add_argument("--risk-aversion", type=float, default=1.0)
    optimizer_parser.add_argument("--target-volatility", type=float, default=0.10,
                                    help="Target portfolio vol for the vol-target method.")

    # --- Mission control (web dashboard) --------------------------------
    serve_parser = subparsers.add_parser("serve", help="Run the web mission-control dashboard.")
    serve_parser.add_argument("--host", default=None, help="Bind host (default: ORION_WEB_HOST or 127.0.0.1).")
    serve_parser.add_argument("--port", type=int, default=None, help="Bind port (default: ORION_WEB_PORT or 8787).")
    serve_parser.add_argument("--no-browser", action="store_true", help="Do not open a browser tab.")

    # --- TUI mission control (terminal dashboard) -----------------------
    tui_parser = subparsers.add_parser("tui", help="Run the terminal mission-control dashboard (read-first, stdlib-only).")
    tui_parser.add_argument("--once", action="store_true", help="Print a single frame and exit (for logs and CI).")
    tui_parser.add_argument("--width", type=int, default=None, help="Render width in columns (default: terminal width).")
    tui_parser.add_argument("--refresh", type=float, default=2.0, help="Refresh interval in seconds (default: 2.0).")
    tui_parser.add_argument("--interactive", action="store_true",
                              help="Read key presses (q=quit, k=engage kill switch, K=disengage, c=run paper cycle).")

    # --- Hardware + model router (audit §11) ---------------------------
    hardware_parser = subparsers.add_parser("hardware", help="Snapshot local hardware + Ollama availability.")
    hardware_parser.add_argument("--json", action="store_true", help="Emit JSON only (default JSON).")

    model_parser = subparsers.add_parser("model", help="Pick a model tier via LocalModelRouter.")
    model_parser.add_argument("--complexity", default="standard", choices=["cheap", "standard", "deep"])
    model_parser.add_argument("--context-tokens", type=int, default=0)
    model_parser.add_argument("--latency-budget-s", type=float, default=None)

    # --- Experiment + strategy registries (audit §21) -----------------
    experiment_parser = subparsers.add_parser("experiment", help="Start a tracked experiment.")
    experiment_parser.add_argument("name")
    experiment_parser.add_argument("--tag", action="append", default=[], help="Key=value tag (repeatable).")

    strategy_parser = subparsers.add_parser("strategy", help="Register an immutable strategy version.")
    strategy_parser.add_argument("name")
    strategy_parser.add_argument("--rule", action="append", required=True, help="Key=value rule (repeatable).")
    strategy_parser.add_argument("--universe", nargs="*", default=[])
    strategy_parser.add_argument("--lineage", nargs="*", default=[])
    strategy_parser.add_argument("--backtest", default="")

    promote_parser = subparsers.add_parser("promote", help="Advance a strategy along its lifecycle.")
    promote_parser.add_argument("name")
    promote_parser.add_argument("target", choices=["validating", "approved", "production", "rejected", "retired"])

    # --- P4-5 single CLI surface --------------------------------------
    brokers_parser = subparsers.add_parser("brokers", help="List the broker catalogue (P4-2).")
    brokers_parser.add_argument("--ping", action="store_true", help="Probe each venue (read-only).")
    brokers_parser.add_argument("--missing-only", action="store_true", help="Only show venues with missing env keys.")

    lessons_parser = subparsers.add_parser("lessons-analysis", help="Show the unified mistake analysis (P4-3).")
    lessons_parser.add_argument("--symbol", default=None, help="Filter to one symbol.")
    lessons_parser.add_argument("--top", type=int, default=5, help="Top-N symbols.")

    cycle_parser = subparsers.add_parser("cycle", help="One end-to-end decision cycle.")
    cycle_parser.add_argument("symbol", nargs="?", default="DEMO")
    cycle_parser.add_argument("--prices", nargs="+", type=float, default=None)
    cycle_parser.add_argument("--close", type=float, default=None, help="If given, reflect on this exit price.")
    cycle_parser.add_argument("--strategy", default=None, help="Strategy name to register with lineage.")

    return parser


def _load_prices(args) -> list[float]:
    """Resolve the price series from --prices-file or --prices.

    When neither is given, a 200-bar synthetic series is used so
    the default invocation (e.g. ``orion evaluate``) is meaningful
    for the ablation lab.  Tests can override with a custom series.
    """
    if args.prices_file:
        path = __import__("pathlib").Path(args.prices_file)
        if not path.exists():
            raise SystemExit(f"prices file not found: {path}")
        out: list[float] = []
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            out.append(float(line.split(",")[0].strip()))
        if not out:
            raise SystemExit(f"prices file {path} contained no usable values")
        return out
    if args.prices:
        return list(args.prices)
    # 200-bar synthetic default: small drift + sine wave noise.
    import math
    out: list[float] = []
    p = 100.0
    for i in range(200):
        p = p * (1.0 + 0.0003 + 0.01 * math.sin(i * 0.37))
        out.append(p)
    return out


def _resolve_callable(dotted_path: str):
    """Resolve ``module.attr`` to the underlying object."""
    import importlib

    module_name, _, attr = dotted_path.rpartition(".")
    if not module_name:
        raise SystemExit(f"--ablation predictor must be a dotted path: {dotted_path!r}")
    try:
        module = importlib.import_module(module_name)
    except ImportError as error:
        raise SystemExit(f"could not import {module_name!r}: {error}") from error
    try:
        return getattr(module, attr)
    except AttributeError as error:
        raise SystemExit(f"{dotted_path!r} is not defined: {error}") from error


def _run_evaluation_cli(system, args) -> dict[str, object]:
    """CLI implementation of ``orion evaluate``."""
    from ..data.contracts import Asset, AssetClass
    from ..evaluation import (
        AblationVariant,
        EvaluationLab,
        LabConfig,
        make_orion_predictor,
    )
    from ..evaluation.baselines import BASELINE_REGISTRY
    from pathlib import Path

    try:
        return _run_evaluation_cli_impl(system, args)
    except ValueError as error:
        # Convert lab-side validation errors into a clean SystemExit
        # so the CLI behaves the way the rest of argparse expects.
        raise SystemExit(str(error)) from None


def _run_evaluation_cli_impl(system, args) -> dict[str, object]:
    """CLI implementation of ``orion evaluate`` (inner)."""
    from ..data.contracts import Asset, AssetClass
    from ..evaluation import (
        AblationVariant,
        EvaluationLab,
        LabConfig,
        make_orion_predictor,
    )
    from ..evaluation.baselines import BASELINE_REGISTRY
    from pathlib import Path

    prices = _load_prices(args)

    # ---- walk-forward override --------------------------------------
    # When --no-walk-forward is set, the user wants a single in-sample
    # fold (train = all but the last bar, test = last bar) instead of
    # the rolling walk-forward harness.  This is useful for tiny series
    # where train_size + test_size would otherwise exceed the available
    # bars, or for smoke-testing the lab on a short input.
    if args.no_walk_forward:
        if len(prices) < 3:
            raise SystemExit(
                f"--no-walk-forward requires at least 3 prices, got {len(prices)}"
            )
        # Single in-sample fold: train on all but the last two bars,
        # predict the return of the last bar.  The walk-forward harness
        # requires train_size + test_size + embargo + purge < n, so we
        # leave at least one bar of headroom.
        effective_train_size = len(prices) - 2
        effective_test_size = 1
    else:
        effective_train_size = args.train_size
        effective_test_size = args.test_size

    # ---- baselines: subset or all ------------------------------------
    chosen = set(args.baseline) if args.baseline else set(BASELINE_REGISTRY.keys())
    missing = chosen - set(BASELINE_REGISTRY.keys())
    if missing:
        raise SystemExit(f"unknown baseline(s): {sorted(missing)}")
    # The reference baseline must be in the spec list for the
    # paired significance test to produce non-empty p-values.
    # Auto-add it when the user didn't pick it explicitly.
    if args.reference not in chosen:
        chosen.add(args.reference)
    selected_baselines = {name: BASELINE_REGISTRY[name] for name in chosen}

    # ---- ablations ---------------------------------------------------
    ablations: list[AblationVariant] = []
    for name, dotted in args.ablation:
        predictor = _resolve_callable(dotted)
        ablations.append(AblationVariant(name, predictor, f"external predictor at {dotted}"))

    # ---- focal predictor --------------------------------------------
    asset = Asset(args.symbol, AssetClass.EQUITY)
    focal = make_orion_predictor(system, asset)

    # ---- stress test: a noise-injected variant of the focal predictor
    stress_results: dict[str, object] = {}
    if not args.no_stress:
        noise = float(args.stress_noise)
        seed = int(args.symbol.__hash__() & 0xFFFF)

        def _noisy(prices, _noise=noise, _seed=seed):
            import math
            import random as _r
            rng = _r.Random(_seed + len(prices))
            base = focal(prices)
            return base + rng.gauss(0.0, _noise)

        stress_lab = EvaluationLab(
            _noisy,
            prices,
            ablations=[],
            config=LabConfig(
                train_size=effective_train_size,
                test_size=effective_test_size,
                step=args.step,
                embargo=args.embargo,
                purge=args.purge,
                reference=args.reference,
                artifact_root=Path(args.artifact_root) / "stress",
            ),
        )
        stress_artifact, stress_report = stress_lab.run()
        stress_results = {
            "noise_std": noise,
            "artifact_dir": str(stress_artifact.artifact_dir),
            "n_folds": stress_report.n_folds,
            "summaries": {
                name: {
                    "mae": s.mae,
                    "rmse": s.rmse,
                    "directional_accuracy": s.directional_accuracy,
                }
                for name, s in stress_report.summaries.items()
            },
        }

    # ---- main ablation ----------------------------------------------
    if args.no_ablation:
        # The user wants only the focal predictor.  Build a minimal
        # lab config and skip the standard-baseline matrix.
        from ..evaluation.ablation import default_specs as _default_specs

        ablations_for_lab = []
    else:
        ablations_for_lab = ablations

    # Always run the standard baseline matrix when ablation is on.
    from ..evaluation.ablation import AblationSpec as _AblationSpec

    def _all_specs(orion_predictor):
        specs: list[_AblationSpec] = [_AblationSpec("orion", orion_predictor, "Full Orion predictor")]
        for name, fn in selected_baselines.items():
            specs.append(_AblationSpec(name, fn, f"Standard baseline: {name}"))
        for variant in ablations_for_lab:
            specs.append(_AblationSpec(variant.name, variant.predictor, variant.description))
        return specs

    # If ablation is disabled, run only the focal predictor; if
    # enabled, include all baselines + custom ablations.
    if args.no_ablation:
        from ..evaluation.ablation import run_ablation as _run_ablation

        report = _run_ablation(
            prices,
            [_AblationSpec("orion", focal, "Full Orion predictor")],
            reference=args.reference,
            train_size=effective_train_size,
            test_size=effective_test_size,
            step=args.step,
            embargo=args.embargo,
            purge=args.purge,
        )
        artifact_dir = Path(args.artifact_root) / "no-ablation"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / "results.json").write_text(
            __import__("json").dumps(report.as_dict(), indent=2, default=str)
        )
    else:
        # Wrap the chosen baselines as a synthetic lab: we use the
        # existing run_ablation but write the artifact tree by hand.
        from ..evaluation.ablation import run_ablation as _run_ablation
        from ..evaluation.lab import LabConfig as _LabConfig

        report = _run_ablation(
            prices,
            _all_specs(focal),
            reference=args.reference,
            train_size=effective_train_size,
            test_size=effective_test_size,
            step=args.step,
            embargo=args.embargo,
            purge=args.purge,
        )
        lab = EvaluationLab(
            focal,
            prices,
            ablations=ablations,
            config=_LabConfig(
                train_size=effective_train_size,
                test_size=effective_test_size,
                step=args.step,
                embargo=args.embargo,
                purge=args.purge,
                reference=args.reference,
                artifact_root=Path(args.artifact_root) / "ablation",
            ),
        )
        # lab.run() will run the ablation again; instead, just persist
        # the report we already have.  The user paid for one walk-forward
        # sweep; running it twice would inflate run time.
        from ..evaluation.lab import _serialise_significance, _serialise_summary
        import json as _json

        artifact_dir = Path(args.artifact_root) / "ablation"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / "ablation.json").write_text(
            _json.dumps(
                {
                    "reference": report.reference,
                    "n_folds": report.n_folds,
                    "specs": {
                        name: {
                            **_serialise_summary(s),
                            "significance_vs_reference": (
                                _serialise_significance(report.significance_vs_reference[name])
                                if name in report.significance_vs_reference
                                else None
                            ),
                        }
                        for name, s in report.summaries.items()
                    },
                },
                indent=2,
                default=str,
            )
        )
        (artifact_dir / "results.json").write_text(
            _json.dumps(report.as_dict(), indent=2, default=str)
        )

    # ---- summary payload --------------------------------------------
    return {
        "command": "evaluate",
        "symbol": args.symbol,
        "n_prices": len(prices),
        "walk_forward": {
            "train_size": args.train_size,
            "test_size": args.test_size,
            "step": args.step,
            "embargo": args.embargo,
            "purge": args.purge,
        },
        "n_folds": report.n_folds,
        "reference": report.reference,
        "walk_forward_override": (
            {"enabled": True, "train_size": effective_train_size, "test_size": effective_test_size}
            if args.no_walk_forward
            else {"enabled": False, "train_size": args.train_size, "test_size": args.test_size}
        ),
        "specs": {
            name: {
                "mae": s.mae,
                "rmse": s.rmse,
                "bias": s.bias,
                "directional_accuracy": s.directional_accuracy,
            }
            for name, s in report.summaries.items()
        },
        "significance_vs_reference": {
            name: {
                "p_value_t": sig.p_value_t,
                "ci95_low": sig.ci95_low,
                "ci95_high": sig.ci95_high,
            }
            for name, sig in report.significance_vs_reference.items()
        },
        "stress": stress_results,
        "artifact_dir": str(artifact_dir),
    }


def _run_filings_cli(system, args) -> dict[str, object]:
    """``orion filings`` — fetch SEC / news / earnings for a symbol."""
    import json
    from datetime import datetime, timezone

    from ..data.contracts import Asset, AssetClass
    from ..data.providers.filings import (
        EarningsCallProvider,
        FilingsManager,
        NewsProvider,
        ReferenceEarningsProvider,
        ReferenceNewsProvider,
        ReferenceSecEdgarProvider,
        SecEdgarProvider,
    )

    asset = Asset(args.symbol, AssetClass.EQUITY)
    if args.use_reference:
        sec = ReferenceSecEdgarProvider()
        news = ReferenceNewsProvider()
        earnings = ReferenceEarningsProvider()
    else:
        try:
            sec = SecEdgarProvider()
        except Exception as error:
            sec = None
        try:
            news = NewsProvider()
        except Exception:
            news = None
        try:
            earnings = EarningsCallProvider()
        except Exception:
            earnings = None
    manager = FilingsManager(sec=sec, news=news, earnings=earnings)
    as_of: datetime | None = None
    if args.as_of:
        as_of = datetime.fromisoformat(args.as_of)
        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=timezone.utc)
    payload_obj = args.payload if hasattr(args, "payload") else "{}"
    bundle = manager.fetch(
        asset,
        as_of=as_of,
        news_query=args.news_query,
        sec_limit=args.sec_limit,
        news_limit=args.news_limit,
        earnings_limit=args.earnings_limit,
    )
    return {
        "command": "filings",
        "symbol": asset.symbol,
        "as_of": bundle.as_of.isoformat(),
        "bundle": bundle.as_dict(),
        "manager_status": manager.status(),
    }


def _run_factors_cli(args) -> dict[str, object]:
    """``orion factors`` — compute the canonical factor signals."""
    from ..portfolio.factors import (
        FACTOR_NAMES,
        compute_factor_signal,
    )

    if args.factor:
        names = tuple(args.factor)
        unknown = [n for n in names if n not in FACTOR_NAMES]
        if unknown:
            raise SystemExit(f"unknown factors: {unknown}")
    else:
        names = FACTOR_NAMES
    signals = []
    for name in names:
        signal = compute_factor_signal(name, args.prices)
        signals.append(signal.as_dict())
    return {
        "command": "factors",
        "prices_count": len(args.prices),
        "signals": signals,
    }


def _run_agents_cli(system, args) -> dict[str, object]:
    """``orion agents`` — run the agent hierarchy for a symbol."""
    from ..agents import (
        AgentContext,
        AgentController,
        DecisionAgent,
        NewsAgent,
        ResearcherAgent,
    )
    from ..intelligence.financial_reasoning import FinancialReasoner
    from ..intelligence.sentiment import SentimentAnalyzer

    reasoner = FinancialReasoner()
    controller = AgentController(
        agents=[
            DecisionAgent(reasoner=reasoner),
            ResearcherAgent(),
            NewsAgent(analyzer=SentimentAnalyzer()),
        ]
    )
    context = AgentContext(
        symbol=args.symbol,
        asset_class="equity",
        prices=list(args.prices),
    )
    report = controller.run(context)
    return {
        "command": "agents",
        "symbol": args.symbol,
        "report": report.as_dict(),
    }


def _run_serve_cli(args) -> dict[str, object]:
    """``orion serve`` — run the web mission-control dashboard."""
    import os
    import webbrowser

    from ..dashboard.web import serve

    host = args.host or os.environ.get("ORION_WEB_HOST") or "127.0.0.1"
    port = int(args.port or os.environ.get("ORION_WEB_PORT") or 8787)
    if not args.no_browser:
        try:
            webbrowser.open(f"http://{host}:{port}")
        except Exception:  # noqa: BLE001 - headless boxes must not crash the server
            pass
    serve(host=host, port=port)
    return {"command": "serve", "status": "stopped", "host": host, "port": port}


def _run_tui_cli(args) -> dict[str, object]:
    """``orion tui`` — render the terminal mission-control dashboard.

    ``--once`` prints a single frame (handy for ``watch`` loops and
    CI smoke tests). Without ``--once`` the run loop refreshes on a
    timer; ``--interactive`` enables key bindings (q/c/k/K/?/r).

    The TUI is read-first: it never imports a real broker adapter,
    never makes a cloud LLM call, and never writes to disk. The
    kill-switch and paper-cycle actions go through the same
    :class:`DashboardState` the web API uses, so the gating is
    identical to the web dashboard.
    """
    from ..dashboard.tui import RenderOptions, TuiApp, TuiRenderer, print_tui
    from ..dashboard.web import DashboardState
    from ..learning.mistakes import LessonStore

    system = OrionSystem(OrionConfig())
    lesson_store = LessonStore()
    state = DashboardState(system=system, lesson_store=lesson_store)
    width = int(args.width) if args.width else None
    if args.once:
        # Single frame; honour NO_COLOR / FORCE_COLOR. Exit cleanly.
        text = print_tui(state, width=width, force_ansi=None)
        return {
            "command": "tui",
            "mode": "once",
            "rendered_bytes": len(text),
        }
    renderer = TuiRenderer(options=RenderOptions(width=width or 100, ansi=None))
    app = TuiApp(
        state=state,
        renderer=renderer,
        refresh_seconds=float(args.refresh),
        interactive=bool(args.interactive),
    )
    frames = app.run()
    return {
        "command": "tui",
        "mode": "loop",
        "frames_rendered": frames,
        "interactive": bool(args.interactive),
    }


def _run_dashboard_cli(args) -> dict[str, object]:
    """``orion dashboard`` — render the human governance card."""
    from ..dashboard import build_approval_card, card_to_json, text_dashboard

    card = build_approval_card(
        candidate_id=args.candidate_id,
        decision=args.decision,
        summary=args.summary,
    )
    if args.json:
        return {"command": "dashboard", "card": json.loads(card_to_json(card))}
    text_dashboard(card)
    return {
        "command": "dashboard",
        "candidate_id": card.candidate_id,
        "decision": card.decision,
        "rendered": card.render(),
    }


def _run_compliance_cli(args) -> dict[str, object]:
    """``orion compliance`` — exercise compliance scaffolding."""
    from ..compliance import AuditLog, RestrictedList

    restricted = RestrictedList(args.restricted)
    check_result: dict[str, object] = {}
    if args.check_symbol is not None:
        check_result = {
            "symbol": args.check_symbol,
            "restricted": restricted.is_restricted(args.check_symbol),
        }
    audit_result: dict[str, object] = {}
    if args.audit_action is not None:
        log = AuditLog()
        record = log.append(args.audit_actor, args.audit_action)
        ok, message = log.verify()
        audit_result = {
            "appended": record.as_dict(),
            "verify_ok": ok,
            "verify_message": message,
            "total_records": len(log.records()),
        }
    return {
        "command": "compliance",
        "restricted_symbols": sorted(restricted.symbols()),
        "check": check_result,
        "audit": audit_result,
    }


def _run_distributed_cli(args) -> dict[str, object]:
    """``orion distributed`` — exercise the in-process queue."""
    import json as _json
    from ..distributed import OrionController

    controller = OrionController()
    pool = getattr(controller, args.pool, None)
    if pool is None or not pool.workers():
        raise SystemExit(f"unknown pool: {args.pool!r}")
    queue = pool.workers()[0].queue
    enqueued: dict[str, object] = {}
    if args.job:
        try:
            payload = _json.loads(args.payload)
        except _json.JSONDecodeError as error:
            raise SystemExit(f"--payload must be valid JSON: {error}") from error
        if not queue.get("__handler__") and not any(True for _ in queue._handlers):
            # Register a no-op demo handler if no handlers exist yet.
            queue.register("demo", lambda record: {"echo": record.payload})
        try:
            record = queue.enqueue(args.job, payload, priority=args.priority)
            enqueued = record.as_dict()
        except KeyError as error:
            raise SystemExit(str(error)) from error
    drained = 0
    if args.drain:
        drained = queue.drain()
    return {
        "command": "distributed",
        "pool": args.pool,
        "enqueued": enqueued,
        "drained": drained,
        "pending": len(queue.pending()),
        "dead_letter": len(queue.dead_letter()),
    }


def _run_hardware_cli(system, args) -> dict[str, object]:
    return system.snapshot_hardware()


def _run_model_cli(system, args) -> dict[str, object]:
    return system.select_local_model(
        args.complexity,
        context_tokens=int(args.context_tokens),
        latency_budget_s=args.latency_budget_s,
    )


def _run_experiment_cli(system, args) -> dict[str, object]:
    tags: dict[str, str] = {}
    for raw in args.tag:
        if "=" in raw:
            k, _, v = raw.partition("=")
            tags[k.strip()] = v.strip()
    return system.start_experiment(args.name, tags=tags)


def _run_strategy_cli(system, args) -> dict[str, object]:
    rules: dict[str, str] = {}
    for raw in args.rule:
        if "=" in raw:
            k, _, v = raw.partition("=")
            rules[k.strip()] = v.strip()
    if not rules:
        raise SystemExit("at least one --rule key=value is required")
    return system.register_strategy(
        args.name,
        rules=rules,
        universe=tuple(args.universe),
        lineage=tuple(args.lineage),
        backtest_ref=args.backtest,
    )


def _run_promote_cli(system, args) -> dict[str, object]:
    return system.promote_strategy(args.name, args.target)


def _run_brokers_cli(args) -> dict[str, object]:
    """``orion brokers`` — show the catalogue (P4-2) and optionally ping."""
    from ..integrations.brokers import (
        BROKERS,
        catalogue_as_dict,
        missing_keys_all,
        ping_all,
    )

    missing = missing_keys_all()
    payload: dict[str, object] = {
        "catalogue": catalogue_as_dict(),
        "missing_keys": missing,
    }
    if args.missing_only:
        payload["catalogue"]["venues"] = [
            v for v in payload["catalogue"]["venues"] if missing.get(v["venue"])
        ]
    if args.ping:
        payload["health"] = [h.as_dict() for h in ping_all(timeout=0.5)]
    return payload


def _run_lessons_analysis_cli(system, args) -> dict[str, object]:
    """``orion lessons-analysis`` — show the unified analysis (P4-3)."""
    analysis = system.lesson_analysis()
    if args.symbol:
        per = analysis["all_time"]["by_symbol"]
        filtered = {symbol: per.get(symbol, 0) for symbol in [args.symbol] if symbol in per}
        analysis["all_time"]["by_symbol"] = filtered
    else:
        top = dict(sorted(analysis["all_time"]["by_symbol"].items(), key=lambda kv: kv[1], reverse=True)[: args.top])
        analysis["all_time"]["by_symbol"] = top
    return {"status": "IMPLEMENTED", **analysis}


def _run_cycle_cli(system, args) -> dict[str, object]:
    """``orion cycle`` — one end-to-end decision cycle (P4-5)."""
    prices = args.prices or [100, 101, 100.5, 102, 103, 104, 105]
    result = system.evaluate(
        args.symbol,
        prices,
        close_price=args.close,
        strategy_name=args.strategy,
        experiment_name=f"cycle:{args.symbol}",
    )
    return {"status": "IMPLEMENTED", "cycle": result}


def _run_optimizer_cli(args) -> dict[str, object]:
    """``orion optimize`` — exercise the portfolio optimiser."""
    from ..portfolio.optimizer import (
        drawdown_aware_weights,
        hierarchical_risk_parity,
        mean_variance,
        mvp_weights,
        risk_parity,
        volatility_targeting,
    )

    symbols = tuple(args.symbols)
    if not symbols:
        raise SystemExit("--symbols must be non-empty")
    expected_returns = (
        dict(zip(symbols, args.returns)) if args.returns else {s: 0.05 for s in symbols}
    )
    vols = (
        dict(zip(symbols, args.volatilities)) if args.volatilities else {s: 0.20 for s in symbols}
    )
    method = args.method
    if method == "mvo":
        result = mean_variance(expected_returns, volatilities=vols, risk_aversion=args.risk_aversion)
    elif method == "mvp":
        result = mvp_weights(symbols, volatilities=vols)
    elif method == "risk-parity":
        result = risk_parity(symbols, volatilities=vols)
    elif method == "hrp":
        # Build a diagonal covariance from volatilities.
        n = len(symbols)
        cov = [[0.0] * n for _ in range(n)]
        for i in range(n):
            cov[i][i] = float(vols[symbols[i]]) ** 2
        result = hierarchical_risk_parity(symbols, covariance=cov)
    elif method == "vol-target":
        base = {s: 1.0 / len(symbols) for s in symbols}
        result = volatility_targeting(
            base, target_volatility=args.target_volatility, volatilities=vols
        )
    else:
        raise SystemExit(f"unknown method: {method!r}")
    return {
        "command": "optimize",
        "method": method,
        "result": result.as_dict(),
    }


def main(argv: list[str] | None = None) -> None:
    from ..infrastructure.env import load_env

    load_env()  # populate os.environ from a repository-root .env (no override)
    parser = build_parser()
    args = parser.parse_args(argv)
    config = OrionConfig()
    config.validate()
    system = OrionSystem(config)
    command = args.command or "status"

    if command == "status":
        payload = system.status()
    elif command == "run":
        payload = system.run(Asset(args.symbol, AssetClass.EQUITY), args.prices, args.actual_return)
    elif command == "analyze":
        payload = system.analyze(args.symbol, args.prices, args.actual_return)
    elif command == "backtest":
        payload = system.backtest(args.prices)
    elif command == "train":
        payload = system.train(baseline_error=args.baseline_error)
    elif command == "evaluate":
        payload = _run_evaluation_cli(system, args)
    elif command == "research":
        payload = system.research(args.question, limit=args.limit)
    elif command == "discover-papers":
        payload = system.research(args.topic, limit=args.limit)
    elif command == "evolve":
        payload = system.evolve(args.prices, population_size=args.population)
    elif command == "simulate":
        payload = system.simulate(args.prices, paths=args.paths, horizon=args.horizon, seed=args.seed)
    elif command == "doctor":
        payload = system.doctor()
    elif command == "benchmark":
        payload = system.benchmark(args.prices, lookbacks=tuple(args.lookbacks))
    elif command == "filings":
        payload = _run_filings_cli(system, args)
    elif command == "factors":
        payload = _run_factors_cli(args)
    elif command == "agents":
        payload = _run_agents_cli(system, args)
    elif command == "dashboard":
        payload = _run_dashboard_cli(args)
    elif command == "compliance":
        payload = _run_compliance_cli(args)
    elif command == "distributed":
        payload = _run_distributed_cli(args)
    elif command == "optimize":
        payload = _run_optimizer_cli(args)
    elif command == "serve":
        payload = _run_serve_cli(args)
    elif command == "tui":
        payload = _run_tui_cli(args)
    elif command == "hardware":
        payload = _run_hardware_cli(system, args)
    elif command == "model":
        payload = _run_model_cli(system, args)
    elif command == "experiment":
        payload = _run_experiment_cli(system, args)
    elif command == "strategy":
        payload = _run_strategy_cli(system, args)
    elif command == "promote":
        payload = _run_promote_cli(system, args)
    elif command == "brokers":
        payload = _run_brokers_cli(args)
    elif command == "lessons-analysis":
        payload = _run_lessons_analysis_cli(system, args)
    elif command == "cycle":
        payload = _run_cycle_cli(system, args)
    else:
        parser.error(f"unknown command: {command}")
        return

    _, router, hardware = create_local_llm_provider()
    if isinstance(payload, dict):
        payload.setdefault("hardware", {"ram_gb": hardware.ram_gb, "gpu": hardware.gpu_name, "cuda": hardware.cuda_available})
        payload.setdefault("model_tier", router.select().name)
    print(json.dumps(payload, default=str, indent=2))
