# Champions I8 — Post-Lever-A Latency Diagnosis & Next-Slice Design

**Status:** `APPROVED` — offline diagnosis basis (Codex review PASS, 2026-07-19). It authorizes **no** code, test, run, gate, or implementation. Lever B and a persistent-backend stratum are recommended candidates but remain **NOT** authorized or approved.

*(Rev. 3 — Rev. 2 corrections (live decision-neutrality not provable from the sidecar; equal net spawn count ≠ equal transport path; `requests_unique ≥ 1` does not prove an incoming request; `transport_retried` was a spurious accounting flag; the tail moved non-uniformly; persistent is a hypothesis, not a proven path to PASS) plus the Rev. 3 review corrections: the median speed-up is stated as the post-Lever-A run's with cause unattributed; the active-valid 1-spawn heavy span is `254.42–320.62 ms`; the "only git_sha differs" claim is scoped to bound single-valued provenance fields.)*

*(Erratum 2026-07-19 — the shorthand "via the fold pattern Lever A proved safe" (§7 candidate 1, §8) is imprecise: stats/types have **no collecting oracle** and `SpeedOracle.opponent_range` bypasses its cache (`speed.py:133`), so Lever B is a **decision-level collection design that requires a `SpeedOracle` cache-first refactor** for any cross-kind win — NOT a drop-in Lever-A fold. See the Lever B design spec `docs/superpowers/specs/2026-07-19-champions-i8-lever-b-stats-types-design.md` §1/§5. The Lever-A design/plan remain the historical implemented contract, unchanged.)*

## 0. Purpose

Explain, from the two frozen I8-D live-gate datasets alone, (a) whether the runs are comparable, (b) whether the Lever A fold reduced the mechanical calc-spawn count **live**, (c) what the bytes do and do **not** say about why the post-Lever-A gate p95 was still a FAIL, and (d) which next latency slice is technically justified. Everything below is derived from the committed evidence bytes; where the bytes are insufficient it is stated as such.

## 1. Evidence provenance (verified this session)

Both datasets are committed on `main @ 34b088e` (PR #32) and re-hashed before analysis; all six files matched their recorded SHA-256 (no drift):

| run | dir | file | sha256 | bytes |
|---|---|---|---|---|
| pre-Lever-A | `data/eval/champions-panel-v0/i8d-live/` | `profile.jsonl` | `d3f76e2b80a0607f3fa2d748155ae7af38eee62cd948a8f37f2614605dcf726c` | 689263 |
| | | `verdict.json` | `af8ce71413ec316257669e601569b73261ef2df55741f8d00f5459c7a5d4fcc1` | 700 |
| | | `seeds.jsonl` | `4d4ad59c2f78a938ce531670f45b4b7fd2371daae11fbb7b66a283b2edb76c6b` | 8540 |
| post-Lever-A | `data/eval/champions-panel-v0/i8d-live-post-lever-a/` | `profile.jsonl` | `c8501ef43fed606fb7fcb5a683ca0867289c8d50f0c2d09dd12c17b18cad2a40` | 690032 |
| | | `verdict.json` | `175b345a010bbaf9cb6f5d7af134be810a3590624d8be309d1c10feb9da4c0b8` | 700 |
| | | `seeds.jsonl` | `4d4ad59c2f78a938ce531670f45b4b7fd2371daae11fbb7b66a283b2edb76c6b` | 8540 |

Both `seeds.jsonl` are byte-identical (same digest) — deterministic Channel-A seeds ⇒ the same 75 battles. Both verdicts re-validate (`validate_live_profile_dataset`, `showdown_bot/src/showdown_bot/eval/decision_profile.py:1014`) to **679 rows / 60 active-valid / 45 distinct battles / 75 seeds**. Bound stratum identical across every row: `config_hash 594295543f13a55d`, `schedule_hash a1192d9dde4c65df`, `panel_hash aac1ea30446fde88`, `calc_backend oneshot`, budget 1000 ms, D-1/D-2 unchanged. The only single-valued provenance field that differs is `git_sha` (`9fc0f36…` → `9d915f2…`).

| | pre-Lever-A | post-Lever-A |
|---|---|---|
| verdict | `FAIL` | `FAIL` |
| active foe-Mega p95 | **1110.213 ms** | **1160.515 ms** (`1160.5149999959394`) |
| active-valid / distinct battles | 60 / 45 | 60 / 45 |
| battles / scored decisions | 75 / 679 | 75 / 679 |
| `stop_reason` | `exposure_floor_met` | `exposure_floor_met` |

## 2. Methodology (reproducible, offline)

- **Join key:** decision identity `(battle_id, decision_index)` — the same identity the live-dataset validator uses for uniqueness (`decision_profile.py:1014`).
- **Verdict population:** `is_active_valid_live_row` (`decision_profile.py:997`): `source=="live" ∧ timer_scope=="agent_choose" ∧ outcome=="ok" ∧ foe_mega_active is True`.
- **p95:** `_latency_p95` (`showdown_bot/src/showdown_bot/client/gauntlet.py:181`), nearest-rank, no interpolation. n=60 ⇒ p95 index `min(59, round(0.95·59)) = 56`.
- **Counters** are read from the frozen `profile.jsonl` (schema `decision-profile-v1`, 41 fields), populated by `CalcClient` (`showdown_bot/src/showdown_bot/engine/calc/client.py`: `transport_attempts` :56/:73/:108, `stats_batch_calls` :58/:137/:324, `types_batch_calls` :59/:148/:335). **The 41 fields carry row identity, populations, outcome, shape telemetry and counters — but NOT the chosen action, score vector, tie-break order, or resolved `GameMode`.**
- Read-only pass over the two frozen files. No mutation, no server, no run.

## 3. Comparability — pairable on everything the sidecar carries (MEASUREMENT)

- `(battle_id, decision_index)`: **matched = 679 / 679**, `pre_only = 0`, `post_only = 0`.
- Per-paired-row mismatches are **0** for `outcome`, `foe_mega_active`, `timer_scope`, `source`, and all shape telemetry — `n_candidates`, `n_responses`, `n_mega_twins`, `n_branches`, `n_worlds`, `depth2_frontier`.
- Verdict populations are the **same 60 gate rows** (symmetric difference = 0). Battle-id sets identical; seeds byte-identical. Among the bound single-valued provenance fields, only `git_sha` differs; the per-row counters and `measured_ms` differ, as expected.

**Conclusion (measurement):** the runs are pairable at full coverage on identity, population, outcome and shape. A paired comparison is valid.

**Scope limit (corrected):** the sidecar does **not** carry the chosen action / score vector / tie-break / `GameMode`, so **live behaviour-neutrality of the decision cannot be proven from this profile.** The identical shape/outcome/population is *consistent with* neutrality but is not itself proof. The separate evidence for behaviour-neutrality is the committed **offline golden decision-equivalence test** (`showdown_bot/tests/test_decision_equivalence_golden.py`), which pins the full ranked candidate list byte-identical pre/post fold on a Reg-I and a Champions board. Cite that, not this profile, for neutrality.

## 4. Did Lever A reduce the spawn counter live? YES (MEASUREMENT), with the accounting stated precisely

Spawn composition totals (sum over all 679 rows):

| | spawn_calls | damage_batch | stats_batch | types_batch | rows with `transport_retried` (pre-fold flag) |
|---|---|---|---|---|---|
| pre-Lever-A | **2447** | 587 | 401 | 511 | 571 |
| post-Lever-A | **1786** | 874 | 401 | 511 | 0 |

Answers to the Step-2 questions, from bytes:

1. **`spawn_calls` dropped on 529 / 679 rows** (0 increased, 150 unchanged); gate rows 42 / 60 dropped.
2. **By how much:** Δ = −1 on 397 rows, −2 on 132 rows, 0 on 150 rows (gate: −1 on 39, −2 on 3, 0 on 18).
3. **Conditional-outgoing cache-served:** the folded outgoing became a shared damage batch when *not* cache-served (`damage_batch_calls` +1 on 253 rows, +2 on 17), and rode the cache on 409 rows (+0). Gate `damage_batch_calls` moved from `{0:5, 1:55}` (pre) to `{1:9, 2:51}` (post).
4. **Rows without an incoming classification request:** **not determinable from the frozen sidecar** — `requests_unique` pools classification *and* scoring requests, so `requests_unique ≥ 1` does not isolate an incoming request. (Gate `requests_unique` min/median/max = 1 / 24 / 36, but that does not settle the question.)
5. **Counter accounting:** pre-fold, `spawn_calls` exceeded `damage_batch_calls + stats_batch_calls + types_batch_calls` on **571** rows — an observed **accounting gap** (≈ **948** spawns in total, `spawn_calls − (dmg+stats+types)`), because the pre-fold game-mode oracle issued **direct classification batches that were not recorded in `transport_calls`**. The `transport_retried` flag on those 571 rows was a **spurious artifact of that accounting gap, not a real transport retry.** Post-fold the gap closes: `spawn_calls == dmg+stats+types` on all 679 rows, `transport_attempts == transport_calls` on all 679, and the `transport_retried` flag is 0.
6. **Mechanism exercised live:** yes. The ≈948-spawn classification accounting gap is gone; the incoming folded into the shared flush and the conditional outgoing became a bounded second shared flush. Net **−661 spawns (2447 → 1786, −27 %)**; gate −45 (360 → 315).

"Lever A works" here means only this **mechanical counter effect** — not the gate outcome.

## 5. What the bytes say about the p95 (DESCRIPTIVE; no causal Lever-A claim)

### 5A. The median got much faster; the tail rose

`measured_ms` over all 679 paired rows: p50 **423.11 → 296.30 ms (−30 %)**, p90 1125.90 → 1155.37, p95 1149.98 → 1218.33. Paired `post_ms − pre_ms`: **median −113.85 ms** (all 679), −63.57 ms (60 gate); **558 / 679 rows faster, 121 slower.** The post-Lever-A run's typical decision was decisively faster (the cause is **not** identified — this run-pair does not attribute it); the **tail (p95)** — what the gate measures — rose.

### 5B. What is clean, and what is not (corrected)

- **Clean (measurement):** every row with a **negative** `spawn_calls` delta got **faster** — all 132 (−2) and 397 (−1) spawn-reduced rows. **No** paired row both lost a spawn and got slower.
- **Not clean:** the 121 slower rows all have **net** `spawn_calls` Δ = 0, but **equal net spawn count is not equal transport path.** Of the 150 net-unchanged-spawn rows, **42 also changed batch composition** (`damage_batch_calls` +1 on 25, +2 on 17); and this is exactly where the slow rows live — **all 18 net-unchanged gate rows and all 15 slower gate rows had `damage_batch_calls` rise by 1–2** (a removed classification transport replaced by an added shared damage batch). On these rows both a **changed batch composition** and **host run-to-run variance** could have contributed to the latency, and **this single run-pair does not causally separate them.**
- The 150 net-unchanged-spawn rows show a median `measured_ms` move of **+15.32 ms** (1118.87 → 1149.32) — reported as a **mixed** quantity (composition change + variance), not as isolated host drift.

### 5C. The gate p95 is a variance-sensitive tail order-statistic (MEASUREMENT)

- p95-determining row **switched**: pre `(0078733c…, 2)` 1110.21 ms → post `(817a07a7…, 4)` 1160.51 ms.
- The upper tail moved **non-uniformly** and reshuffled. Position-wise, gate ranks 55–59 changed by **+45.07, +50.30, +55.03, +14.39, +30.61 ms** (pre `1109.79, 1110.21, 1112.54, 1183.82, 1187.72` → post `1154.87, 1160.51, 1167.58, 1198.20, 1218.32`). Neighbouring gate latencies sit within ~2–60 ms, so a small wall-clock difference reshuffles which row lands on index 56.
- Both p95 rows are the heaviest foe-Mega shape (`n_candidates=45`, `n_responses=225`); the post p95 row has 8 spawns = 2 damage + **3 stats + 3 types** (75 % stats/types).

*(Descriptive only. No stability threshold is proposed; the gate is not changed.)*

### 5D. Residual mechanism — stats/types now dominate the spawn budget (MEASUREMENT)

After Lever A, **`stats_batch_calls (401) + types_batch_calls (511) = 912 = 51.1 %** of the 1786 remaining spawns**, entirely untouched by Lever A (gate stats 100→100, types 104→104). The heaviest tail decision is 75 % stats/types spawns. Damage is now 874 (49 %).

### 5E. The 141.7 ms / 968.513 ms model figures

Cost-per-spawn `measured_ms / spawn_calls`: pre **p50 = 141.75 ms**, post **p50 = 154.92 ms**. The design's "141.7 ms constant" was, to three figures, the **pre-Lever-A run's own median cost-per-spawn** — a single run's median, not a constant. The `968.513 ms` projection assumed that constant and one removed spawn; observed p95 is **1160.515 ms**, so the projection **did not materialize**. *(Caveat: cost-per-spawn is a ratio whose denominator Lever A changed; removing a below-average-cost spawn mechanically raises the ratio, so 5E is an observation, not a mechanism.)*

## 6. Measurement vs observation vs model vs hypothesis

- **Measurement (from bytes):** §3 full pairing on identity/population/outcome/shape; §4 counter totals, −661 spawns, accounting-gap closure, invariant restored; §5A paired latency diffs; §5B negative-spawn rows all faster **and** the composition change on the net-unchanged/slower rows; §5C non-uniform tail + p95-row switch; §5D stats/types = 51.1 %.
- **Descriptive observation:** median improved while the tail rose; the slow rows co-occur with composition change and are variance-sensitive.
- **Model:** the constant-141.7-ms projection (§5E) — a single-run median, falsified as a bound.
- **Not provable from this sidecar:** live decision behaviour-neutrality (needs the offline goldens, §3); whether any given row issued an incoming classification request (§4.4); a causal split of composition-change vs host variance on the net-unchanged-spawn rows (§5B).
- **Hypothesis (open):** that the residual tail is governed by the oneshot per-spawn cost of the stats/types transports and by host variance. Consistent with the data; not proven by one run-pair.

## 7. Next-slice candidates

1. **Lever B — consolidate the stats + types transports.**
   - *Mechanism (evidenced):* stats/types are 912 spawns = **51.1 %** of the post total and untouched; each is a separate `CalcClient` transport (`client.py:137/:148/:324/:335`). Folding them (mirroring Lever A's oracle fold) targets a strictly larger spawn count than the damage Lever A removed.
   - *Expected counter effect:* fewer stats/types spawns on the heavy foe-Mega rows that populate the tail (the post p95 row is 75 % stats/types).
   - *Surface:* `engine/calc/client.py` stats/types batch paths + callers. *Risk:* behaviour/error-domain — stats/types feed speed and type-effectiveness; a fold must be proven byte-identical offline (golden decision-equivalence, as Lever A was).
   - *Counterproofs needed (offline):* RED→GREEN + golden-equivalence + counter-invariant harness; a paired offline spawn-count delta.
   - *New design decision:* yes — its own PROPOSED design + plan.
   - *Why stronger:* largest evidenced localized spawn source; proven-safe fold pattern.
   - **Open:** Lever A reduced spawns 27 % and the gate still failed; whether Lever B's further reduction would close the **oneshot** 1000 ms gate is **unproven** by these data.

2. **Other localized oneshot round-trips.** No other single counter dominates (damage 49 %, types 29 %, stats 22 %). No stronger single candidate than stats/types is visible. *Lower priority.*

3. **Persistent backend — a separate-stratum HYPOTHESIS, not a proven path to PASS (corrected).** The frozen I8 microprofile recorded persistent ≈ 144 ms cold / **≈ 10 ms warm** per call vs oneshot ≈ 142–255 ms/spawn (`reports/champions-panel-v0-i8-microprofile.md`). But the data do **not** show that heavy decisions "sit near the budget regardless": among the **active-valid** heavy-shape (45 candidates / 225 responses) rows the **median is 885.629 ms** (under 1000 ms), and the five **active-valid** 1-spawn (cache-served) heavy rows run **254.42–320.62 ms** (`254.4195–320.6166`). So spawn-count reduction is **not** shown to be futile, and persistent is **not** proven to close the gate. Persistent may be proposed **only as its own stratum with its own separately-authorized gate run** (different `config_hash`; strata never pooled) — a hypothesis requiring a controlled measurement, not a silent swap of the unchanged oneshot gate.

4. **Gate/measurement stability (diagnostic question only).** §5C shows the single-run oneshot p95 is variance-sensitive at this ~110–160 ms-over-budget margin (p95-row switch; non-uniform tail; neighbours within tens of ms). A legitimate diagnostic question about the estimator — **not** a licence to change the pinned 1000 ms budget or exposure rules.

5. **"No further optimization derivable"** — rejected: stats/types (Lever B) is a clear, evidenced spawn target.

## 8. Recommendation

- **Strongest evidenced localized oneshot candidate: Lever B (stats/types transport consolidation)** — 51.1 % of remaining spawns, concentrated on the tail rows, via the fold pattern Lever A proved safe. It is the right next **offline design** slice *if* the goal is to keep reducing the oneshot spawn count. It must go through its own PROPOSED design → plan → RED→GREEN implementation → separately-authorized gate; it is **not** approved here.
- **Open question left open (corrected):** the data do **not** determine whether **Lever B** (further spawn reduction) *or* a **persistent-backend stratum** (lower per-call cost) — or neither — would close the 1000 ms gate. Spawn-minimal heavy decisions already run well under budget (§7.3), so reduction is not shown futile; equally, the oneshot per-spawn cost and tail variance are real. Both are **separate design decisions requiring their own controlled gate**; neither is proven and neither is approved. A human decides which to design next.

## 9. Explicit non-claims

- **No causal Lever-A latency effect** is claimed. No paired row both lost a spawn and got slower, and the post-Lever-A run's median decision was faster — but its cause is **not** identified; the `+50.302 ms` is descriptive, and on the net-unchanged-spawn rows a changed batch composition and host variance cannot be causally separated by one run-pair.
- **No live decision-neutrality claim from this sidecar** — that rests on the separate offline goldens.
- **No Strength claim** — Champions Strength remains **NO-GO**.
- **No budget change** — the 1000 ms budget and D-1/D-2 exposure rules are unchanged and not reinterpreted.
- **No new gate** and **no run authorized** by this document.
- **Neither Lever B nor a persistent stratum is authorized** — both are future, separately-approved design slices; persistent is a hypothesis needing a controlled gate.
- Latency remains the **load-bearing blocker**.

---

`POST-LEVER-A LATENCY DIAGNOSIS — APPROVED (DIAGNOSIS BASIS; CODEX REVIEW PASS) — NO CODE/RUN/PUSH; LEVER B AND PERSISTENT UNAUTHORIZED`
