"""trust-eval: a miniature oversight harness for fabricated-evidence detection."""

from .schema import EvidenceBundle, EvidenceMember, Manifest, ProvenanceStep
from .verify import Property, VerificationResult, verify_bundle
from .corpus import build_corpus
from .attacks import ATTACK_REGISTRY, ATTACK_CLASSES, apply_attack

__all__ = [
    "EvidenceBundle",
    "EvidenceMember",
    "Manifest",
    "ProvenanceStep",
    "Property",
    "VerificationResult",
    "verify_bundle",
    "build_corpus",
    "ATTACK_REGISTRY",
    "ATTACK_CLASSES",
    "apply_attack",
]
