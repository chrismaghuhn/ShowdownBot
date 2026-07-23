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

**The rule was verified, and the proof is frozen.** The sheet's cell grid renders on canvas and is
not extractable as text, so the row order rests on the sheet's own CSV export
(`/gviz/tq?tqx=out:csv&gid=417374305`). That export is now frozen in the evidence directory as
`selection-source-export.csv` (SHA-256 `270bd0d919a6fde7…`, 178 666 bytes, 331 CSV rows), so the
selection is reproducible from the evidence tree alone rather than from a URL that may change.

Re-parsing it (`csv.reader`; real header at row index 2, since rows 0–1 are sheet preamble; data
rows are those with a non-empty `Team ID`, in file order) yields rows 1–6 as exactly PC1102,
PC1101, PC1100, PC1099, PC1098, PC1097, each with `EVs = Yes` and the exact PokéPaste URLs frozen
here. The seventh row (PC1096) also carries `EVs = Yes` — the cut at six is the rule's own count,
**not** the point at which EV data runs out. No row was skipped.

**Provenance of that file, stated plainly:** the browser tool was denied navigation to the
docs.google.com CSV endpoint, so the export was downloaded by the project owner and supplied
locally, then frozen unmodified. It is therefore *not* agent-fetched. It is, however,
independently corroborated: before it was supplied, this agent fetched the same endpoint read-only
and observed the same ordering of the first seven `EVs = Yes` rows. That earlier fetch returned a
model-rendered simplification of the CSV rather than its bytes — the frozen file is the authority
for column names and values, and re-parsing it is what corrected the placement wording below.

---

## 2. The six selected teams

All values below are the publisher's own. Frozen bytes in
`docs/projects/champions/audits/2026-07-22-task13-vgcpastes-source-evidence/`.

Placement columns below are copied verbatim from the frozen CSV (`Rank`, `Tournament / Event`,
`Full Name`). The sheet has **no** "Placement" column: an earlier revision of this audit carried
strings like "1st place (gold), Masters", which were an artifact of the model-rendered CSV reading
and have been corrected against the real bytes.

| # | Team ID | `Rank` | `Tournament / Event` | `Full Name` | PokéPaste | Frozen file | SHA-256 (first 16) | Bytes |
|---|---|---|---|---|---|---|---|---|
| 1 | PC1102 | Champion | PJCS 2026 | Hiroshi Onishi | `pokepast.es/c17e51b1dee42c8c` | `pc1102-paste.txt` | `5fd0fa4de8b29e57` | 937 |
| 2 | PC1101 | Champion (Seniors) | PJCS 2026 | ryu_poke197 | `pokepast.es/1f7d6d16d171d672` | `pc1101-paste.txt` | `645fb9b20b7d8f81` | 934 |
| 3 | PC1100 | Runner Up | PJCS 2026 | alaninepoke | `pokepast.es/34cb00fce368cd94` | `pc1100-paste.txt` | `702cfd156002f451` | 899 |
| 4 | PC1099 | Runner Up (Seniors) | PJCS 2026 | vdmd8olfjy68698 | `pokepast.es/879641da13859e2f` | `pc1099-paste.txt` | `d0de3354333be1a2` | 908 |
| 5 | PC1098 | Top 4 (Seniors) | PJCS 2026 | hiyu000000 | `pokepast.es/8bcfc47c2d206318` | `pc1098-paste.txt` | `cb6fec8dc63995a0` | 927 |
| 6 | PC1097 | Top 4 (Seniors) | PJCS 2026 | nm_k_ | `pokepast.es/25efa05b579532c4` | `pc1097-paste.txt` | `bb350a90ff9c0381` | 902 |

Full digests are in `sources.json`. Manifest verified in both directions: every registered file
exists with a matching digest and byte size, and no unregistered file is present.

Two properties are scoped deliberately, because they do not hold uniformly across the directory:

- **UTF-8, LF-only, single trailing newline** — verified for the six `.txt` pastes, the format
  declarations file, and `sources.json`. The frozen `selection-source-export.csv` is exempt: it is
  a third-party export frozen exactly as served, and normalizing it would defeat the point of
  freezing it. (It happens to contain no CR bytes, but it is not held to this rule.)
- **No local path, username, or hostname** — verified across *all* files in the directory,
  including the CSV. An earlier revision of this audit asserted this for "the committed directory"
  while the check had actually skipped the CSV; the CSV has since been scanned explicitly for
  Windows drive paths, `/Users/`, the operator's username, `Downloads`, `AppData`, `localhost`,
  loopback addresses and e-mail addresses — zero hits for each.

**On "frozen": these `.txt` files are normalized, not byte-identical to the served response.**
Per-line trailing whitespace (a renderer artifact of the text extraction) was stripped, and the
files are written UTF-8/LF with a single trailing newline. No Pokémon, field, value or ordering was
altered. The SHA-256 values are digests of *these normalized files* — the artifact this evidence
tree tracks — and must not be cited as digests of the upstream HTTP response body.

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
transcribed unchanged from the published paste — "unchanged" meaning no value was added, removed,
substituted or reordered; see the normalization note in §2 for the whitespace/line-ending handling
that the digests cover. There is no EV/nature synthesis rule in this path
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

**Declared format, frozen separately from legality.** The selection rule also requires the source
to *declare* `gen9championsvgc2026regma`. The `/raw` endpoint carries only team text, so that
declaration is captured from each paste's own metadata block and frozen as
`paste-format-declarations.txt`: all six declare it. Five pastes were uploaded by the "VGCPastes"
account and PC1098 by "Guest 20026542" — recorded as observed; it changes neither the selection
(which keys on the sheet row) nor legality. What the source *declares* and what `validate-team`
*decides* are kept as two separate claims.

This is the independent legality authority. It is deliberately **not** derived from
`speciesdata.json`/`itemdata.json` — finding H4 of the independent review noted those snapshots
self-declare `gen9vgc2024regg`, and `validate-team` reads neither.

---

## 4a. Blindness attestation (APPROVED spec §3.4)

**The six teams were selected blind to this bot's results.** Stated positively, as the spec
requires independence to be a verifiable property rather than an absence of evidence:

- The selection rule is **positional and mechanical** — the first six table-order entries meeting
  fixed predicates — and was fixed and enumerated by the project owner **before any paste was read
  for construction**.
- **No bot result existed for any of these teams at selection time**, and none was consulted: no
  win rate, no cell exposure, no coverage outcome, no Gate B verdict. Nothing was chosen, kept,
  dropped, or re-ordered because of how the bot performs against it.
- **The claim is checkable without trusting the selector.** Re-running the documented parse over
  `selection-source-export.csv` reproduces the same six IDs in the same order, with no reference to
  any bot artifact. Independence therefore does not rest on assurance.

**What this does not claim:** it is not a claim of archetype-disjointness from the existing panel,
nor that the six are unlike teams the bot was tuned against. That is a separate, narrower property.
Exact hash disjointness and the reference near-duplicate flags are computed later, in Task 13
step 3, and are reported there.

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

## 5a. Reference near-duplicate flags — Task 13 step 3 (the production guard's real run)

**This is the diagnostic §4a/§7 deferred to step 3.** It is the guard the gate actually runs:
`find_near_duplicate_flags` (Task 4), as wired in `combine_strength_holdout_arms`, comparing **each
of the six sealed holdout teams against exactly the nine pinned reference teams**
(`CANONICAL_REFERENCE_TEAM_PATHS`: the five `panel_champions_v0` teams + the four
`panel_champions_coverage_v0` foes), species derived from each team's **real sealed `.packed`** via
`load_team_species`. It is **diagnostic only** — a flag is a normal return value, never an auto-FAIL
and never a leakage finding (exact-identity leakage and hash-disjointness are separately clean,
§7). Threshold: Jaccard `>= 0.5` (inclusive), unchanged from Task 4. Teams are referenced here by
their public selection index (§2); the internal operational IDs live only in the allowlisted panel/
manifest/baseline, never in this file.

Reproduced by `showdown_bot/tests/test_strength_holdout_freeze.py::
test_reference_near_duplicate_audit_is_reproducible_and_diagnostic`.

**Result: six flags across three teams, every one exactly at the 0.5 threshold edge.**

| Holdout (sel. #) | Flagged reference | Jaccard | Shared species (4 of 6) |
|---|---|---|---|
| #2 (PC1101) | `cov_foe_both` | 0.500 | Aerodactyl, Basculegion, Garchomp, Kingambit |
| #2 (PC1101) | `cov_foe_tie` | 0.500 | Aerodactyl, Basculegion, Garchomp, Kingambit |
| #4 (PC1099) | `cov_foe_both` | 0.500 | Aerodactyl, Garchomp, Kingambit, Sneasler |
| #4 (PC1099) | `cov_foe_tie` | 0.500 | Aerodactyl, Garchomp, Kingambit, Sneasler |
| #5 (PC1098) | `cov_foe_both` | 0.500 | Aerodactyl, Garchomp, Kingambit, Sneasler |
| #5 (PC1098) | `cov_foe_tie` | 0.500 | Aerodactyl, Garchomp, Kingambit, Sneasler |

Teams #1 (PC1102), #3 (PC1100) and #6 (PC1097) produce **no** flag against any reference.

**Disposition — dismissed as coincidental format-staple overlap (DESIGN sec 3.3), recorded before
proceeding:**

- **Every flag is at exactly 0.5 — the inclusive boundary, never above it.** For two six-species
  teams, Jaccard `>= 0.5` needs 4 of 6 shared; each flag shares exactly 4, and every shared name is
  a ubiquitous `gen9championsvgc2026regma` staple (Garchomp, Kingambit, Aerodactyl, Basculegion,
  Sneasler). None shares a distinctive 5- or 6-Pokémon core, which is what a genuine near-duplicate
  would show.
- **Every flag is against an engineered `cov_foe_*` COVERAGE team, never a `panel_champions_v0`
  dev/held-out team.** The coverage foes were purpose-built (spec §2.4) to stack Mega-capable
  staples so they force the opponent-Mega cells; overlap with them at the staple level is expected
  and says nothing about the holdout team's provenance. The holdout set does **not** near-duplicate
  the development panel at all.
- **The holdout teams are published PJCS 2026 tournament teams (§2), selection-blind (§4a) and
  sealed before first bot contact.** They cannot be, and were not, derived from or tuned against the
  coverage foes; the firewall (spec §3.4/D-3) is intact.
- The selection is **owner-fixed and may not be re-ordered** (§1); this disposition records the
  property for manual awareness, exactly as DESIGN sec 3.3 requires, and does not (and could not)
  change the team set. No flag is escalated.

The gate contract is **not** changed here: no intra-holdout comparison is added (that remains
audit-only, §5), and the threshold and reference set are unchanged.

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

Everything downstream of sourcing has now been done, offline, across Task 13 steps 1–3: the
canonical `.txt`/`.packed` artifacts and `seal_team` sealing (step 2); exact hash disjointness
against the frozen coverage set and the repo-wide leakage scan (both green); the panel, holdout and
baseline manifests with real frozen hashes (step 3); the reference near-duplicate audit above
(§5a); and the CLI data wiring so both subcommands source real data instead of naming a Task-13
blocker (step 3). What remains is the whole-suite verification and Codex review of this branch —
after which the live Gate B run is a **separate** authorization (plan §17). No live server, battle,
or gate has been involved in any of the above.
