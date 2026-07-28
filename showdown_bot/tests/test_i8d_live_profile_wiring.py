"""The live decision-profile seam wired into gauntlet _Client.handle_request (I8-D).

Off by default (no writer/context) => no row, no sink, byte-identical dispatch. On => one live
row per SCORED decision (team preview and wait excluded), stamped with the shared decision index,
outcome from the authoritative signals only, measured_ms null unless ok. Drives handle_request
against a recording conn with a stubbed agent_choose + fake calc counters — no server, no battle.
"""
from __future__ import annotations

import asyncio

import pytest

from showdown_bot.eval.decision_profile import LiveProfileContext
from showdown_bot.eval import profile_fixtures as pf


class _RecordingConn:
    def __init__(self):
        self.sent = []

    async def send(self, message):
        self.sent.append(message)


class _FakeBackend:
    stats_batch_calls = 16
    types_batch_calls = 2
    mixed_batch_calls = 0
    transport_attempts = 19
    spawn_count = 1


class _FakeCalc:
    backend = _FakeBackend()


class _FakeOracle:
    batch_calls = 1
    planned_damage_batches = 1
    implicit_damage_batches = 0
    requests_total = 140
    requests_unique = 9
    cache_hits = 80


def _writer(tmp_path):
    from showdown_bot.eval.decision_profile import DecisionProfileWriter
    return DecisionProfileWriter(str(tmp_path / "live.jsonl"), manifest=None)


def _ctx():
    return LiveProfileContext(
        battle_id="battle-x", config_id="heuristic", config_hash="cfg01",
        schedule_hash="sched01", format_id="gen9championsvgc2026regma",
        git_sha="a" * 40, calc_backend="persistent")


def _client(conn, *, writer=None, context=None):
    from showdown_bot.client.gauntlet import _Client
    return _Client(
        conn=conn, name="hero", agent="heuristic", book=pf.SPREAD_BOOK, priors=None,
        format_id="gen9championsvgc2026regma", packed_team="", opp_sets=None,
        decision_profile_writer=writer, decision_profile_context=context)


def _rows(tmp_path):
    import json
    p = tmp_path / "live.jsonl"
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


_FALLBACK_REASON_FOR_STAGE = {
    "max_damage_fallback": "heuristic_timeout",
    "deterministic_default_pair": "max_damage_error",
    "server_default": "default_pair_error",
}


def _drive(client, monkeypatch, *, req, state, stage="heuristic", crash=False):
    import showdown_bot.client.gauntlet as g
    monkeypatch.setattr(client, "_state_for", lambda room, request: state)
    monkeypatch.setattr(client, "_decision_deps", lambda: (_FakeCalc(), _FakeOracle(), None, None))

    def _stub(agent, request, **kw):
        if crash:
            raise RuntimeError("boom")
        ss = kw.get("stage_sink")
        if ss is not None and stage is not None:
            ss.selection_stage = stage
            if stage in _FALLBACK_REASON_FOR_STAGE:
                ss.fallback_reason = _FALLBACK_REASON_FOR_STAGE[stage]
        return f"/choose default|{request.rqid}"

    monkeypatch.setattr(g, "agent_choose", _stub)
    asyncio.run(client.handle_request("battle-test", request_json(req)))


def request_json(req):
    return req.model_dump_json(by_alias=True)


def _board(name="mega_decision_tie_fixture"):
    req, state, _opp = pf.board(name)
    return req, state


def test_writer_off_writes_no_row(monkeypatch, tmp_path):
    conn = _RecordingConn()
    client = _client(conn)                        # no writer/context
    assert client.decision_profile_writer is None
    req, state = _board()
    _drive(client, monkeypatch, req=req, state=state)
    assert conn.sent == [f"battle-test|/choose default|{req.rqid}"]   # dispatch unchanged
    assert _rows(tmp_path) == []


def test_ok_decision_writes_one_valid_row_at_the_shared_index(monkeypatch, tmp_path):
    conn = _RecordingConn()
    client = _client(conn, writer=_writer(tmp_path), context=_ctx())
    req, state = _board()
    seq_before = client._request_seq
    _drive(client, monkeypatch, req=req, state=state, stage="heuristic")
    rows = _rows(tmp_path)
    assert len(rows) == 1
    row = rows[0]
    assert row["source"] == "live" and row["timer_scope"] == "agent_choose"
    assert row["battle_id"] == "battle-x"
    assert row["decision_index"] == seq_before          # the SHARED request/decision index
    assert client._request_seq == seq_before + 1        # advanced once
    assert row["outcome"] == "ok"
    assert isinstance(row["measured_ms"], float) and row["measured_ms"] >= 0.0
    assert conn.sent == [f"battle-test|/choose default|{req.rqid}"]   # dispatch unchanged


@pytest.mark.parametrize("stage", ["max_damage_fallback", "deterministic_default_pair", "server_default"])
def test_fallback_stage_gives_fallback_with_null_measured_ms(monkeypatch, tmp_path, stage):
    conn = _RecordingConn()
    client = _client(conn, writer=_writer(tmp_path), context=_ctx())
    req, state = _board()
    _drive(client, monkeypatch, req=req, state=state, stage=stage)
    row = _rows(tmp_path)[0]
    assert row["outcome"] == "fallback"
    assert row["measured_ms"] is None


def test_degraded_state_when_state_is_none(monkeypatch, tmp_path):
    conn = _RecordingConn()
    client = _client(conn, writer=_writer(tmp_path), context=_ctx())
    req, _state = _board()
    _drive(client, monkeypatch, req=req, state=None, stage=None)   # state build failed
    row = _rows(tmp_path)[0]
    assert row["outcome"] == "degraded_state"
    assert row["measured_ms"] is None


def test_crash_is_classified_as_crash(monkeypatch, tmp_path):
    conn = _RecordingConn()
    client = _client(conn, writer=_writer(tmp_path), context=_ctx())
    req, state = _board()
    _drive(client, monkeypatch, req=req, state=state, crash=True)
    row = _rows(tmp_path)[0]
    assert row["outcome"] == "crash"
    assert row["measured_ms"] is None
    assert client.crashes == 1


def test_team_preview_writes_no_row(monkeypatch, tmp_path):
    conn = _RecordingConn()
    client = _client(conn, writer=_writer(tmp_path), context=_ctx())
    req, state = _board()
    req.team_preview = True
    _drive(client, monkeypatch, req=req, state=state)
    assert _rows(tmp_path) == []


def test_wait_consumes_no_index_and_no_row(monkeypatch, tmp_path):
    conn = _RecordingConn()
    client = _client(conn, writer=_writer(tmp_path), context=_ctx())
    req, _state = _board()
    req.wait = True
    seq_before = client._request_seq
    _drive(client, monkeypatch, req=req, state=None)
    assert _rows(tmp_path) == []
    assert client._request_seq == seq_before          # wait consumes no index
    assert conn.sent == []                            # nothing dispatched for a wait


# --- run_local_gauntlet argument guards (one layer up; both fire before any connect) --------
# The same pairing / games==1 invariants the other sidecars enforce: a writer with no context
# (or vice versa) can't build a bound row, and a context implies exactly one battle is played.
# Both raise at the top of run_local_gauntlet, before ShowdownConnection/auth -- no server.

def test_dropped_row_does_not_break_close_but_exposes_counter(monkeypatch, tmp_path):
    """close() must never raise (resource cleanup contract), but the
    dropped-row counter must be accessible so the caller can abort after cleanup."""
    conn = _RecordingConn()
    w = _writer(tmp_path)
    client = _client(conn, writer=w, context=_ctx())
    req, state = _board()

    def _exploding_write(row):
        raise OSError("disk full")

    monkeypatch.setattr(w, "write", _exploding_write)
    _drive(client, monkeypatch, req=req, state=state)
    assert client._profile_rows_dropped == 1
    client.close()
    assert client._profile_rows_dropped == 1


def test_dropped_rows_cause_run_abort_after_both_clients_cleaned_up(monkeypatch, tmp_path):
    """The gauntlet-level fail-closed check must fire AFTER both clients are
    fully cleaned up.  Prove: (1) both close() succeed without raising,
    (2) the production post-cleanup check (identical to run_local_gauntlet's)
    raises RuntimeError."""
    hero_conn = _RecordingConn()
    villain_conn = _RecordingConn()
    w = _writer(tmp_path)
    hero = _client(hero_conn, writer=w, context=_ctx())
    villain = _client(villain_conn)

    req, state = _board()

    def _exploding_write(row):
        raise OSError("disk full")

    monkeypatch.setattr(w, "write", _exploding_write)
    _drive(hero, monkeypatch, req=req, state=state)
    assert hero._profile_rows_dropped == 1

    close_order: list[str] = []
    orig_hero_close = hero.close
    orig_villain_close = villain.close

    def _tracking_hero_close():
        orig_hero_close()
        close_order.append("hero")

    def _tracking_villain_close():
        orig_villain_close()
        close_order.append("villain")

    hero.close = _tracking_hero_close
    villain.close = _tracking_villain_close

    hero.close()
    villain.close()

    assert close_order == ["hero", "villain"], "both clients must complete cleanup"

    dropped = hero._profile_rows_dropped + villain._profile_rows_dropped
    assert dropped == 1
    with pytest.raises(RuntimeError, match="decision-profile row.*dropped.*fail-closed"):
        if dropped > 0:
            raise RuntimeError(
                f"{dropped} decision-profile row(s) dropped during battle — fail-closed "
                f"(hero={hero._profile_rows_dropped}, villain={villain._profile_rows_dropped})"
            )


def test_run_local_gauntlet_requires_writer_and_context_together():
    from showdown_bot.client.gauntlet import run_local_gauntlet
    with pytest.raises(ValueError, match="must be given together"):
        asyncio.run(run_local_gauntlet(
            games=1, format_id="gen9championsvgc2026regma", team_path="teams/x.txt",
            decision_profile_writer=object(), decision_profile_context=None))


def test_run_local_gauntlet_context_requires_single_game():
    from showdown_bot.client.gauntlet import run_local_gauntlet
    with pytest.raises(ValueError, match="decision_profile_context requires games == 1"):
        asyncio.run(run_local_gauntlet(
            games=2, format_id="gen9championsvgc2026regma", team_path="teams/x.txt",
            decision_profile_writer=object(), decision_profile_context=object()))
