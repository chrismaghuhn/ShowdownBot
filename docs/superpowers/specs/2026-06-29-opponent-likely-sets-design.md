# Opponent Likely-Sets, Slice 1: realistic damage spread — Design

**Goal:** Stop modeling the opponent as the worst case in *every* dimension at
once (max offense **and** max bulk **and** max speed). For curated common species,
the opponent's mon uses a single **probable set** (realistic spread + item) in the
damage model — cutting the false threat that drives the bot's over-caution.

**Status:** approved (brainstorming, 2026-06-29). First slice of the larger
"opponent set model / Hirn-Dokument" vision (later slices: speed, moves,
team-preview matchup-awareness; and a generated-from-usage-stats source).

## Context

In `DamageModel` (`battle/evaluate.py`) every mon gets a `SetHypothesis` whose
`spreads` is the worst-case `SpreadBook` entry: as an attacker it uses the
OFFENSE preset (max damage), as a defender the DEFENSE preset (max bulk). So the
opponent is simultaneously the hardest-hitting *and* hardest-to-KO version of
itself — no real set is both. This systematically: (a) under-rates our own KOs
(their bulk over-modeled) → we don't commit to attacks; (b) over-rates incoming
(their offense over-modeled) → we protect/switch. Both feed the over-caution we
measured all session. We just did the exact analogue for OUR mons (Stage C real
spreads via `our_spreads`); this slice does it for the opponent, but with a
curated *likely* set (a prior, not known-real).

This slice is **damage spread only**. Speed (`opponent_range` still assumes
Scarf-max), opponent moves (`predict_responses`), and team preview are out of
scope. So is a probability distribution over sets (point estimate only) and a
usage-stats generator (curated only).

## Design (reuse the Stage C mechanism)

**Data — `config/formats/meta/likely_sets.yaml`:** per-species probable set,
curated for ~20-30 common Reg-G species, hand-authored from VGC meta knowledge:

```yaml
species:
  Incineroar:   {nature: Adamant, evs: {hp: 252, atk: 4, spd: 252}, item: Sitrus Berry}
  Flutter Mane: {nature: Timid,   evs: {spa: 252, spd: 4, spe: 252}, item: Choice Specs}
  # ... ~20-30 common Reg-G species
```

**Loader — `load_likely_sets(path) -> dict[str, SpeciesSpreads]`** (new, in
`engine/belief/hypotheses.py`, next to `load_spread_book` — it reuses
`SpreadPreset`/`SpeciesSpreads` and is format-meta like the book): builds, per species, a
`SpeciesSpreads(offense=likely, defense=likely)` where `likely =
SpreadPreset(nature, evs, items=[item])`. Both presets identical so the set is
used regardless of attacker/defender role — exactly the shape `our_spreads`
already produces. Missing file → empty dict (graceful: everything stays
worst-case, current behavior).

**Integration — `DamageModel.__init__`** gains `opp_sets: dict | None = None`,
applied as a sibling of the existing `our_spreads` branch:

```python
hyp = hypothesis_from_state(mon, book)
if side == our_side and our_spreads and mon.species in our_spreads:
    hyp.spreads = our_spreads[mon.species]
elif side == opp_side and opp_sets and mon.species in opp_sets:
    hyp.spreads = opp_sets[mon.species]   # curated likely set
self.hyps[(side, slot)] = hyp
```

**Graceful fallback:** only curated species get the realistic set; an un-curated
(off-meta) opponent stays **worst-case** — no risk, no surprise.

**Safety margin (approved):** the *spread* becomes realistic but the **damage
roll conventions are unchanged** — incoming still reads `res.max_damage` (max
roll). So "realistic, not panicked" yet not reckless: we stop over-modeling their
bulk/offense, but still assume the high roll.

**Threading:** `opp_sets` is format-level (like the `SpreadBook`). Loaded once
from `cfg.meta_path("likely_sets")` where the book is loaded
([runner.py](showdown_bot/src/showdown_bot/client/runner.py),
[gauntlet.py](showdown_bot/src/showdown_bot/client/gauntlet.py)), passed via
`choose_with_fallback(**deps) -> heuristic_choose_for_request(opp_sets=...) ->
DamageModel`. An env knob `SHOWDOWN_OPP_SETS` (default on; `=0` disables) enables
a clean on/off A/B.

## Testing
- Loader: `likely_sets.yaml` → per-species `SpeciesSpreads`, both presets equal;
  missing file → empty dict.
- `DamageModel`: a curated opponent (e.g. Incineroar) uses the likely set, not
  the worst-case DEFENSE preset (assert the defender hypothesis's evs/nature).
- Fallback: an un-curated opponent species keeps the worst-case book preset.
- Our-mon override still wins for our side (precedence unchanged).

## Verification (guardrail, not a tuning target)
- Full suite green.
- Gauntlet A/B `SHOWDOWN_OPP_SETS=1` vs `=0`: does realistic opponent modeling
  lower predicted-incoming / change behaviour (more committed attacks)? Read the
  diagnostic metrics, not just winrate (the mirror-vs-max_damage benchmark
  rewards recklessness — guardrail only).

## Non-goals (deferred)
Opponent speed (`opponent_range`), opponent moves (`predict_responses`), team
preview matchup-awareness; a distribution over sets; a usage-stats generator.
