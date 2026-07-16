"""I7b-B pre-flight caller gate — five counterexample tests, ADDITIVE to the
approved plan (user directive, landed immediately before Task 4's scoring work).

These pin the *caller-side* gate in ``decision.py``, which is a different contract
from the plan's own ``test_no_eligibility_is_byte_identical_to_pre_i7b_scoring``
(that one pins ``score_evaluated_variants``'s numeric parity given the kwargs;
these pin whether the two entry points are *invoked at all*).

Why this matters: ``battle.opponent.foe_mega_eligibility()`` takes no
``format_config`` parameter -- it gates only on ``side_mega_spent`` and item
resolution. So the Reg-I / ``format_config=None`` guarantee rests entirely on the
CALLER choosing not to call it. And ``opp_mega_click_rate()`` defaults to 0.35
when the env is unset (it is fail-closed against *invalid* values, not "off"), so
"inert by default" is a property of the wiring, not of the env default. Both facts
are load-bearing and neither is self-evident from the functions themselves.

Honest RED/GREEN status (do not relabel):
  * test 1 + test 2 are BASELINE/INVARIANT tests -- green on f50c7af because no
    caller invokes either entry point yet. Their job is to STAY green through
    Task 4. They are not RED->GREEN and must not be reported as such.
  * tests 3, 4, 5 are genuinely RED against the real missing wiring before
    Task 4 Step 4 exists; each records its actual failure mode below.
"""
from __future__ import annotations

import importlib

import pytest

from showdown_bot.battle.decision import _choose_best
from showdown_bot.engine.belief.hypotheses import SpeciesSpreads, SpreadBook, SpreadPreset
from showdown_bot.engine.format_config import load_format_config
from showdown_bot.engine.state import BattleState, PokemonState
from showdown_bot.models.request import BattleRequest


def _explode(name: str):
    """Exploding monkeypatch: any invocation on an inactive path fails loudly and
    immediately, rather than passing silently (user directive)."""

    def _boom(*args, **kwargs):
        raise AssertionError(
            f"{name}() was invoked on a path where it must never run "
            f"(args={args!r} kwargs={kwargs!r})"
        )

    return _boom


def _spy(monkeypatch, name: str) -> list:
    """Wrap the REAL battle.opponent.<name>, recording each call's result.
    Both call sites import it function-locally, so patching the module attribute
    is observed at call time."""
    mod = importlib.import_module("showdown_bot.battle.opponent")
    real = getattr(mod, name)
    calls: list = []

    def _wrapped(*args, **kwargs):
        out = real(*args, **kwargs)
        calls.append(out)
        return out

    monkeypatch.setattr(mod, name, _wrapped)
    return calls


def _gating_req() -> BattleRequest:
    from showdown_bot.engine.state import to_id

    def _move_slots(names):
        return [
            {"move": n, "id": to_id(n), "pp": 8, "maxpp": 8, "target": "normal", "disabled": False}
            for n in names
        ]

    a_moves, b_moves = ["Rock Slide"], ["Moonblast"]
    return BattleRequest.model_validate({
        "active": [
            {"moves": _move_slots(a_moves), "canMegaEvo": True},
            {"moves": _move_slots(b_moves), "canMegaEvo": False},
        ],
        "side": {
            "name": "Player1", "id": "p1",
            "pokemon": [
                {
                    "ident": "p1: Aerodactyl", "details": "Aerodactyl, L50", "condition": "100/100",
                    "active": True, "stats": {"atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100},
                    "moves": [to_id(n) for n in a_moves], "baseTypes": ["Rock", "Flying"],
                    "item": "Aerodactylite",
                },
                {
                    "ident": "p1: Whimsicott", "details": "Whimsicott, L50", "condition": "100/100",
                    "active": True, "stats": {"atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100},
                    "moves": [to_id(n) for n in b_moves], "baseTypes": ["Grass", "Fairy"],
                },
            ],
        },
        "rqid": 1,
    })


def _gating_state(*, foe_mega_capable: bool) -> BattleState:
    """p1.a is always a Mega-capable Aerodactyl. The foe is either an Incineroar
    (real foe_mega_eligibility -> {}) or a real Aerodactyl holding Aerodactylite
    with item_known=True (real foe_mega_eligibility -> {"a": Aerodactyl-Mega})."""
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(
        species="Aerodactyl", base_species_id="aerodactyl", item="Aerodactylite",
        types=["Rock", "Flying"], hp=100, max_hp=100,
    )
    st.sides["p1"]["b"] = PokemonState(
        species="Whimsicott", base_species_id="whimsicott",
        types=["Grass", "Fairy"], hp=100, max_hp=100,
    )
    if foe_mega_capable:
        st.sides["p2"]["a"] = PokemonState(
            species="Aerodactyl", base_species_id="aerodactyl", item="Aerodactylite",
            item_known=True, types=["Rock", "Flying"], hp=100, max_hp=100,
        )
    else:
        st.sides["p2"]["a"] = PokemonState(
            species="Incineroar", base_species_id="incineroar",
            types=["Fire", "Dark"], hp=100, max_hp=100,
        )
    return st


@pytest.fixture
def gating_env():
    """Real SpeedOracle/calc_profile/DamageOracle -- never a stub. Self-contained
    (tests/i7b/ is a sibling of tests/i7a/ and tests/ is not a package, so neither
    i7a's fixtures nor tests/conftest.py's module-level helpers are importable)."""
    from showdown_bot.battle.oracle import DamageOracle
    from showdown_bot.engine.calc.client import SubprocessCalcBackend
    from showdown_bot.engine.calc_profile import calc_profile_from_config
    from showdown_bot.engine.speed import SpeedOracle

    champions = load_format_config("gen9championsvgc2026regma")
    calc_profile = calc_profile_from_config(champions)
    speed_oracle = SpeedOracle(stats_backend=SubprocessCalcBackend(), profile=calc_profile)
    spreads = SpeciesSpreads(
        offense=SpreadPreset(nature="Jolly", evs={"atk": 32, "spe": 32, "hp": 2}),
        defense=SpreadPreset(nature="Impish", evs={"hp": 32, "def": 32, "spd": 2}),
    )
    oracle = DamageOracle()
    return {
        "req": _gating_req(),
        "champions": champions,
        "regi": load_format_config("gen9vgc2025regi"),
        "speed_oracle": speed_oracle,
        "oracle": oracle,
        "calc": oracle.client,
        "book": SpreadBook(default=spreads),
        "our_spreads": {"aerodactyl": spreads, "whimsicott": spreads, "incineroar": spreads},
    }


def _run(env, state, format_config):
    return _choose_best(
        env["req"], state=state, book=env["book"], our_side="p1", calc=env["calc"],
        oracle=env["oracle"], speed_oracle=env["speed_oracle"], dex=None,
        our_spreads=env["our_spreads"], format_config=format_config, risk_lambda=0.0,
    )


# --- 1 + 2: BASELINE/INVARIANT (green on f50c7af; must stay green after Task 4) --


def test_format_config_none_never_touches_either_entry_point(gating_env, monkeypatch):
    """[BASELINE/INVARIANT -- not RED->GREEN] format_config=None must never call
    foe_mega_eligibility() or opp_mega_click_rate(), and must still return a
    legacy result. Exploding patches, so an accidental invocation fails at once.

    Green on f50c7af because nothing calls either yet; the point is that Task 4's
    `if format_config is not None and format_config.mega` gate keeps it green."""
    monkeypatch.setattr("showdown_bot.battle.opponent.foe_mega_eligibility", _explode("foe_mega_eligibility"))
    monkeypatch.setattr("showdown_bot.battle.opponent.opp_mega_click_rate", _explode("opp_mega_click_rate"))

    ja, val = _run(gating_env, _gating_state(foe_mega_capable=True), None)
    assert ja is not None
    assert isinstance(val, float)


def test_reg_i_mega_false_never_touches_either_entry_point(gating_env, monkeypatch):
    """[BASELINE/INVARIANT -- not RED->GREEN] Reg-I (real gen9vgc2025regi,
    mega=False) must never call either entry point. This is the load-bearing
    guard for the plan's I7b-B stop gate (a) "format_config=None/Reg-I callers
    remain byte-identical": foe_mega_eligibility() has no format_config parameter
    of its own, so ONLY the caller's gate protects Reg-I.

    Note the foe here is deliberately Mega-CAPABLE: if the gate were keyed on the
    board instead of on format_config, this would fire."""
    assert gating_env["regi"].mega is False  # pin the premise, don't assume it
    monkeypatch.setattr("showdown_bot.battle.opponent.foe_mega_eligibility", _explode("foe_mega_eligibility"))
    monkeypatch.setattr("showdown_bot.battle.opponent.opp_mega_click_rate", _explode("opp_mega_click_rate"))

    ja, val = _run(gating_env, _gating_state(foe_mega_capable=True), gating_env["regi"])
    assert ja is not None
    assert isinstance(val, float)


# --- 3 + 4 + 5: RED against the real missing wiring before Task 4 Step 4 --------


def test_champions_mega_true_does_call_eligibility(gating_env):
    """[RED before Task 4] Champions (mega=True) MUST call foe_mega_eligibility().
    The positive counterpart to tests 1-2: without it, the gate could be a dead
    branch that never activates and tests 1-2 would pass vacuously forever.

    Actual RED failure mode on f50c7af: `assert calls` -> AssertionError (empty),
    because no Decision/Scoring/Search caller passes the new kwargs yet."""
    assert gating_env["champions"].mega is True
    with pytest.MonkeyPatch.context() as mp:
        calls = _spy(mp, "foe_mega_eligibility")
        _run(gating_env, _gating_state(foe_mega_capable=True), gating_env["champions"])
    assert calls, "foe_mega_eligibility() was never called on the Champions path"


def test_click_rate_is_read_only_when_eligibility_is_non_empty(gating_env):
    """[RED before Task 4] opp_mega_click_rate() must be read ONLY when eligibility
    is non-empty. Both halves:
      (a) Mega-capable foe   -> eligibility non-empty -> click rate IS read.
      (b) Non-Mega foe       -> eligibility empty     -> click rate NEVER read
          (exploding patch). This half also pins that the 0.35 env default cannot
          activate anything on its own.

    Actual RED failure mode on f50c7af: half (a)'s `assert elig_calls` ->
    AssertionError (empty) -- eligibility is never called, so the click-rate
    question is not even reached yet. Half (b) already holds.
    """
    # (a) non-empty eligibility -> click rate read
    with pytest.MonkeyPatch.context() as mp:
        elig_calls = _spy(mp, "foe_mega_eligibility")
        rate_calls = _spy(mp, "opp_mega_click_rate")
        _run(gating_env, _gating_state(foe_mega_capable=True), gating_env["champions"])
    assert elig_calls, "foe_mega_eligibility() must be called on the Champions path"
    assert elig_calls[0], "premise: this board must yield a real foe-Mega hypothesis"
    assert rate_calls, "opp_mega_click_rate() must be read when eligibility is non-empty"

    # (b) empty eligibility -> click rate must never be read
    with pytest.MonkeyPatch.context() as mp:
        elig_calls_b = _spy(mp, "foe_mega_eligibility")
        mp.setattr("showdown_bot.battle.opponent.opp_mega_click_rate", _explode("opp_mega_click_rate"))
        _run(gating_env, _gating_state(foe_mega_capable=False), gating_env["champions"])
    assert elig_calls_b, "eligibility must still be consulted on the Champions path"
    assert all(e == {} for e in elig_calls_b), "premise: Incineroar foe must yield no hypothesis"


def test_champions_with_no_eligible_foe_mega_keeps_the_old_path(gating_env):
    """[RED before Task 4] Champions + no eligible foe Mega: the gate opens, finds
    nothing, and the decision must proceed exactly as before -- distinct from
    test 2, where the gate never opens at all.

    Actual RED failure mode on f50c7af: `assert elig_calls` -> AssertionError
    (empty) -- the gate does not exist, so it cannot "open and find nothing".
    """
    state = _gating_state(foe_mega_capable=False)
    baseline_ja, baseline_val = _run(gating_env, _gating_state(foe_mega_capable=False), gating_env["champions"])

    with pytest.MonkeyPatch.context() as mp:
        elig_calls = _spy(mp, "foe_mega_eligibility")
        mp.setattr("showdown_bot.battle.opponent.opp_mega_click_rate", _explode("opp_mega_click_rate"))
        ja, val = _run(gating_env, state, gating_env["champions"])

    assert elig_calls, "eligibility must be consulted before concluding there is no hypothesis"
    assert all(e == {} for e in elig_calls)
    # No hypothesis => the decision is unchanged vs the same board decided without
    # any foe-Mega machinery in play.
    assert ja == baseline_ja
    assert val == pytest.approx(baseline_val)
