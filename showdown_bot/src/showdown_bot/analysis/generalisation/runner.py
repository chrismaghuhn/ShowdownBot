from __future__ import annotations

from showdown_bot.analysis.generalisation.catalog import (
    load_exposure, load_speed_taxonomy, load_team_catalog,
)
from showdown_bot.analysis.generalisation.compare import compare_observation_pairs
from showdown_bot.analysis.generalisation.contracts import GeneralisationError, load_policy, sha256_id
from showdown_bot.analysis.generalisation.manifest import (
    load_generalisation_manifest, manifest_to_dict,
)
from showdown_bot.analysis.generalisation.metrics import single_run_summary
from showdown_bot.analysis.generalisation.observations import build_from_run_bundle
from showdown_bot.analysis.generalisation.reporting import write_analysis_outputs, write_fatal_report
from showdown_bot.eval.pairing import PairingError, pair_runs
from showdown_bot.eval.report import LogIntegrityError, ReportInputError, RunBundle, run_safety_gates


def _load_bundle(results, seedlog, schedule, panel, teams_root, manifest_path, room_raw):
    return RunBundle.load(results, seedlog, schedule, panel, teams_root=teams_root,
                          manifest_path=manifest_path, room_raw_dir=room_raw)


def _analyze_runs(*, policy_path, catalog_path, exposure_path, taxonomy_path, manifest_path,
                  panel_path, schedule_path, run_a, seedlog_a, room_raw_a, teams_root, out_dir,
                  run_manifest_a=None, run_b=None, seedlog_b=None, room_raw_b=None,
                  run_manifest_b=None, overwrite=False):
    policy = load_policy(policy_path)
    catalog = load_team_catalog(catalog_path, teams_root=teams_root)
    exposure = load_exposure(exposure_path, catalog)
    taxonomy = load_speed_taxonomy(taxonomy_path)
    manifest = load_generalisation_manifest(manifest_path, catalog, policy, exposure)
    bundle_a = _load_bundle(run_a, seedlog_a, schedule_path, panel_path, teams_root,
                            run_manifest_a, room_raw_a)
    gates_a = run_safety_gates(bundle_a, mode="gate")
    observations_a = build_from_run_bundle(bundle_a, manifest=manifest, catalog=catalog,
        exposure=exposure, taxonomy=taxonomy, policy=policy, room_raw_dir=room_raw_a,
        teams_root=teams_root)
    single = single_run_summary(manifest, observations_a.observations, policy)
    comparison = None
    all_observations = list(observations_a.observations)
    if run_b is not None:
        if not seedlog_b or not room_raw_b:
            raise ValueError("run_b requires seedlog_b and room_raw_b")
        bundle_b = _load_bundle(run_b, seedlog_b, schedule_path, panel_path, teams_root,
                                run_manifest_b, room_raw_b)
        gates_b = run_safety_gates(bundle_b, mode="gate")
        observations_b = build_from_run_bundle(bundle_b, manifest=manifest, catalog=catalog,
            exposure=exposure, taxonomy=taxonomy, policy=policy, room_raw_dir=room_raw_b,
            teams_root=teams_root)
        pair_runs(bundle_a.rows, bundle_b.rows, expected_rows=bundle_a.schedule_row_count)
        comparison = compare_observation_pairs(observations_a.observations,
                                               observations_b.observations, policy)
        all_observations.extend(observations_b.observations)
    else:
        gates_b = []
    hard_fail = any(gate.status == "FAIL" for gate in [*gates_a, *gates_b])
    status = "INVALID" if hard_fail else comparison["status"] if comparison else \
        "DESCRIPTIVE_COMPLETE" if single["macro"]["complete"] else "INCONCLUSIVE"
    sides = {item.hero_side for item in all_observations if item.hero_side in {"p1", "p2"}}
    report = {"schema_version": "generalisation-report-v1", "status": status,
              "analysis_id": sha256_id([manifest.manifest_hash, policy.policy_hash,
                                         exposure.exposure_hash, taxonomy.taxonomy_hash]),
              "provenance": {"manifest_hash": manifest.manifest_hash,
                             "policy_hash": policy.policy_hash,
                             "exposure_hash": exposure.exposure_hash,
                             "taxonomy_hash": taxonomy.taxonomy_hash},
              "generalisation_manifest": manifest_to_dict(manifest),
              "safety_gates": [gate.__dict__ for gate in [*gates_a, *gates_b]],
              "coverage": single["coverage"], "cells": single["cells"],
              "unplanned_count": single["unplanned_count"],
              "micro": single["micro"], "macro": single["macro"],
              "diagnostic_slices": single["diagnostic_slices"],
              "worst_cell": single["worst_cell"],
              "archetypes": single["archetypes"],
              "worst_archetype": single["worst_archetype"],
              "stability": single["stability"],
              "robustness_gap": single["robustness_gap"],
              "paired": [] if comparison is None else comparison["cells"],
              "comparison": comparison, "side_capability": "EVALUABLE" if len(sides) == 2
                  else "NOT_EVALUABLE", "findings": []}
    write_analysis_outputs(out_dir, report, [item.to_dict() for item in all_observations],
                           overwrite=overwrite)
    return report


def analyze_runs(**kwargs):
    try:
        return _analyze_runs(**kwargs)
    except (GeneralisationError, PairingError, ReportInputError, LogIntegrityError, OSError) as exc:
        return write_fatal_report(kwargs["out_dir"], exc, overwrite=kwargs.get("overwrite", False))


def plan_schedule(*, policy_path, catalog_path, exposure_path, manifest_path, panel_path, out_dir,
                  teams_root=".", mode="fresh", confirm_heldout=False, ledger_path=None,
                  purpose=None, git_sha=None, justification=None, overwrite=False,
                  observed_counts=None):
    from showdown_bot.analysis.generalisation.planner import build_plan, write_plan
    from showdown_bot.eval.panel import load_panel
    policy = load_policy(policy_path)
    catalog = load_team_catalog(catalog_path, teams_root=teams_root)
    exposure = load_exposure(exposure_path, catalog)
    panel = load_panel(panel_path, teams_root=teams_root)
    manifest = load_generalisation_manifest(manifest_path, catalog, policy, exposure)
    result = build_plan(manifest, catalog, exposure, planner_seed=policy.planner_seed, mode=mode,
                        panel_hash=panel.panel_hash,
                        panel_team_hashes={team.team_hash for team in (
                            panel.heldout_teams if manifest.splits == ("heldout",)
                            else panel.dev_teams)}, panel_policies=set(panel.policies),
                        policy_hash=policy.policy_hash,
                        confirm_heldout=confirm_heldout, observed_counts=observed_counts)
    write_plan(result, out_dir, manifest_to_dict(manifest), overwrite=overwrite,
               ledger_path=ledger_path, purpose=purpose, git_sha=git_sha,
               justification=justification)
    return result
