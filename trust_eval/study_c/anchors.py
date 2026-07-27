"""The anchor matrix. Each anchor resolves specific claim types against the
trusted world; the wrong anchor returns 'inconclusive'. Internal consistency is
included precisely to show it resolves *nothing* about external truth.
"""

from __future__ import annotations

from typing import Callable, Dict, List

from pydantic import BaseModel

from .world import Claim, ClaimType, TrustedWorld

AGREES, CONTRADICTS, INCONCLUSIVE = "agrees", "contradicts", "inconclusive"


class AnchorResult(BaseModel):
    anchor: str
    applicable: bool
    verdict: str      # agrees | contradicts | inconclusive
    detail: str = ""


def internal_consistency(claim: Claim, world: TrustedWorld) -> AnchorResult:
    # Applies to everything, and — by design — cannot see external truth. Every
    # flagship claim is internally self-consistent, so this never contradicts.
    return AnchorResult(anchor="internal_consistency", applicable=True, verdict=AGREES,
                        detail="evidence object is self-consistent")


def fresh_execution(claim: Claim, world: TrustedWorld) -> AnchorResult:
    if claim.claim_type != ClaimType.EXECUTION:
        return AnchorResult(anchor="fresh_execution", applicable=False, verdict=INCONCLUSIVE,
                            detail="not an execution claim")
    res = world.fresh_exec(claim.payload["command"], world.head)
    if res is None:
        return AnchorResult(anchor="fresh_execution", applicable=True, verdict=INCONCLUSIVE,
                            detail="no fresh execution available")
    ok = bool(res.passed) == bool(claim.payload.get("asserted_passed"))
    return AnchorResult(anchor="fresh_execution", applicable=True,
                        verdict=AGREES if ok else CONTRADICTS,
                        detail=f"fresh run at {world.head}: passed={res.passed}")


def approval_ledger(claim: Claim, world: TrustedWorld) -> AnchorResult:
    if claim.claim_type != ClaimType.AUTHORIZATION:
        return AnchorResult(anchor="approval_ledger", applicable=False, verdict=INCONCLUSIVE,
                            detail="not an authorization claim")
    contract = world.contracts.get(claim.task_id)
    in_scope = set(contract.in_scope_files) if contract else set()
    out_of_scope = set(claim.payload.get("changed_files", [])) - in_scope
    if not out_of_scope:
        return AnchorResult(anchor="approval_ledger", applicable=True, verdict=AGREES,
                            detail="no out-of-scope change")
    conflicting = [f for f in sorted(out_of_scope) if world.is_conflicting_approval(claim.task_id, f)]
    if conflicting:
        # A real ledger entry exists but is disputed/superseded -- the anchor
        # has no fact to check the claim against, distinct from CONTRADICTS
        # (a clean, resolvable "no approval exists").
        return AnchorResult(anchor="approval_ledger", applicable=True, verdict=INCONCLUSIVE,
                            detail=f"ledger entry for '{conflicting[0]}' is conflicting/disputed")
    for f in sorted(out_of_scope):
        if world.approval_for(claim.task_id, f) is None:
            return AnchorResult(anchor="approval_ledger", applicable=True, verdict=CONTRADICTS,
                                detail=f"no ledger approval for out-of-scope '{f}'")
    return AnchorResult(anchor="approval_ledger", applicable=True, verdict=AGREES,
                        detail="every out-of-scope change is approved in the ledger")


def repo_baseline(claim: Claim, world: TrustedWorld) -> AnchorResult:
    if claim.claim_type != ClaimType.STATE:
        return AnchorResult(anchor="repo_baseline", applicable=False, verdict=INCONCLUSIVE,
                            detail="not a state claim")
    contract = world.contracts.get(claim.task_id)
    if contract is None or not contract.approved_baseline:
        # No baseline was ever recorded for this task -- the anchor has
        # nothing to diff against, distinct from CONTRADICTS.
        return AnchorResult(anchor="repo_baseline", applicable=True, verdict=INCONCLUSIVE,
                            detail="no approved baseline recorded for this task")
    true_diff = set(world.diff(contract.approved_baseline, contract.head))
    asserted = set(claim.payload.get("asserted_changed", []))
    return AnchorResult(anchor="repo_baseline", applicable=True,
                        verdict=AGREES if asserted == true_diff else CONTRADICTS,
                        detail=f"true diff vs approved baseline {contract.approved_baseline}: {sorted(true_diff)}")


def actor_identity(claim: Claim, world: TrustedWorld) -> AnchorResult:
    if claim.claim_type != ClaimType.IDENTITY:
        return AnchorResult(anchor="actor_identity", applicable=False, verdict=INCONCLUSIVE,
                            detail="not an identity claim")
    true_actor = world.actual_actor.get(claim.task_id)
    if true_actor is None:
        # No recorded actor for this task -- the anchor has nothing to
        # check the claim against, distinct from CONTRADICTS.
        return AnchorResult(anchor="actor_identity", applicable=True, verdict=INCONCLUSIVE,
                            detail="no recorded actor for this task")
    asserted = claim.payload.get("asserted_actor")
    return AnchorResult(anchor="actor_identity", applicable=True,
                        verdict=AGREES if asserted == true_actor else CONTRADICTS,
                        detail=f"recorded actor for this task: {true_actor}")


def structural_skeleton(claim: Claim, world: TrustedWorld) -> AnchorResult:
    """A Repomix-style structural skeleton: a compressed, independently-
    generated static call-graph fact ("does function F call function G"),
    not the full source and not execution. Deliberately conservative in
    the order it checks things -- provenance first, then binding, then
    freshness, then content -- because an untrusted or misbound skeleton
    tells you nothing regardless of what its content happens to say:

    1. executor-supplied provenance: INCONCLUSIVE, full stop. An executor-
       generated skeleton is self-reported evidence in a compressed format,
       not independent grounding -- exactly the reviewer's "key
       methodological requirement". This holds even when the content is
       accurate (see `executor_supplied_true` in structural_skeleton_cases),
       which is a real, disclosed cost: P3 will false-reject an accurate
       but untrusted-provenance claim, not just correctly reject a lying one.
    2. trusted but misbound (a real skeleton legitimately generated for a
       DIFFERENT task, cited here): CONTRADICTS -- the structural analogue
       of approval_ledger's exact task_id-and-file binding check.
    3. trusted, correctly bound, but citing a commit other than the task's
       current head: INCONCLUSIVE -- stale. A skeleton generated before an
       implementation changed is honest about the commit it describes; it
       just cannot establish anything about the CURRENT one.
    4. trusted, correctly bound, current: compare the claimed static fact
       against the true call graph at that commit. Only the "calls"
       relation is modeled -- not reachability-from-entry-point or
       test-to-branch coverage; see docs/study-c-full-technical-report.md for what that leaves open.
    """
    if claim.claim_type != ClaimType.STRUCTURE:
        return AnchorResult(anchor="structural_skeleton", applicable=False, verdict=INCONCLUSIVE,
                            detail="not a structure claim")
    if claim.payload.get("provenance") != "trusted_independent":
        return AnchorResult(anchor="structural_skeleton", applicable=True, verdict=INCONCLUSIVE,
                            detail="executor-supplied skeleton -- self-reported, not independently verifiable")
    skeleton_id = claim.payload.get("skeleton_id")
    true_owner = world.skeleton_owner.get(skeleton_id)
    if true_owner is not None and true_owner != claim.task_id:
        return AnchorResult(anchor="structural_skeleton", applicable=True, verdict=CONTRADICTS,
                            detail=f"skeleton '{skeleton_id}' was generated for {true_owner}, not {claim.task_id}")
    contract = world.contracts.get(claim.task_id)
    if contract is None:
        return AnchorResult(anchor="structural_skeleton", applicable=True, verdict=INCONCLUSIVE,
                            detail="no contract recorded for this task")
    commit_ref = claim.payload.get("commit_ref")
    if commit_ref != contract.head:
        return AnchorResult(anchor="structural_skeleton", applicable=True, verdict=INCONCLUSIVE,
                            detail=f"skeleton reflects {commit_ref}, not the task's current head {contract.head} -- stale")
    subject = claim.payload.get("subject")
    target = claim.payload.get("target")
    true_calls = set(world.call_graph.get(commit_ref, {}).get(subject, []))
    true_val = target in true_calls
    asserted = bool(claim.payload.get("asserted"))
    return AnchorResult(anchor="structural_skeleton", applicable=True,
                        verdict=AGREES if asserted == true_val else CONTRADICTS,
                        detail=f"true call graph at {commit_ref}: {subject} calls {sorted(true_calls)}")


ANCHORS: Dict[str, Callable[[Claim, TrustedWorld], AnchorResult]] = {
    "internal_consistency": internal_consistency,
    "fresh_execution": fresh_execution,
    "approval_ledger": approval_ledger,
    "repo_baseline": repo_baseline,
    "actor_identity": actor_identity,
    "structural_skeleton": structural_skeleton,
}

# The single claim-appropriate anchor for each claim type.
CLAIM_ANCHOR = {
    ClaimType.EXECUTION: "fresh_execution",
    ClaimType.AUTHORIZATION: "approval_ledger",
    ClaimType.STATE: "repo_baseline",
    ClaimType.IDENTITY: "actor_identity",
    ClaimType.STRUCTURE: "structural_skeleton",
}


def anchor_matrix(cases: List[Claim], world: TrustedWorld) -> Dict[str, Dict[str, str]]:
    """case.label -> {anchor -> verdict} for every anchor (the coverage matrix)."""
    out: Dict[str, Dict[str, str]] = {}
    for c in cases:
        out[f"{getattr(c,'flagship','?')}:{c.label}"] = {
            name: fn(c, world).verdict for name, fn in ANCHORS.items()
        }
    return out


__all__ = ["AnchorResult", "ANCHORS", "CLAIM_ANCHOR", "anchor_matrix",
           "internal_consistency", "fresh_execution", "approval_ledger", "repo_baseline",
           "actor_identity", "structural_skeleton", "AGREES", "CONTRADICTS", "INCONCLUSIVE"]
