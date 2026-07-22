# Task 13 — VGCPastes source selection and contract amendment

**Status: PROPOSED — source-selection audit.** Records the owner-chosen replacement source for Task
13 and the evidence that it satisfies the source contract. No team artifact, no sealing, no gate.

**Why this exists.** The independent review of the Rutgers Scarlet Classic evidence
(`2026-07-22-gate-b-source-proof-independent-review.md`) returned **SOURCE-PROOF PASS** but
**Task 13 construction BLOCKED**, on one ground: that source's Open Team Sheet tier structurally
never publishes EVs or natures, so building playable teams from it required synthesizing them —
a step the pre-registered §2 contract did not authorize. Its open question Q1 asked whether
synthetic spreads should be permitted.

**Q1 is not answered "yes". It is made moot.** The project owner chose a different, fully complete
public source. Nothing is synthesized here, so the authority gap Q1 described does not arise.

---

## 1. Source and selection rule

| | |
|---|---|
| Repository | VGCPastes Repository (public, read-only) |
| Sheet | `https://docs.google.com/spreadsheets/d/1axlwmzPA49rYkqXh7zHvAtSP-TKbM0ijGYBPRflLSWw/edit?gid=417374305#gid=417374305` |
| Tab / GID | `Champions M-A Featured Teams` / `417374305` |
| Backing range | `IMPORTRANGE` of `Champions M-A Featured!A1:AS400` from sheet `1r6kYCyhnWbBbLfJrYEwB23sPayo2p9lFKil_ZKHlrYA` |
| Fetched | 2026-07-22, read-only, not signed in |

**Selection rule, fixed by the project owner before any paste was read for construction:**

> The first six entries, in table order, in the sheet "Champions M-A Featured Teams" with
> EVs = Yes, a reachable PokéPaste, six complete Pokémon, and declared format
> `gen9championsvgc2026regma`.

The six resulting team IDs were enumerated explicitly by the owner and **may not be substituted or
re-ordered** — in particular not after seeing species overlap or any bot behaviour.

**The rule was verified, not assumed.** The sheet's cell grid renders on canvas and is not
extractable as text, so the row order was confirmed through the sheet's own CSV export endpoint
(`/gviz/tq?tqx=out:csv&gid=417374305`). Rows 1–6 in table order are exactly PC1102, PC1101, PC1100,
PC1099, PC1098, PC1097, each with `EVs = Yes`. The seventh row (PC1096) also carries `EVs = Yes`,
which matters: the cut at six is the rule's own count, **not** an artifact of EV availability
running out. No row was skipped.

---

## 2. The six selected teams

All values below are the publisher's own. Frozen bytes in
`docs/projects/champions/audits/2026-07-22-task13-vgcpastes-source-evidence/`.

| # | Team ID | Placement | PokéPaste | Frozen file | SHA-256 (first 16) | Bytes |
|---|---|---|---|---|---|---|
| 1 | PC1102 | PJCS 2026 Champion 🥇 (Hiroshi Onishi) | `pokepast.es/c17e51b1dee42c8c` | `pc1102-paste.txt` | `5fd0fa4de8b29e57` | 937 |
| 2 | PC1101 | PJCS 2026 Champion, Seniors | `pokepast.es/1f7d6d16d171d672` | `pc1101-paste.txt` | `645fb9b20b7d8f81` | 934 |
| 3 | PC1100 | PJCS 2026 Runner-up 🥈 | `pokepast.es/34cb00fce368cd94` | `pc1100-paste.txt` | `702cfd156002f451` | 899 |
| 4 | PC1099 | PJCS 2026 Runner-up, Seniors | `pokepast.es/879641da13859e2f` | `pc1099-paste.txt` | `d0de3354333be1a2` | 908 |
| 5 | PC1098 | PJCS 2026 Top 4, Seniors | `pokepast.es/8bcfc47c2d206318` | `pc1098-paste.txt` | `cb6fec8dc63995a0` | 927 |
| 6 | PC1097 | PJCS 2026 Top 4, Seniors | `pokepast.es/25efa05b579532c4` | `pc1097-paste.txt` | `bb350a90ff9c0381` | 902 |

Full digests are in `sources.json`. Manifest verified in both directions: every registered file
exists with a matching digest and byte size; no unregistered file is present; all files are UTF-8,
LF-only, with a single trailing newline; no local path, username, or hostname appears anywhere in
the committed directory.

---

## 3. Completeness evidence (the point of the change)

Parsed programmatically from the frozen bytes, for all six teams:

| Property | Result |
|---|---|
| Pokémon per team | **6 / 6 / 6 / 6 / 6 / 6** |
| Held item on every Pokémon | ✅ 36/36 |
| Ability on every Pokémon | ✅ 36/36 |
| Level on every Pokémon | ✅ 36/36, all `Level: 50` |
| **EVs on every Pokémon** | ✅ **36/36** |
| **Nature on every Pokémon** | ✅ **36/36**, all valid nature names |
| Four moves on every Pokémon | ✅ 36/36 |
| EV total per Pokémon | ✅ exactly **66** on all 36 |
| EV maximum per stat | ✅ ≤ **32** on all 36 |

The EV budget matches `showdown_bot/config/formats/gen9championsvgc2026regma.yaml` exactly
(`kind: stat_points`, `total: 66`, `max_per_stat: 32`, `level: 50`) — an independent consistency
signal that these are genuine Champions-format spreads.

**No synthetic fields.** Species, item, ability, level, EVs, nature and all four moves are
transcribed unchanged from the published paste. There is no EV/nature synthesis rule in this path
and none is needed. The narrowing that the Rutgers path would have forced — "real
species/items/abilities/moves with synthetic spreads" — **does not apply here**.

---

## 4. Legality

`pokemon-showdown validate-team gen9championsvgc2026regma`, run against the pinned checkout at
`f8ac140` (`$HOME/.cache/showdownbot/pokemon-showdown`, node v24.16.0):

| Team | Exit code | Output |
|---|---|---|
| PC1102 | **0** | (empty) |
| PC1101 | **0** | (empty) |
| PC1100 | **0** | (empty) |
| PC1099 | **0** | (empty) |
| PC1098 | **0** | (empty) |
| PC1097 | **0** | (empty) |

This is the independent legality authority. It is deliberately **not** derived from
`speciesdata.json`/`itemdata.json` — finding H4 of the independent review noted those snapshots
self-declare `gen9vgc2024regg`, and `validate-team` reads neither.

---

## 5. Intra-holdout species overlap — audit information only

**This is not a gate and it did not influence the selection.** The six teams are owner-fixed; this
section exists so the property is visible rather than discovered later.

**PC1099 and PC1098 have an identical six-species set** — Aerodactyl, Charizard, Floette-Eternal,
Garchomp, Kingambit, Sneasler — while publishing **different complete sets**: different items
(PC1099 Kingambit @ Chople Berry vs PC1098 @ Black Glasses), different moves (PC1098's Kingambit
runs Swords Dance; PC1099's runs Iron Head), and entirely different EV spreads and several
different natures. They are the same species roster, not the same team.

Pairwise Jaccard over species sets:

| | PC1102 | PC1101 | PC1100 | PC1099 | PC1098 | PC1097 |
|---|---|---|---|---|---|---|
| **PC1102** | 1.000 | 0.500 | 0.000 | 0.500 | 0.500 | 0.000 |
| **PC1101** | 0.500 | 1.000 | 0.000 | 0.500 | 0.500 | 0.000 |
| **PC1100** | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 | 0.091 |
| **PC1099** | 0.500 | 0.500 | 0.000 | 1.000 | **1.000** | 0.000 |
| **PC1098** | 0.500 | 0.500 | 0.000 | 1.000 | **1.000** | 0.000 |
| **PC1097** | 0.000 | 0.000 | 0.091 | 0.000 | 0.000 | 1.000 |

### What the production guard actually does — stated precisely

`find_near_duplicate_flags` (Task 4), as wired in `combine_strength_holdout_arms`, compares **each
holdout team against the nine pinned existing Champions M-A reference teams only**. It does **not**
compare holdout teams against each other. **PC1099 is therefore not compared against PC1098 by the
gate**, and nothing in this audit should be read as claiming otherwise.

The gate contract is **not** extended here. Adding an intra-holdout comparison would be a
production-code and contract change; it is not made, not implied, and would need its own explicit
decision. The table above is recorded as audit information so that a later reader can see the
property without it silently becoming a verdict input.

---

## 6. Relationship to the prior Rutgers evidence

The Rutgers evidence set (`2026-07-21-task13-source-evidence/`) and its independent review are
**retained unchanged as history**. Their findings are not deleted or reinterpreted:

- its SOURCE-PROOF PASS stands for what it assessed;
- its BLOCKED verdict on construction stands and was correct;
- its Q1 is now **moot**, not answered — see the dated addendum appended to that review.

What changes is only which source Task 13 builds from.

---

## 7. Outstanding

Everything downstream of sourcing remains to be done and is listed in
`sources.json` `.not_yet_done`: canonical `.txt`/`.packed` artifacts, `seal_team` sealing, exact
hash disjointness against the frozen coverage set, the repo-wide leakage scan, the panel/holdout/
baseline manifests, and the CLI data wiring. No live server, battle, or gate is involved in any of
it.
