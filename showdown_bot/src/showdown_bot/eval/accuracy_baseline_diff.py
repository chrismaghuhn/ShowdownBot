"""Diff a post-refactor replay of the deduplicated corpus (accuracy off) against the frozen
pre-refactor baseline (Task 4). This is the true refactor-regression check -- unset-vs-explicit-off
alone cannot catch a bug in a wrapper both paths route through after the LineEvaluation refactor."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Regression:
    request_hash: str
    baseline_action: str
    replay_action: str
    baseline_score: str
    replay_score: str


@dataclass(frozen=True)
class BaselineDiffResult:
    matched: int
    regressions: list[Regression]
    missing_from_replay: list[str]
    extra_in_replay: list[str]


def diff_against_baseline(baseline_rows: list[dict], replay_rows: list[dict]) -> BaselineDiffResult:
    baseline_by_hash = {r["request_hash"]: r for r in baseline_rows}
    replay_by_hash = {r["request_hash"]: r for r in replay_rows}

    matched = 0
    regressions: list[Regression] = []
    for req_hash, brow in baseline_by_hash.items():
        rrow = replay_by_hash.get(req_hash)
        if rrow is None:
            continue
        matched += 1
        if brow["chosen_action"] != rrow["chosen_action"] or brow["score"] != rrow["score"]:
            regressions.append(Regression(
                request_hash=req_hash,
                baseline_action=brow["chosen_action"], replay_action=rrow["chosen_action"],
                baseline_score=brow["score"], replay_score=rrow["score"],
            ))

    missing_from_replay = sorted(set(baseline_by_hash) - set(replay_by_hash))
    extra_in_replay = sorted(set(replay_by_hash) - set(baseline_by_hash))

    return BaselineDiffResult(
        matched=matched, regressions=regressions,
        missing_from_replay=missing_from_replay, extra_in_replay=extra_in_replay,
    )
