"""The combined P0 -> P1 -> P2 -> P3/P4/P5 ladder in one table, with Wilson and
exact-binomial 95% CIs on each protocol's FA/FR rate, plus abstention/coverage
so a protocol cannot report a misleadingly low FA/FR purely by abstaining on
the hard cases (see `_selective`).

P0, P2, P3, P4, and P5-as-pure-abstention (the `ladder_row` calls in
`build_ladder`, with no `--p5-adjudicator`) are deterministic and need no
model call. P1 (text-only LLM review, `--provider`) and P5-hybrid
(`--p5-adjudicator`, via `p5_hybrid_row`) are NOT deterministic -- they call
a live judge model, and are two DIFFERENT protocols from plain P5 despite the
shared "P5" root name: plain P5 never consults an adjudicator and is always
identical to P4; P5-hybrid[JUDGE] does, and its result depends on which judge
is in the adjudicator seat. Never refer to "P5" unqualified when the
adjudicated variant is meant -- always "P5-hybrid[provider:model]". Both P1
and P5-hybrid reuse the same cached, self-healing judge layer, so a run with
`--live` fills the cache and a later run without `--live` reproduces the same
numbers with no API key.
"""

from __future__ import annotations

import argparse
from typing import List, Optional, Sequence

from ..harness.cache import ResponseCache
from ..harness.providers import build_provider
from .anchors import AGREES, ANCHORS, CLAIM_ANCHOR, CONTRADICTS
from .llm_review import P1Summary, make_cached_reviewer, run_p1
from .protocols import CANNOT_VERIFY, PROTOCOLS, decide
from .stats import clopper_pearson_ci, wilson_ci
from .surrogates import Case, flagship_cases, scaled_cases
from .world import TrustedWorld, build_flagship_world, build_scaled_world


def _anchor_inconclusive(claim: Case, world: TrustedWorld) -> bool:
    name = CLAIM_ANCHOR.get(claim.claim_type)
    if not name:
        return True
    res = ANCHORS[name](claim, world)
    return (not res.applicable) or (res.verdict not in (AGREES, CONTRADICTS))


def _selective(numerator: int, denominator: int):
    """(rate, wilson_ci, exact_ci) among DECIDED cases only, or (None, None,
    None) if the protocol abstained on every case in this pool -- a
    selective-risk rate with a zero denominator is undefined, not zero."""
    if denominator == 0:
        return None, None, None
    return (numerator / denominator, wilson_ci(numerator, denominator),
            clopper_pearson_ci(numerator, denominator))


def ladder_row(protocol: str, cases: Sequence[Case], world: TrustedWorld) -> dict:
    attacks = [c for c in cases if not c.should_accept]
    truthful = [c for c in cases if c.should_accept]
    decisions_a = [decide(protocol, c, world) for c in attacks]
    decisions_t = [decide(protocol, c, world) for c in truthful]
    fa = sum(1 for c, d in zip(attacks, decisions_a) if d.false_accept(c))
    fr = sum(1 for c, d in zip(truthful, decisions_t) if d.false_reject(c))
    abstain_a = sum(1 for d in decisions_a if d.outcome == CANNOT_VERIFY)
    abstain_t = sum(1 for d in decisions_t if d.outcome == CANNOT_VERIFY)
    decided_a, decided_t = len(attacks) - abstain_a, len(truthful) - abstain_t
    sel_fa, sel_fa_w, sel_fa_c = _selective(fa, decided_a)
    sel_fr, sel_fr_w, sel_fr_c = _selective(fr, decided_t)
    return dict(
        protocol=protocol,
        n_attacks=len(attacks), fa=fa, fa_wilson=wilson_ci(fa, len(attacks)),
        fa_cp=clopper_pearson_ci(fa, len(attacks)),
        n_truthful=len(truthful), fr=fr, fr_wilson=wilson_ci(fr, len(truthful)),
        fr_cp=clopper_pearson_ci(fr, len(truthful)),
        abstain_attacks=abstain_a, abstain_truthful=abstain_t,
        coverage_attacks=decided_a / len(attacks) if attacks else None,
        coverage_truthful=decided_t / len(truthful) if truthful else None,
        selective_fa=sel_fa, selective_fa_wilson=sel_fa_w, selective_fa_cp=sel_fa_c,
        selective_fr=sel_fr, selective_fr_wilson=sel_fr_w, selective_fr_cp=sel_fr_c,
    )


def p1_row(summary: P1Summary) -> dict:
    # P1's prompt forces a binary accept/reject verdict -- structurally no
    # abstention path exists (unlike P4/P5). A cache-miss/parse failure is
    # tracked separately as `errors`, not as abstention.
    return dict(
        protocol=f"P1_llm_text_only ({summary.provider}:{summary.model})",
        n_attacks=summary.n_attacks, fa=summary.false_accept,
        fa_wilson=wilson_ci(summary.false_accept, summary.n_attacks),
        fa_cp=clopper_pearson_ci(summary.false_accept, summary.n_attacks),
        n_truthful=summary.n_truthful, fr=summary.false_reject,
        fr_wilson=wilson_ci(summary.false_reject, summary.n_truthful),
        fr_cp=clopper_pearson_ci(summary.false_reject, summary.n_truthful),
        errors=summary.errors,
        abstain_attacks=0, abstain_truthful=0,
        coverage_attacks=1.0, coverage_truthful=1.0,
        selective_fa=summary.false_accept / summary.n_attacks if summary.n_attacks else None,
        selective_fa_wilson=wilson_ci(summary.false_accept, summary.n_attacks) if summary.n_attacks else None,
        selective_fa_cp=clopper_pearson_ci(summary.false_accept, summary.n_attacks) if summary.n_attacks else None,
        selective_fr=summary.false_reject / summary.n_truthful if summary.n_truthful else None,
        selective_fr_wilson=wilson_ci(summary.false_reject, summary.n_truthful) if summary.n_truthful else None,
        selective_fr_cp=clopper_pearson_ci(summary.false_reject, summary.n_truthful) if summary.n_truthful else None,
    )


def format_ladder(rows: List[dict]) -> str:
    header = (f"{'protocol':<42}{'FA':>7}{'FR':>7}{'Abstain(a/t)':>14}{'Coverage(a/t)':>16}"
              f"{'Sel.FA':>18}{'Sel.FR':>18}")
    lines = [header, "-" * len(header)]
    warnings: List[str] = []
    for r in rows:
        fa_s, fr_s = f"{r['fa']}/{r['n_attacks']}", f"{r['fr']}/{r['n_truthful']}"
        abstain_a, abstain_t = r.get("abstain_attacks"), r.get("abstain_truthful")
        abstain_s = f"{abstain_a}/{abstain_t}" if abstain_a is not None else "n/a"
        cov_a, cov_t = r.get("coverage_attacks"), r.get("coverage_truthful")
        cov_s = f"{cov_a:.0%}/{cov_t:.0%}" if cov_a is not None else "n/a"
        sel_fa = r.get("selective_fa")
        sel_fa_s = f"{r['fa']}/{r['n_attacks']-(abstain_a or 0)}={sel_fa:.2f}" if sel_fa is not None else "n/a (all abstained)"
        sel_fr = r.get("selective_fr")
        sel_fr_s = f"{r['fr']}/{r['n_truthful']-(abstain_t or 0)}={sel_fr:.2f}" if sel_fr is not None else "n/a (all abstained)"
        errors = r.get("errors", 0)
        marker = "  [!]" if errors else ""
        lines.append(f"{r['protocol']:<42}{fa_s:>7}{fr_s:>7}{abstain_s:>14}{cov_s:>16}"
                    f"{sel_fa_s:>18}{sel_fr_s:>18}{marker}")
        if errors:
            warnings.append(f"  [!] {r['protocol']}: {errors} case(s) had no cached/live review "
                            f"(missing/error/unparseable) — its FA/FR above are UNDER-COUNTED, not "
                            f"a true zero. Run with --live and a key, or sync the committed cache.")
    lines.append("")
    lines.append("FA/FR denominators are the full attack/truthful pool (population rate) -- a "
                 "protocol that abstains on hard cases can still show a low population FA/FR. "
                 "Sel.FA/Sel.FR ('selective risk') are FA/FR among cases the protocol actually "
                 "decided (excludes abstentions) -- the number to compare against a protocol that "
                 "never abstains. Wilson/exact 95% CIs for every rate are in the underlying row "
                 "dicts (fa_wilson, fa_cp, selective_fa_wilson, selective_fa_cp, etc.) even though "
                 "this compact view only prints the point estimate.")
    if warnings:
        lines.append("")
        lines.extend(warnings)
    return "\n".join(lines)


def p5_hybrid_row(cases: Sequence[Case], world: TrustedWorld, adjudicator_name: str,
                  adjudicator) -> dict:
    """P5-hybrid: a DIFFERENT protocol from the pure-abstention 'P5' row
    `ladder_row('P5_hybrid_abstain', ...)` produces with no adjudicator --
    that one is architecturally identical to P4 and never diverges from it.
    This one actually consults `adjudicator` (a P1-style judge, not
    deterministic) whenever the claim-appropriate anchor is inconclusive, so
    its result is judge-specific: report it as "P5-hybrid[adjudicator]", never
    bare "P5". Cases where the adjudicator itself has no cached/live response
    are counted as `errors`, not silently folded into abstention or "not FA"
    -- same discipline as p4p5_probe.run_probe."""
    attacks = [c for c in cases if not c.should_accept]
    truthful = [c for c in cases if c.should_accept]

    def _score(pool):
        false_n = abstain = errors = 0
        for c in pool:
            if _anchor_inconclusive(c, world):
                raw = adjudicator(c, world)
                if raw.outcome in ("missing", "error", "unparseable"):
                    errors += 1
                    continue
            d = decide("P5_hybrid_abstain", c, world, adjudicator=adjudicator)
            if d.outcome == CANNOT_VERIFY:
                abstain += 1
            elif (c.should_accept and d.false_reject(c)) or (not c.should_accept and d.false_accept(c)):
                false_n += 1
        return false_n, abstain, errors

    fa, abstain_a, err_a = _score(attacks)
    fr, abstain_t, err_t = _score(truthful)
    decided_a = len(attacks) - abstain_a - err_a
    decided_t = len(truthful) - abstain_t - err_t
    sel_fa, sel_fa_w, sel_fa_c = _selective(fa, decided_a)
    sel_fr, sel_fr_w, sel_fr_c = _selective(fr, decided_t)
    return dict(
        protocol=f"P5-hybrid[{adjudicator_name}]",
        n_attacks=len(attacks), fa=fa, fa_wilson=wilson_ci(fa, len(attacks)),
        fa_cp=clopper_pearson_ci(fa, len(attacks)),
        n_truthful=len(truthful), fr=fr, fr_wilson=wilson_ci(fr, len(truthful)),
        fr_cp=clopper_pearson_ci(fr, len(truthful)),
        abstain_attacks=abstain_a, abstain_truthful=abstain_t,
        coverage_attacks=decided_a / len(attacks) if attacks else None,
        coverage_truthful=decided_t / len(truthful) if truthful else None,
        selective_fa=sel_fa, selective_fa_wilson=sel_fa_w, selective_fa_cp=sel_fa_c,
        selective_fr=sel_fr, selective_fr_wilson=sel_fr_w, selective_fr_cp=sel_fr_c,
        errors=err_a + err_t,
    )


def build_ladder(cases: Sequence[Case], world: TrustedWorld,
                 provider_specs: Sequence[str] = (), live: bool = False,
                 p5_adjudicators: Sequence[str] = ()) -> List[dict]:
    rows = [ladder_row(PROTOCOLS[0], cases, world)]  # P0_self_report
    cache: Optional[ResponseCache] = None
    if provider_specs or p5_adjudicators:
        cache = ResponseCache()
    if provider_specs:
        for spec in provider_specs:
            prov = build_provider(spec)
            review = make_cached_reviewer(prov, cache, live=live)
            rows.append(p1_row(run_p1(list(cases), review, world, prov.name, prov.model)))
    rows += [ladder_row(p, cases, world) for p in PROTOCOLS[1:]]  # P2, P3, P4, P5 (abstain-only)
    for spec in p5_adjudicators:
        prov = build_provider(spec)
        review = make_cached_reviewer(prov, cache, live=live)
        rows.append(p5_hybrid_row(cases, world, spec, review))
    return rows


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="trust-eval-study-c-ladder")
    ap.add_argument("--scaled", action="store_true",
                    help="use the scaled n-instance corpus instead of the single flagship instance")
    ap.add_argument("--n", type=int, default=8, help="instances per flagship pattern when --scaled")
    ap.add_argument("--provider", action="append", default=[], metavar="PROVIDER:MODEL",
                    help="include P1 (text-only LLM review) for this judge; repeatable")
    ap.add_argument("--live", action="store_true", help="call the provider for cache misses")
    ap.add_argument("--p5-adjudicator", action="append", default=[], metavar="PROVIDER:MODEL",
                    help="also report P5 as a genuine hybrid: the anchor is consulted first, "
                         "and this judge is only asked on the cases where the anchor is "
                         "inconclusive; repeatable")
    args = ap.parse_args(argv)

    if args.scaled:
        world, cases = build_scaled_world(args.n), scaled_cases(args.n)
        corpus_desc = f"scaled, n={args.n} instances/pattern"
    else:
        world, cases = build_flagship_world(), flagship_cases()
        corpus_desc = "flagship (n=1 instance/pattern)"

    rows = build_ladder(cases, world, args.provider, args.live, args.p5_adjudicator)
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
