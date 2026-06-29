from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from showdown_bot.engine.calc.models import CalcMon
from showdown_bot.engine.format_config import FormatConfig
from showdown_bot.engine.state import BattleState, PokemonState

# Mode -> role mapping, fixed up front so game_mode (Task 7) cannot invert it:
#   "offense" preset = max offense + min defense (hits hardest / takes most).
#   "defense" preset = max bulk (survives most / hardest to KO).
OFFENSE = "offense"
DEFENSE = "defense"


@dataclass(frozen=True)
class SpreadPreset:
    nature: str
    evs: dict[str, int]
    items: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SpeciesSpreads:
    offense: SpreadPreset
    defense: SpreadPreset

    def preset(self, mode: str) -> SpreadPreset:
        return self.offense if mode == OFFENSE else self.defense


@dataclass
class SpreadBook:
    default: SpeciesSpreads
    species: dict[str, SpeciesSpreads] = field(default_factory=dict)

    def get(self, species: str) -> SpeciesSpreads:
        return self.species.get(species, self.default)


def _preset_from_dict(data: dict) -> SpreadPreset:
    return SpreadPreset(
        nature=data.get("nature", "Hardy"),
        evs={k: int(v) for k, v in (data.get("evs") or {}).items()},
        items=list(data.get("items") or []),
    )


def _spreads_from_dict(data: dict) -> SpeciesSpreads:
    return SpeciesSpreads(
        offense=_preset_from_dict(data["offense"]),
        defense=_preset_from_dict(data["defense"]),
    )


def load_spread_book(path: Path) -> SpreadBook:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    default = _spreads_from_dict(data["default"])
    species = {name: _spreads_from_dict(d) for name, d in (data.get("species") or {}).items()}
    return SpreadBook(default=default, species=species)


@dataclass
class SetHypothesis:
    """A worst-case set model for one observed Pokemon.

    Known facts (revealed ability, moves, item) constrain the hypothesis; the
    offense/defense presets fill the unknown EV/nature/item dimensions.
    """

    species: str
    level: int = 50
    ability: str | None = None
    known_moves: set[str] = field(default_factory=set)
    item: str | None = None  # set only if revealed/known
    item_known: bool = False
    tera_type: str | None = None
    boosts: dict[str, int] = field(default_factory=dict)
    status: str | None = None
    spreads: SpeciesSpreads | None = None

    def item_candidates(self, mode: str) -> list[str]:
        if self.item_known:
            return [self.item] if self.item else []
        if self.spreads is None:
            return []
        return list(self.spreads.preset(mode).items)

    def _to_calc_mon(self, mode: str, *, move: str | None = None) -> CalcMon:
        preset = self.spreads.preset(mode) if self.spreads else SpreadPreset("Hardy", {})
        if self.item_known:
            item = self.item
        else:
            item = preset.items[0] if preset.items else None
        return CalcMon(
            species=self.species,
            level=self.level,
            item=item,
            nature=preset.nature,
            evs=dict(preset.evs),
            ability=self.ability,
            boosts=dict(self.boosts) if self.boosts else None,
            status=self.status,
            tera_type=self.tera_type,
            move=move,
        )

    def as_attacker(self, mode: str = OFFENSE, *, move: str) -> CalcMon:
        """This mon attacking. Default ``offense`` = hits hardest."""
        return self._to_calc_mon(mode, move=move)

    def as_defender(self, mode: str = DEFENSE) -> CalcMon:
        """This mon defending. Default ``defense`` = max bulk / hardest to KO."""
        return self._to_calc_mon(mode)


def hypothesis_from_state(mon: PokemonState, book: SpreadBook) -> SetHypothesis:
    return SetHypothesis(
        species=mon.species,
        level=mon.level,
        ability=mon.ability,
        known_moves=set(mon.moves),
        item=mon.item,
        item_known=mon.item_known,
        tera_type=mon.tera_type if mon.terastallized else None,
        boosts=dict(mon.boosts),
        status=mon.status,
        spreads=book.get(mon.species),
    )


def build_hypotheses(
    state: BattleState,
    format_config: FormatConfig,
    side: str,
    *,
    book: SpreadBook | None = None,
) -> dict[str, SetHypothesis]:
    """Build worst-case set hypotheses for every active mon on ``side``."""
    if book is None:
        book = load_spread_book(format_config.meta_path("default_spreads"))
    return {
        slot: hypothesis_from_state(mon, book)
        for slot, mon in state.side(side).items()
    }


def load_likely_sets(path: Path, *, is_valid_species=None) -> dict[str, SpeciesSpreads]:
    """Curated probable opponent sets. Returns {to_id(species): SpeciesSpreads}
    with both presets = the single likely set. Keys are canonicalized via to_id;
    when ``is_valid_species`` is given, an unknown species key raises (fail loud).
    Missing file -> empty. nature/evs are required; item is optional (no prior)."""
    from showdown_bot.engine.state import to_id

    if not Path(path).exists():
        return {}
    with Path(path).open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    out: dict[str, SpeciesSpreads] = {}
    for name, entry in (data.get("species") or {}).items():
        if is_valid_species is not None and not is_valid_species(name):
            raise ValueError(f"likely_sets: unknown species key {name!r}")
        if "nature" not in entry or "evs" not in entry:
            raise ValueError(f"likely_sets: {name!r} missing nature/evs")
        item = entry.get("item")
        preset = SpreadPreset(
            nature=entry["nature"],
            evs={k: int(v) for k, v in (entry.get("evs") or {}).items()},
            items=[item] if item else [],
        )
        out[to_id(name)] = SpeciesSpreads(offense=preset, defense=preset)
    return out
