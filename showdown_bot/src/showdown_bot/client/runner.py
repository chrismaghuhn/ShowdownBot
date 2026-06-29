from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from showdown_bot.battle.random_agent import pick_random_pair
from showdown_bot.client.connection import ShowdownConnection, login
from showdown_bot.config import Settings
from showdown_bot.models.request import BattleRequest
from showdown_bot.protocol.encoder import encode_choose
from showdown_bot.protocol.messages import parse_message

logger = logging.getLogger(__name__)

LOG_DIR = Path("logs")
_battle_logs: dict[str, Path] = {}


def _log_battle_line(room: str, raw: str) -> None:
    if not room.startswith("battle-"):
        return
    LOG_DIR.mkdir(exist_ok=True)
    if room not in _battle_logs:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        _battle_logs[room] = LOG_DIR / f"{room}_{ts}.log"
    _battle_logs[room].open("a", encoding="utf-8").write(raw + "\n")


async def handle_battle_message(conn: ShowdownConnection, raw: str) -> None:
    msg = parse_message(raw)
    if msg.prefix != "request" or not msg.room.startswith("battle-"):
        return
    req = BattleRequest.model_validate(json.loads(msg.payload))
    pair = pick_random_pair(req)
    choose = encode_choose(pair, rqid=req.rqid)
    await conn.send(f">{msg.room}|{choose}")
    logger.info("sent %s", choose)


async def run_ladder_search(settings: Settings) -> None:
    conn = ShowdownConnection(settings.server_url)
    await conn.connect()
    await login(conn, settings.username, settings.password)
    team = settings.team_path.read_text(encoding="utf-8")
    await conn.send(f"|/utm {team}")
    await conn.send(f"|/search {settings.format_id}")

    async for raw in conn.messages():
        parsed = parse_message(raw)
        if parsed.prefix == "updatesearch" and "games" in parsed.args:
            continue
        if parsed.room.startswith("battle-"):
            _log_battle_line(parsed.room, raw)
            if parsed.prefix == "request":
                await handle_battle_message(conn, raw)
        logger.debug("recv %s", raw[:120])
