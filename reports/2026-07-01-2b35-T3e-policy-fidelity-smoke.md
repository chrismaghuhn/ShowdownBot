# 2b-3.5 T3e P2 / P2a — Policy-Fidelity Activation Smoke (runs 2026-07-02)

Final T3e piece: prove the improved eval policies (type-aware `simple_heuristic`, HP-gated
`greedy_protect`) **actually activate** in live eval execution — `0 invalid / 0 crash` alone
is not enough. Branch: `feat/slice-2b35-t3e-policy-fidelity`.

> **Reading order:** the **P2** sections below record the *initial* smoke, which found
> `simple_heuristic` structurally dormant live (0 activations). **P2a** (bottom) is the fix +
> re-run that makes it activate live (34 activations). The P2 discovery is kept visible on
> purpose — it is why P2a exists.

## What P2 added
- **Env-gated activation telemetry** (`eval/opponents/policies.py`): when
  `SHOWDOWN_EVAL_POLICY_TELEMETRY=<path>` is set, each policy appends a JSONL event when its
  improved branch **fires**. Unset → no-op, no behavior change, `/choose` output unchanged,
  deterministic. Best-effort file append; never raises into the decision path. Eval-only module
  (lazily imported by the gauntlet), so no live-path import pollution.
  - `simple_heuristic` → `{"policy":"simple_heuristic","event":"type_effectiveness_fired"}` when a
    scored move used **known target types** and `effectiveness != 1.0`.
  - `greedy_protect` → `{"policy":"greedy_protect","event":"hp_gated_protect_fired"}` when the
    chosen pair Protects on a slot with `hp_fraction < LOW_HP (0.4)`.

## Smoke — tiny dev schedule (exactly 6 battles, no subset)
Generated `generate_dev_schedule(panel_v001, policies=["simple_heuristic","greedy_protect"])`
over **all 3 dev teams** (trickroom / sun / rain) → **2 policies × 3 teams = 6 battles**.
`schedule_hash=db4d0a7a31070a62`, `panel_hash=760c1e5935fe0474` (the T3e-P1 corrected hash).

```bash
cd showdown_bot
# generate the 6-battle schedule (hero = teams/fixed_team.txt)
python -c "from pathlib import Path; from showdown_bot.eval.panel import load_panel; \
from showdown_bot.eval.panel_schedule import generate_dev_schedule, write_schedule_yaml; \
sb=Path.cwd(); p=load_panel(str(sb.parent/'config/eval/panels/panel_v001.yaml'), teams_root=str(sb)); \
write_schedule_yaml(generate_dev_schedule(p, policies=['simple_heuristic','greedy_protect'], teams_root=str(sb)), '/tmp/dev6.yaml')"
# fresh seeded server (Channel A, counter from 0), server env carries the seed base + log:
#   SHOWDOWN_BATTLE_SEED_BASE=t3e2026 SHOWDOWN_EVAL_SEED_LOG=/tmp/seeds.jsonl node pokemon-showdown start 8000 --no-security
PYTHONHASHSEED=0 SHOWDOWN_CALC_BACKEND=persistent SHOWDOWN_BATTLE_SEED_BASE=t3e2026 \
  SHOWDOWN_EVAL_SEED_LOG=/tmp/seeds.jsonl SHOWDOWN_EVAL_POLICY_TELEMETRY=/tmp/telem.jsonl \
  python -m showdown_bot.cli gauntlet --schedule /tmp/dev6.yaml --result-out /tmp/results.jsonl
```

| Gate | Result |
|---|---|
| Result rows | **6** (one per schedule row), **all re-validate** |
| Safety | **0 invalid · 0 crashes** (per row and in totals) |
| Winners | hero 4 · villain 2 · ties 0 |
| `panel_hash` in rows | **all == `760c1e5935fe0474`** ✅ (T3e-P1 corrected hash) |
| `dirty` present | ✅ (all rows; observed `True` — run was against the uncommitted P2 working tree) |
| `hero_team_hash` present | ✅ all `5aef213f351a6627` (content hash of `fixed_team`) |
| `opp_team_hash` present | ✅ trickroom `e622869d6c68307e` · sun `b0048ae65f0e9ee5` · rain `69f471c2740f1927` |
| Seed-log alignment | **OK** — 6 battles, `seed_i == derive_battle_seed(t3e2026, seed_index)` |
| Per-battle counters | per-battle, NOT cumulative — `decision_latency_p95_ms` = 214/217/191/206/189/192 (non-monotone); every row `invalid=0 crashes=0` |

## Activation evidence
| Policy | Live activations (6-battle smoke) | Fixture evidence |
|---|---|---|
| `greedy_protect` (`hp_gated_protect_fired`) | **25** ✅ | (not needed — fired live) |
| `simple_heuristic` (`type_effectiveness_fired`) | **0** | **1** (deterministic fixture) ✅ |

**`greedy_protect` activates naturally live** (25 HP-gated Protects across the 3 greedy battles):
mons drop below 40% HP and Protect fires, exactly as designed.

**`simple_heuristic` does NOT activate live — an honest finding the telemetry was built to catch.**
The type-aware path requires the **opponent active-mon types** to be present in the villain's
`BattleState`. In the live harness they are not: `state` populates `types` only from the request's
own `base_types`; the opponent's typing is derived on-demand from the dex inside the heuristic's
`DamageModel`, and is **not** stored in the base state that the eval policy reads. So
`target_types_for_action` sees empty types → neutral (1.0) → the type-effectiveness branch never
fires, and `simple_heuristic` runs live in its (legal, deterministic) **base-power fallback** mode.
Verified directly: a state built from a live `|switch|` log has `p1a.species='Incineroar'` but
`types=[]`.

Per the plan's fixture-evidence allowance, **deterministic fixture activation evidence** proves the
improved logic fires when types ARE known (unit test
`test_simple_heuristic_telemetry_fires_on_type_effectiveness`, plus a one-shot fixture):
opponent `a = Fire/Flying` → `simple_heuristic` picks **Rock Tomb (move 2)** over the higher-BP
resisted Flare Blitz and emits `{"event":"type_effectiveness_fired","policy":"simple_heuristic"}`.

## P2 VERDICT (initial): telemetry works; simple_heuristic dormant live
Telemetry seam is env-gated, deterministic, `/choose`-neutral, and eval-only. The initial 6-battle
smoke was clean (0 invalid / 0 crash), fully provenanced, seed-aligned. `greedy_protect`'s HP-gate
fired live; **`simple_heuristic`'s type-aware path was dormant live (0 activations)** because the
eval `BattleState` carries opponent *species* but empty opponent *types*. Plan-Claude ruled this a
**T3e blocker** (fixture-only evidence not acceptable for a structurally-dormant path) → **P2a**.

---

## T3e P2a — resolution: eval-only species→types resolver (live activation)
**Fix (review Option B):** an **eval-only** species→types resolver lets `simple_heuristic` recover
opponent typing from the known species when the live state has empty `types`.
- `eval/opponents/policies.py`: `target_types_for_action(..., resolver=None)` + `_resolved_types`
  — when a target mon has empty `types` but a known `species`, resolve via `resolver.types(species)`.
  **Read-only: the shared `BattleState` is never mutated.** Any failure (no resolver / no species /
  backend down / unknown species) → `[]` → neutral (1.0) → original base-power behavior. Deterministic.
- `client/gauntlet.py`: `_Client._species_type_resolver()` lazily builds `SpeciesDex(make_calc_backend())`
  **only for the `simple_heuristic` agent**, cached; threaded through `agent_choose(..., species_resolver=)`
  into `simple_heuristic_choice(resolver=)`. `battle/` and the live decision path are untouched; the
  live-path guard (`eval/opponents` never imported by `battle/`/runner) stays green.

### P2a re-run — exact same 6-battle smoke (fresh seeded server, same env/schedule)
| Gate | Result |
|---|---|
| Result rows | **6**, all re-validate |
| Safety | **0 invalid · 0 crashes** |
| `panel_hash` | all **`760c1e5935fe0474`** ✅ |
| `dirty` / `hero_team_hash` / `opp_team_hash` | all present ✅ |
| Seed-log alignment | **OK** (`t3e2026`, `schedule_hash=db4d0a7a31070a62`) |
| `greedy_protect` `hp_gated_protect_fired` (live) | **25** ✅ |
| `simple_heuristic` `type_effectiveness_fired` (live) | **34** ✅ (was **0** in P2) |
| Behavioral effect | winrate shifted hero 4→2 / villain 2→4 — the now-type-aware opponent is genuinely stronger |

## VERDICT: **T3e P2a PASS — simple_heuristic type-awareness activates live**
Both improved policies are now proven to fire in live eval: `greedy_protect` HP-gate 25×,
`simple_heuristic` type-effectiveness **34×** (no longer fixture-only). The resolver is eval-only,
non-mutating, graceful, deterministic, and leaves the live decision path unchanged.

**STOP** — T3e P2/P2a done (telemetry + eval-only resolver + activation smoke). Awaiting review;
not merged. No T3f/T4/T5/T6/override.
