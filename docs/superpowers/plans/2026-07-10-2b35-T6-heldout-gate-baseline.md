# 2b-3.5 T6 — Held-out Gate Structure + Heuristic Baseline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. **Git owner:
> Bau-Claude.** Steps use `- [ ]`. Implements the approved spec
> `docs/superpowers/specs/2026-07-10-t6-heldout-gate-baseline-design.md` (incl. the budget-
> interaction amendment); rationale in the review artifact §6/§7. The spec is the authority.

**Goal:** Append-only held-out ledger with access budget + refusal checks; frozen verified
baseline manifest; the first (baseline) held-out run recorded — 34 games on balance+tailwind,
double-run reproduction, readout via the T5 `eval-report` CLI.

**Architecture:** two new modules (`eval/heldout_ledger.py`, `eval/baseline.py`), a `ledger_path`
hook on `generate_heldout_schedule`, one new committed schedule + the ledger + the baseline
manifest as data files, and `data/eval/t6/` artifacts. `eval-report` (T5) is the gate checker —
no throwaway verify scripts for gates anymore.

**Suite baseline:** 757 passed. Branch: create `feat/slice-2b35-t6-heldout-baseline` off `main`.

---

### Task 1: `eval/heldout_ledger.py` (ledger API + budget + append-only test)

**Files:**
- Create: `showdown_bot/src/showdown_bot/eval/heldout_ledger.py`
- Test: `showdown_bot/tests/test_heldout_ledger.py`

- [ ] **Step 1: Failing tests.** Entry shapes per spec §1 (`kind: schedule|run`, required fields
  per kind, `justification: None|str`). Cover:

```python
def test_append_and_read_roundtrip(tmp_path): ...      # two entries, both kinds, order preserved
def test_append_is_literal_file_append(tmp_path): ...  # existing bytes untouched (read back prefix)
def test_malformed_line_fails_fast(tmp_path): ...      # hand-write a broken line -> LedgerError
def test_missing_required_field_rejected(tmp_path): ...# append_entry validates per kind
def test_check_access_first_time_ok(): ...             # no prior run entry for cfg -> None
def test_check_access_second_run_same_config_refused(): ...   # AccessBudgetError
def test_check_access_with_justification_ok(): ...     # passes; justification stored on append
def test_check_access_schedule_entries_dont_consume_budget(): ...  # only kind=="run" counts
def test_ledger_git_history_append_only(): ...
    # replay `git log --follow -p -- config/eval/heldout_ledger.jsonl` from repo root;
    # every hunk may only add lines at EOF (no '-' lines except header noise, no insertions
    # before existing content). pytest.skip if the file has no git history yet.
```

- [ ] **Step 2: FAIL run. Step 3: Implement** (`LedgerError(ValueError)`,
  `AccessBudgetError(LedgerError)`; `append_entry(path, entry)` utf-8/LF append-mode;
  `read_ledger(path)`; `check_access(entries, config_hash, *, justification=None)` — refuse iff
  any prior `run` entry has the same config_hash and justification is None). Docstrings carry the
  §6 rationale (budget targets iterate-until-heldout-passes overfitting).
- [ ] **Step 4: Green + full suite (757+9). Step 5: Commit**
  `feat(2b-3.5 T6): held-out ledger (append-only, access budget)`

### Task 2: Choke-point wiring + leakage drift test

**Files:**
- Modify: `showdown_bot/src/showdown_bot/eval/panel_schedule.py` (`generate_heldout_schedule`)
- Test: `showdown_bot/tests/test_panel_schedule.py` (wiring) + `showdown_bot/tests/test_heldout_leakage.py` (drift)

- [ ] **Step 1: Failing tests.**
  - Wiring: `generate_heldout_schedule(..., ledger_path=str(tmp/"ledger.jsonl"),
    purpose="test")` appends exactly one valid `schedule` entry (panel_hash + schedule_hash +
    git_sha populated); `ledger_path=None` (default) appends nothing and behaves exactly as
    before (existing tests must stay green untouched).
  - Drift (`test_heldout_leakage.py`): for every committed `config/eval/schedules/*.yaml`, load
    it; if ANY row has `panel_split == "dev"` or `panel_split is None` → assert no held-out
    identifier appears anywhere in the file (team_ids `balance`/`tailwind`, their team_paths,
    and their content hashes — read them from `config/eval/panels/panel_v001.yaml` via
    `load_panel`, don't hardcode). Schedules that are entirely heldout-labeled are exempt (the
    T6 schedule arrives in Task 4).
- [ ] **Step 2-4: FAIL → implement → green + full suite.** Implementation: after building the
  schedule, if `ledger_path` is set, import `heldout_ledger` + `git_sha_and_dirty` and append
  (purpose required when ledger_path given — `PanelScheduleError` if missing).
- [ ] **Step 5: Commit** `feat(2b-3.5 T6): ledger hook on heldout generation + leakage drift test`

### Task 3: `eval/baseline.py` (manifest loader, drift verification, winner-sequence check)

**Files:**
- Create: `showdown_bot/src/showdown_bot/eval/baseline.py`
- Test: `showdown_bot/tests/test_baseline.py`

- [ ] **Step 1: Failing tests** — build a synthetic-but-real-shaped manifest in tmp_path pointing
  at COPIES of real repo files (panel, schedules, patch, provenance.yaml, a small reference
  jsonl), then:
  - `load_baseline` round-trip + missing-field rejection.
  - `verify_baseline(manifest, repo_root=...)` green on the untampered copy set.
  - Tamper variants (each → `BaselineDriftError` naming the failed check): panel file edited;
    patch file edited; schedule swapped (hash mismatch); reference jsonl byte flipped (sha
    mismatch); provenance.yaml showdown_commit changed.
  - `verify_winner_sequence(reference_rows, fresh_rows)`: identical → ok; flipped winner →
    error; reordered → error; length mismatch → error (compare winner AND seed per index).
  - `test_baseline_manifest_git_immutability`: replay git history of
    `config/eval/baselines/*.json`; after first appearance content never changes;
    pytest.skip while no baseline file is committed yet.
- [ ] **Step 2-4: FAIL → implement → green + full suite.** Checks in `verify_baseline` (each a
  named entry in the returned results list): panel re-hash == manifest.panel_hash; every
  team_id's content hash == manifest.opp_team_hashes + hero; `load_schedule(dev).schedule_hash`
  == dev_schedule_hash (same for heldout when present); patch sha1[:16] == server_patch_hash;
  provenance.yaml showdown_commit == manifest's; sha256(reference_jsonl) == reference_sha256
  (same for heldout reference when present). Fail-closed: any check exception → drift error.
- [ ] **Step 5: Commit** `feat(2b-3.5 T6): baseline manifest verification (drift-refusing)`

### Task 4: Held-out schedule + generator pin

**Files:**
- Create: `showdown_bot/src/showdown_bot/eval/t6_heldout.py` + `config/eval/schedules/t6_heldout_v001.yaml`
- Test: `showdown_bot/tests/test_t6_heldout.py`

- [ ] Mirror the `t4_matrix.py` pattern: `generate_t6_heldout_schedule(panel, *, teams_root=".",
  ledger_path=None)` = `generate_heldout_schedule(panel, confirm_heldout=True,
  policies=T4_POLICIES, seeds_per_cell=T4_SEEDS_PER_CELL, teams_root=..., ledger_path=...,
  purpose="baseline-heldout-v1")` (import the pinned weights from `eval/t4_matrix` — same
  matrix, held-out teams). Failing test first: 34 rows (2 teams × 17), Counter per policy
  {10,10,6,4,4}, all `panel_split=="heldout"`, reproducible, committed YAML == generator
  (drift test à la `test_t4_matrix.py`), and the generation call with a tmp ledger appends the
  `schedule` entry.
- [ ] Generate the committed YAML **with the REAL ledger** (`config/eval/heldout_ledger.jsonl`
  is born here — first entry, kind=schedule, purpose="baseline-heldout-v1"). Record the printed
  schedule_hash for Task 5/6.
- [ ] Green + full suite. **Commit** (module + test + schedule YAML + the new ledger file):
  `feat(2b-3.5 T6): held-out baseline schedule + first ledger entry`

### Task 5: The baseline held-out run (operational; Opus; R7)

No source changes; no battle retries; outputs under `C:/tmp/t6/` during runs (dirty gate).
Known ops facts: fresh seeded server per run; `MSYS_NO_PATHCONV=1` with `C:/...` paths (not with
`~` paths); background runs + controller nudges; German-locale netstat prints "ABHÖREN".

- [ ] **Preconditions:** clean tree; server clone HEAD == provenance.yaml showdown_commit;
  port 8000 free. `python -c` call `check_access(read_ledger(...), "aeafb78a5beea9cd")` → OK
  (only the schedule entry exists — assert it does NOT raise; record output).
- [ ] **Run 1:** server (`SHOWDOWN_BATTLE_SEED_BASE=t6heldout2026`,
  `SHOWDOWN_EVAL_SEED_LOG=C:/tmp/t6/run1_seeds.jsonl`) + client from `showdown_bot/`
  (`PYTHONHASHSEED=0`, persistent calc, telemetry + room dump on, schedule
  `../config/eval/schedules/t6_heldout_v001.yaml`, `--result-out C:/tmp/t6/run1_results.jsonl`).
  Expect 34 rows + alignment OK + zero warnings. Kill server.
- [ ] **Gate readout via T5 (no throwaway checker):** from `showdown_bot/`:
  `python -m showdown_bot.cli eval-report --run-a C:/tmp/t6/run1_results.jsonl --seedlog-a
  C:/tmp/t6/run1_seeds.jsonl --schedule ../config/eval/schedules/t6_heldout_v001.yaml --panel
  ../config/eval/panels/panel_v001.yaml --out C:/tmp/t6/report_run1` → exit 0, md first line
  `# VERDICT: SINGLE-RUN SAFETY-PASS`, **HELD-OUT banner present** (grep it). Any FAIL →
  BLOCKED with evidence.
- [ ] **Ledger run entry #1:** append kind=run (purpose baseline-heldout-v1, config_hash from
  the run manifest, result_sha256 of run1_results.jsonl, git_sha) via a `python -c` using the
  ledger API. Do NOT commit yet (Task 6 commits everything together — the ledger file will show
  entries 1-3 in one commit; append-only history starts from there).
  **AMENDED at dispatch (controller): appending to the TRACKED ledger between runs would dirty
  the tree and flip run 2's dirty gate. Task 5 therefore writes both pending run entries to
  `C:/tmp/t6/pending_ledger_entries.jsonl` (same shape) and runs the budget exercise against a
  tmp COPY of the ledger with entry #1 applied; Task 6 appends the pending entries to the real
  ledger and commits. The tracked ledger stays untouched during the runs.**
- [ ] **Budget exercise (R7, spec amendment):** `check_access(entries, <config_hash>)` → MUST
  raise AccessBudgetError now; `check_access(..., justification="reproduction re-run of
  baseline-heldout-v1, same session")` → MUST pass. Record both outputs verbatim.
- [ ] **Run 2 (reproduction):** fresh server, same base, `run2_*` outputs → 34 rows. Compare
  ALL 34 (room logs byte-identity via `compare_battle_logs` + winner/seed/turns per row —
  adapt the T4b scratchpad compare script; save to `C:/tmp/t6/repro_run2.txt`). REQUIRED 34/34.
  Ledger run entry #2 WITH the justification string.
- [ ] **Baseline dev reproduction spot-check (§2):** fresh server,
  `SHOWDOWN_BATTLE_SEED_BASE=t4rerun2026`, run `../config/eval/schedules/
  t4_smoke_v001_prefix.yaml` → compare winner+seed sequence vs committed
  `data/eval/t4/rerun/t4rerun-prefix.jsonl` via `verify_winner_sequence` (Task 3 helper) —
  REQUIRED: match. Save output `C:/tmp/t6/baseline_spotcheck.txt`.
- [ ] Report back (gates, both ledger checks, 34/34 verdict, spot-check, durations, anomalies,
  cleanup: servers dead, tree clean, artifacts intact).

### Task 6: Baseline manifest + artifacts + report + closeout

**Files:**
- Create: `config/eval/baselines/heuristic-v1.json`; `data/eval/t6/**`;
  `reports/<run-date>-2b35-T6-heldout-baseline.md`
- Modify: `config/eval/heldout_ledger.jsonl` (the 3 entries from Tasks 4-5, committed here),
  `showdown_bot/tests/test_baseline.py` (+1 real-manifest test)

- [ ] Build `heuristic-v1.json` per spec §2 with the now-known values (heldout schedule hash,
  heldout run sha256, t6heldout2026); run `verify_baseline` against the tree → must pass; add
  the real-manifest test (`verify_baseline(load_baseline(<real path>), repo_root)` green).
- [ ] Copy artifacts → `data/eval/t6/` (both runs' jsonl+manifest+seedlog+telemetry, eval-report
  md+json for run 1, repro_run2.txt, baseline_spotcheck.txt, gzipped room logs both runs,
  sha256 pins). `.gitattributes`: extend for `data/eval/t6/**` (`-text` + room_raw `binary`).
- [ ] Report (house style): structure documentation (ledger/budget/refusals/manifest), the R7
  evidence (both check_access outputs verbatim, 34/34, spot-check), HELD-OUT banner quoted,
  **per-cell numbers present in the committed eval-report artifact but NOT restated or discussed
  in the T6 report body** (one line: "recorded, not discussed — see the banner").
- [ ] Full suite green; commit everything:
  `docs(2b-3.5 T6): baseline manifest + first held-out run recorded + ledger active`
- [ ] Closeout scope check (`git diff main --stat`) + report back for controller review/merge.

---

## Out of scope
2b-4 candidate comparison + gate-runner CLI; panel growth; any discussion of held-out numbers;
changes to report/pairing/stats/battle.

## Self-review (writing-plans)
- Spec coverage: R1/R2→T1, R3→T1+T3 (git-history tests, skip-until-committed) — the skips
  self-arm once Task 6 commits the files; R4→T2; R5→T3+T6 (synthetic then real); R6→T3;
  R7→T5 (both check_access assertions + 34/34 + spot-check + banner); R8→every task. Budget
  amendment honored (justification on run 2). ✓
- Placeholders: operational values marked as recorded-at-runtime (schedule hash, shas) —
  generation-time by nature; everything else concrete. eval-report replaces throwaway gate
  checkers (first production use of T5). ✓
- Consistency: seeds_per_cell mapping reuse verified by T4 Task 1's shared `_build`; purpose
  string identical across schedule + run entries; config_hash for check_access comes from the
  run manifest (aeafb78a5beea9cd expected — same config as T4 rerun since env/agent unchanged,
  but READ it from the manifest, don't assume). ✓
