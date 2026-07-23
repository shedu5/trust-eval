"""Command-line entry point: run the suite and emit per-class FA/FR tables.

Examples
--------
Cache-only (no API key needed — reproduces committed tables)::

    python -m trust_eval --provider anthropic:claude-x --provider openai:gpt-y

Live run (fills the cache; needs the relevant API key)::

    python -m trust_eval --provider anthropic:claude-x --live

Each provider is scored independently and written to ``reports/``. There is no
cross-provider aggregate — comparison is left to the reader, per the project's
claims discipline.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List

from .harness.cache import ResponseCache
from .harness.providers import build_provider
from .harness.runner import run_suite
from .harness.suite import build_suite
from .scorer import ClassScore, format_table, score_results


def _write_reports(spec: str, scores: List[ClassScore], results, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = spec.replace(":", "_").replace("/", "_")

    (out_dir / f"results-{tag}.jsonl").write_text(
        "".join(json.dumps(r.model_dump(mode="json")) + "\n" for r in results)
    )

    md = [f"# Per-class results — `{spec}`", "", "| attack class | metric | n | accept | reject | error | rate |",
          "|---|---|---:|---:|---:|---:|---:|"]
    for s in scores:
        rate = "n/a" if s.rate is None else f"{s.rate:.3f}"
        md.append(
            f"| {s.attack} | {s.metric} | {s.n} | {s.n_accept} | {s.n_reject} "
            f"| {s.n_error} | {rate} |"
        )
    (out_dir / f"table-{tag}.md").write_text("\n".join(md) + "\n")


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="trust-eval")
    parser.add_argument(
        "--provider", action="append", default=[], metavar="PROVIDER:MODEL",
        help="Judge spec, e.g. anthropic:claude-x. Repeat for multi-judge.",
    )
    parser.add_argument("--live", action="store_true", help="Fill cache misses with live calls.")
    parser.add_argument("--cache-dir", default=None, help="Override cache directory.")
    parser.add_argument("--out-dir", default="reports", help="Where to write results/tables.")
    parser.add_argument("--n", type=int, default=None, help="Limit corpus size (default: full).")
    args = parser.parse_args(argv)

    # Env fallbacks so `docker compose up` needs no arguments.
    if not args.provider and os.environ.get("TRUST_EVAL_PROVIDERS"):
        args.provider = [
            s.strip() for s in os.environ["TRUST_EVAL_PROVIDERS"].split(",") if s.strip()
        ]
    if os.environ.get("TRUST_EVAL_LIVE", "").lower() in ("1", "true", "yes"):
        args.live = True

    if not args.provider:
        parser.error("provide --provider PROVIDER:MODEL or set TRUST_EVAL_PROVIDERS")

    cache = ResponseCache(args.cache_dir) if args.cache_dir else ResponseCache()
    cases = build_suite(args.n)
    out_dir = Path(args.out_dir)

    any_missing = False
    for spec in args.provider:
        provider = build_provider(spec)
        results = run_suite(cases, provider, cache, live=args.live)
        n_missing = sum(1 for r in results if r.verdict == "missing")
        any_missing = any_missing or n_missing > 0
        scores = score_results(results)

        print(f"\n=== {spec} ===")
        print(format_table(scores))
        if n_missing:
            print(f"\n[!] {n_missing}/{len(results)} cases had no cached response. "
                  f"Re-run with --live and an API key to fill them.")
        _write_reports(spec, scores, results, out_dir)

    if any_missing and not args.live:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
