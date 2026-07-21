# Champions Coverage `both_foe_slots` Zero-Exposure — Diagnosis

**Status:** APPROVED (2026-07-20, after 4 review rounds — 3 P1s + 1 P1 + 2 P1s + 1 P1, all fixed and
re-verified). **Diagnosis/design only.** No implementation, code, test code, server, battle, gate
run, evidence, push, PR, or merge is authorized by this document. Executed by the separate,
separately-authorized plan `docs/projects/champions/plans/2026-07-20-champions-both-foe-slots-remediation.md`.

**Date:** 2026-07-20 · **Base:** `main @ cb05fca` · **Owner:** Champions strength track

**Purpose.** Diagnose, from frozen evidence and static code analysis only, why the live
`champions-coverage-gate` run on candidate `cbaa4b9` (frozen at
`data/eval/champions-panel-v0/coverage-v0/`, PR #40 @ `cb05fca`) scored **zero** decisions for the
`both_foe_slots` cell across all 50 of its scheduled battles, while `slot0` (82/50), `slot1`
(298/173), and `order_tie` (100/100) all cleared their pre-registered floors comfortably. Propose
2-3 remediation options with trade-offs and a recommendation. Separately, correct the
candidate-identity execution-order gap that let the coverage run execute against a candidate the
I8-D latency gate never actually verified.

## Non-goals (hard)

- **No code, no test code, no implementation.** This is a diagnosis producing a PROPOSED spec only.
- **No server, no battle, no gate run, no retry** of any kind.
- **No evidence change.** `data/eval/champions-panel-v0/coverage-v0/` and every prior frozen
  evidence directory are read-only inputs here, untouched.
- **No threshold, cell, or schedule weakening.** If `both_foe_slots` is not constructibly reachable
  in the real live schedule/team/policy combination that actually ran, that is named explicitly as
  a **design defect**, not worked around by loosening the floor, the schedule, or the cell
  definition.
- **No Strength claim.** Champions Strength remains `NO-GO`.

## Evidence base

Everything below is derived from: the frozen coverage-v0 evidence (`profile.jsonl`, `verdict.json`,
`seeds.jsonl`, `reports/champions-panel-v0-coverage-v0.md`, all byte-unchanged, PR #40 @ `cb05fca`);
the coverage manifest/panel/schedule code (`showdown_bot/src/showdown_bot/eval/coverage_schedule.py`,
`coverage_runner.py`, `coverage.py`, `coverage_verdict.py`); the Mega eligibility/projection/scoring
code (`showdown_bot/src/showdown_bot/battle/opponent.py`, `mega_scoring.py`, `decision.py`,
`showdown_bot/src/showdown_bot/engine/mega_projection.py`); the team-preview code
(`showdown_bot/src/showdown_bot/battle/team_preview.py`); the decision-profile schema
(`showdown_bot/src/showdown_bot/eval/decision_profile.py`); the offline constructibility proof
(`showdown_bot/tests/test_coverage_constructibility.py`,
`showdown_bot/src/showdown_bot/eval/profile_fixtures.py`); the team files under
`showdown_bot/teams/panel_champions_coverage_v0/`; and prior git history (commit `1be0adc`, the F1
review-fix that redesigned `cov_foe_slot0`/`cov_foe_slot1` for the same defect class this diagnosis
finds in `cov_foe_both`).

**Verified: zero source-code drift.** `git diff --stat cbaa4b9..cb05fca -- showdown_bot/src/` is
empty — the code analyzed here (checked out at `cb05fca`) is byte-identical to the code that
actually produced the frozen `cbaa4b9` evidence; only evidence/docs files changed between the two
commits.

**Headline finding, stated up front:** `both_foe_slots`, as currently specified (team
`cov_foe_both.txt` + the project's own deterministic team-preview algorithm + both opponent
policies' greedy per-turn scoring), is **not reliably constructible in real live geometry**. This is
a **design defect**, of the same class already found and fixed for `cov_foe_slot0`/`cov_foe_slot1`
(review finding F1, commit `1be0adc`) but never remediated for `cov_foe_both`. The root mechanism —
team preview brings both Mega-capable Pokemon but leads only one — is proven deterministically (§2,
independently re-derived from scratch, not merely reported) and, on its own, fully and exactly
explains the shape of every one of the run's 50 *active* decisions (§1): each occurs at
`decision_index=1`, where `foe_mega_slots` is `[1]` in all 50, never `[0]`, never `[0,1]`. Why the
battles' other ~397 decisions never show a dual-eligible state either is addressed separately (§3,
Layer 2): a corroborating, structurally-supported but not independently live-confirmed argument that
a benched Meganium's only path onto the field — a switch — is itself closed.

---

## 1. The 50 scheduled `both_foe_slots` battles, by policy

Manifest matchup indices 4 (`opp_policy=heuristic`) and 5 (`opp_policy=max_damage`), both
`opp_team=cov_foe_both`, cyclic at `seed_index % 8` over 200 battles → 25 seed_indices each, 50
total (indices 4,5,12,13,...,196,197). All 50 are present in the frozen `seeds.jsonl` (200/200
rows) and all 50 battle_ids (derived via `make_battle_id(schedule_hash, seed_index, seed)`) are
present in `profile.jsonl`.

Across these 50 battles: **447 total decision rows**, all `outcome=="ok"` (447/447 — zero
crashes/fallbacks/degraded-state in this subset), **exactly 50 with `foe_mega_active==true`** — one
per battle, always at `decision_index=1` (the battle's very first scored decision). Among those 50
active rows, `foe_mega_slots` is **`[1]` in all 50, `[0]` in zero, `[0,1]` in zero** —
`foe_mega_slots` never contains both 0 and 1 in *any* of the 447 rows, active or not. Every one of
the 50 active rows additionally shares `foe_mega_order_tie=true`, `n_mega_twins=149`,
`n_candidates=104` — a **perfectly uniform signature** across all 50 battles and both policies
(`measured_ms` is the only field that varies meaningfully). By contrast, the 50 `slot0`-target
battles show a real mix (`[0]`→80, `[1]`→23 across their active rows, including batches with
multiple decisions per battle), and the 50 `slot1`-target battles likewise (`[1]`→175, `[0]`→2) —
i.e. those cells' underlying battles show genuine variance, while `both_foe_slots`' battles do not.
This perfect, policy-independent uniformity is itself evidence of a deterministic (not
probabilistic) mechanism — confirmed in §2.

Independent sanity check: reimplementing `is_active_valid_live_row` + `coverage_cell_counts` from
scratch against the full 1956-row file reproduces `{slot0: 82/50, slot1: 298/173,
both_foe_slots: 0/0, order_tie: 100/100}` exactly, matching both `verdict.json` and the frozen
report byte-for-byte before any of the above per-cell breakdown is trusted.

## 2. Team-preview selection: were both Mega-capable opponents brought?

`cov_foe_both.txt`'s 6 Pokemon, verified against `showdown_bot/config/items/itemdata.json`: exactly
2 are Mega-capable — **Aerodactyl @ Aerodactylite** (team-sheet position 1) and **Meganium @
Meganiumite** (position 2).

`pick_team_preview_default` (`showdown_bot/src/showdown_bot/battle/team_preview.py:51-68`) is the
**single, deterministic, no-RNG** selection function used by every team-preview call site in the
repo — `max_damage_choice`, the `heuristic`/`greedy_protect` opponent policies, and the hero's own
live decision path all call the identical function. It scores each of a side's own 6 Pokemon from
its **own** moves only (never sees the opponent's team) via:
```
bring_score = 1.0 + 3.0*speed_control + 2.0*fake_out + 1.5*redirect
lead_score  = 3.0*fake_out + 2.5*speed_control + 2.0*redirect
```
brings the top-4 by `bring_score` (ties keep team-sheet order), then re-sorts those 4 by
`lead_score` for the first two (= the doubles leads).

**Independently computed from scratch** (real team file + real `effect_classes.yaml` move tags +
the exact formula above, not merely trusted from a report): Aerodactyl's Tailwind is tagged
`speed_control` (`effect_classes.yaml:20`) → `bring=4.0, lead=2.5`. Meganium's moveset (Solar Beam,
Weather Ball, Dazzling Gleam, Protect) carries **none** of the three scored tags (verified: none of
these four move IDs appear anywhere in `effect_classes.yaml`, and Dazzling Gleam is not the
Fake-Out-equivalent special case) → `bring=1.0, lead=0.0`. Sneasler's Fake Out is the hardcoded
special case (`meta.id=="fakeout"`) → `bring=3.0, lead=3.0`. Kingambit/Basculegion/Garchomp are all
untagged → `bring=1.0, lead=0.0` each.

Running the algorithm on these six scores: **bring-4 = {Aerodactyl, Sneasler, Meganium, Kingambit}**
(both Mega holders *are* brought) — **but leads = {Sneasler, Aerodactyl}** (`lead_score` 3.0 and 2.5,
the two highest). **Meganium and Kingambit start every battle on the bench.** This computation was
verified twice independently — once by hand-deriving it from the raw team file, the raw
`effect_classes.yaml`, and the raw scoring formula, and once by a separate research pass that ran
the real `pick_team_preview_default` function directly against the real team data — both agree
exactly, and both agree with §1's empirical `foe_mega_slots=[1]` (Aerodactyl, the lone leading Mega
holder, occupies foe slot `b`/index 1; Meganium never appears because it is never active at
`decision_index=1`).

**Answer: yes, both are brought; no, only one (Aerodactyl) ever leads — deterministically, every
time, both policies.**

## 3. Lead/switch history: were both ever simultaneously active?

Not at `decision_index=1` (§2: Meganium is benched from turn 1, every battle). For Meganium to
*ever* become active while Aerodactyl is still un-Mega'd, it would have to enter via a switch.
Static tracing of both opponent policies' switch-decision code found this path effectively closed,
for two independent, compounding reasons:

- **Voluntary switching is structurally suppressed.** `max_damage_choice`
  (`showdown_bot/src/showdown_bot/battle/baselines.py:99-119`) scores only damaging moves; a switch
  contributes 0, and ties keep the first-enumerated candidate — moves are enumerated before switches
  (`battle/actions.py:90-95`) — so `max_damage` picks an attack over a voluntary switch whenever any
  damaging move exists, which is essentially every turn. No dedicated "which bench mon to send in"
  scoring exists anywhere in `battle/` or `eval/` for either policy; `PlannedAction` for a switch
  carries no species/target field at all (`battle/resolve.py:26-46`), and the multi-turn condition
  rollout explicitly does not model hypothetical incoming Pokemon
  (`battle/rollout.py`).
- **Even a *forced* replacement (a lead faints) plausibly arrives too late.** Aerodactyl's own Mega
  form is a strict, drawback-free stat upgrade (`showdown_bot/config/species/speciesdata.json`:
  Aerodactyl 80/105/65/60/75/130 → Aerodactyl-Mega 80/135/85/70/95/150, same typing). Both policies'
  per-turn greedy scoring treats a Mega variant as a first-class candidate with no opportunity-cost
  or timing model (`baselines.py:122-213` for `max_damage`; the equivalent turn-scoring in
  `mega_scoring.py` for `heuristic`), so Aerodactyl — a guaranteed lead — very likely Mega-evolves on
  turn 1, before any KO could even occur to force a Meganium swap. This closes the window even in
  the one theoretically-live path.

**This second mechanism is corroborating, not independently confirmed** — it is well-supported by
the code's structure (no opportunity-cost model, Mega scored as a first-class immediate-turn
candidate) but was not traced against `heuristic`'s full opponent-response/world-sampling machinery
in `mega_scoring.py`, and neither mechanism was verified against a live battle log (none exists —
no server run is authorized here). §2's team-preview mechanism **alone** already deterministically
and completely explains why all 50 *active* (`decision_index=1`) rows show only Aerodactyl; closing
the question for the battles' other ~397 decisions relies on this section's
corroborating-but-unconfirmed argument together with the raw data (§1: zero of those ~397 rows ever
register `foe_mega_active` again — consistent with, but not itself proof of, a fully closed
switch-in path).

**Answer: not verified as ever occurring in the frozen evidence (consistent with §1: 447 rows, 0
distinct-active-battle sightings of slot 0 outside `decision_index=1`), and static analysis finds
the path structurally narrow-to-closed via two independent, compounding mechanisms — though, unlike
§2's team-preview proof, not independently confirmed live.**

## 4. Mega eligibility and activation: were both slots ever generated as positive scoring hypotheses?

The **code**, independent of this specific team, structurally supports a dual-slot hypothesis:
`foe_mega_eligibility()` (`showdown_bot/src/showdown_bot/battle/opponent.py:165-212`) iterates both
active opponent slots with no early return or first-match bias, and **can and does** return both
`'a'` and `'b'` keys simultaneously when both are eligible. `score_evaluated_variants`
(`showdown_bot/src/showdown_bot/battle/mega_scoring.py:564-596`) computes
`foe_mega_slots = sorted({...})` as a genuine set that can equal `{0,1}`, and loops over it, calling
`compose_mega_projection_branches` **once per eligible slot** (each individual call handles at most
one foe-side activation — correct, since Mega Evolution is once-per-side-per-battle, so a single
projected board can never show both foe mons *already Mega'd* at once — but the **decision-level**
loop composes both slots' hypotheses as parallel, independently-scored branch-groups, pooled into
one `aggregate_score`). `_choose_best_mega` (`battle/decision.py:783-945`) forwards the full,
unreduced eligibility dict through without collapsing it.

This is proven not just by structure but by execution: multiple existing unit tests
(`test_coverage_constructibility.py:53-62`, `test_coverage_origin_telemetry.py:60-62,107-126`) drive
a hand-built dual-eligible board through the **real, unmocked** `foe_mega_eligibility()` +
`score_evaluated_variants()` pipeline and assert `foe_mega_slots == (0, 1)` — and pass.

**In the live run, however, neither slot's *eligibility* was ever jointly computed with both foe
Pokemon present** — because (§2/§3) Meganium was never on the field at the point any decision was
scored. `foe_mega_eligibility()` only inspects `state.sides[opp_side]`'s **currently active**
Pokemon (`opponent.py:165-212`); an unfielded, benched Meganium is invisible to it. The code's
demonstrated capacity to represent a dual-slot hypothesis (this section) was therefore never
actually exercised live — not because the hypothesis-generation logic failed, but because its
precondition (both Mega holders simultaneously active) was never met (§2/§3).

**Answer: the code can generate this hypothesis and is proven to do so on a synthetic board; in the
50 live battles it was never given the opportunity to, because only one Mega-capable Pokemon was
ever on the field.**

## 5. Telemetry: did a real dual-slot state get lost between scoring and `foe_mega_slots`?

No. `build_live_profile_row` (`showdown_bot/src/showdown_bot/eval/decision_profile.py:306-382`)
reads `foe_mega_slots` directly off a `shape: MegaShapeCounts` object passed in by reference — not
recomputed independently. That same object instance is threaded, by keyword argument, through an
unbroken 8-hop call chain from `client/gauntlet.py`'s `profile_shape_sink` (created once per
decision, `gauntlet.py:671`) down through `agent_choose → choose_with_fallback →
heuristic_choose_for_request → _choose_best_ja → _choose_best → _choose_best_mega →
score_evaluated_variants`, which mutates it in place at the very end of scoring
(`mega_scoring.py:899-903`, `shape_sink.foe_mega_slots = tuple(sorted(_cov_scored_slots))`). There is
no separate/parallel computation path for the telemetry field that could diverge from what the
internal scoring pipeline actually saw.

**One real, code-confirmed narrowing mechanism exists, but is a different bug class from this
incident.** `predict_responses()` (`opponent.py`) only assigns a `foe_mega_slot` tag to opponent
Mega-twin responses with `weight > 0`; if response-weighting (protect priors, click-rate splitting,
cap truncation) drove one *already-eligible* slot's weight to exactly zero, `foe_mega_slots` would
legitimately record only the surviving slot even though eligibility saw both. This is proven live in
the codebase — `test_coverage_origin_telemetry.py::test_only_positively_scored_slots_count`
monkeypatches exactly this on the *same* dual-eligible synthetic board and shows `(0,1)` collapse to
`(0,)`. **This mechanism requires both slots to have been eligible in the first place** (§4: never
true here, since Meganium was never active), so it is not the operative cause in this run, but is
flagged here as a real, separate risk worth keeping in mind for future coverage cells that *do*
achieve simultaneous dual-slot activity: eligibility alone would not guarantee both are recorded.

**Answer: no — the observed telemetry faithfully reflects the internal scoring state (single-slot
eligibility, because only one Mega holder was ever on the field). No translation-loss bug exists in
this dataset.**

## 6. Offline constructibility proof scope

`test_both_foe_slots_matchup_is_constructible` (`test_coverage_constructibility.py:61-62`) asserts
only that `_shape_for(COVERAGE_PROOF_BOARDS["both_foe_slots"])` (which resolves to
`mega_decision_both_foe_slots_fixture`) yields `foe_mega_slots == (0, 1)`. That fixture
(`showdown_bot/src/showdown_bot/eval/profile_fixtures.py:158-165`) builds a `BattleState()` and
assigns `st.sides["p2"]["a"] = _meganium_holder()` / `st.sides["p2"]["b"] = _aerodactyl_holder()`
**directly, by Python object construction** — no team file is parsed, no team-preview function is
called, no lead is selected, no turn is simulated. The test file's own module docstring states this
explicitly and pre-emptively (written when the *sibling* F1 defect was fixed for slot0/slot1):

> "the proof boards above are DISCONNECTED synthetic fixtures — they prove the SCORING path can
> produce a cell's shape, but say nothing about whether the actual schedule TEAM ever reaches that
> shape through the REAL deterministic team-preview picker."

The same file adds two "real team leads its Mega holder" tests for `cov_foe_slot0`/`cov_foe_slot1`
specifically (`test_cov_foe_slot0s_real_team_leads_its_mega_holder_in_slot_a`,
`test_cov_foe_slot1s_real_team_leads_its_mega_holder_in_slot_b`, lines 111-124) — these parse the
*real* packed team files and drive them through the *real* `pick_team_preview_default`, exactly
closing the gap the docstring describes. **No equivalent test exists for `cov_foe_both` or
`cov_foe_tie`.** Git history confirms both `cov_foe_both.txt` and `cov_foe_tie.txt` have exactly one
commit each (`50fd16e`, original creation) and were untouched by the F1 remediation (`1be0adc`),
which touched only `cov_foe_slot0`/`cov_foe_slot1`'s team files, hashes, and tests.

The fixture's two hardcoded species (Meganium/Meganiumite, Aerodactyl/Aerodactylite) are not
coincidental: they match `cov_foe_both.txt`'s two Mega-capable
Pokemon exactly, by design intent (the implementation plan documents pinning "the exact
Champions-Mega species/speeds" from the fixtures into the real team). But the *placement mechanism*
is entirely disconnected from how a real battle would place them — and §2 shows that disconnection
is exactly where the defect lives: the fixture's hand-placement (one Mega holder per slot, both
simultaneously active) simply assumes away the team-preview step that, in the real team, benches
one of them.

**Answer: the proof establishes only that the scoring/classification code correctly labels a
`both_foe_slots` shape *if* handed one — never that the real schedule/team construction reaches
that shape. This is exactly the same scope gap already found (F1) and fixed for `slot0`/`slot1`;
here it was never closed, and the live run subsequently failed for precisely the reason the closed
gap would have caught in advance.**

## 7. Seed 137 fallback: scoped and confirmed unrelated

The run log's single non-`"ok"` decision-profile row (`profile.jsonl` line 1368, `outcome:
"fallback"`, `battle_id: fea99c6c0e37d626`) maps, via `seed_index=137` (`137 % 8 == 1` → manifest
matchup index 1 → `{opp_policy: "max_damage", target_cell: "slot0"}`), to a `slot0`-targeted
battle — **not** one of the 50 `both_foe_slots` battle_ids. This is the only anomaly of any kind in
the entire 1956-row dataset (all other 1955 rows are `outcome=="ok"`). It has no bearing on, and no
overlap with, the `both_foe_slots` zero-exposure — the two findings are fully independent, as the
frozen report (`reports/champions-panel-v0-coverage-v0.md:167-171`) already stated without
diagnosing either.

---

## Root-cause synthesis

**Layer 1 — team-preview/lead defect (proven, deterministic; fully sufficient to explain the shape
of the run's 50 active decisions on its own).** `cov_foe_both.txt`'s Meganium carries no
`speed_control`/`fake_out`/`redirect`-tagged move, so the project's own real, deterministic
`pick_team_preview_default` brings it but never leads it — every one of the 50 scheduled battles,
both policies, with zero variance. Every one of the run's 50 `foe_mega_active` rows occurs at
`decision_index=1` (§1), and Meganium is never active at that point, so `foe_mega_slots` can only
ever show Aerodactyl's slot **at those 50 rows**. This is the same defect class as F1 (commit
`1be0adc`), already found and fixed for `cov_foe_slot0`/`cov_foe_slot1`, never applied to
`cov_foe_both`. Layer 1 alone proves this for `decision_index=1`; on its own it does not account for
the same 50 battles' remaining ~397 decisions (§1), where the question is not "who leads" but "did
Meganium ever come in later" — that is Layer 2's question.

**Layer 2 — Mega-timing/switch-in race (structurally plausible, not independently confirmed live; a
consistent but unestablished account of the remaining ~397 non-first-decision rows).** For Meganium
to affect any decision after `decision_index=1`, it would have to be switched in while Aerodactyl is
still un-Mega'd (§3). Static tracing found this path structurally narrow-to-closed two independent
ways — voluntary switching is scored at 0 against any damaging move, and a forced switch-in likely
arrives only after Aerodactyl's own greedy turn-1 Mega-evolution has already claimed the slot — but
neither was verified against a live battle log. Layer 1 alone fully explains why every *active* row
shows only Aerodactyl (the proven, deterministic part). Layer 2 offers a plausible mechanism
consistent with the remaining ~397 rows (§1: zero of them ever register `foe_mega_active` again);
their exact later-turn causal mechanism is not established by the frozen profile — the data is
consistent with Layer 2's account without proving it is what actually happened in any specific
battle. **Neither the confirmed design defect nor the Option 1 recommendation depends on Layer 2
being correct**: the missing reliable first-decision construction (Layer 1 alone, §2) already
suffices for the redesign — guaranteeing both Mega holders lead at `decision_index=1` fixes the
gate's actual signal regardless of what, if anything, Layer 2 gets right about later turns.
Practically, this means a fix must specifically target **turn-1 simultaneous leads** (§2) rather
than relying on any later-game window, whose reliability Layer 2's unconfirmed account gives no
grounds to assume.

**Meta-level — the gap was pre-registered-detectable and was not caught pre-authorization.** The
`both_foe_slots` offline constructibility proof (§6) never tested the real team/preview path, unlike
its sibling cells after F1. Had the same "real team leads its Mega holder(s)" test class been
applied to `cov_foe_both` before authorizing the 200-battle live run, it would have failed exactly
as `cov_foe_slot0`/`cov_foe_slot1` originally did, and caught this offline at zero live-run cost.

## Design-defect classification (explicit, per this diagnosis's charter)

**`both_foe_slots`, as currently specified, is a confirmed design defect — not reliably
constructible in the real live geometry that actually ran.** This is not a scoring-code defect
(§4/§5: the code correctly represents and records dual-slot hypotheses when given the opportunity)
and not a schedule/floor defect (§1: 50 scheduled battles is generous relative to the 15/6 floor,
consistent with how comfortably the other three cells cleared theirs). It is a **team-construction
and pre-flight-verification gap**: the specific `cov_foe_both.txt` roster, run through the project's
own real team-preview algorithm, cannot reach the target cell, and no offline proof against the real
team was ever built to catch this before the live run was authorized.

## Candidate-identity workflow correction

Independently of `both_foe_slots`, this diagnosis also verified the mechanism behind the
already-documented candidate-identity gap (`reports/champions-panel-v0-coverage-v0.md`'s
"Candidate-identity gap" section; PR #40's review-fix `c2ff5b1`), to propose a durable correction.

**What the APPROVED spec currently says** (`docs/projects/champions/specs/2026-07-20-champions-coverage-strength-holdout-design.md`,
§5 and its execution-order flow near the end): latency and coverage "must run on the identical
candidate identity," and latency is "re-run on the final candidate identity ... before any Strength
claim." The execution-order arrow-flow reads: *build offline → full suite, review, PR, merge (no
live runs) → re-run I8-D latency on the final candidate identity, separate authorization, must PASS
→ coverage run (separate authorization) → ... → freeze evidence + report*. **This flow never
explicitly states whether an evidence-freezing commit/PR for the latency PASS itself is allowed to
land between "latency PASS" and "coverage run"** — and, in practice, exactly that happened: the I8-D
latency gate PASSed on `bd590c1`; PR #39 then merged that evidence, advancing `main` to `cbaa4b9`;
the coverage gate then ran live on `cbaa4b9` — a candidate the latency gate never actually verified,
caught only by a subsequent manual ultrareview, not by any automated check.

**Why this is not just a process slip:** `resolve_coverage_provenance()`
(`showdown_bot/src/showdown_bot/eval/coverage_runner.py:51-91`) and `resolve_i8d_provenance()`
(`showdown_bot/src/showdown_bot/eval/i8d_runner.py:157-199`) both derive `git_sha` independently, via
`git rev-parse HEAD` at the moment each gate is invoked — never pinned, never caller-supplied, never
cross-checked against any other gate's previously-recorded identity. No function anywhere in
`showdown_bot/src` compares one gate's `candidate_identity`/`git_sha` against another's. The
asymmetry is structural but narrower than `verdict.json` alone suggests:
`resolve_coverage_provenance()` computes and persists `candidate_identity` directly into its frozen
`verdict.json` (confirmed: `data/eval/champions-panel-v0/coverage-v0/verdict.json` has
`candidate_identity: "93cd419222683f75"`), while `resolve_i8d_provenance()` **never computes a
`candidate_identity` field at all** (confirmed against its actual body,
`i8d_runner.py:157-199`: it returns only `git_sha`/`config_hash`/`calc_backend`/`hero_agent`, no
composite identity), and the I8-D gate's frozen `verdict.json` persists neither `git_sha` nor
`config_hash` either (confirmed:
`data/eval/champions-panel-v0/i8d-live-post-coverage-harness/verdict.json` has neither field). **But
`git_sha`/`config_hash` are not, in fact, unrecoverable from the frozen evidence** — every row of
that same run's frozen `profile.jsonl` carries both (confirmed, row 1: `git_sha:
"bd590c13320627e2d03c86769257214fcf36d598"`, `config_hash: "594295543f13a55d"`), threaded there via
`LiveProfileContext` (`i8d_runner.py:294-297`). The real gap is narrower than "no automated way to
even read back the candidate identity": the raw ingredients are sitting in the frozen
`profile.jsonl`, but no `candidate_identity` field or composite value is ever computed or persisted
for I8-D anywhere, and no code today parses `profile.jsonl` to reconstruct or cross-check one. The
§5 requirement is enforced only by human/report discipline — not because the underlying data is
missing, but because nothing automates reconstructing `candidate_identity` from I8-D's frozen
`profile.jsonl` or comparing it against the coverage gate's.

**Corrected execution order (proposed, to replace the ambiguous step in the APPROVED spec):**

```
final code-merge SHA (candidate X, no further src changes intended)
        ↓
I8-D latency gate run on candidate X  →  must PASS
        ↓  (on PASS only)
champions-coverage-gate run on the SAME candidate X (freshly re-derived and equality-checked; not re-merged)
        ↓  (on PASS only)
independent Strength-holdout run on the SAME candidate X
        ↓
ONLY NOW: evidence freeze + report + docs reconciliation + merge for latency, coverage, and
holdout together (or as a tightly-sequenced set of PRs that do not themselves advance `main`
until all gates that must share candidate X have completed)
```

The key correction is procedural: **no evidence-freezing PR for an earlier gate advances the
candidate SHA while a later gate on the same candidate is still pending.** If evidence must be
frozen incrementally (as this project's established per-gate evidence/report/docs pattern does),
each such freeze must target a branch that does not merge to `main` until the full set of gates for
that candidate is complete. (A "merge the freeze immediately, then verify the newly-advanced `main`
SHA still matches the prior gate's candidate" alternative is not viable: the freeze-merge itself is
the commit that advances `main`'s SHA, so that check could never pass — the post-merge SHA is, by
construction, never equal to the pre-merge SHA a prior gate actually tested.)

**Recommended (future, separately-authorized) code-level hardening**, since human/report discipline
already demonstrably failed to catch this once: (1) add `candidate_identity`/`git_sha`/`config_hash`
fields to the I8-D gate's `verdict.json` output, matching what the coverage gate's `verdict.json`
already does; (2) have `run_coverage_gate` (and, symmetrically, any Strength-holdout runner) accept
an explicit path to the I8-D gate's `verdict.json` **from the same not-yet-frozen candidate-X
session** — the corrected order above defers freezing until latency, coverage, and holdout have
*all* completed on candidate X, so there is no committed/merged I8-D evidence to read back from at
coverage-run time; the cross-check must instead consume the I8-D run's own working-directory output
from that same session — compare its `candidate_identity` against the coverage gate's own
freshly-derived one, and **fail closed** (refuse to run, no verdict) on a missing path or a
mismatch. This turns §5's requirement from a report-writing convention into a fail-closed code
invariant enforced *within* the single candidate-X session, before any of the three gates' evidence
is frozen — not a check against previously-frozen evidence, since under the corrected order none
exists yet at that point. This is a recommendation for a future implementation slice, not authorized
here.

---

## Proposed solutions

### Option 1 (recommended): redesign `cov_foe_both`'s team so team-preview leads both Mega holders

**Not** by giving Meganium a tag-scoring move. F1's own verification (commit `1be0adc`'s message)
already established, via a real `validate-team` check against actual Showdown learnset data, that
Meganium cannot legally learn any `speed_control`/`fake_out`/`redirect`-tagged move — Fake Out and
Tailwind were both tried there and rejected as illegal for Meganium. "Give Meganium a tag" is not a
legal fix.

The fix instead mirrors F1's *actual* mechanism: **strip the rival tag-scoring move(s) so ties
resolve by team-sheet index**, not add a tag to Meganium. In `cov_foe_both.txt`'s current order —
(1) Aerodactyl/Tailwind, (2) Meganium, (3) Kingambit, (4) Sneasler/Fake Out, (5) Basculegion, (6)
Garchomp — Aerodactyl (`lead=2.5`) already wins a lead slot outright, and Meganium already wins a
bring-4 slot; the only obstacle is Sneasler's Fake Out (`lead=3.0`), which currently outranks
Meganium's tied `lead=0.0` for the second lead slot. Stripping Sneasler's Fake Out for an untagged
move (F1 replaced the identical Sneasler/Fake-Out pairing with Poison Jab in `cov_foe_slot0`/
`cov_foe_slot1`, an already-legal precedent for the same mon) leaves Meganium, Kingambit, and
Sneasler tied at `lead=0.0`; index tie-break then picks Meganium (position 2) over Kingambit
(position 3) and Sneasler (position 4) for the second lead slot — **no team-sheet reorder needed**,
unlike `cov_foe_slot1`'s fix. Since the coverage gate's signal fires at `decision_index=1` (before
either side has acted), guaranteeing both Mega holders lead closes Layer 1 completely and sidesteps
Layer 2 entirely (the timing race only threatens *later* turns; the floor (15 decisions/6 distinct
battles) is well within what a reliable first-decision hit across up to 50 scheduled battles would
provide, matching the pattern already proven for the other three cells).

- **Trade-off:** requires a code+test change (a single move swap on Sneasler in `cov_foe_both.txt`,
  re-derived `panel_hash`/`manifest_hash`/`COVERAGE_EXPECTED_PANEL_HASH`/
  `COVERAGE_EXPECTED_MANIFEST_HASH` constants, and a new "real team leads both Mega holders" offline
  test mirroring the F1 tests) before any live re-run can be authorized. Confined to a
  coverage-gate-only fixture; no production/live-play behavior changes. The specific replacement
  move for Sneasler still needs its own `validate-team` legality check before implementation — not
  done here, since no code/test change is authorized in this diagnosis slice.
- **Confidence:** high — this is the proven F1 pattern (strip-and-index-tiebreak, not add-a-tag),
  applied to the same defect class, on the exact same rival move (Sneasler's Fake Out) F1 already
  stripped once elsewhere, verified by the same mechanism (`pick_team_preview_default`,
  independently re-derivable and testable offline before any live cost is incurred).

### Option 2 (not recommended for this fix; flag as a separate future consideration): make Mega-stone-holding a first-class team-preview signal

Add a "carries an unused Mega stone" bonus to `_bring_score`/`_lead_score` in
`team_preview.py`, so any team's Mega holder(s) are preferentially led regardless of whether they
happen to also carry a tempo-tagged move.

- **Trade-off:** `pick_team_preview_default` is shared, production, **live-play** logic — used by
  the hero's own team-preview decision, not just this coverage-gate's synthetic opponents. This
  would be a real competitive-behavior change requiring its own dedicated behavior-neutrality
  analysis, design review, and separate authorization — a blast radius entirely disproportionate to
  fixing one coverage cell. Recommend logging this as a candidate follow-up item (the current
  formula's blind spot to Mega-holder status generally, independent of this incident) but not
  bundling it into the `both_foe_slots` remediation.

### Option 3 (fallback only, not recommended as primary): accept the design defect and escalate

Leave `cov_foe_both.txt` unchanged; formally record `both_foe_slots` as permanently
non-constructible under the current bot+team combination, and escalate to the project owner for a
scope decision (accept a documented permanent exception, redefine what full "coverage" requires, or
prioritize Option 1/2).

- **Trade-off:** zero implementation cost now, but leaves Champions Strength blocked on this cell
  indefinitely with no remediation path, and does not fix the underlying gap. Included only because
  this diagnosis's charter requires naming the design defect explicitly if the cell is unreachable —
  not because it competes with Option 1 on merits.

**Recommendation: Option 1.** It is the proven pattern for exactly this defect class, has the
smallest blast radius (a test fixture, not production/live-play logic), and directly targets the
mechanism (§2) that deterministically explains the run's 50 active decisions — the missing reliable
first-decision construction that, on its own, already justifies the redesign regardless of Layer 2.

---

## Explicit non-claims and status

This diagnosis establishes, from frozen evidence and static analysis only:
- **A confirmed, deterministic root cause for the run's 50 active decisions** (Layer 1, §2) —
  independently re-derived from the raw team file, raw move-tagging data, and the raw scoring
  formula, not merely reported by a single source — **plus a plausible, not independently
  live-confirmed Layer 2 account** (§3) consistent with the remaining ~397 non-first-decision rows,
  whose exact later-turn causal mechanism the frozen profile does not establish. The design-defect
  classification and the Option 1 recommendation depend only on the former.
- **A design-defect classification**, per this task's explicit charter, since the cell is not
  reliably constructible in the real live geometry that actually ran.
- **A corrected candidate-identity execution-order description**, addressing a documented,
  already-occurred gap independent of the `both_foe_slots` finding.

It does **not** establish:
- Any code, test, or team-file change (Option 1's specifics are a recommendation, not a diff).
- Any live verification of Layer 2 (the Mega-timing race) or of a redesigned team's actual live
  behavior — both would require their own separately-authorized offline proof and/or live run.
- Any Strength result. **Champions Strength remains `NO-GO`** — on the coverage-gate FAIL, the
  candidate-identity gap, and (newly) this named design defect, independently.
- Authorization for implementation. This diagnosis is now **APPROVED** (4 review rounds, 7 P1s
  fixed and re-verified), but that approves the *diagnosis*, not a code change: Option 1's
  implementation is scoped in the separate plan
  `docs/projects/champions/plans/2026-07-20-champions-both-foe-slots-remediation.md`, itself
  PROPOSED and requiring its own review and authorization before any RED/GREEN work begins.
