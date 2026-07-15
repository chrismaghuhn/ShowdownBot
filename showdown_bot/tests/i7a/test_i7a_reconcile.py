from __future__ import annotations

import pytest

from showdown_bot.engine.log_parser import LogEvent, PokemonId, parse_log, parse_log_line
from showdown_bot.engine.mega_reconcile import (
    MegaReconcileError,
    MegaReconcileEvent,
    MegaReconcileReducer,
    reduce_log_events,
)
from showdown_bot.engine.mega_projection import copy_battle_state
from showdown_bot.engine.state import BattleState, PokemonState

# ---------------------------------------------------------------------------
# I7a-C Task 1: parse and reduce Mega protocol events
# ---------------------------------------------------------------------------


def switch_event():
    return parse_log_line(
        "switch",
        ["p1a: Charizard", "Charizard, L50", "100/100"],
    )


def detailschange_event():
    return parse_log_line(
        "detailschange",
        ["p1a: Charizard", "Charizard-Mega-Y, L50"],
    )


def mega_event():
    return parse_log_line(
        "-mega",
        ["p1a: Charizard", "Charizard", "Charizardite Y"],
    )


def test_parse_mega_ground_truth_three_args():
    event = parse_log_line(
        "-mega",
        ["p1a: Charizard", "Charizard", "Charizardite Y"],
    )
    assert event.type == "mega"
    assert event.value == "Charizard"
    assert event.details == "Charizardite Y"


def test_parse_detailschange():
    event = parse_log_line(
        "detailschange",
        ["p1a: Charizard", "Charizard-Mega-Y, L50"],
    )
    assert event.type == "detailschange"
    assert event.pokemon.raw == "p1a: Charizard"
    assert event.details == "Charizard-Mega-Y, L50"


def test_reduced_stream_can_start_with_normal_event():
    raw = [switch_event(), detailschange_event(), mega_event()]
    reduced = reduce_log_events(raw)
    assert isinstance(reduced[0], LogEvent)
    assert isinstance(reduced[1], MegaReconcileEvent)
    state = BattleState.from_reduced_log(reduced)
    assert state.active("p1", "a").species == "Charizard-Mega-Y"


def test_mega_reconcile_event_field_mapping():
    raw = [detailschange_event(), mega_event()]
    reduced = reduce_log_events(raw)
    assert len(reduced) == 1
    event = reduced[0]
    assert isinstance(event, MegaReconcileEvent)
    assert event.pokemon.raw == "p1a: Charizard"
    assert event.mega_species_details == "Charizard-Mega-Y, L50"
    assert event.base_species == "Charizard"
    assert event.stone_display == "Charizardite Y"


def test_orphan_detailschange_flushes_as_ordinary_event():
    # A detailschange with no following -mega for that ident (e.g. a non-Mega
    # form change like Zygarde) must survive the batch as a plain LogEvent.
    other_switch = parse_log_line("switch", ["p2a: Zygarde", "Zygarde, L50", "100/100"])
    other_change = parse_log_line("detailschange", ["p2a: Zygarde", "Zygarde-Complete, L50"])
    raw = [other_switch, other_change]
    reduced = reduce_log_events(raw)
    assert len(reduced) == 2
    assert isinstance(reduced[0], LogEvent)
    assert isinstance(reduced[1], LogEvent)
    assert reduced[1].type == "detailschange"
    assert reduced[1].details == "Zygarde-Complete, L50"


def test_mega_without_pending_detailschange_fails_closed():
    with pytest.raises(MegaReconcileError):
        reduce_log_events([mega_event()])


def test_mega_with_wrong_ident_fails_closed():
    # detailschange pending for p1a, but the -mega event targets p2a: this
    # must NOT silently pair across idents.
    other_change = parse_log_line("detailschange", ["p1a: Charizard", "Charizard-Mega-Y, L50"])
    wrong_mega = parse_log_line(
        "-mega",
        ["p2a: Charizard", "Charizard", "Charizardite Y"],
    )
    with pytest.raises(MegaReconcileError):
        reduce_log_events([other_change, wrong_mega])


def test_reduce_log_events_flushes_exactly_once_at_batch_end():
    # A trailing pending detailschange (nothing follows it in the raw
    # stream) must be emitted exactly once via the final flush, not zero
    # and not duplicated.
    raw = [switch_event(), detailschange_event()]
    reduced = reduce_log_events(raw)
    assert len(reduced) == 2
    assert isinstance(reduced[0], LogEvent)
    assert reduced[0].type == "switch"
    assert isinstance(reduced[1], LogEvent)
    assert reduced[1].type == "detailschange"
    assert reduced[1].details == "Charizard-Mega-Y, L50"
    # Confirm no duplication: exactly one detailschange event survived.
    detailschange_events = [e for e in reduced if isinstance(e, LogEvent) and e.type == "detailschange"]
    assert len(detailschange_events) == 1


def test_reducer_feed_returns_pending_on_second_detailschange_for_same_ident():
    reducer = MegaReconcileReducer()
    first_change = detailschange_event()
    second_change = parse_log_line("detailschange", ["p1a: Charizard", "Charizard-Mega-X, L50"])
    assert reducer.feed(first_change) == []
    emitted = reducer.feed(second_change)
    assert emitted == [first_change]
    tail = reducer.flush_pending()
    assert tail == [second_change]


# ---------------------------------------------------------------------------
# I7a-C Task 2: apply reconciliation with rollback and persistent belief
# updates (T41-T46)
# ---------------------------------------------------------------------------

RAW_MEGA_LOG = """\
|switch|p1a: Charizard|Charizard, L50|100/100
|switch|p2a: Incineroar|Incineroar, L50|100/100
|turn|1
|detailschange|p1a: Charizard|Charizard-Mega-Y, L50
|-mega|p1a: Charizard|Charizard|Charizardite Y
"""


@pytest.fixture
def state():
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Charizard", item=None, item_known=False)
    return st


@pytest.fixture
def book():
    from showdown_bot.engine.belief.hypotheses import load_spread_book
    from showdown_bot.engine.format_config import load_format_config

    cfg = load_format_config("gen9vgc2025regi")
    return load_spread_book(cfg.meta_path("default_spreads"))


def reconcile_event() -> MegaReconcileEvent:
    return MegaReconcileEvent(
        pokemon=PokemonId.parse("p1a: Charizard"),
        mega_species_details="Charizard-Mega-Y, L50",
        base_species="Charizard",
        stone_display="Charizardite Y",
    )


# T41: item conflict -> no spend, state unchanged (rollback).
def test_item_conflict_rolls_back_every_mega_field(state):
    state.active("p1", "a").item = "Leftovers"
    state.active("p1", "a").item_known = True
    before = copy_battle_state(state)
    event = reconcile_event()
    with pytest.raises(MegaReconcileError):
        state.apply_event(event)
    assert state == before
    mon = state.active("p1", "a")
    assert mon.species == "Charizard"
    assert mon.item == "Leftovers"
    assert mon.item_known is True
    assert mon.base_species_id == "charizard"
    assert mon.ability is None
    assert state.side_mega_spent["p1"] is False


# T42: full room log rebuild (BattleState.from_log_text) applies the mega.
def test_full_log_rebuild_applies_mega_reconcile():
    state = BattleState.from_log_text(RAW_MEGA_LOG)
    mon = state.active("p1", "a")
    assert mon.species == "Charizard-Mega-Y"
    assert mon.ability == "Drought"
    assert mon.types == ["Fire", "Flying"]
    assert mon.item == "Charizardite Y"
    assert mon.item_known is True
    assert mon.base_species_id == "charizard"
    assert state.side_mega_spent["p1"] is True
    # No synthetic weather from the mega ability's side effect.
    assert state.field.weather is None


# T43: BeliefTracker.feed batch reaches the same end state as a full rebuild
# via from_log_text (cross-call reducer wiring, not a manual reducer call).
def test_belief_tracker_feed_matches_full_log_rebuild(book):
    from showdown_bot.engine.belief.tracker import BeliefTracker

    expected = BattleState.from_log_text(RAW_MEGA_LOG)

    tracker = BeliefTracker.from_state(BattleState(), book)
    tracker.feed(parse_log(RAW_MEGA_LOG))

    mon = tracker.state.active("p1", "a")
    expected_mon = expected.active("p1", "a")
    assert mon.species == expected_mon.species
    assert mon.ability == expected_mon.ability
    assert mon.types == expected_mon.types
    assert mon.item == expected_mon.item
    assert mon.item_known == expected_mon.item_known
    assert mon.base_species_id == expected_mon.base_species_id
    assert tracker.state.side_mega_spent == expected.side_mega_spent


# T44: detailschange without -mega -> form-only apply, no side_mega_spent set.
def test_standalone_trailing_detailschange_applies_form_only():
    raw = (
        "|switch|p2a: Zygarde|Zygarde, L50|100/100\n"
        "|detailschange|p2a: Zygarde|Zygarde-Complete, L50\n"
    )
    state = BattleState.from_log_text(raw)
    mon = state.active("p2", "a")
    assert mon.species == "Zygarde-Complete"
    # No mega item/spend side effects for an ordinary forme change.
    assert mon.item is None
    assert mon.item_known is False
    assert state.side_mega_spent["p2"] is False


# T45: -mega without a pending detailschange fails closed all the way through
# apply_event/from_log_text, not just at the reducer level (see
# test_mega_without_pending_detailschange_fails_closed above for the
# reducer-only case, which the reducer raises before state is ever touched).
def test_orphan_mega_fails_closed_through_from_log_text():
    raw = "|switch|p1a: Charizard|Charizard, L50|100/100\n|-mega|p1a: Charizard|Charizard|Charizardite Y\n"
    with pytest.raises(MegaReconcileError):
        BattleState.from_log_text(raw)


# T46: wrong ident pairing / wrong actor -> no mutation.
def test_wrong_actor_reconcile_event_rolls_back_without_mutation(state):
    before = copy_battle_state(state)
    # base_species claims Blastoise, but p1a actually holds Charizard: the
    # reconcile event does not match the actual occupant of the slot.
    event = MegaReconcileEvent(
        pokemon=PokemonId.parse("p1a: Charizard"),
        mega_species_details="Blastoise-Mega, L50",
        base_species="Blastoise",
        stone_display="Blastoisinite",
    )
    with pytest.raises(MegaReconcileError):
        state.apply_event(event)
    assert state == before
    assert state.active("p1", "a").species == "Charizard"
    assert state.side_mega_spent["p1"] is False


# Cross-call persistence: update() (not feed()) must pair detailschange and
# -mega across two separate calls via the tracker's persistent reducer.
def test_belief_update_pairs_events_across_calls(state, book):
    from showdown_bot.engine.belief.tracker import BeliefTracker

    tracker = BeliefTracker.from_state(state, book)
    tracker.update(detailschange_event())
    assert tracker.state.active("p1", "a").species == "Charizard"
    tracker.update(mega_event())
    assert tracker.state.active("p1", "a").species == "Charizard-Mega-Y"
    assert tracker.state.side_mega_spent["p1"] is True


# ---------------------------------------------------------------------------
# I7a-C P1.1 fix: enforce one Mega per side per battle (side-wide invariant).
# ---------------------------------------------------------------------------


def second_slot_mega_event() -> MegaReconcileEvent:
    return MegaReconcileEvent(
        pokemon=PokemonId.parse("p1b: Aerodactyl"),
        mega_species_details="Aerodactyl-Mega, L50",
        base_species="Aerodactyl",
        stone_display="Aerodactylite",
    )


@pytest.fixture
def two_mon_state():
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Charizard", item=None, item_known=False)
    st.sides["p1"]["b"] = PokemonState(species="Aerodactyl", item=None, item_known=False)
    return st


# T47: a second, DIFFERENT Mega on the same side (different slot/actor) must
# fail closed, even though the first Mega succeeded normally.
def test_second_different_mega_on_same_side_rejected(two_mon_state):
    two_mon_state.apply_event(reconcile_event())
    assert two_mon_state.side_mega_spent["p1"] is True

    before = copy_battle_state(two_mon_state)
    with pytest.raises(MegaReconcileError):
        two_mon_state.apply_event(second_slot_mega_event())

    # Zero trace: state is byte-identical to right after the first Mega,
    # including the untouched p1b Aerodactyl.
    assert two_mon_state == before
    mon_a = two_mon_state.active("p1", "a")
    assert mon_a.species == "Charizard-Mega-Y"
    mon_b = two_mon_state.active("p1", "b")
    assert mon_b.species == "Aerodactyl"
    assert mon_b.item is None
    assert mon_b.item_known is False
    assert mon_b.base_species_id == "aerodactyl"
    assert two_mon_state.side_mega_spent["p1"] is True


# T48: an exact replay of the SAME already-applied Mega event is an
# idempotent no-op -- no exception, state unchanged.
def test_exact_replay_of_same_mega_event_is_idempotent_noop(state):
    state.apply_event(reconcile_event())
    before = copy_battle_state(state)

    # Re-apply the identical event a second time.
    state.apply_event(reconcile_event())

    assert state == before
    mon = state.active("p1", "a")
    assert mon.species == "Charizard-Mega-Y"
    assert mon.item == "Charizardite Y"
    assert mon.item_known is True
    assert state.side_mega_spent["p1"] is True


# T49: a replay for the SAME slot/actor but with a DIFFERENT stone/form must
# fail closed (not silently accepted as "close enough").
def test_same_slot_different_form_replay_rejected(state):
    state.apply_event(reconcile_event())
    before = copy_battle_state(state)

    different_form_event = MegaReconcileEvent(
        pokemon=PokemonId.parse("p1a: Charizard"),
        mega_species_details="Charizard-Mega-X, L50",
        base_species="Charizard",
        stone_display="Charizardite X",
    )
    with pytest.raises(MegaReconcileError):
        state.apply_event(different_form_event)

    assert state == before
    mon = state.active("p1", "a")
    assert mon.species == "Charizard-Mega-Y"
    assert mon.item == "Charizardite Y"
    assert state.side_mega_spent["p1"] is True


# T50: BeliefTracker.feed and a full raw-log rebuild agree on a same-side
# double-mega sequence -- both reject the second, different Mega the same
# way (same exception type, same resulting state after the rejection).
RAW_DOUBLE_MEGA_LOG = """\
|switch|p1a: Charizard|Charizard, L50|100/100
|switch|p1b: Aerodactyl|Aerodactyl, L50|100/100
|switch|p2a: Incineroar|Incineroar, L50|100/100
|switch|p2b: Landorus|Landorus, L50|100/100
|turn|1
|detailschange|p1a: Charizard|Charizard-Mega-Y, L50
|-mega|p1a: Charizard|Charizard|Charizardite Y
|detailschange|p1b: Aerodactyl|Aerodactyl-Mega, L50
|-mega|p1b: Aerodactyl|Aerodactyl|Aerodactylite
"""


def test_belief_tracker_feed_matches_full_log_rebuild_for_double_mega(book):
    from showdown_bot.engine.belief.tracker import BeliefTracker

    with pytest.raises(MegaReconcileError):
        BattleState.from_log_text(RAW_DOUBLE_MEGA_LOG)

    tracker = BeliefTracker.from_state(BattleState(), book)
    with pytest.raises(MegaReconcileError):
        tracker.feed(parse_log(RAW_DOUBLE_MEGA_LOG))

    # Both entry points must reject at exactly the same point: the first
    # Mega succeeded, the second (different slot) did not.
    mon_a = tracker.state.active("p1", "a")
    assert mon_a.species == "Charizard-Mega-Y"
    mon_b = tracker.state.active("p1", "b")
    assert mon_b.species == "Aerodactyl"
    assert tracker.state.side_mega_spent["p1"] is True
