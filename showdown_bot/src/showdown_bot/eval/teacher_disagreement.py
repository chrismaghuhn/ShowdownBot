"""Teacher-Disagreement Atlas -- classification + bucketing core (2b-3.5 T1).

Mines the rollout-teacher-labelled dataset (``learning.dataset.load_rows`` output: rows shaped
``{"features": {...}, "label": {...}, "metadata": {...}}``) for WHERE the current heuristic's
chosen action disagrees with the rollout teacher's best candidate, and how large the value gap
is. Aimed measurement, not a gate -- see the design spec
``docs/superpowers/specs/2026-07-11-teacher-disagreement-atlas-design.md``.

Ported (with adaptations -- new simplified corpus schema, own exception type, no dataset-format
validation layer) from the user's external Decision-Error-Atlas prototype
(``Showdown-Bot-Analysis-Clone``, ``docs/superpowers/plans/2026-07-10-decision-error-atlas.md``
Task 5 Step 3 / ``tools/analysis/atlas_metrics.py::analyze_rollout_decisions``).

Classification per decision (a group of candidate rows sharing ``metadata.decision_id``):

  - **forced** -- a single candidate (nothing to choose).
  - **teacher-tie** -- more than one ``label.teacher_best`` row (the teacher is indifferent).
  - **genuine choice** -- more than one candidate, exactly one ``teacher_best`` row. The
    denominator for ``disagreement_rate`` (includes both agreements and disagreements).
  - **disagreement** -- a genuine choice where the chosen candidate's ``label.teacher_best`` is
    False (a subset of genuine choices).

Fail-closed invariants (ported verbatim): exactly one ``chosen_by_current_heuristic`` row per
decision, else raise; at least one ``teacher_best`` row per decision, else raise; a finite,
non-negative ``value_gap_to_best`` on the chosen row of every genuine/disagreement decision, else
raise. All raises are ``TeacherDisagreementError``.

Determinism: decisions are iterated in sorted ``decision_id`` order; bucket breakdowns are sorted
by value; ``top_opportunities`` ties break on ``decision_id``. No time/random involved.
"""
from __future__ import annotations

import math
from collections import defaultdict

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


def _turn_bucket(turn: int) -> str:
    if turn <= 3:
        return "turn_1_3"
    if turn <= 6:
        return "turn_4_6"
    return "turn_7_plus"


def _action_signature(features: dict) -> str:
    slot1 = str(features.get("slot1_action_type", "unknown"))
    slot2 = str(features.get("slot2_action_type", "unknown"))
    protects = int(bool(features.get("slot1_is_protect"))) + int(bool(features.get("slot2_is_protect")))
    return f"{slot1}+{slot2}|protects={protects}"


def _response_entropy_bucket(value: float) -> str:
    if value < 1.0:
        return "low"
    if value < 2.0:
        return "medium"
    return "high"


def _heuristic_confidence_bucket(score_gap: float) -> str:
    if score_gap <= 0.0:
        return "tie_or_inverted"
    if score_gap < 0.25:
        return "low"
    if score_gap < 1.0:
        return "medium"
    return "high"


def _nearest_rank(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(fraction * len(ordered)) - 1)
    return ordered[index]


def _breakdown(records: list[dict], key: str) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        groups[str(record[key])].append(record)
    rows = []
    for value, group in sorted(groups.items()):
        disagreements = sum(record["disagreement"] for record in group)
        gaps = [record["value_gap"] for record in group if record["disagreement"]]
        rows.append(
            {
                "value": value,
                "decisions": len(group),
                "disagreements": disagreements,
                "disagreement_rate": disagreements / len(group),
                "mean_disagreement_gap": sum(gaps) / len(gaps) if gaps else 0.0,
            }
        )
    return rows


def analyze_disagreement(decisions: dict[str, list[dict]]) -> dict:
    """Classify every decision and bucket the genuine-choice disagreements.

    ``decisions`` is a ``decision_id -> [candidate rows]`` mapping, e.g. from
    ``group_by_decision``. Returns a deterministic dict (see module docstring for the
    classification rule and the fail-closed invariants)."""
    forced = 0
    teacher_ties = 0
    records: list[dict] = []

    for decision_id, rows in sorted(decisions.items()):
        chosen_rows = [row for row in rows if bool(row["label"]["chosen_by_current_heuristic"])]
        if len(chosen_rows) != 1:
            raise TeacherDisagreementError(f"decision {decision_id} must have exactly one chosen row")
        teacher_best_rows = [row for row in rows if bool(row["label"]["teacher_best"])]
        if not teacher_best_rows:
            raise TeacherDisagreementError(f"decision {decision_id} has no teacher-best row")
        chosen = chosen_rows[0]
        features = chosen["features"]
        if len(rows) == 1:
            forced += 1
            continue
        if len(teacher_best_rows) > 1:
            teacher_ties += 1
            continue

        gap = float(chosen["label"]["value_gap_to_best"])
        if not math.isfinite(gap) or gap < 0:
            raise TeacherDisagreementError(f"decision {decision_id} has invalid value gap: {gap}")
        disagreement = not bool(chosen["label"]["teacher_best"])
        response_entropy = float(features["opponent_response_entropy"])
        heuristic_score_gap = float(features["score_gap_to_second"])
        if not math.isfinite(response_entropy) or not math.isfinite(heuristic_score_gap):
            raise TeacherDisagreementError(
                f"decision {decision_id} has non-finite confidence features"
            )
        record = {
            "decision_id": decision_id,
            "game_id": str(chosen["metadata"]["game_id"]),
            "candidate_count": len(rows),
            "disagreement": disagreement,
            "value_gap": gap,
            "turn_bucket": _turn_bucket(int(features["turn_number"])),
            "game_mode": str(features["game_mode"]),
            "action_signature": _action_signature(features),
            "speed_control_state": str(features["speed_control_state"]),
            "threat_bucket": str(int(features["ko_threatened_count"])),
            "response_entropy": response_entropy,
            "response_entropy_bucket": _response_entropy_bucket(response_entropy),
            "heuristic_score_gap": heuristic_score_gap,
            "heuristic_confidence_bucket": _heuristic_confidence_bucket(heuristic_score_gap),
        }
        records.append(record)

    disagreement_records = [record for record in records if record["disagreement"]]
    positive_gaps = [record["value_gap"] for record in disagreement_records if record["value_gap"] > 0]
    threshold = _nearest_rank(positive_gaps, 0.90)
    top_opportunities = sorted(
        (
            {**record, "high_value": record["value_gap"] >= threshold}
            for record in disagreement_records
        ),
        key=lambda record: (-record["value_gap"], record["decision_id"]),
    )[:20]
    return {
        "corpus": {
            "decisions": len(decisions),
            "forced": forced,
            "teacher_ties": teacher_ties,
            "genuine_choices": len(records),
            "disagreements": len(disagreement_records),
        },
        "disagreement_rate": len(disagreement_records) / len(records) if records else 0.0,
        "high_value_threshold": threshold,
        "breakdowns": {key: _breakdown(records, key) for key in _BREAKDOWN_KEYS},
        "top_opportunities": top_opportunities,
    }
