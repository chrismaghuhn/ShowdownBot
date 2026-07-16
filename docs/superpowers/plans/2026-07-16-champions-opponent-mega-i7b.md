# Champions Mega I7b — Opponent Mega Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement these plans in order. Steps use checkbox (`- [ ]`) syntax for tracking. This plan is executable without the conversation that produced it — every task names exact files, exact existing symbols, complete new-API signatures, RED test names, a GREEN implementation boundary, a verification command, and a commit boundary.

**Status:** APPROVED — I7b-A implemented/merged (`cdc55c2`); **I7b-B Tasks 1-4 IMPLEMENTED on `feat/champions-i7b-b-dual-mega` @ `ca39fb6`** (not merged, not pushed); **Task 5, Task 6 and I7b-C NOT STARTED and review-gated** — **Rev. 7, reconciled with the committed code at `ca39fb6` (zero-weight scoring fix)**. Rev. 6 replaced Task 4's invalid `own_override` speed access with a final-branch-state derivation; Rev. 5 corrected the Task 4 integration fixture and added a species/form coherence gate to Task 2.

> **Rev. 4's header claimed "No production code, test code, or run artifact from this plan exists yet."** That is stale as of `cdc55c2`: I7b-A's production code and `tests/i7b/` exist and are merged. Left otherwise untouched here — Rev. 5 is deliberately narrow (see below) and re-statusing the whole document is not in its scope.

**Companion audit:** `docs/superpowers/specs/2026-07-16-champions-opponent-mega-i7b-audit.md` (Rev. 4) — read it first, especially §Rev.4; every architecture decision below is justified there against the current codebase at commit `1053cf1` and, for the weather-ordering question, against the pinned Showdown source at `f8ac140` and the binding Rev. 10 spec correction.

**Approved design:** `docs/superpowers/specs/2026-07-14-champions-mega-i7-design.md` rev. 10, §9 "I7b — opponent mega" and §10 "Dual-mega speed tie" (binding).

**Goal:** Deliver opponent-side Mega response modeling — limited-view eligibility, mega/no-mega twin expansion, coverage-preserving weight/cap discipline, dual (own+foe) same-turn Mega projection with Trick-Room-aware activation ordering, foe post-Mega speed replan, and a dedicated off-by-default telemetry sidecar proving a foe-Mega hypothesis was actually generated and scored — without touching decision-trace-v3, without a Champions-specific fork in the decision core, and without any Strength claim.

**Tech Stack:** Python 3.11+, pytest, `@pkmn/dex` 0.10.11 (already pinned), pinned `@smogon/calc`. No Showdown server needed until a future, separately-authorized I7b live smoke (out of scope here).

---

## Rev. 7 — reconciled with the committed code at `ca39fb6` (zero-weight scoring fix)

Rev. 7 is a **documentation reconciliation**, not a redesign. Tasks 1-4 are implemented
and committed; this section brings the plan's Task 4 pseudocode in line with what
actually shipped. **No historical decision was removed; the invalid Rev.-6 example was
reclassified as non-executable defect history** (its fence changed from `python` to
`text`, and it is labelled as such in place). Rev. 2-6's reasoning stands as written,
and this section states only where Rev. 6's Task 4 text no longer matches `ca39fb6`.

### The defect Rev. 6 still carried: a zero-weight response is not harmless

`aggregate_scores`' `MUST_REACT` operator is `avg - lambda*(avg - min(scores))`, and
that **`min(scores)` is computed WITHOUT weights** (`battle/policy.py`). A zero-weight
sample therefore cannot move the weighted mean, but it *does* move the aggregate.
Reproduced against the real function at the real default `lambda = 0.6`:

| scores | weights | `MUST_REACT` result |
|---|---|---|
| `[10]` | `[1]` | `10.0` |
| `[10, -100]` | `[1, 0]` | **`-56.0`** |

A `-66.0` swing from a sample whose weight is zero. `NEUTRAL` and `AHEAD` are
unaffected — both weight their mean *and* their variance — so this is
`MUST_REACT`-specific.

Consequences that were live in the Rev. 6 text:

- click rate `0.0` → the foe-Mega hypothesis still moved decisions;
- click rate `1.0` → the no-mega twin still moved decisions;
- both → projection branches composed purely to burn calc latency.

### Rev. 6 → Rev. 7 mapping (Task 4 only)

| # | Rev. 6 text | Rev. 7 / `ca39fb6` |
|---|---|---|
| 1 | `no_mega_resps = [r for r in resps if r.foe_mega_slot is None]` | adds `and (not _i7b_active or r.weight > 0)` — zero-weight responses are removed **before** enqueue, evaluation and `score_vector` on the active path |
| 2 | `foe_mega_slots = {…}` (raw set, no weight filter) | `sorted({… if r.foe_mega_slot is not None and r.weight > 0})` — deterministic order **and** no branches for a zero-weight Mega class |
| 3 | `matching_original = [r for r in resps if r.foe_mega_slot == foe_mega_slot]` | adds `and r.weight > 0` |
| 4 | `targets = … if … else [None]` unconditionally | `[None]` fallback suppressed on the active path |
| 5 | `rec.diagnostic_contexts.append(ctx)` unconditional | gated on `_i7b_active` |
| 6 | `test_branch_replan_preserves_original_mega_identity_and_zero_click_weight` | replaced: the identity test moves to an explicit mid click rate; the zero-weight case becomes its own counterexample |

**Unchanged and still binding:** the three-phase architecture, `world_weight ×
response_weight × branch_weight`, one shared flush per world, `ScoredResponseEvidence`'s
raw-component contract, the original/replanned pairing rule,
`MissingBranchResponseError`, Rev. 5's tie fixture and species coherence gate, Rev. 6's
final-branch-state speed derivation, and every slice boundary and stop gate.

### Rules the implementation now follows (binding)

1. **Zero-weight responses never reach the active I7b score pool** — not enqueued, not
   evaluated, never appended to `score_vector`/`score_weights`. Active path only; the
   legacy path's weighting is untouched and stays byte-identical.
2. **A Mega class whose responses all carry weight `0.0` composes no projection
   branches at all** — there is nothing scoreable to build them for, and building them
   would only cost calc latency.
3. **The unfiltered response set is retained for `retained_classes` / cap coverage.**
   `retained_classes` reads `resps`, *not* the filtered list, so I7b-A's zero-weight
   twins still prove cap coverage exactly as before. I7b-A keeps emitting them; the
   filter lives entirely in the scoring path.
4. **The active path must not manufacture a phantom `[None]` sample.** At click rate
   `1.0` the no-mega twins are zero-weight and filtered out, leaving the target list
   empty; falling back to `[None]` would inject a no-opponent-action line at weight
   `1.0` — the same distortion in mirror image. The foe-Mega branches carry that
   record's samples instead. (Found while implementing, not in review.)
5. **`foe_mega_slots` is `sorted(...)` after filtering.** Evidence rows and
   `score_vector` entries are appended in that iteration order, so raw set iteration
   made both non-reproducible.
6. **`matching_original` and the branch pairing match the committed code**, including
   the `r.weight > 0` filter, so a `_BranchResponsePair` is only ever built for a
   response that will actually be scored.
7. **`diagnostic_contexts` stays EMPTY on the legacy/I7a path** and is populated only
   on the active path, index-parallel to `diagnostic_details`/`diagnostic_weights`.
   Task 6 specifies an empty list as "pre-I7b-B → fall back to
   `ctx_by_slot[own_mega_slot]`"; populating it on the legacy path would make that
   fallback dead code and falsify the parity claim **structurally**, even though the
   bound context is numerically the same one.

### Measurement — what it does and does not license

Measured on the tie fixture, one decision, real Node backend, `MUST_REACT`:

| path | backend batches | ≈ wall clock |
|---|---|---|
| inactive (`eligibility=None`) | 6 | ~1116 ms |
| active, click rate `0.0` | **6** | ~1158 ms |
| active, click rate `0.35` (default) | 16 | ~2676 ms |
| active, click rate `1.0` | 16 | ~2641 ms |

**The only conclusion this licenses: the zero-click overhead is fixed** — rate `0.0`
now costs what the inactive path costs (it was 16 batches / ~2660 ms before). It does
**not** mean Champions latency is solved. **The genuinely active foe-Mega path remains
a separate, open latency blocker** (≈2.4× the inactive decision here), and these
absolute numbers are not comparable to the Champions smokes' p95 (I6 331 ms, I7a-C
588 ms): different harness, synthetic fixture, cold Node subprocess. The dedicated
Champions latency profile/budget stays an open blocker in its own right.

## Rev. 6 — Task 4's `own_override` reads a field that does not exist

Rev. 6 is a **narrow correction**, not a redesign. It changes nothing about the
three-phase architecture, the weighting formula, the flush discipline, the evidence
DTO, or Rev. 5's corrections.

### The defect — CONFIRMED at runtime, not by inspection

Rev. 4/5's Task 4 Phase-A-part-2 computed the own-side post-Mega speed override as
follows. **This is a defect record, NOT an implementation instruction** — the fence is
deliberately not `python` so it can never be lifted out as one:

```text
own_override = (
    {ctx.own_mega_slot: branch.projected_state.sides[our_side][
        "a" if ctx.own_mega_slot == 0 else "b"].effective_speed}   # <-- INVALID
    if ctx.own_mega_slot is not None else None
)
```

`PokemonState` **has no `effective_speed` attribute.** Its real fields are
`species, nickname, level, gender, hp, max_hp, boosts, status, item, item_known,
ability, moves, move_names, tera_type, terastallized, fainted, types,
consecutive_protect, moved_since_switch, item_lost, base_species_id`. Hit for real
while executing Task 4:

```
AttributeError: 'PokemonState' object has no attribute 'effective_speed'
  src/showdown_bot/battle/mega_scoring.py, Phase A part 2
```

Post-Mega speed lives on **`MegaProjectionResult.effective_speed`** — which is what
the existing `_mega_context` correctly uses (`overrides = {own_mega_slot: proj.effective_speed}`).
`compose_mega_projection_branches` obtains that result per activation but keeps only
`step.projected_state`, and `WeightedMegaProjection` carries only
`projected_state`/`weight`/`activation_order`. So the value the plan reaches for is
genuinely not reachable the way it is written.

### Correction (binding for Task 4)

Re-derive the own-Mega speed from the **complete, final** `branch.projected_state`:

- `PokemonState` does **not** gain an `effective_speed` field.
- `WeightedMegaProjection` stays **unchanged** — no new speed field.
- The pre-existing own-Mega context is **not** reused as a speed source.
- For `ctx.own_mega_slot is not None`: determine the slot letter, read the projected
  own mon out of `branch.projected_state`, and call
  `speed_oracle.speed_for_species(...)` with that mon's Mega species, its base
  species, the **final branch** field, `our_spreads`, `book`, and `is_ours=True`.
  Pass the result as `planned_speed_overrides_by_slot={ctx.own_mega_slot: computed_speed}`
  to `_plan_my_actions`.
- No manual stat/EV arithmetic and no access to private `SpeedOracle` methods.
- Do **not** functionally rework the existing Task 3 commits.

```python
    own_override = None
    if ctx.own_mega_slot is not None:
        own_slot_letter = "a" if ctx.own_mega_slot == 0 else "b"
        own_projected = branch.projected_state.sides[our_side][own_slot_letter]
        own_override = {
            ctx.own_mega_slot: speed_oracle.speed_for_species(
                species_name=own_projected.species,
                base_species_id=own_projected.base_species_id or own_projected.species,
                side=our_side,
                mon=own_projected,
                field=branch.projected_state.field,
                our_spreads=our_spreads,
                opp_sets=None,
                book=book,
                is_ours=True,
            )
        }
```

**Required regression test:** the replanned `PlannedAction.speed` for the own Mega'd
slot equals the speed computed over the **final branch state**. The test must be RED
with the real error (the `AttributeError` above) before the correction, and Reg-I /
`format_config=None` parity, live-state non-mutation, and the three phases must stay
green.

**Latency, stated honestly:** deriving on the final branch state is an additional
`speed_for_species` call per `(slot, foe_mega_slot, branch_idx)`. The existing calc
cache should normally absorb it, but that is **not** a semantic contract and must not
be claimed as one — measure it rather than assert it. Champions latency is separately
open (I5 worst p95 3235 ms vs a 1000 ms budget).

**Why not the cheaper alternatives** (recorded so they are not re-litigated): carrying
the speeds on `WeightedMegaProjection` would functionally rework the merged Task 3
commit; reusing the already-computed own-Mega `MegaProjectionResult` would require
either a `MegaEvaluationContext` schema change (which the audit explicitly forbids —
§Rev.2 item 5) or threading the projection results into `score_evaluated_variants`.

**Related fact, deliberately not relied upon:** weather is not a speed modifier in this
model — `speed_modifiers_from_state` reads only `boost_stage`, `tailwind`, `paralyzed`,
`scarf`, `booster_speed` — so a foe's Mega weather does not change our own mon's
effective speed today, and the final-branch derivation is expected to agree numerically
with the plain own-Mega projection. That is an observation about the current model, not
a licence to read the value from somewhere else; deriving it from the final branch state
stays correct if a weather-sensitive speed modifier is ever added.

## Rev. 5 — Task 4 fixture defect and Task 2 species coherence

Rev. 5 is a **narrow correction**, not a redesign. It changes nothing about the Rev. 4
three-phase architecture, the weighting formula, the flush discipline, or the evidence
DTO. Two defects, one found during I7b-B execution prep and independently reproduced by
Codex, plus one consequence that follows mechanically from the second.

### 1. Task 4's integration fixture cannot produce the tie its own test asserts — CONFIRMED

Rev. 4's `test_foe_mega_evidence_is_weighted_by_world_times_response_times_branch`
asserts `assert tied_groups  # this fixture's speed values must exercise a genuine tie`.
A tie requires `compose_mega_projection_branches` to return two `0.5`-weight branches,
which happens only on **exactly equal pre-mega speed**. Measured against the real
`SpeedOracle` + real `SubprocessCalcBackend`, computed exactly the way Task 3's
implementation computes pre-mega speed:

| Fixture slot | Species | Resolver | Pre-mega speed |
|---|---|---|---|
| `p1.a` | Aerodactyl | `our_spreads`, `is_ours=True` | **200** |
| `p2.a` | **Incineroar** | `book.default`, `is_ours=False` | **123** |

Not a tie → **one branch, weight 1.0** → every `by_response` group holds exactly one
row → `tied_groups == []` → the assertion **cannot pass**. No parameter choice rescues
it: `tests/conftest.py::_mega_state()` defines **no `p2.b` at all**, and the Task 4
tests pass `opp_sets=None`, so the foe speed is pinned to `book.default`.

**Root cause:** the Rev. 4 tests pass `eligibility = {"a": mega_form_for("Aerodactyl",
"Aerodactylite")}` — which would tie at 200-vs-200 *if the foe were an Aerodactyl*. It
is an Incineroar. This is the **same bug class the audit itself caught for T51**
("T51's chosen hero speed (140) cannot demonstrate a real order flip", audit §Rev.2
secondary findings) — caught there, missed here.

**Correction (binding for Task 4):**

- Keep `mega_decision_fixture` and `_mega_state()` **default behavior unchanged** — they
  are shared with `tests/i7a/` and Step 0 already commits to "keep the existing
  request/state/book/profile construction".
- Extract the fixture construction into a small **test-only builder**, with the current
  Incineroar opponent as its default.
- Add a dedicated **`mega_decision_tie_fixture`** whose `p2.a` is a **real Aerodactyl
  holding Aerodactylite with `item_known=True`**.
- Build that fixture's `contexts`/`evaluated_variants` from the coherent
  Aerodactyl-vs-Aerodactyl state **from the beginning** — do **not** swap only
  `kw["state"]` after contexts already exist.
- Derive eligibility through the **real `foe_mega_eligibility()`**, never by hand-injecting
  a `MegaForm` onto a mismatched species.
- **Verify the equality with the real backend inside the test**, as an explicit
  precondition, before the scoring assertion — the defect above existed precisely because
  a tie was asserted that nobody computed.
- Task 3's monkeypatched tie test stays as the **isolated branch-enumeration** test.
  Task 4 stays a **real-backend integration** test. The two are not interchangeable.

**Pre-verified against the real backend** (same method as the defect measurement above),
so Rev. 5 does not repeat Rev. 4's mistake of asserting an uncomputed tie:

| Proposed tie-fixture slot | Species | Resolver | Pre-mega speed |
|---|---|---|---|
| `p1.a` | Aerodactyl | `our_spreads`, `is_ours=True` | **200** |
| `p2.a` | **Aerodactyl** (Aerodactylite, `item_known=True`) | `book.default`, `is_ours=False` | **200** |

→ tie **True** → two branches, weight **0.5** each. And the real
`foe_mega_eligibility(state, "p2", opp_sets=None)` returns
`{'a': MegaForm(base_species_id='aerodactyl', form_species_id='aerodactylmega', ...)}`
— the manual injection is unnecessary as well as incoherent.

### 2. `project_mega` does not check species/form coherence — CONFIRMED

Direct read of `engine/mega_projection.py`: `project_mega` validates
`speed_oracle.profile == calc_profile` and that `mega_form.form_species_id` is a known
form, then writes `mon.species = form_meta.form_species_name` and
`mon.base_species_id = mega_form.base_species_id` **without ever checking that the mon
at that slot is actually the form's base species**. Rev. 4's own Task 4 tests exploit
this by accident: they project an *Aerodactyl-Mega* onto an *Incineroar* and it silently
succeeds.

**Correction (binding for Task 2):**

- Add a **fail-closed species/form coherence check to `project_mega()`, before projection**.
- The slot's normalized `base_species_id` **or** normalized `species` must equal
  `mega_form.base_species_id` (the `or` preserves valid sub-form mappings, e.g. an
  already-Mega'd mon whose `species` is `"Aerodactyl-Mega"` but whose `base_species_id`
  is still `"aerodactyl"`).
- On mismatch raise a **dedicated `MegaProjectionSpeciesMismatchError`**.
- Add a **RED→GREEN regression** proving Incineroar + Aerodactyl-Mega is rejected **and
  the input state remains unmutated**.
- Preserve all valid sub-form mappings and existing I7a behavior — every existing I7a
  call site projects a coherent own-side form and must stay green.

**`MegaProjectionSpeciesMismatchError` is deliberately NOT added to Task 4's
`except (UnsupportedMegaAbilityError, MissingMegaSpreadError)` list.** In production an
incoherent hypothesis cannot arise: `foe_mega_eligibility()` derives every form from
`mega_form_for(mon.species, mon.item)` and is therefore coherent by construction. A
mismatch reaching `project_mega` would be a genuine programming error, and crashing is
the correct fail-closed response — silently excluding it would hide the bug.

### 3. Consequence: Task 5's ability-gate test must use a coherent foe

**This item is a mechanical consequence of correction 2, not an independent change** —
flagged explicitly so it can be struck without touching corrections 1-2.

Rev. 4's Task 5 test injects a `Scovillain-Mega` form (described there as "synthetic")
onto the fixture's non-Scovillain foe and expects `UnsupportedMegaAbilityError`.
Verified against real metadata: `scovillainmega` is **a real, known form**
(`species_meta`), its `ability_slot0` is `'Spicy Spray'`, and it is the **only** member
of `FAIL_CLOSED_ABILITIES` in the entire dex — so the test does work today. But once
correction 2 lands, the coherence check fires **before** the ability gate
(`aerodactyl`/`incineroar` ≠ `scovillain`), raising `MegaProjectionSpeciesMismatchError`
— which Task 4 deliberately does not catch. The test would then crash instead of
proving exclusion, and would no longer test the ability gate at all.

**Correction (binding for Task 5):** the test's foe must be a **real Scovillain holding
Scovillainite (`item_known=True`)**, with eligibility derived through the real
`foe_mega_eligibility()`. Pre-verified: `mega_form_for("Scovillain", "Scovillainite")`
returns the real form, the coherence check passes (`scovillain == scovillain`), the
ability gate is then what fires, and the real eligibility path yields
`{'a': MegaForm(base_species_id='scovillain', ...)}`.

### Scope of Rev. 5

Unchanged: the three-phase architecture, `world_w × response_weight × branch_weight`,
one-shared-flush-per-world, `ScoredResponseEvidence`'s raw-component contract, the
original/replanned pairing rule, `MissingBranchResponseError`, Task 6's zero-`search.py`
depth-2 binding, and every slice boundary and stop gate. No I7b-C change. No Strength
claim. No live run.

## Rev. 4 final data-flow corrections

Rev. 4 keeps Rev. 3's three-phase architecture but closes five remaining implementation traps:

1. Branch replanning uses the regenerated response's **actions** while preserving the original Mega hypothesis's `response_id`, `foe_mega_slot`, and post-cap/click-rate `weight`.
2. Foe-side `project_mega` delegates spread resolution to `SpeedOracle.speed_for_species`; it does not reject a valid `book`-only hypothesis with an `opp_sets` pre-check.
3. Every world's complete shared-oracle queue is flushed exactly once after all no-Mega and Mega-branch enqueues.
4. Telemetry records `required_classes`, `retained_classes`, and `scored_classes` separately; scored evidence can no longer masquerade as proof that the cap retained a class.
5. The sidecar sink is threaded and tested across the complete live call graph, not only at `_choose_best_mega`.

These corrections supersede the active Rev. 3 Task 2/Task 4/I7b-C snippets where the two differ. Historical correction notes remain context only.

## Mandatory execution order

1. [I7b-A — Limited-view eligibility, identities, weights, cap discipline](#i7b-a-limited-view-eligibility-identities-weights-cap-discipline)
2. [I7b-B — Dual projection, activation ordering, scoring integration](#i7b-b-dual-projection-activation-ordering-scoring-integration)
3. [I7b-C — Telemetry/provenance and safety-smoke design](#i7b-c-telemetryprovenance-and-safety-smoke-design)

**Execution status as of Rev. 7** (branch `feat/champions-i7b-b-dual-mega` @ `ca39fb6`,
not merged, not pushed):

| Slice / task | Status |
|---|---|
| I7b-A | **MERGED** to `main` @ `cdc55c2` |
| I7b-B Task 1 — `mega_activation_order_key` | **DONE** @ `8ab6e6c` |
| I7b-B Task 2 — side-aware `project_mega` + species coherence gate | **DONE** @ `e21a075` |
| I7b-B Task 3 — `compose_mega_projection_branches` | **DONE** @ `f50c7af` |
| I7b-B Task 4 — three-phase scoring integration + caller gate | **DONE** @ `64d47ba`, zero-weight fix @ `ca39fb6` |
| I7b-B Task 5 — fail-closed ability gate | **NOT STARTED** — review-gated |
| I7b-B Task 6 — depth-2 per-index context binding | **NOT STARTED** — review-gated |
| I7b-C — telemetry/provenance + smoke design | **NOT STARTED** — review-gated |

Task 4 additionally carries five pre-flight caller-gate counterexamples
(`tests/i7b/test_i7b_b_caller_gate.py`) that are **additive to this plan**, added on
explicit user directive: two are honest BASELINE/INVARIANT tests (green before *and*
after the wiring, guarding it), three were genuinely RED against the real missing
wiring.

Each slice starts from the green, reviewed tip produced by the preceding slice. Do not execute them concurrently. Do not start I7b-B until every I7b-A test and the full existing suite pass. Do not start I7b-C until I7b-B proves dual-Mega composition never mutates live state and Reg-I/`format_config=None` remain byte-identical.

## Slice contracts

| Slice | Produces working software | Explicitly excludes |
|---|---|---|
| I7b-A | `OppResponse` identity fields, limited-view `foe_mega_eligibility()`, fail-closed `OpponentResponseCapError`, fail-closed click-rate env parsing, the full cap-check→expand→weight→renormalize pipeline inside `predict_responses` (gated, additive, opt-in; switch/pivot slots excluded from expansion) | Any change to `mega_scoring.py`, `engine/mega_projection.py`, `engine/speed.py`; foe post-Mega speed replan; dual-Mega composition; trace/sidecar changes; any live decision-core wiring (no caller passes the new kwargs yet) |
| I7b-B **[REV.4]** | Side-aware `project_mega` contract; `compose_mega_projection_branches`/`WeightedMegaProjection`/`mega_activation_order_key`; `ScoredResponseEvidence`; foe-Mega responses composed lazily and correctly weighted (`world_w × response_weight × branch_weight`) inside `score_evaluated_variants`; foe post-Mega `PlannedAction` replan at point of use; depth-2 threading; `decision.py::_choose_best_mega` wired (only) | `battle/baselines.py` (max_damage never models opponent responses — out of scope, audit finding 4); any new top-level `MegaEvaluationContext` multiplication in `build_own_mega_contexts` (deleted); trace/sidecar changes; ROADMAP/PROJECT_INDEX changes; Strength claims; any live battle |
| I7b-C | `eval/opp_mega_trace.py` sidecar writer/schema/validator (built from `ScoredResponseEvidence`); `SHOWDOWN_OPP_MEGA_TRACE_OUT` wiring; safety-smoke design (not run) | Running the smoke; opponent-Mega-in-production claims; latency-budget changes; Strength claims |

## Cross-slice stop gates

- Do not start I7b-B unless every I7b-A focused test and the full existing suite pass, and `git diff --check` is clean.
- Do not start I7b-C unless I7b-B proves (a) `format_config=None`/Reg-I callers remain byte-identical, (b) dual-Mega composition never mutates a live `BattleState`, and (c) the ability fail-closed gate (`UnsupportedMegaAbilityError`) applies symmetrically to a hypothesized foe Mega form.
- A failure at any gate stops the next slice; do not weaken a test, widen a cap silently, or exclude a Mega form's fail-closed behavior to make a test pass.
- No task in any slice may introduce `SHOWDOWN_MEGA_MARGIN` (explicitly out of v0 per spec §16), OTS (§9.1), or a Reg-I/legacy behavior change.

## Approved-spec coverage map

| Slice | Approved-design test ownership |
|---|---|
| I7b-A | T19 (weights sum 1), T29 (post-truncate weights sum 1), T32 (coverage-preserving truncate) |
| I7b-B | T26 (dual-mega branches: no-TR / TR-reversed / tie weighted score), T51 (foe post-mega speed replan changes move order) |
| I7b-C | No new T-numbered test (telemetry/provenance is not part of the T1–T54 index); reuses the existing provenance test pattern from I7a-C (`test_i7a_provenance.py`) as a template |

Together I7b-A/B cover every I7b test reserved by the approved design (T19, T26, T29, T32, T51) — the full set the I7a plans explicitly declined to authorize. Rev. 10 only corrects T26's weather winner; it does not change this test allocation.

---

## I7b-A: Limited-view eligibility, identities, weights, cap discipline

**Files this slice creates:**
- `showdown_bot/tests/i7b/__init__.py`
- `showdown_bot/tests/i7b/test_i7b_eligibility.py`
- `showdown_bot/tests/i7b/test_i7b_responses.py`

**Files this slice modifies:**
- `showdown_bot/src/showdown_bot/battle/opponent.py`
- `showdown_bot/src/showdown_bot/eval/config_env.py`
- `showdown_bot/tests/test_opponent.py`
- `showdown_bot/tests/test_config_env.py`

**Explicitly excludes:** `mega_scoring.py`, `engine/mega_projection.py`, `engine/speed.py`, `battle/decision.py`, `battle/baselines.py`, any trace/sidecar file, ROADMAP/PROJECT_INDEX. No caller anywhere passes the new `predict_responses` kwargs yet — this slice is purely additive and inert until I7b-B wires it in.

### Task 1: `OppResponse` identity fields

**Step 1 — write failing tests** in `showdown_bot/tests/test_opponent.py` (append):

```python
def test_opp_response_default_response_id_and_foe_mega_slot_are_backward_compatible():
    from showdown_bot.battle.opponent import OppResponse

    r = OppResponse(actions=[], label="aggro->a")
    assert r.response_id == ""
    assert r.foe_mega_slot is None
```

**Step 2 — confirm RED:**
```powershell
python -m pytest tests/test_opponent.py -k "response_id_and_foe_mega_slot" -q
```
Expected failure: `TypeError` or `AttributeError` — `OppResponse` has no `response_id`/`foe_mega_slot` field yet.

**Step 3 — implement** in `battle/opponent.py`, modifying the existing `OppResponse` dataclass (currently `opponent.py:71-78`):

```python
@dataclass
class OppResponse:
    """One candidate opponent joint response for one ply."""

    actions: list[PlannedAction]
    label: str
    flags: set[str] = field(default_factory=set)
    weight: float = 1.0  # likelihood weight (set from protect priors)
    response_id: str = ""  # f"{label}|mega={none|0|1}"; "" only for pre-I7b-A construction sites
    foe_mega_slot: int | None = None  # opp slot (0/1) this response assumes Mega'd this turn, else None
```

**Step 4 — verify:**
```powershell
python -m pytest tests/test_opponent.py -q
```
Expected: all existing `test_opponent.py` tests still pass (new fields are defaulted; no existing construction site is broken) plus the new test passes.

**Step 5 — commit:**
```powershell
git add src/showdown_bot/battle/opponent.py tests/test_opponent.py
git commit -m "feat(champions-i7b-a): add response_id/foe_mega_slot fields to OppResponse"
```

### Task 2: `foe_mega_eligibility()` — limited-view eligibility discovery

**Step 1 — write failing tests** in new file `showdown_bot/tests/i7b/test_i7b_eligibility.py`:

```python
"""I7b-A: limited-view foe-Mega eligibility discovery."""
from __future__ import annotations

from showdown_bot.battle.opponent import foe_mega_eligibility
from showdown_bot.engine.belief.hypotheses import SpeciesSpreads, SpreadPreset
from showdown_bot.engine.mega_form import MegaForm
from showdown_bot.engine.state import BattleState, PokemonState


def _state_with_opp(species: str, *, item: str | None, item_known: bool, item_lost: bool = False,
                     side_mega_spent: bool = False) -> BattleState:
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=100, max_hp=100)
    mon = PokemonState(species=species, hp=100, max_hp=100, item=item, item_known=item_known, item_lost=item_lost)
    st.sides["p2"]["a"] = mon
    st.sides["p2"]["b"] = PokemonState(species="Rillaboom", hp=100, max_hp=100)
    st.side_mega_spent["p2"] = side_mega_spent
    return st


def test_revealed_stone_makes_slot_eligible():
    state = _state_with_opp("Aerodactyl", item="aerodactylite", item_known=True)

    result = foe_mega_eligibility(state, "p2", opp_sets=None)

    assert "a" in result
    assert isinstance(result["a"], MegaForm)
    assert result["a"].form_species_name == "Aerodactyl-Mega"


def test_unrevealed_unhypothesized_stone_yields_no_response():
    """T19-adjacent counterexample: no revealed item, no opp_sets hypothesis
    listing a mega stone -> not eligible, even though the real (hidden) held item
    IS a mega stone -- eligibility must never see the true hidden item."""
    state = _state_with_opp("Aerodactyl", item=None, item_known=False)

    result = foe_mega_eligibility(state, "p2", opp_sets=None)

    assert "a" not in result


def test_likely_set_stone_makes_slot_eligible_without_reveal():
    state = _state_with_opp("Aerodactyl", item=None, item_known=False)
    curated = SpeciesSpreads(
        offense=SpreadPreset(nature="Jolly", evs={}, items=["Aerodactylite"]),
        defense=SpreadPreset(nature="Jolly", evs={}, items=["Aerodactylite"]),
    )

    result = foe_mega_eligibility(state, "p2", opp_sets={"aerodactyl": curated})

    assert "a" in result
    assert result["a"].form_species_name == "Aerodactyl-Mega"


def test_revealed_stone_still_eligible_even_with_no_curated_hypothesis():
    """Revealed item alone is sufficient -- opp_sets absence must not block it."""
    state = _state_with_opp("Aerodactyl", item="aerodactylite", item_known=True)

    result = foe_mega_eligibility(state, "p2", opp_sets={})

    assert "a" in result


def test_side_already_spent_mega_yields_no_eligible_slot():
    state = _state_with_opp("Aerodactyl", item="aerodactylite", item_known=True, side_mega_spent=True)

    result = foe_mega_eligibility(state, "p2", opp_sets=None)

    assert result == {}


def test_lost_item_never_eligible_even_if_species_could_mega():
    state = _state_with_opp("Aerodactyl", item=None, item_known=True, item_lost=True)

    result = foe_mega_eligibility(state, "p2", opp_sets=None)

    assert "a" not in result


def test_non_mega_capable_species_yields_no_eligible_slot():
    state = _state_with_opp("Incineroar", item="choicescarf", item_known=True)
    # overwrite slot a directly since _state_with_opp always seeds p1/a as Incineroar
    state.sides["p2"]["a"] = PokemonState(species="Incineroar", item="choicescarf", item_known=True)

    result = foe_mega_eligibility(state, "p2", opp_sets=None)

    assert result == {}


def test_eligibility_never_reads_the_real_opponent_team_file():
    """Hard leakage counterexample: opp_sets carries no hypothesis, but a
    hypothetical 'real team paste' dict (simulating a gauntlet schedule's actual
    opponent roster) DOES list a mega stone for this species. foe_mega_eligibility
    must not accept a team-paste-shaped argument at all -- this test proves the
    function signature has no such parameter and that passing real team data as
    opp_sets (the only hypothesis source it accepts) still requires the SAME
    curated-hypothesis shape, not a raw roster dict, to produce a hit."""
    import inspect

    sig = inspect.signature(foe_mega_eligibility)
    assert set(sig.parameters) == {"state", "opp_side", "opp_sets"}

    state = _state_with_opp("Aerodactyl", item=None, item_known=False)
    fake_real_roster = {"real_team_paste": "Aerodactyl @ Aerodactylite"}  # wrong shape on purpose
    result = foe_mega_eligibility(state, "p2", opp_sets=fake_real_roster)
    assert result == {}  # malformed/foreign shape -> no match, never a silent leak
```

**Step 2 — confirm RED:**
```powershell
python -m pytest tests/i7b/test_i7b_eligibility.py -q
```
Expected failure: `ImportError` — `foe_mega_eligibility` does not exist in `battle/opponent.py`.

**Step 3 — implement** in `battle/opponent.py` (add near `_alive_slots`, after the existing imports; add `from showdown_bot.engine.mega_form import MegaForm, mega_form_for` and `from showdown_bot.engine.spread_lookup import lookup_opp_set` — the latter is already imported at `opponent.py:9`):

```python
def foe_mega_eligibility(
    state: BattleState, opp_side: str, *, opp_sets: dict | None,
) -> dict[str, MegaForm]:
    """Limited-view Mega eligibility for the opponent's active slots (I7b §9.1).

    A slot is eligible iff the side has not already spent its Mega this battle
    AND EITHER (a) the mon's held item is revealed (``item_known`` and not
    ``item_lost``) and resolves via ``mega_form_for``, OR (b) a curated
    ``opp_sets`` preset for that species lists an item that resolves via
    ``mega_form_for`` -- the SAME per-format curated hypothesis source
    ``lookup_opp_set`` already uses, never the real battling opponent's actual
    team file (which this function has no parameter to accept at all).

    No ``book`` parameter (Rev. 3 audit finding 6d, corrected): unlike
    ``speed_for_species`` (where ``book``-derived ``hypothesis_from_state`` is
    the PRIMARY foe-speed source and ``opp_sets`` is only a fallback --
    confirmed by reading ``engine/speed.py:169-176``), ``SpreadBook`` exposes
    no item/held-item hypothesis at all, only nature/EV presets -- there is
    nothing for an eligibility check to read from it. Accepting an unused
    ``book`` parameter here would be a dead, YAGNI parameter; earlier plan
    drafts wrongly claimed eligibility draws from "curated opp_sets/book"
    symmetrically with the speed path, which does not hold for this function.
    """
    if state.side_mega_spent.get(opp_side, False):
        return {}
    result: dict[str, MegaForm] = {}
    for slot, mon in state.sides.get(opp_side, {}).items():
        if slot not in ("a", "b") or mon.fainted or mon.hp_fraction <= 0:
            continue
        if mon.item_known and not mon.item_lost and mon.item:
            form = mega_form_for(mon.species, mon.item)
            if form is not None:
                result[slot] = form
                continue
        preset = lookup_opp_set(opp_sets, mon) if opp_sets else None
        if preset is None:
            continue
        for candidate_item in list(preset.offense.items) + list(preset.defense.items):
            form = mega_form_for(mon.species, candidate_item)
            if form is not None:
                result[slot] = form
                break
    return result
```

`lookup_opp_set(opp_sets, mon)` (`engine/spread_lookup.py`, already used at `opponent.py:166`) returns `None` for any dict that isn't keyed/shaped like a curated `SpeciesSpreads` map (e.g. the malformed `fake_real_roster` test fixture) — this is what makes the leakage counterexample pass without extra guard code.

**Step 4 — verify:**
```powershell
python -m pytest tests/i7b/test_i7b_eligibility.py tests/test_opponent.py -q
```
Expected: all pass.

**Step 5 — commit:**
```powershell
git add src/showdown_bot/battle/opponent.py tests/i7b/
git commit -m "feat(champions-i7b-a): add limited-view foe_mega_eligibility()"
```

### Task 3: fail-closed click-rate env parsing

**Step 1 — write failing tests** in `showdown_bot/tests/i7b/test_i7b_responses.py` (new file):

```python
"""I7b-A: click-rate parsing and (later in this file) response pipeline tests."""
from __future__ import annotations

import pytest

from showdown_bot.battle.opponent import InvalidOppMegaClickRateError, opp_mega_click_rate


@pytest.mark.parametrize("raw,expected", [("0.35", 0.35), ("0.0", 0.0), ("1.0", 1.0), ("0.2", 0.2), ("0.5", 0.5)])
def test_opp_mega_click_rate_accepts_valid_values(monkeypatch, raw, expected):
    monkeypatch.setenv("SHOWDOWN_OPP_MEGA_CLICK_RATE", raw)
    assert opp_mega_click_rate() == expected


def test_opp_mega_click_rate_defaults_to_0_35_when_unset(monkeypatch):
    monkeypatch.delenv("SHOWDOWN_OPP_MEGA_CLICK_RATE", raising=False)
    assert opp_mega_click_rate() == 0.35


@pytest.mark.parametrize("raw", ["-0.1", "1.1", "nan", "inf", "-inf", "abc", ""])
def test_opp_mega_click_rate_fails_closed_on_invalid_values(monkeypatch, raw):
    monkeypatch.setenv("SHOWDOWN_OPP_MEGA_CLICK_RATE", raw)
    with pytest.raises(InvalidOppMegaClickRateError):
        opp_mega_click_rate()
```

**Step 2 — confirm RED:** `python -m pytest tests/i7b/test_i7b_responses.py -q` → `ImportError`.

**Step 3 — implement** in `battle/opponent.py` (add `import math` if not already imported — it is not currently imported in this file, confirm before adding):

```python
class InvalidOppMegaClickRateError(ValueError):
    """SHOWDOWN_OPP_MEGA_CLICK_RATE is set but is not a finite float in [0.0, 1.0]."""


def opp_mega_click_rate() -> float:
    raw = os.environ.get("SHOWDOWN_OPP_MEGA_CLICK_RATE", "0.35")
    try:
        value = float(raw)
    except ValueError as exc:
        raise InvalidOppMegaClickRateError(
            f"SHOWDOWN_OPP_MEGA_CLICK_RATE={raw!r} is not a float"
        ) from exc
    if not math.isfinite(value) or not (0.0 <= value <= 1.0):
        raise InvalidOppMegaClickRateError(
            f"SHOWDOWN_OPP_MEGA_CLICK_RATE={value!r} must be a finite value in [0.0, 1.0]"
        )
    return value
```

**Step 4 — verify:** `python -m pytest tests/i7b/test_i7b_responses.py -q`.

**Step 5 — commit:**
```powershell
git add src/showdown_bot/battle/opponent.py tests/i7b/test_i7b_responses.py
git commit -m "feat(champions-i7b-a): fail-closed SHOWDOWN_OPP_MEGA_CLICK_RATE parsing"
```

### Task 4: `OpponentResponseCapError` and cap-aware reserve/truncate/renormalize pipeline

This is the core of I7b-A. It changes `predict_responses`'s body but only inside a new, additive branch.

**Step 1 — write failing tests**, appended to `showdown_bot/tests/i7b/test_i7b_responses.py`:

```python
from showdown_bot.battle.opponent import (
    OpponentResponseCapError,
    OppResponse,
    predict_responses,
)
from showdown_bot.engine.belief.protect_priors import ProtectPriors
from showdown_bot.engine.mega_form import mega_form_for
from showdown_bot.engine.state import BattleState, PokemonState


def _doubles_state(*, opp_a_item=None, opp_a_item_known=False) -> BattleState:
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Incineroar", hp=100, max_hp=100)
    st.sides["p1"]["b"] = PokemonState(species="Rillaboom", hp=100, max_hp=100)
    st.sides["p2"]["a"] = PokemonState(
        species="Aerodactyl", hp=100, max_hp=100, item=opp_a_item, item_known=opp_a_item_known,
    )
    st.sides["p2"]["b"] = PokemonState(species="Meganium", hp=100, max_hp=100)
    return st


def _eligibility_a_only():
    return {"a": mega_form_for("Aerodactyl", "Aerodactylite")}


def test_no_mega_twin_when_slot_not_eligible():
    state = _doubles_state()
    resps = predict_responses(
        state, "p1", "p2", max_candidates=10,
        foe_mega_eligibility={}, opp_mega_click_rate=0.35,
    )
    assert all(r.foe_mega_slot is None for r in resps)
    assert all(r.response_id.endswith("|mega=none") for r in resps)


def test_no_mega_twin_retained_alongside_mega_twin_when_eligible():
    """Binding: revealed/hypothesized stone -> BOTH no-mega and mega twins present."""
    state = _doubles_state(opp_a_item="aerodactylite", opp_a_item_known=True)
    resps = predict_responses(
        state, "p1", "p2", max_candidates=10,
        foe_mega_eligibility=_eligibility_a_only(), opp_mega_click_rate=0.35,
    )
    ids = {r.response_id for r in resps}
    assert any(rid.endswith("|mega=none") for rid in ids)
    assert any(rid.endswith("|mega=0") for rid in ids)  # slot "a" == index 0


@pytest.mark.parametrize("rate", [0.0, 0.35, 1.0])
def test_weights_sum_to_one_at_various_click_rates(rate):
    """T19/T29: weights sum to 1 after the full pipeline, at 0.0/0.35/1.0."""
    state = _doubles_state(opp_a_item="aerodactylite", opp_a_item_known=True)
    resps = predict_responses(
        state, "p1", "p2", max_candidates=10, priors=ProtectPriors(),
        foe_mega_eligibility=_eligibility_a_only(), opp_mega_click_rate=rate,
    )
    assert resps
    assert sum(r.weight for r in resps) == pytest.approx(1.0)


def test_click_rate_zero_gives_mega_twin_zero_weight_not_absence():
    """rate=0.0 must still retain the mega twin (never deterministic), just weight 0."""
    state = _doubles_state(opp_a_item="aerodactylite", opp_a_item_known=True)
    resps = predict_responses(
        state, "p1", "p2", max_candidates=10, priors=ProtectPriors(),
        foe_mega_eligibility=_eligibility_a_only(), opp_mega_click_rate=0.0,
    )
    mega_resps = [r for r in resps if r.foe_mega_slot is not None]
    assert mega_resps
    assert all(r.weight == pytest.approx(0.0) for r in mega_resps)


def test_click_rate_one_gives_no_mega_twin_zero_weight_not_absence():
    state = _doubles_state(opp_a_item="aerodactylite", opp_a_item_known=True)
    resps = predict_responses(
        state, "p1", "p2", max_candidates=10, priors=ProtectPriors(),
        foe_mega_eligibility=_eligibility_a_only(), opp_mega_click_rate=1.0,
    )
    none_resps = [r for r in resps if r.foe_mega_slot is None]
    assert none_resps
    assert all(r.weight == pytest.approx(0.0) for r in none_resps)


def test_cap_too_small_for_reserve_classes_raises():
    """T32-adjacent: R = {none, mega-slot-a} has size 2; max_candidates=1 cannot
    hold both classes -> fail closed, never silently drop a class."""
    state = _doubles_state(opp_a_item="aerodactylite", opp_a_item_known=True)
    with pytest.raises(OpponentResponseCapError):
        predict_responses(
            state, "p1", "p2", max_candidates=1,
            foe_mega_eligibility=_eligibility_a_only(), opp_mega_click_rate=0.35,
        )


def test_cap_sufficient_but_tight_still_reserves_every_class():
    """T32: many heavy no-mega responses cannot eliminate the mega-class
    representative once R fits within max_candidates."""
    state = _doubles_state(opp_a_item="aerodactylite", opp_a_item_known=True)
    resps = predict_responses(
        state, "p1", "p2", max_candidates=2, priors=ProtectPriors(),
        foe_mega_eligibility=_eligibility_a_only(), opp_mega_click_rate=0.35,
    )
    assert len(resps) == 2
    classes = {("none" if r.foe_mega_slot is None else str(r.foe_mega_slot)) for r in resps}
    assert classes == {"none", "0"}


def test_truncation_and_tie_break_are_deterministic():
    """Same inputs -> identical response_id ordering across repeated calls."""
    state = _doubles_state(opp_a_item="aerodactylite", opp_a_item_known=True)
    first = predict_responses(
        state, "p1", "p2", max_candidates=2, priors=ProtectPriors(),
        foe_mega_eligibility=_eligibility_a_only(), opp_mega_click_rate=0.35,
    )
    second = predict_responses(
        state, "p1", "p2", max_candidates=2, priors=ProtectPriors(),
        foe_mega_eligibility=_eligibility_a_only(), opp_mega_click_rate=0.35,
    )
    assert [r.response_id for r in first] == [r.response_id for r in second]


def test_two_eligible_slots_split_mega_weight_50_50():
    state = _doubles_state(opp_a_item="aerodactylite", opp_a_item_known=True)
    state.sides["p2"]["b"] = PokemonState(
        species="Meganium", hp=100, max_hp=100, item="meganiumite", item_known=True,
    )
    eligibility = {
        "a": mega_form_for("Aerodactyl", "Aerodactylite"),
        "b": mega_form_for("Meganium", "Meganiumite"),
    }
    resps = predict_responses(
        state, "p1", "p2", max_candidates=10, priors=ProtectPriors(),
        foe_mega_eligibility=eligibility, opp_mega_click_rate=0.35,
    )
    # Compare within response families where BOTH slots take move-class actions.
    # A pivot family legitimately excludes its switching slot and therefore must
    # not be used to assert a global 50/50 total across all families.
    labels_with_both = {
        r.label for r in resps if r.foe_mega_slot == 0
    } & {
        r.label for r in resps if r.foe_mega_slot == 1
    }
    assert labels_with_both
    for label in labels_with_both:
        slot0_weight = sum(
            r.weight for r in resps if r.label == label and r.foe_mega_slot == 0
        )
        slot1_weight = sum(
            r.weight for r in resps if r.label == label and r.foe_mega_slot == 1
        )
        assert slot0_weight == pytest.approx(slot1_weight, rel=1e-6)


def test_legacy_call_without_mega_kwargs_is_byte_identical_to_before(monkeypatch):
    """Reg-I / format_config=None safety net: omitting foe_mega_eligibility and
    opp_mega_click_rate entirely must reproduce today's exact response set
    (same labels, same weights, same count, same truncate-before-weight order)."""
    state = _doubles_state()
    resps = predict_responses(state, "p1", "p2", max_candidates=5, priors=ProtectPriors())
    assert all(r.foe_mega_slot is None for r in resps)
    assert all(r.response_id == f"{r.label}|mega=none" for r in resps)
    assert sum(r.weight for r in resps) == pytest.approx(1.0)
```

**Step 2 — confirm RED:** `python -m pytest tests/i7b/test_i7b_responses.py -q` → `ImportError` (`OpponentResponseCapError` does not exist; new kwargs not accepted).

**Step 3 — implement** in `battle/opponent.py`. Add the exception class near `InvalidOppMegaClickRateError`:

```python
class OpponentResponseCapError(ValueError):
    """format_config.mega is in play and the number of mandatory reserve
    classes (no-mega + one per eligible foe Mega slot) exceeds max_candidates.
    Raised BEFORE response expansion/truncation -- never silently drops a
    required class (spec §9.5)."""
```

Modify `predict_responses`'s signature (existing signature at `opponent.py:179-192`) to add the two new keyword-only parameters (defaults preserve every existing call site unchanged):

**Add one new module-level constant** next to this signature (Rev. 3 finding 7): `DEFAULT_MAX_CANDIDATES = 5`, and use it as the default below instead of a bare literal — so I7b-C's sidecar writer (Task 1/2) can import the SAME value it reports as `max_candidates` in every row, rather than a second, independently-typed literal `5` that could silently drift from the real cap if this default is ever tuned.

```python
DEFAULT_MAX_CANDIDATES = 5


def predict_responses(
    state: BattleState,
    our_side: str,
    opp_side: str,
    *,
    speed_oracle=None,
    book=None,
    dex: SpeciesDex | None = None,
    field: FieldState | None = None,
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
    priors=None,
    threatened_slots: set[str] | None = None,
    opp_sets: dict | None = None,
    foe_mega_eligibility: dict[str, MegaForm] | None = None,
    opp_mega_click_rate: float | None = None,
) -> list[OppResponse]:
```

**[REV.2 correction]** the review confirmed two real defects in the Rev. 1 body below: (a) the cap check ran **after** building the fully-expanded+weighted list, instead of **before** expansion (spec §9.5's own binding order); (b) a pivot/switch response's switching slot could wrongly grow a Mega twin (Mega Evolution and switching are mutually exclusive for the same mon on the same turn). Both are fixed in the corrected body below — the cap check now runs immediately after computing `classes`, before any twin is built, and `eligible_here` now excludes any slot whose action in *this specific response* has `kind == "switch"`.

Replace the body from the existing `responses = responses[:max_candidates]` line (`opponent.py:275`) through the end of the function with:

```python
    mega_active = bool(foe_mega_eligibility) and opp_mega_click_rate is not None

    if not mega_active:
        # Byte-identical to pre-I7b-A behavior, with response_id populated
        # (harmless -- consumed by nothing that affects weight/choice today).
        responses = responses[:max_candidates]
        for r in responses:
            r.response_id = f"{r.label}|mega=none"
        if priors is not None and responses:
            _apply_protect_prior_split(responses, opp_mons, opp_slots, priors, threatened_slots)
        return responses

    # --- I7b mega-aware pipeline (spec §9.4/§9.5): cap-check -> expand -> weight -> ---
    # --- coverage-preserving truncate -> renormalize                                ---

    # Cap check FIRST, before any expansion (spec §9.5 binding order; Rev. 1 checked
    # this only after expansion -- corrected here).
    classes = {"none"} | {str(0 if s == "a" else 1) for s in foe_mega_eligibility}
    if len(classes) > max_candidates:
        raise OpponentResponseCapError(
            f"format_config.mega requires {len(classes)} reserve classes "
            f"({sorted(classes)}) but max_candidates={max_candidates}"
        )

    for r in responses:
        r.response_id = f"{r.label}|mega=none"
    if priors is not None and responses:
        _apply_protect_prior_split(responses, opp_mons, opp_slots, priors, threatened_slots)
    else:
        n = len(responses) or 1
        for r in responses:
            r.weight = 1.0 / n

    expanded: list[OppResponse] = []
    for family in responses:
        expanded.append(family)
        # A slot whose action IN THIS RESPONSE is a switch cannot also Mega this
        # turn -- Mega Evolution requires a move-class action. Exclude it from
        # this family's twin expansion (Codex review: pivot/switch must never
        # grow a Mega variant for the switching slot).
        acting_move_slots = {a.slot for a in family.actions if a.kind != "switch"}
        eligible_here = sorted(acting_move_slots & foe_mega_eligibility.keys())
        family_mega_weight = family.weight * opp_mega_click_rate
        family.weight *= (1.0 - opp_mega_click_rate)
        n_split = len(eligible_here) or 1
        for slot in eligible_here:
            slot_index = 0 if slot == "a" else 1
            twin = OppResponse(
                actions=list(family.actions),
                label=family.label,
                flags=set(family.flags),
                weight=family_mega_weight / n_split,
                response_id=f"{family.label}|mega={slot_index}",
                foe_mega_slot=slot_index,
            )
            expanded.append(twin)

    total = sum(r.weight for r in expanded)
    if total > 0:
        for r in expanded:
            r.weight /= total

    def _class_of(r: OppResponse) -> str:
        return "none" if r.foe_mega_slot is None else str(r.foe_mega_slot)

    reserved: dict[str, OppResponse] = {}
    for cls in classes:
        candidates = [r for r in expanded if _class_of(r) == cls]
        reserved[cls] = sorted(candidates, key=lambda r: (-r.weight, r.response_id))[0]
    reserved_ids = {id(r) for r in reserved.values()}
    remaining_budget = max_candidates - len(reserved)
    unreserved = sorted(
        (r for r in expanded if id(r) not in reserved_ids),
        key=lambda r: (-r.weight, r.response_id),
    )
    kept = list(reserved.values()) + unreserved[:remaining_budget]
    kept.sort(key=lambda r: r.response_id)

    total_kept = sum(r.weight for r in kept)
    if total_kept > 0:
        for r in kept:
            r.weight /= total_kept

    return kept
```

Note: `reserved[cls] = sorted(candidates, key=lambda r: (-r.weight, r.response_id))[0]` picks highest weight first, `response_id` lexicographic ascending on ties, uniformly for every class (Rev. 1 had a dead `len(candidates) == 1` special-case branch that could never diverge from this sort's own result on a singleton list — removed entirely in Rev. 2, one code path only).

**New Rev. 2 regression test** (append to `test_i7b_responses.py`, alongside the existing cap/truncation tests):

```python
def test_pivot_switch_slot_never_grows_a_mega_twin():
    """Codex review: a slot that switches this response cannot also Mega."""
    state = _doubles_state(opp_a_item="aerodactylite", opp_a_item_known=True)
    resps = predict_responses(
        state, "p1", "p2", max_candidates=10, priors=ProtectPriors(),
        foe_mega_eligibility=_eligibility_a_only(), opp_mega_click_rate=0.35,
    )
    pivot = next(r for r in resps if "pivot" in r.label and r.foe_mega_slot is None)
    switching_slots = {a.slot for a in pivot.actions if a.kind == "switch"}
    assert "a" in switching_slots  # confirms this response's slot "a" switches
    mega_twins_for_pivot_family = [
        r for r in resps if r.label == "pivot" and r.foe_mega_slot == 0
    ]
    assert mega_twins_for_pivot_family == []
```

Extract the existing Protect-prior weight-split logic (currently inline at `opponent.py:277-294`) into a small private helper `_apply_protect_prior_split(responses, opp_mons, opp_slots, priors, threatened_slots)` with the exact same body as today, so both the legacy branch and the new branch call the identical, unmodified logic (no duplicated/diverging copy):

```python
def _apply_protect_prior_split(responses, opp_mons, opp_slots, priors, threatened_slots) -> None:
    threatened_slots = threatened_slots or set()
    pslot = opp_slots[0]
    p_protect = priors.rate(
        opp_mons[pslot].species,
        threatened=pslot in threatened_slots,
        consecutive=opp_mons[pslot].consecutive_protect,
    )
    non_protect = [r for r in responses if "protect" not in r.label]
    for r in responses:
        if "protect" in r.label:
            r.weight = p_protect
        else:
            r.weight = (1.0 - p_protect) / len(non_protect) if non_protect else 0.0
    total = sum(r.weight for r in responses)
    if total > 0:
        for r in responses:
            r.weight /= total
```

**Step 4 — verify:**
```powershell
python -m pytest tests/i7b/ tests/test_opponent.py tests/test_protect_priors.py -q
```
Expected: every new test passes; every pre-existing `test_opponent.py`/`test_protect_priors.py` test still passes unchanged (legacy path untouched in behavior).

**Step 5 — commit:**
```powershell
git add src/showdown_bot/battle/opponent.py tests/i7b/
git commit -m "feat(champions-i7b-a): coverage-preserving mega/no-mega response pipeline"
```

### Task 5: config-hash wiring for the click-rate knob

**Step 1 — write failing test**, append to `showdown_bot/tests/test_config_env.py`:

```python
def test_opp_mega_click_rate_is_behavior_affecting_and_classified():
    assert "SHOWDOWN_OPP_MEGA_CLICK_RATE" in BEHAVIOR_AFFECTING
    assert is_classified("SHOWDOWN_OPP_MEGA_CLICK_RATE")


def test_behavior_env_includes_opp_mega_click_rate(monkeypatch):
    monkeypatch.setenv("SHOWDOWN_OPP_MEGA_CLICK_RATE", "0.5")
    assert behavior_env()["SHOWDOWN_OPP_MEGA_CLICK_RATE"] == "0.5"


def test_config_hash_changes_when_opp_mega_click_rate_toggled(monkeypatch):
    monkeypatch.setenv("SHOWDOWN_OPP_MEGA_CLICK_RATE", "0.20")
    m1 = build_config_manifest(agent="a", format_id="f", priors_hash="p", spreads_hash="s")
    monkeypatch.setenv("SHOWDOWN_OPP_MEGA_CLICK_RATE", "0.50")
    m2 = build_config_manifest(agent="a", format_id="f", priors_hash="p", spreads_hash="s")
    assert make_config_hash(m1) != make_config_hash(m2)
```

(`build_config_manifest`'s default `env=None` resolves to `behavior_env()` per its existing docstring — no new kwarg needed; `make_config_hash`/`behavior_env`/`build_config_manifest`/`is_classified`/`BEHAVIOR_AFFECTING` are all already imported at the top of `test_config_env.py`.)

**Step 2 — confirm RED:** `python -m pytest tests/test_config_env.py -k opp_mega_click_rate -q` → `AssertionError` (name not yet in `BEHAVIOR_AFFECTING`; env var not yet read anywhere in source, so `test_behavior_affecting_flags_are_actually_read_in_source` would also newly fail once the name is added without a real read — implement Task 3 first, which it already is by this point in the plan, so the read exists).

**Step 3 — implement** in `eval/config_env.py`: add `"SHOWDOWN_OPP_MEGA_CLICK_RATE"` to the `BEHAVIOR_AFFECTING` frozenset (`config_env.py:23-82`), with an inline comment matching the existing style:

```python
    # [I7b] Opponent Mega click-rate prior (opponent.opp_mega_click_rate) -- changes
    # the weight split between an opponent's no-mega and mega response twins ->
    # directly changes aggregate scoring -> config_hash.
    "SHOWDOWN_OPP_MEGA_CLICK_RATE",
```

**Step 4 — verify:**
```powershell
python -m pytest tests/test_config_env.py -q
```
Expected: all pass, including the existing drift tests `test_every_showdown_env_read_is_classified` and `test_behavior_affecting_flags_are_actually_read_in_source` (the latter now finds a real `os.environ.get("SHOWDOWN_OPP_MEGA_CLICK_RATE"` read in `battle/opponent.py` from Task 3).

**Step 5 — commit:**
```powershell
git add src/showdown_bot/eval/config_env.py tests/test_config_env.py
git commit -m "feat(champions-i7b-a): wire SHOWDOWN_OPP_MEGA_CLICK_RATE into config_hash"
```

### I7b-A completion gate

- [ ] Every new test in `tests/i7b/test_i7b_eligibility.py`, `tests/i7b/test_i7b_responses.py`, and the `test_config_env.py` additions individually confirmed RED before its implementation, GREEN after.
- [ ] `python -m pytest tests/i7b/ tests/test_opponent.py tests/test_protect_priors.py tests/test_config_env.py -q` — full pass.
- [ ] Full suite: `python -m pytest -q` — full pass, same skip/xfail count as the pre-slice baseline plus the new I7b-A tests.
- [ ] `git diff --check` clean.
- [ ] No caller in `battle/decision.py`, `battle/mega_scoring.py`, or `battle/baselines.py` was modified — `predict_responses`'s new kwargs are unreachable from any live decision path (confirm via `grep -rn "foe_mega_eligibility=" src/showdown_bot/battle/decision.py src/showdown_bot/battle/mega_scoring.py src/showdown_bot/battle/baselines.py` returning nothing).
- [ ] Working tree clean; no push; no I7b-B work started.

---

## I7b-B: Dual projection, activation ordering, scoring integration

**Files this slice creates:**
- `showdown_bot/tests/i7b/conftest.py`
- `showdown_bot/tests/i7b/test_i7b_projection.py`
- `showdown_bot/tests/i7b/test_i7b_scoring.py`

**Files this slice modifies [REV.4]:**
- `showdown_bot/src/showdown_bot/engine/speed.py` (`mega_activation_order_key`, Task 1)
- `showdown_bot/src/showdown_bot/engine/mega_projection.py` (side-aware `project_mega` contract, Task 2; `compose_mega_projection_branches`/`WeightedMegaProjection`, Task 3)
- `showdown_bot/src/showdown_bot/battle/mega_scoring.py` (`ScoredResponseEvidence`, corrected `score_evaluated_variants`, Task 4; fail-closed ability gate proof, Task 5; depth-2 threading, Task 6)
- `showdown_bot/src/showdown_bot/battle/decision.py` (`_choose_best_mega`'s `score_evaluated_variants` call site only, Task 4)

**`showdown_bot/src/showdown_bot/battle/opponent.py` and `showdown_bot/src/showdown_bot/battle/baselines.py` are NOT modified in this slice** — Rev. 1 wrongly planned to rebuild `PlannedAction`s inside `predict_responses` itself (deleted, folded into Task 4's lazy per-response composition) and to wire `_max_damage_choice_mega` (deleted entirely — `max_damage` never models opponent responses, audit §Rev.2 finding 4).

**Explicitly excludes:** any trace/sidecar file, ROADMAP/PROJECT_INDEX, any live battle, Strength claims, `SHOWDOWN_MEGA_MARGIN`, `battle/baselines.py`.

**Fixture-wiring note:** Task 2 below introduces `showdown_bot/tests/i7b/conftest.py` with concrete, real (not fake) fixtures (`i7b_projection_env`, `i7b_aerodactyl_spreads`, `i7b_froslass_spreads`, `opp_sets_meganium`, `i7b_opp_sets_tyranitar`) — every test in Tasks 2-3 uses these directly, resolving Rev. 1's earlier "illustrative fixture names" gap. Names are `i7b_`-prefixed wherever a same-named-but-differently-shaped fixture exists in the sibling `tests/i7a/conftest.py` (Rev. 3 finding 6c: `tests/i7b/` cannot see `tests/i7a/conftest.py`'s fixtures automatically anyway, since it is a sibling directory, not a subdirectory — this suite builds its own self-contained fixtures rather than importing, and the distinct names remove any residual ambiguity for a reader skimming both directories). Task 4 extends the real shared `tests/conftest.py::mega_decision_fixture` additively with the exact scoring dependencies shown in Task 4 Step 0; no test assumes undeclared dictionary keys.

### Task 1: `mega_activation_order_key`

**Step 1 — write failing tests** in new file `showdown_bot/tests/i7b/test_i7b_projection.py`:

```python
"""I7b-B: mega_activation_order_key, WeightedMegaProjection, compose_mega_projection_branches."""
from __future__ import annotations

from showdown_bot.engine.speed import mega_activation_order_key
from showdown_bot.engine.state import FieldState


def test_no_trick_room_higher_speed_sorts_first():
    field = FieldState()
    keyed = sorted([("slow", 80), ("fast", 150)], key=lambda t: mega_activation_order_key(t[1], field))
    assert keyed[0][0] == "fast"


def test_trick_room_lower_speed_sorts_first():
    field = FieldState(trick_room=True)
    keyed = sorted([("slow", 80), ("fast", 150)], key=lambda t: mega_activation_order_key(t[1], field))
    assert keyed[0][0] == "slow"


def test_matches_sort_actions_sign_convention():
    """mega_activation_order_key must use the IDENTICAL sign convention as
    resolve.sort_actions -- not an independently-invented one."""
    from showdown_bot.battle.resolve import sort_actions, PlannedAction
    from showdown_bot.engine.moves import get_move_meta

    field = FieldState(trick_room=True)
    a = PlannedAction(side="p1", slot="a", kind="move", speed=150, move=get_move_meta("Tackle"))
    b = PlannedAction(side="p2", slot="a", kind="move", speed=80, move=get_move_meta("Tackle"))
    resolver_order = [act.slot + act.side for act in sort_actions([a, b], field)]
    key_order = sorted([("a" + "p1", 150), ("a" + "p2", 80)], key=lambda t: mega_activation_order_key(t[1], field))
    assert [x[0] for x in key_order] == resolver_order
```

**Step 2 — confirm RED:** `python -m pytest tests/i7b/test_i7b_projection.py -k order_key -q` → `ImportError`.

**Step 3 — implement** in `engine/speed.py` (add near the top-level functions, after `effective_speed`):

```python
def mega_activation_order_key(pre_mega_speed: int, field: FieldState) -> int:
    """Sort key for Mega-activation order (queue priority 104, Showdown pin
    f8ac140): same speed direction as ``battle.resolve.sort_actions`` uses for
    its own queue ordering -- higher pre-mega speed activates first outside
    Trick Room, lower activates first under it. Ascending sort by this key
    reproduces that order; do not invent a different sign convention."""
    return pre_mega_speed if field.trick_room else -pre_mega_speed
```

**Step 4 — verify:** `python -m pytest tests/i7b/test_i7b_projection.py -q`.

**Step 5 — commit:**
```powershell
git add src/showdown_bot/engine/speed.py tests/i7b/test_i7b_projection.py
git commit -m "feat(champions-i7b-b): mega_activation_order_key (TR-aware, resolver-consistent)"
```

### Task 2 (was: Task 0) — side-aware `project_mega` contract + species coherence gate [REV.2 origin; REV.5 adds the coherence gate; mandatory before anything else in this slice]

**Confirmed P1 blocker (audit §Rev.2 finding 2), not a possible future stop.** `project_mega` (`engine/mega_projection.py:60-115`) hardcodes `lookup_our_spreads(spread_lookup, mon)` (line 93) and `opp_sets=None, book=None, is_ours=True` (lines 104-106) regardless of the `side` argument — calling it with `side=opp_side` today would silently look up the foe's spread via the WRONG accessor and always claim `is_ours=True` to `speed_for_species`. This must be fixed, tested, and green **before** Task 3 (`compose_mega_projection_branches`) is written, since that function calls `project_mega` for both own- and foe-side activations.

**Step 1 — write failing tests**, new section in `test_i7b_projection.py` (create the file with this section first; Task "1" `mega_activation_order_key` tests from above are unaffected and stay in the same file):

```python
"""I7b-B Task 2: side-aware project_mega contract."""
import pytest

from showdown_bot.engine.mega_form import mega_form_for
from showdown_bot.engine.mega_projection import project_mega
from showdown_bot.engine.state import BattleState, PokemonState


def _dual_capable_state() -> BattleState:
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Aerodactyl", item="aerodactylite", item_known=True, hp=100, max_hp=100)
    st.sides["p1"]["b"] = PokemonState(species="Sneasler", hp=100, max_hp=100)
    st.sides["p2"]["a"] = PokemonState(species="Meganium", item="meganiumite", item_known=True, hp=100, max_hp=100)
    st.sides["p2"]["b"] = PokemonState(species="Incineroar", hp=100, max_hp=100)
    return st


def test_project_mega_for_foe_side_uses_opp_set_lookup_not_our_spreads(i7b_projection_env, opp_sets_meganium):
    """A foe-side project_mega call must resolve its spread via lookup_opp_set
    (the curated opp_sets/likely_sets source), never lookup_our_spreads."""
    state = _dual_capable_state()
    form = mega_form_for("Meganium", "Meganiumite")

    result = project_mega(
        state, "p2", "a", form, species_meta=i7b_projection_env["species_meta"],
        speed_oracle=i7b_projection_env["speed_oracle"], calc_profile=i7b_projection_env["calc_profile"],
        is_ours=False, opp_sets=opp_sets_meganium, book=None,
    )
    assert result.projected_state.sides["p2"]["a"].species == "Meganium-Mega"
    assert result.effective_speed > 0


def test_project_mega_for_foe_side_without_any_opp_set_or_book_fails_closed(i7b_projection_env):
    """No spread source at all for the foe -- must raise MissingMegaSpreadError,
    the same fail-closed contract the own-side path already has, never silently
    default to some own-side spread."""
    from showdown_bot.engine.speed import MissingMegaSpreadError

    state = _dual_capable_state()
    form = mega_form_for("Meganium", "Meganiumite")
    with pytest.raises(MissingMegaSpreadError):
        project_mega(
            state, "p2", "a", form, species_meta=i7b_projection_env["species_meta"],
            speed_oracle=i7b_projection_env["speed_oracle"], calc_profile=i7b_projection_env["calc_profile"],
            is_ours=False, opp_sets=None, book=None,
        )


def test_project_mega_for_foe_side_accepts_book_without_opp_sets(i7b_projection_env):
    """The real SpeedOracle contract checks the SpreadBook first and only then
    falls back to opp_sets. project_mega must not reject this valid book-only
    path before SpeedOracle gets a chance to resolve it."""
    from showdown_bot.engine.belief.hypotheses import SpreadBook, SpeciesSpreads, SpreadPreset

    state = _dual_capable_state()
    form = mega_form_for("Meganium", "Meganiumite")
    preset = SpreadPreset(nature="Bold", evs={"hp": 32, "def": 32}, items=["Meganiumite"])
    spreads = SpeciesSpreads(offense=preset, defense=preset)
    book = SpreadBook(default=spreads, species={"meganium": spreads})

    result = project_mega(
        state, "p2", "a", form, species_meta=i7b_projection_env["species_meta"],
        speed_oracle=i7b_projection_env["speed_oracle"], calc_profile=i7b_projection_env["calc_profile"],
        is_ours=False, opp_sets=None, book=book,
    )
    assert result.projected_state.sides["p2"]["a"].species == "Meganium-Mega"
    assert result.effective_speed > 0


def test_project_mega_own_side_default_is_byte_identical_to_before(i7b_projection_env, i7b_aerodactyl_spreads):
    """Regression: every existing I7a call site omits is_ours/opp_sets/book --
    the own-side default behavior (lookup_our_spreads, is_ours=True) must be
    completely unchanged."""
    state = _dual_capable_state()
    form = mega_form_for("Aerodactyl", "Aerodactylite")
    result = project_mega(
        state, "p1", "a", form, species_meta=i7b_projection_env["species_meta"],
        speed_oracle=i7b_projection_env["speed_oracle"], calc_profile=i7b_projection_env["calc_profile"],
        spread_lookup=i7b_aerodactyl_spreads,
    )
    assert result.projected_state.sides["p1"]["a"].species == "Aerodactyl-Mega"


def test_project_mega_rejects_species_form_mismatch_and_does_not_mutate(i7b_projection_env, opp_sets_meganium):
    """[REV.5 correction 2] project_mega must fail closed when the slot's mon is
    not the form's base species. Rev. 4 had no such check: it wrote
    `mon.species = form_meta.form_species_name` unconditionally, so an
    Aerodactyl-Mega form projected onto an Incineroar silently "succeeded" --
    which is exactly what Rev. 4's own Task 4 tests were accidentally relying on.
    The input state must also come back unmutated."""
    from copy import deepcopy

    from showdown_bot.engine.mega_projection import MegaProjectionSpeciesMismatchError

    state = BattleState()
    state.sides["p2"]["a"] = PokemonState(
        species="Incineroar", base_species_id="incineroar", hp=100, max_hp=100,
    )
    before = deepcopy(state)
    form = mega_form_for("Aerodactyl", "Aerodactylite")  # base_species_id="aerodactyl"

    with pytest.raises(MegaProjectionSpeciesMismatchError):
        project_mega(
            state, "p2", "a", form, species_meta=i7b_projection_env["species_meta"],
            speed_oracle=i7b_projection_env["speed_oracle"],
            calc_profile=i7b_projection_env["calc_profile"],
            is_ours=False, opp_sets=opp_sets_meganium, book=None,
        )
    assert state == before  # fail-closed must not leave a half-projected board


def test_project_mega_accepts_already_mega_species_via_base_species_id(i7b_projection_env, i7b_aerodactyl_spreads):
    """[REV.5 correction 2] The coherence check matches on normalized
    base_species_id OR normalized species -- so a valid sub-form mapping (a mon
    whose `species` already reads "Aerodactyl-Mega" but whose `base_species_id`
    is still "aerodactyl") is NOT rejected. Pins the `or` half of the rule; a
    species-only check would break this."""
    state = BattleState()
    state.sides["p1"]["a"] = PokemonState(
        species="Aerodactyl-Mega", base_species_id="aerodactyl",
        item="Aerodactylite", hp=100, max_hp=100,
    )
    form = mega_form_for("Aerodactyl", "Aerodactylite")
    result = project_mega(
        state, "p1", "a", form, species_meta=i7b_projection_env["species_meta"],
        speed_oracle=i7b_projection_env["speed_oracle"],
        calc_profile=i7b_projection_env["calc_profile"],
        spread_lookup=i7b_aerodactyl_spreads,
    )
    assert result.projected_state.sides["p1"]["a"].species == "Aerodactyl-Mega"
```

`i7b_projection_env` and `opp_sets_meganium` are new fixtures added to a new `showdown_bot/tests/i7b/conftest.py` (this is the file that resolves the "fixture-wiring correction" note above — write it now, not later):

```python
"""Shared fixtures for tests/i7b/ -- real SpeedOracle/calc_profile/species_meta,
built the same way tests/conftest.py::mega_decision_fixture already does (real
SubprocessCalcBackend, real calc_profile_from_config), never a fake/stub."""
from __future__ import annotations

import pytest


@pytest.fixture
def i7b_projection_env():
    from showdown_bot.engine.calc.client import SubprocessCalcBackend
    from showdown_bot.engine.calc_profile import calc_profile_from_config
    from showdown_bot.engine.format_config import load_format_config
    from showdown_bot.engine.speed import SpeedOracle
    from showdown_bot.engine.species_meta import species_meta_table

    cfg = load_format_config("gen9championsvgc2026regma")
    calc_profile = calc_profile_from_config(cfg)
    speed_oracle = SpeedOracle(stats_backend=SubprocessCalcBackend(), profile=calc_profile)
    return {"speed_oracle": speed_oracle, "calc_profile": calc_profile, "species_meta": species_meta_table()}


@pytest.fixture
def opp_sets_meganium():
    """`evs={"hp": 32, "def": 32}` -- matches the project's established modest-
    EV test-double convention (tests/conftest.py::mega_decision_fixture,
    tests/i7a/conftest.py::aerodactyl_spreads), not the standard-competitive
    252-max scale (Rev. 3 audit finding 6b: earlier draft used 252 here,
    inconsistent with every sibling fixture in this suite). Verified via
    direct SpeedOracle._base_speed computation against the real calc backend
    that Meganium (base Speed 60) stays well below Aerodactyl's
    i7b_aerodactyl_spreads (100 vs 200 pre-mega Speed) at this same modest
    investment -- not merely assumed from base-stat intuition."""
    from showdown_bot.engine.belief.hypotheses import SpeciesSpreads, SpreadPreset

    preset = SpreadPreset(nature="Bold", evs={"hp": 32, "def": 32}, items=["Meganiumite"])
    return {"meganium": SpeciesSpreads(offense=preset, defense=preset)}


@pytest.fixture
def i7b_aerodactyl_spreads():
    """Deliberately NOT named `aerodactyl_spreads` and NOT imported from the
    sibling `tests/i7a/conftest.py::aerodactyl_spreads` fixture (Rev. 3 audit
    finding 6c, resolved definitively): `tests/i7b/` is a SIBLING of
    `tests/i7a/`, not a subdirectory, so pytest's directory-scoped conftest.py
    discovery does NOT make i7a's fixtures visible here automatically, and a
    `pytest_plugins` cross-import would assert an unverified rootdir-relative
    module path. This project builds its own self-contained, i7b-prefixed
    fixture instead of importing or risking a same-name shadowing collision
    with a fixture of a DIFFERENT shape (i7a's version returns a bare
    `SpeciesSpreads`; every I7b-B call site in this plan expects a
    species-keyed dict, matching `opp_sets_meganium` above) -- same EV values
    as the sibling (32/32/2) for realism-consistency, but a distinct name and
    a distinct (dict) shape, so there is no ambiguity either way."""
    from showdown_bot.engine.belief.hypotheses import SpeciesSpreads, SpreadPreset

    preset = SpreadPreset(nature="Jolly", evs={"atk": 32, "spe": 32, "hp": 2}, items=["Aerodactylite"])
    return {"aerodactyl": SpeciesSpreads(offense=preset, defense=preset)}
```

**Step 2 — confirm RED:** `python -m pytest tests/i7b/test_i7b_projection.py -k project_mega -q` → `TypeError` (`project_mega` doesn't accept `is_ours`/`opp_sets`/`book` yet).

**Step 3 — implement**: modify `project_mega`'s signature (`engine/mega_projection.py:60-70`) to add three new keyword-only parameters, defaulted to preserve every existing (own-side) call site byte-for-byte:

```python
def project_mega(
    state: BattleState,
    side: str,
    slot: str,
    mega_form: MegaForm,
    *,
    species_meta: dict[str, SpeciesFormMeta],
    speed_oracle: SpeedOracle,
    spread_lookup: dict | None = None,
    calc_profile: CalcProfile,
    is_ours: bool = True,
    opp_sets: dict | None = None,
    book=None,
) -> MegaProjectionResult:
```

**[REV.5 correction 2] Add the fail-closed species/form coherence check BEFORE any
projection write.** Place it after the existing `form_meta is None` guard and before the
first mutation of the copied state (`mon.species = form_meta.form_species_name`), so a
mismatch can never leave a half-projected board. Add the new exception next to the two
existing ones (`MissingMegaSpreadError`, `UnsupportedMegaAbilityError`):

```python
class MegaProjectionSpeciesMismatchError(ValueError):
    """The mon at (side, slot) is not the mega_form's base species. In production
    this cannot arise -- battle.opponent.foe_mega_eligibility derives every form
    from mega_form_for(mon.species, mon.item) and is coherent by construction, and
    the own side reads its own request -- so reaching this is a real programming
    error. Fail closed rather than silently rewriting an unrelated mon's species
    (Rev. 4 projected Aerodactyl-Mega onto an Incineroar without complaint)."""
```

```python
    mon = projected_state.sides[side][slot]
    # Match on normalized base_species_id OR normalized species: the `or` keeps
    # valid sub-form mappings working (e.g. an already-Mega'd mon whose species
    # reads "Aerodactyl-Mega" while base_species_id is still "aerodactyl").
    _candidates = {to_id(mon.base_species_id or ""), to_id(mon.species or "")}
    if mega_form.base_species_id not in _candidates:
        raise MegaProjectionSpeciesMismatchError(
            f"{side}/{slot} is {mon.species!r} (base {mon.base_species_id!r}) "
            f"but mega_form base is {mega_form.base_species_id!r}"
        )
```

Needs `to_id` (`showdown_bot.engine.state`) imported in `mega_projection.py` if not already
present — verify before wiring rather than assuming. Every existing I7a call site projects
a coherent own-side form, so all of `tests/i7a/` must stay green unchanged; that is the
regression signal for this check being correctly scoped.

Replace the body's spread-resolution block (currently lines 93-107) with a single call to the existing central resolver. Do **not** preflight the foe with `lookup_opp_set`: `SpeedOracle.speed_for_species` already implements the binding lookup order `book` first, then `opp_sets`, and raises `MissingMegaSpreadError` only when both fail.

```python
    effective_speed = speed_oracle.speed_for_species(
        species_name=form_meta.form_species_name,
        base_species_id=mega_form.base_species_id,
        side=side,
        mon=mon,
        field=projected_state.field,
        our_spreads=spread_lookup if is_ours else None,
        opp_sets=opp_sets if not is_ours else None,
        book=book,
        is_ours=is_ours,
    )
```

Remove `lookup_our_spreads` from `mega_projection.py` if this replacement leaves it unused; do not add `lookup_opp_set` there. Note `spread_lookup`'s type hint changes from `dict` to `dict | None = None` (own-side callers that always pass a real dict are unaffected; the parameter is simply now optional for the `is_ours=False` path, where it is passed through as `None`). The tests above pin all three outcomes: own lookup, foe `opp_sets`, and foe `book`-only, plus fail-closed when neither source resolves.

**Step 4 — verify:**
```powershell
python -m pytest tests/i7b/test_i7b_projection.py tests/i7a/ -q
```
Expected: new tests pass; every existing I7a test that calls `project_mega` (own-side, no new kwargs) remains green — confirms the default `is_ours=True` path is unchanged.

**Step 5 — commit:**
```powershell
git add src/showdown_bot/engine/mega_projection.py tests/i7b/conftest.py tests/i7b/test_i7b_projection.py
git commit -m "feat(champions-i7b-b): side-aware project_mega contract + species coherence gate"
```

### Task 3: `WeightedMegaProjection` and `compose_mega_projection_branches`

**Step 1 — write failing tests**, append to `test_i7b_projection.py`:

```python
from showdown_bot.engine.mega_projection import (
    WeightedMegaProjection,
    compose_mega_projection_branches,
    copy_battle_state,
)
from showdown_bot.engine.mega_form import mega_form_for
from showdown_bot.engine.state import BattleState, PokemonState


def _dual_mega_state() -> BattleState:
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(species="Aerodactyl", item="aerodactylite", item_known=True, hp=100, max_hp=100)
    st.sides["p1"]["b"] = PokemonState(species="Sneasler", hp=100, max_hp=100)
    st.sides["p2"]["a"] = PokemonState(species="Meganium", item="meganiumite", item_known=True, hp=100, max_hp=100)
    st.sides["p2"]["b"] = PokemonState(species="Incineroar", hp=100, max_hp=100)
    return st


def test_unequal_pre_mega_speed_yields_one_full_weight_branch(i7b_projection_env, i7b_aerodactyl_spreads, opp_sets_meganium):
    # Aerodactyl (~200 pre-mega speed) unambiguously outspeeds Meganium here.
    state = _dual_mega_state()
    activations = [
        ("p1", "a", mega_form_for("Aerodactyl", "Aerodactylite")),
        ("p2", "a", mega_form_for("Meganium", "Meganiumite")),
    ]
    branches = compose_mega_projection_branches(
        state, activations, our_side="p1", speed_oracle=i7b_projection_env["speed_oracle"],
        our_spreads=i7b_aerodactyl_spreads, opp_sets=opp_sets_meganium, book=None,
        species_meta=i7b_projection_env["species_meta"], calc_profile=i7b_projection_env["calc_profile"],
    )
    assert len(branches) == 1
    assert branches[0].weight == 1.0
    assert branches[0].activation_order[0] == ("p1", "a")  # Aerodactyl (faster) activates first


def test_equal_pre_mega_speed_yields_two_half_weight_branches(
    i7b_projection_env, i7b_aerodactyl_spreads, opp_sets_meganium, monkeypatch,
):
    """Force equal pre-mega speed via a direct monkeypatch on speed_for_species
    (real fixture, patched return value -- not a fake stand-in class)."""
    state = _dual_mega_state()
    activations = [
        ("p1", "a", mega_form_for("Aerodactyl", "Aerodactylite")),
        ("p2", "a", mega_form_for("Meganium", "Meganiumite")),
    ]
    monkeypatch.setattr(
        i7b_projection_env["speed_oracle"], "speed_for_species", lambda **kwargs: 150,
    )
    branches = compose_mega_projection_branches(
        state, activations, our_side="p1", speed_oracle=i7b_projection_env["speed_oracle"],
        our_spreads=i7b_aerodactyl_spreads, opp_sets=opp_sets_meganium, book=None,
        species_meta=i7b_projection_env["species_meta"], calc_profile=i7b_projection_env["calc_profile"],
    )
    assert len(branches) == 2
    assert {b.weight for b in branches} == {0.5}
    orders = {b.activation_order for b in branches}
    assert orders == {
        (("p1", "a"), ("p2", "a")),
        (("p2", "a"), ("p1", "a")),
    }  # both permutations present, no third/duplicate order


def test_compose_never_mutates_input_state(i7b_projection_env, i7b_aerodactyl_spreads, opp_sets_meganium):
    state = _dual_mega_state()
    before = copy_battle_state(state)
    activations = [
        ("p1", "a", mega_form_for("Aerodactyl", "Aerodactylite")),
        ("p2", "a", mega_form_for("Meganium", "Meganiumite")),
    ]
    compose_mega_projection_branches(
        state, activations, our_side="p1", speed_oracle=i7b_projection_env["speed_oracle"],
        our_spreads=i7b_aerodactyl_spreads, opp_sets=opp_sets_meganium, book=None,
        species_meta=i7b_projection_env["species_meta"], calc_profile=i7b_projection_env["calc_profile"],
    )
    assert state == before


def test_weather_ordering_follows_the_LAST_processed_activator_not_the_first(
    i7b_projection_env, i7b_froslass_spreads, i7b_opp_sets_tyranitar,
):
    """Froslass-Mega (Snow Warning) vs Tyranitar-Mega (Sand Stream), T26 §1,
    CORRECTED per verified pinned Showdown mechanics (audit §Rev.2): the queue
    processes the FASTER pre-mega activator's megaEvo action first (sim/battle.ts
    comparePriority), which fires its weather ability's onStart first
    (sim/pokemon.ts setAbility -> singleEvent('Start', ...) on Mega Evolution,
    confirmed by reading the pinned f8ac140 source) -- then the SLOWER
    activator's megaEvo processes second and its OWN weather ability's onStart
    unconditionally OVERWRITES the field (data/abilities.ts's onStart calls
    field.setWeather(...) unconditionally, no "first setter wins" guard). The
    SLOWER (later-processed) activator's weather is therefore what remains
    active -- NOT the faster one's. This implements the binding Rev. 10 correction
    and matches Rev. 9's own tie-case prose ("last weather-setting ability wins within that
    branch") -- one consistent rule governs both the unequal and tied cases."""
    state = BattleState()
    state.sides["p1"]["a"] = PokemonState(species="Froslass", item="froslassite", item_known=True, hp=100, max_hp=100)
    state.sides["p1"]["b"] = PokemonState(species="Sneasler", hp=100, max_hp=100)
    state.sides["p2"]["a"] = PokemonState(species="Tyranitar", item="tyranitarite", item_known=True, hp=100, max_hp=100)
    state.sides["p2"]["b"] = PokemonState(species="Incineroar", hp=100, max_hp=100)
    activations = [
        ("p1", "a", mega_form_for("Froslass", "Froslassite")),
        ("p2", "a", mega_form_for("Tyranitar", "Tyranitarite")),
    ]
    branches = compose_mega_projection_branches(
        state, activations, our_side="p1", speed_oracle=i7b_projection_env["speed_oracle"],
        our_spreads=i7b_froslass_spreads, opp_sets=i7b_opp_sets_tyranitar, book=None,
        species_meta=i7b_projection_env["species_meta"], calc_profile=i7b_projection_env["calc_profile"],
    )
    assert len(branches) == 1
    last_side, last_slot = branches[0].activation_order[-1]
    expected_weather = "snowscape" if (last_side, last_slot) == ("p1", "a") else "sandstorm"
    assert branches[0].projected_state.field.weather == expected_weather
    # Sanity: this is genuinely the SLOWER activator, not accidentally the faster one.
    assert branches[0].activation_order[-1] != branches[0].activation_order[0]


def test_trick_room_reverses_activation_order_vs_no_tr(i7b_projection_env, i7b_froslass_spreads, i7b_opp_sets_tyranitar, monkeypatch):
    """T26 §2: same speeds, Trick Room on -- activation order reversed vs the
    no-TR unequal-speed case above."""
    state = BattleState()
    state.field.trick_room = True
    state.sides["p1"]["a"] = PokemonState(species="Froslass", item="froslassite", item_known=True, hp=100, max_hp=100)
    state.sides["p1"]["b"] = PokemonState(species="Sneasler", hp=100, max_hp=100)
    state.sides["p2"]["a"] = PokemonState(species="Tyranitar", item="tyranitarite", item_known=True, hp=100, max_hp=100)
    state.sides["p2"]["b"] = PokemonState(species="Incineroar", hp=100, max_hp=100)
    activations = [
        ("p1", "a", mega_form_for("Froslass", "Froslassite")),
        ("p2", "a", mega_form_for("Tyranitar", "Tyranitarite")),
    ]
    tr_branches = compose_mega_projection_branches(
        state, activations, our_side="p1", speed_oracle=i7b_projection_env["speed_oracle"],
        our_spreads=i7b_froslass_spreads, opp_sets=i7b_opp_sets_tyranitar, book=None,
        species_meta=i7b_projection_env["species_meta"], calc_profile=i7b_projection_env["calc_profile"],
    )
    state.field.trick_room = False
    no_tr_branches = compose_mega_projection_branches(
        state, activations, our_side="p1", speed_oracle=i7b_projection_env["speed_oracle"],
        our_spreads=i7b_froslass_spreads, opp_sets=i7b_opp_sets_tyranitar, book=None,
        species_meta=i7b_projection_env["species_meta"], calc_profile=i7b_projection_env["calc_profile"],
    )
    assert len(tr_branches) == 1 and len(no_tr_branches) == 1
    assert tr_branches[0].activation_order != no_tr_branches[0].activation_order
    assert tr_branches[0].activation_order == tuple(reversed(no_tr_branches[0].activation_order))
```

Add two more fixtures to `tests/i7b/conftest.py` (Task 2's file, alongside `i7b_aerodactyl_spreads` already added there — no third `aerodactyl_spreads` re-definition here; that name is reserved, undefined, and unused in this suite, deliberately, per the Rev. 3 finding 6c decision above):

```python
@pytest.fixture
def i7b_froslass_spreads():
    """evs={"spe": 32} (Timid) -- same modest-EV convention as
    i7b_aerodactyl_spreads/opp_sets_meganium (Rev. 3 finding 6b), not 252.
    Verified via direct SpeedOracle._base_speed computation against the real
    calc backend: Froslass, Timid, evs={"spe": 32} -> pre-mega Speed 178,
    unambiguously above i7b_opp_sets_tyranitar's 124 below -- a real,
    checked ordering for test_weather_ordering_follows_the_LAST_processed_
    activator_not_the_first and test_trick_room_reverses_activation_order_
    vs_no_tr (neither test monkeypatches speed here, unlike the Aerodactyl/
    Meganium tie test above, so this ordering must hold for real)."""
    from showdown_bot.engine.belief.hypotheses import SpeciesSpreads, SpreadPreset

    preset = SpreadPreset(nature="Timid", evs={"spe": 32}, items=["Froslassite"])
    return {"froslass": SpeciesSpreads(offense=preset, defense=preset)}


@pytest.fixture
def i7b_opp_sets_tyranitar():
    """evs={"spe": 32} (Jolly) -- same modest-EV convention as the fixtures
    above (Rev. 3 finding 6b). Verified: Tyranitar, Jolly, evs={"spe": 32} ->
    pre-mega Speed 124, unambiguously below i7b_froslass_spreads's 178."""
    from showdown_bot.engine.belief.hypotheses import SpeciesSpreads, SpreadPreset

    preset = SpreadPreset(nature="Jolly", evs={"spe": 32}, items=["Tyranitarite"])
    return {"tyranitar": SpeciesSpreads(offense=preset, defense=preset)}
```

**Step 2 — confirm RED:** `python -m pytest tests/i7b/test_i7b_projection.py -q` → `ImportError` for `WeightedMegaProjection`/`compose_mega_projection_branches`.

**Step 3 — implement** in `engine/mega_projection.py` (add after `project_mega`, using Task 2's side-aware contract):

```python
@dataclass(frozen=True)
class WeightedMegaProjection:
    projected_state: BattleState
    weight: float
    activation_order: tuple[tuple[str, str], ...]


def compose_mega_projection_branches(
    state: BattleState,
    activations: list[tuple[str, str, MegaForm]],
    *,
    our_side: str,
    speed_oracle: SpeedOracle,
    our_spreads: dict | None,
    opp_sets: dict | None,
    book=None,
    species_meta: dict[str, SpeciesFormMeta],
    calc_profile: CalcProfile,
) -> list[WeightedMegaProjection]:
    """Compose 1+ same-turn Mega activations (at most one per side) onto shared
    branch(es). ``our_side`` disambiguates which activation(s) use the own-side
    spread lookup (``our_spreads``) vs the foe-side lookup (``opp_sets``/``book``)
    via Task 2's side-aware ``project_mega`` contract -- never guesses which
    activation is "ours" from list order.

    Unequal pre-mega speed -> one branch, weight 1.0. Equal pre-mega speed ->
    two branches (one per activation-order permutation), each weight 0.5,
    applied sequentially so the LATER activation in that branch's specific
    order overwrites the earlier one's field effects (verified against pinned
    Showdown mechanics -- see the weather-ordering test above; this is a single
    consistent rule for both the tied and unequal-speed cases). Never mutates
    ``state``. No RNG."""
    from showdown_bot.engine.speed import mega_activation_order_key

    pre_mega_speeds: dict[tuple[str, str], int] = {}
    for side, slot, _form in activations:
        mon = state.sides[side][slot]
        is_ours = side == our_side
        pre_mega_speeds[(side, slot)] = speed_oracle.speed_for_species(
            species_name=mon.species, base_species_id=mon.base_species_id or mon.species,
            side=side, mon=mon, field=state.field,
            our_spreads=our_spreads if is_ours else None,
            opp_sets=opp_sets if not is_ours else None,
            book=book, is_ours=is_ours,
        )

    sorted_order = tuple(
        sorted(
            ((side, slot) for side, slot, _form in activations),
            key=lambda pair: mega_activation_order_key(pre_mega_speeds[pair], state.field),
        )
    )

    is_tie = len(activations) == 2 and pre_mega_speeds[sorted_order[0]] == pre_mega_speeds[sorted_order[1]]
    orderings = [sorted_order, tuple(reversed(sorted_order))] if is_tie else [sorted_order]
    weight = 0.5 if is_tie else 1.0

    branches: list[WeightedMegaProjection] = []
    by_pair = {(side, slot): form for side, slot, form in activations}
    for order in orderings:
        projected = copy_battle_state(state)
        for side, slot in order:
            form = by_pair[(side, slot)]
            is_ours = side == our_side
            step = project_mega(
                projected, side, slot, form, species_meta=species_meta,
                speed_oracle=speed_oracle, calc_profile=calc_profile,
                is_ours=is_ours,
                spread_lookup=our_spreads if is_ours else None,
                opp_sets=opp_sets if not is_ours else None,
                book=book,
            )
            projected = step.projected_state
        branches.append(WeightedMegaProjection(projected_state=projected, weight=weight, activation_order=order))
    return branches
```

**Step 4 — verify:** `python -m pytest tests/i7b/test_i7b_projection.py -q`.

**Step 5 — commit:**
```powershell
git add src/showdown_bot/engine/mega_projection.py tests/i7b/
git commit -m "feat(champions-i7b-b): compose_mega_projection_branches (dual-Mega ties, side-aware)"
```

### Task 4 [REV.4] — three-phase scoring integration in `score_evaluated_variants`

**Rev. 3 corrects four confirmed defects in Rev. 2's single-pass design** (Codex review round 3, all independently re-verified against real source before this rewrite, not accepted on the reviewer's word alone):

1. **Branch-state/plan mismatch (finding 1).** Rev. 2 evaluated the STALE own-only-context `plan` (planned against `ctx.projected_state`, before any foe-Mega branch existed) against the branch's OWN `projected_state`, and hand-patched only the foe-mega slot's own action via `replace()` — leaving the foe's PARTNER's speed/move stale even though foe-Mega weather can change it too (weather affects every mon's effective speed, not just the Mega'd one), and `target_mon_for` read the pre-projection `state` rather than `branch.projected_state`.
2. **Batching claim didn't match the pseudocode (finding 2).** Rev. 2's own prose promised "flushed once per world"; the actual code nested `branch_model = DamageModel(...)` / `.enqueue(...)` / `oracle.flush()` inside the per-candidate (`rec`) loop, so the flush count scaled with candidates × responses × branches, not once per branch/world as claimed.
3. **Weighting inconsistency under `priors=None` (finding 3).** The no-mega path used `raw_w = r.weight if (priors is not None and r is not None) else 1.0`; the mega path used `r.weight` unconditionally. Under `priors=None` (this fixture's exact setup), no-mega responses collapsed to a flat `1.0` while mega responses kept their real click-rate-derived weight — the two paths didn't correspond to the same semantics for the SAME decision.
4. **Evidence API defects (finding 4).** No evidence was ever emitted for no-mega responses (the future smoke explicitly requires both a mega AND a no-mega twin per decision); `score_contribution = score * weight` was presented as if it were the response's real additive contribution to the final aggregate score, which is false under `GameMode.MUST_REACT` (`mean - λ*(mean-min)`, `battle/policy.py:69-76`) and `GameMode.NEUTRAL`'s weighted-variance operator (`mean - λ*variance`, `policy.py:78-90`) — both confirmed non-linear in the individual per-response scores by direct read; `world_index`/`world_weight`/`response_weight` were missing entirely, forcing evidence consumers (and this plan's own tests) to reconstruct them indirectly; `rec.variant.joint.joint_action_key()` does not exist (`JointAction` has no such method — the real accessor is the module-level `joint_action_key_v2(ja)` at `battle/candidate_identity.py:48`, confirmed by direct read); and changing the return type to a tuple would silently break the 8 real, existing call sites that do `records = score_evaluated_variants(...)` today (`battle/decision.py:733` plus 7 in `tests/i7a/test_i7a_decision.py`, confirmed via `grep`).

**Corrected design — three explicit phases per world, matching audit §Rev.2.7/§Rev.3.1's data flow with the batching and replanning now fully pinned down:**

- **Phase A — build & enqueue.** For each `(slot, ctx)`: generate `resps` via the existing Mega-aware `predict_responses` call. Record `required_classes` from eligibility and `retained_classes` from the actual returned responses; fail closed if `required_classes` is not a subset of `retained_classes`. Then, for each distinct `foe_mega_slot`, build branches once. For each branch: (a) replan every hero candidate against `branch.projected_state`; (b) regenerate the full opponent response set without recursive Mega expansion; (c) pair each original Mega hypothesis with its regenerated action plan by stable `.label`; and (d) enqueue the regenerated **actions** once. The pair deliberately preserves the original hypothesis's `response_id`, `foe_mega_slot`, and post-cap/click-rate `weight`.
- **Phase B — one shared flush per world.** Every no-Mega and branch model uses the same `DamageOracle`, and every enqueue occurs before evaluation. Therefore one `oracle.flush()` after all Phase-A enqueues resolves the complete world queue. Additional per-branch calls would be empty no-ops because the first flush clears `_pending`.
- **Phase C — evaluate weighted samples with full evidence.** For each `(slot, rec, response)` pair (no-mega AND foe-mega both), evaluate against the CORRECT already-built state/plan/actions/model from Phase A, append to `rec.score_vector`/`rec.score_weights`, and — if `opp_mega_evidence_sink is not None` — append one `ScoredResponseEvidence` per response (finding 4a) carrying RAW components only (finding 4b/4c): `world_index`, `world_weight`, `response_weight`, `branch_weight` (`1.0` for no-mega), `raw_score` — never a pre-multiplied "contribution", since no single per-response product is correct under both `MUST_REACT` and `NEUTRAL`'s non-linear operators; consumers multiply the components themselves according to whichever operator they need.

**Response identity across a re-generated `predict_responses` call:** `OppResponse.response_id` is `f"{label}|mega={none|0|1}"`. Match the original hypothesis to the branch-regenerated response by stable `.label`, but keep them as a pair. The regenerated response supplies only branch-correct `actions`; the original response remains authoritative for `response_id`, `foe_mega_slot`, and `weight`. Replacing those with the regenerated base response would erase `SHOWDOWN_OPP_MEGA_CLICK_RATE` and post-truncation renormalization. If a branch lacks an original label, raise `MissingBranchResponseError`.

**Weighting (finding 3), precisely:** when THIS call's `foe_mega_eligibility` is non-empty (the I7b path genuinely active for this decision), `raw_w = r.weight` unconditionally for every response, no-mega included — overriding the legacy `priors is not None` gate for this call only. When `foe_mega_eligibility` is `None`/empty (every existing I7a-only caller, including the byte-identical Reg-I test below), the EXISTING `raw_w = r.weight if (priors is not None and r is not None) else 1.0` gate is preserved exactly, unchanged — Reg-I stays byte-identical.

**Step 0 [REV.5] — extract a test-only builder; add a separate, coherent tie fixture.**
In `showdown_bot/tests/conftest.py`. `mega_decision_fixture`'s and `_mega_state()`'s
**default behavior stays unchanged** (both are shared with `tests/i7a/`): `_mega_state()`
gains one defaulted parameter whose default reproduces today's Incineroar opponent
exactly, and the construction body moves into a builder that both fixtures call. Fixture
shape `(req, kw)` is unchanged.

```python
def _mega_state(foe_a: "PokemonState | None" = None):
    """Default (foe_a=None) is byte-identical to the pre-Rev.5 board: p2.a Incineroar."""
    st = BattleState()
    st.sides["p1"]["a"] = PokemonState(
        species="Aerodactyl", base_species_id="aerodactyl", item="Aerodactylite",
        types=["Rock", "Flying"], hp=100, max_hp=100,
    )
    st.sides["p1"]["b"] = PokemonState(
        species="Whimsicott", base_species_id="whimsicott",
        types=["Grass", "Fairy"], hp=100, max_hp=100,
    )
    st.sides["p2"]["a"] = foe_a if foe_a is not None else PokemonState(
        species="Incineroar", base_species_id="incineroar",
        types=["Fire", "Dark"], hp=100, max_hp=100,
    )
    return st


def _build_mega_decision_kw(state):
    """Test-only builder. contexts/evaluated_variants are built FROM `state`, so a
    caller-supplied board is coherent from the start -- never a post-hoc
    kw["state"] swap after contexts already exist (which would leave every context's
    projected_state/plans/damage_model bound to the OTHER board)."""
    from showdown_bot.battle.actions import enumerate_my_actions
    from showdown_bot.battle.evaluate import EvalWeights
    from showdown_bot.battle.mega_scoring import build_own_mega_contexts
    from showdown_bot.battle.oracle import DamageOracle
    from showdown_bot.engine.belief.game_mode import GameMode
    from showdown_bot.engine.belief.hypotheses import SpeciesSpreads, SpreadBook, SpreadPreset
    from showdown_bot.engine.calc.client import SubprocessCalcBackend
    from showdown_bot.engine.calc_profile import calc_profile_from_config
    from showdown_bot.engine.format_config import load_format_config
    from showdown_bot.engine.speed import SpeedOracle
    from showdown_bot.engine.species_meta import species_meta_table

    cfg = load_format_config("gen9championsvgc2026regma")
    calc_profile = calc_profile_from_config(cfg)
    speed_oracle = SpeedOracle(stats_backend=SubprocessCalcBackend(), profile=calc_profile)
    spreads = SpeciesSpreads(
        offense=SpreadPreset(nature="Jolly", evs={"atk": 32, "spe": 32, "hp": 2}),
        defense=SpreadPreset(nature="Impish", evs={"hp": 32, "def": 32, "spd": 2}),
    )
    book = SpreadBook(default=spreads)
    req = _mega_req()
    oracle = DamageOracle()
    our_spreads = {"aerodactyl": spreads, "whimsicott": spreads, "incineroar": spreads}
    contexts, evaluated_variants = build_own_mega_contexts(
        req, state, our_side="p1", opp_side="p2", book=book, oracle=oracle,
        speed_oracle=speed_oracle, species_meta=species_meta_table(),
        our_spreads=our_spreads, opp_sets=None, calc_profile=calc_profile,
        my_actions=enumerate_my_actions(req),
    )
    kw = dict(
        state=state, book=book, our_side="p1", oracle=oracle, speed_oracle=speed_oracle,
        format_config=cfg, calc_profile=calc_profile,
        evaluated_variants=evaluated_variants, contexts=contexts, calc=oracle.client,
        dex=None, weights=EvalWeights(), mode=GameMode.NEUTRAL,
        our_spreads=our_spreads, opp_sets=None,
    )
    return req, kw


@pytest.fixture
def mega_decision_fixture():
    """Unchanged default board (p2.a Incineroar). NOT usable for foe-Mega scoring:
    its foe is not a Mega holder, so the real foe_mega_eligibility() returns {}."""
    return _build_mega_decision_kw(_mega_state())


@pytest.fixture
def mega_decision_tie_fixture():
    """[REV.5 correction 1] p2.a is a REAL Aerodactyl holding Aerodactylite with
    item_known=True, so the real foe_mega_eligibility() yields a coherent
    Aerodactyl-Mega hypothesis AND both pre-mega speeds tie -- the two branches at
    weight 0.5 that Task 4's weighting test requires.

    Verified against the real SpeedOracle + real SubprocessCalcBackend, not assumed:
      p1.a Aerodactyl (our_spreads, is_ours=True)  -> 200
      p2.a Aerodactyl (book.default, is_ours=False) -> 200   => tie, 2 branches @ 0.5
    (Rev. 4 used the Incineroar board here: 200 vs 123, one branch @ 1.0, so its own
    `assert tied_groups` could never pass -- see §Rev. 5.)"""
    foe = PokemonState(
        species="Aerodactyl", base_species_id="aerodactyl", item="Aerodactylite",
        item_known=True, types=["Rock", "Flying"], hp=100, max_hp=100,
    )
    return _build_mega_decision_kw(_mega_state(foe_a=foe))
```

Both fixtures intentionally leave the shared oracle unflushed: `build_own_mega_contexts`
only enqueues, and the scoring call under test owns the single world-level flush.

Add `test_mega_decision_fixture_exposes_real_scoring_inputs` to pin every new key plus
`len(evaluated_variants) > 1` and `contexts` non-empty before the I7b tests rely on them.
Add `test_mega_decision_fixture_default_board_is_unchanged` pinning that
`_mega_state()`'s default still yields `p2.a` Incineroar with no item — the guard that
this extraction did not silently alter the board `tests/i7a/` depends on.

**Step 1 — write failing tests**, new file `showdown_bot/tests/i7b/test_i7b_scoring.py`:

```python
"""I7b-B Task 4 (Rev. 5): three-phase foe-Mega scoring integration."""
from __future__ import annotations

import pytest

from showdown_bot.battle.candidate_identity import joint_action_key_v2
from showdown_bot.battle.mega_scoring import MegaScoreRecord, score_evaluated_variants

# [REV.5] `mega_form_for` is deliberately NOT imported here any more: every test in
# this file now derives its hypothesis through the real foe_mega_eligibility() via
# _real_eligibility(), so a hand-built MegaForm has no remaining call site (it would
# be an unused import, and re-introducing one would reopen the incoherent-hypothesis
# defect Rev. 5 closes).


def _real_eligibility(kw):
    """[REV.5] Derive eligibility through the REAL limited-view path, never by
    hand-injecting a MegaForm. Rev. 4 injected an Aerodactyl-Mega form onto an
    Incineroar -- a hypothesis foe_mega_eligibility() can never produce (it resolves
    species-bound via mega_form_for(mon.species, mon.item)) and which Task 2's Rev. 5
    coherence check now rejects outright."""
    from showdown_bot.battle.opponent import foe_mega_eligibility

    elig = foe_mega_eligibility(kw["state"], "p2", opp_sets=kw.get("opp_sets"))
    assert elig, "fixture must yield a real foe-Mega hypothesis for this test to mean anything"
    return elig


def _assert_pre_mega_speeds_tie(kw):
    """[REV.5] Explicit real-backend precondition for every test that asserts two
    0.5-weight branches. Rev. 4's defect was asserting a tie nobody ever computed
    (Aerodactyl 200 vs Incineroar 123); this makes the tie a checked fact, and makes
    a fixture/backend drift fail HERE with a readable message instead of surfacing as
    a confusing `assert tied_groups` failure downstream."""
    st, so = kw["state"], kw["speed_oracle"]
    own_mon, foe_mon = st.sides["p1"]["a"], st.sides["p2"]["a"]
    own = so.speed_for_species(
        species_name=own_mon.species, base_species_id=own_mon.base_species_id or own_mon.species,
        side="p1", mon=own_mon, field=st.field, our_spreads=kw["our_spreads"],
        opp_sets=None, book=kw["book"], is_ours=True,
    )
    foe = so.speed_for_species(
        species_name=foe_mon.species, base_species_id=foe_mon.base_species_id or foe_mon.species,
        side="p2", mon=foe_mon, field=st.field, our_spreads=None,
        opp_sets=kw.get("opp_sets"), book=kw["book"], is_ours=False,
    )
    assert own == foe, f"tie fixture must actually tie: p1.a={own} vs p2.a={foe}"


def _score(kw, req, *, eligibility=None, sink=None, mode=None):
    from showdown_bot.engine.species_meta import species_meta_table

    return score_evaluated_variants(
        kw["evaluated_variants"], kw["contexts"], req=req, state=kw["state"], book=kw["book"],
        our_side="p1", opp_side="p2", calc=kw["calc"], oracle=kw["oracle"],
        speed_oracle=kw["speed_oracle"], dex=kw["dex"], priors=None, weights=kw["weights"],
        mode=mode or kw["mode"], risk_lambda=0.5, rollout_horizon=0, our_spreads=kw.get("our_spreads"),
        opp_sets=None, calc_profile=kw["calc_profile"], accuracy_mode=False, accuracy_branch_cap=6,
        endgame=False, fast_board=False,
        foe_mega_eligibility=eligibility, species_meta=species_meta_table() if eligibility else None,
        opp_mega_evidence_sink=sink,
    )


def test_return_type_is_unchanged_records_only(mega_decision_fixture):
    """Finding 4e: the return type stays `list[MegaScoreRecord]` -- NOT a
    tuple -- so every existing real call site (`decision.py:733` and 7 in
    `tests/i7a/test_i7a_decision.py`, none of which unpack a tuple today)
    keeps working unmodified. Evidence is opt-in via `opp_mega_evidence_sink`."""
    req, kw = mega_decision_fixture
    records = _score(kw, req)
    assert isinstance(records, list)
    assert all(isinstance(r, MegaScoreRecord) for r in records)


def test_foe_mega_evidence_is_weighted_by_world_times_response_times_branch(mega_decision_tie_fixture):
    """T19/T26 weighting: sibling evidence rows for the SAME (candidate,
    response) tie must have equal, sub-1.0 branch_weight values summing to
    1.0 -- a regression that drops branch.weight from the branch-building or
    evaluation path would either collapse the tie to one branch (failing the
    `tied_groups` non-empty check) or leave both siblings at weight 1.0
    (failing the sum-to-1.0 check).

    [REV.5] Uses mega_decision_tie_fixture (real Aerodactyl foe, 200 vs 200), NOT
    the default Incineroar board (200 vs 123) whose single weight-1.0 branch made
    Rev. 4's `assert tied_groups` unsatisfiable. Real-backend integration test --
    Task 3's monkeypatched tie test covers branch ENUMERATION in isolation; this
    one must earn its tie from the real backend."""
    req, kw = mega_decision_tie_fixture
    _assert_pre_mega_speeds_tie(kw)  # REV.5: checked precondition, not an assumption
    eligibility = _real_eligibility(kw)
    evidence: list = []
    _score(kw, req, eligibility=eligibility, sink=evidence)

    foe_evidence = [e for e in evidence if e.foe_mega_slot is not None]
    assert foe_evidence
    by_response: dict[tuple[str, str], list] = {}
    for e in foe_evidence:
        by_response.setdefault((e.candidate_key, e.response_id), []).append(e)
    tied_groups = [g for g in by_response.values() if len(g) > 1]
    assert tied_groups  # this fixture's speed values must exercise a genuine tie
    for group in tied_groups:
        branch_weights = {round(e.branch_weight, 9) for e in group}
        assert len(branch_weights) == 1
        assert next(iter(branch_weights)) < 1.0
        assert sum(e.branch_weight for e in group) == pytest.approx(1.0)


def test_no_mega_responses_also_produce_evidence_rows(mega_decision_tie_fixture):
    """Finding 4a: the future smoke's evidence gate requires BOTH a no-mega
    and a mega twin for the same decision -- Rev. 2 only ever appended
    inside the foe-mega branch loop."""
    req, kw = mega_decision_tie_fixture
    eligibility = _real_eligibility(kw)
    evidence: list = []
    _score(kw, req, eligibility=eligibility, sink=evidence)
    assert any(e.foe_mega_slot is None for e in evidence)
    assert any(e.foe_mega_slot is not None for e in evidence)


def test_evidence_candidate_key_matches_joint_action_key_v2(mega_decision_tie_fixture):
    """Finding 4d: `candidate_key` must come from the real module-level
    `joint_action_key_v2`, not a nonexistent `.joint_action_key()` method."""
    req, kw = mega_decision_tie_fixture
    eligibility = _real_eligibility(kw)
    evidence: list = []
    records = _score(kw, req, eligibility=eligibility, sink=evidence)
    valid_keys = {joint_action_key_v2(r.variant.joint) for r in records}
    assert evidence
    assert all(e.candidate_key in valid_keys for e in evidence)


def test_evidence_carries_raw_unmultiplied_components(mega_decision_tie_fixture):
    """Finding 4b/4c: evidence exposes world_index/world_weight/response_weight
    as separate fields, and `raw_score` is the per-response detail score
    alone -- never pre-multiplied into a single "contribution", since
    aggregate_scores (policy.py:46) is non-linear (MUST_REACT/NEUTRAL) and no
    single per-response product is correct under both operators."""
    req, kw = mega_decision_tie_fixture
    eligibility = _real_eligibility(kw)
    evidence: list = []
    _score(kw, req, eligibility=eligibility, sink=evidence)
    assert evidence
    for e in evidence:
        assert isinstance(e.world_index, int)
        assert isinstance(e.world_weight, float)
        assert isinstance(e.response_weight, float)
        assert isinstance(e.raw_score, float)


def test_i7b_active_path_weights_no_mega_and_mega_responses_consistently(mega_decision_tie_fixture):
    """Finding 3: when foe_mega_eligibility is non-empty, EVERY response
    (no-mega included) must use its real r.weight -- not the legacy
    `1.0`-under-priors=None default, which would otherwise make no-mega and
    mega responses incomparable within the same decision."""
    req, kw = mega_decision_tie_fixture
    eligibility = _real_eligibility(kw)
    evidence: list = []
    _score(kw, req, eligibility=eligibility, sink=evidence)
    no_mega = [e for e in evidence if e.foe_mega_slot is None]
    assert no_mega
    assert any(e.response_weight != 1.0 for e in no_mega)


def test_must_react_min_is_weight_blind_which_is_why_zero_weight_samples_are_excluded():
    """[REV.7 / P1 rationale, pinned] The reason the two counterexamples below exist.

    aggregate_scores' MUST_REACT operator is `avg - lambda*(avg - min(scores))`,
    and that `min(scores)` is computed WITHOUT weights (policy.py). So a
    zero-weight sample cannot move the weighted mean, but DOES move the aggregate:

        [10]        w=[1]    -> 10.0
        [10, -100]  w=[1, 0] -> -56.0     (lambda 0.6: 10 - 0.6*(10 - -100))

    A zero-weight response is therefore NOT harmless, and must never reach
    score_vector/score_weights. NEUTRAL/AHEAD are unaffected (both weight their
    mean and variance), so this is MUST_REACT-specific. If policy.py ever starts
    weighting the min, this test fails and the exclusion rule can be revisited --
    that is exactly what it is here to tell you."""
    from showdown_bot.battle.policy import aggregate_scores
    from showdown_bot.engine.belief.game_mode import GameMode

    lone = aggregate_scores([10.0], GameMode.MUST_REACT, weights=[1.0])
    with_zero = aggregate_scores([10.0, -100.0], GameMode.MUST_REACT, weights=[1.0, 0.0])
    assert lone == pytest.approx(10.0)
    assert with_zero != pytest.approx(lone)  # <-- the whole point
    assert with_zero == pytest.approx(-56.0)
    # ...and the contrast: NEUTRAL genuinely ignores a zero-weight sample.
    assert aggregate_scores([10.0, -100.0], GameMode.NEUTRAL, weights=[1.0, 0.0], risk_lambda=0.5) \
        == pytest.approx(aggregate_scores([10.0], GameMode.NEUTRAL, weights=[1.0], risk_lambda=0.5))


def test_click_rate_zero_makes_the_foe_mega_hypothesis_completely_inert(
    mega_decision_tie_fixture, monkeypatch,
):
    """[REV.7 / P1 counterexample 1 of 2] At click rate 0.0 every foe-Mega twin
    carries weight 0, so the hypothesis must be COMPLETELY inert: no branch composed
    (no wasted calc), no evidence row, no score sample. I7b-A still emits the twin
    for identity/cap coverage -- that is upstream of this path and unchanged.

    RED before the fix: zero-weight mega rows are scored, and score_weights contains
    0.0 -- which under MUST_REACT's weight-blind min() silently moves the decision."""
    from showdown_bot.engine.belief.game_mode import GameMode

    monkeypatch.setenv("SHOWDOWN_OPP_MEGA_CLICK_RATE", "0")
    req, kw = mega_decision_tie_fixture
    eligibility = _real_eligibility(kw)
    evidence: list = []
    records = _score(kw, req, eligibility=eligibility, sink=evidence, mode=GameMode.MUST_REACT)

    assert not [e for e in evidence if e.foe_mega_slot is not None], (
        "click rate 0.0: zero-weight foe-Mega twins must not be enqueued, scored, or evidenced"
    )
    assert [e for e in evidence if e.foe_mega_slot is None], "the no-mega twins must still be scored"
    for r in records:
        assert r.score_weights
        assert all(w > 0 for w in r.score_weights), (
            f"zero-weight sample reached score_weights: {r.score_weights}"
        )


def test_click_rate_one_makes_the_no_mega_twin_completely_inert(
    mega_decision_tie_fixture, monkeypatch,
):
    """[REV.7 / P1 counterexample 2 of 2] Mirror image: at click rate 1.0 the no-mega
    twin carries weight 0 and must not be scored either -- same weight-blind-min
    reason.

    RED before the fix: zero-weight no-mega rows are scored, and score_weights
    contains 0.0."""
    from showdown_bot.engine.belief.game_mode import GameMode

    monkeypatch.setenv("SHOWDOWN_OPP_MEGA_CLICK_RATE", "1")
    req, kw = mega_decision_tie_fixture
    eligibility = _real_eligibility(kw)
    evidence: list = []
    records = _score(kw, req, eligibility=eligibility, sink=evidence, mode=GameMode.MUST_REACT)

    assert not [e for e in evidence if e.foe_mega_slot is None], (
        "click rate 1.0: zero-weight no-mega twins must not be enqueued, scored, or evidenced"
    )
    assert [e for e in evidence if e.foe_mega_slot is not None], "the mega twins must still be scored"
    for r in records:
        assert r.score_weights
        assert all(w > 0 for w in r.score_weights), (
            f"zero-weight sample reached score_weights: {r.score_weights}"
        )


def test_branch_replan_preserves_original_mega_identity_and_weight(
    mega_decision_tie_fixture, monkeypatch,
):
    """A branch replan may replace actions, never the original Mega hypothesis's
    identity or its click-rate/cap/renormalised weight -- the branch-regenerated
    base response must supply ONLY actions.

    [REV.7] Pinned at an explicit mid click rate so the Mega twin is genuinely
    scored. (Rev. 4-6 pinned this at rate 0.0 and asserted the twin was scored with
    weight 0.0; that is now forbidden -- a zero-weight sample moves MUST_REACT's
    weight-blind min(). The rate-0.0 case is covered by its own counterexample above,
    which asserts the twin is excluded outright.)"""
    monkeypatch.setenv("SHOWDOWN_OPP_MEGA_CLICK_RATE", "0.35")
    req, kw = mega_decision_tie_fixture
    eligibility = _real_eligibility(kw)
    evidence: list = []
    _score(kw, req, eligibility=eligibility, sink=evidence)
    mega_rows = [e for e in evidence if e.foe_mega_slot == 0]
    assert mega_rows
    assert all(e.response_id.endswith("|mega=0") for e in mega_rows)
    # The click-rate-derived weight survived the replan: neither 0 (dropped) nor
    # 1.0 (replaced by the regenerated base response's default weight).
    assert all(0.0 < e.response_weight < 1.0 for e in mega_rows)


def test_legacy_path_leaves_diagnostic_contexts_structurally_empty(mega_decision_fixture):
    """[REV.7] Parity is STRUCTURAL, not just numeric. Task 6's depth-2 binding is
    specified as `rec.diagnostic_contexts[i] if rec.diagnostic_contexts else
    ctx_by_slot[rec.variant.own_mega_slot]` -- i.e. an EMPTY list means "pre-I7b-B,
    use the legacy blanket context". Populating the field on the legacy path would
    make that fallback dead code and quietly falsify the byte-identity claim, even
    though the bound context happens to be numerically the same one."""
    req, kw = mega_decision_fixture
    records = _score(kw, req)  # no eligibility => legacy path
    assert records
    assert all(r.diagnostic_contexts == [] for r in records)


def test_active_path_binds_one_diagnostic_context_per_diagnostic_index(mega_decision_tie_fixture):
    """[REV.7] ...and when I7b IS active the parallel-array contract must hold, so
    Task 6 can index diagnostic_contexts[i] directly against diagnostic_details[i]. A
    record's top-M may span a no-mega response AND foe-mega branch responses, which is
    exactly why the per-index binding exists."""
    req, kw = mega_decision_tie_fixture
    eligibility = _real_eligibility(kw)
    records = _score(kw, req, eligibility=eligibility)
    assert records
    for r in records:
        assert r.diagnostic_contexts
        assert len(r.diagnostic_contexts) == len(r.diagnostic_details)
        assert len(r.diagnostic_contexts) == len(r.diagnostic_weights)
    # at least one record must genuinely span both kinds, or the per-index binding
    # would be untested in practice
    assert any(
        {c.foe_mega_slot is None for c in r.diagnostic_contexts} == {True, False}
        for r in records
    ), "no record's diagnostics span both a no-mega and a foe-mega branch context"


def test_scoring_evidence_proves_required_classes_were_retained(mega_decision_tie_fixture):
    req, kw = mega_decision_tie_fixture
    eligibility = _real_eligibility(kw)
    evidence: list = []
    _score(kw, req, eligibility=eligibility, sink=evidence)
    assert evidence
    assert all(set(e.required_classes) <= set(e.retained_classes) for e in evidence)
    assert all(e.required_classes == ("0", "none") for e in evidence)


def test_no_eligibility_is_byte_identical_to_pre_i7b_scoring(mega_decision_fixture):
    """Reg-I / omitted-kwarg safety net: calling with the two new
    keyword-only parameters left at their defaults must be numerically
    identical to calling with them passed explicitly as empty/None, and must
    use the UNCHANGED legacy weighting gate (not finding 3's I7b-active
    override)."""
    req, kw = mega_decision_fixture
    records_default = _score(kw, req)
    records_explicit = _score(kw, req, eligibility=None)
    assert len(records_default) == len(records_explicit)
    for a, b in zip(records_default, records_explicit):
        assert a.score_vector == pytest.approx(b.score_vector)
        assert a.score_weights == pytest.approx(b.score_weights)


def test_flush_count_is_bounded_independent_of_candidate_count(mega_decision_tie_fixture, monkeypatch):
    """Every model shares one oracle and all enqueues precede Phase B, so the
    complete world's pending queue is resolved by exactly one flush."""
    req, kw = mega_decision_tie_fixture
    eligibility = _real_eligibility(kw)
    call_count = {"n": 0}
    real_flush = kw["oracle"].flush

    def counting_flush():
        call_count["n"] += 1
        return real_flush()

    monkeypatch.setattr(kw["oracle"], "flush", counting_flush)
    records = _score(kw, req, eligibility=eligibility)
    assert len(records) >= 2  # this fixture must score more than one candidate
    assert call_count["n"] == 1
```

**Step 2 — confirm RED:** `python -m pytest tests/i7b/test_i7b_scoring.py -q` → `TypeError` (`score_evaluated_variants` doesn't accept `foe_mega_eligibility`/`species_meta`/`opp_mega_evidence_sink` yet; `ScoredResponseEvidence` doesn't exist).

**Step 3 — implement.** First, the evidence DTO and a new fail-closed error, near `MegaScoreRecord` in `mega_scoring.py`:

```python
@dataclass(frozen=True)
class ScoredResponseEvidence:
    """One (candidate, opponent response, Mega branch) scored contribution --
    NOT persisted to decision-trace-v3 (battle_id/decision_index co-location
    does not prove which candidate was scored against which response). Raw
    components only (finding 4b/4c) -- NOT a pre-multiplied "contribution":
    aggregate_scores (policy.py:46) is non-linear under MUST_REACT
    (`mean - λ*(mean-min)`) and NEUTRAL (`mean - λ*variance`), so no single
    per-response product is the correct "contribution" under both operators;
    consumers multiply these components themselves per their own operator.
    Built inline during scoring; consumed directly by eval/opp_mega_trace.py
    (I7b-C), never reconstructed after the fact."""
    candidate_key: str
    response_id: str
    foe_mega_slot: int | None
    branch_index: int
    branch_weight: float
    world_index: int
    world_weight: float
    response_weight: float
    raw_score: float
    required_classes: tuple[str, ...]
    retained_classes: tuple[str, ...]


@dataclass(frozen=True)
class _BranchResponsePair:
    """Original hypothesis metadata plus actions replanned on the branch.

    `original` owns response_id/foe_mega_slot/weight after I7b-A's click-rate,
    cap, and renormalization pipeline. `replanned` owns only the actions that
    see the branch's projected state, weather, species, and speeds.
    """
    original: OppResponse
    replanned: OppResponse


class MissingBranchResponseError(ValueError):
    """A foe-Mega branch's re-generated predict_responses() call did not
    reproduce one of the original top-M response labels (e.g.
    revealed_support becoming newly available post-Mega). Fail closed rather
    than silently drop or mismatch a response."""
```

**Also add one new field to the existing `MegaScoreRecord` dataclass** (`mega_scoring.py:242-259`), used by Task 6's depth-2 threading below — a default is given so every existing construction call site (which never mentions it) is unaffected:

(needs `field` added to `mega_scoring.py:4`'s existing `from dataclasses import dataclass` — confirmed only `dataclass` is imported there today, not `field`):

```python
    diagnostic_contexts: list["MegaEvaluationContext"] = field(default_factory=list)
    # World-0-only, same length/cadence as diagnostic_details/diagnostic_weights
    # (never populated for pooled-world indices beyond world 0): records WHICH
    # MegaEvaluationContext each diagnostic index's detail/outcome was actually
    # computed against -- the pre-existing own-mega-only ctx for a no-mega
    # index, or that specific foe-mega branch's own branch_ctx for a foe-mega
    # index. Task 6 depends on this to bind depth-2 to the CORRECT context per
    # index, since a record's own top-M diagnostic indices may span both a
    # no-mega response and one or more foe-mega branch responses.
```

Modify `score_evaluated_variants`'s signature (`mega_scoring.py:278-303`) — **return type unchanged** (`-> list[MegaScoreRecord]`, finding 4e) — adding three new keyword-only parameters:

```python
def score_evaluated_variants(
    evaluated_variants: list[ScoredMegaVariant],
    contexts: list[MegaEvaluationContext],
    *,
    req: BattleRequest,
    state: BattleState,
    book: SpreadBook,
    our_side: str,
    opp_side: str,
    calc: CalcClient,
    oracle: DamageOracle,
    speed_oracle: SpeedOracle | None,
    dex: SpeciesDex | None,
    priors=None,
    weights: EvalWeights,
    mode: GameMode,
    risk_lambda: float,
    rollout_horizon: int,
    our_spreads: dict | None,
    opp_sets: dict | None,
    calc_profile: CalcProfile,
    accuracy_mode: bool,
    accuracy_branch_cap: int,
    endgame: bool,
    fast_board: bool,
    foe_mega_eligibility: dict[str, MegaForm] | None = None,
    species_meta: dict[str, SpeciesFormMeta] | None = None,
    opp_mega_evidence_sink: list[ScoredResponseEvidence] | None = None,
) -> list[MegaScoreRecord]:
```

Inside the existing per-world loop (`mega_scoring.py:374-...`), replace the body with the three explicit phases:

```python
    from showdown_bot.battle.candidate_identity import joint_action_key_v2
    from showdown_bot.battle.opponent import OppResponse, OpponentResponseCapError, opp_mega_click_rate
    from showdown_bot.engine.mega_projection import compose_mega_projection_branches, UnsupportedMegaAbilityError
    from showdown_bot.engine.speed import MissingMegaSpreadError

    _click_rate = opp_mega_click_rate() if foe_mega_eligibility else None
    _i7b_active = bool(foe_mega_eligibility)

    for world_idx, (world_sets, world_w) in enumerate(worlds):
        merged_sets = {**(opp_sets or {}), **world_sets}
        world_resps_by_slot: dict[int | None, list[OppResponse]] = {}
        world_model_by_slot: dict[int | None, DamageModel] = {}
        world_no_mega_resps_by_slot: dict[int | None, list[OppResponse]] = {}
        world_coverage_by_slot: dict[int | None, tuple[tuple[str, ...], tuple[str, ...]]] = {}

        # --- Phase A, part 1: existing no-mega responses/model (byte-identical) ---
        for slot, ctx in ctx_by_slot.items():
            resps = predict_responses(
                ctx.projected_state, our_side, opp_side, speed_oracle=speed_oracle,
                book=book, dex=dex, field=ctx.field, priors=priors,
                threatened_slots=threatened, opp_sets=merged_sets,
                foe_mega_eligibility=foe_mega_eligibility, opp_mega_click_rate=_click_rate,
            )
            model = DamageModel(
                ctx.projected_state, our_side, opp_side, book=book, oracle=oracle,
                field=ctx.field, our_spreads=our_spreads, opp_sets=merged_sets,
                calc_profile=calc_profile,
            )
            # [REV.7 / P1] A zero-weight response cannot move a weighted mean, but
            # aggregate_scores' MUST_REACT operator takes `min(scores)` WITHOUT
            # weights (policy.py) -- so a weight-0 sample DOES move the aggregate
            # ([10] w=[1] -> 10.0, but [10,-100] w=[1,0] -> -56.0). It must never be
            # enqueued, evaluated, or appended to score_vector. Only on the I7b-active
            # path: the legacy path's weights are untouched, so its behavior stays
            # byte-identical. I7b-A still EMITS the zero-weight twins upstream for
            # identity/cap coverage -- `resps` (not this filtered list) feeds
            # retained_classes below, so cap discipline is unaffected.
            no_mega_resps = [
                r for r in resps
                if r.foe_mega_slot is None and (not _i7b_active or r.weight > 0)
            ]
            required_classes = tuple(sorted(
                {"none"} | {str(0 if s == "a" else 1) for s in foe_mega_eligibility}
            )) if _i7b_active else ("none",)
            retained_classes = tuple(sorted({
                "none" if r.foe_mega_slot is None else str(r.foe_mega_slot)
                for r in resps
            }))
            if _i7b_active and not set(required_classes) <= set(retained_classes):
                raise OpponentResponseCapError(
                    f"required opponent response classes {required_classes} "
                    f"not retained by predict_responses: {retained_classes}"
                )
            model.enqueue(list(ctx.plans.values()) + [r.actions for r in no_mega_resps])
            world_resps_by_slot[slot] = resps
            world_model_by_slot[slot] = model
            world_no_mega_resps_by_slot[slot] = no_mega_resps
            world_coverage_by_slot[slot] = (required_classes, retained_classes)

        # --- Phase A, part 2: every foe-Mega branch, built ONCE per
        # (slot, foe_mega_slot, branch_idx), shared across every candidate ---
        branch_bundles: dict[tuple, dict] = {}
        for slot, ctx in ctx_by_slot.items():
            resps = world_resps_by_slot[slot]
            # [REV.7] sorted(), not raw set iteration: evidence rows and score_vector
            # entries are appended in this order, so an unordered iteration would make
            # both non-reproducible. [P1] weight > 0 filter: a zero-weight Mega class is
            # inert (see the no_mega filter above), so composing its branches would
            # only burn calc latency for samples that must not be scored anyway.
            foe_mega_slots = sorted({
                r.foe_mega_slot for r in resps
                if r.foe_mega_slot is not None and r.weight > 0
            })
            for foe_mega_slot in foe_mega_slots:
                own_form = None
                own_slot_key = "a" if slot == 0 else "b" if slot is not None else None
                if slot is not None:
                    own_mon = state.sides[our_side][own_slot_key]
                    own_form = mega_form_for(own_mon.species, own_mon.item) if own_mon.item else None
                activations = []
                if own_form is not None:
                    activations.append((our_side, own_slot_key, own_form))
                foe_slot_key = "a" if foe_mega_slot == 0 else "b"
                activations.append((opp_side, foe_slot_key, foe_mega_eligibility[foe_slot_key]))
                try:
                    branches = compose_mega_projection_branches(
                        state, activations, our_side=our_side, speed_oracle=speed_oracle,
                        our_spreads=our_spreads, opp_sets=merged_sets, book=book,
                        species_meta=species_meta, calc_profile=calc_profile,
                    )
                except (UnsupportedMegaAbilityError, MissingMegaSpreadError):
                    branches = []  # fail-closed: exclude, never crash the whole score

                for branch_idx, branch in enumerate(branches):
                    # [REV.6] PokemonState has NO effective_speed attribute -- the
                    # Rev.4/5 access here raised AttributeError at runtime. Re-derive
                    # from the COMPLETE, FINAL branch state via the central resolver.
                    own_override = None
                    if ctx.own_mega_slot is not None:
                        own_slot_letter = "a" if ctx.own_mega_slot == 0 else "b"
                        own_projected = branch.projected_state.sides[our_side][own_slot_letter]
                        own_override = {
                            ctx.own_mega_slot: speed_oracle.speed_for_species(
                                species_name=own_projected.species,
                                base_species_id=own_projected.base_species_id or own_projected.species,
                                side=our_side,
                                mon=own_projected,
                                field=branch.projected_state.field,
                                our_spreads=our_spreads,
                                opp_sets=None,
                                book=book,
                                is_ours=True,
                            )
                        }
                    replanned_plans = {
                        joint: _plan_my_actions(
                            req, joint, state=branch.projected_state, our_side=our_side,
                            opp_side=opp_side, speed_oracle=speed_oracle,
                            planned_speed_overrides_by_slot=own_override,
                        )
                        for joint in ctx.plans
                    }
                    branch_resps = predict_responses(
                        branch.projected_state, our_side, opp_side, speed_oracle=speed_oracle,
                        book=book, dex=dex, field=branch.projected_state.field, priors=priors,
                        threatened_slots=threatened, opp_sets=merged_sets,
                    )
                    branch_resps_by_label = {r.label: r for r in branch_resps}
                    # [REV.7 / P1] weight > 0: same exclusion rule as the no-mega path,
                    # so a _BranchResponsePair only ever exists for a response that will
                    # actually be scored.
                    matching_original = [
                        r for r in resps
                        if r.foe_mega_slot == foe_mega_slot and r.weight > 0
                    ]
                    for r in matching_original:
                        if r.label not in branch_resps_by_label:
                            raise MissingBranchResponseError(
                                f"branch-regenerated responses missing label {r.label!r}"
                            )
                    branch_model = DamageModel(
                        branch.projected_state, our_side, opp_side, book=book, oracle=oracle,
                        field=branch.projected_state.field, our_spreads=our_spreads,
                        opp_sets=merged_sets, calc_profile=calc_profile,
                    )
                    response_pairs = [
                        _BranchResponsePair(
                            original=original,
                            replanned=branch_resps_by_label[original.label],
                        )
                        for original in matching_original
                    ]
                    branch_model.enqueue(
                        list(replanned_plans.values())
                        + [pair.replanned.actions for pair in response_pairs]
                    )
                    # Task 6: a real MegaEvaluationContext bound to THIS branch, so
                    # depth-2's existing depth2_value_for_mega_context can be reused
                    # completely unmodified -- never a different branch's or the
                    # base own-mega-only context's projected_state/oracle.
                    branch_ctx = MegaEvaluationContext(
                        context_id=f"foe_mega:{foe_mega_slot}:{branch_idx}",
                        projected_state=branch.projected_state,
                        own_mega_slot=ctx.own_mega_slot, foe_mega_slot=foe_mega_slot,
                        branch_weight=branch.weight, activation_order=branch.activation_order,
                        field=branch.projected_state.field, plans=replanned_plans,
                        damage_model=branch_model,
                    )
                    branch_bundles[(slot, foe_mega_slot, branch_idx)] = {
                        "branch": branch, "model": branch_model,
                        "replanned_plans": replanned_plans,
                        "response_pairs": response_pairs,
                        "branch_ctx": branch_ctx,
                    }

        # --- Phase B: one shared flush for every enqueue in this world ---
        oracle.flush()

        # --- Phase C: evaluate weighted samples with full evidence ---
        for slot, ctx in ctx_by_slot.items():
            model = world_model_by_slot[slot]
            no_mega = world_no_mega_resps_by_slot[slot]
            if _i7b_active:
                # [REV.7] NO [None] fallback on the active path: at click rate 1.0 the
                # no-mega twin is zero-weight and excluded above, and this record's
                # samples come from the foe-Mega branches below. Falling back to [None]
                # here would inject a phantom no-opponent-action line at weight 1.0 --
                # the same zero-weight distortion this filter exists to prevent, in
                # reverse.
                targets = no_mega
            else:
                targets = no_mega if no_mega else [None]
            for rec in records_by_slot.get(slot, []):
                plan = ctx.plans[rec.variant.joint]
                candidate_key = joint_action_key_v2(rec.variant.joint)
                required_classes, retained_classes = world_coverage_by_slot[slot]

                for r in targets:
                    opp_actions = r.actions if r is not None else []
                    detail = _evaluate_line_details(
                        ctx.projected_state, plan, opp_actions, model.damage_fn,
                        our_side=our_side, weights=weights, field=ctx.field,
                        rollout_horizon=rollout_horizon, endgame=endgame,
                        fast_board=fast_board, accuracy_mode=accuracy_mode,
                        accuracy_branch_cap=accuracy_branch_cap,
                    )
                    if _i7b_active:
                        raw_w = r.weight if r is not None else 1.0  # finding 3: consistent under the active path
                    else:
                        raw_w = r.weight if (priors is not None and r is not None) else 1.0  # legacy, unchanged
                    rec.score_vector.append(detail.score)
                    rec.score_weights.append(world_w * raw_w)
                    if world_idx == 0:
                        rec.diagnostic_details.append(detail)
                        rec.diagnostic_weights.append(raw_w)
                        if _i7b_active:
                            # [REV.7] Only on the active path. Task 6's depth-2 binding
                            # treats an EMPTY diagnostic_contexts as "pre-I7b-B, fall back
                            # to ctx_by_slot[own_mega_slot]"; populating it here on the
                            # legacy path would make that fallback dead and break the
                            # structural (not just numeric) parity claim.
                            rec.diagnostic_contexts.append(ctx)
                    if opp_mega_evidence_sink is not None:
                        opp_mega_evidence_sink.append(ScoredResponseEvidence(
                            candidate_key=candidate_key,
                            response_id=(r.response_id if r is not None else "none"),
                            foe_mega_slot=None, branch_index=0, branch_weight=1.0,
                            world_index=world_idx, world_weight=world_w,
                            response_weight=raw_w, raw_score=detail.score,
                            required_classes=required_classes,
                            retained_classes=retained_classes,
                        ))

                for (b_slot, foe_mega_slot, branch_idx), bundle in branch_bundles.items():
                    if b_slot != slot:
                        continue
                    replanned_plan = bundle["replanned_plans"][rec.variant.joint]
                    branch = bundle["branch"]
                    branch_model = bundle["model"]
                    for pair in bundle["response_pairs"]:
                        original = pair.original
                        replanned = pair.replanned
                        detail = _evaluate_line_details(
                            branch.projected_state, replanned_plan, replanned.actions, branch_model.damage_fn,
                            our_side=our_side, weights=weights, field=branch.projected_state.field,
                            rollout_horizon=rollout_horizon, endgame=endgame, fast_board=fast_board,
                            accuracy_mode=accuracy_mode, accuracy_branch_cap=accuracy_branch_cap,
                        )
                        raw_w = original.weight
                        rec.score_vector.append(detail.score)
                        rec.score_weights.append(world_w * raw_w * branch.weight)
                        if world_idx == 0:
                            rec.diagnostic_details.append(detail)
                            rec.diagnostic_weights.append(raw_w * branch.weight)
                            rec.diagnostic_contexts.append(bundle["branch_ctx"])  # Task 6
                        if opp_mega_evidence_sink is not None:
                            opp_mega_evidence_sink.append(ScoredResponseEvidence(
                                candidate_key=candidate_key, response_id=original.response_id,
                                foe_mega_slot=original.foe_mega_slot, branch_index=branch_idx,
                                branch_weight=branch.weight, world_index=world_idx,
                                world_weight=world_w, response_weight=raw_w,
                                raw_score=detail.score,
                                required_classes=required_classes,
                                retained_classes=retained_classes,
                            ))
```

and the function's final line stays `return records` (finding 4e — no tuple, no behavior change for any caller that doesn't pass `opp_mega_evidence_sink`).

**Re-verify before marking GREEN:**
- `_plan_my_actions`'s real keyword-argument name for the post-Mega speed override (`planned_speed_overrides_by_slot`) and its exact shape (`dict[int, float]` keyed by own-mega slot INDEX, per `_mega_context`'s existing usage, `mega_scoring.py:127-133`) — confirmed by direct read this Rev.; re-check it has not drifted before wiring.
- `joint_action_key_v2`'s real parameter type (`JointAction`) matches `rec.variant.joint`'s type exactly (confirmed: `ScoredMegaVariant.joint: JointAction`, `battle/mega_variants.py`).
- All no-Mega and branch models share the same `DamageOracle`. Confirm every enqueue occurs before the single Phase-B `oracle.flush()` and pin `call_count == 1` per world; do not add empty per-branch flush calls after the shared pending queue has already been cleared.
- `predict_responses`'s second (branch-scoped) call must NOT itself recurse into foe-Mega expansion (omit `foe_mega_eligibility`/`opp_mega_click_rate` from that call, as written above) — the branch's OWN foe slot has already spent its Mega in `branch.projected_state.side_mega_spent`, so a real re-check would naturally return no further eligibility there, but omitting the kwargs entirely is clearer and cheaper.

**Step 4 — update `decision.py::_choose_best_mega`'s call site** (return type is UNCHANGED, so this is an additive kwarg only, no tuple-unpack, no restructuring of the surrounding function):

```python
    from showdown_bot.battle.opponent import foe_mega_eligibility as _compute_foe_eligibility

    _foe_eligibility = (
        _compute_foe_eligibility(state, opp_side, opp_sets=opp_sets)
        if format_config is not None and format_config.mega else {}
    )
    records = mega_scoring.score_evaluated_variants(
        evaluated_variants, contexts, req=req, state=state, book=book, our_side=our_side,
        opp_side=opp_side, calc=calc, oracle=oracle, speed_oracle=speed_oracle, dex=dex,
        priors=priors, weights=weights, mode=mode, risk_lambda=risk_lambda,
        rollout_horizon=rollout_horizon, our_spreads=our_spreads, opp_sets=opp_sets,
        calc_profile=calc_profile, accuracy_mode=accuracy_mode, accuracy_branch_cap=accuracy_branch_cap,
        endgame=endgame, fast_board=fast_board, foe_mega_eligibility=_foe_eligibility,
        species_meta=species_meta_table(), opp_mega_evidence_sink=opp_mega_evidence_sink,
    )
```

`opp_mega_evidence_sink` here is `_choose_best_mega`'s OWN new keyword-only parameter (default `None`), threaded in from its caller — see I7b-C Task 2 below for the full call chain up to `gauntlet.py` (mirrors the real, existing `trace: DecisionTrace | None` threading pattern already confirmed at `decision.py:412,667,812,1244,1298,1393`, not a new/invented plumbing shape).

**`battle/baselines.py` is NOT modified in this task** (`max_damage` never models opponent responses and is out of I7b's scope — confirmed by direct read of its docstrings, unchanged from Rev. 2).

**Step 5 — verify:**
```powershell
python -m pytest tests/i7b/test_i7b_scoring.py -q
python -m pytest tests/i7a/ -q
```
Expected: all new Task 4 tests green; every existing `tests/i7a/test_i7a_decision.py` call site (unmodified, still calling `score_evaluated_variants` without the new kwargs) stays green untouched.

**Step 6 — commit:**
```powershell
git add src/showdown_bot/battle/mega_scoring.py src/showdown_bot/battle/decision.py tests/i7b/
git commit -m "feat(champions-i7b-b): three-phase foe-Mega scoring integration (findings 1-4)"
```

### Task 5: fail-closed ability gate for a hypothesized foe Mega form

**[REV.5 correction 3 — consequence of correction 2, see §Rev. 5.]** Rev. 4's version
injected a `Scovillain-Mega` form onto the fixture's *non-Scovillain* foe. Verified
against real metadata, that form is **not** synthetic: `scovillainmega` is a real entry
in `species_meta`, its `ability_slot0` is `'Spicy Spray'`, and it is the **only** member
of `FAIL_CLOSED_ABILITIES` in the whole dex — so Rev. 4's test did work *before* Task 2
gained its coherence check. It cannot survive that check: `aerodactyl`/`incineroar` ≠
`scovillain` raises `MegaProjectionSpeciesMismatchError` **before** the ability gate is
ever reached, and Task 4 deliberately does not catch that error — so the test would
crash instead of proving exclusion, and would no longer exercise the ability gate at all.

The foe must therefore genuinely **be** a Scovillain, with eligibility derived through
the real path. Pre-verified against the real backend:
`mega_form_for("Scovillain", "Scovillainite")` returns the real form, the coherence check
passes (`scovillain == scovillain`), and
`foe_mega_eligibility(state, "p2", opp_sets=None)` yields
`{'a': MegaForm(base_species_id='scovillain', form_species_id='scovillainmega', ...)}`.

**Step 0 — add the fixture** to `tests/conftest.py`, alongside `mega_decision_tie_fixture`
(same builder, different foe — no third construction path):

```python
@pytest.fixture
def mega_decision_unsupported_ability_fixture():
    """[REV.5] p2.a is a REAL Scovillain holding Scovillainite, so the coherence
    check passes and the FAIL_CLOSED_ABILITIES gate ('Spicy Spray', the dex's only
    fail-closed mega ability) is what actually fires. No speed tie is needed or
    asserted here -- this test is about exclusion, not branch weighting."""
    foe = PokemonState(
        species="Scovillain", base_species_id="scovillain", item="Scovillainite",
        item_known=True, types=["Grass", "Fire"], hp=100, max_hp=100,
    )
    return _build_mega_decision_kw(_mega_state(foe_a=foe))
```

**Step 1 — write failing test**, append to `test_i7b_scoring.py`:

```python
def test_foe_mega_with_unsupported_ability_is_excluded_not_crashed(mega_decision_unsupported_ability_fixture):
    """A foe eligibility entry resolving to an unsupported-ability form
    (Scovillain-Mega / 'Spicy Spray') must be silently excluded from
    evidence/scoring via the SAME UnsupportedMegaAbilityError/FAIL_CLOSED_ABILITIES
    gate I7a already uses -- never a new exception type, never a crash.

    [REV.5] The foe really IS a Scovillain and eligibility comes from the real
    foe_mega_eligibility(), so Task 2's coherence check passes and the ability gate
    is the thing under test. Rev. 4 injected the form onto a mismatched species,
    which post-correction-2 would raise MegaProjectionSpeciesMismatchError first."""
    req, kw = mega_decision_unsupported_ability_fixture
    eligibility = _real_eligibility(kw)
    assert eligibility["a"].form_species_id == "scovillainmega"  # gate's real target

    evidence: list = []
    _score(kw, req, eligibility=eligibility, sink=evidence)
    # no scored contribution for slot 0's (Scovillain) mega -- checked via the
    # real foe_mega_slot field, not by parsing response_id's "|mega=" suffix
    assert all(e.foe_mega_slot != 0 for e in evidence)
    assert evidence  # the no-mega rows must still be scored: exclusion, not wipe-out
```

This is already satisfied structurally by Task 4's `try/except (UnsupportedMegaAbilityError, MissingMegaSpreadError): branches = []` — no additional production code should be needed; this task exists to **prove** it, not to write new logic. If it fails, the gap is in Task 4's implementation, not a new mechanism.

**Step 2-5:** confirm RED before Task 4's `try/except` exists (delete it locally to prove the test catches its absence), confirm GREEN with it in place, verify (`python -m pytest tests/i7b/ -q`), commit:
```powershell
git add tests/i7b/test_i7b_scoring.py
git commit -m "test(champions-i7b-b): prove fail-closed ability gate covers a hypothesized foe Mega form"
```

### Task 6 [REV.4 binding — no `search.py` changes at all]: depth-2 threading for foe-Mega branches

**`depth2_value_for_mega_context`'s real signature (`search.py:201-232`, confirmed by direct read, not the audit's earlier summary):**

```python
def depth2_value_for_mega_context(
    ctx: "MegaEvaluationContext",
    outcome: TurnOutcome,
    *,
    our_side: str,
    mode: GameMode,
    risk_lambda: float,
    top_m: int,
    book: SpreadBook | None,
    predict_kwargs: dict | None = None,
    model_kwargs: dict | None = None,
    eval_kwargs: dict | None = None,
) -> float:
```

It is ALWAYS bound to `ctx.projected_state` and `ctx.damage_model.oracle` (its own docstring's binding rule) and takes any `MegaEvaluationContext` — own-Mega-only or otherwise. **The cleanest fix (matching the review's own suggestion) needs zero changes to `search.py`:** Task 4 already builds a real `branch_ctx: MegaEvaluationContext` per `(slot, foe_mega_slot, branch_idx)` bundle (see Task 4's addendum above) and records, per diagnostic index, which context that index actually used (`rec.diagnostic_contexts`, new field). This task only has to fix the EXISTING depth-2 wrap block's own bug: it currently does `ctx = ctx_by_slot[rec.variant.own_mega_slot]` **once per record**, applying that SAME own-only context to every one of the record's top-M diagnostic indices — but with Task 4's foe-Mega branches now interleaved into the same `score_vector`/`diagnostic_details` arrays, a record's own top-M indices may legitimately include one or more foe-Mega branch responses, which must be bound to THEIR OWN `branch_ctx`, not the record's own-only `ctx`.

**Step 1 — write failing test**, append to `test_i7b_scoring.py`:

```python
def test_depth2_for_foe_mega_branch_uses_that_branchs_own_projected_state(mega_decision_tie_fixture, monkeypatch):
    """Depth-2 refinement of a foe-mega-tagged top-M response must be bound to
    THAT response's own composed branch's MegaEvaluationContext (never a
    different branch's or the record's own-only ctx_by_slot entry) -- proven
    by spying on depth2_value_for_mega_context's own ctx argument, the real
    function, not a fake."""
    import showdown_bot.battle.mega_scoring as mega_scoring_mod
    from showdown_bot.engine.species_meta import species_meta_table

    req, kw = mega_decision_tie_fixture
    _assert_pre_mega_speeds_tie(kw)
    eligibility = _real_eligibility(kw)
    monkeypatch.setenv("SHOWDOWN_SEARCH_DEPTH", "2")
    monkeypatch.setenv("SHOWDOWN_WORLD_SAMPLES", "1")

    seen_ctxs: list = []
    real_fn = mega_scoring_mod.depth2_value_for_mega_context

    def spy(ctx, outcome, **kwargs):
        seen_ctxs.append(ctx)
        return real_fn(ctx, outcome, **kwargs)

    monkeypatch.setattr(mega_scoring_mod, "depth2_value_for_mega_context", spy)

    records = score_evaluated_variants(
        kw["evaluated_variants"], kw["contexts"], req=req, state=kw["state"], book=kw["book"],
        our_side="p1", opp_side="p2", calc=kw["calc"], oracle=kw["oracle"],
        speed_oracle=kw["speed_oracle"], dex=kw["dex"], priors=None, weights=kw["weights"],
        mode=kw["mode"], risk_lambda=0.5, rollout_horizon=0, our_spreads=kw.get("our_spreads"),
        opp_sets=None, calc_profile=kw["calc_profile"], accuracy_mode=False, accuracy_branch_cap=6,
        endgame=False, fast_board=False, foe_mega_eligibility=eligibility,
        species_meta=species_meta_table(),
    )
    assert seen_ctxs  # depth-2 gate must actually have fired for this fixture
    foe_mega_ctxs = [c for c in seen_ctxs if c.foe_mega_slot is not None]
    assert foe_mega_ctxs  # at least one foe-mega branch index must have been in a record's top-M
    for c in foe_mega_ctxs:
        assert c.foe_mega_slot in (0, 1)
        assert c.projected_state.side_mega_spent.get("p2", False)  # genuinely a post-branch state
```

**Step 2 — confirm RED:** `python -m pytest tests/i7b/test_i7b_scoring.py -k depth2_for_foe_mega -q`.

**[REV.7 correction — the RED is no longer `AttributeError`-shaped.** Earlier revisions
described this RED as "neither `rec.diagnostic_contexts` nor the corrected per-index
binding exist yet (`AttributeError`/`IndexError`)". That is stale: **`rec.diagnostic_contexts`
already exists and is populated by Task 4** (`64d47ba`, gated on `_i7b_active` since
`ca39fb6`). The remaining defect is narrower and purely in the depth-2 wrap: it still
binds **every** diagnostic index to the single blanket
`ctx_by_slot[rec.variant.own_mega_slot]`. So the real RED is the spy observing depth-2
genuinely running with a non-empty `seen_ctxs`, yet **never** receiving a context with
`foe_mega_slot is not None` — a foe-Mega branch's diagnostic is refined against the
own-only board instead of its own branch board. A failure from a fixture typo, missing
import, or absent calc dependency is **not** this RED and must be fixed in the test
setup first.]**

**Step 3 — implement**: the ONLY change is inside the existing depth-2 wrap block (`mega_scoring.py:420-468`) — replace the single `ctx = ctx_by_slot[rec.variant.own_mega_slot]` line with a per-index lookup using Task 4's new `rec.diagnostic_contexts`:

```python
        for pos in ranked_pos[:top_n]:
            rec = records[pos]
            resp_ws = rec.diagnostic_weights or [1.0] * len(rec.score_vector)
            top_m_idx = sorted(range(len(resp_ws)), key=lambda i: -resp_ws[i])[:top_m]
            for i in top_m_idx:
                outcome = rec.diagnostic_details[i].representative_outcome
                # Task 6: bind to THIS index's own context (own-only ctx_by_slot
                # entry, or a specific foe-mega branch's branch_ctx) -- never a
                # blanket ctx_by_slot[rec.variant.own_mega_slot] for every index.
                bound_ctx = (
                    rec.diagnostic_contexts[i] if rec.diagnostic_contexts
                    else ctx_by_slot[rec.variant.own_mega_slot]  # Reg-I fallback, pre-I7b-B behavior
                )
                rec.score_vector[i] = depth2_value_for_mega_context(
                    bound_ctx, outcome, our_side=our_side, mode=mode, risk_lambda=risk_lambda,
                    top_m=2, book=book, predict_kwargs=d2_predict_kwargs,
                    model_kwargs=d2_model_kwargs, eval_kwargs=d2_eval_kwargs,
                )
```

The `rec.diagnostic_contexts else ctx_by_slot[...]` fallback keeps every existing I7a-only caller (which never populates `diagnostic_contexts`, since Task 4's Phase C is the only writer) byte-identical — this task changes zero behavior when `foe_mega_eligibility` is empty/None.

**No changes to `search.py`; `depth2_value_for_mega_context` itself is not modified at all** (confirmed real signature above already accepts any `MegaEvaluationContext`) — this is the "cleanest solution" the review named, made concrete rather than left as a suggestion.

**Step 4 — verify:**
```powershell
python -m pytest tests/i7b/ tests/i7a/ tests/test_search_depth2.py -q
python -m pytest -q
```

**Step 5 — commit:**
```powershell
git add src/showdown_bot/battle/mega_scoring.py tests/i7b/
git commit -m "feat(champions-i7b-b): bind depth-2 to each diagnostic index's own context (own-mega or foe-mega branch)"
```

### I7b-B completion gate

- [ ] Every new test individually RED before GREEN.
- [ ] `python -m pytest tests/i7b/ tests/i7a/ tests/test_opponent.py tests/test_protect_priors.py tests/test_search_depth2.py tests/test_config_env.py -q` — full pass.
- [ ] Full suite `python -m pytest -q` — full pass, no new skip/xfail beyond what I7b-A introduced.
- [ ] `git diff --check` clean.
- [ ] `ctx_by_slot`/`records_by_slot` in `mega_scoring.py` remain keyed by `own_mega_slot` alone (confirm via `grep -n "ctx_by_slot\s*[:=]" src/showdown_bot/battle/mega_scoring.py` shows no new keying scheme) — Rev. 1's context-multiplication approach was not silently reintroduced.
- [ ] Every foe-mega `MegaScoreRecord.score_weights` entry is verifiably `world_w * response_weight * branch_weight` (not `world_w * response_weight` alone) — a genuine dual-Mega speed tie contributes exactly two such entries, never one unweighted or two double-counted.
- [ ] `UnsupportedMegaAbilityError`/`FAIL_CLOSED_ABILITIES` gate verified to apply to a hypothesized foe form with an unsupported ability (Task 5), **on a coherent Scovillain foe** — not by injecting the form onto a mismatched species (REV.5 correction 3).
- [ ] **[REV.5]** `project_mega` rejects a species/form mismatch with `MegaProjectionSpeciesMismatchError` **before** mutating anything, and the input state is provably unmutated; the `base_species_id` **or** `species` match rule still accepts valid sub-form mappings (Task 2).
- [ ] **[REV.5]** Every test asserting two `0.5`-weight branches runs on `mega_decision_tie_fixture` and calls `_assert_pre_mega_speeds_tie(kw)` first — the tie is a **checked real-backend fact**, never an assumption (this is exactly what Rev. 4 got wrong: 200 vs 123).
- [ ] **[REV.5]** `_mega_state()`'s default board is unchanged (p2.a Incineroar, no item) and all of `tests/i7a/` is green — proving the builder extraction did not disturb the shared fixture.
- [ ] `battle/baselines.py` was **not** modified anywhere in this slice.
- [ ] No task in this slice ran a live battle, touched a trace/sidecar file, or changed ROADMAP/PROJECT_INDEX.
- [ ] Working tree clean; no push; no I7b-C work started.

---

## I7b-C: Telemetry/provenance and safety-smoke design

**Files this slice creates:**
- `showdown_bot/src/showdown_bot/eval/opp_mega_trace.py`
- `showdown_bot/tests/test_opp_mega_trace.py`
- `config/eval/schedules/champions_v0_smoke_i7b_2battle.yaml` (schedule DESIGN only — not run)

**Files this slice modifies:**
- `showdown_bot/src/showdown_bot/battle/decision.py` (evidence-sink pass-through only)
- `showdown_bot/src/showdown_bot/eval/config_env.py` (classify the new IO-path env var as `NON_BEHAVIORAL`)
- `showdown_bot/src/showdown_bot/client/gauntlet.py` (off-by-default wiring, mirroring `agg_trace_writer`)
- `showdown_bot/tests/i7b/test_i7b_scoring.py`
- `showdown_bot/tests/test_config_env.py`
- `showdown_bot/tests/test_gauntlet_dispatch.py`
- `docs/ROADMAP.md`, `docs/PROJECT_INDEX.md` (status-line updates only — see below)

**Explicitly excludes:** running the smoke; starting a Showdown server; any Strength claim; any latency-budget change.

### Task 1 [REV.4] — `eval/opp_mega_trace.py` — raw score evidence plus explicit cap coverage

Rev. 4 keeps the direct candidate/response/branch link and raw score components from Rev. 3, but separates three different facts that must never be conflated: `required_classes` (eligibility set `R`), `retained_classes` (what `predict_responses` returned after the cap), and `scored_classes` (what survived projection and actually contributed a score). A class absent from scored evidence cannot prove that the cap retained it; therefore `reserved_classes` is removed entirely.

**Step 1 — write failing tests**, new file `showdown_bot/tests/test_opp_mega_trace.py`:

```python
"""I7b-C: opp-mega-evidence sidecar (off by default, NEVER read to make a decision).
Consumes ScoredResponseEvidence directly, raw components only (Rev. 3 finding 4)."""
from __future__ import annotations

import pytest

from showdown_bot.eval.opp_mega_trace import (
    OppMegaTraceContext,
    OppMegaTraceError,
    OppMegaTraceWriter,
    build_opp_mega_trace_row,
    validate_opp_mega_trace_row,
)


def _context():
    return OppMegaTraceContext(
        battle_id="b0", config_id="heuristic", config_hash="cfg", schedule_hash="sched",
        format_id="gen9championsvgc2026regma", git_sha="a" * 40,
    )


def _evidence():
    from showdown_bot.battle.mega_scoring import ScoredResponseEvidence

    return [
        ScoredResponseEvidence(
            candidate_key='{"version":2,"slots":[...]}', response_id="aggro->a|mega=none",
            foe_mega_slot=None, branch_index=0, branch_weight=1.0,
            world_index=0, world_weight=1.0, response_weight=0.4, raw_score=0.12,
            required_classes=("0", "none"), retained_classes=("0", "none"),
        ),
        ScoredResponseEvidence(
            candidate_key='{"version":2,"slots":[...]}', response_id="aggro->a|mega=0",
            foe_mega_slot=0, branch_index=0, branch_weight=1.0,
            world_index=0, world_weight=1.0, response_weight=0.35, raw_score=0.31,
            required_classes=("0", "none"), retained_classes=("0", "none"),
        ),
    ]


def test_build_row_keeps_candidate_response_branch_link_explicit():
    row = build_opp_mega_trace_row(
        context=_context(), decision_index=1, turn_number=1, evidence=_evidence(),
        max_candidates=5, click_rate=0.35,
    )
    validate_opp_mega_trace_row(row)
    assert row["candidate_keys"][1] == _evidence()[1].candidate_key
    assert row["response_ids"] == ["aggro->a|mega=none", "aggro->a|mega=0"]
    assert row["foe_mega_slots"] == [None, 0]
    assert row["branch_indices"] == [0, 0]
    assert row["branch_weights"] == [1.0, 1.0]
    assert row["world_indices"] == [0, 0]
    assert row["world_weights"] == [1.0, 1.0]
    assert row["response_weights"] == [0.4, 0.35]
    assert row["raw_scores"] == [0.12, 0.31]
    assert row["opp_mega_click_rate"] == 0.35


def test_required_retained_and_scored_classes_are_distinct_and_validated():
    row = build_opp_mega_trace_row(
        context=_context(), decision_index=1, turn_number=1, evidence=_evidence(),
        max_candidates=5, click_rate=0.35,
    )
    assert row["required_classes"] == ["0", "none"]
    assert row["retained_classes"] == ["0", "none"]
    assert row["scored_classes"] == ["0", "none"]
    assert set(row["required_classes"]) <= set(row["retained_classes"])


def test_validate_rejects_mismatched_parallel_array_lengths():
    row = build_opp_mega_trace_row(
        context=_context(), decision_index=1, turn_number=1, evidence=_evidence(),
        max_candidates=5, click_rate=0.35,
    )
    row["response_ids"] = row["response_ids"][:1]  # corrupt -- now shorter than candidate_keys
    with pytest.raises(OppMegaTraceError):
        validate_opp_mega_trace_row(row)


def test_writer_writes_one_line_per_decision(tmp_path):
    path = tmp_path / "opp_mega_trace.jsonl"
    writer = OppMegaTraceWriter(str(path))
    row = build_opp_mega_trace_row(
        context=_context(), decision_index=0, turn_number=1, evidence=_evidence(),
        max_candidates=5, click_rate=0.35,
    )
    writer.write(row)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1


def test_row_never_includes_result_or_winner_fields():
    """Hard constraint: the sidecar is decision-time evidence only -- it must
    never carry a game outcome/winner field that could turn it into an
    accidental Strength artifact."""
    row = build_opp_mega_trace_row(
        context=_context(), decision_index=1, turn_number=1, evidence=_evidence(),
        max_candidates=5, click_rate=0.35,
    )
    assert "winner" not in row
    assert "result" not in row
    assert "game_outcome" not in row


def test_empty_evidence_produces_a_valid_empty_row():
    """No evidence means no coverage claim. The writer stays valid but must
    not invent a retained or required class."""
    row = build_opp_mega_trace_row(
        context=_context(), decision_index=2, turn_number=3, evidence=[],
        max_candidates=5, click_rate=0.35,
    )
    validate_opp_mega_trace_row(row)
    assert row["candidate_keys"] == []
    assert row["required_classes"] == []
    assert row["retained_classes"] == []
    assert row["scored_classes"] == []


def test_validate_rejects_required_class_missing_from_retained_classes():
    row = build_opp_mega_trace_row(
        context=_context(), decision_index=1, turn_number=1, evidence=_evidence(),
        max_candidates=5, click_rate=0.35,
    )
    row["retained_classes"] = ["none"]
    with pytest.raises(OppMegaTraceError):
        validate_opp_mega_trace_row(row)
```

**Step 2 — confirm RED:** `python -m pytest tests/test_opp_mega_trace.py -q` → `ModuleNotFoundError`.

**Step 3 — implement** `eval/opp_mega_trace.py`, mirroring `research/aggregation_trace.py`'s existing shape (writer/context/row-builder/validator split) exactly:

```python
"""Opp-mega-evidence sidecar (I7b-C): proves a foe-Mega hypothesis was
GENERATED and SCORED for a hero decision -- never read to make a decision,
never a substitute for the actual protocol Mega event, off by default.

Built directly from battle.mega_scoring.ScoredResponseEvidence (candidate_key,
response_id, foe_mega_slot, branch_index, branch_weight, world_index,
world_weight, response_weight, raw_score, required_classes, retained_classes)
-- raw components only, never a
pre-multiplied "contribution" (Rev. 3 finding 4b/4c: aggregate_scores is
non-linear under MUST_REACT/NEUTRAL, so no single per-response product is
correct under both). NOT a loose response/weight list correlated only by
battle_id/decision_index (that link is too weak to prove which candidate was
scored against which response).

Schema is deliberately separate from decision-trace-v3 (see
docs/superpowers/specs/2026-07-16-champions-opponent-mega-i7b-audit.md §5):
response-level opponent data has no analogue in the v3 candidate schema and
must not silently overload it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass


class OppMegaTraceError(ValueError):
    pass


@dataclass(frozen=True)
class OppMegaTraceContext:
    battle_id: str
    config_id: str
    config_hash: str
    schedule_hash: str
    format_id: str
    git_sha: str


_REQUIRED_FIELDS = frozenset({
    "battle_id", "config_id", "config_hash", "schedule_hash", "format_id", "git_sha",
    "decision_index", "turn_number", "candidate_keys", "response_ids", "foe_mega_slots",
    "branch_indices", "branch_weights", "world_indices", "world_weights",
    "response_weights", "raw_scores", "required_classes", "retained_classes",
    "scored_classes", "max_candidates",
    "opp_mega_click_rate",
})
_PARALLEL_FIELDS = (
    "candidate_keys", "response_ids", "foe_mega_slots", "branch_indices",
    "branch_weights", "world_indices", "world_weights", "response_weights", "raw_scores",
)


def _coverage_classes(evidence: list) -> tuple[list[str], list[str], list[str]]:
    if not evidence:
        return [], [], []
    required_sets = {tuple(e.required_classes) for e in evidence}
    retained_sets = {tuple(e.retained_classes) for e in evidence}
    if len(required_sets) != 1 or len(retained_sets) != 1:
        raise OppMegaTraceError(
            "all evidence in one decision row must agree on required/retained classes"
        )
    required = sorted(next(iter(required_sets)))
    retained = sorted(next(iter(retained_sets)))
    scored = sorted({
        "none" if e.foe_mega_slot is None else str(e.foe_mega_slot)
        for e in evidence
    })
    return required, retained, scored


def build_opp_mega_trace_row(
    *, context: OppMegaTraceContext, decision_index: int, turn_number: int,
    evidence: list, max_candidates: int, click_rate: float,
) -> dict:
    required_classes, retained_classes, scored_classes = _coverage_classes(evidence)
    return {
        "battle_id": context.battle_id,
        "config_id": context.config_id,
        "config_hash": context.config_hash,
        "schedule_hash": context.schedule_hash,
        "format_id": context.format_id,
        "git_sha": context.git_sha,
        "decision_index": decision_index,
        "turn_number": turn_number,
        "candidate_keys": [e.candidate_key for e in evidence],
        "response_ids": [e.response_id for e in evidence],
        "foe_mega_slots": [e.foe_mega_slot for e in evidence],
        "branch_indices": [e.branch_index for e in evidence],
        "branch_weights": [float(e.branch_weight) for e in evidence],
        "world_indices": [e.world_index for e in evidence],
        "world_weights": [float(e.world_weight) for e in evidence],
        "response_weights": [float(e.response_weight) for e in evidence],
        "raw_scores": [float(e.raw_score) for e in evidence],
        "required_classes": required_classes,
        "retained_classes": retained_classes,
        "scored_classes": scored_classes,
        "max_candidates": max_candidates,
        "opp_mega_click_rate": click_rate,
    }


def validate_opp_mega_trace_row(row: dict) -> None:
    missing = _REQUIRED_FIELDS - set(row)
    unknown = set(row) - _REQUIRED_FIELDS
    if missing or unknown:
        raise OppMegaTraceError(f"opp-mega-trace row fields missing={sorted(missing)} unknown={sorted(unknown)}")
    lengths = {len(row[f]) for f in _PARALLEL_FIELDS}
    if len(lengths) > 1:
        raise OppMegaTraceError(
            f"opp-mega-trace row's parallel arrays must share one length, got {lengths}"
        )
    for field_name in ("required_classes", "retained_classes", "scored_classes"):
        if not isinstance(row[field_name], list):
            raise OppMegaTraceError(f"{field_name} must be a list")
    if not set(row["required_classes"]) <= set(row["retained_classes"]):
        raise OppMegaTraceError("required_classes must be a subset of retained_classes")
    if not set(row["scored_classes"]) <= set(row["retained_classes"]):
        raise OppMegaTraceError("scored_classes must be a subset of retained_classes")


class OppMegaTraceWriter:
    def __init__(self, path: str) -> None:
        self.path = path

    def write(self, row: dict) -> None:
        validate_opp_mega_trace_row(row)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
```

**`max_candidates` provenance:** the audit confirmed no live caller overrides `predict_responses`'s default of `5` today. Task 2's gauntlet wiring passes the same `battle.opponent.DEFAULT_MAX_CANDIDATES` constant used by the real cap check. `required_classes` and `retained_classes` come from the scoring call's actual pre/post-cap response set; `scored_classes` comes from raw score evidence. None is reconstructed from another class.

**Step 4 — verify:** `python -m pytest tests/test_opp_mega_trace.py -q`.

**Step 5 — commit:**
```powershell
git add src/showdown_bot/eval/opp_mega_trace.py tests/test_opp_mega_trace.py
git commit -m "feat(champions-i7b-c): add opp-mega evidence and cap-coverage sidecar"
```

### Task 2 [REV.4] — full evidence-sink call chain, env classification, and off-by-default gauntlet wiring

`score_evaluated_variants` still returns only `list[MegaScoreRecord]`. The additive sink must traverse the complete real chain, preserving the same list object at every layer:

`_Client.handle_request → agent_choose → choose_with_fallback(**deps) → heuristic_choose_for_request → _choose_best_ja → _choose_best → _choose_best_mega → score_evaluated_variants`.

Add `opp_mega_evidence_sink: list[ScoredResponseEvidence] | None = None` to every explicit signature in that chain (`agent_choose`, `heuristic_choose_for_request`, `_choose_best_ja`, `_choose_best`, `_choose_best_mega`) and pass it unchanged. `choose_with_fallback` already forwards additive entries through `**deps`; do not add a second container there. `_Client.handle_request` creates one fresh list per eligible decision only when its writer is enabled, passes it to `agent_choose`, then writes exactly that list after a successful choice. The sidecar remains independent of `DecisionTrace` construction.

**Step 0 — write one small wiring test proving the call chain, before the env/gauntlet work below:**

```python
def test_choose_best_mega_extends_opp_mega_evidence_sink_when_provided(mega_decision_fixture):
    """Plumbing only, not scoring logic: a caller-supplied list must be
    extended in place with whatever score_evaluated_variants would have
    produced via its own opp_mega_evidence_sink parameter -- proving the
    sink genuinely reaches _choose_best_mega's own call, not a disconnected
    parameter that gets silently dropped somewhere in between."""
    from showdown_bot.battle.decision import _choose_best_mega
    from showdown_bot.engine.mega_form import mega_form_for

    req, kw = mega_decision_fixture
    sink: list = []
    _choose_best_mega(
        req, state=kw["state"], book=kw["book"], our_side="p1", opp_side="p2",
        calc=kw["calc"], oracle=kw["oracle"], speed_oracle=kw["speed_oracle"], dex=kw["dex"],
        priors=None, weights=kw["weights"], risk_lambda=0.5, tera_margin=0.0,
        rollout_horizon=0, report=None, our_spreads=kw.get("our_spreads"), opp_sets=None,
        trace=None, format_config=kw["format_config"], calc_profile=kw["calc_profile"],
        accuracy_mode=False, accuracy_branch_cap=6, endgame=False, fast_board=False,
        mode=kw["mode"], my_actions=list(kw["contexts"][0].plans.keys()),
        opp_mega_evidence_sink=sink,
    )
    assert sink
    assert any(e.foe_mega_slot is not None for e in sink)
    assert all(e.candidate_key for e in sink)
```

Use the exact `_choose_best_mega` keyword list already pinned in the production-contract section and the additive `mega_decision_fixture` extension from I7b-B Task 4 Step 0. No further fixture invention is allowed in this slice.

Add two wrapper tests so the lower integration test cannot hide a dropped middle or upper layer:

```python
def test_agent_choose_passes_same_opp_mega_sink_to_choose_with_fallback(monkeypatch):
    import showdown_bot.client.gauntlet as gauntlet

    sink = []
    seen = {}

    def fake_choose(req, **kwargs):
        seen["sink"] = kwargs["opp_mega_evidence_sink"]
        return f"/choose default|{req.rqid}"

    monkeypatch.setattr(gauntlet, "choose_with_fallback", fake_choose)
    out = gauntlet.agent_choose(
        "heuristic", _req(), state=_state(), book=_book(), our_side="p1",
        opp_mega_evidence_sink=sink,
    )
    assert out.startswith("/choose ")
    assert seen["sink"] is sink


def test_public_heuristic_wrappers_pass_same_sink_to_choose_best(monkeypatch):
    import showdown_bot.battle.decision as decision
    from showdown_bot.battle.actions import enumerate_my_actions

    sink = []
    seen = {}
    legal = enumerate_my_actions(_req())[0]

    def fake_choose_best(req, **kwargs):
        seen["sink"] = kwargs["opp_mega_evidence_sink"]
        return legal, 0.0

    monkeypatch.setattr(decision, "_choose_best", fake_choose_best)
    decision.heuristic_choose_for_request(
        _req(), state=_state(), book=_book(), our_side="p1",
        opp_mega_evidence_sink=sink,
    )
    assert seen["sink"] is sink
```

**Step 1 — write failing test**, append to `showdown_bot/tests/test_config_env.py`:

```python
def test_opp_mega_trace_out_is_non_behavioral_and_classified():
    assert "SHOWDOWN_OPP_MEGA_TRACE_OUT" in NON_BEHAVIORAL
    assert is_classified("SHOWDOWN_OPP_MEGA_TRACE_OUT")


def test_behavior_env_excludes_opp_mega_trace_out(monkeypatch):
    monkeypatch.setenv("SHOWDOWN_OPP_MEGA_TRACE_OUT", "/tmp/x.jsonl")
    assert "SHOWDOWN_OPP_MEGA_TRACE_OUT" not in behavior_env()
```

**Step 2 — confirm RED.**

**Step 3 — implement**: add `"SHOWDOWN_OPP_MEGA_TRACE_OUT"` to `NON_BEHAVIORAL` in `eval/config_env.py`. Add the explicit sink parameter and pass-through at every function named in the call graph above. Then wire `opp_mega_trace_writer`/`opp_mega_trace_context` into `_Client.__init__` and `handle_request`: create `evidence = []` only when the writer is enabled and the heuristic state path is active; pass that exact object into `agent_choose`; after successful dispatch call `build_opp_mega_trace_row(..., evidence=evidence, max_candidates=DEFAULT_MAX_CANDIDATES, click_rate=opp_mega_click_rate())` and write it. With the writer disabled, pass `None` and allocate no list. Do not make this path depend on `trace_obj` or mutate `/choose`.

**Step 4 — verify:**
```powershell
python -m pytest tests/test_config_env.py tests/test_gauntlet_dispatch.py -q
```
Expected: existing aggregation-trace tests remain green, the two wrapper identity tests above pass, and `test_opp_mega_trace_on_writes_row_without_changing_dispatch` monkeypatches `agent_choose` to append a sentinel `ScoredResponseEvidence` to the supplied sink and asserts the writer receives that sentinel. This is the upper-boundary counterproof; merely asserting that the sink is a list is forbidden.

**Step 5 — commit:**
```powershell
git add src/showdown_bot/battle/decision.py src/showdown_bot/eval/config_env.py src/showdown_bot/client/gauntlet.py tests/i7b/test_i7b_scoring.py tests/test_config_env.py tests/test_gauntlet_dispatch.py
git commit -m "feat(champions-i7b-c): wire opp-mega-trace sidecar into gauntlet (off by default)"
```

### Task 3: safety-smoke design (document only, do not run)

**Step 1:** write `config/eval/schedules/champions_v0_smoke_i7b_2battle.yaml` by copying the two frozen rows from `champions_v0_smoke_i7a_2battle.yaml` exactly: row 0 uses `teams/panel_champions_v0/goodstuff.txt` (contains Delphox @ Delphoxite, committed team hash `0054b6894af7215a`); row 1 uses `teams/panel_champions_v0/rain_offense.txt` (contains Meganium @ Meganiumite, committed team hash `e0c96fa0cabf1def`). Keep the same `version`, `panel_hash`, hero team, policies, splits, and seed indices. Both existing opponent teams are Mega-capable and non-Scovillain; no new team file or runtime team-choice decision is allowed. The rain row remains safety evidence only and does not become an independent Strength holdout.

**Step 2:** document (in this plan, not a new file) the exact future-smoke evidence gate, mirroring I7a-C's `mega_evidence.py`/`bind_protocol_mega_pair` precedent:

- Clean run provenance: `git_sha`/`config_hash`/`schedule_hash` consistent across rows, `dirty=false`, matching the I7a-C `eval-report --mode gate` gate set verbatim.
- Zero crashes, zero invalid choices, standard 1000ms latency budget reported (not changed).
- At least one `opp_mega_trace.jsonl` row with a `foe_mega_slots` entry containing `0` or `1` **and** a `foe_mega_slots` entry containing `None` for the SAME row (no-mega twin retained, per-row — not a separate row/decision cross-referenced by `battle_id`/`decision_index` coincidence; Rev. 3 finding 4a/5: both twins now live in the SAME row's own parallel arrays by construction, since Task 4's Phase C emits evidence for every response of a decision into the SAME `opp_mega_evidence_sink` list).
- The row's `required_classes` equals eligibility set `R`, and `required_classes ⊆ retained_classes` (direct proof that the cap retained every mandatory class). Separately, `scored_classes` contains both `"none"` and at least one Mega slot, proving a retained Mega hypothesis also survived projection and contributed a score.
- At least one hero candidate's `aggregate_score` in the same decision's trace-v3 row was computed from a `score_vector`/`score_weights` pool that included a foe-Mega branch's contribution — provable directly from the `opp_mega_trace.jsonl` row's own `candidate_keys`/`foe_mega_slots` arrays (a `candidate_key` appearing with a non-`None` `foe_mega_slot` IS the proof that candidate's score pool included that branch; Rev. 3 correction: the OLD "cross-reference by `battle_id`/`decision_index`" language is exactly finding 5's original weak-correlation complaint from the round-2 review — replaced here with the strong, per-row, per-candidate link the corrected evidence schema already carries, no cross-sidecar join needed at all).
- The actual protocol `-mega` event for the opponent, if the real Showdown battle happens to produce one, is **supporting evidence only** — the gate must pass on the hypothesis-generated-and-scored evidence above even in a battle where the opponent never actually clicks Mega (an eligible-but-unclicked hypothesis is still a valid, complete proof of I7b working correctly).
- No raw room logs committed (same discipline as I7a-C).
- Verdict wording template: `I7b OPPONENT-MEGA SAFETY PASS · NO STRENGTH CLAIM` on full pass; `I7b OPPONENT-MEGA SAFETY INCONCLUSIVE — no full opponent-Mega hypothesis observed` if every other gate passes but no eligible-and-scored hypothesis was ever generated in either battle; name the specific failed axis otherwise. Never write PASS by retrying with a different seed.

**Step 3 — verify:** `python -m pytest tests/test_schedule.py -q` (new schedule file must load with `load_schedule` exactly like the I7a-C schedule did) — write one new schedule-loader regression test, `test_i7b_mega_smoke_schedule_loads_and_shapes`, following `test_i7a_mega_smoke_schedule_loads_and_shapes`'s exact pattern.

**Step 4 — commit:**
```powershell
git add config/eval/schedules/champions_v0_smoke_i7b_2battle.yaml tests/test_schedule.py
git commit -m "docs(champions-i7b-c): design (not run) the I7b opponent-mega safety smoke"
```

### Task 4: minimal ROADMAP.md / PROJECT_INDEX.md updates

Update only the status lines (do not rewrite unrelated sections):

- `docs/ROADMAP.md`: change "I7b opponent Mega NOT STARTED" → "I7b opponent Mega DESIGN/PLAN PROPOSED (not implemented)"; add a pointer to this plan and its audit; keep "Strength blocked... NO-GO until I7b + latency" verbatim (implementation, not just design, is still required before that gate can move); keep the `rain_offense` non-holdout sentence verbatim.
- `docs/PROJECT_INDEX.md`: same status change in "Current Priority" item 1 and "Open blockers"; update "Last reconciled" date.

**Step — commit:**
```powershell
git add docs/ROADMAP.md docs/PROJECT_INDEX.md
git commit -m "docs(champions-i7b): record I7b design/plan proposed status"
```

(This governing design/audit session does not execute this task's commit — see "Deliverables" below; it proposes the exact diff, uncommitted, for review alongside the audit/plan documents.)

### I7b-C completion gate

- [ ] Every new test individually RED before GREEN.
- [ ] `python -m pytest tests/test_opp_mega_trace.py tests/test_config_env.py tests/test_gauntlet_dispatch.py tests/test_schedule.py -q` — full pass.
- [ ] Full suite `python -m pytest -q` — full pass.
- [ ] `git diff --check` clean.
- [ ] No Showdown server started; no battle run; no Strength claim anywhere in any new doc/code/comment.
- [ ] `docs/ROADMAP.md`/`docs/PROJECT_INDEX.md` still say `I7b opponent Mega DESIGN/PLAN PROPOSED (not implemented)` and `Champions Strength NO-GO until I7b + latency` after this slice — never PASS, never GO.

---

## Test-to-task matrix (approved-spec T-numbers) **[REV.2, task numbers updated]**

| Test | Owning task | File |
|---|---|---|
| T19 (weights sum to 1) | I7b-A Task 4 | `tests/i7b/test_i7b_responses.py::test_weights_sum_to_one_at_various_click_rates` |
| T29 (post-truncate weights sum to 1) | I7b-A Task 4 | same file, same test (cap check now runs before expansion, per the Rev. 2 correction; the final renormalize assertion is unchanged) |
| T32 (coverage-preserving truncate) | I7b-A Task 4 | `test_cap_too_small_for_reserve_classes_raises`, `test_cap_sufficient_but_tight_still_reserves_every_class` |
| T26 (dual-mega branches: no-TR / TR-reversed / tie) | I7b-B Task 3 (was Task 2) | `tests/i7b/test_i7b_projection.py::test_weather_ordering_follows_the_LAST_processed_activator_not_the_first` (Rev. 2: corrected expected winner, verified against pinned Showdown source), `test_trick_room_reverses_activation_order_vs_no_tr`, `test_equal_pre_mega_speed_yields_two_half_weight_branches` |
| T51 (foe post-mega speed replan changes move order) | I7b-B Task 4 (was Task 3 — folded into the corrected scoring integration, no longer inside `predict_responses` itself) | `tests/i7b/test_i7b_scoring.py::test_foe_mega_contribution_is_weighted_by_world_times_response_times_branch` and the speed/move rebuild inside Task 4's `score_evaluated_variants` implementation (the replan now happens at the point of use, per audit §Rev.2.7, not as a standalone `predict_responses`-internal test) |

## Placeholder/undefined-symbol self-audit **[REV.4]**

Every function/type referenced above is either an existing repo symbol verified by the audit or a new symbol defined with a complete signature in its owning task. Rev. 4 additionally defines `_BranchResponsePair` before use and removes the invented `reserved_classes` API. `depth2_value_for_mega_context`, `joint_action_key_v2`, and the full decision-wrapper chain were rechecked against commit `1053cf1`.

The only run-time choice intentionally deferred is which existing panel opponent supplies the future two-battle smoke. Task 3 turns absence of a suitable existing team into an explicit smoke blocker; implementation must not invent or seed-shop a replacement.

The weather-ordering direction is binding in spec Rev. 10.

---

**REV. 4 PLAN CORRECTIONS COMPLETE — DESIGN/PLAN PROPOSED — NO COMMIT, NO I7b IMPLEMENTATION.** Data flow: identity/weights/cap in I7b-A → build all projected branches and pair original hypothesis metadata with replanned actions in I7b-B Phase A → one shared oracle flush per world in Phase B → weighted scoring plus explicit required/retained/scored coverage in Phase C → off-by-default sidecar through the complete live wrapper chain.

**READY FOR FINAL USER REVIEW (Rev. 4) — NO CODE/COMMIT/PUSH**
