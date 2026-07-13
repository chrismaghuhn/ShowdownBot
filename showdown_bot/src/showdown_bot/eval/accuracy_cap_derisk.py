"""Accuracy branch-cap / ambiguous-candidate de-risk study (spec:
docs/superpowers/specs/2026-07-13-accuracy-cap-derisk-design.md). Pure, unit-tested logic only --
real corpus runs live in showdown_bot/scripts/. The cap=4 gate verdict
(data/eval/accuracy-gate/gate-b-report.json) is never recomputed here; this module only supports
the auxiliary action-capture / cross-cap comparison / ambiguous-candidate diagnostic described in
the spec.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True)
class DecisionIdComponents:
    seed_base: str
    seed_index: int
    request_hash: str
    log_prefix_hash: str
    side: str
    rqid: int
    turn: int


def compute_decision_id(c: DecisionIdComponents) -> str:
    """Spec Sec.2.2's fixed schema: sha256(canonical_json([seed_base, seed_index, request_hash,
    log_prefix_hash, side, rqid, turn])). Canonical JSON here means: a fixed-order list (not a
    dict, so key-ordering ambiguity can't exist), compact separators, ensure_ascii -- deterministic
    across processes/machines by construction, not by convention."""
    payload = [
        c.seed_base, c.seed_index, c.request_hash, c.log_prefix_hash, c.side, c.rqid, c.turn,
    ]
    canonical = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class DuplicateDecisionIdError(Exception):
    pass


def assert_decision_ids_unique(decision_ids: list[str]) -> None:
    """Fail-closed uniqueness check, spec Sec.2.2 -- raise (not warn, not dedupe) the instant a
    collision is found, naming every duplicated id so the caller can investigate immediately."""
    counts = Counter(decision_ids)
    dupes = {did: n for did, n in counts.items() if n > 1}
    if dupes:
        raise DuplicateDecisionIdError(
            f"{len(dupes)} decision_id collision(s) out of {len(decision_ids)} total: {dupes}"
        )


@dataclass(frozen=True)
class ActionTableRow:
    """One row of a per-decision action-capture table (spec Sec.2.3's row schema). Resolution
    status, rank, and score are intentionally orthogonal fields, not one collapsed enum -- a
    candidate can resolve only via Tera-suffix stripping AND independently sit at a non-zero rank;
    collapsing these into a single status would force losing one fact to keep the other.

    chosen_action_raw is the untouched string from heuristic_choose_for_request (needed for Task
    6's byte-level Stage-1 reproduction check). chosen_action_canonical is normalize_choose(
    chosen_action_raw, <this decision's own real request>), computed ONCE at build time -- never
    recomputed by a comparator, which would require passing in a request and risks silently using
    the WRONG request for a different decision's action. normalize_choose returns a dict, not a
    str, so building this field must go through a deterministic, key-order-independent
    serialization (e.g. `json.dumps(..., sort_keys=True)`) -- two structurally-identical actions
    must never canonicalize to different strings due to dict key order."""
    decision_id: str
    chosen_action_raw: str
    chosen_action_canonical: str
    candidate_resolution_status: str  # exact | tera_stripped | ambiguous_label | chosen_missing | other_resolution_error
    chosen_candidate_rank: int | None
    chosen_rank_mismatch: bool | None  # True when chosen_candidate_rank not in (0, None)
    top_rank_score: float | None  # nullable: an empty/rank-corrupt trace must not drop the row
    chosen_candidate_score: float | None  # nullable: only when candidate_resolution_status resolved one


@dataclass(frozen=True)
class ActionDiffRow:
    decision_id: str
    reference_action_raw: str
    candidate_action_raw: str
    action_changed: bool
    top_rank_score_delta: float | None
    top_rank_score_changed: bool | None
    chosen_candidate_score_delta: float | None
    chosen_candidate_score_changed: bool | None
    score_comparable: bool
    score_incompatible_reason: str | None


@dataclass(frozen=True)
class ActionTableDiff:
    direction: str  # e.g. "cap4 -> cap6", "off -> cap8" -- explicit, never inferred from arg order
    rows: list[ActionDiffRow]

    @property
    def action_changed_count(self) -> int:
        return sum(1 for r in self.rows if r.action_changed)


class DecisionIdPairingError(Exception):
    pass


def compare_action_tables(
    reference_rows: list[ActionTableRow],
    candidate_rows: list[ActionTableRow],
    *,
    direction: str,
    score_comparable: bool = True,
    score_incompatible_reason: str | None = None,
) -> ActionTableDiff:
    """Spec Sec.2.4's comparator -- decision_id-paired, fail-closed, action_changed computed only
    from each row's PRE-COMPUTED chosen_action_canonical field (never influenced by score, never
    calling normalize_choose itself -- see ActionTableRow's docstring for why). Score changes
    reported separately and only when score_comparable=True (spec Sec.2.3's score-semantics rule --
    the caller decides comparability, this function enforces it rather than silently subtracting
    incompatible values). `direction` is a required, explicit label -- never inferred from which
    table is passed first."""
    if not score_comparable and not score_incompatible_reason:
        raise ValueError(
            "score_comparable=False requires a non-empty score_incompatible_reason -- "
            "silently marking scores incomparable with no stated reason is not allowed"
        )
    ref_by_id: dict[str, ActionTableRow] = {}
    for r in reference_rows:
        if r.decision_id in ref_by_id:
            raise DecisionIdPairingError(f"duplicate decision_id in reference_rows: {r.decision_id!r}")
        ref_by_id[r.decision_id] = r
    cand_by_id: dict[str, ActionTableRow] = {}
    for r in candidate_rows:
        if r.decision_id in cand_by_id:
            raise DecisionIdPairingError(f"duplicate decision_id in candidate_rows: {r.decision_id!r}")
        cand_by_id[r.decision_id] = r

    missing_from_candidate = set(ref_by_id) - set(cand_by_id)
    extra_in_candidate = set(cand_by_id) - set(ref_by_id)
    if missing_from_candidate or extra_in_candidate:
        raise DecisionIdPairingError(
            f"decision_id mismatch for direction={direction!r}: "
            f"missing_from_candidate={sorted(missing_from_candidate)} "
            f"extra_in_candidate={sorted(extra_in_candidate)}"
        )

    rows: list[ActionDiffRow] = []
    for decision_id, ref in sorted(ref_by_id.items()):
        cand = cand_by_id[decision_id]
        action_changed = ref.chosen_action_canonical != cand.chosen_action_canonical

        def _delta(a: float | None, b: float | None):
            if not score_comparable or a is None or b is None:
                return None, None
            d = b - a
            return d, (d != 0.0)

        top_delta, top_changed = _delta(ref.top_rank_score, cand.top_rank_score)
        cc_delta, cc_changed = _delta(ref.chosen_candidate_score, cand.chosen_candidate_score)

        rows.append(ActionDiffRow(
            decision_id=decision_id,
            reference_action_raw=ref.chosen_action_raw, candidate_action_raw=cand.chosen_action_raw,
            action_changed=action_changed,
            top_rank_score_delta=top_delta, top_rank_score_changed=top_changed,
            chosen_candidate_score_delta=cc_delta, chosen_candidate_score_changed=cc_changed,
            score_comparable=score_comparable,
            score_incompatible_reason=None if score_comparable else score_incompatible_reason,
        ))

    return ActionTableDiff(direction=direction, rows=rows)
