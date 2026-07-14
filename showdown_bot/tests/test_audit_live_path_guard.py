"""Isolation guard: no live/battle/teacher/inference module may import the offline
audit package (Phase 3, dataset-reranker-audit slice, Task 9)."""
from pathlib import Path


def test_live_paths_do_not_import_learning_audit():
    repo = Path(__file__).resolve().parents[1] / "src" / "showdown_bot"
    forbidden = [
        repo / "battle", repo / "client" / "gauntlet.py",
        repo / "learning" / "teacher.py", repo / "learning" / "rollout.py",
        repo / "learning" / "reranker_shadow.py", repo / "learning" / "reranker_override.py",
    ]
    offenders = []
    for path in forbidden:
        files = path.rglob("*.py") if path.is_dir() else [path]
        for file in files:
            if "showdown_bot.learning.audit" in file.read_text(encoding="utf-8"):
                offenders.append(str(file))
    assert offenders == []
