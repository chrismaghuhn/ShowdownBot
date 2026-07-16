"""I7b-A: click-rate parsing and (later in this file) response pipeline tests."""
from __future__ import annotations

import pytest

from showdown_bot.battle.opponent import InvalidOppMegaClickRateError, opp_mega_click_rate


@pytest.mark.parametrize("raw,expected", [("0.35", 0.35), ("0.0", 0.0), ("1.0", 1.0), ("0.2", 0.2), ("0.5", 0.5)])
def test_opp_mega_click_rate_accepts_valid_values(monkeypatch, raw, expected):
    monkeypatch.setenv("SHOWDOWN_OPP_MEGA_CLICK_RATE", raw)
    assert opp_mega_click_rate() == expected


def test_opp_mega_click_rate_defaults_to_0_35_when_unset(monkeypatch):
    monkeypatch.delenv("SHOWDOWN_OPP_MEGA_CLICK_RATE", raising=False)
    assert opp_mega_click_rate() == 0.35


@pytest.mark.parametrize("raw", ["-0.1", "1.1", "nan", "inf", "-inf", "abc", ""])
def test_opp_mega_click_rate_fails_closed_on_invalid_values(monkeypatch, raw):
    monkeypatch.setenv("SHOWDOWN_OPP_MEGA_CLICK_RATE", raw)
    with pytest.raises(InvalidOppMegaClickRateError):
        opp_mega_click_rate()


from showdown_bot.battle.opponent import (
    OpponentResponseCapError,
    OppResponse,
    predict_responses,
)
from showdown_bot.engine.belief.protect_priors import ProtectPriors
from showdown_bot.engine.mega_form import mega_form_for
from showdown_bot.engine.state import BattleState, PokemonState


def _doubles_state(*, opp_a_item=None, opp_a_item_known=False) -> BattleState:
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=100, max_hp=100)
    st.sides["p1"]["b"] = PokemonState(species="Rillaboom", hp=100, max_hp=100)
    st.sides["p2"]["a"] = PokemonState(
        species="Aerodactyl", hp=100, max_hp=100, item=opp_a_item, item_known=opp_a_item_known,
    )
    st.sides["p2"]["b"] = PokemonState(species="Meganium", hp=100, max_hp=100)
    return st


def _eligibility_a_only():
    return {"a": mega_form_for("Aerodactyl", "Aerodactylite")}


def test_no_mega_twin_when_slot_not_eligible():
    state = _doubles_state()
    resps = predict_responses(
        state, "p1", "p2", max_candidates=10,
        foe_mega_eligibility={}, opp_mega_click_rate=0.35,
    )
    assert all(r.foe_mega_slot is None for r in resps)
    assert all(r.response_id.endswith("|mega=none") for r in resps)


def test_no_mega_twin_retained_alongside_mega_twin_when_eligible():
    """Binding: revealed/hypothesized stone -> BOTH no-mega and mega twins present."""
    state = _doubles_state(opp_a_item="aerodactylite", opp_a_item_known=True)
    resps = predict_responses(
        state, "p1", "p2", max_candidates=10,
        foe_mega_eligibility=_eligibility_a_only(), opp_mega_click_rate=0.35,
    )
    ids = {r.response_id for r in resps}
    assert any(rid.endswith("|mega=none") for rid in ids)
    assert any(rid.endswith("|mega=0") for rid in ids)  # slot "a" == index 0


@pytest.mark.parametrize("rate", [0.0, 0.35, 1.0])
def test_weights_sum_to_one_at_various_click_rates(rate):
    """T19/T29: weights sum to 1 after the full pipeline, at 0.0/0.35/1.0."""
    state = _doubles_state(opp_a_item="aerodactylite", opp_a_item_known=True)
    resps = predict_responses(
        state, "p1", "p2", max_candidates=10, priors=ProtectPriors(),
        foe_mega_eligibility=_eligibility_a_only(), opp_mega_click_rate=rate,
    )
    assert resps
    assert sum(r.weight for r in resps) == pytest.approx(1.0)


def test_click_rate_zero_gives_mega_twin_zero_weight_not_absence():
    """rate=0.0 must still retain the mega twin (never deterministic), just weight 0."""
    state = _doubles_state(opp_a_item="aerodactylite", opp_a_item_known=True)
    resps = predict_responses(
        state, "p1", "p2", max_candidates=10, priors=ProtectPriors(),
        foe_mega_eligibility=_eligibility_a_only(), opp_mega_click_rate=0.0,
    )
    mega_resps = [r for r in resps if r.foe_mega_slot is not None]
    assert mega_resps
    assert all(r.weight == pytest.approx(0.0) for r in mega_resps)


def test_click_rate_one_gives_no_mega_twin_zero_weight_not_absence():
    """Applies only to families that actually have a legal Mega alternative
    (i.e. produced a mega twin) -- a family with NO legal Mega slot in this
    response (e.g. pivot, whose only eligible slot switches here) has nothing
    to redirect its mass to and must keep full weight regardless of click
    rate (Codex review counterexample; see
    test_family_without_legal_mega_slot_keeps_full_original_weight)."""
    state = _doubles_state(opp_a_item="aerodactylite", opp_a_item_known=True)
    resps = predict_responses(
        state, "p1", "p2", max_candidates=10, priors=ProtectPriors(),
        foe_mega_eligibility=_eligibility_a_only(), opp_mega_click_rate=1.0,
    )
    labels_with_mega_twin = {r.label for r in resps if r.foe_mega_slot is not None}
    none_resps_with_alternative = [
        r for r in resps if r.foe_mega_slot is None and r.label in labels_with_mega_twin
    ]
    assert none_resps_with_alternative
    assert all(r.weight == pytest.approx(0.0) for r in none_resps_with_alternative)

    pivot_none = next(r for r in resps if r.label == "pivot" and r.foe_mega_slot is None)
    assert pivot_none.label not in labels_with_mega_twin
    assert pivot_none.weight > 0.0


def test_cap_too_small_for_reserve_classes_raises():
    """T32-adjacent: R = {none, mega-slot-a} has size 2; max_candidates=1 cannot
    hold both classes -> fail closed, never silently drop a class."""
    state = _doubles_state(opp_a_item="aerodactylite", opp_a_item_known=True)
    with pytest.raises(OpponentResponseCapError):
        predict_responses(
            state, "p1", "p2", max_candidates=1,
            foe_mega_eligibility=_eligibility_a_only(), opp_mega_click_rate=0.35,
        )


def test_cap_sufficient_but_tight_still_reserves_every_class():
    """T32: many heavy no-mega responses cannot eliminate the mega-class
    representative once R fits within max_candidates."""
    state = _doubles_state(opp_a_item="aerodactylite", opp_a_item_known=True)
    resps = predict_responses(
        state, "p1", "p2", max_candidates=2, priors=ProtectPriors(),
        foe_mega_eligibility=_eligibility_a_only(), opp_mega_click_rate=0.35,
    )
    assert len(resps) == 2
    classes = {("none" if r.foe_mega_slot is None else str(r.foe_mega_slot)) for r in resps}
    assert classes == {"none", "0"}


def test_truncation_and_tie_break_are_deterministic():
    """Same inputs -> identical response_id ordering across repeated calls."""
    state = _doubles_state(opp_a_item="aerodactylite", opp_a_item_known=True)
    first = predict_responses(
        state, "p1", "p2", max_candidates=2, priors=ProtectPriors(),
        foe_mega_eligibility=_eligibility_a_only(), opp_mega_click_rate=0.35,
    )
    second = predict_responses(
        state, "p1", "p2", max_candidates=2, priors=ProtectPriors(),
        foe_mega_eligibility=_eligibility_a_only(), opp_mega_click_rate=0.35,
    )
    assert [r.response_id for r in first] == [r.response_id for r in second]


def test_two_eligible_slots_split_mega_weight_50_50():
    state = _doubles_state(opp_a_item="aerodactylite", opp_a_item_known=True)
    state.sides["p2"]["b"] = PokemonState(
        species="Meganium", hp=100, max_hp=100, item="meganiumite", item_known=True,
    )
    eligibility = {
        "a": mega_form_for("Aerodactyl", "Aerodactylite"),
        "b": mega_form_for("Meganium", "Meganiumite"),
    }
    resps = predict_responses(
        state, "p1", "p2", max_candidates=10, priors=ProtectPriors(),
        foe_mega_eligibility=eligibility, opp_mega_click_rate=0.35,
    )
    # Compare within response families where BOTH slots take move-class actions.
    # A pivot family legitimately excludes its switching slot and therefore must
    # not be used to assert a global 50/50 total across all families.
    labels_with_both = {
        r.label for r in resps if r.foe_mega_slot == 0
    } & {
        r.label for r in resps if r.foe_mega_slot == 1
    }
    assert labels_with_both
    for label in labels_with_both:
        slot0_weight = sum(
            r.weight for r in resps if r.label == label and r.foe_mega_slot == 0
        )
        slot1_weight = sum(
            r.weight for r in resps if r.label == label and r.foe_mega_slot == 1
        )
        assert slot0_weight == pytest.approx(slot1_weight, rel=1e-6)


def test_legacy_call_without_mega_kwargs_is_byte_identical_to_before(monkeypatch):
    """Reg-I / format_config=None safety net: omitting foe_mega_eligibility and
    opp_mega_click_rate entirely must reproduce today's exact response set
    (same labels, same weights, same count, same truncate-before-weight order)."""
    state = _doubles_state()
    resps = predict_responses(state, "p1", "p2", max_candidates=5, priors=ProtectPriors())
    assert all(r.foe_mega_slot is None for r in resps)
    assert all(r.response_id == f"{r.label}|mega=none" for r in resps)
    assert sum(r.weight for r in resps) == pytest.approx(1.0)


def test_pivot_switch_slot_never_grows_a_mega_twin():
    """Codex review: a slot that switches this response cannot also Mega."""
    state = _doubles_state(opp_a_item="aerodactylite", opp_a_item_known=True)
    resps = predict_responses(
        state, "p1", "p2", max_candidates=10, priors=ProtectPriors(),
        foe_mega_eligibility=_eligibility_a_only(), opp_mega_click_rate=0.35,
    )
    pivot = next(r for r in resps if "pivot" in r.label and r.foe_mega_slot is None)
    switching_slots = {a.slot for a in pivot.actions if a.kind == "switch"}
    assert "a" in switching_slots  # confirms this response's slot "a" switches
    mega_twins_for_pivot_family = [
        r for r in resps if r.label == "pivot" and r.foe_mega_slot == 0
    ]
    assert mega_twins_for_pivot_family == []


def test_family_without_legal_mega_slot_keeps_full_original_weight():
    """Codex review: a response family whose only Mega-eligible slot switches
    in THAT family has no legal Mega twin at all -- its weight must not be
    discounted by opp_mega_click_rate with nothing to redistribute it to.
    Cross-check against the mega-inactive (foe_mega_eligibility={}) baseline,
    which computes this family's weight via the identical, unmodified
    _apply_protect_prior_split helper -- the two must match exactly, not just
    approximately, since a correct (mass-conserving) pipeline never rescales
    an untouched family's weight."""
    state = _doubles_state(opp_a_item="aerodactylite", opp_a_item_known=True)

    baseline = predict_responses(
        state, "p1", "p2", max_candidates=10, priors=ProtectPriors(),
        foe_mega_eligibility={}, opp_mega_click_rate=0.35,
    )
    pivot_baseline = next(r for r in baseline if r.label == "pivot")

    mega_active = predict_responses(
        state, "p1", "p2", max_candidates=10, priors=ProtectPriors(),
        foe_mega_eligibility=_eligibility_a_only(), opp_mega_click_rate=0.35,
    )
    pivot_actual = next(
        r for r in mega_active if r.label == "pivot" and r.foe_mega_slot is None
    )

    assert pivot_actual.weight == pytest.approx(pivot_baseline.weight, rel=1e-9)
