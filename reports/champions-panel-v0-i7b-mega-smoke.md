# Champions I7b Opponent-Mega Safety Smoke — Verdict

## Verdict

**I7b OPPONENT-MEGA SAFETY PASS · NARROW EXPOSURE (1/17 decisions, slot 1 only) · NO STRENGTH CLAIM · NO LATENCY CLAIM**

A 2-battle safety smoke proving that an opponent-Mega hypothesis is *generated and scored*
on the live path, and that its telemetry is provenance-sound. It is **not** a strength
claim, **not** a latency result, and **not** a claim that opponent Mega is validated in
general — see "Narrow exposure" below, which is part of the verdict, not a footnote.

## Provenance

| field | value |
|---|---|
| run_id | `f61212da239c9ee6` |
| config_id | `heuristic` |
| config_hash | `5fb04622afebd59f` |
| format_id | `gen9championsvgc2026regma` |
| schedule_hash | `b67a851881d76918` |
| panel_hash | `aac1ea30446fde88` |
| seed_base | `champions-panel-v0-smoke-i7b-mega` |
| git_sha | `96671cb31f3eaece9ff3b9544803d5bd2f1f76f7` |
| showdown_commit | `f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5` |
| server_patch_hash | `86e31891547e87da` |
| dirty | `false` |
| start_ts | `2026-07-16T18:57:03.104113+00:00` |

`schedule_hash` equals the I7a smoke's by construction: `compute_schedule_hash` covers
`version` + `(format_id, hero_team_path, opp_policy, opp_team_path, seed_index)`, and the
I7b schedule is an exact copy of those frozen rows. Same battles, new code — the runs are
distinguished by `git_sha`, never by the battles they run.

`config_hash` differs from I7a's `e137fce925f25bd8` because this run set two
BEHAVIOR_AFFECTING variables (below). That difference is expected and is exactly what the
config-manifest sidecar exists to record.

## Run environment (complete)

Behaviour-affecting environment, frozen in `results.jsonl.config-manifest.json`:

| variable | value | classification |
|---|---|---|
| `SHOWDOWN_HERO_AGENT` | `heuristic` | BEHAVIOR_AFFECTING → in `config_hash` |
| `SHOWDOWN_OPP_MEGA_CLICK_RATE` | `0.35` | BEHAVIOR_AFFECTING → in `config_hash` |

Non-behavioural / IO and harness variables, deliberately **excluded** from `config_hash`:

| variable | value | why excluded |
|---|---|---|
| `SHOWDOWN_OPP_MEGA_TRACE_OUT` | `../data/eval/champions-panel-v0/smoke-i7b-mega/opp_mega_trace.jsonl` | NON_BEHAVIORAL: an output path. Enabling the sidecar must not perturb `config_hash`, or telemetry-on and telemetry-off runs would be incomparable. Must never be confused with `SHOWDOWN_OPP_MEGA_CLICK_RATE`, which is behavioural. |
| `SHOWDOWN_BATTLE_SEED_BASE` | `champions-panel-v0-smoke-i7b-mega` | seeding (recorded separately as `seed_base`) |
| `SHOWDOWN_EVAL_SEED_LOG` | `…/smoke-i7b-mega/seeds.jsonl` | IO path (Channel-A seed log) |
| `SHOWDOWN_CALC_BACKEND` | `persistent` | harness/transport |
| `SHOWDOWN_ROOM_RAW_DUMP` | external cache only | IO path; raw logs are never committed |
| `PYTHONHASHSEED` | `0` | recorded in the run manifest |

Platform: `Windows-11-10.0.26200-SP0` · Python `3.14.5` · Node `v24.16.0` ·
pydantic `2.13.4`, websockets `16.0`, lightgbm `4.6.0`.

Fresh pinned server started for this run (Channel-A requires it); stopped cleanly
afterwards.

## Result and standard safety gate

`eval-report --mode gate` → **`SINGLE-RUN SAFETY-PASS`**, `safety_pass: true`, **19/19 gates PASS**.

| gate | measured |
|---|---|
| rows_match_schedule | 2 == 2 |
| invalid_choices | 0 |
| crashes | 0 |
| end_reason_normal | all normal |
| latency_p95 | worst=637 (budget 1000) |
| seed_log_alignment | 2 contiguous, derived |
| one_config_hash / one_schedule_hash / one_seed_base / one_run_id / one_git_sha | single value each |
| manifest_match | ok |

Battles: seed 0 vs `goodstuff.txt` (`heuristic`, split `dev`, 8 turns);
seed 1 vs `rain_offense.txt` (`max_damage`, split `heldout`, 5 turns). Hero 0/2.
`opp_team_hash` `0054b6894af7215a` / `e0c96fa0cabf1def` — the frozen panel values.

**The 0/2 record is not a result.** A single run cannot establish anything about strength;
the report's own warnings say so (single-run readout, ceiling effect at n=1 cells, held-out
numbers must never inform tuning).

## Telemetry

- **Decision trace**: 19 rows, 19/19 pass the real `validate_trace_row`, all
  `decision-trace-v3`, `fallback_reason` `null` on every row (no hidden fallback or
  state-degradation claim), 2 `team_preview` rows.
- **Opponent-Mega sidecar**: 17 rows, 17/17 pass `validate_opp_mega_trace_row`, all nine
  parallel arrays equal-length on every row, `opp_mega_click_rate` recorded as `0.35`,
  `max_candidates` `5`.
- **Bytes**: LF-only, no `CR`, one `LF` per row, file ends with `LF` — verified on **raw
  bytes**, because a text-mode read applies universal newlines and would hide a CRLF defect
  on exactly the platform (Windows) that produces one.

## Decision-index join

| battle | trace indices | sidecar indices | gap |
|---|---|---|---|
| `242a0c3ec6d0e79c` | `[0…7]` | `[1…7]` | `[0]` |
| `bc08ec1e58486610` | `[0…10]` | `[1…10]` | `[0]` |

17/17 sidecar `(battle_id, decision_index)` keys resolve to **exactly one** decision-trace
row. The sidecar index set is a subset of the trace's, and **every gap is provably a
`team_preview` row** (`decision_phase: "team_preview"`, `normalized_action.kind:
"team_preview"`) — a decision the sidecar cannot record, because team preview has no battle
state and therefore no opponent-response scoring.

This is the live confirmation of the pre-smoke [P1] fix. The sidecar stamps rows with the
client's shared request sequence, not with a count of rows written. Had it used a row
counter, both battles' sidecars would read `[0…N-1]` and **every row would point at the
wrong decision** — silently, and in a way that looks perfectly well-formed.

## Opponent-Mega evidence gate

**Met, by exactly one decision.**

Battle `242a0c3ec6d0e79c`, `decision_index=4`, `turn_number=3`:

| field | value |
|---|---|
| `required_classes` | `["1", "none"]` |
| `retained_classes` | `["1", "none"]` |
| `scored_classes` | `["1", "none"]` |
| array length | 205 |
| distinct `foe_mega_slots` | `1` and `None` — **in the same row** |
| twin `response_ids` | `aggro->a|mega=1` and `aggro->a|mega=none` |

The three class facts are distinct and all three hold: the eligibility set `R` was
`{1, none}`; the coverage-preserving cap **retained** both; and both **survived projection
and contributed a score**. `required ⊆ retained` and `scored ⊆ retained` hold on all 17
rows. 41 distinct hero candidate keys appear with a non-null `foe_mega_slot` — each such
pairing is itself the proof that that candidate's score pool included a foe-Mega branch, no
cross-sidecar join required.

Per the approved gate, an eligible-but-unclicked hypothesis is a complete proof: the
protocol `-mega` event is supporting evidence only, and the gate does not depend on it.

## Narrow exposure (part of the verdict)

Only **1 of 17** scored decisions ever exposed a foe-Mega hypothesis; the other 16 carry
`required = retained = scored = {"none"}`. The Mega-capable opponent Pokémon
(Delphox @ Delphoxite, Meganium @ Meganiumite) were rarely on the field, so eligibility
almost never fired. Consequently:

- only **slot 1** was ever exercised; **slot 0 was never tested live**;
- only the `max_damage` battle produced exposure; the `heuristic` battle produced none;
- dual-Mega (own + foe on the same turn) was not observed;
- the activation-ordering path was not exercised by this run.

The gate requires "at least one" and that is genuinely met — but this smoke is **thin
evidence of a working mechanism, not broad evidence of correctness across the Mega space**.
Unit and integration tests cover the other paths; this run does not.

## Latency

Worst `decision_latency_p95_ms` = **637 ms** against the unchanged 1000 ms budget; per
battle 637 / 396.

**This is not a latency result.** It says only that *this* run passed the standard gate. It
does **not** replace the dedicated Champions latency profile, and it does **not** refute the
measured ~2.4× overhead of the active foe-Mega path: that path was active in **1 of 17**
decisions here, so this run barely exercises the expensive case. **Latency remains the
load-bearing blocker for Champions Strength, which stays NO-GO.**

## Artifacts

Committed under `data/eval/champions-panel-v0/smoke-i7b-mega/`:

| file | sha256 |
|---|---|
| `results.jsonl` | `3c705fb21e5b6935e00e963b60272a1978cf46b7d4182e5f0f4bb0819ad2734c` |
| `results.jsonl.manifest.json` | `ed91989dea55e0f103762845a5a0d200e5d65a1156cc16c86c1c8927aa785e23` |
| `results.jsonl.config-manifest.json` | `f4ba9341048cdce7c10d141998a03c0f7c87ee96fd312723e355bd0aa8ae4803` |
| `seeds.jsonl` | `b9b52e62c25493f1ee0cceba0670dabe59e570c5f9087aa8ed82795ddcc3b847` |
| `decision_trace.jsonl` | `408fbbb988acd60de78191e7520c8486881c1f1f1b8c011afda21df05cf0f5db` |
| `opp_mega_trace.jsonl` | `cfb5040c21cafe2241e2bafc1abfdcc4f8486b1c57143fe2b73ed4debc58b97d` |
| `report.json` | `d3e4d0cb04e8d067a9265637c9a78cc9f70995677dee8a49fad82d37c6a640a9` |
| `report.md` | `a6875214faa64c1379cd18b1eb36cf211aa654f953a3344fef9a59cbb7e74d25` |

Local-only, never committed (external cache
`~/.cache/showdownbot/measurements/champions-panel-v0-smoke-i7b-mega/`): 2 raw room logs,
`run.log`, `server.log`.

## Evidence hygiene applied before freezing

1. `room_raw_path` set to `null` on both result rows — they held absolute local paths.
   `normalized_room_log_sha256` is deliberately **unchanged**
   (`38cb9902…c8fc`, `977daeff…9575`): it binds each row to its room log by *content*,
   which is precisely what survives dropping a machine-specific path. Both local room logs
   were confirmed to reproduce their recorded digest.
2. `cli_invocation[0]` canonicalised to `showdown_bot.cli` (it held the worktree's absolute
   path), matching the I7a precedent.
3. `results.jsonl.config-manifest.json` written with `write_config_manifest_sidecar` and
   re-verified with `verify_config_manifest_sidecar` **after** the mutation above, so the
   manifest/`config_hash` binding is checked against the frozen bytes rather than the
   pre-cleanup ones.

Both mutations were re-serialised with the original writers' own functions
(`to_jsonl_line`, `json.dumps(sort_keys=True, indent=2)`, `newline="\n"`), so the frozen
bytes stay canonical rather than merely valid. `eval-report --mode gate` was then re-run:
still 19/19 PASS, with the results digest correctly updated to the sanitised file.

The config-manifest step caught a real error rather than rubber-stamping one: an initial
attempt using only `SHOWDOWN_OPP_MEGA_CLICK_RATE` recomputed `379c6df1176c2372`, not the
recorded `5fb04622afebd59f`. `SHOWDOWN_HERO_AGENT` is also BEHAVIOR_AFFECTING, and the
sidecar's fail-closed check refused the incomplete environment instead of freezing a wrong
manifest.

4. **`.gitattributes`: `data/eval/champions-panel-v0/** -text`.** Without it the frozen
   hashes above are not reproducible. The repo runs `core.autocrlf=true` and the Champions
   eval tree had no attribute, so git rewrote LF blobs to CRLF on checkout — measured, not
   assumed: **38 of 39** pre-existing Champions eval files (pilot smoke, I5, I5-hpfix, I6,
   I7a-C, discovery, mechanics) had CRLF working copies against LF blobs, e.g. I7a-C's
   `results.jsonl` at worktree `f4da66b8…` vs blob `7a1df9f8…`. `git status` reported them
   clean throughout, because it consults a stat cache rather than re-reading content after an
   attribute change. The rule follows the existing `data/eval/t4|t6|2b4/**` precedent
   verbatim in rationale, and is deliberately panel-wide so it also repairs the I5/I6/I7a
   evidence rather than only this smoke.

   The 37 drifted files were re-materialised from their **existing blobs** (delete +
   `git checkout --`, never `git add --renormalize`, which would have committed the CRLF
   working copies as new blobs). It was proven first that their only difference from the
   blob was line endings (`worktree.replace(CRLF, LF) == blob` for all 37, zero real content
   differences), so nothing was destroyed; all 37 are now byte-identical to their committed
   blobs and none appears as modified in this commit.

   The rule also caught a defect in **this** slice's own evidence: `write_config_manifest_sidecar`
   writes with the platform default newline (unlike `BattleResultWriter`, which passes
   `newline="\n"`), so `results.jsonl.config-manifest.json` was CRLF on disk while its blob
   was LF — and this report initially pinned the CRLF hash (`f8c07bd4…`), a value no checkout
   would ever reproduce. The file is now LF and the table above cites the blob's hash
   (`f4ba9341…`). **Open finding, out of scope for this evidence-only commit:**
   `write_config_manifest_sidecar` should pass `newline="\n"` like the other JSONL/JSON
   writers; `.gitattributes` protects the committed bytes but does not fix the writer.

## Explicit non-claims

- **No strength claim.** 0/2 says nothing; a strength result needs a paired run against a
  pinned baseline with the positive-evidence rule.
- **No latency claim.** 637 ms passed *this* run's gate; the dedicated latency profile is
  still outstanding and the ~2.4× foe-Mega overhead is untouched by this evidence.
- **No broad opponent-Mega correctness claim.** 1/17 decisions, slot 1 only.
- **No budget change.** The 1000 ms budget is unchanged.
- The run was executed exactly once with this seed base. No rerun, no seed shopping.
