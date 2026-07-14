from __future__ import annotations

import json
from pathlib import Path

from types import SimpleNamespace

import pytest

from showdown_bot.battle.actions import JointAction, SlotAction
from showdown_bot.battle.decision import _maybe_tera
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
