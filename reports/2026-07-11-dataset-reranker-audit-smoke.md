# Dataset / Reranker Audit — reference smoke on `phase3-slice2b25a`

**Date:** 2026-07-11 · **Reference smoke only** — proves dataset/model *trust*, NOT play strength.
No golden counts are frozen; no rows were mutated, no training or battles were run, no held-out data
was touched.

## Command

```powershell
python -m showdown_bot.learning.audit `
  data/datasets/phase3-slice2b25a/dataset.jsonl.gz --out reports/audit-2b25a
```

## Provenance

| field | value |
|---|---|
| dataset | `data/datasets/phase3-slice2b25a/dataset.jsonl.gz` |
| dataset_sha256 (uncompressed JSONL) | `3303351176733fd373eed251a29d7f2bde0f3aa50b4a8fd407eff448f39542d6` |
| split | gamewise, seed 42, ratios 0.8/0.1/0.1 |
| split_sha256 | `a152785edd351ccd5ae2f6b799fe731060e628378dc937e51f8c30f825582a18` |
| games (train / validation / test) | 299 (239 / 30 / 30) |
| decisions | 3302 |
| metric blocks | distribution, duplicates, features, labels, model |
| wall time | ~475 s (near-duplicate detection is O(n²) per block; the smoke is `@pytest.mark.integration`, deselected by the default suite) |

## Status: `AUDIT FAIL` (honest — real findings, not a strength verdict)

`AUDIT FAIL` here means the audit surfaced genuine dataset issues, exactly as designed. It is **not**
a play-strength judgment. All findings below survived the reconciliation of the label checker with
the real `learning/teacher.py` labeler — the earlier ~594 tie-convention false-positives are gone.

| severity | code | count | note |
|---|---|---:|---|
| FAIL | NORMALIZED_MEAN_MISMATCH | 288 | ~9% of decisions; `counterfactual_value_normalized_within_decision` does not sum to ~0. **Real signal → spun off as an investigation ticket** (the normalized values look computed from a different candidate set/version than the stored raw; `value_gap_to_best` and ranks are 100% consistent). |
| FAIL | SEMANTIC_LABEL_CONTRADICTION | 5 | same semantic input + same teacher provenance, different labels — candidate real finding, not yet root-caused. |
| FAIL | SEMANTIC_CROSS_SPLIT_DUPLICATE | 1 | one semantic decision appears in two splits — candidate cross-split leakage worth a look. |
| WARN | CONSTANT_FEATURE | 8 | matches the known ~7 constant/dropped features (spec §21). |
| WARN | HIGH_SPEARMAN_CORRELATION | 2 | redundant numeric feature pairs. |
| WARN | SENTINEL_DOMINATED_FEATURE | 2 | ≥95% sentinel/missing. |
| WARN | NEAR_CROSS_SPLIT_DUPLICATE | 1 | near-duplicate across splits (below the exact threshold). |
| INFO | MIXED_PROVENANCE | 1 | the aggregate merges 4 panel shards (4 `config_hash`es); correctly INFO, not FAIL. |
| INFO | SEMANTIC_SAME_SPLIT_DUPLICATE | 1 | duplicate decision within one split. |
| INFO | TEAM_CATALOG_UNAVAILABLE | 1 | no team catalog supplied → team/archetype dimensions reported as unavailable. |

## Reading

- **No false positives after reconciliation.** The label rank/best/normalized checks were corrected
  to match `teacher.py` (strict-ordinal ranks with a candidate-id tiebreak; a single tie-broken
  best; spec's mean≈0 normalization). The feature denylist was corrected to exempt the documented
  `format_id` feature/metadata overlap.
- **The FAILs are genuine.** The dominant one (NORMALIZED_MEAN_MISMATCH) is a real property of the
  shipped 2b-2.5a labels and is tracked separately; the semantic contradiction/leakage findings are
  the exact diagnostics this audit exists to surface.
- **The WARNs match expectations** (constant/redundant/sentinel features, minor near-duplicate).

## Limitations

Reference smoke: verifies the audit runs end-to-end on the real corpus and produces a structurally
valid, internally consistent report. It does not freeze historical counts and does not attempt to
root-cause the surfaced findings. This audit is dataset/model trust only — no GO/NO-GO on winrate or
play strength, no held-out access, no battles, no training.
