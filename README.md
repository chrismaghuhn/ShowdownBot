# ShowdownBot

Competitive **Pokémon Showdown VGC Doubles** bot — custom protocol client, exact-mechanics engine
(`@smogon/calc` bridge + one-ply tactical resolver), a learned action reranker on top of a
heuristic core, and a **fully reproducible evaluation harness**: every battle is seeded,
provenance-pinned, and byte-for-byte replayable.

## Highlight: byte-reproducible bot-vs-bot evaluation

Pokémon battles are full of randomness (damage rolls, crits, speed ties). This repo makes **our
local bot-vs-bot eval matches** — under a pinned Showdown commit, a versioned seed patch, fixed
schedules, deterministic clients, and a fresh server per run — byte-identically reproducible.
(Scope note: this is about the local eval harness, not arbitrary ladder replays; Showdown keeps
seeds of non-random ladder games private by design.)

1. **Server seeding** — a versioned patch
   ([tools/eval/patches/](tools/eval/patches/)) injects a derivable per-battle seed
   (`sha256(base:index)`) into the Showdown server and logs every seed.
2. **Client determinism** — `PYTHONHASHSEED` pinned; every decision path deterministic (the
   reproducibility gate itself caught and killed a hidden unseeded-random fallback — see
   [reports/2026-07-10-2b35-T4-smoke.md](reports/2026-07-10-2b35-T4-smoke.md)).
3. **Run discipline** — fixed battle order, fresh server per run, **no retries ever**; every run
   carries its full provenance (config/panel/schedule/team hashes, git sha, server commit+patch
   hash) in a manifest sidecar.
4. **Proof, not trust** — normalized battle logs are compared **byte-for-byte**; two independent
   51-game runs match 51/51 ([reports/2026-07-10-2b35-T4-rerun.md](reports/2026-07-10-2b35-T4-rerun.md)),
   and the same battles reproduce exactly on foreign cloud hardware
   ([data/eval/kaggle-validation/](data/eval/kaggle-validation/)).

On top of that sits a statistics layer built for honest claims: paired exact-binomial McNemar with
a positive-evidence-only rule, per-cell Wilson intervals, safety gates before any strength
statement, an append-only **held-out access ledger** with a per-config budget, and a frozen,
drift-verified baseline manifest ([config/eval/baselines/](config/eval/baselines/)).

## Status

| Phase | State |
|---|---|
| 0–0.5 Protocol client, auth, teams, CLI | ✅ |
| 1 Offline engine: parser, `BattleState`, calc bridge, belief tracking | ✅ |
| 2 Heuristic doubles bot (resolver, oracles, game modes, Tera, fallbacks, gauntlet) | ✅ |
| 3 Learned reranker — data pipeline (frozen schema, counterfactual rollout teacher, internal turn simulator, persistent calc), offline LightGBM reranker, live shadow mode | ✅ |
| 3 **Eval harness 2b-3.5** (T0–T6): seeded battles, opponent panel, per-battle result JSONL, report generator (`eval-report`), held-out gate + baseline | ✅ |
| 3 Enriched retrain (panel-diverse dataset generated on Kaggle) | 🔄 in progress |
| 3 Gated override (paired McNemar vs pinned baseline) | ⏳ next |

Architecture: **Preview → Belief → Policy → Search → Fusion** (heuristic core = candidate
generator and safety floor; learned components rerank, never overrule legality/safety).

## Quick start

```bash
cd showdown_bot
pip install -e ".[dev]"
npm ci --prefix tools/calc   # @smogon/calc bridge deps (node_modules is a build artifact, not committed)
python -m pytest -q          # 850+ tests
python -m showdown_bot.cli replay-fixture
```

The `@smogon/calc` damage bridge runs on Node. `node_modules/` under `tools/calc/` is **not**
committed (it made cloud clones dirty and fail-closed the eval-harness safety gate) — run
`npm ci --prefix tools/calc` once after checkout, or the calc-backed tests will fail.

### Local gauntlet + seeded, reproducible eval

Local server setup: `showdown_bot/tools/localserver/README.md` (clone Showdown, apply the seeded-
battle patch). Then:

```bash
# plain gauntlet
python -m showdown_bot.cli gauntlet --games 20 --villain max_damage --strict

# fully seeded, schedule-driven run (fresh server started with SHOWDOWN_BATTLE_SEED_BASE + SHOWDOWN_EVAL_SEED_LOG)
PYTHONHASHSEED=0 SHOWDOWN_CALC_BACKEND=persistent SHOWDOWN_BATTLE_SEED_BASE=mybase \
  SHOWDOWN_EVAL_SEED_LOG=/tmp/seeds.jsonl \
  python -m showdown_bot.cli gauntlet --schedule ../config/eval/schedules/t4_smoke_v001.yaml \
  --result-out /tmp/results.jsonl

# audited report (safety gates -> Wilson tables -> paired McNemar in two-run mode)
python -m showdown_bot.cli eval-report --run-a /tmp/results.jsonl --seedlog-a /tmp/seeds.jsonl \
  --schedule ../config/eval/schedules/t4_smoke_v001.yaml \
  --panel ../config/eval/panels/panel_v001.yaml --out /tmp/report
```

### Ladder / challenge

```bash
cp .env.example .env   # SHOWDOWN_USERNAME / SHOWDOWN_PASSWORD
python -m showdown_bot.cli ladder -v
python -m showdown_bot.cli challenge --opponent TheirUsername -v
```

### Dataset / reranker audit (offline)

Deterministic, fail-closed audit of any schema-compatible reranker dataset — integrity, cross-split
leakage (exact/semantic/near-duplicate), label invariants, feature health/drift/OOD, and (with a
model + manifest) calibration:

```powershell
python -m showdown_bot.learning.audit `
  ../data/datasets/phase3-slice2b25a/dataset.jsonl.gz `
  --out ../reports/audit-2b25a
```

Writes `audit.json` / `audit.md` / `split-manifest.json`; exit 0 on `AUDIT PASS`, 1 on `AUDIT FAIL`.
It proves **dataset/model trust, not play strength** — it never mutates rows, trains, runs battles,
or touches held-out data, and no live/battle/teacher/inference path imports the audit package.

## Repo map

| Path | What |
|---|---|
| `showdown_bot/src/showdown_bot/battle/` | Live decision core (resolver, evaluation, policy, fallbacks) |
| `showdown_bot/src/showdown_bot/engine/` | Calc bridge, belief/spread book, format config |
| `showdown_bot/src/showdown_bot/eval/` | The harness: seeding, schedules, panel, result rows, stats, pairing, report, ledger, baseline |
| `showdown_bot/src/showdown_bot/learning/` | Frozen dataset schema, feature extraction, rollout teacher, reranker train/eval, shadow runtime |
| `config/eval/` | Panels, schedules, gates, baselines, held-out ledger |
| `data/eval/` | Committed run evidence (sha256-pinned): T4/T4-rerun, T6 held-out baseline, Kaggle validation |
| `data/datasets/` | Training datasets (gz + manifest) |
| `tools/kaggle/` | Cloud runners: repro-validation + datagen kernels, API driver |
| `reports/` | Every eval run's report — verdict-first, fully provenanced |
| `docs/superpowers/` | Specs, plans, and review artifacts for every slice |

## Ground rules (enforced by tests)

- The live path only ever plays **legal** actions; the heuristic is the safety floor.
- **No label leakage**: model inputs are the frozen feature columns, never labels/outcomes.
- Model artifacts carry dataset/schema/config hashes; a mismatch at load falls back to heuristic-only.
- Held-out teams: append-only ledger, one gate attempt per config lineage, numbers never inform tuning.
- No battle-level retries; a non-reproducible run is a void run.

## License

Private hobby project.
