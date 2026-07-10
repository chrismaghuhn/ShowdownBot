"""T4b: forced replacements must enumerate per the force-phase contract (plan table F1-F4).

Root cause of the T4 reproduction FAIL (reports/2026-07-10-2b35-T4-smoke.md): these shapes
returned [] from enumerate_my_actions, dropping the choice to an unseeded random fallback.
Battle 19's request was forceSwitch [true,true] (run1-idx19 log); battle 9's hero request
[false,true] is the committed fixture t4b_force_single_2bench.json.
"""
from __future__ import annotations

import json
from pathlib import Path

from showdown_bot.battle.actions import enumerate_my_actions
from showdown_bot.battle.legal_actions import enumerate_slot_pairs
from showdown_bot.models.request import BattleRequest

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
