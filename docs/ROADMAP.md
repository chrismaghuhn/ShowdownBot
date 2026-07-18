# Canonical Roadmap & Status

**Living document — update as slices land, don't let it drift.** This supersedes the old
layered plans (README, `docs/heuristic_bot/`, and the external `../TestBOtpläne/00-14`
Northstar docs) as the single source of truth for *current status and next decision*.
`TestBOtpläne/` remains valid for deep design rationale on things already built, but it is
**not versioned with the code** and must not be read as an up-to-date execution plan —
verify against this file and git history first.

**New agents:** start with [`docs/PROJECT_INDEX.md`](PROJECT_INDEX.md) for orientation; this
roadmap remains the authoritative status matrix.

Last reconciled: 2026-07-18 (**I8-A–C offline latency machinery MERGED via PR #20 @ `32cdd4e`; the reproducible I8 microprofile driver MERGED via PR #21 @ `0730a18`; the authorized 450-row microprofile then RAN CLEAN on the fixed Windows host and is FROZEN (`data/eval/champions-panel-v0/i8-microprofile/`, `reports/champions-panel-v0-i8-microprofile.md`; git_sha `0730a18`, manifest hash `fdc3706038fde45f`; 20/20 independent validation gates, 450/450 outcome=ok, 0 contaminated/retries/crashes) — cost-mechanism localization ONLY, NOT a live latency-gate result and NO Strength claim, and the pinned 1000 ms LIVE budget is not a per-arm microprofile threshold; `reps`=30, D-2=`MAX_BATTLES`200/`MAX_SCORED_DECISIONS`2000 and the fixed Windows measurement host are CLOSED; the D0 + Kaggle D0-K timing calibrations remain cost-data-only/scratch; the I8-D live-latency HARNESS (telemetry → live-dataset validator → exposure/cap runner + three-way verdict → provenance-locked `i8d-live-gate` CLI) is now MERGED via PR #23 @ `3b6070c` (two blocking review rounds resolved, final review PASS; full suite 2777 passed / 2 skipped / 1 xfailed; code + tests ONLY — NO server, battle, live-latency run, or evidence executed); the live-gate RUN then EXECUTED once on the corrected harness (git_sha `9fc0f36`, after the team-path fix) and returned **FAIL** — active foe-Mega decision p95 `1110.213 ms` > `1000 ms` budget, exposure floor met (60 active-valid decisions from 45 distinct battles), `stop_reason=exposure_floor_met`, 75 battles / 679 decisions, atomically published and FROZEN (`data/eval/champions-panel-v0/i8d-live/`, `reports/champions-panel-v0-i8d-live.md`); this is a **load-bearing latency FAIL** (the 1000 ms budget is NOT moved post-hoc), so the next step is a dedicated **latency-reduction slice** then a REPEAT of the same gate unchanged (oneshot, same 1000 ms budget value, D-1/D-2 unchanged); Champions Strength remains NO-GO; Kaggle is reserved for later coverage/outcome/Strength as its own hardware stratum, never pooled.** **I7a own-Mega SAFETY PASS, merged to `main` @ `1053cf1`**; **I7b-A MERGED via PR #12 @ `cdc55c2`**; **I7b-B Tasks 1-6 REVIEW-PASS · MERGED via PR #13 @ `755b144`** — full suite **2169 passed, 2 skipped, 1 xfailed**, no new skip/xfail vs the 2132/2/1 pre-slice baseline; foe-Mega response modeling is now LIVE for `format_config.mega` formats and byte-identical for Reg-I/`format_config=None`; **I7b-C PRE-SMOKE REVIEW-PASS + 2-battle opponent-Mega SAFETY SMOKE PASS · NARROW EXPOSURE** (`reports/champions-panel-v0-i7b-mega-smoke.md`; git_sha `3d23e654a29689b68f3c936653726d6a36a6934d`; 19/19 standard gates PASS, worst p95 672 ms; only **1 of 17** scored decisions ever exposed a foe-Mega hypothesis and only **slot 1** — slot 0, dual-Mega and activation ordering were never exercised live, so this is evidence the mechanism works, not that opponent Mega is broadly validated) — safety/telemetry evidence only, **no Strength and no latency claim**; **Champions Strength still NO-GO** — now blocked on the **dedicated latency gate**, which remains the load-bearing blocker; I7 Mega design spec rev. 10 **APPROVED**, implementation plan at **Rev. 9**; protocol differential audit @ `fc4f251`; I6 live-damage gen-0 PASS @ `3bcd4b3`; HP-suffix revalidation PASS @ `62117b5`; prior I5 mixed verdict @ `4da007b` retained for latency baseline), against an external strategic review (adopted with two
corrections, see "Corrections to the external review" below) and this session's own verified
state (depth-2 slice, value-calibration spec).

**Post-merge reconciliation:** PR #17 is merged to `main` @ `8942232`. I7b-C is closed as
safety/telemetry work. The immediate blocker is the dedicated Champions latency profile;
even after a latency PASS, a separate broader opponent-Mega coverage gate and independent
Strength holdout must be approved before a Strength run.

**I8 offline latency machinery merged (2026-07-17, PR #20 @ `32cdd4e`).** I8-A–C is on `main`:
instrumentation of the calc cost drivers, the decision-profile sidecar + both validator tiers,
the profile-manifest producer, the microprofile arm matrix and harness, and all six previously
unconstructible arms (P-1…P-5), built and proven **offline** against a production-topology
session. **It builds and proves the measurement machine; it measures nothing** — no live battle,
no microprofile, no benchmark, no frozen evidence, and **no latency or Strength claim**. Full
suite at merge **2615 passed, 2 skipped, 1 xfailed**. **D0 and its Kaggle D0-K calibration have
since run — cost data only, scratch-only, not frozen, and carrying no latency/exposure/Strength
verdict.** They found the two battles **byte-identical across platforms** (same `battle_id`,
`turns`, `end_hp_diff`, `normalized_room_log_sha256`), but Kaggle per-decision compute ran
~1.2–1.3× slower **and** its CPU changes between sessions, so a Kaggle p95 is not reproducibly
comparable — and the I8 gate needs exposure **and** latency from the **same** run. The execution
decisions are therefore now **CLOSED**: **`reps` = 30 timed reps/arm** (warmups unchanged →
15 arms × 30 = 450 rows), **`MAX_BATTLES` = 200 / `MAX_SCORED_DECISIONS` = 2000**, and the **fixed
Windows machine** is the measurement host for both the microprofile run and I8-D. **Kaggle is
reserved for later large coverage / outcome / Strength runs as its own hardware stratum; platforms
are never pooled.** **The I8 microprofile driver then merged (PR #21 @ `0730a18`) and the
authorized 450-row microprofile RAN CLEAN on the fixed Windows host and is FROZEN**
(`data/eval/champions-panel-v0/i8-microprofile/`, `reports/champions-panel-v0-i8-microprofile.md`;
manifest hash `fdc3706038fde45f`; 20/20 independent validation gates, 450/450 outcome=ok, 0
contaminated/retries/crashes; ≈18.9 min, exit 0). It is a **cost-mechanism localization only**:
under `oneshot`, latency scales with process starts/batches (depth-2 reaches 94 transports,
≈12.3 s p95); `persistent` is ≈144 ms cold / ≈10 ms warm. **It is NOT a live latency-gate result,
makes NO Strength claim, and the pinned 1000 ms LIVE budget must not be reinterpreted as a per-arm
microprofile threshold.** **The I8-D live-latency HARNESS is now merged (2026-07-18, PR #23 @
`3b6070c`)** — the live telemetry (off by default), the closed-schema live-dataset validator, the
exposure/cap runner + three-way verdict, and the provenance-locked `i8d-live-gate` CLI, hardened
across **two blocking review rounds** (final review PASS; full suite **2777 passed, 2 skipped,
1 xfailed**). It is **code + tests only — NO server, battle, live-latency run, or evidence was
executed**. The live-gate RUN then executed **once** on the corrected harness (after the team-path
fix, `git_sha 9fc0f36`) and returned **`FAIL`**: active foe-Mega decision **p95 1110.213 ms >
1000 ms** budget, exposure floor met (**60** active-valid decisions from **45** distinct battles),
`stop_reason=exposure_floor_met`, **75** battles / **679** scored decisions, `seed_log_verified`,
atomically published and **FROZEN** (`data/eval/champions-panel-v0/i8d-live/`,
`reports/champions-panel-v0-i8d-live.md`; independently re-verified from the frozen bytes). This is
a **load-bearing latency FAIL** — the 1000 ms budget is **not** moved. The next step is a dedicated
**latency-reduction slice**, then a **repeat of the same gate, unchanged** (oneshot, the same
1000 ms budget value, D-1 ≥60-from-≥20 and D-2 caps 200/2000 unchanged); Champions Strength remains
**NO-GO**.

**The first two I8-D live attempts — ABORTED before battle creation (2026-07-18); no verdict, no evidence, no
latency statement.** On the fixed Windows host, both attempts created **zero battles** (`seeds.jsonl`
absent, `out/` never published). **Root cause = an I8-D team-path wiring bug:** `run_local_gauntlet`
loads the battle team files relative to the process CWD, but the `i8d-live-gate` command runs from
the repo root (so the repo-root-relative panel path resolves) while the team files live under
`showdown_bot/teams/`. `--teams-root` was used only to HASH the teams, not to LOAD them at battle
time, so the gauntlet got missing files, `_resolve_side_teams` silently degraded them to EMPTY packed
teams, the server rejected the empty-team challenge, no battle was created, and the gate only timed
out. **Neither timeout (180 s attempt 1, 900 s attempt 2) was ever the cause** — no battle ever
started to be slow. The **900 s decision is RETRACTED**: it rested on a wrong "slow battle" diagnosis
and was **never empirically exercised**; `config_hash 06b2b96e76486563` is void. The aborted runs'
logs are **scratch diagnostics only, never pooled**. The fix threads `teams_root` into the I8-D
runner (resolve team paths to absolute + prove non-empty before the battle; schedule identity and
`run_schedule` untouched). The corrected run (merge `9fc0f36`, PR #26) then took the **original
stratum** — `oneshot`, **standard 180 s / no `SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S`**,
`config_hash 594295543f13a55d`, seed 0 — created **75** battles (vs **0** in both aborts) and
produced the **first real verdict: `FAIL`** (active foe-Mega p95 1110.213 ms > 1000 ms; frozen at
`data/eval/champions-panel-v0/i8d-live/`). A technical abort is not a verdict; this run is. Strength
stays NO-GO.

## Status matrix

| Vorhaben | Status | Evidenz | Nächste Entscheidung |
|---|---|---|---|
| Reranker v1 (dataset/infra, 2b-2.5a) | **Built, in use** | merged `afb9708`; feeds `outcome_join` + value-calibration | keep as foundation, not "parked" |
| Reranker v1 **live override** | **NO-GO** | 2b-4 report: +13 net vs max_damage, McNemar p=0.105 n.s. | not shipped; don't re-attempt without new evidence |
| Scalar aggregation (λ tuning) | **NO-GO** | 4 experiments, see detail table below | stop; no more global-λ experiments |
| +Sampling machinery (K-world) | **Built, off** | latency report: linear-in-K, max K=8 local | hold until calibrated posterior exists (P2/P3) |
| Depth-2 search | **Stage 1+2 GO, merged local main** | `2026-07-12-2c-depth2-derisk-verdict.md` | Stage 3 blocked on TWO things: the panel actually being *run* (below), AND the accuracy chosen-line cap/fallback gate FAIL (row below) being re-derisked first |
| Generalisation analyzer (05) | **Built (tool only)** | merged `35956df` | materialize the actual archetype×opponent panel — data doesn't exist yet |
| VGC-Bench ingestion | **Part A done** | `6210e4d` | Part B (player-perspective, OTS-vs-reveal, legality, leakage audit) |
| Value calibration study | **Spec Revision 2 committed** (T3A arm, disjoint verdict, outcome-encoding, sklearn dep, fold-local categorical encoding all addressed) | `docs/superpowers/specs/2026-07-12-value-calibration-design.md` Rev 2, commit `8e4c47f` | implementation plan once Rev 2 explicitly signed off |
| Outcome-join (04) | **Built** | merged `725257e`/`fea284b`; 299-game reference smoke | consumed by value-calibration study |
| Teacher-disagreement atlas | **Built** | `5830e9e` | diagnostic only — not a strength gate |
| Diagnostics-v0 | **Built** | `849b5c7` | diagnostic only — not a strength gate |
| Belief (item/spread/move priors) | **Not started** | — | P2, after the panel + data-identity fix |
| Value-head (trained model) | **Not started, gated** | — | only after value-calibration says GO |
| PPO/full self-play RL | **Not started, deliberately deferred** | ps-ppo-reference eval | P5, after search/belief/value-labels stabilize |
| Accuracy / hit-probability evaluation | **Default-on safety-clean; strength UNDERPOWERED (unfavorable direction, no claim)** | Gate-B cap=6 PASS 6/944=0.64%; default-on live dev-strength A/B @ `a956b6b` (`reports/2026-07-14-accuracy-default-on-devstrength-verdict.md`: SAFETY-PASS, n_discordant=6, 0 A-only / 6 B-only discordants — follow-up risk signal, not regression proven) | `SHOWDOWN_ACCURACY_MODE` **default-on** when unset; cap **6**; explicit opt-out unchanged; **no GO on strength** — next step user-gated (larger strength run vs Champions-readiness) |
| Champions panel v0 (format target) | **I6 PASS · I7a own-Mega SAFETY PASS (merged) · I7b-A MERGED · I7b-B REVIEW-PASS/MERGED (PR #13 @ `755b144`) · I7b-C PRE-SMOKE REVIEW-PASS + opponent-Mega SAFETY SMOKE PASS (narrow exposure), merged via PR #17 @ `8942232` · I8-A–C offline latency machinery MERGED (PR #20 @ `32cdd4e`, offline-only) · D0 + Kaggle D0-K cost calibration DONE (scratch, no verdict) · reps=30, D-2=200/2000, host=fixed-Windows CLOSED · I8 microprofile driver MERGED (PR #21 @ `0730a18`) · 450-row microprofile RAN CLEAN & FROZEN (cost-mechanism only; 20/20 gates, 450/450 ok; no live-latency/Strength verdict) · I8-D live-latency harness MERGED (PR #23 @ `3b6070c`, code+tests only, 2 blocking review rounds resolved / final PASS, 2777 passed) · team-path wiring fix merged (PR #26 @ `9fc0f36`) · live-gate RUN EXECUTED once on the corrected harness → **FAIL** (active foe-Mega p95 1110.213 ms > 1000 ms; exposure floor met 60/45; `stop_reason=exposure_floor_met`; 75 battles/679 decisions; FROZEN `data/eval/champions-panel-v0/i8d-live/` + `reports/champions-panel-v0-i8d-live.md`) · latency = load-bearing blocker; next = latency-reduction slice then REPEAT same gate unchanged · Strength NO-GO** | P0–P4 on main; I4 calc pin + speed gen-0 merged `f192aff`; I5 @ `4da007b`: **5/94** random-legal degradation, worst p95 **3235 ms** (also contained state-degradation; no causal p95 link); HP fix merged `62117b5`; revalidation @ `62117b5` (`suffix-evidence.json`): **0/99** degraded; this-run p95 **429 ms** (observational only); **I6 @ `3bcd4b3`**: gen-0 damage wired through heuristic/`max_damage`/export; 2-battle smoke **SAFETY-PASS**, worst p95 **331 ms** (`reports/champions-panel-v0-i6-smoke.md`); **protocol differential audit @ `fc4f251`**: `reports/champions-pkmn-protocol-differential-audit.md`; **I7 Mega design spec rev. 10 APPROVED** (`docs/superpowers/specs/2026-07-14-champions-mega-i7-design.md`); **I7a-A/I7a-B/I7a-C merged to `main`** (candidate identity/trace-v3/own-Mega safety smoke, config_hash `e137fce925f25bd8`, git_sha `5690de75a4f7bc627b8d4be4fddb2074c6b586fc`, worst p95 **588 ms**); **I7b-A merged via PR #12 @ `cdc55c2`** (limited-view eligibility, response identities, fail-closed click-rate parsing, coverage-preserving cap/truncation; focused gate **106 passed**; full suite **2132 passed, 2 skipped, 1 xfailed**); **I7b-B Tasks 1-6 merged via PR #13 @ `755b144`** (Codex verdict: PASS, no merge blockers) — `mega_activation_order_key`; side-aware `project_mega` + fail-closed `MegaProjectionSpeciesMismatchError`; `compose_mega_projection_branches` (unequal speed → 1 branch @ 1.0, exact tie → 2 @ 0.5, no RNG, never mutates input); three-phase scoring integration (build+enqueue → **one shared oracle flush per world** → evaluate at `world_weight × response_weight × branch_weight`); the `decision.py::_choose_best_mega` caller gate (`foe_mega_eligibility()` called ONLY when `format_config is not None and format_config.mega` — it has no `format_config` parameter of its own, and `opp_mega_click_rate()` defaults to `0.35` when unset, so this gate is the entire Reg-I guarantee); and per-diagnostic-index depth-2 context binding with **zero `search.py` changes**. **A P1 caught in review and fixed before merge:** `aggregate_scores`' `MUST_REACT` operator takes `min(scores)` WITHOUT weights, so a weight-0 sample cannot move the weighted mean but DOES move the aggregate (`[10]` w=`[1]` → `10.0` vs `[10,-100]` w=`[1,0]` → `-56.0` at λ=0.6) — zero-weight responses are now excluded from enqueue/evaluation/`score_vector` on the active path, and zero-weight Mega classes compose no branches at all (`NEUTRAL`/`AHEAD` were unaffected). Full suite **2169 passed, 2 skipped, 1 xfailed** (no new skip/xfail); `battle/baselines.py` and `battle/search.py` byte-identical across the whole slice; foe-Mega modeling LIVE for `format_config.mega`, byte-identical for Reg-I/`None`. **I7b-C PRE-SMOKE REVIEW-PASS + LIVE SMOKE PASS · NARROW EXPOSURE** (`docs/superpowers/specs/2026-07-16-champions-opponent-mega-i7b-audit.md`, `docs/superpowers/plans/2026-07-16-champions-opponent-mega-i7b.md` Rev. 9; verdict `reports/champions-panel-v0-i7b-mega-smoke.md`) — off-by-default `eval/opp_mega_trace.py` sidecar (raw components only, LF-only bytes, `raw_score` = the FINAL post-depth-2 `score_vector` value), reachable end-to-end `run_schedule → run_local_gauntlet → hero _Client → agent_choose → decision core`, sink forwarded on **both** heuristic agents, and rows stamped with the client's shared **request sequence** rather than a written-row counter. **Two P1s caught in review and fixed before the smoke:** (a) evidence kept the superseded 1-ply `detail.score` while depth-2 overwrote `score_vector[i]` in place and `aggregate_score` read the final vector — the sidecar attributed to the decision a number it never used; (b) `decision_index` drifted against decision-trace, because team preview writes a trace row but no sidecar row, so the first REAL decision was trace 1 / sidecar 0. **2-battle live smoke @ git_sha `3d23e654a29689b68f3c936653726d6a36a6934d`, config_hash `b3cb6ea1a4836060` (LF-stable, platform-independent), run_id `d074ce1c8a69a2e1`**: 2/2 normal, 0 crashes, 0 invalid, **19/19 standard gates PASS**, worst p95 **672 ms** (budget 1000, unchanged); 19/19 trace-v3 rows valid; 17/17 sidecar rows valid and LF-only; every sidecar `(battle_id, decision_index)` resolves to exactly one trace row, with gaps **only** at the two `team_preview` rows — the live confirmation of the [P1] fix. **NARROW EXPOSURE, part of the verdict:** only **1 of 17** scored decisions ever exposed a foe-Mega hypothesis (battle `242a0c3ec6d0e79c`, decision 4: `required = retained = scored = {"1","none"}`, twin `response_ids` `aggro->a|mega=1` + `aggro->a|mega=none`, 41 distinct hero candidates scored against both) — **slot 1 only; slot 0, dual-Mega and activation ordering were never exercised live**. Evidence the mechanism works, NOT broad opponent-Mega validation, and **no Strength or latency claim** | **1)** The measurement-only Champions latency **machinery (I8-A–C) is built and merged offline** (PR #20 @ `32cdd4e`) — instrumentation, sidecar, both validator tiers, manifest producer, arm matrix/harness and all six arms, proven against a production-topology session, with **no run taken and no latency claim**. D0 and its Kaggle D0-K calibration have run (cost data only, scratch, no verdict), closing the execution decisions: **`reps` = 30 timed reps/arm** (warmups unchanged → 15 arms × 30 = 450 rows), **`MAX_BATTLES` = 200 / `MAX_SCORED_DECISIONS` = 2000**, and the **fixed Windows machine** as the measurement host for the microprofile run and I8-D. **Kaggle is reserved for later coverage/outcome/Strength as its own hardware stratum; platforms are never pooled** (its CPU changes between sessions, so a Kaggle p95 is not reproducibly comparable, and the gate needs exposure and latency from the same run). The 450-row microprofile RAN CLEAN and is FROZEN (`data/eval/champions-panel-v0/i8-microprofile/`, `reports/champions-panel-v0-i8-microprofile.md`) — cost-mechanism localization only (oneshot scales with process starts/batches; persistent ≈144 ms cold / ≈10 ms warm), **no live-latency and no Strength verdict**. **The I8-D live-latency HARNESS is merged (PR #23 @ `3b6070c`, code + tests only, two blocking review rounds resolved / final PASS, full suite 2777 passed); after a team-path wiring fix (PR #26 @ `9fc0f36`) the live-gate RUN then EXECUTED once and returned `FAIL`** — active foe-Mega p95 **1110.213 ms > 1000 ms**, exposure floor met (60 active-valid from 45 distinct battles), `stop_reason=exposure_floor_met`, 75 battles / 679 decisions, FROZEN (`data/eval/champions-panel-v0/i8d-live/`, `reports/champions-panel-v0-i8d-live.md`). This is a **load-bearing latency FAIL** — the pinned 1000 ms budget is **not** moved. The next step is a dedicated **latency-reduction slice**, then a **repeat of the same gate unchanged** (oneshot, same 1000 ms budget, D-1/D-2 unchanged); do not reinterpret that LIVE budget as a per-arm microprofile threshold. **2)** If latency passes, approve a separate opponent-Mega coverage + independent-holdout design before any Strength run; the I7b-C smoke's 1/17 slot-1-only exposure is not broad validation. **3)** Strength remains **NO-GO** until both gates pass. **4)** Run the I7a CRLF/config-hash impact audit in parallel as provenance housekeeping; do not cite its historical config hash as cross-platform evidence before classification. |

### Champions front-track sequence (binding after I7b-C)

```text
I7b-C safety/telemetry evidence merged
        ↓
measurement-only Champions latency design + pre-registered budget/exposure rules
        ↓
I8-A–C offline latency machinery merged (PR #20 @ 32cdd4e) — built & proven, NO runs
        ↓
D0 + Kaggle D0-K calibration: DONE — cost data only, scratch, no verdict
   → reps=30, D-2=200/2000, host=fixed-Windows CLOSED (Kaggle = coverage-only stratum, never pooled)
        ↓
microprofile driver merged (PR #21 @ 0730a18); 450-row microprofile (15 arms × 30 reps) RAN CLEAN & FROZEN
   → cost-mechanism only (oneshot scales with process starts/batches; persistent ≈144 ms cold / ≈10 ms warm); NO live-latency/Strength verdict
        ↓
I8-D live-latency HARNESS merged (PR #23 @ 3b6070c) — telemetry + live-dataset validator + runner/verdict + i8d-live-gate CLI
   → code + tests only (2 blocking review rounds resolved, final PASS, 2777 passed); NO server/battle/run/evidence
        ↓
I8-D live-gate RUN (agent_choose scope, pinned 1000 ms budget):   RAN once on the corrected harness → FAIL
   → first two attempts ABORTED before battle creation (team-path wiring: teams not loaded → empty teams → server rejects → 0 battles); 180 s/900 s never the cause; 900 s decision RETRACTED (unexercised)
   → fix threaded teams_root into the I8-D runner (PR #26 @ 9fc0f36); the corrected run took the ORIGINAL stratum (oneshot, standard 180 s, config_hash 594295543f13a55d, seed 0), created 75 battles, and produced the first real verdict
   → FAIL: active foe-Mega p95 1110.213 ms > 1000 ms; exposure floor met (60 active-valid from 45 distinct battles); stop_reason=exposure_floor_met; 75 battles/679 decisions; FROZEN (data/eval/champions-panel-v0/i8d-live/, reports/champions-panel-v0-i8d-live.md)
        ↓
PASS → opponent-Mega coverage gate + independent Strength-holdout design
FAIL (← taken) → dedicated latency-reduction slice, then rerun the UNCHANGED gate (oneshot, same 1000 ms budget, D-1/D-2 unchanged)
        ↓
Strength run only after latency + coverage/holdout gates pass
```

The latency profile must not change `SHOWDOWN_OPP_MEGA_CLICK_RATE`, candidate caps, TOPM,
the pinned 1000 ms budget, or decision behavior to manufacture a PASS. The I7a
CRLF/config-hash impact audit is a separate provenance task and may run in parallel. The
Studio desktop-client/exporter track may also continue in its own worktree; neither task
changes the Champions decision front.

### Scalar-aggregation experiments (detail — the status-matrix row summarizes these four)

| Experiment | Dev-strength result | Held-out result | Evidence | Merged to main? |
|---|---|---|---|---|
| `must_react_lambda` 0.6→0.8 | +11.3pp vs `max_damage`, p=0.0002 (concentrated in the **sun** cell) | **NO-GO**: n_discordant=0, delta=0.0 exactly, both arms 7/34 — does not generalize | `reports/2026-07-12-heldout-mustreact08-verdict.md` | Yes |
| `risk_lambda` 0.5→0.75 (↑, more variance-penalty) | **−12.67pp regression** — never a dev-GO | not sent to held-out (already dev-NO-GO, nothing to spend held-out on) | 2c-aggregation-investigation memory (0a probe) | Yes |
| `risk_lambda` 0.5→0 / CVaR-mean-control (↓, drop the variance-penalty) | +36.0pp vs `max_damage`, p<0.0001 (concentrated in **trickroom/rain**) | **NO-GO**: n_discordant=8, delta=0.0000 exactly — does not generalize | `reports/2026-07-12-cvar-neutral-devstrength-3arm.md` | **No — `feat/slice-2c-cvar-neutral`, pushed to origin, NOT merged to local main** (see review-process note below) |
| Fast-board Protect-penalty | paired rain A/B: `tailwind_both` 91.7%→90.2% (worse), regret 9.26→9.44 (worse) | not sent to held-out (already offline/atlas NO-GO) | `reports/2026-07-11-fast-board-protect-discipline.md` | Yes |

**Net:** the two large `max_damage`-only dev wins (`must_react_lambda=0.8`, `risk_lambda=0`) both collapsed to *exactly* zero on held-out — both were team-archetype-specific and neither generalized. Combined with `risk_lambda=0.75`'s outright dev regression and fast-board's offline NO-GO, **global scalar tuning is exhausted as a strength lever** — this verdict holds independent of the cvar-neutral merge-status housekeeping item below.

## Corrections to the external review that produced this roadmap

1. **Git state is not "95/98 commits ahead" — it's a genuine divergence**, verified 2026-07-12:
   `git rev-list --left-right --count origin/main...main` → `1  95`. The one origin-only
   commit (`8b54fc0`, GitHub PR #2 merge of `feat/slice-fast-board-protect`) is
   **content-identical** to a commit already in local main (`7d0bf81` — same slice, merged
   twice via two different paths, two different merge SHAs). Not data loss, but a real
   push-will-be-rejected situation requiring reconciliation before any push. The
   ~95 locally-only commits (2c-aggregation onward: +Sampling, 05-generalisation, depth-2,
   outcome-join, value-calibration spec) are the real backup-risk the review correctly
   flagged. **Reconciliation + push is autonomous-implementer territory, not done here.**
2. **"Reranker v1 → NO-GO, parken" conflates two things.** The reranker *dataset/feature
   infrastructure* (2b-2.5a) is built, merged, and is the direct foundation `outcome_join`
   and the value-calibration study sit on — it is not dead. What is NO-GO is specifically
   *letting the reranker override the live heuristic's choice* (2b-4). Park the override
   idea; keep the infrastructure.
3. **Follow-up review-process note (2026-07-12, same day):** a later review pass flagged
   `docs/ROADMAP.md` as "untracked" and the value-calibration spec as "needs T3A/disjoint-
   verdict/encoding/sklearn revisions" — both checked against the live repo and found
   **stale relative to this session's own commits**: `docs/ROADMAP.md` was already committed
   (`e9ad6fa`) before that pass, and the spec's Revision 2 (`8e4c47f`) already addresses
   exactly those five items. Likely a timing gap between the review snapshot and this
   session's commits, not a real defect — noted here so the history stays legible. What
   *was* a real, new finding from that same pass: the `risk_lambda=0`/CVaR-mean held-out
   evidence lives on an **unmerged** branch (`feat/slice-2c-cvar-neutral`) — folded into the
   scalar-aggregation detail table above. Merging that branch (or copying its report into
   main) is open housekeeping, not done here (touches git state, needs explicit go-ahead).

## P0 — Integrität und Entscheidungsgrundlage

1. **`candidate_id`/chosen-Kollision beheben.** 253/3302 decisions in `phase3-slice2b25a`
   share action-identity across distinct switch targets (verified this session — not a
   score tie, a writer-side identity bug; root cause is in the feature-extraction pipeline,
   not something the calibration study itself can fix). Real, scoped follow-up; can run
   **in parallel with** the value-calibration study, which was deliberately designed to
   detect-and-exclude these rows without needing the underlying bug fixed first — the two
   are not a hard sequential dependency despite the natural reading order.
2. **Value-calibration study: finish.** Spec written (`5981ccb`), awaiting sign-off →
   implementation plan → run. Primary on the 3049 unambiguous decisions, State-only
   sensitivity on all 3302, game-clustered bootstrap, LOTO-by-team_hash. Positive outcome
   = GO for *counterfactual data collection*, not proof a value-head is justified.
3. **This file.** Keep it current; supersede ad-hoc roadmap prose scattered across memory
   entries and old planning docs.
4. **Reproducibility rounding-out.** Python/Node version pins, dependency/lockfile hashes,
   `tools/calc/package-lock.json` provenance, OS/arch, optional container digest. Env
   provenance partially built (T4c hardening); lockfile/container side still open.
5. **Wire `AccuracyDiagnostics` into `DecisionTrace`.** The accuracy/hit-probability slice
   (merged `3fd3b09`) implemented and unit-tested `battle/evaluate.py::accuracy_diagnostics`
   (ko/survival probability, accuracy-required, miss-punish-value) as a standalone function —
   deliberately NOT wired into any live caller during that slice (the trace-assembly code in
   `decision.py` wasn't read/verified as part of that scope, and guessing at the schema was
   judged worse than shipping a clean, tested, unused function). Explicit open item, not a
   silent gap: either add an `accuracy_diagnostics: AccuracyDiagnostics | None = None` field to
   `DecisionTrace` (populated only when `accuracy_mode` is on) or explicitly re-confirm it's
   still not needed — do not let this disappear. Natural to fold into the start of Depth-2
   Stage 3 (P1) if that lands first, since both touch the same trace-assembly code path.
   **Update 2026-07-13 (accuracy-offline-gate plan, spec §2.4):** `CandidateTrace.accuracy_details`
   now makes per-candidate raw accuracy telemetry (`accuracy_leaf_count`,
   `accuracy_branch_cap_hits`, `events_complete`, tie-order breakdowns) reachable on
   `DecisionTrace` — this **partially** addresses this item (the raw ingredients are now on the
   trace) but does **not close it**: `accuracy_diagnostics()` itself (the
   ko/survival-probability/`accuracy_required`/miss-punish-value function) still isn't called
   from any live decision-code caller. See
   `reports/2026-07-13-accuracy-offline-gate-verdict.md` and the design spec's own §2.4 framing
   ("does not close the whole item").
6. **Accuracy chosen-line cap/fallback re-derisking (new, opened by the 2026-07-13 offline-gate
   FAIL result).** The real Gate B run over the full 85-battle/944-decision deduplicated corpus
   found a chosen-line cap-hit rate of 12.9% (114/881), decisively above the gate's pinned 5%
   threshold — i.e. `SHOWDOWN_ACCURACY_BRANCH_CAP`'s default (4) and/or the current always-hit
   fallback-on-cap behavior is being hit far more often than the safety margin assumed when that
   default was pinned (see `reports/2026-07-12-accuracy-slice-latency-gate.md`). This is not
   fixed by this plan — it is the plan's own headline finding, reported honestly per the user's
   explicit instruction not to interpret or soften it.
   **Concrete next step, offline first:** on the SAME 85-battle corpus, compare
   `SHOWDOWN_ACCURACY_BRANCH_CAP` values (6 and 8 are the natural next probes) and/or a less
   optimistic cap-fallback strategy against today's always-hit-on-cap default, each measured on
   the SAME two axes the gate already reports: chosen-line cap-hit rate and real latency (not
   just one or the other — a lower cap-hit rate that blows the latency budget isn't a fix). Only
   after that offline comparison, re-run the EXISTING accuracy-offline-gate (`eval/accuracy_gate_b.py`
   + `accuracy_gate_stats.py`) **unchanged** against whichever cap/fallback choice looks best —
   do **not** retroactively loosen the pinned 5% threshold to make a result pass; the threshold
   was pinned before this run per spec §4 and must stay pinned across this follow-up too.
   **Also open, don't let it quietly disappear:** the 63/944 decisions Task 10's
   `_chosen_candidate` correctly excluded as ambiguous-`candidate_id` (`decision.py`'s `_label_ja`
   collapses different switch targets in the same slot to the identical label, e.g.
   `"(Knock Off->1, switch)"`) need their own separate diagnosis — the gate's FAIL verdict is
   robust to worst-case treatment of these 63 (12.1%–18.8% either way, still decisively above 5%),
   so this is not blocking the verdict above, but the underlying `_label_ja` non-injectivity is a
   real gap in `decision.py`'s candidate labeling that this plan deliberately did not fix (guarded
   at the gate-consumption layer only, per Task 10's own scoping) — these 63 decisions must not
   simply vanish from future decision-diff/accuracy analyses; they need either a `_label_ja` fix
   (switch target disambiguation) or an explicit, tracked sampling/analysis plan of their own.
   **Update 2026-07-13 (accuracy-cap-derisk plan, the concrete next step above, now done —
   `reports/2026-07-13-accuracy-cap-derisk-verdict.md`):** the offline comparison this item asked
   for was run for real, on the same 85-battle/944-decision corpus. **Cap-hit rate: both cap=6 and
   cap=8 PASS the pinned 5% threshold decisively** (numerator 6/881 = 0.68% point estimate, 1.37%
   bootstrap upper bound — both numerically **identical** between cap=6 and cap=8, i.e. cap=8 buys
   zero additional fidelity over cap=6 on this corpus), versus cap=4's frozen 114/881 = 12.9% FAIL
   (cited unchanged, never recomputed). **Zero chosen-action changes** at cap=6 or cap=8 relative
   to cap=4 (only score movement, 115/118 decisions respectively) — raising the cap only refines
   scores here, it never flips a winner on this corpus. **Latency: both cap=6 and cap=8, both
   trace modes, PASS the existing ×5-scaled 1000ms gate on this real corpus** (worst case
   `cap8_trace_enabled` p95×5 ≈ 968ms, a thin ~3.2% margin) — this **disagrees with** the earlier
   accuracy-hit-probability slice's single-board bench, which found cap=6/cap=8 FAILing the same
   scaled gate (`reports/2026-07-12-accuracy-slice-latency-gate.md`); the disagreement is
   attributed to that board being deliberately built to stress accuracy branching harder than this
   real corpus's average decision, not resolved as a contradiction — flagged for whoever weighs a
   real Kaggle-hardware check, since the ×5 multiplier itself is an estimate, not a measured
   constant. **The ambiguous-candidate diagnosis asked for above is now done too:** all 63 excluded
   decisions, at all three caps, classify identically as `label_collision`/`switch_target_omitted`
   (100%, zero `other_pipeline_error`, zero `chosen_candidate_missing`), and the exclusion set is
   completely cap-invariant (`all_three=63`, `cap4_only=cap6_only=cap8_only=0`) — confirming this
   is a pure `_label_ja` labeling defect, not a cap artifact. A fix-feasibility investigation
   (no code change) recommends a stable structural candidate key (per-slot `(kind, move_index,
   target, target_ident, terastallize)`) as the preferred long-term fix, needing either a new
   `DecisionTrace.chosen_joint_action`-style field or a key assigned at enumeration time — still
   unimplemented, still open. **Per the report's own explicit framing: none of the above is a
   default-on decision, a strength claim, or Depth-2 Stage 3 work** — raising
   `SHOWDOWN_ACCURACY_BRANCH_CAP`'s default, fixing `_label_ja`, and resolving the latency-margin
   disagreement (possibly via a real Kaggle-hardware check) all remain separate, explicit,
   user-owned next steps, not scheduled by this update.
   **Update 2026-07-14 (candidate-identity slice merged, Gate-B cap=6/cap=8 re-run on
   `9f64c28`):** the structural candidate-key resolver (`candidate_identity.py`) is now live on
   `main`. Re-running `run_cap_gate_verdicts.py` over the same 85-battle corpus with the unchanged
   `run_gate_b` path changes the Gate-B denominator from **881 → 944** (the 63 historically
   ambiguous-`candidate_id` decisions now resolve cleanly; **0 exceptions** vs the prior 63).
   **Cap=6 and cap=8 remain PASS** at **6/944 = 0.64%** point estimate (bootstrap upper ≈ 1.36%,
   identical between caps — cap=8 still buys zero additional fidelity). **`gate-b-report.json`
   (cap=4) stays frozen/authoritative** at 114/881 = 12.9% FAIL and was **not** recomputed. See
   refreshed `data/eval/accuracy-cap-derisk/cap{6,8}-report.json` and
   `reports/2026-07-13-accuracy-cap-derisk-verdict.md` (2026-07-14 addendum).
   **Update 2026-07-14 (default-on slice, `8c54843`):** production env parsers now default
   `SHOWDOWN_ACCURACY_MODE` on and `SHOWDOWN_ACCURACY_BRANCH_CAP` to **6** when unset; explicit
   `"0"` / `"false"` / `""` remain off. Spec:
   `docs/superpowers/specs/2026-07-14-accuracy-default-on-design.md`. Decision note:
   `reports/2026-07-14-accuracy-default-on-decision-note.md`. **Dev-strength A/B done**
   (`reports/2026-07-14-accuracy-default-on-devstrength-verdict.md`): SAFETY-PASS, strength
   UNDERPOWERED (n_discordant=6); directional warning only (off favored in all discordants) —
   not equivalence, not regression proven.

## P1 — Nächster realer Stärkeversuch

1. **Materialize the dev-generalization panel (05).** The analyzer/planner exists; the
   actual matrix (hero archetypes × opponent teams × opponent policies, per-cell eval,
   worst-cell protection, paired seeds, staged pilot before the full gate) does not yet
   exist as run data. This is the actual blocker on depth-2 Stage 3, not a parallel task.
2. **VGC-Bench compatibility study (read-only, no integration) — sequenced after the
   accuracy-hit-probability slice, before Depth-2 Stage 3.** User verdict (2026-07-13):
   GO for a small integration study, explicitly NOT a rebuild of our bot — neither
   VGC-Bench's resolver nor its RL stack get integrated into our core now. Feeds directly
   into item 1's panel-diversity gap (we currently have only 4 archetypes and a coarse
   LOTO test). Scope:
   - Adapter for our heuristic agent vs. VGC-Bench's Random/MaxBasePower/SimpleHeuristics
     baselines (external comparison point our internal-only benchmark currently lacks).
   - Check whether the 72 holdout teams (or a license/provenance-clean compatible subset)
     can be adopted into our dev panel — directly addresses item 1's team-diversity gap.
   - Trained policies (BC/RL) as a **future opponent population** for opponent-response/
     belief/Depth-2 — comparison opponents, explicitly NOT ground truth.
   - Compatibility checklist: pinned Showdown commit + poke-env version, format/OTS/team-
     preview/action-space compatibility, team-file licenses, adapter-effort estimate,
     whether our `config_hash`/run-manifest provenance chain survives the integration.
   - Concrete smoke matrix: 100–200 games vs. the 3 heuristic baselines.
   - No BC/RL implementation starts from this study — investigation only.
   Related to, but broader than, the existing P2 item 1 ("VGC-Bench Part B" — that one is
   specifically the OTS/hidden-information angle; this item is benchmarking infrastructure
   — baselines, holdout teams, provenance).
3. **Depth-1 vs depth-2(3,3) on that panel.** The most mature, plausible-impact experiment
   on the table — run before any new architecture slice. GO → depth-2 becomes the new
   baseline candidate. NO-GO → analyze the coarse-approximation failure mode, don't just
   re-tune N/M. Inconclusive → panel/opponents aren't discriminating enough.
4. **Bounded ladder calibration** — only after the candidate wins on the diverse dev panel;
   external validation, not the primary optimization loop.

## P2 — Probabilistische Hidden Information

1. VGC-Bench Part B on a small Reg-I sample: player perspective, OTS-vs-reveal
   availability, legality reconstruction, leakage audit, clear provenance.
2. Belief v1 calibrated **offline first** (not live-deciding): item/move/spread log-loss,
   speed-interval coverage, Brier score, posterior mass on the true set, calibration by turn.
3. Battle-local updates (reveals, turn order, damage ranges, item/ability exclusion, tera).
   Beliefs affect priors/world-weights only at this stage.

## P3 — Belief-basierte Suche

1. Dedupe identical sampled worlds before evaluation (fixes the current linear-in-K
   latency finding).
2. K-world sampling vs single-world ablation, start K=4 (comfortable local latency margin).
3. Depth-2 × K-sampling composition — deliberately not combined yet; needs its own budget/
   fusion design.
4. Adaptive risk aggregation from the actual posterior world distribution + position,
   instead of a global CVaR scalar (global aggregation scalars are 2-for-2 on large
   `max_damage`-only dev wins collapsing to exactly zero on held-out — see the
   scalar-aggregation detail table above; the CVaR *operator* itself stays useful for this
   axis, only its global-scalar deployment is ruled out).

## P4 — Lernen aus besserem Teacher-Signal

1. Generate search-teacher data once a stronger search/belief policy exists (better
   counterfactual labels than the current rollout teacher).
2. Value-head and a new reranker tested **separately**, both ablated against the
   then-current search baseline — not introduced simultaneously.
3. Team preview built on the same value/belief building blocks, not a standalone
   90×90 heuristic re-evaluated on the old eval.

## P5 — Langfristige Forschung

Population/league self-play; exploitability/best-response track; BO3 + cross-game
opponent memory; a new engine or Rust hot-paths only after a demonstrated throughput
bottleneck.

## Explicitly parked / stopped

- Further reranker threshold tuning to rescue live override.
- More global λ/penalty scalar experiments.
- `SHOWDOWN_WORLD_SAMPLES` ≥ 16 before world-dedup + real posteriors exist.
- Starting large PPO/transformer infrastructure now.
- Building all four memory systems at once (meta/set/battle-local first; cross-game
  opponent memory is V2).
- Re-opening the current held-out panel for development decisions.
- Teacher-agreement as a primary gate (see `teacher-agreement-winrate-inversion` — it can
  invert relative to real winrate).
- Treating Elo milestones (1300/1500/1700) as technical acceptance criteria before a real
  ladder baseline exists.

## Long-term sequencing logic (after the Champions front-track gate)

The diagram below remains the long-term search/learning order. It is **not** the immediate
next-task list while the Champions latency and coverage/holdout gates above are open.

```
Datenidentität reparieren
        ↓
Value-Diagnose + Generalisationspanel materialisieren
        ↓
Depth-2 echter Stärke-Gate (Stage 3)
        ↓
kalibrierte Beliefs
        ↓
belief-basiertes Sampling/Search
        ↓
bessere kontrafaktische Labels
        ↓
Value-Head/Reranker neu bewerten
```

Each stage should justify the next. The project's strength is a reproducible measurement
harness (held-out ledger, McNemar gates, paired seeds, byte-identical-off invariants) —
lean on it rather than adding architecture layers whose payoff hasn't been measured.
