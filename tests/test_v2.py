"""The internal-validity vs external-truthfulness distinction, and Tier-2 attacks.

The load-bearing claim of the upgraded study: a Tier-2 attack produces a bundle
that is INTERNALLY VALID (passes every self-consistency check) yet EXTERNALLY
FALSE on exactly one property (diverges from the trusted ledger). These tests
prove that before any model is involved — the instrument stays trustworthy.
"""

import pytest

from trust_eval.attacks_v2 import ATTACK_V2_REGISTRY
from trust_eval.corpus import build_corpus
from trust_eval.external import verify_external
from trust_eval.ledger import TrustedEvent, build_ledger_from_bundles
from trust_eval.verify import verify_bundle

CORPUS = build_corpus()
LEDGER = build_ledger_from_bundles(CORPUS)


def test_ledger_covers_every_member():
    total_members = sum(len(b.members) for b in CORPUS)
    assert len(LEDGER) == total_members


def test_trusted_event_is_immutable():
    ev = next(iter([LEDGER.get(CORPUS[0].bundle_id, CORPUS[0].members[0].member_id)]))
    with pytest.raises(Exception):
        ev.actor = "tampered"


@pytest.mark.parametrize("bundle", CORPUS, ids=lambda b: b.bundle_id)
def test_benign_is_internally_valid_and_externally_true(bundle):
    assert verify_bundle(bundle).is_valid
    assert verify_external(bundle, LEDGER).externally_true


@pytest.mark.parametrize("name", list(ATTACK_V2_REGISTRY.keys()))
@pytest.mark.parametrize("bundle", CORPUS, ids=lambda b: b.bundle_id)
def test_tier2_is_internally_valid_but_externally_false(bundle, name):
    fn, target = ATTACK_V2_REGISTRY[name]
    tampered = fn(bundle)
    # Internally flawless...
    internal = verify_bundle(tampered)
    assert internal.is_valid, (name, bundle.bundle_id, internal.violations)
    # ...yet externally false on exactly the one targeted property.
    external = verify_external(tampered, LEDGER)
    assert not external.externally_true
    assert external.violated_properties == {target.value}, (
        name, bundle.bundle_id, external.violated_properties)


@pytest.mark.parametrize("name", list(ATTACK_V2_REGISTRY.keys()))
def test_tier2_is_pure(name):
    fn, _ = ATTACK_V2_REGISTRY[name]
    original = build_corpus()[0]
    before = original.model_dump()
    fn(original)
    assert original.model_dump() == before, f"{name} mutated its input"
