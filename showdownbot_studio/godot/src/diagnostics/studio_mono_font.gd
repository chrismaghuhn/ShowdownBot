class_name StudioMonoFont
extends RefCounted

## Offline monospace font helper (Plan E §4.6 / Choice Point B Auflage).
## Godot's portable "monospace" SystemFont alias resolves to the platform
## monospace face without bundling any font file or loading a network font
## (B2 CLOSED — §0.8 / §0.13). Apply to hash/raw-evidence surfaces only;
## UI chrome keeps the default sans system stack (§0.9).


static func system_mono() -> SystemFont:
	var font := SystemFont.new()
	font.font_names = PackedStringArray(["monospace"])
	return font


static func apply_to(control: Control) -> void:
	control.add_theme_font_override(&"font", system_mono())
