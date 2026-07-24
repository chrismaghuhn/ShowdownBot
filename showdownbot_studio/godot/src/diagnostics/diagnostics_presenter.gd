class_name DiagnosticsPresenter
extends RefCounted

## Warning list model (Plan E §0.9 / §4): exporter warnings (bundle.warnings,
## ExporterWarningDTO) followed by downgrade warnings (bundle.downgrade_warnings,
## RefuseDiagnostic). One row per entry as {text, icon} — text + icon, never
## color alone (design §6.4).

const ICON_EXPORTER := "!"
const ICON_DOWNGRADE := "~"


static func present(bundle: BundleDTO) -> Array:
	var rows: Array = []
	if bundle == null:
		return rows
	for item in bundle.warnings:
		var w: ExporterWarningDTO = item
		rows.append({"text": _exporter_warning_text(w), "icon": ICON_EXPORTER})
	for item in bundle.downgrade_warnings:
		var d: RefuseDiagnostic = item
		rows.append({"text": _downgrade_warning_text(d), "icon": ICON_DOWNGRADE})
	return rows


static func _exporter_warning_text(w: ExporterWarningDTO) -> String:
	var text := w.code
	if w.decision_index != null:
		text += " (decision #%s)" % str(w.decision_index)
	if w.message != null:
		text += ": %s" % w.message
	return text


static func _downgrade_warning_text(d: RefuseDiagnostic) -> String:
	return "%s: %s" % [d.reason, d.message]
