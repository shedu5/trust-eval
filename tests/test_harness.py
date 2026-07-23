"""Suite construction, cache round-trip, and missing-response handling."""

import json
import re

from trust_eval.harness.cache import ResponseCache, cache_key
from trust_eval.harness.prompt import PROMPT_VERSION, parse_verdict, render_judge_prompt
from trust_eval.harness.providers import ScriptedProvider
from trust_eval.harness.runner import run_case, run_suite
from trust_eval.harness.suite import GroundTruth, build_suite
from trust_eval.attacks import ATTACK_CLASSES


class _RaisingProvider:
    name = "raising"
    model = "boom-1"

    def complete(self, prompt):
        raise RuntimeError("simulated API failure")


def test_suite_shape():
    cases = build_suite()
    assert len(cases) == 15 * len(ATTACK_CLASSES)
    per_attack = {a: 0 for a in ATTACK_CLASSES}
    for c in cases:
        per_attack[c.attack] += 1
        if c.attack == "benign":
            assert c.ground_truth == GroundTruth.TRUSTWORTHY
        else:
            assert c.ground_truth == GroundTruth.TAMPERED
    assert set(per_attack.values()) == {15}


def test_cache_roundtrip_and_missing(tmp_path):
    cache = ResponseCache(tmp_path / "records")
    cases = build_suite()[:6]
    provider = ScriptedProvider()  # reject-all stub

    # First: no cache and not live -> everything missing.
    missing = run_suite(cases, provider, cache, live=False)
    assert all(r.verdict == "missing" and r.source.value == "missing" for r in missing)

    # Live fills the cache.
    live = run_suite(cases, provider, cache, live=True)
    assert all(r.verdict == "reject" and r.source.value == "live" for r in live)

    # Now cache-only reproduces the same verdicts from disk.
    cached = run_suite(cases, provider, cache, live=False)
    assert all(r.verdict == "reject" and r.source.value == "cache" for r in cached)


def test_parse_verdict_variants():
    assert parse_verdict('{"verdict":"accept","reason":"ok"}').accepted is True
    assert parse_verdict('{"verdict":"reject","reason":"bad hash"}').verdict == "reject"
    assert parse_verdict("prose then {\"verdict\": \"ACCEPT\"}").verdict == "accept"
    assert parse_verdict("garbage").verdict == "unparseable"


def test_provider_error_is_recorded_not_cached(tmp_path):
    """One failing judge call is recorded as an error and never cached."""
    cache = ResponseCache(tmp_path / "records")
    cases = build_suite()[:3]
    results = run_suite(cases, _RaisingProvider(), cache, live=True)
    assert all(r.verdict == "error" for r in results)
    assert not list((tmp_path / "records").glob("*.json")), "errors must not be cached"


def test_empty_response_not_cached(tmp_path):
    """A model returning empty text yields unparseable and is not cached."""
    cache = ResponseCache(tmp_path / "records")
    cases = build_suite()[:3]
    empty = ScriptedProvider(model="empty", responder=lambda _p: "")
    results = run_suite(cases, empty, cache, live=True)
    assert all(r.verdict == "unparseable" for r in results)
    assert not list((tmp_path / "records").glob("*.json"))


def test_poisoned_cache_self_heals_on_live(tmp_path):
    """A cached-but-unusable entry is re-fetched on a live run, not trusted."""
    cache = ResponseCache(tmp_path / "records")
    case = build_suite()[0]
    good = ScriptedProvider(responder=lambda _p: '{"verdict":"accept","reason":"ok"}')
    prompt = render_judge_prompt(case.bundle)
    key = cache_key(good.name, good.model, PROMPT_VERSION, prompt)
    # Seed a poisoned (empty-raw) record like the old buggy run produced.
    cache.put(key, {"provider": good.name, "model": good.model,
                    "verdict": "unparseable", "reason": "", "raw": ""})

    # Cache-only surfaces it as not-accept rather than trusting it.
    assert run_case(case, good, cache, live=False).verdict != "accept"
    # Live self-heals: re-fetches and overwrites with a usable verdict.
    healed = run_case(case, good, cache, live=True)
    assert healed.verdict == "accept" and healed.source.value == "live"
