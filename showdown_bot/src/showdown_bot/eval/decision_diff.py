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
from showdown_bot.eval.pairing import pair_runs
from showdown_bot.eval.stats import exact_binom_two_sided_p, mcnemar_counts, wilson_interval


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


# ---------------------------------------------------------------------------
# Task 7: aggregate paired outcomes, matchup buckets, regressions, stability.
# ---------------------------------------------------------------------------

def outcome_category(baseline_row: dict, candidate_row: dict) -> str:
    b, c = baseline_row["winner"], candidate_row["winner"]
    if b not in ("hero", "villain") or c not in ("hero", "villain"):
        return "NON_BINARY"
    if b == "hero" and c == "hero":
        return "BOTH_WIN"
    if b == "villain" and c == "villain":
        return "BOTH_LOSS"
    return "CANDIDATE_FLIP_TO_WIN" if c == "hero" else "CANDIDATE_REGRESSION_TO_LOSS"


def paired_strength_summary(pairs) -> dict:
    counts = mcnemar_counts((pair.hero_win_a, pair.hero_win_b) for pair in pairs)
    return {
        "orientation": "A=baseline,B=candidate",
        "n11": counts.n11, "n00": counts.n00,
        "n10_baseline_only_win": counts.n10,
        "n01_candidate_only_win": counts.n01,
        "n_discordant": counts.n_discordant,
        "candidate_minus_baseline_winrate": -counts.delta,
        "exact_two_sided_p": exact_binom_two_sided_p(counts.n01, counts.n_discordant),
    }


def _lead(row: dict, side: str) -> str:
    slots = row.get("state_summary", {}).get("sides", {}).get(side, {})
    species = [slots.get(slot, {}).get("species") for slot in ("a", "b")]
    return "+".join(species) if all(species) else "unavailable"


def build_matchup_buckets(records: list[dict], *, archetype_by_hash: dict[str, str]) -> list[dict]:
    grouped = {}
    for record in records:
        baseline = record["baseline_row"]
        candidate = record["candidate_row"]
        key = (
            archetype_by_hash.get(baseline.get("hero_team_hash"), "unclassified"),
            archetype_by_hash.get(baseline.get("opp_team_hash"), "unclassified"),
            baseline["opp_policy"], record.get("lead", "unavailable"),
        )
        grouped.setdefault(key, []).append(record)
    buckets = []
    for (hero_arch, opp_arch, policy, lead), rows in sorted(grouped.items()):
        n = len(rows)
        bw = sum(row["baseline_row"]["winner"] == "hero" for row in rows)
        cw = sum(row["candidate_row"]["winner"] == "hero" for row in rows)
        blo, bhi = wilson_interval(bw, n)
        clo, chi = wilson_interval(cw, n)
        buckets.append({
            "hero_archetype": hero_arch, "opponent_archetype": opp_arch,
            "opponent_policy": policy, "lead": lead, "n": n,
            "baseline_wins": bw, "candidate_wins": cw,
            "baseline_win_rate": bw / n, "candidate_win_rate": cw / n,
            "baseline_wilson_lo": blo, "baseline_wilson_hi": bhi,
            "candidate_wilson_lo": clo, "candidate_wilson_hi": chi,
            "positive_flips": sum(outcome_category(row["baseline_row"], row["candidate_row"])
                                  == "CANDIDATE_FLIP_TO_WIN" for row in rows),
            "negative_flips": sum(outcome_category(row["baseline_row"], row["candidate_row"])
                                  == "CANDIDATE_REGRESSION_TO_LOSS" for row in rows),
            "underpowered": n < 10,
        })
    return buckets


def analyze_decision_diff(baseline_bundle, candidate_bundle, *, panel,
                          baseline_trace: ValidatedTraceRun | None,
                          candidate_trace: ValidatedTraceRun | None,
                          outcome_only: bool,
                          baseline_repeat: list[dict] | None = None,
                          candidate_repeat: list[dict] | None = None) -> dict:
    pairs = pair_runs(baseline_bundle.rows, candidate_bundle.rows,
                      expected_rows=baseline_bundle.schedule_row_count)
    comparisons = []
    if not outcome_only:
        if baseline_trace is None or candidate_trace is None:
            raise DecisionDiffError("full mode requires validated traces")
        for pair in pairs:
            comparisons.append(compare_battle_decisions(
                pair.battle_id,
                baseline_trace.rows_by_battle[pair.battle_id],
                candidate_trace.rows_by_battle[pair.battle_id],
            ))
    archetype_by_hash = {
        team.team_hash: team.archetype
        for team in (*panel.dev_teams, *panel.heldout_teams)
    }
    records = build_battle_records(pairs, comparisons, baseline_trace)
    return {
        "capability_mode": "outcome_only" if outcome_only else "full",
        "provenance": {"baseline": baseline_bundle.manifest,
                       "candidate": candidate_bundle.manifest},
        "integrity": integrity_summary(pairs, comparisons),
        "strength": paired_strength_summary(pairs),
        "outcomes": outcome_counts(records),
        "decision_differences": None if outcome_only else decision_summary(comparisons),
        "matchup_buckets": build_matchup_buckets(records, archetype_by_hash=archetype_by_hash),
        "stability": build_stability_block(
            baseline_trace, candidate_trace, baseline_repeat, candidate_repeat),
        "regressions": build_regressions(records, baseline_bundle, candidate_bundle),
        "top_positive_associations": rank_associations(records, positive=True),
        "top_negative_associations": rank_associations(records, positive=False),
    }


def build_battle_records(pairs, comparisons, baseline_trace) -> list[dict]:
    by_battle = {item.battle_id: item for item in comparisons}
    records = []
    for pair in pairs:
        diff = by_battle.get(pair.battle_id)
        lead = "unavailable"
        if baseline_trace is not None:
            regular = next((row for row in baseline_trace.rows_by_battle[pair.battle_id]
                            if row["decision_phase"] == "regular_turn"), None)
            if regular is not None:
                lead = _lead(regular, regular["our_side"])
        records.append({
            "battle_id": pair.battle_id, "baseline_row": pair.row_a,
            "candidate_row": pair.row_b, "first_divergence": None if diff is None else diff.first_divergence,
            "decision_diff": diff, "lead": lead,
            "outcome_category": outcome_category(pair.row_a, pair.row_b),
        })
    return records


def integrity_summary(pairs, comparisons) -> dict:
    return {
        "paired_battles": len(pairs),
        "battles_with_decision_comparison": len(comparisons),
        "directly_comparable_decisions": sum(item.comparable for item in comparisons),
        "direct_agreements": sum(item.agreements for item in comparisons),
        "direct_divergences": sum(len(item.direct_divergences) for item in comparisons),
        "battles_with_state_divergence": sum(item.state_divergence_index is not None
                                             for item in comparisons),
    }


def outcome_counts(records) -> dict:
    names = ("BOTH_WIN", "BOTH_LOSS", "CANDIDATE_FLIP_TO_WIN",
             "CANDIDATE_REGRESSION_TO_LOSS", "NON_BINARY")
    return {name: sum(row["outcome_category"] == name for row in records) for name in names}


def decision_summary(comparisons) -> dict:
    classes = {}
    for comparison in comparisons:
        for item in comparison.direct_divergences:
            classes[item["primary"]] = classes.get(item["primary"], 0) + 1
    return {
        "comparable": sum(item.comparable for item in comparisons),
        "agreements": sum(item.agreements for item in comparisons),
        "divergences": sum(len(item.direct_divergences) for item in comparisons),
        "by_primary_class": dict(sorted(classes.items())),
    }


def build_stability_block(baseline_trace, candidate_trace, baseline_repeat, candidate_repeat) -> dict:
    return {
        "baseline": {"status": "not_provided"} if baseline_repeat is None else
                    compare_repeat_identity(flatten(baseline_trace), baseline_repeat),
        "candidate": {"status": "not_provided"} if candidate_repeat is None else
                     compare_repeat_identity(flatten(candidate_trace), candidate_repeat),
    }


def build_regressions(records, baseline_bundle, candidate_bundle) -> dict:
    return {
        "candidate_regression_to_loss": sum(
            row["outcome_category"] == "CANDIDATE_REGRESSION_TO_LOSS" for row in records),
        "candidate_only_fallbacks": sum(
            row["decision_diff"] is not None and
            any(item["primary"] == "FALLBACK" for item in row["decision_diff"].direct_divergences)
            for row in records),
        "candidate_only_timeouts": sum(
            bool(row["candidate_row"].get("timeouts")) and not bool(row["baseline_row"].get("timeouts"))
            for row in records),
        "candidate_only_crashes": sum(
            row["candidate_row"].get("crashes", 0) > row["baseline_row"].get("crashes", 0)
            for row in records),
        "latency_budget_regressions": sum(
            row["candidate_row"]["decision_latency_p95_ms"] > candidate_bundle.latency_budget_ms
            and row["baseline_row"]["decision_latency_p95_ms"] <= baseline_bundle.latency_budget_ms
            for row in records),
    }


def rank_associations(records, *, positive: bool) -> list[dict]:
    wanted = "CANDIDATE_FLIP_TO_WIN" if positive else "CANDIDATE_REGRESSION_TO_LOSS"
    counts = {}
    for row in records:
        first = row["first_divergence"]
        if row["outcome_category"] == wanted and first is not None:
            key = first["primary"]
            counts[key] = counts.get(key, 0) + 1
    return [
        {"primary": primary, "associated_battles": count}
        for primary, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def flatten(run: ValidatedTraceRun | None) -> list[dict]:
    if run is None:
        raise DecisionDiffError("repeat comparison requires the original validated trace run")
    return [
        row for battle_id in sorted(run.rows_by_battle)
        for row in run.rows_by_battle[battle_id]
    ]


VOLATILE_TRACE_FIELDS = frozenset({"decision_latency_ms"})


def _identity_row(row: dict) -> dict:
    return {key: value for key, value in row.items() if key not in VOLATILE_TRACE_FIELDS}


def compare_repeat_identity(original: list[dict], repeat: list[dict]) -> dict:
    for field in ("trace_schema_version", "config_hash", "schedule_hash", "git_sha"):
        left_values = {row[field] for row in original}
        right_values = {row[field] for row in repeat}
        if len(left_values) != 1 or left_values != right_values:
            raise DecisionDiffError(f"repeat {field} mismatch")
    left = [_identity_row(row) for row in sorted(original, key=lambda r: (r["seed_index"], r["decision_index"]))]
    right = [_identity_row(row) for row in sorted(repeat, key=lambda r: (r["seed_index"], r["decision_index"]))]
    diffs = []
    for index in range(max(len(left), len(right))):
        a = left[index] if index < len(left) else None
        b = right[index] if index < len(right) else None
        if a != b:
            diffs.append({"index": index, "baseline": a, "repeat": b})
    return {"identical": not diffs, "n_compared": min(len(left), len(right)), "diffs": diffs}
