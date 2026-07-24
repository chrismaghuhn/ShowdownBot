# B1 live verification — and two gate-integrity findings

**Status:** audit record. Docs-only: no fix, no run authorised by this note, no gate, no ledger
entry, no evidence freeze, no strength claim.

**Evidence class — read before quoting any number below.** Every measurement here comes from
**diagnostic soak runs whose artifacts are EXTERNAL and UNFROZEN** (local `~/soak_*` directories,
never committed, no manifest, no content hashes, no ledger entry). They are **not gate-grade
evidence** and must never be cited as frozen evidence or as any part of a Gate B verdict.

**Reference convention.** No sealed holdout identifier or content hash appears here; holdout teams,
where they must be named at all, are `H1`…`H6` (manifest `selection_index`). Nothing in this note
required a holdout.

---

## 1. Retraction — stated first

An earlier conclusion, **"B1 does not close the trapped-switch class", was WRONG and is retracted.**

Cause: the adversarial soak that produced it ran with `showdown_bot` imported from the **main repo
checkout**, which at the time sat on `bc2d6df` — *before* B1 — because that path is on `sys.path`
via a `.pth`. The run measured code without the fix and found, unsurprisingly, that the fix was not
in effect. The audit note asserting the wrong conclusion was **never committed**, so nothing false
entered the repository.

Two things about how the error survived a review are worth recording, because they are the reusable
part:

- The wrong conclusion was **independently "confirmed" by the reviewer** — by inspecting the
  worktree's **files on disk**, which did contain B1. That is the wrong check. Files on disk say
  what *would* be imported by a process configured a particular way; they say nothing about what a
  given run *did* import.
- The contradicting signal was present and was not weighted: an offline probe in the same session,
  which explicitly inserted the worktree onto `sys.path`, showed `_voluntary_switches` returning
  **0** switch actions for both slots — i.e. B1 working. Two results that could not both be true
  were held side by side without the conflict being resolved.

## 2. CONFIRMED — B1 is live-effective

Clean A/B: same schedule (`schedule_hash a4321d47ea1da5f5`), same seed base, same throwaway
Gengar + Gengarite opponent, **calc verified answering in both runs** (zero `calc subprocess failed`
lines in either log).

| run | `invalid_choices` | `maybeTrapped` | Mega Gengarite | error lines |
|---|---|---|---|---|
| pre-B1 (`bc2d6df` loaded) | **5 / 30** | 46 occurrences in 29 logs | 30 / 30 battles | 5 |
| B1 loaded | **0 / 30** | 49 occurrences in 29 logs | 30 / 30 battles | 0 |

The single error class in the pre-B1 run was
`[Unavailable choice] Can't switch: The active Pokémon is trapped` — the Gate B SAFETY-FAIL class.

### The interpretation gate (this is the load-bearing part)

**A bare `invalid_choices = 0` means nothing unless the legality surface was actually produced.**

Counter-example from the same session, and the reason this rule is written down: a 30-battle run in
which the calc backend was dead (missing `node_modules` under `tools/calc`, so every decision fell
through to a fallback) reported

```
invalid_choices = 0    crashes = 0    30 clean rows
maybeTrapped = 0       Mega Gengarite = 0
```

That result is **worthless, not reassuring** — the bot never played the position the fix addresses.
Any future `invalid_choices` figure must be reported *after* the surface counts, never before.

## 3. CONFIRMED — a holdout-free reproducer exists

The class reproduces at roughly **17 % of battles (5/30)** on pre-fix code with **no holdout
involvement at all**, using a throwaway opponent whose only job is to create the legality surface.

Parameters, so it is re-runnable:

- **Opponent:** a scratch, non-sealed, `validate-team`-clean `gen9championsvgc2026regma` team whose
  Mega holder is **Gengar @ Gengarite** — Shadow Tag applies once it Mega-Evolves, and the sim
  reports the *last active* hero slot as `maybeTrapped` rather than `trapped`
  (`sim/pokemon.ts:1098,1135-1138` at the pinned commit).
- **Hero:** `teams/fixed_champions_v0.txt`; **format** `gen9championsvgc2026regma`.
- **Schedule:** built with the existing `panel_schedule.generate_dev_schedule`, `seeds_per_cell=15`,
  both opponent policies → 30 battles, `schedule_hash a4321d47ea1da5f5`.
- Fresh server per run, Channel A (`SHOWDOWN_BATTLE_SEED_BASE`), no battle-level retry.

This is now the **standing regression check** for this class: cheap, needs no holdout, spends no
ledger budget, and — unlike the original occurrence, whose only instance sits inside frozen holdout
evidence — it can be re-run at will.

## 4. CONFIRMED — calc degradation is not fail-closed (gate-verdict integrity)

When the damage calculator is unavailable, `battle/decision.py` runs a swallow-everything chain:

```
heuristic_error (:1576) -> max_damage_error (:1596)
                        -> deterministic_default_pair (:1600) -> server_default (:1605)
```

Every step emits `logger.warning` and returns a **legal** move. **No exception propagates.**

Nothing on the Gate B path notices:

- `grep -niE "fallback|degrad|calc_ok|selection_stage"` over
  `eval/strength_holdout_runner.py` → **no hits** (the one textual match is an unrelated comment
  about atomic publish having "no copy fallback").
- `calc_backend` on the arm manifest is **derived from configuration**, not from an answer. It
  records the configured intent, never that anything was computed.
- `crashes` does not catch it: that counter increments on exceptions escaping `agent_choose`, and
  under calc failure none escape.

**Existence proof, not speculation:** the calc-dead run in §2 produced **30 clean rows**
(`invalid_choices = 0`, `crashes = 0`, normal `end_reason`). Had that been a Gate B arm, it would
have published a valid-looking verdict stamped `calc_backend: oneshot` for a bot that never
calculated a single damage roll.

A suitable signal *does* exist — `eval/decision_profile.py:232-233,254-256` maps `selection_stage`
to `ok` / `fallback` and fails closed on an unknown stage — but it lives in the **I8-D live decision
profile**, not on the Gate B arm row. **OPEN, not checked:** whether an I8-D run on the same
candidate would have caught a calc-degraded bot before Gate B ever started.

**No fix is proposed here.**

## 5. CONFIRMED — `invalid_choices` conflates both seats

`client/gauntlet.py:1469`:

```python
stats.invalid_choices = hero.invalid + villain.invalid
```

The per-seat signal exists one line below — `stats.hero_invalid_decision_indices`
(`client/gauntlet.py:1472`), documented as the HERO seat's own indices and never the villain's — but
it is deliberately **in-memory only**, kept off the closed T2 result row. And
`eval/strength_holdout_verdict.py:555` reads exactly the summed field
(`row.get("invalid_choices")`).

Consequence: **an illegal action by the opponent seat fails the candidate** and consumes a held-out
ledger slot, with nothing on the row able to show it.

The original SAFETY-FAIL's attribution to the candidate still holds — but only because the **room
log** resolves it (the dump is written per client, `client.name` in the filename, and each client
counts its own errors), **not** because the row can. That distinction was not previously recorded.

**No fix is proposed here.**

## 6. Process outcome — the rule that came out of this

> **A measuring run produces no result until it has PRINTED `showdown_bot.__file__` and ASSERTED
> both (a) that the change under test is present in the *loaded* module, and (b) that the calc
> backend ANSWERS — a probe damage call returning a number, which must FAIL the preflight rather
> than warn. Files on disk are never evidence of what executed.**

The preflight that satisfies this checks the loaded module by `realpath` + `commonpath` (not
`startswith`, which is defeated by separator and case differences), reads the change out of
`inspect.getsource`, and probes calc via a real `CalcClient().damage(...)` call, treating an absent
or zero result as failure. Existence of `node_modules` is explicitly **not** the check — a
30-battle run already passed with `node_modules` absent and every decision silently degraded.

**And the coupling, which cost a whole run:** pinning `PYTHONPATH` to a worktree fixed the import
but simultaneously moved execution *off* the main checkout's working native dependencies, silently
degrading the run. **The import pin and the native deps must be pinned together** — fixing one
without the other converts a silent-wrong-code failure into a different silent failure.

## 7. Explicit non-claims

- **No strength claim.** Champions Strength remains **NO-GO**.
- Nothing here authorises a Gate B rerun. The ledger decision (justified repeat vs. a new
  independent holdout) and the requirement of the full three-gate sequence on **one fresh candidate
  identity with no intervening commits** are unchanged.
- **Findings §4 and §5 are recorded, not remediated.** Neither has a fix, a test, or a proposal in
  this note.
- Every number in §2 and §3 is diagnostic, from external unfrozen artifacts, and changes no verdict
  — including the standing `SAFETY-FAIL`.
