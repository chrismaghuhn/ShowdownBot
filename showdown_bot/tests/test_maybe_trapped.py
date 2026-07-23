"""Gate B SAFETY-FAIL fix (B1): a slot the server reports as ``maybeTrapped`` must not have
VOLUNTARY switch actions enumerated.

Why this is correct rather than over-conservative -- verified against the pinned simulator
``f8ac140`` and recorded in
``docs/projects/champions/audits/2026-07-23-gate-b-trapped-switch-defect-diagnosis.md``:
all three trapping abilities (Arena Trap, Magnet Pull, Shadow Tag) call ``tryTrap(true)``, which
sets ``this.trapped = 'hidden'`` (``sim/pokemon.ts:1613-1618``; the field is typed
``boolean | "hidden"`` at ``:131``). Request generation then deliberately restricts information for
the LAST active slot (``sim/pokemon.ts:1098``): a non-last slot uses the loose ``if (this.trapped)``
and reports ``trapped: true`` (``:1124``), while the last active uses the strict
``if (this.trapped === true)``, which ``'hidden'`` fails, so it reports ``maybeTrapped: true``
instead (``:1135-1138``). For an ability trap, ``maybeTrapped`` therefore means "actually trapped,
withheld" -- NOT "uncertain". Enumerating a switch for such a slot is enumerating an illegal action.

The live defect: ``ActiveSlot`` modelled ``trapped`` but not ``maybeTrapped``, and pydantic's
default is to IGNORE unknown keys, so the flag was silently dropped, the slot parsed to
``trapped=None``, and ``_voluntary_switches`` offered switches for a trapped Pokemon. The server
rejected with ``[Unavailable choice] Can't switch: The active Pokemon is trapped``, which under
Gate B's fail-closed safety gate failed the whole run (``invalid_choices`` = 1).
"""
from __future__ import annotations

import json
from pathlib import Path

from showdown_bot.battle.actions import _voluntary_switches, enumerate_my_actions
from showdown_bot.battle.legal_actions import _slot_move_actions
from showdown_bot.models.request import ActiveSlot, BattleRequest

FIXTURES = Path(__file__).parent / "fixtures"

# The frozen Gate B request that produced the SAFETY-FAIL, reconstructed offline from the merged
# evidence (battle 9ccc312c51d95bfe, rqid 12). Slot 0 = trapped:true, slot 1 = maybeTrapped:true,
# no forceSwitch, two live bench mons. No live replay is involved.
MAYBE_TRAPPED_REQ = "request_doubles_maybe_trapped.json"


def _req(name: str = MAYBE_TRAPPED_REQ) -> BattleRequest:
    return BattleRequest.model_validate(json.loads((FIXTURES / name).read_text()))


# --------------------------------------------------------------------------------------------
# RED 1 -- parsing: the flag must survive the model at all (today it is silently dropped)
# --------------------------------------------------------------------------------------------

def test_active_slot_parses_maybe_trapped_alias():
    slot = ActiveSlot.model_validate({"moves": [], "maybeTrapped": True})
    assert slot.maybe_trapped is True


def test_active_slot_maybe_trapped_defaults_none_when_absent():
    slot = ActiveSlot.model_validate({"moves": []})
    assert slot.maybe_trapped is None


def test_absent_maybe_trapped_is_omitted_from_model_dump():
    """Behaviour-scoping guard. Several callers serialize this model with
    ``model_dump(..., exclude_none=False)`` (eval/decision_capture.py, eval/room_raw_replay.py) and
    eval/decision_profile.py HASHES that dump. A bare ``maybe_trapped=None`` emitted on every board
    would silently move those hashes -- it did: adding the field without ``exclude_if`` moved the
    pinned C3-proof board from 3d246b21910204ec to 1a15d8ded702c464 and broke
    test_profile_fixtures.py. Omitting the key when the server did not send it is what keeps every
    non-maybeTrapped board byte-identical to before this slice."""
    dumped = ActiveSlot.model_validate({"moves": []}).model_dump(by_alias=True, exclude_none=False)
    assert "maybeTrapped" not in dumped


def test_present_maybe_trapped_is_kept_in_model_dump():
    """The converse: when the server DID send it, it must survive serialization -- otherwise the
    flag could not be captured in a decision trace or replayed."""
    dumped = ActiveSlot.model_validate({"moves": [], "maybeTrapped": True}).model_dump(
        by_alias=True, exclude_none=False
    )
    assert dumped["maybeTrapped"] is True


def test_frozen_gate_b_request_round_trips_both_flags():
    """The real frozen request: slot 0 explicitly trapped, slot 1 only maybeTrapped."""
    req = _req()
    assert req.force_switch is None, "rqid 12 was a VOLUNTARY turn, not a force-switch"
    assert req.active[0].trapped is True
    assert req.active[0].maybe_trapped is None
    assert req.active[1].trapped is None
    assert req.active[1].maybe_trapped is True


# --------------------------------------------------------------------------------------------
# RED 2 -- enumeration: no voluntary switch for a maybeTrapped slot
# --------------------------------------------------------------------------------------------

def test_no_voluntary_switch_for_maybe_trapped_slot():
    """The actual defect. Slot 1 is maybeTrapped and the bench is live, so before the fix this
    returned switch actions -- the illegal action the server rejected."""
    req = _req()
    live_bench = [p for p in req.side.pokemon if not p.active and "fnt" not in p.condition]
    assert live_bench, "fixture must have a live bench or the test proves nothing"
    assert _voluntary_switches(req, 1) == []


def test_frozen_request_enumerates_no_switch_at_all():
    """End-to-end over the real board: with slot 0 trapped and slot 1 maybeTrapped, the joint
    action space must contain no switch on either slot."""
    for ja in enumerate_my_actions(_req()):
        assert ja.slot0.kind != "switch"
        assert ja.slot1.kind != "switch"


# --------------------------------------------------------------------------------------------
# Regression -- must stay GREEN: explicit `trapped` behaviour is unchanged
# --------------------------------------------------------------------------------------------

def test_explicit_trapped_slot_still_returns_no_switches():
    assert _voluntary_switches(_req(), 0) == []


def test_untrapped_slot_still_enumerates_bench_switches():
    """A slot with NEITHER flag must be unaffected: it still offers every live bench mon."""
    req = _req("request_doubles_moves.json")
    for idx, slot in enumerate(req.active):
        if slot is None or slot.trapped or slot.maybe_trapped:
            continue
        expected = {
            p.ident.split(": ", 1)[-1]
            for p in req.side.pokemon
            if not p.active and "fnt" not in p.condition
        }
        got = {a.target_ident for a in _voluntary_switches(req, idx)}
        assert got == expected
        break
    else:
        raise AssertionError("fixture has no untrapped slot to check")


# --------------------------------------------------------------------------------------------
# Regression -- must stay GREEN: the FORCED path is deliberately untouched.
# Trapping does not block a forced replacement after a faint; filtering there would delete legal
# forced switches and hang the battle (the class of bug test_actions.py already regresses).
# --------------------------------------------------------------------------------------------

def test_forced_switch_still_offers_bench_even_when_trapped():
    raw = json.loads((FIXTURES / MAYBE_TRAPPED_REQ).read_text())
    raw["forceSwitch"] = [True, False]
    req = BattleRequest.model_validate(raw)
    forced = [a for a in _slot_move_actions(0, req) if a.kind == "switch"]
    assert forced, "a forced replacement must still be offered for a trapped slot"


def test_forced_switch_still_offers_bench_even_when_maybe_trapped():
    raw = json.loads((FIXTURES / MAYBE_TRAPPED_REQ).read_text())
    raw["forceSwitch"] = [False, True]
    req = BattleRequest.model_validate(raw)
    forced = [a for a in _slot_move_actions(1, req) if a.kind == "switch"]
    assert forced, "a forced replacement must still be offered for a maybeTrapped slot"


# --------------------------------------------------------------------------------------------
# Guard for the ROOT CAUSE: silently dropped request fields.
#
# The defect was not "we mishandled maybeTrapped" -- it was "we never saw it". `extra="forbid"` is
# deliberately NOT used (an unknown future server field would then crash the bot mid-battle), so
# this test is the safety net instead: it fails when the pinned sim can emit a slot field that is
# neither modelled nor explicitly acknowledged below.
#
# Field set derived from the pinned sim f8ac140, from BOTH:
#   * the declared return type of getMoveRequestData (sim/global-types.ts:298-301), and
#   * every `data.<field> =` assignment inside getMoveRequestData (sim/pokemon.ts).
# The union is used because the declared type is INCOMPLETE -- the body also assigns maybeLocked,
# canTerastallize, canMegaEvoX, canMegaEvoY, canDynamax and maxMoves.
# --------------------------------------------------------------------------------------------

# The sim commit SIM_REQUEST_SLOT_FIELDS below was transcribed from. The set is a HAND
# TRANSCRIPTION and is valid ONLY for this commit -- it is not derived at test time, deliberately:
# the sim clone lives outside this repo (~/.cache/showdownbot/pokemon-showdown) and does not exist
# in CI, so reading it here would make this guard skip (vacuous) or flaky. Instead
# test_sim_field_set_is_anchored_to_the_recorded_pin below fails if the project's recorded pin ever
# moves away from this commit, which is what forces the set to be re-derived.
SIM_FIELDS_DERIVED_FROM_COMMIT = "f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5"

SIM_REQUEST_SLOT_FIELDS = frozenset({
    "moves",
    "trapped",
    "maybeTrapped",
    "maybeDisabled",
    "maybeLocked",
    "canMegaEvo",
    "canMegaEvoX",
    "canMegaEvoY",
    "canTerastallize",
    "canUltraBurst",
    "canZMove",
    "canDynamax",
    "maxMoves",
})

# Known to the sim, deliberately NOT modelled by ActiveSlot. Each entry needs a reason: this
# allowlist exists so the test fails on a NEW/unknown field, not so gaps can accumulate silently.
# Closing these is explicitly OUT OF SCOPE for this slice.
UNMODELLED_WITH_REASON = {
    # Display/UX hints about which moves the client should grey out. The bot re-derives
    # legality from `moves[].disabled`, so these add nothing to action enumeration.
    "maybeDisabled": "advisory move-greying hint; legality comes from moves[].disabled",
    "maybeLocked": "advisory lock hint; the bot follows the server's move list instead",
    # Mechanics that do not exist in the formats this bot plays (gen9 VGC / Champions Reg-MA).
    "canUltraBurst": "gen7 Ultra Necrozma only; not reachable in supported formats",
    "canZMove": "gen7 Z-moves; not reachable in supported formats",
    "canDynamax": "gen8 Dynamax; not reachable in supported formats",
    "maxMoves": "gen8 Dynamax move list; only present alongside canDynamax",
    # Gen-6 split Mega stones (Charizard/Mewtwo X-Y). The supported Mega path uses canMegaEvo;
    # modelling the split variants is a separate, deliberate piece of work.
    "canMegaEvoX": "gen6 split Mega (X); supported Mega path uses canMegaEvo",
    "canMegaEvoY": "gen6 split Mega (Y); supported Mega path uses canMegaEvo",
}


def _recorded_showdown_pin() -> str:
    """The sim commit this repo records that its eval runs play against. Read from the in-repo
    provenance file rather than hardcoded a second time, so there is exactly one source of truth.
    Fails closed: a missing file or missing key must never let the anchor pass silently."""
    provenance = Path(__file__).resolve().parents[2] / "config" / "eval" / "provenance.yaml"
    assert provenance.is_file(), (
        f"cannot read the recorded sim pin: {provenance} does not exist. This anchor must fail "
        "closed -- without it SIM_REQUEST_SLOT_FIELDS could silently go stale."
    )
    for line in provenance.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        if key.strip() == "showdown_commit":
            pin = value.strip().strip('"').strip("'")
            assert pin, f"showdown_commit in {provenance} is empty"
            return pin
    raise AssertionError(
        f"no `showdown_commit` key in {provenance} -- the sim pin anchor cannot be verified, and "
        "this test fails closed rather than passing on an unverifiable set."
    )


def test_sim_field_set_is_anchored_to_the_recorded_pin():
    """SIM_REQUEST_SLOT_FIELDS is a HAND TRANSCRIPTION of one specific sim commit. If the pin moves
    and the transcription does not, this guard keeps passing while the new sim emits a field nobody
    modelled -- pydantic drops it, and that is precisely the root cause of the Gate B SAFETY-FAIL,
    now with false assurance on top. So: pin moved => this test fails.

    The sim checkout is deliberately NOT read here (it does not exist in CI, so the test would skip
    or go flaky); the in-repo recorded pin is the anchor instead."""
    recorded = _recorded_showdown_pin()
    derived_from = SIM_FIELDS_DERIVED_FROM_COMMIT
    # Accept full-SHA vs short-SHA on either side by comparing a normalized common prefix.
    n = min(len(recorded), len(derived_from))
    assert n >= 7, f"implausibly short sim commit id: {recorded!r} vs {derived_from!r}"
    assert recorded[:n].lower() == derived_from[:n].lower(), (
        f"the recorded pokemon-showdown pin has MOVED: config/eval/provenance.yaml records "
        f"{recorded!r}, but SIM_REQUEST_SLOT_FIELDS was transcribed from "
        f"{derived_from!r}.\n"
        "SIM_REQUEST_SLOT_FIELDS must now be RE-DERIVED from the new sim, from BOTH:\n"
        "  1. the declared return type of getMoveRequestData in sim/global-types.ts, AND\n"
        "  2. every `data.<field> =` assignment in the body of getMoveRequestData in "
        "sim/pokemon.ts\n"
        "     (the declared type is incomplete -- the body assigns strictly more fields).\n"
        "Then re-review UNMODELLED_WITH_REASON: a field that is newly emitted, or that newly "
        "matters in a supported format, must be modelled on ActiveSlot rather than allowlisted. "
        "Finally update SIM_FIELDS_DERIVED_FROM_COMMIT to the new pin."
    )


def test_active_slot_models_or_acknowledges_every_sim_request_field():
    modelled = set()
    for name, field in ActiveSlot.model_fields.items():
        modelled.add(field.alias or name)
        modelled.add(name)
    unhandled = {
        f for f in SIM_REQUEST_SLOT_FIELDS
        if f not in modelled and f not in UNMODELLED_WITH_REASON
    }
    assert not unhandled, (
        f"request slot field(s) {sorted(unhandled)} are emitted by the pinned sim but are neither "
        "modelled on ActiveSlot nor listed in UNMODELLED_WITH_REASON. pydantic IGNORES unknown "
        "keys, so such a field is silently dropped -- exactly the root cause of the Gate B "
        "SAFETY-FAIL. Model it, or add it to the allowlist with a reason."
    )


def test_trapping_flags_are_actually_modelled():
    """The two fields this slice exists for must be real, not allowlisted away."""
    aliases = {f.alias or n for n, f in ActiveSlot.model_fields.items()}
    assert {"trapped", "maybeTrapped"} <= aliases
    assert not ({"trapped", "maybeTrapped"} & set(UNMODELLED_WITH_REASON))
