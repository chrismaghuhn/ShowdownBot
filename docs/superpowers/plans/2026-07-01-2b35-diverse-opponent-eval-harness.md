# 2b-3.5 — Diverse-Opponent-Eval-Harness — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. **Git owner:
> Bau-Claude** (autonomous track paused). **T0 is a HARD BLOCKER** — T1+ start ONLY after the T0 verdict.
> **No code runs until this plan is reviewed + final.** Companion spec:
> `docs/superpowers/specs/2026-07-01-2b35-diverse-opponent-eval-harness.md`.

**Goal:** A fair, reproducible **non-mirror** eval harness — the *measurement scale* that must exist
before any 2b-4 gated override. Reuses the existing local-server `gauntlet`; the live battle path is
untouched (path B/C). Produces per-opponent Wilson-CI winrates + a paired McNemar version comparison +
a versioned, hashed report.

**Tech Stack:** Python (stdlib stats: Wilson/McNemar), the existing `client/gauntlet.py` + local
`node pokemon-showdown start --no-security 8000` (@ f8ac140). No new sim, no training, no RL.

---

## Cross-Cutting Rules (hold across ALL tasks — the harness invariants)

- **CC-1 — Shadow has NO own winrate.** `--brain shadow` plays the heuristic action (2b-3 is log-only),
  so its games are identical to `--brain heuristic`. The harness must therefore report shadow's winrate
  as *the heuristic's* (never a separate number); shadow contributes the **divergence + counterfactual**
  set on the same panel, not a winrate.
- **CC-2 — `prev_version` is a pinned artifact.** The regression anchor = a **pinned, versioned**
  heuristic-only checkpoint (git_sha / config), loaded via a config flag — never "whatever main is now".
  Cross-version comparisons are meaningless without it being frozen.
- **CC-3 — Determinism caveat travels with every report.** The T0c verdict (`PASS_STRONG` /
  `PASS_WEAK`) is written into every report. On `PASS_WEAK`: the permanent line *"Determinism status:
  start_conditions_only — paired comparison is variance-reducing, not bit-reproducible."*
- **CC-4 — McNemar reports `n_discordant`; flags UNDERPOWERED.** The paired version-delta reports the
  number of discordant pairs. If `n_discordant` is too small (below a stated floor), the report says
  **UNDERPOWERED** and does NOT claim a significant Δ — no over-claiming on a handful of flips.
- **CC-5 — Held-out is READ-ONLY / no tuning.** No hyperparameter (override threshold, K, λ, fusion
  weights) is ever tuned or even inspected on the held-out pool — only at the gate. Same discipline as
  INV-6 for feature leakage. Tuning happens on dev only.

---

## Read-only findings (2026-07-01 — baked in so tasks don't re-derive them)
- `run_local_gauntlet` (`gauntlet.py:298`) is **MIRROR-only** (hero + villain both `packed_team=packed`).
- The challenge is **SEEDLESS**: `hero_conn.send("|/challenge {villain}, {format}")` (`gauntlet.py:386`).
- `GauntletStats` is **AGGREGATE-only** (games/ties/wins/invalid_choices/crashes/latencies); `room_raw`
  (raw protocol frames) is in memory (`gauntlet.py:117`), not persisted.
- Bot heuristic is deterministic; the `random` villain (`pick_random_pair`) is **UNSEEDED**.
- `SHOWDOWN_DATASET_RUN_SEED` = export ID-minting seed ONLY; does NOT affect battle outcomes.
- ⇒ each T1+ item is a **small isolated `gauntlet` addition**, not a new system.

---

## T0 — Determinism-/Seed-Feasibility-Probe (HARD BLOCKER — measure & prove only)

The single gate for the whole harness. **No harness build in T0** — a throwaway probe + a committed
verdict report. Details in spec **§T0**. Summary:

- **T0a — Baseline determinism without a seed.** Same fixed config **R≈5–8×** via `run_local_gauntlet`
  (read-only). Capture `room_raw` + `winner` per run; compare `room_raw`/`winner` identity +
  `first_divergence_frame` + `divergence_reason` (damage roll / crit / speed-tie / secondary / accuracy).
  Quantifies the current non-determinism + locates the RNG source.
- **T0b — Seed-injection feasibility (prove, don't build).** Determine whether the local Showdown can
  take a **per-battle** PRNG seed (`/challenge` seed / `@@@` rules / custom format `PRNGSeed` / server
  flags / battle-init / last-resort minimal server patch). Evidence required.
- **T0c — Verdict:** `PASS_STRONG` (room_raw+result bit-stable) / `PASS_WEAK` (start-conditions only,
  carry CC-3 caveat forever) / `FAIL` (seeds_dont_control → T1+ BLOCKED, re-scope).
- **Deliverable:** `reports/2026-07-01-2b35-T0-determinism-probe.md` with the identity table, the
  feasibility evidence, and the verdict. **Gate:** a verdict exists; if `FAIL`, T1+ do not start.

---

## T1 — Non-Mirror-Team-Scheduling  *(only if T0 ≠ FAIL)*
- **Deliverable:** the gauntlet plays **two different teams** (ours vs an opponent team), driven by a
  **schedule file** — a versioned list of `(config, opp_policy, opp_team, seed)` rows. If T0b PASS,
  each battle also gets its per-battle seed (the T0b path); if PASS_WEAK, the seed sets start conditions.
- **Seam:** `run_local_gauntlet` currently passes `packed_team=packed` to BOTH clients (`gauntlet.py:347-348`)
  and challenges seedless (`:386`). Extend to accept a per-side team + (if feasible) inject the seed at
  the challenge. Small, isolated — the live decision path is untouched.
- **Gate:** a 2-row schedule runs two *different*-team battles; re-running a row is stable to the T0c level.

## T2 — Per-Battle-Result-JSONL  *(pairing substrate)*
- **Deliverable:** one JSONL row per battle: `config, opp_policy, opp_team, seed, winner, turns,
  end_hp_diff, invalid, crashes, timeouts, decision_latency_p95, trace_path`. This is what McNemar pairs on.
- **Seam:** `GauntletStats` is aggregate-only; `on_hero_result(winner)` (`gauntlet.py:355`) is where a
  per-battle record is emitted. `winner`/`turns`/`end-HP` come from `room_raw`; safety counters already
  exist (`self.invalid`/`self.crashes`/`latencies`).
- **Gate:** a smoke run writes one valid row per battle; rows join to the schedule by `(config,opp_policy,opp_team,seed)`.

## T3 — Panel v001  *(frozen opponents + teams, hashed)*
- **Deliverable:** `panel_v001` = the opponent policies + the curated team pool, **frozen + hashed**.
  Policies: reuse `random`/`max_damage`; add rule-based `greedy_protect`, `simple_heuristic`,
  `scripted_vgc` (dock onto the existing `max_damage`/`random` agent pattern — a `choose_with_fallback`-
  like entry). `prev_version` per CC-2 (pinned checkpoint). Team pool ~8–12 archetype-diverse teams
  (real spreads), split **dev (~6) / held-out (~4)** (CC-5). Panel + schedule get a `panel_hash` /
  `schedule_hash`.
- **Gate:** the panel loads, each policy plays a legal battle, the dev/held-out split is enforced + hashed.

## T4 — Smoke-Schedule  *(the fast dev loop)*
- **Deliverable:** a `smoke` preset (~50 games — a cell subset × ~10 seeds, ~20–40 min) that runs
  end-to-end (schedule → gauntlet → per-battle JSONL) with `--strict`.
- **Gate:** `smoke` completes with **0 crashes / 0 invalid / 0 timeouts, p95 < 3 s** (the safety floor).

## T5 — Report-Generator  *(the scale's readout)*
- **Deliverable:** from the per-battle JSONL → a Markdown+JSON report: per-cell + aggregate **Wilson-95%
  CI** winrate, **paired McNemar Δ** with `n_discordant` + UNDERPOWERED flag (CC-4), margin (turns /
  end-HP), safety rollup, and the CC-3 determinism status. Carries `panel_hash`/`schedule_hash`/
  `config_hash` (INV-7-analog, mechanically checkable).
- **Gate:** the report reproduces from a fixed JSONL; hashes present; CC-3/CC-4 lines emitted correctly.

## T6 — Held-out-Gate-Struktur + Heuristik-Baseline  *(the acceptance the harness itself must pass)*
- **Deliverable:** the held-out gate wiring + a **pinned heuristic-only baseline** captured on **dev and
  held-out** (the first fair non-mirror number — the "does the foundation hold?" answer). Per-opponent
  floor gate (no single opponent significant drop) + non-inferiority on held-out.
- **Gate (harness acceptance):** reproducible `(config, schedule)` → same results to the T0c level;
  held-out split enforced; report auto-generated with all hashes; safety floor holds; the heuristic
  baseline is frozen as the reference for every later slice.

---

## 2b-4 Unblock condition
A 2b-4 gated override may be **planned/attempted only when**:
```
T0 verdict ∈ {PASS_STRONG, PASS_WEAK}   (reproducibility at least start-conditions-level)
AND T4 green                            (smoke schedule runs clean, safety floor holds)
AND T6 green                            (held-out gate structure + pinned heuristic baseline exist)
```
Until then, 2b-4 stays blocked (it would otherwise fall back to the misleading mirror).

## Execution note
**T0 runs first, alone**, as a measure-and-prove probe (no harness/live code). After the T0 verdict +
your review, we finalize + execute T1–T6 as PR slices, each with its own TDD breakdown. Nothing is built
before this plan is reviewed + final.
