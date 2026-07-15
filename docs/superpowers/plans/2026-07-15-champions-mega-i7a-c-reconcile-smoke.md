# Champions Mega I7a-C Reconciliation, Provenance, and Smoke Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconcile observed Mega protocol events atomically into battle/belief state, bind Mega metadata to run provenance, and freeze a clean 2-battle I7a safety smoke.

**Architecture:** Raw `LogEvent` streams and already reduced mixed streams use different explicit APIs, eliminating heuristic double-reduction. A persistent reducer pairs `detailschange` and `-mega`, and state application snapshots the affected mon plus side-spend flag before mutation. Provenance hashes the generated item/species metadata, then a clean-tree smoke verifies request/encoder/ranking/trace/rebuild integration without making a Strength claim.

**Tech Stack:** Python 3.11+, pytest, JSONL manifests, Pokemon Showdown local server, existing gauntlet and `eval-report` commands.

---

**Status:** APPROVED. Start only from a reviewed I7a-B tip with its completion gate green.

## File ownership

**Create:**

- `showdown_bot/src/showdown_bot/engine/mega_reconcile.py`
- `showdown_bot/tests/i7a/test_i7a_reconcile.py`
- `showdown_bot/tests/i7a/test_i7a_provenance.py`
- `config/eval/schedules/champions_v0_smoke_i7a_2battle.yaml`
- `data/eval/champions-panel-v0/smoke-i7a-mega/` frozen non-raw artifacts
- `reports/champions-panel-v0-i7a-mega-smoke.md`

**Modify:**

- `showdown_bot/src/showdown_bot/engine/log_parser.py`
- `showdown_bot/src/showdown_bot/engine/state.py`
- `showdown_bot/src/showdown_bot/engine/belief/tracker.py`
- `showdown_bot/src/showdown_bot/eval/config_env.py`
- every production `build_config_manifest` caller found by `rg`
- `docs/ROADMAP.md`
- `docs/PROJECT_INDEX.md`
- focused parser/state/belief/config tests

**Forbidden in this slice:** ranking logic, trace schema redesign, opponent Mega prediction, I7b, latency threshold changes, Strength runs, committed room logs, or local server data.

## Binding raw/reduced API

Do not implement `events_need_reduction()` or inspect the first list element. A reduced stream is intentionally mixed and may begin with an ordinary `LogEvent`.

```python
ReducedLogEvent = LogEvent | MegaReconcileEvent

@classmethod
def from_log(cls, events: list[LogEvent]) -> "BattleState":
    return cls.from_reduced_log(reduce_log_events(events))

@classmethod
def from_reduced_log(cls, events: list[ReducedLogEvent]) -> "BattleState":
    state = cls()
    for event in events:
        state.apply_event(event)
    return state

@classmethod
def from_log_text(cls, raw_log: str) -> "BattleState":
    return cls.from_log(parse_log(raw_log))
```

This explicit split is mandatory. No caller passes a reduced list to `from_log`.

### Task 1: Parse and reduce Mega protocol events

**Files:** log parser, new reducer, reducer tests.

- [ ] **Step 1: Write failing parse, pairing, orphan, and mixed-stream tests**

```python
def switch_event():
    return parse_log_line(
        "switch",
        ["p1a: Charizard", "Charizard, L50", "100/100"],
    )


def detailschange_event():
    return parse_log_line(
        "detailschange",
        ["p1a: Charizard", "Charizard-Mega-Y, L50"],
    )


def mega_event():
    return parse_log_line(
        "-mega",
        ["p1a: Charizard", "Charizard", "Charizardite Y"],
    )


def test_parse_mega_ground_truth_three_args():
    event = parse_log_line(
        "-mega",
        ["p1a: Charizard", "Charizard", "Charizardite Y"],
    )
    assert event.type == "mega"
    assert event.value == "Charizard"
    assert event.details == "Charizardite Y"


def test_reduced_stream_can_start_with_normal_event():
    raw = [switch_event(), detailschange_event(), mega_event()]
    reduced = reduce_log_events(raw)
    assert isinstance(reduced[0], LogEvent)
    assert isinstance(reduced[1], MegaReconcileEvent)
    state = BattleState.from_reduced_log(reduced)
    assert state.active("p1", "a").species == "Charizard-Mega-Y"
```

Also test orphan `detailschange` flushes as an ordinary form change, `-mega` without pending details fails closed, wrong ident fails closed, and `reduce_log_events` flushes exactly once at batch end.

- [ ] **Step 2: Confirm RED**

```powershell
python -m pytest tests/i7a/test_i7a_reconcile.py -k "parse or reducer or reduced_stream" -q
```

- [ ] **Step 3: Implement exact parse and reducer contracts**

`parse_log_line` uses `prefix == "detailschange"` and `prefix == "-mega"`. The three `-mega` positional values map to actor, base species, and stone display name.

```python
@dataclass(frozen=True)
class MegaReconcileEvent:
    pokemon: PokemonId
    mega_species_details: str
    base_species: str
    stone_display: str


class MegaReconcileReducer:
    def __init__(self):
        self.pending_detailschange: dict[str, LogEvent] = {}

    def feed(self, event: LogEvent) -> list[ReducedLogEvent]:
        key = None if event.pokemon is None else f"{event.pokemon.side}{event.pokemon.slot}"
        if event.type == "detailschange":
            emitted = []
            previous = self.pending_detailschange.pop(key, None)
            if previous is not None:
                emitted.append(previous)
            self.pending_detailschange[key] = event
            return emitted
        if event.type == "mega":
            pending = self.pending_detailschange.pop(key, None)
            if pending is None:
                raise MegaReconcileError("mega_without_detailschange")
            return [MegaReconcileEvent(
                pokemon=event.pokemon,
                mega_species_details=pending.details or "",
                base_species=event.value or "",
                stone_display=event.details or "",
            )]
        emitted = []
        if key is not None:
            for pending_key in [k for k in self.pending_detailschange if k != key]:
                emitted.append(self.pending_detailschange.pop(pending_key))
        emitted.append(event)
        return emitted

    def flush_pending(self) -> list[ReducedLogEvent]:
        out = list(self.pending_detailschange.values())
        self.pending_detailschange.clear()
        return out
```

- [ ] **Step 4: Verify reducer behavior**

```powershell
python -m pytest tests/i7a/test_i7a_reconcile.py -k "parse or reducer or reduced_stream" -q
```

- [ ] **Step 5: Commit parser/reducer**

```powershell
git add src/showdown_bot/engine/log_parser.py src/showdown_bot/engine/mega_reconcile.py tests/i7a/test_i7a_reconcile.py
git commit -m "feat(champions): reduce Mega protocol events atomically"
```

### Task 2: Apply reconciliation with rollback and persistent belief updates

**Files:** state, belief tracker, reconcile tests.

- [ ] **Step 1: Add failing T41–T46 and cross-call persistence tests**

```python
def test_belief_update_pairs_events_across_calls(state, book):
    tracker = BeliefTracker.from_state(state, book)
    tracker.update(detailschange_event())
    assert tracker.state.active("p1", "a").species == "Charizard"
    tracker.update(mega_event())
    assert tracker.state.active("p1", "a").species == "Charizard-Mega-Y"
    assert tracker.state.side_mega_spent["p1"] is True


def test_item_conflict_rolls_back_every_mega_field(state):
    state.active("p1", "a").item = "Leftovers"
    state.active("p1", "a").item_known = True
    before = copy_battle_state(state)
    event = MegaReconcileEvent(
        pokemon=PokemonId.parse("p1a: Charizard"),
        mega_species_details="Charizard-Mega-Y, L50",
        base_species="Charizard",
        stone_display="Charizardite Y",
    )
    with pytest.raises(MegaReconcileError):
        state.apply_event(event)
    assert state == before
```

The full-log test calls only `BattleState.from_log_text(raw)`. The belief batch test calls `tracker.feed(parse_log(raw))`; neither manually calls the reducer.

- [ ] **Step 2: Confirm RED**

```powershell
python -m pytest tests/i7a/test_i7a_reconcile.py -k "state or belief or rollback or full_log" -q
```

- [ ] **Step 3: Add explicit raw/reduced state entry points and atomic apply**

`BattleState.apply_event` accepts `ReducedLogEvent` and dispatches `MegaReconcileEvent` before reading `.type`. The ordinary `detailschange` branch applies `parse_details(event.details)`, then refreshes species/types/ability from `speciesdata` without setting item or `side_mega_spent`. `_apply_mega_reconcile` snapshots the affected `PokemonState` and `side_mega_spent[side]`, validates base species and stone, applies species/types/ability/base id/item/spend, and restores the snapshot on every `MegaReconcileError`. It does not synthesize weather.

- [ ] **Step 4: Make reducer lifetime explicit in BeliefTracker**

```python
@dataclass
class BeliefTracker:
    state: BattleState
    book: SpreadBook
    hypotheses: dict[str, dict[str, SetHypothesis]] = field(default_factory=dict)
    speed_observations: list[tuple[str, str]] = field(default_factory=list)
    _mega_reducer: MegaReconcileReducer = field(default_factory=MegaReconcileReducer)

    def _apply_reduced(self, event: ReducedLogEvent) -> None:
        if isinstance(event, LogEvent) and event.type == "move" and event.pokemon is not None:
            self.speed_observations.append((event.pokemon.side, event.pokemon.slot))
        self.state.apply_event(event)
        pokemon = event.pokemon
        if pokemon is not None:
            self._resync_slot(pokemon.side, pokemon.slot)

    def update(self, event: LogEvent) -> None:
        for reduced in self._mega_reducer.feed(event):
            self._apply_reduced(reduced)

    def feed(self, events: list[LogEvent]) -> None:
        for event in events:
            self.update(event)
        for reduced in self._mega_reducer.flush_pending():
            self._apply_reduced(reduced)
```

`update` never flushes, so `detailschange` and `-mega` may pair across update calls. `feed` defines a batch boundary and flushes after the full batch. Add a public `flush_pending()` only if an existing caller needs to end a stream without `feed`.

- [ ] **Step 5: Run and commit state reconciliation**

```powershell
python -m pytest tests/i7a/test_i7a_reconcile.py tests/test_log_parser.py tests/test_battle_state.py tests/test_belief_tracker.py -q
git add src/showdown_bot/engine/state.py src/showdown_bot/engine/belief/tracker.py tests
git commit -m "feat(champions): reconcile observed Mega state with rollback"
```

### Task 3: Add item/species provenance to every manifest caller

**Files:** `eval/config_env.py`, current callers found by `rg`, provenance tests.

- [ ] **Step 1: Add failing hash-change and caller-wiring tests**

Tests must prove `config_provenance_for_format` returns `itemdata_hash` and `speciesdata_hash`; either changed hash changes `config_hash`; stale generated data propagates its typed error; and every production call to `build_config_manifest` passes both values.

- [ ] **Step 2: Enumerate actual callers before editing**

```powershell
rg -n "build_config_manifest\(" src scripts -g "*.py"
```

Record the output in the implementation review. Do not rely on a historical caller count.

- [ ] **Step 3: Confirm RED**

```powershell
python -m pytest tests/i7a/test_i7a_provenance.py tests/test_config_env.py -q
```

- [ ] **Step 4: Wire verified embedded hashes**

```python
def config_provenance_for_format(format_id: str) -> dict[str, str | None]:
    from showdown_bot.engine.calc.pin import calc_pin_hash, format_config_hash
    from showdown_bot.engine.format_config import load_format_config
    from showdown_bot.engine.items import itemdata_content_hash
    from showdown_bot.engine.species_meta import speciesdata_content_hash

    try:
        cfg = load_format_config(format_id)
    except FileNotFoundError:
        cfg = None
    fmt_hash = (
        format_config_hash(cfg.source_path)
        if cfg is not None and cfg.source_path is not None
        else None
    )
    return {
        "format_config_hash": fmt_hash,
        "calc_pin_hash": calc_pin_hash(),
        "itemdata_hash": itemdata_content_hash(),
        "speciesdata_hash": speciesdata_content_hash(),
    }


def build_config_manifest(
    *, agent, format_id, priors_hash, spreads_hash, env=None,
    model_hash=None, model_manifest_hash=None, movedata_hash=None,
    format_config_hash=None, calc_pin_hash=None,
    itemdata_hash=None, speciesdata_hash=None,
) -> dict:
    manifest = {
        "agent": agent,
        "format_id": format_id,
        "priors_hash": priors_hash,
        "spreads_hash": spreads_hash,
        "env": behavior_env() if env is None else env,
    }
    if model_hash is not None:
        manifest["model_hash"] = model_hash
    if model_manifest_hash is not None:
        manifest["model_manifest_hash"] = model_manifest_hash
    if movedata_hash is not None:
        manifest["movedata_hash"] = movedata_hash
    if format_config_hash is not None:
        manifest["format_config_hash"] = format_config_hash
    if calc_pin_hash is not None:
        manifest["calc_pin_hash"] = calc_pin_hash
    if itemdata_hash is not None:
        manifest["itemdata_hash"] = itemdata_hash
    if speciesdata_hash is not None:
        manifest["speciesdata_hash"] = speciesdata_hash
    return manifest
```

Add optional manifest parameters and include them in the canonical config hash payload. There is no fallback to raw file SHA when embedded generator validation fails.

- [ ] **Step 5: Run and commit provenance**

```powershell
python -m pytest tests/i7a/test_i7a_provenance.py tests/test_config_env.py tests/test_cli_run_schedule_export.py -q
git diff --check
git add src/showdown_bot/eval/config_env.py src/showdown_bot/cli.py scripts tests
git commit -m "feat(champions): bind Mega metadata to run provenance"
```

### Task 4: Add and validate the clean 2-battle schedule

**Files:** new schedule and schedule/panel tests.

- [ ] **Step 1: Write the schedule**

Use the existing I6 two-row structure, a new seed base `champions-panel-v0-smoke-i7a-mega`, and these rows:

```yaml
version: champions_v0
panel_hash: aac1ea30446fde88
rows:
- format_id: gen9championsvgc2026regma
  hero_team_path: teams/fixed_champions_v0.txt
  opp_policy: heuristic
  opp_team_path: teams/panel_champions_v0/goodstuff.txt
  seed_index: 0
  hero_team_hash: 1d3a4cf5a4042532
  opp_team_hash: 0054b6894af7215a
  panel_split: dev
- format_id: gen9championsvgc2026regma
  hero_team_path: teams/fixed_champions_v0.txt
  opp_policy: max_damage
  opp_team_path: teams/panel_champions_v0/rain_offense.txt
  seed_index: 1
  hero_team_hash: 1d3a4cf5a4042532
  opp_team_hash: e0c96fa0cabf1def
  panel_split: heldout
```

- [ ] **Step 2: Add schedule hash/path tests and run them**

```powershell
python -m pytest tests/test_schedule.py tests/test_panel.py -q
```

- [ ] **Step 3: Run the full pre-smoke suite**

```powershell
python -m pytest -q
git diff --check
```

Expected: full suite green with only known skip/xfail counts explained.

- [ ] **Step 4: Commit the schedule before capturing its SHA**

```powershell
git add ../config/eval/schedules/champions_v0_smoke_i7a_2battle.yaml tests
git commit -m "test(champions): add I7a Mega safety schedule"
```

- [ ] **Step 5: Verify clean-tree precondition**

```powershell
if (git status --porcelain) { throw "dirty tree before smoke" }
if (Test-Path ..\data\eval\champions-panel-v0\smoke-i7a-mega) { throw "smoke output already exists" }
$env:TASK17A_HEAD = (git rev-parse HEAD).Trim()
Set-Content -NoNewline "$env:TEMP\task17a_head_i7a.txt" $env:TASK17A_HEAD
```

### Task 5: Run, validate, freeze, and document the safety smoke

**Files:** frozen eval directory, report, ROADMAP, PROJECT_INDEX.

**P1.3/P1.4 hardening (Codex I7a-C review, 2026-07-15):** the external review found this
task's original Step 3 evidence bar ("at least one evaluated Mega-capable species is
observed") too weak -- a run could pass without the bot ever actually clicking Mega. Do
NOT start this task until:

- `showdown_bot/src/showdown_bot/eval/mega_evidence.py`'s `derive_mega_evidence` is used to
  gate the verdict (requires an observed `chosen_mega_slot`, a `/choose` string containing
  `"mega"`, and a later non-team-preview decision whose `state_summary` species matches the
  EXACT Mega form `mega_form_for` derives from the pre-click species + stone item -- NOT
  merely any different species, which a later switch could also produce -- see that
  module's docstring for exactly what it does and does not prove);
- `bind_protocol_mega_pair` (same module) is used, while the run's `SHOWDOWN_ROOM_RAW_DUMP`
  local log still exists, to bind the trace-derived evidence to the actual observed
  `detailschange`/`-mega` protocol line pair (compact line/log hashes only -- never
  committing raw log content) -- a trace-level species match alone does not prove real
  protocol events occurred (`merge_request()` can also update species from the request);
- `showdown_bot/src/showdown_bot/eval/config_manifest_freeze.py`'s
  `write_config_manifest_sidecar` is used to freeze `results.jsonl.config-manifest.json`
  (calls the same `effective_config_manifest` the CLI's live `config_hash` uses -- no
  ad-hoc re-derivation), and `verify_config_manifest_sidecar` is used to re-check that
  binding after any post-hoc mutation of a frozen result row.

**A prior live-smoke run already exists** at
`data/eval/champions-panel-v0/smoke-i7a-mega/` (untracked). Its manifest records
`git_sha=cb1934e233044f9195ffd8d0ce8da6ffd2c1c019` -- the schedule commit, BEFORE the
P1.1 (`8932786`) and P1.2 (`838ef2c`) reconciliation/belief fixes existed. **That run does
not count as evidence for this task** (pre-fix code, and it predates this hardened
evidence gate regardless) and must not be cited, frozen, or built upon. Delete or ignore it
and start Step 1 fresh only after explicit sign-off to run a live smoke.

- [ ] **Step 1: Start one fresh Showdown server outside the repository**

Use the pinned server checkout and a single process. Record its PID in the local run log; do not commit server data.

- [ ] **Step 2: Run the gauntlet from `showdown_bot/`**

```powershell
$env:PYTHONHASHSEED = "0"
$env:SHOWDOWN_BATTLE_SEED_BASE = "champions-panel-v0-smoke-i7a-mega"
$env:SHOWDOWN_CALC_BACKEND = "persistent"
$env:SHOWDOWN_EVAL_SEED_LOG = "..\data\eval\champions-panel-v0\smoke-i7a-mega\seeds.jsonl"
$env:SHOWDOWN_ROOM_RAW_DUMP = "$env:USERPROFILE\.cache\showdownbot\measurements\champions-panel-v0-smoke-i7a-mega\room_raw"
python -m showdown_bot.cli gauntlet `
  --schedule "..\config\eval\schedules\champions_v0_smoke_i7a_2battle.yaml" `
  --panel "..\config\eval\panels\panel_champions_v0.yaml" `
  --result-out "..\data\eval\champions-panel-v0\smoke-i7a-mega\results.jsonl" `
  --decision-trace-out "..\data\eval\champions-panel-v0\smoke-i7a-mega\decision_trace.jsonl"
```

- [ ] **Step 3: Run report and artifact assertions**

```powershell
python -m showdown_bot.cli eval-report `
  "..\data\eval\champions-panel-v0\smoke-i7a-mega\results.jsonl" `
  --mode gate `
  --output-dir "..\data\eval\champions-panel-v0\smoke-i7a-mega"
```

Assert 2/2 rows, zero crashes/invalid choices, every row `dirty=false`, every `git_sha == $env:TASK17A_HEAD`, v3 trace rows load, and every active Scovillain slot has `mega_evolve=false` in all evaluated candidate keys.

Then run `derive_mega_evidence` (per battle, `our_side` = hero's side) over the loaded v3
trace rows. If it raises `MegaEvidenceError`, that is a real defect -- stop and fix it, do
not paper over it. If it returns `None` for every battle, the smoke is **INCONCLUSIVE**:
do not silently retry with other seeds, do not change any production threshold or scoring
to force a Mega click, and do not write `PASS`. Only if it returns a `MegaEvidence` for at
least one battle may the verdict proceed to the remaining gates.

Write the derived evidence (not raw logs) to `mega-evidence.json`: `battle_id`,
`mega_decision_index`, `turn_number`, `mega_slot`, `chosen_candidate_key`,
`post_mega_decision_index`, `post_mega_species`, plus the bound `config_hash`/`git_sha`
from that battle's result row and the sha256 of the decision-trace file it was derived
from.

A trace-level species match alone does not prove a real `detailschange`/`-mega` protocol
pair occurred (`merge_request()` can also update species from the request). While the
`SHOWDOWN_ROOM_RAW_DUMP` local cache path still exists for this run (before it is nulled),
call `mega_evidence.bind_protocol_mega_pair` against that normalized log and add its
`detailschange_line_sha256`/`mega_line_sha256`/`normalized_log_sha256` to
`mega-evidence.json` -- these are compact line/whole-log hashes, not raw log content, so
no raw room-log text is committed.

- [ ] **Step 4: Freeze only reproducible non-raw evidence and update docs**

Write `task17a_head.txt` from `$env:TASK17A_HEAD` only after the run. Set committed `room_raw_path` values to null without changing normalized log hashes.

Freeze the config manifest with `write_config_manifest_sidecar` (`eval/config_manifest_freeze.py`) -- do not hand-write `results.jsonl.config-manifest.json`; it must be produced by that function so it is guaranteed to rehash to every row's `config_hash`.

**After the `room_raw_path=null` mutation** (or any other post-hoc edit to a frozen result row), re-run result validation, regenerate `eval-report`, and call `config_manifest_freeze.verify_config_manifest_sidecar` (not a re-run of `write_config_manifest_sidecar`, which refuses to overwrite) to re-check the sidecar/result-row/live-manifest binding -- only commit after that re-verification passes.

Commit results, manifest, config manifest, seeds, trace, `mega-evidence.json`, report JSON/MD, HEAD artifact, verdict note, ROADMAP, and PROJECT_INDEX. Do not commit `_local`, raw rooms, client logs, server data, or helper scripts.

Verdict language is exactly: `I7a OWN-MEGA SAFETY PASS` only if every gate passes AND `derive_mega_evidence` returned evidence for at least one battle; otherwise name the failed axis, or write `I7a OWN-MEGA SAFETY INCONCLUSIVE — no full Mega path observed` if every other gate passed but no evidence was derived. Always include `NO I7b · NO STRENGTH CLAIM`.

- [ ] **Step 5: Re-run frozen checks and commit evidence**

```powershell
python -m pytest tests/i7a tests/test_decision_capture.py tests/test_candidate_identity.py tests/test_mega_evidence.py tests/test_config_manifest_freeze.py -q
git diff --check
git status --short
git add ..\data\eval\champions-panel-v0\smoke-i7a-mega ..\reports\champions-panel-v0-i7a-mega-smoke.md ..\docs\ROADMAP.md ..\docs\PROJECT_INDEX.md
git commit -m "eval(champions): record I7a own-Mega safety smoke"
```

## I7a-C completion gate

- Tests T41–T46 pass through real `from_log_text` and `BeliefTracker` entry points.
- A mixed reduced stream beginning with a normal `LogEvent` applies once through `from_reduced_log`; no reduction-detection heuristic exists.
- Item conflict restores species, base id, types, ability, item knowledge, and side-spend state.
- Config provenance includes verified embedded item/species data hashes at every actual manifest caller.
- Full suite passes before smoke.
- Frozen smoke has 2/2 clean result rows, zero invalid/crash, v3 traces, explicit Scovillain fail-closed evidence, no committed raw logs, and `derive_mega_evidence` returned a `MegaEvidence` (not `None`) for at least one battle -- otherwise the verdict is INCONCLUSIVE, not PASS.
- `results.jsonl.config-manifest.json` was written by `write_config_manifest_sidecar` (not hand-authored) and its hash matches every result row's `config_hash`.
- No I7b, latency-budget, or Strength claim is introduced.
