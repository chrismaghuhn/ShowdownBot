"""Teacher-Disagreement Atlas -- classification + bucketing core (2b-3.5 T3, topset model).

Mines the rollout-teacher-labelled dataset (``learning.dataset.load_rows`` output: rows shaped
``{"features": {...}, "label": {...}, "metadata": {...}}``) for WHERE the current heuristic's
chosen action disagrees with the rollout teacher's best candidate, and how large the value gap
is. Aimed measurement, not a gate -- see the design spec
``docs/superpowers/specs/2026-07-11-teacher-disagreement-atlas-design.md``.

Ported (with adaptations -- ``learning.dataset.load_rows`` row shape, own exception type, own
loader/grouping) from the user's external Decision-Error-Atlas prototype's LIVE, refined module
(``Showdown-Bot-Analysis-Clone``, ``tools/analysis/rollout_metrics.py::analyze_rollout_decisions``
+ its full validation layer). This REPLACES an earlier port (2b-3.5 T1) of a stale plan-doc
snapshot that compared a single chosen row against a single ``teacher_best`` row and raised on
``value_gap_to_best < 0`` -- but this codebase's labels store ``value_gap_to_best = v - best <= 0``
(see ``learning/teacher.py::label_decision``), so that snapshot raised on nearly every real row.
This module uses the **topset model** instead, which handles ties on both sides and never assumes
the gap sign the old snapshot assumed.

Topset model, per decision (a group of candidate rows sharing ``metadata.decision_id``):

  - **heuristic topset** -- the set of ``candidate_index`` where ``label.chosen_by_current_heuristic``
    is true. **teacher topset** -- the set where ``label.teacher_best`` is true. Either topset may
    have more than one member (a tie).
  - **forced** -- a single candidate (nothing to choose); skipped from every other count.
  - **multi_candidate** -- every other decision; the denominator for ``topset_disagreement_rate``.
  - **heuristic_ties** / **teacher_ties** -- counted whenever the respective topset has >1 member
    (evaluated across ALL decisions, forced or not).
  - **topset agreement/disagreement** -- for a multi_candidate decision, the topsets overlap (share
    a candidate_index) or are disjoint. Disagreement is "disjoint topsets".
  - **strict-unique choice** -- a multi_candidate decision with EXACTLY one heuristic row and
    EXACTLY one teacher row. This is the clean subset a ``record`` is built from and the
    denominator for the bucket breakdowns and ``disagreement_rate``. **strict disagreement** = its
    topsets are disjoint (equivalent to "not disjoint" since both topsets are singletons here).
  - **regret_gap = max(0.0, -value_gap_to_best)** on the chosen (heuristic) row -- flips this
    codebase's ``<= 0`` gap sign into a ``>= 0`` regret magnitude.

Fail-closed invariants (ported verbatim via ``_validate_decisions``/``_validate_row``): every
decision's rows are typed and internally consistent (contiguous 0-based ``candidate_index``, a
single ``game_id``, at least one heuristic-top and one teacher-top row, rank-zero flags agree with
the boolean flags, ``value_gap_to_best`` is ``<= 0`` and exactly ``0`` for ``teacher_best`` rows);
``score_gap_to_second`` is non-negative on every strict-unique heuristic row; every emitted number
is finite. All raise ``TeacherDisagreementError``.

Determinism: decisions are iterated in sorted ``decision_id`` order; bucket breakdowns are sorted
by value; ``top_opportunities`` ties break on ``decision_id``. No time/random involved.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

from showdown_bot.learning.dataset import load_rows

_BREAKDOWN_KEYS = (
    "turn_bucket",
    "game_mode",
    "action_signature",
    "speed_control_state",
    "threat_bucket",
    "candidate_count",
    "response_entropy_bucket",
    "heuristic_confidence_bucket",
)

_FEATURE_FIELDS = (
    "turn_number",
    "game_mode",
    "slot1_action_type",
    "slot2_action_type",
    "slot1_is_protect",
    "slot2_is_protect",
    "ko_threatened_count",
    "speed_control_state",
    "opponent_response_entropy",
    "score_gap_to_second",
)
_LABEL_FIELDS = (
    "chosen_by_current_heuristic",
    "teacher_best",
    "heuristic_rank",
    "teacher_rank",
    "value_gap_to_best",
)
_METADATA_FIELDS = ("decision_id", "game_id", "candidate_index")


class TeacherDisagreementError(Exception):
    """Raised on a fail-closed invariant violation in the teacher-disagreement atlas."""


def group_by_decision(rows: list[dict]) -> dict[str, list[dict]]:
    """Group rows (the ``learning.dataset.load_rows`` shape) by ``metadata.decision_id``.

    Row order within a decision's group preserves input encounter order (typically already
    candidate_index order). The returned dict has keys in sorted order for determinism."""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        decision_id = row["metadata"]["decision_id"]
        grouped[decision_id].append(row)
    return {decision_id: grouped[decision_id] for decision_id in sorted(grouped)}


# --- validation layer (ported from the clone's atlas_inputs.py) --------------------------------


def _require_fields(value: dict, fields: tuple[str, ...], context: str) -> None:
    missing = [field for field in fields if field not in value]
    if missing:
        raise TeacherDisagreementError(f"{context} missing fields: {', '.join(missing)}")


def _require_nonempty_string(value: object, field: str, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise TeacherDisagreementError(f"{field} at {context} must be a non-empty string")
    return value


def _require_nonnegative_int(value: object, field: str, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise TeacherDisagreementError(f"{field} at {context} must be a non-negative integer")
    return value


def _require_finite_number(
    value: object, field: str, context: str, *, nonnegative: bool = False
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TeacherDisagreementError(f"{field} at {context} must be a finite number")
    try:
        number = float(value)
    except (OverflowError, ValueError, TypeError) as exc:
        raise TeacherDisagreementError(
            f"{field} at {context} must be a finite number"
        ) from exc
    if not math.isfinite(number) or (nonnegative and number < 0.0):
        qualifier = "non-negative finite" if nonnegative else "finite"
        raise TeacherDisagreementError(f"{field} at {context} must be a {qualifier} number")
    return number


def _validate_row(row: object, context: str) -> dict:
    if not isinstance(row, dict):
        raise TeacherDisagreementError(f"row at {context} must be a JSON object")
    _require_fields(row, ("features", "label", "metadata"), context)
    features = row["features"]
    label = row["label"]
    metadata = row["metadata"]
    for name, nested in (
        ("features", features),
        ("label", label),
        ("metadata", metadata),
    ):
        if not isinstance(nested, dict):
            raise TeacherDisagreementError(f"{name} at {context} must be a JSON object")

    features_context = f"{context} features"
    _require_fields(features, _FEATURE_FIELDS, features_context)
    _require_nonnegative_int(features["turn_number"], "turn_number", features_context)
    threatened_count = _require_nonnegative_int(
        features["ko_threatened_count"],
        "ko_threatened_count",
        features_context,
    )
    if threatened_count > 2:
        raise TeacherDisagreementError(
            f"ko_threatened_count at {features_context} must be in the "
            "VGC doubles domain 0..2"
        )
    for field in (
        "game_mode",
        "slot1_action_type",
        "slot2_action_type",
        "speed_control_state",
    ):
        _require_nonempty_string(features[field], field, features_context)
    for field in ("slot1_is_protect", "slot2_is_protect"):
        if type(features[field]) is not bool:
            raise TeacherDisagreementError(f"{field} at {features_context} must be a boolean")
    _require_finite_number(
        features["opponent_response_entropy"],
        "opponent_response_entropy",
        features_context,
        nonnegative=True,
    )
    _require_finite_number(
        features["score_gap_to_second"], "score_gap_to_second", features_context
    )

    label_context = f"{context} label"
    _require_fields(label, _LABEL_FIELDS, label_context)
    for field in ("chosen_by_current_heuristic", "teacher_best"):
        if type(label[field]) is not bool:
            raise TeacherDisagreementError(f"{field} at {label_context} must be a boolean")
    for field in ("heuristic_rank", "teacher_rank"):
        _require_nonnegative_int(label[field], field, label_context)
    for flag, rank in (
        ("chosen_by_current_heuristic", "heuristic_rank"),
        ("teacher_best", "teacher_rank"),
    ):
        if label[flag] != (label[rank] == 0):
            raise TeacherDisagreementError(
                f"{flag}/{rank} at {label_context} must agree on rank-zero status"
            )
    raw_gap = _require_finite_number(
        label["value_gap_to_best"], "value_gap_to_best", label_context
    )
    if label["teacher_best"] and raw_gap != 0.0:
        raise TeacherDisagreementError(
            f"teacher_best row at {label_context} must have "
            "value_gap_to_best exactly zero"
        )
    if raw_gap > 0.0:
        raise TeacherDisagreementError(
            f"value_gap_to_best at {label_context} must be less than or equal to zero"
        )

    metadata_context = f"{context} metadata"
    _require_fields(metadata, _METADATA_FIELDS, metadata_context)
    _require_nonempty_string(metadata["decision_id"], "decision_id", metadata_context)
    _require_nonempty_string(metadata["game_id"], "game_id", metadata_context)
    _require_nonnegative_int(
        metadata["candidate_index"], "candidate_index", metadata_context
    )
    return row


def _validate_decisions(decisions: object) -> None:
    if not isinstance(decisions, dict):
        raise TeacherDisagreementError("decisions must be a JSON object")
    for decision_id, rows in decisions.items():
        _require_nonempty_string(decision_id, "decision_id", "decisions mapping")
        if not isinstance(rows, (list, tuple)):
            raise TeacherDisagreementError(f"decision {decision_id} rows must be a list")
        if not rows:
            raise TeacherDisagreementError(f"decision {decision_id} has an empty candidate group")

        validated = [
            _validate_row(row, f"decision {decision_id} row {index}")
            for index, row in enumerate(rows)
        ]
        metadata = [row["metadata"] for row in validated]
        if any(item["decision_id"] != decision_id for item in metadata):
            raise TeacherDisagreementError(
                f"decision {decision_id} metadata decision_id values must match"
            )
        game_ids = {item["game_id"] for item in metadata}
        if len(game_ids) != 1:
            raise TeacherDisagreementError(
                f"decision {decision_id} must map to exactly one game_id"
            )
        indices = [item["candidate_index"] for item in metadata]
        if sorted(indices) != list(range(len(rows))):
            raise TeacherDisagreementError(
                f"decision {decision_id} candidate indices must be unique and "
                f"contiguous 0..{len(rows) - 1}"
            )
        if not any(
            row["label"]["chosen_by_current_heuristic"] for row in validated
        ):
            raise TeacherDisagreementError(
                f"decision {decision_id} must have at least one heuristic-top row"
            )
        if not any(row["label"]["teacher_best"] for row in validated):
            raise TeacherDisagreementError(
                f"decision {decision_id} must have at least one teacher-top row"
            )


def _validate_output_numbers(value: object, context: str = "output") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            _validate_output_numbers(nested, f"{context}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            _validate_output_numbers(nested, f"{context}[{index}]")
        return
    if isinstance(value, float) and not math.isfinite(value):
        raise TeacherDisagreementError(f"{context} numeric values must be finite")


# --- bucketing helpers (ported verbatim) --------------------------------------------------------


def _turn_bucket(turn: int) -> str:
    if turn <= 3:
        return "1-3"
    if turn <= 6:
        return "4-6"
    return "7+"


def _action_signature(features: dict) -> str:
    protects = int(features["slot1_is_protect"]) + int(features["slot2_is_protect"])
    return (
        f"{features['slot1_action_type']}+{features['slot2_action_type']}"
        f"|protects={protects}"
    )


def _response_entropy_bucket(value: float) -> str:
    if value < 1.0:
        return "low"
    if value < 2.0:
        return "medium"
    return "high"


def _heuristic_confidence_bucket(value: float) -> str:
    if value <= 0.0:
        return "tie_or_zero"
    if value < 0.25:
        return "low"
    if value < 1.0:
        return "medium"
    return "high"


def _nearest_rank(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[math.ceil(fraction * len(ordered)) - 1]


def _breakdown(records: list[dict], key: str) -> list[dict]:
    grouped: dict[object, list[dict]] = {}
    for record in records:
        grouped.setdefault(record[key], []).append(record)

    rows = []
    for value in sorted(grouped):
        group = grouped[value]
        disagreement_records = [item for item in group if item["disagreement"]]
        disagreements = len(disagreement_records)
        rows.append(
            {
                "value": value,
                "decisions": len(group),
                "agreements": len(group) - disagreements,
                "disagreements": disagreements,
                "disagreement_rate": disagreements / len(group),
                "mean_disagreement_regret": (
                    sum(item["regret_gap"] for item in disagreement_records)
                    / disagreements
                    if disagreements
                    else 0.0
                ),
            }
        )
    return rows


# --- the topset classifier -----------------------------------------------------------------------


def analyze_disagreement(decisions: dict[str, list[dict]]) -> dict:
    """Summarize heuristic-topset disagreement with rollout-teacher topsets (the topset model).

    ``decisions`` is a ``decision_id -> [candidate rows]`` mapping, e.g. from
    ``group_by_decision``. Returns a deterministic dict (see module docstring for the topset
    classification rule, the strict-unique record subset, and the fail-closed invariants)."""
    _validate_decisions(decisions)

    forced = sum(len(rows) == 1 for rows in decisions.values())
    multi_candidate = 0
    heuristic_ties = 0
    teacher_ties = 0
    topset_agreements = 0
    topset_disagreements = 0
    strict_agreements = 0
    strict_disagreements = 0
    records: list[dict] = []

    for decision_id, rows in sorted(decisions.items()):
        heuristic_rows = [
            row for row in rows if row["label"]["chosen_by_current_heuristic"]
        ]
        teacher_rows = [row for row in rows if row["label"]["teacher_best"]]
        heuristic_ties += len(heuristic_rows) > 1
        teacher_ties += len(teacher_rows) > 1
        if len(rows) == 1:
            continue

        multi_candidate += 1
        heuristic_indices = {
            row["metadata"]["candidate_index"] for row in heuristic_rows
        }
        teacher_indices = {
            row["metadata"]["candidate_index"] for row in teacher_rows
        }
        topsets_overlap = bool(heuristic_indices & teacher_indices)
        topset_agreements += topsets_overlap
        topset_disagreements += not topsets_overlap

        if len(heuristic_rows) != 1 or len(teacher_rows) != 1:
            continue

        disagreement = not topsets_overlap
        strict_agreements += not disagreement
        strict_disagreements += disagreement
        chosen = heuristic_rows[0]
        features = chosen["features"]
        heuristic_score_gap = float(features["score_gap_to_second"])
        if heuristic_score_gap < 0.0:
            raise TeacherDisagreementError(
                f"score_gap_to_second for decision {decision_id} strict unique "
                "heuristic row must be non-negative"
            )
        raw_gap = float(chosen["label"]["value_gap_to_best"])
        record = {
            "decision_id": decision_id,
            "game_id": chosen["metadata"]["game_id"],
            "candidate_count": len(rows),
            "disagreement": disagreement,
            "raw_value_gap": raw_gap,
            "regret_gap": max(0.0, -raw_gap),
            "turn_bucket": _turn_bucket(features["turn_number"]),
            "game_mode": features["game_mode"],
            "action_signature": _action_signature(features),
            "speed_control_state": features["speed_control_state"],
            "threat_bucket": str(features["ko_threatened_count"]),
            "response_entropy": float(features["opponent_response_entropy"]),
            "response_entropy_bucket": _response_entropy_bucket(
                features["opponent_response_entropy"]
            ),
            "heuristic_score_gap": heuristic_score_gap,
            "heuristic_confidence_bucket": _heuristic_confidence_bucket(
                heuristic_score_gap
            ),
        }
        records.append(record)

    disagreement_records = [item for item in records if item["disagreement"]]
    threshold = _nearest_rank(
        [item["regret_gap"] for item in disagreement_records], 0.90
    )
    top_opportunities = sorted(
        (
            {
                **record,
                "high_value": (
                    record["regret_gap"] > 0.0
                    and record["regret_gap"] >= threshold
                ),
            }
            for record in disagreement_records
        ),
        key=lambda item: (-item["regret_gap"], item["decision_id"]),
    )[:20]
    strict_unique_choices = len(records)
    strict_rate = (
        strict_disagreements / strict_unique_choices
        if strict_unique_choices
        else 0.0
    )
    result = {
        "corpus": {
            "decisions": len(decisions),
            "forced": forced,
            "multi_candidate": multi_candidate,
            "heuristic_ties": heuristic_ties,
            "teacher_ties": teacher_ties,
            "strict_unique_choices": strict_unique_choices,
            "topset_agreements": topset_agreements,
            "topset_disagreements": topset_disagreements,
            "strict_agreements": strict_agreements,
            "strict_disagreements": strict_disagreements,
        },
        "topset_disagreement_rate": (
            topset_disagreements / multi_candidate if multi_candidate else 0.0
        ),
        "strict_disagreement_rate": strict_rate,
        "disagreement_rate": strict_rate,
        "high_value_threshold": threshold,
        "breakdown_scope": "strict_unique_choices",
        "breakdown_denominator": strict_unique_choices,
        "breakdowns": {key: _breakdown(records, key) for key in _BREAKDOWN_KEYS},
        "top_opportunities": top_opportunities,
    }
    _validate_output_numbers(result)
    return result


# --- loader wiring (2b-3.5 T3f Task 2) -----------------------------------------------------------

LIMITATIONS_NOTE = (
    "The rollout teacher is an OFFLINE one-step counterfactual rollout, which makes it "
    "optimistic: a strict disagreement here is NOT a proven play error, and a strict "
    "agreement is NOT a strength claim. This atlas identifies WHERE regret concentrates, "
    "to aim the next reranker/belief work -- it is aimed measurement, not a gate."
)


def teacher_disagreement_atlas(dataset_path: str, *, validate: bool = True) -> dict:
    """Load a rollout-label dataset and run the topset disagreement classifier.

    Wires ``learning.dataset.load_rows`` -> ``group_by_decision`` -> ``analyze_disagreement``
    and adds a top-level ``dataset`` block (``path``/``rows``/``decisions``/``games``, the
    last counting distinct ``metadata.game_id`` values across ALL loaded rows). Deterministic
    for a given dataset file (``analyze_disagreement`` iterates in sorted ``decision_id``
    order; see its docstring).

    ``validate`` is TEST-ONLY: production callers must keep the default ``True`` (the
    committed rollout datasets are schema-valid, so ``load_rows`` should never silently
    accept a malformed row). Tests may pass ``validate=False`` to exercise this function
    against a minimal hand-authored fixture that satisfies this module's OWN
    ``_validate_row`` invariants without satisfying the full frozen dataset schema
    (``learning.schema.validate_row``, which demands an exact, larger key set)."""
    rows = load_rows(dataset_path, validate=validate)
    decisions = group_by_decision(rows)
    atlas = analyze_disagreement(decisions)
    games = len({row["metadata"]["game_id"] for row in rows})
    result = {
        "dataset": {
            "path": str(dataset_path),
            "rows": len(rows),
            "decisions": len(decisions),
            "games": games,
        },
        **atlas,
    }
    _validate_output_numbers(result)
    return result


# --- markdown rendering ---------------------------------------------------------------------------

_BREAKDOWN_TABLE_COLUMNS = (
    "value",
    "decisions",
    "agreements",
    "disagreements",
    "disagreement_rate",
    "mean_disagreement_regret",
)
_TOP_OPPORTUNITY_COLUMNS = (
    "decision_id",
    "game_id",
    "regret_gap",
    "turn_bucket",
    "game_mode",
    "action_signature",
    "high_value",
)


def _fmt(value: object) -> str:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def _md_table(headers: tuple[str, ...], rows: list[dict]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_fmt(row[h]) for h in headers) + " |")
    return "\n".join(lines)


def format_md(atlas: dict) -> str:
    """Render a deterministic markdown report for a ``teacher_disagreement_atlas`` result.

    Sections: Summary (denominators + topset/strict disagreement rates), one table per
    bucket in ``breakdowns`` (sorted by bucket-key name), Top Opportunities, and an
    honest-limitations section (``LIMITATIONS_NOTE``) making clear the rollout teacher is
    an optimistic offline counterfactual, not a gate. Purely a function of ``atlas`` --
    no time/random -- so equal input always renders equal output."""
    dataset = atlas["dataset"]
    corpus = atlas["corpus"]

    lines = ["# Teacher-Disagreement Atlas", ""]

    lines += [
        "## Summary",
        "",
        f"- dataset: `{dataset['path']}` ({dataset['rows']} rows, "
        f"{dataset['decisions']} decisions, {dataset['games']} games)",
        f"- decisions: {corpus['decisions']}",
        f"- forced: {corpus['forced']}",
        f"- multi_candidate: {corpus['multi_candidate']}",
        f"- strict_unique_choices: {corpus['strict_unique_choices']}",
        f"- topset_disagreement_rate: {_fmt(atlas['topset_disagreement_rate'])} "
        f"({corpus['topset_disagreements']}/{corpus['multi_candidate']})",
        f"- strict_disagreement_rate: {_fmt(atlas['strict_disagreement_rate'])} "
        f"({corpus['strict_disagreements']}/{corpus['strict_unique_choices']})",
        f"- high_value_threshold: {_fmt(atlas['high_value_threshold'])}",
        "",
    ]

    lines += ["## Breakdowns", ""]
    for key in sorted(atlas["breakdowns"]):
        lines += [f"### {key}", "", _md_table(_BREAKDOWN_TABLE_COLUMNS, atlas["breakdowns"][key]), ""]

    lines += ["## Top Opportunities", ""]
    if atlas["top_opportunities"]:
        lines += [_md_table(_TOP_OPPORTUNITY_COLUMNS, atlas["top_opportunities"]), ""]
    else:
        lines += ["(none)", ""]

    lines += ["## Limitations", "", LIMITATIONS_NOTE, ""]

    return "\n".join(lines) + "\n"


# --- CLI --------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    """``python -m showdown_bot.eval.teacher_disagreement <dataset> --out-md <..> --out-json <..>``

    Runs ``teacher_disagreement_atlas`` on a committed rollout-label dataset and writes both
    a markdown report (``format_md``) and a pretty, sort_keys=True JSON dump (both with a
    trailing newline)."""
    parser = argparse.ArgumentParser(
        prog="python -m showdown_bot.eval.teacher_disagreement",
        description=(
            "Mine a rollout-label dataset for WHERE the current heuristic's chosen action "
            "disagrees with the rollout teacher's best candidate."
        ),
    )
    parser.add_argument("dataset", help="path to a rollout-label .jsonl(.gz) dataset")
    parser.add_argument("--out-md", required=True, help="output path for the markdown report")
    parser.add_argument("--out-json", required=True, help="output path for the JSON atlas")
    args = parser.parse_args(argv)

    atlas = teacher_disagreement_atlas(args.dataset)
    md = format_md(atlas)
    json_text = json.dumps(atlas, indent=2, sort_keys=True) + "\n"

    out_md = Path(args.out_md)
    out_json = Path(args.out_json)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(md, encoding="utf-8")
    out_json.write_text(json_text, encoding="utf-8")

    corpus = atlas["corpus"]
    print(
        f"DISAGREEMENT ATLAS: decisions={corpus['decisions']} "
        f"strict_disagreements={corpus['strict_disagreements']} "
        f"(rate={atlas['strict_disagreement_rate']:.6f})"
    )


if __name__ == "__main__":
    main()
