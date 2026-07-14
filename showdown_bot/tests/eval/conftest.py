# showdown_bot/tests/eval/conftest.py
"""Shared pytest fixtures for showdown_bot/tests/eval/ -- kept minimal, just the one fixture
Task 3's tests need (not a duplicate of the top-level tests/conftest.py's decision_fixture,
which bundles fake calc/oracle/speed/dex objects this suite doesn't use)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from showdown_bot.models.request import BattleRequest

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def scripted_request() -> BattleRequest:
    data = json.loads((FIXTURES / "request_doubles_moves.json").read_text())
    return BattleRequest.model_validate(data)
