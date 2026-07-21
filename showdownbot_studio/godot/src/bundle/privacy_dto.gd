class_name PrivacyDTO
extends RefCounted

var _sealed: bool = false
var _profile: String = ""
var _chat: String = ""
var _private_messages: String = ""
var _player_names: String = ""
var _source_url: String = ""
var _raw_source_included: bool = false

var profile: String:
	get:
		return _profile
	set(value):
		if _sealed:
			return
		_profile = value

var chat: String:
	get:
		return _chat
	set(value):
		if _sealed:
			return
		_chat = value

var private_messages: String:
	get:
		return _private_messages
	set(value):
		if _sealed:
			return
		_private_messages = value

var player_names: String:
	get:
		return _player_names
	set(value):
		if _sealed:
			return
		_player_names = value

var source_url: String:
	get:
		return _source_url
	set(value):
		if _sealed:
			return
		_source_url = value

var raw_source_included: bool:
	get:
		return _raw_source_included
	set(value):
		if _sealed:
			return
		_raw_source_included = value


func seal() -> void:
	if _sealed:
		return
	_sealed = true
