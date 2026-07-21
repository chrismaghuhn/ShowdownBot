# Champions `both_foe_slots` Remediation + Candidate-Identity Hardening — Implementation Plan

**Status:** APPROVED (plan review, 2026-07-21, after 3 review rounds — 5 P1s + 3 mechanical, then 3
P1s + 3 mechanical, then 1 P1 + 2 mechanical, all fixed and re-verified) — planning only. No
production code, no test code, no server, no battle, no live gate, no evidence change was produced
here. Approval covers this plan; T1-T4 implementation, the full suite, code review, and PR/merge are
separate, later, separately-authorized steps; the eventual I8-D, coverage, and (once it exists)
holdout gate reruns are separately-authorized steps after merge — I8-D on an unchanged gate
contract, coverage on the deliberately-revised `cov_foe_both` panel/manifest stratum this plan
produces (see Guardrails).

**Design basis (APPROVED):**
`docs/projects/champions/specs/2026-07-20-champions-both-foe-slots-diagnosis.md` (Option 1 +
candidate-identity workflow correction). **Also implements** §5 of
`docs/projects/champions/specs/2026-07-20-champions-coverage-strength-holdout-design.md`
("identical candidate identity" requirement), turning it from report discipline into a
fail-closed code invariant, as recommended in the diagnosis's hardening section.

**Base:** `main`-tracking branch `design/champions-both-foe-slots-diagnosis` @ `a55ab4d`.
Prospective implementation branch: `fix/champions-both-foe-slots-remediation` (to be created only
once implementation is authorized).

**Base command (PowerShell):** `cd showdown_bot; $env:PYTHONPATH = "src"; python -m pytest -q -p no:cacheprovider`
(append a path for a single file; omit for the full suite). All commands below are given in full;
none rely on a shell session carrying `$env:PYTHONPATH` over between separate tool calls.

## Goal

Two independent fixes, bundled into one slice because both were found by the same diagnosis:

1. **`cov_foe_both` team fix** — replace Sneasler's Fake Out so the real, deterministic
   `pick_team_preview_default` leads *both* Mega holders (Aerodactyl, Meganium) instead of
   Aerodactyl + Sneasler, closing the diagnosis's Layer 1 defect. Mirrors F1 (commit `1be0adc`)
   exactly: strip the rival tag-scoring move, let index tie-break do the rest — not add a tag to
   Meganium, which F1 already proved illegal.
2. **Candidate-identity hardening** — give the I8-D gate a `candidate_identity` field (matching
   coverage's own), and make the coverage gate refuse to run against a mismatched or missing one,
   so the identity gap that let the coverage-v0 run execute against an unverified candidate
   (`cbaa4b9`) cannot recur silently.

## Guardrails / non-goals (carried from the diagnosis + design)

- No live server, battle, benchmark, or gate rerun. No push, PR, or merge. No evidence,
  ROADMAP, or PROJECT_INDEX change. Champions Strength stays `NO-GO`.
- Behavior-neutral outside the two targeted changes: no other team file, schedule, panel, or
  production live-play code path (`team_preview.py`'s formula itself) changes. Option 2 from the
  diagnosis (making Mega-holder status a first-class preview signal) is explicitly out of scope.
- No Strength-holdout runner exists yet (confirmed: no file matches `*holdout*` under
  `showdown_bot/src`), so its symmetric identity hardening is deferred until that runner exists —
  not built speculatively here.
- The eventual I8-D rerun must use an **unchanged gate contract** (identical schedule, budget,
  pass/fail logic) — this plan does not touch I8-D's schedule, panel, or teams, only adds a field to
  its verdict output. The eventual coverage rerun keeps the **same cells, floors, 8×25 schedule
  composition, opponent policies, caps, and stop-rules** — but **not** the same panel/manifest hash:
  T1 *deliberately* revises `cov_foe_both`'s team content, so its `team_content_hash`, the panel
  hash, and the manifest hash all change on purpose. No claim anywhere in this plan may say the
  coverage panel or its hash is unchanged.

## Tasks (RED→GREEN checkboxes; each boundary green; full suite at T4)

### T1 — `cov_foe_both` team fix + real-team-preview proof test
Files: `showdown_bot/teams/panel_champions_coverage_v0/cov_foe_both.txt` + `.packed`;
`config/eval/coverage/champions_coverage_v0_manifest.json` (cov_foe_both's `team_content_hash` —
**repo-root-relative, not under `showdown_bot/`**, confirmed via `ls`);
`config/eval/panels/panel_champions_coverage_v0.yaml` (**repo-root-relative**, same confirmation);
`showdown_bot/src/showdown_bot/eval/coverage_schedule.py`
(`COVERAGE_EXPECTED_PANEL_HASH`/`COVERAGE_EXPECTED_MANIFEST_HASH`, ~line 34-36);
`showdown_bot/tests/test_cli_coverage_gate.py` (hardcoded `panel_hash`, ~line 16);
`showdown_bot/tests/test_coverage_constructibility.py`.

- [ ] **RED:** add `test_cov_foe_boths_real_team_leads_both_mega_holders` to
  `test_coverage_constructibility.py`, mirroring `test_cov_foe_slot0s_...`/`test_cov_foe_slot1s_...`
  (lines 111-124): parse the real `cov_foe_both.packed`, drive it through the real
  `pick_team_preview_default`, assert `set(result[:2]) == {1, 2}` (team-sheet positions 1 and 2 =
  Aerodactyl and Meganium; order-independent since `both_foe_slots` only needs both present, not a
  specific letter). Run `cd showdown_bot; $env:PYTHONPATH = "src"; python -m pytest -q
  -p no:cacheprovider tests/test_coverage_constructibility.py` → **expect FAIL**: today's team
  returns leads `{4, 1}` (Sneasler's Fake Out at `lead=3.0` outranks Aerodactyl's `2.5`).
- [ ] **GREEN:**
  1. In `cov_foe_both.txt`, replace Sneasler's `Fake Out` with `Poison Jab` (same swap F1 already
     made for the identical Sneasler moveset in `cov_foe_slot0`/`cov_foe_slot1` — Dire Claw / Close
     Combat / Poison Jab / Protect, ability Poison Touch).
  2. Re-validate the edited team via the real `pokemon-showdown validate-team
     gen9championsvgc2026regma` (mandatory — do not assume legality from precedent alone; confirm
     for this exact file).
  3. Regenerate `cov_foe_both.packed` via `pack-team`; confirm it's byte-consistent with the `.txt`.
  4. Recompute and update, together, so they stay internally consistent: `cov_foe_both`'s
     `team_content_hash` in the manifest JSON, the panel YAML, and
     `COVERAGE_EXPECTED_PANEL_HASH`/`COVERAGE_EXPECTED_MANIFEST_HASH` in `coverage_schedule.py`, and
     the hardcoded `panel_hash` in `test_cli_coverage_gate.py`.
  Run `cd showdown_bot; $env:PYTHONPATH = "src"; python -m pytest -q -p no:cacheprovider
  tests/test_coverage_constructibility.py tests/test_cli_coverage_gate.py` → **expect pass**; new
  test now returns leads `{1, 2}`.
- [ ] **Commit:** `fix(coverage): redesign cov_foe_both so the real preview picker leads both Mega holders`.

### T2 — shared `candidate_identity` helper; I8-D gate gains it in its verdict
Files: `showdown_bot/src/showdown_bot/learning/provenance.py` (new `make_candidate_identity(*,
hero_agent: str, git_sha: str, config_hash: str) -> str`, reusing the file's existing `_sha16()`
helper at lines 31-32); `showdown_bot/src/showdown_bot/eval/coverage_runner.py`
(`resolve_coverage_provenance`, lines 51-91 — refactor its inline sha1 computation at lines 86-89 to
call the new shared helper instead, so both gates provably share one code path, not two
independently-maintained copies of the same formula); `showdown_bot/src/showdown_bot/eval/i8d_runner.py`
(`resolve_i8d_provenance`, lines 157-199, calls the shared helper; `run_i8d_live_gate`'s body,
lines 212-385, computes `candidate_identity` itself from its own already-bound `hero_agent`/
`git_sha`/`config_hash` parameters and writes it into the `report` dict, lines 366-384, before
`_write_json_atomic` at 385); `showdown_bot/tests/test_provenance.py` (**extends the existing
file** — it is not new — with a unit test for the shared helper + a cross-gate consistency test);
`showdown_bot/tests/test_cli_i8d_gate.py` (extends
`test_resolve_provenance_derives_from_repo_and_env`, line 21); `showdown_bot/tests/test_i8d_runner.py`
(extends `test_output_dir_is_published_atomically_and_verdict_equals_return`, line 267).

**How `candidate_identity` reaches the published verdict (the gap the last review found):**
`run_i8d_live_gate` already receives `git_sha`, `config_hash`, and `hero_agent` as bound parameters
(lines 212-216) — it does **not** need a new parameter for the identity. Inside the function body it
calls the shared `make_candidate_identity(hero_agent=hero_agent, git_sha=git_sha,
config_hash=config_hash)` itself and writes the result into the `report` dict. There is no
caller-supplied `candidate_identity` value anywhere that could disagree with the gate's own bound
inputs — the same "derive, don't trust a caller's value" principle T3 applies on the coverage side.

Three RED tests are required — the first alone would only prove the formula is right in isolation,
the second that it survives into the published artifact, the third that both gates' identity
computation is genuinely the *same* code path, not two formulas that happen to agree today:

- [ ] **RED 1 (shared helper, `test_provenance.py`):** add
  `test_make_candidate_identity_matches_the_sha1_formula` asserting
  `make_candidate_identity(hero_agent="h", git_sha="g", config_hash="c") ==
  hashlib.sha1(json.dumps({"hero_agent": "h", "git_sha": "g", "config_hash": "c"}, sort_keys=True,
  separators=(",",":")).encode()).hexdigest()[:16]`. Run `cd showdown_bot; $env:PYTHONPATH = "src";
  python -m pytest -q -p no:cacheprovider
  tests/test_provenance.py::test_make_candidate_identity_matches_the_sha1_formula` → **expect**
  `AttributeError: module 'showdown_bot.learning.provenance' has no attribute
  'make_candidate_identity'`.
- [ ] **RED 2 (cross-gate consistency, `test_provenance.py`):** add
  `test_i8d_and_coverage_produce_the_same_identity_for_the_same_inputs` — monkeypatch both
  `resolve_i8d_provenance()`'s and `resolve_coverage_provenance()`'s underlying `git_sha_and_dirty`
  and config-manifest inputs to identical fixed values, then assert
  `resolve_i8d_provenance()["candidate_identity"] == resolve_coverage_provenance()["candidate_identity"]`.
  Matching output values alone would still be true even if the two gates coded the formula
  independently and happened to agree today, so **also** wrap `make_candidate_identity` with a spy
  (e.g. `unittest.mock.patch(..., wraps=the_real_function)` on
  `showdown_bot.learning.provenance.make_candidate_identity`) and assert it is called at least once
  by each resolver — proving both genuinely execute the *same* function object, not two independent
  implementations that could silently drift apart later. Run the same pytest invocation with
  `-k same_identity` → **expect** `KeyError: 'candidate_identity'` (I8-D side doesn't have the field
  yet).
- [ ] **RED 3 (published artifact, `test_i8d_runner.py`):** extend
  `test_output_dir_is_published_atomically_and_verdict_equals_return` (line 267) — it already
  asserts the on-disk `verdict.json` equals the dict `run_i8d_live_gate` returns; add the assertion
  that both the return value **and** the on-disk file contain matching `candidate_identity`,
  `git_sha`, `config_hash`, `calc_backend`, and `hero_agent`. This is the test that actually proves
  the field reaches the artifact a future gate would read, not just that the formula is right in
  isolation. Run `cd showdown_bot; $env:PYTHONPATH = "src"; python -m pytest -q -p no:cacheprovider
  tests/test_i8d_runner.py::test_output_dir_is_published_atomically_and_verdict_equals_return` →
  **expect** `AssertionError`/`KeyError` (fields absent from both the return value and the file).
- [ ] **GREEN:** add `make_candidate_identity()` to `learning/provenance.py`; have
  `resolve_coverage_provenance()` and `resolve_i8d_provenance()` both call it instead of computing
  sha1 inline; have `run_i8d_live_gate` call it directly (not via a passed-in parameter) using its
  own bound `hero_agent`/`git_sha`/`config_hash`, and add the result to the `report` dict before
  `_write_json_atomic`. Run `cd showdown_bot; $env:PYTHONPATH = "src"; python -m pytest -q
  -p no:cacheprovider tests/test_provenance.py tests/test_cli_i8d_gate.py tests/test_i8d_runner.py
  tests/test_coverage_runner.py` → **expect** pass (the last file is included because
  `resolve_coverage_provenance()` was refactored, not just extended). The 4 already-frozen I8-D
  `verdict.json` files and the 1 frozen coverage `verdict.json` are separate, static, one-shot
  artifacts, not a row-streamed schema — they are simply not touched by this change and stay
  byte-unchanged; they continue to validate under whichever existing readers/tests already cover
  them, which never depended on `candidate_identity` being present.
- [ ] **Commit:** `feat(provenance): shared candidate_identity helper; I8-D verdict gains it too`.

### T3 — coverage gate fails closed unless the *same, PASSing* I8-D candidate identity is proven first
Files: `showdown_bot/src/showdown_bot/eval/coverage_runner.py` (`run_coverage_gate`, signature at
line 143, gains `i8d_verdict_path: str = ""` — **an explicit empty-string default, not a bare
required keyword**: a genuinely omitted required keyword-only argument raises a Python `TypeError`
at the call boundary, before the function body ever runs, so it could never become a
`CoverageRunError`; the runner's own guard treats `i8d_verdict_path == ""` as "missing" and raises
`CoverageRunError` itself. **The check moves to the very top of the function, before
`verify_coverage_schedule`/`build_coverage_live_schedule` (currently lines 155/162)** — i.e.
`resolve_coverage_provenance()` (currently called at line 181) moves to before those, so the gate
fails before the canonical schedule is even built, not merely before battles. This is a considered
reordering of *existing* code, not just an addition — verify at GREEN time that no existing test
depends on today's error-precedence order (e.g. a dirty tree vs. a bad panel_hash reported first)
before finalizing it.); `showdown_bot/src/showdown_bot/cli.py` (`run_coverage_gate_cli`,
lines 710-752, gains the global `--i8d-verdict-path` argument alongside the existing global
`--out-dir` registration, plus a per-command required-check mirroring the existing `--out-dir` check
at lines 729-731); `showdown_bot/tests/test_coverage_runner.py` (runner-level tests, mirroring
`test_the_runner_does_not_accept_caller_supplied_git_sha_or_config_hash` line 104 and
`test_a_technical_abort_publishes_no_out_dir_and_records_no_verdict` line 345);
`showdown_bot/tests/test_cli_coverage_gate.py` (CLI-level tests, mirroring `test_command_requires_out_dir`
line 73; **also review `test_the_command_takes_no_provenance_flags` at line 62** — confirm at GREEN
time whether it means "no flag that lets the caller *supply* an identity value" (still true —
`--i8d-verdict-path` supplies a *path to cross-check against*, not a `git_sha`/`config_hash`/
`candidate_identity` value itself) or "no flags of any kind" (would need updating); do not leave it
silently contradicting the new flag).

**Confirmed at review:** the check belongs in `run_coverage_gate` itself, not only in the CLI
wrapper — the runner already re-derives its own provenance internally, so a CLI-only check would
create two separate derivation points and could be bypassed by any caller that invokes the runner
directly. The CLI's job is only to require and forward the path.

**Confirmed at review (P1, not previously covered): identity match alone is not enough.** A frozen
I8-D `verdict.json` can share the right `candidate_identity` and still be `verdict: "FAIL"` (or
inconclusive) — the diagnosis's binding execution order is "I8-D must **PASS** → coverage runs on
the same candidate," not merely "same candidate." The runner must therefore require **both**:
`candidate_identity` matches **and** the I8-D verdict's `verdict` field is exactly `"PASS"`. Missing
the path, an unreadable/malformed file, a missing `candidate_identity` field, a missing/other
`verdict` value, or a mismatch on either dimension → `CoverageRunError`, no staging, no battle.

**Design decision (confirmed at review):** `--i8d-verdict-path` is **required** for
`champions-coverage-gate`, enforced as a per-command check inside `run_coverage_gate_cli` — **not**
`argparse(..., required=True)`, which is global to the parser and would break `ladder`, `smoke`,
`i8d-live-gate`, and every other command sharing the same parser.

**Confirmed at review (P1): migrating the 9 existing `test_coverage_runner.py` call sites and 2
existing `test_cli_coverage_gate.py` "success path" tests is part of this task, not an
afterthought.** Moving the check to the top of `run_coverage_gate` means every existing caller that
doesn't pass `i8d_verdict_path` now fails at the new pre-check *first* — never reaching whatever
behavior it was actually written to test. `resolve_coverage_provenance` is monkeypatched throughout
`test_coverage_runner.py` to always return the fixture `_PROV` (line 48), whose
`_PROV["candidate_identity"]` is `"cand0123456789ab"` — every migrated call needs a verdict file
carrying exactly that value.

- **New test helper**, added near `_PROV`: `_write_i8d_verdict(tmp_path, *,
  candidate_identity=_PROV["candidate_identity"], verdict="PASS", name="i8d_verdict.json") -> str` —
  writes `{"candidate_identity": ..., "verdict": ...}` as JSON to `tmp_path / name` and returns the
  path as a string.
- **`_run()` (line 89)**, the shared helper most tests route through: call
  `_write_i8d_verdict(tmp_path)` and pass `i8d_verdict_path=<that path>` into its own
  `run_coverage_gate(...)` call (line 94).
- **All 8 direct calls that bypass `_run()`** each get `i8d_verdict_path=_write_i8d_verdict(tmp_path)`
  added to their existing `run_coverage_gate(...)` call, so their original target error is still the
  *first* one reached: `test_a_forged_panel_hash_on_otherwise_legitimate_rows_is_rejected` (line 110,
  call at 123), `test_the_runner_uses_the_derived_calc_backend_not_a_default` (127, call at 136),
  `test_the_out_dir_may_not_be_under_data_eval` (161, call at 165),
  `test_the_runner_refuses_a_leftover_staging_or_out_dir` (206, call at 212),
  `test_a_reordered_matchup_cycle_is_rejected_even_with_a_valid_panel_hash` (216, call at 230),
  `test_a_teams_hash_record_that_no_longer_matches_disk_is_caught_by_the_runner_itself` (234, call
  at 248), `test_the_panel_is_locked_to_the_coverage_panel` (252, call at 260),
  `test_seed_alignment_is_verified` (353, call at 368). That accounts for all 9 existing
  `run_coverage_gate(` call sites in the file (1 in `_run` + 8 direct) — confirm at GREEN time that
  no tenth call site was added or missed.
- **Only the new tests added by this task** (below) deliberately call `_write_i8d_verdict` with a
  wrong `candidate_identity`/`verdict`, or skip it and pass `i8d_verdict_path=""`/omit it, to exercise
  the new guard itself.
- **`test_cli_coverage_gate.py`**: `run_coverage_gate` itself is stubbed at the module seam in this
  file (line 34-40), so only the CLI's *own* new required-check matters here, not the runner's.
  `test_command_locks_the_coverage_panel_derives_provenance_and_reaches_the_runner` (line 44) and
  `test_the_command_takes_no_provenance_flags` (line 62) both construct
  `argparse.Namespace(out_dir=..., teams_root=".")` **without** `i8d_verdict_path` — add
  `i8d_verdict_path="i8d.json"` (any non-empty string; the stub never reads it) to both so they still
  reach `_fake_run`. `test_the_command_takes_no_provenance_flags`'s own assertion
  (`not ({"git_sha", "config_hash", "candidate_identity"} & set(kw))`) is unaffected either way, since
  it never checks for `i8d_verdict_path`. The CLI's new required-check must be added **after** the
  existing `out_dir`/`SHOWDOWN_EVAL_SEED_LOG` checks in `run_coverage_gate_cli`, not before, so
  `test_command_requires_out_dir` (line 73) and `test_command_requires_the_server_seed_log` (line 80)
  — neither of which sets `i8d_verdict_path` either — still hit their own intended check first and
  need no changes themselves.

- [ ] **RED (runner-level, `test_coverage_runner.py`):** add tests mirroring the file's existing
  fail-closed style (`test_a_technical_abort_publishes_no_out_dir_and_records_no_verdict`, line 345),
  each asserting `CoverageRunError` and that no `out_dir`/staging directory and no canonical schedule
  build happen (per the new, earlier insertion point):
  `test_a_missing_i8d_verdict_path_is_refused_before_the_schedule_build`,
  `test_an_unreadable_or_malformed_i8d_verdict_is_refused`,
  `test_an_i8d_verdict_missing_candidate_identity_is_refused`,
  `test_a_mismatched_i8d_candidate_identity_is_refused`,
  `test_an_i8d_verdict_with_the_right_identity_but_verdict_fail_is_refused` (the new, previously
  missing case — same `candidate_identity`, `verdict: "FAIL"`),
  `test_an_i8d_verdict_missing_the_verdict_field_is_refused`. Run `cd showdown_bot; $env:PYTHONPATH =
  "src"; python -m pytest -q -p no:cacheprovider tests/test_coverage_runner.py -k i8d_verdict` →
  **expect** `TypeError: run_coverage_gate() got an unexpected keyword argument 'i8d_verdict_path'`
  (parameter doesn't exist yet).
- [ ] **RED (CLI-level, `test_cli_coverage_gate.py`):** add `test_command_requires_i8d_verdict_path`
  (mirroring `test_command_requires_out_dir`, line 73) and
  `test_other_commands_are_unaffected_by_the_new_flag` (drives e.g. `smoke` or `i8d-live-gate`
  through the parser without `--i8d-verdict-path` and asserts no error from argument parsing itself
  — only `champions-coverage-gate`'s own handler may reject a missing path). Run `cd showdown_bot;
  $env:PYTHONPATH = "src"; python -m pytest -q -p no:cacheprovider tests/test_cli_coverage_gate.py -k
  i8d_verdict_path` → **expect** fail (no such argument exists yet).
- [ ] **GREEN:**
  1. `cli.py`: add `--i8d-verdict-path` as a **global** argument with an empty default (`default=""`),
     alongside `--out-dir`'s own registration — never `required=True` at the parser level.
  2. `run_coverage_gate_cli`: `i8d_verdict_path = getattr(args, "i8d_verdict_path", ""); if not
     i8d_verdict_path: raise SystemExit("champions-coverage-gate requires --i8d-verdict-path")` —
     exact mirror of the existing `--out-dir` check (lines 729-731) — placed **after** the existing
     `out_dir` and `SHOWDOWN_EVAL_SEED_LOG` checks, not before (so `test_command_requires_out_dir`
     and `test_command_requires_the_server_seed_log` keep hitting their own checks first) — then
     forward `i8d_verdict_path=i8d_verdict_path` into the `run_coverage_gate(...)` call (currently
     lines 747-749). The CLI does no comparison itself, only requires-and-forwards.
  3. `coverage_runner.py`: `run_coverage_gate` gains `i8d_verdict_path: str = ""`. Move
     `resolve_coverage_provenance()` (and the new guard) to the very start of the function, before
     `verify_coverage_schedule`. The guard: if `i8d_verdict_path == ""`, `CoverageRunError`; else
     read+parse the file (any read/parse failure → `CoverageRunError`); require both
     `parsed["candidate_identity"] == candidate_identity` (the runner's own freshly-derived value)
     and `parsed.get("verdict") == "PASS"` — anything else (missing field, mismatch, non-PASS
     verdict) → `CoverageRunError`, matching the file's existing message style.
  4. Resolve the `test_the_command_takes_no_provenance_flags` (line 62) question found above; update
     or annotate it so it does not silently contradict the new flag.
  5. Migrate the tests per the "migrating the 9 existing call sites" note above: add
     `_write_i8d_verdict()` to `test_coverage_runner.py`, wire it into `_run()` and all 8 direct
     calls, and add `i8d_verdict_path` to the 2 named `test_cli_coverage_gate.py` Namespaces. This is
     not optional cleanup — without it the focused GREEN suite below would pass while silently
     de-fanging all 9 pre-existing protections (each would raise `CoverageRunError` for "missing
     i8d_verdict_path" instead of its own intended reason, without necessarily failing the test if
     it only asserts the exception type).
  Run `cd showdown_bot; $env:PYTHONPATH = "src"; python -m pytest -q -p no:cacheprovider
  tests/test_coverage_runner.py tests/test_cli_coverage_gate.py` → **expect** pass.
- [ ] **Commit:** `feat(coverage): fail closed in run_coverage_gate unless the same I8-D candidate PASSed (§5 hardening)`.

### T4 — closeout
- [ ] Full suite: `cd showdown_bot; $env:PYTHONPATH = "src"; python -m pytest -q -p no:cacheprovider`
  green; reconcile pass/skip/xfail counts against the pre-slice baseline.
- [ ] All frozen evidence datasets (I8-D ×4, coverage-v0) re-validate byte-unchanged; `git diff --check`.
- [ ] Confirm `cov_foe_slot0`/`cov_foe_slot1`/`order_tie` team files are untouched. This slice edits
  only `cov_foe_both`'s content plus the two *shared* hash constants all four cells' entries are
  derived alongside — `panel_hash` and `manifest_hash`. `schedule_hash` covers matchup
  order/assignment, not team content, so it is unaffected and must stay the same value.

## Sequencing & non-claims

Order T1→T2→T3→T4; each task's boundary green before the next starts; full suite + frozen-dataset
re-validation at T4. This plan does not run, benchmark, or gate anything — **after** merge, the
I8-D latency gate (**unchanged gate contract**) and the coverage gate (**same cells, floors, 8×25
composition, policies, caps, and stop-rules — but the deliberately revised, newly-hashed
`cov_foe_both` panel/manifest stratum**) must each PASS, and (once it exists) the Strength holdout
must also PASS, all on the **same** final candidate SHA, per the diagnosis's corrected execution
order, before any Strength claim. No backend switch, budget/floor/schedule change, or Strength claim
is authorized by this plan; Champions Strength remains `NO-GO`.

---

`BOTH_FOE_SLOTS + IDENTITY-HARDENING PLAN — APPROVED (PLAN REVIEW PASS) — T1-T4 IMPLEMENTATION ITSELF STILL REQUIRES ITS OWN SEPARATE AUTHORIZATION — NO CODE, TEST, RUN, PUSH, PR, OR MERGE AUTHORIZED YET`
