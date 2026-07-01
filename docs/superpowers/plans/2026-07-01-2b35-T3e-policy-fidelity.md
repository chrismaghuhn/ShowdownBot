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
  - with `state=None` (or unknown types), it falls back to **base-power** (current behavior) and returns
    a legal `/choose`;
  - deterministic (two calls equal).
- [ ] **Step 2 — run, expect fail.**
- [ ] **Step 3 — implement** `simple_heuristic_choice(req, *, state=None, our_side=None, **_)`:
  - `opp = _opp_side(our_side or req.side.id or "p1")`.
  - per-slot score (closure over `state`/`opp`): `None → -1`; non-damaging `→ 0`; damaging →
    `base_power × eff`, where `eff = effectiveness(meta.move_type, target_mon.types)` when
    `action.target ∈ {1,2}` and `state.sides[opp]["a"/"b"].types` is non-empty, else `1.0`.
  - reuse `_common.pick_best_pair(req, _slot)` (deterministic tie-break unchanged).
- [ ] **Step 4 — run, expect pass** (existing base-power tests still pass on the no-type-info path).
- [ ] **Step 5 — commit** `feat(2b-3.5 T3e): type-aware simple_heuristic (base-power fallback)`.

## Task 2 — `greedy_protect` situational + no-degenerate-protect

**Files:** Modify `eval/opponents/policies.py`; Test `tests/test_opponents_policies.py`.

- [ ] **Step 1 — failing tests:**
  - **no double-protect:** even when BOTH slots have Protect available (and both low HP), the chosen
    joint action does NOT protect both slots;
  - **situational:** a **healthy** mon (high HP) attacks rather than protects; a **low-HP** mon protects
    (when `state` gives HP);
  - with `state=None`, it falls back to attacking (returns a legal `/choose`);
  - deterministic.
- [ ] **Step 2 — run, expect fail.**
- [ ] **Step 3 — implement** `greedy_protect_choice(req, *, state=None, our_side=None, **_)` with a
  **custom pair loop** (the no-double-protect rule is a joint constraint):
  - per-slot: Protect scores high **only when our mon's `hp_fraction < LOW_HP` (e.g. 0.4)**, else a
    small negative (discourage protecting a healthy mon); damaging → `base_power`; else `0`.
  - **pair rule:** subtract a large penalty when BOTH slots are Protect → at most one slot protects.
  - `state is None` → treat HP as full → no protect (attack). Legal fallback via `/choose default`.
  - Note (scope): hard *consecutive*-Protect prevention (same mon two turns) needs per-battle policy
    memory (stateful) — **out of scope** for this small slice; the situational-HP + no-double-protect
    rules substantially reduce spam and Showdown's consecutive-Protect failure handles the rest. Flag if
    the reviewer wants the stateful version.
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

- [ ] Regenerate a tiny dev schedule with `policies=["simple_heuristic", "greedy_protect"]` (2 policies ×
  3 dev teams = 6 battles, or a subset), fresh seeded server + `PYTHONHASHSEED=0`, `--result-out`;
  confirm **0 invalid / 0 crash**, result rows valid, `panel_hash` present, seed-log alignment OK.
- [ ] Optional behavioral note: the improved opponents should be visibly less degenerate than before
  (e.g. fewer both-protect turns; type-appropriate move choices) — qualitative only, no strength gate.
- [ ] **Report + commit** `docs(2b-3.5 T3e): policy-fidelity smoke report`.

**Phase T3e gate:** type-aware `simple_heuristic` + situational `greedy_protect`, both deterministic +
legal + eval-only (live-path guard green); tiny smoke clean. Unblocks **T4** with competent opponents.

---

## Out of scope
No T4 ~50-game smoke, no T5 report generator, no Wilson/McNemar, no T6 held-out gate, no override, no
stateful/consecutive-Protect memory (optional follow-up), no rollout/search/RL in the policies.

## Self-review (writing-plans)
- Coverage: (1) simple_heuristic type-aware (Task 1) · (2) greedy_protect situational + no double-protect
  (Task 2) · (3) tests — type-aware beats base-power, resisted-high-BP loses to SE-low-BP, no
  double-protect, legal fallback (Tasks 1–2) · (4) live-path guard (Task 3) · (5) tiny smoke (Task 4). ✓
- Building blocks verified present: `engine/typechart.effectiveness`, `PokemonState.{types, hp_fraction}`,
  `_common.pick_best_pair`. ✓
- Determinism + legality: all paths deterministic; `state`/type-info-absent → current behavior, legal
  `/choose`. ✓
- No placeholders; the only deferred item is the optional stateful consecutive-Protect memory (called out).
