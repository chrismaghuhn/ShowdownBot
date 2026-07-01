"""Slice 2b-3a: reranker Shadow Mode runtime. Computes the 2b-2a reranker's choice
live and LOGS it only — never plays it. Post-send, fail-safe, gauntlet-only.
lightgbm is imported ONLY inside from_env, only when SHOWDOWN_RERANKER_SHADOW is on."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from showdown_bot.learning.reranker_features import feature_schema_hash

logger = logging.getLogger(__name__)


class RerankerShadowRuntime:
    def __init__(self, *, booster, manifest, log_path, format_id, timeout_ms, provenance):
        self.booster = booster
        self.manifest = manifest
        self.feature_names = manifest["feature_names"]
        self.categorical_feature_names = manifest["categorical_feature_names"]
        self.encodings = manifest["categorical_encodings"]
        self.log_path = log_path
        self.format_id = format_id
        self.timeout_ms = timeout_ms
        self.provenance = provenance  # {git_sha, dirty_flag, team_hash, config_hash, run_seed}
        self._game_index = -1
        self._decision_local_index = 0
        # Dedicated SINGLE-worker executor for scoring: caps concurrent shadow threads at 1, so a
        # timed-out (orphaned-but-still-running) scoring can never accumulate into many threads.
        from concurrent.futures import ThreadPoolExecutor
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="shadow")
        self.inflight = None  # last submitted future (busy-check in the gauntlet hook)

    def bump_decision_index(self):
        """Advance the per-decision index by one — called by the gauntlet hook on EVERY observed
        decision (including skipped-because-busy), to stay in lockstep with DatasetExportRuntime."""
        self._decision_local_index += 1

    @classmethod
    def from_env(cls, *, format_id, packed_team=None, provenance=None, dex=None, move_meta=None):
        """Eager: load model+manifest, run the INV-7 schema check, open the log. Returns None
        (shadow disabled) when the env flag is off OR on ANY load/check failure — one warning,
        battle runs heuristically. lightgbm import lives here (rule 5)."""
        if not os.environ.get("SHOWDOWN_RERANKER_SHADOW"):
            return None  # rule 5: no lightgbm import when off
        try:
            import time
            import lightgbm as lgb  # imported ONLY here
            from showdown_bot.learning.schema import FEATURE_COLUMNS
            from showdown_bot.learning.provenance import git_sha_and_dirty, team_hash
            model_path = os.environ["SHOWDOWN_RERANKER_MODEL_PATH"]
            manifest_path = os.environ["SHOWDOWN_RERANKER_MANIFEST_PATH"]
            log_path = os.environ.get("SHOWDOWN_RERANKER_SHADOW_LOG") or \
                f"logs/reranker_shadow/{int(time.time())}.jsonl"
            timeout_ms = int(os.environ.get("SHOWDOWN_RERANKER_SHADOW_TIMEOUT_MS", "50"))
            manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
            if not set(manifest["feature_names"]) <= set(FEATURE_COLUMNS):
                raise ValueError("manifest feature_names not a subset of schema.FEATURE_COLUMNS")
            booster = lgb.Booster(model_file=model_path)
            rt_hash = feature_schema_hash(manifest["feature_names"], manifest["categorical_feature_names"])
            if rt_hash != manifest["feature_schema_hash"]:
                raise ValueError("feature_schema_hash_mismatch (manifest self-inconsistent)")
            if list(booster.feature_name()) != list(manifest["feature_names"]):
                raise ValueError("feature_schema_hash_mismatch (model<->manifest feature_names)")
            if provenance is None:
                gs, dirty = git_sha_and_dirty()
                provenance = {"git_sha": gs, "dirty_flag": dirty,
                              "team_hash": team_hash(packed_team or ""),
                              "config_hash": "shadow", "run_seed": 0}
            Path(log_path).parent.mkdir(parents=True, exist_ok=True)
            return cls(booster=booster, manifest=manifest, log_path=log_path,
                       format_id=format_id, timeout_ms=timeout_ms, provenance=provenance)
        except Exception as exc:  # noqa: BLE001 - shadow is best-effort; disable on ANY failure
            logger.warning("reranker shadow disabled: %s", exc)
            return None

    def start_game(self):
        self._game_index += 1
        self._decision_local_index = 0

    # observe_shadow is added in Task 3.
