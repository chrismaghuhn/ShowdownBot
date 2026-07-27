# No mechanical guardrail on the held-out budget — the current behaviour is the design

**Status:** DECIDED (owner), 2026-07-27. **The ruling authorises NOT building something**, which is
exactly why it is written down: without a record, "`check_access` returns for any justification"
reads like a hole and gets reopened as one.

**Scope:** this note changes no behaviour. No code was modified; `heldout_ledger.py`,
`check_access` and both callers are untouched. **No gate run, no ledger entry, no evidence freeze,
no strength claim. Champions Strength remains NO-GO.**

## 1. The question

After Gate B's justified repeat was spent (ledger entry 7), a finding was recorded that
`check_access` does not mechanically prevent a third run: it returns for **any** non-null
justification, before examining a single entry. Should a bar be added — a hard refusal that a
justification cannot bypass?

## 2. What the module already says, quoted rather than paraphrased

`showdown_bot/src/showdown_bot/eval/heldout_ledger.py:21-24`:

> A justification (recorded on the new entry, e.g. a deliberate
> reproduction re-run) or a panel version bump (which changes ``panel_hash`` and what a
> "held-out run" even means) resets the budget -- by design, so the exception is visible
> and auditable rather than silently allowed.

`showdown_bot/src/showdown_bot/eval/heldout_ledger.py:3-5`:

> A solo dev with root cannot be technically stopped from touching held-out teams
> (honesty clause, review §6/§9). This module makes every held-out access visible and
> auditable instead: two entry kinds are appended to a committed JSONL ledger --

So the behaviour is **documented, intentional, and load-bearing**. It is not an oversight that
`check_access` returns on a justification — that is the stated mechanism, and the docstring names
the reason: the module's goal is **visibility and auditability**, explicitly *instead of* technical
prevention, because technical prevention is impossible against the person who owns the repository.

## 3. Why a bar would invert the design rather than harden it

The honesty clause is not a disclaimer; it is the premise the whole module is built on. A hard
refusal would:

1. **Stop nobody.** Anyone who can add a bar can remove it, and anyone who can run the combine can
   edit `config/eval/heldout_ledger.jsonl` directly. The threat model the docstring states is a solo
   dev with root — a bar does not exist within that model.
2. **Move the exception out of the ledger.** Today a repeat must be declared as a justification that
   is recorded verbatim on the appended entry, in a committed, append-only file, checked by a
   git-history test. With a bar, the cheapest path to a repeat becomes a hand-edit or a flag flip —
   which leaves *less* evidence, not more. The exception stops being auditable, which is the one
   property the module exists to provide.
3. **Trade a visible process commitment for an invisible one.** §7 of
   `2026-07-27-gate-b-justified-repeat.md` is a pre-registered, committed, dated commitment that a
   later reader can hold against the outcome. That is a stronger artifact than a boolean, precisely
   because it cannot be satisfied by accident.

The claim is not that a bar is worthless in every project. It is that in *this* threat model it
converts an auditable exception into an unauditable one.

## 4. Scope facts, so the size of the non-change is on record

- `check_access` has **two** call sites, both in `strength_holdout_runner.py`: line **1707** (an
  early fail-fast, before the pairing and verdict work) and line **1889** (inside `_ledger_lock`,
  the authoritative check that gates the reservation). A bar would have had to be correct in both,
  and consistent between them.
- The same reset applies to a **panel version bump**, not only to a justification — a bump changes
  `panel_hash` and, per the docstring, "what a 'held-out run' even means". So a bar would have been
  larger than "one condition": it would have had to take a position on panel bumps too, and that
  position would touch what a held-out run *is*.

## 5. The ruling

**No mechanical guardrail is built.** The current behaviour is the design and is recorded as such.

- **§7 of the Gate B justified-repeat decision record remains the binding limit** on a third attempt
  for `config_hash 594295543f13a55d`.
- **The ledger remains the visible record.** Any future repeat must still be declared as a
  justification recorded verbatim on an appended entry.
- **No code changes.** `check_access` and both callers stay as they are.

### What this ruling explicitly does NOT say

It does **not** say the budget is mechanically enforced. It is not. The distinction the roadmap
already carries stands unchanged and unsoftened:

> **process-forbidden by §7 for this configuration; NOT mechanically enforced.**

§7 is a process commitment, not a technical guarantee, and this decision does not upgrade it into
one. A reader who wants to know whether the code would stop a third run should read this section and
conclude: **no, and deliberately so.**

## 6. How to reopen this

Legitimately, if the threat model changes — more than one person with write access, or an automated
runner that could repeat a gate without a human in the loop. Both would break the premise in §3.1,
and the honesty clause would no longer be the right foundation. Absent that, "`check_access` returns
for any justification" is an answer, not a defect.
