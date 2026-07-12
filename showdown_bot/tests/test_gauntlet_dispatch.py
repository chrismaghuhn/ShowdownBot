from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import pytest

from showdown_bot.client.gauntlet import GauntletStats, agent_choose
from showdown_bot.engine.belief.hypotheses import load_spread_book
from showdown_bot.engine.format_config import load_format_config
from showdown_bot.engine.state import BattleState, PokemonState
from showdown_bot.models.request import BattleRequest

FIXTURES = Path(__file__).parent / "fixtures"
CHOOSE_RE = re.compile(r"^/choose ")


def _req():
    return BattleRequest.model_validate(
        json.loads((FIXTURES / "request_doubles_moves.json").read_text())
    )


def _book():
    cfg = load_format_config("gen9vgc2025regi")
    return load_spread_book(cfg.meta_path("default_spreads"))


def _state():
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=150, max_hp=150)
    st.sides["p1"]["b"] = PokemonState(species="Rillaboom", hp=155, max_hp=155)
    st.sides["p2"]["a"] = PokemonState(species="Flutter Mane", hp=131, max_hp=131)
    st.sides["p2"]["b"] = PokemonState(species="Tornadus", hp=140, max_hp=140)
    return st


def test_agent_choose_random_without_state():
    out = agent_choose("random", _req(), state=None, book=None, our_side="p1")
    assert CHOOSE_RE.match(out)


def test_agent_choose_falls_back_when_no_state():
    # heuristic with no state should still produce a legal choice (random path)
    out = agent_choose("heuristic", _req(), state=None, book=None, our_side="p1")
    assert CHOOSE_RE.match(out)


def test_gauntlet_stats_winrate_and_p95():
    s = GauntletStats(games=4, hero_wins=3)
    assert s.winrate == 0.75
    s.latencies = [0.1, 0.2, 0.3, 0.4, 1.0]
    assert s.latency_p95() == 1.0


# ---------------------------------------------------------------------------
# 2b-2.5a Kaggle-OOM ROOT CAUSE: agent_choose never forwarded the client-owned
# calc into the live decision path, so _choose_best / max_damage_choice's
# `calc = calc or CalcClient()` spawned a fresh `node calc.mjs --server` PER
# DECISION (~70/battle, MEMTRACE v3), never closed. These tests pin the fix:
# agent_choose now threads calc/oracle/speed_oracle/dex through both the
# heuristic (choose_with_fallback) and max_damage (max_damage_choice) branches,
# and a caller-supplied calc suppresses every default construction.
# ---------------------------------------------------------------------------


class _ExplodingDep:
    """Truthy, non-None stand-in for a client-owned calc/oracle/speed_oracle/dex.
    Real use raises (so the heuristic bails through the fallback chain to a legal
    default), but because every dep is non-None the decision core never reaches
    `calc = calc or CalcClient()` -- proving the per-decision Node leak is closed
    once the deps are threaded in."""

    backend = object()

    def close(self):
        pass

    def __getattr__(self, name):
        def _raise(*a, **k):
            raise RuntimeError(f"exploding dep: {name}")

        return _raise


def test_agent_choose_threads_deps_into_choose_with_fallback(monkeypatch):
    import showdown_bot.client.gauntlet as g

    captured: dict = {}

    def _fake_cwf(req, **kw):
        captured.update(kw)
        return f"/choose default|{req.rqid}"

    monkeypatch.setattr(g, "choose_with_fallback", _fake_cwf)
    calc, oracle, speed_oracle, dex = object(), object(), object(), object()
    out = agent_choose(
        "heuristic", _req(), state=object(), book=object(), our_side="p1",
        calc=calc, oracle=oracle, speed_oracle=speed_oracle, dex=dex,
    )
    assert CHOOSE_RE.match(out)
    assert captured["calc"] is calc
    assert captured["oracle"] is oracle
    assert captured["speed_oracle"] is speed_oracle
    assert captured["dex"] is dex


def test_agent_choose_threads_deps_into_max_damage_choice(monkeypatch):
    import showdown_bot.battle.baselines as baselines

    captured: dict = {}

    def _fake_md(req, **kw):
        captured.update(kw)
        return f"/choose default|{req.rqid}"

    monkeypatch.setattr(baselines, "max_damage_choice", _fake_md)
    calc, oracle, speed_oracle = object(), object(), object()
    out = agent_choose(
        "max_damage", _req(), state=object(), book=object(), our_side="p1",
        calc=calc, oracle=oracle, speed_oracle=speed_oracle,
    )
    assert CHOOSE_RE.match(out)
    assert captured["calc"] is calc
    assert captured["oracle"] is oracle
    assert captured["speed_oracle"] is speed_oracle


def test_heuristic_with_threaded_deps_constructs_no_calc_client(monkeypatch):
    """Leak guard: driving agent_choose('heuristic') with client-owned deps must
    NOT default-construct a CalcClient anywhere on the decision path (the OOM
    root cause). A real state+book enters the heuristic; exploding deps force the
    fallback chain, which must still return a legal choice -- with ZERO
    CalcClient constructions."""
    import showdown_bot.engine.calc.client as calc_mod

    constructions: list = []
    real_init = calc_mod.CalcClient.__init__

    def _counting_init(self, *a, **k):
        constructions.append(1)
        real_init(self, *a, **k)

    monkeypatch.setattr(calc_mod.CalcClient, "__init__", _counting_init)

    dep = _ExplodingDep()
    for _ in range(2):
        out = agent_choose(
            "heuristic", _req(), state=_state(), book=_book(), our_side="p1",
            calc=dep, oracle=dep, speed_oracle=dep, dex=dep,
        )
        assert CHOOSE_RE.match(out)
    assert constructions == []  # zero default CalcClient constructions on the hot path


def test_max_damage_with_threaded_deps_constructs_no_calc_client(monkeypatch):
    """Same leak guard for the max_damage branch: a threaded calc suppresses
    max_damage_choice's `calc = calc or CalcClient()`."""
    import showdown_bot.engine.calc.client as calc_mod

    constructions: list = []
    real_init = calc_mod.CalcClient.__init__

    def _counting_init(self, *a, **k):
        constructions.append(1)
        real_init(self, *a, **k)

    monkeypatch.setattr(calc_mod.CalcClient, "__init__", _counting_init)

    dep = _ExplodingDep()
    for _ in range(2):
        out = agent_choose(
            "max_damage", _req(), state=_state(), book=_book(), our_side="p1",
            calc=dep, oracle=dep, speed_oracle=dep,
        )
        assert CHOOSE_RE.match(out)
    assert constructions == []


# ---------------------------------------------------------------------------
# 2b-4 Task 2: "heuristic_reranker" agent dispatch (client/gauntlet.py).
# `agent_choose` runs the heuristic fallback chain EXACTLY ONCE (producing
# both the choose string and a populated DecisionTrace) and, when a
# RerankerOverride is available, hands that SAME trace + choose to
# `override.override_choice(...)`. `override=None` (the default; also what a
# disabled/unavailable override resolves to at the _Client level) makes this
# branch fail-safe to the heuristic's own choose string, UNCHANGED.
# ---------------------------------------------------------------------------


class _StubOverride:
    """Records every `override_choice` call and returns a fixed string."""

    def __init__(self, result: str):
        self.result = result
        self.calls: list[dict] = []

    def override_choice(self, *, trace, state, request, heuristic_choose, our_side):
        self.calls.append(dict(
            trace=trace, state=state, request=request,
            heuristic_choose=heuristic_choose, our_side=our_side,
        ))
        return self.result


def test_agent_choose_heuristic_reranker_uses_override_when_available(monkeypatch):
    import showdown_bot.client.gauntlet as g

    cwf_calls: list = []

    def _fake_cwf(req, **kw):
        cwf_calls.append(kw)
        return "HEURISTIC_CHOOSE"

    monkeypatch.setattr(g, "choose_with_fallback", _fake_cwf)
    stub = _StubOverride("OVERRIDE_CHOOSE")

    out = agent_choose(
        "heuristic_reranker", _req(), state=_state(), book=_book(), our_side="p1",
        override=stub,
    )

    assert out == "OVERRIDE_CHOOSE"
    # The heuristic core ran EXACTLY ONCE (no double-run to get trace + choose).
    assert len(cwf_calls) == 1
    assert len(stub.calls) == 1
    # The override saw the SAME trace object the heuristic call populated, and
    # the exact heuristic choose string it produced.
    assert stub.calls[0]["trace"] is cwf_calls[0]["trace"]
    assert stub.calls[0]["heuristic_choose"] == "HEURISTIC_CHOOSE"
    assert stub.calls[0]["our_side"] == "p1"


def test_agent_choose_heuristic_reranker_falls_back_without_override(monkeypatch):
    import showdown_bot.client.gauntlet as g

    cwf_calls: list = []

    def _fake_cwf(req, **kw):
        cwf_calls.append(kw)
        return "HEURISTIC_ONLY"

    monkeypatch.setattr(g, "choose_with_fallback", _fake_cwf)

    out = agent_choose(
        "heuristic_reranker", _req(), state=_state(), book=_book(), our_side="p1",
        override=None,
    )

    assert out == "HEURISTIC_ONLY"
    assert len(cwf_calls) == 1  # still exactly one heuristic run


def test_agent_choose_heuristic_reranker_default_override_is_none(monkeypatch):
    """Omitting `override` entirely (the default) is the same fail-safe path."""
    import showdown_bot.client.gauntlet as g

    monkeypatch.setattr(g, "choose_with_fallback", lambda req, **kw: "DEFAULT_HEURISTIC")

    out = agent_choose("heuristic_reranker", _req(), state=_state(), book=_book(), our_side="p1")
    assert out == "DEFAULT_HEURISTIC"


def test_agent_choose_heuristic_reranker_threads_deps_like_heuristic(monkeypatch):
    """Leak guard parity with the heuristic branch: calc/oracle/speed_oracle/dex
    passed to agent_choose reach choose_with_fallback unchanged."""
    import showdown_bot.client.gauntlet as g

    captured: dict = {}

    def _fake_cwf(req, **kw):
        captured.update(kw)
        return "H"

    monkeypatch.setattr(g, "choose_with_fallback", _fake_cwf)
    calc, oracle, speed_oracle, dex = object(), object(), object(), object()
    out = agent_choose(
        "heuristic_reranker", _req(), state=object(), book=object(), our_side="p1",
        calc=calc, oracle=oracle, speed_oracle=speed_oracle, dex=dex,
    )
    assert out == "H"
    assert captured["calc"] is calc
    assert captured["oracle"] is oracle
    assert captured["speed_oracle"] is speed_oracle
    assert captured["dex"] is dex


def test_agent_choose_heuristic_reranker_falls_back_when_no_state():
    # Same "state is None -> random path" short-circuit as plain "heuristic".
    out = agent_choose("heuristic_reranker", _req(), state=None, book=None, our_side="p1")
    assert CHOOSE_RE.match(out)


def test_existing_heuristic_agent_unaffected_by_override_param(monkeypatch):
    """The plain "heuristic" branch never even looks at `override` -- passing one
    (as a stray/garbage value) must have zero effect (byte-unchanged contract)."""
    import showdown_bot.client.gauntlet as g

    monkeypatch.setattr(g, "choose_with_fallback", lambda req, **kw: "PLAIN_HEURISTIC")
    out = agent_choose(
        "heuristic", _req(), state=_state(), book=_book(), our_side="p1",
        override=_StubOverride("SHOULD_NEVER_BE_RETURNED"),
    )
    assert out == "PLAIN_HEURISTIC"


# ---------------------------------------------------------------------------
# 2b-4 Task 2: _Client-owned RerankerOverride build-once + env-gating.
# Mirrors the _decision_deps build-once tests in test_gauntlet_close.py.
# ---------------------------------------------------------------------------


class _FakeCalcClient:
    """Stand-in for CalcClient: no Node subprocess, exposes a `backend` the
    oracle/speed-oracle/dex bind to without further I/O."""

    def __init__(self):
        _FakeCalcClient.instances += 1
        self.backend = object()

    def close(self):
        pass


_FakeCalcClient.instances = 0


def _client(**kw):
    from showdown_bot.client.gauntlet import _Client

    defaults = dict(
        conn=object(), name="T", agent="heuristic_reranker", book=None, priors=None,
        format_id="gen9vgc2025regi", packed_team="", opp_sets={},
    )
    defaults.update(kw)
    return _Client(**defaults)


def test_reranker_override_none_when_env_off(monkeypatch):
    monkeypatch.delenv("SHOWDOWN_RERANKER_OVERRIDE", raising=False)
    c = _client()
    assert c._reranker_override() is None
    assert c._override_built is True  # attempted once (real from_env path), cached as None


def test_reranker_override_not_attempted_for_other_agents(monkeypatch):
    import showdown_bot.client.gauntlet as g

    calls: list = []

    def _counting_builder(**kw):
        calls.append(kw)
        return None

    monkeypatch.setattr(g, "_load_reranker_override_from_env", _counting_builder)
    monkeypatch.setenv("SHOWDOWN_RERANKER_OVERRIDE", "1")

    c = _client(agent="heuristic")
    assert c._reranker_override() is None
    assert calls == []  # never even consulted for a non-heuristic_reranker agent


def test_reranker_override_built_once_and_reuses_decision_dex_and_move_meta(monkeypatch):
    import showdown_bot.client.gauntlet as g
    from showdown_bot.engine.moves import _move_table

    _FakeCalcClient.instances = 0
    monkeypatch.setattr(g, "CalcClient", _FakeCalcClient)
    monkeypatch.setenv("SHOWDOWN_RERANKER_OVERRIDE", "1")

    calls: list = []
    stub = object()

    def _counting_builder(*, format_id, dex, move_meta):
        calls.append({"format_id": format_id, "dex": dex, "move_meta": move_meta})
        return stub

    monkeypatch.setattr(g, "_load_reranker_override_from_env", _counting_builder)

    c = _client(agent="heuristic_reranker", format_id="gen9vgc2025regi")
    # handle_request calls _decision_deps() BEFORE _reranker_override() every decision.
    c._decision_deps()

    first = c._reranker_override()
    second = c._reranker_override()
    third = c._reranker_override()

    assert first is stub
    assert second is stub
    assert third is stub
    assert len(calls) == 1  # built ONCE per client, not per decision
    assert calls[0]["format_id"] == "gen9vgc2025regi"
    assert calls[0]["dex"] is c._decision_dex
    assert calls[0]["dex"] is not None  # the client's OWN decision-deps dex, not a fresh one
    assert calls[0]["move_meta"] == _move_table()


def test_reranker_override_disabled_for_max_damage_and_random(monkeypatch):
    import showdown_bot.client.gauntlet as g

    calls: list = []
    monkeypatch.setattr(g, "_load_reranker_override_from_env", lambda **kw: calls.append(kw) or object())
    monkeypatch.setenv("SHOWDOWN_RERANKER_OVERRIDE", "1")

    for agent in ("max_damage", "random", "greedy_protect"):
        c = _client(agent=agent)
        assert c._reranker_override() is None
    assert calls == []


def test_lightgbm_not_imported_when_reranker_override_off(monkeypatch):
    """Rule 5, mirroring test_gauntlet_shadow.py's guard: the disabled override
    path must never pull lightgbm into sys.modules."""
    import sys

    monkeypatch.delenv("SHOWDOWN_RERANKER_OVERRIDE", raising=False)
    for m in [m for m in sys.modules if m == "lightgbm" or m.startswith("lightgbm.")]:
        sys.modules.pop(m, None)

    from showdown_bot.client.gauntlet import _load_reranker_override_from_env

    assert _load_reranker_override_from_env(format_id="gen9vgc2025regi") is None
    assert not any(m == "lightgbm" or m.startswith("lightgbm.") for m in sys.modules)


def test_load_reranker_override_from_env_failsafe_on_bad_model_path(monkeypatch, tmp_path):
    """Wires the real env-gated load path but never loads a real model: a
    missing model file must fail-safe to None, never raise (mirrors
    test_reranker_shadow.py's test_missing_model_disables)."""
    monkeypatch.setenv("SHOWDOWN_RERANKER_OVERRIDE", "1")
    monkeypatch.setenv("SHOWDOWN_RERANKER_MODEL_PATH", str(tmp_path / "nope.txt"))
    monkeypatch.setenv("SHOWDOWN_RERANKER_MANIFEST_PATH", str(tmp_path / "nope.json"))

    from showdown_bot.client.gauntlet import _load_reranker_override_from_env

    assert _load_reranker_override_from_env(format_id="gen9vgc2025regi") is None


# ---------------------------------------------------------------------------
# candidate-vs-baseline-diff Task 4: decision capture wired into handle_request.
# THE INVARIANT: capture OFF (decision_trace_writer is None, the default) must be
# byte-identical dispatch -- no DecisionTrace built for capture, no sidecar
# write, no change to what the bot sends. These tests pin that golden and its
# positive counterpart (capture ON writes a bound row, dispatch still unchanged).
# ---------------------------------------------------------------------------


class _RecordingConn:
    def __init__(self):
        self.sent = []

    async def send(self, message):
        self.sent.append(message)


def test_capture_off_does_not_construct_decision_trace(monkeypatch, decision_fixture):
    import showdown_bot.client.gauntlet as gauntlet

    req, kw = decision_fixture
    conn = _RecordingConn()
    client = _client(conn=conn, agent="heuristic", book=kw["book"])
    monkeypatch.setattr(client, "_state_for", lambda room, request: kw["state"])
    monkeypatch.setattr(client, "_decision_deps", lambda: (None, None, None, None))
    monkeypatch.setattr(gauntlet, "agent_choose", lambda *args, **kwargs: f"/choose default|{req.rqid}")
    monkeypatch.setattr(
        gauntlet, "DecisionTrace",
        lambda: (_ for _ in ()).throw(AssertionError("capture-off built DecisionTrace")),
    )
    client.decision_trace_writer = None
    asyncio.run(client.handle_request("battle-test", req.model_dump_json(by_alias=True)))
    assert conn.sent == [f"battle-test|/choose default|{req.rqid}"]


def test_capture_off_default_client_has_no_writer_or_context():
    """Constructing a `_Client` the plain way (no capture kwargs, matching every caller that
    predates Task 4) leaves capture fully disabled."""
    client = _client(agent="heuristic")
    assert client.decision_trace_writer is None
    assert client.decision_trace_context is None
    assert client._decision_capture_index == 0


class _FakeCaptureWriter:
    def __init__(self):
        self.rows: list[dict] = []

    def write(self, row):
        self.rows.append(row)


def test_capture_on_writes_bound_row_without_changing_dispatch(monkeypatch, decision_fixture):
    """Capture ON: a row is written AFTER the send, bound to the given context, and the
    dispatched /choose message is exactly the same as the capture-off golden above."""
    import showdown_bot.client.gauntlet as gauntlet
    from showdown_bot.eval.decision_capture import BattleTraceContext

    req, kw = decision_fixture
    conn = _RecordingConn()
    context = BattleTraceContext(
        battle_id="battle-x", seed_index=0, config_id="heuristic",
        config_hash="cfg-hash", schedule_hash="sched-hash",
        format_id="gen9vgc2025regi", git_sha="a" * 40,
    )
    writer = _FakeCaptureWriter()
    client = _client(
        conn=conn, agent="heuristic", book=kw["book"],
        decision_trace_writer=writer, decision_trace_context=context,
    )
    monkeypatch.setattr(client, "_state_for", lambda room, request: kw["state"])
    monkeypatch.setattr(client, "_decision_deps", lambda: (None, None, None, None))
    monkeypatch.setattr(gauntlet, "agent_choose", lambda *args, **kwargs: f"/choose default|{req.rqid}")

    asyncio.run(client.handle_request("battle-test", req.model_dump_json(by_alias=True)))

    assert conn.sent == [f"battle-test|/choose default|{req.rqid}"]  # dispatch unchanged
    assert len(writer.rows) == 1
    row = writer.rows[0]
    assert row["battle_id"] == "battle-x"
    assert row["decision_index"] == 0
    assert row["config_id"] == "heuristic"
    assert row["actual_choose_string"] == f"/choose default|{req.rqid}"
    assert row["decision_latency_ms"] >= 0
    assert client._decision_capture_index == 1


# ---------------------------------------------------------------------------
# 2c-Slice-0b Task 3: full-fidelity aggregation-trace sidecar wired into
# handle_request. A SECOND, INDEPENDENT optional writer/context from decision
# capture above (Task 4) -- same off-by-default discipline and the same
# byte-identical-when-off golden, but its own writer/context/counter, gated
# by its own predicate (agg_wants_trace) that never widens capture's or
# export/shadow's own trace_obj conditions.
# ---------------------------------------------------------------------------


def test_agg_trace_off_is_byte_identical(monkeypatch, decision_fixture):
    """THE gate for Task 3 (mirrors test_capture_off_does_not_construct_decision_trace exactly,
    for the SECOND, independent aggregation-trace sidecar): with agg_trace_writer unset (the
    default -- the same plain `_client()` every other capture-off test uses), no DecisionTrace
    is built for this trigger, an AggTraceWriter is never even constructed, and the dispatched
    /choose message is byte-identical."""
    import showdown_bot.client.gauntlet as gauntlet
    import showdown_bot.research.aggregation_trace as agg_trace_mod

    # "off" must be deterministic regardless of ambient env. (At the _Client level the agg seam
    # is gated purely on the instance attr `agg_trace_writer`, which the plain `_client()` never
    # sets -- no env is consulted here -- so this delenv is belt-and-braces at THIS layer; the
    # env alias only actually drives the writer in cli.run_schedule. Cleared anyway so the
    # byte-identity-off gate can never be accidentally green.)
    monkeypatch.delenv("SHOWDOWN_AGG_TRACE_OUT", raising=False)

    req, kw = decision_fixture
    conn = _RecordingConn()
    client = _client(conn=conn, agent="heuristic", book=kw["book"])
    monkeypatch.setattr(client, "_state_for", lambda room, request: kw["state"])
    monkeypatch.setattr(client, "_decision_deps", lambda: (None, None, None, None))
    monkeypatch.setattr(gauntlet, "agent_choose", lambda *args, **kwargs: f"/choose default|{req.rqid}")
    monkeypatch.setattr(
        gauntlet, "DecisionTrace",
        lambda: (_ for _ in ()).throw(AssertionError("agg-trace-off path built a DecisionTrace")),
    )
    monkeypatch.setattr(
        agg_trace_mod, "AggTraceWriter",
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("agg-trace-off path constructed an AggTraceWriter")),
    )
    assert client.agg_trace_writer is None  # default _client() never sets it
    assert client.decision_trace_writer is None  # decision capture independently off too

    asyncio.run(client.handle_request("battle-test", req.model_dump_json(by_alias=True)))
    assert conn.sent == [f"battle-test|/choose default|{req.rqid}"]


def test_agg_trace_off_default_client_has_no_writer_or_context():
    """Constructing a `_Client` the plain way (no agg kwargs, matching every caller that
    predates Task 3) leaves the agg-trace seam fully disabled -- mirrors
    test_capture_off_default_client_has_no_writer_or_context."""
    client = _client(agent="heuristic")
    assert client.agg_trace_writer is None
    assert client.agg_trace_context is None
    assert client._agg_trace_index == 0


class _FakeAggTraceWriter:
    def __init__(self):
        self.rows: list[dict] = []

    def write(self, row):
        self.rows.append(row)


def test_agg_trace_on_writes_bound_row_without_changing_dispatch(monkeypatch, decision_fixture):
    """Agg trace ON: a row is written AFTER the send, bound to the given context, and the
    dispatched /choose message is exactly the same as the off golden above -- INDEPENDENT of
    decision capture (decision_trace_writer stays unset/None here)."""
    import showdown_bot.client.gauntlet as gauntlet
    from showdown_bot.research.aggregation_trace import AggTraceContext

    req, kw = decision_fixture
    conn = _RecordingConn()
    context = AggTraceContext(
        battle_id="battle-x", seed_index=0, our_side="p1", config_id="heuristic",
        config_hash="cfg-hash", schedule_hash="sched-hash",
        format_id="gen9vgc2025regi", git_sha="a" * 40,
    )
    writer = _FakeAggTraceWriter()
    client = _client(
        conn=conn, agent="heuristic", book=kw["book"],
        agg_trace_writer=writer, agg_trace_context=context,
    )
    monkeypatch.setattr(client, "_state_for", lambda room, request: kw["state"])
    monkeypatch.setattr(client, "_decision_deps", lambda: (None, None, None, None))
    monkeypatch.setattr(gauntlet, "agent_choose", lambda *args, **kwargs: f"/choose default|{req.rqid}")

    asyncio.run(client.handle_request("battle-test", req.model_dump_json(by_alias=True)))

    assert conn.sent == [f"battle-test|/choose default|{req.rqid}"]  # dispatch unchanged
    assert len(writer.rows) == 1
    row = writer.rows[0]
    assert row["battle_id"] == "battle-x"
    assert row["decision_index"] == 0
    assert row["config_id"] == "heuristic"
    assert row["selected_action_key"] is not None
    assert client._agg_trace_index == 1
    assert client.decision_trace_writer is None  # decision capture untouched/independent


def test_agg_trace_independent_of_decision_capture_when_both_on(monkeypatch, decision_fixture):
    """Both seams ON simultaneously: each writes to its OWN sidecar with its OWN counter, off
    a single shared trace_obj/decision -- proves neither seam's presence is required for the
    other to fire, and dispatch is still unchanged."""
    import showdown_bot.client.gauntlet as gauntlet
    from showdown_bot.eval.decision_capture import BattleTraceContext
    from showdown_bot.research.aggregation_trace import AggTraceContext

    req, kw = decision_fixture
    conn = _RecordingConn()
    decision_context = BattleTraceContext(
        battle_id="battle-x", seed_index=0, config_id="heuristic",
        config_hash="cfg-hash", schedule_hash="sched-hash",
        format_id="gen9vgc2025regi", git_sha="a" * 40,
    )
    agg_context = AggTraceContext(
        battle_id="battle-x", seed_index=0, our_side="p1", config_id="heuristic",
        config_hash="cfg-hash", schedule_hash="sched-hash",
        format_id="gen9vgc2025regi", git_sha="a" * 40,
    )
    decision_writer = _FakeCaptureWriter()
    agg_writer = _FakeAggTraceWriter()
    client = _client(
        conn=conn, agent="heuristic", book=kw["book"],
        decision_trace_writer=decision_writer, decision_trace_context=decision_context,
        agg_trace_writer=agg_writer, agg_trace_context=agg_context,
    )
    monkeypatch.setattr(client, "_state_for", lambda room, request: kw["state"])
    monkeypatch.setattr(client, "_decision_deps", lambda: (None, None, None, None))
    monkeypatch.setattr(gauntlet, "agent_choose", lambda *args, **kwargs: f"/choose default|{req.rqid}")

    asyncio.run(client.handle_request("battle-test", req.model_dump_json(by_alias=True)))

    assert conn.sent == [f"battle-test|/choose default|{req.rqid}"]  # dispatch STILL unchanged
    assert len(decision_writer.rows) == 1
    assert len(agg_writer.rows) == 1
    assert client._decision_capture_index == 1
    assert client._agg_trace_index == 1


def test_run_local_gauntlet_requires_agg_writer_and_context_together():
    """Mirrors run_local_gauntlet's existing decision_trace_writer/context pairing contract (a
    writer with no battle context, or vice versa, can't produce a valid, bound row). Raises
    before any connection/battle setup -- no live server needed."""
    from showdown_bot.client.gauntlet import run_local_gauntlet

    with pytest.raises(ValueError, match="agg_trace_writer and agg_trace_context must be given together"):
        asyncio.run(run_local_gauntlet(
            games=1, format_id="gen9vgc2025regi", team_path="teams/fixed_team.txt",
            agg_trace_writer=object(),
        ))


# ---------------------------------------------------------------------------
# 2c-Slice-0b bugfix: the agg-trace write must be fail-safe/independent, mirroring the
# export-observe try/except immediately below it in handle_request. Before this fix, a
# raising build_agg_row/writer.write (e.g. validate_agg_row rejecting a legitimate
# duplicate candidate action_key from `_label_ja`) propagated OUT of handle_request,
# skipping the dataset-export observe block and stalling/erroring the decision.
# ---------------------------------------------------------------------------


class _RaisingAggTraceWriter:
    def write(self, row):
        raise RuntimeError("boom: simulated agg-trace write failure")


def test_agg_trace_write_failure_is_best_effort_and_does_not_block_dispatch(monkeypatch, decision_fixture):
    """A raising agg_trace_writer.write must NOT propagate out of handle_request, must NOT
    block the dispatched /choose, and must NOT increment `_agg_trace_index` (the counter then
    reflects only successfully written rows)."""
    import showdown_bot.client.gauntlet as gauntlet
    from showdown_bot.research.aggregation_trace import AggTraceContext

    req, kw = decision_fixture
    conn = _RecordingConn()
    context = AggTraceContext(
        battle_id="battle-x", seed_index=0, our_side="p1", config_id="heuristic",
        config_hash="cfg-hash", schedule_hash="sched-hash",
        format_id="gen9vgc2025regi", git_sha="a" * 40,
    )
    writer = _RaisingAggTraceWriter()
    client = _client(
        conn=conn, agent="heuristic", book=kw["book"],
        agg_trace_writer=writer, agg_trace_context=context,
    )
    monkeypatch.setattr(client, "_state_for", lambda room, request: kw["state"])
    monkeypatch.setattr(client, "_decision_deps", lambda: (None, None, None, None))
    monkeypatch.setattr(gauntlet, "agent_choose", lambda *args, **kwargs: f"/choose default|{req.rqid}")

    # Must not raise -- the whole point of the fix.
    asyncio.run(client.handle_request("battle-test", req.model_dump_json(by_alias=True)))

    assert conn.sent == [f"battle-test|/choose default|{req.rqid}"]  # dispatch still went out
    assert client._agg_trace_index == 0  # NOT incremented on a failed write
