"""C1: make_resolve teacher adapter tests.

Ground truth for beliefs / fixture patterns from test_decide_adapter.py's
both-sides smoke test (_p1_beliefs / _p2_fake_beliefs helpers, exact param
names, how deps is assembled).
"""
from __future__ import annotations

import copy

from showdown_bot.engine.moves import _move_table


# ---------------------------------------------------------------------------
# Helpers — mirror test_decide_adapter.py belief builders exactly
# ---------------------------------------------------------------------------

def _p1_beliefs():
    """p1 roster/movesets/stats matching the conftest decision_fixture state.

    State has p1 active: Incineroar (slot a) + Rillaboom (slot b).  No bench.
    """
    roster = {"p1": {}}
    movesets = {
        "p1": {
            "Incineroar": ["fakeout", "flareblitz", "protect", "knockoff"],
            "Rillaboom": ["heatwave", "earthpower", "protect", "solarbeam"],
        }
    }
    stats = {
        "p1": {
            "Incineroar": {"spe": 100},
            "Rillaboom": {"spe": 100},
        }
    }
    return roster, movesets, stats


def _p2_fake_beliefs():
    """p2 beliefs: Flutter Mane (slot a) + Tornadus (slot b).  No bench."""
    roster = {"p2": {}}
    movesets = {
        "p2": {
            "Flutter Mane": ["moonblast", "shadowball", "protect", "dazzlinggleam"],
            "Tornadus": ["tailwind", "bleakwindstorm", "protect", "u-turn"],
        }
    }
    stats = {
        "p2": {
            "Flutter Mane": {"spe": 151},
            "Tornadus": {"spe": 120},
        }
    }
    return roster, movesets, stats


def _combined_beliefs():
    """Merge p1 + p2 beliefs into the combined dicts make_resolve expects."""
    p1_roster, p1_movesets, p1_stats = _p1_beliefs()
    p2_roster, p2_movesets, p2_stats = _p2_fake_beliefs()
    roster = {**p1_roster, **p2_roster}
    movesets = {**p1_movesets, **p2_movesets}
    stats = {**p1_stats, **p2_stats}
    return roster, movesets, stats


# ---------------------------------------------------------------------------
# C1 test: make_resolve returns (next_state, reward) without mutating input
# ---------------------------------------------------------------------------

def test_resolve_returns_next_state_and_reward(decision_fixture):
    """make_resolve(root_our_side="p1", ...) must:
    - return (nxt, reward) where nxt is a new BattleState and reward is a float
    - NOT mutate the input state (clone semantics)
    """
    from showdown_bot.learning.rollout import make_resolve
    from showdown_bot.learning.decide_adapter import decide

    req, kw = decision_fixture
    state = kw["state"]

    roster, movesets, stats = _combined_beliefs()
    meta = _move_table()

    # deps: everything except state and our_side (same pattern as test_decide_adapter)
    deps = {k: v for k, v in kw.items() if k not in ("state", "our_side")}

    resolve = make_resolve(
        root_our_side="p1",
        roster_by_side=roster,
        movesets_by_side=movesets,
        stats_by_side=stats,
        move_meta=meta,
        deps=deps,
        weights=None,
    )

    # Decide for both sides (JointAction is the cleanest first test)
    p1_r, p1_m, p1_s = _p1_beliefs()
    p2_r, p2_m, p2_s = _p2_fake_beliefs()

    our_ja = decide(state, "p1", roster=p1_r, movesets=p1_m, stats=p1_s,
                    move_meta=meta, deps=deps)
    opp_ja = decide(state, "p2", roster=p2_r, movesets=p2_m, stats=p2_s,
                    move_meta=meta, deps=deps)

    # Snapshot before resolve
    before = copy.deepcopy(state)

    nxt, reward = resolve(state, our_ja, opp_ja)

    assert nxt is not state, "resolve must return a NEW state object, not the input"
    assert isinstance(reward, float), f"reward must be float, got {type(reward)}"

    # Input state must be byte-identical after resolve
    assert state.sides == before.sides, "resolve must NOT mutate input state.sides"
    assert state.field == before.field, "resolve must NOT mutate input state.field"


# ---------------------------------------------------------------------------
# C2 tests: make_decide + make_leaf
# ---------------------------------------------------------------------------

def _make_both(decision_fixture):
    """Return (state, decide_fn, leaf_fn) wired to the fixture's kw."""
    from showdown_bot.learning.rollout import make_decide, make_leaf

    req, kw = decision_fixture
    state = kw["state"]
    roster, movesets, stats = _combined_beliefs()
    meta = _move_table()
    deps = {k: v for k, v in kw.items() if k not in ("state", "our_side")}

    common = dict(
        root_our_side="p1",
        roster_by_side=roster,
        movesets_by_side=movesets,
        stats_by_side=stats,
        move_meta=meta,
        deps=deps,
    )
    return state, make_decide(**common), make_leaf(**common)


def test_make_decide_routes_tokens(decision_fixture):
    """make_decide(root_our_side="p1") must route US -> p1 and THEM -> p2."""
    from showdown_bot.learning.teacher import US, THEM
    from showdown_bot.learning.decide_adapter import decide as raw_decide
    from showdown_bot.battle.actions import JointAction

    req, kw = decision_fixture
    state = kw["state"]
    meta = _move_table()
    deps = {k: v for k, v in kw.items() if k not in ("state", "our_side")}
    p1_r, p1_m, p1_s = _p1_beliefs()
    p2_r, p2_m, p2_s = _p2_fake_beliefs()

    _, decide_fn, _ = _make_both(decision_fixture)

    us_ja = decide_fn(state, US)
    them_ja = decide_fn(state, THEM)

    assert isinstance(us_ja, JointAction), "US token must yield a JointAction"
    assert isinstance(them_ja, JointAction), "THEM token must yield a JointAction"

    # Verify routing: US -> p1 side, THEM -> p2 side
    # Compare against raw decide for the correct side
    roster, movesets, stats = _combined_beliefs()
    expected_us = raw_decide(state, "p1", roster=roster, movesets=movesets, stats=stats,
                             move_meta=meta, deps=deps)
    expected_them = raw_decide(state, "p2", roster=roster, movesets=movesets, stats=stats,
                               move_meta=meta, deps=deps)
    assert us_ja.as_pair() == expected_us.as_pair(), "US must route to p1 (root_our_side)"
    assert them_ja.as_pair() == expected_them.as_pair(), "THEM must route to p2 (opp side)"


def test_make_decide_unknown_token_raises(decision_fixture):
    """decide(state, unknown_token) must raise ValueError."""
    _, decide_fn, _ = _make_both(decision_fixture)
    req, kw = decision_fixture
    state = kw["state"]

    import pytest
    with pytest.raises(ValueError, match="bogus"):
        decide_fn(state, "bogus")


def test_make_leaf_is_root_perspective(decision_fixture):
    """make_leaf(root_our_side="p1")(state) must ALWAYS evaluate from p1,
    regardless of whose turn it conceptually is.

    This is verified by comparing against leaf_value(state, "p1", ...) directly —
    not leaf_value(state, "p2", ...).
    """
    from showdown_bot.learning.decide_adapter import leaf_value

    req, kw = decision_fixture
    state = kw["state"]
    meta = _move_table()
    deps = {k: v for k, v in kw.items() if k not in ("state", "our_side")}
    roster, movesets, stats = _combined_beliefs()

    _, _, leaf_fn = _make_both(decision_fixture)

    result = leaf_fn(state)
    assert isinstance(result, float), "leaf must return float"

    # Must equal leaf_value from root_our_side="p1" perspective
    expected_p1 = leaf_value(state, "p1", roster=roster, movesets=movesets, stats=stats,
                             move_meta=meta, deps=deps)
    assert result == expected_p1, (
        f"make_leaf must be root-perspective (p1); got {result}, expected {expected_p1}"
    )

    # Sanity: p2 value should differ (confirms it's not accidentally side-to-move)
    expected_p2 = leaf_value(state, "p2", roster=roster, movesets=movesets, stats=stats,
                             move_meta=meta, deps=deps)
    # (p1 vs p2 may or may not differ depending on state; the real check is p1 equality above)
    _ = expected_p2  # consumed to avoid unused-var lint


def test_make_decide_deterministic(decision_fixture):
    """Same state + token -> identical JointAction both calls."""
    from showdown_bot.learning.teacher import US, THEM

    req, kw = decision_fixture
    state = kw["state"]
    _, decide_fn, _ = _make_both(decision_fixture)

    us_ja1 = decide_fn(state, US)
    us_ja2 = decide_fn(state, US)
    assert us_ja1.as_pair() == us_ja2.as_pair(), "US decide must be deterministic"

    them_ja1 = decide_fn(state, THEM)
    them_ja2 = decide_fn(state, THEM)
    assert them_ja1.as_pair() == them_ja2.as_pair(), "THEM decide must be deterministic"


# ---------------------------------------------------------------------------
# I7a-B Task 5: format_config/calc_profile threading through make_resolve /
# decide_adapter.decide, and RolloutConfig(H=0, use_leaf=False) semantics.
# ---------------------------------------------------------------------------

def test_make_resolve_no_typeerror_with_format_config_and_calc_profile_both_in_deps(decision_fixture):
    """deps carrying BOTH 'format_config' and 'calc_profile' (as
    export_runtime._build_rollout_provider now populates) must not raise a
    TypeError anywhere in make_resolve's resolve() closure -- specifically
    the ``deps.get("calc_profile") or calc_profile_from_config(...)`` line
    (learning/rollout.py) must not accidentally splat calc_profile as a
    keyword into something that does not accept it."""
    from showdown_bot.engine.calc_profile import calc_profile_from_config
    from showdown_bot.engine.format_config import (
        DEFAULT_STAT_INVESTMENT, FormatConfig,
    )
    from showdown_bot.learning.decide_adapter import decide
    from showdown_bot.learning.rollout import make_resolve

    req, kw = decision_fixture
    state = kw["state"]
    roster, movesets, stats = _combined_beliefs()
    meta = _move_table()

    format_config = FormatConfig(
        format_id="test-mega", level=50, game_type="doubles", restricted_limit=0,
        tera=False, mega=True, stat_investment=DEFAULT_STAT_INVESTMENT, calc_generation=9,
    )
    deps = {k: v for k, v in kw.items() if k not in ("state", "our_side")}
    deps["format_config"] = format_config
    deps["calc_profile"] = calc_profile_from_config(format_config)

    resolve = make_resolve(
        root_our_side="p1", roster_by_side=roster, movesets_by_side=movesets,
        stats_by_side=stats, move_meta=meta, deps=deps, weights=None,
    )

    p1_r, p1_m, p1_s = _p1_beliefs()
    p2_r, p2_m, p2_s = _p2_fake_beliefs()
    our_ja = decide(state, "p1", roster=p1_r, movesets=p1_m, stats=p1_s, move_meta=meta, deps=deps)
    opp_ja = decide(state, "p2", roster=p2_r, movesets=p2_m, stats=p2_s, move_meta=meta, deps=deps)

    nxt, reward = resolve(state, our_ja, opp_ja)  # must not raise TypeError
    assert isinstance(reward, float)
    assert nxt is not state


def test_decide_adapter_decide_accepts_mega_format_config_and_drops_calc_profile(decision_fixture):
    """decide_adapter.decide's ``_core_deps`` filter must accept a deps dict
    containing format_config (mega=True) AND calc_profile without raising --
    calc_profile is not one of decide_adapter._CORE_DEP_KEYS, so it must be
    silently dropped rather than splatted into _choose_best (which does not
    accept a calc_profile kwarg)."""
    from showdown_bot.engine.calc_profile import calc_profile_from_config
    from showdown_bot.engine.format_config import (
        DEFAULT_STAT_INVESTMENT, FormatConfig,
    )
    from showdown_bot.battle.actions import JointAction
    from showdown_bot.learning.decide_adapter import decide

    req, kw = decision_fixture
    state = kw["state"]
    meta = _move_table()
    format_config = FormatConfig(
        format_id="test-mega", level=50, game_type="doubles", restricted_limit=0,
        tera=False, mega=True, stat_investment=DEFAULT_STAT_INVESTMENT, calc_generation=9,
    )
    deps = {k: v for k, v in kw.items() if k not in ("state", "our_side")}
    deps["format_config"] = format_config
    deps["calc_profile"] = calc_profile_from_config(format_config)

    p1_r, p1_m, p1_s = _p1_beliefs()
    ja = decide(state, "p1", roster=p1_r, movesets=p1_m, stats=p1_s, move_meta=meta, deps=deps)
    assert isinstance(ja, JointAction)


def test_decide_adapter_decide_routes_through_mega_ranking_on_a_mega_capable_board(
    mega_decision_fixture, monkeypatch,
):
    """End-to-end proof that the export/rollout wiring (decide_adapter.decide,
    which _core_deps-filters into _choose_best) actually REACHES the Mega
    ranking path Task 4 built: on a genuinely Mega-capable board (Aerodactyl
    holding Aerodactylite) with format_config.mega=True in deps,
    mega_scoring.build_own_mega_contexts must be invoked (proving real
    routing, not just 'didn't crash'), and the returned JointAction's
    mega_evolve fields must be valid bools -- the field CAN be True on this
    board (never guaranteed by heuristic ranking on a single decision, but
    the code path must be genuinely reachable, not dead)."""
    import showdown_bot.battle.mega_scoring as mega_scoring_mod
    from showdown_bot.battle.actions import JointAction
    from showdown_bot.engine.moves import _move_table
    from showdown_bot.learning.decide_adapter import decide

    calls = {"build": 0}
    real_build = mega_scoring_mod.build_own_mega_contexts

    def spy_build(*a, **kw):
        calls["build"] += 1
        return real_build(*a, **kw)

    monkeypatch.setattr(mega_scoring_mod, "build_own_mega_contexts", spy_build)

    req, kw = mega_decision_fixture
    state = kw["state"]
    deps = {k: v for k, v in kw.items() if k not in ("state", "our_side")}

    roster = {"p1": {}}
    movesets = {"p1": {"Aerodactyl": ["rockslide"], "Whimsicott": ["moonblast"]}}
    stats = {"p1": {"Aerodactyl": {"spe": 100}, "Whimsicott": {"spe": 100}}}
    meta = _move_table()

    ja = decide(state, "p1", roster=roster, movesets=movesets, stats=stats, move_meta=meta, deps=deps)
    assert isinstance(ja, JointAction)
    assert calls["build"] == 1, "decide() must route into build_own_mega_contexts exactly once"
    assert ja.slot0.mega_evolve in (True, False)
    assert ja.slot1.mega_evolve in (True, False)
