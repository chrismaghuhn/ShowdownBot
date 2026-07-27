# VERDICT: OPPONENT-MEGA COVERAGE GATE (post-guard-hardening) — PASS

Gate 2 of 3. Run **exactly once**, **unchanged**, on candidate `0390668`
(`candidate_identity 111cf0d16a4f8a59`) — the same identity that PASSed I8-D, with no commit
between the two gates. No per-cell floor, schedule, team or click-rate was touched.

**This is a coverage/safety verdict, not a strength claim. Champions Strength remains NO-GO.**

## Verdict

| field | value |
|---|---|
| `verdict` | **PASS** |
| `stop_reason` | `coverage_floor_met` |
| `battles_played` | 38 |
| `scored_decisions` | 379 (cap 2000) |
| `safety_violations` | 0 |
| `schedule_complete` | `false` (stopped on the floor, not on schedule exhaustion) |
| `seed_log_verified` | `true` |
| `candidate_identity` | `111cf0d16a4f8a59` |
| `schedule_hash` | `4775d9304836cf3e` |
| `panel_hash` | `6f4c98537a320bed` |

### Per-cell exposure against the floors

| cell | decisions | floor | distinct battles | floor | margin |
|---|---|---|---|---|---|
| `slot0` | 32 | 30 | 21 | 10 | +2 / +11 |
| `slot1` | 62 | 30 | 33 | 10 | +32 / +23 |
| `both_foe_slots` | **15** | **15** | **10** | **6** | **0 / +4** |
| `order_tie` | 18 | 15 | 18 | 6 | +3 / +12 |

`both_foe_slots` — the cell whose `0/0` zero-exposure drove the previous coverage FAIL — is now
populated at `15/10` and clears its floor. It landed **exactly** on the decision floor with zero
margin, and that is the stop rule's construction rather than luck: the run stops the instant every
cell clears, so the last cell to clear sits at or just above its floor by definition. The margin on
distinct battles is +4.

### Runtime environment (stamped since PR #107)

```
python    3.14.5
node      v24.16.0
platform  Windows-11-10.0.26200-SP0
deps      pydantic 2.13.4, websockets 16.0, lightgbm 4.6.0
```

## Safety and degradation — what is proven, and what this gate does not capture

**`safety_violations = 0`, with its scope stated exactly.** The counter is *hero-seat* and
*foe-Mega-bound*: it joins `stats.hero_invalid_decision_indices` against each decision row's
`foe_mega_active`. An invalid hero choice on a foe-Mega decision counts; one on a **non**-foe-Mega
decision is explicitly out of this gate's scope and ignored. An invalid index with no present row,
or the `-1` sentinel, aborts fail-closed rather than becoming a PASS. So this is zero foe-Mega hero
safety violations — not "zero illegal actions of any kind".

**Hero-side decision degradation: 0.** All 379 rows carry `outcome == "ok"` (domain
`{ok, crash, fallback, degraded_state}`, produced by `classify_live_outcome`). `backend_class` is
`oneshot` and `transport_retried` is 0 on every row; 797 calc spawn calls across the run; a probe
damage call returning a real number was asserted before battle 1.

**Not captured by this gate — correcting a premise rather than reporting a clean number.** The four
per-seat counters `hero_degraded_decisions` / `villain_degraded_decisions` and
`hero_invalid_choices` / `villain_invalid_choices` arrive through `run_local_gauntlet`'s
`on_battle_result` callback. **`run_coverage_gate` passes no such callback** — its
`run_local_gauntlet(...)` call is the same four-argument shape as `run_i8d_live_gate`'s. What it
consumes instead is `stats.hero_invalid_decision_indices`. Those four values therefore reach no
artifact of this run either; only the Gate B arm path passes the callback.

So: hero-side degradation is proven zero from the run's own bytes, foe-Mega hero safety violations
are zero, and the villain seat plus the per-seat degradation split are **unrecorded, not
verified-zero**. The coverage numbers above are reported with that limitation attached.

## Independent re-verification — from the frozen bytes

- `validate_live_profile_dataset` → `{rows: 379, active_valid_rows: 79, distinct_active_battle_ids: 38}`
- `coverage_cell_counts` recomputed from `profile.jsonl` — **identical** to `verdict.json.cell_counts`
- `seeds.jsonl`: exactly **38** records, contiguous `battle_index`, every seed equal to `derive_battle_seed(base, index)`

## Frozen evidence (`data/eval/champions-panel-v0/coverage-v0-post-guard-hardening/`)

| file | sha256 | bytes |
|---|---|---|
| `profile.jsonl` | `924dc5db54b1f6b3594caf3e048e298928dd3b96e770bad5b37e4ebf6913979e` | 411313 |
| `verdict.json` | `3541a4358052e61ce84cc5fc3c0481149dc01346c9c61aae5a847650ac5ec0fe` | 1454 |
| `seeds.jsonl` | `e30ac9f7a95934e6b3bcccdd8a79d06f8c0282890631d8902cd5a39c5cebf8c9` | 3980 |

Closed inventory: those three plus `sha256.txt`. Each stored blob's SHA-256 was verified equal to
the external run output before the freeze commit.

## Execution

| field | value |
|---|---|
| server | patched `pokemon-showdown` @ `f8ac140`, `--no-security` on port 8000, started fresh; seeding patch verified in the **built** `dist/` output |
| seed base | `champions-coverage-v0`, set on **both** server and client |
| gate command | `python -m showdown_bot.cli champions-coverage-gate --out-dir <run-root>/out --teams-root showdown_bot --i8d-verdict-path <i8d-run>/out/verdict.json`, from the repo root, `PYTHONPATH=showdown_bot/src`, `SHOWDOWN_CALC_BACKEND=oneshot` |
| upstream gate | the I8-D PASS verdict for this same identity (frozen on `evidence/i8d-live-0390668` @ `3ffbe93`) |
| policy | ran **once**; fail-closed; no retry; server stopped and port 8000 freed afterwards |

The T3 upstream-identity guard was checked **offline before any server started**: the I8-D verdict's
field set matches `_I8D_VERDICT_REQUIRED_FIELDS` exactly in both directions (26 required, 26
present, none missing, none extra), including the `environment` block added in PR #107.

## Descriptive comparison (NOT a causal claim)

| | previous coverage run | this run |
|---|---|---|
| candidate | `cbaa4b9` | `0390668` |
| verdict | **FAIL** | **PASS** |
| stop_reason | `schedule_exhausted` | `coverage_floor_met` |
| battles / decisions | 200 / 1956 | 38 / 379 |
| `both_foe_slots` | **0 / 0** (floor unmet) | **15 / 10** |
| safety violations | 0 | 0 |

The two runs used different code on different candidates, and the earlier one ran with the
unrepaired coverage team. No causal claim is made about the size of the difference.

## Non-claims and status

No ledger entry. No strength claim. Not merged to `main` — merging would move `main` and void the
shared candidate identity Gate B must run on. This PASS closes the coverage precondition **for
candidate `111cf0d16a4f8a59` only**. The independent Strength holdout is separately authorised and
has not run. **Champions Strength remains NO-GO.**

## SUPERSEDED as a precondition, 2026-07-27 (appended; nothing above is reworded)

**VALID as a record.** This run happened and this is what it returned: the coverage gate
**PASSed**, `stop_reason: coverage_floor_met`, zero safety violations. Nothing above is
withdrawn, and nothing here is a coverage or a quality finding: **this run failed nothing.**

**SUPERSEDED as a precondition**, for two independent reasons. Either one alone is sufficient;
they are recorded separately because fixing one would not revive this verdict.

1. **Identity.** The verdict binds to `candidate_identity 111cf0d16a4f8a59` at
   `git_sha 0390668`, and `main` has moved several commits since. `_check_identity_fields` can
   never match this verdict again.
2. **Schema.** Since PR #111 the coverage verdict schema requires the four per-seat counter
   fields (`hero_degraded_decisions`, `villain_degraded_decisions`, `hero_invalid_choices`,
   `villain_invalid_choices`). This verdict predates them and carries 21 of the 25 required
   fields, so it now fails the closed-schema check as **missing** — by design.

**Consequence.** This verdict can never again serve as an upstream PASS for a Gate B run and
**must not be cited as one**. It remains fully citable as evidence of what was measured.

**One paragraph above is overtaken by this landing.** "Non-claims and status" says this freeze
stays off `main` because merging would void the shared candidate identity Gate B must run on.
That identity is already void for reason 1, so there is nothing left to protect; the freeze is
landed here to preserve the artifacts, not to serve a gate. The paragraph is left standing as
the record of what was true when the run was frozen.

**Champions Strength remains NO-GO.**
