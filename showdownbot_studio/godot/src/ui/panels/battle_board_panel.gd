class_name BattleBoardPanel
extends Control

@onready var _board_view: AbstractBoardView = $AbstractBoardView


func bind(live: LiveBattleSnapshot) -> void:
	_board_view.bind(LiveBoardPresentationAdapter.build_snapshot(live))


func get_board_view() -> AbstractBoardView:
	return _board_view
