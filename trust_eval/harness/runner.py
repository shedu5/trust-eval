"""Run the suite through a judge provider, using the cache, and record verdicts.

Default behaviour is cache-first: if a case's response is cached it is used and
no network call happens. With ``live=True`` and a configured provider/key, cache
misses are filled by a real model call and written back. With ``live=False`` a
miss is recorded as ``source="missing"`` rather than silently skipped, so an
incomplete cache is visible in the results instead of quietly shrinking the
denominator.
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
    verdict: str  # accept | reject | unparseable | missing
    reason: str
    source: Source


def run_case(
    case: Case,
    provider: JudgeProvider,
    cache: ResponseCache,
    live: bool = False,
) -> CaseResult:
    prompt = render_judge_prompt(case.bundle)
    key = cache_key(provider.name, provider.model, PROMPT_VERSION, prompt)

    record = cache.get(key)
    source = Source.CACHE
    if record is None:
        if not live:
            return CaseResult(
                case_id=case.case_id,
                bundle_id=case.bundle_id,
                attack=case.attack,
                ground_truth=case.ground_truth,
                provider=provider.name,
                model=provider.model,
                verdict="missing",
                reason="no cached response; run with --live and an API key to fill",
                source=Source.MISSING,
            )
        raw = provider.complete(prompt)
        parsed = parse_verdict(raw)
        record = {
            "provider": provider.name,
            "model": provider.model,
            "prompt_version": PROMPT_VERSION,
            "verdict": parsed.verdict,
            "reason": parsed.reason,
            "raw": raw,
        }
        cache.put(key, record)
        source = Source.LIVE

    return CaseResult(
        case_id=case.case_id,
        bundle_id=case.bundle_id,
        attack=case.attack,
        ground_truth=case.ground_truth,
        provider=record.get("provider", provider.name),
        model=record.get("model", provider.model),
        verdict=record.get("verdict", "unparseable"),
        reason=record.get("reason", ""),
        source=source,
    )


def run_suite(
    cases: List[Case],
    provider: JudgeProvider,
    cache: Optional[ResponseCache] = None,
    live: bool = False,
) -> List[CaseResult]:
    cache = cache or ResponseCache()
    return [run_case(c, provider, cache, live=live) for c in cases]


__all__ = ["Source", "CaseResult", "run_case", "run_suite"]
