"""The corpus is valid and reproducible."""

from trust_eval.canonical import canonical_bytes
from trust_eval.corpus import build_corpus
from trust_eval.verify import verify_bundle


def test_corpus_size_and_shape():
    bundles = build_corpus()
    assert len(bundles) == 15
    for b in bundles:
        assert len(b.members) >= 3
        assert len(b.provenance) == len(b.members)


def test_every_corpus_bundle_is_valid():
    for b in build_corpus():
        result = verify_bundle(b)
        assert result.is_valid, (b.bundle_id, result.violations)


def test_corpus_is_deterministic():
    a = build_corpus()
    c = build_corpus()
    dump_a = [canonical_bytes(x.model_dump()) for x in a]
    dump_c = [canonical_bytes(x.model_dump()) for x in c]
    assert dump_a == dump_c


def test_bundle_ids_unique():
    ids = [b.bundle_id for b in build_corpus()]
    assert len(ids) == len(set(ids))
