"""Build the evaluation suite: every valid bundle crossed with every attack.

Each :class:`Case` pairs a (possibly tampered) bundle with its ground-truth
label. The judge is shown only the bundle; the attack name and ground truth are
withheld and used solely for scoring. The suite is fully deterministic — the
corpus is fixed and the attacks are pure — so the same cases are produced every
run, which is what lets cached judge responses reproduce the tables exactly.
"""

from __future__ import annotations

from enum import Enum
from typing import List

from pydantic import BaseModel

from ..attacks import ATTACK_CLASSES, apply_attack
from ..corpus import build_corpus
from ..schema import EvidenceBundle


class GroundTruth(str, Enum):
    TRUSTWORTHY = "trustworthy"  # benign, untampered
    TAMPERED = "tampered"


class Case(BaseModel):
    case_id: str
    bundle_id: str
    attack: str
    ground_truth: GroundTruth
    bundle: EvidenceBundle


def build_suite(n: int | None = None) -> List[Case]:
    """Return the full labeled suite (|corpus| x |attack classes| cases)."""
    corpus = build_corpus() if n is None else build_corpus(n)
    cases: List[Case] = []
    for bundle in corpus:
        for attack in ATTACK_CLASSES:
            tampered = apply_attack(attack, bundle)
            gt = GroundTruth.TRUSTWORTHY if attack == "benign" else GroundTruth.TAMPERED
            cases.append(
                Case(
                    case_id=f"{bundle.bundle_id}::{attack}",
                    bundle_id=bundle.bundle_id,
                    attack=attack,
                    ground_truth=gt,
                    bundle=tampered,
                )
            )
    return cases


__all__ = ["GroundTruth", "Case", "build_suite"]
