"""Provider-agnostic judge back-ends.

A judge provider turns a rendered prompt into raw model text. The harness is
built against the small :class:`JudgeProvider` protocol so that any judge is
interchangeable — which is what makes the "which models detect fabrication
better" comparison cheap once the pipeline exists.

Most vendors expose an **OpenAI-compatible** chat endpoint, so a single
:class:`OpenAICompatibleProvider` (parametrised by base URL + API-key env var)
covers OpenAI, DeepSeek, and Gemini. Anthropic uses its native Messages API.
Real SDKs are imported lazily, so the package and its tests (which use
:class:`ScriptedProvider`) work with no API keys and no SDKs installed. Model ids
are explicit and required for live runs — no evergreen aliases — so a result is
always attributable to a pinned model in the report.
"""

from __future__ import annotations

import os
import time
from typing import Callable, Optional, Protocol, runtime_checkable

from pydantic import BaseModel

# Generous default so reasoning-style judges have room to emit a final answer
# after their internal deliberation, rather than exhausting the budget mid-think
# and returning empty content.
DEFAULT_MAX_TOKENS = 8192


class CompletionResult(BaseModel):
    """A judge response plus the usage it actually cost -- added so cost can
    be measured exactly (Phase 0's cost probe) rather than estimated.
    `reasoning_tokens` is None when a provider doesn't report it (only
    reasoning/thinking-capable models do); when present it is a SUBSET of
    `output_tokens`, already included in it, not additional -- every
    provider modeled here bills reasoning tokens at the ordinary output
    rate, so it is a diagnostic field, not a separate billing line."""
    text: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    reasoning_tokens: Optional[int] = None
    cache_hit_input_tokens: Optional[int] = None  # DeepSeek only; None elsewhere


@runtime_checkable
class JudgeProvider(Protocol):
    name: str
    model: str

    def complete(self, prompt: str) -> str:
        """Return the judge model's raw text response to `prompt`."""
        ...


class OpenAICompatibleProvider:
    """Any judge reachable through the OpenAI chat-completions interface.

    `base_url=None` uses OpenAI's default endpoint. DeepSeek and Gemini just
    point `base_url` at their compatibility endpoints and read a different key.
    """

    def __init__(
        self,
        name: str,
        model: str,
        api_key_env: str,
        base_url: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        retries: int = 2,
        extra: Optional[dict] = None,
    ):
        if not model:
            raise ValueError(f"{name} provider requires an explicit model id.")
        self.name = name
        self.model = model
        self.api_key_env = api_key_env
        self.base_url = base_url
        self.max_tokens = max_tokens
        self.retries = retries
        # Extra create() kwargs (e.g. reasoning_effort for thinking models).
        self.extra = extra or {}

    def complete(self, prompt: str) -> str:
        return self.complete_with_usage(prompt).text

    def complete_with_usage(self, prompt: str) -> CompletionResult:
        from openai import OpenAI  # lazy

        key = os.environ.get(self.api_key_env)
        if not key:
            raise RuntimeError(
                f"{self.name}: environment variable {self.api_key_env} is not set."
            )
        client = OpenAI(api_key=key, base_url=self.base_url)
        last_exc: Optional[Exception] = None
        for attempt in range(self.retries + 1):
            try:
                resp = client.chat.completions.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    messages=[{"role": "user", "content": prompt}],
                    **self.extra,
                )
                content = resp.choices[0].message.content or ""
                if content.strip():
                    usage = getattr(resp, "usage", None)
                    details = getattr(usage, "completion_tokens_details", None)
                    # DeepSeek's OpenAI-compatible endpoint reports cache-hit
                    # input tokens under this field name (mirrors its native
                    # API); other OpenAI-compatible vendors simply won't set
                    # it, and getattr(..., None) makes that safe.
                    prompt_details = getattr(usage, "prompt_tokens_details", None)
                    return CompletionResult(
                        text=content,
                        input_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
                        output_tokens=getattr(usage, "completion_tokens", None) if usage else None,
                        reasoning_tokens=getattr(details, "reasoning_tokens", None) if details else None,
                        cache_hit_input_tokens=getattr(prompt_details, "cached_tokens", None) if prompt_details else None,
                    )
                # Empty content (e.g. token budget exhausted): retry once more.
                last_exc = RuntimeError("empty response content")
            except Exception as e:  # transient network / rate-limit / 5xx
                last_exc = e
            if attempt < self.retries:
                time.sleep(1.0 + attempt)
        raise RuntimeError(f"{self.name}:{self.model} failed after retries: {last_exc}")


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str, max_tokens: int = DEFAULT_MAX_TOKENS):
        if not model:
            raise ValueError("AnthropicProvider requires an explicit model id.")
        self.model = model
        self.max_tokens = max_tokens

    def complete(self, prompt: str) -> str:
        return self.complete_with_usage(prompt).text

    def complete_with_usage(self, prompt: str) -> CompletionResult:
        import anthropic  # lazy

        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("anthropic: ANTHROPIC_API_KEY is not set.")
        client = anthropic.Anthropic(api_key=key)
        resp = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            block.text for block in resp.content if getattr(block, "type", None) == "text"
        )
        usage = getattr(resp, "usage", None)
        return CompletionResult(
            text=text,
            input_tokens=getattr(usage, "input_tokens", None) if usage else None,
            output_tokens=getattr(usage, "output_tokens", None) if usage else None,
            # Anthropic does not report a separate thinking/reasoning token
            # count as of this writing -- extended-thinking tokens, if any,
            # are folded into output_tokens with no independent breakdown.
            reasoning_tokens=None,
        )


class ScriptedProvider:
    """Deterministic offline judge for tests and pipeline demos.

    `responder` maps a rendered prompt to a raw response string. Defaults to a
    fixed 'reject everything' stub. This is NOT a real judge — it exercises the
    harness plumbing without a network call.
    """

    name = "scripted"

    def __init__(self, model: str = "scripted-stub", responder: Callable[[str], str] | None = None):
        self.model = model
        self._responder = responder or (
            lambda _p: '{"verdict": "reject", "reason": "scripted stub"}'
        )

    def complete(self, prompt: str) -> str:
        return self._responder(prompt)

    def complete_with_usage(self, prompt: str) -> CompletionResult:
        # Deterministic stub -- no real usage to report. len()-based token
        # counts are provided (not None) so cost-probe code paths that sum
        # usage can be exercised in tests without a live provider; they are
        # NOT a substitute for a real tokenizer and must never appear in a
        # reported cost figure.
        text = self._responder(prompt)
        return CompletionResult(text=text, input_tokens=len(prompt) // 4,
                                output_tokens=len(text) // 4, reasoning_tokens=None)


# Base URLs and key env vars for the OpenAI-compatible vendors.
_OPENAI_COMPAT = {
    "openai": {"base_url": None, "api_key_env": "OPENAI_API_KEY", "extra": {}},
    "deepseek": {"base_url": "https://api.deepseek.com", "api_key_env": "DEEPSEEK_API_KEY",
                 "extra": {}},
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "api_key_env": "GEMINI_API_KEY",
        # Gemini 3.x are thinking models: cap deliberation so the token budget
        # isn't consumed before the final verdict is emitted.
        "extra": {"reasoning_effort": "low"},
    },
}


def build_provider(spec: str, **kwargs) -> JudgeProvider:
    """Build a provider from a ``"<provider>:<model>"`` spec string."""
    if ":" not in spec:
        raise ValueError(f"provider spec must be '<provider>:<model>', got {spec!r}")
    provider, model = spec.split(":", 1)
    provider = provider.strip().lower()

    if provider in _OPENAI_COMPAT:
        cfg = _OPENAI_COMPAT[provider]
        return OpenAICompatibleProvider(
            name=provider, model=model, api_key_env=cfg["api_key_env"],
            base_url=cfg["base_url"], extra=cfg.get("extra", {}), **kwargs
        )
    if provider == "anthropic":
        return AnthropicProvider(model=model, **kwargs)
    if provider == "scripted":
        return ScriptedProvider(model=model, **kwargs)
    raise ValueError(f"unknown provider {provider!r}")


__all__ = [
    "JudgeProvider",
    "CompletionResult",
    "OpenAICompatibleProvider",
    "AnthropicProvider",
    "ScriptedProvider",
    "build_provider",
]
