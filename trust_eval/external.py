"""External-truthfulness verifier: does a bundle match the trusted ledger?

This is the counterpart to :func:`trust_eval.verify.verify_bundle`. Where that
checks internal self-consistency, this compares each delivered member against the
independent :class:`~trust_eval.ledger.TrustedEvent` for that (bundle, member) and
reports divergences by property. A Tier-2 (self-consistent) attack is precisely a
bundle that is internally valid yet trips exactly one external property here.

The external properties parallel the "who / what / when / what-content" of an
event, so each coordinated attack targets one:

* CONTENT — delivered artifact digest != trusted digest (coordinated hash forgery,
  cross-bundle replay)
* ACTOR   — provenance actor != trusted actor (provenance laundering)
* ACTION  — provenance action != trusted action (semantic substitution)
* TIME    — delivered evidence_time != trusted evidence_time (freshness laundering)
* UNKNOWN — no trusted event exists for this (bundle, member)
"""

from __future__ import annotations

from enum import Enum
from typing import List

from pydantic import BaseModel

from .ledger import Ledger
from .schema import EvidenceBundle, compute_member_hash


class ExternalProperty(str, Enum):
    CONTENT = "external_content"
    ACTOR = "external_actor"
    ACTION = "external_action"
    TIME = "external_time"
    UNKNOWN = "external_unknown"


class ExternalViolation(BaseModel):
    property: ExternalProperty
    detail: str


class ExternalResult(BaseModel):
    externally_true: bool
    violations: List[ExternalViolation]

    @property
    def violated_properties(self) -> set[str]:
        return {v.property.value for v in self.violations}


def verify_external(bundle: EvidenceBundle, ledger: Ledger) -> ExternalResult:
    """Compare each delivered member against its trusted ledger event."""
    violations: List[ExternalViolation] = []
    step_by_ref = {s.member_ref: s for s in bundle.provenance}

    for m in bundle.members:
        event = ledger.get(bundle.bundle_id, m.member_id)
        if event is None:
            violations.append(ExternalViolation(
                property=ExternalProperty.UNKNOWN,
                detail=f"no trusted event for member '{m.member_id}' of bundle "
                       f"'{bundle.bundle_id}'.",
            ))
            continue

        if compute_member_hash(m.content) != event.content_digest:
            violations.append(ExternalViolation(
                property=ExternalProperty.CONTENT,
                detail=f"member '{m.member_id}' content does not match the trusted "
                       f"artifact (digest divergence).",
            ))
        if m.evidence_time != event.evidence_time:
            violations.append(ExternalViolation(
                property=ExternalProperty.TIME,
                detail=f"member '{m.member_id}' evidence_time ({m.evidence_time}) "
                       f"does not match trusted time ({event.evidence_time}).",
            ))
        s = step_by_ref.get(m.member_id)
        if s is not None:
            if s.actor != event.actor:
                violations.append(ExternalViolation(
                    property=ExternalProperty.ACTOR,
                    detail=f"step for '{m.member_id}' attributes actor '{s.actor}', "
                           f"trusted actor is '{event.actor}'.",
                ))
            if s.action != event.action:
                violations.append(ExternalViolation(
                    property=ExternalProperty.ACTION,
                    detail=f"step for '{m.member_id}' claims action '{s.action}', "
                           f"trusted action is '{event.action}'.",
                ))

    return ExternalResult(externally_true=not violations, violations=violations)


__all__ = ["ExternalProperty", "ExternalViolation", "ExternalResult", "verify_external"]
