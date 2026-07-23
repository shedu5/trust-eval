"""Run the suite through a judge provider, using the cache, and record verdicts.

Robustness properties that matter for a harness a stranger will run:

* **One bad call never kills the run.** A provider exception (bad model id, rate
  limit, network) is caught and recorded as ``verdict="error"`` for that case;
  the remaining cases proceed.
* **Failures are never cached.** Only clean ``accept``/``reject`` verdicts are
  written to the cache, so a re-run re-fetches anything that errored or came back
  empty instead of trusting a poisoned entry. A cache entry whose stored raw text
  no longer yields a usable verdict is treated as a miss on a live run and
  re-fetched — the cache self-heals.
* **Verdicts are parsed from the stored raw text on read**, so an improved parser
  applies to already-cached responses with no new API calls.

Default behaviour is cache-first: with ``live=False`` a miss is recorded as
``source="missing"`` rather than silently skipped, so an incomplete cache is
visible in the results instead of quietly shrinking the denominator.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel

from .cache import ResponseCache, cache_key
from .prompt import PROMPT_VERSION, parse_verdict, render_judge_prompt
from .providers import JudgeProvider
from .suite import Case, GroundTruth


class Source(str, Enum):
    CACHE = "cache"
    LIVE = "live"
    MISSING = "missing"


class CaseResult(BaseModel):
    case_id: str
    bundle_id: str
    attack: str
    ground_truth: GroundTruth
    provider: str
    model: str
    verdict: str  # accept | reject | unparseable | error | missing
    reason: str
    source: Source


def _result(case: Case, provider: JudgeProvider, verdict: str, reason: str, source: Source,
            model: Optional[str] = None) -> CaseResult:
    return CaseResult(
        case_id=case.case_id,
        bundle_id=case.bundle_id,
        attack=case.attack,
        ground_truth=case.ground_truth,
        provider=provider.name,
        model=model or provider.model,
        verdict=verdict,
        reason=reason,
        source=source,
    )


def _usable(record: Optional[dict]) -> Optional[object]:
    """Return the parsed verdict if a cache record yields accept/reject, else None."""
    if not record:
        return None
    parsed = parse_verdict(record.get("raw", ""))
    return parsed if parsed.verdict in ("accept", "reject") else None


def run_case(
    case: Case,
    provider: JudgeProvider,
    cache: ResponseCache,
    live: bool = False,
) -> CaseResult:
    prompt = render_judge_prompt(case.bundle)
    key = cache_key(provider.name, provider.model, PROMPT_VERSION, prompt)
    record = cache.get(key)

    parsed = _usable(record)
    if parsed is not None:
        return _result(case, provider, parsed.verdict, parsed.reason, Source.CACHE,
                       model=record.get("model"))

    # No usable cached verdict.
    if not live:
        if record is not None:  # a poisoned/empty cache entry, surfaced in cache-only mode
            p = parse_verdict(record.get("raw", ""))
            return _result(case, provider, p.verdict, "cached response is not usable",
                           Source.CACHE, model=record.get("model"))
        return _result(case, provider, "missing",
                       "no cached response; run with --live and an API key to fill",
                       Source.MISSING)

    # Live: fetch (miss or self-healing a poisoned entry).
    try:
        raw = provider.complete(prompt)
    except Exception as e:  # never let one call kill the whole run
        return _result(case, provider, "error", f"call failed: {e}"[:300], Source.LIVE)

    parsed = parse_verdict(raw)
    if parsed.verdict in ("accept", "reject"):
        cache.put(key, {
            "provider": provider.name,
            "model": provider.model,
            "prompt_version": PROMPT_VERSION,
            "verdict": parsed.verdict,
            "reason": parsed.reason,
            "raw": raw,
        })
        return _result(case, provider, parsed.verdict, parsed.reason, Source.LIVE)

    # Non-empty but unparseable — do not cache, surface it.
    return _result(case, provider, "unparseable", "could not parse a verdict", Source.LIVE)


def run_suite(
    cases: List[Case],
    provider: JudgeProvider,
    cache: Optional[ResponseCache] = None,
    live: bool = False,
) -> List[CaseResult]:
    cache = cache or ResponseCache()
    return [run_case(c, provider, cache, live=live) for c in cases]


__all__ = ["Source", "CaseResult", "run_case", "run_suite"]
