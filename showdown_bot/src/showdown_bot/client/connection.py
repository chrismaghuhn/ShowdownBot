from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

import websockets

from showdown_bot.client.auth import AuthError, fetch_assertion, to_showdown_id
from showdown_bot.config import Settings
from showdown_bot.protocol.messages import parse_message

logger = logging.getLogger(__name__)


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


async def wait_for_challstr(conn: ShowdownConnection, timeout: float = 30.0) -> str:
    async def _read() -> str:
        async for raw in conn.messages():
            msg = parse_message(raw)
            if msg.prefix == "challstr":
                return "|".join(msg.args)
        raise AuthError("connection closed before challstr")

    return await asyncio.wait_for(_read(), timeout=timeout)


async def authenticate(conn: ShowdownConnection, settings: Settings) -> str:
    challstr = await wait_for_challstr(conn)
    logger.debug("received challstr %s", challstr[:20])

    assertion = await asyncio.to_thread(
        fetch_assertion,
        settings.username,
        settings.password,
        challstr,
        login_url=settings.auth_login_url,
        guest_url=settings.auth_guest_url,
    )

    await conn.send(f"|/trn {to_showdown_id(settings.username)},0,{assertion}")

    async def _wait_updateuser() -> str:
        async for raw in conn.messages():
            msg = parse_message(raw)
            if msg.prefix == "nametaken":
                raise AuthError(f"username taken: {msg.args[0] if msg.args else settings.username}")
            if msg.prefix == "updateuser":
                user = msg.args[0] if msg.args else ""
                named = msg.args[1] if len(msg.args) > 1 else "0"
                logger.info("logged in as %s (named=%s)", user.strip(), named)
                return user.strip()
        raise AuthError("connection closed before updateuser")

    return await asyncio.wait_for(_wait_updateuser(), timeout=30.0)


async def join_lobby(conn: ShowdownConnection) -> None:
    await conn.send("|/join lobby")


async def authenticate_local(conn: ShowdownConnection, username: str) -> str:
    """Log in to a ``--no-security`` local server with no assertion.

    Such servers accept ``/trn name,0,`` (empty assertion) for any free name,
    which is all the gauntlet needs."""
    await wait_for_challstr(conn)
    await conn.send(f"|/trn {username},0,")

    async def _wait_updateuser() -> str:
        async for raw in conn.messages():
            msg = parse_message(raw)
            if msg.prefix == "nametaken":
                raise AuthError(f"username taken: {username}")
            if msg.prefix == "updateuser":
                user = (msg.args[0] if msg.args else "").strip()
                named = msg.args[1] if len(msg.args) > 1 else "0"
                # Fail closed: only accept the updateuser that matches the /trn we sent.
                # The previous startswith(username[:1]) check was a no-op (both branches
                # returned the same value) and would have accepted any first character.
                if named != "1" or to_showdown_id(user) != to_showdown_id(username):
                    continue
                return user
        raise AuthError("connection closed before updateuser")

    return await asyncio.wait_for(_wait_updateuser(), timeout=30.0)
