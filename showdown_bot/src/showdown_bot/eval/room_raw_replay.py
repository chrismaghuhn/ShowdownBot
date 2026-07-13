"""Extract real (state, request) decision points from committed room_raw protocol logs.

Mirrors client/gauntlet.py's own BattleState.from_log_text / merge_request /
BattleRequest.model_validate chain exactly -- this module adds no new resolution logic,
only offline replay of what the live client already does per-request.

One deliberate divergence from gauntlet.py's ``_state_for``: gauntlet.py wraps the
state-build chain in try/except and degrades to ``state=None`` per-decision on failure
(a live client must stay resilient to keep playing). This module does NOT catch that
exception -- it is an offline correctness gate, and silently dropping a decision on a
swallowed exception would undermine the statistical rigor the gate depends on. A
malformed line propagates as a hard failure for the whole file instead of a silent
partial result.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from showdown_bot.engine.state import BattleState, merge_request
from showdown_bot.eval.room_dump import read_room_log_frames
from showdown_bot.models.request import BattleRequest


class RequestKind(Enum):
    TEAM_PREVIEW = "team_preview"
    FORCE_SWITCH = "force_switch"
    MOVE = "move"


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ExtractedDecision:
    # hash=False: state/request are unhashable objects; excluding them from hash
    # computation is required for frozen dataclass instances to actually be hashable.
    # Equality (__eq__) still compares every field, including these two, unchanged.
    state: BattleState | None = field(hash=False)  # None for team-preview (see gauntlet._state_for)
    request: BattleRequest = field(hash=False)
    kind: RequestKind
    side: str  # "p1" | "p2"
    turn: int  # 0 if no |turn| line has been seen yet (team preview)
    request_hash: str
    log_prefix_hash: str
    _debug_prefix_line_count: int  # test-only introspection, not used by any consumer


def _request_kind(req: BattleRequest) -> RequestKind:
    if req.team_preview:
        return RequestKind.TEAM_PREVIEW
    if req.force_switch and any(req.force_switch):
        return RequestKind.FORCE_SWITCH
    return RequestKind.MOVE


def _hero_side(req: BattleRequest) -> str:
    side_id = (req.side.id or "").strip()
    if side_id in ("p1", "p2"):
        return side_id
    raise ValueError(f"request carries no resolvable side.id: {req.side!r}")


def extract_decisions_from_log(path: str | Path) -> list[ExtractedDecision]:
    frames = read_room_log_frames(path)
    full_text = frames[0] if frames else ""
    lines = full_text.split("\n")

    decisions: list[ExtractedDecision] = []
    seen_rqids: set[int] = set()
    current_turn = 0

    for i, line in enumerate(lines):
        if line.startswith("|turn|"):
            try:
                current_turn = int(line.split("|", 2)[2])
            except (IndexError, ValueError):
                pass
            continue
        if not line.startswith("|request|"):
            continue

        payload = line[len("|request|"):]
        req = BattleRequest.model_validate(json.loads(payload))

        if req.rqid in seen_rqids:
            continue  # reconnect resend of an already-processed request
        seen_rqids.add(req.rqid)

        if req.wait:
            continue  # opponent's turn -- nothing was chosen here, not a decision point

        prefix_lines = lines[: i + 1]  # up to AND including this line -- matches gauntlet.py
        prefix_text = "\n".join(prefix_lines)

        state: BattleState | None = None
        if not req.team_preview:
            # Intentionally NOT wrapped in try/except (unlike gauntlet.py's _state_for):
            # a malformed line should fail this offline gate loudly, not silently drop
            # a decision and undercount the statistics the gate is built to guarantee.
            state = BattleState.from_log_text(prefix_text)
            merge_request(req, state)

        decisions.append(ExtractedDecision(
            state=state,
            request=req,
            kind=_request_kind(req),
            side=_hero_side(req),
            turn=current_turn,
            request_hash=_sha256(_canonical_json(
                req.model_dump(mode="json", by_alias=True, exclude_none=False)
            )),
            log_prefix_hash=_sha256(prefix_text),
            _debug_prefix_line_count=len(prefix_lines),
        ))

    return decisions
