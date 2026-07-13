"""Accuracy-mode wiring integration test (accuracy-slice Task 5 follow-up, requested in
code review of commit 9060b3c).

Task 5 threaded ``accuracy_mode``/``accuracy_branch_cap`` through all 8
``evaluate_line`` call sites inside ``_choose_best``/``_maybe_tera`` by manual code
reading. This test proves the wiring's *consistency* end-to-end: every call
``evaluate_line`` actually receives during one full live decision must carry the
resolved ``SHOWDOWN_ACCURACY_MODE`` value -- so a future call site that quietly drops
the kwarg (reverting to the always-hit default) fails a test, not just a code review.

``depth2_value``/``search.py`` is out of scope here (documented, separate follow-up
per spec Sec.12 -- see the comment above ``d2_eval_kwargs`` in ``decision.py``); the
default ``decision_fixture`` scenario runs at ``SHOWDOWN_SEARCH_DEPTH`` unset (=1) and
``SHOWDOWN_WORLD_SAMPLES`` unset (=1), so the depth-2 and K-world code paths (which
would reach into ``search.py``) are not exercised, matching that scope boundary.

Accuracy-slice Task 6 changed ``_breakdowns_for`` (the trace-population call site) to
call ``evaluate._evaluate_line_details`` directly instead of the public ``evaluate_line``
wrapper (so the breakdown and the accuracy telemetry come from the same evaluation call,
no duplicate resolve pass). ``evaluate_line`` itself is a thin wrapper that calls
``_evaluate_line_details`` internally and unpacks ``(d.score, d.representative_outcome)``
-- and it does so via a plain module-global name lookup inside ``evaluate.py``, resolved
at call time against ``evaluate.py``'s own namespace regardless of which module's variable
holds a reference to the ``evaluate_line`` function object. So patching
``evaluate_module._evaluate_line_details`` alone transparently intercepts BOTH every
``evaluate_line`` call site still in ``decision.py`` (their internal call bottoms out
there) AND ``_breakdowns_for``'s direct call (its function-local
``from showdown_bot.battle.evaluate import _evaluate_line_details`` re-resolves the name
against ``evaluate.py``'s namespace on every ``_choose_best`` invocation, picking up
whatever is currently patched there) -- one patch, one record per call, no double
counting, no need to separately patch ``decision_module.evaluate_line`` (which would
double-record: once explicitly, once again via the internal ``_evaluate_line_details``
call the original ``evaluate_line`` makes).
"""
from __future__ import annotations

from showdown_bot.battle import evaluate as evaluate_module
from showdown_bot.battle.decision import _choose_best
from showdown_bot.battle.decision_trace import DecisionTrace


def _install_recorder(monkeypatch):
    """Wrap (not replace) the real ``_evaluate_line_details`` so the decision pipeline
    runs exactly as it would live -- same scores feed pick_best/tera/report/trace --
    while recording the accuracy_mode/accuracy_branch_cap every call actually received.
    Patching this one function is sufficient to cover every ``evaluate_line`` call site
    in ``decision.py`` plus ``_breakdowns_for``'s direct call; see the module docstring
    for why."""
    calls: list[dict] = []
    real = evaluate_module._evaluate_line_details

    def _wrapped(*args, **kwargs):
        calls.append({
            "accuracy_mode": kwargs.get("accuracy_mode", False),
            "accuracy_branch_cap": kwargs.get("accuracy_branch_cap", 4),
        })
        return real(*args, **kwargs)

    monkeypatch.setattr(evaluate_module, "_evaluate_line_details", _wrapped)
    return calls


def test_accuracy_mode_on_reaches_every_evaluate_line_call(decision_fixture, monkeypatch):
    """SHOWDOWN_ACCURACY_MODE=1 -> every evaluate_line call made during one full
    _choose_best decision (score_plan, the report metrics line, _breakdowns_for,
    both _maybe_tera branches) carries accuracy_mode=True. report= and trace= are
    both passed so the report/trace-only call sites are exercised too, not just the
    primary scoring path."""
    calls = _install_recorder(monkeypatch)
    monkeypatch.setenv("SHOWDOWN_ACCURACY_MODE", "1")
    req, kw = decision_fixture

    _choose_best(req, report=[], trace=DecisionTrace(), **kw)

    assert len(calls) >= 4, (
        "too few evaluate_line calls recorded -- decision_fixture scenario didn't "
        f"exercise the pipeline as expected (got {len(calls)})"
    )
    assert all(c["accuracy_mode"] is True for c in calls), calls
    assert all(c["accuracy_branch_cap"] == 4 for c in calls), calls


def test_accuracy_mode_off_by_default_reaches_every_evaluate_line_call(decision_fixture, monkeypatch):
    """Mirror of the above with SHOWDOWN_ACCURACY_MODE unset: every recorded call
    carries accuracy_mode=False -- the off-by-default invariant, proven at the same
    granularity (every call site individually), not just the final chosen action."""
    calls = _install_recorder(monkeypatch)
    monkeypatch.delenv("SHOWDOWN_ACCURACY_MODE", raising=False)
    req, kw = decision_fixture

    _choose_best(req, report=[], trace=DecisionTrace(), **kw)

    assert len(calls) >= 4, (
        "too few evaluate_line calls recorded -- decision_fixture scenario didn't "
        f"exercise the pipeline as expected (got {len(calls)})"
    )
    assert all(c["accuracy_mode"] is False for c in calls), calls
