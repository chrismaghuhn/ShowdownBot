#!/usr/bin/env python3
"""Materialize Plan A fixtures 03-06, 10, 16 and SOURCES.md."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

STUDIO = Path(__file__).resolve().parents[1]
FIX = STUDIO / "fixtures" / "viewer-v0"
SRC = FIX / "sources"
BND = FIX / "bundles"
SMOKE = STUDIO.parent / "data" / "eval" / "champions-panel-v0" / "smoke-i7a-mega"
PRIVACY_LOG = STUDIO / "tests" / "python" / "synthetic" / "privacy_leak.log"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export_cli(out: Path, **kwargs: Path | str | None) -> None:
    """Export via library API (avoids Windows directory-replace races in tooling)."""
    import sys
    import time

    sys.path.insert(0, str(STUDIO / "python" / "src"))
    from showdownbot_studio_exporter.export_bundle import export_bundle

    if out.exists():
        shutil.rmtree(out)
        time.sleep(0.05)
    export_bundle(
        out=out.resolve(),
        battle_log=Path(kwargs["battle_log"]).resolve() if kwargs.get("battle_log") else None,
        decision_trace=Path(kwargs["decision_trace"]).resolve() if kwargs.get("decision_trace") else None,
        results=Path(kwargs["results"]).resolve() if kwargs.get("results") else None,
        run_manifest=Path(kwargs["run_manifest"]).resolve() if kwargs.get("run_manifest") else None,
        config_manifest=Path(kwargs["config_manifest"]).resolve() if kwargs.get("config_manifest") else None,
        battle_id=str(kwargs["battle_id"]) if kwargs.get("battle_id") else None,
    )


def fixture_03() -> None:
    dst = SRC / "fixture-03"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(SRC / "fixture-01", dst)
    rows = []
    for line in (dst / "decision_trace.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["decision_index"] == 2:
            row["fallback_reason"] = "heuristic_timeout"
        row["battle_id"] = "synthetic00000003"
        row["config_hash"] = "dddddddddddddddd"
        row["schedule_hash"] = "eeeeeeeeeeeeeeee"
        row["config_id"] = "synthetic_fixture_03"
        rows.append(row)
    (dst / "decision_trace.jsonl").write_text(
        "\n".join(json.dumps(r, sort_keys=True, separators=(",", ":"), ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )
    for name in ("results.jsonl",):
        text = (dst / name).read_text(encoding="utf-8")
        text = text.replace("synthetic00000001", "synthetic00000003")
        text = text.replace("syntheticrun00001", "syntheticrun00003")
        text = text.replace("bbbbbbbbbbbbbbbb", "dddddddddddddddd")
        text = text.replace("cccccccccccccccc", "eeeeeeeeeeeeeeee")
        text = text.replace("synthetic_fixture", "synthetic_fixture_03")
        (dst / name).write_text(text, encoding="utf-8")
    for name in ("results.manifest.json", "results.config-manifest.json"):
        text = (dst / name).read_text(encoding="utf-8")
        text = text.replace("syntheticrun00001", "syntheticrun00003")
        text = text.replace("bbbbbbbbbbbbbbbb", "dddddddddddddddd")
        text = text.replace("cccccccccccccccc", "eeeeeeeeeeeeeeee")
        text = text.replace("synthetic_fixture", "synthetic_fixture_03")
        (dst / name).write_text(text, encoding="utf-8")
    out = BND / "fixture-03"
    if out.exists():
        shutil.rmtree(out)
    export_cli(
        out,
        battle_log=dst / "battle.log",
        decision_trace=dst / "decision_trace.jsonl",
        results=dst / "results.jsonl",
        run_manifest=dst / "results.manifest.json",
        config_manifest=dst / "results.config-manifest.json",
    )


def fixture_04() -> None:
    dst = SRC / "fixture-04"
    dst.mkdir(parents=True, exist_ok=True)
    for name in ("battle.log", "results.jsonl", "results.manifest.json", "results.config-manifest.json"):
        shutil.copy2(SRC / "fixture-01" / name, dst / name)
    out = BND / "fixture-04"
    if out.exists():
        shutil.rmtree(out)
    export_cli(
        out,
        battle_log=dst / "battle.log",
        results=dst / "results.jsonl",
        run_manifest=dst / "results.manifest.json",
        config_manifest=dst / "results.config-manifest.json",
    )


def fixture_05() -> None:
    dst = SRC / "fixture-05"
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SMOKE / "decision_trace.jsonl", dst / "decision_trace.jsonl")
    shutil.copy2(SMOKE / "results.jsonl", dst / "results.jsonl")
    shutil.copy2(SMOKE / "results.jsonl.manifest.json", dst / "results.manifest.json")
    shutil.copy2(SMOKE / "results.jsonl.config-manifest.json", dst / "results.config-manifest.json")
    out = BND / "fixture-05"
    if out.exists():
        shutil.rmtree(out)
    export_cli(
        out,
        decision_trace=dst / "decision_trace.jsonl",
        results=dst / "results.jsonl",
        run_manifest=dst / "results.manifest.json",
        config_manifest=dst / "results.config-manifest.json",
        battle_id="3e6a178b0900195e",
    )


def fixture_06() -> None:
    dst = SRC / "fixture-06"
    dst.mkdir(parents=True, exist_ok=True)
    bundle_src = BND / "fixture-01"
    bundle_dst = dst / "bundle"
    if bundle_dst.exists():
        shutil.rmtree(bundle_dst)
    shutil.copytree(bundle_src, bundle_dst)
    dec = bundle_dst / "decisions.jsonl"
    data = bytearray(dec.read_bytes())
    data[10] ^= 0x01
    dec.write_bytes(bytes(data))


def fixture_10() -> None:
    dst = SRC / "fixture-10"
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PRIVACY_LOG, dst / "battle.log")
    # Minimal provenance for replay-only export (privacy source is the log only).
    mini_results = {
        "battle_id": "privacyfixture01",
        "config_hash": "ffffffffffffffff",
        "schedule_hash": "1111111111111111",
        "format_id": "gen9championsvgc2026regma",
        "git_sha": "unknown",
        "seed_index": 0,
        "config_id": "privacy_fixture",
        "dirty": False,
    }
    (dst / "results.jsonl").write_text(json.dumps(mini_results, sort_keys=True) + "\n", encoding="utf-8")
    out = BND / "fixture-10"
    if out.exists():
        shutil.rmtree(out)
    export_cli(out, battle_log=dst / "battle.log", results=dst / "results.jsonl")


def fixture_16() -> None:
    dst = SRC / "fixture-16"
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SMOKE / "decision_trace.jsonl", dst / "decision_trace.jsonl")
    shutil.copy2(SMOKE / "results.jsonl", dst / "results.jsonl")
    shutil.copy2(SMOKE / "results.jsonl.manifest.json", dst / "results.manifest.json")
    shutil.copy2(SMOKE / "results.jsonl.config-manifest.json", dst / "results.config-manifest.json")
    out = BND / "fixture-16"
    if out.exists():
        shutil.rmtree(out)
    export_cli(
        out,
        decision_trace=dst / "decision_trace.jsonl",
        results=dst / "results.jsonl",
        run_manifest=dst / "results.manifest.json",
        config_manifest=dst / "results.config-manifest.json",
        battle_id="3e6a178b0900195e",
    )


def write_sources_md() -> None:
    lines = ["# Viewer v0 Plan A fixture sources\n"]
    entries = [
        ("fixture-01", "synthetic-coherent-v1", SRC / "fixture-01"),
        ("fixture-03", "synthetic-coherent-v1", SRC / "fixture-03"),
        ("fixture-04", "replay-only (fixture-01 battle slice)", SRC / "fixture-04"),
        ("fixture-05", "smoke trace-only", SRC / "fixture-05"),
        ("fixture-06", "invalid hash (bundle copy)", SRC / "fixture-06"),
        ("fixture-10", "privacy counterexample", SRC / "fixture-10"),
        ("fixture-16", "smoke team-preview empty candidates", SRC / "fixture-16"),
    ]
    for fix_id, kind, path in entries:
        lines.append(f"\n## {fix_id}\n")
        lines.append(f"- source_kind: {kind}\n")
        if fix_id == "fixture-01":
            lines.extend(
                [
                    "- battle_id: synthetic00000001\n",
                    "- run_id: syntheticrun00001\n",
                    "- git_sha: unknown\n",
                    "- config_hash: bbbbbbbbbbbbbbbb\n",
                    "- schedule_hash: cccccccccccccccc\n",
                    "- config_id: synthetic_fixture\n",
                    "- format_id: gen9championsvgc2026regma\n",
                    "- dirty: false\n",
                    "- seed_index: 0\n",
                    "- our_side: p1\n",
                    "- note: bundle emits source_provenance.dirty null because git_sha is unknown (§8.4)\n",
                ]
            )
        elif fix_id == "fixture-03":
            lines.extend(
                [
                    "- battle_id: synthetic00000003\n",
                    "- run_id: syntheticrun00003\n",
                    "- git_sha: unknown\n",
                    "- config_hash: dddddddddddddddd\n",
                    "- schedule_hash: eeeeeeeeeeeeeeee\n",
                    "- config_id: synthetic_fixture_03\n",
                    "- format_id: gen9championsvgc2026regma\n",
                    "- dirty: false\n",
                    "- seed_index: 0\n",
                    "- our_side: p1\n",
                    "- note: bundle emits source_provenance.dirty null because git_sha is unknown (§8.4)\n",
                ]
            )
        for f in sorted(path.rglob("*")):
            if f.is_file():
                rel = f.relative_to(STUDIO).as_posix()
                lines.append(f"- `{rel}` sha256 `{sha256_file(f)}`\n")
    for fix_id in ("fixture-01", "fixture-03", "fixture-04", "fixture-05", "fixture-10", "fixture-16"):
        bpath = BND / fix_id
        if bpath.is_dir():
            lines.append(f"\n## bundle/{fix_id}\n")
            for f in sorted(bpath.iterdir()):
                if f.is_file():
                    rel = f.relative_to(STUDIO).as_posix()
                    lines.append(f"- `{rel}` sha256 `{sha256_file(f)}`\n")
    (FIX / "SOURCES.md").write_text("".join(lines), encoding="utf-8")


def main() -> None:
    fixture_03()
    fixture_04()
    fixture_05()
    fixture_06()
    fixture_10()
    fixture_16()
    write_sources_md()
    print("fixtures materialized")


if __name__ == "__main__":
    main()
