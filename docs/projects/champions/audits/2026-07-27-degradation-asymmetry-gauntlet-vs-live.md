# Degradation on a nulled state build: the gauntlet and the live path do different things

**Status:** AUDIT — findings and options. **This authorises nothing and decides nothing.** No
chooser, fallback or state-build handler was touched. **No gate run, no ledger entry, no evidence
freeze, no strength claim. Champions Strength remains NO-GO.**

Scopes what §4 of `2026-07-27-mega-reconcile-blast-radius-and-options.md` listed as Option D. The
asymmetry is real — but **not in the direction it was framed**, and the correction changes which
option is worth considering.

## 1. Is the asymmetry real? (question a)

Yes. Both call sites, verbatim.

**`showdown_bot/src/showdown_bot/client/gauntlet.py:152-153`** (the evaluation harness):

```python
    if agent == "random" or state is None or book is None:
        return choose_for_request(req)
```

**`showdown_bot/src/showdown_bot/client/runner.py:106-124`** (ladder / challenge / smoke):

```python
    if book is not None and not req.team_preview:
        try:
            state = BattleState.from_log_text("\n".join(_room_raw.get(room, [])))
            merge_request(req, state)
        except Exception as exc:  # noqa: BLE001 - never block a turn on state build
            logger.warning("state build failed in %s: %s", room, exc)
            state = None
    ...
    if book is not None:
        ...
        choose = choose_with_fallback(
            req, state=state, book=book, our_side=req.side.id, priors=priors, report=report,
            ...
        )
    else:
        choose = choose_for_request(req)
```

### The correction that matters

The framing under which this was scoped was that the live path "degrades gracefully" — keeps
playing a policy — while the harness degrades to uniform random. **That is not what happens.**

`choose_with_fallback` gates *both* of its policy layers on the same condition:

- heuristic: `if state is not None and book is not None:` (`battle/decision.py:1555`)
- max_damage: `if state is not None and book is not None:` (`battle/decision.py:1583`)

With `state=None` both are skipped and control falls through to
`encode_choose(pick_default_pair(req), ...)` — the **deterministic first legal pair**.

Executed rather than read (fixture `t4b_force_single_2bench.json`, loaded module asserted):

| Path | Call | Result | Repeats → distinct |
|---|---|---|---|
| live (`runner.py`) | `choose_with_fallback(state=None, book=<obj>)` | `/choose pass, switch Tornadus`, `selection_stage=deterministic_default_pair`, `fallback_reason=None` | 8 → **1** (deterministic) |
| harness (`gauntlet.py`) | `choose_for_request(req)` | — | 60 → **2** (random) |

**So both paths are blind. Neither plays a policy on a nulled state build.** The real difference is
**random-blind vs deterministic-blind** — not graceful vs harsh. Any argument that starts "the live
path keeps playing well" is false.

## 2. Is it deliberate? (question b)

**No recorded rationale exists, and intent is not recoverable from the repository.**

- Both call sites originate in the **same commit**, `8ad61f6` ("feat: Phase 2 one-ply heuristic VGC
  doubles bot"), and the divergence is present in that commit — `gauntlet.py` already had the
  `state is None` short-circuit, `runner.py` already routed through `choose_with_fallback`. This is
  **original divergence, not later drift**.
- `runner.py`'s only comment on the handler (`# noqa: BLE001 - never block a turn on state build`)
  explains the broad `except`, not the chooser choice.
- No spec, plan or audit under `docs/projects/` addresses the runner's degradation behaviour or
  compares the two clients (searched; the only hits for `choose_for_request` are the mega-reconcile
  diagnosis quoting the gauntlet site).

A deliberate choice with a stated reason and an undocumented one are different findings. This is the
undocumented kind — which is why it should not be "harmonised" on the strength of tidiness.

## 3. What does the live path record? (question c)

**Nothing structured. One log line.**

Signal presence in `client/runner.py`:

| Signal | `runner.py` | `gauntlet.py` |
|---|---|---|
| `hero_degraded_decisions` / `villain_degraded_decisions` | **0** | 6 |
| `invalid_choices` | **0** | present |
| `stage_sink` / `SelectionStageSink` | **0** | 13 |
| `classify_live_outcome` / `decision_profile` | **0** | 2 |
| `on_battle_result` | **0** | present |

The entire evidence a ladder battle leaves when its state build fails is
`logger.warning("state build failed in %s: %s", room, exc)` (`runner.py:112`) — and only if someone
kept the logs. There is no row, no counter, no profile row, and no verdict artifact. A degraded
ladder battle is, for practical purposes, **unobservable after the fact**.

That is the substantive gap. It is a *recording* gap, not a *choosing* gap.

## 4. Which behaviour belongs in a measurement harness? (question d)

The crux was posed as: random makes contamination loud and unmistakable; graceful degradation makes
a contaminated run look plausible. **Checked, and it does not hold** — for a reason worth stating
precisely.

In the gauntlet, degradation is detected from the **state**, not from the play:

```python
state_degraded=(state is None),      # gauntlet.py:864 and :974
```

`classify_live_outcome` / `is_degraded_decision` read `state_degraded` *before* the stage sink and
dominate it. Verified by execution: with `state_degraded=True`, **both** the live path's
`deterministic_default_pair` stage and a written-nothing stage classify as `outcome=degraded_state`,
`degraded=True`.

**So the harness's detectability does not depend on which blind chooser runs.** Swapping the
gauntlet to deterministic-blind would not make one contaminated decision less visible: the counter
fires on `state is None` either way, and since PR #111/#117 that counter aborts I8-D, coverage and
both Gate B arms fail-closed on the first occurrence.

What the two choosers actually trade:

- **Random-blind** — the *play* is self-evidently junk, so a human watching a battle notices.
  Costs reproducibility: two runs of the same seed-fixed schedule can diverge after a degraded
  decision, which is exactly what a seed-fixed paired design is built to prevent.
- **Deterministic-blind** — reproducible, and a seed-fixed rerun still matches. Costs nothing in
  detectability (above), but the play is degenerate in a *predictable* way, which is more
  exploitable if it ever happened against a real opponent.

**Argued honestly, the measurement-harness answer is not obvious, and the loudness argument is
weaker than it looked.** Reproducibility is a real property of the Gate B design; "a human would
notice" is not, because no human watches 360 battles — that is precisely what this session
established when the Arm A monitor produced no reading at all. The counter is the detector; the
chooser is not.

## 5. Options — for the owner, not for this document

### Option A — do nothing

The asymmetry is undocumented but harmless where it is measured: gate runs abort fail-closed on the
first degraded decision regardless of which blind chooser would have run. Nothing about the two
choosers changes what a gate certifies.

*Cost:* the divergence stays undocumented and the next reader re-derives it, as happened here.

### Option B — record degradation on the live path (the real gap)

Give `runner.py` the signal the gauntlet already has — at minimum a `SelectionStageSink` and a
counter — so a degraded ladder battle leaves something behind.

*What it changes:* observability only; no chooser, no fallback, no state handler.
*Tradeoff:* `runner.py` currently has no artifact-writing machinery at all, so this is a new write
path in a client whose defining property is that it never blocks a turn. It must not become a
reason to fail a live battle.
*This is the option the findings actually support* — the gap is recording, not choosing.

### Option C — harmonise the two choosers

Make both paths use the same blind chooser.

*Tradeoff:* requires first deciding *which* — and §4 above shows the answer is not obvious, that
detectability is unaffected either way, and that the seed-fixed paired design has a live stake in
reproducibility. Harmonising for symmetry's sake, without that decision, would be changing a
fail-closed-adjacent path on aesthetics.

### Option D — document the divergence and close the item

Record in the code (both sites) that the divergence is intentional-as-of-now and why, and close it.

*Tradeoff:* costs nothing, fixes nothing, and prevents the next re-derivation.

### What I would not do

Change any chooser on the strength of this audit. The finding that motivated the scoping — "the
live path degrades gracefully" — turned out to be false; the finding that survives is that the live
path *records nothing*, which is a different slice with a different shape.

## 6. Non-claims

Nothing here uses the Gate B holdout run beyond the already-recorded fact that the mega-reconcile
defect did not fire in 360 battles. No effect size, direction or matchup informs any option.

**No gate run, no ledger entry, no evidence freeze, no strength claim. Champions Strength remains
NO-GO.**
