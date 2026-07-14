"""I4 T5–T13: remaining SpeedOracle / CalcProfile coverage (commit 7)."""
from __future__ import annotations

import pytest

from showdown_bot.battle.decision import _choose_best, choose_with_fallback
from showdown_bot.engine.belief.hypotheses import SpreadPreset
from showdown_bot.engine.calc_profile import (
    DEFAULT_CALC_PROFILE,
    CalcProfile,
    build_speed_oracle,
    calc_profile_from_config,
)
from showdown_bot.engine.format_config import load_format_config
from showdown_bot.engine.speed import SpeedOracle, SpeedRange
from showdown_bot.engine.state import FieldState, PokemonState


class _GenTrackingBackend:
    def __init__(self, *, spe_by_gen: dict[int, int] | None = None):
        self.spe_by_gen = spe_by_gen or {9: 100, 0: 112}
        self.gens: list[int] = []
        self.calls = 0

    def stats_batch(self, specs, *, gen=9):
        self.calls += 1
        self.gens.append(gen)
        spe = self.spe_by_gen.get(gen, 100)
        return [{"spe": spe} for _ in specs]


def test_build_speed_oracle_uses_default_profile_when_none():
    oracle = build_speed_oracle(_GenTrackingBackend())
    assert oracle.profile == DEFAULT_CALC_PROFILE


def test_speed_oracle_legacy_none_profile_defaults_to_reg_i():
    oracle = SpeedOracle(stats_backend=_GenTrackingBackend())
    assert oracle.profile == DEFAULT_CALC_PROFILE
    assert oracle.profile.generation == 9
    assert oracle.profile.max_spe_investment == 252


def test_likely_speed_passes_profile_generation_to_backend():
    backend = _GenTrackingBackend()
    oracle = SpeedOracle(
        stats_backend=backend,
        profile=CalcProfile(generation=0, max_spe_investment=32),
    )
    mon = PokemonState(species="Incineroar")
    preset = SpreadPreset(nature="Careful", evs={"hp": 32}, items=[])
    oracle.likely_speed(mon, FieldState(), "p2", preset, None)
    assert backend.gens == [0]


def test_speed_oracle_cache_isolates_cross_format_same_spread():
    backend = _GenTrackingBackend(spe_by_gen={9: 200, 0: 112})
    oracle9 = SpeedOracle(
        stats_backend=backend,
        profile=CalcProfile(generation=9, max_spe_investment=252),
    )
    oracle0 = SpeedOracle(
        stats_backend=backend,
        profile=CalcProfile(generation=0, max_spe_investment=32),
    )
    mon = PokemonState(species="Abomasnow")
    preset = SpreadPreset(nature="Hardy", evs={"spe": 32}, items=[])
    field = FieldState()

    spe9 = oracle9.likely_speed(mon, field, "p2", preset, None)
    spe0 = oracle0.likely_speed(mon, field, "p2", preset, None)

    assert spe9 == 200
    assert spe0 == 112
    assert backend.calls == 2


def test_calc_profile_from_config_reg_i_explicit_gen_nine():
    cfg = load_format_config("gen9vgc2025regi")
    profile = calc_profile_from_config(cfg)
    assert profile.generation == 9
    assert profile.max_spe_investment == 252


def test_choose_best_builds_champions_speed_oracle_when_none(
    decision_fixture, monkeypatch,
):
    captured: dict = {}

    class _StubOracle:
        def __init__(self, profile):
            self.profile = profile

        def our_speed(self, base_spe, mon, field, side):
            return base_spe or 100

        def opponent_range(self, mon, field, side, *, book):
            return SpeedRange(min=80, likely=110, max=150)

    def spy_build(backend, profile):
        captured["profile"] = profile
        return _StubOracle(profile)

    monkeypatch.setattr(
        "showdown_bot.engine.calc_profile.build_speed_oracle",
        spy_build,
    )
    req, kw = decision_fixture
    kw = {
        **kw,
        "speed_oracle": None,
        "format_config": load_format_config("gen9championsvgc2026regma"),
    }
    _choose_best(req, **kw)
    assert captured["profile"].generation == 0
    assert captured["profile"].max_spe_investment == 32


def test_choose_with_fallback_max_damage_threads_format_config(
    decision_fixture, monkeypatch,
):
    req, kw = decision_fixture
    cfg = load_format_config("gen9championsvgc2026regma")
    captured: dict = {}

    def spy_md(req, **call_kw):
        captured["format_config"] = call_kw.get("format_config")
        return f"/choose move 1 2, move 2 2|{req.rqid}"

    def _fail_heuristic(*_args, **_kwargs):
        raise RuntimeError("force max_damage fallback")

    monkeypatch.setattr(
        "showdown_bot.battle.baselines.max_damage_choice",
        spy_md,
    )
    monkeypatch.setattr(
        "showdown_bot.battle.decision.heuristic_choose_for_request",
        _fail_heuristic,
    )
    choose_with_fallback(req, format_config=cfg, **kw)
    assert captured["format_config"] is cfg
