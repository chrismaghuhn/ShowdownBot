# 2b-3.5 T0 — Determinism-/Seed-Feasibility-Probe Report (2026-07-01)

Measure-and-prove probe for the eval-harness blocker. **No harness code built** — a throwaway gauntlet
run (T0a) + a Showdown-source feasibility investigation (T0b) + this verdict (T0c). Branch:
`feat/slice-2b35-t0-determinism`. Local server: `~/.cache/showdownbot/pokemon-showdown` @ f8ac140.

## T0a — Baseline determinism WITHOUT a seed

**Method:** 6 identical-config battles in one gauntlet session — same agents (hero `heuristic` vs
villain `max_damage`), same team (mirror `fixed_team`), same format (`gen9vgc2025regi`), same local
server, no seed knob (none exists today). Persistent calc backend.

**Result:**
```
game winners: HeuristicBot, HeuristicBot, BaselineBot, HeuristicBot, BaselineBot, BaselineBot
→ 3/6 hero wins   (split, not 6-0)
safety: invalid_choices=0 · crashes=0 · latency_p95=270 ms
```
**Finding:** the winner **varies across identical-config battles** → the current state is **not
reproducible**. The bot itself is deterministic (heuristic `pick_best` has no RNG); the variation comes
from the **server sim PRNG**, which is unseeded per battle (each battle rolls a fresh random seed).
Bit-level `room_raw` comparison across a *fixed* seed is **not testable today** — there is no seed to
fix (that is exactly what T0b resolves). Safety floor held throughout.

## T0b — Seed-injection feasibility (PROVEN via source, not assumed)

The Showdown sim already supports a per-battle PRNG seed **end-to-end**; the only missing link is that
the challenge path doesn't set it. Evidence (paths in `~/.cache/showdownbot/pokemon-showdown`):

| Layer | Evidence | Meaning |
|---|---|---|
| **sim** | `sim/battle.ts:67,224` `seed?: PRNGSeed` → `this.prng = options.prng \|\| new PRNG(options.seed)`; every roll uses `this.prng` (`random`/`randomChance`/`sample`/`shuffle`, :347–456) | one seed governs **all** battle randomness |
| **sim replay** | `sim/battle.ts:279–291` `>start {…, seed: this.prngSeed}` in the `inputLog` | seed + inputLog **is** Showdown's deterministic-replay mechanism |
| **server room** | `server/room-battle.ts:490` `RoomBattleOptions.seed?: PRNGSeed` → written to the sim stream (`:575` `seed: options.seed`) | the room layer forwards a seed to the sim |
| **server create** | `server/rooms.ts:2189` `createBattle(options: RoomBattleOptions…)` accepts it | the battle-creation API accepts a seed |
| **caller** | `server/ladders.ts:473` `Rooms.createBattle({…})` — the challenge/ladder path — does **NOT** set `seed`; the sim then generates one (`sim/battle.ts:3191` `if (!options.seed) options.seed = PRNG.generateSeed()`) | the ONLY gap: the challenge caller omits the seed |

**Conclusion:** a per-battle seed is injectable via a **minimal, well-localized ~1-line change** at the
challenge→`createBattle` call (`server/ladders.ts:473`) — threading a seed (from env / schedule) into
the options that already flow to the sim. No new mechanism; the seed path exists. (No standard
`/challenge`-protocol seed parameter and no seed custom-rule were found, so the localized server patch
is the path — the "minimal server patch" the plan allowed for, and it is genuinely minimal.)

## T0c — VERDICT: **PASS_STRONG (feasibility proven; empirical bit-stability demo = first T1 step)**

- **Not FAIL:** start conditions (and, via the sim PRNG, the whole battle) **are** controllable — the
  seed path is proven end-to-end.
- **Not PASS_WEAK:** the seed governs **every** roll (not merely start conditions); Showdown's
  seed+inputLog is bit-deterministic by design, and the bot is deterministic → a fixed seed + fixed
  inputs ⇒ a bit-identical battle. So full reproducibility is the expected, designed behavior.
- **Honesty caveat:** T0 did **not** implement the injection (per scope: "prove feasibility, don't
  build"), so bit-stability was **not empirically demonstrated** here. The verdict is PASS_STRONG on
  **proven feasibility + Showdown's replay guarantee**, with the confirming run (seed a battle, run it
  twice, diff `room_raw` → identical) as the **first T1 step**.

## Consequence for the roadmap
- **T1 is unblocked** (verdict ∈ {PASS_STRONG, PASS_WEAK}). T1's opening sub-step = the ~1-line
  `ladders.ts` seed patch on the local server clone + the seeded-twice bit-stability confirmation
  (which upgrades this verdict from "feasibility-proven" to "demonstrated PASS_STRONG"). Then T1 proper
  (non-mirror scheduling threading the schedule's per-battle seed).
- **Determinism status for later reports:** expected **bit-reproducible** once T1 lands the seed
  (PASS_STRONG); until the seeded-twice demo is run, treat as "PASS_STRONG-feasible".

**STOP** — per the T0 scope, no follow-up tasks started; awaiting review.
