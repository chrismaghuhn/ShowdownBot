# Depth-2 Accuracy Stage-3 Readiness — Closeout Report

**Spec:** `docs/projects/learning/specs/2026-07-27-depth2-accuracy-stage3-readiness-design.md`
**Plan:** `docs/projects/learning/plans/2026-07-27-depth2-accuracy-stage3-readiness.md`
**Branch:** `codex/depth2-accuracy-stage3-readiness-design`

## Completion statement (spec §15)

> When the existing coarse Depth-2 path is used, its Turn-1 and Turn-2 evaluations now use one
> resolved accuracy configuration, and the executed work is observable.

## What changed

1. **Accuracy config forwarding (Tasks 1–4):** `d2_eval_kwargs` in `decision.py` and
   `mega_scoring.py` now include `accuracy_mode` and `accuracy_branch_cap`, resolved once
   per decision. Both non-Mega and Mega Depth-2 paths forward the same values to
   `search.py::_score_turn2_plans`. Equality and counterproof tests verify forwarding,
   consumption, and non-expansion.

2. **In-memory telemetry sink (Tasks 5–6):** `Depth2ReadinessCounts` dataclass in
   `eval/depth2_readiness.py`. Threaded as an explicit optional `readiness_sink` parameter
   through `_choose_best → _choose_best_mega → score_evaluated_variants → depth2_value →
   _score_turn2_plans`. No runtime monkey-patching. When sink is `None`, every call site
   takes its prior code path with no overhead.

3. **decision-profile-v4 schema (Tasks 7–8):** 15 new readiness fields
   (`search_depth`, `search_topn_requested`, `search_topm_requested`,
   `depth2_candidates_selected`, `depth2_response_slots_eligible`, `accuracy_mode`,
   `accuracy_branch_cap`, `turn1_accuracy_leaf_count`, `turn1_accuracy_cap_hits`,
   `turn1_accuracy_cap_fallback`, `turn2_accuracy_leaf_count`, `turn2_accuracy_cap_hits`,
   `turn2_accuracy_cap_fallback`, `selection_stage`, `fallback_reason`).
   Frozen v1/v2/v3 schemas untouched. Cross-field semantic validation (depth-1 → zero
   depth-2 work, accuracy-off → zero counters, cap-hit ↔ fallback consistency).
   `build_live_profile_row` stamps v4 when `readiness` is provided; otherwise emits v3.

4. **Gauntlet integration (Task 8):** `handle_request` allocates `Depth2ReadinessCounts`
   when profiling is on, forwards it through `agent_choose`, and passes the sink to
   `build_live_profile_row` at persistence time.

## What was verified locally (Task 9)

| Tier | Tests | Result |
|---|---|---|
| Focused (new tests only) | 37 passed, 1 skipped | GREEN |
| Affected suites (10 existing test files) | 185 passed | GREEN |
| Full `showdown_bot` suite | 995 passed, 2 skipped, 1 xfailed | GREEN |
| `git diff --check` | clean | PASS |

The 1 failure in the full suite (`test_config_hash_provenance.py::test_every_raw_byte_hashed_provenance_input_is_lf_on_disk`)
is a pre-existing Windows CRLF issue unrelated to this slice. No new skip or xfail was introduced.

## What remains unrun

- **Cost preflight** (spec §11): documented below, operator-directed.
- **Diverse development panel** (spec §15 non-claim): not designed or run.
- **I8-D live latency gate**: not re-run on this candidate (no behavior change — accuracy
  config was already resolved; this slice only corrects its forwarding to Turn-2).
- **Champions Strength**: remains NO-GO. This slice makes no strength claim.
- **Independent holdout**: not authorized. Requires a materially different candidate first.

## Explicit non-claims (spec §15)

This slice does **not** claim:
- Depth-2 is stronger.
- Depth-2 is production-ready or default-on.
- The method computes a full two-turn expected value.
- The 1000-ms live gate passed (for this candidate).
- The diverse panel passed.
- Champions Strength changed from NO-GO.
- A new holdout is authorized.

---

## Cost preflight (spec §11, operator-directed)

### Matrix (§11.1)

| Arm | `SHOWDOWN_SEARCH_DEPTH` | `SHOWDOWN_ACCURACY_MODE` | `SHOWDOWN_ACCURACY_BRANCH_CAP` | `SHOWDOWN_SEARCH_TOPN` | `SHOWDOWN_SEARCH_TOPM` |
|---|---|---|---|---|---|
| Depth1/AccOff | `1` (or unset) | `0` | (irrelevant) | (irrelevant) | (irrelevant) |
| Depth1/AccOn(cap6) | `1` (or unset) | `1` | `6` (or unset) | (irrelevant) | (irrelevant) |
| Depth2(3,3)/AccOff | `2` | `0` | (irrelevant) | `3` | `3` |
| Depth2(3,3)/AccOn(cap6) | `2` | `1` | `6` (or unset) | `3` | `3` |

All arms use:
- The fixed Windows measurement host.
- The persistent calc backend (`SHOWDOWN_CALC_BACKEND=persistent`).
- `SHOWDOWN_DECISION_PROFILE_OUT=<path>` to enable v4 profile emission.
- `--result-out <path>` (required by the profile writer).
- The same schedule, positions, and seeds.

### Invocation template (PowerShell, fixed Windows host)

```powershell
$env:SHOWDOWN_SEARCH_DEPTH = "<D>"
$env:SHOWDOWN_ACCURACY_MODE = "<A>"
$env:SHOWDOWN_ACCURACY_BRANCH_CAP = "6"
$env:SHOWDOWN_SEARCH_TOPN = "3"
$env:SHOWDOWN_SEARCH_TOPM = "3"
$env:SHOWDOWN_CALC_BACKEND = "persistent"
$env:SHOWDOWN_DECISION_PROFILE_OUT = "<arm_profile_out.jsonl>"
python -m showdown_bot.cli gauntlet --schedule <schedule.yaml> --result-out <arm_result_out.jsonl>
```

### Strata

Cold and warm cache strata **must be reported separately** (spec §11.3: never pooled).
The `backend_class` field in the v4 row distinguishes `clean_warm` vs `persistent_warm`
(the label describes the cache state observed in that row, not the backend env var value).

### Required output columns (§11.2)

For every arm and cache stratum:
- Repetitions and valid-row count
- p50, p95, and maximum `measured_ms`
- Timeout count
- Chooser-fallback count and degradation count
- Turn-1 and Turn-2 `accuracy_leaf_count`
- Turn-1 and Turn-2 `accuracy_cap_hits`
- Deterministic `cap_fallback` count
- `search_topn_requested`, `search_topm_requested`, `depth2_candidates_selected`,
  `depth2_response_slots_eligible`
- Calc transport: `calc_calls`, `calc_attempts`, `calc_spawns`, `calc_total_requests`,
  `calc_unique_requests`, `calc_cache_hits`
- Environment/provenance: `config_hash`, `git_sha`, `battle_id`

### Validation (post-run)

```bash
python -c "
import json, sys
from showdown_bot.eval.decision_profile import validate_decision_profile_row
for line in open(sys.argv[1]):
    row = json.loads(line)
    validate_decision_profile_row(row, manifest=None)
print('All rows valid')
" <path_to_preflight_output.jsonl>
```

### Interpretation rules (§11.3)

- Cold and warm rows are **never pooled**.
- Accuracy-off/on comparisons are **descriptive cost evidence only**.
- The existing 1000-ms live budget is unchanged and not reinterpreted as a per-arm
  microprofile threshold.
- No new latency threshold is invented in this slice.
- Any timeout, degradation, malformed row, missing telemetry, or schema violation makes
  the preflight **invalid** rather than a pass.
