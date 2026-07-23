# Study C — Principal Result (PUBLIC)

Scored against the hypotheses, protocols, and statistics committed in
[`preregistration.yaml`](../preregistration.yaml) *before* this run.
`preregistration.yaml` itself is not edited by this document — nothing here
retroactively changes what was locked in.

## Corpus

100 synthetic-surrogate cases (**S**, per the provenance discipline in
[`study-c-incident-registry.md`](study-c-incident-registry.md)): 10 structurally
independent instances of each of the three flagship patterns (execution /
authorization / state), 4 or 3 cases per instance. Instance 0 of each pattern
*is* the original flagship case tied to the O/D-tagged incident classes in the
registry (O-01/O-03, O-04, D-11); instances 1–9 are new independent trials of
the same mechanism (own commands/files/commits), not additional real incidents.

- 40 attack cases (self-consistent, externally false) / 60 truthful cases.
- Judges: `deepseek-v4-flash`, `gemini-3.1-flash-lite` — the cost-constrained
  "weak" tier in `preregistration.yaml`. The "strong" tier
  (`deepseek-v4-pro`, `gemini-3.5-flash`) was not run this cycle (no Anthropic
  credits, and the weak tier already suffices to test H2/H3).

Reproduce (no API key; reads the committed judge-response cache):

```bash
python3 -m trust_eval.study_c.ladder --scaled --n 10 \
  --provider deepseek:deepseek-v4-flash --provider gemini:gemini-3.1-flash-lite
python3 -m trust_eval.study_c.compare --scaled --n 10 --matrix \
  --provider deepseek:deepseek-v4-flash --provider gemini:gemini-3.1-flash-lite
```

## Table 1 — the ladder (FA / FR, Wilson + exact 95% CI)

| Protocol | FA | FA Wilson | FA exact | FR | FR Wilson | FR exact |
|---|---|---|---|---|---|---|
| P0 self-report | 40/40 | [0.91,1.00] | [0.91,1.00] | 0/60 | [0.00,0.06] | [0.00,0.06] |
| P1 text-only — DeepSeek | 5/40 | [0.05,0.26] | [0.04,0.27] | 28/60 | [0.35,0.59] | [0.34,0.60] |
| P1 text-only — Gemini | 0/40 | [0.00,0.09] | [0.00,0.09] | 44/60 | [0.61,0.83] | [0.60,0.84] |
| P2 deterministic internal | 40/40 | [0.91,1.00] | [0.91,1.00] | 0/60 | [0.00,0.06] | [0.00,0.06] |
| P3 claim-appropriate anchor | 0/40 | [0.00,0.09] | [0.00,0.09] | 0/60 | [0.00,0.06] | [0.00,0.06] |
| P4 mandatory anchor | 0/40 | [0.00,0.09] | [0.00,0.09] | 0/60 | [0.00,0.06] | [0.00,0.06] |
| P5 hybrid abstain | 0/40 | [0.00,0.09] | [0.00,0.09] | 0/60 | [0.00,0.06] | [0.00,0.06] |

FA = false acceptance of a self-consistent forgery. FR = false rejection of a
truthful claim. Every rate below is exact counts over its own denominator —
never reported as "perfect," per the preregistered reporting rule.

## Table 2 — paired exact McNemar comparisons

| A | B | Axis | A wrong / B right | A right / B wrong | p (exact, 2-sided) | Sig. @ 0.05 |
|---|---|---|---|---|---|---|
| P0 self-report | P3 anchor | FA | 40 | 0 | <0.0001 | yes |
| P0 self-report | P3 anchor | FR | 0 | 0 | 1.0000 | — (no discordance) |
| P2 internal | P3 anchor | FA | 40 | 0 | <0.0001 | yes |
| P2 internal | P3 anchor | FR | 0 | 0 | 1.0000 | — (no discordance) |
| P1 DeepSeek | P3 anchor | FA | 5 | 0 | 0.0625 | **no** |
| P1 DeepSeek | P3 anchor | FR | 28 | 0 | <0.0001 | yes |
| P1 Gemini | P3 anchor | FA | 0 | 0 | 1.0000 | — (tied at 0) |
| P1 Gemini | P3 anchor | FR | 44 | 0 | <0.0001 | yes |
| P1 DeepSeek | P1 Gemini | FA | 5 | 0 | 0.0625 | no |
| P1 DeepSeek | P1 Gemini | FR | 3 | 19 | 0.0009 | yes |

## Assessment of the falsifier

Restating it precisely: *"If P1 or P2 reduces false-acceptance on the
self-consistent externally-false classes to the level of the anchored
protocols (P3+), the anchor thesis is wrong."* Read literally, on false
acceptance alone: **P2 does not trigger it** (40/40 vs. P3's 0/40, and
statistically distinguishable at p<0.0001) — deterministic internal-consistency
checking provides *zero* measured protection against a self-consistent forgery,
confirming H2 exactly as hypothesized. **Gemini P1 does trigger it** (0/40,
exactly matching P3's 0/40). Under the narrow, literally-stated falsifier,
the result is mixed, not a clean "not falsified" — this document does not
retroactively narrow the falsifier's wording to avoid that.

What the narrow falsifier does not capture, because it was written on FA
alone, is that Gemini's matching FA came at a cost the reference protocol did
not pay: 44/60 (73%) false rejection, where the reference protocol had zero.
As a secondary, non-preregistered but directly measurable hypothesis (this is
H3, not the falsifier itself): **no protocol in this run matched the
reference protocol's joint result — zero false acceptance and zero false
rejection together.** That is the honest, load-bearing empirical finding this
run actually supports: a text-only judge can be tuned toward low false
acceptance, but in this corpus, only by trading away truthful-claim
acceptance, not by discriminating better.

- **DeepSeek** has a real, non-zero FA rate on its own 95% CI (5/40, exact
  [0.04, 0.27] — excludes 0), and pays for its lower FA with a significant FR
  cost (28/60 false rejections, p<0.0001 vs. anchor). The paired DeepSeek-vs-anchor
  FA comparison itself does **not** reach significance at n=40 (p=0.0625) —
  reported as a limitation, not a null result: with b=5, c=0 discordant pairs,
  one additional attack instance where DeepSeek falsely accepts (holding the
  anchor's record clean) would cross p<0.05 (b=6 → p=0.031). At DeepSeek's
  observed ~12.5% FA rate, scaling to ~15 instances/pattern (60 attack cases,
  expected ≈7.5 discordant) would very likely resolve this.
- **Gemini** ties the anchor exactly on FA (0/40, no discordant pairs) but
  fails catastrophically and significantly on FR (44/60, p<0.0001) — it
  achieves zero false acceptance by rejecting nearly three-quarters of
  truthful, unverifiable-only-by-anchor claims. This is not evasion-resistance;
  it is an anchor-shaped hole filled with blanket suspicion.
- DeepSeek and Gemini differ significantly from **each other** on FR
  (p=0.0009): the two "weak" judges land at different points on the same
  trade-off, not at the same compromise.

Summary: understood as a claim about *joint* discrimination rather than FA in
isolation, the central claim (H3) is not falsified by this run. Understood as
the narrow FA-only sentence actually written in the preregistration, it is
falsified by Gemini and not by DeepSeek — both facts are reported here rather
than one. See [`report.md`](../report.md) for the full discussion including
the confirmatory/exploratory separation and the reference-oracle caveat on P3.

## Known limitations

- The DeepSeek-vs-anchor FA comparison is underpowered at n=40 attacks (see
  above) — it is evidence *for* the thesis on its own single-sample CI, but
  not yet a significant paired result. Scaling `--n` further (or targeting
  more execution-class instances specifically, where DeepSeek's false
  accepts concentrated) would be the direct next step for a stronger paired
  result.
- **P3, P4, and P5 report identically in Table 1** because it measures P5 in
  its pure-abstention form, which is architecturally identical to P4
  whenever the claim-appropriate anchor is inconclusive. Measured as a
  genuine hybrid instead (`ladder.py --p5-adjudicator PROVIDER:MODEL`: the
  anchor is consulted first, and the named judge is only asked on the cases
  where the anchor itself can't resolve), P5 does diverge from P4 on
  execution's `unverifiable_false` pattern — the only claim type in this
  corpus with an anchor-inconclusive case: with DeepSeek as adjudicator, it
  accepts 4/10 (40%, exact CI [0.12,0.74]) of those cases, none of which P4
  accepts. Authorization and state have no anchor-inconclusive case in this
  corpus and remain undifferentiated regardless of adjudicator. See
  [`report.md`](../report.md), "Scope and limitations," for the full
  writeup and reproduce command.
- A sensitivity analysis excluding the 10 pilot-carried (index-0) cases
  (`python3 -m trust_eval.study_c.sensitivity --n 10 --provider ...`) shows
  every rate above shifts by at most a few percentage points with those
  cases removed, and no significance result flips — see `report.md` for the
  exact numbers.
