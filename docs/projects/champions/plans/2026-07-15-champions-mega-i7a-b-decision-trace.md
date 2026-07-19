# Champions Mega I7a-B Decision and Trace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Score own-side Mega variants correctly in heuristic, K-world, depth-2, max-damage, and export paths while atomically migrating new decision traces to candidate-key v2 and decision-trace v3.

**Architecture:** A `MegaEvaluationContext` binds each evaluated variant to its copied projected state, post-Mega plan speed, and `DamageModel`. A structured score record keeps pooled ranking weights separate from first-world diagnostic weights. Trace-v3 makes Mega a first-class candidate action, while Tera remains a post-ranking overlay on non-Mega winners only.

**Tech Stack:** Python 3.11+, pytest, existing `DamageOracle`, pinned gen-0 calc, `DecisionTrace`, K-world sampling, depth-2 search, export rollout.

---

**Status:** APPROVED. Start only from a reviewed I7a-A tip with its completion gate green.

## File ownership

**Create:**

- `showdown_bot/src/showdown_bot/battle/mega_scoring.py`
- `showdown_bot/tests/i7a/test_i7a_decision.py`
- `showdown_bot/tests/i7a/test_i7a_trace_v3.py`

**Modify:**

- `showdown_bot/src/showdown_bot/battle/candidate_identity.py`
- `showdown_bot/src/showdown_bot/battle/decision_trace.py`
- `showdown_bot/src/showdown_bot/eval/decision_capture.py`
- `showdown_bot/src/showdown_bot/eval/decision_diff.py`
- `showdown_bot/src/showdown_bot/battle/decision.py`
- `showdown_bot/src/showdown_bot/battle/baselines.py`
- `showdown_bot/src/showdown_bot/battle/search.py`
- `showdown_bot/src/showdown_bot/learning/rollout.py`
- `showdown_bot/src/showdown_bot/learning/label_provider.py`
- `showdown_bot/src/showdown_bot/learning/features.py`
- `showdown_bot/src/showdown_bot/learning/reranker_shadow.py`
- trace/gate scripts that resolve candidates through the shared resolver
- focused tests for these consumers

**Forbidden in this slice:** log parser/reconciliation, manifests, schedules, battle runs, opponent Mega hypotheses, dual-side activation branches, latency-budget changes, and Strength claims.

## Binding score-record contract

```python
@dataclass
class MegaEvaluationContext:
    context_id: str
    projected_state: BattleState
    own_mega_slot: int | None
    foe_mega_slot: int | None
    branch_weight: float
    activation_order: tuple[tuple[str, str], ...] | None
    field: FieldState
    plans: dict[JointAction, list[PlannedAction]]
    damage_model: DamageModel


@dataclass
class MegaScoreRecord:
    variant: ScoredMegaVariant
    score_vector: list[float]             # pooled ranking vector; all worlds
    score_weights: list[float] | None     # parallel to score_vector
    diagnostic_details: list[LineEvaluation]  # most-likely world only
    diagnostic_weights: list[float] | None    # parallel to diagnostic_details
    aggregate_score: float


def score_evaluated_variants(
    evaluated_variants: list[ScoredMegaVariant],
    *,
    req: BattleRequest,
    state: BattleState,
    book: SpreadBook,
    our_side: str,
    opp_side: str,
    calc: CalcClient,
    oracle: DamageOracle,
    speed_oracle: SpeedOracle | None,
    dex: SpeciesDex | None,
    priors,
    weights: EvalWeights,
    mode: GameMode,
    risk_lambda: float,
    rollout_horizon: int,
    our_spreads: dict | None,
    opp_sets: dict | None,
    calc_profile: CalcProfile,
    accuracy_mode: bool,
    accuracy_branch_cap: int,
    endgame: bool,
    fast_board: bool,
) -> list[MegaScoreRecord]:
    """Expand no actions; score exactly the supplied evaluated variants."""
```

Rules:

- `aggregate_score` uses `score_vector` plus `score_weights`.
- Candidate `score_vector` may be pooled across worlds, matching current behavior.
- `outcome_breakdowns` and `accuracy_details` come only from `diagnostic_details` for world 0, matching the existing DTO convention.
- `aggregate_breakdown` uses only `diagnostic_weights`. Never divide first-world breakdowns by a pooled all-world weight total.
- Mega candidate tempo/KO features use that candidate's projected context. Decision-level fields use the chosen variant's projected context, not the unprojected live state.

### Task 1: Add key-v2 and trace-v3 atomically

**Files:** candidate identity, trace DTO/capture/diff, shared consumers, trace tests.

- [ ] **Step 1: Write failing v3 positive and negative tests**

```python
def test_joint_action_key_v2_contains_mega_flag():
    base = JointAction(SlotAction("move", move_index=1), SlotAction("pass"))
    mega = base.with_mega(0)
    assert joint_action_key_v2(base) != joint_action_key_v2(mega)
    assert json.loads(joint_action_key_v2(mega))["version"] == 2


@pytest.mark.parametrize("mutation", [
    "v1_key", "missing_mega_field", "unknown_slot_field",
    "non_bool_tera", "dual_overlay", "duplicate_key",
])
def test_v3_rejects_invalid_candidate_keys(valid_v3_row, mutation):
    row = mutate_v3_row(valid_v3_row, mutation)
    with pytest.raises(DecisionCaptureError):
        validate_trace_row(row)
```

Build `valid_v3_row` in the existing `tests/test_decision_capture.py`, where the local `v2_trace_row` fixture is already available:

```python
@pytest.fixture
def valid_v3_row(v2_trace_row):
    row = copy.deepcopy(v2_trace_row)
    row["trace_schema_version"] = TRACE_SCHEMA_VERSION_V3
    row["chosen_mega_slot"] = None
    for candidate in row["candidates"]:
        payload = json.loads(candidate["candidate_key"])
        payload["version"] = 2
        for slot in payload["slots"]:
            slot["mega_evolve"] = False
        candidate["candidate_key"] = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    old_chosen = row["chosen_candidate_key"]
    old_to_new = {
        v2["candidate_key"]: v3["candidate_key"]
        for v2, v3 in zip(v2_trace_row["candidates"], row["candidates"], strict=True)
    }
    row["chosen_candidate_key"] = old_to_new[old_chosen]
    return row


def mutate_v3_row(row, mutation):
    row = copy.deepcopy(row)
    payload = json.loads(row["candidates"][0]["candidate_key"])
    if mutation == "v1_key":
        payload["version"] = 1
    elif mutation == "missing_mega_field":
        del payload["slots"][0]["mega_evolve"]
    elif mutation == "unknown_slot_field":
        payload["slots"][0]["extra"] = 1
    elif mutation == "non_bool_tera":
        payload["slots"][0]["terastallize"] = 1
    elif mutation == "dual_overlay":
        payload["slots"][0]["terastallize"] = True
        payload["slots"][0]["mega_evolve"] = True
    elif mutation == "duplicate_key":
        row["candidates"][1]["candidate_key"] = row["candidates"][0]["candidate_key"]
        return row
    else:
        raise AssertionError(mutation)
    row["candidates"][0]["candidate_key"] = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    )
    return row
```

Add explicit tests that v1/v2 fixtures still load, v3 requires the three chosen keys even when values are null, chosen Mega and Tera slots cannot both be set, normalized `mega` must match the chosen slot, and the chosen key must resolve exactly once.

- [ ] **Step 2: Confirm the v3 suite is RED**

```powershell
python -m pytest tests/i7a/test_i7a_trace_v3.py tests/test_candidate_identity.py tests/test_decision_capture.py -q
```

- [ ] **Step 3: Implement key-v2 and exact validators**

Keep `joint_action_key()` as the v1 payload used by old v2 rows. Add:

```python
def joint_action_key_v2(ja: JointAction) -> str:
    def slot(sa):
        return {
            "kind": sa.kind,
            "move_index": sa.move_index,
            "target": sa.target,
            "target_ident": sa.target_ident,
            "terastallize": sa.terastallize,
            "mega_evolve": sa.mega_evolve,
        }
    return json.dumps(
        {"version": 2, "slots": [slot(ja.slot0), slot(ja.slot1)]},
        sort_keys=True, separators=(",", ":"),
    )
```

`_validate_candidate_key_v2` must compare exact top-level and slot key sets and use `type(value) is bool/int` where booleans must not pass integer checks. New writes use `TRACE_SCHEMA_VERSION_V3`; v1/v2 validation branches remain untouched.

- [ ] **Step 4: Update normalization, DTOs, decision population, and shared resolvers in the same commit**

`DecisionTrace` gains `chosen_mega_slot`. `_MOVE_RE` accepts exactly one optional overlay token `terastallize|mega`. `build_trace_row` writes v3 and always includes `chosen_candidate_key`, `chosen_mega_slot`, and `chosen_tera_slot` keys. Current non-Mega decision candidates are populated with `joint_action_key_v2`; do not emit a v3 row containing v1 keys.

Update `_label_ja` so a move slot with `mega_evolve=True` receives a human-readable ` mega` suffix. Labels remain diagnostic only; structural resolution uses key-v2.

The no-Mega decision path must preserve chosen `/choose`, ranks, candidate scores, and selection stage. It is not expected to preserve sidecar bytes because the schema intentionally changes.

Audit script consumers with:

```powershell
rg -n "chosen_candidate_id|chosen_candidate_key|resolve_chosen_candidate" scripts -g "*.py"
```

`run_accuracy_baseline_freeze.py`, `run_accuracy_baseline_diff.py`, and `run_ambiguous_candidate_diagnostic.py` must continue through `resolve_chosen_candidate`; do not add a script-local v3 first-match fallback.

- [ ] **Step 5: Run atomic trace gate and commit**

```powershell
python -m pytest tests/i7a/test_i7a_trace_v3.py tests/test_candidate_identity.py tests/test_decision_capture.py tests/test_decision_diff.py tests/test_reranker_shadow.py tests/test_label_provider.py -q
git diff --check
git add src/showdown_bot/battle/candidate_identity.py src/showdown_bot/battle/decision_trace.py src/showdown_bot/eval src/showdown_bot/learning scripts tests
git commit -m "feat(trace): add candidate key v2 and decision trace v3"
```

### Task 2: Build Mega evaluation contexts with post-Mega plan speed

**Files:** new `battle/mega_scoring.py`, `battle/decision.py`, `resolve.py`, decision tests.

- [ ] **Step 1: Add failing context, damage-species, immutability, and speed tests**

The speed test must call `SubprocessCalcBackend.stats_batch([mega_calc_mon], gen=0)` and assert request base speed `200`, projected Aerodactyl-Mega speed `222`, and `PlannedAction.speed == 222`. It must also assert the original state and request stats are unchanged.

- [ ] **Step 2: Confirm RED**

```powershell
npm --prefix tools/calc ci
python -m pytest tests/i7a/test_i7a_decision.py -k "context or plan_speed or damage_species" -q
```

- [ ] **Step 3: Add a direct plan-speed override and context builder**

```python
def _planned_speed_for_slot(
    *,
    active_index: int,
    actives: list,
    state: BattleState,
    our_side: str,
    speed_oracle: SpeedOracle | None,
    planned_speed_overrides_by_slot: dict[int, int] | None,
) -> int:
    overrides = planned_speed_overrides_by_slot or {}
    if active_index in overrides:
        return int(overrides[active_index])
    base_spe = (
        int(actives[active_index].stats.get("spe", 0))
        if active_index < len(actives)
        else 0
    )
    mon = state.side(our_side).get(_SLOTS[active_index])
    if speed_oracle is not None and mon is not None:
        return speed_oracle.our_speed(base_spe, mon, state.field, our_side)
    return base_spe
```

Add `planned_speed_overrides_by_slot` to `_plan_my_actions`, call this helper exactly once per slot, and add `is_mega=sa.mega_evolve` to each move `PlannedAction`. Pass/switch actions retain their current construction and use the same computed speed.

`build_own_mega_contexts` creates one context for `None` and one per surviving own Mega slot, computes the projected form speed once through `speed_for_species`, and passes that integer directly to `_plan_my_actions`. It builds `DamageModel` from the projected state and preserves one shared oracle without flushing.

- [ ] **Step 4: Add a correct Mega Sol differential test**

Construct explicit `PlannedAction`s for Meganium-Mega, its partner, and a foe; do not search opponent actions inside `ctx.plans`, which contains only our joint-action plans. Compare a projected Mega-Sol model against a deep-copied neutral model where only Meganium-Mega's ability is blank:

```python
fire_mega = mega_model.damage_fn(our_fire_action, foe_target)
fire_neutral = neutral_model.damage_fn(our_fire_action, foe_target)
water_mega = mega_model.damage_fn(our_water_action, foe_target)
water_neutral = neutral_model.damage_fn(our_water_action, foe_target)
assert fire_mega > fire_neutral
assert water_mega < water_neutral
assert mega_model.damage_fn(partner_action, foe_target) == neutral_model.damage_fn(partner_action, foe_target)
assert mega_model.damage_fn(foe_action, our_target) == neutral_model.damage_fn(foe_action, our_target)
assert mega_context.projected_state.field.weather is None
```

Enqueue both models' explicit actions before one shared-oracle flush. This is T28; the older Body Slam bridge fixture is not used.

- [ ] **Step 5: Run and commit contexts**

```powershell
python -m pytest tests/i7a/test_i7a_decision.py -k "context or plan_speed or damage_species or mega_sol" -q
git add src/showdown_bot/battle/mega_scoring.py src/showdown_bot/battle/decision.py src/showdown_bot/battle/resolve.py tests/i7a/test_i7a_decision.py
git commit -m "feat(champions): build own Mega evaluation contexts"
```

### Task 3: Score single-world, K-world, and depth-2 variants

**Files:** `mega_scoring.py`, `decision.py`, `search.py`, tests.

- [ ] **Step 1: Add failing batching, weight-separation, and depth-2 tests**

Use a counting fake oracle. Assert all contexts enqueue before exactly one `flush()`. In a two-world fixture with unequal weights, assert pooled `score_weights` cover both worlds while `diagnostic_weights` cover only world 0 and the aggregate breakdown is not divided by the pooled total. Add a depth-2 spy that records the projected state species and field for each overwritten frontier slot.

- [ ] **Step 2: Confirm RED**

```powershell
python -m pytest tests/i7a/test_i7a_decision.py -k "batch or k_world or diagnostic_weights or depth2" -q
```

- [ ] **Step 3: Implement score records and one-flush ordering**

For each sampled world, build contexts with that world's merged `opp_sets`, predict responses, enqueue every own and opponent plan, then flush once. For each evaluated variant, append all world scores and world-weighted response weights. Separately retain only world-0 `LineEvaluation` objects and world-0 response weights for diagnostics.

```python
record.aggregate_score = aggregate_scores(
    record.score_vector, mode,
    risk_lambda=risk_lambda,
    weights=record.score_weights,
)
```

- [ ] **Step 4: Bind depth-2 to the candidate context**

For each selected frontier `(variant, response_index)`, take the representative outcome from that record's matching context, derive applied damage from `ctx.projected_state`, and call:

```python
depth2_value(
    ctx.projected_state,
    our_side=our_side,
    applied_damage=applied_damage,
    mode=mode,
    risk_lambda=risk_lambda,
    top_m=2,
    book=book,
    oracle=ctx.damage_model.oracle,
    predict_kwargs={"dex": dex, "speed_oracle": speed_oracle},
    model_kwargs={
        "our_spreads": our_spreads,
        "opp_sets": opp_sets,
        "calc_profile": calc_profile,
    },
    eval_kwargs={
        "weights": weights,
        "rollout_horizon": rollout_horizon,
        "endgame": endgame,
        "fast_board": fast_board,
    },
)
```

Never use base `state` or a different variant's model.

- [ ] **Step 5: Run and commit the scorer**

```powershell
python -m pytest tests/i7a/test_i7a_decision.py -k "batch or k_world or diagnostic_weights or depth2" -q
git add src/showdown_bot/battle/mega_scoring.py src/showdown_bot/battle/search.py tests/i7a/test_i7a_decision.py
git commit -m "feat(champions): score Mega variants across search modes"
```

### Task 4: Integrate Mega ranking and candidate trace population

**Files:** `decision.py`, `mega_scoring.py`, trace/decision tests.

- [ ] **Step 1: Add failing T17, T31, T50, trace, and Tera-exclusion tests**

T17 must prove base action A beats base B but B+Mega wins the full grid. T31 obtains Scovillain's active slot from `state.side(our_side)`, proves the raw Mega variant exists, and proves it is absent from evaluated variants and trace. The mutual-exclusion test uses a synthetic config with both flags true and asserts a chosen Mega winner never enters `_maybe_tera`.

- [ ] **Step 2: Confirm RED**

```powershell
python -m pytest tests/i7a/test_i7a_decision.py tests/i7a/test_i7a_trace_v3.py -k "counterproof or scovillain or trace or tera" -q
```

- [ ] **Step 3: Replace decision ranking with one expansion and one evaluated list**

The Mega-enabled branch performs exactly:

```python
base_joints = enumerate_my_actions(req, moved_since_switch=moved_since_switch)
variants = expand_mega_variants(base_joints, req, state, our_side)
evaluated = filter_projectable_variants(
    variants,
    req,
    state,
    our_side,
    species_meta=species_meta_table(),
    speed_oracle=speed_oracle,
    our_spreads=our_spreads,
    calc_profile=calc_profile,
)
records = score_evaluated_variants(
    evaluated,
    req=req,
    state=state,
    book=book,
    our_side=our_side,
    opp_side=opp_side,
    calc=calc,
    oracle=oracle,
    speed_oracle=speed_oracle,
    dex=dex,
    priors=priors,
    weights=weights,
    mode=mode,
    risk_lambda=risk_lambda,
    rollout_horizon=rollout_horizon,
    our_spreads=our_spreads,
    opp_sets=opp_sets,
    calc_profile=calc_profile,
    accuracy_mode=accuracy_mode,
    accuracy_branch_cap=accuracy_branch_cap,
    endgame=endgame,
    fast_board=fast_board,
)
items = [(record.variant.joint, record.score_vector) for record in records]
best_ja, best_val = pick_best(
    items,
    mode,
    risk_lambda=risk_lambda,
    weights=records[0].score_weights,
)
winner = next(record for record in records if record.variant.joint == best_ja)
```

Do not score a base winner first and overlay Mega. If any slot in `best_ja` has `mega_evolve=True`, skip `_maybe_tera`; otherwise preserve the existing Tera overlay.

- [ ] **Step 4: Populate trace once from score records**

`_populate_mega_decision_trace` receives the unchanged `evaluated` list and matching records. It creates exactly one `CandidateTrace` per exported evaluated variant. Candidate aggregate scores use pooled score weights; outcome/accuracy breakdowns use world-0 diagnostics and world-0 weights. Chosen/projected decision features and tempo use the winner's context. It sets `chosen_candidate_key=joint_action_key_v2(pre_tera_winner)`, `chosen_mega_slot`, and mutually exclusive `chosen_tera_slot`.

The non-Mega branch remains a separate `_populate_legacy_decision_trace` helper. It may emit v3/key-v2, but its scoring, chosen action, ranks, and feature values remain unchanged.

- [ ] **Step 5: Run and commit live heuristic integration**

```powershell
python -m pytest tests/i7a/test_i7a_decision.py tests/i7a/test_i7a_trace_v3.py tests/test_decide_core_equivalence.py tests/test_accuracy_mode_wiring.py -q
git add src/showdown_bot/battle/decision.py src/showdown_bot/battle/mega_scoring.py tests
git commit -m "feat(champions): rank and trace own Mega candidates"
```

### Task 5: Integrate max-damage and export/rollout consumers

**Files:** baselines, export/rollout/labels, tests.

- [ ] **Step 1: Add failing consumer tests**

For `max_damage_choice`, use two states with identical outgoing calculations but radically different incoming threats and assert the same selected action. Monkeypatch `showdown_bot.battle.evaluate.evaluate_line` to raise; if `baselines` exposes a locally imported `evaluate_line`, patch that symbol too. Assert the stub is never reached. Add an injected-oracle test proving the consumer uses the shared expand/filter/context path once.

For export, build `RolloutConfig(H=0, gamma=0.75, top_k=1, use_leaf=False)`, a v3 DTO with a non-switch `PlannedAction`, and labels keyed by `resolved.candidate_key`; assert `counterfactual_value == 0.0` and the inner decision receives `format_config` without a `calc_profile` splat TypeError.

- [ ] **Step 2: Confirm RED**

```powershell
python -m pytest tests/i7a/test_i7a_decision.py tests/test_export_runtime.py tests/test_rollout.py tests/test_label_provider.py -k "mega or max_damage or v3" -q
```

- [ ] **Step 3: Integrate max-damage without incoming evaluation**

When `format_config.mega` is true, max-damage expands/filters once, builds contexts with one shared oracle, and scores only outgoing fractions plus `_KO_BONUS`. Enumeration-order ties remain strict first-wins. When Mega is false or absent, retain the existing function body and output exactly.

- [ ] **Step 4: Thread format and profile through export**

`export_runtime` loads one format config, derives one calc profile, stores both in rollout deps, and passes only `format_config` through `_CORE_DEP_KEYS` into inner `_choose_best`. `make_resolve` reads `deps.get("calc_profile") or calc_profile_from_config(deps.get("format_config"))`. Candidate labels and reranker joins use structural v3 keys.

- [ ] **Step 5: Run the I7a-B gate and commit**

```powershell
python -m pytest tests/i7a/test_i7a_decision.py tests/i7a/test_i7a_trace_v3.py tests/test_candidate_identity.py tests/test_decision_capture.py tests/test_decide_core_equivalence.py tests/test_accuracy_mode_wiring.py tests/test_baselines.py tests/test_export_runtime.py tests/test_rollout.py tests/test_label_provider.py tests/test_reranker_shadow.py -q
git diff --check
git add src/showdown_bot/battle src/showdown_bot/eval src/showdown_bot/learning tests
git commit -m "feat(champions): wire Mega ranking into all decision consumers"
```

## I7a-B completion gate

- Tests T14–T17, T20–T22, T25, T28, T31, T33–T37, T47–T50, and T52–T54 pass.
- Reg-I and `format_config=None` chosen `/choose` strings remain byte-identical; trace rows intentionally move to v3.
- v1 and v2 trace fixtures remain loadable and resolve fail-closed on ambiguity.
- K-world score weights and first-world diagnostic weights are separately tested.
- T28 uses explicit own/partner/foe actions and proves Mega Sol is not a global-weather shortcut.
- A chosen Mega candidate cannot receive a Tera overlay.
- No state parser, manifest, schedule, run artifact, I7b hypothesis, latency threshold, or Strength claim changes.
