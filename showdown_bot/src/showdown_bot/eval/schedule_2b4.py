"""2b-4 Task 3 schedules: determinism-gate + dev-strength schedules for the gated reranker
override agent (``heuristic_reranker``, 2b-4 Task 2). Mirrors ``eval.datagen_2b25a``'s pattern
(a thin generator module over ``panel_schedule.generate_dev_schedule`` + a hash-pinning test
against the committed YAML, per ``test_t4_matrix.py``/``test_datagen_2b25a.py``'s convention).

**Why ONE schedule per purpose, not a "hero-agent" schedule field:** ``eval.schedule.Schedule``
rows encode ONLY the opponent side (``opp_policy``/``opp_team_path``) + ``seed_index`` -- there
is no per-row hero-agent field, and the HERO agent is a run-time choice
(``SHOWDOWN_HERO_AGENT``, read by ``cli.run_schedule``; see that module and
``tools/kaggle/kernel_payload.py``'s ``run_gated_override_determinism``/``_strength``), not a
schedule-authoring concern. So:

- the determinism gate runs ``2b4_determinism_v001.yaml`` TWICE on fresh servers (Channel A)
  with the SAME seed_base and ``hero_agent="heuristic_reranker"`` (override ON) both times, then
  ``eval.identity.compare_identity``s the two result-row lists for byte identity.
- the dev-strength gate runs ``2b4_devstrength_v001.yaml`` TWICE with the SAME seed_base: once
  ``hero_agent="heuristic"`` (baseline heuristic), once ``hero_agent="heuristic_reranker"``
  (override). Same schedule + same seeds + same opponent (``max_damage``, the standard
  fixed-benchmark opponent -- see ``battle/baselines.py``) on both runs is exactly what T5's
  ``eval.pairing.pair_runs`` expects for "the same evaluation conditions": ``schedule_hash``/
  ``seed_base``/``panel_hash``/``format_id`` equal across the two runs, ``config_hash`` differing
  (it does -- ``SHOWDOWN_RERANKER_OVERRIDE`` is BEHAVIOR_AFFECTING and only appears in the
  override run's env, see ``eval.config_env``). This is the "TWO runs of ONE schedule"
  resolution of the plan's paired-comparison design question: it reuses ``pair_runs``'s existing
  same-schedule/different-config_hash contract directly instead of inventing a two-schedule
  side-by-side format the loader cannot express.

DETERMINISM_SEEDS_PER_CELL=8 x 3 panel_v001 dev teams = 24 rows (within the plan's 20-30 range).
DEVSTRENGTH_SEEDS_PER_CELL=50 x 3 panel_v001 dev teams = 150 rows (the T5/PokéAgent >=150-battle
floor for a single paired arm; the controller may scale this up before spending Kaggle time).
"""
from __future__ import annotations

from showdown_bot.eval.panel_schedule import generate_dev_schedule
from showdown_bot.eval.schedule import Schedule

HERO_TEAM = "teams/fixed_team.txt"
# The standard fixed-benchmark opponent (battle/baselines.py's max_damage_choice; T4's matrix
# and 2b-2.5a's datagen both treat it as one of the two "informative" reference policies).
BASELINE_POLICY = "max_damage"

DETERMINISM_SEEDS_PER_CELL = 8   # x 3 dev teams = 24 rows
DEVSTRENGTH_SEEDS_PER_CELL = 50  # x 3 dev teams = 150 rows

_SCHEDULE_RELPATHS = {
    "determinism": "config/eval/schedules/2b4_determinism_v001.yaml",
    "devstrength": "config/eval/schedules/2b4_devstrength_v001.yaml",
}


def generate_determinism_schedule(panel, *, teams_root=".") -> Schedule:
    """24-row schedule (8 seeds/cell x 3 panel_v001 dev teams), hero=fixed_team vs the
    baseline villain -- the Channel-A double-run identity check's fixture."""
    return generate_dev_schedule(
        panel, hero_team_path=HERO_TEAM, policies=[BASELINE_POLICY],
        seeds_per_cell=DETERMINISM_SEEDS_PER_CELL, teams_root=teams_root,
    )


def generate_devstrength_schedule(panel, *, teams_root=".") -> Schedule:
    """150-row schedule (50 seeds/cell x 3 panel_v001 dev teams), hero=fixed_team vs the
    baseline villain -- run TWICE (heuristic, then heuristic_reranker) for the T5 paired
    strength comparison (see module docstring)."""
    return generate_dev_schedule(
        panel, hero_team_path=HERO_TEAM, policies=[BASELINE_POLICY],
        seeds_per_cell=DEVSTRENGTH_SEEDS_PER_CELL, teams_root=teams_root,
    )


def schedule_relpath(key: str) -> str:
    """Repo-relative path of the committed YAML for ``key`` ('determinism'/'devstrength')."""
    return _SCHEDULE_RELPATHS[key]


def generate_2b4_schedules(panel, *, teams_root=".") -> dict[str, Schedule]:
    """Both 2b-4 schedules keyed like ``schedule_relpath``'s keys."""
    return {
        "determinism": generate_determinism_schedule(panel, teams_root=teams_root),
        "devstrength": generate_devstrength_schedule(panel, teams_root=teams_root),
    }
