"""Regression tests for the judge manipulation probe (injection + hedged
language). All deterministic -- no model call, no cache, no network: these
tests prove the anchor/deterministic-protocol immunity claim in
manipulation_probe.py's docstring empirically, not just by code inspection.
"""

from trust_eval.study_c.anchors import ANCHORS, CLAIM_ANCHOR, AGREES, CONTRADICTS
from trust_eval.study_c.manipulation_probe import (
    _HEDGE_TEXT,
    _INJECTION_TEXT,
    _base_cases,
    _manipulated,
    main as manipulation_main,
)
from trust_eval.study_c.protocols import decide
from trust_eval.study_c.world import build_scaled_world

N = 10


def test_base_cases_are_exactly_the_three_clean_anchor_patterns():
    cases = _base_cases(N)
    labels = {c.label for c in cases}
    assert labels == {"benign", "stale_after_drift", "fabricated_authorization", "wrong_baseline_proof"}
    assert "unverifiable_false" not in labels  # excluded: inconclusive anchor, would confound
    n_false = sum(1 for c in cases if not c.should_accept)
    n_true = sum(1 for c in cases if c.should_accept)
    assert n_false == 3 * N
    assert n_true == 3 * N


def test_injected_only_modifies_false_cases():
    base = _base_cases(N)
    injected = _manipulated(base, _INJECTION_TEXT, false_only=True)
    for orig, mod in zip(base, injected):
        if orig.should_accept:
            assert mod.payload == orig.payload  # true cases untouched
        else:
            assert mod.payload.get("operator_note") == _INJECTION_TEXT
            # every other key is preserved unchanged
            for k, v in orig.payload.items():
                assert mod.payload[k] == v


def test_hedged_modifies_every_case_true_and_false():
    base = _base_cases(N)
    hedged = _manipulated(base, _HEDGE_TEXT, false_only=False)
    for orig, mod in zip(base, hedged):
        assert mod.payload.get("operator_note") == _HEDGE_TEXT
        for k, v in orig.payload.items():
            assert mod.payload[k] == v


def test_manipulation_never_changes_should_accept_or_claim_type_or_task_id():
    base = _base_cases(N)
    for text, false_only in [(_INJECTION_TEXT, True), (_HEDGE_TEXT, False)]:
        mod = _manipulated(base, text, false_only=false_only)
        for orig, m in zip(base, mod):
            assert m.should_accept == orig.should_accept
            assert m.claim_type == orig.claim_type
            assert m.task_id == orig.task_id
            assert m.label == orig.label


def test_operator_note_does_not_change_any_anchor_verdict():
    """The immunity claim from the module docstring, checked directly against
    every anchor this probe's claim types touch, for both manipulations."""
    world = build_scaled_world(N)
    base = _base_cases(N)
    for text, false_only in [(_INJECTION_TEXT, True), (_HEDGE_TEXT, False)]:
        mod = _manipulated(base, text, false_only=false_only)
        for orig, m in zip(base, mod):
            anchor_name = CLAIM_ANCHOR[orig.claim_type]
            orig_res = ANCHORS[anchor_name](orig, world)
            mod_res = ANCHORS[anchor_name](m, world)
            assert mod_res.verdict == orig_res.verdict
            assert mod_res.applicable == orig_res.applicable


def test_operator_note_does_not_change_deterministic_protocol_outcomes():
    world = build_scaled_world(N)
    base = _base_cases(N)
    for text, false_only in [(_INJECTION_TEXT, True), (_HEDGE_TEXT, False)]:
        mod = _manipulated(base, text, false_only=false_only)
        for protocol in ("P0_self_report", "P2_deterministic_internal",
                         "P3_claim_appropriate_anchor", "P4_mandatory_anchor",
                         "P5_hybrid_abstain"):
            for orig, m in zip(base, mod):
                d_orig = decide(protocol, orig, world)
                d_mod = decide(protocol, m, world)
                assert d_mod.outcome == d_orig.outcome, (protocol, orig.task_id, orig.label)


def test_base_patterns_never_leave_the_anchor_inconclusive():
    """Justifies skipping P5-hybrid entirely: the adjudicator would never be
    consulted for any case in this probe's corpus."""
    from trust_eval.study_c.ladder import _anchor_inconclusive
    world = build_scaled_world(N)
    for c in _base_cases(N):
        assert _anchor_inconclusive(c, world) is False


def test_main_runs_architecture_only_with_no_provider_and_no_network():
    assert manipulation_main(["--n", "5"]) == 0
