"""Scorer math, including an end-to-end 'perfect judge' pipeline check.

The perfect-judge test wires the real suite through the runner and scorer using
an offline judge that consults the ground-truth verifier. A perfect judge must
yield FA = 0 for every tampered class and FR = 0 for benign — which confirms the
suite labels, the verdict plumbing, and the scorer all agree with ground truth.
"""

import json
import re

from trust_eval.harness.cache import ResponseCache
from trust_eval.harness.providers import ScriptedProvider
from trust_eval.harness.runner import run_suite
from trust_eval.harness.suite import build_suite
from trust_eval.schema import EvidenceBundle
from trust_eval.scorer import score_results
from trust_eval.verify import verify_bundle

_JSON_BLOCK = re.compile(r"```json\n(.*)\n```", re.DOTALL)


def _perfect_responder(prompt: str) -> str:
    """Extract the bundle from the prompt and decide via ground truth."""
    m = _JSON_BLOCK.search(prompt)
    bundle = EvidenceBundle.model_validate(json.loads(m.group(1)))
    valid = verify_bundle(bundle).is_valid
    verdict = "accept" if valid else "reject"
    return json.dumps({"verdict": verdict, "reason": "ground-truth"})


def _score_map(scores):
    return {s.attack: s for s in scores}


def test_perfect_judge_is_flawless(tmp_path):
    cache = ResponseCache(tmp_path / "records")
    provider = ScriptedProvider(model="perfect", responder=_perfect_responder)
    results = run_suite(build_suite(), provider, cache, live=True)
    scores = _score_map(score_results(results))

    assert scores["benign"].metric == "FR"
    assert scores["benign"].rate == 0.0
    for attack, s in scores.items():
        if attack == "benign":
            continue
        assert s.metric == "FA"
        assert s.rate == 0.0, (attack, s)
        assert s.n == 15


def test_accept_all_judge(tmp_path):
    cache = ResponseCache(tmp_path / "records")
    provider = ScriptedProvider(
        model="accept-all",
        responder=lambda _p: '{"verdict":"accept","reason":"x"}',
    )
    results = run_suite(build_suite(), provider, cache, live=True)
    scores = _score_map(score_results(results))
    # Accepts everything: benign FR = 0, every tampered class FA = 1.
    assert scores["benign"].rate == 0.0
    for attack, s in scores.items():
        if attack != "benign":
            assert s.rate == 1.0, (attack, s)


def test_reject_all_judge(tmp_path):
    cache = ResponseCache(tmp_path / "records")
    provider = ScriptedProvider(model="reject-all")  # default reject-all
    results = run_suite(build_suite(), provider, cache, live=True)
    scores = _score_map(score_results(results))
    # Rejects everything: benign FR = 1, every tampered class FA = 0.
    assert scores["benign"].rate == 1.0
    for attack, s in scores.items():
        if attack != "benign":
            assert s.rate == 0.0, (attack, s)
