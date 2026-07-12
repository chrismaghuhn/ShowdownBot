from showdown_bot.analysis.generalisation.log_features import classify_room_log


def _log(tmp_path, lines):
    path = tmp_path / "battle.log"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def test_classifies_side_leads_and_speed_control(tmp_path):
    path = _log(tmp_path, [
        "|player|p1|HeuristicBot123|1|", "|player|p2|BaselineBot123|1|",
        "|switch|p1a: Tornadus|Tornadus, L50|100/100",
        "|switch|p1b: Urshifu|Urshifu, L50|100/100",
        "|switch|p2a: Indeedee-F|Indeedee-F, L50|100/100",
        "|switch|p2b: Armarouge|Armarouge, L50|100/100", "|turn|1",
        "|move|p1a: Tornadus|Tailwind|p1a: Tornadus",
        "|-sidestart|p1: HeuristicBot123|move: Tailwind",
        "|move|p2b: Armarouge|Trick Room|p2b: Armarouge",
        "|-fieldstart|move: Trick Room", "|win|HeuristicBot123",
    ])
    value = classify_room_log(path)
    assert value.hero_side == "p1"
    assert value.hero_lead == ("tornadus", "urshifu")
    assert value.opponent_lead == ("indeedeef", "armarouge")
    assert value.hero_speed_control == ("tailwind", "trick_room")
    assert value.opponent_speed_control == ("trick_room",)


def test_drag_before_turn_makes_only_that_lead_unavailable(tmp_path):
    path = _log(tmp_path, [
        "|player|p1|HeuristicBot1|1|", "|player|p2|BaselineBot1|1|",
        "|switch|p1a: A|A, L50|100/100", "|drag|p1b: B|B, L50|100/100",
        "|switch|p2a: C|C, L50|100/100", "|switch|p2b: D|D, L50|100/100",
        "|turn|1", "|tie",
    ])
    value = classify_room_log(path)
    assert value.hero_lead == "unavailable"
    assert value.opponent_lead == ("c", "d")


def test_unknown_names_never_guess_hero_side(tmp_path):
    path = _log(tmp_path, ["|player|p1|Alice|1|", "|player|p2|Bob|1|", "|tie"])
    value = classify_room_log(path)
    assert value.hero_side == "unavailable"
