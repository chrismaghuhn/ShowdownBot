from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import random

from showdown_bot.analysis.generalisation.catalog import classify_novelty
from showdown_bot.analysis.generalisation.contracts import GeneralisationError, sha256_id
from showdown_bot.eval.schedule import Schedule, ScheduleRow, compute_schedule_hash
from showdown_bot.eval.panel_schedule import write_schedule_yaml


class PlannerError(GeneralisationError):
    pass


@dataclass(frozen=True)
class PlanRow:
    seed_index: int
    cell_id: str
    replicate_index: int
    hero_team_hash: str
    opponent_team_hash: str
    opponent_policy: str
    format_id: str
    panel_split: str


@dataclass(frozen=True)
class PlanResult:
    manifest_hash: str
    policy_hash: str
    panel_hash: str
    planner_seed: int
    mode: str
    rows: tuple[PlanRow, ...]
    schedule: Schedule
    plan_hash: str


def _cell_id(manifest, catalog, exposure, hero, opponent, policy, format_id, split):
    values = {"hero_team_hash": hero.team_hash, "hero_archetype": hero.archetype,
              "hero_novelty": classify_novelty(hero.team_hash, catalog, exposure),
              "opponent_team_hash": opponent.team_hash, "opponent_archetype": opponent.archetype,
              "opponent_novelty": classify_novelty(opponent.team_hash, catalog, exposure),
              "opponent_policy": policy, "panel_split": split, "format_id": format_id}
    selected = {name: values[name] for name in manifest.required_axes}
    return sha256_id(selected, 20)


def build_plan(manifest, catalog, exposure, *, planner_seed, mode, panel_hash,
               panel_team_hashes, panel_policies, policy_hash, confirm_heldout=False,
               observed_counts=None):
    if mode not in {"fresh", "dev-supplement", "heldout-fresh"}:
        raise PlannerError(f"unsupported planner mode {mode}")
    if len(manifest.splits) != 1:
        raise PlannerError("planner requires exactly one split")
    if manifest.side_control != "observed_only":
        raise PlannerError("current runner cannot plan verified hero sides")
    split = manifest.splits[0]
    if mode == "heldout-fresh" and (split != "heldout" or not confirm_heldout):
        raise PlannerError("heldout-fresh requires heldout split and confirm_heldout")
    if mode != "heldout-fresh" and split == "heldout":
        raise PlannerError("heldout split requires heldout-fresh mode")
    if mode == "dev-supplement" and split != "dev":
        raise PlannerError("dev-supplement requires dev split")
    protected = {cell.cell_id: cell for cell in manifest.cells}
    if set(manifest.opponent_policies) - set(panel_policies):
        raise PlannerError("manifest policies are not covered by panel_hash")
    concrete = []
    for hero_hash in manifest.hero_team_hashes:
        for opponent_hash in manifest.opponent_team_hashes:
            hero, opponent = catalog.by_hash[hero_hash], catalog.by_hash[opponent_hash]
            if opponent.team_hash not in panel_team_hashes:
                raise PlannerError(f"opponent {opponent.team_id} is absent from the selected panel split")
            if opponent.declared_split != split:
                raise PlannerError(f"opponent {opponent.team_id} is not declared {split}")
            for policy in manifest.opponent_policies:
                for format_id in manifest.format_ids:
                    cell_id = _cell_id(manifest, catalog, exposure, hero, opponent, policy,
                                       format_id, split)
                    if cell_id not in protected:
                        raise PlannerError(f"concrete row maps outside matrix: {cell_id}")
                    concrete.append((cell_id, hero, opponent, policy, format_id))
    by_cell = {cell_id: [] for cell_id in protected}
    for value in concrete:
        by_cell[value[0]].append(value)
    if any(not values for values in by_cell.values()):
        raise PlannerError("at least one materialized cell has no concrete team row")
    counts = observed_counts or {}
    plan_rows = []
    for cell_id in sorted(by_cell):
        target = protected[cell_id].required_unique_seeds
        missing = target if mode != "dev-supplement" else max(0, target - int(counts.get(cell_id, 0)))
        options = sorted(by_cell[cell_id], key=lambda value: (value[1].team_hash, value[2].team_hash,
                                                               value[3], value[4]))
        for replicate in range(missing):
            chosen = options[replicate % len(options)]
            plan_rows.append((replicate, chosen))
    rng = random.Random(sha256_id([planner_seed, manifest.manifest_hash], 16))
    ordered = []
    for replicate in sorted({item[0] for item in plan_rows}):
        block = [item for item in plan_rows if item[0] == replicate]
        block.sort(key=lambda item: item[1][0])
        if block:
            offset = rng.randrange(len(block))
            ordered.extend(block[offset:] + block[:offset])
    result_rows, schedule_rows = [], []
    for seed_index, (replicate, (_, hero, opponent, policy, format_id)) in enumerate(ordered):
        cell_id = _cell_id(manifest, catalog, exposure, hero, opponent, policy, format_id, split)
        result_rows.append(PlanRow(seed_index, cell_id, replicate, hero.team_hash,
                                   opponent.team_hash, policy, format_id, split))
        schedule_rows.append(ScheduleRow(format_id, hero.team_path, policy, opponent.team_path,
                                         seed_index, hero.team_hash, opponent.team_hash, split))
    schedule = Schedule(manifest.manifest_id, tuple(schedule_rows),
                        compute_schedule_hash(manifest.manifest_id, schedule_rows), panel_hash)
    plan_hash = sha256_id({"manifest_hash": manifest.manifest_hash, "policy_hash": policy_hash,
                           "panel_hash": panel_hash, "planner_seed": planner_seed, "mode": mode,
                           "rows": [asdict(row) for row in result_rows]})
    return PlanResult(manifest.manifest_hash, policy_hash, panel_hash, planner_seed, mode,
                      tuple(result_rows), schedule, plan_hash)


def write_plan(result: PlanResult, out_dir, materialized_manifest, *, overwrite=False,
               ledger_path=None, purpose=None, git_sha=None, justification=None):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    targets = [out / "generalisation-manifest.json", out / "generalisation-plan.json",
               out / "schedule.yaml", out / "schedule-preview.md"]
    if not overwrite and any(path.exists() for path in targets):
        raise PlannerError("planner output exists; pass overwrite to replace known outputs")
    payload = {"schema_version": "generalisation-plan-v1", "manifest_hash": result.manifest_hash,
               "policy_hash": result.policy_hash, "panel_hash": result.panel_hash,
               "planner_seed": result.planner_seed, "mode": result.mode,
               "plan_hash": result.plan_hash, "schedule_hash": result.schedule.schedule_hash,
               "rows": [asdict(row) for row in result.rows]}
    manifest_tmp = out / ".generalisation-manifest.json.tmp"
    plan_tmp = out / ".generalisation-plan.json.tmp"
    schedule_tmp = out / ".schedule.yaml.tmp"
    preview_tmp = out / ".schedule-preview.md.tmp"
    manifest_tmp.write_text(json.dumps(materialized_manifest, sort_keys=True, indent=2) + "\n",
                            encoding="utf-8")
    plan_tmp.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    write_schedule_yaml(result.schedule, str(schedule_tmp))
    counts = {}
    for row in result.rows:
        counts[row.cell_id] = counts.get(row.cell_id, 0) + 1
    preview = ["# Generalisation schedule preview", "", f"- mode: `{result.mode}`",
               f"- plan hash: `{result.plan_hash}`", f"- schedule hash: `{result.schedule.schedule_hash}`",
               f"- rows: {len(result.rows)}", "", "| cell_id | rows |", "|---|---:|"]
    preview.extend(f"| {cell_id} | {counts[cell_id]} |" for cell_id in sorted(counts))
    preview_tmp.write_text("\n".join(preview) + "\n", encoding="utf-8", newline="\n")
    for source, target in zip((manifest_tmp, plan_tmp, schedule_tmp, preview_tmp), targets):
        source.replace(target)
    if result.mode == "heldout-fresh":
        if ledger_path is None or not purpose or not git_sha:
            raise PlannerError("heldout output requires ledger_path, purpose and git_sha")
        from datetime import date
        from showdown_bot.eval.heldout_ledger import append_entry
        append_entry(ledger_path, {"kind": "generalisation_schedule",
            "date": date.today().isoformat(), "purpose": purpose,
            "panel_hash": result.panel_hash, "schedule_hash": result.schedule.schedule_hash,
            "git_sha": git_sha, "justification": justification,
            "manifest_hash": result.manifest_hash, "policy_hash": result.policy_hash,
            "plan_hash": result.plan_hash})
    return tuple(targets)
