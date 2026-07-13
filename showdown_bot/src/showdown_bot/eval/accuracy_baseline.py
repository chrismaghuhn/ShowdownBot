"""Freeze a pre-refactor baseline of chosen actions/scores over the deduplicated corpus,
in SHOWDOWN_ACCURACY_MODE=off, BEFORE the LineEvaluation/_evaluate_line_details refactor lands.

This artifact is a hard checkpoint (spec Sec.7): once committed, never regenerated. A later
diff against it is the true refactor-regression check -- unset-vs-explicit-off alone cannot
catch a bug in a wrapper that both paths route through post-refactor.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from showdown_bot.eval.room_raw_replay import ExtractedDecision


def canonical_float(value: float, *, ndigits: int = 10) -> str:
    """Fixed serialization so a harmless formatting/precision difference can never be
    misread as a scoring regression when diffing against this frozen baseline."""
    return f"{round(value, ndigits):.{ndigits}f}"


@dataclass(frozen=True)
class BaselineRow:
    request_hash: str
    log_prefix_hash: str
    side: str
    turn: int
    chosen_action: str
    score: str  # canonical_float output
    accuracy_mode: bool
    source_commit: str
    config_hash: str
    python_version: str
    dependency_lock_hash: str


ChooserFn = Callable[[ExtractedDecision], tuple[str, float]]


def freeze_baseline(
    decisions: Sequence[ExtractedDecision],
    *,
    out_path: str | Path,
    chooser: Callable[[ExtractedDecision], tuple[str, float]] | Callable[..., tuple[str, float]],
    source_commit: str,
    config_hash: str,
    python_version: str,
    dependency_lock_hash: str,
) -> list[BaselineRow]:
    rows: list[BaselineRow] = []
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        for decision in decisions:
            chosen_action, score = chooser(decision, accuracy_mode=False)
            row = BaselineRow(
                request_hash=decision.request_hash,
                log_prefix_hash=decision.log_prefix_hash,
                side=decision.side,
                turn=decision.turn,
                chosen_action=chosen_action,
                score=canonical_float(score),
                accuracy_mode=False,
                source_commit=source_commit,
                config_hash=config_hash,
                python_version=python_version,
                dependency_lock_hash=dependency_lock_hash,
            )
            rows.append(row)
            fh.write(json.dumps(asdict(row), sort_keys=True) + "\n")
    return rows
