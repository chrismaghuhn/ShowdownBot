# Champions Opponent-Mega Coverage — Implementation Plan (Gate A)

**Status:** APPROVED — 2026-07-20 (Rev. 3). **Implementation/execution is NOT authorized by this
document**; beginning implementation requires separate authorization and does not follow from this
approval. No server start, battle, benchmark, live gate run, or push is triggered here. (The read-only
`validate-team` team-legality check in Task 4 GREEN is the only external invocation, and only at
implementation time.)

**Date:** 2026-07-20 · **Rev.:** 3 · **Base:** `main @ 9c780a2` · **Branch:** `design/champions-coverage-strength-holdout`

**Design (contract):**
`docs/projects/champions/specs/2026-07-20-champions-coverage-strength-holdout-design.md` (APPROVED) —
this plan implements **Gate A (coverage) only**. The independent Strength holdout (Gate B) is a
**separate** plan; its six blind-curated teams are an **external prerequisite for that plan, not this
one**.

**Goal.** Build, test-first and entirely offline, the opponent-Mega **coverage** gate: a **live-only
decision-profile v3** telemetry (foe-Mega slot + activation-order-tie) with full v1/v2 backward
compatibility and an unchanged microprofile writer; a **server-authoritative** safety signal; the
per-cell live validator; the standard coverage panel + closed-schema coverage manifest + team files +
four schedule-linked offline constructibility proofs; the three-way coverage verdict
(PASS/FAIL/INCONCLUSIVE) with ABORTED kept off the verdict; and a provenance-**deriving**, panel-locked
coverage runner + CLI — **with no server start, battle, benchmark, or live gate run**.

## Non-goals (hard)

- **No server start, battle, benchmark, or live gate run.** Every test uses synthetic offline boards
  (`eval/profile_fixtures.py`) or **injected** battle profiles (as `tests/test_i8d_runner.py` already
  does), never a live gauntlet. The runner and CLI are *built and unit-tested*, never executed live.
  The **only** external invocation is the read-only `validate-team` team-legality check in Task 4 GREEN
  (no server, no battle).
- **No Strength holdout** (separate plan). **No change** to the I8-D latency gate's budget or its
  frozen evidence. (The live builder becomes v3, so a future latency re-run naturally emits v3 — that
  is the spec §5 requirement, not a change here.) The Task 6 gauntlet seam is **additive-only** and lives
  **on the in-memory `GauntletStats` dataclass**, never on the shared per-battle result row: the closed T2
  writer `eval/result_jsonl.py` and `_battle_result_record` are untouched, so I8-D's budget, verdict
  logic, and every T2 row stay byte-identical (behaviour-neutrality gate, Task 6).
- **The microprofile writer stays `decision-profile-v2`** and byte-stable (frozen microprofile evidence
  untouched). v3 is **live-only**.
- **Behavior-neutral:** the v3 telemetry (including the safety label) records facts only — it must not
  change any decision output (golden decision-equivalence, byte-identical decisions).
- **No `data/eval/**` frozen-evidence bytes touched**; frozen v1/v2 datasets must still validate.

## Tech stack & conventions

- Python 3, pytest. **All commands run from `showdown_bot/`.** Full suite: `python -m pytest -q`.
- Green baseline (Task 0): the current `main @ 9c780a2` full suite, expected ≈
  `2837 passed / 1 skipped / 1 xfailed` (the skip is
  `tests/test_panel.py::test_panel_champions_v0_packed_reproducible_from_txt`; the xfail is
  `tests/test_baseline.py::test_verify_baseline_real_committed_manifest_green`). Record the exact
  numbers and treat them as the baseline; each task adds tests and keeps that skip/xfail set unchanged.
- **TDD is mandatory:** write the failing test first, run it, confirm it fails for the intended reason,
  then write the minimal code to green. Never code before a red test.
- **Candidate identity (spec §5):** the runner **derives** a candidate-identity hash (agent config +
  `git_sha` + `config_hash`); a coverage PASS binds to that identity only. Provenance is **never
  caller-supplied**.
- **Commit boundaries:** seven logical commits (Tasks 1–7), each `git diff --check`-clean with its
  targeted suite green; the **full suite** runs at Task 2 (behavior-neutrality) and Task 7 (closeout).
  No partial/broken intermediate commit.

## Source map (grounded, `main @ 9c780a2`)

- `SRC = showdown_bot/src/showdown_bot/`, `T = showdown_bot/tests/`.
- `SRC/eval/decision_profile.py`: `SCHEMA_VERSION_V1` (L199), `SCHEMA_VERSION="decision-profile-v2"`
  (L200), `_SCHEMA_VERSIONS` (L206), `_OUTCOMES = frozenset({"ok","crash","fallback","degraded_state"})`
  (L209); `PROFILE_ROW_FIELDS`/`_FIELD_SET` (L61-111), `PROFILE_ROW_FIELDS_V1`/`_FIELD_SET_V1`
  (L116-119); `validate_profile_row_fields` (L132-155, branch L149); value rules incl. the
  `n_mega_twins>0 ⇒ foe_mega_active` rule (L854-857) and `outcome=='ok' ⇔ measured_ms set` (L864-865);
  `build_live_profile_row` (L290-361; stamps version L315; shape→row L352-358; `foe_mega_active` L358;
  `outcome` L359); `is_active_valid_live_row` (L1051-1065; requires `outcome=='ok'` **and**
  `foe_mega_active is True` — L1063-1064, so a non-foe-Mega row is present but **not** active-valid);
  `validate_live_profile_dataset` (L1068-1128 → `{rows,active_valid_rows,distinct_active_battle_ids}`);
  `_require_single_schema_version` (L978-990, `key=repr`); `DecisionProfileWriter.write` (L1241-1259);
  the **microprofile** row builder is `SRC/eval/profile_harness.py` (imports `SCHEMA_VERSION` L59,
  stamps it L329 — this stays v2).
- `SRC/battle/mega_scoring.py`: `MegaShapeCounts` (L37-60, six int fields); `MegaEvaluationContext`
  (`foe_mega_slot` L76, `activation_order` L78); `ScoredResponseEvidence` (`foe_mega_slot` L314);
  `score_evaluated_variants` (L360-390; `shape_sink` L389); real scored foe slots L549-552
  (`{r.foe_mega_slot for r in resps if r.foe_mega_slot is not None and r.weight>0}`); `n_mega_twins += 1`
  L741-743; `branch_ctx.activation_order`
  L646-653.
- `SRC/engine/mega_projection.py::compose_mega_projection_branches` (L155): the tie
  signature — `is_tie` L201, **two `0.5`-weighted reversed orderings** L202-203 (vs one `1.0`).
- `SRC/client/gauntlet.py`: per-seat safety machinery (Task 6). `_is_real_invalid` (L51 — a server
  `|error|` real illegal choice, benign race-errors excluded); the per-client counter `client.invalid`
  (incremented L925 on a `pm` frame, L936 on an `|error|` frame); `run_local_gauntlet` (L1174; **`games`
  is a required parameter**, L1176 — the coverage runner **invokes it with `games=1`**, so each call plays
  exactly one battle) sets the in-memory `GauntletStats.invalid_choices = hero.invalid + villain.invalid`
  (L1424 — a **sum**, blind to seat). The `|error|` for an illegal choice arrives **after**
  `decision_seq` advances, so Task 6 records the sent choice's `decision_index` **per room at send time**
  (mirroring `last_choose[room]`, L700) and, on the later `|error|` (which already reads
  `last_choose[parsed.room]`, L940), attributes that recorded index — **never** the since-advanced counter
  — to `GauntletStats.hero_invalid_decision_indices` (**on the stats dataclass** L223-230). The runner then
  **joins** each index to that decision's `decision_profile.foe_mega_active` (`decision_profile.py:358`,
  per-decision, true iff the decision scored a foe-Mega twin) so **only a hero illegal choice on a foe-Mega
  decision counts**. It
  does **not** touch `_battle_result_record` (L1113-1145) or the closed T2 row writer
  `eval/result_jsonl.py` (its `REQUIRED_FIELDS`/`NULLABLE_FIELDS` allowlist, L17/L24, rejects unknown keys
  — so the seam stays off that shared row). `SRC/battle/legal_actions.py` is only what the bot *chooses
  from*, never the safety authority.
- `SRC/eval/i8d_runner.py`: constants L28-33; `should_stop` L46-58; `i8d_verdict` L71-88;
  `resolve_i8d_provenance` L157-199 (derives `git_sha`/`config_hash`/`calc_backend`, refuses dirty tree
  L174-183); `_verify_seed_alignment` L136-154; `run_i8d_live_gate` L212-389 (staging `{out_dir}.staging`
  L275, refuse-preexisting L276-282, per-battle writer+adopt L325/L342-345, final
  verify+verdict+`os.replace` L361-388); `_write_json_atomic` L106-112; `_adopt_battle_atomic` L122-133.
- `SRC/eval/i8d_schedule.py`: `I8D_SEED_BASE` (L27), `I8D_FORMAT` (L28), `I8D_HERO_TEAM` (L29),
  `I8D_MAX_BATTLES=200` (L30), `I8D_PANEL_PATH` (L37), `I8D_EXPECTED_PANEL_HASH` (L38), `I8D_MATCHUPS`
  (L43-50); `build_i8d_schedule` (L57-116), `verify_i8d_schedule` (L119-186),
  `verify_i8d_panel_and_teams` (L189-229).
- `SRC/eval/profile_fixtures.py` (offline, node-free): `_board_no_foe` (L120), **`_board_tie`** (L126,
  own==foe==200 speed tie → the two-`0.5`-branch `order_tie` basis; arm `A09_dual_mega_tie` in
  `profile_arms.py:195`), `_board_foe_slotb` (L132, foe Mega slot b=1), `_board_no_own_mega` (L139),
  `_board_dual_unequal` (L146, foe Mega slot a=0, strict inequality → one `1.0` branch),
  `_board_dual_unequal_tr` (L152); `BOARDS` (L159-166), `board(name)` (L169-171); `ProfileSession.score()`
  builds `MegaShapeCounts()` and calls `score_evaluated_variants(..., shape_sink=shape)` (L252-262),
  real `foe_mega_eligibility(...)` (L251); `FIXTURE_HASHES` pinned at import (L190).
- `SRC/cli.py` (`showdown_bot/src/showdown_bot/cli.py`): the `i8d-live-gate`
  command handler L672-704, arg-parser registration L716/853, dispatch L1025.
- Test conventions to mirror: `T/test_decision_profile_validator.py`, `T/test_i8d_live_row.py`,
  `T/test_i8d_live_dataset_validator.py`, `T/test_i8d_shape_threading.py`, `T/test_mega_shape_counts.py`,
  `T/test_i8d_runner.py`, `T/test_i8d_schedule.py`, `T/test_i8d_schedule_verify.py`,
  `T/test_cli_i8d_gate.py`, `T/test_profile_fixtures.py`, `T/eval/test_profile_schema_v2_mixed.py`.

---

## Task 0 — Baseline (no commit)

- [ ] From `showdown_bot/`: `python -m pytest -q`. **Record** the exact `passed/skipped/xfailed` and
  the skip/xfail identities. This is the frozen baseline; every later task must preserve the skip/xfail
  set and only add passing tests. No code change, no commit.

---

## Task 1 — live-only decision-profile **v3** schema + invariants + v1/v2 back-compat *(req 1)*

**Files:** modify `SRC/eval/decision_profile.py`, `SRC/battle/mega_scoring.py`; create
`T/test_decision_profile_v3.py`; extend `T/eval/test_profile_schema_v2_mixed.py`.

v3 adds **exactly two** fields — **`foe_mega_slots`** (JSON array of ints ⊆ `{0,1}`, sorted/unique) and
**`foe_mega_order_tie`** (bool) — stamped **only by the live builder**; the microprofile writer
(`profile_harness.py`) keeps `decision-profile-v2` and its exact field set. **No client-side safety
field is added and `_OUTCOMES` is unchanged:** the bot only ever chooses from `battle/legal_actions`
(legal *by construction*), so an illegal choice would be a **server-rejected bug** — an authoritative,
**server-side** signal captured by the gauntlet at the battle level (Task 6), never a client-derived
decision-profile outcome.

- [ ] **RED** — write `T/test_decision_profile_v3.py`:
  - `test_a_v3_live_row_has_the_two_new_fields_and_validates` — `build_live_profile_row(...)` output has
    `foe_mega_slots`, `foe_mega_order_tie`, `schema_version=="decision-profile-v3"`, and passes
    `validate_profile_row_fields`.
  - `test_the_microprofile_writer_stays_v2_and_omits_the_v3_fields` — a `profile_harness` row still
    stamps `"decision-profile-v2"` and validates under `_FIELD_SET` **without** the two v3 fields.
  - `test_a_v2_row_still_validates_and_rejects_a_v3_field` — a 42-field v2 row validates; adding
    `foe_mega_slots` to it is rejected as unknown.
  - `test_a_v1_row_still_validates_unchanged`; `test_v3_fields_are_absent_not_null_on_pre_v3_rows`.
  - `test_slots_must_be_a_sorted_unique_int_subset_of_0_1` — `[2]`, `[1,0]`, `[0,0]`, `"x"` each raise
    `DecisionProfileError`.
  - `test_a_recorded_slot_implies_n_mega_twins_positive` — `foe_mega_slots != [] and n_mega_twins==0`
    is rejected.
  - `test_order_tie_true_implies_twins_positive_and_a_recorded_foe_slot` — `foe_mega_order_tie is True`
    with `n_mega_twins==0` **or** `foe_mega_slots==[]` is rejected.
  - **Frozen-tier regression (both real dataset validators, read-only, bytes untouched).** Let
    `ROOT = Path(__file__).resolve().parents[2]` (tests/ → showdown_bot/ → repo root):
    - `test_the_frozen_v2_live_dataset_still_validates` — the **live** tier
      `validate_live_profile_dataset((ROOT / "data/eval/champions-panel-v0/i8d-live-post-lever-b/profile.jsonl").as_posix())`
      still passes and returns its recorded population (v2 back-compat).
    - `test_the_frozen_microprofile_dataset_still_validates` — the **microprofile** tier
      `validate_decision_profile_dataset((ROOT / "data/eval/champions-panel-v0/i8-microprofile/profile.jsonl").as_posix(), manifest=json.loads((ROOT / "data/eval/champions-panel-v0/i8-microprofile/profile_manifest.json").read_text()))`
      still passes (still v2).
  - In `T/eval/test_profile_schema_v2_mixed.py`: `test_a_dataset_mixing_v2_and_v3_is_rejected`.
  - **Run (RED):** `python -m pytest tests/test_decision_profile_v3.py tests/eval/test_profile_schema_v2_mixed.py -q --tb=line -rs`
    → **fails**: `foe_mega_slots`/`foe_mega_order_tie` are unknown fields, and `SCHEMA_VERSION_LIVE` and
    the invariants do not yet exist. (The two frozen-tier tests pass from the start — they guard
    back-compat and must keep passing through GREEN.)
- [ ] **GREEN** — `SRC/battle/mega_scoring.py`: add to `MegaShapeCounts` (defaulted, additive):
  `foe_mega_slots: tuple[int, ...] = ()`, `foe_mega_order_tie: bool = False`.
- [ ] **GREEN** — `SRC/eval/decision_profile.py`:
  - Add `SCHEMA_VERSION_V2 = "decision-profile-v2"` (alias of the current `SCHEMA_VERSION`) and
    `SCHEMA_VERSION_LIVE = "decision-profile-v3"`; leave `SCHEMA_VERSION = SCHEMA_VERSION_V2`
    (microprofile/default stamp unchanged); `_SCHEMA_VERSIONS = frozenset({SCHEMA_VERSION_V1,
    SCHEMA_VERSION_V2, SCHEMA_VERSION_LIVE})`. **`_OUTCOMES` is unchanged.**
  - Keep `_FIELD_SET` = v2 (unchanged). Add
    `_FIELD_SET_LIVE = _FIELD_SET | {"foe_mega_slots","foe_mega_order_tie"}`; `_FIELD_SET_V1` unchanged.
  - `validate_profile_row_fields`: branch `_FIELD_SET_V1` if v1, `_FIELD_SET_LIVE` if
    `SCHEMA_VERSION_LIVE`, else `_FIELD_SET` (v2).
  - Value rules (extend near L854-865): `foe_mega_slots` sorted-unique ints ⊆ `{0,1}`;
    `foe_mega_order_tie` bool; **`foe_mega_slots != [] ⇒ n_mega_twins > 0`**;
    **`foe_mega_order_tie is True ⇒ n_mega_twins > 0 and foe_mega_slots != []`**.
  - `build_live_profile_row`: stamp `SCHEMA_VERSION_LIVE` (L315); write
    `"foe_mega_slots": sorted(shape.foe_mega_slots) if shape else []`,
    `"foe_mega_order_tie": bool(shape.foe_mega_order_tie) if shape else False`. Do **not** touch
    `profile_harness.py`; add **no** `choice_legal` field.
  - **Run (GREEN):** the Task-1 command → passes (frozen-tier tests still green); then
    `python -m pytest tests/test_decision_profile_writer.py tests/test_decision_profile_validator.py tests/test_decision_profile_dataset.py tests/test_i8d_live_row.py tests/test_i8d_live_dataset_validator.py tests/test_profile_fixtures.py -q --tb=line -rs`
    → green (microprofile + v1/v2 consumers unaffected, fixture hashes byte-stable).
- [ ] `git diff --check`; **commit:**
  `eval(decision-profile): live-only v3 schema (foe-Mega slot/order-tie) + invariants + v1/v2 back-compat`.

---

## Task 2 — origin telemetry: fill `foe_mega_slots` + `foe_mega_order_tie` (+ the `both_foe_slots` fixture) *(req 2)*

**Files:** modify `SRC/battle/mega_scoring.py`, `SRC/eval/profile_fixtures.py`; create
`T/test_coverage_origin_telemetry.py`; touch `T/test_profile_fixtures.py`,
`T/test_i8d_shape_threading.py`.

This task creates the **one** missing fixture it needs (`_board_both_foe_slots`) — **RED before GREEN**,
no production/fixture code ahead of a failing test (`_board_dual_unequal`→slot0, `_board_foe_slotb`→slot1,
`_board_tie`→order_tie already exist).

- [ ] **RED (fixture)** — add `T/test_profile_fixtures.py::test_the_both_foe_slots_board_is_byte_stable`
  that calls `board("mega_decision_both_foe_slots_fixture")` and pins its `fixture_input_hash`.
  **Run:** `python -m pytest tests/test_profile_fixtures.py -q --tb=line -rs`
  → **fails**: `"mega_decision_both_foe_slots_fixture"` is not a key in `BOARDS` (`KeyError`).
- [ ] **GREEN (fixture)** — `SRC/eval/profile_fixtures.py`: add `_board_both_foe_slots()` (two foe-Mega
  holders, one in each slot; own Mega present so a foe-Mega branch is scored in both), register in
  `BOARDS` as `"mega_decision_both_foe_slots_fixture"` (joins `FIXTURE_HASHES` at import). Re-run
  `tests/test_profile_fixtures.py` → green; record the pinned `fixture_input_hash` in the test.
- [ ] **RED** — `T/test_coverage_origin_telemetry.py` (offline; each scores a board via
  `ProfileSession.score()` / `score_evaluated_variants(..., shape_sink=shape)`):
  - `test_foe_slot0_board_fills_foe_mega_slots_with_0` — `_board_dual_unequal` ⇒ `shape.foe_mega_slots
    == (0,)`, `shape.foe_mega_order_tie is False`.
  - `test_foe_slot1_board_fills_foe_mega_slots_with_1` — `_board_foe_slotb` ⇒ `(1,)`.
  - `test_both_foe_slots_board_fills_0_and_1` — `_board_both_foe_slots` ⇒ `(0, 1)`.
  - `test_tie_board_sets_order_tie_true_only_when_both_reversed_orderings_are_scored` — `_board_tie` ⇒
    `shape.foe_mega_order_tie is True` **and** `shape.foe_mega_slots != ()`, **because both** mutually-
    reversed `0.5`-weighted activation orderings of the foe-Mega interaction were scored.
  - `test_a_single_05_branch_alone_does_not_set_order_tie` — a foe-Mega interaction where only **one**
    ordering of a would-be tie pair is scored (inject a partial pair) leaves `foe_mega_order_tie is
    False` (a lone `0.5` branch is not a tie).
  - `test_a_strict_inequality_11_branch_is_not_a_tie` — `_board_dual_unequal` (one `1.0` branch) ⇒
    `foe_mega_order_tie is False`.
  - `test_only_positively_scored_slots_count` — a foe-Mega response at `weight==0` does not add its
    slot.
  - `test_an_aborted_scoring_leaves_the_cell_fields_at_defaults` — if `score_evaluated_variants` raises
    partway (inject a failure after the first branch), the sink's `foe_mega_slots == ()` and
    `foe_mega_order_tie is False` (cells are finalized only on successful completion).
  - **Run (RED):** `python -m pytest tests/test_coverage_origin_telemetry.py -q --tb=line -rs`
    → **fails**: `shape.foe_mega_slots`/`foe_mega_order_tie` stay at their defaults (origin does not fill
    them yet).
- [ ] **GREEN** — `SRC/battle/mega_scoring.py`, in `score_evaluated_variants`:
  - Accumulate the scored foe slots (L549-552, `{r.foe_mega_slot for r in resps if r.foe_mega_slot is not None and r.weight>0}`) and the tie flag into
    **local** accumulators as branches are scored. **`order_tie` requires the complete pair:** set the
    tie flag **only** when a scored foe-Mega interaction emitted the **two** mutually-reversed activation
    orderings each at weight `0.5` (the `is_tie` pair in `compose_mega_projection_branches`, L201-203)
    **and both were scored** — a single `0.5` branch, or a strict-inequality `1.0` branch, is **not** a
    tie. (Track per foe-Mega line the set of scored ordering keys; the flag is true iff that set is the
    full reversed pair.)
  - **Write them onto `shape_sink` only at the successful completion of scoring** (the normal return of
    `score_evaluated_variants`) — so a decision whose scoring aborts/raises leaves
    `shape_sink.foe_mega_slots == ()` and `foe_mega_order_tie is False`. A cell is thus recorded **only
    for a fully, successfully scored decision** (and, downstream, counted only for `outcome=="ok"` rows,
    Task 3) — never for a partial/aborted scoring.
  - **Byte-identical decisions:** only `shape_sink` is written — no ordering/selection/scoring change.
- [ ] **Golden decision-equivalence + full suite (behavior-neutral checkpoint):**
  - `python -m pytest tests/test_mega_shape_counts.py tests/i7b/test_i7b_scoring.py tests/test_i8d_shape_threading.py tests/test_coverage_origin_telemetry.py -q --tb=line -rs`
    (incl. `test_shape_sink_none_is_byte_identical_to_a_scored_run`); add
    `test_filling_the_new_fields_leaves_the_chosen_action_and_six_counts_identical`.
  - `python -m pytest -q` → Task-0 pass count **+** the new tests; skip/xfail set unchanged.
- [ ] `git diff --check`; **commit:**
  `battle(mega-scoring): fill foe-Mega slot/order-tie telemetry at origin + both-foe-slots fixture (behavior-neutral)`.

---

## Task 3 — validated per-cell counts over the v3 live dataset *(req 3)*

**Files:** create `SRC/eval/coverage.py`; create `T/test_coverage_cell_counts.py`; touch
`T/test_i8d_live_dataset_validator.py`.

Cells (spec §2.1): `slot0 ⇔ 0∈foe_mega_slots`, `slot1 ⇔ 1∈foe_mega_slots`,
`both_foe_slots ⇔ {0,1}⊆foe_mega_slots`, `order_tie ⇔ foe_mega_order_tie is True`. Counting is over
**active-valid** rows only (`outcome=="ok"`, i.e. successfully scored), and **must never count malformed
JSONL**. (The safety signal is **not** in this dataset — it is server-authoritative, Task 6.)

- [ ] **RED** — `T/test_coverage_cell_counts.py`:
  - `test_coverage_cell_counts_returns_decisions_and_distinct_battles_per_cell` — a synthetic v3 live
    JSONL ⇒ `coverage_cell_counts(path)` returns `{cell: {"decisions": int, "distinct_battles": int}}`
    for the four cells.
  - `test_malformed_jsonl_is_rejected_not_counted` — a file with a truncated/invalid JSON line makes
    `coverage_cell_counts(path)` raise `DecisionProfileError` (it validates first); nothing is counted.
  - `test_only_active_valid_rows_count` — inactive / `outcome!='ok'` / non-`agent_choose` rows excluded.
  - `test_a_non_ok_decision_credits_no_cell` — a row with `foe_mega_active is True` but
    `outcome=="crash"` (or `"fallback"`) credits **no** cell (a cell requires successful scoring).
  - `test_both_foe_slots_also_credits_slot0_and_slot1`; `test_distinct_battles_dedupes_by_battle_id`.
  - `test_the_live_dataset_validator_accepts_a_v3_dataset` (in `T/test_i8d_live_dataset_validator.py`).
  - **Run (RED):** `python -m pytest tests/test_coverage_cell_counts.py tests/test_i8d_live_dataset_validator.py -q --tb=line -rs`
    → **fails**: `SRC/eval/coverage.py` does not exist.
- [ ] **GREEN** — `SRC/eval/coverage.py`: `coverage_cell_counts(path: str) -> dict[str, dict[str,int]]`.
  It **calls `validate_live_profile_dataset(path)` first** (rejecting malformed/mixed-version data),
  then tallies cells over `is_active_valid_live_row` rows only.
  `python -m pytest tests/test_coverage_cell_counts.py -q --tb=line -rs` → green.
- [ ] `git diff --check`; **commit:** `eval(coverage): validated per-cell counts over the v3 live dataset`.

---

## Task 4 — engineered panel + team files + schedule + **schedule-linked** constructibility proofs *(req 4)*

**Files (all in this commit's scope):** create `config/eval/panels/panel_champions_coverage_v0.yaml`
(a **standard panel**: teams + splits, exactly the `panel_champions_v0.yaml` schema — **no** new keys);
create the **coverage manifest** `config/eval/coverage/champions_coverage_v0_manifest.json` (a **new
closed schema** holding matchup order, per-matchup `target_cell`, and each coverage team's content
hash); create the engineered team files under `showdown_bot/teams/panel_champions_coverage_v0/*.txt`
**and their `*.packed` siblings**; create `SRC/eval/coverage_schedule.py`; create
`T/test_coverage_schedule.py`, `T/test_coverage_constructibility.py`, `T/test_coverage_manifest.py`.

Per spec §2.4 (D-3): a **touched** engineered panel is allowed and is **strictly separated** from the
future holdout; and **each cell needs a real offline constructibility proof tied to the matchup that
targets it**. **`target_cell` lives in the coverage manifest, not the panel** — the existing panel
schema has no such field, and adding one would break every panel consumer. The manifest declares, per
matchup, its `target_cell ∈ {slot0, slot1, both_foe_slots, order_tie}` (plus matchup order and each
team's content hash); each proof scores that matchup's board offline and asserts the target cell —
proofs, manifest, and schedule are one unit.

**Separation from the holdout is not asserted here (it would be vacuous).** Gate A does not know the
holdout teams (a later, separate plan). Its only obligation is to **freeze its own coverage team
content hashes in the coverage manifest**; the **holdout plan proves disjointness against these frozen
coverage hashes** — that is where the disjointness check belongs, with real teams on both sides.

**Panel identity & split — fixed decision.** `panel_champions_coverage_v0` is a **new, standalone panel
with its own identity**, never a slice of the existing engineered `panel_champions_v0`. The split is
named concretely on both edges:
- **Named membership — one hero + four foe teams, nothing else.** The **hero** is the candidate team
  `teams/fixed_champions_v0.txt`, **referenced at its canonical path** (it *is* the candidate identity, so
  it is not copied — `panel_champions_v0` likewise keeps it "not in panel"). The **four foe teams** are the
  files `teams/panel_champions_coverage_v0/{cov_foe_slot0, cov_foe_slot1, cov_foe_both, cov_foe_tie}.txt`,
  one per cell.
- **YAML dev/heldout schema — determined (a loader formality).** `load_panel` (`eval/panel.py:118`)
  **requires both `dev_teams` and `heldout_teams` non-empty**, no team in both, each entry exactly
  `{team_id, team_path, archetype}` (`_TEAM_REQUIRED`, `panel.py:19`), plus a non-empty `policies` list of
  known policies (`eval/policies.POLICIES`) and a `version`. Coverage has **no** train/test semantics, so
  the split is a **fixed formality** frozen in the `panel_hash`: `dev_teams = [cov_foe_slot0,
  cov_foe_slot1]`, `heldout_teams = [cov_foe_both, cov_foe_tie]`, `policies: [heuristic, max_damage]`,
  `version: champions-coverage-v0`. The gate **never reads the split** — schedule and cell targeting come
  **entirely from the manifest's `target_cell`s**, which reference teams across the full `dev ∪ heldout`
  registry.
- **Own identity + own storage.** Its own `panel_hash` (over `panel_champions_coverage_v0.yaml`), its own
  `COVERAGE_EXPECTED_MANIFEST_HASH` and `schedule_hash`, its own foe-team directory
  `teams/panel_champions_coverage_v0/`, and — only when a run is later separately frozen — its own output
  subtree `data/eval/champions-panel-v0/coverage-v0/` (spec §2.4), disjoint from the strength subtree. The
  manifest freezes the `team_content_hash` of the hero **and** all four foe teams.
- **Split edge 1 — Coverage ⟂ the new six-team Strength holdout (D-1a): strictly disjoint by
  `team_content_hash`.** The four `cov_foe_*` hashes plus the hero's, frozen in the coverage manifest, are
  the exact reference the holdout plan checks its six blind teams against; no team may appear on both
  sides. This is the load-bearing firewall. (The holdout here is the *new blind six*, **not**
  `panel_champions_v0`'s own internal dev/held-out split.)
- **Split edge 2 — Coverage ↔ `panel_champions_v0`: deliberate content reuse, not a firewall.**
  `cov_foe_slot0`/`cov_foe_slot1` are byte-copies of `teams/panel_champions_v0/{rain_offense, goodstuff}.txt`
  and the hero is shared, so their content hashes deliberately **coincide** with those panel teams. That
  overlap is explicitly **allowed** (D-3) because coverage only *exercises* the opp-Mega path and makes
  **no strength claim**; the coverage panel is **never** consumed by a strength schedule and never
  contributes to a strength verdict.

**Grounded cell cores** (from the offline fixtures, which pin the exact Champions-Mega species/speeds):
`slot0` = a foe **Meganium @ Meganiumite** (~145) slot-0 active vs the hero Aerodactyl-Mega (as
`_board_dual_unequal`); `slot1` = a foe **Aerodactyl @ Aerodactylite** (~200) slot-1 active behind a
non-Mega slot 0 (as `_board_foe_slotb`); `order_tie` = hero **Aerodactyl @ Aerodactylite** (200) vs a
foe **Aerodactyl @ Aerodactylite** (200) → exact pre-mega speed tie → two `0.5` orderings (as
`_board_tie`); `both_foe_slots` = a foe with **two** active Mega-capable mons.

- [ ] **RED** — `T/test_coverage_constructibility.py` (each builds the board for the panel matchup
  targeting the cell, scores it offline, asserts the cell on the resulting `MegaShapeCounts`):
  - `test_slot0_matchup_is_constructible` — the `slot0` matchup ⇒ `0 ∈ shape.foe_mega_slots`.
  - `test_slot1_matchup_is_constructible` — the `slot1` matchup ⇒ `1 ∈ shape.foe_mega_slots`.
  - `test_both_foe_slots_matchup_is_constructible` — ⇒ `shape.foe_mega_slots == (0, 1)`.
  - `test_order_tie_matchup_is_constructible` — ⇒ `shape.foe_mega_order_tie is True` and **exactly two**
    activation orderings @ weight `0.5` were scored (assert via `compose_mega_projection_branches`).
  - `test_every_manifest_matchup_has_a_target_cell_and_a_proof` — the coverage manifest's
    matchup→`target_cell` map covers all four cells and every matchup listed has a corresponding proof.
  - **Run (RED):** `python -m pytest tests/test_coverage_constructibility.py -q --tb=line -rs`
    → **fails**: the coverage manifest + its board bindings do not exist yet.
- [ ] **RED** — `T/test_coverage_manifest.py`:
  - `test_the_manifest_has_a_closed_schema` — unknown keys are rejected; required keys
    (`matchups` [ordered], each with `hero_team`/`opp_team`/`opp_policy`/`target_cell`,
    `team_content_hashes`) are required.
  - `test_the_coverage_manifest_freezes_its_team_content_hashes` — the manifest pins each coverage
    team's content hash (the frozen record the holdout plan later checks disjointness against; **no**
    vacuous holdout-registry assertion here).
  - **Run (RED):** `python -m pytest tests/test_coverage_manifest.py -q --tb=line -rs`
    → **fails**: the manifest + its loader/validator do not exist yet.
- [ ] **RED** — `T/test_coverage_schedule.py` (mirror `test_i8d_schedule.py` /
  `test_i8d_schedule_verify.py`):
  - `test_build_coverage_schedule_targets_all_four_cells` — from the standard panel
    `panel_champions_coverage_v0` **plus** the coverage manifest, `build_coverage_schedule(...)` yields a
    content-hashed schedule whose matchups (ordered by the manifest) cover the four `target_cell`s.
  - `test_the_coverage_panel_loads_with_the_fixed_dev_heldout_split` — `load_panel(COVERAGE_PANEL_PATH)`
    succeeds and returns `dev_teams == (cov_foe_slot0, cov_foe_slot1)`, `heldout_teams == (cov_foe_both,
    cov_foe_tie)`, `policies == (heuristic, max_damage)` — the non-empty split `load_panel` requires
    (`panel.py:118`) is present and frozen in the `panel_hash`.
  - `test_the_200_battle_composition_is_frozen_25_per_matchup` — the schedule is exactly 200 battles,
    **exactly 25 per manifest matchup** (8 × 25 = 200), in the pre-registered manifest order; a
    truncated/reshaped schedule is rejected by `verify_coverage_schedule` (mirrors
    `test_distribution_is_exactly_34_34_33_33_33_33`).
  - `test_verify_coverage_schedule_recomputes_the_hash`,
    `test_verify_coverage_panel_and_teams_rehashes_from_disk`.
  - **Run (RED):** `python -m pytest tests/test_coverage_schedule.py -q --tb=line -rs`
    → **fails**: `SRC/eval/coverage_schedule.py` does not exist.
- [ ] **GREEN** —
  - Author the engineered teams (`showdown_bot/teams/panel_champions_coverage_v0/*.txt` + `.packed`),
    tournament-legal `gen9championsvgc2026regma`, compositions selected to force each cell (may reuse
    `rain_offense`'s Mega-capable species). Their content hashes are frozen **in the coverage manifest**
    for the holdout plan to later check disjointness against — see the team/manifest specification below.
  - Author `config/eval/panels/panel_champions_coverage_v0.yaml` as a **standard panel** loadable by
    `load_panel` — `version: champions-coverage-v0`, `policies: [heuristic, max_damage]`,
    `dev_teams: [cov_foe_slot0, cov_foe_slot1]`, `heldout_teams: [cov_foe_both, cov_foe_tie]` (each entry
    exactly `{team_id, team_path, archetype}`); own `panel_hash`; **no `target_cell`** (that lives in the
    manifest). The dev/heldout split is the loader formality fixed above; the gate reads teams from the
    manifest, never the split.
  - Author `config/eval/coverage/champions_coverage_v0_manifest.json` (closed schema): ordered
    `matchups` (each `hero_team`/`opp_team`/`opp_policy`/`target_cell`) + `team_content_hashes`; pin its
    own manifest hash.
  - `SRC/eval/coverage_schedule.py`: constants `COVERAGE_SEED_BASE = "champions-coverage-v0"`,
    `COVERAGE_FORMAT = "gen9championsvgc2026regma"`,
    `COVERAGE_PANEL_PATH = "config/eval/panels/panel_champions_coverage_v0.yaml"`,
    `COVERAGE_MANIFEST_PATH = "config/eval/coverage/champions_coverage_v0_manifest.json"`,
    `COVERAGE_EXPECTED_PANEL_HASH` and `COVERAGE_EXPECTED_MANIFEST_HASH` (pin the computed hashes);
    `load_coverage_manifest(path: str = COVERAGE_MANIFEST_PATH) -> CoverageManifest` (closed-schema
    validate); `build_coverage_schedule(panel: Panel, manifest: CoverageManifest, *, n_battles: int = COVERAGE_MAX_BATTLES, teams_root: str = ".") -> Schedule`;
    `verify_coverage_schedule(schedule: Schedule, *, expected_battles: int = COVERAGE_MAX_BATTLES) -> None`;
    `verify_coverage_panel_and_teams(schedule, *, teams_root: str, expected_panel_hash: str = COVERAGE_EXPECTED_PANEL_HASH) -> None`
    (mirror `i8d_schedule`). Register each manifest `target_cell → board` binding used by the proofs.
  - All three Task-4 commands (constructibility, manifest, schedule) → green.

### Legality finding + team/manifest specification (Option A grounding, `f8ac140`, read-only)

**Two-Mega legality — AUTHORITATIVE, does NOT fail-close.** `gen9championsvgc2026regma` (mod
`championsregma inherit champions`) uses `ruleset: ['Flat Rules', 'VGC Timer', 'Open Team Sheets']`
with no own banlist. The champions Flat Rules (`data/mods/champions/rulesets.ts` L28-33) add
**`Item Clause = 1`** — which bans *the same* item held more than once, **not** two *different* items.
There is **no Mega Clause / Mega-count limit** (mega mechanic `data/mods/champions/scripts.ts`
`canMegaEvo` L184-196 checks only each mon's own stone; no `onValidateTeam` counting). Two proofs:
`showdown_bot/teams/fixed_champions_v0.txt` already runs **Scovillain @ Scovillainite + Aerodactyl @
Aerodactylite** as co-active leads (`PROVENANCE.md` L50, `validation_exit 0`); a read-only
`validate-team gen9championsvgc2026regma` on it returned exit 0. `both_foe_slots` = the bot scoring
**two alternative** foe-Mega slot-hypotheses (either co-active foe mon *could* Mega; only one Megas per
battle) — **legally constructible**.

**Grounded Mega speeds (Mega-forme base Speed):** Aerodactyl-Mega **150** (Aerodactylite),
Meganium-Mega **80** (Meganiumite), Delphox-Mega 134, Scovillain-Mega 75 (full roster from
`data/items.ts` `megaStone` + `data/pokedex.ts` `baseStats.spe`; M-A excludes the `championsregma/items.ts`
re-disabled `Future`/`Past` stones — e.g. Blaziken/Metagross/Swampert megas — and Flat-Rules-banned
Mythical/Restricted-Legendary megas).

**Coverage hero (candidate) team — all matchups:** the existing, validated
`teams/fixed_champions_v0.txt` (its Aerodactyl @ Aerodactylite, Jolly / 32 Atk / 32 Spe / 2 HP, is the
own-Mega for `order_tie`).

**Four format-legal coverage foe teams** (Level 50, champions `32/32/2` spreads, default 31 IVs;
two reuse already-**validated** legal panel teams, two are new-from-validated-legal mons and get their
own `validate-team` gate in GREEN):

| Team file (under `teams/panel_champions_coverage_v0/`) | target_cell | Mega core → cell mechanism | basis |
|---|---|---|---|
| `cov_foe_slot0.txt` | `slot0` | Meganium @ Meganiumite (Overgrow, Modest; Solar Beam/Weather Ball/Dazzling Gleam/Protect) + Pelipper\@Focus Sash, Archaludon\@Leftovers, Kingambit\@Chople, Basculegion\@Choice Scarf, Sneasler\@White Herb | = validated `rain_offense.txt` |
| `cov_foe_slot1.txt` | `slot1` | Delphox @ Delphoxite (Blaze, Timid; Heat Wave/Psyshock/Encore/Protect) + Incineroar\@Sitrus, Garchomp\@Haban, Kingambit\@Chople, Sneasler\@White Herb, Rotom-Wash\@Leftovers | = validated `goodstuff.txt` |
| `cov_foe_both.txt` | `both_foe_slots` | **two** Megas: Aerodactyl @ Aerodactylite (Jolly) **+** Meganium @ Meganiumite (Modest) + Kingambit\@Chople, Sneasler\@Focus Sash, Basculegion\@Choice Scarf, Garchomp\@Sitrus | NEW (legal mons) → `validate-team` gate |
| `cov_foe_tie.txt` | `order_tie` | Aerodactyl @ Aerodactylite (Jolly / 32 Atk / 32 Spe / 2 HP — **identical spread to the hero's Aerodactyl** → exact pre-mega speed tie) + Garchomp\@Sitrus, Kingambit\@Chople, Sneasler\@White Herb, Basculegion\@Choice Scarf, Pelipper\@Focus Sash | NEW (legal mons) → `validate-team` gate |

**Full sets for the two NEW teams — every mon is copied *verbatim* from a validated existing block**
(so each set's species/item/ability/nature/moves/EVs/IVs is fully pinned by the source; all six items
per team are distinct → `Item Clause = 1` holds; all six species distinct → Species Clause holds):

- **`cov_foe_both.txt`** (two Megas): **Aerodactyl @ Aerodactylite** ← copy the Aerodactyl block of
  `fixed_champions_v0.txt`; **Meganium @ Meganiumite** ← the Meganium block of `rain_offense.txt`;
  **Kingambit @ Chople Berry** ← the Kingambit block of `rain_offense.txt`; **Sneasler @ Focus Sash** ←
  the Sneasler block of `fixed_champions_v0.txt`; **Basculegion @ Choice Scarf** ← the Basculegion block
  of `fixed_champions_v0.txt`; **Garchomp @ Sitrus Berry** ← the Garchomp block of `fixed_champions_v0.txt`.
- **`cov_foe_tie.txt`** (one Mega, speed-matched to hero): **Aerodactyl @ Aerodactylite** ← copy the
  Aerodactyl block of `fixed_champions_v0.txt` **byte-for-byte** (identical spread ⇒ exact pre-mega
  speed tie with the hero's Aerodactyl); **Garchomp @ Sitrus Berry** ← `fixed_champions_v0.txt`;
  **Kingambit @ Chople Berry** ← `goodstuff.txt`; **Sneasler @ White Herb** ← `rain_offense.txt`;
  **Basculegion @ Choice Scarf** ← `fixed_champions_v0.txt`; **Pelipper @ Focus Sash** ← `rain_offense.txt`.

Each `.txt` gets its committed `.packed` sibling. The **coverage manifest**
`config/eval/coverage/champions_coverage_v0_manifest.json` (closed schema) pins the **ordered** matchups
— the four cells in order, hero `fixed_champions_v0` throughout: `slot0` (`opp:"cov_foe_slot0"`), `slot1`
(`opp:"cov_foe_slot1"`), `both_foe_slots` (`opp:"cov_foe_both"`), `order_tie` (`opp:"cov_foe_tie"`), each
crossed with both `{heuristic, max_damage}` opponent policies (**8 matchups** = 4 cells × 2 policies) —
plus each team's `team_content_hash` (computed in GREEN). **The 200-battle composition is pre-registered:**
the schedule cycles these 8 manifest matchups over exactly `COVERAGE_MAX_BATTLES = 200` battles →
**exactly 25 battles per matchup**, a fixed composition frozen by `schedule_hash` (as I8-D's
`34/34/33/33/33/33` distribution is frozen), never chosen ad-hoc or reshaped post-run.
The **board proofs** (§2.4) build the exact per-cell board from each foe team's Mega core:
`slot0`/`slot1` place the single Mega in slot a=0 / b=1; `both_foe_slots` co-actives both Megas → scored
slot set `{0,1}`; `order_tie` pairs the hero Aerodactyl vs the foe Aerodactyl at equal speed → the two
`0.5` orderings. **`slot0`/`slot1` live exposure is lead-dependent** — the per-cell distinct-battle
floors (§2.3) ensure enough battles hit each; the offline proof only shows constructibility.

- [ ] **GREEN (legality gate) — full Windows PowerShell commands, from the repo root** (the pinned
  clone lives at `$HOME/.cache/showdownbot/pokemon-showdown`, documented in
  `config/eval/provenance.yaml` — the commands derive it from `$HOME`, with no username or
  machine-specific absolute path; each must exit 0 **before commit**; this `validate-team` invocation is
  authorized only when implementing this task, not now):

  ```powershell
  $Launcher = Join-Path $HOME '.cache/showdownbot/pokemon-showdown/pokemon-showdown'
  Get-Content -Raw showdown_bot/teams/panel_champions_coverage_v0/cov_foe_both.packed | node $Launcher validate-team gen9championsvgc2026regma
  if ($LASTEXITCODE -ne 0) { throw "cov_foe_both is not legal in gen9championsvgc2026regma" }
  Get-Content -Raw showdown_bot/teams/panel_champions_coverage_v0/cov_foe_tie.packed  | node $Launcher validate-team gen9championsvgc2026regma
  if ($LASTEXITCODE -ne 0) { throw "cov_foe_tie is not legal in gen9championsvgc2026regma" }
  ```

  The two reused teams (`rain_offense`, `goodstuff`) are already `validation_exit 0`.

- [ ] `git diff --check`; **commit:**
  `config+teams+eval(coverage): standard panel_champions_coverage_v0 + closed-schema coverage manifest (target_cell/hashes) + team files + schedule + four constructibility proofs`.

---

## Task 5 — coverage **verdict**: PASS / FAIL / INCONCLUSIVE (ABORTED off the verdict) *(req 5)*

**Files:** create `SRC/eval/coverage_verdict.py`; create `T/test_coverage_verdict.py`.

Per-cell floors (spec §2.3, D-2): `slot0 30/10`, `slot1 30/10`, `both_foe_slots 15/6`, `order_tie 15/6`.
The verdict reads **dataset-sourced** cell counts (Task 3) and the **server-authoritative**
`safety_violations` count (from the Task-6 runner report) — never a caller-supplied `safety_ok`.

- [ ] **RED** — `T/test_coverage_verdict.py` (mirror `test_i8d_runner.py` verdict tests):
  - `test_coverage_floor_met_is_PASS` — all four cells ≥ their decision **and** distinct-battle floors,
    zero safety violations ⇒ `verdict=="PASS"`, `stop_reason=="coverage_floor_met"`.
  - `test_schedule_exhausted_with_a_cell_below_floor_is_FAIL` — schedule complete, a cell short ⇒
    `verdict=="FAIL"`, `stop_reason=="schedule_exhausted"` (spec §2.6(b) — a defect, not INCONCLUSIVE).
  - `test_a_cap_truncation_before_schedule_end_is_INCONCLUSIVE` — a cap hit before schedule completion,
    a cell short ⇒ `verdict=="INCONCLUSIVE"`, `stop_reason ∈ {"max_battles","max_scored_decisions"}`.
  - `test_a_safety_violation_is_FAIL_with_its_own_stop_reason` — `safety_violations > 0` (the
    server-authoritative count from the runner report) ⇒ `verdict=="FAIL"` **and**
    `stop_reason=="safety_violation"`, regardless of cell counts.
  - `test_coverage_should_stop_checks_safety_first_then_the_floor_before_the_caps` — `coverage_should_stop`
    returns `(True, "safety_violation")` when `safety_violations>0` **before** the floor/caps (fail-fast);
    otherwise mirrors `test_should_stop_fires_on_d1_before_the_caps_and_names_it`.
  - **Run (RED):** `python -m pytest tests/test_coverage_verdict.py -q --tb=line -rs`
    → **fails**: `SRC/eval/coverage_verdict.py` does not exist.
- [ ] **GREEN** — `SRC/eval/coverage_verdict.py`:
  - `COVERAGE_CELL_FLOORS = {"slot0": (30,10), "slot1": (30,10), "both_foe_slots": (15,6), "order_tie": (15,6)}`.
  - `coverage_floor_met(cell_counts: dict) -> bool` (every cell ≥ its `(decisions, distinct_battles)`).
  - `coverage_should_stop(*, battles_played: int, scored_decisions: int, cell_counts: dict, safety_violations: int) -> tuple[bool,str|None]`
    — order: **`safety_violations > 0` → `"safety_violation"` (first, fail-fast)**, then floor →
    `"coverage_floor_met"`, `"max_battles"` (≥ `COVERAGE_MAX_BATTLES`), `"max_scored_decisions"`
    (≥ `COVERAGE_MAX_SCORED_DECISIONS`), else `(False, None)`.
  - `coverage_verdict(*, cell_counts: dict, safety_violations: int, schedule_complete: bool, stop_reason: str) -> dict`
    — **`FAIL` with `stop_reason=="safety_violation"` if `safety_violations > 0`**; else `PASS`
    (`stop_reason=="coverage_floor_met"`) if all cells meet floor; else `FAIL` if `schedule_complete`
    (a `schedule_exhausted` shortfall); else `INCONCLUSIVE` (a `max_battles`/`max_scored_decisions`
    truncation). Stop-reasons are thus one-to-one with the verdict:
    `safety_violation→FAIL`, `coverage_floor_met→PASS`, `schedule_exhausted→FAIL`, cap→`INCONCLUSIVE`.
    A technical abort is never routed here (the runner voids it, Task 6).
  - `python -m pytest tests/test_coverage_verdict.py -q --tb=line -rs` → green.
- [ ] `git diff --check`; **commit:** `eval(coverage): three-way verdict + stop-reasons (dataset-sourced cells + server-authoritative safety)`.

---

## Task 6 — coverage **runner** + foe-Mega-bound hero safety seam: derived provenance, locked panel, caps, atomic publish *(req 6)*

**Files:** extend `SRC/client/gauntlet.py` (bounded, additive per-seat safety field); create
`T/test_gauntlet_hero_invalid.py`, `SRC/eval/coverage_runner.py`, `T/test_coverage_runner.py`.

Mirror `i8d_runner.run_i8d_live_gate` **structurally**, unit-tested with **injected** per-battle
profiles (no live gauntlet). **Provenance is derived internally, never caller-supplied; the panel and
out-dir are locked.** **Safety is per-seat AND foe-Mega-bound:** the gauntlet's per-battle
`invalid_choices` is the **sum** `hero.invalid + villain.invalid` (`gauntlet.py:1354`/`:1424`), blind to
seat; and a coverage safety violation is specifically a **hero** illegal choice **on a foe-Mega
decision**, not any illegal choice on any turn. The first step below records the `decision_index` of each
hero invalid choice on `GauntletStats`; the runner then **joins** it to that decision's `foe_mega_active`
so only a foe-Mega-decision illegal choice FAILs the gate.

- [ ] **RED** — `T/test_gauntlet_hero_invalid.py` (the safety seam must be **hero-specific** *and* must
  stay **off** the closed T2 result row — it rides the in-memory `GauntletStats`, not
  `_battle_result_record`):
  - `test_gauntlet_stats_records_the_decision_index_of_each_hero_invalid_choice` — a
    `run_local_gauntlet(games=1, …)` where the **hero** emits a server-rejected illegal choice on decision `k` yields
    `stats.hero_invalid_decision_indices == (k,)` (the index recorded **per room at send time**, alongside
    `last_choose[room]`, `gauntlet.py:700`).
  - `test_the_recorded_index_is_the_rejected_choice_not_the_advanced_counter` — the sequencing case: the
    server `|error|` for decision `k`'s choice arrives **after** `decision_seq` has advanced (a retry makes
    the live counter `k+1`), yet `stats.hero_invalid_decision_indices == (k,)`, **not** `(k+1,)` — proving
    the attribution reads the per-room send-time record, not the since-advanced counter.
  - `test_an_opponent_invalid_choice_is_not_recorded_for_the_hero` — a `run_local_gauntlet(games=1, …)` run
    where only the **villain** emits one yields `stats.hero_invalid_decision_indices == ()` **while** the summed
    `stats.invalid_choices == 1` (proves the list reads the hero seat, not `hero.invalid + villain.invalid`).
  - `test_the_closed_t2_result_row_and_writer_are_untouched` — `_battle_result_record(...)` returns **no**
    new key, and `eval/result_jsonl.py`'s `REQUIRED_FIELDS`/`NULLABLE_FIELDS` allowlist is unchanged — so
    the closed row writer that I8-D shares never sees a new key.
  - `test_an_unattributable_error_records_a_fail_closed_sentinel` (**Guard 1**) — a hero `|error|` for a
    room with **no** recorded send-time index appends a fail-closed sentinel (`-1`) to
    `hero_invalid_decision_indices` — **never** silently dropped — so the runner's join (Guard 3) turns it
    into an abort rather than ignore a possible foe-Mega illegal choice.
  - **Run (RED):** `python -m pytest tests/test_gauntlet_hero_invalid.py -q --tb=line -rs`
    → **fails**: `GauntletStats` has no `hero_invalid_decision_indices` attribute.
- [ ] **GREEN** — `SRC/client/gauntlet.py` (bounded, additive; **only the in-memory stats dataclass**):
  - **Attribution mechanism (the sequencing fix).** The server `|error|` for an illegal choice arrives
    **after** the choice was sent and after `decision_seq` has advanced, so the *current* counter no longer
    names the rejected decision. Mirror the existing `last_choose[room]` seam: at the send point
    (`self.last_choose[room] = choose`, `gauntlet.py:700`, where `decision_seq` is in scope) also record
    `self._last_choice_decision_index[room] = decision_seq` — the index of the choice just sent for that
    room. The `|error|` handler already reads `last_choose[parsed.room]` (`gauntlet.py:940`); at that same
    `_is_real_invalid` → `client.invalid += 1` point (`gauntlet.py:936`) append
    `client._last_choice_decision_index[parsed.room]` (the SENT choice's index, **never** the advanced
    counter) to the hero list. **Guard 1 (complete attribution, fail-closed):** if that room has **no**
    recorded index (an unattributable `|error|` — which the protocol should never produce, since every
    rejection follows a send), append the fail-closed sentinel `-1` **instead of silently skipping**, so
    the runner's join (Guard 3) turns it into an abort.
  - `GauntletStats` (L223-230) gains `hero_invalid_decision_indices: tuple[int, ...] = ()`, accumulated
    from those per-room recorded indices. Because the coverage runner **invokes `run_local_gauntlet(games=1, …)`**
    (as I8-D does), each call plays exactly one battle, so the list is exactly that battle's hero-invalid
    decisions and the runner can fail-fast on the offending battle.
  - **`_battle_result_record` and `eval/result_jsonl.py` are NOT touched** — no key is added to the closed
    T2 row, so the shared writer and every I8-D row stay byte-identical.
  - **Behaviour-neutrality gate:** `python -m pytest tests/test_gauntlet_battle_result.py tests/test_result_jsonl.py -q`
    — the closed-row builder and its writer/allowlist tests still pass unchanged.
  - `python -m pytest tests/test_gauntlet_hero_invalid.py -q --tb=line -rs` → green.
- [ ] **RED** — `T/test_coverage_runner.py` (mirror `test_i8d_runner.py`):
  - `test_caps_are_200_and_2000` — `COVERAGE_MAX_BATTLES == 200`, `COVERAGE_MAX_SCORED_DECISIONS == 2000`.
  - `test_resolve_coverage_provenance_derives_from_repo_and_env_and_refuses_dirty` — a dirty tree /
    unknown `SHOWDOWN_CALC_BACKEND` fail closed; the returned dict has `git_sha`, `config_hash`,
    `calc_backend`, `hero_agent`, and a derived `candidate_identity` — and takes **no** provenance
    argument from the caller.
  - `test_the_runner_does_not_accept_caller_supplied_git_sha_or_config_hash` — `run_coverage_gate`'s
    signature has no `git_sha`/`config_hash`/`candidate_identity` parameter; it calls
    `resolve_coverage_provenance()`.
  - `test_the_panel_is_locked_to_the_coverage_panel` — the runner uses `COVERAGE_PANEL_PATH` /
    `COVERAGE_EXPECTED_PANEL_HASH` (not a caller path) and re-hashes teams before battle 1.
  - `test_output_dir_is_published_atomically_and_verdict_equals_return` — with injected battle profiles,
    it stages `{out_dir}.staging`, adopts each validated battle atomically, does a single
    `os.replace(staging, out_dir)`; `verdict.json` on disk equals the returned dict.
  - `test_the_runner_refuses_a_leftover_staging_or_out_dir`.
  - `test_the_out_dir_may_not_be_under_data_eval` — `run_coverage_gate` refuses an `out_dir` inside
    `data/eval/` (live output never lands directly in frozen-evidence storage).
  - `test_a_hero_illegal_choice_on_a_foe_mega_decision_is_a_safety_violation` — an injected per-battle
    `GauntletStats` with `hero_invalid_decision_indices == (k,)` where the battle's decision dataset marks
    decision `k` `foe_mega_active == True` (our candidate emitted a server-rejected illegal choice **on a
    foe-Mega decision**) sets `report["safety_violations"] > 0` and drives verdict `FAIL` with
    `stop_reason=="safety_violation"`.
  - `test_a_hero_illegal_choice_on_a_non_foe_mega_decision_is_not_a_coverage_safety_violation` — an
    injected `GauntletStats` with `hero_invalid_decision_indices == (m,)` where decision `m` is
    `foe_mega_active == False` does **not** raise `report["safety_violations"]` and does **not** FAIL: an
    illegal choice unrelated to foe-Mega is a general-legality concern, **out of this gate's scope**.
  - `test_an_opponent_invalid_choice_is_never_a_candidate_safety_violation` — an injected `GauntletStats`
    with the summed `invalid_choices > 0` **but** `hero_invalid_decision_indices == ()` (the **opponent**
    made the illegal choice) does **not** raise `report["safety_violations"]` and does **not** FAIL.
    (Client-side `battle/legal_actions` is only what the bot *chooses from*; the server `|error|` frame,
    reduced **per seat and joined to `foe_mega_active`**, is the authority.)
  - `test_the_runner_invokes_run_local_gauntlet_with_games_1` — the injected `run_local_gauntlet` stub
    **requires** `games == 1` (it raises if called with anything else), proving the coverage runner passes
    `games=1` on every per-battle call (`games` is a **required** parameter, `gauntlet.py:1176`).
  - `test_a_battle_that_did_not_complete_exactly_one_game_is_discarded_fail_closed` (**Guard 2**) — an
    injected `run_local_gauntlet` returning `stats.games != 1` (e.g. a timeout with `games == 0`) discards
    the battle's staged artifacts **and** its `hero_invalid_decision_indices` (never adopted) and raises a
    technical `CoverageRunError` → restart from seed 0, **no verdict** (mirrors `i8d_runner.py:330`).
  - `test_an_unjoinable_hero_invalid_index_aborts_fail_closed` (**Guard 3**) — an injected battle whose
    `hero_invalid_decision_indices` holds an index with **no matching row present** in the battle's
    validated decision dataset (a dropped best-effort profile write, or the `-1` sentinel) does **not**
    silently pass: the runner **aborts** (technical: no `out_dir`, no `verdict.json`). An index that **does**
    resolve to a present row is judged by that row's `foe_mega_active` — `True` → violation, `False` →
    out of scope — and is **never** aborted (this is the non-foe-Mega path, which must be ignored, not
    aborted).
  - `test_a_technical_abort_publishes_no_out_dir_and_records_no_verdict`.
  - `test_seed_alignment_is_verified`.
  - **Run (RED):** `python -m pytest tests/test_coverage_runner.py -q --tb=line -rs`
    → **fails**: `SRC/eval/coverage_runner.py` does not exist.
- [ ] **GREEN** — `SRC/eval/coverage_runner.py`:
  - `resolve_coverage_provenance(*, hero_agent: str = "heuristic", format_id: str = COVERAGE_FORMAT) -> dict`
    — mirror `resolve_i8d_provenance` (derive `git_sha`/dirty guard, `config_hash`, normalize
    `calc_backend`), then compute the candidate identity from a **canonical, unambiguous serialization**:
    `candidate_identity = sha1(json.dumps({"hero_agent": hero_agent, "git_sha": git_sha, "config_hash": config_hash}, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:16]`
    — a delimited JSON object, **never** bare string concatenation, so `("a","bc")` and `("ab","c")`
    cannot collide.
  - `COVERAGE_SEED_BASE = "champions-coverage-v0"`, `COVERAGE_MAX_BATTLES = 200`,
    `COVERAGE_MAX_SCORED_DECISIONS = 2000`. **The runner never writes into `data/eval/`:** `out_dir` is a
    caller-supplied run-output location (a scratch/run tree), and `run_coverage_gate` **rejects any
    `out_dir` under `data/eval/`**. Freezing a run's output into
    `data/eval/champions-panel-v0/coverage-v0/` is a **separate, deliberate, separately-authorized
    evidence-freeze commit** (as the I8-D evidence was frozen), never the runner's target.
  - `run_coverage_gate(*, schedule, out_dir: str, seed_log_path: str, calc_backend: str = "oneshot",
    hero_agent: str = "heuristic", expected_battles: int = COVERAGE_MAX_BATTLES,
    expected_panel_hash: str = COVERAGE_EXPECTED_PANEL_HASH, teams_root: str = ".") -> dict` — reuse
    `_write_json_atomic`, `_adopt_battle_atomic`, `DecisionProfileWriter`, `validate_live_profile_dataset`,
    `coverage_cell_counts`, `coverage_should_stop`, `coverage_verdict`, `_verify_seed_alignment`;
    **reject an `out_dir` under `data/eval/`**; **derive** provenance via `resolve_coverage_provenance()`
    and stamp `candidate_identity` into `verdict.json`; source **safety authoritatively, per-seat, and
    foe-Mega-bound** — each `run_local_gauntlet(games=1, …)` call returns a `GauntletStats` whose
    `hero_invalid_decision_indices` are **joined** to that battle's decision dataset: a safety violation is
    a hero index `k` whose decision row is `foe_mega_active == True` (a hero illegal choice **on a foe-Mega
    decision**). Such a violation increments `report["safety_violations"]` and, via `coverage_should_stop`,
    halts the run with `stop_reason=="safety_violation"` (fail-fast). The summed `invalid_choices` and any
    hero index on a non-foe-Mega decision are **never** charged to this gate; the shared closed T2 result
    row (`eval/result_jsonl.py`) is never extended; the client `battle/legal_actions` is only what the bot
    *chooses from* and is never the safety authority.
  - **Fail-closed safety chain (three guards, end-to-end).** A hero illegal choice can never slip to a PASS
    through a missing piece: **Guard 1 (complete attribution)** at the gauntlet seam records a `-1` sentinel
    for any unattributable `|error|`; **Guard 2 (whole-battle only)** — the runner invokes
    `run_local_gauntlet(games=1, …)` (`games` is required, `gauntlet.py:1176`) and, after each call,
    `if stats.games != 1` discards the staged battle **and** its `hero_invalid_decision_indices` and raises
    a technical `CoverageRunError` (restart from seed 0), never adopting a partial battle's
    exposure/decisions/safety signal (mirrors `i8d_runner.py:330`); **Guard 3 (complete join)** — every
    recorded hero-invalid index must resolve to a **present** `(battle_id, decision_index)` row in the
    battle's validated dataset (that key is unique, `decision_profile.py:1080`); a present row is judged by
    its `foe_mega_active` (`True` → violation, `False` → **out of scope, not a violation**), while a
    **missing** row or the `-1` sentinel **aborts** the run (technical: no `out_dir`, no verdict), never a
    PASS. "Present" is deliberately **weaker than "active-valid"** — `is_active_valid_live_row` also
    requires `foe_mega_active is True` (`decision_profile.py:1064`), so a non-foe-Mega decision is a
    present-but-not-active-valid row that must be **ignored, never aborted**. Only when all three guards
    hold does the join reach the `foe_mega_active` verdict.
  - `python -m pytest tests/test_coverage_runner.py -q --tb=line -rs` → green.
- [ ] `git diff --check`; **commit:**
  `eval(coverage): runner + hero-specific safety seam — derived provenance + candidate identity, locked panel, caps 200/2000, atomic publish (offline)`.

---

## Task 7 — provenance-locked CLI command + closeout *(req 7)*

**Files:** modify `SRC/cli.py` (= `showdown_bot/src/showdown_bot/cli.py`); create
`T/test_cli_coverage_gate.py`.

- [ ] **RED** — `T/test_cli_coverage_gate.py` (mirror `test_cli_i8d_gate.py`):
  - `test_command_locks_the_coverage_panel_derives_provenance_and_reaches_the_runner` — the
    `champions-coverage-gate` command hard-locks `COVERAGE_PANEL_PATH`, requires `--out-dir` +
    `SHOWDOWN_EVAL_SEED_LOG` + `SHOWDOWN_BATTLE_SEED_BASE == "champions-coverage-v0"`, calls
    `resolve_coverage_provenance()`, refuses a pre-existing out-dir, and dispatches into
    `run_coverage_gate` — verified with a **stubbed** `run_coverage_gate` (the CLI is never executed
    against a live server).
  - `test_the_command_takes_no_provenance_flags` — there is no `--git-sha`/`--config-hash` argument.
  - **Run (RED):** `python -m pytest tests/test_cli_coverage_gate.py -q --tb=line -rs`
    → **fails**: the `champions-coverage-gate` command is not registered.
- [ ] **GREEN** — register `champions-coverage-gate` in `SRC/cli.py` (mirror the `i8d-live-gate`
  handler L672-704 + parser L716/853 + dispatch L1025), locking the coverage panel and deriving
  provenance; no live invocation. `python -m pytest tests/test_cli_coverage_gate.py -q --tb=line -rs`
  → green.
- [ ] **Closeout gates (from `showdown_bot/`):**
  - `python -m pytest -q` → Task-0 pass count **+** all new tests; skip/xfail set unchanged.
  - `git diff --check` (repo root) clean; `git status` shows only the planned files;
    `git diff --name-only main -- data/eval` **empty** (frozen evidence untouched); staged blobs LF-only.
  - `git grep -n 'decision-profile-v2' -- showdown_bot/src` still resolves (v2 remains valid and
    back-compatible; the microprofile writer still stamps it).
- [ ] `git diff --check`; **commit:**
  `cli(coverage): provenance-locked champions-coverage-gate command (built, never run live)`.

---

## Requirement traceability

| Spec/ask | Task |
|---|---|
| 1 — decision-profile v3 (live-only) + full v1/v2 compat, microprofile stays v2 | Task 1 |
| 2 — origin telemetry `slot0/slot1/both_foe_slots/order_tie` | Task 2 |
| 3 — live validator + per-cell evaluation (validated input, malformed rejected) | Task 3 |
| 4 — engineered coverage panel + team files + four schedule-linked constructibility proofs | Task 4 |
| 5 — PASS/FAIL/INCONCLUSIVE/ABORTED + stop-reasons (safety FAIL dataset-sourced) | Task 5 |
| 6 — caps 200/2000, atomic publish, **derived** candidate-identity provenance, safety signal | Task 6 |
| 7 — full RED→GREEN, exact commands, logical commit boundaries | all tasks + Task 7 |
| 8 — no server/battle/benchmark/live-run | non-goals + every task (offline/injected only) |

## What this plan does **not** do (deferred, separately authorized)

- No coverage **run** — the runner + CLI are built and unit-tested; the first live coverage run is a
  later, separately-authorized step (spec §8), and it, plus the bound **latency re-run on the final
  v3 candidate identity**, must both precede any Strength claim.
- No Strength holdout (Gate B) — separate plan; the six blind-curated teams are its external
  prerequisite.
