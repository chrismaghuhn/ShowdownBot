# Phase 1: Game Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** An offline engine that reconstructs battle state and reproduces damage. Exit criterion: in cases where both sets are known, calc results match stored battle logs in >= 95% of obvious single-target hits ("strict" validation).

**Architecture:** Pure-Python state/belief layer + a Node `@smogon/calc` bridge behind a transport-agnostic client. No search, no fusion, no team-preview agent yet.

**Tech Stack:** Python 3.11+, pyyaml, pydantic (reused), Node 22 + `@smogon/calc`, pytest.

**Depends on:** Phase 0/0.5 client, design spec `docs/superpowers/specs/2026-06-29-vgc-showdown-bot-design.md`.

---

## File Structure

```
showdown_bot/
  config/formats/
    gen9vgc2026regi.yaml            # regulation: level/restricted/tera + meta paths
    meta/
      default_spreads.yaml          # per-species offense/defense presets
      protect_priors.yaml           # Phase 2 stub
  tools/calc/
    package.json                    # @smogon/calc
    calc.mjs                        # stdin JSON array -> stdout result array
  src/showdown_bot/engine/
    format_config.py                # FormatConfig loader
    log_parser.py                   # LogEvent + parse_log
    state.py                        # BattleState/PokemonState/FieldState, from_log, merge_request
    validate.py                     # validate-log engine (in-range, strict/union)
    calc/
      models.py                     # CalcMon, DamageRequest, DamageResult
      client.py                     # CalcBackend Protocol, SubprocessCalcBackend, CalcClient
    belief/
      hypotheses.py                 # SetHypothesis + offense/defense presets (per-role)
      tracker.py                    # BeliefTracker (post-exit)
      game_mode.py                  # GameMode + compute_game_mode (post-exit)
  tests/
    fixtures/logs/sample_damage_turn.log
    fixtures/logs/validate_sample.log
    fixtures/logs/validate_sets.json
    test_format_config.py / test_log_parser.py / test_battle_state.py
    test_calc_client.py / test_hypotheses.py / test_validate_log.py
    test_belief_tracker.py / test_game_mode.py
```

`pyproject.toml`: added `pyyaml`; `@pytest.mark.integration` reused for calc-backed tests.

---

## Key design decisions (from review)

1. **Mode semantics fixed up front.** `offense` preset = max offense + min defense (applied to the attacking role); `defense` preset = max bulk (applied to the defending role). `SetHypothesis.as_attacker(mode, move)` / `as_defender(mode)` make the role explicit, so `game_mode` cannot invert.
2. **Transport-agnostic calc.** `CalcBackend` Protocol with `calc_batch`; Phase 1 uses `SubprocessCalcBackend` (one Node call per batch via a stdin array). A persistent backend can drop in for Phase 2 without caller changes. `DamageResult.rolls` carries the full 16-roll range.
3. **In-range validation.** A match is "observed value within `[min_roll, max_roll]`" in `% maxHP` (not `±10%`/`±16 HP`). Two buckets: `strict` (both sets known -> measures engine correctness, exit-relevant) and `union` (opponent defender -> union over plausible spreads, informative only). Showdown HP rounding absorbed via a per-defender tolerance. KOs handled via overkill (calc max must reach the remaining HP).
4. **`@smogon/calc` field, not format.** The bridge builds `Generations.get(9)` + `Field({gameType:'Doubles'})`; `format_id` only drives our own config/spread selection.

---

## Tasks (all complete)

- [x] **Task 1 — Format-Config:** `gen9vgc2026regi.yaml` + `FormatConfig` loader resolving meta paths. Tests: loads, `level==50`, meta paths exist.
- [x] **Task 2 — Log parser:** `LogEvent`/`PokemonId`/`HpStatus` + `parse_log`; handles switch/damage/heal/boost/weather/field/side/turn/move/faint/status/item. Fixture `sample_damage_turn.log`. Tests: Delibird damage, turn increments, faint/boost/enditem.
- [x] **Task 3 — BattleState:** `PokemonState`/`FieldState`/`BattleState` with `from_log`, `from_log_text`, and `merge_request` (private moves/HP). Tests: two active per side, damage/faint/Intimidate tracked, request merges moves.
- [x] **Task 4 — Calc bridge + client:** `calc.mjs` (batch, full rolls) + `CalcBackend`/`SubprocessCalcBackend`/`CalcClient` + `CalcMon`/`DamageRequest`/`DamageResult`. Tests: mocked backend mapping + ordering + error path; `@integration` Flare Blitz OHKO with 16 rolls.
- [x] **Task 5 — Set hypotheses:** `default_spreads.yaml` (~15 meta mons) + `SetHypothesis` with role-based `as_attacker`/`as_defender`. Tests: item candidates expand/collapse, offense vs defense presets differ, `@integration` offense hits harder than defense.
- [x] **Task 6 — validate-log (exit):** `engine/validate.py` + CLI `validate-log --log --sets --side --format`. Strict in-range check; KO overkill handling; union over presets. Tests: instance pairing skips recoil; `@integration` strict 3/3 == 100% (>= 95% exit); union runs without sets. CLI verified end-to-end.
- [x] **Task 7 — Belief tracker + game_mode (post-exit):** `BeliefTracker` (re-derives hypotheses on each event, records move order) + `compute_game_mode` with corrected logic (opponent always in `offense_mode` when attacking; `ahead` requires surviving offense_mode AND KOing a `defense_mode` opponent). Tests: tracker learns move/item + resyncs on switch; scripted-backend must_react/ahead/neutral.

---

## Exit verification

```bash
cd showdown_bot
python -m pytest -q                 # 57 passed (unit + integration)
python -m showdown_bot.cli validate-log \
  --log tests/fixtures/logs/validate_sample.log \
  --sets tests/fixtures/logs/validate_sets.json
# strict: 3/3 (100.0%) | union: 0/0 (n/a)
```

One-time setup: `cd tools/calc && npm install`.

---

## Handoff to Phase 2

- `compute_game_mode()` -> search weights (must_react/ahead/neutral).
- `CalcClient.damage_batch` + `SetHypothesis.as_attacker/as_defender` -> `ko_value`, `survive_next`; swap in a persistent `CalcBackend` for search throughput.
- `BattleState` + `BeliefTracker` feed `battle/decision.py`, replacing `random_agent` incrementally.
