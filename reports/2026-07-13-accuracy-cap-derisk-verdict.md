# Accuracy Branch-Cap De-Risk — Task 12 closeout (final)

**Date:** 2026-07-13 · **Worktree:** `.claude/worktrees/accuracy-cap-derisk` · **Scope:** Task 12
(final) of the 12-task implementation plan
(`docs/superpowers/plans/2026-07-13-accuracy-cap-derisk.md`) — synthesize all 11 prior tasks' real
findings into reports, run the full test suite as a final regression gate, update the roadmap.
Design spec: `docs/superpowers/specs/2026-07-13-accuracy-cap-derisk-design.md`. Parent study this
plan de-risks: the accuracy-offline-gate plan's FAIL verdict at
`SHOWDOWN_ACCURACY_BRANCH_CAP=4` (`reports/2026-07-13-accuracy-offline-gate-verdict.md`).

## The one thing this report is not allowed to bury

> **No default-on decision, no strength claim, and no Depth-2 Stage 3 work follows from this
> report alone.** This study exists to produce numbers for those downstream decisions to be
> *reviewed against* — it does not make any of them itself, and nothing below should be read as
> making one. This restates, for this new and separate report, the exact same requirement the
> parent accuracy-offline-gate closeout report already carried (`reports/2026-07-13-accuracy-
> offline-gate-verdict.md`: *"No default-on decision, no strength claim, and no Depth-2 Stage 3
> work follows from this gate alone"*) — a future reader could encounter this report on its own,
> without ever having read the parent report, so the requirement is restated here in full rather
> than assumed inherited. Anyone reading only this report should walk away with numbers, not a
> decision.

## Glossary: what `SHOWDOWN_ACCURACY_BRANCH_CAP` and "cap-hit" mean (read this before any table below)

This report claims to stand on its own for a reader who has not read the parent
accuracy-offline-gate report, so the two terms every table below depends on are defined here
explicitly rather than assumed known. `SHOWDOWN_ACCURACY_BRANCH_CAP` bounds how many
`resolve_turn` expansion calls (`battle/evaluate.py`'s `resolve_turn_branches`) any single scored
candidate line may perform while resolving accuracy-branching (hit vs. miss) for the sub-100%-
accuracy moves in that line, before it must stop branching and fall back to the legacy always-hit
assumption for the rest of that line's event tree. Each additional simultaneous sub-100%-accuracy
event in a line roughly doubles the branching work needed to resolve it fully (a line with *k*
simultaneous accuracy<100 events needs up to 2^(k+1)−1 total `resolve_turn` calls to fully resolve
every hit/miss combination); the cap exists so that a pathological line with several such events
can't blow the decision-time latency budget. A decision is a **"cap-hit"** when at least one of its
scored candidate lines — specifically the *chosen* candidate, for the numerators below — actually
exhausted this budget and had to fall back to always-hit for part of its own event tree, meaning
that candidate's accuracy-aware score (and therefore its EV) may be less precise than a fully
resolved line would have produced. The **cap-hit rate** in every table below is the fraction of
real replayed decisions where this happened on the chosen candidate: a high rate means the
accuracy machinery frequently falls back to the always-hit behavior it exists to replace
(undermining its own purpose on those decisions); a low rate means branches are being fully
resolved almost every time.

## What this task did

1. Read `showdown_bot/scripts/render_accuracy_gate_reports.py`,
   `reports/2026-07-13-accuracy-offline-gate-verdict.md`, and
   `reports/2026-07-12-accuracy-slice-latency-gate.md` in full, and `docs/ROADMAP.md`'s existing P0
   item 6, per this task's own required-reading list.
2. Independently re-verified every real number carried into this report against the actual
   committed JSON artifacts from Tasks 4–11 (not trusted from any prior summary) — see
   "Independent verification" below. No discrepancy was found against the plan's own carried-over
   context; every number below is cited from a source file, not restated from memory.
3. Wrote `showdown_bot/scripts/render_cap_derisk_reports.py` (mirrors
   `render_accuracy_gate_reports.py`'s `build_report_object`/`render_markdown` split, itself
   mirroring `eval/decision_diff_report.py`'s pattern) and ran it to produce real
   `data/eval/accuracy-cap-derisk/cap6-report.md` / `cap8-report.md` from Task 7's
   `cap{6,8}-report.json`, Task 8's `cross-cap-diffs.json`, and Task 9's `latency-results.json`.
4. Wrote this closeout report.
5. Ran the full test suite as the final regression gate (see "Verification performed" below).
6. Updated `docs/ROADMAP.md`'s existing P0 item 6 (extended, not replaced or duplicated).
7. Confirmed `data/eval/accuracy-gate/` has zero git diff across this entire plan's execution (see
   "Non-contamination confirmation" below).
8. Committed.

## Independent verification performed for this report

Every number cited below was read directly from its source JSON/MD file in this worktree, not
copied from the plan's carried-over context summary:

- `data/eval/accuracy-cap-derisk/decision-id-manifest.jsonl`: **944 rows, 944 unique
  `decision_id` values** (Task 4).
- `data/eval/accuracy-cap-derisk/{cap4_auxiliary,cap6,cap8}-action-capture.jsonl`: **944 rows
  each**, `candidate_resolution_status` breakdown **identical across all three**:
  `{"exact": 880, "ambiguous_label": 63, "tera_stripped": 1}` (Task 5).
- `data/eval/accuracy-cap-derisk/cap4-auxiliary-validation-report.json`: `stage1_passed=true`,
  `stage1_raw_diff_count=20`, `stage2_semantic_diff_count=20`, `diffs_among_historical_63=0`
  (Task 6 — the hard checkpoint).
- `data/eval/accuracy-cap-derisk/cap6-report.json` / `cap8-report.json`: both
  `cap_hit_verdict="PASS"`, `cap_hit_verdict_detail={numerator: 6, n_decisions: 881, g: 85,
  point_estimate: 0.00681044267877412, bootstrap_ci_upper: 0.013713606654783125}` — **numerically
  identical between cap=6 and cap=8**, and both `exception_count=63` (Task 7).
- `data/eval/accuracy-gate/gate-b-report.json` (the frozen cap=4 verdict): `cap_hit_verdict="FAIL"`,
  `cap_hit_verdict_detail={numerator: 114, n_decisions: 881, point_estimate: 0.12939841089670828,
  bootstrap_ci_upper: 0.16133090765443706}`.
- `data/eval/accuracy-cap-derisk/cross-cap-diffs.json`: `cap4 -> cap6`
  `{action_changed_count: 0, score_changed_count: 115, total: 944}`; `cap4 -> cap8`
  `{action_changed_count: 0, score_changed_count: 118, total: 944}`; `off -> cap6` and
  `off -> cap8` both `{action_changed_count: 20, total: 944}` with the **exact same 20
  `decision_id` values** in both rows' lists (Task 8).
- `data/eval/accuracy-cap-derisk/latency-results.json`: `counterbalancing.cap_position_counts =
  {"4": [29,28,28], "6": [28,29,28], "8": [28,28,29]}`, `trace_order_counts =
  {"trace_enabled_first": 127, "trace_none_first": 128}`; all 6 series `n=944`,
  `expected_denominator=944`, `exceptions=0` (Task 9 — see the latency table below for the actual
  p50/p95/max figures).
- `data/eval/accuracy-cap-derisk/ambiguous-candidate-diagnostic.json`: `overlap.all_three=63`,
  `cap4_only=cap6_only=cap8_only=0`; `per_cap.{cap4,cap6,cap8}.count=63` each, with every one of
  the 63 cases at every cap classified `primary_cause="label_collision"`,
  `label_collision_subtype="switch_target_omitted"` — **zero** `other_pipeline_error`, **zero**
  `chosen_candidate_missing` at any cap (Task 11).

**No discrepancy was found** between these independently-re-read numbers and the plan's own
carried-over context summary — every figure matches exactly.

## Cap=4 — the frozen gate verdict, unchanged (cited, not re-run)

Cited from `data/eval/accuracy-gate/gate-b-report.json` (sha256
`cfcffd1d20ac1d7fd3446b465d1058c2ff3aa533140af14cc901af3baeb9ee86`, committed at
`a739967e1a8f9762d1784c087fa5f059ab2192a5`):

| field | value |
|---|---|
| numerator | 114 |
| denominator (`n_decisions_compared`) | 881 |
| point estimate | 0.129398 (≈12.9%) |
| bootstrap upper bound (95%, game-clustered) | 0.161331 (≈16.1%) |
| PASS threshold | 0.05 (5%) |
| **verdict** | **FAIL** |

**This verdict is unchanged by this entire plan.** No task in this plan ever re-runs, regenerates,
or modifies `data/eval/accuracy-gate/gate-b-report.json` or any other file under
`data/eval/accuracy-gate/` — the cap=4 FAIL result stands exactly as the accuracy-offline-gate plan
left it.

## Cap=6 / cap=8 — real cap-hit rates and verdicts (Task 7, this plan)

| cap | numerator | denominator | point estimate | bootstrap CI upper | g | verdict |
|---|---:|---:|---:|---:|---:|---|
| 4 (reference, frozen) | 114 | 881 | 12.94% | 16.13% | 85 | **FAIL** |
| 6 | 6 | 881 | 0.68% | 1.37% | 85 | **PASS** |
| 8 | 6 | 881 | 0.68% | 1.37% | 85 | **PASS** |

**Both cap=6 and cap=8 clear the 5% threshold, decisively** — both the point estimate (0.68%) and
the bootstrap upper bound (1.37%) sit far below 5%, not just barely under it. **Cap=6 and cap=8 are
numerically identical** on this corpus: same numerator (6), same point estimate, same bootstrap
upper bound. Raising the branch cap from 6 to 8 changed **zero** additional decisions' cap-hit
status here — whatever headroom cap=6 buys over cap=4, cap=8 buys nothing further on top of it, on
this real 85-battle/944-decision corpus.

**Action-changed counts, both directions, real (Task 8):**

- `cap4 -> cap6`: **0/944 action changes**, but `score_changed_count=115` — real score movement
  (the additional accuracy fidelity does change scores) without ever flipping which candidate wins.
- `cap4 -> cap8`: **0/944 action changes**, `score_changed_count=118`.
- `off -> cap6` and `off -> cap8`: **20/944 action changes each**, and these are the exact same 20
  `decision_id`s in both — i.e. raising the cap from 6 to 8 does not change which decisions diverge
  from the always-hit baseline either. The score axis is explicitly skipped for this off-vs-cap
  comparison (`legacy_frozen_score` is not proven equivalent to `top_rank_score`/
  `chosen_candidate_score` — every row states this as its own `score_incompatible_reason`); the
  action axis is not skipped and is the real, load-bearing number.
- **Tera-diffs, isolated as their own subset (spec §2.7), not folded into the general diff count:
  0/20 at both cap=6 and cap=8** (of each cap's own 20 off-vs-on diffs, zero have `tera_changed=
  True` — none of the real accuracy-driven divergences on this corpus involved a Tera-decision
  flip, at either cap).

**Interpretation, stated plainly and not softened:** at this real corpus's actual decision mix,
moving the branch cap from 4 to 6 (or 8) resolves the cap-hit rate from a decisive FAIL (12.9%) to
a decisive PASS (0.68%), while changing **zero** chosen actions relative to cap=4 — the additional
accuracy-branch budget only refines *scores* on this corpus, it never flips a winner. This is a
real, reportable finding about this specific corpus's cap-hit behavior. It is **not** a
recommendation to change the default — see the boxed disclaimer above and "Explicit scope
confirmation" below.

## Cap=6 / cap=8 — real latency figures (Task 9, this plan) vs. the existing scaled gate

The accuracy-hit-probability slice's own latency-gate benchmark
(`reports/2026-07-12-accuracy-slice-latency-gate.md`) measured **one fixed, deliberately
accuracy-branching-heavy hand-built board** with the production `persistent` calc backend, and
applied the depth-2 precedent's rule: p95, scaled ×5 for Kaggle-board weight, must stay under
1000ms. Its own finding, cited directly (not re-derived): **cap=4 PASS (p95×5 ≈ 871.5–905.5ms
across two runs, ~10–13% margin) but cap=6 and cap=8 both FAIL (p95×5 ≈ 1015–1075ms, over the
1000ms pin)** on that one board, with cap=6 and cap=8 buying "almost nothing extra" fidelity-wise
(identical branch-cap-hit rate on that board, 6.9% both).

This study's real numbers, measured on the full 944-decision corpus (not one hand-built board),
both trace modes, with verified counterbalancing (`cap_position_counts` /
`trace_order_counts` above — cap order and trace order are not confounded with warm-up/backend
state):

| series | p50 (ms) | p95 (ms) | max (ms) | p95×5 (Kaggle est.) | vs. 1000ms gate |
|---|---:|---:|---:|---:|---|
| cap4_trace_none | 38.3 | 140.1 | 198.9 | 700.6 | PASS (29.9% margin) |
| cap4_trace_enabled | 45.8 | 151.1 | 258.8 | 755.4 | PASS (24.5% margin) |
| cap6_trace_none | 39.3 | 173.0 | 278.3 | 865.2 | PASS (13.5% margin) |
| cap6_trace_enabled | 46.9 | 183.9 | 258.3 | 919.4 | PASS (8.1% margin) |
| cap8_trace_none | 39.3 | 179.0 | 308.0 | 894.8 | PASS (10.5% margin) |
| cap8_trace_enabled | 47.0 | 193.6 | 276.1 | 968.2 | PASS (3.2% margin — thin) |

**This study's real-corpus numbers DISAGREE with the prior single-board bench's cap=6/cap=8 FAIL
finding — reported honestly, not reconciled away.** At the same ×5 scaling rule, all six series
here (including both cap=6 and cap=8, both trace modes) stay under the 1000ms pin, whereas the
prior single-board bench found cap=6/cap=8 exceeding it. The direction of the underlying effect is
consistent between the two studies — cap=6/cap=8 do cost measurably more latency than cap=4 in both
(the earlier board added ~15–20ms p95 per cap step; this corpus shows a similar shape, e.g.
cap4→cap6 trace_none: 140.1→173.0ms) — but the earlier hand-built board was deliberately
constructed to exercise accuracy branching hard (two simultaneous sub-100%-accuracy spread moves in
the same line), which this real 85-battle corpus's average decision does not resemble as
consistently. **Neither number is "wrong"**: the single-board bench is evidence about a
worst-case-shaped board; this real-corpus figure is evidence about the actual measured corpus this
plan re-used. The `cap8_trace_enabled` margin here (3.2%) is thin enough that it should not be read
as a confident PASS if the true Kaggle-scaling multiplier turns out higher than the 5× estimate (an
estimate, not a measured constant, per the earlier report's own caveat) — this is flagged, not
resolved, here.

## Ambiguous-candidate diagnostic — headline finding (Task 11, this plan)

All **63** of the historically-excluded Gate-B decisions (the same 63 at cap=4, cap=6, and cap=8 —
`gate-b-report.json`, `cap6-report.json`, `cap8-report.json` all carry the identical
`exception_count=63`) were re-classified via a real, live re-run at every cap. The result is
completely homogeneous:

- **Primary cause: `label_collision` × 63, at every one of the three caps** (189 total
  classifications across cap4/cap6/cap8, all `label_collision`).
- **Subtype: `switch_target_omitted` × 63, at every cap** — `decision.py`'s `_label_ja` renders
  every non-move slot action as the bare string `"switch"`, dropping which benched mon it switches
  to, so two structurally different joint actions that switch to different bench mons in the same
  slot render a byte-identical `candidate_id`.
- **`other_pipeline_error`: zero at every cap.** The diagnostic's routing guards (which would have
  diverted any decision whose original exception was not this exact ambiguity pattern, or whose
  live re-run failed to reproduce as a genuine ≥2-match ambiguity) were exercised but never fired —
  every one of the 63 reproduced cleanly as the same switch-slot label collision. There is no
  second, unrelated defect hiding in this population.
- **`chosen_candidate_missing`: zero at every cap** — the chosen candidate is never actually absent
  from the traced top-K; the problem is telling it apart from an identically-labeled sibling, not
  capacity.
- **Overlap across caps: `all_three=63`, `cap4_only=cap6_only=cap8_only=0`.** The excluded-decision
  set is **completely invariant to the accuracy branch cap** — exactly the same 63 decisions
  collide regardless of cap, which is expected: the branch cap only bounds accuracy telemetry
  depth, never which joint actions are enumerated or how `_label_ja` labels them.

**Fix-feasibility bottom line (investigation only, no `decision.py` change made):** of the three
fix variants evaluated (object identity, object equality, a stable structural key), the
investigation's recommendation is **Variant 3 — a stable structural candidate key** (per-slot
`(kind, move_index, target, target_ident, terastallize)`, Tera handled non-raw against the
pre-overlay enumerated space). This variant is preferred because it is provably accuracy-invariant,
serializable into the offline report, and dissolves both the switch-target collision and a
secondary Tera-overlay label mismatch that the current `_chosen_candidate` resolver already works
around via a tera-stripped fallback. It requires either a new
`DecisionTrace.chosen_joint_action`-style field (none exists today —
`decision_trace.py`'s `DecisionTrace` stores only `chosen_candidate_id: str | None`, a `_label_ja`
string) or a key assigned once at enumeration time and carried through scoring/ranking/trace
construction. **This is explicitly out of scope for this measurement plan** — recorded as the
investigation's conclusion, not implemented; the full five-question analysis and three-variant
comparison is in `data/eval/accuracy-cap-derisk/ambiguous-candidate-diagnostic.md`.

## Explicit, prominent restatement — what this report does NOT license

> **No default-on decision.** `SHOWDOWN_ACCURACY_MODE`'s default remains off, unchanged by this
> entire plan.
>
> **No change to `SHOWDOWN_ACCURACY_BRANCH_CAP`.** It remains `4` in `decision.py`'s
> `_accuracy_branch_cap()`; this plan touched zero production code.
>
> **No strength or winrate claim.** Every number in this report and in `cap6-report.md`/
> `cap8-report.md` is a cap-hit rate, an action-diff count, a latency figure, or a diagnostic
> classification — none of them measure whether the bot plays better or worse games. See the boxed
> statement at the top of this report.
>
> **No Depth-2 Stage 3 work starts from this report.** This report's only relationship to Depth-2
> Stage 3 is that it was one of the two things the roadmap listed as blocking Stage 3 (the other
> being the dev-generalization panel, still separately open, see `docs/ROADMAP.md` P1 item 1). This
> report existing does not itself unblock Stage 3 — a human decision to weigh these numbers and
> choose a path (raise the default cap? fix `_label_ja`'s labeling? both? neither, if the
> latency-margin disagreement above needs a real Kaggle-hardware check first?) is a separate,
> explicit, user-owned next step.

## Non-contamination confirmation (spec §3.4)

No diagnostically-reconstructed telemetry was ever written back into the frozen cap=4 verdict or
its artifacts across this entire plan's execution. Confirmed directly:

```
$ git status --short -- data/eval/accuracy-gate/
(no output)
```

Zero changes to any file under `data/eval/accuracy-gate/` across all 12 tasks of this plan —
`gate-b-report.json`, `gate-b-report.md`, `pre-refactor-baseline.jsonl`,
`post-refactor-diff-report.json`, `dedup-report.json`, and `gate-a-report.{json,md}` are all
byte-identical to how the accuracy-offline-gate plan left them.

## Verification performed for this task

1. **Environment check:** `PYTHONPATH="$(pwd)/src" python -c "import showdown_bot; print(showdown_bot.__file__)"`
   resolved to this worktree's `src/showdown_bot/__init__.py`, confirmed before any run/import.
2. **Renderer run:** `PYTHONPATH="$(pwd)/src" python scripts/render_cap_derisk_reports.py` — wrote
   `data/eval/accuracy-cap-derisk/cap6-report.md` and `cap8-report.md` from the three real Task
   7/8/9 JSON artifacts plus the cited (never modified) cap=4 reference row, no exceptions.
3. **Full test suite, final regression gate:**
   `cd showdown_bot && PYTHONPATH="$(pwd)/src" python -m pytest tests/ -v` →

   ```
   1755 passed, 2 skipped, 1 xfailed in 435.92s (0:07:15)
   ```

   **Genuinely green, 0 failures.** This exceeds the plan's own baseline (1705 passed / 1 skipped
   / 1 xfailed on `main`) by 50 newly-passing tests, consistent with this plan's own new test
   coverage (Tasks 1–11). Run independently twice this task (once in the foreground, once as a
   background invocation that also completed to the identical `1755 passed, 2 skipped, 1 xfailed
   in 431.95s (0:07:11)` — same counts, different wall-clock, as expected for two independent
   runs) — both agree exactly. All three non-passing results were inspected directly, not assumed
   benign:
   - `tests/test_agg_teacher_join.py::test_real_shard_join_and_full_fidelity_probe_teacher_agreement`
     — **SKIPPED**, pre-existing (local-only Kaggle shard not present, gitignored), matches the
     parent accuracy-offline-gate report's own documented baseline skip exactly.
   - `tests/test_baseline.py::test_verify_baseline_real_committed_manifest_green` — **XFAIL**,
     pre-existing, matches the parent report's own documented baseline xfail exactly.
   - `tests/test_movedata.py::test_generated_data_is_fresh` — **SKIPPED** (`generator deps not
     installed (run: npm install in tools/gen)`), the one skip beyond the plan's stated 1-skip
     baseline. Confirmed environment-conditional, not a regression from this plan: this worktree
     has `node` available (`node --version` → `v24.16.0`) but `tools/gen/node_modules/` does not
     exist here, and the test's own source
     (`tests/test_movedata.py:41-46`) calls `pytest.skip("generator deps not installed...")`
     specifically when that directory is absent. This is the **exact same** skip, for the exact
     same reason, that the parent accuracy-offline-gate closeout report already documented in its
     own worktree (`reports/2026-07-13-accuracy-offline-gate-verdict.md`: *"this worktree's
     `tools/gen` lacks installed Node generator deps"*) — a per-worktree property (whether
     `npm install` was ever run in this specific worktree's `tools/gen/`), not something this
     plan's tasks touched or caused. This plan did not modify `movedata.json`, its generator, or
     any file under `tools/gen/`.

## Status: DONE

All 12 tasks of the accuracy-cap-derisk plan are complete. Cap=4's frozen FAIL verdict is
unchanged and cited by content hash throughout. Cap=6 and cap=8 both real-run over the full
deduplicated 944-decision/85-battle corpus: both **PASS** the 5% cap-hit threshold decisively
(0.68% point estimate, 1.37% bootstrap upper bound, identical between the two caps), with **zero**
action changes relative to cap=4 (only score movement) and the same 20/944 action changes relative
to accuracy-off that cap=6 and cap=8 share with each other. Real-corpus latency at ×5 Kaggle-scaling
**passes** the existing 1000ms gate for both caps and both trace modes — disagreeing with, not
confirming, the earlier single-board bench's cap=6/cap=8 FAIL finding, with the disagreement
attributed to (not resolved by) board-representativeness rather than treated as a contradiction to
paper over. The ambiguous-candidate diagnostic found the excluded 63 decisions completely
homogeneous (100% `label_collision`/`switch_target_omitted`, cap-invariant, zero unrelated defects)
with a recommended-but-unimplemented structural-key fix direction. Full test suite green (pasted
above). `data/eval/accuracy-gate/` carries zero git diff across this plan's entire execution.
**This report produces numbers, not a decision** — the default-cap question, any strength claim,
the `_label_ja` fix, and Depth-2 Stage 3 scoping all remain explicitly open, separate, user-owned
next steps.
