from __future__ import annotations

import json
from pathlib import Path

import pytest

from showdown_bot.client import runner
from showdown_bot.client.runner import (
    _get_format_config,
    handle_battle_message,
    reset_format_caches,
)
from showdown_bot.models.request import BattleRequest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _clear_runner_caches():
    reset_format_caches()
    yield
    reset_format_caches()


def test_get_format_config_loads_and_caches():
    cfg1 = _get_format_config("gen9championsvgc2026regma")
    cfg2 = _get_format_config("gen9championsvgc2026regma")
    assert cfg1 is not None
    assert cfg1 is cfg2
    assert cfg1.tera is False


def test_get_format_config_missing_returns_none():
    assert _get_format_config("does_not_exist_yaml") is None
    assert "does_not_exist_yaml" in runner._format_config_cache
    assert runner._format_config_cache["does_not_exist_yaml"] is None


def _req():
    return BattleRequest.model_validate(
        json.loads((FIXTURES / "request_doubles_moves.json").read_text())
    )


@pytest.mark.asyncio
async def test_runner_passes_format_config_to_choose_with_fallback(monkeypatch):
    captured: dict = {}

    async def _fake_send(_self, _msg):
        return None

    monkeypatch.setattr(
        "showdown_bot.client.runner.choose_with_fallback",
        lambda req, **kw: captured.update(kw) or f"/choose default|{req.rqid}",
    )
    monkeypatch.setattr(runner, "_active_format", "gen9championsvgc2026regma")
    monkeypatch.setattr(runner, "_our_spreads", None)
    monkeypatch.setattr(runner, "_opp_sets", {})
    monkeypatch.setattr(runner, "_room_raw", {"battle-test": []})

    class _Conn:
        send = _fake_send

    req = _req()
    await handle_battle_message(_Conn(), "battle-test", req.model_dump_json(by_alias=True))

    assert captured["format_config"] is not None
    assert captured["format_config"].tera is False
    assert captured["format_config"] is _get_format_config("gen9championsvgc2026regma")
