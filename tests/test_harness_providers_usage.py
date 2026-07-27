"""Tests for `complete_with_usage` -- the token-usage capture added for
Phase 0's cost probe. Uses fake SDK client objects (SimpleNamespace) via
monkeypatch, since this sandbox has no API keys and no network access to
any of these providers (see docs/study-c-full-technical-report.md's Phase 0 section) -- these tests
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


def test_default_timeout_is_finite_and_passed_to_client(monkeypatch):
    # A live Gemini run sat idle for 30+ minutes on 2026-07-24 with no
    # explicit timeout set -- the client MUST be constructed with a finite
    # timeout so a genuinely stalled request fails into the retry loop
    # instead of hanging indefinitely.
    captured = {}
    usage = SimpleNamespace(prompt_tokens=1, completion_tokens=1)
    resp = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))], usage=usage)

    class FakeCompletions:
        def create(self, **kwargs):
            return resp

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.chat = FakeChat()

    import openai
    monkeypatch.setattr(openai, "OpenAI", FakeClient)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    prov = OpenAICompatibleProvider(name="gemini", model="gemini-3.1-pro-preview",
                                    api_key_env="GEMINI_API_KEY")
    prov.complete_with_usage("prompt")
    assert "timeout" in captured
    assert captured["timeout"] == 60.0  # the default -- finite, not None/unset
    assert prov.timeout == 60.0


def test_explicit_timeout_overrides_default(monkeypatch):
    captured = {}
    usage = SimpleNamespace(prompt_tokens=1, completion_tokens=1)
    resp = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))], usage=usage)

    class FakeCompletions:
        def create(self, **kwargs):
            return resp

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.chat = FakeChat()

    import openai
    monkeypatch.setattr(openai, "OpenAI", FakeClient)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    prov = OpenAICompatibleProvider(name="deepseek", model="deepseek-v4-pro",
                                    api_key_env="DEEPSEEK_API_KEY", timeout=15.0)
    prov.complete_with_usage("prompt")
    assert captured["timeout"] == 15.0


def test_rate_limit_error_gets_long_backoff_not_generic_short_one(monkeypatch):
    # A 429 was observed live against gemini:gemini-3.1-pro-preview on
    # 2026-07-24 -- the generic 1-2s backoff is useless against a
    # per-minute quota and just burns the retry budget instantly. A 429
    # must sleep much longer (>=15s here; real backoff is 20-63s) than a
    # same-shaped non-429 error (<=2s), so the two paths must diverge.
    sleeps = []
    monkeypatch.setattr("trust_eval.harness.providers.time.sleep", lambda s: sleeps.append(s))
    monkeypatch.setattr("trust_eval.harness.providers.random.uniform", lambda a, b: 0.0)

    class FakeCompletions:
        def create(self, **kwargs):
            raise RuntimeError("Error code: 429 - [{'error': {'code': 429, "
                              "'message': 'You exceeded your current quota'}}]")

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = FakeChat()

    import openai
    monkeypatch.setattr(openai, "OpenAI", FakeClient)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    prov = OpenAICompatibleProvider(name="gemini", model="gemini-3.1-pro-preview",
                                    api_key_env="GEMINI_API_KEY", retries=2)
    with pytest.raises(RuntimeError, match="failed after retries"):
        prov.complete_with_usage("prompt")
    assert len(sleeps) == 2         # one sleep between each of the 3 attempts
    assert all(s >= 15.0 for s in sleeps)   # long backoff, not the generic 1-2s


def test_non_rate_limit_error_keeps_the_short_generic_backoff(monkeypatch):
    sleeps = []
    monkeypatch.setattr("trust_eval.harness.providers.time.sleep", lambda s: sleeps.append(s))

    class FakeCompletions:
        def create(self, **kwargs):
            raise RuntimeError("connection reset by peer")

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = FakeChat()

    import openai
    monkeypatch.setattr(openai, "OpenAI", FakeClient)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    prov = OpenAICompatibleProvider(name="deepseek", model="deepseek-v4-pro",
                                    api_key_env="DEEPSEEK_API_KEY", retries=2)
    with pytest.raises(RuntimeError, match="failed after retries"):
        prov.complete_with_usage("prompt")
    assert len(sleeps) == 2
    assert all(s <= 2.0 for s in sleeps)   # unchanged generic backoff for non-429s


def test_min_interval_paces_successive_calls(monkeypatch):
    # A live run against gemini:gemini-3.1-pro-preview hit sustained 429s on
    # a high-volume surface even on a confirmed Tier 1 account -- the
    # reactive backoff alone can't stop a burst from outrunning a per-
    # minute quota before any call has failed. min_interval enforces a
    # floor between call STARTS, checked before firing, not after failing.
    times = iter([100.0, 100.4, 103.4])  # call1 start, call2 check, (after sleep) call2 start
    monkeypatch.setattr("trust_eval.harness.providers.time.time", lambda: next(times))
    sleeps = []
    monkeypatch.setattr("trust_eval.harness.providers.time.sleep", lambda s: sleeps.append(s))

    usage = SimpleNamespace(prompt_tokens=1, completion_tokens=1)
    resp = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))], usage=usage)

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
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    prov = OpenAICompatibleProvider(name="gemini", model="gemini-3.1-pro-preview",
                                    api_key_env="GEMINI_API_KEY", min_interval=3.0)
    prov.complete_with_usage("prompt")   # first call: no prior call, no pacing sleep
    assert sleeps == []
    prov.complete_with_usage("prompt")   # second call, only 0.4s after the first: must wait
    assert len(sleeps) == 1
    assert 2.5 <= sleeps[0] <= 3.0        # ~2.6s remaining to reach the 3.0s floor


def test_min_interval_defaults_to_zero_and_never_sleeps(monkeypatch):
    sleeps = []
    monkeypatch.setattr("trust_eval.harness.providers.time.sleep", lambda s: sleeps.append(s))
    usage = SimpleNamespace(prompt_tokens=1, completion_tokens=1)
    resp = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))], usage=usage)

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
                                    api_key_env="DEEPSEEK_API_KEY")
    prov.complete_with_usage("prompt")
    prov.complete_with_usage("prompt")
    assert sleeps == []   # default min_interval=0.0 -- no pacing behavior change


def test_build_provider_gives_gemini_a_pacing_floor_but_not_deepseek(monkeypatch):
    from trust_eval.harness.providers import build_provider
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    gem = build_provider("gemini:gemini-3.1-pro-preview")
    ds = build_provider("deepseek:deepseek-v4-pro")
    assert gem.min_interval == 3.0
    assert ds.min_interval == 0.0
