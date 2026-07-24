"""Judge-provider pricing, confirmed against each provider's own live docs
on 2026-07-24 -- not estimated, not carried over from training-data prices
(every model named here postdates this harness's knowledge cutoff). See
report.md's Phase 0 section for the fetched sources.

Prices are dollars per 1,000,000 tokens. `batch_discount` is the fraction
off standard price a provider's real batch mechanism gives; `None` means
no batch/off-peak discount is currently confirmed for that model -- price
it at standard synchronous rate and say so, never assume a discount that
isn't documented. As of 2026-07-24, that is true of BOTH DeepSeek models:
their live pricing docs (https://api-docs.deepseek.com/quick_start/pricing)
do not mention an off-peak or batch discount for the v4 generation, despite
an older (R1/V3-era) off-peak program having existed previously. Re-check
before this stops being current -- pricing pages change.

Reasoning/thinking output tokens are billed at the SAME rate as ordinary
output tokens by every provider modeled here -- there is no separate,
cheaper rate for them. They matter for projecting cost because a reasoning
model can emit far more of them per call, not because each one costs more.
"""

from __future__ import annotations

from typing import Optional

CONFIRMED_DATE = "2026-07-24"

# provider:model -> pricing. cache_hit_input is DeepSeek-only (None elsewhere
# means "no separate cache-hit rate published"; treat all input as the
# standard/cache-miss rate for those providers).
PRICING = {
    "deepseek:deepseek-v4-flash": {
        "input": 0.14, "cache_hit_input": 0.0028, "output": 0.28, "batch_discount": None,
    },
    "deepseek:deepseek-v4-pro": {
        "input": 0.435, "cache_hit_input": 0.003625, "output": 0.87, "batch_discount": None,
    },
    "gemini:gemini-3.1-flash-lite": {
        "input": 0.25, "cache_hit_input": None, "output": 1.50, "batch_discount": 0.5,
    },
    "gemini:gemini-3.1-pro-preview": {
        "input": 2.00, "cache_hit_input": None, "output": 12.00, "batch_discount": 0.5,
    },
    "anthropic:claude-sonnet-5": {
        "input": 2.00, "cache_hit_input": None, "output": 10.00, "batch_discount": 0.5,
    },
    "openai:gpt-5.6-sol": {
        "input": 2.50, "cache_hit_input": None, "output": 15.00, "batch_discount": 0.5,
    },
}


def estimate_cost(provider_model: str, input_tokens: int, output_tokens: int, *,
                  use_batch: bool = True, cache_hit_input_tokens: int = 0) -> float:
    """Dollar cost for one call's measured usage. `output_tokens` should
    already be the provider's own completion/output token count -- if that
    call also reports reasoning_tokens, they are a SUBSET of output_tokens
    (already counted), not additional; do not add them again."""
    if provider_model not in PRICING:
        raise KeyError(f"no pricing entry for {provider_model!r} -- add it to PRICING first, "
                       f"confirmed against that provider's current docs, before using it")
    p = PRICING[provider_model]
    discount = p["batch_discount"] if (use_batch and p["batch_discount"]) else 0.0
    hit_tokens = max(0, min(cache_hit_input_tokens, input_tokens))
    miss_tokens = input_tokens - hit_tokens
    miss_rate = p["input"] * (1 - discount)
    hit_rate = (p["cache_hit_input"] if p["cache_hit_input"] is not None else p["input"]) * (1 - discount)
    out_rate = p["output"] * (1 - discount)
    return (miss_tokens / 1_000_000) * miss_rate + (hit_tokens / 1_000_000) * hit_rate \
        + (output_tokens / 1_000_000) * out_rate


def batch_discount_for(provider_model: str) -> Optional[float]:
    if provider_model not in PRICING:
        raise KeyError(f"no pricing entry for {provider_model!r}")
    return PRICING[provider_model]["batch_discount"]


__all__ = ["PRICING", "CONFIRMED_DATE", "estimate_cost", "batch_discount_for"]
