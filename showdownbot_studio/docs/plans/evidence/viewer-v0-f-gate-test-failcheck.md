# Plan F — fail-check pass for the gate-coverage tests (commit `1980174`)

**Status: PARTIAL.** Only the priority group (gates 10/11/12) was checked. Recorded honestly rather
than left implied — see "Not reached" below.

A test that cannot fail is not coverage. The Rev. 5 audit's central finding was that the *previous*
coverage counted "does not raise on real data" as proof; commit `1980174` replaced it, and this pass
exists to confirm the replacement is not the same mistake in new clothes.

Method: temporarily break the production behaviour a test claims to cover, run only that test,
confirm it goes red, restore, confirm green again. Production files are restored after every check —
verified with `git status` (clean) after each.

Environment: `PYTHONPATH` pinned to this worktree; loaded exporter confirmed as
`…/.worktrees/studio-plan-f-exec/showdownbot_studio/python/src/showdownbot_studio_exporter/__init__.py`
before each run. Without this the global editable install resolves to the main checkout.

## Result — gates 10/11/12 (the audit's over-claimed group)

| Test | Break applied | Result |
|---|---|---|
| `test_a4_decisions_v3.py::test_chosen_candidate_key_unresolvable_refuses` | disabled `_resolve_chosen`'s `len(matches) == 0` → `ExportRefuse("chosen_integrity", "…unresolvable")` branch in `export_decisions.py` (replaced with `return candidates[0]`) | **STAYED GREEN** |
| the other four in the group (`…_resolves_to_exactly_one_matching_candidate_with_agreeing_rank`, `…_agrees_with_normalized_action`, `test_chosen_rank_mismatch_refuses`, `test_duplicate_candidate_key_within_row_refuses`) | same break | **STAYED GREEN** |

## What that actually means — not "the test asserts nothing"

The test does assert a real refusal. It is not empty. But it does **not** exercise the guard it
appears to name, and the two are distinguishable by their messages:

- the test asserts `reason == "chosen_integrity"` and `"must reference a traced candidate" in message`
- the guard broken above raises `chosen_integrity` with `"decision N: chosen_candidate_key unresolvable"`

Different message ⇒ different code path. The test calls `load_trace_rows(...)`, whose upstream
validation (`showdown_bot.eval.decision_capture.validate_trace_row`) refuses first. The Studio
exporter's own `_resolve_chosen` branches never run on that path.

**This is the same structural finding an earlier batch made for fixture 11**, where the plan assumed
`ExportRefuse("non_finite_value", …)` and the real pipeline produced `trace_validation` because
`validate_trace_row` fires earlier. `export_decisions._resolve_chosen`'s refuse branches appear to be
dead code on the real `load_trace_rows` → `export_bundle` path, reachable only by calling the inner
helper directly.

**Consequence for the coverage claim:** gates 10/11/12 are covered *at the upstream-validator layer*,
which is where the refusal genuinely happens, and that is legitimate proof that a malformed trace is
rejected. They are **not** covered at the Studio-exporter layer, and no test in this repo would
notice if `_resolve_chosen`'s guards were deleted.

## Recommended follow-up (not done here — out of this task's scope)

1. Decide whether `_resolve_chosen`'s refuse branches are intended defence-in-depth (keep, and test
   them by calling the helper directly) or genuinely redundant (remove, and say so). Do **not**
   silently leave unreachable refuse code that reads as a guarantee.
2. Same question for the `non_finite_value` branches the earlier batch found.
3. Whichever way: record it, because "the exporter refuses X" currently means "something upstream of
   the exporter refuses X", and those are different claims.

## Not reached

No fail-check was performed for: gate 25 (`config_hash` reverse-lookup), gates 16/17 (minor-version
rules), gate 23 (`source_hashes`), gates 3/7/9, the privacy tests, the canonical-form tests, or the
Godot-side `test_sort_never_changes_chosen_identity_or_candidate_ranks`. Three successive attempts at
this pass were cut short; the group above was prioritised because the audit had specifically flagged
it as previously over-claimed.

Those tests are green but **unproven**. Until each has been shown to fail against a broken
implementation, the honest statement is "asserted", not "covered".
