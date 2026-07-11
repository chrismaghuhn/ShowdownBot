# tests/test_reranker_ablation.py
import json
from pathlib import Path

import pytest

lgb = pytest.importorskip("lightgbm")  # reranker_ablation imports reranker_train -> lightgbm

from showdown_bot.learning.dataset import (
    group_decisions, load_rows, split_by_game,
)
from showdown_bot.learning.reranker_ablation import (
    FEATURE_CLASSES, INCONCLUSIVE, LOAD_BEARING, MISC, NOT_APPLICABLE, PRUNABLE,
    SelfCheckError, VariantMetrics, _ablate_decisions, _classify, ablation_result_to_json,
    classify_verdict, dropped_constant_columns, format_ablation_report, main, partition_features,
    run_ablation, self_check,
)
import showdown_bot.learning.reranker_ablation as reranker_ablation
from showdown_bot.learning.reranker_features import (
    LABEL_DENYLIST, METADATA_DENYLIST, active_feature_names,
)
from showdown_bot.learning.reranker_train import attack_strict_decisions

# Committed 2b-2.5a dataset (repo root, not showdown_bot/) -- see
# reports/2026-07-11-2b25a-offline-eval.md for the pinned numbers this test
# file reproduces.
_DS = (Path(__file__).resolve().parents[2] / "data" / "datasets" / "phase3-slice2b25a"
       / "dataset.jsonl.gz")

# Committed offline-eval numbers (reports/2026-07-11-2b25a-offline-eval.md,
# "Final offline eval" table): dropped_constant 7, live 66, ATTACK-strict gate.
_COMMITTED_LIVE_FEATURE_COUNT = 66
_COMMITTED_ATTACK_MODEL_REGRET = 0.6172
_COMMITTED_ATTACK_HEURISTIC_REGRET = 2.2286
_COMMITTED_MODEL_WRONG_NEAR_EQUAL = 8


def _load_real_split():
    decisions = group_decisions(load_rows(str(_DS)))
    sp = split_by_game(decisions, seed=42)
    tr = attack_strict_decisions(sp.train)
    va = attack_strict_decisions(sp.val)
    te = attack_strict_decisions(sp.test)
    return tr, va, te


# --- partition_features: exhaustive + disjoint on the real live feature set ---

def test_partition_exhaustive_and_disjoint_on_committed_dataset():
    assert _DS.exists(), f"missing committed dataset artifact: {_DS}"
    tr, _va, _te = _load_real_split()
    live = active_feature_names(tr)
    assert len(live) == _COMMITTED_LIVE_FEATURE_COUNT

    partition = partition_features(live)

    # exhaustive: every live feature appears exactly once across all classes
    union = [n for members in partition.values() for n in members]
    assert sorted(union) == sorted(live)
    assert len(union) == len(set(union))            # disjoint (no duplicates)

    # misc is present (possibly empty) and its members are accessible
    assert MISC in partition
    assert isinstance(partition[MISC], list)

    # every declared class is present in the output, even if some end up empty
    for cls in FEATURE_CLASSES:
        assert cls in partition

    # spec-explicit, small/known classes (sanity-pin the exact membership;
    # order follows FEATURE_COLUMNS/live order, not declaration order)
    assert sorted(partition["weather_terrain"]) == sorted([
        "field_weather", "tailwind_ours", "tailwind_opp", "trick_room_active",
    ])
    assert partition["mirror"] == ["mirror_flag"]
    assert sorted(partition["species_id"]) == sorted([
        "slot1_actor_species_id", "slot2_actor_species_id",
        "slot1_switch_target_species_id", "slot2_switch_target_species_id",
        "slot1_target_species_id_if_known", "slot2_target_species_id_if_known",
    ])
    # a class removal changes the feature count by exactly len(class) -- spot
    # check on the real partition too
    for cls, members in partition.items():
        assert len(live) - len([f for f in live if f not in members]) == len(members)


def test_validate_partition_rejects_non_disjoint():
    # _classify is first-match-wins, so it can never itself produce an
    # overlapping assignment -- exercise the validator directly with a
    # hand-built, deliberately-broken partition dict to prove the disjoint
    # check actually fires.
    from showdown_bot.learning.reranker_ablation import _validate_partition

    bad = {"a": ["turn_number"], "b": ["turn_number"]}
    with pytest.raises(ValueError, match="not disjoint"):
        _validate_partition(bad, ["turn_number"])


def test_validate_partition_rejects_non_exhaustive():
    from showdown_bot.learning.reranker_ablation import _validate_partition

    bad = {"a": ["turn_number"]}
    with pytest.raises(ValueError, match="not exhaustive"):
        _validate_partition(bad, ["turn_number", "endgame_flag"])


def test_classify_known_columns():
    assert _classify("field_weather") == "weather_terrain"
    assert _classify("slot1_move_type") == "move_desc"
    assert _classify("slot2_is_protect") == "move_desc"          # NOT "protect" (explicit wins)
    assert _classify("slot1_actor_species_id") == "species_id"
    assert _classify("mirror_flag") == "mirror"
    assert _classify("predicted_outgoing_damage") == "damage"
    assert _classify("we_outspeed_count") == "speed"
    assert _classify("our_alive_count") == "board"
    assert _classify("protect_stall_penalty") == "protect"
    assert _classify("turn_number") == MISC


# --- loop mechanics: synthetic decisions fixture, real (tiny) LightGBM train ---

def _synth_rows(game_ids):
    rows = []
    gaps = [0.0, -0.3, -3.0, -8.0]
    for g in game_ids:
        for i, gap in enumerate(gaps):
            rows.append({
                "features": {
                    "slot1_move_id": "moonblast" if i % 2 == 0 else "tackle",
                    "heuristic_aggregate_score": 5.0 - i,
                    "predicted_outgoing_damage": 50.0 - 5 * i,
                },
                "metadata": {"game_id": g, "decision_id": f"{g}-d", "candidate_index": i},
                "label": {"teacher_best": i == 0, "chosen_by_current_heuristic": i == 0,
                          "value_gap_to_best": gap},
            })
    return rows


def _synth_decisions(n, offset=0):
    return group_decisions(_synth_rows([f"g{offset + i}" for i in range(n)]))


_SYNTH_LIVE = ["slot1_move_id", "heuristic_aggregate_score", "predicted_outgoing_damage"]


def _synth_ablation():
    tr = _synth_decisions(10)
    va = _synth_decisions(3, offset=100)
    te = _synth_decisions(3, offset=200)
    return _ablate_decisions(tr, va, te, _SYNTH_LIVE)


def test_synthetic_partition_has_empty_and_nonempty_classes():
    # predicted_outgoing_damage -> damage; slot1_move_id + heuristic_aggregate_score
    # -> misc (no explicit/prefix match); every other class is empty for this tiny
    # live set -- this fixture is deliberately chosen to exercise BOTH the
    # identity (empty-class) path and the count-delta (nonempty-class) path.
    partition = partition_features(_SYNTH_LIVE)
    assert partition["damage"] == ["predicted_outgoing_damage"]
    assert partition[MISC] == ["slot1_move_id", "heuristic_aggregate_score"]
    for cls in ("weather_terrain", "move_desc", "species_id", "mirror", "speed", "board", "protect"):
        assert partition[cls] == []


def test_loco_empty_class_is_identical_to_full():
    result = _synth_ablation()
    for cls in ("weather_terrain", "move_desc", "species_id", "mirror", "speed", "board", "protect"):
        assert result.partition[cls] == []
        variant = result.loco[cls]
        assert variant is not None
        assert variant.feature_names == result.full.feature_names
        assert variant.n_features == result.full.n_features
        assert variant.model_regret == result.full.model_regret
        assert variant.heuristic_regret == result.full.heuristic_regret
        assert variant.model_wrong_near_equal == result.full.model_wrong_near_equal
        assert variant.gate_pass == result.full.gate_pass
        assert variant.delta_vs_full == 0.0
        assert variant.variant == "LOCO"
        assert variant.class_name == cls
        # empty-class SCO is undefined (nothing to train on)
        assert result.sco[cls] is None


def test_loco_and_sco_feature_counts_change_by_exactly_len_class():
    result = _synth_ablation()
    live = result.live_features
    assert live == _SYNTH_LIVE

    for cls in ("damage", MISC):
        members = result.partition[cls]
        assert len(members) > 0
        loco_variant = result.loco[cls]
        sco_variant = result.sco[cls]
        assert loco_variant.n_features == len(live) - len(members)
        assert sco_variant.n_features == len(members)
        assert set(loco_variant.feature_names) == set(live) - set(members)
        assert set(sco_variant.feature_names) == set(members)
        # order is preserved from the live feature list
        assert loco_variant.feature_names == [f for f in live if f not in members]
        assert sco_variant.feature_names == [f for f in live if f in members]


def test_variant_metrics_never_contain_denied_columns():
    result = _synth_ablation()
    denylist = LABEL_DENYLIST | METADATA_DENYLIST
    all_variants = [result.full] + [v for v in result.loco.values() if v] + \
        [v for v in result.sco.values() if v]
    assert all_variants, "expected at least the FULL variant"
    for v in all_variants:
        assert isinstance(v, VariantMetrics)
        assert not (set(v.feature_names) & denylist)


def test_heuristic_regret_is_identical_across_variants():
    # heuristic_regret/heuristic_wrong_near_equal depend only on the fixed
    # chosen-vs-teacher gap, never on which features the MODEL trained on --
    # so they must be numerically constant across every FULL/LOCO/SCO variant
    # in a run (only model_regret / model_wrong_near_equal should vary).
    result = _synth_ablation()
    all_variants = [result.full] + [v for v in result.loco.values() if v] + \
        [v for v in result.sco.values() if v]
    heuristic_regrets = {v.heuristic_regret for v in all_variants}
    heuristic_wrongs = {v.heuristic_wrong_near_equal for v in all_variants}
    assert len(heuristic_regrets) == 1
    assert len(heuristic_wrongs) == 1


# --- real-data wiring proof (tiny slice + full committed reproduction) -------

def test_ablate_decisions_wires_real_feature_dicts_on_a_tiny_slice():
    # A small real slice (not synthetic strings): proves build_feature_matrix /
    # train_lambdarank / regret_metrics wiring against genuine feature values
    # (real categorical encodings, real move/species ids) without paying for
    # the full 300-game dataset in every test run.
    assert _DS.exists(), f"missing committed dataset artifact: {_DS}"
    tr_full, va_full, te_full = _load_real_split()
    tr, va, te = tr_full[:12], va_full[:4], te_full[:4]
    assert tr and va and te, "tiny slice must be non-empty in every split"

    live = active_feature_names(tr)
    assert live, "tiny real slice must still have >=1 live feature"

    result = _ablate_decisions(tr, va, te, live)
    assert result.full.variant == "FULL"
    assert result.full.n_features == len(live)
    assert sorted(n for members in result.partition.values() for n in members) == sorted(live)
    # every produced variant obeys INV-6 and reports a real gate_pass bool
    for v in [result.full] + [x for x in result.loco.values() if x] + \
            [x for x in result.sco.values() if x]:
        assert isinstance(v.gate_pass, bool)
        assert not (set(v.feature_names) & (LABEL_DENYLIST | METADATA_DENYLIST))


def test_run_ablation_full_variant_reproduces_committed_2b25a_numbers():
    # HARD REQUIREMENT: the harness must call the SAME code paths as
    # reranker_train.main, so the FULL-model ablation row reproduces the
    # committed 2b-2.5a offline-eval report exactly (float-exact -- same
    # split, same params, same data).
    assert _DS.exists(), f"missing committed dataset artifact: {_DS}"
    result = run_ablation(str(_DS))
    assert len(result.live_features) == _COMMITTED_LIVE_FEATURE_COUNT
    assert result.full.model_regret == _COMMITTED_ATTACK_MODEL_REGRET
    assert result.full.heuristic_regret == _COMMITTED_ATTACK_HEURISTIC_REGRET
    assert result.full.model_wrong_near_equal == _COMMITTED_MODEL_WRONG_NEAR_EQUAL
    assert result.full.gate_pass is True
    assert result.full.delta_vs_full == 0.0
    # partition covers the live set exhaustively + disjointly (Task 1's own check)
    union = sorted(n for members in result.partition.values() for n in members)
    assert union == sorted(result.live_features)


# --- Task 2: dropped_constant_columns / self-check ---------------------------

def test_dropped_constant_columns_matches_committed_set():
    assert _DS.exists(), f"missing committed dataset artifact: {_DS}"
    result = run_ablation(str(_DS))
    dropped = dropped_constant_columns(result.live_features)
    assert len(dropped) == 7
    # 6 class-B sentinel-capture columns + tera_used (per the 2b-2.5a report's
    # "still-dead" sections).
    assert sorted(dropped) == sorted([
        "action_economy_score", "fakeout_invalid_penalty", "protect_prior_target1",
        "protect_prior_target2", "screens_opp", "screens_ours", "tera_used",
    ])
    assert not (set(dropped) & (LABEL_DENYLIST | METADATA_DENYLIST))


def test_self_check_passes_on_committed_full_row():
    assert _DS.exists(), f"missing committed dataset artifact: {_DS}"
    result = run_ablation(str(_DS))
    dropped = dropped_constant_columns(result.live_features)
    self_check(result, dropped)  # must not raise


def test_self_check_raises_on_metric_mismatch():
    result = _synth_ablation()  # synthetic numbers never match the committed constants
    dropped = dropped_constant_columns(result.live_features)  # wrong count too (not 7)
    with pytest.raises(SelfCheckError, match="self-check FAILED"):
        self_check(result, dropped)


def test_self_check_error_message_lists_each_mismatch():
    result = _synth_ablation()
    try:
        self_check(result, dropped=[])
    except SelfCheckError as exc:
        msg = str(exc)
        assert "dropped_constant_columns count" in msg
        assert "model_regret" in msg
    else:
        pytest.fail("expected SelfCheckError")


# --- Task 2: verdict classification ------------------------------------------

def _variant(*, model_regret, gate_pass, delta_vs_full):
    return VariantMetrics(
        variant="LOCO", class_name="x", feature_names=["a"], n_features=1,
        model_regret=model_regret, heuristic_regret=2.0, model_wrong_near_equal=1,
        heuristic_wrong_near_equal=1, gate_pass=gate_pass, delta_vs_full=delta_vs_full,
    )


_FULL = _variant(model_regret=0.6, gate_pass=True, delta_vs_full=0.0)


def test_classify_verdict_load_bearing_when_gate_flips():
    loco = _variant(model_regret=1.0, gate_pass=False, delta_vs_full=0.4)
    assert classify_verdict(loco, None, _FULL) == LOAD_BEARING


def test_classify_verdict_load_bearing_on_material_absolute_delta():
    loco = _variant(model_regret=0.75, gate_pass=True, delta_vs_full=0.15)  # >= 0.10 abs
    assert classify_verdict(loco, None, _FULL) == LOAD_BEARING


def test_classify_verdict_load_bearing_on_material_relative_delta():
    # 0.6 * 0.15 = 0.09 relative threshold; use a small FULL regret so a small
    # absolute delta is still a large relative jump.
    full = _variant(model_regret=0.1, gate_pass=True, delta_vs_full=0.0)
    loco = _variant(model_regret=0.13, gate_pass=True, delta_vs_full=0.03)  # 30% relative
    assert classify_verdict(loco, None, full) == LOAD_BEARING


def test_classify_verdict_prunable_on_near_zero_delta_and_weak_sco():
    loco = _variant(model_regret=0.61, gate_pass=True, delta_vs_full=0.01)
    sco = _variant(model_regret=1.5, gate_pass=False, delta_vs_full=0.9)  # weak standalone
    assert classify_verdict(loco, sco, _FULL) == PRUNABLE


def test_classify_verdict_prunable_on_empty_class_with_no_sco():
    loco = _variant(model_regret=0.6, gate_pass=True, delta_vs_full=0.0)
    assert classify_verdict(loco, None, _FULL) == PRUNABLE


def test_classify_verdict_inconclusive_when_near_zero_delta_but_strong_sco():
    loco = _variant(model_regret=0.61, gate_pass=True, delta_vs_full=0.01)
    sco = _variant(model_regret=0.62, gate_pass=True, delta_vs_full=0.02)  # near FULL alone too
    assert classify_verdict(loco, sco, _FULL) == INCONCLUSIVE


def test_classify_verdict_inconclusive_on_mid_range_delta():
    loco = _variant(model_regret=0.65, gate_pass=True, delta_vs_full=0.05)  # between noise & material
    assert classify_verdict(loco, None, _FULL) == INCONCLUSIVE


def test_classify_verdict_not_applicable_when_loco_is_none():
    assert classify_verdict(None, None, _FULL) == NOT_APPLICABLE


# --- Task 2: report + JSON structure (small synthetic fixture run) -----------

def test_format_ablation_report_contains_required_sections():
    result = _synth_ablation()
    dropped = dropped_constant_columns(result.live_features)
    md = format_ablation_report(result, dropped)

    for header in (
        "# 2b-2b Feature Ablation", "## Self-check", "## Feature-class partition",
        "## LOCO — leave-one-class-out", "## SCO — single-class-only", "## Verdicts",
        "## Caveats", "## Reproduction",
    ):
        assert header in md, f"missing section: {header}"

    # every partition class (incl. misc) appears in the partition table
    for cls in result.partition:
        assert f"| {cls} |" in md

    # LOCO table is sorted by delta descending (most load-bearing first)
    lines = md.splitlines()
    loco_start = next(i for i, l in enumerate(lines) if l.startswith("| class | features removed"))
    table_rows = []
    for line in lines[loco_start + 2:]:
        if not line.startswith("|"):
            break
        table_rows.append(line)
    row_deltas = [float(row.split("|")[4].strip()) for row in table_rows]
    assert row_deltas == sorted(row_deltas, reverse=True)


def test_ablation_result_to_json_contains_required_keys():
    result = _synth_ablation()
    dropped = dropped_constant_columns(result.live_features)
    obj = ablation_result_to_json(result, dropped)

    for key in (
        "dataset_path", "dataset_sha256", "split_seed", "live_feature_count", "live_features",
        "dropped_constant_columns", "dropped_constant_count", "partition", "full", "loco", "sco",
        "verdicts", "verdict_thresholds",
    ):
        assert key in obj

    assert obj["full"]["variant"] == "FULL"
    assert set(obj["partition"]) == set(result.partition)
    assert set(obj["loco"]) == set(result.partition)
    assert set(obj["sco"]) == set(result.partition)
    assert set(obj["verdicts"]) == set(result.partition)
    for v in obj["verdicts"].values():
        assert v in (LOAD_BEARING, PRUNABLE, INCONCLUSIVE, NOT_APPLICABLE)

    # deterministic, pretty-printed, key-sorted JSON round-trips cleanly
    dumped = json.dumps(obj, indent=2, sort_keys=True)
    assert json.loads(dumped) == obj
    dumped_again = json.dumps(obj, indent=2, sort_keys=True)
    assert dumped == dumped_again


def test_main_writes_report_and_json_from_small_fixture(tmp_path, monkeypatch):
    # CLI wiring test: monkeypatch run_ablation to the cheap synthetic loop (the
    # real 30-60s full run is executed once, separately, to produce the
    # committed artifacts -- this test only proves main()'s plumbing).
    monkeypatch.setattr(
        reranker_ablation, "run_ablation",
        lambda dataset_path, *, split_seed=42: _synth_ablation(),
    )
    monkeypatch.setattr(reranker_ablation, "self_check", lambda result, dropped: None)

    out_report = tmp_path / "report.md"
    out_json = tmp_path / "report.json"
    main([
        "unused-dataset-path.jsonl.gz",
        "--out-report", str(out_report),
        "--out-json", str(out_json),
    ])

    assert out_report.exists()
    assert out_json.exists()
    md = out_report.read_text(encoding="utf-8")
    assert "# 2b-2b Feature Ablation" in md
    raw = out_json.read_text(encoding="utf-8")
    assert raw.endswith("\n")
    obj = json.loads(raw)
    assert "verdicts" in obj and "full" in obj
