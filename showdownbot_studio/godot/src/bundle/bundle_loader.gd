class_name BundleLoader
extends Node

enum State { IDLE, LOADING, COMPLETED, REFUSED, CANCELLED }

signal progress(message: String)
signal completed(bundle: BundleDTO)
signal refused(diagnostic: RefuseDiagnostic)
signal cancelled

var _worker_thread: Thread = null
var _pending_path: String = ""
var _active_request_id: int = 0
var _state: State = State.IDLE
var _queue_mutex: Mutex = Mutex.new()
var _message_queue: Array = []
var _worker_hooks: BundleWorker.WorkerHooks = null
var _cancel_flag: Dictionary = {"cancelled": false}
var _suppress_publish: bool = false
var _terminal_received_for_active: bool = false
var _shutting_down: bool = false
var _last_progress_emit_thread_id: int = -1


func get_state() -> State:
	return _state


func is_worker_thread_joined() -> bool:
	return _worker_thread == null


func get_last_progress_emit_thread_id() -> int:
	return _last_progress_emit_thread_id


func set_worker_hooks(hooks: BundleWorker.WorkerHooks) -> void:
	_worker_hooks = hooks


func load_async(path: String) -> void:
	if _worker_thread != null:
		_pending_path = path
		_cancel_flag["cancelled"] = true
		_suppress_publish = true
		return

	_start_load(path)


func cancel() -> void:
	_cancel_flag["cancelled"] = true
	_pending_path = ""
	_suppress_publish = true
	if _state != State.LOADING:
		_state = State.CANCELLED


func _process(_delta: float) -> void:
	_drain_queue()
	_maybe_finalize_worker()


func _exit_tree() -> void:
	_shutting_down = true
	_cancel_flag["cancelled"] = true
	_pending_path = ""
	_suppress_publish = true
	_join_worker_thread()
	_queue_mutex.lock()
	_message_queue.clear()
	_queue_mutex.unlock()


func _start_load(path: String) -> void:
	_active_request_id += 1
	_state = State.LOADING
	_cancel_flag = {"cancelled": false}
	_suppress_publish = false
	_terminal_received_for_active = false

	# Shared context only — no Node self capture on the worker thread.
	var ctx := {
		"request_id": _active_request_id,
		"path": path,
		"cancel_flag": _cancel_flag,
		"queue_mutex": _queue_mutex,
		"message_queue": _message_queue,
		"hooks": _worker_hooks,
	}
	_worker_thread = Thread.new()
	_worker_thread.start(BundleWorker.thread_main.bind(ctx))


func _drain_queue() -> void:
	_queue_mutex.lock()
	var batch: Array = _message_queue.duplicate()
	_message_queue.clear()
	_queue_mutex.unlock()

	for envelope in batch:
		_handle_envelope(envelope)


func _handle_envelope(envelope: Dictionary) -> void:
	var request_id: int = envelope.get("request_id", -1)
	if request_id != _active_request_id:
		return

	var kind: String = envelope.get("kind", "")
	match kind:
		BundleWorker.ENVELOPE_PROGRESS:
			if not _shutting_down:
				_last_progress_emit_thread_id = OS.get_main_thread_id()
				progress.emit(String(envelope.get("payload", "")))
		BundleWorker.ENVELOPE_OK, BundleWorker.ENVELOPE_REFUSE, BundleWorker.ENVELOPE_CANCELLED:
			_handle_terminal(envelope)


func _handle_terminal(envelope: Dictionary) -> void:
	if _shutting_down:
		_terminal_received_for_active = true
		return

	if _suppress_publish or _cancel_flag.get("cancelled", false):
		_state = State.CANCELLED
		cancelled.emit()
		_terminal_received_for_active = true
		return

	var kind: String = envelope.get("kind", "")
	match kind:
		BundleWorker.ENVELOPE_OK:
			var result: ValidationResult = envelope.get("payload")
			if result == null or result.bundle == null:
				_publish_internal_loader_error()
			else:
				var published := _deep_copy_and_seal_bundle(result.bundle)
				_state = State.COMPLETED
				completed.emit(published)
		BundleWorker.ENVELOPE_REFUSE:
			var result: ValidationResult = envelope.get("payload")
			if result == null or result.diagnostic == null:
				_publish_internal_loader_error()
			else:
				var diagnostic := _deep_copy_and_seal_diagnostic(result.diagnostic)
				_state = State.REFUSED
				refused.emit(diagnostic)
		BundleWorker.ENVELOPE_CANCELLED:
			_state = State.CANCELLED
			cancelled.emit()

	_terminal_received_for_active = true


func _maybe_finalize_worker() -> void:
	if _worker_thread == null:
		return

	var thread_done := not _worker_thread.is_alive()
	if not thread_done and not _terminal_received_for_active:
		return

	if thread_done and not _terminal_received_for_active:
		_join_worker_thread()
		if not _shutting_down:
			_publish_internal_loader_error()
		_maybe_start_pending()
		return

	if _terminal_received_for_active or thread_done:
		_join_worker_thread()
		_maybe_start_pending()


func _maybe_start_pending() -> void:
	if _pending_path.is_empty():
		return
	var next_path := _pending_path
	_pending_path = ""
	_start_load(next_path)


func _join_worker_thread() -> void:
	if _worker_thread == null:
		return
	_worker_thread.wait_to_finish()
	_worker_thread = null


func _publish_internal_loader_error() -> void:
	if _shutting_down:
		return
	var diagnostic := RefuseDiagnostic.new()
	diagnostic.reason = "internal_loader_error"
	diagnostic.message = "worker returned without terminal envelope"
	diagnostic.offender = ""
	diagnostic.seal()
	_state = State.REFUSED
	refused.emit(diagnostic)


func _deep_copy_and_seal_diagnostic(source: RefuseDiagnostic) -> RefuseDiagnostic:
	var copy := RefuseDiagnostic.new()
	copy.reason = source.reason
	copy.message = source.message
	copy.offender = source.offender
	copy.seal()
	return copy


func _deep_copy_and_seal_bundle(source: BundleDTO) -> BundleDTO:
	var copy := BundleDTO.new()
	copy.declared_mode = source.declared_mode
	copy.effective_mode = source.effective_mode
	copy.trace_trusted = source.trace_trusted
	copy.replay_trusted = source.replay_trusted
	copy.manifest = _deep_copy_manifest(source.manifest)
	copy.decisions = _deep_copy_decisions(source.decisions)
	copy.battle_events = _deep_copy_battle_events(source.battle_events)
	copy.warnings = _deep_copy_warnings(source.warnings)
	if source.config_manifest is ConfigManifestRawDTO:
		copy.config_manifest = _deep_copy_config_manifest(source.config_manifest)
	else:
		copy.config_manifest = null
	copy.downgrade_warnings = _deep_copy_diagnostics(source.downgrade_warnings)
	copy.seal()
	return copy


func _deep_copy_manifest(source: BundleManifestDTO) -> BundleManifestDTO:
	var copy := BundleManifestDTO.new()
	copy.schema_major = source.schema_major
	copy.schema_minor = source.schema_minor
	copy.required_capabilities = source.required_capabilities.duplicate()
	copy.exporter_name = source.exporter_name
	copy.exporter_version = source.exporter_version
	copy.battle_id = source.battle_id
	copy.format_id = source.format_id
	copy.git_sha = source.git_sha
	copy.config_hash = source.config_hash
	copy.trace_schema_version = source.trace_schema_version
	copy.privacy = _deep_copy_privacy(source.privacy)
	copy.source_hashes_battle_log = source.source_hashes_battle_log
	copy.source_hashes_decision_trace = source.source_hashes_decision_trace
	copy.files = _deep_copy_files_table(source.files)
	copy.source_provenance = _deep_copy_source_provenance(source.source_provenance)
	copy.unknown_fields = source.unknown_fields.duplicate(true)
	return copy


func _deep_copy_privacy(source: PrivacyDTO) -> PrivacyDTO:
	var copy := PrivacyDTO.new()
	copy.profile = source.profile
	copy.chat = source.chat
	copy.private_messages = source.private_messages
	copy.player_names = source.player_names
	copy.source_url = source.source_url
	copy.raw_source_included = source.raw_source_included
	return copy


func _deep_copy_file_entry(source: FileEntryDTO) -> FileEntryDTO:
	var copy := FileEntryDTO.new()
	copy.path = source.path
	copy.present = source.present
	copy.required = source.required
	copy.sha256 = source.sha256
	return copy


func _deep_copy_files_table(source: FilesTableDTO) -> FilesTableDTO:
	var copy := FilesTableDTO.new()
	copy.battle_log = _deep_copy_file_entry(source.battle_log)
	copy.decision_trace = _deep_copy_file_entry(source.decision_trace)
	copy.warnings = _deep_copy_file_entry(source.warnings)
	copy.config_manifest = _deep_copy_file_entry(source.config_manifest)
	return copy


func _deep_copy_source_provenance(source: SourceProvenanceDTO) -> SourceProvenanceDTO:
	var copy := SourceProvenanceDTO.new()
	copy.dirty = source.dirty
	copy.our_side = source.our_side
	copy.config_id = source.config_id
	copy.schedule_hash = source.schedule_hash
	copy.seed_index = source.seed_index
	copy.showdown_commit = source.showdown_commit
	copy.server_patch_hash = source.server_patch_hash
	copy.unknown_fields = source.unknown_fields.duplicate(true)
	return copy


func _deep_copy_candidate(source: CandidateDTO) -> CandidateDTO:
	var copy := CandidateDTO.new()
	copy.candidate_id = source.candidate_id
	copy.rank = source.rank
	copy.aggregate_score = source.aggregate_score
	copy.candidate_key = source.candidate_key
	copy.unknown_fields = source.unknown_fields.duplicate(true)
	return copy


func _deep_copy_decision(source: DecisionRowDTO) -> DecisionRowDTO:
	var copy := DecisionRowDTO.new()
	copy.decision_index = source.decision_index
	copy.turn_number = source.turn_number
	copy.decision_phase = source.decision_phase
	copy.decision_latency_ms = source.decision_latency_ms
	copy.observable_state_hash = source.observable_state_hash
	copy.request_hash = source.request_hash
	copy.state_summary = source.state_summary.duplicate(true)
	copy.normalized_action = source.normalized_action.duplicate(true)
	copy.actual_choose_string = source.actual_choose_string
	var candidates: Array = []
	for item in source.candidates:
		if item is CandidateDTO:
			candidates.append(_deep_copy_candidate(item))
	copy.candidates = candidates
	copy.chosen_candidate_key = source.chosen_candidate_key
	copy.chosen_candidate_id = source.chosen_candidate_id
	copy.chosen_rank = source.chosen_rank
	copy.chosen_tera_slot = source.chosen_tera_slot
	copy.chosen_mega_slot = source.chosen_mega_slot
	copy.selection_stage = source.selection_stage
	copy.fallback_reason = source.fallback_reason
	copy.aggregation_mode = source.aggregation_mode
	copy.aggregation_risk_lambda = source.aggregation_risk_lambda
	copy.aggregation_must_react_lambda = source.aggregation_must_react_lambda
	copy.request_protocol_index = source.request_protocol_index
	copy.top1_top2_margin = source.top1_top2_margin
	copy.fallback_used = source.fallback_used
	copy.warning_count = source.warning_count
	copy.decision_valid = source.decision_valid
	copy.unknown_fields = source.unknown_fields.duplicate(true)
	return copy


func _deep_copy_decisions(source: Array) -> Array:
	var copy: Array = []
	for item in source:
		if item is DecisionRowDTO:
			copy.append(_deep_copy_decision(item))
	return copy


func _deep_copy_battle_event(source: BattleEventDTO) -> BattleEventDTO:
	var copy := BattleEventDTO.new()
	copy.protocol_index = source.protocol_index
	copy.type = source.type
	# Variant fields may hold containers — always deep-copy (never share with worker DTO).
	copy.pokemon_side = JsonNumbers.deep_copy_value(source.pokemon_side)
	copy.pokemon_slot = JsonNumbers.deep_copy_value(source.pokemon_slot)
	copy.pokemon_species = JsonNumbers.deep_copy_value(source.pokemon_species)
	copy.target_side = JsonNumbers.deep_copy_value(source.target_side)
	copy.target_slot = JsonNumbers.deep_copy_value(source.target_slot)
	copy.details = JsonNumbers.deep_copy_value(source.details)
	copy.value = JsonNumbers.deep_copy_value(source.value)
	copy.side = JsonNumbers.deep_copy_value(source.side)
	copy.amount = JsonNumbers.deep_copy_value(source.amount)
	copy.hp_current = JsonNumbers.deep_copy_value(source.hp_current)
	copy.hp_maximum = JsonNumbers.deep_copy_value(source.hp_maximum)
	copy.hp_fainted = JsonNumbers.deep_copy_value(source.hp_fainted)
	copy.hp_status = JsonNumbers.deep_copy_value(source.hp_status)
	copy.tags = source.tags.duplicate()
	copy.unknown_fields = source.unknown_fields.duplicate(true)
	return copy


func _deep_copy_battle_events(source: Array) -> Array:
	var copy: Array = []
	for item in source:
		if item is BattleEventDTO:
			copy.append(_deep_copy_battle_event(item))
	return copy


func _deep_copy_warning(source: ExporterWarningDTO) -> ExporterWarningDTO:
	var copy := ExporterWarningDTO.new()
	copy.code = source.code
	copy.decision_index = source.decision_index
	copy.message = source.message
	copy.unknown_fields = source.unknown_fields.duplicate(true)
	return copy


func _deep_copy_warnings(source: Array) -> Array:
	var copy: Array = []
	for item in source:
		if item is ExporterWarningDTO:
			copy.append(_deep_copy_warning(item))
	return copy


func _deep_copy_config_manifest(source: ConfigManifestRawDTO) -> ConfigManifestRawDTO:
	var copy := ConfigManifestRawDTO.new()
	copy.root = source.root.duplicate(true)
	return copy


func _deep_copy_diagnostics(source: Array) -> Array:
	var copy: Array = []
	for item in source:
		if item is RefuseDiagnostic:
			copy.append(_deep_copy_and_seal_diagnostic(item))
	return copy
