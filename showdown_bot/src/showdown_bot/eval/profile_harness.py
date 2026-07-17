"""The I8 microprofile harness (I8-C): one arm, N repetitions, N rows.

Design §2.4 (rows), §2.5 (timer scopes), §2.6 (crash semantics), §2.8 (lifecycle, cache
sampling). It builds rows. It does not decide anything, measure anything on its own
authority, or freeze anything: the caller supplies the session, and where the rows go is
the caller's problem.

The session seam
----------------
The harness never imports a fixture. The boards live in tests/ -- they are test fixtures,
and production code cannot reach them -- so a ``session`` object supplies exactly what the
harness needs and nothing else:

    counters()    -> the backends' CUMULATIVE counters, right now
    cache_sizes() -> len() of the three semantic caches, right now
    prepare()     -> build this rep's contexts (context construction only)
    score()       -> run score_evaluated_variants over them; return the shape of the work

``prepare`` and ``score`` are split for one reason: the timer scope. Context construction
(``build_own_mega_contexts``) runs before ``score_evaluated_variants`` and, on a shared
backend, spawns and warms the speed cache while doing so (§2.8). So the narrow scope
(``score_evaluated_variants``) must be able to exclude it and the wide scope
(``contexts_and_score``) to include it -- which is only possible if the harness, not the
session, decides where the timer and the counter snapshot sit relative to ``prepare``.

Deltas, and why the harness owns them
-------------------------------------
I8-A's counters are cumulative since construction, deliberately: a backend has no concept
of a "decision", and the row's ``spawn_count_before`` is DEFINED as the cumulative count
before one, so it is computable only from a cumulative counter. The per-decision figures
are therefore taken HERE, by snapshotting around the measured call.

``spawn_count_before`` is sampled at REP START -- before ``prepare`` -- so a fresh per_rep
backend reads 0, which is exactly what the dataset tier's per_rep identity demands. The
counter BASE for the row's deltas is a different snapshot and depends on the scope: at the
narrow scope it is taken AFTER ``prepare`` (so context construction is excluded), at the
wide scope it coincides with the rep-start snapshot (so context construction is included).
``spawn_calls`` uses that same scope-dependent base, which is what keeps the oneshot
identity ``spawn_calls == transport_attempts`` true at both scopes.

Environment boundary
--------------------
``run_arm`` owns the process environment for the arm's whole execution (§4, C3). It clears
every ambient behavior-affecting ``SHOWDOWN_*`` plus the steering vars that do not move
config_hash but do steer what is measured (backend, depth-2 frontier), sets exactly the
arm's env, checks the effective behavior_env against the manifest arm, and restores on the
way out. Without it an ambient var would let a row measure a config its manifest never
declared.
"""
from __future__ import annotations

import os
import time
from contextlib import contextmanager
from enum import StrEnum

from showdown_bot.eval import config_env
from showdown_bot.eval.decision_profile import (
    SCHEMA_VERSION,
    DecisionProfileError,
    backend_class_of,
    expected_cache_class,
)


class RepOutcome(StrEnum):
    OK = "ok"
    CRASH = "crash"


_MICRO_SCOPES = ("contexts_and_score", "score_evaluated_variants")
# The one scope whose window contains context construction (§2.5). The other microprofile
# scope, score_evaluated_variants, excludes it.
_WIDE_SCOPE = "contexts_and_score"

# The four objects ONE session owns. `contexts_and_variants` is deliberately absent: it is
# rebuilt per rep by the caller, not carried in the session, so it may differ freely (§2.8's
# warm-cache configuration pairs a per_arm backend with per_rep contexts).
_SESSION_OBJECTS = ("calc_backend", "damage_oracle", "speed_oracle", "species_dex")

# EXCLUDED from behavior_env (so they never move config_hash) yet they steer WHAT an arm
# measures: which backend implementation runs, and whether the depth-2 frontier is reached.
# run_arm isolates them explicitly, so an arm that does not declare them measures the default
# rather than whatever the ambient shell happened to set (§2.7's TOPM/TOPN exclusion note,
# §2.1's CALC_BACKEND note).
_STEERING_ENV = ("SHOWDOWN_CALC_BACKEND", "SHOWDOWN_SEARCH_TOPM", "SHOWDOWN_SEARCH_TOPN")

_DELTA_FIELDS = (
    "damage_batch_calls",
    "planned_damage_batches",
    "implicit_damage_batches",
    "stats_batch_calls",
    "types_batch_calls",
    "requests_total",
    "requests_unique",
    "cache_hits",
    "transport_attempts",
)


@contextmanager
def _arm_env(arm_env: dict, expected_behavior_env: dict, arm_id: str):
    """The arm's environment boundary: active before session construction and across warmup
    and every timed rep, restored fully on exit.

    Cleared: every set ``SHOWDOWN_*`` that is behavior-affecting (not ``is_excluded``), PLUS
    the steering vars (``CALC_BACKEND``/``TOPM``/``TOPN``) that ``behavior_env`` excludes but
    that still change what is measured. Then exactly ``arm_env`` is set.

    The in-boundary check asserts the effective ``behavior_env`` equals what the manifest arm
    declares. It catches two different faults with one comparison: an ambient behavior var the
    clear somehow missed, and an arm declaration that drifted from the manifest entry its rows
    will be validated against.
    """
    to_clear = {
        k for k in os.environ if k.startswith("SHOWDOWN_") and not config_env.is_excluded(k)
    }
    to_clear.update(_STEERING_ENV)
    touched = to_clear | set(arm_env)
    saved = {k: os.environ.get(k) for k in touched}
    try:
        for k in touched:
            os.environ.pop(k, None)
        for k, v in arm_env.items():
            os.environ[k] = str(v)
        effective = config_env.behavior_env(os.environ)
        if effective != expected_behavior_env:
            raise DecisionProfileError(
                f"arm {arm_id!r}: effective behavior_env {effective} does not match the "
                f"manifest arm's {expected_behavior_env}. Either an ambient SHOWDOWN_* var "
                f"leaked into the measurement, or the arm declaration drifted from the "
                f"manifest entry its rows are validated against"
            )
        yield
    finally:
        for k, original in saved.items():
            if original is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = original


def run_arm(
    decl,
    session_factory,
    *,
    agent: str,
    format_id: str,
    config_id: str,
    git_sha: str,
    config_hash: str,
    profile_manifest_hash: str,
    reps: int,
    behavior_env: dict,
) -> list[dict]:
    """Run one arm's warmup and timed repetitions; return one row per TIMED repetition.

    ``session_factory`` is called to construct a session, and HOW OFTEN it is called is the
    arm's declared lifecycle:

        per_rep -> a fresh session for every repetition, warmup included: its caches and
                   its backend start empty each time, which is what "cold" MEANS.
        per_arm -> one session for the whole arm, so caches and backend carry across reps.

    Taking a single session and reusing it regardless would BE per_arm behaviour wearing
    whatever label the arm declared. This harness's first cut did exactly that, and the
    dataset tier rejected its own output -- a per_rep arm must report
    ``spawn_count_before == 0`` on every rep, and a reused session cannot.

    ``reps`` is passed in rather than read off the arm: it is a RUN parameter, uniform
    across the matrix and fixed in advance by whoever authorizes the run, not a property an
    arm may choose for itself. A per-arm rep count would be an unlogged lever on which arm
    looks cheap.

    ``behavior_env`` is MANDATORY -- the manifest arm's declared behavior_env, cross-checked
    inside the environment boundary. It is required, not defaulted from ``decl.env``, because a
    self-derived default would only ever check ``decl.env`` against itself and could never
    catch a decl that drifted from the manifest its rows are validated against (§2.7, C3-fix).

    ``timer_scope`` is NOT a parameter: it is read from ``decl.timer_scope``, the single source
    the manifest arm was also built from (via ``arm_specs``). Accepting it as a free argument
    would be a second, independent scope truth the frozen evidence never cross-checks -- the
    exact drift the manifest's pinned ``timer_scope`` and the row validator now forbid (§2.5).

    ``agent`` is accepted for symmetry with the manifest producer and is not read here: the
    arm's identity is already pinned by ``config_hash``, which was derived from it.
    """
    if not isinstance(reps, int) or isinstance(reps, bool) or reps < 1:
        raise ValueError(f"reps must be a positive int, got {reps!r}")
    timer_scope = decl.timer_scope
    if timer_scope not in _MICRO_SCOPES:
        # agent_choose is live-only. A microprofile row at that scope is a category error,
        # and pooling it would compare an end-to-end ms with a sub-call ms (§2.5).
        raise DecisionProfileError(
            f"arm {decl.arm_id!r} declares timer_scope {timer_scope!r}, not a microprofile "
            f"scope; expected one of {list(_MICRO_SCOPES)}"
        )

    # ONE session covers the backend AND the three caches, so this harness can only honour
    # a lifecycle where all four agree. A mixed declaration (per_arm caches on a per_rep
    # backend, say) would be silently flattened to whichever branch the code happens to
    # take, and the arm would measure something other than what it declared.
    session_scope = {decl.lifecycle.get(k) for k in _SESSION_OBJECTS}
    if len(session_scope) != 1:
        raise DecisionProfileError(
            f"arm {decl.arm_id!r} declares a mixed lifecycle across "
            f"{sorted(_SESSION_OBJECTS)}: {sorted(map(str, session_scope))}. One session "
            f"covers all four, so this harness cannot represent them independently -- it "
            f"would silently measure something other than the declaration"
        )
    per_rep = session_scope.pop() == "per_rep"
    expected_behavior_env = behavior_env
    arm_entry = {"warmup": decl.warmup, "lifecycle": dict(decl.lifecycle)}

    rows: list[dict] = []
    # The boundary wraps session construction too: `make_calc_backend` reads
    # SHOWDOWN_CALC_BACKEND at construction, so it must already be the arm's.
    with _arm_env(dict(decl.env), expected_behavior_env, decl.arm_id):
        shared = None if per_rep else session_factory()

        # Warmup: untimed, and emits NO rows (§2.8). It runs the FULL decision -- prepare()
        # then score() -- so a warm-cache arm's timed reps start with contexts already built
        # once and caches already populated.
        #
        # FAIL CLOSED. A swallowed warmup failure is worse than no warmup: the point of
        # warming is to GUARANTEE the state the timed reps then claim, so a warmup that raised
        # leaves every following row asserting a warm cache nobody established. No timed rep
        # runs, and no row is emitted.
        for index in range(decl.warmup):
            warm = session_factory() if per_rep else shared
            try:
                warm.prepare()
                warm.score()
            except Exception as exc:  # noqa: BLE001
                raise DecisionProfileError(
                    f"arm {decl.arm_id!r}: warmup repetition {index} failed ({exc!r}). A "
                    f"failed warmup guarantees no warm state, so this arm produces no timed "
                    f"rows: a row claiming a warm cache that nothing established would read "
                    f"as ordinary evidence and be false"
                ) from exc

        for rep in range(reps):
            session = session_factory() if per_rep else shared
            rows.append(_run_rep(decl, session, arm_entry, rep,
                                 format_id=format_id, config_id=config_id, git_sha=git_sha,
                                 config_hash=config_hash,
                                 profile_manifest_hash=profile_manifest_hash,
                                 timer_scope=timer_scope))
    return rows


def _timed(session, *, prepare: bool):
    """Run the measured window and return (outcome, shape, measured_ms).

    ``prepare=True`` (wide scope) puts context construction INSIDE the window; a crash there
    is an ordinary crash row. ``prepare=False`` (narrow scope) means prepare() already ran,
    untimed, before this call.
    """
    started = time.perf_counter()
    try:
        if prepare:
            session.prepare()
        shape = session.score() or {}
        measured_ms = (time.perf_counter() - started) * 1000.0
        return RepOutcome.OK, shape, measured_ms
    except Exception:  # noqa: BLE001 - the row is still emitted: its counters are real,
        return RepOutcome.CRASH, {}, None   # and dropping it would silently bias the mix.


def _run_rep(decl, session, arm_entry, rep, *, format_id, config_id, git_sha,
             config_hash, profile_manifest_hash, timer_scope) -> dict:
    wide = timer_scope == _WIDE_SCOPE

    # AT REP START -- before context construction (§2.8). Cache sizes here, not at timer
    # start: context construction legitimately populates _spe_cache before
    # score_evaluated_variants is entered, so a timer-start sample would report every
    # cold-cache arm as warm. spawn_count_before here too, and for the same reason it must be
    # here rather than after prepare: a fresh per_rep backend reads 0 at rep start, which is
    # exactly the per_rep dataset identity -- reading it after prepare would see the shared
    # backend's context-construction spawn and report 1.
    sizes = session.cache_sizes()
    rep_start = session.counters()
    spawn_count_before = rep_start["spawn_count"]

    if not wide:
        # NARROW (score_evaluated_variants): prepare OUTSIDE the timer and the counter base,
        # so context construction is excluded from the row entirely. A prepare() failure
        # aborts the arm FAIL-CLOSED -- there is no score_evaluated_variants to measure for a
        # rep whose contexts never built, and a timed row here would label crash-handler time
        # as scoring time (contrast the wide scope, where prepare is legitimately measured).
        try:
            session.prepare()
        except Exception as exc:  # noqa: BLE001
            raise DecisionProfileError(
                f"arm {decl.arm_id!r}: rep {rep} context construction failed at "
                f"timer_scope={timer_scope!r} ({exc!r}). The narrow scope excludes context "
                f"construction from the window, so a rep whose contexts never built has no "
                f"score_evaluated_variants to measure; emitting a timed row would label "
                f"crash-handler time as scoring time. The arm aborts"
            ) from exc
        base = session.counters()
        outcome, shape, measured_ms = _timed(session, prepare=False)
    else:
        # WIDE (contexts_and_score): the counter base and the timer both sit BEFORE prepare,
        # so context construction is part of the measured decision. base coincides with the
        # rep-start snapshot, so here spawn_count_before IS the delta base.
        base = rep_start
        outcome, shape, measured_ms = _timed(session, prepare=True)

    after = session.counters()
    delta = {f: after[f] - base[f] for f in _DELTA_FIELDS}
    # spawn_calls shares the scope-dependent base with the other deltas, so oneshot's
    # `spawn_calls == transport_attempts` holds at BOTH scopes. It is NOT after-minus-
    # spawn_count_before: at the narrow scope those differ (spawn_count_before is rep-start,
    # base is post-prepare), and using the rep-start value would fold context construction's
    # spawn back into a window that excludes it.
    spawn_calls = after["spawn_count"] - base["spawn_count"]

    transport_calls = (
        delta["damage_batch_calls"] + delta["stats_batch_calls"] + delta["types_batch_calls"]
    )
    transport_retried = delta["transport_attempts"] > transport_calls

    backend = decl.env.get("SHOWDOWN_CALC_BACKEND", "oneshot")

    return {
        "schema_version": SCHEMA_VERSION,
        "source": "microprofile",
        "battle_id": None,
        "decision_index": None,
        "arm_id": decl.arm_id,
        "rep": rep,
        "config_id": config_id,
        "format_id": format_id,
        "git_sha": git_sha,
        "config_hash": config_hash,
        "schedule_hash": None,
        "profile_manifest_hash": profile_manifest_hash,
        "calc_backend": backend,
        "backend_class": backend_class_of(
            backend, spawn_count_before, spawn_calls, transport_retried
        ),
        # DERIVED from the arm's declared lifecycle, then falsified by the sizes above:
        # a "cold" row whose caches were already populated disproves the declaration.
        "cache_class": expected_cache_class(arm_entry, rep),
        "damage_cache_size_at_rep_start": sizes["damage"],
        "speed_cache_size_at_rep_start": sizes["speed"],
        "dex_cache_size_at_rep_start": sizes["dex"],
        "spawn_count_before": spawn_count_before,
        "transport_retried": transport_retried,
        "timer_scope": timer_scope,
        "measured_ms": measured_ms,
        "damage_batch_calls": delta["damage_batch_calls"],
        "planned_damage_batches": delta["planned_damage_batches"],
        "implicit_damage_batches": delta["implicit_damage_batches"],
        "stats_batch_calls": delta["stats_batch_calls"],
        "types_batch_calls": delta["types_batch_calls"],
        "transport_calls": transport_calls,
        "transport_attempts": delta["transport_attempts"],
        "spawn_calls": spawn_calls,
        "requests_total": delta["requests_total"],
        "requests_unique": delta["requests_unique"],
        "cache_hits": delta["cache_hits"],
        "n_candidates": shape.get("n_candidates", 0),
        "n_responses": shape.get("n_responses", 0),
        "n_mega_twins": shape.get("n_mega_twins", 0),
        "n_branches": shape.get("n_branches", 0),
        "n_worlds": shape.get("n_worlds", 0),
        "depth2_frontier": shape.get("depth2_frontier", 0),
        "foe_mega_active": bool(shape.get("foe_mega_active", False)),
        "outcome": str(outcome),
    }
