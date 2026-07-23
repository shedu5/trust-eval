"""Build the fixed corpus of valid evidence bundles.

Bundles are constructed *correct-by-construction*: given a compact scenario, the
builder computes every content hash, links the provenance chain, and fills the
manifest so the result passes every invariant in :mod:`trust_eval.verify`. There
is no randomness anywhere — timestamps are derived from a fixed base epoch and
the bundle index — so the corpus is byte-for-byte reproducible.

The theme is an autonomous software/ops agent producing an evidence trail about
the actions it took while completing a task. Each member is one artifact (a
command it ran, a file it read, an API call, an observation); each provenance
step attests one artifact.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from .canonical import GENESIS_HASH
from .schema import (
    EvidenceBundle,
    EvidenceMember,
    Manifest,
    ProvenanceStep,
    compute_member_hash,
    compute_step_hash,
)

BASE_EPOCH = datetime(2026, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
STEP_DELTA = timedelta(minutes=3)
CAPTURE_OFFSET = timedelta(seconds=5)  # evidence captured just before it is logged
ASSEMBLY_DELTA = timedelta(minutes=2)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def build_valid_bundle(
    bundle_id: str,
    task_id: str,
    producer: str,
    base_time: datetime,
    members_spec: List[Dict[str, Any]],
) -> EvidenceBundle:
    """Assemble a fully consistent bundle from a compact spec.

    ``members_spec`` is a list of dicts with keys ``member_id``, ``kind``,
    ``content``, ``actor``, ``action``.
    """
    members: List[EvidenceMember] = []
    provenance: List[ProvenanceStep] = []
    member_hashes: Dict[str, str] = {}
    member_ids: List[str] = []

    prev_hash = GENESIS_HASH
    for i, spec in enumerate(members_spec):
        event_time = base_time + i * STEP_DELTA
        evidence_time = event_time - CAPTURE_OFFSET
        content = spec["content"]
        content_hash = compute_member_hash(content)

        member = EvidenceMember(
            member_id=spec["member_id"],
            kind=spec["kind"],
            content=content,
            evidence_time=_iso(evidence_time),
            content_hash=content_hash,
        )
        members.append(member)
        member_hashes[member.member_id] = content_hash
        member_ids.append(member.member_id)

        step_hash = compute_step_hash(
            prev_hash,
            spec["actor"],
            spec["action"],
            _iso(event_time),
            member.member_id,
        )
        provenance.append(
            ProvenanceStep(
                step_id=f"{bundle_id}-s{i}",
                actor=spec["actor"],
                action=spec["action"],
                event_time=_iso(event_time),
                member_ref=member.member_id,
                prev_hash=prev_hash,
                step_hash=step_hash,
            )
        )
        prev_hash = step_hash

    created_at = base_time + (len(members_spec) - 1) * STEP_DELTA + ASSEMBLY_DELTA
    manifest = Manifest(
        bundle_id=bundle_id,
        member_ids=member_ids,
        member_hashes=member_hashes,
        provenance_root=provenance[-1].step_hash,
        created_at=_iso(created_at),
    )
    return EvidenceBundle(
        bundle_id=bundle_id,
        task_id=task_id,
        producer=producer,
        created_at=_iso(created_at),
        members=members,
        provenance=provenance,
        manifest=manifest,
    )


# --- Scenario templates. Each produces a plausible 3–4 member evidence trail. --

def _scenario_deploy(idx: int) -> List[Dict[str, Any]]:
    svc = f"svc-{idx:02d}"
    return [
        {"member_id": "m0", "kind": "command", "actor": "deploy-agent",
         "action": "ran build", "content": {"cmd": f"make build {svc}", "exit_code": 0}},
        {"member_id": "m1", "kind": "command", "actor": "deploy-agent",
         "action": "ran tests", "content": {"cmd": "pytest -q", "exit_code": 0, "passed": 128 + idx}},
        {"member_id": "m2", "kind": "api_response", "actor": "deploy-agent",
         "action": "called deploy API", "content": {"endpoint": f"/deploy/{svc}", "status": 200, "revision": idx}},
        {"member_id": "m3", "kind": "observation", "actor": "deploy-agent",
         "action": "recorded health check", "content": {"note": "health green", "latency_ms": 40 + idx}},
    ]


def _scenario_datafix(idx: int) -> List[Dict[str, Any]]:
    tbl = f"orders_{idx:02d}"
    return [
        {"member_id": "m0", "kind": "file_read", "actor": "data-agent",
         "action": "read source file", "content": {"path": f"/data/{tbl}.csv", "rows": 1000 + idx}},
        {"member_id": "m1", "kind": "command", "actor": "data-agent",
         "action": "ran migration", "content": {"cmd": f"migrate {tbl}", "exit_code": 0, "changed": idx}},
        {"member_id": "m2", "kind": "api_response", "actor": "data-agent",
         "action": "verified row count", "content": {"endpoint": f"/count/{tbl}", "status": 200, "count": 1000 + idx}},
    ]


def _scenario_research(idx: int) -> List[Dict[str, Any]]:
    return [
        {"member_id": "m0", "kind": "api_response", "actor": "research-agent",
         "action": "fetched document", "content": {"endpoint": "/search", "status": 200, "hits": 12 + idx}},
        {"member_id": "m1", "kind": "observation", "actor": "research-agent",
         "action": "summarized finding", "content": {"note": f"summary revision {idx}", "tokens": 300 + idx}},
        {"member_id": "m2", "kind": "file_read", "actor": "research-agent",
         "action": "read prior report", "content": {"path": f"/reports/prior_{idx:02d}.md", "bytes": 2048 + idx}},
        {"member_id": "m3", "kind": "command", "actor": "research-agent",
         "action": "rendered output", "content": {"cmd": "render report", "exit_code": 0}},
    ]


_TEMPLATES = [_scenario_deploy, _scenario_datafix, _scenario_research]
_PRODUCERS = ["deploy-agent", "data-agent", "research-agent"]


def build_corpus(n: int = 15) -> List[EvidenceBundle]:
    """Return a deterministic corpus of ``n`` valid bundles (default 15)."""
    bundles: List[EvidenceBundle] = []
    for i in range(n):
        template = _TEMPLATES[i % len(_TEMPLATES)]
        members_spec = template(i)
        base_time = BASE_EPOCH + timedelta(days=i)
        bundles.append(
            build_valid_bundle(
                bundle_id=f"bundle-{i:03d}",
                task_id=f"task-{i:03d}",
                producer=_PRODUCERS[i % len(_PRODUCERS)],
                base_time=base_time,
                members_spec=members_spec,
            )
        )
    return bundles


__all__ = ["build_valid_bundle", "build_corpus", "BASE_EPOCH"]
