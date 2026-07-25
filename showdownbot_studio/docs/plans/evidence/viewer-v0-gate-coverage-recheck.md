# Viewer v0 — gate-coverage recheck against current `main`

**Date:** 2026-07-25. **Base:** `main @ 92dcb97`.

This supersedes the status column of
[`viewer-v0-f-gate-coverage-audit.md`](viewer-v0-f-gate-coverage-audit.md) — **not its method**,
which was right and is reused here. It does not restate the 37-row table; it records why that
table can no longer be read as current, and what was actually measured instead.

---

## 1. Why the old audit's numbers cannot be used

Its headline is **8 COVERED / 15 PARTIAL / 14 MISSING of 37**, measured on `main @ 5feaa7c`.

`git merge-base --is-ancestor 24686cf 1980174` confirms the audit commit is an **ancestor** of
commit `1980174`, whose message is *"close gate-coverage gaps the Plan F audit verified"* — the
commit that consumed the audit's own MISSING list. Nine commits touched Studio tests since the
audit's base; python test functions went **80 → 109** (`git grep -c "^def test_"` at each rev).

The audit was accurate when written. It is a **snapshot of a superseded tree**, and its MISSING
column is the part most likely to be wrong, because closing it was the explicit purpose of the very
next commit.

### This cost real work, twice, on 2026-07-25

Both slices below started from the stale table and had to be narrowed after the fact:

| Slice | Started as | Actually true |
|---|---|---|
| PR #82 | "gate 9 is MISSING" | `test_a1_canonicalize.py::test_candidate_key_round_trips_byte_identically_never_reserialized` already existed. One of the two tests added was largely redundant. **PR #82's body claim — _"No test anywhere compares a source row's `candidate_key` bytes to the output row's"_ — is false**, and is corrected here and in PR #83. |
| PR #83 | "gates 3 and 7 are MISSING" | Both already covered. The gate-7 test written for it was **dropped outright**; only the decision-trace half of gate 3 survived as genuinely additive. |

The failure mode in both cases was identical: quoting the audit instead of checking the tests.

---

## 2. The distinction this recheck exists to enforce

**A test naming a gate in its docstring is not evidence the gate is covered.**

A grep of docstrings finds **21 of 37** gates named by at least one test. That number is worthless
on its own, in both directions:

- It **overstates**: the pre-existing fail-check pass
  ([`viewer-v0-f-gate-test-failcheck.md`](viewer-v0-f-gate-test-failcheck.md)) proved all five
  gate-10/11/12 tests **stay green** when the guard they name is deleted — they exercise
  `showdown_bot`'s upstream `validate_trace_row`, not the Studio exporter branch they appear to test.
- It **understates**: gates 6, 18 and 30 name no gate number anywhere yet are plainly exercised
  (the JCS vector suite, the privacy counterexample, the request-hash recipes).

Only a fail-check separates the two: break the behaviour, confirm that exact test goes red, restore.

---

## 3. Fail-check results measured for this recheck

Method: neutralise one production guard, run the tests that claim it, restore via
`git checkout --`. Each run **aborts if the tree is not clean first** — the initial attempt at this
batch had a broken restore path (`cwd` relative to the wrong directory), which stacked three breaks
on top of each other and contaminated its own results. Those numbers were discarded and every row
below was re-measured on a verified-clean tree; the tree was clean again at the end.

| Guard broken | Claiming test | Result |
|---|---|---|
| `export_decisions.py` `duplicate_candidate_key` refuse | `test_a4_decisions_v3.py` | **RED** — genuinely covered |
| `export_bundle.py` `config_hash_mismatch` refuse | `test_a6_provenance_modes.py` | **RED** — genuinely covered |
| `validate_bundle.py` `unsupported_capability` refuse | `test_a7_validate_bundle.py` | **RED** — genuinely covered |
| `validate_bundle.py` `unsupported_major` refuse | — | **STAYED GREEN** |
| `export_decisions.py` `decision_latency_ms` → `int(...)` | — | **STAYED GREEN** (109 passed, 0 failed) |
| `export_decisions.py` re-serialize `candidate_key` inner JSON via JCS | — | **STAYED GREEN** (107 passed, 0 failed) |

### The three green rows, stated precisely

**`unsupported_major` — a narrower finding than it first looks.** Gate 15 *is* covered:
`godot/tests/bundle/test_bundle_validator.gd:105::test_fixture07_unsupported_major_refuses`
asserts the refusal against fixture-07 on `BundleValidator`, which is the validator the viewer
actually runs. What has **zero** coverage is the *Python exporter's own* guard at
`validate_bundle.py:97`. That is live production code — `export_bundle` calls
`validate_bundle_dir(staging)` before publishing — and deleting it leaves the whole Python suite
green. The only python-side mention of gate 15 is a cross-reference at
`test_a7_validate_bundle.py:218` pointing at the Godot side; line 16 asserts `major == 1` on a
*good* bundle and never constructs an unsupported one.

**`decision_latency_ms` → `int(...)`** is real data loss — 1.5 ms rendered as 1 ms — and no test
in the repo noticed. Closed by PR #83 for the decision-trace path.

**JCS re-serialization of `candidate_key`** is the §7.3.2 defect that destroys candidate identity.
The pre-existing gate-9 test cannot discriminate it: every `candidate_key` in the committed
fixtures holds only strings, ints, nulls and bools with already-sorted member names, so a JCS
round-trip reproduces them byte-for-byte. Closed by PR #82's float-injection test. **This is the
one conclusion from PR #82 that survives** — the measurement was always right; only the
"gate 9 was uncovered" framing drawn from it was wrong.

---

## 4. What this recheck does **not** establish

- **A current 37-row status table.** Deliberately not produced. Re-deriving one by reading test
  bodies would reproduce the original audit's method but not its weakness — and the weakness is the
  point: a body-reading pass still cannot tell "asserted" from "covered". The next useful artifact
  is a **completed fail-check pass**, not a refreshed table.
- **Coverage of the ~12 other tests `1980174` added** (gates 16, 17, 19, 21, 23, 25 and the
  positive halves of 10/11/12). They are green and unproven. Given that 3 of the 6 guards probed
  here stayed green, treating the untested remainder as covered is not justified.
- **Anything about the Godot suite's fail-check status.** 276 cases, none fail-checked. The
  original audit excluded gdUnit bodies by scope; that exclusion still stands and is now the larger
  unmeasured surface.
- **Any strength, safety, or release claim.** None of this speaks to the bot.

## 5. Standing instruction

Do not open a slice on the basis of the old audit's MISSING column. Check the current tests first —
`grep` for the behaviour, then break it and confirm a test goes red. Two slices on 2026-07-25 were
narrowed or discarded for skipping that step.
