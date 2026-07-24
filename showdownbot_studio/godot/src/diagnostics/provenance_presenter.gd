class_name ProvenancePresenter
extends RefCounted

## Formats manifest + source_provenance into an ordered Array of {label, value}
## dictionaries (Plan E §4.2). Never invent hashes; null optional -> "not recorded"
## (reuses DecisionPresenter.optional_text). dirty tri-state reuses
## StateBannerPresenter.dirty_label (true/false/null -> "dirty state not recorded").
##
## Rows also carry `mono: bool` (default false) marking hash-like fields
## (`git_sha`, `config_hash`, `source_hashes_*` — §0.9 / §4.6). `{label, value}`
## stays intact for existing callers; `mono` is additive.


static func present(bundle: BundleDTO) -> Array:
	var rows: Array = []
	if bundle == null or bundle.manifest == null:
		return rows
	var m: BundleManifestDTO = bundle.manifest
	rows.append(_row("schema", "%d.%d" % [m.schema_major, m.schema_minor]))
	rows.append(_row(
		"trace_schema_version", DecisionPresenter.optional_text(m.trace_schema_version)
	))
	rows.append(_row("format_id", DecisionPresenter.optional_text(m.format_id)))
	rows.append(_row("battle_id", DecisionPresenter.optional_text(m.battle_id)))
	rows.append(_row("git_sha", DecisionPresenter.optional_text(m.git_sha), true))
	rows.append(_row("config_hash", DecisionPresenter.optional_text(m.config_hash), true))
	rows.append(_row(
		"source_hashes_battle_log", DecisionPresenter.optional_text(m.source_hashes_battle_log), true
	))
	rows.append(_row(
		"source_hashes_decision_trace",
		DecisionPresenter.optional_text(m.source_hashes_decision_trace),
		true
	))
	rows.append(_row("exporter_name", DecisionPresenter.optional_text(m.exporter_name)))
	rows.append(_row("exporter_version", DecisionPresenter.optional_text(m.exporter_version)))
	var dirty: Variant = null
	if m.source_provenance != null:
		dirty = m.source_provenance.dirty
	rows.append(_row("dirty", StateBannerPresenter.dirty_label(dirty)))
	return rows


static func _row(label: String, value: String, mono: bool = false) -> Dictionary:
	return {"label": label, "value": value, "mono": mono}
