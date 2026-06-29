from __future__ import annotations

import json
import re
from pathlib import Path

from showdown_bot.client.gauntlet import GauntletStats, agent_choose
from showdown_bot.models.request import BattleRequest

FIXTURES = Path(__file__).parent / "fixtures"
CHOOSE_RE = re.compile(r"^/choose ")


def _req():
    return BattleRequest.model_validate(
        json.loads((FIXTURES / "request_doubles_moves.json").read_text())
    )


def test_agent_choose_random_without_state():
    out = agent_choose("random", _req(), state=None, book=None, our_side="p1")
    assert CHOOSE_RE.match(out)


def test_agent_choose_falls_back_when_no_state():
    # heuristic with no state should still produce a legal choice (random path)
    out = agent_choose("heuristic", _req(), state=None, book=None, our_side="p1")
    assert CHOOSE_RE.match(out)


def test_gauntlet_stats_winrate_and_p95():
    s = GauntletStats(games=4, hero_wins=3)
    assert s.winrate == 0.75
    s.latencies = [0.1, 0.2, 0.3, 0.4, 1.0]
    assert s.latency_p95() == 1.0
