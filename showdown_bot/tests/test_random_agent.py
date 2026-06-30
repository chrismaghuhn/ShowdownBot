import json
import random
from copy import deepcopy
from pathlib import Path

from showdown_bot.battle.random_agent import pick_random_pair
from showdown_bot.battle.legal_actions import enumerate_slot_pairs
from showdown_bot.models.request import BattleRequest

FIXTURES = Path(__file__).parent / "fixtures"


def _req(name="request_doubles_moves.json") -> BattleRequest:
    return BattleRequest.model_validate(
        json.loads((FIXTURES / name).read_text())
    )


def test_pick_random_is_legal():
    req = _req()
    legal = set(enumerate_slot_pairs(req))
    pair = pick_random_pair(req, rng=random.Random(42))
    assert pair in legal


def test_random_never_double_tera_when_both_can_tera():
    """Both active slots have canTerastallize — sampled pairs must NEVER have
    terastallize=True on BOTH slots simultaneously (Showdown only allows one
    Terastallization per side per battle)."""
    req = _req()
    # Verify the fixture actually has both slots with tera available
    assert req.active is not None
    assert req.active[0].can_terastallize, "fixture slot0 must have canTerastallize for this test"
    assert req.active[1].can_terastallize, "fixture slot1 must have canTerastallize for this test"

    rng = random.Random(0)
    for _ in range(200):
        pair = pick_random_pair(req, rng=rng)
        assert not (pair.slot0.terastallize and pair.slot1.terastallize), (
            f"Illegal double-tera in sampled pair: {pair}"
        )


def test_random_no_tera_when_cannot_tera():
    """If a slot's canTerastallize is falsy, the sampler must never produce a
    terastallize=True action for that slot."""
    data = json.loads((FIXTURES / "request_doubles_moves.json").read_text())
    # Remove canTerastallize from both slots
    for active_slot in data["active"]:
        active_slot.pop("canTerastallize", None)
        active_slot["canTerastallize"] = None  # or omit entirely

    req = BattleRequest.model_validate(data)
    rng = random.Random(1)
    for _ in range(200):
        pair = pick_random_pair(req, rng=rng)
        assert not pair.slot0.terastallize, f"slot0 tera when not available: {pair}"
        assert not pair.slot1.terastallize, f"slot1 tera when not available: {pair}"
