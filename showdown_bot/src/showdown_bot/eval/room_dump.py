"""room_raw capture + battle-log normalization for the T1a seeded bit-stability proof.

The gauntlet accumulates every raw protocol frame of a battle in ``_Client.room_raw``.
For the seed proof we dump that stream per battle, then compare two same-seed battles.

Two battles created with the *same* injected sim seed differ only in **server-session
metadata** — the room id (a global counter), wall-clock ``|t:|`` timestamps, timer
``|inactive|`` messages, chat/join/leave, and UI html. Those are not sim outputs.
``normalize_battle_log`` strips exactly those and keeps every sim-outcome line (moves,
damage, crits, misses, statuses, boosts, faints, turn markers, requests, win), so the
comparison proves the *battle* is bit-identical without being fooled by session noise.
"""
from __future__ import annotations

import difflib
import os

# PS protocol tags that carry nondeterministic server-session metadata, never sim
# outcomes. Everything NOT in this set is kept, so a real battle divergence can never
# be hidden by normalization.
_METADATA_TAGS = frozenset({
    "t:",            # unix timestamp
    ":",             # server timestamp header (|:|<epoch>)
    "inactive",      # battle timer messages (wall-clock dependent)
    "inactiveoff",
    "player",        # |player|p1|NAME|avatar|rating — name/avatar are session metadata
    "j", "J", "join",
    "l", "L", "leave",
    "n", "name",     # renames
    "c", "c:", "chat",
    "uhtml", "uhtmlchange", "html", "raw",  # UI frames
    "queryresponse",
    "",              # empty tag (blank |-only lines)
})


def _iter_lines(frames):
    for raw in frames:
        for line in raw.split("\n"):
            yield line.rstrip("\r")


def normalize_battle_log(frames):
    """Return the sim-relevant protocol lines, dropping server-session metadata.

    ``frames`` is a list of raw protocol strings (each may be multi-line), i.e. the
    contents of ``_Client.room_raw[room]``.
    """
    out = []
    for line in _iter_lines(frames):
        if not line:
            continue
        if line.startswith(">"):
            # room id header (>battle-<format>-<counter>) — session metadata
            continue
        if line.startswith("|"):
            tag = line.split("|", 2)[1] if line.count("|") >= 1 else ""
            if tag in _METADATA_TAGS:
                continue
        out.append(line)
    return out


def compare_battle_logs(frames_a, frames_b):
    """Compare two battles' normalized logs.

    Returns ``(identical, diff)``: ``identical`` True iff the normalized sim protocols
    are byte-equal; ``diff`` is a unified diff string (empty when identical).
    """
    a = normalize_battle_log(frames_a)
    b = normalize_battle_log(frames_b)
    if a == b:
        return True, ""
    diff = "\n".join(difflib.unified_diff(a, b, fromfile="run_a", tofile="run_b", lineterm=""))
    return False, diff


def dump_room_raw(dump_dir, name, room, frames):
    """Write a battle's raw frames to ``<dump_dir>/<name>__<room>.log``; return the path."""
    os.makedirs(dump_dir, exist_ok=True)
    safe_room = room.replace("/", "_").replace("\\", "_")
    path = os.path.join(dump_dir, f"{name}__{safe_room}.log")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(frames))
    return path
