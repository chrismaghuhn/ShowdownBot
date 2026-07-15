# Champions I7a Own-Mega Safety Smoke — Verdict

## Verdict

**I7a OWN-MEGA SAFETY PASS · NO I7b · NO STRENGTH CLAIM**

This is a 2-battle safety smoke proving own-Mega evaluate → click → protocol → rebuild →
next-decision integration on the I7a-C branch. It is not a strength claim, not an I7b
(opponent Mega) claim, and not a latency-budget change.

## Provenance

| field | value |
|---|---|
| run_id | e1180db12f8ceba6 |
| config_id | heuristic |
| config_hash | e137fce925f25bd8 |
| format_id | gen9championsvgc2026regma |
| schedule_hash | b67a851881d76918 |
| panel_hash | aac1ea30446fde88 |
| seed_base | champions-panel-v0-smoke-i7a-mega |
| git_sha | 5690de75a4f7bc627b8d4be4fddb2074c6b586fc |
| showdown_commit | f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5 |
| dirty | false |

`config_hash` differs from a prior local diagnostic run (`b8a0aa12b9f6c4de`) because that
earlier run's captures were (unintentionally) produced against the main-repo checkout's
package resolution rather than this worktree — see "Operational notes" below. This run's
`config_hash` is the correct, worktree-derived value.

## Safety gates (`eval-report --mode gate`)

Result: **SAFETY-PASS**. All 18 gates PASS, including:

| gate | measured |
|---|---|
| rows_match_schedule | 2 == 2 |
| invalid_choices | 0 |
| crashes | 0 |
| end_reason_normal | all normal |
| latency_p95 | worst=588ms (budget 1000ms) |
| seed_log_alignment | 2 contiguous, derived |
| dirty | none |
| one_config_hash / one_schedule_hash / one_git_sha | consistent |
| manifest_match | ok |

## Trace validation

- 20/20 decision-trace rows are `decision-trace-v3` and pass `validate_trace_row`.
- `selection_stage` is `heuristic` on every regular-turn row (`None` only on the
  team-preview rows, which carry no selection stage) — no random/legacy degradation.
- `fallback_reason` is `null` on every row.
- Every Scovillain candidate (across both battles) has `mega_evolve: false` on its own
  slot — Spicy Spray fail-closed holds.

## Own-Mega evidence (`eval.mega_evidence.derive_mega_evidence`)

Both battles exposed a full own-Mega path — not INCONCLUSIVE:

| battle_id | mega_decision_index | turn | mega_slot | post_mega_decision_index | post_mega_species |
|---|---|---|---|---|---|
| `3e6a178b0900195e` | 1 | 1 | 1 | 2 | `Aerodactyl-Mega` |
| `7eca1f7492671b1a` | 1 | 1 | 1 | 2 | `Aerodactyl-Mega` |

For both battles, the pre-click state (from the **capture-boundary fix**, `5690de7`)
correctly shows the hero's own held item: `species=Aerodactyl`, `item=aerodactylite`,
`item_known=true`. The chosen `/choose` string contains `mega` in both battles
(`move 2 2, move 2 2 mega|4` and `move 3 2, move 3 mega|4`).

## Protocol-pair binding (`eval.mega_evidence.bind_protocol_mega_pair`)

For each battle, the normalized room log was re-derived from the local (never-committed)
`room_raw` dump via `read_room_log_frames` + `normalize_battle_log(frames,
name_subs=GAUNTLET_NAME_SUBS)` — the same recipe `eval.room_dump.normalized_room_log_sha256`
uses — and its hash was confirmed to equal the result row's own
`normalized_room_log_sha256` before any binding was attempted.

`bind_protocol_mega_pair` found exactly one unambiguous, correctly-ordered
`detailschange` → `-mega` pair for `p1b: Aerodactyl` in each battle (battle 2 also
contains an opponent `p2b: Meganium` Mega pair — a `max_damage` policy on its own team —
which the actor-scoped match correctly ignores). Compact line/log hashes only; no raw
protocol lines or full room logs were committed. See `mega-evidence.json` for the full
per-battle binding.

## Config-manifest sidecar

`results.jsonl.config-manifest.json` was written by `write_config_manifest_sidecar`
(not hand-authored) and re-verified with `verify_config_manifest_sidecar` **after**
`room_raw_path` was set to `null` in the committed result rows — both passed.

## Operational notes (process, not evidence)

- Two earlier attempts in this run's session were discarded (not committed, local-only):
  one where the Showdown server was started without `SHOWDOWN_EVAL_SEED_LOG`/
  `SHOWDOWN_BATTLE_SEED_BASE` set server-side (seed-log alignment failed before any gate
  ran); one where `python -m showdown_bot.cli` resolved `showdown_bot` from the main
  repo checkout's editable install rather than this worktree's `src/` (no `PYTHONPATH`
  override), so the capture-boundary fix was never actually exercised even though the
  battles themselves ran safely. Both were operational/environment mistakes, not
  evidence-shopping — corrected before any gate was evaluated, then this run was recorded
  once, cleanly, with `PYTHONPATH` pinned to this worktree.
- A prior diagnostic run at commit `1da2cb7` (pre-capture-fix) is preserved outside the
  repository at
  `%USERPROFILE%\.cache\showdownbot\measurements\champions-panel-v0-smoke-i7a-mega\diagnostic-pre-capture-fix-1da2cb7\`
  and is not part of this frozen evidence.

## Explicit non-claims

- No opponent-Mega modeling (I7b) claim.
- No I7b completion claim.
- No Champions Strength claim — 1/2 win-rate on n=1 cells carries no statistical meaning.
- No general Champions-readiness claim.
- No latency-budget change or improvement claim beyond this run's own measured p95.

## Reproduction

```powershell
cd $env:USERPROFILE\.cache\showdownbot\pokemon-showdown
$env:SHOWDOWN_BATTLE_SEED_BASE = "champions-panel-v0-smoke-i7a-mega"
$env:SHOWDOWN_EVAL_SEED_LOG = "<repo>\data\eval\champions-panel-v0\smoke-i7a-mega\seeds.jsonl"
node pokemon-showdown start --no-security
```

```powershell
cd showdown_bot
$env:PYTHONPATH = "$(Get-Location)\src"   # required: pins the worktree package
$env:PYTHONHASHSEED = "0"
$env:SHOWDOWN_BATTLE_SEED_BASE = "champions-panel-v0-smoke-i7a-mega"
$env:SHOWDOWN_CALC_BACKEND = "persistent"
$env:SHOWDOWN_ROOM_RAW_DUMP = "<local cache path>\room_raw"
python -m showdown_bot.cli gauntlet `
  --schedule ..\config\eval\schedules\champions_v0_smoke_i7a_2battle.yaml `
  --panel ..\config\eval\panels\panel_champions_v0.yaml `
  --result-out ..\data\eval\champions-panel-v0\smoke-i7a-mega\results.jsonl `
  --decision-trace-out ..\data\eval\champions-panel-v0\smoke-i7a-mega\decision_trace.jsonl
```

Regenerate the report:

```powershell
python -m showdown_bot.cli eval-report --run-a results.jsonl --seedlog-a seeds.jsonl --schedule champions_v0_smoke_i7a_2battle.yaml --panel panel_champions_v0.yaml --out <dir> --mode gate
```
