"""Map a populated DecisionTrace to schema Rows (Phase 3 slice 1b-B1).

Group-3 (eval) reads ONLY from the trace; G1/G2/G4 are deterministic reads of
state/request/dex/move_meta/speed_oracle/context. No Node/calc. This file is the
SCAFFOLD: every feature is a sentinel stub; later tasks fill real values.
"""
from __future__ import annotations

from dataclasses import dataclass

from showdown_bot.learning.schema import (
    FEATURE_COLUMNS,
    CONTEXT_FEATURES,
    ACTION_FEATURES,
    HEURISTIC_FEATURES,
    TEMPO_FEATURES,
    METADATA_KEYS,
    LABEL_KEYS,
    Row,
)

# ---------------------------------------------------------------------------
# Central sentinel constants (frozen — Tasks 2–4 read these, never redefine)
# ---------------------------------------------------------------------------
SENTINEL_CAT_NONE = "__none__"          # not applicable (e.g. move field on a switch)
SENTINEL_CAT_UNKNOWN = "__unknown__"    # applicable but not revealed (e.g. opp species)
SENTINEL_CAT_UNTRACKED = "__untracked__"  # state does not model it (screens)
SENTINEL_NUM = -1                        # optional numeric slot/target
SENTINEL_BOOL = False                    # optional bool

# Re-export CONTEXT_FEATURES as CONTEXT_COLUMNS (the per-decision-identical group)
CONTEXT_COLUMNS = list(CONTEXT_FEATURES)

# ---------------------------------------------------------------------------
# Columns bucketed by value type — used only by _stub_features().
# These sets partition FEATURE_COLUMNS exactly.
# ---------------------------------------------------------------------------

# Integer counts / slots (non-negative integers, 0 as stub)
_INT_COLS = frozenset({
    "turn_number",
    "our_alive_count", "opp_alive_count",
    "slot1_target_slot", "slot2_target_slot",  # SENTINEL_NUM = -1, overridden below
    "slot1_priority", "slot2_priority",
    "predicted_kos_for", "predicted_kos_against",
    "ko_secured_count", "ko_threatened_count", "survives_for_sure_count",
    "we_outspeed_count", "they_outspeed_count", "speed_tie_count",
    "our_fastest_active_speed", "opp_fastest_active_speed",
    "must_react_reason_flags",
    "response_count",
})

# Integer sentinel = SENTINEL_NUM (-1) for "optional slot" columns
_INT_SENTINEL_NUM_COLS = frozenset({
    "slot1_target_slot", "slot2_target_slot",
})

# Float scores / fractions / ratios (0.0 as stub)
_FLOAT_COLS = frozenset({
    "our_total_hp_frac", "opp_total_hp_frac",
    "heuristic_aggregate_score", "score_gap_to_top", "score_gap_to_second",
    "score_min_vs_opp", "score_mean_vs_opp", "score_var_vs_opp",
    "score_worst_response",
    "predicted_outgoing_damage", "predicted_incoming_damage", "out_in_ratio",
    "protect_stall_penalty", "partner_abandon_penalty",
    "fakeout_invalid_penalty", "action_economy_score",
    "protect_prior_target1", "protect_prior_target2",
    "opponent_response_entropy", "value_range_across_opp_responses",
})

# Boolean flags (False as stub)
_BOOL_COLS = frozenset({
    "endgame_flag",
    "tailwind_ours", "tailwind_opp", "trick_room_active",
    "mirror_flag",
    "slot1_is_damaging", "slot2_is_damaging",
    "slot1_is_protect", "slot2_is_protect",
    "slot1_is_switch", "slot2_is_switch",
    "tera_used",
})

# Categorical strings (SENTINEL_CAT_NONE as stub)
_CAT_COLS = frozenset(FEATURE_COLUMNS) - _INT_COLS - _FLOAT_COLS - _BOOL_COLS


def _stub_features() -> dict:
    """Every FEATURE_COLUMNS key -> a typed sentinel.

    Numeric/score columns -> 0/0.0, bool -> False, categorical -> SENTINEL_CAT_NONE.
    Tasks 2–4 overwrite these with real values without modifying this function.
    """
    f: dict = {}
    for c in FEATURE_COLUMNS:
        if c in _BOOL_COLS:
            f[c] = SENTINEL_BOOL
        elif c in _INT_SENTINEL_NUM_COLS:
            f[c] = SENTINEL_NUM
        elif c in _INT_COLS:
            f[c] = 0
        elif c in _FLOAT_COLS:
            f[c] = 0.0
        else:
            # categorical
            f[c] = SENTINEL_CAT_NONE
    return f


# Verify at import time that the bucket sets cover FEATURE_COLUMNS exactly.
# This makes a misconfiguration an ImportError rather than a silent test failure.
_ALL_BUCKETED = _INT_COLS | _FLOAT_COLS | _BOOL_COLS | _CAT_COLS
assert _ALL_BUCKETED == frozenset(FEATURE_COLUMNS), (
    f"Bucket mismatch — extra: {_ALL_BUCKETED - frozenset(FEATURE_COLUMNS)}, "
    f"missing: {frozenset(FEATURE_COLUMNS) - _ALL_BUCKETED}"
)


# ---------------------------------------------------------------------------
# Group-1 helpers
# ---------------------------------------------------------------------------

def _opp_side(our_side: str) -> str:
    return "p2" if our_side == "p1" else "p1"


def _active_living(state, side: str) -> list:
    """Return PokemonState objects in slots 'a'/'b' that are not fainted."""
    return [
        m for s, m in state.side(side).items()
        if s in ("a", "b") and m is not None and not m.fainted
    ]


def _speed_control_state(field, our_side: str, opp: str) -> str:
    o = bool(field.tailwind.get(our_side, False))
    p = bool(field.tailwind.get(opp, False))
    tr = bool(field.trick_room)
    if tr and (o or p):
        return "mixed"
    if tr:
        return "trick_room"
    if o and p:
        return "tailwind_both"
    if o:
        return "tailwind_ours"
    if p:
        return "tailwind_opp"
    return "none"


def _group1_context(state, request, trace, ctx: "FeatureContext") -> dict:
    our_side = ctx.our_side
    opp = _opp_side(our_side)
    field = state.field
    our_alive = sum(
        1 for p in request.side.pokemon
        if "fnt" not in (p.condition or "")
    )
    opp_faints = sum(
        1 for m in state.side(opp).values()
        if getattr(m, "fainted", False)
    )
    opp_alive = max(0, 4 - opp_faints)
    return {
        "game_mode": trace.game_mode if trace.game_mode is not None else SENTINEL_CAT_NONE,
        "turn_number": ctx.turn_number,
        "endgame_flag": our_alive <= 1,
        "our_alive_count": our_alive,
        "opp_alive_count": opp_alive,
        "our_total_hp_frac": sum(m.hp_fraction for m in _active_living(state, our_side)),
        "opp_total_hp_frac": sum(m.hp_fraction for m in _active_living(state, opp)),
        "field_weather": field.weather or SENTINEL_CAT_NONE,
        "field_terrain": field.terrain or SENTINEL_CAT_NONE,
        "tailwind_ours": bool(field.tailwind.get(our_side, False)),
        "tailwind_opp": bool(field.tailwind.get(opp, False)),
        "trick_room_active": bool(field.trick_room),
        "screens_ours": SENTINEL_CAT_UNTRACKED,
        "screens_opp": SENTINEL_CAT_UNTRACKED,
        "speed_control_state": _speed_control_state(field, our_side, opp),
        "format_id": ctx.format_id,
        "mirror_flag": ctx.mirror_flag,
    }


# ---------------------------------------------------------------------------
# FeatureContext DTO
# ---------------------------------------------------------------------------

@dataclass
class FeatureContext:
    run_id: str
    game_id: str
    decision_id: str
    decision_local_index: int
    turn_number: int
    our_side: str
    format_id: str
    team_hash: str
    config_hash: str
    git_sha: str
    dirty_flag: bool
    teacher_config: dict
    sampling_policy: str
    mirror_flag: bool
    # Optional read-only tools (not used by the scaffold; Tasks 2–4 consume these)
    dex: object | None = None
    move_meta: object | None = None
    speed_oracle: object | None = None
    protect_priors_by_opp_slot: dict | None = None  # {"a": p, "b": p} normalized flat dict


# ---------------------------------------------------------------------------
# Metadata / label builders
# ---------------------------------------------------------------------------

def _metadata(ctx: FeatureContext, candidate_index: int) -> dict:
    """Build a metadata dict with exactly METADATA_KEYS — no more, no less."""
    return {
        "game_id": ctx.game_id,
        "decision_id": ctx.decision_id,
        "candidate_index": candidate_index,
        "format_id": ctx.format_id,
        "game_outcome": "__pending__",
        "final_turn": -1,
        "winner": "__pending__",
        "teacher_trace": "",
        "schema_version": "1",
        "feature_extractor_version": "1b-B1",
        "teacher_version": "stub-h0",
        "git_sha": ctx.git_sha,
        "team_hash": ctx.team_hash,
        "config_hash": ctx.config_hash,
        "teacher_config": ctx.teacher_config,
    }


def _stub_label() -> dict:
    """Build a label dict with exactly LABEL_KEYS — all zeroed stubs."""
    return {k: 0 for k in LABEL_KEYS}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_features(trace, state, request, context: FeatureContext) -> list[Row]:
    """Return one schema-valid Row per candidate in trace.candidates.

    This scaffold sets every feature to its typed sentinel; later tasks replace
    stubs with real values group by group, without breaking these gates.
    """
    g1 = _group1_context(state, request, trace, context)
    rows = []
    for i, cand in enumerate(trace.candidates):
        features = _stub_features()
        features.update(g1)
        rows.append(
            Row(
                features=features,
                metadata=_metadata(context, i),
                label=_stub_label(),
            )
        )
    return rows
