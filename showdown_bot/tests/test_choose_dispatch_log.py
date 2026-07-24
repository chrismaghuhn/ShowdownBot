"""The submitted /choose string, logged next to the rqid it was computed for.

Diagnosing the trapped-switch class stalled TWICE on the same missing artefact: the room dump is
the server->client stream only, so the bot's own submitted choice -- and crucially WHICH request it
was computed against -- never appears. B1 is verified correct on the request that precedes the
error, so the switch comes from somewhere else; without the rqid the choice was computed for, a
stale-choice dispatch cannot be distinguished from a second dispatch path by evidence.

Two properties are pinned here:
  1. the dump the diagnostic writer sees CONTAINS `>choose rqid=<N> <choice>`, with N the rqid of
     the request the choice was computed from;
  2. `room_raw` itself stays FREE of that line -- it is fed to BattleState.from_log_text
     (client/gauntlet.py:555), so writing a synthetic frame into it would change parsing, i.e.
     change how the bot plays. The log must never touch the decision path.
"""
from __future__ import annotations

import asyncio
import json

from showdown_bot.client.gauntlet import _Client

ROOM = "battle-gen9-test-1"


class _FakeConn:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, msg: str) -> None:
        self.sent.append(msg)


def _client(conn):
    return _Client(conn=conn, name="T", agent="max_damage", book=None, priors=None,
                   format_id="gen9vgc2025regi", packed_team="", opp_sets={})


def _payload(rqid: int) -> str:
    return json.dumps({
        "active": [{"moves": [
            {"move": "Rock Slide", "id": "rockslide", "pp": 8, "maxpp": 8,
             "target": "allAdjacentFoes", "disabled": False},
        ]}],
        "side": {"name": "T", "id": "p1", "pokemon": [
            {"ident": "p1: Aerodactyl", "details": "Aerodactyl, L50", "condition": "100/100",
             "active": True, "stats": {"atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100},
             "moves": ["rockslide"]},
        ]},
        "rqid": rqid,
    })


def _drive(rqid: int):
    conn = _FakeConn()
    c = _client(conn)
    asyncio.run(c.handle_request(ROOM, _payload(rqid)))
    return c, conn


def test_dump_frames_contain_the_choose_line_with_the_rqid_it_was_computed_for():
    c, conn = _drive(7)
    assert conn.sent, "the client must have dispatched a choice"
    lines = [l for l in c.dump_frames(ROOM) if l.startswith(">choose ")]
    assert len(lines) == 1, f"expected exactly one >choose line, got {lines}"
    assert lines[0].startswith(">choose rqid=7 "), lines[0]
    # the logged choice must be the string actually sent (conn.sent is "<room>|<choose>")
    sent_choice = conn.sent[-1].split("|", 1)[1]
    assert lines[0] == f">choose rqid=7 {sent_choice}"


def test_room_raw_stays_free_of_the_choose_line():
    """room_raw feeds BattleState.from_log_text -- a synthetic frame there would change parsing,
    and therefore how the bot plays. The log lives beside it, never in it."""
    c, _ = _drive(11)
    assert not any(">choose" in frame for frame in c.room_raw.get(ROOM, []))


def test_the_logged_rqid_tracks_the_request_not_a_counter():
    """Two decisions in a row must each carry their OWN request's rqid -- that is the whole point:
    a choice logged with an rqid older than the request the server errored on is exactly the
    stale-dispatch signature this artefact exists to make visible."""
    conn = _FakeConn()
    c = _client(conn)
    asyncio.run(c.handle_request(ROOM, _payload(4)))
    asyncio.run(c.handle_request(ROOM, _payload(6)))
    rqids = [l.split()[1] for l in c.dump_frames(ROOM) if l.startswith(">choose ")]
    assert rqids == ["rqid=4", "rqid=6"], rqids
