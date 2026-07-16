# I7b Opponent Mega — Code Audit (against approved design rev. 10)

**Status:** Review abgeschlossen / I7b-A freigegeben — I7b-B/I7b-C remain review-gated — **Rev. 4 final data-flow corrections applied**
**Date:** 2026-07-16 (Rev. 4)
**Base commit:** `1053cf1` (`main` == `origin/main`, I7a merged and closed: `I7a OWN-MEGA SAFETY PASS · NO I7b · NO STRENGTH CLAIM`)
**Companion plan:** `docs/superpowers/plans/2026-07-16-champions-opponent-mega-i7b.md` (Rev. 4)
**Companion spec correction:** `docs/superpowers/specs/2026-07-14-champions-mega-i7-design.md` rev. 10 now binds T26§1's source-verified weather-winner correction.
**Input spec:** `docs/superpowers/specs/2026-07-14-champions-mega-i7-design.md` rev. 10 (APPROVED/binding).

This is a documentation-only artifact. No production code, test code, or generated metadata was touched to produce it. Every active Rev. 4 claim below was rechecked against the cited source at commit `1053cf1` in worktree `C:\Users\chris\Documents\SHowdown BOt-i7b-design`.

---

## Rev. 4 — final Codex data-flow corrections

Rev. 4 supersedes the affected Rev. 3 conclusions and plan snippets in five places:

1. **Original Mega hypothesis metadata must survive branch replanning.** The second `predict_responses(branch.projected_state, ...)` call is only an action replan. Its base response weight cannot replace the original Mega twin's click-rate/cap-renormalized weight, and its label cannot replace the original `response_id`. The scoring bundle therefore stores `(original, replanned)` pairs: actions from `replanned`; identity and weight from `original`.
2. **`SpeedOracle.speed_for_species` is the sole foe spread resolver.** A manual `lookup_opp_set` pre-check in `project_mega` would reject a valid book-only hypothesis before the real resolver's primary `book` path runs. The side-aware projection delegates directly to the existing central accessor.
3. **One shared oracle means one flush per world.** Every model enqueues into the same `DamageOracle`; its first `flush()` drains the complete pending queue. Per-branch calls after that are empty no-ops, not separate batches.
4. **Cap coverage and scored evidence are different facts.** `required_classes` comes from eligibility `R`; `retained_classes` comes from the actual post-cap response set; `scored_classes` comes from branch evidence. A sidecar may claim cap coverage only when `required_classes ⊆ retained_classes`. Deriving "reserved" classes solely from scored evidence is invalid and removed.
5. **The sink must cross the real live call graph.** The same list instance is passed through `_Client.handle_request → agent_choose → choose_with_fallback → heuristic_choose_for_request → _choose_best_ja → _choose_best → _choose_best_mega → score_evaluated_variants`. Tests pin non-empty lower-layer evidence, wrapper object identity, and the upper gauntlet writer boundary.

The Rev. 10 weather correction is accepted and binding: faster Mega activation is processed first outside Trick Room; the later-processed weather setter overwrites it.

## Rev. 3 — corrections from Codex review round 2

> Historical record only. Rev. 4 supersedes Rev. 3's branch-response weight/identity handling, multi-flush description, foe `book` pre-check, evidence-derived `reserved_classes`, and incomplete sink-wiring proof.

All seven numbered findings from the second review round were independently re-verified against real source before acceptance (never taken on the reviewer's word) — direct reads of `battle/policy.py`, `battle/candidate_identity.py`, `battle/search.py`, `battle/opponent.py`, `battle/mega_scoring.py`, `engine/mega_projection.py`, `engine/speed.py`, `engine/spread_lookup.py`, `tests/i7a/conftest.py`, `tests/i7a/test_i7a_decision.py`, and the pinned Showdown source. All seven were **confirmed real** (finding 6d was confirmed only in part — see below, a genuine refinement of the reviewer's own claim, not a rejection of it). Rev. 2's Task 4/Task 6/I7b-C Task 1-2 content is **superseded** by the corrected versions now in the companion plan; this section documents what changed and why.

1. **Branch-state/plan mismatch (finding 1) — CONFIRMED.** Rev. 2's foe-Mega scoring evaluated the record's own-only-context `plan` (planned against the pre-branch `ctx.projected_state`) against the branch's OWN `projected_state`, and patched only the foe-mega slot's own action via `replace()` — leaving the foe's untouched partner's speed/move stale even though Mega weather changes every mon's effective speed, not just the Mega'd one's; `target_mon_for` also read the pre-projection `state`. Rev. 3 correctly required full hero-plan and opponent-response replanning, but incorrectly let the replanned response replace the original Mega hypothesis metadata. **Rev. 4 is binding:** pair original identity/weight with replanned actions and fail closed when the corresponding branch response cannot be found.
2. **Batching claim didn't match the pseudocode (finding 2) — CONFIRMED.** Rev. 2's prose promised "flushed once per world"; the real code nested `branch_model`/`.enqueue()`/`oracle.flush()` inside the per-candidate loop, so the flush count scaled with candidates × responses × branches. Rev. 3 reduced that to multiple staged flushes, but all models share one oracle, so every later flush would be an empty no-op after the first drained the queue. **Rev. 4 is binding:** build and enqueue the complete world, call `oracle.flush()` exactly once, then evaluate.
3. **Weighting inconsistency under `priors=None` (finding 3) — CONFIRMED, fixed.** The no-mega path defaulted to a flat `1.0` weight under `priors=None`; the mega path used the real `r.weight` unconditionally — the two paths didn't correspond to the same semantics for the same decision. **Fixed**: when `foe_mega_eligibility` is non-empty (the I7b path genuinely active), every response — no-mega included — now uses its real `r.weight`; the legacy `priors is not None` gate is preserved byte-identically when `foe_mega_eligibility` is empty/`None` (every existing I7a-only caller), verified by the Reg-I byte-identical test.
4. **Evidence API defects (finding 4) — CONFIRMED, fixed, in five parts:**
   - **4a (no no-mega evidence):** confirmed — Rev. 2 only ever appended inside the foe-mega branch loop. Fixed: Task 4's Phase C now appends one `ScoredResponseEvidence` per response, no-mega included.
   - **4b/4c (non-additive "contribution", missing world/response breakdown):** confirmed by direct read of `battle/policy.py:46-90` — `aggregate_scores` is non-linear under `GameMode.MUST_REACT` (`mean - λ*(mean-min)`) and the weighted-variance operator (`mean - λ*variance`), so a single pre-multiplied `score * weight` product is not a real per-response "contribution" under either. Fixed: `ScoredResponseEvidence` now carries `world_index`/`world_weight`/`response_weight`/`raw_score` as separate raw components; no field claims to be an additive contribution.
   - **4d (`joint_action_key_v2` vs the nonexistent `.joint_action_key()` method):** confirmed by direct read of `battle/candidate_identity.py:30,48` — `JointAction` has no such method; the real accessors are the module-level functions `joint_action_key(ja)`/`joint_action_key_v2(ja)`. Fixed throughout the plan.
   - **4e (return-type change breaks real callers):** confirmed by `grep` — 8 real call sites (`battle/decision.py:733` + 7 in `tests/i7a/test_i7a_decision.py`) do `records = score_evaluated_variants(...)` today, none unpacking a tuple. Fixed: the return type stays `list[MegaScoreRecord]`; evidence is opt-in via a new `opp_mega_evidence_sink: list | None = None` keyword-only out-parameter, appended to in place — mirroring the real, existing `trace: DecisionTrace | None` threading pattern already used throughout `battle/decision.py` (confirmed at lines 412, 667, 812, 1244, 1298, 1393), not an invented plumbing shape.
   - A related, previously-unnoticed consequence discovered while fixing 4a-4e: the existing depth-2 wrap block (`mega_scoring.py:420-468`) binds ALL of a record's top-M diagnostic indices to one blanket `ctx_by_slot[rec.variant.own_mega_slot]` — with foe-Mega branch responses now interleaved into the same `score_vector`/`diagnostic_details` arrays, a record's own top-M may legitimately include a foe-Mega branch response, which must bind to THAT branch's own context. Fixed by a new `MegaScoreRecord.diagnostic_contexts` field (world-0-only, same cadence as `diagnostic_details`/`diagnostic_weights`) recording which context each diagnostic index actually used — this is what makes Task 6 (finding 5) possible without touching `search.py` at all.
5. **Depth-2 remained a real placeholder (finding 5) — CONFIRMED, fixed.** Rev. 2's Task 6 was an admittedly-incomplete test skeleton deferring to "read the real signature later." `search.py::depth2_value_for_mega_context`'s real signature (`search.py:201-232`) was read in full this Rev.: it takes any `MegaEvaluationContext` and is always bound to `ctx.projected_state`/`ctx.damage_model.oracle`. Per the review's own suggested cleanest solution, Task 6 now builds a real, branch-scoped `MegaEvaluationContext` per `(slot, foe_mega_slot, branch_idx)` (in Task 4's Phase A) and reuses `depth2_value_for_mega_context` **completely unmodified** — `search.py` is not touched by this slice at all. The one remaining production change is fixing the existing wrap block's per-record blanket-context bug (see finding 4's last bullet above) to look up the correct context per diagnostic index via the new `diagnostic_contexts` field.
6. **Plan provenance was internally contradictory (finding 6) — CONFIRMED, four parts:**
   - **6a (spec vs. plan weather contradiction):** confirmed — approved spec Rev. 9's T26 test 1 prose ("faster activator's weather wins") contradicted both §2.5's general branch rule ("last weather-setting ability wins within that branch") and the pinned Showdown mechanics verified in the I7b audit. The correction is now accepted and binding in design Rev. 10: faster activates first outside Trick Room; the later/slower weather setter overwrites it.
   - **6b (fixture EV scale, 252 vs. the project's established ~32 convention):** confirmed — the plan's own new I7b fixtures used standard-competitive `evs={"spe": 252}`-style values inconsistent with every sibling fixture in this suite (`tests/conftest.py::mega_decision_fixture`, `tests/i7a/conftest.py::aerodactyl_spreads`, `tests/test_baselines.py`, all using small ~32-point investments for test doubles). Fixed: every I7b-B Task 3 fixture now uses the same modest-EV convention, with the exact speed values (e.g. Froslass Timid spe=32 → 178, Tyranitar Jolly spe=32 → 124) **verified via direct `SpeedOracle._base_speed` computation against the real calc backend**, not assumed from base-stat intuition (the same discipline this project applied to catching T51's under-specified hero-speed value earlier in this slice's history).
   - **6c (sibling-`conftest.py` fixture-import decision left open):** confirmed and resolved definitively, not left open — `tests/i7b/` is a SIBLING of `tests/i7a/`, not a subdirectory, so pytest's directory-scoped conftest discovery does not make `tests/i7a/conftest.py`'s fixtures visible in `tests/i7b/` automatically (confirmed: no `pytest_plugins` cross-import exists in this project, and asserting one would risk an unverified rootdir-relative module path). Decision: I7b builds its own self-contained, `i7b_`-prefixed fixtures (`i7b_aerodactyl_spreads`, `i7b_froslass_spreads`, `i7b_opp_sets_tyranitar`) rather than importing across the sibling boundary — the prefix also resolves the fact that `tests/i7a/conftest.py::aerodactyl_spreads` already exists with a DIFFERENT shape (a bare `SpeciesSpreads`, wrapped into a dict by each of ITS OWN call sites — confirmed at `tests/i7a/test_i7a_decision.py:117`) than every I7b-B call site expects (a species-keyed dict directly) — reusing the real name would have been a same-name, different-shape collision risk even before the cross-directory-visibility question.
   - **6d (`book` claimed as an eligibility source) — confirmed IN PART, refined.** The plan's `foe_mega_eligibility` accepted an unused `book=None` parameter and its docstring claimed eligibility draws from "a curated `opp_sets`/`book` preset" — confirmed FALSE by direct read of the proposed function body (only `opp_sets` via `lookup_opp_set` is ever consulted; `book` was accepted but never read). Fixed: the parameter is removed from `foe_mega_eligibility` entirely (YAGNI — `SpreadBook` carries no item field for an eligibility check to read). **Refinement of the reviewer's broader claim** ("both eligibility and `project_mega` essentially only use `opp_sets`"): by direct read of `engine/speed.py:150-177`, `speed_for_species`'s foe-side branch (`is_ours=False`, used by `project_mega`'s foe-side speed lookup) treats `book`-derived `hypothesis_from_state` as the **primary** source and `opp_sets` as only a fallback when no `book` hypothesis exists — so `book` is NOT dead in `project_mega`'s speed path, only in the separate `foe_mega_eligibility` function. The plan's language is corrected to state this distinction precisely rather than treat the two functions as symmetric.
7. **I7b-C not fully wired (finding 7) — CONFIRMED.** `reserved_classes` did not exist in source and Rev. 3's attempt to derive it from scored evidence was not a valid cap-retention proof: a class excluded before scoring cannot appear in that evidence. **Rev. 4 is binding:** persist distinct `required_classes` from eligibility, `retained_classes` from the post-cap response set, and `scored_classes` from evidence; require `required_classes ⊆ retained_classes`. `max_candidates` still comes from the shared `battle.opponent.DEFAULT_MAX_CANDIDATES` constant. The sidecar uses its direct per-row candidate/response link, never a weak cross-file `battle_id`/`decision_index` coincidence.

**Rev. 3 self-audit note:** Rev. 2's own corrective rewrite of Task 4's tests had introduced two vacuous `... or True` assertions and one literal `TODO` string — caught and fixed in a prior pass (documented in the plan's own hygiene history) before this Rev. 3 round began. This round's rewrite was checked against the same anti-pattern before being finalized (see the companion plan's placeholder/`or True` grep results in its own closing self-audit section).

## Rev. 2 — corrections from Codex review round 1

All six numbered findings and the six secondary findings from the review were independently re-verified against the actual source (not accepted on say-so). Every one was **confirmed real**. None was found to be a false positive. Rev. 1's architecture decisions in §3 are **superseded** by this section; §1/§2 below are corrected in place with `[REV.2]` markers rather than rewritten wholesale, so the original evidence trail stays visible.

1. **Confirmed — dual-Mega contexts would be silently overwritten and `branch_weight` was never factored into scoring.** `mega_scoring.py::score_evaluated_variants` indexes its per-decision state **exclusively** by `own_mega_slot`:
   ```python
   ctx_by_slot: dict[int | None, MegaEvaluationContext] = {c.own_mega_slot: c for c in contexts}
   ```
   (`mega_scoring.py:334`), and `records_by_slot` (`:370-372`) groups the same way. Rev. 1's plan (I7b-B Task 4) appended additional top-level contexts sharing an existing `own_mega_slot` key (differing only in `foe_mega_slot`/`activation_order`) — under this dict comprehension, only the **last**-appended context per `own_mega_slot` would survive; every earlier dual-mega context for that same own-slot would silently vanish, never scored, never erroring. Separately, the score-weight accumulation (`rec.score_weights.append(world_w * raw_w)`, `mega_scoring.py:415`) **never multiplies in `ctx.branch_weight` at all** — a genuine tie's two 0.5-weight branches would each contribute as if `weight=1.0`, silently doubling their combined influence. **Corrected architecture (§Rev.2.7 below): stop building extra top-level contexts entirely; compose foe-Mega branches lazily, per-response, inside `score_evaluated_variants`'s existing per-`(slot, ctx)` loop, and multiply `world_w * raw_w * branch.weight` explicitly.**

2. **Confirmed — `project_mega` is hardcoded own-side-only today; this is a P1 blocker, not a possible future stop.** Read directly from `engine/mega_projection.py`:
   ```python
   preset = lookup_our_spreads(spread_lookup, mon)          # mega_projection.py:93 -- always own-side lookup
   ...
   effective_speed = speed_oracle.speed_for_species(
       ..., opp_sets=None, book=None, is_ours=True,          # mega_projection.py:104-106 -- hardcoded
   )
   ```
   This means `project_mega(state, "p2", ...)` (a foe-side call) would silently resolve the foe's spread via `lookup_our_spreads` against whatever dict is passed as `spread_lookup` (semantically wrong — that accessor is for the hero's own team) and would always pass `is_ours=True`/`opp_sets=None` to `speed_for_species`, which the audited signature (§1.9) shows branches its whole lookup strategy on `is_ours`. Rev. 1's plan (`compose_mega_projection_branches`, plan line 979) called `project_mega` for a foe activation without addressing this at all — a real, confirmed gap, not a hypothetical. **Fixed in Rev. 2 by a new, dedicated I7b-B Task 0 (below) that gives `project_mega` an explicit, tested side-aware spread/speed contract before anything is built on top of it.**

3. **Confirmed — response identity and projection context were incoherently double-owned.** Rev. 1 had TWO independent places deciding "did the opponent Mega this turn": `predict_responses` (I7b-A, tagging a response's identity) **and** a second, redundant top-level context-building pass in `mega_scoring.py` (I7b-B Task 4, projecting the foe unconditionally per eligible slot before any response even existed). Neither reconciled with the other, so (as the review states) a mega-tagged response could be scored against an unprojected board, a no-mega response could be scored against a board where the opponent was already forcibly projected, and the hero's own-Mega projection could be recomputed a second time. **Corrected architecture: response *identity* (I7b-A, `predict_responses`) stays purely logical — no projection call, no `PlannedAction` rebuild, exactly the "tag `foe_mega_slot`/`response_id`, leave the action list untouched" shape Rev. 1's I7b-A Task 4 already had (that part was already correct and is unchanged). All actual projection, `PlannedAction` replanning, and DamageModel construction for a foe-Mega response now happens exactly once, lazily, at the single point where a response is matched to its scoring context — inside the corrected `score_evaluated_variants` (§Rev.2.7). Rev. 1's I7b-B Task 3 (which had `predict_responses` itself call `project_mega`) is deleted outright, not merely fixed in place.**

4. **Confirmed — the `max_damage` audit claim was wrong; `max_damage` must be removed from I7b's live-wiring scope.** Direct read of `battle/baselines.py`:
   ```python
   """max_damage baseline: pick the legal joint action with the most immediate
   damage, preferring guaranteed KOs, IGNORING incoming damage, NEVER Tera.
   ...
   """
   ```
   (`baselines.py:20-24`), and its Mega-enabled branch `_max_damage_choice_mega` (`baselines.py:120-207`) has its own docstring stating explicitly: *"Still NEVER evaluates incoming damage, NEVER calls `evaluate.evaluate_line` or any opponent-response modeling"* (`baselines.py:142-144`) — confirmed in the scoring loop itself, which sums outgoing damage fractions per `ctx.damage_model.damage_fn` and never calls `predict_responses`/`score_evaluated_variants` at all. Rev. 1's audit (§1.10) conflated "`max_damage_choice` shares `build_own_mega_contexts` with `decision.py`" (true, and still true — both build the *same own-Mega* contexts) with "`max_damage_choice` consumes opponent responses" (**false** — it never has, for either the Mega or non-Mega path). **Corrected: I7b's foe-eligibility/click-rate wiring (Rev. 1 plan's old Task 5) is scoped to `decision.py::_choose_best_mega` only. `battle/baselines.py` is untouched by I7b entirely.** A foe-Mega-sensitive `max_damage` variant would be a distinct semantic change (giving the "ignore incoming damage" baseline an incoming-damage model) requiring its own separate justification — explicitly out of scope here, not silently added.

5. **Confirmed — `battle_id`/`decision_index` co-location does not prove which candidate was scored against which response.** The review is correct that this is too weak a link, and that `DecisionTrace` today only stores `opponent_responses`/`opponent_response_weights` as raw action lists (`battle/decision_trace.py:125-126`), never `response_id`-tagged objects, and never a per-candidate response link. **Corrected: I7b-B gains a new, explicit, non-persisted-until-written evidence unit, `ScoredResponseEvidence`** (candidate_key, response_id, foe_mega_slot, branch_index, branch_weight, score_contribution), built inline in the same corrected scoring loop that computes `MegaScoreRecord`s (§Rev.2.7), and *that* structured list — not a battle/decision-index coincidence — is what I7b-C's sidecar writer consumes. See the plan's revised I7b-B Task 5 and I7b-C Task 1.

6. **Confirmed — depth-2 was never actually threaded through the corrected dual-Mega scoring path.** Rev. 1 asserted "reuse `depth2_value_for_mega_context` verbatim" without a task that reconciles it against a *foe*-Mega branch's own `projected_state`/weight. **Corrected: a new, explicit I7b-B task reads `search.py::depth2_value_for_mega_context`'s real current signature first (not assumed) and extends it with a branch-scoped context parameter, threaded from the same per-response branch loop introduced in §Rev.2.7 — not a bare re-run of the existing (I7a-only) depth-2 tests.**

**Secondary findings, all confirmed:**

- **Cap check must run before expansion, not after** (spec §9.5's own binding order) — Rev. 1's I7b-A Task 4 pseudocode built the full expanded+weighted list first and raised `OpponentResponseCapError` only afterward. Corrected in the revised Task 4 below: compute `classes = {"none"} ∪ {eligible foe slots}` and raise immediately if `len(classes) > max_candidates`, **before** any twin is appended to `expanded`.
- **A pivot/switch response must never grow a Mega twin for the switching slot** — Mega Evolution and switching are mutually exclusive actions for the same mon on the same turn (the mon must be an active battler taking a move-class action to Mega). Rev. 1's twin-expansion loop (`eligible_here = sorted(acting_slots & foe_mega_eligibility.keys())`) did not exclude a slot whose `PlannedAction.kind == "switch"` for that particular response. Corrected: `eligible_here` now excludes any slot whose action in this specific response has `kind == "switch"`.
- **T51's chosen hero speed (140) cannot demonstrate a real order flip.** The audited Aerodactyl fixture's pre-mega speed is ~200 and post-mega ~222 (both confirmed in `tests/conftest.py`'s `_mega_state`/`_mega_req` and the I7a fixtures) — a hero speed of 140 is slower than *both*, so the move order is identical (opponent always first) regardless of Mega. Corrected: the hero speed in this test must sit strictly between the pre- and post-mega values (e.g. 210) so the order provably flips.
- **Two tests contained `... or True`, an always-true expression that cannot fail regardless of implementation correctness.** Confirmed at both cited lines. Corrected to real, falsifiable assertions in the revised test bodies below.
- **The weather-ordering test's expected winner was backwards relative to verified Showdown mechanics — resolved against the pinned source, not guessed.** Read directly from the pinned checkout at `f8ac140` (`~/.cache/showdownbot/pokemon-showdown`):
  - `sim/battle.ts:2734-2736`: the action queue processes `case 'megaEvo': this.actions.runMegaEvo(action.pokemon)` in queue order (pre-mega-speed order, per `comparePriority`, `battle.ts:404-410` — faster first outside Trick Room, exactly as `mega_activation_order_key` sorts).
  - `sim/battle-actions.ts:1902-1920` (`runMegaEvo`) → `sim/pokemon.ts:1433-1497` (`formeChange`) → `sim/pokemon.ts:1913-1946` (`setAbility`): `setAbility` ends with `this.battle.singleEvent('Start', ability, this.abilityState, this, source)` (`pokemon.ts:1944`) whenever the new ability differs — **confirming Mega Evolution does retrigger the new ability's `onStart` hook**, so Drought/Sand Stream/Snow Warning do fire immediately on Mega Evolution (validating the premise of projecting weather at all).
  - Each weather ability's `onStart` calls `this.field.setWeather(...)` unconditionally (`data/abilities.ts:1079-1082` for Drought, structurally identical for Sand Stream/Snow Warning) — an unconditional overwrite, not a "first setter wins" guard.
  - Because the queue processes the **faster** (lower `mega_activation_order_key`) Pokemon's `megaEvo` action first, that Pokemon's weather is set first — and then the **slower** Pokemon's `megaEvo` action processes second, and its own `setWeather` call **overwrites** the first. **The slower (later-processed) activator's weather is what remains active at the end of the turn's Mega-activation phase — not the faster one's.**
  - This **reverses** approved Rev. 9's own T26§1 prose ("Unequal pre-mega speed, no Trick Room — faster activator's weather wins") but is **fully consistent** with Rev. 9's own tie-case prose one paragraph later ("apply `project_mega` steps sequentially... last weather-setting ability wins within that branch") — i.e. one single rule ("last-processed-in-activation-order wins") governs both cases; Rev. 9's T26§1 sentence is the one internally-inconsistent line, not the tie-case sentence.
  - This historical discrepancy is closed by the binding Rev. 10 correction: the slower/later-processed activator's weather wins outside Trick Room; the plan tests the verified mechanics.
- **`my_actions=[]` cannot exercise a dual-own-Mega test.** `build_own_mega_contexts`/`expand_mega_variants` both iterate `my_actions`/`base_joints` — an empty list produces zero own-Mega variants regardless of eligibility, so Rev. 1's "dual own+foe Mega" test could never have exercised what it claimed to. This finding is now moot under the corrected architecture (§Rev.2.7 eliminates the extra-context-building task this test targeted), but the underlying test-authoring lesson (use the real fixture's real base joints, never an empty placeholder list, when a test's own docstring claims to exercise own-Mega variants) is carried into the revised plan's fixture guidance.
- **The three Rev. 1 open-implementation-decision markers are resolved.** (a) Fixture wiring: the plan now gives an exact additive extension of `tests/conftest.py::mega_decision_fixture`, including every scoring key its tests consume. (b) Own-side re-projection avoidance is moot under §Rev.2.7 (no second `build_own_mega_contexts` pass). (c) The I7b-C smoke reuses the frozen I7a rows exactly: `goodstuff.txt` (Delphoxite) and `rain_offense.txt` (Meganiumite), both confirmed from committed team files; no new team or later runtime choice remains.

### Rev.2.7 — the corrected central data flow (binding for Plan Rev. 2)

```
response hypothesis (predict_responses, I7b-A: pure identity — response_id, weight, foe_mega_slot; NO projection)
        │
        ▼  (per world, per existing {None,0,1} own-Mega context — unchanged from I7a)
matching projection context (score_evaluated_variants, I7b-B: lazily composed per (own_mega_slot, foe_mega_slot)
        │                     via compose_mega_projection_branches; foe PlannedAction replanned HERE, once, at point of use)
        ▼
weighted candidate score (score_vector/score_weights += world_w * raw_w * branch.weight, per branch — a genuine
        │                  tie contributes exactly 2 weighted entries, never 1 unweighted or 2 double-counted)
        ▼
evidence sidecar (ScoredResponseEvidence, I7b-B: built inline during scoring, NOT reconstructed from
                   battle_id/decision_index coincidence — I7b-C: written by eval/opp_mega_trace.py, off by default)
```

No top-level `MegaEvaluationContext` multiplication. `ctx_by_slot`/`records_by_slot` remain keyed by `own_mega_slot` alone, exactly as I7a built them — **zero changes to `build_own_mega_contexts`** are needed under this corrected architecture (Rev. 1's I7b-B Task 4, which modified it, is deleted in full).

---

## 0. Consistency check (Phase 4 requirement) — result: NO CONTRADICTION

Cross-checked `docs/ROADMAP.md`, `docs/PROJECT_INDEX.md`, `reports/champions-panel-v0-i7a-mega-smoke.md`, `data/eval/champions-panel-v0/smoke-i7a-mega/mega-evidence.json`, and all four `docs/superpowers/plans/2026-07-15-champions-mega-i7a*.md` files against the approved spec's binding gates. Result:

- ROADMAP.md / PROJECT_INDEX.md state: I7a-A/I7a-B/I7a-C are merged at `1053cf1`; **I7b opponent Mega DESIGN/PLAN PROPOSED — NOT IMPLEMENTED**; Strength **NO-GO until I7b implementation + latency**; `rain_offense` is explicitly not an independent Strength holdout.
- `reports/champions-panel-v0-i7a-mega-smoke.md`'s verdict line and "Explicit non-claims" section both explicitly disclaim I7b and Strength.
- All four I7a plan documents carry an explicit I7b-forbidden/reservation statement (the split index `2026-07-15-champions-mega-i7a.md` has a dedicated "## I7b reservation" heading naming T19/T26/T29/T32/T51 as I7b-only and stating the index "does not authorize opponent Mega hypothesis expansion, dual-side activation ordering, or a Champions Strength run").
- No document claims I7b completion, opponent-Mega-modeling-done, general Champions readiness, or a Strength GO.

`AGENTS.md` was checked and is **absent** from the repository root.

No contradiction between approved rev. 10 and merged code was found (per the stop-rule in the governing instructions, this audit would have halted here if one existed).

---

## 1. Audited call graph (Phase 1, all 15 questions)

### 1.1 `predict_responses()` call sites

Defined `showdown_bot/src/showdown_bot/battle/opponent.py:179`. Five call sites, all in `battle/`:

| Caller | File:line | Note |
|---|---|---|
| `_choose_best` (K-world branch) | `battle/decision.py:444` | non-Mega path |
| `_choose_best` (single-world branch) | `battle/decision.py:487` | non-Mega path |
| `_choose_best_mega` | `battle/decision.py:774` | own-Mega grid, non-Mega-opponent |
| `score_evaluated_variants` | `battle/mega_scoring.py:380` | called once per `(world, context)` pair, against `ctx.projected_state` |
| `_score_turn2_plans` / `depth2_value` | `battle/search.py:85`, `battle/search.py:159` | depth-2; `search.py:85` calls it with `our_side`/`opp_side` **swapped** to reuse it as a generic "plausible joint actions for a side from `BattleState` alone" generator for our own turn-2 candidates (`replace(a, is_ours=True)` corrects the flag afterward) |

No `client/gauntlet.py` call site — gauntlet calls `heuristic_choose_for_request`/`choose_for_request`, which is upstream of all of the above.

### 1.2 Response DTO

`OppResponse` (`battle/opponent.py:71-78`):

```python
@dataclass
class OppResponse:
    actions: list[PlannedAction]
    label: str
    flags: set[str] = field(default_factory=set)
    weight: float = 1.0
```

**No species/item/mega hypothesis field, no top-level speed field.** Speed lives per-action on `PlannedAction.speed` (`battle/resolve.py:37`); species/item are read transiently while building each `PlannedAction` (`opponent.py:210-215` → `_opponent_speed` → `lookup_opp_set`) and never attached to the response object. This is a real, confirmed gap I7b must close: today's DTO cannot represent "this response assumes the opponent Mega evolved slot 0."

### 1.3 Response eligibility discovery

Not a legal-action enumerator. `predict_responses` (`opponent.py:179-296`) hardcodes exactly four fixed archetypes per call — aggressive focus-fire (≤2, `opponent.py:250-253`), a Protect read (`256-259`), one revealed-support line (`262-268`, gated on `revealed_support()` actually finding a revealed support move), and a pivot/switch (`271-273`, only when ≥2 alive opp slots). Alive-slot filtering is `_alive_slots` (`139-144`): `not mon.fainted and mon.hp_fraction > 0`. There is no PP/trapped/choice-lock check. This matters for I7b: adding "foe Mega" means adding a **fifth archetype-generation step** (mega/no-mega twins of the existing four), not extending a legality enumerator.

### 1.4 Where weights are normalized

`opponent.py:277-294`, inside `predict_responses`, gated on `priors is not None`: a Protect-prior split (`p_protect`, from `ProtectPriors.rate(...)`) followed by an explicit `total = sum(...)` renormalization to 1.0. **If `priors is None`, weights are never touched and stay at the dataclass default `1.0` each (unnormalized).** No softmax anywhere in this codebase's opponent modeling.

### 1.5 / 1.6 Candidate cap and truncation order relative to weighting

`opponent.py:275`: `responses = responses[:max_candidates]` (default `max_candidates: int = 5`, keyword-only param, `opponent.py:188`). This is a **plain list slice**, not weight-ordered (the four archetype blocks are appended in a fixed order and the slice just keeps however many of the first `max_candidates` were appended).

Confirmed order by reading top-to-bottom: **truncation (line 275) happens before weighting (lines 277-294).** Today this rarely bites because at most 5 responses are ever built (2 aggro + 1 protect + 1 support + 1 pivot = 5 = the default cap), but the ordering is real and would silently misbehave once I7b adds foe-Mega twins that can push the count above 5 — a heavy-weighted no-Mega response could be truncated away before a lighter mega-eligible representative ever gets weighted, unless the pipeline is deliberately reordered (design spec §9.4/§9.5 requires exactly this reordering, gated to a new mega-aware path — see §3 below).

Separately confirmed: **no current call site ever overrides `max_candidates`** — `decision.py`, `mega_scoring.py`, and `search.py` all call `predict_responses` without passing it, so every live call uses the default `5` today. I7b's cap-provenance work starts from a clean slate here (no existing caller assumption to preserve beyond "default stays 5").

### 1.7 Opponent planned speed construction

`PlannedAction` (`battle/resolve.py:27-46`) is a flat, non-frozen dataclass with `speed: int = 0`, `is_ours: bool = False`, `is_tera: bool = False`, and **`is_mega: bool = False`** (already present, see §1.12).

For the opponent side, `.speed` is set via `opp_speed(slot)` (closure in `predict_responses`, `opponent.py:210-215`) → `_opponent_speed` (`opponent.py:157-176`), which resolves from whatever `mon.species`/typing/item the live `BattleState`'s `PokemonState` **currently shows** for that slot (i.e., only what the protocol has already revealed — including an already-completed real Mega evolution from a prior turn, thanks to the `base_species_id`-aware `lookup_opp_set` fix from I7a's P1.2). **There is no branching over a hypothetical, not-yet-happened opponent Mega this turn** — that's precisely the I7b gap: today's opponent speed planning never calls anything resembling `project_mega` for the foe side.

### 1.8 How I7a own-Mega projection enters scoring

`battle/opponent.py` itself imports none of `engine/mega_projection.py`, `engine/mega_form.py`, or `battle/mega_variants.py` (confirmed: its only imports are `battle.resolve.PlannedAction`, `engine.moves`, `engine.spread_lookup`, `engine.state`, `engine.typechart`). So `predict_responses` does not call into I7a machinery **directly**.

But it is not fully isolated in practice: `battle/mega_scoring.py::score_evaluated_variants` (`mega_scoring.py:380-384`) calls `predict_responses(ctx.projected_state, our_side, opp_side, ..., field=ctx.field, ...)`, where `ctx.projected_state` is the **already own-Mega-projected** board for that branch — so today's opponent-response prediction already "sees" the effect of *our* Mega decision (docstring at `mega_scoring.py:318-321`: "a Mega branch's opponent-response prediction sees the Mega'd typing/bulk, never the base mon"). It never itself models or branches on a possible *opponent* Mega evolution — that composition is exactly what I7b must add.

Single-world, K-world, and depth-2 all funnel through the same `MegaEvaluationContext`/`build_own_mega_contexts`/`score_evaluated_variants` pipeline (`mega_scoring.py:154-475`) already built for I7a's own-Mega grid — see §1.9/§2 below for exactly which fields already exist as I7b placeholders.

### 1.9 Can the same machinery compose own + foe Mega without mutating live state?

Yes, structurally — with new code. `project_mega` (`engine/mega_projection.py:60-113`) never mutates its `state` argument: it deep-copies via `copy_battle_state` (`mega_projection.py:37-51`, itself `copy.deepcopy` plus an extra per-mon/`FieldState`/`side_mega_spent` re-copy) and every subsequent write targets only the copy. `mega_form_for` (`engine/mega_form.py:17-45`) is fully side-agnostic — no `side`/`is_ours` parameter at all, so it already works unmodified for a foe-side lookup. `speed_for_species` (`engine/speed.py`) already takes `is_ours: bool` and branches its spread-lookup path accordingly.

**What's missing, confirmed absent by repo-wide grep:**
- `compose_mega_projection_branches` / `WeightedMegaProjection` — **not implemented anywhere**; the only hit for either name is the design-spec markdown itself. This is the function that would sequence own+foe (or foe+foe, doubles) activations onto one shared projected-state copy when both sides Mega the same turn.
- `mega_activation_order_key` — **not implemented anywhere** in `engine/speed.py` or elsewhere (only in the spec's pseudocode, `docs/superpowers/specs/2026-07-14-champions-mega-i7-design.md:414`). The Trick-Room-aware sign convention it needs already exists as a *pattern* in `battle/resolve.py::sort_actions` (`resolve.py:126,132`: `tr = bool(field and field.trick_room)`; `speed_sort = a.speed if tr else -a.speed`) — I7b's new function should reuse this exact sign convention, not invent a new one.

`MegaEvaluationContext` (`battle/mega_scoring.py:36-54`) **already has** the exact field shape the design spec proposes — `foe_mega_slot: int | None`, `branch_weight: float`, `activation_order: tuple[tuple[str, str], ...] | None` — but its own docstring and both construction sites (`_none_context`/`_mega_context`, lines 88-98/141-151) hard-code `foe_mega_slot=None, branch_weight=1.0, activation_order=None` **unconditionally**. So I7b's context-building work is "populate existing fields with real values," not "add new fields to this dataclass."

### 1.10 Export/rollout/max_damage/K-world/depth-2 consumers

- `battle/decision.py::_choose_best`/`_choose_best_mega` — both the non-Mega K-world/single-world paths and the Mega grid path consume `OppResponse.actions`/`.weight`.
- `battle/baselines.py::max_damage_choice` — confirmed in code (not just by design-doc claim) to dispatch to `_max_damage_choice_mega` (`baselines.py:72-84`), which itself calls the **identical** `mega_scoring.build_own_mega_contexts` (`baselines.py:172`) that `decision._choose_best_mega` calls — no second `expand_mega_variants`/`filter_projectable_variants` pass, no divergence between the two consumers.
- `battle/search.py::depth2_value` / `_score_turn2_plans` — depth-2 for the non-Mega path; `mega_scoring.py:420-468` (gated `_search_depth() > 1 and world_samples() <= 1`) calls `search.depth2_value_for_mega_context` for the Mega grid, always bound to one record's own `ctx` (never a different branch's `projected_state`/oracle — enforced by that function's own docstring contract).
- `client/gauntlet.py` does not call `predict_responses` directly; it is a rollout/self-play harness upstream of `heuristic_choose_for_request`.
- ~~`max_damage_choice` genuinely does consume opponent responses (via the shared `build_own_mega_contexts`/`score_evaluated_variants` pipeline once `format_config.mega` is set) — so... `max_damage` is a real, in-scope consumer for I7b, not a symmetry inclusion.~~ **[REV.2 — this claim was WRONG, confirmed by direct code read; see §Rev.2 finding 4.** `_max_damage_choice_mega` shares `build_own_mega_contexts` (own-Mega **context construction** only) with `decision.py`, but its own docstring states it "NEVER... calls `evaluate.evaluate_line` or any opponent-response modeling" (`baselines.py:142-144`), and its scoring loop never calls `predict_responses`/`score_evaluated_variants` — it sums outgoing damage fractions only. **`max_damage` is therefore NOT an I7b consumer at all** and is removed from the live-wiring scope in Plan Rev. 2.]

### 1.11 What trace-v3 records about opponent responses today

**Nothing, at the persisted-row level.** `eval/decision_capture.py`'s `_REQUIRED_TRACE_FIELDS` (lines 544-549) and nullable sets (550-558) contain no `opponent_responses`/`opponent_response_weights`/`response_*` key. `build_trace_row` (`decision_capture.py:592-662`)'s row-construction dict extracts, per candidate, only `candidate_id`, `candidate_key`, `rank`, `aggregate_score` (lines 621-629) — describing the **hero's own** joint action, never an opponent response.

The **in-memory** `DecisionTrace` dataclass (`battle/decision_trace.py:116-140`) does carry `opponent_responses: list[Any]` and `opponent_response_weights: list[float]` (lines 125-126), populated at `battle/decision.py:971-972` and `:1170-1171` in the **non-Mega** path only — `mega_scoring.py` never sets these fields on a `DecisionTrace`. Neither field is read by `build_trace_row` at all; their only real consumers today are a **separate** research sidecar (`research/aggregation_trace.py`, off by default via `SHOWDOWN_AGG_TRACE_OUT`, `NON_BEHAVIORAL`) and `learning/features.py`/`learning/rollout.py` (ML feature export, not the trace-v3 JSONL).

### 1.12 Is `PlannedAction.is_mega` serialized anywhere?

The field exists (`battle/resolve.py:42`, default `False`) and is set to a real value at exactly one site: `battle/decision.py:256` (`_plan_my_actions`, for our own side only: `is_mega=sa.mega_evolve`). Every `PlannedAction` `opponent.py` builds (`attack`/`protect`/`support`/`switch`) never passes `is_mega=` — it stays `False` for every opponent action today. It is **not** read anywhere in `resolve.py::resolve_turn`/`sort_actions`, and it is **not** part of the trace-v3 schema (Mega identity there is tracked at the `candidate_key`/`JointAction.slotN.mega_evolve` level instead — a different, hero-only representation).

### 1.13 Can existing trace-v3 fields prove an opponent-Mega hypothesis was generated and scored?

**No** — see §1.11: the persisted row has no response-level fields at all. See §5 for the full trace/schema verdict and the chosen path.

### 1.14 Config/provenance fields; I7b click-rate wiring

`eval/config_env.py`'s current sets (verbatim, verified directly):

```python
BEHAVIOR_AFFECTING = frozenset({
    "SHOWDOWN_ROLLOUT_HORIZON", "SHOWDOWN_PROTECT_PENALTY", "SHOWDOWN_MUST_REACT_LAMBDA",
    "SHOWDOWN_RISK_LAMBDA", "SHOWDOWN_WORLD_SAMPLES", "SHOWDOWN_SEARCH_DEPTH",
    "SHOWDOWN_OPP_SETS", "SHOWDOWN_OUR_ROLL", "SHOWDOWN_OUR_DEF_PRESET", "SHOWDOWN_OPP_SPEED",
    "SHOWDOWN_REAL_SPREADS", "SHOWDOWN_RERANKER_SHADOW", "SHOWDOWN_RERANKER_MODEL_PATH",
    "SHOWDOWN_RERANKER_MANIFEST_PATH", "SHOWDOWN_RERANKER_SHADOW_TIMEOUT_MS",
    "SHOWDOWN_RERANKER_OVERRIDE", "SHOWDOWN_CALC_TIMEOUT_MS", "SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S",
    "SHOWDOWN_HERO_AGENT", "SHOWDOWN_FAST_BOARD_PROTECT_PENALTY", "SHOWDOWN_ACCURACY_MODE",
    "SHOWDOWN_ACCURACY_BRANCH_CAP",
})
SERVER_SIDE_BEHAVIOR_AFFECTING = frozenset({"SHOWDOWN_EVAL_ROOM_DEALLOC"})
NON_BEHAVIORAL = frozenset({
    "SHOWDOWN_TURN_TRACE", "SHOWDOWN_DECISION_DIFF", "SHOWDOWN_AGG_TRACE_OUT",
    "SHOWDOWN_ROOM_RAW_DUMP", "SHOWDOWN_EVAL_SEED_LOG", "SHOWDOWN_EVAL_POLICY_TELEMETRY",
    "SHOWDOWN_USERNAME", "SHOWDOWN_PASSWORD", "SHOWDOWN_SERVER", "SHOWDOWN_RERANKER_SHADOW_LOG",
    "SHOWDOWN_BATTLE_SEED_BASE", "SHOWDOWN_CALC_BACKEND",
})
NON_BEHAVIORAL_PREFIXES = ("SHOWDOWN_AUTH_", "SHOWDOWN_DATASET_")
```

No `SHOWDOWN_OPP_MEGA_CLICK_RATE` or any opponent-behavior-probability env knob exists today (confirmed by grep; the only hit is the design-spec markdown proposing it). `OpponentResponseCapError` does not exist anywhere (grep, zero hits) — the §9.5 fail-closed cap error is genuinely unimplemented.

**Mechanism confirmed for automatic config_hash inclusion:** `behavior_env()` (`config_env.py:167-174`) includes every set `SHOWDOWN_*` var **except** those in `NON_BEHAVIORAL`/`EXCLUDED_BY_REASON`/prefix families — membership in `BEHAVIOR_AFFECTING` is not even consulted by the inclusion check; that set exists purely for the drift tests (`test_every_showdown_env_read_is_classified`, `test_behavior_affecting_flags_are_actually_read_in_source` in `showdown_bot/tests/test_config_env.py`). So `SHOWDOWN_OPP_MEGA_CLICK_RATE` enters `config_hash` automatically the moment it is (a) actually read via `os.environ` somewhere in Python source and (b) not added to any exclusion set — **no change to `make_config_hash`/`build_config_manifest`/`effective_config_manifest`/`config_manifest_freeze.py` is needed.** The only required change is: read the var, add its name to `BEHAVIOR_AFFECTING` (documentary + drift-test requirement).

The closest existing opponent-behavior-probability prior is `ProtectPriors` (`engine/belief/protect_priors.py`) — YAML-loaded, not an env var, scoped to Protect only. No equivalent exists for Mega.

### 1.15 Leakage risk — full input surface to opponent modeling

`battle/opponent.py` never reads `opp_team_path`/`packed_team`/`villain`/`team_path` (grep across the file: zero matches). `predict_responses`'s full input surface is: `state` (built only from the live protocol request stream — what has actually been revealed), `book` (`SpreadBook`, curated statistical hypothesis), `opp_sets` (curated **per-format** file via `load_opp_sets_for_format`, `engine/belief/hypotheses.py:190-211`, loaded from `load_format_config(format_id).meta_path("likely_sets")` — a static, checked-in, per-format file, not the real battling opponent's actual packed team), `dex` (typing only), `priors` (`ProtectPriors`, Protect-only), `field`.

`opp_team_path`/`packed_team`/`villain` DO appear, but only in `client/gauntlet.py` (self-play harness): `_resolve_side_teams`/`_is_mirror_battle` load each side's own team for `/utm` submission, and **both** the hero and villain `Runner` are built from the **same, symmetric, curated** `opp_sets`/`book` (`gauntlet.py:811`, threaded to both sides at `:876`/`:1092`/`:1099`) — never from either side's own real packed team. There is no code path today where a gauntlet schedule's actual opponent team paste, a future protocol event, or a result/winner field flows into `predict_responses`'s inputs.

**Binding constraint for I7b (carried into the plan):** any new foe-Mega-hypothesis source must draw from this same curated/statistical layer (`book`, `opp_sets`-as-curated-file, revealed `mon.item`) — never from `client/gauntlet.py`'s villain-team plumbing, `result_jsonl.py`/schedule "winner" fields, or any as-yet-unobserved protocol line.

---

## 2. Confirmed gaps (what does NOT exist yet)

| Design-spec item | Status | Evidence |
|---|---|---|
| `compose_mega_projection_branches` / `WeightedMegaProjection` | **Not implemented** | repo-wide grep, zero hits outside the spec markdown |
| `mega_activation_order_key` | **Not implemented** | repo-wide grep, zero hits outside the spec markdown |
| `SHOWDOWN_OPP_MEGA_CLICK_RATE` / any click-rate knob | **Not implemented** | grep, zero hits; not in `config_env.py`'s sets |
| `OpponentResponseCapError` | **Not implemented** | grep, zero hits |
| Foe-Mega eligibility discovery (limited-view) | **Not implemented** | `opponent.py` has no such function; `_slot_can_mega`/`filter_projectable_variants` in `mega_variants.py` are own-side-only (read `req.active[i].can_mega_evo`, which only exists for the hero's own request) |
| `OppResponse` mega/species identity fields | **Not implemented** | `OppResponse` has only `actions`/`label`/`flags`/`weight` |
| Foe post-Mega `PlannedAction.speed` replan | **Not implemented** | `_opponent_speed` only ever reads the mon's currently-known state; no projection call |
| `MegaEvaluationContext.foe_mega_slot`/`branch_weight`/`activation_order` populated with real values | **Field shape exists, always hardcoded `None`/`1.0`/`None`** | `mega_scoring.py:88-98,141-151` |
| Coverage-preserving normalize→truncate→renormalize pipeline | **Not implemented** (today: truncate-then-weight, unconditionally) | `opponent.py:275` vs `277-294` |
| Trace/telemetry evidence for a scored opponent-Mega hypothesis | **Not implemented** at any layer (row or sidecar) | §1.11, §5 |

## 3. Architecture decisions (binding for the plan) — **[REV.1, SUPERSEDED where marked — see §Rev.2 above]**

These follow directly from the audit. Items 1, 2, 3, 6, 7 remain valid as-is (re-confirmed in Rev. 2). Items 4 and 5 are **corrected** per §Rev.2.7 — the corrected wording is shown; strike-through marks what Rev. 1 originally said and why it changed.

1. **`OppResponse` gains two new fields**, both defaulted (backward compatible with every existing construction site, all of which use keyword args for everything but `actions`):
   ```python
   response_id: str = ""            # f"{label}|mega={none|0|1}", per spec §9.3
   foe_mega_slot: int | None = None  # which opp slot (0/1) this response assumes Mega'd, else None
   ```
2. **Foe-Mega eligibility is a new, explicit, limited-view-only function** in `battle/opponent.py` (co-located with `predict_responses`, its sole caller) — not derived from any `BattleRequest` (the opponent's request is never visible to the bot; own-side eligibility's `req.active[i].can_mega_evo` pattern does not apply here). Eligibility = NOT `state.side_mega_spent[opp_side]` AND (revealed item resolves via `mega_form_for`, OR a curated `opp_sets` preset for that species lists a mega-stone item that resolves via `mega_form_for`). No `book` parameter (Rev. 3 finding 6d, corrected: `SpreadBook` carries no item hypothesis, only nature/EV presets -- there is nothing for eligibility to read from it, unlike the foe-side speed lookup where `book` genuinely is the primary source, see item 4 below). Simulator/gauntlet team data is never consulted (§1.15).
3. **`predict_responses` gains two new, defaulted, keyword-only parameters** (`foe_mega_eligibility: dict[str, MegaForm] | None = None`, `opp_mega_click_rate: float | None = None`). When either is `None`/empty, behavior is **byte-identical** to today (existing Reg-I/non-Mega callers never pass them). When both are given and non-empty, a **new internal branch** runs the full spec §9.4 pipeline (build families → expand mega/no-mega twins → normalize → coverage-preserving truncate → renormalize) instead of today's truncate-then-weight order — the reordering is isolated to this new branch, so no existing caller's behavior changes. **This function stays pure identity/weight logic — it never calls `project_mega` and never rebuilds a `PlannedAction` (confirmed correct in Rev. 1, unchanged; the error was in a *different*, now-deleted task that duplicated this responsibility — see finding 3).**
4. ~~`compose_mega_projection_branches`/`WeightedMegaProjection`/`mega_activation_order_key` are new, pure, side-agnostic additions... only `mega_scoring.py`'s context-building orchestration is new.~~ **[REV.2]** `compose_mega_projection_branches`/`WeightedMegaProjection`/`mega_activation_order_key` remain new, pure additions to `engine/mega_projection.py`/`engine/speed.py` — but `project_mega` is **not yet side-agnostic in practice** (finding 2: hardcoded `lookup_our_spreads`/`opp_sets=None`/`is_ours=True`) and must gain an explicit side-aware contract **first** (new I7b-B Task 0). And the orchestration that calls these is **not** `mega_scoring.py`'s context-building (that stays untouched, see item 5) — it is a new per-response branch loop **inside `score_evaluated_variants`**, at the exact point a foe-Mega-tagged response is matched to its score contribution (§Rev.2.7).
5. ~~`MegaEvaluationContext` is not schema-changed... `build_own_mega_contexts` gains a new, additive code path... one context per surviving `(own_mega_slot, foe_mega_slot, branch_index)` combination.~~ **[REV.2]** `MegaEvaluationContext`'s schema is still unchanged (correct, kept). But **`build_own_mega_contexts` is NOT modified at all** — the "one context per `(own_mega_slot, foe_mega_slot, branch_index)`" idea is **deleted** (finding 1: it collided in `ctx_by_slot`'s `own_mega_slot`-only keying and never multiplied in `branch_weight`). `ctx_by_slot`/`records_by_slot` stay exactly as I7a built them, keyed by `own_mega_slot` alone; foe-Mega composition happens lazily, per response, inside `score_evaluated_variants` (§Rev.2.7), which explicitly computes `world_w * raw_w * branch.weight` per contribution.
6. **Click-rate config-hash wiring requires no change to hashing machinery** (§1.14) — only: read `SHOWDOWN_OPP_MEGA_CLICK_RATE` somewhere in Python source, add the name to `BEHAVIOR_AFFECTING`, and the existing fail-closed `behavior_env()`/`make_config_hash()` chain does the rest automatically.
7. **Fail-closed cap discipline**: a new `OpponentResponseCapError(ValueError)` in `battle/opponent.py`, raised when `format_config.mega` and `len(R) > max_candidates` where `R = {no_mega} ∪ {legal foe mega slots}` — evaluated **before** expansion (finding: Rev. 1's own pseudocode built the expanded list first — corrected in Plan Rev. 2's Task 4).

## 4. Limited-view safety — hard constraints carried into the plan's tests

- Foe-Mega eligibility may use **only**: revealed `mon.item` (already known via protocol reveal, exactly the same `item_known`/`item_lost` tri-state I7a's own `apply_own_team_knowledge` already respects for the hero's side — §1.15 confirms this is symmetric/curated for the opponent), and curated `opp_sets` presets (the same per-format `likely_sets` file already used for opponent speed/damage hypotheses today; NOT `book` -- Rev. 3 finding 6d, `SpreadBook` has no item field to read).
- Forbidden inputs, explicitly tested against (see plan §"Required tests"): the real opponent team paste (`opp_team_path`/`packed_team`/gauntlet schedule team files), any future/not-yet-occurred protocol event, `result`/`winner`/outcome fields, and OTS (explicitly out of v0 per spec §9.1).
- A hard counterexample test constructs a `BattleState`+`opp_sets` where the *schedule's real opponent team file* (not `opp_sets`) contains a mega stone the bot has neither seen revealed nor hypothesized via `opp_sets`, and asserts `foe_mega_eligibility` returns no entry for that slot — proving the function never falls back to reading team-file data even if it were accidentally in scope/passed.

## 5. Trace/schema verdict — chosen path: **(2) new optional sidecar**

Per §1.11/§1.13, existing trace-v3 fields are **proven insufficient**: the persisted row has zero response-level fields (only the hero's own `candidates[]`/`chosen_*`), and even today's non-Mega `DecisionTrace.opponent_responses`/`.opponent_response_weights` in-memory fields never reach the row. Path (1) is therefore **disproven**, not chosen by convenience.

Path (3) (new `decision-trace-v4`) is **rejected**: nothing about I7b's evidence needs — or should get — mixed into the hero's own candidate-ranking schema (that schema's job is "which of *my* joint actions did I evaluate/choose," and rev. 9's own correction log already treats "no silent trace extension" and "no overloaded string labels" as load-bearing precedent from the I7a-B key-v2 migration). Bumping the schema version would also force every existing v1/v2/v3 loader/consumer to reason about a concept (opponent-Mega branch identity) that is completely orthogonal to what they read today.

**Chosen: path (2), a new, dedicated, off-by-default sidecar, following the exact precedent already established by `research/aggregation_trace.py`** (`SHOWDOWN_AGG_TRACE_OUT`, `NON_BEHAVIORAL`, a separate writer/context/counter mirroring `decision_capture`'s own shape without touching it). New module `showdown_bot/src/showdown_bot/eval/opp_mega_trace.py`, gated by a new `SHOWDOWN_OPP_MEGA_TRACE_OUT` env var (`NON_BEHAVIORAL` — an IO path, exactly like `SHOWDOWN_AGG_TRACE_OUT`/`SHOWDOWN_ROOM_RAW_DUMP`). Exact schema and task-level spec: see the plan document, I7b-C.

The sidecar's job is narrower and stricter than `aggregation_trace.py`'s ML-matrix export: it must let a future smoke **prove a foe-Mega hypothesis was generated and scored**, not merely that the real opponent eventually Mega evolved in the protocol log. Its rows therefore record, per hero decision: every response's `response_id` and raw score components; `required_classes` from eligibility; `retained_classes` from the actual post-cap response set; and `scored_classes` from evaluated evidence. It is explicitly evidence/telemetry, never read to make a decision.

## 6. Proposed slice boundaries

**I7b-A: limited-view eligibility, identities, weights, and cap discipline.**
**I7b-B: dual projection, activation ordering, and scoring integration.**
**I7b-C: telemetry/provenance and safety-smoke design.**

Justification: this mirrors I7a's own A (foundation/metadata/protocol) → B (decision/scoring integration) → C (reconcile/provenance/smoke) rhythm, which the project has already used successfully once and which this audit's own dependency graph independently supports — eligibility/weights/cap discipline (I7b-A) can be fully unit-tested as pure data-shape logic without `compose_mega_projection_branches` existing yet; the dual-projection/scoring wiring (I7b-B) is the one slice that must touch the shared `mega_scoring.py`/`engine/mega_projection.py`/`engine/speed.py` core and is therefore the highest-risk, most-reviewable-alone slice; telemetry/smoke design (I7b-C) depends on both being complete and stable before any live-run evidence gate can be written. No sub-slice claims Strength or runs a live smoke. Full task breakdown: see the plan document.

## 7. Open risks (carried into the plan as explicit stop-conditions / follow-ups)

1. **Depth-2 for the dual-Mega grid** — has a dedicated task (I7b-B Task 6) that records the exact branch-scoped context per diagnostic index and reuses `search.py::depth2_value_for_mega_context` with its existing signature. `search.py` is not modified and no new search algorithm is introduced.
2. **`OppResponse.weight` is unnormalized (`1.0` each) when `priors is None` on the legacy path.** I7b's active Mega/no-Mega mixture must use its real normalized twin weights consistently; omitted/empty eligibility must preserve the legacy numeric result exactly. Separate tests pin both contracts.
3. **`max_candidates` is never overridden by any live caller today** (§1.6) — I7b-A's cap-error test must use an explicit small `max_candidates` in its own fixture (there is no existing production call site exercising a tight cap to borrow a regression fixture from).
4. **Growth (Meganium's other signature move interaction) and Spicy Spray remain unsupported** per I7a's own fail-closed scope — I7b must not silently claim support for either; the same `UnsupportedMegaAbilityError`/`FAIL_CLOSED_ABILITIES` gate (`engine/mega_projection.py:13,24-25`) applies symmetrically when a foe's revealed/hypothesized Mega form has an unsupported ability, via the same exception type, not a new one.
5. **The `rain_offense` panel team's non-holdout status is unaffected by I7b** — no test or task in the plan reclassifies it; the plan's smoke design explicitly repeats ROADMAP's existing wording.
6. **Weather ordering is closed by binding spec Rev. 10.** Outside Trick Room, the faster activation is processed first; the later/slower weather setter overwrites it. Trick Room reverses activation order, and true speed ties remain two weighted permutations.
7. **[REV.2, new] `max_damage` is out of I7b's scope entirely** (finding 4) — if a future slice wants a foe-Mega-aware `max_damage` variant, that is a distinct semantic change to the "ignore incoming damage" baseline's own contract and needs its own separate design discussion, not a byproduct of I7b.

---

**REV. 4 DOCUMENTATION COMPLETE — Review abgeschlossen / I7b-A freigegeben — I7b-B/I7b-C remain review-gated.** The active architecture now preserves original hypothesis weights across branch replanning, delegates foe spread resolution correctly, batches one shared flush per world, proves cap retention separately from scored evidence, and pins the complete telemetry call graph.

**I7b-A IMPLEMENTATION AUTHORIZED (Rev. 4) — I7b-B/I7b-C REMAIN REVIEW-GATED**
