# Viewer v0 — Plan E: Diagnostics, Accessibility, and Layout

**Status:** APPROVED — 2026-07-21 (Rev. 3). Owner review PASS across Rev. 1–3.
Amended Rev. 4 (additive Plan-D test coverage, owner-authorised, pre-implementation).
**Implementation not authorized** until a separate go-ahead (§10 Schritt 4; own branch).
**Date:** 2026-07-21 · **Rev.:** 4 (Plan-D coverage gaps T1–T3 + settled-load rule)
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
| 8 | `DECISION RECORDED` | Selected decision present and `decision_phase == BundleMode.PHASE_REGULAR_TURN` |

**Priority 8 / phase allowlist (defense-in-depth):** The loader allowlists exactly three
phases — `PHASE_TEAM_PREVIEW`, `PHASE_FORCED_REPLACEMENT`, `PHASE_REGULAR_TURN`
(`bundle_validator.gd:73–75`) — and refuses any other string with `unknown decision_phase`
(`bundle_validator.gd:683`). After priorities 6–7, the only reachable remaining phase is
`PHASE_REGULAR_TURN`. There are **no** other live “recorded phase strings.” A hypothetical
unknown phase must never be treated as a production-covered banner path (same class of note as
`ambiguous_decision_index` in §0.3).

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
| Min window size | **1280×720** (`DisplayServer.window_set_min_size(Vector2i(1280, 720))`) — Choice Point A **CLOSED** |
| Mixed-DPI | Manual Windows checklist → evidence note for Plan F (not an automated green gate) |

### 0.8 Scale and density (binding)

| Item | Binding |
|---|---|
| Scale range | 75%–200% user override (`Window.content_scale_factor` or equivalent project setting) |
| Presets | Snap buttons/menu: **75 / 100 / 150 / 200** (design §9.2) |
| Density | **Compact** / **Comfortable** — same information + same selection; only spacing/font metrics change |
| Truncation | Visual truncate + tooltip/full detail; **copy paths never truncate IDs** |
| Fonts | **B2 CLOSED:** offline **system stack** only (no bundled font files; no network fonts). **Binding Auflage:** provenance value labels, hash fields, and the raw-evidence surface MUST use an explicit **monospace** fallback (see §0.9 / §4.2 / §4.6). |

### 0.9 Provenance + raw evidence (binding)

Provenance panel shows when present on sealed DTOs:

- `schema_major.schema_minor`, `trace_schema_version`
- `format_id`, `battle_id`
- `git_sha`, `config_hash`
- `source_hashes_battle_log`, `source_hashes_decision_trace`
- `exporter_name`, `exporter_version`
- `source_provenance.dirty` tri-state: `true` / `false` / `null`→**`dirty state not recorded`**

**Monospace (binding — Choice Point B Auflage):** Every control that displays `git_sha`,
`config_hash`, source hashes, or raw evidence text MUST render with a monospace system font.
Binding mechanism (Godot 4.5.2 Control / SystemFont APIs — do not invent):

1. Build `var mono := SystemFont.new()` and set
   `mono.font_names = PackedStringArray(["monospace"])` — Godot’s portable system-font **alias**
   for monospace (resolves to platform monospace; see Godot “Using fonts” / `SystemFont.font_names`).
2. Apply with `Control.add_theme_font_override(&"font", mono)` on each hash/raw surface control
   ([`Control.add_theme_font_override`](https://docs.godotengine.org/en/stable/classes/class_control.html#class-control-method-add-theme-font-override)).
3. Tests assert `control.has_theme_font_override(&"font")` and that
   `control.get_theme_font(&"font")` is a `SystemFont` whose `font_names` contains `"monospace"`
   ([`has_theme_font_override`](https://docs.godotengine.org/en/stable/classes/class_control.html#class-control-method-has-theme-font-override) /
   [`get_theme_font`](https://docs.godotengine.org/en/stable/classes/class_control.html#class-control-method-get-theme-font)).

UI chrome (banner title, buttons) may use the default sans system stack; hash/raw surfaces may not.

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

This Rev. 3 is **DRAFT**. Choice Points A–C are **CLOSED** (§0.13). Code still starts only after:
(1) status → **APPROVED**, (2) separate implementation go-ahead. Approve-commit precedes code.

### 0.13 Choice points — CLOSED (owner, Rev. 2)

Options below remain as protocol. Status of each point: **CLOSED (owner, Rev. 2)**.

#### Choice Point A — Minimum supported window size (E3)

**Spec:** design §6.1 / §9.2 + MASTER_SPEC §5 — primary controls reachable at min window; numbers
were TBD (index §9 item 4).

| Option | Numbers | Consequence |
|---|---|---|
| A1 | **1280×720** min | Comfortable for stacked Replay+Decision; matches common laptop logical size |
| A2 | **1024×640** min | Harder layout; forces earlier stacking; better small-laptop coverage |
| A3 | **1280×720** min + **1024×640** “degraded stack” documented | Two tiers; more test surface |

| | |
|---|---|
| **Decision** | **A1 — 1280×720** as the acceptance minimum |
| **Rationale** | Derived from the real AppShell (vertical stack of two `size_flags_vertical=3` workspaces). 1024×640 without a finished layout shell would be a rewrite, not a pin. Narrower widths may stack; timeline and Path/Open remain reachable. |
| **Status** | **CLOSED (owner, Rev. 2)** |

#### Choice Point B — Offline fonts (E6)

| Option | Approach | Consequence |
|---|---|---|
| B1 | Bundle license-reviewed font (e.g. IBM Plex family matching mockup dossier) under `godot/assets/fonts/` + OFL text | Repo size ↑; consistent glyphs; license audit once |
| B2 | Approved **system stack** only (no bundled files): e.g. `Segoe UI` / `SF Pro` / `Noto Sans` fallbacks via Theme | Zero asset weight; platform glyph drift; still offline |

Mockup HTML may keep Google Fonts; **app must not** load network fonts (design §8 / index §5.8).

| | |
|---|---|
| **Decision** | **B2 — system stack**, with binding Auflage |
| **Rationale** | Phase-0 offline + YAGNI. |
| **Auflage (binding)** | Provenance, hash, and raw-evidence surfaces get an explicit **monospace** Theme/Control font fallback (`SystemFont` + alias `"monospace"` via `add_theme_font_override` — §0.9 / §4.6). A viewer whose job is reading `git_sha` / `config_hash` / source hashes must not render hex digits with platform-dependent proportional glyph drift on those surfaces. |
| **Status** | **CLOSED (owner, Rev. 2)** |

#### Choice Point C — “Next close” semantics (E4 binds a shortcut)

**Background:** Plan D §0.9 and `DecisionPresenter.find_next_nav_row` (`decision_presenter.gd:110–111`)
define `"close"` as `top1_top2_margin != null` with **no numeric threshold**. Design §6.5:
“v0 defines no universal close-decision threshold.”

Empirics (bundles on tip; unchanged):

| Fixture | Decisions | With non-null margin | Without |
|---|---|---|---|
| fixture-01 | 3 | 1 | 2 |
| fixture-05 | 11 | 10 | 1 |

So on fixture-05, Next-close ≈ Next-decision; on fixture-01 it still filters.

| Option | Change | Consequence |
|---|---|---|
| C1 | **Keep** Plan D / design (null check only) | Spec-faithful; E4 binds `jump_next("close")` as-is; weak UX on dense-margin fixtures |
| C2 | Introduce numeric threshold | Requires **design §6.5 amendment** + Plan D presenter/tests change — **not** a silent E cleanup |

| | |
|---|---|
| **Decision** | **C1 — leave unchanged** |
| **Rationale** | design §6.5 remains authoritative. A threshold would be a spec change plus Plan D presenter/tests — not Plan E cleanup. Empirics stay documented above. |
| **Status** | **CLOSED (owner, Rev. 2)** |

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
- Changing Next-close threshold (Choice Point C **CLOSED** as C1; C2 would need a design §6.5 amend)
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
| `godot/src/diagnostics/studio_mono_font.gd` | §4.6 `StudioMonoFont` helper |
| `godot/src/workspace/workspace_layout.gd` + `.tscn` | Docks, density, scale, reset |
| `godot/src/workspace/workspace_shortcuts.gd` | Keyboard → existing APIs |
| `godot/src/workspace/shortcut_labels.gd` | Ctrl vs Cmd strings |
| `godot/src/workspace/app_shell.gd` / `.tscn` | Mount banner + layout; keep D deep link |
| `godot/assets/fonts/` | **Not used** (B2 — no bundled fonts) |
| Theme / `SystemFont` monospace override | Hash + raw surfaces (§0.9 / §4.6) |
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

**View binding:** each **value** control for hash-like fields (`git_sha`, `config_hash`,
`source_hashes_*`, and any other hex/hash string shown in the provenance tab) MUST receive the
monospace override from §4.6 before display.

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

Min window: `DisplayServer.window_set_min_size(Vector2i(1280, 720))` (Choice Point A CLOSED).

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

### 4.6 Monospace helper (binding — Choice Point B Auflage)

```gdscript
class_name StudioMonoFont
extends RefCounted

## Shared SystemFont using Godot's portable "monospace" alias.
static func system_mono() -> SystemFont:
	var font := SystemFont.new()
	font.font_names = PackedStringArray(["monospace"])
	return font


static func apply_to(control: Control) -> void:
	# Control.add_theme_font_override(name: StringName, font: Font)
	control.add_theme_font_override(&"font", system_mono())
```

**Surfaces that MUST call `apply_to`:** provenance hash/value labels, raw-evidence `TextEdit`
(or equivalent). Asserted by §5.3 `test_hash_surfaces_use_monospace`.

---

## 5. Named tests (binding)

Shared helpers: same pattern as Plan D §14 (`_fixture_path`, `_fixture_bundle`, `_spawn_shell_ready`,
`_await_shell_settled`, `_make_candidate`). Do not invent alternate loaders.

**Settled ≠ loaded (binding):** `_await_shell_settled` only asserts `is_loading() == false`
(Plan D §14 helper). If a load never starts, the wait loop runs zero iterations and the assert
still passes — so “settled” is **not** proof of a successful open. Every Plan E test that
requires a loaded bundle MUST assert an additional positive load signal after settle:
`get_loaded_bundle() != null`, **or** (refuse fixtures) the pinned refuse reason (same rule as
§5.6 fixture-06 / `hash_mismatch`). Do not conclude “loaded” from settle alone.

### 5.1 `tests/diagnostics/test_state_banner_presenter.gd`

| Test | Assert |
|---|---|
| `test_refuse_is_bundle_invalid` | refuse non-null → `BUNDLE INVALID` |
| `test_fixture04_trace_missing` | fixture-04 loaded, no refuse → `TRACE MISSING` |
| `test_waiting_when_no_selection` | trusted bundle, `selected=null` → `WAITING / NO DECISION ROW` |
| `test_fallback_used` | fixture-03 decision with `fallback_used` → `FALLBACK USED` |
| `test_phase_team_preview` | fixture-01: select row for `decision_index == 0` (`team_preview`) → `TEAM PREVIEW`. **Real sealed row** (Loader → Validator allowlist `bundle_validator.gd:73–75` → `bundle_loader.gd:308` copies `decision_phase`) — not a hand-built DTO that only exercises the presenter `match`. |
| `test_phase_forced_replacement` | fixture-01: select row for `decision_index == 1` (`forced_replacement`) → `FORCED REPLACEMENT`. Same full-chain rationale as above. |
| `test_decision_recorded_regular` | fixture-01 selected `PHASE_REGULAR_TURN` → `DECISION RECORDED` |
| `test_degraded_downgrade_warnings` | non-empty `downgrade_warnings` beats waiting (3v4 sample) |
| `test_dirty_null_label` | `dirty_label(null) == "dirty state not recorded"` |
| **Precedence (both conditions set — F1)** | |
| `test_precedence_1v2_refuse_beats_trace_missing` | **bundle and `refuse_diagnostic` both non-null** → `BUNDLE INVALID` (catches impls that key only on `bundle == null`) |
| `test_precedence_2v3_trace_missing_beats_degraded` | `not trace_trusted` **and** non-empty `downgrade_warnings` → `TRACE MISSING` |
| `test_precedence_3v4_degraded_beats_waiting` | `trace_trusted`, non-empty `downgrade_warnings`, `selected=null` → `STATE DEGRADED` (3 and 4 both match; 3 wins) |
| `test_precedence_4v5_waiting_vs_fallback_exclusive` | **Unreachable simultaneous:** 4 needs `selected==null`, 5 needs a selected row with `fallback_used`. Assert `selected==null`→`WAITING / NO DECISION ROW` and selected+`fallback_used`→`FALLBACK USED` in this named case; document exclusivity. |
| `test_precedence_5v6_fallback_beats_forced` | `fallback_used == true` **and** `decision_phase == PHASE_FORCED_REPLACEMENT` → `FALLBACK USED` |
| `test_precedence_6v7_phases_mutually_exclusive` | `FORCED_REPLACEMENT` and `TEAM_PREVIEW` **cannot co-occur** on one row (validator allowlist `bundle_validator.gd:73–75`, refuse `:683`). Assert FORCED→`FORCED REPLACEMENT` and TEAM→`TEAM PREVIEW` separately in this named case; document unreachable simultaneous. |
| `test_precedence_7v8_team_preview_beats_decision_recorded` | selected present **and** `decision_phase == PHASE_TEAM_PREVIEW` → `TEAM PREVIEW` (not `DECISION RECORDED`) |

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
| `test_hash_surfaces_use_monospace` | After dock bind of fixture-01: each provenance hash **value** control and the raw `TextEdit` satisfy `has_theme_font_override(&"font") == true`, `get_theme_font(&"font") is SystemFont`, and `"monospace" in (font as SystemFont).font_names` (§4.6) |

### 5.4 `tests/workspace/test_workspace_layout.gd`

| Test | Assert |
|---|---|
| `test_scale_clamped` | set 0.5 → becomes 0.75; set 3.0 → 2.0 |
| `test_scale_presets` | 0.75/1.0/1.5/2.0 stick |
| `test_density_preserves_selection` | change compact↔comfortable; decision_index + timeline entry unchanged |
| `test_reset_to_safe_restores_defaults` | after custom scale/density/collapse → reset → defaults |
| `test_min_window_set` | after ready, min size equals **`Vector2i(1280, 720)`** |

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
| `test_banner_visible_fixture01` | after open + settle, banner **`TEAM PREVIEW`** (Plan D selects first `decision_index` = 0; fixture-01 d0 phase is `team_preview`); control visible |
| `test_banner_fixture04_trace_missing` | `TRACE MISSING` |
| `test_banner_fixture03_fallback_on_selected_row` | Open fixture-03; `select_decision_row` for the row with `fallback_used == true` (fixture-03 d2 / Plan D nav target); banner **`FALLBACK USED`** (deterministic — no “or”) |
| `test_banner_fixture05_forced_on_d4` | Open `bundles/fixture-05`; select the row with `decision_index == 4` (`forced_replacement`, `fallback_used == false` — measured in `decisions.jsonl`); banner **`FORCED REPLACEMENT`**. Pins priority 6 on real data (no soft “one of §0.5 labels”). |
| `test_banner_fixture06_refuse_hash_mismatch` | Path **`sources/fixture-06/bundle`** (there is **no** `bundles/fixture-06` — same path as `test_app_shell_smoke.gd:82` / `test_bundle_validator.gd:96`). Assert `get_refuse_reason() == "hash_mismatch"` **and** banner `BUNDLE INVALID`. Pinning the reason prevents a green test on a wrong/missing path that merely fails to open. |
| `test_deep_link_refuse_uses_plan_d_reason` | mismatch → status/detail contains `battle_id_mismatch` **literal** |
| `test_keyboard_only_smoke_fixture01` | sequence: open → next decision → focus filter → type → focus selected (no mouse API) |

### 5.7 Manual evidence (not gdUnit pass/fail)

| Artifact | Content |
|---|---|
| `docs/plans/evidence/viewer-v0-e-manual-checks.md` | Blank checklist: SR steps + DPI steps; filled during E6/E5 acceptance; Plan F archives |

### 5.8 Plan-D coverage gaps closed in Plan E (binding)

These cases land in **existing Plan D suites** — primarily
`tests/decision/test_decision_presenter.gd`, and table-facing checks only if a sort mode must be
driven through `CandidateTableView.set_sort_mode` (`candidate_table_view.gd:22–27` offers the five
modes). They are **not** new Plan E suite files: they prove Plan D surfaces that Plan E builds on.
Found in the post-merge Plan D test-code review (1568 lines / 59 tests after PR **#47** / **#48**);
**additive coverage only** — no production behavior change.

Reuse the existing `_make_candidate(candidate_id, rank, score, key)` helper already in those suites
(Plan D §14). Do not invent a second factory.

**APIs under test (verified tip):**

| Symbol | Path:lines |
|---|---|
| `resolve_chosen_row_index` + duplicate fail-closed | `decision_presenter.gd:14–29` (`:26–27` return `-1` on second match) |
| `sorted_candidate_indices` + five modes | `decision_presenter.gd:55–92` (`SORT_*` consts `:7–11`) |
| `header_text` | `decision_presenter.gd:46–52` |
| `format_state_summary` | `decision_presenter.gd:162–170` (`NOT_RECORDED` `:5`) |

#### T1 — Sort order + permutation

| Test | Assert |
|---|---|
| `test_sort_rank_ascending` | `SORT_RANK` (`"rank"`): ranks non-decreasing along returned indices. Prefer sealed fixture-16 decision with ≥3 candidates (`bundles/fixture-16`, first non-empty candidates row). |
| `test_sort_score_descending_rank_tiebreak` | `SORT_SCORE`: `aggregate_score` descending; on equal score, lower `rank` first. **Constructed** via `_make_candidate` — fixtures do not reliably expose intentional equal-score pairs; justify constructed DTO in the test comment. |
| `test_sort_label_ascending_rank_tiebreak` | `SORT_LABEL`: `candidate_id` ascending; equal id → lower `rank` first. Constructed for the tie (same rationale). |
| `test_sort_key_ascending_null_empty_rank_tiebreak` | `SORT_KEY`: `str(candidate_key)` ascending with `null → ""` (`decision_presenter.gd:75–76`); equal key text → lower `rank` first. Constructed (need null key + tie). |
| `test_sort_chosen_first_then_rank` | `SORT_CHOSEN_FIRST`: chosen index at position 0; remaining by rank ascending. Prefer sealed fixture row with resolvable chosen (e.g. fixture-16 non-empty) + assert `out[0] == resolve_chosen_row_index(d)`. |
| `test_sort_all_modes_are_permutation` | For **each** of the five `SORT_*` modes: output length == `n`, every index in `0…n-1` appears exactly once (no drops, no duplicates). Catches `return range(n)` only when combined with order tests — both are required. |

#### T2 — Duplicate chosen-key fail-closed

| Test | Assert |
|---|---|
| `test_resolve_chosen_duplicate_key_fail_closed` | `decision_valid = true`; two candidates with the **same** non-null `candidate_key`; `chosen_candidate_key` equals that key → `resolve_chosen_row_index` returns **exactly `-1`** (`decision_presenter.gd:26–27`). Constructed (fixtures refuse / never seal duplicate chosen keys). |

#### T3 — `format_state_summary` / `header_text`

| Test | Assert |
|---|---|
| `test_format_state_summary_empty_or_null` | `decision == null` **or** empty `state_summary` → `DecisionPresenter.NOT_RECORDED` (`"not recorded"`) |
| `test_format_state_summary_sorted_keys` | Non-empty `state_summary` → keys ascending; each line `"<key>: <value>"`; joined with `"\n"` (`decision_presenter.gd:165–170`). Constructed dict with deliberately unsorted insertion order. |
| `test_header_text_valid_invalid_null` | `null` → `""`; `decision_valid == true` → exactly `"decision #<n>"`; `decision_valid == false` → `"decision #<n> (invalid)"` (`decision_presenter.gd:46–52`). Prefer fixture-01 row for the valid branch; constructed/`decision_valid=false` for the invalid suffix. |

**Named-test count for E7 Δ:** **10** cases in §5.8 (6 + 1 + 3).

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

### Task E3 — Scale + density (+ min window 1280×720)

- [ ] **RED:** §5.4 scale/density/min-window tests (`Vector2i(1280, 720)`).
- [ ] **GREEN:** `WorkspaceLayout.set_ui_scale` / `set_density` / min size.
- [ ] **Commit:** `feat(studio): add UI scale and density controls`

### Task E4 — Keyboard shortcuts

- [ ] **Next-close:** Choice Point C **CLOSED** as C1 — no presenter threshold change; bind `jump_next("close")` as-is.
- [ ] **RED:** §5.5 tests — especially filter focus identity + Space suppression.
- [ ] **GREEN:** `WorkspaceShortcuts` + `ShortcutLabels`; bind only §0.6 APIs.
- [ ] **Commit:** `feat(studio): wire keyboard shortcuts to Plan C/D APIs`

### Task E5 — Layout shell + reset

- [ ] **RED:** reset + reachability-oriented layout tests; update shell scene tree.
- [ ] **GREEN:** splits/collapse/reset; small-window stack behavior.
- [ ] **Manual:** start Mixed-DPI checklist draft (unfilled OK until E done).
- [ ] **Commit:** `feat(studio): add workspace layout shell and reset`

### Task E6 — Offline fonts (B2) + monospace surfaces + manual evidence templates

- [ ] **Choice Point B CLOSED as B2 + Auflage.**
- [ ] **RED/GREEN:** §5.3 `test_hash_surfaces_use_monospace`; implement §4.6 `StudioMonoFont`.
- [ ] Grep: no `fonts.googleapis` / http font URLs under `godot/src` and `godot/assets`.
- [ ] Add `docs/plans/evidence/viewer-v0-e-manual-checks.md` template (SR + DPI).
- [ ] **Commit:** `feat(studio): system fonts with monospace hash surfaces + evidence template`

### Task E7 — Full regression + pin

- [ ] §5.8 Plan-D coverage gaps (T1–T3) green in `test_decision_presenter.gd` (and table suite only if needed); suite case count increases by **exactly 10** vs pre-E tip — no silent deletions
- [ ] Every Plan E load path asserts positive load signal after `_await_shell_settled` (§5 settled rule)
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
| Scale 75/100/150/200 | §5.4 + primary controls reachable at **1280×720** |
| Banner correct for fixtures 1, 3, 4, 5, 6 | §5.6 named tests (fixture-06 via `sources/fixture-06/bundle` + `hash_mismatch`) |
| Banner precedence | §5.1 adjacent-pair tests |
| Dirty null honesty | §5.1 / §5.2 |
| Deep link reasons unchanged | Literal `battle_id_mismatch` etc.; `DecisionDeepLink.REASON_*` in prod |
| Offline fonts + monospace hashes | B2; §5.3 `test_hash_surfaces_use_monospace` |
| Mixed-DPI | Checklist **filed** (not “tests passed”) |
| Screen-reader | Honest smoke notes **filed**; no completeness claim |
| Next-close | C1 — unchanged Plan D semantics |
| Plan-D coverage gaps (T1–T3) | §5.8 green; +10 cases |

---

## 8. Self-review checklist (author)

- [x] Sketch ownership split preserved (§0.2)
- [x] Filter precondition recorded as satisfied; no second filter
- [x] Every E4 action maps to a cited existing API
- [x] `_disable_all_nav` marked taboo
- [x] Deep-link vocabulary not duplicated
- [x] D→E handoffs documented
- [x] Choice Points A–C **CLOSED** with decision + rationale; option lists retained
- [x] Spec §6.5 “no universal close threshold” aligned with C1
- [x] SR + DPI are evidence artifacts, not fake gates
- [x] Approve-before-implement sequencing explicit
- [x] F1 precedence pairs named; F2 fixtures 5/6 + no soft “or”; F3 priority-8 DiD; F4 changelog
- [x] B2 monospace Auflage in §0.8 / §0.9 / §4.6 + named test
- [x] Rev. 3: fixture-05 d4 pin; phase tests use sealed fixture-01 rows (G1/G2)
- [x] Rev. 4: §5.8 Plan-D coverage gaps (T1–T3) + settled≠loaded rule (additive, pre-implementation)
- [x] Owner marks APPROVED (not author)

---

## 9. Spec / sketch conflict log

| Topic | Sketch / master | Design (wins) | Plan E handling |
|---|---|---|---|
| Close threshold | Empirics tempt a threshold | §6.5: no universal threshold | Choice Point C → **C1 CLOSED** |
| Master §2.4 SR | Best effort | §9.2 best effort | Evidence note only |
| Master binding | Sketch cites MASTER_SPEC | Index §2.2: non-binding context | Cited as context; design is authority |

---

## 10. Handoff

1. Owner reviews this DRAFT (Rev. 2) against code + design.
2. ~~Owner closes Choice Points A–C~~ — **done in Rev. 2** (§0.13).
3. Status → **APPROVED** in a **docs-only** commit (owner).
4. Separate go-ahead → isolated branch → E1…E7.
5. Plan F consumes manual evidence files.

**Do not** start E code from this DRAFT alone.

---

## 11. Suggested commit cadence (after APPROVED)

| Commit | Content |
|---|---|
| docs | APPROVED mark |
| E1 | Banner |
| E2 | Diagnostics dock |
| E3 | Scale/density/min window |
| E4 | Shortcuts |
| E5 | Layout shell |
| E6 | System fonts + monospace hash surfaces + evidence template |
| E7 | Regression |

---

## 12. Changelog

### Rev. 4 — Plan-D coverage gaps (T1–T3) + settled-load rule

- **Anlass:** Post-merge review of Plan D test code (~1568 lines / 59 tests after PR **#47** /
  **#48**). Production APIs are real; gaps are in **proof** (sort order, duplicate chosen-key
  fail-closed, `format_state_summary` / filled `header_text`).
- **Umfang:** New §5.8 (10 named cases into Plan D presenter suite); binding note that
  `_await_shell_settled` alone is not “loaded”; E7 checkbox for §5.8 + case-count Δ.
- **Einordnung:** Additive amendment **after** APPROVED (Rev. 3 / `f8396e6`) and **before**
  implementation go-ahead — not a scope expansion, not a new approve cycle. Owner box stays checked.

### Rev. 3 — Deterministic fixture-05 banner + real phase rows (G1/G2)

- **G2:** Replaced soft `test_banner_fixture05_after_selection` with
  `test_banner_fixture05_forced_on_d4` — select `decision_index == 4` → pin
  `FORCED REPLACEMENT` (measured: fixture-05 d4/d7 are `forced_replacement`; no
  `fallback_used` anywhere in that file).
- **G1:** `test_phase_team_preview` / `test_phase_forced_replacement` now use fixture-01
  sealed rows (d0 / d1) so Loader → Validator → Seal → `bundle_loader.gd:308` are in the
  proof chain, not only a constructed DTO `match`.

### Rev. 2 — Choice points closed + F1–F4

- §0.13: A→**A1 1280×720**, B→**B2 system stack + monospace Auflage**, C→**C1 keep Plan D close nav** — all **CLOSED (owner, Rev. 2)**; option tables retained as protocol.
- B2 Auflage made binding in §0.8 / §0.9 / §4.2 / §4.6 with Godot `SystemFont` + `Control.add_theme_font_override` / `has_theme_font_override` / `get_theme_font` cites; named test `test_hash_surfaces_use_monospace`.
- **F1:** §5.1 adds seven adjacent precedence cases (1v2…7v8); 1v2 / 2v3 / 5v6 called out; 4v5 and 6v7 documented where simultaneous is unreachable.
- **F2:** §5.6 adds fixture-05 and fixture-06 (`sources/fixture-06/bundle` + pin `hash_mismatch`); replaces soft `test_banner_fixture03_or_fallback_path` with deterministic fallback-row assert.
- **F3:** Priority 8 limited to `PHASE_REGULAR_TURN`; other phases marked unreachable / DiD with `bundle_validator.gd:73–75` / `:683`.
- **F4:** Document that **E7** (full regression + pin) is new vs sketch E1–E6 (intentional, not scope creep).

### Rev. 1 — sketch → executable

- Expanded to Plan D structural density: §0 closed decisions, open choice points, file map,
  contracts, named tests, TDD tasks, acceptance, handoff.
- Locked E4 to verified TimelineController playback API (`play`/`pause`/`toggle_play`).
- Recorded D→E handoffs from `19e1bc7`.
- Marked filter precondition satisfied (Plan D shipped).
- Separated prominent `StateBanner` from operational `StatusLabel`.
- Added honesty protocol for screen-reader and Mixed-DPI evidence.
- Introduced **E7** (regression + pin) beyond sketch E1–E6.