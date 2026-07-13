# Accuracy Off/On Offline Decision-Diff Gate — Design

**Status:** spec-ready (incorporates 3 rounds of corrections; round 3 fixed two real architecture
errors — an event-discovery bug re-introduced at the diagnostic layer, and an unverified "same
pass" claim — plus 7 smaller precision fixes)
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

**Gate B — real replayed corpus.** `data/eval/t4/rerun/room_raw/{run1,run2,prefix}`,
`data/eval/t4/room_raw_divergent`, `data/eval/t6/room_raw/{run1,run2}`, and
`data/eval/kaggle-validation/room_raw` contain **197 real gzipped Showdown protocol logs** from
past gauntlet runs (turns 6–21, real KOs/switches/damage, opponent policies spanning
`heuristic`/`max_damage`/`greedy_protect`/`simple_heuristic`/`scripted_vgc`). A direct count
against these on-disk files (not an estimate) gives **3038 total `|request|` frames, 197
team-preview, ~66 force-switch, leaving ~2775 plausible move-decision requests** — see §6 for
why this means Gate B can very likely run on the **full corpus**, not a sample. This is real
data, not synthetic — Gate B replays real `(state, request)` pairs through
`heuristic_choose_for_request` with `SHOWDOWN_ACCURACY_MODE` off vs on and compares.

**Gate B's own scope boundary, stated explicitly in the TL;DR of its report:** the corpus's hero
side is only 2 fixed teams (`data/eval/t4/`'s team and `data/eval/t6/`'s team). Gate B is a
**policy/state generality check** (real turns, real damage/KO/switch states, diverse opponent
policies) — it is **not a hero-team generality check**. Do not let the report's language imply
otherwise.

## 2. `LineEvaluation` detail path — exact call-flow, not an assumed one

### 2.1 What the current code actually does (verified against `decision.py`, not assumed)

`evaluate_line()`'s `_one(tb)` closure (`battle/evaluate.py:466-487`) already computes
`leaves, fallback_leaves, fork_records = resolve_turn_branches(...)` internally when
`accuracy_mode` is on, then discards `leaves`/`fork_records`, keeping only the aggregated
`(score, representative_outcome)`.

`decision.py`'s ranking and trace-population code are **already, today, independently of any
change in this gate, two separate call sites** that each invoke `evaluate_line` fresh for the
same `(candidate, opponent-response)` pairs:

- **Ranking** (`score_plan`, `decision.py:403-414` for the K-world path / `:441-459` for the
  single-world path): called once per candidate in `plans`, for every opponent response, to
  produce the scores `pick_best`/`aggregate_scores` rank on. Discards the `TurnOutcome` — keeps
  only `evaluate_line(...)[0]`.
- **Trace population** (`_breakdowns_for`, `decision.py:598-612`): called again, **after**
  ranking has already picked `best_ja`, only for the top-`TOP_K_TRACE_CANDIDATES` candidates
  (`decision.py:657`), over `rep_resps` — the *same* response list structure `score_plan` used
  (`decision.py:596`) — to build `OutcomeBreakdown`s for `CandidateTrace`.
- **Report metrics** (`decision.py:563-567`): a **third**, independent `evaluate_line` call for
  the chosen candidate only, `rollout_horizon=0`, used solely for the human-readable
  incoming/outgoing/gap report line. Untouched by this gate — not part of `CandidateTrace`.

**This means the original claim in round-2 of this spec — "the new trace-population code path
calls `_evaluate_line_details` directly and reads `leaves`/`fork_records`/`fallback_leaves` from
the *same* pass that produced the score — no drift is possible by construction, no duplicate
compute" — is false as written.** `_breakdowns_for`'s call is not, and after this change still
will not be, the same invocation as `score_plan`'s ranking call. That double-evaluation is
pre-existing `decision.py` architecture (trace population always re-scores the top-K post-hoc for
richer per-candidate detail than ranking needs), not something this gate introduces, and fixing
it for real — threading or caching one `LineEvaluation` per `(candidate, response)` from ranking
through to trace population — would mean restructuring `score_plan`'s K-world, single-world, and
depth-2 variants to store results keyed by `(candidate_id, response_index)` and having
`_breakdowns_for` read from that store instead of recomputing. That is a materially larger,
higher-risk change than this gate's telemetry needs, and is **not** part of this design.

### 2.2 What this design actually achieves, and how zero-drift is proven

What `_evaluate_line_details` **does** fix: today, `_breakdowns_for`'s own already-separate call
computes `resolve_turn_branches` internally (via `evaluate_line`) and throws the `leaves`/
`fork_records`/`fallback_leaves` away, keeping only `(score, TurnOutcome)`. Switching
`_breakdowns_for` to call `_evaluate_line_details` directly means **that one call it already
makes** returns the accuracy telemetry too — no *additional* `resolve_turn_branches` invocation is
added on top of what `_breakdowns_for` does today. The pre-existing double-evaluation between
`score_plan` and `_breakdowns_for` is unchanged in count; it just means each of those two
existing, separate calls now has access to full detail when it needs it.

Given `_breakdowns_for`'s call remains a separate invocation from `score_plan`'s, "no drift" is
not an object-identity guarantee — it is a **provable determinism property**: `resolve_turn`,
`resolve_turn_branches`, `_evaluate_line_details` are pure functions of their arguments (`state`,
action lists, `damage_fn`, `field`, `accuracy_mode`, `accuracy_branch_cap`, tie-break) — no hidden
mutable global state, no RNG. Given byte-identical inputs, two separate calls **must** produce
byte-identical `LineEvaluation` results. §7 adds a dedicated regression test
(`test_evaluate_line_details_repeat_call_identical`) that calls `_evaluate_line_details` twice
with identical arguments and asserts every field that participates in scoring or trace population
is equal — turning "no drift by construction" (false) into "no drift, verified by a determinism
test" (true and checked).

### 2.3 `LineEvaluation` and the event-union fix (round-3 correction #1: the discovery bug)

```python
@dataclass
class AccuracyEventDetail:
    attacker: SlotId
    target: SlotId
    move_id: str
    hit_probability: float


@dataclass
class LineEvaluation:
    score: float
    representative_outcome: TurnOutcome
    leaves: list[tuple[float, TurnOutcome]] | None = None    # None when accuracy_mode is off
    fork_records: list[ForkRecord] | None = None              # None when accuracy_mode is off
    fallback_leaves: int = 0
    accuracy_events: list[AccuracyEventDetail] = field(default_factory=list)  # [] when off
```

Round 2 of this spec populated the (then dict-shaped) event field from
`LineEvaluation.leaves[0][1].attempted_hits` — the all-hit representative leaf only. **This is
exactly the one-shot-discovery bug `resolve_turn_branches` was built to fix, reintroduced one
layer up.** `resolve.py:363-367`'s own docstring states it precisely: an action that never reaches
`apply_hit` in one branch's resolve (because an earlier hit/miss decision changed who's alive, or
who gets redirected onto) is invisible to a list built from that branch alone. `leaves[0]` is one
branch among many — reading only it silently drops every accuracy event that only becomes
attempted in a miss-branch, which is precisely the KO-dependent/redirection-dependent case the
merged slice's Task 4 regression test exists to catch.

**Fix: iterate the full `leaves` list** (already the complete, flat set of every leaf across the
whole tree — confirmed from `resolve_turn_branches`'s own implementation, `resolve.py:429`:
`expand` returns `hit_leaves + miss_leaves`, concatenating both branches at every fork, so the
top-level `leaves = expand(...)` genuinely contains every leaf, not just the spine to `leaves[0]`)
and union every leaf's `attempted_hits`, deduplicated by `(attacker, target, move_id)`:

```python
def _accuracy_events_from_leaves(
    actions: list[PlannedAction],
    state: BattleState,
    leaves: list[tuple[float, TurnOutcome]],
    field: FieldState | None,
) -> list[AccuracyEventDetail]:
    actions_by_key = {a.key: a for a in actions}
    seen: dict[tuple[SlotId, SlotId, str], float] = {}
    for _weight, out in leaves:
        for ah in out.attempted_hits:
            key3 = (ah.attacker, ah.target, ah.move_id)
            if key3 in seen:
                continue
            attacker_action = actions_by_key.get(ah.attacker)
            if attacker_action is None or attacker_action.move is None:
                continue
            attacker_mon = state.sides.get(ah.attacker[0], {}).get(ah.attacker[1])
            target_mon = state.sides.get(ah.target[0], {}).get(ah.target[1])
            if attacker_mon is None or target_mon is None:
                continue
            p = hit_probability(attacker_action.move, attacker_mon, target_mon, field)
            if p is None or p >= 1.0:
                continue  # guaranteed-hit moves aren't accuracy-uncertain events
            seen[key3] = p
    return [AccuracyEventDetail(a, t, m, p) for (a, t, m), p in seen.items()]
```

Deduplication by `(attacker, target, move_id)` is safe **within one `resolve_turn_branches`
call**: `hit_probability(...)` reads the attacker/target `PokemonState` from the original,
pre-turn `state` (not the in-turn-mutated `cur_frac`), so the same `(attacker, target, move_id)`
triple yields the same probability regardless of which branch discovers it first — this is a
property of `hit_probability`'s actual implementation (`resolve.py:408`), not an assumption. This
adds one extra `hit_probability` call per **distinct** event (cheap, pure — the same function
`expand()` already calls internally) — **no additional `resolve_turn`/`resolve_turn_branches`
calls**, so the expensive part of the work does not grow.

`resolve.py` itself is **not modified** by this design — `resolve_turn_branches`'s existing,
already-merged, already-tested 3-tuple return contract (`leaves, fallback_leaves, fork_records`)
stays exactly as-is. `_accuracy_events_from_leaves` is new code in `evaluate.py` that consumes
that contract from the outside, keeping the blast radius to one file plus its call sites.

`_evaluate_line_details`:

```python
def _evaluate_line_details(
    state, my_actions, opp_actions, damage_fn, *,
    our_side, weights=None, field=None, rollout_horizon=0, rollout_gamma=0.7,
    endgame=False, fast_board=False, accuracy_mode=False, accuracy_branch_cap=4,
    _force_tie_break=None,
) -> LineEvaluation:
    field = field or state.field
    all_actions = my_actions + opp_actions

    def _scored(out: TurnOutcome) -> float:
        sc = score_outcome(out, our_side, weights, endgame=endgame, fast_board=fast_board)
        if rollout_horizon > 0:
            sc += _rollout_value(
                state, all_actions, out, our_side, weights or EvalWeights(),
                field, rollout_horizon, rollout_gamma,
            )
        return sc

    def _one(tb: str) -> LineEvaluation:
        if not accuracy_mode:
            out = resolve_turn(state, all_actions, damage_fn, our_side=our_side, field=field, tie_break=tb)
            return LineEvaluation(score=_scored(out), representative_outcome=out)
        leaves, fallback_leaves, fork_records = resolve_turn_branches(
            state, all_actions, damage_fn, our_side=our_side, field=field,
            tie_break=tb, branch_cap=accuracy_branch_cap,
        )
        total = sum(w * _scored(out) for w, out in leaves)
        representative = leaves[0][1]
        representative.accuracy_branch_cap_hits = fallback_leaves  # unchanged existing side effect
        events = _accuracy_events_from_leaves(all_actions, state, leaves, field)
        return LineEvaluation(
            score=total, representative_outcome=representative, leaves=leaves,
            fork_records=fork_records, fallback_leaves=fallback_leaves, accuracy_events=events,
        )

    if _force_tie_break is not None:
        return _one(_force_tie_break)
    if _has_genuine_tie(all_actions, field):
        d_first = _one("ours_first")
        d_last = _one("ours_last")
        # Matches evaluate_line's existing tie-EV convention exactly: only ours_last's
        # outcome/leaves/events survive into the result; ours_first only contributes its score.
        return LineEvaluation(
            score=0.5 * (d_first.score + d_last.score),
            representative_outcome=d_last.representative_outcome,
            leaves=d_last.leaves, fork_records=d_last.fork_records,
            fallback_leaves=d_last.fallback_leaves, accuracy_events=d_last.accuracy_events,
        )
    return _one("ours_last")


def evaluate_line(...) -> tuple[float, TurnOutcome]:
    d = _evaluate_line_details(...)
    return d.score, d.representative_outcome
```

Every existing `evaluate_line` call site (all live sites in `decision.py`) needs zero changes —
same signature, same return shape, byte-identical behavior.

### 2.4 Trace wiring (round-3 correction #2: per-response granularity, not a flat dict)

Round 2's `CandidateTrace.event_hit_probabilities: dict[tuple[SlotId, SlotId], float]` had two
problems beyond the discovery bug: (a) a candidate's `aggregate_score` is computed over **multiple
opponent responses** (`score_vector`/`outcome_breakdowns` are already per-response parallel lists
— `CandidateTrace`, `decision_trace.py:46-47`), so accuracy telemetry needs the same per-response
shape, not one flattened dict that silently overwrites entries across responses; (b) dict keys
lose path/response identity needed to tell two genuinely different events apart.

```python
@dataclass
class AccuracyEventTrace:
    attacker: SlotId
    target: SlotId
    move_id: str
    hit_probability: float
    response_index: int  # index into rep_resps / DecisionTrace.opponent_responses


@dataclass
class AccuracyResponseDetail:
    accuracy_leaf_count: int         # len(leaves) for this (candidate, response) -- real branch count
    accuracy_event_count: int        # len(events) -- distinct uncertain events, NOT a leaf count
    accuracy_branch_cap_hits: int    # fallback_leaves for this (candidate, response)
    events: list[AccuracyEventTrace]


@dataclass
class CandidateTrace:
    # ...existing fields unchanged...
    accuracy_details: list[AccuracyResponseDetail] = field(default_factory=list)  # parallel to
    # score_vector/outcome_breakdowns, one entry per opponent response; [] when accuracy_mode off
```

`accuracy_branch_cap_hits` already equals the capped-leaf count by construction (every `expand()`
call that hits the cap immediately returns exactly one leaf — `resolve.py:417-419`), so no
separate "fallback leaf count" field is added; `AccuracyResponseDetail.accuracy_branch_cap_hits`
already is that count.

`decision.py`'s `_breakdowns_for` (the one, pre-existing, already-separate call site described in
§2.1) is modified to build both outputs from the same `_evaluate_line_details` call it already
makes per response:

```python
def _breakdowns_for(plan):
    out = []
    acc_details = []
    for ri, ra in enumerate(rep_resps):
        d = _evaluate_line_details(
            state, plan, ra, model.damage_fn, our_side=our_side,
            weights=weights, field=state.field, rollout_horizon=0,
            endgame=endgame, fast_board=fast_board,
            accuracy_mode=accuracy_mode, accuracy_branch_cap=accuracy_branch_cap,
        )
        out.append(
            score_outcome_with_breakdown(
                d.representative_outcome, our_side, weights, endgame=endgame, fast_board=fast_board
            )[1]
        )
        acc_details.append(AccuracyResponseDetail(
            accuracy_leaf_count=len(d.leaves) if d.leaves is not None else 0,
            accuracy_event_count=len(d.accuracy_events),
            accuracy_branch_cap_hits=d.fallback_leaves,
            events=[
                AccuracyEventTrace(e.attacker, e.target, e.move_id, e.hit_probability, response_index=ri)
                for e in d.accuracy_events
            ],
        ))
    return out, acc_details
```

The caller (`decision.py:657-668`) unpacks `bds, acc_details = _breakdowns_for(plans[ja])` and
passes `accuracy_details=acc_details` into `CandidateTrace(...)`.

This closes part of `docs/ROADMAP.md`'s P0 item 5 (`AccuracyDiagnostics`→`DecisionTrace`) as a
side effect, though it does not close the whole item — `accuracy_diagnostics()` itself (the
already-merged `ko_probability`/`survival_probability`/`accuracy_required`/`miss_punish_value`
function) still isn't called from live decision code after this; `LineEvaluation` just makes the
raw ingredients reachable without an architecture that risks drift.

## 3. Terminology correction (real finding, not just gate-report hygiene)

The already-merged `AccuracyDiagnostics.accuracy_required` field (`battle/evaluate.py:376,
414-426`) is misnamed: its docstring/spec description calls it "a derived threshold above which a
risky line becomes advantageous," but the actual Task 6 implementation just assigns
`hit_probability(attacker_action.move, attacker_mon, target_mon, field)`'s raw value to it — no
threshold is derived anywhere. This is a real, pre-existing naming bug in the merged slice, caught
while scoping this gate, not a property of this gate's own design. (It also shares round 2's
`leaves[0]`-only discovery-bug pattern at `evaluate.py:415` — out of scope to fix here, noted for
the separate follow-up.)

**This gate does not use or touch `AccuracyDiagnostics.accuracy_required`.** Its own new types are
named for what they actually are: `AccuracyEventDetail`/`AccuracyEventTrace.hit_probability` (the
move's computed hit probability for a specific attacker/target/field/response,
`hit_probability(...)`'s raw return) — `move_accuracy` (the move's base accuracy value,
`MoveMeta.accuracy`) is referenced only where the distinction between base accuracy and the
stage/weather-adjusted probability matters in report prose, not as a new field. Neither name
implies a derived break-even threshold. The `AccuracyDiagnostics.accuracy_required` naming
mismatch itself is flagged as a small separate follow-up (rename or fix the field to match its
docstring) — tracked, not fixed here, and not blocking this gate.

## 4. Acceptance rules, pinned before any run

- **No exceptions, NaNs, or invalid actions** across the full replayed sample (Gate A and B).
- **Off-path byte-identical**, re-confirmed empirically on the real corpus (not just trusted from
  the merged slice's own unit/integration tests) — same chosen action, same score, for every
  replayed decision with `SHOWDOWN_ACCURACY_MODE` unset vs. the identical decision computed
  through the same code path with the flag forced off. This check runs **twice**, for two
  different purposes — see §7's frozen-baseline requirement: (1) unset-vs-explicit-off on
  post-refactor code (an env-parser unit test), and (2) post-refactor-vs-pre-refactor on a frozen
  artifact (a regression test that a refactor bug can't hide behind, because both unset and
  explicit-off route through the *same* new wrapper post-refactor).
- **Chosen-line cap-hit rate — the precise metric that matters, pinned exactly:**
  - **Denominator:** number of *replayed decisions* (not candidates, not individual
    `resolve_turn_branches` calls).
  - **Numerator:** a decision counts if, for the chosen candidate's `accuracy_details: list[
    AccuracyResponseDetail]` (one entry per opponent response actually scored — §2.4), **any**
    response's `accuracy_branch_cap_hits >= 1` — OR-across-responses, the conservative rule
    appropriate for a gate whose job is to catch risk, not average it away. Additionally report,
    per decision: `sum(accuracy_branch_cap_hits across responses)` and `max(...)`, so the headline
    any-triggered rate doesn't hide how concentrated or spread cap-hits are across responses.
  - Report numerator, denominator, the resulting rate, **and a game-clustered bootstrap CI**
    (resample at the game level, matching §6's stratification and this project's established
    game-clustered-bootstrap convention from the value-calibration work) — not a naive
    per-decision CI, since multiple decisions from the same game are correlated, not independent.
  - **Verdict bands, pinned now, not chosen after seeing results, and dependent on BOTH the point
    estimate and the confidence interval — not the point estimate alone:**
    - **PASS:** point estimate ≤5% **and** the game-clustered bootstrap CI's upper bound ≤5%.
    - **INCONCLUSIVE:** point estimate ≤5% but the CI upper bound >5% — the sample is too
      small/noisy to license a PASS. Report this honestly as a power limitation, not a soft pass.
      Do not loosen the 5% threshold after seeing this outcome, whichever direction it points.
    - **FAIL:** point estimate >5%, regardless of CI width.
    - This mirrors the already-learned lesson (`teacher-agreement-winrate-inversion`, this
      project's memory) that a point estimate alone, without respecting sampling uncertainty, can
      produce a false sense of confidence.
    - For an eventual production default-on decision (separate, later, not this gate), the target
      should sit meaningfully closer to 0% than this gate's 5% bar — 5% is this diagnostic gate's
      threshold, not the production bar.
- **Latency within the already-pinned budget** (`reports/2026-07-12-accuracy-slice-latency-gate.md`'s
  p95×5-scaled 1000ms gate at `branch_cap=4`) — re-verified on Gate B's real corpus, not assumed
  to transfer from the one synthetic board Task 8 measured. If Gate B's trace-enabled path is used
  for any latency number, that number must explicitly include the trace-detail overhead (§6) and
  be reported as a distinct, separately-labeled figure from the non-traced production latency.
- **Every decision diff must be reproducible** (deterministic re-run, same inputs → same result)
  **and have a mechanically plausible accuracy cause** — traceable to a specific
  `AccuracyEventTrace` entry for one of the diffing candidates, not an unexplained score wobble. A
  diff that can't be explained this way is a red flag to investigate separately, not to silently
  fold into the accuracy-effect count.

## 5. Per-diff capture schema (both gates)

For every decision where the chosen action differs between accuracy off and on, capture:

- Off-chosen action and on-chosen action (full `JointAction`/`/choose` representation).
- Score of each candidate, and each one's margin to its own runner-up. Selected by **`rank`
  field**, not list position: `next(c for c in trace.candidates if c.rank == 0)` /
  `rank == 1` — not `trace.candidates[0]`/`[1]`. `decision.py`'s current candidate-construction
  (`scored.sort(key=lambda t: (-t[2], ...))` then `enumerate(scored[:TOP_K_TRACE_CANDIDATES])` at
  `decision.py:655-657`) does today build `candidates` already in rank order, but the gate script
  must not depend on that being true by accident — §7 adds a regression test pinning it.
  **Off-run and on-run candidates for the "same" nominal action are paired by `candidate_id`**
  (`_label_ja(req, ja)`, `decision.py:233-246` — confirmed a pure function of `req`+`ja` only,
  unaffected by `accuracy_mode`, since legal-action enumeration doesn't depend on accuracy
  scoring), never by rank or list position: `accuracy_mode` changes scores, which can reorder or
  reshuffle which candidates make the top-`TOP_K_TRACE_CANDIDATES` cut, so rank/position is a
  valid *within-run* key but not a stable *cross-run* key. When a `candidate_id` present in one
  run's top-K is absent from the other's, report it explicitly as "left/entered top-K" rather than
  silently excluding it from the comparison denominator.
- `AccuracyEventTrace` entries (`attacker`, `target`, `move_id`, `hit_probability`,
  `response_index`) for every accuracy-uncertain event, read from
  `trace.candidates[i].accuracy_details[*].events` for whichever candidate is the off-chosen or
  on-chosen one — the full per-response list, not a flattened dict (§2.4).
- Per-candidate `accuracy_leaf_count` (real branch count), `accuracy_event_count` (distinct
  uncertain-event count — **not** the same quantity as leaf count: two independent binary events
  can produce 4 leaves; KO/Protect pruning can produce fewer), and `accuracy_branch_cap_hits`
  (already the capped-leaf count by construction) — all read directly off
  `CandidateTrace.accuracy_details`, summed/maxed across responses per §4's numerator rule.
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
5. **Full-corpus-first sampling policy, checked empirically, not assumed:**
   - A direct count against all 197 on-disk logs gives 3038 total `|request|` frames — 197
     team-preview, ~66 force-switch (regex-approximate; the extraction module's real parser filters
     these precisely) — leaving **~2775 plausible move-decision requests**. `run1`/`run2` within
     `t4` and `t6` were confirmed to be genuinely distinct battles (different `regi-NNN` battle
     IDs, not duplicate re-runs of the same games), so no double-counting risk from using both.
   - At the Task 8 latency benchmark's per-decision cost with accuracy on, the full corpus × 2
     (off + on) is on the order of 15-20 minutes of wall-clock compute — plausibly well within a
     normal local-run budget. **Use the full corpus as the primary sample.** Before committing to
     this, run a small timed dry-run (e.g. 50 decisions) and extrapolate; only fall back to
     sub-sampling if the extrapolated full-corpus runtime is actually prohibitive — measured, not
     assumed either way.
   - **If sampling is forced (fallback only), pin these parameters now, not after a preliminary
     look at results:**
     - Sampling unit is the **game** (log file), not the individual decision — draw a fixed number
       of games per stratum, then use every suitable (non-team-preview, non-force-switch) decision
       from each drawn game. Independent per-decision draws are not used, ever, at any sample size.
     - Strata: source directory × turn-tercile, where turn-tercile is computed **per game,
       relative to that game's own turn range** (first/middle/last third of that specific game's
       own `[min_turn, max_turn]` span), not a fixed absolute cutoff — game lengths vary
       meaningfully across directories (t6 games run shorter than t4's), so a fixed absolute
       threshold would put an entire short game into a single bucket.
     - RNG seed: `20260713`, stated here, not re-rolled after a preliminary look at results.
     - Minimum stratum size: strata with fewer than 3 games include all of them (no further
       reduction) and are flagged explicitly in the report as under-powered, rather than silently
       treated as adequately sampled.
6. **Sample/usage manifest, one row per decision used** (whether from the full corpus or a
   fallback sample): source file, battle ID, turn number, side, request hash, and log-prefix hash
   (the hash of exactly the frames used to build that decision's state) — full provenance,
   auditable and reproducible, matching this project's established `config_hash`/`movedata_hash`
   provenance discipline.
7. **Games are clusters, not independent samples.** Whether the run uses the full corpus or a
   fallback sample, multiple decisions from the same game are correlated — every aggregate
   statistic (cap-hit rate, its CI, decision-diff rate) must be computed with game-level
   clustering, bootstrap resampling whole games, not individual decisions.
8. **Small hermetic fixtures, in addition to the real-log regression test.** The one real log used
   for TDD (§7) is good end-to-end coverage but hard to control for specific edge cases. Add
   hand-constructed, small, synthetic room_raw-format fixtures exercising, as dedicated unit tests:
   - a duplicate/reconnect `|request|` frame pair (exercises requirement 2),
   - a force-switch request mid-log, not just team-preview (exercises requirement 4's "otherwise
     invalid" branch on a decision that isn't the very first one),
   - a case where reading one frame too many would observably change the extracted state (a
     scenario where getting the causality boundary in requirement 1 wrong produces a *detectably
     different, wrong* state, not just a state that happens to look the same either way) — this is
     the requirement most likely to be silently gotten wrong and least covered by real-log
     spot-checks alone.

## 7. Testing / verification approach

- `_evaluate_line_details`/`LineEvaluation`: TDD, mirrors the existing `evaluate_line` test
  patterns from the merged accuracy slice.
  - Off-path byte-identical to today's `evaluate_line` output.
  - On-path `leaves`/`fork_records`/`fallback_leaves` match what a direct `resolve_turn_branches`
    call on the same inputs produces; tie-averaging case explicitly tested (only `ours_last`'s
    `leaves`/`fork_records`/`accuracy_events` survive into the result, matching §2.3's code).
  - `test_accuracy_events_use_full_leaf_union`: the regression test for round-3's discovery-bug
    fix — a scripted scenario (same shape as the merged slice's Task 4 KO-dependent regression
    test) where an event is only attempted in a miss-branch, asserting it **is** present in
    `LineEvaluation.accuracy_events` even though it is absent from `leaves[0][1].attempted_hits`.
  - `test_evaluate_line_details_repeat_call_identical` (§2.2): call `_evaluate_line_details` twice
    with byte-identical arguments and assert the two `LineEvaluation` results are equal on every
    field that participates in scoring or trace population — the determinism proof that replaces
    the false "same pass" claim.
- **Frozen pre-refactor baseline (prerequisite step, before `_evaluate_line_details` lands):**
  unset-vs-explicit-off comparison alone is insufficient once `evaluate_line` becomes a wrapper
  around `_evaluate_line_details` — both paths then route through the *same new code*, so a bug in
  the wrapper affects both equally and the two stay "equal to each other" while both silently
  diverge from pre-refactor behavior. Before the refactor lands: run the **current, unmodified**
  `heuristic_choose_for_request`/`evaluate_line` against a representative slice of the Gate B
  corpus (recommend: one stratum from each turn-tercile × source-directory cell, or the full
  corpus if runtime allows — see §6) and freeze the results (chosen action, score, request hash,
  prefix hash) to a committed artifact. After the refactor, replay the identical slice and diff
  against this frozen artifact — any difference is a refactor regression, full stop, independent
  of the unset-vs-off env-parser test (which stays, as a narrower, different check: does env-var
  parsing itself correctly treat unset/`"0"`/`"false"` as equivalent — a unit-level concern, not a
  behavioral-regression one).
- `test_decision_trace_candidates_rank_sorted` (§5's point-8 fix): asserts
  `[c.rank for c in trace.candidates] == list(range(len(trace.candidates)))` on a real decision
  trace, so any future change to `decision.py`'s candidate-construction code that breaks this
  ordering is caught immediately rather than silently miscompared by the gate script.
- `room_raw_replay`'s extraction module: TDD against one of the real, already-on-disk logs for the
  causality requirement (state at request N excludes frames after N) and the
  team-preview/force-switch separation, **plus** the small hermetic fixtures from §6 point 8 for
  the reconnect-duplicate, mid-log force-switch, and causality-boundary-detectability cases the
  one real log doesn't reliably exercise.
- Gate A and Gate B scripts themselves: not TDD (measurement/report tasks, following the Task 8
  precedent within the merged slice) — real, honest numbers, no fabrication, explicit reporting of
  any cap/sampling/exclusion so nothing is silently dropped.

## 8. Explicitly out of scope

- Materializing the full 05 generalization panel (stays Depth-2 Stage 3's separate blocker).
- Any live server battles or new game generation.
- Fixing `AccuracyDiagnostics.accuracy_required`'s naming mismatch or its own `leaves[0]`-only
  discovery-bug pattern (tracked as a separate, small follow-up, not part of this gate).
- Fully closing `docs/ROADMAP.md` P0 item 5 (`LineEvaluation` makes the data reachable; wiring
  `accuracy_diagnostics()` itself into a live trace consumer is still open).
- Actually caching/threading `LineEvaluation` from ranking (`score_plan`) through to trace
  population (`_breakdowns_for`) to eliminate their pre-existing double-evaluation — a real,
  larger refactor identified while scoping this gate (§2.1), not part of it.
- Any default-on decision, strength claim, or Depth-2 Stage 3 work — all explicitly downstream of
  this gate's results being reviewed, not part of it.
