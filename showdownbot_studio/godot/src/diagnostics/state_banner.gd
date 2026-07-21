class_name StateBanner
extends HBoxContainer

@onready var _icon_label: Label = $IconLabel
@onready var _state_label: Label = $StateLabel
@onready var _detail_label: Label = $DetailLabel


func _ready() -> void:
	if _state_label.text.is_empty():
		set_banner(StateBannerPresenter.BUNDLE_INVALID, "")


func set_banner(state: String, detail: String = "") -> void:
	_icon_label.text = _icon_for(state)
	_state_label.text = state
	_detail_label.text = detail
	_detail_label.visible = not detail.is_empty()


func get_state_text() -> String:
	return _state_label.text


func get_detail_text() -> String:
	return _detail_label.text


func _icon_for(state: String) -> String:
	# Text + icon (never color alone) — design §6.4 / Plan E §0.5.
	match state:
		StateBannerPresenter.BUNDLE_INVALID:
			return "!"
		StateBannerPresenter.TRACE_MISSING:
			return "?"
		StateBannerPresenter.STATE_DEGRADED:
			return "~"
		StateBannerPresenter.WAITING_NO_DECISION:
			return "..."
		StateBannerPresenter.FALLBACK_USED:
			return ">"
		StateBannerPresenter.FORCED_REPLACEMENT:
			return "R"
		StateBannerPresenter.TEAM_PREVIEW:
			return "T"
		StateBannerPresenter.DECISION_RECORDED:
			return "*"
		_:
			return "-"
