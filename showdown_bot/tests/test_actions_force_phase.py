"""T4b: forced replacements must enumerate per the force-phase contract (plan table F1-F4).

Root cause of the T4 reproduction FAIL (reports/2026-07-10-2b35-T4-smoke.md): these shapes
returned [] from enumerate_my_actions, dropping the choice to an unseeded random fallback.
Battle 19's request was forceSwitch [true,true] (run1-idx19 log); battle 9's hero request
[false,true] is the committed fixture t4b_force_single_2bench.json.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from showdown_bot.battle.actions import enumerate_my_actions
from showdown_bot.battle.decision import heuristic_choose_for_request
from showdown_bot.battle.legal_actions import enumerate_slot_pairs
from showdown_bot.engine.belief.hypotheses import load_spread_book
from showdown_bot.engine.calc.models import DamageResult
from showdown_bot.engine.format_config import load_format_config
from showdown_bot.engine.speed import SpeedRange
from showdown_bot.engine.state import BattleState, PokemonState
from showdown_bot.models.request import BattleRequest
from showdown_bot.protocol.encoder import encode_choose

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture_request(name: str) -> BattleRequest:
    return BattleRequest.model_validate(json.loads((FIXTURES / name).read_text()))


def _base_f2_dict() -> dict:
    """The committed real request (battle 9's hero, run1-idx09 log): forceSwitch
    [false, true], Incineroar alive/unforced, Rillaboom fainted/forced, bench
    Tornadus + Flutter Mane both alive."""
    return json.loads((FIXTURES / "t4b_force_single_2bench.json").read_text())


def _f1_request() -> BattleRequest:
    """F1: double forced, 2 bench. Both actives fainted; bench {Tornadus, Flutter Mane}."""
    d = _base_f2_dict()
    d["forceSwitch"] = [True, True]
    d["side"]["pokemon"][0]["condition"] = "0 fnt"  # Incineroar now fainted too
    return BattleRequest.model_validate(d)


def _f3_request() -> BattleRequest:
    """F3: double forced, 1 bench (suspected battle-19 shape). Both actives fainted;
    Flutter Mane also fainted -> only Tornadus left on the bench."""
    d = _base_f2_dict()
    d["forceSwitch"] = [True, True]
    d["side"]["pokemon"][0]["condition"] = "0 fnt"  # Incineroar fainted
    d["side"]["pokemon"][3]["condition"] = "0 fnt"  # Flutter Mane fainted -> bench = {Tornadus}
    return BattleRequest.model_validate(d)


def _f4_request() -> BattleRequest:
    """F4: single forced, 1 bench. Rillaboom fainted/forced (as in F2); Flutter Mane
    also fainted -> only Tornadus left on the bench."""
    d = _base_f2_dict()
    d["side"]["pokemon"][3]["condition"] = "0 fnt"  # Flutter Mane fainted -> bench = {Tornadus}
    return BattleRequest.model_validate(d)


def _all_f_fixtures() -> list[BattleRequest]:
    return [
        _load_fixture_request("t4b_force_single_2bench.json"),
        _f1_request(),
        _f3_request(),
        _f4_request(),
    ]


def _joint_shapes(jas):
    return sorted(
        ((ja.slot0.kind, ja.slot0.target_ident), (ja.slot1.kind, ja.slot1.target_ident))
        for ja in jas
    )


def test_f2_single_forced_two_bench_real_request():
    req = _load_fixture_request("t4b_force_single_2bench.json")
    jas = enumerate_my_actions(req)
    assert _joint_shapes(jas) == sorted([
        (("pass", None), ("switch", "Tornadus")),
        (("pass", None), ("switch", "Flutter Mane")),
    ])


def test_f1_double_forced_two_bench_enumerates_both_assignments():
    req = _f1_request()  # synthetic: forceSwitch [true,true], bench {Tornadus, Flutter Mane}
    jas = enumerate_my_actions(req)
    assert _joint_shapes(jas) == sorted([
        (("switch", "Tornadus"), ("switch", "Flutter Mane")),
        (("switch", "Flutter Mane"), ("switch", "Tornadus")),
    ])


def test_f3_double_forced_one_bench_switch_plus_pass():
    req = _f3_request()  # forceSwitch [true,true], bench {Tornadus}
    jas = enumerate_my_actions(req)
    assert _joint_shapes(jas) == sorted([
        (("switch", "Tornadus"), ("pass", None)),
        (("pass", None), ("switch", "Tornadus")),
    ])


def test_f4_single_forced_one_bench():
    req = _f4_request()
    jas = enumerate_my_actions(req)
    assert _joint_shapes(jas) == sorted([(("pass", None), ("switch", "Tornadus"))])


def test_voluntary_double_switch_still_pruned():
    # Normal turn (no force phase): allow_double_switch=False still drops switch+switch.
    req = _load_fixture_request("request_doubles_moves.json")
    jas = enumerate_my_actions(req)
    assert not any(
        ja.slot0.kind == "switch" and ja.slot1.kind == "switch" for ja in jas
    )
    # sanity: the fixture actually offers voluntary switches to prune against.
    assert any(ja.slot0.kind == "switch" or ja.slot1.kind == "switch" for ja in jas)


def test_enumerate_slot_pairs_nonempty_on_all_force_shapes():
    for req in _all_f_fixtures():
        assert enumerate_slot_pairs(req)  # random/default fallback substrate legal too
    # F3 was EMPTY here pre-fix (same-target dedup ate the only combination and no
    # pass was offered) -- Task 4's pick_default_pair builds on enumerate_slot_pairs,
    # so pin the exact F3 set: maximal-switch assignments only, no (pass, pass),
    # no same-target double switch.
    f3_pairs = enumerate_slot_pairs(_f3_request())
    f3_shapes = sorted(
        ((p.slot0.kind, p.slot0.target_ident), (p.slot1.kind, p.slot1.target_ident))
        for p in f3_pairs
    )
    assert f3_shapes == sorted([
        (("switch", "Tornadus"), ("pass", None)),
        (("pass", None), ("switch", "Tornadus")),
    ])


# ---------------------------------------------------------------------------
# Task 3: heuristic evaluates forced replacements end-to-end (determinism +
# no-fallback). Fakes replicated from conftest.py / test_decision_replay.py
# (no live server/calc backend needed) -- same pattern used throughout the
# suite (e.g. test_decide_adapter.py's "Fakes from conftest" section).
# ---------------------------------------------------------------------------


def _book():
    cfg = load_format_config("gen9vgc2025regi")
    return load_spread_book(cfg.meta_path("default_spreads"))


class _FakeCalc:
    """Never a guaranteed KO -> NEUTRAL game mode."""

    backend = None

    def damage_batch(self, requests):
        return [DamageResult(min_damage=20, max_damage=35, max_hp=150) for _ in requests]


class _FakeOracle:
    def request(self, req):
        return (req.attacker.species, req.move, req.defender.species)

    def get(self, key):
        return DamageResult(min_damage=45, max_damage=70, max_hp=150)

    def damage(self, req):
        return DamageResult(min_damage=45, max_damage=70, max_hp=150)

    def flush(self):
        pass


class _FakeSpeed:
    def our_speed(self, base, mon, field, side):
        return base or 100

    def opponent_range(self, mon, field, side, *, book):
        return SpeedRange(min=80, likely=110, max=150)


class _FakeDex:
    def types(self, species):
        return {"Flutter Mane": ["Ghost", "Fairy"], "Tornadus": ["Flying"]}.get(
            species, ["Normal"]
        )


def _force_state(req: BattleRequest) -> BattleState:
    """State for our own side (p1) mirroring an F-fixture: Incineroar (slot a) /
    Rillaboom (slot b), fainted per ``req.force_switch`` -- same species/HP as
    conftest's ``decision_fixture`` state, faint flags layered on top so the
    evaluation pipeline sees the same picture the live bot would (a mon faints
    -> state marks it fainted -> next request forces the replacement). p2 is an
    unrelated placeholder pair (Flutter Mane/Tornadus, matching conftest) so
    ``predict_responses`` has real move data to work with; it never needs to be
    forced since only our own side is under test."""
    fs = req.force_switch or [False, False]
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(
        species="Incineroar", hp=0 if fs[0] else 150, max_hp=150, fainted=bool(fs[0]),
    )
    st.sides["p1"]["b"] = PokemonState(
        species="Rillaboom", hp=0 if fs[1] else 155, max_hp=155, fainted=bool(fs[1]),
    )
    fm = PokemonState(species="Flutter Mane", hp=131, max_hp=131)
    fm.move_names = {"Moonblast", "Shadow Ball"}
    tor = PokemonState(species="Tornadus", hp=140, max_hp=140)
    tor.move_names = {"Tailwind", "Bleakwind Storm"}
    st.sides["p2"]["a"] = fm
    st.sides["p2"]["b"] = tor
    return st


def _fake_deps(req: BattleRequest) -> dict:
    return dict(
        state=_force_state(req),
        book=_book(),
        our_side="p1",
        calc=_FakeCalc(),
        oracle=_FakeOracle(),
        speed_oracle=_FakeSpeed(),
        dex=_FakeDex(),
    )


def _legal_choices(req: BattleRequest) -> set[str]:
    """Every ``/choose`` string enumerate_my_actions considers legal for req --
    the ground truth the heuristic's pick must land in."""
    return {
        encode_choose(ja.as_pair(), rqid=req.rqid) for ja in enumerate_my_actions(req)
    }


def test_heuristic_answers_force_requests_deterministically(caplog):
    """R2: for every F1-F4 shape, the heuristic answers via evaluation (not the
    fallback), producing the SAME legal /choose string across repeated calls."""
    for req in _all_f_fixtures():
        legal = _legal_choices(req)
        choices: set[str] = set()
        for _ in range(5):
            with caplog.at_level(logging.WARNING):
                choices.add(heuristic_choose_for_request(req, **_fake_deps(req)))
        assert len(choices) == 1, (req.force_switch, choices)  # deterministic
        choice = next(iter(choices))
        assert choice.startswith("/choose ")
        assert choice.endswith(f"|{req.rqid}")
        assert choice in legal, (choice, legal)  # a legal answer for this shape
    assert "falling back" not in caplog.text  # evaluated, NOT the fallback path


def test_f4_heuristic_switches_the_only_bench_mon_into_the_forced_slot():
    """F4 has exactly one legal joint action: (pass, switch Tornadus) -- the
    single bench mon must fill the forced slot (slot b, since force_switch is
    [False, True])."""
    req = _f4_request()
    legal = _legal_choices(req)
    assert len(legal) == 1
    choice = heuristic_choose_for_request(req, **_fake_deps(req))
    assert choice == next(iter(legal))
    assert choice == f"/choose pass, switch Tornadus|{req.rqid}"
