class_name LiveBattleProjection
extends RefCounted

## The single owner of "current" derived battle state (spec section 4.7's derived-state rule,
## applied structurally): workspace/ and ui/panels/ only ever RECEIVE a published
## LiveBattleSnapshot; they never hold or compute one themselves. Also owns the parallel
## timeline projection so a future reconnect reset (M1e, Task 39) clears both together -- a
## decoupled reset would violate "state is rebuilt COMPLETELY," not just board state.

signal snapshot_published(snapshot: LiveBattleSnapshot)
signal battle_completed(room_id: String)

var _current: LiveBattleSnapshot = LiveBattleSnapshot.new()
var _timeline: Array[ProtocolEventDTO] = []
var _room_id: String = ""


func get_current_snapshot() -> LiveBattleSnapshot:
	return _current


func get_timeline() -> Array[ProtocolEventDTO]:
	return _timeline.duplicate()


## Set by whoever confirms the room join (M1d's composition root) -- purely for attributing
## battle_completed to the right room id; never used for room-membership filtering (that is
## the composition root's own job, applied before events reach this class at all, M1d Task 29).
func set_room_id(room_id: String) -> void:
	_room_id = room_id


func apply_event(event: ProtocolEventDTO) -> void:
	_timeline.append(event)
	_current = LiveBattleReducer.apply(_current, event)
	snapshot_published.emit(_current)
	if _current.battle_completed:
		battle_completed.emit(_room_id)
