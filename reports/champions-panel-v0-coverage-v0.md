# VERDICT: CHAMPIONS OPPONENT-MEGA COVERAGE GATE — FAIL (`both_foe_slots` zero-exposure, `schedule_exhausted`)

The single separately-authorized `champions-coverage-gate` live run was executed **exactly once**
(after one prior technical abort, see below) on candidate `cbaa4b9` — the merge SHA of the
opponent-Mega coverage-gate harness (Plan A, PR #37 @ `10f9adf`), status docs (PR #38), and the
post-coverage-harness I8-D latency PASS (PR #39). This is the **first** live run of the coverage
gate; there is no prior coverage-gate evidence to compare against. It ran the full, fixed,
pre-registered 200-battle schedule (8 matchups x 25 battles each) to completion, scored 1956
decisions, and recorded **zero** safety violations.

The verdict is **`FAIL`**, `stop_reason=schedule_exhausted`: the fixed schedule ran to its end
and three of the four pre-registered coverage cells (`slot0`, `slot1`, `order_tie`) cleared their
floor comfortably, but the fourth, **`both_foe_slots`, scored zero decisions from zero distinct
battles** against its floor of 15 decisions / 6 distinct battles. Per the pre-registered verdict
contract (`coverage_verdict`, spec Sec.2.6(b)), a fully-exhausted schedule with any cell's floor
unmet is **FAIL**, not INCONCLUSIVE — this is a **load-bearing FAIL**, not a technical abort.

**The zero-exposure in `both_foe_slots` is the immediate, verified driver of this FAIL. Its
technical cause is explicitly NOT diagnosed in this report** — that is separate, out-of-scope
follow-up work. This record establishes only that the driver is real and reproducible from the
frozen bytes, not why it occurred.

## Not merged with I8-D evidence

This report and its frozen evidence are **entirely separate** from every I8-D live-latency run
and report (`i8d-live`, `i8d-live-post-lever-a`, `i8d-live-post-lever-b`,
`i8d-live-post-coverage-harness`) — different gate, different schedule/panel/manifest, different
hash space, never pooled. The I8-D latency **PASS for candidate `bd590c1`** (active foe-Mega p95
864.94 ms <= 1000 ms) is unaffected and stands on its own **as evidence for that candidate**; it
does **not** establish a latency PASS for this run's candidate `cbaa4b9` (see the candidate-identity
gap below). **This coverage-gate FAIL is, on its own, sufficient to block Champions Strength**,
independently of the latency result and of the identity gap.

## Candidate-identity gap — the I8-D latency PASS does not transfer to this candidate

The I8-D latency PASS ran on candidate `bd590c1` (`candidate_identity b3c2e0521505932d`, computed
as sha1[:16] of `{hero_agent, git_sha, config_hash}`). This coverage-gate run ran on candidate
`cbaa4b9` (`candidate_identity 93cd419222683f75`) — the merge SHA produced by PR #39, which merged
that very latency evidence into `main`. **These are two different candidate identities**: `git_sha`
differs (`bd590c1` vs `cbaa4b9`) even though `config_hash` (`594295543f13a55d`) and `hero_agent`
(`heuristic`) are identical between them.

Per the APPROVED coverage/Strength-holdout design spec
(`docs/projects/champions/specs/2026-07-20-champions-coverage-strength-holdout-design.md`), Sec.5
("Shared candidate identity & verdict coupling", P1): *"The gates must pin and verify one and the
same candidate identity ... Coverage and strength must run on the identical candidate identity"*
and *"The latency PASS must correspond to the same candidate identity that runs coverage and
strength ... a prior latency PASS on a decision-equivalent-but-different candidate does not satisfy
this gate."* The spec is explicit that a decision-equivalent merge — exactly this situation, PR #39
changed only evidence/docs, no decision-affecting code — still does **not** carry the PASS over, by
the identical logic the spec already applies to the `3db4ac7` PASS: *"stands as evidence for its
candidate only; it does not transfer."*

**The latency precondition for candidate `cbaa4b9` — the candidate this coverage run actually
tested — is therefore NOT satisfied.** This is a gap independent of, and in addition to, the
`both_foe_slots` coverage FAIL documented below: even had every cell cleared its floor, Strength
would still not be authorized for `cbaa4b9` without its own latency PASS. The `bd590c1` PASS remains
fully valid as historical evidence for its own candidate. A future fix must re-run the latency gate
and the coverage gate on the **same** final merge SHA, before any subsequent evidence-merge changes
that SHA again (so this gap does not recur).

## First attempt — technical abort, explicitly not a verdict

A first attempt (external run directory `coverage-live-cbaa4b9`, no `-attempt2` suffix) exited
immediately (`exit code 1`) with `champions-coverage-gate requires SHOWDOWN_EVAL_SEED_LOG`. Root
cause: an operator error (a required environment variable was not re-exported in the specific
shell invocation that launched the gate). This failed at CLI argument validation, **before**
`build_coverage_live_schedule`, provenance resolution, or any contact with the running server.
Confirmed **zero** side effects: no `seeds.jsonl`, no `out/`, no `out.staging/`, an empty
server-side error log, and a server process that ran the entire time without fault (its per-battle
seed counter never incremented, because no battle was ever requested). No retry followed
automatically; a fresh attempt with a fresh output path was separately authorized and is the one
this report documents. This first attempt is **kept out of the frozen evidence** and is not part of
the verdict population in any way.

## Frozen evidence (`data/eval/champions-panel-v0/coverage-v0/`)

| file | sha256 | bytes |
|---|---|---|
| `profile.jsonl` | `7d15626e8cc7101ec30febc6130391bccc68105fb57f844958a33c15dacbb90c` | 2122340 |
| `verdict.json` | `f8d8f668001e49071d8cd280e96d2a24c849d2339bfe6a6a5163b4d4712c615d` | 1238 |
| `seeds.jsonl` | `195fa8ffd6a5805cc19a2ddb5ad96d8fbaefd429b2f3e4dd88bc9224344175ba` | 21090 |

Stored byte-exact under `.gitattributes: data/eval/champions-panel-v0/** -text` (no newline
normalization; all three are LF-only). Each git-stored blob's SHA-256 was verified equal to the
external run output (source held outside the repository, unchanged) both immediately after the
copy and again after the commit.

## Verdict

| field | value |
|---|---|
| **verdict** | **`FAIL`** |
| `stop_reason` | `schedule_exhausted` — the full 200-battle fixed schedule completed; **not** a cap and **not** a timeout |
| `safety_violations` | `0` |
| `battles_played` | `200` (== the fixed schedule's own full length; not an early cap truncation) |
| `scored_decisions` | `1956` (`max_scored_decisions` = 2000, **not reached**) |
| `seed_log_verified` | `true` (200/200 seeds, single `seed_base`, contiguous `battle_index` 0-199) |

## Per-cell coverage — the FAIL is driven entirely by one cell

| cell | decisions | distinct battles | floor (decisions / battles) | met? |
|---|---|---|---|---|
| `slot0` | 82 | 50 | 30 / 10 | **yes**, well over |
| `slot1` | 298 | 173 | 30 / 10 | **yes**, well over |
| `order_tie` | 100 | 100 | 15 / 6 | **yes**, well over |
| `both_foe_slots` | **0** | **0** | 15 / 6 | **no — zero exposure** |

The verdict population is defined once, in production, as `is_active_valid_live_row` joined to the
per-row `foe_mega_slots` / `foe_mega_order_tie` fields (`coverage_cell_counts`,
`decision-profile-v3`-only fields). `both_foe_slots <=> {0,1} subset-of foe_mega_slots`: across all
50 battles scheduled against the `both_foe_slots`-target cell (2 matchups — `heuristic` and
`max_damage` opponent policies, both against `cov_foe_both` — x 25 battles each), this condition
was never true on any scored decision.

## Provenance

| field | value |
|---|---|
| git_sha | `cbaa4b99f77d682bf51d06309e7cb4032a5a8145` (opponent-Mega coverage-gate harness + docs + I8-D PASS, PRs #37/#38/#39) |
| dirty | `false` (fresh detached worktree at `cbaa4b9`, tracked tree clean) |
| candidate_identity | `93cd419222683f75` (sha1[:16] of `{hero_agent, git_sha, config_hash}`, canonical JSON) |
| config_hash | `594295543f13a55d` — **identical to every I8-D live-gate run to date** (same `oneshot` stratum, `SHOWDOWN_EVAL_ROOM_DEALLOC` unset) |
| calc_backend | `oneshot` |
| hero_agent | `heuristic` |
| format_id | `gen9championsvgc2026regma` (Champions Reg M-A) |
| `SHOWDOWN_CALC_BACKEND` | **unset** -> `oneshot` |
| `SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S` | **unset** (standard per-battle timeout) |
| `SHOWDOWN_EVAL_ROOM_DEALLOC` | **unset** (explicit — the headless-eval immediate room-dealloc patch was present in the server but inactive this run) |
| schema_version | `decision-profile-v3` (uniform across all 1956 rows; `foe_mega_slots`/`foe_mega_order_tie` exist only on v3 rows and are the coverage gate's own cell-counting inputs) |
| server | patched `pokemon-showdown` pinned at `f8ac140` + seeded-battle patch (Channel A) + immediate-room-dealloc patch (present, unused), `--no-security` on port 8000 |
| host | fixed Windows host |
| seed_base | `champions-coverage-v0` (distinct from every I8-D seed namespace) |

## Content-lock hashes

| artifact | hash |
|---|---|
| `panel_hash` | `11d63978cb64a961` |
| `manifest_hash` | `c4ca3da5118b24ba` |
| `schedule_hash` | `4775d9304836cf3e` |
| `hero_team_hash` | `1d3a4cf5a4042532` |
| `opp_team_hashes` | `0b6930668a9f6e72`, `5bd94d4b1558ba28`, `8b68400f463fe581`, `b7077a81e579aa72` |

All content-derived and freshly re-verified against the exact `cbaa4b9` checkout before the run
(panel + manifest load against their frozen expected hashes; every team file re-hashed from disk;
the schedule's structural invariants — 8 matchups x 25 battles each, contiguous `seed_index`,
`schedule_hash` re-derivation — all independently reproduced offline, with zero server contact,
during preflight).

## Independent re-verification — from the frozen bytes only

Re-checked twice: once against the original external run output before the freeze, and again
against the committed git blobs after the freeze — both reproduce identically, using only the
production predicate/validator/verdict functions, no re-derivation of logic:

- `validate_live_profile_dataset(profile.jsonl)` -> `{rows: 1956, active_valid_rows: 380,
  distinct_active_battle_ids: 199}` (closed-schema, single-version, uniqueness checks all pass).
- `coverage_cell_counts(profile.jsonl)` recomputed independently: **exact match**, all four cells,
  to the published `verdict.json`'s `cell_counts`.
- `coverage_verdict(...)` recomputed independently from the recomputed cell counts: **exact
  match** on `verdict` (`FAIL`) and `stop_reason` (`schedule_exhausted`).
- `seeds.jsonl`: 200 rows, single `seed_base`, matching `battles_played` exactly.
- Hygiene: canonical schema on every row; provenance fields single-valued (one run); no local
  filesystem path, username, or host name in any row.

One further, unrelated operational note observed in the run log: a single per-decision heuristic
search fallback (`"heuristic timed out after 4.0s, falling back"`) occurred once, mid-run. This is
the heuristic agent's own existing soft per-decision search budget, not a gate-level or server-level
timeout; the battle it occurred in completed normally and is included in the 200 played battles.
It has no bearing on the verdict population or the `both_foe_slots` finding.

## Explicit non-claims and status

This record establishes only that, at `git_sha cbaa4b9`, under `oneshot` with
`SHOWDOWN_EVAL_ROOM_DEALLOC` unset, on this single run of the full pre-registered 200-battle
coverage schedule, the opponent-Mega coverage gate returned **FAIL** because the `both_foe_slots`
cell scored zero decisions against its floor, while every other cell passed comfortably. It does
**not** establish, and must not be read as:

- an **OOM, timeout, or cap finding** — `battles_played` reached the schedule's own full length
  (not an early `max_battles` truncation), `scored_decisions` stayed under its cap, and the server
  ran the entire 200-battle schedule without a reported fault;
- a **diagnosis** of *why* `both_foe_slots` was never triggered — that determination (a
  team/matchup construction issue, a scoring-path gap, or something else) is separate,
  out-of-scope follow-up work;
- any claim about **I8-D latency** — the PASS for candidate `bd590c1` (p95 864.94 ms <= 1000 ms)
  is untouched and kept in its own, separate evidence line;
- any **Strength** result — Champions Strength remains **`NO-GO`**. The latency precondition for
  `bd590c1` is closed **for that candidate only**; per the candidate-identity gap above, the
  latency precondition for **this run's candidate `cbaa4b9` is NOT established**, independent of
  and in addition to this coverage-gate FAIL;
- validity for any **other** candidate commit, schedule, or manifest — this FAIL is scoped to
  `cbaa4b9` and the frozen `schedule_hash`/`panel_hash`/`manifest_hash` above exactly.

**The coverage gate FAILs for candidate `cbaa4b9` on `both_foe_slots` zero-exposure; separately,
the latency precondition for `cbaa4b9` itself is unestablished (candidate-identity gap above);
Strength stays NO-GO on both grounds.** Diagnosing the zero-exposure, closing the identity gap by
re-running latency and coverage on the same final merge SHA, and any resulting fix are separate,
not authorized here.
