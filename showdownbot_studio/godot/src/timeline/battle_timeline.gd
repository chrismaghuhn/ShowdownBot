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
