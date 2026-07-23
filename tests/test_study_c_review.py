"""P1 text-only LLM review (offline, scripted judges).

A gullible reviewer accepts every self-consistent forgery (matching deterministic
P0/P2); a skeptical one rejects everything. Both are what a text-only monitor with
no anchor looks like at the extremes; a real model lands in between and is measured
live via the harness.
"""

from trust_eval.harness.cache import ResponseCache
from trust_eval.harness.providers import ScriptedProvider
from trust_eval.study_c.llm_review import make_cached_reviewer, run_p1
from trust_eval.study_c.surrogates import flagship_cases
from trust_eval.study_c.world import build_flagship_world

W = build_flagship_world()
CASES = flagship_cases()


def test_p1_gullible_accepts_every_forgery(tmp_path):
    cache = ResponseCache(tmp_path / "r")
    prov = ScriptedProvider(model="gullible",
                            responder=lambda _p: '{"verdict":"accept","reason":"looks internally fine"}')
    s = run_p1(CASES, make_cached_reviewer(prov, cache, live=True), W, "scripted", "gullible")
    assert s.false_accept == s.n_attacks     # accepts all self-consistent forgeries
    assert s.false_reject == 0
    assert s.errors == 0


def test_p1_skeptical_rejects_everything(tmp_path):
    cache = ResponseCache(tmp_path / "r")
    prov = ScriptedProvider(model="skeptical")   # default reject-all
    s = run_p1(CASES, make_cached_reviewer(prov, cache, live=True), W, "scripted", "skeptical")
    assert s.false_accept == 0
    assert s.false_reject == s.n_truthful


def test_p1_cache_reproduces_without_live(tmp_path):
    cache = ResponseCache(tmp_path / "r")
    prov = ScriptedProvider(model="gullible",
                            responder=lambda _p: '{"verdict":"accept","reason":"x"}')
    run_p1(CASES, make_cached_reviewer(prov, cache, live=True), W, "s", "gullible")   # fill cache
    # cache-only: no live, must reproduce (no errors)
    s = run_p1(CASES, make_cached_reviewer(prov, cache, live=False), W, "s", "gullible")
    assert s.errors == 0 and s.false_accept == s.n_attacks
