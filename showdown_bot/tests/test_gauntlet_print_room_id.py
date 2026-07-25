"""--print-room-id emits exactly one unambiguous, machine-readable marker line to stdout as
soon as the room exists, distinct from the gauntlet's normal human-readable summary output, and
does NOT exit the process afterward -- the battle keeps running (owner-approved
test-infrastructure exception, 2026-07-25 M1-plan review, second pass; see
docs/plans/2026-07-25-phase3-m1-connect-spectate.md, Task 33/34).
"""
from __future__ import annotations

import re

from showdown_bot.client import gauntlet

_MARKER_RE = re.compile(r"^SHOWDOWN_ROOM_ID=(\S+)$", re.MULTILINE)


def test_print_room_id_marker_line_format():
    line = gauntlet.format_room_id_marker("battle-gen9vgc2025regg-1")
    assert line == "SHOWDOWN_ROOM_ID=battle-gen9vgc2025regg-1"
    match = _MARKER_RE.search(line)
    assert match is not None
    assert match.group(1) == "battle-gen9vgc2025regg-1"


def test_move_delay_seconds_defaults_to_zero_when_not_the_e2e_scenario():
    # The pacing delay is opt-in -- a normal gauntlet run (no --print-room-id/--move-delay-seconds)
    # must not slow down, only the E2E seeding path deliberately does.
    assert gauntlet.DEFAULT_MOVE_DELAY_SECONDS == 0.0
