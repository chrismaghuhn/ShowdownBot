"""T1a seed-proof helpers: room_raw dump + battle-log normalization + compare.

The proof these back: two battles created with the same injected sim seed (via the
pokemon-showdown-seeded-battle.patch) produce a bit-identical *battle protocol*. The
normalization strips only nondeterministic server-session metadata (room id, wall-clock
timestamps, timer/inactivity, chat/join/leave, UI html) — never sim-outcome lines
(moves, damage, crits, misses, faints, turn markers, win).
"""
from __future__ import annotations

from showdown_bot.eval.room_dump import (
    GAUNTLET_NAME_SUBS,
    compare_battle_logs,
    dump_room_raw,
    normalize_battle_log,
)


def test_dump_writes_joined_frames(tmp_path):
    frames = [">battle-gen9vgc2025regi-1\n|init|battle", "|move|p1a: X|Tackle|p2a: Y"]
    path = dump_room_raw(str(tmp_path), "HeroBot1234", "battle-gen9vgc2025regi-1", frames)
    text = open(path, encoding="utf-8").read()
    assert text == "\n".join(frames)


def test_normalize_drops_session_metadata_but_keeps_sim_lines():
    frames = [
        ">battle-gen9vgc2025regi-7",
        "|t:|1719800000",
        "|player|p1|HeuristicBot1234|169|",
        "|inactive|Battle timer is ON",
        "|move|p1a: Incineroar|Fake Out|p2a: Rillaboom",
        "|-damage|p2a: Rillaboom|82/100",
        "|c:|1719800001|HeuristicBot1234|gg",
        "|turn|2",
    ]
    norm = normalize_battle_log(frames)
    # sim-outcome lines survive
    assert "|move|p1a: Incineroar|Fake Out|p2a: Rillaboom" in norm
    assert "|-damage|p2a: Rillaboom|82/100" in norm
    assert "|turn|2" in norm
    # session metadata is stripped
    assert not any(line.startswith(">battle-") for line in norm)
    assert not any(line.startswith("|t:|") for line in norm)
    assert not any(line.startswith("|player|") for line in norm)
    assert not any(line.startswith("|inactive|") for line in norm)
    assert not any(line.startswith("|c:|") for line in norm)


def test_compare_identical_after_stripping_roomid_and_timestamps():
    # Same battle, two runs: differ ONLY in room id + timestamps -> must compare equal.
    run_a = [">battle-gen9vgc2025regi-1", "|t:|100", "|move|p1a: X|Tackle|p2a: Y", "|turn|1"]
    run_b = [">battle-gen9vgc2025regi-2", "|t:|999", "|move|p1a: X|Tackle|p2a: Y", "|turn|1"]
    identical, diff = compare_battle_logs(run_a, run_b)
    assert identical is True
    assert diff == ""


def test_compare_detects_a_real_battle_divergence():
    # A genuine sim difference (different damage roll) must NOT be hidden.
    run_a = [">battle-x-1", "|t:|100", "|-damage|p2a: Y|82/100", "|turn|1"]
    run_b = [">battle-x-2", "|t:|100", "|-damage|p2a: Y|75/100", "|turn|1"]
    identical, diff = compare_battle_logs(run_a, run_b)
    assert identical is False
    assert "82/100" in diff and "75/100" in diff


def test_name_subs_canonicalize_per_run_suffix():
    # Cross-run compare (T1b): the random bot-name suffix (HeuristicBot5519 vs
    # HeuristicBot1044) is a per-run session label, not a sim output. name_subs
    # canonicalizes it; the win line otherwise leaks it.
    a = ["|win|HeuristicBot5519", "|move|p1a: X|Tackle|p2a: Y"]
    b = ["|win|HeuristicBot1044", "|move|p1a: X|Tackle|p2a: Y"]
    assert compare_battle_logs(a, b)[0] is False                       # without: differ
    assert compare_battle_logs(a, b, name_subs=GAUNTLET_NAME_SUBS)[0] is True  # with: identical

def test_name_subs_do_not_hide_real_divergence():
    # A real difference must survive name canonicalization.
    a = ["|win|HeuristicBot5519", "|-damage|p2a: Y|82/100"]
    b = ["|win|HeuristicBot1044", "|-damage|p2a: Y|70/100"]
    assert compare_battle_logs(a, b, name_subs=GAUNTLET_NAME_SUBS)[0] is False
