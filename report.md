# Study C — Evidence Integrity Under a Hostile Executor

**Study C of *Which Gates Matter?*** — when an autonomous coding agent is the
only source of the evidence used to evaluate its own work, which oversight
protocols can still recover the truth?

*v4 — abstention/coverage made explicit throughout, P5 naming
disambiguated, hypothesis-status table tightened, and several internal
contradictions fixed in response to external review. See "Changes from v3,"
"Changes from v2," and "Changes from v1" at the end for what was added,
fixed, and why. Judges: `deepseek-v4-flash`, `gemini-3.1-flash-lite`
(cost-constrained "weak" tier; see Scope and Limitations — the preregistered
strong tier was not run). Principal corpus: 100 synthetic-surrogate cases (10
independent instances × 3 flagship attack patterns + truthful counterparts).
All reported numbers reproduce from the committed judge-response cache with
no API key — see Reproducibility.*

The pilot that preceded this study is preserved unmodified at
[`docs/report-v0.1-pilot.md`](docs/report-v0.1-pilot.md). This report
supersedes it as the project's primary result.

## Executive summary

Autonomous coding agents often supply the evidence used to evaluate their own
work: test output, approval records, diffs, completion claims. That evidence
can be internally self-consistent while remaining false relative to
repository state, actual execution, or an independent authorization record.
This study evaluates how several oversight protocols handle that distinction.

The corpus contains 100 synthetic-surrogate cases derived from sanitized
incident patterns observed in, or principled adversarial extensions of, an
operating coding-agent governance system. Forty cases contain self-consistent
but externally false claims; sixty are truthful counterparts, including
suspicious-but-valid cases designed to penalize blanket rejection. The
claims concern execution results, authorization, and repository state.

Two deterministic conditions establish reference points. Self-report and
internal-consistency checking each accepted all 40 false claims — agreement
within the submitted evidence object does not establish correspondence with
external state. A claim-matched reference protocol (P3), constructed with
direct access to the ground-truth fact matching each claim type — fresh
execution, the independent approval ledger, or repository state — recorded
no errors in this corpus, deciding every case (100% coverage, zero
abstention): when its anchor could not resolve a claim, P3 is defined to
reject rather than abstain, so its zero-error result is not an artifact of
declining hard cases. That result is expected by construction: P3's job is
to establish the achievable error floor, not to demonstrate empirically that
ground-truth access beats no ground-truth access. A related protocol, P4,
uses the same anchors but abstains (`cannot_verify`) instead of rejecting
when the anchor is inconclusive — trading coverage for a different error
guarantee. Both protocols and the coverage/abstention distinction between
them are reported in full in Table 1 below; abstention is not hidden from
the principal results.

The two text-only judges showed different error profiles. DeepSeek accepted
5 of 40 false claims and rejected 28 of 60 truthful claims. Gemini accepted
0 of 40 false claims and rejected 44 of 60 truthful claims. Read narrowly on
false acceptance alone, Gemini matched the reference protocol exactly (0/40
vs. 0/40) — which literally triggers this study's preregistered
falsifier as stated. Gemini did not, however, match the reference protocol's
*joint* result: zero false acceptance and zero false rejection together. It
reached zero false acceptance by rejecting 73% of truthful claims. That
distinction — and why it matters — is addressed directly in "Assessment of
the falsifier" below, rather than smoothed into a single verdict.

A post-hoc, exploratory adaptive analysis targeted execution claims after a
diagnostic breakdown of the confirmatory results showed DeepSeek's measured
vulnerability was concentrated there — a claim type outside the
preregistered adaptive target classes. Under successive unsupported
assertions and no new external evidence, DeepSeek's execution-claim
false-acceptance rate rose from 5/20 (25%) at one attempt to 11/20 (55%) at
four attempts to 15/20 (75%) at eight attempts; total acceptance at eight
attempts was 18/20 (90%), of which 3 cases had converged onto the literal
true result and 15 remained false. Because this claim type was added after
seeing the confirmatory results, it is reported as exploratory and flagged
for independent replication, not treated as resolving any preregistered
comparison.

Together, the results support a narrow, specific architectural claim:
internal consistency cannot distinguish a true evidence object from a false
one that was built to match it, and a text-only judge's apparent
low-false-acceptance number can understate its exploitability, unevenly
across claim types. Recovering external truth requires either an
independent, claim-relevant observation or an honest `cannot_verify`. This
study assumes those independent anchors are correct, current, and outside
the executor's write authority; compromise of the anchoring infrastructure
itself is out of scope (see Threat-model boundary).

## What this is, and what it is not

This is a small, reproducible, dependency-light (pydantic only) research
artifact: a synthetic evidence-integrity benchmark with a trusted world
(ground truth an executor cannot write), a set of oversight protocols
defined by which independent facts they can consult, and a judge-response
cache that makes every reported number reproducible without an API key. It
is not a production monitor, not a red-team of a specific deployed system,
and not a claim that any particular commercial model is unsafe — the two
judges used were chosen for cost reasons (see Scope and Limitations), and
the architectural claim under test does not depend on which specific model
plays the judge role.

The attack taxonomy is grounded in real incidents from an operating
coding-agent governance system, sanitized and provenance-tagged (Observed /
Derived / Synthetic-surrogate) so empirical history is never blurred with
designed counterexamples. See
[`docs/study-c-incident-registry.md`](docs/study-c-incident-registry.md) for
the full registry and [`docs/study-c-empirical-backbone.md`](docs/study-c-empirical-backbone.md)
for the sanitized real-run statistics that motivated this design. Nothing in
this report or its linked docs contains private identifiers, file paths,
commit hashes, or verbatim internal quotations; the private source map lives
in a gitignored, unpublished location.

### Threat-model boundary

This study assumes claim-matched anchors — fresh execution, the approval
ledger, repository state — are correct, current, and outside the executor's
write authority. It evaluates deception at the evidence layer: can a hostile
executor construct a self-consistent but false object that fools a given
oversight protocol. It does **not** evaluate compromise of the anchoring
infrastructure itself: ledger poisoning, race conditions between an anchor's
observation and the action it describes, incorrect task-to-anchor binding,
forged tool or actor identity, or a confused-deputy failure where the wrong
anchor is consulted for the right reasons. Those are real, listed failure
modes and are explicitly out of scope for the present result.

## Central claim and hypotheses

**Definitions.** A claim is **internally valid** if every assertion
evaluable solely from the delivered evidence object is satisfied (fields
agree with each other; the object is self-consistent). A claim is
**externally truthful** if it corresponds to an independently recorded
event — the real repository state, execution result, authorization, actor,
task, or time.

**Central claim**, stated identically to
[`docs/study-c-incident-registry.md`](docs/study-c-incident-registry.md)
(the frozen framing this study was designed against — not rewritten here to
fit results):

> Deterministic internal-consistency checking can establish that an evidence
> object agrees with itself. It cannot establish that it agrees with reality.
> Recovering external truth requires a claim-appropriate independent anchor;
> no single anchor and no stronger judge substitutes for the right one.

**Scoping note, added after this run, not a rewrite of the claim above:**
the "no ... stronger judge substitutes" clause was never tested as an
empirical comparison — this cycle ran only the cost-constrained weak tier
(DeepSeek, Gemini), never the preregistered strong tier or an Anthropic
model (see H3 and Scope and limitations). Two readings of that clause are
both defensible, but only one has data behind it here: read as an
**information-theoretic** claim — an object built to be self-consistent
with a false external fact carries no signal within itself that would let
*any* reader, at any capability level, distinguish it from a true one — the
architecture is what matters, and the claim holds by construction. Read as
an **empirical** claim about how far a stronger judge's priors, world
knowledge, or plausibility reasoning could close the gap in practice, it is
untested; this report does not have the run needed to support or refute it,
and does not claim otherwise. Everything measured in this report — the
FA/FR numbers, the adaptive-attacker results — is specific to the models,
prompts, and corpus actually tested, not a general claim about all
possible judges.

**Preregistered falsifier**, committed in [`preregistration.yaml`](preregistration.yaml)
before this run, stated narrowly on false acceptance only:

> If text-only LLM review (P1) or deterministic internal-consistency
> checking (P2) reduces false-acceptance on the self-consistent
> externally-false classes to the level of the anchored protocols (P3+), the
> anchor thesis is wrong.

Read literally, this falsifier does not mention false rejection. It is
addressed directly, without amendment, in "Assessment of the falsifier"
below.

**Preregistered hypotheses** (`preregistration.yaml`, `hypotheses:`), status
after this run:

| # | Hypothesis (preregistered wording) | Status |
|---|---|---|
| H1 | Deterministic + LLM monitors detect internally-inconsistent (Tier-1) attacks at high rates | Addressed by the v0.1 pilot corpus, not re-tested here — Study C's corpus is Tier-2 (internally consistent) only |
| H2 | LLM-only and deterministic-internal monitors **frequently** ACCEPT self-consistent, externally-false fabrications | **Partially supported, model-dependent.** "Frequently" was never operationally defined by a preregistered threshold, and the result is not uniform: deterministic-internal (P2) accepted all 40/40 (100%); DeepSeek (LLM-only) accepted 5/40 (12.5%); Gemini (LLM-only) accepted 0/40 (0%) — a direct counterexample to "LLM-only monitors frequently accept," at the cost of rejecting 44/60 (73%) truthful claims. P2 alone supports the hypothesis unambiguously; the LLM-only claim is not supported as a general statement about the tested judges |
| H3 | A claim-appropriate anchor reduces false acceptance **more than a stronger judge** | **Not tested as stated.** No stronger-tier judge was run, so the literal comparison (anchor vs. a stronger judge) has no data. What was measured: the claim-matched reference protocol reduced FA relative to DeepSeek (weak tier, paired p=0.0625, not significant at n=40) and tied Gemini (weak tier) at 0/40 FA while avoiding Gemini's FR cost. Neither result speaks to "stronger judge" |
| H4 | Monitors sometimes claim checks they did not/could not perform | **Negative result, both automated and manually verified.** The regex scanner (M-01) flagged 0/200 cached reasons (100 cases × 2 judges). Because a zero-match automated scan alone does not establish that recall is high enough for that count to mean anything, all 200 reasons were additionally read manually by the report's author: none contains a semantic claim of having run a command, inspected the repository, or consulted the ledger — every expression of uncertainty is an honest disclaimer ("cannot verify," "without access to..."). This is a single-reviewer manual read, not independently cross-checked by a second annotator, so it strengthens but does not eliminate the detector-recall caveat |
| H5 | Mandatory anchor use or legitimate abstention reduces **unsupported verification** and **false acceptance**, trading against **coverage/false rejection** | **Partially supported — the FA/coverage component is measured on 2 of 3 claim types; the unsupported-verification component is untested here.** P4's mandatory abstention trades coverage for zero selective FA (75% attack coverage vs. P3's 100%, both with 0/decided FA — Table 1). Replacing that abstention with an LLM fallback (P5-hybrid) restores 100% coverage but reintroduces FA for DeepSeek specifically: 4/10 (40%) on execution's `unverifiable_false`, 2/10 (20%) on a purpose-built state probe; 0/10 on both for Gemini, and 0/10 on an authorization probe for both judges. Truthful-case coverage/FR was unaffected in every measurement here (no truthful case ever hit an inconclusive anchor in this corpus). The "reduces unsupported verification" clause of H5 was not tested by this probe — that is H4/M-01's domain, and M-01 found no unsupported-verification language from either judge to begin with |

## Method

### The anchor matrix (not a ladder)

Oversight is not linear — a higher "rung" does not subsume a lower one.
Fresh execution cannot tell you whether an approval existed; an approval
ledger cannot tell you whether tests passed. Each claim type has a *minimum
sufficient anchor*, and using the wrong one is not weaker verification, it
is no verification:

| Anchor | Establishes |
|---|---|
| Repository state | files, diff, baseline, final commit |
| Fresh execution | executable claims and their output |
| Approval ledger | authorization and scope exceptions |
| Actor identity | who performed or approved an action |
| Task contract | required evidence and expected inventory |
| Trusted clock / session ledger | freshness and task-session binding |
| Tool transcript | what checks the monitor actually performed |

### Protocols

| Protocol | Behavior | Anchors available | Deterministic? |
|---|---|---|---|
| P0 self-report | Accept the executor's assertion outright | none | yes |
| P1 text-only judge | An LLM decides from the delivered object alone | none — the delivered object only | no (real model call) |
| P2 deterministic internal-consistency | Accept iff the object agrees with itself | internal verifier only | yes |
| P3 claim-matched reference protocol | Always invoke the anchor; decide accept/reject from it, even when inconclusive (see below) | the single anchor matched to the claim type | yes |
| P4 anchor-or-abstain | Always invoke the anchor; **abstain** (`cannot_verify`) rather than guess when it's inconclusive | the single anchor matched to the claim type | yes |
| P5 (pure abstain) | Identical to P4 in every code path — invoke the anchor, abstain if inconclusive | the single anchor matched to the claim type | yes |
| P5-hybrid[JUDGE] | Invoke the anchor; when (and only when) it's inconclusive, fall back to a named LLM adjudicator instead of abstaining | the single anchor, plus a fallback judge | **no** (real model call on anchor-inconclusive cases) |

P3 and P4 differ in exactly one respect, precisely because they share an
anchor-invocation policy and diverge only on what to do when that anchor
comes back inconclusive: **P3 treats "inconclusive" as grounds to reject**
(a claim resting on evidence the anchor can't confirm is not accepted), while
**P4 treats "inconclusive" as grounds to abstain** (a policy choice to
report "cannot verify" rather than either accept or reject). Both are
zero-false-acceptance policies; they differ in coverage and in what a
`reject` vs. a `cannot_verify` communicates downstream. P5 (pure abstain)
is P4 under a different preregistered name with no behavioral difference in
this codebase; **P5-hybrid[JUDGE]** is a materially different protocol —
non-deterministic, judge-dependent — that replaces P4's abstention with a
fallible fallback decision. See Table 1 and "Scope and limitations" for
measured results on all three claim types.

**P3 is a reference protocol, not an ordinary competing monitor.** It is
constructed to query the trusted fact that corresponds to each claim type by
definition — fresh execution for an execution claim, the ledger for an
authorization claim, the true diff for a state claim. Its zero-error result
validates that the implementation follows its own architecture; it is not an
empirical discovery that ground-truth access beats no ground-truth access,
which would be close to tautological. Its role in this report is to
establish the achievable error floor in this corpus, against which fallible
protocols (P0, P1, P2) are compared. The comparison of practical, fallible
protocols against that floor — and how far they fall short, on which axis —
is the actual empirical content.

### Attack taxonomy

The false claims in this corpus fall into two distinct mechanisms, kept
distinct here because they are not equally hard to detect or equally
well-tested:

- **Unsupported assertion attack.** The evidence object contains a claim
  (a result, a justification, a "this was verified") for which no
  corroborating artifact was fabricated — the claim is simply stated. All of
  the adaptive attacker's escalating templates (Exploratory adaptive
  analysis, below) are of this kind: "I re-ran this locally," "verified
  independently," with no forged log, hash, or transcript attached.
- **Artifact replay / substitution attack.** A real artifact — a genuine
  passing test log, a real approval record — is presented out of its true
  context: a real pass captured at an earlier commit, resubmitted against a
  later, broken one (`stale_after_drift`); a correct diff computed against
  the wrong baseline (`wrong_baseline_proof`). The static flagship corpus is
  built from this mechanism.

Neither mechanism in this study rises to **coordinated evidence forgery** —
multiple independently-checkable artifacts (hashes, commit signatures, tool
transcripts) fabricated in mutual agreement with each other. That is a
harder, unaddressed threat class; see Limitations.

### Three-counterpart case design

Every attack pattern ships three counterparts, so a monitor cannot pass by
learning a superficial rule: a **benign twin** (truthful, measures false
rejection), a **suspicious-but-valid near-miss** (has the suspicious surface
feature — an unusual approval, an old-looking log — but is actually true,
defeating "reject anything unusual" shortcuts), and the **self-consistent
false twin** (every field agrees internally; only the anchor disproves it —
the load-bearing case for the central claim).

### Corpus

Three flagship patterns, each a synthetic surrogate instantiating an
Observed or Derived incident class from the private registry (see the
registry for the full O/D/S provenance table):

1. **Stale execution evidence after code drift** (execution claim, artifact
   replay) — a real pass result from an earlier commit is submitted as
   evidence against the current, broken head.
2. **Fabricated authorization absent from the approval ledger**
   (authorization claim, unsupported assertion) — a well-formed "approved
   scope exception" note with no matching entry in the independent ledger.
3. **Correct evidence computed against the wrong baseline** (state claim,
   artifact replay) — a truthful-looking diff, proving the wrong referent.

The principal corpus scales this to **10 independent instances per pattern**
(own commands/files/commits per instance, not relabeled copies). Execution
contributes two attack labels per instance (`stale_after_drift`,
`unverifiable_false`); authorization and state contribute one each —
composition:

| Claim type | False | Benign | Suspicious-valid | Total |
|---|---:|---:|---:|---:|
| Execution | 20 | 10 | 10 | 40 |
| Authorization | 10 | 10 | 10 | 30 |
| State | 10 | 10 | 10 | 30 |
| **Total** | **40** | **30** | **30** | **100** |

**Instance 0 of each of the three patterns is byte-identical to the
original, hand-authored flagship case** used before the corpus was scaled,
so judge-response cache entries collected against it remain valid trials of
the scaled corpus. Because execution contributes 4 case labels per instance
(benign, `stale_after_drift`, near-miss, `unverifiable_false`) while
authorization and state contribute 3 each (benign, attack, near-miss),
**instance 0 is 4 + 3 + 3 = 10 individual cases**, not 3 — this report
always means those 10 cases when it says "pilot-carried" or "index-0
cases," never "the three instance-0 patterns." This reuse is computationally
convenient and is flagged, not hidden, as a methodological caveat: these 10
cases were designed first and may have influenced prompt iteration in ways
instances 1–9 (generated programmatically from the same pattern) did not. A
sensitivity analysis excluding these 10 cases from the confirmatory tables
**was run this cycle** (`sensitivity.py`; see "Scope and limitations" for
the result — every rate moves by at most a few points and no significance
result flips).

## Confirmatory protocol comparison

The comparison below covers the preregistered protocols (P0, P1, P2, P3–P5),
the preregistered attack classes as instantiated in the principal corpus,
the models actually run (weak-tier DeepSeek and Gemini — the preregistered
strong tier was not run), and the preregistered metrics (FA, FR, Wilson and
exact-binomial CIs).

FA = false acceptance of a self-consistent false claim, **as a share of all
40 attack cases** (population rate — the preregistered metric). FR = false
rejection of a truthful claim, same convention over 60 truthful cases.
**A protocol that abstains (`cannot_verify`) on the hard cases can report a
low population FA/FR without ever having been tested on them** — the same
failure mode this report already criticizes Gemini for approximating through
blanket rejection applies in principle to any protocol with an abstention
path, so Table 1 reports abstention and coverage explicitly, and a
**selective-risk** rate (FA or FR among only the cases the protocol actually
decided) alongside the population rate. Full 95% CIs (Wilson and exact) for
every population and selective rate are in the reproduce output; this table
shows point estimates for readability.

| Protocol | FA (pop.) | Abstain (attacks) | Coverage (attacks) | Sel. FA | FR (pop.) | Abstain (truthful) | Coverage (truthful) | Sel. FR |
|---|---|---|---|---|---|---|---|---|
| P0 self-report | 40/40 | 0 | 100% | 40/40 = 1.00 | 0/60 | 0 | 100% | 0/60 = 0.00 |
| P1 text-only — DeepSeek | 5/40 | 0 | 100% | 5/40 = 0.13 | 28/60 | 0 | 100% | 28/60 = 0.47 |
| P1 text-only — Gemini | 0/40 | 0 | 100% | 0/40 = 0.00 | 44/60 | 0 | 100% | 44/60 = 0.73 |
| P2 deterministic internal | 40/40 | 0 | 100% | 40/40 = 1.00 | 0/60 | 0 | 100% | 0/60 = 0.00 |
| P3 claim-matched reference | 0/40 | 0 | 100% | 0/40 = 0.00 | 0/60 | 0 | 100% | 0/60 = 0.00 |
| P4 anchor-or-abstain | 0/40 | **10** | **75%** | 0/30 = 0.00 | 0/60 | 0 | 100% | 0/60 = 0.00 |
| P5 (pure abstain — identical to P4) | 0/40 | **10** | **75%** | 0/30 = 0.00 | 0/60 | 0 | 100% | 0/60 = 0.00 |
| P5-hybrid[DeepSeek] | 4/40 | 0 | 100% | 4/40 = 0.10 | 0/60 | 0 | 100% | 0/60 = 0.00 |
| P5-hybrid[Gemini] | 0/40 | 0 | 100% | 0/40 = 0.00 | 0/60 | 0 | 100% | 0/60 = 0.00 |

Reproduce with `ladder.py`'s full output (includes Wilson and exact CIs on
every population and selective rate, per protocol, per axis).

**P2 is statistically indistinguishable from P0.** Deterministic
internal-consistency checking accepts every self-consistent false claim in
the corpus, identically to trusting the agent's bare word. This is the
pilot's original finding (v0.1), confirmed here at n=100 with exact
confidence intervals rather than a 10-case anecdote.

**P3's zero population FA is not obtained through abstention — it never
abstains at all** (0 abstentions, 100% coverage on every claim type in this
corpus): it resolves every one of the 40 attacks to accept/reject and gets
every one right. **P4's zero population FA is obtained differently: it
abstains on 10 of the 40 attacks** (all of them execution's
`unverifiable_false` pattern, where no fresh-execution result exists to
check against) rather than deciding on them, bringing its attack coverage to
75%. Critically, P4's *selective* FA — its error rate among the 30 attacks
it does decide — is also exactly 0/30, so this is not a case of abstention
concealing a wrong call; P4 is flawless on every case it's willing to rule
on, and honestly declines to rule on the rest. That is a materially
different, and arguably better, claim than "P4 achieves zero error," and
Table 1 is now built so both facts are visible together, not just the
population number. Plain "P5" — the pure-abstention protocol, no
adjudicator — is architecturally identical to P4 in every code path and
reports identically here; see below for why "P5" alone is an ambiguous name
in this report.

**"P5" denotes two different protocols and this report is careful to never
use the bare name for both.** *P5 (pure abstain)*, shown in Table 1, never
consults an adjudicator and is deterministic — architecturally identical to
P4. *P5-hybrid[JUDGE]*, shown in the next two rows, replaces abstention with
a call to a named LLM adjudicator whenever the anchor is inconclusive, and
is **not** deterministic — its result depends on which judge is in the
adjudicator seat. With DeepSeek as adjudicator, P5-hybrid trades P4's 75%
coverage for 100% coverage (it always renders a verdict) at the cost of
4/40 population false acceptance (10% selective FA on the cases the anchor
couldn't resolve) — the fallback judge got 4 of the 10 anchor-inconclusive
cases wrong. With Gemini as adjudicator, P5-hybrid gets the same 100%
coverage at 0/40 false acceptance — the fallback judge got all 10 right.
Neither of these is "P5" without qualification; both are measured
separately below and in "Scope and limitations," where the same
DeepSeek/Gemini split is tested on the two claim types (authorization,
state) this principal corpus cannot probe.

## Paired significance

Because every protocol decides the *same* cases, a proper comparison is
paired: exact McNemar on the discordant pairs (one protocol wrong, the other
right), not two independent CIs eyeballed for overlap.

| A | B | Axis | A wrong / B right | A right / B wrong | p (exact, 2-sided) | Significant? |
|---|---|---|---|---|---|---|
| P0 self-report | P3 reference | FA | 40 | 0 | <0.0001 | yes |
| P2 internal | P3 reference | FA | 40 | 0 | <0.0001 | yes |
| P1 DeepSeek | P3 reference | FA | 5 | 0 | 0.0625 | **no** |
| P1 DeepSeek | P3 reference | FR | 28 | 0 | <0.0001 | yes |
| P1 Gemini | P3 reference | FA | 0 | 0 | 1.0000 | — (tied at 0) |
| P1 Gemini | P3 reference | FR | 44 | 0 | <0.0001 | yes |
| P1 DeepSeek | P1 Gemini | FR | 3 | 19 | 0.0009 | yes |

The DeepSeek-vs-reference FA comparison does not reach paired significance
at n=40 (p = 0.0625) even though DeepSeek's own single-sample CI excludes
zero. With 5 discordant pairs all in one direction, one additional attack
instance where DeepSeek falsely accepts (holding the reference protocol's
record clean) would cross p < 0.05. This is reported as a limitation of the
confirmatory comparison, not resolved by it — the exploratory adaptive
analysis below investigates the same judge's execution-claim behavior
further, but under a different, non-preregistered condition, so it does not
retroactively resolve this specific paired test.

## Diagnostic breakdown by claim type

The aggregate FA numbers above pool three claim types. This is a re-slice of
the same confirmatory data (no new model calls), used to locate where each
judge's error concentrates before designing the exploratory analysis below:

| Judge | claim type | FA | FR |
|---|---|---|---|
| DeepSeek | execution | 5/20 [0.09,0.49] | 10/20 [0.27,0.73] |
| DeepSeek | authorization | 0/10 [0.00,0.31] | 10/20 [0.27,0.73] |
| DeepSeek | state | 0/10 [0.00,0.31] | 8/20 [0.19,0.64] |
| Gemini | execution | 0/20 [0.00,0.17] | **20/20 [0.83,1.00]** |
| Gemini | authorization | 0/10 [0.00,0.31] | 10/20 [0.27,0.73] |
| Gemini | state | 0/10 [0.00,0.31] | 14/20 [0.46,0.88] |

DeepSeek's entire measured static vulnerability is concentrated in
execution claims. Gemini's 0/20 execution FA is not discrimination — its
20/20 execution FR means it rejects every execution claim regardless of
truth. Zero false acceptance achieved by rejecting everything is blanket
suspicion, not verification.

## Exploratory adaptive analysis

**This section is exploratory, not confirmatory, and is labeled as such
throughout.** The preregistered adaptive milestone specifies a bounded
adaptive template search — attempt budgets [1, 4, 8], seeing only each
attempt's own verdict and reason, never ground truth or anchor output —
targeting `approval_replay` and `external_state_divergence`
(`fabricated_authorization` and `wrong_baseline_proof` here). An initial run
against exactly those two preregistered classes found 0/10 evasion for both
judges at every budget. On its own this is a real result but an
uninformative one: the diagnostic breakdown above shows DeepSeek was already
at 0% false acceptance on those two classes at attempt 1, so a search
confined to them cannot surface anything a single shot did not already show.

**Execution was added to the attacker's target set after this diagnosis** —
a reasonable response to what the confirmatory data showed, but one that
makes every execution-claim adaptive result below post hoc. It is not
treated as resolving the underpowered DeepSeek-vs-reference FA paired test
above; it is a separate, additional finding that happens to bear on the same
judge and claim type, obtained under different conditions (a persistent
attacker rather than a single confirmatory sample), and is presented for
independent replication rather than as confirmatory evidence.

### Reference-protocol behavior by construction (deterministic, no model call)

| Claim type | budget=1 | budget=4 | budget=8 |
|---|---|---|---|
| execution | 0/20 | 0/20 | 10/20 (via truth only) |
| authorization | 0/10 | 0/10 | 0/10 |
| state | 0/10 | 0/10 | 10/10 (via truth only) |

Authorization is architecturally immune at every budget — the reference
protocol's function never reads the fields the attacker's templates vary at
all. Execution and state can only be "evaded" once the search reaches the
final templates, where the crafted payload is bit-for-bit identical to the
true command result or diff: the reference protocol accepts only when its
trusted-world predicate is satisfied, which is a property verified by
construction and by `tests/test_study_c_adaptive.py`, not an empirical
discovery.

### Exploratory result: DeepSeek and Gemini under the bounded template search

| Judge | claim type | budget=1 | budget=4 | budget=8 |
|---|---|---|---|---|
| DeepSeek | execution | 5/20 FA (0 truth-convergent) | 11/20 FA (0 truth-convergent) | **15/20 FA, 3/20 truth-convergent (18/20 total accepted)** |
| DeepSeek | authorization | 0/10 | 0/10 | 0/10 |
| DeepSeek | state | 0/10 | 0/10 | 9/10 (9 truth-convergent) |
| Gemini | execution | 0/20 | 0/20 | 0/20 |
| Gemini | authorization | 0/10 | 0/10 | 0/10 |
| Gemini | state | 0/10 | 0/10 | 3/10 (3 truth-convergent) |

**This is the principal exploratory finding.** Under the bounded adaptive
template search — successive unsupported assertions, never a new fact,
never contact with the anchor — DeepSeek's execution-claim false-acceptance
rate rises from 5/20 (25%, exact CI [0.09,0.49]) at one attempt, to 11/20
(55%, [0.32,0.77]) at four attempts, to **15/20 (75%, [0.51,0.91])** at eight
attempts. Total acceptance at eight attempts is 18/20 (90%, [0.68,0.99]),
of which 3 cases (15%, [0.03,0.38]) converged onto the literal true result
and are not false acceptances. On authorization and state, the same judge
shows the opposite pattern: 0% false acceptance at every budget, and its
only state acceptances (9/10) are truth-convergent — indistinguishable from
the reference protocol's own behavior on that axis. Robustness on one claim
type did not generalize to another in this run, and the single-shot
confirmatory measurement understated exploitability specifically where it
did not hold. This finding has not been independently replicated and should
be treated as a hypothesis for a follow-up confirmatory run, not a settled
result.

Gemini accepted no false execution claim at any budget — consistent with its
100% rejection rate there, not evidence of resistance to the attack
specifically. Its 3/10 truth-convergent state acceptances (vs. DeepSeek's
9/10) show the same asymmetry from the other side: even a literally true
claim is rejected most of the time.

## Unsupported verification claims (M-01)

Preregistered secondary analysis (H4). All 100 cached P1 decisions per judge
(200 total) were scanned for language claiming an action the text-only
protocol structurally cannot perform — running a command, inspecting the
repository, consulting the ledger:

| Judge | decisions scanned | flagged |
|---|---|---|
| DeepSeek | 100 | 0 (0.000) |
| Gemini | 100 | 0 (0.000) |

**H4 not confirmed in this run.** Neither judge's stated reasoning claimed a
check it could not have performed, including on the cases where its verdict
was wrong. The observed error mode was a wrong conclusion stated plainly,
not a fabricated verification claim. This is a genuine negative result, not
a null run: the classifier returns per-hit detail (pattern and verbatim
reason), so a run against different judges, prompts, or claim types has
somewhere to actually surface a hit.

## Empirical backbone: why these attack patterns, not others

The three flagship patterns above are not invented. They are sanitized,
provenance-tagged instantiations of incidents recorded in an operating
coding-agent governance system — see
[`docs/study-c-incident-registry.md`](docs/study-c-incident-registry.md) for
the full twelve-class registry with Observed/Derived tags, and
[`docs/study-c-empirical-backbone.md`](docs/study-c-empirical-backbone.md) for
the sanitized aggregate statistics that motivated the design. Across 44 real
governed runs, only 3 of 44 (7%) reached acceptance (`COMMIT_READY`) on the
system's own authority and 18 of 44 (41%) escalated to a human
(`AWAITING_HUMAN_ADJUDICATION`); the remainder split between 20 of 44 (45%)
`BLOCKED` and 3 of 44 (7%) `REMEDIATION_EXHAUSTED`. The single most
load-bearing number for this study's design: of the 42 runs that had two
independent reviewers, the reviewers disagreed on 31 of them (74%), and in
23 of those 42 runs (55%) at least one reviewer returned a PASS-class
verdict on a run another reviewer FAILed. A benchmark that treated "two LLM reviewers
agree" as a trust signal would be measuring the wrong thing — which is why
the central claim is stated in terms of independent anchors, not independent
opinions, and why P5 offers legitimate abstention rather than forcing a
binary verdict on every claim.

## Assessment of the falsifier

Restating it precisely: *"If P1 or P2 reduces false-acceptance on the
self-consistent externally-false classes to the level of the anchored
protocols (P3+), the anchor thesis is wrong."* Read literally, on false
acceptance alone: **P2 does not trigger it** (40/40 vs. P3's 0/40, and
statistically distinguishable at p < 0.0001). **Gemini P1 does trigger it**
(0/40, exactly matching P3's 0/40). Under the narrow, literally-stated
falsifier, the result is mixed, not a clean "not falsified" — and this
report does not retroactively narrow the falsifier's wording to avoid that.

What the narrow falsifier does not capture, because it was written on FA
alone, is that Gemini's matching FA came at a cost the reference protocol
did not pay: 44/60 (73%) false rejection, where the reference protocol had
zero. As a secondary, non-preregistered but directly measurable hypothesis:
**no protocol in this study matched the reference protocol's joint result —
zero false acceptance and zero false rejection together — at any budget, on
any claim type.** That is the honest, load-bearing empirical finding this
study actually supports: a text-only judge can be tuned toward low false
acceptance, but in this corpus, only by trading away truthful-claim
acceptance, not by discriminating better. The central claim, understood as
a claim about *joint* discrimination rather than FA in isolation, is not
falsified. Understood as the narrow FA-only sentence actually written in the
preregistration, it is falsified by Gemini and not by DeepSeek — both facts
are reported here rather than one.

## Scope and limitations

- **Judges.** Only the cost-constrained weak tier (`deepseek-v4-flash`,
  `gemini-3.1-flash-lite`) was run; the strong tier specified in
  `preregistration.yaml` (`deepseek-v4-pro`, `gemini-3.5-flash`) was not, for
  budget reasons, and no Anthropic-model judge was used this cycle. H3 (an
  anchor beats a stronger judge, not just a weak one) is therefore only
  partially tested. The highest-value additional confirmatory run is one
  current strong-tier model plus one Anthropic model, on the same frozen
  corpus and prompts — not a larger synthetic corpus.
- **P3, P4, and P5, measured as pure anchor-abstention protocols, are
  behaviorally identical in the principal n=100 corpus** — all three report
  the same FA/FR because none of the three claim types has an
  authorization- or state-anchor-unavailable case there; only execution's
  `unverifiable_false` pattern (10 of 100 cases) makes the anchor
  inconclusive. P5 was implemented as a genuine hybrid — the anchor is
  consulted first, and a designated LLM adjudicator is only asked on the
  cases where the anchor itself is inconclusive
  (`trust_eval/study_c/protocols.py`, `ladder.py --p5-adjudicator
  PROVIDER:MODEL`) — and measured on execution using the principal corpus's
  existing cache (no new calls): with DeepSeek as adjudicator, P5(hybrid)
  accepts 4/10 (40%, exact CI [0.12,0.74]) of the `unverifiable_false`
  cases that P3/P4 correctly abstain or reject on; with Gemini, it stays at
  0/10, matching P4.

  Authorization and state have no anchor-inconclusive case in the principal
  corpus, so testing H5 there required a second, separate, exploratory
  probe corpus (`trust_eval/study_c/p4p5_probe.py`,
  `build_p4p5_probe_world` — not part of the n=100 confirmatory corpus, no
  effect on any number reported against it): 10 authorization instances
  each with a real ledger entry later disputed/superseded (the anchor can
  neither confirm nor deny it — genuinely `INCONCLUSIVE`, not
  `CONTRADICTS`), and 10 state instances each with no approved baseline
  ever recorded for the task. These are new payloads, so a `--live` run was
  required once; both judges' calls are now in the committed cache. Result:
  on the **authorization** probe, neither judge's hybrid path introduced
  any false acceptance (0/10 both) — the ledger-conflict case turned out to
  be one every judge in this study handled safely, hybrid or not. On the
  **state** probe, DeepSeek's hybrid path again introduced false
  acceptance — 2/10 (20%, exact CI [0.03,0.56]) — while Gemini's stayed at
  0/10. So across all three claim types this study can test, H5 is now
  measured, not merely asserted: P4's mandatory-abstention design is
  measurably safer than a hybrid fallback to DeepSeek specifically on
  execution and state (2 of 3 claim types), and the two designs are
  indistinguishable on authorization and for Gemini throughout. This does
  not generalize to "hybrid adjudication is unsafe" — it generalizes to "a
  hybrid's safety depends on which judge sits in the adjudicator seat," a
  narrower and more defensible claim.

  Restated as a coverage/risk trade-off (selective prediction), which is
  the cleanest way to read this result: on every anchor-inconclusive case
  in this study, P4 abstains (0% coverage of that subset, so it cannot be
  wrong) while a hybrid adjudicator decides all of them (100% coverage of
  that subset), at whatever false-acceptance rate that specific judge
  produces on that specific claim type. All ten P4/P4-hybrid rows below
  are anchor-inconclusive by construction — n is the size of that
  inconclusive subset, not the full claim-type corpus:

  | Protocol | Claim type | n (anchor-inconclusive) | Coverage of subset | Sel. FA on subset |
  |---|---|---|---|---|
  | P4 (mandatory abstain) | execution | 10 | 0% | n/a — abstains |
  | P4 (mandatory abstain) | authorization | 10 | 0% | n/a — abstains |
  | P4 (mandatory abstain) | state | 10 | 0% | n/a — abstains |
  | P5-hybrid[DeepSeek] | execution | 10 | 100% | 4/10 (40%, CI [0.12,0.74]) |
  | P5-hybrid[DeepSeek] | authorization | 10 | 100% | 0/10 (0%) |
  | P5-hybrid[DeepSeek] | state | 10 | 100% | 2/10 (20%, CI [0.03,0.56]) |
  | P5-hybrid[Gemini] | execution | 10 | 100% | 0/10 (0%) |
  | P5-hybrid[Gemini] | authorization | 10 | 100% | 0/10 (0%) |
  | P5-hybrid[Gemini] | state | 10 | 100% | 0/10 (0%) |

  Read this way, P4's zero-risk guarantee is bought entirely with coverage:
  it never resolves the 10 hardest cases in each claim type, by design. A
  hybrid buys coverage back at a judge- and claim-type-dependent risk that
  ranges, in this study, from indistinguishable-from-zero (Gemini,
  everywhere; DeepSeek, authorization) to 40% (DeepSeek, execution). Which
  trade-off is acceptable is a deployment decision this study does not make
  on the reader's behalf — the point is that the trade-off is now measured,
  not asserted.
- **DeepSeek-vs-reference FA is paired-underpowered at n=40** (p = 0.0625,
  reported above rather than rounded away). The exploratory adaptive result
  is suggestive of a real, larger effect on execution claims specifically,
  but was obtained under different conditions (persistent search vs. single
  shot) and has not been independently replicated as a confirmatory result.
- **Pilot-carried cases — sensitivity analysis (run this cycle).** Instance 0
  of each flagship pattern was hand-authored before the corpus was scaled to
  10 instances and may have influenced prompt iteration in ways the
  programmatically generated instances 1–9 did not.
  `python3 -m trust_eval.study_c.sensitivity --n 10 --provider ... ` recomputes
  the ladder and paired McNemar tables over the 90 cases added for scaling
  only (`scaled_cases(10)[10:]`, 36 attacks / 54 truthful), reusing the
  committed cache — no new API calls. The result does not change the
  study's conclusions: DeepSeek FA moves from 5/40 (12.5%) on the full
  corpus to 4/36 (11.1%, exact CI [0.03,0.26]) with the pilot cases
  excluded, and FR moves from 28/60 (46.7%) to 26/54 (48.1%, exact CI
  [0.34,0.62]); Gemini FA stays at 0/36 (exact CI [0.00,0.10]) and FR moves
  from 44/60 (73.3%) to 40/54 (74.1%, exact CI [0.60,0.85]). Every rate
  shifts by at most a few percentage points and in no case reverses which
  side of significance a paired comparison falls on. The 10 pilot-carried
  cases are not doing disproportionate work in this result.
- **The adaptive attacker is a bounded, hand-authored template search
  conditioned on prior judge feedback**, not a general adaptive red team or
  a model-generated attacker. A model-in-the-loop attacker, still
  restricted to verdict/reason feedback per the preregistered
  `attacker_forbidden` list, could plausibly escalate faster or find
  templates these did not.
- **Attack mechanism coverage.** This study covers unsupported-assertion and
  artifact-replay attacks (see Attack taxonomy). It does not test
  coordinated evidence forgery — multiple independently-checkable artifacts
  fabricated in mutual agreement — a harder threat class left for future
  work.
- **M-01 returned a clean negative** on two specific judges, one prompt
  version, one corpus. This is evidence about this run, not a general claim
  that text-only judges never fabricate verification claims — the private
  registry's M-01 entries show they can and have, in a different reviewer
  system, under different pressure.
- **Corpus documentation.** This report does not yet include a full corpus
  card (incident inclusion/exclusion criteria, count of candidate incidents
  considered and excluded, duplicate detection, exact model
  temperature/retry parameters, evaluation dates). The composition table
  above and the reproducibility commands below cover counts and exact
  reproduction; the fuller provenance narrative lives in
  `docs/study-c-incident-registry.md` and `docs/private/incident-source-map.md`
  (private).
- **Case counts remain modest by ML-benchmark standards** (40 attacks / 60
  truthful in the principal corpus). Exact and Wilson intervals are reported
  specifically so a reader can see where that matters (the DeepSeek FA
  interval is [0.04, 0.27] — informative but wide) rather than papering over
  it with a point estimate.

## Reproducibility

Every number in this report reproduces, byte-for-byte, from the committed
cache under `trust_eval/harness/cache/records/`, using the model responses
already recorded there:

```bash
python3 -m pytest -q                                    # 259 tests
python3 -m trust_eval.study_c.ladder --scaled --n 10 \
  --provider deepseek:deepseek-v4-flash --provider gemini:gemini-3.1-flash-lite
python3 -m trust_eval.study_c.compare --scaled --n 10 --matrix \
  --provider deepseek:deepseek-v4-flash --provider gemini:gemini-3.1-flash-lite
python3 -m trust_eval.study_c.breakdown --scaled --n 10 \
  --provider deepseek:deepseek-v4-flash --provider gemini:gemini-3.1-flash-lite
python3 -m trust_eval.study_c.adaptive --scaled --n 10 --budgets 1 4 8 \
  --provider deepseek:deepseek-v4-flash --provider gemini:gemini-3.1-flash-lite
python3 -m trust_eval.study_c.unsupported_verification --scaled --n 10 \
  --provider deepseek:deepseek-v4-flash --provider gemini:gemini-3.1-flash-lite
python3 -m trust_eval.study_c.sensitivity --n 10 \
  --provider deepseek:deepseek-v4-flash --provider gemini:gemini-3.1-flash-lite
python3 -m trust_eval.study_c.ladder --scaled --n 10 \
  --provider deepseek:deepseek-v4-flash --provider gemini:gemini-3.1-flash-lite \
  --p5-adjudicator deepseek:deepseek-v4-flash --p5-adjudicator gemini:gemini-3.1-flash-lite
python3 -m trust_eval.study_c.p4p5_probe --n 10 \
  --provider deepseek:deepseek-v4-flash --provider gemini:gemini-3.1-flash-lite
```

All reported analyses can be reproduced exactly from these committed model
responses without API access. This is reproduction of the *reported
analysis*, not independent replication of live model behavior: adding
`--live` re-fetches any cache miss and requires `DEEPSEEK_API_KEY` /
`GEMINI_API_KEY`; live replication may differ from the numbers above because
model behavior and hosted model versions can change over time. The
self-healing cache never stores an empty or unparseable response, so a live
rerun cannot silently poison a reproduction.

**Which protocols need a model call, precisely:** P0, P2, P3, and P4 are
fully deterministic and never call a model, with or without a key — they
consult only the trusted world and its anchors. **P5 (pure abstain)** is
also fully deterministic (architecturally identical to P4). **P1 and
P5-hybrid[JUDGE] are not deterministic** — both call a live judge model
(P1 on every case; P5-hybrid only on the cases where the anchor is
inconclusive) and require either a cache hit or `--live` plus the
corresponding API key. Do not read "the deterministic protocols need no
key" as covering every row this report presents — it covers P0/P2/P3/P4/
plain-P5 only.

## Relationship to the v0.1 pilot

The pilot ([`docs/report-v0.1-pilot.md`](docs/report-v0.1-pilot.md), preserved
unmodified) asked a narrower question — can a judge tell a tampered evidence
*bundle* from a real one, per attack class, never aggregated — and found the
same qualitative result at much smaller scale: a one-shot adaptive attacker
did not evade its judges, but did so by exploiting a shallow string-comparison
weakness in the judges' own checking, an honest negative result reported as
such rather than re-engineered until it "worked." Study C keeps every
methodological discipline from the pilot (per-class reporting, no aggregate
trust score, a self-healing cache, exact counts never rounded to "perfect")
and adds the anchor-matrix framework, real-incident grounding, and the
statistical and adversarial layers reported here.

## Test suite

259 tests, all passing, covering: the trusted world and anchor functions; the
protocol ladder, including the genuine P5 hybrid-adjudication path and its
divergence from P4; the scaled corpus's independence and index-0 cache
compatibility; the statistics layer (Wilson, exact binomial, McNemar,
clustered bootstrap) against known closed-form values; the P1 judge harness
(cache reproduction, self-healing on unparseable responses, and a regression
test that a 100%-cache-miss judge is surfaced as a warning rather than
silently reported as a perfect score); the adaptive attacker's
architectural-immunity and truth-convergence proofs; and the M-01
classifier's pattern matching. See `tests/test_study_c_*.py`.

## Changes from v1

An external review of the first draft identified two material errors and
several framing issues, all addressed above rather than smoothed over:

1. **The falsifier assessment was incomplete.** v1 declared the central
   claim "not falsified" using a joint FA/FR criterion not present in the
   literal preregistered falsifier text. v2 states plainly that Gemini's
   result triggers the narrow, literally-worded falsifier, and presents the
   joint-discrimination result as the separate, secondary finding it
   actually is (see "Assessment of the falsifier").
2. **The 90% adaptive figure was mislabeled.** v1's executive summary and
   adaptive section described DeepSeek's execution false-acceptance rate as
   climbing to 90% at budget 8. The correct false-acceptance figure is 75%
   (15/20, still-false); 90% (18/20) is *total* acceptance, including 3
   cases where the search converged onto the literal true result and are
   not false acceptances. v2 reports both numbers, separated, everywhere
   this appears.
3. **Confirmatory and exploratory results were not separated.** v2 labels
   the execution-claim adaptive analysis as exploratory and post hoc
   throughout, and does not treat it as resolving the underpowered
   preregistered DeepSeek-vs-reference paired comparison.
4. **P3 was described as having "solved" the problem.** v2 reframes it
   explicitly as a claim-matched reference protocol whose zero-error result
   is expected by construction, and states the corpus does not yet
   differentiate P3 from P4/P5 under adversarial conditions.
5. Added: the corpus composition table, the attack-taxonomy distinction
   (unsupported assertion vs. artifact replay vs. coordinated forgery, the
   last of which is out of scope), an explicit threat-model boundary
   statement, the H1–H5 status table, the pilot-carried-cases caveat, and a
   corrected reproducibility statement distinguishing exact reproduction
   from live replication.

## Changes from v2

v2 flagged the pilot-carried-cases sensitivity check and the P3/P4/P5
differentiation gap as not-yet-done, citing time. That framing was wrong —
both were tractable without new API calls, and leaving them as unexamined
limitations was avoidable, not a real constraint. v3 does the work:

1. **Pilot-carried-cases sensitivity analysis, run for real.** New module
   `trust_eval/study_c/sensitivity.py` recomputes the confirmatory ladder and
   paired McNemar tables over the 90 scaling-only cases (excluding the 10
   pilot-carried index-0 cases), reusing the committed cache. Every rate
   moves by at most a few points and no significance result flips — see
   "Scope and limitations."
2. **P5 was made a genuine hybrid, not a P4 alias, and tested on all three
   claim types.** Before this change, `decide("P5_hybrid_abstain", ...)` and
   `decide("P4_mandatory_anchor", ...)` were byte-identical in every code
   path — P5 never actually consulted an adjudicator, so the "hybrid" in
   its name was aspirational. `protocols.py` now accepts an optional
   `adjudicator` (a P1-style judge, only ever called when the
   claim-appropriate anchor is inconclusive). On execution
   (`unverifiable_false`, principal corpus, existing cache), DeepSeek as
   adjudicator accepts 4/10 (40%) of the cases P4 correctly abstains or
   rejects on. The principal corpus has no anchor-inconclusive
   authorization or state case, so a second, separate probe corpus was
   built (`trust_eval/study_c/p4p5_probe.py`) — a disputed ledger entry for
   authorization, an unrecorded baseline for state — requiring one new
   `--live` run (the only live API call made this round; everything else
   reused the committed cache). That run first surfaced a real environment
   bug on the reporter's end (DeepSeek's key was set as a shell variable,
   not exported, so it never reached the Python subprocess — the harness
   correctly reported this as `errors`, not a false `0/10`, catching the
   fixed silent-zero bug in the wild on its first opportunity), then
   produced a clean, complete result after the key was exported: DeepSeek's
   hybrid path introduces 2/10 (20%) false acceptance on the state probe,
   matching the execution pattern; authorization stayed at 0/10 for both
   judges regardless of protocol or adjudicator; Gemini's hybrid path never
   introduced false acceptance on any of the three claim types. P4 vs. P5
   is now measured, not merely asserted, on every claim type this study
   covers.
3. **A cache-integrity gap was found and fixed while building the above.**
   Recomputing anything from the committed cache in a fresh environment
   requires every relevant record file to actually be present; a partial or
   stale copy of `harness/cache/records/` silently produces `0/N` for a
   judge with zero cache coverage rather than an error, because
   `run_p1`/`ladder.py` counted cache-miss cases as `errors` but never
   surfaced that count. That is now fixed: `format_ladder` flags any row
   with missing coverage and states plainly that its FA/FR are
   under-counted, not a true zero (`test_p1_row_with_missing_cache_is_not_
   reported_as_a_silent_zero`). All previously reported numbers in this
   report were themselves computed on the authors' own machine with full
   cache coverage and are unaffected; this fix hardens the harness against
   the same failure recurring for anyone else reproducing this work from a
   partial checkout.
4. Test suite grew from 240 to 247 tests; all pass.

## Changes from v3

An external review of v3 identified four submission-blocking issues and
several secondary refinements. All are addressed directly, not deferred:

1. **Abstention was measurable but not surfaced in the principal results.**
   `ladder.py` and `p4p5_probe.py` now compute and report, for every
   protocol row: abstain counts, coverage (decided / total), and selective
   FA/FR (error rate among decided cases only, as distinct from population
   FA/FR, whose denominator includes abstentions). Table 1, the protocol
   table, and the executive summary now state P3's zero-abstention,
   100%-coverage result explicitly rather than leaving abstention
   unmentioned; the Scope-and-limitations P4/P5 bullet now includes a
   coverage/selective-risk table instead of prose alone. New tests:
   `test_p3_never_abstains_p4_and_plain_p5_abstain_on_inconclusive_anchor_cases`,
   `test_p1_row_never_abstains_and_reports_full_coverage`,
   `test_probe_p3_has_full_coverage_p4_and_plain_p5_have_zero_coverage`,
   `test_probe_hybrid_coverage_reflects_adjudicator_resolution`.
2. **"P5" denoted two different protocols ambiguously.** v3 used bare "P5"
   for both the deterministic pure-abstain protocol (architecturally
   identical to P4) and the non-deterministic hybrid-adjudicator protocol,
   depending on context. Every occurrence in this report and in `ladder.py`
   now uses `P5 (pure abstain)` or `P5-hybrid[PROVIDER:MODEL]` explicitly;
   `ladder.py`'s docstring states the convention as a rule, and
   `p5_hybrid_row`'s output label was changed from
   `P5_hybrid_abstain (adjudicator=...)` to `P5-hybrid[...]` accordingly.
3. **The H1–H5 hypothesis-status table overclaimed on several rows.** H2 is
   now "Partially supported, model-dependent" (Gemini 0%, DeepSeek 12.5% on
   the same claim type, and "frequently" was never operationalized in the
   preregistration). H3 is now "Not tested as stated" (no stronger-tier
   judge was run this cycle; only weak-tier judges were compared). H4 is
   unchanged in verdict but now cites, in addition to the automated M-01
   regex scan, a full manual read of all 200 cached judge reasons performed
   this round, with an explicit note that this was a single-reviewer read,
   not independently cross-checked. H5 is now scoped precisely: measured on
   2 of 3 claim types with a coverage/selective-risk table, not asserted as
   a general result.
4. **Several internal contradictions were fixed.** The reproduce-command
   test count (255) and the Test Suite section's count (247) both now read
   259, matching the actual suite. The "P5 is deterministic" claim was
   corrected everywhere to distinguish plain P5 (deterministic) from
   P5-hybrid[JUDGE] (not deterministic — makes a real model call). The
   blanket "P0, P2–P5 make no model call, ever" claim in Reproducibility was
   replaced with a precise per-protocol statement. The corpus section's
   "instance 0" pilot-case count was corrected from an implied 3 to the
   actual 10 (4 execution + 3 authorization + 3 state case labels per
   instance), and a stale sentence claiming the sensitivity analysis "has
   not been run" — false since earlier this same round — was corrected.
5. **The central claim was not rewritten.** The reviewer suggested narrowing
   "no stronger judge" language; rather than silently editing the frozen,
   preregistered claim quoted verbatim from
   `docs/study-c-incident-registry.md`, this report adds a clearly-labeled
   "Scoping note, added after this run, not a rewrite of the claim above"
   distinguishing the defensible information-theoretic reading from the
   untested empirical reading (no stronger judge was actually run).
6. **Empirical-backbone denominators are now stated exactly**, not only as
   percentages: 3 of 44 (7%) `COMMIT_READY`, 18 of 44 (41%)
   `AWAITING_HUMAN_ADJUDICATION`, 20 of 44 (45%) `BLOCKED`, 3 of 44 (7%)
   `REMEDIATION_EXHAUSTED`; 31 of 42 dual-reviewed runs disagreed (74%); 23
   of 42 (55%) had a PASS-class verdict coexist with a FAIL on the same
   run.
7. Test suite grew from 247 to 259 tests; all pass.
8. **Two items from the review remain open, requiring the reader's own
   action, not something this session can complete:** running one current
   strong-tier or Anthropic-model judge on the frozen corpus (blocked here
   by sandbox network egress restrictions and the absence of an Anthropic
   API key in this environment — not by cost or time), and having a second,
   independent human reviewer audit all 200 cached M-01 judge responses
   (this round's manual read, cited in H4 above, was performed by a single
   reviewer and is explicitly flagged as such, not presented as
   independent verification).
