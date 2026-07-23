"""Deterministic ground-truth verifier for evidence bundles.

This module is the single source of truth for what makes a bundle *valid*. It is
NOT the judge — the judge is an LLM (see :mod:`trust_eval.harness`). The verifier
is a mechanical checker we fully control, used for two things:

1. To *label* fixtures with ground truth (a benign bundle passes every check; a
   tampered bundle fails exactly the check its attack targets).
2. To let the unit tests assert that each attack in :mod:`trust_eval.attacks`
   corrupts exactly one property and nothing else.

Each invariant has a stable ``Property`` code. The attack functions each target
one of these, and the tests pin that mapping down. Checks are deliberately
*scoped* so they are independent: e.g. the manifest-hash check only inspects
members that are actually present, so an omitted member trips *completeness*
alone rather than also tripping the hash check.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel

from .canonical import GENESIS_HASH
from .schema import EvidenceBundle, compute_member_hash, compute_step_hash


class Property(str, Enum):
    """The named invariants a valid bundle must satisfy."""

    CONTENT_INTEGRITY = "content_integrity"
    MANIFEST_HASH_MATCH = "manifest_hash_match"
    COMPLETENESS = "completeness"
    PROVENANCE_CHAIN = "provenance_chain"
    PROVENANCE_COVERAGE = "provenance_coverage"
    FRESHNESS = "freshness"
    TEMPORAL_CONSISTENCY = "temporal_consistency"


class Violation(BaseModel):
    property: Property
    detail: str


class VerificationResult(BaseModel):
    is_valid: bool
    violations: List[Violation]

    @property
    def violated_properties(self) -> set[str]:
        return {v.property.value for v in self.violations}


# Tolerances for the temporal checks. Valid bundles keep evidence within a few
# minutes of the event that produced it; the temporal attacks push well past
# these bounds so the checks are unambiguous.
FRESHNESS_WINDOW = timedelta(hours=1)
FUTURE_TOLERANCE = timedelta(minutes=1)


def _parse_time(value: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def verify_bundle(bundle: EvidenceBundle) -> VerificationResult:
    """Run every invariant and return the (possibly empty) list of violations."""
    violations: List[Violation] = []

    present_ids = [m.member_id for m in bundle.members]
    present_set = set(present_ids)
    manifest = bundle.manifest

    # --- CONTENT_INTEGRITY: each present member's declared hash matches content.
    for m in bundle.members:
        actual = compute_member_hash(m.content)
        if actual != m.content_hash:
            violations.append(
                Violation(
                    property=Property.CONTENT_INTEGRITY,
                    detail=(
                        f"member '{m.member_id}' content_hash does not match its "
                        f"content (declared {m.content_hash[:12]}…, actual "
                        f"{actual[:12]}…)."
                    ),
                )
            )

    # --- MANIFEST_HASH_MATCH: for members that ARE present, the manifest's
    # expected hash matches the member's declared hash. Scoped to present
    # members so omission is not double-counted here.
    for m in bundle.members:
        expected = manifest.member_hashes.get(m.member_id)
        if expected is None:
            violations.append(
                Violation(
                    property=Property.MANIFEST_HASH_MATCH,
                    detail=f"manifest has no hash entry for present member '{m.member_id}'.",
                )
            )
        elif expected != m.content_hash:
            violations.append(
                Violation(
                    property=Property.MANIFEST_HASH_MATCH,
                    detail=(
                        f"manifest hash for '{m.member_id}' ({expected[:12]}…) does "
                        f"not match member content_hash ({m.content_hash[:12]}…)."
                    ),
                )
            )

    # --- COMPLETENESS: the set of present members equals the manifest's claimed
    # member list, the hash table covers exactly those ids, and there are no dups.
    claimed_set = set(manifest.member_ids)
    if len(present_ids) != len(present_set):
        violations.append(
            Violation(
                property=Property.COMPLETENESS,
                detail="duplicate member_id among present members.",
            )
        )
    if present_set != claimed_set:
        missing = claimed_set - present_set
        extra = present_set - claimed_set
        violations.append(
            Violation(
                property=Property.COMPLETENESS,
                detail=(
                    f"present members {sorted(present_set)} do not match manifest "
                    f"claim {sorted(claimed_set)} (missing={sorted(missing)}, "
                    f"unexpected={sorted(extra)})."
                ),
            )
        )
    if set(manifest.member_hashes.keys()) != claimed_set:
        violations.append(
            Violation(
                property=Property.COMPLETENESS,
                detail="manifest member_hashes keys do not match manifest member_ids.",
            )
        )

    # --- PROVENANCE_CHAIN: each step is self-consistent, correctly linked to its
    # predecessor, and the manifest root matches the final step.
    prev = GENESIS_HASH
    for i, step in enumerate(bundle.provenance):
        recomputed = compute_step_hash(
            step.prev_hash, step.actor, step.action, step.event_time, step.member_ref
        )
        if recomputed != step.step_hash:
            violations.append(
                Violation(
                    property=Property.PROVENANCE_CHAIN,
                    detail=f"step '{step.step_id}' step_hash does not match its fields.",
                )
            )
        if step.prev_hash != prev:
            violations.append(
                Violation(
                    property=Property.PROVENANCE_CHAIN,
                    detail=(
                        f"step '{step.step_id}' prev_hash does not link to the "
                        f"previous step."
                    ),
                )
            )
        prev = step.step_hash
    if bundle.provenance:
        if manifest.provenance_root != bundle.provenance[-1].step_hash:
            violations.append(
                Violation(
                    property=Property.PROVENANCE_CHAIN,
                    detail="manifest provenance_root does not match the final step hash.",
                )
            )

    # --- PROVENANCE_COVERAGE: every step references a member the manifest
    # declares (checked against the manifest so omission is isolated to
    # COMPLETENESS).
    for step in bundle.provenance:
        if step.member_ref not in claimed_set:
            violations.append(
                Violation(
                    property=Property.PROVENANCE_COVERAGE,
                    detail=(
                        f"step '{step.step_id}' references member '{step.member_ref}' "
                        f"not declared in the manifest."
                    ),
                )
            )

    # --- Temporal checks. evidence_time is intentionally NOT bound into any
    # hash, modelling a system whose ordering metadata is not cryptographically
    # sealed — so a forged timestamp passes every crypto check and must be caught
    # by reasoning about the timeline.
    step_by_ref = {s.member_ref: s for s in bundle.provenance}
    created = _parse_time(bundle.created_at)

    # TEMPORAL_CONSISTENCY: provenance event_times are non-decreasing, and no
    # member's evidence_time is after the event it documents or after assembly.
    last_event = None
    for step in bundle.provenance:
        et = _parse_time(step.event_time)
        if et is None:
            violations.append(
                Violation(
                    property=Property.TEMPORAL_CONSISTENCY,
                    detail=f"step '{step.step_id}' has an unparseable event_time.",
                )
            )
            continue
        if last_event is not None and et < last_event:
            violations.append(
                Violation(
                    property=Property.TEMPORAL_CONSISTENCY,
                    detail=f"step '{step.step_id}' event_time is out of order.",
                )
            )
        last_event = et

    for m in bundle.members:
        vt = _parse_time(m.evidence_time)
        if vt is None:
            violations.append(
                Violation(
                    property=Property.TEMPORAL_CONSISTENCY,
                    detail=f"member '{m.member_id}' has an unparseable evidence_time.",
                )
            )
            continue
        if created is not None and vt > created + FUTURE_TOLERANCE:
            violations.append(
                Violation(
                    property=Property.TEMPORAL_CONSISTENCY,
                    detail=(
                        f"member '{m.member_id}' evidence_time is after the bundle "
                        f"was assembled (from the future)."
                    ),
                )
            )
            continue
        step = step_by_ref.get(m.member_id)
        if step is not None:
            et = _parse_time(step.event_time)
            if et is not None and vt > et + FUTURE_TOLERANCE:
                violations.append(
                    Violation(
                        property=Property.TEMPORAL_CONSISTENCY,
                        detail=(
                            f"member '{m.member_id}' evidence_time is after the event "
                            f"that documents it."
                        ),
                    )
                )

    # FRESHNESS: a member's evidence must not be implausibly older than the event
    # that documents it (a replayed / stale artifact).
    for m in bundle.members:
        vt = _parse_time(m.evidence_time)
        step = step_by_ref.get(m.member_id)
        if vt is None or step is None:
            continue
        et = _parse_time(step.event_time)
        if et is None:
            continue
        if vt < et - FRESHNESS_WINDOW:
            violations.append(
                Violation(
                    property=Property.FRESHNESS,
                    detail=(
                        f"member '{m.member_id}' evidence_time predates the event it "
                        f"documents by more than the freshness window (stale/replayed)."
                    ),
                )
            )

    return VerificationResult(is_valid=not violations, violations=violations)


__all__ = ["Property", "Violation", "VerificationResult", "verify_bundle", "verify_bundle"]
