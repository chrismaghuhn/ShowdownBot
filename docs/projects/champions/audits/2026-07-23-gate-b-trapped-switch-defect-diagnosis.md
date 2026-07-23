# Gate B SAFETY-FAIL — trapped-switch defect: root-cause diagnosis

**Status:** DIAGNOSIS ONLY — **no fix is implemented or proposed as chosen**. The fix shape is a
design decision reserved to the project owner (§7).
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

Consequently the failing case is **fix shape (B)** in §7 — a design decision, **not** a one-line
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

## 5. Corroboration (inference, not proof)

- The server's `maybeTrapped → trapped` upgrade on the re-request (`rqid` 14, `update: true`) is
  consistent with slot 1 having been probed: the probe resolved the ambiguity and the server
  restated the slot as definitively trapped.
- On the accepted resubmission both slots played moves (slot 1 `Tailwind`, slot 0 `Dire Claw`),
  i.e. the switch intent disappeared once switching was no longer offered.

Neither observation is needed for the verdict; both are consistent with it.

## 6. Root cause statement

The heuristic enumerated a voluntary switch for an active slot that the server had marked
`maybeTrapped: true`, because **`maybeTrapped` is not modelled anywhere in the codebase** — it is
silently discarded by `ActiveSlot`'s pydantic parse. The bot correctly honors the definitive
`trapped` flag; it has no representation for the *possibly*-trapped state, so it treats
"possibly trapped" as "free to switch". Under Gate B's fail-closed safety gate, the resulting
server rejection counts as one illegal candidate action and fails the entire run regardless of
margin.

## 7. The two fix shapes, and which one applies

**(A) An explicit `trapped: true` slot was enumerated for switching → the legality filter must honor
the per-slot flag.** **DOES NOT APPLY.** §2(a) shows the filter already honors it, and §3 shows slot
0 was correctly excluded. There is no bug of this shape here.

**(B) A `maybeTrapped: true` slot was probed → design decision.** **THIS IS THE CASE.** It is
genuinely a design question, and the two options trade against each other:

| Option | Effect | Cost |
|---|---|---|
| **B1** — treat `maybeTrapped` as non-switchable during enumeration | No illegal action can ever be emitted from this cause; safe under a fail-closed gate | **Forfeits every legitimate switch** whenever the bot is flagged `maybeTrapped` but is not actually trapped. This is a real play-strength cost, not a theoretical one |
| **B2** — allow the probe, but add a client-side legal resubmit so a rejected probe never reaches `invalid_choices` | Preserves the switch option when it is in fact legal; the server's rejection becomes information rather than a gate failure | Adds a retry path on the live decision loop (latency implication against the 1000 ms p95 budget), and changes what `invalid_choices` means — that counter is the Gate B safety signal, so suppressing entries in it needs an explicit, documented contract or it weakens the gate |

**This choice is the owner's and is deliberately not made here.** One consideration that bears on it,
flagged as **inference**: in this Mega-enabled format `maybeTrapped` is plausibly **not rare** — the
opposing side had a Gengar on the field at the failing turn, and a Gengar that may still Mega-Evolve
is a canonical `maybeTrapped` trigger. If that generalizes, **B1's forfeit cost would recur across
many battles**, not just this one. I did not verify the trap mechanism (see §8), and the choice
should not be made on my inference alone.

## 8. What remains UNVERIFIED

1. **The trap source itself.** No trapping ability is visible in the log — only `Unnerve` (ours),
   `Intimidate` and `Stamina` (theirs). Why slot 0 was definitively `trapped` while slot 1 was only
   `maybeTrapped` is **not established**. The Mega-Gengar/Shadow-Tag hypothesis in §7 is untested
   inference. Per the work order this was noted, not chased.
2. **The exact submitted `/choose` string.** Still absent from the evidence (§4). The verdict does
   not depend on it, but no artifact in the frozen set records the bot's literal submission.
3. **The counterfactual.** What the heuristic would have played had slot 1's switches been withheld
   is unknown; no behavioural claim is made about whether the battle outcome would have differed.
4. **Frequency.** Whether other battles in the 180-matchup schedule encountered `maybeTrapped`
   without producing an illegal action is **not** measured here. Only one row in either arm has
   `invalid_choices` > 0, but that counts *rejections*, not `maybeTrapped` *occurrences*.
5. **B2's latency cost** against the 1000 ms p95 budget is unquantified.

## 9. Reproduction (read-only; no run, no server)

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

## 10. Recommended next step (NOT taken)

No further evidence is needed to identify the defect. The open item is the **owner's choice between
B1 and B2** (§7), after which a fix would be implemented under strict TDD in its own slice, with a
RED test that reconstructs the `rqid` 12 request offline and asserts no switch is enumerated (B1) or
that a rejection is legally resubmitted (B2). An offline/hermetic reconstruction is sufficient — a
**live battle replay is not required** and is not proposed.

This diagnosis makes **no strength claim**, does not change the run's `SAFETY-FAIL`, and Champions
Strength remains **NO-GO**.
