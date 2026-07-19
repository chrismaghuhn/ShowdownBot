# Accuracy Default-On — Dev/Strength Panel Measurement Spec

**Status:** APPROVED — 2026-07-14 (measurement only; **no bot code** in this slice)
**Provenance condition:** local runs require `git status --porcelain` empty — use a clean
worktree/checkout or Kaggle at `REPO_SHA=a956b6b` (untracked files in the main worktree block
`dirty=false`).
**Date:** 2026-07-14
**Commit basis:** `a956b6b` (`main` = `origin/main`)
**Implements:** checklist item 6 in
[`reports/2026-07-14-accuracy-default-on-decision-note.md`](reports/2026-07-14-accuracy-default-on-decision-note.md)

## 0. What this slice does

Run one **paired dev-strength A/B** under production default-on (`a956b6b`), compare against an
**explicit accuracy-off arm on the same commit**, and produce a deterministic `eval-report` paired
readout. This slice defines **how to measure**; it does not change bot code, gate artifacts, or
make a ship/strength claim before human review.

## 1. Explicit non-goals

- **No bot / eval-harness code changes** before this spec is approved and the run completes.
- **No edit** to `data/eval/accuracy-gate/` or cap-derisk gate JSON (frozen references).
- **No held-out panel** (`t6_heldout_v001`) — user-gated; out of scope for this run.
- **No automatic GO/ship claim** from the report verdict alone; human review required.
- **No retroactive pairing** against archived single-arm runs (different `git_sha` / `seed_base`).
- **No new latency sweep** — only observe `latency_p95` on the live 150-game panel.

## 2. Question under test

> On the existing dev-strength panel, does **production default-on accuracy** (unset env → mode on,
> branch cap 6 at `a956b6b`) change paired winrate vs **explicit accuracy-off** on the **same
> commit**, without violating safety gates?

This is **not** “accuracy improves strength.” It is a bounded measurement of the default flip’s
effect on the dev panel vs the reproducible off-path.

## 3. Corpus, teams, opponents

Reuse the committed dev-strength schedule unchanged:

| Field | Value |
|-------|-------|
| Schedule | `config/eval/schedules/2b4_devstrength_v001.yaml` |
| Schedule hash | `9ce8872b75065c63` (from schedule file) |
| Panel | `config/eval/panels/panel_v001.yaml` |
| Panel hash | `760c1e5935fe0474` |
| Panel split | **dev only** (3 cells) |
| Format | `gen9vgc2025regi` |
| Games | **150** (50 seeds × 3 cells) |
| Hero team | `teams/fixed_team.txt` (`hero_team_hash` `5aef213f351a6627`) |
| Hero agent | default heuristic gauntlet config (`config_id` expected: `heuristic`) |

### 3.1 Opponent cells (all `max_damage`)

| Cell | Opp team path | Opp team hash | Seeds |
|------|---------------|---------------|-------|
| trickroom | `teams/panel_v001/trickroom_dev.txt` | `e622869d6c68307e` | 0–49 |
| sun | `teams/panel_v001/sun_dev.txt` | `b0048ae65f0e9ee5` | 50–99 |
| rain | `teams/panel_v001/rain_dev.txt` | `69f471c2740f1927` | 100–149 |

**Caveat (must appear in the report narrative):** all opponents are `max_damage` (worst-case damage).
Dev-panel results do **not** prove generalization to varied or human opponents.

## 4. Experimental design — paired env A/B

Two arms, **same** `git_sha`, schedule, panel, format, and `seed_base`; **only** `extra_env`
differs. Pairing contract: `eval.pairing.pair_runs` + McNemar in `eval-report` paired mode.

| Arm | Role in `eval-report` | Env (`extra_env`) | Intended behavior at `a956b6b` |
|-----|----------------------|-------------------|--------------------------------|
| **A — candidate** | `--run-a` / `--seedlog-a` | `{}` (omit accuracy keys) | Production path: unset → accuracy **on**, branch cap **6** |
| **B — baseline** | `--run-b` / `--seedlog-b` | `{"SHOWDOWN_ACCURACY_MODE": "0"}` | Explicit opt-out: always-hit accuracy path |

**Do not** set `SHOWDOWN_ACCURACY_BRANCH_CAP` on either arm unless debugging — candidate arm must
exercise the **unset → 6** production default; baseline arm’s cap is irrelevant when mode is off.

**Provenance check after run:** both manifests’ `behavior_env` (or row-level env snapshot) must
reflect the intended arms; `config_hash` **must differ** between A and B
(`SHOWDOWN_ACCURACY_MODE` is behavior-affecting per `eval/config_env.py`).

### 4.1 Why not pair against archived `2b4-devstrength-v001`?

| Reference | Path / identity | Role in this measurement |
|-----------|-----------------|--------------------------|
| **Primary baseline (B)** | Fresh arm B on `a956b6b`, `SHOWDOWN_ACCURACY_MODE=0` | **Only valid McNemar baseline** — same code, paired seeds |
| **Contextual (non-paired)** | `data/eval/2b4/strength/heuristic/results.jsonl` @ `13795ab`, `seed_base` `2b4-devstrength-v001`, `config_hash` `23351717487f69e5` | Historical accuracy-off-by-default snapshot (26/150 ≈ 17.3% overall). **Not pairable** — different `git_sha`, different `seed_base`, many intervening commits |

Use the contextual row only as background in the write-up; **never** as the McNemar denominator.

## 5. Run identity

### 5.1 Pinned constants (declare before launch)

| Constant | Value | Notes |
|----------|-------|-------|
| `REPO_SHA` | `a956b6b` | Required; no floating `main` |
| `seed_base` | **`accuracy-default-on-v001`** | **New** — distinct from `2b4-devstrength-v001` and `2c1-mustreact-v001` to avoid archive collision |
| `schedule_relpath` | `config/eval/schedules/2b4_devstrength_v001.yaml` | Default for `run_devstrength_env_ab` |
| Measurement slug | `accuracy-default-on-devstrength-ab` | For paths and report title |

### 5.2 Runtime-generated (record from manifests, do not pre-assign)

| Field | Source |
|-------|--------|
| `run_id` | `make_run_id(seed_base, schedule_hash, config_hash, start_ts)` per arm |
| `config_hash` | `make_config_hash(behavior_env)` — expect **two distinct values** |
| `start_ts`, `git_sha`, `dirty`, input file sha256 | Run manifest + `eval-report` provenance block |

### 5.3 Expected offline gate context (not re-run)

Gate-B already passed at cap 6 on the **replay corpus** (`6/944`, 0 exceptions). This measurement
tests **live battles** on the dev panel; the known offline action delta for off → cap 6 was **20/944**
(`cross-cap-diffs.json`). Live discordant battles may differ; do not assume 20/150.

## 6. Execution

### 6.1 Preferred path — local paired runner

Use existing infrastructure without code changes:

```text
tools/kaggle/kernel_payload.run_devstrength_env_ab(
    repo_root, showdown_dir, out_dir,
    baseline_env={"SHOWDOWN_ACCURACY_MODE": "0"},
    candidate_env={},
    seed_base="accuracy-default-on-v001",
)
```

Equivalent to two `run_schedule_seeded(...)` calls (see `tools/kaggle/kernel_payload.py`). Requires
local Node Showdown + calc bridge (same as other gauntlet repros).

**Output layout (working):**

```text
<out_dir>/
  baseline/   results.jsonl  seeds.jsonl  (+ manifest, room_raw, client.log)
  candidate/  results.jsonl  seeds.jsonl  (+ manifest, room_raw, client.log)
```

Suggested commit staging root:

```text
data/eval/accuracy-default-on/devstrength-ab/
  baseline/
  candidate/
  paired-report/
```

### 6.2 Alternate path — Kaggle `env_ab_kernel.py`

Push one kernel with header:

```json
{
  "REPO_SHA": "a956b6b",
  "BASELINE_ENV": {"SHOWDOWN_ACCURACY_MODE": "0"},
  "CANDIDATE_ENV": {},
  "SEED_BASE": "accuracy-default-on-v001"
}
```

Copy `/kaggle/working/{baseline,candidate}/` locally before `eval-report`. Same pairing contract.

### 6.3 Pre-flight checklist

- [ ] `git rev-parse HEAD` = `a956b6b`, working tree clean (`dirty: false`)
- [ ] `seed_base` = `accuracy-default-on-v001` on **both** arms
- [ ] Schedule/panel files match hashes in §3
- [ ] No extra `SHOWDOWN_*` behavior knobs set unless documented
- [ ] Both arms complete 150 rows (`rows_match_schedule`)

## 7. Report generation

From repo root (panel paths resolve relative to `showdown_bot/`):

```bash
python -m showdown_bot.cli eval-report \
  --run-a data/eval/accuracy-default-on/devstrength-ab/candidate/results.jsonl \
  --seedlog-a data/eval/accuracy-default-on/devstrength-ab/candidate/seeds.jsonl \
  --run-b data/eval/accuracy-default-on/devstrength-ab/baseline/results.jsonl \
  --seedlog-b data/eval/accuracy-default-on/devstrength-ab/baseline/seeds.jsonl \
  --schedule config/eval/schedules/2b4_devstrength_v001.yaml \
  --panel config/eval/panels/panel_v001.yaml \
  --out data/eval/accuracy-default-on/devstrength-ab/paired-report \
  --mode gate
```

Optional follow-up (diagnostic, **not** gating): `decision-diff` on discordant battles — only after
paired report exists.

## 8. Acceptance and report criteria

### 8.1 Safety (dominates — either arm fails → **SAFETY-FAIL**, no strength readout)

From `eval/report.py` `run_safety_gates` with `--mode gate`:

| Gate | Criterion |
|------|-----------|
| `rows_match_schedule` | 150 / 150 |
| `invalid_choices` | 0 |
| `crashes` | 0 |
| `end_reason_normal` | all `normal` |
| `latency_p95` | worst row ≤ **1000 ms** (`config/eval/gates.yaml`) |
| `seed_log_alignment` | pass |
| `no_duplicate_rows` | pass |
| `panel_hash_match` | pass |
| `dirty` | pass (gate mode: fail if dirty) |
| `split_integrity` | dev cells only |

If **SAFETY-FAIL**: stop. File incident note; do not interpret McNemar.

### 8.2 Paired strength readout (only if safety passes)

Verdict tree (`_paired_verdict`, spec §1.3):

| Outcome | Meaning for this measurement |
|---------|------------------------------|
| **SAFETY-FAIL** | Blocked — fix infra/env before re-run |
| **UNDERPOWERED** | `n_discordant` < 10 — report numbers but **no strength claim** |
| **NO-GO** | Safety passed but positive-evidence tree failed (Δ≤0, p≥0.05, cell flip, or strength_delta≤0) |
| **GO** | All of: Δ>0, exact McNemar p<0.05, no winning→losing cell flip, strength_delta>0 on `max_damage` cells |

**Strength policies in this schedule:** only `max_damage` — entire panel counts toward
`strength_delta` (150 pairs).

### 8.3 Required report contents (human review)

The post-run note (separate from this spec) must include:

1. **Provenance table** — both arms’ `run_id`, `config_hash`, `git_sha`, `seed_base`, input sha256
2. **McNemar table** — n10, n01, n_discordant, Δ, exact p, automated verdict
3. **Per-cell winrate** — trickroom / sun / rain (`opp_team_hash` or path)
4. **Discordant battle list** — from report JSON (`discordant_battles`)
5. **Safety gate table** — both arms
6. **Explicit caveats** — `max_damage`-only dev panel; not held-out; contextual `13795ab` reference
   not paired
7. **No ship language** unless user promotes a follow-up held-out plan

### 8.4 What this measurement can and cannot conclude

| Can conclude (if safety passes) | Cannot conclude |
|--------------------------------|-----------------|
| Paired winrate effect of default-on vs explicit-off on this panel | Generalization to held-out or human opponents |
| Whether sun/trickroom/rain cells regressed individually | That Gate-B replay fidelity implies live winrate gain |
| Whether latency budget survived live cap-6 branching | Automatic production “ship” approval |

## 9. Artifacts to commit (after run + review)

| Path | Content |
|------|---------|
| `data/eval/accuracy-default-on/devstrength-ab/baseline/` | results, seeds, manifest (+ optional room_raw if policy matches prior eval commits) |
| `data/eval/accuracy-default-on/devstrength-ab/candidate/` | same |
| `data/eval/accuracy-default-on/devstrength-ab/paired-report/` | `report.md`, `report.json` |
| `reports/2026-07-14-accuracy-default-on-devstrength-verdict.md` | Human verdict note (post-run) |

Do **not** commit: local `AGENTS.md`, `CLAUDE.md`, partial logs, or gate JSON under
`data/eval/accuracy-gate/`.

## 10. Approval gate before any follow-up code

1. User approves **this measurement spec**.
2. Execute §6 run at `a956b6b`.
3. Generate §7 report; write §9 verdict note.
4. User reviews verdict note — **only then** consider further bot/eval work (e.g. held-out plan,
   ROADMAP strength row update, Depth-2 Stage 3 discussion).

---

**Summary:** One paired 150-game dev-strength run at `a956b6b`, `seed_base=accuracy-default-on-v001`,
candidate = production unset env, baseline = `SHOWDOWN_ACCURACY_MODE=0`, McNemar via
`eval-report --mode gate`. Primary comparison is arm B on the same commit; archived `13795ab`
heuristic run is contextual only.
