"""T3c scripted_vgc: determinism + VGC-mechanic COVERAGE (not a strength claim).

In fixtures where each is the intended option, scripted_vgc must attempt Fake Out, a
redirect/support move, Protect (last resort), and Terastallize.
"""
from __future__ import annotations

from showdown_bot.engine.moves import get_move_meta
from showdown_bot.eval.opponents.scripted_vgc import scripted_vgc_choice
from showdown_bot.models.request import BattleRequest


def _mv(mid: str) -> dict:
    return {"move": mid, "id": mid, "pp": 10, "maxpp": 10,
            "target": get_move_meta(mid).target, "disabled": False}


def _make_req(slot0_ids, can_tera=None, slot1_ids=("tackle",)) -> BattleRequest:
    active0 = {"moves": [_mv(m) for m in slot0_ids]}
    if can_tera:
        active0["canTerastallize"] = can_tera
    active1 = {"moves": [_mv(m) for m in slot1_ids]}
    side = {"name": "x", "id": "p1", "pokemon": [
        {"ident": "p1: A", "details": "", "condition": "100/100", "active": True},
        {"ident": "p1: B", "details": "", "condition": "100/100", "active": True},
        {"ident": "p1: C", "details": "", "condition": "100/100", "active": False},
    ]}
    return BattleRequest.model_validate({"active": [active0, active1], "side": side, "rqid": 9})


def _slot0(out: str) -> str:
    return out[len("/choose "):].split("|")[0].split(", ")[0]


def test_scripted_attempts_fake_out():
    out = scripted_vgc_choice(_make_req(["fakeout", "flareblitz", "protect", "knockoff"], can_tera="Fire"))
    assert _slot0(out).startswith("move 1")  # Fake Out is move 1, top priority


def test_scripted_attempts_redirect_support():
    out = scripted_vgc_choice(_make_req(["followme", "moonblast", "dazzlinggleam", "protect"]))
    assert _slot0(out).startswith("move 1")  # Follow Me (redirect) is move 1


def test_scripted_attempts_protect_as_last_resort():
    out = scripted_vgc_choice(_make_req(["protect", "willowisp", "toxic", "spore"]))
    assert _slot0(out).startswith("move 1")  # only Protect scores above the status moves


def test_scripted_attempts_terastallize():
    out = scripted_vgc_choice(_make_req(["flareblitz", "knockoff", "earthquake", "uturn"], can_tera="Fire"))
    assert "terastallize" in out  # attacker + tera offered -> a tera'd attack is chosen


def test_scripted_is_deterministic():
    r = _make_req(["fakeout", "flareblitz", "protect", "knockoff"], can_tera="Fire")
    assert scripted_vgc_choice(r) == scripted_vgc_choice(r)
