class_name LiveClientWorkspace
extends VBoxContainer

## Connection + Spectator areas (spec section 4.6). Holds no derived battle state itself
## (battle/LiveBattleProjection owns that); composes modules and routes already-published values
## only. Room join/leave never reaches net/'s transport except through SpectatorRoomGateway.
##
## Layout fix (owner review, 2026-07-26, third pass, P1): the root used to be a bare Control with
## all five children at layout_mode = 1 and no anchors/offsets -- a geometry probe over the real
## instantiated scene found RoomEntryPanel with a real size (from its own earlier internal
## container fix) but ConnectionStatusPanel/BattleBoardPanel/LiveBattleLogPanel all reporting
## 0x0, and ConnectButton overlapping the room panel. The root is now a VBoxContainer (same idiom
## as RoomEntryPanel's own fix and replay/ReplayWorkspace: a Container-typed root with
## layout_mode = 2 children), arranged as a spectator layout: a top row (Connect + room entry +
## connection status) and a split body below it (board and log side by side). Each panel that has
## no real minimum size of its own (its own root is a plain Control, which never aggregates a
## child's minimum size the way a Container does) carries an explicit custom_minimum_size here at
## the instance point, so nothing collapses to zero and the HSplitContainer has sane proportions.

const SHOWDOWN_WEBSOCKET_URL := "wss://sim3.psim.us/showdown/websocket"

@onready var _room_entry_panel: RoomEntryPanel = $TopRow/RoomEntryPanel
@onready var _connection_status_panel: ConnectionStatusPanel = $TopRow/ConnectionStatusPanel
@onready var _battle_board_panel: BattleBoardPanel = $BodySplit/BattleBoardPanel
@onready var _live_battle_log_panel: LiveBattleLogPanel = $BodySplit/LiveBattleLogPanel
@onready var _connect_button: Button = $TopRow/ConnectButton

var _transport: WebSocketTransport
var _decoder := ProtocolDecoder.new()
var _room_state_machine: RoomStateMachine
var _gateway: SpectatorRoomGateway
var _projection := LiveBattleProjection.new()
var _bus := ObservationEventBus.new()
## Watchlist M1c ("Unknown or inconsistent state events fail closed and remain diagnostically
## visible", 2026-07-26 review fix): keyed by ProtocolEventDTO.protocol_index (stable, monotonic,
## never reused), so LiveBattleLogPanel's rebuild-from-timeline can annotate exactly the events
## LiveBattleProjection.event_not_applied fired for -- without this workspace owning or patching
## any authoritative battle state itself (this is display-annotation metadata, not a snapshot).
var _not_applied_reasons: Dictionary[int, String] = {}


func _ready() -> void:
	_transport = WebSocketTransport.new()
	add_child(_transport)
	_wire_domain_and_ui()  # one-time only -- never re-run, see this task's small-fix-#1 note
	_wire_transport()
	_connect_button.pressed.connect(connect_to_showdown)


func configure_transport_for_test(peer_factory: Callable) -> void:
	remove_child(_transport)
	_transport.free()
	_transport = WebSocketTransport.new(peer_factory)
	add_child(_transport)
	_wire_transport()  # transport-dependent only -- safe to re-run on every swap


## Depends on _transport, so it is re-run every time _transport is replaced
## (configure_transport_for_test). Constructs RoomStateMachine/SpectatorRoomGateway fresh each
## time, since both hold a reference to the specific transport instance.
func _wire_transport() -> void:
	_room_state_machine = RoomStateMachine.new(_transport)
	_gateway = SpectatorRoomGateway.new(_transport, _room_state_machine)
	# M1 hardening (owner review of PR #94, P1 item 2, 2026-07-26): configure() now also wires
	# RoomEntryPanel's RoomStateMachine.state_changed subscription (see its own doc comment) -- a
	# fresh RoomStateMachine instance each time this function re-runs, so this never double-wires
	# the same object twice.
	_room_entry_panel.configure(_gateway, _room_state_machine)
	# Owner review of PR #96 (M1 hardening lifecycle-UI commit), second pass, P1 finding 2
	# (2026-07-26): a SEPARATE subscriber to the same state_changed signal RoomEntryPanel already
	# subscribes to (via configure(), above) -- this workspace is the one place that holds both
	# RoomStateMachine and LiveBattleProjection, so it is the correct (and only) place to
	# translate "the room I was displaying just ended" into "reset the projection" (AGENTS.md
	# rule 5: battle state is derived and owned by battle/, never patched by protocol/'s state
	# machine or ui/panels/ reaching into it themselves). A fresh RoomStateMachine instance each
	# time this function re-runs, so this never double-wires the same object twice.
	_room_state_machine.state_changed.connect(_on_room_state_changed_for_battle_reset)
	_transport.connection_state_changed.connect(_on_connection_state_changed)
	_transport.raw_text_received.connect(_decoder.decode_frame)


## One-time wiring only: connects _decoder (a fixed instance, never recreated) and _bus (ditto)
## to their subscribers. Fixed in this revision (small fix #1): this used to be part of the same
## _wire() that also ran on every configure_transport_for_test() call, which reconnected these
## signals a second time and processed every subsequent event twice.
func _wire_domain_and_ui() -> void:
	_decoder.event_decoded.connect(_on_event_decoded)
	_bus.connection_state_changed.connect(_connection_status_panel.on_connection_state_changed)
	_bus.battle_state_published.connect(_battle_board_panel.bind)
	_bus.battle_state_published.connect(_on_battle_state_published_for_log)
	# Real signal wiring (2026-07-26 review fix), per the schema doc's own description of this
	# event as "republishing battle/LiveBattleProjection.snapshot_published" -- replaces the
	# manual _bus.publish_battle_state_published(_projection.get_current_snapshot()) calls that
	# used to follow every apply_event() call in _on_event_decoded(). Publishes exactly once per
	# event the reducer actually applies (proved by
	# test_snapshot_published_reaches_the_bus_exactly_once_per_applied_event's red-first run,
	# which caught a genuine double-publish before the manual calls were removed).
	_projection.snapshot_published.connect(_bus.publish_battle_state_published)
	_projection.event_not_applied.connect(_on_event_not_applied)
	# Owner finding 6 (M1 hardening, 2026-07-26): subscribed exactly once here, replacing the
	# manual re-derivation that used to follow every _projection.apply_event() call in
	# _on_event_decoded() (checking get_current_snapshot().battle_completed after every applied
	# event, which republished on every event once battle_completed was true). LiveBattleProjection
	# now owns firing this signal exactly once, on the false->true transition.
	_projection.battle_completed.connect(_bus.publish_battle_completed)


func _on_battle_state_published_for_log(_snapshot: LiveBattleSnapshot) -> void:
	_live_battle_log_panel.rebuild_from_timeline(_projection.get_timeline(), _not_applied_reasons)


## Production sink for LiveBattleProjection's diagnostic signal (2026-07-26 review fix): an
## unhandled or inconsistent event previously only reached the timeline silently -- nothing ever
## rendered it, so the M1c diagnostic existed in code but was never actually visible at runtime.
## Records the reason keyed by the event's own protocol_index and immediately rebuilds the log
## panel (not just on the next successful apply) so the marked line appears right away.
func _on_event_not_applied(event: ProtocolEventDTO, reason: String) -> void:
	_not_applied_reasons[event.protocol_index] = reason
	_live_battle_log_panel.rebuild_from_timeline(_projection.get_timeline(), _not_applied_reasons)


func connect_to_showdown() -> void:
	_transport.connect_to_server(SHOWDOWN_WEBSOCKET_URL)


func get_transport() -> WebSocketTransport:
	return _transport


func get_room_entry_panel() -> RoomEntryPanel:
	return _room_entry_panel


func get_connection_status_panel() -> ConnectionStatusPanel:
	return _connection_status_panel


func get_battle_board_panel() -> BattleBoardPanel:
	return _battle_board_panel


func get_connect_button_for_test() -> Button:
	return _connect_button


func get_room_state_machine() -> RoomStateMachine:
	return _room_state_machine


func get_projection_for_test() -> LiveBattleProjection:
	return _projection


## Test-only seam for the watchlist's "domain/UI signals connected exactly once" proof: exposes
## the stable _decoder instance so a test can inspect event_decoded.get_connections().size()
## directly, rather than inferring wiring correctness only from indirect side effects.
func get_decoder_for_test() -> ProtocolDecoder:
	return _decoder


## Test-only seam: proves the bus receives snapshot_published exactly once per applied event
## (2026-07-26 review fix) -- see test_snapshot_published_reaches_the_bus_exactly_once_per_applied_event.
func get_observation_bus_for_test() -> ObservationEventBus:
	return _bus


func get_live_battle_log_panel() -> LiveBattleLogPanel:
	return _live_battle_log_panel


func _on_connection_state_changed(old_state: ConnectionStateMachine.State, new_state: ConnectionStateMachine.State) -> void:
	_bus.publish_connection_state_changed(old_state, new_state)


## Owner review, 2026-07-26, fifth pass, P2: docs/architecture/LIVE_STATE_MACHINES.md's RoomState
## table gives the "UI resets to pre-join state" annotation ONLY on the LEAVING -> NOT_JOINED row
## (a confirmed human leave) and the CLOSED -> NOT_JOINED row (the user dismissing an already-
## closed room) -- verified against the table directly. The ACTIVE -> CLOSED row itself carries
## only "Room closed" shown, nothing about resetting the UI. An earlier revision of this method
## also reset on ACTIVE -> CLOSED, reasoning that "there is nothing left to show once the room is
## closed" -- that over-reached the binding contract: the consequence was that the FINAL battle
## view (the very thing a spectator wants to see right as a battle ends) vanished the instant
## "Room closed" appeared, before the user had any chance to look at it. Fixed: only the two
## table-named triggers reset; the board/timeline now correctly remain visible through CLOSED and
## clear only on dismiss. LiveBattleProjection.reset() still publishes the cleared snapshot
## through the SAME snapshot_published -> bus -> board/log wiring every other state change already
## uses (_wire_domain_and_ui(), one-time) -- no second render path.
func _on_room_state_changed_for_battle_reset(old_state: RoomStateMachine.State, new_state: RoomStateMachine.State) -> void:
	var leave_confirmed := (
		old_state == RoomStateMachine.State.LEAVING and new_state == RoomStateMachine.State.NOT_JOINED
	)
	var dismissed := (
		old_state == RoomStateMachine.State.CLOSED and new_state == RoomStateMachine.State.NOT_JOINED
	)
	if leave_confirmed or dismissed:
		_projection.reset()


func _on_event_decoded(event: ProtocolEventDTO) -> void:
	# Room isolation: an event for any room other than the one this workspace joined never
	# reaches the projection, the log, or (fixed 2026-07-26 review) the error/JOINING branch
	# below -- the socket is shared across whatever rooms the server multiplexes over it, but
	# this UI shows exactly one room. This filter used to run AFTER the error/JOINING check,
	# so an unscoped (room_id == "") or foreign-room error frame arriving mid-join would
	# spuriously reject the in-flight join; moving it above handles both cases uniformly
	# through the same room-scoping mechanism every other event type already uses, while still
	# rejecting correctly on the join-target room's own error (its room_id always matches
	# get_room_id(), set immediately by request_join()).
	if event.room_id != _room_state_machine.get_room_id():
		return
	# Owner finding 3 (M1 hardening, 2026-07-26): the pinned real server rejects an unknown or
	# private room join with `noinit`, verified live -- never `error`. Both are handled
	# identically here (join rejection, surfaced reason); `error` stays handled too since it
	# remains a real, valid decode for other rejection paths and removing it would be an
	# unproven, unrequested behavior change.
	if event.event_type in ["error", "noinit"] and _room_state_machine.get_state() == RoomStateMachine.State.JOINING:
		# M1 hardening (owner review of PR #94, P1 item 2, 2026-07-26): RoomEntryPanel now
		# subscribes directly to RoomStateMachine.state_changed (wired once in
		# _wire_transport(), via configure()) and renders get_last_error_reason() uniformly
		# for every JOINING -> NOT_JOINED transition, whether the rejection came from the
		# server (this case) or from a local join_send_failed() -- this call used to reach
		# the panel through a second, independent path for the exact same render.
		_room_state_machine.join_rejected(str(event.error_reason))
		return
	if event.event_type == "init":
		if str(event.condition_label) != "battle":
			return  # a non-battle init (e.g. "chat") never confirms a battle join
		_room_state_machine.rejoin_confirmed()
		_projection.set_room_id(event.room_id)
		# Fixed (item B): the init event itself must reach the projection too -- Task 38's (M1e)
		# reset-on-repeat-init logic can only ever fire if the projection actually sees every
		# init, including this one. The bus publish itself now happens via the
		# _projection.snapshot_published -> _bus.publish_battle_state_published signal wiring
		# (2026-07-26 review fix) whenever apply_event() actually applies -- init itself is an
		# unhandled event type, so it never re-publishes an unchanged snapshot; this matches the
		# schema doc's own description and removes the manual re-derivation this task's earlier
		# red-run proved would otherwise double-publish for handled event types.
		_projection.apply_event(event)
		return
	if event.event_type == "deinit":
		# Fixed (item D): state-aware dispatch. A deinit while a human leave() is already in
		# flight (LEAVING) confirms that leave, rather than calling server_closed_room() -- which
		# is invalid from LEAVING and would silently no-op, wedging RoomState forever.
		if _room_state_machine.get_state() == RoomStateMachine.State.LEAVING:
			_room_state_machine.leave_confirmed()
		elif _room_state_machine.get_state() == RoomStateMachine.State.ACTIVE:
			_room_state_machine.server_closed_room()
		return
	# Owner review, 2026-07-26, fourth pass, P1: everything above this point is a lifecycle frame
	# (error/noinit/init/deinit) with its own branch and its own `return`; only a NON-lifecycle,
	# already room-scope-matched event ever reaches here. Fail closed (AGENTS.md rule 10) for
	# exactly the "not yet confirmed" window: NOT_JOINED (defensive -- should not normally have a
	# matching room id at all) and JOINING (this room's own battle init has not landed yet). A
	# same-room-id event arriving in either state (e.g. a resent |win| racing ahead of the room's
	# own |init|battle|, the owner's exact repro) must never reach the projection's reducer -- it
	# would corrupt the fresh projection state (wrong battle_completed, wrong room-id attribution)
	# before that room's own history has even started. Deliberately narrower than "!= ACTIVE": a
	# battle event arriving while LEAVING (the leave requested but not yet confirmed by the
	# server) or CLOSED is a different, already-confirmed room and must keep applying normally --
	# this finding is only about the PRE-confirmation window. Rejected via
	# LiveBattleProjection.reject_before_room_confirmed(), not silently dropped.
	if _room_state_machine.get_state() in [RoomStateMachine.State.NOT_JOINED, RoomStateMachine.State.JOINING]:
		_projection.reject_before_room_confirmed(event)
		return
	_projection.apply_event(event)
