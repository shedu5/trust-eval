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
import random
import time
from typing import Callable, Optional, Protocol, runtime_checkable

from pydantic import BaseModel

# Generous default so reasoning-style judges have room to emit a final answer
# after their internal deliberation, rather than exhausting the budget mid-think
# and returning empty content.
DEFAULT_MAX_TOKENS = 8192


def _is_rate_limit_error(exc: Exception) -> bool:
    """HTTP 429 / RESOURCE_EXHAUSTED -- a quota or requests-per-minute limit,
    not a transient network blip. Gemini's docs (checked directly,
    2026-07-24, ai.google.dev/gemini-api/docs/troubleshooting) confirm 429
    means RESOURCE_EXHAUSTED (any of RPM/TPM/RPD/spend) but do NOT document
    a Retry-After value in the response -- their own guidance is generic
    exponential backoff with jitter, which is what `_rate_limit_backoff`
    below implements. A short 1-2s backoff (fine for a genuine transient
    5xx) is USELESS against a per-minute quota and just burns the retry
    budget instantly -- this is what silently made a rate limit look like a
    hang before an explicit timeout was added."""
    msg = str(exc)
    return "429" in msg or "RESOURCE_EXHAUSTED" in msg or "rate limit" in msg.lower()


def _rate_limit_backoff(attempt: int) -> float:
    """Exponential backoff with jitter, capped at 60s -- long enough to
    plausibly clear a per-minute quota window, short enough not to stall a
    whole run on one case if the account is upgraded mid-run."""
    return min(60.0, 20.0 * (2 ** attempt)) + random.uniform(0, 3)


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
        timeout: float = 60.0,
        min_interval: float = 0.0,
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
        # Explicit per-request timeout (seconds). Without this the underlying
        # SDK's own default applies, which can leave a single stalled
        # request (connection accepted, server never responds) hanging far
        # longer than is useful for an interactive/scripted run -- observed
        # live against Gemini's endpoint on 2026-07-24: a request sat with
        # the process alive but near-zero CPU for 30+ minutes with nothing
        # written to the cache, well past what a real "just slow" response
        # should take. 60s makes a genuine stall fail fast into the retry
        # loop below (worst case ~(retries+1)*60s instead of unbounded).
        self.timeout = timeout
        # Proactive pacing: minimum seconds between the START of one call
        # and the start of the next, enforced BEFORE firing a request, not
        # just reactively after a 429. Default 0.0 (no change) for
        # providers that haven't needed it. Added after a live run against
        # gemini:gemini-3.1-pro-preview showed the 429-then-backoff loop
        # alone isn't enough for a surface that fires many calls back-to-
        # back with no gap (e.g. a 50-case single-claim ladder) -- a burst
        # can blow through a per-minute quota before any single call ever
        # fails, so there's nothing for the reactive backoff to catch. This
        # is a floor, not a guarantee -- it does not replace the reactive
        # backoff, which still handles whatever a burst estimate misses.
        self.min_interval = min_interval
        self._last_call_start: Optional[float] = None

    def complete(self, prompt: str) -> str:
        return self.complete_with_usage(prompt).text

    def complete_with_usage(self, prompt: str) -> CompletionResult:
        return self.complete_with_usage_messages([{"role": "user", "content": prompt}])

    def complete_with_usage_messages(self, messages: list[dict]) -> CompletionResult:
        """Same call/retry/backoff path as `complete_with_usage`, but takes a
        full messages list instead of wrapping a single prompt string. This is
        what a genuine multi-turn follow-up needs -- e.g. asking a judge a
        second question with its own first-turn verdict still in context --
        which `complete_with_usage` cannot express since it always sends
        exactly one user turn. `complete_with_usage` is now a one-line
        wrapper around this so existing single-turn callers are unaffected."""
        from openai import OpenAI  # lazy

        if self.min_interval > 0 and self._last_call_start is not None:
            elapsed = time.time() - self._last_call_start
            wait = self.min_interval - elapsed
            if wait > 0:
                time.sleep(wait)
        self._last_call_start = time.time()

        key = os.environ.get(self.api_key_env)
        if not key:
            raise RuntimeError(
                f"{self.name}: environment variable {self.api_key_env} is not set."
            )
        client = OpenAI(api_key=key, base_url=self.base_url, timeout=self.timeout)
        last_exc: Optional[Exception] = None
        for attempt in range(self.retries + 1):
            try:
                resp = client.chat.completions.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    messages=messages,
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
                if _is_rate_limit_error(last_exc):
                    time.sleep(_rate_limit_backoff(attempt))
                else:
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

    def complete_with_usage_messages(self, messages: list[dict]) -> CompletionResult:
        # `responder` only understands a single prompt string, so the stub
        # concatenates each turn's role/content -- deterministic and good
        # enough for exercising multi-turn plumbing in tests, not a real
        # conversation model.
        joined = "\n".join(f"[{m['role']}] {m['content']}" for m in messages)
        return self.complete_with_usage(joined)


# Base URLs and key env vars for the OpenAI-compatible vendors.
_OPENAI_COMPAT = {
    "openai": {"base_url": None, "api_key_env": "OPENAI_API_KEY", "extra": {}, "min_interval": 0.0},
    "deepseek": {"base_url": "https://api.deepseek.com", "api_key_env": "DEEPSEEK_API_KEY",
                 "extra": {}, "min_interval": 0.0},
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "api_key_env": "GEMINI_API_KEY",
        # Gemini 3.x are thinking models: cap deliberation so the token budget
        # isn't consumed before the final verdict is emitted.
        "extra": {"reasoning_effort": "low"},
        # Proactive pacing floor: a live run against gemini-3.1-pro-preview
        # on 2026-07-24 hit sustained 429s specifically on high-call-volume
        # surfaces (e.g. a 50-case single-claim ladder firing calls back-
        # to-back), even on a confirmed Tier 1 (billing-linked) account --
        # the reactive backoff alone can't prevent a burst from outrunning
        # a per-minute quota before any call has failed. 3.0s targets
        # roughly 20 requests/minute, in the neighborhood of third-party-
        # reported (NOT Google-published; Google doesn't expose exact
        # numbers outside the AI Studio dashboard) Tier 1 limits for Gemini
        # 3 Pro-series preview models (~20-25 RPM) -- a floor, not a
        # guarantee; the reactive 429 backoff still applies on top of this
        # for whatever a burst estimate misses.
        "min_interval": 3.0,
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
        kwargs.setdefault("min_interval", cfg.get("min_interval", 0.0))
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
