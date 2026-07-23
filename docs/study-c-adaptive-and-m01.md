## Study C — Adaptive Best-of-N Attacker and M-01 (PUBLIC)

Scored against the `adaptive:` block and H4 in
[`preregistration.yaml`](../preregistration.yaml). See
[`study-c-principal-result.md`](study-c-principal-result.md) for the static
(single-shot) ladder and paired McNemar comparisons this extends.

### Adaptive best-of-N attacker

Corpus: scaled, n=10 instances/pattern. Targets three flagship patterns:
`fabricated_authorization` and `wrong_baseline_proof` (the two closest to the
preregistered `target_classes`, `approval_replay` and
`external_state_divergence`), plus `execution` (`stale_after_drift` /
`unverifiable_false`) — added after an initial live run showed a judge's
entire measured static false-acceptance concentrated there, which the
preregistered target_classes alone would not have tested (see the "why
execution was added" note below). Budgets 1/4/8; the attacker sees only each
attempt's own verdict/reason — never ground truth or anchor output.

**Deterministic, vs. the anchor (P3):**

| Claim type | budget=1 | budget=4 | budget=8 |
|---|---|---|---|
| execution | 0/20 | 0/20 | 10/20 (via truth-only) |
| authorization | 0/10 | 0/10 | 0/10 |
| state | 0/10 | 0/10 | 10/10 (via truth-only) |

Authorization is architecturally immune at every budget — the anchor never
reads the fields the templates escalate. Execution and state can only be
"evaded" once the search reaches attempt 7/8, where the crafted payload is
bit-for-bit identical to the true command result / diff: the anchor cannot be
tricked, only satisfied by literal truth.

**Live, vs. DeepSeek and Gemini** (all 60 attack instances × 3 claim types,
cache-only reproduction after the live run — no key needed to re-verify):

| Judge | claim type | budget=1 | budget=4 | budget=8 |
|---|---|---|---|---|
| DeepSeek | execution | 5/20 (0 truth) | 11/20 (0 truth) | **18/20 (15 still-false, 3 truth)** |
| DeepSeek | authorization | 0/10 | 0/10 | 0/10 |
| DeepSeek | state | 0/10 | 0/10 | 9/10 (9 truth) |
| Gemini | execution | 0/20 | 0/20 | 0/20 |
| Gemini | authorization | 0/10 | 0/10 | 0/10 |
| Gemini | state | 0/10 | 0/10 | 3/10 (3 truth) |

**This is the headline finding of the adaptive milestone.** DeepSeek's
false-acceptance rate on execution claims does not sit still at its static
(attempt-1) value of 5/20 (25%, exact 95% CI [0.09,0.49]) — it climbs to
11/20 (55%, [0.32,0.77]) at budget 4 and 18/20 (90%, [0.68,0.99]) at budget 8,
and **15 of those 18** are still-false claims the judge accepted purely
because the fabricated justification escalated (re-ran locally, matches every
prior run, "verified independently"), not because the claim became true —
only 3 of the 18 acceptances coincide with the payload converging on the real
result. Persistence alone, with no new evidence, roughly quadruples DeepSeek's
exploitable surface on this claim type (75% still-false acceptance, exact CI
[0.51,0.91], vs. the 25% static baseline). On authorization and state,
DeepSeek shows the opposite pattern: 0% false acceptance at every budget, and
its only state acceptances (9/10 at budget 8) are truth-convergent, matching
the anchor's own invulnerability almost exactly. A judge's apparent
robustness on one claim type does not generalize to another, and a single-shot
static measurement understates exploitability wherever it doesn't hold.

Gemini shows no execution acceptances at any budget — consistent with its
20/20 static false-rejection rate there (see the breakdown table below):
zero false acceptance achieved by rejecting everything is not verification,
it is blanket suspicion, and escalating justification text cannot move a
judge that isn't reading it as evidence either way. Gemini's 3/10
truth-convergent state acceptances at budget 8 (vs. DeepSeek's 9/10) is the
same story: even the literally true claim gets rejected most of the time.

**Why execution was added:** the static ladder (principal result) reported
DeepSeek's aggregate FA as 5/40 across all three flagship patterns pooled. A
per-claim-type breakdown of those same cached responses (`breakdown.py`)
localized it entirely to execution:

| Judge | claim type | FA | FR |
|---|---|---|---|
| DeepSeek | execution | 5/20 [0.09,0.49] | 10/20 [0.27,0.73] |
| DeepSeek | authorization | 0/10 [0.00,0.31] | 10/20 [0.27,0.73] |
| DeepSeek | state | 0/10 [0.00,0.31] | 8/20 [0.19,0.64] |
| Gemini | execution | 0/20 [0.00,0.17] | **20/20 [0.83,1.00]** |
| Gemini | authorization | 0/10 [0.00,0.31] | 10/20 [0.27,0.73] |
| Gemini | state | 0/10 [0.00,0.31] | 14/20 [0.46,0.88] |

The preregistered `target_classes` (authorization, state) alone would have
reported 0/10 evasion at every budget for both judges and closed the
milestone on a technically-true but uninformative result. Extending to
execution is what surfaced the escalation effect above.

### M-01 — unsupported verification claims (H4)

Scanned all 100 cached P1 decisions per judge (200 total) for language
claiming an action P1 cannot structurally perform (running a command,
inspecting the repo, consulting the ledger):

| Judge | decisions scanned | flagged |
|---|---|---|
| DeepSeek | 100 | 0 (0.000) |
| Gemini | 100 | 0 (0.000) |

**H4 not confirmed in this run.** Neither judge's stated reasoning claimed a
check it could not have performed — including on the cases where DeepSeek's
*verdict* was wrong (the execution false-accepts above). The error mode
observed here is a wrong conclusion stated plainly, not a fabricated
verification claim. This is a genuine negative result on H4 for these two
judges on this corpus, not a null run: `run_m01` returns per-hit detail
(pattern + verbatim reason), so a future run against different judges,
prompts, or claim types has somewhere to actually surface a hit rather than
silently passing.

Scope note: M-01 only scans P1's free-text LLM reasoning. The deterministic
protocols' `detail` strings are template-generated by this codebase, not
model output, so scanning them would not be a meaningful test of H4.
