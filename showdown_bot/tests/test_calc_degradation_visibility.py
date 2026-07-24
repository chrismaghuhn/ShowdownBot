"""Make a DEGRADED run impossible to count as a clean one (Gate B finding 4).

Established defect this file closes, recorded on `main` in
`docs/projects/champions/audits/2026-07-24-b1-live-verification-and-gate-integrity-findings.md`:
`choose_with_fallback`'s chain (`heuristic_error -> max_damage_error ->
deterministic_default_pair -> server_default`) logs a warning and returns a LEGAL move, so no
exception propagates. `crashes` counts exceptions escaping `agent_choose` and none fly;
`calc_backend` on the arm manifest is derived from CONFIGURATION, so it records intent, never that
anything was computed. A 30-battle run with the calc backend dead therefore produced
`invalid_choices=0`, `crashes=0` and 30 clean rows -- a gate run would have published a
valid-looking verdict for a bot that never calculated a damage roll.

The fix is deliberately NOT to remove the fallback chain: a bot that returns a legal default beats
one that dies mid-battle. It is to make the degradation VISIBLE on the result row, per seat, and
refusable by the gate.
"""
from __future__ import annotations

import pytest

from showdown_bot.eval.decision_profile import (
    BASELINE_FALLBACK_STAGES,
    BASELINE_OK_STAGE,
    LIVE_FALLBACK_STAGES,
    LIVE_OK_STAGE,
    is_degraded_decision,
)


# ---------------------------------------------------------------------------------------------
# The classifier. It reuses the EXISTING selection-stage vocabulary rather than inventing a
# second one; the only addition is the baseline arm's own stages, because Gate B's Baseline B is
# `max_damage`, whose degradation happens in `agent_choose`'s own except branch and never touches
# `choose_with_fallback` at all.
# ---------------------------------------------------------------------------------------------

def _degraded(stage, *, crashed=False, state_degraded=False) -> bool:
    return is_degraded_decision(
        crashed=crashed, state_degraded=state_degraded, selection_stage=stage)


def test_the_classifier_returns_a_real_bool():
    """The remaining assertions use plain truthiness, so pin the return type once here: a
    truthy-but-not-bool return (e.g. a stage string) must not read as a verdict."""
    assert isinstance(_degraded(LIVE_OK_STAGE), bool)
    assert isinstance(_degraded("some_future_stage"), bool)


def test_the_two_intended_completion_stages_are_not_degraded():
    for stage in (LIVE_OK_STAGE, BASELINE_OK_STAGE):
        assert not _degraded(stage), stage


@pytest.mark.parametrize("stage", sorted(LIVE_FALLBACK_STAGES | BASELINE_FALLBACK_STAGES))
def test_every_fallback_stage_is_degraded(stage):
    assert _degraded(stage)


def test_a_crash_and_a_degraded_state_are_degraded_regardless_of_stage():
    """Mirrors classify_live_outcome's dominance order: the crash flag and state-is-None are
    authoritative and are classified BEFORE the stage sink, so a crash whose partial sink still
    reads 'heuristic' is never mistaken for a completed decision."""
    assert _degraded(LIVE_OK_STAGE, crashed=True)
    assert _degraded(LIVE_OK_STAGE, state_degraded=True)


def test_an_unknown_or_absent_stage_fails_CLOSED_to_degraded():
    """The whole point of the slice: never guess a decision was clean. Unlike
    classify_live_outcome -- which RAISES on an unclassifiable stage because it runs inside a
    best-effort sidecar writer -- this runs in the battle loop, where raising would kill the
    battle. It therefore fails closed to `degraded` instead."""
    for stage in (None, "", "team_preview", "some_future_stage"):
        assert _degraded(stage), stage


def test_the_baseline_stage_names_do_not_collide_with_the_live_vocabulary():
    """LIVE_* is the frozen I8-D live-profile vocabulary that `classify_live_outcome` validates
    against. Reusing one of its names for the baseline arm would silently reclassify frozen I8-D
    evidence, so the two sets must stay disjoint."""
    assert BASELINE_OK_STAGE != LIVE_OK_STAGE
    assert not (BASELINE_FALLBACK_STAGES & LIVE_FALLBACK_STAGES)
    assert BASELINE_OK_STAGE not in LIVE_FALLBACK_STAGES
    assert LIVE_OK_STAGE not in BASELINE_FALLBACK_STAGES


def test_classify_live_outcome_still_rejects_the_baseline_stages():
    """The I8-D classifier's closed vocabulary is UNCHANGED by this slice. It must keep failing
    closed on the new baseline stages, because a live profile row is only ever written for a
    heuristic agent -- if one ever appeared for `max_damage`, that is a defect, not a new
    outcome."""
    from showdown_bot.eval.decision_profile import DecisionProfileError, classify_live_outcome

    for stage in [BASELINE_OK_STAGE, *sorted(BASELINE_FALLBACK_STAGES)]:
        with pytest.raises(DecisionProfileError):
            classify_live_outcome(crashed=False, state_degraded=False, selection_stage=stage)


# ---------------------------------------------------------------------------------------------
# The sink is written on BOTH arms' paths. Gate B plays hero_agent='heuristic' (Candidate A) and
# 'max_damage' (Baseline B) -- covering only the heuristic chain would leave the baseline arm
# able to degrade invisibly, which is the same hole one level down.
# ---------------------------------------------------------------------------------------------

class _FakeRequest:
    """The only attribute agent_choose's max_damage branch reads off the request."""
    rqid = 7
    team_preview = False
    wait = False


def test_max_damage_agent_marks_the_sink_on_success(monkeypatch):
    """agent_choose's `max_damage` branch does NOT go through choose_with_fallback, so nothing
    marked its stage before this slice. Patched at the source module because the branch imports
    it locally -- no test-only parameter is added to production for this."""
    import showdown_bot.battle.baselines as baselines
    from showdown_bot.battle.decision import SelectionStageSink
    from showdown_bot.client.gauntlet import agent_choose

    calls = []
    monkeypatch.setattr(
        baselines, "max_damage_choice",
        lambda req, **kw: (calls.append(1), "/choose move 1|7")[1],
    )
    sink = SelectionStageSink()
    sentinel = object()
    choice = agent_choose(
        "max_damage", _FakeRequest(), state=sentinel, book=sentinel, our_side="p1",
        stage_sink=sink,
    )
    assert choice == "/choose move 1|7"
    assert calls == [1]
    assert sink.selection_stage == BASELINE_OK_STAGE
    assert not _degraded(sink.selection_stage)


def test_max_damage_agent_marks_the_sink_when_its_own_except_branch_fires(monkeypatch):
    """This is the baseline arm's silent-degradation path: max_damage_choice raises (e.g. the
    calc subprocess is gone), the branch swallows it and returns a legal `/choose default`."""
    import showdown_bot.battle.baselines as baselines
    from showdown_bot.battle.decision import SelectionStageSink
    from showdown_bot.client.gauntlet import agent_choose

    def _boom(req, **kw):
        raise RuntimeError("calc subprocess failed")

    monkeypatch.setattr(baselines, "max_damage_choice", _boom)
    sink = SelectionStageSink()
    sentinel = object()
    choice = agent_choose(
        "max_damage", _FakeRequest(), state=sentinel, book=sentinel, our_side="p1",
        stage_sink=sink,
    )
    assert choice == "/choose default|7"          # behaviour UNCHANGED: still a legal move
    assert sink.selection_stage in BASELINE_FALLBACK_STAGES
    assert _degraded(sink.selection_stage)


def test_max_damage_branch_tolerates_no_sink(monkeypatch):
    """stage_sink stays None for every caller that does not ask for it (the default through the
    whole chain); the branch must not start requiring one."""
    import showdown_bot.battle.baselines as baselines
    from showdown_bot.client.gauntlet import agent_choose

    monkeypatch.setattr(baselines, "max_damage_choice", lambda req, **kw: "/choose move 1|7")
    sentinel = object()
    assert agent_choose(
        "max_damage", _FakeRequest(), state=sentinel, book=sentinel, our_side="p1",
    ) == "/choose move 1|7"


# ---------------------------------------------------------------------------------------------
# The per-battle result row: per SEAT, never summed. Finding 5 recorded that `invalid_choices`
# sums hero+villain, so an opponent-seat illegal action fails the candidate and consumes a ledger
# slot with nothing on the row able to show it. The new counter must not repeat that.
# ---------------------------------------------------------------------------------------------

def test_per_battle_counters_emit_per_seat_degraded_deltas():
    from showdown_bot.client.gauntlet import _PerBattleCounters

    c = _PerBattleCounters()
    first = c.emit(invalid=0, crashes=0, latencies=[], hero_degraded=2, villain_degraded=1)
    assert first["hero_degraded_decisions"] == 2
    assert first["villain_degraded_decisions"] == 1
    # Cumulative client counters -> the SECOND battle must carry its own delta, not the total.
    second = c.emit(invalid=0, crashes=0, latencies=[], hero_degraded=5, villain_degraded=1)
    assert second["hero_degraded_decisions"] == 3
    assert second["villain_degraded_decisions"] == 0


def test_battle_result_record_carries_both_seats_separately():
    from showdown_bot.client.gauntlet import _battle_result_record

    frames = ["|player|p1|hero|", "|player|p2|villain|", "|turn|1", "|win|hero"]
    record = _battle_result_record(
        "hero", "villain", frames,
        invalid_choices=0, crashes=0, decision_latency_p95_ms=1, room_raw_path=None,
        hero_degraded_decisions=3, villain_degraded_decisions=0,
    )
    assert record["hero_degraded_decisions"] == 3
    assert record["villain_degraded_decisions"] == 0


def _valid_row() -> dict:
    return {
        "battle_id": "b0", "run_id": "r", "config_id": "heuristic",
        "format_id": "gen9championsvgc2026regma", "config_hash": "cfg", "schedule_hash": "s",
        "seed_index": 0, "opp_policy": "heuristic", "hero_team_path": "h.txt",
        "opp_team_path": "o.txt", "seed": "0", "seed_base": "b", "winner": "hero", "turns": 5,
        "invalid_choices": 0, "crashes": 0, "decision_latency_p95_ms": 10,
        "git_sha": "deadbeef", "dirty": False, "end_reason": "normal",
    }


def test_the_closed_row_schema_accepts_the_new_fields():
    from showdown_bot.eval.result_jsonl import validate_battle_row

    row = _valid_row()
    row["hero_degraded_decisions"] = 0
    row["villain_degraded_decisions"] = 4
    validate_battle_row(row)          # must not raise


def test_the_closed_row_schema_still_accepts_a_legacy_row_without_them():
    """Nullable, exactly like normalized_room_log_sha256 and decision_trace_count before it:
    rows written before this field existed must still validate."""
    from showdown_bot.eval.result_jsonl import validate_battle_row

    validate_battle_row(_valid_row())


@pytest.mark.parametrize("bad", [-1, True, 1.0, "3"])
def test_the_row_schema_rejects_a_type_wrong_degraded_count(bad):
    """Same discipline as compute_safety_pass's `_is_clean_safety_counter`: a bool is an int in
    Python and 0.0 == 0, so a type-wrong counter must be refused at the schema rather than
    silently read as clean."""
    from showdown_bot.eval.result_jsonl import ResultRowError, validate_battle_row

    row = _valid_row()
    row["hero_degraded_decisions"] = bad
    with pytest.raises(ResultRowError):
        validate_battle_row(row)


# ---------------------------------------------------------------------------------------------
# The Gate B arm must let the new fields through its closed callback whitelist, and the verdict
# path must be able to REFUSE a degraded run.
# ---------------------------------------------------------------------------------------------

def test_the_gate_b_callback_whitelist_admits_the_new_fields():
    """_CALLBACK_RECORD_FIELDS is an exact set: any unexpected OR missing field makes the arm
    refuse the battle. Adding fields to the record without adding them here would abort every
    Gate B battle, so this binds the two together."""
    from showdown_bot.eval.strength_holdout_runner import _CALLBACK_RECORD_FIELDS

    assert {"hero_degraded_decisions", "villain_degraded_decisions"} <= _CALLBACK_RECORD_FIELDS


def _gate_row(*, hero_degraded=0, villain_degraded=0) -> dict:
    row = _valid_row()
    row["hero_degraded_decisions"] = hero_degraded
    row["villain_degraded_decisions"] = villain_degraded
    return row


def test_safety_pass_refuses_a_degraded_candidate_decision():
    from showdown_bot.eval.strength_holdout_verdict import compute_safety_pass

    assert not compute_safety_pass([_gate_row(hero_degraded=1)], [_gate_row()])


def test_safety_pass_refuses_a_degraded_baseline_decision():
    """The baseline arm is half the comparison: a silently-degraded baseline makes the paired
    McNemar test measure the wrong thing just as thoroughly as a degraded candidate does."""
    from showdown_bot.eval.strength_holdout_verdict import compute_safety_pass

    assert not compute_safety_pass([_gate_row()], [_gate_row(hero_degraded=2)])


def test_safety_pass_passes_when_no_seat_degraded():
    from showdown_bot.eval.strength_holdout_verdict import compute_safety_pass

    assert compute_safety_pass([_gate_row()], [_gate_row()])


def test_safety_pass_fails_CLOSED_when_the_counter_is_absent():
    """A row with no degraded counter cannot demonstrate the bot computed anything, so it is not
    clean. Absent must never read as zero -- that is precisely how the calc-dead run passed."""
    from showdown_bot.eval.strength_holdout_verdict import compute_safety_pass

    row = _gate_row()
    del row["hero_degraded_decisions"]
    assert not compute_safety_pass([row], [_gate_row()])


@pytest.mark.parametrize("bad", [True, 1.0, "0", None, -1])
def test_safety_pass_rejects_a_type_wrong_degraded_counter(bad):
    from showdown_bot.eval.strength_holdout_verdict import compute_safety_pass

    row = _gate_row()
    row["hero_degraded_decisions"] = bad
    assert not compute_safety_pass([row], [_gate_row()])


# ---------------------------------------------------------------------------------------------
# Task 4 -- the cheap insurance: prove calc ANSWERS before battle 1, rather than discovering it
# from 180 silently-degraded rows afterwards. This does not replace the counter above (calc can
# die mid-run); it catches the common case early.
# ---------------------------------------------------------------------------------------------

def test_calc_preflight_passes_when_the_probe_returns_a_number():
    from showdown_bot.eval.strength_holdout_runner import assert_calc_answers

    class _Result:
        max_damage = 42
        error = None

    class _Calc:
        def damage(self, request):
            return _Result()

        def close(self):
            pass

    assert_calc_answers(calc_factory=lambda: _Calc())      # must not raise


@pytest.mark.parametrize("result_attrs", [
    {"max_damage": 0, "error": None},                       # answered, but with nothing
    {"max_damage": 0, "error": "ERR_MODULE_NOT_FOUND"},     # the real calc-dead signature
    {"max_damage": None, "error": None},
])
def test_calc_preflight_ABORTS_when_the_probe_does_not_answer(result_attrs):
    """Fails the run, never warns. The 30-battle calc-dead soak is the reason: it warned on every
    single decision and still produced 30 clean-looking rows."""
    from showdown_bot.eval.strength_holdout_runner import GateBAbort, assert_calc_answers

    class _Result:
        pass

    for k, v in result_attrs.items():
        setattr(_Result, k, v)

    class _Calc:
        def damage(self, request):
            return _Result()

        def close(self):
            pass

    with pytest.raises(GateBAbort):
        assert_calc_answers(calc_factory=lambda: _Calc())


def test_calc_preflight_ABORTS_when_the_backend_cannot_even_be_built():
    """`node_modules` absent, node missing, transport dead: the factory itself raises. Existence
    of node_modules is explicitly NOT the check -- only a returned number is."""
    from showdown_bot.eval.strength_holdout_runner import GateBAbort, assert_calc_answers

    def _boom():
        raise RuntimeError("ERR_MODULE_NOT_FOUND: @smogon/calc")

    with pytest.raises(GateBAbort):
        assert_calc_answers(calc_factory=_boom)


def test_calc_preflight_closes_the_probe_backend_even_when_it_fails():
    """The arm spawns one calc per battle; leaking the probe's subprocess would be a resource
    leak on the exact path the Kaggle-OOM fix exists to protect."""
    from showdown_bot.eval.strength_holdout_runner import GateBAbort, assert_calc_answers

    closed = []

    class _Calc:
        def damage(self, request):
            raise RuntimeError("dead")

        def close(self):
            closed.append(True)

    with pytest.raises(GateBAbort):
        assert_calc_answers(calc_factory=lambda: _Calc())
    assert closed == [True]


# ---------------------------------------------------------------------------------------------
# The latency window. I8-D gates decision latency at p95 <= 1000 ms and its frozen evidence sits
# at 864.94 / 873.762 ms -- roughly 13% headroom. Per-decision work added BETWEEN the
# `time.perf_counter()` start and the `decision_latency_ms` measurement would both eat that
# headroom and make a future I8-D run incomparable with the frozen numbers. This slice's counter
# must therefore sit outside the window, and stay outside it.
# ---------------------------------------------------------------------------------------------

def test_no_degradation_work_lies_inside_the_measured_latency_window():
    """Source-level guard, deliberately: the cost being protected is a few microseconds, far
    below what a timing assertion could resolve without being flaky. What is actually checkable
    -- and what actually regressed once during this slice -- is the STATEMENT ORDER."""
    import inspect
    import re

    from showdown_bot.client.gauntlet import _Client

    src = inspect.getsource(_Client)
    start = src.index("start = time.perf_counter()")
    stop = src.index("decision_latency_ms = (time.perf_counter() - start)")
    assert start < stop
    window = src[start:stop]
    for forbidden in ("is_degraded_decision", "self.degraded"):
        assert forbidden not in window, (
            f"{forbidden!r} sits INSIDE the measured decision-latency window. I8-D gates p95 at "
            "1000 ms with frozen evidence at 864.94/873.762 ms; per-decision work added here "
            "eats that headroom and makes a future run incomparable. Move it after the "
            "decision_latency_ms measurement."
        )
    # ...and it must still actually happen, somewhere after the window -- a guard that passes
    # because the counter was deleted would be worse than no guard.
    after = src[stop:]
    assert "self.degraded += 1" in after
    assert re.search(r"is_degraded_decision\(", after)


def test_the_arm_runs_the_calc_preflight_before_battle_1(monkeypatch):
    """test_strength_holdout_runner.py neutralises the real preflight for its 32 arm call sites,
    so SOMETHING has to prove the arm still calls it -- otherwise deleting the call would leave
    the whole suite green. Source-level, because reaching the call in a real arm run would
    require a live server and a sealed panel."""
    import inspect

    from showdown_bot.eval import strength_holdout_runner as arm

    src = inspect.getsource(arm.run_strength_holdout_arm)
    assert "assert_calc_answers()" in src, (
        "run_strength_holdout_arm no longer runs the calc preflight"
    )
    # ...and it must run BEFORE any battle is played, not after the loop.
    assert src.index("assert_calc_answers()") < src.index("for key in schedule.battle_keys")


def test_the_preflight_probe_is_a_real_damage_call_not_an_existence_check():
    """Existence of node_modules / a configured calc_backend is explicitly NOT the check: a
    30-battle run already passed with node_modules absent and every decision degraded, while
    still stamping itself `calc_backend: oneshot`."""
    import ast
    import inspect
    import textwrap

    from showdown_bot.eval.strength_holdout_runner import assert_calc_answers

    tree = ast.parse(textwrap.dedent(inspect.getsource(assert_calc_answers)))
    fn = tree.body[0]
    # Drop the docstring: it EXPLAINS why existence checks are wrong and therefore names them.
    # Checking the prose instead of the code would fail on a correct implementation.
    body = fn.body[1:] if ast.get_docstring(fn) else fn.body
    code = chr(10).join(ast.unparse(node) for node in body)
    assert ".damage(" in code
    assert "DamageRequest" in code
    for existence_check in ("node_modules", "os.path.exists", "shutil.which"):
        assert existence_check not in code, existence_check


# ---------------------------------------------------------------------------------------------
# Both seats block a verdict, for DIFFERENT reasons -- and must stay distinguishable. Collapsing
# them into one number would be finding 5 all over again in a brand-new field.
# ---------------------------------------------------------------------------------------------

def test_safety_pass_refuses_a_degraded_villain_decision():
    """A degraded opponent means the environment was not the one the schedule specified: the
    opponent the candidate actually faced is not the opponent recorded on the row."""
    from showdown_bot.eval.strength_holdout_verdict import compute_safety_pass

    assert not compute_safety_pass([_gate_row(villain_degraded=1)], [_gate_row()])
    assert not compute_safety_pass([_gate_row()], [_gate_row(villain_degraded=1)])


def test_safety_pass_fails_CLOSED_when_the_villain_counter_is_absent():
    from showdown_bot.eval.strength_holdout_verdict import compute_safety_pass

    row = _gate_row()
    del row["villain_degraded_decisions"]
    assert not compute_safety_pass([row], [_gate_row()])


def test_the_two_seats_are_never_summed_into_one_number():
    """Finding 5 is `invalid_choices = hero.invalid + villain.invalid`: one number that cannot be
    attributed, so an opponent-seat violation fails the candidate invisibly. The degraded
    counters must not repeat it -- each seat keeps its own field end to end, and each blocks on
    its own."""
    hero_only = _gate_row(hero_degraded=1, villain_degraded=0)
    villain_only = _gate_row(hero_degraded=0, villain_degraded=1)
    # Distinguishable on the row itself -- which is where attribution has to survive.
    assert hero_only["hero_degraded_decisions"] != hero_only["villain_degraded_decisions"]
    assert villain_only["villain_degraded_decisions"] != villain_only["hero_degraded_decisions"]
    assert hero_only != villain_only

    from showdown_bot.eval.strength_holdout_verdict import compute_safety_pass
    assert not compute_safety_pass([hero_only], [_gate_row()])
    assert not compute_safety_pass([villain_only], [_gate_row()])

    # And no producer anywhere collapses them into a single field.
    import inspect

    from showdown_bot.client.gauntlet import _battle_result_record, _PerBattleCounters

    for fn in (_battle_result_record, _PerBattleCounters.emit):
        src = inspect.getsource(fn)
        assert "hero_degraded" in src and "villain_degraded" in src
        for summed in ("hero_degraded + villain_degraded",
                       "hero.degraded + villain.degraded",
                       "degraded_decisions\": hero_degraded + "):
            assert summed not in src, (fn.__name__, summed)
