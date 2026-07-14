# Champions Panel v0 — Team Provenance

P2 team curation only. No panel YAML, schedule, or strength claims.

**Format ID:** `gen9championsvgc2026regma`  
**Pinned Showdown:** `~/.cache/showdownbot/pokemon-showdown` @ `f8ac140`  
**Access date:** 2026-07-14  
**Stat budget:** 66 total Stat Points, max 32 per stat (Champions; `@Tera Type` omitted)

### Fidelity labels (read before citing these teams)

| Label | Meaning |
|-------|---------|
| **tournament-exact** | Six species, moves, items, abilities match a single cited Limitless teamlist; only Champions Stat Point spreads (and Showdown move-name normalization) differ. |
| **composite — NOT tournament-exact** | Validated roster assembled from multiple cited sources and/or deliberate species swaps. **Do not cite as a top-cut or single-player paste.** |
| **synthetic — NOT tournament-exact** | Panel-designed roster inspired by an archetype; species/items/moves differ materially from any one cited paste. |

**Validator (per team):**

```bash
cd showdown_bot
Get-Content teams/<path>.txt -Raw | node ~/.cache/showdownbot/pokemon-showdown/pokemon-showdown validate-team gen9championsvgc2026regma
# exit 0 required; all six teams pass as of access date
```

**Pack (panel convention; P3 must verify reproducibility):**

```bash
cd showdown_bot
Get-Content teams/<path>.txt -Raw | node ~/.cache/showdownbot/pokemon-showdown/pokemon-showdown pack-team > teams/<path>.packed
```

Committed `.packed` files are derived artefacts. P3 panel freeze must include a repro check: `pack-team` output matches committed `.packed` for every team path.

---

## Hero — `fixed_champions_v0`

| Field | Value |
|-------|-------|
| `team_id` | `hero_champions_v0` |
| `team_path` | `teams/fixed_champions_v0.txt` |
| `fidelity` | **tournament-exact** |
| `archetype` | flexible offense (mega support + scarf water + priority) |
| `source` | [Limitless — Andrea C, Crown Fight Bo3 #66](https://play.limitlesstcg.com/tournament/69c31fd3d478313a15a321be/player/andrevgc/teamlist) |
| `source_date` | 2026-07-14 |
| `format_id` | `gen9championsvgc2026regma` |
| `validation_exit` | `0` |
| `team_hash` | `1d3a4cf5a4042532` |
| `notes` | Roster matches source moves/items/abilities. Added Champions Stat Point spreads (32/32/2). Fixed move name `Last Respects` (source: `Last Respect`). **Mega stones (documented):** Scovillainite, Aerodactylite. |

---

## Panel — `goodstuff`

> **⚠ composite — NOT tournament-exact.** This is a validated balance/goodstuff *archetype slot* for panel v0, **not** any player's Crown Fight #66 teamlist and **not** a top-cut paste. Sources below are reference only.

| Field | Value |
|-------|-------|
| `team_id` | `goodstuff` |
| `team_path` | `teams/panel_champions_v0/goodstuff.txt` |
| `fidelity` | **composite — NOT tournament-exact** |
| `archetype` | balance / goodstuff |
| `source` | Reference only: [Vanilla0731](https://play.limitlesstcg.com/tournament/69c31fd3d478313a15a321be/player/vanilla0731/teamlist) (Delphox/Kingambit/Sneasler core); [TheBardo](https://play.limitlesstcg.com/tournament/69c31fd3d478313a15a321be/player/thebardo/teamlist) (Incineroar + Haban Garchomp pattern) |
| `source_date` | 2026-07-14 |
| `format_id` | `gen9championsvgc2026regma` |
| `validation_exit` | `0` |
| `team_hash` | `0054b6894af7215a` |
| `notes` | **Panel assembly, not a tournament export.** Borrowed pieces: Delphoxite Delphox, Kingambit, Sneasler from Vanilla0731; Garchomp moveset with Haban Berry from TheBardo; Incineroar moves from TheBardo. **Deliberate swaps vs either single source:** Tsareena → Incineroar; Aerodactyl → Rotom-Wash; Garchomp item/moveset hybrid. Added Stat Point spreads. **Mega stone:** Delphoxite only. No claim of meta prevalence or event placement for this exact six. |

---

## Panel — `tailwind_offense`

| Field | Value |
|-------|-------|
| `team_id` | `tailwind_offense` |
| `team_path` | `teams/panel_champions_v0/tailwind_offense.txt` |
| `fidelity` | **tournament-exact** |
| `archetype` | Tailwind offense |
| `source` | [Limitless — BatCoach, Crown Fight Bo3 #66](https://play.limitlesstcg.com/tournament/69c31fd3d478313a15a321be/player/batcoach/teamlist) |
| `source_date` | 2026-07-14 |
| `format_id` | `gen9championsvgc2026regma` |
| `validation_exit` | `0` |
| `team_hash` | `ea99dd840d0adce2` |
| `notes` | Matches source roster; Talonflame intentionally **no item** (Acrobatics set). Added Stat Point spreads. **Mega stone:** Froslassite. |

---

## Panel — `trick_room`

| Field | Value |
|-------|-------|
| `team_id` | `trick_room` |
| `team_path` | `teams/panel_champions_v0/trick_room.txt` |
| `fidelity` | **tournament-exact** |
| `archetype` | Trick Room |
| `source` | [Limitless — Dodi90, Crown Fight Bo3 #66](https://play.limitlesstcg.com/tournament/69c31fd3d478313a15a321be/player/dodi90/teamlist) |
| `source_date` | 2026-07-14 |
| `format_id` | `gen9championsvgc2026regma` |
| `validation_exit` | `0` |
| `team_hash` | `64ecc8fb2e6da7f1` |
| `notes` | Roster matches source moves/items/abilities (including Gyarados `Helping Hand`). Added Stat Point spreads. **Mega stone:** Tyranitarite. |

---

## Panel — `rain_offense`

| Field | Value |
|-------|-------|
| `team_id` | `rain_offense` |
| `team_path` | `teams/panel_champions_v0/rain_offense.txt` |
| `fidelity` | **tournament-exact** |
| `archetype` | rain / weather offense |
| `source` | [Limitless — Furnoz, Crown Fight Bo3 #66](https://play.limitlesstcg.com/tournament/69c31fd3d478313a15a321be/player/furnoz/teamlist) |
| `source_date` | 2026-07-14 |
| `format_id` | `gen9championsvgc2026regma` |
| `validation_exit` | `0` |
| `team_hash` | `e0c96fa0cabf1def` |
| `notes` | Roster matches source moves/items/abilities. Added Stat Point spreads. **Mega stone:** Meganiumite. |

---

## Panel — `disruption`

| Field | Value |
|-------|-------|
| `team_id` | `disruption` |
| `team_path` | `teams/panel_champions_v0/disruption.txt` |
| `fidelity` | **tournament-exact** |
| `archetype` | disruption / bulky control |
| `source` | [Limitless — scoseb, Crown Fight Bo3 #66](https://play.limitlesstcg.com/tournament/69c31fd3d478313a15a321be/player/scoseb/teamlist) |
| `source_date` | 2026-07-14 |
| `format_id` | `gen9championsvgc2026regma` |
| `validation_exit` | `0` |
| `team_hash` | `7b568b09f44b20fd` |
| `notes` | **Replaced an earlier synthetic v0 draft** (Sableye + Incineroar stress slot) with this tournament-exact scoseb paste after validation probe. Roster matches source moves/items/abilities; only Stat Point spreads added. **Mega stone:** Lucarionite. scoseb is a real Crown Fight #66 entry — still no strength claim for panel v0. |

---

## P2 gate summary

| Team | Fidelity | `validate-team` exit | `team_hash` |
|------|----------|---------------------|-------------|
| `fixed_champions_v0.txt` | tournament-exact | 0 | `1d3a4cf5a4042532` |
| `goodstuff.txt` | **composite — NOT tournament-exact** | 0 | `0054b6894af7215a` |
| `tailwind_offense.txt` | tournament-exact | 0 | `ea99dd840d0adce2` |
| `trick_room.txt` | tournament-exact | 0 | `64ecc8fb2e6da7f1` |
| `rain_offense.txt` | tournament-exact | 0 | `e0c96fa0cabf1def` |
| `disruption.txt` | tournament-exact | 0 | `7b568b09f44b20fd` |

**Not in scope (P2 non-goals):** `panel_champions_v0.yaml`, schedules, gauntlet smoke, bot code, strength claims, VGC-Bench/HolidayOugi downloads. Champions `FormatConfig` and Mega-readiness remain separate gates before strength/decision-quality runs.

**P3 dependency:** `.packed` must reproduce from `.txt` via `pack-team` (see command above).
