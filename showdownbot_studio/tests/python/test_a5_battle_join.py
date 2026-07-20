from __future__ import annotations

import json

import pytest

from conftest import STUDIO_ROOT

from showdownbot_studio_exporter.export_battle import export_battle_jsonl, read_battle_log
from showdownbot_studio_exporter.export_decisions import export_decisions_jsonl, load_trace_rows
from showdownbot_studio_exporter.join import index_requests_from_log, join_request_protocol_indices

FIX01 = STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources" / "fixture-01"


def test_sparse_protocol_index_gaps():
    log = read_battle_log(FIX01 / "battle.log")
    battle = export_battle_jsonl(log)
    indices = [json.loads(ln)["protocol_index"] for ln in battle.decode("utf-8").splitlines()]
    assert indices == sorted(indices)
    assert len(indices) < len(log)


def test_move_event_does_not_set_pokemon_species():
    lines = [
        "|switch|p1a: Pikachu|Pikachu, L50|35/35",
        "|move|p1a: Pikachu|Tackle|p2a: Bulbasaur",
    ]
    rows = [json.loads(ln) for ln in export_battle_jsonl(lines).decode("utf-8").splitlines()]
    switch, move = rows
    assert switch["type"] == "switch"
    assert switch["pokemon"]["species"] == "Pikachu"
    assert move["type"] == "move"
    assert move["details"] == "Tackle"
    assert "species" not in move.get("pokemon", {})


def test_join_resolves_fixture01():
    log = read_battle_log(FIX01 / "battle.log")
    rows = load_trace_rows(FIX01 / "decision_trace.jsonl")
    joined = join_request_protocol_indices(rows, log)
    assert all(v is not None for v in joined.values())


def test_request_skip_rules():
    lines = [
        "|request|" + json.dumps({"rqid": 1, "wait": False, "side": {"id": "p1"}}),
        "|request|" + json.dumps({"rqid": 1, "wait": False, "side": {"id": "p1"}}),
        "|request|" + json.dumps({"rqid": 2, "wait": True, "side": {"id": "p1"}}),
        "|request|" + json.dumps({"rqid": 3, "wait": False, "side": {"id": "p1"}}),
    ]
    entries = index_requests_from_log(lines)
    assert len(entries) == 2
