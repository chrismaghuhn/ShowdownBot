# VERDICT: I8-D LIVE LATENCY GATE — FAIL (active foe-Mega p95 1110.213 ms > 1000 ms budget)

The single separately-authorized I8-D live latency gate ran **exactly once** on the corrected
harness, on the fixed Windows host, against the pinned patched server. It created 75 real battles,
scored 679 live decisions, **met the D-1 exposure floor** (60 active-valid foe-Mega decisions from
45 distinct battles), stopped on the exposure floor, and **atomically published** a verdict. The
verdict is **`FAIL`**: the active foe-Mega decision p95 is **1110.213 ms**, over the **1000 ms**
budget.

**This is a load-bearing latency verdict, not a Strength claim.** The 1000 ms budget is *not*
moved after the fact. Champions Strength remains **NO-GO**; live decision latency is a load-bearing
blocker whose next step is a dedicated latency-reduction slice followed by the **same** gate,
unchanged.

Frozen evidence (this directory / `data/eval/champions-panel-v0/i8d-live/`):

| file | sha256 | bytes |
|---|---|---|
| `profile.jsonl` | `d3f76e2b80a0607f3fa2d748155ae7af38eee62cd948a8f37f2614605dcf726c` | 689263 |
| `verdict.json` | `af8ce71413ec316257669e601569b73261ef2df55741f8d00f5459c7a5d4fcc1` | 700 |
| `seeds.jsonl` | `4d4ad59c2f78a938ce531670f45b4b7fd2371daae11fbb7b66a283b2edb76c6b` | 8540 |

Stored byte-exact under `.gitattributes: data/eval/champions-panel-v0/** -text`; the git-stored
blob is byte-identical to the working file (verified: `git cat-file blob | sha256sum` equals the
table above). All three are LF-only (0 CRLF). The bytes above are a copy of the run output at
`C:/Users/chris/i8d-live-run-9fc0f36/{out/profile.jsonl, out/verdict.json, seeds.jsonl}`, whose
source sha256 equals the frozen sha256 for each file.

## Verdict

| field | value |
|---|---|
| **verdict** | **`FAIL`** |
| gate value | active foe-Mega decision **p95 = 1110.213 ms** (`1110.2130000072066`) |
| budget | **1000 ms** (`p95_is_gate_value: true`) |
| margin | +110.213 ms (≈ +11.0 %) over budget |
| `stop_reason` | `exposure_floor_met` — a clean D-1 stop, **not** a cap and **not** a timeout |
| `exposure_floor_met` | `true` |
| active-valid decisions | **60** (threshold `min_active_decisions` = 60) |
| distinct active battles | **45** (threshold `min_distinct_battles` = 20) |
| battles played | **75** |
| scored decisions | **679** (`scored_overshoot` = 0; cap `max_scored_decisions` = 2000 not reached) |
| `seed_log_verified` | `true` (server Channel-A seed log verified before the verdict) |

The verdict population is defined once, in production, as `is_active_valid_live_row`
(`decision_profile.py`): `source == "live"` ∧ `timer_scope == "agent_choose"` ∧ `outcome == "ok"`
∧ `foe_mega_active is True`. p95 uses the project nearest-rank convention (`gauntlet._latency_p95`,
no interpolation) — the same function the per-battle gate uses, reused rather than re-derived.

## Provenance

| field | value |
|---|---|
| git_sha | `9fc0f362d0078ecd74e01b206f7490e3de77f7dd` (merge of PR #26, the team-path wiring fix) |
| dirty | `false` (run on a fresh detached worktree at `9fc0f36`, tracked tree clean) |
| format_id | `gen9championsvgc2026regma` (Champions Reg M-A) |
| config_hash | `594295543f13a55d` (the original stratum) |
| calc_backend | `oneshot` |
| `SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S` | **unset** — standard/default per-battle timeout (BEHAVIOR_AFFECTING; its absence is part of `config_hash 594295543f13a55d`) |
| schema_version | `decision-profile-v1` (uniform across all 679 rows) |

All of `git_sha`, `config_hash`, `calc_backend`, `schedule_hash`, `format_id`, `source`, and
`schema_version` are single-valued across every one of the 679 rows — one run, no pooling of strata.

## Content-lock hash verification

| artifact | hash | check |
|---|---|---|
| seed namespace (`seed_base`) | `champions-panel-v0-i8d-latency` | single value across all 75 seed rows |
| `schedule_hash` | `a1192d9dde4c65df` | matches the schedule; every profile `battle_id` is `make_battle_id(schedule_hash, index, seed)`-derivable |
| `panel_hash` (content-derived) | `aac1ea30446fde88` | frozen Champions panel/team content lock |
| `hero_team_hash` | `1d3a4cf5a4042532` | one hero team |
| `opp_team_hashes` | `0054b6894af7215a`, `64ecc8fb2e6da7f1`, `ea99dd840d0adce2` | three opponent teams |

Seed proof (Channel A): the server read `SHOWDOWN_BATTLE_SEED_BASE=champions-panel-v0-i8d-latency`
and logged one `{battle_index, seed, seed_base}` per created battle; the 75 rows are contiguous
`battle_index` 0..74 and every logged `seed` reproduces `derive_battle_seed(seed_base, battle_index)`
exactly (re-checked independently below).

## Execution

| field | value |
|---|---|
| host | `DESKTOP-1V4BPFQ`, Windows 11 |
| server | patched `pokemon-showdown` pinned at `f8ac140` + `pokemon-showdown-seeded-battle.patch`, `--no-security` on port 8000 |
| gate command | `python -m showdown_bot.cli i8d-live-gate --out-dir …/out --teams-root showdown_bot` (PYTHONPATH `showdown_bot/src`, `SHOWDOWN_CALC_BACKEND=oneshot`, no timeout env) |
| run output | `C:/Users/chris/i8d-live-run-9fc0f36/` (seedlog + `out/`), outside the repo |
| policy | ran **once**; fail-closed; **no automatic retry**; server + worker stopped and port 8000 freed after the process ended |

## Independent re-verification — from the frozen bytes, all gates PASS

Re-checked reading only the committed copies, reusing the production predicate, validator, and p95:

- `validate_live_profile_dataset('…/i8d-live/profile.jsonl')` → `{rows: 679, active_valid_rows: 60, distinct_active_battle_ids: 45}`.
- **679** rows, all `(battle_id, decision_index)` pairs unique.
- Verdict population recomputed independently via `is_active_valid_live_row`: **exactly 60** active-valid decisions from **exactly 45** distinct battles.
- p95 recomputed via `gauntlet._latency_p95` over the 60 active `measured_ms`: **`1110.2130000072066`** — bit-identical to `verdict.json.p95_ms`, and `> 1000` ⇒ `FAIL`.
- `seeds.jsonl`: exactly **75** rows, single `seed_base`, contiguous `battle_index` 0..74, every seed equals `derive_battle_seed(base, index)`; every profile `battle_id` is a logged, `schedule_hash`-derivable battle.
- Hygiene: every row carries the identical canonical 41-key schema; all three files are LF-only; **no local filesystem path or username leaked** into any row (the run-time absolute team paths did not enter the dataset); provenance fields uniform (single run).

## Demarcation from the two earlier ABORTED attempts (not verdicts)

Two prior authorized live attempts **aborted before any battle was created** — an I8-D team-path
wiring bug meant the gauntlet loaded empty teams, the server rejected the challenge, no battle was
created, and the gate only timed out. A technical abort **is not a verdict**: each produced no
verdict, no evidence, and no latency statement (see spec §5.4c).

| attempt | run dir | stratum | seedlog | `out/` | outcome |
|---|---|---|---|---|---|
| 1 | `i8d-live-run-8616901` | oneshot, standard timeout (`config_hash 594295543f13a55d`) | **no file** (0 battles) | not published | `ABORTED before battle creation` |
| 2 | `i8d-live-run-4c32cfc-t900` | oneshot, 900 s timeout (`config_hash 06b2b96e76486563`, **RETRACTED / void**) | **no file** (0 battles) | not published | `ABORTED before battle creation` |
| **3 (this run)** | `i8d-live-run-9fc0f36` | oneshot, standard timeout (`config_hash 594295543f13a55d`) | **75 rows** | published + atomic | **`FAIL` (real verdict)** |

Neither timeout was ever the cause. The **900 s decision is retracted** — it rested on a wrong
"slow battle" diagnosis, was never empirically exercised, and its `config_hash 06b2b96e76486563`
is void; strata are never pooled. The team-path fix landed in PR #26 (merge `9fc0f36`); this run is
the first on the corrected harness, and this run's stratum is the **original** one
(`594295543f13a55d`) — the same stratum attempt 1 nominally targeted, not the retracted 900 s one.

## Explicit non-claims and next step

This record establishes only that, at `git_sha 9fc0f36`, under `oneshot` on the fixed Windows host,
the active foe-Mega decision p95 (1110.213 ms) does **not** meet the 1000 ms live budget. It does
**not** establish, and must not be read as:

- any **Strength** result — Champions Strength remains **NO-GO**;
- any **cross-platform** latency figure, any **persistent-backend** figure, or a claim about a
  different `config_hash` (this is `oneshot` / `594295543f13a55d` only);
- an **optimization** verdict — no optimization code was written for this run.

**Next step:** a dedicated **latency-reduction slice**, then a repeat of this **same** gate,
**unchanged** — `oneshot`, the same **1000 ms** budget value, D-1 (≥ 60 active from ≥ 20 battles)
and D-2 (caps 200 / 2000) unchanged. The budget is not reinterpreted or moved.
