from __future__ import annotations

import json
from pathlib import Path

from showdown_bot.battle.baselines import max_damage_choice
from showdown_bot.battle.decision import _choose_best
from showdown_bot.client.gauntlet import _Client
from showdown_bot.engine.belief.hypotheses import SpreadPreset, load_spread_book
from showdown_bot.engine.calc.models import DamageResult
from showdown_bot.engine.calc_profile import (
    DEFAULT_CALC_PROFILE,
    CalcProfile,
    build_speed_oracle,
    calc_profile_from_config,
)
from showdown_bot.engine.format_config import load_format_config
from showdown_bot.engine.speed import SpeedOracle, SpeedRange
from showdown_bot.engine.state import BattleState, FieldState, PokemonState
from showdown_bot.learning.export_runtime import DatasetExportRuntime
from showdown_bot.models.request import BattleRequest

_FIXTURES = Path(__file__).parent / "fixtures"


def _book():
    cfg = load_format_config("gen9vgc2025regi")
    return load_spread_book(cfg.meta_path("default_spreads"))


def _req() -> BattleRequest:
    return BattleRequest.model_validate(
        json.loads((_FIXTURES / "request_doubles_moves.json").read_text())
    )


def _state() -> BattleState:
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=150, max_hp=150)
    st.sides["p1"]["b"] = PokemonState(species="Rillaboom", hp=155, max_hp=155)
    st.sides["p2"]["a"] = PokemonState(species="Flutter Mane", hp=131, max_hp=131)
    st.sides["p2"]["b"] = PokemonState(species="Tornadus", hp=140, max_hp=140)
    return st


class _FakeDamageOracle:
    def __init__(self, frac: float):
        self.frac = frac

    def _res(self) -> DamageResult:
        dmg = int(self.frac * 100)
        return DamageResult(min_damage=dmg, max_damage=dmg, max_hp=100)

    def request(self, req):
        return id(req)

    def get(self, key):
        return self._res()

    def damage(self, req):
        return self._res()

    def flush(self):
        pass


class _InjectedSpeedOracle:
    def our_speed(self, base_spe, mon, field, side):
        return base_spe or 100

    def opponent_range(self, mon, field, side, *, book):
        return SpeedRange(min=80, likely=110, max=150)


class _StubCalc:
    class _StubBackend:
        def stats_batch(self, specs, *, gen=9):
            return [{"spe": 100} for _ in specs]

    backend = _StubBackend()


def test_calc_profile_from_config_none_uses_default():
    assert calc_profile_from_config(None) == DEFAULT_CALC_PROFILE
    assert DEFAULT_CALC_PROFILE.generation == 9
    assert DEFAULT_CALC_PROFILE.max_spe_investment == 252


def test_calc_profile_from_config_champions():
    cfg = load_format_config("gen9championsvgc2026regma")
    profile = calc_profile_from_config(cfg)
    assert profile.generation == 0
    assert profile.max_spe_investment == 32


class _GenTrackingBackend:
    def __init__(self, spe: int = 100):
        self.spe = spe
        self.gens: list[int] = []
        self.max_spe_evs: list[int | None] = []

    def stats_batch(self, specs, *, gen=9):
        self.gens.append(gen)
        if len(specs) >= 3:
            self.max_spe_evs.append(specs[2].evs.get("spe"))
        return [{"spe": self.spe} for _ in specs]


def test_speed_oracle_cache_key_includes_generation():
    backend = _GenTrackingBackend()
    reg_profile = CalcProfile(generation=9, max_spe_investment=252)
    gen0_profile = CalcProfile(generation=0, max_spe_investment=32)
    oracle9 = SpeedOracle(stats_backend=backend, profile=reg_profile)
    oracle0 = SpeedOracle(stats_backend=backend, profile=gen0_profile)
    mon = PokemonState(species="Incineroar")
    field = FieldState()
    preset = SpreadPreset(nature="Careful", evs={"hp": 252}, items=[])

    oracle9.likely_speed(mon, field, "p2", preset, None)
    oracle0.likely_speed(mon, field, "p2", preset, None)

    assert backend.gens == [9, 0]
    assert backend.gens[0] != backend.gens[1]


def test_speed_oracle_champions_max_spe_uses_profile_not_252():
    backend = _GenTrackingBackend()
    cfg = load_format_config("gen9championsvgc2026regma")
    book = load_spread_book(cfg.meta_path("default_spreads"))
    oracle = build_speed_oracle(backend, calc_profile_from_config(cfg))
    mon = PokemonState(species="Flutter Mane")
    oracle.opponent_range(mon, FieldState(), "p2", book=book)
    assert backend.max_spe_evs == [32]


def test_speed_oracle_reg_i_max_spe_uses_252():
    backend = _GenTrackingBackend()
    cfg = load_format_config("gen9vgc2025regi")
    book = load_spread_book(cfg.meta_path("default_spreads"))
    oracle = build_speed_oracle(backend, calc_profile_from_config(cfg))
    mon = PokemonState(species="Flutter Mane")
    oracle.opponent_range(mon, FieldState(), "p2", book=book)
    assert backend.max_spe_evs == [252]


def test_choose_best_does_not_replace_injected_speed_oracle(decision_fixture, monkeypatch):
    factory_calls: list[tuple] = []

    def spy_build(*args, **kwargs):
        factory_calls.append((args, kwargs))
        return build_speed_oracle(*args, **kwargs)

    monkeypatch.setattr(
        "showdown_bot.engine.calc_profile.build_speed_oracle",
        spy_build,
    )
    req, kw = decision_fixture
    injected = kw["speed_oracle"]
    kw = {
        **kw,
        "speed_oracle": injected,
        "format_config": load_format_config("gen9championsvgc2026regma"),
    }
    _choose_best(req, **kw)
    assert factory_calls == []


def test_gauntlet_decision_deps_uses_format_calc_profile():
    cfg = load_format_config("gen9championsvgc2026regma")
    c = _Client(
        conn=object(),
        name="T",
        agent="heuristic",
        book=load_spread_book(cfg.meta_path("default_spreads")),
        priors={},
        format_id=cfg.format_id,
        format_config=cfg,
        packed_team="",
        opp_sets={},
    )
    _calc, _oracle, speed_oracle, _dex = c._decision_deps()
    assert speed_oracle is not None
    assert speed_oracle.profile.generation == 0
    assert speed_oracle.profile.max_spe_investment == 32


def test_export_build_rollout_provider_uses_calc_profile_factory(monkeypatch):
    cfg = load_format_config("gen9championsvgc2026regma")
    captured: dict = {}

    def spy_build(backend, profile):
        captured["profile"] = profile
        return build_speed_oracle(backend, profile)

    monkeypatch.setattr(
        "showdown_bot.engine.calc_profile.build_speed_oracle",
        spy_build,
    )

    provider, _calc = DatasetExportRuntime._build_rollout_provider(
        format_id=cfg.format_id,
        dex=None,
        move_meta={},
        calc=_StubCalc(),
        book=load_spread_book(cfg.meta_path("default_spreads")),
        our_spreads={},
        opp_sets={},
        priors={},
        cfg_dict={},
    )
    assert captured["profile"].generation == 0
    assert captured["profile"].max_spe_investment == 32
    assert provider._deps["speed_oracle"].profile.generation == 0


def test_max_damage_champions_uses_calc_profile_factory(monkeypatch):
    captured: dict = {}

    def spy_build(backend, profile):
        captured["profile"] = profile
        return build_speed_oracle(backend, profile)

    monkeypatch.setattr(
        "showdown_bot.engine.calc_profile.build_speed_oracle",
        spy_build,
    )
    cfg = load_format_config("gen9championsvgc2026regma")
    max_damage_choice(
        _req(),
        state=_state(),
        book=_book(),
        our_side="p1",
        calc=_StubCalc(),
        oracle=_FakeDamageOracle(0.3),
        speed_oracle=None,
        format_config=cfg,
    )
    assert captured["profile"].generation == 0
    assert captured["profile"].max_spe_investment == 32


def test_max_damage_legacy_default_format_config_none(monkeypatch):
    captured: dict = {}

    def spy_build(backend, profile):
        captured["profile"] = profile
        return build_speed_oracle(backend, profile)

    monkeypatch.setattr(
        "showdown_bot.engine.calc_profile.build_speed_oracle",
        spy_build,
    )
    max_damage_choice(
        _req(),
        state=_state(),
        book=_book(),
        our_side="p1",
        calc=_StubCalc(),
        oracle=_FakeDamageOracle(0.3),
        speed_oracle=None,
        format_config=None,
    )
    assert captured["profile"] == DEFAULT_CALC_PROFILE


def test_max_damage_does_not_replace_injected_speed_oracle(monkeypatch):
    factory_calls: list[tuple] = []

    def spy_build(*args, **kwargs):
        factory_calls.append((args, kwargs))
        return build_speed_oracle(*args, **kwargs)

    monkeypatch.setattr(
        "showdown_bot.engine.calc_profile.build_speed_oracle",
        spy_build,
    )
    cfg = load_format_config("gen9championsvgc2026regma")
    injected = _InjectedSpeedOracle()
    max_damage_choice(
        _req(),
        state=_state(),
        book=_book(),
        our_side="p1",
        calc=_StubCalc(),
        oracle=_FakeDamageOracle(0.3),
        speed_oracle=injected,
        format_config=cfg,
    )
    assert factory_calls == []
