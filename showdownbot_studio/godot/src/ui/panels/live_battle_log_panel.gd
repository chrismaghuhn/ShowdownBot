class_name LiveBattleLogPanel
extends Control

## Rebuilds its full displayed text from LiveBattleProjection.get_timeline() every time it is
## notified -- never a second, independently-accumulated copy of the same data (which would
## double-render after an M1e reconnect reset). Bounded, scrolling: one RichTextLabel, never one
## Control per row (ADR-001's "instantiating one Control per unbounded row is prohibited" rule).
## Server-delivered species/text is sanitized via UntrustedTextSanitizer before display.

const MAX_DISPLAYED_LINES := 500

@onready var _text: RichTextLabel = $LogText


func rebuild_from_timeline(timeline: Array[ProtocolEventDTO]) -> void:
	var lines: Array[String] = []
	for event in timeline:
		lines.append(_summarize(event))
	if lines.size() > MAX_DISPLAYED_LINES:
		lines = lines.slice(lines.size() - MAX_DISPLAYED_LINES, lines.size())
	_text.text = "\n".join(lines)


func get_log_text() -> String:
	return _text.text


func _summarize(event: ProtocolEventDTO) -> String:
	match event.event_type:
		"turn":
			return "turn %s" % str(event.turn_number)
		"switch", "drag":
			var species := UntrustedTextSanitizer.sanitize(str(event.pokemon_species))
			return "%s%s switched in: %s" % [str(event.pokemon_side), str(event.pokemon_slot), species]
		"faint":
			return "%s%s fainted" % [str(event.pokemon_side), str(event.pokemon_slot)]
		"win", "tie":
			return "battle ended (%s)" % event.event_type
		_:
			return event.event_type
