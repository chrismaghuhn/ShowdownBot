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
        head, _, rest = line[1:].partition("|")
        room = head.strip()
        line = f"|{rest}" if rest else ""
    if not line.startswith("|"):
        return ParsedMessage(prefix="", args=[line], room=room)
    parts = line[1:].split("|")
    prefix = parts[0]
    args = parts[1:]
    payload = args[-1] if prefix == "request" and args else ""
    if prefix == "request":
        args = args[:-1]
    return ParsedMessage(prefix=prefix, args=args, payload=payload, room=room)


def parse_incoming(raw: str) -> list[ParsedMessage]:
    """Parse a possibly multiline Showdown packet (room header + messages)."""
    lines = raw.split("\n")
    room = ""
    if lines and lines[0].startswith(">"):
        room = lines[0][1:].strip()
        lines = lines[1:]

    messages: list[ParsedMessage] = []
    for line in lines:
        if not line.strip():
            continue
        msg = parse_message(line)
        if room and not msg.room:
            messages.append(
                ParsedMessage(
                    prefix=msg.prefix,
                    args=msg.args,
                    payload=msg.payload,
                    room=room,
                )
            )
        else:
            messages.append(msg)
    if not messages and room:
        messages.append(ParsedMessage(prefix="", args=[], room=room))
    return messages
