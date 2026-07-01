# 2b-3.5 T3d — Panel-Load Smoke (2026-07-01)

The last T3 piece: turn `panel_v001` into T1c schedules (dev/held-out gated) and prove a tiny
generated dev schedule **loads + runs** end-to-end. This is a *load + runs* smoke — the full
~50-game smoke is **T4**. Branch: `feat/slice-2b35-t3d-panel-schedules-smoke`.

## What was built
- **`eval/panel_schedule.py`** — `generate_dev_schedule(panel, policies=None, seeds_per_cell=1,
  allow_nonreproducible=False)` (dev_team × policy cells, contiguous `seed_index` from 0, `format_id`,
  `panel_hash` on the schedule); **reproducible-only by default** — `random`/non-reproducible policies
  require `allow_nonreproducible=True` and then `Schedule.reproducible=False` (T3-CC-3);
  `generate_heldout_schedule(…, confirm_heldout=True)` **raises unless `confirm_heldout=True`** (T3-CC-1);
  `write_schedule_yaml` emits a YAML the existing `eval/schedule.load_schedule` round-trips.
- **`eval/schedule.py`** — `Schedule.panel_hash` (loader reads a top-level `panel_hash:` key; legacy →
  `None`) + a computed `reproducible` property; `compute_schedule_hash` shared by loader + generator.
- **`cli.run_schedule`** — writes `schedule.panel_hash` into each T2 result row (Fix 6); legacy → `null`.

## Generation checks (unit — 7 tests)
Reproducible-only default (random excluded), random gated by `allow_nonreproducible`, held-out gated by
`confirm_heldout`, dev never contains a held-out team, contiguous seeds, `seeds_per_cell`, and a
**round-trip** (`write_schedule_yaml` → `load_schedule` keeps `schedule_hash` stable + `panel_hash`).

## Smoke — tiny generated dev schedule
`panel_v001` (panel_hash `9aa3af95e461881f`) → `generate_dev_schedule(policies=["scripted_vgc"])` →
**3 battles** (our `fixed_team` vs each dev team: trickroom / sun / rain), opponent = `scripted_vgc`
(a **new T3c policy**, for live coverage). `write_schedule_yaml` → run via `gauntlet --schedule …
--result-out …`, fresh seeded server (`SHOWDOWN_BATTLE_SEED_BASE=t3d2026`), `PYTHONHASHSEED=0`.

| Gate | Result |
|---|---|
| Schedule loads + runs | 3 battles ran; `schedule_hash=724be4c1f00933eb`, `reproducible=True` |
| Safety | **0 invalid · 0 crashes** |
| Result rows | 3 written (one per row), **all validate** on re-read |
| `panel_hash` in rows | **all == `9aa3af95e461881f`** ✅ |
| Seed-log alignment | OK — `seed_i == derive_battle_seed(t3d2026, seed_index)` |
| New-policy coverage | `scripted_vgc` played all 3 (hero won 3/3 — scripted is deliberately weak) |

## VERDICT: **panel-load smoke PASS** → parent-plan **T3 (Panel v001) complete**
Panel loads + hashes (content team_hash), dev/held-out split mechanically enforced, schedules generate
with contiguous seeds + `format_id` + `panel_hash`, a tiny dev run is clean, held-out generation is
gated. **Unlocks T4** (the real ~50-game smoke schedule).

## Carry-forward: policy-fidelity debt (NOT a T3d blocker)
The T3c policies are minimal, request-only baselines. Before T4/T5, decide whether to strengthen:
- **`simple_heuristic`** is base-power-greedy (highest-BP move), **weaker than the spec's type-aware
  competence baseline** — no type effectiveness, no state.
- **`greedy_protect`** protects **whenever a Protect move is available**, not situationally.
- Consider **type-aware / simple-state logic** + **consecutive-Protect damping** so these are competent
  (not stall-prone) opponents for meaningful paired Δ. `scripted_vgc` is intentionally weak (mechanic
  coverage), so it is exempt.
These do not affect T3d correctness (all smokes clean); flagged for a pre-T4 decision.

## Reproduce
```bash
cd <repo>/showdown_bot
python -c "from pathlib import Path; from showdown_bot.eval.panel import load_panel; \
from showdown_bot.eval.panel_schedule import generate_dev_schedule, write_schedule_yaml; \
sb=Path.cwd(); p=load_panel(str(sb.parent/'config/eval/panels/panel_v001.yaml'), teams_root=str(sb)); \
write_schedule_yaml(generate_dev_schedule(p, policies=['scripted_vgc']), '/tmp/dev.yaml')"
# fresh seeded server (SHOWDOWN_BATTLE_SEED_BASE + SHOWDOWN_EVAL_SEED_LOG), then:
PYTHONHASHSEED=0 SHOWDOWN_CALC_BACKEND=persistent SHOWDOWN_BATTLE_SEED_BASE=t3d2026 \
  SHOWDOWN_EVAL_SEED_LOG=/tmp/seeds.jsonl \
  python -m showdown_bot.cli gauntlet --schedule /tmp/dev.yaml --result-out /tmp/results.jsonl
```

**STOP** — T3d done (generator + gates + tiny smoke). Awaiting review; **not merged**. No T4/T5/T6/override.
