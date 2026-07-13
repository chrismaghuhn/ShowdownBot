# Accuracy / hit-probability slice — Task 9 closeout (final)

**Date:** 2026-07-12 · **Branch:** `feat/slice-accuracy-hit-probability` · **HEAD (before this
commit):** `fa14574` · **Scope:** Task 9 of the 9-task implementation plan
(`docs/plans/2026-07-12-accuracy-hit-probability.md`) — final verification + closeout report,
no new features.

## What shipped

- **Accuracy field generation.** `showdown_bot/tools/gen/gen_movedata.mjs` now emits an
  `accuracy` field per move into `config/moves/movedata.json`; `MoveMeta.accuracy` (loader in
  `showdown_bot/src/showdown_bot/engine/moves.py`) fails closed on a missing field rather than
  silently defaulting (commit `6610fcb`).
- **`hit_probability()`** (`showdown_bot/src/showdown_bot/engine/moves.py:173`) — base accuracy,
  accuracy/evasion boost-stage math (`raw = base*(3+stage)/3` / `base*3/(3-stage)`, truncated to
  an int before the /100 the way `sim/battle-actions.ts` does), and exactly two pinned weather
  rules (Thunder/Hurricane in Rain → unconditional hit; in Sun → accuracy becomes a numeric 50
  that still goes through the stage pipeline; Blizzard in Snow → unconditional hit), verified
  against the real pinned Pokémon Showdown server commit recorded in
  `config/eval/provenance.yaml` (commit `56a039f`, plus `eee186d` for the negative-stage/`field
  is None` regression coverage).
- **`resolve_turn_branches()`** (`showdown_bot/src/showdown_bot/battle/resolve.py:350`) —
  recursive, depth-first expansion of `resolve_turn` over genuinely-uncertain accuracy events,
  re-discovering newly-revealed pending events after every partial resolve instead of trusting a
  single one-shot discovery pass. This fixes a real correctness bug: a one-shot event list is
  wrong whenever a hit/miss outcome changes who even gets to act (KO-before-act) or who gets
  targeted (redirection) — an action invisible to the branch that discovered the list would
  otherwise silently be scored as an always-hit. `fork_records` tracks, for every fork on the
  path to the fully-resolved "everything hits" leaf, that fork's own miss-sibling subtree (input
  a later diagnostic needs to reconstruct tree structure a flat leaf list can't recover). This
  was the highest-risk piece of the slice (commits `4cf7cb7`, `a216bdd`; see "Notable things
  caught" below), plus `forced_miss` plumbing through `resolve_turn`/`apply_hit` and
  attempted/missed-hit tracking (`8eec22e`, `5c76aed`).
- **`evaluate_line`/`decision.py` integration** — `evaluate_line` gained
  `accuracy_mode`/`accuracy_branch_cap` kwargs (default off, byte-identical); when on it expands
  hit/miss branches via `resolve_turn_branches` and returns a probability-weighted score instead
  of the always-hit `resolve_turn` path. `decision.py` resolves `SHOWDOWN_ACCURACY_MODE` /
  `SHOWDOWN_ACCURACY_BRANCH_CAP` once in `_choose_best` and threads them through **all 8**
  `evaluate_line` call sites that feed the live decision inside `_choose_best`/`_maybe_tera` (both
  `score_plan` variants, the K-world `score_plan`, `score_plan_with_outcome`, the report metrics
  line, `_breakdowns_for`, and both `_maybe_tera` calls) — including the Tera-decision path, not
  just the primary scoring path (commit `9060b3c`, integration-verified by `dc95a0f`). `depth2_value`
  / `search.py` is untouched (separate, later scope — see boundary #4 below).
- **`AccuracyDiagnostics`** (`showdown_bot/src/showdown_bot/battle/evaluate.py:373`,
  `accuracy_diagnostics()` at line 386) — all 4 fields: `ko_probability`, `survival_probability`,
  `accuracy_required`, `miss_punish_value` (commit `b2ff854`, duplicate-target double-count and
  empty-leaves-guard fix in `44bffe9`). Implemented and unit-tested as a standalone function;
  **not yet wired into any live caller** — see Open Follow-Up Item below.
- **`movedata_hash` provenance** — a content hash of `config/moves/movedata.json`, threaded into
  `build_config_manifest`/`make_config_hash` unconditionally (mirroring `priors_hash`/
  `spreads_hash`), so two runs with different accuracy data never share a config lineage even
  when `SHOWDOWN_ACCURACY_MODE` itself is off (commit `2ed181a`).
- **Latency-pinned branch-cap default** — a real local micro-benchmark (persistent Node `CalcClient`
  backend, n=25/config, p95 gate) confirmed `SHOWDOWN_ACCURACY_BRANCH_CAP=4` is the largest cap
  value that clears the depth-2 precedent's scaled-×5 1000ms gate (cap=6/8 both exceed it); the
  default was left unchanged (commit `fa14574`, `reports/2026-07-12-accuracy-slice-latency-gate.md`).

## The off-by-default guarantee and how it was verified

`SHOWDOWN_ACCURACY_MODE` defaults off. Off means unset, `""`, `"0"`, or `"false"`
(case-insensitive) — via an **explicit off-list parser**
(`showdown_bot/src/showdown_bot/battle/decision.py:91`, `_accuracy_mode()`):

```python
raw = os.environ.get("SHOWDOWN_ACCURACY_MODE", "").strip().lower()
return raw not in ("", "0", "false")
```

This is deliberately **not** `bool(os.environ.get(...))` — that shortcut (used elsewhere in this
codebase for presence-only flags, e.g. `SHOWDOWN_RERANKER_SHADOW`) treats the strings `"0"` and
`"false"` as truthy, which would have been a real bug for this flag specifically: an operator
setting `SHOWDOWN_ACCURACY_MODE=0` expecting "off" would silently get "on." This was caught and
fixed during code review before it shipped (documented in the function's own docstring).

Byte-identical off-path behavior is proven at three levels:

1. **Unit level:** `tests/test_evaluate.py::test_evaluate_line_accuracy_mode_off_is_byte_identical_to_default`
   — `evaluate_line`'s default and an explicit `accuracy_mode=False` produce identical scores and
   `hp_delta`.
2. **Integration level:** `tests/test_accuracy_mode_wiring.py` — wraps (not replaces) the real
   `evaluate_line` inside one full `_choose_best` decision and records every call's
   `accuracy_mode` kwarg. With `SHOWDOWN_ACCURACY_MODE` unset, all recorded calls (≥4 asserted;
   in practice this fixture drives dozens of calls per decision, and the Task 8 latency bench
   independently measured ~350 `evaluate_line`-adjacent calls on a heavier board) carry
   `accuracy_mode=False`. The companion test proves the `=1` case reaches every call site too, so
   a future call site that quietly drops the kwarg fails a test, not just a code review.
3. **Parser-matrix level:** `tests/test_config_env.py::test_accuracy_mode_parser_matrix` —
   `unset/""/"0"/"false"/"False"` all parse to `False`; `"1"/"true"` parse to `True`.

**Task 9's own independent, final check** (not committed as a pytest test — see Deviations
below): a standalone script drove one full `_choose_best` live decision three times — unset,
explicit `"0"`, explicit `"false"` — using the same fakes as `tests/conftest.py::decision_fixture`
(no live Node subprocess needed). Result: **the chosen action was byte-identical across all
three** (confirmed via full string-equality on the returned `JointAction`, not just a truncated
repr). `_accuracy_mode()` parsed all three as `False`, as expected.

**One nuance surfaced by this check, reported honestly rather than smoothed over:** `config_hash`
was **not** identical across the three (three distinct hashes). This is not a bug in this slice —
`behavior_env()` (`showdown_bot/src/showdown_bot/eval/config_env.py`) folds the **raw environment
string** for every `BEHAVIOR_AFFECTING` var into the manifest it hashes, not the parsed boolean.
Every flag in that set has this same property (e.g. `SHOWDOWN_MUST_REACT_LAMBDA="0.5"` vs
`"0.50"` would also hash differently despite parsing to the same float) — this is the module's
documented fail-closed-by-literal-value design ("a forgotten behavior-affecting flag then only
makes runs non-pairable (safe); it can never produce the same config_hash for different behavior
(dangerous)"). So: **the guarantee that actually matters — identical chosen actions — holds.**
`config_hash` identity across textually-different-but-semantically-equivalent env values was never
a design goal of `config_hash`, for this flag or any other, and the plan text's expectation that it
would match was not correct; that expectation is corrected here rather than papered over.

Given the existing Task 5 integration test already proves per-call-site wiring consistency
end-to-end, and the parser-matrix test already proves `"0"`/`"false"` both parse to off, this
task's addition (the three-way full-decision run + the `config_hash` check) is a genuinely new,
narrow data point (config_hash's behavior under equivalent-off env spellings) rather than
redundant coverage — worth keeping as a documented one-off check, not worth promoting into a
committed test given it would just re-assert what the parser matrix + Task 5 wiring test already
guarantee about the parsed value.

## Fallback-rate figures (Task 8 benchmark) — reported, not acted on

From `reports/2026-07-12-accuracy-slice-latency-gate.md` (persistent Node `CalcClient` backend,
n=25/config, one representative doubles board with an accuracy<100 spread move on each side):

| `SHOWDOWN_ACCURACY_BRANCH_CAP` | call-hit% (branch-cap exhausted, ≥1 leaf) | dec-hit% |
|---|---|---|
| 2 | 44.0% (both runs) | 100% |
| 4 (default) | 44.0% (both runs) | 100% |
| 6 | 6.9% (both runs) | 100% |
| 8 | 6.9% (both runs) | 100% |

`call-hit%` is the fraction of `resolve_turn_branches` invocations (~350/decision on this board)
where at least one leaf in that call's tree hit the cap and fell back to today's legacy
all-remaining-hit resolution for the rest of that subtree. `dec-hit%` saturates at 100% for every
on-config across ~350 lines/decision and is not informative on its own (sample-size artifact, per
the Task 8 report). At the shipped default (cap=4), **44.0% of `resolve_turn_branches` calls on
this board hit the cap and partially fell back.** This is an artifact for a **future, separate**
default-on gating decision to weigh — this task and this plan explicitly do not decide whether
`SHOWDOWN_ACCURACY_MODE`'s default should ever flip to on; that decision is out of scope here.

## Explicit scope boundaries

1. **`rollout.py` untouched throughout.** A separate fixed-policy multi-turn condition engine,
   confirmed out of scope by the design spec. Verified for this closeout via
   `git diff main...HEAD -- showdown_bot/src/showdown_bot/battle/rollout.py` — empty diff.
2. **Ability/item accuracy modifiers not modeled.** Documented as a v1.1 limitation directly in
   `hit_probability`'s own docstring (`engine/moves.py:173`): only base accuracy, boost stages,
   and the two pinned weather rules are in v1 scope.
3. **Risk-priority fork ordering not implemented.** `resolve_turn_branches`'s `expand()`
   (`battle/resolve.py:420`, `pair, p = pending[0]  # deterministic: first attempted-hit order`)
   forks on the first-attempted-hit-order pending pair, not ranked by miss-probability or
   downstream risk. This is the documented v1 baseline, not a gap discovered late.
4. **`depth2_value` / `showdown_bot/src/showdown_bot/battle/search.py` untouched by this entire
   slice.** Confirmed via `git diff main...HEAD -- showdown_bot/src/showdown_bot/battle/search.py`
   across the full commit range (`af575e5`..`fa14574`, all 16 commits including the 3 spec/plan
   docs commits) — empty diff. Deliberate, explicit boundary: Depth-2 Stage 3 integration is
   separate, later work.
5. **OPEN FOLLOW-UP ITEM (not a closed decision):** `AccuracyDiagnostics` is implemented and unit
   -tested as a standalone function (`battle/evaluate.py::accuracy_diagnostics`,
   `battle/evaluate.py:373` for the dataclass) but is **not wired into the live `DecisionTrace`
   schema.** Confirmed for this closeout — `battle/decision_trace.py`'s `DecisionTrace` class has
   zero references to `accuracy`. No caller in this slice invokes `accuracy_diagnostics`
   automatically during a live decision. **A future short task (or the start of Depth-2 Stage 3,
   whichever comes first) must either wire it into `DecisionTrace` with a clearly separated field
   name (e.g. `accuracy_diagnostics: AccuracyDiagnostics | None = None`, `None` when
   `accuracy_mode` is off) or explicitly re-confirm it's still not needed.** This must not be
   allowed to disappear silently.

## Notable things caught during implementation

The code-review process across this 9-task plan caught and fixed several real bugs before they
shipped, worth recording as evidence of the rigor applied, not just as trivia:

- **`p==0.0` accuracy event silently treated as a guaranteed hit instead of a guaranteed miss**
  (commit `a216bdd`, fixing `4cf7cb7`). The `pending` filter in `resolve_turn_branches` originally
  excluded `p==0.0` events; because `resolve_turn` defaults any pair not explicitly in
  `forced_miss` to a hit, an unforked guaranteed-miss event would have silently resolved as a
  guaranteed hit — the exact opposite of correct. Fixed by dropping the unnecessary/wrong `0.0 <`
  lower bound, keeping only `p < 1.0`.
- **A duplicate-`targets`-list double-counting bug in `AccuracyDiagnostics`** (commit `44bffe9`,
  fixing `b2ff854`). `ko_probability`'s inner loop iterated the raw `targets` list instead of a
  deduped structure, so a repeated slot (e.g. two attackers targeting the same weakened opposing
  slot) accumulated weight more than once, producing out-of-range probabilities (>1.0, or negative
  survival probability). The same commit also added a guard for an empty leaf list that previously
  raised a generic `IndexError` instead of a documented precondition failure.
- **Narrower-than-required `evaluate_line` call-site wiring caught at plan-review time, before
  Task 5's code was written.** An earlier draft of the implementation plan
  (`docs/plans/2026-07-12-accuracy-hit-probability.md`) wired only 2 of the 8 live
  `_choose_best`/`_maybe_tera` call sites and would have left the rest (including `_maybe_tera`,
  the report metrics line, and the `DecisionTrace` breakdown call) silently on legacy always-hit
  scoring — a live decision-correctness bug (Tera-or-not decisions never reflecting accuracy risk)
  and a training-data integrity bug (exported `DecisionTrace` rows silently inconsistent with the
  actual chosen-action scoring) rather than a cosmetic gap. Plan review flagged this and the plan
  was corrected (commit `cc20894`, "fix plan-review findings... all 8 call sites") **before** Task
  5's implementation commit (`9060b3c`) was written, so the shipped code never went through a
  narrower intermediate state — it landed with all 8 sites wired from the start, verified by the
  dedicated integration test (`dc95a0f`).

## Verification performed for this task

1. **Full suite, clean run:** `cd showdown_bot && python -m pytest -q -rs` →
   **1645 passed, 1 skipped, 1 xfailed in 391.01s (6:31).** The 1 skip
   (`tests/test_agg_teacher_join.py`: local-only Kaggle shard not present, gitignored) and 1 xfail
   are both pre-existing from before this slice started; no new skips or xfails were introduced.
2. **Off-path byte-identity, independent final check:** see "off-by-default guarantee" section
   above — chosen action byte-identical across unset/`"0"`/`"false"`; `config_hash` differs across
   the three by design (raw-string hashing), not a defect.
3. **`movedata.json` freshness:** `node gen_movedata.mjs --check` inside
   `showdown_bot/tools/gen` → `fresh`, exit 0. `node_modules` was already present in this worktree
   (no `npm ci` needed this time).

## Deviations from the plan text

- **Step 2's standalone script was not added as a committed pytest test**, per the plan's own
  permission ("if you find the existing Task 5 integration test already fully covers this and
  adding more is redundant, say so... rather than padding effort"). The script lives at
  `scratchpad/verify_offpath_byte_identity.py` (this session's Temp scratchpad, not the repo) and
  was run once for this report; it is not committed, matching the plan's framing of Step 2 as a
  final belt-and-suspenders check rather than new test infrastructure.
- **Step 2's assumption that `config_hash` would be identical across unset/`"0"`/`"false"` did not
  hold**, for the reason explained above (raw-string hashing of `BEHAVIOR_AFFECTING` env vars is
  this codebase's general, pre-existing, documented design — not something introduced by this
  slice). This is reported as a finding rather than silently adjusted to match the plan's
  expectation.

## Status: DONE

All 9 tasks of the accuracy/hit-probability slice are complete. Full suite green
(1645/1/1, no new skips/xfails). Off-path byte-identity holds for the guarantee that matters
(chosen actions). `movedata.json` confirmed fresh against the generator. One open, explicitly
flagged follow-up item remains (`AccuracyDiagnostics` not wired into `DecisionTrace` — item 5
above), by design not a blocker for this plan's completion, but not to be forgotten either.
