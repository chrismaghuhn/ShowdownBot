from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DEFAULT_SERVER = "wss://sim3.psim.us/showdown/websocket"
DEFAULT_LOGIN_URL = "https://play.pokemonshowdown.com/api/login"
DEFAULT_GUEST_URL = "https://play.pokemonshowdown.com/action.php"


@dataclass(frozen=True)
class Settings:
    username: str
    password: str
    server_url: str
    team_path: Path
    format_id: str = "gen9vgc2025regg"
    auth_login_url: str = DEFAULT_LOGIN_URL
    auth_guest_url: str = DEFAULT_GUEST_URL

    @classmethod
    def from_env(cls) -> "Settings":
        username = os.environ.get("SHOWDOWN_USERNAME", "")
        password = os.environ.get("SHOWDOWN_PASSWORD", "")
        if not username:
            raise ValueError("SHOWDOWN_USERNAME is required")
        team = Path(os.environ.get("SHOWDOWN_TEAM_PATH", "teams/fixed_team.txt"))
        server = os.environ.get("SHOWDOWN_SERVER", DEFAULT_SERVER)
        fmt = os.environ.get("SHOWDOWN_FORMAT", "gen9vgc2025regg")
        login_url = os.environ.get("SHOWDOWN_AUTH_LOGIN_URL", DEFAULT_LOGIN_URL)
        guest_url = os.environ.get("SHOWDOWN_AUTH_GUEST_URL", DEFAULT_GUEST_URL)
        return cls(
            username=username,
            password=password,
            server_url=server,
            team_path=team,
            format_id=fmt,
            auth_login_url=login_url,
            auth_guest_url=guest_url,
        )
