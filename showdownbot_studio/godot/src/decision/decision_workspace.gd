class_name DecisionWorkspace
extends VBoxContainer

@onready var _loading: Label = $LoadingLabel
@onready var _empty: Label = $EmptyStateLabel
@onready var _header: Label = $HeaderLabel
@onready var _stage: Label = $ChromeRow/StageLabel
@onready var _fallback: Label = $ChromeRow/FallbackLabel
@onready var _mega: Label = $ChromeRow/MegaLabel
@onready var _tera: Label = $ChromeRow/TeraLabel
@onready var _prev: Button = $NavRow/PrevDecisionButton
@onready var _next: Button = $NavRow/NextDecisionButton
@onready var _close: Button = $NavRow/NextCloseButton
@onready var _fb: Button = $NavRow/NextFallbackButton
@onready var _warn: Button = $NavRow/NextWarningButton
@onready var _table: CandidateTableView = $CandidateTable
@onready var _detail: DecisionDetailView = $Detail
@onready var _controller: DecisionController = $DecisionController


func _ready() -> void:
	_prev.pressed.connect(_controller.jump_prev_decision)
	_next.pressed.connect(func(): _controller.jump_next("decision"))
	_close.pressed.connect(func(): _controller.jump_next("close"))
	_fb.pressed.connect(func(): _controller.jump_next("fallback"))
	_warn.pressed.connect(func(): _controller.jump_next("warning"))
	_controller.decision_selection_changed.connect(_on_decision_selection_changed)
	_table.candidate_selected.connect(_on_candidate_selected)
	clear()


func reset(bundle: BundleDTO, timeline: TimelineController) -> void:
	set_loading(false)
	if bundle == null or not bundle.trace_trusted:
		_controller.clear()
		_show_empty_trace()
		return
	_empty.visible = false
	_empty.text = ""
	_controller.reset(bundle, timeline)
	_set_nav_enabled(true)
	_refresh_from_controller()


func clear() -> void:
	_controller.clear()
	_table.clear_view()
	_detail.clear_view()
	_header.text = ""
	_stage.text = ""
	_fallback.text = ""
	_mega.text = ""
	_tera.text = ""
	_empty.visible = false
	_empty.text = ""
	_set_nav_enabled(false)
	set_loading(false)


func set_loading(active: bool) -> void:
	_loading.text = "Loading..." if active else ""


func get_decision_controller() -> DecisionController:
	return _controller


func get_candidate_table_view() -> CandidateTableView:
	return _table


func get_detail_view() -> DecisionDetailView:
	return _detail


func get_empty_state_visible() -> bool:
	return _empty.visible


func get_header_text() -> String:
	return _header.text


func _show_empty_trace() -> void:
	_empty.visible = true
	_empty.text = DecisionPresenter.EMPTY_TRACE_TEXT
	_table.clear_view()
	_detail.clear_view()
	_header.text = ""
	_stage.text = ""
	_fallback.text = ""
	_mega.text = ""
	_tera.text = ""
	_set_nav_enabled(false)


func _on_decision_selection_changed(_row: int) -> void:
	_refresh_from_controller()


func _on_candidate_selected(_candidate_index: int) -> void:
	_detail.bind_candidate(_table.get_selected_candidate())


func _refresh_from_controller() -> void:
	var decision: DecisionRowDTO = _controller.get_selected_decision()
	if decision == null:
		_table.clear_view()
		_detail.clear_view()
		_header.text = ""
		_stage.text = ""
		_fallback.text = ""
		_mega.text = ""
		_tera.text = ""
		_set_nav_enabled(false)
		return
	_header.text = DecisionPresenter.header_text(decision)
	_stage.text = "stage: %s" % DecisionPresenter.optional_text(decision.selection_stage)
	_fallback.text = "fallback: %s (%s)" % [
		str(decision.fallback_used),
		DecisionPresenter.optional_text(decision.fallback_reason),
	]
	_mega.text = "mega: %s" % DecisionPresenter.optional_text(decision.chosen_mega_slot)
	_tera.text = "tera: %s" % DecisionPresenter.optional_text(decision.chosen_tera_slot)
	_table.bind(decision)
	_detail.bind_decision(decision)
	_detail.bind_candidate(_table.get_selected_candidate())
	_prev.disabled = not _controller.has_prev_decision()
	_next.disabled = not _controller.has_next("decision")
	_close.disabled = not _controller.has_next("close")
	_fb.disabled = not _controller.has_next("fallback")
	_warn.disabled = not _controller.has_next("warning")


func _set_nav_enabled(enabled: bool) -> void:
	if not enabled:
		_prev.disabled = true
		_next.disabled = true
		_close.disabled = true
		_fb.disabled = true
		_warn.disabled = true
