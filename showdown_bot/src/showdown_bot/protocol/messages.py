from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedMessage:
    prefix: str
    args: list[str]
    payload: str = ""
    room: str = ""


def parse_message(raw: str) -> ParsedMessage:
    line = raw.strip()
    room = ""
    if line.startswith(">"):
        room, line = line[1:].split("|", 1)
        line = "|" + line
    if not line.startswith("|"):
        return ParsedMessage(prefix="", args=[line])
    parts = line[1:].split("|")
    prefix = parts[0]
    args = parts[1:]
    payload = args[-1] if prefix == "request" and args else ""
    if prefix == "request":
        args = args[:-1]
    return ParsedMessage(prefix=prefix, args=args, payload=payload, room=room)
