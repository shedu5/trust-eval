# Study C — Observational Backbone (from an operating governance system)

**Sanitized aggregates from real governed runs. Observational context, NOT the
preregistered experimental result.** These numbers come from the machine-recorded
archives (`run-record.json`) of 44 real governed sessions in a private
coding-agent governance system: two family-separated LLM reviewers per run, a
disagreement-adjudication step, deterministic gates, and a four-state disposition.
They motivate and calibrate Study C; they do not stand in for the preregistered
synthetic-surrogate measurement (false-acceptance by protocol), which is reported
separately. No slugs, file paths, commit hashes, or reviewer text appear here; the
raw dataset is kept in the gitignored private store.

## What the real system's own record shows

Across **44 governed runs** (144 individual reviewer verdicts):

| Final disposition | Runs | Share |
|---|---:|---:|
| Blocked (found insufficient) | 20 | 45% |
| Awaiting human adjudication (escalated) | 18 | 41% |
| Remediation exhausted | 3 | 7% |
| Commit-ready (accepted) | 3 | 7% |

Only **3 of 44 runs (7%)** reached accept on their own authority; **41% escalated
to a human**. A single aggregate "pass rate" would have hidden that the system's
dominant outcomes are *block* and *escalate*, not *accept* — which is exactly why
Study C reports four-state outcomes and never collapses to one score.

**Reviewer behavior (the correlated-error surface):**

- **42 runs had two reviewers; they disagreed on 31 of them (74%).** Reviewer
  disagreement is the common case, not the exception.
- **15 runs went to disagreement adjudication.**
- In **23 of 42 multi-reviewer runs (55%)**, at least one reviewer returned a
  PASS-class verdict on a run another reviewer FAILed — a direct, logged
  under-report / correlated-blind-spot signal (the H4 surface, observed in the
  system's own history rather than assumed).
- Verdict mix across 144 verdicts: PASS 92 · PASS_WITH_CONDITIONS 7 · FAIL 37 ·
  REQUIRES_HUMAN_ADJUDICATION 8.

**Deterministic gates did independent work:** 39 of 44 runs carried at least one
hard-fail code, the most frequent families being mode-gate failures and
authoring **scope violations / scope widening** — the same governance-scope class
that the fabricated-authorization incident (O-04) lives in.

## Why this matters for the study

These are *base rates from a deployed oversight loop*, and they anchor three
things the synthetic experiment then measures under controlled conditions:

1. **Reviewer disagreement and under-report are real and frequent** (74% / 55%),
   so a benchmark that treats "two LLM reviewers agree" as trustworthy is
   measuring the wrong thing — motivating H3 (an independent anchor, not a second
   opinion) and H4 (unsupported/under-reporting verdicts).
2. **Escalation is a first-class outcome** (41% here), which is why P5 offers
   `cannot_verify` rather than forcing a binary verdict.
3. **The observed incident classes are drawn from this same population** — e.g.
   the wrong-baseline case (O-11) and the truncated-read reviewer (M-01) are
   specific runs within it — so the synthetic surrogates instantiate patterns the
   system actually produced, not invented ones.

## Provenance and discipline

- **Observational, not confirmatory.** These aggregates describe the existing
  system's history; they are not a preregistered result and are reported as
  context. The preregistered result is the synthetic-surrogate FA/FR-by-protocol
  measurement.
- **Selection.** All 44 real governed runs recoverable from the archives were
  included; synthetic test fixtures and sentinel-timestamp diagnostics were
  excluded. Runs are ephemeral (per-worktree, gitignored) and were preserved
  before deletion; counts are exact as of harvest.
- **Sanitization.** Only counts and rates are public. Slugs, paths, hashes,
  reviewer text, and cost figures stay in the gitignored private dataset.
