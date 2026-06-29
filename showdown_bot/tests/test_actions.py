from __future__ import annotations

import json
from pathlib import Path

from showdown_bot.battle.actions import JointAction, enumerate_my_actions
from showdown_bot.battle.legal_actions import enumerate_slot_pairs
from showdown_bot.models.actions import SlotAction
from showdown_bot.models.request import BattleRequest

FIXTURES = Path(__file__).parent / "fixtures"


def _req(name="request_doubles_moves.json") -> BattleRequest:
    return BattleRequest.model_validate(json.loads((FIXTURES / name).read_text()))


def test_enumerate_strips_tera():
    acts = enumerate_my_actions(_req())
    assert acts
    for ja in acts:
        assert not ja.slot0.terastallize
        assert not ja.slot1.terastallize


def test_enumerate_has_move_move():
    acts = enumerate_my_actions(_req())
    kinds = {(ja.slot0.kind, ja.slot1.kind) for ja in acts}
    assert ("move", "move") in kinds


def test_double_switch_dropped_by_default():
    acts = enumerate_my_actions(_req(), allow_double_switch=False)
    assert not any(
        ja.slot0.kind == "switch" and ja.slot1.kind == "switch" for ja in acts
    )


def test_fainted_active_slot_passes_not_moves():
    """Regression (real game stall): slot1's active mon (Landorus) had fainted
    with no replacement, so the slot stays in ``active`` with moves but the
    server expects ``pass``. The bot emitted 'move 1 1, move 1 1' -> server
    rejected ('more choices than unfainted Pokemon') -> game hung. The fainted
    slot must pass; the living slot still gets real moves."""
    acts = enumerate_my_actions(_req("request_fainted_active_slot.json"))
    assert acts
    assert all(ja.slot1.kind == "pass" for ja in acts)
    assert any(ja.slot0.kind == "move" for ja in acts)


def test_legal_pairs_pass_fainted_active_slot():
    """Same fix in the baseline path (legal_actions.enumerate_slot_pairs)."""
    pairs = enumerate_slot_pairs(_req("request_fainted_active_slot.json"))
    assert pairs
    assert all(p.slot1.kind == "pass" for p in pairs)


def test_dead_fake_out_pruned_when_moved_since_switch():
    """Bug (user's game, turns 9 & 11): Incineroar kept picking Fake Out though it
    had been out since turn 1 -> 'But it failed!', wasting the whole turn. Fake Out
    (move 1) must NOT be offered for a slot whose mon already moved since switch-in."""
    req = _req()  # Incineroar in slot0, Fake Out = move_index 1
    acts = enumerate_my_actions(req, moved_since_switch=[True, False])
    assert acts
    assert not any(ja.slot0.kind == "move" and ja.slot0.move_index == 1 for ja in acts)
    # the real attacks are still there (Flare Blitz = move 2)
    assert any(ja.slot0.kind == "move" and ja.slot0.move_index == 2 for ja in acts)


def test_fake_out_kept_on_switch_in_turn():
    """Fresh switch-in (moved_since_switch False, or unknown) keeps Fake Out legal."""
    req = _req()
    on_switch = enumerate_my_actions(req, moved_since_switch=[False, False])
    assert any(ja.slot0.kind == "move" and ja.slot0.move_index == 1 for ja in on_switch)
    # backward compatible: no info given -> Fake Out still offered
    default = enumerate_my_actions(req)
    assert any(ja.slot0.kind == "move" and ja.slot0.move_index == 1 for ja in default)


def test_double_switch_allowed_when_requested():
    acts = enumerate_my_actions(_req(), allow_double_switch=True)
    assert any(
        ja.slot0.kind == "switch" and ja.slot1.kind == "switch" for ja in acts
    )


def test_with_tera_applies_to_move_slot():
    ja = JointAction(
        slot0=SlotAction(kind="move", move_index=1, target=1),
        slot1=SlotAction(kind="switch", target_ident="Flutter Mane"),
    )
    t0 = ja.with_tera(0)
    assert t0.slot0.terastallize is True
    assert t0.slot1.terastallize is False
    # cannot tera while switching -> no-op
    t1 = ja.with_tera(1)
    assert t1.slot1.terastallize is False
    assert t1 is ja or t1.slot1.terastallize is False


def test_as_pair_roundtrip():
    ja = JointAction(
        slot0=SlotAction(kind="move", move_index=2, target=1),
        slot1=SlotAction(kind="move", move_index=1, target=2),
    )
    pair = ja.as_pair()
    assert pair.slot0 is ja.slot0
    assert pair.slot1 is ja.slot1
