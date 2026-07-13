"""Gate B: the confirmatory run. Replays real (state, request) pairs from the deduplicated
room_raw corpus through heuristic_choose_for_request off vs on, applies spec Sec.4's acceptance
rules, and produces the per-diff capture schema from spec Sec.5. Full deduplicated corpus only --
if infeasible, the caller reports INCONCLUSIVE/BLOCKED FOR COMPUTE, this module does not silently
sub-sample (spec Sec.6 item 6)."""

from __future__ import annotations

import copy
import os
from collections.abc import Callable
from dataclasses import dataclass, field

from showdown_bot.battle.decision import heuristic_choose_for_request
from showdown_bot.battle.decision_trace import CandidateTrace, DecisionTrace
from showdown_bot.eval.accuracy_gate_stats import Verdict, verdict_for_cap_hit_rate
from showdown_bot.eval.decision_capture import normalize_choose
from showdown_bot.eval.decision_diff import classify_action_diff
from showdown_bot.eval.room_raw_replay import ExtractedDecision, RequestKind


@dataclass(frozen=True)
class AcceptanceSummary:
    no_exceptions: bool
    exceptions: list[tuple[str, str]]  # (request_hash, error message)
    off_path_byte_identical: bool | None  # verified separately by Task 4/7's frozen-baseline
    # diff, not recomputed here -- Gate B's own job is the off-vs-on comparison, not the
    # unset-vs-explicit-off env-parser check.
    latency_within_budget: bool | None  # None if not measured in this run


@dataclass(frozen=True)
class DecisionDiffRow:
    request_hash: str
    off_chosen_action: str
    on_chosen_action: str
    off_score: float | None
    on_score: float | None
    off_margin_to_runner_up: float | None
    on_margin_to_runner_up: float | None
    tera_changed: bool
    action_diff_kind: str  # classify_action_diff's taxonomy: FALLBACK/TERA/SWITCH/PROTECT/
    # ATTACK_MOVE/ATTACK_TARGET/OTHER_ACTION
    events_complete: bool
    mechanically_explained: bool  # NEVER True when events_complete is False (spec Sec.4)
    left_top_k: list[str]      # candidate_ids present off-run, absent on-run
    entered_top_k: list[str]   # candidate_ids present on-run, absent off-run


@dataclass
class GateBResult:
    n_decisions_compared: int
    excluded_team_preview_count: int
    excluded_force_switch_count: int
    diffs: list[DecisionDiffRow] = field(default_factory=list)
    acceptance: AcceptanceSummary | None = None
    cap_hit_verdict: Verdict | None = None
    cap_hit_verdict_detail: dict = field(default_factory=dict)


def _by_rank(trace: DecisionTrace, rank: int) -> CandidateTrace | None:
    """Spec Sec.5: select by rank FIELD, never list position -- candidates aren't guaranteed
    sorted by construction alone (see decision_trace.py's own rank-sortedness test)."""
    for c in trace.candidates:
        if c.rank == rank:
            return c
    return None


def _strip_tera_suffix(candidate_id: str) -> str:
    """`_label_ja` (decision.py) appends ' tera' per-slot when that slot terastallizes. Needed
    because of a confirmed pre-existing bug (found and independently verified during Task 4):
    `_maybe_tera` can overlay a Tera flag onto the chosen line AFTER `trace.candidates` was
    already built from the pre-Tera candidate set, so `trace.chosen_candidate_id` can legitimately
    contain a ' tera' suffix that matches no `candidate_id` in `trace.candidates` verbatim. Tera is
    never part of the enumerated candidate space itself, so at most one slot's suffix needs
    stripping and the stripped match is guaranteed unique when it exists -- same proof Task 4's
    `accuracy_baseline.py` driver already established and validated against a real occurrence
    (1/944 real decisions)."""
    return candidate_id.replace(" tera", "")


def _chosen_candidate(trace: DecisionTrace) -> CandidateTrace:
    """Raises RuntimeError (not silently returns None) if no candidate matches -- a silent
    None here would make `run_gate_b`'s cap-hit rule default to "not capped" for exactly the
    decisions where a Tera-related mismatch occurred, silently biasing the gate's own verdict.
    Fail loud instead; `run_gate_b`'s existing per-decision try/except already turns this into
    a reported exception rather than crashing the whole run."""
    for c in trace.candidates:
        if c.candidate_id == trace.chosen_candidate_id:
            return c
    stripped_target = _strip_tera_suffix(trace.chosen_candidate_id or "")
    fallback = [c for c in trace.candidates if _strip_tera_suffix(c.candidate_id) == stripped_target]
    if len(fallback) == 1:
        return fallback[0]
    raise RuntimeError(
        f"no candidate matches chosen_candidate_id={trace.chosen_candidate_id!r} "
        f"(exact or tera-stripped); found {len(fallback)} stripped matches, expected exactly 1 -- "
        f"candidate_ids present: {[c.candidate_id for c in trace.candidates]}"
    )


def candidate_any_cap_hit(candidate: CandidateTrace) -> bool:
    """Spec Sec.4's numerator rule: ANY of the candidate's scored opponent-response
    accuracy_details has accuracy_branch_cap_hits >= 1. That field is already summed across
    BOTH evaluated tie orderings when a response was scored under a genuine tie (Task 5/6's
    wiring), so this single flat check already covers "any response, any tie order" -- no
    separate nested tie-order loop is needed here."""
    return any(d.accuracy_branch_cap_hits >= 1 for d in candidate.accuracy_details)


def candidate_events_complete(candidate: CandidateTrace) -> bool:
    """True only if EVERY scored response's event list is complete (no branch_cap truncation
    anywhere for this candidate) -- False if any single response is incomplete."""
    return all(d.events_complete for d in candidate.accuracy_details)


def pair_candidates_by_id(
    off_trace: DecisionTrace, on_trace: DecisionTrace,
) -> tuple[dict[str, tuple[CandidateTrace, CandidateTrace]], list[str], list[str]]:
    """Spec Sec.5: off-run and on-run candidates for the "same" nominal action are paired by
    candidate_id, never by rank or list position -- accuracy_mode can reorder or reshuffle
    top-K membership. Returns (paired_by_id, entered_top_k, left_top_k), both sorted lists."""
    off_by_id = {c.candidate_id: c for c in off_trace.candidates}
    on_by_id = {c.candidate_id: c for c in on_trace.candidates}
    common = set(off_by_id) & set(on_by_id)
    left_top_k = sorted(set(off_by_id) - set(on_by_id))
    entered_top_k = sorted(set(on_by_id) - set(off_by_id))
    paired = {cid: (off_by_id[cid], on_by_id[cid]) for cid in common}
    return paired, entered_top_k, left_top_k


def _diff_row_from_traces(
    *, request_hash: str, off_action: str, on_action: str,
    off_trace: DecisionTrace, on_trace: DecisionTrace, request,
) -> DecisionDiffRow:
    _paired, entered_top_k, left_top_k = pair_candidates_by_id(off_trace, on_trace)
    off_top = _by_rank(off_trace, 0)
    on_top = _by_rank(on_trace, 0)
    off_runner_up = _by_rank(off_trace, 1)
    on_runner_up = _by_rank(on_trace, 1)
    on_chosen = _chosen_candidate(on_trace)  # raises if unresolvable; never silently None
    events_complete = candidate_events_complete(on_chosen)

    off_norm = normalize_choose(off_action.split("|", 1)[0].strip(), request) if request else {"kind": "joint", "slots": []}
    on_norm = normalize_choose(on_action.split("|", 1)[0].strip(), request) if request else {"kind": "joint", "slots": []}
    action_diff = classify_action_diff(off_norm, on_norm)

    return DecisionDiffRow(
        request_hash=request_hash, off_chosen_action=off_action, on_chosen_action=on_action,
        off_score=off_top.aggregate_score if off_top else None,
        on_score=on_top.aggregate_score if on_top else None,
        off_margin_to_runner_up=(
            off_top.aggregate_score - off_runner_up.aggregate_score
            if off_top and off_runner_up else None
        ),
        on_margin_to_runner_up=(
            on_top.aggregate_score - on_runner_up.aggregate_score
            if on_top and on_runner_up else None
        ),
        tera_changed="tera_changed" in action_diff.markers,
        action_diff_kind=action_diff.primary,
        events_complete=events_complete,
        mechanically_explained=events_complete,  # spec Sec.4: never claim a complete
        # mechanical explanation when the underlying event list is known-partial
        left_top_k=left_top_k, entered_top_k=entered_top_k,
    )


def _decide_with_trace(
    decision: ExtractedDecision, *, accuracy_on: bool, book, calc, oracle_factory, speed_oracle, dex,
) -> tuple[str, DecisionTrace]:
    if accuracy_on:
        os.environ["SHOWDOWN_ACCURACY_MODE"] = "1"
    else:
        os.environ.pop("SHOWDOWN_ACCURACY_MODE", None)
    trace = DecisionTrace()
    chosen = heuristic_choose_for_request(
        decision.request, state=copy.deepcopy(decision.state), book=book, our_side=decision.side,
        calc=calc, oracle=oracle_factory(), speed_oracle=speed_oracle, dex=dex, trace=trace,
    )
    return chosen, trace


def run_gate_b(
    *,
    decisions: list[ExtractedDecision],
    battle_id_for: Callable[[ExtractedDecision], str],
    book=None, calc=None, oracle_factory=None, speed_oracle=None, dex=None,
) -> GateBResult:
    move_decisions = [d for d in decisions if d.kind == RequestKind.MOVE]
    excluded_team_preview = sum(1 for d in decisions if d.kind == RequestKind.TEAM_PREVIEW)
    excluded_force_switch = sum(1 for d in decisions if d.kind == RequestKind.FORCE_SWITCH)

    diffs: list[DecisionDiffRow] = []
    per_decision_cap_hit: list[tuple[str, bool]] = []
    per_game_any_cap_hit: dict[str, bool] = {}
    exceptions: list[tuple[str, str]] = []

    try:
        for d in move_decisions:
            game_id = battle_id_for(d)
            per_game_any_cap_hit.setdefault(game_id, False)
            try:
                off_action, off_trace = _decide_with_trace(
                    d, accuracy_on=False, book=book, calc=calc,
                    oracle_factory=oracle_factory, speed_oracle=speed_oracle, dex=dex,
                )
                on_action, on_trace = _decide_with_trace(
                    d, accuracy_on=True, book=book, calc=calc,
                    oracle_factory=oracle_factory, speed_oracle=speed_oracle, dex=dex,
                )
                # _chosen_candidate can raise RuntimeError (a real, confirmed possibility --
                # see its own docstring on the tera/trace mismatch) -- deliberately kept INSIDE
                # this try block so such a decision is recorded as a per-decision exception,
                # not an uncaught crash that would lose every already-accumulated result.
                on_chosen = _chosen_candidate(on_trace)
                cap_hit_this_decision = candidate_any_cap_hit(on_chosen)
                if off_action != on_action:
                    diff_row = _diff_row_from_traces(
                        request_hash=d.request_hash, off_action=off_action, on_action=on_action,
                        off_trace=off_trace, on_trace=on_trace, request=d.request,
                    )
                else:
                    diff_row = None
            except Exception as exc:  # noqa: BLE001
                exceptions.append((d.request_hash, str(exc)))
                continue

            per_decision_cap_hit.append((game_id, cap_hit_this_decision))
            if cap_hit_this_decision:
                per_game_any_cap_hit[game_id] = True
            if diff_row is not None:
                diffs.append(diff_row)
    finally:
        os.environ.pop("SHOWDOWN_ACCURACY_MODE", None)

    verdict, detail = verdict_for_cap_hit_rate(
        per_decision_cap_hit=per_decision_cap_hit,
        per_game_any_cap_hit=per_game_any_cap_hit,
        n_decisions=len(per_decision_cap_hit),
    )

    return GateBResult(
        n_decisions_compared=len(per_decision_cap_hit),
        excluded_team_preview_count=excluded_team_preview,
        excluded_force_switch_count=excluded_force_switch,
        diffs=diffs,
        acceptance=AcceptanceSummary(
            no_exceptions=(len(exceptions) == 0), exceptions=exceptions,
            off_path_byte_identical=None, latency_within_budget=None,
        ),
        cap_hit_verdict=verdict,
        cap_hit_verdict_detail=detail,
    )
