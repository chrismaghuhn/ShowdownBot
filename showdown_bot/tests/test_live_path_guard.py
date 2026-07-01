"""T3c live-path guard: the live bot must never import the eval-only opponent policies.

`eval/opponents/` depends on `battle/` (one-way); the live decision path (`battle/*` +
`client/runner`/`fixture_runner`) must NOT depend on `eval/opponents/`. The gauntlet's
`agent_choose` may (via local imports) — it is the eval dispatch, not the live bot.
"""
from __future__ import annotations

import re
from pathlib import Path

import showdown_bot.battle.decision as _decision

_PAT = re.compile(r"eval[./]opponents")


def test_live_decision_and_runner_do_not_import_eval_opponents():
    battle_dir = Path(_decision.__file__).parent          # .../showdown_bot/battle/
    client_dir = battle_dir.parent / "client"
    live_files = list(battle_dir.glob("*.py")) + [
        client_dir / "runner.py",
        client_dir / "fixture_runner.py",
    ]
    offenders = [
        f.name for f in live_files
        if f.exists() and _PAT.search(f.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"live path must not import eval/opponents: {offenders}"
