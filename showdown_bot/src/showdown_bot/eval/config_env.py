"""Fail-closed SHOWDOWN_* env classification for the effective ``config_hash`` (T3f Task 1).

**Fail-closed:** ``behavior_env()`` includes **every set ``SHOWDOWN_*`` var EXCEPT** those
explicitly excluded. A *forgotten* behavior-affecting flag then only makes runs non-pairable
(safe); it can never produce the same ``config_hash`` for different behavior (dangerous).

Every ``SHOWDOWN_*`` read in the source must fall into exactly one class (enforced by the
drift test in ``tests/test_config_env.py``):

- ``BEHAVIOR_AFFECTING`` — changes how the bot plays → part of ``config_hash`` (via env).
- ``SERVER_SIDE_BEHAVIOR_AFFECTING`` — changes pokemon-showdown SERVER behavior; also part of
  ``config_hash`` (via env), but read in the versioned TS server patch, NOT the Python package.
- ``NON_BEHAVIORAL`` (exact names + ``NON_BEHAVIORAL_PREFIXES`` families) — diagnostics,
  auth, IO paths, seed plumbing → excluded from the env dict.
- ``EXCLUDED_BY_REASON`` — behavior-relevant, but captured by an explicit manifest field
  (not the env dict), so excluding it avoids a double-count.
"""
from __future__ import annotations

import os

# Flags that change how the bot plays -> must be inside config_hash.
BEHAVIOR_AFFECTING = frozenset({
    "SHOWDOWN_ROLLOUT_HORIZON",
    "SHOWDOWN_PROTECT_PENALTY",
    "SHOWDOWN_MUST_REACT_LAMBDA",
    # [2c-1] NEUTRAL-mode aggregation risk-aversion knob (mirrors
    # SHOWDOWN_MUST_REACT_LAMBDA above): changes which candidate wins the variance
    # penalty in aggregate_scores/pick_best -> directly changes which move is
    # played -> config_hash.
    "SHOWDOWN_RISK_LAMBDA",
    # [2c-sampling] K sampled opponent-set worlds in _choose_best -> changes which
    # candidate wins (aggregation over sampled worlds) -> config_hash. Off/<=1 = 1
    # world = byte-identical.
    "SHOWDOWN_WORLD_SAMPLES",
    # [2c-depth2] Search depth (1 = verbatim 1-ply, 2 = approximate depth-2 backup) in
    # _choose_best's single-world path -> changes which candidate's score vector is used
    # (1-ply leaf vs depth-2 backup), which can flip which move is played -> config_hash.
    # Off/<=1 = 1-ply = byte-identical.
    "SHOWDOWN_SEARCH_DEPTH",
    "SHOWDOWN_OPP_SETS",
    "SHOWDOWN_OUR_ROLL",
    "SHOWDOWN_OUR_DEF_PRESET",
    "SHOWDOWN_OPP_SPEED",
    "SHOWDOWN_REAL_SPREADS",
    "SHOWDOWN_RERANKER_SHADOW",
    "SHOWDOWN_RERANKER_MODEL_PATH",
    "SHOWDOWN_RERANKER_MANIFEST_PATH",
    "SHOWDOWN_RERANKER_SHADOW_TIMEOUT_MS",
    # [2b-4 Task 2] Gates the heuristic_reranker override agent (client.gauntlet); when
    # on, live decisions can be RE-PICKED by the committed reranker model instead of the
    # heuristic's own choice -> directly changes which move is played -> config_hash.
    "SHOWDOWN_RERANKER_OVERRIDE",
    # A calc timeout can trigger fallback behavior under load -> behavior-affecting.
    "SHOWDOWN_CALC_TIMEOUT_MS",
    # [2b-2.5a, 2026-07-11] Per-battle gauntlet wall-clock timeout override (datagen: 900s).
    # It changes which battles produce a result row at all (a battle that times out yields NO
    # row -> a lower-effort/lower-timeout run silently drops legitimate long stall games), so
    # two runs that differ on it must not be paired -> part of config_hash. Read directly in
    # Python source (showdown_bot.client.gauntlet), so it belongs in this set, NOT
    # SERVER_SIDE_BEHAVIOR_AFFECTING.
    "SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S",
    # [2b-4 Task 3] Selects the hero agent for a schedule run (cli.run_schedule) -- "heuristic"
    # (default) vs "heuristic_reranker" (the gated override agent, Task 2). Directly changes
    # which move is played -> config_hash, same rationale as SHOWDOWN_RERANKER_OVERRIDE above.
    "SHOWDOWN_HERO_AGENT",
    # [2026-07-11, fast-board Protect discipline] Sets EvalWeights.fast_board_protect
    # (default 0.0 = OFF, byte-identical). Independently gated from
    # SHOWDOWN_PROTECT_PENALTY -- when non-zero it changes the score of a wasted Protect
    # on a both-Tailwind board, which can flip which candidate is chosen -> config_hash.
    "SHOWDOWN_FAST_BOARD_PROTECT_PENALTY",
    # [accuracy-slice] On/off switch for hit/miss branching in evaluate_line -- directly
    # changes which candidate's score is used (always-hit vs probability-weighted) -> config_hash.
    # Off/unset = byte-identical.
    "SHOWDOWN_ACCURACY_MODE",
    # [accuracy-slice] Max resolve_turn_branches expansion depth. A different cap can change
    # which lines hit the per-branch fallback and therefore which candidate scores highest --
    # deliberately UNCONDITIONAL here (not excluded when SHOWDOWN_ACCURACY_MODE is off), to
    # avoid repeating the SHOWDOWN_SEARCH_TOPN/TOPM conditional-exclusion bug the project's
    # audit found.
    "SHOWDOWN_ACCURACY_BRANCH_CAP",
    # [I7b] Opponent Mega click-rate prior (opponent.opp_mega_click_rate) -- changes
    # the weight split between an opponent's no-mega and mega response twins ->
    # directly changes aggregate scoring -> config_hash.
    "SHOWDOWN_OPP_MEGA_CLICK_RATE",
})

# Server-side (pokemon-showdown patch) flags that change SERVER behavior and so belong in the
# effective config_hash (fail-closed inclusion by behavior_env, exactly like any non-excluded
# SHOWDOWN_* var). They are read in the versioned TS server patch
# (tools/eval/patches/pokemon-showdown-seeded-battle.patch), NOT the Python package, so they are
# kept OUT of BEHAVIOR_AFFECTING: the "read in Python source" hardening test guards that set, and
# the Python-only drift scan never sees a server-side flag (so it needs no Python read to be
# valid). is_classified() still recognizes them so a future Python read would classify cleanly.
SERVER_SIDE_BEHAVIOR_AFFECTING = frozenset({
    # [2b-2.5a] Expire an ENDED headless-eval battle room the moment its last user leaves; stock
    # deallocation waits up to 40min (TIMEOUT_INACTIVE_DEALLOCATE) -> VM OOM after ~50-75
    # sequential battles. Strictly post-battle: zero effect on RNG/log bytes, but it DOES change
    # server behavior, so two runs that differ on it must not be paired -> part of config_hash.
    "SHOWDOWN_EVAL_ROOM_DEALLOC",
})

# Non-behavioral: diagnostics, auth, IO paths, seed plumbing — no effect on how the bot
# plays, so excluded from config_hash.
#
# SHOWDOWN_CALC_BACKEND caveat: oneshot and persistent backends both call the same
# @smogon/calc Node script -> numerically identical results TODAY. If a future
# Python/approximate backend changes scoring, SHOWDOWN_CALC_BACKEND MUST move to
# BEHAVIOR_AFFECTING.
NON_BEHAVIORAL = frozenset({
    "SHOWDOWN_TURN_TRACE",
    "SHOWDOWN_DECISION_DIFF",
    # [I7b-C Task 2] Opponent-Mega evidence sidecar output PATH (eval/opp_mega_trace.py).
    # Same species as SHOWDOWN_AGG_TRACE_OUT below: an IO path with no /choose effect, so it
    # must stay OUT of config_hash -- otherwise merely writing telemetry to a different file
    # would perturb the hash and break run pairing. This classifies the sidecar's PATH only;
    # the click-rate knob the sidecar RECORDS (SHOWDOWN_OPP_MEGA_CLICK_RATE) genuinely does
    # affect decisions and is already BEHAVIOR_AFFECTING from I7b-A -- the two must not be
    # confused.
    "SHOWDOWN_OPP_MEGA_TRACE_OUT",
    # [2c-Slice-0b Task 3] Research-only full-fidelity aggregation sidecar PATH (env alias for
    # --agg-trace-out; the Kaggle datagen kernel injects it via EXTRA_ENV). IO/telemetry-only,
    # no /choose effect -> excluded from config_hash. MUST stay non-behavioral so a per-shard
    # export path never perturbs config_hash / breaks datagen pairing (same species as
    # SHOWDOWN_DECISION_DIFF above and the SHOWDOWN_DATASET_ prefix family).
    "SHOWDOWN_AGG_TRACE_OUT",
    "SHOWDOWN_ROOM_RAW_DUMP",
    "SHOWDOWN_EVAL_SEED_LOG",
    "SHOWDOWN_EVAL_POLICY_TELEMETRY",   # T3e P2 activation telemetry: log-only, no /choose effect
    "SHOWDOWN_USERNAME",
    "SHOWDOWN_PASSWORD",
    "SHOWDOWN_SERVER",
    "SHOWDOWN_RERANKER_SHADOW_LOG",
    "SHOWDOWN_BATTLE_SEED_BASE",
    "SHOWDOWN_CALC_BACKEND",            # (see caveat above)
})

# Whole prefix families that are non-behavioral (auth creds, dataset-export plumbing).
NON_BEHAVIORAL_PREFIXES = ("SHOWDOWN_AUTH_", "SHOWDOWN_DATASET_")

# Behavior-relevant, but captured by an explicit manifest field (NOT the env dict), so we
# exclude it from env to avoid a double-count. The value is the documented reason.
EXCLUDED_BY_REASON = {
    "SHOWDOWN_FORMAT": "captured via the manifest field format_id",
    "SHOWDOWN_TEAM_PATH": "captured via hero_team_hash / team content hashes",
    "SHOWDOWN_SEARCH_TOPN": "depth-2 frontier cap; unused unless SHOWDOWN_SEARCH_DEPTH>=2 "
                            "(byte-identical at depth=1), captured by the stage-1 latency-gate "
                            "run manifest, not config_hash",
    "SHOWDOWN_SEARCH_TOPM": "depth-2 frontier cap; unused unless SHOWDOWN_SEARCH_DEPTH>=2 "
                            "(byte-identical at depth=1), captured by the stage-1 latency-gate "
                            "run manifest, not config_hash",
}


def _matches_prefix(name: str) -> bool:
    return any(name.startswith(p) for p in NON_BEHAVIORAL_PREFIXES)


def is_excluded(name: str) -> bool:
    """True iff ``name`` is explicitly excluded from ``behavior_env`` — a NON_BEHAVIORAL
    name/prefix or an EXCLUDED_BY_REASON name. Everything else (BEHAVIOR_AFFECTING **and**
    unknown/new ``SHOWDOWN_*``) is included: fail-closed toward inclusion."""
    return name in NON_BEHAVIORAL or name in EXCLUDED_BY_REASON or _matches_prefix(name)


def is_classified(name: str) -> bool:
    """True iff ``name`` is in one of the three documented classes (or a non-behavioral
    prefix family). The drift test asserts every ``SHOWDOWN_*`` read in the source is
    classified, so a new unclassified read fails fast."""
    return (
        name in BEHAVIOR_AFFECTING
        or name in SERVER_SIDE_BEHAVIOR_AFFECTING
        or name in NON_BEHAVIORAL
        or name in EXCLUDED_BY_REASON
        or _matches_prefix(name)
    )


def behavior_env(environ=None) -> dict[str, str]:
    """The behavior-affecting ``SHOWDOWN_*`` environment (fail-closed).

    Returns every set ``SHOWDOWN_*`` var EXCEPT those ``is_excluded`` — so unknown/new
    ``SHOWDOWN_*`` vars are INCLUDED. ``environ`` defaults to ``os.environ`` (injectable
    for tests)."""
    env = os.environ if environ is None else environ
    return {k: str(v) for k, v in env.items() if k.startswith("SHOWDOWN_") and not is_excluded(k)}


def build_config_manifest(*, agent, format_id, priors_hash, spreads_hash, env=None,
                          model_hash=None, model_manifest_hash=None, movedata_hash=None,
                          format_config_hash=None, calc_pin_hash=None,
                          itemdata_hash=None, speciesdata_hash=None) -> dict:
    """Assemble the effective-config manifest that ``make_config_hash`` hashes.

    ``env`` defaults to ``behavior_env()``. ``model_hash``/``model_manifest_hash`` are
    included ONLY when provided (i.e. when the reranker is enabled), so a reranker-off run
    and a reranker-on run never collide. ``movedata_hash`` is a content hash of
    ``config/moves/movedata.json`` -- included whenever provided (unconditionally by the
    caller, mirroring ``priors_hash``/``spreads_hash``, not gated behind
    ``SHOWDOWN_ACCURACY_MODE``), so two runs with different accuracy data never share a
    config lineage even when the accuracy feature itself is off.

    ``format_config_hash`` / ``calc_pin_hash`` pin the resolved format yaml and vendored
    ``@smogon/calc`` artifact (I4 §5). Included whenever provided by the caller.

    ``itemdata_hash`` / ``speciesdata_hash`` (I7a §14) pin ``config/items/itemdata.json``
    and ``config/species/speciesdata.json`` -- Mega depends on both (megaStone mapping /
    required_item). Included whenever provided by the caller."""
    manifest = {
        "agent": agent,
        "format_id": format_id,
        "priors_hash": priors_hash,
        "spreads_hash": spreads_hash,
        "env": behavior_env() if env is None else env,
    }
    if model_hash is not None:
        manifest["model_hash"] = model_hash
    if model_manifest_hash is not None:
        manifest["model_manifest_hash"] = model_manifest_hash
    if movedata_hash is not None:
        manifest["movedata_hash"] = movedata_hash
    if format_config_hash is not None:
        manifest["format_config_hash"] = format_config_hash
    if calc_pin_hash is not None:
        manifest["calc_pin_hash"] = calc_pin_hash
    if itemdata_hash is not None:
        manifest["itemdata_hash"] = itemdata_hash
    if speciesdata_hash is not None:
        manifest["speciesdata_hash"] = speciesdata_hash
    return manifest


def file_content_hash(path) -> str | None:
    """sha1[:16] of a file's bytes, or None if it can't be read (T3f config_hash provenance).

    Public/exported so every caller that needs a provenance file hash (the CLI's live
    config_hash computation, a dedicated config-manifest freeze helper, ad-hoc scripts)
    shares this one implementation instead of each keeping its own private copy."""
    import hashlib
    from pathlib import Path

    try:
        return hashlib.sha1(Path(path).read_bytes()).hexdigest()[:16]
    except Exception:  # noqa: BLE001 - provenance is best-effort; missing file -> None
        return None


def effective_config_manifest(
    *, agent: str, format_id: str, env: dict[str, str] | None = None,
    model_hash: str | None = None, model_manifest_hash: str | None = None,
) -> dict:
    """The single canonical config payload for ``(agent, format_id)`` -- exactly what
    ``make_config_hash`` hashes into the run's effective ``config_hash`` (I7a-C P1.4).

    This is the ONE place that assembles priors_hash/spreads_hash/movedata_hash plus
    ``config_provenance_for_format``'s format/calc/item/species hashes into a
    ``build_config_manifest`` payload. Both the CLI's live per-(agent, format) config_hash
    cache and any dedicated config-manifest freeze helper MUST call this function rather
    than re-deriving the same hashes locally -- a second, independently-written assembly is
    exactly the drift risk this function exists to close.

    ``env`` defaults to ``behavior_env()`` (matching ``build_config_manifest``'s own
    default) when not provided."""
    from showdown_bot.engine.format_config import load_format_config
    from showdown_bot.engine.moves import movedata_path

    priors_hash = spreads_hash = None
    try:
        cfg = load_format_config(format_id)
        priors_hash = file_content_hash(cfg.meta_path("protect_priors"))
        spreads_hash = file_content_hash(cfg.meta_path("default_spreads"))
    except Exception:  # noqa: BLE001 - provenance best-effort; missing config -> None
        pass
    movedata_hash = file_content_hash(movedata_path())
    provenance = config_provenance_for_format(format_id)
    return build_config_manifest(
        agent=agent, format_id=format_id,
        priors_hash=priors_hash, spreads_hash=spreads_hash, env=env,
        model_hash=model_hash, model_manifest_hash=model_manifest_hash,
        movedata_hash=movedata_hash,
        format_config_hash=provenance["format_config_hash"],
        calc_pin_hash=provenance["calc_pin_hash"],
        itemdata_hash=provenance["itemdata_hash"],
        speciesdata_hash=provenance["speciesdata_hash"],
    )


def config_provenance_for_format(format_id: str) -> dict[str, str | None]:
    """Format yaml + calc pin + item/species data hashes for ``build_config_manifest``.

    Missing format yaml -> ``format_config_hash`` is None. Malformed yaml/schema
    errors propagate. Calc pin errors always propagate (§5.4 fail-closed).

    ``itemdata_hash`` / ``speciesdata_hash`` are FAIL-CLOSED (I7a §14): they call
    ``itemdata_content_hash()`` / ``speciesdata_content_hash()`` unguarded, so a stale
    embedded generator hash (``ItemdataStaleError`` / ``SpeciesMetaStaleError``)
    propagates straight out of this function -- there is no fallback to a raw file SHA.
    """
    from showdown_bot.engine.calc.pin import calc_pin_hash, format_config_hash
    from showdown_bot.engine.format_config import load_format_config
    from showdown_bot.engine.items import itemdata_content_hash
    from showdown_bot.engine.species_meta import speciesdata_content_hash

    fmt_hash: str | None = None
    try:
        cfg = load_format_config(format_id)
    except FileNotFoundError:
        cfg = None
    if cfg is not None and cfg.source_path is not None:
        fmt_hash = format_config_hash(cfg.source_path)

    pin = calc_pin_hash()
    return {
        "format_config_hash": fmt_hash,
        "calc_pin_hash": pin,
        "itemdata_hash": itemdata_content_hash(),
        "speciesdata_hash": speciesdata_content_hash(),
    }
