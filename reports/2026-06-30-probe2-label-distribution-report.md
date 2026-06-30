# Dataset Probe 2 — Live-Gauntlet Label Distribution (2026-06-30)

Real rollout-export dataset from a **live local gauntlet** (HeuristicBot vs max_damage baseline,
mirror `fixed_team`, `gen9vgc2024regg`), persistent calc, rollout teacher H=1, `sample_policy=all`.
No JSONL committed — this report is the durable record.

## Setup (reproducible)
```
pokemon-showdown server: ~/.cache/showdownbot/pokemon-showdown @ commit f8ac140
  started: node pokemon-showdown start --no-security 8000   (stopped after the probe)
env: SHOWDOWN_DATASET_EXPORT=<path> SHOWDOWN_DATASET_TEACHER=rollout
     SHOWDOWN_CALC_BACKEND=persistent SHOWDOWN_ROLLOUT_HORIZON=1 SHOWDOWN_DATASET_SAMPLE_POLICY=all
     SHOWDOWN_TEAM_PATH=teams/fixed_team.txt
cmd: cli gauntlet --games 15 --villain max_damage --format gen9vgc2024regg
result: 5/15 wins, 0 crashes, 0 invalid_choices, no stall
```

## Dataset
- **664 rows · 135 decisions · 15 games** (~9 decisions/game = normal VGC).
- All `teacher_version="rollout-h1-v1"`, `trainable_label=true`, **config_hash stable** (`cc5d6b24`).
- Label keys exact (8/8), **0 NaN, 0 None**. Candidates/decision: {1:14, 2:16, 5:12, 6:93}
  (the 14 one-candidate = forced/single-legal, e.g. force-switch — trivial, not skips).

## Key model-design signals
- **Heuristic == teacher_best (on real multi-candidate decisions): 60% (72/121)** — 64% incl.
  trivial. ⇒ **~40% learnable disagreement** — the reranker has real room.
- **Contestable decisions: 30% (41/135)** have ≥1 near-equal alternative (|value_gap|≤0.5). These
  are where reranking matters; the rest are dominated by a clear best.
- **teacher_best is unique in 120/135 decisions** (15 have 2 co-best ties) — labels are decisive.
- **Per-action-type agreement (heuristic's chosen action):**
  - **attack: 47% (40/85)** ← the biggest opportunity (the teacher prefers a different line on ~half of attacks)
  - protect: 76% (13/17)
  - other/status/switch: ~100% (largely trivial/forced)
  (rough categorization via `predicted_outgoing_damage`/`protect_stall_penalty`; the rows also carry
  clean `slot{1,2}_action_type`/`is_switch`/`is_protect`/`move_category` for precise per-type work.)
- **value_gap_to_best** (non-best, n=402): median −2.99, p25 −6.27, p75 −0.62; **21% within 0.5 of
  best, 28% within 1.0** — a healthy mix of clear-cut and near-equal.
- **normalized_within_decision:** min −9.56 · median 0.00 · max 10.34 · stdev 2.59 — real spread,
  not skewed/degenerate.

## Runtime
- Persistent calc backend made it feasible: ~3s/sampled-decision (vs ~146s one-shot); the whole
  15-game probe ran without the per-batch Node startup tax.

## Bugs the live probe surfaced (separate from hero/export — flagged for follow-up)
1. **Format misnomer (FIXED):** the bot's internal name `gen9vgc2026regi` = what Showdown calls
   `gen9vgc2025regi` (VGC 2025 Reg I). The config has been renamed to `gen9vgc2025regi` and all
   references updated; CLI default is now `gen9vgc2025regi` (the real server id).
2. **`random` baseline tera bug:** `pick_random_pair` emits invalid **double-Terastallize** choices
   (`/choose move terastallize, move terastallize`) → server rejects → intermittent game stalls.
   `max_damage` (never-tera) is clean. Fix: cap tera to ≤1 slot + respect `canTerastallize`.
3. (Minor) one `no legal joint actions` heuristic fallback over the run (team-preview/force-switch edge).

## Go/No-Go for Slice 2b (Model + Training)
**GO.** The dataset is real, clean, deterministic, and shows a genuine learnable signal: ~40%
multi-candidate disagreement, 30% contestable decisions, with **attack decisions (47% agreement)
the clearest opportunity**. The near-equal-margin training rule is justified by the 30% contestable
rate. Next: scale the export (more games), then design the reranker grounded in these numbers.
