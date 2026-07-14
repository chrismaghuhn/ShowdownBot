from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from showdown_bot.eval.room_raw_replay import (
    AmbiguousManifestMatchError,
    DedupReport,
    SeedIdentity,
    SeedIdentityConflictError,
    deduplicate_battle_logs,
)

# NOTE: parents[3] (NOT parents[3].parent) is the repo root here -- verified empirically
# against this worktree's actual layout (tests/eval/<file>.py -> parents[3] == repo root
# containing data/). This matches the sibling test_room_raw_replay.py's own REAL_LOG
# convention (also parents[3], no trailing .parent) at the identical directory depth.
REPO_ROOT = Path(__file__).resolve().parents[3]  # .../SHowdown BOt (or this worktree's root)
DATA_T4 = REPO_ROOT / "data" / "eval" / "t4"
DATA_T6 = REPO_ROOT / "data" / "eval" / "t6"
DATA_KAGGLE = REPO_ROOT / "data" / "eval" / "kaggle-validation"


def _make_manifest_row(
    room_raw_path: str, schedule_hash: str, seed_base: str, seed_index: int,
    seed: str | None = None,
) -> dict:
    return {
        "room_raw_path": room_raw_path,
        "seed": seed if seed is not None else f"sodium,synthetic-{seed_base}-{seed_index}",
        "schedule_hash": schedule_hash,
        "seed_base": seed_base,
        "seed_index": seed_index,
        "battle_id": f"synthetic-{seed_index}",
    }


def _write_synthetic_log(dirpath: Path, name: str, lines: list[str]) -> Path:
    dirpath.mkdir(parents=True, exist_ok=True)
    path = dirpath / f"{name}.log.gz"
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return path


def _write_manifest(path: Path, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def test_seed_identity_equality_and_hash_ignore_schedule_hash_and_seed():
    """SeedIdentity.__eq__/__hash__ intentionally compare/hash only (seed_base, seed_index) --
    schedule_hash and seed are provenance detail, not part of identity. This is currently NOT
    exercised by any real call site in deduplicate_battle_logs (which manually unpacks tuples
    instead of comparing SeedIdentity objects directly) -- this test exists so a future
    regression in the override itself would be caught even before any call site starts relying
    on it directly."""
    a = SeedIdentity(seed_base="X", seed_index=1, schedule_hash="HASH_A", seed="seedA")
    b = SeedIdentity(seed_base="X", seed_index=1, schedule_hash="HASH_B_DIFFERENT", seed="seedB_DIFFERENT")
    c = SeedIdentity(seed_base="Y", seed_index=1, schedule_hash="HASH_A", seed="seedA")

    assert a == b  # same (seed_base, seed_index) -> equal, despite differing schedule_hash/seed
    assert hash(a) == hash(b)
    assert a != c  # different seed_index -> not equal
    assert {a, b} == {a}  # collapse to one element in a set
    assert len({a: 1, b: 2}) == 1  # b overwrites a's entry in a dict


def test_manifest_join_dedups_run1_vs_run2_reproduction(tmp_path):
    battle_lines = [
        ">battle-x-1",
        '|request|{"active":[{"moves":[]}],"side":{"name":"H","id":"p1","pokemon":[]},"rqid":1}',
    ]
    run1_dir = tmp_path / "run1"
    run2_dir = tmp_path / "run2"
    p1 = _write_synthetic_log(run1_dir, "HeuristicBot1__battle-abc-1", battle_lines)
    p2 = _write_synthetic_log(run2_dir, "HeuristicBot2__battle-xyz-2", battle_lines)

    manifest1 = tmp_path / "run1.jsonl"
    manifest2 = tmp_path / "run2.jsonl"
    _write_manifest(manifest1, [_make_manifest_row(
        "C:/tmp/run1/HeuristicBot1__battle-abc-1.log", "SCHEDULE_A", "seedbaseA", 0,
    )])
    _write_manifest(manifest2, [_make_manifest_row(
        "C:/tmp/run2/HeuristicBot2__battle-xyz-2.log", "SCHEDULE_A", "seedbaseA", 0,  # SAME identity
    )])

    report = deduplicate_battle_logs(
        log_files=[p1, p2],
        manifest_files=[manifest1, manifest2],
        keep_priority=["run1", "run2"],
    )
    assert report.files_found == 2
    assert len(report.kept) == 1
    assert report.kept[0] == p1  # run1 wins the priority order
    assert len(report.excluded) == 1
    assert report.excluded[0].reason == "duplicate_seed_identity"
    assert report.final_g == 1


def test_manifest_join_ignores_schedule_hash_and_dedups_prefix_against_run1(tmp_path):
    """The core round-6 regression: two files with DIFFERENT schedule_hash but the SAME
    (seed_base, seed_index) must be recognized as the same battle -- this is exactly the real
    run1-vs-prefix relationship, and a schedule_hash-inclusive key would wrongly miss it."""
    battle_lines = [
        ">battle-p",
        '|request|{"active":[{"moves":[]}],"side":{"name":"H","id":"p1","pokemon":[]},"rqid":1}',
    ]
    run1_dir = tmp_path / "run1"
    prefix_dir = tmp_path / "prefix"
    p1 = _write_synthetic_log(run1_dir, "HeuristicBot1__battle-run1-0", battle_lines)
    p2 = _write_synthetic_log(prefix_dir, "HeuristicBot2__battle-prefix-0", battle_lines)

    manifest1 = tmp_path / "run1.jsonl"
    manifest2 = tmp_path / "prefix.jsonl"
    _write_manifest(manifest1, [_make_manifest_row(
        "C:/tmp/run1/HeuristicBot1__battle-run1-0.log", "SCHEDULE_FULL", "sharedbase", 0,
    )])
    _write_manifest(manifest2, [_make_manifest_row(
        "C:/tmp/prefix/HeuristicBot2__battle-prefix-0.log", "SCHEDULE_PREFIX_DIFFERENT_HASH",
        "sharedbase", 0,  # same (seed_base, seed_index), DIFFERENT schedule_hash
    )])

    report = deduplicate_battle_logs(
        log_files=[p1, p2], manifest_files=[manifest1, manifest2], keep_priority=["run1", "prefix"],
    )
    assert report.final_g == 1
    assert report.kept == [p1]
    assert report.excluded[0].reason == "duplicate_seed_identity"


def test_manifest_join_keeps_genuinely_distinct_seeds(tmp_path):
    battle_lines_a = [">battle-a", '|request|{"active":[],"side":{"name":"H","id":"p1","pokemon":[]},"rqid":1}']
    battle_lines_b = [">battle-b", '|request|{"active":[],"side":{"name":"H","id":"p1","pokemon":[]},"rqid":1}']
    d = tmp_path / "run1"
    p1 = _write_synthetic_log(d, "HeuristicBot1__battle-a", battle_lines_a)
    p2 = _write_synthetic_log(d, "HeuristicBot2__battle-b", battle_lines_b)
    manifest = tmp_path / "run1.jsonl"
    _write_manifest(manifest, [
        _make_manifest_row("C:/tmp/run1/HeuristicBot1__battle-a.log", "SCHED_T4", "t4base", 0),
        _make_manifest_row("C:/tmp/run1/HeuristicBot2__battle-b.log", "SCHED_T6", "t6base", 0),
    ])
    report = deduplicate_battle_logs(log_files=[p1, p2], manifest_files=[manifest], keep_priority=["run1"])
    assert report.final_g == 2
    assert set(report.kept) == {p1, p2}


def test_seed_identity_conflict_fails_closed_on_content_mismatch(tmp_path):
    """The fail-closed hardening: two files share (seed_base, seed_index) per their manifest
    rows AND the same full seed value, but their normalized room-log CONTENT genuinely differs
    (simulating e.g. manifest corruption or a future corpus violating the invariant verified for
    today's frozen 85-group corpus). Must raise, not silently pick one or accept both."""
    lines_a = [">battle-f", '|request|{"active":[],"side":{"name":"H","id":"p1","pokemon":[]},"rqid":1}', "|turn|1"]
    lines_b = [  # same seed/identity claimed, but genuinely different resolved content
        ">battle-f",
        '|request|{"active":[],"side":{"name":"H","id":"p1","pokemon":[]},"rqid":1}',
        "|turn|1",
        "|switch|p1a: SomeOtherMon",
    ]
    d = tmp_path / "run1"
    p1 = _write_synthetic_log(d, "HeuristicBot1__battle-f", lines_a)
    p2 = _write_synthetic_log(d, "HeuristicBot2__battle-f2", lines_b)
    manifest = tmp_path / "run1.jsonl"
    same_seed = "sodium,deadbeefdeadbeefdeadbeefdeadbeef"
    _write_manifest(manifest, [
        _make_manifest_row("C:/tmp/run1/HeuristicBot1__battle-f.log", "SCHED_X", "base", 5, seed=same_seed),
        _make_manifest_row("C:/tmp/run1/HeuristicBot2__battle-f2.log", "SCHED_X", "base", 5, seed=same_seed),
    ])
    with pytest.raises(SeedIdentityConflictError):
        deduplicate_battle_logs(log_files=[p1, p2], manifest_files=[manifest], keep_priority=["run1"])


def test_seed_identity_conflict_fails_closed_on_seed_value_mismatch(tmp_path):
    """Same (seed_base, seed_index) but a DIFFERENT full seed value across manifest rows --
    must also fail closed, independent of whether content happens to match."""
    battle_lines = [">battle-g", '|request|{"active":[],"side":{"name":"H","id":"p1","pokemon":[]},"rqid":1}']
    d = tmp_path / "run1"
    p1 = _write_synthetic_log(d, "HeuristicBot1__battle-g", battle_lines)
    p2 = _write_synthetic_log(d, "HeuristicBot2__battle-g2", battle_lines)
    manifest = tmp_path / "run1.jsonl"
    _write_manifest(manifest, [
        _make_manifest_row("C:/tmp/run1/HeuristicBot1__battle-g.log", "SCHED_X", "base", 9,
                            seed="sodium,aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"),
        _make_manifest_row("C:/tmp/run1/HeuristicBot2__battle-g2.log", "SCHED_X", "base", 9,
                            seed="sodium,bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"),  # different seed
    ])
    with pytest.raises(SeedIdentityConflictError):
        deduplicate_battle_logs(log_files=[p1, p2], manifest_files=[manifest], keep_priority=["run1"])


@pytest.mark.skipif(
    not (DATA_T4 / "rerun" / "t4rerun-run1.jsonl").exists(),
    reason="real t4/t6/kaggle-validation corpus not present",
)
def test_real_corpus_satisfies_seed_identity_invariant_for_all_85_groups():
    """Confirms, against the REAL frozen corpus, the exact fact the user verified independently
    before authorizing this task: 85 groups, sizes {2: 75, 4: 10}, zero seed mismatches, zero
    normalized-content-hash mismatches. This documents (seed_base, seed_index) as a VERIFIED
    valid replicate key for THIS corpus specifically -- deduplicate_battle_logs itself enforces
    this on every run (it would have raised SeedIdentityConflictError here if it didn't hold), so
    this test's job is to prove the real corpus runs through cleanly, not to re-derive the check."""
    import glob
    from collections import Counter

    regular_log_files = [
        Path(p) for p in glob.glob(str(DATA_T4 / "rerun" / "room_raw" / "**" / "*.log.gz"), recursive=True)
    ]
    regular_log_files += [Path(p) for p in glob.glob(str(DATA_T6 / "room_raw" / "**" / "*.log.gz"), recursive=True)]
    regular_log_files += [Path(p) for p in glob.glob(str(DATA_KAGGLE / "room_raw" / "*.log.gz"))]
    manifests = [
        DATA_T4 / "rerun" / "t4rerun-run1.jsonl", DATA_T4 / "rerun" / "t4rerun-run2.jsonl",
        DATA_T4 / "rerun" / "t4rerun-prefix.jsonl",
        DATA_T6 / "t6-run1.jsonl", DATA_T6 / "t6-run2.jsonl", DATA_KAGGLE / "results.jsonl",
    ]
    # No SeedIdentityConflictError means the invariant held for every one of the 85 groups --
    # that IS the assertion; a raised exception fails this test automatically.
    report = deduplicate_battle_logs(
        log_files=regular_log_files, manifest_files=manifests,
        keep_priority=["run1", "run2", "prefix", "kaggle-validation"],
    )
    assert report.final_g == 85
    group_sizes = Counter()
    # Reconstruct group sizes from files_found vs excluded reasons, matching the user's own
    # independently-verified histogram {2: 75, 4: 10} (85 groups, 190 files, no other size).
    dup_count_by_winner = Counter(e.duplicate_of for e in report.excluded if e.reason == "duplicate_seed_identity")
    for winner in report.kept:
        group_sizes[dup_count_by_winner.get(winner, 0) + 1] += 1
    assert dict(group_sizes) == {2: 75, 4: 10}, (
        f"expected the verified {{2: 75, 4: 10}} group-size histogram; got {dict(group_sizes)} -- "
        f"if the corpus genuinely changed, re-verify the invariant manually before touching this "
        f"assertion, don't just widen it"
    )


def test_room_raw_divergent_excluded_a_priori_never_content_hash_admitted(tmp_path):
    """Round-5/6 requirement: files under a `room_raw_divergent` directory must be excluded
    outright, even when their content genuinely differs from any kept file's (they were
    deliberately preserved AS evidence of divergence -- admitting them via content-hash
    mismatch would wrongly inflate G)."""
    kept_lines = [">battle-d", '|request|{"active":[],"side":{"name":"H","id":"p1","pokemon":[]},"rqid":1}']
    divergent_lines = [  # deliberately DIFFERENT content -- a divergent-outcome capture
        ">battle-d",
        '|request|{"active":[],"side":{"name":"H","id":"p1","pokemon":[]},"rqid":1}',
        "|switch|p1a: SomethingElse",
    ]
    run1_dir = tmp_path / "run1"
    divergent_dir = tmp_path / "room_raw_divergent"
    kept = _write_synthetic_log(run1_dir, "HeuristicBot1__battle-d", kept_lines)
    divergent = _write_synthetic_log(divergent_dir, "run1-idx00-battle-d", divergent_lines)

    manifest = tmp_path / "run1.jsonl"
    _write_manifest(manifest, [_make_manifest_row(
        "C:/tmp/run1/HeuristicBot1__battle-d.log", "SCHED_T4", "t4base", 0,
    )])

    report = deduplicate_battle_logs(
        log_files=[kept, divergent], manifest_files=[manifest], keep_priority=["run1"],
    )
    assert report.final_g == 1
    assert report.kept == [kept]
    assert report.excluded[0].source_file == divergent
    assert report.excluded[0].reason == "excluded_diagnostic_artifact"


def test_ambiguous_manifest_match_fails_closed(tmp_path):
    battle_lines = [">battle-e", '|request|{"active":[],"side":{"name":"H","id":"p1","pokemon":[]},"rqid":1}']
    d = tmp_path / "run1"
    p1 = _write_synthetic_log(d, "HeuristicBot1__battle-e", battle_lines)
    manifest_a = tmp_path / "a.jsonl"
    manifest_b = tmp_path / "b.jsonl"
    # Two manifests disagreeing about the SAME file's identity -- must never be silently resolved.
    _write_manifest(manifest_a, [_make_manifest_row(
        "C:/tmp/run1/HeuristicBot1__battle-e.log", "SCHED_X", "baseX", 0,
    )])
    _write_manifest(manifest_b, [_make_manifest_row(
        "C:/tmp/run1/HeuristicBot1__battle-e.log", "SCHED_Y", "baseY", 7,  # different (seed_base, seed_index)
    )])
    with pytest.raises(AmbiguousManifestMatchError):
        deduplicate_battle_logs(
            log_files=[p1], manifest_files=[manifest_a, manifest_b], keep_priority=["run1"],
        )


@pytest.mark.skipif(
    not (DATA_T4 / "rerun" / "t4rerun-run1.jsonl").exists(),
    reason="real t4/t6/kaggle-validation corpus not present",
)
def test_real_corpus_dedup_collapses_190_regular_files_to_85():
    """Integration check against the REAL committed corpus, per spec §7's
    test_global_dedup_uses_seed_schedule_not_room_id -- the 197-files-to-85-unique-battles ratio
    is itself a load-bearing claim this gate's credibility depends on, so this must run against
    real data, not only synthetic fixtures. G=85 is VERIFIED (not an estimate) -- see this plan's
    provenance-facts section for the exact join performed to arrive at it."""
    import glob

    regular_log_files = [
        Path(p) for p in glob.glob(str(DATA_T4 / "rerun" / "room_raw" / "**" / "*.log.gz"), recursive=True)
    ]
    regular_log_files += [Path(p) for p in glob.glob(str(DATA_T6 / "room_raw" / "**" / "*.log.gz"), recursive=True)]
    regular_log_files += [Path(p) for p in glob.glob(str(DATA_KAGGLE / "room_raw" / "*.log.gz"))]
    divergent_log_files = [Path(p) for p in glob.glob(str(DATA_T4 / "room_raw_divergent" / "*.log.gz"))]

    assert len(regular_log_files) == 190, (
        f"expected 190 regular-directory files (t4 run1+run2+prefix=112, t6 run1+run2=68, "
        f"kaggle-validation=10); got {len(regular_log_files)} -- the corpus itself changed, "
        f"re-derive every downstream number in this plan and the spec before proceeding"
    )
    assert len(divergent_log_files) == 7

    manifests = [
        DATA_T4 / "rerun" / "t4rerun-run1.jsonl", DATA_T4 / "rerun" / "t4rerun-run2.jsonl",
        DATA_T4 / "rerun" / "t4rerun-prefix.jsonl",
        DATA_T6 / "t6-run1.jsonl", DATA_T6 / "t6-run2.jsonl", DATA_KAGGLE / "results.jsonl",
    ]
    all_log_files = regular_log_files + divergent_log_files
    report = deduplicate_battle_logs(
        log_files=all_log_files, manifest_files=manifests,
        keep_priority=["run1", "run2", "prefix", "kaggle-validation"],
    )
    assert report.files_found == 197

    # Every regular-directory file must resolve to exactly one manifest match -- none may
    # silently fall through to the content-hash fallback (that path is defense-in-depth only;
    # a real fallback hit here would mean a manifest/on-disk mismatch worth investigating).
    fallback_reasons = {e.source_file: e.reason for e in report.excluded}
    for f in regular_log_files:
        assert fallback_reasons.get(f) != "duplicate_content_hash", (
            f"{f} silently fell through to content-hash dedup instead of matching a manifest row"
        )

    # room_raw_divergent's 7 files must be excluded with their own dedicated reason, never
    # counted toward kept/G, regardless of content.
    divergent_excluded = {e.source_file: e.reason for e in report.excluded if e.source_file in divergent_log_files}
    assert len(divergent_excluded) == 7
    assert all(r == "excluded_diagnostic_artifact" for r in divergent_excluded.values())

    # The verified number: 190 regular files -> exactly 85 unique (seed_base, seed_index)
    # identities. Do not loosen this to a range if it fails -- it is a directly re-derivable,
    # exact fact (see the provenance-facts section), not an estimate.
    assert report.final_g == 85, (
        f"expected the VERIFIED G=85 (t4's 51 unique seeds + t6's 34); got {report.final_g} -- "
        f"if the corpus genuinely changed since this plan was written, re-run the provenance "
        f"verification in the plan's own provenance-facts section and update every downstream "
        f"number (this test, Task 4/9/11, and the spec's §1/§4/§6) together, don't just widen this"
    )
    unique_identities = {(i.seed_base, i.seed_index) for i in report.kept_identities.values()}
    assert len(unique_identities) == 85
