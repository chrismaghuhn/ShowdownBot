from __future__ import annotations

from dataclasses import dataclass, field

from showdown_bot.protocol.messages import parse_incoming


@dataclass(frozen=True)
class PokemonId:
    """An active-slot reference like ``p1a: Incineroar``."""

    raw: str
    side: str  # "p1" / "p2"
    slot: str  # "a" / "b"
    name: str  # nickname / species shown in protocol

    @classmethod
    def parse(cls, token: str) -> "PokemonId":
        ident, _, name = token.partition(":")
        ident = ident.strip()
        name = name.strip()
        side = ident[:2]
        slot = ident[2:]
        return cls(raw=token.strip(), side=side, slot=slot, name=name)


@dataclass(frozen=True)
class HpStatus:
    current: int
    maximum: int | None
    fainted: bool = False
    status: str | None = None

    @classmethod
    def parse(cls, condition: str) -> "HpStatus":
        cond = condition.strip()
        parts = cond.split()
        hp_part = parts[0]
        status = None
        fainted = False
        rest = parts[1:]
        if rest:
            if rest[0] == "fnt":
                fainted = True
            else:
                status = rest[0]
        if "/" in hp_part:
            cur_s, max_s = hp_part.split("/", 1)
            current = int(cur_s)
            maximum = int(max_s)
        else:
            current = int(hp_part)
            maximum = None
        if current == 0 and fainted:
            pass
        return cls(current=current, maximum=maximum, fainted=fainted, status=status)


@dataclass(frozen=True)
class LogEvent:
    type: str
    pokemon: PokemonId | None = None
    target: PokemonId | None = None
    details: str | None = None  # species details (switch) or move name (move)
    hp: HpStatus | None = None
    value: str | None = None  # weather/terrain/status/item/stat name
    amount: int | None = None  # boost stages, turn number
    side: str | None = None  # "p1"/"p2" for side conditions
    tags: list[str] = field(default_factory=list)  # raw trailing [from], [miss], ...
    raw: str = ""


def _split_tags(args: list[str]) -> tuple[list[str], list[str]]:
    """Separate positional args from trailing ``[...]`` annotation tags."""
    positional: list[str] = []
    tags: list[str] = []
    for a in args:
        if a.startswith("["):
            tags.append(a)
        else:
            positional.append(a)
    return positional, tags


def _clean_move_name(move: str) -> str:
    return move.removeprefix("move: ").strip()


def parse_log_line(prefix: str, args: list[str], raw: str = "") -> LogEvent | None:
    positional, tags = _split_tags(args)

    if prefix in ("switch", "drag"):
        return LogEvent(
            type="switch",
            pokemon=PokemonId.parse(positional[0]),
            details=positional[1] if len(positional) > 1 else None,
            hp=HpStatus.parse(positional[2]) if len(positional) > 2 else None,
            tags=tags,
            raw=raw,
        )

    if prefix == "-damage":
        return LogEvent(
            type="damage",
            pokemon=PokemonId.parse(positional[0]),
            hp=HpStatus.parse(positional[1]) if len(positional) > 1 else None,
            tags=tags,
            raw=raw,
        )

    if prefix == "-heal":
        return LogEvent(
            type="heal",
            pokemon=PokemonId.parse(positional[0]),
            hp=HpStatus.parse(positional[1]) if len(positional) > 1 else None,
            tags=tags,
            raw=raw,
        )

    if prefix == "-sethp":
        return LogEvent(
            type="sethp",
            pokemon=PokemonId.parse(positional[0]),
            hp=HpStatus.parse(positional[1]) if len(positional) > 1 else None,
            tags=tags,
            raw=raw,
        )

    if prefix in ("-boost", "-unboost"):
        sign = 1 if prefix == "-boost" else -1
        return LogEvent(
            type="boost",
            pokemon=PokemonId.parse(positional[0]),
            value=positional[1] if len(positional) > 1 else None,
            amount=sign * int(positional[2]) if len(positional) > 2 else None,
            tags=tags,
            raw=raw,
        )

    if prefix == "-weather":
        name = positional[0] if positional else "none"
        return LogEvent(type="weather", value=None if name == "none" else name, tags=tags, raw=raw)

    if prefix in ("-fieldstart", "-fieldend"):
        return LogEvent(
            type="fieldstart" if prefix == "-fieldstart" else "fieldend",
            value=_clean_move_name(positional[0]) if positional else None,
            tags=tags,
            raw=raw,
        )

    if prefix in ("-sidestart", "-sideend"):
        side_token = positional[0] if positional else ""
        side = side_token.split(":", 1)[0].strip()[:2]
        return LogEvent(
            type="sidestart" if prefix == "-sidestart" else "sideend",
            side=side,
            value=_clean_move_name(positional[1]) if len(positional) > 1 else None,
            tags=tags,
            raw=raw,
        )

    if prefix == "turn":
        return LogEvent(type="turn", amount=int(positional[0]) if positional else None, raw=raw)

    if prefix == "move":
        return LogEvent(
            type="move",
            pokemon=PokemonId.parse(positional[0]),
            details=positional[1] if len(positional) > 1 else None,
            target=PokemonId.parse(positional[2])
            if len(positional) > 2 and ":" in positional[2]
            else None,
            tags=tags,
            raw=raw,
        )

    if prefix == "faint":
        return LogEvent(type="faint", pokemon=PokemonId.parse(positional[0]), raw=raw)

    if prefix == "-status":
        return LogEvent(
            type="status",
            pokemon=PokemonId.parse(positional[0]),
            value=positional[1] if len(positional) > 1 else None,
            tags=tags,
            raw=raw,
        )

    if prefix == "-curestatus":
        return LogEvent(
            type="curestatus",
            pokemon=PokemonId.parse(positional[0]),
            value=positional[1] if len(positional) > 1 else None,
            tags=tags,
            raw=raw,
        )

    if prefix == "-enditem":
        return LogEvent(
            type="enditem",
            pokemon=PokemonId.parse(positional[0]),
            value=positional[1] if len(positional) > 1 else None,
            tags=tags,
            raw=raw,
        )

    if prefix == "-item":
        return LogEvent(
            type="item",
            pokemon=PokemonId.parse(positional[0]),
            value=positional[1] if len(positional) > 1 else None,
            tags=tags,
            raw=raw,
        )

    return None


def parse_log(raw_log: str) -> list[LogEvent]:
    """Parse a full Showdown battle log (sim protocol) into structured events."""
    events: list[LogEvent] = []
    for line in raw_log.splitlines():
        if not line.strip():
            continue
        for msg in parse_incoming(line):
            if not msg.prefix:
                continue
            event = parse_log_line(msg.prefix, msg.args, raw=line)
            if event is not None:
                events.append(event)
    return events
