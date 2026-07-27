"""Tests for cost_probe.py's `report` aggregation -- the code path that
reads Phase 0's measured numbers back from the cache. Built against a
temp cache directory with synthetic usage-annotated records, since this
sandbox cannot produce real ones (no key, no network to any judge
provider -- see docs/full-technical-report.md's Phase 0 section). `run` itself (which fills
the cache live) is intentionally NOT exercised here beyond argument
wiring -- it needs a real key and is meant to run on the user's machine.
"""

import json

import pytest

from trust_eval.harness.cache import cache_key
from trust_eval.study_c import cost_probe


def _write_record(cache_dir, provider, model, prompt_version, prompt, usage):
    key = cache_key(provider, model, prompt_version, prompt)
    record = {"provider": provider, "model": model, "prompt_version": prompt_version,
             "verdict": "accept", "reason": "x", "raw": '{"verdict":"accept","reason":"x"}',
             "evaluated_at": "2026-07-24T00:00:00+00:00", "usage": usage}
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / f"{key}.json").write_text(json.dumps(record))


def test_report_aggregates_exact_totals_across_surfaces(tmp_path, monkeypatch, capsys):
    cache_dir = tmp_path / "records"
    _write_record(cache_dir, "deepseek", "deepseek-v4-pro", "trust-eval/study-c/p1-review/v1",
                  "prompt-1", {"input_tokens": 100, "output_tokens": 400, "reasoning_tokens": 350,
                              "cache_hit_input_tokens": 20})
    _write_record(cache_dir, "deepseek", "deepseek-v4-pro", "trust-eval/study-c/p1-review/v2",
                  "prompt-2", {"input_tokens": 150, "output_tokens": 500, "reasoning_tokens": 420,
                              "cache_hit_input_tokens": 0})
    # A different model's record must NOT be counted in the deepseek-v4-pro totals.
    _write_record(cache_dir, "deepseek", "deepseek-v4-flash", "trust-eval/study-c/p1-review/v1",
                  "prompt-3", {"input_tokens": 9999, "output_tokens": 9999})

    monkeypatch.setattr(cost_probe, "DEFAULT_CACHE_DIR", cache_dir)
    rc = cost_probe.report(["--provider-model", "deepseek:deepseek-v4-pro"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "judge calls made:            2" in out
    assert "250" in out       # total input tokens (100+150)
    assert "900" in out       # total output tokens (400+500)
    assert "770" in out       # total reasoning tokens (350+420)
    assert "9999" not in out  # the flash record must not leak into pro's totals
    assert "STANDARD SYNCHRONOUS rate" in out   # no confirmed DeepSeek batch discount
    assert "PROJECTED COST TABLE" in out
    assert "gemini-3.1-pro-preview" in out
    assert "full 4-judge panel" in out
    # Claude and GPT-5.6 were dropped from the panel after this probe --
    # confirms the projection doesn't silently keep projecting for them.
    assert "gpt-5.6-sol" not in out
    assert "claude-sonnet-5" not in out


def test_report_with_no_records_fails_clearly(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cost_probe, "DEFAULT_CACHE_DIR", tmp_path / "empty")
    (tmp_path / "empty").mkdir()
    rc = cost_probe.report(["--provider-model", "deepseek:deepseek-v4-pro"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "No cache records found" in out


def test_run_dispatches_via_main_subcommand(monkeypatch):
    # Confirms the "run"/"report" subcommand split itself, without touching
    # any surface's real main() (that would need a live key) -- patch every
    # surface module's main to a no-op recorder and check they're all called.
    called = []
    for name in ("ladder", "p4p5_probe", "adaptive", "extended_attacks",
                 "coordination_probe", "skeleton_probe"):
        mod = getattr(cost_probe, name)
        monkeypatch.setattr(mod, "main", lambda argv, _n=name: (called.append(_n) or 0))
    rc = cost_probe.main(["run"])
    assert rc == 0
    for name in ("ladder", "p4p5_probe", "adaptive", "extended_attacks",
                 "coordination_probe", "skeleton_probe"):
        assert name in called


def test_main_requires_a_subcommand():
    with pytest.raises(SystemExit):
        cost_probe.main([])


def test_run_defaults_to_phase0_provider(monkeypatch):
    seen = []
    monkeypatch.setattr(cost_probe.ladder, "main", lambda argv: (seen.append(argv) or 0))
    for name in ("p4p5_probe", "adaptive", "extended_attacks", "coordination_probe", "skeleton_probe"):
        monkeypatch.setattr(getattr(cost_probe, name), "main", lambda argv: 0)
    cost_probe.run([])
    assert cost_probe.PHASE0_PROVIDER in seen[0]


def test_run_isolates_to_the_given_provider_only(monkeypatch):
    # A --provider run must touch ONLY that provider:model on every surface --
    # never PHASE0_PROVIDER, never any other FULL_PANEL member -- so results
    # stay exactly attributable to the single judge requested. Uses
    # gemini-2.5-pro deliberately (a real, priced, but currently NOT-in-panel
    # model) so this also covers isolating to a non-panel provider correctly.
    seen = []
    for name in ("ladder", "p4p5_probe", "adaptive", "extended_attacks",
                 "coordination_probe", "skeleton_probe"):
        mod = getattr(cost_probe, name)
        monkeypatch.setattr(mod, "main", lambda argv: (seen.append(argv) or 0))
    cost_probe.run(["--provider", "gemini:gemini-2.5-pro"])
    for argv in seen:
        assert "gemini:gemini-2.5-pro" in argv
        assert cost_probe.PHASE0_PROVIDER not in argv
        for other in cost_probe.FULL_PANEL:
            assert other not in argv
