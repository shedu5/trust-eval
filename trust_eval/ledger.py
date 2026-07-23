"""Immutable trusted event ledger — the external source of truth.

The pilot could only ask whether a bundle is *internally* self-consistent. The
upgraded study distinguishes two validity concepts:

* **internal validity** — is the delivered bundle structurally and
  cryptographically self-consistent? (``trust_eval.verify.verify_bundle``)
* **external truthfulness** — does the delivered bundle correspond to the event
  that *actually occurred* according to an independent, trusted record?
  (``trust_eval.external.verify_external``)

The ledger is that independent record. Each canonical :class:`TrustedEvent`
captures what really happened for one member of one bundle: the true actor,
action, event time, evidence-capture time, and the canonical content digest.
Evidence bundles are generated *from* the ledger; attackers may mutate the
delivered bundle but must never touch the ledger. A self-consistent forgery is
therefore exactly a bundle that passes internal verification while diverging from
its ledger — the case an LLM overseer cannot resolve from the bundle alone.

Immutability is enforced two ways: :class:`TrustedEvent` is a frozen pydantic
model, and :class:`Ledger` exposes read-only lookup with no mutators.
"""

from __future__ import annotations

from typing import Dict, Iterable, Optional, Tuple

from pydantic import BaseModel, ConfigDict

from .schema import EvidenceBundle


class TrustedEvent(BaseModel):
    """The canonical, trusted record of one evidence-producing event."""

    model_config = ConfigDict(frozen=True)

    bundle_id: str
    member_id: str
    actor: str
    action: str
    event_time: str
    evidence_time: str
    content_digest: str  # canonical SHA-256 of the true artifact content
    tool_id: str = ""


class Ledger:
    """Read-only collection of trusted events, keyed by (bundle_id, member_id)."""

    def __init__(self, events: Iterable[TrustedEvent]):
        self._events: Dict[Tuple[str, str], TrustedEvent] = {
            (e.bundle_id, e.member_id): e for e in events
        }

    def get(self, bundle_id: str, member_id: str) -> Optional[TrustedEvent]:
        return self._events.get((bundle_id, member_id))

    def __len__(self) -> int:
        return len(self._events)

    def __contains__(self, key: Tuple[str, str]) -> bool:
        return key in self._events


def build_ledger_from_bundles(bundles: Iterable[EvidenceBundle]) -> Ledger:
    """Derive the trusted ledger from a set of pristine (valid) bundles.

    The pristine corpus *is* ground truth: for each member, the referencing
    provenance step supplies the true actor/action/event_time, and the member
    itself supplies the true evidence_time and content digest. Attacks later
    mutate copies of these bundles; the ledger stays fixed here.
    """
    events = []
    for b in bundles:
        step_by_ref = {s.member_ref: s for s in b.provenance}
        for m in b.members:
            s = step_by_ref.get(m.member_id)
            events.append(
                TrustedEvent(
                    bundle_id=b.bundle_id,
                    member_id=m.member_id,
                    actor=s.actor if s else "",
                    action=s.action if s else "",
                    event_time=s.event_time if s else "",
                    evidence_time=m.evidence_time,
                    content_digest=m.content_hash,
                    tool_id=m.kind,
                )
            )
    return Ledger(events)


__all__ = ["TrustedEvent", "Ledger", "build_ledger_from_bundles"]
