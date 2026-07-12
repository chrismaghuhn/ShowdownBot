from pathlib import Path
import json

from showdown_bot.analysis.generalisation.runner import analyze_runs


ROOT = Path(__file__).resolve().parents[3]
SB = ROOT / "showdown_bot"
RERUN = ROOT / "data/eval/t4/rerun"
FIX = Path(__file__).with_name("fixtures")


def _candidate_copy(tmp_path):
    rows = [json.loads(line) for line in (RERUN / "t4rerun-run2.jsonl").read_text(
        encoding="utf-8").splitlines() if line]
    for row in rows:
        row["config_id"] = "fixture-candidate"
        row["config_hash"] = "fixture-candidate-config"
        row["run_id"] = "fixture-candidate-run"
    results = tmp_path / "candidate.jsonl"
    results.write_text("".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
                               for row in rows), encoding="utf-8", newline="\n")
    manifest = json.loads((RERUN / "t4rerun-run2.jsonl.manifest.json").read_text(encoding="utf-8"))
    manifest["config_hash"] = "fixture-candidate-config"
    manifest["run_id"] = "fixture-candidate-run"
    manifest_path = tmp_path / "candidate.manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return results, manifest_path


def run_real_fixture(out_dir):
    out_dir = Path(out_dir)
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    candidate, candidate_manifest = _candidate_copy(out_dir.parent)
    return analyze_runs(
        policy_path=SB / "config/analysis/generalisation_policy_v1.yaml",
        catalog_path=FIX / "catalog.json", exposure_path=FIX / "exposure.json",
        taxonomy_path=SB / "config/analysis/speed_control_taxonomy_v1.yaml",
        manifest_path=FIX / "manifest.yaml", panel_path=ROOT / "config/eval/panels/panel_v001.yaml",
        schedule_path=ROOT / "config/eval/schedules/t4_smoke_v001.yaml",
        run_a=RERUN / "t4rerun-run1.jsonl", seedlog_a=RERUN / "t4rerun-run1-seedlog.jsonl",
        room_raw_a=RERUN / "room_raw/run1",
        run_manifest_a=RERUN / "t4rerun-run1.jsonl.manifest.json", run_b=candidate,
        seedlog_b=RERUN / "t4rerun-run2-seedlog.jsonl", room_raw_b=RERUN / "room_raw/run2",
        run_manifest_b=candidate_manifest, teams_root=SB, out_dir=out_dir)
