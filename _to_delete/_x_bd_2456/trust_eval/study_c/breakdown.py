"""Per-claim-type breakdown of a judge's FA/FR.

The aggregate ladder (ladder.py) pools execution/authorization/state
together, which can hide *where* a judge's errors concentrate -- e.g. the
adaptive attacker only targets authorization/state (the preregistered
target_classes), so if a judge's aggregate FA came entirely from execution
claims, an adaptive run showing 0 evasion on authorization/state is not in
tension with that aggregate number; it's testing a different slice. This
splits the same cached responses back out by claim type so that question has
a direct, checkable answer instead of an assumption.
"""

from __future__ import annotations

import argparse
from typing import List, Optional, Sequence, Tuple

from ..harness.cache import ResponseCache
from ..harness.providers import build_provider
from .llm_review import P1Summary, make_cached_reviewer, run_p1
from .stats import clopper_pearson_ci
from .surrogates import Case, flagship_cases, scaled_cases
from .world import ClaimType, TrustedWorld, build_flagship_world, build_scaled_world


def by_claim_type(cases: Sequence[Case], world: TrustedWorld, provider_specs: Sequence[str],
                  live: bool = False, cache: Optional[ResponseCache] = None
                  ) -> List[Tuple[str, str, P1Summary]]:
    cache = cache if cache is not None else ResponseCache()
    rows: List[Tuple[str, str, P1Summary]] = []
    for spec in provider_specs:
        prov = build_provider(spec)
        review = make_cached_reviewer(prov, cache, live=live)
        for ctype in (ClaimType.EXECUTION, ClaimType.AUTHORIZATION, ClaimType.STATE):
            subset = [c for c in cases if c.claim_type == ctype]
            rows.append((spec, ctype.value, run_p1(subset, review, world, prov.name, prov.model)))
    return rows


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="trust-eval-study-c-breakdown")
    ap.add_argument("--scaled", action="store_true")
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--provider", action="append", default=[], metavar="PROVIDER:MODEL")
    ap.add_argument("--live", action="store_true")
    args = ap.parse_args(argv)
    if not args.provider:
        ap.error("at least one --provider PROVIDER:MODEL is required")

    if args.scaled:
        world, cases = build_scaled_world(args.n), scaled_cases(args.n)
        corpus_desc = f"scaled, n={args.n}"
    else:
        world, cases = build_flagship_world(), flagship_cases()
        corpus_desc = "flagship (n=1)"

    print(f"\nSTUDY C -- P1 FA/FR BY CLAIM TYPE  (corpus: {corpus_desc})\n")
    header = f"{'provider:model':<32}{'claim_type':<16}{'FA':>8}{'FA 95% exact':>16}{'FR':>8}{'FR 95% exact':>16}"
    print(header)
    print("-" * len(header))
    for spec, ctype, s in by_claim_type(cases, world, args.provider, args.live):
        fa_s, fr_s = f"{s.false_accept}/{s.n_attacks}", f"{s.false_reject}/{s.n_truthful}"
        fa_c = clopper_pearson_ci(s.false_accept, s.n_attacks)
        fr_c = clopper_pearson_ci(s.false_reject, s.n_truthful)
        print(f"{spec:<32}{ctype:<16}{fa_s:>8}{f'[{fa_c[0]:.2f},{fa_c[1]:.2f}]':>16}"
              f"{fr_s:>8}{f'[{fr_c[0]:.2f},{fr_c[1]:.2f}]':>16}")
        if s.errors:
            print(f"  [!] {s.errors} cases had no cached response (run with --live)")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())


__all__ = ["by_claim_type", "main"]
