"""Frozen training-data contract for the reranker (Phase 3, slice 1).

features = ONLY decision-time info. metadata = outcome/versioning/debug (never a
feature). label = counterfactual teacher value/ranks. One JSONL row per
(decision x candidate); group by metadata.decision_id / metadata.game_id.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

# --- feature columns, 4 frozen groups (decision-time info only) -------------
CONTEXT_FEATURES = [
    "game_mode", "turn_number", "endgame_flag", "our_alive_count", "opp_alive_count",
    "our_total_hp_frac", "opp_total_hp_frac", "field_weather", "field_terrain",
    "tailwind_ours", "tailwind_opp", "trick_room_active", "screens_ours",
    "screens_opp", "speed_control_state", "format_id", "mirror_flag",
]
ACTION_FEATURES = [
    "slot1_action_type", "slot2_action_type", "slot1_move_id", "slot2_move_id",
    "slot1_move_type", "slot2_move_type", "slot1_move_category", "slot2_move_category",
    "slot1_target_kind", "slot2_target_kind", "slot1_target_slot", "slot2_target_slot",
    "slot1_priority", "slot2_priority", "slot1_is_damaging", "slot2_is_damaging",
    "slot1_is_protect", "slot2_is_protect", "slot1_is_switch", "slot2_is_switch",
    "tera_used", "slot1_actor_species_id", "slot2_actor_species_id",
    "slot1_switch_target_species_id", "slot2_switch_target_species_id",
    "slot1_target_species_id_if_known", "slot2_target_species_id_if_known",
]
HEURISTIC_FEATURES = [
    # NB: the heuristic's *rank* is a LABEL (heuristic_rank, for teacher-vs-heuristic
    # disagreement); the heuristic's *scores/gaps* below are the model features.
    "heuristic_aggregate_score", "score_gap_to_top",
    "score_gap_to_second", "score_min_vs_opp", "score_mean_vs_opp",
    "score_var_vs_opp", "score_worst_response", "predicted_outgoing_damage",
    "predicted_incoming_damage", "out_in_ratio", "predicted_kos_for",
    "predicted_kos_against", "ko_secured_count", "ko_threatened_count",
    "survives_for_sure_count", "protect_stall_penalty", "partner_abandon_penalty",
    "fakeout_invalid_penalty", "action_economy_score",
]
TEMPO_FEATURES = [
    "we_outspeed_count", "they_outspeed_count", "speed_tie_count",
    "our_fastest_active_speed", "opp_fastest_active_speed", "must_react_reason_flags",
    "protect_prior_target1", "protect_prior_target2", "response_count",
    "opponent_response_entropy", "value_range_across_opp_responses",
]
FEATURE_COLUMNS = CONTEXT_FEATURES + ACTION_FEATURES + HEURISTIC_FEATURES + TEMPO_FEATURES

METADATA_KEYS = [
    "game_id", "decision_id", "candidate_index", "format_id", "game_outcome",
    "final_turn", "winner", "teacher_trace", "schema_version",
    "feature_extractor_version", "teacher_version", "git_sha", "team_hash",
    "config_hash", "teacher_config",
]
LABEL_KEYS = [
    "counterfactual_value_raw", "counterfactual_value_normalized_within_decision",
    "value_gap_to_best", "counterfactual_rank", "teacher_rank", "teacher_best",
    "chosen_by_current_heuristic", "heuristic_rank",
]

_FEATURE_SET = frozenset(FEATURE_COLUMNS)
_META_SET = frozenset(METADATA_KEYS)
_LABEL_SET = frozenset(LABEL_KEYS)
# format_id intentionally appears in BOTH features (model-relevant) and metadata
# (dataset-relevant); it is the only allowed feature/metadata overlap.


@dataclass(frozen=True)
class Row:
    features: dict
    metadata: dict
    label: dict = field(default_factory=dict)


def validate_row(row: Row) -> None:
    """Strict frozen-contract check: features / metadata / label must each be
    EXACTLY the declared key set (no missing, no unknown). Catches broken JSONL at
    write time instead of at training time."""
    for name, keys, allowed in (
        ("feature", set(row.features), _FEATURE_SET),
        ("metadata", set(row.metadata), _META_SET),
        ("label", set(row.label), _LABEL_SET),
    ):
        unknown = keys - allowed
        if unknown:
            raise ValueError(f"unknown {name} key(s): {sorted(unknown)}")
        missing = allowed - keys
        if missing:
            raise ValueError(f"missing {name} key(s): {sorted(missing)}")


def to_jsonl_line(row: Row) -> str:
    validate_row(row)  # never write a broken row
    return json.dumps(
        {"features": row.features, "metadata": row.metadata, "label": row.label},
        sort_keys=True, separators=(",", ":"),   # no default=str: non-JSON types must crash
    )


def from_jsonl_line(line: str) -> Row:
    d = json.loads(line)
    return Row(features=d["features"], metadata=d["metadata"], label=d.get("label", {}))
