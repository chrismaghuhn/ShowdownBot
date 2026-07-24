class_name DiagnosticsDock
extends TabContainer

## Provenance | Warnings | Raw (Plan E §3.1). Raw evidence is bundle-normalized
## JSON built only from sealed DTO fields (no filesystem browser, no absolute
## local paths) and is bounded: over MAX_RAW_CHARS is truncated with an explicit
## marker (§0.9 / §5.3 test_raw_tab_bounded).
##
## Note (Task E2 scope): value/text controls below intentionally do NOT call
## StudioMonoFont.apply_to() yet — that helper and its RED/GREEN cycle are Task E6
## (plan §6), not this task.

const TRUNCATION_MARKER := "… truncated"
const MAX_RAW_CHARS := 20000

## Provenance/Warnings tabs are ScrollContainer > VBoxContainer("Rows") so
## per-row content (11 provenance rows, N warning rows) never inflates the
## TabContainer's own minimum size and forces MainSplit taller than the
## window (root cause of the 1280x720 transport-row overflow — see
## fix(studio) commit message). Raw stays a bare TextEdit; it already scrolls.
@onready var _provenance_list: VBoxContainer = $Provenance/Rows
@onready var _warnings_list: VBoxContainer = $Warnings/Rows
@onready var _raw_text: TextEdit = $Raw


func bind_bundle(bundle: BundleDTO) -> void:
	_rebuild_provenance(bundle)
	_rebuild_warnings(bundle)
	bind_raw_text(_bundle_raw_text(bundle))


func bind_raw_text(text: String) -> void:
	if text.length() > MAX_RAW_CHARS:
		_raw_text.text = "%s\n%s" % [text.substr(0, MAX_RAW_CHARS), TRUNCATION_MARKER]
	else:
		_raw_text.text = text


func get_raw_text() -> String:
	return _raw_text.text


func get_raw_control() -> Control:
	return _raw_text


func get_provenance_row_count() -> int:
	return _provenance_list.get_child_count()


func get_provenance_label_at(i: int) -> String:
	return (_provenance_list.get_child(i).get_node("Label") as Label).text


func get_provenance_value_at(i: int) -> String:
	return (_provenance_list.get_child(i).get_node("Value") as Label).text


func get_provenance_value_control_at(i: int) -> Control:
	return _provenance_list.get_child(i).get_node("Value")


func get_warning_row_count() -> int:
	return _warnings_list.get_child_count()


func get_warning_text_at(i: int) -> String:
	return (_warnings_list.get_child(i).get_node("Text") as Label).text


func get_warning_icon_control_at(i: int) -> Control:
	return _warnings_list.get_child(i).get_node("Icon")


func _rebuild_provenance(bundle: BundleDTO) -> void:
	_clear(_provenance_list)
	for row in ProvenancePresenter.present(bundle):
		_provenance_list.add_child(_make_row("Label", "%s:" % row.label, "Value", row.value))


func _rebuild_warnings(bundle: BundleDTO) -> void:
	_clear(_warnings_list)
	for row in DiagnosticsPresenter.present(bundle):
		_warnings_list.add_child(_make_row("Icon", row.icon, "Text", row.text))


func _clear(container: Control) -> void:
	for child in container.get_children():
		container.remove_child(child)
		child.free()


func _make_row(name_a: String, text_a: String, name_b: String, text_b: String) -> HBoxContainer:
	var row := HBoxContainer.new()
	var a := Label.new()
	a.name = name_a
	a.text = text_a
	var b := Label.new()
	b.name = name_b
	b.text = text_b
	row.add_child(a)
	row.add_child(b)
	return row


func _bundle_raw_text(bundle: BundleDTO) -> String:
	if bundle == null or bundle.manifest == null:
		return "{}"
	var m: BundleManifestDTO = bundle.manifest
	var data := {
		"battle_id": m.battle_id,
		"format_id": m.format_id,
		"git_sha": m.git_sha,
		"config_hash": m.config_hash,
		"exporter_name": m.exporter_name,
		"exporter_version": m.exporter_version,
		"trace_schema_version": m.trace_schema_version,
		"source_hashes_battle_log": m.source_hashes_battle_log,
		"source_hashes_decision_trace": m.source_hashes_decision_trace,
		"dirty": StateBannerPresenter.dirty_label(
			m.source_provenance.dirty if m.source_provenance != null else null
		),
		"decision_count": bundle.decisions.size(),
	}
	return JSON.stringify(data, "  ")
