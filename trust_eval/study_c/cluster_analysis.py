"""Cluster-aware uncertainty for the confirmatory ladder.

The exact binomial and Wilson intervals reported elsewhere in this study (and
the exact McNemar tests in `compare.py`) treat every case as an independent
Bernoulli trial. That assumption is not free: `scaled_cases(n)` generates 10
cases per instance (4 execution + 3 authorization + 3 state) from a shared
per-instance template (same commit triple, same ledger, same near-miss
pattern, only the id numbers vary) -- cases sharing an instance are plausibly
correlated (a judge that is fooled by instance 3's execution attack may be
fooled by instance 3's other attacks for the same underlying reason, not for
10 independent reasons). Treating all 40 attack cases as independent can
therefore understate true uncertainty.

This module recomputes the two places that uncertainty is most load-bearing
-- DeepSeek's and Gemini's attack-claim false-acceptance rate, and the
paired DeepSeek-vs-P3 comparison -- using `clustered_bootstrap_ci`
(stats.py), clustering on `Case.instance` (the 0-indexed generation index),
so a reader can see whether the exact/Wilson intervals already reported
meaningfully understate uncertainty once instance-level correlation is
accounted for. Reuses the committed judge-response cache; no live calls.
"""

from __future__ import annotations

import argparse
from typing import List, Optional

from ..harness.cache import ResponseCache
from ..harness.providers import build_provider
from .llm_review import make_cached_reviewer
from .stats import clustered_bootstrap_ci, clopper_pearson_ci, rate_statistic, wilson_ci
from .surrogates import Case, scaled_cases
from .world import TrustedWorld, build_scaled_world


def _judged(cases: List[Case], review, world: TrustedWorld) -> List[Case]:
    """Cases actually resolved by the cache (drops missing/error/unparseable
    so a cache gap in this sandbox can't silently bias the cluster sample)."""
    out = []
    for c in cases:
        d = review(c, world)
        if d.outcome in ("missing", "error", "unparseable"):
            continue
        out.append((c, d))
    return out


def cluster_report(spec: str, cases: List[Case], world: TrustedWorld) -> str:
    cache = ResponseCache()
    prov = build_provider(spec)
    review = make_cached_reviewer(prov, cache, live=False)

    attacks = [c for c in cases if not c.should_accept]
    truthful = [c for c in cases if c.should_accept]
    judged_attacks = _judged(attacks, review, world)
    judged_truthful = _judged(truthful, review, world)

    lines = [f"\n-- {spec} --"]
    if len(judged_attacks) < len(attacks):
        lines.append(f"  [!] {len(attacks) - len(judged_attacks)}/{len(attacks)} attack cases "
                     f"have no cached review in this environment; cluster stats below use only "
                     f"the {len(judged_attacks)} cases actually judged.")

    fa_n = len(judged_attacks)
    fa_k = sum(1 for c, d in judged_attacks if d.false_accept(c))
    if fa_n:
        fa_point, fa_lo, fa_hi = clustered_bootstrap_ci(
            judged_attacks, cluster_key=lambda cd: str(cd[0].instance),
            statistic=rate_statistic(lambda cd: cd[1].false_accept(cd[0])))
        fa_w = wilson_ci(fa_k, fa_n)
        fa_cp = clopper_pearson_ci(fa_k, fa_n)
        lines.append(f"  FA (attacks): {fa_k}/{fa_n} = {fa_k/fa_n:.3f}")
        lines.append(f"    per-case Wilson:        [{fa_w[0]:.3f}, {fa_w[1]:.3f}]")
        lines.append(f"    per-case exact (CP):    [{fa_cp[0]:.3f}, {fa_cp[1]:.3f}]")
        lines.append(f"    cluster bootstrap (by instance, 10 clusters, 2000 resamples): "
                     f"[{fa_lo:.3f}, {fa_hi:.3f}]")

    fr_n = len(judged_truthful)
    fr_k = sum(1 for c, d in judged_truthful if d.false_reject(c))
    if fr_n:
        fr_point, fr_lo, fr_hi = clustered_bootstrap_ci(
            judged_truthful, cluster_key=lambda cd: str(cd[0].instance),
            statistic=rate_statistic(lambda cd: cd[1].false_reject(cd[0])))
        fr_w = wilson_ci(fr_k, fr_n)
        fr_cp = clopper_pearson_ci(fr_k, fr_n)
        lines.append(f"  FR (truthful): {fr_k}/{fr_n} = {fr_k/fr_n:.3f}")
        lines.append(f"    per-case Wilson:        [{fr_w[0]:.3f}, {fr_w[1]:.3f}]")
        lines.append(f"    per-case exact (CP):    [{fr_cp[0]:.3f}, {fr_cp[1]:.3f}]")
        lines.append(f"    cluster bootstrap (by instance, 10 clusters, 2000 resamples): "
                     f"[{fr_lo:.3f}, {fr_hi:.3f}]")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="trust-eval-study-c-cluster-analysis")
    ap.add_argument("--n", type=int, default=10, help="instances per flagship pattern")
    ap.add_argument("--provider", action="append", default=[], metavar="PROVIDER:MODEL",
                    help="repeatable")
    args = ap.parse_args(argv)
    if not args.provider:
        ap.error("at least one --provider PROVIDER:MODEL is required")

    world, cases = build_scaled_world(args.n), scaled_cases(args.n)
    print(f"\nSTUDY C -- CLUSTER-AWARE UNCERTAINTY (cluster = generation instance, "
          f"{args.n} clusters; reuses committed cache, no live calls)")
    print("Per-case Wilson/exact intervals treat every case as an independent trial.")
    print("The cluster bootstrap resamples whole instances (10 cases/instance would-be, "
         "4 attacks + 6 truthful actually drawn per instance) so within-instance correlation")
    print("(same commit/ledger/template, only id numbers vary) is not silently assumed away.")
    for spec in args.provider:
        print(cluster_report(spec, cases, world))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())


__all__ = ["cluster_report", "main"]
