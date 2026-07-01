# 2b-3.5 T3f — T4/T5 Run-Provenance Readiness — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. **Git owner:
> Bau-Claude** (autonomous track paused). Steps use `- [ ]`. A slice inserted **after T3e, before T4**,
> that lands the result-schema + run-provenance additions T5 will consume. Promotes the accepted §1
> findings of `docs/superpowers/reviews/2026-07-01-fable-t5-t6-eval-architecture-review.md` (non-binding
> review artifact). **Plan only — no code until reviewed.**

**Goal:** Make each result-JSONL run **self-describing and pairable** so T5 can consume two runs safely:
add `seed_base`, `run_id` + a run manifest, `panel_split`, `end_reason` to the row/writer; **redefine
`config_hash`** over the effective config (so two behaviorally-different bots never collide); and **pin
the latency budget** as a number. Statistics (Wilson/McNemar) and gate logic stay in **T5**.

**Depends on:** T3e merged (its P4 already added `dirty` + `hero_team_hash`/`opp_team_hash` and documented
`battle_id` as the pairing key; T3f does not repeat those).

**Architecture:** Additive fields on `eval/result_jsonl` + `eval/schedule.ScheduleRow`; the panel generator
stamps `panel_split`; `cli.run_schedule` populates the new row fields, computes the effective
`config_hash`, and emits a `<result-out>.manifest.json` run manifest. `battle/` untouched (INV-1).

**Tech Stack:** stdlib (hashlib/json/os/subprocess), `learning/provenance.git_sha_and_dirty`, the existing
`eval/{schedule,panel,panel_schedule,result_jsonl}` + `cli.run_schedule`.

---

## Cross-cutting rules
- **T3f-CC-1 — additive + truthful.** New fields only; `schedule_hash` and `battle_id` **unchanged**
  (provenance fields are not part of the identity payload). Legacy schedules → new fields `null`/default.
- **T3f-CC-2 — `config_hash` must separate behavior.** Two bots that would play differently MUST get
  different `config_hash` (proven by a test flipping a behavior-affecting env flag).
- **T3f-CC-3 — the run is self-describing.** A single `--result-out` run emits a manifest sidecar with
  the full environment/provenance so T5 never has to re-derive it.

---

## Task 1 — Effective `config_hash` (behavior-covering, **fail-closed** env classification)

**Problem (review §1/§10):** `make_config_hash(config_id, format_id)` — two behaviorally different bots
share it → a config can be paired against itself (`n_discordant≈0` reads as "perfectly safe").

**Design principle (Plan-Claude required):** **fail-closed.** A *forgotten* behavior-affecting env var is
dangerous (same `config_hash`, different behavior). An *over-included* env var is safe (only makes runs
non-pairable). So config_hash **includes every set `SHOWDOWN_*` env var EXCEPT a documented non-behavioral
denylist** — not an incomplete allowlist-with-examples. Two explicit, documented sets classify every
`SHOWDOWN_*` read; a drift test forbids unclassified reads.

**Files:** Create `eval/config_env.py` (the two classification sets + `behavior_env()`); Modify
`eval/result_jsonl.py` (`make_config_hash`); Modify `cli.run_schedule`; Tests `tests/test_config_env.py`,
`tests/test_result_jsonl.py`.

- [ ] **Step 1 — classification (`eval/config_env.py`):**
  - **`BEHAVIOR_AFFECTING`** (documented, must include at minimum): `SHOWDOWN_ROLLOUT_HORIZON`,
    `SHOWDOWN_PROTECT_PENALTY`, `SHOWDOWN_MUST_REACT_LAMBDA`, `SHOWDOWN_OPP_SETS`, `SHOWDOWN_OUR_ROLL`,
    `SHOWDOWN_OUR_DEF_PRESET`, `SHOWDOWN_OPP_SPEED`, `SHOWDOWN_REAL_SPREADS`, `SHOWDOWN_RERANKER_SHADOW`,
    `SHOWDOWN_RERANKER_MODEL_PATH`, `SHOWDOWN_RERANKER_MANIFEST_PATH`, `SHOWDOWN_RERANKER_SHADOW_TIMEOUT_MS`,
    **`SHOWDOWN_CALC_TIMEOUT_MS`** (a calc timeout can trigger fallback behavior under load → behavior-affecting).
  - **`NON_BEHAVIORAL`** (documented denylist; exact names + prefix families `SHOWDOWN_AUTH_*`,
    `SHOWDOWN_DATASET_*`): `SHOWDOWN_TURN_TRACE`, `SHOWDOWN_DECISION_DIFF`, `SHOWDOWN_ROOM_RAW_DUMP`,
    `SHOWDOWN_EVAL_SEED_LOG`, `SHOWDOWN_USERNAME`, `SHOWDOWN_PASSWORD`, `SHOWDOWN_SERVER`,
    `SHOWDOWN_RERANKER_SHADOW_LOG`, `SHOWDOWN_BATTLE_SEED_BASE`, `SHOWDOWN_CALC_BACKEND` **(with caveat)**.
    - **`SHOWDOWN_CALC_BACKEND` caveat (documented in code):** oneshot/persistent both call the same
      `@smogon/calc` Node script → numerically identical, so non-behavioral **for current code**. **If a
      future Python/approximate backend changes scoring, this MUST move to `BEHAVIOR_AFFECTING`.**
  - **`behavior_env() -> dict`** = `{k: v for k, v in os.environ.items() if k.startswith("SHOWDOWN_") and
    not _denied(k)}` — **fail-closed**: any set `SHOWDOWN_*` not on the denylist is INCLUDED (unknown/new →
    included → non-pairable, safe). `_denied(k)` matches exact denylist names + the prefix families.
- [ ] **Step 2 — drift test (`tests/test_config_env.py`):** statically scan `battle/` + `engine/`
  source for `SHOWDOWN_*` reads (`os.environ[...]` / `os.environ.get(...)` / `os.getenv(...)`); **assert
  every read name is classified** — i.e. present in `BEHAVIOR_AFFECTING` **or** matched by `NON_BEHAVIORAL`
  (exact or prefix). A **new unclassified `SHOWDOWN_*` read → the drift test FAILS**, forcing an explicit
  classification decision (never a silent omission). Plus: each `BEHAVIOR_AFFECTING` var, when set, appears
  in `behavior_env()`; each `NON_BEHAVIORAL` var, when set, does NOT.
- [ ] **Step 3 — failing test (`make_config_hash`):** `make_config_hash(manifest: dict)` order-independent
  + stable; two manifests differing only in a behavior-affecting env var (e.g. `SHOWDOWN_MUST_REACT_LAMBDA`,
  `SHOWDOWN_REAL_SPREADS`) → **different** hashes; identical manifests → identical hash; a denylisted var
  changing (e.g. `SHOWDOWN_CALC_BACKEND`) does **not** change the hash.
- [ ] **Step 4 — run, expect fail.**
- [ ] **Step 5 — implement:** `make_config_hash(manifest)` = `sha1(canonical(manifest))[:16]`; the runner
  builds `manifest = {"agent": hero_agent, "format_id", "priors_hash": <content-hash of protect_priors
  file>, "spreads_hash": <content-hash of default_spreads file>, "env": behavior_env(),
  "model_hash"/"model_manifest_hash": present only when the reranker is enabled}`. Remove the old 2-arg
  form; update T2's row assembly to pass the manifest.
- [ ] **Step 6 — run, expect pass.**
- [ ] **Step 7 — commit** `feat(2b-3.5 T3f): fail-closed config_hash env classification + drift test`.

## Task 2 — `seed_base` per row

**Files:** Modify `eval/result_jsonl.py` (schema), `cli.run_schedule`; Test `tests/test_result_jsonl.py`.

- [ ] Add `seed_base` to `REQUIRED_FIELDS`. `run_schedule` writes `seed_base = SHOWDOWN_BATTLE_SEED_BASE`
  (already required for `--result-out`). Test: a valid row includes `seed_base`; missing → `ResultRowError`.
  (Pairing precondition per review §2 — the validator checks it explicitly, not re-derived from `seed`.)
- [ ] **Commit** `feat(2b-3.5 T3f): seed_base row field`.

## Task 3 — `run_id` + run manifest

**Files:** Create `eval/run_manifest.py`; Modify `eval/result_jsonl.py` (row `run_id`), `cli.run_schedule`;
Tests `tests/test_run_manifest.py`.

- [ ] **run_id** = `sha1(canonical([seed_base, schedule_hash, config_hash, start_ts]))[:16]`; add
  `run_id` to `REQUIRED_FIELDS`; every row in one run carries the **same** `run_id`.
- [ ] **Run manifest** (`<result-out>.manifest.json`, written once at run start/end): `{run_id, seed_base,
  schedule_hash, panel_hash, config_hash, pythonhashseed (from env), timestamp, cli_invocation (argv),
  showdown_commit (pinned in config), server_patch_hash (content-hash of
  tools/eval/patches/pokemon-showdown-seeded-battle.patch), git_sha, dirty}`. This closes the
  server/patch-provenance gap (review §1, P5b).
- [ ] Tests: manifest builds from known inputs; `run_id` is stable + shared across rows; a `showdown_commit`
  constant lives in config (`config/eval/provenance.yaml` or similar), not hard-coded in code.
- [ ] **Commit** `feat(2b-3.5 T3f): run_id + run manifest (server/patch provenance)`.

## Task 4 — `panel_split: dev | heldout` per row

**Files:** Modify `eval/schedule.py` (`ScheduleRow.panel_split`), `eval/panel_schedule.py` (stamp it),
`eval/result_jsonl.py` (nullable field), `cli.run_schedule`; Tests `tests/test_panel_schedule.py`.

- [ ] `generate_dev_schedule` stamps `panel_split="dev"`, `generate_heldout_schedule` stamps
  `panel_split="heldout"` on each row; `write_schedule_yaml`/`load_schedule` round-trip it; legacy
  schedules → `None`. `run_schedule` writes it into each row (`panel_split` nullable in `result_jsonl`).
  Test: a dev schedule's rows carry `"dev"`, held-out `"heldout"`; a legacy schedule → `null`.
  (Review §1/§6 — stamped at write time so T6 leakage checks don't re-derive against a mutated panel.)
- [ ] **Commit** `feat(2b-3.5 T3f): panel_split stamped on generated schedules + rows`.

## Task 5 — `end_reason: normal | timeout | forfeit | crash` per row

**Files:** Modify `eval/battle_parse.py` (detect the end cause from `room_raw`), `client/gauntlet.py`
(pass it through `_battle_result_record`), `eval/result_jsonl.py` (field); Tests `tests/test_battle_parse.py`.

- [ ] `parse_battle_result` returns `end_reason` (best-effort from `room_raw`): `normal` (a normal
  `|win|`/`|tie`), `timeout` (win attributable to a timer/inactivity), `forfeit` (a forfeit message),
  `crash` (battle error frame); default `normal`. Add `end_reason` to `REQUIRED_FIELDS` (default `"normal"`
  when a result arrived). Test: synthetic frames for each case classify correctly; unknown → `normal`.
  (Review §1/§5 — a timeout-forced loss must be distinguishable from a real loss; a non-`normal` row is a
  T5 SAFETY-FAIL input.)
- [ ] **Commit** `feat(2b-3.5 T3f): end_reason classification (normal/timeout/forfeit/crash)`.

## Task 6 — Pin the latency budget

**Files:** Create/extend `config/eval/provenance.yaml` (or `config/eval/gates.yaml`); Test.

- [ ] Pin `decision_latency_p95_budget_ms: 1000` as a config constant (current baseline ~200 ms), with a
  loader + a test that it reads back. (T3f only *pins* the number; T5 enforces it as a gate.)
- [ ] **Commit** `feat(2b-3.5 T3f): pin decision-latency p95 budget in config`.

## Task 7 — Tiny provenance smoke + report

**Files:** Report `reports/2026-07-02-2b35-T3f-run-provenance-smoke.md`.

- [ ] Regenerate a tiny dev schedule (panel-driven), run via `gauntlet --schedule … --result-out …`
  (fresh seeded server, `PYTHONHASHSEED=0`); confirm every row carries **`seed_base`, `run_id`,
  `panel_split="dev"`, `end_reason="normal"`, the effective `config_hash`** (+ T3e's `dirty`/team hashes),
  the **run manifest** was written with server/patch provenance, and `config_hash` is constant across the
  run. 0 invalid / 0 crash; seed-log alignment OK.
- [ ] **Report + commit** `docs(2b-3.5 T3f): run-provenance smoke report`.

**Phase T3f gate:** rows are pairable + self-describing (`seed_base`, `run_id`, `panel_split`,
`end_reason`, effective `config_hash`); a run manifest with server/patch provenance is emitted; the latency
budget is a pinned number. This satisfies the review's "schema additions landed in T2's writer" and
"config_hash redefined … latency budget pinned" preconditions. Unblocks **T4** (real smoke), then **T5**.

---

## Out of scope (belongs to T4/T5/T6, not T3f)
No Wilson/McNemar, no report generator, no safety-gate/verdict logic, no pairing validator, no held-out
ledger/baseline manifest, no override. `battle/` decision logic untouched.

**Carried-forward design decisions (recorded for T5, not implemented here):**
- The T5 report generator **independently re-verifies** seed-log alignment + panel/team hashes — it audits
  its inputs, never trusts rows (review §5/preconditions).
- Verdict thresholds (`n_discordant` 6 / 10, losing-cell rule) become **T5 spec constants**.
- Exact binomial McNemar (not chi-square) — a **T5** decision.

## Self-review (writing-plans)
- Coverage of review §1 "missing": `seed_base` (T2), `run_id`+manifest (T3), `panel_split` (T4),
  `end_reason` (T5), effective `config_hash` (T1); `battle_id` docs already in T3e P4; latency budget
  pinned (T6). ✓
- Additive + truthful: `schedule_hash`/`battle_id` unchanged; legacy → null/default; `config_hash` is
  behavior-covering via a **fail-closed** env classification (include every `SHOWDOWN_*` except a documented
  non-behavioral denylist) + a **drift test** that fails on any unclassified `SHOWDOWN_*` read in
  `battle/`/`engine/` — a forgotten behavior flag can't silently produce same-hash/different-behavior; an
  over-included flag only makes runs non-pairable (safe). ✓
- Scope discipline: statistics/gates/ledger/baseline all explicitly deferred to T4/T5/T6; the review is a
  non-binding artifact and only its §1 schema-readiness findings are promoted here. ✓
- No placeholders (the one config constant, `showdown_commit`, is pinned in config with a loader test).
