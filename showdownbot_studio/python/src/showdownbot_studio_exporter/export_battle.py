"""Battle log normalization to battle.jsonl."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from .canonicalize import dumps
from .privacy import is_excluded_protocol_line, pseudonymize_request_payload, scrub_string_literals

_REPO_SRC = Path(__file__).resolve().parents[4] / "showdown_bot" / "src"
if _REPO_SRC.is_dir() and str(_REPO_SRC) not in sys.path:
    sys.path.insert(0, str(_REPO_SRC))


def _parse_log_line(line: str):
    from showdown_bot.engine.log_parser import parse_log_line as bot_parse
    from showdown_bot.protocol.messages import parse_message

    if line.startswith("|request|"):
        return None
    if line.startswith(">"):
        return None
    msg = parse_message(line)
    if not msg.prefix:
        return None
    return bot_parse(msg.prefix, msg.args, raw=line)


# LogEvent.details carries species only for these types (see log_parser.py).
_SPECIES_DETAIL_TYPES = frozenset({"switch", "detailschange"})


def _event_to_dict(event, protocol_index: int) -> dict[str, Any]:
    row: dict[str, Any] = {"protocol_index": protocol_index, "type": event.type}
    if event.pokemon is not None:
        row["pokemon"] = {
            "side": event.pokemon.side,
            "slot": event.pokemon.slot,
        }
        if event.type in _SPECIES_DETAIL_TYPES and event.details:
            row["pokemon"]["species"] = scrub_string_literals(event.details.split(",")[0].strip())
    if event.target is not None:
        row["target"] = {"side": event.target.side, "slot": event.target.slot}
    if event.details is not None and event.type not in _SPECIES_DETAIL_TYPES:
        row["details"] = scrub_string_literals(event.details)
    elif event.details is not None and event.type in _SPECIES_DETAIL_TYPES and "pokemon" not in row:
        row["details"] = scrub_string_literals(event.details)
    if event.hp is not None:
        row["hp"] = {
            "current": event.hp.current,
            "maximum": event.hp.maximum,
            "fainted": event.hp.fainted,
            "status": event.hp.status,
        }
    if event.value is not None:
        row["value"] = scrub_string_literals(event.value)
    if event.amount is not None:
        row["amount"] = event.amount
    if event.side is not None:
        row["side"] = event.side
    if event.tags:
        row["tags"] = [scrub_string_literals(t) for t in event.tags]
    return row


def export_battle_jsonl(lines: list[str]) -> bytes:
    """Export normalized battle events preserving sparse protocol_index."""
    out_lines: list[bytes] = []
    for i, line in enumerate(lines):
        if is_excluded_protocol_line(line):
            continue
        if line.startswith("|request|"):
            continue
        event = _parse_log_line(line)
        if event is None:
            continue
        row = _event_to_dict(event, i)
        out_lines.append(dumps(row) + b"\n")
    return b"".join(out_lines)


def read_battle_log(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    if text.endswith("\n"):
        text = text[:-1]
    return text.split("\n") if text else []
