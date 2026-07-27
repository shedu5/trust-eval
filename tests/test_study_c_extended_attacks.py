"""Regression tests for the extended attack surface added in direct response
to a third external review's paragraph naming five untested attack classes:
race conditions (TOCTOU), task-to-anchor binding confusion, coordinated
multi-artifact forgery, and forged actor/tool identity. (The fifth, poisoned
approval-ledger content, remains a disclosed limitation -- see docs/full-technical-report.md.)

All deterministic -- no model call, no cache, no network.
"""

from trust_eval.study_c.anchors import ANCHORS, CLAIM_ANCHOR, AGREES, CONTRADICTS
from trust_eval.study_c.coordination_probe import (
    anchored_bundle_decision,
    build_coordination_world,
    coordination_bundles,
    cross_artifact_consistency,
    run_coordination_probe,
)
from trust_eval.study_c.extended_attacks import main as extended_attacks_main
from trust_eval.study_c.protocols import ACCEPT, CANNOT_VERIFY, PROTOCOLS, REJECT, decide
from trust_eval.study_c.world import (
    ClaimType,
    binding_confusion_cases,
    build_binding_confusion_world,
    build_identity_world,
    build_race_condition_world,
    identity_cases,
    race_condition_cases,
)

N = 6


# ---------------------------------------------------------------------------
# Race conditions (TOCTOU)
# ---------------------------------------------------------------------------

def test_race_condition_case_counts_and_labels():
    cases = race_condition_cases(N)
    assert len(cases) == 2 * N
    assert sum(1 for c in cases if c.label == "stale_replay") == N
    assert sum(1 for c in cases if c.label == "honest_current_result") == N
    assert all(c.claim_type == ClaimType.EXECUTION for c in cases)


def test_race_condition_anchor_correctly_contradicts_stale_replay():
    world = build_race_condition_world(N)
    cases = race_condition_cases(N)
    for c in cases:
        res = ANCHORS[CLAIM_ANCHOR[ClaimType.EXECUTION]](c, world)
        assert res.applicable is True
        expected = AGREES if c.should_accept else CONTRADICTS
        assert res.verdict == expected, (c.task_id, c.label, res)


def test_race_condition_anchored_protocols_never_false_accept_or_reject():
    world = build_race_condition_world(N)
    cases = race_condition_cases(N)
    for protocol in ("P3_claim_appropriate_anchor", "P4_mandatory_anchor", "P5_hybrid_abstain"):
        for c in cases:
            d = decide(protocol, c, world)
            assert not d.false_accept(c), (protocol, c.task_id)
            assert not d.false_reject(c), (protocol, c.task_id)
            assert d.outcome != CANNOT_VERIFY  # a fresh, applicable anchor decides every case here


def test_race_condition_naive_protocols_false_accept_the_replay():
    world = build_race_condition_world(N)
    cases = race_condition_cases(N)
    attacks = [c for c in cases if not c.should_accept]
    for protocol in ("P0_self_report", "P2_deterministic_internal"):
        assert all(decide(protocol, c, world).false_accept(c) for c in attacks)


# ---------------------------------------------------------------------------
# Task-to-anchor binding confusion
# ---------------------------------------------------------------------------

def test_binding_confusion_case_counts_and_labels():
    cases = binding_confusion_cases(N)
    assert len(cases) == 2 * N
    assert sum(1 for c in cases if c.label == "borrowed_approval") == N
    assert sum(1 for c in cases if c.label == "correctly_bound_approval") == N
    assert all(c.claim_type == ClaimType.AUTHORIZATION for c in cases)


def test_binding_confusion_anchor_rejects_borrowed_approval():
    world = build_binding_confusion_world(N)
    cases = binding_confusion_cases(N)
    for c in cases:
        res = ANCHORS[CLAIM_ANCHOR[ClaimType.AUTHORIZATION]](c, world)
        assert res.applicable is True
        expected = AGREES if c.should_accept else CONTRADICTS
        assert res.verdict == expected, (c.task_id, c.label, res)


def test_binding_confusion_anchored_protocols_never_false_accept_or_reject():
    world = build_binding_confusion_world(N)
    cases = binding_confusion_cases(N)
    for protocol in ("P3_claim_appropriate_anchor", "P4_mandatory_anchor", "P5_hybrid_abstain"):
        for c in cases:
            d = decide(protocol, c, world)
            assert not d.false_accept(c), (protocol, c.task_id)
            assert not d.false_reject(c), (protocol, c.task_id)


# ---------------------------------------------------------------------------
# Forged actor/tool identity
# ---------------------------------------------------------------------------

def test_identity_claim_type_exists_and_dispatches():
    assert ClaimType.IDENTITY.value == "identity"
    assert CLAIM_ANCHOR[ClaimType.IDENTITY] == "actor_identity"
    assert "actor_identity" in ANCHORS


def test_identity_case_counts_and_labels():
    cases = identity_cases(N)
    assert len(cases) == 2 * N
    assert sum(1 for c in cases if c.label == "forged_identity") == N
    assert sum(1 for c in cases if c.label == "correct_identity") == N
    assert all(c.claim_type == ClaimType.IDENTITY for c in cases)


def test_identity_anchor_correctly_distinguishes_forged_from_correct():
    world = build_identity_world(N)
    cases = identity_cases(N)
    for c in cases:
        res = ANCHORS["actor_identity"](c, world)
        assert res.applicable is True
        expected = AGREES if c.should_accept else CONTRADICTS
        assert res.verdict == expected, (c.task_id, c.label, res)


def test_identity_anchor_inconclusive_when_no_actor_recorded():
    world = build_identity_world(N)
    from trust_eval.study_c.world import Claim
    orphan = Claim(task_id="no-such-task", claim_type=ClaimType.IDENTITY,
                   payload={"asserted_actor": "someone"}, label="orphan", should_accept=False)
    res = ANCHORS["actor_identity"](orphan, world)
    assert res.applicable is True
    assert res.verdict not in (AGREES, CONTRADICTS)  # inconclusive


def test_identity_deterministic_protocols_full_ladder_behaves_as_predicted():
    world = build_identity_world(N)
    cases = identity_cases(N)
    for protocol in ("P0_self_report", "P2_deterministic_internal"):
        attacks = [c for c in cases if not c.should_accept]
        assert all(decide(protocol, c, world).false_accept(c) for c in attacks)
    for protocol in ("P3_claim_appropriate_anchor", "P4_mandatory_anchor", "P5_hybrid_abstain"):
        for c in cases:
            d = decide(protocol, c, world)
            assert not d.false_accept(c)
            assert not d.false_reject(c)


def test_extended_attacks_cli_runs_clean_for_all_three():
    assert extended_attacks_main(["--n", "3", "--which", "all"]) == 0
    assert extended_attacks_main(["--n", "3", "--which", "race"]) == 0
    assert extended_attacks_main(["--n", "3", "--which", "binding"]) == 0
    assert extended_attacks_main(["--n", "3", "--which", "identity"]) == 0


# ---------------------------------------------------------------------------
# Coordinated multi-artifact forgery
# ---------------------------------------------------------------------------

def test_coordination_bundle_counts_and_claim_shape():
    bundles = coordination_bundles(N)
    assert len(bundles) == 2 * N
    forged = [b for b in bundles if not b.should_accept]
    honest = [b for b in bundles if b.should_accept]
    assert len(forged) == N and len(honest) == N
    for b in bundles:
        assert len(b.claims) == 2
        types = {c.claim_type for c in b.claims}
        assert types == {ClaimType.EXECUTION, ClaimType.STATE}


def test_coordinated_bundle_claims_share_a_commit_reference():
    """The whole point of 'coordinated' -- both artifacts in a forged bundle
    cite the identical fabricated reference, exactly as a real honest
    bundle's two artifacts would agree with each other."""
    bundles = coordination_bundles(N)
    for b in bundles:
        refs = {c.payload.get("commit_ref") for c in b.claims}
        assert len(refs) == 1, (b.task_id, refs)


def test_cross_artifact_consistency_is_fooled_by_every_coordinated_bundle():
    bundles = coordination_bundles(N)
    forged = [b for b in bundles if not b.should_accept]
    assert all(cross_artifact_consistency(b) for b in forged)  # FA on every one


def test_cross_artifact_consistency_correctly_accepts_honest_bundles():
    bundles = coordination_bundles(N)
    honest = [b for b in bundles if b.should_accept]
    assert all(cross_artifact_consistency(b) for b in honest)


def test_anchored_per_claim_decision_is_never_fooled_by_coordination():
    world = build_coordination_world(N)
    bundles = coordination_bundles(N)
    forged = [b for b in bundles if not b.should_accept]
    honest = [b for b in bundles if b.should_accept]
    assert all(not anchored_bundle_decision(b, world) for b in forged)
    assert all(anchored_bundle_decision(b, world) for b in honest)


def test_run_coordination_probe_matches_the_predicted_asymmetry():
    world = build_coordination_world(N)
    bundles = coordination_bundles(N)
    r = run_coordination_probe(bundles, world)
    assert r["cross_fa"] == N       # naive checker: fooled every time
    assert r["cross_fr"] == 0
    assert r["anchored_fa"] == 0    # per-claim anchoring: never fooled
    assert r["anchored_fr"] == 0
