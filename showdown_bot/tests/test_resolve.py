from __future__ import annotations

from showdown_bot.battle.resolve import PlannedAction, resolve_turn, sort_actions
from showdown_bot.engine.moves import get_move_meta
from showdown_bot.engine.state import BattleState, FieldState, PokemonState


def _state(p1_hp=1.0, p2_hp=1.0):
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=int(p1_hp * 100), max_hp=100)
    st.sides["p2"]["a"] = PokemonState(species="Flutter Mane", hp=int(p2_hp * 100), max_hp=100)
    return st


def test_sort_priority_beats_speed():
    fake = get_move_meta("Fake Out")  # priority 3
    tackle = get_move_meta("Moonblast")  # priority 0
    slow = PlannedAction("p1", "a", "move", speed=50, move=fake, target=("p2", "a"))
    fast = PlannedAction("p2", "a", "move", speed=200, move=tackle, target=("p1", "a"))
    ordered = sort_actions([fast, slow], FieldState())
    assert ordered[0] is slow  # higher priority acts first despite lower speed


def test_sort_speed_within_same_priority():
    m = get_move_meta("Moonblast")
    slow = PlannedAction("p1", "a", "move", speed=80, move=m, target=("p2", "a"))
    fast = PlannedAction("p2", "a", "move", speed=120, move=m, target=("p1", "a"))
    ordered = sort_actions([slow, fast], FieldState())
    assert ordered[0] is fast


def test_sort_trick_room_inverts_speed():
    m = get_move_meta("Moonblast")
    slow = PlannedAction("p1", "a", "move", speed=80, move=m, target=("p2", "a"))
    fast = PlannedAction("p2", "a", "move", speed=120, move=m, target=("p1", "a"))
    ordered = sort_actions([slow, fast], FieldState(trick_room=True))
    assert ordered[0] is slow  # slower acts first under TR


def test_sort_speed_tie_pessimistic():
    m = get_move_meta("Moonblast")
    mine = PlannedAction("p1", "a", "move", speed=100, move=m, target=("p2", "a"), is_ours=True)
    theirs = PlannedAction("p2", "a", "move", speed=100, move=m, target=("p1", "a"), is_ours=False)
    ordered = sort_actions([mine, theirs], FieldState())
    assert ordered[0] is theirs  # we lose the tie


def test_switch_resolves_before_moves():
    m = get_move_meta("Quick Attack")  # priority 1
    sw = PlannedAction("p1", "a", "switch", speed=1)
    mv = PlannedAction("p2", "a", "move", speed=200, move=m, target=("p1", "a"))
    ordered = sort_actions([mv, sw], FieldState())
    assert ordered[0] is sw


def test_ko_before_act_cancels_victim_action():
    st = _state(p1_hp=0.3, p2_hp=1.0)
    moon = get_move_meta("Moonblast")
    # p2 fast hits p1 for lethal; p1 slower would have hit p2.
    opp = PlannedAction("p2", "a", "move", speed=200, move=moon, target=("p1", "a"), is_ours=False)
    mine = PlannedAction("p1", "a", "move", speed=50, move=moon, target=("p2", "a"), is_ours=True)

    def dmg(action, target):
        return 0.99 if action.side == "p2" else 0.99

    out = resolve_turn(st, [opp, mine], dmg, our_side="p1")
    assert out.opp_kos == 1  # they KO us
    assert out.my_kos == 0  # our action was cancelled
    assert any(p.side == "p1" for p in out.prevented_actions)


def test_protect_blocks_damaging_move():
    st = _state()
    protect = get_move_meta("Protect")
    moon = get_move_meta("Moonblast")
    prot = PlannedAction("p1", "a", "protect", speed=50, move=protect, is_ours=True)
    atk = PlannedAction("p2", "a", "move", speed=200, move=moon, target=("p1", "a"), is_ours=False)

    def dmg(action, target):
        return 0.8

    out = resolve_turn(st, [prot, atk], dmg, our_side="p1")
    assert len(out.protected_hits) == 1
    assert out.hp_delta[("p1", "a")] == 0.0  # no damage taken


def test_damage_and_hp_delta():
    st = _state(p2_hp=1.0)
    moon = get_move_meta("Moonblast")
    atk = PlannedAction("p1", "a", "move", speed=100, move=moon, target=("p2", "a"), is_ours=True)

    def dmg(action, target):
        return 0.4

    out = resolve_turn(st, [atk], dmg, our_side="p1")
    assert abs(out.hp_delta[("p2", "a")] + 0.4) < 1e-9
    assert out.my_kos == 0


def _doubles_state():
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=100, max_hp=100)
    st.sides["p1"]["b"] = PokemonState(species="Rillaboom", hp=100, max_hp=100)
    st.sides["p2"]["a"] = PokemonState(species="Flutter Mane", hp=100, max_hp=100)
    st.sides["p2"]["b"] = PokemonState(species="Amoonguss", hp=100, max_hp=100)
    return st


def test_fake_out_flinch_prevents_opponent_move():
    st = _doubles_state()
    fake = get_move_meta("Fake Out")
    moon = get_move_meta("Moonblast")
    mine = PlannedAction("p1", "a", "move", speed=50, move=fake, target=("p2", "a"), is_ours=True)
    opp = PlannedAction("p2", "a", "move", speed=200, move=moon, target=("p1", "a"), is_ours=False)

    def dmg(action, target):
        return 0.2 if action.is_ours else 0.5

    out = resolve_turn(st, [mine, opp], dmg, our_side="p1")
    assert any(p.reason == "flinch" and p.side == "p2" for p in out.prevented_actions)
    assert out.hp_delta[("p1", "a")] == 0.0  # flinched -> no incoming damage


def test_rage_powder_redirects_single_target():
    st = _doubles_state()
    rage = get_move_meta("Rage Powder")
    moon = get_move_meta("Moonblast")
    redir = PlannedAction("p2", "b", "move", speed=150, move=rage, is_ours=False)
    mine = PlannedAction("p1", "a", "move", speed=100, move=moon, target=("p2", "a"), is_ours=True)

    def dmg(action, target):
        return 0.5

    out = resolve_turn(st, [redir, mine], dmg, our_side="p1")
    assert len(out.redirected_hits) == 1
    assert out.redirected_hits[0].new_target == ("p2", "b")
    assert out.hp_delta[("p2", "b")] == -0.5
    assert out.hp_delta[("p2", "a")] == 0.0


def test_rage_powder_does_not_redirect_grass_attacker():
    st = _doubles_state()
    st.sides["p1"]["a"].types = ["Grass"]  # Grass-types ignore powder redirection
    rage = get_move_meta("Rage Powder")
    moon = get_move_meta("Moonblast")
    redir = PlannedAction("p2", "b", "move", speed=150, move=rage, is_ours=False)
    mine = PlannedAction("p1", "a", "move", speed=100, move=moon, target=("p2", "a"), is_ours=True)

    def dmg(action, target):
        return 0.5

    out = resolve_turn(st, [redir, mine], dmg, our_side="p1")
    assert out.redirected_hits == []  # Grass attacker is immune to Rage Powder
    assert out.hp_delta[("p2", "a")] == -0.5
    assert out.hp_delta[("p2", "b")] == 0.0


def test_rage_powder_still_redirects_non_grass_attacker():
    st = _doubles_state()
    st.sides["p1"]["a"].types = ["Fire", "Dark"]  # Incineroar typing, not immune
    rage = get_move_meta("Rage Powder")
    moon = get_move_meta("Moonblast")
    redir = PlannedAction("p2", "b", "move", speed=150, move=rage, is_ours=False)
    mine = PlannedAction("p1", "a", "move", speed=100, move=moon, target=("p2", "a"), is_ours=True)

    def dmg(action, target):
        return 0.5

    out = resolve_turn(st, [redir, mine], dmg, our_side="p1")
    assert len(out.redirected_hits) == 1
    assert out.hp_delta[("p2", "b")] == -0.5


def test_consecutive_protect_fails_in_resolver():
    st = _doubles_state()
    st.sides["p1"]["a"].consecutive_protect = 1  # protected last turn already
    protect = get_move_meta("Protect")
    moon = get_move_meta("Moonblast")
    mine = PlannedAction("p1", "a", "protect", speed=100, move=protect, is_ours=True)
    opp = PlannedAction("p2", "a", "move", speed=120, move=moon, target=("p1", "a"), is_ours=False)

    def dmg(action, target):
        return 0.5

    out = resolve_turn(st, [mine, opp], dmg, our_side="p1")
    assert any(f.startswith("protect_failed") for f in out.flags)
    assert out.hp_delta[("p1", "a")] == -0.5  # protect failed -> took the hit
    # A failed Protect must be charged the lost-action tempo cost, otherwise its
    # +4 priority lets a doomed Protect outscore actually attacking (Protect spam).
    assert any(
        p.side == "p1" and p.reason == "protect_failed"
        for p in out.prevented_actions
    )


def test_first_protect_succeeds():
    st = _doubles_state()  # consecutive_protect == 0
    protect = get_move_meta("Protect")
    moon = get_move_meta("Moonblast")
    mine = PlannedAction("p1", "a", "protect", speed=100, move=protect, is_ours=True)
    opp = PlannedAction("p2", "a", "move", speed=120, move=moon, target=("p1", "a"), is_ours=False)

    def dmg(action, target):
        return 0.5

    out = resolve_turn(st, [mine, opp], dmg, our_side="p1")
    assert out.hp_delta[("p1", "a")] == 0.0  # blocked
    assert any(p.target == ("p1", "a") for p in out.protected_hits)


def test_fake_out_fails_after_first_turn():
    st = _doubles_state()
    st.sides["p1"]["a"].moved_since_switch = True  # not fresh anymore
    fake = get_move_meta("Fake Out")
    mine = PlannedAction("p1", "a", "move", speed=100, move=fake, target=("p2", "a"), is_ours=True)

    def dmg(action, target):
        return 0.3

    out = resolve_turn(st, [mine], dmg, our_side="p1")
    assert "wasted_move" in out.flags
    assert out.hp_delta[("p2", "a")] == 0.0  # failed -> no damage, no flinch


def test_fake_out_works_when_fresh():
    st = _doubles_state()  # moved_since_switch == False
    fake = get_move_meta("Fake Out")
    mine = PlannedAction("p1", "a", "move", speed=100, move=fake, target=("p2", "a"), is_ours=True)

    def dmg(action, target):
        return 0.3

    out = resolve_turn(st, [mine], dmg, our_side="p1")
    assert "wasted_move" not in out.flags
    assert out.hp_delta[("p2", "a")] < 0


def test_spread_move_hits_both_foes_reduced():
    st = _doubles_state()
    heat = get_move_meta("Heat Wave")  # allAdjacentFoes
    mine = PlannedAction("p1", "a", "move", speed=100, move=heat, target=None, is_ours=True)

    def dmg(action, target):
        return 0.4

    out = resolve_turn(st, [mine], dmg, our_side="p1")
    assert abs(out.hp_delta[("p2", "a")] + 0.3) < 1e-9  # 0.4 * 0.75
    assert abs(out.hp_delta[("p2", "b")] + 0.3) < 1e-9


def test_failed_target_retargets_to_living_foe():
    st = _doubles_state()
    st.sides["p2"]["a"].fainted = True
    st.sides["p2"]["a"].hp = 0
    moon = get_move_meta("Moonblast")
    mine = PlannedAction("p1", "a", "move", speed=100, move=moon, target=("p2", "a"), is_ours=True)

    def dmg(action, target):
        return 0.5

    out = resolve_turn(st, [mine], dmg, our_side="p1")
    assert "retarget" in out.flags
    assert out.hp_delta[("p2", "b")] == -0.5


def test_status_move_no_damage_records_flag():
    st = _state()
    tw = get_move_meta("Tailwind")
    act = PlannedAction("p1", "a", "move", speed=100, move=tw, is_ours=True)

    def dmg(action, target):
        raise AssertionError("status move should not call damage_fn")

    out = resolve_turn(st, [act], dmg, our_side="p1")
    assert any(f.startswith("status:tailwind") for f in out.flags)


def _atk(side, slot, speed, ours):
    return PlannedAction(side, slot, "move", speed=speed, move=get_move_meta("Tackle"),
                         target=("p2" if ours else "p1", "a"), is_ours=ours)


def test_tie_break_orders_both_ways():
    ours = _atk("p1", "a", 100, True)
    opp = _atk("p2", "a", 100, False)
    last = sort_actions([opp, ours], tie_break="ours_last")
    first = sort_actions([opp, ours], tie_break="ours_first")
    assert last[0] is opp and last[1] is ours      # ours acts last (default)
    assert first[0] is ours and first[1] is opp     # ours acts first
