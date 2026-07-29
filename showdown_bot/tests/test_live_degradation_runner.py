from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from showdown_bot.client import runner
from showdown_bot.client.live_degradation import LiveDegradationRecorder

FIXTURES = Path(__file__).parent / "fixtures"
ROOM = "battle-gen9vgc2025regg-1"


def _request_payload(name: str = "request_doubles_moves.json") -> str:
    """The fixture JSON as one line. parse_message splits on '|', and the fixtures contain
    none, so a single-line payload round-trips."""
    return json.dumps(json.loads((FIXTURES / name).read_text(encoding="utf-8")))


class _StubConnection:
    """Records what the runner sent and replays a fixed frame list."""

    def __init__(self, frames: list[str]) -> None:
        self._frames = list(frames)
        self.sent: list[str] = []
        self.closed = False

    async def send(self, message: str) -> None:
        self.sent.append(message)

    async def close(self) -> None:
        self.closed = True

    async def messages(self):
        for frame in self._frames:
            yield frame


class _RaisingConnection(_StubConnection):
    async def messages(self):
        for frame in self._frames:
            yield frame
        raise RuntimeError("stream exploded")


class _CancellingConnection(_StubConnection):
    async def messages(self):
        for frame in self._frames:
            yield frame
        raise asyncio.CancelledError()


class _FakeState:
    """Stand-in for BattleState so a test controls whether the build succeeds."""


def _install_recorder(monkeypatch, tmp_path) -> LiveDegradationRecorder:
    rec = LiveDegradationRecorder.preflight(parent=tmp_path)
    monkeypatch.setattr(runner, "_recorder", rec)
    return rec


def _events_of(rec) -> list[dict]:
    """Every event the run produced, wherever it currently lives: buffered before the run-end
    flush exists, on disk afterwards."""
    path = rec.run_dir / "events.jsonl"
    on_disk = []
    if path.exists():
        on_disk = [json.loads(line) for line in
                   path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return list(rec._events) + on_disk


def _battle_rows(rec) -> list[dict]:
    path = rec.run_dir / "battles.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in
            path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _use_heuristic_path(monkeypatch, *, stage="heuristic", reason=None,
                        state_raises=False, chooser_raises=None):
    """Make handle_battle_message take the book-present branch deterministically."""
    monkeypatch.setenv("SHOWDOWN_TURN_TRACE", "0")
    monkeypatch.setattr(runner, "_active_format", "gen9vgc2025regg")
    monkeypatch.setattr(runner, "_our_spreads", None)
    monkeypatch.setattr(runner, "_opp_sets", {})
    monkeypatch.setattr(runner, "_get_book", lambda fmt: object())
    monkeypatch.setattr(runner, "_get_priors", lambda fmt: None)
    monkeypatch.setattr(runner, "_get_format_config", lambda fmt: None)

    def _from_log_text(text):
        if state_raises:
            raise ValueError("corrupt log")
        return _FakeState()

    monkeypatch.setattr(
        runner, "BattleState",
        type("_BS", (), {"from_log_text": staticmethod(_from_log_text)}))
    monkeypatch.setattr(runner, "merge_request", lambda req, state: None)

    def _choose(req, **kwargs):
        if chooser_raises is not None:
            raise chooser_raises
        sink = kwargs.get("stage_sink")
        if sink is not None:
            sink.selection_stage = stage
            sink.fallback_reason = reason
        return f"/choose default|{req.rqid}"

    monkeypatch.setattr(runner, "choose_with_fallback", _choose)


@pytest.fixture
def _clean_runner_state(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "LOG_DIR", tmp_path / "battle-logs")
    runner._battle_logs.clear()
    runner._room_raw.clear()
    runner._last_rqid.clear()
    yield
    runner._battle_logs.clear()
    runner._room_raw.clear()
    runner._last_rqid.clear()


# --- Task 9: decisions, crash re-raise, events -------------------------------


@pytest.mark.asyncio
async def test_a_clean_decision_is_recorded(tmp_path, monkeypatch):
    rec = _install_recorder(monkeypatch, tmp_path)
    _use_heuristic_path(monkeypatch)
    conn = _StubConnection([])
    await runner.handle_battle_message(conn, ROOM, _request_payload())
    row = rec._decisions[ROOM][0]
    assert row["derivation_applicable"] is True
    assert row["is_degraded"] is False and row["outcome"] == "ok"
    assert row["selection_stage"] == "heuristic"


@pytest.mark.asyncio
async def test_the_action_is_sent_before_anything_is_recorded(tmp_path, monkeypatch):
    """C11, proven by ORDER rather than by outcome: the send must already have happened when
    record_decision runs, so no recorder defect can cost the turn."""
    rec = _install_recorder(monkeypatch, tmp_path)
    _use_heuristic_path(monkeypatch)
    order: list[str] = []

    class _OrderedConnection(_StubConnection):
        async def send(self, message: str) -> None:
            order.append("send")
            await super().send(message)

    real_record = rec.record_decision

    def _tracked(**kwargs):
        order.append("record")
        return real_record(**kwargs)

    monkeypatch.setattr(rec, "record_decision", _tracked)
    conn = _OrderedConnection([])
    await runner.handle_battle_message(conn, ROOM, _request_payload())
    assert order == ["send", "record"]


@pytest.mark.asyncio
async def test_state_build_failure_is_recorded_and_is_not_state_is_none(tmp_path, monkeypatch):
    """Section 5: the raw fact is 'the build was ATTEMPTED and failed', never 'state is None'."""
    rec = _install_recorder(monkeypatch, tmp_path)
    _use_heuristic_path(monkeypatch, stage="deterministic_default_pair", state_raises=True)
    conn = _StubConnection([])
    await runner.handle_battle_message(conn, ROOM, _request_payload())
    row = rec._decisions[ROOM][0]
    assert row["state_build_failed"] is True
    assert row["is_degraded"] is True and row["outcome"] == "degraded_state"


@pytest.mark.asyncio
async def test_team_preview_is_recorded_as_not_applicable(tmp_path, monkeypatch):
    rec = _install_recorder(monkeypatch, tmp_path)
    _use_heuristic_path(monkeypatch)
    conn = _StubConnection([])
    await runner.handle_battle_message(
        conn, ROOM, _request_payload("request_team_preview.json"))
    row = rec._decisions[ROOM][0]
    assert row["team_preview"] is True
    assert row["state_build_failed"] is False
    assert row["is_degraded"] is None and row["outcome"] == "not_applicable"


@pytest.mark.asyncio
async def test_book_absent_is_recorded_as_not_applicable(tmp_path, monkeypatch):
    rec = _install_recorder(monkeypatch, tmp_path)
    monkeypatch.setenv("SHOWDOWN_TURN_TRACE", "0")
    monkeypatch.setattr(runner, "_get_book", lambda fmt: None)
    monkeypatch.setattr(runner, "choose_for_request",
                        lambda req: f"/choose default|{req.rqid}")
    conn = _StubConnection([])
    await runner.handle_battle_message(conn, ROOM, _request_payload())
    row = rec._decisions[ROOM][0]
    assert row["book_absent"] is True
    assert row["is_degraded"] is None and row["outcome"] == "not_applicable"


@pytest.mark.asyncio
async def test_chooser_exception_is_recorded_then_re_raised(tmp_path, monkeypatch):
    """C5: the chooser call is unguarded today, so the exception propagates. Adding a
    default-choose fallback here would change what the bot DOES, not what it records."""
    rec = _install_recorder(monkeypatch, tmp_path)
    _use_heuristic_path(monkeypatch, chooser_raises=ValueError("boom"))
    conn = _StubConnection([])
    with pytest.raises(ValueError, match="boom"):
        await runner.handle_battle_message(conn, ROOM, _request_payload())
    row = rec._decisions[ROOM][0]
    assert row["agent_crash_type"] == "ValueError"
    assert row["outcome"] == "crash" and row["is_degraded"] is True
    assert conn.sent == []          # nothing was chosen, so nothing was sent


@pytest.mark.asyncio
async def test_cancellation_in_the_chooser_is_not_recorded_as_an_agent_crash(
        tmp_path, monkeypatch):
    """`except Exception`, NOT BaseException: CancelledError, KeyboardInterrupt and SystemExit
    are control flow, not agent crashes."""
    rec = _install_recorder(monkeypatch, tmp_path)
    _use_heuristic_path(monkeypatch, chooser_raises=asyncio.CancelledError())
    conn = _StubConnection([])
    with pytest.raises(asyncio.CancelledError):
        await runner.handle_battle_message(conn, ROOM, _request_payload())
    assert rec._decisions.get(ROOM, []) == []


@pytest.mark.asyncio
async def test_the_chosen_action_is_byte_identical_with_and_without_the_recorder(
        tmp_path, monkeypatch):
    """C5/C10: recording must not alter the action string."""
    _use_heuristic_path(monkeypatch)
    monkeypatch.setattr(runner, "_recorder", None)
    without = _StubConnection([])
    await runner.handle_battle_message(without, ROOM, _request_payload())

    _install_recorder(monkeypatch, tmp_path)
    with_rec = _StubConnection([])
    await runner.handle_battle_message(with_rec, ROOM, _request_payload())

    assert with_rec.sent == without.sent
    assert len(with_rec.sent) == 1


@pytest.mark.asyncio
async def test_a_recorder_failure_after_a_successful_choice_does_not_stop_the_send(
        tmp_path, monkeypatch):
    """C11, both guarantees at once: the send has already happened when record_decision is
    called, and the call is guarded, so a recorder defect neither loses the action nor kills
    the battle."""
    rec = _install_recorder(monkeypatch, tmp_path)
    _use_heuristic_path(monkeypatch)

    def _explode(**kwargs):
        raise RuntimeError("recorder defect")

    monkeypatch.setattr(rec, "record_decision", _explode)
    conn = _StubConnection([])
    await runner.handle_battle_message(conn, ROOM, _request_payload())    # must NOT raise
    assert len(conn.sent) == 1
    assert rec.recorder_errors_total == 1
    assert rec.exit_status() != 0


@pytest.mark.asyncio
async def test_no_recorder_means_no_behaviour_change(tmp_path, monkeypatch):
    _use_heuristic_path(monkeypatch)
    monkeypatch.setattr(runner, "_recorder", None)
    conn = _StubConnection([])
    await runner.handle_battle_message(conn, ROOM, _request_payload())
    assert len(conn.sent) == 1


@pytest.mark.asyncio
async def test_server_error_records_the_real_payload_not_an_empty_string(
        tmp_path, monkeypatch, _clean_runner_state):
    """REGRESSION: parse_message fills `payload` only for prefix == 'request'
    (protocol/messages.py:26). Recording parsed.payload for |error| wrote '' every time."""
    rec = _install_recorder(monkeypatch, tmp_path)
    runner._last_rqid[ROOM] = 4
    conn = _StubConnection([
        f">{ROOM}\n|init|battle",
        f">{ROOM}\n|error|[Invalid choice] Can't move: Zamazenta needs a target",
    ])
    await runner._run_battle_loop(conn, max_battles=1, cancel_on_done=None)
    errors = [e for e in _events_of(rec) if e["event_type"] == "server_error"]
    assert len(errors) == 1
    assert errors[0]["payload"] == "[Invalid choice] Can't move: Zamazenta needs a target"
    assert errors[0]["attribution"] == "room" and errors[0]["room_id"] == ROOM


@pytest.mark.asyncio
async def test_invalid_choice_pm_with_two_active_battles_is_unattributed(
        tmp_path, monkeypatch, _clean_runner_state):
    rec = _install_recorder(monkeypatch, tmp_path)
    conn = _StubConnection([
        f">{ROOM}\n|init|battle",
        ">battle-gen9vgc2025regg-2\n|init|battle",
        "|pm| Staff|~|Invalid choice",
    ])
    await runner._run_battle_loop(conn, max_battles=5, cancel_on_done=None)
    pms = [e for e in _events_of(rec) if e["event_type"] == "invalid_choice_pm"]
    assert len(pms) == 1
    assert pms[0]["attribution"] == "unattributed" and pms[0]["room_id"] is None
    assert pms[0]["active_battle_count"] == 2


# --- Task 10: boundaries, finally, preflight call sites ----------------------


def _settings():
    from showdown_bot.config import Settings

    return Settings(
        username="tester", password="", server_url="ws://localhost:8000/showdown/websocket",
        team_path=Path("teams/fixed_team.txt"), format_id="gen9vgc2025regg")


@pytest.mark.asyncio
async def test_flush_happens_before_room_raw_is_popped(
        tmp_path, monkeypatch, _clean_runner_state):
    """Section 9: that pop is where today's evidence is thrown away."""
    rec = _install_recorder(monkeypatch, tmp_path)
    _use_heuristic_path(monkeypatch)
    conn = _StubConnection([
        f">{ROOM}\n|init|battle",
        f">{ROOM}\n|request|{_request_payload()}",
        f">{ROOM}\n|win|opponent",
    ])
    finished = await runner._run_battle_loop(conn, max_battles=1, cancel_on_done=None)
    assert finished == 1
    rows = _battle_rows(rec)
    assert len(rows) == 1
    assert rows[0]["end_reason"] == "win"
    assert rows[0]["decisions_total"] == 1        # the decision survived the pop
    assert ROOM not in runner._room_raw


@pytest.mark.asyncio
async def test_stream_end_flushes_active_rooms_as_unterminated(
        tmp_path, monkeypatch, _clean_runner_state):
    rec = _install_recorder(monkeypatch, tmp_path)
    _use_heuristic_path(monkeypatch)
    conn = _StubConnection([
        f">{ROOM}\n|init|battle",
        f">{ROOM}\n|request|{_request_payload()}",
    ])
    await runner._run_battle_loop(conn, max_battles=1, cancel_on_done=None)
    rows = _battle_rows(rec)
    assert [r["end_reason"] for r in rows] == ["unterminated"]
    assert rows[0]["decisions_total"] == 1
    assert rec.unterminated_rooms == [ROOM]


@pytest.mark.asyncio
async def test_exception_exit_flushes_active_rooms_as_unterminated(
        tmp_path, monkeypatch, _clean_runner_state):
    """A post-loop statement would be SKIPPED here -- exactly where the evidence matters."""
    rec = _install_recorder(monkeypatch, tmp_path)
    _use_heuristic_path(monkeypatch)
    conn = _RaisingConnection([
        f">{ROOM}\n|init|battle",
        f">{ROOM}\n|request|{_request_payload()}",
    ])
    with pytest.raises(RuntimeError, match="stream exploded"):
        await runner._run_battle_loop(conn, max_battles=1, cancel_on_done=None)
    assert [r["end_reason"] for r in _battle_rows(rec)] == ["unterminated"]


@pytest.mark.asyncio
async def test_the_not_ladderable_popup_still_flushes(
        tmp_path, monkeypatch, _clean_runner_state):
    """_run_battle_loop raises RuntimeError itself on this popup."""
    rec = _install_recorder(monkeypatch, tmp_path)
    _use_heuristic_path(monkeypatch)
    conn = _StubConnection([
        f">{ROOM}\n|init|battle",
        f">{ROOM}\n|request|{_request_payload()}",
        "|popup|The ladder is not ladderable right now.",
    ])
    with pytest.raises(RuntimeError, match="ladderable"):
        await runner._run_battle_loop(conn, max_battles=1, cancel_on_done=None)
    assert [r["end_reason"] for r in _battle_rows(rec)] == ["unterminated"]
    assert conn.closed is True


@pytest.mark.asyncio
async def test_cancellation_flushes_active_rooms_as_unterminated(
        tmp_path, monkeypatch, _clean_runner_state):
    rec = _install_recorder(monkeypatch, tmp_path)
    _use_heuristic_path(monkeypatch)
    conn = _CancellingConnection([
        f">{ROOM}\n|init|battle",
        f">{ROOM}\n|request|{_request_payload()}",
    ])
    with pytest.raises(asyncio.CancelledError):
        await runner._run_battle_loop(conn, max_battles=1, cancel_on_done=None)
    assert [r["end_reason"] for r in _battle_rows(rec)] == ["unterminated"]


@pytest.mark.asyncio
async def test_completion_is_written_at_run_end(
        tmp_path, monkeypatch, _clean_runner_state):
    rec = _install_recorder(monkeypatch, tmp_path)
    _use_heuristic_path(monkeypatch)
    conn = _StubConnection([
        f">{ROOM}\n|init|battle",
        f">{ROOM}\n|request|{_request_payload()}",
        f">{ROOM}\n|win|opponent",
    ])
    await runner._run_battle_loop(conn, max_battles=1, cancel_on_done=None)
    completion = json.loads((rec.run_dir / "completion.json").read_text(encoding="utf-8"))
    assert completion["battles_finished"] == 1
    assert completion["unterminated_rooms"] == []
    assert completion["preflight_ok"] is True


@pytest.mark.asyncio
async def test_run_scoped_events_are_written_at_run_end(
        tmp_path, monkeypatch, _clean_runner_state):
    rec = _install_recorder(monkeypatch, tmp_path)
    conn = _StubConnection([
        f">{ROOM}\n|init|battle",
        ">battle-gen9vgc2025regg-2\n|init|battle",
        "|pm| Staff|~|Invalid choice",
    ])
    await runner._run_battle_loop(conn, max_battles=5, cancel_on_done=None)
    events = [json.loads(line) for line in
              (rec.run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert any(e["attribution"] == "unattributed" for e in events)


@pytest.mark.asyncio
async def test_preflight_failure_aborts_before_connect(tmp_path, monkeypatch):
    """Section 10.1: the ONE place a recording failure may stop the run -- nothing has been
    played yet, so aborting costs nothing."""
    from showdown_bot.client.live_degradation import PreflightError

    connected = {"called": False}

    async def _should_not_connect(settings):
        connected["called"] = True
        raise AssertionError("connect must not be reached after a preflight failure")

    def _fail(**kwargs):
        raise PreflightError("preflight [probe]: writer probe failed")

    monkeypatch.setattr(runner.LiveDegradationRecorder, "preflight", staticmethod(_fail))
    monkeypatch.setattr(runner, "_connect_and_login", _should_not_connect)
    with pytest.raises(PreflightError):
        await runner.run_ladder_search(_settings(), max_battles=1)
    assert connected["called"] is False


@pytest.mark.asyncio
async def test_preflight_runs_for_challenge_and_smoke_too(tmp_path, monkeypatch):
    from showdown_bot.client.live_degradation import PreflightError

    def _fail(**kwargs):
        raise PreflightError("preflight [probe]: writer probe failed")

    async def _should_not_connect(settings):
        raise AssertionError("connect must not be reached after a preflight failure")

    monkeypatch.setattr(runner.LiveDegradationRecorder, "preflight", staticmethod(_fail))
    monkeypatch.setattr(runner, "_connect_and_login", _should_not_connect)
    with pytest.raises(PreflightError):
        await runner.run_challenge(_settings(), "someone", max_battles=1)
    with pytest.raises(PreflightError):
        await runner.run_smoke_battle(_settings())


@pytest.mark.asyncio
async def test_preflight_runs_before_any_search_or_utm_is_sent(tmp_path, monkeypatch):
    """Not just before connect: nothing may reach the wire before the sink is proven, or a
    /search could pair us into a battle whose evidence has nowhere to go."""
    from showdown_bot.client.live_degradation import PreflightError

    sent: list[str] = []

    class _RecordingConn(_StubConnection):
        async def send(self, message: str) -> None:
            sent.append(message)

    async def _connect(settings):
        return _RecordingConn([])

    def _fail(**kwargs):
        raise PreflightError("preflight [probe]: writer probe failed")

    monkeypatch.setattr(runner, "_connect_and_login", _connect)
    monkeypatch.setattr(runner.LiveDegradationRecorder, "preflight", staticmethod(_fail))
    with pytest.raises(PreflightError):
        await runner.run_ladder_search(_settings(), max_battles=1)
    assert sent == []
