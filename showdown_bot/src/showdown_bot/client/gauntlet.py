from __future__ import annotations

import asyncio
import functools
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from showdown_bot.battle.decision import (
    SelectionStageSink,
    choose_for_request,
    choose_with_fallback,
)
from showdown_bot.battle.mega_scoring import MegaShapeCounts
from showdown_bot.eval.decision_profile import (
    BASELINE_FALLBACK_STAGES,
    BASELINE_OK_STAGE,
    is_degraded_decision,
    snapshot_calc_counters,
)

# The single member of BASELINE_FALLBACK_STAGES, unpacked once so `agent_choose` marks the
# set's own value rather than a second literal that could drift away from it.
(_BASELINE_DEFAULT_STAGE,) = BASELINE_FALLBACK_STAGES

# The agents whose decisions run through a calc-backed chain and can therefore DEGRADE.
# The eval-only opponent policies (greedy_protect/simple_heuristic/scripted_vgc/random) are
# request-only: they have no fallback chain and no calc, so they have nothing to degrade and
# are correctly counted as 0 rather than as unmeasured.
_DEGRADABLE_AGENTS = frozenset({"heuristic", "heuristic_reranker", "max_damage"})
from showdown_bot.battle.decision_trace import DecisionTrace
from showdown_bot.battle.opponent import SpeciesDex
from showdown_bot.battle.oracle import DamageOracle
from showdown_bot.client.connection import (
    ShowdownConnection,
    authenticate_local,
)
from showdown_bot.engine.calc.client import CalcClient
from showdown_bot.engine.belief.hypotheses import SpreadBook, load_opp_sets_for_format, load_spread_book
from showdown_bot.engine.format_config import load_format_config
from showdown_bot.engine.moves import _move_table
from showdown_bot.engine.speed import SpeedOracle
from showdown_bot.engine.state import BattleState, merge_request
from showdown_bot.eval.room_dump import normalized_room_log_sha256 as _compute_normalized_room_log_sha256
from showdown_bot.learning.export_runtime import DatasetExportRuntime
from showdown_bot.learning.reranker_override import RerankerOverride
from showdown_bot.learning.reranker_shadow import RerankerShadowRuntime
from showdown_bot.models.request import BattleRequest
from showdown_bot.protocol.messages import parse_incoming
from showdown_bot.team.pack import load_packed_team
from showdown_bot.team.spreads import our_spreads_from_packed

logger = logging.getLogger(__name__)

LOCAL_SERVER = "ws://localhost:8000/showdown/websocket"

# Race conditions, not bad choices: the server rejects a choice we sent for a
# turn that already resolved. These are harmless (the rqid guard protects us) so
# they must not count against the strict invalid-choice criterion.
_BENIGN_CHOICE_ERRORS = ("too late", "nothing to choose")


def _is_real_invalid(text: str | None) -> bool:
    low = (text or "").lower()
    if "invalid choice" not in low and "can't" not in low:
        return False
    return not any(b in low for b in _BENIGN_CHOICE_ERRORS)


def agent_choose(
    agent: str,
    req: BattleRequest,
    *,
    state: BattleState | None,
    book: SpreadBook | None,
    our_side: str | None,
    priors=None,
    report: list[str] | None = None,
    our_spreads: dict | None = None,
    opp_sets: dict | None = None,
    trace=None,
    species_resolver=None,
    calc=None,
    oracle=None,
    speed_oracle=None,
    dex=None,
    override=None,
    format_config=None,
    opp_mega_evidence_sink=None,
    stage_sink=None,
    shape_sink=None,
) -> str:
    """Pure per-request dispatch shared by both gauntlet clients (unit-testable).

    ``heuristic`` uses the full fallback chain; ``max_damage`` uses the baseline
    via the fallback chain; ``random`` uses the legacy random agent. ``report``
    (heuristic only) collects a readable decision block for the turn trace.

    ``calc``/``oracle``/``speed_oracle``/``dex`` (2b-2.5a Kaggle-OOM root-cause
    fix) are the CLIENT-OWNED decision deps, threaded into the heuristic
    (``choose_with_fallback``) and max_damage (``max_damage_choice``) branches so
    the decision core reuses ONE calc for the whole battle instead of the buggy
    per-decision ``calc = calc or CalcClient()`` (which spawned a fresh
    ``node calc.mjs --server`` per live decision, ~70/battle, never closed).
    ``None`` (the request-only eval policies + random never pass them) preserves
    the prior default-construction behavior for callers that don't own a calc.

    ``heuristic_reranker`` (2b-4 Task 2): runs the SAME heuristic fallback chain
    exactly once -- reusing ``trace`` if the caller already built one, else a
    fresh ``DecisionTrace()`` -- to get BOTH the heuristic's own ``choose``
    string AND its populated candidate trace (no second heuristic run). When
    ``override`` (a ``RerankerOverride``, built once per client from env -- see
    ``_Client._reranker_override``) is available, that SAME trace + choose are
    handed to ``override.override_choice(...)``, whose own fail-safe contract
    means it never raises and returns ``heuristic_choose`` unchanged on any
    failure. ``override=None`` (the default; also what a disabled/unavailable
    override resolves to) makes this branch return the heuristic's choose
    string UNCHANGED -- byte-identical to plain ``"heuristic"``.
    """
    # Eval-only opponent policies (T3c): request-only + deterministic, no state/book needed.
    # Local imports keep eval/opponents off the default/import path (live-path guard).
    if agent == "greedy_protect":
        from showdown_bot.eval.opponents.policies import greedy_protect_choice
        # T3e Task 2: thread state/our_side so Protect is HP-gated when HP is known;
        # both default to None (attack, full-HP behavior) when state build failed.
        return greedy_protect_choice(req, state=state, our_side=our_side)
    if agent == "simple_heuristic":
        from showdown_bot.eval.opponents.policies import simple_heuristic_choice
        # T3e Task 1: thread state/our_side so scoring is type-aware when typing is known.
        # T3e P2a: species_resolver derives opponent typing from species when the live state
        # carries only the species (types empty) — eval-only, never mutates state.
        return simple_heuristic_choice(
            req, state=state, our_side=our_side, resolver=species_resolver)
    if agent == "scripted_vgc":
        from showdown_bot.eval.opponents.scripted_vgc import scripted_vgc_choice
        return scripted_vgc_choice(req)
    if agent == "random" or state is None or book is None:
        return choose_for_request(req)
    if agent == "max_damage":
        from showdown_bot.battle.baselines import max_damage_choice

        # Eval-deterministic (T3c): paired seed comparison needs a deterministic opponent,
        # so max_damage's rare fallbacks use `/choose default` (not pick_random_pair). The
        # live path (decision.py) calls max_damage_choice with the default fallback -> unchanged.
        # Gate B finding 4: this except branch is the BASELINE arm's silent-degradation path --
        # max_damage_choice raising (a dead calc subprocess, say) is swallowed here and answered
        # with a legal `/choose default`, so nothing downstream could tell a computed baseline
        # from a blind one. Mark the same sink choose_with_fallback marks; the returned choice is
        # byte-identical either way, and the sink stays None for every caller that wants none.
        try:
            choice = max_damage_choice(
                req, state=state, book=book, our_side=our_side,
                calc=calc, oracle=oracle, speed_oracle=speed_oracle,
                format_config=format_config, our_spreads=our_spreads,
                fallback=lambda r: f"/choose default|{r.rqid}",
            )
            if stage_sink is not None:
                stage_sink.selection_stage = BASELINE_OK_STAGE
            return choice
        except Exception:  # noqa: BLE001
            if stage_sink is not None:
                stage_sink.selection_stage = _BASELINE_DEFAULT_STAGE
                stage_sink.fallback_reason = "max_damage_error"
            return f"/choose default|{req.rqid}"
    if agent == "heuristic_reranker":
        # Run the heuristic core EXACTLY ONCE -- reuse a caller-supplied trace
        # (mirrors the heuristic branch below) or build a fresh one, so the same
        # populated trace + choose string are available to the override with no
        # second heuristic invocation.
        local_trace = trace if trace is not None else DecisionTrace()
        heuristic_choose = choose_with_fallback(
            req, state=state, book=book, our_side=our_side, priors=priors, report=report,
            our_spreads=our_spreads, opp_sets=opp_sets, trace=local_trace,
            calc=calc, oracle=oracle, speed_oracle=speed_oracle, dex=dex,
            format_config=format_config,
            # [I7b-C REV.9 finding 2] Same scorer as the plain heuristic branch below,
            # so it generates and scores the SAME foe-Mega hypotheses and must fill the
            # SAME sink. Omitting it here made every reranker decision invisible to the
            # sidecar.
            opp_mega_evidence_sink=opp_mega_evidence_sink,
            stage_sink=stage_sink, shape_sink=shape_sink,
        )
        if override is None:
            return heuristic_choose
        # The sink is deliberately NOT passed to the override: the sidecar records which
        # opponent hypotheses were generated and scored, not which action finally won.
        # An override may change the choice; it may never reinterpret or edit evidence.
        return override.override_choice(
            trace=local_trace, state=state, request=req,
            heuristic_choose=heuristic_choose, our_side=our_side,
        )
    return choose_with_fallback(
        req, state=state, book=book, our_side=our_side, priors=priors, report=report,
        our_spreads=our_spreads, opp_sets=opp_sets, trace=trace,
        calc=calc, oracle=oracle, speed_oracle=speed_oracle, dex=dex,
        format_config=format_config,
        # Rides through choose_with_fallback's existing **deps into
        # heuristic_choose_for_request -- no second container there (I7b-C Task 2).
        opp_mega_evidence_sink=opp_mega_evidence_sink,
            stage_sink=stage_sink, shape_sink=shape_sink,
    )


def _latency_p95(latencies) -> float:
    if not latencies:
        return 0.0
    ordered = sorted(latencies)
    idx = min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))
    return ordered[idx]


class _PerBattleCounters:
    """Turn lifetime-cumulative client counters into per-battle deltas (T3e-P0).

    ``_Client.invalid``/``.crashes`` accumulate over the client's whole life and
    ``.latencies`` is append-only, so a T2 result row built from the raw totals makes
    row N carry battles 0..N (a run-lifetime total), not battle N. This keeps a watermark
    (snapshot) of the cumulative values consumed so far; ``emit`` returns the delta for
    the single battle that just finished and computes latency p95 over ONLY the latencies
    appended since the previous emit, then advances the watermark. Battles are sequential,
    so "delta since last emit" is exactly this battle's count.

    First battle: watermark starts at zero, so the delta equals the raw values — the
    existing single-battle-per-row behavior is preserved bit-for-bit.
    """

    def __init__(self) -> None:
        self._invalid = 0
        self._crashes = 0
        self._lat_len = 0
        self._hero_degraded = 0
        self._villain_degraded = 0

    def emit(self, *, invalid: int, crashes: int, latencies: list[float],
             hero_degraded: int = 0, villain_degraded: int = 0) -> dict:
        new_lat = latencies[self._lat_len:]
        record = {
            "invalid_choices": invalid - self._invalid,
            "crashes": crashes - self._crashes,
            "decision_latency_p95_ms": round(_latency_p95(new_lat) * 1000),
            # PER SEAT, deliberately not summed (Gate B finding 5): `invalid_choices` above sums
            # both seats, so an opponent-seat violation fails the candidate with nothing on the
            # row able to show it. The counter added here must not inherit that defect.
            "hero_degraded_decisions": hero_degraded - self._hero_degraded,
            "villain_degraded_decisions": villain_degraded - self._villain_degraded,
        }
        self._invalid = invalid
        self._crashes = crashes
        self._lat_len = len(latencies)
        self._hero_degraded = hero_degraded
        self._villain_degraded = villain_degraded
        return record


@dataclass
class GauntletStats:
    games: int = 0
    hero_wins: int = 0
    villain_wins: int = 0
    ties: int = 0
    invalid_choices: int = 0
    crashes: int = 0
    latencies: list[float] = field(default_factory=list)
    # Task 6 (coverage safety): the hero seat's OWN invalid-choice decision indices for this battle
    # (a -1 marks an unattributable |error|). In-memory only -- NEVER on the closed T2 result row.
    hero_invalid_decision_indices: tuple[int, ...] = ()

    @property
    def winrate(self) -> float:
        return self.hero_wins / self.games if self.games else 0.0

    def latency_p95(self) -> float:
        return _latency_p95(self.latencies)


def _load_reranker_override_from_env(*, format_id: str, dex=None, move_meta=None) -> RerankerOverride | None:
    """Build a ``RerankerOverride`` from env (2b-4 Task 2), mirroring
    ``RerankerShadowRuntime.from_env``'s gating pattern: returns ``None``
    (override disabled) when ``SHOWDOWN_RERANKER_OVERRIDE`` is unset, or on ANY
    load/schema failure (bad path, unreadable manifest, booster load error) --
    one warning, never raises. ``heuristic_reranker`` then behaves exactly like
    ``heuristic`` (fail-safe -- see ``agent_choose``'s ``heuristic_reranker``
    branch).

    lightgbm is imported ONLY here, ONLY when the env flag is on (rule 5,
    mirroring the shadow's own import-time discipline -- the disabled path
    stays lightgbm-free; see ``test_gauntlet_shadow.py``'s import guard).

    A thin module-level function (not a ``RerankerOverride`` classmethod --
    2b-4 Task 2 is scoped to ``client/gauntlet.py`` only) so ``_Client`` --
    and tests -- can monkeypatch/stub it directly without constructing a real
    booster.
    """
    if not os.environ.get("SHOWDOWN_RERANKER_OVERRIDE"):
        return None  # rule 5: no lightgbm import when off
    try:
        import lightgbm as lgb  # imported ONLY here, ONLY when enabled

        model_path = os.environ["SHOWDOWN_RERANKER_MODEL_PATH"]
        manifest_path = os.environ["SHOWDOWN_RERANKER_MANIFEST_PATH"]
        manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        booster = lgb.Booster(model_file=model_path)
        return RerankerOverride(
            booster=booster, manifest=manifest, format_id=format_id, dex=dex, move_meta=move_meta,
        )
    except Exception as exc:  # noqa: BLE001 - override is best-effort; disable on ANY failure
        logger.warning("reranker override disabled: %s", exc)
        return None


class _Client:
    """One gauntlet bot: per-room state, agent dispatch, challenge handling."""

    def __init__(self, conn, name, agent, *, book, priors, format_id, format_config=None, packed_team, trace=False, opp_sets=None,
                 export_runtime=None, allow_own_export=True, is_mirror=True,
                 decision_trace_writer=None, decision_trace_context=None,
                 agg_trace_writer=None, agg_trace_context=None,
                 opp_mega_trace_writer=None, opp_mega_trace_context=None,
                 decision_profile_writer=None, decision_profile_context=None):
        self.conn = conn
        self.name = name
        self.agent = agent
        self.book = book
        self.priors = priors
        self.format_id = format_id
        self.format_config = format_config
        self.packed_team = packed_team
        # Decision capture seam (candidate-vs-baseline-diff Task 4) — off by default. A caller
        # (cli.run_schedule, HERO client only) can supply a DecisionTraceWriter + a per-battle
        # BattleTraceContext to bind every decision this client makes to an optional sidecar
        # file. `None` (both, the default) is a NO-OP: `handle_request` never builds a
        # DecisionTrace for capture, never calls prepare_capture/build_trace_row, and the
        # dispatched /choose messages are byte-identical to before this seam existed.
        self.decision_trace_writer = decision_trace_writer
        self.decision_trace_context = decision_trace_context
        self._decision_capture_index = 0
        # Aggregation-trace capture seam (2c-Slice-0b Task 3) — off by default, and INDEPENDENT
        # of decision capture above (a SEPARATE writer/context/counter, mirroring its shape
        # exactly). A caller (cli.run_schedule, HERO client only) can supply an AggTraceWriter +
        # a per-battle AggTraceContext (research/aggregation_trace.py) to bind every decision
        # this client makes to a SECOND, independent sidecar file (the full-fidelity per-
        # candidate x per-opponent-response score matrix). `None` (both, the default) is a
        # NO-OP: `handle_request` never builds a DecisionTrace for THIS trigger, never calls
        # build_agg_row, and the dispatched /choose messages are byte-identical to before this
        # seam existed.
        self.agg_trace_writer = agg_trace_writer
        self.agg_trace_context = agg_trace_context
        self._agg_trace_index = 0
        # Opponent-Mega evidence seam (I7b-C Task 2) — off by default, and a THIRD writer/
        # context/counter, independent of BOTH seams above (it does not read, build or need
        # `trace_obj` at all: its evidence comes from the scoring call's own
        # `opp_mega_evidence_sink`, not from DecisionTrace). A caller can supply an
        # OppMegaTraceWriter + a per-battle OppMegaTraceContext (eval/opp_mega_trace.py) to
        # record which foe-Mega hypotheses were generated AND scored for each decision.
        # `None` (both, the default) is a NO-OP: `handle_request` allocates no evidence list,
        # passes an explicit `None` down the chain, and the dispatched /choose messages are
        # byte-identical to before this seam existed.
        self.opp_mega_trace_writer = opp_mega_trace_writer
        self.opp_mega_trace_context = opp_mega_trace_context
        # Live decision-profile seam (I8-D) — off by default, a FOURTH writer/context
        # independent of the three above. When a caller (cli.run_schedule, HERO client only)
        # supplies a DecisionProfileWriter + a per-battle LiveProfileContext, handle_request
        # snapshots the calc counters around agent_choose, drives the stage/shape sinks inside
        # the existing timer, and writes one live row per scored decision. `None` (both, the
        # default) is a NO-OP: no sink is allocated, no row is built, /choose is byte-identical.
        self.decision_profile_writer = decision_profile_writer
        self.decision_profile_context = decision_profile_context
        # [P1] Rows WRITTEN, not the decision index. The two differ whenever a decision
        # produces no row, which is why this must never be used to number one.
        self._opp_mega_rows_written = 0
        # [P1] The shared request/decision sequence: advances once per handled non-wait
        # request, independent of any writer, and is what every sidecar row's
        # `decision_index` is stamped with. A per-writer row counter cannot do this job:
        # decision capture writes a row for team preview (its write is NOT gated on
        # `state`) while the opp-mega sidecar cannot (state is None -> no sink -> no row),
        # so a row counter gave the FIRST REAL decision trace index 1 and sidecar index 0 --
        # two numbers for one decision, breaking exactly the join the smoke's evidence gate
        # depends on. A state-build failure, an agent crash, or a dropped best-effort write
        # each shifted it further. Sidecar rows may legitimately have GAPS; they must never
        # be renumbered.
        self._request_seq = 0
        # Real own-team spreads (Stage C), default on. SHOWDOWN_REAL_SPREADS=0
        # falls back to the worst-case proxy (OUR_DEF_PRESET) for a clean A/B.
        _real = os.environ.get("SHOWDOWN_REAL_SPREADS", "1") != "0"
        self.our_spreads = our_spreads_from_packed(packed_team) if (packed_team and _real) else None
        self.opp_sets = opp_sets
        self.trace = trace
        # Eval-only species->types resolver for simple_heuristic (T3e P2a): built lazily +
        # cached so the type-aware path can activate when the live state has only species.
        self._eval_species_dex = None
        self._eval_species_dex_tried = False
        # Client-owned live-decision deps (2b-2.5a Kaggle-OOM root-cause fix): ONE
        # calc/oracle/speed_oracle/dex bundle per battle, built lazily on the first
        # decision that needs it (heuristic/max_damage only) and threaded into every
        # decision so the core never default-builds a fresh CalcClient per decision.
        self._decision_deps_built = False
        self._decision_calc = None
        self._decision_oracle = None
        self._decision_speed_oracle = None
        self._decision_dex = None
        self.room_raw: dict[str, list[str]] = {}
        # Diagnostic-only companion to room_raw: the choices this seat SENT, each tagged with the
        # rqid of the request it was computed from. Deliberately a SEPARATE dict, never appended
        # into room_raw -- room_raw is fed to BattleState.from_log_text (_state_for below), so a
        # synthetic frame there would change parsing and therefore how the bot plays. Merged into
        # the diagnostic dump only, via dump_frames(). No decision path reads it, and the dump is
        # not hashed by eval/decision_profile.py.
        self.choose_log: dict[str, list[str]] = {}
        self.last_choose: dict[str, str] = {}
        # Task 6: the decision_index of the choice last SENT per room (recorded at send time), and
        # this seat's own invalid-choice decision indices (a -1 = unattributable |error|).
        self._last_choice_decision_index: dict[str, int] = {}
        self._invalid_decision_indices: list[int] = []
        self.last_request: dict[str, str] = {}
        self.latencies: list[float] = []
        self.invalid = 0
        self.crashes = 0
        # Gate B finding 4: this seat's decisions that did NOT complete on its agent's intended
        # path. Run-lifetime cumulative like .invalid/.crashes; _PerBattleCounters turns it into
        # the per-battle delta that reaches the row.
        self.degraded = 0
        # Dataset export seam (2b-2.5a run-scoped fix): a caller (cli.run_schedule) can BORROW
        # a runtime that spans multiple sequential run_local_gauntlet() calls/battles -- this
        # client must then never build its own AND close() must never close a runtime it does
        # not own (the runtime outlives this client). `allow_own_export=False` (villain, always)
        # means this client never touches the export path at all: an explicit hero-only
        # contract (a "heuristic" villain would otherwise build a SECOND runtime pointed at the
        # same SHOWDOWN_DATASET_EXPORT path and clobber the hero's flushes) that also removes a
        # per-battle wasted runtime/CalcClient build for every non-exporting villain.
        self.owns_export = False
        if export_runtime is not None:
            self._export = export_runtime  # borrowed — never built or closed by this client
            # 2b-2.5a wiring fix: a borrowed (run-scoped) runtime spans MANY battles across a
            # schedule, and the villain can differ per row -- mirror_flag is battle-specific, so
            # it must be refreshed here for the battle THIS client is about to play (the
            # smallest correct seam: a fresh `_Client` is built per `run_local_gauntlet` call =
            # per battle, so this fires exactly once per battle, before `start_game()`/
            # `observe()`). dex/move_meta on a borrowed runtime are RUN-scoped (built once by
            # `build_schedule_export_runtime`) and are intentionally left untouched here.
            self._export.mirror_flag = is_mirror
        elif allow_own_export:
            # Thread calc/book/our_spreads/opp_sets/dex/move_meta so rollout mode can reuse
            # the gauntlet's already-built deps (avoids a second CalcClient).
            # In rollout mode from_env builds CalcClient/oracle/speed_oracle from these;
            # in stub mode (default) they are ignored.
            # 2b-2.5a wiring fix: move_meta is a pure, run-invariant lookup table (data-driven,
            # memoized via functools.lru_cache) so it is safe to pass directly here. dex is
            # per-battle/client-scoped -- built lazily off the live-decision calc backend in
            # `_decision_deps()` (which only runs once the first decision is made, AFTER this
            # constructor returns) -- so it starts None and gets threaded in from there instead.
            self._export = DatasetExportRuntime.from_env(
                format_id=self.format_id,
                packed_team=self.packed_team,
                mirror_flag=is_mirror,
                dex=None,
                move_meta=_move_table(),
                book=self.book,
                our_spreads=self.our_spreads,
                opp_sets=self.opp_sets,
                priors=self.priors,
            )
            self.owns_export = self._export is not None
        else:
            self._export = None  # hero-only contract: this client never exports
        # Reranker Shadow Mode seam (slice 2b-3a) — None when SHOWDOWN_RERANKER_SHADOW is unset
        # (bit-identical path). Pass the export's provenance so shadow IDs join the export dataset.
        # RerankerShadowRuntime does NOT import lightgbm at module scope; only from_env does, when
        # enabled — so the module-top import above keeps the disabled path lightgbm-free.
        _prov = None
        if self._export is not None:
            _prov = {"git_sha": self._export.git_sha, "dirty_flag": self._export.dirty_flag,
                     "team_hash": self._export.team_hash_, "config_hash": self._export.config_hash_,
                     "run_seed": self._export.run_seed}
        self._shadow = RerankerShadowRuntime.from_env(
            format_id=format_id, packed_team=packed_team, provenance=_prov)
        # Reranker Override seam (2b-4 Task 2) — lazily built ONCE per client
        # (mirrors _decision_deps' build-once bundle) by `_reranker_override()`,
        # only for agent == "heuristic_reranker" (no env lookup, no construction
        # attempt, for any other agent). Starts None/not-attempted here; the
        # first heuristic_reranker decision builds it (needs THIS client's
        # decision-deps dex, itself built lazily on the first decision).
        self._override = None
        self._override_built = False

    def _species_type_resolver(self):
        """Eval-only species->types resolver for simple_heuristic (T3e P2a). Built lazily and
        cached; ``None`` for other agents or when the calc backend can't be built (graceful —
        the policy then stays in base-power mode). Reads types only; never mutates state."""
        if self.agent != "simple_heuristic":
            return None
        if not self._eval_species_dex_tried:
            self._eval_species_dex_tried = True
            try:
                from showdown_bot.battle.opponent import SpeciesDex
                from showdown_bot.engine.calc.client import make_calc_backend

                self._eval_species_dex = SpeciesDex(make_calc_backend())
            except Exception as exc:  # noqa: BLE001 - stay base-power if backend unavailable
                logger.debug("[%s] eval species resolver unavailable: %s", self.name, exc)
                self._eval_species_dex = None
        return self._eval_species_dex

    def _decision_deps(self):
        """Client-owned ``(calc, oracle, speed_oracle, dex)`` bundle for the live
        decision path (2b-2.5a Kaggle-OOM ROOT-CAUSE fix). Built ONCE per client
        (= per battle; the schedule runner plays games=1 per battle) and threaded
        into every decision so the core reuses one calc instead of the buggy
        per-decision ``calc = calc or CalcClient()`` that spawned a fresh
        ``node calc.mjs --server`` per live decision (~70/battle, MEMTRACE v3),
        never closed.

        Only agents that actually use calc build the bundle: ``heuristic``,
        ``max_damage``, and ``heuristic_reranker`` (2b-4 Task 2 -- it runs the
        SAME heuristic fallback chain, so it needs the SAME deps). The
        request-only eval policies (greedy_protect / simple_heuristic /
        scripted_vgc) and ``random`` return all-None and never construct a
        CalcClient (live-path/OOM guard). Built lazily + cached; the
        speed_oracle/dex fall back to ``None`` if the calc backend can't be built,
        mirroring decision.py so a decision still degrades gracefully.

        Determinism: DamageOracle/SpeedOracle/SpeciesDex are memoized PURE lookups
        (damage/speed/typing keyed by full semantic payload), so sharing them
        across a battle's decisions changes no decision output -- only the number
        of Node round trips. Per-battle scope (a fresh client per battle) keeps the
        bit-identical contract with prior recorded runs; never shared across battles.
        """
        if self.agent not in ("heuristic", "max_damage", "heuristic_reranker"):
            return (None, None, None, None)
        if not self._decision_deps_built:
            self._decision_deps_built = True
            self._decision_calc = CalcClient()
            self._decision_oracle = DamageOracle(self._decision_calc)
            try:
                from showdown_bot.engine.calc_profile import (
                    build_speed_oracle,
                    calc_profile_from_config,
                )

                self._decision_speed_oracle = build_speed_oracle(
                    self._decision_calc.backend,
                    calc_profile_from_config(self.format_config),
                )
            except Exception as exc:  # noqa: BLE001 - degrade like decision.py if backend unavailable
                logger.debug("[%s] decision speed oracle unavailable: %s", self.name, exc)
                self._decision_speed_oracle = None
            try:
                self._decision_dex = SpeciesDex(self._decision_calc.backend)
            except Exception as exc:  # noqa: BLE001 - degrade like decision.py if backend unavailable
                logger.debug("[%s] decision species dex unavailable: %s", self.name, exc)
                self._decision_dex = None
            # 2b-2.5a wiring fix: thread this SAME client-scoped dex into an OWNED export
            # runtime (never a borrowed/run-scoped one -- that one keeps its own independent,
            # run-invariant SpeciesDex built once by `build_schedule_export_runtime`, which
            # must NOT be swapped out per-battle). `observe()` reads `self._export.dex` fresh
            # on every call, and this runs before the first `observe()` of the battle
            # (`handle_request` calls `_decision_deps()` before `agent_choose()`/`observe()`),
            # so even the very first decision's exported row gets a real dex. `None` here
            # (backend build failed above) degrades gracefully -- `from_env`/`features.py`
            # already tolerate `dex=None`.
            if self._export is not None and self.owns_export:
                self._export.dex = self._decision_dex
        return (
            self._decision_calc,
            self._decision_oracle,
            self._decision_speed_oracle,
            self._decision_dex,
        )

    def _reranker_override(self):
        """Client-owned ``RerankerOverride`` (2b-4 Task 2): built ONCE per
        client -- lazily, on the first ``heuristic_reranker`` decision --
        mirroring ``_decision_deps``'s build-once bundle. ``None`` for every
        other agent (no env lookup, no construction attempt at all -- the
        ``SHOWDOWN_RERANKER_OVERRIDE`` gate is only even consulted for
        ``heuristic_reranker``, mirroring ``_decision_deps``'s own agent
        guard) and ``None`` when the override is disabled or unavailable
        (fail-safe: ``agent_choose("heuristic_reranker", ...)`` then returns
        the heuristic's own choose string unchanged, byte-identical to plain
        ``"heuristic"``).

        Reuses THIS client's decision-deps dex (built by ``_decision_deps()``,
        which ``handle_request`` calls just before this) and the run-invariant
        ``_move_table()`` move_meta, so the override's feature context matches
        the shadow's real-dex/move_meta context mode exactly.
        """
        if self.agent != "heuristic_reranker":
            return None
        if not self._override_built:
            self._override_built = True
            self._override = _load_reranker_override_from_env(
                format_id=self.format_id, dex=self._decision_dex, move_meta=_move_table(),
            )
        return self._override

    def _state_for(self, room: str, req: BattleRequest) -> BattleState | None:
        if self.book is None or req.team_preview:
            return None
        try:
            st = BattleState.from_log_text("\n".join(self.room_raw.get(room, [])))
            merge_request(req, st)
            return st
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] state build failed: %s", self.name, exc)
            return None

    async def set_team(self) -> None:
        await self.conn.send(f"|/utm {self.packed_team}" if self.packed_team else "|/utm null")

    def _note_invalid_choice(self, room: str) -> None:
        """Record ONE real invalid choice for this seat (Task 6): bump the counter AND append the
        SENT choice's decision_index for ``room`` -- recorded at send time, so it is the REJECTED
        decision, never the since-advanced counter. A room with no recorded send-time index (an
        unattributable |error|, which the protocol should never produce) appends the fail-closed
        sentinel -1 instead of being silently dropped, so the runner's join aborts."""
        self.invalid += 1
        self._invalid_decision_indices.append(self._last_choice_decision_index.get(room, -1))

    def dump_frames(self, room: str) -> list[str]:
        """Frames for the DIAGNOSTIC room dump: the server stream plus this seat's own sent
        choices, each tagged with the rqid it was computed from.

        Kept out of ``room_raw`` on purpose -- that list is parsed by
        ``BattleState.from_log_text`` in ``_state_for``, so a synthetic frame there would change
        how the bot reads the board. This merge is read by the dump writer only; nothing in the
        decision path calls it, and the dump is not an input to ``eval/decision_profile.py``.

        The choices are appended AFTER the server frames rather than interleaved: each line
        already carries its own ``rqid``, which is what binds it to a request, so position adds
        nothing and splicing would risk disturbing the server stream the seed proof compares.
        """
        return list(self.room_raw.get(room, [])) + list(self.choose_log.get(room, []))

    async def handle_request(self, room: str, payload: str) -> None:
        req = BattleRequest.model_validate(json.loads(payload))
        if req.wait:
            # Opponent's turn; we've already locked in. Nothing to choose.
            # Deliberately BEFORE the sequence is read: a wait request is not a decision
            # and must not consume an index.
            return
        # [P1] This request's slot in the shared sequence, read BEFORE any work so every
        # sidecar row for THIS decision is stamped with the same number the decision-trace
        # row for this decision carries -- whatever happens further down.
        decision_seq = self._request_seq
        self.last_request[room] = payload
        state = self._state_for(room, req)
        report: list[str] | None = [] if (self.trace and self.agent == "heuristic") else None
        # Build a DecisionTrace only when export OR shadow is enabled and the heuristic is active.
        # With both seams off (self._export is None and self._shadow is None) -> trace_obj=None
        # (bit-identical path — no trace is constructed, choose is unaffected). Decision capture
        # below (Task 4) never widens THIS condition -- it is an ADDITIONAL, independent trigger
        # for the same trace_obj, so export/shadow's own construction is untouched by capture.
        trace_obj = DecisionTrace() if (
            (self._export is not None or self._shadow is not None)
            and self.agent == "heuristic" and state is not None) else None
        # Decision capture (candidate-vs-baseline-diff Task 4, off by default): an independent
        # trigger for the SAME trace_obj. When export/shadow already built one (agent ==
        # "heuristic"), capture reuses it -- one heuristic run, one trace, multiple consumers.
        # When they did not (e.g. hero_agent == "heuristic_reranker", which export/shadow never
        # wire into -- see the explicit `self.agent == "heuristic"` guard on their own observe()
        # calls below), capture builds its OWN trace here so it can see the reranker's real
        # candidates too. `self.decision_trace_writer is None` (the default) makes
        # capture_wants_trace False, so trace_obj is left EXACTLY as computed above --
        # byte-identical to every caller that predates this seam.
        capture_wants_trace = (
            self.decision_trace_writer is not None
            and self.agent in ("heuristic", "heuristic_reranker")
            and state is not None
        )
        # Aggregation trace (2c-Slice-0b Task 3, off by default): a SECOND, INDEPENDENT trigger
        # for the SAME trace_obj, mirroring capture_wants_trace's own shape exactly (same agent/
        # state gate) so the agg-trace sidecar sees real populated candidates for both
        # "heuristic" and "heuristic_reranker". `self.agg_trace_writer is None` (the default)
        # makes agg_wants_trace False, so trace_obj is left EXACTLY as computed by the export/
        # shadow condition above and by capture_wants_trace -- this NEVER widens either of
        # those; it only adds one more independent OR-branch below.
        agg_wants_trace = (
            self.agg_trace_writer is not None
            and self.agent in ("heuristic", "heuristic_reranker")
            and state is not None
        )
        if (capture_wants_trace or agg_wants_trace) and trace_obj is None:
            trace_obj = DecisionTrace()
        prepared_capture = None
        if self.decision_trace_writer is not None:
            from showdown_bot.eval.decision_capture import prepare_capture

            prepared_capture = prepare_capture(state, req, our_spreads=self.our_spreads)
        # Client-owned decision deps (2b-2.5a Kaggle-OOM root-cause fix): built once
        # per battle (heuristic/max_damage/heuristic_reranker only) and threaded into
        # every decision so the core reuses ONE calc instead of spawning a fresh Node
        # server per decision.
        calc, oracle, speed_oracle, dex = self._decision_deps()
        # Client-owned reranker override (2b-4 Task 2): built once per client from env,
        # reusing THIS client's decision-deps dex (just built above) + move_meta. `None`
        # for every agent other than "heuristic_reranker" and when disabled/unavailable
        # (fail-safe -- see agent_choose's heuristic_reranker branch).
        override = self._reranker_override()
        capture_stage_override = None
        capture_reason_override = None
        # Opponent-Mega evidence (I7b-C Task 2, off by default): ONE fresh list per decision,
        # allocated ONLY when this seam's own writer is enabled — with it off, `None` goes down
        # the chain and not a single object is created. The agent gate matches
        # agg_wants_trace's own pair: BOTH heuristic agents run the same
        # choose_with_fallback scorer and therefore score the same foe-Mega hypotheses
        # ([REV.9] finding 2 — an earlier revision excluded "heuristic_reranker" because that
        # branch dropped the sink; the branch now forwards it, and excluding the agent had
        # silently made every reranker decision invisible to the sidecar). Agents that never
        # run that scorer (max_damage models no opponent responses at all) stay out: they could
        # only ever produce an all-empty row, which is a FALSE "this decision generated no
        # foe-Mega hypothesis" claim.
        opp_mega_evidence: list | None = (
            [] if (
                self.opp_mega_trace_writer is not None
                and self.agent in ("heuristic", "heuristic_reranker")
                and state is not None
            ) else None
        )
        opp_mega_agent_ok = True
        # I8-D live profile (off by default): allocate the stage/shape sinks and snapshot the
        # cumulative calc counters ONLY when the writer is on and this is a scored hero decision
        # (team preview writes no profile row; a wait already returned above without an index).
        # The sinks flow INTO agent_choose so the outcome/work-set are recorded inside the same
        # window; the counter snapshots straddle it. No second timer, no serialisation here.
        profile_on = (
            self.decision_profile_writer is not None
            and not req.team_preview
            and self.agent in ("heuristic", "heuristic_reranker")
        )
        # Allocated for EVERY scored decision now, not only when the I8-D profile writer is on:
        # the degraded counter below is what makes a degraded gate run refusable, and it must not
        # depend on an off-by-default sidecar being enabled. Cost is one small dataclass and two
        # scalar assignments; it never touches the returned action.
        profile_stage_sink = SelectionStageSink()
        profile_shape_sink = MegaShapeCounts() if profile_on else None
        profile_before = (
            snapshot_calc_counters(oracle, calc.backend)
            if (profile_on and calc is not None) else None
        )
        agent_crashed = False
        start = time.perf_counter()
        try:
            choose = agent_choose(
                self.agent, req, state=state, book=self.book,
                our_side=req.side.id, priors=self.priors, report=report,
                our_spreads=self.our_spreads, opp_sets=self.opp_sets, trace=trace_obj,
                species_resolver=self._species_type_resolver(),
                calc=calc, oracle=oracle, speed_oracle=speed_oracle, dex=dex,
                override=override,
                format_config=self.format_config,
                opp_mega_evidence_sink=opp_mega_evidence,
                stage_sink=profile_stage_sink,
                shape_sink=profile_shape_sink,
            )
        except Exception as exc:  # noqa: BLE001 - last-ditch, keep the battle alive
            logger.warning("[%s] agent crashed: %s", self.name, exc)
            self.crashes += 1
            choose = f"/choose default|{req.rqid}"
            trace_obj = None  # discard partial trace on crash
            capture_stage_override = "client_exception_default"
            capture_reason_override = "agent_exception"
            # Discard partial foe-Mega evidence for the same reason the trace is discarded:
            # the dispatched choice is a blind `/choose default`, so writing this decision's
            # (possibly empty, possibly half-filled) evidence would misattribute provenance to
            # a decision that never actually completed.
            opp_mega_agent_ok = False
            # I8-D: the crash is classified from THIS flag, never from the (partial) stage sink.
            agent_crashed = True
        # Existing decision-latency window (choice computed, not yet sent) — measured ONCE here
        # so the capture sidecar's decision_latency_ms and self.latencies derive from the exact
        # SAME perf_counter() call; the sidecar latency is never the WebSocket send time.
        decision_latency_ms = (time.perf_counter() - start) * 1000
        # I8-D: snapshot the counters immediately after the window, before the send — the
        # per-decision deltas are after-minus-before around exactly the measured call.
        profile_after = (
            snapshot_calc_counters(oracle, calc.backend)
            if (profile_on and calc is not None) else None
        )
        # Gate B finding 4: classify THIS decision. Deliberately placed AFTER the latency window
        # above -- the I8-D gate measures decision latency against a 1000 ms p95 budget with the
        # frozen evidence at 864.94/873.762 ms (~13% headroom), so per-decision work added
        # between `start` and the `perf_counter()` above would both eat that headroom and make a
        # future run incomparable with the frozen numbers. Nothing here touches the returned
        # action or the measurement. Team preview is excluded (not a calc decision; it marks its
        # own `team_preview` stage), as are the request-only opponent policies, which have no
        # fallback chain to degrade from.
        if not req.team_preview and self.agent in _DEGRADABLE_AGENTS and is_degraded_decision(
            crashed=agent_crashed,
            state_degraded=(state is None),
            selection_stage=profile_stage_sink.selection_stage,
        ):
            self.degraded += 1
        self.latencies.append(decision_latency_ms / 1000)
        self.last_choose[room] = choose
        self._last_choice_decision_index[room] = decision_seq  # Task 6: bind the SENT choice's index
        # Diagnostic: the choice, tagged with the rqid of the request it was COMPUTED FROM. If the
        # server later rejects it against a newer request, the mismatch between this rqid and the
        # one the |error| follows is the stale-dispatch signature -- previously unanswerable,
        # because the room dump carries only the server->client direction.
        self.choose_log.setdefault(room, []).append(f">choose rqid={req.rqid} {choose}")
        await self.conn.send(f"{room}|{choose}")
        # [P1] The request has been answered, so it has consumed its slot -- advance the
        # shared sequence here, BEFORE the sidecar writes below (which already captured
        # `decision_seq`). Advancing here rather than at the end of the method is what makes
        # the sequence robust: a crashed decision, a degraded state, or a dropped sidecar
        # write all still consume exactly one slot, so the NEXT decision is numbered
        # correctly instead of silently reusing this one's index.
        self._request_seq += 1
        # Decision capture: write ONLY after a successful send, and never mutate an
        # already-validated row. Off (writer is None, the default) -> no-op; prepared_capture is
        # already None in that case too, so this is zero new objects, zero behavior change.
        if self.decision_trace_writer is not None:
            from showdown_bot.eval.decision_capture import build_trace_row

            row = build_trace_row(
                context=self.decision_trace_context,
                prepared=prepared_capture,
                request=req,
                choose=choose,
                trace=trace_obj,
                decision_index=self._decision_capture_index,
                decision_latency_ms=decision_latency_ms,
                selection_stage_override=capture_stage_override,
                fallback_reason_override=capture_reason_override,
            )
            self.decision_trace_writer.write(row)
            self._decision_capture_index += 1
        # Aggregation trace (2c-Slice-0b Task 3): write ONLY after a successful send, mirroring
        # decision capture's own placement/discipline exactly -- but a SECOND, INDEPENDENT
        # writer/context/counter, never mutating or reusing decision capture's. Off
        # (self.agg_trace_writer is None, the default) -> no-op: zero new objects, zero
        # behavior change. Reuses trace_obj (built above by EITHER capture_wants_trace OR
        # agg_wants_trace, whichever fired) so a decision that ONLY the agg-trace seam wants
        # still gets a real, populated trace instead of a degenerate None one.
        if self.agg_trace_writer is not None:
            from showdown_bot.research.aggregation_trace import build_agg_row

            try:
                agg_row = build_agg_row(
                    context=self.agg_trace_context,
                    trace=trace_obj,
                    request=req,
                    choose=choose,
                    decision_index=self._agg_trace_index,
                    turn_number=getattr(state, "turn", None),
                )
                self.agg_trace_writer.write(agg_row)
                self._agg_trace_index += 1
            except Exception as exc:  # noqa: BLE001 - agg-trace is best-effort; never stall the battle
                logger.debug(
                    "[%s] agg-trace write failed (decision dropped from sidecar): %s", self.name, exc
                )
        # Opponent-Mega evidence (I7b-C Task 2): write ONLY after a successful send AND only for
        # a decision the agent actually completed, mirroring the two seams above in placement and
        # best-effort discipline but with its OWN writer/context/counter and NO dependence on
        # trace_obj. `opp_mega_evidence is not None` already implies the writer is enabled and
        # the heuristic state path was active, so this is the whole gate. Off -> no-op.
        if opp_mega_evidence is not None and opp_mega_agent_ok:
            from showdown_bot.battle.opponent import DEFAULT_MAX_CANDIDATES, opp_mega_click_rate
            from showdown_bot.eval.opp_mega_trace import build_opp_mega_trace_row

            try:
                opp_mega_row = build_opp_mega_trace_row(
                    context=self.opp_mega_trace_context,
                    # [P1] The request's own sequence number, NOT a count of rows written.
                    decision_index=decision_seq,
                    turn_number=getattr(state, "turn", None),
                    evidence=opp_mega_evidence,
                    max_candidates=DEFAULT_MAX_CANDIDATES,
                    click_rate=opp_mega_click_rate(),
                )
                self.opp_mega_trace_writer.write(opp_mega_row)
                self._opp_mega_rows_written += 1
            except Exception as exc:  # noqa: BLE001 - sidecar is best-effort; never stall the battle
                logger.debug(
                    "[%s] opp-mega-trace write failed (decision dropped from sidecar): %s",
                    self.name, exc,
                )
        # I8-D live decision profile (off by default): build ONE row from the existing signals
        # and write it best-effort AFTER the send, stamped with decision_seq -- the SAME shared
        # index every other sidecar uses. Outcome comes from the authoritative sources only:
        # the crash flag, state-is-None, and the stage sink (never a reconstruction). A dropped
        # write is logged; the battle never stalls.
        if profile_on and profile_before is not None and profile_after is not None:
            from showdown_bot.eval.decision_profile import (
                build_live_profile_row,
                classify_live_outcome,
            )
            try:
                ctx = self.decision_profile_context
                outcome = classify_live_outcome(
                    crashed=agent_crashed,
                    state_degraded=(state is None),
                    selection_stage=(
                        profile_stage_sink.selection_stage
                        if profile_stage_sink is not None else None
                    ),
                )
                row = build_live_profile_row(
                    battle_id=ctx.battle_id, decision_index=decision_seq,
                    schedule_hash=ctx.schedule_hash, config_id=ctx.config_id,
                    format_id=ctx.format_id, git_sha=ctx.git_sha, config_hash=ctx.config_hash,
                    calc_backend=ctx.calc_backend, outcome=outcome,
                    latency_ms=decision_latency_ms,
                    counters_before=profile_before, counters_after=profile_after,
                    shape=profile_shape_sink,
                )
                self.decision_profile_writer.write(row)
            except Exception as exc:  # noqa: BLE001 - best-effort; never stall the battle
                logger.debug(
                    "[%s] decision-profile write failed (row dropped): %s", self.name, exc
                )
        # Export observe: only when trace was built (export enabled, heuristic, non-preview).
        # The explicit `self.agent == "heuristic"` guard (redundant when capture is off, since
        # trace_obj is then non-None only for "heuristic" already) keeps this fully decoupled
        # from decision capture's own, separately-gated trace_obj build for "heuristic_reranker".
        if self._export is not None and trace_obj is not None and self.agent == "heuristic" \
                and not req.team_preview:
            try:
                self._export.observe(
                    trace=trace_obj, state=state, request=req,
                    turn_number=getattr(state, "turn", 0),
                    our_side=req.side.id or "p1",
                )
            except Exception as exc:  # noqa: BLE001 - export is best-effort; never stall the battle
                logger.debug("[%s] export observe failed: %s", self.name, exc)
        # Reranker Shadow observe: post-send, bounded, off the event loop (single-worker executor),
        # LOG-ONLY. SAME condition as export (including the agent guard, for the same decoupling
        # reason) so shadow decision indices stay in lockstep with the export dataset. choose is
        # already computed + sent above; this never mutates it.
        if self._shadow is not None and trace_obj is not None and self.agent == "heuristic" \
                and not req.team_preview:   # SAME cond as export
            sh = self._shadow
            decision_index = sh._decision_local_index
            sh.bump_decision_index()                          # advance synchronously, lockstep with export
            if sh.inflight is not None and not sh.inflight.done():
                logger.debug("[%s] shadow busy -> skip (index kept in lockstep)", self.name)
            else:
                fut = asyncio.get_running_loop().run_in_executor(
                    sh.executor, functools.partial(
                        sh.observe_shadow, trace=trace_obj, state=state, request=req, choose=choose,
                        turn_number=getattr(state, "turn", 0), our_side=req.side.id or "p1",
                        decision_index=decision_index))
                sh.inflight = fut
                try:
                    await asyncio.wait_for(asyncio.shield(fut), timeout=sh.timeout_ms / 1000)
                except asyncio.TimeoutError:
                    logger.debug("[%s] shadow scoring exceeded %dms; 1-worker executor caps orphans at 1",
                                 self.name, sh.timeout_ms)
                except Exception as exc:  # noqa: BLE001 - best-effort; never stall the battle
                    logger.debug("[%s] shadow observe failed: %s", self.name, exc)
        if report is not None and not req.team_preview:
            try:
                from showdown_bot.battle.diagnostics import format_turn_trace

                decision = "\n".join(report) if report else "(no decision report)"
                logger.info(
                    "[%s] %s", self.name, format_turn_trace(self.room_raw.get(room, []), decision)
                )
            except Exception as exc:  # noqa: BLE001 - diagnostics are best-effort
                logger.debug("[%s] trace failed: %s", self.name, exc)

    def close(self) -> None:
        """Idempotent, best-effort: close every calc-owning resource this client
        created and OWNS (2b-2.5a Kaggle-OOM fix — the schedule runner builds a
        fresh hero and villain _Client per battle; each one's live-decision calc /
        export runtime / eval species dex can hold a PersistentCalcBackend Node
        process that otherwise only dies at process exit). The live-decision calc
        (``_decision_calc``) is THE root-cause resource: before this it was never
        even threaded into the decision path, so the core spawned a fresh Node
        server per decision. Called once per run_local_gauntlet invocation, on both
        the success and failure paths (see the caller's try/finally), after the
        battle result is recorded. Never raises -- one resource's close failure
        must not skip the others'.

        2b-2.5a run-scoped fix: a BORROWED export runtime (``owns_export`` False)
        must NOT be closed here — it spans multiple battles and the caller
        (cli.run_schedule) owns its lifecycle, closing it once after the whole
        schedule finishes."""
        if self._export is not None and self.owns_export:
            try:
                self._export.close()
            except Exception as exc:  # noqa: BLE001
                logger.debug("[%s] export close failed: %s", self.name, exc)
        if self._eval_species_dex is not None:
            try:
                self._eval_species_dex.close()
            except Exception as exc:  # noqa: BLE001
                logger.debug("[%s] eval species dex close failed: %s", self.name, exc)
        # 2b-2.5a root-cause fix: tear down the client-owned live-decision calc
        # (one Node server per battle now, instead of ~70). Idempotent, best-effort.
        if self._decision_calc is not None:
            try:
                self._decision_calc.close()
            except Exception as exc:  # noqa: BLE001
                logger.debug("[%s] decision calc close failed: %s", self.name, exc)


async def _run_client(
    client: _Client,
    *,
    accept_from: str | None,
    on_result,
    stop: asyncio.Event,
) -> None:
    await client.set_team()
    try:
        async for raw in client.conn.messages():
            if stop.is_set():
                break
            parsed_list = list(parse_incoming(raw))
            for room in {p.room for p in parsed_list if p.room.startswith("battle-")}:
                client.room_raw.setdefault(room, []).append(raw)
            for parsed in parsed_list:
                # Never let a single bad frame kill the loop and stall the game.
                try:
                    if parsed.prefix == "pm" and parsed.args and accept_from:
                        # Challenge PM: |pm| sender| receiver|/challenge <format>|...
                        # "/challenge" is not in the trailing arg, so scan all args.
                        joined = "|".join(a or "" for a in parsed.args)
                        sender = (parsed.args[0] or "").strip().lower()
                        if "/challenge" in joined and accept_from.lower() in sender:
                            await client.conn.send(f"|/accept {accept_from}")
                    if parsed.prefix == "pm" and parsed.args and _is_real_invalid(parsed.args[-1]):
                        client._note_invalid_choice(parsed.room)
                    if parsed.room.startswith("battle-"):
                        if parsed.prefix == "init" and parsed.args and parsed.args[0] == "battle":
                            await client.conn.send(f"|/join {parsed.room}")
                            if client._export is not None:
                                client._export.start_game()
                            if client._shadow is not None:
                                client._shadow.start_game()
                        if parsed.prefix == "error":
                            err_text = parsed.args[0] if parsed.args else ""
                            if _is_real_invalid(err_text):
                                client._note_invalid_choice(parsed.room)
                                logger.warning(
                                    "[%s] INVALID CHOICE in %s: server=%r | sent=%r | request=%s",
                                    client.name, parsed.room, err_text,
                                    client.last_choose.get(parsed.room),
                                    client.last_request.get(parsed.room, "")[:400],
                                )
                        if parsed.prefix == "request":
                            await client.handle_request(parsed.room, parsed.payload)
                        if parsed.prefix in ("win", "tie"):
                            winner = parsed.args[0].strip() if (parsed.prefix == "win" and parsed.args) else None
                            # Snapshot frames BEFORE pop (T2 result parse + T1a dump both need them).
                            room_frames = client.dump_frames(parsed.room)
                            room_raw_path = None
                            # T1a seed-proof: env-gated raw dump. Unset -> no-op (bit-identical path).
                            _dump_dir = os.environ.get("SHOWDOWN_ROOM_RAW_DUMP")
                            if _dump_dir:
                                try:
                                    from showdown_bot.eval.room_dump import dump_room_raw

                                    room_raw_path = dump_room_raw(_dump_dir, client.name, parsed.room, room_frames)
                                except Exception as exc:  # noqa: BLE001 - diagnostic dump is best-effort
                                    logger.debug("[%s] room_raw dump failed: %s", client.name, exc)
                            client.room_raw.pop(parsed.room, None)
                            client.choose_log.pop(parsed.room, None)
                            if client._export is not None:
                                client._export.flush()
                            if on_result is not None:
                                await on_result(winner, room_frames, room_raw_path)
                except Exception as exc:  # noqa: BLE001 - keep the loop alive
                    logger.warning("[%s] frame error (%s): %s", client.name, parsed.prefix, exc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] client loop error: %s", client.name, exc)


def _load_belief_deps(format_id: str):
    """Load ``(format_config, book, priors, opp_sets)`` for ``format_id``.

    ``format_config`` is loaded from the format yaml even when spread/prior meta
    files fail; ``book``/``priors`` remain best-effort. When ``book`` is ``None``,
    ``agent_choose`` short-circuits to the random agent (``book is None`` guard),
    so ``format_config`` is not forwarded and format flags (e.g. ``tera``) are
    not applied on that path."""
    cfg = None
    book = None
    priors = None
    try:
        cfg = load_format_config(format_id)
    except Exception:  # noqa: BLE001
        pass
    if cfg is not None:
        try:
            book = load_spread_book(cfg.meta_path("default_spreads"))
            from showdown_bot.engine.belief.protect_priors import load_protect_priors

            priors = load_protect_priors(cfg.meta_path("protect_priors"))
        except Exception:  # noqa: BLE001
            pass
    opp_sets = load_opp_sets_for_format(format_id)
    return cfg, book, priors, opp_sets


def _is_mirror_battle(team_path: str, opp_team_path: str | None) -> bool:
    """True when the villain fields the SAME team as the hero.

    Matches ``_resolve_side_teams``'s own definition of "mirror": a missing/empty
    ``opp_team_path`` means the villain reuses the hero's packed team (mirror); an explicit but
    IDENTICAL path is also a mirror. A distinct path is non-mirror. Pure string comparison —
    2b-2.5a wiring fix: the real per-battle ``mirror_flag``, replacing the pre-fix hardcoded
    ``False`` at both ``DatasetExportRuntime`` construction sites in this module.
    """
    return not opp_team_path or opp_team_path == team_path


def build_schedule_export_runtime(format_id: str, hero_team_path: str, villain_team_path: str | None = None):
    """Build ONE run-scoped ``DatasetExportRuntime`` for a whole ``cli.run_schedule`` call
    (2b-2.5a fix: ``run_schedule`` plays each row as a separate ``run_local_gauntlet(games=1)``
    call; before this, each call's hero built+closed its OWN runtime pointed at the same
    ``SHOWDOWN_DATASET_EXPORT`` path, so every battle's flush overwrote the previous battle's
    rows — only the last battle in a schedule ever survived to disk).

    Returns ``None`` when ``SHOWDOWN_DATASET_EXPORT`` is unset (``from_env``'s own gate) — the
    caller passes that straight through as ``run_local_gauntlet(export_runtime=None)``, which
    then means "export disabled" for every row in the schedule (no per-row build attempt).

    Mirrors the deps a hero ``_Client`` would build for itself inside a single
    ``run_local_gauntlet`` call (book/priors/opp_sets via ``_load_belief_deps``, our_spreads via
    ``our_spreads_from_packed`` gated by ``SHOWDOWN_REAL_SPREADS``) so passing this ONE runtime
    through N sequential calls produces the same per-decision rollout labels the old (broken)
    per-battle runtime would have — just accumulated into a single file instead of N
    overwriting ones. ``hero_team_path`` is resolved via ``_resolve_side_teams`` (mirror lookup
    with no opponent path) so a bad/missing team degrades to ``""`` the same way the per-battle
    path already tolerates.

    ``villain_team_path`` (2b-2.5a wiring fix, optional): the representative row's villain team
    path, used to seed this shared runtime's INITIAL ``mirror_flag`` via ``_is_mirror_battle``.
    Schedule rows can each field a DIFFERENT villain, so this initial value only covers the
    window before the first battle starts — ``_Client.__init__`` refreshes ``mirror_flag`` on
    this SAME shared runtime for every subsequent battle via its own ``is_mirror`` param (the
    per-battle update seam; see the comment at that assignment). ``None`` (the pre-existing
    2-arg call shape) matches ``_resolve_side_teams``'s own "no opp path -> mirror" convention.

    Also builds a RUN-scoped ``move_meta`` (``_move_table()`` — data-driven, memoized via
    ``functools.lru_cache``, cheap to call repeatedly) and a RUN-scoped ``SpeciesDex()`` (its own
    default ``SubprocessCalcBackend`` — one-shot ``node`` per lookup batch, memoized cache, no
    persistent process to leak) so the move/species feature columns that were unconditionally
    sentinel (``dex=None``, ``move_meta=None`` hardcoded here) get populated. This dex is
    intentionally independent of any per-battle calc client: those are built + closed once PER
    BATTLE (``_Client._decision_deps`` / ``close()``), but this runtime — and its dex — persist
    across the WHOLE schedule.
    """
    cfg, book, priors, opp_sets = _load_belief_deps(format_id)
    hero_packed, _ = _resolve_side_teams(hero_team_path)
    _real = os.environ.get("SHOWDOWN_REAL_SPREADS", "1") != "0"
    our_spreads = our_spreads_from_packed(hero_packed) if (hero_packed and _real) else None
    return DatasetExportRuntime.from_env(
        format_id=format_id,
        packed_team=hero_packed,
        mirror_flag=_is_mirror_battle(hero_team_path, villain_team_path),
        dex=SpeciesDex(),
        move_meta=_move_table(),
        book=book,
        our_spreads=our_spreads,
        opp_sets=opp_sets,
        priors=priors,
    )


def _resolve_side_teams(team_path, opp_team_path=None):
    """Return ``(hero_packed, villain_packed)`` for the gauntlet.

    ``opp_team_path=None`` -> **mirror** (villain gets the hero's packed team; the
    original single-team behavior). A distinct ``opp_team_path`` -> non-mirror (T1c).
    Load failures degrade to ``""`` (same tolerance as the original single-team path).
    """
    def _load(path):
        try:
            return load_packed_team(path)
        except Exception:  # noqa: BLE001
            return ""

    hero_packed = _load(team_path)
    villain_packed = _load(opp_team_path) if opp_team_path else hero_packed
    return hero_packed, villain_packed


def _end_hp_diff(parsed, hero_name, villain_name):
    """Hero-side HP sum − villain-side HP sum, via the |player| slot map. None if unreliable."""
    hp = parsed.get("hp_by_slot")
    players = parsed.get("players") or {}
    if not hp:
        return None
    slot_of = {name: slot for slot, name in players.items()}
    hs, vs = slot_of.get(hero_name), slot_of.get(villain_name)
    if hs not in ("p1", "p2") or vs not in ("p1", "p2") or hs == vs:
        return None  # side mapping unreliable -> null, never a blind p1-p2 (T2 Fix 2)
    return round(hp[hs] - hp[vs], 6)


def _normalized_room_log_sha256(frames) -> str | None:
    """sha256 hex over the normalized room log (T4c R1: binds a result row to its log).

    Delegates to ``eval.room_dump.normalized_room_log_sha256`` -- the single shared recipe
    both this write site and the ``eval.report`` re-derivation path (T4c R2, which reads the
    frames back from a dumped log via ``eval.room_dump.read_room_log_frames``) use, so the two
    can never silently drift apart. See that function's docstring for the exact recipe.

    Computed in-process at the write site (frames are already in hand -- no re-read from
    disk). Never raises: any exception degrades to ``None`` (never fails the battle
    record), with a debug log for diagnosis.
    """
    try:
        return _compute_normalized_room_log_sha256(frames)
    except Exception as exc:  # noqa: BLE001 - a hash failure must never fail the battle record
        logger.debug("[battle-result] normalized_room_log_sha256 computation failed: %s", exc)
        return None


def _battle_result_record(hero_name, villain_name, frames, *, invalid_choices, crashes,
                          decision_latency_p95_ms, room_raw_path,
                          hero_degraded_decisions=0, villain_degraded_decisions=0):
    """Assemble the battle-derived T2 fields with EXPLICIT hero/villain/tie mapping (Fix 2).

    Unknown winner -> ResultRowError (never guessed). ``end_hp_diff`` is hero-side minus
    villain-side, or None if the |player| slot mapping is unreliable.
    """
    from showdown_bot.eval.battle_parse import parse_battle_result
    from showdown_bot.eval.result_jsonl import ResultRowError

    p = parse_battle_result(frames)
    if p["is_tie"]:
        winner = "tie"
    elif p["winner_name"] == hero_name:
        winner = "hero"
    elif p["winner_name"] == villain_name:
        winner = "villain"
    else:
        raise ResultRowError(
            f"winner {p['winner_name']!r} matches neither hero {hero_name!r} nor villain {villain_name!r}"
        )
    return {
        "winner": winner,
        "turns": p["turns"],
        "end_reason": p["end_reason"],  # T3f Task 5: normal/timeout/forfeit/crash from room_raw
        "end_hp_diff": _end_hp_diff(p, hero_name, villain_name),
        "invalid_choices": invalid_choices,
        "crashes": crashes,
        # Gate B finding 4: decisions that did NOT complete on the agent's intended path. A
        # non-zero count means the seat answered with a fallback -- legal, but not computed.
        "hero_degraded_decisions": hero_degraded_decisions,
        "villain_degraded_decisions": villain_degraded_decisions,
        "decision_latency_p95_ms": decision_latency_p95_ms,
        "room_raw_path": room_raw_path,
        # T4c R1: binds this row to its room log; None on any hashing failure (never
        # fails the battle record) -- see _normalized_room_log_sha256 for the recipe.
        "normalized_room_log_sha256": _normalized_room_log_sha256(frames),
    }


def _effective_battle_timeout(games: int, battle_timeout_s: float | None, env) -> float:
    """Resolve the per-battle gauntlet timeout in seconds (2b-2.5a, 2026-07-11).

    Precedence: the explicit ``battle_timeout_s`` param (if not ``None``) > the
    ``SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S`` env var (if set to a float > 0) > the pre-existing
    formula ``max(180.0, games * 150.0)``. The formula is always the final fallback -- a guard
    against truly endless games -- so this function never returns "unlimited".

    Pure + injectable: ``env`` is a plain mapping (production passes a dict sourced from
    ``os.environ``), so the precedence logic is unit-testable without mutating real process env
    vars.
    """
    if battle_timeout_s is not None:
        return float(battle_timeout_s)
    raw = env.get("SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S", "") if env else ""
    if raw:
        try:
            parsed = float(raw)
        except (TypeError, ValueError):
            parsed = 0.0
        if parsed > 0:
            return parsed
    return max(180.0, games * 150.0)


async def run_local_gauntlet(
    *,
    games: int,
    hero_agent: str = "heuristic",
    villain_agent: str = "max_damage",
    format_id: str,
    team_path: str,
    opp_team_path: str | None = None,
    server_url: str = LOCAL_SERVER,
    hero_name: str = "HeuristicBot",
    villain_name: str = "BaselineBot",
    on_battle_result=None,
    export_runtime=None,
    battle_timeout_s: float | None = None,
    decision_trace_writer=None,
    decision_trace_context=None,
    agg_trace_writer=None,
    agg_trace_context=None,
    opp_mega_trace_writer=None,
    opp_mega_trace_context=None,
    decision_profile_writer=None,
    decision_profile_context=None,
) -> GauntletStats:
    """Play ``games`` battles between two local bots and return aggregate stats.

    ``opp_team_path`` (T1c): when given, the villain fields a **different** packed team
    (non-mirror); default ``None`` keeps the mirror behavior. ``on_battle_result`` (T2):
    when given, a callback is fired once per battle with the assembled battle record
    (default ``None`` -> no behavior change). ``export_runtime`` (2b-2.5a run-scoped fix):
    when given, the HERO client BORROWS it (does not build or close its own runtime) — the
    caller (cli.run_schedule) owns its lifecycle across multiple sequential calls so a
    schedule's battles all land in one file instead of each call's flush overwriting the
    last. Default ``None`` preserves the plain ``--games N`` path unchanged: the hero builds
    and owns (and closes) its own runtime spanning this call's games, gated on
    ``SHOWDOWN_DATASET_EXPORT`` as before. The VILLAIN client NEVER builds or borrows an
    export runtime, in either mode — an explicit hero-only contract (a "heuristic" villain
    is a valid opponent policy and would otherwise independently export its own decisions to
    the same path, racing the hero's flushes). ``battle_timeout_s`` (2b-2.5a, 2026-07-11): see
    ``_effective_battle_timeout`` for the full precedence rule (param > env > formula) — this
    knob exists because rollout-teacher datagen makes some legitimate long stall games exceed
    the flat 180s budget. Requires a local
    ``node pokemon-showdown start --no-security`` server.

    2b-2.5a wiring fix: this function already knows both ``team_path`` and ``opp_team_path``, so
    the real ``mirror_flag`` (``_is_mirror_battle``) is derived here and threaded into the hero
    ``_Client`` as ``is_mirror`` -- it reaches the export runtime either at construction (owned
    runtime) or via a per-battle refresh (borrowed/run-scoped runtime; see the
    ``self._export.mirror_flag = is_mirror`` assignment in ``_Client.__init__``).

    ``decision_trace_writer``/``decision_trace_context`` (candidate-vs-baseline-diff Task 4,
    off by default): an optional per-decision capture sidecar for the HERO client only (the
    villain never receives either -- an explicit hero-only contract, mirroring
    ``export_runtime``'s). Exactly one of the two being given is a caller bug -- raises
    ``ValueError`` -- since a writer with no battle context (or vice versa) can't produce a
    valid, bound trace row. A context implies exactly one battle is being played, so it also
    requires ``games == 1``. Both ``None`` (the default) is byte-identical to every caller that
    predates this seam: neither client ever sees a non-None writer/context, so
    ``_Client.handle_request`` never builds a capture ``DecisionTrace``, never calls
    ``prepare_capture``/``build_trace_row``, and the dispatched ``/choose`` messages are
    unchanged.

    ``agg_trace_writer``/``agg_trace_context`` (2c-Slice-0b Task 3, off by default): a SECOND,
    INDEPENDENT optional per-decision full-fidelity aggregation-trace sidecar (see
    ``research/aggregation_trace.py``) — same hero-only contract and the same pairing/``games
    == 1`` validation as ``decision_trace_writer``/``decision_trace_context`` above, but fully
    independent of it: either, both, or neither may be given, and each writes to its own file
    with its own per-decision counter. Both ``None`` (the default) is likewise byte-identical:
    the hero client never sees a non-None agg writer/context, so ``_Client.handle_request``
    never builds a ``DecisionTrace`` for THIS trigger, never calls ``build_agg_row``, and the
    dispatched ``/choose`` messages are unchanged.

    ``opp_mega_trace_writer``/``opp_mega_trace_context`` (I7b-C Task 2 Step 6, off by
    default): a THIRD, INDEPENDENT optional per-decision sidecar recording which foe-Mega
    hypotheses were generated AND scored (see ``eval/opp_mega_trace.py``) — same hero-only
    contract and the same pairing/``games == 1`` validation as the two seams above, and
    likewise independent of both. Unlike them it needs no ``DecisionTrace`` at all: its
    evidence comes from the scoring call's own ``opp_mega_evidence_sink``. Both ``None``
    (the default) is byte-identical: the hero client allocates no evidence list, passes an
    explicit ``None`` down the chain, and the dispatched ``/choose`` messages are unchanged.

    ``decision_profile_writer``/``decision_profile_context`` (I8-D, off by default): a FOURTH,
    INDEPENDENT optional sidecar -- one live decision-profile row per SCORED hero decision
    (see ``eval/decision_profile.py``), stamped with the shared decision index and the
    per-battle ``LiveProfileContext``. Same hero-only contract and the same pairing /
    ``games == 1`` validation as the seams above. Both ``None`` (the default) is
    byte-identical: the hero client builds no row, allocates no sinks, and the dispatched
    ``/choose`` messages are unchanged.
    """
    if (decision_trace_writer is None) != (decision_trace_context is None):
        raise ValueError(
            "decision_trace_writer and decision_trace_context must be given together"
        )
    if decision_trace_context is not None and games != 1:
        raise ValueError("decision_trace_context requires games == 1")
    if (agg_trace_writer is None) != (agg_trace_context is None):
        raise ValueError(
            "agg_trace_writer and agg_trace_context must be given together"
        )
    if (opp_mega_trace_writer is None) != (opp_mega_trace_context is None):
        raise ValueError(
            "opp_mega_trace_writer and opp_mega_trace_context must be given together"
        )
    if opp_mega_trace_context is not None and games != 1:
        raise ValueError("opp_mega_trace_context requires games == 1")
    if (decision_profile_writer is None) != (decision_profile_context is None):
        raise ValueError(
            "decision_profile_writer and decision_profile_context must be given together"
        )
    if decision_profile_context is not None and games != 1:
        raise ValueError("decision_profile_context requires games == 1")
    if agg_trace_context is not None and games != 1:
        raise ValueError("agg_trace_context requires games == 1")
    cfg, book, priors, opp_sets = _load_belief_deps(format_id)
    hero_packed, villain_packed = _resolve_side_teams(team_path, opp_team_path)
    is_mirror = _is_mirror_battle(team_path, opp_team_path)

    # Unique names per run so a killed run's lingering battles aren't rejoined
    # (with --no-security, /trn re-attaches to the same user and its open games).
    import random

    suffix = f"{random.randint(1000, 9999)}"
    hero_name = f"{hero_name}{suffix}"
    villain_name = f"{villain_name}{suffix}"

    hero_conn = ShowdownConnection(server_url)
    villain_conn = ShowdownConnection(server_url)
    await hero_conn.connect()
    await villain_conn.connect()
    await authenticate_local(hero_conn, hero_name)
    await authenticate_local(villain_conn, villain_name)

    trace = os.environ.get("SHOWDOWN_TURN_TRACE", "0") == "1"
    hero = _Client(hero_conn, hero_name, hero_agent, book=book, priors=priors, format_id=format_id,
                   format_config=cfg, packed_team=hero_packed, trace=trace, opp_sets=opp_sets,
                   export_runtime=export_runtime, allow_own_export=True, is_mirror=is_mirror,
                   decision_trace_writer=decision_trace_writer,
                   decision_trace_context=decision_trace_context,
                   agg_trace_writer=agg_trace_writer,
                   agg_trace_context=agg_trace_context,
                   opp_mega_trace_writer=opp_mega_trace_writer,
                   opp_mega_trace_context=opp_mega_trace_context,
                   decision_profile_writer=decision_profile_writer,
                   decision_profile_context=decision_profile_context)
    # The villain deliberately receives NO opp-mega or decision-profile writer/context (same
    # hero-only contract as export_runtime and both trace seams): its decisions are the
    # opponent policy's, not the bot under test, so neither its foe-Mega hypotheses nor its
    # per-decision latency are the evidence these sidecars are about.
    villain = _Client(villain_conn, villain_name, villain_agent, book=book, priors=priors, format_id=format_id,
                       format_config=cfg, packed_team=villain_packed, opp_sets=opp_sets,
                       export_runtime=None, allow_own_export=False)

    stats = GauntletStats()
    # Per-battle counter deltas (T3e-P0): the row for battle N must carry battle N's
    # invalid/crashes/latency-p95, not the run-lifetime cumulative totals on the clients.
    per_battle = _PerBattleCounters()
    stop = asyncio.Event()
    next_game = asyncio.Event()
    next_game.set()  # allow first challenge

    async def on_hero_result(winner, room_frames=None, room_raw_path=None):
        if not room_frames:
            return
        stats.games += 1
        if winner is None:
            stats.ties += 1
        elif winner.lower().startswith(hero_name.lower()[:6]):
            stats.hero_wins += 1
        else:
            stats.villain_wins += 1
        logger.info("game %d/%d done (winner=%s)", stats.games, games, winner)
        # T2 per-battle result: build + emit the record. Counters are per-battle deltas
        # (T3e-P0) so a multi-battle run reports each row's own invalid/crashes/latency, not
        # the run-lifetime cumulative totals. Best-effort: a bad record is logged, never stalls
        # progression; a missing row then trips the runner's row-count == len(rows) check.
        if on_battle_result is not None and room_frames is not None:
            try:
                # Advance the per-battle watermark first (T3e-P0): even if record assembly
                # raises for this battle, its counts are "spent" and must not leak into the
                # next row. Deltas are the finishing battle's counts, not the run totals.
                deltas = per_battle.emit(
                    invalid=hero.invalid + villain.invalid,
                    crashes=hero.crashes + villain.crashes,
                    latencies=hero.latencies,
                    hero_degraded=hero.degraded,
                    villain_degraded=villain.degraded,
                )
                record = _battle_result_record(
                    hero.name, villain.name, room_frames,
                    invalid_choices=deltas["invalid_choices"],
                    crashes=deltas["crashes"],
                    decision_latency_p95_ms=deltas["decision_latency_p95_ms"],
                    room_raw_path=room_raw_path,
                    hero_degraded_decisions=deltas["hero_degraded_decisions"],
                    villain_degraded_decisions=deltas["villain_degraded_decisions"],
                )
                on_battle_result(record)
            except Exception as exc:  # noqa: BLE001 - never stall the run; runner row-count catches it
                logger.warning("[battle-result] record/emit failed: %s", exc)
        if stats.games >= games:
            stop.set()
        else:
            next_game.set()

    hero_task = asyncio.create_task(
        _run_client(hero, accept_from=None, on_result=on_hero_result, stop=stop)
    )
    villain_task = asyncio.create_task(
        _run_client(villain, accept_from=hero_name, on_result=None, stop=stop)
    )

    async def challenger():
        await villain.set_team()
        await asyncio.sleep(0.5)
        while not stop.is_set():
            await next_game.wait()
            next_game.clear()
            if stop.is_set():
                break
            await hero.set_team()
            await asyncio.sleep(0.2)
            await hero_conn.send(f"|/challenge {villain_name}, {format_id}")
            await asyncio.sleep(0.2)

    chal_task = asyncio.create_task(challenger())

    try:
        # VGC games run ~15-25 turns and each decision can take a couple seconds (Node calc per
        # turn), so budget generously per game via the formula below. SHOWDOWN_GAUNTLET_BATTLE_
        # TIMEOUT_S (2026-07-11) overrides it: rollout-teacher datagen labels every decision
        # (~3-4s each), so legitimate 50+-turn stall wars (e.g. sun_dev vs rain_dev tail cells)
        # can exceed the flat 180s budget even on a healthy VM (the leak fix alone wasn't
        # enough) -- datagen kernels set it to 900s. A timeout is still always applied (never
        # unlimited) as a guard against truly endless games.
        battle_timeout = _effective_battle_timeout(
            games, battle_timeout_s,
            {"SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S": os.environ.get("SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S", "")},
        )
        await asyncio.wait_for(stop.wait(), timeout=battle_timeout)
    except asyncio.TimeoutError:
        logger.warning("gauntlet timed out")
        stop.set()
    finally:
        for t in (chal_task, hero_task, villain_task):
            t.cancel()
        await hero_conn.close()
        await villain_conn.close()
        # 2b-2.5a Kaggle-OOM fix: release calc-owning resources (export runtime's
        # rollout CalcClient, eval species dex) per battle -- success AND failure
        # paths -- so the schedule runner's 75 sequential run_local_gauntlet(games=1)
        # calls don't leak a Node process per hero/villain client per battle.
        hero.close()
        villain.close()

    stats.latencies = hero.latencies
    stats.invalid_choices = hero.invalid + villain.invalid
    # Task 6: the HERO seat's own invalid-choice decision indices (never the villain's) -- the
    # per-seat, foe-Mega-bindable safety signal, in-memory only (off the closed T2 row).
    stats.hero_invalid_decision_indices = tuple(hero._invalid_decision_indices)
    stats.crashes = hero.crashes + villain.crashes
    return stats
