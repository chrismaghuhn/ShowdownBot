# Champions rain held-out parser validation

**Date:** 2026-07-14 (updated after Solar Beam release fix)
**Schedule:** `config/eval/schedules/champions_rain_heldout_parser_validation.yaml` (`schedule_hash: fe3c2b5227d74b4e`, `seed_base: champions-rain-heldout-parser-v0`)
**Scope:** parser / request / choose-path safety only.

---

## Verdict: **CHOOSE-PATH PASS · RESULT-ROW HARNESS BLOCKER**

The Solar Beam release invalid-choice blocker is **cleared**. After removing MoveMeta target backfill and treating `move.target is None` as targetless in `_move_targets`, rain held-out battles complete without invalid Solar Beam choices or choose-path timeout.

This is **not** a full gauntlet/pipeline PASS: `results.jsonl` has **0 rows**. Gauntlet logged `winner None matches neither hero nor villain` on battle end (`invalid=0`, `crashes=0`). Result recording is a **separate harness blocker**, not a parser/choose regression in this slice.

---

## Fix summary (this slice)

| Change | File |
|--------|------|
| Removed `@model_validator` MoveMeta target backfill | `showdown_bot/src/showdown_bot/models/request.py` |
| `_move_targets(None) → [None]` | `showdown_bot/src/showdown_bot/battle/legal_actions.py` |
| Turn-6 release fixture + regression tests | `showdown_bot/tests/fixtures/request_champions_solarbeam_release.json`, `test_request_models.py`, `test_legal_actions.py` |

**Semantics:** Server omitting `target` on a move slot means targetless `/choose`. Explicit `"target": "normal"` in the request still yields `[1, 2]` legal targets.

---

## Run history

### Run 1 (pre-fix, backfill active)

- **Verdict:** FAIL — BOT-DECISION-BLOCKER
- Battle `HeuristicBot9603` vs `BaselineBot9603`: Turn 6 hang
- Turn-6 minimal Solar Beam → backfill `target="normal"` → `/choose move 1 2` → server rejected

### Run 2 (post-fix, 2026-07-14T16:33 UTC)

| Check | Result |
|-------|--------|
| Fresh Showdown server | yes |
| Single diagnostic gauntlet process | yes |
| Schedule rows executed | 2/2 (heuristic + max_damage opp) |
| `invalid_choices` | 0 |
| `crashes` | 0 |
| Solar Beam release invalid-choice hang | **none** |
| `results.jsonl` rows | **0** (harness winner-name mismatch) |

**Key diagnostic evidence** — battle `battle-gen9championsvgc2026regma-1263`, BaselineBot charge-release (minimal slot):

- Request: `{"move":"Solar Beam","id":"solarbeam"}` only, `trapped: true`
- `validate`: OK, `legal_pairs`: 2
- **`/choose`:** `/choose move 1, move 2 1|23` (Solar Beam **without** target digit)
- No `INVALID CHOICE` warning; battle proceeded to completion

Turn 5 charge start in same battle still used full slot with `"target": "normal"` → targeted `/choose move 1 2, move 2 1|19` (correct).

---

## Classification (post-fix)

| Class | Applies? |
|-------|----------|
| SAME-BLOCKER | No |
| NEW-PARSER-BLOCKER | No |
| BOT-DECISION-BLOCKER (Solar Beam release) | **No** — fixed |
| HARNESS-BLOCKER (result row / winner=None) | **Yes** — separate from choose-path fix |
| CHOOSE-PATH PASS | **Yes** |
| Full pipeline PASS | **No** — 0 result rows |

---

## Verification

```
python -m pytest showdown_bot/tests/test_request_models.py \
  showdown_bot/tests/test_actions.py \
  showdown_bot/tests/test_legal_actions.py \
  showdown_bot/tests/test_decide_adapter.py -q
# 34 passed (post-fix count includes new Solar Beam tests)
```

`git diff --check`: clean on committed-scope files.

---

## Artifacts (local, do not commit)

| Path | Notes |
|------|-------|
| `data/eval/.../rain-heldout-parser-validation/diagnostic.jsonl` | Run 2 diagnostic log |
| `showdown_bot/data/eval/.../` | Wrong relative output path |
| `tools/_champions_rain_heldout_diagnostic.py` | Local instrumentation only |

---

## Non-claims

- No strength / win-rate conclusions.
- No FormatConfig or panel changes.
- Invalid-choice recovery not implemented.
- Result-row harness fix not in scope.
- No push.
