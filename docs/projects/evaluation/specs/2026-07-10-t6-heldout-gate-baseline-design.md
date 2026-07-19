# 2b-3.5 T6 — Held-out Gate Structure + Heuristic Baseline — Design

> Implements the T6 half of `docs/projects/evaluation/reviews/2026-07-01-fable-t5-t6-eval-architecture-
> review.md` (§6 held-out discipline, §7 baseline freezing, §9 preconditions). User decisions
> 2026-07-10: the baseline HELD-OUT run is executed as part of this slice (first ledger entry);
> panel stays v001 (2 held-out teams — a future v002 bump resets the access budget by design).

**Goal:** Every held-out access is visible, auditable, and budgeted; the heuristic baseline is
frozen as a verified, reproduction-checked manifest; a baseline held-out run is recorded. After
T6, the only missing piece for a 2b-4 decision is the candidate itself.

**Honesty clause (spec-mandated, from the review):** a solo dev with root cannot be technically
stopped from touching held-out teams. T6's goal is that every access leaves a committed, append-
only trace — discipline made auditable, not enforced.

## 1. `eval/heldout_ledger.py` + `config/eval/heldout_ledger.jsonl`

- **Committed, append-only JSONL.** Two entry kinds:
  - `{"kind": "schedule", "date", "purpose", "panel_hash", "schedule_hash", "git_sha",
    "justification": null|str}` — appended when a held-out schedule is generated.
  - `{"kind": "run", "date", "purpose", "panel_hash", "schedule_hash", "config_hash",
    "git_sha", "result_sha256", "justification": null|str}` — appended after a held-out run.
- API: `append_entry(path, entry)` (validates shape, opens append-mode, LF, utf-8);
  `read_ledger(path) -> list[dict]` (fail-fast on malformed lines);
  `check_access(entries, config_hash, *, justification=None)` — raises `AccessBudgetError` if a
  prior `run` entry exists for the same `config_hash` and no justification is given (**budget:
  one held-out gate attempt per config_hash lineage**; a justification entry or a panel version
  bump resets it).
- **Choke-point wiring:** `generate_heldout_schedule(...)` gains `ledger_path=None` +
  `purpose=None`; when `ledger_path` is set, a `schedule` entry is appended automatically
  (git_sha via `learning/provenance.git_sha_and_dirty`). Default `None` keeps the function pure
  (existing tests unchanged). `confirm_heldout=True` stays required regardless.
- **Enforcement tests:**
  - Append-only via git history: a test replays `git log --follow -p -- config/eval/
    heldout_ledger.jsonl` and asserts every commit only ADDS trailing lines (no edits/deletions
    of prior lines). Skips cleanly if git is unavailable.
  - Leakage: no held-out `team_hash`/`team_path`/`team_id` (panel v001: balance, tailwind)
    appears in any committed dev schedule under `config/eval/schedules/` (drift test).
  - Budget: second `run` entry for the same config_hash without justification → AccessBudgetError.

## 2. `eval/baseline.py` + `config/eval/baselines/heuristic-v1.json`

- **Manifest content** (built once from the T4-rerun reference run, then immutable):
  `{"baseline_id": "heuristic-v1", "config_id": "heuristic", "config_hash": "aeafb78a5beea9cd",
  "git_sha": "e2d6f34d…", "panel_version": "v001", "panel_hash": "760c1e5935fe0474",
  "dev_schedule_hash": "a7f000867fdfbde0", "heldout_schedule_hash": <pinned in this slice>,
  "hero_team_hash": "5aef213f351a6627", "opp_team_hashes": {<all 5 dev+heldout by team_id>},
  "showdown_commit": "f8ac1400…", "server_patch_hash": "bb973ec76d83cddb",
  "seed_base": "t4rerun2026", "pythonhashseed": "0",
  "reference_jsonl": "data/eval/t4/rerun/t4rerun-run1.jsonl", "reference_sha256": <from
  data/eval/t4/rerun/sha256.txt>, "heldout_reference_jsonl": <this slice's run>,
  "heldout_reference_sha256": <...>, "heldout_seed_base": <this slice's fresh base>,
  "dev_schedule_path": "config/eval/schedules/t4_smoke_v001.yaml",
  "heldout_schedule_path": "config/eval/schedules/t6_heldout_v001.yaml"}`.
  **(Amended 2026-07-10 during Task 3: the `*_schedule_path` fields are required alongside the
  hashes — a hash alone cannot be loaded for verification. Also clarified: `verify_baseline`
  checks only the team_ids listed in the manifest; full-panel coverage is transitively enforced
  by the `panel_hash` re-hash check, and a panel bump correctly fails old baselines as drift.)**
- API: `load_baseline(path)`; `verify_baseline(baseline, *, repo_root) -> list[check results]` —
  re-checks EVERY hash against the working tree: panel re-hash + team content hashes,
  provenance.yaml showdown_commit, patch file hash, schedule hashes via `load_schedule`,
  reference JSONL sha256s. Any mismatch → `BaselineDriftError` ("baseline drift → refuse").
- **Reproduction spot-check:** `verify_winner_sequence(reference_rows, fresh_rows)` compares the
  winner sequence (+ seeds) of a fresh prefix-schedule run against reference rows 0-9. The fresh
  run itself is operational (reuses `config/eval/schedules/t4_smoke_v001_prefix.yaml` +
  `seed_base t4rerun2026` — byte-reproducibility proven in T4b). A baseline that cannot be
  re-reproduced is a label, not a baseline.
- **Immutability test:** same git-history mechanism as the ledger, stricter — after its first
  commit the file content never changes (a change requires a NEW versioned file, e.g.
  `heuristic-v2.json`).

## 3. Held-out schedule + baseline held-out run (operational)

- Schedule: `generate_heldout_schedule(panel_v001, confirm_heldout=True, policies=<all 5>,
  seeds_per_cell=T4_SEEDS_PER_CELL, ledger_path=..., purpose="baseline-heldout-v1")` → 2 teams ×
  (5+5+3+2+2) = **34 rows**, committed as `config/eval/schedules/t6_heldout_v001.yaml`
  (+ drift test vs generator, analogous to `test_t4_matrix.py`). Note: `seeds_per_cell` mapping +
  held-out generation compose (T4 Task 1 built the mapping into `_build`, shared by both
  generators — verify with a test).
- Run: fresh seeded server, **fresh seed base `t6heldout2026`**, PYTHONHASHSEED=0, persistent
  calc, outputs OUTSIDE the repo during the run (dirty gate), then committed under
  `data/eval/t6/` (results + manifest + seedlog + telemetry + gates output + gzipped room logs +
  sha256 pins — same pattern as `data/eval/t4/rerun/`).
- Readout: `eval-report` single-run gate mode → REQUIRED `SINGLE-RUN SAFETY-PASS` **with the
  HELD-OUT banner present** (all rows `panel_split="heldout"`). A `run` ledger entry is appended
  with the result sha256. The report is committed; **per-cell numbers are recorded, never
  discussed or acted upon** (they exist solely as the future 2b-4 comparison substrate).
- Reproduction evidence for the held-out run itself: a 10-row prefix is NOT defined for this
  schedule; instead run the full 34-game schedule twice (≈2×7 min) and require 34/34
  winner/seed/turns identity (cheap at this size, stronger than a prefix).
- **Budget interaction (deliberate):** the reproduction re-run appends a second `run` entry for
  the same config_hash and therefore REQUIRES an explicit justification
  (`"reproduction re-run of baseline-heldout-v1, same session"`) — exercising the budget
  mechanism end-to-end on day one instead of special-casing it. `check_access` is called before
  BOTH runs; the second call must fail without the justification and pass with it (that pair of
  assertions is part of R7).

## 4. Requirements (testable)

- **R1** Ledger API round-trips; malformed line → error; append is literally file-append.
- **R2** `check_access`: first access OK; second same-config_hash `run` without justification →
  `AccessBudgetError`; with justification → OK and the justification is stored.
- **R3** Git-history tests: ledger append-only; baseline manifest immutable after first commit.
- **R4** Leakage drift test: held-out identifiers absent from all committed dev schedules.
- **R5** `verify_baseline` passes on the committed manifest against the current tree; each
  tampered variant (panel edit, patch edit, schedule swap, reference sha mismatch) →
  `BaselineDriftError` (tamper copies under tmp_path).
- **R6** Winner-sequence spot-check helper: identical rows pass; a flipped winner or swapped
  order fails.
- **R7 (operational acceptance)** Held-out run: 34/34 rows, `SINGLE-RUN SAFETY-PASS`, held-out
  banner, double-run 34/34 identity, ledger `schedule` + `run` entries present, baseline
  reproduction spot-check (dev prefix, winners match reference) executed and green.
- **R8** Full suite green (757 baseline); stdlib-only; `battle/` untouched.

## 5. Out of scope

The 2b-4 candidate comparison and its gate-runner CLI (refusal helpers are built, the runner
that orchestrates candidate-vs-baseline comes with 2b-4); panel growth to ≥4 held-out teams
(explicitly deferred — a v002 bump later resets the access budget by design); any tuning
discussion of held-out numbers; changes to report/pairing/stats beyond consuming them.

## 6. References

Review artifact §6 (ledger, budget, refusals, banner), §7 (manifest, immutability,
reproduction), §9 (T6 preconditions for 2b-4). T5 spec for report semantics. Baseline facts:
`reports/2026-07-10-2b35-T4-rerun.md` + `data/eval/t4/rerun/sha256.txt`.
