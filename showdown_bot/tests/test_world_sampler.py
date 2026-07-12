import pytest
from showdown_bot.engine.belief.hypotheses import SpreadPreset, SpeciesSpreads, SpreadBook
from showdown_bot.engine.belief import world_sampler as ws


def _spreads(nature):
    p = SpreadPreset(nature=nature, evs={"hp": 4}, items=[])
    return SpeciesSpreads(offense=p, defense=p)


def _book():
    d = _spreads("Hardy")
    return SpreadBook(default=d, species={"incineroar": _spreads("Adamant")})


def test_world_samples_default_is_one(monkeypatch):
    monkeypatch.delenv("SHOWDOWN_WORLD_SAMPLES", raising=False)
    assert ws.world_samples() == 1


def test_world_samples_clamps(monkeypatch):
    monkeypatch.setenv("SHOWDOWN_WORLD_SAMPLES", "8"); assert ws.world_samples() == 8
    monkeypatch.setenv("SHOWDOWN_WORLD_SAMPLES", "0"); assert ws.world_samples() == 1
    monkeypatch.setenv("SHOWDOWN_WORLD_SAMPLES", "999"); assert ws.world_samples() == 32
    monkeypatch.setenv("SHOWDOWN_WORLD_SAMPLES", "nan"); assert ws.world_samples() == 1


def test_world_seed_deterministic():
    a = ws.world_seed("base", 3, "boardkey")
    b = ws.world_seed("base", 3, "boardkey")
    c = ws.world_seed("base", 4, "boardkey")
    assert a == b and a != c and isinstance(a, int)


def test_build_world_dist_two_point_when_curated_differs():
    book = _book()
    curated = _spreads("Timid")
    opp_sets = {"incineroar": curated}
    dist = ws.build_world_dist([("incineroar", "Incineroar")], book, opp_sets)
    assert "incineroar" in dist
    sets = [s for s, w in dist["incineroar"]]
    assert curated in sets and book.get("Incineroar") in sets
    assert abs(sum(w for _, w in dist["incineroar"]) - 1.0) < 1e-9


def test_build_world_dist_omits_fixed_mons():
    dist = ws.build_world_dist([("incineroar", "Incineroar")], _book(), {})
    assert dist == {}


def test_sample_worlds_k1_is_most_likely_only():
    book = _book()
    opp_sets = {"incineroar": _spreads("Timid")}
    dist = ws.build_world_dist([("incineroar", "Incineroar")], book, opp_sets)
    worlds = ws.sample_worlds(dist, 1, seed=123)
    assert len(worlds) == 1
    w0, weight = worlds[0]
    assert w0["incineroar"] == opp_sets["incineroar"]
    assert weight == pytest.approx(1.0)


def test_sample_worlds_stratified_and_normalized():
    book = _book()
    opp_sets = {"incineroar": _spreads("Timid")}
    dist = ws.build_world_dist([("incineroar", "Incineroar")], book, opp_sets)
    worlds = ws.sample_worlds(dist, 4, seed=7)
    assert len(worlds) == 4
    assert worlds[0][0]["incineroar"] == opp_sets["incineroar"]
    assert abs(sum(w for _, w in worlds) - 1.0) < 1e-9


def test_sample_worlds_deterministic():
    book = _book(); opp_sets = {"incineroar": _spreads("Timid")}
    dist = ws.build_world_dist([("incineroar", "Incineroar")], book, opp_sets)
    assert ws.sample_worlds(dist, 4, seed=7) == ws.sample_worlds(dist, 4, seed=7)


def test_empty_dist_returns_one_empty_world():
    worlds = ws.sample_worlds({}, 4, seed=7)
    assert worlds == [({}, 1.0)]
