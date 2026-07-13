from __future__ import annotations

from showdown_bot.battle.resolve import (
    MissedHit,
    PlannedAction,
    resolve_turn,
    resolve_turn_branches,
    sort_actions,
)
from showdown_bot.engine.moves import MoveMeta, get_move_meta
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


def test_attempted_hits_recorded_even_with_no_forced_miss():
    st = _state()
    moon = get_move_meta("Moonblast")
    atk = PlannedAction("p1", "a", "move", speed=100, move=moon, target=("p2", "a"), is_ours=True)

    def dmg(action, target):
        return 0.4

    out = resolve_turn(st, [atk], dmg, our_side="p1")
    assert len(out.attempted_hits) == 1
    assert out.attempted_hits[0].attacker == ("p1", "a")
    assert out.attempted_hits[0].target == ("p2", "a")
    assert out.missed_hits == []


def test_forced_miss_prevents_damage_and_records_missed_hit():
    st = _state()
    moon = get_move_meta("Moonblast")
    atk = PlannedAction("p1", "a", "move", speed=100, move=moon, target=("p2", "a"), is_ours=True)

    def dmg(action, target):
        return 0.4

    out = resolve_turn(
        st, [atk], dmg, our_side="p1", forced_miss=frozenset({(("p1", "a"), ("p2", "a"))}),
    )
    assert out.hp_delta[("p2", "a")] == 0.0
    assert len(out.missed_hits) == 1
    assert out.missed_hits[0] == MissedHit(("p1", "a"), ("p2", "a"), moon.id)


def test_forced_miss_default_is_todays_exact_behavior():
    st = _state()
    moon = get_move_meta("Moonblast")
    atk = PlannedAction("p1", "a", "move", speed=100, move=moon, target=("p2", "a"), is_ours=True)

    def dmg(action, target):
        return 0.4

    out_default = resolve_turn(st, [atk], dmg, our_side="p1")
    out_explicit_empty = resolve_turn(st, [atk], dmg, our_side="p1", forced_miss=frozenset())
    assert out_default.hp_delta == out_explicit_empty.hp_delta


def test_protect_blocked_hit_not_reclassified_as_missed_even_if_also_forced_miss():
    st = _state()
    protect = get_move_meta("Protect")
    moon = get_move_meta("Moonblast")
    prot = PlannedAction("p1", "a", "protect", speed=50, move=protect, is_ours=True)
    atk = PlannedAction("p2", "a", "move", speed=200, move=moon, target=("p1", "a"), is_ours=False)

    def dmg(action, target):
        return 0.8

    out = resolve_turn(
        st, [prot, atk], dmg, our_side="p1",
        forced_miss=frozenset({(("p2", "a"), ("p1", "a"))}),
    )
    assert len(out.protected_hits) == 1
    assert out.missed_hits == []  # protect check comes first; never reaches the miss check
    assert out.attempted_hits == []  # ...nor the attempted-hit bookkeeping


def test_spread_move_partial_forced_miss_hits_one_target_misses_other():
    st = _doubles_state()
    # Heat Wave (allAdjacentFoes) rather than Earthquake (allAdjacent): Earthquake
    # also hits the ally slot p1:b under real PS mechanics (already modeled
    # correctly by this resolver), which would make this a 3-target case instead
    # of the intended 2-target foe-only spread scenario.
    heat = get_move_meta("Heat Wave")
    atk = PlannedAction("p1", "a", "move", speed=100, move=heat, target=None, is_ours=True)
    others = [
        PlannedAction("p1", "b", "pass", speed=1, is_ours=True),
        PlannedAction("p2", "a", "pass", speed=1, is_ours=False),
        PlannedAction("p2", "b", "pass", speed=1, is_ours=False),
    ]

    def dmg(action, target):
        return 0.3

    out = resolve_turn(
        st, [atk] + others, dmg, our_side="p1",
        forced_miss=frozenset({(("p1", "a"), ("p2", "a"))}),
    )
    assert out.hp_delta[("p2", "a")] == 0.0  # forced miss
    assert out.hp_delta[("p2", "b")] < 0.0   # still hit
    assert len(out.missed_hits) == 1
    assert len(out.attempted_hits) == 2  # both targets attempted, one missed


def test_resolve_turn_branches_discovers_ko_dependent_event():
    """Regression test: X's uncertain move KOs slower Y in the all-hit run, so Y never
    reaches apply_hit there and Y's own uncertain move is invisible to any event list
    built from that run alone. The recursive expansion must discover it in the branch
    where X's move misses and Y survives to act."""
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Fast", hp=100, max_hp=100)
    st.sides["p2"]["a"] = PokemonState(species="Slow", hp=100, max_hp=100)
    x_move = MoveMeta(id="xmove", name="X", accuracy=70, base_power=100,
                       category="physical", target="normal")
    y_move = MoveMeta(id="ymove", name="Y", accuracy=50, base_power=100,
                       category="physical", target="normal")
    x = PlannedAction("p1", "a", "move", speed=200, move=x_move, target=("p2", "a"), is_ours=True)
    y = PlannedAction("p2", "a", "move", speed=50, move=y_move, target=("p1", "a"), is_ours=False)

    def dmg(action, target):
        return 1.0  # any hit is lethal

    leaves, fallback_leaves, fork_records = resolve_turn_branches(
        st, [x, y], dmg, our_side="p1", field=FieldState(), tie_break="ours_last", branch_cap=8,
    )
    assert fallback_leaves == 0
    assert len(leaves) == 3  # X-hit (Y never acts); X-miss+Y-hit; X-miss+Y-miss
    total_weight = sum(w for w, _ in leaves)
    assert abs(total_weight - 1.0) < 1e-9

    x_hit_weight, x_hit_out = leaves[0]  # depth-first hit-first -> leaves[0] is the all-hit leaf
    assert abs(x_hit_weight - 0.7) < 1e-9
    # x is OUR mon (p1, is_ours=True) KOing the opponent's p2:a -> that's a kill WE scored.
    # my_kos = kills we score (evaluate.py:109 adds it positively to our score); opp_kos = kills
    # the opponent scores against us (see test_ko_before_act_cancels_victim_action: "they KO us").
    assert x_hit_out.my_kos == 1
    assert x_hit_out.opp_kos == 0
    assert not any(ah.attacker == ("p2", "a") for ah in x_hit_out.attempted_hits)

    # The other two leaves are exactly the event a one-shot discovery pass would have missed:
    # Y surviving X's miss and taking its OWN uncertain-accuracy action.
    for w, out in leaves[1:]:
        assert any(ah.attacker == ("p2", "a") for ah in out.attempted_hits)
    remaining_weight = sum(w for w, _ in leaves[1:])
    assert abs(remaining_weight - 0.3) < 1e-9

    # fork_records: exactly one fork lies on the path to leaves[0] (X's pair). Its recorded
    # miss-sibling subtree must be exactly leaves[1:] (the two branches where X missed) --
    # this is the structure miss_punish_value (a later task, spec Sec.7) depends on.
    assert len(fork_records) == 1
    fork_pair, miss_subtree = fork_records[0]
    assert fork_pair == (("p1", "a"), ("p2", "a"))
    assert len(miss_subtree) == 2
    assert abs(sum(w for w, _ in miss_subtree) - 0.3) < 1e-9


def test_resolve_turn_branches_all_hit_leaf_when_no_uncertainty():
    st = _state()
    swift = get_move_meta("Swift")  # always-hit
    atk = PlannedAction("p1", "a", "move", speed=100, move=swift, target=("p2", "a"), is_ours=True)

    def dmg(action, target):
        return 0.3

    leaves, fallback_leaves, fork_records = resolve_turn_branches(
        st, [atk], dmg, our_side="p1", field=FieldState(), tie_break="ours_last", branch_cap=4,
    )
    assert fallback_leaves == 0
    assert len(leaves) == 1
    assert abs(leaves[0][0] - 1.0) < 1e-9
    assert fork_records == []  # no uncertainty -> no fork points at all


def test_resolve_turn_branches_two_independent_events_four_leaves():
    st = _doubles_state()
    m1 = MoveMeta(id="m1", name="M1", accuracy=60, base_power=100, category="physical", target="normal")
    m2 = MoveMeta(id="m2", name="M2", accuracy=40, base_power=100, category="physical", target="normal")
    a1 = PlannedAction("p1", "a", "move", speed=150, move=m1, target=("p2", "a"), is_ours=True)
    a2 = PlannedAction("p1", "b", "move", speed=140, move=m2, target=("p2", "b"), is_ours=True)
    others = [
        PlannedAction("p2", "a", "pass", speed=1, is_ours=False),
        PlannedAction("p2", "b", "pass", speed=1, is_ours=False),
    ]

    def dmg(action, target):
        return 0.1  # non-lethal -> both events are independent, no KO interaction

    leaves, fallback_leaves, fork_records = resolve_turn_branches(
        st, [a1, a2] + others, dmg, our_side="p1", field=FieldState(), tie_break="ours_last",
        branch_cap=8,
    )
    assert fallback_leaves == 0
    assert len(leaves) == 4
    total = sum(w for w, _ in leaves)
    assert abs(total - 1.0) < 1e-9
    weights = sorted(round(w, 6) for w, _ in leaves)
    expected = sorted(round(w, 6) for w in
                       [0.6 * 0.4, 0.6 * 0.6, 0.4 * 0.4, 0.4 * 0.6])
    assert weights == expected

    # fork_records for the two-fork case: the inner fork (discovered second, on the (p1,b)
    # event, while still on the all-hit path) is appended first (post-order -- its recursive
    # call completes before the outer fork's own append runs); the outer fork (the (p1,a)
    # event, forked first at the root) is appended last. Values verified via a direct run of
    # resolve_turn_branches with this exact scenario, not hand-derived.
    assert len(fork_records) == 2
    inner_pair, inner_subtree = fork_records[0]
    outer_pair, outer_subtree = fork_records[1]
    assert inner_pair == (("p1", "b"), ("p2", "b"))
    assert len(inner_subtree) == 1
    assert abs(sum(w for w, _ in inner_subtree) - 0.36) < 1e-9
    assert outer_pair == (("p1", "a"), ("p2", "a"))
    assert len(outer_subtree) == 2
    assert abs(sum(w for w, _ in outer_subtree) - 0.4) < 1e-9


def test_resolve_turn_branches_zero_probability_event_forces_miss_not_default_hit():
    """Regression test: hit_probability can return exactly 0.0 (e.g. very low base accuracy
    stacked against max evasion). The pending filter must NOT exclude p==0.0 -- excluding it
    would mean the pair never enters any miss_set, so it would silently default to a
    guaranteed HIT (resolve_turn's default for anything not in forced_miss) instead of the
    guaranteed MISS the probability actually demands."""
    st = _state()
    zero_acc = MoveMeta(id="zeroacc", name="ZeroAcc", accuracy=1, base_power=100,
                         category="physical", target="normal")
    atk = PlannedAction("p1", "a", "move", speed=100, move=zero_acc, target=("p2", "a"), is_ours=True)
    tgt_mon = st.sides["p2"]["a"]
    tgt_mon.boosts["evasion"] = 6  # pushes hit_probability to exactly 0.0 (verified separately)

    def dmg(action, target):
        return 0.5

    leaves, fallback_leaves, fork_records = resolve_turn_branches(
        st, [atk], dmg, our_side="p1", field=FieldState(), tie_break="ours_last", branch_cap=4,
    )
    assert fallback_leaves == 0
    assert len(leaves) == 2  # forked: hit-branch (weight 0.0) + miss-branch (weight 1.0)
    total = sum(w for w, _ in leaves)
    assert abs(total - 1.0) < 1e-9
    # No leaf with positive weight may show damage landing -- the event must be a guaranteed
    # miss, not silently resolved as a guaranteed hit.
    hit_weight = sum(w for w, out in leaves if out.hp_delta.get(("p2", "a"), 0.0) < 0.0)
    assert abs(hit_weight) < 1e-9
    miss_weight = sum(w for w, out in leaves if out.hp_delta.get(("p2", "a"), 0.0) == 0.0)
    assert abs(miss_weight - 1.0) < 1e-9


def test_resolve_turn_branches_cap_bounds_total_leaves():
    """The single largest named risk for this function is exponential blowup on many
    independent uncertain events. Lock in that branch_cap actually bounds len(leaves),
    regardless of how many genuinely-independent uncertain events exist."""
    st = BattleState()
    st.sides["p2"]["a"] = PokemonState(species="Bag", hp=100, max_hp=100)
    actions = []
    for i in range(12):
        st.sides["p1"][f"s{i}"] = PokemonState(species=f"Att{i}", hp=100, max_hp=100)
        mv = MoveMeta(id=f"u{i}", name=f"U{i}", accuracy=50, base_power=10,
                      category="physical", target="normal")
        actions.append(
            PlannedAction("p1", f"s{i}", "move", speed=100 - i, move=mv,
                          target=("p2", "a"), is_ours=True)
        )

    def dmg(action, target):
        return 0.01  # tiny, non-lethal even if all 12 land

    leaves, fallback_leaves, fork_records = resolve_turn_branches(
        st, actions, dmg, our_side="p1", field=FieldState(), tie_break="ours_last",
        branch_cap=3,
    )
    assert len(leaves) <= 3
    assert fallback_leaves >= 1  # 12 uncertain events can't fully resolve under cap=3
    total = sum(w for w, _ in leaves)
    assert abs(total - 1.0) < 1e-9


def test_resolve_turn_branches_cap_produces_per_branch_fallback_not_whole_line():
    st = _doubles_state()
    # Four independent uncertain events (2 per side) -> a cap of 2 forces exactly one fork,
    # so at least one leaf must stop expanding early while its sibling still resolves fully.
    moves = [MoveMeta(id=f"u{i}", name=f"U{i}", accuracy=50, base_power=100,
                       category="physical", target="normal") for i in range(2)]
    a1 = PlannedAction("p1", "a", "move", speed=150, move=moves[0], target=("p2", "a"), is_ours=True)
    a2 = PlannedAction("p1", "b", "move", speed=140, move=moves[1], target=("p2", "b"), is_ours=True)
    others = [
        PlannedAction("p2", "a", "pass", speed=1, is_ours=False),
        PlannedAction("p2", "b", "pass", speed=1, is_ours=False),
    ]

    def dmg(action, target):
        return 0.1

    leaves, fallback_leaves, fork_records = resolve_turn_branches(
        st, [a1, a2] + others, dmg, our_side="p1", field=FieldState(), tie_break="ours_last",
        branch_cap=2,
    )
    assert fallback_leaves >= 1  # at least one path exhausted the cap before fully resolving
    total = sum(w for w, _ in leaves)
    assert abs(total - 1.0) < 1e-9  # weight is still fully conserved despite the cap
    # fork_records only ever records forks that were actually reached and split before the cap
    # fired -- each one's miss-sibling subtree is non-empty with positive total weight.
    for _pair, miss_subtree in fork_records:
        assert len(miss_subtree) >= 1
        assert sum(w for w, _ in miss_subtree) > 0.0
