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
