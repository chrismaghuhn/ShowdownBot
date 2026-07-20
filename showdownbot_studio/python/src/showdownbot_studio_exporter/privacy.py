"""portable-pseudonymous-v1 privacy transforms."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any

PRIVACY_PROFILE = {
    "profile": "portable-pseudonymous-v1",
    "chat": "excluded",
    "private_messages": "excluded",
    "player_names": "seat-pseudonyms",
    "source_url": "excluded",
    "raw_source_included": False,
}

_EXCLUDED_LINE_PREFIXES = (
    "|c|",
    "|c:",
    "|chat|",
    "|pm|",
    "|j|",
    "|l|",
    "|n|",
    "|title|",
    "|t:|",
    "|inactive|",
    "|player|",
)

_URL_RE = re.compile(r"https?://[^\s\"']+", re.IGNORECASE)
_WIN_ABS_PATH_RE = re.compile(r"[A-Za-z]:\\[^\s\"']+")
_UNIX_ABS_PATH_RE = re.compile(r"/(?:Users|home|tmp)/[^\s\"']+")


def is_excluded_protocol_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    for prefix in _EXCLUDED_LINE_PREFIXES:
        if stripped.startswith(prefix):
            return True
    if _URL_RE.search(stripped):
        return True
    if _WIN_ABS_PATH_RE.search(stripped) or _UNIX_ABS_PATH_RE.search(stripped):
        return True
    return False


def _seat_from_side_id(side_id: str | None) -> str:
    if side_id in ("p1", "p2"):
        return side_id
    return "p1"


def pseudonymize_request_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Parse |request| JSON and replace cleartext names with seat labels."""
    out = deepcopy(payload)
    side = out.get("side")
    if isinstance(side, dict):
        seat = _seat_from_side_id(side.get("id"))
        side["name"] = seat
        pokemon = side.get("pokemon")
        if isinstance(pokemon, list):
            for mon in pokemon:
                if not isinstance(mon, dict):
                    continue
                ident = mon.get("ident")
                if isinstance(ident, str) and ":" in ident:
                    slot_part = ident.split(":", 1)[0].strip()
                    if slot_part in ("p1", "p2"):
                        mon["ident"] = f"{slot_part}:"
                    else:
                        mon["ident"] = f"{seat}:"
    return out


def strip_state_summary_nicknames(state_summary: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(state_summary)
    sides = out.get("sides")
    if not isinstance(sides, dict):
        return out
    for side_slots in sides.values():
        if not isinstance(side_slots, dict):
            continue
        for mon in side_slots.values():
            if isinstance(mon, dict) and "nickname" in mon:
                mon.pop("nickname", None)
    return out


def scrub_string_literals(text: str) -> str:
    """Remove URL/abs-path substrings from free text (defensive)."""
    text = _URL_RE.sub("", text)
    text = _WIN_ABS_PATH_RE.sub("", text)
    text = _UNIX_ABS_PATH_RE.sub("", text)
    return text


def parse_request_line(line: str) -> dict[str, Any] | None:
    if not line.startswith("|request|"):
        return None
    payload_text = line[len("|request|") :]
    return json.loads(payload_text)


def format_request_line(payload: dict[str, Any]) -> str:
    return "|request|" + json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
