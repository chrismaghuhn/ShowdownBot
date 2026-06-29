from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from showdown_bot.engine.belief.hypotheses import (
    DEFENSE,
    OFFENSE,
    SpreadBook,
    hypothesis_from_state,
    load_spread_book,
)
from showdown_bot.engine.calc.client import CalcClient
from showdown_bot.engine.calc.models import CalcMon, DamageRequest, DamageResult
from showdown_bot.engine.format_config import FormatConfig
from showdown_bot.engine.log_parser import LogEvent, parse_log
from showdown_bot.engine.state import BattleState, PokemonState, parse_details

# Tolerances expressed in HP fraction to absorb Showdown's HP rounding.
PERCENT_DEFENDER_TOLERANCE = 0.02  # opponent HP is shown in 1% steps
EXACT_DEFENDER_TOLERANCE_HP = 1.0  # our own mons: ~1 HP of integer rounding

# Indirect-damage tags that must NOT be attributed to a move's direct hit.
_INDIRECT_TAGS = ("recoil", "item:", "ability:", "psn", "brn", "Leech Seed", "Spikes")


@dataclass(frozen=True)
class KnownSet:
    species: str
    level: int = 50
    nature: str | None = None
    ability: str | None = None
    item: str | None = None
    evs: dict[str, int] = field(default_factory=dict)
    ivs: dict[str, int] | None = None


def load_known_sets(path: Path) -> dict[str, KnownSet]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out: dict[str, KnownSet] = {}
    for species, spec in data.items():
        out[species] = KnownSet(
            species=species,
            level=int(spec.get("level", 50)),
            nature=spec.get("nature"),
            ability=spec.get("ability"),
            item=spec.get("item"),
            evs={k: int(v) for k, v in (spec.get("evs") or {}).items()},
            ivs=spec.get("ivs"),
        )
    return out


@dataclass
class FieldSnapshot:
    game_type: str = "Doubles"
    weather: str | None = None
    terrain: str | None = None

    def to_payload(self) -> dict:
        payload: dict[str, object] = {"gameType": self.game_type}
        if self.weather:
            payload["weather"] = self.weather
        if self.terrain:
            payload["terrain"] = self.terrain
        return payload


def _map_terrain(name: str | None) -> str | None:
    if not name:
        return None
    return name.replace(" Terrain", "").replace("Terrain", "").strip() or None


def _map_weather(name: str | None) -> str | None:
    if not name:
        return None
    table = {
        "RainDance": "Rain",
        "Rain": "Rain",
        "SunnyDay": "Sun",
        "Sun": "Sun",
        "Sandstorm": "Sand",
        "Sand": "Sand",
        "Snow": "Snow",
        "Hail": "Hail",
    }
    return table.get(name, name)


def _field_from_state(state: BattleState) -> FieldSnapshot:
    return FieldSnapshot(
        game_type="Doubles",
        weather=_map_weather(state.field.weather),
        terrain=_map_terrain(state.field.terrain),
    )


@dataclass
class DamageInstance:
    attacker_side: str
    attacker_species: str
    defender_side: str
    defender_species: str
    move: str
    pre_hp: int
    post_hp: int
    max_hp: int
    fainted: bool
    attacker_state: PokemonState
    defender_state: PokemonState
    field: FieldSnapshot
    reported_percent: bool  # defender HP shown in 1% steps (opponent)


@dataclass
class ValidationRecord:
    instance: DamageInstance
    mode: str  # "strict" | "union"
    calc_min_frac: float
    calc_max_frac: float
    observed_frac: float
    matched: bool
    desc: str | None = None


@dataclass
class ValidationReport:
    records: list[ValidationRecord] = field(default_factory=list)

    def _bucket(self, mode: str) -> list[ValidationRecord]:
        return [r for r in self.records if r.mode == mode]

    def matched(self, mode: str) -> int:
        return sum(1 for r in self._bucket(mode) if r.matched)

    def total(self, mode: str) -> int:
        return len(self._bucket(mode))

    def ratio(self, mode: str) -> float:
        total = self.total(mode)
        return self.matched(mode) / total if total else 0.0

    def summary(self) -> str:
        lines = []
        for mode in ("strict", "union"):
            total = self.total(mode)
            if total:
                lines.append(
                    f"{mode}: {self.matched(mode)}/{total} "
                    f"({self.ratio(mode) * 100:.1f}%)"
                )
            else:
                lines.append(f"{mode}: 0/0 (n/a)")
        return " | ".join(lines)


def _is_indirect(event: LogEvent) -> bool:
    for tag in event.tags:
        body = tag.strip("[]")
        for marker in _INDIRECT_TAGS:
            if marker in body:
                return True
    return False


def _collect_instances(events: list[LogEvent]) -> list[DamageInstance]:
    """Walk the log, pairing each single-target ``move`` with its direct damage."""
    state = BattleState()
    instances: list[DamageInstance] = []

    # Buffer the damage events caused by the current move so we can drop spread
    # moves (which produce more than one direct-damage hit).
    pending_move: LogEvent | None = None
    pending: list[DamageInstance] = []

    def flush() -> None:
        if len(pending) == 1:
            instances.append(pending[0])
        pending.clear()

    for event in events:
        if event.type == "move":
            flush()
            pending_move = event
            state.apply_event(event)
            continue

        if event.type == "damage" and pending_move is not None and not _is_indirect(event):
            defender_pid = event.pokemon
            mover_pid = pending_move.pokemon
            if (
                defender_pid is not None
                and mover_pid is not None
                and not (
                    defender_pid.side == mover_pid.side
                    and defender_pid.slot == mover_pid.slot
                )
            ):
                attacker_mon = state.active(mover_pid.side, mover_pid.slot)
                defender_mon = state.active(defender_pid.side, defender_pid.slot)
                if attacker_mon and defender_mon and defender_mon.max_hp:
                    pre_hp = defender_mon.hp
                    post = event.hp
                    pending.append(
                        DamageInstance(
                            attacker_side=mover_pid.side,
                            attacker_species=attacker_mon.species,
                            defender_side=defender_pid.side,
                            defender_species=defender_mon.species,
                            move=pending_move.details or "",
                            pre_hp=pre_hp,
                            post_hp=post.current if post else pre_hp,
                            max_hp=defender_mon.max_hp,
                            fainted=bool(post and post.fainted),
                            attacker_state=_copy_mon(attacker_mon),
                            defender_state=_copy_mon(defender_mon),
                            field=_field_from_state(state),
                            reported_percent=defender_mon.max_hp == 100,
                        )
                    )
            state.apply_event(event)
            continue

        if event.type in ("turn", "switch", "faint"):
            flush()
            pending_move = None
        state.apply_event(event)

    flush()
    return instances


def _copy_mon(mon: PokemonState) -> PokemonState:
    return PokemonState(
        species=mon.species,
        nickname=mon.nickname,
        level=mon.level,
        gender=mon.gender,
        hp=mon.hp,
        max_hp=mon.max_hp,
        boosts=dict(mon.boosts),
        status=mon.status,
        item=mon.item,
        item_known=mon.item_known,
        ability=mon.ability,
        moves=set(mon.moves),
        move_names=set(mon.move_names),
        tera_type=mon.tera_type,
        terastallized=mon.terastallized,
        fainted=mon.fainted,
    )


def _mon_from_known(
    known: KnownSet, mon: PokemonState, *, move: str | None = None
) -> CalcMon:
    return CalcMon(
        species=known.species,
        level=known.level,
        item=known.item,
        nature=known.nature,
        ability=known.ability,
        evs=dict(known.evs),
        ivs=known.ivs,
        boosts=dict(mon.boosts) if mon.boosts else None,
        status=mon.status,
        tera_type=mon.tera_type if mon.terastallized else None,
        move=move,
    )


def _tolerance(instance: DamageInstance) -> float:
    if instance.reported_percent:
        return PERCENT_DEFENDER_TOLERANCE
    return EXACT_DEFENDER_TOLERANCE_HP / instance.max_hp


def _matches(instance: DamageInstance, calc_min_frac: float, calc_max_frac: float) -> tuple[bool, float]:
    tol = _tolerance(instance)
    pre_frac = instance.pre_hp / instance.max_hp
    if instance.fainted:
        # Actual damage was >= remaining HP; engine must be able to deal that.
        observed = pre_frac
        matched = (calc_max_frac + tol) >= observed
        return matched, observed
    observed = (instance.pre_hp - instance.post_hp) / instance.max_hp
    matched = (calc_min_frac - tol) <= observed <= (calc_max_frac + tol)
    return matched, observed


def validate_log(
    raw_log: str,
    *,
    calc: CalcClient,
    format_config: FormatConfig,
    known_sets: dict[str, KnownSet] | None = None,
    book: SpreadBook | None = None,
) -> ValidationReport:
    known_sets = known_sets or {}
    if book is None:
        book = load_spread_book(format_config.meta_path("default_spreads"))

    events = parse_log(raw_log)
    instances = _collect_instances(events)

    report = ValidationReport()
    for inst in instances:
        attacker_known = inst.attacker_species in known_sets
        defender_known = inst.defender_species in known_sets
        field_payload = inst.field.to_payload()

        if attacker_known and defender_known:
            attacker = _mon_from_known(
                known_sets[inst.attacker_species], inst.attacker_state, move=inst.move
            )
            defender = _mon_from_known(known_sets[inst.defender_species], inst.defender_state)
            result = calc.damage(
                DamageRequest(attacker=attacker, defender=defender, move=inst.move, field=field_payload)
            )
            cmin, cmax = _result_fracs(result)
            matched, observed = _matches(inst, cmin, cmax)
            report.records.append(
                ValidationRecord(inst, "strict", cmin, cmax, observed, matched, result.desc)
            )
        else:
            cmin, cmax, desc = _union_fracs(inst, known_sets, book, calc, field_payload)
            matched, observed = _matches(inst, cmin, cmax)
            report.records.append(
                ValidationRecord(inst, "union", cmin, cmax, observed, matched, desc)
            )

    return report


def _result_fracs(result: DamageResult) -> tuple[float, float]:
    if not result.max_hp:
        return 0.0, 0.0
    return result.min_damage / result.max_hp, result.max_damage / result.max_hp


def _union_fracs(
    inst: DamageInstance,
    known_sets: dict[str, KnownSet],
    book: SpreadBook,
    calc: CalcClient,
    field_payload: dict,
) -> tuple[float, float, str | None]:
    # Attacker: use known set if available, else worst-case offense preset.
    if inst.attacker_species in known_sets:
        attacker = _mon_from_known(
            known_sets[inst.attacker_species], inst.attacker_state, move=inst.move
        )
    else:
        att_hyp = hypothesis_from_state(inst.attacker_state, book)
        attacker = att_hyp.as_attacker(OFFENSE, move=inst.move)

    # Defender: union over plausible spreads (offense + defense presets).
    def_hyp = hypothesis_from_state(inst.defender_state, book)
    defenders = [def_hyp.as_defender(OFFENSE), def_hyp.as_defender(DEFENSE)]

    requests = [
        DamageRequest(attacker=attacker, defender=d, move=inst.move, field=field_payload)
        for d in defenders
    ]
    results = calc.damage_batch(requests)

    fracs = [_result_fracs(r) for r in results]
    cmin = min(f[0] for f in fracs)
    cmax = max(f[1] for f in fracs)
    return cmin, cmax, results[0].desc if results else None
