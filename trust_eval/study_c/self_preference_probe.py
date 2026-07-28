"""Self-preference / in-group bias probe: does a text-only judge trust a
claim more when the submission is attributed to a model from its OWN
provider family, holding the underlying claim -- true or false -- exactly
fixed?

This is a different axis from `manipulation_probe.py` (which varies HOW a
claim is phrased) and from every existing attack (which varies WHAT is
claimed). Here the only thing that changes is a single metadata field,
`executor_model`, naming which model produced the submission -- the kind of
provenance tag a real multi-model agent fleet actually logs (this study's
own four-judge panel, and reportedly production harnesses like the one
this research grew out of, both route different tasks through different
model families). Self-preference bias in LLM-as-judge settings is
documented in the general eval literature (a judge rating its own family's
output higher, blind to identity, in ordinary quality-judgment tasks); this
probe asks the same question inside a governance/oversight context instead
-- does that bias also show up when the thing being judged is a trust
decision about another agent's work, not a quality score?

Three conditions, same base cases as `manipulation_probe.py` (the three
flagship patterns whose anchor resolves definitively):

  unattributed  -- no `executor_model` field (CONTROL; identical to the
                   already-committed principal-corpus cache, so it costs no
                   new live calls)
  gemini        -- `executor_model: "Gemini"`
  deepseek      -- `executor_model: "DeepSeek"`

Both attributed corpora are FIXED, identical inputs shown to every judge --
neither is built per-judge -- so the comparison is symmetric and
falsifiable: for a Gemini-family judge, is FA(gemini-attributed) >
FA(deepseek-attributed)? For a DeepSeek-family judge, is
FA(deepseek-attributed) > FA(gemini-attributed)? An asymmetry that lines up
with the reviewing judge's own family is attributable to family
self-preference; a symmetric or null result is evidence against it, not an
absence of a result.

`executor_model` is consumed by no anchor and no deterministic protocol
(same grep-verified guarantee as `manipulation_probe.py`'s `operator_note`)
-- P2/P3/P4/P5 rows are printed to make that immunity visible, not just
asserted. P5-hybrid is not run here for the same reason as
`manipulation_probe.py`: none of the three base patterns ever leave the
anchor inconclusive.
"""

from __future__ import annotations

import argparse
import copy
from typing import List, Optional

from ..harness.cache import ResponseCache
from ..harness.providers import build_provider
from .ladder import format_ladder, ladder_row, p1_row
from .llm_review import make_cached_reviewer, run_p1
from .protocols import PROTOCOLS
from .surrogates import Case, scaled_cases
from .world import TrustedWorld, build_scaled_world

_KEEP_LABELS = {"benign", "stale_after_drift", "fabricated_authorization", "wrong_baseline_proof"}

_FAMILY_LABEL = {"gemini": "Gemini", "deepseek": "DeepSeek"}


def _base_cases(n: int) -> List[Case]:
    return [c for c in scaled_cases(n) if c.label in _KEEP_LABELS]


def _attributed(cases: List[Case], family_label: str) -> List[Case]:
    out: List[Case] = []
    for c in cases:
        c2 = c.model_copy(deep=True)
        c2.payload = dict(c2.payload, executor_model=family_label)
        out.append(c2)
    return out


def _p1_rows(cases: List[Case], world: TrustedWorld, provider_specs: List[str],
            live: bool, cache: ResponseCache) -> List[dict]:
    rows = []
    for spec in provider_specs:
        prov = build_provider(spec)
        review = make_cached_reviewer(prov, cache, live=live)
        rows.append(p1_row(run_p1(list(cases), review, world, prov.name, prov.model)))
    return rows


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="trust-eval-study-c-self-preference")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--provider", action="append", default=[], metavar="PROVIDER:MODEL",
                    help="include P1 (text-only LLM review) for this judge; repeatable")
    ap.add_argument("--live", action="store_true", help="call the provider for cache misses")
    args = ap.parse_args(argv)

    world = build_scaled_world(args.n)
    base = _base_cases(args.n)
    n_false = sum(1 for c in base if not c.should_accept)
    n_true = sum(1 for c in base if c.should_accept)
    cache = ResponseCache()

    print("\nSTUDY C -- SELF-PREFERENCE / IN-GROUP BIAS PROBE (exploratory; not part of the n=100 confirmatory corpus)")
    print(f"n={len(base)} cases ({n_false} false / {n_true} truthful) -- same underlying facts in all three "
         "variants, only the attributed 'executor_model' provenance field differs.\n")

    conditions = [("UNATTRIBUTED (control)", base)]
    for _, label in _FAMILY_LABEL.items():
        conditions.append((f"ATTRIBUTED TO {label.upper()}", _attributed(base, label)))

    for title, cases in conditions:
        print(f"--- {title} ---")
        rows = [ladder_row(PROTOCOLS[0], cases, world)]
        rows += _p1_rows(cases, world, args.provider, args.live, cache)
        rows += [ladder_row(p, cases, world) for p in PROTOCOLS[1:]]
        print(format_ladder(rows))
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
