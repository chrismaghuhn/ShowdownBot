# Mega-reconcile mismatch after PR #109 — what still fires, what it costs, and the options

**Status:** AUDIT — findings and options. **This authorises nothing and decides nothing.** Whether
to change the coherence guard is the owner's call and belongs in a decision record, not here.
**No gate ran, no ledger entry, no evidence freeze, no strength claim. Champions Strength remains
NO-GO.**

Follows §4 of `2026-07-27-mega-reconcile-actor-mismatch-diagnosis.md`, which left two things open:
whether the defect still fires, and what the blind fallback costs. Nothing in the repository was
modified to produce this document.

## 1. The three premises, re-verified rather than accepted

| Premise | Verified how | Result |
|---|---|---|
| PR #109 fixed the actor comparison at family granularity | `engine/state.py:276-278` resolves through `get_species_form_meta(...).base_species_id`; commit `f4a5239`, merge `19d6e84` | **CONFIRMED** |
| All four per-seat counters zero across the 360 `5ab1083` battles | summed both frozen `rows.jsonl` on `main` | **CONFIRMED**, 360 rows, all four = 0 |
| PR #111 + #117 closed the gate path | `_abort_on_degradation` call sites: `i8d_runner` 2, `coverage_runner` 1, `strength_holdout_runner` 1 | **CONFIRMED** |

Also confirmed, because the "did not fire" claim depends on it: a mismatch **is** observable in
those counters. `MegaReconcileError` → `_state_for` returns `None` (`client/gauntlet.py:671-680`,
broad `except Exception`, log, return `None`) → `classify_live_outcome`/`is_degraded_decision` read
`state_degraded` **before** the stage sink and dominate it (`eval/decision_profile.py:267, 286`).
A mismatch cannot fire without moving a counter. The counters are the detector.

## 2. Does it still fire? (§4 question 1)

**Corpus searched — everything on `main` that post-dates the `19d6e84` fix merge:**

| Artifact | Granularity | Battles | Decisions | Result |
|---|---|---|---|---|
| `gate-b-5ab1083/arm-a-heuristic/rows.jsonl` | per battle | 180 | — | all four counters **0** |
| `gate-b-5ab1083/arm-b-max-damage/rows.jsonl` | per battle | 180 | — | all four counters **0** |
| `i8d-live-5ab1083/profile.jsonl` | per decision | 72 | 651 | `outcome`: **651 ok**, 0 degraded |
| `coverage-v0-5ab1083/profile.jsonl` | per decision | 38 | 379 | `outcome`: **379 ok**, 0 degraded |

`19d6e84` is an ancestor of `5ab1083` (checked), so all four post-date the fix. No live logs outside
these artifacts post-date it — the only runs since were these gates.

**But two thirds of that corpus is not evidence, and saying otherwise would overstate the result.**
The trigger is a single forme whose `battleOnly` differs from its `baseSpecies`. That species is
**absent from both gate panels** (`panel_champions_v0`, `panel_champions_coverage_v0` — grepped, zero
files) and **present across the sealed holdout set** (all six teams). So the 110 gate battles / 1030
decisions **could not have fired it** regardless of the fix, and prove nothing about it.

**The real evidence is the 360 holdout battles** — run on the very teams that triggered the defect
in the aborted 2026-07-27 attempt, where it fired within 3 battles. After #109: **0 occurrences in
360 battles.**

**Finding:** the defect did not fire once on the population that reliably triggered it before.
That is a strong negative result, not a proof of absence — the guard has no notion of `battleOnly`,
so a future forme with the same shape would trip it again. This is a defect that no longer fires,
not one that fires weekly.

## 3. What does the blind fallback cost? (§4 question 2)

**What is now precisely known about the fallback's shape** (all read from the code, not inferred):

- It is not a weaker policy. `agent_choose` (`client/gauntlet.py`) branches
  `if agent == "random" or state is None or book is None: return choose_for_request(req)`, and
  `choose_for_request` → `pick_random_pair` → `rng.choice(legal_pairs)` — **uniform random over
  legal actions**.
- It applies to **both** the `heuristic` and `max_damage` agents; neither has a state-free policy path.
- It hits **both seats**, because both build state from the same battle stream.
- It is **persistent**: `_state_for` rebuilds from the whole log every time, so once the `-mega`
  line is in the log every later build fails too.
- **Blast radius sizing**, from the frozen post-#109 profiles: **mean 9.0 decisions per battle**
  (median 9, max 16) for I8-D, **mean 10.0** (median 8, max 25) for coverage. A mismatch at
  decision *k* therefore costs roughly *9 − k* decisions in that battle, on both seats.

**What the cost is NOT, and why I did not produce a number.** §4 says the cost is unmeasured; it
still is. A sound cost measurement is a **winrate delta** between a battle played by the policy
throughout and one played by the policy until turn *k* and at random after — a live A/B, i.e. its
own slice.

A cheap offline proxy was available and is deliberately **not** reported as a cost: divergence
between the random choice and the policy choice in the same position. Two reasons it would mislead:

1. It is near-trivially high by construction (uniform random over legal pairs), so it measures the
   chooser's definition rather than the harm.
2. This project has already **live-verified** that offline agreement is not a valid proxy for
   outcome — it inverted against winrate by ±11.3pp in both directions. Substituting an offline
   number for an outcome number is precisely the error that finding forbids.

**Finding:** the cost remains unmeasured, and it is qualitatively severe — the remainder of an
affected battle is played at random by both seats. Those two statements are not in tension, and the
second must not be silently upgraded into the first.

## 4. Options — for the owner to weigh, not for this document to pick

The guard is deliberate. `engine/state.py:327-330` restores the snapshot and re-raises **precisely
so an incoherent state never reaches a consumer**. Every "handle it locally" option below converts a
loud refusal into a quietly partial state. That is the whole tradeoff, and it is a safety tradeoff,
not an engineering-taste one.

### Option A — do nothing

*What the state carries:* unchanged. *Wrong-value risk:* none new.

The case for it is real, not a formality: after #109 the defect has not fired in 360 battles on the
population that triggered it; the gate path is now fail-closed on the first degraded decision
(#111, #117), so a recurrence during a gate costs one battle and produces `abort.json` rather than a
contaminated verdict; and the cost of the fallback is unmeasured, so any change would be justified
by an unquantified benefit against a real safety loss.

The residual exposure is **live play outside gates**, which has no degradation abort at all
(`grep` for `_abort_on_degradation` in `client/gauntlet.py`: 0 hits). There, a mismatch silently
degrades the rest of the battle and only the profile row records it.

### Option B — mark the slot uncertain instead of nulling the build

Reconcile fails → the affected slot is flagged (e.g. `species_uncertain`) and the state is returned.

*What the state carries:* every other slot correct; the affected slot's species/forme unreliable.
*Which consumer could read a wrong value:* the damage oracle (types and base stats of that slot),
the speed oracle, and Mega-response modelling — all read species without asking whether it is known.
*How a caller would know:* only by checking the new flag, which every consumer would have to be
audited for. Until that audit is complete this is strictly worse than nulling, because it produces
confident wrong numbers instead of an obvious refusal.

### Option C — narrow the guard to `battleOnly`-aware comparison

Teach the reconcile the `battleOnly` relationship so the legitimate `Floette-Eternal → Floette-Mega`
pairing is not a mismatch at all, and keep the fail-closed raise for genuine mismatches.

*What the state carries:* fully correct state in the known-legitimate case; unchanged refusal otherwise.
*Wrong-value risk:* none, if the relation is read from the item/species tables rather than hardcoded.
*Caveat that makes this a decision, not a cleanup:* PR #109 already fixed the observed instance at
family granularity, so this option's benefit is only for **future** formes with the same shape. The
relation is already available without new data — verified here:
`engine/mega_form.py::mega_form_for("floetteeternal", "Floettite")` returns the `Floette-Mega` form
(and `"floette"` returns `None`), i.e. the existing item + species tables are already keyed on the
`battleOnly` forme. What made the `battleOnly` route unacceptable during #109 was not the lookup but
the risk of moving `config_hash` by touching generated data; an option built on `mega_form_for`
would have to prove it does not.

### Option D — keep the guard, add a degradation abort to live play

Leave the state build alone; give non-gate play the same fail-closed treatment the gates now have.

*What the state carries:* unchanged. *Wrong-value risk:* none new. *Tradeoff:* live play stops
instead of finishing degraded, which is right for measurement runs and wrong for anything that must
stay up. Needs a decision about which live callers are measurement and which are not.

### What I would not do without a decision

Widen, relax or narrow the coherence guard on the strength of the argument above. The 360-battle
negative result makes Option A defensible today; it does not make the guard unnecessary.

## 5. Non-claims

Nothing here is derived from the Gate B strength result. The holdout run is used **only** as
evidence that the defect did not fire — its counters, nothing else. No effect size, direction or
matchup from that run informs any option above.

**No gate run, no ledger entry, no evidence freeze, no strength claim. Champions Strength remains
NO-GO.**
