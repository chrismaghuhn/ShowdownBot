from pathlib import Path


def test_generalisation_never_imports_live_client_or_subprocess():
    root = Path(__file__).parents[2] / "src/showdown_bot/analysis/generalisation"
    source = "\n".join(path.read_text(encoding="utf-8") for path in sorted(root.glob("*.py")))
    forbidden = ("showdown_bot.client", "websockets", "subprocess", "run_local_gauntlet",
                 "run_schedule")
    assert not any(token in source for token in forbidden)
