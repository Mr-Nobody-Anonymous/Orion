"""Probability theory utilities: expectations, information theory, Bayes."""

from __future__ import annotations

from dataclasses import dataclass
from math import log
from statistics import fmean
from typing import Mapping, Sequence


def expectation(outcomes: Sequence[float], probabilities: Sequence[float] | None = None) -> float:
    if probabilities is None:
        if not outcomes:
            raise ValueError("outcomes must be non-empty")
        return fmean(outcomes)
    if len(outcomes) != len(probabilities):
        raise ValueError("outcomes and probabilities must have equal length")
    total = sum(probabilities)
    if abs(total - 1.0) > 1e-9:
        raise ValueError("probabilities must sum to one")
    if any(p < 0 for p in probabilities):
        raise ValueError("probabilities must be non-negative")
    return sum(o * p for o, p in zip(outcomes, probabilities))


def variance(values: Sequence[float], probabilities: Sequence[float] | None = None) -> float:
    mean = expectation(values, probabilities)
    if probabilities is None:
        return sum((v - mean) ** 2 for v in values) / len(values)
    return sum(p * (v - mean) ** 2 for v, p in zip(values, probabilities))


def covariance(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b) or len(a) < 2:
        raise ValueError("covariance requires equal-length series of length >= 2")
    mean_a, mean_b = fmean(a), fmean(b)
    return sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b)) / len(a)


def pearson_correlation(a: Sequence[float], b: Sequence[float]) -> float:
    cov = covariance(a, b)
    std_a = variance(a) ** 0.5
    std_b = variance(b) ** 0.5
    if std_a == 0 or std_b == 0:
        return 0.0
    return max(-1.0, min(1.0, cov / (std_a * std_b)))


def shannon_entropy(probabilities: Sequence[float]) -> float:
    """Entropy in nats; zero-probability outcomes contribute nothing."""
    if not probabilities:
        raise ValueError("probabilities must be non-empty")
    if any(p < 0 for p in probabilities):
        raise ValueError("probabilities must be non-negative")
    total = sum(probabilities)
    if abs(total - 1.0) > 1e-9:
        raise ValueError("probabilities must sum to one")
    return -sum(p * log(p) for p in probabilities if p > 0)


def kl_divergence(p: Sequence[float], q: Sequence[float]) -> float:
    """Kullback-Leibler divergence D(P || Q) in nats; +inf when Q puts no mass where P does."""
    if len(p) != len(q) or not p:
        raise ValueError("distributions must be non-empty and equal length")
    if any(x < 0 for x in p) or any(x < 0 for x in q):
        raise ValueError("probabilities must be non-negative")
    if abs(sum(p) - 1.0) > 1e-9 or abs(sum(q) - 1.0) > 1e-9:
        raise ValueError("both distributions must sum to one")
    total = 0.0
    for pi, qi in zip(p, q):
        if pi > 0 and qi == 0:
            return float("inf")
        if pi > 0:
            total += pi * log(pi / qi)
    return total


@dataclass(frozen=True, slots=True)
class BayesUpdate:
    prior: float
    likelihood: float
    false_positive_rate: float
    posterior: float

    @property
    def bayes_factor(self) -> float:
        return self.likelihood / self.false_positive_rate if self.false_positive_rate > 0 else float("inf")


def bayes_update(prior: float, likelihood: float, false_positive_rate: float) -> BayesUpdate:
    """P(H|E) from P(H), P(E|H) and P(E|not H)."""
    if not 0 <= prior <= 1 or not 0 <= likelihood <= 1 or not 0 <= false_positive_rate <= 1:
        raise ValueError("probabilities must be within [0, 1]")
    denominator = likelihood * prior + false_positive_rate * (1 - prior)
    if denominator == 0:
        raise ValueError("evidence has zero probability under both hypotheses")
    return BayesUpdate(prior, likelihood, false_positive_rate, likelihood * prior / denominator)


def discrete_bayes(priors: Mapping[str, float], likelihoods: Mapping[str, float]) -> dict[str, float]:
    """Normalize P(h) * P(E|h) over hypotheses; missing likelihoods mean P(E|h) = 0."""
    if not priors:
        raise ValueError("priors must be non-empty")
    if abs(sum(priors.values()) - 1.0) > 1e-9:
        raise ValueError("priors must sum to one")
    unnormalized = {h: prior * likelihoods.get(h, 0.0) for h, prior in priors.items()}
    total = sum(unnormalized.values())
    if total == 0:
        raise ValueError("evidence has zero probability under every hypothesis")
    return {h: value / total for h, value in unnormalized.items()}


def mixture_expectation(component_means: Sequence[float], weights: Sequence[float]) -> float:
    if len(component_means) != len(weights) or not component_means:
        raise ValueError("components and weights must be non-empty and equal length")
    total = sum(weights)
    if total <= 0:
        raise ValueError("weights must sum to a positive value")
    return sum(m * w for m, w in zip(component_means, weights)) / total


__all__ = [
    "BayesUpdate",
    "bayes_update",
    "covariance",
    "discrete_bayes",
    "expectation",
    "kl_divergence",
    "mixture_expectation",
    "pearson_correlation",
    "shannon_entropy",
    "variance",
]
