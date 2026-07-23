"""Each attack corrupts exactly its target property — and nothing else.

This is the load-bearing test of the whole project: it proves the measurement
instrument is trustworthy before any LLM judge is ever called. For every valid
bundle in the corpus and every attack, we assert that the ground-truth verifier
reports invalidity whose violated-property set is *exactly* the one the attack
declares it targets.
"""

import pytest

from trust_eval.attacks import ATTACK_REGISTRY
from trust_eval.corpus import build_corpus
from trust_eval.verify import verify_bundle

CORPUS = build_corpus()
NON_BENIGN = {k: v for k, v in ATTACK_REGISTRY.items() if v[1] is not None}


@pytest.mark.parametrize("bundle", CORPUS, ids=lambda b: b.bundle_id)
def test_benign_is_valid(bundle):
    fn, _ = ATTACK_REGISTRY["benign"]
    assert verify_bundle(fn(bundle)).is_valid


@pytest.mark.parametrize("name", list(NON_BENIGN.keys()))
@pytest.mark.parametrize("bundle", CORPUS, ids=lambda b: b.bundle_id)
def test_attack_corrupts_exactly_its_target(bundle, name):
    fn, target = ATTACK_REGISTRY[name]
    tampered = fn(bundle)
    result = verify_bundle(tampered)
    assert not result.is_valid, f"{name} on {bundle.bundle_id} was not detected"
    assert result.violated_properties == {target.value}, (
        f"{name} on {bundle.bundle_id} broke {result.violated_properties}, "
        f"expected exactly {{{target.value}}}"
    )


@pytest.mark.parametrize("name", list(ATTACK_REGISTRY.keys()))
def test_attacks_are_pure(name):
    """Applying an attack must not mutate the input bundle."""
    fn, _ = ATTACK_REGISTRY[name]
    original = build_corpus()[0]
    before = original.model_dump()
    fn(original)
    assert original.model_dump() == before, f"{name} mutated its input bundle"
