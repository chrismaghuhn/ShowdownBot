"""Fast-board Protect discipline (2026-07-11 plan Task 1): fast_board context +
env-gated ``fast_board_protect`` penalty, mirroring the existing ``endgame``
mechanism end-to-end (see docs/projects/core-bot/specs/2026-07-11-fast-board-protect-
discipline-design.md).
"""
from __future__ import annotations

from showdown_bot.battle.decision import (
    _choose_best,
    _fast_board_protect_weight,
    _is_fast_board,
)
from showdown_bot.engine.state import FieldState


# --- _is_fast_board: both-Tailwind True; one-side / none False -------------------------


def test_is_fast_board_true_when_both_sides_tailwind():
    f = FieldState(tailwind={"p1": True, "p2": True})
    assert _is_fast_board(f) is True


def test_is_fast_board_false_when_only_our_side_tailwind():
    f = FieldState(tailwind={"p1": True, "p2": False})
    assert _is_fast_board(f) is False


def test_is_fast_board_false_when_only_opp_side_tailwind():
    f = FieldState(tailwind={"p1": False, "p2": True})
    assert _is_fast_board(f) is False


def test_is_fast_board_false_when_neither_side_tailwind():
    assert _is_fast_board(FieldState()) is False  # default {"p1": False, "p2": False}


def test_is_fast_board_false_on_missing_tailwind_attr():
    """Robust to a field-like object with no tailwind dict at all."""
    class _NoTailwind:
        pass

    assert _is_fast_board(_NoTailwind()) is False


# --- byte-identical-off: env unset (weight 0.0) -> fast_board True/False identical -----


def test_byte_identical_off_fast_board_true_vs_false(decision_fixture, monkeypatch):
    """CRITICAL invariant: with SHOWDOWN_FAST_BOARD_PROTECT_PENALTY unset, the
    resulting fast_board_protect weight is 0.0, so a fixture decision's chosen
    action + score are identical whether fast_board evaluates True or False.

    Isolates the ``fast_board`` boolean itself (monkeypatching ``_is_fast_board``)
    rather than mutating ``state.field.tailwind`` directly: the pre-existing
    ``classify_game_mode`` ALSO reads ``field.tailwind`` (independent of this
    slice) to pick must_react/ahead/neutral, which would confound a tailwind-
    mutation test with an unrelated game-mode change. Patching ``_is_fast_board``
    isolates exactly the plumbing this task adds.
    """
    monkeypatch.delenv("SHOWDOWN_FAST_BOARD_PROTECT_PENALTY", raising=False)
    req, kw = decision_fixture

    import showdown_bot.battle.decision as decision_mod

    monkeypatch.setattr(decision_mod, "_is_fast_board", lambda field: False)
    ja_off, val_off = _choose_best(req, **kw)

    monkeypatch.setattr(decision_mod, "_is_fast_board", lambda field: True)
    ja_on, val_on = _choose_best(req, **kw)

    assert ja_off.as_pair() == ja_on.as_pair()
    assert val_off == val_on


def test_fast_board_computed_correctly_from_decision_state(decision_fixture, monkeypatch):
    """Sanity: the fixture's default field really is not a fast board, and
    setting both sides' Tailwind really does flip _is_fast_board -- otherwise the
    byte-identical test above would be vacuous."""
    monkeypatch.delenv("SHOWDOWN_FAST_BOARD_PROTECT_PENALTY", raising=False)
    req, kw = decision_fixture

    assert _is_fast_board(kw["state"].field) is False
    kw["state"].field.tailwind = {"p1": True, "p2": True}
    assert _is_fast_board(kw["state"].field) is True


# --- SHOWDOWN_FAST_BOARD_PROTECT_PENALTY env parsing ------------------------------------


def test_fast_board_protect_weight_defaults_to_zero_when_unset(monkeypatch):
    monkeypatch.delenv("SHOWDOWN_FAST_BOARD_PROTECT_PENALTY", raising=False)
    assert _fast_board_protect_weight() == 0.0


def test_fast_board_protect_weight_reads_env_float(monkeypatch):
    monkeypatch.setenv("SHOWDOWN_FAST_BOARD_PROTECT_PENALTY", "-2.5")
    assert _fast_board_protect_weight() == -2.5


def test_fast_board_protect_weight_falls_back_to_zero_on_bad_value(monkeypatch):
    monkeypatch.setenv("SHOWDOWN_FAST_BOARD_PROTECT_PENALTY", "not-a-float")
    assert _fast_board_protect_weight() == 0.0


def test_fast_board_protect_weight_independent_of_protect_penalty_gate(monkeypatch):
    """Default 0.0 keeps fast_board_protect OFF even when the historic
    SHOWDOWN_PROTECT_PENALTY gate is on (default) -- independently gated."""
    monkeypatch.delenv("SHOWDOWN_FAST_BOARD_PROTECT_PENALTY", raising=False)
    monkeypatch.delenv("SHOWDOWN_PROTECT_PENALTY", raising=False)
    assert _fast_board_protect_weight() == 0.0


def test_choose_best_builds_weights_with_fast_board_protect_from_env(decision_fixture, monkeypatch):
    """The weight the env produces actually reaches the EvalWeights instance
    _choose_best builds (plumbing check independent of whether this particular
    fixture's optimal candidate happens to involve Protect)."""
    monkeypatch.setenv("SHOWDOWN_FAST_BOARD_PROTECT_PENALTY", "-2.0")
    req, kw = decision_fixture

    import showdown_bot.battle.decision as decision_mod
    from showdown_bot.battle.evaluate import EvalWeights

    captured: list[EvalWeights] = []
    real_evaluate_line = decision_mod.evaluate_line

    def _spy(*args, **kwargs):
        if kwargs.get("weights") is not None:
            captured.append(kwargs["weights"])
        return real_evaluate_line(*args, **kwargs)

    monkeypatch.setattr(decision_mod, "evaluate_line", _spy)
    _choose_best(req, **kw)

    assert captured, "evaluate_line was never called with weights= (spy didn't fire)"
    assert all(w.fast_board_protect == -2.0 for w in captured)
