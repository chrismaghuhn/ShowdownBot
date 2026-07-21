# EV/Nature Synthesis Rule for Task 13 Holdout Teams

Frozen: 2026-07-21T18:22:00Z, before any Task 12 team file exists. Fixed at this point so it
cannot be adjusted after seeing battle results -- same discipline as the placement-selection
rule (plan sec 2 rule 2), applied to the same risk.

## Why this exists

The tournament's own Team Sheet Policy (see `user_supplied_full_rules_document` in
`sources.json`) defines two tiers: a Closed Team Sheet (exact Pokemon, moves, abilities, held
items, stat spreads, levels -- submitted to organizers) and an Open Team Sheet (Pokemon, moves,
abilities, held items -- published to opponents before each match). Every sheet frozen for this
holdout panel is Open-tier by the tournament's own design: EVs, Nature, and Level are
structurally never public for any placement. This was never an extraction gap on this evidence
set's side -- the Closed tier simply never becomes public for anyone.

Rule 1 already tolerates this ("natures/EVs where published"). But Task 12 still needs a
complete, legal team file per holdout Pokemon, so something has to fill the EV/Nature/Level gap.
This document is that something.

## What was considered and rejected

**`default_spreads.yaml`** (`showdown_bot/config/formats/meta/champions/default_spreads.yaml`):
rejected. Its own header states it is "Derived from committed hero + panel team pastes; hero
file wins on duplicate species" -- reverse-engineered from this project's own existing panel.
Checked programmatically against all six sourced holdout teams: 23 of 36 roster slots (63.9%)
have a species-specific entry in that file's `species:` table. Applying it would assign holdout
Pokemon the literal EV/Nature/item combination already used by an existing panel/hero Pokemon of
the same species, for the majority of the holdout roster. That is not species overlap (already
disclosed separately in `holdout_independence_limitation`) -- it would be build-level duplication
between holdout and panel Pokemon, undermining the property Gate B exists to test. The file's
generic `default:` block (non-species-keyed) was also considered and rejected: same file, same
header, same derivation -- diluted risk, not absent risk.

**Smogon Strategy Pokedex** (VGC 2026 Regulation M-A): checked as a comparison, not adopted as an
input. See "Smogon comparison" below for what was found and why it stayed a comparison.

## Input set (the only data this rule reads)

- `showdown_bot/config/species/speciesdata.json` -- `baseStats` only (hp/atk/def/spa/spd/spe)
- `showdown_bot/config/moves/movedata.json` -- `category` only (Physical/Special/Status)
- The already-sourced, already-legality-checked published sheet itself -- species/item/ability/
  moves, from `sources.json`'s `entries[]`/`replacement_entries[]`
- `showdown_bot/config/formats/gen9championsvgc2026regma.yaml` -- EV budget only (kind:
  stat_points, total: 66, max_per_stat: 32); Level 50 is format-fixed, not derived

No file derived from this project's own team data (`default_spreads.yaml`, `likely_sets.yaml`,
any panel/hero/coverage team file under `showdown_bot/teams/`) is read by this rule. Mega Stone
holders use their BASE form's `baseStats` -- the sheets already list species in pre-Mega form per
the tournament's own convention (see `mega_stone_ability_audit`), so no special-casing was
needed: `speciesdata.json[norm(sheet_species_name)]` is already the base form.

## Algorithm

For a species with base stats (hp, atk, def, spa, spd, spe) and its 4 published moves:

1. Count damaging moves among the 4 by `movedata.json` category: `phys = count(Physical)`,
   `spec = count(Special)`. `dmg = phys + spec`.
2. Archetype:
   - `dmg >= 2` -> **OFFENSE**
   - `dmg == 0` -> **BULK**
   - `dmg == 1` -> OFFENSE if `max(atk,spa) >= max(def,spd)`, else BULK (base-stat tiebreak; a
     single damaging move is too weak a signal alone)
3. If OFFENSE:
   - `primary = atk if phys >= spec else spa` (ties go to atk)
   - `unused` = the other of {atk, spa}
   - if `spe >= base_stat[primary]`: Nature boosts Spe, lowers `unused` (Jolly if primary=atk,
     Timid if primary=spa)
   - else: Nature boosts `primary`, lowers `unused` (Adamant if primary=atk, Modest if
     primary=spa)
   - EVs: `{primary: 32, spe: 32, hp: 2}`
4. If BULK:
   - `primary_bulk = def if def >= spd else spd`
   - `secondary_bulk` = the other of {def, spd}
   - `weaker_attack = atk if atk <= spa else spa` (nature lowers this -- the less useful attack
     stat)
   - Nature boosts `primary_bulk`, lowers `weaker_attack`: Bold (def/atk), Impish (def/spa),
     Calm (spd/atk), or Careful (spd/spa)
   - EVs: `{hp: 32, primary_bulk: 32, secondary_bulk: 2}`
5. Level: 50 for every Pokemon (format-fixed, not derived from this rule).

Deterministic: the same species + moveset always produces the same output. No per-team,
per-player, or per-placement branching, and no manual override.

## Disclosure scope

Species, held item, ability, and all four moves come from the real published sheet (already
legality-checked under rule 2). Level comes from the format. **Only EVs and Nature are
synthetic**, produced by the algorithm above -- not what the player actually ran, and not
claimed to be. Any Gate B verdict built on these teams must carry this scope: "independent
strength holdout against real tournament species/items/abilities/moves, with synthetic,
mechanically-derived EVs and Natures" -- not "against the teams these players actually played."

## Known limitations (disclosed, not corrected after the fact)

A prior version of this document (before the Smogon comparison below) was already fixed at this
algorithm. Comparing its output against Smogon's published VGC 2026 Regulation M-A sets afterward
surfaced real, systematic misses. They are recorded here, not patched into the algorithm above --
adjusting the rule now, having seen this comparison, would be the same discipline violation as
re-ordering team selection after seeing standings, just with Smogon's answer standing in for a
battle outcome.

- **Kingambit**: real builds invest zero Speed (Smogon: 32 HP / 32 Atk / 2 Def) -- base 50 Spe is
  low enough that real play leans into being slow rather than chasing a losing speed tier. This
  rule mechanically maxes Speed on every OFFENSE call regardless, producing 2 HP / 32 Atk / 32
  Spe instead.
- **Incineroar** and **Scovillain**: both are real bulky-support/pivot Pokemon (Intimidate +
  Fake Out + Parting Shot; Rage Powder redirection) despite having 2+ nominally "damaging" moves
  in their kit -- enough to trip this rule's `dmg >= 2` threshold into OFFENSE. A utility move
  that happens to carry base power (Fake Out, a lure Overheat) reads as offense signal to a
  move-counting rule but functions as support in practice.
- **Archaludon**: Smogon's real spread pairs a Modest nature with an almost entirely bulk-invested
  EV spread (32 HP / 25 SpD, only 5 SpA) -- optimizing a small nature bonus onto a fundamentally
  defensive build. This rule's binary offense/bulk split cannot express that combination; it
  produces a fully offense-invested 2 HP / 32 SpA / 32 Spe instead.

These are accepted as the cost of a mechanical, non-panel-derived rule, per the framing already
established for this decision: holdout teams are the environment both arms play against, not the
measurement itself, so a spread that diverges from real play does not bias candidate vs. baseline
-- it only narrows external validity ("strength against real tournament teams" reads more
precisely as "against real tournament species/items/abilities/moves with synthetic spreads"),
which the Disclosure scope above already states plainly.

## Smogon comparison (informational only -- not an input to this rule)

Checked against Smogon's Strategy Pokedex, VGC 2026 Regulation M-A
(`https://www.smogon.com/dex/champions/pokemon/<species>/vgc-2026-regulation-m-a/`), for all 21
unique species across the six holdout teams, fetched 2026-07-21.

Coverage: 14/21 species have a real VGC 2026 Regulation M-A set published. 3/21
(Pelipper, Aegislash, Lopunny) have no M-A page -- the URL falls back to an unrelated OU/Battle
Stadium Singles page. 4/21 (Sinistcha, both formes; Ninetales-Alola; Arcanine-Hisui; Lucario)
have no published analysis for any format ("No movesets available").

Of the 14 checkable species: 5 matched this rule's output closely on both nature and EV shape
(Sneasler, Basculegion, Aerodactyl, Floette-Eternal, Rotom-Wash -- though Rotom-Wash matched
Smogon's second of two listed sets, not its first). 5 partially matched (archetype or nature
right, exact EV split different: Charizard, Gengar, Whimsicott, Sableye, Garchomp). 4 were clear
archetype-level misses, listed under Known limitations above. 5 of the 14 checkable species list
2 or more competing named sets (Basculegion x3, Rotom-Wash x2, Charizard x3 incl. alt spreads,
Gengar x2, Whimsicott x3 incl. alt spreads) -- adopting Smogon values directly would still require
an undocumented per-species choice among them, the exact judgment-call risk this rule exists to
avoid.

This comparison is recorded for anyone auditing this rule later. It is evidence that the rule's
failure modes are real and identifiable, not evidence used to change the rule.

## Computed output (as of this freeze)

Species, item, and ability are transcribed from the already-frozen export sheets
(`sources.json` `entries[]`/`replacement_entries[]`) for cross-reference only; EVs and Nature are
this rule's output. Level 50 for all (not shown per-row; format-fixed).

### Place 2 -- William Brown / wb_vg

| Species | Item | Ability | Archetype | Nature | EVs |
|---|---|---|---|---|---|
| Archaludon | Leftovers | Stamina | OFFENSE | Modest | 2 HP / 32 SPA / 32 SPE |
| Sneasler | White Herb | Unburden | OFFENSE | Adamant | 2 HP / 32 ATK / 32 SPE |
| Pelipper | Sitrus Berry | Drizzle | OFFENSE | Modest | 2 HP / 32 SPA / 32 SPE |
| Scovillain | Scovillainite | Moody | OFFENSE | Modest | 2 HP / 32 SPA / 32 SPE |
| Basculegion | Choice Scarf | Adaptability | OFFENSE | Adamant | 2 HP / 32 ATK / 32 SPE |
| Sableye | Roseli Berry | Prankster | BULK | Impish | 32 HP / 32 DEF / 2 SPD |

### Place 3 -- Nicholas Morales / charmdi

| Species | Item | Ability | Archetype | Nature | EVs |
|---|---|---|---|---|---|
| Aerodactyl | Focus Sash | Unnerve | OFFENSE | Jolly | 2 HP / 32 ATK / 32 SPE |
| Floette-Eternal | Floettite | Flower Veil | OFFENSE | Modest | 2 HP / 32 SPA / 32 SPE |
| Kingambit | Chople Berry | Defiant | OFFENSE | Adamant | 2 HP / 32 ATK / 32 SPE |
| Garchomp | Dragon Fang | Rough Skin | OFFENSE | Adamant | 2 HP / 32 ATK / 32 SPE |
| Sinistcha | Kasib Berry | Hospitality | OFFENSE | Modest | 2 HP / 32 SPA / 32 SPE |
| Charizard | Charizardite Y | Blaze | OFFENSE | Modest | 2 HP / 32 SPA / 32 SPE |

### Place 5 -- Chris Han / darts

| Species | Item | Ability | Archetype | Nature | EVs |
|---|---|---|---|---|---|
| Aegislash | Colbur Berry | Stance Change | OFFENSE | Jolly | 2 HP / 32 ATK / 32 SPE |
| Rotom-Wash | Sitrus Berry | Levitate | OFFENSE | Modest | 2 HP / 32 SPA / 32 SPE |
| Gengar | Gengarite | Cursed Body | OFFENSE | Modest | 2 HP / 32 SPA / 32 SPE |
| Garchomp | Choice Scarf | Rough Skin | OFFENSE | Adamant | 2 HP / 32 ATK / 32 SPE |
| Ninetales-Alola | Focus Sash | Snow Warning | OFFENSE | Timid | 2 HP / 32 SPA / 32 SPE |
| Incineroar | Shuca Berry | Intimidate | OFFENSE | Adamant | 2 HP / 32 ATK / 32 SPE |

### Place 6 -- Thaison Hughes / charismaacheck

| Species | Item | Ability | Archetype | Nature | EVs |
|---|---|---|---|---|---|
| Scovillain | Scovillainite | Moody | OFFENSE | Modest | 2 HP / 32 SPA / 32 SPE |
| Aerodactyl | Aerodactylite | Unnerve | OFFENSE | Jolly | 2 HP / 32 ATK / 32 SPE |
| Sneasler | White Herb | Unburden | OFFENSE | Adamant | 2 HP / 32 ATK / 32 SPE |
| Basculegion | Choice Scarf | Adaptability | OFFENSE | Adamant | 2 HP / 32 ATK / 32 SPE |
| Pelipper | Sitrus Berry | Drizzle | OFFENSE | Modest | 2 HP / 32 SPA / 32 SPE |
| Archaludon | Leftovers | Stamina | OFFENSE | Modest | 2 HP / 32 SPA / 32 SPE |

### Place 7 -- Rob McNeilly / rovbmc

| Species | Item | Ability | Archetype | Nature | EVs |
|---|---|---|---|---|---|
| Lopunny | Lopunnite | Limber | OFFENSE | Jolly | 2 HP / 32 ATK / 32 SPE |
| Floette-Eternal | Floettite | Flower Veil | OFFENSE | Modest | 2 HP / 32 SPA / 32 SPE |
| Arcanine-Hisui | Chople Berry | Intimidate | OFFENSE | Adamant | 2 HP / 32 ATK / 32 SPE |
| Whimsicott | Fairy Feather | Prankster | BULK | Bold | 32 HP / 32 DEF / 2 SPD |
| Basculegion | Choice Scarf | Adaptability | OFFENSE | Adamant | 2 HP / 32 ATK / 32 SPE |
| Aegislash | Focus Sash | Stance Change | OFFENSE | Jolly | 2 HP / 32 ATK / 32 SPE |

### Place 8 -- Joshua Robinson / quivern

| Species | Item | Ability | Archetype | Nature | EVs |
|---|---|---|---|---|---|
| Whimsicott | Focus Sash | Prankster | BULK | Bold | 32 HP / 32 DEF / 2 SPD |
| Charizard | Charizardite Y | Solar Power | OFFENSE | Modest | 2 HP / 32 SPA / 32 SPE |
| Basculegion | Choice Scarf | Adaptability | OFFENSE | Adamant | 2 HP / 32 ATK / 32 SPE |
| Lucario | Lucarionite | Inner Focus | OFFENSE | Adamant | 2 HP / 32 ATK / 32 SPE |
| Garchomp | White Herb | Rough Skin | OFFENSE | Adamant | 2 HP / 32 ATK / 32 SPE |
| Kingambit | Black Glasses | Defiant | OFFENSE | Adamant | 2 HP / 32 ATK / 32 SPE |
