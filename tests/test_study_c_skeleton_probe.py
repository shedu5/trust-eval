"""Regression tests for the structural-skeleton evidence surface, added in
direct response to a fifth external review proposing a Repomix-style
structural skeleton as a new lossy evidence position between P1 (text-only
narrative) and P3 (full claim-matched anchoring).

All deterministic -- no model call, no cache, no network.
"""

from trust_eval.study_c.anchors import ANCHORS, CLAIM_ANCHOR, AGREES, CONTRADICTS, INCONCLUSIVE
from trust_eval.study_c.protocols import ACCEPT, CANNOT_VERIFY, REJECT, decide
from trust_eval.study_c.skeleton_probe import (
    build_skeleton_execution_world,
    main as skeleton_probe_main,
    run_skeleton_execution_probe,
    skeleton_execution_bundles,
    skeleton_only_decision,
    skeleton_plus_execution_decision,
)
from trust_eval.study_c.world import (
    Claim,
    ClaimType,
    build_structural_skeleton_world,
    structural_skeleton_cases,
)

N = 6


# ---------------------------------------------------------------------------
# Single-claim ladder: four falsification conditions + baseline
# ---------------------------------------------------------------------------

def test_structure_claim_type_exists_and_dispatches():
    assert ClaimType.STRUCTURE.value == "structure"
    assert CLAIM_ANCHOR[ClaimType.STRUCTURE] == "structural_skeleton"
    assert "structural_skeleton" in ANCHORS


def test_skeleton_case_counts_and_labels():
    cases = structural_skeleton_cases(N)
    assert len(cases) == 5 * N
    labels = {
        "current_truthful_skeleton": (N, True),
        "stale_skeleton_hides_regression": (N, False),
        "misbound_skeleton": (N, False),
        "executor_supplied_false": (N, False),
        "executor_supplied_true": (N, True),
    }
    for label, (count, should_accept) in labels.items():
        matching = [c for c in cases if c.label == label]
        assert len(matching) == count, label
        assert all(c.should_accept == should_accept for c in matching), label
    assert all(c.claim_type == ClaimType.STRUCTURE for c in cases)


def test_current_truthful_skeleton_agrees():
    world = build_structural_skeleton_world(N)
    cases = [c for c in structural_skeleton_cases(N) if c.label == "current_truthful_skeleton"]
    for c in cases:
        res = ANCHORS["structural_skeleton"](c, world)
        assert res.applicable is True
        assert res.verdict == AGREES, (c.task_id, res)


def test_stale_skeleton_is_inconclusive_not_contradicts():
    """A stale skeleton was honestly generated -- it just can't establish
    anything about the CURRENT head. Distinct from CONTRADICTS."""
    world = build_structural_skeleton_world(N)
    cases = [c for c in structural_skeleton_cases(N) if c.label == "stale_skeleton_hides_regression"]
    for c in cases:
        res = ANCHORS["structural_skeleton"](c, world)
        assert res.applicable is True
        assert res.verdict == INCONCLUSIVE, (c.task_id, res)
        assert "stale" in res.detail


def test_misbound_skeleton_contradicts():
    world = build_structural_skeleton_world(N)
    cases = [c for c in structural_skeleton_cases(N) if c.label == "misbound_skeleton"]
    for c in cases:
        res = ANCHORS["structural_skeleton"](c, world)
        assert res.applicable is True
        assert res.verdict == CONTRADICTS, (c.task_id, res)


def test_executor_supplied_is_always_inconclusive_regardless_of_truth():
    """Provenance is checked before content -- an executor-supplied
    skeleton is inconclusive whether it lies (executor_supplied_false) or
    happens to be accurate (executor_supplied_true)."""
    world = build_structural_skeleton_world(N)
    cases = [c for c in structural_skeleton_cases(N)
             if c.label in ("executor_supplied_false", "executor_supplied_true")]
    assert len(cases) == 2 * N
    for c in cases:
        res = ANCHORS["structural_skeleton"](c, world)
        assert res.applicable is True
        assert res.verdict == INCONCLUSIVE, (c.task_id, c.label, res)


def test_p3_false_rejects_the_accurate_executor_supplied_claim():
    """The disclosed cost of distrusting provenance outright: P3
    (anchor-or-reject) REJECTS executor_supplied_true even though it is
    ground-truth accurate -- a genuine false reject, not just a missed
    false accept elsewhere."""
    world = build_structural_skeleton_world(N)
    cases = [c for c in structural_skeleton_cases(N) if c.label == "executor_supplied_true"]
    for c in cases:
        d = decide("P3_claim_appropriate_anchor", c, world)
        assert d.outcome == REJECT
        assert d.false_reject(c)


def test_p4_p5_abstain_rather_than_false_reject_the_same_claim():
    """P4/P5's abstain-on-inconclusive design pays no false-reject cost
    here where P3's reject-by-default does -- exactly the P3-vs-P4/P5
    distinction this study's own vocabulary predicts."""
    world = build_structural_skeleton_world(N)
    cases = [c for c in structural_skeleton_cases(N) if c.label == "executor_supplied_true"]
    for protocol in ("P4_mandatory_anchor", "P5_hybrid_abstain"):
        for c in cases:
            d = decide(protocol, c, world)
            assert d.outcome == CANNOT_VERIFY
            assert not d.false_reject(c)


def test_naive_protocols_false_accept_every_structural_attack():
    world = build_structural_skeleton_world(N)
    cases = structural_skeleton_cases(N)
    attacks = [c for c in cases
               if not c.should_accept and c.label != "executor_supplied_false"]
    # executor_supplied_false is also caught (inconclusive) by anchored
    # protocols, but P0/P2 never consult the anchor at all -- assert the
    # broader claim across ALL attack labels including that one.
    all_attacks = [c for c in cases if not c.should_accept]
    for protocol in ("P0_self_report", "P2_deterministic_internal"):
        assert all(decide(protocol, c, world).false_accept(c) for c in all_attacks)


def test_anchored_protocols_never_false_accept_any_structural_attack():
    world = build_structural_skeleton_world(N)
    cases = structural_skeleton_cases(N)
    attacks = [c for c in cases if not c.should_accept]
    for protocol in ("P3_claim_appropriate_anchor", "P4_mandatory_anchor", "P5_hybrid_abstain"):
        for c in attacks:
            d = decide(protocol, c, world)
            assert not d.false_accept(c), (protocol, c.task_id, c.label)


def test_skeleton_probe_cli_runs_clean():
    assert skeleton_probe_main(["--n", "3", "--which", "all"]) == 0
    assert skeleton_probe_main(["--n", "3", "--which", "ladder"]) == 0
    assert skeleton_probe_main(["--n", "3", "--which", "composite"]) == 0


# ---------------------------------------------------------------------------
# Composite: structural skeleton + claim-matched execution anchor
# ---------------------------------------------------------------------------

def test_composite_bundle_shape():
    bundles = skeleton_execution_bundles(N)
    assert len(bundles) == N
    for b in bundles:
        assert len(b.claims) == 2
        types = {c.claim_type for c in b.claims}
        assert types == {ClaimType.STRUCTURE, ClaimType.EXECUTION}


def test_skeleton_only_is_fooled_by_wired_but_broken_bundles():
    """The structural skeleton is identical (and correct) in both bundle
    variants -- skeleton_only cannot see the runtime brokenness, so it
    ACCEPTs every 'wired but broken' bundle: a false accept by
    construction, demonstrating the reviewer's point that structure alone
    'cannot establish that the behavior executes... or passed'."""
    world = build_skeleton_execution_world(N)
    bundles = skeleton_execution_bundles(N)
    broken = [b for b in bundles if not b.should_accept]
    assert broken, "expected at least one wired-but-broken bundle"
    assert all(skeleton_only_decision(b, world) for b in broken)


def test_skeleton_plus_execution_is_never_fooled():
    world = build_skeleton_execution_world(N)
    bundles = skeleton_execution_bundles(N)
    broken = [b for b in bundles if not b.should_accept]
    working = [b for b in bundles if b.should_accept]
    assert broken and working
    assert all(not skeleton_plus_execution_decision(b, world) for b in broken)
    assert all(skeleton_plus_execution_decision(b, world) for b in working)


def test_run_skeleton_execution_probe_matches_predicted_asymmetry():
    world = build_skeleton_execution_world(N)
    bundles = skeleton_execution_bundles(N)
    r = run_skeleton_execution_probe(bundles, world)
    assert r["skel_fa"] == r["n_attacks"]   # skeleton alone: fooled every time
    assert r["skel_fr"] == 0
    assert r["comb_fa"] == 0                # skeleton + execution: never fooled
    assert r["comb_fr"] == 0
