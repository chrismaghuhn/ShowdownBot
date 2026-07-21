# Viewer v0 — Plan D: Decision Inspection

**Status:** APPROVED — 2026-07-21 (Rev. 5). Codex review PASS; implementation go-ahead given.
Self-contained; supersedes Rev. 1–4 text (no cross-rev references for acceptance).
**Date:** 2026-07-21 · **Rev.:** 5 · **Approved:** 2026-07-21
**Depends on (code start):** Plan A fixtures **1, 3, 16** under `fixtures/viewer-v0/bundles/`;
Plan B **merged** via PR **#44** (sealed DTOs + `BundleLoader` + `AppShell`);
Plan C **merged** via PR **#46** @ `1b0be1d` (`TimelineController.selection_changed`,
`ReplayWorkspace`, sealed `ReplayDTO` / `TimelineEntryDTO`).
**Unblocks:** Plan E (banner/keyboard polish on D surfaces); Plan F (deep-link E2E freeze).

**Authority:** [`../specs/viewer-v0-design.md`](../specs/viewer-v0-design.md) §3.2 / §5.3–5.4 /
§6.1 / §6.5 / §7 / §9.2,
[`../specs/viewer-v0-bundle-contract-design.md`](../specs/viewer-v0-bundle-contract-design.md)
§9 / §10.2 / §10.4 / §11.1–11.2 / §11.4 / §16,
[`2026-07-21-viewer-v0-implementation-index.md`](2026-07-21-viewer-v0-implementation-index.md) §3 / §5,
[`2026-07-21-viewer-v0-b-godot-shell-and-loader.md`](2026-07-21-viewer-v0-b-godot-shell-and-loader.md)
(APPROVED; **merged** implementation is source of truth for DTO/loader names),
[`2026-07-21-viewer-v0-c-replay-and-timeline.md`](2026-07-21-viewer-v0-c-replay-and-timeline.md)
(APPROVED; **merged** implementation is source of truth for timeline selection),
[`../design/viewer-v0-mockups/README.md`](../design/viewer-v0-mockups/README.md)

> **For agentic workers:** execute task-by-task with TDD (gdUnit4 headless on pinned Godot **4.5.2**).
> No Python exporter changes. No edits under `showdown_bot/`, `data/eval/`, `config/eval/`, or
> `reports/`. No Plan E banners/a11y/layout/diagnostics polish, and no Plan F E2E freeze work.
> This document supersedes Plan D Rev. 1–4 and the prior sketch; do not look up older text for
> acceptance. Depth target: same executable density as Plans A/B/C (closed decisions, full
> GDScript bodies, scene trees, named tests, RED/GREEN tasks, commit boundaries).

---

## 0. Closed decisions (binding)

### 0.1 Verified Plan B + Plan C surface (do not invent)

Verified on `main` @ `1b0be1d` (Plan C tip via PR **#46**). Plan D consumes these exact names:

| Kind | Identifier | Path |
|---|---|---|
| Node | `BundleLoader` | `godot/src/bundle/bundle_loader.gd` |
| States | `BundleLoader.State`: `IDLE`, `LOADING`, `COMPLETED`, `REFUSED`, `CANCELLED` | same |
| Signals | `progress(message: String)`, `completed(bundle: BundleDTO)`, `refused(diagnostic: RefuseDiagnostic)`, `cancelled` | same |
| DTO | `BundleDTO` | `godot/src/bundle/bundle_dto.gd` |
| Fields | `declared_mode`, `effective_mode`, `replay_trusted`, `trace_trusted`, `manifest`, `decisions`, `battle_events`, `warnings`, `downgrade_warnings`, `config_manifest` | BundleDTO |
| DTO | `BundleManifestDTO.battle_id` | `godot/src/bundle/bundle_manifest_dto.gd` |
| DTO | `DecisionRowDTO` (full field list §0.1.1) | `godot/src/bundle/decision_row_dto.gd` |
| DTO | `CandidateDTO` | `godot/src/bundle/candidate_dto.gd` |
| Fields | `candidate_id: String`, `rank: int`, `aggregate_score: float`, `candidate_key: Variant`, `unknown_fields: Dictionary` | CandidateDTO |
| Consts | `BundleMode.REPLAY_TRACE` / `REPLAY_ONLY` / `TRACE_ONLY` | `godot/src/bundle/bundle_mode.gd` |
| Consts | `PHASE_TEAM_PREVIEW` / `PHASE_FORCED_REPLACEMENT` / `PHASE_REGULAR_TURN` | same |
| Node | `AppShell` | `godot/src/workspace/app_shell.gd` |
| Scene | `$VBox/PathRow`, `$VBox/StatusLabel`, `$VBox/ReplayWorkspace`, `$BundleLoader` | `app_shell.tscn` |
| API | `open_bundle_path`, `get_replay_workspace`, `get_loaded_bundle`, `get_trace_trusted`, `get_replay_trusted`, `get_decision_count`, `parse_cli_args`, `is_loading` | AppShell |
| Stub to replace | `cli_decision_index` int-only `--decision` parse; `_selected_decision_index` never written | AppShell @ `1b0be1d` |
| Node | `ReplayWorkspace` | `godot/src/replay/replay_workspace.gd` |
| API | `reset(replay, bundle)`, `clear()`, `set_loading(active)`, `get_timeline_controller()`, `get_timeline_view()`, `get_board_view()`, `get_board_model()` | same |
| Node | `TimelineController` | `godot/src/timeline/timeline_controller.gd` |
| Signals | `selection_changed(entry_index: int)`, `playback_changed(playing: bool)` | same |
| API | `select`, `reset`, `clear`, `step_prev`, `step_next`, `jump_start`, `jump_end`, `play`, `pause`, `toggle_play`, `get_selected_entry_index`, `get_replay`, `get_bundle`, `is_playing` | same |
| DTO | `ReplayDTO`, `TimelineEntryDTO` | `godot/src/replay/replay_dto.gd`, `godot/src/timeline/timeline_entry_dto.gd` |
| Entry fields | `kind`, `event_index`, `decision_row_index`, `protocol_anchor` | TimelineEntryDTO |
| Kinds | `EVENT`, `DECISION`, `DECISION_WITHOUT_REPLAY_EVENT` | `timeline_entry_kind.gd` |
| Join | `BattleTimeline.build(bundle) -> ReplayDTO` | `battle_timeline.gd` |

#### 0.1.1 `DecisionRowDTO` fields Plan D may display

| Field | Type | Notes |
|---|---|---|
| `decision_index` | `int` | Fachliche ID — labels + deep link |
| `turn_number` | `int` | Display |
| `decision_phase` | `String` | Open recorded string |
| `decision_latency_ms` | `float` | Mandatory recorded latency |
| `observable_state_hash` | `String` | |
| `request_hash` | `String` | |
| `state_summary` | `Dictionary` | Sealed/frozen; display keys as recorded |
| `normalized_action` | `Dictionary` | Overview only |
| `actual_choose_string` | `String` | Overview |
| `candidates` | `Array` of `CandidateDTO` | Read-only after seal |
| `chosen_candidate_key` | `Variant` | Opaque structural identity |
| `chosen_candidate_id` | `Variant` | Lossy label — not identity |
| `chosen_rank` | `Variant` | |
| `chosen_tera_slot` | `Variant` | Chrome only |
| `chosen_mega_slot` | `Variant` | Chrome only |
| `selection_stage` | `Variant` | Chrome only; open vocabulary |
| `fallback_reason` | `Variant` | Chrome; open vocabulary |
| `aggregation_mode` | `Variant` | Flattened from JSON `aggregation.mode` |
| `aggregation_risk_lambda` | `Variant` | Flattened |
| `aggregation_must_react_lambda` | `Variant` | Flattened |
| `request_protocol_index` | `Variant` | Join key; null in TRACE_ONLY |
| `top1_top2_margin` | `Variant` | Nav; null if &lt;2 candidates |
| `fallback_used` | `bool` | Never null |
| `warning_count` | `int` | Never null |
| `decision_valid` | `bool` | Set by loader |
| `unknown_fields` | `Dictionary` | **Omit** from Plan D primary tabs |

**Binding:** There is **no** nested `aggregation` property on the sealed DTO. UI reads the three
flattened fields only (`bundle_validator.gd` flatten at load).

### 0.2 Naming + scene ownership (binding)

| Item | Decision |
|---|---|
| Package dir | `godot/src/decision/` |
| Presenter | `DecisionPresenter` — `RefCounted`, static helpers only |
| Controller | `DecisionController` — `Node`, child of `DecisionWorkspace` |
| Workspace | `DecisionWorkspace` |
| Table | `CandidateTableView` |
| Detail | `DecisionDetailView` |
| Deep link | `DecisionDeepLink` — `RefCounted` parse/resolve; **no** `godot/src/app/` |
| Mount | `AppShell.$VBox/DecisionWorkspace` **immediately after** `$VBox/ReplayWorkspace` |
| Size flags | Both workspaces `size_flags_vertical = SIZE_EXPAND_FILL` |
| Controller inject | Timeline bridge wired inside `DecisionWorkspace.reset` / `clear` |
| CLI | `AppShell.parse_cli_args` + `_apply_pending_deep_link` after completed |

### 0.3 Data authority (binding)

| Rule | Binding |
|---|---|
| Source of truth | Sealed Plan B DTOs only |
| No recompute | Never re-rank, re-score, re-derive margin/fallback/warning_count, or parse `candidate_key` JSON |
| Chosen identity | `chosen_candidate_key` ↔ `CandidateDTO.candidate_key` string equality only |
| Label | `candidate_id` display-only; never identity |
| Sort | Presentation indices only; never mutate sealed `candidates` or `rank` |
| Absent optionals | Literal `not recorded` — never invent `0` / `false` / `[]` |
| `suspected` | Never render (§16.3) |
| Score detail | `aggregate_score` only (§16.5) |
| Open vocabs | Render `selection_stage` / `fallback_reason` verbatim (§16.6) |
| Trust `decision_valid` | Do not re-run export refusal; presentation only |

### 0.4 Index separation (binding)

| Name | Meaning | Use |
|---|---|---|
| `decision_row_index` | Index into `bundle.decisions` | `TimelineEntryDTO.decision_row_index`; controller selection |
| `decision_index` | Fachliche ID | UI `decision #N`, deep link, nav order |

Deep-link resolve: scan for `decisions[i].decision_index == target`; require exactly one match.

### 0.5 Chosen-key presentation (binding)

| Case | Presentation |
|---|---|
| Empty `candidates` + null chosen fields | No rows; no highlight; **not an error** |
| Non-empty + `decision_valid == true` | Exactly one chosen highlight |
| Non-empty + `decision_valid == false` | Show rows; **no** highlight; header shows `(invalid)` |
| Never | Label-match `chosen_candidate_id` / `candidate_id` |

### 0.6 Timeline ↔ decision selection (binding)

```text
TimelineController.selection_changed(entry_index)
  -> DecisionController.on_timeline_selection(entry_index)
       DECISION / DECISION_WITHOUT_REPLAY_EVENT -> _set_row(entry.decision_row_index, sync_timeline=false)
       EVENT -> keep current decision selection

DecisionController.select_decision_row / nav jumps / deep link
  -> TimelineController.select(first matching entry by decision_row_index)
  -> decision_selection_changed(row_i)
  -> DecisionWorkspace rebinds table + detail (candidate selection resets)
```

| Moment | Action |
|---|---|
| `DecisionController.reset` with `trace_trusted` + decisions | Select row with **lowest** fachliche `decision_index` for the **panel only** |
| `reset` timeline sync | **Do not** call `TimelineController.select` on initial reset — Plan C keeps entry `0` / `-1` |
| Deep link success / user decision nav / table-driven decision jump | **Does** sync timeline via `_sync_timeline_to_row` |
| `reset` without trace | `_selected_row = -1` |
| EVENT cursor | Does **not** clear decision panel |
| Clear / refuse / cancel | `DecisionWorkspace.clear()` |
| Playback over DECISION* | Updates decision panel; EVENT ticks leave it |

**Why no timeline sync on reset:** Fixture battles may have EVENT entries before the first
DECISION. Plan C `TimelineController.reset` selects entry `0`. If Decision reset forced the
timeline onto the first decision, it would override Plan C’s start cursor. Binding contract:
panel shows the lowest-`decision_index` decision immediately; board/timeline stay on Plan C’s
cursor until the user (or deep link) explicitly navigates a decision.

Suppress timeline echo with a bool flag when decision→timeline sync would re-enter
`on_timeline_selection`.

### 0.6.1 Candidate selection vs chosen highlight (binding)

| Concept | Meaning |
|---|---|
| Chosen | Structural `chosen_candidate_key` highlight (`*` marker) — identity only |
| Selected | User/list selection of a candidate row for Candidate detail — **independent** |

Rules:

- Selecting a non-chosen candidate **never** moves or clears the chosen marker.
- Changing decision / clear / new `bind(decision)` resets selected candidate to `-1` (or to chosen
  index when `decision_valid` and chosen resolves — see §0.15: **reset selection to chosen when
  resolvable, else `-1`**).
- `CandidateTableView` emits `candidate_selected(candidate_index: int)` (`-1` = none).
- Filter text / chosen-only / `bind(decision)` that change the effective selected index **must**
  emit `candidate_selected` after rebuild so Candidate detail stays in sync (never leave detail
  on a stale non-chosen while the table shows chosen/empty).
- `DecisionDetailView` Candidate tab binds the selected `CandidateDTO` (or empty) via the
  workspace signal path (`candidate_selected` → `_on_candidate_selected`).
- “Jump to selected candidate” (design §6.3): ensure ItemList selects/scrolls to the current
  selected visual row via `CandidateTableView.focus_selected()` — keyboard focus wiring remains
  Plan E; the **API** is Plan D.

### 0.7 Deep link (binding; replaces int stub)

| Item | Decision |
|---|---|
| Format | `--decision <battle_id>:<decision_index>` (design §3.2) |
| Parse | Split on first `:`; non-empty battle_id; `is_valid_int` index |
| Reject | Bare int; missing `:`; empty id; non-int; **`--decision` with no following token** |
| Missing value | `ParseResult.ok=false`, `reason=malformed_decision_arg` (never silent ignore) |
| Apply | After `completed` + both workspaces `reset` |
| One-shot | After apply attempt (success **or** refuse), clear `_pending_deep_link = null` so a later manual open does **not** re-apply the CLI arg |
| Refuse sticky | `_deep_link_refuse_reason` must **not** survive a later manual open: clear it in `_start_load` and when `_apply_pending_deep_link` finds no pending |
| Match | `bundle.manifest.battle_id` string equality |
| Resolve | Exactly one decision_index match |
| Success | `select_decision_row` (**does** sync timeline) |
| Failure | Status `Deep link refused: <reason>`; **bundle stays loaded**; no substitute |
| Reasons | `malformed_decision_arg`, `battle_id_mismatch`, `decision_index_not_found`, `ambiguous_decision_index`, `trace_not_trusted` |
| Stub | Remove `cli_decision_index` int path; replace `test_cli_stub_records_decision_without_navigation` |
| Task split | **D3 AppShell has zero `DecisionDeepLink` types/calls.** D4 adds `decision_deep_link.gd` + AppShell parse/apply atomically |

### 0.8 Mode gates (binding)

| Condition | Decision panel |
|---|---|
| `not trace_trusted` (REPLAY_ONLY / fixture-04) | Empty-state **No decision trace in this bundle**; controls disabled |
| `trace_trusted` | Full inspection |
| TRACE_ONLY (fixture-16) | Full panel; board stays Plan C empty-state |
| Deep link + `not trace_trusted` | `trace_not_trusted` |

### 0.9 Navigation jumps (binding)

Order: ascending fachliche `decision_index`, **strictly after** current; **no wrap**.

| Jump | Predicate |
|---|---|
| Next / prev decision | Adjacent by `decision_index` |
| Next close | `top1_top2_margin != null` (no numeric threshold) |
| Next fallback | `fallback_used == true` |
| Next warning | `warning_count > 0` |

Disable buttons when no target exists.

### 0.10 Aggregation honesty (binding)

| Condition | UI |
|---|---|
| Always show aggregation block on Overview | Yes |
| All three aggregation_* null | Label **`aggregation mode not recorded`** |
| Individual null | That field: `not recorded` |
| Never | Infer from `config_hash` |

### 0.11 Candidate table columns (binding)

| Column | Source |
|---|---|
| Chosen | Marker from §0.5 |
| Label | `candidate_id` |
| Key | `candidate_key` or `not recorded` |
| Aggregate score | `aggregate_score` |

**Not** table columns: stage, mega, tera, fallback (those live in workspace chrome / Overview).

**ItemList line format (binding — must match §5.1 `_rebuild`):**

```text
"{marker}[{rank}] {candidate_id} | {key_text} | {aggregate_score:.4f}"
```

where `marker` is `"* "` when the row is the resolved chosen index, else `"  "`, and
`key_text = DecisionPresenter.optional_text(candidate_key)`.

**Sort modes (Plan D):** `rank` (default), `score`, `label`, `key`, `chosen_first`.

**Filter (Plan D — binding; design §6.5):** presentation-only; never mutates sealed DTOs.

| Control | Semantics |
|---|---|
| `FilterLineEdit` | Case-insensitive substring match on `candidate_id` **or** key text (`optional_text(candidate_key)`); empty = no text filter |
| `ChosenOnlyCheckBox` | When checked, keep only rows where candidate index == `resolve_chosen_row_index` (if `-1`, list empty) |

Filter applies after sort. Filtered-out rows are not listed; chosen marker still uses structural
index among **visible** rows. Changing filter resets **selected** candidate to chosen-if-resolvable
else `-1` (same as decision bind), then **emits** `candidate_selected` with the effective index
so Candidate detail rebinds (chosen or empty — never a stale prior selection).

**Plan E owns only:** keyboard shortcut to **focus** `FilterLineEdit` (“focus candidate filter”).
Plan E must **not** re-define filter semantics. See Plan E sketch amendment note in §0.13.

**Bounded rendering:** single `ItemList` (or equivalent); proven against fixture-16 row with
**104** candidates. Never one `Control` node per candidate beyond ItemList’s own items.

### 0.12 Fixtures (Plan D)

| Role | Path | `battle_id` | Expectation |
|---|---|---|---|
| Happy path | `bundles/fixture-01/` | `synthetic00000001` | Empty d0; sync; chosen unique later |
| Fallback + aggregation | `bundles/fixture-03/` | `synthetic00000003` | d2 `fallback_used`; all-null aggregation label |
| TRACE_ONLY + 104 | `bundles/fixture-16/` | `3e6a178b0900195e` | Empty d0; 104-cand bind; no replay board |
| No trace claims | `bundles/fixture-04/` | `synthetic00000001` | Empty-state; deep link → `trace_not_trusted` |
| Refuse clear | `sources/fixture-06/bundle/` | (refuse) | Clears decision panel |
| Unit cases | Constructed sealed DTOs | n/a | No new unit JSONL required |

### 0.13 Scope fence

**In:** DecisionPresenter/Controller/Workspace, candidate table, detail tabs, timeline sync,
nav jumps, deep link, gdUnit tests, pin commands.

**Out:** Plan E global banner / a11y / density / remappable keys / **focus** candidate-filter
shortcut only; Plan F E2E / remaining fixtures; artwork; mechanics sim; exporter /
`showdown_bot/` edits; score graph; `suspected`; score components.

**Filter ownership (binding):** Candidate **filter semantics + UI controls + tests** are Plan D
(§0.11). Plan E must claim only “focus the existing filter LineEdit” and must not leave filter
unimplemented across A–F. Plan E sketch is amended on this branch to record that ownership split.

Plan D may show **inline** invalid / aggregation / empty-trace labels on the decision surface.
Plan E owns the always-visible global state banner.

### 0.14 Implementation gate

Rev. 5 is **APPROVED**; implementation go-ahead is in effect.
Hard deps on tip already satisfied (B DTOs + C selection + fixtures 1/3/16).

### 0.15 Closed choice points (no implementer discretion)

| Topic | Binding |
|---|---|
| Mount | `$VBox/DecisionWorkspace` after ReplayWorkspace |
| Deep link format | `battle_id:decision_index` only |
| Int stub | Removed |
| `--decision` missing value | `malformed_decision_arg` (not silent) |
| Deep-link one-shot | Clear pending after apply attempt |
| Deep-link refuse sticky | Clear `_deep_link_refuse_reason` on `_start_load` and when apply finds no pending |
| D3 vs D4 | D3 **zero** `DecisionDeepLink` references; D4 adds class + AppShell CLI atomically |
| Aggregation | Flattened fields |
| 104-cand proof | fixture-16 |
| Next close | non-null margin; no threshold |
| EVENT selection | Keep decision |
| Bidirectional sync | Yes via `decision_row_index` — **not** on initial `reset` |
| Initial panel row | Lowest `decision_index`; timeline cursor stays Plan C |
| Candidate selected vs chosen | Independent; selected≠chosen never moves chosen marker |
| Candidate detail | Dedicated Candidate tab binds selected `CandidateDTO` via workspace signal path |
| Filter→detail sync | Filter/chosen-only emit `candidate_selected` after rebuild |
| Selection reset on decision bind | Chosen index if resolvable, else `-1`; emit after rebuild |
| Stage / mega / tera / fallback | Chrome + Overview — not table columns |
| Filter | Plan D (text + chosen-only); Plan E = focus shortcut only |
| Nav wrap | No |
| Tabs | `Overview` / `Candidate` / `State summary` |
| `unknown_fields` | Omit in D |
| `chosen_candidate_id` | Overview as non-identity label |
| Deep-link refuse | Bundle stays open |
| Unit fixtures | Constructed sealed DTOs |
| EOL restore | Tracked paths only after `git status`; never recursive delete of fixture trees |
| D2 GREEN | §6.3 GREEN before D2 commit |
| D3 RED | Shell mount tests start in D3 (no deep-link types); workspace signal-path tests |
| D4 RED | Deep-link class + AppShell CLI + one-shot + refuse-then-manual-open tests |

---

## 1. Goal / non-goals

**Goal:** Inspect recorded decisions: candidate table with structural chosen-key emphasis, detail
views for recorded fields only, exporter navigation values, bidirectional timeline sync, and
fail-closed deep-link launch.

**Non-goals:** re-ranking/score recompute; `suspected`; score-component breakdown; score graph;
aggregation inference from `config_hash`; Plan E banner/a11y/layout; Plan F E2E; exporter changes.

---

## 2. Architecture

```text
AppShell._start_load
  -> ReplayWorkspace.clear() + set_loading(true)
  -> DecisionWorkspace.clear() + set_loading(true)
  -> BundleLoader.load_async(path)

completed(BundleDTO)
  -> replay = BattleTimeline.build(bundle)
  -> ReplayWorkspace.reset(replay, bundle)
  -> DecisionWorkspace.reset(bundle, timeline_controller)
  -> optional DecisionDeepLink.apply -> select_decision_row

TimelineController.selection_changed(i)
  -> DecisionController.on_timeline_selection(i)
  -> CandidateTableView.bind + DecisionDetailView.bind

DecisionController.decision_selection_changed / nav
  -> TimelineController.select(matching_entry)
  -> rebind views
```

---

## 3. File map

| Path | Responsibility |
|---|---|
| `godot/src/decision/decision_presenter.gd` | Chosen resolve, sort, aggregation label, nav search |
| `godot/src/decision/decision_controller.gd` | Selection + timeline bridge + jumps |
| `godot/src/decision/decision_deep_link.gd` | Parse + resolve |
| `godot/src/decision/decision_workspace.gd` + `.tscn` | Panel hub |
| `godot/src/decision/candidate_table_view.gd` + `.tscn` | Bounded table |
| `godot/src/decision/decision_detail_view.gd` + `.tscn` | Tabs |
| `godot/src/workspace/app_shell.gd` + `.tscn` | Mount + deep link + clear-before-load |
| `godot/tests/decision/test_decision_presenter.gd` | §6.1 |
| `godot/tests/decision/test_decision_controller.gd` | §6.2 |
| `godot/tests/decision/test_candidate_table_view.gd` | §6.3 table |
| `godot/tests/decision/test_decision_detail_view.gd` | §6.3 detail |
| `godot/tests/decision/test_decision_deep_link.gd` | §6.4 |
| `godot/tests/workspace/test_app_shell_decision.gd` | §6.5 |
| `godot/tests/workspace/test_app_shell_smoke.gd` | Replace CLI stub test |

Every new `.gd` ships a matching `.gd.uid` (Godot import), same as Plans B/C.

### 3.1 Binding scene trees

**`app_shell.tscn` (after D3):**

```text
AppShell (Control)
├── VBox (VBoxContainer)
│   ├── PathRow (HBoxContainer)
│   │   ├── PathEdit (LineEdit)
│   │   └── OpenButton (Button)
│   ├── StatusLabel (Label)
│   ├── ReplayWorkspace (instance)          # existing
│   └── DecisionWorkspace (instance)        # NEW $VBox/DecisionWorkspace
└── BundleLoader (Node)
```

**`decision_workspace.tscn`:**

```text
DecisionWorkspace (VBoxContainer)           # script decision_workspace.gd
├── LoadingLabel (Label)                    # $LoadingLabel
├── EmptyStateLabel (Label)                 # $EmptyStateLabel
├── HeaderLabel (Label)                     # $HeaderLabel
├── ChromeRow (HBoxContainer)               # $ChromeRow
│   ├── StageLabel (Label)                  # $ChromeRow/StageLabel
│   ├── FallbackLabel (Label)               # $ChromeRow/FallbackLabel
│   ├── MegaLabel (Label)                   # $ChromeRow/MegaLabel
│   └── TeraLabel (Label)                   # $ChromeRow/TeraLabel
├── NavRow (HBoxContainer)                  # $NavRow
│   ├── PrevDecisionButton (Button)
│   ├── NextDecisionButton (Button)
│   ├── NextCloseButton (Button)
│   ├── NextFallbackButton (Button)
│   └── NextWarningButton (Button)
├── CandidateTable (instance candidate_table_view.tscn)  # $CandidateTable
├── Detail (instance decision_detail_view.tscn)          # $Detail
└── DecisionController (Node)               # $DecisionController
```

**`candidate_table_view.tscn`:**

```text
CandidateTableView (VBoxContainer)
├── FilterRow (HBoxContainer)               # $FilterRow
│   ├── FilterLineEdit (LineEdit)           # $FilterRow/FilterLineEdit
│   └── ChosenOnlyCheckBox (CheckBox)       # $FilterRow/ChosenOnlyCheckBox
├── SortOption (OptionButton)               # $SortOption
└── CandidateList (ItemList)                # $CandidateList  (select_mode = SELECT_SINGLE)
```

**`decision_detail_view.tscn`:**

```text
DecisionDetailView (TabContainer)
├── Overview (VBoxContainer)                # tab title Overview
│   ├── AggregationLabel (Label)
│   ├── RiskLambdaLabel (Label)
│   ├── MustReactLambdaLabel (Label)
│   ├── LatencyLabel (Label)
│   ├── ChooseStringLabel (Label)
│   ├── ChosenKeyLabel (Label)
│   ├── ChosenIdLabel (Label)
│   ├── RequestHashLabel (Label)
│   └── ObservableHashLabel (Label)
├── Candidate (VBoxContainer)               # tab title Candidate
│   ├── CandidateIdLabel (Label)
│   ├── CandidateRankLabel (Label)
│   ├── CandidateScoreLabel (Label)
│   └── CandidateKeyLabel (Label)
└── StateSummary (VBoxContainer)            # tab title State summary
    └── StateSummaryLabel (Label)
```

---

## 4. DTO / model contracts

### 4.1 `DecisionPresenter` (binding body)

```gdscript
class_name DecisionPresenter
extends RefCounted

const AGGREGATION_NOT_RECORDED := "aggregation mode not recorded"
const NOT_RECORDED := "not recorded"
const EMPTY_TRACE_TEXT := "No decision trace in this bundle"
const SORT_RANK := "rank"
const SORT_SCORE := "score"
const SORT_LABEL := "label"
const SORT_KEY := "key"
const SORT_CHOSEN_FIRST := "chosen_first"


static func resolve_chosen_row_index(decision: DecisionRowDTO) -> int:
	if decision == null or not decision.decision_valid:
		return -1
	if decision.candidates.is_empty():
		return -1
	if decision.chosen_candidate_key == null:
		return -1
	var key := str(decision.chosen_candidate_key)
	var found := -1
	for i in range(decision.candidates.size()):
		var c: CandidateDTO = decision.candidates[i]
		if c.candidate_key != null and str(c.candidate_key) == key:
			if found >= 0:
				return -1
			found = i
	return found


static func aggregation_headline(decision: DecisionRowDTO) -> String:
	if decision.aggregation_mode == null \
			and decision.aggregation_risk_lambda == null \
			and decision.aggregation_must_react_lambda == null:
		return AGGREGATION_NOT_RECORDED
	if decision.aggregation_mode == null:
		return NOT_RECORDED
	return str(decision.aggregation_mode)


static func optional_text(value: Variant) -> String:
	return NOT_RECORDED if value == null else str(value)


static func header_text(decision: DecisionRowDTO) -> String:
	if decision == null:
		return ""
	var base := "decision #%d" % decision.decision_index
	if not decision.decision_valid:
		base += " (invalid)"
	return base


static func sorted_candidate_indices(decision: DecisionRowDTO, mode: String) -> PackedInt32Array:
	var idxs: Array = []
	for i in range(decision.candidates.size()):
		idxs.append(i)
	var chosen := resolve_chosen_row_index(decision)
	idxs.sort_custom(func(a, b):
		var ca: CandidateDTO = decision.candidates[a]
		var cb: CandidateDTO = decision.candidates[b]
		match mode:
			SORT_SCORE:
				if ca.aggregate_score == cb.aggregate_score:
					return ca.rank < cb.rank
				return ca.aggregate_score > cb.aggregate_score
			SORT_LABEL:
				var la := ca.candidate_id
				var lb := cb.candidate_id
				if la == lb:
					return ca.rank < cb.rank
				return la < lb
			SORT_KEY:
				var ka := "" if ca.candidate_key == null else str(ca.candidate_key)
				var kb := "" if cb.candidate_key == null else str(cb.candidate_key)
				if ka == kb:
					return ca.rank < cb.rank
				return ka < kb
			SORT_CHOSEN_FIRST:
				var a_ch := a == chosen
				var b_ch := b == chosen
				if a_ch != b_ch:
					return a_ch
				return ca.rank < cb.rank
			_:
				return ca.rank < cb.rank
	)
	var out := PackedInt32Array()
	for i in idxs:
		out.append(int(i))
	return out


static func find_next_nav_row(
		bundle: BundleDTO,
		current_decision_index: int,
		kind: String
) -> int:
	var best_row := -1
	var best_id := 2147483647
	for row_i in range(bundle.decisions.size()):
		var d: DecisionRowDTO = bundle.decisions[row_i]
		if d.decision_index <= current_decision_index:
			continue
		var ok := false
		match kind:
			"decision":
				ok = true
			"close":
				ok = d.top1_top2_margin != null
			"fallback":
				ok = d.fallback_used
			"warning":
				ok = d.warning_count > 0
			_:
				ok = false
		if ok and d.decision_index < best_id:
			best_id = d.decision_index
			best_row = row_i
	return best_row


static func find_prev_decision_row(bundle: BundleDTO, current_decision_index: int) -> int:
	var best_row := -1
	var best_id := -2147483648
	for row_i in range(bundle.decisions.size()):
		var d: DecisionRowDTO = bundle.decisions[row_i]
		if d.decision_index >= current_decision_index:
			continue
		if d.decision_index > best_id:
			best_id = d.decision_index
			best_row = row_i
	return best_row


static func timeline_entry_for_decision_row(replay: ReplayDTO, decision_row_index: int) -> int:
	if replay == null:
		return -1
	for i in range(replay.entries.size()):
		var e: TimelineEntryDTO = replay.entries[i]
		if e.kind == TimelineEntryKind.DECISION \
				or e.kind == TimelineEntryKind.DECISION_WITHOUT_REPLAY_EVENT:
			if e.decision_row_index == decision_row_index:
				return i
	return -1


static func first_row_by_decision_index(bundle: BundleDTO) -> int:
	if bundle == null or bundle.decisions.is_empty():
		return -1
	var best_row := 0
	var best_id: int = bundle.decisions[0].decision_index
	for i in range(1, bundle.decisions.size()):
		var d: DecisionRowDTO = bundle.decisions[i]
		if d.decision_index < best_id:
			best_id = d.decision_index
			best_row = i
	return best_row


static func format_state_summary(decision: DecisionRowDTO) -> String:
	if decision == null or decision.state_summary.is_empty():
		return NOT_RECORDED
	var keys: Array = decision.state_summary.keys()
	keys.sort()
	var lines: PackedStringArray = PackedStringArray()
	for k in keys:
		lines.append("%s: %s" % [str(k), str(decision.state_summary[k])])
	return "\n".join(lines)
```

### 4.2 `DecisionController` (binding body)

```gdscript
class_name DecisionController
extends Node

signal decision_selection_changed(decision_row_index: int)

var _bundle: BundleDTO = null
var _timeline: TimelineController = null
var _selected_row: int = -1
var _suppress_timeline_echo: bool = false


func reset(bundle: BundleDTO, timeline: TimelineController) -> void:
	if _timeline != null and _timeline.selection_changed.is_connected(on_timeline_selection):
		_timeline.selection_changed.disconnect(on_timeline_selection)
	_bundle = bundle
	_timeline = timeline
	_selected_row = -1
	if _timeline != null:
		_timeline.selection_changed.connect(on_timeline_selection)
	if bundle != null and bundle.trace_trusted and bundle.decisions.size() > 0:
		_selected_row = DecisionPresenter.first_row_by_decision_index(bundle)
	decision_selection_changed.emit(_selected_row)
	# Do NOT sync timeline here — Plan C keeps entry 0 / -1 (§0.6).


func clear() -> void:
	if _timeline != null and _timeline.selection_changed.is_connected(on_timeline_selection):
		_timeline.selection_changed.disconnect(on_timeline_selection)
	_bundle = null
	_timeline = null
	_selected_row = -1
	decision_selection_changed.emit(_selected_row)


func on_timeline_selection(entry_index: int) -> void:
	if _suppress_timeline_echo:
		return
	if _bundle == null or _timeline == null:
		return
	var replay: ReplayDTO = _timeline.get_replay()
	if replay == null or entry_index < 0 or entry_index >= replay.entries.size():
		return
	var entry: TimelineEntryDTO = replay.entries[entry_index]
	if entry.kind == TimelineEntryKind.EVENT:
		return
	if entry.decision_row_index < 0:
		return
	_set_row(entry.decision_row_index, false)


func select_decision_row(row_i: int) -> void:
	_set_row(row_i, true)


func jump_next(kind: String) -> void:
	if _bundle == null or _selected_row < 0:
		return
	var cur: DecisionRowDTO = _bundle.decisions[_selected_row]
	var next_row := DecisionPresenter.find_next_nav_row(_bundle, cur.decision_index, kind)
	if next_row >= 0:
		select_decision_row(next_row)


func jump_prev_decision() -> void:
	if _bundle == null or _selected_row < 0:
		return
	var cur: DecisionRowDTO = _bundle.decisions[_selected_row]
	var prev_row := DecisionPresenter.find_prev_decision_row(_bundle, cur.decision_index)
	if prev_row >= 0:
		select_decision_row(prev_row)


func get_selected_decision_row_index() -> int:
	return _selected_row


func get_selected_decision() -> DecisionRowDTO:
	if _bundle == null or _selected_row < 0:
		return null
	return _bundle.decisions[_selected_row]


func has_next(kind: String) -> bool:
	if _bundle == null or _selected_row < 0:
		return false
	var cur: DecisionRowDTO = _bundle.decisions[_selected_row]
	return DecisionPresenter.find_next_nav_row(_bundle, cur.decision_index, kind) >= 0


func has_prev_decision() -> bool:
	if _bundle == null or _selected_row < 0:
		return false
	var cur: DecisionRowDTO = _bundle.decisions[_selected_row]
	return DecisionPresenter.find_prev_decision_row(_bundle, cur.decision_index) >= 0


func _set_row(row_i: int, sync_timeline: bool) -> void:
	if _bundle == null or row_i < 0 or row_i >= _bundle.decisions.size():
		return
	if row_i == _selected_row:
		if sync_timeline:
			_sync_timeline_to_row(row_i)
		return
	_selected_row = row_i
	decision_selection_changed.emit(_selected_row)
	if sync_timeline:
		_sync_timeline_to_row(row_i)


func _sync_timeline_to_row(row_i: int) -> void:
	if _timeline == null or row_i < 0:
		return
	var entry_i := DecisionPresenter.timeline_entry_for_decision_row(
		_timeline.get_replay(), row_i
	)
	if entry_i < 0:
		return
	_suppress_timeline_echo = true
	_timeline.select(entry_i)
	_suppress_timeline_echo = false
```

### 4.3 `DecisionDeepLink` (binding body)

```gdscript
class_name DecisionDeepLink
extends RefCounted

class ParseResult extends RefCounted:
	var ok: bool = false
	var battle_id: String = ""
	var decision_index: int = 0
	var reason: String = ""


class ApplyResult extends RefCounted:
	var ok: bool = false
	var decision_row_index: int = -1
	var reason: String = ""


static func parse_arg(value: String) -> ParseResult:
	var r := ParseResult.new()
	var sep := value.find(":")
	if sep <= 0 or sep >= value.length() - 1:
		r.reason = "malformed_decision_arg"
		return r
	var battle_id := value.substr(0, sep)
	var index_text := value.substr(sep + 1)
	if battle_id.is_empty() or not index_text.is_valid_int():
		r.reason = "malformed_decision_arg"
		return r
	r.ok = true
	r.battle_id = battle_id
	r.decision_index = index_text.to_int()
	return r


static func resolve(bundle: BundleDTO, battle_id: String, decision_index: int) -> ApplyResult:
	var r := ApplyResult.new()
	if bundle == null or not bundle.trace_trusted:
		r.reason = "trace_not_trusted"
		return r
	if bundle.manifest == null or str(bundle.manifest.battle_id) != battle_id:
		r.reason = "battle_id_mismatch"
		return r
	var found := -1
	for i in range(bundle.decisions.size()):
		var d: DecisionRowDTO = bundle.decisions[i]
		if d.decision_index == decision_index:
			if found >= 0:
				r.reason = "ambiguous_decision_index"
				return r
			found = i
	if found < 0:
		r.reason = "decision_index_not_found"
		return r
	r.ok = true
	r.decision_row_index = found
	return r
```

---

## 5. View contracts

### 5.1 `CandidateTableView`

```gdscript
class_name CandidateTableView
extends VBoxContainer

signal candidate_selected(candidate_index: int)

@onready var _filter_edit: LineEdit = $FilterRow/FilterLineEdit
@onready var _chosen_only: CheckBox = $FilterRow/ChosenOnlyCheckBox
@onready var _sort: OptionButton = $SortOption
@onready var _list: ItemList = $CandidateList

var _decision: DecisionRowDTO = null
var _mode: String = DecisionPresenter.SORT_RANK
var _filter_text: String = ""
var _chosen_only_on: bool = false
## Index into decision.candidates (−1 = none). Independent of chosen marker.
var _selected_candidate_index: int = -1
## Parallel to ItemList rows: candidates array index for each visible item.
var _visible_candidate_indices: PackedInt32Array = PackedInt32Array()


func _ready() -> void:
	_sort.clear()
	_sort.add_item(DecisionPresenter.SORT_RANK)
	_sort.add_item(DecisionPresenter.SORT_SCORE)
	_sort.add_item(DecisionPresenter.SORT_LABEL)
	_sort.add_item(DecisionPresenter.SORT_KEY)
	_sort.add_item(DecisionPresenter.SORT_CHOSEN_FIRST)
	_sort.item_selected.connect(_on_sort_selected)
	_list.item_selected.connect(_on_item_selected)
	_filter_edit.text_changed.connect(_on_filter_text_changed)
	_chosen_only.toggled.connect(_on_chosen_only_toggled)


func bind(decision: DecisionRowDTO) -> void:
	_decision = decision
	_reset_selection_for_decision()
	_rebuild()
	candidate_selected.emit(_selected_candidate_index)


func clear_view() -> void:
	_decision = null
	_selected_candidate_index = -1
	_visible_candidate_indices = PackedInt32Array()
	_list.clear()
	candidate_selected.emit(-1)


func get_item_count() -> int:
	return _list.item_count


func get_selected_candidate_index() -> int:
	return _selected_candidate_index


func get_selected_candidate() -> CandidateDTO:
	if _decision == null or _selected_candidate_index < 0:
		return null
	if _selected_candidate_index >= _decision.candidates.size():
		return null
	return _decision.candidates[_selected_candidate_index]


func get_chosen_item_index() -> int:
	# Visual list index of chosen marker among currently visible rows, or -1.
	if _decision == null:
		return -1
	var chosen_row := DecisionPresenter.resolve_chosen_row_index(_decision)
	if chosen_row < 0:
		return -1
	for visual_i in range(_visible_candidate_indices.size()):
		if int(_visible_candidate_indices[visual_i]) == chosen_row:
			return visual_i
	return -1


func get_sort_mode() -> String:
	return _mode


func set_sort_mode(mode: String) -> void:
	_mode = mode
	for i in range(_sort.item_count):
		if _sort.get_item_text(i) == mode:
			_sort.select(i)
			break
	_rebuild()


func focus_selected() -> void:
	# Plan D API for “jump to selected candidate”; Plan E binds the shortcut.
	var visual := _visual_index_for_candidate(_selected_candidate_index)
	if visual < 0:
		return
	_list.select(visual)
	_list.ensure_current_is_visible()


func select_candidate_index(candidate_index: int) -> void:
	# Test/API seam: select by candidates[] index without simulating InputEvent.
	if _decision == null or candidate_index < 0 or candidate_index >= _decision.candidates.size():
		return
	var visual := _visual_index_for_candidate(candidate_index)
	if visual < 0:
		return
	_list.select(visual)
	_on_item_selected(visual)


func get_filter_line_edit() -> LineEdit:
	return _filter_edit


func set_filter_text(text: String) -> void:
	# Test/API seam — same path as FilterLineEdit.text_changed.
	_filter_edit.text = text
	_on_filter_text_changed(text)


func set_chosen_only(pressed: bool) -> void:
	_chosen_only.button_pressed = pressed
	_on_chosen_only_toggled(pressed)


func _on_sort_selected(index: int) -> void:
	_mode = _sort.get_item_text(index)
	_rebuild()


func _on_filter_text_changed(text: String) -> void:
	_filter_text = text
	_reset_selection_for_decision()
	_rebuild()
	# Must notify: reset alone does not emit; detail would otherwise stay on prior selection.
	candidate_selected.emit(_selected_candidate_index)


func _on_chosen_only_toggled(pressed: bool) -> void:
	_chosen_only_on = pressed
	_reset_selection_for_decision()
	_rebuild()
	candidate_selected.emit(_selected_candidate_index)


func _on_item_selected(visual_index: int) -> void:
	if visual_index < 0 or visual_index >= _visible_candidate_indices.size():
		return
	_selected_candidate_index = int(_visible_candidate_indices[visual_index])
	candidate_selected.emit(_selected_candidate_index)


func _reset_selection_for_decision() -> void:
	if _decision == null:
		_selected_candidate_index = -1
		return
	var chosen := DecisionPresenter.resolve_chosen_row_index(_decision)
	_selected_candidate_index = chosen if chosen >= 0 else -1


func _visual_index_for_candidate(candidate_index: int) -> int:
	if candidate_index < 0:
		return -1
	for i in range(_visible_candidate_indices.size()):
		if int(_visible_candidate_indices[i]) == candidate_index:
			return i
	return -1


func _passes_filter(candidate_index: int, chosen_row: int) -> bool:
	var c: CandidateDTO = _decision.candidates[candidate_index]
	if _chosen_only_on and candidate_index != chosen_row:
		return false
	if _filter_text.is_empty():
		return true
	var needle := _filter_text.to_lower()
	var label := c.candidate_id.to_lower()
	var key_text := DecisionPresenter.optional_text(c.candidate_key).to_lower()
	return label.contains(needle) or key_text.contains(needle)


func _rebuild() -> void:
	_list.clear()
	_visible_candidate_indices = PackedInt32Array()
	if _decision == null:
		return
	var chosen_row := DecisionPresenter.resolve_chosen_row_index(_decision)
	var order := DecisionPresenter.sorted_candidate_indices(_decision, _mode)
	for i in range(order.size()):
		var row_i: int = int(order[i])
		if not _passes_filter(row_i, chosen_row):
			continue
		var c: CandidateDTO = _decision.candidates[row_i]
		var key_text := DecisionPresenter.optional_text(c.candidate_key)
		var marker := "* " if row_i == chosen_row else "  "
		var line := "%s[%d] %s | %s | %.4f" % [
			marker, c.rank, c.candidate_id, key_text, c.aggregate_score
		]
		_list.add_item(line)
		_visible_candidate_indices.append(row_i)
	var visual := _visual_index_for_candidate(_selected_candidate_index)
	if visual >= 0:
		_list.select(visual)
	elif _selected_candidate_index >= 0:
		# Filtered out: drop selection; callers (bind/filter/chosen-only) emit after _rebuild.
		_selected_candidate_index = -1
```

### 5.2 `DecisionDetailView`

```gdscript
class_name DecisionDetailView
extends TabContainer

@onready var _aggregation: Label = $Overview/AggregationLabel
@onready var _risk: Label = $Overview/RiskLambdaLabel
@onready var _must_react: Label = $Overview/MustReactLambdaLabel
@onready var _latency: Label = $Overview/LatencyLabel
@onready var _choose: Label = $Overview/ChooseStringLabel
@onready var _chosen_key: Label = $Overview/ChosenKeyLabel
@onready var _chosen_id: Label = $Overview/ChosenIdLabel
@onready var _request_hash: Label = $Overview/RequestHashLabel
@onready var _observable_hash: Label = $Overview/ObservableHashLabel
@onready var _cand_id: Label = $Candidate/CandidateIdLabel
@onready var _cand_rank: Label = $Candidate/CandidateRankLabel
@onready var _cand_score: Label = $Candidate/CandidateScoreLabel
@onready var _cand_key: Label = $Candidate/CandidateKeyLabel
@onready var _state_summary: Label = $StateSummary/StateSummaryLabel

var _decision: DecisionRowDTO = null


func bind_decision(decision: DecisionRowDTO) -> void:
	_decision = decision
	if decision == null:
		clear_view()
		return
	_aggregation.text = "aggregation: %s" % DecisionPresenter.aggregation_headline(decision)
	_risk.text = "risk_lambda: %s" % DecisionPresenter.optional_text(
		decision.aggregation_risk_lambda
	)
	_must_react.text = "must_react_lambda: %s" % DecisionPresenter.optional_text(
		decision.aggregation_must_react_lambda
	)
	_latency.text = "latency_ms: %s" % str(decision.decision_latency_ms)
	_choose.text = "actual_choose: %s" % decision.actual_choose_string
	_chosen_key.text = "chosen_key: %s" % DecisionPresenter.optional_text(
		decision.chosen_candidate_key
	)
	_chosen_id.text = "chosen_id (label, not identity): %s" % DecisionPresenter.optional_text(
		decision.chosen_candidate_id
	)
	_request_hash.text = "request_hash: %s" % decision.request_hash
	_observable_hash.text = "observable_state_hash: %s" % decision.observable_state_hash
	_state_summary.text = DecisionPresenter.format_state_summary(decision)


func bind_candidate(candidate: CandidateDTO) -> void:
	if candidate == null:
		_cand_id.text = "candidate: %s" % DecisionPresenter.NOT_RECORDED
		_cand_rank.text = ""
		_cand_score.text = ""
		_cand_key.text = ""
		return
	_cand_id.text = "candidate_id: %s" % candidate.candidate_id
	_cand_rank.text = "rank: %d" % candidate.rank
	_cand_score.text = "aggregate_score: %.4f" % candidate.aggregate_score
	_cand_key.text = "candidate_key: %s" % DecisionPresenter.optional_text(candidate.candidate_key)


func clear_view() -> void:
	_decision = null
	for lbl in [
		_aggregation, _risk, _must_react, _latency, _choose, _chosen_key, _chosen_id,
		_request_hash, _observable_hash, _cand_id, _cand_rank, _cand_score, _cand_key,
		_state_summary,
	]:
		lbl.text = ""


func get_aggregation_text() -> String:
	return _aggregation.text


func get_latency_text() -> String:
	return _latency.text


func get_candidate_id_text() -> String:
	return _cand_id.text
```

### 5.3 `DecisionWorkspace`

```gdscript
class_name DecisionWorkspace
extends VBoxContainer

@onready var _loading: Label = $LoadingLabel
@onready var _empty: Label = $EmptyStateLabel
@onready var _header: Label = $HeaderLabel
@onready var _stage: Label = $ChromeRow/StageLabel
@onready var _fallback: Label = $ChromeRow/FallbackLabel
@onready var _mega: Label = $ChromeRow/MegaLabel
@onready var _tera: Label = $ChromeRow/TeraLabel
@onready var _prev: Button = $NavRow/PrevDecisionButton
@onready var _next: Button = $NavRow/NextDecisionButton
@onready var _close: Button = $NavRow/NextCloseButton
@onready var _fb: Button = $NavRow/NextFallbackButton
@onready var _warn: Button = $NavRow/NextWarningButton
@onready var _table: CandidateTableView = $CandidateTable
@onready var _detail: DecisionDetailView = $Detail
@onready var _controller: DecisionController = $DecisionController


func _ready() -> void:
	_prev.pressed.connect(_controller.jump_prev_decision)
	_next.pressed.connect(func(): _controller.jump_next("decision"))
	_close.pressed.connect(func(): _controller.jump_next("close"))
	_fb.pressed.connect(func(): _controller.jump_next("fallback"))
	_warn.pressed.connect(func(): _controller.jump_next("warning"))
	_controller.decision_selection_changed.connect(_on_decision_selection_changed)
	_table.candidate_selected.connect(_on_candidate_selected)
	clear()


func reset(bundle: BundleDTO, timeline: TimelineController) -> void:
	set_loading(false)
	if bundle == null or not bundle.trace_trusted:
		_controller.clear()
		_show_empty_trace()
		return
	_empty.visible = false
	_empty.text = ""
	_controller.reset(bundle, timeline)
	_set_nav_enabled(true)
	_refresh_from_controller()


func clear() -> void:
	_controller.clear()
	_table.clear_view()
	_detail.clear_view()
	_header.text = ""
	_stage.text = ""
	_fallback.text = ""
	_mega.text = ""
	_tera.text = ""
	_empty.visible = false
	_empty.text = ""
	_set_nav_enabled(false)
	set_loading(false)


func set_loading(active: bool) -> void:
	_loading.text = "Loading..." if active else ""


func get_decision_controller() -> DecisionController:
	return _controller


func get_candidate_table_view() -> CandidateTableView:
	return _table


func get_detail_view() -> DecisionDetailView:
	return _detail


func get_empty_state_visible() -> bool:
	return _empty.visible


func get_header_text() -> String:
	return _header.text


func _show_empty_trace() -> void:
	_empty.visible = true
	_empty.text = DecisionPresenter.EMPTY_TRACE_TEXT
	_table.clear_view()
	_detail.clear_view()
	_header.text = ""
	_stage.text = ""
	_fallback.text = ""
	_mega.text = ""
	_tera.text = ""
	_set_nav_enabled(false)


func _on_decision_selection_changed(_row: int) -> void:
	_refresh_from_controller()


func _on_candidate_selected(_candidate_index: int) -> void:
	_detail.bind_candidate(_table.get_selected_candidate())


func _refresh_from_controller() -> void:
	var decision: DecisionRowDTO = _controller.get_selected_decision()
	if decision == null:
		_table.clear_view()
		_detail.clear_view()
		_header.text = ""
		_stage.text = ""
		_fallback.text = ""
		_mega.text = ""
		_tera.text = ""
		_set_nav_enabled(false)
		return
	_header.text = DecisionPresenter.header_text(decision)
	_stage.text = "stage: %s" % DecisionPresenter.optional_text(decision.selection_stage)
	_fallback.text = "fallback: %s (%s)" % [
		str(decision.fallback_used),
		DecisionPresenter.optional_text(decision.fallback_reason),
	]
	_mega.text = "mega: %s" % DecisionPresenter.optional_text(decision.chosen_mega_slot)
	_tera.text = "tera: %s" % DecisionPresenter.optional_text(decision.chosen_tera_slot)
	_table.bind(decision)
	_detail.bind_decision(decision)
	_detail.bind_candidate(_table.get_selected_candidate())
	_prev.disabled = not _controller.has_prev_decision()
	_next.disabled = not _controller.has_next("decision")
	_close.disabled = not _controller.has_next("close")
	_fb.disabled = not _controller.has_next("fallback")
	_warn.disabled = not _controller.has_next("warning")


func _set_nav_enabled(enabled: bool) -> void:
	if not enabled:
		_prev.disabled = true
		_next.disabled = true
		_close.disabled = true
		_fb.disabled = true
		_warn.disabled = true
```

### 5.4 `AppShell` deltas (binding)

#### 5.4.1 D3 surface (no `DecisionDeepLink` types)

Mount DecisionWorkspace; clear both workspaces before load; reset decision on completed.
**Do not** reference `DecisionDeepLink`, `_pending_deep_link`, or `_apply_pending_deep_link` in D3.

```gdscript
@onready var _replay_workspace: ReplayWorkspace = $VBox/ReplayWorkspace
@onready var _decision_workspace: DecisionWorkspace = $VBox/DecisionWorkspace


func get_decision_workspace() -> DecisionWorkspace:
	return _decision_workspace


func get_selected_decision_index() -> int:
	var d: DecisionRowDTO = _decision_workspace.get_decision_controller().get_selected_decision()
	if d == null:
		return -1
	return d.decision_index


func _start_load(path: String) -> void:
	_current_bundle = null
	_current_refuse = null
	# D4: also clear `_deep_link_refuse_reason = ""` here (field introduced in §5.4.2).
	_replay_workspace.clear()
	_replay_workspace.set_loading(true)
	_decision_workspace.clear()
	_decision_workspace.set_loading(true)
	_set_status("Loading...")
	_loader.load_async(path)


func _on_completed(bundle: BundleDTO) -> void:
	_current_bundle = bundle
	_current_refuse = null
	var replay: ReplayDTO = BattleTimeline.build(bundle)
	_replay_workspace.reset(replay, bundle)
	_decision_workspace.reset(bundle, _replay_workspace.get_timeline_controller())
	_set_status(_format_loaded_status(bundle))


func _on_refused(diagnostic: RefuseDiagnostic) -> void:
	_current_bundle = null
	_current_refuse = diagnostic
	_replay_workspace.clear()
	_decision_workspace.clear()
	_set_status("Refused: %s" % diagnostic.reason)


func _on_cancelled() -> void:
	_current_bundle = null
	_current_refuse = null
	_replay_workspace.clear()
	_decision_workspace.clear()
	_set_status("Load cancelled")
```

Keep existing `parse_cli_args` int stub **unchanged in D3** (still present on tip) — D4 replaces it
atomically with the deep-link parser. D3 tests must not assert deep-link behavior.

#### 5.4.2 D4 additions (atomic with `decision_deep_link.gd`)

```gdscript
var _pending_deep_link: DecisionDeepLink.ParseResult = null
var _deep_link_refuse_reason: String = ""


func parse_cli_args(args: PackedStringArray = PackedStringArray()) -> void:
	_pending_deep_link = null
	_deep_link_refuse_reason = ""
	var source := args if not args.is_empty() else OS.get_cmdline_user_args()
	var index := 0
	while index < source.size():
		var token := String(source[index])
		if token == "--decision":
			if index + 1 >= source.size():
				_pending_deep_link = DecisionDeepLink.ParseResult.new()
				_pending_deep_link.ok = false
				_pending_deep_link.reason = "malformed_decision_arg"
				index += 1
				continue
			_pending_deep_link = DecisionDeepLink.parse_arg(String(source[index + 1]))
			index += 2
			continue
		index += 1


func get_deep_link_refuse_reason() -> String:
	return _deep_link_refuse_reason


func _start_load(path: String) -> void:
	_current_bundle = null
	_current_refuse = null
	_deep_link_refuse_reason = ""  # refuse must not stick across a fresh manual open
	_replay_workspace.clear()
	_replay_workspace.set_loading(true)
	_decision_workspace.clear()
	_decision_workspace.set_loading(true)
	_set_status("Loading...")
	_loader.load_async(path)


func _on_completed(bundle: BundleDTO) -> void:
	_current_bundle = bundle
	_current_refuse = null
	var replay: ReplayDTO = BattleTimeline.build(bundle)
	_replay_workspace.reset(replay, bundle)
	_decision_workspace.reset(bundle, _replay_workspace.get_timeline_controller())
	_apply_pending_deep_link(bundle)
	if _deep_link_refuse_reason.is_empty():
		_set_status(_format_loaded_status(bundle))


func _apply_pending_deep_link(bundle: BundleDTO) -> void:
	if _pending_deep_link == null:
		_deep_link_refuse_reason = ""  # no pending → normal loaded status on this completion
		return
	var pending := _pending_deep_link
	_pending_deep_link = null  # one-shot: never re-apply on later opens
	if not pending.ok:
		_deep_link_refuse_reason = pending.reason
		_set_status("Deep link refused: %s" % _deep_link_refuse_reason)
		return
	var applied := DecisionDeepLink.resolve(bundle, pending.battle_id, pending.decision_index)
	if not applied.ok:
		_deep_link_refuse_reason = applied.reason
		_set_status("Deep link refused: %s" % _deep_link_refuse_reason)
		return
	_deep_link_refuse_reason = ""
	_decision_workspace.get_decision_controller().select_decision_row(applied.decision_row_index)
```

---

## 6. Named tests (binding)

Shared helpers: **exact §14 bodies** (do not invent alternate fixture loaders). Decision suites
also use `_make_candidate` from §14.
### 6.1 `tests/decision/test_decision_presenter.gd`

| Test | Assert |
|---|---|
| `test_empty_candidates_no_chosen_row` | fixture-01 decision 0 → resolve `-1` |
| `test_valid_chosen_key_unique` | fixture-01 first non-empty → unique highlight |
| `test_invalid_decision_no_highlight` | constructed `decision_valid=false` → `-1` |
| `test_never_label_matches_chosen_id` | `decision_valid=true`, wrong key, matching `candidate_id`/`chosen_candidate_id` → resolve `-1` (does not pick by label) |
| `test_aggregation_all_null_label` | fixture-03 → `AGGREGATION_NOT_RECORDED` |
| `test_optional_null_is_not_recorded` | null → `not recorded` |
| `test_sort_modes_preserve_chosen_identity` | all sort modes → same `candidate_key` at chosen marker |
| `test_next_close_skips_null_margin` | constructed margins |
| `test_next_fallback_fixture03` | from lowest id → d2 |
| `test_next_warning_when_count_positive` | fixture-01 warning_count |
| `test_timeline_entry_for_decision_row` | fixture-01 maps row ↔ entry |
| `test_first_row_by_decision_index` | noncontiguous ids |

### 6.2 `tests/decision/test_decision_controller.gd`

| Test | Assert |
|---|---|
| `test_timeline_decision_selects_row` | DECISION entry → matching row |
| `test_timeline_event_keeps_row` | EVENT after DECISION → unchanged |
| `test_select_row_syncs_timeline` | select_decision_row moves timeline |
| `test_clear_emits_minus_one` | clear → `-1` |
| `test_replay_only_reset_no_selection` | REPLAY_ONLY → `-1` |
| `test_reset_does_not_move_timeline_cursor` | Constructed: EVENT then DECISION; after dual reset, timeline stays at 0 (EVENT); decision panel still on first decision |
| `test_jump_next_fallback` | fixture-03 |
| `test_nav_buttons_no_wrap` | at last decision `has_next("decision")` false |

### 6.3 Views

| Suite | Test | Assert |
|---|---|---|
| table | `test_table_bounded_104_candidates` | fixture-16 d1 → item_count 104 |
| table | `test_empty_candidates_table_empty` | fixture-16 d0 → 0 |
| table | `test_sort_keeps_chosen_marker` | chosen list index tracks key |
| table | `test_selected_ne_chosen_keeps_chosen_marker` | select non-chosen row → chosen visual marker unchanged; selected index differs |
| table | `test_decision_bind_resets_selection` | after rebind, selection = chosen if resolvable |
| table | `test_filter_text_narrows_list` | substring on label reduces count; chosen marker still structural |
| table | `test_filter_chosen_only` | checkbox keeps only chosen row when resolvable |
| table | `test_filter_resyncs_selection_signal` | non-chosen selected → chosen-only → emits chosen; selected index matches |
| detail | `test_detail_shows_aggregation_not_recorded` | fixture-03 |
| detail | `test_detail_shows_latency_ms` | contains recorded latency |
| detail | `test_chosen_id_caption_not_identity` | label contains `not identity` |

### 6.4 `tests/decision/test_decision_deep_link.gd`

| Test | Assert |
|---|---|
| `test_parse_ok` | `synthetic00000001:1` |
| `test_parse_rejects_bare_int` | `"2"` → malformed |
| `test_parse_rejects_empty_string` | `""` → `malformed_decision_arg` (parser half of missing-target) |
| `test_parse_rejects_missing_colon` | `"abc"` → malformed |
| `test_resolve_success_fixture01` | ok row |
| `test_resolve_battle_id_mismatch` | wrong id |
| `test_resolve_missing_index` | huge index |
| `test_resolve_trace_not_trusted` | fixture-04 |

### 6.5 `tests/workspace/test_app_shell_decision.gd`

| Test | Assert |
|---|---|
| `test_fixture01_timeline_and_decision_nav_same_index` | same `decision_index` after **user** decision nav |
| `test_fixture01_reset_keeps_plan_c_timeline_cursor` | after open, timeline entry 0 unchanged by decision panel init |
| `test_fixture03_fallback_nav` | lands fallback_used |
| `test_fixture16_empty_candidates_clean` | 0 items; no crash |
| `test_fixture16_104_candidates_bind` | 104 items |
| `test_fixture04_no_candidate_claims` | empty-state visible |
| `test_refuse_clears_decision_panel` | fixture-06 |
| `test_start_load_clears_decision_before_async` | clear before load |
| `test_bundle_switch_01_to_04_hides_claims` | 01→04 empty-state |
| `test_workspace_candidate_signal_updates_detail` | select non-chosen via table → Candidate tab updates **without** manual `bind_candidate` |
| `test_workspace_filter_resyncs_detail` | non-chosen → chosen-only → table + Candidate tab both show chosen |

### 6.5.1 Deep-link shell tests (D4 only)

| Test | Assert |
|---|---|
| `test_deep_link_success` | selects target index |
| `test_deep_link_mismatch_refuses` | reason set; not silent swap |
| `test_deep_link_missing_value_malformed` | `parse_cli_args(["--decision"])` → refuse reason `malformed_decision_arg` |
| `test_deep_link_one_shot_not_reapplied_on_manual_open` | CLI link on first open; second open without re-parse does not re-apply pending |
| `test_deep_link_refuse_cleared_on_later_manual_open` | mismatch refuse → manual open other bundle → reason `""` + normal Loaded status |

Replace in `test_app_shell_smoke.gd`:
`test_cli_stub_records_decision_without_navigation` → removed; covered by §6.4/§6.5 deep-link tests.

---

## 7. Tasks (TDD)

Local commands from `showdownbot_studio/godot/`:

```powershell
.\tools\verify_engine_pin.ps1
.\tools\run_gdunit_headless.ps1 -a "res://tests/decision/test_decision_presenter.gd"
.\tools\run_gdunit_headless.ps1 -a "res://tests/decision/"
.\tools\run_gdunit_headless.ps1 -a "res://tests/workspace/test_app_shell_decision.gd"
.\tools\run_gdunit_headless.ps1 -a "res://tests/"
```

Windows LF restore if `hash_mismatch` (do **not** change git config; do **not**
`Remove-Item -Recurse` / wipe fixture trees — that can destroy untracked local fixture work):

```powershell
# 1) Inspect dirtiness first — refuse to proceed if unexpected untracked fixture edits matter
git status --short -- ../fixtures/viewer-v0 tests/fixtures

# 2) Restore only known *tracked* paths needed by Plan D tests.
#    `git checkout -- <dir>` updates tracked files under that dir; untracked siblings stay.
#    Prefer listing concrete tracked files if status shows mixed local work.
git -c core.autocrlf=input -c core.eol=lf checkout HEAD -- `
  ../fixtures/viewer-v0/bundles/fixture-01/manifest.json `
  ../fixtures/viewer-v0/bundles/fixture-01/battle.jsonl `
  ../fixtures/viewer-v0/bundles/fixture-01/decisions.jsonl `
  ../fixtures/viewer-v0/bundles/fixture-01/config-manifest.json `
  ../fixtures/viewer-v0/bundles/fixture-01/warnings.json `
  ../fixtures/viewer-v0/bundles/fixture-03/manifest.json `
  ../fixtures/viewer-v0/bundles/fixture-03/battle.jsonl `
  ../fixtures/viewer-v0/bundles/fixture-03/decisions.jsonl `
  ../fixtures/viewer-v0/bundles/fixture-03/config-manifest.json `
  ../fixtures/viewer-v0/bundles/fixture-03/warnings.json `
  ../fixtures/viewer-v0/bundles/fixture-04/manifest.json `
  ../fixtures/viewer-v0/bundles/fixture-04/battle.jsonl `
  ../fixtures/viewer-v0/bundles/fixture-04/config-manifest.json `
  ../fixtures/viewer-v0/bundles/fixture-16/manifest.json `
  ../fixtures/viewer-v0/bundles/fixture-16/decisions.jsonl `
  ../fixtures/viewer-v0/bundles/fixture-16/config-manifest.json `
  ../fixtures/viewer-v0/bundles/fixture-16/warnings.json `
  ../fixtures/viewer-v0/sources/fixture-06/bundle/manifest.json `
  ../fixtures/viewer-v0/sources/fixture-06/bundle/battle.jsonl `
  ../fixtures/viewer-v0/sources/fixture-06/bundle/decisions.jsonl `
  ../fixtures/viewer-v0/sources/fixture-06/bundle/config-manifest.json `
  ../fixtures/viewer-v0/sources/fixture-06/bundle/warnings.json
```

### Task D0 — DecisionPresenter

**Files:**
- Create: `src/decision/decision_presenter.gd` (exact §4.1) + `.uid`
- Create: `tests/decision/test_decision_presenter.gd` (+ `.uid`)

- [ ] **Step 1: Write failing tests** (all §6.1). Critical bodies:

```gdscript
func test_empty_candidates_no_chosen_row() -> void:
	var bundle := _fixture_bundle("bundles/fixture-01")
	var d: DecisionRowDTO = null
	for row in bundle.decisions:
		if row.candidates.is_empty():
			d = row
			break
	assert_object(d).is_not_null()
	assert_int(DecisionPresenter.resolve_chosen_row_index(d)).is_equal(-1)


func test_aggregation_all_null_label() -> void:
	var bundle := _fixture_bundle("bundles/fixture-03")
	var d: DecisionRowDTO = bundle.decisions[0]
	assert_str(DecisionPresenter.aggregation_headline(d)).is_equal(
		DecisionPresenter.AGGREGATION_NOT_RECORDED
	)


func test_sort_modes_preserve_chosen_identity() -> void:
	var bundle := _fixture_bundle("bundles/fixture-01")
	var d: DecisionRowDTO = null
	for row in bundle.decisions:
		if row.candidates.size() >= 2 and row.decision_valid:
			d = row
			break
	assert_object(d).is_not_null()
	var chosen := DecisionPresenter.resolve_chosen_row_index(d)
	assert_int(chosen).is_greater(-1)
	var key := str(d.candidates[chosen].candidate_key)
	for mode in [
		DecisionPresenter.SORT_RANK, DecisionPresenter.SORT_SCORE,
		DecisionPresenter.SORT_LABEL, DecisionPresenter.SORT_KEY,
		DecisionPresenter.SORT_CHOSEN_FIRST,
	]:
		var order := DecisionPresenter.sorted_candidate_indices(d, mode)
		var seen := false
		for idx in order:
			if int(idx) == chosen:
				seen = true
				assert_str(str(d.candidates[int(idx)].candidate_key)).is_equal(key)
		assert_bool(seen).is_true()


func test_next_fallback_fixture03() -> void:
	var bundle := _fixture_bundle("bundles/fixture-03")
	var start_id: int = bundle.decisions[
		DecisionPresenter.first_row_by_decision_index(bundle)
	].decision_index
	var row := DecisionPresenter.find_next_nav_row(bundle, start_id - 1, "fallback")
	assert_int(row).is_greater(-1)
	assert_bool(bundle.decisions[row].fallback_used).is_true()


func test_valid_chosen_key_unique() -> void:
	var bundle := _fixture_bundle("bundles/fixture-01")
	var d: DecisionRowDTO = null
	for row in bundle.decisions:
		if row.candidates.size() >= 1 and row.chosen_candidate_key != null:
			d = row
			break
	assert_object(d).is_not_null()
	var chosen := DecisionPresenter.resolve_chosen_row_index(d)
	assert_int(chosen).is_greater(-1)
	assert_str(str(d.candidates[chosen].candidate_key)).is_equal(str(d.chosen_candidate_key))


func test_invalid_decision_no_highlight() -> void:
	var d := DecisionRowDTO.new()
	d.decision_index = 9
	d.turn_number = 1
	d.decision_phase = BundleMode.PHASE_REGULAR_TURN
	d.decision_latency_ms = 1.0
	d.observable_state_hash = "obs"
	d.request_hash = "req"
	d.state_summary = {}
	d.normalized_action = {}
	d.actual_choose_string = "move 1"
	d.candidates = [
		_make_candidate("A", 1, 1.0, "key-a"),
		_make_candidate("B", 2, 0.5, "key-b"),
	]
	d.chosen_candidate_key = "key-missing"
	d.fallback_used = false
	d.warning_count = 0
	d.decision_valid = false
	d.seal()
	assert_int(DecisionPresenter.resolve_chosen_row_index(d)).is_equal(-1)


func test_never_label_matches_chosen_id() -> void:
	var d := DecisionRowDTO.new()
	d.decision_index = 9
	d.turn_number = 1
	d.decision_phase = BundleMode.PHASE_REGULAR_TURN
	d.decision_latency_ms = 1.0
	d.observable_state_hash = "obs"
	d.request_hash = "req"
	d.state_summary = {}
	d.normalized_action = {}
	d.actual_choose_string = "move 1"
	d.candidates = [_make_candidate("looks-chosen", 1, 1.0, "structural-a")]
	d.chosen_candidate_key = "structural-missing"
	d.chosen_candidate_id = "looks-chosen"
	d.fallback_used = false
	d.warning_count = 0
	d.decision_valid = true  # must reach key scan; label must not win
	d.seal()
	assert_int(DecisionPresenter.resolve_chosen_row_index(d)).is_equal(-1)


func test_next_close_skips_null_margin() -> void:
	var d0 := DecisionRowDTO.new()
	d0.decision_index = 0
	d0.turn_number = 1
	d0.decision_phase = BundleMode.PHASE_REGULAR_TURN
	d0.decision_latency_ms = 0.0
	d0.observable_state_hash = "o"
	d0.request_hash = "r"
	d0.state_summary = {}
	d0.normalized_action = {}
	d0.actual_choose_string = ""
	d0.candidates = []
	d0.top1_top2_margin = null
	d0.fallback_used = false
	d0.warning_count = 0
	d0.decision_valid = true
	d0.seal()
	var d1 := DecisionRowDTO.new()
	d1.decision_index = 1
	d1.turn_number = 1
	d1.decision_phase = BundleMode.PHASE_REGULAR_TURN
	d1.decision_latency_ms = 0.0
	d1.observable_state_hash = "o"
	d1.request_hash = "r"
	d1.state_summary = {}
	d1.normalized_action = {}
	d1.actual_choose_string = "move 1"
	d1.candidates = [
		_make_candidate("A", 1, 10.0, "a"),
		_make_candidate("B", 2, 7.0, "b"),
	]
	d1.chosen_candidate_key = "a"
	d1.top1_top2_margin = 3.0
	d1.fallback_used = false
	d1.warning_count = 0
	d1.decision_valid = true
	d1.seal()
	var bundle := BundleDTO.new()
	bundle.declared_mode = BundleMode.TRACE_ONLY
	bundle.effective_mode = BundleMode.TRACE_ONLY
	bundle.replay_trusted = false
	bundle.trace_trusted = true
	bundle.manifest = _make_manifest()
	bundle.warnings = []
	bundle.downgrade_warnings = []
	bundle.config_manifest = null
	bundle.battle_events = []
	bundle.decisions = [d0, d1]
	bundle.seal()
	var row := DecisionPresenter.find_next_nav_row(bundle, -1, "close")
	assert_int(row).is_equal(1)
	assert_float(float(bundle.decisions[row].top1_top2_margin)).is_equal(3.0)
```

- [ ] **Step 2: RED**

```powershell
.\tools\run_gdunit_headless.ps1 -a "res://tests/decision/test_decision_presenter.gd"
```

Expected: FAIL (missing class / asserts).

- [ ] **Step 3: Implement** exact §4.1 (no stubs).
- [ ] **Step 4: GREEN** — same command PASS.
- [ ] **Step 5: Commit**

```powershell
git add src/decision/decision_presenter.gd src/decision/decision_presenter.gd.uid `
  tests/decision/test_decision_presenter.gd tests/decision/test_decision_presenter.gd.uid
git commit --trailer "Co-authored-by: Cursor <cursoragent@cursor.com>" -m "feat(studio): DecisionPresenter chosen-key and navigation helpers"
```

---

### Task D1 — DecisionController

**Files:**
- Create: `src/decision/decision_controller.gd` (+ `.uid`) exact §4.2
- Create: `tests/decision/test_decision_controller.gd` (+ `.uid`)

- [ ] **Step 1: Write failing tests** (all §6.2). Critical bodies:

```gdscript
func test_timeline_event_keeps_row() -> void:
	var bundle := _fixture_bundle("bundles/fixture-01")
	var replay := BattleTimeline.build(bundle)
	var ctl := TimelineController.new()
	add_child(ctl)
	var dec := DecisionController.new()
	add_child(dec)
	dec.reset(bundle, ctl)
	ctl.reset(replay, bundle)
	await await_idle_frame()
	var decision_entry := -1
	for i in range(replay.entries.size()):
		if replay.entries[i].kind == TimelineEntryKind.DECISION:
			decision_entry = i
			break
	assert_int(decision_entry).is_greater(-1)
	ctl.select(decision_entry)
	await await_idle_frame()
	var row_after_decision := dec.get_selected_decision_row_index()
	var event_entry := -1
	for i in range(replay.entries.size()):
		if replay.entries[i].kind == TimelineEntryKind.EVENT:
			event_entry = i
			break
	ctl.select(event_entry)
	await await_idle_frame()
	assert_int(dec.get_selected_decision_row_index()).is_equal(row_after_decision)


func test_select_row_syncs_timeline() -> void:
	var bundle := _fixture_bundle("bundles/fixture-01")
	var replay := BattleTimeline.build(bundle)
	var ctl := TimelineController.new()
	add_child(ctl)
	var dec := DecisionController.new()
	add_child(dec)
	ctl.reset(replay, bundle)
	dec.reset(bundle, ctl)
	var cursor_after_reset := ctl.get_selected_entry_index()
	var target_row := 0
	for i in range(bundle.decisions.size()):
		if bundle.decisions[i].candidates.size() > 0:
			target_row = i
			break
	dec.select_decision_row(target_row)
	await await_idle_frame()
	var entry := DecisionPresenter.timeline_entry_for_decision_row(replay, target_row)
	assert_int(ctl.get_selected_entry_index()).is_equal(entry)
	assert_int(cursor_after_reset).is_equal(0)  # Plan C start; reset did not move it


func test_reset_does_not_move_timeline_cursor() -> void:
	var events: Array = [
		_make_event(1, "turn", {"amount": 1}),
		_make_event(2, "turn", {"amount": 2}),
	]
	var decisions: Array = [_make_decision(5, 2, true)]
	var bundle := _make_minimal_bundle_with_decisions(decisions, events)
	var replay := BattleTimeline.build(bundle)
	var ctl := TimelineController.new()
	add_child(ctl)
	var dec := DecisionController.new()
	add_child(dec)
	ctl.reset(replay, bundle)
	assert_int(ctl.get_selected_entry_index()).is_equal(0)
	assert_str(replay.entries[0].kind).is_equal(TimelineEntryKind.EVENT)
	dec.reset(bundle, ctl)
	await await_idle_frame()
	assert_int(ctl.get_selected_entry_index()).is_equal(0)
	assert_int(dec.get_selected_decision().decision_index).is_equal(5)
```

- [ ] **Step 2: RED**

```powershell
.\tools\run_gdunit_headless.ps1 -a "res://tests/decision/test_decision_controller.gd"
```

- [ ] **Step 3: Implement** exact §4.2.
- [ ] **Step 4: GREEN**.
- [ ] **Step 5: Commit**

```powershell
git add src/decision/decision_controller.gd src/decision/decision_controller.gd.uid `
  tests/decision/test_decision_controller.gd tests/decision/test_decision_controller.gd.uid
git commit --trailer "Co-authored-by: Cursor <cursoragent@cursor.com>" -m "feat(studio): DecisionController bridges timeline and decision selection"
```

---

### Task D2 — Candidate table + detail views

**Files:**
- Create: `candidate_table_view.gd` + `.tscn` + `.uid` (exact §5.1 / §3.1)
- Create: `decision_detail_view.gd` + `.tscn` + `.uid` (exact §5.2 / §3.1)
- Create: `tests/decision/test_candidate_table_view.gd`, `test_decision_detail_view.gd` (+ uids)

- [ ] **Step 1: Write failing tests** (§6.3). Critical bodies:

```gdscript
func test_table_bounded_104_candidates() -> void:
	var bundle := _fixture_bundle("bundles/fixture-16")
	var d: DecisionRowDTO = null
	for row in bundle.decisions:
		if row.candidates.size() == 104:
			d = row
			break
	assert_object(d).is_not_null()
	var view: CandidateTableView = preload("res://src/decision/candidate_table_view.tscn").instantiate()
	add_child(view)
	await await_idle_frame()
	view.bind(d)
	assert_int(view.get_item_count()).is_equal(104)


func test_detail_shows_aggregation_not_recorded() -> void:
	var bundle := _fixture_bundle("bundles/fixture-03")
	var view: DecisionDetailView = preload("res://src/decision/decision_detail_view.tscn").instantiate()
	add_child(view)
	await await_idle_frame()
	view.bind_decision(bundle.decisions[0])
	assert_bool(
		view.get_aggregation_text().contains(DecisionPresenter.AGGREGATION_NOT_RECORDED)
	).is_true()


func test_selected_ne_chosen_keeps_chosen_marker() -> void:
	var view: CandidateTableView = preload("res://src/decision/candidate_table_view.tscn").instantiate()
	add_child(view)
	await await_idle_frame()
	var bundle := _fixture_bundle("bundles/fixture-01")
	var d: DecisionRowDTO = null
	for row in bundle.decisions:
		if row.candidates.size() >= 2 and row.decision_valid:
			d = row
			break
	assert_object(d).is_not_null()
	view.bind(d)
	var chosen := DecisionPresenter.resolve_chosen_row_index(d)
	assert_int(chosen).is_greater(-1)
	var chosen_visual_before := view.get_chosen_item_index()
	assert_int(chosen_visual_before).is_greater(-1)
	var other := 0 if chosen != 0 else 1
	view.select_candidate_index(other)
	assert_int(view.get_selected_candidate_index()).is_equal(other)
	assert_int(view.get_selected_candidate_index()).is_not_equal(chosen)
	assert_int(view.get_chosen_item_index()).is_equal(chosen_visual_before)
	assert_int(DecisionPresenter.resolve_chosen_row_index(d)).is_equal(chosen)


func test_filter_resyncs_selection_signal() -> void:
	var view: CandidateTableView = preload("res://src/decision/candidate_table_view.tscn").instantiate()
	add_child(view)
	await await_idle_frame()
	var bundle := _fixture_bundle("bundles/fixture-01")
	var d: DecisionRowDTO = null
	for row in bundle.decisions:
		if row.candidates.size() >= 2 and row.decision_valid:
			d = row
			break
	assert_object(d).is_not_null()
	view.bind(d)
	var chosen := DecisionPresenter.resolve_chosen_row_index(d)
	var other := 0 if chosen != 0 else 1
	view.select_candidate_index(other)
	var emitted := [-2]
	view.candidate_selected.connect(func(i: int) -> void: emitted[0] = i)
	view.set_chosen_only(true)
	assert_int(emitted[0]).is_equal(chosen)
	assert_int(view.get_selected_candidate_index()).is_equal(chosen)
	assert_int(view.get_chosen_item_index()).is_greater(-1)
```

- [ ] **Step 2: RED**

```powershell
.\tools\run_gdunit_headless.ps1 -a "res://tests/decision/test_candidate_table_view.gd"
.\tools\run_gdunit_headless.ps1 -a "res://tests/decision/test_decision_detail_view.gd"
```

- [ ] **Step 3: Implement** §5.1–5.2 + scenes.
- [ ] **Step 4: GREEN** — both suites PASS. **Required before D2 commit.**
- [ ] **Step 5: Commit**

```powershell
git add src/decision/candidate_table_view.gd src/decision/candidate_table_view.gd.uid `
  src/decision/candidate_table_view.tscn `
  src/decision/decision_detail_view.gd src/decision/decision_detail_view.gd.uid `
  src/decision/decision_detail_view.tscn `
  tests/decision/test_candidate_table_view.gd tests/decision/test_candidate_table_view.gd.uid `
  tests/decision/test_decision_detail_view.gd tests/decision/test_decision_detail_view.gd.uid
git commit --trailer "Co-authored-by: Cursor <cursoragent@cursor.com>" -m "feat(studio): bounded candidate table and decision detail tabs"
```

---

### Task D3 — DecisionWorkspace + AppShell mount

**Files:**
- Create: `decision_workspace.gd` + `.tscn` + `.uid` (exact §5.3)
- Modify: `app_shell.gd` / `app_shell.tscn` — **only** §5.4.1 surface (mount, clear, reset).
  **Forbidden in D3:** any `DecisionDeepLink` type, `_pending_deep_link`, `_apply_pending_deep_link`,
  `_deep_link_refuse_reason`. Leave tip `parse_cli_args` int stub untouched until D4.
- Create: `tests/workspace/test_app_shell_decision.gd` — §6.5 **without** §6.5.1 deep-link cases
- [ ] **Step 1: Write failing tests** (fixture-01/03/04/16 subset of §6.5, no deep link). Critical:

```gdscript
func test_fixture04_no_candidate_claims() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-04"))
	await _await_shell_settled(shell)
	var ws := shell.get_decision_workspace()
	assert_bool(ws.get_empty_state_visible()).is_true()
	assert_int(ws.get_candidate_table_view().get_item_count()).is_equal(0)


func test_fixture01_timeline_and_decision_nav_same_index() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	var replay_ws := shell.get_replay_workspace()
	var dec_ws := shell.get_decision_workspace()
	var timeline := replay_ws.get_timeline_controller()
	var replay: ReplayDTO = timeline.get_replay()
	var decision_entry := -1
	for i in range(replay.entries.size()):
		if replay.entries[i].kind == TimelineEntryKind.DECISION:
			decision_entry = i
			break
	timeline.select(decision_entry)
	await await_idle_frame()
	var from_timeline: int = dec_ws.get_decision_controller().get_selected_decision().decision_index
	dec_ws.get_decision_controller().jump_next("decision")
	await await_idle_frame()
	var from_decision: int = dec_ws.get_decision_controller().get_selected_decision().decision_index
	var entry_i := timeline.get_selected_entry_index()
	var row_i: int = replay.entries[entry_i].decision_row_index
	assert_int(shell.get_loaded_bundle().decisions[row_i].decision_index).is_equal(from_decision)
	assert_int(from_timeline).is_greater(-1)
```

```gdscript
func test_fixture16_104_candidates_bind() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-16"))
	await _await_shell_settled(shell)
	var dec := shell.get_decision_workspace().get_decision_controller()
	var bundle := shell.get_loaded_bundle()
	var row_104 := -1
	for i in range(bundle.decisions.size()):
		if bundle.decisions[i].candidates.size() == 104:
			row_104 = i
			break
	assert_int(row_104).is_greater(-1)
	dec.select_decision_row(row_104)
	await await_idle_frame()
	assert_int(
		shell.get_decision_workspace().get_candidate_table_view().get_item_count()
	).is_equal(104)


func test_fixture01_reset_keeps_plan_c_timeline_cursor() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	var timeline := shell.get_replay_workspace().get_timeline_controller()
	var replay: ReplayDTO = timeline.get_replay()
	assert_int(timeline.get_selected_entry_index()).is_equal(0)
	assert_str(replay.entries[0].kind).is_not_equal("")  # Plan C entry 0 preserved
	# Decision panel may already show first decision_index without moving timeline.
	var selected := shell.get_decision_workspace().get_decision_controller().get_selected_decision()
	assert_object(selected).is_not_null()
	assert_int(timeline.get_selected_entry_index()).is_equal(0)


func test_workspace_candidate_signal_updates_detail() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	var ws := shell.get_decision_workspace()
	var table := ws.get_candidate_table_view()
	var detail := ws.get_detail_view()
	var d: DecisionRowDTO = ws.get_decision_controller().get_selected_decision()
	# Prefer a multi-candidate decision if current row is empty/single.
	if d == null or d.candidates.size() < 2 or not d.decision_valid:
		var bundle := shell.get_loaded_bundle()
		for i in range(bundle.decisions.size()):
			var row: DecisionRowDTO = bundle.decisions[i]
			if row.candidates.size() >= 2 and row.decision_valid:
				ws.get_decision_controller().select_decision_row(i)
				await await_idle_frame()
				d = row
				break
	assert_object(d).is_not_null()
	var chosen := DecisionPresenter.resolve_chosen_row_index(d)
	var other := 0 if chosen != 0 else 1
	table.select_candidate_index(other)
	await await_idle_frame()
	assert_bool(detail.get_candidate_id_text().contains(d.candidates[other].candidate_id)).is_true()
	assert_int(table.get_selected_candidate_index()).is_equal(other)


func test_workspace_filter_resyncs_detail() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	var ws := shell.get_decision_workspace()
	var table := ws.get_candidate_table_view()
	var detail := ws.get_detail_view()
	var d: DecisionRowDTO = ws.get_decision_controller().get_selected_decision()
	if d == null or d.candidates.size() < 2 or not d.decision_valid:
		var bundle := shell.get_loaded_bundle()
		for i in range(bundle.decisions.size()):
			var row: DecisionRowDTO = bundle.decisions[i]
			if row.candidates.size() >= 2 and row.decision_valid:
				ws.get_decision_controller().select_decision_row(i)
				await await_idle_frame()
				d = row
				break
	assert_object(d).is_not_null()
	var chosen := DecisionPresenter.resolve_chosen_row_index(d)
	var other := 0 if chosen != 0 else 1
	table.select_candidate_index(other)
	await await_idle_frame()
	assert_bool(detail.get_candidate_id_text().contains(d.candidates[other].candidate_id)).is_true()
	table.set_chosen_only(true)
	await await_idle_frame()
	assert_int(table.get_selected_candidate_index()).is_equal(chosen)
	assert_bool(detail.get_candidate_id_text().contains(d.candidates[chosen].candidate_id)).is_true()


func test_start_load_clears_decision_before_async() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	assert_int(shell.get_decision_workspace().get_candidate_table_view().get_item_count()).is_greater(0)
	var loader: BundleLoader = shell.get_node("BundleLoader")
	var hooks := BundleWorker.WorkerHooks.new()
	var release := Semaphore.new()
	hooks.on_before_terminal_enqueue = func() -> void:
		release.wait()
	loader.set_worker_hooks(hooks)
	shell.open_bundle_path(_fixture_path("bundles/fixture-04"))
	var frames := 0
	while not shell.is_loading() and frames < 600:
		await await_idle_frame()
		frames += 1
	assert_bool(shell.is_loading()).is_true()
	assert_bool(shell.get_decision_workspace().get_empty_state_visible()).is_false()
	assert_int(shell.get_decision_workspace().get_candidate_table_view().get_item_count()).is_equal(0)
	assert_str(shell.get_decision_workspace().get_header_text()).is_equal("")
	release.post()
	await _await_shell_settled(shell)
```

- [ ] **Step 2: RED**

```powershell
.\tools\run_gdunit_headless.ps1 -a "res://tests/workspace/test_app_shell_decision.gd"
```

- [ ] **Step 3: Implement** §5.3 + AppShell §5.4.1 only. D3 must compile with **no**
  `DecisionDeepLink` symbol references.
- [ ] **Step 4: GREEN**.
- [ ] **Step 5: Commit**

```powershell
git add src/decision/decision_workspace.gd src/decision/decision_workspace.gd.uid `
  src/decision/decision_workspace.tscn `
  src/workspace/app_shell.gd src/workspace/app_shell.tscn `
  tests/workspace/test_app_shell_decision.gd tests/workspace/test_app_shell_decision.gd.uid
git commit --trailer "Co-authored-by: Cursor <cursoragent@cursor.com>" -m "feat(studio): mount DecisionWorkspace beside ReplayWorkspace"
```

---

### Task D4 — Deep link fail-closed

**Files:**
- Create: `decision_deep_link.gd` (+ `.uid`) exact §4.3
- Modify: `app_shell.gd` — full §5.4 parse/apply; remove `cli_decision_index`
- Create: `tests/decision/test_decision_deep_link.gd`
- Extend: `test_app_shell_decision.gd` deep-link cases
- Modify: `test_app_shell_smoke.gd` — delete int stub test

- [ ] **Step 1: Write failing tests** (§6.4 + deep-link §6.5). Critical:

```gdscript
func test_parse_rejects_bare_int() -> void:
	var r := DecisionDeepLink.parse_arg("2")
	assert_bool(r.ok).is_false()
	assert_str(r.reason).is_equal("malformed_decision_arg")


func test_parse_rejects_empty_string() -> void:
	var r := DecisionDeepLink.parse_arg("")
	assert_bool(r.ok).is_false()
	assert_str(r.reason).is_equal("malformed_decision_arg")


func test_deep_link_success() -> void:
	var bundle := _fixture_bundle("bundles/fixture-01")
	var target: DecisionRowDTO = bundle.decisions[1]
	var shell: AppShell = await _spawn_shell_ready()
	shell.parse_cli_args(PackedStringArray([
		"--decision", "%s:%d" % [bundle.manifest.battle_id, target.decision_index]
	]))
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	assert_str(shell.get_deep_link_refuse_reason()).is_equal("")
	assert_int(shell.get_selected_decision_index()).is_equal(target.decision_index)


func test_deep_link_mismatch_refuses() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.parse_cli_args(PackedStringArray(["--decision", "wrong-battle:1"]))
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	assert_str(shell.get_deep_link_refuse_reason()).is_equal("battle_id_mismatch")
	assert_bool(shell.get_status_text().contains("Deep link refused")).is_true()
	assert_object(shell.get_loaded_bundle()).is_not_null()


func test_deep_link_missing_value_malformed() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.parse_cli_args(PackedStringArray(["--decision"]))
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	assert_str(shell.get_deep_link_refuse_reason()).is_equal("malformed_decision_arg")
	assert_object(shell.get_loaded_bundle()).is_not_null()


func test_deep_link_one_shot_not_reapplied_on_manual_open() -> void:
	var bundle := _fixture_bundle("bundles/fixture-01")
	var target: DecisionRowDTO = bundle.decisions[1]
	var shell: AppShell = await _spawn_shell_ready()
	shell.parse_cli_args(PackedStringArray([
		"--decision", "%s:%d" % [bundle.manifest.battle_id, target.decision_index]
	]))
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	assert_int(shell.get_selected_decision_index()).is_equal(target.decision_index)
	# Manual open of a different battle without re-parsing CLI must not re-apply pending.
	shell.open_bundle_path(_fixture_path("bundles/fixture-03"))
	await _await_shell_settled(shell)
	assert_str(shell.get_deep_link_refuse_reason()).is_equal("")
	assert_str(shell.get_loaded_bundle().manifest.battle_id).is_equal("synthetic00000003")


func test_deep_link_refuse_cleared_on_later_manual_open() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.parse_cli_args(PackedStringArray(["--decision", "wrong-battle:1"]))
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	assert_str(shell.get_deep_link_refuse_reason()).is_equal("battle_id_mismatch")
	assert_bool(shell.get_status_text().contains("Deep link refused")).is_true()
	# Fresh manual open with no pending deep link must restore normal Loaded status.
	shell.open_bundle_path(_fixture_path("bundles/fixture-03"))
	await _await_shell_settled(shell)
	assert_str(shell.get_deep_link_refuse_reason()).is_equal("")
	assert_bool(shell.get_status_text().contains("Deep link refused")).is_false()
	assert_str(shell.get_loaded_bundle().manifest.battle_id).is_equal("synthetic00000003")
```

- [ ] **Step 2: RED**
- [ ] **Step 3: Implement** §4.3 + §5.4.2 atomically; remove `cli_decision_index` + smoke stub test.
- [ ] **Step 4: GREEN**.
- [ ] **Step 5: Commit**

```powershell
git add src/decision/decision_deep_link.gd src/decision/decision_deep_link.gd.uid `
  src/workspace/app_shell.gd `
  tests/decision/test_decision_deep_link.gd tests/decision/test_decision_deep_link.gd.uid `
  tests/workspace/test_app_shell_decision.gd tests/workspace/test_app_shell_smoke.gd
git commit --trailer "Co-authored-by: Cursor <cursoragent@cursor.com>" -m "feat(studio): fail-closed battle_id:decision_index deep links"
```

---

### Task D5 — Full regression + pin

- [ ] **Step 1:**

```powershell
.\tools\verify_engine_pin.ps1
.\tools\run_gdunit_headless.ps1 -a "res://tests/"
```

Expected: pin PASS; Plan B + C + D green; 2 privilege skips remain skips.

- [ ] **Step 2:** `git diff --check` clean.
- [ ] **Step 3: Commit** only if leftover fix required:

```text
test(studio): Plan D decision-inspection regression green
```

---

## 8. Acceptance (Plan D done)

- Fixture **01**: after open, Plan C timeline cursor at entry 0 is preserved; user DECISION nav and
  decision nav share `decision_index`; empty d0 has no chosen row; later rows highlight unique key;
  sort/filter preserve chosen identity; selected≠chosen never moves chosen marker.
- Fixture **03**: next-fallback reaches `fallback_used`; Overview shows `aggregation mode not recorded`.
- Fixture **16**: empty candidates clean; 104-candidate bind bounded; TRACE_ONLY panel works with Plan C empty board.
- Fixture **04**: empty-state; no candidate claims.
- Deep link: success + malformed (incl. `--decision` without value) / mismatch / missing /
  `trace_not_trusted`; never silent substitute; one-shot pending; refuse reason cleared on later
  manual open (normal Loaded status); bundle remains loaded on refuse.
- Candidate detail tab follows table selection via workspace signal path; filter/chosen-only
  re-emits so table + detail stay aligned; filter owned by Plan D.
- `_start_load` clears decision + replay (+ deep-link refuse reason in D4) before `load_async`.
- No Plan E/F scope beyond E’s focus-filter shortcut ownership note; sealed Plan B DTOs remain authority.
- Pin PASS + full gdUnit green (privilege skips only).

---

## 9. Visual input

Follow [`../design/viewer-v0-mockups/README.md`](../design/viewer-v0-mockups/README.md): dense text table, not cards; abstract board already Plan C. Offline fonts / remappable shortcuts / global banner → Plan E. Candidate filter LineEdit is Plan D; Plan E only focuses it.

---

## 10. Self-review checklist (this Rev. 5 APPROVED)

- [x] Grounded against `1b0be1d` sealed DTOs (flattened aggregation)
- [x] `decision_row_index` vs `decision_index` separated
- [x] Full GDScript bodies — no `...` stubs in code fences
- [x] Full scene trees for workspace/table/detail/shell
- [x] ItemList line format locked in §0.11 and implemented in §5.1 identically
- [x] Candidate selected ≠ chosen; Candidate tab; filter in D; E = focus only
- [x] Filter/chosen-only emit `candidate_selected`; workspace signal-path tests
- [x] D3 compiles without `DecisionDeepLink`; D4 atomic CLI
- [x] `--decision` missing value → `malformed_decision_arg`
- [x] Deep-link one-shot consume pending
- [x] Deep-link refuse cleared on later manual open
- [x] Decision reset does not override Plan C timeline cursor
- [x] Safe EOL restore (no recursive fixture deletes)
- [x] `test_never_label_matches_chosen_id` uses `decision_valid=true`
- [x] Timeline bidirectional sync on user/deep-link only + EVENT keeps decision
- [x] Scope fence vs E/F explicit; choice points closed
- [x] Status marked **APPROVED** — implementation authorized
- [x] Parity pass vs Plans A/B/C structure
---

## 11. Stale status documents (report only)

Studio README / plans README / implementation-index tip line were updated on this branch for A/B/C merge status + Next=Plan D review. Plan A/B/C **headers** retain historical authorization wording (docs APPROVED gates); tip delivery status lives in README/index tip line. Do not rewrite Plan A/B/C bodies in Plan D.

---

## 12. Rev. 5 changelog

| Item | Change |
|---|---|
| Rev. 4 → Rev. 5 | Filter emits selection for detail sync; clear sticky deep-link refuse on manual load; workspace signal-path tests |
| Rev. 3 → Rev. 4 | D3 free of DeepLink; candidate selection/detail/filter; missing `--decision` value; one-shot; cursor; EOL; label test |
| Rev. 2 → Rev. 3 | Plan A/B/C parity pass |
| Rev. 1 → Rev. 2 | Expand to executable depth |
| Open O1–O8 | Closed as binding §0.15 choice points |

---

## 13. Handoff

After APPROVED + go-ahead: isolated worktree from tip; execute D0→D5; no exporter / `showdown_bot/`
edits; stop for review between tasks if using subagent-driven flow.

---

## 14. Shared test helpers (binding copy for decision suites)

Each new decision test suite includes these helpers (same pattern as Plan C presenter tests).
Do not invent alternate fixture loaders.

```gdscript
const _FIXTURES_ROOT := "res://../fixtures/viewer-v0"
const _APP_SHELL_SCENE := preload("res://src/workspace/app_shell.tscn")


func _fixture_path(relative: String) -> String:
	return ProjectSettings.globalize_path(_FIXTURES_ROOT.path_join(relative))


func _fixture_bundle(rel: String) -> BundleDTO:
	var path := _fixture_path(rel)
	var result: ValidationResult = BundleValidator.validate_dir(path)
	assert_object(result.bundle).is_not_null()
	return result.bundle


func _spawn_shell() -> AppShell:
	var shell: AppShell = _APP_SHELL_SCENE.instantiate()
	add_child(shell)
	return shell


func _spawn_shell_ready() -> AppShell:
	var shell := _spawn_shell()
	await await_idle_frame()
	return shell


func _await_shell_settled(shell: AppShell, max_frames: int = 600) -> void:
	var frames := 0
	while shell.is_loading() and frames < max_frames:
		await await_idle_frame()
		frames += 1
	assert_bool(shell.is_loading()).is_false()


func _make_candidate(candidate_id: String, rank: int, score: float, key: Variant) -> CandidateDTO:
	var c := CandidateDTO.new()
	c.candidate_id = candidate_id
	c.rank = rank
	c.aggregate_score = score
	c.candidate_key = key
	c.seal()
	return c


func _make_file_entry(present: bool = true) -> FileEntryDTO:
	var entry := FileEntryDTO.new()
	entry.path = "battle.jsonl" if present else null
	entry.present = present
	entry.required = present
	entry.sha256 = "abc" if present else null
	return entry


func _make_files_table() -> FilesTableDTO:
	var table := FilesTableDTO.new()
	table.battle_log = _make_file_entry(true)
	table.decision_trace = _make_file_entry(true)
	table.warnings = _make_file_entry(false)
	table.config_manifest = _make_file_entry(false)
	return table


func _make_privacy() -> PrivacyDTO:
	var privacy := PrivacyDTO.new()
	privacy.profile = "portable-pseudonymous-v1"
	privacy.chat = "excluded"
	privacy.private_messages = "excluded"
	privacy.player_names = "seat-pseudonyms"
	privacy.source_url = "excluded"
	privacy.raw_source_included = false
	return privacy


func _make_source_provenance() -> SourceProvenanceDTO:
	var provenance := SourceProvenanceDTO.new()
	provenance.dirty = false
	provenance.our_side = "p1"
	provenance.config_id = "cfg-1"
	provenance.schedule_hash = "sched"
	provenance.seed_index = 0
	return provenance


func _make_manifest() -> BundleManifestDTO:
	var manifest := BundleManifestDTO.new()
	manifest.schema_major = 1
	manifest.schema_minor = 0
	manifest.required_capabilities = PackedStringArray(["viewer-v0"])
	manifest.exporter_name = "test-exporter"
	manifest.exporter_version = "0.0.0"
	manifest.battle_id = "battle-1"
	manifest.format_id = "gen9ou"
	manifest.git_sha = "deadbeef"
	manifest.config_hash = "cfg-hash"
	manifest.trace_schema_version = BundleMode.TRACE_VERSION_V3
	manifest.privacy = _make_privacy()
	manifest.source_hashes_battle_log = "hash-bl"
	manifest.source_hashes_decision_trace = "hash-dt"
	manifest.files = _make_files_table()
	manifest.source_provenance = _make_source_provenance()
	return manifest


func _make_event(protocol_index: int, type: String, fields: Dictionary = {}) -> BattleEventDTO:
	var e := BattleEventDTO.new()
	e.protocol_index = protocol_index
	e.type = type
	for key in fields.keys():
		e.set(key, fields[key])
	return e


func _make_decision(decision_index: int, request_protocol_index: Variant, valid: bool) -> DecisionRowDTO:
	var d := DecisionRowDTO.new()
	d.decision_index = decision_index
	d.request_protocol_index = request_protocol_index
	d.decision_valid = valid
	d.turn_number = 1
	d.decision_phase = BundleMode.PHASE_REGULAR_TURN
	d.decision_latency_ms = 0.0
	d.observable_state_hash = "obs"
	d.request_hash = "req"
	d.state_summary = {}
	d.normalized_action = {}
	d.actual_choose_string = "move 1"
	d.fallback_used = false
	d.warning_count = 0
	return d


func _make_replay_only_bundle(events: Array) -> BundleDTO:
	var bundle := BundleDTO.new()
	bundle.declared_mode = BundleMode.REPLAY_ONLY
	bundle.effective_mode = BundleMode.REPLAY_ONLY
	bundle.replay_trusted = true
	bundle.trace_trusted = false
	bundle.manifest = _make_manifest()
	bundle.warnings = []
	bundle.downgrade_warnings = []
	bundle.config_manifest = null
	var sealed_events: Array = []
	for item in events:
		var e: BattleEventDTO = item
		e.seal()
		sealed_events.append(e)
	bundle.battle_events = sealed_events
	bundle.decisions = []
	bundle.seal()
	return bundle


func _make_minimal_bundle_with_decisions(decisions: Array, events: Array) -> BundleDTO:
	var bundle := BundleDTO.new()
	bundle.declared_mode = BundleMode.REPLAY_TRACE
	bundle.effective_mode = BundleMode.REPLAY_TRACE
	bundle.replay_trusted = true
	bundle.trace_trusted = true
	bundle.manifest = _make_manifest()
	bundle.warnings = []
	bundle.downgrade_warnings = []
	bundle.config_manifest = null
	var sealed_events: Array = []
	for item in events:
		var e: BattleEventDTO = item
		e.seal()
		sealed_events.append(e)
	var sealed_decisions: Array = []
	for item in decisions:
		var d: DecisionRowDTO = item
		d.seal()
		sealed_decisions.append(d)
	bundle.battle_events = sealed_events
	bundle.decisions = sealed_decisions
	bundle.seal()
	return bundle
```

No new unit JSONL. Workspace tests also call `after_test` free of `AppShell` /
`DecisionWorkspace` / `DecisionController` children exactly as Plan C / smoke suites.

Also add in §6 intro: helpers above are **binding** — do not invent alternate loaders.

---

## 15. Suggested commit cadence (summary)

| Task | Commit message |
|---|---|
| D0 | `feat(studio): DecisionPresenter chosen-key and navigation helpers` |
| D1 | `feat(studio): DecisionController bridges timeline and decision selection` |
| D2 | `feat(studio): bounded candidate table and decision detail tabs` |
| D3 | `feat(studio): mount DecisionWorkspace beside ReplayWorkspace` |
| D4 | `feat(studio): fail-closed battle_id:decision_index deep links` |
| D5 | `test(studio): Plan D decision-inspection regression green` (only if needed) |

---

## 16. Review-response ledger (Rev. 5)

| Risk | Mitigation in this DRAFT |
|---|---|
| Filter desyncs Candidate detail | §5.1 emit after filter/chosen-only/bind; workspace filter+signal tests |
| Sticky deep-link refuse after manual open | Clear reason in `_start_load` + no-pending apply; refuse→manual test |
| Weak detail test (manual bind) | `test_workspace_candidate_signal_updates_detail` uses real signal path |
| D3 references DeepLink before D4 | §5.4.1 / D3 forbids DeepLink symbols; D4 atomic §5.4.2 |
| No candidate selection/detail | §0.6.1 + §5.1 signal/API + Candidate tab + tests |
| Filter orphaned to E | §0.11 filter in D; Plan E focus-only (sketch amended) |
| `--decision` without value silent | §5.4.2 + `test_deep_link_missing_value_malformed` |
| Pending deep link re-applied | One-shot clear + `test_deep_link_one_shot_*` |
| Decision reset overrides Plan C cursor | §0.6 no timeline sync on reset + controller/shell tests |
| Destructive EOL delete | Tracked-path checkout after `git status` only |
| Weak label-identity test | `decision_valid=true` + wrong key + matching label |
| Sketch-level ambiguity | Full §0 closed decisions + §0.15 choice points |
| Flattened aggregation missed | §0.1.1 + §4.1 `aggregation_headline` |
| 104-cand on wrong fixture | §0.12 / D2 binds fixture-16 |
