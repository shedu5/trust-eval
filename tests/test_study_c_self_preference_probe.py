"""Regression tests for the self-preference / in-group bias probe. All
deterministic -- no model call, no cache, no network: these prove the
`executor_model` field is inert to every anchor and deterministic protocol,
the same immunity guarantee `manipulation_probe.py` requires for its own
free-text field, checked independently here since this module adds the
field to EVERY case (not just false ones).
"""

from trust_eval.study_c.anchors import ANCHORS, CLAIM_ANCHOR
from trust_eval.study_c.protocols import decide
from trust_eval.study_c.self_preference_probe import (
    _FAMILY_LABEL,
    _attributed,
    _base_cases,
    main as self_preference_main,
)
from trust_eval.study_c.world import build_scaled_world

N = 10


def test_base_cases_match_manipulation_probes_corpus():
    """Both new probes are meant to compare against the exact same base
    facts -- if these ever drift apart the two results stop being
    comparable in the write-up."""
    from trust_eval.study_c.manipulation_probe import _base_cases as _mp_base_cases
    a = _base_cases(N)
    b = _mp_base_cases(N)
    assert [(c.task_id, c.label, c.payload) for c in a] == [(c.task_id, c.label, c.payload) for c in b]


def test_attributed_adds_executor_model_to_every_case():
    base = _base_cases(N)
    for _, label in _FAMILY_LABEL.items():
        attributed = _attributed(base, label)
        assert len(attributed) == len(base)
        for orig, mod in zip(base, attributed):
            assert mod.payload.get("executor_model") == label
            assert mod.should_accept == orig.should_accept
            assert mod.claim_type == orig.claim_type
            for k, v in orig.payload.items():
                assert mod.payload[k] == v


def test_gemini_and_deepseek_attributed_corpora_differ_only_in_that_one_field():
    base = _base_cases(N)
    gemini = _attributed(base, "Gemini")
    deepseek = _attributed(base, "DeepSeek")
    for g, d in zip(gemini, deepseek):
        assert g.payload["executor_model"] != d.payload["executor_model"]
        g_rest = {k: v for k, v in g.payload.items() if k != "executor_model"}
        d_rest = {k: v for k, v in d.payload.items() if k != "executor_model"}
        assert g_rest == d_rest


def test_executor_model_does_not_change_any_anchor_verdict():
    world = build_scaled_world(N)
    base = _base_cases(N)
    for _, label in _FAMILY_LABEL.items():
        attributed = _attributed(base, label)
        for orig, mod in zip(base, attributed):
            anchor_name = CLAIM_ANCHOR[orig.claim_type]
            orig_res = ANCHORS[anchor_name](orig, world)
            mod_res = ANCHORS[anchor_name](mod, world)
            assert mod_res.verdict == orig_res.verdict
            assert mod_res.applicable == orig_res.applicable


def test_executor_model_does_not_change_deterministic_protocol_outcomes():
    world = build_scaled_world(N)
    base = _base_cases(N)
    for _, label in _FAMILY_LABEL.items():
        attributed = _attributed(base, label)
        for protocol in ("P0_self_report", "P2_deterministic_internal",
                         "P3_claim_appropriate_anchor", "P4_mandatory_anchor",
                         "P5_hybrid_abstain"):
            for orig, mod in zip(base, attributed):
                d_orig = decide(protocol, orig, world)
                d_mod = decide(protocol, mod, world)
                assert d_mod.outcome == d_orig.outcome, (protocol, orig.task_id, orig.label)


def test_main_runs_architecture_only_with_no_provider_and_no_network():
    assert self_preference_main(["--n", "5"]) == 0
