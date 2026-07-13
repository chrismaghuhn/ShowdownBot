# Accuracy Off/On Offline Decision-Diff Gate — Design

**Status:** spec-ready (incorporates 5 rounds of corrections; round 3 fixed two real architecture
errors — an event-discovery bug re-introduced at the diagnostic layer, and an unverified "same
pass" claim; round 4 fixed a tie-averaging telemetry gap, a degenerate-bootstrap statistical gap,
and 2 smaller precision fixes; round 5 fixed a real corpus-independence error — the ~197-file
corpus is confirmed, not assumed, to contain massive reproduction-rerun duplication, corrected to
a provisional ~85-unique-battle count pending a systematic dedup step — plus removed an
ill-defined game-level sampling stratum)
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
`data/eval/kaggle-validation/room_raw` contain **197 real gzipped Showdown protocol log files**
from past gauntlet runs (turns 6–21, real KOs/switches/damage, opponent policies spanning
`heuristic`/`max_damage`/`greedy_protect`/`simple_heuristic`/`scripted_vgc`). This is real data,
not synthetic — Gate B replays real `(state, request)` pairs through `heuristic_choose_for_request`
with `SHOWDOWN_ACCURACY_MODE` off vs on and compares.

**197 files is not 197 independent battles — confirmed, not assumed, and material to every
statistic in this design.** Reading the actual provenance reports for these runs
(`reports/2026-07-10-2b35-T4-smoke.md`, the T6 heldout-baseline report, and
`data/eval/kaggle-validation/provenance.json`) shows `t4/rerun/room_raw/run2` is an explicit
**reproduction re-run of the identical 51-seed schedule** as `run1` (same `schedule_hash
a7f000867fdfbde0`; seed logs confirmed byte-identical at 48/51 indices, the other 3 a
since-fixed determinism bug — not new scenarios). `t4/rerun/room_raw/prefix` (10 files) re-runs
the **first 10 rows of that same schedule**. `t4/room_raw_divergent` (7 files) are **literal
copies** of 7 already-counted battles from `run1`/`run2`/`prefix` (its own README names them:
`run1`/`run2` idx 09/19/48 + `prefix` idx 09). `kaggle-validation/room_raw` (10 files) replays
**the same schedule as `t4/rerun/room_raw/prefix`** again, verified directly by comparing seed
values in `kaggle-validation/seeds.jsonl` against `t4/rerun/t4rerun-prefix-seedlog.jsonl` (its own
`provenance.json` says as much: purpose was to prove Kaggle-generated logs match this exact local
reference). `t6/room_raw/run2` is, the same way, a confirmed reproduction re-run of `run1`'s
34-seed schedule (`schedule_hash 3076a71aa6841c8c`, seed logs byte-identical at all 34 indices).

**Net effect: at most two genuinely independent seed schedules exist across all 197 files** —
`t4`'s 51 seeds (canonically `run1`) and `t6`'s 34 seeds (canonically `run1`) — giving a
**provisional G ≈ 85 unique battles**, not 197. This number is provisional, not final: it is
strong directional evidence from reading committed provenance manifests, not yet the output of
the systematic dedup step §6 requires before Gate B runs. Every "~2775 decisions" / "197 games" /
"1.5% zero-event bound" figure anywhere in an earlier round of this spec was computed against the
wrong denominator and must be treated as superseded by §6's corrected, dedup-first numbers.

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

### 2.3 `LineEvaluation`: the event-union fix (round-3) and the tie-averaging merge (round-4)

```python
@dataclass
class AccuracyEventDetail:
    attacker: SlotId
    target: SlotId
    move_id: str
    hit_probability: float
    tie_order: str  # "ours_first" | "ours_last" -- which evaluated tie ordering discovered this


@dataclass
class TieOrderEvaluation:
    """One evaluated tie ordering's own accuracy telemetry (round-4 fix, see below)."""
    tie_order: str            # "ours_first" | "ours_last"
    weight: float              # 0.5/0.5 for a genuine tie; 1.0 when there is no tie
    accuracy_leaf_count: int
    accuracy_branch_cap_hits: int
    events_complete: bool      # accuracy_branch_cap_hits == 0 for THIS ordering alone


@dataclass
class LineEvaluation:
    score: float
    representative_outcome: TurnOutcome
    leaves: list[tuple[float, TurnOutcome]] | None = None    # None when accuracy_mode is off;
    # d_last's own tree when tied -- unchanged "representative" convention, NOT tie-merged.
    fork_records: list[ForkRecord] | None = None              # None when accuracy_mode is off;
    # same d_last-only convention as `leaves` -- informational (ko_probability/miss_punish_value
    # inputs), not safety-gating, so it is deliberately NOT part of the round-4 tie-merge fix.
    fallback_leaves: int = 0   # SUM across all evaluated tie orderings (0, 1, or 2 of them) --
    # a raw work/cap-hit COUNT, not a probability-weighted rate. When tied, this is NOT the same
    # quantity as `representative_outcome.accuracy_branch_cap_hits` (round-4 fix below) -- that field keeps
    # its existing merged-slice meaning (d_last's own count only); THIS field is the new,
    # safety-relevant, tie-merged count. Callers needing the tie-merged number must read this
    # field, not the TurnOutcome-embedded one.
    accuracy_events: list[AccuracyEventDetail] = field(default_factory=list)  # UNION across all
    # evaluated tie orderings, deduplicated by (attacker, target, move_id, tie_order) -- an event
    # only reachable under one specific tie ordering stays visible even though the other
    # ordering's tree is what `leaves`/`fork_records` reflect.
    tie_order_details: list[TieOrderEvaluation] = field(default_factory=list)  # one entry (no
    # tie / forced) or two entries (genuine tie), always summing to `fallback_leaves` and unioning
    # to `accuracy_events` -- exposed for per-ordering explainability in the diff report.
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
    tie_order: str,
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
    return [AccuracyEventDetail(a, t, m, p, tie_order) for (a, t, m), p in seen.items()]
```

Deduplication by `(attacker, target, move_id)` is safe **within one `resolve_turn_branches`
call**: `hit_probability(...)` reads the attacker/target `PokemonState` from the original,
pre-turn `state` (not the in-turn-mutated `cur_frac`), so the same `(attacker, target, move_id)`
triple yields the same probability regardless of which branch discovers it first — this is a
property of `hit_probability`'s actual implementation (`resolve.py:408`), not an assumption. This
adds one extra `hit_probability` call per **distinct** event (cheap, pure — the same function
`expand()` already calls internally) — **no additional `resolve_turn`/`resolve_turn_branches`
calls**, so the expensive part of the work does not grow. `_accuracy_events_from_leaves` does
**not** dedupe across tie orderings — that happens (deliberately, as a union not a further
dedup) at the tie-merge step below, since `tie_order` is part of an event's exported identity.

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
        events = _accuracy_events_from_leaves(all_actions, state, leaves, field, tie_order=tb)
        return LineEvaluation(
            score=total, representative_outcome=representative, leaves=leaves,
            fork_records=fork_records, fallback_leaves=fallback_leaves, accuracy_events=events,
            tie_order_details=[TieOrderEvaluation(
                tie_order=tb, weight=1.0, accuracy_leaf_count=len(leaves),
                accuracy_branch_cap_hits=fallback_leaves, events_complete=(fallback_leaves == 0),
            )],
        )

    if _force_tie_break is not None:
        return _one(_force_tie_break)
    if _has_genuine_tie(all_actions, field):
        d_first = _one("ours_first")
        d_last = _one("ours_last")
        # Round-4 fix: the score is a genuine 50/50 blend of BOTH orderings, so a
        # cap-hit or event visible only under ours_first must not disappear from the
        # telemetry just because only ours_last is kept as the representative outcome.
        # representative_outcome/leaves/fork_records: UNCHANGED convention, d_last-only --
        # these are informational trees (ko_probability/miss_punish_value inputs), not
        # safety-gating, so they deliberately stay exactly as before this fix.
        # fallback_leaves/accuracy_events: conservatively merged (summed / unioned) across
        # BOTH evaluated orderings -- these ARE safety-gating (§4's cap-hit rate).
        return LineEvaluation(
            score=0.5 * (d_first.score + d_last.score),
            representative_outcome=d_last.representative_outcome,
            leaves=d_last.leaves, fork_records=d_last.fork_records,
            fallback_leaves=d_first.fallback_leaves + d_last.fallback_leaves,
            accuracy_events=d_first.accuracy_events + d_last.accuracy_events,
            tie_order_details=[
                TieOrderEvaluation(
                    tie_order="ours_first", weight=0.5,
                    accuracy_leaf_count=len(d_first.leaves) if d_first.leaves else 0,
                    accuracy_branch_cap_hits=d_first.fallback_leaves,
                    events_complete=(d_first.fallback_leaves == 0),
                ),
                TieOrderEvaluation(
                    tie_order="ours_last", weight=0.5,
                    accuracy_leaf_count=len(d_last.leaves) if d_last.leaves else 0,
                    accuracy_branch_cap_hits=d_last.fallback_leaves,
                    events_complete=(d_last.fallback_leaves == 0),
                ),
            ],
        )
    return _one("ours_last")


def evaluate_line(...) -> tuple[float, TurnOutcome]:
    d = _evaluate_line_details(...)
    return d.score, d.representative_outcome
```

Every existing `evaluate_line` call site (all live sites in `decision.py`) needs zero changes —
same signature, same return shape, byte-identical behavior (`representative_outcome` is untouched
by the round-4 tie-merge fix, so `evaluate_line`'s own return value is unaffected).

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
    tie_order: str        # "ours_first" | "ours_last" -- which evaluated ordering saw this


@dataclass
class AccuracyTieOrderTrace:
    tie_order: str
    weight: float
    accuracy_leaf_count: int
    accuracy_branch_cap_hits: int
    events_complete: bool


@dataclass
class AccuracyResponseDetail:
    accuracy_leaf_count: int         # SUM across this response's evaluated tie orderings --
    # a raw branch-count total across BOTH orderings when tied (not a single tree's leaf count;
    # see `tie_orders` below for the per-ordering breakdown).
    accuracy_event_count: int        # len(events) -- distinct uncertain events (unioned across
    # tie orderings), NOT a leaf count.
    accuracy_branch_cap_hits: int    # SUM across this response's evaluated tie orderings -- the
    # safety-relevant quantity: >= 1 if EITHER evaluated ordering capped, since both orderings
    # genuinely contributed to the score whenever this response was scored under a tie.
    events_complete: bool            # accuracy_branch_cap_hits == 0 -- False means the exported
    # `events` list is a KNOWN-PARTIAL view (branch_cap truncated discovery in at least one
    # evaluated tie ordering) -- see §4 and §5 for how the diff report must handle this.
    tie_orders: list[AccuracyTieOrderTrace]  # one entry (no tie) or two (genuine tie)
    events: list[AccuracyEventTrace]         # union across tie orderings, each tagged tie_order


@dataclass
class CandidateTrace:
    # ...existing fields unchanged...
    accuracy_details: list[AccuracyResponseDetail] = field(default_factory=list)  # parallel to
    # score_vector/outcome_breakdowns, one entry per opponent response; [] when accuracy_mode off
```

`decision.py`'s `_breakdowns_for` (the one, pre-existing, already-separate call site described in
§2.1) is modified to build both outputs from the same `_evaluate_line_details` call it already
makes per response — `LineEvaluation`'s own `fallback_leaves`/`accuracy_events`/
`tie_order_details` are already tie-merged (§2.3), so `_breakdowns_for` just copies them across,
no additional tie-handling logic needed here:

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
            accuracy_leaf_count=sum(t.accuracy_leaf_count for t in d.tie_order_details),
            accuracy_event_count=len(d.accuracy_events),
            accuracy_branch_cap_hits=d.fallback_leaves,
            events_complete=(d.fallback_leaves == 0),
            tie_orders=[
                AccuracyTieOrderTrace(
                    t.tie_order, t.weight, t.accuracy_leaf_count,
                    t.accuracy_branch_cap_hits, t.events_complete,
                )
                for t in d.tie_order_details
            ],
            events=[
                AccuracyEventTrace(
                    e.attacker, e.target, e.move_id, e.hit_probability,
                    response_index=ri, tie_order=e.tie_order,
                )
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
    (resample at the *deduplicated* game level, §6, matching this project's established
    game-clustered-bootstrap convention from the value-calibration work) — not a naive
    per-decision CI, since multiple decisions from the same game are correlated, not independent.
    **Pinned bootstrap parameters, not chosen after seeing results:** `B = 10,000` resamples,
    one-sided 95% upper bound (the 95th percentile of the resampled rate distribution — not the
    97.5th; a two-sided CI's upper endpoint is a different, more conservative quantity than a
    proper one-sided bound, and only the upper bound is used for the PASS decision), a dedicated
    RNG stream seeded `20260713` (the same numeric seed as §6's sampling seed, but instantiated as
    a separate generator for this distinct purpose — sampling which games to use, and bootstrap
    resampling from the already-fixed collected data, must not share one RNG stream).
  - **Degenerate zero-event case, pinned now because a plain cluster bootstrap fails silently
    here:** if the observed chosen-line cap-hit numerator is exactly `0` across the *entire*
    replayed sample, every possible bootstrap resample can only ever redraw from all-zero games —
    the percentile bootstrap distribution is a point mass at `0`, so its "upper bound" is `0` by
    construction, not because the true rate is provably `0`. **This degenerate bootstrap number
    must not be reported as evidence of a PASS.** Report it anyway, explicitly labeled
    `[0%, 0%] (degenerate — not an upper bound; see game-level bound below)`, for format
    consistency across runs, and additionally compute a real, non-degenerate bound: define
    `game_has_cap_hit = 1` for a game if *any* replayed decision in that game triggered a
    chosen-line cap-hit, else `0`; treat the `G` replayed games as (approximately) independent
    draws (a materially weaker, more defensible assumption than "decisions are independent," since
    within-game decisions are correlated but different games are not); compute the **exact
    one-sided 95% Clopper-Pearson upper bound at 0 observed successes out of `G` trials**,
    `p_upper = 1 - 0.05^(1/G)` (closed form; equivalent to the "rule of three" approximation
    `≈ 3/G` for large `G`, but exact rather than approximate). At the provisional deduplicated
    corpus size `G ≈ 85` (§1/§6 — the *unique-battle* count, not the 197-file count) this is
    ≈3.46% (verified numerically) — still a PASS-capable bound, but with far less margin than an
    (incorrect) 197-game assumption would have suggested. Solving `1 - 0.05^(1/G) ≤ 0.05` gives a
    **hard minimum of `G ≥ 59` unique battles** for a zero-event PASS to be reachable at all
    (verified numerically); below that, the zero-event branch can only ever report INCONCLUSIVE,
    regardless of how the events themselves turn out. `t4`'s 51 unique seeds *alone* would fail
    this floor (`G=51` → ≈5.7% — just short); only combining `t4`'s 51 with `t6`'s 34 clears it.
    This is now the concrete, quantified reason (beyond runtime) that Gate B must use the full
    deduplicated corpus rather than a small sample (§6).
  - **Verdict bands, pinned now, not chosen after seeing results, and dependent on BOTH the point
    estimate and the confidence interval — not the point estimate alone — with the zero-event case
    handled separately from the nonzero case:**
    - **If the observed numerator is 0:** PASS only if the game-level Clopper-Pearson upper bound
      (above) is ≤5%; otherwise INCONCLUSIVE (not FAIL — zero observed events is not evidence of a
      high true rate, just of an underpowered sample if `G` is small).
    - **If the observed numerator is ≥1:** use the decision-level point estimate and the
      game-clustered bootstrap's one-sided 95% upper bound.
      - **PASS:** point estimate ≤5% **and** the bootstrap upper bound ≤5%.
      - **INCONCLUSIVE:** point estimate ≤5% but the bootstrap upper bound >5% — the sample is too
        small/noisy to license a PASS. Report this honestly as a power limitation, not a soft
        pass. Do not loosen the 5% threshold after seeing this outcome, whichever direction it
        points.
      - **FAIL:** point estimate >5%, regardless of CI width.
    - This mirrors the already-learned lesson (`teacher-agreement-winrate-inversion`, this
      project's memory) that a point estimate alone, without respecting sampling uncertainty, can
      produce a false sense of confidence — the zero-event branch is the sharpest form of that
      lesson, since a naive reading of "0 observed" as "clean pass" is exactly the failure mode
      that lesson warns about.
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
  fold into the accuracy-effect count. **If the relevant `AccuracyResponseDetail.events_complete`
  is `False`** (branch_cap truncated discovery in at least one evaluated tie ordering — §2.4/§5),
  the diff report must say so explicitly and report the discovered events as a **partial,
  contributing** explanation only — never claim a complete mechanical explanation for a diff whose
  event list is known-incomplete.

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
  `response_index`, `tie_order`) for every accuracy-uncertain event, read from
  `trace.candidates[i].accuracy_details[*].events` for whichever candidate is the off-chosen or
  on-chosen one — the full per-response, per-tie-order-tagged list, not a flattened dict (§2.4).
  When a captured decision was a genuine tie, also capture `accuracy_details[*].tie_orders` (the
  per-ordering `AccuracyTieOrderTrace` breakdown) so the diff report can say *which* evaluated
  ordering an event or cap-hit came from, not just that one existed somewhere in the union.
- Per-candidate, per-response `accuracy_leaf_count` (real branch count, summed across evaluated
  tie orderings when tied — §2.4), `accuracy_event_count` (distinct uncertain-event count — **not**
  the same quantity as leaf count: two independent binary events can produce 4 leaves; KO/Protect
  pruning can produce fewer), `accuracy_branch_cap_hits` (summed across tie orderings; the
  safety-relevant quantity — see §4's numerator rule), and `events_complete` (`False` means the
  exported event list for that response is a known-partial view — §4 requires the diff report to
  flag this, not claim full mechanical explanation) — all read directly off
  `CandidateTrace.accuracy_details`.
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
5. **Global battle-level deduplication — a required step BEFORE Gate B runs, not an optional
   cleanup.** §1 already found strong directional evidence that most of the 197 files are
   reproduction re-runs or literal copies of two underlying seed schedules (t4's 51, t6's 34), not
   197 independent battles. This step turns that finding into a systematic, reproducible procedure
   rather than a one-off manual exclusion list:
   - **Primary key: `(schedule_hash, seed_base, seed_index)` cross-referenced against each
     directory's own committed provenance manifest** (`*-seedlog.jsonl`, `provenance.json`) — NOT
     the battle/room ID visible in filenames. This correction matters and is evidence-based, not a
     style preference: Showdown assigns a **fresh, effectively arbitrary room-id slug at
     battle-creation time regardless of whether the underlying seed is a replay** — confirmed
     directly in §1's investigation, where `t4/rerun/room_raw/run1` and `run2` carry entirely
     different `battle-gen9vgc2025regi-NNN` filenames for what their own seed logs prove are the
     *same* seeded scenario. A room/battle-ID-keyed dedup would silently miss every one of these
     real duplicates. Two files with matching `(schedule_hash, seed_base, seed_index)` are the same
     underlying battle; keep exactly one (prefer the lowest-numbered/canonical run — e.g. `run1`
     over `run2`, full runs over `prefix`) and record the rest as excluded duplicates.
   - **Secondary, defense-in-depth: content-level dedup via `(request_hash, log_prefix_hash,
     side)`** for any file lacking a clean provenance-manifest match, or to catch coincidental
     overlap the manifest-based pass didn't anticipate — this is the mechanism originally proposed
     as primary; it remains valid, just demoted to a fallback/cross-check since the manifest-based
     key is the one actually proven (§1) to catch this corpus's real duplication pattern.
   - Prefix/partial-copy files (any file whose full request sequence is a strict prefix of an
     already-kept file's sequence) are never counted as separate battles, regardless of which key
     caught them.
   - **`G`, used for both the bootstrap and the Clopper-Pearson bound (§4), is the number of
     unique battles remaining after this dedup — not the number of `.gz` files.**
   - Report, as separate numbers, not folded together: files found (197), unique battles kept,
     duplicates/partial-copies excluded (with which key caught each), and the final `G`.
   - §1's ~85-unique-battle figure is **provisional** — directional evidence from reading
     provenance manifests, not yet this step's actual output. Treat it as a planning estimate only;
     the real `G` comes from running this procedure.
6. **Gate B (the confirmatory run) uses the full deduplicated corpus only — no fallback sampling
   by default.** A 50-decision timed dry-run is run **purely to estimate total runtime** (at the
   Task 8 latency benchmark's per-decision cost, the full deduplicated corpus × 2 (off + on) is
   estimated on the order of several minutes of wall-clock compute — plausibly well within a normal
   local-run budget, but this must be measured, not assumed). **If the full deduplicated corpus
   turns out infeasible to run in full, the result is `INCONCLUSIVE / BLOCKED FOR COMPUTE`** — no
   default-on approval follows from a partial run — **not** a switch to a smaller, separately
   sampled subset. A gate that quietly downgrades its own evidence standard when the going gets
   slow is worse than an honest "we didn't run enough," especially since §4 already shows the
   zero-event PASS threshold needs `G ≥ 59` — sampling down from the already-small deduplicated
   corpus risks losing exactly the statistical power this gate depends on.
   - **If a fallback sample is nonetheless kept for a future run** (e.g. corpus growth makes a full
     run genuinely too slow later): sample **games**, not decisions, using only game-level features
     available before running anything (source directory, opponent policy) — turn-tercile is
     **not** a valid sampling stratum, because a single game's own decisions span all three turn
     terciles by construction (§7's original stratification design conflated a per-decision
     property with a per-game sampling unit). Use **every** valid decision from each drawn game;
     treat early/mid/late turn as a **post-hoc evaluation grouping** applied after the data is
     collected, not a pre-hoc sampling stratum. Pin the exact number of unique games to draw before
     running anything, with RNG seed `20260713`. **Require the drawn `G` to be at least the §4
     minimum (`G ≥ 59`) for a zero-event PASS to even be reachable** — a fallback sample smaller
     than that can, by construction, only ever report INCONCLUSIVE regardless of what the data
     shows, which is itself grounds to prefer not sampling at all.
7. **Sample/usage manifest, one row per decision used**: source file, battle ID, turn number, side,
   request hash, and log-prefix hash (the hash of exactly the frames used to build that decision's
   state) — full provenance, auditable and reproducible, matching this project's established
   `config_hash`/`movedata_hash` provenance discipline. This manifest sits downstream of, and is
   consistent with, requirement 5's separate dedup report (files found / unique battles / excluded
   duplicates / final `G`) — the two are not the same artifact.
8. **Games are clusters, not independent samples.** Every aggregate statistic (cap-hit rate, its
   CI, decision-diff rate) must be computed with game-level clustering — bootstrap resampling whole
   (deduplicated) games, not individual decisions.
9. **Small hermetic fixtures, in addition to the real-log regression test.** The one real log used
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
  - On-path, no-tie case: `leaves`/`fork_records`/`fallback_leaves` match what a direct
    `resolve_turn_branches` call on the same inputs produces.
  - On-path, tie case: `representative_outcome`/`leaves`/`fork_records` come from `ours_last` only
    (unchanged convention — a regression test pins this explicitly), while `fallback_leaves` is
    the **sum** and `accuracy_events` is the **union** across both evaluated orderings (round-4
    fix — see the next test).
  - `test_accuracy_events_use_full_leaf_union`: the regression test for round-3's discovery-bug
    fix — a scripted scenario (same shape as the merged slice's Task 4 KO-dependent regression
    test) where an event is only attempted in a miss-branch, asserting it **is** present in
    `LineEvaluation.accuracy_events` even though it is absent from `leaves[0][1].attempted_hits`.
  - `test_tie_averaging_preserves_asymmetric_cap_hit_and_event` (round-4 fix, §2.3): a scripted
    scenario with a genuine speed/priority tie where the `ours_first` action-queue ordering makes
    an attacker act (and its accuracy event become attempted) before a KO removes the opportunity,
    while the `ours_last` ordering's KO-before-act order removes that action before it ever
    attempts — i.e. an event and/or a branch-cap hit that exists under exactly one of the two
    evaluated tie orderings. Assert: (a) it **is** present in the merged `LineEvaluation.
    accuracy_events`/counted in `fallback_leaves` even though it is absent from `ours_last` alone;
    (b) `representative_outcome` is unchanged from what `ours_last` alone would produce (the fix
    must not leak into the untouched representative-outcome convention); (c)
    `tie_order_details` correctly attributes the event/cap-hit to its actual originating ordering.
  - `test_evaluate_line_details_repeat_call_identical` (§2.2): call `_evaluate_line_details` twice
    with byte-identical arguments and assert the two `LineEvaluation` results are equal on every
    field that participates in scoring or trace population — the determinism proof that replaces
    the false "same pass" claim.
  - `test_events_complete_reflects_branch_cap` (round-4 fix, §2.4): a scripted scenario forcing
    `fallback_leaves >= 1` for one evaluated tie ordering asserts that ordering's
    `TieOrderEvaluation.events_complete` is `False` and the merged `AccuracyResponseDetail.
    events_complete` (§2.4) is `False`; a scenario with `fallback_leaves == 0` on every evaluated
    ordering asserts `events_complete` is `True`.
- **Frozen pre-refactor baseline — a hard checkpoint, exact sequencing pinned:**
  unset-vs-explicit-off comparison alone is insufficient once `evaluate_line` becomes a wrapper
  around `_evaluate_line_details` — both paths then route through the *same new code*, so a bug in
  the wrapper affects both equally and the two stay "equal to each other" while both silently
  diverge from pre-refactor behavior. Exact order, to be reflected directly in the implementation
  plan's task sequencing:
  1. Finish and land the `room_raw_replay` extraction module (§6), **including the global
     deduplication step (§6 point 5)**, first — the baseline must be collected against the
     deduplicated corpus, not the raw 197-file set, or it would freeze a baseline containing
     near-duplicate decisions from confirmed reproduction re-runs.
  2. **Before any `_evaluate_line_details`/`LineEvaluation` code lands:** run the **current,
     unmodified** `heuristic_choose_for_request`/`evaluate_line` in `SHOWDOWN_ACCURACY_MODE=off`
     against the **full deduplicated corpus** (§6's primary plan; only falls back to a smaller
     sample under the same §6-point-6 rules, not a separately-chosen slice) and freeze the results
     to a committed artifact. Beyond chosen action / score / request hash / prefix hash, also
     record: the source git commit, `config_hash`, the Python interpreter version and locked
     dependency versions (whatever this project's existing environment-pin mechanism already
     captures — e.g. the same block `T4c`'s manifest environment-hardening added), and scores in a
     **canonical float representation** (fixed serialization, e.g. `repr()` or a pinned decimal
     precision) — so a harmless formatting/precision difference in a later diff tool can never be
     misread as a scoring regression.
  3. This baseline artifact is a **hard checkpoint**: the `_evaluate_line_details` refactor task
     must not start until it exists and is committed, and once frozen, it is **never regenerated**
     — if a later comparison against it looks wrong, that is itself a signal to investigate (a
     refactor bug, or a baseline-collection bug), not a reason to silently re-run and replace it.
  4. After the refactor lands, replay the identical deduplicated corpus/sample and diff against the
     frozen artifact — any difference is a refactor regression, full stop, independent of the
     unset-vs-off env-parser test (which stays, as a narrower, different check: does env-var
     parsing itself correctly treat unset/`"0"`/`"false"` as equivalent — a unit-level concern,
     not a behavioral-regression one).
- `test_bootstrap_zero_events_uses_game_level_bound` (round-4 fix, §4): given a synthetic result
  set with zero chosen-line cap-hit decisions across `G` games, assert the report (a) labels the
  plain bootstrap CI as degenerate rather than presenting it as evidence, (b) computes the
  game-level Clopper-Pearson upper bound via the pinned closed form, and (c) reaches the correct
  verdict (PASS only if that bound is ≤5%, else INCONCLUSIVE) — plus a second case with `G` small
  enough that the bound exceeds 5%, asserting INCONCLUSIVE rather than a false PASS or FAIL.
- `test_decision_trace_candidates_rank_sorted` (§5's point-8 fix): asserts
  `[c.rank for c in trace.candidates] == list(range(len(trace.candidates)))` on a real decision
  trace, so any future change to `decision.py`'s candidate-construction code that breaks this
  ordering is caught immediately rather than silently miscompared by the gate script.
- `room_raw_replay`'s extraction module: TDD against one of the real, already-on-disk logs for the
  causality requirement (state at request N excludes frames after N) and the
  team-preview/force-switch separation, **plus** the small hermetic fixtures from §6 point 9 for
  the reconnect-duplicate, mid-log force-switch, and causality-boundary-detectability cases the
  one real log doesn't reliably exercise.
- `test_global_dedup_uses_seed_schedule_not_room_id` (round-5 fix, §6 point 5): the concrete,
  already-known-true regression case — feed the extractor's dedup pass a scenario shaped exactly
  like `t4/rerun/room_raw/run1` vs `run2` (two files with different filename/room-id patterns but
  matching `(schedule_hash, seed_base, seed_index)` from their provenance manifests) and assert
  only one is kept, with the other recorded as an excluded duplicate — proving the primary key is
  actually the seed/schedule identity, not the room-id string a naive dedup could be tempted to use
  instead (§6 explains why room-id alone provably misses this corpus's real duplicates). Run this
  against the actual `t4`/`t6` provenance manifests as an integration-level check, not only a
  synthetic unit fixture, since the real dedup ratio (~197 files → ~85 unique battles, provisional)
  is itself a claim this gate's credibility depends on.
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
