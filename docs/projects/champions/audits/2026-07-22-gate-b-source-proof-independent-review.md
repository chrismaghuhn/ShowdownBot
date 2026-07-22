# Gate B — D-1b Source-Proof, Independent Review

**Status: PROPOSED — independent review.** Not a decision record. Nothing here authorizes work.

**Reviewer position:** this review was performed against the frozen bytes and, where the review
scope permitted, against the live source. No claim in `sources.json` was accepted on trust; every
load-bearing statement below was recomputed or re-fetched independently.

| | |
|---|---|
| Reviewed artifact | `docs/projects/champions/audits/2026-07-21-task13-source-evidence/` (21 files, frozen in `16fb5fb`) |
| Repo state at review | branch `feat/champions-gate-b-task-1-schedule`, HEAD `cebf99f` |
| **Source-proof verdict** | **PASS** |
| **Task 13 construction** | **BLOCKED** — see §7 and §10 |

---

## 1. Scope and non-goals

**In scope.** Whether the frozen evidence set satisfies plan §2 rule 1 (source-proof), whether the
§2 rule 2 selection rule was applied as pre-registered, and whether the evidence honestly separates
what it proves from what it does not.

**Explicit non-goals, none of which were performed.** No team file, no `.packed` file, no
`validate-team`, no sealing, no panel/manifest/baseline edit, no test or production-code change, no
server, battle, or gate run, no evidence freeze, no commit/push/PR/merge. No new source was
selected and the UmbreNews fallback was not opened (§2 rule 4 makes it reachable only if the
primary source fails rule 1, which it does not — see §5). `showdown_bot/uv.lock` was not touched.

Internet access was used read-only and only against URLs already documented in
`sources.json`: the standings page and three player sheets (places 1, 2, 4). No other URL was
fetched.

**One capability limit, stated up front.** This review can verify what the source *publishes* and
what the repo's data files *contain*. It cannot independently adjudicate Pokémon Champions' own
legality rules; every legality statement in the evidence set (and in this review) is made against
`showdown_bot/config/species/speciesdata.json` and `.../items/itemdata.json` as a proxy. See §9,
finding H4.

---

## 2. Sources of truth

| Contract | Location |
|---|---|
| §2 rule 1 — source-proof | `docs/projects/champions/plans/2026-07-21-gate-b-independent-strength-holdout.md:974-978` |
| §2 rule 2 — pre-registered selection rule | same file, `:979-983` |
| §2 rule 3 — no reconstruction | same file, `:984-986` |
| §2 rule 4 — fallback | same file, `:987-990` |
| Task 13 definition of done | same file, §16 |
| Held-out discipline | `docs/projects/champions/specs/2026-07-20-champions-coverage-strength-holdout-design.md` §3.3 |
| Independence / blindness / sealing | same file, §3.4 |
| Canonical team hash (Task 12) | `showdown_bot/src/showdown_bot/eval/panel.py:51-69` |
| Sealing contract (Task 12) | `showdown_bot/src/showdown_bot/eval/team_sealing.py` |

Rule 1 verbatim: *"confirm all six candidate team sheets are publicly and reproducibly retrievable
as **full sheets** (species, items, moves, natures/EVs where published) — not Pokémon
icons/species-only standings rows."*

Rule 3 verbatim: *"**No reconstruction.** No team is completed or guessed from icons, species-only
standings, memory, or inference."*

---

## 3. Evidence-integrity table

**Method.** `sources.json` was parsed in full and every `sha256`/`export_sha256` field recomputed
with SHA-256 over the file's exact bytes. Directory listing compared against the registered set in
both directions.

**Result: 20 of 20 registered digests match exactly. No registered file missing. No unregistered
file present.** All files are LF-only, UTF-8, with a trailing newline — matching the declared
convention at `sources.json` `.sha256_algorithm`.

| Place | Player | Display file | Export file | Standings binding | Sheet fields | Rule-2 decision |
|---|---|---|---|---|---|---|
| 1 | James Evans | `place-1-thekingvillager-teamlist.txt` ✅ | `place-1-thekingvillager-export.txt` ✅ | ✅ line 3 | 6 mons · 6 items · 6 abilities · 4 moves ×6 · **no EVs/nature** | **SKIP** (ability) |
| 2 | William Brown | `place-2-wb_vg-teamlist.txt` ✅ | `place-2-wb_vg-export.txt` ✅ | ✅ line 4 | 6 · 6 · 6 · 4×6 · no EVs/nature | SELECT |
| 3 | Nicholas Morales | `place-3-charmdi-teamlist.txt` ✅ | `place-3-charmdi-export.txt` ✅ | ✅ line 5 | 6 · 6 · 6 · 4×6 · no EVs/nature | SELECT |
| 4 | Richard Wan | `place-4-richpro16-teamlist.txt` ✅ | `place-4-richpro16-export.txt` ✅ | ✅ line 6 | 6 · **5 resolvable items + 1 defective** · 6 · 4×6 · no EVs/nature | **SKIP** (item) |
| 5 | Chris Han | `place-5-darts-teamlist.txt` ✅ | `place-5-darts-export.txt` ✅ | ✅ line 7 | 6 · 6 · 6 · 4×6 · no EVs/nature | SELECT |
| 6 | Thaison Hughes | `place-6-charismaacheck-teamlist.txt` ✅ | `place-6-charismaacheck-export.txt` ✅ | ✅ line 8 | 6 · 6 · 6 · 4×6 · no EVs/nature | SELECT |
| 7 | Rob McNeilly | `place-7-rovbmc-teamlist.txt` ✅ | `place-7-rovbmc-export.txt` ✅ | ✅ line 9 | 6 · 6 · 6 · 4×6 · no EVs/nature | SELECT (replacement) |
| 8 | Joshua Robinson | `place-8-quivern-teamlist.txt` ✅ | `place-8-quivern-export.txt` ✅ | ✅ line 10 | 6 · 6 · 6 · 4×6 · no EVs/nature | SELECT (replacement) |

Non-placement artifacts, all digests verified: `standings-combined.txt`, `tournament-rules-section.txt`,
`user-supplied-full-rules-document.txt`, `ev-nature-synthesis-rule.md`.

**File-assignment check.** For all eight placements the display file's own header line 1 equals
`sources.json`'s `player`, header line 2 equals its `record`, and the display and export views list
the *same six species* once the documented naming divergence is normalized
(`sources.json` `.naming_divergence_note`). No file is mis-assigned to the wrong player or place.

**Independent live re-verification** (read-only, documented URLs only):

- Standings page returns exactly the same eight names in the same order, and confirms per-player
  team sheets are linked.
- Place 2's live sheet returns **byte-equivalent content** to the frozen export — same six species,
  items, abilities, and four moves each — and explicitly shows **no EV spread, nature, or level**.
- Place 1's live sheet shows Delphox @ Delphoxite, Ability **Levitate** — as frozen.
- Place 4's live sheet shows Garchomp's held-item position reading **"Dragon Claw"**, with Dragon
  Claw also its first move — as frozen.

This upgrades the "reproducibly retrievable" half of rule 1 from *asserted* to *independently
observed*.

---

## 4. Placement / selection-rule table

Rule 2 permits a skip **only** for illegality, exact contamination, or a sheet that is not fully
accessible, in placement order, with replacement by the next place and no re-ordering.

| Step | Place | Outcome | Ground |
|---|---|---|---|
| 1 | 1 | SKIP | Ability not resolvable to a base ability (§6.1) |
| 2 | 2 | SELECT | Complete sheet, all items/species resolve |
| 3 | 3 | SELECT | Complete sheet |
| 4 | 4 | SKIP | Held item is a defective record (§6.2) |
| 5 | 5 | SELECT | Complete sheet |
| 6 | 6 | SELECT | Complete sheet |
| 7 | 7 | SELECT — replacement for the first skip | Complete sheet |
| 8 | 8 | SELECT — replacement for the second skip | Complete sheet |

**Final panel: places 2, 3, 5, 6, 7, 8.** This is exactly "start at 1–6, skip in order, replace
with the next place" — two skips, two replacements taken strictly in sequence. No placement was
re-ordered, and no placement was skipped for archetype, overlap, desired outcome, or bot behaviour.

**Evidence that the rule was not bent toward a desired result.** The rule as applied removes the
tournament *winner* from the panel, and `sources.json:37` records that consequence explicitly
rather than burying it. A rule adjusted after seeing the data would not normally cost its author
the headline data point. I weight this as genuine.

**Verified independently:** places 2, 3, 5, 6, 7, 8 contain no unresolvable species and no
unresolvable item; the only unresolvable item anywhere in the eight sheets is place 4's
`Dragon Claw`. So no *further* placement would have been skippable on the same grounds, and the
selection is forced.

---

## 5. Source-proof — rule 1 verdict

**Rule 1 is satisfied for all six selected placements. Verdict: PASS.**

Each selected sheet publishes, for all six Pokémon: species, held item, ability, and exactly four
moves — verified by parsing the frozen export files, and re-confirmed live for place 2.

The three categories the review brief requires to be kept apart:

1. **Publicly absent, and rule 1 permits the absence — EVs and natures.** No sheet in the evidence
   set carries an EV spread, nature, or level. Rule 1's own wording is *"natures/EVs where
   published"*, so their absence does not defeat the source-proof. Crucially, this is **not an
   extraction gap**: my independent live fetch of place 2 confirms the page itself displays no EV,
   nature, or level. The tournament's two-tier sheet policy (Closed sheet with stat spreads to
   organizers; Open sheet without them to opponents) explains why, but the source-proof does **not
   depend** on that explanation — the live observation stands on its own.
2. **Required for an unambiguous legal build, but unknown.** Exactly two fields, both on skipped
   placements: place 1's Delphox base ability, and place 4's Garchomp held item. Neither was filled
   in; both triggered a skip. Correct handling.
3. **Later supplied by a new synthetic rule.** EVs and natures, via
   `ev-nature-synthesis-rule.md`. This is a *different act* from (1) and must not be folded into
   it — see §7. Rule 1's tolerance of an absent EV in the **source** is not an authorization to
   manufacture one into the **artifact**.

No field anywhere in the six selected sheets was completed from memory, inference, or icons.

---

## 6. Rule-2 skip verdicts

### 6.1 Place 1 — Delphox ability

**Directly proven by the frozen files and the live page:** Delphox is listed with item
`Delphoxite` and `Ability: Levitate` (`place-1-thekingvillager-export.txt`, live-confirmed).

**Directly proven by repo data:** `speciesdata.json` gives `Delphox` abilities `Blaze` / `Magician`
(hidden), and `Delphox-Mega` ability `Levitate`. So the published ability is the *Mega* ability and
is not one of the base abilities.

**Verified, not merely asserted:** I re-ran the whole mega-stone audit myself. Across places 1–6
there are **exactly 10** mega-stone holders, and **exactly one** — place 1's Delphox — reports a
non-base ability. All nine others report a genuine base ability. `sources.json:26`'s central claim
is accurate, and its per-instance base/mega ability lists match `speciesdata.json` exactly.

**What is interpretation, and the evidence set says so itself.** The premise "the sheet convention
is species *and ability* both pre-Mega" is a combination of two separate rules, not a quote —
flagged at `sources.json:19` (`rules_section.precision_note`). That candour is the right call.

**Is rule 2 sufficient?** The skip is filed under *"a sheet that is not fully accessible"*. Read
strictly, the sheet **is** accessible — it renders completely; one field is ambiguous *for build
purposes*. So this is a reading of that clause, not a literal application. It nevertheless reaches
the correct outcome by a second, independent route: choosing between Blaze and Magician is
inference, and rule 3 forbids it, so the team cannot be built and must be skipped regardless of
which clause is cited. **Outcome upheld; the clause-fit should be ratified rather than assumed**
(§11, Q2).

**Was the rule changed after seeing data?** No. `sources.json:26` records that an *earlier* draft
proposed a more permissive rule ("accept base or Mega ability whenever a Mega Stone is held") and
that this draft was **rejected** as over-generalizing from a single outlier. The movement was
toward strictness, against the author's convenience.

### 6.2 Place 4 — Garchomp held item

**Directly proven:** the held-item position reads `Dragon Claw` in both frozen views and on the live
page. `Dragon Claw` is **not** among `itemdata.json`'s 583 items — I verified this directly, and
also verified that every real dragon-type item `sources.json` lists as present (Dragon Fang, Dragon
Gem, Dragon Memory, Dragon Scale, Dragoninite, Dragonium Z) genuinely is present. The same string
also occupies Garchomp's first move slot.

**Interpretation:** that this is a duplication/shift defect in the record rather than a player
error. `sources.json:41` correctly limits the claim — both views come from the same page and the
same underlying record, so their agreement proves *the source publishes this*, not *the player
submitted this*. That precision is exactly right and I endorse it.

**Is rule 2 sufficient?** Same clause, same reservation as §6.1, same independent rule-3 backstop:
the held item is unknown, and "no item" is a substantive gameplay choice, not a neutral default.
**Outcome upheld.**

### 6.3 Both skips — summary

Both skips are **correctly grounded, correctly ordered, and honestly disclosed**. Neither is a
pretext. The only defect is a clause-fit question that does not change either outcome.

---

## 7. No-reconstruction / EV-nature ruling gap

**This is the finding that blocks Task 13.**

The three questions the brief poses, answered directly:

**Q1 — Is the pure source-proof satisfied even though EVs/natures are publicly absent? → YES.**
Rule 1 says "natures/EVs *where published*". They are not published; their absence is anticipated
and permitted. §5 stands on its own.

**Q2 — May Task 13 build playable team files with synthetic EVs/natures from these sheets? → NOT
UNDER THE CURRENT CONTRACT.**

§2 rule 3 reads: *"No reconstruction. **No team is completed or guessed** from icons, species-only
standings, memory, or inference."* The prohibited **act** is *completing* a team. The trailing list
qualifies the *sources* of a completion, not the act.

`sources.json:68` argues rule 3 is not violated because only EVs and natures are synthesized while
species/item/ability/moves are never guessed. That is a reasonable reading — but it is a **reading
of a rule written to forbid exactly this class of gap-filling**, produced by the same process that
needs the permission. A team file with a manufactured EV spread and a manufactured nature is, on
the plain words, a team that has been *completed*. Two readings exist; the contract does not
resolve between them; and the tie must not be broken by the party that benefits.

Three further facts make this a design decision rather than an execution detail:

- **It was authored, frozen, and fully computed in the same commit as the evidence it depends on.**
  `ev-nature-synthesis-rule.md` was added by `16fb5fb` alongside the sheets, and already contains
  the finished EV/nature spread for **all six** selected teams (its "Computed output" section). The
  construction is, in substance, already designed.
- **Its own text concedes it is filling a gap the contract left open:** *"Rule 1 already tolerates
  this … But Task 12 still needs a complete, legal team file per holdout Pokémon, so something has
  to fill the EV/Nature/Level gap. This document is that something."*
  (`ev-nature-synthesis-rule.md:17-19`).
- **No prior authorization is traceable.** §2 contains four numbered conditions; none mentions
  synthesizing absent fields. The approved spec §3.4 requires the six to be "tournament-legal"
  teams that are "natural, not engineered". A mechanically synthesized spread is neither the spread
  actually played (not natural) nor tuned for difficulty (not engineered) — it is a third category
  the spec does not contemplate.

To its credit, the evidence set does not hide any of this: `sources.json:64` states plainly that a
Gate B verdict on these teams tests *"real tournament species/items/abilities/moves with synthetic
spreads, not … the teams these players actually played."* The disclosure is exemplary. **The gap is
one of authority, not of honesty.**

**Q3 — Does the synthesis need an explicit new decision? → YES.** It exceeds the pre-registered
contract, it is not derivable from rule 1's "where published" clause, and it materially narrows
what a Gate B verdict can claim.

**Consequence, stated exactly as the brief requires:** the source-proof PASS in §5 **does not**
constitute authorization to construct teams. The two are ruled separately below.

**Design quality note, not a blocker.** If the synthesis is authorized, the rule itself is
well-built: it reads only base stats, move categories, the sheet, and the format's EV budget
(independently verified against `showdown_bot/config/formats/gen9championsvgc2026regma.yaml` —
level 50, `stat_points`, total 66, max 32 per stat; every published spread sums to exactly 66). It
explicitly **rejected** `default_spreads.yaml` because that file is derived from this project's own
panel/hero teams and would have imported build-level duplication onto 23 of 36 roster slots
(`sources.json:62`) — that rejection is the correct instinct and protects the property Gate B
exists to measure. Its Smogon comparison was kept informational and its four archetype-level misses
were recorded rather than patched in, which is the right discipline. None of this cures the
authority gap.

---

## 8. Independence limitations

The evidence set separates the four notions correctly, and I confirm the separation:

| Notion | Status |
|---|---|
| Source-proof (rule 1) | **Established** (§5) |
| Exact hash contamination (rule 2) | **Not yet checkable.** Requires a packed team file, which does not exist before Task 12. Correctly listed under `sources.json` `.not_yet_done[0]` |
| Species-overlap diagnosis | **Measured, non-binding.** A proxy only |
| Content-meaningful independence | **Not established, and correctly not claimed** |

The measured overlaps: place 2 shares 4/6 species with `rain_offense`/`cov_foe_slot0`; place 6
shares 4/6 with `rain_offense`/`cov_foe_slot0`/`cov_foe_tie`; places 3, 7, 8 show no 4+/6 overlap
(`sources.json:67`).

**Both directions of the brief's warning are respected.** These overlaps are *not* re-labelled as
exact contamination — rule 2's criterion is hash collision and no hash has been computed yet. And
the independence claim is *not* inflated: `sources.json:68` states that what Gate B proves is
hash-disjointness, not archetype-disjointness, and that a holdout team sharing 4 of 6 species with a
team the bot was tuned against "is not independent in the content-meaningful sense". I agree, and I
would go one step further for the record: **two of the six selected teams carry a 4/6 overlap with
tuned-against teams, so Task 4's near-duplicate check is expected to flag them.** §16 item 5
requires a written disposition per flag — that requirement is live, not hypothetical, and should not
be discharged as routine.

Second narrowing, already noted in §7: the panel is the published sheet **plus synthetic spreads**.

---

## 9. Provenance and hygiene findings

| # | Severity | Finding |
|---|---|---|
| **H1** | **Should fix** | `sources.json:47` embeds a local absolute path including the operator's username: `C:\Users\chris\Downloads\Tournament Format & Rules – Pokémon Champions VGC.txt`. Committed, and the only such leak in the evidence set. Recommend redacting to a non-identifying description. Reported, not silently corrected |
| **H2** | Accepted | `user-supplied-full-rules-document.txt` is user-supplied, not agent-fetched, and `verified_against_live_source: false` (`sources.json:48`). It is correctly marked `load_bearing: false` (`:53`) with an explicit tripwire for later misuse. **Independently confirmed sound:** my live fetch of place 2 establishes the EV/nature absence without this document, so no rule-1 or rule-2 conclusion depends on it. Handled correctly |
| **H3** | Note | Tournament structure is described inconsistently: plan §2 and `tournament-rules-section.txt:4` say "7 Rounds Swiss + Top 8 Cut", while `standings-combined.txt:1` reads "Phase: Combined (2 Single Elimination Bracket + 1 Swiss Rounds)". Most likely Limitless phase labelling, but it is unexplained in the evidence set. Does not affect placement order, which I verified live |
| **H4** | Note | `speciesdata.json` and `itemdata.json` both self-declare `"format": "gen9vgc2024regg"`, yet `sources.json:42` describes itemdata as "583 items, **Champions-current**". The item count (583) and content (Mega stones, Champions-era species) check out, so the audit's substance holds — but the "Champions-current" label is not supported by the files' own metadata. **Every ability and item determination in *this evidence set* — including both skip rulings — rests on these two snapshots**, and that is the scope of the uncertainty. It does **not** propagate forward: `validate-team` is the external `pokemon-showdown` CLI, which validates against Showdown's own dex and format rules and reads neither of these files. A later `validate-team` result therefore does not inherit this uncertainty — it is an independent authority, and running it is the appropriate way to settle legality rather than something the snapshots could contaminate. What remains true is narrower: the two skips were decided *before* any `validate-team` run, on the snapshots alone |
| **H5** | Note | Both skips are labelled `DECIDED:` (`sources.json:36`, `:42`). Acceptable — they execute a rule pre-registered *before* the data was read. The EV/nature synthesis rule is presented with the same finality but has no comparable prior authorization (§7). The two must not be read as equally settled |
| **H6** | Positive | `sources.json` `.not_yet_done` is accurate and complete: exact contamination, team-file creation, sealing, and every remaining §16 item are listed as outstanding. No step is claimed as done that is not done |

---

## 10. Final verdict

### SOURCE-PROOF PASS

For the six selected placements (2, 3, 5, 6, 7, 8):

1. Evidence integrity is exact — 20/20 registered SHA-256 digests recomputed and matching, no
   missing file, no unregistered file, correct player/place assignment throughout.
2. Every selected sheet publishes full per-Pokémon detail: species, item, ability, four moves, six
   Pokémon.
3. Public retrievability was independently re-confirmed live for the standings and three sheets,
   including a byte-equivalent match for a selected placement.
4. Absent EVs/natures do not defeat rule 1, whose text anticipates them, and their absence is a
   structural property of the source confirmed by direct live observation.
5. Rule 2 was applied in placement order, with both skips grounded in live-verifiable published
   facts and disclosed against the author's own interest.

Rule 4's UmbreNews fallback is **not** reached: it is conditioned on rule 1 failing for the primary
source, and rule 1 passes.

### TASK 13 CONSTRUCTION: BLOCKED

Not because the sourcing is deficient — it is not — but because building playable team files from
these sheets requires manufacturing EVs and natures that the source never published, and:

- §2 rule 3 forbids a team being "completed" without qualifying by field;
- no §2 condition and no approved-spec clause authorizes synthesizing absent fields;
- the synthesizing rule was authored, frozen, and fully computed by the implementing process itself,
  with no traceable prior authorization;
- the resulting panel supports a **narrower claim** than "tested against real tournament teams", by
  the evidence set's own admission.

A source-proof PASS is **not** a construction authorization, and this review does not present it as
one.

---

## 11. Next decision required

Task 13 stays blocked pending an explicit ruling on the following. These are decisions for the
project owner; this review deliberately does not pre-empt them.

**Q1 (primary, blocking).** May Task 13 construct the six holdout team files as *published sheet +
mechanically synthesized EV/Nature spread*, per the frozen `ev-nature-synthesis-rule.md`?

- **If YES:** §2 should be amended to record the permission explicitly (rule 1 or a new rule 5),
  and every downstream Gate B artifact — verdict payload, report banner, ROADMAP entry — should
  carry the narrowed wording from `sources.json:64` rather than a plain "real tournament teams"
  claim. The narrowing must travel with the number, not live only in this audit.
- **If NO:** the six sheets cannot become team files under the current contract. The realistic
  alternatives are (a) a source that publishes Closed-tier sheets including spreads, or (b) an
  explicit decision to change what Gate B measures. Neither should be chosen by the implementing
  agent.

**Q2 (secondary, non-blocking).** Ratify or correct the reading of rule 2's *"not fully
accessible"* clause as covering a sheet that renders completely but contains an ambiguous or
defective required field. Both skip outcomes are independently supported by rule 3, so no re-work
follows either way — but the clause should mean what it is being used to mean.

**Q3 (hygiene).** Approve redaction of the local path and username at `sources.json:47` (H1), and
decide whether the H4 snapshot-authority note warrants re-deriving the two skip rulings against an
authoritative `gen9championsvgc2026regma` data source. (H4 does not affect `validate-team`, which is
external and independent — see H4.)

**Limit of any H1 redaction, stated explicitly so it is not over-promised.** A redaction landed as a
normal follow-up commit removes the username and local path from the **current tree only**. The
string remains in the repository's history, reachable at `16fb5fb` for anyone who clones the repo
or reads the blob directly. Genuinely removing it would require rewriting history — a force-push
over published commits — which is **not authorized** here and is not proposed by this review. The
realistic options are therefore: (a) accept the historical exposure and redact going forward, or
(b) make a separate, explicit decision to rewrite history. This review recommends (a) unless the
operator considers the exposure material; either way the choice belongs to the project owner, and
a follow-up redaction commit should not be described as having "removed" the data.

---

## Appendix — what this review executed

Read in full: plan §2 and §16; approved spec §3.3 and §3.4; commit `16fb5fb`'s complete file list;
all 21 frozen evidence files; `sources.json` in full including every nested field; `panel.py`'s
`team_content_hash`; `team_sealing.py`.

Recomputed independently: all 20 registered SHA-256 digests; per-sheet completeness (species/item/
ability/move counts, EV/nature/level presence) for all eight placements; species/item resolvability
against `speciesdata.json` and `itemdata.json`; the full 10-instance mega-stone ability audit;
display-vs-export species agreement and player/record header binding; standings-to-`sources.json`
placement binding; the format EV budget.

Fetched read-only (documented URLs only): the standings page; the place 1, 2, and 4 player sheets.

Not executed: anything in the §1 non-goals list.

---

# Addendum — 2026-07-22, later the same day: Q1 is moot, not answered

**Everything above this line is unchanged and remains the review of the Rutgers Scarlet Classic
evidence set as it stood.** This addendum does not revise a single finding, table, or verdict
above; it records what happened to the open question afterwards. Nothing above was written with
knowledge of the source described here.

**What changed.** After this review was delivered, the project owner selected a different source
for Task 13: six complete published teams from the VGCPastes "Champions M-A Featured Teams" sheet
(PC1102, PC1101, PC1100, PC1099, PC1098, PC1097). That source publishes **full** sets — species,
item, ability, level, EVs, nature and four moves for every Pokémon.

**Effect on §7 / Q1.** Q1 asked whether Task 13 may build team files with *synthesized* EVs and
natures. That question is now **moot rather than answered**: the chosen source publishes them, so
nothing is synthesized and the authority gap Q1 identified does not arise. Q1 was **not** resolved
in favour of "synthetic spreads are permitted", and this addendum must not be cited as such a
ruling. If a synthetic-spread path is ever wanted again, Q1 is still open and still needs its own
decision.

**Effect on the verdicts above.**

- The **SOURCE-PROOF PASS** for the Rutgers evidence stands, for exactly what it assessed.
- The **Task 13 construction BLOCKED** verdict stands and was correct on its own terms. It is not
  overturned; it is *bypassed* by no longer using that source for construction.
- **Q2** (the rule-2 "not fully accessible" clause reading) and **Q3** (hygiene, incl. the H1
  local-path/username exposure and its history-rewrite limitation) remain open and unaffected —
  they concern the Rutgers artifact, which is retained as history.

**Status of the Rutgers evidence set.** Retained unchanged as the historical record of a source
that was assessed and then superseded. It is no longer the Task 13 construction path.

**Where the new source is documented.**
`docs/projects/champions/audits/2026-07-22-task13-vgcpastes-source-selection.md` and
`docs/projects/champions/audits/2026-07-22-task13-vgcpastes-source-evidence/`.
