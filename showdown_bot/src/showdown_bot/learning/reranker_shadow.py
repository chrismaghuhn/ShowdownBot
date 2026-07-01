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

    def _append(self, row):
        """Best-effort append of one ShadowTrace JSONL row. Never raises."""
        try:
            with open(self.log_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")
        except Exception as exc:  # noqa: BLE001 - logging is best-effort
            logger.warning("reranker shadow: failed to append row: %s", exc)

    def observe_shadow(self, *, trace, state, request, choose, turn_number, our_side,
                       decision_index) -> None:
        """Score the top-K candidates with the 2b-2a model, find the heuristic's
        authoritative pick (trace.chosen_candidate_id) and append one ShadowTrace row.
        Post-send, LOG-ONLY, fail-safe: it NEVER raises to the caller and never mutates
        self._decision_local_index (the gauntlet hook owns that)."""
        import time

        t0 = time.perf_counter()
        # Every §7 field initialised so a no-score path still writes a complete row.
        row = {
            "game_id": None,
            "decision_id": None,
            "turn_number": turn_number,
            "our_side": our_side,
            "actual_choose_string": choose,
            "heuristic_choice_index": None,
            "reranker_choice_index": None,
            "diverged": None,
            "candidate_count": 0,
            "candidate_indices": [],
            "model_scores": [],
            "model_top_margin": None,
            "model_dataset_sha256": self.manifest.get("dataset_sha256"),
            "model_git_sha": self.manifest.get("git_sha"),
            "training_feature_schema_hash": self.manifest.get("feature_schema_hash"),
            "runtime_feature_schema_hash": None,
            "manifest_feature_names_hash": None,
            "feature_vector_hash": None,
            "missing_model_features": [],
            "extra_live_features": [],
            "dropped_constant_columns_present_values": [],
            "feature_context_mode": "2b2a_move_meta_none",
            "feature_parity_warnings": [],
            "fallback_reason": None,
            "shadow_enabled_but_not_scored": False,
            "shadow_latency_ms": None,
        }
        try:
            import hashlib

            from showdown_bot.learning.features import extract_features
            from showdown_bot.learning.provenance import build_feature_context
            from showdown_bot.learning.reranker_features import feature_schema_hash, vectorize

            def _sha1(payload) -> str:
                return hashlib.sha1(json.dumps(payload).encode("utf-8")).hexdigest()

            # (2) FeatureContext — move_meta=None, sampling_policy="all", mirror_flag=False.
            ctx = build_feature_context(
                git_sha=self.provenance["git_sha"],
                dirty_flag=self.provenance["dirty_flag"],
                team_hash_=self.provenance["team_hash"],
                config_hash_=self.provenance["config_hash"],
                run_seed=self.provenance["run_seed"],
                game_index=self._game_index,
                decision_local_index=decision_index,
                turn_number=turn_number,
                our_side=our_side,
                format_id=self.format_id,
                mirror_flag=False,
                # extract_features()->_metadata reads teacher_config["teacher_version"]; a bare {}
                # KeyErrors. Metadata is irrelevant to scoring (we consume only row.features), so we
                # pass a minimal valid teacher_config to let extraction succeed.
                teacher_config={"teacher_version": "shadow"},
                sampling_policy="all",
                dex=None,
                move_meta=None,
            )
            row["game_id"] = ctx.game_id
            row["decision_id"] = ctx.decision_id

            # (3) extract_features(labels=None) -> one Row per candidate, trace order.
            try:
                rows = extract_features(trace, state, request, ctx)
            except Exception:  # noqa: BLE001 - fail-safe
                logger.warning("reranker shadow: extract_features failed", exc_info=True)
                row["fallback_reason"] = "extract_features_error"
                row["shadow_enabled_but_not_scored"] = True
                row["shadow_latency_ms"] = round((time.perf_counter() - t0) * 1000, 3)
                self._append(row)
                return
            row["candidate_count"] = len(rows)
            row["candidate_indices"] = list(range(len(rows)))

            # Parity diagnostics that only need the manifest / live feature keys.
            row["runtime_feature_schema_hash"] = feature_schema_hash(
                self.feature_names, self.categorical_feature_names)
            row["manifest_feature_names_hash"] = _sha1(self.feature_names)
            if rows:
                live_keys = set(rows[0].features)
                row["extra_live_features"] = sorted(live_keys - set(self.feature_names))
                present = [
                    c for c in self.manifest.get("dropped_constant_columns", [])
                    if rows[0].features.get(c) not in (None, "__none__", "__untracked__", 0, 0.0, False)
                ]
                row["dropped_constant_columns_present_values"] = present
                row["feature_parity_warnings"] = [
                    f"train-dead column {c} now present" for c in present
                ]

            # (4) vectorize using ONLY row.features + the persisted encodings.
            X, missing = vectorize(
                [r.features for r in rows],
                feature_names=self.feature_names,
                encodings=self.encodings,
            )
            row["feature_vector_hash"] = _sha1(X)
            if missing:
                row["missing_model_features"] = missing
                row["fallback_reason"] = "feature_name_missing_in_row"
                row["shadow_enabled_but_not_scored"] = True
                row["shadow_latency_ms"] = round((time.perf_counter() - t0) * 1000, 3)
                self._append(row)
                return

            # (5) Score.
            import numpy as np

            try:
                scores = list(self.booster.predict(np.array(X, dtype=float)))
            except Exception:  # noqa: BLE001 - fail-safe
                logger.warning("reranker shadow: booster.predict failed", exc_info=True)
                row["fallback_reason"] = "predict_error"
                row["shadow_enabled_but_not_scored"] = True
                row["shadow_latency_ms"] = round((time.perf_counter() - t0) * 1000, 3)
                self._append(row)
                return
            row["shadow_latency_ms"] = round((time.perf_counter() - t0) * 1000, 3)
            reranker_choice_index = int(max(range(len(scores)), key=lambda i: scores[i]))
            row["reranker_choice_index"] = reranker_choice_index
            row["model_scores"] = [
                {"candidate_index": i, "score": float(s)} for i, s in enumerate(scores)
            ]
            if len(scores) >= 2:
                ordered = sorted((float(s) for s in scores), reverse=True)
                row["model_top_margin"] = ordered[0] - ordered[1]
            else:
                row["model_top_margin"] = 0.0

            # (6) Heuristic pick via the trace (authoritative).
            heuristic_choice_index = None
            chosen = trace.chosen_candidate_id
            if chosen is not None:
                for i, cand in enumerate(trace.candidates):
                    if cand.candidate_id == chosen:
                        heuristic_choice_index = i
                        break
            if heuristic_choice_index is None:
                row["fallback_reason"] = "heuristic_choice_not_in_trace"
                row["diverged"] = None
            else:
                row["heuristic_choice_index"] = heuristic_choice_index
                row["diverged"] = reranker_choice_index != heuristic_choice_index

            self._append(row)
        except Exception as exc:  # noqa: BLE001 - shadow is post-send + fail-safe
            logger.warning("reranker shadow: unexpected error, no-score: %s", exc, exc_info=True)
            row["shadow_enabled_but_not_scored"] = True
            if row.get("fallback_reason") is None:
                row["fallback_reason"] = "shadow_unexpected_error"
            if row.get("shadow_latency_ms") is None:
                row["shadow_latency_ms"] = round((time.perf_counter() - t0) * 1000, 3)
            self._append(row)
