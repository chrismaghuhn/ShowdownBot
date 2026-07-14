# Champions Panel v0 — P0 Format Discovery Verdict

**Date:** 2026-07-14  
**Verdict:** **PASS**  
**Branch:** `champions-panel-v0-p0` (worktree)  
**Spec:** `docs/superpowers/specs/2026-07-14-champions-panel-v0-design.md`

## Readout

P0 format discovery **PASS**. Primary BO1 target:

**`gen9championsvgc2026regma`** — `[Gen 9 Champions] VGC 2026 Reg M-A`

Also documented (not panel-default): `gen9championsvgc2026regmabo3`, `gen9championsvgc2026regmb`,
`gen9championsvgc2026regmbbo3`.

## Key findings

| Finding | Implication |
|---------|-------------|
| Live `formats.js` ↔ pinned `formats.ts` (`f8ac140`) agree on all four VGC Reg M entries | Harness pin is usable for validation + future smoke |
| `validate-team gen9championsvgc2026regma` works | Team curation gate is well-defined |
| `fixed_team.txt` **fails** Champions validation; **passes** Reg I | Reg-I hero must not be reused blindly |
| `gen9vgc2025regma` / `regmb` **not** valid Showdown format IDs | VGC-Bench log headers remain ingest-only aliases — no gauntlet workaround |
| Replay + sim `\|tier\|` = `[Gen 9 Champions] VGC 2026 Reg M-A` | Challenge string confirmed |

## Gate decision

| Gate | Status |
|------|--------|
| P0 Format discovery | **PASS** |
| P1 Mechanics audit | **Unlocked** — pending explicit approval |
| Team curation / panel v0 | **Unlocked** — pending P1 + user approval |
| P4 pipeline smoke | Still blocked on panel artefacts (not P0) |

## Non-actions (confirmed)

- No teams, panel YAML, or schedules committed in P0.
- No Reg-I or VGC-Bench format aliases used.
- No strength run.

**Detail:** `data/eval/champions-panel-v0/discovery/format-discovery-report.md`
