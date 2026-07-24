"""The P4/P5 probe: genuinely anchor-inconclusive AUTHORIZATION and STATE
cases (the principal n=100 corpus only has this for EXECUTION, via
`unverifiable_false`). Exploratory, separate from the confirmatory corpus --
these tests only need to prove the anchor logic and protocol wiring are
correct; the live-judge numbers themselves are measured, not asserted here.
"""

from trust_eval.study_c.anchors import ANCHORS, CLAIM_ANCHOR, INCONCLUSIVE
from trust_eval.study_c.p4p5_probe import p4p5_probe_cases, run_probe
from trust_eval.study_c.protocols import Decision, decide
from trust_eval.study_c.world import ClaimType, build_p4p5_probe_world

N = 6
W = build_p4p5_probe_world(N)
CASES = p4p5_probe_cases(N)


def test_probe_case_counts_and_labels():
    auth = [c for c in CASES if c.claim_type == ClaimType.AUTHORIZATION]
    state = [c for c in CASES if c.claim_type == ClaimType.STATE]
    assert len(auth) == N
    assert len(state) == N
    assert all(c.label == "conflicting_ledger_entry" for c in auth)
    assert all(c.label == "baseline_unrecorded" for c in state)
    assert all(not c.should_accept for c in CASES)  # neither pattern is trustworthy evidence


def test_approval_ledger_anchor_is_inconclusive_for_conflicting_entries():
    auth = next(c for c in CASES if c.claim_type == ClaimType.AUTHORIZATION)
    res = ANCHORS[CLAIM_ANCHOR[ClaimType.AUTHORIZATION]](auth, W)
    assert res.applicable is True
    assert res.verdict == INCONCLUSIVE


def test_repo_baseline_anchor_is_inconclusive_when_baseline_unrecorded():
    state = next(c for c in CASES if c.claim_type == ClaimType.STATE)
    res = ANCHORS[CLAIM_ANCHOR[ClaimType.STATE]](state, W)
    assert res.applicable is True
    assert res.verdict == INCONCLUSIVE


def test_p3_rejects_inconclusive_cases_p4_and_p5_abstain():
    for c in CASES:
        assert decide("P3_claim_appropriate_anchor", c, W).outcome == "reject"
        assert decide("P4_mandatory_anchor", c, W).outcome == "cannot_verify"
        assert decide("P5_hybrid_abstain", c, W).outcome == "cannot_verify"


def test_probe_deterministic_protocols_never_false_accept():
    for protocol in ("P3_claim_appropriate_anchor", "P4_mandatory_anchor", "P5_hybrid_abstain"):
        for row in run_probe(CASES, W, protocol):
            assert row.fa == 0, (protocol, row.claim_type, row.fa)
            assert row.errors == 0


def _scripted(outcome):
    return lambda claim, world: Decision(protocol="adjudicator", outcome=outcome, detail="scripted")


def test_probe_hybrid_p5_diverges_from_p4_with_a_gullible_adjudicator():
    rows_p4 = {r.claim_type: r for r in run_probe(CASES, W, "P4_mandatory_anchor")}
    rows_p5_hybrid = {r.claim_type: r
                      for r in run_probe(CASES, W, "P5_hybrid_abstain", adjudicator=_scripted("accept"))}
    for ctype in ("authorization", "state"):
        assert rows_p4[ctype].fa == 0
        assert rows_p5_hybrid[ctype].fa == N   # every case: anchor inconclusive -> adjudicator accepts -> FA


def test_probe_hybrid_p5_matches_p4_with_a_skeptical_adjudicator():
    rows_p5_hybrid = run_probe(CASES, W, "P5_hybrid_abstain", adjudicator=_scripted("reject"))
    assert all(r.fa == 0 for r in rows_p5_hybrid)


def test_probe_adjudicator_cache_miss_is_counted_as_an_error_not_a_silent_zero():
    """Same failure mode fixed in ladder.py: an adjudicator that was never
    actually asked (e.g. a 'missing' cache-miss outcome) must be counted as
    an error, not silently treated as a clean non-acceptance."""
    rows = run_probe(CASES, W, "P5_hybrid_abstain", adjudicator=_scripted("missing"))
    for r in rows:
        assert r.fa == 0
        assert r.errors == N
