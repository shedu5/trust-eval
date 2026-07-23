"""The scaled corpus: n independent instances per flagship pattern, and the
combined ladder table built from it. Index 0 of the scaled corpus must be
byte-identical to the original flagship instance (so a filled judge-response
cache stays valid), and every instance must be internally independent and
scored correctly against build_scaled_world's ground truth -- same guarantees
already proven for n=1 in test_study_c.py, now checked at scale.
"""

from trust_eval.study_c.anchors import CLAIM_ANCHOR, ANCHORS, AGREES, CONTRADICTS
from trust_eval.study_c.ladder import build_ladder, format_ladder
from trust_eval.study_c.protocols import decide
from trust_eval.study_c.surrogates import flagship_cases, scaled_cases
from trust_eval.study_c.world import build_flagship_world, build_scaled_world

N = 8
ANCHORED = ("P3_claim_appropriate_anchor", "P4_mandatory_anchor", "P5_hybrid_abstain")


def test_scaled_corpus_size():
    cases = scaled_cases(N)
    assert len(cases) == 10 * N  # 4 execution + 3 authorization + 3 state per instance


def test_scaled_index_zero_matches_original_flagship():
    scaled = scaled_cases(N)[:10]
    original = flagship_cases()
    assert [c.model_dump() for c in scaled] == [c.model_dump() for c in original]


def test_scaled_world_has_no_id_collisions():
    world = build_scaled_world(N)
    # commit ids and exec_result keys must all be distinct (dict construction
    # would have silently overwritten a collision rather than erroring)
    assert len(world.commits) == len(set(world.commits))
    assert len(world.exec_results) == len(set(world.exec_results))
    approval_keys = [(a.task_id, a.scope_exception_file) for a in world.approvals]
    assert len(approval_keys) == len(set(approval_keys))


def test_scaled_anchors_catch_every_new_attack_instance():
    world = build_scaled_world(N)
    cases = scaled_cases(N)
    attacks = [c for c in cases if not c.should_accept and c.label != "unverifiable_false"]
    for c in attacks:
        appropriate = ANCHORS[CLAIM_ANCHOR[c.claim_type]](c, world)
        assert appropriate.verdict == CONTRADICTS, (c.label, c.task_id, appropriate)


def test_scaled_anchored_protocols_zero_false_acceptance():
    world = build_scaled_world(N)
    cases = scaled_cases(N)
    attacks = [c for c in cases if not c.should_accept]
    for p in ANCHORED:
        fa = sum(1 for c in attacks if decide(p, c, world).false_accept(c))
        assert fa == 0, p


def test_scaled_anchored_protocols_no_false_rejection_of_truthful():
    world = build_scaled_world(N)
    cases = scaled_cases(N)
    truthful = [c for c in cases if c.should_accept]
    for p in ANCHORED:
        fr = sum(1 for c in truthful if decide(p, c, world).false_reject(c))
        assert fr == 0, p


def test_scaled_deterministic_protocols_still_accept_every_forgery():
    world = build_scaled_world(N)
    cases = scaled_cases(N)
    attacks = [c for c in cases if not c.should_accept]
    for p in ("P0_self_report", "P2_deterministic_internal"):
        fa = sum(1 for c in attacks if decide(p, c, world).false_accept(c))
        assert fa == len(attacks), p


def test_build_ladder_deterministic_only_has_five_rows():
    world, cases = build_flagship_world(), flagship_cases()
    rows = build_ladder(cases, world)
    assert [r["protocol"] for r in rows] == [
        "P0_self_report", "P2_deterministic_internal",
        "P3_claim_appropriate_anchor", "P4_mandatory_anchor", "P5_hybrid_abstain",
    ]
    # sanity: format_ladder must not raise and must mention every protocol
    table = format_ladder(rows)
    for r in rows:
        assert r["protocol"] in table


def test_build_ladder_ci_bounds_are_sane():
    world, cases = build_scaled_world(N), scaled_cases(N)
    rows = build_ladder(cases, world)
    for r in rows:
        for lo, hi in (r["fa_wilson"], r["fa_cp"], r["fr_wilson"], r["fr_cp"]):
            assert 0.0 <= lo <= hi <= 1.0
