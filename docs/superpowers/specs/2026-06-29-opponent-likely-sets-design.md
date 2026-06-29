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
curated for ~20-30 common Reg-G species. `nature`/`evs` are the **spread**
(always used when the species is curated + the field is unknown); `item` is an
**optional, separate** prior — items vary more than spreads and a wrong item
(Specs/Band/AV) shifts damage hard, so a species may omit it and `item` is held
as its own field, easy to disable later. `set_id`/`source`/`confidence`/
`item_confidence` are metadata (unused by v1 logic; kept for debugging + future):

```yaml
species:
  Incineroar:
    set_id: bulky_support
    nature: Careful
    evs: {hp: 252, atk: 4, spd: 252}
    item: Sitrus Berry
    item_confidence: medium
    source: curated_reg_g
    confidence: medium
  Flutter Mane:
    set_id: specs_fast
    nature: Timid
    evs: {spa: 252, spd: 4, spe: 252}
    item: Choice Specs
    item_confidence: medium
    source: curated_reg_g
    confidence: medium
  # ... ~20-30 common Reg-G species
```

**Canonical species keys (required):** every key is normalized to the dex
canonical species (via `to_id` + a known-species check); a key that does not
resolve to a real species — a typo or shorthand like `Landorus-T`, `Fluttermane`,
`Landorus Therian` — **fails schema validation loudly** (no silent misses).
Lookups normalize `mon.species` through the same function so they always agree.

**Loader — `load_likely_sets(path) -> dict[str, SpeciesSpreads]`** (new, in
`engine/belief/hypotheses.py`, next to `load_spread_book` — reuses
`SpreadPreset`/`SpeciesSpreads`, format-meta like the book): for each species it
**canonicalizes the key** (failing loudly on an unknown species) and builds
`SpeciesSpreads(offense=likely, defense=likely)` with `likely =
SpreadPreset(nature, evs, items=[item] if item else [])` — both presets identical
so role doesn't matter (the shape `our_spreads` already produces), and an omitted
`item` → no item prior. Missing file → empty dict; a malformed/invalid file (bad
species key, missing nature/evs) → caught at the call site → empty dict + a log
warning, so a broken YAML can never silently corrupt opponent modeling.

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

**Precedence — revealed info always wins:** (1) revealed protocol info wins
(revealed item via `|-item|`; consumed/removed via `|-enditem|` → `item_lost`;
later: revealed ability/moves); (2) the likely set fills only **unknown** fields;
(3) no curated entry → worst-case fallback. For the item this is **already
enforced** by the `item_known` gate in `SetHypothesis._to_calc_mon` (revealed →
`self.item`; else → the likely set's `items[0]`): an Incineroar curated as Sitrus
that *reveals* Assault Vest is calc'd with Assault Vest. The spread (EVs/nature)
is never revealed, so the likely spread always applies. Constraint: setting
`hyp.spreads` must NOT touch `hyp.item` / `hyp.item_known` (it doesn't) — revealed
items must survive.

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
DamageModel`.

**Env knob `SHOWDOWN_OPP_SETS`:** `=0` disables; `=1` enables; **default =
enabled only if `likely_sets.yaml` exists AND validates** (missing/invalid file →
off → worst-case, i.e. current behaviour). A wrong prior changes a lot of
behaviour, so the default never silently activates a broken file. (Option: keep
it default-off during initial rollout until the A/B is clean, then flip to on.)

## Testing
- Loader: `likely_sets.yaml` → per-species `SpeciesSpreads`, both presets equal;
  missing file → empty dict; an omitted `item` → `items == []` (no item prior).
- `DamageModel`: a curated opponent (e.g. Incineroar) uses the likely set, not
  the worst-case DEFENSE preset (assert the defender hypothesis's evs/nature).
- Fallback: an un-curated opponent species keeps the worst-case book preset (no
  behaviour change).
- Our-mon override still wins for our side (precedence unchanged).
- **Revealed item wins:** an opponent curated as Sitrus but with a revealed
  Assault Vest (`item_known=True`) is calc'd with Assault Vest, not the prior.
- **Canonicalization:** `Landorus-Therian` resolves and matches `mon.species`; an
  **invalid species key** (`Landorus-T`, `Fluttermane`) **fails validation**.
- **A/B cleanliness:** `SHOWDOWN_OPP_SETS=0` → behaviour **bit-identical** to the
  current baseline (no opp_sets applied) — critical for clean A/Bs.

## Verification (guardrail, not a tuning target)
- Full suite green.
- Gauntlet A/B `SHOWDOWN_OPP_SETS=1` vs `=0`: does realistic opponent modeling
  lower predicted-incoming / change behaviour (more committed attacks)? Read the
  diagnostic metrics, not just winrate (the mirror-vs-max_damage benchmark
  rewards recklessness — guardrail only).

## Non-goals (deferred)
Opponent speed (`opponent_range`), opponent moves (`predict_responses`), team
preview matchup-awareness; a distribution over sets; a usage-stats generator.
