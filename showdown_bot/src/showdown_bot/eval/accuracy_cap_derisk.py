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


def _strip_tera(candidate_id: str) -> str:
    # Mirrors accuracy_gate_b.py's _strip_tera_suffix exactly -- Tera is never itself a dimension
    # of the enumerated candidate space, so stripping " tera" is a safe, non-lossy normalization.
    return candidate_id.replace(" tera", "")


def _canonical_action(chosen_action: str, request) -> str:
    from showdown_bot.eval.decision_capture import DecisionCaptureError, normalize_choose

    try:
        normalized = normalize_choose(chosen_action, request)
    except DecisionCaptureError as exc:
        # This table's whole point is to keep a row -- with the real chosen_action_raw -- for
        # EVERY decision, including ones whose raw action string normalize_choose's stricter
        # doubles-shape parser rejects (e.g. a single-slot action, or any other malformed
        # /choose body). Falling back to a deterministic, still-JSON-serializable marker keeps
        # chosen_action_canonical non-empty and comparable (two identically-malformed raw
        # actions still canonicalize identically) without ever raising out of this function.
        normalized = {"kind": "unparseable", "raw": chosen_action, "error": str(exc)}
    return json.dumps(normalized, sort_keys=True)


def build_action_table_row(decision_id: str, chosen_action: str, trace, request) -> ActionTableRow:
    """Spec Sec.2.3: resolve the structurally-chosen candidate the SAME way
    accuracy_gate_b.py::_chosen_candidate does (exact match, then tera-suffix-stripped fallback),
    but NEVER raise -- report a status instead, since this table must still carry a row (with its
    real chosen_action_raw) for decisions where trace-based resolution fails, unlike run_gate_b's
    own exception path. `request` MUST be the real BattleRequest this specific decision was answered
    against -- normalize_choose is request-specific, never a shared/default value across rows."""
    canonical = _canonical_action(chosen_action, request)
    candidates = list(trace.candidates)
    top = next((c for c in candidates if c.rank == 0), None)
    top_rank_score = top.aggregate_score if top is not None else None

    def _row(status: str, rank=None, rank_mismatch=None, cc_score=None) -> ActionTableRow:
        return ActionTableRow(
            decision_id=decision_id, chosen_action_raw=chosen_action, chosen_action_canonical=canonical,
            candidate_resolution_status=status,
            chosen_candidate_rank=rank, chosen_rank_mismatch=rank_mismatch,
            top_rank_score=top_rank_score, chosen_candidate_score=cc_score,
        )

    chosen_id = trace.chosen_candidate_id
    if chosen_id is None:
        return _row("chosen_missing")

    exact = [c for c in candidates if c.candidate_id == chosen_id]
    if len(exact) == 1:
        resolved, status = exact[0], "exact"
    elif len(exact) > 1:
        return _row("ambiguous_label")
    else:
        stripped_target = _strip_tera(chosen_id)
        fallback = [c for c in candidates if _strip_tera(c.candidate_id) == stripped_target]
        if len(fallback) == 1:
            resolved, status = fallback[0], "tera_stripped"
        elif len(fallback) > 1:
            return _row("ambiguous_label")
        else:
            return _row("chosen_missing")

    return _row(status, rank=resolved.rank, rank_mismatch=(resolved.rank != 0), cc_score=resolved.aggregate_score)


@dataclass(frozen=True)
class Stage1Result:
    passed: bool
    raw_diff_decision_ids: set[str]


class Stage1ReproductionError(Exception):
    pass


def run_stage1_raw_reproduction(
    auxiliary_rows: list[ActionTableRow],
    frozen_off_actions_by_decision_id: dict[str, str],
    frozen_on_actions_for_the_20: dict[str, str],
) -> Stage1Result:
    """Spec Sec.2.3 Stage 1: raw (un-normalized) string comparison only, restricted to the
    historical 881-eligible set (callers must pre-filter both inputs to that set before calling).
    Must exactly reproduce the frozen 20 -- both WHICH decision_ids differ AND the exact historical
    on_chosen_action value for each -- any deviation raises immediately. Reproducing only the diff
    SET (without checking the actual on-value) is explicitly insufficient and was a real bug caught
    in this plan's own review."""
    aux_by_id = {r.decision_id: r for r in auxiliary_rows}
    if set(aux_by_id) != set(frozen_off_actions_by_decision_id):
        raise Stage1ReproductionError(
            f"decision_id set mismatch between auxiliary rows and frozen off-actions: "
            f"only-in-auxiliary={set(aux_by_id) - set(frozen_off_actions_by_decision_id)} "
            f"only-in-frozen={set(frozen_off_actions_by_decision_id) - set(aux_by_id)}"
        )
    raw_diff_ids = {
        did for did, off_action in frozen_off_actions_by_decision_id.items()
        if aux_by_id[did].chosen_action_raw != off_action
    }
    expected_diff_ids = set(frozen_on_actions_for_the_20)
    if raw_diff_ids != expected_diff_ids:
        raise Stage1ReproductionError(
            f"raw reproduction FAILED (diff-ID set): expected {sorted(expected_diff_ids)}, "
            f"got {sorted(raw_diff_ids)} -- unexpected={sorted(raw_diff_ids - expected_diff_ids)} "
            f"missing={sorted(expected_diff_ids - raw_diff_ids)}"
        )
    wrong_on_value = {
        did: (aux_by_id[did].chosen_action_raw, expected_on)
        for did, expected_on in frozen_on_actions_for_the_20.items()
        if aux_by_id[did].chosen_action_raw != expected_on
    }
    if wrong_on_value:
        raise Stage1ReproductionError(
            f"raw reproduction FAILED (on-action value): the diff-ID set matches, but "
            f"{len(wrong_on_value)} decision(s) reproduced a DIFFERENT wrong action than the "
            f"historically recorded one -- {wrong_on_value}"
        )
    return Stage1Result(passed=True, raw_diff_decision_ids=raw_diff_ids)


def run_stage2_semantic_diff(
    auxiliary_rows: list[ActionTableRow],
    frozen_actions_canonical_by_decision_id: dict[str, str],
) -> ActionTableDiff:
    """Spec Sec.2.3 Stage 2: only meaningful after Stage 1 passes. Canonical-field-based semantic
    diff via compare_action_tables -- answers "how many semantically distinct decisions", not "is
    this the same run". `frozen_actions_canonical_by_decision_id` must already be pre-computed
    canonical forms (see decision-id-manifest.jsonl's legacy_frozen_action_canonical field, Task 4)
    -- this function never calls normalize_choose itself."""
    frozen_rows = [
        ActionTableRow(
            decision_id=did, chosen_action_raw=canonical, chosen_action_canonical=canonical,
            candidate_resolution_status="exact",
            chosen_candidate_rank=0, chosen_rank_mismatch=False, top_rank_score=None, chosen_candidate_score=None,
        )
        for did, canonical in frozen_actions_canonical_by_decision_id.items()
    ]
    aux_by_id = {r.decision_id: r for r in auxiliary_rows if r.decision_id in frozen_actions_canonical_by_decision_id}
    return compare_action_tables(
        frozen_rows, list(aux_by_id.values()), direction="off -> cap4_auxiliary",
        score_comparable=False,
        score_incompatible_reason="legacy_frozen_score not proven equivalent (see Task 4's verified finding)",
    )


class DuplicateRequestHashError(Exception):
    pass


def build_request_hash_index(manifest_rows: list[dict]) -> dict[str, dict]:
    """Fail-closed request_hash -> manifest-row index. This plan's actual join key is
    decision_id (Sec.2.2) -- this helper exists ONLY to translate EXTERNAL request_hash-keyed
    inputs (gate-b-report.json's diffs/acceptance.exceptions, which predate decision_id) into
    decision_id space. A bare `{r["request_hash"]: r for r in manifest_rows}` dict comprehension
    would silently keep only the last row for a duplicated request_hash and drop the other,
    quietly breaking the "decision_id-joined" claim this plan makes throughout -- so this helper
    asserts `len(index) == len(manifest_rows)` and names every colliding request_hash before
    returning, rather than silently constructing a lossy index. Reused by Task 6's
    validate_cap4_auxiliary.py and Task 11's run_ambiguous_candidate_diagnostic.py -- both driver
    scripts that need to look up a manifest row by request_hash."""
    index = {r["request_hash"]: r for r in manifest_rows}
    if len(index) != len(manifest_rows):
        counts: dict[str, int] = {}
        for r in manifest_rows:
            counts[r["request_hash"]] = counts.get(r["request_hash"], 0) + 1
        dupes = {rh: n for rh, n in counts.items() if n > 1}
        raise DuplicateRequestHashError(
            f"{len(dupes)} duplicate request_hash value(s) across {len(manifest_rows)} manifest "
            f"rows -- a bare request_hash-keyed dict would silently collapse these to one row, "
            f"breaking decision_id-based joining: {dupes}"
        )
    return index


# Task 9's full-corpus latency sweep (spec Sec.2.6, driven by
# showdown_bot/scripts/run_cap_latency_sweep.py). CAPS lives here -- not duplicated in the driver
# script -- so cap_order_for_game has exactly one source of truth for what it's rotating.
CAPS = [4, 6, 8]  # cap=4 here is cap4_auxiliary, per spec Sec.2.3's explicit allowance


def cap_order_for_game(game_index: int) -> list[int]:
    """Cyclic Latin square over CAPS, keyed by game_index: rotate CAPS by game_index mod len(CAPS).
    Over any len(CAPS) consecutive game indices this guarantees each cap appears in each
    cap-order position exactly once -- a real combinatorial guarantee, not a probabilistic one.
    This is what makes Task 9's "counterbalanced by construction" claim true: a random.shuffle-based
    design (an earlier draft) only makes bias unpredictable, it doesn't bound it -- nothing stops
    one cap from landing in cap-order position 0 (measured first every time, before any
    run-specific warm state accrues) more often than the others just by chance. The caller
    (run_cap_latency_sweep.py) additionally records realized position-frequency counts and
    fail-closed asserts they differ by at most 1 before ever reporting a latency number, so
    "counterbalanced" is a verified property of the actual run, not just this function's intent."""
    n = len(CAPS)
    r = game_index % n
    return CAPS[r:] + CAPS[:r]


@dataclass(frozen=True)
class AmbiguousCaseClassification:
    primary_cause: str  # label_collision | chosen_candidate_missing | invalid_or_nonreconstructable_request | other_pipeline_error
    label_collision_subtype: str | None  # switch_target_omitted | ... (only when primary_cause == label_collision)
    companion_flags: frozenset[str]


def classify_ambiguous_case(
    *,
    chosen_candidate_id: str,
    matching_candidate_ids: list[str],
    matching_joint_actions_distinct_switch_targets: bool,
    matching_joint_actions_distinct_tera: bool,
    matching_joint_actions_distinct_move_or_target: bool,
    exact_score_tie: bool,
    collision_spans_nonzero_rank: bool,
    top_k_truncated: bool = False,
    request_reconstructable: bool = True,
    force_other_pipeline_error: bool = False,
    other_pipeline_error_rationale: str | None = None,
) -> AmbiguousCaseClassification:
    """Spec Sec.3.1's two-tier scheme. Primary cause is exactly one of 4 (5 with the optional
    other_resolution_error); companion flags are zero-or-more, independent of the primary cause.

    `collision_spans_nonzero_rank` deliberately does NOT claim anything about "the chosen
    candidate"'s rank -- this function is only ever invoked on genuinely ambiguous cases (0 or >=2
    structural matches), where there is no single candidate that can be singled out as "the chosen
    one" from the data available. It measures a real, honest, weaker property instead: whether the
    SET of matching/colliding candidates collectively includes at least one non-rank-0 entry."""
    flags: set[str] = set()
    if exact_score_tie:
        flags.add("exact_score_tie")
    if collision_spans_nonzero_rank:
        flags.add("collision_spans_nonzero_rank")
    if matching_joint_actions_distinct_switch_targets:
        flags.add("distinct_switch_targets_same_label")
    if matching_joint_actions_distinct_tera:
        flags.add("distinct_tera_state_same_label")
    if matching_joint_actions_distinct_move_or_target:
        flags.add("distinct_move_or_target_same_label")
    if top_k_truncated:
        flags.add("top_k_truncated")
    if len(matching_candidate_ids) >= 2:
        flags.add("multiple_structurally_equal_candidates")

    if force_other_pipeline_error:
        if not other_pipeline_error_rationale:
            raise ValueError("other_pipeline_error requires a concrete rationale, never a bare 'other'")
        return AmbiguousCaseClassification(
            primary_cause="other_pipeline_error", label_collision_subtype=None,
            companion_flags=frozenset(flags),
        )

    if not request_reconstructable:
        return AmbiguousCaseClassification(
            primary_cause="invalid_or_nonreconstructable_request", label_collision_subtype=None,
            companion_flags=frozenset(flags),
        )

    if len(matching_candidate_ids) == 0:
        return AmbiguousCaseClassification(
            primary_cause="chosen_candidate_missing", label_collision_subtype=None,
            companion_flags=frozenset(flags),
        )

    if len(matching_candidate_ids) >= 2:
        if matching_joint_actions_distinct_switch_targets:
            subtype = "switch_target_omitted"
        elif matching_joint_actions_distinct_tera:
            subtype = "tera_state_omitted"
        elif matching_joint_actions_distinct_move_or_target:
            subtype = "move_or_target_omitted"
        else:
            subtype = "unspecified_collision"
        return AmbiguousCaseClassification(
            primary_cause="label_collision", label_collision_subtype=subtype,
            companion_flags=frozenset(flags),
        )

    # exactly one match, none of the above -- shouldn't be reachable for a genuinely "ambiguous"
    # case, but fail with a clear reason rather than silently miscategorizing.
    raise ValueError(
        f"classify_ambiguous_case called on a non-ambiguous case (1 match, "
        f"chosen_candidate_id={chosen_candidate_id!r}) -- caller should only invoke this for "
        f"cases that genuinely failed to resolve to exactly one match on re-run (see Task 11's "
        f"reproduction check, which routes exactly-one-match re-runs to other_pipeline_error "
        f"instead of calling this function at all)."
    )
