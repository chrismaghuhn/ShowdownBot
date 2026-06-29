from __future__ import annotations

import re
from dataclasses import dataclass, field

from showdown_bot.engine.log_parser import LogEvent, parse_log
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
    boosts: dict[str, int] = field(default_factory=dict)
    status: str | None = None
    item: str | None = None
    item_known: bool = False
    ability: str | None = None
    moves: set[str] = field(default_factory=set)  # normalized move ids
    move_names: set[str] = field(default_factory=set)  # display names from |move|
    tera_type: str | None = None
    terastallized: bool = False
    fainted: bool = False
    types: list[str] = field(default_factory=list)
    consecutive_protect: int = 0  # trailing run of Protect-type moves used

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
    tailwind: dict[str, bool] = field(default_factory=lambda: {"p1": False, "p2": False})


@dataclass
class BattleState:
    sides: dict[str, dict[str, PokemonState]] = field(
        default_factory=lambda: {"p1": {}, "p2": {}}
    )
    field: FieldState = field(default_factory=FieldState)
    turn: int = 0

    def side(self, side: str) -> dict[str, PokemonState]:
        return self.sides[side]

    def active(self, side: str, slot: str) -> PokemonState | None:
        return self.sides.get(side, {}).get(slot)

    def apply_event(self, event: LogEvent) -> None:  # noqa: C901 - protocol dispatch
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
                if mid in _PROTECT_MOVE_IDS:
                    mon.consecutive_protect += 1
                else:
                    mon.consecutive_protect = 0
        elif et == "item":
            mon.item = event.value
            mon.item_known = True
        elif et == "enditem":
            mon.item = None
            mon.item_known = True

    @classmethod
    def from_log(cls, events: list[LogEvent]) -> "BattleState":
        state = cls()
        for event in events:
            state.apply_event(event)
        return state

    @classmethod
    def from_log_text(cls, raw_log: str) -> "BattleState":
        return cls.from_log(parse_log(raw_log))


def merge_request(req: BattleRequest, state: BattleState) -> BattleState:
    """Merge our own private knowledge (moves, exact HP, item) from a request.

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
            if cur_s.isdigit():
                mon.hp = int(cur_s)
            if max_s.isdigit():
                mon.max_hp = int(max_s)

    return state
