from __future__ import annotations

import pytest

from showdown_bot.engine.log_parser import LogEvent, parse_log_line
from showdown_bot.engine.mega_reconcile import (
    MegaReconcileError,
    MegaReconcileEvent,
    MegaReconcileReducer,
    reduce_log_events,
)
from showdown_bot.engine.state import BattleState

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
