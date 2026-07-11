"""Double-run identity comparison (2b-4 Task 3): the Channel-A determinism gate.

The 2b-4 override agent (``heuristic_reranker`` with the LightGBM override live) must be
byte-reproducible before ANY strength claim is made (spec: "Identity before strength —
non-negotiable"). This mirrors the T4 double-run reproduction check (see
``data/eval/t4/rerun/repro-run1-vs-run2.txt``: ``row N: winner X==Y ... turns A==B
hashes_match=True``) and T4c's row<->log binding (``normalized_room_log_sha256``, the sha256
over the normalized room log — see ``eval.room_dump.normalized_room_log_sha256`` — that T4c
binds onto every result row): two runs are "identical" iff, for every battle, ``winner``,
``turns``, and ``normalized_room_log_sha256`` all match.

No existing helper does this row-level comparison (T4's rerun check was a one-off script;
``eval.baseline.verify_winner_sequence`` compares only winner+seed and raises instead of
reporting; ``eval.room_dump.compare_battle_logs`` compares raw frames, not result rows) — see
plan Task 3 controller notes ("If a helper already exists, extend/wrap it; only write new if
none"). ``compare_identity`` is pure (no file I/O, no battle) so it is fully unit-testable
against fabricated result-row fixtures; the Kaggle kernel (``tools/kaggle/kernel_payload.py``'s
``run_gated_override_determinism``) loads two ``results.jsonl`` files and hands the parsed rows
here.
"""
from __future__ import annotations

from dataclasses import dataclass

# The triple that defines "the same battle happened" (T4/T4c): winner + turn count + the
# content hash of the normalized room log. seed/seed_index identify the battle SLOT, not its
# outcome, so they are not compared here (a slot mismatch is its own "_missing" diff below).
_IDENTITY_FIELDS = ("winner", "turns", "normalized_room_log_sha256")


@dataclass(frozen=True)
class IdentityReport:
    identical: bool
    n_compared: int
    diffs: tuple[dict, ...]


def compare_identity(results_a: list[dict], results_b: list[dict]) -> IdentityReport:
    """Pair two result-row lists by ``seed_index`` and compare winner/turns/
    normalized_room_log_sha256 per battle. Never raises: a missing/extra ``seed_index`` in
    either run becomes a ``field="_missing"`` diff (visible in the report) rather than an
    exception, and every real field mismatch on a shared ``seed_index`` becomes its own diff
    entry ``{"seed_index", "field", "a", "b"}``. ``identical`` is True iff ``diffs`` is empty;
    ``n_compared`` is the number of ``seed_index`` values present in BOTH runs (the ones
    actually field-compared — missing-row diffs are not double-counted here).
    """
    by_a = {row["seed_index"]: row for row in results_a}
    by_b = {row["seed_index"]: row for row in results_b}

    diffs: list[dict] = []
    for idx in sorted(set(by_a) - set(by_b)):
        diffs.append({"seed_index": idx, "field": "_missing", "a": by_a[idx].get("battle_id"), "b": None})
    for idx in sorted(set(by_b) - set(by_a)):
        diffs.append({"seed_index": idx, "field": "_missing", "a": None, "b": by_b[idx].get("battle_id")})

    common = sorted(set(by_a) & set(by_b))
    for idx in common:
        row_a, row_b = by_a[idx], by_b[idx]
        for field in _IDENTITY_FIELDS:
            va, vb = row_a.get(field), row_b.get(field)
            if va != vb:
                diffs.append({"seed_index": idx, "field": field, "a": va, "b": vb})

    return IdentityReport(identical=not diffs, n_compared=len(common), diffs=tuple(diffs))
