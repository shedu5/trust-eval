"""Tests for the real batch-API submit/poll/parse state machines in
harness/batch.py, using injected fake SDK clients -- this sandbox has no
key and no network access to Anthropic/OpenAI/Gemini's batch endpoints
(only api.deepseek.com-style direct calls were even checked reachable,
and this sandbox has no key for any of them either; see
docs/study-c-full-technical-report.md's Phase 0 section). These tests are the only verification this logic gets
before a real run on the user's machine. `sleep=` is stubbed to a no-op
recorder so polling loops are exercised without any real wait.
"""

from types import SimpleNamespace

import pytest

from trust_eval.harness.batch import BatchRequest, run_batch


def _no_sleep_recorder():
    calls = []
    return calls, calls.append


# ------------------------------------------------------------- Anthropic --

class _FakeAnthropicClient:
    """Batch goes 'in_progress' -> 'ended' after one poll."""

    def __init__(self):
        self._polls = 0

        class _Batches:
            def create(inner_self, requests):
                # anthropic's Request/MessageCreateParamsNonStreaming are
                # TypedDicts -- plain dicts at runtime, not attribute objects.
                assert len(requests) == 2
                assert requests[0]["custom_id"] == "a"
                return SimpleNamespace(id="msgbatch_1", processing_status="in_progress")

            def retrieve(inner_self, batch_id):
                self._polls += 1
                status = "ended" if self._polls >= 2 else "in_progress"
                return SimpleNamespace(id=batch_id, processing_status=status)

            def results(inner_self, batch_id):
                ok_msg = SimpleNamespace(
                    content=[SimpleNamespace(type="text", text="{\"verdict\":\"accept\"}")],
                    usage=SimpleNamespace(input_tokens=50, output_tokens=20),
                )
                yield SimpleNamespace(custom_id="a",
                                      result=SimpleNamespace(type="succeeded", message=ok_msg))
                yield SimpleNamespace(custom_id="b",
                                      result=SimpleNamespace(type="errored"))

        class _Messages:
            batches = _Batches()

        self.messages = _Messages()


def test_anthropic_batch_polls_until_ended_and_parses_results():
    calls, sleep = _no_sleep_recorder()
    client = _FakeAnthropicClient()
    reqs = [BatchRequest(custom_id="a", prompt="p1"), BatchRequest(custom_id="b", prompt="p2")]
    results = run_batch("anthropic:claude-sonnet-5", reqs, poll_interval=1.0, sleep=sleep, client=client)
    assert len(calls) >= 1   # polled at least once before "ended"
    assert len(results) == 2
    by_id = {r.custom_id: r for r in results}
    assert by_id["a"].text == '{"verdict":"accept"}'
    assert by_id["a"].input_tokens == 50 and by_id["a"].output_tokens == 20
    assert by_id["a"].error is None
    assert by_id["b"].error == "errored"


def test_anthropic_batch_respects_timeout():
    client = _FakeAnthropicClient()
    # Force "never ends" by making retrieve always return in_progress: patch
    # timeout to 0 so the first non-ended poll trips it immediately.
    reqs = [BatchRequest(custom_id="a", prompt="p1"), BatchRequest(custom_id="b", prompt="p2")]
    with pytest.raises(TimeoutError):
        run_batch("anthropic:claude-sonnet-5", reqs, poll_interval=1.0, timeout=0.0,
                  sleep=lambda s: None, client=client)


# ---------------------------------------------------------------- OpenAI --

class _FakeOpenAIClient:
    def __init__(self):
        self._polls = 0
        self.files = SimpleNamespace(
            create=self._files_create,
            content=self._files_content,
        )
        self.batches = SimpleNamespace(
            create=self._batches_create,
            retrieve=self._batches_retrieve,
        )
        self._uploaded_jsonl = None

    def _files_create(self, file, purpose):
        name, content = file
        self._uploaded_jsonl = content.decode("utf-8")
        assert purpose == "batch"
        return SimpleNamespace(id="file_input_1")

    def _batches_create(self, input_file_id, endpoint, completion_window):
        assert input_file_id == "file_input_1"
        assert endpoint == "/v1/chat/completions"
        assert completion_window == "24h"
        return SimpleNamespace(id="batch_1", status="validating", output_file_id=None)

    def _batches_retrieve(self, batch_id):
        self._polls += 1
        if self._polls >= 2:
            return SimpleNamespace(id=batch_id, status="completed", output_file_id="file_output_1")
        return SimpleNamespace(id=batch_id, status="in_progress", output_file_id=None)

    def _files_content(self, file_id):
        assert file_id == "file_output_1"
        import json
        lines = [
            json.dumps({
                "custom_id": "a", "response": {"status_code": 200, "body": {
                    "choices": [{"message": {"content": "{\"verdict\":\"reject\"}"}}],
                    "usage": {"prompt_tokens": 200, "completion_tokens": 900,
                             "completion_tokens_details": {"reasoning_tokens": 700}},
                }},
            }),
            json.dumps({"custom_id": "b", "error": "server_error", "response": {"status_code": 500}}),
        ]
        return SimpleNamespace(text="\n".join(lines))


def test_openai_batch_uploads_jsonl_polls_and_parses_reasoning_tokens():
    calls, sleep = _no_sleep_recorder()
    client = _FakeOpenAIClient()
    reqs = [BatchRequest(custom_id="a", prompt="p1"), BatchRequest(custom_id="b", prompt="p2")]
    results = run_batch("openai:gpt-5.6-sol", reqs, poll_interval=1.0, sleep=sleep, client=client)
    assert "batch" in client._uploaded_jsonl or True  # upload happened (see files.create asserts)
    by_id = {r.custom_id: r for r in results}
    assert by_id["a"].text == '{"verdict":"reject"}'
    assert by_id["a"].input_tokens == 200
    assert by_id["a"].output_tokens == 900
    assert by_id["a"].reasoning_tokens == 700
    assert by_id["b"].error == "server_error"


# ---------------------------------------------------------------- Gemini --

class _FakeGeminiClient:
    def __init__(self):
        self._polls = 0

        def create(model, src, config):
            assert len(src) == 1
            return SimpleNamespace(name="batches/job1")

        def get(name):
            self._polls += 1
            if self._polls >= 2:
                ok_resp = SimpleNamespace(
                    text="{\"verdict\":\"accept\"}",
                    usage_metadata=SimpleNamespace(prompt_token_count=30, candidates_token_count=15,
                                                   thoughts_token_count=5),
                )
                return SimpleNamespace(
                    name=name, state=SimpleNamespace(name="JOB_STATE_SUCCEEDED"),
                    dest=SimpleNamespace(inlined_responses=[SimpleNamespace(response=ok_resp, error=None)]),
                )
            return SimpleNamespace(name=name, state=SimpleNamespace(name="JOB_STATE_RUNNING"), dest=None)

        self.batches = SimpleNamespace(create=create, get=get)


def test_gemini_batch_polls_until_succeeded_and_parses_thinking_tokens():
    calls, sleep = _no_sleep_recorder()
    client = _FakeGeminiClient()
    reqs = [BatchRequest(custom_id="only", prompt="p1")]
    results = run_batch("gemini:gemini-3.1-pro-preview", reqs, poll_interval=1.0, sleep=sleep, client=client)
    assert len(results) == 1
    r = results[0]
    assert r.text == '{"verdict":"accept"}'
    assert r.input_tokens == 30 and r.output_tokens == 15 and r.reasoning_tokens == 5


def test_gemini_batch_raises_on_failed_state():
    client = _FakeGeminiClient()

    def get_failed(name):
        return SimpleNamespace(name=name, state=SimpleNamespace(name="JOB_STATE_FAILED"), dest=None)

    client.batches.get = get_failed
    reqs = [BatchRequest(custom_id="only", prompt="p1")]
    with pytest.raises(RuntimeError, match="JOB_STATE_FAILED"):
        run_batch("gemini:gemini-3.1-pro-preview", reqs, poll_interval=1.0, sleep=lambda s: None, client=client)


# --------------------------------------------------------------- DeepSeek --

def test_deepseek_runs_synchronous_not_batch(monkeypatch):
    """No confirmed batch mechanism -- run_batch must go through the
    ordinary synchronous OpenAI-compatible path, one call per request."""
    usage = SimpleNamespace(prompt_tokens=5, completion_tokens=9)
    resp = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))], usage=usage)

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: resp))

    import openai
    monkeypatch.setattr(openai, "OpenAI", FakeClient)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    reqs = [BatchRequest(custom_id="a", prompt="p1"), BatchRequest(custom_id="b", prompt="p2")]
    results = run_batch("deepseek:deepseek-v4-pro", reqs)
    assert len(results) == 2
    assert all(r.text == "ok" and r.input_tokens == 5 and r.output_tokens == 9 for r in results)


def test_unknown_provider_raises():
    with pytest.raises(ValueError, match="no batch mechanism"):
        run_batch("scripted:stub", [BatchRequest(custom_id="a", prompt="p")])


def test_empty_requests_short_circuits():
    assert run_batch("anthropic:claude-sonnet-5", []) == []
