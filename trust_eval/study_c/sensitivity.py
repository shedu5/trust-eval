"""Sensitivity analysis excluding the pilot-carried (index-0) cases.

`scaled_cases(n)` is built as `flagship_cases()` (the original 10 pilot cases,
reused verbatim so the live-judge cache paid for during the pilot/early runs
stays valid) followed by `n-1` further independent instances. That reuse is a
legitimate cache-cost optimization, but it means those 10 cases are *not*
independent draws from the same generative process as the other 90 -- they
were authored earlier, by hand, before the scaled corpus existed, and every
downstream table (`study-c-principal-result.md`, `study-c-evidence-integrity.md`) has so far
reported statistics over all 100 cases without checking whether those 10
carried cases are quietly driving the result.

This module answers that directly: it recomputes every confirmatory table
(the ladder and the paired McNemar comparisons) over the 90 cases added for
scaling only (`scaled_cases(n)[10:]`), reusing the already-committed judge
cache -- no live API calls needed, since every one of those 90 cases was
already scored by both live judges when the n=100 run was performed.
"""

from __future__ import annotations

import argparse
from typing import List, Optional, Sequence

from ..harness.cache import ResponseCache
from .compare import PairedComparison, run_matrix
from .ladder import build_ladder, format_ladder
from .surrogates import Case, scaled_cases
from .world import TrustedWorld, build_scaled_world

PILOT_CARRIED_COUNT = 10  # len(flagship_cases()) -- verified equal in tests


def exclude_pilot_carried(cases: Sequence[Case]) -> List[Case]:
    """Drop the first PILOT_CARRIED_COUNT cases (`scaled_cases(n)[:10]`),
    which are byte-identical to `flagship_cases()` by construction."""
    return list(cases[PILOT_CARRIED_COUNT:])


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="trust-eval-study-c-sensitivity")
    ap.add_argument("--n", type=int, default=10, help="instances per flagship pattern")
    ap.add_argument("--provider", action="append", default=[], metavar="PROVIDER:MODEL")
    ap.add_argument("--live", action="store_true")
    args = ap.parse_args(argv)

    world = build_scaled_world(args.n)
    all_cases = scaled_cases(args.n)
    sens_cases = exclude_pilot_carried(all_cases)
    n_attacks = sum(1 for c in sens_cases if not c.should_accept)
    n_truthful = sum(1 for c in sens_cases if c.should_accept)

    print(f"\nSTUDY C -- SENSITIVITY ANALYSIS (excluding {PILOT_CARRIED_COUNT} pilot-carried "
          f"index-0 cases; {len(sens_cases)} of {len(all_cases)} cases = "
          f"{n_attacks} attacks + {n_truthful} truthful)\n")

    rows = build_ladder(sens_cases, world, args.provider, args.live)
    print(format_ladder(rows))

    if args.provider:
        cache = ResponseCache()
        print("\n-- Paired exact McNemar (sensitivity corpus) --\n")
        results = run_matrix(sens_cases, world, cache, args.live, args.provider)
        for r in results:
            sig = "yes" if r.p_value < 0.05 else "no"
            print(f"{r.name_a:38s} vs {r.name_b:32s} {r.axis}  "
                  f"b={r.a_wrong_b_right:3d} c={r.a_right_b_wrong:3d}  "
                  f"p={r.p_value:.4f}  sig@0.05={sig}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())


__all__ = ["PILOT_CARRIED_COUNT", "exclude_pilot_carried", "main"]
