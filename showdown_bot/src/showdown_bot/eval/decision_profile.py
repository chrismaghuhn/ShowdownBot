"""Decision-profile sidecar (I8-B): the per-decision cost record behind the foe-Mega
latency verdict -- never read to make a decision, off by default.

Design: docs/superpowers/specs/2026-07-16-champions-i8-latency-design.md (Rev. 11) §2.4.

What a row is, and is not
-------------------------
A row records what ONE decision cost: its measured duration at a named ``timer_scope``,
the transport it paid for, and the state the calc backend and the semantic caches were in
when it started. It is telemetry. Nothing in a decision path reads it, and no consumer may
compare rows across ``source`` or ``timer_scope`` -- a microprofile row measures a strictly
narrower boundary than a live one, so pooling them compares an end-to-end millisecond with
a sub-call millisecond (§2.5).

Two counter semantics meet here, and conflating them is the defect this module exists to
avoid. The BACKENDS count cumulatively since construction (I8-A: a backend has no concept
of a "decision", and the row's ``spawn_count_before`` is *defined* as the cumulative count
before one, so it is computable only from a cumulative counter). The ROW carries
per-decision DELTAS. Deltas are therefore taken here, by snapshotting the cumulative
counters around the measured call -- never re-counted, and never asked of a backend.

Failed transport keeps its real delta. A batch that raised still made its round trip and
still paid its latency; I8-A counts the attempt for exactly that reason, and a row that
zeroed it would contradict both the backend and the design's crash semantics, which keep a
non-ok row's counters *because* they describe transport that really happened (§2.6).

Byte contract
-------------
Mirrors eval/opp_mega_trace.py, whose contract was proven under the I7b-C smoke:
LF-only, key-sorted, compact. JSONL is an interchange format and this file is provenance;
the same decision must serialise byte-identically on Windows and on the Linux eval hosts.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os


class DecisionProfileError(ValueError):
    pass


# The exact, closed field set of design §2.4 -- 41 fields, in the design's own order.
#
# ORDER AND MEMBERSHIP ARE THE CONTRACT, so this list is kept flat and literal rather than
# assembled from fragments: it is meant to be diffable against the design's table by eye.
#
# 41, and the road here is the point. A first pass transcribed 39: it read the design's
# table one row at a time and took the first backticked name in each, but ONE row declares
# THREE fields --
#     | `config_id`, `format_id`, `git_sha` | str | provenance, same values as the siblings |
# -- so `format_id` and `git_sha` vanished silently. The test that was supposed to catch
# that parsed the table with the SAME assumption and therefore certified the wrong answer.
# This is the design's own §9 failure mode (entries 25, 30, 31, 36) reproduced twice over,
# in the code and in its guard. The drift test now extracts EVERY name per cell.
PROFILE_ROW_FIELDS: tuple[str, ...] = (
    # identity / provenance
    "schema_version",
    "source",
    "battle_id",
    "decision_index",
    "arm_id",
    "rep",
    "config_id",
    "format_id",
    "git_sha",
    "config_hash",
    "schedule_hash",
    "profile_manifest_hash",
    # backend + cache state at the start of the decision
    "calc_backend",
    "backend_class",
    "cache_class",
    "damage_cache_size_at_rep_start",
    "speed_cache_size_at_rep_start",
    "dex_cache_size_at_rep_start",
    "spawn_count_before",
    "transport_retried",
    # the measurement
    "timer_scope",
    "measured_ms",
    # transport, as per-decision deltas
    "damage_batch_calls",
    "planned_damage_batches",
    "implicit_damage_batches",
    "stats_batch_calls",
    "types_batch_calls",
    "transport_calls",
    "transport_attempts",
    "spawn_calls",
    "requests_total",
    "requests_unique",
    "cache_hits",
    # shape of the work
    "n_candidates",
    "n_responses",
    "n_mega_twins",
    "n_branches",
    "n_worlds",
    "depth2_frontier",
    "foe_mega_active",
    "outcome",
)

_FIELD_SET = frozenset(PROFILE_ROW_FIELDS)

# Classified NON_BEHAVIORAL in eval/config_env.py, and that REGISTRATION is what makes the
# claim true -- not this comment. config_env.is_excluded fails closed toward INCLUSION, so
# an unclassified SHOWDOWN_* var lands in behavior_env and therefore in config_hash: an
# unregistered sink path would silently change the run's identity the moment the sidecar
# was switched on, and a microprofile row's config_hash could never match its arm's
# effective_config_hash. This is an IO path with no /choose effect -- unlike
# SHOWDOWN_OPP_MEGA_CLICK_RATE, which is BEHAVIOR_AFFECTING and must never be confused
# with one.
PROFILE_OUT_ENV = "SHOWDOWN_DECISION_PROFILE_OUT"


def validate_profile_row_fields(row: dict) -> None:
    """Exact-closed field check: every field present, nothing extra.

    B1's half of the row contract. The semantic invariants on top of it (the
    backend_class predicate, the cache rules, source/timer_scope compatibility) are
    B2's ``validate_decision_profile_row``.

    Exact-closed rather than merely "required": an unknown key means the writer and the
    reader disagree about the schema, which is how a sidecar silently grows a field that
    nothing validates and every consumer guesses at.
    """
    missing = _FIELD_SET - set(row)
    unknown = set(row) - _FIELD_SET
    if missing or unknown:
        raise DecisionProfileError(
            f"decision-profile row fields missing={sorted(missing)} unknown={sorted(unknown)}"
        )


_COUNTER_FIELDS = (
    "damage_batch_calls",
    "planned_damage_batches",
    "implicit_damage_batches",
    "stats_batch_calls",
    "types_batch_calls",
    "transport_calls",
    "transport_attempts",
    "spawn_calls",
    "requests_total",
    "requests_unique",
    "cache_hits",
    "spawn_count_before",
    "n_candidates",
    "n_responses",
    "n_mega_twins",
    "n_branches",
    "n_worlds",
    "depth2_frontier",
)

_CACHE_FIELDS = (
    "cache_class",
    "damage_cache_size_at_rep_start",
    "speed_cache_size_at_rep_start",
    "dex_cache_size_at_rep_start",
)

_SIZE_FIELDS = _CACHE_FIELDS[1:]

_MICRO_SCOPES = frozenset({"contexts_and_score", "score_evaluated_variants"})

# Every enumerated value design §2.4's field table pins. Unenumerated is unvalidated: a row
# whose `outcome` reads "banana", or whose `schema_version` is the integer 1, would
# otherwise satisfy every arithmetic rule and still be meaningless.
#
# There is deliberately NO cache_class enum here. It would be dead: expected_cache_class
# returns only "cold" or "warm", so the equality rule below already constrains the domain,
# and a check that can never fire is a check that misleads the next reader into thinking
# something is guarded. (An enum was written, and mutation testing showed no test could
# distinguish its presence from its absence -- which is the definition of dead.)
SCHEMA_VERSION = "decision-profile-v1"
_SOURCES = frozenset({"live", "microprofile"})
_BACKENDS = frozenset({"oneshot", "persistent"})
_OUTCOMES = frozenset({"ok", "crash", "fallback", "degraded_state"})

# Provenance a row always carries, whatever its source.
_ALWAYS_SET = ("config_id", "format_id", "git_sha", "config_hash")


def profile_manifest_hash(manifest: dict) -> str:
    """The manifest's canonical hash, COMPUTED from the manifest (§2.7).

    A manifest must not contain its own hash. A document carrying a digest of itself
    cannot be hashed consistently: the field would be an input to the digest that depends
    on the digest. So the hash is derived here and never read back out of the manifest,
    and a row's ``profile_manifest_hash`` is checked against THIS rather than against a
    field in which the manifest asserts its own identity.

    The design's serialiser: ``encode`` has already fixed all ordering, so ``sort_keys``
    is deliberately NOT used -- it would re-sort nothing and must not be relied on to.
    """
    return _sha1_16(encode(manifest))


def fixture_input_hash(inputs: dict) -> str:
    """The fixture-bound scoring inputs' canonical hash (§2.7, group A).

    THE SAME ``encode`` as the manifest hash, deliberately. Two canonicalisations would be
    free to disagree about the one question both exist to answer -- are these inputs the
    same inputs -- and the design's §9 is largely a record of two descriptions of one thing
    drifting apart.
    """
    return _sha1_16(encode(inputs))


def group_a_fixture_dto(
    *, req, state, my_actions, book, our_spreads, opp_sets, calc_profile, our_side, opp_side
) -> dict:
    """The COMPLETE §2.7 group-A input set -- every input that determines V (n_candidates) and
    the scoring -- assembled for :func:`fixture_input_hash`.

    It binds the **request**, the full **state** (both sides AND the field), the action
    **order**, the **book**, **our_spreads**, **opp_sets**, the **calc_profile** and the side
    labels. Crucially it does NOT hand-pick fields: it hands the RAW objects to ``encode``,
    which serialises each one completely -- a dataclass by every one of its fields (name-
    sorted, recursed), a pydantic model by ``model_dump`` -- so a change to any move, spread,
    item, nature, EV or field flips the hash automatically, and a field added to any of these
    types later is picked up without editing here.

    This is the fix for a reduced descriptor that enumerated only a board slice (species/item
    per slot). That descriptor omitted moves, spreads and most of the request, so two
    genuinely different boards could share a hash -- which silently defeats the dataset
    fixture-identity check (identical ``fixture_input_hash`` is supposed to GUARANTEE identical
    ``n_candidates``). Under-binding here is the one failure mode §2.7 cannot tolerate, so the
    builder binds the whole input and lets ``encode`` be exhaustive.

    The action ORDER is the one input NOT handed raw: each action is bound by
    ``joint_action_key_v2`` -- the SAME canonical identity the scoring path stamps onto
    ``candidate_key`` (``mega_scoring.py``). Re-encoding a ``JointAction``'s dataclass fields
    here would be a second action-identity recipe free to disagree with the canonical one
    (its v2 schema deliberately overlays the mega/tera flags), which is exactly the "two
    canonicalisations drift" defect §2.7 exists to prevent.
    """
    from showdown_bot.battle.candidate_identity import joint_action_key_v2

    return {
        "our_side": our_side,
        "opp_side": opp_side,
        "request": req,
        "state": state,
        # canonical per-action key, order preserved (the first-wins tie-break) -- NOT a raw
        # re-encoding of the action internals, which would be a second identity recipe.
        "action_order": [joint_action_key_v2(j) for j in my_actions],
        "book": book,
        "our_spreads": our_spreads,
        "opp_sets": opp_sets,
        "calc_profile": calc_profile,
    }


def _sha1_16(encoded) -> str:
    # `encode` has already fixed all ordering, so sort_keys is deliberately NOT used: it
    # would re-sort nothing and must not be relied on to.
    payload = json.dumps(encoded, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def encode(value):
    """Design §2.7's recursive encoder. ONE canonicalisation, for every hash in this slice.

    **Sort only what has no order.** That rule is not stylistic: it is the correction to a
    defect the design shipped and withdrew (§9 entries 33-37). Sorting looked canonical and
    was catastrophic for lists -- `items[0]` is the default assumption
    (`default_spreads.yaml:12`, read at `hypotheses.py:109` and `team/spreads.py:91`), and
    `legal_actions` order is the first-wins tie-break (`mega_scoring.py:184-198`). Sorting
    either one maps two genuinely different fixtures onto one hash.

      set/frozenset -> sorted     (no order exists; sorting is the only deterministic form)
      list/tuple    -> preserved  (order is meaningful, or at minimum not ours to discard)
      dict          -> key-sorted (a keyed lookup; key order carries nothing)
      dataclass     -> fields name-sorted, recursed
      BaseModel     -> model_dump with PINNED options, recursed
      scalars       -> verbatim; float -> repr at full precision; None -> null, never elided
      anything else -> raise

    The asymmetry that licenses it: for a fixture IDENTITY, over-discrimination costs a
    comparison, while under-discrimination corrupts every claim built on it. So the encoder
    errs toward splitting, and fails closed on an unhandled TYPE -- a closed, checkable set
    -- rather than on a field name someone forgot to list.
    """
    # bool BEFORE int: bool is a subclass of int and would otherwise encode as 0/1.
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, dict):
        return {str(k): encode(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (set, frozenset)):
        return sorted(encode(v) for v in value)
    if isinstance(value, (list, tuple)):
        return [encode(v) for v in value]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        # EVERY field, enumerated from the dataclass -- never a hand-written list. Rev. 5
        # hand-listed inputs and missed eight; Rev. 6 hand-listed preset fields and missed
        # `items`. A field added later is picked up here automatically.
        return {
            f.name: encode(getattr(value, f.name))
            for f in sorted(dataclasses.fields(value), key=lambda f: f.name)
        }
    dumped = _model_dump(value)
    if dumped is not None:
        return encode(dumped)
    raise DecisionProfileError(f"cannot encode a {type(value).__name__}: no rule for this type")


def _model_dump(value):
    """A pydantic model's dict, with every option pinned, or ``None`` if not a model.

    `BattleRequest` is a pydantic BaseModel, not a dataclass, so without this branch the
    encoder would fail closed on the very input §2.7 names (§9 entry 40).

    The options are pinned because they change the bytes: `by_alias` demonstrably alters
    the keys (`forceSwitch` vs `force_switch`), and the three `exclude_*` flags stay False
    for the same reason `None` is never elided -- an omitted field is not an absent input,
    it is a defaulted one.
    """
    dump = getattr(value, "model_dump", None)
    if dump is None or isinstance(value, type):
        return None
    return dump(
        mode="python",
        by_alias=True,
        exclude_unset=False,
        exclude_defaults=False,
        exclude_none=False,
    )


def backend_class_of(
    calc_backend: str, spawn_count_before: int, spawn_calls: int, transport_retried: bool
) -> str:
    """§5.5's predicate. A PREDICATE WITH A RESIDUAL, not an enum -- and that is the point.

    Design revisions 4, 5 and 6 each hand-enumerated backend states and each missed a
    reachable cell (§9 entries 23, 27, 51): a cold start that retries, a process revived
    between decisions with no retry, a process revived mid-decision with no retry. Every
    miss classified a real, successful row as impossible.

    So `contaminated` is defined as the NEGATION of the two clean cases. Every combination
    of the three facts lands somewhere, including cells nobody has thought of yet.
    """
    if calc_backend == "oneshot":
        return "oneshot"
    if spawn_count_before == 0 and spawn_calls == 1 and not transport_retried:
        return "clean_cold"
    if spawn_count_before >= 1 and spawn_calls == 0 and not transport_retried:
        return "clean_warm"
    return "contaminated"


# --------------------------------------------------------------------------
# The profile manifest's contract: ONE definition, here, beside the validator that
# enforces it. eval/profile_manifest.py (the producer) imports these rather than keeping
# its own copy -- a second, independently-written field list is exactly the drift the
# design's §9 records over and over. The dependency runs producer -> here, so there is no
# cycle.
# --------------------------------------------------------------------------

PROFILE_MANIFEST_SCHEMA_VERSION = "profile-manifest-v1"

# Design §2.7's run-level table, exactly. `arms` is a LIST (Erratum 1), and there is
# deliberately NO run-level `warmup`: it is per-arm, and a second one here would be a
# second truth about the same quantity.
MANIFEST_RUN_FIELDS: tuple[str, ...] = (
    "schema_version",
    "git_sha",
    "dirty",
    "calc_pin_hash",
    "format_id",
    "format_config_hash",
    "speciesdata_hash",
    "itemdata_hash",
    "movedata_hash",
    "arms",
)

# Design §2.7's arm-entry table, exactly. `timer_scope` is pinned per arm (C3-fix): an arm
# is measured at exactly one microprofile scope, so the manifest must record it and the row
# validator must check every row against it -- otherwise the harness could carry a second,
# independent scope truth that the frozen evidence never cross-checks (§2.5).
MANIFEST_ARM_FIELDS: tuple[str, ...] = (
    "arm_id",
    "effective_config_hash",
    "behavior_env",
    "arm_params",
    "scoring_params",
    "fixture_input_hash",
    "reps",
    "warmup",
    "lifecycle",
    "timer_scope",
)

# Provenance that must actually pin something. `None` is what file_content_hash returns
# when it cannot read a file, and what config_provenance_for_format returns for a missing
# format yaml -- a manifest recording "I could not pin this" is not an anchor.
_MANIFEST_PROVENANCE_FIELDS = (
    "git_sha",
    "calc_pin_hash",
    "format_id",
    "format_config_hash",
    "speciesdata_hash",
    "itemdata_hash",
    "movedata_hash",
)

# learning.provenance.git_sha_and_dirty() returns ("unknown", False) when git is
# unavailable -- a sentinel, never None -- so "unknown" is a perfectly good non-empty str
# and passes every generic check above. The PROFILE contract is deliberately stricter than
# that repo-wide helper: a manifest that cannot name the commit does not bind the code its
# arms ran against, so its measurements are attributable to no version of anything. The
# helper may keep returning the sentinel and other artifacts may keep accepting it; a
# git-less environment may run tests. It may not produce I8 evidence.
_UNKNOWN_GIT_SHA = "unknown"


def validate_profile_manifest(manifest: dict) -> dict[str, dict]:
    """Validate the WHOLE manifest, then return an ``arm_id`` -> entry index.

    Design §2.7 + Erratum 1. The design calls the manifest content **exact** and the
    manifest itself the microprofile's **provenance anchor**, so this checks the complete
    contract -- not just the arms. An earlier cut validated only ``arms``, which meant a
    hand-written manifest with no ``git_sha``, no ``calc_pin_hash`` and no data hashes
    validated rows and datasets happily. An anchor that pins nothing is not an anchor, and
    B2/B3 reach a manifest through this function alone.

    Order is the contract, twice over:

      1. the top level first -- nothing below the anchor is worth judging without it;
      2. then the arms list **in full**, and only then the index. An implementation that
         indexed as it went would have to decide what a duplicate means before anything
         had judged it, and would already have dropped the first entry by the time it
         noticed.

    ``arms`` is a LIST with ``arm_id`` as a field of each entry, not a mapping keyed by it.
    That is not a style choice. A mapping **cannot represent** a duplicate ``arm_id``:
    ``{a["arm_id"]: a for a in arms}`` silently drops one at construction, so the duplicate
    never reaches the frozen artifact and can only ever be caught by trusting the producer.
    The dataset tier already rests on the opposite principle -- frozen evidence must not
    blindly trust the writer that made it.
    """
    _require(isinstance(manifest, dict), f"manifest must be a dict, got {type(manifest).__name__}")

    # ---- the anchor itself ------------------------------------------------
    missing = [f for f in MANIFEST_RUN_FIELDS if f not in manifest]
    unknown = [f for f in manifest if f not in MANIFEST_RUN_FIELDS]
    if missing or unknown:
        # Erratum 1's run-level `warmup` lands here as an unknown field, which is the
        # right answer: it is not part of the contract. The dedicated message below
        # explains the *why* for a manifest that is otherwise well-formed.
        raise DecisionProfileError(
            f"profile manifest fields missing={sorted(missing)} unknown={sorted(unknown)}"
            + (
                " -- 'warmup' is a PER-ARM field (Erratum 1); a run-level one would be a "
                "second truth about the same quantity"
                if "warmup" in unknown
                else ""
            )
        )
    _require(
        manifest["schema_version"] == PROFILE_MANIFEST_SCHEMA_VERSION,
        f"schema_version must be {PROFILE_MANIFEST_SCHEMA_VERSION!r}, "
        f"got {manifest['schema_version']!r}",
    )
    for name in _MANIFEST_PROVENANCE_FIELDS:
        value = manifest[name]
        _require(
            isinstance(value, str) and value != "",
            f"{name} must be a non-empty str to pin anything, got {value!r}",
        )
    _require(
        manifest["git_sha"] != _UNKNOWN_GIT_SHA,
        f"git_sha is {_UNKNOWN_GIT_SHA!r}: a manifest that cannot name the commit does not "
        f"bind the code its arms ran against, so it is not a provenance anchor. A git-less "
        f"environment may run tests; it may not produce I8 evidence",
    )
    _require(
        isinstance(manifest["dirty"], bool),
        f"dirty must be a bool, got {manifest['dirty']!r}",
    )

    arms = manifest.get("arms")
    _require(
        isinstance(arms, list),
        f"manifest 'arms' must be a list of arm entries, got {type(arms).__name__}: a mapping "
        f"keyed by arm_id cannot represent a duplicate arm_id (§2.7, Erratum 1)",
    )
    _require(arms, "manifest declares no arms")

    index: dict[str, dict] = {}
    for position, arm in enumerate(arms):
        where = f"arms[{position}]"
        _require(isinstance(arm, dict), f"{where} must be a dict, got {type(arm).__name__}")

        arm_id = arm.get("arm_id")
        _require(
            isinstance(arm_id, str) and arm_id,
            f"{where} has no usable arm_id: {arm_id!r}",
        )
        _require(
            arm_id not in index,
            f"{where}: duplicate arm_id {arm_id!r}; two arms cannot claim one identity",
        )

        arm_missing = [f for f in MANIFEST_ARM_FIELDS if f not in arm]
        arm_unknown = [f for f in arm if f not in MANIFEST_ARM_FIELDS]
        if arm_missing or arm_unknown:
            raise DecisionProfileError(
                f"{where} ({arm_id!r}) fields "
                f"missing={sorted(arm_missing)} unknown={sorted(arm_unknown)}"
            )

        warmup = arm.get("warmup")
        _require(
            isinstance(warmup, int) and not isinstance(warmup, bool) and warmup >= 0,
            f"{where} ({arm_id!r}) must declare a non-negative int warmup, got {warmup!r}",
        )
        # Raises on a mixed declaration, which is what keeps expected_cache_class total
        # without inventing a `mixed` class (§9 entries 27-30).
        cache = cache_lifecycle_of(arm)
        _require(
            not (cache == "per_rep" and warmup >= 1),
            f"{where} ({arm_id!r}) declares per_rep caches and warmup={warmup}: a cold-cache "
            f"arm that warms up is a contradiction, because its caches are discarded anyway "
            f"(§2.8)",
        )

        scope = arm.get("timer_scope")
        _require(
            scope in _MICRO_SCOPES,
            f"{where} ({arm_id!r}) has timer_scope {scope!r}; a microprofile arm must declare "
            f"one of {sorted(_MICRO_SCOPES)} (§2.5). agent_choose is live-only",
        )

        index[arm_id] = arm

    return index


def arm_by_id(manifest: dict, arm_id: str) -> dict:
    """The ONE way to reach an arm. Validates the whole manifest, then resolves.

    Central by design: a call site that scanned for itself would resolve against a manifest
    nobody had judged, so a duplicate elsewhere in the list would pass unnoticed for every
    row that did not happen to name it.
    """
    index = validate_profile_manifest(manifest)
    arm = index.get(arm_id)
    _require(
        arm is not None,
        f"unknown arm_id {arm_id!r}: the manifest declares {sorted(index)}",
    )
    return arm


def cache_lifecycle_of(arm: dict) -> str:
    """The one lifecycle shared by the three semantic caches.

    §2.8 requires them to agree. That constraint is what keeps ``expected_cache_class``
    total without inventing a `mixed` class -- the enumeration reflex that produced §9
    entries 27-30. It forbids nothing legitimate: both coherent configurations (cold-cache:
    all per_rep; warm-cache: all per_arm) already declare the three identically.
    """
    lifecycle = arm.get("lifecycle") or {}
    declared = {lifecycle.get(k) for k in ("damage_oracle", "speed_oracle", "species_dex")}
    if len(declared) != 1 or declared == {None}:
        raise DecisionProfileError(
            f"manifest arm declares disagreeing cache lifecycles: {sorted(map(str, declared))}; "
            f"damage_oracle/speed_oracle/species_dex must share one (§2.8)"
        )
    return declared.pop()


def expected_cache_class(arm: dict, rep: int) -> str:
    """Derived from the arm's DECLARED lifecycle. Total by construction.

    `rep` is 0-BASED (§2.4), so rep 0 is the first TIMED repetition. Rev. 10 branched on
    `rep > 1` / `rep == 1` and thereby left rep 0 matching no branch at all while calling
    the genuinely warm rep 1 "cold" -- in the same paragraph that claimed exhaustiveness
    (§9 entry 50). The third branch here is a RESIDUAL rather than a third condition, so
    the function cannot have a hole.
    """
    if cache_lifecycle_of(arm) == "per_rep":
        return "cold"
    if int(arm.get("warmup", 0)) == 0 and rep == 0:
        return "cold"
    return "warm"


def _require(cond: bool, message: str) -> None:
    if not cond:
        raise DecisionProfileError(message)


def validate_decision_profile_row(row: dict, *, manifest: dict | None) -> None:
    """Design §2.4's per-row validator, rule for rule.

    The validator RECOMPUTES every derived label rather than trusting the writer, so a
    mislabelled row fails instead of quietly skewing a contrast.
    """
    validate_profile_row_fields(row)

    # ---- enumerated values and types ------------------------------------
    # Structural completeness is not validity: every field below was present and the row
    # was still nonsense. An unenumerated string field is an unvalidated one.
    _require(
        row["schema_version"] == SCHEMA_VERSION,
        f"schema_version must be {SCHEMA_VERSION!r}, got {row['schema_version']!r}",
    )
    source = row["source"]
    _require(source in _SOURCES, f"unknown source {source!r}")
    _require(row["outcome"] in _OUTCOMES, f"unknown outcome {row['outcome']!r}")
    _require(
        row["calc_backend"] in _BACKENDS, f"unknown calc_backend {row['calc_backend']!r}"
    )

    for field in _ALWAYS_SET:
        _require(
            isinstance(row[field], str) and row[field] != "",
            f"{field} must be a non-empty str, got {row[field]!r}",
        )

    for field in ("transport_retried", "foe_mega_active"):
        _require(isinstance(row[field], bool), f"{field} must be a bool, got {row[field]!r}")

    measured = row["measured_ms"]
    _require(
        measured is None or (isinstance(measured, float) and measured >= 0.0),
        f"measured_ms must be a non-negative float or null, got {measured!r}",
    )

    # ---- counters -------------------------------------------------------
    for name in _COUNTER_FIELDS:
        value = row[name]
        _require(
            isinstance(value, int) and not isinstance(value, bool) and value >= 0,
            f"{name} must be a non-negative int, got {value!r}",
        )

    _require(
        row["damage_batch_calls"]
        == row["planned_damage_batches"] + row["implicit_damage_batches"],
        "damage_batch_calls != planned + implicit",
    )
    _require(
        row["transport_calls"]
        == row["damage_batch_calls"] + row["stats_batch_calls"] + row["types_batch_calls"],
        "transport_calls != damage + stats + types",
    )
    # A retry adds attempts, never calls.
    _require(
        row["transport_attempts"] >= row["transport_calls"],
        "transport_attempts < transport_calls",
    )
    _require(row["requests_unique"] <= row["requests_total"], "requests_unique > requests_total")
    _require(
        not (row["n_mega_twins"] > 0 and not row["foe_mega_active"]),
        "n_mega_twins > 0 but foe_mega_active is false",
    )

    # ---- outcome <-> measured_ms (§2.6) ---------------------------------
    # A crashed decision's wall clock is the crash handler, not decision work; recording
    # it as a latency would be a false datum. Its COUNTERS stay, because they describe
    # transport that really happened.
    _require(
        (row["outcome"] == "ok") == (row["measured_ms"] is not None),
        "outcome == 'ok' must be equivalent to measured_ms being set",
    )

    # ---- transport_retried: the ONLY definition (§5.5) -------------------
    # It is a statement about FAILED ATTEMPTS, never about spawns: `_ensure` revives a
    # dead process before the first attempt with no failure at all.
    _require(
        row["transport_retried"] == (row["transport_attempts"] > row["transport_calls"]),
        "transport_retried must equal (transport_attempts > transport_calls)",
    )

    # ---- backend_class is recomputed (§5.5) -----------------------------
    if row["calc_backend"] == "oneshot":
        _require(
            row["spawn_calls"] == row["transport_attempts"],
            "oneshot spawns exactly once per attempt",
        )
    _require(
        row["backend_class"]
        == backend_class_of(
            row["calc_backend"],
            row["spawn_count_before"],
            row["spawn_calls"],
            row["transport_retried"],
        ),
        f"backend_class {row['backend_class']!r} contradicts the row's own facts",
    )

    # ---- source <-> timer_scope is a CONTRACT (§2.5) --------------------
    # A live row measures agent_choose end-to-end; a microprofile row measures a strictly
    # narrower boundary. Pooling them compares an end-to-end ms with a sub-call ms.
    scope = row["timer_scope"]
    if source == "live":
        _require(scope == "agent_choose", f"live row at timer_scope {scope!r}")
    else:
        _require(scope in _MICRO_SCOPES, f"microprofile row at timer_scope {scope!r}")

    # ---- identity ------------------------------------------------------
    if source == "live":
        for field in ("battle_id", "decision_index", "schedule_hash"):
            _require(row[field] is not None, f"live row missing {field}")
        for field in ("arm_id", "rep", "profile_manifest_hash"):
            _require(row[field] is None, f"live row carries microprofile identity {field}")
    else:
        for field in ("arm_id", "rep", "profile_manifest_hash"):
            _require(row[field] is not None, f"microprofile row missing {field}")
        for field in ("battle_id", "decision_index", "schedule_hash"):
            _require(row[field] is None, f"microprofile row carries live identity {field}")

    # ---- the cache contract is a MICROPROFILE concept (§2.8) ------------
    # It is defined against an arm's declared lifecycle, and a live row has no arm, no rep
    # and no manifest. Rev. 10 wrote these rules unqualified, so NO live row could satisfy
    # them: there was no arm to resolve against, and the sizes were null (§9 entry 49).
    if source == "live":
        for field in _CACHE_FIELDS:
            _require(row[field] is None, f"live row carries cache field {field}")
        return

    _require(manifest is not None, "a microprofile row cannot be validated without its manifest")
    # COMPUTED, never read out of the manifest: a manifest that stated its own hash would
    # be asserting its identity rather than having one, and could not be hashed at all.
    _require(
        row["profile_manifest_hash"] == profile_manifest_hash(manifest),
        "profile_manifest_hash does not identify the supplied manifest",
    )
    # ONE lookup helper: it validates the whole arms list before resolving, so a duplicate
    # arm_id elsewhere in the manifest cannot pass unnoticed just because this row named a
    # different arm. An unknown arm_id raises here.
    arm = arm_by_id(manifest, row["arm_id"])
    _require(
        row["config_hash"] == arm.get("effective_config_hash"),
        "config_hash does not match this arm's effective_config_hash",
    )
    # timer_scope is pinned per arm (§2.5, C3-fix): a row measured at a different scope than
    # its arm declares is a category error the harness must not be free to introduce -- there
    # is one scope per arm, recorded in the manifest, and every row is checked against it.
    _require(
        row["timer_scope"] == arm.get("timer_scope"),
        f"timer_scope {row['timer_scope']!r} does not match arm {row['arm_id']!r}'s declared "
        f"{arm.get('timer_scope')!r}: the row was measured at a scope the manifest did not pin",
    )

    for field in _SIZE_FIELDS:
        value = row[field]
        _require(
            isinstance(value, int) and not isinstance(value, bool) and value >= 0,
            f"{field} must be a non-negative int on a microprofile row, got {value!r}",
        )

    _require(
        row["cache_class"] == expected_cache_class(arm, row["rep"]),
        f"cache_class {row['cache_class']!r} contradicts the arm's declared lifecycle",
    )

    # The SOUND direction only. A freshly constructed cache is provably empty
    # (oracle.py:24, speed.py:103, opponent.py:45), so a non-empty one at rep start
    # disproves the declared lifecycle -- catching a HARNESS that reused an object the
    # manifest called fresh, which manifest-equality alone cannot.
    if row["cache_class"] == "cold":
        _require(
            all(row[f] == 0 for f in _SIZE_FIELDS),
            "cache_class == 'cold' but a cache was already populated at rep start",
        )
    else:
        # The CONVERSE is unsound and deliberately NOT asserted: a reused SpeciesDex on a
        # board whose species were never looked up is legitimately empty. Rev. 5 shipped
        # exactly that over-strict shape and would have rejected a real row (§9 entry 23).
        _require(
            row["rep"] >= 1 or int(arm.get("warmup", 0)) >= 1,
            "cache_class == 'warm' on the first rep with no warmup: nothing ran before it",
        )


def validate_decision_profile_dataset(path: str, manifest: dict) -> dict:
    """Design §2.4's dataset tier. Runs ONCE over a finished sidecar, **before any row is
    read as evidence**, and FAILS THE RUN rather than annotating it.

    Every rule is an exact predicate. The design's prose called for comparing an arm's
    observed ``backend_class`` *distribution* against its declared lifecycle -- "a per_arm
    arm whose rows are predominantly clean_cold". "Predominantly" is not a rule: no
    threshold, no direction, nothing a function can return False from. It is replaced by an
    accounting IDENTITY that is deterministic and strictly stronger (see ``_check_arm``).

    Returns a report. Contaminated rows are **excluded from contrasts and counted**, never
    silently dropped and never rejected: they describe real, successful decisions whose
    backend state simply cannot enter a cold/warm comparison (§5.5).
    """
    rows = _read_rows(path)
    _require(rows, f"{path} has no rows: a run that produced no evidence is not a clean run")

    by_arm: dict[str, dict[int, dict]] = {}
    for index, row in enumerate(rows):
        # A file on disk is not a trusted writer: it may have been hand-edited, truncated
        # or concatenated since its rows were validated on write.
        try:
            validate_decision_profile_row(row, manifest=manifest)
        except DecisionProfileError as exc:
            raise DecisionProfileError(f"{path} row {index}: {exc}") from exc
        _require(
            row["source"] == "microprofile",
            f"{path} row {index}: a microprofile dataset may not contain a "
            f"{row['source']!r} row; the two sources measure different boundaries (§2.5)",
        )
        reps = by_arm.setdefault(row["arm_id"], {})
        _require(
            row["rep"] not in reps,
            f"{path} row {index}: duplicate rep {row['rep']} for arm {row['arm_id']!r}",
        )
        reps[row["rep"]] = row

    report: dict = {
        "rows": len(rows),
        "arms": {},
        "backend_class_counts": {},
        "excluded_from_contrast": 0,
    }
    for arm_id, reps in sorted(by_arm.items()):
        ordered = [reps[k] for k in sorted(reps)]
        _check_arm(arm_id, arm_by_id(manifest, arm_id), ordered)
        report["arms"][arm_id] = {"reps": len(ordered)}
        for row in ordered:
            klass = row["backend_class"]
            report["backend_class_counts"][klass] = report["backend_class_counts"].get(klass, 0) + 1
            if klass not in ("clean_cold", "clean_warm"):
                report["excluded_from_contrast"] += 1

    _check_fixture_identity(by_arm, manifest)
    return report


def _read_rows(path: str) -> list[dict]:
    rows: list[dict] = []
    with open(path, encoding="utf-8") as fh:
        for index, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise DecisionProfileError(
                    f"{path} line {index + 1} is not JSON: {exc}"
                ) from exc
    return rows


def _check_arm(arm_id: str, arm: dict, ordered: list[dict]) -> None:
    """The backend and cache lifecycle identities, over one arm's reps in rep order."""
    backend_lifecycle = (arm.get("lifecycle") or {}).get("calc_backend")
    warmup = int(arm.get("warmup", 0))

    if backend_lifecycle == "per_rep":
        # A fresh object every rep, so its cumulative count is 0 at every rep start.
        for row in ordered:
            _require(
                row["spawn_count_before"] == 0,
                f"arm {arm_id!r} declares calc_backend per_rep, but rep {row['rep']} starts "
                f"with spawn_count_before={row['spawn_count_before']}: the backend was reused",
            )
    else:
        # ONE object across the arm, so spawn_count never resets and accumulates exactly.
        # The identity holds THROUGH a respawn, which only adds to spawn_calls -- which is
        # why it is an identity and not a distribution. §9 entries 23 and 51 record two
        # revisions that rejected a real, successful respawn row.
        if warmup >= 1:
            _require(
                ordered[0]["spawn_count_before"] >= 1,
                f"arm {arm_id!r} declares warmup={warmup} with calc_backend per_arm, but its "
                f"first timed rep starts with spawn_count_before=0: nothing ran before it",
            )
        for prev, nxt in zip(ordered, ordered[1:]):
            expected = prev["spawn_count_before"] + prev["spawn_calls"]
            _require(
                nxt["spawn_count_before"] == expected,
                f"arm {arm_id!r} declares calc_backend per_arm, but spawn_count_before is "
                f"{nxt['spawn_count_before']} at rep {nxt['rep']} where the identity requires "
                f"{prev['spawn_count_before']}+{prev['spawn_calls']}={expected}: "
                f"the backend was rebuilt",
            )

    if cache_lifecycle_of(arm) == "per_rep":
        for row in ordered:
            for field in _SIZE_FIELDS:
                _require(
                    row[field] == 0,
                    f"arm {arm_id!r} declares per_rep caches, but rep {row['rep']} starts "
                    f"with {field}={row[field]}",
                )
    else:
        # The three caches are never cleared or evicted (design F-14), so a reused object's
        # size at rep start can only grow. A shrink means it was not the same object.
        for prev, nxt in zip(ordered, ordered[1:]):
            for field in _SIZE_FIELDS:
                _require(
                    nxt[field] >= prev[field],
                    f"arm {arm_id!r} declares per_arm caches, but {field} shrank from "
                    f"{prev[field]} to {nxt[field]} at rep {nxt['rep']}: the cache was rebuilt",
                )


def _check_fixture_identity(by_arm: dict[str, dict[int, dict]], manifest: dict) -> None:
    """Identical ``fixture_input_hash`` => identical ``n_candidates`` (§2.7).

    V is determined by the group-A inputs the fixture hash binds, so rows of one fixture
    cannot legitimately disagree about it. When they do, the hash bound FEWER inputs than
    the scoring path consumed. The grouping key is the ARM's fixture hash rather than the
    arm id, because two arms differing only in call-bound scoring_params share a fixture.
    """
    seen: dict[str, tuple[int, str]] = {}
    for arm_id, reps in sorted(by_arm.items()):
        fixture = arm_by_id(manifest, arm_id).get("fixture_input_hash")
        if fixture is None:
            continue
        for rep in sorted(reps):
            n = reps[rep]["n_candidates"]
            if fixture not in seen:
                seen[fixture] = (n, f"{arm_id} rep {rep}")
                continue
            expected, where = seen[fixture]
            _require(
                n == expected,
                f"fixture {fixture!r} yields n_candidates={expected} at {where} but {n} at "
                f"{arm_id} rep {rep}: the fixture hash binds fewer inputs than the scoring "
                f"path consumed",
            )


class DecisionProfileWriter:
    """One run-scoped writer; every row appends to the same file.

    ``manifest`` is the profile manifest for a microprofile run, and ``None`` for a live
    run (a live row has no arm and no manifest to resolve against). It is held here rather
    than passed per row because it is a property of the RUN, and because a per-call
    manifest could differ between two rows of one file.
    """

    def __init__(self, path: str, *, manifest: dict | None = None) -> None:
        self.path = path
        self.manifest = manifest

    def write(self, row: dict) -> None:
        # The FULL per-row validator, at every write, inside the writer -- not merely the
        # field check. The design makes this the per-row tier's contract: an invalid row
        # raises and is never emitted. A writer that checked only the field set would
        # leave every semantic rule in validate_decision_profile_row enforced by nobody
        # at write time -- the same defect as a validation tier nobody invokes (§9 e52).
        validate_decision_profile_row(row, manifest=self.manifest)
        # sort_keys + compact separators: the sidecar is provenance, so the same decision
        # must serialise byte-identically regardless of dict insertion order or platform.
        #
        # newline="" disables the platform newline translation text mode applies on write:
        # without it every "\n" below lands on disk as "\r\n" under Windows, so the SAME
        # decision produces different bytes -- and a different digest -- than it does on
        # the Linux eval hosts. Reading such a file back in text mode HIDES this, since
        # universal newlines translate "\r\n" back to "\n", which is why the tests assert
        # on raw bytes. (I7b-C shipped a "determinism" test that passed for exactly this
        # reason on the platform that was producing CRLF.)
        with open(self.path, "a", encoding="utf-8", newline="") as fh:
            fh.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def writer_from_env(
    env: dict | None = None, *, manifest: dict | None = None
) -> DecisionProfileWriter | None:
    """The sidecar's only switch. Unset or empty -> ``None``, and nothing is created.

    Off by default is not a convenience: with the var unset this module has no effect on
    any run, so enabling the profile can never be the thing that changed a result.
    """
    env = os.environ if env is None else env
    out = env.get(PROFILE_OUT_ENV, "")
    if not out:
        return None
    # Fail closed on a non-empty existing file, the same rule the opp-mega sidecar uses:
    # appending onto an earlier run's rows interleaves two runs into one file that later
    # reads as a single run. This file is provenance; it must never silently mix.
    if os.path.exists(out) and os.path.getsize(out) > 0:
        raise DecisionProfileError(
            f"{PROFILE_OUT_ENV} {out} already has rows; must be non-existing or empty"
        )
    return DecisionProfileWriter(out, manifest=manifest)
