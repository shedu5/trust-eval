"""Runnable deterministic demonstration of the Study C central result.

    python -m trust_eval.study_c

Shows (1) the anchor coverage matrix — internal-consistency catches none of the
self-consistent forgeries, and only the claim-appropriate anchor catches each —
and (2) per-protocol false-acceptance / false-rejection / abstention, with no
model call.
"""

from __future__ import annotations

from typing import Dict, List

from .anchors import ANCHORS, CLAIM_ANCHOR
from .protocols import ACCEPT, CANNOT_VERIFY, PROTOCOLS, REJECT, decide
from .surrogates import flagship_cases
from .world import build_flagship_world


def _anchor_matrix_lines(cases, world) -> List[str]:
    names = list(ANCHORS.keys())
    header = f"{'attack case':<34}" + "".join(f"{n[:16]:>18}" for n in names)
    lines = ["ANCHOR COVERAGE MATRIX (attacks only — 'contradicts' = caught)", header, "-" * len(header)]
    for c in cases:
        if c.should_accept:
            continue
        row = f"{c.flagship + ':' + c.label:<34}"
        for n in names:
            v = ANCHORS[n](c, world).verdict
            mark = {"contradicts": "CAUGHT", "agrees": "miss", "inconclusive": "n/a"}[v]
            row += f"{mark:>18}"
        lines.append(row)
    lines.append("")
    lines.append("claim-appropriate anchor per type: " +
                 ", ".join(f"{k.value}->{v}" for k, v in CLAIM_ANCHOR.items()))
    return lines


def _score_lines(cases, world) -> List[str]:
    attacks = [c for c in cases if not c.should_accept]
    truthful = [c for c in cases if c.should_accept]
    header = f"{'protocol':<30}{'FA (accept false)':>20}{'FR (reject true)':>20}{'abstain':>10}"
    lines = ["", "PER-PROTOCOL OUTCOMES", header, "-" * len(header)]
    for p in PROTOCOLS:
        fa = sum(1 for c in attacks if decide(p, c, world).false_accept(c))
        fr = sum(1 for c in truthful if decide(p, c, world).false_reject(c))
        ab = sum(1 for c in cases if decide(p, c, world).outcome == CANNOT_VERIFY)
        lines.append(f"{p:<30}{f'{fa}/{len(attacks)}':>20}{f'{fr}/{len(truthful)}':>20}{ab:>10}")
    return lines


def main() -> int:
    world = build_flagship_world()
    cases = flagship_cases()
    for ln in _anchor_matrix_lines(cases, world):
        print(ln)
    for ln in _score_lines(cases, world):
        print(ln)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
