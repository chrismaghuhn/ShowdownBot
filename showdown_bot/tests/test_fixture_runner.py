from pathlib import Path

from showdown_bot.client.fixture_runner import replay_request_fixture

FIXTURES = Path(__file__).parent / "fixtures"


def test_replay_fixture_returns_choose_with_move():
    result = replay_request_fixture(FIXTURES / "request_doubles_moves.json", seed=0)
    assert result.startswith("/choose")
    assert "move" in result
