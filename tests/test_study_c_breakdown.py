"""Per-claim-type FA/FR breakdown (offline, scripted judge)."""

from trust_eval.harness.cache import ResponseCache
from trust_eval.study_c.breakdown import by_claim_type
from trust_eval.study_c.surrogates import flagship_cases
from trust_eval.study_c.world import build_flagship_world

W = build_flagship_world()
CASES = flagship_cases()


def test_by_claim_type_splits_flagship_corpus_correctly(tmp_path, monkeypatch):
    # flagship_cases(): execution has 4 (2 attacks: stale_after_drift,
    # unverifiable_false / 2 truthful: benign, near_miss); authorization has 3
    # (1 attack / 2 truthful); state has 3 (1 attack / 2 truthful).
    from trust_eval.harness.providers import ScriptedProvider
    from trust_eval.study_c.llm_review import make_cached_reviewer

    cache = ResponseCache(tmp_path / "r")
    # a judge that accepts everything -- so FA == n_attacks per type, exposing
    # the split without needing real provider specs.
    prov = ScriptedProvider(model="gullible", responder=lambda _p: '{"verdict":"accept","reason":"x"}')
    review = make_cached_reviewer(prov, cache, live=True)

    from trust_eval.study_c.llm_review import run_p1
    from trust_eval.study_c.world import ClaimType

    counts = {}
    for ctype in (ClaimType.EXECUTION, ClaimType.AUTHORIZATION, ClaimType.STATE):
        subset = [c for c in CASES if c.claim_type == ctype]
        s = run_p1(subset, review, W, "scripted", "gullible")
        counts[ctype.value] = (s.n_attacks, s.false_accept, s.n_truthful, s.false_reject)

    assert counts["execution"] == (2, 2, 2, 0)
    assert counts["authorization"] == (1, 1, 2, 0)
    assert counts["state"] == (1, 1, 2, 0)


def test_by_claim_type_helper_matches_manual_split(tmp_path):
    from trust_eval.harness.providers import ScriptedProvider

    cache = ResponseCache(tmp_path / "r")

    # Monkeypatch build_provider indirectly isn't worth it here -- instead
    # verify by_claim_type's row shape and coverage using a real spec would
    # need network; assert instead that it returns exactly 3 rows per
    # provider spec requested, over the three claim types, with no overlap.
    import trust_eval.study_c.breakdown as breakdown_mod

    def fake_build_provider(spec):
        return ScriptedProvider(model=spec, responder=lambda _p: '{"verdict":"reject","reason":"no anchor"}')

    orig = breakdown_mod.build_provider
    breakdown_mod.build_provider = fake_build_provider
    try:
        rows = breakdown_mod.by_claim_type(CASES, W, ["fake:model"], live=True, cache=cache)
    finally:
        breakdown_mod.build_provider = orig

    types_seen = [ctype for _, ctype, _ in rows]
    assert types_seen == ["execution", "authorization", "state"]
    total_cases = sum(s.n_attacks + s.n_truthful for _, _, s in rows)
    assert total_cases == len(CASES)
