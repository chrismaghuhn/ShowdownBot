"""2b-2.5a Kaggle datagen schedules (Task 4): four hero-team schedules, one per hero,
each a uniform 5-policy x 5-seeds/cell dev matrix against panel v001's 3 dev teams
(trickroom, sun, rain) -- 5 policies x 5 seeds x 3 opp teams = 75 rows/hero, 15 rows
per policy.

This is a UNIFORM training-diversity mix, deliberately different from ``eval.t4_matrix``'s
WEIGHTED eval matrix (5/5/3/2/2 seeds/cell, heuristic+max_damage over-weighted as the only
"informative" opponents for calibration). Here every one of the 5 ``T4_POLICIES`` gets the
same seed budget: the point of this dataset is to reactivate class-A dead reranker features
via diverse (policy x hero x opponent) coverage, not to calibrate against strong opponents,
so no policy should be starved relative to another.

Four heroes = four distinct "our side" teams (the fixed team plus each of the panel's own
3 dev-team archetypes played as hero), each facing the SAME pool of 3 panel dev teams as
opponents -- hero identity and opponent-pool identity are independent axes here, matching
``panel_schedule.generate_dev_schedule``'s contract (opponents always come from
``panel.dev_teams``; ``hero_team_path`` is caller-supplied per schedule).

``SEED_BASES`` are the per-hero ``SHOWDOWN_BATTLE_SEED_BASE`` provenance strings the Task 5
Kaggle kernel wiring pins per hero (one fresh server run per hero schedule).
"""
from __future__ import annotations

from showdown_bot.eval.panel_schedule import generate_dev_schedule
from showdown_bot.eval.schedule import Schedule
from showdown_bot.eval.t4_matrix import T4_POLICIES

HERO_TEAMS = {
    "fixed": "teams/fixed_team.txt",
    "trickroom": "teams/panel_v001/trickroom_dev.txt",
    "sun": "teams/panel_v001/sun_dev.txt",
    "rain": "teams/panel_v001/rain_dev.txt",
}
SEED_BASES = {
    "fixed": "dg25a-fixed",
    "trickroom": "dg25a-trickroom",
    "sun": "dg25a-sun",
    "rain": "dg25a-rain",
}
DATAGEN_POLICIES = list(T4_POLICIES)  # all 5 reproducible policies, uniform seed budget
DATAGEN_SEEDS_PER_CELL = 5


def generate_datagen_schedules(panel, *, teams_root=".") -> dict[str, Schedule]:
    """One 75-row uniform dev schedule per hero team, keyed by hero key (``HERO_TEAMS``
    insertion order: fixed, trickroom, sun, rain)."""
    return {
        key: generate_dev_schedule(
            panel, hero_team_path=hero_team_path, policies=DATAGEN_POLICIES,
            seeds_per_cell=DATAGEN_SEEDS_PER_CELL, teams_root=teams_root,
        )
        for key, hero_team_path in HERO_TEAMS.items()
    }


def schedule_relpath(hero_key: str) -> str:
    """Repo-relative path of the committed YAML for ``hero_key`` (a key of ``HERO_TEAMS``)."""
    return f"config/eval/schedules/datagen_2b25a_hero_{hero_key}.yaml"
