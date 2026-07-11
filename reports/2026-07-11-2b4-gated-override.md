# 2b-4 Gated Reranker Override — Closeout (2026-07-11)

**VERDICT: determinism gate PASS; dev-panel strength NO-GO (certified).** The override agent is
**NOT shipped.** The 2b-4 machinery goal — determinism gate → paired eval → certified verdict,
end to end — **is** achieved, and it correctly refused an unproven strength claim rather than
rounding a favorable-looking raw winrate up to a claim. Plan:
`docs/superpowers/plans/2026-07-11-2b4-gated-override.md`. Spec:
`docs/superpowers/specs/2026-07-11-2b4-gated-override-design.md`. Branch
`feat/slice-2b4-gated-override`, evidence git_sha `13795ab9df4f4204d90d1d295ccd3ae2e7c05019`
(clean, `dirty=False` in every manifest below).

Kaggle runs (Task 4) were controller-orchestrated, not local — this closeout commits their
evidence and reports the certified result. No battles were run to produce this report.

## 1. Determinism gate — PASS

Channel-A double-run identity check: the `heuristic_reranker` override agent run twice on the
same 24-battle seeded schedule (`config/eval/schedules/2b4_determinism_v001.yaml`), compared
battle-for-battle on winner + turns + `normalized_room_log_sha256` (the T4/T4c identity
recipe).

```
2B4-DETERMINISM: PASS (24 battles compared, 0 diff(s))
```

Both runs: `git_sha 13795ab9df4f4204d90d1d295ccd3ae2e7c05019`, `dirty=false`,
`panel_hash 760c1e5935fe0474`, `schedule_hash 1638a2d9034eb0f3`,
`seed_base 2b4-determinism-v001`, `pythonhashseed 0`, `config_hash cb5dd363dd630277`
(`heuristic_reranker`). Evidence: `data/eval/2b4/determinism/{run1,run2}/{results.jsonl,
results.jsonl.manifest.json,seeds.jsonl}` + `data/eval/2b4/determinism/determinism-verdict.txt`.

Identity before strength is non-negotiable per the spec's ordering — this gate passing is what
authorized the dev-strength run below.

## 2. Dev-panel paired strength — NO-GO (certified)

Paired McNemar, `heuristic_reranker` (override) vs `heuristic` (baseline), both vs `max_damage`
opponents, same 150 seeds over the dev panel (`panel_v001`, 3 opponent teams × 50 seeds each;
`config/eval/schedules/2b4_devstrength_v001.yaml`, `schedule_hash 9ce8872b75065c63`,
`seed_base 2b4-devstrength-v001`, `panel_hash 760c1e5935fe0474`, `git_sha 13795ab9…`,
`dirty=false` in both runs). Outcome = hero win/loss per battle.

The committed paired report (`data/eval/2b4/strength/2b4-paired-report/report.md`) labels its
two input runs generically "A"/"candidate" and "B"/"baseline" by CLI argument order, not by
which one is the actual candidate: **run A = `heuristic`** (win_rate 0.1733, 26/150),
**run B = `heuristic_reranker`/override** (win_rate 0.2600, 39/150). `delta = winrate_A -
winrate_B = 0.1733 - 0.2600 = -0.0867` — negative under the report's A-minus-B convention
because the override (B) has the *higher* raw winrate. Read for strength purposes as:
**override 26% (39/150) vs heuristic 17% (26/150), +8.7pp / +13 net wins.**

### Contingency (override vs heuristic, paired on seed)

| | heuristic won | heuristic lost |
|---|---|---|
| **override won** | n11 = 5 | n10 = 21 |
| **override lost** | n01 = 34 | n00 = 90 |

- n_discordant = 55 (n10 + n01), total = 150.
- 55 ≫ `N_DISCORDANT_CLAIM_MIN` (10) and ≫ the math floor (6) — **not UNDERPOWERED**; there is
  plenty of discordant signal, it just doesn't point decisively one way.
- **Exact two-sided binomial p = 0.10478** (n10=21 of n_discordant=55, H0 p=0.5) — **≥ 0.05, not
  significant.**
- One cell flipped **winning → losing** under the override vs the heuristic:
  `max_damage × 69f471c2740f1927` (`teams/panel_v001/rain_dev.txt`). Per the positive-evidence
  verdict tree, any losing-cell flip alone is sufficient to block GO regardless of p.
- All 20 safety gates **PASS** in both runs (rows_match_schedule, invalid_choices=0, crashes=0,
  end_reason_normal, latency_p95 within budget, seed_log_alignment, no_duplicate_rows,
  panel_hash_match, **dirty=none**, team_hashes_present, opp_hashes_subset_panel,
  split_integrity, reproducible_policies, and the one-value-per-run gates for config/schedule/
  seed_base/run_id/git_sha, manifest_match). The `dirty` gate is the one that would have
  fail-closed this whole run before the fix in §3.

**Verdict line (report.md):**
```
VERDICT: NO-GO — delta <= 0 (candidate not ahead) · p too high (p=0.1048 >= 0.05) ·
cell flip winning->losing: max_damage x 69f471c2740f1927 · weak-policy-only improvement
(flat/negative delta on heuristic+max_damage cells) · worst cell: max_damage x
69f471c2740f1927 (win_rate 0.0400, wilson upper 0.1346)
```

Evidence: `data/eval/2b4/strength/{heuristic,override}/{results.jsonl,
results.jsonl.manifest.json,seeds.jsonl}` + `data/eval/2b4/strength/2b4-paired-report/
{report.md,report.json}`.

## 3. Fail-safe override contract (spec)

The `heuristic_reranker` agent (`showdown_bot/src/showdown_bot/learning/reranker_override.py`
+ `client/gauntlet.py` dispatch) runs the heuristic to produce its decision trace and pick, then
scores the trace's own candidates with the committed reranker model
(`models/reranker/2026-07-11-2b25a-attack-lgbm.txt`) and overrides to the argmax candidate,
translated back to a legal `choose` string via the same encoder the heuristic uses. Tie-break is
an explicit lowest-`candidate_index` rule (deterministic, no RNG). **On any failure** — model
load, feature/schema-hash mismatch, `predict` error, argmax not resolvable to a legal choose
string, empty candidates — it returns the heuristic's `choose` string unchanged and never
raises. The override therefore never invents an action outside the heuristic's own legal
candidate set (INV-1) and is never worse-behaved than the heuristic on the error path. This
contract is what makes the determinism gate meaningful: the fallback path is itself
deterministic, so gate PASS or FAIL is attributable to the model-scoring path, not to
timeout/RNG noise in the fallback.

## 4. Dirty-gate finding + fix — provenance hardening (13795ab)

Task 4's first Kaggle attempt tripped the `dirty` safety gate: a partial commit of
`showdown_bot/tools/calc/node_modules/@smogon/calc` (src files without `dist/`, an artifact of
an earlier `npm ci`) meant every **fresh clone**'s own `setup_calc_bridge` `npm ci` rebuilt
`dist/` and other files, leaving the working tree dirty on a brand-new checkout before a single
battle ran. `13795ab` untracked `node_modules` (`.gitignore` +
`showdown_bot/tools/calc/node_modules/`, 145 files / 76,075 lines removed) — it is a build
artifact regenerable from the committed `package-lock.json`, not source. Both certified runs
above are on this fixed tree (`git_sha 13795ab…`, `dirty=false` in every manifest). This is a
provenance-hardening fix that benefits **every** future Kaggle-orchestrated run in this repo,
not just 2b-4 — any slice that clones fresh and runs `npm ci` for the calc bridge was exposed to
the same false-dirty failure mode before this fix.

## 5. The honest read

The raw winrate favors the override (26% vs 17%, +13 net wins over 150 paired seeds), but the
paired test does **not** certify a strength improvement — with n_discordant=55 and exact
p=0.105, a +13 net swing this size is well within what chance alone produces at this sample
size, and one previously-winning cell flips to losing under the override. This is consistent
with the 2b-2b LOCO/SCO ablation (`reports/2026-07-11-2b2b-feature-ablation.md`): the reranker's
`move_desc` and `species_id` feature classes — the ones most directly relevant to re-picking
among the heuristic's own candidates — came back `inconclusive`/not clearly load-bearing for the
model's own offline gate metric, not a robust "these features reliably reorder good choices"
signal. A live paired NO-GO at this sample size is the on-policy echo of that offline finding,
not a contradiction of it.

**Benchmark caveat:** the dev panel here is mirror-heuristic-family vs `max_damage`, where both
the heuristic and override lose the large majority of games (90/150 double-losses) — `max_damage`
rewards recklessness that neither heuristic-derived policy is built to punish efficiently. That
makes this a weak discriminator: even a certified GO here would have been comparatively weak
evidence of general strength, and a NO-GO here does not rule out the override being stronger
against a more heuristic-punishing benchmark. It is the benchmark 2b-3.5/T6 already committed to
for this comparison, so it is used as-is, but the caveat belongs on the record.

**Held-out confirmation NOT spent — deferred + user-gated.** Per the spec's explicit ordering,
held-out spend is a one-shot resource (T6 ledger, one run per `config_hash` lineage) reserved
for *after* a dev-panel GO, and only with explicit user approval. This slice produced a NO-GO on
the dev panel, so no held-out run was requested, attempted, or justified — the T6 ledger is
untouched by this slice. Any future held-out spend on this or a revised override remains a
separate decision requiring the user's explicit go-ahead.

## 6. Committed evidence

`data/eval/2b4/` (byte-pinned by `data/eval/2b4/sha256.txt`; `.gitattributes` marks
`data/eval/2b4/** -text` so checksums survive checkout on any platform):

```
data/eval/2b4/determinism/determinism-verdict.txt
data/eval/2b4/determinism/run{1,2}/{results.jsonl,results.jsonl.manifest.json,seeds.jsonl}
data/eval/2b4/strength/{heuristic,override}/{results.jsonl,results.jsonl.manifest.json,seeds.jsonl}
data/eval/2b4/strength/2b4-paired-report/{report.md,report.json}
data/eval/2b4/sha256.txt
```

Room-raw logs (24 battles × 2 determinism runs, 150 × 2 strength runs) are **not** committed —
they are large and the identity/report artifacts already carry the byte-pinned
`normalized_room_log_sha256` per row.

## 7. Suite

`cd showdown_bot && python -m pytest -q` — all green + 1 xfailed (`test_baseline.py` known
strict-xfail). No source changes in this slice; evidence + report + `.gitattributes` only.

## Cross-references

- `reports/2026-07-11-2b2b-feature-ablation.md` — the offline LOCO/SCO ablation whose
  `move_desc`/`species_id` `inconclusive` verdicts this NO-GO is consistent with.
- `docs/superpowers/specs/2026-07-11-2b4-gated-override-design.md` — fail-safe contract, gate
  ordering, held-out deferral.
- `reports/2026-07-10-2b35-T6-heldout-baseline.md` — the held-out gate/ledger machinery this
  slice deliberately did not spend against.
