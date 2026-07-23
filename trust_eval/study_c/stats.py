"""Statistics layer for Study C: Wilson/exact binomial CIs, exact McNemar,
clustered bootstrap by base case.

Stdlib-only (math + random) on purpose — the harness has one runtime dependency
(pydantic) and reproducibility should never depend on a numpy/scipy version. The
exact (Clopper-Pearson) interval is computed from a self-contained regularized
incomplete beta function (continued-fraction form, Numerical Recipes 6.4) plus a
bisection inverse, not from a table or a scipy call.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from random import Random
from typing import Callable, Dict, List, Sequence, Tuple, TypeVar

Z95 = 1.959963984540054  # two-sided 95% normal quantile


# ---------------------------------------------------------------- Wilson CI --

def wilson_ci(successes: int, n: int, z: float = Z95) -> Tuple[float, float]:
    """Wilson score interval for a binomial proportion. Well-behaved (unlike the
    normal-approximation interval) at small n and at p near 0 or 1 — exactly the
    regime a 4-vs-10-case pilot corpus lives in."""
    if n <= 0:
        return (0.0, 1.0)
    phat = successes / n
    denom = 1 + z * z / n
    center = phat + z * z / (2 * n)
    margin = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))
    lo = (center - margin) / denom
    hi = (center + margin) / denom
    return (max(0.0, lo), min(1.0, hi))


# --------------------------------------------------- exact (Clopper-Pearson) --

def _betacf(x: float, a: float, b: float, max_iter: int = 200, eps: float = 1e-12) -> float:
    """Continued-fraction evaluation used by the regularized incomplete beta
    function. Standard Lentz's-method form (Numerical Recipes 6.4.6)."""
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < 1e-30:
        d = 1e-30
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def _betainc(x: float, a: float, b: float) -> float:
    """Regularized incomplete beta function I_x(a, b), x in [0, 1]."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    ln_beta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(ln_beta + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(x, a, b) / a
    return 1.0 - front * _betacf(1.0 - x, b, a) / b


def _betaincinv(y: float, a: float, b: float, tol: float = 1e-10, max_iter: int = 200) -> float:
    """Invert I_x(a, b) = y for x via bisection (monotone in x, so bisection is
    exact-enough and never diverges — no need for Newton's method here)."""
    if y <= 0.0:
        return 0.0
    if y >= 1.0:
        return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        if _betainc(mid, a, b) < y:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return (lo + hi) / 2.0


def clopper_pearson_ci(successes: int, n: int, confidence: float = 0.95) -> Tuple[float, float]:
    """Exact binomial CI: guaranteed >= nominal coverage, unlike Wilson's
    approximate coverage. Wider, especially at small n — report both."""
    if n <= 0:
        return (0.0, 1.0)
    alpha = 1.0 - confidence
    lo = 0.0 if successes == 0 else _betaincinv(alpha / 2, successes, n - successes + 1)
    hi = 1.0 if successes == n else _betaincinv(1 - alpha / 2, successes + 1, n - successes)
    return (lo, hi)


# ------------------------------------------------------------- exact McNemar --

def mcnemar_exact(b: int, c: int) -> float:
    """Exact two-sided McNemar test on the discordant pairs (b, c) of a paired
    2x2 comparison (e.g. protocol X wrong / protocol Y right vs. the reverse).
    This is exactly an exact binomial test of b against Binomial(b+c, 0.5), so it
    needs no incomplete-beta machinery: sum the two-sided tail of the binomial
    pmf at p=0.5, which is exact in floating point via math.comb."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    total = 2.0 ** n
    tail = sum(math.comb(n, i) for i in range(0, k + 1))
    p = (2.0 * tail) / total
    return min(1.0, p)


# ---------------------------------------------------------- clustered bootstrap --

T = TypeVar("T")


def clustered_bootstrap_ci(items: Sequence[T], cluster_key: Callable[[T], str],
                            statistic: Callable[[Sequence[T]], float],
                            n_resamples: int = 2000, confidence: float = 0.95,
                            seed: int = 0) -> Tuple[float, float, float]:
    """Percentile-bootstrap CI for `statistic` (e.g. false-accept rate) that
    resamples whole clusters (e.g. all cases sharing a base scenario / flagship
    instance index), not individual cases — so it doesn't overstate precision
    when cases within a cluster are correlated by construction (same commits,
    same approval ledger, same near-miss pattern).

    Returns (point_estimate, lo, hi).
    """
    by_cluster: Dict[str, List[T]] = {}
    for it in items:
        by_cluster.setdefault(cluster_key(it), []).append(it)
    clusters = list(by_cluster.values())
    point = statistic(items)
    if not clusters:
        return (point, point, point)
    rng = Random(seed)
    draws: List[float] = []
    for _ in range(n_resamples):
        sample: List[T] = []
        for _ in range(len(clusters)):
            sample.extend(clusters[rng.randrange(len(clusters))])
        draws.append(statistic(sample))
    draws.sort()
    alpha = 1.0 - confidence
    lo_idx = max(0, int((alpha / 2) * len(draws)))
    hi_idx = min(len(draws) - 1, int((1 - alpha / 2) * len(draws)) - 1)
    return (point, draws[lo_idx], draws[hi_idx])


def rate_statistic(is_event: Callable[[T], bool]) -> Callable[[Sequence[T]], float]:
    """Build a `statistic` fn for clustered_bootstrap_ci: fraction of items for
    which `is_event` holds (e.g. false_accept)."""
    def stat(sample: Sequence[T]) -> float:
        if not sample:
            return 0.0
        return sum(1 for it in sample if is_event(it)) / len(sample)
    return stat


__all__ = [
    "wilson_ci", "clopper_pearson_ci", "mcnemar_exact",
    "clustered_bootstrap_ci", "rate_statistic",
]
