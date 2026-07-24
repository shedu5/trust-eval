"""Tests for harness/pricing.py's cost arithmetic -- confirmed against
each provider's live docs on 2026-07-24 (see report.md's Phase 0 section
for sources); these tests check the ARITHMETIC is correct given those
confirmed numbers, not the numbers themselves (that's a documentation
fact, re-verify against the docs if it goes stale).
"""

import pytest

from trust_eval.harness.pricing import PRICING, batch_discount_for, estimate_cost


def test_deepseek_has_no_confirmed_batch_discount():
    """The load-bearing fact behind Phase 0's DeepSeek pricing decision --
    if this ever flips true, the report's Phase 0 section needs revisiting,
    which is exactly why it's asserted here, not just documented."""
    assert batch_discount_for("deepseek:deepseek-v4-flash") is None
    assert batch_discount_for("deepseek:deepseek-v4-pro") is None


def test_deepseek_use_batch_true_has_no_effect_without_a_confirmed_discount():
    cost_batch = estimate_cost("deepseek:deepseek-v4-pro", 1_000_000, 1_000_000, use_batch=True)
    cost_sync = estimate_cost("deepseek:deepseek-v4-pro", 1_000_000, 1_000_000, use_batch=False)
    assert cost_batch == cost_sync == pytest.approx(0.435 + 0.87)


def test_strong_tier_batch_discount_is_exactly_half():
    for pm in ("gemini:gemini-3.1-pro-preview", "anthropic:claude-sonnet-5", "openai:gpt-5.6-sol"):
        p = PRICING[pm]
        full = estimate_cost(pm, 1_000_000, 1_000_000, use_batch=False)
        half = estimate_cost(pm, 1_000_000, 1_000_000, use_batch=True)
        assert half == pytest.approx(full / 2), pm
        assert full == pytest.approx(p["input"] + p["output"]), pm


def test_deepseek_cache_hit_tokens_priced_at_hit_rate():
    p = PRICING["deepseek:deepseek-v4-pro"]
    # 100 input tokens, 40 of them cache-hit
    cost = estimate_cost("deepseek:deepseek-v4-pro", input_tokens=100, output_tokens=0,
                         cache_hit_input_tokens=40)
    expected = (60 / 1_000_000) * p["input"] + (40 / 1_000_000) * p["cache_hit_input"]
    assert cost == pytest.approx(expected)


def test_cache_hit_tokens_clamped_to_input_tokens():
    # Asking for more cache-hit tokens than total input must not go negative.
    cost = estimate_cost("deepseek:deepseek-v4-pro", input_tokens=10, output_tokens=0,
                         cache_hit_input_tokens=999)
    p = PRICING["deepseek:deepseek-v4-pro"]
    assert cost == pytest.approx((10 / 1_000_000) * p["cache_hit_input"])


def test_unknown_model_raises_rather_than_silently_pricing_at_zero():
    with pytest.raises(KeyError):
        estimate_cost("openai:some-future-model", 100, 100)
