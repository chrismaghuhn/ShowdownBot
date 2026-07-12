# src/showdown_bot/analysis/generalisation/observations.py
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from showdown_bot.analysis.generalisation.catalog import (
    classify_novelty, static_speed_profile,
)
from showdown_bot.analysis.generalisation.contracts import GeneralisationError, sha256_id
from showdown_bot.analysis.generalisation.log_features import classify_room_log, resolve_room_log_path
from showdown_bot.eval.room_dump import normalized_room_log_sha256, read_room_log_frames


class ObservationError(GeneralisationError):
    pass


@dataclass(frozen=True)
class MatchupObservation:
    schema_version: str
    analysis_id: str
    policy_hash: str
    generalisation_manifest_hash: str
    exposure_hash: str
    speed_control_taxonomy_hash: str
    run_id: str
    battle_id: str
    schedule_hash: str
    seed_base: str
    seed_index: int
    seed: str
    config_id: str
    config_hash: str
    git_sha: str
    dirty: bool
    format_id: str
    panel_hash: str
    panel_split: str
    hero_team_hash: str
    hero_team_id: str
    hero_archetype: str
    hero_novelty: str
    opponent_team_hash: str
    opponent_team_id: str
    opponent_archetype: str
    opponent_novelty: str
    opponent_policy: str
    cell_id: str
    planned_cell: bool
    protected_cell: bool
    winner: str
    hero_win: bool
    turns: int
    end_reason: str
    end_hp_diff: float | None
    hero_side: str
    hero_lead: tuple[str, str] | str
    opponent_lead: tuple[str, str] | str
    hero_static_speed_control: str
    opponent_static_speed_control: str
    hero_activated_speed_control: tuple[str, ...] | str
    opponent_activated_speed_control: tuple[str, ...] | str
    result_row_sha256: str
    normalized_room_log_sha256: str

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class ObservationBundle:
    observations: tuple[MatchupObservation, ...]
    safety_gates: tuple[dict, ...] = ()


class _Builder:
    @staticmethod
    def ensure_unique_seeds(keys):
        seen = set()
        for key in keys:
            if key in seen:
                raise ObservationError(f"duplicate seed in cell: {key}")
            seen.add(key)

    @staticmethod
    def from_contexts(contexts, *, policy_hash, manifest_hash, exposure_hash, taxonomy_hash):
        observations = []
        for context in contexts:
            row = context.row
            hero = context.hero_record if hasattr(context, "hero_record") else None
            opponent = context.opponent_record if hasattr(context, "opponent_record") else None
            values = dict(
                schema_version="matchup-observation-v1",
                analysis_id=sha256_id([manifest_hash, policy_hash, exposure_hash, taxonomy_hash]),
                policy_hash=policy_hash, generalisation_manifest_hash=manifest_hash,
                exposure_hash=exposure_hash, speed_control_taxonomy_hash=taxonomy_hash,
                run_id=row["run_id"], battle_id=row["battle_id"],
                schedule_hash=row["schedule_hash"], seed_base=row["seed_base"],
                seed_index=int(row["seed_index"]), seed=row["seed"], config_id=row["config_id"],
                config_hash=row["config_hash"], git_sha=row["git_sha"], dirty=bool(row["dirty"]),
                format_id=row["format_id"], panel_hash=row["panel_hash"],
                panel_split=row["panel_split"], hero_team_hash=row["hero_team_hash"],
                hero_team_id=hero.team_id if hero else "hero", hero_archetype=context.hero_archetype,
                hero_novelty=context.hero_novelty, opponent_team_hash=row["opp_team_hash"],
                opponent_team_id=opponent.team_id if opponent else "opponent",
                opponent_archetype=context.opponent_archetype,
                opponent_novelty=context.opponent_novelty, opponent_policy=row["opp_policy"],
                cell_id=context.cell_id, planned_cell=bool(getattr(context, "planned", True)),
                protected_cell=bool(context.protected),
                winner=row["winner"], hero_win=row["winner"] == "hero", turns=int(row["turns"]),
                end_reason=row["end_reason"], end_hp_diff=row.get("end_hp_diff"),
                hero_side=context.log_features.hero_side, hero_lead=context.log_features.hero_lead,
                opponent_lead=context.log_features.opponent_lead,
                hero_static_speed_control=context.static_hero,
                opponent_static_speed_control=context.static_opponent,
                hero_activated_speed_control=context.log_features.hero_speed_control,
                opponent_activated_speed_control=context.log_features.opponent_speed_control,
                result_row_sha256=sha256_id(row),
                normalized_room_log_sha256=row["normalized_room_log_sha256"])
            observations.append(MatchupObservation(**values))
        observations.sort(key=lambda item: (item.config_hash, item.seed_index, item.battle_id))
        _Builder.ensure_unique_seeds((item.cell_id, item.seed) for item in observations)
        return ObservationBundle(tuple(observations))


build_observation_bundle = _Builder()


def build_from_run_bundle(bundle, *, manifest, catalog, exposure, taxonomy, policy,
                          room_raw_dir, teams_root):
    cells = {cell.cell_id: cell for cell in manifest.cells}
    contexts = []
    for row in bundle.rows:
        hero = catalog.by_hash.get(row.get("hero_team_hash"))
        opponent = catalog.by_hash.get(row.get("opp_team_hash"))
        if hero is None or opponent is None:
            raise ObservationError(f"team hash absent from catalog at seed_index {row['seed_index']}")
        hero_novelty = classify_novelty(hero.team_hash, catalog, exposure)
        opponent_novelty = classify_novelty(opponent.team_hash, catalog, exposure)
        log_path = resolve_room_log_path(room_raw_dir, row.get("room_raw_path"))
        log_features = classify_room_log(log_path)
        axis_values = {
            "hero_team_hash": hero.team_hash, "hero_archetype": hero.archetype,
            "hero_novelty": hero_novelty, "opponent_team_hash": opponent.team_hash,
            "opponent_archetype": opponent.archetype, "opponent_novelty": opponent_novelty,
            "opponent_policy": row["opp_policy"], "panel_split": row["panel_split"],
            "format_id": row["format_id"], "hero_side": log_features.hero_side,
        }
        provisional = {name: axis_values[name] for name in manifest.required_axes}
        cell_id = sha256_id(provisional, 20)
        cell = cells.get(cell_id)
        planned = cell is not None
        row_for_analysis = dict(row)
        row_for_analysis["normalized_room_log_sha256"] = (
            row.get("normalized_room_log_sha256")
            or normalized_room_log_sha256(read_room_log_frames(log_path)))
        contexts.append(type("Context", (), {
            "row": row_for_analysis, "hero_record": hero, "opponent_record": opponent,
            "hero_archetype": hero.archetype, "opponent_archetype": opponent.archetype,
            "hero_novelty": hero_novelty, "opponent_novelty": opponent_novelty,
            "static_hero": static_speed_profile(Path(teams_root) / hero.team_path, taxonomy),
            "static_opponent": static_speed_profile(Path(teams_root) / opponent.team_path, taxonomy),
            "log_features": log_features, "cell_id": cell_id,
            "planned": planned, "protected": cell.protected if cell is not None else False,
        })())
    result = build_observation_bundle.from_contexts(
        contexts, policy_hash=policy.policy_hash, manifest_hash=manifest.manifest_hash,
        exposure_hash=exposure.exposure_hash, taxonomy_hash=taxonomy.taxonomy_hash)
    return ObservationBundle(result.observations, tuple())
