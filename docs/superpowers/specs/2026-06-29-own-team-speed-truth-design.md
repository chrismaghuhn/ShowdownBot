# Own-Team Knowledge, Slice 1: Speed Truth — Design

**Goal:** Make the bot use the truth about its OWN team's speed — its known items
(Choice Scarf!) and a correct treatment of speed ties — instead of under-rating
its own mons and losing every tie by fiat.

**Status:** approved (brainstorming, 2026-06-29). First slice of the larger
"full own-team knowledge" vision (later slices: bench knowledge for switches,
tera planning).

## Context

The speed machinery is mostly sound: `engine/speed.py::effective_speed` correctly
applies boosts, Tailwind (×2), paralysis (÷2), Choice Scarf (×1.5), booster (×1.5),
and deliberately excludes Trick Room (TR is sort-order only, in `sort_actions`).
`SpeedOracle.our_speed` feeds our real base speed (from request stats) through it.
Two concrete gaps remain:

1. **Our own item is never known.** `merge_request` (state.py) does NOT set our
   item despite its docstring claiming it does — it merges only level/gender/
   types/moves/HP. So `speed_modifiers_from_state` sees `item_known=False` and
   never applies our **Choice Scarf (Landorus-T)** → we under-rate our speed by
   1.5×, mis-judge who outspeeds, see false threats, and pick less aggressive
   lines. This is the bigger lever.
2. **Ties lost by fiat.** `sort_actions` uses `tie = 1 if a.is_ours` → our mon
   loses *every* speed tie deterministically. In a mirror, identical mons tie
   exactly → we always assume we're slower.

Both fixes are *positive-confidence* corrections (we're faster / not auto-last),
so unlike the Stage-C real-spreads change they are not expected to regress the
mirror. The mirror-vs-`max_damage` gauntlet is used only as a **catastrophe
guardrail** here, never as an optimization target (it rewards recklessness).

---

## Fix A — Own-item truth (build first; small, correct, broadly useful)

Set our own item authoritatively, with a **precedence rule** so a consumed or
removed item can never be "resurrected" by the packed-team fallback. Beyond
speed, this later helps our-mon damage (AV / Band / Specs / Life Orb).

**New state field:** `PokemonState.item_consumed: bool = False`.

**Item-truth precedence for OUR mons:**
1. **Live request item, if explicitly present** (`req.side.pokemon[].item` non-empty):
   `mon.item = req item`, `mon.item_known = True`. (The request reflects the
   *current* held item, so it already respects consumption — a consumed berry
   shows empty.)
2. **Protocol events override** (already partly in state.py, extend):
   - `|-item|` → `item` set, `item_known = True`.
   - `|-enditem|` (berry eaten, Focus Sash / Booster Energy used, Knock Off
     removal — all surface as `|-enditem|`) → `item = None`, `item_known = True`,
     **`item_consumed = True`**.
3. **Packed-team fallback** (from Stage C `our_spreads`): used **only when**
   `item_known` is False **and** `item_consumed` is False **and** no live-request/
   protocol event contradicts. Never resurrect a consumed/removed item.

**Where:** `merge_request` applies rule 1 for our mons (set item + `item_known`
from a non-empty `req` item; do NOT clobber on an empty request item — leave the
log's `|-enditem|` result standing). The protocol handler (`state.py::_apply`)
applies rule 2 (add `item_consumed = True` to the existing `enditem` branch). The
packed-team fallback (rule 3) fills remaining-unknown items from `our_spreads`
right before speed computation in the decision setup (it already receives
`our_spreads`); it must respect `item_known`/`item_consumed`.

**Opponent items stay hidden** — Fix A touches only `req.side` (our side). The
opponent's item remains unknown unless a protocol event reveals it.

**Verification note:** confirm the server populates `req.side.pokemon[].item`
(expected: yes). If ever empty, rule 3's packed-team fallback covers it.

### Fix A tests
- own request `item=choicescarf` → `mon.item_known = True`, `mon.item` set.
- Landorus-Therian effective speed with Scarf = `base × 1.5`.
- Sitrus consumed via `|-enditem|` → `item_consumed = True`; packed-team fallback
  does **not** restore Sitrus.
- unknown/missing request item → packed-team fallback may set it initially.
- opponent item stays hidden unless a protocol event reveals it (don't
  accidentally "know" opponent items).

---

## Fix B — Speed ties as expected value (correctness; bounded impact)

Replace the `tie = 1 if a.is_ours` fiat with a 50/50 expected value over both
orderings, for the first genuine our-vs-opp tie.

**Approach:** `sort_actions` / `resolve_turn` gain a `tie_break` param
(`ours_first` | `ours_last`). `evaluate_line` detects a genuine tie and, when
present, resolves the line under **both** orderings and averages:
`score = 0.5 * score_first + 0.5 * score_last`. **v1 handles only the first
relevant tie** (two passes); multiple tie groups are deferred (permutation
blow-up).

**A "genuine tie" requires ALL of these equal** — i.e. everything already in the
sort key, not merely the raw speed number:
- action order (switch-before-move) equal,
- dynamic priority equal (Grassy Glide, Fake Out, Protect, etc.),
- effective speed equal (with Tailwind/TR/para/Scarf already applied),
- one action ours vs one the opponent's,
- both actions still executable.

**Performance guardrail (must be in the spec):** the two resolver passes reuse
the same `DamageOracle` / prefetch cache. The second pass must create **no**
additional oracle requests — if it does, the prefetch was incomplete and the
test must fail.

### Fix B tests
- `sort_actions(tie_break=ours_first|ours_last)` orders the tied pair both ways.
- `evaluate_line` with a genuine speed tie → averages the two orderings (two
  `resolve_turn` calls) and `oracle` batch-call count is unchanged.
- non-tie line → bit-identical to current behavior (additivity / regression).

---

## Build order

1. Fix A: own-item truth in `merge_request` (+ `item_consumed`, enditem branch,
   packed-team fallback respecting precedence).
2. Tests for item precedence + Scarf speed.
3. Mini-gauntlet / replay check (guardrail, not target).
4. Fix B: `tie_break` param + EV averaging in `evaluate_line`.
5. Tests for tie / non-tie / additivity + oracle-call guardrail.
6. Guardrail gauntlet (no crash; ideally neutral/slightly better — NOT a tuning
   target).

## Expected impact & non-goals

- **Fix A is the larger lever** (the bot currently under-rates every fast mon it
  owns); **Fix B is bounded** (fires only on exact ties, mostly the mirror).
- **Out of scope (deferred):** opponent *likely*-speed instead of pessimistic max
  (that's the opponent-modeling slice); booster-energy speed inference; multiple
  simultaneous tie groups; the other own-team-knowledge slices (bench for
  switches, tera planning).
- The mirror gauntlet is a **guardrail**, not the optimization target.
