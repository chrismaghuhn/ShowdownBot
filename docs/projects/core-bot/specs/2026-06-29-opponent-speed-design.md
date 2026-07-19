# Opponent Likely-Sets, Slice 2: realistic speed — Design

**Goal:** Model a curated opponent's speed from its probable set (spread + item,
Scarf-aware) instead of assuming every opponent is a Jolly-252-Spe-Choice-Scarf
speed demon. Removes the last big false-threat dimension and lets our (now
correctly-known) fast mons actually outspeed correctly-slow opponents.

**Status:** approved (brainstorming, 2026-06-29). Slice 2 of the opponent set
model; slice 1 (damage spread) is built and confirmed a major lever. Still
deferred: opponent moves, team preview, a distribution over sets.

## Context

`battle/opponent.py::predict_responses` builds opponent responses; the inner
`opp_speed(slot)` returns `speed_oracle.opponent_range(mon, field, opp_side,
book=book).max` — the **pessimistic max** (a +nature, 252-Spe, **Scarf-assumed**
build) for EVERY opponent, so even a bulky Careful Incineroar is modeled as a
speed demon. We now have `opp_sets` (curated `{to_id(species): SpeciesSpreads}`,
slice 1) threaded into the decision; use it to compute a realistic point speed.

The speed machinery (`engine/speed.py`) is sound: `effective_speed` applies
boosts/Tailwind(×2)/paralysis(÷2)/Scarf(×1.5)/booster(×1.5) and excludes Trick
Room; `speed_modifiers_from_state` derives the kwargs from observed state.

## Core algorithm

```
opp_speed(slot):
    if SHOWDOWN_OPP_SPEED disabled:           return opponent_range(...).max
    if to_id(species) not in opp_sets:        return opponent_range(...).max   # worst-case fallback
    preset = opp_sets[to_id(species)].defense  # the single likely set (offense==defense)
    item_for_speed = (
        None                if mon.item_lost                  # known absent -> no item
        else mon.item       if mon.item_known                 # revealed item wins
        else (preset.items[0] if preset.items else None)      # else curated item
    )
    return speed_oracle.likely_speed(mon, field, opp_side, preset, item_for_speed)
```

```
SpeedOracle.likely_speed(mon, field, side, preset, item_for_speed):
    base = cached_base_speed(mon.species, preset.nature, preset.evs)  # ivs=31, level=50
    mods = speed_modifiers_from_state(mon, field, side)               # boosts/Tailwind/para/booster(from state)
    mods["scarf"] = item_for_speed in ("Choice Scarf", "choicescarf") # ONLY Scarf is read from the item;
    # booster_speed is left exactly as state gave it (guardrail 2 -- never set from a curated item)
    return effective_speed(base, **mods)
```

## Guardrails (all required)

1. **Revealed item / `item_lost` always wins over the curated item — both
   directions.** `item_for_speed` is the revealed item if `item_known`, `None`
   if `item_lost` (known absent), else the curated item. So: curated Scarf but a
   revealed Sitrus → no Scarf speed; curated Scarf but `|-enditem|`/Knock Off
   (`item_lost`) → no Scarf speed; curated non-Scarf but a **revealed** Scarf →
   Scarf speed. No false positive-confidence.

2. **Booster Energy is not applied blindly from a likely item.** Only **Choice
   Scarf** (curated or revealed) feeds the speed directly. A curated/likely
   **Booster Energy** does NOT set `booster_speed` — that stays driven by state
   (`speed_modifiers_from_state`, off unless a Protosynthesis/Quark-Drive speed
   boost is known active). Otherwise we'd re-inflate opponent speed.

3. **Cache `stats_batch`.** `likely_speed` must not call the backend per action.
   Cache base speed by `(species_id, nature, frozenset(evs.items()), ivs, level)
   -> base_speed`; recompute only `effective_speed` per turn from state mods.
   `predict_responses` runs several times per decision, so this matters.

4. **Level/IVs explicit.** VGC `level = 50`; `ivs = 31` for any stat the likely
   set doesn't specify (the likely set only carries EVs/nature). No silent speed
   drift.

5. **`SHOWDOWN_OPP_SPEED` gates cleanly.** `=0` → always `opponent_range.max`;
   `=1` → `likely_speed` only for a validated curated species; **default = on iff
   `SHOWDOWN_OPP_SETS` is on and `likely_sets.yaml` validates** (i.e. `opp_sets`
   is non-empty — which already requires that). Lets us A/B the speed slice in
   isolation from the damage slice.

## Threading

`predict_responses(..., opp_sets=None)`; `decision.py` passes the `opp_sets` it
already holds. `opp_speed` (a closure in `predict_responses`) captures `opp_sets`,
`speed_oracle`, `to_id`. The base-speed cache lives on the `SpeedOracle`.

## Testing
- bulky Incineroar (Careful, no Spe EVs) → slow; Scarf Landorus-T (curated Choice
  Scarf) → fast (×1.5).
- **likely Scarf applies only when item unknown**; a **revealed non-Scarf**
  overrides a likely Scarf; a **known `item_lost`** disables likely Scarf; a
  curated **Booster Energy** does NOT apply a speed boost unless the booster
  state is active.
- un-curated species → `opponent_range.max` unchanged.
- `SHOWDOWN_OPP_SPEED=0` → bit-identical to current behaviour (always `.max`).
- base-speed cache: a second `likely_speed` for the same (species, nature, evs)
  does not call `stats_batch` again.

## Verification (guardrail, not a tuning target)
Full suite green; gauntlet A/B `SHOWDOWN_OPP_SPEED=1` vs `=0` (with `OPP_SETS` on)
— read whether more of our fast mons are modeled as outspeeding (move-order
changes, speed-control value), not just winrate.

## Non-goals (deferred)
Opponent moves, team preview; a distribution over sets; speed inference beyond
`item_known` (e.g. "they moved first, so they have Scarf").
