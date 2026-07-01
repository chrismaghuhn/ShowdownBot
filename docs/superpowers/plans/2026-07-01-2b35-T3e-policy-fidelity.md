# 2b-3.5 T3e — Policy Fidelity + Pre-T4 Harness Correctness — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. **Git owner:
> Bau-Claude** (autonomous track paused). Steps use `- [ ]`. A slice inserted BEFORE T4 (the first real
> measurement slice) so T4 neither measures against degenerate opponents NOR records wrong/untruthful
> harness metadata. **Plan only — no code until reviewed.**

**Goal:** (a) make `simple_heuristic` **type-aware** and `greedy_protect` **situational/non-degenerate**
(eval-only, deterministic, lightweight — no rollout/search/RL), and (b) fix three pre-T4 **harness
correctness** gaps found in review: **P0** per-battle counters, **P1** panel policy provenance, **P4**
result-row provenance — plus **P2** an activation-evidence gate proving the improved logic actually runs.

**Architecture:** Policies stay in `eval/opponents/` (eval-only); they gain `state` access (already
passed by `agent_choose`) for opponent types (`engine/typechart.effectiveness`) and our HP
(`PokemonState.hp_fraction`), degrading to current behavior when info is absent. The harness fixes touch
`client/gauntlet.py` (per-battle deltas), `eval/panel_schedule.py`/`eval/panel.py` (policy-subset
enforcement + team-hash plumbing), `eval/result_jsonl.py`/`cli.run_schedule` (row provenance). Live
decision path untouched.

**Tech Stack:** `engine/typechart.effectiveness`, `engine/state.PokemonState.{types, hp_fraction}`,
`_common.pick_best_pair`, `learning/provenance.git_sha_and_dirty`, the T3a `panel` content-hash.

---

## Cross-cutting rules
- **T3e-CC-1 — eval-only, live path untouched.** No `battle/` or live `decision`/`runner` change; the
  live-path guard (`tests/test_live_path_guard.py`) must still pass (eval/opponents importing
  `engine/typechart`+`engine/state` is one-way, allowed).
- **T3e-CC-2 — deterministic + state-graceful.** No randomness; `state`/type-info absent → current
  behavior; always a legal `/choose`.
- **T3e-CC-3 — still lightweight.** Only base power × type multiplier and HP thresholds — no calc,
  rollout, or search.
- **T3e-CC-4 — harness metadata must be truthful.** Per-battle counters are per-battle; `panel_hash`
  covers the policy list the schedule uses; result rows carry honest provenance (dirty flag, team hashes).

---

## Task P0 — Per-battle counter fix (MUST land before T4)

**Bug:** `on_battle_result` (T2, `gauntlet.py`) reports `invalid_choices = hero.invalid + villain.invalid`,
`crashes = hero.crashes + villain.crashes`, `decision_latency_p95_ms` from `hero.latencies` — but those
client counters are **cumulative over the run's lifetime**. In a multi-battle `run_local_gauntlet` the
2nd+ battle's row would carry run totals, not that battle's values. (The schedule path is games=1/row so
it's accidentally correct today, but the seam is wrong and T4 must be able to trust it.)

**Files:** Modify `client/gauntlet.py`; Test `tests/test_per_battle_counters.py`.

- [ ] **Step 1 — failing test (pure helper):** `per_battle_stats(snapshot, cur_invalid, cur_crashes,
  all_latencies) -> (invalid, crashes, latency_p95_ms, new_snapshot)`. Feed a **two-battle** cumulative
  sequence: battle 1 → cumulative `(invalid=2, crashes=1, latencies=[0.1,0.2])`; battle 2 → cumulative
  `(invalid=3, crashes=1, latencies=[0.1,0.2,0.5,0.3])`. Assert battle 1 delta = `(2,1, p95([0.1,0.2]))`
  and battle 2 delta = `(1,0, p95([0.5,0.3]))` — **per-battle**, not cumulative.
- [ ] **Step 2 — run, expect fail.**
- [ ] **Step 3 — implement:** a `snapshot = (invalid, crashes, len(latencies))` baseline reset at each
  battle start (the `init` frame / `start_game` seam); in `on_battle_result` compute deltas via
  `per_battle_stats` (latency p95 over `all_latencies[snapshot_len:]`) and pass the **per-battle** values
  into `_battle_result_record`. Keep the record's field names unchanged.
- [ ] **Step 4 — run, expect pass** (existing single-battle behavior unchanged — games=1 delta == total).
- [ ] **Step 5 — commit** `fix(2b-3.5 T3e P0): per-battle invalid/crashes/latency (delta, not cumulative)`.

## Task 1 — Type-aware `simple_heuristic`

**Files:** Modify `eval/opponents/policies.py`; Modify `client/gauntlet.py` (pass `state`/`our_side`);
Test `tests/test_opponents_policies.py`.

- [ ] **Step 1 — failing tests:** SE low-BP beats resisted high-BP when opp types known (Water/Ground
  target: 60-BP Grass ×4 beats 120-BP Fire ×0.25); immune (×0) never chosen over positive damage; a
  **spread** move scored by **max** effectiveness over the affected foes; unknown info (state=None /
  unknown target / unknown types) → eff `1.0` → base-power, legal `/choose`, no crash; missing move
  metadata (no `base_power`/`move_type`) → no crash; deterministic.
- [ ] **Step 2 — run, expect fail.**
- [ ] **Step 3 — implement** `simple_heuristic_choice(req, *, state=None, our_side=None, **_)`:
  - **Helper `target_types_for_action(action, state, our_side) -> list[tuple[str, ...]]`:** single-target
    → the one foe slot if known; spread (`meta.target ∈ {"allAdjacentFoes","allAdjacent"}` or a damaging
    spread) → **both** foe active slots if known; unknown target/side or empty `types` → contribute
    nothing; **never crashes on partial state**.
  - per-slot score: `None → -1`; non-damaging `→ 0`; damaging → `bp × eff` where `bp = base_power` (>0) or
    the current base-power behavior, and if neither `base_power` nor `move_type` is available → **score 0**
    (never crash); `eff = max(effectiveness(move_type, t) for t in types)` if types non-empty and
    `move_type` known, else `1.0` (**spread → max**). Reuse `_common.pick_best_pair`.
- [ ] **Step 4 — run, expect pass** (base-power tests still pass on the no-type-info path).
- [ ] **Step 5 — commit** `feat(2b-3.5 T3e): type-aware simple_heuristic (spread-max, base-power fallback)`.

## Task 2 — Situational `greedy_protect` (HP-gated, no double-protect)

**Files:** Modify `eval/opponents/policies.py`; Test `tests/test_opponents_policies.py`.

- [ ] **Step 1 — failing tests (explicit HP cases):** both-healthy → both attack; low-HP + healthy
  partner → low may Protect / healthy attacks; both-low → **at most one Protect** with a deterministic
  tie-break; `state=None` → attacks / legal fallback; deterministic.
- [ ] **Step 2 — run, expect fail.**
- [ ] **Step 3 — implement** `greedy_protect_choice(req, *, state=None, our_side=None, **_)` with a custom
  pair loop: Protect scores high only when our slot's `hp_fraction < LOW_HP` (e.g. 0.4), else a small
  negative; damaging → `base_power`; else 0; **pair rule:** big penalty when BOTH slots Protect (≤1
  protects). `state=None` → HP treated full → attack. Legal fallback via `/choose default`.
  - **Scope decision (Plan-Claude): stateful consecutive-Protect DEFERRED** → future optional debt.
- [ ] **Step 4 — run, expect pass.**
- [ ] **Step 5 — commit** `feat(2b-3.5 T3e): situational greedy_protect (HP-gated, no double-protect)`.

## Task 3 — Dispatch threads `state`; live-path guard re-affirmed
- [ ] Thread `state=state, our_side=our_side` into the `greedy_protect`/`simple_heuristic` dispatch calls
  (`scripted_vgc` unchanged). Live-path guard passes.
- [ ] **Commit** `feat(2b-3.5 T3e): thread state into eval policy dispatch + guard`.

## Task P1 — Panel policy provenance

**Problem:** `generate_dev/heldout_schedule` validates policies against the *registry* (`is_known`), NOT
against `panel.policies`. So a generated schedule can use policies the `panel_hash` never covered (T3d's
smoke used `scripted_vgc`, which is not in `panel_v001.policies=[heuristic,max_damage]`). `panel_hash`
must truthfully cover the policies the schedule uses.

**Files:** Modify `eval/panel_schedule.py` (`_resolve_policies`); Modify `config/eval/panels/panel_v001.yaml`
(intentional hash change); Update **current** `panel_hash` references in `tests/test_panel.py`,
`tests/test_panel_schedule.py`; add a **supersession note** (not a rewrite) to the T3d report.

- [ ] **Step 1 — failing tests:** `_resolve_policies` raises if any chosen policy ∉ `panel.policies`
  (both default and explicit-list paths); a panel listing all reproducible policies generates cleanly.
- [ ] **Step 2 — run, expect fail.**
- [ ] **Step 3 — implement:** enforce **`chosen ⊆ panel.policies`** (fail fast). Update
  `panel_v001.yaml` `policies:` to the full reproducible panel set
  `[heuristic, max_damage, greedy_protect, simple_heuristic, scripted_vgc]` — this **intentionally
  changes `panel_hash`** (panel_hash covers the policy list). (Keep `panel_v001`; no `panel_v002` unless
  the reviewer prefers.)
  - **Provenance discipline (do NOT retcon history):**
    - The **T3d report keeps its OLD observed `panel_hash=9aa3af95e461881f`** as a historical fact of
      that smoke run — do not rewrite it to the new hash.
    - Add a one-line **supersession note** to the T3d report: *"T3e corrected `panel_v001.policies`,
      changing `panel_hash` from `9aa3af95e461881f` (OLD) to `<NEW>`. The T3d smoke remains a historical
      load-smoke; the T3e smoke supersedes it for pre-T4 readiness."*
    - The **T3e report uses the NEW `panel_hash`** (its rows carry it).
    - **Tests / current references** that assert *the current* `panel_v001` hash update to `<NEW>`;
      historical-report text is left as-is.
- [ ] **Step 4 — run, expect pass.**
- [ ] **Step 5 — commit** `fix(2b-3.5 T3e P1): enforce policy ⊆ panel + panel_v001 policy list (hash change)`.

## Task P4 — Result-row provenance hardening

**Files:** Modify `eval/result_jsonl.py` (schema), `eval/schedule.py` (`ScheduleRow` team-hash fields),
`eval/panel_schedule.py` (populate hashes), `eval/panel.py` (expose the content-hash helper),
`cli.run_schedule`; Tests `tests/test_result_jsonl.py`, `tests/test_panel_schedule.py`.

- [ ] **Step 1 — failing tests:** `dirty` is a **required** row field; `hero_team_hash`/`opp_team_hash`
  are **nullable**; a generated schedule carries per-row `opp_team_hash` (from the panel team's
  `team_hash`) and `hero_team_hash` (content-hash of the hero team file), and `write_schedule_yaml` →
  `load_schedule` round-trips them; legacy schedules → `null`; `battle_id` is documented as the **pairing
  key** (repeats across paired version runs), not a globally unique row id.
- [ ] **Step 2 — run, expect fail.**
- [ ] **Step 3 — implement:**
  - `result_jsonl`: add `dirty` to `REQUIRED_FIELDS`; add `hero_team_hash`, `opp_team_hash` to
    `NULLABLE_FIELDS`. Update the `battle_id` docstring: **pairing key, not unique row id.**
  - `panel.py`: make the content-hash public (e.g. `team_content_hash(teams_root, team_path)`).
  - `schedule.py`: `ScheduleRow` gains optional `hero_team_hash`/`opp_team_hash` (loader reads them,
    default `None`; schedule_hash **unchanged** — hashes are not part of the identity payload).
  - `panel_schedule.py`: the generator sets `opp_team_hash` = the panel team's `team_hash` and
    `hero_team_hash` = `team_content_hash(teams_root, hero_team_path)`; `write_schedule_yaml` emits them.
  - `cli.run_schedule`: write `dirty` (from `git_sha_and_dirty()[1]`), `hero_team_hash`, `opp_team_hash`
    (from the row) into each T2 row; legacy rows → `null`.
- [ ] **Step 4 — run, expect pass.**
- [ ] **Step 5 — commit** `feat(2b-3.5 T3e P4): row provenance (dirty + team hashes) + battle_id doc`.

## Task 4 — Tiny smoke with activation evidence (P2) + both policies

**Files:** Modify `eval/opponents/` (env-gated telemetry), Report `reports/2026-07-01-2b35-T3e-policy-fidelity-smoke.md`.

- [ ] **Step 1 — activation telemetry (P2):** env-gated `SHOWDOWN_EVAL_POLICY_TELEMETRY=<path>` (unset →
  no-op, bit-identical). When set, `simple_heuristic` appends an event when the **type-effectiveness path
  fired** (`eff != 1.0`), and `greedy_protect` when the **HP-gated protect fired**. (Behavioral unit
  tests in Tasks 1–2 already prove the paths *can* fire deterministically; this proves they fire LIVE.)
- [ ] **Step 2 — smoke:** generate a tiny dev schedule covering **BOTH** improved policies —
  `policies=["simple_heuristic", "greedy_protect"]` × all **3 dev teams** = **exactly 6 battles** (no
  subset). Fresh seeded server + `PYTHONHASHSEED=0` + `SHOWDOWN_EVAL_POLICY_TELEMETRY` + `--result-out`.
  Assert: **0 invalid / 0 crash**; result rows valid; **per-battle counters correct** (P0); `panel_hash`
  (new) + `dirty` + team hashes present (P4); seed-log alignment OK; **activation evidence (P2):**
  `simple_heuristic` type-effectiveness ≥ 1 AND `greedy_protect` HP-gated protect ≥ 1 — if the HP-gate
  doesn't fire naturally in 6 short battles, cover it with a deterministic **fixture** request/state
  proving the gate triggers (per the review: fixture is acceptable when hard to force live).
- [ ] **Step 3 — report + commit** `docs(2b-3.5 T3e): policy-fidelity + harness-correctness smoke report`.

**Phase T3e gate:** per-battle counters correct (P0); `chosen ⊆ panel.policies` enforced + `panel_v001`
policy list truthful (P1); type-aware `simple_heuristic` + situational `greedy_protect`, deterministic +
eval-only (live-path guard green); row provenance (dirty + team hashes) present (P4); tiny smoke clean
with **activation evidence** for both improvements (P2). Unblocks **T4**.

---

## Out of scope
No T4 ~50-game smoke, no T5 Wilson/McNemar report generator, **no full `config_hash` redesign**, **no
panel growth**, no T6 held-out gate, no override, no rollout/search/RL in the policies.

**Future optional debt (deferred):** stateful per-battle policy memory for hard *consecutive*-Protect
prevention (same mon two turns) — not required to start T4; the T3e stateless HP-gate + no-double-protect
is the first hardening stage. Revisit only if T4/T5 shows greedy_protect still degenerate.

## Self-review (writing-plans)
- Coverage: policy fidelity (Tasks 1–2) + P0 per-battle counters + P1 panel policy provenance + P2
  activation evidence + P4 row provenance + live-path guard (Task 3) + both-policy smoke (Task 4). ✓
- Truthfulness: P1 changes `panel_hash` intentionally — **current** references (tests) update to the new
  hash, but the **T3d report's historical `9aa3af95e461881f` is preserved** with a supersession note (no
  retcon of what actually ran); T3e report uses the new hash. P4 adds `dirty`/team hashes without touching
  `schedule_hash` (hashes not in the identity payload); `battle_id` re-documented as pairing key. ✓
- Determinism + legality + eval-only preserved; `state`/type/metadata absent → current behavior, legal
  `/choose`; telemetry env-gated (no-op when unset). ✓
- No placeholders; stateful consecutive-Protect explicitly deferred as recorded debt.
