from __future__ import annotations

import json

import pytest

from showdown_bot.battle.actions import JointAction
from showdown_bot.battle.candidate_identity import (
    ChosenCandidateResolutionError,
    TeraSlotDerivationError,
    assert_unique_candidate_identities,
    candidate_identity,
    derive_tera_slot,
    joint_action_key,
    resolve_chosen_candidate,
)
from showdown_bot.battle.decision_trace import CandidateTrace, DecisionTrace
from showdown_bot.battle.evaluate import OutcomeBreakdown
from showdown_bot.models.actions import SlotAction


def _ct(*, candidate_id: str, candidate_key: str | None = None, rank: int = 0) -> CandidateTrace:
    return CandidateTrace(
        candidate_id=candidate_id,
        joint_action=None,
        rank=rank,
        aggregate_score=1.0,
        score_vector=[1.0],
        outcome_breakdowns=[OutcomeBreakdown()],
        aggregate_breakdown=OutcomeBreakdown(),
        candidate_key=candidate_key,
    )


def test_joint_action_key_versioned_schema_and_deterministic():
    ja = JointAction(
        slot0=SlotAction(kind="move", move_index=1, target=1),
        slot1=SlotAction(kind="switch", target_ident="Flutter Mane"),
    )
    key = joint_action_key(ja)
    payload = json.loads(key)
    assert payload["version"] == 1
    assert len(payload["slots"]) == 2
    assert payload["slots"][0]["kind"] == "move"
    assert payload["slots"][1]["target_ident"] == "Flutter Mane"
    assert key == joint_action_key(ja)


def test_joint_action_key_distinguishes_switch_targets():
    other_slot = SlotAction(kind="pass")
    a = JointAction(
        slot0=SlotAction(kind="switch", target_ident="Incineroar"),
        slot1=other_slot,
    )
    b = JointAction(
        slot0=SlotAction(kind="switch", target_ident="Flutter Mane"),
        slot1=other_slot,
    )
    assert joint_action_key(a) != joint_action_key(b)


def test_joint_action_key_includes_terastallize():
    base = SlotAction(kind="move", move_index=2, target=1, terastallize=False)
    tera = SlotAction(kind="move", move_index=2, target=1, terastallize=True)
    assert joint_action_key(JointAction(base, SlotAction(kind="pass"))) != joint_action_key(
        JointAction(tera, SlotAction(kind="pass"))
    )


def test_derive_tera_slot_none_when_identical():
    ja = JointAction(
        slot0=SlotAction(kind="move", move_index=1, target=1),
        slot1=SlotAction(kind="pass"),
    )
    assert derive_tera_slot(ja, ja) is None


def test_derive_tera_slot_single_move_overlay():
    pre = JointAction(
        slot0=SlotAction(kind="move", move_index=1, target=1, terastallize=False),
        slot1=SlotAction(kind="pass"),
    )
    post = pre.with_tera(0)
    assert derive_tera_slot(pre, post) == 0


@pytest.mark.parametrize(
  "pre,post",
  [
      (
          JointAction(SlotAction(kind="move", move_index=1, target=1), SlotAction(kind="pass")),
          JointAction(SlotAction(kind="move", move_index=1, target=2), SlotAction(kind="pass")),
      ),
      (
          JointAction(SlotAction(kind="move", move_index=1, target=1), SlotAction(kind="pass")),
          JointAction(
              SlotAction(kind="move", move_index=1, target=1, terastallize=True),
              SlotAction(kind="move", move_index=2, target=2, terastallize=True),
          ),
      ),
      (
          JointAction(SlotAction(kind="move", move_index=1, target=1, terastallize=True), SlotAction(kind="pass")),
          JointAction(SlotAction(kind="move", move_index=1, target=1, terastallize=False), SlotAction(kind="pass")),
      ),
      (
          JointAction(SlotAction(kind="switch", target_ident="A"), SlotAction(kind="pass")),
          JointAction(SlotAction(kind="switch", target_ident="A", terastallize=True), SlotAction(kind="pass")),
      ),
      (
          JointAction(SlotAction(kind="pass"), SlotAction(kind="pass")),
          JointAction(SlotAction(kind="move", move_index=1, target=1), SlotAction(kind="pass")),
      ),
  ],
)
def test_derive_tera_slot_rejects_invalid_transitions(pre, post):
    with pytest.raises(TeraSlotDerivationError):
        derive_tera_slot(pre, post)


def test_candidate_identity_prefers_key():
    cand = _ct(candidate_id="label", candidate_key="key-a")
    assert candidate_identity(cand) == "key-a"


def test_candidate_identity_falls_back_to_label():
    cand = _ct(candidate_id="label", candidate_key=None)
    assert candidate_identity(cand) == "label"


def test_assert_unique_candidate_identities_fail_closed_on_legacy_collision():
    with pytest.raises(ChosenCandidateResolutionError):
        assert_unique_candidate_identities([
            _ct(candidate_id="(switch, pass)", candidate_key=None, rank=0),
            _ct(candidate_id="(switch, pass)", candidate_key=None, rank=1),
        ])


def test_resolve_chosen_candidate_uses_key_without_label_fallback():
    key_a = "key-a"
    key_b = "key-b"
    trace = DecisionTrace(
        chosen_candidate_key=key_a,
        chosen_candidate_id="(switch, pass)",
        candidates=[
            _ct(candidate_id="(switch, pass)", candidate_key=key_a, rank=0),
            _ct(candidate_id="(switch, pass)", candidate_key=key_b, rank=1),
        ],
    )
    resolved = resolve_chosen_candidate(trace)
    assert candidate_identity(resolved) == key_a


def test_resolve_chosen_candidate_key_ambiguous_raises():
    dup = "same-key"
    trace = DecisionTrace(
        chosen_candidate_key=dup,
        candidates=[
            _ct(candidate_id="a", candidate_key=dup, rank=0),
            _ct(candidate_id="b", candidate_key=dup, rank=1),
        ],
    )
    with pytest.raises(ChosenCandidateResolutionError, match="ambiguous"):
        resolve_chosen_candidate(trace)


def test_resolve_chosen_candidate_legacy_label_collision_raises():
    trace = DecisionTrace(
        chosen_candidate_id="(switch, pass)",
        candidates=[
            _ct(candidate_id="(switch, pass)", rank=0),
            _ct(candidate_id="(switch, pass)", rank=1),
        ],
    )
    with pytest.raises(ChosenCandidateResolutionError, match="ambiguous"):
        resolve_chosen_candidate(trace)


def test_resolve_chosen_candidate_legacy_tera_strip_fallback():
    pre_key = joint_action_key(
        JointAction(
            slot0=SlotAction(kind="move", move_index=1, target=1),
            slot1=SlotAction(kind="pass"),
        )
    )
    trace = DecisionTrace(
        chosen_candidate_id="(Fake Out->1 tera, pass)",
        candidates=[_ct(candidate_id="(Fake Out->1, pass)", candidate_key=pre_key, rank=0)],
    )
    resolved = resolve_chosen_candidate(trace)
    assert resolved.rank == 0
