# Champions `pkmn/ps` Protocol-/Client-Differential-Audit (I7 Design Input)

**Date:** 2026-07-14 (rev. 3 — design-input-ready)
**Verdict:** **Reference useful; not a rewrite target**
**Readiness:** **Design-input-ready** for a separate I7 design spec — **not** implementation-plan-ready
**Scope:** Read-only differential audit — no production code, no dependency uptake.
**Ground truth:** Pinned Showdown `f8ac140` @ `~/.cache/showdownbot/pokemon-showdown`
**Comparison oracle:** `@pkmn/protocol@0.7.3`, `@pkmn/client@0.7.3` (npm, MIT, repo `github:pkmn/ps`)

## Executive summary

Our request → legal-actions → `/choose` → trace pipeline is **aligned with Showdown ground truth** on
the audited non-Mega cases (move slots, Solar Beam `target`-omission pattern, HP suffix grammar). **Mega
Evolution is the blocking gap** and is **not Tera-isomorphic**: Mega changes form, stats, types, ability,
and sometimes weather **before the chosen move resolves**. A `_maybe_mega` overlay that only flips a flag
on the pre-mega line would still score the **base form** and can systematically wrong-rank Mega turns.

**Belastbar (sim-proven):** `canMegaEvo: true` in request JSON; `mega` choice token; one Mega per side
per battle; both active slots may simultaneously offer Mega when each holds a stone; no `@pkmn/ps`
runtime dependency warranted.

**Next artifact:** a **separate I7 design spec** (interfaces below) → then an implementation plan.
This report is audit + design **input** only.

### I7 slice sketch (input, not plan)

| Slice | Intent | Gate |
|-------|--------|------|
| **I7a** | Own-side Mega: parse/encode/enumerate, **pre-turn form projection**, effects before planning | Legal Mega choices; own-side ranking uses mega form |
| **I7b** | Opponent Mega in **response model** (foe Mega before foe move executes) | Champions **strength eval** until I7b |
| **Trace** | **`decision-trace-v3`** + candidate-key payload **v2** | No silent trace-v2 / key-v1 extension |

---

## Pinning and license

| Package | Version | License | Repository | Role |
|---------|---------|---------|------------|------|
| `@pkmn/protocol` | **0.7.3** | MIT | `github:pkmn/ps` | Request JSON, `parseRequest`, `parseHealth`, `parseBattleLine` |
| `@pkmn/client` | **0.7.3** | MIT | `github:pkmn/ps` | PS-client handlers — reference only |
| Pokémon Showdown sim | **f8ac140** | MIT | smogon/pokemon-showdown | **Ground truth** |

**Boundary:** “pkmn parses it” ≠ “Showdown accepts it.”

---

## Correction log

| Rev | Change |
|-----|--------|
| 2 | Mega ≠ Tera; I7b foe response gate; trace-v3; pkmn `-mega` defect documented; HP/Solar fidelity |
| 3 | **Corrected pkmn probe** (3-arg GT line); **`_plan_my_actions` speed timing**; design-input readiness; open interfaces listed; HP y+g live consistent; trailing whitespace removed |

---

## pkmn `-mega` probe (corrected)

Rev. 1–2 documented a **two-arg** synthetic line. **Fixed** in `run_pkmn_probes.mjs` and re-run.

**Ground-truth line (Showdown sim):**

```text
|-mega|p1a: Charizard|Charizard|Charizardite Y
```

**`Protocol.parseBattleLine` result (`@pkmn/protocol@0.7.3`):**

| Field | Value |
|-------|-------|
| `prefix` | `-mega` |
| `arg_count` | **3** |
| `args[0]` | `p1a: Charizard` |
| `args[1]` | `Charizard` |
| `args[2]` | `Charizardite Y` |

Artifact: `%USERPROFILE%\.cache\showdownbot\pkmn-audit-0.7.3\out\pkmn_probes.json` (case
`protocol_mega_line_ground_truth`).

**Client split (reference, not GT):** `|detailschange|` → form/ability; `Handler.mega()` → **item only**.

---

## Same-turn speed: must precede `_plan_my_actions`

Mega speed recalc affects **turn order**. In our stack, `PlannedAction.speed` is assigned in
`_plan_my_actions` **before** `evaluate_line` / `resolve`:

```186:228:showdown_bot/src/showdown_bot/battle/decision.py
def _plan_my_actions(
    req: BattleRequest,
    ja: JointAction,
    *,
    state: BattleState,
    our_side: str,
    opp_side: str,
    speed_oracle: SpeedOracle | None,
) -> list[PlannedAction]:
    ...
        if speed_oracle is not None and mon is not None:
            speed = speed_oracle.our_speed(base_spe, mon, state.field, our_side)
        else:
            speed = base_spe
    ...
        plans.append(
            PlannedAction(
                our_side, slot, kind, speed=speed, move=meta, target=target,
                is_ours=True, is_tera=sa.terastallize,
            )
        )
```

**Design input:** Mega form projection (stats/types/ability/weather) must feed **`speed_oracle` and/or
the `PokemonState` read here** — projecting only inside `evaluate_line`/`resolve` is **too late** for
speed-ordered scoring and one-ply ordering. This is a **P0 design constraint** for the I7 spec.

---

## Mega is not Tera-isomorphic

| Dimension | Terastallize | Mega |
|-----------|--------------|------|
| Pre-move mutation | Mostly type overlay on same species | **Full forme**: stats, types, ability |
| Weather | Rare at click | **Mega-Y → Drought** same turn |
| Speed | Unchanged at click | **Recalc** → reorder risk |
| Overlay-only scoring | Risky but structurally used today | **Systematically wrong** without projection |

**P0 design inputs (not implementation detail here):** target-form derivation; non-mutating projection
into planning path; ability/weather activation timing; optional ranking pass only after correct projection.

---

## Opponent Mega — I7b gate

Post-hoc `|-mega|` log parse **does not** fix turn-T counterfactuals: opponent response branches score
against defender state at **`evaluate_line` time**. Foe Mega + attack requires mega defender **before**
foe move resolution. **Strength eval NO-GO** until I7b unless explicitly scoped out.

---

## HP suffix evidence (consistent)

| Suffix | Status |
|--------|--------|
| **`y`** | **Live** — `suffix-evidence.json` (damage lines) |
| **`g`** | **Live** — one heal line `|-heal|p2b: Milotic|50/100g` in same artifact |
| **`r`** | **Grammar probe only** — not observed in live evidence |

Our parser and `@pkmn/protocol` `parseHealth` both strip suffix digits correctly on all three (grammar).

---

## Differential matrix (abbreviated)

| Case | Our stack | `@pkmn/protocol` | Showdown GT | Class |
|------|-----------|------------------|-------------|-------|
| Full move slot | OK | OK | OK | identisch |
| Solar `target` omitted fixture | OK | OK | omission valid | identisch (grammar); **phase not proven** for fixture |
| Solar release-shaped fixture | OK | OK | OK | identisch |
| HP `y` / live `g` | OK | OK | live | identisch |
| HP `r` | OK (grammar) | OK | not live | grammar probe |
| `canMegaEvo` | **Gap** | typed `boolean` | `true` | echter Gap |
| `mega` token | **Gap** | no encoder | `move … mega` | echter Gap |
| One mega / side | **Gap** | — | enforced | echter Gap |
| Both slots offered | **Gap** | — | both `true` | echter Gap |
| `-mega` 3-arg line | **Gap** | **3 args parsed** | see probe table | Gap (us) / protocol OK |
| Pre-turn mechanics | **Gap** | N/A | form before move | echter Gap |
| Foe mega in response tree | **Gap** | N/A | before foe move | I7b Gap |
| Trace | Tera v2 only | N/A | N/A | trace-v3 Gap |

---

## Confirmed Mega semantics (belastbar)

1. Request: `canMegaEvo: true` (boolean) per eligible slot.
2. Choice: `move <idx> [<target>] mega`.
3. One Mega per side per battle; both slots may offer simultaneously.
4. Protocol: `|detailschange|…Mega-Y…` then `|-mega|ident|Charizard|Charizardite Y`.
5. Post-mega: Mega-Y, Drought, Fire/Flying, speed recalc; side-wide `canMegaEvo` false after spend.

---

## Trace (design input — spec must define)

Rev. 2 conclusion stands: **`decision-trace-v3`**, candidate-key payload **v2**, **`chosen_mega_slot`**,
new validators, loaders for **v1 / v2 / v3**. Do not extend trace-v2 or key version 1 silently.

**Open for I7 design spec (not decided in this audit):**

- Exact v3 row fields and backward-compat loader behaviour
- When v3 is emitted (Champions-only vs format-gated)
- Interaction with `chosen_tera_slot` on Reg-I (orthogonal; Champions tera off)
- Normalization rules for `/choose` parse of `mega` token in `decision_capture`

---

## Open interfaces for I7 design spec

The following **must be specified** before an implementation plan. This audit records **need only**.

| Interface / decision | Question for spec |
|---------------------|-------------------|
| `mega_form_for(species, item)` | Single resolver: stone → forme id; fallback when request omits internal string; Champions dex vs generic |
| **Isolated state projection** | Copy/`clone_state` + apply mega fields **without** mutating live `BattleState` used across candidates |
| **Ability / weather activation** | Which abilities fire on mega turn (Drought, etc.); field update order vs speed calc |
| **Speed path** | Hook point **before** `_plan_my_actions`; relation to `SpeedOracle.our_speed` inputs |
| **Damage / calc** | How projected forme reaches gen-0 calc profile (I6 path) |
| **Foe mega candidates** | Source: enumerated foe joint actions? request-invisible — belief / likely_sets? protocol-predicted? |
| **Foe mega timing** | Where in `evaluate_line` / response builder mega applies relative to move resolution |
| **Trace v3 write/load** | Schema version string, required fields, validation, gzip sidecar contract |

---

## Local files read

`models/request.py`, `models/actions.py`, `battle/actions.py`, `battle/legal_actions.py`,
`protocol/encoder.py`, `engine/log_parser.py`, `engine/state.py`, `battle/resolve.py`,
`battle/decision.py` (`_plan_my_actions`, `_maybe_tera`), `battle/candidate_identity.py`,
`eval/decision_capture.py`, `engine/format_config.py`, fixtures under `tests/fixtures/`,
`suffix-evidence.json`, `gen9championsvgc2026regma.yaml`.

---

## Probe artifacts (not committed)

| Path | Notes |
|------|-------|
| `tools/_pkmn_differential_audit/` | Our-stack probes |
| `%USERPROFILE%\.cache\showdownbot\pkmn-audit-0.7.3\` | pkmn + sim probes; **`pkmn_probes.json` corrected rev. 3** |

---

## Sign-off

| Check | Status |
|-------|--------|
| Four rev. 2 concept fixes | Yes |
| pkmn probe **corrected** (3-arg) | Yes |
| `_plan_my_actions` speed timing | Yes |
| Design-input-ready (not impl-plan) | Yes |
| Open interfaces listed | Yes |
| HP y+g live, r grammar — consistent | Yes |
| Trailing whitespace cleaned | Yes |
| Commit: report only | This commit |

**Next step:** commit this audit → author **separate `I7` design spec** → then implementation plan.
