class_name LiveClientWorkspace
extends Control

## Connection + Spectator areas (spec section 4.6). Holds no derived battle state itself
## (battle/LiveBattleProjection owns that); composes modules and routes already-published values
## only. Room join/leave never reaches net/'s transport except through SpectatorRoomGateway.

const SHOWDOWN_WEBSOCKET_URL := "wss://sim3.psim.us/showdown/websocket"

@onready var _room_entry_panel: RoomEntryPanel = $RoomEntryPanel
@onready var _connection_status_panel: ConnectionStatusPanel = $ConnectionStatusPanel
@onready var _battle_board_panel: BattleBoardPanel = $BattleBoardPanel
@onready var _live_battle_log_panel: LiveBattleLogPanel = $LiveBattleLogPanel
@onready var _connect_button: Button = $ConnectButton

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
	_room_entry_panel.configure(_gateway)
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
	if event.event_type == "error" and _room_state_machine.get_state() == RoomStateMachine.State.JOINING:
		_room_state_machine.join_rejected(str(event.error_reason))
		_room_entry_panel.on_join_rejected(str(event.error_reason))
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
	_projection.apply_event(event)
	if _projection.get_current_snapshot().battle_completed:
		_bus.publish_battle_completed(event.room_id)
