# Accuracy Offline Gate — Task 11 closeout (final)

**Date:** 2026-07-13 · **Worktree:** `.claude/worktrees/accuracy-offline-gate` · **Scope:** Task
11 of the 11-task implementation plan
(`docs/superpowers/plans/2026-07-13-accuracy-offline-gate.md`) — run Gate A + Gate B for real,
produce report artifacts, closeout. Design spec:
`docs/superpowers/specs/2026-07-13-accuracy-offline-gate-design.md`.

## The one thing this report is not allowed to bury

> **No default-on decision, no strength claim, and no Depth-2 Stage 3 work follows from this
> report alone.** This gate exists to produce numbers for those three downstream decisions to be
> *reviewed against* — it does not make any of the three decisions itself, and nothing below
> should be read as making one. This is the design spec's own framing (§1: *"Gates three
> downstream decisions — flipping `SHOWDOWN_ACCURACY_MODE`'s default, a new strength baseline, and
> Depth-2 Stage 3 — none of which start until this gate's numbers exist and are reviewed. No
> default-on, no strength claim, and no Depth-2 Stage 3 work follows from this gate alone."*), and
> it is restated here at the user's explicit, repeated instruction for this task. Anyone reading
> only this report should walk away with numbers, not a decision.

## What this task did

1. Attempted the plan's Step 1 runtime-extrapolation dry run — `scripts/run_accuracy_baseline_freeze.py`
   has **no `--dry-run-only` flag** (confirmed by inspecting its source directly: it takes no
   command-line arguments at all) and, separately, would refuse to run regardless because
   `data/eval/accuracy-gate/pre-refactor-baseline.jsonl` already exists (its own hard-checkpoint
   guard, correctly firing). Per this task's own instructions, adapted to real prior evidence
   instead (see "Runtime extrapolation" below) rather than fabricating a dry run that couldn't
   happen.
2. Rendered `data/eval/accuracy-gate/gate-a-report.md` from Task 9's **already-real** Gate A sweep
   (`data/eval/accuracy-gate/gate-a-report.json`, commit `57b7f36`) — **not re-run**, per this
   task's explicit instructions.
3. Ran Gate B **for real**, for the first time, over the full deduplicated corpus — the
   load-bearing real run of the entire 11-task plan. New driver:
   `showdown_bot/scripts/run_accuracy_gate_b.py` (reuses Task 4/7's exact corpus-extraction/dedup
   wiring and Task 9's real `CalcClient`/`DamageOracle`/`SpeedOracle`/`SpeciesDex` construction
   pattern — no new dedup/extraction logic was written). Wrote
   `data/eval/accuracy-gate/gate-b-report.json`, then rendered
   `data/eval/accuracy-gate/gate-b-report.md` from it via
   `showdown_bot/scripts/render_accuracy_gate_reports.py` (mirrors `eval/decision_diff_report.py`'s
   `build_report_object`/`render_markdown` split, adapted to Gate A's/Gate B's own schemas rather
   than inventing an unrelated format).
4. Wrote this closeout report.
5. Ran the full test suite as a final regression gate (see "Verification performed" below).
6. Committed (data/eval + this report, then a separate small ROADMAP.md update).

## Runtime extrapolation (Step 1, adapted)

The plan's literal Step 1 command does not exist and could not have run (see above). The
following real evidence was used instead, and the actual measured Gate B runtime is reported
alongside it so the extrapolation's honesty can be checked directly rather than taken on faith:

- **Task 7's real, already-completed single-pass replay:** 944 MOVE decisions, accuracy off only,
  **34.5s measured** (`data/eval/accuracy-gate/post-refactor-diff-report.json`, `elapsed_seconds:
  34.5`) → ≈36.5 ms/decision average across the real, diverse 85-battle corpus.
- **The accuracy-hit-probability slice's own latency-gate benchmark**
  (`reports/2026-07-12-accuracy-slice-latency-gate.md`), on one fixed representative board with
  the production `persistent` calc backend, `SHOWDOWN_ACCURACY_BRANCH_CAP=4` (today's default):
  accuracy=off p50/p95 ≈ 57–59 ms, accuracy=on(cap=4) p50/p95 ≈ 160–181 ms — an on/off ratio of
  roughly **2.8×–3.0×** on that board.
- **Extrapolation:** applying that ratio to the real corpus's measured off-average (36.5 ms) gives
  an estimated on-average of ≈36.5 × 2.9 ≈ 106 ms/decision, so an estimated off+on combined cost of
  ≈142 ms/decision × 944 decisions ≈ **≈134s (≈2.2 minutes)**, before accounting for Gate B's own
  (lightweight, pure-Python) trace-pairing/cap-hit-scanning overhead on top of the two
  `heuristic_choose_for_request` calls per decision.
- Per the task's own framing, this estimate is well under "many hours" — the full run was
  expected to be feasible, not `INCONCLUSIVE / BLOCKED FOR COMPUTE` (spec §6 item 6), and it was
  run in full, unsampled, unsubstituted.
- **Actual measured Gate B runtime: 92.1s (≈1.5 minutes)** — faster than the ≈134s extrapolation,
  consistent with the extrapolation's on/off ratio being drawn from a single "heavier" benchmark
  board (deliberately built to exercise accuracy branching hard) rather than the real corpus's
  more varied, on-average-lighter decision mix.

## Gate A — smoke test (cited, not re-run)

Per this task's explicit instructions, Task 9's Gate A sweep was **not re-run**. Cited from
`data/eval/accuracy-gate/gate-a-report.json` (commit `57b7f36`), rendered to
`data/eval/accuracy-gate/gate-a-report.md`:

- 2 boards (`primary`, `single_target`) × 7 field-bucket variants (`neutral`, `tailwind_both`,
  `tailwind_p1`, `tailwind_p2`, `trick_room`, `sun`, `rain`) = **14 rows**.
- **0 exceptions, 0 action diffs.**
- Elapsed 46.5s.

**Explicitly labeled, per spec §1: this is a smoke test and cannot license anything on its own** —
field variants of two fixed boards are not independent game situations and barely touch late-game
states, damaged mons, KOs, redirection, or switch states. It is a necessary
connectivity/no-crash/no-diff precondition for Gate B being worth running, not evidence of
correctness or strength.

## Gate B — real replayed corpus (run for real, this task)

Full results in `data/eval/accuracy-gate/gate-b-report.json` /
`data/eval/accuracy-gate/gate-b-report.md`. Summary:

### Dedup breakdown (reported as separate numbers, spec §6 item 5 — not folded into one figure)

| metric | value |
|---|---|
| `.log.gz` files found (4 canonical corpus dirs) | 197 |
| excluded as `duplicate_seed_identity` | 105 |
| excluded as `excluded_diagnostic_artifact` (`room_raw_divergent`, a-priori) | 7 |
| excluded total | 112 |
| final deduplicated unique battles (**G**) | **85** |
| expected G (Task 4's directly-verified real-corpus number) | 85 |
| **G matches expected** | **True** |

### Decision extraction

| kind | count |
|---|---|
| `team_preview` (excluded — no move-accuracy content, spec §6 item 4) | 85 |
| `force_switch` (excluded — no move-accuracy content, spec §6 item 4) | 152 |
| `move` (replayed off+on) | **944** |

### Acceptance rule (spec §4)

- `no_exceptions`: **False**
- `no_nans`: **True** — swept over every replayed decision, not just diverging ones.
- **exception_count: 63** (63/944 = 6.7% of MOVE decisions)
- **n_decisions_compared: 881** (= 944 − 63, exact)

**Every one of the 63 exceptions is the exact, already-documented, already-expected
`RuntimeError`** from `_chosen_candidate` (`eval/accuracy_gate_b.py`) on an ambiguous
`candidate_id`: `decision.py`'s `_label_ja` renders every non-move slot action as the bare string
`"switch"` (dropping which benched mon it switches to), so two structurally different joint
actions switching to different bench mons in the same slot can render a byte-identical
`candidate_id` (e.g. `"(Knock Off->1, switch)"`). Task 10 built this to fail loud rather than
silently guess which candidate was actually chosen, and its own small smoke test had already seen
this fire once in eleven decisions; across the full 944-decision corpus it fired 63 times, spread
across 8 distinct ambiguous-label patterns, always exactly 2 matching candidates. **This is not a
bug in this run — it is documented, expected, correctly-caught behavior, reported honestly as an
excluded/reported exception set, not something "fixed" here.** The full 63-row table
(`request_hash`, ambiguous label, match count) is in `gate-b-report.md`.

**Exclusion-bias bound (recomputed directly from `gate-b-report.json`, not assumed):** the 63
excluded decisions are not part of the 881/114 cap-hit numerator/denominator above, so it's worth
stating explicitly how much they could move the rate under the most extreme hypothetical
treatment, rather than leaving a reader to derive it. Treating all 63 as non-cap-hits (folding
them into the denominator with zero additional hits) gives 114/944 = 12.1%; treating all 63 as
cap-hits (folding them into both numerator and denominator) gives 177/944 = 18.8%. **Even under
this most extreme hypothetical treatment of the 63 excluded decisions, the rate ranges
12.1%-18.8%, still decisively above the 5% threshold — the FAIL verdict is robust to how this
exclusion is treated.**

### Cap-hit verdict (spec §4)

| field | value |
|---|---|
| numerator (decisions with ≥1 `accuracy_branch_cap_hits` on the chosen candidate) | 114 |
| denominator (`n_decisions_compared`) | 881 |
| point estimate (rate) | 0.129398 (≈12.9%) |
| g (distinct battles) | 85 |
| branch applied | **nonzero → game-clustered bootstrap** (numerator > 0, so the zero-event Clopper-Pearson branch does not apply) |
| bootstrap upper bound (one-sided 95%, B=10,000 resamples, seed 20260713, game-clustered) | 0.161331 |
| PASS threshold | 0.05 |
| **verdict** | **FAIL** |

The verdict is `FAIL` directly from the point estimate (0.1294 > 0.05) — the bootstrap upper bound
is still reported for completeness but wasn't needed to reach the verdict. **This is a real,
reportable finding about the current implementation's cap-hit rate on this real corpus at the
shipped default `SHOWDOWN_ACCURACY_BRANCH_CAP=4`** — roughly 1 in 8 chosen-candidate decisions had
at least one scored response whose accuracy-branch expansion exhausted the cap and fell back to
legacy always-hit resolution for part of its tree. Per this report's own framing above, **this
verdict does not by itself justify or block any change to `SHOWDOWN_ACCURACY_BRANCH_CAP`,
`SHOWDOWN_ACCURACY_MODE`'s default, or anything else** — it is a number for a future, separate,
explicit review to weigh (consistent with the accuracy-hit-probability slice's own closeout
report already flagging the branch-cap fallback rate as "an artifact for a future, separate
default-on gating decision to weigh").

### Decision diffs (spec §5 full capture schema)

**20 diffs** (decisions where the chosen action differs off vs on), out of 881 compared
(≈2.3%). Taxonomy breakdown (`action_diff_kind`): `ATTACK_TARGET` ×9, `ATTACK_MOVE` ×7,
`PROTECT` ×3, `SWITCH` ×1. See `gate-b-report.md` for the full 20-row breakdown with every field
(`off/on_chosen_action`, `off/on_score`, `off/on_margin_to_runner_up`, `tera_changed`,
`action_diff_kind`, `events_complete`, `mechanically_explained`, `left_top_k`, `entered_top_k`).
Highlights:

- `events_complete` is `False` on 7 of the 20 diffs (the branch-cap was exhausted somewhere in
  the chosen candidate's own event tree for that decision) — on every one of those 7,
  `mechanically_explained` is also `False`, per spec §4's rule that a known-partial event list can
  never be reported as a complete mechanical explanation. The other 13 diffs have complete event
  lists and complete explanations.
- `tera_changed` is `False` on all 20 diffs — none of the real off-vs-on divergences in this run
  involved a Tera-decision flip.
- One diff (`10f7668ff6ac...`) shows real top-K churn: 3 candidates left the top-K and 3 entered
  it, illustrating that accuracy_mode can meaningfully reorder/reshuffle candidate rankings beyond
  just the #1 choice, not only flip the winner.

## Corpus size confirmation

**Final deduplicated G = 85, matching Task 4's directly-verified real-corpus number exactly.**
Every downstream number in this report (`n_decisions_compared`, the cap-hit verdict, the 20
diffs, the 63 exceptions) was **re-derived this task, from a fresh real dedup run over the same 4
glob directories and 6 manifest files**, not assumed or copy-pasted from an earlier task's output
— `run_accuracy_gate_b.py` calls `deduplicate_battle_logs` itself and hard-fails
(`SystemExit`) before doing any replay work if `final_g != 85`. Since the corpus did not change,
no re-derivation-because-of-drift was needed, but the machinery that would have caught drift ran
and passed.

## Off-path refactor regression check (cited, not re-run)

Task 7 already ran the true refactor-regression check for `SHOWDOWN_ACCURACY_MODE` off: it
replayed the identical 944-decision corpus Task 4 froze
(`data/eval/accuracy-gate/pre-refactor-baseline.jsonl`, frozen at commit `7b6d1ba`, **hard
checkpoint, never regenerated — confirmed untouched this task**) through the **post**-Task-5/6-refactor
`heuristic_choose_for_request`, with `SHOWDOWN_ACCURACY_MODE` explicitly off, and diffed the
result against that frozen baseline
(`data/eval/accuracy-gate/post-refactor-diff-report.json`, commit `edd20d8`):

**`matched=944, regressions=0, missing_from_replay=0, extra_in_replay=0`.**

This is evidence the `LineEvaluation`/`_evaluate_line_details` refactor (Tasks 5/6) did not
change off-path (accuracy-mode-off) behavior — the exact guarantee the accuracy-hit-probability
slice's own closeout already established (unset/`"0"`/`"false"` byte-identical chosen actions) is
now additionally confirmed to survive the later refactor, over the real full corpus, not just a
parser-matrix/wiring-count proof. **Not re-run this task** — cited as already-complete evidence
per this task's explicit instructions.

## Open, untouched follow-up: `AccuracyDiagnostics.accuracy_required` naming bug

**Still open. Not touched by this task, this plan, or any task in this plan.** Per the design
spec §3: the already-merged `AccuracyDiagnostics.accuracy_required` field
(`battle/evaluate.py`, `AccuracyDiagnostics` class / `accuracy_diagnostics()` function — cited by
name, not line number, since line numbers drift and the design spec's own cited lines were
already stale by this task) is misnamed — its docstring calls it "a derived threshold
above which a risky line becomes advantageous," but the actual implementation just assigns
`hit_probability(...)`'s raw return value to it, with no threshold derivation at all. This gate
does not use or touch `AccuracyDiagnostics.accuracy_required` anywhere — Gate A/B's own types
(`AccuracyEventTrace.hit_probability`, etc.) are named for what they actually are and do not
inherit the mismatch. The naming fix (or a fix to the implementation to match the docstring) is
explicitly out of scope for this entire plan and remains a separate, small, tracked follow-up.

## Explicit scope confirmation — what this task did NOT do

- Did **not** flip `SHOWDOWN_ACCURACY_MODE`'s default (still off; unchanged this task).
- Did **not** make any strength-of-play claim from the Gate B numbers above (see the boxed
  statement at the top of this report).
- Did **not** start or scope any Depth-2 Stage 3 work.
- Did **not** touch `AccuracyDiagnostics.accuracy_required` (see above).
- Did **not** regenerate `data/eval/accuracy-gate/pre-refactor-baseline.jsonl` — confirmed via
  `git status`/`git diff` before and after this task's work: zero changes to that file.
- Did **not** re-run Task 9's Gate A sweep or Task 7's baseline diff — both cited from their
  existing, already-committed results.

## Verification performed for this task

1. **Environment check:** `PYTHONPATH="$(pwd)/src" python -c "import showdown_bot; print(showdown_bot.__file__)"`
   resolved to this worktree's `src/showdown_bot/__init__.py`, not the main-repo editable install
   — confirmed before any run.
2. **Gate B real run:** `showdown_bot/scripts/run_accuracy_gate_b.py`, real `CalcClient`
   (`SHOWDOWN_CALC_BACKEND=persistent`), full 944-decision corpus, completed in 92.1s with no
   crashes, no truncation, no sampling. Dedup guard (`final_g == 85`) passed before any replay
   work began.
3. **Full test suite, final regression gate:**
   `cd showdown_bot && PYTHONPATH="$(pwd)/src" python -m pytest tests/ -v` →
   **1704 passed, 2 skipped, 1 xfailed in 452.27s (0:07:32), exit code 0 — genuinely green, 0
   failures.** This exceeds the accuracy-hit-probability slice's prior known-green count (1645
   passed / 1 skipped / 1 xfailed) by 59 newly-passing tests, consistent with this 11-task plan's
   own new test coverage (Tasks 1-10). Both skips and the one xfail were inspected directly, not
   assumed benign:
   - `tests/test_agg_teacher_join.py::test_real_shard_join_and_full_fidelity_probe_teacher_agreement`
     — pre-existing skip (local-only Kaggle shard not present, gitignored), matches the slice's
     prior baseline exactly.
   - `tests/test_movedata.py::test_generated_data_is_fresh` — a **new** skip relative to the prior
     1645-count baseline, but confirmed environment-conditional, not a regression: its own source
     (`tests/test_movedata.py:43,46`) calls `pytest.skip("node not available")` /
     `pytest.skip("generator deps not installed (run: npm install in tools/gen)")` — this
     worktree's `tools/gen` lacks installed Node generator deps. This task did not touch
     `movedata.json` or its generator; the skip is a property of this worktree's environment, not
     of any change made in this task.
   - `tests/test_baseline.py::test_verify_baseline_real_committed_manifest_green` (xfail) —
     pre-existing, matches the slice's prior baseline exactly.

## Deviations from the plan text

- **Step 1's literal command does not exist** (`--dry-run-only` is not a flag on
  `run_accuracy_baseline_freeze.py`) and the script would refuse to run regardless (its own hard
  -checkpoint guard against an existing `pre-refactor-baseline.jsonl`). Adapted per this task's
  own explicit fallback instructions: used Task 7's real 34.5s single-pass evidence plus the
  accuracy-hit-probability slice's own on/off latency-ratio benchmark to extrapolate, then
  reported the actual measured Gate B runtime (92.1s) alongside it for an honest comparison — see
  "Runtime extrapolation" above.
- **Two new driver scripts were written and committed** beyond the plan's literal "Files: Create"
  list: `showdown_bot/scripts/run_accuracy_gate_b.py` (the real Gate B corpus-replay driver) and
  `showdown_bot/scripts/render_accuracy_gate_reports.py` (the JSON→Markdown renderer, following
  `eval/decision_diff_report.py`'s `build_report_object`/`render_markdown` pattern rather than
  inventing an unrelated format). The plan's Step 3 sketch was an inline `python -c` one-liner and
  Step 6's `git add` list only names `data/eval/accuracy-gate/` and this report — committing the
  two driver scripts alongside their output data is a deliberate deviation, matching the same
  precedent Tasks 4 and 7 already established (`run_accuracy_baseline_freeze.py`,
  `run_accuracy_baseline_diff.py` are both committed drivers, not one-off shell commands) for the
  same reason: a load-bearing real run's reproducibility matters, and an uncommitted script that
  produced committed data would be a provenance gap.

## Status: DONE

All 11 tasks of the accuracy-offline-gate plan are complete. Gate A cited (already real, not
re-run). Gate B run for real over the full deduplicated 944-decision / 85-battle corpus (no
sampling, no truncation) — verdict `FAIL` on the cap-hit acceptance rule at the shipped
`SHOWDOWN_ACCURACY_BRANCH_CAP=4` default, 63 documented/expected ambiguous-candidate-id
exceptions, 20 real decision diffs, all reported in full. Full test suite green
(1704 passed / 2 skipped / 1 xfailed / 0 failed). `SHOWDOWN_ACCURACY_MODE`'s default is
unchanged (still off). **This report produces numbers, not a decision** — the default-on
question, any strength claim, and Depth-2 Stage 3 scoping all remain explicitly open, separate,
user-owned next steps.
