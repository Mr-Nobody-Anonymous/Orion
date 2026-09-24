"""Deterministic derivative-free optimization.

These solvers are intentionally simple, seeded (where randomness is used) and
dependency-free. They are used for parameter search inside candidate
evaluation, not as a substitute for proper convex solvers.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from random import Random
from typing import Callable, Sequence


@dataclass(frozen=True, slots=True)
class OptimumResult:
    x: float
    value: float
    evaluations: int


@dataclass(frozen=True, slots=True)
class GridResult:
    best_parameters: dict[str, float]
    best_value: float
    evaluations: int


def golden_section_search(
    objective: Callable[[float], float],
    lower: float,
    upper: float,
    *,
    tolerance: float = 1e-6,
    max_evaluations: int = 200,
) -> OptimumResult:
    """Minimize a unimodal function on [lower, upper]."""
    if upper <= lower:
        raise ValueError("upper bound must exceed lower bound")
    if tolerance <= 0:
        raise ValueError("tolerance must be positive")
    inv_phi = (sqrt(5.0) - 1.0) / 2.0
    a, b = lower, upper
    c = b - inv_phi * (b - a)
    d = a + inv_phi * (b - a)
    fc, fd = objective(c), objective(d)
    evaluations = 2
    while b - a > tolerance and evaluations < max_evaluations:
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - inv_phi * (b - a)
            fc = objective(c)
        else:
            a, c, fc = c, d, fd
            d = a + inv_phi * (b - a)
            fd = objective(d)
        evaluations += 1
    best_x = (a + b) / 2.0
    return OptimumResult(best_x, objective(best_x), evaluations + 1)


def grid_search(
    objective: Callable[[dict[str, float]], float],
    bounds: dict[str, tuple[float, float]],
    *,
    steps: int = 8,
) -> GridResult:
    """Exhaustive search over a rectangular parameter grid (minimization)."""
    if not bounds:
        raise ValueError("bounds must be non-empty")
    if steps < 2:
        raise ValueError("steps must be at least two")
    names = sorted(bounds)
    axes: list[list[float]] = []
    for name in names:
        low, high = bounds[name]
        if high <= low:
            raise ValueError(f"invalid bounds for {name}: {low}..{high}")
        axes.append([low + (high - low) * i / (steps - 1) for i in range(steps)])
    best: dict[str, float] | None = None
    best_value = float("inf")
    evaluations = 0

    def recurse(index: int, current: dict[str, float]) -> None:
        nonlocal best, best_value, evaluations
        if index == len(names):
            value = objective(dict(current))
            evaluations += 1
            if value < best_value:
                best_value = value
                best = dict(current)
            return
        for value in axes[index]:
            current[names[index]] = value
            recurse(index + 1, current)

    recurse(0, {})
    assert best is not None
    return GridResult(best, best_value, evaluations)


def nelder_mead(
    objective: Callable[[Sequence[float]], float],
    start: Sequence[float],
    *,
    step: float = 0.5,
    tolerance: float = 1e-8,
    max_iterations: int = 500,
) -> OptimumResult:
    """Nelder-Mead simplex minimization in n dimensions."""
    if not start:
        raise ValueError("start point must be non-empty")
    n = len(start)
    simplex: list[list[float]] = [[float(v) for v in start]]
    for i in range(n):
        point = [float(v) for v in start]
        point[i] += step if point[i] >= 0 else -step
        simplex.append(point)
    values = [objective(p) for p in simplex]
    evaluations = n + 1
    for _ in range(max_iterations):
        order = sorted(range(n + 1), key=lambda i: values[i])
        simplex = [simplex[i] for i in order]
        values = [values[i] for i in order]
        if abs(values[-1] - values[0]) < tolerance:
            break
        centroid = [sum(simplex[i][j] for i in range(n)) / n for j in range(n)]
        worst = simplex[-1]
        reflected = [centroid[j] + (centroid[j] - worst[j]) for j in range(n)]
        fr = objective(reflected)
        evaluations += 1
        if fr < values[0]:
            expanded = [centroid[j] + 2 * (centroid[j] - worst[j]) for j in range(n)]
            fe = objective(expanded)
            evaluations += 1
            simplex[-1], values[-1] = (expanded, fe) if fe < fr else (reflected, fr)
        elif fr < values[-2]:
            simplex[-1], values[-1] = reflected, fr
        else:
            contracted = [centroid[j] + 0.5 * (worst[j] - centroid[j]) for j in range(n)]
            fc = objective(contracted)
            evaluations += 1
            if fc < values[-1]:
                simplex[-1], values[-1] = contracted, fc
            else:
                for i in range(1, n + 1):
                    simplex[i] = [(simplex[i][j] + simplex[0][j]) / 2.0 for j in range(n)]
                    values[i] = objective(simplex[i])
                    evaluations += 1
    best_index = min(range(n + 1), key=lambda i: values[i])
    return OptimumResult(float(best_index), values[best_index], evaluations)


def coordinate_descent(
    objective: Callable[[dict[str, float]], float],
    start: dict[str, float],
    bounds: dict[str, tuple[float, float]],
    *,
    passes: int = 3,
) -> GridResult:
    """Line-search each coordinate in turn (minimization); deterministic."""
    if not start or set(start) != set(bounds):
        raise ValueError("start and bounds must cover identical parameter sets")
    if passes < 1:
        raise ValueError("passes must be at least one")
    current = dict(start)
    current_value = objective(current)
    evaluations = 1
    for _ in range(passes):
        for name in sorted(current):
            low, high = bounds[name]
            local_best_value = current_value
            local_best = current[name]
            for i in range(21):
                candidate = low + (high - low) * i / 20
                trial = dict(current)
                trial[name] = candidate
                value = objective(trial)
                evaluations += 1
                if value < local_best_value:
                    local_best_value = value
                    local_best = candidate
            current[name] = local_best
            current_value = local_best_value
    return GridResult(current, current_value, evaluations)


def random_restart_search(
    objective: Callable[[Sequence[float]], float],
    bounds: Sequence[tuple[float, float]],
    *,
    restarts: int = 8,
    seed: int = 7,
) -> OptimumResult:
    """Multi-start random search over vectors; deterministic for a fixed seed.

    `OptimumResult.x` carries the mean of the best vector (diagnostic only);
    the vector itself is not returned to keep the result type uniform.
    """
    if not bounds:
        raise ValueError("bounds must be non-empty")
    if restarts < 1:
        raise ValueError("restarts must be at least one")
    rng = Random(seed)
    best_vector: list[float] | None = None
    best_value = float("inf")
    evaluations = 0
    for _ in range(restarts):
        candidate = [rng.uniform(low, high) for low, high in bounds]
        value = objective(candidate)
        evaluations += 1
        if value < best_value:
            best_value = value
            best_vector = candidate
    assert best_vector is not None
    return OptimumResult(sum(best_vector) / len(best_vector), best_value, evaluations)


__all__ = [
    "GridResult",
    "OptimumResult",
    "coordinate_descent",
    "golden_section_search",
    "grid_search",
    "nelder_mead",
    "random_restart_search",
]

