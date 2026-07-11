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
