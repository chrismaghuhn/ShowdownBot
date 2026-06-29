from pathlib import Path

from showdown_bot.team.pack import load_packed_team


def test_load_packed_team():
    root = Path(__file__).resolve().parents[1]
    packed = load_packed_team(root / "teams" / "fixed_team.txt")
    assert packed.startswith("Incineroar")
    assert "\n" not in packed
    assert packed.count("]") == 5
