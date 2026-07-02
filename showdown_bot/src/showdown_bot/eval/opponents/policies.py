"""Eval-only opponent policies: greedy_protect + simple_heuristic (T3c).

Deterministic, request-only (no calc/rollout). Both take ``(req, **_ignored)`` so the eval
dispatch can call them with the same kwargs as the other agents. ``simple_heuristic`` also
accepts ``state``/``our_side`` (T3e Task 1) to score damage type-aware when the opposing
active typing is known; without them it degrades to the original base-power behavior.

This module is eval-only (imported lazily by the gauntlet dispatch), so the ``os``/``json``
imports below never touch the live decision path.
"""
from __future__ import annotations

import json
import os

from showdown_bot.battle.legal_actions import enumerate_slot_pairs
from showdown_bot.battle.team_preview import pick_team_preview_default
from showdown_bot.engine.typechart import effectiveness
from showdown_bot.eval.opponents._common import PROTECT_IDS, move_meta_for, pick_best_pair
from showdown_bot.protocol.encoder import encode_choose, encode_team_preview


def _emit_policy_telemetry(event: dict) -> None:
    """Append one policy-activation event as JSONL when ``SHOWDOWN_EVAL_POLICY_TELEMETRY``
    is set (T3e P2, eval-only). Unset -> no-op (no behavior change, no file). Best-effort:
    never raises into the decision path, and never affects the returned ``/choose``.
    """
    path = os.environ.get("SHOWDOWN_EVAL_POLICY_TELEMETRY")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
    except OSError:
        pass  # telemetry is diagnostic only — a bad path must not break the eval run

# Situational-Protect thresholds (T3e Task 2). Protect is only worth it defensively when a
# slot is genuinely in danger; a healthy slot Protecting just wastes a turn.
_LOW_HP = 0.4
_PROTECT_LOW_SCORE = 1000.0          # low-HP slot: Protect dominates any attack
_PROTECT_HEALTHY_SCORE = -50.0       # healthy slot: Protect discouraged (below any attack/status)
_DOUBLE_PROTECT_PENALTY = -1_000_000.0  # joint constraint: never Protect on BOTH slots


def _is_protect(meta) -> bool:
    return meta is not None and meta.id in PROTECT_IDS


def _slot_hp_fraction(state, our_side, slot: str) -> float:
    """HP fraction of our active mon in ``slot`` ("a"/"b"); full when unknown/no state."""
    if state is None or not our_side:
        return 1.0
    mon = state.active(our_side, slot)
    return mon.hp_fraction if mon is not None else 1.0


def _greedy_slot_score(meta, hp_fraction: float) -> float:
    if meta is None:
        return -1.0  # discourage switch/pass
    if meta.id in PROTECT_IDS:
        return _PROTECT_LOW_SCORE if hp_fraction < _LOW_HP else _PROTECT_HEALTHY_SCORE
    return float(meta.base_power) if meta.is_damaging else 0.0  # damage by power; other status = 0


def greedy_protect_choice(req, *, state=None, our_side=None, **_ignored) -> str:
    """Situational Protect: a slot Protects only when it is low on HP, and never both slots
    at once (a joint no-double-protect penalty); otherwise it takes the highest-power attack.

    HP is read from ``state`` (slot0 -> our "a", slot1 -> our "b"); without ``state``/``our_side``
    every slot is treated as full, so the policy attacks. A custom pair loop (not independent
    slot scoring) is used because no-double-protect couples the two slots. Deterministic:
    first max-scoring pair in enumeration order wins.
    """
    if req.team_preview:
        return encode_team_preview(pick_team_preview_default(req), rqid=req.rqid)
    pairs = enumerate_slot_pairs(req)
    if not pairs:
        return f"/choose default|{req.rqid}"
    hp0 = _slot_hp_fraction(state, our_side, "a")
    hp1 = _slot_hp_fraction(state, our_side, "b")
    best = pairs[0]
    best_score = float("-inf")
    for pair in pairs:
        meta0 = move_meta_for(req, 0, pair.slot0)
        meta1 = move_meta_for(req, 1, pair.slot1)
        score = _greedy_slot_score(meta0, hp0) + _greedy_slot_score(meta1, hp1)
        if _is_protect(meta0) and _is_protect(meta1):
            score += _DOUBLE_PROTECT_PENALTY
        if score > best_score:  # strict > -> first pair wins ties (deterministic)
            best_score = score
            best = pair
    # Activation telemetry (T3e P2): did the HP-gate actually produce a low-HP Protect?
    if (hp0 < _LOW_HP and _is_protect(move_meta_for(req, 0, best.slot0))) or \
       (hp1 < _LOW_HP and _is_protect(move_meta_for(req, 1, best.slot1))):
        _emit_policy_telemetry({"policy": "greedy_protect", "event": "hp_gated_protect_fired"})
    return encode_choose(best, rqid=req.rqid)


def _resolved_types(mon, resolver) -> list[str]:
    """Types of ``mon``: its known ``types`` if present, else an eval-only species->types
    lookup via ``resolver`` (T3e P2a). Read-only — never mutates the shared ``BattleState``.
    Any failure (no resolver, no species, backend down, unknown species) -> ``[]`` so the
    caller degrades to neutral/base-power. Mirrors ``battle.opponent._types_of`` but keeps
    the derivation eval-only (the live state is left untouched)."""
    if mon is None:
        return []
    if getattr(mon, "types", None):
        return list(mon.types)
    species = getattr(mon, "species", None)
    if resolver is not None and species:
        try:
            return list(resolver.types(species))
        except Exception:  # noqa: BLE001 - resolver is best-effort; fall back to neutral
            return []
    return []


def target_types_for_action(meta, action, state, our_side, resolver=None) -> list[tuple[str, ...]]:
    """Defender type-tuples for the opposing active mon(s) a move would hit.

    ``meta`` is needed to tell a spread move (hits BOTH foes) from a single-target one
    (hits the slot named by ``action.target``: 1 -> opp "a", 2 -> opp "b", matching
    ``decision._map_target``). Types come from the mon's known typing, or — when only the
    species is known (the live eval-state case, T3e P2a) — from the eval-only ``resolver``.
    Any unknown situation (no ``state``/``our_side``, non-move action, no foe target, no
    types resolvable) yields ``[]`` so the caller falls back to neutral (1.0).
    """
    if state is None or not our_side or meta is None:
        return []
    if action is None or action.kind != "move":
        return []
    opp_side = "p2" if our_side == "p1" else "p1"
    if meta.is_spread:
        slots = ["a", "b"]
    elif action.target == 1:
        slots = ["a"]
    elif action.target == 2:
        slots = ["b"]
    else:
        slots = []  # None / self / ally / unknown -> no explicit foe target
    out: list[tuple[str, ...]] = []
    for slot in slots:
        types = _resolved_types(state.active(opp_side, slot), resolver)
        if types:
            out.append(tuple(types))
    return out


def _score_and_effect(meta, action, state, our_side, resolver) -> tuple[float, bool]:
    """Return ``(score, used_type_effectiveness)``. ``used_type_effectiveness`` is True iff
    the type-aware branch fired with a **non-neutral** multiplier (target types known — via
    the state or the eval-only ``resolver`` — AND ``effectiveness != 1.0``): the activation
    signal."""
    if meta is None:
        return -1.0, False
    if not meta.is_damaging:
        return 0.0, False
    base_power = float(meta.base_power)
    # move_type may be None for an unknown move -> keep base-power behavior (neutral).
    types_list = target_types_for_action(meta, action, state, our_side, resolver)
    if not types_list or meta.move_type is None:
        return base_power, False
    eff = max(effectiveness(meta.move_type, list(t)) for t in types_list)
    return base_power * eff, (eff != 1.0)


def _simple_heuristic_slot(meta, action, *, state, our_side, resolver=None) -> float:
    return _score_and_effect(meta, action, state, our_side, resolver)[0]


def simple_heuristic_choice(req, *, state=None, our_side=None, resolver=None, **_ignored) -> str:
    """Highest-scoring damaging move per slot — power-greedy, no calc/search.

    Damage is scored as ``base_power * effectiveness(move_type, target_types)`` (spread =
    max over affected foes) when the opposing typing is resolvable — from ``state`` typing,
    or via the eval-only ``resolver`` (species->types) when the live state carries only the
    species (T3e P2a). Otherwise it degrades to the original base-power ranking. Deterministic
    tie-break stays ``pick_best_pair``'s first-pair-wins order.
    """
    fired = False

    def slot_score(meta, action) -> float:
        nonlocal fired
        score, used_effect = _score_and_effect(meta, action, state, our_side, resolver)
        if used_effect:
            fired = True  # activation: a scored move used resolvable types + eff != 1.0
        return score

    out = pick_best_pair(req, slot_score)
    if fired:
        _emit_policy_telemetry({"policy": "simple_heuristic", "event": "type_effectiveness_fired"})
    return out
