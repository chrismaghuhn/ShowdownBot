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

**Status: COMPLETE for the python suite.** 15 guards broken, covering every test commit
`1980174` added plus the three probed before it. 10 RED, 5 green — and every green row is now
either closed by a test or an explicit owner decision.

Negative assertions (a test claiming something does *not* happen) are broken by **adding** code,
not removing it — noted per row below, since "break the guard" does not apply to them.

| Guard broken | Result |
|---|---|
| `export_decisions.py` `duplicate_candidate_key` refuse | **RED** |
| `export_bundle.py` `config_hash_mismatch` refuse | **RED** |
| `validate_bundle.py` `unsupported_capability` refuse | **RED** |
| `privacy.py` seat pseudonym (`side["name"] = seat`) | **RED** |
| `export_battle.py` emit `LogEvent.raw` *(added)* | **RED** |
| `export_decisions.py` `chosen_rank` off by one | **RED** |
| `export_decisions.py` `normalized_action` replaced | **RED** |
| `validate_bundle.py` refuse a higher minor *(added)* | **RED** |
| `validate_bundle.py` cross-check `source_hashes` vs `files.*.sha256` *(added)* | **RED** |
| `provenance.py` reverse lookup keyed by `config_hash` *(added)* | **RED** |
| `validate_bundle.py` `unsupported_major` refuse | **GREEN** → owner decision, see below |
| `export_decisions.py` `decision_latency_ms` → `int(...)` | **GREEN** (109 passed) → closed, PR #83 |
| `export_decisions.py` re-serialize `candidate_key` via JCS | **GREEN** (107 passed) → closed, PR #82 |
| `privacy.py` `strip_state_summary_nicknames` neutralised | **GREEN** → closed, PR #86 |
| `export_bundle.py` `trace_source_hash` constant | **GREEN** → closed, PR #86 |

### The five green rows, stated precisely

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

**`strip_state_summary_nicknames`** had no test at all. The nickname test that existed covers the
`|request|` line path (`pseudonymize_request_payload`); the `state_summary` path was uncovered.
Closed by PR #86 — as a **structural** guarantee that the field is dropped, not as leak
prevention: measured, no committed fixture holds a player-chosen nickname there. All 144 values
across the 11 trace fixtures are species names or base-form/mega variants (`Aerodactyl` for
species `Aerodactyl-Mega`). An earlier reading of this same data as "18 real nicknames" was wrong.

**`trace_source_hash`** exposed a scope gap rather than a vacuous test. The existing gate-23 test
reads `bundles/fixture-01` off disk and compares its recorded hashes to fresh digests — true and
useful about the **artifact**, but it never re-exports, so a **producer** regression stays
invisible until somebody regenerates the fixture. Closed by PR #86 with a fresh-export assertion;
the artifact test is untouched.

---

## 4. What this recheck does **not** establish

- **A current 37-row status table.** Deliberately not produced. Re-deriving one by reading test
  bodies would reproduce the original audit's method but not its weakness — and the weakness is the
  point: a body-reading pass still cannot tell "asserted" from "covered". The completed fail-check
  pass in §3 is the artifact that does, and it is per-guard, not per-gate: several §15 gates are
  split across a positive and a refuse half that are covered by different code, so a single
  COVERED/MISSING letter per gate would lose information this table keeps.
- **Anything about the Godot suite's fail-check status.** 276 cases, **none** fail-checked. The
  original audit excluded gdUnit bodies by scope; that exclusion still stands and is now by far the
  larger unmeasured surface — and it is where all the UI logic lives, including every rendering
  and degradation gate (26–29) that the python suite structurally cannot reach.
- **That a RED row proves a gate is fully covered.** It proves *that break* is caught. A gate whose
  wording covers more than the one guard probed (e.g. gate 19's "no reversible map is present",
  distinct from the seat-pseudonym half broken here) may still be partly unproven.
- **Any strength, safety, or release claim.** None of this speaks to the bot.

## 5. Standing instruction

Do not open a slice on the basis of the old audit's MISSING column. Check the current tests first —
`grep` for the behaviour, then break it and confirm a test goes red. Two slices on 2026-07-25 were
narrowed or discarded for skipping that step.
