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

## Task 1 — Effective `config_hash` (behavior-covering)

**Problem (review §1/§10):** `make_config_hash(config_id, format_id)` — two behaviorally different bots
share it → a config can be paired against itself (`n_discordant≈0` reads as "perfectly safe").

**Files:** Modify `eval/result_jsonl.py` (`make_config_hash`); Modify `cli.run_schedule`; Test
`tests/test_result_jsonl.py`.

- [ ] **Step 1 — failing test:** `make_config_hash(manifest: dict)` is order-independent + stable; two
  manifests differing only in a **behavior-affecting env flag** (e.g. `SHOWDOWN_REAL_SPREADS`,
  `SHOWDOWN_RERANKER_SHADOW`, reranker model/manifest paths) produce **different** hashes; identical
  manifests → identical hash.
- [ ] **Step 2 — run, expect fail.**
- [ ] **Step 3 — implement:** `make_config_hash(manifest)` = `sha1(canonical(manifest))[:16]` where the
  runner builds the manifest = `{"agent": hero_agent, "format_id", "priors_hash":
  <content-hash of the protect_priors file>, "spreads_hash": <content-hash of the default_spreads file>,
  "env": {behavior-affecting flags only}, "model_hash"/"model_manifest_hash": present only when the
  reranker is enabled}`. Keep the old 2-arg form deprecated/removed; update T2's row assembly to pass the
  manifest. (Non-behavioral env like `SHOWDOWN_CALC_BACKEND`/`SHOWDOWN_EVAL_SEED_LOG` are excluded — a
  documented allowlist.)
- [ ] **Step 4 — run, expect pass.**
- [ ] **Step 5 — commit** `feat(2b-3.5 T3f): effective config_hash over behavior manifest`.

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
- Additive + truthful: `schedule_hash`/`battle_id` unchanged; legacy → null/default; behavior-covering
  `config_hash` proven by an env-flag test. ✓
- Scope discipline: statistics/gates/ledger/baseline all explicitly deferred to T4/T5/T6; the review is a
  non-binding artifact and only its §1 schema-readiness findings are promoted here. ✓
- No placeholders (the one config constant, `showdown_commit`, is pinned in config with a loader test).
