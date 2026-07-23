"""Provider-agnostic judge back-ends.

A judge provider turns a rendered prompt into raw model text. The harness is
built against the small :class:`JudgeProvider` protocol so that Anthropic,
OpenAI, or an offline scripted judge are interchangeable — which is what makes
the "which models detect fabrication better" comparison cheap once the pipeline
exists.

The real SDK clients are imported lazily, so the package (and its tests, which
use :class:`ScriptedProvider`) work with no API keys and no SDKs installed.
Model ids are explicit and required for live runs — no `-latest` aliases — so a
result is always attributable to a pinned model in the report.
"""

from __future__ import annotations

import os
from typing import Callable, Dict, Protocol, runtime_checkable


@runtime_checkable
class JudgeProvider(Protocol):
    name: str
    model: str

    def complete(self, prompt: str) -> str:
        """Return the judge model's raw text response to `prompt`."""
        ...


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str, max_tokens: int = 512):
        if not model:
            raise ValueError("AnthropicProvider requires an explicit model id.")
        self.model = model
        self.max_tokens = max_tokens

    def complete(self, prompt: str) -> str:
        import anthropic  # lazy

        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        resp = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            block.text for block in resp.content if getattr(block, "type", None) == "text"
        )


class OpenAIProvider:
    name = "openai"

    def __init__(self, model: str, max_tokens: int = 512):
        if not model:
            raise ValueError("OpenAIProvider requires an explicit model id.")
        self.model = model
        self.max_tokens = max_tokens

    def complete(self, prompt: str) -> str:
        from openai import OpenAI  # lazy

        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        resp = client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content or ""


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


def build_provider(spec: str, **kwargs) -> JudgeProvider:
    """Build a provider from a ``"<provider>:<model>"`` spec string."""
    if ":" not in spec:
        raise ValueError(f"provider spec must be '<provider>:<model>', got {spec!r}")
    provider, model = spec.split(":", 1)
    provider = provider.strip().lower()
    if provider == "anthropic":
        return AnthropicProvider(model=model, **kwargs)
    if provider == "openai":
        return OpenAIProvider(model=model, **kwargs)
    if provider == "scripted":
        return ScriptedProvider(model=model, **kwargs)
    raise ValueError(f"unknown provider {provider!r}")


__all__ = [
    "JudgeProvider",
    "AnthropicProvider",
    "OpenAIProvider",
    "ScriptedProvider",
    "build_provider",
]
