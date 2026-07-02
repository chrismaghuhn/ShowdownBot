"""T1c non-mirror schedule loader.

A versioned schedule = rows of (config_id, hero_team_path, opp_policy, opp_team_path,
seed_index). Loader fails fast on unknown/missing fields and on a seed_index that is not
unique + contiguous-from-0 (Channel A aligns seed_index with the server counter purely by
execution order — a gappy/duplicate index would silently misalign the seed). schedule_hash
is stable from canonical content.
"""
from __future__ import annotations

import textwrap

import pytest

import json

from showdown_bot.eval.schedule import (
    ScheduleError,
    load_schedule,
    verify_schedule_alignment,
)
from showdown_bot.eval.seeding import SeedLogError, derive_battle_seed


def _write(tmp_path, body):
    p = tmp_path / "sched.yaml"
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return str(p)


_VALID = """
    version: v001
    rows:
      - {config_id: gen9vgc2025regi, hero_team_path: teams/a.txt, opp_policy: max_damage, opp_team_path: teams/b.txt, seed_index: 1}
      - {config_id: gen9vgc2025regi, hero_team_path: teams/a.txt, opp_policy: heuristic, opp_team_path: teams/c.txt, seed_index: 0}
"""


def test_load_sorts_by_seed_index_and_parses(tmp_path):
    sched = load_schedule(_write(tmp_path, _VALID))
    assert [r.seed_index for r in sched.rows] == [0, 1]           # sorted
    assert sched.rows[0].opp_policy == "heuristic"                # seed_index 0 row
    assert sched.rows[1].opp_team_path == "teams/b.txt"
    assert sched.version == "v001"


def test_schedule_hash_stable_and_content_sensitive(tmp_path):
    h1 = load_schedule(_write(tmp_path, _VALID)).schedule_hash
    h2 = load_schedule(_write(tmp_path, _VALID)).schedule_hash
    assert h1 == h2 and h1  # stable, non-empty
    changed = _VALID.replace("teams/b.txt", "teams/z.txt")
    assert load_schedule(_write(tmp_path, changed)).schedule_hash != h1


_VALID_FORMAT = """
    version: v001
    rows:
      - {format_id: gen9vgc2025regi, hero_team_path: teams/a.txt, opp_policy: heuristic, opp_team_path: teams/c.txt, seed_index: 0}
"""


def test_format_id_preferred(tmp_path):
    sched = load_schedule(_write(tmp_path, _VALID_FORMAT))
    assert sched.rows[0].format_id == "gen9vgc2025regi"


def test_config_id_is_a_backward_compatible_alias(tmp_path):
    # _VALID uses the legacy `config_id` field -> maps onto ScheduleRow.format_id.
    sched = load_schedule(_write(tmp_path, _VALID))
    assert sched.rows[0].format_id == "gen9vgc2025regi"


def test_both_format_id_and_config_id_fail_fast(tmp_path):
    body = """
        version: v001
        rows:
          - {format_id: g, config_id: g, hero_team_path: a, opp_policy: heuristic, opp_team_path: b, seed_index: 0}
    """
    with pytest.raises(ScheduleError):
        load_schedule(_write(tmp_path, body))


def test_neither_format_id_nor_config_id_fails_fast(tmp_path):
    body = """
        version: v001
        rows:
          - {hero_team_path: a, opp_policy: heuristic, opp_team_path: b, seed_index: 0}
    """
    with pytest.raises(ScheduleError):
        load_schedule(_write(tmp_path, body))


def test_missing_field_fails_fast(tmp_path):
    body = """
        version: v001
        rows:
          - {config_id: c, hero_team_path: a, opp_policy: heuristic, seed_index: 0}
    """
    with pytest.raises(ScheduleError):
        load_schedule(_write(tmp_path, body))  # missing opp_team_path


def test_unknown_field_fails_fast(tmp_path):
    body = """
        version: v001
        rows:
          - {config_id: c, hero_team_path: a, opp_policy: heuristic, opp_team_path: b, seed_index: 0, extra: 9}
    """
    with pytest.raises(ScheduleError):
        load_schedule(_write(tmp_path, body))


def test_noncontiguous_seed_index_fails_fast(tmp_path):
    body = """
        version: v001
        rows:
          - {config_id: c, hero_team_path: a, opp_policy: heuristic, opp_team_path: b, seed_index: 0}
          - {config_id: c, hero_team_path: a, opp_policy: heuristic, opp_team_path: b, seed_index: 2}
    """
    with pytest.raises(ScheduleError):
        load_schedule(_write(tmp_path, body))


def test_duplicate_seed_index_fails_fast(tmp_path):
    body = """
        version: v001
        rows:
          - {config_id: c, hero_team_path: a, opp_policy: heuristic, opp_team_path: b, seed_index: 0}
          - {config_id: c, hero_team_path: a, opp_policy: heuristic, opp_team_path: b, seed_index: 0}
    """
    with pytest.raises(ScheduleError):
        load_schedule(_write(tmp_path, body))


def test_unknown_policy_fails_fast(tmp_path):
    body = """
        version: v001
        rows:
          - {config_id: c, hero_team_path: a, opp_policy: mystery_bot, opp_team_path: b, seed_index: 0}
    """
    with pytest.raises(ScheduleError):
        load_schedule(_write(tmp_path, body))


def test_missing_version_fails_fast(tmp_path):
    body = """
        rows:
          - {config_id: c, hero_team_path: a, opp_policy: heuristic, opp_team_path: b, seed_index: 0}
    """
    with pytest.raises(ScheduleError):
        load_schedule(_write(tmp_path, body))


def test_panel_hash_read_from_yaml(tmp_path):
    body = _VALID_FORMAT.replace("version: v001", "version: v001\n    panel_hash: pan123")
    sched = load_schedule(_write(tmp_path, body))
    assert sched.panel_hash == "pan123"


def test_panel_hash_absent_is_none(tmp_path):
    sched = load_schedule(_write(tmp_path, _VALID_FORMAT))
    assert sched.panel_hash is None


def _write_seed_log(path, base, n):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for i in range(n):
            fh.write(json.dumps(
                {"battle_index": i, "seed": derive_battle_seed(base, i), "seed_base": base}) + "\n")


def test_verify_schedule_alignment_ok(tmp_path):
    sched = load_schedule(_write(tmp_path, _VALID))          # 2 rows, seed_index 0,1
    log = tmp_path / "seeds.jsonl"
    _write_seed_log(str(log), "run2026", 2)
    records = verify_schedule_alignment(sched, str(log), "run2026")
    assert [r["battle_index"] for r in records] == [0, 1]


def test_verify_schedule_alignment_rejects_extra_battle(tmp_path):
    # A retry/extra battle -> 3 log lines for a 2-row schedule -> fail fast.
    sched = load_schedule(_write(tmp_path, _VALID))
    log = tmp_path / "seeds.jsonl"
    _write_seed_log(str(log), "run2026", 3)
    with pytest.raises(SeedLogError):
        verify_schedule_alignment(sched, str(log), "run2026")


# --- T3e P4: optional per-row team-hash provenance (NOT part of schedule identity) ---

_VALID_WITH_HASHES = """
    version: v001
    rows:
      - {format_id: gen9vgc2025regi, hero_team_path: teams/a.txt, opp_policy: heuristic, opp_team_path: teams/c.txt, seed_index: 0, hero_team_hash: hh0, opp_team_hash: oh0}
"""

_VALID_NO_HASHES = """
    version: v001
    rows:
      - {format_id: gen9vgc2025regi, hero_team_path: teams/a.txt, opp_policy: heuristic, opp_team_path: teams/c.txt, seed_index: 0}
"""


def test_team_hashes_load_when_present(tmp_path):
    sched = load_schedule(_write(tmp_path, _VALID_WITH_HASHES))
    assert sched.rows[0].hero_team_hash == "hh0"
    assert sched.rows[0].opp_team_hash == "oh0"


def test_legacy_schedule_rows_have_null_team_hashes(tmp_path):
    sched = load_schedule(_write(tmp_path, _VALID_NO_HASHES))
    assert sched.rows[0].hero_team_hash is None
    assert sched.rows[0].opp_team_hash is None


def test_schedule_hash_unchanged_by_team_hashes(tmp_path):
    # Team hashes are provenance, not identity payload -> schedule_hash must be identical.
    with_hashes = load_schedule(_write(tmp_path, _VALID_WITH_HASHES)).schedule_hash
    without = load_schedule(_write(tmp_path, _VALID_NO_HASHES)).schedule_hash
    assert with_hashes == without
