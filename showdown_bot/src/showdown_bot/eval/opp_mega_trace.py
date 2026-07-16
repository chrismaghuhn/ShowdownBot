"""Opp-mega-evidence sidecar (I7b-C): proves a foe-Mega hypothesis was
GENERATED and SCORED for a hero decision -- never read to make a decision,
never a substitute for the actual protocol Mega event, off by default.

Built directly from battle.mega_scoring.ScoredResponseEvidence (candidate_key,
response_id, foe_mega_slot, branch_index, branch_weight, world_index,
world_weight, response_weight, raw_score, required_classes, retained_classes)
-- raw components only, never a pre-multiplied "contribution" (Rev. 3 finding
4b/4c: aggregate_scores is non-linear under MUST_REACT (`mean - lambda*(mean-min)`)
and NEUTRAL (`mean - lambda*variance`), so no single per-response product is
correct under both; consumers multiply the components themselves per their own
operator). NOT a loose response/weight list correlated only by
battle_id/decision_index -- that link is too weak to prove which candidate was
scored against which response.

Three facts that must never be conflated (Rev. 4 finding 7):
  required_classes -- the eligibility set R, from the scoring call's own
                      pre-cap discovery;
  retained_classes -- what predict_responses actually returned after the
                      coverage-preserving cap;
  scored_classes   -- what survived projection and actually contributed a score.
A class absent from scored evidence cannot prove the cap retained it, so a
"reserved_classes" field would be invalid and deliberately does not exist.

Schema is deliberately separate from decision-trace-v3 (see
docs/superpowers/specs/2026-07-16-champions-opponent-mega-i7b-audit.md Sec.5):
response-level opponent data has no analogue in the v3 candidate schema and must
not silently overload it. Mirrors research/aggregation_trace.py's shape
(context/row-builder/validator/writer split, SHOWDOWN_*_OUT env gate,
NON_BEHAVIORAL classification).
"""
from __future__ import annotations

import json
from dataclasses import dataclass


class OppMegaTraceError(ValueError):
    pass


@dataclass(frozen=True)
class OppMegaTraceContext:
    battle_id: str
    config_id: str
    config_hash: str
    schedule_hash: str
    format_id: str
    git_sha: str


_REQUIRED_FIELDS = frozenset({
    "battle_id", "config_id", "config_hash", "schedule_hash", "format_id", "git_sha",
    "decision_index", "turn_number", "candidate_keys", "response_ids", "foe_mega_slots",
    "branch_indices", "branch_weights", "world_indices", "world_weights",
    "response_weights", "raw_scores", "required_classes", "retained_classes",
    "scored_classes", "max_candidates",
    "opp_mega_click_rate",
})
_PARALLEL_FIELDS = (
    "candidate_keys", "response_ids", "foe_mega_slots", "branch_indices",
    "branch_weights", "world_indices", "world_weights", "response_weights", "raw_scores",
)


def _coverage_classes(evidence: list) -> tuple[list[str], list[str], list[str]]:
    if not evidence:
        return [], [], []
    required_sets = {tuple(e.required_classes) for e in evidence}
    retained_sets = {tuple(e.retained_classes) for e in evidence}
    if len(required_sets) != 1 or len(retained_sets) != 1:
        raise OppMegaTraceError(
            "all evidence in one decision row must agree on required/retained classes"
        )
    required = sorted(next(iter(required_sets)))
    retained = sorted(next(iter(retained_sets)))
    scored = sorted({
        "none" if e.foe_mega_slot is None else str(e.foe_mega_slot)
        for e in evidence
    })
    return required, retained, scored


def build_opp_mega_trace_row(
    *, context: OppMegaTraceContext, decision_index: int, turn_number: int,
    evidence: list, max_candidates: int, click_rate: float,
) -> dict:
    required_classes, retained_classes, scored_classes = _coverage_classes(evidence)
    return {
        "battle_id": context.battle_id,
        "config_id": context.config_id,
        "config_hash": context.config_hash,
        "schedule_hash": context.schedule_hash,
        "format_id": context.format_id,
        "git_sha": context.git_sha,
        "decision_index": decision_index,
        "turn_number": turn_number,
        "candidate_keys": [e.candidate_key for e in evidence],
        "response_ids": [e.response_id for e in evidence],
        "foe_mega_slots": [e.foe_mega_slot for e in evidence],
        "branch_indices": [e.branch_index for e in evidence],
        "branch_weights": [float(e.branch_weight) for e in evidence],
        "world_indices": [e.world_index for e in evidence],
        "world_weights": [float(e.world_weight) for e in evidence],
        "response_weights": [float(e.response_weight) for e in evidence],
        "raw_scores": [float(e.raw_score) for e in evidence],
        "required_classes": required_classes,
        "retained_classes": retained_classes,
        "scored_classes": scored_classes,
        "max_candidates": max_candidates,
        "opp_mega_click_rate": click_rate,
    }


def validate_opp_mega_trace_row(row: dict) -> None:
    missing = _REQUIRED_FIELDS - set(row)
    unknown = set(row) - _REQUIRED_FIELDS
    if missing or unknown:
        raise OppMegaTraceError(
            f"opp-mega-trace row fields missing={sorted(missing)} unknown={sorted(unknown)}"
        )
    lengths = {len(row[f]) for f in _PARALLEL_FIELDS}
    if len(lengths) > 1:
        raise OppMegaTraceError(
            f"opp-mega-trace row's parallel arrays must share one length, got {lengths}"
        )
    for field_name in ("required_classes", "retained_classes", "scored_classes"):
        if not isinstance(row[field_name], list):
            raise OppMegaTraceError(f"{field_name} must be a list")
    if not set(row["required_classes"]) <= set(row["retained_classes"]):
        raise OppMegaTraceError("required_classes must be a subset of retained_classes")
    if not set(row["scored_classes"]) <= set(row["retained_classes"]):
        raise OppMegaTraceError("scored_classes must be a subset of retained_classes")


class OppMegaTraceWriter:
    def __init__(self, path: str) -> None:
        self.path = path

    def write(self, row: dict) -> None:
        validate_opp_mega_trace_row(row)
        # sort_keys + compact separators: the sidecar is provenance, so the same
        # decision must serialise byte-identically regardless of dict insertion
        # order or platform.
        #
        # newline="" (I7b-C Rev. 9 finding 4) disables the platform newline
        # translation that text mode applies on write: without it, every "\n"
        # below lands on disk as "\r\n" under Windows, so the SAME decision
        # produces different bytes -- and a different digest -- than it does on
        # the Linux CI/eval hosts. JSONL is an interchange format; LF-only is the
        # only cross-platform-stable choice. (Reading such a file back in text
        # mode hides this, since universal newlines translate "\r\n" to "\n" --
        # which is why the test asserts on raw bytes.)
        with open(self.path, "a", encoding="utf-8", newline="") as fh:
            fh.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
