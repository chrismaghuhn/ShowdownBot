from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from showdown_bot.eval.room_dump import read_room_log_frames


_HERO = re.compile(r"HeuristicBot\d*")
_VILLAIN = re.compile(r"BaselineBot\d*")


def _id(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _lines(frames):
    for frame in frames:
        for line in frame.splitlines():
            if line:
                yield line.rstrip("\r")


def _slot_and_species(field: str):
    match = re.match(r"^(p[12])([ab]):\s*(.+)$", field)
    return None if match is None else (match.group(1), match.group(2), _id(match.group(3)))


@dataclass(frozen=True)
class LogFeatures:
    hero_side: str
    hero_lead: tuple[str, str] | str
    opponent_lead: tuple[str, str] | str
    hero_speed_control: tuple[str, ...] | str
    opponent_speed_control: tuple[str, ...] | str


def resolve_room_log_path(room_raw_dir, room_raw_path) -> Path:
    if not room_raw_path:
        raise ValueError("result row has no room_raw_path")
    base = str(room_raw_path).replace("\\", "/").rsplit("/", 1)[-1]
    for name in (base, base + ".gz"):
        candidate = Path(room_raw_dir) / name
        if candidate.is_file():
            return candidate
    raise ValueError(f"room log {base} not found under {room_raw_dir}")


def classify_room_log(path) -> LogFeatures:
    players = {}
    leads = {"p1": {}, "p2": {}}
    invalid_lead = {"p1": False, "p2": False}
    speed = {"p1": set(), "p2": set()}
    complete = False
    last_move_side = None
    for line in _lines(read_room_log_frames(path)):
        parts = line.split("|")
        tag = parts[1] if len(parts) > 1 else ""
        if tag == "player" and len(parts) > 3 and parts[2] in {"p1", "p2"}:
            players[parts[2]] = parts[3]
        elif tag == "turn" and len(parts) > 2 and parts[2] == "1":
            complete = True
        elif tag in {"switch", "drag"} and not complete and len(parts) > 2:
            parsed = _slot_and_species(parts[2])
            if parsed is not None:
                side, slot, species = parsed
                if tag == "drag" or slot in leads[side]:
                    invalid_lead[side] = True
                else:
                    leads[side][slot] = species
        elif tag == "move" and len(parts) > 2:
            parsed = _slot_and_species(parts[2])
            last_move_side = None if parsed is None else parsed[0]
        elif tag == "-sidestart" and len(parts) > 3 and _id(parts[3]) == "movetailwind":
            target = parts[2][:2]
            if target in speed:
                speed[target].add("tailwind")
        elif tag == "-fieldstart" and len(parts) > 2 and _id(parts[2]) == "movetrickroom":
            speed["p1"].add("trick_room")
            speed["p2"].add("trick_room")
        elif tag in {"-boost", "-unboost"} and len(parts) > 4 and _id(parts[3]) == "spe":
            parsed = _slot_and_species(parts[2])
            target_side = None if parsed is None else parsed[0]
            if target_side is not None and tag == "-boost" and last_move_side == target_side:
                speed[target_side].add("speed_boost")
            elif target_side is not None and tag == "-unboost" and last_move_side in speed \
                    and last_move_side != target_side:
                speed[last_move_side].add("speed_reduction")
        elif tag in {"win", "tie"}:
            complete = True
    hero_slots = [slot for slot, name in players.items() if _HERO.fullmatch(name)]
    villain_slots = [slot for slot, name in players.items() if _VILLAIN.fullmatch(name)]
    hero_side = hero_slots[0] if len(hero_slots) == 1 and len(villain_slots) == 1 \
        and hero_slots[0] != villain_slots[0] else "unavailable"

    def lead(side):
        return (leads[side]["a"], leads[side]["b"]) \
            if not invalid_lead[side] and set(leads[side]) == {"a", "b"} else "unavailable"

    if hero_side == "unavailable":
        return LogFeatures(hero_side, "unavailable", "unavailable", "unavailable", "unavailable")
    opponent_side = "p2" if hero_side == "p1" else "p1"
    return LogFeatures(hero_side, lead(hero_side), lead(opponent_side),
                       tuple(sorted(speed[hero_side])), tuple(sorted(speed[opponent_side])))
