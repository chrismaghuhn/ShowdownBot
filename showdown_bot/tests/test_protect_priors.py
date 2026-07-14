from __future__ import annotations

from showdown_bot.battle.opponent import predict_responses
from showdown_bot.engine.belief.protect_priors import (
    ProtectPriors,
    load_protect_priors,
)
from showdown_bot.engine.format_config import load_format_config
from showdown_bot.engine.state import BattleState, PokemonState


def test_load_protect_priors():
    cfg = load_format_config("gen9vgc2025regi")
    priors = load_protect_priors(cfg.meta_path("protect_priors"))
    assert 0.0 < priors.default < 1.0
    assert "Incineroar" in priors.species


def test_rate_threatened_bump_and_consecutive_penalty():
    p = ProtectPriors(default=0.2, threatened_bump=0.4, consecutive_penalty=0.5)
    assert abs(p.rate("X") - 0.2) < 1e-9
    assert abs(p.rate("X", threatened=True) - 0.6) < 1e-9
    assert abs(p.rate("X", consecutive=1) - 0.1) < 1e-9  # 0.2 * 0.5
    assert p.rate("X", threatened=True) <= 1.0


def test_predict_responses_weights_sum_to_one_with_priors():
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=100, max_hp=100)
    fm = PokemonState(species="Flutter Mane", hp=100, max_hp=100)
    fm.move_names = {"Moonblast", "Protect"}
    st.sides["p2"]["a"] = fm
    priors = ProtectPriors(default=0.2, threatened_bump=0.4, consecutive_penalty=0.5)
    resps = predict_responses(st, "p1", "p2", dex=None, priors=priors)
    total = sum(r.weight for r in resps)
    assert abs(total - 1.0) < 1e-9
    # protect read carries the configured prior weight after normalization
    protect = [r for r in resps if "protect" in r.label]
    assert protect and protect[0].weight > 0


def test_champions_protect_priors_load():
    cfg = load_format_config("gen9championsvgc2026regma")
    priors = load_protect_priors(cfg.meta_path("protect_priors"))
    assert priors.default == 0.18
    assert priors.species == {}
