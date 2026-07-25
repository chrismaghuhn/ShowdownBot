class_name RoomEntryPanel
extends Control

## Direct room-ID/URL entry, no fallback room, no room browser (spec section 6.1, section 3.2).
## Holds a SpectatorRoomGatewayPort (Task 27/28), injected via configure() -- never a direct
## reference to protocol/'s encoder or net/'s transport, and never the concrete SpectatorRoomGateway
## type either (so a test fake can satisfy this without the gateway's own dependencies). There is
## no join_requested signal: this panel calls the gateway directly from its own button handler.

@onready var _input: LineEdit = $RoomIdInput
@onready var _error_label: Label = $ErrorLabel
@onready var _join_button: Button = $JoinButton

var _gateway: SpectatorRoomGatewayPort


func _ready() -> void:
	_join_button.pressed.connect(_on_join_pressed)


func configure(gateway: SpectatorRoomGatewayPort) -> void:
	_gateway = gateway


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


func on_join_rejected(server_error_text: String) -> void:
	# Untrusted server content: rendered as plain Label text, sanitized before display.
	_error_label.text = UntrustedTextSanitizer.sanitize(server_error_text)


func get_error_text() -> String:
	return _error_label.text


func set_input_text_for_test(text: String) -> void:
	_input.text = text


func press_watch_for_test() -> void:
	_on_join_pressed()
