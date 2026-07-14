"""Canonical observable pre-states and `/choose` actions for decision capture.

This is an offline module: it does not touch the live battle path. It exists
so that a decision sidecar can bind each hero decision to a deterministic
hash of what was actually visible to the bot at decision time (never
outcomes, winners, future logs, or un-revealed information).
"""
from __future__ import annotations

import gzip
import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

from showdown_bot.engine.state import BattleState, PokemonState, to_id
from showdown_bot.models.request import BattleRequest

TRACE_SCHEMA_VERSION_V1 = "decision-trace-v1"
TRACE_SCHEMA_VERSION_V2 = "decision-trace-v2"
TRACE_SCHEMA_VERSION = TRACE_SCHEMA_VERSION_V2
SUPPORTED_TRACE_SCHEMA_VERSIONS = frozenset({TRACE_SCHEMA_VERSION_V1, TRACE_SCHEMA_VERSION_V2})
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


# ---------------------------------------------------------------------------
# Sidecar trace rows: validate, write, load, and bind to battles.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BattleTraceContext:
    battle_id: str
    seed_index: int
    config_id: str
    config_hash: str
    schedule_hash: str
    format_id: str
    git_sha: str
    our_side: str = "p1"


def _validate_v1_row(row: dict) -> None:
    for candidate in row["candidates"]:
        score = candidate["aggregate_score"]
        if not isinstance(score, (int, float)) or not math.isfinite(score):
            raise DecisionCaptureError("candidate aggregate_score must be finite")


def _validate_chosen_tera_slot(tera_slot) -> None:
    if tera_slot is not None and (type(tera_slot) is not int or tera_slot not in (0, 1)):
        raise DecisionCaptureError("chosen_tera_slot must be null or int 0/1")


def _validate_v2_tera_overlay(row: dict, *, chosen_key: str, tera_slot: int | None) -> None:
    normalized = row.get("normalized_action")
    if not isinstance(normalized, dict) or normalized.get("kind") != "joint":
        return
    norm_slots = normalized.get("slots")
    if not isinstance(norm_slots, list) or len(norm_slots) != 2:
        return

    tera_indices = [
        i for i, slot in enumerate(norm_slots)
        if slot.get("kind") == "move" and slot.get("tera") is True
    ]
    if tera_slot is None:
        if tera_indices:
            raise DecisionCaptureError(
                "chosen_tera_slot is null but normalized_action has a tera overlay"
            )
    elif len(tera_indices) != 1 or tera_indices[0] != tera_slot:
        raise DecisionCaptureError(
            "chosen_tera_slot inconsistent with normalized_action tera overlay"
        )

    try:
        payload = json.loads(chosen_key)
    except json.JSONDecodeError as exc:
        raise DecisionCaptureError("chosen_candidate_key must be valid JSON") from exc
    key_slots = payload.get("slots")
    if not isinstance(key_slots, list) or len(key_slots) != 2:
        raise DecisionCaptureError("chosen_candidate_key must contain exactly two slots")

    for idx, (key_slot, norm_slot) in enumerate(zip(key_slots, norm_slots, strict=True)):
        if not isinstance(key_slot, dict) or not isinstance(norm_slot, dict):
            raise DecisionCaptureError("chosen_candidate_key slot payload must be an object")
        if key_slot.get("kind") != norm_slot.get("kind"):
            raise DecisionCaptureError(
                "chosen_candidate_key kind mismatch vs normalized_action"
            )
        if norm_slot.get("kind") == "move":
            if key_slot.get("move_index") != norm_slot.get("move_index"):
                raise DecisionCaptureError(
                    "chosen_candidate_key move_index mismatch vs normalized_action"
                )
            if key_slot.get("target") != norm_slot.get("target"):
                raise DecisionCaptureError(
                    "chosen_candidate_key target mismatch vs normalized_action"
                )
            if tera_slot == idx:
                if key_slot.get("terastallize") is not False:
                    raise DecisionCaptureError(
                        "pre-tera chosen_candidate_key slot must have terastallize=false"
                    )
            elif key_slot.get("terastallize") is True or norm_slot.get("tera") is True:
                raise DecisionCaptureError(
                    "unexpected tera on non-chosen slot between key and normalized_action"
                )
        elif norm_slot.get("kind") == "switch":
            target_ident = key_slot.get("target_ident")
            switch_target = norm_slot.get("switch_target")
            if not isinstance(target_ident, str) or not target_ident:
                raise DecisionCaptureError(
                    "chosen_candidate_key switch slot must have non-empty target_ident"
                )
            if not isinstance(switch_target, str) or not switch_target:
                raise DecisionCaptureError(
                    "normalized_action switch slot must have non-empty switch_target"
                )
            if to_id(target_ident) != switch_target:
                raise DecisionCaptureError(
                    "chosen_candidate_key switch target_ident mismatch vs normalized_action"
                )
        elif norm_slot.get("kind") == "pass":
            if key_slot.get("target_ident") is not None:
                raise DecisionCaptureError(
                    "chosen_candidate_key pass slot must not carry target_ident"
                )


def _validate_v2_row(row: dict) -> None:
    candidates = row["candidates"]
    keys = [c.get("candidate_key") for c in candidates]
    if candidates:
        if any(not isinstance(k, str) or not k for k in keys):
            raise DecisionCaptureError("v2 candidate_key must be non-empty string")
        if len(set(keys)) != len(keys):
            raise DecisionCaptureError("v2 candidate_key values must be unique within row")
        chosen_key = row.get("chosen_candidate_key")
        if not isinstance(chosen_key, str) or not chosen_key:
            raise DecisionCaptureError("v2 chosen_candidate_key required when candidates present")
        if chosen_key not in keys:
            raise DecisionCaptureError("v2 chosen_candidate_key must reference a traced candidate")

        chosen_id = row.get("chosen_candidate_id")
        if not isinstance(chosen_id, str) or not chosen_id:
            raise DecisionCaptureError("v2 chosen_candidate_id must be non-empty string")

        chosen_rank = row.get("chosen_rank")
        if type(chosen_rank) is not int:
            raise DecisionCaptureError("v2 chosen_rank must be int")

        matched = next(c for c in candidates if c.get("candidate_key") == chosen_key)
        if chosen_rank != matched.get("rank"):
            raise DecisionCaptureError(
                "chosen_rank must match rank of candidate under chosen_candidate_key"
            )
        if matched.get("candidate_id") != chosen_id:
            raise DecisionCaptureError(
                "chosen_candidate_id must match candidate_id for chosen_candidate_key"
            )

        tera_slot = row.get("chosen_tera_slot")
        _validate_chosen_tera_slot(tera_slot)
        _validate_v2_tera_overlay(row, chosen_key=chosen_key, tera_slot=tera_slot)
    else:
        for field in ("chosen_candidate_key", "chosen_candidate_id", "chosen_rank", "chosen_tera_slot"):
            if row.get(field) is not None:
                raise DecisionCaptureError(f"v2 fallback row must have null {field}")
    for candidate in candidates:
        score = candidate["aggregate_score"]
        if not isinstance(score, (int, float)) or not math.isfinite(score):
            raise DecisionCaptureError("candidate aggregate_score must be finite")


_REQUIRED_TRACE_FIELDS = frozenset({
    "trace_schema_version", "battle_id", "seed_index", "decision_index", "turn_number",
    "our_side", "config_id", "config_hash", "schedule_hash", "format_id", "git_sha",
    "observable_state_hash", "request_hash", "decision_phase", "state_summary",
    "actual_choose_string", "normalized_action", "candidates", "decision_latency_ms",
})
_NULLABLE_TRACE_FIELDS = frozenset({
    "chosen_candidate_id", "chosen_rank", "selection_stage", "fallback_reason",
})
_V2_ONLY_NULLABLE_FIELDS = frozenset({
    "chosen_candidate_key", "chosen_tera_slot",
})


def validate_trace_row(row: dict) -> None:
    version = row.get("trace_schema_version")
    if version not in SUPPORTED_TRACE_SCHEMA_VERSIONS:
        raise DecisionCaptureError("unknown trace schema version")
    nullable = _NULLABLE_TRACE_FIELDS
    if version == TRACE_SCHEMA_VERSION_V2:
        nullable = nullable | _V2_ONLY_NULLABLE_FIELDS
    missing = _REQUIRED_TRACE_FIELDS - set(row)
    unknown = set(row) - _REQUIRED_TRACE_FIELDS - nullable
    if missing or unknown:
        raise DecisionCaptureError(f"trace fields missing={sorted(missing)} unknown={sorted(unknown)}")
    if row["decision_phase"] not in {"team_preview", "forced_replacement", "regular_turn"}:
        raise DecisionCaptureError("unknown decision phase")
    for key in ("seed_index", "decision_index", "turn_number"):
        if not isinstance(row[key], int) or row[key] < 0:
            raise DecisionCaptureError(f"{key} must be a non-negative int")
    for key in ("observable_state_hash", "request_hash"):
        if not isinstance(row[key], str) or re.fullmatch(r"[0-9a-f]{64}", row[key]) is None:
            raise DecisionCaptureError(f"{key} must be lowercase sha256 hex")
    if not isinstance(row["decision_latency_ms"], (int, float)) or not math.isfinite(row["decision_latency_ms"]):
        raise DecisionCaptureError("decision_latency_ms must be finite")
    if version == TRACE_SCHEMA_VERSION_V1:
        _validate_v1_row(row)
    else:
        _validate_v2_row(row)


def build_trace_row(*, context: BattleTraceContext, prepared: PreparedCapture,
                    request: BattleRequest, choose: str, trace, decision_index: int,
                    decision_latency_ms: float,
                    selection_stage_override: str | None = None,
                    fallback_reason_override: str | None = None) -> dict:
    from showdown_bot.battle.candidate_identity import (
        ChosenCandidateResolutionError,
        assert_unique_candidate_identities,
        resolve_chosen_candidate,
    )

    if trace is None or not trace.candidates:
        candidates = []
        chosen_candidate_id = None
        chosen_candidate_key = None
        chosen_rank = None
        chosen_tera_slot = None
    else:
        assert_unique_candidate_identities(trace.candidates)
        try:
            chosen = resolve_chosen_candidate(trace)
        except ChosenCandidateResolutionError as exc:
            raise DecisionCaptureError(str(exc)) from exc
        chosen_candidate_id = trace.chosen_candidate_id
        chosen_candidate_key = trace.chosen_candidate_key
        chosen_rank = chosen.rank
        chosen_tera_slot = trace.chosen_tera_slot
        candidates = [
            {
                "candidate_id": c.candidate_id,
                "candidate_key": c.candidate_key,
                "rank": c.rank,
                "aggregate_score": c.aggregate_score,
            }
            for c in trace.candidates
        ]

    row = {
        "trace_schema_version": TRACE_SCHEMA_VERSION_V2,
        "battle_id": context.battle_id,
        "seed_index": context.seed_index,
        "decision_index": decision_index,
        "turn_number": prepared.state_summary.get("turn", 0),
        "our_side": context.our_side,
        "config_id": context.config_id,
        "config_hash": context.config_hash,
        "schedule_hash": context.schedule_hash,
        "format_id": context.format_id,
        "git_sha": context.git_sha,
        "observable_state_hash": prepared.observable_state_hash,
        "request_hash": prepared.request_hash,
        "decision_phase": prepared.decision_phase,
        "state_summary": prepared.state_summary,
        "actual_choose_string": choose,
        "normalized_action": normalize_choose(choose, request),
        "chosen_candidate_id": chosen_candidate_id,
        "chosen_candidate_key": chosen_candidate_key,
        "chosen_tera_slot": chosen_tera_slot,
        "chosen_rank": chosen_rank,
        "candidates": candidates,
        "selection_stage": selection_stage_override if selection_stage_override is not None else
                           (None if trace is None else trace.selection_stage),
        "fallback_reason": fallback_reason_override if fallback_reason_override is not None else
                           (None if trace is None else trace.fallback_reason),
        "decision_latency_ms": float(decision_latency_ms),
    }
    validate_trace_row(row)
    return row


def _open_text(path, mode: str):
    path = Path(path)
    return gzip.open(path, mode + "t", encoding="utf-8", newline="\n") \
        if path.suffix == ".gz" else open(path, mode, encoding="utf-8", newline="\n")


class DecisionTraceWriter:
    def __init__(self, path):
        self.path = Path(path)
        if self.path.exists() and self.path.stat().st_size:
            raise DecisionCaptureError(f"trace output must be missing or empty: {self.path}")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._keys = set()
        self._lines_by_battle = {}
        self._errors_by_battle = {}

    def write(self, row: dict) -> None:
        battle_id = str(row.get("battle_id", ""))
        try:
            validate_trace_row(row)
            key = (battle_id, row["decision_index"], row["our_side"])
            if key in self._keys:
                raise DecisionCaptureError(f"duplicate decision key: {key!r}")
            line = _canonical_json(row) + "\n"
            with _open_text(self.path, "a") as fh:
                fh.write(line)
            self._keys.add(key)
            self._lines_by_battle.setdefault(battle_id, []).append(line.encode("utf-8"))
        except Exception as exc:
            self._errors_by_battle.setdefault(battle_id, []).append(str(exc))
            raise

    def finish_battle(self, battle_id: str) -> dict:
        errors = self._errors_by_battle.get(battle_id, [])
        if errors:
            raise DecisionCaptureError(f"battle {battle_id} capture errors: {errors}")
        lines = self._lines_by_battle.get(battle_id, [])
        if not lines:
            raise DecisionCaptureError(f"battle {battle_id} has no decision rows")
        return {
            "decision_trace_count": len(lines),
            "decision_trace_sha256": hashlib.sha256(b"".join(lines)).hexdigest(),
        }


def load_decision_trace(path) -> list[dict]:
    rows = []
    with _open_text(path, "r") as fh:
        for line_number, line in enumerate(fh, 1):
            try:
                row = json.loads(line)
                validate_trace_row(row)
            except Exception as exc:
                raise DecisionCaptureError(f"{path}:{line_number}: {exc}") from exc
            rows.append(row)
    return rows
