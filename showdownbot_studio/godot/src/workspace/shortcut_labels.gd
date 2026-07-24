class_name ShortcutLabels
extends RefCounted

## Plan E Task E4 (§4.5) — Ctrl vs Cmd label for shortcut hints.


static func mod_key() -> String:
	return "Cmd" if OS.get_name() == "macOS" else "Ctrl"
