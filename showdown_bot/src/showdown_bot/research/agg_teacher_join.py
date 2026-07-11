"""Offline join of ML-dataset teacher labels onto full-fidelity aggregation-trace
rows (2c-Slice-0b, Task 5).

``research/aggregation_trace.py`` (Tasks 1-3) persists the exact per-candidate score
matrices used by ``battle/policy.py::aggregate_scores``, but always writes
``teacher_best_action_keys`` as ``[]`` -- game outcomes/teacher labels are joined
OFFLINE, out-of-band, here (see that module's own docstring). The dataset
(``learning/export.py`` / ``learning/dataset.py``) and the agg-trace sidecar
(``research/aggregation_trace.py``) are written by two INDEPENDENT writers during the
same eval run and share NO common key: the dataset keys rows by a content/seed-derived
``(game_id, decision_id)`` (``learning/export.py::make_game_id``/``make_decision_id``),
while the agg-trace keys rows by ``(battle_id, decision_index, our_side)`` with a plain
``seed_index``/``turn_number`` -- no ``game_id`` at all (see
``research/aggregation_trace.py::build_agg_row``).

So joining them requires FIRST reconstructing which ``game_id`` corresponds to which
``seed_index``, by re-deriving ``make_game_id(make_run_id(...), game_index)`` for
``game_index`` in ``0..N-1`` (``N`` = the number of battles in ``results.jsonl``) and
matching the resulting SET of game_ids against the dataset's own distinct game_ids
(``_reconstruct_gid_to_seed_index``). ``git_sha``/``team_hash``/``config_hash`` are
run-constant and read straight off any dataset row's metadata; ``dirty``/``run_seed``
are not directly recoverable from either file, so a small ``(dirty, run_seed)``
candidate space is swept (the results-derived ``dirty`` tried first) until the
reconstructed game_id set matches exactly -- fail-closed: raises ``TeacherJoinError``
if none do. ``game_index -> seed_index`` is then read off ``results.jsonl`` in FILE
ORDER (``results[game_index]["seed_index"]``) -- this is what makes the reconstruction
correct for BOTH an unsharded run (``game_index == seed_index``) and a sharded one
(arbitrary order/offset).

Once seed_index is known for both sides, rows are keyed by ``(seed_index,
turn_number)`` and INTERSECTION-joined: the dataset has STRICTLY MORE decisions than
the agg-trace (the sidecar write is best-effort -- see
``research/aggregation_trace.py``'s module docstring), and a handful of
``(seed_index, turn_number)`` keys hold >1 decision on either side (intra-turn
force-switch). Ambiguous keys are SKIPPED, never guessed, and every skip is counted by
reason in the returned report. A joined decision's ``teacher_best_action_keys`` is
built POSITIONALLY: dataset ``candidate_index k`` and agg-trace ``candidates[k]`` are
the same rank-sorted ``trace.candidates`` list from the SAME live decision, so no
``action_key`` string-matching is needed (or even possible -- the dataset never
records ``action_key`` at all).

Offline, deterministic (sorted key iteration), no RNG, no battles, no live-path
changes.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from showdown_bot.learning.dataset import group_decisions, load_rows
from showdown_bot.learning.export import make_game_id, make_run_id
from showdown_bot.research.aggregation_trace import load_agg_trace, validate_agg_row

TEACHER_JOIN_REPORT_SCHEMA_VERSION = "agg-teacher-join-v1"

_REASONS = (
    "ambiguous_agg", "ambiguous_dataset", "dataset_only", "agg_only",
    "candidate_count_mismatch",
)


class TeacherJoinError(ValueError):
    """Fatal, fail-closed: the run provenance (game_id -> seed_index) could not be
    reconstructed, an internal per-game turn-count cross-check failed, or a dataset
    decision's candidate_index set was not the dense 0..k-1 range the positional
    teacher-key mapping requires. Every downstream join result would be
    untrustworthy, so this raises immediately rather than silently mis-joining."""


@dataclass(frozen=True)
class JoinConfig:
    """Search space for the ``(dirty, run_seed)`` provenance-reconstruction guess.

    ``git_sha``/``team_hash``/``config_hash`` are read directly off the dataset
    (always present, run-constant -- see
    ``learning/provenance.py::build_feature_context``). ``dirty`` is read off
    ``results.jsonl`` (also run-constant for a single run) and tried FIRST; its
    boolean complement is tried next as a defensive fallback (covers a
    dataset/results pair whose recorded ``dirty`` values genuinely disagree).
    ``run_seed`` has no directly-recorded value anywhere, so ``run_seed_candidates``
    is swept in order -- default ``(0,)``, the well-known default (see
    ``learning/export_runtime.py::DatasetExportRuntime.from_env``,
    ``SHOWDOWN_DATASET_RUN_SEED``). Pass a wider tuple if the default fails to
    reconstruct a bijection.
    """
    run_seed_candidates: tuple[int, ...] = (0,)


def _read_results(results_path) -> list[dict]:
    """``results.jsonl`` -> ``list[dict]``, in FILE ORDER -- order is load-bearing:
    the ``game_index -> seed_index`` mapping is defined AS this file order. Plain
    JSONL, one row per line (mirrors ``eval.result_jsonl.BattleResultWriter``, which
    never gzips)."""
    rows = []
    with open(results_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _reconstruct_gid_to_seed_index(
    *, dataset_game_ids: set[str], dataset_max_turn_by_game_id: dict[str, int],
    results: list[dict], git_sha: str, team_hash_: str, config_hash_: str,
    config: JoinConfig,
) -> tuple[dict[str, int], bool, int]:
    """Returns ``(gid_to_seed_index, winning_dirty, winning_run_seed)``.

    Fail-closed: raises ``TeacherJoinError`` if no ``(dirty, run_seed)`` pair in the
    swept space reproduces the dataset's exact game_id set, or if the winning
    mapping fails the per-game turn-count cross-check (``max dataset turn_number for
    that game <= results[game_index]["turns"]``).
    """
    n = len(results)
    results_dirty = bool(results[0]["dirty"])
    dirty_candidates = (results_dirty, not results_dirty)

    tried = []
    for dirty in dirty_candidates:
        for run_seed in config.run_seed_candidates:
            run_id = make_run_id(git_sha, dirty, team_hash_, config_hash_, run_seed)
            gid_by_index = [make_game_id(run_id, i) for i in range(n)]
            tried.append((dirty, run_seed))
            if set(gid_by_index) != dataset_game_ids:
                continue

            for i, gid in enumerate(gid_by_index):
                max_turn = dataset_max_turn_by_game_id.get(gid)
                if max_turn is not None and max_turn > results[i]["turns"]:
                    raise TeacherJoinError(
                        f"cross-check failed: game_index={i} gid={gid!r} has a "
                        f"dataset turn_number {max_turn} exceeding results.jsonl "
                        f"turns {results[i]['turns']} "
                        f"(seed_index={results[i]['seed_index']})"
                    )

            gid_to_seed = {gid: results[i]["seed_index"] for i, gid in enumerate(gid_by_index)}
            return gid_to_seed, dirty, run_seed

    raise TeacherJoinError(
        f"could not bijectively reconstruct run_id: tried (dirty, run_seed) in "
        f"{tried}; none reproduced the dataset's {len(dataset_game_ids)} distinct "
        f"game_ids from {n} results.jsonl rows"
    )


def join_teacher_labels(
    agg_trace_path, dataset_path, results_path, *, config: JoinConfig | None = None,
) -> tuple[list[dict], dict]:
    """Join ML-dataset teacher labels onto full-fidelity agg-trace rows.

    Returns ``(enriched_rows, report)``: ``enriched_rows`` is the FULL agg-trace row
    list (same length/order as ``load_agg_trace(agg_trace_path)``), each still
    ``validate_agg_row``-valid, with ``teacher_best_action_keys`` populated for
    joined decisions and left ``[]`` for everything else (degenerate rows, and any
    row this join could not confidently match). ``report`` counts agg
    non-degenerate rows, dataset decisions, joined decisions, teacher-labeled
    decisions, and skips by reason. See the module docstring for the full
    algorithm.
    """
    config = config or JoinConfig()

    agg_rows = load_agg_trace(agg_trace_path)
    dataset_rows = load_rows(str(dataset_path), validate=True)
    results = _read_results(results_path)

    if not dataset_rows:
        raise TeacherJoinError(f"dataset has no rows: {dataset_path}")
    if not results:
        raise TeacherJoinError(f"results.jsonl has no rows: {results_path}")

    decisions = group_decisions(dataset_rows)

    dataset_game_ids: set[str] = {d.game_id for d in decisions}
    dataset_max_turn_by_game_id: dict[str, int] = {}
    for d in decisions:
        turn_number = d.rows[0]["features"]["turn_number"]
        cur = dataset_max_turn_by_game_id.get(d.game_id)
        if cur is None or turn_number > cur:
            dataset_max_turn_by_game_id[d.game_id] = turn_number

    meta0 = dataset_rows[0]["metadata"]
    gid_to_seed, winning_dirty, winning_run_seed = _reconstruct_gid_to_seed_index(
        dataset_game_ids=dataset_game_ids,
        dataset_max_turn_by_game_id=dataset_max_turn_by_game_id,
        results=results,
        git_sha=meta0["git_sha"], team_hash_=meta0["team_hash"],
        config_hash_=meta0["config_hash"], config=config,
    )

    # --- Key both sides by (seed_index, turn_number). ---
    dataset_by_key: dict[tuple[int, int], list] = {}
    for d in decisions:
        seed_index = gid_to_seed[d.game_id]
        turn_number = d.rows[0]["features"]["turn_number"]
        dataset_by_key.setdefault((seed_index, turn_number), []).append(d)

    agg_by_key: dict[tuple[int, int], list[dict]] = {}
    for row in agg_rows:
        if row["turn_number"] is not None:
            key = (row["seed_index"], row["turn_number"])
            agg_by_key.setdefault(key, []).append(row)

    # --- Intersection join, fail-closed, reason-counted, sorted (deterministic). ---
    skipped_by_reason = {reason: 0 for reason in _REASONS}
    joined_count = 0
    teacher_labeled_count = 0

    # Reason precedence for a key present on both sides but not cleanly 1:1: the agg
    # side is checked FIRST (ambiguous_agg / agg-side-count-zero before the dataset
    # equivalents). This is an explicit, deterministic tie-break for the one case the
    # spec's 5-reason vocabulary doesn't itself disambiguate -- a key ambiguous on
    # BOTH sides at once (agg_count > 1 AND dataset_count > 1) is counted as
    # "ambiguous_agg", not "ambiguous_dataset". This is not a hypothetical: it
    # happens for real on the reference shard (10 of its 14 dataset-ambiguous keys
    # are ALSO agg-ambiguous).
    all_keys = sorted(set(dataset_by_key) | set(agg_by_key))
    for key in all_keys:
        agg_list = agg_by_key.get(key, [])
        dataset_list = dataset_by_key.get(key, [])

        if not agg_list:
            skipped_by_reason["dataset_only"] += 1
            continue
        if len(agg_list) > 1:
            skipped_by_reason["ambiguous_agg"] += 1
            continue
        if not dataset_list:
            skipped_by_reason["agg_only"] += 1
            continue
        if len(dataset_list) > 1:
            skipped_by_reason["ambiguous_dataset"] += 1
            continue

        agg_row = agg_list[0]
        decision = dataset_list[0]
        if len(agg_row["candidates"]) != len(decision.rows):
            skipped_by_reason["candidate_count_mismatch"] += 1
            continue

        candidate_indices = [r["metadata"]["candidate_index"] for r in decision.rows]
        if candidate_indices != list(range(len(candidate_indices))):
            raise TeacherJoinError(
                f"decision {(decision.game_id, decision.decision_id)!r} has "
                f"non-contiguous candidate_index values {candidate_indices}; the "
                "positional agg-trace join requires a dense 0..k-1 range"
            )

        teacher_keys = [
            agg_row["candidates"][i]["action_key"]
            for i, cand_row in enumerate(decision.rows)
            if bool(cand_row["label"]["teacher_best"])
        ]
        agg_row["teacher_best_action_keys"] = teacher_keys
        joined_count += 1
        if teacher_keys:
            teacher_labeled_count += 1

    for row in agg_rows:
        validate_agg_row(row)

    report = {
        "report_schema_version": TEACHER_JOIN_REPORT_SCHEMA_VERSION,
        "reconstruction": {
            "dirty": winning_dirty, "run_seed": winning_run_seed, "games_total": len(results),
        },
        "agg_non_degenerate_count": sum(len(v) for v in agg_by_key.values()),
        "dataset_decisions_count": len(decisions),
        "joined_count": joined_count,
        "teacher_labeled_count": teacher_labeled_count,
        "skipped_by_reason": skipped_by_reason,
    }
    return agg_rows, report
