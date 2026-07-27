"""Isolated single-judge cost probe (see docs/full-technical-report.md and CHANGELOG.md for the
full directive this responds to). `run` touches exactly ONE provider:model
-- PHASE0_PROVIDER (deepseek:deepseek-v4-pro) by default, or any other
FULL_PANEL member via --provider -- live, across every judge-calling
surface a full panel run would touch, at the SAME n=10 already used
throughout this report -- NOT scaled up further; scaling n is a later,
separately-gated step (the power calculation), which only happens after
each probe's cost is measured and approved. Each run stays isolated to
the single provider:model it was given -- never combined with another
judge in the same invocation -- so results stay exactly attributable.
Reports EXACT measured call counts, token totals, and dollar cost, read
back from the cache records this run itself writes -- never an estimate.

Two subcommands, on purpose, not one:

    python3 -m trust_eval.study_c.cost_probe run [--provider P:M]        # fills the cache, live, needs a key
    python3 -m trust_eval.study_c.cost_probe report --provider-model P:M # reads the cache, prints exact numbers

so a `report` re-run never re-touches the network, matching this whole
harness's reproduce-from-committed-cache discipline. MUST run `run` from a
machine with the relevant provider's API key set and network access to
that provider's endpoint -- this cloud build session has neither for any
judge provider (verified directly).

DeepSeek has no confirmed batch/off-peak discount for the v4 generation as
of 2026-07-24 (see harness/pricing.py); Gemini, Anthropic, and OpenAI each
confirm a 50% batch discount, unused here since `run` calls the ordinary
synchronous endpoint via the existing `--provider --live` mechanism on
every surface's own CLI, not `harness/batch.py`'s real batch clients
(those are for a full multi-judge panel run, a separate and larger step
than these single-judge isolated probes).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Optional

from ..harness.cache import DEFAULT_CACHE_DIR
from ..harness.pricing import CONFIRMED_DATE, PRICING, estimate_cost
from . import adaptive, coordination_probe, extended_attacks, ladder, p4p5_probe, skeleton_probe

PHASE0_PROVIDER = "deepseek:deepseek-v4-pro"
BASE_N = 10  # the n already used throughout docs/full-technical-report.md today -- see module docstring

FULL_PANEL = [
    "deepseek:deepseek-v4-flash",
    "deepseek:deepseek-v4-pro",
    "gemini:gemini-3.1-flash-lite",
    "gemini:gemini-3.1-pro-preview",
]
# Gemini's Pro-tier slot: gemini-3.1-pro-preview, restored here after a
# brief detour. Sequence, for the record (full account in
# docs/full-technical-report.md/CHANGELOG.md): (1) an isolated probe against
# gemini-3.1-pro-preview hit persistent 429s on a Free-tier account; (2)
# swapped to gemini-2.5-pro (GA, cheaper) to sidestep preview-tier rate
# limits; (3) gemini-2.5-pro then 404'd -- turned out to require its own
# paid-tier gating, unresolved even after confirming the account had
# billing linked; (4) the account was independently confirmed at rate-
# limit Tier 1 (billing-linked, not Free), at which point retrying
# gemini-3.1-pro-preview directly worked cleanly with no further 429s --
# meaning Tier 1 billing was the actual fix all along, not the model
# choice. Reverted back to gemini-3.1-pro-preview here since that is what
# the live run actually completed against; gemini-2.5-pro's pricing stays
# sourced in harness/pricing.py as real, useful data, just unused by this
# panel. Its 404 was never root-caused and is not chased further now that
# the preview model works.
#
# Anthropic (claude-sonnet-5) and OpenAI (gpt-5.6-sol) were in the original
# six-judge panel but were dropped after this Phase 0 probe showed DeepSeek
# Pro's uncapped reasoning-token volume running well past a naive estimate
# -- the report author chose to keep the study to a clean 2x2 (provider x
# tier: DeepSeek flash/Pro, Gemini flash-lite/Pro), which still delivers
# the within-family flash-vs-Pro contrasts H3 needs, at the cost of the
# four-provider cross-section the original panel would have given. Their
# pricing stays in harness/pricing.py's PRICING table (removing it would
# lose the sourced numbers for no reason) -- they are just excluded from
# this projection and from any future confirmatory run.


def run(argv: Optional[List[str]] = None) -> int:
    """Touches every judge-calling surface with a single provider:model, live,
    filling the cache with usage-annotated records. Defaults to
    PHASE0_PROVIDER (the original Phase 0 probe subject); pass --provider to
    run this same isolated, single-model probe against any other judge in
    FULL_PANEL (e.g. gemini:gemini-3.1-pro-preview) -- each such run touches
    ONLY the provider:model given, never combined with any other judge in
    the same call, so results stay attributable to exactly one model.
    Prints progress only -- run `report --provider-model <same value>` after
    this to read exact cost numbers back from the cache."""
    ap = argparse.ArgumentParser(prog="trust-eval-study-c-cost-probe-run")
    ap.add_argument("--provider", default=PHASE0_PROVIDER,
                    help="'<provider>:<model>' to run this isolated probe against")
    args = ap.parse_args(argv)
    provider_model = args.provider

    print(f"Phase 0/isolated probe: filling cache for {provider_model} across every judge-calling surface, live.")
    print(f"n={BASE_N} (the corpus size already used throughout docs/full-technical-report.md -- not yet scaled up).\n")

    print("[1/7] confirmatory protocol comparison (ladder --scaled), P1 role")
    ladder.main(["--scaled", "--n", str(BASE_N), "--provider", provider_model, "--live"])

    print("\n[2/7] confirmatory protocol comparison, P5-hybrid adjudicator role")
    ladder.main(["--scaled", "--n", str(BASE_N), "--p5-adjudicator", provider_model, "--live"])

    print("\n[3/7] balanced observational-equivalence probe (p4p5_probe --balanced)")
    p4p5_probe.main(["--balanced", "--n", str(BASE_N), "--provider", provider_model, "--live"])

    print("\n[4/7] p4p5 probe, non-balanced, P5-hybrid adjudicator role")
    p4p5_probe.main(["--n", str(BASE_N), "--provider", provider_model, "--live"])

    print("\n[5/7] adaptive best-of-N attacker")
    adaptive.main(["--scaled", "--n", str(BASE_N), "--budgets", "1", "4", "8",
                  "--provider", provider_model, "--live"])

    print("\n[6/7] extended attack surface (race + binding + identity), P1 + P5-hybrid roles")
    extended_attacks.main(["--n", str(BASE_N), "--which", "all",
                           "--provider", provider_model, "--live",
                           "--p5-adjudicator", provider_model])
    print("       coordinated multi-artifact forgery")
    coordination_probe.main(["--n", str(BASE_N), "--provider", provider_model, "--live"])

    print("\n[7/7] structural skeleton (single-claim ladder + composite), P1 + P5-hybrid roles")
    skeleton_probe.main(["--n", str(BASE_N), "--which", "all",
                         "--provider", provider_model, "--live",
                         "--p5-adjudicator", provider_model])

    print(f"\nDone. Run `python3 -m trust_eval.study_c.cost_probe report --provider-model {provider_model}` "
         "for exact measured totals.")
    return 0


def _iter_cache_records(cache_dir: Path):
    for path in sorted(cache_dir.glob("*.json")):
        yield json.loads(path.read_text())


def report(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="trust-eval-study-c-cost-probe-report")
    ap.add_argument("--provider-model", default=PHASE0_PROVIDER,
                    help="'<provider>:<model>' to aggregate cache records for")
    args = ap.parse_args(argv)
    provider, model = args.provider_model.split(":", 1)

    records = [r for r in _iter_cache_records(DEFAULT_CACHE_DIR)
              if r.get("provider") == provider and r.get("model") == model and "usage" in r]
    n_calls = len(records)

    print(f"\n=== PHASE 0 -- MEASURED COST PROBE: {args.provider_model} ===")
    print(f"(pricing confirmed against provider docs on {CONFIRMED_DATE}; see docs/full-technical-report.md's Phase 0 section)\n")
    if n_calls == 0:
        print("No cache records found for this provider:model with usage data.")
        print("Run `python3 -m trust_eval.study_c.cost_probe run` first, live, with DEEPSEEK_API_KEY set.")
        return 1

    total_in = sum(r["usage"].get("input_tokens") or 0 for r in records)
    total_out = sum(r["usage"].get("output_tokens") or 0 for r in records)
    reasoning_vals = [r["usage"].get("reasoning_tokens") for r in records
                      if r["usage"].get("reasoning_tokens") is not None]
    total_hit = sum(r["usage"].get("cache_hit_input_tokens") or 0 for r in records)

    print(f"judge calls made:            {n_calls}")
    print(f"input tokens  (total):       {total_in}   (mean {total_in / n_calls:.1f})")
    if total_hit:
        print(f"  of which cache-hit input:  {total_hit}")
    print(f"output tokens (total):       {total_out}   (mean {total_out / n_calls:.1f})")
    if reasoning_vals:
        total_reasoning = sum(reasoning_vals)
        print(f"  of which reasoning:        {total_reasoning}   (mean over {len(reasoning_vals)} calls "
             f"reporting it: {total_reasoning / len(reasoning_vals):.1f})")
        print("  reasoning tokens are a SUBSET of output tokens above, already counted -- not additional")
    else:
        print("  reasoning-token breakdown: NOT present in any cached record for this provider:model --")
        print("  either this response shape doesn't report it, or every call reasoned for zero tokens;")
        print("  the output total above is the only figure available either way")

    use_batch = PRICING[args.provider_model]["batch_discount"] is not None
    cost = sum(
        estimate_cost(args.provider_model, r["usage"].get("input_tokens") or 0,
                      r["usage"].get("output_tokens") or 0, use_batch=use_batch,
                      cache_hit_input_tokens=r["usage"].get("cache_hit_input_tokens") or 0)
        for r in records
    )
    rate_note = ("batch/off-peak rate" if use_batch else
                "STANDARD SYNCHRONOUS rate -- no confirmed batch/off-peak discount for this "
                "model as of the pricing check date above; see harness/pricing.py")
    print(f"\nmeasured cost of this Phase 0 run ({rate_note}): ${cost:.4f}")

    _print_projection(n_calls, total_in / n_calls, total_out / n_calls, args.provider_model)
    return 0


def _print_projection(n_calls: int, mean_in: float, mean_out: float, base_provider_model: str) -> None:
    print("\n=== PROJECTED COST TABLE ===")
    print(f"Anchored on {base_provider_model}'s MEASURED per-call token profile above "
         f"(mean {mean_in:.0f} in / {mean_out:.0f} out) -- projected onto every judge AS IF it used "
         f"the same profile. That assumption is explicitly weak for reasoning models whose reasoning-\n"
         f"token volume differs from DeepSeek Pro's; flagged per-row below, not silently assumed away.\n")
    print(f"{'judge':<32}{'calls':>8}{'projected $':>14}  note")
    print("-" * 100)
    row_totals = {}
    for pm in FULL_PANEL:
        use_batch = PRICING[pm]["batch_discount"] is not None
        per_call = estimate_cost(pm, int(mean_in), int(mean_out), use_batch=use_batch)
        total = per_call * n_calls
        row_totals[pm] = total
        notes = []
        if pm == "openai:gpt-5.6-sol":
            notes.append("reasoning model -- likely emits MORE reasoning tokens than DeepSeek Pro; "
                         "widen this projection, do not treat as parity")
        if not use_batch:
            notes.append("no confirmed batch/off-peak discount -- priced at standard synchronous rate")
        print(f"{pm:<32}{n_calls:>8}{('$' + format(total, '.2f')):>14}  {'; '.join(notes)}")

    panel_total = sum(row_totals.values())
    print(f"\nfull {len(FULL_PANEL)}-judge panel at n={BASE_N} (this run's n): ${panel_total:.2f}  "
         f"(sum of the {len(FULL_PANEL)} rows above -- see per-row notes)")
    print("\nCost is LINEAR in n in this harness (each added instance contributes a fixed number of "
         "judge calls per surface) -- scale the n=10 total by (target_n / 10):")
    for target_n in (20, 30, 50, 100):
        print(f"  n={target_n:<4d} full {len(FULL_PANEL)}-judge panel: ~${panel_total * (target_n / BASE_N):.2f}")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="trust-eval-study-c-cost-probe")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run")
    sub.add_parser("report")
    args, rest = ap.parse_known_args(argv)
    if args.cmd == "run":
        return run(rest)
    return report(rest)


if __name__ == "__main__":
    import sys
    sys.exit(main())


__all__ = ["run", "report", "main", "PHASE0_PROVIDER", "BASE_N", "FULL_PANEL"]
