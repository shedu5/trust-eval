"""Study C — Evidence Integrity Under a Hostile Executor.

The public, runnable core: a trusted world (the independent anchors), three
flagship surrogate tasks that instantiate observed incident patterns with no
private code, an anchor matrix, and the P0-P5 oversight protocols. The central
result is demonstrable deterministically, without any model call: deterministic
internal-consistency accepts every self-consistent forgery, and only the
claim-appropriate independent anchor recovers the truth.
"""

from .world import TrustedWorld, Claim, ClaimType, build_flagship_world
from .surrogates import Case, flagship_cases
from .anchors import ANCHORS, AnchorResult, anchor_matrix
from .protocols import Decision, decide, PROTOCOLS

__all__ = [
    "TrustedWorld", "Claim", "ClaimType", "build_flagship_world",
    "Case", "flagship_cases", "ANCHORS", "AnchorResult", "anchor_matrix",
    "Decision", "decide", "PROTOCOLS",
]
