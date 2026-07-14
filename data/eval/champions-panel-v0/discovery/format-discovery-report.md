# Champions Panel v0 — P0 Format Discovery Report

**Date:** 2026-07-14  
**Verdict:** **PASS**  
**Spec:** `docs/superpowers/specs/2026-07-14-champions-panel-v0-design.md` §3  
**Worktree:** `champions-panel-v0-p0` @ `ee320f7`  
**Pinned Showdown:** `f8ac140` (`~/.cache/showdownbot/pokemon-showdown`)

## Summary

Live Pokémon Showdown exposes stable **Gen 9 Champions VGC 2026** doubles format IDs under the
`gen9championsvgc2026regm*` namespace. The eval harness pin (`f8ac140`) defines the same four
formats as the live `formats.js` snapshot. `validate-team` and local battle sim accept the
primary BO1 ID. **VGC-Bench legacy IDs (`gen9vgc2025regma` / `regmb`) are not valid challenge or
validator IDs** on the pinned server.

**P1 (mechanics / validation audit) and team curation may proceed.** No Reg-I or VGC-Bench alias
workarounds.

## Confirmed format IDs

| Human tier | Machine ID | Mod | gameType | Ruleset (pinned) | Panel v0 role |
|------------|------------|-----|----------|------------------|---------------|
| [Gen 9 Champions] VGC 2026 Reg M-A | **`gen9championsvgc2026regma`** | `championsregma` | doubles | Flat Rules, VGC Timer, Open Team Sheets | **Primary BO1** |
| [Gen 9 Champions] VGC 2026 Reg M-A (Bo3) | `gen9championsvgc2026regmabo3` | `championsregma` | doubles | + Force OTS, Best of = 3 | Document |
| [Gen 9 Champions] VGC 2026 Reg M-B | `gen9championsvgc2026regmb` | `champions` | doubles | Flat Rules, VGC Timer, Open Team Sheets | Document |
| [Gen 9 Champions] VGC 2026 Reg M-B (Bo3) | `gen9championsvgc2026regmbbo3` | `champions` | doubles | + Force OTS, Best of = 3 | Document |

IDs resolved via `Dex.formats.get(name).id` on pinned clone (authoritative — not inferred from
name alone).

## Source A — live `formats.js`

- **Artifact:** `data/eval/champions-panel-v0/discovery/formats.js.snapshot` (145 903 bytes,
  fetched 2026-07-14 from `https://play.pokemonshowdown.com/data/formats.js`)
- All four VGC 2026 Reg M-A/M-B names present with matching `mod`, `gameType: doubles`, and
  `ruleset` strings vs pinned `config/formats.ts`.

## Source B — pinned `config/formats.ts` @ `f8ac140`

Excerpt (lines 289–316):

- M-A BO1: `mod: 'championsregma'`, `gameType: 'doubles'`, OTS ruleset
- M-B BO1: `mod: 'champions'`, `gameType: 'doubles'`, OTS ruleset
- Bo3 variants: `Force Open Team Sheets`, `Best of = 3`

**No** `gen9vgc2025regma` / `gen9vgc2025regmb` entries in pinned `formats.ts`.

## Source C — live replay cross-check

- URL: https://replay.pokemonshowdown.com/gen9championsvgc2026regma-2598085389
- Replay page format: **`[Gen 9 Champions] VGC 2026 Reg M-A`**
- Path segment matches primary machine ID.

## Source D — legacy / negative check

| ID | Role | Pinned validator |
|----|------|------------------|
| `gen9vgc2025regma` | VGC-Bench log battle header only | **Reject** — `should be a 'Format', but was a 'Condition'` |
| `gen9vgc2025regmb` | VGC-Bench log battle header only | **Not defined** on pinned server (same class as `regma`) |
| `gen9notrealformat` | Control | **Reject** — unknown format |

These must **not** be used for gauntlet challenges, panel validation, or team curation.

## Validator probes (pinned `node pokemon-showdown validate-team`)

| Probe | Format ID | Exit | Result |
|-------|-----------|------|--------|
| Reg-I hero control | `gen9vgc2025regi` | 0 | `showdown_bot/teams/fixed_team.txt` validates (expected) |
| Reg-I hero on Champions | `gen9championsvgc2026regma` | 1 | Fails — SV species illegal in Champions dex (e.g. Flutter Mane, Rillaboom), Champions stat budget (66 total, max 32/stat), item/move pool mismatches |
| Minimal legal M-A team | `gen9championsvgc2026regma` | 0 | Pass (local probe only — **not committed**) |
| All four Champions IDs | `…regma`, `…regmabo3`, `…regmb`, `…regmbbo3` | 0 / 1 per team | Format recognized on all four; same probe team fails only on legality, not unknown format |
| Legacy bench ID | `gen9vgc2025regma` | crash | Not a Format |

**P0 gate:** format ID known and validator operational — **PASS**. Full mechanics table is **P1**
(fail-closed Reg-I rejection already demonstrated).

## Tier / battle-creation probe

Local sim (`dist/sim/battle`, pinned clone) with `formatid: gen9championsvgc2026regma`:

```
|gen|9
|tier|[Gen 9 Champions] VGC 2026 Reg M-A
```

Matches replay tier string. Gauntlet challenges use the same format ID string passed to
`/challenge …, <id>`; sim acceptance satisfies the spec’s battle-tier check without a live
ladder session in P0.

## Live vs pinned stability

| Check | Result |
|-------|--------|
| Four VGC names in live `formats.js` | Yes |
| Same names/mods/rulesets in pinned `formats.ts` | Yes |
| `validate-team` on pinned clone | Works for primary ID |
| ID namespace drift (`gen9champions…` vs hypothesis) | None — hypothesis confirmed |

Live server may be **ahead** of `f8ac140` on unrelated formats; for the four Champions VGC 2026
Reg M targets, **no drift observed** on 2026-07-14.

## PASS / NO-GO checklist (spec §3.3)

| Criterion | Status |
|-----------|--------|
| BO1 ID accepts battle creation | **PASS** (sim + replay) |
| `validate-team <id>` not unknown | **PASS** |
| Live vs pinned ID stable for targets | **PASS** |
| `\|tier\|` matches human name | **PASS** |
| VGC doubles exists (not debug-only) | **PASS** |

## Next steps (user-gated)

1. **Approve P1** — mechanics audit (Mega/Tera/restricted/dex/stat system) using primary ID.
2. **Approve team curation / panel v0** — all teams must pass `validate-team gen9championsvgc2026regma`
   with Champions spreads (66 stat-point budget, legal items/moves).
3. **Do not** use `gen9vgc2025regi`, `gen9vgc2025regma`, or VGC-Bench headers as format shortcuts.

## Artefacts

| File | Committed |
|------|-----------|
| `data/eval/champions-panel-v0/discovery/formats.js.snapshot` | Yes |
| `data/eval/champions-panel-v0/discovery/format-discovery-report.json` | Yes |
| `data/eval/champions-panel-v0/discovery/format-discovery-report.md` | Yes (this file) |
| `reports/champions-panel-v0-format-discovery.md` | Yes (verdict summary) |

Probe team paste used for validator exit-0 check: **local only, not committed** (per P0 scope).
