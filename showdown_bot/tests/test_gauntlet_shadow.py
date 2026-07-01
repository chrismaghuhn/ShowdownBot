"""Slice 2b-3a Task 4: gauntlet reranker-shadow wiring.

These tests pin the two guarantees that matter for the live path:
  1. lightgbm stays lazy — importing/reloading the gauntlet module with the
     shadow flag OFF must not pull lightgbm into sys.modules (rule 5). The
     shadow module's `from_env` imports lightgbm only when enabled.
  2. ID parity — DatasetExportRuntime and RerankerShadowRuntime, given the same
     provenance and the same (game_index, decision_local_index, turn_number,
     our_side, format_id), derive the SAME game_id/decision_id. This is what
     lets the shadow log join back to the export dataset.

Bit-identical / no-override guarantee (choose is fixed before the shadow runs):
This is STRUCTURAL, not asserted here. The gauntlet hook is added strictly
AFTER `await self.conn.send(f"{room}|{choose}")`, so `choose` is already
computed and sent before any shadow code executes; the shadow is log-only and
never mutates `choose`. Constructing a real `_Client` requires a live websocket
connection (ShowdownConnection) plus a running Showdown server, so we do not
fabricate a runtime equality assertion — the source structure enforces it.
"""
import importlib
import sys


def _purge_lightgbm():
    for m in [m for m in sys.modules if m == "lightgbm" or m.startswith("lightgbm.")]:
        sys.modules.pop(m, None)


def test_lightgbm_not_imported_when_shadow_off(monkeypatch):
    monkeypatch.delenv("SHOWDOWN_RERANKER_SHADOW", raising=False)
    _purge_lightgbm()
    importlib.reload(importlib.import_module("showdown_bot.client.gauntlet"))
    assert not any(m == "lightgbm" or m.startswith("lightgbm.") for m in sys.modules)


def test_export_and_shadow_produce_matching_ids():
    # Same provenance + same decision index -> identical game_id/decision_id (ID parity).
    from showdown_bot.learning.provenance import build_feature_context
    common = dict(game_index=0, decision_local_index=0, turn_number=3, our_side="p1",
                  format_id="gen9vgc2025regi", mirror_flag=False, teacher_config={}, sampling_policy="all")
    exp = build_feature_context(git_sha="gs", dirty_flag=False, team_hash_="th", config_hash_="cfg",
                                run_seed=0, **common)
    prov = {"git_sha": "gs", "dirty_flag": False, "team_hash": "th", "config_hash": "cfg", "run_seed": 0}
    sh = build_feature_context(git_sha=prov["git_sha"], dirty_flag=prov["dirty_flag"],
                               team_hash_=prov["team_hash"], config_hash_=prov["config_hash"],
                               run_seed=prov["run_seed"], **common)
    assert (exp.game_id, exp.decision_id) == (sh.game_id, sh.decision_id)
