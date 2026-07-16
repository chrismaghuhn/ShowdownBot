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
| run_id | `d074ce1c8a69a2e1` |
| config_id | `heuristic` |
| config_hash | `b3cb6ea1a4836060` (LF-stable, platform-independent) |
| format_id | `gen9championsvgc2026regma` |
| schedule_hash | `b67a851881d76918` |
| panel_hash | `aac1ea30446fde88` |
| seed_base | `champions-panel-v0-smoke-i7b-mega` |
| git_sha | `3d23e654a29689b68f3c936653726d6a36a6934d` |
| showdown_commit | `f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5` |
| server_patch_hash | `86e31891547e87da` |
| dirty | `false` |
| start_ts | see `results.jsonl.manifest.json` |

`schedule_hash` equals the I7a smoke's by construction: `compute_schedule_hash` covers
`version` + `(format_id, hero_team_path, opp_policy, opp_team_path, seed_index)`, and the
I7b schedule is an exact copy of those frozen rows. Same battles, new code — the runs are
distinguished by `git_sha`, never by the battles they run.

`config_hash` `b3cb6ea1a4836060` is the **platform-stable LF value**: a Linux and a Windows
checkout now compute it identically, and CI's `provenance-bytes` job asserts that on both.
It is not comparable to I7a's `e137fce925f25bd8`, which is a pre-fix Windows-byte-specific
value (see "Superseded first run" below).

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
| latency_p95 | worst=672 (budget 1000) |
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

Worst `decision_latency_p95_ms` = **672 ms** against the unchanged 1000 ms budget; per
battle 672 / 421.

**This is not a latency result.** It says only that *this* run passed the standard gate. It
does **not** replace the dedicated Champions latency profile, and it does **not** refute the
measured ~2.4× overhead of the active foe-Mega path: that path was active in **1 of 17**
decisions here, so this run barely exercises the expensive case. **Latency remains the
load-bearing blocker for Champions Strength, which stays NO-GO.**

## Artifacts

Committed under `data/eval/champions-panel-v0/smoke-i7b-mega/`:

| file | sha256 |
|---|---|
| `results.jsonl` | `51b44a42d9f99d44987e0e44b2497962af6ebe64dba1623a9359c8d549e88639` |
| `results.jsonl.manifest.json` | `930084e02067ebbccdadd3a108fd3b7f80f6f6b1c3804b449ffbb5acf427b602` |
| `results.jsonl.config-manifest.json` | `eec436004502d381645da3b19b6cf3c3253a713b2f79603e294fc4093178674d` |
| `seeds.jsonl` | `b9b52e62c25493f1ee0cceba0670dabe59e570c5f9087aa8ed82795ddcc3b847` |
| `decision_trace.jsonl` | `7d41824727fa9d03560ca82d856446f2d2d82427fb3479a785182447f90a52d4` |
| `opp_mega_trace.jsonl` | `8469a15ae0b6a90efa6917f83416b174ae20e811d8b0d552f4b2f618b32d69c1` |
| `report.json` | `364a753c1d034601ee3f07692cc6b111449281e916cb256e573618c5209fec92` |
| `report.md` | `ad266e075e18c76b68d665f8f779a9dd2db461d14197f64141337b8d10c3d79f` |

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

## Superseded first run (why this evidence was re-recorded)

An earlier execution of these identical battles (`run_id f61212da239c9ee6`,
`git_sha 96671cb3`) is archived at
`data/eval/champions-panel-v0/superseded-smoke-i7b-mega-crlf-config-hash/`. It was sound in
every respect except one: its `config_hash` `5fb04622afebd59f` was **Windows-byte-specific**.

`config_hash` was built from raw file bytes over inputs that `core.autocrlf` checked out as
CRLF on Windows and LF on Linux, so the identical configuration hashed to `5fb04622afebd59f`
on this machine and `b3cb6ea1a4836060` on CI. `config_hash` was an identity of the
configuration *plus the host's line endings*. Fixed on `main` (PR #18): `text eol=lf` for
every raw-byte-hashed provenance input, plus a `provenance-bytes` CI job that runs on
**both** ubuntu and windows and asserts they agree.

The archived rows are **not** re-hashed. They record what the run that actually happened
computed; rewriting them to the LF value would falsify a run that never produced those bytes.
This run re-records the same battles under the fixed, platform-stable hash.

One further attempt (`run_id 57367d7a2e6bfd83`) was discarded outside the repository: it
recorded `dirty=true` because the evidence archive was still uncommitted when the gauntlet
read `git_sha_and_dirty()`. Operational failure, before any gate evaluation, so it was voided
and repeated with a clean tree rather than explained away.

## Explicit non-claims

- **No strength claim.** 0/2 says nothing; a strength result needs a paired run against a
  pinned baseline with the positive-evidence rule.
- **No latency claim.** 672 ms passed *this* run's gate; the dedicated latency profile is
  still outstanding and the ~2.4× foe-Mega overhead is untouched by this evidence.
- **No broad opponent-Mega correctness claim.** 1/17 decisions, slot 1 only.
- **No budget change.** The 1000 ms budget is unchanged.
- The battles were executed with the schedule and seed base unchanged. The seed log is
  **byte-identical** to the superseded run's, so these are the same two battles -- not a
  reseed and not seed shopping.
- No claim is made that this run's telemetry is byte-identical to the superseded one; it is
  not, and it should not be. `opp_mega_trace.jsonl` differs in exactly `config_hash` and
  `git_sha`; `decision_trace.jsonl` additionally in `decision_latency_ms` (timing) and
  `request_hash`/`observable_state_hash` (the bots' per-run name suffixes). The
  `normalized_room_log_sha256` values are identical, which is what says the battles
  themselves played out the same.
