# 2b-3.5 T6 — Held-out Gate Structure + Heuristic Baseline (run 2026-07-10)

## VERDICT: T6 COMPLETE

The held-out gate machinery is built, tested, and **activated**: an append-only access ledger
with a per-config budget and refusal helpers, a frozen + drift-verified + immutable heuristic
baseline manifest, and the **first held-out run recorded** — 34/34 games, `SINGLE-RUN
SAFETY-PASS` with the held-out banner, double-run 34/34 byte-identity, dev reproduction
spot-check 10/10. Full suite **799 passed, 0 skipped** post-commit (both git-history enforcement
tests now armed and green).

**With T6 complete, all of 2b-3.5 (T0–T6) is done.** The only missing piece for a 2b-4 decision
is the candidate itself: the gate — pinned baseline, held-out schedule, ledger/budget, refusal
helpers, and the T5 `eval-report` readout — is ready and waiting for a config to compare.

Scope note: the held-out per-cell numbers exist **solely as the future 2b-4 comparison
substrate**. They are recorded in the committed eval-report artifact and are **never discussed or
acted upon** in this report (see §6).

---

## 1. Structure delivered (spec §1–§2)

| Piece | File(s) | State |
|---|---|---|
| Access ledger (append-only JSONL, one write choke-point) | `config/eval/heldout_ledger.jsonl` + `eval/heldout_ledger.py` | **Active — 3 entries** (1 `schedule` + 2 `run`) |
| Access budget (`check_access`) | `eval/heldout_ledger.py` | one gate attempt per `config_hash` lineage; second `run` refused unless justified |
| Choke-point wiring | `eval/panel_schedule.py::generate_heldout_schedule` (`ledger_path`/`purpose` hook) | ledger `schedule` entry auto-appended at generation |
| Baseline manifest (frozen, verified) | `config/eval/baselines/heuristic-v1.json` + `eval/baseline.py` | **`verify_baseline` green — 9/9 checks** |
| Refusal helpers | `verify_baseline` (drift → `BaselineDriftError`), `verify_winner_sequence` (→ `WinnerSequenceError`) | tested (synthetic tamper variants + real manifest) |
| Enforcement tests (git history) | `test_heldout_ledger.py` (append-only), `test_baseline.py` (immutable) | **armed + green** after this commit |
| Leakage drift test | `test_heldout_leakage.py` | no held-out id/path/hash in any committed dev schedule |

**Ledger contents (`config/eval/heldout_ledger.jsonl`, in order):**

1. `schedule` · purpose `baseline-heldout-v1` · schedule_hash `3076a71aa6841c8c` · git_sha `c65634b6…` · justification `null` (born in Task 4 when the held-out schedule was generated)
2. `run` · config_hash `aeafb78a5beea9cd` · result_sha256 `ab6d6227…` · git_sha `564a06f7…` · justification `null` (baseline held-out run, Run 1)
3. `run` · config_hash `aeafb78a5beea9cd` · result_sha256 `f25d0ba8…` · git_sha `564a06f7…` · justification `"reproduction re-run of baseline-heldout-v1, same session"` (Run 2)

**Append-only enforcement:** this commit is the ledger's **second** commit; it appends entries 2–3
at EOF and edits nothing above. `test_ledger_git_history_append_only` replays
`git log --follow -p` and passes. The baseline manifest is committed here for the **first** time;
`test_baseline_manifest_git_immutability` asserts it is never touched by more than one commit.

**Honesty clause (spec-mandated):** a solo dev with root cannot be *technically* stopped from
touching held-out teams. T6's goal is that every access leaves a committed, append-only, auditable
trace — discipline made visible, not enforced.

## 2. `verify_baseline` — 9/9 checks green against the working tree

`verify_baseline(load_baseline("config/eval/baselines/heuristic-v1.json"), repo_root=".")`
re-derives every hash from the **current** tree and refuses on any single mismatch:

| # | Check | Measured (== manifest) |
|---|---|---|
| 1 | `panel_hash` (re-hash of panel_v001) | `760c1e5935fe0474` |
| 2 | `hero_team_hash` (`teams/fixed_team.txt`) | `5aef213f351a6627` |
| 3 | `opp_team_hashes` (all 5 panel teams) | balance `f10c6e67…` · rain `69f471c2…` · sun `b0048ae6…` · tailwind `389416a6…` · trickroom `e622869d…` |
| 4 | `dev_schedule_hash` (`t4_smoke_v001.yaml`) | `a7f000867fdfbde0` |
| 5 | `heldout_schedule_hash` (`t6_heldout_v001.yaml`) | `3076a71aa6841c8c` |
| 6 | `showdown_commit` (provenance.yaml) | `f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5` |
| 7 | `server_patch_hash` (seeded-battle patch) | `bb973ec76d83cddb` |
| 8 | `reference_sha256` (dev `t4rerun-run1.jsonl`) | `14107d6c2004298de007a970f41dc533f264af08766fcb396ddc9589f56377dd` |
| 9 | `heldout_reference_sha256` (`t6-run1.jsonl`) | `ab6d6227a1be303fcb2da11ba341fd628aca85bbd7d0830ff4d8668661c57e8e` |

The manifest freezes the **T4-rerun** reference (`git_sha e2d6f34d…`, `seed_base t4rerun2026`)
plus this slice's held-out reference (`heldout_seed_base t6heldout2026`). Full-panel coverage is
transitively enforced by check #1 — a panel bump correctly fails this baseline as drift and resets
the held-out budget by design.

## 3. R7 — operational acceptance

**Provenance (both held-out runs):**

```
git_sha            564a06f7d5afa5e74ed92cac333e3c2b5b479947  (== HEAD; dirty=false in every row + both manifests)
config_hash        aeafb78a5beea9cd
panel_hash         760c1e5935fe0474
schedule_hash      3076a71aa6841c8c   (t6_heldout_v001.yaml, 34 rows: 2 held-out teams × {10,10,6,4,4})
seed_base          t6heldout2026
pythonhashseed     "0"          calc backend  SHOWDOWN_CALC_BACKEND=persistent
showdown_commit    f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5   (== server clone HEAD == provenance.yaml)
server_patch_hash  bb973ec76d83cddb

run_id 31f0c2bee34f5695   Run 1 (gated readout)  · result_sha256 ab6d6227…  · ~5.9 min
run_id d4df2e93a4d2395b   Run 2 (reproduction)   · result_sha256 f25d0ba8…  · ~5.9 min
run_id b177fd41472aa2b4   dev spot-check (prefix)· seed_base t4rerun2026     · ~1.9 min
```

**Both `check_access` assertions (R7 budget mechanism, exercised end-to-end):**

Pre-Run-1 (only the `schedule` entry exists — schedule entries never consume budget):
```
check_access(read_ledger(...), "aeafb78a5beea9cd") -> returned None   (clean pass)
```

Pre-Run-2, against the ledger with Run 1's `run` entry present:
```
# without justification -> MUST refuse:
AccessBudgetError: held-out access budget exceeded for config_hash='aeafb78a5beea9cd': a prior
'run' entry already exists for this config; pass justification=<reason> to proceed anyway (the
reason is recorded on the new ledger entry)

# with justification -> MUST pass:
check_access(..., justification="reproduction re-run of baseline-heldout-v1, same session")
  -> returned None   (clean pass)
```

The reproduction re-run deliberately spends a second budget entry and therefore **requires** the
recorded justification — the budget is proven on day one instead of special-cased.

**Gate readout (T5 `eval-report`, single-run gate mode — first production use, no throwaway
checker):** `data/eval/t6/t6-run1-report.md` first line:
```
# VERDICT: SINGLE-RUN SAFETY-PASS
```
All 19 safety gates PASS (rows 34==34, invalid 0, crashes 0, all `end_reason` normal, p95 worst
334 ms < 1000, 34 contiguous derived seeds, one config/schedule/seed_base/run_id/git_sha,
`split_integrity` consistent, manifest match). **Held-out banner present** (grep-confirmed in the
committed report):

> HELD-OUT RUN — these numbers must never inform tuning decisions.

**Double-run reproduction (`data/eval/t6/repro_run2.txt`):**
```
LOG IDENTITY: 34/34 ; ROW IDENTITY: 34/34
T6 DOUBLE-RUN REPRODUCTION PASS 34/34
```
All 34 rows match on winner + seed + turns + room-log byte-hash; `run_id` differs by design,
`config_hash`/`schedule_hash` identical.

**Baseline dev reproduction spot-check (`data/eval/t6/baseline_spotcheck.txt`)** — a fresh
`t4rerun2026`-seeded prefix run compared to the frozen dev reference rows 0–9 via
`verify_winner_sequence`:
```
BASELINE DEV SPOT-CHECK PASS: winner+seed sequences match (10/10)
```
A baseline that cannot be re-reproduced is a label, not a baseline — this proves the frozen dev
reference still regenerates byte-for-byte.

## 4. The Struggle blocker — first attempt BLOCKED, fix proved in production

The first held-out run attempt was **BLOCKED** mid-run: a Pokémon that had exhausted all PP was
handed a Struggle-only request whose `MoveSlot` omitted the `pp`/`maxpp` fields, and the request
parser rejected it. This is a **correctness fault surfaced by the run, not a determinism or gate
failure** — exactly what a live run is for. The fix landed as its own commit **before** Task 6:

> `564a06f` — `fix(2b-3.5 T6): tolerate Struggle-only requests (MoveSlot pp/maxpp optional)`
> (`models/request.py` + a `request_struggle_only.json` fixture + 52 lines of new tests)

The run was **restarted from scratch** on the fixed tree (`564a06f`), and both held-out runs +
the reproduction + the spot-check all passed cleanly — i.e. the fix was **proved in production**,
not just in unit tests. **The aborted attempt cost NO held-out budget:** it never produced a
completed 34-row result and never appended a `run` ledger entry (its evidence sits at
`C:/tmp/t6_aborted`, deliberately **not committed**). The budget lineage begins with Run 1 on the
fixed tree.

## 5. Committed artifacts (`data/eval/t6/`)

Byte-pinned by `data/eval/t6/sha256.txt` (83 files): both runs' `t6-run{1,2}.jsonl` +
`.manifest.json` + `-seedlog.jsonl` + `-telemetry.jsonl`; the Run 1 eval-report
(`t6-run1-report.md` / `.json`); `repro_run2.txt`; `baseline_spotcheck.txt`; the spot-check
`spot_results.jsonl` (+ manifest) / `spot_seeds.jsonl`; and **68 gzipped room logs**
(`room_raw/run1/` 34 + `room_raw/run2/` 34). `.gitattributes` marks `data/eval/t6/** -text` and
`data/eval/t6/room_raw/** binary` so the checksums survive checkout on any platform.

## 6. Held-out numbers — recorded, not discussed

The per-cell win rates for the held-out run live in `data/eval/t6/t6-run1-report.md` /
`.json`. They are **recorded, never discussed or acted upon** here — see the banner quoted in §3:
*"HELD-OUT RUN — these numbers must never inform tuning decisions."* They exist solely as the
future 2b-4 comparison substrate; a single run cannot establish improvement over any baseline, and
any strength claim requires a paired run against this pinned baseline with the positive-evidence
rule (McNemar, n_discordant ≥ 10, positive delta).

## 7. Suite

- **Pre-commit:** 798 passed, 1 skipped (baseline-immutability test skips — file not yet in git
  history).
- **Post-commit:** 799 passed, 0 skipped — both git-history enforcement tests (ledger append-only,
  baseline immutable) armed and green. New test:
  `test_baseline.py::test_verify_baseline_real_committed_manifest_green` (the only source-tree
  change in Task 6, per plan). `battle/` untouched; stdlib-only.

## 8. Reproduction commands

Fresh seeded server per run (Channel A, counter from 0), then the client from `showdown_bot/`.
Held-out runs used `t6_heldout_v001.yaml`, seed base **`t6heldout2026`**; the spot-check used
`t4_smoke_v001_prefix.yaml`, seed base **`t4rerun2026`**.

```bash
# --- server (per run; clone HEAD f8ac1400…, seeded-battle patch bb973ec7…) ---
MSYS_NO_PATHCONV=1 SHOWDOWN_BATTLE_SEED_BASE=t6heldout2026 \
  SHOWDOWN_EVAL_SEED_LOG=C:/tmp/t6/run1_seeds.jsonl \
  node pokemon-showdown start 8000 --no-security

# --- Run 1 (gated) → run_id 31f0c2bee34f5695 ---
cd showdown_bot
MSYS_NO_PATHCONV=1 PYTHONHASHSEED=0 SHOWDOWN_CALC_BACKEND=persistent \
  SHOWDOWN_BATTLE_SEED_BASE=t6heldout2026 SHOWDOWN_EVAL_SEED_LOG=C:/tmp/t6/run1_seeds.jsonl \
  python -m showdown_bot.cli gauntlet \
    --schedule ../config/eval/schedules/t6_heldout_v001.yaml \
    --result-out C:/tmp/t6/run1_results.jsonl

# --- gate readout via T5 ---
python -m showdown_bot.cli eval-report --run-a C:/tmp/t6/run1_results.jsonl \
  --seedlog-a C:/tmp/t6/run1_seeds.jsonl \
  --schedule ../config/eval/schedules/t6_heldout_v001.yaml \
  --panel ../config/eval/panels/panel_v001.yaml --out C:/tmp/t6/report_run1 --mode gate

# --- Run 2 (reproduction; fresh server + run2_seeds.jsonl) → run_id d4df2e93a4d2395b ---
#     …identical client invocation with --result-out C:/tmp/t6/run2_results.jsonl
```

Re-runnable baseline verification against the committed tree:

```bash
cd showdown_bot
python -c "from showdown_bot.eval.baseline import load_baseline, verify_baseline; \
  b=load_baseline('../config/eval/baselines/heuristic-v1.json'); \
  print('BASELINE OK', len(verify_baseline(b, repo_root='..')), 'checks')"
```

The winner/seed/turns compares and room-log byte-diffs were run with throwaway scripts; their
results are fully captured in the committed `repro_run2.txt` / `baseline_spotcheck.txt`, and every
gate + hash above is enumerated so no external script is needed to audit this run.
