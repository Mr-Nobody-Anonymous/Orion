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

    evaluate_parser = subparsers.add_parser("evaluate")
    evaluate_parser.add_argument("--baseline-mae", type=Decimal, default=Decimal("0.01"))

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
    return parser


def main(argv: list[str] | None = None) -> None:
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
        payload = system.evaluate()
        payload["baseline_mae"] = str(args.baseline_mae)
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
    else:
        parser.error(f"unknown command: {command}")
        return

    _, router, hardware = create_local_llm_provider()
    if isinstance(payload, dict):
        payload.setdefault("hardware", {"ram_gb": hardware.ram_gb, "gpu": hardware.gpu_name, "cuda": hardware.cuda_available})
        payload.setdefault("model_tier", router.select().name)
    print(json.dumps(payload, default=str, indent=2))
