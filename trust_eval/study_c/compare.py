"""Paired exact McNemar comparisons between two protocols on the same corpus.

Every protocol decides the exact same cases, so a proper comparison is paired,
not two independent Wilson/Clopper-Pearson intervals eyeballed for overlap.
McNemar's test looks only at the cases where the two protocols disagree (one
wrong, one right) and asks whether that disagreement is lopsided enough to be
more than noise. `mcnemar_exact` (stats.py) computes the exact two-sided
binomial p-value on the discordant pairs -- no chi-square approximation, valid
even when the discordant count is small.

This reuses the P1 judge cache read-only by default (`--live` off): if a
`ladder.py --live` run already paid for the judge calls, `compare.py`
reproduces every p-value from the committed cache with no API key.
"""

from __future__ import annotations

import argparse
from typing import Callable, List, Optional, Sequence, Tuple

from pydantic import BaseModel

from ..harness.cache import ResponseCache
from ..harness.providers import build_provider
from .llm_review import make_cached_reviewer
from .protocols import PROTOCOLS, Decision, decide
from .stats import mcnemar_exact
from .surrogates import Case, flagship_cases, scaled_cases
from .world import TrustedWorld, build_flagship_world, build_scaled_world

Decider = Callable[[Case, TrustedWorld], Decision]


def decider_for(spec: str, cache: ResponseCache, live: bool) -> Decider:
    """`spec` is either a deterministic protocol name (e.g.
    'P3_claim_appropriate_anchor') or 'provider:model' for a P1 judge
    (cached-or-live per `live`)."""
    if spec in PROTOCOLS:
        return lambda c, w: decide(spec, c, w)
    prov = build_provider(spec)
    return make_cached_reviewer(prov, cache, live=live)


class PairedComparison(BaseModel):
    name_a: str
    name_b: str
    axis: str          # "FA" | "FR"
    n: int
    a_wrong_b_right: int   # McNemar b
    a_right_b_wrong: int   # McNemar c
    both_wrong: int
    both_right: int
    p_value: float


def paired_errors(name_a: str, decide_a: Decider, name_b: str, decide_b: Decider,
                  cases: Sequence[Case], world: TrustedWorld, axis: str) -> PairedComparison:
    if axis not in ("FA", "FR"):
        raise ValueError(f"axis must be 'FA' or 'FR', got {axis!r}")
    pool = [c for c in cases if (not c.should_accept if axis == "FA" else c.should_accept)]
    is_error = (lambda d, cl: d.false_accept(cl)) if axis == "FA" else (lambda d, cl: d.false_reject(cl))
    b = c_ = both_wrong = both_right = 0
    for cl in pool:
        ea = is_error(decide_a(cl, world), cl)
        eb = is_error(decide_b(cl, world), cl)
        if ea and not eb:
            b += 1
        elif eb and not ea:
            c_ += 1
        elif ea and eb:
            both_wrong += 1
        else:
            both_right += 1
    return PairedComparison(name_a=name_a, name_b=name_b, axis=axis, n=len(pool),
                            a_wrong_b_right=b, a_right_b_wrong=c_,
                            both_wrong=both_wrong, both_right=both_right,
                            p_value=mcnemar_exact(b, c_))


def format_comparison(r: PairedComparison) -> str:
    sig = "significant at alpha=0.05" if r.p_value < 0.05 else "not significant at alpha=0.05"
    return (f"{r.axis} comparison: {r.name_a}  vs  {r.name_b}  (n={r.n} cases)\n"
            f"  {r.name_a} wrong / {r.name_b} right: {r.a_wrong_b_right}\n"
            f"  {r.name_a} right / {r.name_b} wrong: {r.a_right_b_wrong}\n"
            f"  both wrong: {r.both_wrong}   both right: {r.both_right}\n"
            f"  exact McNemar two-sided p = {r.p_value:.4f}  ({sig})")


def run_matrix(cases: Sequence[Case], world: TrustedWorld, cache: ResponseCache, live: bool,
               provider_specs: Sequence[str], baseline: str = "P3_claim_appropriate_anchor"
               ) -> List[PairedComparison]:
    """The canonical comparison set for the write-up: each deterministic
    non-anchored protocol vs. the anchored baseline, each live judge vs. the
    anchored baseline, and every judge vs. every other judge -- each on both
    the FA and FR axis."""
    pairs: List[Tuple[str, str]] = [("P0_self_report", baseline), ("P2_deterministic_internal", baseline)]
    pairs += [(spec, baseline) for spec in provider_specs]
    for i in range(len(provider_specs)):
        for j in range(i + 1, len(provider_specs)):
            pairs.append((provider_specs[i], provider_specs[j]))

    results: List[PairedComparison] = []
    for name_a, name_b in pairs:
        decide_a = decider_for(name_a, cache, live)
        decide_b = decider_for(name_b, cache, live)
        for axis in ("FA", "FR"):
            results.append(paired_errors(name_a, decide_a, name_b, decide_b, cases, world, axis))
    return results


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="trust-eval-study-c-compare")
    ap.add_argument("--scaled", action="store_true")
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--provider", action="append", default=[], metavar="PROVIDER:MODEL")
    ap.add_argument("--a", help="protocol name or provider:model (single-pair mode)")
    ap.add_argument("--b", help="protocol name or provider:model (single-pair mode)")
    ap.add_argument("--axis", choices=["FA", "FR", "both"], default="both")
    ap.add_argument("--matrix", action="store_true",
                    help="run the canonical comparison matrix instead of a single --a/--b pair")
    args = ap.parse_args(argv)

    if args.scaled:
        world, cases = build_scaled_world(args.n), scaled_cases(args.n)
        corpus_desc = f"scaled, n={args.n} instances/pattern"
    else:
        world, cases = build_flagship_world(), flagship_cases()
        corpus_desc = "flagship (n=1 instance/pattern)"
    cache = ResponseCache()

    print(f"\nSTUDY C -- PAIRED McNEMAR COMPARISONS  (corpus: {corpus_desc})")

    if args.matrix:
        for r in run_matrix(cases, world, cache, args.live, args.provider):
            print()
            print(format_comparison(r))
        return 0

    if not args.a or not args.b:
        ap.error("either --matrix, or both --a and --b, are required")
    decide_a = decider_for(args.a, cache, args.live)
    decide_b = decider_for(args.b, cache, args.live)
    for axis in (["FA", "FR"] if args.axis == "both" else [args.axis]):
        print()
        print(format_comparison(paired_errors(args.a, decide_a, args.b, decide_b, cases, world, axis)))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())


__all__ = ["Decider", "decider_for", "PairedComparison", "paired_errors",
          "format_comparison", "run_matrix", "main"]
