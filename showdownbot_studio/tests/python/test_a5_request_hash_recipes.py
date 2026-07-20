from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from conftest import REPO_ROOT

from showdownbot_studio_exporter.hashutil import canonical_json, request_hash_from_payload

FIXTURES = {
    "showdown_bot/tests/fixtures/request_doubles_moves.json": "31594636317e9438c8c52b4b6f49a4bf48a3d8c71146f2aa3cc66a62a3e283ae",
    "showdown_bot/tests/fixtures/request_team_preview.json": "9cb835c3253fb13f08d8cfdbec991fdbb05cc1fe303a6848b6bd04d1e3014e57",
    "showdown_bot/tests/fixtures/i7a_scovillain_can_mega_request.json": "443be11f769bc03f72ba75846d81805e18d9bf6dd0f7fb7399679a4e0e667bfe",
}


@pytest.mark.parametrize("rel,want", FIXTURES.items())
def test_fixture_bytes_pinned(rel: str, want: str):
    path = REPO_ROOT / rel
    got = hashlib.sha256(path.read_bytes()).hexdigest()
    assert got == want


def test_request_hash_live_offline_recipes_byte_identical():
    from showdown_bot.eval.decision_capture import _sha256, request_payload
    from showdown_bot.eval.room_raw_replay import _canonical_json as offline_canon, _sha256 as offline_sha
    from showdown_bot.models.request import BattleRequest

    for rel in FIXTURES:
        payload = json.loads((REPO_ROOT / rel).read_text(encoding="utf-8"))
        req = BattleRequest.model_validate(payload)
        live = _sha256(request_payload(req))
        dump = req.model_dump(mode="json", by_alias=True, exclude_none=False)
        offline = offline_sha(offline_canon(dump))
        studio = request_hash_from_payload(dump)
        assert live == offline
        assert live == studio
