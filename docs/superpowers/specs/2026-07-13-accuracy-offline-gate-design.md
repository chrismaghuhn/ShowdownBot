# Accuracy Off/On Offline Decision-Diff Gate — Design

**Status:** spec-ready (incorporates 2 rounds of corrections)
**Scope:** an evaluation/measurement task, not a new bot feature. Gates three downstream
decisions — flipping `SHOWDOWN_ACCURACY_MODE`'s default, a new strength baseline, and Depth-2
Stage 3 — none of which start until this gate's numbers exist and are reviewed. No default-on,
no strength claim, and no Depth-2 Stage 3 work follows from this gate alone.

## 1. Two gates, two verdicts

**Gate A — smoke test.** The board from `scratchpad/bench_accuracy_latency.py` (already has an
accuracy<100 spread move on each side) plus 1–2 additional real archetypes pulled from
`config/eval/panels/panel_v001.yaml`, each swept across the 7 field-bucket variants the Depth-2
Stage 2 script used (`neutral`, `tailwind_both`, `tailwind_p1`, `tailwind_p2`, `trick_room`,
`sun`, `rain`). Direct `heuristic_choose_for_request` calls, no server. Reported and verdicted
**separately from Gate B**, explicitly labeled a smoke test: field variants of a small number of
fixed boards are not independent game situations and barely touch late-game states, damaged
mons, KOs, redirection, or switch states — Gate A cannot license anything on its own.

**Gate B — real replayed corpus.** A genuinely valuable finding changed this gate's shape:
`data/eval/t4/`, `data/eval/t6/room_raw/`, and `data/eval/kaggle-validation/room_raw/` contain
197 real gzipped Showdown protocol logs from past gauntlet runs (turns 1–21, real KOs/switches/
damage, ~15+11 distinct opponent teams across `heuristic`/`max_damage`/`greedy_protect`/
`simple_heuristic`/`scripted_vgc` policies). This is real data, not synthetic — Gate B replays a
**frozen, stratified sample** of real `(state, request)` pairs through `heuristic_choose_for_request`
with `SHOWDOWN_ACCURACY_MODE` off vs on and compares.

**Gate B's own scope boundary, stated explicitly in the TL;DR of its report:** the corpus's hero
side is only 2 fixed teams (`data/eval/t4/`'s team and `data/eval/t6/`'s team). Gate B is a
**policy/state generality check** (real turns, real damage/KO/switch states, diverse opponent
policies) — it is **not a hero-team generality check**. Do not let the report's language imply
otherwise.

## 2. Prerequisite: an internal `LineEvaluation` detail path (not a second resolver call)

`evaluate_line()`'s `_one(tb)` closure already computes `leaves, fallback_leaves, fork_records =
resolve_turn_branches(...)` internally when `accuracy_mode` is on, then discards `leaves`/
`fork_records`, keeping only the aggregated `(score, representative_outcome)`. Calling
`resolve_turn_branches` a **second time** from trace-population code to recover this data was
rejected: it doubles a meaningful chunk of work in trace-enabled decisions and creates a real risk
of the recorded diagnostics silently drifting from the score that actually drove the decision
(different inputs, different tie-break resolution, different cap state between the two calls).

**Chosen design:** extract the current `_one`/tie-averaging logic out of `evaluate_line` into a
private `_evaluate_line_details(...) -> LineEvaluation`, where:

```python
@dataclass
class LineEvaluation:
    score: float
    representative_outcome: TurnOutcome
    leaves: list[tuple[float, TurnOutcome]] | None = None   # None when accuracy_mode is off
    fork_records: list[ForkRecord] | None = None             # None when accuracy_mode is off
    fallback_leaves: int = 0
```

`_evaluate_line_details` does the exact same single resolve pass `_one`/`evaluate_line` does
today (including tie-averaging: `leaves`/`fork_records` correspond to whichever tie-break
resolution produced the representative outcome, matching the existing convention that a tied
line's returned `TurnOutcome` already only reflects one ordering). The **public**
`evaluate_line(...) -> tuple[float, TurnOutcome]` becomes a two-line wrapper:

```python
def evaluate_line(...) -> tuple[float, TurnOutcome]:
    d = _evaluate_line_details(...)
    return d.score, d.representative_outcome
```

Every existing call site (all ~10 in `decision.py`) needs zero changes — same signature, same
return shape, byte-identical behavior. The new trace-population code path calls
`_evaluate_line_details` directly and reads `leaves`/`fork_records`/`fallback_leaves` from the
**same** pass that produced the score — no drift is possible by construction, no duplicate
compute.

This closes part of `docs/ROADMAP.md`'s P0 item 5 (`AccuracyDiagnostics`→`DecisionTrace`) as a
side effect, though it does not close the whole item — `accuracy_diagnostics()` itself still isn't
called from live decision code after this; `LineEvaluation` just makes the raw ingredients
reachable without an architecture that risks drift.

**Small wiring alongside this:** `_evaluate_line_details` is private to `evaluate.py` — Gate A/B's
scripts don't call it directly. Instead, `decision.py`'s existing trace-population block (the
`_breakdowns_for`-style loop) switches to calling `_evaluate_line_details` internally and extracts
two new **lightweight, summary** fields onto `CandidateTrace` — not the full `leaves`/
`fork_records` trees, which would bloat trace files with redundant nested `TurnOutcome` data for
no benefit here:

```python
@dataclass
class CandidateTrace:
    # ...existing fields unchanged...
    accuracy_branch_cap_hits: int = 0
    event_hit_probabilities: dict[tuple[SlotId, SlotId], float] = field(default_factory=dict)
```

`event_hit_probabilities` is populated from `LineEvaluation.leaves[0][1].attempted_hits` (the
all-hit representative leaf) paired with `hit_probability(...)` per pair — structurally the same
lookup `accuracy_diagnostics()`'s `accuracy_required` loop already does, just correctly named
here (see §3) and computed from data already in hand, not a second resolve pass. Both fields
default to `0`/`{}` when `accuracy_mode` is off, matching `TurnOutcome.accuracy_branch_cap_hits`'s
existing off-path default. Gate A/B's scripts read these off `trace.candidates[i]` for whichever
candidate is `chosen_candidate_id`, via the same `trace=DecisionTrace()` pattern the Task 5
integration test (`tests/test_accuracy_mode_wiring.py`) already established — not a new access
pattern. `aggregate_score`/`rank` are already present per `CandidateTrace` — margin-to-runner-up
(`trace.candidates[0].aggregate_score - trace.candidates[1].aggregate_score`) needs no new field.

## 3. Terminology correction (real finding, not just gate-report hygiene)

The already-merged `AccuracyDiagnostics.accuracy_required` field (`battle/evaluate.py`) is
misnamed: its docstring/spec description calls it "a derived threshold above which a risky line
becomes advantageous," but the actual Task 6 implementation just assigns
`hit_probability(attacker_action.move, attacker_mon, target_mon, field)`'s raw value to it — no
threshold is derived anywhere. This is a real, pre-existing naming bug in the merged slice, caught
while scoping this gate, not a property of this gate's own design.

**This gate does not use or touch `AccuracyDiagnostics.accuracy_required`.** Its own new fields
are named for what they actually are: **`event_hit_probability`** (the move's computed hit
probability for a specific attacker/target/field, i.e. `hit_probability(...)`'s raw return) and
**`move_accuracy`** (the move's base accuracy value, `MoveMeta.accuracy`) where the distinction
matters (base accuracy vs. stage/weather-adjusted probability). Neither name implies a derived
break-even threshold. The `AccuracyDiagnostics.accuracy_required` naming mismatch itself is
flagged as a small separate follow-up (rename or fix the field to match its docstring) — tracked,
not fixed here, and not blocking this gate.

## 4. Acceptance rules, pinned before any run

- **No exceptions, NaNs, or invalid actions** across the full replayed sample (Gate A and B).
- **Off-path byte-identical**, re-confirmed empirically on the real corpus (not just trusted from
  the merged slice's own unit/integration tests) — same chosen action, same score, for every
  replayed decision with `SHOWDOWN_ACCURACY_MODE` unset vs. the identical decision computed
  through the same code path with the flag forced off.
- **Chosen-line cap-hit rate — the precise metric that matters, pinned exactly:**
  - **Denominator:** number of *replayed decisions* (not candidates, not individual
    `resolve_turn_branches` calls).
  - **Numerator:** number of those decisions where `trace.candidates[i].accuracy_branch_cap_hits
    >= 1` for whichever `i` matches `trace.chosen_candidate_id` specifically — not any other
    candidate's rate, not an aggregate across all candidates.
  - Report numerator, denominator, the resulting rate, **and a game-clustered bootstrap CI**
    (resample at the game level, matching point 4 below and this project's established
    game-clustered-bootstrap convention from the value-calibration work) — not a naive
    per-decision CI, since multiple decisions from the same game are correlated, not independent.
  - **Verdict bands, pinned now, not chosen after seeing results:**
    - **0–5% chosen-line cap-hit rate:** gate PASSES on this axis. Any rate above exactly 0% is
      still reported explicitly as residual uncertainty in the TL;DR, not silently accepted as a
      clean pass.
    - **>5%:** gate does **not** pass on this axis — reported as FAIL/INCONCLUSIVE, not PASS. The
      branch-cap default or fallback strategy needs re-evaluation before default-on is considered
      again.
    - For an eventual production default-on decision (separate, later, not this gate), the target
      should sit meaningfully closer to 0% than this gate's 5% bar — 5% is this diagnostic gate's
      threshold, not the production bar.
- **Latency within the already-pinned budget** (`reports/2026-07-12-accuracy-slice-latency-gate.md`'s
  p95×5-scaled 1000ms gate at `branch_cap=4`) — re-verified on Gate B's real corpus, not assumed
  to transfer from the one synthetic board Task 8 measured. If Gate B's trace-enabled path is used
  for any latency number, that number must explicitly include the trace-detail overhead (see §6)
  and be reported as a distinct, separately-labeled figure from the non-traced production latency.
- **Every decision diff must be reproducible** (deterministic re-run, same inputs → same result)
  **and have a mechanically plausible accuracy cause** — traceable to a specific entry in
  `trace.candidates[i].event_hit_probabilities` for one of the diffing candidates, not an
  unexplained score wobble. A diff that can't be explained this way is a red flag to investigate
  separately, not to silently fold into the accuracy-effect count.

## 5. Per-diff capture schema (both gates)

For every decision where the chosen action differs between accuracy off and on, capture:

- Off-chosen action and on-chosen action (full `JointAction`/`/choose` representation).
- Score of each, and each one's margin to its own runner-up candidate (already computable from
  existing `CandidateTrace.aggregate_score`/`rank` — no new field needed for this specific piece).
- `event_hit_probability`/`move_accuracy` for every accuracy-uncertain event, read from
  `trace.candidates[i].event_hit_probabilities` for whichever candidate is the off-chosen or
  on-chosen one.
- Exact-branch count vs. cap-fallback count for both candidates — `accuracy_branch_cap_hits` from
  `CandidateTrace` directly (a count of cap-hit forks for that candidate's own line, per §2's
  wiring; exact-branch count is `len(event_hit_probabilities)` as a proxy for how many uncertain
  events were actually resolved for that candidate, not a full leaf count).
- Full diff taxonomy (move/target/switch/protect/other), **with Tera reported as its own explicit
  separate flag**, not folded into a generic "action changed" bucket.

## 6. `room_raw` extraction module — hard requirements

New module (e.g. `showdown_bot/src/showdown_bot/eval/room_raw_replay.py`), mirroring the exact
existing `BattleState.from_log_text` / `merge_request` / `BattleRequest.model_validate` calls the
live client (`gauntlet.py::handle_request`/`_state_for`) already makes — not new resolution logic.

1. **State built strictly from the log prefix up to and including the frame immediately before
   each request** — no frames after the request may be read when constructing that request's
   state. This is a causality requirement: the extractor must walk frames in order and yield
   `(deep_copy_of_state_so_far, parsed_request)` at the exact moment a `|request|{...}` frame is
   reached, before processing anything further in the log.
2. **Deduplicate reconnect/duplicate `|request|` frames** (confirmed real logs can carry these on
   reconnect) — keep only the first/canonical instance per decision point.
3. **Unambiguously determine the hero side.** Verified directly against a real log
   (`data/eval/t4/room_raw_divergent/prefix-idx09-regi-380.log.gz`): a room_raw dump only ever
   captures frames from the client's own connection, so every `|request|` frame in a given log
   belongs to whichever side that client played — readable from the request's own
   `side.id`/`side.name`, cross-checked against the `|player|p{1,2}|<name>|` frames.
4. **Handle `teamPreview`/`forceSwitch`/otherwise-invalid requests separately, not mixed into the
   main accuracy comparison sample.** Confirmed necessary from real data: the very first request
   in the log checked above is a team-preview request. Team-preview and pure-force-switch
   decisions have no move-accuracy content to compare — exclude them from the primary sample,
   report their counts separately.
5. **Fixed seed and stratification rule, pinned before the first accuracy comparison is run** —
   stratify by turn-bucket (early/mid/late, thresholds set from the real corpus's actual 6–21 turn
   range before sampling) crossed with source directory/opponent policy; a fixed RNG seed for
   sample selection, stated in the spec/report, not chosen after a preliminary look at results.
6. **Sample manifest, one row per sampled decision:** source file, battle ID, turn number, side,
   request hash, and log-prefix hash (the hash of exactly the frames used to build that decision's
   state) — full provenance, auditable and reproducible, matching this project's established
   `config_hash`/`movedata_hash` provenance discipline.
7. **Games are clusters, not independent samples.** Multiple decisions from the same game are
   correlated; the sampling scheme must not treat them as independent draws, and every aggregate
   statistic (cap-hit rate, its CI, decision-diff rate) must be computed with game-level
   clustering — bootstrap resamples whole games, not individual decisions.

## 7. Testing / verification approach

- `_evaluate_line_details`/`LineEvaluation`: TDD, mirrors the existing `evaluate_line` test
  patterns from the merged accuracy slice — off-path byte-identical to today's `evaluate_line`
  output, on-path `leaves`/`fork_records`/`fallback_leaves` match what a direct
  `resolve_turn_branches` call on the same inputs produces, tie-averaging case explicitly tested.
- `room_raw_replay`'s extraction module: TDD against one of the real, already-on-disk logs (not a
  synthetic fixture) for at least the causality requirement (state at request N excludes frames
  after N) and the team-preview/force-switch separation — these are the two requirements most
  likely to be silently gotten wrong.
- Gate A and Gate B scripts themselves: not TDD (measurement/report tasks, following the Task 8
  precedent within the merged slice) — real, honest numbers, no fabrication, explicit reporting of
  any cap/sampling/exclusion so nothing is silently dropped.

## 8. Explicitly out of scope

- Materializing the full 05 generalization panel (stays Depth-2 Stage 3's separate blocker).
- Any live server battles or new game generation.
- Fixing `AccuracyDiagnostics.accuracy_required`'s naming mismatch (tracked as a separate,
  small follow-up, not part of this gate).
- Fully closing `docs/ROADMAP.md` P0 item 5 (`LineEvaluation` makes the data reachable; wiring
  `accuracy_diagnostics()` itself into a live trace consumer is still open).
- Any default-on decision, strength claim, or Depth-2 Stage 3 work — all explicitly downstream of
  this gate's results being reviewed, not part of it.
