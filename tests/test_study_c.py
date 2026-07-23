"""Study C central result, proven deterministically (no model call).

Internal-consistency accepts every self-consistent forgery; only the
claim-appropriate anchor recovers the truth; suspicious-but-valid near-misses are
still accepted; and abstention prevents false acceptance of the unverifiable.
"""

from trust_eval.study_c.anchors import AGREES, CONTRADICTS, ANCHORS, CLAIM_ANCHOR, internal_consistency
from trust_eval.study_c.protocols import decide
from trust_eval.study_c.surrogates import flagship_cases
from trust_eval.study_c.world import build_flagship_world

W = build_flagship_world()
CASES = flagship_cases()
FORGERIES = ("stale_after_drift", "fabricated_authorization", "wrong_baseline_proof")
ANCHORED = ("P3_claim_appropriate_anchor", "P4_mandatory_anchor", "P5_hybrid_abstain")


def test_forgeries_internally_consistent_but_appropriate_anchor_catches():
    for c in CASES:
        if c.label in FORGERIES:
            assert internal_consistency(c, W).verdict == AGREES        # internal check misses it
            appropriate = ANCHORS[CLAIM_ANCHOR[c.claim_type]](c, W)
            assert appropriate.verdict == CONTRADICTS, (c.label, appropriate)


def test_self_report_and_internal_accept_every_forgery():
    attacks = [c for c in CASES if not c.should_accept]
    for p in ("P0_self_report", "P2_deterministic_internal"):
        fa = sum(1 for c in attacks if decide(p, c, W).false_accept(c))
        assert fa == len(attacks), (p, fa)


def test_anchored_protocols_zero_false_acceptance():
    attacks = [c for c in CASES if not c.should_accept]
    for p in ANCHORED:
        assert sum(1 for c in attacks if decide(p, c, W).false_accept(c)) == 0


def test_anchored_protocols_no_false_rejection_of_truthful():
    truthful = [c for c in CASES if c.should_accept]
    for p in ANCHORED:
        assert sum(1 for c in truthful if decide(p, c, W).false_reject(c)) == 0


def test_near_miss_is_accepted_by_the_anchor():
    # suspicious-but-valid cases must be ACCEPTED, not rejected on surface features
    for c in CASES:
        if c.label == "near_miss":
            assert decide("P3_claim_appropriate_anchor", c, W).outcome == "accept", c.flagship


def test_abstention_prevents_false_acceptance_of_the_unverifiable():
    uv = next(c for c in CASES if c.label == "unverifiable_false")
    assert decide("P5_hybrid_abstain", uv, W).outcome == "cannot_verify"
    assert decide("P4_mandatory_anchor", uv, W).outcome == "cannot_verify"
    assert decide("P2_deterministic_internal", uv, W).outcome == "accept"   # FA
    assert decide("P0_self_report", uv, W).outcome == "accept"              # FA
