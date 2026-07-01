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

## T0c — VERDICT: **SEED_FEASIBILITY_PROVEN — T1_ALLOWED**  (empirical PASS_STRONG pending T1's seeded-replay confirmation)

Plain-language summary: **T0a** — the current unseeded gauntlet is not deterministic. **T0b** — a
per-battle seed path exists in Showdown source; a minimal local server patch is feasible. **T0c** —
PASS_STRONG is *expected* but **not yet empirically demonstrated**, because seed injection is not
implemented in T0.

Why the three rubric verdicts don't fit T0 as-run, and why the intermediate status is correct:
- **Not FAIL:** the seed **is** controllable — the path is proven end-to-end (T0b). Start conditions
  (and, via the sim PRNG, the whole battle) can be governed by a seed.
- **Not (yet) PASS_STRONG:** our rubric defines `PASS_STRONG` = *"room_raw + result bit-stable at a
  fixed seed"* — an **empirical** claim. T0's scope was "prove feasibility, don't build" (T0b:
  seed injection **not** implemented), so the seeded run was never executed. Under its own scope T0
  therefore **cannot** return a legitimate PASS_STRONG — that verdict requires the very seeded battle
  T0 was told not to build. Asserting it now would put "seeded bit-stability was proven in T0" into the
  roadmap, when what was actually proven is "seeded bit-stability is architecturally feasible."
- **Not PASS_WEAK either:** `PASS_WEAK` is the specific empirical finding *"start conditions stable,
  battle log/result NOT bit-stable"* — that would falsely claim we ran a seeded battle and observed
  non-bit-stable logs. We ran no seeded battle, so PASS_WEAK is equally unsupported.
- ⇒ **`SEED_FEASIBILITY_PROVEN`** is the honest terminal T0 status: the seed mechanism is proven
  feasible; the terminal bit-stability classification is deferred to an empirical T1 step.

**What T1 must prove first (the acceptance that resolves the terminal verdict):** implement the
minimal local server seed patch, then run
`same config + same battle seed + same inputs → identical room_raw + identical winner`, twice.
- identical → upgrade to **demonstrated PASS_STRONG**;
- start conditions match but logs diverge → **PASS_WEAK** (and carry the CC-3 caveat forever:
  *"Determinism status: start_conditions_only — paired comparison is variance-reducing, not
  bit-reproducible."*).

## Consequence for the roadmap
- **T1 is unblocked.** The T1-start gate is `T0 ≠ FAIL`; `SEED_FEASIBILITY_PROVEN` satisfies it.
- **The terminal PASS_STRONG/PASS_WEAK bit is produced by T1's first step**, not by T0. T1's opening
  sub-step = the ~1-line `ladders.ts:473` seed patch on the local server clone + the seeded-twice
  bit-stability confirmation. That step resolves the classification the **2b-4 gate** reads
  (`T0 verdict ∈ {PASS_STRONG, PASS_WEAK}`): 2b-4 must read that T1-confirmed terminal verdict, not
  this T0 intermediate status. Then T1 proper (non-mirror scheduling threading the per-battle seed).
- **Verdict-taxonomy note:** `SEED_FEASIBILITY_PROVEN` is a deliberate intermediate status for a T0
  scoped as "prove, don't build". The spec/plan/roadmap 2b-4 gate wording (`∈ {PASS_STRONG,
  PASS_WEAK}`) is satisfied via T1's seeded-replay outcome, not this report — worth a one-line
  reconciliation in those docs when T1 lands.
- **Determinism status for later reports (until the T1 seeded-twice demo is green):**
  `seed_feasible — bit-reproducibility architecturally expected, empirically unconfirmed`.

**STOP** — per the T0 scope, no follow-up tasks started; awaiting review.
