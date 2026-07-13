# Accuracy Branch-Cap / Ambiguous-Candidate De-Risk — Measurement Study Design

**Status:** approved by user, ready for implementation plan.

## 0. Why this exists

The accuracy-offline-gate (`docs/superpowers/specs/2026-07-13-accuracy-offline-gate-design.md`,
merged local `main` `1b9fdef`) ran Gate B for real over the full deduplicated 85-battle/944-decision
corpus at `SHOWDOWN_ACCURACY_BRANCH_CAP=4` (today's production default) and found a chosen-line
cap-hit rate of **12.9% (114/881), decisively above the gate's pinned 5% threshold — FAIL**
(`data/eval/accuracy-gate/gate-b-report.json`, `reports/2026-07-13-accuracy-offline-gate-verdict.md`).
That result is frozen and stays authoritative — this study does not recompute it.

`docs/ROADMAP.md`'s P0 item 6 (added when that verdict was recorded) opened two concrete follow-ups:

1. Compare `SHOWDOWN_ACCURACY_BRANCH_CAP ∈ {6, 8}` against the frozen cap=4 result, on the same
   corpus, same rules, both on cap-hit rate and real latency — before ever touching the 5% threshold
   or the production default.
2. Diagnose the 63/944 decisions Task 10's `_chosen_candidate` correctly excluded as
   ambiguous-`candidate_id` (a real, confirmed `decision.py` labeling gap) — root-cause them
   properly rather than let them quietly stay unexplained, and investigate whether a structural fix
   is feasible.

This document specs both, as one measurement study on **existing infrastructure** — no
`decision.py`/`evaluate.py`/`accuracy_gate_b.py`/`accuracy_gate_stats.py`/`accuracy_baseline_diff.py`
changes. A fallback-strategy redesign (replacing always-hit-on-cap with something less optimistic)
is explicitly **out of scope** for this spec — it requires new production logic, not a parameter
sweep, and is a separate, later slice.

## 1. Explicit non-goals (restated, not to be relitigated)

- **The cap=4 gate verdict is not recomputed.** `data/eval/accuracy-gate/gate-b-report.json`/`.md`
  remain the sole authoritative cap=4 result (114/881 = 12.9%, FAIL).
- No fallback-strategy (non-always-hit) implementation or comparison.
- No `SHOWDOWN_ACCURACY_MODE` default flip, no strength/winrate claim, no Depth-2 Stage 3 work.
- No change to the pinned 5% threshold, the bootstrap/Clopper-Pearson statistics, or the
  any-response/any-tie-order cap-hit rule.
- No production fix to `_label_ja`'s non-injective switch-slot labeling — this study diagnoses and
  reports feasibility only; the actual fix (if pursued) is a separate follow-up slice.
- No diagnostically-reconstructed telemetry is ever written back into the frozen cap=4 verdict or
  its artifacts.

## 2. Primary comparison — branch-cap sweep

### 2.1 Corpus and rule reuse

Same `room_raw_replay.py` extraction/dedup as every prior task in this lineage (Tasks 2/4/7/9/10/11
of the accuracy-offline-gate plan) — same manifest files, same `(seed_base, seed_index)` identity
key, same `G=85`. The frozen `data/eval/accuracy-gate/pre-refactor-baseline.jsonl` (accuracy-off,
cap-independent by construction — the off-path never consults `SHOWDOWN_ACCURACY_BRANCH_CAP` at
all) is read-only and cited by content hash, never re-run, never modified.

`accuracy_gate_b.py::run_gate_b`, `accuracy_gate_stats.py::verdict_for_cap_hit_rate`, and
`accuracy_baseline_diff.py::diff_against_baseline` are used **unmodified**. The only new code is
new scripts under `showdown_bot/scripts/` and a new eval module for the decision-key/diagnostic
logic described below.

### 2.2 `decision_id` — stable multi-field key, not bare `request_hash`

`request_hash` alone is not assumed to be a safe primary key across four different tables (frozen
off, cap4-auxiliary, cap6, cap8) built at different times by different runs. Every table in this
study keys on a composite `decision_id`:

```
(seed_base, seed_index_or_canonical_battle_id, request_hash, log_prefix_hash, side, rqid_or_turn)
```

The exact field sourcing (which of these already exist on `ExtractedDecision`/the dedup manifest
vs. need threading through at extraction time) is verified against the real current code as the
first implementation step — do not assume field names/paths without checking, per this project's
established discipline for every prior task in this lineage.

**Fail-closed uniqueness, asserted before any comparison runs**: before extracting/replaying,
assert `decision_id` is unique across all 944 extracted decisions. Before pairing any two tables
(off/cap4/cap6/cap8) by `decision_id`, assert every key present in one table that's expected in the
other actually is — a decision present in one table and silently absent from another is a fail-closed
error (raise, do not drop), not a silently-shrunk denominator. This mirrors the fail-closed pattern
already established in `room_raw_replay.py`'s `SeedIdentityConflictError` and
`accuracy_baseline_diff.py`'s request-hash collision guard (both from this same lineage).

### 2.3 Cap=4 auxiliary action-capture — validation-gated, explicitly not a new verdict

The existing `gate-b-report.json` stores only the 20 rows where cap4-on differed from off — not a
full 944-row "chosen action per decision" table, which is needed to compute cap6-vs-cap4 and
cap8-vs-cap4 diffs. Closing this gap requires **one narrowly-scoped auxiliary run**, explicitly
distinguished from a new gate run:

- Named and tagged throughout code/artifacts as **`cap4_auxiliary_action_capture`** — never referred
  to as a new cap=4 gate run or verdict anywhere in code, comments, or reports.
- Produces exactly one artifact: a full `{decision_id, chosen_action, score}` table for all 944
  decisions at `SHOWDOWN_ACCURACY_BRANCH_CAP=4`, `SHOWDOWN_ACCURACY_MODE=1` — modeled on
  `accuracy_baseline.py`'s existing `BaselineRow`/`freeze_baseline` shape (reused as a pattern, not
  by calling that function directly, since it's hard-wired to the frozen off-path file and must stay
  untouched).
- Written **only** under `data/eval/accuracy-cap-derisk/` — never touches
  `data/eval/accuracy-gate/`.

**Hard validation gate, must pass before this table is used for anything:** diff the auxiliary
table against the frozen off-path baseline (via `diff_against_baseline`, canonicalizing actions
through `normalize_choose` first) and confirm it **exactly reproduces** the frozen 20 cap4-vs-off
decision diffs already in `gate-b-report.json` — at minimum, the same 20 `decision_id`s and the
same normalized chosen actions. If a score comparison is also done, use `canonical_float`
representation (reused from `accuracy_baseline.py`) or a pre-pinned numeric tolerance, decided
before the run, not after seeing a mismatch.

**If this validation fails** (different diff count, different decision_ids, or different actions):
STOP, do not proceed to cap6/cap8 comparison, and root-cause the discrepancy before doing anything
else. Cap=6/8 must never be compared against an unvalidated cap=4 auxiliary table.

### 2.4 Cross-cap diffs via `diff_against_baseline` — directionality verified first, not assumed

Before relying on `diff_against_baseline` for cap6-vs-cap4/cap8-vs-cap4 (a symmetric-looking
function originally built for off-vs-on comparison), write a small isolated test proving it carries
no baked-in "first argument is always accuracy-off" semantic — that passing cap4's table as the
first argument and cap6's as the second produces `Regression.baseline_action`/`replay_action` in
the cap4→cap6 direction, correctly, and that the reporting code built on top of it labels this
correctly for a reader (not literally displaying "baseline"/"replay" column headers for a
cap-vs-cap comparison where that terminology is misleading). All actions are canonicalized via
`normalize_choose` before comparison in every direction.

Four diffs computed per cap-6/cap-8 pair: cap6-vs-cap4, cap6-vs-off, cap8-vs-cap4, cap8-vs-off (the
vs-off diffs are also available as a byproduct of each cap's own `run_gate_b` call — Section 2.5 —
and both sources should agree, a useful internal cross-check, not a required blocking gate).

### 2.5 Cap-hit verdicts — cap4 cited, cap6/8 freshly run, denominators always visible

- **Cap=4: cited only**, directly from `data/eval/accuracy-gate/gate-b-report.json` by content hash
  — 114/881 = 12.9%, FAIL. Never recomputed.
- **Cap=6, cap=8: each run once, fresh, on the full G=85/944-decision corpus** — full corpus, no
  sampling for this axis (matches spec §6 of the original gate design: full-corpus-only, no silent
  sub-sampling).
- Existing 5% threshold, game-clustered bootstrap (B=10,000, seed 20260713, per-game local
  decision-level rate — the Task-8-fixed version), zero-event Clopper-Pearson branch, and
  any-response/any-tie-order numerator rule: all reused **unchanged** via
  `verdict_for_cap_hit_rate`/`candidate_any_cap_hit`.
- **Per cap, report separately**: the number of ambiguous/unscorable (excluded) decisions at that
  cap, the resulting fully-paired denominator, and the resulting rate + CI/bound — never a bare
  cross-cap rate comparison without both denominators shown side by side. (Denominators may differ
  across caps if the ambiguous-candidate rate itself varies with cap — see Section 3.3.)

### 2.6 Latency — full-corpus-first, both trace modes, confound-controlled

Full 944-decision corpus for the latency axis too, for both `SHOWDOWN_ACCURACY_BRANCH_CAP ∈ {6, 8}`
(cap=4's latency figures are cited from the existing `2026-07-12-accuracy-slice-latency-gate.md`
single-board bench where directly comparable, and freshly measured on the real corpus alongside 6/8
for an apples-to-apples comparison — the existing report used one synthetic board, this study uses
real corpus boards). A short timing dry-run at the start estimates total runtime (the existing full
trace-based Gate B run took ~92s for one cap-comparison pass, making a full-corpus pass for both
trace modes × 2 new caps look tractable) — the dry-run informs planning, it does not by itself
trigger sampling; sampling only happens if the dry-run shows genuine infeasibility, and if it does,
it happens at the **game level** with a pre-pinned seed (drawing whole games, measuring every valid
decision within drawn games), explicitly labeled as a subsample in the report, never a silent
truncation.

**Confound controls, required:**
- Warm the persistent calc backend once, in a controlled fashion, before any timed measurement.
- Rotate/balance cap order per game or block deterministically — never always run 4→6→8 in the same
  sequence for every game, to avoid confounding cap effects with warm-up/ordering/backend-state
  effects.
- Trace-none (production-realistic, no `trace=` kwarg) and trace-enabled
  (`trace=DecisionTrace()`, what Gate B itself uses) are measured and reported **separately** — two
  independent latency series per cap, never merged.
- Report p50/p95/max **plus** the count of decisions actually measured and any exceptions
  encountered during the latency pass, for every series.

### 2.7 Report contents (per cap: 6, 8; cap=4 cited throughout as the reference row)

- Cap-hit numerator/denominator/rate + bootstrap-or-Clopper-Pearson detail + PASS/INCONCLUSIVE/FAIL.
- Decision diffs vs cap=4 and vs accuracy-off (both directions correctly labeled per §2.4).
- Leaf-count/event-count distributions and the fraction of incomplete (`events_complete=False`)
  event lists.
- Tera-diffs isolated as their own subset, not folded into the general diff count.
- Latency: p50/p95/max, trace-none and trace-enabled separately, per §2.6.
- No strength or winrate claim anywhere in this report — pure measurement, matching the existing
  gate's own framing, restated explicitly at the top of the report (same convention as
  `reports/2026-07-13-accuracy-offline-gate-verdict.md`'s boxed disclaimer).

## 3. Ambiguous-candidate diagnostic

### 3.1 Two-tier classification — exclusive primary cause, non-exclusive companion flags

A single "root cause" bucket per case loses real, co-occurring mechanisms (a score tie can
influence *which* colliding candidate becomes `best_ja` and what rank it lands at, without itself
*creating* the label collision that made resolution ambiguous in the first place — both can be true
of the same case). The classification is therefore two-tier:

**A. Primary resolution cause — exactly one per case:**

1. `label_collision` — at least two structurally different `JointAction`s render the same
   `_label_ja`/candidate-id string. Sub-typed, not assumed to be switch-only:
   `switch_target_omitted` (the confirmed dominant type from Task 10's investigation) plus whatever
   other collision types are actually observed during classification (do not force everything into
   the switch bucket without checking).
2. `chosen_candidate_missing` — the structurally-actual chosen `JointAction` is genuinely absent
   from the candidate set the trace considered at all (zero matches, not ≥2) — with a required
   sub-reason: top-K truncation, filtering, or some other loss. Checked via direct structural
   candidate comparison, not assumed to be co-equal in frequency with `label_collision` just because
   both are "ambiguity" — expected rare/absent for the historical 63 (already confirmed as ≥2-match
   cases), verified rather than assumed.
3. `invalid_or_nonreconstructable_request` — the request/state can't be consistently reconstructed
   during diagnostic replay.
4. `other_pipeline_error` — only when none of the above fit, with a mandatory concrete rationale per
   case (never a bare "other").

**B. Companion flags — zero or more per case, non-exclusive:**

`exact_score_tie`, `pick_best_vs_sorted_rank_mismatch`, `chosen_rank_nonzero`, `top_k_truncated`,
`multiple_structurally_equal_candidates`, `distinct_switch_targets_same_label`,
`distinct_tera_state_same_label`, `distinct_move_or_target_same_label`,
`candidate_absent_in_other_mode_top_k`, plus any further flags concretely observed and named during
classification (the list above is a floor, not a ceiling — do not force a newly-observed mechanism
into an existing flag if it's genuinely distinct).

This lets the report say, honestly, e.g. "Primary cause `label_collision/switch_target_omitted`;
also `exact_score_tie` and `pick_best_vs_sorted_rank_mismatch`" rather than losing a real, co-occurring
mechanism to a forced single-bucket rule.

### 3.2 Fix-feasibility — three variants evaluated separately, five questions answered explicitly

**Variant 1 — object identity within the same decision call.** Likely locally unique within one
`_choose_best` invocation, but not serializable and not stable across separate off/on runs (a fresh
`JointAction` object is constructed independently each call). Only viable as a short-lived internal
mapping, not a persisted key.

**Variant 2 — dataclass/object equality (`JointAction.__eq__`).** Investigate whether the existing
`__eq__` (if `JointAction` even defines one, vs. relying on default identity) actually covers every
semantically relevant field — switch target, move target, terastallize flag — before assuming
equality is a safe substitute for identity. Do not assume this without checking the actual
dataclass definition.

**Variant 3 — a stable structural candidate key (preferred long-term direction).** Either a
canonical serialization of every decision-relevant `JointAction` field, or a key assigned once at
enumeration time and carried through scoring/ranking/trace construction unchanged. Under this
variant, `_label_ja` reverts to being a purely human-readable display string, no longer
double-duty'd as a uniqueness-bearing identifier — which is the actual root defect this whole
ambiguity class stems from.

**Questions the diagnostic must answer explicitly, not leave implicit:**

1. Can `best_ja` be traced directly back to its originating `scored`/`items` entry within the same
   call, without going through `_label_ja` at all?
2. Does that traceability survive any copy/reconstruction across K-world sampling, single-world, and
   Depth-2 code paths, or is it lost somewhere in one of them?
3. Is a canonical structural key stable across accuracy off vs on (same `JointAction`, scored twice
   under different `SHOWDOWN_ACCURACY_MODE` states — must resolve to the same key both times)?
4. Which exact fields must the key include so that switch-target, move-target, and Tera variants
   never collide?
5. Could a future fix-slice generate the chosen candidate's telemetry directly, without raising
   `TOP_K_TRACE_CANDIDATES` globally (i.e., without changing the shared trace-population budget for
   every other consumer of `CandidateTrace`)?

This is an investigation and report, not a `decision.py` code change — implementing whichever
variant looks best is explicitly a separate, later fix-slice.

### 3.3 Scope: historical 63 (cap=4) plus the same diagnostic applied to cap=6/cap=8

The same classification code runs against every ambiguous/excluded case surfaced at **all three**
caps (the historical 63 at cap=4, and whatever set of cases cap=6/cap=8 produce during their own
Section 2.5 runs) — not hand-built once for the historical 63 and left unapplied elsewhere. Per
cap, report:

- Count of ambiguous cases.
- Overlap with the historical 63, by `decision_id` — which cases recur across caps, which are new,
  which disappeared (a case ambiguous at cap=4 might resolve cleanly at cap=6 if the underlying
  candidate set shifts, and vice versa; report this rather than assume stability across caps).
- Primary causes and companion flags per case, aggregated per cap.
- Conservative bounds (per §2.5, unchanged) — the ambiguous-case count already feeds directly into
  each cap's own reported denominator.

### 3.4 Non-contamination rule

No diagnostically-reconstructed telemetry (e.g., a manually-resolved "true" chosen candidate for an
ambiguous case) is ever written back into the frozen cap=4 verdict or its artifacts, or silently
folded into any cap's own headline cap-hit rate. A full sensitivity analysis (e.g., "what would the
rate be if all N ambiguous cases resolved to X") may be reported **separately and explicitly
labeled as a sensitivity analysis**, cleanly distinguished from the frozen gate result, following
the same pattern already used for the exclusion-bias-bound sentence in the original gate's closeout
report.

## 4. Deliverables / file layout

- `data/eval/accuracy-cap-derisk/` (new directory, everything from this study lives here):
  - `cap4-auxiliary-action-capture.json` (§2.3, explicitly tagged, validation-gated)
  - `cap6-report.json` / `cap6-report.md`, `cap8-report.json` / `cap8-report.md` (§2.5–2.7)
  - `ambiguous-candidate-diagnostic.json` / `.md` (§3, covering cap4/6/8)
- `reports/2026-07-13-accuracy-cap-derisk-verdict.md` (closeout, cites cap=4 from
  `data/eval/accuracy-gate/` by content hash, never duplicates or restates it as newly computed)
- `showdown_bot/scripts/` — new driver script(s) for the cap sweep and the diagnostic; exact
  script/module boundaries decided during plan-writing, following this codebase's established
  pattern of one focused script per distinct real-run responsibility (mirrors
  `run_accuracy_gate_b.py`/`render_accuracy_gate_reports.py`'s split).
- `data/eval/accuracy-gate/` — **read-only** for this entire study. Nothing in this directory is
  created, modified, or regenerated by any task in this plan.

## 5. Testing approach

TDD throughout, matching every prior task in this lineage: unit tests for `decision_id` uniqueness
assertion and fail-closed pairing, a dedicated test proving `diff_against_baseline`'s directionality
(§2.4) before it's relied on for cap-vs-cap comparisons, a test proving the cap4-auxiliary
validation gate actually catches a deliberately-broken reproduction (not just that it passes on
real data), and unit tests for the two-tier classification scheme against hand-built
label-collision/missing-candidate/tie fixtures. Real-corpus runs (§2.5, §2.6, §3.3) are integration
checks with real numbers reported honestly, same discipline as the original gate's Tasks 9–11.

## 6. Open items deferred to the implementation plan, not resolved here

- Exact field sourcing for `decision_id`'s components against the real current `ExtractedDecision`/
  dedup-manifest code (verify, don't assume, per §2.2).
- Exact script/module boundaries under `showdown_bot/scripts/`.
- Whether `JointAction` already defines `__eq__` and what it covers (§3.2, Variant 2) — verified
  during implementation, not assumed here.
