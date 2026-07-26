class_name LiveBattleProjection
extends RefCounted

## The single owner of "current" derived battle state (spec section 4.7's derived-state rule,
## applied structurally): workspace/ and ui/panels/ only ever RECEIVE a published
## LiveBattleSnapshot; they never hold or compute one themselves. Also owns the parallel
## timeline projection so a future reconnect reset (M1e, Task 39) clears both together -- a
## decoupled reset would violate "state is rebuilt COMPLETELY," not just board state.

signal snapshot_published(snapshot: LiveBattleSnapshot)
signal battle_completed(room_id: String)
## Watchlist M1c ("Unknown or inconsistent state events fail closed and remain diagnostically
## visible") -- fired instead of silently no-op'ing, for exactly the two ways LiveBattleReducer
## already fails closed: "unhandled_type" (no match arm at all, e.g. "move"/"init"/"title") and
## "inconsistent_state" (a modeled event whose own data cannot be trusted -- missing
## pokemon_side/pokemon_slot, OR, owner finding 4, M1 hardening, a "turn" event with a null
## turn_number from a malformed `|turn|abc` line). Applies the watchlist's own precedence rule
## (this document's "Rule of precedence": the watchlist's acceptance test wins over the earlier,
## less complete M1c plan code sample -- the same rule that already governed M1a's literal
## peer-null guard) -- no owner block needed.
signal event_not_applied(event: ProtocolEventDTO, reason: String)

var _current: LiveBattleSnapshot = LiveBattleSnapshot.new()
var _timeline: Array[ProtocolEventDTO] = []
var _room_id: String = ""
## M1e (Task 38): true once this projection has observed its first battle `init`. A SECOND
## `init` after this is real Showdown's own signal that authoritative history is starting over
## (a reconnect resend, spec section 6.2) -- apply_event() resets both _current and _timeline
## completely before folding it and everything that follows, never incrementally. Full reset and
## refold is the intended model; no content-based protocol-line deduplication is introduced.
var _has_seen_init: bool = false


func get_current_snapshot() -> LiveBattleSnapshot:
	return _current


func get_timeline() -> Array[ProtocolEventDTO]:
	return _timeline.duplicate()


## Set by whoever confirms the room join (M1d's composition root) -- purely for attributing
## battle_completed to the right room id; never used for room-membership filtering (that is
## the composition root's own job, applied before events reach this class at all, M1d Task 29).
func set_room_id(room_id: String) -> void:
	_room_id = room_id


## Owner review, 2026-07-26, fourth pass, P1: the previous reset() cleared snapshot/timeline but
## deliberately preserved _room_id, needed by the repeat-init/reconnect path below. That same
## choice was WRONG for reset()'s OTHER caller, LiveClientWorkspace's room-ending triggers (leave
## confirmed / server closed / dismissed): after those, _room_id must NOT survive into the next
## room's lifecycle, or a battle_completed wrongly emitted for a not-yet-confirmed NEW room
## misattributes to the OLD room's id (owner repro: join battle-1, leave, join battle-2, a
## premature |win| before battle-2's own init emitted battle_completed("battle-1")).
##
## Split into a shared PRIVATE clear (_clear_battle_state(), the exact shape BOTH callers need:
## fresh empty snapshot, empty timeline, _has_seen_init reset, published through
## snapshot_published so the board/log panels the bus feeds actually blank -- spec section 4.7's
## single render path, no second path) plus per-caller room-id handling: this PUBLIC reset()
## (room ended) also clears _room_id; apply_event()'s repeat-init branch below calls only the
## shared private clear, keeping whatever room id LiveClientWorkspace already set via
## set_room_id() moments earlier -- that path legitimately needs it (a reconnect rejoins the SAME
## room), and clearing it there would wipe a value the caller had just set.
func reset() -> void:
	_clear_battle_state()
	_room_id = ""


func _clear_battle_state() -> void:
	_current = LiveBattleSnapshot.new()
	_timeline = []
	_has_seen_init = false
	snapshot_published.emit(_current)


## Fail-closed guard for a genuinely different defect class (owner review, 2026-07-26, fourth
## pass, P1): an event whose room_id matches the currently joined room can still arrive BEFORE
## that room's own battle init is confirmed (RoomState reaches ACTIVE) -- e.g. a resent |win| line
## racing ahead of the |init|battle| line for a just-(re)joined room. LiveClientWorkspace (the one
## place that holds RoomStateMachine) is the correct, and only, place to decide THIS is true --
## protocol/'s room-lifecycle state and battle/'s derived state stay strictly separated (AGENTS.md
## rule 6); this method is where that decision becomes visible. Reuses the EXACT event_not_applied
## diagnostic signal apply_event() already fires for "unhandled_type"/"inconsistent_state" (a
## THIRD reason literal, "room_not_confirmed", same discipline) -- but deliberately does NOT
## append to _timeline the way apply_event()'s own not-applied cases do: unlike those, this event
## is not even part of the room's real history yet (its own room hasn't started), so it must not
## seed a timeline that the genuine, ordered, confirmed stream will build from scratch once the
## real init arrives. Never a silent drop: a real signal fires, observable the same way the other
## two reasons already are.
func reject_before_room_confirmed(event: ProtocolEventDTO) -> void:
	event_not_applied.emit(event, "room_not_confirmed")


func apply_event(event: ProtocolEventDTO) -> void:
	# Quality-review fix (2026-07-26): gated on condition_label == "battle" INTERNALLY, never
	# trusting a caller to have already filtered out a non-battle (e.g. "chat") init before
	# calling apply_event() -- workspace/'s own _on_event_decoded() already does that filtering,
	# but AGENTS.md rule 10 (fail closed by default) means this class must not fail OPEN if some
	# other or future caller forwards a chat init anyway. A non-battle init is a complete no-op
	# for the reset path (never resets, never arms/disarms _has_seen_init) and simply flows into
	# the normal not-applied/ignored handling below, exactly like any other event_type this
	# reducer has no arm for -- "init" is never in LiveBattleReducer's own handled-type list
	# regardless of condition_label, so it always falls through to that same path anyway.
	if event.event_type == "init" and event.condition_label == "battle":
		if _has_seen_init:
			_clear_battle_state()
		_has_seen_init = true
	_timeline.append(event)
	if not LiveBattleReducer.is_handled_event_type(event.event_type):
		event_not_applied.emit(event, "unhandled_type")
		return
	if not LiveBattleReducer.is_event_data_consistent(event):
		event_not_applied.emit(event, "inconsistent_state")
		return
	# Owner finding 6 (M1 hardening, 2026-07-26): battle_completed must fire exactly once, on the
	# false->true transition -- not level-triggered on every event applied while battle_completed
	# stays true (a trailing event after win/tie previously re-published completion).
	var was_completed := _current.battle_completed
	_current = LiveBattleReducer.apply(_current, event)
	snapshot_published.emit(_current)
	if _current.battle_completed and not was_completed:
		battle_completed.emit(_room_id)
