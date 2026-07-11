"""Full-fidelity aggregation-trace sidecar rows (2c-Slice-0b, Task 2).

Offline, research-only module: NOT on the live decision path. Persists the
EXACT per-candidate x per-opponent-response score matrix, the response
weights, and the exact aggregation mode/lambdas that
``battle/policy.py::aggregate_scores`` used at decision time (see
``battle/decision_trace.py``'s ``aggregation_mode``/``risk_lambda``/
``must_react_lambda``/``score_vector``/``aggregate_score`` fields, and
``battle/decision.py::_choose_best`` where they are populated).

A later offline probe (2c-Slice-0b Task 4) replays the exact aggregation
formula against these rows and self-consistency-checks it against the
``exported_aggregate_score`` that was actually produced. This module never
reads or writes game outcomes, winners, or teacher traces -- those are
joined in offline, matched on ``(battle_id, decision_index, our_side)``, by
a separate step (Task 5). ``teacher_best_action_keys`` is always written as
``[]`` here; a later step overwrites it out-of-band.

Mirrors ``eval/decision_capture.py`` (Spec-01) for the writer/loader
mechanics: gzip-aware I/O, per-battle ``(battle_id, decision_index,
our_side)`` dedup, per-battle count+sha256 ``finish_battle`` binding,
canonical ``json.dumps(sort_keys=True, separators=(",", ":"))``, a
missing-or-empty output guard, and fail-closed validation.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from showdown_bot.eval.decision_capture import normalize_choose

AGG_TRACE_SCHEMA_VERSION = "agg-trace-v1"


class AggTraceError(ValueError):
    pass


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _finite(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


# ---------------------------------------------------------------------------
# Opponent-response canonicalization.
#
# ``trace.opponent_responses`` entries are INTERNAL ``PlannedAction``-shaped
# objects (battle/resolve.py::PlannedAction) -- one list per predicted
# opponent joint response, e.g. [p2-slot-a action, p2-slot-b action]. They
# are NOT ``/choose`` strings, so ``normalize_choose`` does not apply here;
# ``_response_key`` builds its own deterministic, order-independent key from
# each action's identifying fields (side/slot/kind/move id/target/tera).
# ``speed`` (a computed number, not part of the action's identity) and
# ``is_ours`` (always False for opponent responses) are deliberately excluded.
# ---------------------------------------------------------------------------

def _action_identity(action: Any) -> dict:
    move = getattr(action, "move", None)
    target = getattr(action, "target", None)
    return {
        "side": action.side,
        "slot": action.slot,
        "kind": action.kind,
        "move_id": getattr(move, "id", None) if move is not None else None,
        "target": list(target) if target is not None else None,
        "is_tera": bool(getattr(action, "is_tera", False)),
    }


def _response_key(actions: list) -> str:
    """Canonical, order-independent key for one opponent joint response."""
    identities = sorted(
        (_action_identity(a) for a in actions),
        key=lambda d: (d["side"], d["slot"]),
    )
    return _canonical_json(identities)


# ---------------------------------------------------------------------------
# Row schema, build, validate.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AggTraceContext:
    battle_id: str
    seed_index: int
    our_side: str
    config_id: str
    config_hash: str
    schedule_hash: str
    format_id: str
    git_sha: str


def build_agg_row(*, context: AggTraceContext, trace, request, choose: str | None,
                   decision_index: int, turn_number: int | None = None) -> dict:
    """Build one full-fidelity aggregation-trace row.

    ``trace`` is a ``battle.decision_trace.DecisionTrace`` (or ``None`` for a
    minimal/degenerate row -- e.g. a decision where trace population never
    ran, such as team preview). ``request``/``choose`` are the same
    ``BattleRequest``/``/choose ...`` string used by ``eval.decision_capture``;
    ``choose`` may be ``None`` (-> ``selected_action_key`` is ``None``).

    ``turn_number`` (optional, default ``None``) is the in-battle turn number
    at decision time -- carried so an offline probe can join dataset teacher
    labels onto agg-trace rows via ``(seed_index, turn_number)``. It is
    ``None`` for team-preview/degenerate rows (no ``state``) and is otherwise
    a non-negative int; see ``validate_agg_row``.
    """
    response_actions = [] if trace is None else list(trace.opponent_responses)
    response_weights = [] if trace is None else list(trace.opponent_response_weights)
    resp_keys = [_response_key(actions) for actions in response_actions]

    selected_action_key = (
        _canonical_json(normalize_choose(choose, request)) if choose else None
    )

    row = {
        "agg_trace_schema_version": AGG_TRACE_SCHEMA_VERSION,
        "battle_id": context.battle_id,
        "seed_index": context.seed_index,
        "decision_index": decision_index,
        "turn_number": turn_number,
        "our_side": context.our_side,
        "config_id": context.config_id,
        "config_hash": context.config_hash,
        "schedule_hash": context.schedule_hash,
        "format_id": context.format_id,
        "git_sha": context.git_sha,
        "game_mode": None if trace is None else trace.game_mode,
        "aggregation_mode": None if trace is None else trace.aggregation_mode,
        "risk_lambda": None if trace is None else trace.risk_lambda,
        "must_react_lambda": None if trace is None else trace.must_react_lambda,
        "selected_action_key": selected_action_key,
        "response_keys": resp_keys,
        "response_weights": [float(w) for w in response_weights],
        "teacher_best_action_keys": [],
        "candidates": [
            {
                "action_key": c.candidate_id,
                "exported_aggregate_score": float(c.aggregate_score),
                "response_scores": [float(x) for x in c.score_vector],
            }
            for c in ([] if trace is None else trace.candidates)
        ],
    }
    validate_agg_row(row)
    return row


_REQUIRED_AGG_FIELDS = frozenset({
    "agg_trace_schema_version", "battle_id", "seed_index", "decision_index", "our_side",
    "config_id", "config_hash", "schedule_hash", "format_id", "git_sha",
    "response_keys", "response_weights", "teacher_best_action_keys", "candidates",
})
_NULLABLE_AGG_FIELDS = frozenset({
    "game_mode", "aggregation_mode", "risk_lambda", "must_react_lambda", "selected_action_key",
    "turn_number",
})
_CANDIDATE_FIELDS = frozenset({"action_key", "exported_aggregate_score", "response_scores"})


def validate_agg_row(row: dict) -> None:
    """Fail-closed schema + invariant check.

    ``response_weights`` may be EMPTY even when ``response_keys`` is
    non-empty -- that is the real, common "unweighted" case (see
    ``battle/decision.py``: ``trace.opponent_response_weights = resp_weights
    or []`` whenever ``priors`` is not supplied). This mirrors
    ``battle/policy.py::aggregate_scores``'s own ``use_weights`` guard, which
    treats an empty/mismatched weights list as "no weights" rather than an
    error. When ``response_weights`` IS populated it must be parallel to
    ``response_keys``.
    """
    missing = _REQUIRED_AGG_FIELDS - set(row)
    unknown = set(row) - _REQUIRED_AGG_FIELDS - _NULLABLE_AGG_FIELDS
    if missing or unknown:
        raise AggTraceError(f"agg-trace fields missing={sorted(missing)} unknown={sorted(unknown)}")
    if row["agg_trace_schema_version"] != AGG_TRACE_SCHEMA_VERSION:
        raise AggTraceError("unknown agg-trace schema version")

    for key in ("seed_index", "decision_index"):
        if not isinstance(row[key], int) or isinstance(row[key], bool) or row[key] < 0:
            raise AggTraceError(f"{key} must be a non-negative int")

    # turn_number is ADDITIVE (2c-Slice-0b bugfix) -- unlike the other nullable fields above,
    # an OLD row may be missing the key entirely (not even `null`); `.get()` treats that the
    # same as an explicit `null`. When present and non-null it must be a non-negative int,
    # mirroring the seed_index/decision_index check.
    turn_number = row.get("turn_number")
    if turn_number is not None and (
        not isinstance(turn_number, int) or isinstance(turn_number, bool) or turn_number < 0
    ):
        raise AggTraceError("turn_number must be a non-negative int or null")

    for key in ("risk_lambda", "must_react_lambda"):
        val = row[key]
        if val is not None and not _finite(val):
            raise AggTraceError(f"{key} must be finite or null")

    response_keys = row["response_keys"]
    if not isinstance(response_keys, list) or not all(isinstance(k, str) for k in response_keys):
        raise AggTraceError("response_keys must be a list of str")

    response_weights = row["response_weights"]
    if not isinstance(response_weights, list) or not all(_finite(w) for w in response_weights):
        raise AggTraceError("response_weights must be a list of finite numbers")
    if len(response_weights) not in (0, len(response_keys)):
        raise AggTraceError(
            f"response_weights length {len(response_weights)} must be 0 (unweighted) "
            f"or match response_keys length {len(response_keys)}"
        )

    teacher_keys = row["teacher_best_action_keys"]
    if not isinstance(teacher_keys, list) or not all(isinstance(k, str) for k in teacher_keys):
        raise AggTraceError("teacher_best_action_keys must be a list of str")

    candidates = row["candidates"]
    if not isinstance(candidates, list):
        raise AggTraceError("candidates must be a list")
    seen_action_keys = set()
    for candidate in candidates:
        if set(candidate) != _CANDIDATE_FIELDS:
            raise AggTraceError(f"candidate fields must be exactly {sorted(_CANDIDATE_FIELDS)}")
        action_key = candidate["action_key"]
        if not isinstance(action_key, str) or not action_key:
            raise AggTraceError("candidate action_key must be a non-empty str")
        if action_key in seen_action_keys:
            raise AggTraceError(f"duplicate candidate action_key: {action_key!r}")
        seen_action_keys.add(action_key)
        if not _finite(candidate["exported_aggregate_score"]):
            raise AggTraceError("exported_aggregate_score must be finite")
        scores = candidate["response_scores"]
        if not isinstance(scores, list) or not all(_finite(s) for s in scores):
            raise AggTraceError("response_scores must be a list of finite numbers")
        if len(scores) != len(response_keys):
            raise AggTraceError(
                f"response_scores length {len(scores)} != response_keys length {len(response_keys)}"
            )


# ---------------------------------------------------------------------------
# Writer / loader -- mirrors eval/decision_capture.py::DecisionTraceWriter /
# load_decision_trace exactly (same gzip-aware I/O, per-battle dedup key,
# count+sha256 binding, fail-closed validation on write and on load).
# ---------------------------------------------------------------------------

def _open_text(path, mode: str):
    path = Path(path)
    return gzip.open(path, mode + "t", encoding="utf-8", newline="\n") \
        if path.suffix == ".gz" else open(path, mode, encoding="utf-8", newline="\n")


class AggTraceWriter:
    def __init__(self, path):
        self.path = Path(path)
        if self.path.exists() and self.path.stat().st_size:
            raise AggTraceError(f"agg-trace output must be missing or empty: {self.path}")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._keys = set()
        self._lines_by_battle = {}
        self._errors_by_battle = {}

    def write(self, row: dict) -> None:
        battle_id = str(row.get("battle_id", ""))
        try:
            validate_agg_row(row)
            key = (battle_id, row["decision_index"], row["our_side"])
            if key in self._keys:
                raise AggTraceError(f"duplicate decision key: {key!r}")
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
            raise AggTraceError(f"battle {battle_id} capture errors: {errors}")
        lines = self._lines_by_battle.get(battle_id, [])
        if not lines:
            raise AggTraceError(f"battle {battle_id} has no agg-trace rows")
        return {
            "agg_trace_count": len(lines),
            "agg_trace_sha256": hashlib.sha256(b"".join(lines)).hexdigest(),
        }


def load_agg_trace(path) -> list[dict]:
    rows = []
    with _open_text(path, "r") as fh:
        for line_number, line in enumerate(fh, 1):
            try:
                row = json.loads(line)
                validate_agg_row(row)
            except Exception as exc:
                raise AggTraceError(f"{path}:{line_number}: {exc}") from exc
            rows.append(row)
    return rows
