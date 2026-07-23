"""The combined P0 -> P1 -> P2 -> P3/P4/P5 ladder in one table, with Wilson and
exact-binomial 95% CIs on each protocol's FA/FR rate.

Deterministic protocols (P0, P2, P3, P4, P5) need no model call and run on any
corpus size. P1 (text-only LLM review) is included only when at least one
--provider is given; it reuses the same cached, self-healing judge layer as the
pilot, so a run with --live fills the cache and a later run without --live
reproduces the same numbers with no API key.
"""

from __future__ import annotations

import argparse
from typing import List, Optional, Sequence

from ..harness.cache import ResponseCache
from ..harness.providers import build_provider
from .llm_review import P1Summary, make_cached_reviewer, run_p1
from .protocols import PROTOCOLS, decide
from .stats import clopper_pearson_ci, wilson_ci
from .surrogates import Case, flagship_cases, scaled_cases
from .world import TrustedWorld, build_flagship_world, build_scaled_world


def ladder_row(protocol: str, cases: Sequence[Case], world: TrustedWorld) -> dict:
    attacks = [c for c in cases if not c.should_accept]
    truthful = [c for c in cases if c.should_accept]
    fa = sum(1 for c in attacks if decide(protocol, c, world).false_accept(c))
    fr = sum(1 for c in truthful if decide(protocol, c, world).false_reject(c))
    return dict(
        protocol=protocol,
        n_attacks=len(attacks), fa=fa, fa_wilson=wilson_ci(fa, len(attacks)),
        fa_cp=clopper_pearson_ci(fa, len(attacks)),
        n_truthful=len(truthful), fr=fr, fr_wilson=wilson_ci(fr, len(truthful)),
        fr_cp=clopper_pearson_ci(fr, len(truthful)),
    )


def p1_row(summary: P1Summary) -> dict:
    return dict(
        protocol=f"P1_llm_text_only ({summary.provider}:{summary.model})",
        n_attacks=summary.n_attacks, fa=summary.false_accept,
        fa_wilson=wilson_ci(summary.false_accept, summary.n_attacks),
        fa_cp=clopper_pearson_ci(summary.false_accept, summary.n_attacks),
        n_truthful=summary.n_truthful, fr=summary.false_reject,
        fr_wilson=wilson_ci(summary.false_reject, summary.n_truthful),
        fr_cp=clopper_pearson_ci(summary.false_reject, summary.n_truthful),
    )


def format_ladder(rows: List[dict]) -> str:
    header = (f"{'protocol':<42}{'FA':>7}{'FA 95% Wilson':>17}{'FA 95% exact':>16}"
              f"{'FR':>7}{'FR 95% Wilson':>17}{'FR 95% exact':>16}")
    lines = [header, "-" * len(header)]
    for r in rows:
        fa_s, fr_s = f"{r['fa']}/{r['n_attacks']}", f"{r['fr']}/{r['n_truthful']}"
        fa_w = f"[{r['fa_wilson'][0]:.2f},{r['fa_wilson'][1]:.2f}]"
        fa_c = f"[{r['fa_cp'][0]:.2f},{r['fa_cp'][1]:.2f}]"
        fr_w = f"[{r['fr_wilson'][0]:.2f},{r['fr_wilson'][1]:.2f}]"
        fr_c = f"[{r['fr_cp'][0]:.2f},{r['fr_cp'][1]:.2f}]"
        lines.append(f"{r['protocol']:<42}{fa_s:>7}{fa_w:>17}{fa_c:>16}{fr_s:>7}{fr_w:>17}{fr_c:>16}")
    return "\n".join(lines)


def build_ladder(cases: Sequence[Case], world: TrustedWorld,
                 provider_specs: Sequence[str] = (), live: bool = False) -> List[dict]:
    rows = [ladder_row(PROTOCOLS[0], cases, world)]  # P0_self_report
    if provider_specs:
        cache = ResponseCache()
        for spec in provider_specs:
            prov = build_provider(spec)
            review = make_cached_reviewer(prov, cache, live=live)
            rows.append(p1_row(run_p1(list(cases), review, world, prov.name, prov.model)))
    rows += [ladder_row(p, cases, world) for p in PROTOCOLS[1:]]  # P2, P3, P4, P5
    return rows


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="trust-eval-study-c-ladder")
    ap.add_argument("--scaled", action="store_true",
                    help="use the scaled n-instance corpus instead of the single flagship instance")
    ap.add_argument("--n", type=int, default=8, help="instances per flagship pattern when --scaled")
    ap.add_argument("--provider", action="append", default=[], metavar="PROVIDER:MODEL",
                    help="include P1 (text-only LLM review) for this judge; repeatable")
    ap.add_argument("--live", action="store_true", help="call the provider for cache misses")
    args = ap.parse_args(argv)

    if args.scaled:
        world, cases = build_scaled_world(args.n), scaled_cases(args.n)
        corpus_desc = f"scaled, n={args.n} instances/pattern"
    else:
        world, cases = build_flagship_world(), flagship_cases()
        corpus_desc = "flagship (n=1 instance/pattern)"

    rows = build_ladder(cases, world, args.provider, args.live)
    n_attacks = sum(1 for c in cases if not c.should_accept)
    n_truthful = sum(1 for c in cases if c.should_accept)
    print(f"\nSTUDY C — COMBINED LADDER  (corpus: {corpus_desc}; "
          f"{len(cases)} cases = {n_attacks} attacks + {n_truthful} truthful)\n")
    print(format_ladder(rows))
    print("\nFA = false acceptance of a self-consistent forgery. FR = false rejection of a truthful claim.")
    print("95% CIs are per-protocol, on that protocol's own FA or FR rate over its own denominator.")
    print("Wilson: approximate coverage, tighter. Exact (Clopper-Pearson): guaranteed >= nominal coverage, wider.")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())


__all__ = ["ladder_row", "p1_row", "format_ladder", "build_ladder", "main"]
