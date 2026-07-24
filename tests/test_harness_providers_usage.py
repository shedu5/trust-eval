"""Tests for `complete_with_usage` -- the token-usage capture added for
Phase 0's cost probe. Uses fake SDK client objects (SimpleNamespace) via
monkeypatch, since this sandbox has no API keys and no network access to
any of these providers (see report.md's Phase 0 section) -- these tests
are the only way this logic gets verified before a real run.
"""

from types import SimpleNamespace

import pytest

from trust_eval.harness.providers import (
    AnthropicProvider,
    CompletionResult,
    OpenAICompatibleProvider,
    ScriptedProvider,
)


def test_scripted_provider_reports_usage_and_matches_complete():
    prov = ScriptedProvider(model="stub", responder=lambda p: "some reply text")
    cr = prov.complete_with_usage("some prompt text")
    assert isinstance(cr, CompletionResult)
    assert cr.text == "some reply text"
    assert cr.text == prov.complete("some prompt text")
    assert cr.input_tokens is not None and cr.output_tokens is not None
    assert cr.reasoning_tokens is None


def test_openai_compatible_complete_with_usage_full_fields(monkeypatch):
    usage = SimpleNamespace(
        prompt_tokens=120, completion_tokens=340,
        completion_tokens_details=SimpleNamespace(reasoning_tokens=280),
        prompt_tokens_details=SimpleNamespace(cached_tokens=40),
    )
    resp = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="  {\"verdict\":\"accept\"}  "))],
                           usage=usage)

    class FakeCompletions:
        def create(self, **kwargs):
            return resp

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = FakeChat()

    import openai
    monkeypatch.setattr(openai, "OpenAI", FakeClient)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    prov = OpenAICompatibleProvider(name="deepseek", model="deepseek-v4-pro",
                                    api_key_env="DEEPSEEK_API_KEY",
                                    base_url="https://api.deepseek.com")
    cr = prov.complete_with_usage("prompt")
    assert cr.text == "  {\"verdict\":\"accept\"}  "
    assert cr.input_tokens == 120
    assert cr.output_tokens == 340
    assert cr.reasoning_tokens == 280   # subset of output_tokens, reported for visibility
    assert cr.cache_hit_input_tokens == 40


def test_openai_compatible_complete_with_usage_missing_reasoning_fields_is_none(monkeypatch):
    # A non-reasoning model's usage object has no completion_tokens_details
    # / prompt_tokens_details at all -- getattr(..., None) must not raise.
    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5)
    resp = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))], usage=usage)

    class FakeCompletions:
        def create(self, **kwargs):
            return resp

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    import openai
    monkeypatch.setattr(openai, "OpenAI", FakeClient)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    prov = OpenAICompatibleProvider(name="gemini", model="gemini-3.1-flash-lite",
                                    api_key_env="GEMINI_API_KEY")
    cr = prov.complete_with_usage("prompt")
    assert cr.reasoning_tokens is None
    assert cr.cache_hit_input_tokens is None
    assert cr.input_tokens == 10 and cr.output_tokens == 5


def test_anthropic_complete_with_usage(monkeypatch):
    resp = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="hello "), SimpleNamespace(type="text", text="world")],
        usage=SimpleNamespace(input_tokens=7, output_tokens=3),
    )

    class FakeMessages:
        def create(self, **kwargs):
            return resp

    class FakeClient:
        def __init__(self, **kwargs):
            self.messages = FakeMessages()

    import anthropic
    monkeypatch.setattr(anthropic, "Anthropic", FakeClient)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    prov = AnthropicProvider(model="claude-sonnet-5")
    cr = prov.complete_with_usage("prompt")
    assert cr.text == "hello world"
    assert cr.input_tokens == 7
    assert cr.output_tokens == 3
    # Anthropic reports no separate reasoning/thinking token count.
    assert cr.reasoning_tokens is None
    assert cr.text == prov.complete("prompt")


def test_no_key_raises_before_any_network_attempt(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    prov = OpenAICompatibleProvider(name="openai", model="gpt-5.6-sol", api_key_env="OPENAI_API_KEY")
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        prov.complete_with_usage("prompt")
