from dataclasses import replace
import json
import pytest

from showdown_bot.analysis.generalisation.contracts import (
    AnalysisPolicy, SchemaError, canonical_json, load_policy, sha256_id,
)


def test_canonical_hash_is_order_independent():
    assert canonical_json({"b": 2, "a": 1}) == '{"a":1,"b":2}'
    assert sha256_id({"a": 1, "b": 2}) == sha256_id({"b": 2, "a": 1})


def test_default_policy_is_exact(tmp_path):
    path = tmp_path / "policy.yaml"
    path.write_text("""schema_version: generalisation-policy-v1
confidence_level: 0.95
alpha: 0.05
descriptive_min_unique_seeds_per_cell: 10
gate_min_unique_seeds_per_cell: 30
required_cell_coverage: 1.0
required_pairing_coverage: 1.0
bootstrap_replicates: 10000
bootstrap_seed: 20260712
regression_margin: 0.02
improvement_margin: 0.0
tie_mode: non_win
multiple_testing: holm
planner_seed: 20260712
allow_nonreproducible_policies: false
""", encoding="utf-8")
    policy = load_policy(path)
    assert policy.gate_min_unique_seeds_per_cell == 30
    assert policy.required_cell_coverage == 1.0
    assert len(policy.policy_hash) == 64


def test_policy_rejects_unknown_key_and_partial_coverage(tmp_path):
    base = AnalysisPolicy()
    with pytest.raises(SchemaError, match="required_cell_coverage"):
        replace(base, required_cell_coverage=0.9).validate()
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"schema_version": "generalisation-policy-v1", "extra": 1}),
                    encoding="utf-8")
    with pytest.raises(SchemaError, match="unknown fields"):
        load_policy(path)
