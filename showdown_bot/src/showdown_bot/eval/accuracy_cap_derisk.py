"""Accuracy branch-cap / ambiguous-candidate de-risk study (spec:
docs/superpowers/specs/2026-07-13-accuracy-cap-derisk-design.md). Pure, unit-tested logic only --
real corpus runs live in showdown_bot/scripts/. The cap=4 gate verdict
(data/eval/accuracy-gate/gate-b-report.json) is never recomputed here; this module only supports
the auxiliary action-capture / cross-cap comparison / ambiguous-candidate diagnostic described in
the spec.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True)
class DecisionIdComponents:
    seed_base: str
    seed_index: int
    request_hash: str
    log_prefix_hash: str
    side: str
    rqid: int
    turn: int


def compute_decision_id(c: DecisionIdComponents) -> str:
    """Spec Sec.2.2's fixed schema: sha256(canonical_json([seed_base, seed_index, request_hash,
    log_prefix_hash, side, rqid, turn])). Canonical JSON here means: a fixed-order list (not a
    dict, so key-ordering ambiguity can't exist), compact separators, ensure_ascii -- deterministic
    across processes/machines by construction, not by convention."""
    payload = [
        c.seed_base, c.seed_index, c.request_hash, c.log_prefix_hash, c.side, c.rqid, c.turn,
    ]
    canonical = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class DuplicateDecisionIdError(Exception):
    pass


def assert_decision_ids_unique(decision_ids: list[str]) -> None:
    """Fail-closed uniqueness check, spec Sec.2.2 -- raise (not warn, not dedupe) the instant a
    collision is found, naming every duplicated id so the caller can investigate immediately."""
    counts = Counter(decision_ids)
    dupes = {did: n for did, n in counts.items() if n > 1}
    if dupes:
        raise DuplicateDecisionIdError(
            f"{len(dupes)} decision_id collision(s) out of {len(decision_ids)} total: {dupes}"
        )
