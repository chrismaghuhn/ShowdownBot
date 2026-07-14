"""Regression: duplicate empty |win| callbacks must not double-count or emit rows.

When room_raw is popped after the first |win|, a second callback with empty
room_frames used to increment stats and fail record assembly (winner None).
"""
from __future__ import annotations

import asyncio
import random

import pytest

from showdown_bot.client import gauntlet as g


class _FakeConn:
    async def connect(self):
        return None

    async def send(self, _msg):
        return None

    async def close(self):
        return None


@pytest.mark.asyncio
async def test_empty_duplicate_win_callback_counts_one_game_and_one_row(monkeypatch):
    async def _auth(_conn, _name):
        return None

    monkeypatch.setattr(g, "ShowdownConnection", lambda _url: _FakeConn())
    monkeypatch.setattr(g, "authenticate_local", _auth)
    monkeypatch.setattr(g, "_load_belief_deps", lambda _fmt: (None, None, None))
    monkeypatch.setattr(g, "_resolve_side_teams", lambda _t, _o: ("packed1", "packed2"))
    monkeypatch.setattr(g, "_is_mirror_battle", lambda _t, _o: False)
    monkeypatch.setattr(random, "randint", lambda _a, _b: 1234)

    hero_name = "HeuristicBot1234"
    villain_name = "BaselineBot1234"
    frames = "\n".join([
        f"|player|p1|{hero_name}",
        f"|player|p2|{villain_name}",
        "|switch|p1a: Incineroar|Incineroar, L50|100/100",
        "|switch|p2a: Rillaboom|Rillaboom, L50|100/100",
        "|turn|1",
        f"|win|{hero_name}",
    ])

    async def fake_run_client(client, *, accept_from, on_result, stop):
        if on_result is not None:
            await on_result(hero_name, [frames], None)
            await on_result(None, [], None)
        await stop.wait()

    monkeypatch.setattr(g, "_run_client", fake_run_client)

    records = []
    stats = await g.run_local_gauntlet(
        games=1,
        hero_agent="heuristic",
        villain_agent="max_damage",
        format_id="gen9championsvgc2026regma",
        team_path="teams/fixed_team.txt",
        on_battle_result=records.append,
    )

    assert stats.games == 1
    assert len(records) == 1
    assert records[0]["winner"] == "hero"
