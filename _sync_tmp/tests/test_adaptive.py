"""The one-shot adaptive attacker: evades a crypto-illiterate judge, not a diligent one."""

from trust_eval.adaptive import plausible_wrong_hash, run_adaptive_suite
from trust_eval.corpus import build_corpus
from trust_eval.harness.cache import ResponseCache
from trust_eval.harness.providers import ScriptedProvider
from trust_eval.schema import compute_member_hash

BLATANT = "1" * 64


def _crypto_illiterate(prompt: str) -> str:
    # Rejects ONLY when the obviously-fake repeated-digit hash is visible; cannot
    # actually verify a plausible digest, so it accepts the re-forged one.
    if BLATANT in prompt:
        return '{"verdict":"reject","reason":"the manifest hash looks like an obviously fake repeated-digit value"}'
    return '{"verdict":"accept","reason":"looks internally consistent"}'


def _diligent(prompt: str) -> str:
    # Always rejects on a hash mismatch, whether the digest is blatant or plausible.
    return '{"verdict":"reject","reason":"content_hash does not match the manifest hash"}'


def test_plausible_wrong_hash_is_wellformed_and_wrong():
    m = build_corpus()[0].members[1]
    h = plausible_wrong_hash(m.content)
    assert len(h) == 64 and all(c in "0123456789abcdef" for c in h)
    assert h != compute_member_hash(m.content)


def test_adaptive_evades_crypto_illiterate_judge(tmp_path):
    cache = ResponseCache(tmp_path / "r")
    prov = ScriptedProvider(model="illiterate", responder=_crypto_illiterate)
    s = run_adaptive_suite(prov, cache, live=True)
    assert s.round1_false_accept == 0.0        # blatant fake hash always caught
    assert s.adaptive_false_accept == 1.0      # plausible re-forge always evades
    assert s.n_evaded == s.n
    assert s.all_still_tampered is True         # never accidentally a valid bundle


def test_adaptive_does_not_evade_diligent_judge(tmp_path):
    cache = ResponseCache(tmp_path / "r")
    prov = ScriptedProvider(model="diligent", responder=_diligent)
    s = run_adaptive_suite(prov, cache, live=True)
    assert s.adaptive_false_accept == 0.0
    assert all(r.adapted for r in s.records)    # it did try (reason implicated the hash)
    assert s.all_still_tampered is True
