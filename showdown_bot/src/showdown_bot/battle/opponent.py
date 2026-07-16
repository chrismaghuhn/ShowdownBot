from __future__ import annotations

import math
import os

from dataclasses import dataclass, field

from showdown_bot.battle.resolve import PlannedAction
from showdown_bot.engine.mega_form import MegaForm, mega_form_for
from showdown_bot.engine.moves import MoveMeta, get_move_meta, to_id
from showdown_bot.engine.spread_lookup import lookup_opp_set
from showdown_bot.engine.state import BattleState, FieldState, PokemonState
from showdown_bot.engine.typechart import effectiveness

# Revealed support moves we explicitly model as opponent "lines".
SUPPORT_MOVE_IDS = {
    "trickroom", "tailwind", "fakeout", "spore", "ragepowder",
    "followme", "icywind", "willowisp", "widerguard", "wideguard",
}
_SUPPORT_PRIORITY = [
    "trickroom", "tailwind", "fakeout", "ragepowder", "followme",
    "icywind", "spore", "willowisp", "wideguard",
]

# Representative STAB move per type for opponents whose moves are unrevealed.
STAB_MOVE = {
    "Normal": "Hyper Voice", "Fire": "Heat Wave", "Water": "Surf",
    "Grass": "Energy Ball", "Electric": "Thunderbolt", "Ice": "Ice Beam",
    "Fighting": "Close Combat", "Poison": "Sludge Bomb", "Ground": "Earth Power",
    "Flying": "Air Slash", "Psychic": "Psychic", "Bug": "Bug Buzz",
    "Rock": "Rock Slide", "Ghost": "Shadow Ball", "Dragon": "Draco Meteor",
    "Dark": "Dark Pulse", "Steel": "Flash Cannon", "Fairy": "Moonblast",
}


class SpeciesDex:
    """Memoized species -> typing, backed by the calc bridge dex."""

    def __init__(self, backend=None) -> None:
        if backend is None:
            from showdown_bot.engine.calc.client import SubprocessCalcBackend

            backend = SubprocessCalcBackend()
        self.backend = backend
        self._cache: dict[str, list[str]] = {}

    def types(self, species: str) -> list[str]:
        if species not in self._cache:
            self._cache[species] = self.backend.types_batch([species])[0]
        return self._cache[species]

    def to_id(self, species: str) -> str:
        """Normalize a species name to its id form -- the same Showdown "toID"
        transform as ``engine.moves.to_id`` / ``engine.state.to_id`` /
        ``engine.items.to_id`` (pure string normalization, no backend lookup).

        Added (2b-2.5a wiring fix) so ``learning/features.py``'s
        ``ctx.dex.to_id(...)`` species-id feature columns
        (``slot{1,2}_actor_species_id`` / ``switch_target_species_id`` /
        ``target_species_id_if_known``) actually resolve real ids once a real
        ``SpeciesDex`` is threaded into the export path, instead of silently
        falling back to their sentinel on ``AttributeError`` (this method did
        not exist before -- ``SpeciesDex`` only exposed ``.types()``).
        """
        return to_id(species)

    def close(self) -> None:
        """Close the backing calc backend (idempotent). Per-battle teardown seam
        (2b-2.5a Kaggle-OOM fix) — see PersistentCalcBackend.close."""
        self.backend.close()


@dataclass
class OppResponse:
    """One candidate opponent joint response for one ply."""

    actions: list[PlannedAction]
    label: str
    flags: set[str] = field(default_factory=set)
    weight: float = 1.0  # likelihood weight (set from protect priors)
    response_id: str = ""  # f"{label}|mega={none|0|1}"; "" only for pre-I7b-A construction sites
    foe_mega_slot: int | None = None  # opp slot (0/1) this response assumes Mega'd this turn, else None


def _types_of(mon: PokemonState | None, dex: SpeciesDex | None) -> list[str]:
    if mon is None:
        return []
    if getattr(mon, "types", None):
        return list(mon.types)
    if dex is not None and getattr(mon, "species", None):
        try:
            return list(dex.types(mon.species))
        except Exception:  # noqa: BLE001
            return []
    return []


def _damage_score(
    meta: MoveMeta, attacker: PokemonState, target_mon: PokemonState | None, dex: SpeciesDex | None
) -> float:
    """Cheap damage proxy: base_power x STAB x type-effectiveness (x accuracy if
    known). Far better than raw base power for picking an opponent's threat."""
    score = float(meta.base_power)
    mtype = meta.move_type
    if mtype:
        if mtype in _types_of(attacker, dex):
            score *= 1.5  # STAB
        tgt_types = _types_of(target_mon, dex)
        if tgt_types:
            score *= effectiveness(mtype, tgt_types)
    # TODO: accuracy is not yet carried on MoveMeta; multiply by accuracy/100 once
    # the generator exposes it, so risky low-accuracy moves aren't over-valued.
    acc = getattr(meta, "accuracy", None)
    if isinstance(acc, (int, float)) and 0 < acc <= 100:
        score *= acc / 100.0
    return score


def best_damaging_move(
    mon: PokemonState, dex: SpeciesDex | None, *, target_mon: PokemonState | None = None
) -> MoveMeta:
    """Strongest plausible attack vs ``target_mon`` by the damage proxy (base
    power x STAB x type effectiveness), else a STAB fallback from species typing."""
    metas = [get_move_meta(n) for n in mon.move_names]
    damaging = [m for m in metas if m.is_damaging]
    if damaging:
        return max(damaging, key=lambda m: _damage_score(m, mon, target_mon, dex))
    if dex is not None:
        for t in dex.types(mon.species):
            if t in STAB_MOVE:
                return get_move_meta(STAB_MOVE[t])
    return get_move_meta("Tackle")


def revealed_support(mon: PokemonState) -> MoveMeta | None:
    revealed = {to_id(n) for n in mon.move_names}
    for sid in _SUPPORT_PRIORITY:
        if sid in revealed:
            return get_move_meta(sid)
    return None


def _alive_slots(side_mons: dict[str, PokemonState]) -> list[str]:
    return [
        slot
        for slot, mon in side_mons.items()
        if not mon.fainted and mon.hp_fraction > 0 and slot in ("a", "b")
    ]


def foe_mega_eligibility(
    state: BattleState, opp_side: str, *, opp_sets: dict | None,
) -> dict[str, MegaForm]:
    """Limited-view Mega eligibility for the opponent's active slots (I7b §9.1).

    A slot is eligible iff the side has not already spent its Mega this battle
    AND EITHER (a) the mon's held item is revealed (``item_known`` and not
    ``item_lost``) and resolves via ``mega_form_for``, OR (b) a curated
    ``opp_sets`` preset for that species lists an item that resolves via
    ``mega_form_for`` -- the SAME per-format curated hypothesis source
    ``lookup_opp_set`` already uses, never the real battling opponent's actual
    team file (which this function has no parameter to accept at all).

    No ``book`` parameter (Rev. 3 audit finding 6d, corrected): unlike
    ``speed_for_species`` (where ``book``-derived ``hypothesis_from_state`` is
    the PRIMARY foe-speed source and ``opp_sets`` is only a fallback --
    confirmed by reading ``engine/speed.py:169-176``), ``SpreadBook`` exposes
    no item/held-item hypothesis at all, only nature/EV presets -- there is
    nothing for an eligibility check to read from it. Accepting an unused
    ``book`` parameter here would be a dead, YAGNI parameter; earlier plan
    drafts wrongly claimed eligibility draws from "curated opp_sets/book"
    symmetrically with the speed path, which does not hold for this function.
    """
    if state.side_mega_spent.get(opp_side, False):
        return {}
    result: dict[str, MegaForm] = {}
    for slot, mon in state.sides.get(opp_side, {}).items():
        if slot not in ("a", "b") or mon.fainted or mon.hp_fraction <= 0:
            continue
        if mon.item_known and not mon.item_lost and mon.item:
            form = mega_form_for(mon.species, mon.item)
            if form is not None:
                result[slot] = form
                continue
        preset = lookup_opp_set(opp_sets, mon) if opp_sets else None
        if preset is None:
            continue
        for candidate_item in list(preset.offense.items) + list(preset.defense.items):
            form = mega_form_for(mon.species, candidate_item)
            if form is not None:
                result[slot] = form
                break
    return result


class InvalidOppMegaClickRateError(ValueError):
    """SHOWDOWN_OPP_MEGA_CLICK_RATE is set but is not a finite float in [0.0, 1.0]."""


def opp_mega_click_rate() -> float:
    raw = os.environ.get("SHOWDOWN_OPP_MEGA_CLICK_RATE", "0.35")
    try:
        value = float(raw)
    except ValueError as exc:
        raise InvalidOppMegaClickRateError(
            f"SHOWDOWN_OPP_MEGA_CLICK_RATE={raw!r} is not a float"
        ) from exc
    if not math.isfinite(value) or not (0.0 <= value <= 1.0):
        raise InvalidOppMegaClickRateError(
            f"SHOWDOWN_OPP_MEGA_CLICK_RATE={value!r} must be a finite value in [0.0, 1.0]"
        )
    return value


class OpponentResponseCapError(ValueError):
    """format_config.mega is in play and the number of mandatory reserve
    classes (no-mega + one per eligible foe Mega slot) exceeds max_candidates.
    Raised BEFORE response expansion/truncation -- never silently drops a
    required class (spec §9.5)."""


def _item_for_speed(mon, curated_items):
    """Item that determines Scarf speed. Revealed item / known-absence beats the
    curated item; the curated item is used only when the item is unknown."""
    if getattr(mon, "item_lost", False):
        return None
    if mon.item_known:
        return mon.item
    return curated_items[0] if curated_items else None


def _opponent_speed(mon, field, opp_side, *, speed_oracle, book, opp_sets):
    """Resolver speed for an opponent mon: the realistic likely-set point for a
    curated species (Scarf-aware), else the pessimistic opponent_range.max.

    Looks up the curated preset via ``lookup_opp_set`` (base-species-id aware),
    not a raw ``to_id(mon.species)`` key, so an already-observed Mega evolution
    (``mon.species`` = post-Mega display name, ``mon.base_species_id`` = the
    pre-Mega base id that ``opp_sets`` is actually keyed by) still resolves to
    its curated set instead of silently falling back to the pessimistic max."""
    preset_spreads = lookup_opp_set(opp_sets, mon) if opp_sets else None
    use_likely = (
        os.environ.get("SHOWDOWN_OPP_SPEED", "1") != "0"
        and preset_spreads is not None
    )
    if use_likely:
        preset = preset_spreads.defense
        return speed_oracle.likely_speed(
            mon, field, opp_side, preset, _item_for_speed(mon, preset.items)
        )
    return speed_oracle.opponent_range(mon, field, opp_side, book=book).max


DEFAULT_MAX_CANDIDATES = 5


def predict_responses(
    state: BattleState,
    our_side: str,
    opp_side: str,
    *,
    speed_oracle=None,
    book=None,
    dex: SpeciesDex | None = None,
    field: FieldState | None = None,
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
    priors=None,
    threatened_slots: set[str] | None = None,
    opp_sets: dict | None = None,
    foe_mega_eligibility: dict[str, MegaForm] | None = None,
    opp_mega_click_rate: float | None = None,
) -> list[OppResponse]:
    """A small set of plausible opponent joint responses for one-ply scoring.

    Candidates: aggressive (focus each of our slots), a Protect read, a revealed
    support line, and a pivot/switch. Opponent speed is the pessimistic upper
    bound (assume they outspeed) when a SpeedOracle+book is provided.

    When ``priors`` (ProtectPriors) is given, each response gets a likelihood
    ``weight``: the Protect read carries the species' Protect prior (bumped if we
    threaten a KO on it -- the KO-line discount), the rest split the remainder.
    """
    field = field or state.field
    opp_mons = state.sides.get(opp_side, {})
    opp_slots = _alive_slots(opp_mons)
    our_slots = _alive_slots(state.sides.get(our_side, {})) or ["a"]
    if not opp_slots:
        return []

    def opp_speed(slot: str) -> int:
        if speed_oracle is None or book is None:
            return 0
        return _opponent_speed(
            opp_mons[slot], field, opp_side, speed_oracle=speed_oracle, book=book, opp_sets=opp_sets
        )

    def attack(slot: str, target_slot: str) -> PlannedAction:
        target_mon = state.sides.get(our_side, {}).get(target_slot)
        return PlannedAction(
            side=opp_side,
            slot=slot,
            kind="move",
            speed=opp_speed(slot),
            move=best_damaging_move(opp_mons[slot], dex, target_mon=target_mon),
            target=(our_side, target_slot),
            is_ours=False,
        )

    def protect(slot: str) -> PlannedAction:
        return PlannedAction(
            side=opp_side, slot=slot, kind="protect", speed=opp_speed(slot),
            move=get_move_meta("Protect"), is_ours=False,
        )

    def support(slot: str, meta: MoveMeta) -> PlannedAction:
        target = (our_side, our_slots[0]) if meta.hits_foe else None
        return PlannedAction(
            side=opp_side, slot=slot, kind="move", speed=opp_speed(slot),
            move=meta, target=target, is_ours=False,
        )

    def switch(slot: str) -> PlannedAction:
        return PlannedAction(
            side=opp_side, slot=slot, kind="switch", speed=opp_speed(slot), is_ours=False,
        )

    responses: list[OppResponse] = []

    # Aggressive: focus-fire each of our alive slots (cap at 2).
    for tgt in our_slots[:2]:
        responses.append(
            OppResponse([attack(s, tgt) for s in opp_slots], label=f"aggro->{tgt}")
        )

    # Protect read on the first opp slot, partner attacks.
    if len(opp_slots) >= 1:
        acts = [protect(opp_slots[0])]
        acts += [attack(s, our_slots[0]) for s in opp_slots[1:]]
        responses.append(OppResponse(acts, label="protect+aggro", flags={"protect_read"}))

    # Revealed support line on whichever slot has one.
    for s in opp_slots:
        meta = revealed_support(opp_mons[s])
        if meta is not None:
            acts = [support(s, meta)]
            acts += [attack(o, our_slots[0]) for o in opp_slots if o != s]
            responses.append(OppResponse(acts, label=f"support:{meta.id}", flags={"support"}))
            break

    # Pivot: first opp slot switches (no damage this turn), partner attacks.
    if len(opp_slots) >= 2:
        acts = [switch(opp_slots[0]), attack(opp_slots[1], our_slots[0])]
        responses.append(OppResponse(acts, label="pivot", flags={"switch"}))

    mega_active = bool(foe_mega_eligibility) and opp_mega_click_rate is not None

    if not mega_active:
        # Byte-identical to pre-I7b-A behavior, with response_id populated
        # (harmless -- consumed by nothing that affects weight/choice today).
        responses = responses[:max_candidates]
        for r in responses:
            r.response_id = f"{r.label}|mega=none"
        if priors is not None and responses:
            _apply_protect_prior_split(responses, opp_mons, opp_slots, priors, threatened_slots)
        return responses

    # --- I7b mega-aware pipeline (spec §9.4/§9.5): cap-check -> expand -> weight -> ---
    # --- coverage-preserving truncate -> renormalize                                ---

    # Cap check FIRST, before any expansion (spec §9.5 binding order; Rev. 1 checked
    # this only after expansion -- corrected here).
    classes = {"none"} | {str(0 if s == "a" else 1) for s in foe_mega_eligibility}
    if len(classes) > max_candidates:
        raise OpponentResponseCapError(
            f"format_config.mega requires {len(classes)} reserve classes "
            f"({sorted(classes)}) but max_candidates={max_candidates}"
        )

    for r in responses:
        r.response_id = f"{r.label}|mega=none"
    if priors is not None and responses:
        _apply_protect_prior_split(responses, opp_mons, opp_slots, priors, threatened_slots)
    else:
        n = len(responses) or 1
        for r in responses:
            r.weight = 1.0 / n

    expanded: list[OppResponse] = []
    for family in responses:
        expanded.append(family)
        # A slot whose action IN THIS RESPONSE is a switch cannot also Mega this
        # turn -- Mega Evolution requires a move-class action. Exclude it from
        # this family's twin expansion (Codex review: pivot/switch must never
        # grow a Mega variant for the switching slot).
        acting_move_slots = {a.slot for a in family.actions if a.kind != "switch"}
        eligible_here = sorted(acting_move_slots & foe_mega_eligibility.keys())
        family_mega_weight = family.weight * opp_mega_click_rate
        family.weight *= (1.0 - opp_mega_click_rate)
        n_split = len(eligible_here) or 1
        for slot in eligible_here:
            slot_index = 0 if slot == "a" else 1
            twin = OppResponse(
                actions=list(family.actions),
                label=family.label,
                flags=set(family.flags),
                weight=family_mega_weight / n_split,
                response_id=f"{family.label}|mega={slot_index}",
                foe_mega_slot=slot_index,
            )
            expanded.append(twin)

    total = sum(r.weight for r in expanded)
    if total > 0:
        for r in expanded:
            r.weight /= total

    def _class_of(r: OppResponse) -> str:
        return "none" if r.foe_mega_slot is None else str(r.foe_mega_slot)

    reserved: dict[str, OppResponse] = {}
    for cls in classes:
        candidates = [r for r in expanded if _class_of(r) == cls]
        reserved[cls] = sorted(candidates, key=lambda r: (-r.weight, r.response_id))[0]
    reserved_ids = {id(r) for r in reserved.values()}
    remaining_budget = max_candidates - len(reserved)
    unreserved = sorted(
        (r for r in expanded if id(r) not in reserved_ids),
        key=lambda r: (-r.weight, r.response_id),
    )
    kept = list(reserved.values()) + unreserved[:remaining_budget]
    kept.sort(key=lambda r: r.response_id)

    total_kept = sum(r.weight for r in kept)
    if total_kept > 0:
        for r in kept:
            r.weight /= total_kept

    return kept


def _apply_protect_prior_split(responses, opp_mons, opp_slots, priors, threatened_slots) -> None:
    threatened_slots = threatened_slots or set()
    pslot = opp_slots[0]
    p_protect = priors.rate(
        opp_mons[pslot].species,
        threatened=pslot in threatened_slots,
        consecutive=opp_mons[pslot].consecutive_protect,
    )
    non_protect = [r for r in responses if "protect" not in r.label]
    for r in responses:
        if "protect" in r.label:
            r.weight = p_protect
        else:
            r.weight = (1.0 - p_protect) / len(non_protect) if non_protect else 0.0
    total = sum(r.weight for r in responses)
    if total > 0:
        for r in responses:
            r.weight /= total
