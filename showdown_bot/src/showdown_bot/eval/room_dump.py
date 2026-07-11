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
import gzip
import hashlib
import os
import re

# The gauntlet gives each run's bots a random numeric suffix (HeuristicBot5519). That
# suffix is a per-run session label, not a sim output, and it leaks into `|win|` /
# `|request|`. For CROSS-run comparison (T1b) canonicalize it away, exactly like the
# room id. WITHIN a run (T1a) names are identical, so default comparison omits this.
GAUNTLET_NAME_SUBS = [
    (re.compile(r"HeuristicBot\d+"), "HeuristicBot"),
    (re.compile(r"BaselineBot\d+"), "BaselineBot"),
]

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


def normalize_battle_log(frames, *, name_subs=None):
    """Return the sim-relevant protocol lines, dropping server-session metadata.

    ``frames`` is a list of raw protocol strings (each may be multi-line), i.e. the
    contents of ``_Client.room_raw[room]``. ``name_subs`` (optional) is a list of
    ``(compiled_regex, replacement)`` applied to each surviving line — used for
    cross-run comparison to canonicalize per-run player-name suffixes (see
    ``GAUNTLET_NAME_SUBS``). Default ``None`` = T1a behavior, unchanged.
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
        if name_subs:
            for pattern, repl in name_subs:
                line = pattern.sub(repl, line)
        out.append(line)
    return out


def compare_battle_logs(frames_a, frames_b, *, name_subs=None):
    """Compare two battles' normalized logs.

    Returns ``(identical, diff)``: ``identical`` True iff the normalized sim protocols
    are byte-equal; ``diff`` is a unified diff string (empty when identical). Pass
    ``name_subs`` for cross-run comparison (canonicalize per-run name suffixes).
    """
    a = normalize_battle_log(frames_a, name_subs=name_subs)
    b = normalize_battle_log(frames_b, name_subs=name_subs)
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


def read_room_log_frames(path) -> list:
    """Read a dumped room_raw log (plain ``.log`` or gzipped ``.log.gz``) back into the
    ``frames`` shape ``normalize_battle_log`` expects (T4c R2: shared by
    ``eval/report.py``'s row<->log re-derivation; mirrors the convention
    ``tools/kaggle/kernel_payload.py``'s ``_read_room_log_frames`` already established for the
    Kaggle-side identity check).

    ``dump_room_raw`` writes a file as ``"\\n".join(frames)``, so reading the whole file back
    as a single-element list round-trips correctly -- ``normalize_battle_log`` re-splits on
    ``"\\n"`` internally regardless of the original per-frame boundaries.
    """
    path = str(path)
    if path.endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return [fh.read()]
    with open(path, "r", encoding="utf-8") as fh:
        return [fh.read()]


def normalized_room_log_sha256(frames) -> str:
    """sha256 hex over the normalized room log (T4c R1/R2 shared recipe).

    This is the canonical recipe both the gauntlet write site
    (``client.gauntlet._normalized_room_log_sha256``, which computes it in-process from
    frames already in hand and degrades to ``None`` on any exception) and the report
    re-derivation path (``eval.report``, which reads the frames back from a dumped log via
    ``read_room_log_frames``) must agree on byte-for-byte:

      1. ``normalize_battle_log(frames, name_subs=GAUNTLET_NAME_SUBS)`` -- strips
         server-session metadata (room id, timestamps, chat/join/leave, UI html) and
         canonicalizes the per-run ``HeuristicBot<N>``/``BaselineBot<N>`` numeric suffix.
      2. ``"\\n".join(normalized_lines).encode("utf-8")`` -- then ``hashlib.sha256(...)
         .hexdigest()``.

    Raises on failure (unlike the gauntlet write site's ``None``-on-exception wrapper) --
    callers that need the "never fails the battle record" tolerance wrap this themselves.
    """
    normalized = normalize_battle_log(frames, name_subs=GAUNTLET_NAME_SUBS)
    return hashlib.sha256("\n".join(normalized).encode("utf-8")).hexdigest()
