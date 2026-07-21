from __future__ import annotations

import json
from pathlib import Path

from types import SimpleNamespace

import pytest

from showdown_bot.battle.actions import JointAction, SlotAction
from showdown_bot.battle.decision import _maybe_tera, _plan_my_actions
from showdown_bot.engine.format_config import load_format_config
from showdown_bot.models.request import BattleRequest

FIXTURES = Path(__file__).parent / "fixtures"


def _req() -> BattleRequest:
    return BattleRequest.model_validate(
        json.loads((FIXTURES / "request_doubles_moves.json").read_text())
    )


def _best_ja() -> JointAction:
    return JointAction(
        SlotAction(kind="move", move_index=1, target=1),
        SlotAction(kind="pass"),
    )


def _maybe_tera_args(req, best, *, format_config=None):
    return dict(
        req=req,
        best_ja=best,
        best_val=1.0,
        mode=None,
        state=SimpleNamespace(field={}),
        our_side="p1",
        opp_side="p2",
        speed_oracle=None,
        opp_resps=[],
        model=SimpleNamespace(damage_fn=lambda: None),
        weights=None,
        risk_lambda=0.5,
        tera_margin=0.1,
        format_config=format_config,
    )


@pytest.fixture
def _spy_plan_my_actions(monkeypatch):
    import showdown_bot.battle.decision as decision

    calls: list = []
    monkeypatch.setattr(
        decision,
        "_plan_my_actions",
        lambda *a, **k: calls.append((a, k)) or [],
    )
    monkeypatch.setattr(decision, "evaluate_line", lambda *a, **k: (0.0,))
    return calls


def test_maybe_tera_cfg_tera_false_skips_overlay(_spy_plan_my_actions):
    cfg = load_format_config("gen9championsvgc2026regma")
    best = _best_ja()
    result = _maybe_tera(**_maybe_tera_args(_req(), best, format_config=cfg))
    assert result is best
    assert _spy_plan_my_actions == []


def test_maybe_tera_format_config_none_enters_overlay_loop(_spy_plan_my_actions):
    best = _best_ja()
    _maybe_tera(**_maybe_tera_args(_req(), best, format_config=None))
    assert len(_spy_plan_my_actions) >= 1


def test_maybe_tera_regi_cfg_tera_true_enters_overlay_loop(_spy_plan_my_actions):
    cfg = load_format_config("gen9vgc2025regi")
    assert cfg.tera is True
    best = _best_ja()
    _maybe_tera(**_maybe_tera_args(_req(), best, format_config=cfg))
    assert len(_spy_plan_my_actions) >= 1


def test_null_active_slot_is_safe_in_planning_and_tera_overlay(_spy_plan_my_actions):
    original = _req()
    req = original.model_copy(update={"active": [original.active[0], None]})
    slot1_move = JointAction(
        SlotAction(kind="pass"),
        SlotAction(kind="move", move_index=1, target=1),
    )
    plans = _plan_my_actions(
        req,
        slot1_move,
        state=SimpleNamespace(side=lambda _side: {}),
        our_side="p1",
        opp_side="p2",
        speed_oracle=None,
    )
    assert [plan.kind for plan in plans] == ["pass", "move"]
    assert _maybe_tera(**_maybe_tera_args(req, slot1_move, format_config=None)) is slot1_move
