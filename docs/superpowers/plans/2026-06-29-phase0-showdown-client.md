# Phase 0: Showdown Client — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Python client that connects to Pokémon Showdown, parses `|request|` JSON, generates legal VGC doubles slot-pair actions, and sends `/choose` commands — ladder-playable with a random agent.

**Architecture:** `websockets` for transport; pure functions for protocol parse/encode; `pydantic` models for battle requests; CLI entrypoint for live ladder or fixture replay.

**Tech Stack:** Python 3.11+, websockets, pydantic, pytest, python-dotenv

**Depends on:** Design spec `docs/superpowers/specs/2026-06-29-vgc-showdown-bot-design.md`

---

## File Structure

```
showdown_bot/
  pyproject.toml
  .env.example
  src/showdown_bot/
    __init__.py
    config.py
    models/
      __init__.py
      request.py          # Pydantic models for |request| JSON
      actions.py          # SlotAction, SlotPair
    protocol/
      __init__.py
      messages.py         # split/parse pipe messages
      encoder.py          # build /choose strings
    battle/
      __init__.py
      legal_actions.py    # enumerate legal slot-pairs
      random_agent.py     # pick random legal pair
    client/
      __init__.py
      connection.py       # WebSocket lifecycle
      runner.py           # battle loop glue
    cli.py
  tests/
    fixtures/
      request_force_switch.json
      request_doubles_moves.json
      request_team_preview.json
    test_messages.py
    test_request_models.py
    test_legal_actions.py
    test_encoder.py
    test_random_agent.py
  teams/
    fixed_team.txt
```

---

### Task 1: Project scaffold

**Files:**
- Create: `showdown_bot/pyproject.toml`
- Create: `showdown_bot/src/showdown_bot/__init__.py`
- Create: `showdown_bot/src/showdown_bot/config.py`
- Create: `showdown_bot/.env.example`
- Create: `showdown_bot/tests/conftest.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "showdown-bot"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "websockets>=12.0",
  "pydantic>=2.0",
  "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23"]

[project.scripts]
showdown-bot = "showdown_bot.cli:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["src"]
```

- [ ] **Step 2: Create `config.py`**

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DEFAULT_SERVER = "wss://sim3.psim.us/showdown/websocket"


@dataclass(frozen=True)
class Settings:
    username: str
    password: str
    server_url: str
    team_path: Path
    format_id: str = "gen9vgc2024regf"

    @classmethod
    def from_env(cls) -> "Settings":
        username = os.environ.get("SHOWDOWN_USERNAME", "")
        password = os.environ.get("SHOWDOWN_PASSWORD", "")
        if not username:
            raise ValueError("SHOWDOWN_USERNAME is required")
        team = Path(os.environ.get("SHOWDOWN_TEAM_PATH", "teams/fixed_team.txt"))
        server = os.environ.get("SHOWDOWN_SERVER", DEFAULT_SERVER)
        fmt = os.environ.get("SHOWDOWN_FORMAT", "gen9vgc2024regf")
        return cls(
            username=username,
            password=password,
            server_url=server,
            team_path=team,
            format_id=fmt,
        )
```

- [ ] **Step 3: Create `.env.example`**

```env
SHOWDOWN_USERNAME=MyBotName
SHOWDOWN_PASSWORD=
SHOWDOWN_SERVER=wss://sim3.psim.us/showdown/websocket
SHOWDOWN_FORMAT=gen9vgc2024regf
SHOWDOWN_TEAM_PATH=teams/fixed_team.txt
```

- [ ] **Step 4: Install and verify**

Run:
```bash
cd showdown_bot
pip install -e ".[dev]"
pytest --version
```
Expected: pytest 8.x, no errors.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/showdown_bot/ .env.example tests/conftest.py
git commit -m "chore: scaffold showdown-bot Python project"
```

---

### Task 2: Protocol message parsing

**Files:**
- Create: `src/showdown_bot/protocol/messages.py`
- Create: `tests/test_messages.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_messages.py
from showdown_bot.protocol.messages import parse_message, ParsedMessage


def test_parse_request_message():
    raw = '|request|{"rqid":1,"active":[{"moves":[]}]}'
    msg = parse_message(raw)
    assert msg.prefix == "request"
    assert msg.payload.startswith('{"rqid"')


def test_parse_battle_init():
    raw = "|init|battle"
    msg = parse_message(raw)
    assert msg.prefix == "init"
    assert msg.args == ["battle"]


def test_parse_with_room_prefix():
    raw = ">battle-gen9vgc2024regf-123|request|{}"
    msg = parse_message(raw)
    assert msg.room == "battle-gen9vgc2024regf-123"
    assert msg.prefix == "request"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_messages.py -v`  
Expected: FAIL — `ModuleNotFoundError` or `parse_message` not defined

- [ ] **Step 3: Implement `messages.py`**

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedMessage:
    prefix: str
    args: list[str]
    payload: str = ""
    room: str = ""


def parse_message(raw: str) -> ParsedMessage:
    line = raw.strip()
    room = ""
    if line.startswith(">"):
        room, line = line[1:].split("|", 1)
        line = "|" + line
    if not line.startswith("|"):
        return ParsedMessage(prefix="", args=[line])
    parts = line[1:].split("|")
    prefix = parts[0]
    args = parts[1:]
    payload = args[-1] if prefix == "request" and args else ""
    if prefix == "request":
        args = args[:-1]
    return ParsedMessage(prefix=prefix, args=args, payload=payload, room=room)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_messages.py -v`  
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/showdown_bot/protocol/ tests/test_messages.py
git commit -m "feat: parse Showdown pipe protocol messages"
```

---

### Task 3: Request JSON models

**Files:**
- Create: `src/showdown_bot/models/request.py`
- Create: `tests/fixtures/request_doubles_moves.json`
- Create: `tests/test_request_models.py`

- [ ] **Step 1: Add fixture** (`tests/fixtures/request_doubles_moves.json`)

```json
{
  "active": [
    {
      "moves": [
        {"move": "Fake Out", "id": "fakeout", "pp": 16, "maxpp": 16, "target": "adjacentFoe", "disabled": false},
        {"move": "Flare Blitz", "id": "flareblitz", "pp": 24, "maxpp": 24, "target": "normal", "disabled": false},
        {"move": "Protect", "id": "protect", "pp": 16, "maxpp": 16, "target": "self", "disabled": false},
        {"move": "Knock Off", "id": "knockoff", "pp": 32, "maxpp": 32, "target": "normal", "disabled": false}
      ],
      "canTerastallize": "Fire"
    },
    {
      "moves": [
        {"move": "Heat Wave", "id": "heatwave", "pp": 16, "maxpp": 16, "target": "allAdjacentFoes", "disabled": false},
        {"move": "Earth Power", "id": "earthpower", "pp": 16, "maxpp": 16, "target": "normal", "disabled": false},
        {"move": "Protect", "id": "protect", "pp": 16, "maxpp": 16, "target": "self", "disabled": false},
        {"move": "Solar Beam", "id": "solarbeam", "pp": 16, "maxpp": 16, "target": "normal", "disabled": false}
      ],
      "canTerastallize": "Grass"
    }
  ],
  "side": {
    "name": "Player1",
    "id": "p1",
    "pokemon": [
      {"ident": "p1: Incineroar", "details": "Incineroar, L50, F", "condition": "150/150", "active": true, "stats": {"atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100}, "moves": ["fakeout", "flareblitz", "protect", "knockoff"], "baseTypes": ["Fire", "Dark"]},
      {"ident": "p1: Rillaboom", "details": "Rillaboom, L50, M", "condition": "155/155", "active": true, "stats": {"atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100}, "moves": ["heatwave", "earthpower", "protect", "solarbeam"], "baseTypes": ["Grass"]},
      {"ident": "p1: Flutter Mane", "details": "Flutter Mane, L50", "condition": "131/131", "active": false, "stats": {"atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100}, "moves": ["moonblast", "shadowball", "dazzlinggleam", "protect"], "baseTypes": ["Ghost", "Fairy"]},
      {"ident": "p1: Landorus", "details": "Landorus-Therian, L50, M", "condition": "179/179", "active": false, "stats": {"atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100}, "moves": ["earthpower", "sludgebomb", "protect", "u-turn"], "baseTypes": ["Ground", "Flying"]}
    ]
  },
  "rqid": 2
}
```

- [ ] **Step 2: Write failing test**

```python
# tests/test_request_models.py
import json
from pathlib import Path

from showdown_bot.models.request import BattleRequest


FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_doubles_move_request():
    data = json.loads((FIXTURES / "request_doubles_moves.json").read_text())
    req = BattleRequest.model_validate(data)
    assert req.rqid == 2
    assert len(req.active) == 2
    assert req.active[0].moves[0].id == "fakeout"
    assert req.active[0].can_terastallize == "Fire"
    assert len(req.side.pokemon) == 4
```

- [ ] **Step 3: Implement `request.py`**

```python
from __future__ import annotations

from pydantic import BaseModel, Field


class MoveSlot(BaseModel):
    move: str
    id: str
    pp: int
    maxpp: int
    target: str
    disabled: bool = False


class ActiveSlot(BaseModel):
    moves: list[MoveSlot]
    can_terastallize: str | None = Field(default=None, alias="canTerastallize")
    trapped: bool | None = None

    model_config = {"populate_by_name": True}


class PokemonSlot(BaseModel):
    ident: str
    details: str
    condition: str
    active: bool
    moves: list[str] = []
    base_types: list[str] = Field(default_factory=list, alias="baseTypes")

    model_config = {"populate_by_name": True}


class SideInfo(BaseModel):
    name: str | None = None
    id: str | None = None
    pokemon: list[PokemonSlot] = []


class BattleRequest(BaseModel):
    active: list[ActiveSlot] = []
    side: SideInfo = Field(default_factory=SideInfo)
    rqid: int
    force_switch: list[bool] | None = Field(default=None, alias="forceSwitch")
    team_preview: bool | None = Field(default=None, alias="teamPreview")
    max_team_size: int | None = Field(default=None, alias="maxTeamSize")

    model_config = {"populate_by_name": True}
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_request_models.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/showdown_bot/models/ tests/fixtures/ tests/test_request_models.py
git commit -m "feat: pydantic models for Showdown battle requests"
```

---

### Task 4: Legal slot-pair enumeration

**Files:**
- Create: `src/showdown_bot/models/actions.py`
- Create: `src/showdown_bot/battle/legal_actions.py`
- Create: `tests/test_legal_actions.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_legal_actions.py
import json
from pathlib import Path

from showdown_bot.battle.legal_actions import enumerate_slot_pairs
from showdown_bot.models.request import BattleRequest

FIXTURES = Path(__file__).parent / "fixtures"


def test_enumerate_move_pairs_for_doubles():
    data = json.loads((FIXTURES / "request_doubles_moves.json").read_text())
    req = BattleRequest.model_validate(data)
    pairs = enumerate_slot_pairs(req)
    assert len(pairs) > 0
    assert all(p.slot0 is not None and p.slot1 is not None for p in pairs)
    ids = {(p.slot0.kind, p.slot1.kind) for p in pairs}
    assert ("move", "move") in ids


def test_no_double_switch_to_same_bench():
    data = json.loads((FIXTURES / "request_force_switch.json").read_text())
    req = BattleRequest.model_validate(data)
    pairs = enumerate_slot_pairs(req)
    for p in pairs:
        if p.slot0.kind == "switch" and p.slot1.kind == "switch":
            assert p.slot0.target != p.slot1.target
```

- [ ] **Step 2: Add force-switch fixture** (`tests/fixtures/request_force_switch.json`)

```json
{
  "forceSwitch": [true, false],
  "active": [
    {"moves": [{"move": "Protect", "id": "protect", "pp": 16, "maxpp": 16, "target": "self", "disabled": false}]},
    {"moves": [{"move": "Heat Wave", "id": "heatwave", "pp": 16, "maxpp": 16, "target": "allAdjacentFoes", "disabled": false}]}
  ],
  "side": {
    "pokemon": [
      {"ident": "p1: A", "details": "A", "condition": "0 fnt", "active": true, "moves": []},
      {"ident": "p1: B", "details": "B", "condition": "100/100", "active": true, "moves": []},
      {"ident": "p1: C", "details": "C", "condition": "100/100", "active": false, "moves": []},
      {"ident": "p1: D", "details": "D", "condition": "100/100", "active": false, "moves": []}
    ]
  },
  "rqid": 5
}
```

- [ ] **Step 3: Implement `actions.py` and `legal_actions.py`**

```python
# src/showdown_bot/models/actions.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class SlotAction:
    kind: Literal["move", "switch", "pass"]
    move_index: int | None = None      # 1-based for /choose
    target: int | None = None          # 1 or 2 for foe slots, -1 ally, -2 self
    terastallize: bool = False
    target_ident: str | None = None    # for switch: bench ident suffix


@dataclass(frozen=True)
class SlotPair:
    slot0: SlotAction
    slot1: SlotAction
```

```python
# src/showdown_bot/battle/legal_actions.py
from __future__ import annotations

from itertools import product

from showdown_bot.models.actions import SlotAction, SlotPair
from showdown_bot.models.request import BattleRequest


def _bench_switch_targets(req: BattleRequest, slot_index: int) -> list[SlotAction]:
    actions: list[SlotAction] = []
    for mon in req.side.pokemon:
        if mon.active or "fnt" in mon.condition:
            continue
        ident_suffix = mon.ident.split(": ", 1)[-1]
        actions.append(SlotAction(kind="switch", target_ident=ident_suffix))
    if not actions and req.force_switch and req.force_switch[slot_index]:
        actions.append(SlotAction(kind="pass"))
    return actions


def _move_targets(move_target: str) -> list[int | None]:
    if move_target == "self":
        return [None]
    if move_target in ("adjacentFoe", "normal"):
        return [1, 2]
    if move_target == "adjacentAlly":
        return [-1]
    if move_target in ("allAdjacent", "allAdjacentFoes", "all"):
        return [None]
    return [1, 2]


def _slot_move_actions(active_index: int, req: BattleRequest) -> list[SlotAction]:
    if req.force_switch and req.force_switch[active_index]:
        return _bench_switch_targets(req, active_index)
    active = req.active[active_index]
    actions: list[SlotAction] = []
    for i, move in enumerate(active.moves, start=1):
        if move.disabled:
            continue
        for target in _move_targets(move.target):
            actions.append(SlotAction(kind="move", move_index=i, target=target))
            if active.can_terastallize:
                actions.append(
                    SlotAction(kind="move", move_index=i, target=target, terastallize=True)
                )
    return actions


def enumerate_slot_pairs(req: BattleRequest) -> list[SlotPair]:
    if not req.active:
        return []
    slot0_actions = _slot_move_actions(0, req)
    slot1_actions = _slot_move_actions(1, req) if len(req.active) > 1 else [SlotAction(kind="pass")]
    pairs: list[SlotPair] = []
    for a0, a1 in product(slot0_actions, slot1_actions):
        if a0.kind == "switch" and a1.kind == "switch":
            if a0.target_ident == a1.target_ident:
                continue
        pairs.append(SlotPair(slot0=a0, slot1=a1))
    return pairs
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_legal_actions.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/showdown_bot/models/actions.py src/showdown_bot/battle/legal_actions.py tests/
git commit -m "feat: enumerate legal VGC doubles slot-pairs"
```

---

### Task 5: Action encoder (`/choose`)

**Files:**
- Create: `src/showdown_bot/protocol/encoder.py`
- Create: `tests/test_encoder.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_encoder.py
from showdown_bot.models.actions import SlotAction, SlotPair
from showdown_bot.protocol.encoder import encode_choose, format_slot_action


def test_format_move_with_target():
    a = SlotAction(kind="move", move_index=1, target=2)
    assert format_slot_action(a) == "move 1 2"


def test_format_protect():
    a = SlotAction(kind="move", move_index=3)
    assert format_slot_action(a) == "move 3"


def test_format_switch():
    a = SlotAction(kind="switch", target_ident="Rillaboom")
    assert format_slot_action(a) == "switch Rillaboom"


def test_encode_choose_with_rqid():
    pair = SlotPair(
        slot0=SlotAction(kind="move", move_index=1, target=1),
        slot1=SlotAction(kind="move", move_index=3),
    )
    assert encode_choose(pair, rqid=2) == "/choose move 1 1, move 3"
```

- [ ] **Step 2: Implement `encoder.py`**

```python
from __future__ import annotations

from showdown_bot.models.actions import SlotAction, SlotPair


def format_slot_action(action: SlotAction) -> str:
    if action.kind == "pass":
        return "pass"
    if action.kind == "switch":
        return f"switch {action.target_ident}"
    parts = ["move", str(action.move_index)]
    if action.target is not None:
        parts.append(str(action.target))
    if action.terastallize:
        parts.append("terastallize")
    return " ".join(parts)


def encode_choose(pair: SlotPair, rqid: int | None = None) -> str:
    body = f"{format_slot_action(pair.slot0)}, {format_slot_action(pair.slot1)}"
    if rqid is not None:
        return f"/choose {body} #{rqid}"
    return f"/choose {body}"
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_encoder.py -v`  
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/showdown_bot/protocol/encoder.py tests/test_encoder.py
git commit -m "feat: encode /choose commands for doubles"
```

---

### Task 6: Random agent

**Files:**
- Create: `src/showdown_bot/battle/random_agent.py`
- Create: `tests/test_random_agent.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_random_agent.py
import json
from pathlib import Path

from showdown_bot.battle.random_agent import pick_random_pair
from showdown_bot.battle.legal_actions import enumerate_slot_pairs
from showdown_bot.models.request import BattleRequest

FIXTURES = Path(__file__).parent / "fixtures"


def test_pick_random_is_legal():
    data = json.loads((FIXTURES / "request_doubles_moves.json").read_text())
    req = BattleRequest.model_validate(data)
    legal = set(enumerate_slot_pairs(req))
    pair = pick_random_pair(req, rng=__import__("random").Random(42))
    assert pair in legal
```

- [ ] **Step 2: Implement**

```python
# src/showdown_bot/battle/random_agent.py
from __future__ import annotations

import random

from showdown_bot.battle.legal_actions import enumerate_slot_pairs
from showdown_bot.models.actions import SlotPair
from showdown_bot.models.request import BattleRequest


def pick_random_pair(req: BattleRequest, rng: random.Random | None = None) -> SlotPair:
    rng = rng or random.Random()
    pairs = enumerate_slot_pairs(req)
    if not pairs:
        raise ValueError("No legal actions for request")
    return rng.choice(pairs)
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_random_agent.py -v`  
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/showdown_bot/battle/random_agent.py tests/test_random_agent.py
git commit -m "feat: random legal action agent for ladder testing"
```

---

### Task 7: WebSocket client + battle runner

**Files:**
- Create: `src/showdown_bot/client/connection.py`
- Create: `src/showdown_bot/client/runner.py`
- Create: `src/showdown_bot/cli.py`

- [ ] **Step 1: Implement `connection.py`**

```python
from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

import websockets

from showdown_bot.protocol.messages import parse_message


class ShowdownConnection:
    def __init__(self, server_url: str) -> None:
        self.server_url = server_url
        self._ws: websockets.ClientConnection | None = None

    async def connect(self) -> None:
        self._ws = await websockets.connect(self.server_url)

    async def send(self, message: str) -> None:
        if not self._ws:
            raise RuntimeError("Not connected")
        await self._ws.send(message)

    async def messages(self) -> AsyncIterator[str]:
        if not self._ws:
            raise RuntimeError("Not connected")
        async for raw in self._ws:
            yield raw

    async def close(self) -> None:
        if self._ws:
            await self._ws.close()
            self._ws = None


async def login(conn: ShowdownConnection, username: str, password: str = "") -> None:
    await conn.send("|/trn " + username + ",0," + (password or ""))
    await conn.send("|/avatar unown")
    await conn.send("|/join lobby")
```

- [ ] **Step 2: Implement `runner.py`**

```python
from __future__ import annotations

import json
import logging

from showdown_bot.battle.random_agent import pick_random_pair
from showdown_bot.config import Settings
from showdown_bot.models.request import BattleRequest
from showdown_bot.protocol.encoder import encode_choose
from showdown_bot.protocol.messages import parse_message
from showdown_bot.client.connection import ShowdownConnection, login

logger = logging.getLogger(__name__)


async def handle_battle_message(
    conn: ShowdownConnection,
    room: str,
    raw: str,
) -> None:
    msg = parse_message(raw if raw.startswith("|") else f"|{raw.split('|', 1)[-1]}")
    if msg.prefix != "request":
        return
    req = BattleRequest.model_validate(json.loads(msg.payload))
    pair = pick_random_pair(req)
    choose = encode_choose(pair, rqid=req.rqid)
    await conn.send(f">{room}|{choose}")
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
            if parsed.prefix == "request":
                await handle_battle_message(conn, parsed.room, raw)
        logger.debug("recv %s", raw[:120])
```

- [ ] **Step 3: Implement `cli.py`**

```python
from __future__ import annotations

import argparse
import asyncio
import logging

from showdown_bot.config import Settings
from showdown_bot.client.runner import run_ladder_search


def main() -> None:
    parser = argparse.ArgumentParser(description="VGC Showdown Bot")
    parser.add_argument("command", choices=["ladder"], help="Run bot on ladder")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    settings = Settings.from_env()
    if args.command == "ladder":
        asyncio.run(run_ladder_search(settings))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Manual smoke test**

Run:
```bash
cp .env.example .env
# Edit .env with real SHOWDOWN_USERNAME
showdown-bot ladder -v
```
Expected: connects, searches ladder, receives `|request|`, sends `/choose`, battle progresses without illegal move errors.

- [ ] **Step 5: Commit**

```bash
git add src/showdown_bot/client/ src/showdown_bot/cli.py
git commit -m "feat: websocket client and random ladder runner"
```

---

### Task 8: Fixture replay mode (offline test without account)

**Files:**
- Modify: `src/showdown_bot/cli.py`
- Create: `src/showdown_bot/client/fixture_runner.py`
- Create: `tests/test_fixture_runner.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_fixture_runner.py
from pathlib import Path

from showdown_bot.client.fixture_runner import replay_request_fixture

FIXTURES = Path(__file__).parent / "fixtures"


def test_replay_produces_choose_command():
    cmd = replay_request_fixture(FIXTURES / "request_doubles_moves.json")
    assert cmd.startswith("/choose ")
    assert "move" in cmd
```

- [ ] **Step 2: Implement fixture runner**

```python
# src/showdown_bot/client/fixture_runner.py
from __future__ import annotations

import json
from pathlib import Path

from showdown_bot.battle.random_agent import pick_random_pair
from showdown_bot.models.request import BattleRequest
from showdown_bot.protocol.encoder import encode_choose


def replay_request_fixture(path: Path, seed: int = 0) -> str:
    import random

    data = json.loads(path.read_text(encoding="utf-8"))
    req = BattleRequest.model_validate(data)
    pair = pick_random_pair(req, rng=random.Random(seed))
    return encode_choose(pair, rqid=req.rqid)
```

- [ ] **Step 3: Add CLI subcommand `replay-fixture`**

Extend `cli.py`:
```python
parser.add_argument("command", choices=["ladder", "replay-fixture"])
parser.add_argument("--fixture", type=str, default="tests/fixtures/request_doubles_moves.json")
# in main:
if args.command == "replay-fixture":
    from pathlib import Path
    from showdown_bot.client.fixture_runner import replay_request_fixture
    print(replay_request_fixture(Path(args.fixture)))
```

- [ ] **Step 4: Run**

```bash
pytest tests/test_fixture_runner.py -v
showdown-bot replay-fixture
```
Expected: PASS + printed `/choose ...`

- [ ] **Step 5: Commit**

```bash
git add src/showdown_bot/client/fixture_runner.py tests/test_fixture_runner.py src/showdown_bot/cli.py
git commit -m "feat: offline fixture replay for request handling"
```

---

## Phase 0 Exit Checklist

- [ ] All pytest tests pass: `pytest -v`
- [ ] `showdown-bot replay-fixture` prints valid `/choose`
- [ ] Bot completes 10 ladder games without disconnect/illegal move
- [ ] Battle logs saved per game (add logging in Task 7 if not present)

---

## Handoff to Phase 1

Phase 1 consumes:
- `BattleRequest` model
- `SlotPair` / `SlotAction`
- Saved battle logs from ladder runs

See: `docs/superpowers/plans/2026-06-29-phase1-game-engine.md`
