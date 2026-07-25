class_name LiveBattleLogPanel
extends Control

## Rebuilds its full displayed text from LiveBattleProjection.get_timeline() every time it is
## notified -- never a second, independently-accumulated copy of the same data (which would
## double-render after an M1e reconnect reset). Bounded, scrolling: one RichTextLabel, never one
## Control per row (ADR-001's "instantiating one Control per unbounded row is prohibited" rule).
## Server-delivered species/text is sanitized via UntrustedTextSanitizer before display.

const MAX_DISPLAYED_LINES := 500

@onready var _text: RichTextLabel = $LogText


## `not_applied_reasons` (2026-07-26 review fix): keyed by ProtocolEventDTO.protocol_index,
## supplied by LiveClientWorkspace from LiveBattleProjection.event_not_applied (watchlist M1c:
## "Unknown or inconsistent state events fail closed and remain diagnostically visible"). Default
## empty keeps every existing caller byte-identical. Folded into the SAME full rebuild-from-
## timeline pass -- never a second, independently-appended line -- so a marked event's diagnostic
## text persists exactly as long as the event itself stays in the timeline, with no separate reset
## path to keep in sync after an M1e reconnect reset.
func rebuild_from_timeline(timeline: Array[ProtocolEventDTO], not_applied_reasons: Dictionary[int, String] = {}) -> void:
	var lines: Array[String] = []
	for event in timeline:
		lines.append(_summarize(event, not_applied_reasons))
	if lines.size() > MAX_DISPLAYED_LINES:
		lines = lines.slice(lines.size() - MAX_DISPLAYED_LINES, lines.size())
	_text.text = "\n".join(lines)


func get_log_text() -> String:
	return _text.text


func _summarize(event: ProtocolEventDTO, not_applied_reasons: Dictionary[int, String]) -> String:
	var summary := _summarize_event(event)
	if not_applied_reasons.has(event.protocol_index):
		# Sanitized even though today's reasons ("unhandled_type"/"inconsistent_state") are
		# client-internal literals, never raw server text -- §6.1's surfaced-warnings discipline
		# applied defensively at the one render point, not conditioned on the reason's own source.
		var reason := UntrustedTextSanitizer.sanitize(str(not_applied_reasons[event.protocol_index]))
		return "[not applied: %s] %s" % [reason, summary]
	return summary


func _summarize_event(event: ProtocolEventDTO) -> String:
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
