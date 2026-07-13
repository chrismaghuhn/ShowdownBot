"""Real run: extract all 944 decisions from the full deduplicated corpus, compute decision_id
(spec Sec.2.2) for each, assert uniqueness, then do the ONE-TIME enrichment of the frozen
data/eval/accuracy-gate/pre-refactor-baseline.jsonl into decision_id space (join on request_hash,
cross-checked against log_prefix_hash/side/turn, fail-closed on ambiguous/missing matches). Each
enriched row's legacy chosen action is ALSO canonicalized via normalize_choose against that exact
decision's own real request (never a shared/default request).

Writes data/eval/accuracy-cap-derisk/decision-id-manifest.jsonl + a small provenance sidecar
(decision-id-manifest-meta.json). The frozen baseline file itself is read-only and untouched.
Refuses to overwrite an existing manifest OR an existing meta sidecar (checked independently --
either one present blocks the run) and writes both files ATOMICALLY (temp file + os.replace) only
after all computation has succeeded, so a mid-run crash can never leave a half-written, blocking
artifact behind -- delete both explicitly first if a genuine rebuild is intended.

Usage (from showdown_bot/): PYTHONPATH="$(pwd)/src" python scripts/build_decision_id_manifest.py
"""

from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SHOWDOWN_BOT_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SHOWDOWN_BOT_ROOT.parent
sys.path.insert(0, str(SHOWDOWN_BOT_ROOT / "src"))

DATA_EVAL = REPO_ROOT / "data" / "eval"
FROZEN_BASELINE = DATA_EVAL / "accuracy-gate" / "pre-refactor-baseline.jsonl"
OUT_DIR = DATA_EVAL / "accuracy-cap-derisk"
OUT_PATH = OUT_DIR / "decision-id-manifest.jsonl"
META_PATH = OUT_DIR / "decision-id-manifest-meta.json"
EXPECTED_FINAL_G = 85
EXPECTED_DECISION_COUNT = 944


def _atomic_write_text(path: Path, content: str) -> None:
    """Write content to path atomically: full write to a sibling temp file, then os.replace
    (atomic on both POSIX and Windows) -- a crash mid-write leaves only an orphaned .tmp file,
    never a half-written file at the real path that would trip the existence guard above on the
    next run without ever having actually succeeded."""
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(content, encoding="utf-8", newline="\n")
    os.replace(tmp_path, path)


def main() -> None:
    existing = [p for p in (OUT_PATH, META_PATH) if p.exists()]
    if existing:
        raise SystemExit(
            f"BLOCKED: {[str(p) for p in existing]} already exist. This script does not "
            f"silently overwrite an existing manifest or meta sidecar (checked independently, "
            f"either one present blocks the run) -- delete both explicitly first if a genuine "
            f"rebuild is intended."
        )

    from showdown_bot.eval.accuracy_cap_derisk import (
        DecisionIdComponents,
        _canonical_action,
        assert_decision_ids_unique,
        compute_decision_id,
    )
    from showdown_bot.eval.room_raw_replay import (
        RequestKind,
        deduplicate_battle_logs,
        extract_decisions_from_log,
    )

    # --- corpus extraction, byte-identical to run_accuracy_gate_b.py (Task 11 of the
    # accuracy-offline-gate plan) ---
    glob_dirs = [
        DATA_EVAL / "t4" / "rerun" / "room_raw",
        DATA_EVAL / "t4" / "room_raw_divergent",
        DATA_EVAL / "t6" / "room_raw",
        DATA_EVAL / "kaggle-validation" / "room_raw",
    ]
    log_files: list[Path] = []
    for d in glob_dirs:
        log_files += [Path(p) for p in glob.glob(str(d / "**" / "*.log.gz"), recursive=True)]
    log_files = sorted(set(log_files), key=str)

    manifest_files = [
        DATA_EVAL / "t4" / "rerun" / "t4rerun-run1.jsonl",
        DATA_EVAL / "t4" / "rerun" / "t4rerun-run2.jsonl",
        DATA_EVAL / "t4" / "rerun" / "t4rerun-prefix.jsonl",
        DATA_EVAL / "t6" / "t6-run1.jsonl",
        DATA_EVAL / "t6" / "t6-run2.jsonl",
        DATA_EVAL / "kaggle-validation" / "results.jsonl",
    ]
    dedup_report = deduplicate_battle_logs(
        log_files=log_files, manifest_files=manifest_files,
        keep_priority=["run1", "run2", "prefix", "kaggle-validation"],
    )
    if dedup_report.final_g != EXPECTED_FINAL_G:
        raise SystemExit(
            f"BLOCKED: expected final_g == {EXPECTED_FINAL_G}, got {dedup_report.final_g}. "
            f"Refusing to build decision_ids over an unverified corpus."
        )
    print(f"dedup: kept={len(dedup_report.kept)} final_g={dedup_report.final_g}")

    missing_identity = [p for p in dedup_report.kept if p not in dedup_report.kept_identities]
    if missing_identity:
        raise SystemExit(
            f"BLOCKED: {len(missing_identity)} kept file(s) have no SeedIdentity in "
            f"kept_identities (content-hash-fallback-kept) -- this plan's decision_id scheme "
            f"assumes every kept file has one, verified true for this corpus as of writing; "
            f"re-verify before proceeding. Files: {missing_identity}"
        )

    # --- extract, computing decision_id per row as we go (needs each file's SeedIdentity), and
    # keeping each decision's real request alongside its decision_id for the enrichment step below
    # (canonicalizing the LEGACY action requires the SAME real request the live decision used, not
    # a shared/default one) ---
    manifest_rows: list[dict] = []
    request_by_decision_id: dict[str, object] = {}
    kind_counts: Counter = Counter()
    for p in sorted(dedup_report.kept, key=str):
        identity = dedup_report.kept_identities[p]
        decisions = extract_decisions_from_log(p)
        for d in decisions:
            kind_counts[d.kind] += 1
            if d.kind != RequestKind.MOVE:
                continue
            did = compute_decision_id(DecisionIdComponents(
                seed_base=identity.seed_base, seed_index=identity.seed_index,
                request_hash=d.request_hash, log_prefix_hash=d.log_prefix_hash,
                side=d.side, rqid=d.request.rqid, turn=d.turn,
            ))
            request_by_decision_id[did] = d.request
            manifest_rows.append({
                "decision_id": did,
                "seed_base": identity.seed_base, "seed_index": identity.seed_index,
                "request_hash": d.request_hash, "log_prefix_hash": d.log_prefix_hash,
                "side": d.side, "rqid": d.request.rqid, "turn": d.turn,
                "source_file": str(p),
            })

    print(f"decision kinds: {dict(kind_counts)}")
    if len(manifest_rows) != EXPECTED_DECISION_COUNT:
        raise SystemExit(
            f"BLOCKED: expected {EXPECTED_DECISION_COUNT} MOVE decisions, got "
            f"{len(manifest_rows)}. Investigate before proceeding."
        )

    assert_decision_ids_unique([r["decision_id"] for r in manifest_rows])
    print(f"decision_id uniqueness confirmed: {len(manifest_rows)} unique ids")

    # --- one-time frozen-baseline enrichment: join on request_hash, cross-check
    # log_prefix_hash/side/turn, fail-closed on 0 or 2+ matches ---
    by_request_hash: dict[str, list[dict]] = {}
    for r in manifest_rows:
        by_request_hash.setdefault(r["request_hash"], []).append(r)

    frozen_rows = [json.loads(line) for line in FROZEN_BASELINE.read_text(encoding="utf-8").splitlines() if line]
    print(f"frozen baseline: {len(frozen_rows)} rows read (read-only)")

    for r in manifest_rows:
        r["legacy_frozen_score"] = None
        r["legacy_frozen_chosen_action"] = None
        r["legacy_frozen_action_canonical"] = None

    manifest_by_did = {r["decision_id"]: r for r in manifest_rows}
    enriched = 0
    for frow in frozen_rows:
        candidates = [
            r for r in by_request_hash.get(frow["request_hash"], [])
            if r["log_prefix_hash"] == frow["log_prefix_hash"]
            and r["side"] == frow["side"] and r["turn"] == frow["turn"]
        ]
        if len(candidates) != 1:
            raise SystemExit(
                f"BLOCKED: frozen baseline row request_hash={frow['request_hash']!r} "
                f"log_prefix_hash={frow['log_prefix_hash']!r} side={frow['side']!r} "
                f"turn={frow['turn']!r} matched {len(candidates)} decision_id candidates "
                f"(expected exactly 1) -- fail-closed, investigate before proceeding."
            )
        did = candidates[0]["decision_id"]
        manifest_by_did[did]["legacy_frozen_score"] = frow["score"]
        manifest_by_did[did]["legacy_frozen_chosen_action"] = frow["chosen_action"]
        manifest_by_did[did]["legacy_frozen_action_canonical"] = _canonical_action(
            frow["chosen_action"], request_by_decision_id[did]
        )
        enriched += 1

    print(f"frozen-baseline enrichment: {enriched}/{len(frozen_rows)} rows matched "
          f"exactly one decision_id (fail-closed on any other outcome, none occurred)")

    # --- all computation is done; get provenance, then write BOTH files atomically. Doing this
    # write step LAST (rather than writing OUT_PATH first and only computing/writing META_PATH
    # afterward, as an earlier draft of this script did) means a failure anywhere above -- or in
    # source_commit's own subprocess call -- can never leave OUT_PATH present without META_PATH,
    # a half-finished state that would trip the existence guard on every future run without this
    # run ever having actually succeeded. ---
    try:
        source_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT), text=True
        ).strip()
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"could not determine source_commit via git rev-parse HEAD: {exc}")

    manifest_content = "".join(
        json.dumps(r, sort_keys=True) + "\n"
        for r in sorted(manifest_rows, key=lambda x: x["decision_id"])
    )
    meta_content = json.dumps({
        "source_commit": source_commit, "python_version": sys.version,
        "row_count": len(manifest_rows), "generated_at_epoch": time.time(),
    }, indent=2, sort_keys=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(OUT_PATH, manifest_content)
    print(f"wrote {OUT_PATH} ({len(manifest_rows)} rows)")
    _atomic_write_text(META_PATH, meta_content)
    print(f"wrote {META_PATH}")


if __name__ == "__main__":
    main()
