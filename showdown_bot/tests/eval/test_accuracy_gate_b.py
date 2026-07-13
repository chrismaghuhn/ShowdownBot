from __future__ import annotations

import pytest

from showdown_bot.battle.decision_trace import (
    AccuracyEventTrace,
    AccuracyResponseDetail,
    AccuracyTieOrderTrace,
    CandidateTrace,
    DecisionTrace,
)
from showdown_bot.eval.accuracy_gate_b import (
    GateBResult,
    _chosen_candidate,
    candidate_any_cap_hit,
    candidate_events_complete,
    pair_candidates_by_id,
    run_gate_b,
)


def _detail(*, cap_hits: int, complete: bool, tie_orders: list[AccuracyTieOrderTrace] | None = None) -> AccuracyResponseDetail:
    return AccuracyResponseDetail(
        accuracy_leaf_count=4, accuracy_event_count=1, accuracy_branch_cap_hits=cap_hits,
        events_complete=complete, tie_orders=tie_orders or [], events=[],
    )


def _candidate(candidate_id: str, rank: int, score: float, details: list[AccuracyResponseDetail]) -> CandidateTrace:
    return CandidateTrace(
        candidate_id=candidate_id, joint_action=None, rank=rank, aggregate_score=score,
        score_vector=[score] * len(details), outcome_breakdowns=[], aggregate_breakdown=None,
        accuracy_details=details,
    )


def test_any_response_cap_hit_true_when_only_second_response_capped():
    # Response 0 clean, response 1 capped -- the OR rule must still flag the candidate.
    c = _candidate("A", 0, 1.0, [_detail(cap_hits=0, complete=True), _detail(cap_hits=1, complete=False)])
    assert candidate_any_cap_hit(c) is True
    assert candidate_events_complete(c) is False  # NOT complete, because response 1 isn't


def test_any_response_cap_hit_false_when_all_responses_clean():
    c = _candidate("A", 0, 1.0, [_detail(cap_hits=0, complete=True), _detail(cap_hits=0, complete=True)])
    assert candidate_any_cap_hit(c) is False
    assert candidate_events_complete(c) is True


def test_any_tie_order_cap_hit_is_already_folded_into_accuracy_branch_cap_hits():
    # A response whose OWN accuracy_branch_cap_hits is 2 (summed across two tie orders, one of
    # which capped) must still trip the any-response rule -- proving the "any tie order" case
    # is already covered by reading accuracy_branch_cap_hits directly, per Task 6's wiring.
    tie_orders = [
        AccuracyTieOrderTrace(tie_order="ours_first", weight=0.5, accuracy_leaf_count=2,
                                accuracy_branch_cap_hits=0, events_complete=True),
        AccuracyTieOrderTrace(tie_order="ours_last", weight=0.5, accuracy_leaf_count=2,
                                accuracy_branch_cap_hits=1, events_complete=False),
    ]
    detail = _detail(cap_hits=1, complete=False, tie_orders=tie_orders)  # summed: 0 + 1 = 1
    c = _candidate("A", 0, 1.0, [detail])
    assert candidate_any_cap_hit(c) is True
    assert any(t.accuracy_branch_cap_hits >= 1 for t in c.accuracy_details[0].tie_orders)


def test_chosen_candidate_falls_back_across_tera_suffix_mismatch():
    """Regression test for a real, confirmed pre-existing decision.py bug (found during Task 4):
    _maybe_tera can overlay a Tera flag onto the chosen line AFTER trace.candidates was already
    built from the pre-Tera candidate set, so trace.chosen_candidate_id can carry a ' tera' suffix
    matching no candidate_id verbatim. _chosen_candidate must recover via the tera-stripped
    fallback match (the same proven pattern Task 4's accuracy_baseline.py driver already
    validated against a real occurrence), not silently misbehave."""
    trace = DecisionTrace(
        chosen_candidate_id="(protect, moonblast->1 tera)",  # note the ' tera' suffix
        candidates=[
            _candidate("(protect, moonblast->1)", 0, 5.0, [_detail(cap_hits=0, complete=True)]),
            _candidate("(protect, shadowball->1)", 1, 3.0, [_detail(cap_hits=0, complete=True)]),
        ],
    )
    resolved = _chosen_candidate(trace)
    assert resolved.candidate_id == "(protect, moonblast->1)"


def test_chosen_candidate_raises_when_unresolvable():
    """Fail loud, never silently None -- a silent miss here would make run_gate_b's cap-hit
    rule default to "not capped" for exactly the decisions where this occurs, silently biasing
    the gate's own verdict. This must surface as an exception (caught by run_gate_b's existing
    per-decision try/except and reported), not disappear into a false negative."""
    trace = DecisionTrace(
        chosen_candidate_id="(this matches nothing, not even stripped)",
        candidates=[
            _candidate("(protect, moonblast->1)", 0, 5.0, [_detail(cap_hits=0, complete=True)]),
        ],
    )
    with pytest.raises(RuntimeError):
        _chosen_candidate(trace)


def test_chosen_candidate_raises_on_ambiguous_label_not_first_match_wins():
    """Blocking finding from code review, independently confirmed against decision.py's real
    _label_ja source: it renders every NON-move slot action as the bare string sa.kind (e.g.
    "switch"), with NO target-mon info. Two structurally different joint actions that switch to
    DIFFERENT benched mons in the same slot (with the same other-slot action) can therefore
    render byte-identical candidate_id labels -- both "(switch, pass)" here. Their boards, and
    therefore their accuracy telemetry, can genuinely differ (candidate c1 is clean, c2 is
    capped), so a first-match-wins resolution would silently read the WRONG candidate's cap-hit
    status into the gate's headline statistic. _chosen_candidate must raise, not silently return
    whichever of the two happens to appear first in trace.candidates."""
    c1 = _candidate("(switch, pass)", 0, 5.0, [_detail(cap_hits=0, complete=True)])
    c2 = _candidate("(switch, pass)", 1, 4.0, [_detail(cap_hits=1, complete=False)])
    trace = DecisionTrace(chosen_candidate_id="(switch, pass)", candidates=[c1, c2])
    with pytest.raises(RuntimeError):
        _chosen_candidate(trace)


def test_pair_candidates_by_id_excludes_ambiguous_labels_rather_than_mispairing():
    """The same _label_ja switch-collision the _chosen_candidate regression test covers also
    threatens pair_candidates_by_id's dict-comprehension construction, which would otherwise
    silently collapse a collision to whichever duplicate is last in list order -- risking a
    wrong pairing or a spurious entered/left top-K entry in the spec Sec.5 diff schema. Unlike
    _chosen_candidate (which raises, since it resolves the ONE headline-numerator-affecting
    candidate), pair_candidates_by_id excludes ambiguous ids from its output instead: this
    function's output is investigative-only, and it runs inside run_gate_b's SAME per-decision
    try/except that the headline cap-hit numerator is recorded from, so raising here would drop
    an otherwise-valid decision's cap-hit contribution too. The ambiguous id must appear in
    NONE of paired/entered_top_k/left_top_k -- never silently guessed."""
    off_trace = DecisionTrace(candidates=[
        _candidate("(switch, pass)", 0, 5.0, [_detail(cap_hits=0, complete=True)]),  # -> mon X
        _candidate("(switch, pass)", 1, 4.0, [_detail(cap_hits=0, complete=True)]),  # -> mon Y
        _candidate("A", 2, 1.0, [_detail(cap_hits=0, complete=True)]),
    ])
    on_trace = DecisionTrace(candidates=[
        _candidate("(switch, pass)", 0, 6.0, [_detail(cap_hits=0, complete=True)]),
        _candidate("A", 1, 2.0, [_detail(cap_hits=0, complete=True)]),
    ])
    paired, entered, left = pair_candidates_by_id(off_trace, on_trace)
    assert "(switch, pass)" not in paired
    assert "(switch, pass)" not in entered
    assert "(switch, pass)" not in left
    assert set(paired) == {"A"}


def test_pair_candidates_by_id_stable_across_reordering():
    # accuracy_mode changing scores can reorder rank -- candidate_id pairing must not care.
    off_trace = DecisionTrace(candidates=[
        _candidate("A", 0, 5.0, [_detail(cap_hits=0, complete=True)]),
        _candidate("B", 1, 3.0, [_detail(cap_hits=0, complete=True)]),
    ])
    on_trace = DecisionTrace(candidates=[
        _candidate("B", 0, 6.0, [_detail(cap_hits=0, complete=True)]),  # B now ranks first
        _candidate("A", 1, 4.0, [_detail(cap_hits=1, complete=False)]),
    ])
    paired, entered, left = pair_candidates_by_id(off_trace, on_trace)
    assert set(paired) == {"A", "B"}
    off_a, on_a = paired["A"]
    assert off_a.rank == 0 and on_a.rank == 1  # correctly paired despite rank flip
    assert entered == [] and left == []


def test_pair_candidates_detects_entered_and_left_top_k():
    off_trace = DecisionTrace(candidates=[
        _candidate("A", 0, 5.0, [_detail(cap_hits=0, complete=True)]),
        _candidate("C", 1, 1.0, [_detail(cap_hits=0, complete=True)]),  # drops out on-run
    ])
    on_trace = DecisionTrace(candidates=[
        _candidate("A", 0, 5.0, [_detail(cap_hits=0, complete=True)]),
        _candidate("D", 1, 4.5, [_detail(cap_hits=0, complete=True)]),  # newly enters top-K
    ])
    paired, entered, left = pair_candidates_by_id(off_trace, on_trace)
    assert set(paired) == {"A"}
    assert entered == ["D"]
    assert left == ["C"]


def test_incomplete_event_list_never_reported_as_fully_explained():
    """Spec Sec.4: if events_complete is False, mechanically_explained must be False -- a
    diff whose event list is known-partial must never claim a complete explanation."""
    from showdown_bot.eval.room_raw_replay import ExtractedDecision, RequestKind

    from showdown_bot.eval.accuracy_gate_b import _diff_row_from_traces

    off_trace = DecisionTrace(chosen_candidate_id="A", candidates=[
        _candidate("A", 0, 5.0, [_detail(cap_hits=0, complete=True)]),
        _candidate("B", 1, 4.0, [_detail(cap_hits=0, complete=True)]),
    ])
    on_trace = DecisionTrace(chosen_candidate_id="B", candidates=[
        _candidate("B", 0, 6.0, [_detail(cap_hits=1, complete=False)]),  # capped, incomplete
        _candidate("A", 1, 4.0, [_detail(cap_hits=0, complete=True)]),
    ])
    row = _diff_row_from_traces(
        request_hash="req0", off_action="/choose move 1, move 1|rqid",
        on_action="/choose move 2, move 1|rqid", off_trace=off_trace, on_trace=on_trace,
        request=None,
    )
    assert row.events_complete is False
    assert row.mechanically_explained is False


def test_run_gate_b_reports_dropped_or_excluded_decisions_explicitly():
    from showdown_bot.eval.room_raw_replay import ExtractedDecision, RequestKind

    decisions = [
        ExtractedDecision(
            state=None, request=None, kind=RequestKind.TEAM_PREVIEW, side="p1", turn=0,
            request_hash="tp0", log_prefix_hash="p0", _debug_prefix_line_count=1,
        ),
        ExtractedDecision(
            state=None, request=None, kind=RequestKind.FORCE_SWITCH, side="p1", turn=3,
            request_hash="fs0", log_prefix_hash="p1", _debug_prefix_line_count=1,
        ),
    ]
    result = run_gate_b(decisions=decisions, battle_id_for=lambda d: "game0")
    assert result.excluded_team_preview_count == 1
    assert result.excluded_force_switch_count == 1
    assert result.n_decisions_compared == 0


def test_run_gate_b_end_to_end_on_the_conftest_fixture_board(decision_fixture, monkeypatch):
    """Proves run_gate_b's real heuristic_choose_for_request(trace=...) wiring connects, using
    this project's existing decision_fixture/fake-backend convention (same one
    tests/test_accuracy_mode_wiring.py already uses) -- not a full real-calc integration run,
    just a connectivity/shape proof."""
    from showdown_bot.eval.room_raw_replay import ExtractedDecision, RequestKind

    req, kw = decision_fixture
    decision = ExtractedDecision(
        state=kw["state"], request=req, kind=RequestKind.MOVE, side="p1", turn=1,
        request_hash="real0", log_prefix_hash="realprefix0", _debug_prefix_line_count=1,
    )
    result = run_gate_b(
        decisions=[decision], battle_id_for=lambda d: "game0",
        book=kw["book"], calc=kw["calc"], oracle_factory=lambda: kw["oracle"],
        speed_oracle=kw["speed_oracle"], dex=kw["dex"],
    )
    assert result.n_decisions_compared == 1
    assert result.acceptance.no_exceptions is True
    assert result.acceptance.exceptions == []
    assert result.cap_hit_verdict is not None


def test_trace_has_nan_score_detects_a_nan_aggregate_score():
    """Spec Sec.4's acceptance rule's 2nd part (no NaNs) needs an explicit sweep -- NaN
    arithmetic silently propagates through comparisons/sorting rather than raising, so it
    would never surface via the exceptions list on its own."""
    from showdown_bot.eval.accuracy_gate_b import _trace_has_nan_score

    clean = DecisionTrace(candidates=[_candidate("A", 0, 5.0, [_detail(cap_hits=0, complete=True)])])
    nan_trace = DecisionTrace(candidates=[
        _candidate("A", 0, float("nan"), [_detail(cap_hits=0, complete=True)]),
    ])
    assert _trace_has_nan_score(clean) is False
    assert _trace_has_nan_score(nan_trace) is True


def test_run_gate_b_reports_no_nans_false_when_a_candidate_score_is_nan(monkeypatch):
    """End-to-end proof that a NaN aggregate_score surfacing from the real
    heuristic_choose_for_request wiring gets caught in AcceptanceSummary.no_nans -- not just at
    the _trace_has_nan_score helper level. Monkeypatches accuracy_gate_b's own imported name
    (the local binding _decide_with_trace actually calls), matching the pattern
    test_accuracy_mode_wiring.py already documents for patching call sites that resolve names
    via plain module-global lookup at call time."""
    from showdown_bot.eval import accuracy_gate_b as gate_b_module
    from showdown_bot.eval.room_raw_replay import ExtractedDecision, RequestKind

    def _fake_choose(req, *, state, book, our_side, calc, oracle, speed_oracle, dex, trace=None):
        trace.chosen_candidate_id = "A"
        trace.candidates = [_candidate("A", 0, float("nan"), [_detail(cap_hits=0, complete=True)])]
        return "/choose move 1, move 1|1"

    monkeypatch.setattr(gate_b_module, "heuristic_choose_for_request", _fake_choose)
    decision = ExtractedDecision(
        state=None, request=None, kind=RequestKind.MOVE, side="p1", turn=1,
        request_hash="nan0", log_prefix_hash="nanprefix0", _debug_prefix_line_count=1,
    )
    result = run_gate_b(
        decisions=[decision], battle_id_for=lambda d: "game0",
        oracle_factory=lambda: None,
    )
    assert result.n_decisions_compared == 1
    assert result.acceptance.no_exceptions is True
    assert result.acceptance.no_nans is False
