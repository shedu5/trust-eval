"""The P4/P5 probe: genuinely anchor-inconclusive AUTHORIZATION and STATE
cases (the principal n=100 corpus only has this for EXECUTION, via
`unverifiable_false`). Exploratory, separate from the confirmatory corpus --
these tests only need to prove the anchor logic and protocol wiring are
correct; the live-judge numbers themselves are measured, not asserted here.
"""

from trust_eval.study_c.anchors import ANCHORS, CLAIM_ANCHOR, INCONCLUSIVE
from trust_eval.study_c.p4p5_probe import (
    balanced_probe_cases,
    p4p5_probe_cases,
    run_balanced_probe,
    run_probe,
)
from trust_eval.study_c.protocols import Decision, decide
from trust_eval.study_c.world import ClaimType, build_balanced_probe_world, build_p4p5_probe_world

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


def test_probe_p3_has_full_coverage_p4_and_plain_p5_have_zero_coverage():
    """Every case in this probe is anchor-inconclusive by construction: P3
    rejects all of them (100% coverage, 0 abstention), while P4 and plain P5
    abstain on all of them (0% coverage) -- the starkest version of the
    coverage/abstention distinction this probe exists to demonstrate."""
    for row in run_probe(CASES, W, "P3_claim_appropriate_anchor"):
        assert row.abstain == 0
        assert row.coverage == 1.0
        assert row.selective_fa == 0.0
    for protocol in ("P4_mandatory_anchor", "P5_hybrid_abstain"):
        for row in run_probe(CASES, W, protocol):
            assert row.abstain == N
            assert row.coverage == 0.0
            assert row.selective_fa is None


def test_probe_hybrid_coverage_reflects_adjudicator_resolution():
    rows = run_probe(CASES, W, "P5_hybrid_abstain", adjudicator=_scripted("accept"))
    for row in rows:
        assert row.abstain == 0
        assert row.coverage == 1.0
        assert row.selective_fa == 1.0   # every decided case was a false accept


# ---------------------------------------------------------------------------
# Balanced true/false anchor-inconclusive probe -- answers the gap an
# external review correctly flagged: p4p5_probe_cases (above) and the
# principal corpus's `unverifiable_false` pattern only ever test FALSE
# anchor-inconclusive claims, so a protocol that rejects/abstains on every
# one of them looks flawless without ever being tested on a truthful one.
# ---------------------------------------------------------------------------

NB = 5
WB = build_balanced_probe_world(NB)
BAL_CASES = balanced_probe_cases(NB)


def test_balanced_probe_case_counts_and_labels():
    for ctype in (ClaimType.EXECUTION, ClaimType.AUTHORIZATION, ClaimType.STATE):
        of_type = [c for c in BAL_CASES if c.claim_type == ctype]
        assert len(of_type) == 2 * NB
        assert sum(1 for c in of_type if c.should_accept) == NB
        assert sum(1 for c in of_type if not c.should_accept) == NB


def test_balanced_probe_anchor_is_inconclusive_for_both_true_and_false():
    """The whole point: the anchor cannot tell true from false apart on
    these cases -- INCONCLUSIVE regardless of should_accept."""
    for c in BAL_CASES:
        name = CLAIM_ANCHOR[c.claim_type]
        res = ANCHORS[name](c, WB)
        assert res.applicable is True
        assert res.verdict == INCONCLUSIVE, (c.task_id, c.should_accept, res)


def test_p3_false_rejects_every_truthful_anchor_inconclusive_case():
    """This is the regression test for the gap itself: P3's reject-on-
    inconclusive policy, which looked flawless (0 errors, 100% coverage) in
    every prior corpus because those corpora had no truthful anchor-
    inconclusive case, false-rejects ALL of them here. P3 is a policy, not
    an oracle."""
    truthful = [c for c in BAL_CASES if c.should_accept]
    assert len(truthful) == 3 * NB
    for c in truthful:
        d = decide("P3_claim_appropriate_anchor", c, WB)
        assert d.outcome == "reject"
        assert d.false_reject(c)


def test_p4_and_plain_p5_abstain_on_every_case_regardless_of_truth():
    """P4/plain-P5 pay for zero FA and zero FR with 0% coverage on BOTH
    sides now, not just on the (previously untested) false side."""
    for protocol in ("P4_mandatory_anchor", "P5_hybrid_abstain"):
        for row in run_balanced_probe(BAL_CASES, WB, protocol):
            assert row.ta == row.fa == row.fr == row.tr == 0
            assert row.abstain_false == row.n_false
            assert row.abstain_true == row.n_true
            assert row.coverage_false == 0.0
            assert row.coverage_true == 0.0


def test_p3_never_abstains_full_coverage_both_sides():
    for row in run_balanced_probe(BAL_CASES, WB, "P3_claim_appropriate_anchor"):
        assert row.abstain_false == 0
        assert row.abstain_true == 0
        assert row.coverage_false == 1.0
        assert row.coverage_true == 1.0
        assert row.fa == 0            # never falsely accepts (it never accepts at all here)
        assert row.fr == row.n_true   # but false-rejects every truthful case
        assert row.selective_fr == 1.0


def test_balanced_hybrid_gullible_adjudicator_trades_fr_for_fa():
    """A hybrid that always accepts recovers all the coverage P3/P4 give up
    on the true side (TA = n_true, FR = 0) but pays for it in full on the
    false side (FA = n_false) -- the coverage-risk trade the probe exists to
    make visible, with real hidden-ground-truth scoring instead of an
    assumption."""
    rows = run_balanced_probe(BAL_CASES, WB, "P5_hybrid_abstain",
                              adjudicator=_scripted("accept"))
    for row in rows:
        assert row.ta == row.n_true
        assert row.fr == 0
        assert row.fa == row.n_false
        assert row.tr == 0
        assert row.coverage_false == 1.0
        assert row.coverage_true == 1.0


def test_balanced_hybrid_skeptical_adjudicator_matches_p3_exactly():
    """A hybrid that always rejects is behaviorally identical to P3 on this
    probe: zero FA, but false-rejects every truthful inconclusive case."""
    rows = run_balanced_probe(BAL_CASES, WB, "P5_hybrid_abstain",
                              adjudicator=_scripted("reject"))
    for row in rows:
        assert row.fa == 0
        assert row.fr == row.n_true
        assert row.tr == row.n_false
        assert row.ta == 0


def test_balanced_probe_adjudicator_cache_miss_is_counted_as_error_on_correct_side():
    rows = run_balanced_probe(BAL_CASES, WB, "P5_hybrid_abstain",
                              adjudicator=_scripted("missing"))
    for row in rows:
        assert row.errors_false == row.n_false
        assert row.errors_true == row.n_true
        assert row.fa == row.fr == row.ta == row.tr == 0
