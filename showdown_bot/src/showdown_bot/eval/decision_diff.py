"""Bind decision-trace sidecar rows to result rows and fail closed on any
mismatch between the two.

This is an offline module: it does not touch the live battle path. It exists
so downstream candidate-vs-baseline diff tooling can trust that a sidecar
trace file actually corresponds to the result rows it claims to bind to
(same battle, same decision count, same content) before drawing any
conclusions from it.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

from showdown_bot.eval.decision_capture import TRACE_SCHEMA_VERSION


class DecisionDiffError(ValueError):
    pass


@dataclass(frozen=True)
class ValidatedTraceRun:
    config_hash: str
    schedule_hash: str
    rows_by_battle: dict[str, tuple[dict, ...]]


def _trace_line(row: dict) -> bytes:
    return (json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def validate_trace_run(result_rows: list[dict], trace_rows: list[dict]) -> ValidatedTraceRun:
    by_result = {row["battle_id"]: row for row in result_rows}
    if len(by_result) != len(result_rows):
        raise DecisionDiffError("duplicate result battle_id")
    grouped = {}
    for row in trace_rows:
        if row["trace_schema_version"] != TRACE_SCHEMA_VERSION:
            raise DecisionDiffError("unknown trace schema version")
        battle_id = row["battle_id"]
        if battle_id not in by_result:
            raise DecisionDiffError(f"trace battle absent from results: {battle_id}")
        result = by_result[battle_id]
        for field in ("seed_index", "config_hash", "schedule_hash", "format_id", "git_sha"):
            if row[field] != result[field]:
                raise DecisionDiffError(f"{battle_id}: {field} mismatch")
        grouped.setdefault(battle_id, []).append(row)
    for battle_id, result in by_result.items():
        expected_count = result.get("decision_trace_count")
        expected_sha = result.get("decision_trace_sha256")
        if expected_count is None or expected_sha is None:
            raise DecisionDiffError(f"{battle_id}: missing decision trace binding")
        rows = sorted(grouped.get(battle_id, []), key=lambda row: row["decision_index"])
        indices = [row["decision_index"] for row in rows]
        if indices != list(range(len(rows))):
            raise DecisionDiffError(f"{battle_id}: non-contiguous or duplicate decision key")
        if len(rows) != expected_count:
            raise DecisionDiffError(f"{battle_id}: count mismatch")
        actual_sha = hashlib.sha256(b"".join(_trace_line(row) for row in rows)).hexdigest()
        if actual_sha != expected_sha:
            raise DecisionDiffError(f"{battle_id}: sha mismatch")
        grouped[battle_id] = tuple(rows)
    config_hashes = {row["config_hash"] for row in result_rows}
    schedule_hashes = {row["schedule_hash"] for row in result_rows}
    if len(config_hashes) != 1 or len(schedule_hashes) != 1:
        raise DecisionDiffError("run provenance is not constant")
    return ValidatedTraceRun(
        config_hash=next(iter(config_hashes)), schedule_hash=next(iter(schedule_hashes)),
        rows_by_battle={key: grouped[key] for key in sorted(grouped)},
    )


@dataclass(frozen=True)
class ActionDiff:
    primary: str
    markers: tuple[str, ...]


@dataclass(frozen=True)
class BattleDecisionDiff:
    battle_id: str
    comparable: int
    agreements: int
    direct_divergences: tuple[dict, ...]
    first_divergence: dict | None
    state_divergence_index: int | None
    baseline_suffix_count: int
    candidate_suffix_count: int


def classify_action_diff(baseline: dict, candidate: dict,
                         *, baseline_stage: str | None = None,
                         candidate_stage: str | None = None) -> ActionDiff:
    markers = []
    if baseline_stage != candidate_stage and (
        "fallback" in (baseline_stage or "") or "fallback" in (candidate_stage or "")
        or "default" in (baseline_stage or "") or "default" in (candidate_stage or "")
    ):
        return ActionDiff("FALLBACK", ("selection_stage_changed",))
    bslots = baseline.get("slots", [])
    cslots = candidate.get("slots", [])
    for marker, predicate in (
        ("tera_changed", lambda b, c: b.get("kind") == c.get("kind") == "move" and b.get("tera") != c.get("tera")),
        ("switch_changed", lambda b, c: b.get("switch_target") != c.get("switch_target") or b.get("kind") != c.get("kind")),
        ("protect_changed", lambda b, c: b.get("kind") == c.get("kind") == "move" and b.get("is_protect") != c.get("is_protect")),
        ("move_changed", lambda b, c: b.get("kind") == c.get("kind") == "move" and b.get("move_id") != c.get("move_id")),
        ("target_changed", lambda b, c: b.get("kind") == c.get("kind") == "move" and b.get("target") != c.get("target")),
    ):
        if any(predicate(b, c) for b, c in zip(bslots, cslots)):
            markers.append(marker)
    for marker, primary in (
        ("tera_changed", "TERA"),
        ("switch_changed", "SWITCH"),
        ("protect_changed", "PROTECT"),
        ("move_changed", "ATTACK_MOVE"),
        ("target_changed", "ATTACK_TARGET"),
    ):
        if marker in markers:
            return ActionDiff(primary, tuple(markers))
    return ActionDiff("OTHER_ACTION", tuple(markers))


def compare_battle_decisions(pair: str, baseline_rows: tuple[dict, ...],
                             candidate_rows: tuple[dict, ...]) -> BattleDecisionDiff:
    battle_id = pair
    comparable = 0
    agreements = 0
    divergences: list[dict] = []
    first_direct_divergence: dict | None = None
    state_divergence_index: int | None = None
    length = max(len(baseline_rows), len(candidate_rows))
    for index in range(length):
        baseline = baseline_rows[index] if index < len(baseline_rows) else None
        candidate = candidate_rows[index] if index < len(candidate_rows) else None
        one_side_missing = baseline is None or candidate is None
        if one_side_missing:
            if first_direct_divergence is None:
                raise DecisionDiffError(f"{battle_id}: decision key missing before divergence")
            return BattleDecisionDiff(
                battle_id=battle_id, comparable=comparable, agreements=agreements,
                direct_divergences=tuple(divergences), first_divergence=first_direct_divergence,
                state_divergence_index=state_divergence_index,
                baseline_suffix_count=len(baseline_rows) - index,
                candidate_suffix_count=len(candidate_rows) - index,
            )
        if baseline["observable_state_hash"] != candidate["observable_state_hash"]:
            state_divergence_index = index
            return BattleDecisionDiff(
                battle_id=battle_id, comparable=comparable, agreements=agreements,
                direct_divergences=tuple(divergences), first_divergence=first_direct_divergence,
                state_divergence_index=state_divergence_index,
                baseline_suffix_count=len(baseline_rows) - index,
                candidate_suffix_count=len(candidate_rows) - index,
            )
        comparable += 1
        if baseline["normalized_action"] == candidate["normalized_action"]:
            markers = ("score_rank_changed",) if baseline.get("chosen_rank") != candidate.get("chosen_rank") else ()
            agreements += 1
        else:
            diff = classify_action_diff(
                baseline["normalized_action"], candidate["normalized_action"],
                baseline_stage=baseline.get("selection_stage"),
                candidate_stage=candidate.get("selection_stage"),
            )
            direct = {"decision_index": index, "turn_number": baseline["turn_number"],
                      "decision_phase": baseline["decision_phase"], "primary": diff.primary,
                      "markers": list(diff.markers)}
            divergences.append(direct)
            first_direct_divergence = first_direct_divergence or direct
    return BattleDecisionDiff(
        battle_id=battle_id, comparable=comparable, agreements=agreements,
        direct_divergences=tuple(divergences), first_divergence=first_direct_divergence,
        state_divergence_index=state_divergence_index,
        baseline_suffix_count=0, candidate_suffix_count=0,
    )
