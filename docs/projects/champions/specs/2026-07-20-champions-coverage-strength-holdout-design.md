# Champions Opponent-Mega Coverage + Independent Strength-Holdout — Design

**Status:** APPROVED (2026-07-20). **Design/contract only.** No implementation, code, test
code, server, battle, run, evidence, push, PR, or merge is authorized by this document.

**Date:** 2026-07-20 · **Base:** `main @ 9c780a2` · **Owner:** Champions strength track

**Purpose.** Define the two pre-registered gates that must **both** pass before any Champions
Strength claim can be made: **(A)** a broader opponent-Mega **coverage** gate and **(B)** a
genuinely **independent Strength holdout**. Champions Strength remains **NO-GO** until both are
designed, approved, and satisfied. A latency PASS alone does not authorize a Strength run.

This spec closes the contract. The binding decisions that could not be grounded from the repo were
surfaced as Open Decisions and **ruled at review on 2026-07-20 (§7)**; the body now reflects those
rulings (D-1a, D-2, D-3, D-4). A few non-binding naming/path details remain marked **PROPOSED** for the
implementation plan.

---

## 0. Grounding provenance

The facts below are cited from the code/config as they stand on `main @ 9c780a2` (mapped this
session). Load-bearing citations are inline. Two upstream maps back this design:

- **I8-D live-gate machinery** — exposure floor, verdict, schedule, provenance (§1, §2).
- **Team inventory + strength methodology + contamination** — (§3, §4).

Where a number or identity is *not* pinned by the repo it is marked **PROPOSED** (a non-binding
naming/path detail for the implementation plan); the binding decisions were ruled (§7). Nothing here
is asserted as grounded when it is not.

---

## 1. Why this gate exists (grounded gap)

The merged I8-D live-latency gate judges only **latency**, over the population
`is_active_valid_live_row` = `source=="live" ∧ timer_scope=="agent_choose" ∧ outcome=="ok" ∧
foe_mega_active is True` (`eval/decision_profile.py:1051-1065`). `foe_mega_active` is a single
boolean, `bool(shape is not None and shape.n_mega_twins > 0)` (`decision_profile.py:358`), where
`shape` is a `MegaShapeCounts` with exactly six fields — `n_candidates, n_responses, n_mega_twins,
n_branches, n_worlds, depth2_frontier` (`eval/mega_scoring.py:55-60`).

**The live verdict row therefore records only *presence/count* of foe-Mega branches — not which
coverage case occurred.** The three coverage dimensions this design targets are **absent from the
live row**:

- **foe-Mega slot (0 vs 1)** — exists upstream as `MegaEvaluationContext.foe_mega_slot`
  (`mega_scoring.py:76`) and `ScoredResponseEvidence.foe_mega_slot` (`mega_scoring.py:313`), and the
  scoring loop iterates real slots (`mega_scoring.py:549-562`), but it is **collapsed to a count** in
  `MegaShapeCounts` and never threaded into `build_live_profile_row`.
- **dual-Mega (both foe slots Mega in one decision)** — not distinguishable: `n_mega_twins` counts
  foe-Mega branch *lines*, not distinct slots.
- **activation ordering / speed-tie** — `MegaEvaluationContext.activation_order` exists
  (`mega_scoring.py:78`) and `mega_activation_order_key` lives in `engine/speed.py:48-54`, but neither
  is in `MegaShapeCounts` nor the live row.

Slot/dual/order **are** recorded in a *separate* sidecar, `eval/opp_mega_trace.py` (per-response
`foe_mega_slots` `:100`, `scored_classes` `:77-80`) — but the I8-D runner instantiates only
`DecisionProfileWriter` (`i8d_runner.py:325`), never `OppMegaTraceWriter`, so that telemetry is **not
part of any verdict population**. The i8-latency design already flags this and defers "slot 0 and slot
1; dual-Mega and activation ordering" to "a separate approved spec"
(`docs/projects/champions/specs/2026-07-16-champions-i8-latency-design.md:1645-1651`). **This is that
spec.**

Live evidence to date (I7b-C smoke, `reports/champions-panel-v0-i7b-mega-smoke.md`): a foe-Mega
hypothesis appeared in only **1 of 17** scored decisions and only in **slot 1**; slot 0, dual-Mega,
and activation ordering were **never exercised live**. The mechanism is proven to *work*; opponent
Mega is **not** proven broadly exercised. That is the coverage gap Gate A closes.

---

## 2. Gate A — Opponent-Mega Coverage

**Goal.** Prove, on live battles, that the bot's opponent-Mega decision path is *actually exercised*
across the coverage cells below, each to a pre-registered minimum, before any strength number over
Mega formats is interpreted. Coverage is an **exposure** gate, not a latency or strength gate.

### 2.1 Coverage cells (the pre-registered dimensions)

A scored decision is assigned to zero or more **cells** based on the foe-Mega shape it actually
evaluated (all derived from the upstream `MegaEvaluationContext` / `ScoredResponseEvidence` facts in
§1). **Only positive, actually-scored contributions count** — a cell credit requires that the
foe-Mega branch(es) defining it were genuinely enumerated **and scored** in that decision, never
merely eligible or hypothesised. The cells:

| Cell | Predicate (on a scored active decision) |
|---|---|
| `slot0` | a foe-Mega hypothesis in foe **slot 0** was scored |
| `slot1` | a foe-Mega hypothesis in foe **slot 1** was scored |
| `both_foe_slots` | foe-Mega hypotheses in **both** foe slots were scored in the same decision |
| `order_tie` | a foe-Mega **activation-order tie** was scored: **exactly two** mutually-reversed own-/foe-Mega activation orderings, **each carrying weight `0.5`**, and **both** orderings were scored in that decision |

`both_foe_slots` implies both `slot0` and `slot1` on that decision; `order_tie` is independent of the
slot cells. The **`order_tie` predicate is exact** (D-3): it is satisfied **only** when the decision
enumerated the two mutually-reversed activation orderings of an own-Mega vs foe-Mega interaction, each
carrying the `0.5` tie weight (a genuine speed tie, `mega_activation_order_key` non-strict —
`engine/speed.py:48-54`), and **scored both** — never any decision that merely contained a Mega, and
never a strict speed inequality (which yields a single ordering).

### 2.2 Coverage telemetry (new — contract, not implementation)

The verdict population must be computable **from the live decision-profile dataset alone**, because
that is the only artifact the runner/validator read (§1). Therefore the coverage run must record, on
each active-valid live row, the per-decision facts needed to assign cells:

- `foe_mega_slots`: the set/flags of foe slots for which a Mega hypothesis was scored (enables
  `slot0`, `slot1`, `both_foe_slots`).
- `foe_mega_order_tie`: whether an `order_tie` branch was scored — the two `0.5`-weighted
  mutually-reversed own-/foe-Mega orderings both scored (enables `order_tie`).

**Approach (confirmed direction):** extend `MegaShapeCounts` (and `build_live_profile_row`) with these
fields, threaded from the already-existing upstream `MegaEvaluationContext.foe_mega_slot` /
`.activation_order` — **not** by wiring `opp_mega_trace` into the runner, because the verdict dataset
never reads that sidecar. This bumps the decision-profile schema to **`v3`**, and the v3 migration is
**binding on all four of**:

1. **both dataset validators** — the strict live-dataset validator *and* the offline/profile
   validator tier are updated to accept and check the new fields;
2. the **single-schema-version-per-dataset** rule is preserved (no v1/v2/v3 mixing within one dataset);
3. **full v1/v2 backward compatibility** — existing v1 and v2 rows and datasets still validate
   unchanged; the new fields are treated as absent (not null) on pre-v3 rows;
4. **all frozen evidence bytes remain untouched** — no existing `data/eval/**` dataset is rewritten,
   re-validated into v3, or otherwise altered.

**This is behavior-neutral telemetry** (adds recorded fields; must not change any decision output) —
the golden decision-equivalence discipline from the Lever-A/B slices applies. The actual code lands in
the *implementation plan* (a later step), not here.

### 2.3 Pre-registered exposure requirement (per cell)

The gate PASSes only if **every** cell reaches its pre-registered minimum number of active-valid
decisions from a pre-registered minimum number of **distinct battles** (a per-cell echo of I8-D's
aggregate floor `I8D_MIN_ACTIVE_DECISIONS=60` / `I8D_MIN_DISTINCT_BATTLES=20`,
`i8d_runner.py:28-31`). **Ruled (D-2):**

| Cell | min active-valid decisions | from ≥ distinct battles |
|---|---|---|
| `slot0` | 30 | 10 |
| `slot1` | 30 | 10 |
| `both_foe_slots` | 15 | 6 |
| `order_tie` | 15 | 6 |

**Only positive, actually-scored contributions are counted** toward a cell (§2.1). The caps stay at
**`MAX_BATTLES = 200`** and **`MAX_SCORED_DECISIONS = 2000`** (D-2). Rationale: enough per cell that a
single lucky battle cannot satisfy it (distinct-battle floor), scaled below the aggregate-latency
floor because four cells must each be met within the caps. These are a **floor to prove exposure**,
never lowered to rescue a run.

### 2.4 Coverage schedule (engineered — may target hard cases)

Coverage **may deliberately engineer** matchups that force the hard cells (**ruled, D-3**). This is
legitimate *because coverage is not strength* and its data is never used for the strength verdict
(§4). Requirements:

- A fixed, content-hashed coverage schedule (its own `schedule_hash` / `panel_hash`) built from
  Champions teams whose compositions guarantee foe-Mega hypotheses in **slot 0**, in **slot 1**, in
  **both foe slots**, and in an **`order_tie`** (§2.1) configuration.
- Coverage teams **may reuse already-"touched" teams** (e.g. `rain_offense`, the repo's proven
  foe-Mega exposure vehicle) and/or newly engineered coverage teams — **ruled (D-3): a touched
  engineered coverage panel is allowed.** Their only job is to *exercise* the path.
- **Hard firewall (ruled, D-3):** the engineered coverage team set and the strength-holdout team set
  (§3) **must be disjoint and strictly separated** — coverage team choice must never be tuned to, or
  leak into, the strength holdout, and vice-versa (§4, anti-co-optimization).
- **Per-cell offline constructibility proof (ruled, D-3):** **before implementation, each of the four
  cells must have a real offline proof that the engineered schedule can actually produce it** — a
  concrete board/team construction, verified **offline** (no live run), showing the scoring path
  enumerates and scores exactly the branch(es) the cell requires (e.g. a genuine `order_tie` with the
  two `0.5`-weighted reversed orderings). A cell without a passing constructibility proof blocks the
  coverage implementation.
- A small engineered coverage panel (e.g. `panel_champions_coverage_v0`) with matchups selected to hit
  each cell; exact team compositions and the four constructibility proofs are pinned in the impl plan.

### 2.5 Seeds, caps, provenance (independent from I8-D and from Gate B)

Reuse the I8-D provenance *pattern* with **its own** identifiers so nothing pools:

- Distinct `seed_base` (**PROPOSED** `"champions-coverage-v0"`), distinct `config_hash` /
  `schedule_hash` / `panel_hash`, and a distinct frozen output tree
  (**PROPOSED** `data/eval/champions-panel-v0/coverage-v0/`).
- Server-side Channel-A seeding proven via `SHOWDOWN_BATTLE_SEED_BASE` + `SHOWDOWN_EVAL_SEED_LOG`,
  seed-log alignment verified post-run (as `seeding.py` / `i8d_runner.py:136-154`).
- Fail-closed provenance: dirty-tree refusal, panel/team re-hash before battle 1, whole-run atomic
  staging + single `os.replace` publish (as `i8d_runner.py`, `cli.py` provenance locks).
- D-2 caps on the coverage run: **ruled (D-2)** — `MAX_BATTLES=200` / `MAX_SCORED_DECISIONS=2000`.

### 2.6 Verdict — PASS / FAIL / INCONCLUSIVE (and: a technical abort is *not* a verdict)

The verdict is three-way, computed **only** from a fully-completed, validated coverage run's frozen
dataset:

- **PASS** — every cell in §2.3 met **both** its decision minimum **and** its distinct-battle minimum
  (`stop_reason = coverage_floor_met`), with no safety failure.
- **INCONCLUSIVE** — a **cap** (`max_battles` / `max_scored_decisions`) **truncated the run before the
  fixed schedule completed**, so cell satisfaction is indeterminate: the un-run remainder of the
  schedule might have met the cells. No coverage claim; re-run with an adjusted budget under separate
  authorization. **This is the *only* INCONCLUSIVE path** — reaching the end of the schedule is never
  INCONCLUSIVE.
- **FAIL** — a real, non-abort **negative** gate outcome: **(a)** a **safety failure** (the bot
  produced an illegal or invalid choice on a foe-Mega decision — the Mega decision path is behaviorally
  broken); or **(b)** the fixed schedule ran **to completion** (`schedule_exhausted`) with **≥1 cell
  below its floor** — the pre-registered, per-cell offline-constructibility-proven schedule (§2.4)
  failed to deliver the required exposure, which is a schedule/mechanism **defect, not indeterminacy**.
  A schedule-exhausted shortfall may **not** be relabeled INCONCLUSIVE or rescued by re-running; it
  requires a new, separately-approved pre-registration. FAIL is a verdict about the candidate/schedule,
  never about the run's plumbing.

**A technical abort is *not* a verdict.** A dirty tree, seed-log mismatch, provenance/hash mismatch, a
server/battle infrastructure failure, a parser crash, or zero battles created ⇒ the run is **void and
discarded** — no PASS/FAIL/INCONCLUSIVE is recorded — and it is re-run only under a separate
authorization. Aborted-run logs are scratch diagnostics, never frozen and never pooled (as I8-D: "a
technical abort is not a verdict; this run is").

`stop_reason` maps one-to-one to the verdict for a completed run: **`coverage_floor_met` ⇒ PASS**
(all cells met, stopped early); **`schedule_exhausted` ⇒ FAIL** (schedule ran to the end with a cell
still below floor — §2.6(b)); **`max_battles` / `max_scored_decisions` ⇒ INCONCLUSIVE** (a cap
truncated the run before the schedule completed). **Composition is fixed in advance and never
re-optimized toward a desired verdict**: the coverage schedule, cells, and floors
are frozen (content hashes) before the run; a failing or inconclusive run may not be "fixed" by
relaxing a floor or reshaping cells post-hoc — that requires a new, separately-approved
pre-registration.

---

## 3. Gate B — Independent Strength Holdout

**Goal.** Measure Champions play strength on **fresh, independent, sealed** teams/matchups that have
never informed development, and render a pre-registered GO / NO-GO / UNDERPOWERED verdict — run
**only after Gate A PASS**, on its own schedule/seeds/dataset, its data never mixed with coverage.

### 3.1 The contamination finding (grounded — load-bearing)

**No untouched team set exists anywhere in the repo.** Every committed team — including all four
teams nominally labelled "held-out" — has been used in dev/parser/safety/latency work:

- Champions `rain_offense` (nominally held-out) is the **most-contaminated** team: the foe-Mega
  exposure vehicle across the entire Champions I-series (dedicated parser validation, I5, I6, I7a,
  I7b). Champions `disruption` (held-out) was used in the I5 smoke.
- Champions dev (`goodstuff`, `tailwind_offense`, `trick_room`) are the I8-D live-gate matchups.
- The Reg-I "held-out" pair (`balance_held`, `tailwind_held`) is *also* spent — consumed by three
  McNemar held-out gates (T6 baseline, mustreact-0.8, cvar-neutral).
- The **VGC-Bench "72 holdout teams"** are an **external, PROPOSED-not-approved** compat study
  (`docs/ROADMAP.md:314-333`); no team files are in the repo, and they are `gen9vgc2025reg*`
  replay-header aliases classified `MECHANICALLY_SIMILAR_BUT_NOT_TARGET`
  (`…champions-panel-v0-design.md:96-99`) — not Champions-live drop-ins.

**Consequence + ruling (D-1a):** an independent Champions Strength holdout **cannot** be assembled
from existing teams, and VGC-Bench is out of scope for v0. It is therefore built as **six new,
tournament-legal `gen9championsvgc2026regma` teams from a bot-results-blind source/curation, sealed
(provenance, archetypes, legality, content hashes) before first access** (§3.4). **No existing repo
team and no VGC-Bench import for Gate v0.**

### 3.2 The strength comparison (ruled — D-4)

The holdout renders a **paired A-vs-B strength comparison** with a fully pre-registered design:

- **Candidate A** = the current Champions heuristic agent. **Baseline B** = the hero-agent
  `max_damage`. A and B are the two *hero* configurations under comparison; they differ **only** in the
  hero agent, run on the identical (fixed, standard Champions) hero team over identical matchups.
- **Opponent policies** = `{heuristic, max_damage}`.
- **Schedule** = the **6 fresh holdout teams (§3.1) as the opponent-team axis × 2 opponent policies ×
  15 seeds = 180 paired battle-keys** per configuration. A and B play the **identical** 180
  battle-keys — the same `(holdout_team, opponent_policy, seed)` triples and matchups — so the
  comparison is paired.
- **Decision rule:** exact two-sided binomial **McNemar** on the discordant win/loss pairs
  (`eval/stats.py`), Wilson per-cell CIs. Pinned constants (`stats.py:15-18`):
  `N_DISCORDANT_MATH_FLOOR = 6`, `N_DISCORDANT_CLAIM_MIN = 10`. **`n_discordant < 10` ⇒ UNDERPOWERED**
  (no GO/NO-GO/equivalence/regression claim). **GO follows the existing positive McNemar contract
  unchanged** — precedence `SAFETY-FAIL > UNDERPOWERED > GO > NO-GO`, positive-evidence-only, no
  losing-cell flip, not weak-policy-only. **No additional baseline in v0.**
- **Baseline manifest:** a **new Champions-specific baseline manifest** is frozen for this gate; the
  Reg-I `config/eval/baselines/heuristic-v1.json` is **not reused**. The manifest re-hash guard
  (`eval/baseline.py`, `BaselineDriftError` on any panel/team/schedule/patch drift) applies to the new
  Champions manifest.
- **Pairing integrity:** as `eval/pairing.py` — A and B must share `schedule_hash` / `seed_base` /
  `panel_hash` / `format_id` and differ only in `config_hash`; a missing pair aborts the analysis
  (a technical abort — not a verdict, §2.6).

### 3.3 Held-out discipline (grounded — contamination protection)

The holdout inherits the T6 held-out contract
(`docs/projects/evaluation/specs/2026-07-10-t6-heldout-gate-baseline-design.md`,
`eval/heldout_ledger.py`):

- **Append-only ledger** `config/eval/heldout_ledger.jsonl`: **one gate attempt per `config_hash`
  lineage** (`check_access` → `AccessBudgetError` without an approved justification); git-history
  append-only test.
- **Leakage-drift test (repo-wide, with an explicit allowlist — P1):** the T6 R4 check (`team_hash` /
  `team_path` / `team_id` not in committed dev schedules under `config/eval/schedules/`) is far too
  narrow. The holdout guard is **repo-wide**: a scan of git-tracked content for each holdout identifier
  (`team_hash`, `team_path`, `team_id`, packed/`.txt` content) must return **zero hits outside the
  holdout's own operational artifacts.** The **allowlist** — the *only* places a holdout identifier may
  legitimately appear — is exactly: **(i)** the holdout **team files** under `showdown_bot/teams/`;
  **(ii)** the holdout's **own dedicated strength-holdout schedule and panel** (the gate config that
  *must* reference the six teams to run them); **(iii)** the **ledger/manifest** registration
  (`heldout_ledger.jsonl` + the Champions baseline manifest); and **(iv)** the holdout's **own frozen
  evidence tree** (`data/eval/champions-panel-v0/strength-holdout-v0/`, once the gate runs).
  **Everywhere else must have zero hits** — every *dev*, *coverage*, *latency/I8-D*, *smoke*, and
  *datagen* schedule and panel under `config/eval/`, every *other* team file under
  `showdown_bot/teams/`, and all *other* frozen datasets under `data/eval/`, plus `reports/`, docs,
  tests, and tooling. The holdout set must additionally be **disjoint from the engineered coverage
  panel** (§2.4) by hash. Beyond exact identity, a **content-overlap check at sealing** flags any
  holdout team whose species set substantially overlaps a touched or coverage team for manual
  disjointness review (near-duplicates are not independent). Once sealed, the holdout teams are
  registered and **kept out of every schedule and panel except their own dedicated strength-holdout
  schedule/panel** — this is what keeps them independent and sealed.
- **Mandatory report banner:** "HELD-OUT RUN — these numbers must never inform tuning." Per-cell
  numbers recorded, never acted on for development.

### 3.4 Independence, blindness, and sealing (ruled — D-1a sharpened; P1)

**Freshly created is not the same as independent.** Six brand-new teams chosen while looking at the
bot's results would still be contaminated. Independence here is a positive, verifiable property:

- **Blind source/curation (ruled, D-1a):** the six teams come from a source or curation process that
  is **blind to the bot's own results** — no team is selected, kept, or dropped because the bot wins,
  loses, exposes a cell, or performs any particular way on it. The sourcing rationale (archetype
  targets, tournament basis) is fixed *before* any team is ever exposed to the bot.
- **Seal before first access:** the teams' **provenance, archetypes, legality, and content hashes are
  recorded and sealed *before* the first time the bot ever sees or plays them.** After sealing they
  are not inspected, tuned against, or reshaped; the sealed hashes are exactly what the gate verifies
  at run time (and are registered in the ledger + leakage-drift, §3.3).
- **Natural, not engineered:** representative Champions teams/matchups — **not** engineered to be easy
  or hard (that is the coverage panel's job, §2.4), and not curated toward a desired strength outcome.
- **Firewall (ruled, D-3):** the engineered coverage team set (§2.4) and the holdout team set are
  **disjoint and strictly separated**; neither selection may optimize the other, and holdout results
  never reshape coverage nor vice-versa.
- **v0 provenance rule (ruled, D-1):** the six are **new**, tournament-legal
  `gen9championsvgc2026regma` teams — **no existing repo team and no VGC-Bench import for Gate v0.**

### 3.5 Seeds / caps / provenance / Kaggle (independent)

- **Distinct** `seed_base`, schedule, dataset, and verdict from Gate A **and** from dev-strength.
  **PROPOSED** `seed_base "champions-strength-holdout-v0"`, output tree
  `data/eval/champions-panel-v0/strength-holdout-v0/`.
- **Kaggle** may be used **only as its own hardware/date stratum and never pooled** with the fixed
  Windows measurement host (`docs/ROADMAP.md:36-38`, `docs/PROJECT_INDEX.md:46-47`; enforced via the
  per-run provenance chain — `config_hash`/`panel_hash`/`showdown_commit`/`server_patch_hash` — and
  separate output trees). A Kaggle strength stratum is a *separate* pre-registered run, never merged
  into a Windows dataset.
- Atomic evidence (staging + single publish), dirty-tree fail-closed, seed-log verified.

---

## 4. Shared rules (both gates share these; the gates stay operationally independent)

**Shared (one document to prevent contract drift):** provenance locks (dirty-tree fail-closed,
content-hashed schedule/panel/config, atomic staging+publish, seed-log verification), contamination
protection (ledger + leakage-drift + baseline-drift), and atomic frozen evidence.

**Independent (must never couple):**

1. **Separate schedules, seeds, datasets, and verdicts** for coverage vs strength.
2. **Coverage data is never used for the strength evaluation** — the strength verdict is computed
   only from the strength dataset.
3. **Strength runs only after a coverage PASS.** A coverage INCONCLUSIVE/FAIL leaves Strength NO-GO.
4. **Each run is separately authorized** — coverage run, then (if PASS) strength run, each on its own
   explicit go. No spontaneous runs.
5. **Windows and Kaggle are never pooled** — separate hardware/date strata, separate datasets.
6. **Anti-gaming:** every composition (cells, floors, schedules, teams, sample sizes) is
   pre-registered and content-hashed before its run and **never re-optimized toward a wanted
   result**; coverage and holdout team choices are independent (§2.4, §3.4).

---

## 5. Shared candidate identity & verdict coupling

- **Shared candidate identity (P1).** The gates must pin and verify **one and the same candidate
  identity** — the identical bot version/config under test, captured as a candidate identity hash
  (agent config + `git_sha` + relevant `config_hash`) recorded in each gate's provenance. **Coverage
  and strength must run on the identical candidate identity**, and a coverage PASS licenses a strength
  run **only** for that same identity. If the candidate changes (any change that alters its identity
  hash), the coverage PASS is void for the new candidate and coverage must be re-run for it. Coverage
  exposes candidate *X*; strength measures candidate *X*; a GO applies to candidate *X* only. Candidate
  A (§3.2) **is** that shared candidate; Baseline B is the reference, not a separately-gated candidate.
- **Latency linkage (P1).** The latency PASS must correspond to the **same candidate identity that
  runs coverage and strength** — the one carrying the v3 coverage telemetry (§2.2). **Decision-
  equivalence does *not* carry the latency PASS over:** behavior-neutral telemetry keeps *decisions*
  byte-identical but adds recorded fields and work, which can change *latency*; a prior latency PASS on
  a decision-equivalent-but-different candidate does **not** satisfy this gate. The I8-D latency gate is
  therefore **re-run on the final candidate identity** (with the coverage telemetry present) and must
  PASS before any Strength claim. The existing `3db4ac7` PASS stands as evidence for *its* candidate
  only; it does not transfer.
- Gate A PASS authorizes *only* running Gate B (separately), for that same candidate. It makes **no**
  strength claim.
- Gate B GO is a strength claim **only** if Gate A PASSed **for the same candidate identity** **and**
  Gate B is not UNDERPOWERED and shows no losing-cell flip (per `stats.py` precedence).
- **Champions Strength stays NO-GO** until, **for one and the same candidate identity**: latency PASS
  **and** coverage PASS **and** an independent-holdout GO. Any one missing ⇒ NO-GO.

---

## 6. Non-goals (this spec)

- **No** code, test code, server, battle, run, evidence, benchmark, push, PR, or merge.
- **No** reuse of any dev/parser/I5/I6/I7 team as the strength holdout.
- **No** change to the I8-D latency gate, its budget, or its frozen evidence.
- **No** pooling of coverage and strength data, or of Windows and Kaggle data.

---

## 7. Decisions (ruled at review, 2026-07-20)

All four are **closed**; the body sections now reflect them.

- **D-1 → D-1a (sharpened).** Independent holdout = **six new, tournament-legal
  `gen9championsvgc2026regma` teams from a bot-results-blind source/curation, sealed (provenance,
  archetypes, legality, content hashes) before first access**; **no** existing repo team and **no**
  VGC-Bench import for Gate v0. (§3.1, §3.4)
- **D-2 → confirmed.** Per-cell floors `slot0 30/10`, `slot1 30/10`, `both_foe_slots 15/6`,
  `order_tie 15/6`; only positive, actually-scored contributions counted; caps `MAX_BATTLES=200` /
  `MAX_SCORED_DECISIONS=2000`. (§2.1, §2.3)
- **D-3 → confirmed (corrected predicate).** An engineered coverage panel from already-touched teams
  is allowed and strictly firewalled from the holdout; `order_tie` = exactly two mutually-reversed
  own-/foe-Mega activation orderings, each weight `0.5`, both scored; a real **offline
  constructibility proof per cell** is required before implementation. (§2.1, §2.4)
- **D-4 → fixed.** Candidate A = current Champions heuristic; Baseline B = hero-agent `max_damage`;
  opponent policies `{heuristic, max_damage}`; schedule `6 teams × 2 policies × 15 seeds = 180` paired
  battle-keys per config, identical seeds/matchups for A/B; a **new Champions-specific baseline
  manifest** (Reg-I `heuristic-v1` **not** reused); `n_discordant < 10 ⇒ UNDERPOWERED`, GO per the
  existing positive McNemar contract; no additional baseline in v0. (§3.2)

**Additional binding (review).** The v3 telemetry migration binds **both** dataset validators, the
**single-schema-version-per-dataset** check, and **full v1/v2 backward compatibility**, with **all
frozen evidence bytes untouched** (§2.2).

---

## 8. Sequencing after approval (for reference; not authorized here)

Approve this spec → write the TDD **implementation plan** (coverage telemetry + validator, engineered
coverage schedule with the four per-cell constructibility proofs, coverage exposure-gate + verdict;
independent strength-holdout schedule + verdict; new Champions baseline manifest; repo-wide leakage
guard; atomic evidence + provenance + contamination protection) → build offline, full suite, review,
PR, merge (**no live runs**) → **re-run the I8-D latency gate on the final candidate identity** (the one
carrying the v3 telemetry, §5), separate authorization, and it must **PASS** → **coverage run**
(separate authorization); if PASS → **strength-holdout run** (separate authorization) → freeze evidence
+ report → only then evaluate Champions Strength **GO / NO-GO**. Strength stays **NO-GO** until **all
three** gates — latency (re-run), coverage, and independent holdout — pass for the **same candidate
identity**.


---

# Amendment A1 — 2026-07-22 — APPROVED (owner decision)

**Scope: narrow, Gate B only.** Nothing above changes; no other gate is affected.

## A1.1 Opaque internal holdout team IDs

The six holdout teams carry **opaque internal IDs** — a fixed `gbh_*` set, assigned in the frozen
selection order (selection index 1 first). Neither the concrete IDs nor their mapping to the public
`PC…` source IDs is written here.

Only the **mapping** from public source ID to opaque internal ID is exclusive to the holdout manifest. The internal IDs themselves necessarily appear in the allowlisted operational artifacts — team filenames, the panel, the baseline manifest and the run's own evidence — and that is fine, because those are exactly the places §3.3 permits a holdout identifier to live. What must never happen is the *mapping* leaking, or an internal ID appearing anywhere outside those artifacts. Documents and tests therefore hardcode neither: they read both from the manifest.

The mapping's home is `config/eval/holdout/champions_strength_holdout_v0_manifest.json`.

*Why opaque, and why not the obvious choices:* §3.3's leakage guard exists so a holdout identifier
appears nowhere but the holdout's own operational artifacts. Source-derived IDs (`pc…`) would put
them in every document describing the source. A `holdout_N` scheme was measured against the real
scanner and produced **121 identifier hits across 7 files** — it collides with this repo's
long-standing *fixture* vocabulary in the plan and six existing test files. The adopted scheme
measures **zero**.

## A1.2 One additional allowlisted directory

§3.3's allowlist gains **exactly one** entry:
`docs/projects/champions/audits/2026-07-22-task13-vgcpastes-source-evidence/`.

*Why this is necessary, not a loosening:* the six sealed `.txt` files are **deliberately
byte-identical** to the pastes frozen there — that equality is the evidence nothing was altered
between published source and sealed artifact. The raw-payload leg uses those bytes as its needle,
so without this entry the guard reports the holdout's own authoritative provenance as a leak.
Renaming cannot avoid it: the needle is content, not name.

**Deliberately NOT allowlisted**, each of which must keep failing the scan: any broader `docs/`
prefix; the sibling selection-audit file; any test file; any report, dataset, schedule, panel or
team file elsewhere. The entry is a slash-terminated prefix, so a similarly-named sibling directory
does not inherit the exemption.

## A1.3 The Gate B baseline manifest is a pre-run static definition

Gate B's baseline manifest defines **Baseline B (`max_damage`) and its static environment**, frozen
*before* the run. Baseline B's *result* does not exist until the separately-authorized arm-B run.

- `reference_jsonl` / `reference_sha256` are **not** part of this contract: a result file cannot
  exist before the run, and committing one afterwards would change the candidate SHA the gate is
  bound to.
- There is **no** `dev_schedule_path` — Gate B's schedule is canonically **re-derived from code**
  (`build_strength_holdout_schedule`), not loaded from YAML.
- The generic T6 contract (`load_baseline`/`verify_baseline`) and every existing Reg-I manifest
  stay **byte- and behaviour-identical**. Gate B gets an **additive** loader/verifier; the generic
  one is not relaxed, reinterpreted, or given optional dummy fields.

The Gate B verifier re-derives panel hash, hero and opponent team content hashes, the canonical
schedule hash, and the server/seed pins from the current clean checkout, failing closed on drift.
