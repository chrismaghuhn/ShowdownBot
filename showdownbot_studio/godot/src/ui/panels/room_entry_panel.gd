class_name RoomEntryPanel
extends VBoxContainer

## Direct room-ID/URL entry, no fallback room, no room browser (spec section 6.1, section 3.2).
## Holds a SpectatorRoomGatewayPort (Task 27/28), injected via configure() -- never a direct
## reference to protocol/'s encoder or net/'s transport, and never the concrete SpectatorRoomGateway
## type either (so a test fake can satisfy this without the gateway's own dependencies). There is
## no join_requested signal: this panel calls the gateway directly from its own button handlers.
##
## M1 hardening (owner review of PR #94, P1 item 2, 2026-07-26): this panel used to have only
## "Watch" -- no Leave action, no way to dismiss a CLOSED room (a successful join was a one-shot
## dead end), and none of the RoomState table's user-visible states or local send-failure text was
## ever rendered. Fixed by also holding an optional RoomStateMachine (protocol/) reference: it is
## used ONLY for its read-only getters (get_state()/get_room_id()/get_last_error_reason()) and for
## dismiss_closed_room(), a pure local transition with no network side effect -- unlike join()/
## leave(), which only ever reach the wire through the gateway, this never calls send_raw_text() or
## ProtocolCommandEncoder. configure() is the ONE wiring call for both dependencies: it stores the
## RoomStateMachine reference and subscribes this panel to its state_changed signal in the same
## place, so there is exactly one place that ever wires RoomState visibility into this panel, never
## a second path.
##
## Layout fix (owner review of the M1 hardening lifecycle-UI commit, PR #96, 2026-07-26, second
## pass, P1 finding 1): the six controls used to be direct children of a plain Control with
## layout_mode = 0 and no offsets/anchors -- they all sat at the same origin and overlapped, so
## real clicks were unreliable even though the *_for_test helpers (which called the private
## handler directly) could never observe it. The root is now a VBoxContainer (matching
## replay/ReplayWorkspace's own idiom: a Container-typed root with layout_mode = 2 children,
## rather than manual per-node anchors/offsets), with a nested HBoxContainer for the three
## buttons -- Godot's Container types give every child its own non-overlapping rect automatically,
## and each button/the input carry a sensible custom_minimum_size so nothing collapses to zero
## width at a small window size (MASTER_SPEC section 5).

@onready var _input: LineEdit = $RoomIdInput
@onready var _error_label: Label = $ErrorLabel
@onready var _status_label: Label = $StatusLabel
@onready var _join_button: Button = $ButtonsRow/JoinButton
@onready var _leave_button: Button = $ButtonsRow/LeaveButton
@onready var _dismiss_button: Button = $ButtonsRow/DismissButton

var _gateway: SpectatorRoomGatewayPort
var _room_state_machine: RoomStateMachine


func _ready() -> void:
	_join_button.pressed.connect(_on_join_pressed)
	_leave_button.pressed.connect(_on_leave_pressed)
	_dismiss_button.pressed.connect(_on_dismiss_pressed)
	_leave_button.disabled = true
	_dismiss_button.disabled = true


## Sole wiring call for both dependencies (see class doc). room_state_machine is optional so
## existing single-argument call sites (and tests exercising only the write path) keep working
## unchanged; production (LiveClientWorkspace._wire_transport()) always passes both.
func configure(gateway: SpectatorRoomGatewayPort, room_state_machine: RoomStateMachine = null) -> void:
	_gateway = gateway
	_room_state_machine = room_state_machine
	if _room_state_machine != null:
		_room_state_machine.state_changed.connect(_on_room_state_changed)
		_on_room_state_changed(_room_state_machine.get_state(), _room_state_machine.get_state())


static func extract_room_id(raw_input: String) -> String:
	var trimmed := raw_input.strip_edges()
	if trimmed.is_empty():
		return ""
	if not (trimmed.begins_with("http://") or trimmed.begins_with("https://")):
		return trimmed
	var without_trailing_slash := trimmed.rstrip("/")
	var segments := without_trailing_slash.split("/")
	return segments[segments.size() - 1]


func _on_join_pressed() -> void:
	var room_id := extract_room_id(_input.text)
	if room_id.is_empty():
		_error_label.text = "Enter a battle room ID or URL"
		return
	_error_label.text = ""
	_gateway.join(RoomJoinIntent.new(room_id))


func _on_leave_pressed() -> void:
	_gateway.leave()


## Pure local reset (RoomStateMachine.dismiss_closed_room(), CLOSED -> NOT_JOINED): the room
## already closed server-side, so no network command is ever sent for this. Same pure-transition
## category as SpectatorRoomGateway's own request_join()/request_leave() calls -- never protocol
## encoding, never the transport -- so calling it directly here (not through the gateway) does not
## reintroduce a second encoder/transport path.
func _on_dismiss_pressed() -> void:
	if _room_state_machine != null:
		_room_state_machine.dismiss_closed_room()


func _on_room_state_changed(old_state: RoomStateMachine.State, new_state: RoomStateMachine.State) -> void:
	_join_button.disabled = new_state != RoomStateMachine.State.NOT_JOINED
	_leave_button.disabled = new_state != RoomStateMachine.State.ACTIVE
	_dismiss_button.disabled = new_state != RoomStateMachine.State.CLOSED
	_status_label.text = _describe_state(new_state)
	if _is_local_error_transition(old_state, new_state):
		_error_label.text = UntrustedTextSanitizer.sanitize(_room_state_machine.get_last_error_reason())
	else:
		_error_label.text = ""


func _describe_state(state: RoomStateMachine.State) -> String:
	match state:
		RoomStateMachine.State.NOT_JOINED:
			return "Not watching"
		RoomStateMachine.State.JOINING:
			return "Joining..."
		RoomStateMachine.State.ACTIVE:
			return "Watching " + _room_state_machine.get_room_id()
		RoomStateMachine.State.LEAVING:
			return "Leaving..."
		RoomStateMachine.State.CLOSED:
			return "Room closed"
		_:
			return ""


## Both JOINING -> NOT_JOINED (server join_rejected() OR local join_send_failed() -- both set
## RoomStateMachine.get_last_error_reason() before emitting state_changed) and LEAVING -> ACTIVE
## (local leave_send_failed() only -- the only transition that ever lands on ACTIVE from LEAVING)
## are the error-bearing transitions per docs/architecture/LIVE_STATE_MACHINES.md's RoomState
## table. Every other transition clears any stale error text.
func _is_local_error_transition(old_state: RoomStateMachine.State, new_state: RoomStateMachine.State) -> bool:
	if old_state == RoomStateMachine.State.JOINING and new_state == RoomStateMachine.State.NOT_JOINED:
		return true
	if old_state == RoomStateMachine.State.LEAVING and new_state == RoomStateMachine.State.ACTIVE:
		return true
	return false


func on_join_rejected(server_error_text: String) -> void:
	# Untrusted server content: rendered as plain Label text, sanitized before display.
	# Retained as a directly callable render primitive for unit tests
	# (test_room_entry_panel.gd); production code no longer calls this directly -- the
	# RoomStateMachine.state_changed subscription above (wired once, in configure()) now covers
	# this case uniformly with join_send_failed's, since both set get_last_error_reason() before
	# the same JOINING -> NOT_JOINED transition fires.
	_error_label.text = UntrustedTextSanitizer.sanitize(server_error_text)


func get_error_text() -> String:
	return _error_label.text


func get_status_text() -> String:
	return _status_label.text


func is_join_enabled_for_test() -> bool:
	return not _join_button.disabled


func is_leave_enabled_for_test() -> bool:
	return not _leave_button.disabled


func is_dismiss_enabled_for_test() -> bool:
	return not _dismiss_button.disabled


func set_input_text_for_test(text: String) -> void:
	_input.text = text


## Global rects (not get_rect(), which is parent-local): JoinButton/LeaveButton/DismissButton
## live one nesting level deeper (under ButtonsRow) than RoomIdInput, so their LOCAL rects are
## not directly comparable across that boundary -- only global position proves real, absolute
## non-overlap across the whole panel.
func get_room_id_input_rect_for_test() -> Rect2:
	return _input.get_global_rect()


func get_join_button_rect_for_test() -> Rect2:
	return _join_button.get_global_rect()


func get_leave_button_rect_for_test() -> Rect2:
	return _leave_button.get_global_rect()


func get_dismiss_button_rect_for_test() -> Rect2:
	return _dismiss_button.get_global_rect()


## These three now drive the REAL Button node's own `pressed` signal (owner review of the M1
## hardening lifecycle-UI commit, PR #96, 2026-07-26, second pass, P1 finding 1) instead of
## calling the private handler directly -- that is the regression guard for the layout-overlap
## class of defect: it proves the button exists at its expected path and is actually wired to
## `_ready()`'s `.pressed.connect(...)` call, not just that the handler function works in
## isolation. `disabled` does not block a manually emitted signal (only real input dispatch), so
## these still exercise the handler regardless of the button's current enabled state -- unchanged
## behavior from before this fix.
func press_watch_for_test() -> void:
	_join_button.pressed.emit()


func press_leave_for_test() -> void:
	_leave_button.pressed.emit()


func press_dismiss_for_test() -> void:
	_dismiss_button.pressed.emit()
