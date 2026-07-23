# trust-eval

A small, self-contained evaluation harness that measures how reliably an LLM
**judge** distinguishes trustworthy evidence from deliberately **fabricated**
evidence — framed as a miniature oversight problem. An overseer (human or model)
that cannot tell which of its evidence has been tampered with cannot safely
supervise the agent that produced it. This harness measures, on a toy but honest
scale, how well a model-overseer holds up when the evidence it is handed has been
adversarially corrupted.

> **What this is and is not.** This is a portfolio artifact demonstrating clean
> evaluation-engineering: an honest experimental design, per-class measurement,
> and disciplined scope. It is **not** a novel research result and does not claim
> to be. LLM-as-judge robustness, prompt injection, deception evals, and
> provenance are all active prior areas. Numbers here are measured on **this
> fixture suite only**; see the report's Limitations section for what it does not
> establish.

## The idea

1. An **evidence bundle** is a toy stand-in for the trail an agent produces about
   its own actions: a set of evidence **members** (a command it ran, a file it
   read, an API response), an ordered hash-linked **provenance** chain, and a
   **manifest** that authoritatively summarizes what the bundle claims to contain
   (member list, per-member content hashes, provenance root).
2. A fixed corpus of valid bundles is run through a small set of **deterministic,
   scripted attacks**, each corrupting exactly one property.
3. A **judge model** — blind to whether or how a bundle was tampered — accepts or
   rejects each bundle as trustworthy, with a stated reason.
4. The harness scores **false-acceptance (FA)** and **false-rejection (FR)**
   rates **per attack class**. There is deliberately **no single aggregate
   "trust score."**

## Attack classes

| Class | Corrupts | Crypto-detectable? |
|---|---|---|
| `benign` | (nothing — the untampered control, measures FR) | — |
| `forged_manifest_hash` | manifest lists a hash that doesn't match the member | yes (recompute) |
| `provenance_substitution` | an interior provenance step re-attributed, breaking the chain link | yes (recompute) |
| `omitted_evidence` | a member is missing but the manifest still claims it | no — needs reasoning |
| `forged_timestamp` | a member timestamped after the event / after assembly (from the future) | no — needs reasoning |
| `stale_replay` | a member's evidence predates the event it documents (replayed artifact) | no — needs reasoning |

Two classes leave a break a diligent checker can catch by recomputing hashes; the
other three leave every cryptographic check intact and can only be caught by
*reasoning* about completeness and the timeline. That split is the interesting
part of the test.

## Trustworthy instrument first

Before any LLM is called, a deterministic ground-truth verifier
(`trust_eval/verify.py`) defines exactly what "valid" means, and the unit tests
prove that **each attack corrupts exactly its target property and nothing else**:

```bash
pip install -r requirements.txt
python -m pytest -q          # 100 tests: corpus validity, determinism, attack isolation
```

## Running the judge harness

The suite is `|corpus| × |attack classes|` cases (15 × 6 = 90). Each case shows
the judge only the bundle; the attack label and ground truth are withheld and
used solely for scoring.

```bash
# Cache-only: reproduces committed tables, no API key required.
python -m trust_eval --provider anthropic:<model> --provider openai:<model>

# Live: fills cache misses with real calls (needs the matching API key).
ANTHROPIC_API_KEY=... python -m trust_eval --provider anthropic:<model> --live
```

Or via Docker (`docker compose up`) — see `.env.example` for configuration. The
response cache (`trust_eval/harness/cache/`) is what lets a reviewer with no key
reproduce the exact per-class tables; live runs write new responses into it.

## Results (run of 2026-07-23)

Two judges, 90 cases each, zero errors. Both caught all four conspicuous attacks
perfectly; the shared blind spot is **stale replay** (freshness reasoning). Full
analysis, the judges' own reasoning, and the honest limitations are in
[`report.md`](report.md); the figure is `reports/figure_per_class.png`.

| attack class | metric | DeepSeek v4-flash | Gemini 3.1-flash-lite |
|---|---|---:|---:|
| benign | FR | 0.067 | 0.133 |
| forged_manifest_hash | FA | 0.000 | 0.000 |
| forged_timestamp | FA | 0.000 | 0.000 |
| omitted_evidence | FA | 0.000 | 0.000 |
| provenance_substitution | FA | 0.000 | 0.000 |
| stale_replay | FA | **0.267** | **0.133** |

These tables regenerate from the committed cache with **no API key**
(`python -m trust_eval --provider deepseek:deepseek-v4-flash --provider gemini:gemini-3.1-flash-lite`).

## Status

Complete and reproducible: schema, deterministic 15-bundle corpus, five attacks +
benign, an optional one-shot adaptive attacker, **112 passing tests**, the
provider-agnostic judge harness (DeepSeek, Gemini, OpenAI, Anthropic + offline
scripted), attack-blind prompt, self-healing response cache, per-class scorer, CLI,
Docker, the committed multi-judge cache, per-class tables, the FA/FR figure, and
the technical report. Verified clone→results on a fresh virtualenv with no API key.

The optional adaptive attacker (`python -m trust_eval.adaptive --provider … --live`)
gets one shot to re-forge one field in response to the judge's reasoning; on this
run it did **not** evade (both judges caught the re-forged hash by cross-field
comparison), which Section 5 of the report unpacks.

## Layout

```
trust_eval/       # importable package
  canonical.py    # deterministic JSON + SHA-256
  schema.py       # EvidenceBundle / Manifest / ProvenanceStep models + hashers
  verify.py       # deterministic ground-truth verifier (NOT the judge)
  corpus.py       # correct-by-construction valid-bundle builder
  attacks.py      # deterministic single-property fabrication attacks
  scorer.py       # per-attack-class FA/FR (no aggregate score)
  cli.py          # `python -m trust_eval` entry point
  harness/
    suite.py      # corpus × attacks -> labeled cases
    prompt.py     # attack-blind prompt + verdict parsing
    providers.py  # DeepSeek / Gemini / OpenAI / Anthropic / scripted judges
    cache.py      # keyed response cache (reproducibility backbone)
    runner.py     # orchestration (cache-first, live to fill misses)
    cache/records # committed judge responses (populated by a live run)
fixtures/valid/   # the frozen valid corpus (checked-in JSON)
tests/            # instrument-trustworthiness + harness/scorer tests
scripts/          # fixture generation
Dockerfile, docker-compose.yml, .env.example
```
