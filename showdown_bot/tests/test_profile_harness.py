"""I8-C Task C2 — the microprofile harness.

Design §2.5 (timer scopes), §2.8 (lifecycle + cache sampling at rep start), §2.4 (rows as
per-decision DELTAS of A's cumulative counters).

NOT A RUN. Every test here drives the harness over a fake scorer and writes only into
tmp_path. No server, no battle, no benchmark, no frozen evidence: this slice builds the
machine and proves it, it does not measure anything.

The three properties that are easy to get wrong, and are therefore tested first:

  * deltas, not totals -- the backends count cumulatively since construction (a backend has
    no concept of a "decision"), so a row's counters are after-minus-before around the
    measured call. Reading a cumulative counter straight onto a row would make rep 5 look
    five times more expensive than rep 1.
  * cache sizes sampled at REP START -- before context construction, not at timer start.
    Context construction legitimately warms _spe_cache before score_evaluated_variants is
    entered, so a timer-start sample would call every cold-cache arm warm (§2.8).
  * a failed rep keeps its real deltas -- the round trip happened and paid its latency.
"""

from __future__ import annotations

import json

import pytest

from showdown_bot.eval.decision_profile import (
    DecisionProfileError,
    validate_decision_profile_dataset,
)
from showdown_bot.eval.profile_harness import RepOutcome, run_arm
from showdown_bot.eval.profile_arms import ArmDecl

FORMAT = "gen9championsvgc2026regma"

_COLD = {
    "calc_backend": "per_rep",
    "damage_oracle": "per_rep",
    "speed_oracle": "per_rep",
    "species_dex": "per_rep",
    "contexts_and_variants": "per_rep",
}
_WARM = {**_COLD, "calc_backend": "per_arm", "damage_oracle": "per_arm",
         "speed_oracle": "per_arm", "species_dex": "per_arm"}


def _decl(**over):
    over.setdefault("reps", 2)
    reps = over.pop("reps")
    _decl.reps = reps
    d = dict(
        arm_id="A03_click_rate_default",
        design_arm="3",
        fixture="mega_decision_tie_fixture",
        env={"SHOWDOWN_OPP_MEGA_CLICK_RATE": "0.35"},
        scoring_params={"mode": "NEUTRAL"},
        lifecycle=_COLD,
        warmup=0,
    )
    d.update(over)
    return ArmDecl(**d)


class _FakeRep:
    """Stands in for one repetition's real work: counts up like the real backends do."""

    def __init__(self, *, fail_on=None):
        self.damage_batch_calls = 0
        self.planned = 0
        self.implicit = 0
        self.stats = 0
        self.types = 0
        self.attempts = 0
        self.spawn_count = 0
        self.caches = {"damage": 0, "speed": 0, "dex": 0}
        self._fail_on = fail_on
        self.rep = -1

    # -- the seams the harness reads --
    def counters(self):
        return {
            "damage_batch_calls": self.damage_batch_calls,
            "planned_damage_batches": self.planned,
            "implicit_damage_batches": self.implicit,
            "stats_batch_calls": self.stats,
            "types_batch_calls": self.types,
            "transport_attempts": self.attempts,
            "spawn_count": self.spawn_count,
            "requests_total": 0,
            "requests_unique": 0,
            "cache_hits": 0,
        }

    def cache_sizes(self):
        return dict(self.caches)

    def score(self):
        self.rep += 1
        # one damage batch + one spawn, exactly like a cold rep
        self.damage_batch_calls += 1
        self.planned += 1
        self.attempts += 1
        self.spawn_count += 1
        if self._fail_on is not None and self.rep == self._fail_on:
            raise RuntimeError("scorer blew up")
        return {"n_candidates": 12, "n_responses": 3, "n_mega_twins": 2,
                "n_branches": 2, "n_worlds": 1, "depth2_frontier": 0,
                "foe_mega_active": True}


def _run(decl, session, **kw):
    # a per_rep arm gets a fresh session per rep; a per_arm arm keeps this one
    kw.setdefault("timer_scope", "score_evaluated_variants")
    kw.setdefault("reps", getattr(_decl, "reps", 2))
    factory = session if callable(session) else (lambda: session)
    return run_arm(
        decl,
        factory,
        agent="heuristic",
        format_id=FORMAT,
        config_id="cfg",
        git_sha="a1bb619f52c635013782de6f12f06f29b43a4fa6",
        config_hash="0123456789abcdef",
        profile_manifest_hash="fedcba9876543210",
        **kw,
    )


# ==========================================================================
# rows are DELTAS of cumulative counters, never the totals
# ==========================================================================


def test_each_rep_reports_its_own_cost_not_the_running_total():
    """On a per_arm arm ONE session accumulates -- which is where a total could be mistaken
    for a delta. Its counter reaches 3; every row must still say 1."""
    session = _FakeRep()
    rows = _run(_decl(reps=3, lifecycle=_WARM), session)

    assert len(rows) == 3
    assert session.damage_batch_calls == 3
    assert [r["damage_batch_calls"] for r in rows] == [1, 1, 1]
    assert [r["spawn_calls"] for r in rows] == [1, 1, 1]


def test_a_per_rep_arm_gets_a_FRESH_session_every_repetition():
    """The lifecycle is real, not a label.

    Handed a FACTORY, a per_rep arm builds a new session per rep, so every rep starts with
    spawn_count_before == 0 -- which is precisely what the dataset tier's identity demands
    of a per_rep arm. The first cut of this harness reused one session regardless, and B3
    rejected its own output.
    """
    built = []

    def factory():
        s = _FakeRep()
        built.append(s)
        return s

    rows = _run(_decl(reps=3), factory)
    assert len(built) == 3
    assert [r["spawn_count_before"] for r in rows] == [0, 0, 0]


def test_a_per_arm_arm_reuses_one_session():
    built = []

    def factory():
        s = _FakeRep()
        built.append(s)
        return s

    rows = _run(_decl(reps=3, lifecycle=_WARM), factory)
    assert len(built) == 1
    assert [r["spawn_count_before"] for r in rows] == [0, 1, 2]


def test_spawn_count_before_is_the_cumulative_count_not_a_delta():
    """The one field that IS cumulative: the backend's count BEFORE this decision.

    It starts at 1, not 0, and that is the point: warmup=1 ran one repetition before rep 0,
    so a per_arm arm's first TIMED rep already carries a spawn. B3's identity requires
    exactly this -- a warmed per_arm arm whose rep 0 reported spawn_count_before == 0 would
    be contradicting its own warmup declaration.
    """
    session = _FakeRep()
    rows = _run(_decl(reps=3, lifecycle=_WARM, warmup=1), session)
    assert [r["spawn_count_before"] for r in rows] == [1, 2, 3]


def test_the_row_arithmetic_holds_on_every_rep():
    rows = _run(_decl(reps=3), _FakeRep())
    for r in rows:
        assert r["damage_batch_calls"] == r["planned_damage_batches"] + r["implicit_damage_batches"]
        assert r["transport_calls"] == (
            r["damage_batch_calls"] + r["stats_batch_calls"] + r["types_batch_calls"]
        )
        assert r["transport_attempts"] >= r["transport_calls"]


# ==========================================================================
# cache sizes at REP START -- before context construction
# ==========================================================================


def test_cache_sizes_are_sampled_before_the_rep_runs():
    class _Warming(_FakeRep):
        def score(self):
            # context construction warms the caches BEFORE the timed call; a sample taken
            # at timer start would see these and call the rep warm.
            self.caches = {"damage": 9, "speed": 9, "dex": 9}
            return super().score()

    rows = _run(_decl(reps=1), _Warming)
    assert rows[0]["damage_cache_size_at_rep_start"] == 0
    assert rows[0]["cache_class"] == "cold"


def test_a_warm_arm_reports_growing_caches():
    class _Growing(_FakeRep):
        def score(self):
            out = super().score()
            self.caches = {k: v + 1 for k, v in self.caches.items()}
            return out

    # warmup=1 grew the caches once before rep 0, so the timed reps start at 1.
    rows = _run(_decl(reps=3, lifecycle=_WARM, warmup=1), _Growing())
    assert [r["damage_cache_size_at_rep_start"] for r in rows] == [1, 2, 3]
    assert all(r["cache_class"] == "warm" for r in rows)


# ==========================================================================
# outcome / crash semantics (§2.6)
# ==========================================================================


def test_a_failed_rep_emits_a_row_with_null_latency_and_real_counters():
    rows = _run(_decl(reps=3, lifecycle=_WARM), _FakeRep(fail_on=1))

    assert [r["outcome"] for r in rows] == ["ok", "crash", "ok"]
    assert rows[1]["measured_ms"] is None            # the crash handler is not decision work
    assert rows[1]["damage_batch_calls"] == 1        # but the round trip really happened
    assert rows[0]["measured_ms"] is not None


def test_an_ok_rep_carries_a_real_duration():
    rows = _run(_decl(reps=1), _FakeRep())
    assert isinstance(rows[0]["measured_ms"], float)
    assert rows[0]["measured_ms"] >= 0.0


# ==========================================================================
# identity, scope, warmup
# ==========================================================================


def test_reps_are_zero_based_and_contiguous():
    rows = _run(_decl(reps=4), _FakeRep())
    assert [r["rep"] for r in rows] == [0, 1, 2, 3]


def test_warmup_reps_emit_no_rows():
    # §2.8: warmup repetitions are untimed and emit NO profile rows.
    session = _FakeRep()
    rows = _run(_decl(reps=2, lifecycle=_WARM, warmup=3), session)
    assert len(rows) == 2
    assert session.rep == 4          # 3 warmup + 2 timed actually ran
    assert [r["rep"] for r in rows] == [0, 1]


def test_rows_are_microprofile_rows_with_no_live_identity():
    rows = _run(_decl(reps=1), _FakeRep())
    r = rows[0]
    assert r["source"] == "microprofile"
    assert r["arm_id"] == "A03_click_rate_default"
    assert r["battle_id"] is None and r["decision_index"] is None
    assert r["schedule_hash"] is None


@pytest.mark.parametrize("scope", ["contexts_and_score", "score_evaluated_variants"])
def test_the_timer_scope_is_recorded_verbatim(scope):
    rows = _run(_decl(reps=1), _FakeRep(), timer_scope=scope)
    assert rows[0]["timer_scope"] == scope


def test_a_live_timer_scope_is_refused():
    # agent_choose is live-only: a microprofile row at that scope is a category error.
    with pytest.raises(DecisionProfileError):
        _run(_decl(reps=1), _FakeRep(), timer_scope="agent_choose")


# ==========================================================================
# every row the harness emits passes the validators
# ==========================================================================


def test_the_harness_output_passes_the_dataset_validator(tmp_path):
    """End to end, into tmp only: matrix -> manifest -> harness rows -> B3.

    tmp_path, deliberately: this slice freezes no evidence.
    """
    from showdown_bot.eval.decision_profile import profile_manifest_hash
    from showdown_bot.eval.profile_manifest import build_profile_manifest
    from showdown_bot.eval.profile_arms import arm_specs, PROFILE_ARMS

    specs = arm_specs({a.fixture: "0123456789abcdef" for a in PROFILE_ARMS}, reps=3)
    manifest = build_profile_manifest(agent="heuristic", format_id=FORMAT, arms=specs)
    mhash = profile_manifest_hash(manifest)
    arm = next(a for a in PROFILE_ARMS if a.arm_id == "A03_click_rate_default")

    rows = run_arm(
        arm, _FakeRep,          # a FACTORY: A03 is per_rep, so each rep needs its own
        agent="heuristic", format_id=FORMAT, config_id="cfg",
        git_sha=manifest["git_sha"],
        config_hash=next(e for e in manifest["arms"] if e["arm_id"] == arm.arm_id)[
            "effective_config_hash"
        ],
        profile_manifest_hash=mhash,
        timer_scope="score_evaluated_variants",
        reps=3,
    )

    out = tmp_path / "profile.jsonl"
    with open(out, "a", encoding="utf-8", newline="") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n")

    report = validate_decision_profile_dataset(str(out), manifest)
    assert report["rows"] == len(rows)


def test_a_failed_warmup_aborts_the_arm_and_emits_no_rows():
    """Fail closed. A swallowed warmup failure is worse than no warmup at all.

    The point of warming is to GUARANTEE the state the timed reps then claim. A warmup that
    raised leaves every following row asserting a warm cache nobody established -- rows that
    look ordinary and are false. So the arm aborts and produces nothing.
    """
    class _WarmupDies(_FakeRep):
        def score(self):
            if self.rep < 0:          # the warmup rep, before any timed one
                self.rep += 1
                raise RuntimeError("node never came up")
            return super().score()

    with pytest.raises(DecisionProfileError, match="warmup"):
        _run(_decl(reps=3, lifecycle=_WARM, warmup=1), _WarmupDies())


def test_a_mixed_lifecycle_arm_is_refused():
    """One session covers the backend AND the three caches, so a mixed declaration cannot
    be represented -- it would be flattened to whichever branch the code took, and the arm
    would measure something other than what it declared.

    No runnable arm is mixed today (every one is fully per_rep), so this is not a live
    measurement error. Without the guard it would become one, quietly, the first time a
    warm arm was added.
    """
    mixed = {**_COLD, "damage_oracle": "per_arm", "speed_oracle": "per_arm",
             "species_dex": "per_arm"}
    with pytest.raises(DecisionProfileError, match="mixed lifecycle"):
        _run(_decl(reps=1, lifecycle=mixed), _FakeRep)


def test_contexts_and_variants_may_differ_from_the_session_objects():
    # §2.8's warm-cache configuration pairs a per_arm backend with per_rep contexts, so
    # contexts_and_variants is deliberately outside the guard.
    ok = {**_WARM, "contexts_and_variants": "per_rep"}
    _run(_decl(reps=1, lifecycle=ok), _FakeRep())


def test_RepOutcome_is_the_harnesss_only_verdict_vocabulary():
    assert set(RepOutcome) == {"ok", "crash"}
