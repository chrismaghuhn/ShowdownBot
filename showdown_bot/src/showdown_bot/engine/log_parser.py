from __future__ import annotations

from dataclasses import dataclass, field

from showdown_bot.protocol.messages import parse_incoming

_HP_COLOR_SUFFIX = frozenset("ryg")

# Sentinel distinguishing "HP arg present but unparseable" from "HP arg genuinely absent" --
# see parse_log_line's _hp() helper for why the distinction is load-bearing.
_HP_MALFORMED = object()


def parse_hp_integer(token: str, *, allow_color_suffix: bool = False) -> int:
    """Parse a Showdown HP token.

    Numerator tokens must be strictly numeric. Denominator tokens may carry an
    optional single-letter Showdown color marker (r/y/g) immediately after the digits.
    """
    s = token.strip()
    if allow_color_suffix and len(s) >= 2 and s[-1] in _HP_COLOR_SUFFIX and s[:-1].isdigit():
        s = s[:-1]
    if not s.isdigit():
        raise ValueError(f"invalid HP integer: {token!r}")
    return int(s)


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
        if not parts:
            raise ValueError(f"invalid HP condition: {condition!r}")
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
            current = parse_hp_integer(cur_s)
            maximum = parse_hp_integer(max_s, allow_color_suffix=True)
        else:
            current = parse_hp_integer(hp_part)
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

    def _pokemon(idx: int = 0) -> PokemonId | None:
        if idx >= len(positional):
            return None
        token = str(positional[idx]).strip()
        if not token or ":" not in token:
            return None
        return PokemonId.parse(token)

    def _hp(idx: int) -> HpStatus | None | object:
        """Returns a parsed ``HpStatus``, ``None`` if the arg slot is genuinely absent/blank, or
        the ``_HP_MALFORMED`` sentinel if the slot is present but fails to parse.

        (review finding) The two failure modes are NOT interchangeable: an HP-defining event
        (``-damage``/``-heal``/``-sethp``) whose token is present-but-garbled must drop the
        WHOLE event, matching ``_pokemon()``'s existing precedent -- silently keeping it with
        ``hp=None`` let a real hit (e.g. "Thunderbolt") get paired downstream with a fabricated
        ``post_hp == pre_hp`` "no damage happened" record instead of being excluded as unknown.
        """
        if idx >= len(positional) or not str(positional[idx]).strip():
            return None
        try:
            return HpStatus.parse(positional[idx])
        except ValueError:
            return _HP_MALFORMED

    if prefix in ("switch", "drag"):
        pokemon = _pokemon(0)
        if pokemon is None:
            return None
        # HP is supplementary on a switch (species/side tracking is the point of the event), so
        # a malformed token here is treated the same as absent -- unlike -damage/-heal/-sethp
        # below, where HP is the entire point and a malformed token drops the whole event.
        hp = _hp(2)
        return LogEvent(
            type="switch",
            pokemon=pokemon,
            details=positional[1] if len(positional) > 1 else None,
            hp=None if hp is _HP_MALFORMED else hp,
            tags=tags,
            raw=raw,
        )

    if prefix == "-damage":
        pokemon = _pokemon(0)
        if pokemon is None:
            return None
        hp = _hp(1)
        if hp is _HP_MALFORMED:
            return None
        return LogEvent(
            type="damage",
            pokemon=pokemon,
            hp=hp,
            tags=tags,
            raw=raw,
        )

    if prefix == "-heal":
        pokemon = _pokemon(0)
        if pokemon is None:
            return None
        hp = _hp(1)
        if hp is _HP_MALFORMED:
            return None
        return LogEvent(
            type="heal",
            pokemon=pokemon,
            hp=hp,
            tags=tags,
            raw=raw,
        )

    if prefix == "-sethp":
        pokemon = _pokemon(0)
        if pokemon is None:
            return None
        hp = _hp(1)
        if hp is _HP_MALFORMED:
            return None
        return LogEvent(
            type="sethp",
            pokemon=pokemon,
            hp=hp,
            tags=tags,
            raw=raw,
        )

    if prefix in ("-boost", "-unboost"):
        pokemon = _pokemon(0)
        if pokemon is None:
            return None
        amount = None
        if len(positional) > 2:
            try:
                amount = (1 if prefix == "-boost" else -1) * int(positional[2])
            except ValueError:
                amount = None
        return LogEvent(
            type="boost",
            pokemon=pokemon,
            value=positional[1] if len(positional) > 1 else None,
            amount=amount,
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
        amount = None
        if positional:
            try:
                amount = int(positional[0])
            except ValueError:
                amount = None
        return LogEvent(type="turn", amount=amount, raw=raw)

    if prefix == "move":
        pokemon = _pokemon(0)
        if pokemon is None:
            return None
        # (review finding) a move event with no move name must drop the whole event too --
        # keeping it with details=None let downstream code (validate.py's `pending_move.details
        # or ""`) fabricate an empty move name, which then got fed to the damage calculator as
        # if "" were a real move and compared against a genuine HP delta.
        move_name = positional[1] if len(positional) > 1 else None
        if not move_name or not move_name.strip():
            return None
        return LogEvent(
            type="move",
            pokemon=pokemon,
            details=move_name,
            target=PokemonId.parse(positional[2])
            if len(positional) > 2 and ":" in positional[2]
            else None,
            tags=tags,
            raw=raw,
        )

    if prefix == "faint":
        pokemon = _pokemon(0)
        if pokemon is None:
            return None
        return LogEvent(type="faint", pokemon=pokemon, raw=raw)

    if prefix == "-status":
        pokemon = _pokemon(0)
        if pokemon is None:
            return None
        return LogEvent(
            type="status",
            pokemon=pokemon,
            value=positional[1] if len(positional) > 1 else None,
            tags=tags,
            raw=raw,
        )

    if prefix == "-curestatus":
        pokemon = _pokemon(0)
        if pokemon is None:
            return None
        return LogEvent(
            type="curestatus",
            pokemon=pokemon,
            value=positional[1] if len(positional) > 1 else None,
            tags=tags,
            raw=raw,
        )

    if prefix == "-enditem":
        pokemon = _pokemon(0)
        if pokemon is None:
            return None
        return LogEvent(
            type="enditem",
            pokemon=pokemon,
            value=positional[1] if len(positional) > 1 else None,
            tags=tags,
            raw=raw,
        )

    if prefix == "detailschange":
        pokemon = _pokemon(0)
        if pokemon is None:
            return None
        return LogEvent(
            type="detailschange",
            pokemon=pokemon,
            details=positional[1] if len(positional) > 1 else None,
            tags=tags,
            raw=raw,
        )

    if prefix == "-mega":
        pokemon = _pokemon(0)
        if pokemon is None:
            return None
        return LogEvent(
            type="mega",
            pokemon=pokemon,
            value=positional[1] if len(positional) > 1 else None,
            details=positional[2] if len(positional) > 2 else None,
            tags=tags,
            raw=raw,
        )

    if prefix == "-item":
        pokemon = _pokemon(0)
        if pokemon is None:
            return None
        return LogEvent(
            type="item",
            pokemon=pokemon,
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
