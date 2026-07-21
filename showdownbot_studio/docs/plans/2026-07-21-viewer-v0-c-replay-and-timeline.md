# Viewer v0 — Plan C: Replay and Timeline

**Status:** APPROVED — 2026-07-21 (Rev. 5). Authorizes this plan’s document scope only.
Self-contained; supersedes Rev. 1–4 text (no cross-rev references for acceptance).
**Does not authorize code.** Implementation starts only after a separate implementation
go-ahead is given. Plan B is already **merged** to `main` via PR **#44** @ `c830465`.
**Date:** 2026-07-21 · **Rev.:** 5
**Depends on (code start):** Plan B **merged** @ `c830465` (loader + sealed DTOs + AppShell);
Plan A fixtures **1, 4, 5** under `fixtures/viewer-v0/bundles/`; separate implementation go-ahead.
**Unblocks:** Plan D (timeline selection signal); Plan E (banner/keyboard polish on C surfaces);
Plan C code only after go-ahead

**Authority:** [`../specs/viewer-v0-design.md`](../specs/viewer-v0-design.md) §5.3–5.4 / §6.1 /
§6.3 / §7,
[`../specs/viewer-v0-bundle-contract-design.md`](../specs/viewer-v0-bundle-contract-design.md)
§10.3 / §11.1 / §11.3 (incl. §14.1 Amendment A as fixture context only),
[`2026-07-21-viewer-v0-implementation-index.md`](2026-07-21-viewer-v0-implementation-index.md) §3 / §5,
[`2026-07-21-viewer-v0-b-godot-shell-and-loader.md`](2026-07-21-viewer-v0-b-godot-shell-and-loader.md)
(APPROVED Rev. 6; **merged** implementation is source of truth for class/signal names),
[`../design/viewer-v0-mockups/README.md`](../design/viewer-v0-mockups/README.md)

> **For agentic workers:** after this plan is marked **APPROVED** and a separate implementation
> go-ahead is given, execute task-by-task with TDD (gdUnit4 headless on pinned Godot **4.5.2**).
> No Python exporter changes. No edits under `showdown_bot/`, `data/eval/`, `config/eval/`, or
> `reports/`. No Plan D candidate table, Plan E a11y/layout/diagnostics, or Plan F E2E freeze work.
> This document supersedes Plan C Rev. 1–4; do not look up older text for acceptance.

---

## 0. Closed decisions (binding)

### 0.1 Verified Plan B surface (do not invent)

Verified on `main` @ `c830465`. Plan C consumes these exact names:

| Kind | Identifier | Path |
|---|---|---|
| Node | `BundleLoader` | `godot/src/bundle/bundle_loader.gd` |
| States | `BundleLoader.State`: `IDLE`, `LOADING`, `COMPLETED`, `REFUSED`, `CANCELLED` | same |
| Signals | `progress(message: String)`, `completed(bundle: BundleDTO)`, `refused(diagnostic: RefuseDiagnostic)`, `cancelled` | same |
| API | `load_async(path)`, `cancel()`, `get_state()`, `is_worker_thread_joined()` | same |
| Shell | `AppShell` | `godot/src/workspace/app_shell.gd` + `app_shell.tscn` |
| Shell API | `open_bundle_path`, `get_loaded_bundle`, `get_declared_mode`, `get_effective_mode`, `get_trace_trusted`, `get_replay_trusted`, `get_status_text`, … | same |
| Mode consts | `BundleMode.REPLAY_TRACE`, `REPLAY_ONLY`, `TRACE_ONLY` | `bundle_mode.gd` |
| Events | `BundleDTO.battle_events: Array[BattleEventDTO]` | `bundle_dto.gd` |
| Decisions | `BundleDTO.decisions: Array[DecisionRowDTO]` | same |
| Join field | `DecisionRowDTO.request_protocol_index: Variant` (int\|null) | `decision_row_dto.gd` |
| Fachliche Decision-ID | `DecisionRowDTO.decision_index: int` | same — **display id**, may be non-contiguous |
| Validity | `DecisionRowDTO.decision_valid: bool` | same |
| Event index | `BattleEventDTO.protocol_index: int` | `battle_event_dto.gd` |
| Flattened event fields | `pokemon_side`, `pokemon_slot`, `pokemon_species`, `hp_current`, `hp_maximum`, `hp_fainted`, `hp_status`, `details`, `amount`, `value`, `side`, `target_side`, `target_slot`, `tags`, … | same |
| Engine pin | `godot/tools/verify_engine_pin.ps1`, `run_gdunit_headless.ps1` | Plan B |

**Failed loads:** no `FAILED` enum. Failures → `State.REFUSED`. Plan C treats **REFUSED** as the
fail terminal.

**Worker rule:** UI Nodes never hold worker Threads, never call `BundleWorker.thread_main`, never
read `_message_queue`. Only `BundleLoader` signals on the main thread.

### 0.2 Naming + scene ownership (binding)

| `class_name` | File | Role |
|---|---|---|
| `TimelineEntryKind` | `godot/src/timeline/timeline_entry_kind.gd` | String constants |
| `TimelineEntryDTO` | `godot/src/timeline/timeline_entry_dto.gd` | Sealed entry row |
| `ReplayDTO` | `godot/src/replay/replay_dto.gd` | Sealed derived model |
| `BattleTimeline` | `godot/src/timeline/battle_timeline.gd` | `BundleDTO` → `ReplayDTO` |
| `BoardModel` | `godot/src/replay/board_model.gd` | Mutable presentation state |
| `ReplayPresenter` | `godot/src/replay/replay_presenter.gd` | Events → fresh `BoardModel` |
| `TimelineController` | `godot/src/timeline/timeline_controller.gd` | Cursor + Timer |
| `TimelineView` | `godot/src/timeline/timeline_view.gd` + `.tscn` | Bounded list UI |
| `AbstractBoardView` | `godot/src/replay/abstract_board_view.gd` + `.tscn` | Abstract board UI |
| `ReplayWorkspace` | `godot/src/replay/replay_workspace.gd` + `.tscn` | Owns controller + views |

One public `class_name` per `.gd` file (Plan B §6.0).

**Scene ownership:** `AppShell` instances **exactly one** `ReplayWorkspace` at
`$VBox/ReplayWorkspace`. `ReplayWorkspace` owns `$TimelineController`, `$Board`, `$Timeline`.

**Controller injection (binding):** `TimelineView.set_controller(controller: TimelineController)` —
not `@export`. `ReplayWorkspace` calls it in `_ready` / `reset`.

### 0.3 Data authority

1. Sealed Plan-B `BundleDTO` from `BundleLoader.completed` is the only battle/decision authority.
2. `ReplayDTO` is derived on the main thread; stores indices into sealed arrays; no JSON re-parse.
3. `BoardModel` is ephemeral; rebuilt from recorded events; wiped on bundle change / refuse / cancel.
4. UI Nodes never open bundle files and never touch worker threads.

### 0.4 Timeline join (contract §11.3.3 — binding)

```text
Input: sealed BundleDTO
replay_ok = bundle.replay_trusted
trace_ok  = bundle.trace_trusted

events = bundle.battle_events if replay_ok else []
decisions = bundle.decisions if trace_ok else []

entries = [EVENT(event_index=i) for i in range(events.size())]

for d in decisions sorted by DecisionRowDTO.decision_index ascending:
  decision_row_index = index of d in bundle.decisions array  # NOT decision_index
  rpi = d.request_protocol_index
  if rpi == null:
    kind = DECISION_WITHOUT_REPLAY_EVENT
    append at end (null-rpi tail; ascending because we process ascending)
  else:
    kind = DECISION
    # 1) insert_at = index after last EVENT with protocol_index < rpi (0 if none)
    # 2) advance insert_at across already-inserted DECISION entries in this gap
    #    (same event-gap), stopping before the next EVENT and before any
    #    DECISION_WITHOUT_REPLAY_EVENT tail entry
    # Result: same-gap decisions stay ascending by DecisionRowDTO.decision_index
```

**Index vocabulary:**

| Name | Meaning |
|---|---|
| `event_index` | Array index into `bundle.battle_events` |
| `decision_row_index` | Array index into `bundle.decisions` |
| `DecisionRowDTO.decision_index` | Fachliche ID for labels (`decision #i`); may be non-contiguous |
| `selected_entry_index` | Cursor into `ReplayDTO.entries` |

**Verified fixture-01 join (for tests):**

| entry | kind | note |
|---|---|---|
| 0 | DECISION id 0 | **before first EVENT** (rpi=3) |
| 1 | EVENT turn 1 | event_index 0 |
| 2 | EVENT switch Pikachu | event_index 1 |
| 3 | DECISION id 1 | rpi=6 |
| 4 | EVENT turn 2 | event_index 2 |
| 5 | EVENT move Tackle | event_index 3 |
| 6 | DECISION id 2 | after last move (rpi=9) |

### 0.5 Cursor / board semantics (binding)

| Concept | Rule |
|---|---|
| Cursor | `selected_entry_index` in `[0, entries.size())`, or `-1` when empty |
| Board rebuild | Every selection: **fresh** `BoardModel`, apply all `EVENT` entries with entry index `<= selected_entry_index` |
| `has_replay` | **`replay.replay_trusted`** — independent of apply-set emptiness |
| `has_recorded_state` | true iff any recorded field is non-empty after apply (see §4.4) |
| Decision before first event | `has_replay=true` (when trusted), `has_recorded_state=false`; **never** show “No replay evidence…” |
| Decision entries | do not mutate board; only move cursor |
| Backward step | future state disappears via rebuild-from-start |
| Invalid decision | label suffix `(invalid)`; never invent chosen candidate |
| Play | Timer 250 ms default; pause cancels; stop at end |
| Trace-only | `has_replay=false`; empty-state text shown |
| Effective mode | always `bundle.effective_mode` |

### 0.6 Loader / shell coupling (binding)

| Moment | Action |
|---|---|
| `AppShell._start_load` **before** `load_async` | `ReplayWorkspace.clear()` + `set_loading(true)` — empty timeline/board, stop Timer, disable controls, Loading chrome on both views |
| `LOADING` / `progress` | keep disabled + Loading chrome |
| `completed(bundle)` | `build` → `ReplayWorkspace.reset(replay, bundle)` → cursor Start → board rebuild → enable per mode → clear Loading |
| `refused` / `cancelled` | `ReplayWorkspace.clear()`; shell status as today |

**Loading chrome (required):** `TimelineView` / `AbstractBoardView` `set_loading(active)`.

### 0.7 Fixtures (Plan C)

| Role | Path | Expectation |
|---|---|---|
| Trusted replay+trace | `bundles/fixture-01/` | Join per §0.4 table; p1a Pikachu after switch |
| Replay-only | `bundles/fixture-04/` | Events only; **also** p1a Pikachu — cursor-reset only |
| Trace-only | `bundles/fixture-05/` | `has_replay=false`; empty-state text |
| Hash refuse | `sources/fixture-06/bundle/` | Clear surfaces |
| Unit cases | Constructed sealed DTOs in test helpers | No new JSONL under `tests/fixtures/unit/` |

**Bundle-switch board proof (binding):** **only** fixture **01 → 05**. Never 01→04 for species leftover.
**Cursor proof:** 01 → 04.

### 0.8 Scope fence

**In:** timeline model, bounded timeline view, abstract board, playback controls, mode-correct
empty/waiting states, `ReplayWorkspace` wiring, gdUnit tests, pin+headless commands.

**Out:** Plan D candidates; Plan E a11y/layout/diagnostics; Plan F E2E; artwork; mechanics sim.

### 0.9 Implementation gate

Rev. 5 is **APPROVED** for document scope only. Coding still requires a separate
implementation go-ahead.

### 0.10 Closed choice points (no implementer discretion)

| Topic | Binding |
|---|---|
| Loading chrome | Required via `set_loading` |
| Shell child | `$VBox/ReplayWorkspace` |
| Unit fixtures | Constructed sealed DTOs only |
| C3 tests | §6.5 GREEN before C3 commit |
| C4 tests | §6.4 RED starts in C4 only |
| Board leftover proof | **01 → 05 only** |
| Cursor reset proof | 01 → 04 |
| Board rebuild | Fresh model from start |
| Timeline bind | `bind(replay, bundle)` |
| Controller inject | **`set_controller(controller)` only** |
| Field effects | Terrain whitelist vs `field_conditions` (§4.5) |

---

## 1. Goal / non-goals

**Goal:** Derive a deterministic protocol/decision timeline and abstract doubles board from sealed
Plan-B DTOs; step/jump/play; honor modes and refuse/cancel; rebuild board from start on every
selection; distinguish “no replay in bundle” from “replay trusted but no field state yet”.

**Non-goals:** candidates; diagnostics/a11y program; E2E freeze; exporter changes; worker work.

---

## 2. Architecture

```text
AppShell._start_load
  -> ReplayWorkspace.clear() + set_loading(true)   # BEFORE load_async
  -> BundleLoader.load_async(path)

completed(BundleDTO)
  -> ReplayDTO = BattleTimeline.build(bundle)
  -> ReplayWorkspace.reset(replay, bundle)
       TimelineController.reset → selection_changed(0)
       ReplayPresenter.build_board → AbstractBoardView.bind
       TimelineView.bind(replay, bundle)

TimelineController.selection_changed(i)
  -> fresh BoardModel via ReplayPresenter.build_board
  -> AbstractBoardView.bind(board)
  -> TimelineView.set_selected_entry_index(i)
```

---

## 3. File map

| Path | Responsibility |
|---|---|
| `godot/src/timeline/timeline_entry_kind.gd` | Kind constants |
| `godot/src/timeline/timeline_entry_dto.gd` | Sealed entry |
| `godot/src/timeline/battle_timeline.gd` | Join builder |
| `godot/src/replay/replay_dto.gd` | Sealed replay model |
| `godot/src/replay/board_model.gd` | Presentation state + mutators |
| `godot/src/replay/replay_presenter.gd` | Apply map |
| `godot/src/timeline/timeline_controller.gd` | Cursor + Timer |
| `godot/src/timeline/timeline_view.gd` + `.tscn` | List + controls |
| `godot/src/replay/abstract_board_view.gd` + `.tscn` | Board chrome |
| `godot/src/replay/replay_workspace.gd` + `.tscn` | Wiring hub |
| `godot/src/workspace/app_shell.gd` + `.tscn` | Parent workspace |
| `godot/tests/timeline/test_battle_timeline.gd` | Join tests |
| `godot/tests/replay/test_replay_presenter.gd` | Board apply tests |
| `godot/tests/timeline/test_timeline_controller.gd` | Cursor tests |
| `godot/tests/timeline/test_timeline_view.gd` | View label tests |
| `godot/tests/replay/test_abstract_board_view.gd` | Board view tests |
| `godot/tests/workspace/test_app_shell_replay.gd` | Shell integration |

### 3.1 Binding scene trees

**`app_shell.tscn` (after C4)** — add child under existing `VBox`:

```text
AppShell (Control)                         # existing
├── VBox (VBoxContainer)                   # existing $VBox
│   ├── PathRow (HBoxContainer)            # existing $VBox/PathRow
│   │   ├── PathEdit                       # existing
│   │   └── OpenButton                     # existing
│   ├── StatusLabel                        # existing $VBox/StatusLabel
│   └── ReplayWorkspace                    # NEW $VBox/ReplayWorkspace  (instance)
└── BundleLoader                           # existing $BundleLoader
```

**`replay_workspace.tscn`:**

```text
ReplayWorkspace (VBoxContainer)            # script replay_workspace.gd
├── Board (instance abstract_board_view.tscn)   # $Board
├── Timeline (instance timeline_view.tscn)      # $Timeline
└── TimelineController (Node)                   # $TimelineController
```

**`timeline_view.tscn`:**

```text
TimelineView (VBoxContainer)
├── LoadingLabel (Label)                   # $LoadingLabel  text=""
├── EntryList (ItemList)                   # $EntryList
└── Controls (HBoxContainer)               # $Controls
    ├── PrevButton (Button)                # $Controls/PrevButton
    ├── NextButton (Button)                # $Controls/NextButton
    ├── StartButton (Button)               # $Controls/StartButton
    ├── EndButton (Button)                 # $Controls/EndButton
    └── PlayButton (Button)                # $Controls/PlayButton
```

**`abstract_board_view.tscn`:**

```text
AbstractBoardView (VBoxContainer)
├── LoadingLabel (Label)                   # $LoadingLabel
├── EmptyStateLabel (Label)                # $EmptyStateLabel
├── MetaRow (HBoxContainer)                # $MetaRow
│   ├── TurnLabel (Label)                  # $MetaRow/TurnLabel
│   ├── WeatherLabel (Label)               # $MetaRow/WeatherLabel
│   ├── TerrainLabel (Label)               # $MetaRow/TerrainLabel
│   └── FieldConditionsLabel (Label)       # $MetaRow/FieldConditionsLabel
├── SideConditionsRow (HBoxContainer)      # $SideConditionsRow
│   ├── P1SideLabel (Label)                # $SideConditionsRow/P1SideLabel
│   └── P2SideLabel (Label)                # $SideConditionsRow/P2SideLabel
└── Slots (GridContainer)                  # $Slots  columns=2
    ├── P1ASpecies (Label)                 # $Slots/P1ASpecies
    ├── P1AHP (Label)                      # $Slots/P1AHP
    ├── P1AStatus (Label)                  # $Slots/P1AStatus
    ├── P1BSpecies / P1BHP / P1BStatus
    ├── P2ASpecies / P2AHP / P2AStatus
    └── P2BSpecies / P2BHP / P2BStatus
```

---

## 4. DTO / model contracts

### 4.1 `TimelineEntryKind`

```gdscript
class_name TimelineEntryKind
extends RefCounted

const EVENT := "EVENT"
const DECISION := "DECISION"
const DECISION_WITHOUT_REPLAY_EVENT := "DECISION_WITHOUT_REPLAY_EVENT"
```

### 4.2 `TimelineEntryDTO` (sealed — binding body)

| Field | Type | Rules |
|---|---|---|
| `kind` | `String` | one of §4.1 |
| `event_index` | `int` | into `battle_events`, or `-1` |
| `decision_row_index` | `int` | into `decisions`, or `-1` |
| `protocol_anchor` | `Variant` | event `protocol_index` / decision `request_protocol_index` |

```gdscript
class_name TimelineEntryDTO
extends RefCounted

var _sealed: bool = false
var _kind: String = ""
var _event_index: int = -1
var _decision_row_index: int = -1
var _protocol_anchor: Variant = null

var kind: String:
	get:
		return _kind
	set(value):
		if _sealed:
			return
		_kind = value

var event_index: int:
	get:
		return _event_index
	set(value):
		if _sealed:
			return
		_event_index = value

var decision_row_index: int:
	get:
		return _decision_row_index
	set(value):
		if _sealed:
			return
		_decision_row_index = value

var protocol_anchor: Variant:
	get:
		return _protocol_anchor
	set(value):
		if _sealed:
			return
		_protocol_anchor = value


func seal() -> void:
	if _sealed:
		return
	_sealed = true
```

### 4.3 `ReplayDTO` (sealed — binding body)

| Field | Type |
|---|---|
| `entries` | `Array` of `TimelineEntryDTO` |
| `declared_mode` | `String` |
| `effective_mode` | `String` |
| `replay_trusted` | `bool` |
| `trace_trusted` | `bool` |

```gdscript
class_name ReplayDTO
extends RefCounted

var _sealed: bool = false
var _entries: Array = []
var _declared_mode: String = ""
var _effective_mode: String = ""
var _replay_trusted: bool = false
var _trace_trusted: bool = false

var entries: Array:
	get:
		return _entries
	set(value):
		if _sealed:
			return
		_entries = value if value != null else []

var declared_mode: String:
	get:
		return _declared_mode
	set(value):
		if _sealed:
			return
		_declared_mode = value

var effective_mode: String:
	get:
		return _effective_mode
	set(value):
		if _sealed:
			return
		_effective_mode = value

var replay_trusted: bool:
	get:
		return _replay_trusted
	set(value):
		if _sealed:
			return
		_replay_trusted = value

var trace_trusted: bool:
	get:
		return _trace_trusted
	set(value):
		if _sealed:
			return
		_trace_trusted = value


func seal() -> void:
	if _sealed:
		return
	for entry in _entries:
		if entry is TimelineEntryDTO:
			entry.seal()
	_entries.make_read_only()
	_sealed = true
```

### 4.4 `BoardModel` — exact structure (binding)

```gdscript
class_name BoardModel
extends RefCounted

## True iff the sealed replay carries trusted battle events (replay.replay_trusted).
## Independent of whether any EVENT has been applied yet.
var has_replay: bool = false

## True iff at least one recorded presentation field is non-empty after apply.
var has_recorded_state: bool = false

var turn_number: Variant = null
var weather: Variant = null
var terrain: Variant = null
var last_move: Variant = null
var field_conditions: PackedStringArray = PackedStringArray()

## slots[side][slot] -> Dictionary with keys:
## species, hp_current, hp_maximum, hp_fainted, hp_status  (all Variant; null = unset)
var slots: Dictionary = {}

## side_conditions[side] -> PackedStringArray
var side_conditions: Dictionary = {}


func _init() -> void:
	slots = {
		"p1": {"a": _empty_slot(), "b": _empty_slot()},
		"p2": {"a": _empty_slot(), "b": _empty_slot()},
	}
	side_conditions = {
		"p1": PackedStringArray(),
		"p2": PackedStringArray(),
	}


static func _empty_slot() -> Dictionary:
	return {
		"species": null,
		"hp_current": null,
		"hp_maximum": null,
		"hp_fainted": null,
		"hp_status": null,
	}


func get_slot(side: String, slot: String) -> Dictionary:
	return slots[side][slot]


func set_slot_species(side: String, slot: String, species: Variant) -> void:
	slots[side][slot]["species"] = species


## Partial HP update for damage/heal/sethp/detailschange — never used for switch.
func apply_slot_hp(side: String, slot: String, event: BattleEventDTO) -> void:
	var cell: Dictionary = slots[side][slot]
	if event.hp_current != null:
		cell["hp_current"] = event.hp_current
	if event.hp_maximum != null:
		cell["hp_maximum"] = event.hp_maximum
	if event.hp_fainted != null:
		cell["hp_fainted"] = event.hp_fainted
	if event.hp_status != null:
		cell["hp_status"] = event.hp_status


## Full slot replace for `switch`: overwrites species and all five HP fields,
## including explicit nulls (clears prior burn/status/HP from the previous occupant).
func replace_slot_from_switch(side: String, slot: String, event: BattleEventDTO) -> void:
	slots[side][slot] = {
		"species": event.pokemon_species,
		"hp_current": event.hp_current,
		"hp_maximum": event.hp_maximum,
		"hp_fainted": event.hp_fainted,
		"hp_status": event.hp_status,
	}


func set_slot_status(side: String, slot: String, status: Variant) -> void:
	slots[side][slot]["hp_status"] = status


## Recorded faint proves 0 HP. Always force hp_current=0 and hp_fainted=true,
## even when a prior positive hp_current was recorded.
func set_slot_fainted(side: String, slot: String) -> void:
	slots[side][slot]["hp_fainted"] = true
	slots[side][slot]["hp_current"] = 0



func add_side_condition(side: String, label: String) -> void:
	var arr: PackedStringArray = side_conditions[side]
	if not label in arr:
		arr.append(label)
		side_conditions[side] = arr


func remove_side_condition(side: String, label: String) -> void:
	var arr: PackedStringArray = side_conditions[side]
	var next := PackedStringArray()
	for item in arr:
		if item != label:
			next.append(item)
	side_conditions[side] = next


func add_field_condition(label: String) -> void:
	if not label in field_conditions:
		field_conditions.append(label)


func remove_field_condition(label: String) -> void:
	var next := PackedStringArray()
	for item in field_conditions:
		if item != label:
			next.append(item)
	field_conditions = next


func recompute_has_recorded_state() -> void:
	if turn_number != null or weather != null or terrain != null or last_move != null:
		has_recorded_state = true
		return
	if field_conditions.size() > 0:
		has_recorded_state = true
		return
	for side in ["p1", "p2"]:
		if side_conditions[side].size() > 0:
			has_recorded_state = true
			return
		for slot in ["a", "b"]:
			var cell: Dictionary = slots[side][slot]
			# Any of the five slot fields being non-null counts, including
			# recorded hp_fainted=false and a lone hp_maximum.
			if (
				cell["species"] != null
				or cell["hp_current"] != null
				or cell["hp_maximum"] != null
				or cell["hp_fainted"] != null
				or cell["hp_status"] != null
			):
				has_recorded_state = true
				return
	has_recorded_state = false
```

### 4.5 `ReplayPresenter` apply map (binding)

```gdscript
class_name ReplayPresenter
extends RefCounted

const KNOWN_TERRAINS := PackedStringArray([
	"Electric Terrain",
	"Grassy Terrain",
	"Misty Terrain",
	"Psychic Terrain",
])


static func build_board(bundle: BundleDTO, replay: ReplayDTO, selected_entry_index: int) -> BoardModel:
	var board := BoardModel.new()
	board.has_replay = replay.replay_trusted
	if not replay.replay_trusted:
		board.recompute_has_recorded_state()
		return board
	var end_i := mini(selected_entry_index, replay.entries.size() - 1)
	for i in range(0, end_i + 1):
		var entry: TimelineEntryDTO = replay.entries[i]
		if entry.kind != TimelineEntryKind.EVENT:
			continue
		var event: BattleEventDTO = bundle.battle_events[entry.event_index]
		_apply_event(board, event)
	board.recompute_has_recorded_state()
	return board


static func _field_label(event: BattleEventDTO) -> Variant:
	if event.value != null and typeof(event.value) == TYPE_STRING:
		return event.value
	if event.details != null and typeof(event.details) == TYPE_STRING:
		return event.details
	return null


static func _is_terrain_label(label: String) -> bool:
	return label in KNOWN_TERRAINS


static func _is_board_side(side: String) -> bool:
	return side == "p1" or side == "p2"


static func _is_board_slot(slot: String) -> bool:
	return slot == "a" or slot == "b"


## Returns [side, slot] only for p1/p2 × a/b. Unknown sides, numeric slots
## (e.g. 0/1), or missing values → empty Array (fail-soft recorded no-op).
## Never index BoardModel.slots with unvalidated keys.
static func _pokemon_side_slot(event: BattleEventDTO) -> Array:
	if event.pokemon_side == null or event.pokemon_slot == null:
		return []
	var side := String(event.pokemon_side)
	var slot := String(event.pokemon_slot)
	if not _is_board_side(side) or not _is_board_slot(slot):
		return []
	return [side, slot]


static func _apply_event(board: BoardModel, event: BattleEventDTO) -> void:
	match event.type:
		"turn":
			if typeof(event.amount) == TYPE_INT:
				board.turn_number = event.amount
		"switch":
			var id := _pokemon_side_slot(event)
			if id.is_empty():
				return
			board.replace_slot_from_switch(id[0], id[1], event)
		"detailschange":
			var id := _pokemon_side_slot(event)
			if id.is_empty():
				return
			if event.pokemon_species != null:
				board.set_slot_species(id[0], id[1], event.pokemon_species)
			board.apply_slot_hp(id[0], id[1], event)
		"move":
			if typeof(event.details) == TYPE_STRING:
				board.last_move = event.details
		"damage", "heal", "sethp":
			var id := _pokemon_side_slot(event)
			if id.is_empty():
				return
			board.apply_slot_hp(id[0], id[1], event)
		"faint":
			var id := _pokemon_side_slot(event)
			if id.is_empty():
				return
			# Optional recorded max/status first, then force faint + 0 HP.
			board.apply_slot_hp(id[0], id[1], event)
			board.set_slot_fainted(id[0], id[1])
		"status":
			var id := _pokemon_side_slot(event)
			if id.is_empty():
				return
			var st: Variant = event.details if event.details != null else event.value
			board.set_slot_status(id[0], id[1], st)
		"curestatus":
			var id := _pokemon_side_slot(event)
			if id.is_empty():
				return
			board.set_slot_status(id[0], id[1], null)
		"weather":
			board.weather = event.value
		"fieldstart":
			var label = _field_label(event)
			if label == null:
				return
			var s := String(label)
			if _is_terrain_label(s):
				board.terrain = s
			else:
				board.add_field_condition(s)
		"fieldend":
			var label = _field_label(event)
			if label == null:
				return
			var s := String(label)
			if _is_terrain_label(s):
				if board.terrain == s:
					board.terrain = null
			else:
				board.remove_field_condition(s)
		"sidestart":
			if event.side == null:
				return
			var side := String(event.side)
			if not _is_board_side(side):
				return
			var label = _field_label(event)
			if label == null:
				return
			board.add_side_condition(side, String(label))
		"sideend":
			if event.side == null:
				return
			var side := String(event.side)
			if not _is_board_side(side):
				return
			var label = _field_label(event)
			if label == null:
				return
			board.remove_side_condition(side, String(label))
		_:
			pass  # boost/item/enditem/mega — recorded no-op
```


**Empty apply-set rule:** if `replay_trusted` and cursor is on a decision before the first EVENT
(fixture-01 entry 0), board stays blank cells but `has_replay == true` and
`has_recorded_state == false`.

### 4.6 `TimelineController` API

```gdscript
class_name TimelineController
extends Node

signal selection_changed(entry_index: int)
signal playback_changed(playing: bool)

var _replay: ReplayDTO = null
var _bundle: BundleDTO = null
var _selected: int = -1
var _playing: bool = false
var _timer: Timer


func _ready() -> void:
	_timer = Timer.new()
	_timer.wait_time = 0.25
	_timer.one_shot = false
	add_child(_timer)
	_timer.timeout.connect(_on_timer_timeout)


func reset(replay: ReplayDTO, bundle: BundleDTO) -> void:
	pause()
	_replay = replay
	_bundle = bundle
	_selected = 0 if replay.entries.size() > 0 else -1
	selection_changed.emit(_selected)


func clear() -> void:
	pause()
	_replay = null
	_bundle = null
	_selected = -1
	selection_changed.emit(_selected)


func select(entry_index: int) -> void:
	if _replay == null or _replay.entries.is_empty():
		return
	var next := clampi(entry_index, 0, _replay.entries.size() - 1)
	if next == _selected:
		return
	_selected = next
	selection_changed.emit(_selected)


func step_prev() -> void:
	select(_selected - 1)


func step_next() -> void:
	select(_selected + 1)


func jump_start() -> void:
	select(0)


func jump_end() -> void:
	if _replay == null or _replay.entries.is_empty():
		return
	select(_replay.entries.size() - 1)


func play() -> void:
	if _replay == null or _replay.entries.is_empty():
		return
	_playing = true
	_timer.start()
	playback_changed.emit(true)


func pause() -> void:
	_playing = false
	if _timer != null:
		_timer.stop()
	playback_changed.emit(false)


func toggle_play() -> void:
	if _playing:
		pause()
	else:
		play()


func get_selected_entry_index() -> int:
	return _selected


func is_playing() -> bool:
	return _playing


func get_replay() -> ReplayDTO:
	return _replay


func get_bundle() -> BundleDTO:
	return _bundle


func set_timer_wait_time(seconds: float) -> void:
	_timer.wait_time = seconds


func _on_timer_timeout() -> void:
	if _replay == null:
		pause()
		return
	if _selected >= _replay.entries.size() - 1:
		pause()
		return
	step_next()
```

### 4.7 `ReplayWorkspace` API + wiring

```gdscript
class_name ReplayWorkspace
extends VBoxContainer

@onready var _board_view: AbstractBoardView = $Board
@onready var _timeline_view: TimelineView = $Timeline
@onready var _controller: TimelineController = $TimelineController

var _presenter := ReplayPresenter.new()
var _board: BoardModel = null
var _replay: ReplayDTO = null
var _bundle: BundleDTO = null


func _ready() -> void:
	_timeline_view.set_controller(_controller)
	_controller.selection_changed.connect(_on_selection_changed)
	clear()


func clear() -> void:
	_controller.clear()
	_replay = null
	_bundle = null
	_board = null
	_timeline_view.bind(null, null)
	_board_view.bind(null)
	set_loading(false)
	_timeline_view.set_controls_enabled(false)


func set_loading(active: bool) -> void:
	_timeline_view.set_loading(active)
	_board_view.set_loading(active)


func reset(replay: ReplayDTO, bundle: BundleDTO) -> void:
	_replay = replay
	_bundle = bundle
	set_loading(false)
	_timeline_view.bind(replay, bundle)
	_timeline_view.set_controls_enabled(replay.entries.size() > 0)
	_controller.reset(replay, bundle)  # emits selection_changed → board bind


func get_timeline_controller() -> TimelineController:
	return _controller


func get_timeline_view() -> TimelineView:
	return _timeline_view


func get_board_view() -> AbstractBoardView:
	return _board_view


func get_board_model() -> BoardModel:
	return _board


func _on_selection_changed(entry_index: int) -> void:
	_timeline_view.set_selected_entry_index(entry_index)
	if _replay == null or _bundle == null or entry_index < 0:
		_board = null
		_board_view.bind(null)
		return
	_board = ReplayPresenter.build_board(_bundle, _replay, entry_index)
	_board_view.bind(_board)
```

---

## 5. View contracts

### 5.1 `TimelineView`

```gdscript
class_name TimelineView
extends VBoxContainer

@onready var _loading: Label = $LoadingLabel
@onready var _list: ItemList = $EntryList
@onready var _prev: Button = $Controls/PrevButton
@onready var _next: Button = $Controls/NextButton
@onready var _start: Button = $Controls/StartButton
@onready var _end: Button = $Controls/EndButton
@onready var _play: Button = $Controls/PlayButton

var _controller: TimelineController = null
var _labels: PackedStringArray = PackedStringArray()


func set_controller(controller: TimelineController) -> void:
	_controller = controller
	if not _prev.pressed.is_connected(_controller.step_prev):
		_prev.pressed.connect(_controller.step_prev)
		_next.pressed.connect(_controller.step_next)
		_start.pressed.connect(_controller.jump_start)
		_end.pressed.connect(_controller.jump_end)
		_play.pressed.connect(_controller.toggle_play)
	if not _list.item_selected.is_connected(_on_item_selected):
		_list.item_selected.connect(_on_item_selected)


func _on_item_selected(index: int) -> void:
	if _controller == null:
		return
	_controller.select(index)


func bind(replay: ReplayDTO, bundle: BundleDTO) -> void:
	_list.clear()
	_labels = PackedStringArray()
	if replay == null or bundle == null:
		return
	for i in range(replay.entries.size()):
		var label := _label_for(replay.entries[i], bundle)
		_labels.append(label)
		_list.add_item(label)


func set_selected_entry_index(entry_index: int) -> void:
	if entry_index < 0 or entry_index >= _list.item_count:
		_list.deselect_all()
		return
	_list.select(entry_index)


func set_loading(active: bool) -> void:
	_loading.text = "Loading..." if active else ""


func set_controls_enabled(enabled: bool) -> void:
	_prev.disabled = not enabled
	_next.disabled = not enabled
	_start.disabled = not enabled
	_end.disabled = not enabled
	_play.disabled = not enabled


func get_visible_label(entry_index: int) -> String:
	if entry_index < 0 or entry_index >= _labels.size():
		return ""
	return _labels[entry_index]


func _label_for(entry: TimelineEntryDTO, bundle: BundleDTO) -> String:
	if entry.kind == TimelineEntryKind.EVENT:
		var ev: BattleEventDTO = bundle.battle_events[entry.event_index]
		if ev.type == "turn":
			return "turn %s" % str(ev.amount) if typeof(ev.amount) == TYPE_INT else "turn"
		if ev.type == "move":
			return "move %s" % str(ev.details) if typeof(ev.details) == TYPE_STRING else "move"
		return ev.type
	var row: DecisionRowDTO = bundle.decisions[entry.decision_row_index]
	var base := "decision #%d" % row.decision_index
	if entry.kind == TimelineEntryKind.DECISION_WITHOUT_REPLAY_EVENT:
		base += " (no replay event)"
	if not row.decision_valid:
		base += " (invalid)"
	return base
```

### 5.2 `AbstractBoardView`

```gdscript
class_name AbstractBoardView
extends VBoxContainer

const EMPTY_REPLAY_TEXT := "No replay evidence in this bundle"

@onready var _loading: Label = $LoadingLabel
@onready var _empty: Label = $EmptyStateLabel
@onready var _turn: Label = $MetaRow/TurnLabel
@onready var _weather: Label = $MetaRow/WeatherLabel
@onready var _terrain: Label = $MetaRow/TerrainLabel
@onready var _field_conditions: Label = $MetaRow/FieldConditionsLabel
@onready var _p1_side: Label = $SideConditionsRow/P1SideLabel
@onready var _p2_side: Label = $SideConditionsRow/P2SideLabel
@onready var _p1a_species: Label = $Slots/P1ASpecies
@onready var _p1a_hp: Label = $Slots/P1AHP
@onready var _p1a_status: Label = $Slots/P1AStatus
@onready var _p1b_species: Label = $Slots/P1BSpecies
@onready var _p1b_hp: Label = $Slots/P1BHP
@onready var _p1b_status: Label = $Slots/P1BStatus
@onready var _p2a_species: Label = $Slots/P2ASpecies
@onready var _p2a_hp: Label = $Slots/P2AHP
@onready var _p2a_status: Label = $Slots/P2AStatus
@onready var _p2b_species: Label = $Slots/P2BSpecies
@onready var _p2b_hp: Label = $Slots/P2BHP
@onready var _p2b_status: Label = $Slots/P2BStatus

var _bound: BoardModel = null


func bind(board: BoardModel) -> void:
	_bound = board
	if board == null or not board.has_replay:
		_empty.visible = true
		_empty.text = EMPTY_REPLAY_TEXT
		_clear_slots_and_meta()
		return
	_empty.visible = false
	_empty.text = ""
	# has_replay and not has_recorded_state: blank slots, NO empty-state banner.
	_render(board)


func set_loading(active: bool) -> void:
	_loading.text = "Loading..." if active else ""


func get_slot_species(side: String, slot: String) -> String:
	return _slot_label(side, slot, "species").text


func get_slot_hp_text(side: String, slot: String) -> String:
	return _slot_label(side, slot, "hp").text


func get_weather_text() -> String:
	return _weather.text


func get_terrain_text() -> String:
	return _terrain.text


func get_field_conditions_text() -> String:
	return _field_conditions.text


func get_side_conditions_text(side: String) -> String:
	return _p1_side.text if side == "p1" else _p2_side.text


func get_empty_state_visible() -> bool:
	return _empty.visible


func _clear_slots_and_meta() -> void:
	_turn.text = ""
	_weather.text = ""
	_terrain.text = ""
	_field_conditions.text = ""
	_p1_side.text = ""
	_p2_side.text = ""
	for lbl in [
		_p1a_species, _p1a_hp, _p1a_status, _p1b_species, _p1b_hp, _p1b_status,
		_p2a_species, _p2a_hp, _p2a_status, _p2b_species, _p2b_hp, _p2b_status,
	]:
		lbl.text = ""


func _render(board: BoardModel) -> void:
	_turn.text = "" if board.turn_number == null else "turn %s" % str(board.turn_number)
	_weather.text = "" if board.weather == null else str(board.weather)
	_terrain.text = "" if board.terrain == null else str(board.terrain)
	_field_conditions.text = ", ".join(board.field_conditions)
	_p1_side.text = ", ".join(board.side_conditions["p1"])
	_p2_side.text = ", ".join(board.side_conditions["p2"])
	_write_slot(_p1a_species, _p1a_hp, _p1a_status, board.get_slot("p1", "a"))
	_write_slot(_p1b_species, _p1b_hp, _p1b_status, board.get_slot("p1", "b"))
	_write_slot(_p2a_species, _p2a_hp, _p2a_status, board.get_slot("p2", "a"))
	_write_slot(_p2b_species, _p2b_hp, _p2b_status, board.get_slot("p2", "b"))


func _write_slot(species_lbl: Label, hp_lbl: Label, status_lbl: Label, cell: Dictionary) -> void:
	species_lbl.text = "" if cell["species"] == null else str(cell["species"])
	if cell["hp_current"] == null and cell["hp_maximum"] == null:
		hp_lbl.text = ""
	else:
		hp_lbl.text = "%s/%s" % [
			"?" if cell["hp_current"] == null else str(cell["hp_current"]),
			"?" if cell["hp_maximum"] == null else str(cell["hp_maximum"]),
		]
	status_lbl.text = "" if cell["hp_status"] == null else str(cell["hp_status"])


func _slot_label(side: String, slot: String, kind: String) -> Label:
	# kind: species|hp|status — explicit map only (no dynamic get_node inventing)
	match "%s-%s-%s" % [side, slot, kind]:
		"p1-a-species":
			return _p1a_species
		"p1-a-hp":
			return _p1a_hp
		"p1-a-status":
			return _p1a_status
		"p1-b-species":
			return _p1b_species
		"p1-b-hp":
			return _p1b_hp
		"p1-b-status":
			return _p1b_status
		"p2-a-species":
			return _p2a_species
		"p2-a-hp":
			return _p2a_hp
		"p2-a-status":
			return _p2a_status
		"p2-b-species":
			return _p2b_species
		"p2-b-hp":
			return _p2b_hp
		"p2-b-status":
			return _p2b_status
		_:
			push_error("invalid slot seam %s-%s-%s" % [side, slot, kind])
			return _p1a_species
```

---

## 6. Named tests (binding)

### 6.1 `tests/timeline/test_battle_timeline.gd`

| Test | Assert |
|---|---|
| `test_fixture01_join_order_deterministic` | Build twice; identical kinds + indices + anchors; entry 0 is DECISION before first EVENT |
| `test_fixture01_decision_after_last_event_lt_rpi` | rpi placement invariant |
| `test_fixture04_replay_only_events_only` | All EVENT |
| `test_fixture05_trace_only_decisions_without_replay` | All `DECISION_WITHOUT_REPLAY_EVENT` |
| `test_null_rpi_never_attaches_to_neighbor_event` | Constructed |
| `test_effective_mode_not_declared_alone` | Follows effective trust flags |
| `test_invalid_decision_marked_not_dropped` | Entry present |
| `test_noncontiguous_decision_ids_preserve_row_index` | ids `{2,7}` → row indices 0/1 |
| `test_same_rpi_decisions_stay_ascending` | Two decisions, identical non-null rpi, ids 2 then 7 → timeline order `#2` then `#7` |
| `test_same_event_gap_different_rpi_stay_ascending` | Events pi=4 then pi=20; decisions rpi=5 id=2 and rpi=12 id=7 → both in gap after first event, order `#2` then `#7` |
| `test_nonnull_rpi_inserts_before_null_rpi_tail` | Non-null rpi decision (higher decision_index, inserted later in loop) stays before already-appended null-rpi tail |

### 6.2 `tests/replay/test_replay_presenter.gd`

| Test | Assert |
|---|---|
| `test_fixture01_switch_applies_species_and_hp` | After entry 2: Pikachu 35/35 |
| `test_fixture01_decision_before_first_event_keeps_has_replay` | Entry 0: `has_replay==true`, `has_recorded_state==false`, species null |
| `test_trace_only_board_empty` | fixture-05: `has_replay==false` |
| `test_replay_only_board_from_events` | fixture-04 board updates |
| `test_decision_cursor_does_not_invent_hp` | Decision cursor equals prior event apply-set |
| `test_damage_heal_sethp_update_hp` | Constructed |
| `test_faint_and_status_curestatus` | Constructed |
| `test_switch_replaces_prior_status` | Burned occupant → healthy switch with `hp_status=null` → slot status null (not leftover burn) |
| `test_faint_forces_zero_hp_after_positive` | Positive HP then faint → `hp_fainted=true` and `hp_current=0` |
| `test_unknown_side_is_noop` | `pokemon_side="p3"` switch does not crash; slots unchanged |
| `test_numeric_slot_is_noop` | `pokemon_slot=0` (int) switch does not crash; slots unchanged |
| `test_weather_terrain_vs_trick_room_field_conditions` | Electric Terrain → `terrain`; Trick Room → `field_conditions` only; fieldend removes from correct target |
| `test_side_conditions_start_end` | Constructed sidestart/sideend |
| `test_detailschange_updates_species` | Constructed |
| `test_reverse_navigation_drops_future_state` | switch→damage→status then step back |
| `test_build_board_returns_fresh_model` | Distinct identities |

### 6.3 `tests/timeline/test_timeline_controller.gd`

| Test | Assert |
|---|---|
| `test_step_next_prev_clamped` | Bounds |
| `test_jump_start_end` | 0 / last |
| `test_play_advances_on_timer` | Short wait_time |
| `test_pause_stops_advances` | |
| `test_reset_on_new_replay_clears_cursor` | |
| `test_clear_stops_playback` | |
| `test_selection_changed_emitted_on_select` | |

### 6.4 `tests/workspace/test_app_shell_replay.gd` (C4)

| Test | Assert |
|---|---|
| `test_fixture01_open_builds_timeline_and_board` | entries>0; after select switch entry, Pikachu |
| `test_fixture04_no_decision_entries` | |
| `test_fixture05_no_replay_board_state` | empty-state visible; `has_replay==false` |
| `test_fixture06_refuse_clears_replay` | |
| `test_cancel_clears_replay` | |
| `test_start_load_clears_before_async` | Before completed: empty + Loading + controls disabled |
| `test_bundle_switch_resets_cursor` | 01 → 04: cursor 0, not playing |
| `test_bundle_switch_clears_board_species` | **01 → 05 only**: no Pikachu; empty-state visible |
| `test_selection_updates_board_across_event_boundary` | fixture-01: select **switch entry (2)** → Pikachu present; `select(1)` (prior turn EVENT) → species gone. **Do not** use `jump_end`/`step_prev` (entry 6↔5 share apply-set) |

### 6.5 View suites (C3)

#### `tests/timeline/test_timeline_view.gd`

| Test | Assert |
|---|---|
| `test_bind_event_labels_use_type_turn_move` | |
| `test_bind_decision_labels_use_fachliche_id` | `#2` / `#7` |
| `test_bind_invalid_decision_suffix` | `(invalid)` |
| `test_set_loading_shows_and_clears` | |
| `test_controls_disabled_when_set` | |
| `test_item_selected_calls_controller_select` | Emit/select ItemList index → `controller.get_selected_entry_index()` matches |

#### `tests/replay/test_abstract_board_view.gd`

| Test | Assert |
|---|---|
| `test_bind_shows_species_hp_status` | |
| `test_bind_shows_weather_terrain_field_and_side_conditions` | Trick Room in field conditions text; terrain separate |
| `test_empty_state_only_when_not_has_replay` | `has_replay=false` → banner; `has_replay=true` + `has_recorded_state=false` → banner **hidden** |
| `test_set_loading_shows_and_clears` | |

---

## 7. Tasks (RED → GREEN → commit)

Cwd: `showdownbot_studio/godot/`.
Every commit requires GREEN suite + `git diff --check` clean.
No red commits. No unrelated files.

### Local commands

```powershell
.\tools\verify_engine_pin.ps1
.\tools\run_gdunit_headless.ps1 -a "res://tests/<suite>.gd"
.\tools\run_gdunit_headless.ps1 -a "res://tests/"
```

**Helpers (binding — copy into each test file that needs them; no invented variants):**

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

No new unit JSONL. Workspace tests also call `after_test` free of `AppShell` children exactly as
`tests/workspace/test_app_shell_smoke.gd`.

---

### Task C0 — Timeline kinds + sealed ReplayDTO + builder

**Files:**
- Create: `src/timeline/timeline_entry_kind.gd`
- Create: `src/timeline/timeline_entry_dto.gd`
- Create: `src/timeline/battle_timeline.gd`
- Create: `src/replay/replay_dto.gd`
- Create: `tests/timeline/test_battle_timeline.gd`

- [ ] **Step 1: Write failing tests** (representative + all §6.1 names):

```gdscript
extends GdUnitTestSuite

const _FIXTURES_ROOT := "res://../fixtures/viewer-v0"

func _fixture_bundle(rel: String) -> BundleDTO:
	var path := ProjectSettings.globalize_path(_FIXTURES_ROOT.path_join(rel))
	var result: ValidationResult = BundleValidator.validate_dir(path)
	assert_object(result.bundle).is_not_null()
	return result.bundle


func test_fixture01_join_order_deterministic() -> void:
	var bundle := _fixture_bundle("bundles/fixture-01")
	var a: ReplayDTO = BattleTimeline.build(bundle)
	var b: ReplayDTO = BattleTimeline.build(bundle)
	assert_int(a.entries.size()).is_equal(b.entries.size())
	assert_str(a.entries[0].kind).is_equal(TimelineEntryKind.DECISION)
	assert_int(a.entries[0].decision_row_index).is_equal(0)
	assert_str(a.entries[1].kind).is_equal(TimelineEntryKind.EVENT)
	assert_int(a.entries[2].event_index).is_equal(1)  # switch
	for i in range(a.entries.size()):
		assert_str(a.entries[i].kind).is_equal(b.entries[i].kind)
		assert_int(a.entries[i].event_index).is_equal(b.entries[i].event_index)
		assert_int(a.entries[i].decision_row_index).is_equal(b.entries[i].decision_row_index)


func test_noncontiguous_decision_ids_preserve_row_index() -> void:
	var bundle := _make_minimal_bundle_with_decisions([
		_make_decision(2, 10, true),
		_make_decision(7, 20, true),
	], [
		_make_event(0, "turn", {"amount": 1}),
		_make_event(15, "turn", {"amount": 2}),
	])
	var replay: ReplayDTO = BattleTimeline.build(bundle)
	var decision_entries: Array = []
	for e in replay.entries:
		if e.kind == TimelineEntryKind.DECISION:
			decision_entries.append(e)
	assert_int(decision_entries.size()).is_equal(2)
	assert_int(decision_entries[0].decision_row_index).is_equal(0)
	assert_int(decision_entries[1].decision_row_index).is_equal(1)
	assert_int(bundle.decisions[decision_entries[0].decision_row_index].decision_index).is_equal(2)
	assert_int(bundle.decisions[decision_entries[1].decision_row_index].decision_index).is_equal(7)


func _decision_ids_in_timeline(replay: ReplayDTO, bundle: BundleDTO) -> Array:
	var ids: Array = []
	for e in replay.entries:
		if e.kind == TimelineEntryKind.DECISION or e.kind == TimelineEntryKind.DECISION_WITHOUT_REPLAY_EVENT:
			ids.append(bundle.decisions[e.decision_row_index].decision_index)
	return ids


func test_same_rpi_decisions_stay_ascending() -> void:
	var bundle := _make_minimal_bundle_with_decisions([
		_make_decision(2, 10, true),
		_make_decision(7, 10, true),
	], [
		_make_event(4, "turn", {"amount": 1}),
		_make_event(20, "turn", {"amount": 2}),
	])
	var replay := BattleTimeline.build(bundle)
	assert_that(_decision_ids_in_timeline(replay, bundle)).is_equal([2, 7])


func test_same_event_gap_different_rpi_stay_ascending() -> void:
	var bundle := _make_minimal_bundle_with_decisions([
		_make_decision(2, 5, true),
		_make_decision(7, 12, true),
	], [
		_make_event(4, "turn", {"amount": 1}),
		_make_event(20, "turn", {"amount": 2}),
	])
	var replay := BattleTimeline.build(bundle)
	# Both land after event pi=4 and before event pi=20; ascending ids preserved.
	assert_that(_decision_ids_in_timeline(replay, bundle)).is_equal([2, 7])
	assert_str(replay.entries[0].kind).is_equal(TimelineEntryKind.EVENT)
	assert_str(replay.entries[1].kind).is_equal(TimelineEntryKind.DECISION)
	assert_str(replay.entries[2].kind).is_equal(TimelineEntryKind.DECISION)
	assert_str(replay.entries[3].kind).is_equal(TimelineEntryKind.EVENT)


func test_nonnull_rpi_inserts_before_null_rpi_tail() -> void:
	# Process ascending: id=2 null-rpi first (tail), then id=7 non-null rpi.
	# Non-null must still insert before the null-rpi tail, not after it.
	var bundle := _make_minimal_bundle_with_decisions([
		_make_decision(2, null, true),
		_make_decision(7, 5, true),
	], [
		_make_event(4, "turn", {"amount": 1}),
		_make_event(20, "turn", {"amount": 2}),
	])
	var replay := BattleTimeline.build(bundle)
	var kinds: Array = []
	var ids: Array = []
	for e in replay.entries:
		kinds.append(e.kind)
		if e.kind != TimelineEntryKind.EVENT:
			ids.append(bundle.decisions[e.decision_row_index].decision_index)
	assert_that(ids).is_equal([7, 2])
	assert_str(kinds[kinds.size() - 1]).is_equal(TimelineEntryKind.DECISION_WITHOUT_REPLAY_EVENT)
```

Helpers `_make_event` / `_make_decision` / `_make_minimal_bundle_with_decisions` live in the
same test file; they assign flattened `BattleEventDTO` / `DecisionRowDTO` fields and call `seal()`.

- [ ] **Step 2: RED**

```powershell
.\tools\run_gdunit_headless.ps1 -a "res://tests/timeline/test_battle_timeline.gd"
```

Expected: missing `BattleTimeline` / `ReplayDTO` / `decision_row_index`.

- [ ] **Step 3: Implement** §4.1 kinds, **exact §4.2 `TimelineEntryDTO` body**, **exact §4.3 `ReplayDTO` body**, and join §0.4 / `_insert_decision` below. Do not invent alternate seal/setter patterns.

```gdscript
class_name BattleTimeline
extends RefCounted

static func build(bundle: BundleDTO) -> ReplayDTO:
	var replay := ReplayDTO.new()
	replay.declared_mode = bundle.declared_mode
	replay.effective_mode = bundle.effective_mode
	replay.replay_trusted = bundle.replay_trusted
	replay.trace_trusted = bundle.trace_trusted
	var entries: Array = []
	if bundle.replay_trusted:
		for i in range(bundle.battle_events.size()):
			var e := TimelineEntryDTO.new()
			e.kind = TimelineEntryKind.EVENT
			e.event_index = i
			e.decision_row_index = -1
			e.protocol_anchor = bundle.battle_events[i].protocol_index
			entries.append(e)
	if bundle.trace_trusted:
		var order: Array = []
		for i in range(bundle.decisions.size()):
			order.append(i)
		order.sort_custom(func(a, b):
			return bundle.decisions[a].decision_index < bundle.decisions[b].decision_index
		)
		for row_i in order:
			_insert_decision(entries, bundle, int(row_i))
	for e in entries:
		e.seal()
	replay.entries = entries
	replay.seal()
	return replay


static func _insert_decision(entries: Array, bundle: BundleDTO, decision_row_index: int) -> void:
	var d: DecisionRowDTO = bundle.decisions[decision_row_index]
	var entry := TimelineEntryDTO.new()
	entry.event_index = -1
	entry.decision_row_index = decision_row_index
	entry.protocol_anchor = d.request_protocol_index
	if d.request_protocol_index == null:
		entry.kind = TimelineEntryKind.DECISION_WITHOUT_REPLAY_EVENT
		entries.append(entry)
		return
	entry.kind = TimelineEntryKind.DECISION
	var rpi: int = int(d.request_protocol_index)
	var insert_at := 0
	for i in range(entries.size()):
		var existing: TimelineEntryDTO = entries[i]
		if existing.kind != TimelineEntryKind.EVENT:
			continue
		if int(existing.protocol_anchor) < rpi:
			insert_at = i + 1
	# Keep ascending decision_index inside the same event-gap: advance past
	# DECISIONs already placed here; stop before next EVENT or null-rpi tail.
	while insert_at < entries.size():
		var at: TimelineEntryDTO = entries[insert_at]
		if at.kind == TimelineEntryKind.EVENT:
			break
		if at.kind == TimelineEntryKind.DECISION_WITHOUT_REPLAY_EVENT:
			break
		if at.kind == TimelineEntryKind.DECISION:
			insert_at += 1
			continue
		break
	entries.insert(insert_at, entry)
```

- [ ] **Step 4: GREEN** — same command PASS.
- [ ] **Step 5: Commit**

```powershell
git add src/timeline/timeline_entry_kind.gd src/timeline/timeline_entry_dto.gd `
  src/timeline/battle_timeline.gd src/replay/replay_dto.gd `
  tests/timeline/test_battle_timeline.gd
git commit -m "feat(studio): deterministic BattleTimeline and sealed ReplayDTO"
```

---

### Task C1 — BoardModel + ReplayPresenter

**Files:**
- Create: `src/replay/board_model.gd` (exact §4.4)
- Create: `src/replay/replay_presenter.gd` (exact §4.5)
- Create: `tests/replay/test_replay_presenter.gd`

- [ ] **Step 1: Write failing tests** (all §6.2). Critical bodies:

```gdscript
func test_fixture01_decision_before_first_event_keeps_has_replay() -> void:
	var bundle := _fixture_bundle("bundles/fixture-01")
	var replay := BattleTimeline.build(bundle)
	var board := ReplayPresenter.build_board(bundle, replay, 0)
	assert_bool(board.has_replay).is_true()
	assert_bool(board.has_recorded_state).is_false()
	assert_object(board.get_slot("p1", "a")["species"]).is_null()


func test_weather_terrain_vs_trick_room_field_conditions() -> void:
	var events: Array = [
		_make_event(1, "fieldstart", {"value": "Electric Terrain"}),
		_make_event(2, "fieldstart", {"value": "Trick Room"}),
		_make_event(3, "fieldend", {"value": "Trick Room"}),
		_make_event(4, "fieldend", {"value": "Electric Terrain"}),
	]
	var bundle := _make_replay_only_bundle(events)
	var replay := BattleTimeline.build(bundle)
	var after_both := ReplayPresenter.build_board(bundle, replay, 1)
	assert_str(str(after_both.terrain)).is_equal("Electric Terrain")
	assert_int(after_both.field_conditions.size()).is_equal(1)
	assert_str(after_both.field_conditions[0]).is_equal("Trick Room")
	var after_tr_end := ReplayPresenter.build_board(bundle, replay, 2)
	assert_str(str(after_tr_end.terrain)).is_equal("Electric Terrain")
	assert_int(after_tr_end.field_conditions.size()).is_equal(0)
	var after_terrain_end := ReplayPresenter.build_board(bundle, replay, 3)
	assert_object(after_terrain_end.terrain).is_null()
	assert_int(after_terrain_end.field_conditions.size()).is_equal(0)


func test_reverse_navigation_drops_future_state() -> void:
	var events: Array = [
		_make_event(1, "switch", {
			"pokemon_side": "p1", "pokemon_slot": "a", "pokemon_species": "Pikachu",
			"hp_current": 35, "hp_maximum": 35, "hp_fainted": false,
		}),
		_make_event(2, "damage", {
			"pokemon_side": "p1", "pokemon_slot": "a",
			"hp_current": 20, "hp_maximum": 35, "hp_fainted": false,
		}),
		_make_event(3, "status", {
			"pokemon_side": "p1", "pokemon_slot": "a", "details": "brn",
		}),
	]
	var bundle := _make_replay_only_bundle(events)
	var replay := BattleTimeline.build(bundle)
	var at_end := ReplayPresenter.build_board(bundle, replay, 2)
	assert_int(int(at_end.get_slot("p1", "a")["hp_current"])).is_equal(20)
	assert_str(str(at_end.get_slot("p1", "a")["hp_status"])).is_equal("brn")
	var at_switch := ReplayPresenter.build_board(bundle, replay, 0)
	assert_int(int(at_switch.get_slot("p1", "a")["hp_current"])).is_equal(35)
	assert_object(at_switch.get_slot("p1", "a")["hp_status"]).is_null()


func test_switch_replaces_prior_status() -> void:
	var events: Array = [
		_make_event(1, "switch", {
			"pokemon_side": "p1", "pokemon_slot": "a", "pokemon_species": "BurnedMon",
			"hp_current": 100, "hp_maximum": 100, "hp_fainted": false, "hp_status": "brn",
		}),
		_make_event(2, "switch", {
			"pokemon_side": "p1", "pokemon_slot": "a", "pokemon_species": "HealthyMon",
			"hp_current": 80, "hp_maximum": 80, "hp_fainted": false, "hp_status": null,
		}),
	]
	var bundle := _make_replay_only_bundle(events)
	var replay := BattleTimeline.build(bundle)
	var board := ReplayPresenter.build_board(bundle, replay, 1)
	assert_str(str(board.get_slot("p1", "a")["species"])).is_equal("HealthyMon")
	assert_object(board.get_slot("p1", "a")["hp_status"]).is_null()


func test_faint_forces_zero_hp_after_positive() -> void:
	var events: Array = [
		_make_event(1, "switch", {
			"pokemon_side": "p1", "pokemon_slot": "a", "pokemon_species": "Pikachu",
			"hp_current": 35, "hp_maximum": 35, "hp_fainted": false,
		}),
		_make_event(2, "damage", {
			"pokemon_side": "p1", "pokemon_slot": "a",
			"hp_current": 20, "hp_maximum": 35, "hp_fainted": false,
		}),
		_make_event(3, "faint", {"pokemon_side": "p1", "pokemon_slot": "a"}),
	]
	var bundle := _make_replay_only_bundle(events)
	var replay := BattleTimeline.build(bundle)
	var board := ReplayPresenter.build_board(bundle, replay, 2)
	assert_bool(bool(board.get_slot("p1", "a")["hp_fainted"])).is_true()
	assert_int(int(board.get_slot("p1", "a")["hp_current"])).is_equal(0)


func test_unknown_side_is_noop() -> void:
	var events: Array = [
		_make_event(1, "switch", {
			"pokemon_side": "p3", "pokemon_slot": "a", "pokemon_species": "X",
			"hp_current": 10, "hp_maximum": 10, "hp_fainted": false,
		}),
	]
	var bundle := _make_replay_only_bundle(events)
	var replay := BattleTimeline.build(bundle)
	var board := ReplayPresenter.build_board(bundle, replay, 0)
	assert_object(board.get_slot("p1", "a")["species"]).is_null()
	assert_object(board.get_slot("p2", "a")["species"]).is_null()


func test_numeric_slot_is_noop() -> void:
	var events: Array = [
		_make_event(1, "switch", {
			"pokemon_side": "p1", "pokemon_slot": 0, "pokemon_species": "X",
			"hp_current": 10, "hp_maximum": 10, "hp_fainted": false,
		}),
	]
	var bundle := _make_replay_only_bundle(events)
	var replay := BattleTimeline.build(bundle)
	var board := ReplayPresenter.build_board(bundle, replay, 0)
	assert_object(board.get_slot("p1", "a")["species"]).is_null()
	assert_object(board.get_slot("p1", "b")["species"]).is_null()
```


- [ ] **Step 2: RED**

```powershell
.\tools\run_gdunit_headless.ps1 -a "res://tests/replay/test_replay_presenter.gd"
```

- [ ] **Step 3: Implement** copy §4.4 + §4.5 into the two source files (no invented alternate maps).
- [ ] **Step 4: GREEN**.
- [ ] **Step 5: Commit** `feat(studio): ReplayPresenter applies recorded events to BoardModel`

---

### Task C2 — TimelineController

**Files:**
- Create: `src/timeline/timeline_controller.gd` (exact §4.6)
- Create: `tests/timeline/test_timeline_controller.gd`

- [ ] **Step 1: Write** all §6.3 tests. Playback test uses `set_timer_wait_time(0.01)` + await frames.
- [ ] **Step 2: RED**

```powershell
.\tools\run_gdunit_headless.ps1 -a "res://tests/timeline/test_timeline_controller.gd"
```

- [ ] **Step 3: Implement** §4.6 skeleton.
- [ ] **Step 4: GREEN**.
- [ ] **Step 5: Commit** `feat(studio): TimelineController cursor and playback timer`

---

### Task C3 — TimelineView + AbstractBoardView (GREEN required)

**Files:**
- Create: `src/timeline/timeline_view.gd` + `timeline_view.tscn` (§3.1 + §5.1)
- Create: `src/replay/abstract_board_view.gd` + `abstract_board_view.tscn` (§3.1 + §5.2)
- Create: `tests/timeline/test_timeline_view.gd`
- Create: `tests/replay/test_abstract_board_view.gd`

Do **not** wire AppShell/ReplayWorkspace here.

- [ ] **Step 1: Write** all §6.5 tests. Critical empty-state test:

```gdscript
func test_empty_state_only_when_not_has_replay() -> void:
	var view: AbstractBoardView = preload("res://src/replay/abstract_board_view.tscn").instantiate()
	add_child(view)
	var no_replay := BoardModel.new()
	no_replay.has_replay = false
	view.bind(no_replay)
	assert_bool(view.get_empty_state_visible()).is_true()

	var trusted_empty := BoardModel.new()
	trusted_empty.has_replay = true
	trusted_empty.has_recorded_state = false
	view.bind(trusted_empty)
	assert_bool(view.get_empty_state_visible()).is_false()
```

Controller injection in timeline tests:

```gdscript
var controller := TimelineController.new()
add_child(controller)
view.set_controller(controller)  # binding — not @export


func test_item_selected_calls_controller_select() -> void:
	var view: TimelineView = preload("res://src/timeline/timeline_view.tscn").instantiate()
	add_child(view)
	var controller := TimelineController.new()
	add_child(controller)
	view.set_controller(controller)
	var bundle := _make_replay_only_bundle([
		_make_event(1, "turn", {"amount": 1}),
		_make_event(2, "turn", {"amount": 2}),
		_make_event(3, "turn", {"amount": 3}),
	])
	var replay := BattleTimeline.build(bundle)
	controller.reset(replay, bundle)
	view.bind(replay, bundle)
	view.get_node("EntryList").select(2)
	view.get_node("EntryList").item_selected.emit(2)
	await await_idle_frame()
	assert_int(controller.get_selected_entry_index()).is_equal(2)
```

- [ ] **Step 2: RED**

```powershell
.\tools\run_gdunit_headless.ps1 -a "res://tests/timeline/test_timeline_view.gd"
.\tools\run_gdunit_headless.ps1 -a "res://tests/replay/test_abstract_board_view.gd"
```

- [ ] **Step 3: Implement** scenes + scripts per §3.1 / §5.1 / §5.2. Use
  `set_controller(controller)` only.
- [ ] **Step 4: GREEN** — both commands PASS. **No commit while red.**
- [ ] **Step 5: Commit** `feat(studio): abstract board and bounded timeline views`

---

### Task C4 — ReplayWorkspace + AppShell wiring

**Files:**
- Create: `src/replay/replay_workspace.gd` + `replay_workspace.tscn` (§3.1 + §4.7)
- Modify: `src/workspace/app_shell.gd`, `app_shell.tscn`
- Create: `tests/workspace/test_app_shell_replay.gd`

- [ ] **Step 1: Write** all §6.4 tests. Binding selection test (event boundary):

```gdscript
func test_selection_updates_board_across_event_boundary() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	var ws: ReplayWorkspace = shell.get_replay_workspace()
	var ctl := ws.get_timeline_controller()
	ctl.select(2)  # switch EVENT — Pikachu
	await await_idle_frame()
	assert_str(ws.get_board_view().get_slot_species("p1", "a")).is_equal("Pikachu")
	ctl.select(1)  # prior turn EVENT — no switch yet
	await await_idle_frame()
	assert_str(ws.get_board_view().get_slot_species("p1", "a")).is_equal("")
```

Board leftover proof (**01 → 05 only**):

```gdscript
func test_bundle_switch_clears_board_species() -> void:
	var shell: AppShell = await _spawn_shell_ready()
	shell.open_bundle_path(_fixture_path("bundles/fixture-01"))
	await _await_shell_settled(shell)
	shell.get_replay_workspace().get_timeline_controller().select(2)
	await await_idle_frame()
	assert_str(shell.get_replay_workspace().get_board_view().get_slot_species("p1", "a")).is_equal("Pikachu")
	shell.open_bundle_path(_fixture_path("bundles/fixture-05"))
	await _await_shell_settled(shell)
	assert_bool(shell.get_replay_workspace().get_board_view().get_empty_state_visible()).is_true()
	assert_str(shell.get_replay_workspace().get_board_view().get_slot_species("p1", "a")).is_equal("")
```

- [ ] **Step 2: RED**

```powershell
.\tools\run_gdunit_headless.ps1 -a "res://tests/workspace/test_app_shell_replay.gd"
```

- [ ] **Step 3: Implement** §4.7 workspace + AppShell hooks:

```gdscript
# app_shell.gd additions
@onready var _replay_workspace: ReplayWorkspace = $VBox/ReplayWorkspace

func get_replay_workspace() -> ReplayWorkspace:
	return _replay_workspace

func _start_load(path: String) -> void:
	_current_bundle = null
	_current_refuse = null
	_replay_workspace.clear()
	_replay_workspace.set_loading(true)
	_set_status("Loading...")
	_loader.load_async(path)

func _on_completed(bundle: BundleDTO) -> void:
	_current_bundle = bundle
	_current_refuse = null
	var replay: ReplayDTO = BattleTimeline.build(bundle)
	_replay_workspace.reset(replay, bundle)
	_set_status(_format_loaded_status(bundle))

func _on_refused(diagnostic: RefuseDiagnostic) -> void:
	_current_bundle = null
	_current_refuse = diagnostic
	_replay_workspace.clear()
	_set_status("Refused: %s" % diagnostic.reason)

func _on_cancelled() -> void:
	_current_bundle = null
	_current_refuse = null
	_replay_workspace.clear()
	_set_status("Load cancelled")
```

- [ ] **Step 4: GREEN**.
- [ ] **Step 5: Commit** `feat(studio): wire replay timeline into AppShell loader lifecycle`

---

### Task C5 — Full regression + pin

- [ ] **Step 1:**

```powershell
.\tools\verify_engine_pin.ps1
.\tools\run_gdunit_headless.ps1 -a "res://tests/"
```

Expected: pin PASS; Plan B + Plan C green; 2 privilege skips remain skips.

- [ ] **Step 2:** `git diff --check` clean.
- [ ] **Step 3: Commit** only if a leftover fix was required:
  `test(studio): Plan C replay/timeline regression green`

---

## 8. Acceptance (Plan C done)

- Fixture **01**: join per §0.4 table; entry 0 decision keeps `has_replay` without empty-state banner;
  switch/HP via recorded events; reverse rebuild drops future state.
- Fixture **04**: events only; cursor reset via 01→04.
- Fixture **05**: `has_replay=false` + empty-state; board leftover cleared via **01→05**.
- Workspace selection crosses an **EVENT** boundary (switch→prior turn), not decision/move pair.
- Terrain whitelist vs Trick Room `field_conditions` covered by constructed tests.
- `_start_load` clears/disables before `load_async`.
- No worker references from UI; sealed Plan-B DTOs remain byte authority.
- Pin PASS + full gdUnit green (privilege skips only).

---

## 9. Visual input

Follow [`../design/viewer-v0-mockups/README.md`](../design/viewer-v0-mockups/README.md): abstract
sprite-free board; offline fonts / platform shortcut labels → Plan E.

---

## 10. Self-review checklist (this Rev. 5)

- [x] `has_replay = replay.replay_trusted`; `has_recorded_state` separate; entry-0 case covered
- [x] Terrain whitelist vs `field_conditions`; Trick Room tests
- [x] Workspace selection test crosses EVENT boundary (not jump_end/step_prev)
- [x] `replace_slot_from_switch` full overwrite; faint forces `hp_current=0`
- [x] Unknown side / numeric slot fail-soft; ItemList → `controller.select`
- [x] Same-gap decisions stay ascending; non-null before null-rpi tail
- [x] Full `TimelineEntryDTO` + `ReplayDTO` GDScript bodies (seal + read-only entries)
- [x] No `...` / stub comments in binding skeletons; helpers fully defined
- [x] `recompute_has_recorded_state` checks all five slot fields (incl. `hp_fainted=false`)
- [x] `set_controller` only; board leftover **01→05 only**
- [x] Join §11.3.3; index separation; C3 GREEN before commit; C4 separate RED
- [x] Status set to **APPROVED** (Rev. 5); still does **not** authorize code without go-ahead

---

## 11. Stale status documents (report only — not edited)

| Location | Stale claim |
|---|---|
| `showdownbot_studio/docs/plans/README.md` | Plan B blocked / Next merge Plan A |
| `showdownbot_studio/README.md` | Plans B–F DRAFT; Next Plan A/B review |
| Plan B gate lines | Coding blocked on PR #41 (historical) |
| `docs/ROADMAP.md` / `docs/PROJECT_INDEX.md` | No Viewer v0 A/B merge rows at tip |

---

## 12. Rev. 3 changelog (prior review — retained)

| Finding | Resolution |
|---|---|
| P1 `has_replay` vs empty apply-set | `has_replay = replay_trusted`; add `has_recorded_state`; empty-state only when `not has_replay` |
| P1 fieldstart→terrain | Known terrains only; else `field_conditions`; fieldend targeted; Trick Room tests |
| P1 workspace board-change test | Select switch entry 2 → turn entry 1; assert Pikachu disappears |
| P1 non-executable steps | §3.1 scene paths; §4.4–4.7 / §5 APIs; per-task GDScript skeletons |
| P2 leftover choices | `set_controller(controller)`; board switch **01→05 only** |

## 13. Rev. 4 changelog (prior review — retained)

| Finding | Resolution |
|---|---|
| P1 switch keeps prior status | `replace_slot_from_switch` full overwrite incl. null `hp_status`; regression test |
| P1 faint leaves positive HP | `set_slot_fainted` always sets `hp_current=0`; test after positive HP |
| P1 unknown side/slot crash | `_pokemon_side_slot` / side events accept only p1/p2 × a/b; else no-op + tests |
| P1 ItemList not wired | `item_selected` → `controller.select`; view test |
| P2 skeleton placeholders | Full AbstractBoardView, `_insert_decision`, all test helpers; no `...` stubs |
| Consistency | `recompute_has_recorded_state` treats any non-null of five slot fields as recorded |

## 14. Rev. 5 changelog (review response)

| Finding | Resolution |
|---|---|
| P1 same-gap decisions reversed | `_insert_decision` advances past DECISIONs in the gap; stop before next EVENT / null-rpi tail; three order tests |
| P2 missing DTO skeletons | Full §4.2 `TimelineEntryDTO` + §4.3 `ReplayDTO` bodies with `_sealed`, setters, `seal()`, entries `make_read_only()` |
