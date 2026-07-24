"""Smoke tests for the new --provider/--live/--p5-adjudicator wiring added
to extended_attacks.py, coordination_probe.py, and skeleton_probe.py this
round (needed so Phase 0's cost probe can touch every judge-calling
surface, including the three that had none before). Uses `scripted:*`
provider specs (ScriptedProvider, offline, deterministic) -- no network,
no key -- to confirm the CLI plumbing and the v2 prompt/cache wiring
actually execute end to end, not just that the deterministic protocols
still work (those are already covered by each module's original tests).
"""

from trust_eval.study_c.coordination_probe import main as coordination_main
from trust_eval.study_c.extended_attacks import main as extended_attacks_main
from trust_eval.study_c.llm_review import PROMPT_VERSION_2
from trust_eval.study_c.skeleton_probe import main as skeleton_probe_main


def test_extended_attacks_accepts_scripted_provider_and_p5_adjudicator():
    rc = extended_attacks_main(["--n", "2", "--which", "identity",
                               "--provider", "scripted:stub",
                               "--p5-adjudicator", "scripted:stub", "--live"])
    assert rc == 0


def test_coordination_probe_accepts_scripted_provider():
    rc = coordination_main(["--n", "2", "--provider", "scripted:stub", "--live"])
    assert rc == 0


def test_skeleton_probe_accepts_scripted_provider_for_ladder_and_composite():
    rc = skeleton_probe_main(["--n", "2", "--which", "all",
                             "--provider", "scripted:stub",
                             "--p5-adjudicator", "scripted:stub", "--live"])
    assert rc == 0


def test_scripted_provider_default_reject_all_produces_v2_cache_records(tmp_path, monkeypatch):
    """The default ScriptedProvider stub rejects everything -- so P1 should
    show 0 false accepts (it never accepts anything) and false-reject every
    truthful case. Confirms the v2 prompt_version is what actually gets
    written to cache for these surfaces, not v1 (which would silently
    invalidate/collide with the confirmatory corpus's cache namespace)."""
    from trust_eval.harness.cache import ResponseCache, cache_key
    from trust_eval.harness.providers import ScriptedProvider
    from trust_eval.study_c.llm_review import _SYSTEM_V2, make_cached_reviewer, render_review_prompt
    from trust_eval.study_c.world import build_identity_world, identity_cases

    cache = ResponseCache(tmp_path / "records")
    prov = ScriptedProvider(model="stub")
    review = make_cached_reviewer(prov, cache, live=True, system=_SYSTEM_V2, prompt_version=PROMPT_VERSION_2)
    world = build_identity_world(2)
    cases = identity_cases(2)
    for c in cases:
        review(c, world)

    prompt = render_review_prompt(cases[0], world, system=_SYSTEM_V2)
    key = cache_key("scripted", "stub", PROMPT_VERSION_2, prompt)
    rec = cache.get(key)
    assert rec is not None
    assert rec["prompt_version"] == PROMPT_VERSION_2
    assert "evaluated_at" in rec
    assert "usage" in rec   # ScriptedProvider.complete_with_usage always reports something
