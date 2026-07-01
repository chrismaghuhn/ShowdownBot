# 2b-3.5 T3e — Policy-Fidelity Hardening (pre-T4) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. **Git owner:
> Bau-Claude** (autonomous track paused). Steps use `- [ ]`. A small slice inserted BEFORE T4 (the first
> real measurement slice), so T4 doesn't measure against degenerate opponents. **Plan only — no code
> until reviewed.**

**Goal:** Make `simple_heuristic` (currently base-power-greedy) **type-aware**, and `greedy_protect`
(currently protects whenever available) **situational + non-degenerate**, while staying eval-only,
deterministic, and legal-fallback-safe. Both remain lightweight (no rollout/search/RL).

**Architecture:** Both live in `eval/opponents/` (eval-only, T3c). They gain access to `state` (already
passed by `agent_choose`) to read opponent types (via the existing `engine/typechart.effectiveness`) and
our own HP (`PokemonState.hp_fraction`). When `state`/type info is absent they **degrade to the current
behavior** (base-power / no protect) — never crash, always legal.

**Tech Stack:** `engine/typechart.effectiveness(move_type, defender_types)` (exists),
`engine/state.PokemonState.{types, hp_fraction}`, the T3c `_common.pick_best_pair` machinery.

---

## Cross-cutting rules
- **T3e-CC-1 — eval-only, live path untouched.** No `battle/` or live `decision`/`runner` change; the
  existing live-path guard (`tests/test_live_path_guard.py`) must still pass (`eval/opponents` importing
  `engine/typechart`+`engine/state` is fine — one-way; the guard checks the *reverse*).
- **T3e-CC-2 — deterministic + state-graceful.** No randomness. When `state is None` or opponent
  `types` are unknown (limited view), fall back to the current base-power / attack behavior. Always a
  legal `/choose`.
- **T3e-CC-3 — still lightweight.** No damage calc, no rollout, no search — only base power × type
  multiplier and HP thresholds.

---

## Task 1 — `simple_heuristic` type-awareness

**Files:** Modify `eval/opponents/policies.py`; Modify `client/gauntlet.py` (pass `state`/`our_side` to
the eval policies); Test `tests/test_opponents_policies.py`.

- [ ] **Step 1 — failing tests:**
  - a super-effective **low-BP** move beats a resisted **high-BP** move when opponent types are known
    (e.g. slot faces a Water/Ground target: a 60-BP Grass move (×4) beats a 120-BP Fire move (×0.25));
  - an **immune** target (×0) is never chosen over any positive-damage move;
  - a **spread** move (targets both foes) is scored by **max** effectiveness over the affected foes
    (Fix 1) — e.g. one foe ×2, one foe ×0.5 → multiplier 2.0;
  - **unknown info** (state=None, unknown target, or unknown types) → effectiveness `1.0`, falls back to
    **base-power** (current behavior), returns a legal `/choose`, never crashes;
  - **missing move metadata** (no `base_power`/`move_type`) → does not crash (Fix 2);
  - deterministic (two calls equal).
- [ ] **Step 2 — run, expect fail.**
- [ ] **Step 3 — implement** `simple_heuristic_choice(req, *, state=None, our_side=None, **_)`:
  - **Helper `target_types_for_action(action, state, our_side) -> list[tuple[str, ...]]`** (Fix 1) —
    returns the type-lists of the affected opponent active mons:
    - **single-target** move (`action.target ∈ {1,2}`): the one foe slot (`opp` `"a"`/`"b"`), if known;
    - **spread** move (target hits both foes — detect via `meta.target ∈ {"allAdjacentFoes","allAdjacent"}`
      or `action.target is None` for a damaging spread): **both** foe active slots, if known;
    - **unknown** target / unknown side / a foe with empty `types` → that foe contributes nothing;
    - **never crashes on partial state** (missing sides/mons → empty list).
  - per-slot score (closure over `state`/`opp`): `None → -1`; non-damaging `→ 0`; damaging:
    - `bp = meta.base_power` if present and `> 0`, else the current base-power behavior; if neither
      `base_power` nor `move_type` is available → **score 0** (Fix 2), never crash;
    - `types = target_types_for_action(action, state, us)`; `eff = max(effectiveness(meta.move_type, t)
      for t in types)` if `types` non-empty **and** `meta.move_type` known, else `1.0` (spread → **max**,
      Fix 1);
    - `score = bp × eff`.
  - reuse `_common.pick_best_pair(req, _slot)` (deterministic tie-break unchanged).
- [ ] **Step 4 — run, expect pass** (existing base-power tests still pass on the no-type-info path).
- [ ] **Step 5 — commit** `feat(2b-3.5 T3e): type-aware simple_heuristic (spread-max, base-power fallback)`.

## Task 2 — `greedy_protect` situational + no-degenerate-protect

**Files:** Modify `eval/opponents/policies.py`; Test `tests/test_opponents_policies.py`.

- [ ] **Step 1 — failing tests (Fix 3 — explicit HP cases):**
  - **both healthy** (HP high on both slots) → **both attack** (neither protects);
  - **low HP + healthy partner** → the low-HP slot **may Protect**, the healthy slot **attacks**;
  - **both low HP** (both slots have Protect) → **at most one Protect** (never double-protect), with a
    **deterministic tie-break** (same choice across two calls);
  - **`state=None`** → attacks / legal `/choose` fallback (no HP info → no protect);
  - deterministic overall.
- [ ] **Step 2 — run, expect fail.**
- [ ] **Step 3 — implement** `greedy_protect_choice(req, *, state=None, our_side=None, **_)` with a
  **custom pair loop** (the no-double-protect rule is a joint constraint):
  - per-slot: Protect scores high **only when our mon's `hp_fraction < LOW_HP` (e.g. 0.4)**, else a
    small negative (discourage protecting a healthy mon); damaging → `base_power`; else `0`.
  - **pair rule:** subtract a large penalty when BOTH slots are Protect → at most one slot protects.
  - `state is None` → treat HP as full → no protect (attack). Legal fallback via `/choose default`.
  - **Scope decision (Plan-Claude): DEFERRED.** Hard *consecutive*-Protect prevention (same mon two
    turns) needs per-battle policy memory (stateful) — **explicitly NOT in T3e**. The stateless
    situational-HP + no-double-protect rules substantially reduce spam, and Showdown's consecutive-Protect
    failure handles the rest. Recorded as **future optional debt** (see Out of scope).
- [ ] **Step 4 — run, expect pass.**
- [ ] **Step 5 — commit** `feat(2b-3.5 T3e): situational greedy_protect (no double-protect, HP-gated)`.

## Task 3 — dispatch threads state; live-path guard re-affirmed

**Files:** Modify `client/gauntlet.py` (`agent_choose` calls); Test `tests/test_live_path_guard.py`
(already exists — re-run).

- [ ] Thread `state=state, our_side=our_side` into the `greedy_protect`/`simple_heuristic` dispatch
  calls (they currently pass `req` only). `scripted_vgc` unchanged (request-only).
- [ ] Gate: existing live-path guard passes (no `battle/`/runner import of `eval/opponents`); the eval
  policies may import `engine/typechart`+`engine/state` (one-way, allowed).
- [ ] **Commit** `feat(2b-3.5 T3e): thread state into eval policy dispatch + guard`.

## Task 4 — tiny smoke (improved policies)

**Files:** Report `reports/2026-07-01-2b35-T3e-policy-fidelity-smoke.md`.

- [ ] Regenerate a tiny dev schedule covering **BOTH** improved policies (Fix 4):
  `policies=["simple_heuristic", "greedy_protect"]` × all **3 dev teams** = **exactly 6 battles** (no
  subset — so neither policy is silently untested live). Fresh seeded server + `PYTHONHASHSEED=0`,
  `--result-out`; confirm **0 invalid / 0 crash**, result rows valid, `panel_hash` present, seed-log
  alignment OK.
- [ ] Optional behavioral note: the improved opponents should be visibly less degenerate than before
  (e.g. fewer both-protect turns; type-appropriate move choices) — qualitative only, no strength gate.
- [ ] **Report + commit** `docs(2b-3.5 T3e): policy-fidelity smoke report`.

**Phase T3e gate:** type-aware `simple_heuristic` + situational `greedy_protect`, both deterministic +
legal + eval-only (live-path guard green); tiny smoke clean. Unblocks **T4** with competent opponents.

---

## Out of scope
No T4 ~50-game smoke, no T5 report generator, no Wilson/McNemar, no T6 held-out gate, no override, no
rollout/search/RL in the policies.

**Future optional debt (recorded, deferred by Plan-Claude):** stateful per-battle policy memory for hard
*consecutive*-Protect prevention (same mon two turns). Not required to start T4; the T3e stateless
HP-gate + no-double-protect is the first hardening stage. Revisit only if T4/T5 shows greedy_protect is
still degenerate.

## Self-review (writing-plans)
- Coverage: (1) simple_heuristic type-aware (Task 1) · (2) greedy_protect situational + no double-protect
  (Task 2) · (3) tests (Tasks 1–2) · (4) live-path guard (Task 3) · (5) both-policy smoke (Task 4). ✓
- Review fixes applied: **(1)** explicit `target_types_for_action` helper (single/spread/unknown; spread
  uses **max** effectiveness; never crashes on partial state); **(2)** move-metadata fallback (missing
  base_power/move_type → base-power behavior or score 0, never crash); **(3)** greedy_protect tests cover
  both-healthy / low+healthy / both-low / state=None with deterministic tie-break; **(4)** smoke runs
  BOTH improved policies × 3 dev teams = exactly 6 battles (no subset). Stateful consecutive-Protect
  **deferred** → future optional debt. ✓
- Building blocks verified present: `engine/typechart.effectiveness`, `PokemonState.{types, hp_fraction}`,
  `_common.pick_best_pair`. ✓
- Determinism + legality: all paths deterministic; `state`/type-info-absent → current behavior, legal
  `/choose`; no placeholders. ✓
