"""Paired exact McNemar comparisons (offline, scripted judges + deterministic
protocols only -- no live calls needed to validate the pairing/counting logic
and the matrix wiring)."""

from trust_eval.harness.cache import ResponseCache
from trust_eval.harness.providers import ScriptedProvider
from trust_eval.study_c.compare import decider_for, paired_errors, run_matrix
from trust_eval.study_c.protocols import decide
from trust_eval.study_c.surrogates import flagship_cases
from trust_eval.study_c.world import build_flagship_world

W = build_flagship_world()
CASES = flagship_cases()
BASELINE = "P3_claim_appropriate_anchor"


def _det(protocol):
    return lambda c, w: decide(protocol, c, w)


def test_p0_vs_p3_fa_is_fully_discordant():
    r = paired_errors("P0_self_report", _det("P0_self_report"),
                      BASELINE, _det(BASELINE), CASES, W, axis="FA")
    assert r.n == 4                     # 4 attacks in the flagship corpus
    assert r.a_wrong_b_right == 4       # P0 always wrong, P3 always right
    assert r.a_right_b_wrong == 0
    assert r.both_wrong == 0 and r.both_right == 0
    # n=4 fully discordant is the strongest possible signal at this sample
    # size, yet the exact two-sided binomial floor at n=4 is 2*(1/2)**4=0.125
    # -- it still can't clear p<0.05. This is exactly why the corpus was
    # scaled to n=100 before trusting any McNemar comparison (see the scaled
    # matrix run, where the same fully-discordant pattern at n=40 reaches
    # p<1e-10).
    assert abs(r.p_value - 0.125) < 1e-9


def test_identical_protocol_vs_itself_has_no_discordant_pairs():
    r = paired_errors(BASELINE, _det(BASELINE), BASELINE, _det(BASELINE), CASES, W, axis="FA")
    assert r.a_wrong_b_right == 0 and r.a_right_b_wrong == 0
    assert r.p_value == 1.0


def test_axis_must_be_fa_or_fr():
    import pytest
    with pytest.raises(ValueError):
        paired_errors("a", _det(BASELINE), "b", _det(BASELINE), CASES, W, axis="bogus")


def test_decider_for_deterministic_protocol_matches_decide_directly():
    cache = ResponseCache()
    d = decider_for("P0_self_report", cache, live=False)
    for c in CASES:
        assert d(c, W).outcome == decide("P0_self_report", c, W).outcome


def test_decider_for_scripted_provider_uses_cache(tmp_path):
    cache = ResponseCache(tmp_path / "r")
    prov = ScriptedProvider(model="gullible",
                            responder=lambda _p: '{"verdict":"accept","reason":"x"}')
    # can't build_provider() a ScriptedProvider by spec string, so exercise the
    # underlying cached-reviewer path the same way decider_for would for a real
    # provider:model spec.
    from trust_eval.study_c.llm_review import make_cached_reviewer
    review = make_cached_reviewer(prov, cache, live=True)
    for c in CASES:
        assert review(c, W).outcome == "accept"


def test_run_matrix_covers_fixed_pairs_on_both_axes():
    cache = ResponseCache()
    results = run_matrix(CASES, W, cache, live=False, provider_specs=[])
    # P0 vs baseline and P2 vs baseline, each on FA and FR = 4 rows
    assert len(results) == 4
    pairs = {(r.name_a, r.name_b, r.axis) for r in results}
    assert ("P0_self_report", BASELINE, "FA") in pairs
    assert ("P2_deterministic_internal", BASELINE, "FR") in pairs


def test_run_matrix_p2_vs_baseline_fa_matches_p0():
    # P2 (deterministic internal-consistency) also always accepts every
    # flagship forgery, so its FA discordance vs. the anchored baseline should
    # mirror P0's exactly on this corpus.
    cache = ResponseCache()
    results = run_matrix(CASES, W, cache, live=False, provider_specs=[])
    p0 = next(r for r in results if r.name_a == "P0_self_report" and r.axis == "FA")
    p2 = next(r for r in results if r.name_a == "P2_deterministic_internal" and r.axis == "FA")
    assert p0.a_wrong_b_right == p2.a_wrong_b_right == 4
