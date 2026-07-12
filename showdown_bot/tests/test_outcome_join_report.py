from showdown_bot.learning.outcome_join.report import build_report, format_json, format_md

def _group_result(team, labelled, skipped_reason=None, constants=(True, 0),
                  dist=None, turn_violations=0):
    return {"team_hash": team, "labelled": labelled, "skipped_reason": skipped_reason,
            "constants": list(constants), "distribution": dist or {},
            "turn_violations": turn_violations}

def test_report_is_deterministic_and_flags_incomplete():
    r1 = build_report(dataset_sha="d", groups=[
        _group_result("t2", 0, skipped_reason="no_cover"),
        _group_result("t1", 75, dist={"hero": 40, "villain": 33, "tie": 2})])
    r2 = build_report(dataset_sha="d", groups=[
        _group_result("t1", 75, dist={"hero": 40, "villain": 33, "tie": 2}),
        _group_result("t2", 0, skipped_reason="no_cover")])
    assert format_json(r1) == format_json(r2)          # order-independent
    assert r1["status"] == "INCOMPLETE"                # a group was skipped
    assert "t2" in format_md(r1)
