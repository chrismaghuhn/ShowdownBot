"""Map a populated DecisionTrace to schema Rows (Phase 3 slice 1b-B1).

Group-3 (eval) reads ONLY from the trace; G1/G2/G4 are deterministic reads of
state/request/dex/move_meta/speed_oracle/context. No Node/calc. This file is the
SCAFFOLD: every feature is a sentinel stub; later tasks fill real values.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import pvariance

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
# Group-2: is_protect detection
#
# Canonical approach: move_id membership in the known protect-move set (primary),
# with "protect" in effect_classes as secondary fallback for any move the
# effect_classes overlay correctly annotates.
#
# NOTE: "protect" in move.flags means "this move is BLOCKABLE by Protect"
# (almost every attacking move has it), NOT that it IS a protect move.
# Checking flags for protect detection would produce massive false positives
# and is intentionally avoided here.
#
# engine/state.py has a private _PROTECT_MOVE_IDS frozenset but it lacks
# "craftyshield", "burningbulwark", and "silktrap" (newer Gen-9 moves).
# We define our own complete canonical set here rather than importing a private name.
# ---------------------------------------------------------------------------
_PROTECT_MOVES = frozenset({
    "protect", "detect",
    "wideguard", "quickguard", "craftyshield",
    "spikyshield", "kingsshield",
    "banefulbunker", "silktrap", "burningbulwark",
    "maxguard",
})


def _is_protect_move(move_id: str, meta: object) -> bool:
    """Return True if this move IS a protect-family move (not merely blockable by Protect).

    Two-path check:
    1. Membership in the hardcoded _PROTECT_MOVES set (primary — catches all
       Gen-9 protect variants including silktrap/burningbulwark/maxguard that
       the effect_classes overlay may not yet annotate).
    2. "protect" in meta.effect_classes (secondary — catches any future protect
       move the overlay curates before this set is updated).

    Never checks meta.flags: "protect" in flags means "blockable by Protect",
    which applies to almost every attacking and most status moves.
    """
    if move_id in _PROTECT_MOVES:
        return True
    ec = getattr(meta, "effect_classes", ()) or ()
    return "protect" in ec


# ---------------------------------------------------------------------------
# Group-2 helpers
# ---------------------------------------------------------------------------

def _target_kind(target: int | None) -> str:
    """Convert SlotAction.target int to a named category string."""
    if target is None:
        return SENTINEL_CAT_NONE
    if target in (1, 2):
        return "foe"
    if target == -1:
        return "ally"
    if target == -2:
        return "self"
    return SENTINEL_CAT_NONE


def _opp_active_species(state, opp_side: str, target: int | None) -> str | None:
    """Return the species of the opponent's active mon targeted by `target`, or None.

    target 1 -> opp slot 'a', target 2 -> opp slot 'b'.
    Returns None if the slot is empty or the mon's species is unknown.
    """
    if target not in (1, 2):
        return None
    slot_letter = "a" if target == 1 else "b"
    mon = state.side(opp_side).get(slot_letter)
    if mon is None or getattr(mon, "fainted", False):
        return None
    species = getattr(mon, "species", None)
    return species if species else None


def _bench_species_from_ident(request, target_ident: str | None) -> str | None:
    """Find the species of a bench Pokémon by its ident suffix.

    BattleRequest.side.pokemon[i].ident has the form "p1: Flutter Mane".
    SlotAction.target_ident stores only the suffix part: "Flutter Mane".
    Match by stripping the "SIDE: " prefix from the request idents.
    """
    if not target_ident:
        return None
    for pslot in request.side.pokemon:
        suffix = pslot.ident.split(": ", 1)[-1]
        if suffix == target_ident:
            # Species is in pslot.details, e.g. "Flutter Mane, L50" or "Incineroar, L50, F"
            parts = [p.strip() for p in pslot.details.split(",")]
            return parts[0] if parts else None
    return None


def _slot_action_features(
    slot_n: int,
    sa,
    request,
    state,
    ctx: "FeatureContext",
    opp_side: str,
    active_index: int,
    slot_letter: str,
) -> dict:
    """Build the slotN_* feature entries for one SlotAction.

    slot_n: 1 or 2 (the schema column prefix, e.g. slot1_move_id)
    sa: SlotAction
    active_index: 0-based index into request.active (= slot_n - 1)
    slot_letter: 'a' or 'b' (maps active_index to state.side()[letter])
    """
    prefix = f"slot{slot_n}_"
    out: dict = {}

    kind = sa.kind  # "move" | "switch" | "pass"
    out[f"{prefix}action_type"] = kind
    out[f"{prefix}is_switch"] = kind == "switch"

    # Actor species (who is in this active slot)
    our_side = ctx.our_side
    our_mon = state.side(our_side).get(slot_letter)
    if our_mon is not None and not getattr(our_mon, "fainted", False):
        actor_species = getattr(our_mon, "species", None)
        if actor_species and ctx.dex is not None:
            try:
                out[f"{prefix}actor_species_id"] = ctx.dex.to_id(actor_species)
            except Exception:
                out[f"{prefix}actor_species_id"] = SENTINEL_CAT_NONE
        else:
            out[f"{prefix}actor_species_id"] = SENTINEL_CAT_NONE
    else:
        out[f"{prefix}actor_species_id"] = SENTINEL_CAT_NONE

    # Move-specific fields
    if kind == "move":
        move_id: str | None = None
        meta = None

        # Resolve move_id from request
        move_index = sa.move_index
        try:
            active_slot = request.active[active_index] if request.active and active_index < len(request.active) else None
            if active_slot is not None and move_index is not None:
                zero_idx = move_index - 1  # 1-based -> 0-based
                if 0 <= zero_idx < len(active_slot.moves):
                    move_id = active_slot.moves[zero_idx].id
        except (IndexError, TypeError, AttributeError):
            move_id = None

        if move_id is not None and ctx.move_meta is not None:
            try:
                meta = ctx.move_meta.get(move_id)
            except AttributeError:
                meta = None

        if move_id is not None:
            out[f"{prefix}move_id"] = move_id
        else:
            out[f"{prefix}move_id"] = SENTINEL_CAT_NONE

        if meta is not None:
            out[f"{prefix}move_type"] = meta.move_type or SENTINEL_CAT_NONE
            out[f"{prefix}move_category"] = meta.category
            out[f"{prefix}priority"] = meta.priority
            out[f"{prefix}is_damaging"] = bool(meta.is_damaging)
            out[f"{prefix}is_protect"] = _is_protect_move(move_id or "", meta)
        else:
            out[f"{prefix}move_type"] = SENTINEL_CAT_NONE
            out[f"{prefix}move_category"] = SENTINEL_CAT_NONE
            out[f"{prefix}priority"] = 0
            out[f"{prefix}is_damaging"] = SENTINEL_BOOL
            out[f"{prefix}is_protect"] = SENTINEL_BOOL

        # Target
        target = sa.target
        out[f"{prefix}target_kind"] = _target_kind(target)
        out[f"{prefix}target_slot"] = target if target is not None else SENTINEL_NUM

        # Target species (foe/ally whose mon is known in state)
        target_species_id = SENTINEL_CAT_UNKNOWN
        if target in (1, 2) and ctx.dex is not None:
            raw_species = _opp_active_species(state, opp_side, target)
            if raw_species is not None:
                try:
                    target_species_id = ctx.dex.to_id(raw_species)
                except Exception:
                    target_species_id = SENTINEL_CAT_UNKNOWN
        elif target == -1:
            # Ally slot: the other active slot's species
            ally_letter = "b" if slot_letter == "a" else "a"
            ally_mon = state.side(our_side).get(ally_letter)
            if ally_mon is not None and not getattr(ally_mon, "fainted", False) and ctx.dex is not None:
                ally_species = getattr(ally_mon, "species", None)
                if ally_species:
                    try:
                        target_species_id = ctx.dex.to_id(ally_species)
                    except Exception:
                        target_species_id = SENTINEL_CAT_UNKNOWN
        elif target == -2:
            # Self — we know the species
            if our_mon is not None and ctx.dex is not None:
                self_species = getattr(our_mon, "species", None)
                if self_species:
                    try:
                        target_species_id = ctx.dex.to_id(self_species)
                    except Exception:
                        target_species_id = SENTINEL_CAT_UNKNOWN
        elif target is None:
            # No target (spread, field, self-stat moves) -> unknown
            target_species_id = SENTINEL_CAT_UNKNOWN
        out[f"{prefix}target_species_id_if_known"] = target_species_id

        # Switch target species: n/a for move
        out[f"{prefix}switch_target_species_id"] = SENTINEL_CAT_NONE

    elif kind == "switch":
        # Move fields all n/a
        out[f"{prefix}move_id"] = SENTINEL_CAT_NONE
        out[f"{prefix}move_type"] = SENTINEL_CAT_NONE
        out[f"{prefix}move_category"] = SENTINEL_CAT_NONE
        out[f"{prefix}priority"] = 0
        out[f"{prefix}is_damaging"] = SENTINEL_BOOL
        out[f"{prefix}is_protect"] = SENTINEL_BOOL
        out[f"{prefix}target_kind"] = SENTINEL_CAT_NONE
        out[f"{prefix}target_slot"] = SENTINEL_NUM
        out[f"{prefix}target_species_id_if_known"] = SENTINEL_CAT_UNKNOWN

        # Resolve switch target species via request bench
        raw_species = _bench_species_from_ident(request, sa.target_ident)
        if raw_species is not None and ctx.dex is not None:
            try:
                out[f"{prefix}switch_target_species_id"] = ctx.dex.to_id(raw_species)
            except Exception:
                out[f"{prefix}switch_target_species_id"] = SENTINEL_CAT_NONE
        else:
            out[f"{prefix}switch_target_species_id"] = SENTINEL_CAT_NONE

    else:
        # kind == "pass": all fields are sentinels
        out[f"{prefix}move_id"] = SENTINEL_CAT_NONE
        out[f"{prefix}move_type"] = SENTINEL_CAT_NONE
        out[f"{prefix}move_category"] = SENTINEL_CAT_NONE
        out[f"{prefix}priority"] = 0
        out[f"{prefix}is_damaging"] = SENTINEL_BOOL
        out[f"{prefix}is_protect"] = SENTINEL_BOOL
        out[f"{prefix}target_kind"] = SENTINEL_CAT_NONE
        out[f"{prefix}target_slot"] = SENTINEL_NUM
        out[f"{prefix}target_species_id_if_known"] = SENTINEL_CAT_UNKNOWN
        out[f"{prefix}switch_target_species_id"] = SENTINEL_CAT_NONE

    return out


def _group2_action(candidate, request, state, ctx: "FeatureContext") -> dict:
    """Build all Group-2 (candidate-action) features for one CandidateTrace.

    Maps JointAction.slot0/slot1 -> schema columns slot1_*/slot2_* respectively.
    Slot-1 (schema) = active_index 0 = state slot 'a'.
    Slot-2 (schema) = active_index 1 = state slot 'b'.
    """
    ja = candidate.joint_action
    opp_side = _opp_side(ctx.our_side)

    out: dict = {}
    out.update(_slot_action_features(
        slot_n=1, sa=ja.slot0, request=request, state=state, ctx=ctx,
        opp_side=opp_side, active_index=0, slot_letter="a",
    ))
    out.update(_slot_action_features(
        slot_n=2, sa=ja.slot1, request=request, state=state, ctx=ctx,
        opp_side=opp_side, active_index=1, slot_letter="b",
    ))

    # tera_used: True if either slot terastallizes
    out["tera_used"] = bool(ja.slot0.terastallize or ja.slot1.terastallize)

    return out


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
# Group-3 + Group-4 helpers
# ---------------------------------------------------------------------------


def _entropy(weights) -> float:
    """Shannon entropy in bits for a weight distribution.

    Returns 0.0 for empty, zero-sum, or single-element inputs (no uncertainty).
    """
    ws = [w for w in (weights or []) if w > 0]
    tot = sum(ws)
    if tot <= 0 or len(ws) <= 1:
        return 0.0
    return -sum((w / tot) * math.log2(w / tot) for w in ws)



def _group3_eval(candidate, trace) -> dict:
    """Group-3 eval features: read ONLY from trace, never recompute."""
    sv = candidate.score_vector or []
    bd = candidate.aggregate_breakdown
    mf = candidate.model_features
    cands = trace.candidates
    top = cands[0].aggregate_score if cands else candidate.aggregate_score
    second = cands[1].aggregate_score if len(cands) > 1 else top
    out = bd.predicted_outgoing_damage
    inc = bd.predicted_incoming_damage
    return {
        "heuristic_aggregate_score": candidate.aggregate_score,
        "score_gap_to_top": candidate.aggregate_score - top,
        "score_gap_to_second": candidate.aggregate_score - second,
        "score_min_vs_opp": min(sv) if sv else 0.0,
        "score_mean_vs_opp": (sum(sv) / len(sv)) if sv else 0.0,
        "score_var_vs_opp": pvariance(sv) if len(sv) > 1 else 0.0,
        "score_worst_response": min(sv) if sv else 0.0,
        "predicted_outgoing_damage": out,
        "predicted_incoming_damage": inc,
        "out_in_ratio": out / (inc + 1e-6),
        "predicted_kos_for": bd.my_kos,
        "predicted_kos_against": bd.my_faints,
        "ko_secured_count": mf.ko_secured_count,
        "ko_threatened_count": mf.ko_threatened_count,
        "survives_for_sure_count": mf.survives_for_sure_count,
        "protect_stall_penalty": bd.protect_stall_penalty,
        "partner_abandon_penalty": bd.partner_abandon_penalty,
        "fakeout_invalid_penalty": 0.0,      # sentinel (future task)
        "action_economy_score": 0.0,          # sentinel (future task)
    }


def _group4_tempo(candidate, trace, state, ctx: "FeatureContext") -> dict:
    """Group-4 tempo/risk features: trace + state + context."""
    sv = candidate.score_vector or []
    priors = ctx.protect_priors_by_opp_slot or {}
    tf = trace.tempo_features
    return {
        "we_outspeed_count": tf.we_outspeed_count,
        "they_outspeed_count": tf.they_outspeed_count,
        "speed_tie_count": tf.speed_tie_count,
        "our_fastest_active_speed": tf.our_fastest_active_speed,
        "opp_fastest_active_speed": tf.opp_fastest_active_speed,
        "must_react_reason_flags": 1 if trace.game_mode == "MUST_REACT" else 0,
        "protect_prior_target1": float(priors.get("a", 0.0)),
        "protect_prior_target2": float(priors.get("b", 0.0)),
        "response_count": len(trace.opponent_responses),
        "opponent_response_entropy": _entropy(trace.opponent_response_weights),
        "value_range_across_opp_responses": (max(sv) - min(sv)) if sv else 0.0,
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
        "teacher_version": ctx.teacher_config["teacher_version"],
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

def extract_features(trace, state, request, context: FeatureContext, *, labels=None) -> list[Row]:
    """Return one schema-valid Row per labeled candidate in trace.candidates.

    ``labels`` must be a dict mapping candidate_id -> label dict (one per LABEL_KEYS).
    If omitted (None), falls back to stub zero-labels for all candidates (backward-compat).

    When provided, ``labels`` must be a prefix of trace.candidates in trace order
    (validated by _validate_label_prefix).  Rows are emitted only for candidates
    whose candidate_id appears in ``labels``, preserving trace order.

    This scaffold sets every feature to its typed sentinel; later tasks replace
    stubs with real values group by group, without breaking these gates.
    """
    from showdown_bot.battle.candidate_identity import candidate_identity
    from showdown_bot.learning.label_provider import _validate_label_prefix

    if labels is None:
        from showdown_bot.battle.candidate_identity import assert_unique_candidate_identities
        assert_unique_candidate_identities(trace.candidates)
        labels = {candidate_identity(c): _stub_label() for c in trace.candidates}
    else:
        _validate_label_prefix(trace, labels)

    g1 = _group1_context(state, request, trace, context)
    rows = []
    candidate_index = 0
    for cand in trace.candidates:
        ident = candidate_identity(cand)
        if ident not in labels:
            continue
        features = _stub_features()
        features.update(g1)
        features.update(_group2_action(cand, request, state, context))
        features.update(_group3_eval(cand, trace))
        features.update(_group4_tempo(cand, trace, state, context))
        rows.append(
            Row(
                features=features,
                metadata=_metadata(context, candidate_index),
                label=labels[ident],
            )
        )
        candidate_index += 1
    return rows
