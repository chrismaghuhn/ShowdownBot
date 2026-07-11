"""Canonical observable pre-states and `/choose` actions for decision capture.

This is an offline module: it does not touch the live battle path. It exists
so that a decision sidecar can bind each hero decision to a deterministic
hash of what was actually visible to the bot at decision time (never
outcomes, winners, future logs, or un-revealed information).
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from showdown_bot.engine.state import BattleState, PokemonState, to_id
from showdown_bot.models.request import BattleRequest

TRACE_SCHEMA_VERSION = "decision-trace-v1"
PROTECT_IDS = frozenset({
    "protect", "detect", "wideguard", "quickguard", "spikyshield",
    "kingsshield", "banefulbunker", "silktrap", "burningbulwark", "maxguard",
})


class DecisionCaptureError(ValueError):
    pass


@dataclass(frozen=True)
class PreparedCapture:
    observable_state_hash: str
    request_hash: str
    state_summary: dict
    decision_phase: str


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(payload: object) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _pokemon_payload(mon: PokemonState) -> dict:
    return {
        "species": mon.species,
        "nickname": mon.nickname,
        "level": mon.level,
        "gender": mon.gender,
        "hp": mon.hp,
        "max_hp": mon.max_hp,
        "boosts": dict(sorted(mon.boosts.items())),
        "status": mon.status,
        "item": mon.item if mon.item_known else None,
        "item_known": mon.item_known,
        "ability": mon.ability,
        "moves": sorted(mon.moves),
        "tera_type": mon.tera_type,
        "terastallized": mon.terastallized,
        "fainted": mon.fainted,
        "types": list(mon.types),
        "consecutive_protect": mon.consecutive_protect,
        "moved_since_switch": mon.moved_since_switch,
        "item_lost": mon.item_lost,
    }


def observable_state_payload(state: BattleState | None) -> dict | None:
    if state is None:
        return None
    return {
        "turn": state.turn,
        "field": {
            "weather": state.field.weather,
            "terrain": state.field.terrain,
            "trick_room": state.field.trick_room,
            "tailwind": dict(sorted(state.field.tailwind.items())),
        },
        "sides": {
            side: {slot: _pokemon_payload(mon) for slot, mon in sorted(slots.items())}
            for side, slots in sorted(state.sides.items())
        },
    }


def request_payload(request: BattleRequest) -> dict:
    return request.model_dump(mode="json", by_alias=True, exclude_none=False)


def prepare_capture(state: BattleState | None, request: BattleRequest) -> PreparedCapture:
    state_payload = observable_state_payload(state)
    req_payload = request_payload(request)
    if request.team_preview:
        phase = "team_preview"
    elif request.force_switch is not None and any(request.force_switch):
        phase = "forced_replacement"
    else:
        phase = "regular_turn"
    return PreparedCapture(
        observable_state_hash=_sha256({"state": state_payload, "request": req_payload}),
        request_hash=_sha256(req_payload),
        state_summary=state_payload or {"turn": 0, "field": {}, "sides": {}},
        decision_phase=phase,
    )


_MOVE_RE = re.compile(r"^move (?P<index>\d+)(?: (?P<target>-?\d+))?(?: (?P<tera>terastallize))?$")


def _slot_action(token: str, request: BattleRequest, slot_index: int) -> dict:
    token = " ".join(token.strip().lower().split())
    if token == "pass":
        return {"kind": "pass"}
    if token.startswith("switch "):
        target = token[len("switch "):].strip()
        if not target:
            raise DecisionCaptureError("empty switch target")
        return {"kind": "switch", "switch_target": to_id(target)}
    match = _MOVE_RE.fullmatch(token)
    if match is None:
        raise DecisionCaptureError(f"unsupported slot action: {token!r}")
    move_index = int(match.group("index"))
    active = request.active[slot_index] if slot_index < len(request.active) else None
    if active is None or not 1 <= move_index <= len(active.moves):
        raise DecisionCaptureError(f"move index {move_index} unavailable for slot {slot_index}")
    move_id = to_id(active.moves[move_index - 1].id)
    return {
        "kind": "move",
        "move_index": move_index,
        "move_id": move_id,
        "target": int(match.group("target")) if match.group("target") is not None else None,
        "tera": match.group("tera") is not None,
        "is_protect": move_id in PROTECT_IDS,
    }


def normalize_choose(choose: str, request: BattleRequest) -> dict:
    if not choose.startswith("/choose "):
        raise DecisionCaptureError(f"not a /choose command: {choose!r}")
    body = choose[len("/choose "):].split("|", 1)[0].strip()
    if body == "default":
        return {"kind": "default"}
    if body.startswith("team "):
        order = body[len("team "):].strip()
        if not order.isdigit():
            raise DecisionCaptureError(f"invalid team preview order: {order!r}")
        return {"kind": "team_preview", "order": [int(ch) for ch in order]}
    tokens = body.split(", ")
    if len(tokens) != 2:
        raise DecisionCaptureError(f"expected two slot actions: {body!r}")
    slots = [_slot_action(token, request, i) for i, token in enumerate(tokens)]
    return {"kind": "joint", "slots": slots}
