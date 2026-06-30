"""The testable seam between the live client and the export pipeline (slice 1b-B3).

`_Client` holds one `DatasetExportRuntime` (or None) and calls start_game/observe/
flush. All env setup, provenance, counters, and the driver call live here so they can
be tested without Node/WebSocket.
"""

from __future__ import annotations

import os

from showdown_bot.learning.export import DatasetExporter, SamplingPolicy
from showdown_bot.learning.export_driver import maybe_observe_decision
from showdown_bot.learning.provenance import (
    build_feature_context, config_hash, git_sha_and_dirty, team_hash,
)

_HEURISTIC_KNOBS = (
    "SHOWDOWN_PROTECT_PENALTY", "SHOWDOWN_REAL_SPREADS", "SHOWDOWN_OPP_SETS",
    "SHOWDOWN_OPP_SPEED", "SHOWDOWN_MUST_REACT_LAMBDA", "SHOWDOWN_ROLLOUT_HORIZON",
)


class DatasetExportRuntime:
    def __init__(self, exporter, export_path, *, git_sha, dirty_flag, team_hash_,
                 config_hash_, run_seed, format_id, mirror_flag, sampling_policy_name,
                 dex=None, move_meta=None, protect_priors_by_opp_slot=None):
        self.exporter = exporter
        self.export_path = export_path
        self.git_sha = git_sha; self.dirty_flag = dirty_flag
        self.team_hash_ = team_hash_; self.config_hash_ = config_hash_
        self.run_seed = run_seed; self.format_id = format_id; self.mirror_flag = mirror_flag
        self.sampling_policy_name = sampling_policy_name
        self.teacher_config = {"teacher_version": "stub-h0", "trainable_label": False}
        self.dex = dex; self.move_meta = move_meta
        self.protect_priors_by_opp_slot = protect_priors_by_opp_slot
        self._game_index = -1            # first start_game -> 0
        self._decision_local_index = 0   # per-game (decision_id)
        self._sampling_decision_index = 0  # global run-level (SamplingPolicy)

    @classmethod
    def from_env(cls, *, format_id, packed_team, mirror_flag, dex=None, move_meta=None,
                 protect_priors_by_opp_slot=None):
        path = os.environ.get("SHOWDOWN_DATASET_EXPORT")
        if not path:
            return None                  # env off -> exporter stays None (gate: bit-identical)
        seed = int(os.environ.get("SHOWDOWN_DATASET_RUN_SEED", "0"))
        policy = os.environ.get("SHOWDOWN_DATASET_SAMPLE_POLICY", "all")
        rate = int(os.environ.get("SHOWDOWN_DATASET_SAMPLE_RATE", "1"))
        git_sha, dirty = git_sha_and_dirty()
        th = team_hash(packed_team)
        # config_hash = dataset-semantic config ONLY (NOT the output path)
        cfg = {"sample_policy": policy, "sample_rate": rate, "top_k": 6, "team_hash": th}
        cfg.update({k: os.environ.get(k) for k in _HEURISTIC_KNOBS})
        ch = config_hash(cfg)
        exp = DatasetExporter(SamplingPolicy(policy=policy, rate=rate, seed=seed))
        return cls(exp, path, git_sha=git_sha, dirty_flag=dirty, team_hash_=th, config_hash_=ch,
                   run_seed=seed, format_id=format_id, mirror_flag=mirror_flag,
                   sampling_policy_name=policy, dex=dex, move_meta=move_meta,
                   protect_priors_by_opp_slot=protect_priors_by_opp_slot)

    def start_game(self) -> None:
        self._game_index += 1
        self._decision_local_index = 0          # reset per game; sampling index does NOT reset

    def observe(self, *, trace, state, request, turn_number, our_side) -> int:
        ctx = build_feature_context(
            git_sha=self.git_sha, dirty_flag=self.dirty_flag, team_hash_=self.team_hash_,
            config_hash_=self.config_hash_, run_seed=self.run_seed, game_index=self._game_index,
            decision_local_index=self._decision_local_index, turn_number=turn_number, our_side=our_side,
            format_id=self.format_id, mirror_flag=self.mirror_flag, teacher_config=self.teacher_config,
            sampling_policy=self.sampling_policy_name, dex=self.dex, move_meta=self.move_meta,
            protect_priors_by_opp_slot=self.protect_priors_by_opp_slot)
        n = maybe_observe_decision(self.exporter, self._sampling_decision_index,
                                   ctx=ctx, trace=trace, state=state, request=request)
        self._decision_local_index += 1
        self._sampling_decision_index += 1       # GLOBAL: counts across all games
        return n

    def flush(self) -> None:
        self.exporter.flush_sorted(self.export_path)
