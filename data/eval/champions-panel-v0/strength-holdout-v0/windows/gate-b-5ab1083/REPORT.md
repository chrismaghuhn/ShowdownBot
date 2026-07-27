# Gate B — independent strength holdout, run `gate-b-5ab1083` — VERDICT: NO-GO

**HELD-OUT RUN — these numbers must never inform tuning.**

This is the justified repeat pre-registered in
`docs/projects/champions/decisions/2026-07-27-gate-b-justified-repeat.md`. It consumed the one
authorised repeat on `config_hash 594295543f13a55d` (held-out ledger entry 7). **Champions
Strength remains NO-GO.**

| field | value |
|---|---|
| `verdict` | **NO-GO** |
| `candidate_identity` | `908883ee69a0b713` |
| `git_sha` | `5ab10830513c7fbb5995ea92751509d830f7418e` |
| `date_stratum_id` | `2026-07-27-windows-gate-b-5ab1083` |
| `stratum` | `windows` |
| `n_total` | 180 paired matchups (180 battles per arm, 360 total) |
| `panel_hash` / `schedule_hash` | `122764211b6db3ba` / `37df91c10c24801d` |

## The two NO-GO reasons, verbatim from `combine/verdict.json`

```
p too high (p=0.2181 >= 0.05)
cell flip winning->losing: heuristic x 7f026166ceb58d38, max_damage x cb76e5fbf51a992d
```

Nothing in this document is derived from the cell flip, and no direction is inferred from any
number above. The verdict is the verdict; what it authorises is a separate decision.

## The safety result — a correctness finding, stated plainly

`safety_pass` is **true**. Across all 360 battles both arms recorded **zero** illegal actions and
zero degraded decisions: `hero_invalid_choices`, `villain_invalid_choices`,
`hero_degraded_decisions`, `villain_degraded_decisions`, `invalid_choices` and `crashes` all sum to
0, and all six fields are present (non-null) in all 360 rows.

The consumed attempt (`bc2d6df`) ended in a fail-closed SAFETY-FAIL on exactly one illegal action
in the heuristic arm. That defect does not reproduce here. This is a statement about legality, not
about strength.

## Hero logs: NOT CAPTURED, NOT RECOVERABLE

This freeze contains **0** hero logs where the `bc2d6df` freeze contains 360.

**Cause.** The raw room dump is env-gated on `SHOWDOWN_ROOM_RAW_DUMP`
(`showdown_bot/src/showdown_bot/client/gauntlet.py:1151`). The variable was not set for either arm,
so `dump_room_raw` was never called and `room_raw_path` is null in all 360 rows.

**Not recoverable.** Hero logs exist only as a by-product of playing the battles. The one-attempt
budget for this `config_hash` is consumed, and §7 of the decision record forbids a third attempt on
this configuration.

**A trap for later readers.** The rows *do* carry 360 valid `normalized_room_log_sha256` values.
Those are computed from the in-memory frames (`gauntlet.py:1295`) independently of the dump — they
are hashes of logs that were never written to disk. **No such files exist anywhere and none can be
produced.** Do not go looking for them.

The difference from the precedent is in *captured evidence*, not in what was played: both runs
played 180 + 180 battles under the same schedule, panel and seeds.

## Byte-provenance of the frozen files

`rows_path_transform` is a **NO-OP** for this run. The `bc2d6df` freeze rewrote `room_raw_path`
from an absolute machine path to a relative frozen log path; here `room_raw_path` is null
throughout, so there was nothing to rewrite. The frozen `rows.jsonl` are **byte-identical to what
the arms produced** — verified with `cmp` against the source worktrees before hashing, and re-hashed
from this directory rather than carried over.

`combine/arm_a/` and `combine/arm_b/`, the combine's own copies of the arm inputs, are **not**
frozen here. All six were verified byte-identical to the arm directories before anything was
copied, which is what makes them redundant rather than missing; the fact is recorded as
`combine_arm_copies_identical` in `inventory.json`. Same convention as the precedent.

Every declared file carries `bytes` and `sha256` in `inventory.json`. `inventory.json` itself is
not listed there — it cannot contain its own hash — so the closed-set check is
`{on-disk} == {declared} + {inventory.json}`. `showdown_bot/tests/test_gate_b_freeze_inventory.py`
enforces both the hashes and the closed set on every CI run.

## Upstream gate artifacts

The two preconditions are frozen **beside** this run-dir, under their own paths, matching the
existing `i8d-live-*` / `coverage-v0-*` freezes:

- `data/eval/champions-panel-v0/i8d-live-5ab1083/` — I8-D live latency gate, PASS
- `data/eval/champions-panel-v0/coverage-v0-5ab1083/` — opponent-Mega coverage gate, PASS

Both carry `profile.jsonl`, `verdict.json` and `sha256.txt` — **two** hashed files, where the older
freezes hash three. `seeds.jsonl` is deliberately omitted: neither gate verdict records a seed-log
hash (they carry only `seed_log_verified`, a boolean, and `seed_base`), so a copied seed log would
be a file we believe is the seed log rather than evidence bound to the verdict. The same gap exists
in the older freezes, where `seeds.jsonl` is hashed into `sha256.txt` but bound to no verdict field.

The arm manifests are different: their `seed_log_sha256` (`29f8d198…`, identical in both arms
because both arms play the same seed-fixed schedule) does bind `seeds.jsonl`, so the arm seed logs
are frozen here as evidence.

## Teams

Interpretation caveats about the holdout set are recorded in §6 of the decision record. Teams are
referred to by manifest `selection_index` (H1…H6). The near-duplicate flags in
`combine/verdict.json` concern **H2, H4 and H5**, each at `overlap_fraction` 0.5 against the two
engineered coverage teams. They are an interpretation caveat, not a leakage finding, and they are
not among the verdict's `reasons`.

**No strength claim is made in this document in any direction.**
