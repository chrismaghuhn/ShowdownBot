"""The testable seam between the live client and the export pipeline (slice 1b-B3).

`DatasetExportRuntime` holds one `DatasetExporter` (or None), a `LabelProvider`,
and the rollout deps.  It calls start_game/observe/flush.  All env setup,
provenance, counters, provider dispatch, and the driver call live here so
they can be tested without Node/WebSocket.

Slice 1d-3 additions:
  - ``provider`` parameter (StubLabelProvider or RolloutLabelProvider)
  - Skip counters (``sampled_count`` / ``skipped_count``) + hard-fail threshold
  - ``from_env`` reads SHOWDOWN_DATASET_TEACHER ("stub"|"rollout"); rollout mode
    builds a CalcClient + full deps bundle and extends config_hash.
  - ``observe`` gates on SamplingPolicy, catches ONLY RolloutLabelError.
"""

from __future__ import annotations

import logging
import os

from showdown_bot.learning.export import DatasetExporter, SamplingPolicy
from showdown_bot.learning.export_driver import maybe_observe_decision
from showdown_bot.learning.label_provider import StubLabelProvider
from showdown_bot.learning.provenance import (
    build_feature_context, canonical_hash, config_hash,
    git_sha_and_dirty, team_hash,
)
from showdown_bot.learning.rollout import RolloutLabelError

logger = logging.getLogger(__name__)

_HEURISTIC_KNOBS = (
    "SHOWDOWN_PROTECT_PENALTY", "SHOWDOWN_REAL_SPREADS", "SHOWDOWN_OPP_SETS",
    "SHOWDOWN_OPP_SPEED", "SHOWDOWN_MUST_REACT_LAMBDA", "SHOWDOWN_ROLLOUT_HORIZON",
)


class DatasetExportRuntime:
    def __init__(
        self,
        exporter,
        export_path,
        *,
        git_sha,
        dirty_flag,
        team_hash_,
        config_hash_,
        run_seed,
        format_id,
        mirror_flag,
        sampling_policy_name,
        provider=None,
        dex=None,
        move_meta=None,
        protect_priors_by_opp_slot=None,
    ):
        self.exporter = exporter
        self.export_path = export_path
        self.git_sha = git_sha
        self.dirty_flag = dirty_flag
        self.team_hash_ = team_hash_
        self.config_hash_ = config_hash_
        self.run_seed = run_seed
        self.format_id = format_id
        self.mirror_flag = mirror_flag
        self.sampling_policy_name = sampling_policy_name
        self.dex = dex
        self.move_meta = move_meta
        self.protect_priors_by_opp_slot = protect_priors_by_opp_slot

        # LabelProvider — defaults to StubLabelProvider if not supplied.
        self._provider = provider if provider is not None else StubLabelProvider()
        # teacher_config is derived from the provider (run-level, immutable).
        self.teacher_config = self._provider.teacher_config()

        # Skip counters and hard-fail threshold.
        self.sampled_count: int = 0
        self.skipped_count: int = 0
        self.max_skip_rate: float = 0.05
        self.min_sampled: int = 20

        # Decision indices.
        self._game_index = -1           # first start_game -> 0
        self._decision_local_index = 0  # per-game (decision_id)
        self._sampling_decision_index = 0  # global run-level (SamplingPolicy)

    @classmethod
    def from_env(
        cls,
        *,
        format_id: str,
        packed_team: str,
        mirror_flag: bool,
        provider=None,
        dex=None,
        move_meta=None,
        protect_priors_by_opp_slot=None,
        # Rollout deps — threaded in by gauntlet so we don't build a second CalcClient.
        calc=None,
        book=None,
        our_spreads=None,
        opp_sets=None,
    ):
        """Build a DatasetExportRuntime from environment variables.

        Returns None when SHOWDOWN_DATASET_EXPORT is not set (bit-identical path).

        Reads:
          SHOWDOWN_DATASET_EXPORT       — output file path (required to enable)
          SHOWDOWN_DATASET_RUN_SEED     — int seed (default 0)
          SHOWDOWN_DATASET_SAMPLE_POLICY — "all" | "every_nth" (default "all")
          SHOWDOWN_DATASET_SAMPLE_RATE  — int rate for every_nth (default 1)
          SHOWDOWN_DATASET_TEACHER      — "stub" | "rollout" (default "stub")
          SHOWDOWN_ROLLOUT_HORIZON      — int H for rollout mode (default 4)

        If ``provider`` is passed explicitly, it takes precedence over the env-derived
        mode.  This is the test injection path.
        """
        path = os.environ.get("SHOWDOWN_DATASET_EXPORT")
        if not path:
            return None  # env off -> exporter stays None (gate: bit-identical)

        seed = int(os.environ.get("SHOWDOWN_DATASET_RUN_SEED", "0"))
        policy = os.environ.get("SHOWDOWN_DATASET_SAMPLE_POLICY", "all")
        rate = int(os.environ.get("SHOWDOWN_DATASET_SAMPLE_RATE", "1"))
        git_sha, dirty = git_sha_and_dirty()
        th = team_hash(packed_team)

        # config_hash = dataset-semantic config ONLY (NOT the output path).
        cfg_dict = {"sample_policy": policy, "sample_rate": rate, "top_k": 6, "team_hash": th}
        cfg_dict.update({k: os.environ.get(k) for k in _HEURISTIC_KNOBS})

        # Determine provider (explicit injection wins over env mode).
        if provider is None:
            mode = os.environ.get("SHOWDOWN_DATASET_TEACHER", "stub")
            if mode == "rollout":
                provider = cls._build_rollout_provider(
                    format_id=format_id,
                    dex=dex,
                    move_meta=move_meta,
                    calc=calc,
                    book=book,
                    our_spreads=our_spreads,
                    opp_sets=opp_sets,
                    cfg_dict=cfg_dict,  # mutated in-place with rollout hashes
                )
            else:
                provider = StubLabelProvider()
                # Stub mode: cfg_dict stays unchanged -> same config_hash as pre-1d.

        ch = config_hash(cfg_dict)
        exp = DatasetExporter(SamplingPolicy(policy=policy, rate=rate, seed=seed))
        return cls(
            exp,
            path,
            git_sha=git_sha,
            dirty_flag=dirty,
            team_hash_=th,
            config_hash_=ch,
            run_seed=seed,
            format_id=format_id,
            mirror_flag=mirror_flag,
            sampling_policy_name=policy,
            provider=provider,
            dex=dex,
            move_meta=move_meta,
            protect_priors_by_opp_slot=protect_priors_by_opp_slot,
        )

    @staticmethod
    def _build_rollout_provider(
        *,
        format_id: str,
        dex,
        move_meta,
        calc,
        book,
        our_spreads,
        opp_sets,
        cfg_dict: dict,
    ):
        """Build a RolloutLabelProvider and extend cfg_dict with rollout hashes.

        Mirrors battle/decision.py:182-186 for the deps construction:
          calc = calc or CalcClient()
          oracle = DamageOracle(calc)
          speed_oracle = SpeedOracle(stats_backend=calc.backend)

        All _CORE_DEP_KEYS (decide_adapter.py:32-34) are included:
          book, calc, oracle, speed_oracle, dex, priors, weights,
          risk_lambda, tera_margin, rollout_horizon, our_spreads, opp_sets
        Plus move_meta (needed by rollout_labels).

        risk_lambda=0.5 and tera_margin=1.0 mirror decision.py:156-157 defaults exactly.
        rollout_horizon=0 suppresses the inner condition-rollout (see deps comment below).
        """
        from showdown_bot.battle.oracle import DamageOracle
        from showdown_bot.engine.calc.client import CalcClient
        from showdown_bot.engine.speed import SpeedOracle
        from showdown_bot.learning.label_provider import RolloutLabelProvider
        from showdown_bot.engine.belief.hypotheses import load_opp_sets_for_format
        from showdown_bot.engine.belief.move_priors import load_move_priors_for_format
        from showdown_bot.learning.teacher import RolloutConfig

        # Mirror decision.py:182-186: build calc/oracle/speed_oracle if not provided.
        if calc is None:
            calc = CalcClient()
        oracle = DamageOracle(calc)
        try:
            speed_oracle = SpeedOracle(stats_backend=calc.backend)
        except Exception:  # noqa: BLE001
            speed_oracle = None

        H = int(os.environ.get("SHOWDOWN_ROLLOUT_HORIZON", "4"))
        cfg = RolloutConfig(H=H)

        # Load likely_sets and move_priors for this format.
        likely_sets = load_opp_sets_for_format(format_id)
        move_priors = load_move_priors_for_format(format_id)

        # Full deps dict mirroring _CORE_DEP_KEYS + move_meta.
        deps = {
            "book": book,
            "calc": calc,
            "oracle": oracle,
            "speed_oracle": speed_oracle,
            "dex": dex,
            "move_meta": move_meta or {},
            "our_spreads": our_spreads,
            "opp_sets": opp_sets if opp_sets is not None else {},
            # priors/weights: None matches decision.py defaults; priors threading from
            # the gauntlet is a documented v1 gap — the rollout's inner opponent model
            # omits Protect priors (decision.py also defaults weights=None).
            "priors": None,
            "weights": None,
            # Mirror decision.py:156-157 defaults exactly.
            "risk_lambda": 0.5,
            "tera_margin": 1.0,
            # rollout_horizon=0 (not decision.py's None→~2): the H-loop is the outer
            # rollout; the inner decide runs one-ply to avoid (a) nesting a condition-
            # rollout inside every H-loop turn and (b) the SHOWDOWN_ROLLOUT_HORIZON env
            # collision (that var sets the OUTER H, line ~211).  Documented v1 choice.
            "rollout_horizon": 0,
        }

        # Extend cfg_dict with rollout-specific semantic hashes so consumers know
        # which config produced this data.  Stub mode leaves these out, keeping
        # stub config_hash byte-identical to pre-1d.
        cfg_dict["rollout_config"] = canonical_hash({
            "H": cfg.H,
            "gamma": cfg.gamma,
            "top_k": cfg.top_k,
            "use_leaf": cfg.use_leaf,
        })
        cfg_dict["move_priors_hash"] = canonical_hash(move_priors)
        cfg_dict["likely_sets_hash"] = canonical_hash(likely_sets)

        return RolloutLabelProvider(
            deps=deps,
            likely_sets=likely_sets,
            move_priors=move_priors,
            cfg=cfg,
            speed_oracle=speed_oracle,
        )

    def start_game(self) -> None:
        self._game_index += 1
        self._decision_local_index = 0  # reset per game; sampling index does NOT reset

    def observe(self, *, trace, state, request, turn_number, our_side) -> int:
        """Observe one decision: sample-gate, label, extract, add rows.

        The sampling gate is here (not in the driver).  If sampled:
          1. Increment sampled_count.
          2. Ask provider for labels; catch ONLY RolloutLabelError -> skip.
             Any other exception propagates (hard-fail).
          3. If labels obtained, call maybe_observe_decision.
          4. After any skip, check the skip-rate threshold.

        Always increments both decision indices.
        """
        ctx = build_feature_context(
            git_sha=self.git_sha,
            dirty_flag=self.dirty_flag,
            team_hash_=self.team_hash_,
            config_hash_=self.config_hash_,
            run_seed=self.run_seed,
            game_index=self._game_index,
            decision_local_index=self._decision_local_index,
            turn_number=turn_number,
            our_side=our_side,
            format_id=self.format_id,
            mirror_flag=self.mirror_flag,
            teacher_config=self.teacher_config,
            sampling_policy=self.sampling_policy_name,
            dex=self.dex,
            move_meta=self.move_meta,
            protect_priors_by_opp_slot=self.protect_priors_by_opp_slot,
        )

        n = 0
        if self.exporter.sampling_policy.should_sample(self._sampling_decision_index):
            self.sampled_count += 1
            try:
                labels = self._provider.labels_for_decision(
                    trace, state, request, context=ctx
                )
            except RolloutLabelError as exc:
                self.skipped_count += 1
                logger.debug("rollout skip (decision %d): %s", self._sampling_decision_index, exc)
                self._check_threshold()
                # n stays 0
            else:
                n = maybe_observe_decision(
                    self.exporter,
                    ctx=ctx,
                    trace=trace,
                    state=state,
                    request=request,
                    labels=labels,
                )

        self._decision_local_index += 1
        self._sampling_decision_index += 1  # GLOBAL: counts across all games
        return n

    def _check_threshold(self) -> None:
        """Raise RuntimeError if the skip rate exceeds max_skip_rate after min_sampled."""
        if (
            self.sampled_count >= self.min_sampled
            and self.skipped_count / self.sampled_count > self.max_skip_rate
        ):
            raise RuntimeError(
                f"RolloutLabelError skip rate too high: "
                f"{self.skipped_count}/{self.sampled_count} "
                f"({self.skipped_count / self.sampled_count:.1%} > {self.max_skip_rate:.0%}). "
                "Check rollout deps or increase SHOWDOWN_DATASET_SAMPLE_RATE."
            )

    def flush(self) -> None:
        self.exporter.flush_sorted(self.export_path)
