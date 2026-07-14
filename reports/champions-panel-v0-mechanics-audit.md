# Champions Panel v0 — P1 Mechanics Audit

**Date:** 2026-07-14  
**Verdict:** **PASS**  
**Format:** `gen9championsvgc2026regma` — `[Gen 9 Champions] VGC 2026 Reg M-A`  
**Pinned Showdown:** `f8ac140` (`~/.cache/showdownbot/pokemon-showdown`)  
**Spec:** `docs/superpowers/specs/2026-07-14-champions-panel-v0-design.md` §4  
**P0:** `reports/champions-panel-v0-format-discovery.md` (PASS)

## Summary

Champions M-A on the pinned server is a **distinct ruleset** from our current Reg-I target
(`gen9vgc2025regi`). Mega Evolution is active; Terastallize is not. Teams use **Stat Points**
(66 total, 32 max per stat, all IVs 31), not VGC EV spreads. Flat Rules ban **all** Restricted
Legendaries and Mythicals (stricter than Reg-I’s one-restricted allowance). The Showdown validator
rejects Reg-I `fixed_team.txt` as expected and accepts a minimal Champions-formatted probe team.

**Team curation may be considered for approval** — this audit does not start curation.

## Ruleset (pinned `config/formats.ts` + mod chain)

| Field | Value |
|-------|-------|
| **Machine ID** | `gen9championsvgc2026regma` |
| **Mod** | `championsregma` → inherits `champions` |
| **gameType** | `doubles` |
| **Declared ruleset** | `Flat Rules`, `VGC Timer`, `Open Team Sheets` |
| **searchShow** | `false` (manual/challenge format — expected) |

### Flat Rules expansion (Champions mod)

From `data/mods/champions/rulesets.ts` + base `flatrules`:

- Level 50, Species Clause, Item Clause = 1, Team Preview, Cancel Mod
- **Banlist:** `Mythical`, `Restricted Legendary` (no restricted slot — unlike Reg-I)
- Bring 6, pick 4 (auto for doubles via `Picked Team Size = Auto`)

### Stat system (Champions-specific)

Source: `sim/dex-formats.ts` (`evlimit=Auto` + `mod.startsWith('champions')` → **66**),
`sim/team-validator.ts` (`useStatPoints = dex.currentMod.startsWith('champions')`):

| Rule | Champions M-A | Reg-I (`gen9vgc2025regi`) |
|------|---------------|---------------------------|
| Investment unit | **Stat Points** (field still named `EVs:` in paste) | EVs (508/510 typical) |
| Total budget | **66** | 510 |
| Per-stat cap | **32** | 252 |
| IV requirement | **All 31** | Flexible (bottle cap rules) |
| Stat formula | `stat + points + 20` (+ nature) — see `mods/champions/scripts.ts` | Standard Gen 9 |

Validator probes confirm:

- 508-point Reg-I spread → *“508 total Stat Points … limit of 66”*
- 33 in one stat → *“more than 32 Stat Points in HP”*
- Valid 32/32/2 spread on six species → **exit 0**

## Mega vs Tera

| Mechanic | Champions M-A | Evidence |
|----------|---------------|----------|
| **Mega Evolution** | **On** | `mods/champions/scripts.ts::actions.canMegaEvo`; sim: Charizard + Charizardite Y → `canMegaEvo: "Charizard-Mega-Y"`; validator accepts mega stone team |
| **Terastallize** | **Off** | `actions.canTerastallize()` returns `null`; validator deletes `teraType` for champions mods; sim: `canTerastallize: null` on Incineroar; paste `Tera Type:` line does not fail validation (ignored) |

**Bot implication (document only — no code change in P1):** our Reg-I path assumes `tera: true` in
`gen9vgc2025regi.yaml` and has no Mega handling. FormatConfig for Champions remains a **blocker**
for decision-quality eval (spec §8.2); not a blocker for this mechanics audit.

## Dex / species / items / moves (validator probes)

Artifact: `data/eval/champions-panel-v0/mechanics/validator-probes.json`

| Probe | Expected | Exit | Key message |
|-------|----------|------|-------------|
| `fixed_team.txt` @ Reg-I | pass | 0 | — |
| `fixed_team.txt` @ Champions | **fail** | 1 | SV species illegal, 508>66, Knock Off, Covert Cloak, etc. |
| Miraidon + Koraidon team | fail | 1 | *Restricted Legendary, banned by Flat Rules* |
| Flutter Mane | fail | 1 | *does not exist in Gen 9* (Champions dex) |
| Covert Cloak on Whimsicott | fail | 1 | *item … does not exist in Gen 9* |
| Knock Off on Incineroar | fail | 1 | *can't learn Knock Off* |
| Minimal legal probe (local) | pass | 0 | — (not committed) |
| Charizard-Mega-Y + stone | pass | 0 | Mega legal |
| Paste with `Tera Type:` | pass | 0 | Tera line ignored |

Champions uses a **curated Gen 9 dex** (`data/mods/championsregma/formats-data.ts` + champions
learnsets/items). Many SV Reg-I staples are absent or have different move/item pools.

## Our `FormatConfig` gap

| | Reg-I (exists) | Champions (missing) |
|--|----------------|---------------------|
| File | `showdown_bot/config/formats/gen9vgc2025regi.yaml` | **None** |
| `tera` | `true` | should be `false` when added |
| `restricted_limit` | `2` | N/A — Flat Rules hard-bans restricted |
| Meta paths | default_spreads, priors, likely_sets | **TBD** — separate Champions meta or empty degrade |

P1 documents the gap; **does not** add yaml (non-goal).

## Reg-I vs Champions — decision-relevant deltas

```
Reg-I panel teams / fixed_team.txt  ──✗──►  Champions validator (expected fail)
Champions Stat-Point spreads        ──✗──►  Reg-I EV validator (would fail if tried)
VGC-Bench log IDs (gen9vgc2025regma) ──✗──►  Live validator/challenge (P0 confirmed)
```

## PASS / NO-GO (spec §4)

| Criterion | Status |
|-----------|--------|
| Ruleset documented from pinned Showdown | **PASS** |
| Mega availability clarified | **PASS** — on |
| Tera availability clarified | **PASS** — off |
| Stat budget 66/32 verified | **PASS** |
| Restricted/dex/items/moves probed | **PASS** |
| `fixed_team.txt` fails Champions | **PASS** |
| Minimal legal probe passes locally | **PASS** (not committed) |

## Next gate (user approval required)

- **Team curation / panel v0** — only after explicit go-ahead.
- Curation must use: `validate-team gen9championsvgc2026regma`, Stat Points (66/32), Champions-legal
  species/items/moves, no `@Tera Type`, mega stones where intended.
- **Still not started:** `panel_champions_v0.yaml`, schedules, gauntlet smoke, bot code.

## Non-goals confirmed

No team files committed, no panel YAML, no schedule, no gauntlet run, no bot changes, no strength
claim.
