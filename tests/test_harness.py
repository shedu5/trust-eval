"""Suite construction, cache round-trip, and missing-response handling."""

import json
import re

from trust_eval.harness.cache import ResponseCache
from trust_eval.harness.prompt import parse_verdict
from trust_eval.harness.providers import ScriptedProvider
from trust_eval.harness.runner import run_suite
from trust_eval.harness.suite import GroundTruth, build_suite
from trust_eval.attacks import ATTACK_CLASSES


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
