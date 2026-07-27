# Diagnosis — `mega_reconcile_actor_mismatch` on the Eternal-Flower forme

**Status:** DIAGNOSIS ONLY. No fix, no gate run, no ledger entry, no evidence freeze, no strength
claim. **Champions Strength stays NO-GO.**

**Trigger:** the Gate B attempt on candidate `111cf0d16a4f8a59` (`main` @ `0390668`) was aborted
after 3 battles — per-seat degradation counters non-zero on **both** seats (hero 5/4/9, villain
5/5/8), invalid choices 0/0. The ledger is untouched and the justified repeat is unspent.

**Headline, and it is not the expected answer:** the retroactive question *can* be settled from the
frozen `bc2d6df` evidence, and the answer is that the same defect **did** fire there — in 59 of
180 battles in Arm A and 57 of 180 in Arm B. See §5.

> **Addendum, 2026-07-27 (appended on landing; the body above is unchanged).** This is a
> point-in-time diagnosis, written *before* the fix and deliberately left as written — an audit is
> a dated record of what was known when, not a live status page. Read on its own the status line
> above describes an OPEN defect; it is not one any more.
>
> **The defect is fixed.** PR #109 @ `f4a5239` landed the family-granularity comparison: the guard
> now resolves the actor's family through `species_meta` instead of comparing a forme id against a
> field that cannot express formes, and `mega_form_for` is resolved from the actor's own forme
> rather than the event's family base. Neither required a data change — see the PR for the
> real-data A/B over this document's own corpus.
>
> **The citations still resolve.** `mega_reconcile_actor_mismatch` is at `engine/state.py:280` on
> current `main`; PR #109 changed what the guard compares, not where it fires. Everything §1–§5
> establishes about the cause, the scope and the retroactive question stands unchanged, and the
> `bc2d6df` SAFETY-FAIL record is untouched.
>
> **Still open from §4's second half:** a reconcile mismatch continues to null the entire state
> build, so any future mismatch still blinds the rest of that battle. That was scoped out of the
> fix deliberately and remains its own slice.

---

## 1. Where the mismatch fires — CONFIRMED

`engine/state.py`, inside the Mega reconcile application (the block that raises
`MegaReconcileError`), the coherence guard:

```python
# Coherence: the reconcile event's claimed actor must match the
# Pokemon actually occupying this slot (guards against a
# misrouted/mismatched -mega pairing reaching state application).
if mon.base_species_id != to_id(event.base_species):
    raise MegaReconcileError(f"mega_reconcile_actor_mismatch: slot={pid.raw} ...")
```

The two sides:

| side | value in the failing case | origin |
|---|---|---|
| `mon.base_species_id` | `'floetteeternal'` | our state; set from the species the slot actually holds (`to_id(self.species)` at construction, or `mega_form.base_species_id` via `engine/mega_projection.py`) |
| `to_id(event.base_species)` | `'floette'` | the second field of the server's `\|-mega\|` protocol line |

## 2. Which side is wrong — CONFIRMED: **neither datum. The assumption is.**

Read from the pinned sim (`~/.cache/showdownbot/pokemon-showdown` @ `f8ac140`), not inferred —
`sim/pokemon.ts`, in `formeChange`:

```ts
// The species the opponent sees
const apparentSpecies =
    this.illusion ? this.illusion.species.name : species.baseSpecies;
...
this.battle.add('-mega', this, apparentSpecies, species.requiredItem);
```

So the `-mega` event's second field is `species.baseSpecies` **of the Mega forme** — the *family*
base. It is not, and was never documented to be, the actor's pre-Mega forme.

The dex entry (`data/pokedex.ts`) makes the distinction explicit:

```
floetteeternal:  name "Floette-Eternal",  baseSpecies "Floette",  forme "Eternal"
floettemega:     name "Floette-Mega",     baseSpecies "Floette",  forme "Mega",
                 requiredItem "Floettite", battleOnly "Floette-Eternal"
```

`battleOnly` is the field that names the true pre-Mega forme — **`Floette-Eternal`** — while
`baseSpecies` names the family. For essentially every Mega those two coincide, so
`event.base_species` happens to identify the actor and the guard holds. Here they diverge, and the
guard compares our (correct) forme id against a (correct) family name.

Our state is right. The event is right. The guard's premise — *"the `-mega` event's second field
identifies the actor's pre-Mega forme"* — is what is false.

## 3. Species-specific or a class — CONFIRMED narrow **in this dex**, but the defect is an assumption

Scanned every Mega/Primal forme in the pinned `data/pokedex.ts`: **94 formes**, of which **exactly
one** has `battleOnly != baseSpecies`:

```
floettemega   forme=Mega   baseSpecies=Floette   battleOnly=Floette-Eternal
```

So in the format actually supported today this is a **one-forme** trigger. That is a fact about the
data, not about the code: the guard has no notion of `battleOnly` at all, so any future forme with
the same shape — a Mega whose pre-Mega forme is itself a non-base forme — would fail identically and
with no warning. Treating this as "the Floette bug" would fix the instance and leave the assumption.

**Not verified:** whether any format the bot may later support (other mods, other generations)
already contains such a forme. Only the pinned dex was scanned.

## 4. Impact on the chosen action — CONFIRMED, and worse than "unreasoned"

`MegaReconcileError` propagates out of the state build. In `client/gauntlet.py` the builder catches
it, logs `state build failed: …`, and returns `None`. The chooser then reaches:

```python
if agent == "random" or state is None or book is None:
    return choose_for_request(req)
```

So a degraded decision does not merely lose refinement — with `state is None` **every** agent falls
to `choose_for_request`, the blind chooser. The hero bypasses the heuristic entirely; the
`max_damage` baseline bypasses the damage calc entirely. Both seats degrade because both build
state from the same battle stream, which is why the counters move together.

**The failure is persistent for the remainder of the battle, not a single decision.** The state is
rebuilt from the *whole* log each time (`BattleState.from_log_text` over the accumulated room
lines), so once the `-mega` line is in the log, every subsequent build in that battle fails. That
matches the observed per-battle counts rising with battle length (5, 4, 9).

**Not verified:** whether the blind choice is measurably worse than the policy choice in these
positions. It is unreasoned by construction; how much that costs is unmeasured.

## 5. The retroactive question — CONFIRMED, and the expected answer was wrong

The expectation was that this could not be settled, because the reconcile error is a bot-side log
line while the frozen room dumps are the server stream. The first half is right — no frozen artifact
contains the bot-side warning, and the `bc2d6df` rows predate the per-seat degradation counters
entirely (their fields are `invalid_choices` summed and `crashes`, nothing per-seat).

But the *trigger* is a server-stream event, and the server stream **is** frozen. Decompressing all
360 hero logs:

| arm | battles carrying a Floette Mega event | events |
|---|---|---|
| Arm A | **59 / 180** | 59 |
| Arm B | **57 / 180** | 57 |
| total | | **116** |

with lines exactly of the failing shape:

```
|-mega|p2a: Floette|Floette|Floettite
|-mega|p2b: Floette|Floette|Floettite
```

And the guard existed then, byte-identical: `git show bc2d6df…:showdown_bot/src/showdown_bot/engine/state.py`
carries `if mon.base_species_id != to_id(event.base_species):` and the
`mega_reconcile_actor_mismatch` message at the same positions.

**CONFIRMED:** the triggering event fired in the `bc2d6df` run, and the code that rejects it was
present and unchanged.

**INFERENCE (strong, one gap):** therefore the mismatch fired and those battles degraded to the
blind chooser from the Mega onward. The gap is that the guard fires only if the slot actually held
`Floette-Eternal` at that moment — which the sim requires, since `Floette-Mega` is `battleOnly` on
`Floette-Eternal`, so a Mega could not have occurred otherwise. No frozen artifact records the
resulting bot-side state, so this is deduction from the event plus the code, not a recorded outcome.

**What this means for the `bc2d6df` descriptive numbers** (`n_total` 180, `n_discordant` 100,
`delta` +0.044444, head-to-head 89–81): roughly **a third of the battles in each arm** contained
decisions in which *neither* arm was playing its policy. Those numbers were already descriptive-only
and carried no strength claim; this makes them weaker still, and it is now on record why.

**What artifact would have settled it outright:** the per-seat degradation counters on the result
rows — which exist today and are exactly what stopped the current attempt after three battles. A
captured client-side log would have done it too. The counters were added after `bc2d6df`; that is
the whole gap.

## Candidate fix shapes — presented, deliberately NOT chosen

1. **Compare against `battleOnly` when present.** Resolve the Mega forme from `event.stone_display`
   / the details species and compare `mon.base_species_id` against that forme's `battleOnly` when it
   has one, falling back to `baseSpecies` otherwise. Fixes the class, and needs `battleOnly` to be
   available in our dex projection — **unverified whether it is**.
2. **Accept either the family base or the actor's own forme.** Widen the guard to pass when
   `mon.base_species_id` is the family base *or* a forme of it. Cheapest, but it weakens exactly the
   misrouting protection the guard exists for — it would also accept a genuinely wrong actor that
   happens to share a family.
3. **Normalise one forme.** Map `floetteeternal` → `floette` for this comparison only. Smallest
   diff, fixes the instance, leaves the assumption and needs re-doing for the next such forme.
4. **Do not fail the whole state build on a reconcile mismatch.** Orthogonal to 1–3: treat the
   mismatch as a scoped Mega-application failure rather than one that nulls the entire state and
   blinds every subsequent decision in the battle. This addresses the *blast radius* (§4)
   independently of which of 1–3 addresses the *cause*.

Shapes 1 and 4 are addressing different halves and are not alternatives to each other.

## Explicitly unverified

- Whether our dex projection exposes `battleOnly` at all (decides whether shape 1 is even available).
- Whether any other supported or future format contains a second forme of this shape.
- The magnitude of the play-quality cost of a blind decision versus a policy decision.
- Whether the I8-D and coverage runs on this same candidate also degraded: their runners pass no
  `on_battle_result` callback, so their artifacts carry no per-seat counters. The trigger forme is
  carried by three of the six holdout teams and by no dev-panel, coverage, or hero team, so those
  two gates had no opportunity to hit it — but that is an argument from team composition, not a
  measurement.

Any fix produces a new `git_sha`, hence a new candidate identity, hence fresh I8-D and coverage runs
before Gate B can be attempted again.
