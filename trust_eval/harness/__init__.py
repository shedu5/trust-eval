"""The judge harness: build cases, render attack-blind prompts, call a judge
(with caching), and record verdicts. Scoring lives in :mod:`trust_eval.scorer`."""

from .suite import Case, build_suite, GroundTruth
from .prompt import PROMPT_VERSION, render_judge_prompt, parse_verdict, Verdict

__all__ = [
    "Case",
    "build_suite",
    "GroundTruth",
    "PROMPT_VERSION",
    "render_judge_prompt",
    "parse_verdict",
    "Verdict",
]
