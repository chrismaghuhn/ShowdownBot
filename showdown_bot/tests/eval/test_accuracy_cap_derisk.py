# showdown_bot/tests/eval/test_accuracy_cap_derisk.py
from __future__ import annotations

import pytest

from showdown_bot.eval.accuracy_cap_derisk import (
    DecisionIdComponents,
    DuplicateDecisionIdError,
    assert_decision_ids_unique,
    compute_decision_id,
)


def test_compute_decision_id_is_deterministic():
    c = DecisionIdComponents(
        seed_base="abc123", seed_index=2, request_hash="rh1",
        log_prefix_hash="lp1", side="p1", rqid=5, turn=3,
    )
    assert compute_decision_id(c) == compute_decision_id(c)


def test_compute_decision_id_changes_with_any_field():
    base = DecisionIdComponents(
        seed_base="abc123", seed_index=2, request_hash="rh1",
        log_prefix_hash="lp1", side="p1", rqid=5, turn=3,
    )
    variants = [
        DecisionIdComponents(seed_base="other_seed", seed_index=2, request_hash="rh1", log_prefix_hash="lp1", side="p1", rqid=5, turn=3),
        DecisionIdComponents(seed_base="abc123", seed_index=99, request_hash="rh1", log_prefix_hash="lp1", side="p1", rqid=5, turn=3),
        DecisionIdComponents(seed_base="abc123", seed_index=2, request_hash="other_hash", log_prefix_hash="lp1", side="p1", rqid=5, turn=3),
        DecisionIdComponents(seed_base="abc123", seed_index=2, request_hash="rh1", log_prefix_hash="other_prefix", side="p1", rqid=5, turn=3),
        DecisionIdComponents(seed_base="abc123", seed_index=2, request_hash="rh1", log_prefix_hash="lp1", side="p2", rqid=5, turn=3),
        DecisionIdComponents(seed_base="abc123", seed_index=2, request_hash="rh1", log_prefix_hash="lp1", side="p1", rqid=99, turn=3),
        DecisionIdComponents(seed_base="abc123", seed_index=2, request_hash="rh1", log_prefix_hash="lp1", side="p1", rqid=5, turn=99),
    ]
    base_id = compute_decision_id(base)
    for v in variants:
        assert compute_decision_id(v) != base_id


def test_compute_decision_id_is_a_hex_sha256():
    c = DecisionIdComponents(
        seed_base="abc123", seed_index=2, request_hash="rh1",
        log_prefix_hash="lp1", side="p1", rqid=5, turn=3,
    )
    did = compute_decision_id(c)
    assert len(did) == 64
    int(did, 16)  # raises if not valid hex


def test_assert_decision_ids_unique_passes_on_unique_ids():
    assert_decision_ids_unique(["a", "b", "c"])  # no raise


def test_assert_decision_ids_unique_raises_on_duplicate():
    with pytest.raises(DuplicateDecisionIdError) as exc_info:
        assert_decision_ids_unique(["a", "b", "a", "c", "b"])
    msg = str(exc_info.value)
    assert "a" in msg and "b" in msg  # both duplicated ids named, not just a count
