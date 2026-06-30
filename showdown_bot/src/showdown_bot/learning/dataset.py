"""Offline dataset tooling for the Phase-3 reranker (slice 2b-1).

Pure/offline: loads rollout-label JSONL, groups rows into Decisions
(keyed by (game_id, decision_id)), derives a JOINT action class from the
slot move_ids (the slot*_is_* / move_category feature flags are dead in the
2b-0 export). No model, no live behavior. split_by_game is added in Task 2.
"""
from __future__ import annotations

import gzip
from dataclasses import dataclass

from showdown_bot.engine.moves import get_move_meta, to_id, is_known_move
from showdown_bot.learning.schema import from_jsonl_line, validate_row

PROTECT_MOVE_IDS = frozenset({
    "protect", "detect", "spikyshield", "kingsshield", "banefulbunker",
    "obstruct", "silktrap", "burningbulwark", "maxguard",
})


def _open(path: str):
    return gzip.open(path, "rt", encoding="utf-8") if str(path).endswith(".gz") \
        else open(path, "rt", encoding="utf-8")


def load_rows(path: str, *, validate: bool = True) -> list[dict]:
    """Load a rollout-label JSONL (.jsonl or .jsonl.gz) into plain dict rows.
    With validate=True (default) each row is checked against the frozen schema
    via validate_row, which RAISES ValueError on a malformed row. Loader-only
    unit tests with minimal fixtures can pass validate=False."""
    rows = []
    with _open(path) as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            row = from_jsonl_line(line)
            if validate:
                try:
                    validate_row(row)
                except ValueError as e:
                    raise ValueError(f"{path}:{line_no}: schema validation failed: {e}") from e
            rows.append({"features": row.features, "metadata": row.metadata, "label": row.label})
    return rows


def action_class(row: dict, *, strict: bool = False) -> str:
    """JOINT-action class over BOTH active slots (not slot1-only).
    One of 'attack' | 'protect' | 'switch' | 'status'. A joint action's class
    is attack if it deals any damage, so the all-active-protect joints are the
    'protect' class. strict=True raises on an unknown move id."""
    f = row["features"]
    slots: list[tuple[str, str]] = []
    for s in (1, 2):
        action_type = f.get(f"slot{s}_action_type")
        move_id = f.get(f"slot{s}_move_id") or ""
        # switch first: a switch action legitimately has an empty move_id.
        if action_type == "switch" or f.get(f"slot{s}_is_switch") is True:
            slots.append(("switch", move_id))
            continue
        if action_type == "pass" or move_id in ("", "__none__"):
            continue
        mid = to_id(move_id)
        if mid in PROTECT_MOVE_IDS:
            slots.append(("protect", mid))
            continue
        if strict and not is_known_move(mid):
            raise ValueError(f"unknown move id in action_class(strict): {move_id!r}")
        slots.append(("attack" if get_move_meta(mid).is_damaging else "status", mid))
    if not slots:
        return "switch"
    if any(kind == "attack" for kind, _ in slots):
        return "attack"
    if all(kind == "protect" for kind, _ in slots):
        return "protect"
    if any(kind == "switch" for kind, _ in slots):
        return "switch"
    return "status"


@dataclass
class Decision:
    game_id: str
    decision_id: str
    rows: list[dict]  # sorted by candidate_index

    @property
    def is_multi_candidate(self) -> bool:
        return len(self.rows) > 1

    def chosen_row(self) -> dict:
        """The single heuristic-chosen candidate. Fail-fast: != 1 choice is a bug."""
        cs = [r for r in self.rows if r["label"]["chosen_by_current_heuristic"]]
        if len(cs) != 1:
            raise ValueError(
                f"decision {(self.game_id, self.decision_id)} has {len(cs)} heuristic choices")
        return cs[0]

    def teacher_best_rows(self) -> list[dict]:
        bs = [r for r in self.rows if r["label"]["teacher_best"]]
        if not bs:
            raise ValueError(
                f"decision {(self.game_id, self.decision_id)} has no teacher_best row")
        return bs

    @property
    def is_tie(self) -> bool:
        return len(self.teacher_best_rows()) > 1

    def zero_gap_nonbest_count(self) -> int:
        return sum(1 for r in self.rows
                   if not r["label"]["teacher_best"]
                   and r["label"]["value_gap_to_best"] == 0.0)


def group_decisions(rows: list[dict]) -> list[Decision]:
    """Group rows by (game_id, decision_id); sort each group by candidate_index.
    Deterministic order: by first-seen (game_id, decision_id)."""
    order: list[tuple[str, str]] = []
    buckets: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        m = r["metadata"]
        key = (m["game_id"], m["decision_id"])
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(r)
    out = []
    for key in order:
        grp = sorted(buckets[key], key=lambda r: r["metadata"]["candidate_index"])
        out.append(Decision(game_id=key[0], decision_id=key[1], rows=grp))
    return out
