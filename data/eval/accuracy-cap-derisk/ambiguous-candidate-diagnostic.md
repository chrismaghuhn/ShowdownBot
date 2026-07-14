# Ambiguous-candidate diagnostic + fix-feasibility investigation (spec Sec.3.2 / Sec.3.3)

Companion write-up to `ambiguous-candidate-diagnostic.json` (produced by
`showdown_bot/scripts/run_ambiguous_candidate_diagnostic.py`). Sec.3.3 is the real
classification run (numbers below); Sec.3.2 is the hand-written fix-feasibility investigation,
which re-verifies the relevant `JointAction`/`SlotAction`/`DecisionTrace`/`decision.py` facts
directly against the current source (commit at time of writing:
`26c955882ae86d767186417f56af02ff95a8abd1`) rather than copying the plan's prose.

This is an **investigation only** — no change was made to `decision.py`, `accuracy_cap_derisk.py`,
or the frozen `data/eval/accuracy-gate/`.

## Sec.3.3 — real classification results

Each of the 63 historical Gate-B exceptions (identical set of 63 in `gate-b-report.json`,
`cap6-report.json`, and `cap8-report.json`) was joined to a `decision_id` via the manifest,
re-extracted from the corpus by full per-file `SeedIdentity` + `compute_decision_id`, and
re-run live (accuracy ON, branch cap = 4/6/8) to obtain a fresh `DecisionTrace` to classify.

| cap  | classified | primary_cause                | label_collision_subtype        |
|------|-----------:|------------------------------|--------------------------------|
| cap4 |         63 | `label_collision` ×63        | `switch_target_omitted` ×63    |
| cap6 |         63 | `label_collision` ×63        | `switch_target_omitted` ×63    |
| cap8 |         63 | `label_collision` ×63        | `switch_target_omitted` ×63    |

Companion flags (all 63 at every cap): `collision_spans_nonzero_rank`,
`distinct_switch_targets_same_label`, `exact_score_tie`, `multiple_structurally_equal_candidates`.

**Overlap by `decision_id` across caps:** `all_three = 63`, `cap4_only = cap6_only = cap8_only = 0`.

Interpretation: the exclusion set is **invariant to the accuracy branch cap** — the same 63
decisions collide at 4, 6, and 8. This is expected and confirmatory: the branch cap only bounds
accuracy *telemetry*, never which joint actions are enumerated or how they are labeled, so a
label collision is a purely structural property. All 63 are the **switch-slot label
non-injectivity** defect (see Sec.3.2 below), not a cap artifact.

**`other_pipeline_error` / `chosen_candidate_missing`: zero of each.** Corrections 1/3's routing
guards (which would have diverted any decision whose original exception was *not* a
`_chosen_candidate` ambiguity/no-match `RuntimeError`, or whose live re-run failed to reproduce as
a genuine ≥2-match ambiguity) were exercised as guards but never fired — every one of the 63
original exceptions is a `RuntimeError: ambiguous chosen_candidate_id=…` and every one reproduced
as ≥2 structural matches on re-run. So the 63-exception population is **homogeneous**: there is no
second, unrelated defect hiding in it. No separate follow-up defect is flagged from this run.

## Sec.3.2 — re-verified API facts (checked directly, not copied)

- **`SlotAction`** (`src/showdown_bot/models/actions.py:7-13`), a frozen dataclass, fields:
  `kind: Literal["move","switch","pass"]`, `move_index: int|None` (1-based), `target: int|None`
  (1/2 foe, −1 ally, −2 self), `terastallize: bool`, `target_ident: str|None` (switch bench ident
  suffix). Frozen ⇒ it has value-based `__eq__`/`__hash__`.
- **`JointAction`** (`src/showdown_bot/battle/actions.py:16-38`): `slot0`, `slot1`, plus
  `as_pair()` and `with_tera(slot_index)`. `with_tera` returns
  `replace(self, slotN=replace(self.slotN, terastallize=True))` — i.e. a **new** object
  (`dataclasses.replace`), not an in-place mutation.
- **`enumerate_my_actions(req, *, allow_double_switch, moved_since_switch)`**
  (`src/showdown_bot/battle/actions.py:90-132`) enumerates the candidate space from `req` **only**
  — no accuracy state. Its docstring line 99 states "Tera stripped (overlay only)": **the
  enumerated space carries `terastallize=False` throughout; Tera is applied later as an overlay.**
- **`_label_ja(req, ja)`** (`src/showdown_bot/battle/decision.py:233-246`): for a **move** slot it
  renders `name(->target)(  tera)` (so `move_index`, `target`, `terastallize` are all reflected);
  for **every non-move slot** (switch / pass) it renders the bare `sa.kind` string ("switch" /
  "pass"), **dropping `target_ident` entirely**. This is the root cause: two joint actions that
  switch the same slot to *different* benched mons (same other slot) render byte-identical labels,
  e.g. both `"(Knock Off->1, switch)"`.
- **`DecisionTrace`** (`src/showdown_bot/battle/decision_trace.py:116-135`) stores
  `chosen_candidate_id: str|None` (a `_label_ja` **string**) — and has **no**
  `chosen_joint_action` / structural-key field. Each `CandidateTrace`
  (`decision_trace.py:103-112`) does carry `joint_action: Any` (the real object), but only for the
  exported top-K, rank-sorted candidates.
- **Trace-population block** (`src/showdown_bot/battle/decision.py:679-702`, inside the
  `if trace is not None:` guard opened at line 587): `scored` (679-683) is built from `items`
  (the **pre-Tera** candidate set); each `CandidateTrace` stores `candidate_id=_label_ja(req, ja)`
  and `joint_action=ja` (line 688); and `trace.chosen_candidate_id = _label_ja(req, best_ja)`
  (line 699), where `best_ja` is the **post-`_maybe_tera`** object.
- **`_maybe_tera`** (`src/showdown_bot/battle/decision.py:536`, def at 832-848) reassigns
  `best_ja` and, when it spends Tera, returns `best_ja.with_tera(i)` — a fresh object that differs
  from every pre-Tera candidate by `terastallize=True` on one slot. This is the **overlay-timing
  mismatch**: the chosen label can carry a ` tera` suffix that no candidate label has, which is
  why `_chosen_candidate` (`src/showdown_bot/eval/accuracy_gate_b.py:99-145`) needs a tera-stripped
  fallback after the exact match fails.

The offline resolver `_chosen_candidate` (`accuracy_gate_b.py:99-145`) therefore has exactly the
two documented failure modes, both string-based: (1) `len(exact) > 1` → `RuntimeError: ambiguous
chosen_candidate_id=…` (the switch-target collision — **all 63 cases here**); (2) exact-match 0 →
tera-stripped fallback → `RuntimeError: no candidate matches …` if that isn't exactly 1 (0 in this
corpus).

## Sec.3.2 — the five spec questions

**Q1. Can `best_ja` be traced back to its originating `scored`/`items` entry within the same
call, without `_label_ja`?**
Yes, in principle — but with one real caveat. At the trace-population point (`decision.py:699`)
`best_ja` is a live object, and `scored`/`items` hold the same `JointAction` instances that were
enumerated (`plans.items()` at 526, or `full.items()` at 476-477). So a `is`/`==` match against
each `scored` entry would identify the origin without `_label_ja`. **Caveat:** `best_ja` is
reassigned by `_maybe_tera` at line 536 *before* line 699. When Tera is spent, the reassigned
`best_ja` is a `with_tera` copy — not `is` (nor `==`) to any pre-Tera `scored` entry (they differ
by `terastallize`). So identity/equality matching succeeds for the non-Tera path but fails for
exactly the Tera-overlay decisions — the same decisions that force `_chosen_candidate`'s
`_strip_tera` fallback today. Traceability is real; the Tera overlay is the one thing any resolver
must still handle.

**Q2. Does that traceability survive the K-world / single-world / Depth-2 code paths?**
Yes — the candidate `JointAction` objects flow through all three paths **identity-preserving**, and
none of the three reconstructs them:
- Single-world (`decision.py:526`): `items = [(ja, score_plan(plan)) for ja, plan in plans.items()]`
  — `ja` keys are the `plans` keys, unchanged.
- K-world / Depth-2 wrap (`decision.py:461, 476-477`): `full = {ja: … for ja, plan in plans.items()}`
  then `items = [(ja, …) for ja, vec in full.items()]` — again the same `plans` keys. The depth-2
  refinement mutates `scores_vec[i]` (the score) in place at line 524; it never touches the `ja`
  object.
- `pick_best` (`decision.py:527`) returns one of the `items` `ja` — the same object.

The **only** identity break in any path is the shared `_maybe_tera` overlay (Q1), which is common
to all three, not a path-specific deep-copy/reconstruction. (Aside: the depth-2 wrap deliberately
omits accuracy kwargs from `depth2_value` — `decision.py:499-506` — a known score-methodology gap,
but it concerns scores, not `JointAction` identity, so it does not affect traceability.)

**Q3. Is a canonical structural key stable across accuracy off vs on?**
Yes, by construction. A structural key over `(kind, move_index, target, target_ident,
terastallize)` per slot contains **no accuracy-mode-dependent field**; `SlotAction` is a pure frozen
action record, and `enumerate_my_actions` (`actions.py:90`) derives the candidate space from `req`
alone. Accuracy mode changes only score telemetry (accuracy events, branch-cap hits), never which
joint actions exist or their fields. This is also borne out empirically by Sec.3.3: the identical
63 decisions collide at cap 4/6/8 (`all_three=63`, `*_only=0`).

**Q4. Which fields must the key include so switch-target / move-target / Tera variants never
collide?**
Per slot: `kind`, `move_index`, `target`, **`target_ident`**, and `terastallize` — the first four
included raw, `terastallize` handled **Tera-aware, not raw**. Rationale grounded in the verified
fields:
- `target_ident` is the field `_label_ja` drops for switch slots (`decision.py:244-245`); including
  it is the fix for `switch_target_omitted` (the *sole* subtype across all 63 cases).
- `move_index` + `target` separate different moves and different move targets.
- `terastallize` must NOT be a raw key component compared post-overlay, because the chosen
  `best_ja` may be a `with_tera` copy while its enumerated origin has `terastallize=False` (Q1). If
  compared raw, the chosen key matches 0 candidate keys — the exact situation the current
  `_strip_tera` fallback bridges. It must instead be resolved either before `_maybe_tera` runs (no
  suffix yet) or via a Tera-normalizing comparison.

**Q5. Could a future fix generate the chosen candidate's telemetry without raising
`TOP_K_TRACE_CANDIDATES` globally?**
Yes. The problem is **identification**, not **capacity**. The chosen candidate is `pick_best`'s
argmax (`decision.py:527`), i.e. effectively rank 0 after the `-agg` sort at line 683 — it is
always already inside the top-K (`TOP_K_TRACE_CANDIDATES = 6`, `decision.py:34`), which is why this
corpus produced **zero** `chosen_candidate_missing` / top-K-truncation cases. What fails is telling
the chosen one apart from its identically-*labeled* siblings. Resolving via a structural key at the
**same point `_label_ja` already runs** (line 699 / the trace-population block), or storing
`best_ja` (or its key) into a new `DecisionTrace.chosen_joint_action`-style field there, makes the
offline lookup injective — exactly-one always — **without** needing more candidates in the top-K.
Raising `TOP_K_TRACE_CANDIDATES` globally would not address the identification ambiguity at all
(it would just add more same-labeled rows) and would inflate every decision's telemetry payload;
it is neither necessary nor sufficient.

## Sec.3.2 — the three fix variants: verdicts

1. **Object identity (`is`)** — *short-lived only.* Correctly identifies the origin within a single
   `_choose_best` call for the non-Tera path, but breaks the instant `best_ja` becomes a
   `with_tera` copy (`decision.py:536`), and is inherently process-local — it cannot be serialized
   into an offline report at all. Usable only as an *in-call* resolution performed **before** the
   Tera overlay; not a durable telemetry key.

2. **Object equality (`==`)** — *solves the switch collision, needs a Tera-aware wrapper.*
   `JointAction`/`SlotAction` are frozen dataclasses, so `==` is structural and immediately
   distinguishes the two same-labeled switch candidates (different `target_ident` ⇒ not equal),
   killing the `switch_target_omitted` collision that is 100% of this run's cases. It still fails
   the Tera-overlay mismatch (post-Tera chosen `!=` pre-Tera candidate), so it requires a
   Tera-normalizing comparison/wrapper to be complete.

3. **Structural key** — *preferred.* A per-slot tuple `(kind, move_index, target, target_ident,
   terastallize)` (Tera handled per Q4) is injective over the enumerated space, **serializable**
   into the offline JSON report, and provably **accuracy-invariant** (Q3). It needs one of: a new
   `DecisionTrace.chosen_joint_action` / `chosen_candidate_key` field (there is none today —
   `decision_trace.py:116-135`), or a key assigned at enumeration and carried on both the chosen
   pointer and each `CandidateTrace`. This is the recommended direction: it dissolves both the
   switch-target collision and the Tera-overlay mismatch, and (per Q5) does so at the existing
   resolution point without touching `TOP_K_TRACE_CANDIDATES`.

**Recommendation:** pursue variant 3 (structural key + a `chosen_joint_action`-style trace field),
resolving the chosen candidate at/alongside the current `_label_ja` call in the trace-population
block, with the `terastallize` dimension normalized against the pre-overlay enumerated space. This
is a `decision.py`/`decision_trace.py` change and is explicitly **out of scope for this
measurement task** — recorded here as the investigation's conclusion, not implemented.
