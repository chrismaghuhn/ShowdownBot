"""Decision-level regression guards for the 2c +Sampling K-world branch.

The K-world branch in ``battle/decision.py`` (``_choose_best``) had three
hot-path bugs found in review (fixed in abc3cc5). The sampler *unit* tests
(``test_world_sampler.py``) never exercise that branch, so without these guards
a regression of any of the three would stay green. Each test below pins one:

  Guard A  ``if world_dist:`` guard (fix #3) + byte-identical-off:
           K>=2 with no set-uncertainty (empty dist) routes to the single-world
           path -> choice identical to unset.
  Guard B  ``UnboundLocalError: opp_resps`` (fix #1) + per-world-vs-per-response
           weight-length (fix #2): force the branch to fire and assert it runs
           to completion with an aligned, genuinely-multiplied score vector.

Uses the same calc-stubbing fakes as ``test_decision_trace.py`` (no live
server, no Node calc subprocess).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from showdown_bot.battle.decision_trace import DecisionTrace
from showdown_bot.engine.belief.hypotheses import (
    SpreadPreset,
    SpeciesSpreads,
    load_spread_book,
)
from showdown_bot.engine.calc.models import DamageResult
from showdown_bot.engine.format_config import load_format_config
from showdown_bot.engine.speed import SpeedRange
from showdown_bot.engine.state import BattleState, PokemonState
from showdown_bot.models.request import BattleRequest

FIXTURES = Path(__file__).parent / "fixtures"


# --- calc-stubbing fakes (mirror test_decision_trace.py; no live server) ---


class _FakeCalc:
    """Returns non-KO damage (keeps game mode NEUTRAL)."""

    backend = None

    def damage_batch(self, requests):
        return [DamageResult(min_damage=20, max_damage=35, max_hp=150) for _ in requests]


class _FakeOracle:
    def request(self, req):
        return (req.attacker.species, req.move, req.defender.species)

    def get(self, key):
        return DamageResult(min_damage=45, max_damage=70, max_hp=150)

    def damage(self, req):
        return DamageResult(min_damage=45, max_damage=70, max_hp=150)

    def flush(self):
        pass


class _FakeSpeed:
    def our_speed(self, base, mon, field, side):
        return base or 100

    def opponent_range(self, mon, field, side, *, book):
        return SpeedRange(min=80, likely=110, max=150)

    def likely_speed(self, mon, field, side, preset, item_for_speed):
        # Reached only when opp_sets contains this mon (the curated-set / K-world
        # path). Returns the same point as opponent_range.likely for consistency.
        return 110


class _FakeDex:
    def types(self, species):
        return {"Flutter Mane": ["Ghost", "Fairy"], "Tornadus": ["Flying"]}.get(
            species, ["Normal"]
        )


def _book():
    cfg = load_format_config("gen9vgc2025regi")
    return load_spread_book(cfg.meta_path("default_spreads"))


def _req():
    data = json.loads((FIXTURES / "request_doubles_moves.json").read_text())
    return BattleRequest.model_validate(data)


def _state():
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=150, max_hp=150)
    st.sides["p1"]["b"] = PokemonState(species="Rillaboom", hp=155, max_hp=155)
    fm = PokemonState(species="Flutter Mane", hp=131, max_hp=131)
    fm.move_names = {"Moonblast", "Shadow Ball"}
    tor = PokemonState(species="Tornadus", hp=140, max_hp=140)
    tor.move_names = {"Tailwind", "Bleakwind Storm"}
    st.sides["p2"]["a"] = fm
    st.sides["p2"]["b"] = tor
    return st


def _fresh():
    """A fresh (req, kw) each call — the decision path enriches state in place,
    so parity comparisons build a new state per invocation."""
    kw = dict(
        state=_state(),
        book=_book(),
        our_side="p1",
        calc=_FakeCalc(),
        oracle=_FakeOracle(),
        speed_oracle=_FakeSpeed(),
        dex=_FakeDex(),
    )
    return _req(), kw


def _spreads(nature: str) -> SpeciesSpreads:
    p = SpreadPreset(nature=nature, evs={"hp": 4}, items=[])
    return SpeciesSpreads(offense=p, defense=p)


# ---------------------------------------------------------------------------
# Guard A — empty-dist / off-parity (pins the `if world_dist:` guard, fix #3)
# ---------------------------------------------------------------------------


def test_kworld_empty_dist_is_byte_identical_to_unset(monkeypatch):
    """K>=2 with no opponent-set uncertainty (fixture passes no opp_sets ->
    build_world_dist returns {}) must route to the single-world path, so the
    choice is identical to the toggle being unset. If a regression drops the
    `if world_dist:` guard, K>=2 would enter the K-world branch even with an
    empty dist and this parity could break."""
    from showdown_bot.battle.decision import heuristic_choose_for_request

    monkeypatch.delenv("SHOWDOWN_WORLD_SAMPLES", raising=False)
    req1, kw1 = _fresh()
    choice_unset = heuristic_choose_for_request(req1, **kw1)

    monkeypatch.setenv("SHOWDOWN_WORLD_SAMPLES", "2")
    req2, kw2 = _fresh()
    choice_k2 = heuristic_choose_for_request(req2, **kw2)

    assert choice_k2 == choice_unset


# ---------------------------------------------------------------------------
# Guard B — branch fires: completion + weight alignment + real multiplication
# (pins UnboundLocalError fix #1 and per-world-vs-per-response weights fix #2)
# ---------------------------------------------------------------------------


def test_kworld_branch_fires_weights_align_and_multiply(monkeypatch):
    """Force a 2-point opponent-set distribution so the K-world branch actually
    runs, then assert it (1) completes and returns a legal choice — the
    _maybe_tera/report/trace tail references opp_resps/model, so an
    UnboundLocalError regression crashes here; (2) yields a score vector whose
    length equals the response-weight vector — a per-world (instead of
    per-response) weight regression breaks this; (3) is strictly longer than
    the single-world vector — proves the worlds genuinely multiplied the eval
    (guards against a vacuous green where the branch silently collapses)."""
    import showdown_bot.battle.decision as decision
    from showdown_bot.battle.decision import heuristic_choose_for_request

    forced = {"fluttermane": [(_spreads("Timid"), 0.6), (_spreads("Modest"), 0.4)]}
    monkeypatch.setattr(decision, "build_world_dist", lambda *a, **k: forced)

    # Single-world baseline: K=1 never calls build_world_dist (monkeypatch moot).
    monkeypatch.setenv("SHOWDOWN_WORLD_SAMPLES", "1")
    req1, kw1 = _fresh()
    tr1 = DecisionTrace()
    heuristic_choose_for_request(req1, trace=tr1, **kw1)
    n_single = len(tr1.candidates[0].score_vector)

    # K=2: forced dist is non-empty -> K-world branch runs to completion.
    monkeypatch.setenv("SHOWDOWN_WORLD_SAMPLES", "2")
    req2, kw2 = _fresh()
    tr2 = DecisionTrace()
    choice = heuristic_choose_for_request(req2, trace=tr2, **kw2)

    assert choice is not None  # (1) ran through _maybe_tera/report/trace
    top = tr2.candidates[0]
    assert len(top.score_vector) == len(tr2.opponent_response_weights)  # (2)
    assert len(top.score_vector) > n_single  # (3) worlds genuinely multiplied
