from __future__ import annotations

from typing import AsyncIterator

import websockets


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
