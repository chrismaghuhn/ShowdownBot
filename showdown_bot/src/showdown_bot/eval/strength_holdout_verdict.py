"""Task 7: two independent, fail-closed upstream verdict verifiers -- I8-D and Coverage.

Gate B may only run once a genuine I8-D PASS and a genuine Coverage PASS are proven for the SAME
candidate identity (DESIGN sec 5). I8-D and Coverage have genuinely DIFFERENT verdict schemas --
this module never shares a generic mini-check between them; each verifier owns its own closed
field schema, its own gate-specific constants, and its own fresh offline rebuild of that gate's
canonical schedule (never trusting the artifact's own claims).

``verify_i8d_verdict_artifact`` mirrors the I8-D verification block already hardened inline in
``coverage_runner.run_coverage_gate`` (eight review rounds deep) -- reusing its exact field set,
check order, and constants rather than re-deriving a second, possibly-drifted copy. The two
canonical-schedule rebuilders (``build_i8d_canonical_schedule`` / ``build_coverage_live_schedule``)
are imported, not reimplemented, from ``coverage_runner`` -- the same functions that block already
uses. No existing runner or evidence file is modified by this module.

Every artifact/schema/type/provenance/rebuild failure raises ``StrengthHoldoutRunError`` -- never a
raw ``KeyError``/``TypeError``/``JSONDecodeError``/``OSError`` or a lower-level Panel/Schedule
error. Malformed types are validated explicitly before ever reaching ``.get()``/``dict(...)``/
``sorted(...)``/numeric comparisons that could otherwise raise something else."""
from __future__ import annotations

import json
from dataclasses import dataclass

from showdown_bot.eval.coverage_runner import build_coverage_live_schedule, build_i8d_canonical_schedule
from showdown_bot.eval.coverage_schedule import COVERAGE_CELLS, COVERAGE_EXPECTED_PANEL_HASH, COVERAGE_SEED_BASE
from showdown_bot.eval.coverage_verdict import COVERAGE_CELL_FLOORS, COVERAGE_MAX_SCORED_DECISIONS
from showdown_bot.eval.gates import load_latency_budget_ms
from showdown_bot.eval.i8d_runner import (
    I8D_MAX_SCORED_DECISIONS, I8D_MIN_ACTIVE_DECISIONS, I8D_MIN_DISTINCT_BATTLES,
)
from showdown_bot.eval.i8d_schedule import I8D_EXPECTED_PANEL_HASH, I8D_SEED_BASE
from showdown_bot.eval.pairing import Pair
from showdown_bot.eval.report import _build_cells, _find_cell_flips, _paired_verdict, _strength_delta
from showdown_bot.eval.stats import exact_binom_two_sided_p, mcnemar_counts

# (mirrors coverage_runner._I8D_VERDICT_REQUIRED_FIELDS exactly -- the field set a genuine I8-D
# verdict.json always carries, per i8d_runner.run_i8d_live_gate's own report construction.)
_I8D_VERDICT_REQUIRED_FIELDS = frozenset({
    "candidate_identity", "git_sha", "config_hash", "calc_backend", "hero_agent",
    "verdict", "panel_hash", "schedule_hash", "seed_base", "seed_log_verified",
    "p95_is_gate_value", "hero_team_hash", "opp_team_hashes", "battles_played",
    "scored_decisions", "max_scored_decisions", "scored_overshoot",
    "active_valid_decisions", "distinct_active_battles", "stop_reason",
    "exposure_floor_met", "min_active_decisions", "min_distinct_battles",
    "budget_ms", "p95_ms",
})

# The field set a genuine coverage verdict.json always carries, per coverage_runner.
# run_coverage_gate's own report construction (report's own keys + coverage_verdict()'s keys).
_COVERAGE_VERDICT_REQUIRED_FIELDS = frozenset({
    "schedule_hash", "panel_hash", "candidate_identity", "git_sha", "config_hash",
    "calc_backend", "hero_agent", "hero_team_hash", "opp_team_hashes", "seed_base",
    "seed_log_verified", "battles_played", "scored_decisions", "max_scored_decisions",
    "cell_floors", "cell_counts", "safety_violations", "schedule_complete",
    "verdict", "stop_reason",
})

_CELL_COUNT_FIELDS = frozenset({"decisions", "distinct_battles"})


class StrengthHoldoutRunError(Exception):
    """An upstream (I8-D or Coverage) verdict artifact could not be verified -- a missing/
    malformed file, a schema violation, an identity/provenance mismatch, or a schedule-binding
    failure. Gate B may never run without both PASSing, so this is fail-closed: any doubt raises
    this, never a raw KeyError/TypeError/JSONDecodeError/OSError or a lower-level Panel/Schedule
    error."""


def _load_verdict_json(verdict_path: str, *, gate_name: str) -> dict:
    if not isinstance(verdict_path, str) or not verdict_path:
        raise StrengthHoldoutRunError(
            f"{gate_name} verdict_path must be a non-empty string, got {verdict_path!r}"
        )
    try:
        with open(verdict_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise StrengthHoldoutRunError(
            f"cannot read the {gate_name} verdict at {verdict_path!r}: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} is not a JSON object "
            f"(got {type(data).__name__}): not a genuine {gate_name} gate artifact"
        )
    return data


def _check_closed_schema(data: dict, required: frozenset, *, verdict_path: str, gate_name: str) -> None:
    actual = set(data)
    missing = required - actual
    extra = actual - required
    if missing or extra:
        problems = []
        if missing:
            problems.append(f"missing required field(s) {sorted(missing)}")
        if extra:
            problems.append(f"unexpected extra field(s) {sorted(extra)}")
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} has {' and '.join(problems)}: not a "
            f"genuine {gate_name} gate artifact"
        )


def _check_identity_fields(data: dict, *, verdict_path: str, gate_name: str, candidate_identity: str,
                            git_sha: str, config_hash: str, hero_agent: str, calc_backend: str) -> None:
    for field, expected in (
        ("candidate_identity", candidate_identity), ("git_sha", git_sha),
        ("config_hash", config_hash), ("hero_agent", hero_agent), ("calc_backend", calc_backend),
    ):
        if data[field] != expected:
            raise StrengthHoldoutRunError(
                f"the {gate_name} verdict at {verdict_path!r} has {field}={data[field]!r} != "
                f"expected {expected!r}: {gate_name} must have run on the SAME candidate"
            )


def _check_nonempty_str(value, *, field: str, verdict_path: str, gate_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} has {field}={value!r}, not a non-empty "
            f"string: not a genuine {gate_name} gate artifact"
        )


def _check_list_of_nonempty_strs(value, *, field: str, verdict_path: str, gate_name: str) -> None:
    if not isinstance(value, list) or not all(isinstance(x, str) and x for x in value):
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} has {field}={value!r}, not a list of "
            f"non-empty strings: not a genuine {gate_name} gate artifact"
        )


def _check_nonnegative_int(value, *, field: str, verdict_path: str, gate_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} has {field}={value!r}, not a "
            f"non-negative int: not a genuine {gate_name} gate artifact"
        )


def verify_i8d_verdict_artifact(
    *, verdict_path: str, teams_root: str, candidate_identity: str, git_sha: str,
    config_hash: str, hero_agent: str, calc_backend: str,
) -> dict:
    """Verify a real I8-D verdict.json exists, has the exact closed I8-D schema, identifies the
    SAME candidate as the five given identity fields, binds panel/seed/schedule identity to the
    pinned I8-D constants and a schedule freshly rebuilt from the current checkout (never trusting
    the artifact's own claims), and genuinely PASSed. Returns the loaded verdict dict on success;
    raises ``StrengthHoldoutRunError`` on the first violation found."""
    gate_name = "I8-D"
    data = _load_verdict_json(verdict_path, gate_name=gate_name)
    _check_closed_schema(data, _I8D_VERDICT_REQUIRED_FIELDS, verdict_path=verdict_path, gate_name=gate_name)

    # Five per-run counters: type-safe first (never a bool, never negative), then their mutual
    # consistency -- the scored_overshoot formula and the two subset relationships hold for ANY
    # genuine artifact, PASS or not (coverage_runner.py review round 8, P1).
    for counter_field in ("battles_played", "scored_decisions", "scored_overshoot",
                          "active_valid_decisions", "distinct_active_battles"):
        _check_nonnegative_int(data[counter_field], field=counter_field, verdict_path=verdict_path, gate_name=gate_name)
    expected_overshoot = max(0, data["scored_decisions"] - I8D_MAX_SCORED_DECISIONS)
    if data["scored_overshoot"] != expected_overshoot:
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} has scored_overshoot "
            f"{data['scored_overshoot']!r} != max(0, scored_decisions - {I8D_MAX_SCORED_DECISIONS}) "
            f"= {expected_overshoot!r}: not a genuine {gate_name} gate artifact"
        )
    if data["active_valid_decisions"] > data["scored_decisions"]:
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} has active_valid_decisions "
            f"{data['active_valid_decisions']!r} > scored_decisions {data['scored_decisions']!r}: "
            f"active-valid rows cannot outnumber all scored rows"
        )
    if data["distinct_active_battles"] > data["battles_played"]:
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} has distinct_active_battles "
            f"{data['distinct_active_battles']!r} > battles_played {data['battles_played']!r}: "
            f"distinct active battles cannot outnumber battles played"
        )

    if data["panel_hash"] != I8D_EXPECTED_PANEL_HASH:
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} has panel_hash {data['panel_hash']!r} "
            f"!= the pinned I8-D panel {I8D_EXPECTED_PANEL_HASH!r}: not a genuine {gate_name} gate artifact"
        )
    if data["seed_base"] != I8D_SEED_BASE:
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} has seed_base {data['seed_base']!r} != "
            f"the pinned I8-D seed namespace {I8D_SEED_BASE!r}: not a genuine {gate_name} gate artifact"
        )
    if data["seed_log_verified"] is not True:
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} does not have seed_log_verified=True: "
            f"not a genuine {gate_name} gate artifact"
        )
    if data["min_active_decisions"] != I8D_MIN_ACTIVE_DECISIONS:
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} has min_active_decisions "
            f"{data['min_active_decisions']!r} != the pinned floor {I8D_MIN_ACTIVE_DECISIONS!r}"
        )
    if data["min_distinct_battles"] != I8D_MIN_DISTINCT_BATTLES:
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} has min_distinct_battles "
            f"{data['min_distinct_battles']!r} != the pinned floor {I8D_MIN_DISTINCT_BATTLES!r}"
        )
    if data["max_scored_decisions"] != I8D_MAX_SCORED_DECISIONS:
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} has max_scored_decisions "
            f"{data['max_scored_decisions']!r} != the pinned cap {I8D_MAX_SCORED_DECISIONS!r}"
        )
    budget_ms = load_latency_budget_ms()
    if data["budget_ms"] != budget_ms:
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} has budget_ms {data['budget_ms']!r} != "
            f"the pinned latency budget {budget_ms!r}"
        )

    _check_identity_fields(
        data, verdict_path=verdict_path, gate_name=gate_name, candidate_identity=candidate_identity,
        git_sha=git_sha, config_hash=config_hash, hero_agent=hero_agent, calc_backend=calc_backend,
    )

    _check_nonempty_str(data["hero_team_hash"], field="hero_team_hash", verdict_path=verdict_path, gate_name=gate_name)
    _check_list_of_nonempty_strs(data["opp_team_hashes"], field="opp_team_hashes", verdict_path=verdict_path, gate_name=gate_name)

    try:
        canonical = build_i8d_canonical_schedule(teams_root=teams_root)
    except Exception as exc:  # noqa: BLE001 -- deliberately broad: any rebuild failure (a
        # lower-level Panel/Schedule error, a missing file, ...) must translate to
        # StrengthHoldoutRunError, never escape this module raw.
        raise StrengthHoldoutRunError(
            f"failed to rebuild the canonical {gate_name} schedule from "
            f"teams_root={teams_root!r}: {type(exc).__name__}: {exc}"
        ) from exc
    if data["battles_played"] > len(canonical.rows):
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} has battles_played "
            f"{data['battles_played']!r} > the canonical {gate_name} schedule's "
            f"{len(canonical.rows)} row(s): a genuine run can never play more battles than the "
            f"schedule has"
        )
    if data["schedule_hash"] != canonical.schedule_hash:
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} has schedule_hash "
            f"{data['schedule_hash']!r} != the canonical I8-D schedule_hash freshly rebuilt from "
            f"the pinned I8-D panel ({canonical.schedule_hash!r})"
        )
    canonical_hero_hash = canonical.rows[0].hero_team_hash if canonical.rows else None
    if data["hero_team_hash"] != canonical_hero_hash:
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} has hero_team_hash "
            f"{data['hero_team_hash']!r} != the canonical I8-D hero_team_hash {canonical_hero_hash!r}"
        )
    canonical_opp_hashes = sorted({r.opp_team_hash for r in canonical.rows if r.opp_team_hash is not None})
    if data["opp_team_hashes"] != canonical_opp_hashes:
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} has opp_team_hashes "
            f"{data['opp_team_hashes']!r} != the canonical I8-D opp_team_hashes {canonical_opp_hashes!r}"
        )

    if data["verdict"] != "PASS":
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} is {data['verdict']!r}, not 'PASS': "
            f"Gate B may only run after {gate_name} PASSes on the same candidate"
        )
    if data["p95_is_gate_value"] is not True:
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} claims verdict='PASS' but "
            f"p95_is_gate_value is not True: not a genuine {gate_name} gate artifact"
        )
    if data["exposure_floor_met"] is not True:
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} claims verdict='PASS' but "
            f"exposure_floor_met is not True: not a genuine {gate_name} gate artifact"
        )
    if data["active_valid_decisions"] < data["min_active_decisions"]:
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} claims exposure_floor_met=True but "
            f"active_valid_decisions {data['active_valid_decisions']!r} < min_active_decisions "
            f"{data['min_active_decisions']!r}"
        )
    if data["distinct_active_battles"] < data["min_distinct_battles"]:
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} claims exposure_floor_met=True but "
            f"distinct_active_battles {data['distinct_active_battles']!r} < min_distinct_battles "
            f"{data['min_distinct_battles']!r}"
        )
    if data["stop_reason"] != "exposure_floor_met":
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} claims verdict='PASS' but stop_reason is "
            f"{data['stop_reason']!r}, not 'exposure_floor_met'"
        )
    p95_ms = data["p95_ms"]
    # A closed range check is NaN-safe: `0 <= NaN` is already False under IEEE 754, so the
    # chained comparison short-circuits to False and `not (...)` correctly flags it -- the same
    # range naturally excludes negative values and +/-inf too, with no separate isnan()/isinf()
    # needed (coverage_runner.py review round 8, P1 finding, empirically reproduced there).
    if (isinstance(p95_ms, bool) or not isinstance(p95_ms, (int, float))
            or not (0 <= p95_ms <= budget_ms)):
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} claims verdict='PASS' but p95_ms "
            f"{p95_ms!r} is not a finite real number in [0, {budget_ms}] ms"
        )
    return data


def verify_coverage_verdict_artifact(
    *, verdict_path: str, teams_root: str, candidate_identity: str, git_sha: str,
    config_hash: str, hero_agent: str, calc_backend: str,
) -> dict:
    """Verify a real Coverage verdict.json exists, has the exact closed Coverage schema (a
    genuinely different shape from I8-D's -- cell_floors/cell_counts/safety_violations/
    schedule_complete, no p95/budget/exposure-floor fields at all), identifies the SAME candidate
    as the five given identity fields, binds panel/seed/schedule identity to the pinned Coverage
    constants and a schedule freshly rebuilt from the current checkout, every cell meets its
    pinned floor, safety is clean, and the run genuinely PASSed. Returns the loaded verdict dict
    on success; raises ``StrengthHoldoutRunError`` on the first violation found."""
    gate_name = "Coverage"
    data = _load_verdict_json(verdict_path, gate_name=gate_name)
    _check_closed_schema(data, _COVERAGE_VERDICT_REQUIRED_FIELDS, verdict_path=verdict_path, gate_name=gate_name)

    for counter_field in ("battles_played", "scored_decisions", "safety_violations"):
        _check_nonnegative_int(data[counter_field], field=counter_field, verdict_path=verdict_path, gate_name=gate_name)

    if data["panel_hash"] != COVERAGE_EXPECTED_PANEL_HASH:
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} has panel_hash {data['panel_hash']!r} "
            f"!= the pinned Coverage panel {COVERAGE_EXPECTED_PANEL_HASH!r}"
        )
    if data["seed_base"] != COVERAGE_SEED_BASE:
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} has seed_base {data['seed_base']!r} != "
            f"the pinned Coverage seed namespace {COVERAGE_SEED_BASE!r}"
        )
    if data["seed_log_verified"] is not True:
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} does not have seed_log_verified=True: "
            f"not a genuine {gate_name} gate artifact"
        )
    if data["max_scored_decisions"] != COVERAGE_MAX_SCORED_DECISIONS:
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} has max_scored_decisions "
            f"{data['max_scored_decisions']!r} != the pinned cap {COVERAGE_MAX_SCORED_DECISIONS!r}"
        )

    _check_identity_fields(
        data, verdict_path=verdict_path, gate_name=gate_name, candidate_identity=candidate_identity,
        git_sha=git_sha, config_hash=config_hash, hero_agent=hero_agent, calc_backend=calc_backend,
    )

    _check_nonempty_str(data["hero_team_hash"], field="hero_team_hash", verdict_path=verdict_path, gate_name=gate_name)
    _check_list_of_nonempty_strs(data["opp_team_hashes"], field="opp_team_hashes", verdict_path=verdict_path, gate_name=gate_name)

    try:
        canonical = build_coverage_live_schedule(teams_root=teams_root)
    except Exception as exc:  # noqa: BLE001 -- deliberately broad: any rebuild failure (a
        # lower-level Panel/Schedule error, a missing file, ...) must translate to
        # StrengthHoldoutRunError, never escape this module raw.
        raise StrengthHoldoutRunError(
            f"failed to rebuild the canonical {gate_name} schedule from "
            f"teams_root={teams_root!r}: {type(exc).__name__}: {exc}"
        ) from exc
    if data["battles_played"] > len(canonical.rows):
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} has battles_played "
            f"{data['battles_played']!r} > the canonical {gate_name} schedule's "
            f"{len(canonical.rows)} row(s): a genuine run can never play more battles than the "
            f"schedule has"
        )
    if data["schedule_hash"] != canonical.schedule_hash:
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} has schedule_hash "
            f"{data['schedule_hash']!r} != the canonical Coverage schedule_hash freshly rebuilt "
            f"from the locked Coverage panel/manifest ({canonical.schedule_hash!r})"
        )
    canonical_hero_hash = canonical.rows[0].hero_team_hash if canonical.rows else None
    if data["hero_team_hash"] != canonical_hero_hash:
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} has hero_team_hash "
            f"{data['hero_team_hash']!r} != the canonical Coverage hero_team_hash {canonical_hero_hash!r}"
        )
    canonical_opp_hashes = sorted({r.opp_team_hash for r in canonical.rows if r.opp_team_hash is not None})
    if data["opp_team_hashes"] != canonical_opp_hashes:
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} has opp_team_hashes "
            f"{data['opp_team_hashes']!r} != the canonical Coverage opp_team_hashes {canonical_opp_hashes!r}"
        )

    if not isinstance(data["schedule_complete"], bool):
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} has schedule_complete "
            f"{data['schedule_complete']!r}, not a bool: not a genuine {gate_name} gate artifact"
        )
    # schedule_complete is NOT required to be True -- a coverage PASS can legitimately happen
    # before the schedule is exhausted (the floor stop fires first). But its value must exactly
    # reflect whether the schedule genuinely was exhausted (Task 7 review-fix, P1 #2): True only
    # when battles_played == every row of the canonical schedule, False otherwise.
    expected_schedule_complete = data["battles_played"] == len(canonical.rows)
    if data["schedule_complete"] != expected_schedule_complete:
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} has schedule_complete "
            f"{data['schedule_complete']!r}, but battles_played {data['battles_played']!r} "
            f"{'==' if expected_schedule_complete else '!='} the canonical schedule's "
            f"{len(canonical.rows)} row(s): schedule_complete must reflect that exactly"
        )

    # A straight equality check against the pinned floors is type-safe for ANY value of
    # data["cell_floors"] (a dict != a list/int/str/None never raises), so this ALSO serves as
    # the "cell_floors falsch oder typfalsch" check -- no separate isinstance guard needed.
    expected_cell_floors = {cell: list(floor) for cell, floor in COVERAGE_CELL_FLOORS.items()}
    if data["cell_floors"] != expected_cell_floors:
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} has cell_floors {data['cell_floors']!r} "
            f"!= the pinned COVERAGE_CELL_FLOORS {expected_cell_floors!r}"
        )

    cell_counts = data["cell_counts"]
    if not isinstance(cell_counts, dict):
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} has cell_counts "
            f"{cell_counts!r}, not an object: not a genuine {gate_name} gate artifact"
        )
    if set(cell_counts) != set(COVERAGE_CELLS):
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} has cell_counts covering "
            f"{sorted(cell_counts)}, expected exactly {sorted(COVERAGE_CELLS)}"
        )
    for cell in COVERAGE_CELLS:
        counts = cell_counts[cell]
        if not isinstance(counts, dict):
            raise StrengthHoldoutRunError(
                f"the {gate_name} verdict at {verdict_path!r} has cell_counts[{cell!r}]="
                f"{counts!r}, not an object: not a genuine {gate_name} gate artifact"
            )
        if set(counts) != _CELL_COUNT_FIELDS:
            raise StrengthHoldoutRunError(
                f"the {gate_name} verdict at {verdict_path!r} has cell_counts[{cell!r}] fields "
                f"{sorted(counts)}, expected exactly {sorted(_CELL_COUNT_FIELDS)}"
            )
        for count_field in _CELL_COUNT_FIELDS:
            _check_nonnegative_int(
                counts[count_field], field=f"cell_counts[{cell!r}][{count_field!r}]",
                verdict_path=verdict_path, gate_name=gate_name,
            )
        if counts["decisions"] > data["scored_decisions"]:
            raise StrengthHoldoutRunError(
                f"the {gate_name} verdict at {verdict_path!r} has "
                f"cell_counts[{cell!r}]['decisions']={counts['decisions']!r} > scored_decisions "
                f"{data['scored_decisions']!r}: a cell's decisions cannot outnumber all scored "
                f"decisions"
            )
        if counts["distinct_battles"] > data["battles_played"]:
            raise StrengthHoldoutRunError(
                f"the {gate_name} verdict at {verdict_path!r} has "
                f"cell_counts[{cell!r}]['distinct_battles']={counts['distinct_battles']!r} > "
                f"battles_played {data['battles_played']!r}: a cell's distinct battles cannot "
                f"outnumber all battles played"
            )

    if data["safety_violations"] != 0:
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} has safety_violations "
            f"{data['safety_violations']!r}, not 0: a coverage PASS must have zero safety violations"
        )

    for cell, (min_decisions, min_battles) in COVERAGE_CELL_FLOORS.items():
        counts = cell_counts[cell]
        if counts["decisions"] < min_decisions or counts["distinct_battles"] < min_battles:
            raise StrengthHoldoutRunError(
                f"the {gate_name} verdict at {verdict_path!r} claims verdict='PASS' but cell "
                f"{cell!r} has decisions={counts['decisions']!r}/"
                f"distinct_battles={counts['distinct_battles']!r}, below its floor "
                f"({min_decisions}, {min_battles})"
            )

    if data["verdict"] != "PASS":
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} is {data['verdict']!r}, not 'PASS': "
            f"Gate B may only run after {gate_name} PASSes on the same candidate"
        )
    if data["stop_reason"] != "coverage_floor_met":
        raise StrengthHoldoutRunError(
            f"the {gate_name} verdict at {verdict_path!r} claims verdict='PASS' but stop_reason "
            f"is {data['stop_reason']!r}, not 'coverage_floor_met'"
        )
    return data


# --- Task 8: McNemar verdict rendering via the real, unmodified report.py pipeline -----------


@dataclass(frozen=True)
class GateBVerdict:
    verdict: str
    reasons: tuple
    n_discordant: int
    n_total: int
    delta: float
    exact_p: float | None
    strength_delta: float
    cell_flips: tuple


def render_strength_holdout_verdict(pairs: list[Pair], *, safety_pass: bool) -> GateBVerdict:
    """Wires already-paired battle results into the EXISTING, UNCHANGED report.py pipeline --
    the same _build_cells/_find_cell_flips/_strength_delta/_paired_verdict a live paired gate
    already uses (report.py's _generate_paired). This function does not reimplement any
    statistics or cell logic; it only builds the two per-run row lists those functions expect."""
    rows_a = [p.row_a for p in pairs]
    rows_b = [p.row_b for p in pairs]

    counts = mcnemar_counts([(p.hero_win_a, p.hero_win_b) for p in pairs])
    # exact_binom_two_sided_p already returns 1.0 for n=0 internally (stats.py) -- no separate
    # guard needed here, matching report.py._generate_paired's own unconditional call exactly.
    exact_p = exact_binom_two_sided_p(counts.n10, counts.n_discordant)

    cells_a = _build_cells(rows_a, {})  # {} = team_path_by_hash, cosmetic-display-only field
    cells_b = _build_cells(rows_b, {})
    cell_flips = _find_cell_flips(cells_a, cells_b)
    strength_delta, _n_strength, _n10_s, _n01_s = _strength_delta(pairs)

    verdict, reasons = _paired_verdict(counts, exact_p, cell_flips, strength_delta, safety_pass)

    return GateBVerdict(
        verdict=verdict, reasons=tuple(reasons), n_discordant=counts.n_discordant,
        n_total=counts.total, delta=counts.delta,
        # A SAFETY-FAIL makes no strength claim on any axis, including the p-value -- mirrors
        # report.py._build_paired_stats's own `exact_p if safety_pass else None` exactly.
        exact_p=(exact_p if safety_pass else None),
        strength_delta=strength_delta,
        cell_flips=tuple(tuple(c) for c in cell_flips),
    )


def _is_clean_safety_counter(value) -> bool:
    """True only for a genuine non-negative int that equals exactly 0. bool is explicitly
    excluded (Python's == treats False as 0, so an unguarded `!= 0` check would silently accept
    a type-wrong flag as a clean counter) -- a missing (None, via dict.get) or otherwise
    malformed value is never clean."""
    return isinstance(value, int) and not isinstance(value, bool) and value == 0


def compute_safety_pass(rows_a: list[dict], rows_b: list[dict]) -> bool:
    """Narrow, Gate-B-specific mirror of report.py's run_safety_gates core fields
    (invalid_choices==0, crashes==0, end_reason=='normal') across BOTH arms -- not the full
    RunBundle-based safety table, which needs machinery (schedule_row_count, panel hashes,
    manifest, ...) Gate B's simpler two-row-list shape does not produce. Disclosed narrowing,
    not a silent one.

    invalid_choices/crashes must be genuine non-negative ints, never bool -- a missing or
    type-wrong counter is treated as unsafe, never as passing."""
    for rows in (rows_a, rows_b):
        for row in rows:
            if not _is_clean_safety_counter(row.get("invalid_choices")):
                return False
            if not _is_clean_safety_counter(row.get("crashes")):
                return False
            if row["end_reason"] != "normal":
                return False
    return True
