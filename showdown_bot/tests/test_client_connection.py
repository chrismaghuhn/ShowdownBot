import asyncio

from showdown_bot.client.connection import authenticate, authenticate_local
from showdown_bot.config import Settings


class _ScriptedConnection:
    def __init__(self, message_batches):
        self._message_batches = iter(message_batches)
        self.sent = []

    async def send(self, message):
        self.sent.append(message)

    async def messages(self):
        for message in next(self._message_batches):
            yield message


def test_authenticate_local_waits_for_matching_named_identity():
    conn = _ScriptedConnection([
        ["|challstr|1|challenge"],
        [
            "|updateuser|Other User|1|0",
            "|updateuser|Target User|0|0",
            "|updateuser|Target-User|1|0",
        ],
    ])

    authenticated = asyncio.run(authenticate_local(conn, "Target User"))

    assert conn.sent == ["|/trn Target User,0,"]
    assert authenticated == "Target-User"


def test_authenticate_rejects_an_unrelated_or_not_yet_named_identity(monkeypatch, tmp_path):
    # (review finding, P1) authenticate() -- the real-server login path -- accepted the FIRST
    # updateuser message unconditionally, with no check that it matched the requested identity.
    # A stale/unrelated confirmation (or a same-name-but-not-yet-named one) was returned as if
    # it were the real login.
    import showdown_bot.client.connection as connection_mod

    monkeypatch.setattr(connection_mod, "fetch_assertion", lambda *a, **k: "fake-assertion")

    conn = _ScriptedConnection([
        ["|challstr|1|challenge"],
        [
            "|updateuser|Some Other Guy|1|0",
            "|updateuser|RealUser|0|0",
            "|updateuser|RealUser|1|0",
        ],
    ])
    settings = Settings(
        username="RealUser", password="secret", server_url="ws://x", team_path=tmp_path,
    )

    authenticated = asyncio.run(authenticate(conn, settings))

    assert authenticated == "RealUser"
