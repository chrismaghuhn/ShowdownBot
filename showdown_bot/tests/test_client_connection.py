import asyncio

from showdown_bot.client.connection import authenticate_local


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
