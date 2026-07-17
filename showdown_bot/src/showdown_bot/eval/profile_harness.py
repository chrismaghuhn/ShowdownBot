"""The I8 microprofile harness (I8-C, C2): one arm, N repetitions, N rows.

Design §2.4 (rows), §2.5 (timer scopes), §2.6 (crash semantics), §2.8 (lifecycle, cache
sampling). It builds rows. It does not decide anything, measure anything on its own
authority, or freeze anything: the caller supplies the session, and where the rows go is
the caller's problem.

The session seam
----------------
The harness never imports a fixture. The boards live in tests/conftest.py -- they are test
fixtures, and production code cannot reach them -- so a ``session`` object supplies the
three things the harness needs and nothing else:

    counters()    -> the backends' CUMULATIVE counters, right now
    cache_sizes() -> len() of the three semantic caches, right now
    score()       -> run one repetition; return the shape of the work it did

That seam is what lets the arm matrix live in src/ (unit-tested) while the boards stay in
tests/, and it is the same split ``scripts/run_cap_latency_sweep.py`` states for itself:
pure logic in a module, the driver elsewhere.

Deltas, and why the harness owns them
-------------------------------------
I8-A's counters are cumulative since construction, deliberately: a backend has no concept
of a "decision", and the row's ``spawn_count_before`` is DEFINED as the cumulative count
before one, so it is computable only from a cumulative counter. The per-decision figures
are therefore taken HERE, by snapshotting around the measured call. Reading a cumulative
counter straight onto a row would make rep 5 look five times more expensive than rep 1.

A failed repetition keeps its real deltas. The round trip happened and paid its latency;
I8-A counts the attempt for exactly that reason, and §2.6 keeps a non-ok row's counters
*because* they describe transport that really happened. Only ``measured_ms`` goes null --
a crashed rep's wall clock is the crash handler, not decision work.
"""
from __future__ import annotations

import time
from enum import StrEnum

from showdown_bot.eval.decision_profile import (
    SCHEMA_VERSION,
    DecisionProfileError,
    expected_cache_class,
)


class RepOutcome(StrEnum):
    OK = "ok"
    CRASH = "crash"


_MICRO_SCOPES = ("contexts_and_score", "score_evaluated_variants")

# The four objects ONE session owns. `contexts_and_variants` is deliberately absent: it is
# rebuilt per rep by the caller, not carried in the session, so it may differ freely (§2.8's
# warm-cache configuration pairs a per_arm backend with per_rep contexts).
_SESSION_OBJECTS = ("calc_backend", "damage_oracle", "speed_oracle", "species_dex")

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
    timer_scope: str,
    reps: int,
) -> list[dict]:
    """Run one arm's warmup and timed repetitions; return one row per TIMED repetition.

    ``session_factory`` is called to construct a session, and HOW OFTEN it is called is the
    arm's declared lifecycle. That is what makes the lifecycle real rather than merely
    declared:

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

    ``agent`` is accepted for symmetry with the manifest producer and is not read here: the
    arm's identity is already pinned by ``config_hash``, which was derived from it.
    """
    if not isinstance(reps, int) or isinstance(reps, bool) or reps < 1:
        raise ValueError(f"reps must be a positive int, got {reps!r}")
    if timer_scope not in _MICRO_SCOPES:
        # agent_choose is live-only. A microprofile row at that scope is a category error,
        # and pooling it would compare an end-to-end ms with a sub-call ms (§2.5).
        raise DecisionProfileError(
            f"timer_scope {timer_scope!r} is not a microprofile scope; expected one of "
            f"{list(_MICRO_SCOPES)}"
        )

    # ONE session covers the backend AND the three caches, so this harness can only honour
    # a lifecycle where all four agree. A mixed declaration (per_arm caches on a per_rep
    # backend, say) would be silently flattened to whichever branch the code happens to
    # take, and the arm would measure something other than what it declared. No runnable
    # arm is mixed today -- every one is fully per_rep -- so this is not a live measurement
    # error; without the guard it would become one, quietly, the first time a warm arm was
    # added.
    session_scope = {decl.lifecycle.get(k) for k in _SESSION_OBJECTS}
    if len(session_scope) != 1:
        raise DecisionProfileError(
            f"arm {decl.arm_id!r} declares a mixed lifecycle across "
            f"{sorted(_SESSION_OBJECTS)}: {sorted(map(str, session_scope))}. One session "
            f"covers all four, so this harness cannot represent them independently -- it "
            f"would silently measure something other than the declaration"
        )
    per_rep = session_scope.pop() == "per_rep"
    shared = None if per_rep else session_factory()
    arm_entry = {"warmup": decl.warmup, "lifecycle": dict(decl.lifecycle)}

    # Warmup: untimed, and emits NO rows (§2.8). It exists so a warm-cache arm's timed reps
    # start warm.
    #
    # FAIL CLOSED. A swallowed warmup failure is worse than no warmup: the point of warming
    # is to GUARANTEE the state the timed reps then claim, so a warmup that raised leaves
    # every following row asserting a warm cache nobody established. The rows would look
    # ordinary and be wrong. No timed rep runs, and no row is emitted.
    for index in range(decl.warmup):
        try:
            (session_factory() if per_rep else shared).score()
        except Exception as exc:  # noqa: BLE001
            raise DecisionProfileError(
                f"arm {decl.arm_id!r}: warmup repetition {index} failed ({exc!r}). A failed "
                f"warmup guarantees no warm state, so this arm produces no timed rows: a row "
                f"claiming a warm cache that nothing established would read as ordinary "
                f"evidence and be false"
            ) from exc

    rows: list[dict] = []
    for rep in range(reps):
        session = session_factory() if per_rep else shared
        rows.append(_run_rep(decl, session, arm_entry, rep,
                             format_id=format_id, config_id=config_id, git_sha=git_sha,
                             config_hash=config_hash,
                             profile_manifest_hash=profile_manifest_hash,
                             timer_scope=timer_scope))
    return rows


def _run_rep(decl, session, arm_entry, rep, *, format_id, config_id, git_sha,
             config_hash, profile_manifest_hash, timer_scope) -> dict:
    # AT REP START -- before the rep runs, so before context construction. Not at timer
    # start: context construction legitimately populates _spe_cache before
    # score_evaluated_variants is entered, so a timer-start sample would report every
    # cold-cache arm as warm (§2.8).
    sizes = session.cache_sizes()
    before = session.counters()
    spawn_count_before = before["spawn_count"]

    outcome = RepOutcome.OK
    shape: dict = {}
    started = time.perf_counter()
    try:
        shape = session.score() or {}
        measured_ms = (time.perf_counter() - started) * 1000.0
    except Exception:  # noqa: BLE001 - the row is still emitted: its counters are real,
        outcome = RepOutcome.CRASH   # and dropping it would silently bias the distribution.
        measured_ms = None

    after = session.counters()
    delta = {f: after[f] - before[f] for f in _DELTA_FIELDS}
    spawn_calls = after["spawn_count"] - spawn_count_before

    transport_calls = (
        delta["damage_batch_calls"] + delta["stats_batch_calls"] + delta["types_batch_calls"]
    )
    transport_retried = delta["transport_attempts"] > transport_calls

    backend = decl.env.get("SHOWDOWN_CALC_BACKEND", "oneshot")

    from showdown_bot.eval.decision_profile import backend_class_of

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
