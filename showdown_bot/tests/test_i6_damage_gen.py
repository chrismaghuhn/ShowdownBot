"""I6 — live damage calc generation threading (hermetic gates G2–G11)."""
from __future__ import annotations

import dataclasses
import json
import inspect
from pathlib import Path

import pytest

from showdown_bot.battle.baselines import max_damage_choice
from showdown_bot.battle.decision import _choose_best
from showdown_bot.battle.evaluate import DamageModel
from showdown_bot.battle.oracle import DamageOracle
from showdown_bot.battle.resolve import PlannedAction
from showdown_bot.engine.belief.game_mode import classify_game_mode, guaranteed_ohko
from showdown_bot.engine.belief.hypotheses import load_spread_book
from showdown_bot.engine.calc.models import CalcMon, DamageRequest, DamageResult
from showdown_bot.engine.calc_profile import (
    DEFAULT_CALC_PROFILE,
    CalcProfile,
    calc_profile_from_config,
)
from showdown_bot.engine.format_config import load_format_config
from showdown_bot.engine.moves import get_move_meta
from showdown_bot.engine.state import BattleState, PokemonState
from showdown_bot.learning.decide_adapter import _CORE_DEP_KEYS, _core_deps
from showdown_bot.learning.export_runtime import DatasetExportRuntime
from showdown_bot.learning.rollout import make_resolve
from showdown_bot.models.request import BattleRequest

_FIXTURES = Path(__file__).parent / "fixtures"
_CHAMPIONS = "gen9championsvgc2026regma"


class GenCapturingClient:
    def __init__(self) -> None:
        self.gens: list[int] = []

    def damage_batch(self, requests: list[DamageRequest]) -> list[DamageResult]:
        out = []
        for r in requests:
            self.gens.append(r.gen)
            out.append(
                DamageResult(
                    rolls=[50] * 16,
                    min_damage=50,
                    max_damage=50,
                    max_hp=100,
                    id=r.id,
                )
            )
        return out


def _champions_cfg():
    return load_format_config(_CHAMPIONS)


def _champions_book():
    cfg = _champions_cfg()
    return load_spread_book(cfg.meta_path("default_spreads"))


def _twov2_state() -> BattleState:
    st = BattleState()
    p1a = PokemonState(
        species="Garchomp", hp=100, max_hp=100, moves=["earthquake", "protect"]
    )
    p1a.move_names = {"Earthquake", "Protect"}
    p1b = PokemonState(
        species="Incineroar", hp=100, max_hp=100, moves=["flareblitz", "protect"]
    )
    p1b.move_names = {"Flare Blitz", "Protect"}
    p2a = PokemonState(
        species="Flutter Mane", hp=100, max_hp=100, moves=["moonblast", "protect"]
    )
    p2a.move_names = {"Moonblast", "Protect"}
    p2b = PokemonState(
        species="Tornadus", hp=100, max_hp=100, moves=["bleakwindstorm", "protect"]
    )
    p2b.move_names = {"Bleakwind Storm", "Protect"}
    st.sides["p1"]["a"] = p1a
    st.sides["p1"]["b"] = p1b
    st.sides["p2"]["a"] = p2a
    st.sides["p2"]["b"] = p2b
    return st


def _model_with_capturing_oracle(
    st: BattleState,
    *,
    calc_profile: CalcProfile | None = None,
) -> tuple[DamageModel, GenCapturingClient]:
    client = GenCapturingClient()
    oracle = DamageOracle(client=client)  # type: ignore[arg-type]
    model = DamageModel(
        st,
        "p1",
        "p2",
        book=_champions_book(),
        oracle=oracle,
        calc_profile=calc_profile or calc_profile_from_config(_champions_cfg()),
    )
    return model, client


def _req() -> BattleRequest:
    return BattleRequest.model_validate(
        json.loads((_FIXTURES / "request_doubles_moves.json").read_text())
    )


# --- G2: DamageModel four builders ---


def test_damage_model_default_profile_is_gen_nine():
    st = _twov2_state()
    client = GenCapturingClient()
    oracle = DamageOracle(client=client)  # type: ignore[arg-type]
    model = DamageModel(st, "p1", "p2", book=_champions_book(), oracle=oracle)
    eq = get_move_meta("Earthquake")
    action = PlannedAction(
        "p1", "a", "move", speed=100, move=eq, target=("p2", "a"), is_ours=True
    )
    model.prefetch([[action]])
    assert client.gens
    assert all(g == 9 for g in client.gens)


def test_damage_model_champions_profile_emits_gen_zero_on_all_builders():
    st = _twov2_state()
    model, client = _model_with_capturing_oracle(st)
    eq = get_move_meta("Earthquake")
    action = PlannedAction(
        "p1", "a", "move", speed=100, move=eq, target=("p2", "a"), is_ours=True
    )
    model.prefetch([[action]])
    model.secures_ko(("p1", "a"), ("p2", "a"), "earthquake")
    model.has_ko_chance(("p1", "a"), ("p2", "a"), "earthquake")
    model.survives_for_sure(("p2", "a"), ("p1", "a"), "earthquake")
    assert client.gens
    assert all(g == 0 for g in client.gens)


# --- G4: cache separates gen ---


def test_oracle_cache_separates_gen_zero_and_nine():
    oracle = DamageOracle(client=GenCapturingClient())  # type: ignore[arg-type]
    base = DamageRequest(
        attacker=CalcMon(species="Garchomp"),
        defender=CalcMon(species="Incineroar"),
        move="Earthquake",
        gen=9,
    )
    gen0 = DamageRequest(
        attacker=CalcMon(species="Garchomp"),
        defender=CalcMon(species="Incineroar"),
        move="Earthquake",
        gen=0,
    )
    assert oracle._key(base) != oracle._key(gen0)


# --- G5: non-Mega Champions panel case (I6 live-model) ---


def test_damage_model_champions_garchomp_panel_emits_gen_zero():
    """Non-Mega panel species — not the I4 Meganium-Mega Body Slam bridge case."""
    st = _twov2_state()
    model, client = _model_with_capturing_oracle(st)
    eq = get_move_meta("Earthquake")
    action = PlannedAction(
        "p1", "a", "move", speed=100, move=eq, target=("p2", "a"), is_ours=True
    )
    model.damage_fn(action, None)
    assert client.gens == [0]


# --- G3: game_mode ---


def test_game_mode_champions_emits_gen_zero():
    st = _twov2_state()
    client = GenCapturingClient()
    profile = calc_profile_from_config(_champions_cfg())
    classify_game_mode(
        st,
        our_side="p1",
        calc=client,  # type: ignore[arg-type]
        book=_champions_book(),
        calc_profile=profile,
    )
    assert client.gens
    assert all(g == 0 for g in client.gens)


def test_guaranteed_ohko_champions_emits_gen_zero():
    st = _twov2_state()
    client = GenCapturingClient()
    profile = calc_profile_from_config(_champions_cfg())
    atk = st.sides["p1"]["a"]
    tgt = st.sides["p2"]["a"]
    guaranteed_ohko(
        st, atk, "earthquake", tgt,
        calc=client,  # type: ignore[arg-type]
        book=_champions_book(),
        calc_profile=profile,
    )
    assert client.gens == [0]


# --- G6: heuristic ---


class _StubCalc:
    class _StubBackend:
        def stats_batch(self, specs, *, gen=9):
            return [{"spe": 100} for _ in specs]

    backend = _StubBackend()

    def damage_batch(self, requests):
        return [
            DamageResult(min_damage=30, max_damage=30, max_hp=100, id=r.id)
            for r in requests
        ]


class _FakeDamageOracle:
    def request(self, req):
        return id(req)

    def get(self, key):
        return DamageResult(min_damage=30, max_damage=30, max_hp=100)

    def damage(self, req):
        return DamageResult(min_damage=30, max_damage=30, max_hp=100)

    def flush(self):
        pass


class _FakeSpeed:
    def our_speed(self, base_spe, mon, field, side):
        return base_spe or 100

    def opponent_range(self, mon, field, side, *, book):
        from showdown_bot.engine.speed import SpeedRange
        return SpeedRange(min=80, likely=110, max=150)


class _FakeDex:
    def types(self, species):
        return ["Normal"]


def _decision_state() -> BattleState:
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=150, max_hp=150)
    st.sides["p1"]["b"] = PokemonState(species="Rillaboom", hp=155, max_hp=155)
    st.sides["p2"]["a"] = PokemonState(species="Flutter Mane", hp=131, max_hp=131)
    st.sides["p2"]["b"] = PokemonState(species="Tornadus", hp=140, max_hp=140)
    return st


def test_choose_best_champions_damage_requests_use_gen_zero(decision_fixture, monkeypatch):
    captured: list[int] = []

    class CapturingOracle(_FakeDamageOracle):
        def request(self, req):
            captured.append(req.gen)
            return super().request(req)

        def damage(self, req):
            captured.append(req.gen)
            return super().damage(req)

    req, kw = decision_fixture
    cfg = _champions_cfg()
    book = load_spread_book(cfg.meta_path("default_spreads"))
    _choose_best(
        req,
        state=_decision_state(),
        book=book,
        our_side="p1",
        calc=_StubCalc(),
        oracle=CapturingOracle(),
        speed_oracle=_FakeSpeed(),
        dex=_FakeDex(),
        format_config=cfg,
    )
    assert captured
    assert all(g == 0 for g in captured)


# --- G7: max_damage ---


def test_max_damage_champions_damage_gen_zero_with_injected_speed_oracle(monkeypatch):
    captured: list[int] = []

    class CapturingOracle(_FakeDamageOracle):
        def request(self, req):
            captured.append(req.gen)
            return super().request(req)

    cfg = _champions_cfg()
    book = load_spread_book(cfg.meta_path("default_spreads"))
    max_damage_choice(
        _req(),
        state=_decision_state(),
        book=book,
        our_side="p1",
        calc=_StubCalc(),
        oracle=CapturingOracle(),
        speed_oracle=_FakeSpeed(),
        format_config=cfg,
    )
    assert captured
    assert all(g == 0 for g in captured)


# --- G8/G9: rollout ---


def test_make_resolve_champions_uses_gen_zero():
    cfg = _champions_cfg()
    book = load_spread_book(cfg.meta_path("default_spreads"))
    client = GenCapturingClient()
    oracle = DamageOracle(client=client)  # type: ignore[arg-type]
    profile = calc_profile_from_config(cfg)
    deps = {
        "book": book,
        "oracle": oracle,
        "calc_profile": profile,
        "format_config": cfg,
    }
    resolve = make_resolve(
        root_our_side="p1",
        roster_by_side={"p1": {}, "p2": {}},
        movesets_by_side={"p1": {}, "p2": {}},
        stats_by_side={"p1": {}, "p2": {}},
        move_meta={},
        deps=deps,
    )
    st = _twov2_state()
    eq = get_move_meta("Earthquake")
    our_plan = [
        PlannedAction(
            "p1", "a", "move", speed=100, move=eq, target=("p2", "a"), is_ours=True
        ),
    ]
    resolve(st, our_plan, [])
    assert client.gens
    assert all(g == 0 for g in client.gens)


def test_make_resolve_back_compat_defaults_gen_nine():
    cfg = load_format_config("gen9vgc2025regi")
    book = load_spread_book(cfg.meta_path("default_spreads"))
    client = GenCapturingClient()
    oracle = DamageOracle(client=client)  # type: ignore[arg-type]
    deps = {"book": book, "oracle": oracle}
    resolve = make_resolve(
        root_our_side="p1",
        roster_by_side={"p1": {}, "p2": {}},
        movesets_by_side={"p1": {}, "p2": {}},
        stats_by_side={"p1": {}, "p2": {}},
        move_meta={},
        deps=deps,
    )
    st = _twov2_state()
    eq = get_move_meta("Earthquake")
    our_plan = [
        PlannedAction(
            "p1", "a", "move", speed=100, move=eq, target=("p2", "a"), is_ours=True
        ),
    ]
    resolve(st, our_plan, [])
    assert client.gens
    assert all(g == 9 for g in client.gens)


def test_core_deps_includes_format_config_not_calc_profile():
    deps = {
        "book": object(),
        "format_config": _champions_cfg(),
        "calc_profile": calc_profile_from_config(_champions_cfg()),
    }
    filtered = _core_deps(deps)
    assert "format_config" in filtered
    assert "calc_profile" not in filtered


def test_rollout_inner_decide_splats_format_config_only(decision_fixture):
    from showdown_bot.learning.rollout import make_decide
    from showdown_bot.engine.moves import _move_table
    from showdown_bot.learning.teacher import US

    captured: list[int] = []

    class CapturingCalc(_StubCalc):
        def damage_batch(self, requests):
            for r in requests:
                captured.append(r.gen)
            return super().damage_batch(requests)

    class CapturingOracle(_FakeDamageOracle):
        def request(self, req):
            captured.append(req.gen)
            return super().request(req)

    cfg = _champions_cfg()
    book = load_spread_book(cfg.meta_path("default_spreads"))
    req, kw = decision_fixture
    roster = {"p1": {}}
    movesets = {
        "p1": {
            "Incineroar": ["fakeout", "flareblitz", "protect", "knockoff"],
            "Rillaboom": ["heatwave", "earthpower", "protect", "solarbeam"],
        }
    }
    stats = {
        "p1": {
            "Incineroar": {"spe": 100},
            "Rillaboom": {"spe": 100},
        }
    }
    deps = {
        "book": book,
        "calc": CapturingCalc(),
        "oracle": CapturingOracle(),
        "speed_oracle": _FakeSpeed(),
        "dex": _FakeDex(),
        "format_config": cfg,
        "calc_profile": calc_profile_from_config(cfg),
        "rollout_horizon": 0,
    }
    decide = make_decide(
        root_our_side="p1",
        roster_by_side=roster,
        movesets_by_side=movesets,
        stats_by_side=stats,
        move_meta=_move_table(),
        deps=deps,
    )
    decide(kw["state"], US)
    assert captured
    assert all(g == 0 for g in captured)
    filtered = _core_deps(deps)
    assert "format_config" in filtered
    assert "calc_profile" not in filtered


def test_export_rollout_deps_include_format_config_and_calc_profile():
    cfg = _champions_cfg()
    provider, _ = DatasetExportRuntime._build_rollout_provider(
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
    assert provider._deps["format_config"].format_id == cfg.format_id
    assert provider._deps["format_config"].calc_generation == 0
    assert provider._deps["calc_profile"].generation == 0


# --- G10: depth-2 ---


def test_search_module_has_no_direct_damage_request_construction():
    import showdown_bot.battle.search as search_mod

    src = inspect.getsource(search_mod)
    assert "DamageRequest(" not in src


def test_depth2_passes_same_calc_profile_instance_to_depth2_value(monkeypatch, decision_fixture):
    """G10a: depth2_value must receive the exact CalcProfile object _choose_best derived.

    Uses a mega=False variant of the Champions config: this gate is about
    calc_profile threading into the LEGACY single-world depth-2 path
    (search.depth2_value), orthogonal to Mega ranking. Since I7a-B Task 4,
    format_config.mega=True redirects _choose_best to the separate Mega
    ranking branch (decision._choose_best_mega), which does not wire depth-2
    (a documented, accepted gap -- see mega_scoring/search's own depth-2
    primitive, ``search.depth2_value_for_mega_context``, which Task 4 does not
    call from the ranking loop). Real Champions has mega=True; this test only
    needs a real, loadable FormatConfig for ``meta_path``/``calc_generation``,
    so a mega-disabled copy keeps this gate exercising the code it was written
    to test instead of silently no-op'ing through the Mega branch.
    """
    from showdown_bot.battle import decision

    sentinel = CalcProfile(generation=0, max_spe_investment=32)
    monkeypatch.setattr(
        "showdown_bot.engine.calc_profile.calc_profile_from_config",
        lambda cfg: sentinel,
    )
    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "2")
    monkeypatch.delenv("SHOWDOWN_WORLD_SAMPLES", raising=False)

    captured: list[dict | None] = []

    def spy_depth2(*args, **kwargs):
        captured.append(kwargs.get("model_kwargs"))
        return 0.0

    monkeypatch.setattr(decision, "depth2_value", spy_depth2)

    req, _kw = decision_fixture
    cfg = dataclasses.replace(_champions_cfg(), mega=False)
    book = load_spread_book(cfg.meta_path("default_spreads"))
    decision._choose_best(
        req,
        state=_decision_state(),
        book=book,
        our_side="p1",
        calc=_StubCalc(),
        oracle=_FakeDamageOracle(),
        speed_oracle=_FakeSpeed(),
        dex=_FakeDex(),
        format_config=cfg,
    )

    assert captured, "depth2_value was never invoked with SHOWDOWN_SEARCH_DEPTH=2"
    for model_kwargs in captured:
        assert model_kwargs is not None
        assert model_kwargs["calc_profile"] is sentinel


def test_depth2_turn2_damage_model_emits_gen_zero(monkeypatch):
    """G10b: search._score_turn2_plans turn-2 DamageModel uses calc_profile -> gen=0."""
    import showdown_bot.battle.search as search_mod
    from showdown_bot.battle.opponent import OppResponse

    profile = calc_profile_from_config(_champions_cfg())
    captured_profiles: list[CalcProfile | None] = []
    client = GenCapturingClient()
    oracle = DamageOracle(client=client)  # type: ignore[arg-type]

    real_damage_model = search_mod.DamageModel

    class SpyDamageModel(real_damage_model):
        def __init__(self, *args, **kwargs):
            captured_profiles.append(kwargs.get("calc_profile"))
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(search_mod, "DamageModel", SpyDamageModel)

    moon = get_move_meta("Moonblast")
    opp_action = PlannedAction(
        "p2", "a", "move", speed=150, move=moon, target=("p1", "a"), is_ours=False
    )
    opp_resps = [OppResponse(actions=[opp_action], label="focus")]

    search_mod._score_turn2_plans(
        _twov2_state(),
        our_side="p1",
        opp_side="p2",
        opp_resps=opp_resps,
        book=_champions_book(),
        oracle=oracle,
        predict_kwargs={},
        model_kwargs={"calc_profile": profile},
        eval_kwargs={},
    )

    assert captured_profiles == [profile]
    assert client.gens
    assert all(g == 0 for g in client.gens)


# --- G11: Reg-I regression ---


def test_damage_model_none_format_defaults_gen_nine():
    st = _twov2_state()
    client = GenCapturingClient()
    oracle = DamageOracle(client=client)  # type: ignore[arg-type]
    reg_book = load_spread_book(
        load_format_config("gen9vgc2025regi").meta_path("default_spreads")
    )
    model = DamageModel(st, "p1", "p2", book=reg_book, oracle=oracle)
    eq = get_move_meta("Earthquake")
    action = PlannedAction(
        "p1", "a", "move", speed=100, move=eq, target=("p2", "a"), is_ours=True
    )
    model.prefetch([[action]])
    assert client.gens
    assert all(g == 9 for g in client.gens)
    assert DEFAULT_CALC_PROFILE.generation == 9


def test_core_dep_keys_contains_format_config():
    assert "format_config" in _CORE_DEP_KEYS
    assert "calc_profile" not in _CORE_DEP_KEYS
