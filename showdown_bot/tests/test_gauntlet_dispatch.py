from __future__ import annotations

import json
import re
from pathlib import Path

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
