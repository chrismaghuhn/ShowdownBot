# Champions FormatConfig v0 — Multi-Format Adapter Design

**Status:** PROPOSED — pending review (spec/docs only; **no implementation** in this slice)

**Date:** 2026-07-14

**Builds on:** [`2026-07-14-champions-panel-v0-design.md`](2026-07-14-champions-panel-v0-design.md) §8.2 · P0–P4 + rain held-out reports under `reports/champions-panel-v0-*.md`
**Precedes:** Champions strength / decision-quality eval on `panel_champions_v0`

## 0. Guiding principle — adapter, not fork

Champions FormatConfig v0 is the **first second format** wired through the existing
`FormatConfig` system. It must **not** introduce `if format_id == "gen9champions…"` (or
equivalent) branches in the decision core.

| Belongs in FormatConfig / format-scoped meta | Does **not** belong in decision core |
|----------------------------------------------|--------------------------------------|
| `tera`, `mega`, stat-investment rules, restricted policy | Champions-specific species lists hardcoded in Python |
| Per-format yaml + meta paths (`default_spreads`, priors, …) | Reg-I yaml paths reused for Champions |
| Generic helpers keyed off `FormatConfig` (e.g. tera overlay gate, speed-range max investment) | One-off Champions damage hacks |

**Rule:** if the decision core needs to behave differently across formats, add or read a
**generic** field on `FormatConfig` (or a small helper that takes `FormatConfig`) and set it
in yaml. Champions is just the first consumer.

## 1. Problem statement

Champions panel work is **PIPELINE-READY** (P4) and rain held-out is **parser/harness PASS**,
but any schedule with `format_id: gen9championsvgc2026regma` still hits:

```python
# gauntlet._load_belief_deps — FileNotFoundError swallowed
book = None
priors = None
```

Downstream:

```python
# gauntlet.agent_choose
if agent == "random" or state is None or book is None:
    return choose_for_request(req)  # random legal choice
```

So P4 rows labeled `heuristic` / `max_damage` were **random-legal**, not heuristic. That was
acceptable for harness smoke (spec §8.2) but is a **hard blocker** for strength or
decision-quality runs unless explicitly declared as a degraded baseline.

**Goal of v0:** define the smallest **honest** FormatConfig + meta bundle so `book != None`,
beliefs load, and policies are the policies they claim — without pretending Reg-I meta or
252-scale spreads are valid for Champions.

## 2. Current FormatConfig audit (Reg-I only)

### 2.1 Loader & dataclass

File: `showdown_bot/src/showdown_bot/engine/format_config.py`

| Field | Reg-I usage | Notes |
|-------|-------------|-------|
| `format_id` | yaml key | Selects `showdown_bot/config/formats/{id}.yaml` |
| `level` | `50` | VGC |
| `game_type` | `doubles` | |
| `restricted_limit` | `2` (Reg-I) | Loaded but **not referenced** elsewhere in `src/` today |
| `tera` | `true` (Reg-I) | Loaded but **not referenced** in decision path today |
| `meta_paths` | 4 yaml files under `meta/` | Resolved relative to format yaml directory |

Tests: `showdown_bot/tests/test_format_config.py` (Reg-I load + path existence only).

### 2.2 Existing format yamls

| File | Shared meta |
|------|-------------|
| `showdown_bot/config/formats/gen9vgc2025regi.yaml` | `meta/default_spreads.yaml`, `protect_priors.yaml`, `likely_sets.yaml`, `move_priors.yaml` |
| `showdown_bot/config/formats/gen9vgc2024regg.yaml` | same shared `meta/` tree |

**No** `gen9championsvgc2026regma.yaml`.

### 2.3 Meta schema (format-agnostic today, Reg-I-valued)

| File | Role | Empty/missing behaviour |
|------|------|-------------------------|
| `default_spreads.yaml` | Worst-case offense/defense presets per species | **Required** for non-random heuristic — load raises if malformed |
| `protect_priors.yaml` | Opponent Protect rate prior | File required when path set; species map may be `{}` |
| `likely_sets.yaml` | Curated probable opponent spread | Missing/invalid → `{}` (worst-case fallback) |
| `move_priors.yaml` | Curated move priors | Missing → `{}` |

Spread yaml uses key **`evs`** regardless of investment semantics (`SpreadPreset.evs` →
`CalcMon.evs`). Reg-I files use 252-scale values and include species **illegal in Champions**
(e.g. Flutter Mane, Booster Energy items).

### 2.4 Load sites

| Consumer | Uses |
|----------|------|
| `gauntlet._load_belief_deps` | book + priors (+ opp_sets side channel) |
| `runner._get_book` / `_get_priors` | live ladder |
| `load_opp_sets_for_format` / `load_move_priors_for_format` | opp belief |
| `cli._config_hash_for` | hashes spreads + priors paths for provenance |
| `validate_log` | spread book for damage union |

**Decision core (`battle/decision.py`) does not receive `FormatConfig` today.** Tera overlay
(`_maybe_tera`) gates only on `req.active[i].can_terastallize` (server truth). That happens to
disable Tera on Champions, but Reg-I yaml `tera: false` is not consulted — a generic gap for
multi-format.

### 2.5 Hardcoded Reg-I assumptions outside yaml (adapter debt)

These are **not** Champions bugs; they are missing generic hooks:

| Location | Assumption | Generic fix (implementation slice) |
|----------|------------|-------------------------------------|
| `engine/speed.py` `opponent_range` | max speed uses `evs={"spe": 252}` | use `format_config.stat_investment.max_per_stat` |
| `default_spreads.yaml` default preset | `{atk:252, spa:252, spe:252}` offense | scale default worst-case to format investment caps |
| `@smogon/calc` via `CalcMon.evs` | standard Gen 9 EV stat formula | document v0 gap; future calc adapter keyed on `stat_investment.kind` |
| (none) | Mega Evolution | no bot code yet; `FormatConfig.mega` flags capability for future overlay |

## 3. Champions requirements (from completed gates)

| Requirement | Value | Source |
|-------------|-------|--------|
| Primary format ID | `gen9championsvgc2026regma` | P0 format discovery |
| Mega Evolution | **on** | P1 mechanics audit |
| Terastallize | **off** | P1; server sets `canTerastallize: null` |
| Stat investment | **66 total / 32 max per stat** (paste still labeled `EVs:`) | P1 validator + Showdown mod |
| Restricted | Flat Rules **ban** all restricted/mythical (no slot) | P1 |
| Legal pool | Curated Champions dex (items/moves differ from Reg-I) | P1 probes |
| Panel | `panel_hash = aac1ea30446fde88`, `config/eval/panels/panel_champions_v0.yaml` | P3 |
| Hero team | `showdown_bot/teams/fixed_champions_v0.txt` | P3 provenance |
| Opponent teams | `showdown_bot/teams/panel_champions_v0/*.txt` (5 archetypes) | P3 |

Panel species union: **25 unique species** across committed hero +
`showdown_bot/teams/panel_champions_v0/*.txt` paste files (6 teams × 6 slots, with overlap).
Used as the **v0 meta coverage target** — not the full Champions dex.

## 4. Proposed generic FormatConfig schema (v0)

Extend `FormatConfig` + yaml schema for **all** formats. Reg-I yamls gain explicit
`stat_investment` for documentation/backfill; Champions is the first yaml that **requires**
non-default values.

### 4.1 New / clarified yaml fields

```yaml
# showdown_bot/config/formats/gen9championsvgc2026regma.yaml (proposed)
format_id: gen9championsvgc2026regma
level: 50
game_type: doubles

# Restricted: server enforces Flat Rules ban; field documents intent for humans/tools.
restricted_limit: 0

tera: false
mega: true

stat_investment:
  kind: stat_points   # ev | stat_points
  total: 66
  max_per_stat: 32
  iv_policy: all_31    # documented; validator-enforced on Showdown side

meta_paths:
  default_spreads: meta/champions/default_spreads.yaml
  protect_priors: meta/champions/protect_priors.yaml
  likely_sets: meta/champions/likely_sets.yaml
  move_priors: meta/champions/move_priors.yaml
```

Reg-I backfill (same schema, no behaviour change until callers read it):

```yaml
stat_investment:
  kind: ev
  total: 510          # legal Showdown budget (508 = effective usable after 4-EV nature tie; not the rule cap)
  max_per_stat: 252
  iv_policy: flexible
tera: true
mega: false
```

**Dataclass additions:** `mega: bool`, `stat_investment: StatInvestment` (frozen dataclass
with `kind`, `total`, `max_per_stat`, optional `iv_policy`). Defaults preserve today’s Reg-I
semantics when yaml omits the block (loader migration in implementation slice).

### 4.2 Meta directory layout

```
showdown_bot/config/formats/
  gen9championsvgc2026regma.yaml          # NEW
  gen9vgc2025regi.yaml                    # + stat_investment backfill
  meta/
    default_spreads.yaml                  # Reg-I (unchanged path for Reg-I yamls)
    …
    champions/                            # NEW — Champions-only meta, never shared
      default_spreads.yaml
      protect_priors.yaml
      likely_sets.yaml
      move_priors.yaml
```

**Forbidden:** pointing Champions `meta_paths` at Reg-I `meta/default_spreads.yaml` or
`likely_sets.yaml`.

## 5. Champions meta v0 — file-by-file scope

### 5.1 `default_spreads.yaml` — **REQUIRED, must not be Reg-I stub**

Purpose: load `SpreadBook` so `book != None` and worst-case hypotheses use **legal-scale**
investments.

| Section | v0 content |
|---------|------------|
| `default.offense` | Timid/Hasty-style: `{spa or atk: 32, spe: 32, hp: 2}` (not 252 triple) |
| `default.defense` | Bold/Calm-style: `{hp: 32, def or spd: 32, spare: 2}` |
| `species.*` | **Panel union species only** (25 entries), offense/defense presets capped at 32/stat |

Derivation source (implementation): parse spreads from committed hero + panel team pastes;
offense/defense presets can initially mirror the **single known team spread** per species
(honest v0 — not fabricated 252 spreads).

**Dangerous stub:** Reg-I file or default preset still at 252 → heuristic runs but damage/speed
beliefs are **wrong direction** (misleading strength numbers).

### 5.2 `protect_priors.yaml` — **REQUIRED file, minimal content OK**

Purpose: load `ProtectPriors` so `priors != None`.

| Content | v0 |
|---------|-----|
| `default`, `threatened_bump`, `consecutive_penalty` | Copy Reg-I **schema defaults** (0.18 / 0.45 / 0.4) — mechanic-agnostic |
| `species` | Panel union only; rates may copy Reg-I where species overlap, else `default` |

**Safe stub:** global defaults + empty `species: {}` (all species use `default`).

**Risky stub:** Reg-I species entries for illegal mons (harmless at runtime if never seen;
pollutes provenance / future validation).

### 5.3 `likely_sets.yaml` — loader/smoke vs strength

Purpose: realistic opponent spread in damage model (see
[`2026-06-29-opponent-likely-sets-design.md`](../../core-bot/specs/2026-06-29-opponent-likely-sets-design.md)).

Missing file → `{}` already; no crash. Empty `likely_sets` does **not** cause random play
(`book=None` does — see §1); it only weakens opponent spread realism (worst-case book fallback).

| v0 option | When to use |
|-----------|-------------|
| **B:** `species: {}` (empty) | **Loader / I5 smoke only** — proves yaml paths load; not for strength claims |
| **A (required for first honest strength run):** panel-derived point spreads from committed hero + panel pastes | First strength run on `panel_champions_v0` |
| **C:** Reg-I file | **Forbidden** — illegal species + 252 spreads |

**Labeling (Option A):** file header / provenance must state **panel-derived v0 prior** — scoped
to the 25 species in committed panel teams, **not** general Champions-format meta. Do not copy
Reg-I `likely_sets.yaml`.

### 5.4 `move_priors.yaml` — **optional**

Omit or empty `{}`. Loader already degrades to no move prior.

## 6. Review questions (explicit answers)

### 6.1 Stub FormatConfig vs none?

| Mode | Heuristic behaviour | Verdict |
|------|---------------------|---------|
| **None** (today) | `book=None` → **random legal** | Mislabeled; worst for interpretability |
| **Yaml only, broken meta paths** | same as none | Useless |
| **Yaml + Reg-I meta stub** | heuristic runs, **wrong calcs** | **More dangerous than none** — looks legitimate in reports |
| **Yaml + Champions meta v0 (§5)** | heuristic runs, panel-scoped investments | **Smallest honest v0** |

**Conclusion:** ship yaml + Champions-scoped meta; never Reg-I alias. If meta cannot be curated
in time, run with explicit env/policy label `random` or document `book=None` degraded baseline
— do **not** silently alias Reg-I.

### 6.2 Reuse Reg-I `default_spreads` / `protect_priors`?

**No** for Champions strength/decision-quality.

| Reason | Detail |
|--------|--------|
| Investment scale | 252 EV presets ≠ 66/32 Stat Points — breaks damage + speed oracle max |
| Legal pool | Reg-I species/items (Flutter Mane, Booster Energy, Covert Cloak, …) invalid |
| Tera items | Booster Energy priors irrelevant (`tera: false`) |

Partial reuse of **protect rate numbers** for overlapping species is fine if keys are
Champions-legal only.

### 6.3 Smallest honest v0 that allows Strength runs?

**Minimum bar (pipeline + non-random heuristic):**

1. `showdown_bot/config/formats/gen9championsvgc2026regma.yaml` with correct flags + **Champions** meta paths
2. `showdown_bot/config/formats/meta/champions/default_spreads.yaml` — 25 panel species, 32-cap investments
3. `showdown_bot/config/formats/meta/champions/protect_priors.yaml` — schema defaults (species map optional)

**Required before first honest strength run (not just loader/smoke):**

4. `showdown_bot/config/formats/meta/champions/likely_sets.yaml` — **panel-derived v0 prior** (Option A, §5.3); empty `{}` acceptable for I5 smoke only
5. Implementation slice threads `FormatConfig` into decision (§7) — at minimum `cfg.tera` gate
6. Document known gaps: calc stat formula, speed max investment, no Mega overlay (§8)

**Not required for v0 yaml slice:** Mega decision logic, full dex-wide meta, VGC-Bench-derived
priors.

## 7. Decision-core integration (implementation slice — no code here)

All changes are **format-generic**; Champions yaml supplies values.

| Step | Change |
|------|--------|
| 1 | `gauntlet._Client` loads `FormatConfig` once per `format_id`; pass to `agent_choose` / `choose_with_fallback` |
| 2 | `_maybe_tera`: skip overlay when `not format_config.tera` (keep server `can_terastallize` check) |
| 3 | `SpeedOracle.opponent_range`: max investment from `format_config.stat_investment.max_per_stat`, not literal `252` |
| 4 | Optional: validate spread book entries against `max_per_stat` / `total` at load time (fail loud in tests) |
| 5 | `config_hash` / CLI provenance: include format yaml hash or `stat_investment` + `mega`/`tera` fields |

**Explicit non-goal for v0:** Mega Evolution overlay in decision (no `canMegaEvo` handling yet).
`mega: true` in yaml is **declarative** for provenance and future work; absence must not imply
Mega is off in battles (Showdown still megas via team items).

## 8. Known quality gaps (honest limits)

Even with correct yaml/meta, v0 strength runs should be interpreted with these open gaps:

| Gap | Impact | v0 mitigation |
|-----|--------|---------------|
| `@smogon/calc` EV formula vs Stat Points | Hidden-mon damage may be approximate | Panel spreads use 32-scale values; our mons use request stats for speed |
| Speed oracle max tier | Was hardcoded 252 Spe | Generic max_per_stat (§7.3) |
| No Mega modelling | Undervalues/overvalues mega lines | Document; server still megas; future overlay uses `format_config.mega` |
| Narrow meta (panel-only species) | Unknown species fall back to `default` preset | Accept for panel-scoped eval |
| `restricted_limit` unused in bot | No effect today | Document Flat Rules; no bot teambuilder in scope |

## 9. Implementation plan (review-gated, ordered)

| Phase | Deliverable | Tests |
|-------|-------------|-------|
| **I1 — schema** | Extend `FormatConfig` + loader; backfill Reg-I yaml `stat_investment`; add Champions yaml skeleton | extend `test_format_config.py` |
| **I2 — meta** | Generate `meta/champions/*.yaml` from panel/hero pastes (script or manual) | loader tests + species key validation vs calc |
| **I3 — thread config** | Pass `FormatConfig` through gauntlet → decision; `cfg.tera` gate | focused gauntlet/decision replay tests |
| **I4 — speed cap** | `SpeedOracle` reads `max_per_stat` | `test_speed.py` with stat_points fixture |
| **I5 — smoke** | Re-run champions smoke; confirm `book`/`priors` hashes in manifest; heuristic ≠ random spot-check | existing smoke schedule |

**Stop line:** no strength / McNemar run until I1+I2+I3 complete and smoke shows non-random
heuristic path (single decision replay fixture suffices).

## 10. Verification (this spec slice)

| Check | Expectation |
|-------|-------------|
| `git diff --check` | clean (docs only) |
| Test suite | not required for docs-only |
| Review | Codex before push / implementation |

## 11. Acceptance checklist (implementation slice)

- [ ] `load_format_config("gen9championsvgc2026regma")` succeeds; meta paths exist and are **not** Reg-I aliases
- [ ] `_load_belief_deps("gen9championsvgc2026regma")` returns non-`None` book and priors
- [ ] No `gen9champions…` string literals added to `battle/decision.py`
- [ ] Reg-I tests unchanged behaviour (stat_investment defaults)
- [ ] Champions smoke or replay proves heuristic path uses spread book (not random-only)
- [ ] `docs/ROADMAP.md` updated when implementation lands (out of scope for this doc-only slice)

## 12. Open risks

1. **False confidence:** Reg-I meta alias would produce plausible-looking winrates — highest risk; mitigated by separate `meta/champions/` tree.
2. **Calc fidelity:** Stat Points may not match calc until adapter work; strength trends may shift after fix — record `config_hash` at each run.
3. **Panel-only meta:** Strength vs unseen species relies on generic default preset — acceptable for v0 panel eval, not for ladder claims.
4. **Mega blind spot:** Aerodactylite / Scovillainite lines not optimised in decision — format flag documents gap; not a yaml blocker.
## 13. Related artefacts

| Doc | Role |
|-----|------|
| `reports/champions-panel-v0-format-discovery.md` | format ID |
| `reports/champions-panel-v0-mechanics-audit.md` | 66/32, mega/tera, dex |
| `reports/champions-panel-v0-pilot-smoke.md` | P4 random-heuristic classification |
| `reports/champions-rain-heldout-parser-validation.md` | held-out harness PASS |
| `docs/ROADMAP.md` | next gate: FormatConfig before strength |

---

**Review ask:** approve generic schema (§4), Champions meta layout (§4.2–5), and implementation
phases (§9) before I1 coding. **likely_sets:** empty `{}` for loader/smoke (§5.3 option B);
panel-derived v0 prior (§5.3 option A) for first honest strength run.
