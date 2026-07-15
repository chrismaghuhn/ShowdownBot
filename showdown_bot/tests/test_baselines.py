from __future__ import annotations

import json
import re
from pathlib import Path

from showdown_bot.battle.baselines import max_damage_choice
from showdown_bot.engine.belief.hypotheses import load_spread_book
from showdown_bot.engine.calc.models import DamageResult
from showdown_bot.engine.format_config import load_format_config
from showdown_bot.engine.state import BattleState, PokemonState, to_id
from showdown_bot.models.request import BattleRequest

FIXTURES = Path(__file__).parent / "fixtures"
CHOOSE_RE = re.compile(r"^/choose .+, .+\|\d+$")


def _book():
    cfg = load_format_config("gen9vgc2025regi")
    return load_spread_book(cfg.meta_path("default_spreads"))


def _req():
    return BattleRequest.model_validate(
        json.loads((FIXTURES / "request_doubles_moves.json").read_text())
    )


def _state():
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=150, max_hp=150)
    st.sides["p1"]["b"] = PokemonState(species="Rillaboom", hp=155, max_hp=155)
    st.sides["p2"]["a"] = PokemonState(species="Flutter Mane", hp=131, max_hp=131)
    st.sides["p2"]["b"] = PokemonState(species="Tornadus", hp=140, max_hp=140)
    return st


class FakeOracle:
    def __init__(self, frac):
        self.frac = frac

    def _res(self):
        return DamageResult(min_damage=int(self.frac * 100), max_damage=int(self.frac * 100), max_hp=100)

    def request(self, req):
        return id(req)

    def get(self, key):
        return self._res()

    def damage(self, req):
        return self._res()

    def flush(self):
        pass


def test_max_damage_returns_legal_choose():
    out = max_damage_choice(
        _req(), state=_state(), book=_book(), our_side="p1",
        oracle=FakeOracle(0.3), speed_oracle=None,
    )
    assert CHOOSE_RE.match(out), out


def test_max_damage_never_teras():
    out = max_damage_choice(
        _req(), state=_state(), book=_book(), our_side="p1",
        oracle=FakeOracle(0.3), speed_oracle=None,
    )
    assert "terastallize" not in out


def test_max_damage_prefers_attacks_over_passive():
    # With positive damage on every move, the chosen pair should be two moves
    # (max damage), not a switch/protect line.
    out = max_damage_choice(
        _req(), state=_state(), book=_book(), our_side="p1",
        oracle=FakeOracle(0.5), speed_oracle=None,
    )
    body = out[len("/choose "):].split("|")[0]
    left, right = body.split(", ")
    assert left.startswith("move")
    assert right.startswith("move")


# --- T3c: eval-deterministic fallback (live default unchanged) ---

def test_equal_damage_tie_is_deterministic():
    # FakeOracle(const) makes EVERY move deal equal damage -> a genuine tie across
    # many joint actions. The pick must be deterministic (enumeration-order tie-break).
    kw = dict(state=_state(), book=_book(), our_side="p1", oracle=FakeOracle(0.3), speed_oracle=None)
    a = max_damage_choice(_req(), **kw)
    b = max_damage_choice(_req(), **kw)
    assert a == b


def test_default_fallback_routes_through_pick_default_pair(monkeypatch):
    # T4b (docs/superpowers/plans/2026-07-10-2b35-T4b-forced-replacement-determinism.md):
    # fallback=None (live default) now routes the no-actions path through the
    # DETERMINISTIC pick_default_pair, not pick_random_pair -- superseding the T3c
    # "byte-for-byte" note this test previously pinned.
    from showdown_bot.battle.legal_actions import enumerate_slot_pairs
    monkeypatch.setattr("showdown_bot.battle.baselines.enumerate_my_actions", lambda req: [])
    seen = {}

    def fake_pdp(req):
        seen["called"] = True
        return enumerate_slot_pairs(req)[0]

    monkeypatch.setattr("showdown_bot.battle.baselines.pick_default_pair", fake_pdp)
    out = max_damage_choice(_req(), state=_state(), book=_book(), our_side="p1",
                            oracle=FakeOracle(0.3), speed_oracle=None)  # fallback default (None)
    assert seen.get("called") and out.startswith("/choose")


def test_injected_fallback_is_used_on_empty_actions(monkeypatch):
    monkeypatch.setattr("showdown_bot.battle.baselines.enumerate_my_actions", lambda req: [])
    req = _req()
    out = max_damage_choice(req, state=_state(), book=_book(), our_side="p1",
                            oracle=FakeOracle(0.3), speed_oracle=None,
                            fallback=lambda r: f"/choose default|{r.rqid}")
    assert out == f"/choose default|{req.rqid}"


# ---------------------------------------------------------------------------
# I7a-B Task 5: max_damage Mega integration.
#
# These tests use a REAL SpeedOracle/DamageOracle/CalcClient (mirrors
# tests/i7a/conftest.py's champions_cfg / calc_profile / aerodactyl_spreads
# pattern) because Mega projectability (mega_projection.project_mega) asserts
# speed_oracle.profile == calc_profile and calls speed_oracle.speed_for_species
# -- a hand-rolled fake would have to reimplement that surface exactly, so we
# reuse the real one the same way tests/i7a already does.
# ---------------------------------------------------------------------------


def _champions_cfg():
    return load_format_config("gen9championsvgc2026regma")


def _champions_calc_profile():
    from showdown_bot.engine.calc_profile import calc_profile_from_config

    return calc_profile_from_config(_champions_cfg())


def _champions_speed_oracle(calc_profile):
    from showdown_bot.engine.calc.client import SubprocessCalcBackend
    from showdown_bot.engine.speed import SpeedOracle

    return SpeedOracle(stats_backend=SubprocessCalcBackend(), profile=calc_profile)


def _aerodactyl_spreads():
    from showdown_bot.engine.belief.hypotheses import SpeciesSpreads, SpreadPreset

    return SpeciesSpreads(
        offense=SpreadPreset(nature="Jolly", evs={"atk": 32, "spe": 32, "hp": 2}),
        defense=SpreadPreset(nature="Impish", evs={"hp": 32, "def": 32, "spd": 2}),
    )


def _mega_req() -> BattleRequest:
    """Aerodactyl (can Mega, holding Aerodactylite) + Whimsicott vs a single
    opponent active mon (Incineroar) -- mirrors tests/i7a/test_i7a_decision.py's
    ``_build_req``/``_build_state`` helpers (no p2 'b' slot, so target resolution
    is unambiguous)."""
    a_moves = ["Rock Slide"]
    b_moves = ["Moonblast"]

    def _move_slots(names):
        return [
            {
                "move": name, "id": to_id(name), "pp": 8, "maxpp": 8,
                "target": "normal", "disabled": False,
            }
            for name in names
        ]

    return BattleRequest.model_validate({
        "active": [
            {"moves": _move_slots(a_moves), "canMegaEvo": True},
            {"moves": _move_slots(b_moves), "canMegaEvo": False},
        ],
        "side": {
            "name": "Player1",
            "id": "p1",
            "pokemon": [
                {
                    "ident": "p1: Aerodactyl",
                    "details": "Aerodactyl, L50",
                    "condition": "100/100",
                    "active": True,
                    "stats": {"atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100},
                    "moves": [to_id(n) for n in a_moves],
                    "baseTypes": ["Rock", "Flying"],
                    "item": "Aerodactylite",
                },
                {
                    "ident": "p1: Whimsicott",
                    "details": "Whimsicott, L50",
                    "condition": "100/100",
                    "active": True,
                    "stats": {"atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100},
                    "moves": [to_id(n) for n in b_moves],
                    "baseTypes": ["Grass", "Fairy"],
                },
            ],
        },
        "rqid": 1,
    })


def _mega_state(*, foe_moves: list[str] | None = None) -> BattleState:
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(
        species="Aerodactyl", base_species_id="aerodactyl", item="Aerodactylite",
        types=["Rock", "Flying"], hp=100, max_hp=100,
    )
    st.sides["p1"]["b"] = PokemonState(
        species="Whimsicott", base_species_id="whimsicott",
        types=["Grass", "Fairy"], hp=100, max_hp=100,
    )
    foe = PokemonState(
        species="Incineroar", base_species_id="incineroar",
        types=["Fire", "Dark"], hp=100, max_hp=100,
    )
    if foe_moves is not None:
        foe.move_names = set(foe_moves)
    st.sides["p2"]["a"] = foe
    return st


def _mega_kwargs():
    calc_profile = _champions_calc_profile()
    speed_oracle = _champions_speed_oracle(calc_profile)
    from showdown_bot.battle.oracle import DamageOracle
    from showdown_bot.engine.belief.hypotheses import SpreadBook

    spreads = _aerodactyl_spreads()
    book = SpreadBook(default=spreads)
    return dict(
        book=book,
        our_side="p1",
        oracle=DamageOracle(),
        speed_oracle=speed_oracle,
        format_config=_champions_cfg(),
    )


def test_max_damage_mega_same_action_despite_different_incoming_threats():
    """Two states share IDENTICAL outgoing calculations (our side + the
    opponent mon we attack are unchanged) but differ in the opponent's
    revealed moveset -- a proxy for wildly different incoming threat levels.
    ``move_names`` is only ever consulted by opponent-response modeling
    (battle/opponent.py), never by DamageModel.damage_fn, so a max_damage
    baseline that truly ignores incoming damage must pick the same action
    either way."""
    kwargs = _mega_kwargs()

    out_weak = max_damage_choice(
        _mega_req(), state=_mega_state(foe_moves=["Splash"]), **kwargs,
    )
    out_strong = max_damage_choice(
        _mega_req(),
        state=_mega_state(foe_moves=["Flare Blitz", "Knock Off", "Fake Out", "U-turn"]),
        **kwargs,
    )
    assert out_weak == out_strong


def test_max_damage_mega_never_calls_evaluate_line(monkeypatch):
    """max_damage stays a pure outgoing-damage baseline even in the Mega
    branch: it must never call battle.evaluate.evaluate_line (or a locally
    imported alias of it in baselines.py -- there isn't one today, but guard
    both symbols so a future import doesn't silently reintroduce incoming
    evaluation)."""
    def _boom(*a, **kw):
        raise AssertionError("max_damage_choice must never call evaluate_line")

    monkeypatch.setattr("showdown_bot.battle.evaluate.evaluate_line", _boom)
    if hasattr(__import__("showdown_bot.battle.baselines", fromlist=["*"]), "evaluate_line"):
        monkeypatch.setattr("showdown_bot.battle.baselines.evaluate_line", _boom)

    out = max_damage_choice(_mega_req(), state=_mega_state(), **_mega_kwargs())
    assert CHOOSE_RE.match(out), out


def test_max_damage_mega_single_expand_filter_context_pass_and_single_flush(monkeypatch):
    """The Mega branch must call mega_scoring.build_own_mega_contexts (the
    shared single expand+filter+context path) exactly once, and flush the
    shared oracle exactly once -- never a second expansion, never a
    per-context/per-candidate flush."""
    import showdown_bot.battle.mega_scoring as mega_scoring_mod

    calls = {"build": 0, "flush": 0}
    real_build = mega_scoring_mod.build_own_mega_contexts

    def spy_build(*a, **kw):
        calls["build"] += 1
        return real_build(*a, **kw)

    monkeypatch.setattr(mega_scoring_mod, "build_own_mega_contexts", spy_build)

    kwargs = _mega_kwargs()
    oracle = kwargs["oracle"]
    real_flush = oracle.flush

    def spy_flush():
        calls["flush"] += 1
        return real_flush()

    monkeypatch.setattr(oracle, "flush", spy_flush)

    out = max_damage_choice(_mega_req(), state=_mega_state(), **kwargs)
    assert CHOOSE_RE.match(out), out
    assert calls["build"] == 1, f"expected exactly 1 build_own_mega_contexts call, got {calls['build']}"
    assert calls["flush"] == 1, f"expected exactly 1 oracle.flush() call, got {calls['flush']}"


def test_max_damage_mega_never_teras():
    out = max_damage_choice(_mega_req(), state=_mega_state(), **_mega_kwargs())
    assert "terastallize" not in out


def test_max_damage_mega_returns_legal_choose():
    out = max_damage_choice(_mega_req(), state=_mega_state(), **_mega_kwargs())
    assert CHOOSE_RE.match(out), out


def test_max_damage_non_mega_path_unchanged_when_format_config_absent(monkeypatch):
    """format_config=None must still take the legacy (non-Mega) branch --
    i.e. NOT dispatch into build_own_mega_contexts at all."""
    import showdown_bot.battle.mega_scoring as mega_scoring_mod

    calls = {"build": 0}
    real_build = mega_scoring_mod.build_own_mega_contexts

    def spy_build(*a, **kw):
        calls["build"] += 1
        return real_build(*a, **kw)

    monkeypatch.setattr(mega_scoring_mod, "build_own_mega_contexts", spy_build)
    out = max_damage_choice(
        _req(), state=_state(), book=_book(), our_side="p1",
        oracle=FakeOracle(0.3), speed_oracle=None,
    )
    assert CHOOSE_RE.match(out), out
    assert calls["build"] == 0
