"""VGC-Bench raw battle-log parser (2b-5a Part A Task 1).

Reuses the existing Showdown-protocol parsers rather than reimplementing
them: ``eval.battle_parse.parse_battle_result`` re-derives winner/turns/
end_reason directly from the log (no external field is ever trusted), and
``eval.room_dump.normalized_room_log_sha256`` supplies the canonical
normalized-log hash recipe already used to bind our own result rows to their
room logs.
"""
from __future__ import annotations

import hashlib

from showdown_bot.eval.battle_parse import parse_battle_result
from showdown_bot.eval.room_dump import normalized_room_log_sha256

from .schema import VgcBenchParseError, VgcBenchRawBattle


def parse_battle(battle_id: str, epoch: int, log: str) -> VgcBenchRawBattle:
    """Parse one VGC-Bench ``(battle_id, epoch, log)`` triple.

    ``frames`` for the reused eval helpers is a single-element list holding
    the whole raw log text -- the same shape ``room_dump.read_room_log_frames``
    produces when reading a dumped room log back off disk, so
    ``normalized_room_log_sha256`` here matches byte-for-byte with the
    recipe our own row<->log binding uses.
    """
    frames = [log]
    log_lines = tuple(line.rstrip("\r") for line in log.split("\n"))

    raw_log_sha256 = hashlib.sha256(log.encode("utf-8")).hexdigest()
    normalized_log_sha256 = normalized_room_log_sha256(frames)

    result = parse_battle_result(frames)

    gametype: str | None = None
    format_name: str | None = None
    players: dict[str, str] = {}
    rules: list[str] = []

    for line in log_lines:
        if not line.startswith("|"):
            continue
        parts = line.split("|")
        tag = parts[1] if len(parts) > 1 else ""
        if tag == "gametype" and len(parts) >= 3:
            gametype = "|".join(parts[2:])
        elif tag == "player" and len(parts) >= 4:
            slot, name = parts[2], parts[3]
            if slot in ("p1", "p2") and name:
                players[slot] = name
        elif tag == "tier" and len(parts) >= 3:
            format_name = "|".join(parts[2:])
        elif tag == "rule" and len(parts) >= 3:
            rules.append("|".join(parts[2:]))

    if format_name is None:
        raise VgcBenchParseError(f"{battle_id}: missing |tier| header line")
    if gametype is None:
        raise VgcBenchParseError(f"{battle_id}: missing |gametype| header line")
    if not players:
        raise VgcBenchParseError(f"{battle_id}: missing |player| header line(s)")

    return VgcBenchRawBattle(
        battle_id=battle_id,
        epoch_seconds=int(epoch),
        raw_log_sha256=raw_log_sha256,
        normalized_log_sha256=normalized_log_sha256,
        format_name=format_name,
        gametype=gametype,
        players=tuple(sorted(players.items())),
        rules=tuple(rules),
        log_lines=log_lines,
        winner=result["winner_name"],
        is_tie=result["is_tie"],
        turns=result["turns"],
        end_reason=result["end_reason"],
    )
