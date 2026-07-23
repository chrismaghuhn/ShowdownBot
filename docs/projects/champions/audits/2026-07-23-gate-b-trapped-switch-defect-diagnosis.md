# Gate B SAFETY-FAIL — trapped-switch defect: root-cause diagnosis

**Status:** DIAGNOSIS ONLY — **no fix is implemented here**. The mechanism is now sim-verified (§5)
and the owner **decided fix shape B1** (§8, 2026-07-23). **B1 has since LANDED** in its own TDD
slice: PR #60 @ `7dafde8` (production + tests), with the schema guard's pin anchor in PR #61 @
`a9475e5`. This document is unchanged as a diagnosis; only the status of the follow-on slice moved.
**Type:** docs-only audit. No production code, config, sealed file, or data is changed.
**Subject:** the single illegal action (`invalid_choices` = 1) that made the Gate B independent
strength-holdout run a **SAFETY-FAIL** (candidate `bc2d6df`, identity `32f79b8e52444aa3`; evidence
frozen + merged, PR #57 @ `cccfb30`).

**Reference convention (leakage discipline).** Holdout teams are named only by the positional alias
`H1`…`H6` (= manifest `selection_index`). The sealed `gbh_*` IDs and the holdout content hashes are
Gate B leakage-scan identifiers and this audit is **not** on the scan allowlist
(`holdout_leakage_scan.ALLOWED_EXACT_PATHS` / `ALLOWED_DIRECTORY_PREFIXES`), so naming one here
would make the next `combine_strength_holdout_arms` fail closed with `LeakageDriftError`. Do not
reintroduce them. In particular the offending row's `opp_team_hash` field is such a hash and is
deliberately **not** quoted anywhere below.

## 1. The question, and the verdict

**Question.** In battle `9ccc312c51d95bfe`, which active slot did the heuristic actually try to
switch — the slot the server had marked `"trapped": true`, or the slot marked `"maybeTrapped": true`?

**Verdict: CONFIRMED — the bot attempted to switch SLOT 1, the `maybeTrapped` slot.**
A switch on slot 0 (`trapped: true`) was **provably not in the enumerated action space** and
therefore could not have been submitted. This is settled by static analysis of the production
action-enumeration path plus the frozen request bytes; it is **not** an inference from the
`maybeTrapped → trapped` upgrade.

Consequently the failing case is **fix shape (B)** in §8 — a design decision, **not** a one-line
legality bug.

## 2. Code evidence (verified by reading the production path)

The heuristic's decision path is
`battle/decision.py:471` → `battle/actions.py::enumerate_my_actions` → `_slot_actions` →
`_voluntary_switches`.

**(a) The bot DOES honor the per-slot `trapped` flag.** `battle/actions.py:50-66`:

```python
def _voluntary_switches(req: BattleRequest, active_index: int) -> list[SlotAction]:
    if (
        req.active
        and active_index < len(req.active)
        and req.active[active_index] is not None
        and req.active[active_index].trapped
    ):
        return []
```

A slot with `trapped: true` contributes **no** switch actions. Fix shape (A) is therefore already
implemented and was **not** the failure.

**(b) The bot has NO notion of `maybeTrapped` at all.** A repo-wide search for `maybeTrapped` /
`maybe_trapped` across `showdown_bot/` returns **0 occurrences**. `models/request.py::ActiveSlot`
declares `moves`, `can_terastallize` (alias `canTerastallize`), `can_mega_evo` (alias `canMegaEvo`)
and `trapped` — and no `maybeTrapped` field. Its `model_config` does not set `extra="forbid"`, so
pydantic's default silently **ignores** the unknown key. The flag is dropped at parse time and never
reaches any decision code. A slot carrying only `maybeTrapped: true` parses to `trapped = None`,
which is falsy, so the guard in (a) does not fire and **switch actions are enumerated for it**.

**(c) There is no second switch source on a voluntary turn.** Only two sites construct a switch
action in the battle path: `battle/actions.py:65` (inside `_voluntary_switches`, guarded above) and
`battle/legal_actions.py:34` (inside `_bench_switch_targets`). `_bench_switch_targets` has exactly
one caller, `legal_actions.py:81`, which sits inside the `if forced:` branch — reachable only when
`req.force_switch[active_index]` is true.

**(d) The client fail-safe cannot produce this error.** The only fallback choice strings are
`/choose default|<rqid>` (`client/gauntlet.py:138,141,694`; `client/runner.py:152`). `/choose
default` never contains a switch and cannot elicit `Can't switch`. The rejected submission therefore
contained an explicit switch, which on this turn can only have come from `_voluntary_switches`.

## 3. Frozen-log evidence (verified from the merged bytes)

From the frozen hero log
`data/eval/champions-panel-v0/strength-holdout-v0/windows/gate-b-safety-fail-bc2d6df/hero-logs/arm-a/HeuristicBot8652__battle-gen9championsvgc2026regma-2998.log.gz`:

| line | `rqid` | `forceSwitch` | slot 0 flags | slot 1 flags |
|---|---|---|---|---|
| 78 | 10 | absent | `{}` | `{}` |
| **93** | **12** | **absent** | **`{'trapped': True}`** | **`{'maybeTrapped': True}`** |
| 95 | 14 (`update: true`) | absent | `{'trapped': True}` | `{'trapped': True}` |

Line 94, between them: `|error|[Unavailable choice] Can't switch: The active Pokémon is trapped`.

`forceSwitch` is **absent** on `rqid` 12 — this was a **voluntary** turn, so the `forced` branch of
§2(c) is unreachable and `_voluntary_switches` was the only possible switch source. Slot 0 was
`trapped: true` there, so it contributed nothing. **Slot 1 is the only remaining candidate.**

## 4. Why the log alone could never have answered this

The frozen room log is the **server → client** stream only. The bot's own `/choose` string is not
present in it, in this battle or any other. The work order's premise was correct: the chosen slot is
not readable from the log. What settles the question is not the log but the **action-enumeration
code**, which proves a slot-0 switch was never a candidate. No additional artifact is required.

## 5. The sim mechanism — why one slot was masked (VERIFIED against the pinned sim)

The slot-0 / slot-1 asymmetry initially looked unexplained. It is now **fully explained**, verified
by reading the pinned simulator (`~/.cache/showdownbot/pokemon-showdown` at **`f8ac140`**, the
commit pinned in `config/eval/provenance.yaml`).

**(a) Ability traps are recorded as a distinct, masked state.** `sim/pokemon.ts:1613-1618`:

```ts
tryTrap(isHidden = false) {
    if (!this.runStatusImmunity('trapped')) return false;
    if (this.trapped && isHidden) return true;
    this.trapped = isHidden ? 'hidden' : true;
    return true;
}
```

The field is typed `trapped: boolean | "hidden"` (`sim/pokemon.ts:131`). All three trapping
abilities call `tryTrap(true)`, i.e. the **hidden** form — `data/abilities.ts`: **Arena Trap**
(line 200), **Magnet Pull** (2509), **Shadow Tag** (4149).

**(b) The request serializer deliberately restricts information for the LAST active slot.**
`sim/pokemon.ts:1098` — `// Information should be restricted for the last active Pokémon`. The two
branches then differ in strictness:

- non-last active (`sim/pokemon.ts:1124`): `if (this.trapped) data.trapped = true;` — a **loose**
  check; `'hidden'` is truthy, so the slot is reported as **`trapped: true`**.
- last active (`sim/pokemon.ts:1135-1138`): `if (this.trapped === true) { data.trapped = true; }
  else if (this.maybeTrapped) { data.maybeTrapped = true; }` — a **strict** check; `'hidden'` is not
  `=== true`, so it falls through and the slot is reported as **`maybeTrapped: true`**.

**(c) The masking exists to prevent ability-leaking.** `sim/battle.ts:1728-1736`:
*"canceling switches would leak information / if a foe might have a trapping ability"* — and the
`FoeMaybeTrapPokemon` loop explicitly **skips the foe's actual ability**
(`if (abilityName === source.ability) { continue; }`), because that case was already handled.

**Conclusion.** Both hero actives were equally and genuinely trapped by the **revealed** Mega
Gengar's Shadow Tag. Slot 1 was merely the *last active* and therefore received the masked form.

> **For ability traps, `maybeTrapped` does not mean "uncertain" — it means "actually trapped,
> withheld".** The bot was not making a reasonable gamble on an ambiguous flag; it was switching a
> Pokémon the simulator already knew was trapped, and merely declined to say so plainly.

**Corroboration (inference, consistent with the above):** the `maybeTrapped → trapped` upgrade on
the re-request (`rqid` 14, `update: true`) is what one expects once the probe forces the issue; and
on the accepted resubmission both slots played moves (slot 1 `Tailwind`, slot 0 `Dire Claw`).

## 6. Root cause statement

The heuristic enumerated a voluntary switch for an active slot that the server had marked
`maybeTrapped: true`, because **`maybeTrapped` is not modelled anywhere in the codebase** — it is
silently discarded by `ActiveSlot`'s pydantic parse. The bot correctly honors the definitive
`trapped` flag; it has no representation for the *possibly*-trapped state, so it treats
"possibly trapped" as "free to switch". Under Gate B's fail-closed safety gate, the resulting
server rejection counts as one illegal candidate action and fails the entire run regardless of
margin.

## 7. Measured exposure across the frozen run (verified)

Scanned all 360 frozen hero logs on `main` (command in §10):

| arm | battles with a `maybeTrapped` slot | `maybeTrapped` slot-occurrences | battles with an explicit `trapped` slot | `Can't switch` rejections |
|---|---|---|---|---|
| A (heuristic) | **26 / 180 (14.4 %)** | **76** | 26 / 180 | **1** |
| B (max_damage) | 15 / 180 (8.3 %) | 34 | 15 / 180 | 0 |

Two things follow:

- **The exposure is real but not dominant** — the flag appeared in ~1 in 7 of the candidate's
  battles, yet produced exactly **one** rejection in 180. So the heuristic rarely *wanted* to
  switch in these spots.
- **The battle counts for `maybeTrapped` and explicit `trapped` are identical within each arm**
  (26 = 26, 15 = 15). That is exactly what §5's mechanism predicts: when an ability trap is live in
  doubles, one active slot is reported truthfully and the other (the last active) is masked. This is
  an independent confirmation of the mechanism, derived from the frozen bytes rather than the source.

**Honest bound.** These logs record what the server *offered*, not what the bot *wanted*. They
cannot distinguish "did not want to switch" from "switched successfully because it was not actually
trapped". The forfeit cost of B1 is therefore **bounded above** by these counts, **not measured**.

## 8. Options considered, and the owner's decision

**(A) An explicit `trapped: true` slot was enumerated for switching → the legality filter must honor
the per-slot flag.** **DID NOT APPLY.** §2(a) shows the filter already honors it and §3 shows slot 0
was correctly excluded. There was no bug of this shape.

**(B) A `maybeTrapped: true` slot was probed.** This was the case, and it was a design decision.

### DECIDED: B1 — treat `maybeTrapped` as non-switchable. Owner, 2026-07-23.

**B1 (CHOSEN).** Given §5's mechanism, for the ability-trap class this is **correct rather than
over-conservative**: a `maybeTrapped` slot under an ability trap *is* trapped, so declining to
enumerate its switches removes an action that was never legal. The §7 figures are an **upper bound**
on what it forfeits, and the mechanism substantially reduces even that bound, since much of the
flagged exposure is masked-real-trap rather than genuine uncertainty. It costs **strength, not
safety** — and strength is already NO-GO while the fail-closed safety gate is the binding constraint.

**B2 (REJECTED)** — allow the probe, add a client-side legal resubmit. Two independent reasons:
1. Its "harmless probe" premise **does not hold** for ability traps. The rejection is not a cheap
   query returning information; the Pokémon really is trapped, so the probe is simply an illegal
   action that the server refuses.
2. It would **redefine `invalid_choices`**, which is the Gate B safety signal itself. Changing a
   safety metric in response to that metric failing is **not acceptable here**. If the metric is
   genuinely too broad, that belongs in a deliberate, pre-registered spec change — not in the
   reaction to the failure it just reported.

**B3 (DEFERRED, largely moot)** — model trapping from public information. The *revealed* case is
already handled correctly by B1, and the genuinely-uncertain case is information the simulator
**deliberately withholds** (§5c), so public-information modelling cannot resolve it.

**This decision is recorded here, not implemented here** — this document changes no production code.
**B1 has since LANDED** in its own TDD slice: **PR #60 @ `7dafde8`** (`ActiveSlot.maybe_trapped`
plus the `_voluntary_switches` guard, forced path untouched) and **PR #61 @ `a9475e5`** (the sim-pin
anchor for the schema-coverage guard). See the ROADMAP reconciliation for the landed detail,
including the `exclude_if` serialization fix that keeps non-`maybeTrapped` boards byte-identical.

## 9. What remains UNVERIFIED

1. **The split within the measured exposure.** What fraction of the 76 (arm A) / 34 (arm B)
   `maybeTrapped` slot-occurrences were **masked real traps** versus **genuine unrevealed-ability
   uncertainty** is **not** established. This is the quantity that would turn B1's bounded forfeit
   into a measured one.
2. **The exact submitted `/choose` string.** Still absent from the evidence (§4). The verdict does
   not depend on it, but no artifact in the frozen set records the bot's literal submission.
3. **The counterfactual.** What the heuristic would have played had slot 1's switches been withheld
   is unknown; no behavioural claim is made about whether the battle outcome would have differed.
4. **B2's latency cost** against the 1000 ms p95 budget is unquantified (moot under the B1 decision,
   recorded for completeness).

## 10. Reproduction (read-only; no run, no server)

Sim mechanism (§5), against the pinned checkout — verify it is at `f8ac140` first:

```bash
SIM=~/.cache/showdownbot/pokemon-showdown
git -C "$SIM" rev-parse --short HEAD                      # -> f8ac140
sed -n '131p;1098p;1124p;1135,1138p;1613,1618p' "$SIM/sim/pokemon.ts"
sed -n '1728,1737p' "$SIM/sim/battle.ts"
grep -n "tryTrap(true)" "$SIM/data/abilities.ts"          # -> 200, 2509, 4149
```

Measured exposure (§7) over the 360 frozen hero logs, from the repo root on `main`:

```bash
python -c "
import gzip,json,glob
b='data/eval/champions-panel-v0/strength-holdout-v0/windows/gate-b-safety-fail-bc2d6df/hero-logs'
for arm in ('arm-a','arm-b'):
    bm=bt=om=ot=rej=0
    for f in sorted(glob.glob(f'{b}/{arm}/*.log.gz')):
        hm=ht=False
        for line in gzip.open(f,'rt',encoding='utf-8',errors='replace'):
            if line.startswith('|error|') and \"Can't switch\" in line: rej+=1
            if not line.startswith('|request|'): continue
            try: r=json.loads(line[9:] or '{}')
            except Exception: continue
            for a in (r.get('active') or []):
                if not a: continue
                if a.get('maybeTrapped'): om+=1; hm=True
                if a.get('trapped'): ot+=1; ht=True
        bm+=hm; bt+=ht
    print(arm,'maybeTrapped',bm,'battles',om,'occ |trapped',bt,'battles',ot,'occ | rejections',rej)
"
```

Static facts, from the repo root on `main`:

```bash
grep -rn "trapped" showdown_bot/src/showdown_bot | grep -vi test
grep -rni "maybetrapped\|maybe_trapped" showdown_bot | wc -l   # -> 0
sed -n '50,66p' showdown_bot/src/showdown_bot/battle/actions.py
grep -rn "_bench_switch_targets" showdown_bot/src/showdown_bot | grep -v test
```

Frozen-log facts (reads the merged evidence, starts nothing):

```bash
python -c "
import gzip,json
p='data/eval/champions-panel-v0/strength-holdout-v0/windows/gate-b-safety-fail-bc2d6df/hero-logs/arm-a/HeuristicBot8652__battle-gen9championsvgc2026regma-2998.log.gz'
for l in gzip.open(p,'rt',encoding='utf-8',errors='replace'):
    if l.startswith('|request|'):
        r=json.loads(l[9:] or '{}')
        if r.get('rqid') in (12,14):
            print(r['rqid'], r.get('forceSwitch'), [{k:v for k,v in (a or {}).items() if k in ('trapped','maybeTrapped')} for a in r.get('active') or []])
    elif l.startswith('|error|'): print(l.strip())
"
```

## 11. Next step — LANDED (not taken *in this document*)

The defect was identified and the fix shape decided (**B1**, §8). The implementation slice has since
been executed under its own authorization and strict TDD, exactly as scoped here: a RED test that
reconstructs the frozen `rqid` 12 request offline and asserts **no switch action is enumerated for a
`maybeTrapped` slot**, then the minimal change to `_voluntary_switches` plus the `ActiveSlot` model
learning the field at all (§2b). An offline/hermetic reconstruction was sufficient — **no live
battle replay was run**, as anticipated.

Landed in **PR #60 @ `7dafde8`** (production + tests) and **PR #61 @ `a9475e5`** (sim-pin anchor for
the schema-coverage guard). Two things worth carrying forward that this diagnosis did not predict:
the new field needed `exclude_if` because `model_dump(..., exclude_none=False)` is **hashed** by
`eval/decision_profile.py` (it moved a pinned fixture hash until fixed at source), and the root
cause — a silently dropped request key — is now guarded by a schema-coverage test anchored to
`showdown_commit`. The remaining §9 unverified items are unchanged by the fix.

This diagnosis makes **no strength claim**, does not change the run's `SAFETY-FAIL`, and Champions
Strength remains **NO-GO**.
