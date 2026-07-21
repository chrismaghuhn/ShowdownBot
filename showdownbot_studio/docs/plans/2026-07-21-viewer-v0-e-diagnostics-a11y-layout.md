# Viewer v0 — Plan E: Diagnostics, Accessibility, and Layout

**Status:** DRAFT — executable plan for review; **implementation not authorized**
**Date:** 2026-07-21 · **Rev.:** 1 (sketch → executable)
**Depends on (code start, when APPROVED + go-ahead):** Plans B–D **merged** on `main`
@ `0256602` (PR **#44** / **#46** / **#47** + follow-ups PR **#48** @ `19e1bc7`).
Filter UI + semantics ship in Plan D — Plan E only wires keyboard focus onto that control.
**Unblocks:** Plan F closeout (a11y/DPI evidence notes, keyboard E2E freeze).

**Authority:** [`../specs/viewer-v0-design.md`](../specs/viewer-v0-design.md) §6 / §8 / §9.2–9.3,
[`../MASTER_SPEC.md`](../MASTER_SPEC.md) §2.4 / §5 (Phase-0 **context**; index §2.2 —
non-binding for Phase-0 planning, but sketch cites it; conflicts → design wins, noted below),
[`../decisions/ADR-001-godot-ui-technology.md`](../decisions/ADR-001-godot-ui-technology.md),
[`2026-07-21-viewer-v0-implementation-index.md`](2026-07-21-viewer-v0-implementation-index.md)
§3 / §5 / §9 item 4,
[`2026-07-21-viewer-v0-d-decision-inspection.md`](2026-07-21-viewer-v0-d-decision-inspection.md)
§0.9 / §0.11 / §0.13 (filter ownership — **binding**),
mockups README binding corrections.

> **For agentic workers:** do **not** implement from this DRAFT. After the project owner marks
> **APPROVED** and gives a separate go-ahead, execute E1→E6 with TDD (gdUnit4 headless on pinned
> Godot **4.5.2**). No Python exporter changes. No edits under `showdown_bot/`, `data/eval/`,
> `config/eval/`, or `reports/`. No Plan F catalogue fixtures. Do not invent a second candidate
> filter. Do not call `DecisionWorkspace._disable_all_nav()`.
>
> **Sequencing (binding):** Approve-commit **before** any implementation commit. Do **not**
> repeat Plan D’s accidental order (implementation before approve).

---

## 0. Closed decisions (binding)

### 0.1 Verified Plan B–D surface (do not invent)

Verified on `main` @ `0256602` (includes Plan D follow-ups `19e1bc7`). Plan E consumes these
exact names — cite before coding; if a signature drifted, stop and amend this plan.

| Kind | Identifier | Path:lines (as of tip) |
|---|---|---|
| Node | `AppShell` | `godot/src/workspace/app_shell.gd` |
| API | `parse_cli_args`, `get_deep_link_refuse_reason`, `open_bundle_path` | `app_shell.gd:25`, `:57`, `:61` |
| API | `get_replay_workspace`, `get_decision_workspace` | `app_shell.gd:66`, `:70` |
| API | `get_loaded_bundle`, `get_trace_trusted`, `get_status_text`, `get_selected_decision_index` | `app_shell.gd:78`, `:94`, `:128`, `:132` |
| Scene | `$VBox/PathRow`, `$VBox/StatusLabel`, `$VBox/ReplayWorkspace`, `$VBox/DecisionWorkspace` | `app_shell.tscn` |
| Node | `ReplayWorkspace` | `godot/src/replay/replay_workspace.gd` |
| API | `get_timeline_controller() -> TimelineController` | `replay_workspace.gd:45` |
| Node | `TimelineController` | `godot/src/timeline/timeline_controller.gd` |
| Signals | `selection_changed(entry_index: int)`, `playback_changed(playing: bool)` | `timeline_controller.gd:4–5` |
| API | `select`, `step_prev`, `step_next`, `jump_start`, `jump_end` | `timeline_controller.gd:38–63` |
| API | `play`, `pause`, `toggle_play`, `is_playing`, `get_selected_entry_index` | `timeline_controller.gd:66–93` |
| Wiring today | TimelineView Play button → `toggle_play` | `timeline_view.gd` (Plan C) |
| Node | `DecisionWorkspace` | `godot/src/decision/decision_workspace.gd` |
| API | `get_decision_controller()`, `get_candidate_table_view()`, `get_detail_view()` | `decision_workspace.gd:63–72` |
| **Private — taboo** | `_disable_all_nav()` | `decision_workspace.gd:134–139` — **Plan E must not call** |
| Node | `DecisionController` | `godot/src/decision/decision_controller.gd` |
| Signal | `decision_selection_changed(decision_row_index: int)` | `decision_controller.gd:4` |
| API | `select_decision_row`, `jump_next(kind)`, `jump_prev_decision` | `decision_controller.gd:61–80` |
| API | `get_selected_decision`, `has_next(kind)`, `has_prev_decision` | `decision_controller.gd:87–104` |
| Presenter | `find_next_nav_row(..., "close")` → `top1_top2_margin != null` | `decision_presenter.gd:95–121` |
| Node | `CandidateTableView` | `godot/src/decision/candidate_table_view.gd` |
| Filter nodes | `_filter_edit: LineEdit`, `_chosen_only: CheckBox` | `candidate_table_view.gd:6–7` |
| API | `focus_selected()`, `select_candidate_index(i)` | `candidate_table_view.gd:91–108` |
| API | `get_filter_line_edit() -> LineEdit` | `candidate_table_view.gd:111–112` |
| API | `set_filter_text`, `set_chosen_only` | `candidate_table_view.gd:115–123` |
| Deep link | `DecisionDeepLink.REASON_*` (six consts) | `decision_deep_link.gd:4–9` |
| Parse | `parse_arg` uses **`rfind(":")`** (since `19e1bc7`) | `decision_deep_link.gd:27` |
| Resolve | `ambiguous_decision_index` = defense-in-depth only | `decision_deep_link.gd` + loader `bundle_validator.gd:655` |
| Phase consts | `BundleMode.PHASE_TEAM_PREVIEW` / `PHASE_FORCED_REPLACEMENT` / `PHASE_REGULAR_TURN` | `bundle_mode.gd:13–15` |
| Provenance | `BundleManifestDTO`: `schema_*`, `trace_schema_version`, `format_id`, `git_sha`, `config_hash`, `exporter_*`, source hashes | `bundle_manifest_dto.gd` |
| Dirty | `SourceProvenanceDTO.dirty: Variant` | `source_provenance_dto.gd:14–20` |
| Warnings | `ExporterWarningDTO` (`code`, `decision_index`, `message`) | `exporter_warning_dto.gd` |

**Playback seam for E4 (verified, not guessed):** keyboard play/pause calls
`AppShell.get_replay_workspace().get_timeline_controller().toggle_play()` (or `play`/`pause`).
Do **not** reimplement a timer.

### 0.2 Ownership split vs Plan D (binding — unchanged from sketch)

| Concern | Owner |
|---|---|
| Filter text + chosen-only checkbox UI | Plan D (shipped) |
| Filter semantics + gdUnit coverage | Plan D (shipped) |
| `CandidateTableView.get_filter_line_edit()` | Plan D |
| `CandidateTableView.focus_selected()` API | Plan D |
| Keyboard shortcut to **focus** existing filter `LineEdit` | **Plan E** |
| Keyboard shortcut to call `focus_selected()` | **Plan E** |
| Global state banner / density / scale / a11y polish / layout shell | **Plan E** |

**Precondition (satisfied):** Plan D shipped filter. Plan E **must not** invent a second filter
control. “Focus candidate filter” = `get_filter_line_edit().grab_focus()` only.

### 0.3 D→E handoffs (document only; do not rewrite APPROVED Plan D)

| Fact | Implication for E |
|---|---|
| D sketch showed `_set_nav_enabled(enabled)`; code since `19e1bc7` is `_disable_all_nav()` and can **only disable** | E never calls it; never “enable all nav” via workspace private API. Nav enablement stays in `_refresh_from_controller()` / Plan D buttons. |
| `parse_arg` splits on **last** colon (`rfind`) | Deep-link tests / docs in E may use battle_ids containing `:`. |
| `ambiguous_decision_index` is defense-in-depth | E diagnostics / reports must not treat it as a production-covered path. |

### 0.4 State banner vs `StatusLabel` (binding)

Design §6.4: **exactly one prominent state banner**.

| Surface | Role after Plan E |
|---|---|
| **`StateBanner`** (new) | Sole prominent §6.4 state: enum label + icon + optional short detail. Always visible when AppShell is shown. |
| **`StatusLabel`** (existing) | **Operational** line only: load progress, open path echo, deep-link refuse detail (`Deep link refused: <reason>`). Must not duplicate the banner enum as a second “mode chrome.” |

Deep-link refuse reasons continue to use **`DecisionDeepLink.REASON_*` string values** (tests pin
literals; production uses consts). Banner may show `STATE DEGRADED` or keep operational refuse on
`StatusLabel` — binding: refuse **reason token** is never reinvented.

### 0.5 Banner state derivation (binding)

`StateBannerPresenter.compute(bundle, selected_decision, refuse_diagnostic) -> BannerState`.

Priority (first match wins; highest severity first):

| Priority | Banner id (exact label text) | When |
|---|---|---|
| 1 | `BUNDLE INVALID` | `refuse_diagnostic != null` **or** no successful load (shell has refuse) |
| 2 | `TRACE MISSING` | Bundle loaded, `not bundle.trace_trusted` |
| 3 | `STATE DEGRADED` | `downgrade_warnings` non-empty **or** optional required-for-display file absent with persistent warning already on bundle |
| 4 | `WAITING / NO DECISION ROW` | `trace_trusted` and selected decision is `null` |
| 5 | `FALLBACK USED` | Selected decision `fallback_used == true` |
| 6 | `FORCED REPLACEMENT` | Selected `decision_phase == BundleMode.PHASE_FORCED_REPLACEMENT` |
| 7 | `TEAM PREVIEW` | Selected `decision_phase == BundleMode.PHASE_TEAM_PREVIEW` |
| 8 | `DECISION RECORDED` | Selected decision present (incl. `PHASE_REGULAR_TURN` / other recorded phase strings) |

**Warnings:** banner and diagnostics lists use **text + icon**, never color alone (design §6.4).

**Honesty:** absent optional fields → `not recorded` (design §6.5 / §8). Never paint `dirty: null`
as clean — show **`dirty state not recorded`**.

### 0.6 Keyboard actions → existing APIs (binding)

| Action (design §6.3) | Call |
|---|---|
| Previous / next timeline entry | `TimelineController.step_prev` / `step_next` |
| Previous / next decision | `DecisionController.jump_prev_decision` / `jump_next("decision")` |
| Play / pause | `TimelineController.toggle_play` |
| Jump to selected candidate | `CandidateTableView.focus_selected()` |
| Focus candidate filter | `CandidateTableView.get_filter_line_edit().grab_focus()` |
| Open diagnostics | `WorkspaceLayout` / shell focuses diagnostics dock (E2/E5) |
| Reset layout / scale | `WorkspaceLayout.reset_to_safe()` (E3+E5) |
| Honor deep link | Already Plan D on `AppShell`; E adds no second parser |

**Proposed default bindings (closed unless owner overrides at approval):**

| Action | Windows/Linux | macOS label |
|---|---|---|
| Timeline prev / next | `Left` / `Right` | same |
| Decision prev / next | `Ctrl+Up` / `Ctrl+Down` | `Cmd+Up` / `Cmd+Down` |
| Play / pause | `Space` | `Space` |
| Focus filter | `Ctrl+F` | `Cmd+F` |
| Focus selected candidate | `Ctrl+L` | `Cmd+L` |
| Open diagnostics | `Ctrl+Shift+D` | `Cmd+Shift+D` |
| Reset layout/scale | `Ctrl+Shift+0` | `Cmd+Shift+0` |

Shortcuts are **visible** via `ShortcutLabels` (Ctrl vs Cmd). Remapping is **out** unless cheap
(design §6.3) — Plan E does **not** ship a remapper.

**Input ownership:** one `WorkspaceShortcuts` (or AppShell `_unhandled_input`) layer; do not
scatter `_input` across D views. When filter `LineEdit` has focus, character keys type into the
filter; navigation shortcuts that would conflict while typing (`Left`/`Right`/`Space`) are
**suppressed** while the filter (or other text field) has focus — assert in E4 tests.

### 0.7 Layout shell (binding)

| Requirement | Binding |
|---|---|
| Resizable / collapsible docks | `WorkspaceLayout` owns split/tab containers wrapping Replay + Decision + Diagnostics |
| Reset-to-safe | Restores default split ratios, density Comfortable, scale 100%, all primary docks visible |
| Small window | May stack/tab; **timeline controls and path/open (file) row remain reachable** (design §6.1) |
| Min window size | **OPEN — Choice Point A (E3)** |
| Mixed-DPI | Manual Windows checklist → evidence note for Plan F (not an automated green gate) |

### 0.8 Scale and density (binding)

| Item | Binding |
|---|---|
| Scale range | 75%–200% user override (`Window.content_scale_factor` or equivalent project setting) |
| Presets | Snap buttons/menu: **75 / 100 / 150 / 200** (design §9.2) |
| Density | **Compact** / **Comfortable** — same information + same selection; only spacing/font metrics change |
| Truncation | Visual truncate + tooltip/full detail; **copy paths never truncate IDs** |
| Fonts | Offline only — **OPEN — Choice Point B (E6)** |

### 0.9 Provenance + raw evidence (binding)

Provenance panel shows when present on sealed DTOs:

- `schema_major.schema_minor`, `trace_schema_version`
- `format_id`, `battle_id`
- `git_sha`, `config_hash`
- `source_hashes_battle_log`, `source_hashes_decision_trace`
- `exporter_name`, `exporter_version`
- `source_provenance.dirty` tri-state: `true` / `false` / `null`→**`dirty state not recorded`**

Diagnostics panel: exporter warnings + downgrade warnings (text + icon).

Raw evidence tab: **bundle-normalized** JSON/text only (no filesystem browser). Bounded: max
chars / virtualized or truncated with explicit `… truncated` marker (design §6.6 / §9.3).

### 0.10 Screen-reader and Mixed-DPI (honesty — not automated gates)

| Check | How evidence is recorded | What “pass” means |
|---|---|---|
| Screen-reader | Manual note under `showdownbot_studio/docs/plans/evidence/` (or Plan F appendix) after trying Godot 4.5.2 + one OS screen reader | **Best effort.** Report what worked / failed. **Must not** claim SR completeness. MASTER_SPEC §2.4 + design §9.2. |
| Mixed-DPI | Manual Windows checklist: move window across monitors with different scaling; record scale readability, control reachability, **selected timeline entry preserved** | Checklist filed for Plan F. Failure = plan amendment or recorded limitation — **not** a silent gdUnit green. |

### 0.11 Scope fence

**In:** State banner, diagnostics/provenance/raw tab, workspace layout (splits/collapse/reset),
UI scale + density, offline fonts decision implementation, keyboard shortcut layer, shortcut
labels, gdUnit tests for programmable behavior, evidence templates for manual checks.

**Out:** Filter semantics/UI (Plan D); Plan F fixtures; exporter / `showdown_bot/`; remappable
keys; score graph; artwork; theme polish beyond workable defaults; inventing APIs; calling
`_disable_all_nav`.

### 0.12 Implementation gate

This Rev. 1 is **DRAFT**. Code starts only after: (1) owner closes Choice Points A–C,
(2) status → **APPROVED**, (3) separate implementation go-ahead. Approve-commit precedes code.

### 0.13 Open choice points (owner decides — implementer must not close)

#### Choice Point A — Minimum supported window size (E3)

**Spec:** design §6.1 / §9.2 + MASTER_SPEC §5 — primary controls reachable at min window; numbers
TBD (index §9 item 4).

| Option | Numbers | Consequence |
|---|---|---|
| A1 | **1280×720** min | Comfortable for stacked Replay+Decision; matches common laptop logical size |
| A2 | **1024×640** min | Harder layout; forces earlier stacking; better small-laptop coverage |
| A3 | **1280×720** min + **1024×640** “degraded stack” documented | Two tiers; more test surface |

**Recommendation:** **A1 (1280×720)** as the **acceptance** minimum for “primary controls
reachable” + scale matrix; document that narrower widths may stack (still no unreachable
timeline/path). Rationale: current AppShell is a vertical stack of two `size_flags_vertical=3`
workspaces — 1024×640 without a finished layout shell is a layout rewrite, not a pin.

**Status:** OPEN.

#### Choice Point B — Offline fonts (E6)

| Option | Approach | Consequence |
|---|---|---|
| B1 | Bundle license-reviewed font (e.g. IBM Plex family matching mockup dossier) under `godot/assets/fonts/` + OFL text | Repo size ↑; consistent glyphs; license audit once |
| B2 | Approved **system stack** only (no bundled files): e.g. `Segoe UI` / `SF Pro` / `Noto Sans` fallbacks via Theme | Zero asset weight; platform glyph drift; still offline |

Mockup HTML may keep Google Fonts; **app must not** load network fonts (design §8 / index §5.8).

**Recommendation:** **B2 for v0** (system stack), with Theme fallbacks documented. Rationale:
Phase 0 offline + YAGNI; mockup already uses IBM Plex via network for design only. Bundle fonts
can be a post-v0 polish if glyph consistency becomes a real defect.

**Status:** OPEN.

#### Choice Point C — “Next close” semantics (E4 binds a shortcut)

**Background:** Plan D §0.9 and `DecisionPresenter.find_next_nav_row` (`decision_presenter.gd:110–111`)
define `"close"` as `top1_top2_margin != null` with **no numeric threshold**. Design §6.5:
“v0 defines no universal close-decision threshold.”

Empirics (bundles on tip):

| Fixture | Decisions | With non-null margin | Without |
|---|---|---|---|
| fixture-01 | 3 | 1 | 2 |
| fixture-05 | 11 | 10 | 1 |

So on fixture-05, Next-close ≈ Next-decision; on fixture-01 it still filters.

| Option | Change | Consequence |
|---|---|---|
| C1 | **Keep** Plan D / design (null check only) | Spec-faithful; E4 binds `jump_next("close")` as-is; weak UX on dense-margin fixtures |
| C2 | Introduce numeric threshold | Requires **design §6.5 amendment** + Plan D presenter/tests change — **not** a silent E cleanup |

**Recommendation:** **C1 — leave as-is.** E documents the empirics; does not invent a threshold.
If the owner wants C2, that is a **spec amendment** before E implementation, not an E task.

**Status:** OPEN.

---

## 1. Goal / non-goals

### Goal

Ship the persistent state banner, diagnostics/provenance/raw panels, Compact/Comfortable density,
75%–200% scale, keyboard-first workflows on **existing** B–D APIs, and layout resilience gates —
without network font loads.

### Non-goals

- Screen-reader completeness as a hard release gate (best effort + honest report only)
- Shortcut remapping
- Localization
- Dark/light theme polish beyond workable defaults
- Candidate filter semantics / UI / tests (Plan D)
- Changing Next-close threshold without Choice Point C → C2 + spec amend
- Strength / bot-correctness claims

---

## 2. Architecture

```text
AppShell
├── PathRow (open)
├── StateBanner          ← E1 (prominent §6.4)
├── StatusLabel          ← operational (load / deep-link detail)
├── WorkspaceLayout      ← E5 splits / collapse / reset
│   ├── ReplayWorkspace  ← Plan C (timeline play via TimelineController)
│   ├── DecisionWorkspace← Plan D (filter LineEdit exists)
│   └── DiagnosticsDock  ← E2 provenance + warnings + raw
├── WorkspaceShortcuts   ← E4 (_unhandled_input → existing APIs)
└── BundleLoader         ← Plan B
```

Presenters are pure/static where practical (`StateBannerPresenter`, `ProvenancePresenter`) so
gdUnit can assert derivation without full scene trees. Views bind sealed DTOs read-only.

---

## 3. File map

| Path | Responsibility |
|---|---|
| `godot/src/diagnostics/state_banner_presenter.gd` | Banner enum derivation (§0.5) |
| `godot/src/diagnostics/state_banner.gd` + `.tscn` | Exactly one prominent banner view |
| `godot/src/diagnostics/provenance_presenter.gd` | Field formatting; dirty tri-state |
| `godot/src/diagnostics/diagnostics_presenter.gd` | Warning list model |
| `godot/src/diagnostics/diagnostics_dock.gd` + `.tscn` | Provenance + warnings + raw tab |
| `godot/src/workspace/workspace_layout.gd` + `.tscn` | Docks, density, scale, reset |
| `godot/src/workspace/workspace_shortcuts.gd` | Keyboard → existing APIs |
| `godot/src/workspace/shortcut_labels.gd` | Ctrl vs Cmd strings |
| `godot/src/workspace/app_shell.gd` / `.tscn` | Mount banner + layout; keep D deep link |
| `godot/assets/fonts/` **or** Theme system stack | Per Choice Point B |
| `godot/tests/diagnostics/test_state_banner_presenter.gd` | E1 |
| `godot/tests/diagnostics/test_provenance_presenter.gd` | E2 |
| `godot/tests/diagnostics/test_diagnostics_dock.gd` | E2 |
| `godot/tests/workspace/test_workspace_layout.gd` | E3/E5 |
| `godot/tests/workspace/test_workspace_shortcuts.gd` | E4 |
| `godot/tests/workspace/test_app_shell_plan_e.gd` | Shell integration |
| `docs/plans/evidence/viewer-v0-e-manual-checks.md` | SR + DPI templates (filled in E/F) |

### 3.1 Binding scene notes

- `StateBanner`: `HBox` with `TextureRect`/`Label` icon + `Label` state + optional detail `Label`.
- `DiagnosticsDock`: `TabContainer` → Provenance | Warnings | Raw.
- `WorkspaceLayout`: prefer `HSplitContainer` / `VSplitContainer` or `TabContainer` at narrow
  width; must keep PathRow + timeline transport reachable after collapse.

---

## 4. Presenter / view contracts

### 4.1 `StateBannerPresenter` (binding)

```gdscript
class_name StateBannerPresenter
extends RefCounted

const BUNDLE_INVALID := "BUNDLE INVALID"
const TRACE_MISSING := "TRACE MISSING"
const STATE_DEGRADED := "STATE DEGRADED"
const WAITING_NO_DECISION := "WAITING / NO DECISION ROW"
const FALLBACK_USED := "FALLBACK USED"
const FORCED_REPLACEMENT := "FORCED REPLACEMENT"
const TEAM_PREVIEW := "TEAM PREVIEW"
const DECISION_RECORDED := "DECISION RECORDED"

## Returns one of the consts above.
static func compute(
		bundle: BundleDTO,
		selected: DecisionRowDTO,
		refuse: RefuseDiagnostic
) -> String:
	# Priority table §0.5 — implement exactly; no extra states in v0.
	pass


static func dirty_label(dirty: Variant) -> String:
	if dirty == null:
		return "dirty state not recorded"
	return "dirty: true" if dirty else "dirty: false"
```

### 4.2 `ProvenancePresenter` (binding)

Formats manifest + `source_provenance` into ordered `Array` of `{label, value}` dictionaries.
Never invent hashes. Null optional → `not recorded` (reuse `DecisionPresenter.optional_text`
where applicable).

### 4.3 `WorkspaceLayout` (binding API)

```gdscript
## Density: "compact" | "comfortable"
func set_density(mode: String) -> void
func get_density() -> String

## Scale factor in [0.75, 2.0]; presets snap to 0.75/1.0/1.5/2.0
func set_ui_scale(factor: float) -> void
func get_ui_scale() -> float

func reset_to_safe() -> void
func focus_diagnostics() -> void
```

Min window: `DisplayServer.window_set_min_size(Vector2i(W, H))` with **W×H from Choice Point A**.

### 4.4 `WorkspaceShortcuts` (binding)

Constructed with references obtained **only** via public getters:

```text
shell.get_replay_workspace().get_timeline_controller()
shell.get_decision_workspace().get_decision_controller()
shell.get_decision_workspace().get_candidate_table_view()
shell.get_layout()  # WorkspaceLayout
```

### 4.5 `ShortcutLabels` (binding)

```gdscript
static func mod_key() -> String:
	# "Cmd" on macOS, "Ctrl" elsewhere (OS.get_name()).
```

---

## 5. Named tests (binding)

Shared helpers: same pattern as Plan D §14 (`_fixture_path`, `_fixture_bundle`, `_spawn_shell_ready`,
`_await_shell_settled`). Do not invent alternate loaders.

### 5.1 `tests/diagnostics/test_state_banner_presenter.gd`

| Test | Assert |
|---|---|
| `test_refuse_is_bundle_invalid` | refuse non-null → `BUNDLE INVALID` |
| `test_fixture04_trace_missing` | fixture-04 loaded, no refuse → `TRACE MISSING` |
| `test_waiting_when_no_selection` | trusted bundle, `selected=null` → `WAITING / NO DECISION ROW` |
| `test_fallback_used` | fixture-03 decision with `fallback_used` → `FALLBACK USED` |
| `test_phase_team_preview` | constructed phase → `TEAM PREVIEW` |
| `test_phase_forced_replacement` | constructed → `FORCED REPLACEMENT` |
| `test_decision_recorded_regular` | fixture-01 selected regular → `DECISION RECORDED` |
| `test_degraded_downgrade_warnings` | non-empty `downgrade_warnings` beats waiting |
| `test_dirty_null_label` | `dirty_label(null) == "dirty state not recorded"` |

### 5.2 `tests/diagnostics/test_provenance_presenter.gd`

| Test | Assert |
|---|---|
| `test_fixture01_shows_battle_id_and_hashes` | labels include `battle_id`, `config_hash` or `not recorded` |
| `test_dirty_tri_state_null` | null → `dirty state not recorded` (never “clean”) |
| `test_exporter_version_shown` | contains recorded `exporter_version` |

### 5.3 `tests/diagnostics/test_diagnostics_dock.gd`

| Test | Assert |
|---|---|
| `test_raw_tab_bounded` | huge string input truncated with marker; no one Control per line beyond TextEdit |
| `test_warnings_show_text_and_icon` | warning row has non-empty text; icon node visible |
| `test_no_filesystem_paths_in_raw` | raw view does not include absolute local path of fixture dir |

### 5.4 `tests/workspace/test_workspace_layout.gd`

| Test | Assert |
|---|---|
| `test_scale_clamped` | set 0.5 → becomes 0.75; set 3.0 → 2.0 |
| `test_scale_presets` | 0.75/1.0/1.5/2.0 stick |
| `test_density_preserves_selection` | change compact↔comfortable; decision_index + timeline entry unchanged |
| `test_reset_to_safe_restores_defaults` | after custom scale/density/collapse → reset → defaults |
| `test_min_window_set` | after ready, min size equals Choice Point A numbers |

### 5.5 `tests/workspace/test_workspace_shortcuts.gd`

| Test | Assert |
|---|---|
| `test_timeline_step_next_via_shortcut` | synthetic key → timeline index +1 |
| `test_decision_jump_next_via_shortcut` | → `jump_next("decision")` effect |
| `test_toggle_play_via_shortcut` | `is_playing` flips via `toggle_play` |
| `test_focus_filter_grabs_plan_d_line_edit` | focus owner == `get_filter_line_edit()`; **same instance** |
| `test_focus_selected_candidate` | after select non-chosen, shortcut → list selection visible |
| `test_focus_diagnostics` | diagnostics dock receives focus / visible |
| `test_reset_layout_shortcut` | triggers `reset_to_safe` observable defaults |
| `test_filter_focus_suppresses_space_play` | with filter focused, Space does **not** toggle play |
| `test_no_second_filter_control` | shell has exactly one `FilterLineEdit` under decision workspace |

### 5.6 `tests/workspace/test_app_shell_plan_e.gd`

| Test | Assert |
|---|---|
| `test_banner_visible_fixture01` | after open, banner text in allowed set; control visible |
| `test_banner_fixture04_trace_missing` | `TRACE MISSING` |
| `test_banner_fixture03_or_fallback_path` | fallback or decision-recorded per selection |
| `test_deep_link_refuse_uses_plan_d_reason` | mismatch → status/detail contains `battle_id_mismatch` **literal** |
| `test_keyboard_only_smoke_fixture01` | sequence: open → next decision → focus filter → type → focus selected (no mouse API) |

### 5.7 Manual evidence (not gdUnit pass/fail)

| Artifact | Content |
|---|---|
| `docs/plans/evidence/viewer-v0-e-manual-checks.md` | Blank checklist: SR steps + DPI steps; filled during E6/E5 acceptance; Plan F archives |

---

## 6. Tasks (TDD)

Engine pin + runner (every GREEN):

```powershell
cd showdownbot_studio/godot
.\tools\verify_engine_pin.ps1
.\tools\run_gdunit_headless.ps1 -a "res://tests/<suite>.gd"
```

Expected final suite: prior tip case count **+** new Plan E cases (exact delta recorded at
implementation start by counting §5 names). No silent case deletion.

### Task E1 — State banner

**Files:** create presenter + view; modify `app_shell.tscn` to mount banner above operational status.

- [ ] **RED:** add `test_state_banner_presenter.gd` cases from §5.1 (fail: missing class).
- [ ] **GREEN:** implement `StateBannerPresenter.compute` per §0.5 priority; mount `StateBanner`.
- [ ] **Assert:** fixture-01/03/04 banner ids via shell or presenter tests.
- [ ] **Commit:** `feat(studio): add Plan E state banner presenter and view`

### Task E2 — Provenance + diagnostics dock

- [ ] **RED:** §5.2–5.3 tests.
- [ ] **GREEN:** `ProvenancePresenter`, `DiagnosticsPresenter`, `DiagnosticsDock` with Raw bounded.
- [ ] **Commit:** `feat(studio): add diagnostics and provenance dock`

### Task E3 — Scale + density (+ min window after Choice Point A)

- [ ] **Owner must have closed Choice Point A** (else stop).
- [ ] **RED:** §5.4 scale/density/min-window tests.
- [ ] **GREEN:** `WorkspaceLayout.set_ui_scale` / `set_density` / min size.
- [ ] **Commit:** `feat(studio): add UI scale and density controls`

### Task E4 — Keyboard shortcuts

- [ ] **Owner should have closed Choice Point C** (default C1 = no code change to presenter).
- [ ] **RED:** §5.5 tests — especially filter focus identity + Space suppression.
- [ ] **GREEN:** `WorkspaceShortcuts` + `ShortcutLabels`; bind only §0.6 APIs.
- [ ] **Commit:** `feat(studio): wire keyboard shortcuts to Plan C/D APIs`

### Task E5 — Layout shell + reset

- [ ] **RED:** reset + reachability-oriented layout tests; update shell scene tree.
- [ ] **GREEN:** splits/collapse/reset; small-window stack behavior.
- [ ] **Manual:** start Mixed-DPI checklist draft (unfilled OK until E done).
- [ ] **Commit:** `feat(studio): add workspace layout shell and reset`

### Task E6 — Offline fonts + manual evidence templates

- [ ] **Owner must have closed Choice Point B**.
- [ ] **GREEN:** Theme/system stack **or** bundled fonts + license file; grep CI/local script:
  no `fonts.googleapis` / http font URLs under `godot/src` and `godot/assets`.
- [ ] Add `docs/plans/evidence/viewer-v0-e-manual-checks.md` template (SR + DPI).
- [ ] **Commit:** `feat(studio): offline fonts and Plan E manual evidence template`

### Task E7 — Full regression + pin

- [ ] `verify_engine_pin.ps1` OK
- [ ] `run_gdunit_headless.ps1 -a "res://tests/"` → 0 failures (privilege skips OK)
- [ ] `git diff --check` clean
- [ ] **Commit:** `test(studio): Plan E regression green`

---

## 7. Acceptance (Plan E done)

| Criterion | Evidence |
|---|---|
| Keyboard-only inspection of fixture-01 | §5.6 smoke + §5.5 shortcuts green |
| Focus filter focuses Plan D `LineEdit` | Same instance assert; no second filter |
| Scale 75/100/150/200 | §5.4 + recorded note that primary controls reachable at Choice Point A size |
| Banner correct for fixtures 1, 3, 4, 5, 6 | Presenter/shell tests; fixture-06 refuse → `BUNDLE INVALID` / cleared UI |
| Dirty null honesty | §5.1 / §5.2 |
| Deep link reasons unchanged | Literal `battle_id_mismatch` etc.; `DecisionDeepLink.REASON_*` in prod |
| Offline fonts | Choice Point B implemented; no network font loads in app |
| Mixed-DPI | Checklist **filed** (not “tests passed”) |
| Screen-reader | Honest smoke notes **filed**; no completeness claim |
| Next-close | Per Choice Point C (default: unchanged Plan D semantics) |

---

## 8. Self-review checklist (author)

- [x] Sketch ownership split preserved verbatim in spirit (§0.2)
- [x] Filter precondition recorded as satisfied; no second filter
- [x] Every E4 action maps to a cited existing API
- [x] `_disable_all_nav` marked taboo
- [x] Deep-link vocabulary not duplicated
- [x] D→E handoffs (`_disable_all_nav`, `rfind`, defense-in-depth) documented
- [x] Choice Points A–C open with options + recommendation
- [x] Spec §6.5 “no universal close threshold” aligned with recommendation C1
- [x] SR + DPI are evidence artifacts, not fake gates
- [x] Approve-before-implement sequencing explicit
- [ ] Owner closes A–C and marks APPROVED (not author)

---

## 9. Spec / sketch conflict log

| Topic | Sketch / master | Design (wins) | Plan E handling |
|---|---|---|---|
| Close threshold | Empirics tempt a threshold | §6.5: no universal threshold | Choice Point C; recommend keep |
| Master §2.4 SR | Best effort | §9.2 best effort | Evidence note only |
| Master binding | Sketch cites MASTER_SPEC | Index §2.2: non-binding context | Cited as context; design is authority |

---

## 10. Handoff

1. Owner reviews this DRAFT against code + design.
2. Owner closes Choice Points A–C (record decisions in a Rev. 2 §0.13 table).
3. Status → **APPROVED** in a **docs-only** commit.
4. Separate go-ahead → isolated branch → E1…E7.
5. Plan F consumes manual evidence files.

**Do not** start E code from this DRAFT alone.

---

## 11. Suggested commit cadence (after APPROVED)

| Commit | Content |
|---|---|
| docs | APPROVED mark + closed choice points |
| E1 | Banner |
| E2 | Diagnostics dock |
| E3 | Scale/density/min window |
| E4 | Shortcuts |
| E5 | Layout shell |
| E6 | Fonts + evidence template |
| E7 | Regression |

---

## 12. Rev. 1 changelog (sketch → executable)

- Expanded to Plan D structural density: §0 closed decisions, open choice points, file map,
  contracts, named tests, TDD tasks, acceptance, handoff.
- Locked E4 to verified TimelineController playback API (`play`/`pause`/`toggle_play`).
- Recorded D→E handoffs from `19e1bc7`.
- Marked filter precondition satisfied (Plan D shipped).
- Separated prominent `StateBanner` from operational `StatusLabel`.
- Added honesty protocol for screen-reader and Mixed-DPI evidence.
