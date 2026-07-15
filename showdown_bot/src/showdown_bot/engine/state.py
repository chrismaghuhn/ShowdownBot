from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field as dc_field

from showdown_bot.engine.log_parser import LogEvent, parse_hp_integer, parse_log
from showdown_bot.engine.mega_form import mega_form_for
from showdown_bot.engine.mega_reconcile import (
    MegaReconcileError,
    MegaReconcileEvent,
    ReducedLogEvent,
    reduce_log_events,
)
from showdown_bot.engine.species_meta import get_species_form_meta
from showdown_bot.models.request import BattleRequest

_BOOST_KEYS = ("atk", "def", "spa", "spd", "spe", "accuracy", "evasion")
_PROTECT_MOVE_IDS = frozenset({
    "protect", "detect", "wideguard", "quickguard", "spikyshield",
    "kingsshield", "banefulbunker", "silktrap", "burningbulwark", "maxguard",
})


def to_id(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


@dataclass
class ParsedDetails:
    species: str
    level: int = 50
    gender: str | None = None
    tera_type: str | None = None


def parse_details(details: str) -> ParsedDetails:
    parts = [p.strip() for p in details.split(",")]
    species = parts[0]
    level = 50
    gender: str | None = None
    tera_type: str | None = None
    for token in parts[1:]:
        if token.startswith("L") and token[1:].isdigit():
            level = int(token[1:])
        elif token in ("M", "F"):
            gender = token
        elif token.lower().startswith("tera:"):
            tera_type = token.split(":", 1)[1].strip()
    return ParsedDetails(species=species, level=level, gender=gender, tera_type=tera_type)


@dataclass
class PokemonState:
    species: str
    nickname: str = ""
    level: int = 50
    gender: str | None = None
    hp: int = 100
    max_hp: int | None = None
    boosts: dict[str, int] = dc_field(default_factory=dict)
    status: str | None = None
    item: str | None = None
    item_known: bool = False
    ability: str | None = None
    moves: set[str] = dc_field(default_factory=set)  # normalized move ids
    move_names: set[str] = dc_field(default_factory=set)  # display names from |move|
    tera_type: str | None = None
    terastallized: bool = False
    fainted: bool = False
    types: list[str] = dc_field(default_factory=list)
    consecutive_protect: int = 0  # trailing run of Protect-type moves used
    moved_since_switch: bool = False  # has acted since last switch-in (Fake Out gate)
    item_lost: bool = False  # item consumed / removed / knocked / activated -> known absent
    base_species_id: str = ""

    def __post_init__(self) -> None:
        if not self.base_species_id:
            self.base_species_id = to_id(self.species)

    @property
    def hp_fraction(self) -> float:
        if not self.max_hp:
            return 0.0 if self.fainted else 1.0
        return self.hp / self.max_hp


@dataclass
class FieldState:
    weather: str | None = None
    terrain: str | None = None
    trick_room: bool = False
    tailwind: dict[str, bool] = dc_field(default_factory=lambda: {"p1": False, "p2": False})


@dataclass
class BattleState:
    sides: dict[str, dict[str, PokemonState]] = dc_field(
        default_factory=lambda: {"p1": {}, "p2": {}}
    )
    field: FieldState = dc_field(default_factory=FieldState)
    side_mega_spent: dict[str, bool] = dc_field(
        default_factory=lambda: {"p1": False, "p2": False}
    )
    turn: int = 0

    def side(self, side: str) -> dict[str, PokemonState]:
        return self.sides[side]

    def active(self, side: str, slot: str) -> PokemonState | None:
        return self.sides.get(side, {}).get(slot)

    def apply_event(self, event: ReducedLogEvent) -> None:  # noqa: C901 - protocol dispatch
        if isinstance(event, MegaReconcileEvent):
            self._apply_mega_reconcile(event)
            return

        et = event.type

        if et == "turn":
            if event.amount is not None:
                self.turn = event.amount
            return

        if et == "weather":
            self.field.weather = event.value
            return

        if et == "fieldstart":
            if event.value and event.value.lower() == "trick room":
                self.field.trick_room = True
            elif event.value and event.value.lower().endswith("terrain"):
                self.field.terrain = event.value
            return

        if et == "fieldend":
            if event.value and event.value.lower() == "trick room":
                self.field.trick_room = False
            elif event.value and event.value.lower().endswith("terrain"):
                self.field.terrain = None
            return

        if et in ("sidestart", "sideend") and event.side:
            if event.value and event.value.lower() == "tailwind":
                self.field.tailwind[event.side] = et == "sidestart"
            return

        pid = event.pokemon
        if pid is None:
            return
        side = self.sides.setdefault(pid.side, {})

        if et == "switch":
            details = parse_details(event.details or pid.name)
            mon = PokemonState(
                species=details.species,
                nickname=pid.name,
                level=details.level,
                gender=details.gender,
                tera_type=details.tera_type,
            )
            if event.hp is not None:
                mon.hp = event.hp.current
                mon.max_hp = event.hp.maximum
                mon.status = event.hp.status
                mon.fainted = event.hp.fainted
            side[pid.slot] = mon
            return

        mon = side.get(pid.slot)
        if mon is None:
            # Event for a slot we have not seen switch in yet; synthesize.
            mon = PokemonState(species=pid.name, nickname=pid.name)
            side[pid.slot] = mon

        if et in ("damage", "heal", "sethp"):
            if event.hp is not None:
                mon.hp = event.hp.current
                if event.hp.maximum is not None:
                    mon.max_hp = event.hp.maximum
                mon.status = event.hp.status
                mon.fainted = event.hp.fainted
        elif et == "boost":
            if event.value in _BOOST_KEYS and event.amount is not None:
                mon.boosts[event.value] = mon.boosts.get(event.value, 0) + event.amount
        elif et == "status":
            mon.status = event.value
        elif et == "curestatus":
            mon.status = None
        elif et == "faint":
            mon.fainted = True
            mon.hp = 0
        elif et == "move":
            if event.details:
                mid = to_id(event.details)
                mon.moves.add(mid)
                mon.move_names.add(event.details)
                mon.moved_since_switch = True
                if mid in _PROTECT_MOVE_IDS:
                    mon.consecutive_protect += 1
                else:
                    mon.consecutive_protect = 0
        elif et == "item":
            mon.item = event.value
            mon.item_known = True
            mon.item_lost = False
        elif et == "enditem":
            mon.item = None
            mon.item_known = True
            mon.item_lost = True
        elif et == "detailschange":
            # Ordinary (non-Mega) permanent forme change, e.g. Zygarde-Complete
            # or Wishiwashi School. Refresh species/types/ability from
            # speciesdata; item and side_mega_spent are untouched here -- those
            # are exclusively a MegaReconcileEvent concern.
            if event.details:
                details = parse_details(event.details)
                mon.species = details.species
                form_meta = get_species_form_meta(details.species)
                if form_meta is not None:
                    mon.types = list(form_meta.types)
                    mon.ability = form_meta.ability_slot0

    def _apply_mega_reconcile(self, event: MegaReconcileEvent) -> None:
        pid = event.pokemon
        side = self.sides.setdefault(pid.side, {})
        mon = side.get(pid.slot)
        if mon is None:
            raise MegaReconcileError(f"mega_reconcile_unknown_pokemon: {pid.raw}")

        details = parse_details(event.mega_species_details)
        target_base_id = to_id(event.base_species)
        stone_id = to_id(event.stone_display)

        # Showdown allows exactly one Mega Evolution per side per battle. If
        # this side has already spent its Mega, only an EXACT replay of the
        # SAME already-applied event (same slot, same resulting species/
        # base-species/stone) is tolerated -- as an idempotent no-op. Any
        # other Mega attempt on an already-spent side (a different slot/
        # actor, or the same slot with a different stone/form) must fail
        # closed without mutating state.
        if self.side_mega_spent.get(pid.side, False):
            already_matches = (
                mon.species == details.species
                and mon.base_species_id == target_base_id
                and mon.item_known
                and to_id(mon.item or "") == stone_id
            )
            if already_matches:
                return  # idempotent replay of the same already-applied event
            raise MegaReconcileError(
                f"mega_reconcile_side_already_spent: side={pid.side!r} already "
                f"used its Mega this battle; rejecting {pid.raw} -> {details.species!r}"
            )

        snapshot = copy.deepcopy(mon)
        spent_snapshot = self.side_mega_spent.get(pid.side, False)

        try:
            # Coherence: the reconcile event's claimed actor must match the
            # Pokemon actually occupying this slot (guards against a
            # misrouted/mismatched -mega pairing reaching state application).
            if mon.base_species_id != to_id(event.base_species):
                raise MegaReconcileError(
                    f"mega_reconcile_actor_mismatch: slot={pid.raw} "
                    f"holds base_species_id={mon.base_species_id!r}, "
                    f"event claims base_species={event.base_species!r}"
                )

            mega_form = mega_form_for(event.base_species, event.stone_display)
            if mega_form is None or to_id(mega_form.form_species_name) != to_id(details.species):
                raise MegaReconcileError(
                    f"mega_reconcile_incoherent: base_species={event.base_species!r} "
                    f"stone={event.stone_display!r} details_species={details.species!r}"
                )

            if mon.item_known:
                if to_id(mon.item or "") != stone_id:
                    raise MegaReconcileError(
                        f"mega_reconcile_item_conflict: known item={mon.item!r} "
                        f"!= stone={event.stone_display!r}"
                    )
                # Known item already matches the stone: keep as-is.
            else:
                mon.item = event.stone_display
                mon.item_known = True
                mon.item_lost = False

            mon.species = details.species
            mon.base_species_id = to_id(event.base_species)
            form_meta = get_species_form_meta(details.species)
            if form_meta is not None:
                mon.types = list(form_meta.types)
                mon.ability = form_meta.ability_slot0

            # No synthetic weather here: unlike mega_projection.project_mega
            # (our own pre-decision projection), the reconcile path applies
            # OBSERVED protocol only. -weather / ability-trigger log lines
            # remain the sole authority for weather.
            self.side_mega_spent[pid.side] = True
        except MegaReconcileError:
            side[pid.slot] = snapshot
            self.side_mega_spent[pid.side] = spent_snapshot
            raise

    @classmethod
    def from_log(cls, events: list[LogEvent]) -> "BattleState":
        return cls.from_reduced_log(reduce_log_events(events))

    @classmethod
    def from_reduced_log(cls, events: list[ReducedLogEvent]) -> "BattleState":
        state = cls()
        for event in events:
            state.apply_event(event)
        return state

    @classmethod
    def from_log_text(cls, raw_log: str) -> "BattleState":
        return cls.from_log(parse_log(raw_log))


def merge_request(req: BattleRequest, state: BattleState) -> BattleState:
    """Merge our own private knowledge (moves, exact HP) from a request.

    Item truth is owned by apply_own_team_knowledge (team/spreads.py), not here.
    The requesting side is identified by ``req.side.id``. Active team members are
    mapped to active slots (a, b, ...) in listing order; revealed move ids and
    condition are merged into the existing log-derived state where possible.
    """
    side_id = req.side.id or "p1"
    side = state.sides.setdefault(side_id, {})

    by_species = {mon.species: (slot, mon) for slot, mon in side.items()}

    active_slots = ["a", "b", "c"]
    active_index = 0
    for poke in req.side.pokemon:
        details = parse_details(poke.details)
        slot_mon = by_species.get(details.species)
        if slot_mon is not None:
            slot, mon = slot_mon
        elif poke.active and active_index < len(active_slots):
            slot = active_slots[active_index]
            mon = side.get(slot)
            if mon is None or mon.species != details.species:
                mon = PokemonState(species=details.species, nickname=details.species)
                side[slot] = mon
        else:
            continue

        if poke.active:
            active_index += 1

        mon.level = details.level
        if details.gender:
            mon.gender = details.gender
        if poke.base_types and not mon.types:
            mon.types = list(poke.base_types)
        for move_id in poke.moves:
            mon.moves.add(to_id(move_id))

        cond = poke.condition
        if "/" in cond:
            cur_s, rest = cond.split("/", 1)
            max_s = rest.split()[0]
            try:
                mon.hp = parse_hp_integer(cur_s)
            except ValueError:
                pass
            try:
                mon.max_hp = parse_hp_integer(max_s, allow_color_suffix=True)
            except ValueError:
                pass

    return state
