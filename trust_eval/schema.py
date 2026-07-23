"""Evidence-bundle + manifest schema.

An *evidence bundle* is a toy stand-in for the package of evidence an agent
produces about its own actions — the trail a model- or human-overseer would
inspect to decide whether to trust what the agent reports. A bundle has three
parts:

* **members** — the individual pieces of evidence (a log line, a tool output,
  an observation). Each carries its own ``content`` payload, the time the
  evidence was captured (``evidence_time``), and a ``content_hash`` over the
  payload.
* **provenance** — an ordered, hash-linked chain of steps. Each step records
  who did what and when (``actor``/``action``/``event_time``), points at the
  member it produced, and links to the previous step via ``prev_hash``. This is
  a miniature tamper-evident log.
* **manifest** — the authoritative summary an overseer checks a bundle
  *against*: the complete list of member ids the bundle claims to contain
  (the completeness claim), the expected content hash of each member, and the
  provenance root (the hash of the last step).

The models here are deliberately *permissive* data containers: constructing one
does **not** enforce internal consistency. Consistency is defined and checked in
one place — :mod:`trust_eval.verify`. That separation is what lets the attack
functions in :mod:`trust_eval.attacks` deliberately produce bundles that violate
exactly one invariant, while the ground-truth verifier stays the single source
of truth about what "valid" means.
"""

from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field

from .canonical import GENESIS_HASH, sha256_hex

SCHEMA_VERSION = "trust-eval/evidence-bundle/v1"


class EvidenceMember(BaseModel):
    """A single piece of evidence within a bundle."""

    member_id: str
    kind: str = Field(description="e.g. 'log', 'tool_output', 'observation'")
    content: Dict[str, Any] = Field(
        description="JSON payload of the evidence itself."
    )
    evidence_time: str = Field(
        description="ISO-8601 UTC time the evidence was captured."
    )
    content_hash: str = Field(
        description="SHA-256 over the canonical form of `content`."
    )


class ProvenanceStep(BaseModel):
    """One link in the tamper-evident provenance chain."""

    step_id: str
    actor: str = Field(description="Which agent/tool performed the action.")
    action: str = Field(description="What was done, e.g. 'captured tool output'.")
    event_time: str = Field(description="ISO-8601 UTC time the action occurred.")
    member_ref: str = Field(description="member_id this step produced/attests.")
    prev_hash: str = Field(description="step_hash of the previous step, or GENESIS.")
    step_hash: str = Field(description="Hash binding this step to its predecessor.")


class Manifest(BaseModel):
    """The authoritative summary an overseer checks a bundle against."""

    bundle_id: str
    schema_version: str = SCHEMA_VERSION
    member_ids: List[str] = Field(
        description="Complete list of member_ids the bundle claims to contain."
    )
    member_hashes: Dict[str, str] = Field(
        description="member_id -> expected content_hash."
    )
    provenance_root: str = Field(
        description="step_hash of the final provenance step."
    )
    created_at: str = Field(description="ISO-8601 UTC time the bundle was assembled.")


class EvidenceBundle(BaseModel):
    """A full evidence bundle: members + provenance + manifest."""

    bundle_id: str
    task_id: str
    producer: str = Field(description="Agent id that produced the bundle.")
    created_at: str
    members: List[EvidenceMember]
    provenance: List[ProvenanceStep]
    manifest: Manifest

    def member_by_id(self, member_id: str) -> EvidenceMember | None:
        for m in self.members:
            if m.member_id == member_id:
                return m
        return None

    def model_copy_deep(self) -> "EvidenceBundle":
        """Deep copy — attacks operate on copies so fixtures stay pristine."""
        return EvidenceBundle.model_validate(self.model_dump())


# ---------------------------------------------------------------------------
# Hash helpers. These define *how* the two kinds of hash in the schema are
# computed. The verifier and the corpus builder both call these so that
# "valid" is defined the same way everywhere.
# ---------------------------------------------------------------------------


def compute_member_hash(content: Dict[str, Any]) -> str:
    """Content hash of an evidence member's payload."""
    return sha256_hex({"content": content})


def compute_step_hash(
    prev_hash: str,
    actor: str,
    action: str,
    event_time: str,
    member_ref: str,
) -> str:
    """Hash binding a provenance step to its predecessor and its fields."""
    return sha256_hex(
        {
            "prev_hash": prev_hash,
            "actor": actor,
            "action": action,
            "event_time": event_time,
            "member_ref": member_ref,
        }
    )


__all__ = [
    "SCHEMA_VERSION",
    "GENESIS_HASH",
    "EvidenceMember",
    "ProvenanceStep",
    "Manifest",
    "EvidenceBundle",
    "compute_member_hash",
    "compute_step_hash",
]
