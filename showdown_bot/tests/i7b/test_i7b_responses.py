"""I7b-A: click-rate parsing and (later in this file) response pipeline tests."""
from __future__ import annotations

import pytest

from showdown_bot.battle.opponent import InvalidOppMegaClickRateError, opp_mega_click_rate


@pytest.mark.parametrize("raw,expected", [("0.35", 0.35), ("0.0", 0.0), ("1.0", 1.0), ("0.2", 0.2), ("0.5", 0.5)])
def test_opp_mega_click_rate_accepts_valid_values(monkeypatch, raw, expected):
    monkeypatch.setenv("SHOWDOWN_OPP_MEGA_CLICK_RATE", raw)
    assert opp_mega_click_rate() == expected


def test_opp_mega_click_rate_defaults_to_0_35_when_unset(monkeypatch):
    monkeypatch.delenv("SHOWDOWN_OPP_MEGA_CLICK_RATE", raising=False)
    assert opp_mega_click_rate() == 0.35


@pytest.mark.parametrize("raw", ["-0.1", "1.1", "nan", "inf", "-inf", "abc", ""])
def test_opp_mega_click_rate_fails_closed_on_invalid_values(monkeypatch, raw):
    monkeypatch.setenv("SHOWDOWN_OPP_MEGA_CLICK_RATE", raw)
    with pytest.raises(InvalidOppMegaClickRateError):
        opp_mega_click_rate()
