# Fast-Board Protect Discipline — play-quality lever attempt (atlas-gauged)

**Date:** 2026-07-11
**Branch:** `feat/slice-fast-board-protect`
**Spec/plan:** `docs/superpowers/specs/2026-07-11-fast-board-protect-discipline-design.md`,
`docs/superpowers/plans/2026-07-11-fast-board-protect-discipline.md`

## Verdict: NOT a lever — DEPTH-BOUND (env code merged OFF-by-default)

An env-gated `fast_board` Protect penalty, aimed by the teacher-disagreement atlas at the
`tailwind_both` weakness (heuristic disagrees with the rollout teacher ~92% of the time in
both-sides-Tailwind boards), does **not** reduce that disagreement. In a clean paired rain-panel A/B
the `tailwind_both` disagreement moved 91.7% → 90.2% (−1.5pp, noise on n=132) and mean regret got
slightly **worse** (9.26 → 9.44). Every other speed-control bucket is frozen. This is the
depth-bound outcome the spec anticipated: the tailwind_both gap is not reachable by a one-ply
valuation tweak → concrete motivation for belief/search.

## The change (byte-identical when off)

Mirrors the existing `endgame` Protect mechanism exactly. `battle/decision.py` computes
`fast_board = both sides have Tailwind up` and threads it into
`battle/evaluate.py::score_outcome_with_breakdown`; when we Protect on a fast board **and the Protect
blocked nothing** (the same wasted-tempo condition as the existing `protect_stall`), it adds the
`fast_board_protect` weight. The weight defaults to `0.0` and is only set by
`SHOWDOWN_FAST_BOARD_PROTECT_PENALTY` (classified BEHAVIOR_AFFECTING in `eval/config_env.py`). With
the env unset every score is unchanged → the 2b-2.5a dataset, the atlas, and all recorded runs stay
valid; every existing test stays green. Implemented in commit `8d53a37`.

## Measurement — clean paired rain A/B (the principled gauge, not winrate-vs-max_damage)

Winrate-vs-max_damage is a confounded gauge here (it rewards recklessness). The teacher-disagreement
atlas (`showdown_bot.eval.teacher_disagreement`) is the principled gauge — the teacher is a fixed
reference of better play.

- **flag-ON:** Kaggle kernel `sb-fbp-rain` (rain panel, `SHOWDOWN_FAST_BOARD_PROTECT_PENALTY=-3.0`),
  75 games / 7579 rows / 1386 decisions.
- **flag-OFF (paired baseline):** the rain subset of the committed 2b-2.5a aggregate
  (`data/datasets/phase3-slice2b25a/dataset.jsonl.gz`), isolated by `config_hash =
  9ef99d8415353a77` — identified as the rain shard by `team_hash` overlap (1/1) with the flag-ON set,
  since `game_id` encodes `config_hash` and does not overlap across the flag. 75 games / 7581 rows /
  1387 decisions.

Both sides re-labelled by the same rollout teacher; the atlas buckets by `speed_control_state`.

### Result — `speed_control_state` disagreement rate (flag-OFF → flag-ON)

| bucket | n | OFF rate | ON rate | Δ rate | OFF regret | ON regret |
|---|---|---|---|---|---|---|
| **tailwind_both** | 132 | **0.9167** | **0.9015** | **−0.0152** | 9.26 | 9.44 (**+0.18**) |
| tailwind_ours | 397 | 0.5441 | 0.5441 | 0.0000 | 6.20 | 6.20 |
| none | 573/574 | 0.6150 | 0.6161 | +0.0011 | — | — |
| tailwind_opp | 8 | 0.5000 | 0.5000 | 0.0000 | — | — |
| trick_room | 31 | 0.4194 | 0.4194 | 0.0000 | — | — |
| mixed | 5 | 1.0000 | 1.0000 | 0.0000 | — | — |
| **overall** | ~1386 | 0.6208 | 0.6195 | −0.0012 | — | — |

Evidence JSON: `reports/2026-07-11-fast-board-protect-discipline-flag-off-rain-atlas.json`
(OFF), `…-flag-on-atlas.json` (ON).

## Interpretation

- **−1.5pp on n=132 is noise** (a couple of decisions flipping), and mean regret rose. The penalty
  did not make the heuristic agree with the teacher more.
- **Why:** per the dataset action analysis (memory `tailwind-both-overdefensiveness`), of 126
  tailwind_both disagreements only a minority are Protect-spam — **93 are move→move** (different
  move/target) and **33 are heuristic-attacks → teacher-switches-one**. The dominant mechanism is the
  teacher's H-step **pivot-to-best-attacker** line, whose payoff accrues over later turns the one-ply
  resolver cannot see. A static valuation penalty on wasted Protect touches only the minority and
  cannot recover the depth signal.
- **Panel-stability sanity:** flag-OFF rain tailwind_both = 91.7% ≈ the committed full-panel baseline
  92% (n=137, regret 9.19), so `tailwind_both` is panel-stable and the bucket is a real weakness —
  just not a tunable one.

## Caveats

- Single penalty value (−3.0). A larger penalty is **not** expected to help: the mechanism analysis
  shows the gap is dominated by non-Protect disagreements, and a stronger penalty risks suppressing
  *good* Protects elsewhere. Not worth another Kaggle run.
- Rain panel only; mitigated by the panel-stability check above.

## Decision

NO-GO as a play-quality lever. The env-gated code is merged **OFF-by-default** (byte-identical when
unset), documented as a negative result. This is direct, quantified motivation for **belief/search**:
the teacher finds the aggressive fast-board line by depth; the one-ply heuristic cannot, penalty or
no penalty.

## Reproduction

```bash
# flag-ON atlas (from the sb-fbp-rain kernel output dataset.jsonl.gz):
python -m showdown_bot.eval.teacher_disagreement <sb-fbp-rain>/dataset.jsonl.gz \
  --out-md atlas_on.md --out-json atlas_on.json
# flag-OFF paired baseline: filter the 2b-2.5a aggregate to config_hash 9ef99d8415353a77,
# then run the same atlas on that subset.
```
