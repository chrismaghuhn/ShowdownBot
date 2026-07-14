from __future__ import annotations

from showdown_bot.client.gauntlet import _load_belief_deps


def test_load_belief_deps_champions_returns_cfg_and_book():
    cfg, book, priors, opp_sets = _load_belief_deps("gen9championsvgc2026regma")
    assert cfg is not None
    assert cfg.format_id == "gen9championsvgc2026regma"
    assert cfg.tera is False
    assert cfg.mega is True
    assert cfg.stat_investment.kind == "stat_points"
    assert book is not None
    assert priors is not None
    assert isinstance(opp_sets, dict)
