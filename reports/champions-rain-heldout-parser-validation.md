# Champions rain held-out parser validation

**Date:** 2026-07-14 (updated after result-recording fix)
**Schedule:** `config/eval/schedules/champions_rain_heldout_parser_validation.yaml` (`schedule_hash: fe3c2b5227d74b4e`, `seed_base: champions-rain-heldout-parser-v0`)
**Scope:** parser / request / choose-path / result-recording safety only — not strength.

---

## Verdict: **PARSER/HARNESS SAFETY PASS** (2/2 result rows)

Rain-heldout validation completes with **2 `results.jsonl` rows** (`invalid=0`, `crashes=0`, `end_reason=normal`). This confirms:

1. Solar Beam release choose-path (from `4d985fc`) — targetless `/choose` when server omits `target`.
2. Gauntlet result recording — `parse_battle_result` resolves `winner_name` and `_battle_result_record` maps hero/villain.

**Not a strength claim.** Win/loss outcomes are incidental; the gate is parse + choose + row emission.

---

## Root cause (result-row harness blocker)

**Symptom:** Callback saw `winner=BaselineBot…` from `|win|…`, but `_battle_result_record` raised `winner None matches neither hero nor villain`; `results.jsonl` stayed empty.

**Mechanism:** Champions room logs include damage HP like `|-damage|p2b: Basculegion|20/100y` (max-HP suffix `y` without a space). `_hp_fraction()` called `float("100y")` → `ValueError`. The broad `try/except` in `parse_battle_result()` aborted the loop **before** the later `|win|` line, leaving `winner_name=None`.

**Not the cause:** duplicate empty win callbacks (already guarded in `on_hero_result`), hero/villain name mismatch, or missing `|win|` in room_frames.

**Fix:** Teach `_hp_fraction` to strip trailing alphabetic max-HP flags and return `None` on parse failure instead of raising.

---

## Fix history

| Slice | Verdict |
|-------|---------|
| Pre-`4d985fc` | FAIL — BOT-DECISION-BLOCKER (targeted Solar Beam release) |
| `4d985fc` | CHOOSE-PATH PASS · RESULT-ROW HARNESS BLOCKER |
| Result-recording fix (local) | PARSER/HARNESS SAFETY PASS |

---

## Validation run (post result-recording fix, 2026-07-14)

| Check | Result |
|-------|--------|
| Schedule rows | 2/2 |
| `results.jsonl` rows | **2** |
| `invalid_choices` | 0 |
| `crashes` | 0 |
| `winner` field | `hero` (seed_index 0), `villain` (seed_index 1) |
| `end_reason` | `normal` both rows |

Example row fields: `turns` 9 / 6, `end_hp_diff` populated, `normalized_room_log_sha256` set.

Note: CLI may exit non-zero if `seeds.jsonl` is missing/misaligned on a reused server (Channel A hygiene). Row emission succeeded independently.

---

## Tests

```
python -m pytest showdown_bot/tests/test_battle_parse.py \
  showdown_bot/tests/test_gauntlet_battle_result.py \
  showdown_bot/tests/test_gauntlet_duplicate_win_callback.py -q
# 23 passed (includes test_champions_hp_suffix_y_* )
```

---

## Changed files (this slice, uncommitted)

- `showdown_bot/src/showdown_bot/eval/battle_parse.py` — `_hp_fraction` handles `100y`-style suffix
- `showdown_bot/tests/test_battle_parse.py` — regression: suffix must not block winner parse
- `showdown_bot/tests/test_gauntlet_battle_result.py` — regression: `_battle_result_record` through suffix line

---

## Local artifacts (do not commit)

- `showdown_bot/data/eval/.../results.jsonl`, `seeds.jsonl`, `manifest`
- `data/eval/.../rain-heldout-parser-validation/` (diagnostic, room_raw_debug)
- `tools/_champions_rain_heldout_diagnostic.py`

---

## Non-claims

- No FormatConfig / panel / strength conclusions.
- No invalid-choice recovery.
- No push until Codex review.

---

## Follow-up (not this commit)

`parse_battle_result()` still wraps the entire line loop in one broad `try/except` (sets `hp_ok=False` on any exception). That is why an HP parse failure could abort winner/turn/player parsing. The `_hp_fraction` fix covers the known Champions `100y` case; a later harness-hardening slice should narrow the guard so HP surprises only disable `hp_by_slot` / `end_hp_diff`, never `winner_name` / `turns` / `players`.
