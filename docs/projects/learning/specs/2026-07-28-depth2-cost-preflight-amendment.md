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

**Current state:** Attempts 1–4 are invalidated (Appendix A.1–A.4). Attempt 5 is
pre-registered (Appendix A.5) and **not yet executed**. The Attempt-4 defect — the arm
variables never reached the gauntlet process, so all four arms ran identical code
defaults and no depth-2 search was executed — is closed by four independent checks added
in this revision: full variable names (§6.3), same-process environment delivery (§6.4),
a pre-arm resolver and `config_hash` gate (§7.3), and per-arm treatment validation —
enforced between arms — including a depth-2 frontier requirement (§11.0, §11.1a) and
cross-arm `config_hash` uniqueness (§11.3).

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

### 2.2 Calc backend dependencies

The persistent calc backend (`SHOWDOWN_CALC_BACKEND=persistent`) spawns a Node process
from `<candidate>/showdown_bot/tools/calc/calc.mjs`, which requires `@smogon/calc` in
`node_modules`. Since `node_modules` is gitignored, it must be installed in the candidate
worktree **before** writing `operator-preflight.json` and before battle 1.

Installation must use the frozen lockfile:

```
npm ci --prefix <candidate>/showdown_bot/tools/calc
```

`operator-preflight.json` (§7.1) records:

- `node_version`: output of `node --version`
- `npm_version`: output of `npm --version`
- `calc_lockfile_sha256`: SHA-256 of `<candidate>/showdown_bot/tools/calc/package-lock.json`
- `calc_deps_installed`: `true` after `npm ci` completes with exit code 0

All four values must be recorded **before** the first arm starts. If `npm ci` fails or
the lockfile is missing, the attempt is invalid.

**Rationale (Attempt 2):** Attempt 2 wrote `operator-preflight.json` before installing
the calc dependencies. The first arm (`d1_acc_off`) ran with a missing `node_modules`,
producing 239 contaminated fallback rows. The dependencies were then installed mid-run
via `npm install --omit=dev` (not `npm ci`), the contaminated arm output was deleted and
re-created under the same paths, and the remaining arms ran cleanly. This violated three
rules: §9.2/§11.5 (contaminated rows invalidate the preflight), §10 (nothing is
overwritten), and the operator-preflight no longer reflected the actual runtime
environment.

**Rationale (Attempt 1):** Attempt 1 ran with the process CWD inside the candidate
worktree but without pinning `PYTHONPATH`. Python resolved the installed editable package
from the main repo (`SHowdown BOt/showdown_bot/src`), so `cli_invocation` and
`showdown_bot.__file__` pointed to a different checkout. The production bytes were
identical (only the amendment/schedule YAML differ between `d64982a` and `25d3dae`), but
the approved candidate-provenance contract was not met. The 17 output files are preserved
as `attempt-1-invalid-import-root/` with frozen SHA-256 hashes (Appendix A). No data
from any invalidated attempt may be reused, pooled, or cited as evidence for a later
attempt.

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

- Attempt 1 (invalidated — see Appendix A.1): `cost-preflight-d2-d64982a/`
- Attempt 2 (invalidated — see Appendix A.2): `cost-preflight-d2-d64982a-attempt2/`
- Attempt 3 (invalidated — see Appendix A.3): `cost-preflight-d2-d64982a-attempt3/`
- Attempt 4 (invalidated — see Appendix A.4): `cost-preflight-d2-d64982a-attempt4/`
- **Attempt 5:** `cost-preflight-d2-d64982a-attempt5/`

All arms share:
- `PYTHONPATH=<candidate-worktree>/showdown_bot/src` (exclusive; no other entries — see §2.1)
- `SHOWDOWN_CALC_BACKEND=persistent`
- `SHOWDOWN_DECISION_PROFILE_OUT=<output-root>/cost_preflight_<arm>_profile.jsonl`
- `SHOWDOWN_BATTLE_SEED_BASE=champions-panel-v0-d2-cost-preflight`
- `SHOWDOWN_EVAL_SEED_LOG=<output-root>/cost_preflight_<arm>_seedlog.jsonl`
- `PYTHONHASHSEED=0`
- `--schedule` loaded via absolute path to the frozen YAML
- `--result-out <output-root>/cost_preflight_<arm>_result.jsonl`

where `<output-root>` is the absolute path to the current attempt's output directory
(Attempt 5: `cost-preflight-d2-d64982a-attempt5/`) and `<arm>` is one of `d1_acc_off`,
`d1_acc_on`, `d2_acc_off`, `d2_acc_on`.

### 6.3 Arm-specific environment

Variable names are given **in full**. Every name carries the `SHOWDOWN_` prefix, because
that is what the candidate's resolvers in
`showdown_bot/src/showdown_bot/battle/decision.py` actually read. A short name without
the prefix is silently ignored and the arm falls through to the code default — this is
exactly what invalidated Attempt 4 (Appendix A.4).

| Arm ID | `SHOWDOWN_SEARCH_DEPTH` | `SHOWDOWN_ACCURACY_MODE` | `SHOWDOWN_ACCURACY_BRANCH_CAP` | `SHOWDOWN_SEARCH_TOPN` | `SHOWDOWN_SEARCH_TOPM` |
|---|---|---|---|---|---|
| `d1_acc_off` | `1` | `0` | (unset) | (unset) | (unset) |
| `d1_acc_on` | `1` | `1` | `6` | (unset) | (unset) |
| `d2_acc_off` | `2` | `0` | (unset) | `3` | `3` |
| `d2_acc_on` | `2` | `1` | `6` | `3` | `3` |

Every `SHOWDOWN_*` variable listed above must be explicitly set or removed before each
arm. No arm inherits values from a previous arm.

**Code defaults when a variable is absent** (`decision.py`, candidate `d64982a`):

| Variable | Default when unset | Note |
|---|---|---|
| `SHOWDOWN_SEARCH_DEPTH` | `1` | `>= 2` resolves to depth 2, everything else to depth 1 |
| `SHOWDOWN_ACCURACY_MODE` | **`True`** | off requires an explicit `0`, `false`, or empty string — an absent variable means accuracy **on**, not off |
| `SHOWDOWN_ACCURACY_BRANCH_CAP` | `6` | |
| `SHOWDOWN_SEARCH_TOPN` | `2` | |
| `SHOWDOWN_SEARCH_TOPM` | `2` | |

The accuracy default is inverted relative to the naive expectation. An arm that intends
accuracy **off** must set `SHOWDOWN_ACCURACY_MODE=0`; removing the variable produces
accuracy **on**.

**Resolved treatment per arm** — the values the resolvers must return, and the values
every profile row of that arm must carry:

| Arm ID | `search_depth` | `accuracy_mode` | `accuracy_branch_cap` | `search_topn_requested` | `search_topm_requested` |
|---|---|---|---|---|---|
| `d1_acc_off` | `1` | `false` | `6` (default, unused) | `2` (default, unused) | `2` (default, unused) |
| `d1_acc_on` | `1` | `true` | `6` | `2` (default, unused) | `2` (default, unused) |
| `d2_acc_off` | `2` | `false` | `6` (default, unused) | `3` | `3` |
| `d2_acc_on` | `2` | `true` | `6` | `3` | `3` |

**Pre-registered expected `config_hash` per arm** (computed with the candidate code at
`d64982a`, `agent="heuristic"`, `format_id="gen9championsvgc2026regma"`, CWD
`<candidate>/showdown_bot`):

| Arm ID | `behavior_env` contents | Expected `config_hash` |
|---|---|---|
| `d1_acc_off` | `SHOWDOWN_ACCURACY_MODE=0`, `SHOWDOWN_SEARCH_DEPTH=1` | `03d2d5ee27911fc4` |
| `d1_acc_on` | `SHOWDOWN_ACCURACY_BRANCH_CAP=6`, `SHOWDOWN_ACCURACY_MODE=1`, `SHOWDOWN_SEARCH_DEPTH=1` | `50cf67d5b04a1b04` |
| `d2_acc_off` | `SHOWDOWN_ACCURACY_MODE=0`, `SHOWDOWN_SEARCH_DEPTH=2` | `b4c98c07c32f3f9f` |
| `d2_acc_on` | `SHOWDOWN_ACCURACY_BRANCH_CAP=6`, `SHOWDOWN_ACCURACY_MODE=1`, `SHOWDOWN_SEARCH_DEPTH=2` | `68e04be0173586b2` |

All four are distinct, and none equals `594295543f13a55d` — the hash produced by an
**empty** `behavior_env`, which is what all four Attempt-4 arms actually carried.

**`config_hash` cannot verify `SHOWDOWN_SEARCH_TOPN` / `SHOWDOWN_SEARCH_TOPM`.** Both are
in `EXCLUDED_BY_REASON` in `showdown_bot/src/showdown_bot/eval/config_env.py` and are
therefore absent from `behavior_env` and from `config_hash`. A depth-2 arm run with the
wrong frontier caps would still produce the pre-registered `config_hash`. The frontier
caps are verifiable **only** from the profile rows' `search_topn_requested` /
`search_topm_requested` fields — see §11.1a.

### 6.4 Environment delivery

Every arm sets its complete environment (§6.2 shared + §6.3 arm-specific) **inside one
PowerShell process**, which then launches **both** Python invocations for that arm as
children of itself. Environment set by one tool call does not survive into the next: each
PowerShell invocation is a fresh process, so an assignment made in an earlier call reaches
no later one.

Per arm, in a **single** PowerShell command, in this order:

1. `Remove-Item Env:SHOWDOWN_*` — clear every inherited `SHOWDOWN_*` variable.
2. `$env:*` assignments for §6.2 + §6.3, full `SHOWDOWN_`-prefixed names only.
3. Start the Showdown server (`node`) as a child of this process, so it inherits
   `SHOWDOWN_EVAL_SEED_LOG` and `SHOWDOWN_BATTLE_SEED_BASE` (§7.2).
4. **First Python child:** the verification script (§7.3).
5. **No environment mutation of any kind between steps 4 and 6.**
6. **Second Python child:** `python -m showdown_bot.cli gauntlet ...`.

Steps 4 and 6 are two distinct Python processes — `python -m showdown_bot.cli gauntlet`
dispatches straight to `run_gauntlet(args)` and offers no pre-run hook, so a verification
step cannot execute inside the gauntlet interpreter without a production code change,
which this amendment does not make. What binds them is the **shared parent environment**:
both inherit the identical environment block from the same PowerShell process, and no
assignment occurs between them. The verification child therefore observes exactly what the
gauntlet child will observe.

That inheritance argument is an argument, not evidence. The evidence is produced
afterwards: the gauntlet's own run manifest and every profile row carry a `config_hash`
computed from the gauntlet process's live environment. §11.1 and §11.3 check those against
the same pre-registered value the verification child checked. If the two children had
somehow differed, the manifest hash would not match, and the arm fails closed.

**Rationale (Attempt 4):** the arm variables were assigned, but under short names, and
nothing ever compared what a Python process actually resolved against what the arm
intended. Split environment delivery has the identical failure signature — variables that
look set but never reach the interpreter — so §7.3's verification plus §11's manifest and
row checks are the binding evidence, not the assignment itself.

### 6.5 Timeout

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
| `node_version` | output of `node --version` |
| `npm_version` | output of `npm --version` |
| `calc_lockfile_sha256` | SHA-256 of `<candidate>/showdown_bot/tools/calc/package-lock.json` |
| `calc_deps_installed` | `true` after `npm ci` completes with exit code 0 |

The SHA-256 of `operator-preflight.json` is included in the freeze evidence alongside
the run manifests and output-file hashes.

### 7.2 Server lifecycle provenance

§8.1 already requires stopping the Showdown server before each arm and restarting it
with the new arm's environment. This section makes the **reason** and the **evidence**
explicit.

`SHOWDOWN_EVAL_SEED_LOG` is a **server-side** environment variable: the Showdown server
reads it at process startup and writes one seed-log entry per battle for the lifetime of
that process. Changing the variable in the Python gauntlet process has no effect on the
already-running server. Consequently:

1. Before each arm, the previous server process must be **stopped** (not just
   disconnected) and port 8000 must be confirmed free.
2. The arm-specific `SHOWDOWN_EVAL_SEED_LOG` path must be set in the environment
   **before** the new server process is started.
3. The new server process must be started fresh. No server may serve battles for more
   than one arm.

**Rationale (Attempt 3):** The server started for arm 1 (`d1_acc_off`) was kept running
for arm 2 (`d1_acc_on`). The server still held arm 1's seed-log path, so the battle
from arm 2 was appended to arm 1's seed log (31 entries instead of 30). Arm 2's own
seed log was never created. The gauntlet's post-battle-1 seed-log wiring check detected
the mismatch and aborted after 1/30 battles, but by then the partial output files were
already written and arm 1's seed log was contaminated.

To make the server restart verifiable, each arm writes an **immutable** record before
battle 1:

`<output-root>/operator-server-<arm>.json`

| Field | Value |
|---|---|
| `arm_id` | one of `d1_acc_off`, `d1_acc_on`, `d2_acc_off`, `d2_acc_on` |
| `server_pid` | PID of the newly started server process |
| `previous_server_pid` | PID of the previous arm's server (or `null` for the first arm) |
| `previous_server_stopped` | `true` if the previous server process is confirmed stopped (or `null` for the first arm) |
| `port_free_before_start` | `true` if port 8000 was confirmed free before the new server started |
| `server_start_command` | `node pokemon-showdown start --no-security` |
| `seed_log_path` | absolute path to this arm's `SHOWDOWN_EVAL_SEED_LOG` |
| `seed_log_absent_or_empty_before_start` | `true` if the seed log file did not exist or was empty before the server started |
| `utc_start_time` | ISO 8601 UTC timestamp of server start |
| `arm_env_raw` | object: every arm-specific `SHOWDOWN_*` name from §6.3 mapped to its literal value as read back from the process environment, or `null` if unset. Full names only. |
| `resolved_search_depth` | return value of `decision._search_depth()` in the verification child (§6.4 step 4) |
| `resolved_accuracy_mode` | return value of `decision._accuracy_mode()` |
| `resolved_accuracy_branch_cap` | return value of `decision._accuracy_branch_cap()` |
| `resolved_search_topn` | return value of `decision._search_topn()` |
| `resolved_search_topm` | return value of `decision._search_topm()` |
| `expected_config_hash` | the arm's pre-registered `config_hash` from §6.3 |
| `computed_config_hash` | `make_config_hash(effective_config_manifest(agent="heuristic", format_id="gen9championsvgc2026regma"))` evaluated in the verification child against the live environment |
| `resolvers_match_arm` | `true` if all five resolved values equal §6.3's resolved-treatment row for this arm |
| `config_hash_matches_expected` | `computed_config_hash == expected_config_hash` |

These files are included in §10's output inventory and in the final hash freeze.
Once written, they must not be deleted, emptied, or re-created.

**Fail-closed conditions (server lifecycle):**

The entire attempt is invalid if any of the following occur:

- Any `operator-server-<arm>.json` field is missing or `false` where `true` is required.
- The previous server process is still running when the new arm begins.
- Port 8000 is occupied before the new server starts.
- The `seed_log_path` does not match the arm's expected
  `<output-root>/cost_preflight_<arm>_seedlog.jsonl`.
- After an arm completes, its seed log does not contain exactly **30 entries**.
- `resolvers_match_arm` is `false`, or `config_hash_matches_expected` is `false`.

A failed attempt must not be repaired or continued. A retry requires a new output root
and a new attempt pre-registration.

### 7.3 Pre-arm treatment verification

Files on disk and shell assignments are not evidence of what an interpreter loaded. The
check runs in the **first Python child** of the arm's PowerShell process (§6.4 step 4),
after the server is started (so `server_pid` is known) and before the gauntlet child is
launched:

1. Import the candidate's `showdown_bot.battle.decision` and assert
   `decision.__file__` is under `<candidate>/showdown_bot/src/` (§2.1's rule, applied to
   the module that owns the resolvers).
2. Call `_search_depth()`, `_accuracy_mode()`, `_accuracy_branch_cap()`,
   `_search_topn()`, `_search_topm()` and compare all five against §6.3's
   resolved-treatment row for this arm.
3. Compute `config_hash` from the live environment and compare against §6.3's
   pre-registered value for this arm.
4. Read back each arm-specific variable from `os.environ` and record it verbatim in
   `arm_env_raw`.
5. Write `operator-server-<arm>.json` with all of the above, including the two match
   flags.

**On failure of any comparison in (1)–(3):**

- `operator-server-<arm>.json` **is** written, with `resolvers_match_arm` and/or
  `config_hash_matches_expected` set to `false` and the observed values recorded. It is
  the immutable failure record and must not be deleted or edited afterwards.
- The Showdown server for this arm is stopped.
- The gauntlet child is **not** launched. No result, profile, or manifest file is created
  for this arm.
- The entire attempt is invalid (§7.2 fail-closed list, §11.5). It must not be repaired or
  continued; a retry needs a new output root and a new pre-registration.

This is the only case in which an attempt's output root legitimately contains fewer than
21 files (§10). A failure record without its arm's four data files is the expected shape
of a pre-arm abort, not a violation of output completeness.

This verification alone does not prove the *gauntlet* process saw the same environment —
it is a different process. §6.4 explains why the inheritance holds, and §11.1 / §11.3
supply the post-hoc evidence from the gauntlet's own manifest and profile rows.

---

## 8. Environment discipline

### 8.1 Between arms

1. Stop the Showdown server process.
2. Stop the persistent calc backend (Node process).
3. Clear or unset every `SHOWDOWN_*` environment variable.
4. Set exactly the new arm's variables (§6.2 + §6.3), using full `SHOWDOWN_`-prefixed
   names, in the same process that will launch the server and Python (§6.4).
5. Verify `SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S` is unset.
6. Restart the server with the new seed base + seed log.
7. Run the pre-arm treatment verification as the first Python child and write
   `operator-server-<arm>.json` (§7.3). Do not launch the gauntlet if any comparison
   fails.
8. Run the arm.
9. After the arm's gauntlet child exits, run the post-arm treatment gate (§11.0) before
   returning to step 1 for the next arm.

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
| `operator-server-<arm>.json` | Server lifecycle provenance (§7.2) |

Plus one shared file (written once before the first arm):

| File | Content |
|---|---|
| `operator-preflight.json` | Server provenance, live-checkout verification, output root (§7.1) |

Expected total: **21 files** per complete attempt (5 per arm × 4 arms + 1 shared). An
attempt aborted by §7.3's pre-arm gate ends with fewer files: the failed arm contributes
only its `operator-server-<arm>.json` failure record and no data files. That shape is
defined in §7.3 and is still an invalid attempt.

Nothing is overwritten. Each arm writes to its own files. Once an attempt begins
(operator-preflight.json is written), no output file under that attempt's output root
may be deleted, emptied, or re-created. Any arm failure invalidates the entire attempt;
a retry requires a new output root and a new attempt pre-registration.

---

## 11. Validation

### 11.0 Post-arm treatment gate (between arms)

**No arm may start until the preceding arm's treatment has been verified.**

After each arm's gauntlet child exits, and **before** the next arm's environment is set or
its server is started, run §11.1a against that arm's completed profile JSONL. If any row
deviates, the attempt is invalid and no further arm is started.

The check is post-arm rather than post-battle-1 by necessity, not preference.
`python -m showdown_bot.cli gauntlet` dispatches to `run_gauntlet(args)` and executes all
30 battles synchronously; there is no pause point, no per-battle callback, and no
supported way for an external observer to halt it after battle 1. Specifying "abort after
battle 1" would describe a mechanism that does not exist.

The gauntlet does contain one post-battle-1 abort — the seed-log wiring check that
terminated Attempt 3's arm 2 — but that check is **inside** `run_gauntlet`, written into
production code. It is evidence that such a gate is implementable, not that an external
observer can impose one. Adding a treatment gate at the same point would be a production
change to the gauntlet loop; the alternative is a fully specified background monitor with a
defined kill path. Neither is in scope for this amendment, and neither is needed to close
the Attempt-4 defect.

The exposure this leaves is bounded and acceptable: §7.3's pre-arm gate already blocks the
known failure mode before battle 1 of every arm, so a treatment error would have to survive
a resolver comparison *and* a `config_hash` comparison to reach the gauntlet at all. §11.0
bounds the residual worst case at **one arm** of wasted output (30 battles) instead of
Attempt 4's four (120 battles).

### 11.1 Per-row validation (after each arm)

1. `validate_decision_profile_row` on every line of the profile JSONL.
2. Verify `git_sha` == `d64982ae9fdba6a877c8c2b7e804923ebcc7fec4` in every row.
3. Verify `config_hash` is consistent within the arm **and** equals the arm's
   pre-registered value from §6.3.

### 11.1a Treatment validation (after each arm)

Every profile row of the arm must carry the arm's resolved treatment:

| Arm ID | `search_depth` | `accuracy_mode` | `accuracy_branch_cap` | `search_topn_requested` | `search_topm_requested` |
|---|---|---|---|---|---|
| `d1_acc_off` | `1` | `false` | `6` | `2` | `2` |
| `d1_acc_on` | `1` | `true` | `6` | `2` | `2` |
| `d2_acc_off` | `2` | `false` | `6` | `3` | `3` |
| `d2_acc_on` | `2` | `true` | `6` | `3` | `3` |

A single row deviating on any of the five fields invalidates the attempt. No row is
filtered and no majority rule applies.

**Depth-2 frontier evidence.** For `d2_acc_off` and `d2_acc_on`, at least one profile row
must have `depth2_frontier > 0`. Depth-2 rows with a uniformly zero frontier mean no
depth-2 search was executed and therefore no depth-2 cost was measured — the arm produced
no evidence for the question the preflight exists to answer, regardless of how many
battles completed. This check is separate from the `search_depth == 2` check: `search_depth`
records the requested depth, `depth2_frontier` records that a frontier was actually
expanded.

For `d1_acc_off` and `d1_acc_on`, every row must have `depth2_frontier == 0`.

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
14. **`config_hash` uniqueness across arms.** The four run manifests' `config_hash`
    values must be **four distinct values**, and each must equal its arm's pre-registered
    value from §6.3. Four identical hashes mean the arms were not differentiated and the
    attempt is invalid — this is the check that would have caught Attempt 4 without
    reading a single profile row.
15. The four `config_hash` values must all differ from `594295543f13a55d`, the hash of an
    **empty** `behavior_env`. That value means no arm-specific `SHOWDOWN_*` variable
    reached the process.

### 11.4 Cache-class validation (after all four arms)

16. No `contaminated` row exists in any arm. If any exists, the entire preflight is
    invalid.
17. `backend_class` values are exclusively `clean_cold` or `clean_warm`.

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
- Inconsistent `config_hash`, or a `config_hash` ≠ the arm's pre-registered value (§6.3)
- Fewer than four distinct `config_hash` values across the four arms
- Any profile row whose `search_depth`, `accuracy_mode`, `accuracy_branch_cap`,
  `search_topn_requested`, or `search_topm_requested` deviates from §11.1a
- No profile row with `depth2_frontier > 0` in either depth-2 arm
- Any `depth2_frontier > 0` in either depth-1 arm
- `resolvers_match_arm` or `config_hash_matches_expected` `false` in any
  `operator-server-<arm>.json` (§7.2, §7.3)
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
| Attempt | `5` |
| Output root | `cost-preflight-d2-d64982a-attempt5/` |
| Expected `config_hash` per arm | `d1_acc_off` `03d2d5ee27911fc4`, `d1_acc_on` `50cf67d5b04a1b04`, `d2_acc_off` `b4c98c07c32f3f9f`, `d2_acc_on` `68e04be0173586b2` |
| Node | `v24.16.0` |
| npm | `11.13.0` |
| Calc lockfile SHA-256 | `c03c577c3e62c7c1de12ba74ac60ca311bf3dd077e37e09c30d5269f2b61dabe` |

---

## 15. Completion

On a fully valid matrix: the parent spec's §12 step 11 ("Run and freeze the cost
preflight") is satisfied. The closeout statement moves from DRAFT to final.

On an invalid matrix: issue #123 stays open with the exact failure reason documented.

---

## Appendix A: Attempt history

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

No data from Attempt 1 may be reused, pooled, or cited as evidence.

### A.2 Attempt 2 — invalidated (contaminated arm, overwritten output, stale preflight)

Attempt 2 fixed the import-root provenance violation (§2.1) but introduced three new
invalidation reasons:

1. **Contaminated arm (§9.2 / §11.5):** The first run of `d1_acc_off` started before
   the calc backend's Node dependencies (`@smogon/calc`) were installed in the candidate
   worktree. All 239 profile rows were `outcome=fallback`,
   `selection_stage=deterministic_default_pair`, `backend_class=contaminated`. Any
   contaminated row invalidates the entire preflight.

2. **Overwritten output (§10):** The contaminated arm's four output files were deleted
   and re-created under the same paths within the same output root. §10 requires that
   nothing is overwritten; the original contaminated files can no longer be frozen as
   evidence.

3. **Stale operator-preflight (§7.1 / §2.2):** `operator-preflight.json` was written
   before `npm install --omit=dev` installed the calc dependencies. The recorded preflight does not
   reflect the actual runtime environment (missing `node_version`, `npm_version`,
   `calc_lockfile_sha256`, `calc_deps_installed` fields; and the calc backend was
   non-functional at the time of recording).

The 17 surviving output files (arms 2–4 are clean; arm 1 is the re-run, not the
original contaminated output) are preserved at
`C:\Users\chris\Documents\cost-preflight-d2-d64982a-attempt2\` with these SHA-256 hashes:

| File | SHA-256 |
|---|---|
| `cost_preflight_d1_acc_off_profile.jsonl` | `6919f06efd8f43e3a10e9e9dfaf827ee084bf7c5da081834cbb00ec2e7fd4f1f` |
| `cost_preflight_d1_acc_off_result.jsonl` | `b06d6b023feea94160608476583114e06d00dc059cb2a43690c228e7eb8263d3` |
| `cost_preflight_d1_acc_off_result.jsonl.manifest.json` | `ce46c50f7979efcc7c4c5661113a73bd52ddd93d81fffed22fad17196f6347da` |
| `cost_preflight_d1_acc_off_seedlog.jsonl` | `3362a305c20ef53b8846564281cc76bcbc2373713a3d324c8b651b29bf6bae43` |
| `cost_preflight_d1_acc_on_profile.jsonl` | `01d76e1c1ef28e50dacf1534aea514243aa91eea6a778f30d541a6c8d49dcb50` |
| `cost_preflight_d1_acc_on_result.jsonl` | `384eccab9e87f27167a1c0b15379ff89d3a843f369a5756cc3760bfa4b0bd13d` |
| `cost_preflight_d1_acc_on_result.jsonl.manifest.json` | `3a34a3bbc9de4738c1d614d8f5bc8b5aa636addc019ea8d2dae846769e3934eb` |
| `cost_preflight_d1_acc_on_seedlog.jsonl` | `3362a305c20ef53b8846564281cc76bcbc2373713a3d324c8b651b29bf6bae43` |
| `cost_preflight_d2_acc_off_profile.jsonl` | `c613309d578a62b2c7038b4f8585599f2bb6ed93e090fa1e9052dd67254b95c1` |
| `cost_preflight_d2_acc_off_result.jsonl` | `aace11426e05a3464e4c83a0ef5c9c73ea5371b1f37891513b82cb4ac07443ea` |
| `cost_preflight_d2_acc_off_result.jsonl.manifest.json` | `6bbbef81f8975a6597241da8487d1f2906009c34086a129b6a8ebccc8798182a` |
| `cost_preflight_d2_acc_off_seedlog.jsonl` | `3362a305c20ef53b8846564281cc76bcbc2373713a3d324c8b651b29bf6bae43` |
| `cost_preflight_d2_acc_on_profile.jsonl` | `1ba31c0144e3335e7d83b8b58624ad86a31988b21b68bd6724e26d56825a6e0a` |
| `cost_preflight_d2_acc_on_result.jsonl` | `bae5373701f05fb2d71125a983e2db3438aaee3da0bc5f5eed0456126e057ffb` |
| `cost_preflight_d2_acc_on_result.jsonl.manifest.json` | `d5f9d8a8270c43a5df72b9030730ee2e35771827bc053e8cc49e3bb13bbf62f4` |
| `cost_preflight_d2_acc_on_seedlog.jsonl` | `3362a305c20ef53b8846564281cc76bcbc2373713a3d324c8b651b29bf6bae43` |
| `operator-preflight.json` | `a4760c7a3768fe6e9abae271dc99344eb4d6676ba498be55440304d4e0a34ebe` |

**Note:** The `d1_acc_off` files above are the **re-run** output, not the original
contaminated output. The original contaminated files (239 fallback rows) were deleted
mid-attempt and cannot be frozen. This is itself an invalidation reason (point 2 above).

No data from Attempt 1 or Attempt 2 may be reused, pooled, or cited as evidence.

### A.3 Attempt 3 — invalidated (server lifecycle violation, seedlog contamination)

Attempt 3 fixed the import-root provenance (§2.1) and calc dependency (§2.2) issues
from Attempts 1 and 2. Arm 1 (`d1_acc_off`) completed 30/30 battles and passed all
per-arm validation checks. However, the Showdown server was **not restarted** between
arms 1 and 2, violating §8.1 and §7.2.

**Failure sequence:**

1. Arm 1 (`d1_acc_off`) completed normally (30/30 battles, 0 crashes, 0 invalid, all
   profile rows `clean_cold`/`clean_warm`, correct `cli_invocation`).
2. The server (PID 11104) was kept running for arm 2. The server still held arm 1's
   `SHOWDOWN_EVAL_SEED_LOG` path.
3. Arm 2 (`d1_acc_on`) started. Battle 1 completed (winner=BaselineBot7845). The
   server wrote the battle's seed entry to **arm 1's** seed log (because the server's
   `SHOWDOWN_EVAL_SEED_LOG` was never updated).
4. After battle 1, the gauntlet's seed-log wiring check found arm 2's seed log absent
   and aborted with: "seed-log wiring incomplete: after battle 1 the log is still
   empty or absent."
5. Arm 2 wrote three partial output files (profile, result, manifest) for its single
   completed battle. Arm 2's seed log was never created.

**Invalidation reasons:**

1. **Arm 2 partial failure (§11.5):** `d1_acc_on` completed 1/30 battles and aborted.
   Three partial output files were written to the output root.
2. **Arm 1 seedlog contamination:** Arm 1's seed log contains **31 entries** instead
   of 30 — the server appended arm 2's battle seed because it was still using arm 1's
   seed-log path. The seed-log hash changed from its post-arm-1 value.
3. **Arm 2 missing seedlog:** No seed log exists for arm 2 (`d1_acc_on`) because the
   server never wrote to the arm 2 path.

The 8 surviving output files are preserved at
`C:\Users\chris\Documents\cost-preflight-d2-d64982a-attempt3\` with these SHA-256
hashes:

| File | SHA-256 |
|---|---|
| `cost_preflight_d1_acc_off_profile.jsonl` | `77cec14ea7c86e16fbf7d7e62e18a5874df311bdd38f78bde51f2eb8b80bb014` |
| `cost_preflight_d1_acc_off_result.jsonl` | `65a6ddba5a0bc75cdbecbb21525677aaf5ea4fe768f0c784d3c1f6c5fa615734` |
| `cost_preflight_d1_acc_off_result.jsonl.manifest.json` | `ee556fcf6737091417cfad4a1db82b5002e7d25cd1c5024206c8b2e78c2561bc` |
| `cost_preflight_d1_acc_off_seedlog.jsonl` | `fdeb47c8cb922687136fffb1fa93fa616dd7a2a87b15936e76f9a7c452c2bcda` |
| `cost_preflight_d1_acc_on_profile.jsonl` | `7e6821ef105159c6f58dfd420f7f65d7bf797e7a634045c8d8f5c928039e7338` |
| `cost_preflight_d1_acc_on_result.jsonl` | `1046743417be61be90d304e6c0df0a1c561a5bd6635ff6438e08c78d9d2cc21b` |
| `cost_preflight_d1_acc_on_result.jsonl.manifest.json` | `6d6fa99dd747513e058b2bcb93f42e2ecaa4381e4a76a10a4da5ecd99326f5c5` |
| `operator-preflight.json` | `baa34b101b11eb5732dc5ad9f772428fe3bf04e7a9b1b4fd649de63179986b5a` |

**Note:** The `d1_acc_off_seedlog.jsonl` hash above reflects the **contaminated** state
(31 entries). The pre-contamination 30-entry hash was not captured before arm 2 ran.

No data from any invalidated attempt may be reused, pooled, or cited as evidence for a
later attempt.

### A.4 Attempt 4 — invalidated (arm-specific environment never reached the process)

Attempt 4 fixed every defect from Attempts 1–3. All four arms completed **30/30 battles**
with zero crashes and zero invalid choices. The server was stopped and restarted before
each arm, port 8000 was confirmed free each time, each arm wrote its own
`operator-server-<arm>.json`, and each arm's seed log contains exactly 30 entries. All 21
expected output files exist.

The attempt is nevertheless invalid, and the reason is more serious than a partial
failure: **no arm ran the treatment it was supposed to run.**

**Failure:** §6.3 listed the arm-specific variables under short names — `SEARCH_DEPTH`,
`ACCURACY_MODE`, `ACCURACY_BRANCH_CAP`, `SEARCH_TOPN`, `SEARCH_TOPM`. The resolvers in
`showdown_bot/src/showdown_bot/battle/decision.py` read the `SHOWDOWN_`-prefixed names
(`SHOWDOWN_SEARCH_DEPTH`, etc.). The short-named variables were set, seen by no one, and
every arm fell through to the code defaults.

**Evidence:**

1. All four arms have **identical** `config_hash` `594295543f13a55d` in both the run
   manifest and every profile row. That value reproduces exactly from an **empty**
   `behavior_env` under the candidate code — no arm-specific `SHOWDOWN_*` variable was
   present in the process.
2. Every profile row of every arm carries the same treatment:
   `search_depth=1`, `accuracy_mode=true`, `accuracy_branch_cap=6`,
   `search_topn_requested=2`, `search_topm_requested=2`, `depth2_frontier=0`.
   Each arm emitted exactly **293** profile rows — the four arms are the same experiment
   run four times.
3. `depth2_frontier == 0` in all 1172 profile rows. **No depth-2 search was executed in
   any arm.** The preflight exists to measure depth-2 cost; it measured none.
4. The intended `accuracy_mode=false` arms ran with accuracy **on**, because
   `SHOWDOWN_ACCURACY_MODE` defaults to `True` when absent (§6.3). An unset accuracy
   variable does not mean accuracy off.

**Invalidation reasons:** §11.5 — no distinct `config_hash` across arms; every profile row
deviates from the arm's intended treatment; no depth-2 frontier evidence in either
depth-2 arm.

The 21 output files are preserved at
`C:\Users\chris\Documents\cost-preflight-d2-d64982a-attempt4\` with these SHA-256 hashes:

| File | SHA-256 |
|---|---|
| `cost_preflight_d1_acc_off_profile.jsonl` | `c4c55759b2ea129be45da4556c5a98c2ebfb244b0c01360de715f172d26d0508` |
| `cost_preflight_d1_acc_off_result.jsonl` | `c0a74d7c2f68740b654cc46b71a1fa35f11f51a436607ebd68593b9f2d87334a` |
| `cost_preflight_d1_acc_off_result.jsonl.manifest.json` | `160efebac1340965b30af0e79522e1d128c2a5e1b808b27e4d7ae404ad071fa8` |
| `cost_preflight_d1_acc_off_seedlog.jsonl` | `3362a305c20ef53b8846564281cc76bcbc2373713a3d324c8b651b29bf6bae43` |
| `cost_preflight_d1_acc_on_profile.jsonl` | `13da96cbd5e1f4b0c94e2d4c4b3233f08ea9f834fcd32d429b92bae40135243d` |
| `cost_preflight_d1_acc_on_result.jsonl` | `58235e07fa43633414d66b4c23ac7d74e1006510f50878806b1186497864fd5e` |
| `cost_preflight_d1_acc_on_result.jsonl.manifest.json` | `1664f8b44d425956015f39f226ba6292f676c8c78253cf0a88bc705d8db79667` |
| `cost_preflight_d1_acc_on_seedlog.jsonl` | `3362a305c20ef53b8846564281cc76bcbc2373713a3d324c8b651b29bf6bae43` |
| `cost_preflight_d2_acc_off_profile.jsonl` | `f5b18ca8faba30dfb7ade2a4a7a30af5726a8e404c0dfaf5a76625f2c67c2260` |
| `cost_preflight_d2_acc_off_result.jsonl` | `334108512b10a9d20b142252784c6fd01ba3acd1cb44f648498d585a14d733f9` |
| `cost_preflight_d2_acc_off_result.jsonl.manifest.json` | `d994d0473df52910155ac75a0829df1025da9b70b1f3cc57c860ce267bb981ef` |
| `cost_preflight_d2_acc_off_seedlog.jsonl` | `3362a305c20ef53b8846564281cc76bcbc2373713a3d324c8b651b29bf6bae43` |
| `cost_preflight_d2_acc_on_profile.jsonl` | `9574c51f4933325ca8b0f9c9057651952b7452091a807588c5e5ae5404e1f707` |
| `cost_preflight_d2_acc_on_result.jsonl` | `47c357ce13ae6f70dbfd2f3cbb7c6accb81437f3bdeb16d57d7aee57114e6328` |
| `cost_preflight_d2_acc_on_result.jsonl.manifest.json` | `cd74d23ee36a3ea87eec5d7126f8220023a300b62a3d0ba141ccccde098c93ad` |
| `cost_preflight_d2_acc_on_seedlog.jsonl` | `3362a305c20ef53b8846564281cc76bcbc2373713a3d324c8b651b29bf6bae43` |
| `operator-preflight.json` | `2487dd3d6bf5619859da5caca58fa0b0ad439fac4d66a47bb10f47f7b767d7cd` |
| `operator-server-d1_acc_off.json` | `a7d8cdde46b070614c466e137f320b18dda551c669cc1fea06355203daa7b059` |
| `operator-server-d1_acc_on.json` | `1668653ecd0bb4a84e5617b46d90078f991e6b66ae6ec113fe56b32a31fade0f` |
| `operator-server-d2_acc_off.json` | `4082dd46fc5887997ec8d2080aefaaca2888bef036302ff8ce35929bc6a28d4c` |
| `operator-server-d2_acc_on.json` | `150d0a6ac002ce50c934eef82c918a5bc9aeb09b61a4b86ac070000d373d79f2` |

The four seed logs share one hash: same seed base, same schedule, same 30 seeds. That is
expected and independently confirms the server *was* correctly restarted per arm — the
lifecycle fix from Attempt 3 worked. Only the treatment did not.

**What this attempt cost and what it bought.** Four arms × 30 battles produced zero usable
cost evidence. It did produce the diagnosis, and the checks added in §6.3, §6.4, §7.3,
§11.0, §11.1a, and §11.3 items 14–15 would each independently have caught it. §7.3's
pre-arm gate would have caught it before arm 1's first battle, and §11.0 would have
stopped the run after arm 1 rather than arm 4.

No data from any invalidated attempt may be reused, pooled, or cited as evidence for a
later attempt.

### A.5 Attempt 5 — pre-registration

| Property | Value |
|---|---|
| Reason for repeat | Arm-specific environment never reached the gauntlet process (§A.4): short variable names, all four arms ran code defaults, no depth-2 search executed |
| Candidate SHA | `d64982ae9fdba6a877c8c2b7e804923ebcc7fec4` (unchanged) |
| Candidate worktree | same detached worktree as Attempts 1–4 |
| Output root | `cost-preflight-d2-d64982a-attempt5/` (sibling of candidate worktree, outside git tree) |
| `PYTHONPATH` | exclusively `<candidate-worktree>/showdown_bot/src` |
| Import-root verification | `showdown_bot.__file__`, `showdown_bot.cli.__file__`, and `showdown_bot.battle.decision.__file__` all under `<candidate>/showdown_bot/src/` |
| Calc dependencies | `npm ci --prefix <candidate>/showdown_bot/tools/calc` **before** writing `operator-preflight.json`; lockfile SHA-256 `c03c577c3e62c7c1de12ba74ac60ca311bf3dd077e37e09c30d5269f2b61dabe` |
| Node version | `v24.16.0` |
| npm version | `11.13.0` |
| Arm variable names | full `SHOWDOWN_`-prefixed names only (§6.3) |
| Environment delivery | one PowerShell process per arm sets the environment and launches both Python children (verification, then gauntlet) with no assignment between them (§6.4) |
| Pre-arm treatment gate | resolver + `config_hash` verification in the first Python child of the arm's shell process, before the gauntlet child is launched; recorded in `operator-server-<arm>.json` (§7.3) |
| Expected `config_hash` | `d1_acc_off` `03d2d5ee27911fc4`, `d1_acc_on` `50cf67d5b04a1b04`, `d2_acc_off` `b4c98c07c32f3f9f`, `d2_acc_on` `68e04be0173586b2` — four distinct values, none equal to `594295543f13a55d` |
| Post-arm gate | profile rows verified against §11.1a after each arm completes and before the next arm starts (§11.0) |
| Depth-2 evidence gate | ≥1 profile row with `depth2_frontier > 0` in each depth-2 arm; `depth2_frontier == 0` in every depth-1 row (§11.1a) |
| Server lifecycle | server stopped and restarted before each arm per §7.2; `operator-server-<arm>.json` written before battle 1 of each arm |
| Operator-preflight timing | written **after** calc dependency installation and import-root verification, **before** battle 1 |
| Arms | same 4-arm matrix, same fixed order, same schedule, same seeds |
| Expected output files | 21 (5 per arm × 4 arms + 1 shared `operator-preflight.json`) |
| Output immutability | no output file may be deleted, emptied, or re-created after `operator-preflight.json` is written; any arm failure invalidates the entire attempt |
| Data isolation | no data from Attempts 1–4 reused or pooled |

All other parameters (schedule, panel, seeds, server provenance, environment discipline,
validation rules) are unchanged from the body of this amendment.
