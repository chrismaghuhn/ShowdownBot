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
from dataclasses import replace

import pytest

from showdown_bot.eval import config_env
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
    """Stands in for one repetition's real work: counts up like the real backends do.

    The work is split across the two seams the harness drives, mirroring production:

      prepare() -- context construction. With ``prepare_work=True`` it does a stats_batch
                   that spawns and warms the speed cache, exactly as build_own_mega_contexts
                   does via speed_for_species on a shared backend (§2.8's call chain). This
                   is the work the narrow timer scope EXCLUDES and the wide one INCLUDES.
      score()   -- the scored call: one damage batch that spawns, like a cold decision.
    """

    def __init__(self, *, fail_on=None, prepare_fail_on=None, prepare_work=False):
        self.damage_batch_calls = 0
        self.planned = 0
        self.implicit = 0
        self.stats = 0
        self.types = 0
        self.mixed = 0
        self.attempts = 0
        self.spawn_count = 0
        self.caches = {"damage": 0, "speed": 0, "dex": 0}
        self._fail_on = fail_on
        self._prepare_fail_on = prepare_fail_on
        self._prepare_work = prepare_work
        self.rep = -1
        self.prepared = 0
        self.env_seen_inside = None   # os.environ snapshot the last score() observed

    # -- the seams the harness reads --
    def counters(self):
        return {
            "damage_batch_calls": self.damage_batch_calls,
            "planned_damage_batches": self.planned,
            "implicit_damage_batches": self.implicit,
            "stats_batch_calls": self.stats,
            "types_batch_calls": self.types,
            "mixed_batch_calls": self.mixed,
            "transport_attempts": self.attempts,
            "spawn_count": self.spawn_count,
            "requests_total": 0,
            "requests_unique": 0,
            "cache_hits": 0,
        }

    def cache_sizes(self):
        return dict(self.caches)

    def prepare(self):
        idx = self.prepared
        self.prepared += 1
        if self._prepare_work:
            # context construction on a shared backend: a stats_batch that spawns and warms
            # the speed cache. The narrow scope excludes this from the row; the wide one keeps it.
            self.stats += 1
            self.attempts += 1
            self.spawn_count += 1
            self.caches = {**self.caches, "speed": self.caches["speed"] + 1}
        if self._prepare_fail_on is not None and idx == self._prepare_fail_on:
            raise RuntimeError("context construction blew up")

    def score(self):
        import os
        self.env_seen_inside = {k: v for k, v in os.environ.items() if k.startswith("SHOWDOWN_")}
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


def _run(decl, session, *, timer_scope=None, behavior_env=None, **kw):
    # timer_scope now lives on the decl (the single source run_arm reads); a test that varies
    # it rebinds the frozen decl rather than passing a second truth to run_arm.
    if timer_scope is not None and timer_scope != decl.timer_scope:
        decl = replace(decl, timer_scope=timer_scope)
    # behavior_env is mandatory: default to the arm's own, which is what the manifest entry
    # would carry; the mismatch test overrides it with a wrong value.
    if behavior_env is None:
        behavior_env = config_env.behavior_env(dict(decl.env))
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
        behavior_env=behavior_env,
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
            r["damage_batch_calls"] + r["stats_batch_calls"]
            + r["types_batch_calls"] + r["mixed_batch_calls"]
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

    entry = next(e for e in manifest["arms"] if e["arm_id"] == arm.arm_id)
    rows = run_arm(
        arm, _FakeRep,          # a FACTORY: A03 is per_rep, so each rep needs its own
        agent="heuristic", format_id=FORMAT, config_id="cfg",
        git_sha=manifest["git_sha"],
        config_hash=entry["effective_config_hash"],
        profile_manifest_hash=mhash,
        reps=3,
        behavior_env=entry["behavior_env"],
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


# ==========================================================================
# C3: the prepare() seam -- context construction, and which timer scope contains it
# ==========================================================================
#
# §2.5/§2.8: build_own_mega_contexts runs BEFORE score_evaluated_variants and, on a shared
# backend, spawns and warms the speed cache while doing so. The narrow scope
# (score_evaluated_variants) must EXCLUDE that work; the wide scope (contexts_and_score)
# must INCLUDE it. The harness owns the ordering; the session only exposes prepare()/score().


def test_prepare_runs_once_per_timed_rep_and_per_warmup_rep():
    session = _FakeRep()
    _run(_decl(reps=3, lifecycle=_WARM, warmup=2), session)
    assert session.prepared == 5           # 2 warmup + 3 timed, each a prepare()


def test_narrow_scope_excludes_context_construction_from_the_row():
    """prepare() does a stats_batch that spawns; at score_evaluated_variants scope the row's
    counters are taken AFTER prepare, so none of that context-construction cost appears."""
    rows = _run(_decl(reps=1), _FakeRep(prepare_work=True),
                timer_scope="score_evaluated_variants")
    r = rows[0]
    assert r["stats_batch_calls"] == 0     # prepare's stats_batch is outside the window
    assert r["spawn_calls"] == 1           # only score()'s spawn
    assert r["damage_batch_calls"] == 1
    assert r["transport_attempts"] == 1


def test_wide_scope_includes_context_construction_in_the_row():
    """At contexts_and_score scope the counter snapshot is taken BEFORE prepare, so the
    stats_batch and the spawn it did are part of the measured decision."""
    rows = _run(_decl(reps=1), _FakeRep(prepare_work=True),
                timer_scope="contexts_and_score")
    r = rows[0]
    assert r["stats_batch_calls"] == 1     # prepare's stats_batch is inside the window
    assert r["spawn_calls"] == 2           # prepare's spawn + score()'s spawn
    assert r["transport_calls"] == 2       # damage(1) + stats(1)
    assert r["transport_attempts"] == 2


def test_cache_sizes_are_sampled_before_prepare_even_when_prepare_warms_them():
    """§2.8's sampling point: rep start, BEFORE prepare. prepare() warms the speed cache, but
    a cold arm's row must still read 0 -- otherwise every cold arm on a shared backend would
    be mislabelled warm."""
    for scope in ("score_evaluated_variants", "contexts_and_score"):
        rows = _run(_decl(reps=1), _FakeRep(prepare_work=True), timer_scope=scope)
        assert rows[0]["speed_cache_size_at_rep_start"] == 0, scope
        assert rows[0]["cache_class"] == "cold", scope


def test_spawn_count_before_is_sampled_at_rep_start_not_after_prepare():
    """The crux that keeps the per_rep dataset identity sound. A cold arm's prepare() spawns
    the shared backend, but spawn_count_before is sampled at REP START -- so it is 0, exactly
    what the dataset tier demands of a per_rep arm. Sampling it after prepare would read 1 and
    make every cold arm fail its own lifecycle check."""
    rows = _run(_decl(reps=1), _FakeRep(prepare_work=True),
                timer_scope="contexts_and_score")
    assert rows[0]["spawn_count_before"] == 0


def test_a_failed_narrow_prepare_aborts_the_arm_fail_closed():
    """A narrow-scope row is defined as measuring score_evaluated_variants with context
    construction already done. If prepare() raises, there is no such measurement to make, and
    emitting a timed row would label crash-handler time as scoring time. The arm aborts and
    emits nothing -- like a failed warmup, and for the same reason."""
    with pytest.raises(DecisionProfileError, match="context construction"):
        _run(_decl(reps=2), _FakeRep(prepare_fail_on=0),
             timer_scope="score_evaluated_variants")


def test_a_failed_wide_prepare_is_an_ordinary_crash_row():
    """At contexts_and_score scope, prepare() is INSIDE the measured window, so a crash there
    is a legitimate crash row -- measured_ms null, counters real -- not a fail-closed abort.
    The row is not mislabelled: its scope genuinely includes context construction."""
    rows = _run(_decl(reps=2, lifecycle=_WARM), _FakeRep(prepare_fail_on=0),
                timer_scope="contexts_and_score")
    assert [r["outcome"] for r in rows] == ["crash", "ok"]
    assert rows[0]["measured_ms"] is None


# ==========================================================================
# C3: run_arm owns the environment boundary
# ==========================================================================


def test_run_arm_sets_exactly_the_arms_env_and_clears_ambient_behavior_vars(monkeypatch):
    """A behavior-affecting ambient var must not leak into an arm's measurement: the row
    would then measure a config the manifest never declared. run_arm clears it and sets
    exactly decl.env before any session work."""
    monkeypatch.setenv("SHOWDOWN_PROTECT_PENALTY", "9.9")   # ambient, behavior-affecting
    session = _FakeRep()
    _run(_decl(reps=1, env={"SHOWDOWN_OPP_MEGA_CLICK_RATE": "0.35"}), session)
    seen = session.env_seen_inside
    # the arm's env is set, and the ambient behavior-affecting var is gone. (Membership, not
    # exact equality: a Showdown dev shell may carry excluded vars -- USERNAME/SERVER -- that
    # the boundary deliberately leaves alone because they never move config_hash.)
    assert seen.get("SHOWDOWN_OPP_MEGA_CLICK_RATE") == "0.35"
    assert "SHOWDOWN_PROTECT_PENALTY" not in seen
    # and no behavior-affecting var other than the arm's own survives
    from showdown_bot.eval import config_env
    assert config_env.behavior_env(seen) == {"SHOWDOWN_OPP_MEGA_CLICK_RATE": "0.35"}


def test_run_arm_isolates_ambient_calc_backend_and_topm(monkeypatch):
    """CALC_BACKEND and TOPM are excluded from behavior_env (so they never move config_hash),
    but they steer WHAT is measured -- the backend and whether the depth-2 frontier is
    reached. run_arm clears them too, so an arm that does not declare them measures the
    default, not whatever the shell had."""
    monkeypatch.setenv("SHOWDOWN_CALC_BACKEND", "persistent")
    monkeypatch.setenv("SHOWDOWN_SEARCH_TOPM", "7")
    session = _FakeRep()
    _run(_decl(reps=1, env={"SHOWDOWN_OPP_MEGA_CLICK_RATE": "0.35"}), session)
    assert "SHOWDOWN_CALC_BACKEND" not in session.env_seen_inside
    assert "SHOWDOWN_SEARCH_TOPM" not in session.env_seen_inside


def test_run_arm_restores_the_environment_afterwards(monkeypatch):
    monkeypatch.setenv("SHOWDOWN_PROTECT_PENALTY", "9.9")
    monkeypatch.delenv("SHOWDOWN_OPP_MEGA_CLICK_RATE", raising=False)
    import os
    _run(_decl(reps=1, env={"SHOWDOWN_OPP_MEGA_CLICK_RATE": "0.35"}), _FakeRep())
    assert os.environ["SHOWDOWN_PROTECT_PENALTY"] == "9.9"          # ambient restored
    assert "SHOWDOWN_OPP_MEGA_CLICK_RATE" not in os.environ         # arm's env removed


def test_run_arm_restores_even_when_the_arm_raises(monkeypatch):
    monkeypatch.setenv("SHOWDOWN_PROTECT_PENALTY", "9.9")
    with pytest.raises(DecisionProfileError):
        _run(_decl(reps=1), _FakeRep(prepare_fail_on=0),
             timer_scope="score_evaluated_variants")
    import os
    assert os.environ["SHOWDOWN_PROTECT_PENALTY"] == "9.9"


def test_the_in_boundary_check_rejects_a_manifest_env_mismatch():
    """When the caller supplies the manifest arm's behavior_env, run_arm asserts the effective
    environment it just built matches it -- catching a decl that drifted from the manifest the
    row will be validated against."""
    with pytest.raises(DecisionProfileError, match="behavior_env"):
        _run(_decl(reps=1, env={"SHOWDOWN_OPP_MEGA_CLICK_RATE": "0.35"}), _FakeRep(),
             behavior_env={"SHOWDOWN_OPP_MEGA_CLICK_RATE": "0.99"})
