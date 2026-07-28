# Depth-2 Accuracy Stage-3 Readiness — Closeout Report

**Spec:** `docs/projects/learning/specs/2026-07-27-depth2-accuracy-stage3-readiness-design.md`
**Plan:** `docs/projects/learning/plans/2026-07-27-depth2-accuracy-stage3-readiness.md`
**Branch:** `codex/depth2-accuracy-stage3-readiness-design`

## Completion statement (spec §15) — FINAL

> When the existing coarse Depth-2 path is used, its Turn-1 and Turn-2 evaluations now use one
> resolved accuracy configuration, and the executed work is observable.

**Status: final as of 2026-07-28.** The cost preflight (§11 below) has been executed on a
fully valid matrix and its evidence is frozen. See
`docs/projects/learning/reports/2026-07-28-depth2-cost-preflight-attempt6-freeze.md`
and its companion operator-artifacts document, plus Appendix A.6 of
`docs/projects/learning/specs/2026-07-28-depth2-cost-preflight-amendment.md`.

Attempt 6 ran four arms × 30 battles with 0 timeouts, 0 crashes, 0 invalid choices, 0
degradation, 0 chooser fallback and no contaminated rows; all post-arm gates and the
cross-arm validation passed. Depth-2 search was actually executed (`depth2_frontier > 0`
on every profile row of both depth-2 arms). Attempts 1–5 are invalidated and none of their
data is reused (Appendix A.1–A.5).

**This finalisation asserts observability and measured cost only.** It does not upgrade any
non-claim below: no strength claim, no production-readiness claim, no live-gate claim, no
default change.

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

5. **Review-round fixes (post-Task-9):**
   - `N`/`M`/`search_depth` once-resolved at `_choose_best_ja` entry and threaded as
     parameters through `_choose_best_mega` → `score_evaluated_variants` (eliminates
     redundant env-var reads).
   - K-world `shape_sink.n_worlds` wired at the origin of world sampling (both K-world
     and single-world branches).
   - `_Client.close()` never raises; the fail-closed RuntimeError check fires AFTER
     both hero and villain are fully cleaned up.
   - `STAGE_ALLOWED_REASONS` enforces exact stage↔reason coupling in the V4 validator
     (`max_damage_fallback` → `{heuristic_timeout, heuristic_error}`,
     `deterministic_default_pair` → `{max_damage_error}`,
     `server_default` → `{default_pair_error}`).
   - `profile_fixtures.py` updated to forward `search_depth`/`search_topn`/`search_topm`
     to `score_evaluated_variants` (regression fix for arm 12).
   - Origin counterproof tests: search resolvers once per decision, real K-world
     `n_worlds > 1` with zero depth-2 work, eligible slots pre-cap (separate for Mega
     and non-Mega paths).

## What was verified locally (Task 9, updated 2026-07-28)

| Tier | Tests | Result |
|---|---|---|
| New tests (46 new test functions) | 46 passed | GREEN |
| Affected suites (6 modified + 1 downstream test files) | 167 passed | GREEN |
| Full `showdown_bot` suite | 3853 passed, 6 failed, 2 skipped, 1 xfailed | RED (6 pre-existing) |
| `git diff --check` | clean | PASS |

6 pre-existing failures in unmodified test files (none introduced by this branch):
`test_eval_report_golden.py` (2, golden-file drift from `main`),
`test_strength_holdout_verdict.py` (2, schedule/team path fixtures),
`test_strength_holdout_runner.py` (1, schedule/team path fixture),
`test_profile_arms_end_to_end.py` (1, arm 12 fixture path).
One regression found and fixed during review: `profile_fixtures.py` was
missing the `search_depth`/`search_topn`/`search_topm` parameters added to
`score_evaluated_variants` in this slice.
No new skip or xfail was introduced.

## What remains unrun

- ~~**Cost preflight** (spec §11)~~ — **run and frozen 2026-07-28** (Attempt 6, valid matrix).
  The operator-directed procedure documented below is retained as the historical record of
  what was specified; the executed parameters, results and all 21 output hashes live in the
  Attempt-6 freeze report.
- **Diverse development panel** (spec §15 non-claim): not designed or run.
- **I8-D live latency gate**: not re-run on this candidate (no behavior change — accuracy
  config was already resolved; this slice only corrects its forwarding to Turn-2).
- **Champions Strength**: remains NO-GO. This slice makes no strength claim.
- **Independent holdout**: not authorized. Requires a materially different candidate first.

## Explicit non-claims (spec §15)

These non-claims are **unchanged** by the completed cost preflight. The preflight produced
cost and readiness evidence only; it upgrades none of them.

This slice does **not** claim:
- Depth-2 is stronger.
- Depth-2 is production-ready or default-on.
- The method computes a full two-turn expected value.
- The 1000-ms live gate passed (for this candidate).
- The diverse panel passed.
- Champions Strength changed from NO-GO.
- A new holdout is authorized.

---

## Cost preflight (spec §11, operator-directed) — EXECUTED

**This section is the original specification, retained unchanged as the historical record of
what was pre-registered.** It is not the result. The executed run, its parameters, its §12
evidence per arm × stratum, the 21 frozen output hashes and the operator scripts are in
`docs/projects/learning/reports/2026-07-28-depth2-cost-preflight-attempt6-freeze.md`.

The template below was **incomplete as an executable procedure**: it fixed the environment
variables and the invocation shape, but left the schedule, the seeds, the import root, the
server lifecycle and the validation gates unspecified. The amendment
(`2026-07-28-depth2-cost-preflight-amendment.md`) supplied exactly those.

The template is **not** the source of the Attempt-4 defect. It uses the correct, fully
`SHOWDOWN_`-prefixed variable names throughout. The short-name defect that made all four
Attempt-4 arms run code defaults was introduced by an early revision of the amendment's
§6.3 table and corrected there; see Appendix A.4.

Five attempts were invalidated before a valid matrix was obtained (Appendix A.1–A.5).


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
The `backend_class` field in the v4 row distinguishes `clean_cold`, `clean_warm`, and
`contaminated` (the label describes the cache state observed in that row, not the backend
env var value).

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
- Calc transport: `transport_calls`, `transport_attempts`, `spawn_calls`, `requests_total`,
  `requests_unique`, `cache_hits`
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
