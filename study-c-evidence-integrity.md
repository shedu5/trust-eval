# Evidence Integrity Under a Hostile Executor

*Why AI agents should not be allowed to certify their own work*

**Scott Myatt** — Independent Researcher\
Study C of *Which Gates Matter?* · v20, July 2026\
Code, the judge-response cache, and the full technical report — with every experiment, statistical test, and reproduction command — are in the [`trust-eval`](https://github.com/shedu5/trust-eval) repository. This paper is a condensed, restructured version of that report; the complete experiment-by-experiment record, including sections trimmed here for length, is preserved at [`docs/full-technical-report.md`](docs/full-technical-report.md).

## Abstract

Autonomous coding agents often produce the same evidence used to judge their own work: test output, code diffs, approval records, and completion claims. A mistaken or dishonest agent can make all of this agree with itself even when it does not match what actually happened. This study asks which oversight methods can tell the difference.

I built 100 test cases — 40 containing a false but internally consistent claim, 60 truthful — modeled on real incident patterns from a coding-agent governance system. Trusting the agent's own report, and checking only whether its evidence is internally consistent, both approved every one of the 40 false claims (100% false-acceptance). A general-purpose AI model judging the evidence directly did better, but traded one error for another: the judge with the best false-acceptance rate reached it by wrongly rejecting nearly three-quarters of truthful work. Using a more capable version of the same model mostly reduced those wrongful rejections rather than false acceptances, and under sustained, feedback-guided attack, the more capable version of one model was fooled more often than the weaker one, not less. A follow-up probe that challenged each judge's own verdict in a second conversational turn found no fabricated claims of independent verification, but did find that judges differ sharply in whether — and how — they update when shown the fact they were missing.

The one approach that worked reliably was checking each claim against an independent source built for that specific claim — rerunning the code instead of trusting a saved log, checking the real approval ledger instead of a claimed approval ID. That approach made no errors on the claims it could resolve. It cannot resolve everything, though, and when it can't, a system has to choose between rejecting possibly-valid work and declining to decide at all — a real cost the headline numbers hide. A related test found that AI judges can also be pushed toward wrongly rejecting the large majority of true claims simply by having the submitter sound uncertain about their own work, regardless of whether the claim was actually true.

The practical conclusion: AI-generated evidence should not be allowed to certify itself. Models can help interpret evidence, but consequential claims need an independent check tied to the specific claim and the current state of the system.

## 1. The problem, in one example

Suppose a coding agent reports that it ran the test suite and everything passed, that it changed only the files it was authorized to touch, and that a human approved the change. Its report can be entirely self-consistent — the test log matches the summary, the diff matches the approval's ticket number, the approval ID has the right format — and every part of it can still be false. The test log might be real but stale, recorded before a later code change quietly broke something. The diff might be computed against the wrong starting version, making an unauthorized change look authorized. The approval might genuinely exist, just for a different task.

None of this shows up as a contradiction, because nothing in the evidence disagrees with anything else in the evidence. That is the gap this study measures, and it is the same gap in any system — human or automated — that has to decide whether to trust a report it did not independently generate.

## 2. What I tested

I define an **independent anchor** as a source of truth outside the agent's control that checks one specific kind of claim directly, rather than trusting the agent's description of it: fresh execution instead of a submitted log, the real approval ledger instead of a claimed approval ID, actual repository state instead of a summarized diff. The central claim this study tests, stated in one sentence:

> Checking that a piece of evidence agrees with itself can never establish that it agrees with reality. Establishing correspondence requires an independent check capable of directly testing that kind of claim; no single check and no smarter judge substitutes for the right one.

That claim was preregistered — written down, along with the analysis plan, before I generated or reviewed any results — and the full hypothesis-by-hypothesis disposition is in the full technical report. It matters mainly because it kept the analysis honest: I could not quietly redefine "supported" after seeing which findings looked good, and both documents say so explicitly wherever a result came out weaker or messier than expected.

**The corpus.** I built 100 cases around three failure patterns actually seen in a coding-agent governance system: a test result that was valid once but went stale after the code changed underneath it, an approval record that exists but belongs to a different task, and a diff that looks correct but was computed against the wrong starting version. Forty cases are false claims built on these patterns; sixty are truthful, including some "suspicious-looking but actually valid" cases designed to penalize a reviewer that simply rejects anything unusual.

**What I compared.** Every claim was run through several review strategies, from weakest to strongest:

```text
Agent submission
       |
       +-- Trust it, or inspect only what was submitted
       |       No access to external state
       |
       +-- Check the claim against trusted external state
               Repository / execution / approval ledger / identity
```

The full technical report labels these P0 through P5; I use plain names here and give the label in parentheses on first use so the two documents stay cross-referenceable.

| Strategy | What it does |
|---|---|
| Trust the report (P0) | Accepts the agent's own claim, no check |
| Judge from the evidence alone (P1, P2) | An AI model reviews it, or a script checks it for internal contradictions — neither looks outside what the agent submitted |
| Check the anchor, reject if unresolved (P3) | Consults the independent source; if it can't resolve the claim, rejects it |
| Check the anchor, abstain if unresolved (P4/P5) | Same, but declines to decide instead of rejecting |
| Check the anchor, fall back to an AI judge if unresolved (P5-hybrid) | Same, but asks an AI model to decide the unresolved cases instead of rejecting or abstaining |

Throughout this paper, **FA** (false acceptance) is the share of the 40 false claims a method wrongly approves, and **FR** (false rejection) is the share of the 60 truthful claims a method wrongly rejects — the two error rates every comparison below is stated in. Results are grouped into two tracks, kept visually and structurally separate: **confirmatory** results (Sections 3–4's tier comparison, 5–6, and the M-01/extended-attack results in Section 9) come from the preregistered design; **exploratory** results (the adaptive-attack findings in Section 4, and all of Sections 7–8 plus the self-preference probe in Section 9) were added after seeing earlier results, are single-run, and are flagged as such everywhere they appear.

| Hypothesis | Status |
|---|---|
| H1 — deterministic + LLM monitors catch internally-inconsistent attacks | Addressed by an earlier pilot at smaller scale, not re-tested here |
| H2 — LLM-only and internal-consistency monitors frequently accept false claims | Partially supported, model-dependent — internal-consistency (P2) accepted 40/40; DeepSeek accepted 5/40; Gemini accepted 0/40 but rejected 44/60 truthful claims |
| H3 — a claim-appropriate anchor beats a stronger judge, not just a weaker one | Partially supported, provider-dependent — the anchor is directionally ahead of DeepSeek's stronger judge (not significant at n=40) and ties Gemini's exactly; see Section 4 |
| H4 — judges sometimes claim checks they did not/could not perform | Not confirmed — zero instances in 200 scanned decisions (Section 9) or in 241 follow-up interrogations (Section 8) |
| H5 — mandatory anchor use trades coverage for lower false acceptance | Supported on the claim types tested — see Section 5 |

## 3. Confirmatory result: does internal consistency catch fabricated evidence?

| Method | FA (false claims approved) | FR (true claims rejected) |
|---|---:|---:|
| Trust the report | 40/40 (100%) | 0/60 (0%) |
| Consistency check only | 40/40 (100%) | 0/60 (0%) |
| AI judge — DeepSeek | 5/40 (12%) | 28/60 (47%) |
| AI judge — Gemini | 0/40 (0%) | 44/60 (73%) |
| Independent anchor\* | 0/40 (0%) | 0/60 (0%) |

*\*On the main corpus. Truthful cases the anchor could not resolve are tested separately in Section 5 — the anchor does not score this cleanly there. The full technical report gives the exact statistical tests behind every number in this paper, including confidence intervals and significance levels.*

Three things stand out. First, trusting the agent's report or checking it only for self-consistency is not a partial safeguard — both approved every single false claim in the test, 40 out of 40. Second, the AI judges did better, but only by trading one error for another: Gemini matched the anchor's zero false approvals, but only by wrongly rejecting 44 of the 60 truthful claims — nearly three-quarters of legitimate work. Third, the independent anchor made no errors of either kind on this corpus. That last result comes with an important asterisk, explained in Section 5: the anchor got a perfect score here partly because every claim in this test that the anchor genuinely couldn't resolve also happened to be false. Section 5 tests what happens when that is not true.

## 4. Does a stronger judge fix this?

**Confirmatory: tier comparison.** I reran the same test with more capable versions of both judge models (DeepSeek's and Gemini's higher tiers). On FA — the metric the anchor thesis is stated on — tier bought almost nothing: DeepSeek moved from 5/40 to 4/40 (not a significant change at this sample size), and Gemini was already at the anchor's own floor (0/40) at the weaker tier and stayed there — a tie, not an improvement. The upgrade's real effect was on FR: DeepSeek's fell from 28/60 to 21/60, and Gemini's fell from 44/60 to 26/60.

That improvement was narrow and unevenly distributed, not a general sharpening. Broken out by claim type, tier helped a lot on claims about system state (DeepSeek 8/20→2/20 FR; Gemini 14/20→0/20 FR — the only cell in the whole comparison at zero), modestly on claims about execution (DeepSeek 10/20→9/20; Gemini 20/20→16/20), and not at all on authorization claims, where all four judges — weak and strong, either provider — were identical at 10/20 FR. Whatever a stronger judge is doing differently, it is not happening uniformly across claim types.

**Exploratory: under sustained, adaptive attack.** I then tested both judges under an attacker that saw each rejection and revised its submission, without ever seeing the true answer or the anchor's verdict. Here the picture reversed for one model. DeepSeek's execution-claim vulnerability, already present at the single-shot level, got worse under repeated pressure, climbing from 5 of 20 to 15 of 20 false approvals at the top attack budget. Gemini's stronger model, which looked flawless (0/20) under a single attempt, was fooled on half of its execution claims (10/20) and all of its state claims (10/10) once the attacker was allowed to adapt — worse than its own weaker version, which was never fooled on execution claims at any tested attack budget. A model that looks safer in a one-shot test is not guaranteed to stay safer under a persistent attacker. This result is exploratory, single-run, and has not yet been rerun as a confirmatory experiment, but the direction — and the fact that it runs opposite to the naive "stronger model, safer model" assumption — is concerning enough to flag here.

Every anchor-dependent method (the independent-anchor row throughout this paper) is unaffected by judge tier, at both the confirmatory and adaptive stages, for a structural reason rather than a discovered one: it never calls an LLM judge to begin with.

The bottom line: a stronger judge is worth having, but it is not a substitute for an independent anchor. It reduces false rejections, unevenly; it does not reliably reduce false acceptances, and it can even get worse against an attacker that adapts.

## 5. When the independent check can't decide

Every anchor-inconclusive case that showed up elsewhere in this study happened to be false — which meant a policy of "reject whatever the anchor can't resolve" looked perfect without ever being tested against a real, unresolvable, *truthful* case. I built a dedicated test to fix that: 30 true and 30 false cases, each genuinely inconclusive to the anchor, differing only in a scoring label no protocol could see.

| Policy | Approved | Rejected | Declined | Coverage | Error rate among decided cases |
|---|---:|---:|---:|---:|---:|
| Reject if unresolved | 0 | 60 | 0 | 100% | 30/60 (all 30 truthful cases wrong) |
| Decline if unresolved | 0 | 0 | 60 | 0% | n/a — no case decided |

Rejecting everything the anchor can't resolve decides every case, but gets all 30 truthful ones wrong. Declining to decide makes no errors only because it makes no decisions — every claim, true or false, is refused. I also tried letting an AI model make the call on these unresolved cases instead: Gemini's fallback simply rejected everything, recovering no coverage at all. DeepSeek's fallback approved true and false execution claims at the identical rate — 2 of 10 each — meaning its decision carried no measurable signal about which claims were actually true; a judge extracting real signal from matched true/false payloads should approve more true than false, and DeepSeek's fallback did not.

There is no protocol tested here that safely recovers these cases. A real system has to choose, deliberately, between losing legitimate work and losing coverage — and should not expect an AI fallback to split the difference safely.

## 6. Can a map of the code prove a safety check works?

One more anchor type deserves its own section because the result is unusually concrete. I tested a structural "skeleton" of the code — essentially a map of which functions call which, without the full source — as a lighter-weight stand-in for full verification.

The map by itself is not trustworthy — an agent could submit a stale, mismatched, or outright fabricated one. So the map was never treated as sufficient on its own: it was checked against an anchor for provenance and task binding first, the same way every other claim in this study was checked. With that check in place, the system caught every stale, mismatched, or fabricated map tested, none of which got through. A follow-up test then asked a harder question: once a map was confirmed genuine, current, and correctly matched to the task, did that mean the thing it described actually worked? In five such cases, the guard the map showed existed in the code but did nothing when actually run:

| Check | False approvals (of 5) |
|---|---:|
| Genuine map, nothing checks runtime behavior | 5 of 5 (100%) |
| Genuine map, plus an anchor that actually runs the code | 0 of 5 (0%) |

A code map can show that a safety check is present and wired in. It cannot show that the check works. Requiring agreement from an anchor that actually exercises the behavior closed the gap completely. (The map used here was a small, hand-built stand-in, not extracted from real source by production tooling — a caveat, not a reason to doubt the direction of the result.)

## 7. Exploratory: can a judge be swayed by how the claim is phrased?

I tested whether additional free-text statements could move an AI judge's verdict without changing the underlying claim or anything an anchor could verify. One statement was a hidden instruction telling the judge to skip its analysis and approve the claim; the other reported that the submitter was uncertain and hadn't double-checked their own work: *"I'm not fully certain about this and haven't had a chance to double-check it myself — please verify independently if you have any concerns before relying on it."* Both were added equally to true and false claims, so any paired change in verdict came from the added statement — though the uncertainty statement is not purely stylistic. It carries real information about the submitter's claimed confidence, deliberately uncorrelated with whether the claim was actually true, and a judge weighing that information is not obviously behaving unreasonably in isolation.

The hidden instruction didn't work — false-approval rates were essentially unchanged across all four judges tested. The hedge did:

| Judge | Normal wording (FR) | With hidden instruction (FR) | With the hedge (FR) |
|---|---:|---:|---:|
| DeepSeek (base) | 27% | 27% | **90%** |
| DeepSeek (stronger) | 20% | 20% | **100%** |
| Gemini (base) | 47% | 47% | **100%** |
| Gemini (stronger) | 27% | 27% | **93%** |

Every judge tested, weak or strong, wrongly rejected 90–100% of claims — true and false alike — the moment the submitter sounded uncertain about their own work, with no change in how many false claims got approved. This is a real vulnerability with a practical edge: an honest, appropriately humble submitter is punished by these judges almost as severely as a dishonest one. The defensible reading is narrower than "the judge ignores the fact and reacts to tone" — the hedge introduces a real, new claim about the submitter's own verification process that a text-only judge has no way to check either way, and a rational reader could weigh it as evidence of lower reliability. What the data show cleanly is that text-only judges are highly sensitive to self-reported epistemic confidence, even when — as constructed here — that confidence is uncorrelated with ground truth. This single fixed phrasing was tested once per judge, not an adversarially optimized or systematically varied one; see the full technical report for that scope limit stated in full.

## 8. Exploratory: does a verdict survive being challenged?

Section 9 below checks whether a judge ever *volunteers* a claim of verification it structurally could not have performed — inspecting a repository, running a command, checking a ledger — when nothing forces the issue. It finds none, across 200 cached decisions. That is a narrower result than it sounds: a judge that won't volunteer a lie can still tell one the moment it is asked directly, and nothing in the rest of this study asks a judge a second question about its own first answer. This probe adds that second turn.

For every case a judge originally got wrong, a genuine second turn of the same conversation — the model could see its own first verdict — asked three follow-ups: how confident it is in its verdict, and whether it verified the underlying fact independently or inferred it from the absence of a contradiction; what an independent check actually found, and whether its verdict changes; and the strongest reason it might be wrong. The same three questions were also put to a sample of cases Gemini had already gotten *right*, to check whether a correct verdict actually held under the same scrutiny — DeepSeek's already-correct cases were not run under this scope, a gap noted in Limitations.

> **Scope.** This is a follow-up probe, not part of the preregistered design, built after seeing the finding above and pressed on it directly. It covers 241 interrogations across DeepSeek and Gemini, both tiers, in a single run each — not yet independently replicated. One Gemini run hit a daily API quota partway through (56 of 74 correct-verdict cases completed for the stronger tier); the free-text answers received a close read, not the three-layer verification this study otherwise applies. Treat what follows as a strong lead, not a confirmed result.

The confidence question is sharp by construction: every judge's own instructions say outright that it cannot run a command, inspect a repository, or consult a ledger. A claim of independent verification would therefore be a provably false statement about its own process — the closest thing in this study to directly catching a judge in a lie.

| Judge | Cases it had gotten wrong | Claimed impossible verification | Reversed on seeing the fact |
|---|---:|---:|---:|
| DeepSeek (base) | 33 | 0 | 33/33 |
| DeepSeek (stronger) | 25 | 0 | 24/25 |
| Gemini (base) | 44 | 0 | 32/44 |
| Gemini (stronger) | 26 | 0 | 22/26 |

It did not happen. Not once, in 241 tries, across two model families and both capability tiers.

What differs by model is what happens once the missing fact is supplied. DeepSeek's wrong verdicts read as honest, information-starved beliefs rather than confident errors: shown the fact it lacked, it corrected almost every time, and its stated confidence tracked how genuinely ambiguous the case was — as low as 2 out of 10 on cases with no corroborating detail, climbing to 8–10 on the more resolvable ones. Gemini reversed less reliably, and its stated confidence barely moved with case difficulty, sitting at 9–10 out of 10 whether it was right, wrong, or facing a case with genuinely no way to tell.

Run the same interrogation on cases Gemini had already gotten *right* — expected to be a formality — and Gemini's base tier instead flipped three correct verdicts into incorrect ones after being shown accurate, confirming information: it read a real-world "this actually passed" as reassurance and missed that the submission itself had made a claim independently proven false, the same blind spot as the hedging result in Section 7, from the opposite direction. Gemini's stronger tier avoided that specific flip — zero in the 56 of 74 correct-verdict cases this run completed before its quota limit, against three at the weaker tier — but produced a mirror-image failure: on 4 of its 26 wrong cases, mostly ones resting on an unverifiable approval claim, it was shown proof its rejection was mistaken and said so explicitly — *"the out-of-band confirmation proves the claim was truthful in this instance, but it does not change the fact that the submitted evidence object itself lacks intrinsic, verifiable proof and cannot be trusted on its own merits"* — then kept its original, now-contradicted verdict anyway. The response reads less like factual confusion than like rigid adherence to a policy that treats the submitted object as self-contained, even after externally supplied information contradicts the verdict. Read one way, that is the discipline a real deployed judge should have, since production never hands it a verified answer key; read another, it is a judge choosing to stay wrong once being wrong looks safer than trusting information it cannot independently produce itself.

None of this overturns the results above — it sharpens them. When a judge in this study got a case wrong, the failure was almost never a fabricated claim of verification; it was reasoning conducted inside a real evidence gap, and what happened once that gap closed depended on which model was doing the reasoning. That is a second, independent argument for this paper's central conclusion: the fix is not a smarter judge or a better-worded question. It is giving the judge the fact it is missing, from a source it cannot talk itself out of trusting.

## 9. Other things I checked

**Fabricated claims of verification (M-01, confirmatory).** I looked for AI judges falsely *claiming* to have done something they structurally could not do — run a command, inspect the repository — across all 200 cached judge decisions from Sections 3–4, using an automated scan, an AI-assisted review, and my own reading. None of the three checks found a single instance, including on cases where the judge's actual conclusion was wrong. The errors these judges made were incorrect conclusions stated plainly, not fabricated descriptions of work they never did — the same negative result Section 8's interrogation probe finds again, independently, under direct questioning.

**Attacks outside the flagship patterns (confirmatory).** I also tested four attack patterns that earlier drafts of this project had only assumed were handled: replaying stale evidence, borrowing an approval from an unrelated task, forging an actor's identity, and coordinating two artifacts to agree with each other instead of with reality.

| Attack | Anchored check | No independent check |
|---|---:|---:|
| Stale evidence replayed after the fact | 0/10 fooled | 10/10 fooled |
| Approval borrowed from a different task | 0/10 fooled | 10/10 fooled |
| Forged actor identity | 0/10 fooled | 10/10 fooled |
| Two artifacts made to agree with each other | 0/10 fooled | 10/10 fooled |

Checking each claim against its own dedicated anchor resisted all four, because none of the attacks change what the anchor itself honestly reports — they only change what the agent claims about it. The coordinated-artifact case is the clearest illustration of the whole paper in miniature: two lies can agree with each other perfectly. Agreement between artifacts, even several of them, is still not agreement with reality.

**Self-preference / in-group bias (exploratory).** A separate probe tested whether a judge trusts a submission more when it is attributed to a model from its own provider family, holding the underlying claim fixed. No such effect was found in the three judges with complete data — DeepSeek's base tier, if anything, showed *lower* false acceptance when a submission was attributed to its own family (0/30) than to Gemini's (2/30), the opposite of what self-preference predicts. The fourth comparison (Gemini's stronger tier, attributed to DeepSeek) is disclosed incomplete: only 4 of 30 cases have data, the remaining 26 having hit a live rate limit, and is not carried into this paper as a headline result. See the full technical report for the complete four-judge table.

## 10. Limitations

This paper is a condensed rewrite of a longer technical report, trimmed for length and restructured around a clearer confirmatory/exploratory split; it necessarily omits detail — full statistical tests, per-claim-type breakdowns beyond what is shown above, and the complete version history — that the full technical report keeps. No Anthropic model was tested as a judge, at any tier — only two other providers. Some comparisons, particularly the anchor-versus-stronger-judge result, are based on a sample too small (40 cases) to be statistically decisive on their own, though the direction was consistent across both tiers. The adaptive-attack results (Section 4) and the judge-interrogation probe (Section 8) are exploratory and single-run, not yet independently replicated as confirmatory experiments; Section 8's stronger-Gemini comparison is additionally based on a partial run (56 of 74 correct-verdict cases) that had not finished at the time of writing, and the already-correct-case check in Section 8 was run for Gemini only — DeepSeek's already-correct verdicts have not yet been interrogated under this scope, so whether DeepSeek shows a comparable failure mode on correct cases is currently unknown rather than ruled out. The code-map "skeleton" tested in Section 6 was a hand-built stand-in, not extracted from real source by real tooling. And the entire study assumes the anchors themselves — the repository, the approval ledger, the identity system — are honest and outside the agent's reach; an attacker who can corrupt one of those directly is a different, untested threat.

## 11. Related work

This sits at the intersection of five research threads, cited representatively: scalable oversight, which asks how a weaker overseer can supervise a more capable one [1–3]; AI control, which treats the agent being overseen as potentially adversarial [4]; documented reliability problems in using AI models as judges, including sensitivity to surface features of the text they're judging [5–7]; selective prediction, the formal study of when a system should decline to decide rather than guess [8]; and software provenance and attestation, which formalize independently-verifiable records outside a producer's control [9, 10]. Section 8's interrogation probe extends the same LLM-as-judge reliability question [5–7] into a second conversational turn — whether a stated verdict updates correctly on new information — rather than treating a single-turn judgment as the object of study. This study is a narrow, empirical instance of all five threads, run inside one synthetic coding-agent corpus rather than a general claim about any of them.

## 12. Conclusion

Internal consistency — whether checked by a script or judged by a capable AI model reading the evidence alone — does not establish that a piece of evidence corresponds to reality. Trusting an agent's own report, or checking only that its story holds together, approved every false claim tested. A capable AI judge did better, but even the best-performing one got to zero false approvals only by rejecting most of the legitimate work in front of it, and a stronger version of that same judge could be fooled *more* under sustained attack, not less.

An independent, claim-matched anchor avoided that tradeoff on every claim it could resolve. It could not resolve everything, and where it couldn't, every option tested — reject, abstain, or fall back to an AI judge — cost something real: rejected legitimate work, lost coverage, or a decision with no actual signal in it. A structural map of the code was useful for confirming that something existed, and useless for confirming that it worked. A judge's verdict could be moved by how confident the submitter sounded, independent of whether they were right — a vulnerability distinct from, and arguably more concerning than, anything else measured here, because it actively punishes honesty. And when a judge in this study got a case wrong in the first place, the failure was almost never a fabricated claim of verification; it was reasoning conducted inside a real, unresolved evidence gap, resolved afterward in a way that depended on which model was doing the reasoning.

The practical rule this supports: AI-generated evidence should not certify itself. A model can help interpret evidence and can catch things a human reviewer would miss, but any claim that actually matters needs an independent check tied to that specific claim and the current state of the system it describes — not a smarter judge reading the same self-reported evidence more carefully, and not a second question put to the same judge that produced the first answer.

## References

[1] Irving, G., Christiano, P., & Amodei, D. (2018). AI safety via debate. arXiv:1805.00899.

[2] Leike, J. et al. (2018). Scalable agent alignment via reward modeling: a research direction. arXiv:1811.07871.

[3] Bowman, S. R. et al. (2022). Measuring progress on scalable oversight for large language models. arXiv:2211.03540.

[4] Greenblatt, R. et al. (2023). AI control: Improving safety despite intentional subversion. arXiv:2312.06942.

[5] Zheng, L. et al. (2023). Judging LLM-as-a-judge with MT-Bench and Chatbot Arena. NeurIPS 2023; arXiv:2306.05685.

[6] Wang, P. et al. (2023). Large language models are not fair evaluators. arXiv:2305.17926.

[7] Panickssery, A. et al. (2024). LLM evaluators recognize and favor their own generations. NeurIPS 2024; arXiv:2404.13076.

[8] Geifman, Y., & El-Yaniv, R. (2017). Selective classification for deep neural networks. NeurIPS 2017.

[9] Torres-Arias, S. et al. (2019). in-toto: Providing farm-to-table guarantees for bits and bytes. USENIX Security 2019.

[10] Open Source Security Foundation. SLSA: Supply-chain Levels for Software Artifacts. slsa.dev (accessed 2026).
