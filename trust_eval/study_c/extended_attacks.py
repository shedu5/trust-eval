"""Extended attack surface: race conditions (TOCTOU), task-to-anchor binding
confusion, and forged actor/tool identity -- three of the five untested
attack classes a third external review named, closed with real cases and
real deterministic results rather than left as a disclosed limitation. (A
fourth, coordinated multi-artifact forgery, needs a different mechanism --
see coordination_probe.py. A fifth, poisoned approval-ledger *content*, is
a different research question from this study's central claim -- see
Threat-model boundary -- and is not addressed here.)

Deterministic protocols (P0, P2, P3, P4, plain P5) always run, reusing
`ladder_row`/`format_ladder` from ladder.py unmodified. P1 (text-only LLM)
and P5-hybrid (LLM adjudicator) run too when `--provider`/`--p5-adjudicator`
are given, through `llm_review.py`'s v2 prompt (`PROMPT_VERSION_2` /
`_SYSTEM_V2`) -- a SEPARATE prompt_version from the principal corpus's v1,
so filling live judge results here cannot invalidate the 200 already-cached
confirmatory-corpus records keyed on v1's exact text. Omit `--provider`
entirely and this module behaves exactly as before: an architecture-only
answer that needs no judge and no key.
"""

from __future__ import annotations

import argparse
from typing import List, Optional

from ..harness.cache import ResponseCache
from ..harness.providers import build_provider
from .ladder import format_ladder, ladder_row, p1_row, p5_hybrid_row
from .llm_review import PROMPT_VERSION_2, _SYSTEM_V2, make_cached_reviewer, run_p1
from .protocols import PROTOCOLS
from .world import (
    Claim,
    TrustedWorld,
    binding_confusion_cases,
    build_binding_confusion_world,
    build_identity_world,
    build_race_condition_world,
    identity_cases,
    race_condition_cases,
)


def _print_report(title: str, blurb: str, cases: List[Claim], world: TrustedWorld,
                  provider_specs: List[str], live: bool, p5_adjudicators: List[str]) -> None:
    print(f"\nSTUDY C -- {title} (exploratory; not part of the n=100 confirmatory corpus)")
    print(blurb)
    n_false = sum(1 for c in cases if not c.should_accept)
    n_true = sum(1 for c in cases if c.should_accept)
    print(f"n={len(cases)} cases ({n_false} false / {n_true} truthful)\n")

    rows = [ladder_row(PROTOCOLS[0], cases, world)]  # P0
    cache: Optional[ResponseCache] = None
    if provider_specs or p5_adjudicators:
        cache = ResponseCache()
    for spec in provider_specs:
        prov = build_provider(spec)
        review = make_cached_reviewer(prov, cache, live=live, system=_SYSTEM_V2,
                                      prompt_version=PROMPT_VERSION_2)
        rows.append(p1_row(run_p1(list(cases), review, world, prov.name, prov.model)))
    rows += [ladder_row(p, cases, world) for p in PROTOCOLS[1:]]  # P2, P3, P4, P5
    for spec in p5_adjudicators:
        prov = build_provider(spec)
        review = make_cached_reviewer(prov, cache, live=live, system=_SYSTEM_V2,
                                      prompt_version=PROMPT_VERSION_2)
        rows.append(p5_hybrid_row(cases, world, spec, review))
    print(format_ladder(rows))


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="trust-eval-study-c-extended-attacks")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--which", choices=["race", "binding", "identity", "all"], default="all")
    ap.add_argument("--provider", action="append", default=[], metavar="PROVIDER:MODEL",
                    help="include P1 (text-only LLM review, v2 prompt) for this judge; repeatable")
    ap.add_argument("--live", action="store_true", help="call the provider for cache misses")
    ap.add_argument("--p5-adjudicator", action="append", default=[], metavar="PROVIDER:MODEL",
                    help="also report P5 as a genuine hybrid using this judge (v2 prompt); repeatable")
    args = ap.parse_args(argv)

    if args.which in ("race", "all"):
        _print_report(
            "RACE-CONDITION (TOCTOU) EXECUTION REPLAY",
            "Attack: replay a stale PASS recorded before the world's head moved on, even\n"
            "though a fresh execution result now exists at the current head and disagrees.\n"
            "fresh_execution is keyed strictly by the CURRENT head, never by any commit the\n"
            "claim itself cites -- this tests whether that design holds under a case built\n"
            "specifically to exploit staleness, not just by reading the anchor code.",
            race_condition_cases(args.n), build_race_condition_world(args.n),
            args.provider, args.live, args.p5_adjudicator,
        )

    if args.which in ("binding", "all"):
        _print_report(
            "TASK-TO-ANCHOR BINDING CONFUSION",
            "Attack: cite a REAL approval-ledger entry that belongs to a DIFFERENT task.\n"
            "approval_for(task_id, file) matches on exact task_id AND file -- this tests\n"
            "whether a borrowed-but-genuine approval is correctly rejected for the task it\n"
            "was never granted to, not just assumed safe from reading the anchor code.",
            binding_confusion_cases(args.n), build_binding_confusion_world(args.n),
            args.provider, args.live, args.p5_adjudicator,
        )

    if args.which in ("identity", "all"):
        _print_report(
            "FORGED ACTOR/TOOL IDENTITY",
            "Attack: assert a different actor performed the task than the one recorded by\n"
            "an out-of-band identity anchor (e.g. a session/auth log outside the executor's\n"
            "write authority). The first end-to-end exercise of ClaimType.IDENTITY and the\n"
            "actor_identity anchor added in direct response to a third external review.",
            identity_cases(args.n), build_identity_world(args.n),
            args.provider, args.live, args.p5_adjudicator,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
