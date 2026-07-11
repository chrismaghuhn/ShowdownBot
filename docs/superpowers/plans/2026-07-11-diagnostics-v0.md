# Diagnostics v0 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development.
> Steps use checkbox (`- [ ]`) syntax.

**Goal:** A pure, deterministic, fixture-tested diagnostics module that mines normalized battle
logs for three tactical-failure buckets, aggregates them, and computes a candidate-vs-baseline
bucket delta — then a demonstration of the delta on the 2b-4 strength logs.

**Architecture:** New `showdown_bot/src/showdown_bot/eval/diagnostics.py`, consuming the T4c
`room_dump.normalize_battle_log` frame form. No live-path hook, no battles. Spec:
`docs/superpowers/specs/2026-07-11-diagnostics-v0-design.md`.

**Tech stack:** existing repo (pytest). **Constraint:** run only touched test files per task;
full suite once at closeout (1 strict-xfail known; and remember `npm ci --prefix tools/calc` must
have been run for calc tests — irrelevant here, this slice touches no calc).

---

### Task 1: schema + three detectors (Sonnet)

**Files:** Create `showdown_bot/src/showdown_bot/eval/diagnostics.py`; test
`showdown_bot/tests/test_diagnostics.py`.

- [ ] Study `eval/room_dump.py` (`normalize_battle_log`, `GAUNTLET_NAME_SUBS`, and the frame
  form: a list of `|`-delimited protocol lines) and `eval/battle_parse.py` (how it iterates
  frames + splits `|tag|args` — reuse its splitting idiom, do not reinvent). Study a real
  normalized log shape from the committed fixture `data/eval/t4/rerun/room_raw/` (gunzip one).
- [ ] `DiagnosticBucket` Literal (v0: "PANIC_SWITCHING", "ATTACK_INTO_PROTECT",
  "IMMUNITY_PUNISHED") + frozen `DiagnosticEvent` dataclass (battle_id, turn, side, bucket,
  severity, action, target, evidence dict with SORTED keys for determinism).
- [ ] `_iter_turns(frames)` helper: yield (turn_number, [lines in that turn]) using `|turn|N`
  markers (turn 0 = pre-first-turn lead/switch block). Deterministic.
- [ ] Three pure detectors, each `detect_<bucket>(frames, *, battle_id) -> list[DiagnosticEvent]`:
  - `detect_attack_into_protect`: within a turn, a `|move|<atk>|<mv>|<tgt>` whose target shows
    `|-activate|<tgt>|move: Protect` (or `|-block|<tgt>|...Protect`) same turn AND the move is a
    damaging move targeting an OPPONENT slot (attacker side != target side). Severity "warn".
  - `detect_immunity_punished`: a `|move|<atk>|<mv>|<tgt>` immediately (same turn, next relevant
    line) followed by `|-immune|<tgt>`. attacker side != target side. Severity "warn".
  - `detect_panic_switching`: per side, collect `|switch|<slot>: <species>` per turn; flag an
    A→B→A species oscillation on the SAME slot within a 3-turn window with no `|faint|` on that
    side in between. Severity "warn" (one event per detected oscillation, on the switching side).
  - Every detector wrapped so a malformed line is skipped (try/except per line, never raises).
- [ ] `diagnose_battle(frames, *, battle_id) -> list[DiagnosticEvent]` runs all three, returns
  events sorted by (turn, side, bucket) for determinism.
- [ ] Tests: hand-authored tiny normalized-log fixtures (as `list[str]`) — one POSITIVE + one
  NEGATIVE per detector (e.g. attack-into-protect fires; attack into a non-protected target does
  not; a status move into Protect does not; immune-negated move fires; super-effective does not;
  A→B→A oscillation fires; A→B with a faint between does not). Determinism test: same input →
  identical event list twice. Malformed-frame test: a garbage line is skipped, others still detect.
- [ ] Run touched tests. Commit `feat(diagnostics): schema + attack-into-protect/immunity/panic-switch detectors`.

### Task 2: aggregation + candidate-vs-baseline bucket delta (Sonnet)

**Files:** extend `eval/diagnostics.py`; test `test_diagnostics.py`.

- [ ] `aggregate(events) -> dict`: {bucket -> {count, by_severity {info/warn/fail}}, total,
  n_battles} — pure, deterministic (sorted keys).
- [ ] `diagnose_run(battles) -> (all_events, aggregate)` where `battles` is an iterable of
  (battle_id, frames). Skips a battle whose frames fail to parse, counting it in a
  `parse_skipped` tally in the aggregate (fail-closed, surfaced — never silently dropped).
- [ ] `bucket_delta(events_a, events_b, *, hero_side_a, hero_side_b) -> dict`: per bucket, the
  HERO-side event count in run A (baseline agent) vs run B (candidate) and delta = B_count −
  A_count; a `verdict_per_bucket` of "candidate_improves" (delta<0), "candidate_regresses"
  (delta>0), "flat" (delta==0). Include a top-level `note` string embedding the invariant:
  "diagnostic signal only — NOT a gate; strength gate stays paired McNemar/winrate".
- [ ] `format_diagnostics_md(aggregate, *, delta=None) -> str`: a compact markdown section
  (bucket table + optional delta table + the not-a-gate note + parse_skipped).
- [ ] Tests: aggregate over fabricated events (counts/severity correct, parse_skipped surfaced);
  bucket_delta on fabricated A/B event lists (improve/regress/flat verdicts, hero-side filtering
  correct); the markdown contains the required sections + the not-a-gate note (structure test).
- [ ] Run touched tests. Commit `feat(diagnostics): run aggregation + candidate-vs-baseline bucket delta`.

### Task 3 (controller-orchestrated): apply to 2b-4 strength logs + closeout

- [ ] Run `diagnose_run` + `bucket_delta` on the LOCAL 2b-4 strength archives
  (`C:/tmp/kaggle25a/2b4/strength_v2/heuristic/room_raw` = baseline hero, `.../override/room_raw`
  = candidate hero; both hero side = p1, paired by seed). Both must be gunzipped + normalized via
  `normalize_battle_log(GAUNTLET_NAME_SUBS)` first.
- [ ] Write `reports/2026-07-11-diagnostics-v0.md`: what the three detectors are, the aggregate
  bucket counts for heuristic vs override on the 2b-4 dev-strength battles, the bucket delta
  (did the override change PANIC/PROTECT/IMMUNITY habits?), the explicit not-a-gate framing, and
  the honest caveat that this is 3 buckets of a larger taxonomy (link `TestBOtpläne/12-...` via
  the reports dir's convention / cite it). Commit the report (logs stay local; numbers cited).
- [ ] Full suite once: green + 1 xfailed (known). Commit report. `git diff main --stat` → merge decision.

## Self-review (writing-plans)

- Spec coverage: detectors→Task 1, aggregation+delta→Task 2, 2b-4 application→Task 3. ✓
- No battles, no live-path hook, fixture-based tests; the real-data run is a report demo on local
  logs (reproducible parts are the committed detectors + fixtures). ✓
- Not-a-gate invariant embedded in code (`bucket_delta` note) + report. ✓
- Deterministic (sorted keys, sorted event lists, never-raise detectors). ✓
