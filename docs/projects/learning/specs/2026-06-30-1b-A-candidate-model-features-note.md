# 1b-A amendment: CandidateModelFeatures (KO/survive counts in the trace) — design note

**Why:** `features.py` has no `DamageModel` handle, and the no-recomputation rule
forbids re-deriving eval-internal features. So the KO/survive counts are captured in
the **trace** (1b-A), where the decision context is in scope.

**No-drift principle:** the counts MUST use the *same* semantics as the bot's real
KO logic, which lives in `engine/belief/game_mode.py::compute_game_mode`
(attacker `OFFENSE` vs defender `DEFENSE` book preset, **known** moves only —
`move_names` — over **active living** mons, criterion `is_guaranteed_ohko`). The
unused `DamageModel.secures_ko/has_ko_chance/survives_for_sure` use a *frail*
(`OFFENSE`) defender preset and would **drift** from game_mode — so they are NOT used.
Instead we extract a shared helper from `compute_game_mode`.

## The six questions, pinned
1. **`ko_secured_count`** — candidate-level. Distinct opponent **active slots**
   guaranteed-OHKO'd by one of the candidate's **actually selected** damaging moves
   against its **selected** target (our `OFFENSE` vs opp `DEFENSE`, `is_guaranteed_ohko`).
2. **`ko_threatened_count`** — decision-level. Our active mons that **at least one
   known opponent move** can guarantee-OHKO (same enumeration as `compute_game_mode`).
3. **`survives_for_sure_count`** — decision-level. Our active mons for which **no
   known opponent move can OHKO** (not `can_ohko` for all known moves).
4. **Top-K?** `ko_secured` only for exported Top-K candidates; `ko_threatened` /
   `survives` are decision-level and copied to each candidate. **v1 limitation
   (documented + tested):** switch candidates use the **pre-switch** threat state.
5. **Calc reuse:** threat/survive reuse the extracted incoming game_mode helper
   (the batch `compute_game_mode` already runs at decision time → warm); secured-KO
   uses the **same game_mode-compatible preset/path**, never independent model-method
   semantics. ~0 new Node round-trips.
6. **Unknowns:** unknown opponent moves are **ignored exactly like
   `compute_game_mode`** — same deliberate blind spot, kept consistent.

## Implementation (no duplication)
- `game_mode.py`: extract `_ko_request(attacker_mon, move, defender_mon, book, field)`
  (the `OFFENSE`-vs-`DEFENSE` `DamageRequest`); add `ko_threat_counts(state, our_side,
  *, calc, book) -> (threatened, survives)` (one batch over active-our × active-opp ×
  known-moves, per-mon attribution) and `guaranteed_ohko(attacker_mon, move,
  defender_mon, *, calc, book, field) -> bool`. **Refactor `compute_game_mode` to use
  `ko_threat_counts`** for its must_react check (`threatened > 0`) — behaviour
  preserved (existing game_mode tests stay green).
- `battle/decision_trace.py`: `@dataclass CandidateModelFeatures(ko_secured_count=0,
  ko_threatened_count=0, survives_for_sure_count=0)`; field `model_features:
  CandidateModelFeatures` on `CandidateTrace`.
- `battle/decision.py` trace block: `ko_threatened/survives` once via
  `ko_threat_counts`; `ko_secured` per candidate via `guaranteed_ohko` over the
  candidate's selected damaging move→target pairs (distinct opp slots).

## Tests
- `compute_game_mode` and `ko_threat_counts` agree on a known guaranteed-OHKO fixture
  (must_react ⟺ threatened > 0).
- `ko_secured_count` counts **distinct target slots**, not number of moves.
- `ko_secured_count` ignores non-damaging moves and non-selected targets.
- switch-candidate v1 limitation = pre-switch threat state (documented/tested).
- `trace=None` vs `trace=DecisionTrace()` still returns the identical chosen action.
- full suite green.
