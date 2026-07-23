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
    true_diff = set(world.diff(contract.approved_baseline, contract.head))
    asserted = set(claim.payload.get("asserted_changed", []))
    return AnchorResult(anchor="repo_baseline", applicable=True,
                        verdict=AGREES if asserted == true_diff else CONTRADICTS,
                        detail=f"true diff vs approved baseline {contract.approved_baseline}: {sorted(true_diff)}")


ANCHORS: Dict[str, Callable[[Claim, TrustedWorld], AnchorResult]] = {
    "internal_consistency": internal_consistency,
    "fresh_execution": fresh_execution,
    "approval_ledger": approval_ledger,
    "repo_baseline": repo_baseline,
}

# The single claim-appropriate anchor for each claim type.
CLAIM_ANCHOR = {
    ClaimType.EXECUTION: "fresh_execution",
    ClaimType.AUTHORIZATION: "approval_ledger",
    ClaimType.STATE: "repo_baseline",
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
           "AGREES", "CONTRADICTS", "INCONCLUSIVE"]
