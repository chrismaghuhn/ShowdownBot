# Candidate-vs-Baseline Decision Diff — fixture smoke

**Date:** 2026-07-11 · **Fixture smoke, not strength evidence.** All numbers below come from a
small, hand-built baseline/candidate fixture (4 battles, real `DecisionTraceWriter`/
`build_trace_row` sidecars, real T2 result rows, a real 4-row schedule, the real committed
`config/eval/panels/panel_v001.yaml`). **No battles were started** — this only proves the real
`decision-diff` CLI (`RunBundle.load` → `validate_trace_run` → `analyze_decision_diff` →
`build_report_object` → `render_markdown`) runs end-to-end on well-formed inputs and produces a
structurally sane report. It is not a play-strength claim about any bot configuration; the
`cfg-smoke-baseline`/`cfg-smoke-candidate` config hashes are fixture labels, not real configs.

## Command (equivalent to)

The fixture files were constructed directly (schedule.yaml, per-run manifest.json sidecars,
seedlog.jsonl, results.jsonl, decision-trace sidecars) rather than by running battles, then fed
to the same entry point `gauntlet --decision-trace-out` + `decision-diff` would produce:

```powershell
python -m showdown_bot.cli decision-diff `
  --baseline-run baseline.jsonl --baseline-seedlog baseline-seeds.jsonl `
  --baseline-trace baseline-trace.jsonl.gz `
  --candidate-run candidate.jsonl --candidate-seedlog candidate-seeds.jsonl `
  --candidate-trace candidate-trace.jsonl.gz `
  --schedule schedule.yaml --panel config/eval/panels/panel_v001.yaml `
  --teams-root showdown_bot --out report
```

`run_decision_diff` (the real, unmocked function in `showdown_bot/cli.py`) was invoked directly
with an `argparse.Namespace` carrying the paths above — no subprocess, no live server, no battle.

## Fixture design

4 battles (seed_index 0–3), same `schedule_hash`/`seed_base`/`panel_hash`/`format_id` across both
runs, differing only in `config_hash` (`cfg-smoke-baseline` vs `cfg-smoke-candidate`):

| battle | opponent (panel archetype) | baseline winner | candidate winner | decisions | what it exercises |
|---|---|---|---|---|---|
| 0 | rain (dev) | villain | hero | 1, agree | **positive flip** (`CANDIDATE_FLIP_TO_WIN`) |
| 1 | sun (dev) | hero | villain | 1, agree | **negative flip** (`CANDIDATE_REGRESSION_TO_LOSS`) |
| 2 | trick_room (dev) | hero | hero | 3; agree at 0–1, observable state diverges at index 2 | **later state suffix** (divergence at index 2, not index 0 — `state_divergence_index: 2`, `baseline_suffix_count`/`candidate_suffix_count`: 1 each) |
| 3 | balance (held-out) | villain | villain | 2; agree at 0, direct action divergence at 1 | **direct policy divergence** (`ATTACK_MOVE`: fakeout → flareblitz, same target) |

Hero team is the real `teams/fixed_team.txt`; opponent teams are the real panel_v001 dev/held-out
teams (their real content-hashed `team_hash`, used by `analyze_decision_diff`'s matchup-bucket
archetype lookup). `schedule_hash` was computed by the real `load_schedule` from the fixture
`schedule.yaml`; `battle_id`/`seed` were computed by the real `make_battle_id`/
`derive_battle_seed`; `decision_trace_count`/`decision_trace_sha256` were produced by the real
`DecisionTraceWriter.finish_battle`, exactly like a real `gauntlet --decision-trace-out` run
would bind them.

## Fixture files and hashes (sha256, uncompressed unless noted)

| file | sha256 |
|---|---|
| `schedule.yaml` | `d2bf27554eef59e20359587392b2a2b200b3681575f43bf1911e8269cc0e5ee1` |
| `config/eval/panels/panel_v001.yaml` (real, committed) | `13474d0f6766c08be14d1e38a410f3e52ef266f6676b75d28cfd478efe56ba9c` |
| `baseline.jsonl` (4 result rows) | `a49e12bb49ce997fb761674c34603990328aa12596a902464acd508c08560b1b` |
| `baseline.jsonl.manifest.json` | `05a3e75294c576fa364104876848eb2934895dc73a1353baf2887f9e9522e217` |
| `baseline-seeds.jsonl` | `e29d068161c9b45d5f4d30e58d719e028a48f17b84462aaa137b23888314b742` |
| `baseline-trace.jsonl.gz` (7 decision rows) | `84f9c513848add5972574dae7d53dc8e3ebe1c11c77121c1db7b576462199ed8` |
| `candidate.jsonl` (4 result rows) | `c689fa3ecd2d48b11574743aaacb894ce5cd9e3c9870c8a0b838f9b4b42a2e60` |
| `candidate.jsonl.manifest.json` | `2212637f3dd2f0943fa5de4602d4df6ca952385ab68b7662594e9793dc612799` |
| `candidate-seeds.jsonl` (identical content to baseline's — same schedule/seed_base) | `e29d068161c9b45d5f4d30e58d719e028a48f17b84462aaa137b23888314b742` |
| `candidate-trace.jsonl.gz` (7 decision rows) | `ed7f6575b921a82887fe4eaf3eaf2eee60d5dd3fd853736d099fd0a13d002dff` |
| `report/report.md` (CLI output) | `6d4fd867ecfaace39d7c91451d36e713bdcaf1fccd11da990388f0bd82d5bef8` |
| `report/report.json` (CLI output) | `2839cc777fc87d8c21f6eca9ada4e493d7ed4defed413708da852678eaec6421` |

Derived provenance: `schedule_hash = e452ec9dc45911e2`; `panel_hash = 760c1e5935fe0474` (matches
the panel's real, previously-published hash — see `tests/test_eval_report.py`).

None of these fixture files are committed (they are throwaway, regenerable from the fixture
recipe above); only this summary and its hashes are.

## Full-mode integrity and coverage (real `analyze_decision_diff` output)

```json
{
  "capability_mode": "full",
  "integrity": {
    "paired_battles": 4,
    "battles_with_decision_comparison": 4,
    "directly_comparable_decisions": 6,
    "direct_agreements": 5,
    "direct_divergences": 1,
    "battles_with_state_divergence": 1
  },
  "decision_differences": {
    "comparable": 6,
    "agreements": 5,
    "divergences": 1,
    "by_primary_class": {"ATTACK_MOVE": 1}
  }
}
```

## Outcome flips (both categories exercised)

| category | count |
|---|---|
| BOTH_WIN | 1 |
| BOTH_LOSS | 1 |
| `CANDIDATE_FLIP_TO_WIN` (positive) | 1 |
| `CANDIDATE_REGRESSION_TO_LOSS` (negative) | 1 |
| NON_BINARY | 0 |

## Direct divergence and later state suffix

- **Direct divergence** (battle 3, held-out `balance`): decision index 0 agrees (same observable
  state, same normalized action); decision index 1 has the same observable state on both sides but
  a different action — baseline chose `fakeout@1`, candidate chose `flareblitz@1` — classified
  `ATTACK_MOVE`, recorded as `first_divergence` for that battle.
- **Later state suffix** (battle 2, dev `trick_room`): decisions 0 and 1 agree (both observable
  state and action). At decision index 2 the observable state itself diverges (not the first
  decision), so `compare_battle_decisions` stops comparing there: `state_divergence_index: 2`,
  with one decision left uncompared on each side (`baseline_suffix_count: 1`,
  `candidate_suffix_count: 1`) — the "different-length suffix after divergence" case, occurring
  after two decisions of agreement rather than immediately.

## Matchup buckets (all `n=1`, correctly flagged `underpowered`)

| hero archetype | opponent archetype | policy | lead | n | candidate win rate | underpowered |
|---|---|---|---|---:|---:|---|
| unclassified | balance | max_damage | Incineroar+Rillaboom | 1 | 0.0 | true |
| unclassified | rain | max_damage | Incineroar+Rillaboom | 1 | 1.0 | true |
| unclassified | sun | max_damage | Incineroar+Rillaboom | 1 | 0.0 | true |
| unclassified | trick_room | max_damage | Incineroar+Rillaboom | 1 | 1.0 | true |

(`hero_archetype` is `unclassified` because the fixture's hero team is `teams/fixed_team.txt`,
which is not itself a panel-listed team — expected, real behavior of the archetype lookup, not a
bug.)

## Existing paired strength evidence (unchanged gate, carried through verbatim)

`n_discordant = 2` (below `N_DISCORDANT_CLAIM_MIN`), `exact_two_sided_p = 1.0`,
`candidate_minus_baseline_winrate = 0.0` — this fixture is far too small to support any strength
claim, and the report says so structurally (this section is the pre-existing paired-statistics
output, not a new gate). This confirms the report never manufactures a strength verdict of its
own: the McNemar block is a pass-through of `paired_strength_summary`, identical in shape to a
real run's.

## Stability and regressions

No repeat traces were supplied, so `stability` reports the real, honest
`{"status": "not_provided"}` for both sides (not fabricated). `regressions` are all `0` except
`candidate_regression_to_loss: 1` (battle 1, the negative flip) — no fallback/timeout/crash/
latency-budget regressions were built into this fixture.

## Limitations

Fixture smoke, not strength evidence. This run verifies the `decision-diff` CLI executes
end-to-end on well-formed, hand-built inputs — including the full `RunBundle.load` file/provenance
audit, `validate_trace_run`'s sidecar-binding checks, `analyze_decision_diff`'s pairing (the
Task 7 `pair.battle_id` fix), and deterministic `report.md`/`report.json` rendering — and produces
a structurally valid, internally consistent report. It draws no conclusion about any real bot
configuration, cites no held-out or committed raw evaluation data, and starts no battles.
