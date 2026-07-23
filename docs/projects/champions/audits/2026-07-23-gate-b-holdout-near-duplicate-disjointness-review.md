# Gate B holdout — near-duplicate disjointness review (Option A: documented ACCEPT)

**Status:** reviewer draft — RECOMMEND ACCEPT. Owner sign-off pending (§7). Records an adjacent
intra-holdout diversity caveat (§3.6) that does not change the recommendation.
**Type:** docs-only audit. Nothing sealed is changed by this document.

**Reference convention (leakage discipline — read before editing).** This review refers to the six
sealed holdout teams positionally as **H1–H6**, where **H*n*** is the team at manifest
`selection_index` *n* (H1 = `selection_index` 1 … H6 = `selection_index` 6). The map from `H#` to
the sealed opaque `gbh_*` holdout IDs — and onward to their public sources — lives **only** in the
holdout manifest (`config/eval/holdout/champions_strength_holdout_v0_manifest.json`; spec §3.3 /
Amendment A1.1 `internal_id_scheme`). This document deliberately does **not** name the sealed
`gbh_*` IDs or their content hashes. Reason: those IDs and hashes are Gate B **leakage-scan
identifiers** — `holdout_leakage_scan.assert_no_holdout_leakage` greps every non-allowlisted
git-tracked file for them, and this audit is **not** on that allowlist
(`ALLOWED_EXACT_PATHS` / `ALLOWED_DIRECTORY_PREFIXES`). A copy here that named them would make the
next `combine_strength_holdout_arms` fail closed with `LeakageDriftError`. Do **not** reintroduce
the `gbh_*` IDs or the sealed content hashes into this file.

## 1. Scope & decision

The Gate B independent strength holdout
([spec §3.3/§3.4](../specs/2026-07-20-champions-coverage-strength-holdout-design.md)) runs a
content-overlap check at sealing that *"flags any holdout team whose species set substantially
overlaps a touched or coverage team for **manual disjointness review** (near-duplicates are not
independent)."* The sealing check flagged **3 of the 6** sealed holdout teams (`H2`, `H4`,
`H5`) as species-level near-duplicates of **2 engineered coverage teams** (`cov_foe_both`,
`cov_foe_tie`). Per spec, these flags are **diagnostic-only** — they trigger a manual review, they
do **not** auto-reject (`near_duplicate.py`: `find_near_duplicate_flags` returns flags;
`combine` records them in `verdict.json.near_duplicate_flags` and continues with `reasons:[]`).

This document is that manual review. It recommends the project owner **ACCEPT the sealed holdout
set unchanged**. The sealed set is **byte-identical**: no team file, manifest, panel, baseline,
schedule, `config_hash`, or ledger entry is modified, added, or deleted by this review; no content
hash changes. Per §3.4 the acceptance ruling is the **owner's**, not the implementer's — this is a
recommendation with the evidence it rests on, plus a blank owner sign-off block.

**This review does not resolve the run's `SAFETY-FAIL` and makes no strength claim.** Champions
Strength remains **NO-GO**. The independence judgment below is deliberately **bot-performance-blind**
— it rests only on team composition, never on any win/loss/delta/cell-flip number (using a result to
argue independence would itself be a contamination).

## 2. Reproduction (the flags are mechanically re-derivable)

Run from the **repo root** with `teams_root="."`, against the sealed `.packed`/`.txt` files. The
flag set reproduces **byte-for-byte** the frozen `near_duplicate_flags` in the SAFETY-FAIL evidence
commit `48558aa`
(`…/gate-b-safety-fail-bc2d6df/combine/verdict.json`). Confirmed: **True** (6 flags, identical
pairs / `overlap_fraction` / `shared_species`).

```bash
python - <<'PY'
import json, subprocess, sys
sys.path.insert(0, "showdown_bot/src")
from showdown_bot.eval.near_duplicate import load_team_species, find_near_duplicate_flags
from showdown_bot.eval.strength_holdout_runner import CANONICAL_REFERENCE_TEAM_PATHS
from showdown_bot.cli import _load_holdout_content_hashes
HD = "showdown_bot/teams/panel_champions_strength_holdout_v0"
holdout = sorted(_load_holdout_content_hashes("."))                       # H1..H6
hs = {t: load_team_species(f"{HD}/{t}.txt", teams_root=".") for t in holdout}
rs = {r: load_team_species(p, teams_root=".") for r, p in CANONICAL_REFERENCE_TEAM_PATHS.items()}  # 9 refs
flags = sorted(({"candidate_team_id": f.candidate_team_id, "reference_team_id": f.reference_team_id,
                 "overlap_fraction": f.overlap_fraction, "shared_species": list(f.shared_species)}
                for t in holdout for f in find_near_duplicate_flags(
                    candidate_team_id=t, candidate_species=hs[t], reference_teams=rs)),
               key=lambda d: (d["candidate_team_id"], d["reference_team_id"]))
frozen = sorted(json.loads(subprocess.run(
    ["git","show","48558aa:data/eval/champions-panel-v0/strength-holdout-v0/windows/"
     "gate-b-safety-fail-bc2d6df/combine/verdict.json"], capture_output=True, text=True,
    check=True).stdout)["near_duplicate_flags"], key=lambda d: (d["candidate_team_id"], d["reference_team_id"]))
print("byte-equal to frozen verdict.json@48558aa:", flags == frozen, "| flags:", len(flags))
PY
```

Threshold: `near_duplicate.NEAR_DUPLICATE_REVIEW_THRESHOLD = 0.5` Jaccard = **≥ 4 of 6 shared
species** (`|A∩B| / |A∪B| = 4/8 = 0.5`); flags are inclusive of the threshold and are
diagnostic-only by contract.

## 3. Evidence (computed, not asserted)

### 3.1 The six flags

| holdout | reference | kind | `overlap_fraction` (Jaccard) | shared species |
|---|---|---|---|---|
| `H2` | `cov_foe_both` | coverage | 0.500 | Aerodactyl, Basculegion, Garchomp, Kingambit |
| `H2` | `cov_foe_tie`  | coverage | 0.500 | Aerodactyl, Basculegion, Garchomp, Kingambit |
| `H4` | `cov_foe_both` | coverage | 0.500 | Aerodactyl, Garchomp, Kingambit, Sneasler |
| `H4` | `cov_foe_tie`  | coverage | 0.500 | Aerodactyl, Garchomp, Kingambit, Sneasler |
| `H5` | `cov_foe_both` | coverage | 0.500 | Aerodactyl, Garchomp, Kingambit, Sneasler |
| `H5` | `cov_foe_tie`  | coverage | 0.500 | Aerodactyl, Garchomp, Kingambit, Sneasler |

Every flag is **exactly at** the 0.5 threshold (4/6 shared). There is no flag above it.

### 3.2 Full species sets (of the flagged teams)

| team | species (6) |
|---|---|
| `H2` (holdout) | Aerodactyl, Basculegion, **Charizard**, Garchomp, Kingambit, **Sylveon** |
| `H4` (holdout) | Aerodactyl, **Charizard**, **Floette-Eternal**, Garchomp, Kingambit, Sneasler |
| `H5` (holdout) | Aerodactyl, **Charizard**, **Floette-Eternal**, Garchomp, Kingambit, Sneasler |
| `cov_foe_both` (coverage) | Aerodactyl, Basculegion, Garchomp, Kingambit, **Meganium**, Sneasler |
| `cov_foe_tie` (coverage)  | Aerodactyl, Basculegion, Garchomp, Kingambit, **Pelipper**, Sneasler |

Non-shared species (bold) differ in every flagged pair: each holdout team brings species the
coverage team does not, and vice-versa.

### 3.3 Overlap is confined to coverage teams — ZERO dev-panel overlap (with margin)

- All **6** flags land on the 2 coverage teams. **No** holdout team flags against **any** of the 5
  `panel_champions_v0` dev-panel teams (disruption, goodstuff, rain_offense, tailwind_offense,
  trick_room): computed dev-panel flags = **0**.
- The **best** (largest) holdout↔dev-panel species overlap across all 30 holdout×dev pairs is
  **Jaccard 0.333** (`H4` vs `goodstuff`) — a full **0.167 below** the 0.5 review threshold. The
  dev panel is comfortably clear, not a near-miss.

### 3.4 Non-species differences on the shared staples (distinct strategic objects)

The format is `gen9championsvgc2026regma` — a **Mega-Evolution** format; these teams declare **no
Tera type** (Tera is not applicable here), so the strategic differentiators are **Mega identity,
item, ability, EV/nature spread, and moves**. The shared staple species are built as different
objects across the holdout and coverage teams:

**Mega identity (the load-bearing difference).** In the coverage teams the shared **Aerodactyl is
the Mega** (`Aerodactylite`). In `H4`/`H5` the shared **Aerodactyl holds `Focus Sash`** (a
non-Mega utility lead) and the team's Mega is elsewhere (`Charizardite Y` and/or `Floettite` on
Floette-Eternal). `H2` carries a *different* Mega pair again (`Aerodactylite` + `Charizardite Y`).
Same species, opposite role.

Per-shared-species build comparison (item / ability / nature / notable moves):

| shared species | `H2` (holdout) | `H4` (holdout) | `H5` (holdout) | `cov_foe_both` | `cov_foe_tie` |
|---|---|---|---|---|---|
| **Aerodactyl** | Aerodactylite (**Mega**), Unnerve, Jolly, +Wide Guard | **Focus Sash** (non-Mega), Unnerve, Jolly, +Protect | **Focus Sash** (non-Mega), Unnerve, Jolly, +Dual Wingbeat | Aerodactylite (**Mega**), Unnerve, Jolly, +Protect | Aerodactylite (**Mega**), Unnerve, Jolly, +Protect |
| **Garchomp** | **Choice Scarf**, Adamant, Stomping Tantrum/Rock Tomb | **Choice Scarf**, **Jolly**, Stomping Tantrum/Rock Slide | **Choice Scarf**, Adamant, Dragon Rush/Rock Slide | **Sitrus Berry**, Adamant, +Protect | **Sitrus Berry**, Adamant, +Protect |
| **Kingambit** | Chople Berry, Defiant, +Low Kick (no Protect) | Chople Berry, Defiant, +Protect | **Black Glasses**, Defiant, +Swords Dance/Protect | Chople Berry, Defiant, +Protect | Chople Berry, Defiant, +Protect |
| **Basculegion** | **Focus Sash**, Adaptability, Jolly, Liquidation/**Protect** | *(not on team)* | *(not on team)* | **Choice Scarf**, Adaptability, Adamant, Wave Crash/**Flip Turn** | **Choice Scarf**, Adaptability, Adamant, Wave Crash/**Flip Turn** |
| **Sneasler** | *(not on team)* | White Herb, **Unburden**, Jolly, +Feint | White Herb, **Unburden**, Adamant, +Protect | **Focus Sash**, **Poison Touch**, Jolly, +Poison Jab | White Herb, Unburden, Jolly, +Protect |

Even on the identically-named staples, holdout and coverage differ in Mega assignment, item
(Sash/Scarf/Berry/Mega-stone), ability (Sneasler Unburden vs Poison Touch), nature, and moves.
The teams are distinct strategic objects that happen to draw from the same Reg-MA staple pool.

### 3.5 Hard hash firewall (identity, not similarity) — PASSES

`holdout_disjointness.assert_disjoint_from_coverage` over the six sealed holdout content hashes
returns **PASS**: no holdout team **is** a coverage team (no content-hash collision). Near-duplicate
similarity is a *diagnostic* signal; this firewall is the *hard* one and it holds.

### 3.6 Intra-holdout diversity observation (adjacent scope — NOT a §3.3 finding)

The §3.3 near-duplicate check compares each holdout team against the nine touched/coverage reference
teams; it does **not** compare holdout teams against each other. A reviewer-requested holdout×holdout
pass surfaces an adjacent fact that must be recorded but is **outside** §3.3's scope.

**`H4` and `H5` are two variants of one archetype.** Computed holdout×holdout species Jaccard
matrix (from the sealed `.packed`, via `near_duplicate.load_team_species`):

|        | H1 | H2 | H3 | H4 | H5 | H6 |
|---|---|---|---|---|---|---|
| **H1** | 1.000 | 0.500 | 0.000 | 0.500 | 0.500 | 0.000 |
| **H2** | 0.500 | 1.000 | 0.000 | 0.500 | 0.500 | 0.000 |
| **H3** | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 | 0.091 |
| **H4** | 0.500 | 0.500 | 0.000 | 1.000 | **1.000** | 0.000 |
| **H5** | 0.500 | 0.500 | 0.000 | **1.000** | 1.000 | 0.000 |
| **H6** | 0.000 | 0.000 | 0.091 | 0.000 | 0.000 | 1.000 |

- The **only** off-diagonal pair at Jaccard **1.0** is (`H4`, `H5`) — species-identical
  {Aerodactyl, Charizard, Floette-Eternal, Garchomp, Kingambit, Sneasler}. The **next-highest** pair
  is **0.500** (e.g. `H2`↔`H5`; `H1`/`H2`/`H4`/`H5` form a 0.5 staple cluster).
- **Items: 5 of 6 identical** between `H4` and `H5` (only **Kingambit** differs — `Chople
  Berry` vs `Black Glasses`).
- **0 of 6 mon blocks are byte-identical** (diff of `H4.txt` vs `H5.txt`): they differ in EV
  spreads, in natures (**Garchomp** and **Sneasler** are Jolly in `H4` vs Adamant in `H5`), and
  in 1–2 moves each (e.g. Floette-Eternal: `H4` Moonblast/Light-of-Ruin vs `H5`
  Draining-Kiss/Calm-Mind). Two distinct **builds** of one archetype — not duplicate teams.

**Scope.** This is holdout-vs-holdout, **outside** the §3.3 near-duplicate check (holdout-vs-
touched/coverage). It is therefore **not** a disjointness or leakage finding and **does not change
the ACCEPT recommendation (§6)** or the owner sign-off block (§7). The hard content-hash firewall
(§3.5) already proves `H4` and `H5` are distinct sealed teams.

**Effect on the holdout as a measurement instrument (record for interpreting any future strength
result).** Effective **archetype** diversity is **~5 distinct, not 6** (`H4`/`H5` collapse to
one archetype). That archetype occupies **2 of 6 teams = 60 of 180 schedule battle-keys (1/3)** of
the strength schedule (180 = 6 teams × 2 policies × 15 seeds ⇒ 30 keys/team). A future McNemar
strength verdict would therefore draw ~**1/3** of its paired evidence from a single archetype
(effectively double-weighted). This is a descriptive interpretation caveat only; it uses no bot
result and is moot under the current SAFETY-FAIL.

**Not actionable as a fix.** Dropping or swapping either team would break the blind, positional,
pre-registered selection (manifest `selection_rule` / `blind_attestation`; spec §3.4 *"freshly
created is not the same as independent"*) — the same trap as a hand-swap. The fixed positional rule
legitimately produced two variants of one archetype from **two consecutive entries** in the sealed
selection order (manifest `selection_index` 4 and 5, both Seniors-division placements; the source
identities themselves are sealed to the manifest and are deliberately **not** reproduced here). It is
**documented, not remedied**; the only clean remedy, if the owner judges the double-weighting
unacceptable, is the same full blind re-selection escalation as §5 — never an edit of this set.

**Reproduction** (repo root, `teams_root="."`):

```bash
python - <<'PY'
import sys, itertools
sys.path.insert(0, "showdown_bot/src")
from showdown_bot.eval.near_duplicate import load_team_species, overlap_fraction
from showdown_bot.cli import _load_holdout_content_hashes
HD = "showdown_bot/teams/panel_champions_strength_holdout_v0"
ids = sorted(_load_holdout_content_hashes("."))
sp = {t: frozenset(load_team_species(f"{HD}/{t}.txt", teams_root=".")) for t in ids}
for a in ids:
    print(a, " ".join(f"{overlap_fraction(sp[a], sp[b]):.3f}" for b in ids))
print("1.0 pairs:", [(a, b) for a, b in itertools.combinations(ids, 2) if overlap_fraction(sp[a], sp[b]) == 1.0])
PY
```

## 4. Independence argument (grounded strictly in §3)

1. **Species-level only.** The overlap is a shared *species set*, never a shared team: the hard
   content-hash firewall (§3.5) passes, and on the shared species the builds differ in Mega/item/
   ability/spread/moves (§3.4). The teams are not the same object.
2. **The shared species are Reg-MA staples.** Aerodactyl, Garchomp, Kingambit, Sneasler, Basculegion
   are among the most common `gen9championsvgc2026regma` picks. Two independently-built Reg-MA teams
   co-occurring on 4 of 6 staples is *expected* in a shared metagame — it is weak evidence of
   derivation, not strong.
3. **Overlap is confined to the coverage teams we engineered, and ZERO dev-panel teams (§3.3).** The
   coverage panel (`cov_foe_*`) was **engineered by us** to exercise opponent-Mega decision cells
   (spec §2.4), so it deliberately concentrates Mega-relevant staples. A blind, independently-sourced
   holdout team built from the same metagame naturally lands on those same staples. Co-occurrence
   with an engineered staple-dense team is therefore the *expected* direction of a false-positive,
   not a signature of contamination.
4. **Different strategic role for the shared staples (§3.4).** Most decisively, the shared Aerodactyl
   is the **Mega** on the coverage teams but a **non-Mega Focus-Sash lead** on `H4`/`H5`; the
   holdout Megas are Charizard-Y / Floette-Eternal. Sharing a species while assigning it the opposite
   role is the opposite of near-duplication.
5. **Selection was blind, positional, and mechanical (§3.4).** From the holdout manifest
   `blind_attestation`: *"The six teams were selected blind to this bot's results. The selection rule
   is positional and mechanical — the first six table-order entries meeting fixed predicates — and
   was fixed and enumerated by the project owner BEFORE any paste was read for construction. No team
   was chosen, kept, dropped, or re-ordered because of how the bot performs against it; no bot
   result, win rate, cell exposure, coverage outcome, or Gate B verdict existed for any of these
   teams at selection time, and none was consulted."* The `selection_rule` is the fixed positional
   predicate (*"the first six entries, in sheet table order… with EVs = Yes, a reachable PokePaste,
   six complete Pokemon, and declared format gen9championsvgc2026regma"*). The species overlap is a
   consequence of the metagame, not of any results-aware choice.
6. **Firewall holds (§3.5).** The hard disjointness firewall passes; sealed hashes are unchanged.

## 5. Residual risk (honest — not a rubber stamp)

The independence here is **strong but not zero-risk**, and this review does not pretend otherwise.
A holdout team sharing **4 of 6 species with a coverage team the pipeline touched** is a **small,
real distributional link**: the coverage panel is engineered rather than sampled, so its staple
concentration is a property *we chose*, and three holdout teams sit exactly at the 0.5 review
threshold against it. If one wanted to be maximally conservative, "the holdout should share as
little as possible with anything the pipeline has already exercised" is a defensible stricter bar
than "not the same team."

It is judged **acceptable** — not risk-free — because: (a) the link is species-only while the builds,
Mega identity, items, abilities, spreads and moves differ (§3.4); (b) the shared species are metagame
staples, so co-occurrence is expected rather than derived (§4.2); (c) the overlap is entirely with
**engineered** coverage teams and **zero** dev-panel teams, with a clear 0.167 margin on the dev side
(§3.3); and (d) selection was provably blind, positional, and pre-registered (§4.5). None of these
uses a bot result.

**Escalation path if the owner disagrees.** The correct remedy is **not** a hand-swap of the three
flagged teams — a post-hoc hand-swap would break the blind/positional attestation (spec §3.4:
*"Freshly created is not the same as independent"*; a team chosen while aware of this flag is no
longer blind). The remedy is a **full blind re-selection of all six teams under a corrected fixed
positional predicate** (e.g. one that additionally excludes substantial overlap with the coverage
panel), re-sealed before first access — a new independent holdout, not an edit of this one. That is a
separate, owner-authorized work item, and it also interacts with the already-consumed ledger budget
for this `config_hash` (see the SAFETY-FAIL evidence record).

Separately from §3.3 disjointness, see **§3.6** for an adjacent intra-holdout observation (`H4`
and `H5` are two builds of one archetype): outside this check's scope, not a leakage/disjointness
finding, no change to the recommendation below — but a recorded interpretation caveat (~5 effective
archetypes; that archetype carries 1/3 of the schedule) for any eventual strength result.

## 6. Verdict (reviewer draft)

**RECOMMEND ACCEPT** the sealed holdout set unchanged, resolving the §3.3 near-duplicate flags via
this documented manual disjointness review. The flags are diagnostic-only, mechanically reproducible,
confined to engineered coverage teams (zero dev-panel overlap), species-level only with distinct
per-species builds, and the hard content-hash firewall passes. Residual risk is stated in §5 and
judged acceptable on composition grounds alone.

This recommendation is **bot-performance-blind** and makes **no strength claim**; it does not change
the run's `SAFETY-FAIL` or the `NO-GO` status.

## 7. Owner sign-off (required per §3.4 — ruling is the owner's)

The acceptance ruling belongs to the project owner, not the implementer. Please record the decision:

- Decision (ACCEPT / RE-SELECT / OTHER): `________________________________`
- Rationale / conditions: `________________________________________________`
- Owner: `______________________`   Date: `________________`   Commit/branch at decision: `______________`

*Until this block is signed, this document is a reviewer recommendation only, not an accepted ruling.*

## 8. Cross-references

- Spec §3.3 (held-out discipline; content-overlap flags → manual disjointness review; diagnostic,
  not auto-reject) and §3.4 (independence/blindness/sealing; *"freshly created is not the same as
  independent"*; firewall D-3): [design](../specs/2026-07-20-champions-coverage-strength-holdout-design.md).
- Holdout manifest (blind attestation, positional selection rule, opaque `internal_id_scheme`):
  `config/eval/holdout/champions_strength_holdout_v0_manifest.json`.
- Near-duplicate logic + threshold + diagnostic-only contract:
  `showdown_bot/src/showdown_bot/eval/near_duplicate.py`
  (`NEAR_DUPLICATE_REVIEW_THRESHOLD = 0.5`, `find_near_duplicate_flags`).
- Reference set (`CANONICAL_REFERENCE_TEAM_PATHS`, nine teams):
  `showdown_bot/src/showdown_bot/eval/strength_holdout_runner.py`.
- Hard disjointness firewall: `showdown_bot/src/showdown_bot/eval/holdout_disjointness.py`
  (`assert_disjoint_from_coverage`).
- Frozen flags reproduced: `verdict.json.near_duplicate_flags` at commit `48558aa`
  (`data/eval/champions-panel-v0/strength-holdout-v0/windows/gate-b-safety-fail-bc2d6df/combine/verdict.json`).
