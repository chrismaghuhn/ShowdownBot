# Project Index

**Orientation card for new Cursor / Claude / Codex sessions.**
This file is an entry map — not a replacement for [`docs/ROADMAP.md`](ROADMAP.md), which remains
the authoritative status matrix and next-decision source. When they disagree, trust the roadmap
and git history; update this index if it drifts.

Last reconciled: 2026-07-20 (**I8-A–C offline latency machinery MERGED via PR #20 @ `32cdd4e`; the reproducible microprofile driver MERGED via PR #21 @ `0730a18`; the authorized 450-row microprofile then RAN CLEAN on the fixed Windows host and is FROZEN (`data/eval/champions-panel-v0/i8-microprofile/`, `reports/champions-panel-v0-i8-microprofile.md`; manifest hash `fdc3706038fde45f`; 20/20 validation gates, 450/450 outcome=ok, 0 contaminated/retries/crashes) — cost-mechanism localization ONLY, NOT a live latency-gate result and NO Strength claim, and the pinned 1000 ms LIVE budget is not a per-arm microprofile threshold; `reps`=30, D-2=200/2000 and the fixed Windows host CLOSED; the D0 + Kaggle D0-K calibrations remain cost-data-only/scratch; the I8-D live-latency HARNESS is now MERGED via PR #23 @ `3b6070c` (telemetry → live-dataset validator → exposure/cap runner + three-way verdict → provenance-locked `i8d-live-gate` CLI; two blocking review rounds resolved, final review PASS; 2777 passed / 2 skipped / 1 xfailed; code + tests ONLY — NO server/battle/live-latency run/evidence); after a team-path wiring fix (PR #26 @ `9fc0f36`) the live-gate RUN then EXECUTED once and returned **FAIL** (active foe-Mega p95 `1110.213 ms` > `1000 ms`; exposure floor met 60/45; `stop_reason=exposure_floor_met`; 75 battles/679 decisions; FROZEN `data/eval/champions-panel-v0/i8d-live/` + `reports/champions-panel-v0-i8d-live.md`) — a load-bearing latency FAIL (budget NOT moved); the latency-reduction slice (Lever A) is MERGED via PR #30 @ `6b2f955` (a behavior-neutral fold of the game-mode incoming classification into the decision's single shared `DamageOracle` scoring flush, plus hardened counterproofs; full suite 2799 passed / 1 skipped / 1 xfailed; cost contract ≥1 spawn removed per decision, board-/cache-dependent); the UNCHANGED post-Lever-A I8-D live-gate rerun then RAN once on `9d915f2` and returned **FAIL** (active foe-Mega p95 `1160.515 ms` > `1000 ms`; exposure floor met 60/45; `stop_reason=exposure_floor_met`; 75 battles/679 decisions; evidence frozen LOCALLY at commit `1262e36` under `data/eval/champions-panel-v0/i8d-live-post-lever-a/` + verdict report `fe05054` `reports/champions-panel-v0-i8d-live-post-lever-a.md`; the 968.513 ms model projection did NOT materialize empirically; the +50.302 ms vs the pre-Lever-A FAIL is descriptive only — no causal Lever-A latency effect is derivable); evidence/docs PR MERGED (PR #32 @ `34b088e`); offline latency diagnosis + Lever B (B2) design + impl MERGED via PR #33 @ `b192825` (behavior-neutral decision-start `mixed_batch` pre-pass, golden byte-identical, full suite 2835/1/1, CI 8/8, engages on the live path); the UNCHANGED I8-D live-gate rerun then RAN once on `3db4ac7` → valid **PASS** (active foe-Mega p95 850.245 ms ≤ 1000 ms; exposure floor met 60/44; 72 battles/651 decisions; stop=exposure_floor_met; seed_log_verified; evidence `4b4be54`, report `062b6d0`); drop vs the FAILs descriptive only (no causal Lever-B or variance claim); **latency blocker CLOSED**; the Lever-B PASS evidence is FROZEN + MERGED (PR #35 @ `6de0578`) and the docs-project-organization migration is MERGED (PR #36 @ `9c780a2`); the opponent-Mega coverage-gate design + implementation (Plan A) is now MERGED via PR #37 @ `10f9adf` (code + tests only, no run — two ultrareview rounds resolved, 6 P1s + 2 follow-ups); because it touches the LIVE decision-profile v3 write path, the prior I8-D PASS does not carry over; the UNCHANGED I8-D latency rerun then RAN once on `bd590c1` and returned a valid **PASS** — active foe-Mega p95 **864.94 ms ≤ 1000 ms**, exposure floor met (60 active-valid from 45 distinct battles; 75 battles/679 decisions; `stop_reason=exposure_floor_met`; `seed_log_verified`), evidence frozen MERGED via PR #39 @ `cbaa4b9` under `data/eval/champions-panel-v0/i8d-live-post-coverage-harness/` + verdict report `f0d42dd`; kept strictly separate from every prior I8-D run (comparisons descriptive only — no causal or variance claim); the latency precondition for candidate `bd590c1` is CLOSED (candidate-identity gap: NOT closed for `cbaa4b9` — see below). The separately-authorized `champions-coverage-gate` then ran exactly once on `cbaa4b9` (after one technical-abort first attempt, excluded from the verdict population) and returned **FAIL** (`schedule_exhausted`; 200 battles/1956 decisions; safety violations 0; `slot0`/`slot1`/`order_tie` floors met; `both_foe_slots` 0/0 floor NOT met — evidence frozen LOCALLY, not yet merged, at `4109abd` + verdict report `e08412e`); next = review + merge this evidence/report/docs, then a separately-authorized diagnosis/design slice for the zero-exposure — now **DIAGNOSED + REMEDIATED** (T1 `cov_foe_both` team redesign, T2 shared `candidate_identity` helper, T3 same-candidate I8-D-PASS gate, four independent review rounds hardening the I8-D-verdict guard to the full real 25-field schema) and **MERGED via PR #42 @ `f2bb818`** (2026-07-21; full suite 2971 passed/18 pre-existing unrelated failed/1 skipped/1 xfailed) — safety/provenance/defect-fix only, no live gate ran; next = a separately-authorized I8-D rerun on the fresh candidate identity for `f2bb818` (new `git_sha`, does not inherit `bd590c1`/`cbaa4b9`), then, only if PASS, a separately-authorized coverage-gate rerun with the repaired team (no identical rerun of the FAIL, no post-hoc threshold/schedule change). Champions Strength remains NO-GO — the coverage-gate FAIL is a load-bearing blocker, and separately the latency precondition for this same candidate `cbaa4b9` is itself unestablished (candidate-identity gap: the `bd590c1` PASS, identity `b3c2e0521505932d`, does not transfer to `cbaa4b9`, identity `93cd419222683f75`, per the APPROVED spec's shared-candidate-identity requirement); Kaggle reserved for later coverage/outcome/Strength as its own hardware stratum, never pooled**; **I7a own-Mega SAFETY PASS, merged to `main` @ `1053cf1`**; **I7b-A MERGED via PR #12 @ `cdc55c2`**; **I7b-B Tasks 1-6 REVIEW-PASS · MERGED via PR #13 @ `755b144`**, full suite **2169 passed, 2 skipped, 1 xfailed**, foe-Mega modeling now LIVE for `format_config.mega` and byte-identical for Reg-I/`None`; **I7b-C PRE-SMOKE REVIEW-PASS + 2-battle opponent-Mega SAFETY SMOKE PASS · NARROW EXPOSURE, merged via PR #17 @ `8942232`** (1/17 scored decisions, slot 1 only; `reports/champions-panel-v0-i7b-mega-smoke.md`) — safety/telemetry evidence only; **Strength still NO-GO** — the I8-D latency precondition for candidate `bd590c1` is CLOSED; the load-bearing blockers are now the coverage-gate FAIL (`both_foe_slots` zero-exposure, `cbaa4b9`) and the unestablished latency precondition for that same candidate `cbaa4b9` (candidate-identity gap — the `bd590c1` PASS, identity `b3c2e0521505932d`, does not transfer to `cbaa4b9`, identity `93cd419222683f75`, per the APPROVED spec's shared-candidate-identity requirement), followed by the independent Strength-holdout design; I7 Mega design spec rev. 10 **APPROVED**, implementation plan **Rev. 9 / execution complete**; protocol audit @ `fc4f251`; I6 @ `3bcd4b3` on `main`).

---

## Purpose

This repository is **not just a Pokémon Showdown bot**. It is a reproducible
**eval / trace / provenance pipeline** for Showdown and Champions-format work: paired seeds,
schedule manifests, panel hashes, `DecisionTrace`, candidate identity, gate artifacts, and
McNemar-style strength readouts — with explicit non-claims when evidence is thin.

---

## Current North Star

Build a **reproducible** Pokémon Showdown / Champions bot whose decision pipeline is **measurable**
(harness-first, fail-closed gates, provenance on every eval row).

---

## Current Priority

Ordered front-track work as of **2026-07-20** (I8-A–C machinery merged PR #20 @ `32cdd4e`; microprofile driver merged PR #21 @ `0730a18`; the 450-row microprofile RAN CLEAN & FROZEN — cost-mechanism only, no live-latency/Strength verdict; I8-D live-latency HARNESS merged PR #23 @ `3b6070c` — code + tests only; team-path fix PR #26 @ `9fc0f36`; live-gate RUN then EXECUTED once → **FAIL** (active foe-Mega p95 1110.213 ms > 1000 ms; frozen); latency-reduction slice (Lever A) MERGED via PR #30 @ `6b2f955` (behavior-neutral fold + hardened counterproofs, full suite 2799/1/1); the UNCHANGED post-Lever-A I8-D live-gate rerun then RAN once on `9d915f2` → **FAIL** (active foe-Mega p95 1160.515 ms > 1000 ms; exposure floor met 60/45; 75 battles/679 decisions; stop=exposure_floor_met; evidence frozen locally `1262e36` + report `fe05054`; the 968.513 ms model projection did NOT materialize; the +50.302 ms vs the pre-Lever-A FAIL is descriptive only — no causal Lever-A latency effect); evidence/docs PR MERGED (PR #32 @ `34b088e`); offline latency diagnosis + Lever B (B2) design + impl MERGED via PR #33 @ `b192825` (behavior-neutral decision-start `mixed_batch` pre-pass, golden byte-identical, full suite 2835/1/1, CI 8/8, engages on the live path); the UNCHANGED I8-D live-gate rerun then RAN once on `3db4ac7` → valid **PASS** (active foe-Mega p95 850.245 ms ≤ 1000 ms; exposure floor met 60/44; 72 battles/651 decisions; stop=exposure_floor_met; seed_log_verified; evidence `4b4be54`, report `062b6d0`); drop vs the FAILs descriptive only (no causal Lever-B or variance claim); **latency blocker CLOSED**; the opponent-Mega coverage-gate design + implementation (Plan A) is now MERGED via PR #37 @ `10f9adf` (code + tests only, no run); because it touches the LIVE decision-profile v3 write path, the prior I8-D PASS does not carry over — the UNCHANGED rerun then RAN once on `bd590c1` → **PASS** (p95 864.94 ms ≤ 1000 ms; 60/45; 75 battles/679 decisions; exposure_floor_met; seed_log_verified; evidence + report MERGED via PR #39 @ `cbaa4b9`; latency precondition for `bd590c1` CLOSED, NOT `cbaa4b9` -- identity gap, no transfer); the coverage gate then ran once on `cbaa4b9` (after one technical-abort attempt, excluded from the verdict population) → **FAIL** (`schedule_exhausted`; 200 battles/1956 decisions; safety=0; `slot0`/`slot1`/`order_tie` floors met; `both_foe_slots` 0/0 floor NOT met; evidence frozen locally `4109abd` + report `e08412e`); next = review+merge this evidence/docs, then a separately-authorized diagnosis/design slice for the zero-exposure, then the independent Strength-holdout design):

1. **Champions latency — offline machinery merged (I8-A–C, PR #20 @ `32cdd4e`) + reproducible
   microprofile driver merged (PR #21 @ `0730a18`); the 450-row microprofile RAN CLEAN & FROZEN;
   I8-D live-latency HARNESS merged (PR #23 @ `3b6070c`, code + tests only); after the team-path fix (PR #26 @ `9fc0f36`) the live-gate RUN EXECUTED once → **FAIL** (p95 1110.213 ms > 1000 ms; frozen); latency-reduction slice (Lever A) MERGED via PR #30 @ `6b2f955` (behavior-neutral fold + hardened counterproofs, full suite 2799/1/1); the UNCHANGED post-Lever-A I8-D live-gate rerun then RAN once on `9d915f2` → **FAIL** (active foe-Mega p95 1160.515 ms > 1000 ms; exposure floor met 60/45; 75 battles/679 decisions; stop=exposure_floor_met; evidence frozen locally `1262e36` + report `fe05054`; the 968.513 ms model projection did NOT materialize; the +50.302 ms vs the pre-Lever-A FAIL is descriptive only — no causal Lever-A latency effect); evidence/docs PR MERGED (PR #32 @ `34b088e`); offline latency diagnosis + Lever B (B2) design + impl MERGED via PR #33 @ `b192825` (behavior-neutral decision-start `mixed_batch` pre-pass, golden byte-identical, full suite 2835/1/1, CI 8/8, engages on the live path); the UNCHANGED I8-D live-gate rerun then RAN once on `3db4ac7` → valid **PASS** (active foe-Mega p95 850.245 ms ≤ 1000 ms; exposure floor met 60/44; 72 battles/651 decisions; stop=exposure_floor_met; seed_log_verified; evidence `4b4be54`, report `062b6d0`); drop vs the FAILs descriptive only (no causal Lever-B or variance claim); **latency blocker CLOSED**; the opponent-Mega coverage-gate design + implementation (Plan A) is now MERGED via PR #37 @ `10f9adf` (code + tests only, no run — two ultrareview rounds resolved, 6 P1s + 2 follow-ups); because it touches the LIVE decision-profile v3 write path, the prior I8-D PASS does not carry over; the UNCHANGED I8-D latency rerun (fresh worktree, unchanged budget/exposure) then RAN once on `bd590c1` and returned a valid **PASS** — active foe-Mega p95 **864.94 ms ≤ 1000 ms**, exposure floor met (60 active-valid from 45 distinct battles; 75 battles/679 decisions; `stop_reason=exposure_floor_met`; `seed_log_verified`); all rows carry `schema_version=decision-profile-v3`, offline-verified before the run to validate cleanly and not affect the schema-version-agnostic verdict population; evidence MERGED via PR #39 @ `cbaa4b9` (originally frozen at `1166627` under `data/eval/champions-panel-v0/i8d-live-post-coverage-harness/` + verdict report `f0d42dd`, `reports/champions-panel-v0-i8d-live-post-coverage-harness.md`), kept strictly separate from every prior I8-D run — comparisons descriptive only, no causal or variance claim. The latency precondition for candidate `bd590c1` is CLOSED — candidate-identity gap: NOT closed for `cbaa4b9` (see below). The `champions-coverage-gate` then ran exactly once on `cbaa4b9` (after one technical-abort first attempt, excluded from the verdict population) → **FAIL** (`schedule_exhausted`; 200 battles/1956 decisions; safety violations 0; `slot0`/`slot1`/`order_tie` floors met; `both_foe_slots` 0/0 floor NOT met; evidence frozen locally, not yet merged, at `4109abd` + verdict report `e08412e`, `reports/champions-panel-v0-coverage-v0.md`). Next = review + merge this evidence/report/docs, then a separately-authorized diagnosis/design slice for the zero-exposure — now **DIAGNOSED + REMEDIATED** (T1 `cov_foe_both` team redesign, T2 shared `candidate_identity` helper, T3 same-candidate I8-D-PASS gate, four independent review rounds hardening the I8-D-verdict guard to the full real 25-field schema) and **MERGED via PR #42 @ `f2bb818`** (2026-07-21; full suite 2971 passed/18 pre-existing unrelated failed/1 skipped/1 xfailed) — safety/provenance/defect-fix only, no live gate ran; next = a separately-authorized I8-D rerun on the fresh candidate identity for `f2bb818` (new `git_sha`, does not inherit `bd590c1`/`cbaa4b9`), then, only if PASS, a separately-authorized coverage-gate rerun with the repaired team (no identical rerun of the FAIL, no post-hoc threshold/schedule change), then the independent Strength-holdout design.**
   The measurement-only latency machinery is now on
   `main`: instrumentation of the calc cost drivers, the decision-profile sidecar + both
   validator tiers, the manifest producer, the microprofile arm matrix/harness and all six
   previously-unconstructible arms (P-1…P-5), built and proven **offline** against a
   production-topology session (full suite at merge **2615 passed, 2 skipped, 1 xfailed**).
   **No latency, exposure or Strength verdict exists.** D0 and its Kaggle **D0-K** calibration
   have since run (cost data only, scratch-only, not frozen): the two battles were
   **byte-identical across platforms**, but Kaggle per-decision compute ran ~1.2–1.3× slower and
   its CPU changes between sessions, so a Kaggle p95 is not reproducibly comparable. The execution
   decisions are now **CLOSED**: **`reps` = 30 timed reps/arm** (warmups unchanged → 15 × 30 =
   450 rows), **`MAX_BATTLES` = 200 / `MAX_SCORED_DECISIONS` = 2000**, and the **fixed Windows
   machine** as the measurement host for the microprofile run and I8-D; **Kaggle is reserved for
   later coverage/outcome/Strength as its own hardware stratum, never pooled**. The **450-row
   microprofile then RAN CLEAN on the fixed Windows host and is FROZEN**
   (`data/eval/champions-panel-v0/i8-microprofile/`, `reports/champions-panel-v0-i8-microprofile.md`;
   git_sha `0730a18`, manifest hash `fdc3706038fde45f`; 20/20 independent validation gates,
   450/450 outcome=ok, 0 contaminated/retries/crashes) — a **cost-mechanism localization only**
   (under `oneshot`, latency scales with process starts/batches, depth-2 ≈12.3 s p95; `persistent`
   ≈144 ms cold / ≈10 ms warm; the ≈2.4× active-vs-inactive foe-Mega cost is now confirmed causally,
   A02 vs A03), **NOT a live latency-gate result and NO Strength claim; the pinned 1000 ms LIVE
   budget is not a per-arm microprofile threshold**. **The I8-D live-latency HARNESS is now merged
   (PR #23 @ `3b6070c`)** — live telemetry (off by default), the closed-schema live-dataset
   validator, the exposure/cap runner + three-way verdict, and the provenance-locked
   `i8d-live-gate` CLI, hardened across two blocking review rounds (final review PASS; full suite
   **2777 passed, 2 skipped, 1 xfailed**); **code + tests only — NO server, battle, live-latency
   run, or evidence executed**. After a team-path wiring fix (PR #26 @ `9fc0f36`) the live-gate RUN
   then executed **once** and returned **`FAIL`**: active foe-Mega p95 **1110.213 ms > 1000 ms**,
   exposure floor met (60 active-valid from 45 distinct battles), `stop_reason=exposure_floor_met`,
   75 battles / 679 decisions, FROZEN (`data/eval/champions-panel-v0/i8d-live/`,
   `reports/champions-panel-v0-i8d-live.md`). A **load-bearing latency FAIL** — the 1000 ms budget
   is **not** moved. The **latency-reduction slice (Lever A) is MERGED via PR #30 @ `6b2f955`** — a behavior-neutral fold
   of the game-mode incoming (`ko_threat`) classification into the decision's single shared `DamageOracle`
   scoring flush, plus hardened counterproofs (full suite 2799/1/1). The **UNCHANGED post-Lever-A I8-D
   live-gate rerun then RAN once on `9d915f2` → FAIL** (active foe-Mega p95 **1160.515 ms** > 1000 ms;
   exposure floor met 60/45; `stop_reason=exposure_floor_met`; 75 battles/679 decisions; evidence frozen
   LOCALLY at `1262e36` under `data/eval/champions-panel-v0/i8d-live-post-lever-a/` + report `fe05054`;
   the 968.513 ms model projection did **not** materialize; the **+50.302 ms** vs the pre-Lever-A FAIL is
   **descriptive only — no causal Lever-A latency effect** is derivable). That evidence/docs PR is now
   MERGED (PR #32 @ `34b088e`), and the **offline latency diagnosis + Lever B (B2) design +
   implementation are MERGED via PR #33 @ `b192825`** (a behavior-neutral decision-start `mixed_batch`
   pre-pass; golden byte-identical; full suite 2835/1/1; CI 8/8; it engages on the gauntlet live path);
   the **UNCHANGED I8-D live-gate rerun then RAN once on `3db4ac7` and returned a valid PASS** — active
   foe-Mega p95 **850.245 ms ≤ 1000 ms**, exposure floor met (60 active-valid from 44 distinct battles;
   72 battles / 651 decisions; `stop_reason=exposure_floor_met`; `seed_log_verified`), evidence frozen
   `4b4be54` + report `062b6d0`. The drop vs the FAILs is **descriptive only** (no causal Lever-B
   latency claim and no run-to-run-variance claim — a single `oneshot` run). **The 1000 ms latency
   blocker is now CLOSED for this run**; the PASS evidence is FROZEN + MERGED (PR #35 @ `6de0578`) and the
   docs-project-organization migration is MERGED (PR #36 @ `9c780a2`); the opponent-Mega
   coverage-gate design + implementation (Plan A) is now MERGED via PR #37 @ `10f9adf` (code +
   tests only, no run); because it touches the LIVE decision-profile v3 write path, the prior
   I8-D PASS does not carry over; the UNCHANGED I8-D latency rerun then RAN once on `bd590c1`
   and returned a valid **PASS** — active foe-Mega p95 **864.94 ms <= 1000 ms**, exposure floor
   met (60 active-valid from 45 distinct battles; 75 battles/679 decisions;
   `stop_reason=exposure_floor_met`; `seed_log_verified`); evidence + report MERGED via PR #39 @ `cbaa4b9`
   under `data/eval/champions-panel-v0/i8d-live-post-coverage-harness/` + verdict report
   `f0d42dd`, kept strictly separate from every prior I8-D run -- comparisons descriptive only,
   no causal or variance claim. The latency precondition for candidate `bd590c1` is CLOSED —
   candidate-identity gap: this does **NOT** close it for `cbaa4b9` (see item 1's closing note
   below). The
   separately-authorized `champions-coverage-gate` then ran exactly once on the new merge SHA
   `cbaa4b9` (after one technical-abort first attempt -- no battle, no verdict, excluded from
   the verdict population) and returned **FAIL** (`stop_reason=schedule_exhausted`; 200
   battles/1956 decisions; safety violations 0; `slot0`/`slot1`/`order_tie` floors met;
   **`both_foe_slots` 0/0 did not meet its 15/6 floor**); evidence frozen LOCALLY (not yet
   merged) at `4109abd` + verdict report `e08412e`
   (`reports/champions-panel-v0-coverage-v0.md`). Strength remains NO-GO -- the coverage-gate
   FAIL is a load-bearing blocker; separately, the latency precondition for this same candidate
   `cbaa4b9` is itself unestablished (candidate-identity gap: the `bd590c1` PASS, identity
   `b3c2e0521505932d`, does not transfer to `cbaa4b9`, identity `93cd419222683f75`, per the
   APPROVED spec's shared-candidate-identity requirement, Sec.5) -- Strength stays NO-GO on both
   grounds.
2. **Champions coverage + Strength design** — the coverage-gate design is MERGED (PR #37 @
   `10f9adf`) and has now RUN once, returning FAIL on `both_foe_slots` zero-exposure (see item 1).
   The immediate next step is a separately-authorized diagnosis/design slice for that
   zero-exposure -- no identical rerun, no post-hoc threshold or schedule change -- followed by
   its own separately-authorized rerun. The independent Strength holdout still needs its own
   design: I7b-B/I7b-C prove the mechanism end-to-end on two battles, but the smoke exposed a
   foe-Mega hypothesis in only **1 of 17** scored decisions and only in slot 1. The
   `rain_offense` panel team is not an independent Strength holdout (reused across
   parser/I5/I6/I7a safety work). **Strength remains NO-GO** until a fresh coverage-gate PASS
   and the independent holdout are both satisfied; a latency PASS alone does not authorize a
   Strength run.
3. **I7a CRLF/config-hash impact audit** — provenance housekeeping that may run in parallel
   with the latency design. It does not block the new profile, but the historical I7a
   `config_hash` must not be cited as cross-platform evidence until the audit classifies it.
4. **Accuracy larger follow-up** — user-gated only; not front track unless reprioritized.
5. **poke-env** — reference-only for parser diffs (`reports/champions-poke-env-reference-audit.md`).

**Reference oracle (not runtime dependency):** `@pkmn/protocol` / `@pkmn/client` differential audit — `reports/champions-pkmn-protocol-differential-audit.md` @ `fc4f251`. Showdown sim `f8ac140` remains ground truth; `pkmn/ps` is comparison oracle only, not a rewrite target.

**EPOké:** later belief-reference audit — **not** part of I7.

**Closed (2026-07-14):** HP-suffix state parser — revalidated @ `62117b5`
(`reports/champions-panel-v0-i5-hpfix-validation.md`): 0 state-degraded non-preview decisions.

**Closed (2026-07-14):** Live damage → calc gen-0 (I6) — wired + 2-battle safety smoke @ `3bcd4b3`
(`reports/champions-panel-v0-i6-smoke.md`): hermetic G2–G11 PASS, `eval-report` SAFETY-PASS.

---

## Active Tracks

### 1. Champions Panel v0

| | |
|---|---|
| **Status** | P0–P4 on main; I5 mixed @ `4da007b`; **HP-suffix PASS** @ `62117b5`; **I6 PASS** @ `3bcd4b3`; audit @ `fc4f251`; **I7 Mega design APPROVED rev. 10** (plan Rev. 9); **I7a own-Mega SAFETY PASS, merged to `main`** @ `1053cf1`; **I7b-A MERGED** @ `cdc55c2`; **I7b-B Tasks 1-6 REVIEW-PASS/MERGED** @ `755b144` (PR #13); **I7b-C PRE-SMOKE REVIEW-PASS + opponent-Mega SAFETY SMOKE PASS · NARROW EXPOSURE** (1/17 decisions, slot 1 only) @ `3d23e654`; **I8-A–C offline latency machinery MERGED via PR #20 @ `32cdd4e`** (measurement machine built & proven offline) — **D0 + Kaggle D0-K cost calibration DONE** (scratch, no verdict); **reps=30, D-2=200/2000, host=fixed-Windows CLOSED**; **microprofile driver MERGED (PR #21 @ `0730a18`); 450-row microprofile RAN CLEAN & FROZEN** (cost-mechanism only; 20/20 gates, 450/450 ok); **I8-D live-latency harness MERGED (PR #23 @ `3b6070c`, code + tests only); team-path fix (PR #26 @ `9fc0f36`); live-gate RUN EXECUTED once → FAIL** (active foe-Mega p95 1110.213 ms > 1000 ms; exposure floor met 60/45; 75 battles/679 decisions; FROZEN `data/eval/champions-panel-v0/i8d-live/` + `reports/champions-panel-v0-i8d-live.md`); **latency-reduction slice (Lever A) MERGED via PR #30 @ `6b2f955` (behavior-neutral fold + hardened counterproofs, full suite 2799/1/1); the UNCHANGED post-Lever-A I8-D live-gate rerun then RAN once on `9d915f2` → **FAIL** (active foe-Mega p95 1160.515 ms > 1000 ms; exposure floor met 60/45; 75 battles/679 decisions; stop=exposure_floor_met; evidence frozen locally `1262e36` + report `fe05054`; the 968.513 ms model projection did NOT materialize; the +50.302 ms vs the pre-Lever-A FAIL is descriptive only — no causal Lever-A latency effect); evidence/docs PR MERGED (PR #32 @ `34b088e`); offline latency diagnosis + Lever B (B2) design + impl MERGED via PR #33 @ `b192825` (behavior-neutral decision-start `mixed_batch` pre-pass, golden byte-identical, full suite 2835/1/1, CI 8/8, engages on the live path); the UNCHANGED I8-D live-gate rerun then RAN once on `3db4ac7` → valid **PASS** (active foe-Mega p95 850.245 ms ≤ 1000 ms; exposure floor met 60/44; 72 battles/651 decisions; stop=exposure_floor_met; seed_log_verified; evidence `4b4be54`, report `062b6d0`); drop vs the FAILs descriptive only (no causal Lever-B or variance claim); **latency blocker CLOSED**; the opponent-Mega coverage-gate design + implementation (Plan A) is now MERGED via PR #37 @ `10f9adf` (code + tests only, no run); because it touches the LIVE decision-profile v3 write path, the prior I8-D PASS does not carry over; the UNCHANGED rerun then RAN once on `bd590c1` -> **PASS** (p95 864.94 ms <= 1000 ms; 60/45; 75 battles/679 decisions; exposure_floor_met; seed_log_verified; evidence + report MERGED via PR #39 @ `cbaa4b9`); latency precondition for `bd590c1` CLOSED (but NOT for `cbaa4b9` -- identity gap, does not transfer); the coverage gate then ran once on `cbaa4b9` (after one technical-abort attempt, excluded from the verdict population) -> **FAIL** (`schedule_exhausted`; 200 battles/1956 decisions; safety violations 0; `slot0`/`slot1`/`order_tie` floors met; `both_foe_slots` 0/0 floor NOT met; evidence frozen locally `4109abd` + report `e08412e`); next = review+merge this evidence/docs, then a separately-authorized diagnosis/design slice for the zero-exposure — now **DIAGNOSED + REMEDIATED** (T1 `cov_foe_both` team redesign, T2 shared `candidate_identity` helper, T3 same-candidate I8-D-PASS gate, four independent review rounds hardening the I8-D-verdict guard to the full real 25-field schema) and **MERGED via PR #42 @ `f2bb818`** (2026-07-21; full suite 2971 passed/18 pre-existing unrelated failed/1 skipped/1 xfailed) — safety/provenance/defect-fix only, no live gate ran; next = a separately-authorized I8-D rerun on the fresh candidate identity for `f2bb818` (new `git_sha`, does not inherit `bd590c1`/`cbaa4b9`), then, only if PASS, a separately-authorized coverage-gate rerun with the repaired team (no identical rerun of the FAIL, no post-hoc threshold/schedule change)**; Kaggle = coverage-only stratum, never pooled — **latency blocker CLOSED for candidate bd590c1; Strength NO-GO**. |
| **Format** | `gen9championsvgc2026regma` (Champions M-A BO1) |
| **Panel hash** | `aac1ea30446fde88` (pinned in `config/eval/panels/panel_champions_v0.yaml`) |

**Phase evidence**

| Phase | Verdict | Primary artifacts |
|-------|---------|-------------------|
| P0 Format discovery | PASS | `reports/champions-panel-v0-format-discovery.md` |
| P1 Mechanics audit | PASS | `reports/champions-panel-v0-mechanics-audit.md` |
| P2 Team curation | PASS @ `7660d44` | `showdown_bot/teams/panel_champions_v0/`, `PROVENANCE.md` |
| P3 Panel freeze | PASS @ `550f1ad` | `config/eval/panels/panel_champions_v0.yaml`, `showdown_bot/tests/test_panel.py` |
| P4 Pilot smoke | PASS @ `04b0eb7` (`dirty=false`) | `reports/champions-panel-v0-pilot-smoke.md`, `data/eval/champions-panel-v0/smoke/` |
| I5 FormatConfig smoke | **Mixed** @ `4da007b` (`dirty=false`) | `reports/champions-panel-v0-i5-smoke.md`, `data/eval/champions-panel-v0/smoke-i5/` |
| I5 HP-fix revalidation | **HP-SUFFIX PASS** @ `62117b5` (`dirty=false`) | `reports/champions-panel-v0-i5-hpfix-validation.md`, `data/eval/champions-panel-v0/smoke-i5-hpfix-validation/` (incl. `suffix-evidence.json`) |
| I6 Live-damage gen-0 smoke | **I6 PASS · 2-BATTLE SAFETY-PASS** @ `3bcd4b3` (`dirty=false`) | `reports/champions-panel-v0-i6-smoke.md`, `data/eval/champions-panel-v0/smoke-i6-damage-gen0/` |
| I7a-C own-Mega smoke | **I7a OWN-MEGA SAFETY PASS, merged to `main`** @ `1053cf1` (`dirty=false`) | `reports/champions-panel-v0-i7a-mega-smoke.md`, `data/eval/champions-panel-v0/smoke-i7a-mega/` (incl. `mega-evidence.json`) |
| I7b-A opponent-Mega foundation | **IMPLEMENTED · CODE-REVIEWED · MERGED via PR #12 @ `cdc55c2`** (focused gate 106 passed; full suite 2132 passed, 2 skipped, 1 xfailed) · additive/inert until I7b-B | `docs/projects/champions/audits/2026-07-16-champions-opponent-mega-i7b-audit.md`, `docs/projects/champions/plans/2026-07-16-champions-opponent-mega-i7b.md` |
| I7b-B dual projection + scoring | **REVIEW-PASS · MERGED via PR #13 @ `755b144`** (Tasks 1-6; full suite 2169 passed, 2 skipped, 1 xfailed, no new skip/xfail) · foe-Mega modeling LIVE for `format_config.mega`, byte-identical for Reg-I/`None` · `baselines.py`/`search.py` byte-identical across the slice | plan Rev. 7 (`docs/projects/champions/plans/2026-07-16-champions-opponent-mega-i7b.md`); no report — no live run, no Strength claim |
| I7b-C telemetry + opponent-Mega smoke | **PRE-SMOKE REVIEW-PASS + LIVE SMOKE PASS · NARROW EXPOSURE** @ `3d23e654` (`dirty=false`; 19/19 standard gates PASS, worst p95 672 ms; 19/19 trace-v3 rows, 17/17 sidecar rows LF-only; every sidecar `(battle_id, decision_index)` → exactly one trace row, gaps only at `team_preview`) · **1 of 17** decisions exposed a foe-Mega hypothesis, **slot 1 only** — slot 0/dual-Mega/activation-ordering never exercised live · **no Strength claim, no latency claim** | `reports/champions-panel-v0-i7b-mega-smoke.md`, `data/eval/champions-panel-v0/smoke-i7b-mega/` (incl. `opp_mega_trace.jsonl`, `results.jsonl.config-manifest.json`); plan Rev. 9 |
| I8 offline latency machinery (A–C) | **MERGED via PR #20 @ `32cdd4e`** — instrumentation, decision-profile sidecar + both validator tiers, manifest producer, microprofile arm matrix/harness, and all six previously-blocked arms (P-1…P-5), built & proven **offline** against a production-topology session (full suite **2615 passed, 2 skipped, 1 xfailed**) · **D0 + Kaggle D0-K cost calibration DONE** (scratch, no verdict); **reps=30, D-2=200/2000, host=fixed-Windows CLOSED**; **microprofile driver MERGED (PR #21 @ `0730a18`) and the 450-row microprofile RAN CLEAN & FROZEN** (cost-mechanism only; 20/20 gates, 450/450 ok; no live-latency/Strength verdict); **I8-D live-latency HARNESS merged (PR #23 @ `3b6070c`, code + tests only); team-path fix PR #26 @ `9fc0f36`; live-gate RUN EXECUTED once → FAIL** (p95 1110.213 ms > 1000 ms; frozen); **latency-reduction slice (Lever A) MERGED via PR #30 @ `6b2f955` (behavior-neutral fold + hardened counterproofs, full suite 2799/1/1); the UNCHANGED post-Lever-A I8-D live-gate rerun then RAN once on `9d915f2` → **FAIL** (active foe-Mega p95 1160.515 ms > 1000 ms; exposure floor met 60/45; 75 battles/679 decisions; stop=exposure_floor_met; evidence frozen locally `1262e36` + report `fe05054`; the 968.513 ms model projection did NOT materialize; the +50.302 ms vs the pre-Lever-A FAIL is descriptive only — no causal Lever-A latency effect); evidence/docs PR MERGED (PR #32 @ `34b088e`); offline latency diagnosis + Lever B (B2) design + impl MERGED via PR #33 @ `b192825` (behavior-neutral decision-start `mixed_batch` pre-pass, golden byte-identical, full suite 2835/1/1, CI 8/8, engages on the live path); the UNCHANGED I8-D live-gate rerun then RAN once on `3db4ac7` → valid **PASS** (active foe-Mega p95 850.245 ms ≤ 1000 ms; exposure floor met 60/44; 72 battles/651 decisions; stop=exposure_floor_met; seed_log_verified; evidence `4b4be54`, report `062b6d0`); drop vs the FAILs descriptive only (no causal Lever-B or variance claim); **latency blocker CLOSED**; the opponent-Mega coverage-gate design + implementation (Plan A) is now MERGED via PR #37 @ `10f9adf` (code + tests only, no run); because it touches the LIVE decision-profile v3 write path, the prior I8-D PASS does not carry over; the UNCHANGED rerun then RAN once on `bd590c1` -> **PASS** (p95 864.94 ms <= 1000 ms; 60/45; 75 battles/679 decisions; exposure_floor_met; seed_log_verified; evidence + report MERGED via PR #39 @ `cbaa4b9`); latency precondition for `bd590c1` CLOSED (but NOT for `cbaa4b9` -- identity gap, does not transfer); the coverage gate then ran once on `cbaa4b9` (after one technical-abort attempt, excluded from the verdict population) -> **FAIL** (`schedule_exhausted`; 200 battles/1956 decisions; safety violations 0; `slot0`/`slot1`/`order_tie` floors met; `both_foe_slots` 0/0 floor NOT met; evidence frozen locally `4109abd` + report `e08412e`); next = review+merge this evidence/docs, then a separately-authorized diagnosis/design slice for the zero-exposure — now **DIAGNOSED + REMEDIATED** (T1 `cov_foe_both` team redesign, T2 shared `candidate_identity` helper, T3 same-candidate I8-D-PASS gate, four independent review rounds hardening the I8-D-verdict guard to the full real 25-field schema) and **MERGED via PR #42 @ `f2bb818`** (2026-07-21; full suite 2971 passed/18 pre-existing unrelated failed/1 skipped/1 xfailed) — safety/provenance/defect-fix only, no live gate ran; next = a separately-authorized I8-D rerun on the fresh candidate identity for `f2bb818` (new `git_sha`, does not inherit `bd590c1`/`cbaa4b9`), then, only if PASS, a separately-authorized coverage-gate rerun with the repaired team (no identical rerun of the FAIL, no post-hoc threshold/schedule change)**; **Kaggle = coverage-only stratum, never pooled** | `docs/projects/champions/specs/2026-07-16-champions-i8-latency-design.md`, `docs/projects/champions/plans/2026-07-17-champions-i8-latency.md`; **microprofile evidence `data/eval/champions-panel-v0/i8-microprofile/` + `reports/champions-panel-v0-i8-microprofile.md`** |
| I8-D live-latency harness | **MERGED via PR #23 @ `3b6070c`** — live telemetry (off by default) + closed-schema live-dataset validator + exposure/cap runner & three-way verdict + provenance-locked `i8d-live-gate` CLI; hardened across two blocking review rounds (final review PASS); full suite **2777 passed, 2 skipped, 1 xfailed** · **code + tests only** at merge · team-path fix (PR #26 @ `9fc0f36`) · **live-gate RUN EXECUTED once → FAIL** (active foe-Mega p95 1110.213 ms > 1000 ms; exposure floor met 60/45; `stop_reason=exposure_floor_met`; 75 battles/679 decisions; independently re-verified from frozen bytes) · **latency-reduction slice (Lever A) MERGED via PR #30 @ `6b2f955` (behavior-neutral fold + hardened counterproofs, full suite 2799/1/1); the UNCHANGED post-Lever-A I8-D live-gate rerun then RAN once on `9d915f2` → **FAIL** (active foe-Mega p95 1160.515 ms > 1000 ms; exposure floor met 60/45; 75 battles/679 decisions; stop=exposure_floor_met; evidence frozen locally `1262e36` + report `fe05054`; the 968.513 ms model projection did NOT materialize; the +50.302 ms vs the pre-Lever-A FAIL is descriptive only — no causal Lever-A latency effect); evidence/docs PR MERGED (PR #32 @ `34b088e`); offline latency diagnosis + Lever B (B2) design + impl MERGED via PR #33 @ `b192825` (behavior-neutral decision-start `mixed_batch` pre-pass, golden byte-identical, full suite 2835/1/1, CI 8/8, engages on the live path); the UNCHANGED I8-D live-gate rerun then RAN once on `3db4ac7` → valid **PASS** (active foe-Mega p95 850.245 ms ≤ 1000 ms; exposure floor met 60/44; 72 battles/651 decisions; stop=exposure_floor_met; seed_log_verified; evidence `4b4be54`, report `062b6d0`); drop vs the FAILs descriptive only (no causal Lever-B or variance claim); **latency blocker CLOSED**; the opponent-Mega coverage-gate design + implementation (Plan A) is now MERGED via PR #37 @ `10f9adf` (code + tests only, no run); because it touches the LIVE decision-profile v3 write path, the prior I8-D PASS does not carry over; the UNCHANGED rerun then RAN once on `bd590c1` -> **PASS** (p95 864.94 ms <= 1000 ms; 60/45; 75 battles/679 decisions; exposure_floor_met; seed_log_verified; evidence + report MERGED via PR #39 @ `cbaa4b9`); latency precondition for `bd590c1` CLOSED (but NOT for `cbaa4b9` -- identity gap, does not transfer); the coverage gate then ran once on `cbaa4b9` (after one technical-abort attempt, excluded from the verdict population) -> **FAIL** (`schedule_exhausted`; 200 battles/1956 decisions; safety violations 0; `slot0`/`slot1`/`order_tie` floors met; `both_foe_slots` 0/0 floor NOT met; evidence frozen locally `4109abd` + report `e08412e`); next = review+merge this evidence/docs, then a separately-authorized diagnosis/design slice for the zero-exposure — now **DIAGNOSED + REMEDIATED** (T1 `cov_foe_both` team redesign, T2 shared `candidate_identity` helper, T3 same-candidate I8-D-PASS gate, four independent review rounds hardening the I8-D-verdict guard to the full real 25-field schema) and **MERGED via PR #42 @ `f2bb818`** (2026-07-21; full suite 2971 passed/18 pre-existing unrelated failed/1 skipped/1 xfailed) — safety/provenance/defect-fix only, no live gate ran; next = a separately-authorized I8-D rerun on the fresh candidate identity for `f2bb818` (new `git_sha`, does not inherit `bd590c1`/`cbaa4b9`), then, only if PASS, a separately-authorized coverage-gate rerun with the repaired team (no identical rerun of the FAIL, no post-hoc threshold/schedule change)** | `docs/projects/champions/specs/2026-07-16-champions-i8-latency-design.md`, `docs/projects/champions/plans/2026-07-17-champions-i8-latency.md`; harness on `main` @ `3b6070c`; **FAIL evidence `data/eval/champions-panel-v0/i8d-live/` + `reports/champions-panel-v0-i8d-live.md`** |

**Open blockers**

- **Latency gate (I8-D):** the measurement machinery is merged (I8-A–C PR #20 @ `32cdd4e`;
  microprofile driver PR #21 @ `0730a18`), the **offline 450-row microprofile ran clean & is
  frozen**, and the **I8-D live-latency harness is now merged (PR #23 @ `3b6070c`, code + tests
  only)** and, after a team-path wiring fix, the **LIVE latency gate has now RUN once → FAIL**
  (below). **The first two live attempts ABORTED before battle creation (2026-07-18, no verdict/evidence/latency statement):** on
  the fixed Windows host both created **zero battles** (`seeds.jsonl` absent, `out/` never published).
  **Root cause = an I8-D team-path wiring bug** — `run_local_gauntlet` loads teams CWD-relative, the
  gate runs from the repo root, the teams live under `showdown_bot/teams/`, and `--teams-root` only
  hashed the teams (didn't LOAD them), so `_resolve_side_teams` silently degraded missing files to
  EMPTY teams → server rejected → 0 battles → timeout. **Neither the 180 s nor the 900 s timeout was
  ever the cause.** The **900 s decision is RETRACTED** (wrong "slow battle" diagnosis, never
  exercised; `config_hash 06b2b96e76486563` void). Logs are scratch-only, **not pooled**. The fix
  threads `teams_root` into the I8-D runner (absolute team paths + non-empty proof before the battle;
  `run_schedule` untouched; PR #26 @ `9fc0f36`); the corrected run took the **original stratum**
  (`oneshot`, **standard 180 s / no `SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S`**, `config_hash 594295543f13a55d`,
  seed 0), created **75** battles (vs **0** in both aborts), and produced the **first real verdict:
  `FAIL`** — active foe-Mega p95 **1110.213 ms > 1000 ms**, exposure floor met (60 active-valid from
  45 distinct battles), `stop_reason=exposure_floor_met`, 679 decisions, `seed_log_verified`, FROZEN
  (`data/eval/champions-panel-v0/i8d-live/`, `reports/champions-panel-v0-i8d-live.md`).
  Context: I5 pre-fix worst p95 **3235 ms** vs
  the pinned **1000 ms** budget (that run also contained state-degradation; no causal link);
  I6/I7a-C/I7b-C safety smokes measured 331/588/672 ms, none a dedicated profile; the active
  foe-Mega path still measures about **2.4×** the inactive decision on the synthetic tie fixture.
  D0 and its Kaggle **D0-K** calibration ran (cost data only, scratch, no verdict), closing the
  execution decisions (**`reps`=30**, **`MAX_BATTLES`=200 / `MAX_SCORED_DECISIONS`=2000**, **fixed
  Windows host**). The **450-row microprofile then RAN CLEAN & FROZEN**
  (`data/eval/champions-panel-v0/i8-microprofile/`) — cost-mechanism only (oneshot scales with
  process starts/batches; persistent ≈144 ms cold / ≈10 ms warm; the ≈2.4× active-vs-inactive
  foe-Mega cost now confirmed causally, A02 vs A03), **no live-latency/Strength verdict**. The
  **I8-D live-latency harness is merged (PR #23 @ `3b6070c`)** and, after the team-path fix
  (PR #26 @ `9fc0f36`), the **live-gate RUN executed once → FAIL** (above). The **latency-reduction slice (Lever A) is MERGED via PR #30 @ `6b2f955`** — a behavior-neutral fold of
  the game-mode incoming (`ko_threat`) classification into the decision's single shared `DamageOracle`
  scoring flush, plus hardened counterproofs (full suite 2799/1/1). The **UNCHANGED post-Lever-A I8-D
  live-gate rerun then RAN once on `9d915f2` → FAIL** (active foe-Mega p95 **1160.515 ms** > 1000 ms;
  exposure floor met 60/45; `stop_reason=exposure_floor_met`; 75 battles/679 decisions; evidence frozen
  LOCALLY at `1262e36` under `data/eval/champions-panel-v0/i8d-live-post-lever-a/` + report `fe05054`;
  the 968.513 ms model projection did **not** materialize; the **+50.302 ms** vs the pre-Lever-A FAIL is
  **descriptive only — no causal Lever-A latency effect**). That evidence/docs PR is now MERGED (PR #32
  @ `34b088e`), and the **offline latency diagnosis + Lever B (B2) design + implementation are MERGED
  via PR #33 @ `b192825`** (a behavior-neutral decision-start `mixed_batch` pre-pass; golden
  byte-identical; full suite 2835/1/1; CI 8/8; it engages on the gauntlet live path); the **UNCHANGED
  I8-D live-gate rerun then RAN once on `3db4ac7` and returned a valid PASS** — active foe-Mega p95
  **850.245 ms ≤ 1000 ms**, exposure floor met (60 active-valid from 44 distinct battles; 72 battles /
  651 decisions; `stop_reason=exposure_floor_met`; `seed_log_verified`), evidence `4b4be54` + report
  `062b6d0`. The drop vs the FAILs is **descriptive only** (no causal Lever-B or run-to-run-variance
  claim — a single `oneshot` run). **The 1000 ms latency blocker is now CLOSED for this run**; the PASS evidence is
  FROZEN + MERGED (PR #35 @ `6de0578`) and the docs-project-organization migration is MERGED (PR #36 @ `9c780a2`);
  the opponent-Mega coverage-gate design + implementation (Plan A) is now MERGED via PR #37 @
  `10f9adf` (code + tests only, no run — two ultrareview rounds resolved, 6 P1s + 2 follow-ups).
  Because it touches the LIVE decision-profile v3 write path, the prior I8-D PASS does not carry
  over. The separately-authorized **I8-D latency RERUN** (fresh worktree on the merge SHA,
  preflight, then an unchanged run) has now RUN on candidate `bd590c1` → **PASS** (active foe-Mega
  p95 864.94 ms ≤ 1000 ms budget; exposure floor met — 60 active-valid decisions from 45 distinct
  battles; 75 battles/679 decisions; `exposure_floor_met`; `seed_log_verified`; evidence frozen
  locally at `1166627`, report `f0d42dd`). The latency precondition for `bd590c1` is CLOSED (evidence + report MERGED via PR #39 @
  `cbaa4b9`) — but candidate-identity gap: this does **NOT** close the latency precondition for
  `cbaa4b9` itself (`bd590c1` identity `b3c2e0521505932d` != `cbaa4b9` identity
  `93cd419222683f75`; APPROVED spec Sec.5 requires the identical identity, no transfer). The
  separately-authorized `champions-coverage-gate` then ran exactly once on
  `cbaa4b9` (after one technical-abort first attempt, excluded from the verdict population) and
  returned **FAIL** (`schedule_exhausted`; 200 battles/1956 decisions; safety violations 0;
  `slot0`/`slot1`/`order_tie` floors met; `both_foe_slots` 0/0 floor NOT met; evidence frozen
  LOCALLY, not yet merged, at `4109abd` + report `e08412e`). The zero-exposure
  diagnosis/design slice is now **DONE** — diagnosed (the real preview picker never led with both
  Mega holders, so the cell was structurally unreachable) and remediated (T1 `cov_foe_both` team
  redesign, T2 shared `candidate_identity` helper, T3 same-candidate I8-D-PASS gate, four
  independent review rounds hardening the I8-D-verdict guard to the full real 25-field schema +
  cross-field consistency + NaN/negative rejection) and **MERGED via PR #42 @ `f2bb818`** (full
  suite 2971 passed / 18 pre-existing unrelated failed / 1 skipped / 1 xfailed, zero new
  failures) — **safety/provenance/defect-fix only, no live gate ran, no Strength claim**. Next =
  a separately-authorized I8-D latency rerun on the fresh candidate identity for `f2bb818` (a new
  `git_sha` carries a new identity; `bd590c1`/`cbaa4b9` do not transfer), then — only if PASS — a
  separately-authorized coverage-gate rerun with the repaired team; only after a fresh coverage
  PASS AND the independent Strength-holdout **design** (spec first — no run) both pass does a
  Strength run become possible. The
  1000 ms budget is **not** moved; do not lower the click rate or change the budget to manufacture a
  PASS.
- **Opponent-Mega live coverage:** I7b-C is merged and its telemetry chain is live, but the
  frozen smoke exposed a hypothesis in only **1/17** scored decisions and only for foe slot 1.
  The pre-registered `champions-coverage-gate` (a fixed 200-battle schedule over the four target
  cells `slot0`/`slot1`/`both_foe_slots`/`order_tie`, live-only decision-profile v3 telemetry,
  per-cell floor/cap three-way verdict) is now **designed and MERGED via PR #37 @ `10f9adf`
  (code + tests only)**. The fresh I8-D latency rerun that gated it (the v3 schema change touches
  the live decision path, so the prior latency PASS did not carry over) RAN on candidate
  `bd590c1` → **PASS** (p95 864.94 ms ≤ 1000 ms; evidence + report MERGED via PR #39 @
  `cbaa4b9`); the latency precondition is CLOSED. The coverage gate itself has now also **RUN
  exactly once**, on the new merge SHA `cbaa4b9` (after one technical-abort first attempt,
  excluded from the verdict population), and returned **FAIL** (`schedule_exhausted`; 200
  battles/1956 decisions; safety violations 0; `slot0`/`slot1`/`order_tie` floors met;
  **`both_foe_slots` 0/0 did not meet its 15/6 floor** — the verdict driver; evidence frozen
  LOCALLY, not yet merged, at `4109abd`, report `e08412e`). The zero-exposure root cause is now
  **DIAGNOSED** (the real preview picker never led with both Mega holders, so the cell was
  structurally unreachable) and **REMEDIATED** — T1 (`cov_foe_both` team redesign), T2 (shared
  `candidate_identity` helper), T3 (same-candidate I8-D-PASS gate) plus four independent review
  rounds hardening the I8-D-verdict guard — **MERGED via PR #42 @ `f2bb818`** (full suite 2971
  passed / 18 pre-existing unrelated failed / 1 skipped / 1 xfailed) — safety/provenance/defect-fix
  work only, no live gate ran. It is now blocked behind a separately-authorized I8-D latency
  rerun on the fresh candidate identity for `f2bb818`, then — only if PASS — a
  separately-authorized coverage-gate rerun with the repaired team, before any Strength result can
  be interpreted broadly.
- **Independent Strength holdout:** `rain_offense` is development/safety evidence, not a fresh
  holdout. A new holdout and statistical decision rule must be approved before a Strength run.

**Closed blockers**

- ~~Mega overlay / opponent-Mega telemetry~~ — I7a + I7b-A/B/C are merged; I7b-C live smoke
  and sidecar evidence are frozen under `data/eval/champions-panel-v0/smoke-i7b-mega/`.
- ~~Champions-Mega CI coverage~~ — the parallel `champions-mega` job runs I7a/I7b plus
  generated-metadata freshness; PR #17 additionally ran the platform-provenance matrix.
- ~~Live damage path (gen-0 calc_profile)~~ — I6 @ `3bcd4b3`; hermetic G2–G11 + 2-battle smoke (`reports/champions-panel-v0-i6-smoke.md`).
- ~~HP-suffix state parser (`100y`/`100g`/`100r`)~~ — fixed @ `62117b5`; revalidated 0/99 degraded (`reports/champions-panel-v0-i5-hpfix-validation.md`).

**Explicit non-claims**

- I6 proves **gen-0 calc_profile wiring + minimal harness safety** on 2 battles — not strength.
- I5 proves **config/provenance wiring + harness completion** on a 10-row panel — not strength, not full safety pass, not full heuristic fidelity.
- Hero win counts (P4 2/6, I5 3/10, I6 0/2) are **not** interpreted.

**Related**

- poke-env audit (reference): `reports/champions-poke-env-reference-audit.md` @ `75bbb4b`
- pkmn/ps protocol differential audit (I7 design input): `reports/champions-pkmn-protocol-differential-audit.md` @ `fc4f251`
- Design: `docs/projects/champions/specs/2026-07-14-champions-panel-v0-design.md`
- I7 Mega design: `docs/projects/champions/specs/2026-07-14-champions-mega-i7-design.md`

---

### 2. Accuracy Default-On

| | |
|---|---|
| **Status** | **Implemented** @ `8c54843`. Default-on when env unset; branch cap **6**; explicit opt-out unchanged. |
| **Gate-B** | cap=6 and cap=8 **PASS** (6/944 = 0.64%) after Candidate Identity; frozen cap=4 FAIL reference unchanged (114/881). |
| **Dev-strength A/B** | **SAFETY-PASS** @ `a956b6b`; strength **UNDERPOWERED** (n_discordant=6); unfavorable direction (0 A-only / 6 B-only discordants) — **no strength claim**. |

**Authoritative artifacts**

- Decision note: `reports/2026-07-14-accuracy-default-on-decision-note.md`
- Dev-strength verdict: `reports/2026-07-14-accuracy-default-on-devstrength-verdict.md`
- Spec: `docs/projects/accuracy/specs/2026-07-14-accuracy-default-on-design.md`
- Gate data: `data/eval/accuracy-gate/gate-b-report.json` (frozen cap=4),
  `data/eval/accuracy-cap-derisk/cap{6,8}-report.json`
- Run data: `data/eval/accuracy-default-on/devstrength-ab/`

**Open blockers**

- None for **default-on safety**; no **GO on strength**.
- Larger re-run is **user-gated** (power discordant floor vs Champions work).

**Explicit non-claims**

- Default-on does **not** improve or preserve winrate (underpowered A/B).
- Not equivalence, not regression proven, not held-out generalization.

---

### 3. Candidate Identity

| | |
|---|---|
| **Status** | **Merged** @ `9f64c28`. Structural candidate keys live in `showdown_bot/battle/candidate_identity.py`. |
| **Fix** | 63 historically ambiguous Gate-B decisions resolved via per-slot structural keys
  `(kind, move_index, target, target_ident, terastallize)` — not `_label_ja` collision guessing. |
| **Trace schema** | v2 emit (`trace_schema_version`: `decision-trace-v2`); v1 read compatibility retained in consumers. |

**Authoritative artifacts**

- Gate refresh addendum: `reports/2026-07-13-accuracy-cap-derisk-verdict.md` (2026-07-14 section)
- Tests: `showdown_bot/tests/eval/test_candidate_identity_replay.py`, `test_decision_capture.py`

**Open blockers**

- None for identity resolution itself.
- Downstream reruns / re-exports only as needed when consuming old traces.

**Explicit non-claims**

- Fixing identity does **not** authorize default-on or strength claims by itself.

---

### 4. Accuracy Cap / Hit Probability

| | |
|---|---|
| **Status** | Hit-probability evaluation **implemented**; cap de-risk **done**. Production default cap = **6**. |
| **History** | cap=4 **FAIL** (12.9% cap-hit rate, frozen reference). cap=6 / cap=8 **PASS** after Candidate Identity. |

**Authoritative artifacts**

- Cap de-risk verdict: `reports/2026-07-13-accuracy-cap-derisk-verdict.md`
- Offline gate (parent FAIL): `reports/2026-07-13-accuracy-offline-gate-verdict.md`
- Latency sweep: `data/eval/accuracy-cap-derisk/latency-results.json`

**Open blockers**

- None for current default (cap 6, mode on).
- `accuracy_diagnostics()` still not wired into live `DecisionTrace` callers (roadmap P0 item; partial progress via `accuracy_details` on candidates).

**Explicit non-claims**

- Cap de-risk numbers do **not** imply strength GO or Depth-2 Stage 3 work.

---

### 5. External Battle Logs / VGC-Bench / HolidayOugi

| | |
|---|---|
| **Status** | **PROPOSED** — read-only import-audit spec only; execution **not approved**. |
| **Trust model** | Track A/B: VGC-Bench (high trust). Track C: HolidayOugi replays (lower trust, optional). |

**Authoritative artifacts**

- Spec: `docs/projects/evaluation/audits/2026-07-14-vgc-battle-logs-import-audit.md` (PROPOSED @ `1251dd6`)
- Part A ingest (separate, done): `6210e4d` — `load_raw`, `parse_battle`, `gate_format`

**Open blockers**

- Explicit user approval before any Phase 0a–0d execution.
- No mixing with current accuracy or Champions eval gates.

**Explicit non-claims**

- Not started for import audit execution.
- **No raw large data commits** (~GB-scale Parquet stays out of repo).
- Not a substitute for Champions panel work or accuracy gates.

---

### 6. Value-Calibration / Value-Head

| | |
|---|---|
| **Status** | **Spec Revision 2 committed** (`docs/projects/learning/specs/2026-07-12-value-calibration-design.md` @ `8e4c47f`); **implementation not started** — awaits explicit sign-off → plan → run. |
| **Role** | Diagnostic: does action carry signal beyond board state? Positive outcome = **GO for counterfactual data collection**, not proof a value-head is justified. |

**Authoritative artifacts**

- Spec: `docs/projects/learning/specs/2026-07-12-value-calibration-design.md`
- Outcome-join infra (built): `showdown_bot/learning/outcome_join/`
- Dataset: `data/datasets/phase3-slice2b25a/`

**Open blockers**

- Spec sign-off and implementation plan before any run.
- Depth-2 Stage 3 and dev-generalization panel remain separately gated (see roadmap P1).

**Explicit non-claims**

- Not current implementation front unless explicitly resumed.
- Value-head training (**P4**) remains deliberately deferred.

---

## Do Not Reopen Unless Explicitly Asked

- **Accuracy default flip** — already implemented (`8c54843`); do not relitigate without new data.
- **poke-env foundation rewrite** — reference-only per `reports/champions-poke-env-reference-audit.md`.
- **Strength claim from P4/I5 Champions smoke** — explicitly forbidden.
- **Large public-log imports into eval gates** — import audit is PROPOSED, not approved.
- **Global scalar λ tuning** — exhausted as a strength lever (see roadmap scalar-aggregation table).
- **Reranker live override** — NO-GO (2b-4); infrastructure remains in use.

---

## First Files To Read For New Agents

1. **`docs/PROJECT_INDEX.md`** (this file) — orientation.
2. **`docs/ROADMAP.md`** — authoritative status matrix and sequencing.
3. **Active track report** for the task at hand, e.g.:
   - Champions: `reports/champions-panel-v0-i6-smoke.md` (I6), `reports/champions-panel-v0-i5-smoke.md` (I5), `reports/champions-panel-v0-pilot-smoke.md` (P4)
   - Accuracy: `reports/2026-07-14-accuracy-default-on-decision-note.md`
   - Parser follow-up: `reports/champions-poke-env-reference-audit.md`
4. **Relevant tests** — e.g. `showdown_bot/tests/test_panel.py`, `showdown_bot/tests/eval/test_candidate_identity_replay.py`, request fixtures under `showdown_bot/tests/fixtures/`.
5. **Working agreement** — `AGENTS.md` / `CLAUDE.md` (partnership: verify claims against code, do not reflexively agree).

---

## Quick Links

| Need | Go to |
|------|--------|
| What to build next | [Current Priority](#current-priority) + `docs/ROADMAP.md` |
| Champions panel config | `config/eval/panels/panel_champions_v0.yaml` |
| Champions smoke schedule (P4) | `config/eval/schedules/champions_v0_smoke_pilot.yaml` |
| Champions smoke schedule (I5) | `config/eval/schedules/champions_v0_smoke_i5.yaml` |
| Champions smoke schedule (I6) | `config/eval/schedules/champions_v0_smoke_i6_2battle.yaml` |
| Champions smoke schedule (I7b-C) | `config/eval/schedules/champions_v0_smoke_i7b_2battle.yaml` |
| Opponent-Mega frozen evidence | `data/eval/champions-panel-v0/smoke-i7b-mega/` + `reports/champions-panel-v0-i7b-mega-smoke.md` |
| Eval provenance pattern | `data/eval/champions-panel-v0/smoke-i5/` (I5 baseline), `smoke-i5-hpfix-validation/` (HP-fix revalidation @ `62117b5`), `smoke-i6-damage-gen0/` (I6 @ `3bcd4b3`) |
| Accuracy env knobs | `SHOWDOWN_ACCURACY_MODE`, `SHOWDOWN_ACCURACY_BRANCH_CAP` |
| Future ShowdownBot Studio desktop client (not active front track) | `showdownbot_studio/README.md` |
