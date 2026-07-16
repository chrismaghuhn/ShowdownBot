"""I7b-B: mega_activation_order_key, WeightedMegaProjection, compose_mega_projection_branches."""
from __future__ import annotations

from showdown_bot.engine.speed import mega_activation_order_key
from showdown_bot.engine.state import FieldState


def test_no_trick_room_higher_speed_sorts_first():
    field = FieldState()
    keyed = sorted([("slow", 80), ("fast", 150)], key=lambda t: mega_activation_order_key(t[1], field))
    assert keyed[0][0] == "fast"


def test_trick_room_lower_speed_sorts_first():
    field = FieldState(trick_room=True)
    keyed = sorted([("slow", 80), ("fast", 150)], key=lambda t: mega_activation_order_key(t[1], field))
    assert keyed[0][0] == "slow"


def test_matches_sort_actions_sign_convention():
    """mega_activation_order_key must use the IDENTICAL sign convention as
    resolve.sort_actions -- not an independently-invented one."""
    from showdown_bot.battle.resolve import sort_actions, PlannedAction
    from showdown_bot.engine.moves import get_move_meta

    field = FieldState(trick_room=True)
    a = PlannedAction(side="p1", slot="a", kind="move", speed=150, move=get_move_meta("Tackle"))
    b = PlannedAction(side="p2", slot="a", kind="move", speed=80, move=get_move_meta("Tackle"))
    resolver_order = [act.slot + act.side for act in sort_actions([a, b], field)]
    key_order = sorted([("a" + "p1", 150), ("a" + "p2", 80)], key=lambda t: mega_activation_order_key(t[1], field))
    assert [x[0] for x in key_order] == resolver_order
