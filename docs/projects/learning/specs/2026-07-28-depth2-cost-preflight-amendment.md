# Depth-2 Cost Preflight — Spec Amendment

**Amends:** `docs/projects/learning/specs/2026-07-27-depth2-accuracy-stage3-readiness-design.md` §11–§12
**Candidate SHA:** `d64982ae9fdba6a877c8c2b7e804923ebcc7fec4`
**Date:** 2026-07-28

---

## Motivation

The parent spec (§11) defines the 4-arm cost-preflight matrix but leaves five execution
parameters as placeholders: schedule, positions, seeds, repetition count, and output paths.
The offline microprofile runner (`profile_runner.py`) cannot serve this purpose because
`decision-profile-v4` is live-only — the microprofiler produces v2 rows and has no
readiness sink, chooser stage, or accuracy fields. This amendment pins all parameters for
a **live-gauntlet** measurement path that natively produces v4 rows.

This amendment adds no production code. The candidate remains `d64982a`.

---

## 1. Measurement path

Live gauntlet (`python -m showdown_bot.cli gauntlet --schedule <path>`), which natively
emits v4 decision-profile rows when `SHOWDOWN_DECISION_PROFILE_OUT` is set.

---

## 2. Clean candidate worktree

The amendment and schedule YAML are versioned on their own branch, separate from the
candidate. The measurement run executes in a **detached worktree** checked out at exactly
`d64982ae9fdba6a877c8c2b7e804923ebcc7fec4`.

Before battle 1 in any arm, the following must hold:

- `git rev-parse HEAD` in the worktree equals `d64982ae9fdba6a877c8c2b7e804923ebcc7fec4`.
- `git status --porcelain` in the worktree is empty (no modified, untracked, or staged
  files).
- `git diff d64982a -- showdown_bot/src showdown_bot/tests` produces no output (no
  production-file diff against the candidate).
- The run manifest's `dirty` field is `false`.
- The run manifest's `git_sha` field equals the full 40-character SHA of `d64982a`.
- The run manifest's `cli_invocation` path contains the candidate worktree root, not any
  other checkout (see §2.1).

If any of these fail, the arm is invalid and the preflight is invalid.

### 2.1 Import-root provenance

The Python interpreter must load `showdown_bot` exclusively from the candidate worktree.
Before battle 1 of the first arm, record and verify:

- `showdown_bot.__file__` is under `<candidate-worktree>/showdown_bot/src/`.
- `showdown_bot.cli.__file__` is under `<candidate-worktree>/showdown_bot/src/`.

The interpreter must be invoked with `PYTHONPATH` set exclusively to
`<candidate-worktree>/showdown_bot/src` (no other entries), ensuring no installed or
editable package from another checkout is picked up. The two `__file__` values are
recorded in `operator-preflight.json` (§7.1).

**Rationale (Attempt 1):** Attempt 1 ran with the process CWD inside the candidate
worktree but without pinning `PYTHONPATH`. Python resolved the installed editable package
from the main repo (`SHowdown BOt/showdown_bot/src`), so `cli_invocation` and
`showdown_bot.__file__` pointed to a different checkout. The production bytes were
identical (only the amendment/schedule YAML differ between `d64982a` and `25d3dae`), but
the approved candidate-provenance contract was not met. The 17 output files are preserved
as `attempt-1-invalid-import-root/` with frozen SHA-256 hashes (Appendix A). No data
from Attempt 1 may be reused or pooled with Attempt 2.

---

## 3. Schedule

A static YAML generated from the existing I8-D development panel
(`config/eval/panels/panel_champions_v0.yaml`) with `n_battles=30`.

| Property | Value |
|---|---|
| File | `config/eval/schedules/cost_preflight_d2_30.yaml` |
| Battles | 30 (5 full cycles of 6 I8-D matchups, zero remainder) |
| `schedule_hash` | `b6f5910e4bc3c584` |
| `panel_hash` | `aac1ea30446fde88` |
| Hero team | `teams/fixed_champions_v0.txt` |
| Dev teams | goodstuff, tailwind_offense, trick_room |
| Policies | heuristic, max_damage |
| Panel split | dev only — no held-out teams |
| Seed indices | 0–29, contiguous |

The YAML is frozen as an input artifact. The gauntlet reads it via `load_schedule`.

---

## 4. Working directory and team-path discipline

### 4.1 Process CWD

The gauntlet process CWD is `<candidate-worktree>/showdown_bot`. The schedule YAML is
loaded via its **absolute path** (not a relative path that could resolve against an
unintended root).

### 4.2 Pre-battle-1 schedule and team checks

Before the first battle of each arm:

1. **Reconstruct the canonical schedule** from the panel
   (`build_i8d_schedule(panel, n_battles=30)`) and verify byte-equality of the resulting
   `schedule_hash` against the YAML's frozen `b6f5910e4bc3c584`. A mismatch means the
   panel or the generation code changed between YAML creation and the run.

2. **Run `verify_i8d_panel_and_teams(schedule, teams_root=<candidate>/showdown_bot)`**.
   This re-reads every distinct team file from the candidate worktree, re-hashes their
   contents, and checks `panel_hash == aac1ea30446fde88`. This is the TOCTOU guard
   that binds team-file contents (not just paths) to the run identity.

3. **Pack and verify every team**: for every distinct `hero_team_path` and
   `opp_team_path` in the schedule, load the packed team string and assert it is
   **non-empty**. The gauntlet's `load_schedule` silently produces an empty string on
   file-not-found; an empty packed team is an invalid arm, and the preflight is invalid.

If any of (1)–(3) fail, the arm is invalid and the preflight is invalid.

---

## 5. Seeds

Seed base: `champions-panel-v0-d2-cost-preflight`

Set as `SHOWDOWN_BATTLE_SEED_BASE` for every arm. The server derives per-battle seeds via
Channel A (`derive_battle_seed(base, seed_index)`). The same base + schedule produces
identical seeds across all four arms.

Distinct from existing namespaces (`champions-panel-v0-i8d-latency`,
`champions-coverage-v0`, `champions-strength-holdout-v0`).

---

## 6. Arms

### 6.1 Pre-registered arm order

Arms are executed in this exact order: `d1_acc_off`, `d1_acc_on`, `d2_acc_off`,
`d2_acc_on`. The order is **pre-registered**, not randomised. Because arm and wall-clock
time are therefore inseparable, any host drift during the run is a confound that cannot
be distinguished from the Depth/Accuracy manipulation. Cross-arm comparisons are
consequently **descriptive only** — this is not a limitation introduced by the analysis
but a property of the single-pass fixed-order design.

### 6.2 Shared environment

Output root: a sibling directory of the candidate worktree, **outside** the git tree.
Writing output inside the worktree would make `git status` non-empty and set the run
manifest's `dirty` flag to `true`, invalidating the run by §2's own clean-candidate rule.
Created before the first arm if it does not exist. All arm-specific paths below use
**absolute paths** under this root.

- Attempt 1 (invalidated — see Appendix A): `cost-preflight-d2-d64982a/`
- **Attempt 2:** `cost-preflight-d2-d64982a-attempt2/`

All arms share:
- `PYTHONPATH=<candidate-worktree>/showdown_bot/src` (exclusive; no other entries — see §2.1)
- `SHOWDOWN_CALC_BACKEND=persistent`
- `SHOWDOWN_DECISION_PROFILE_OUT=<output-root>/cost_preflight_<arm>_profile.jsonl`
- `SHOWDOWN_BATTLE_SEED_BASE=champions-panel-v0-d2-cost-preflight`
- `SHOWDOWN_EVAL_SEED_LOG=<output-root>/cost_preflight_<arm>_seedlog.jsonl`
- `PYTHONHASHSEED=0`
- `--schedule` loaded via absolute path to the frozen YAML
- `--result-out <output-root>/cost_preflight_<arm>_result.jsonl`

where `<output-root>` is the absolute path to `cost-preflight-d2-d64982a/` and `<arm>`
is one of `d1_acc_off`, `d1_acc_on`, `d2_acc_off`, `d2_acc_on`.

### 6.3 Arm-specific environment

| Arm ID | `SEARCH_DEPTH` | `ACCURACY_MODE` | `ACCURACY_BRANCH_CAP` | `SEARCH_TOPN` | `SEARCH_TOPM` |
|---|---|---|---|---|---|
| `d1_acc_off` | `1` | `0` | (unset) | (unset) | (unset) |
| `d1_acc_on` | `1` | `1` | `6` | (unset) | (unset) |
| `d2_acc_off` | `2` | `0` | (unset) | `3` | `3` |
| `d2_acc_on` | `2` | `1` | `6` | `3` | `3` |

Every `SHOWDOWN_*` variable listed above must be explicitly set or removed before each
arm. No arm inherits values from a previous arm.

### 6.4 Timeout

`SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S` is **explicitly unset** for every arm. The effective
timeout is the code default of **180 seconds**.

---

## 7. Server and determinism provenance

The following values are **pre-registered** as part of this amendment. Before battle 1 of
the first arm, every value must be checked against the real environment. Any mismatch
makes the preflight invalid.

| Property | Pre-registered value | Verification |
|---|---|---|
| `PYTHONHASHSEED` | `0` | `os.environ["PYTHONHASHSEED"] == "0"` |
| Showdown commit | `f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5` | `load_showdown_commit()` from `config/eval/provenance.yaml` — **and** `git -C <server-dir> rev-parse HEAD` equals the same SHA |
| Server patch hash | `86e31891547e87da` | `server_patch_hash()` from `tools/eval/patches/pokemon-showdown-seeded-battle.patch` — **and** `git -C <server-dir> diff HEAD` output hashes to the same value (the patch is actually applied) |
| Server start command | `node pokemon-showdown start --no-security` | recorded in `operator-preflight.json` (§7.1) |
| Server port | `8000` | server WebSocket endpoint `ws://localhost:8000/showdown/websocket` reachable before battle 1; recorded in `operator-preflight.json` |
| Timeout | 180 s (unset `SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S`) | `os.environ.get("SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S") is None` |

`load_showdown_commit()` reads a YAML config value, not the live server checkout. It is
therefore necessary but **not sufficient**: the actual server directory's HEAD commit and
applied patch diff must be checked independently before battle 1. Both checks (YAML
config and live checkout) must agree.

The run manifest records `showdown_commit`, `server_patch_hash`, and `pythonhashseed` in
their standard fields. These are checked both pre-registered (before battle 1) and
post-hoc (in the frozen manifest).

### 7.1 Operator preflight record

The existing run manifest schema has no field for the server start command, server port,
or live-checkout verification results. These are recorded in a **separate** file:

`<output-root>/operator-preflight.json`

Written once before battle 1 of the first arm. Contains:

| Field | Value |
|---|---|
| `server_start_command` | `node pokemon-showdown start --no-security` |
| `server_port` | `8000` |
| `server_ws_endpoint` | `ws://localhost:8000/showdown/websocket` |
| `server_dir_head` | output of `git -C <server-dir> rev-parse HEAD` |
| `server_dir_diff_hash` | SHA-1 prefix of `git -C <server-dir> diff HEAD` output |
| `provenance_yaml_commit` | output of `load_showdown_commit()` |
| `patch_file_hash` | output of `server_patch_hash()` |
| `head_matches_provenance` | `server_dir_head == provenance_yaml_commit` |
| `diff_matches_patch` | `server_dir_diff_hash == patch_file_hash` |
| `candidate_sha` | `d64982ae9fdba6a877c8c2b7e804923ebcc7fec4` |
| `candidate_dirty` | `false` |
| `output_root` | absolute path to output directory |
| `pythonpath` | value of `PYTHONPATH` (must equal `<candidate>/showdown_bot/src` exclusively) |
| `showdown_bot_file` | `showdown_bot.__file__` (must be under `<candidate>/showdown_bot/src/`) |
| `showdown_bot_cli_file` | `showdown_bot.cli.__file__` (must be under `<candidate>/showdown_bot/src/`) |
| `import_root_verified` | `true` if both `__file__` paths are under the candidate worktree |

The SHA-256 of `operator-preflight.json` is included in the freeze evidence alongside
the run manifests and output-file hashes.

---

## 8. Environment discipline

### 8.1 Between arms

1. Stop the Showdown server process.
2. Stop the persistent calc backend (Node process).
3. Clear or unset every `SHOWDOWN_*` environment variable.
4. Set exactly the new arm's variables (§6.2 + §6.3).
5. Verify `SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S` is unset.
6. Restart the server with the new seed base + seed log.
7. Run the arm.

### 8.2 Cross-arm contamination

Each arm starts a fresh server + fresh backend. No shared state carries between arms.

---

## 9. Cache semantics

### 9.1 Row-level classification

Cold/warm is a property of **individual decision-profile rows**, not of entire battles.
The `backend_class` field in each v4 row is computed by `backend_class_of()` from the
row's own calc-counter deltas. A single battle may contain both `clean_cold` and
`clean_warm` rows (the first scored decision after a fresh backend spawn is cold;
subsequent decisions in the same battle are warm).

### 9.2 Aggregation rule

- Aggregation is performed exclusively by the **actual `backend_class` value** of each
  profile row.
- `clean_cold` and `clean_warm` rows are reported in **separate strata** — never pooled.
- `contaminated` rows (transport retry, unexpected respawn, or any combination not
  matching the two clean predicates) are counted separately. **Any `contaminated` row in
  any arm makes the entire preflight invalid.**

### 9.3 Repetitions vs. observations

- **30 battles** are the arm repetitions (the schedule has 30 rows).
- **Profile rows** are decision-level observations *within* those battles. A single
  battle produces one or more profile rows (one per scored decision). Profile rows are
  NOT additional repetitions.
- Evidence tables report both the battle count (from the result JSONL) and the
  observation count (from the profile JSONL), clearly distinguished.

---

## 10. Output files

All output under the attempt's output root (outside the candidate worktree; see §6.2).
Per arm:

| File | Content |
|---|---|
| `cost_preflight_<arm>_result.jsonl` | Gauntlet per-battle result (T2) |
| `cost_preflight_<arm>_profile.jsonl` | Decision-profile v4 rows |
| `cost_preflight_<arm>_seedlog.jsonl` | Server Channel-A seed log |
| `cost_preflight_<arm>_result.jsonl.manifest.json` | Run manifest |

Plus one shared file (written once before the first arm):

| File | Content |
|---|---|
| `operator-preflight.json` | Server provenance, live-checkout verification, output root (§7.1) |

Nothing is overwritten. Each arm writes to its own files.

---

## 11. Validation

### 11.1 Per-row validation (after each arm)

1. `validate_decision_profile_row` on every line of the profile JSONL.
2. Verify `git_sha` == `d64982ae9fdba6a877c8c2b7e804923ebcc7fec4` in every row.
3. Verify `config_hash` is consistent within the arm.

### 11.2 Dataset-level validation (after each arm)

4. `validate_live_profile_dataset(profile_path)` — this enforces:
   - single schema version (unique `(battle_id, decision_index)`, `source == "live"`).
5. **Explicit v4 check**: every row's `schema_version` field equals the string
   `"decision-profile-v4"` (`SCHEMA_VERSION_V4`). `validate_live_profile_dataset`
   enforces a *single* schema version but does not require a *specific* one — a pure v3
   dataset would pass its check. This additional assertion closes that gap.
6. Profile JSONL is **non-empty** (at least one scored decision occurred).
7. Every `battle_id` present in the 30 result rows has **at least one** corresponding
   profile row.
8. Result JSONL has exactly **30 rows**, with **zero crashes** and **zero invalid
   choices**.
9. Every profile row has `outcome == "ok"`, `selection_stage == "heuristic"`, and
   `fallback_reason` is `null`.

### 11.3 Cross-arm validation (after all four arms)

10. The sets of `battle_id` keys (derived from `seed_base + seed_index`) are **identical**
    across all four arms.
11. `schedule_hash`, `panel_hash`, and `seed_base` in every run manifest are identical
    across arms.
12. Every arm has a complete run manifest with all fields populated (including
    `showdown_commit`, `server_patch_hash`, `pythonhashseed`, `git_sha`, `dirty`).
13. Content hashes (SHA-256) of every output file are recorded for freeze evidence.

### 11.4 Cache-class validation (after all four arms)

14. No `contaminated` row exists in any arm. If any exists, the entire preflight is
    invalid.
15. `backend_class` values are exclusively `clean_cold` or `clean_warm`.

### 11.5 Invalidation

The preflight is **invalid** if any of the following occur in any arm:
- Timeout
- Degradation
- Chooser fallback (any `selection_stage` ∉ `{heuristic}`)
- Any `outcome` ∉ `{ok}`
- Any `fallback_reason` that is not `null`
- Missing telemetry field
- Malformed JSONL line
- Schema violation
- Wrong `git_sha`
- `dirty == true` in the run manifest
- Inconsistent `config_hash`
- Seed-log mismatch
- Result row count ≠ 30
- Result crash or invalid choice
- Empty profile dataset
- Missing profile row for any result battle_id
- Duplicate `(battle_id, decision_index)`
- Any `contaminated` `backend_class`
- Cross-arm schedule/panel/seed/battle-key mismatch
- Incomplete run manifest

No rows are filtered. No successful subset is reported as a result.

---

## 12. Required evidence (per arm × backend_class stratum)

Unchanged from parent spec §11.2, with the aggregation unit corrected:

Evidence is stratified by the **actual `backend_class` value** of each profile row
(`clean_cold`, `clean_warm`), not by battle ordinal. Each stratum reports:

- **Observation count** (profile rows in this stratum) and **battle count** (distinct
  battle_ids contributing rows to this stratum)
- p50, p95, and maximum `measured_ms`
- Timeout count
- Chooser-fallback and degradation count
- Turn-1 and Turn-2 `accuracy_leaf_count`
- Turn-1 and Turn-2 `accuracy_cap_hits`
- Deterministic `cap_fallback` count
- `search_topn_requested`, `search_topm_requested`, `depth2_candidates_selected`,
  `depth2_response_slots_eligible`
- Calc transport: `transport_calls`, `transport_attempts`, `spawn_calls`,
  `requests_total`, `requests_unique`, `cache_hits`
- `config_hash`, `git_sha`, `battle_id`

Plus: full commands, environment variables, seed base, host identity, run manifests,
output-file content hashes.

---

## 13. Claims

Unchanged from parent spec §11.3. The preflight produces **cost and readiness evidence
only**. It does not claim:

- Depth-2 is stronger
- Depth-2 is production-ready
- The live latency gate passed
- 1000 ms is a microprofile threshold
- Accuracy on/off shows a causal effect

---

## 14. Identity

The preflight run is identified by:

| Property | Value |
|---|---|
| Candidate SHA | `d64982ae9fdba6a877c8c2b7e804923ebcc7fec4` |
| Schedule hash | `b6f5910e4bc3c584` |
| Panel hash | `aac1ea30446fde88` |
| Seed base | `champions-panel-v0-d2-cost-preflight` |
| Arms | `d1_acc_off`, `d1_acc_on`, `d2_acc_off`, `d2_acc_on` (fixed order) |
| `PYTHONHASHSEED` | `0` |
| Showdown commit | `f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5` |
| Server patch hash | `86e31891547e87da` |
| Battle timeout | 180 s (unset) |

---

## 15. Completion

On a fully valid matrix: the parent spec's §12 step 11 ("Run and freeze the cost
preflight") is satisfied. The closeout statement moves from DRAFT to final.

On an invalid matrix: issue #123 stays open with the exact failure reason documented.

---

## Appendix A: Attempt 1 invalidation and Attempt 2 pre-registration

### A.1 Attempt 1 — invalidated (import-root provenance violation)

Attempt 1 completed all four arms (30/30 battles each, 0 crashes, 0 invalid choices, all
validation checks passed). However, the Python interpreter resolved `showdown_bot` from
the main repo's editable install (`C:\Users\chris\Documents\SHowdown BOt\showdown_bot\src`)
instead of the candidate worktree (`cost-preflight-worktree-d64982a/showdown_bot/src`).

**Evidence:** All four run manifests record `cli_invocation` with
`C:\Users\chris\Documents\SHowdown BOt\showdown_bot\src\showdown_bot\cli.py` — the main
worktree, not the detached candidate.

**Root cause:** The gauntlet was launched with CWD inside the candidate worktree but without
pinning `PYTHONPATH`. Python's module resolution picked up the editable install from the
main repo rather than the local `src/` directory.

**Note:** The production bytes at `d64982a` and `main` (`25d3dae`) are identical — only the
amendment and schedule YAML (which do not affect execution) differ. The data is technically
valid but the approved candidate-provenance contract (§2) was not met.

The 17 output files are preserved at `C:\Users\chris\Documents\attempt-1-invalid-import-root\`
with these SHA-256 hashes:

| File | SHA-256 |
|---|---|
| `cost_preflight_d1_acc_off_profile.jsonl` | `eab067701e95ecbeff37321976892dae03eb8dd7f22e96758d51d7b6853934ca` |
| `cost_preflight_d1_acc_off_result.jsonl` | `03f60a926d357bbc39c47b6f8c1041b5496d539f123a8e9b597038cd3781ef6d` |
| `cost_preflight_d1_acc_off_result.jsonl.manifest.json` | `e83ab72c22f27bc285ab5070b391f8b5d44a4638bd40381884a01c186ae3784e` |
| `cost_preflight_d1_acc_off_seedlog.jsonl` | `3362a305c20ef53b8846564281cc76bcbc2373713a3d324c8b651b29bf6bae43` |
| `cost_preflight_d1_acc_on_profile.jsonl` | `da37ef8a8faf84e5e64c6a74590a5e4c37b52b5551e0eb8272e9a209ba8aed55` |
| `cost_preflight_d1_acc_on_result.jsonl` | `91ab56a9bfe023427e0c6f4a1a2a91500a5198c879e3f34a4be6048625fc25c3` |
| `cost_preflight_d1_acc_on_result.jsonl.manifest.json` | `37fb73537b9369838e9563dd78bad42fc4805aab71fe69cb5261f0d690d1f762` |
| `cost_preflight_d1_acc_on_seedlog.jsonl` | `3362a305c20ef53b8846564281cc76bcbc2373713a3d324c8b651b29bf6bae43` |
| `cost_preflight_d2_acc_off_profile.jsonl` | `8a2e46724267d665394ea5e73e15e6bf2643f89b17280ad929501e23e00c78d6` |
| `cost_preflight_d2_acc_off_result.jsonl` | `0929f4e92224a4896b15d5f1d6b7e7d2c4146ec3c188c28ff5050d3f7a484808` |
| `cost_preflight_d2_acc_off_result.jsonl.manifest.json` | `10d623f5b5e1096c0d318c52091522abd38e3247996de66042aa6ee652530e8d` |
| `cost_preflight_d2_acc_off_seedlog.jsonl` | `3362a305c20ef53b8846564281cc76bcbc2373713a3d324c8b651b29bf6bae43` |
| `cost_preflight_d2_acc_on_profile.jsonl` | `f7ee981b95cc10b7c0ef4b840b01e9879021269e38b68dea8ede6271e9cc7baa` |
| `cost_preflight_d2_acc_on_result.jsonl` | `7b67fca260caece82b1e7b1dda596b8b6c163a651a3ac967f4d051e121439f66` |
| `cost_preflight_d2_acc_on_result.jsonl.manifest.json` | `cf9017d1184dcb4f5ab8b5459e16e3021b0440523f2683b9659825af2d288668` |
| `cost_preflight_d2_acc_on_seedlog.jsonl` | `3362a305c20ef53b8846564281cc76bcbc2373713a3d324c8b651b29bf6bae43` |
| `operator-preflight.json` | `d4e1c1b8cc5e8678e065599deb8716a981db7d492048c3f891b48ce710b7b123` |

No data from Attempt 1 may be reused, pooled, or cited as evidence for Attempt 2.

### A.2 Attempt 2 — pre-registration

| Property | Value |
|---|---|
| Reason for repeat | Import-root provenance violation (§2.1, Attempt 1) |
| Candidate SHA | `d64982ae9fdba6a877c8c2b7e804923ebcc7fec4` (unchanged) |
| Candidate worktree | same detached worktree as Attempt 1 |
| Output root | `cost-preflight-d2-d64982a-attempt2/` (sibling of candidate worktree, outside git tree) |
| `PYTHONPATH` | exclusively `<candidate-worktree>/showdown_bot/src` |
| Import-root verification | `showdown_bot.__file__` and `showdown_bot.cli.__file__` both under `<candidate>/showdown_bot/src/`, recorded in `operator-preflight.json` |
| Arms | same 4-arm matrix, same fixed order, same schedule, same seeds |
| Data isolation | no Attempt 1 data reused or pooled |

All other parameters (schedule, panel, seeds, server provenance, environment discipline,
validation rules) are unchanged from the body of this amendment.
