# poke-env 0.15.x Reference Audit — Champions Solar Beam / `target`

**Date:** 2026-07-14  
**Verdict:** **Reference useful** (not a foundation swap)  
**Scope:** Isolated audit slice — no gauntlet rewrite, no DecisionTrace/Provenance changes.

## Framing

poke-env would not have been the right **foundation** for this repo: we are an eval/trace/provenance
machine, not a thin Showdown client. As a **reference parser** for live Showdown request quirks,
poke-env 0.15.0 is useful now — specifically for the Champions `target`-omission case that blocked
P4 rain held-out (`Meganium` / `Solar Beam`).

## Setup

| Item | Value |
|------|-------|
| poke-env | **0.15.0** (pip, audit-only — not a project dependency) |
| Our stack | `BattleRequest` / `MoveSlot` pydantic, `enumerate_slot_pairs` |
| Fixture | `showdown_bot/tests/fixtures/request_doubles_moves.json` |
| Champions gap variant | Same fixture, `Solar Beam` entry with `target` removed |
| Local audit helper | `tools/_poke_env_champions_audit.py` (not committed, not a dependency, not CI) |

## Champions / format support in poke-env 0.15.0

- **No** `gen9championsvgc2026regma` string, Champions format module, or M-A-specific parser code
  in the installed package.
- Release notes mention “Pokémon Champions data” (static dex/move tables), not a dedicated Champions
  VGC client path.
- poke-env treats this like any other gen-9 doubles request: `DoubleBattle.parse_request` +
  static `gen9moves.json` fallback.

**Implication:** poke-env does not “already support Champions”; it supports **generic gen-9
Showdown JSON** with a more permissive move-slot parse than ours.

## Parser diff — the P4 failure mode

| Case | Our `BattleRequest` | poke-env `parse_request` |
|------|---------------------|--------------------------|
| Fixture with `"target": "normal"` on Solar Beam | **OK** | **OK** |
| Champions gap (no `target` on Solar Beam) | **FAIL** — pydantic `missing` on `('active', 1, 'moves', 3, 'target')` | **OK** |

### Why poke-env survives the gap

1. `available_moves_from_request` indexes moves **by `id` only** — it never reads per-slot
   `target` from the request JSON.
2. `Move.deduced_target` falls back to static move data (`gen9moves.json`: Solar Beam
   `"target": "normal"`) when no request override is present.
3. Strict consistency checks (`check_move_consistency`) compare request `target` **only if**
   the field is present — omitted fields skip the assert path.

### Why we fail

In `showdown_bot/src/showdown_bot/models/request.py`, `MoveSlot.target` is currently required.
Champions (or at least the rain held-out server payload) can omit it; gauntlet dies before action
enumeration.

### Recommended fix direction (our stack, not poke-env)

Make `target` optional on `MoveSlot` and backfill from existing `get_move_meta(move.id).target`
(same pattern as `pp`/`maxpp` optional for Struggle-only requests). poke-env confirms the server
omission is plausible and the static fallback is reasonable — it does **not** prescribe copying
their full battle object model.

## Legal actions / action masks

On the minimal doubles fixture (no opponent actives seeded):

| Stack | Joint legal choices |
|-------|---------------------|
| Ours (when parse succeeds) | **126** slot-pairs |
| poke-env | **82** `DoubleBattleOrder`s |

Differences are expected on a partial board, not a Champions-specific divergence:

- **Target semantics for `normal`:** our `_move_targets("normal")` → foe slots `[1, 2]` only;
  poke-env’s `get_possible_showdown_targets` can include ally `-1` for `normal` when both sides
  are populated.
- **Enumeration shape:** we emit `SlotPair` with explicit tera variants; poke-env emits
  `SingleBattleOrder` messages (`/choose move …`, switches, pass).
- **Opponent state:** poke-env action count shrinks without seeded opponent actives; not an
  apples-to-apples strength comparison.

**For the Solar Beam gap specifically:** once poke-env parses the request, Solar Beam is present
in `available_moves[1]` with `deduced_target = NORMAL` from static data — identical with and
without the missing request field. We never reach that stage.

## Thin adapter prototype (smoke only)

Attempted wrapping `heuristic_choose_for_request` behind poke-env’s `Player.choose_move`:

- **Blockers:** needs live `BattleState` + `SpreadBook` (not just raw request JSON); return type
  is our `SlotPair`, not poke-env `BattleOrder`.
- **Verdict:** a comparison adapter is ~50 lines of glue (request JSON → `BattleRequest` →
  `SlotPair` → `DoubleBattleOrder`) but adds no production value beyond this audit. Not pursued
  further.

## Reference useful / not useful

| Question | Answer |
|----------|--------|
| Replace gauntlet / client foundation? | **No** |
| Use as ongoing CI dependency? | **No** (keep audit isolated) |
| Use as reference for Champions `target` omission? | **Yes** |
| Use for legal-action golden tests? | **Partial** — good for “does parse succeed?” diffs; full mask parity needs fully seeded battles and is not worth maintaining |
| Champions format already handled by poke-env? | **No** — generic gen-9 doubles only |

## Concrete parser diffs (summary)

1. **Required vs optional `target` on move slots** — blocking gap on our side; poke-env tolerant.
2. **Target source** — we trust server JSON; poke-env trusts static `gen9moves.json` when request
   omits `target` (and largely ignores request `target` for enumeration anyway).
3. **No Champions-specific code path** in poke-env 0.15.0 — any “Champions support” in release
   notes is data-table coverage, not format-id routing.
4. **Action masks** — structurally different APIs; poke-env is not a drop-in oracle for our
   `enumerate_slot_pairs` without a full battle-state fixture harness.

## Next step (in our stack, separate from this audit)

Parser follow-up for rain held-out: optional `MoveSlot.target` + `get_move_meta` backfill + regression
test with Champions-shaped JSON (Solar Beam without `target`). This audit does not block that work;
it validates the fix pattern.
