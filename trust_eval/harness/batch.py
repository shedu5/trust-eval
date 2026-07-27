"""Real batch-API submission -- an actual async job submitted to the
provider's batch endpoint, not a synchronous call priced at a discounted
rate after the fact. Anthropic, OpenAI, and Gemini each expose a real batch
mechanism (submit, poll, fetch); DeepSeek does not currently document one
for the v4 generation (see pricing.py's docstring), so its path here is an
ordinary synchronous loop at standard pricing, clearly not a batch job.

Every provider path returns the same `List[BatchResult]` shape, in the
same order as the input `requests`, so a caller never has to branch on
which provider it is talking to. Each `_run_*_batch` function accepts an
optional `client=` for tests to inject a fake SDK client -- this lets the
submit/poll/parse state machines be exercised without any network access
or API key, which is the only way this module's logic gets verified from
this sandbox (it cannot reach any of these APIs directly; see
docs/study-c-full-technical-report.md's Phase 0 section).

Real batch SLAs run up to 24 hours (Anthropic, OpenAI) — `timeout` defaults
generously and `sleep` is injectable so tests never actually wait.
"""

from __future__ import annotations

import json
import os
import time
from typing import Callable, List, Optional

from pydantic import BaseModel

DEFAULT_POLL_INTERVAL = 60.0
DEFAULT_TIMEOUT = 24 * 3600.0  # 24h -- the documented SLA ceiling for OpenAI/Anthropic batch


class BatchRequest(BaseModel):
    custom_id: str
    prompt: str


class BatchResult(BaseModel):
    custom_id: str
    text: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    reasoning_tokens: Optional[int] = None
    cache_hit_input_tokens: Optional[int] = None
    error: Optional[str] = None


def run_batch(provider_spec: str, requests: List[BatchRequest], *,
              max_tokens: int = 8192, poll_interval: float = DEFAULT_POLL_INTERVAL,
              timeout: float = DEFAULT_TIMEOUT, sleep: Callable[[float], None] = time.sleep,
              client=None) -> List[BatchResult]:
    """Dispatch to the right provider's real batch mechanism. `provider_spec`
    is "<provider>:<model>", exactly like `providers.build_provider()`.
    `client` is for test injection only -- omit it for a real run."""
    if not requests:
        return []
    if ":" not in provider_spec:
        raise ValueError(f"provider spec must be '<provider>:<model>', got {provider_spec!r}")
    provider, model = provider_spec.split(":", 1)
    provider = provider.strip().lower()
    if provider == "anthropic":
        return _run_anthropic_batch(model, requests, max_tokens, poll_interval, timeout, sleep, client)
    if provider == "openai":
        return _run_openai_batch(model, requests, max_tokens, poll_interval, timeout, sleep, client)
    if provider == "gemini":
        return _run_gemini_batch(model, requests, max_tokens, poll_interval, timeout, sleep, client)
    if provider == "deepseek":
        return _run_deepseek_synchronous(model, requests, max_tokens)
    raise ValueError(f"no batch mechanism wired for provider {provider!r}")


# ------------------------------------------------------------- Anthropic --

def _run_anthropic_batch(model: str, requests: List[BatchRequest], max_tokens: int,
                         poll_interval: float, timeout: float, sleep, client=None) -> List[BatchResult]:
    if client is None:
        import anthropic as anthropic_sdk
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("anthropic: ANTHROPIC_API_KEY is not set.")
        client = anthropic_sdk.Anthropic(api_key=key)

    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request as BatchCreateRequest

    batch_requests = [
        BatchCreateRequest(
            custom_id=r.custom_id,
            params=MessageCreateParamsNonStreaming(
                model=model, max_tokens=max_tokens,
                messages=[{"role": "user", "content": r.prompt}],
            ),
        )
        for r in requests
    ]
    batch = client.messages.batches.create(requests=batch_requests)
    batch_id = batch.id

    elapsed = 0.0
    while batch.processing_status != "ended":
        if elapsed >= timeout:
            raise TimeoutError(f"anthropic batch {batch_id} did not end within {timeout}s")
        sleep(poll_interval)
        elapsed += poll_interval
        batch = client.messages.batches.retrieve(batch_id)

    by_id = {}
    for item in client.messages.batches.results(batch_id):
        if item.result.type == "succeeded":
            msg = item.result.message
            text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
            usage = getattr(msg, "usage", None)
            by_id[item.custom_id] = BatchResult(
                custom_id=item.custom_id, text=text,
                input_tokens=getattr(usage, "input_tokens", None) if usage else None,
                output_tokens=getattr(usage, "output_tokens", None) if usage else None,
                # No separate reasoning-token count reported -- see providers.py.
                reasoning_tokens=None,
            )
        else:
            by_id[item.custom_id] = BatchResult(custom_id=item.custom_id, error=str(item.result.type))
    return [by_id.get(r.custom_id, BatchResult(custom_id=r.custom_id, error="missing from batch results"))
            for r in requests]


# ---------------------------------------------------------------- OpenAI --

def _run_openai_batch(model: str, requests: List[BatchRequest], max_tokens: int,
                      poll_interval: float, timeout: float, sleep, client=None) -> List[BatchResult]:
    if client is None:
        from openai import OpenAI
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("openai: OPENAI_API_KEY is not set.")
        client = OpenAI(api_key=key)

    lines = [
        json.dumps({
            "custom_id": r.custom_id,
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {"model": model, "max_tokens": max_tokens,
                     "messages": [{"role": "user", "content": r.prompt}]},
        })
        for r in requests
    ]
    jsonl_bytes = ("\n".join(lines) + "\n").encode("utf-8")
    uploaded = client.files.create(file=("batch_input.jsonl", jsonl_bytes), purpose="batch")
    batch = client.batches.create(input_file_id=uploaded.id, endpoint="/v1/chat/completions",
                                  completion_window="24h")

    elapsed = 0.0
    terminal = {"completed", "failed", "expired", "cancelled"}
    while batch.status not in terminal:
        if elapsed >= timeout:
            raise TimeoutError(f"openai batch {batch.id} did not complete within {timeout}s")
        sleep(poll_interval)
        elapsed += poll_interval
        batch = client.batches.retrieve(batch.id)

    if batch.status != "completed" or not getattr(batch, "output_file_id", None):
        raise RuntimeError(f"openai batch {batch.id} ended with status {batch.status!r}, no output file "
                           f"(errors, if any, are in batch.error_file_id -- fetch and inspect before retrying)")

    raw = client.files.content(batch.output_file_id).text
    by_id = {}
    for line in raw.splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        cid = rec.get("custom_id")
        resp = rec.get("response") or {}
        body = resp.get("body") or {}
        if rec.get("error") or resp.get("status_code") != 200:
            by_id[cid] = BatchResult(custom_id=cid, error=str(rec.get("error") or resp.get("status_code")))
            continue
        choice = (body.get("choices") or [{}])[0]
        text = ((choice.get("message") or {}).get("content")) or ""
        usage = body.get("usage") or {}
        reasoning = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
        by_id[cid] = BatchResult(custom_id=cid, text=text,
                                 input_tokens=usage.get("prompt_tokens"),
                                 output_tokens=usage.get("completion_tokens"),
                                 reasoning_tokens=reasoning)
    return [by_id.get(r.custom_id, BatchResult(custom_id=r.custom_id, error="missing from output file"))
            for r in requests]


# ---------------------------------------------------------------- Gemini --

def _run_gemini_batch(model: str, requests: List[BatchRequest], max_tokens: int,
                      poll_interval: float, timeout: float, sleep, client=None) -> List[BatchResult]:
    """Uses the native `google-genai` SDK's batch mode, NOT the OpenAI-
    compatible endpoint the synchronous path in providers.py goes through
    -- Gemini's real batch submission (`client.batches.create`) is only
    exposed via the native client as of the docs checked for this build
    (2026-07-24). `usage_metadata.thoughts_token_count` is this module's
    best-effort read of Gemini's thinking-token field; it was not directly
    confirmed against a live response (this sandbox cannot reach the API --
    see docs/study-c-full-technical-report.md's Phase 0 section), so treat it as unverified until a
    real run confirms the field name."""
    if client is None:
        from google import genai
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("gemini: GEMINI_API_KEY is not set.")
        client = genai.Client(api_key=key)

    inline_requests = [
        {"contents": [{"parts": [{"text": r.prompt}], "role": "user"}]}
        for r in requests
    ]
    job = client.batches.create(model=model, src=inline_requests,
                                config={"display_name": "trust-eval-study-c-batch"})

    completed_states = {"JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED"}
    elapsed = 0.0
    job = client.batches.get(name=job.name)
    while job.state.name not in completed_states:
        if elapsed >= timeout:
            raise TimeoutError(f"gemini batch {job.name} did not finish within {timeout}s")
        sleep(poll_interval)
        elapsed += poll_interval
        job = client.batches.get(name=job.name)

    if job.state.name != "JOB_STATE_SUCCEEDED":
        raise RuntimeError(f"gemini batch {job.name} ended with state {job.state.name}")

    results: List[BatchResult] = []
    responses = (job.dest.inlined_responses if job.dest else None) or []
    for r, inline_response in zip(requests, responses):
        if getattr(inline_response, "response", None) is not None:
            resp = inline_response.response
            text = getattr(resp, "text", "") or ""
            usage = getattr(resp, "usage_metadata", None)
            results.append(BatchResult(
                custom_id=r.custom_id, text=text,
                input_tokens=getattr(usage, "prompt_token_count", None) if usage else None,
                output_tokens=getattr(usage, "candidates_token_count", None) if usage else None,
                reasoning_tokens=getattr(usage, "thoughts_token_count", None) if usage else None,
            ))
        else:
            results.append(BatchResult(custom_id=r.custom_id, error=str(getattr(inline_response, "error", "unknown"))))
    return results


# --------------------------------------------------------------- DeepSeek --

def _run_deepseek_synchronous(model: str, requests: List[BatchRequest], max_tokens: int) -> List[BatchResult]:
    """No confirmed batch/off-peak mechanism for deepseek-v4 as of
    2026-07-24 -- see pricing.py's docstring. Runs the ordinary synchronous
    endpoint, one call per request, at STANDARD pricing. Not a batch job;
    named `_synchronous`, not `_batch`, to keep that visible in the call
    graph, not just in a comment."""
    from .providers import OpenAICompatibleProvider
    provider = OpenAICompatibleProvider(name="deepseek", model=model,
                                        api_key_env="DEEPSEEK_API_KEY",
                                        base_url="https://api.deepseek.com",
                                        max_tokens=max_tokens)
    results: List[BatchResult] = []
    for r in requests:
        try:
            cr = provider.complete_with_usage(r.prompt)
            results.append(BatchResult(custom_id=r.custom_id, text=cr.text,
                                       input_tokens=cr.input_tokens, output_tokens=cr.output_tokens,
                                       reasoning_tokens=cr.reasoning_tokens,
                                       cache_hit_input_tokens=cr.cache_hit_input_tokens))
        except Exception as e:
            results.append(BatchResult(custom_id=r.custom_id, error=str(e)[:200]))
    return results


__all__ = ["BatchRequest", "BatchResult", "run_batch",
           "DEFAULT_POLL_INTERVAL", "DEFAULT_TIMEOUT"]
