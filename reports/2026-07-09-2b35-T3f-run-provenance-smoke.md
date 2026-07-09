# 2b-3.5 T3f Task 7 — Run-Provenance Readiness Smoke (run 2026-07-09)

Final T3f piece: prove the run-provenance plumbing end-to-end on a live tiny dev eval —
every result row carries the new provenance fields, one self-describing run manifest is
written with server/patch provenance, and `config_hash`/`run_id` are constant across the
run. Branch: `feat/slice-2b35-t3f-run-provenance-readiness`. `git HEAD`:
`1bc905236bd496da50807ec37dbdf05b207d9bf0` (clean tree). This smoke proves *provenance
plumbing*, not playing strength — win rates are recorded, not editorialized.

## What T3f added (verified by this smoke)
- **`seed_base`** result-row field — the raw `SHOWDOWN_BATTLE_SEED_BASE` string (not re-derived
  from `seed`), so T5 can pair on `(schedule_hash, seed_base, seed_index)`.
- **`run_id` + run manifest** (`eval/run_manifest.py`) — one `run_id` constant across every row
  of a `--result-out` run, plus a `<result-out>.manifest.json` sidecar stamping server/patch
  provenance (`showdown_commit`, `server_patch_hash`), `git_sha`/`dirty`, `pythonhashseed`,
  `cli_invocation`, `start_ts`, and the run-level `config_hash`.
- **`panel_split`** result-row field — `"dev"`/`"heldout"` from the schedule row (null for legacy).
- **`end_reason`** result-row field — `normal`/`timeout`/`forfeit`/`crash`.
- **effective `config_hash`** (`eval/config_env.py` fail-closed `SHOWDOWN_*` classification) —
  stable, order-independent hash of the effective-config manifest; constant across a run.
- (+ T3e's `dirty` flag and `hero_team_hash`/`opp_team_hash` team-content provenance.)

## Smoke — tiny dev schedule (exactly 6 battles, no subset)
`generate_dev_schedule(panel_v001, policies=["simple_heuristic","greedy_protect"])` over **all 3
dev teams** (trickroom / sun / rain) → **2 policies × 3 teams = 6 battles**.
`schedule_hash=db4d0a7a31070a62`, `panel_hash=760c1e5935fe0474`, all rows `panel_split="dev"`.
Fresh seeded server, `PYTHONHASHSEED=0`, seed base `t3f2026`, clean working tree.

```bash
cd showdown_bot
# 1) generate the 6-battle schedule (hero = teams/fixed_team.txt)
python -c "from pathlib import Path; from showdown_bot.eval.panel import load_panel; \
from showdown_bot.eval.panel_schedule import generate_dev_schedule, write_schedule_yaml; \
sb=Path.cwd(); p=load_panel(str(sb.parent/'config/eval/panels/panel_v001.yaml'), teams_root=str(sb)); \
write_schedule_yaml(generate_dev_schedule(p, policies=['simple_heuristic','greedy_protect'], teams_root=str(sb)), 'C:/tmp/t3f_dev6.yaml')"
# 2) fresh seeded server (Channel A, counter from 0), server env carries seed base + log:
#   MSYS_NO_PATHCONV=1 SHOWDOWN_BATTLE_SEED_BASE=t3f2026 SHOWDOWN_EVAL_SEED_LOG=C:/tmp/t3f_seeds.jsonl \
#     node pokemon-showdown start 8000 --no-security
# 3) client run:
MSYS_NO_PATHCONV=1 PYTHONHASHSEED=0 SHOWDOWN_CALC_BACKEND=persistent \
  SHOWDOWN_BATTLE_SEED_BASE=t3f2026 SHOWDOWN_EVAL_SEED_LOG=C:/tmp/t3f_seeds.jsonl \
  python -m showdown_bot.cli gauntlet --schedule C:/tmp/t3f_dev6.yaml --result-out C:/tmp/t3f_results.jsonl
```

> **Operational note (not a code bug):** on Git Bash / Windows, POSIX `/tmp/...` paths passed as
> **command-line arguments** are rewritten by MSYS to the `/tmp` mount
> (`C:\Users\chris\AppData\Local\Temp`), while `/tmp/...` inside a Python string literal resolves
> **drive-relative** to `C:\tmp`. Those two locations differ, so a schedule written by the
> generator to one path is not found by the client at the other. Fix used here: explicit
> drive-letter paths (`C:/tmp/...`) plus `MSYS_NO_PATHCONV=1` so every native process resolves the
> same file. The client correctly opened exactly the path it was handed — no source change.

## Gates (all measured this run)
| Gate | Result |
|---|---|
| Result rows | **6** (one per schedule row), **all re-validate** (`validate_battle_row`) |
| Safety | **0 invalid · 0 crashes** (per row and in totals) |
| `seed_base` in rows | all **`t3f2026`** ✅ |
| `run_id` in rows | all **`854770b14c28b0a2`**, constant across the run, **== manifest** ✅ |
| `panel_split` in rows | all **`dev`** ✅ |
| `end_reason` in rows | all **`normal`** ✅ |
| `config_hash` in rows | all **`aeafb78a5beea9cd`**, constant across the run, **== manifest** ✅ |
| `dirty` in rows | all **`false`** (clean tree) ✅ |
| `hero_team_hash` | all **`5aef213f351a6627`** ✅ |
| `opp_team_hash` | trickroom `e622869d6c68307e` · sun `b0048ae65f0e9ee5` · rain `69f471c2740f1927` ✅ |
| `panel_hash` in rows | all **`760c1e5935fe0474`** ✅ |
| `git_sha` in rows | all **`1bc9052…`** (== `git rev-parse HEAD`) ✅ |
| Run manifest | written once at `<result-out>.manifest.json`; all fields present ✅ |
| manifest `pythonhashseed` | **`"0"`** ✅ |
| manifest `server_patch_hash` | **`bb973ec76d83cddb`** (non-null; == sha1[:16] of the versioned patch) ✅ |
| manifest `showdown_commit` cross-check | **`f8ac1400…`** == clone HEAD == `config/eval/provenance.yaml` ✅ |
| manifest `git_sha` / `dirty` | `1bc9052…` / `false` (both == rows) ✅ |
| Seed-log alignment | **OK** — `verify_schedule_alignment`: 6 battles, contiguous `battle_index` 0..5, `seed == derive_battle_seed(t3f2026, seed_index)` ✅ |
| Per-battle counters | per-battle, **NOT cumulative** — `decision_latency_p95_ms` = 291/303/306/279/347/267 (non-monotone) ✅ |
| Winners (record only) | hero 2 · villain 4 · ties 0 |

## Provenance block
```
schedule_hash       db4d0a7a31070a62
panel_hash          760c1e5935fe0474
config_hash         aeafb78a5beea9cd   (constant across the run; rows == manifest)
run_id              854770b14c28b0a2   (constant across the run; rows == manifest)
seed_base           t3f2026
git_sha             1bc905236bd496da50807ec37dbdf05b207d9bf0
dirty               false
start_ts            2026-07-09T22:03:50.402492+00:00 (UTC)
pythonhashseed      "0"
showdown_commit     f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5  (== clone HEAD == provenance.yaml)
server_patch_hash   bb973ec76d83cddb                          (== sha1[:16] of pokemon-showdown-seeded-battle.patch)
```

## Anomalies (all benign; no gate affected)
- **Battle seed_index=4** (rain / `simple_heuristic`) logged three end-game warnings —
  `heuristic failed, falling back: no legal joint actions` → `max_damage fallback failed` →
  `random fallback failed: No legal actions for request`. This is the ordinary end-of-battle
  no-legal-action situation (the request offered no choosable action); the battle still finished
  with a winner and the row recorded `invalid_choices=0`, `crashes=0`, `end_reason="normal"`.
- **Win rate** shifted to hero 2 / villain 4 (vs the pre-T3e-P2a hero 4 / villain 2). This is the
  expected effect of T3e's now-type-aware `simple_heuristic` opponent, not a T3f change; recorded
  here only for the record.
- **Date roll:** the run's UTC `start_ts` is 2026-07-09 (local clock had just passed midnight into
  07-10 at UTC+2); report filename uses the UTC run date per the controller decision.

## VERDICT: **PASS**
All provenance gates hold on a live 6-battle dev run: every row carries `seed_base`,
`run_id` (constant, == manifest), `panel_split="dev"`, `end_reason="normal"`, and a constant
effective `config_hash` (plus T3e's `dirty=false` and team hashes). The run manifest was written
once with correct server/patch provenance, its `showdown_commit` matches both the actual server
clone HEAD and `provenance.yaml`, and seed-log alignment verified 6 contiguous battles with
Python↔server seed agreement. 0 invalid / 0 crash.
