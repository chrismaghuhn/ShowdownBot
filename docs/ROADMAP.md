# Canonical Roadmap & Status

**Living document — update as slices land, don't let it drift.** This supersedes the old
layered plans (README, `docs/guides/heuristic-bot/`, and the external `../TestBOtpläne/00-14`
Northstar docs) as the single source of truth for *current status and next decision*.
`TestBOtpläne/` remains valid for deep design rationale on things already built, but it is
**not versioned with the code** and must not be read as an up-to-date execution plan —
verify against this file and git history first.

**New agents:** start with [`docs/PROJECT_INDEX.md`](PROJECT_INDEX.md) for orientation; this
roadmap remains the authoritative status matrix.

Last reconciled: 2026-07-23 (**Champions Gate B — the Independent Strength Holdout RAN and returned SAFETY-FAIL on candidate `bc2d6df`, candidate identity `32f79b8e52444aa3` (hero `heuristic`, baseline `max_damage`): the candidate emitted 1 illegal action (`invalid_choices` A=1 / B=0; server `Can't switch: The active Pokémon is trapped`) in battle `9ccc312c51d95bfe`, and the fail-closed safety gate failed the run regardless of margin — root cause PLAUSIBLE not CONFIRMED (one active slot `trapped:true`, the other `maybeTrapped:true` upgraded on re-request; which slot was actually chosen is NOT settleable from the frozen room-log). Harness fixes PR #54 @ `a7d5330` (Windows-retry-safe atomic publish) + PR #55 @ `bc2d6df` (combine derives the upstream `teams_root` from repo_root) landed first. All three gates ran on the SAME identity, no commits between: I8-D latency PASS (active foe-Mega p95 873.762 ms ≤ 1000 ms, `p95_is_gate_value=true`) and opponent-Mega coverage PASS (0 safety violations, `stop_reason=coverage_floor_met`) — that latency/coverage evidence is EXTERNAL and UNFROZEN and must NOT be cited as frozen or merged evidence — then the combine → SAFETY-FAIL. Evidence FROZEN + MERGED via PR #57 @ `cccfb30` (freeze `48558aa`; closed 370-file inventory incl. 360 normalized hero logs with raw+normalized SHA-256). The near-duplicate disjointness review is ACCEPTED + MERGED via PR #56 @ `7412f27` (owner sign-off 2026-07-23; adjacent caveat: two holdout teams, positional aliases H4/H5, are species-identical → ~5 effective archetypes not 6, that archetype holding 60 of 180 schedule keys). The ledger's one-attempt budget for `config_hash 594295543f13a55d` is CONSUMED with `justification: null`, so the next attempt needs either a documented justified repeat or a new independent holdout — DECISION NOT YET MADE. Paired numbers (`n_total` 180, `n_discordant` 100, `delta` +0.044444, head-to-head 89 vs 81, `exact_p: null`) are DESCRIPTIVE ONLY and are NOT a strength claim. The trapped-switch defect is now FIXED and merged (PR #60 @ `7dafde8` production+tests, PR #61 @ `a9475e5` pin anchor): ActiveSlot gained `maybe_trapped` (alias `maybeTrapped`) -- the field the server sends and pydantic was silently dropping -- and `_voluntary_switches` returns [] when either `trapped` or `maybe_trapped` is truthy, while the FORCED replacement path stays untouched (still legal while trapped, pinned by regression tests). The new field carries `exclude_if` so it is omitted when absent: without it, `model_dump(exclude_none=False)` -- which decision_profile HASHES -- moved the pinned C3-proof fixture_input_hash 3d246b21910204ec -> 1a15d8ded702c464; that was fixed at source, NOT by re-pinning the proof. Two fail-closed guards were added: a schema-coverage test for request slot fields that are neither modelled nor allowlisted-with-reason, and an anchor binding that hand-transcribed set to `showdown_commit` in config/eval/provenance.yaml. No gate run, no evidence freeze, no ledger change, no strength claim; the fix yields a NEW git_sha hence a NEW candidate identity and does NOT authorize a Gate B rerun. Next, separately authorized and NOT started: the ledger re-run decision (now the gating item); runtime detection of unmodelled request keys for a server no pin governs (NOT via extra="allow", which would re-break the serialization hashes); the un-pinned Node version; and the local suite's pre-existing 115 failures / 21 errors from missing `npm ci --prefix tools/calc` in fresh worktrees. Champions Strength remains NO-GO. Prior state, now SUPERSEDED (PR #52 @ `7a9685c`): Gate B IMPLEMENTED and MERGED — code + sealed teams + docs ONLY, NO I8-D/coverage/Strength run. Prior 2026-07-21 state:** **I8-A–C offline latency machinery MERGED via PR #20 @ `32cdd4e`; the reproducible I8 microprofile driver MERGED via PR #21 @ `0730a18`; the authorized 450-row microprofile then RAN CLEAN on the fixed Windows host and is FROZEN (`data/eval/champions-panel-v0/i8-microprofile/`, `reports/champions-panel-v0-i8-microprofile.md`; git_sha `0730a18`, manifest hash `fdc3706038fde45f`; 20/20 independent validation gates, 450/450 outcome=ok, 0 contaminated/retries/crashes) — cost-mechanism localization ONLY, NOT a live latency-gate result and NO Strength claim, and the pinned 1000 ms LIVE budget is not a per-arm microprofile threshold; `reps`=30, D-2=`MAX_BATTLES`200/`MAX_SCORED_DECISIONS`2000 and the fixed Windows measurement host are CLOSED; the D0 + Kaggle D0-K timing calibrations remain cost-data-only/scratch; the I8-D live-latency HARNESS (telemetry → live-dataset validator → exposure/cap runner + three-way verdict → provenance-locked `i8d-live-gate` CLI) is now MERGED via PR #23 @ `3b6070c` (two blocking review rounds resolved, final review PASS; full suite 2777 passed / 2 skipped / 1 xfailed; code + tests ONLY — NO server, battle, live-latency run, or evidence executed); the live-gate RUN then EXECUTED once on the corrected harness (git_sha `9fc0f36`, after the team-path fix) and returned **FAIL** — active foe-Mega decision p95 `1110.213 ms` > `1000 ms` budget, exposure floor met (60 active-valid decisions from 45 distinct battles), `stop_reason=exposure_floor_met`, 75 battles / 679 decisions, atomically published and FROZEN (`data/eval/champions-panel-v0/i8d-live/`, `reports/champions-panel-v0-i8d-live.md`); this is a **load-bearing latency FAIL** (the 1000 ms budget is NOT moved post-hoc); the **latency-reduction slice (Lever A) is MERGED via PR #30 @ `6b2f955`** — a behavior-neutral fold of the game-mode incoming (`ko_threat`) classification into the decision's single shared `DamageOracle` scoring flush (removing the per-decision classification Node spawns), plus hardened counterproofs; full suite **2799 passed / 1 skipped / 1 xfailed** (skip/xfail set unchanged); cost contract **≥ 1 spawn removed per decision, board-/cache-dependent**. The **UNCHANGED post-Lever-A I8-D live-gate rerun then RAN once on `9d915f2` and returned FAIL** — active foe-Mega decision p95 `1160.515 ms` > `1000 ms`, exposure floor met (60 active-valid from 45 distinct battles), `stop_reason=exposure_floor_met`, 75 battles / 679 decisions, evidence frozen LOCALLY at commit `1262e36` under `data/eval/champions-panel-v0/i8d-live-post-lever-a/` + verdict report `fe05054` (`reports/champions-panel-v0-i8d-live-post-lever-a.md`); the `968.513 ms` model projection **did NOT materialize empirically** (observed p95 1160.515 ms), and the **+50.302 ms** vs the pre-Lever-A FAIL is **descriptive only — no causal Lever-A latency effect is derivable** (a single `oneshot` run carries run-to-run variance); so the evidence/docs PR is now MERGED (PR #32 @ `34b088e`), and the follow-on **offline latency diagnosis + Lever B (B2) design + implementation are MERGED via PR #33 @ `b192825`** (a behavior-neutral, gated, best-effort decision-start `mixed_batch` pre-pass coalescing the early world-invariant board stats+types and warming the speed + dex caches; golden decision-equivalence byte-identical; full suite 2835 passed / 1 skipped / 1 xfailed; CI 8/8; it engages on the gauntlet live path) — but the **UNCHANGED I8-D live-gate rerun then RAN once on `3db4ac7` and returned a valid PASS** (active foe-Mega p95 850.245 ms ≤ 1000 ms; exposure floor met 60/44; 72 battles/651 decisions; stop=exposure_floor_met; seed_log_verified; evidence `4b4be54`, report `062b6d0`); the drop vs the FAILs is descriptive only (no causal Lever-B or run-to-run-variance claim); the **1000 ms latency blocker is now CLOSED for this run**; the Lever-B PASS evidence is FROZEN + MERGED (PR #35 @ `6de0578`) and the docs-project-organization migration is MERGED (PR #36 @ `9c780a2`); the opponent-Mega coverage-gate design + implementation (Plan A) is now MERGED via PR #37 @ `10f9adf` (code + tests only, no run — two ultrareview rounds resolved, 6 P1s + 2 follow-ups); because it touches the LIVE decision-profile v3 write path, the prior I8-D PASS does not carry over; the UNCHANGED I8-D latency rerun then RAN once on `bd590c1` and returned a valid **PASS** — active foe-Mega p95 **864.94 ms ≤ 1000 ms**, exposure floor met (60 active-valid from 45 distinct battles; 75 battles/679 decisions; `stop_reason=exposure_floor_met`; `seed_log_verified`), evidence MERGED via PR #39 @ `cbaa4b9` (`data/eval/champions-panel-v0/i8d-live-post-coverage-harness/` + verdict report `f0d42dd`); kept strictly separate from every prior I8-D run (comparisons descriptive only — no causal or variance claim); the **latency precondition for candidate `bd590c1` is CLOSED** (candidate-identity gap: this does NOT close it for `cbaa4b9` — see below). The separately-authorized `champions-coverage-gate` then ran exactly once on the new merge SHA `cbaa4b9` (after one technical-abort first attempt — no battle, no verdict, excluded from the verdict population) and returned **FAIL**, `stop_reason=schedule_exhausted`: 200 battles / 1956 decisions, 0 safety violations; `slot0` 82/50, `slot1` 298/173, `order_tie` 100/100 all cleared their floor; **`both_foe_slots` 0/0 did not meet its 15/6 floor**; evidence frozen LOCALLY (not yet merged) at `4109abd` + verdict report `e08412e`. **Champions Strength remains NO-GO** — the coverage-gate FAIL (`both_foe_slots` zero-exposure) is now historical — **diagnosed and remediated, MERGED via PR #42 @ `f2bb818`** (2026-07-21; safety/provenance/defect-fix only, no live gate ran); Strength remains NO-GO pending a separately-authorized I8-D rerun on the fresh candidate identity for `f2bb818` and, only if that PASSes, a separately-authorized coverage-gate rerun with the repaired team; Kaggle is reserved for later coverage/outcome/Strength as its own hardware stratum, never pooled.** **I7a own-Mega SAFETY PASS, merged to `main` @ `1053cf1`**; **I7b-A MERGED via PR #12 @ `cdc55c2`**; **I7b-B Tasks 1-6 REVIEW-PASS · MERGED via PR #13 @ `755b144`** — full suite **2169 passed, 2 skipped, 1 xfailed**, no new skip/xfail vs the 2132/2/1 pre-slice baseline; foe-Mega response modeling is now LIVE for `format_config.mega` formats and byte-identical for Reg-I/`format_config=None`; **I7b-C PRE-SMOKE REVIEW-PASS + 2-battle opponent-Mega SAFETY SMOKE PASS · NARROW EXPOSURE** (`reports/champions-panel-v0-i7b-mega-smoke.md`; git_sha `3d23e654a29689b68f3c936653726d6a36a6934d`; 19/19 standard gates PASS, worst p95 672 ms; only **1 of 17** scored decisions ever exposed a foe-Mega hypothesis and only **slot 1** — slot 0, dual-Mega and activation ordering were never exercised live, so this is evidence the mechanism works, not that opponent Mega is broadly validated) — safety/telemetry evidence only, **no Strength and no latency claim**; **Champions Strength still NO-GO** — the I8-D latency precondition for candidate `bd590c1` is CLOSED; the load-bearing blockers are now the coverage-gate FAIL (`both_foe_slots` zero-exposure, `cbaa4b9`) and the unestablished latency precondition for that same candidate `cbaa4b9` (candidate-identity gap — the `bd590c1` PASS, identity `b3c2e0521505932d`, does not transfer to `cbaa4b9`, identity `93cd419222683f75`, per the APPROVED spec's shared-candidate-identity requirement), followed by the independent Strength-holdout design; I7 Mega design spec rev. 10 **APPROVED**, implementation plan at **Rev. 9**; protocol differential audit @ `fc4f251`; I6 live-damage gen-0 PASS @ `3bcd4b3`; HP-suffix revalidation PASS @ `62117b5`; prior I5 mixed verdict @ `4da007b` retained for latency baseline; **the `both_foe_slots` zero-exposure is now DIAGNOSED + REMEDIATED (T1 team redesign, T2 shared `candidate_identity`, T3 same-candidate I8-D-PASS gate, four independent review rounds hardening the I8-D-verdict guard to the full real 25-field schema + cross-field consistency + NaN/negative rejection) and MERGED via PR #42 @ `f2bb818`** (full suite 2971 passed / 18 pre-existing unrelated failed / 1 skipped / 1 xfailed) — **safety/provenance/defect-fix only, no live gate ran**; next = a separately-authorized I8-D latency rerun on the fresh candidate identity for `f2bb818` (new git_sha, does not inherit `bd590c1`/`cbaa4b9`), then — only if PASS — a separately-authorized coverage-gate rerun with the repaired team; **Champions Strength remains NO-GO**), against an external strategic review (adopted with two
corrections, see "Corrections to the external review" below) and this session's own verified
state (depth-2 slice, value-calibration spec).

**Post-merge reconciliation:** PR #17 is merged to `main` @ `8942232`. I7b-C is closed as
safety/telemetry work. The immediate blocker is the dedicated Champions latency profile;
even after a latency PASS, a separate broader opponent-Mega coverage gate and independent
Strength holdout must be approved before a Strength run.

**Post-merge reconciliation (2026-07-23, PR #57 @ `cccfb30` — Gate B RAN: SAFETY-FAIL, evidence frozen).**
Gate B is **no longer un-run**. The first end-to-end-valid independent Strength-holdout combine
EXECUTED on candidate `bc2d6df`, candidate identity `32f79b8e52444aa3` (hero `heuristic`, baseline
`max_damage`), and returned **SAFETY-FAIL**. Two harness defects that only the live runs surfaced
landed first, each via strict TDD and its own PR: **PR #54 @ `a7d5330`** (a Windows-retry-safe atomic
directory publish, used by both the arm and the combine publish — the first Arm A attempt aborted at
final publish with WinError 5) and **PR #55 @ `bc2d6df`** (the combine now derives the upstream
`teams_root` as `Path(repo_root)/"showdown_bot"` instead of passing Gate B's own `teams_root="."` to
the I8-D/coverage verdict verifiers). Neither is a strength change.
**All three gates ran on the SAME candidate identity, with no commits between them** (spec §5
satisfied): **(1)** I8-D latency **PASS** — active foe-Mega decision p95 **873.762 ms ≤ 1000 ms**,
exposure floor met, `p95_is_gate_value=true`; **(2)** opponent-Mega coverage **PASS** — 0 safety
violations, `stop_reason=coverage_floor_met`; **(3)** the Gate B combine → **SAFETY-FAIL**.
**Non-claim, stated explicitly:** the latency and coverage evidence for this sequence is **EXTERNAL
and UNFROZEN** (local run directories, never committed) — it must **not** be cited as frozen or
merged evidence.
**Cause of the SAFETY-FAIL:** `invalid_choices` — Arm A (heuristic, the candidate) = **1**, Arm B
(max_damage, baseline) = **0**. The candidate emitted **one illegal action** across the 180 held-out
matchups (server: `Can't switch: The active Pokémon is trapped`), located as battle
`9ccc312c51d95bfe`. Gate B's safety gate is **fail-closed**: any illegal candidate action fails the
run regardless of win margin. **Root cause is PLAUSIBLE, not CONFIRMED:** at that decision the server
reported one active slot `trapped:true` and the other `maybeTrapped:true`, and the re-request
upgraded the latter to `trapped:true`, so the bot most likely attempted to switch the
**`maybeTrapped`** slot. Which slot it actually chose **cannot be settled from the frozen server
room-log** — that needs the bot's own `/choose` string or the DecisionTrace, neither of which is in
the frozen evidence. The simpler "ignored an explicit `trapped` flag" reading is **not** asserted.
**Descriptive-only paired numbers — NOT a strength claim, and no strength readout may be derived
from them:** `n_total` **180**, `n_discordant` **100**, `delta` **+0.044444** (= 8/180), raw
head-to-head heuristic **89** / max_damage **81**, `exact_p: null`. The run is a SAFETY-FAIL and
carries no strength meaning.
**Evidence FROZEN + MERGED** via **PR #57 @ `cccfb30`** (freeze commit `48558aa`) under
`data/eval/champions-panel-v0/strength-holdout-v0/windows/gate-b-safety-fail-bc2d6df/`: a closed
370-file inventory — both arms' `arm_manifest.json`/`rows.jsonl`/`seeds.jsonl`, the combine bundle
(`verdict.json`, `cells.json`), and 360 normalized hero logs each carrying raw + normalized SHA-256,
plus `inventory.json` and `REPORT.md`. Independently re-verified from the committed bytes before merge.
**Ledger:** the one-attempt budget for `config_hash 594295543f13a55d` is now **CONSUMED** on `main`
with `justification: null`. A repeat on this `config_hash` is **not auto-allowed**; the next Strength
attempt requires either a documented **justified repeat** (a non-null `justification` resets the
budget by design — precedent: the ledger's own `baseline-heldout-v1` line) or a **new independent
holdout**. **That decision is not yet made.**
**Near-duplicate disjointness review ACCEPTED** — merged **PR #56 @ `7412f27`**, owner sign-off
2026-07-23. The spec §3.3 species-overlap flags (three holdout teams at Jaccard 0.5 against two
**engineered coverage** teams; **zero** dev-panel overlap; the hard content-hash firewall passes) are
resolved via documented manual review. Recorded adjacent caveat: two holdout teams (positional
aliases **H4**/**H5**) are species-identical, so effective **archetype** diversity is **~5, not 6**,
and that archetype holds **60 of the 180** schedule keys (1/3) — double-weighted in any future
McNemar verdict. (Holdout teams are referenced here by positional alias `H1`…`H6` = manifest
`selection_index`; the sealed IDs and content hashes live only in the holdout manifest.)
**Champions Strength remains NO-GO.**

**Post-merge reconciliation (2026-07-23, PR #60 @ `7dafde8` + PR #61 @ `a9475e5` — the
trapped-switch defect is FIXED).** Item **(a)** above is **DONE**; item **(b)**, the ledger re-run
decision, is **still open and is now the gating item**.

**The fix (B1).** `ActiveSlot` gained `maybe_trapped` (alias `maybeTrapped`) — the field the server
actually sends and that pydantic was **silently dropping**, since `extra="forbid"` is deliberately
not used (an unknown future server field must not crash the bot mid-battle). `_voluntary_switches`
now returns `[]` when **either** `trapped` or `maybe_trapped` is truthy. The **forced** path is
deliberately untouched: a forced replacement after a faint stays legal while trapped, pinned by two
regression tests. 14 tests accompany the change; the 11 behavioural ones were written and observed
failing before the production change.

**A real regression, caught by the suite and fixed at source (provenance lesson).** The new field
would have emitted `"maybeTrapped": null` on **every** board through
`model_dump(..., exclude_none=False)`, which `eval/decision_profile.py` **hashes** — it moved the
pinned C3-proof `fixture_input_hash` from `3d246b21910204ec` to `1a15d8ded702c464`. It was fixed
with `exclude_if` (the same device `can_mega_evo` already uses), **not** by re-pinning the proof
hashes to match the new code. Boards without the flag now serialize byte-identically to before.

**Root-cause guards (both fail closed).** A schema-coverage test fails when the pinned sim can emit
a request slot field that is neither modelled on `ActiveSlot` nor explicitly allowlisted with a
stated reason; and an anchor test binds that hand-transcribed field set to `showdown_commit` in
`config/eval/provenance.yaml`, so a sim-pin bump fails loudly instead of letting the set go stale.

**Non-claims.** No gate run, no evidence freeze, no ledger change, no strength claim. The fix
produces a **new `git_sha` ⇒ a new candidate identity**; it does **not** authorize a Gate B rerun.
Any future attempt still needs the full three-gate sequence (I8-D → coverage → combine) on one fresh
identity with **no commits between**, **and** the ledger decision. **Champions Strength remains
NO-GO.**

**Still open, none started:** the **ledger re-run decision** (the gating item — documented justified
repeat vs. a new independent holdout); runtime detection of unmodelled request keys for a server no
pin governs, e.g. the live ladder — explicitly **not** via `extra="allow"`, which would re-break the
serialization hashes above; the un-pinned Node version (P0-4); and the local suite's pre-existing
115 failures / 21 errors from missing `npm ci --prefix tools/calc` in fresh worktrees.

**Post-merge reconciliation (2026-07-23, PR #52 @ `7a9685c` — Champions Gate B implemented).**
The **independent Strength holdout** is no longer just a future design — it is now **IMPLEMENTED and
MERGED** (PR #52). Delivered (Tasks 1–13, APPROVED spec `2026-07-20-champions-coverage-strength-holdout-design.md`
+ Amendment A1; plan `2026-07-21-gate-b-independent-strength-holdout.md` Rev. 25): the 180 battle-key
schedule (6 teams × 2 policies × 15 seeds, `panel_hash` bound into `schedule_hash`); **six sealed,
blind-curated, `validate-team`-legal `gen9championsvgc2026regma` holdout teams** (published PJCS-2026
teams, opaque `gbh_*` IDs whose public→internal mapping lives only in the holdout manifest, Amendment
A1.1); the strength-holdout panel + the **additive** closed-schema Gate B static baseline (the generic
T6 contract is byte-identical to before — Gate B added functions only, A1.3); the repo-wide leakage
scan, coverage-disjointness, species near-duplicate audit, strata guard, ledger, and McNemar verdict
pipeline; and the `champions-strength-holdout-arm` / `-combine` CLIs (source real manifest/panel data,
enforce the frozen identity + baseline before battle 1 / before any verdict). Full offline suite green
at merge (**3582 passed / 3 skipped / 1 xfailed**); multiple static + full-suite code-review rounds
resolved to PASS; the baseline manifest is a single immutable commit (an owner-authorized history
rewrite; pre→post SHA map in
`docs/projects/champions/audits/2026-07-23-gate-b-baseline-immutability-rewrite-sha-map.md`).
**At that merge this was code + sealed teams + docs ONLY: no I8-D, coverage, or Strength run had been
taken, no evidence was frozen, and no Strength claim was made.** That "no run" state is **SUPERSEDED**
— the live sequence has since executed and returned SAFETY-FAIL; see the PR #57 @ `cccfb30`
reconciliation block above. The sequencing contract itself is unchanged and still governs every
future attempt: separately authorized, in order, on **one and the same candidate identity**:
**(1)** I8-D latency rerun → must PASS; **(2)** only then a coverage-gate rerun on that identity →
must PASS; **(3)** only then the independent Gate B Strength-holdout run. **No commits may land
between those three gates** (a new `git_sha` would break the shared-candidate-identity requirement,
spec §5). **Champions Strength remains NO-GO.**

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
a **load-bearing latency FAIL** — the 1000 ms budget is **not** moved. The
**latency-reduction slice (Lever A) is MERGED via PR #30 @ `6b2f955`** — a behavior-neutral fold of the
game-mode incoming (`ko_threat`) classification into the decision's single shared `DamageOracle` scoring
flush, plus hardened counterproofs (full suite 2799 passed / 1 skipped / 1 xfailed). The **UNCHANGED
post-Lever-A I8-D live-gate rerun then RAN once on `9d915f2` and returned FAIL** — active foe-Mega p95
`1160.515 ms` > `1000 ms`, exposure floor met (60 active-valid from 45 distinct battles),
`stop_reason=exposure_floor_met`, 75 battles / 679 decisions; evidence frozen LOCALLY at `1262e36` under
`data/eval/champions-panel-v0/i8d-live-post-lever-a/` + verdict report `fe05054`
(`reports/champions-panel-v0-i8d-live-post-lever-a.md`). The `968.513 ms` model projection **did not
materialize empirically**; the **+50.302 ms** vs the pre-Lever-A FAIL is **descriptive only — no causal
Lever-A latency effect is derivable** (a single `oneshot` run carries run-to-run variance). That
evidence/docs PR is now MERGED (PR #32 @ `34b088e`), and the follow-on **offline latency diagnosis +
Lever B (B2) design + implementation are MERGED via PR #33 @ `b192825`** — a behavior-neutral, gated,
best-effort decision-start `mixed_batch` pre-pass that coalesces the early world-invariant board
stats+types and warms the speed + dex caches (golden decision-equivalence byte-identical; full suite
**2835 passed / 1 skipped / 1 xfailed**; CI 8/8; it engages on the gauntlet live path). The **UNCHANGED
I8-D live-gate rerun then RAN once on `3db4ac7` and returned a valid PASS** — active foe-Mega p95
**850.245 ms ≤ 1000 ms**, exposure floor met (60 active-valid from 44 distinct battles; 72 battles /
651 decisions; `stop_reason=exposure_floor_met`; `seed_log_verified`), evidence frozen `4b4be54` +
report `062b6d0`. The drop vs the FAILs is **descriptive only** (no causal Lever-B latency claim and no
run-to-run-variance claim — a single `oneshot` run). **The 1000 ms latency blocker is now CLOSED for
this run**; the PASS evidence is FROZEN + MERGED (PR #35 @ `6de0578`) and the docs-project-organization
migration is MERGED (PR #36 @ `9c780a2`). **The opponent-Mega coverage-gate design + implementation
(Plan A) is now MERGED via PR #37 @ `10f9adf`** — a fixed 200-battle cyclic schedule over four
target cells (`slot0`, `slot1`, `both_foe_slots`, `order_tie`), live-only decision-profile v3
telemetry filled at origin, a per-cell floor/cap three-way verdict, and a provenance-locked,
hero-specific-safety-seamed `champions-coverage-gate` runner + CLI, hardened across two ultrareview
rounds (6 confirmed P1s plus 2 follow-up findings, all independently reproduced and fixed with
RED→GREEN TDD before merge). **Code + tests only — no server, battle, or coverage-gate run
executed.** Because the v3 schema change touches the **live** decision-profile write path (every
live decision now also stamps `foe_mega_slots`/`foe_mega_order_tie`), the prior I8-D PASS
(`3db4ac7`, active foe-Mega p95 850.245 ms) does **not** carry over to this merge SHA — it measured
different code. A fresh worktree preflight (clean tree at `bd590c1`; patched server `f8ac140`
compiled but not started; port 8000 free; calc dependencies installed; `oneshot` backend with
`SHOWDOWN_CALC_BACKEND`/`SHOWDOWN_GAUNTLET_BATTLE_TIMEOUT_S` explicitly unset; seed namespace,
`schedule_hash`/`panel_hash` byte-identical to every prior run; `config_hash` freshly derived as
`594295543f13a55d`, matching the last known-good PASS; the v3 write path offline-verified to
validate cleanly and correctly populate the exposure-floor/p95 population) preceded the run — two
geometry mistakes caught and fixed before any live action: the gate must run from the worktree
ROOT with `--teams-root showdown_bot` (not from the `showdown_bot/` subdirectory), and the
external output container must be created before the server starts (so it can safely write
`seeds.jsonl`) while `seeds.jsonl`/`out`/`out.staging` themselves stay absent until the run.
**The UNCHANGED I8-D live-gate rerun then RAN once on `bd590c1` and returned a valid PASS** —
active foe-Mega p95 **864.94 ms ≤ 1000 ms**, exposure floor met (60 active-valid decisions from
45 distinct battles; 75 battles/679 decisions; `stop_reason=exposure_floor_met`;
`seed_log_verified`); all rows carry `schema_version=decision-profile-v3` (the live write path
now stamps this unconditionally, for coverage-gate and I8-D alike — offline-verified before the
run to validate cleanly and not affect the verdict population, which is schema-version-agnostic
by construction). Evidence is **MERGED via PR #39 @ `cbaa4b9`** (originally frozen at `1166627`) under
`data/eval/champions-panel-v0/i8d-live-post-coverage-harness/` + verdict report `f0d42dd`
(`reports/champions-panel-v0-i8d-live-post-coverage-harness.md`), kept strictly separate from
every prior I8-D run (pre-Lever-A FAIL, post-Lever-A FAIL, post-Lever-B PASS) — never pooled; all
comparisons are explicitly descriptive only, no causal or run-to-run-variance claim. **The
latency precondition for candidate `bd590c1` is CLOSED** — candidate-identity gap: this does
**NOT** close it for `cbaa4b9` (see below). The separately-authorized
`champions-coverage-gate` then ran exactly once on the new merge SHA `cbaa4b9` (after one
technical-abort first attempt — no battle, no verdict, excluded from the verdict population) and
returned **FAIL**, `stop_reason=schedule_exhausted`: 200 battles / 1956 decisions, 0 safety
violations; `slot0`/`slot1`/`order_tie` all cleared their floor; **`both_foe_slots` scored 0
decisions from 0 distinct battles against its 15/6 floor** — the verdict driver. **The
zero-exposure root cause is now diagnosed and fixed**: the real preview picker never led with
BOTH Mega holders (Aerodactyl + Meganium), so `both_foe_slots` was structurally unreachable
regardless of schedule/threshold — diagnosis APPROVED @ `a55ab4d`, remediation plan APPROVED @
`78a2274`. Evidence for the FAIL run itself is frozen **LOCALLY** (not yet merged) at `4109abd` +
verdict report `e08412e` (`reports/champions-panel-v0-coverage-v0.md`). The remediation — **T1**
(redesign `cov_foe_both` so the real picker leads with both Mega holders), **T2** (shared
`candidate_identity` provenance helper, now also carried by the I8-D verdict), **T3** (the
coverage gate fails closed unless the SAME I8-D candidate PASSed) — plus **four independent
code-review rounds** progressively hardening the I8-D-verdict-artifact guard (unbound fields →
`calc_backend`/dict-type safety → raw `git_sha`/`config_hash`/`hero_agent`/`schedule_hash`/
`p95_is_gate_value` bindings → the full real 25-field schema, presence + value-checked →
dynamic-counter cross-field consistency + NaN/negative/±∞ `p95_ms` rejection; final re-review
PASS, no remaining findings) — is now **MERGED via PR #42 @ `f2bb818`** (full suite **2971
passed / 18 pre-existing unrelated failed / 1 skipped / 1 xfailed**, zero new failures across the
whole branch). **This PR is safety/provenance/defect-fix work only — no live gate ran, no
Strength claim.** Because `f2bb818` is a new `git_sha`, it carries a **new** `candidate_identity`
— the `bd590c1`/`cbaa4b9` identities do not transfer, per the same identity-gap pattern as every
prior merge. Next = a separately-authorized I8-D latency rerun on this fresh candidate identity,
then — **only if that PASSes** — a separately-authorized `champions-coverage-gate` rerun with the
repaired `both_foe_slots` team, to test whether the fix actually restores exposure (this IS the
fix, not an identical rerun; no post-hoc threshold/schedule change); each verdict still gets
byte-frozen evidence, a report, and a ROADMAP/PROJECT_INDEX reconciliation merged via its own
review PR. The independent Strength-holdout (six new blind-curated teams, leakage protection, paired
holdout) is **no longer future work, and no longer un-run — it was BUILT and MERGED (PR #52 @
`7a9685c`) and has since RUN once, returning SAFETY-FAIL on candidate `bc2d6df` (evidence FROZEN +
MERGED, PR #57 @ `cccfb30`; see the reconciliation block above)**. **Champions Strength remains
NO-GO** — but the load-bearing blocker is no longer the candidate's illegal action: the
trapped-switch defect is **FIXED and merged** (PR #60 @ `7dafde8`, anchor PR #61 @ `a9475e5`). What
remains is the **ledger decision** (justified repeat vs. new independent holdout), separately
authorized and not started, and then the full three-gate sequence again on one fresh candidate
identity with no commits between.

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
| Value calibration study | **Spec Revision 2 committed** (T3A arm, disjoint verdict, outcome-encoding, sklearn dep, fold-local categorical encoding all addressed) | `docs/projects/learning/specs/2026-07-12-value-calibration-design.md` Rev 2, commit `8e4c47f` | implementation plan once Rev 2 explicitly signed off |
| Outcome-join (04) | **Built** | merged `725257e`/`fea284b`; 299-game reference smoke | consumed by value-calibration study |
| Teacher-disagreement atlas | **Built** | `5830e9e` | diagnostic only — not a strength gate |
| Diagnostics-v0 | **Built** | `849b5c7` | diagnostic only — not a strength gate |
| Belief (item/spread/move priors) | **Not started** | — | P2, after the panel + data-identity fix |
| Value-head (trained model) | **Not started, gated** | — | only after value-calibration says GO |
| PPO/full self-play RL | **Not started, deliberately deferred** | ps-ppo-reference eval | P5, after search/belief/value-labels stabilize |
| Accuracy / hit-probability evaluation | **Default-on safety-clean; strength UNDERPOWERED (unfavorable direction, no claim)** | Gate-B cap=6 PASS 6/944=0.64%; default-on live dev-strength A/B @ `a956b6b` (`reports/2026-07-14-accuracy-default-on-devstrength-verdict.md`: SAFETY-PASS, n_discordant=6, 0 A-only / 6 B-only discordants — follow-up risk signal, not regression proven) | `SHOWDOWN_ACCURACY_MODE` **default-on** when unset; cap **6**; explicit opt-out unchanged; **no GO on strength** — next step user-gated (larger strength run vs Champions-readiness) |
| Champions panel v0 (format target) | **I6 PASS · I7a own-Mega SAFETY PASS (merged) · I7b-A MERGED · I7b-B REVIEW-PASS/MERGED (PR #13 @ `755b144`) · I7b-C PRE-SMOKE REVIEW-PASS + opponent-Mega SAFETY SMOKE PASS (narrow exposure), merged via PR #17 @ `8942232` · I8-A–C offline latency machinery MERGED (PR #20 @ `32cdd4e`, offline-only) · D0 + Kaggle D0-K cost calibration DONE (scratch, no verdict) · reps=30, D-2=200/2000, host=fixed-Windows CLOSED · I8 microprofile driver MERGED (PR #21 @ `0730a18`) · 450-row microprofile RAN CLEAN & FROZEN (cost-mechanism only; 20/20 gates, 450/450 ok; no live-latency/Strength verdict) · I8-D live-latency harness MERGED (PR #23 @ `3b6070c`, code+tests only, 2 blocking review rounds resolved / final PASS, 2777 passed) · team-path wiring fix merged (PR #26 @ `9fc0f36`) · live-gate RUN EXECUTED once on the corrected harness → **FAIL** (active foe-Mega p95 1110.213 ms > 1000 ms; exposure floor met 60/45; `stop_reason=exposure_floor_met`; 75 battles/679 decisions; FROZEN `data/eval/champions-panel-v0/i8d-live/` + `reports/champions-panel-v0-i8d-live.md`) · latency = load-bearing blocker; latency-reduction slice (Lever A) MERGED via PR #30 @ `6b2f955`; the UNCHANGED post-Lever-A I8-D live-gate rerun RAN once on `9d915f2` → **FAIL** (active foe-Mega p95 1160.515 ms > 1000 ms; exposure floor met 60/45; 75 battles/679 decisions; evidence frozen locally `1262e36` + report `fe05054`; 968.513 ms projection NOT materialized; +50.302 ms vs pre-Lever-A FAIL descriptive only, no causal Lever-A effect); evidence/docs PR MERGED (PR #32 @ `34b088e`); offline latency diagnosis + Lever B (B2) design + impl MERGED via PR #33 @ `b192825` (behavior-neutral decision-start `mixed_batch` pre-pass, golden byte-identical, full suite 2835/1/1, CI 8/8, engages on the live path); the UNCHANGED I8-D live-gate rerun then RAN once on `3db4ac7` → valid **PASS** (active foe-Mega p95 850.245 ms ≤ 1000 ms; exposure floor met 60/44; 72 battles/651 decisions; stop=exposure_floor_met; seed_log_verified; evidence `4b4be54`, report `062b6d0`); drop vs the FAILs descriptive only (no causal Lever-B or variance claim); **latency blocker CLOSED**; the coverage-gate design + implementation (Plan A) is MERGED via PR #37 @ `10f9adf` (code + tests only, no run); the UNCHANGED I8-D rerun then RAN once on `bd590c1` → **PASS** (p95 864.94 ms ≤ 1000 ms; 60/45; 75 battles/679 decisions; exposure_floor_met; evidence + report MERGED via PR #39 @ `cbaa4b9`); latency precondition for `bd590c1` CLOSED (NOT `cbaa4b9` — identity gap, no transfer); the coverage gate then ran once on `cbaa4b9` (after one technical-abort attempt, excluded from the verdict population) → **FAIL** (`schedule_exhausted`; 200 battles/1956 decisions; safety violations 0; `slot0`/`slot1`/`order_tie` floors met; `both_foe_slots` 0/0 floor NOT met; evidence frozen locally `4109abd` + report `e08412e`); next = review+merge this evidence/docs, then a separately-authorized diagnosis/design slice for the zero-exposure — now **DIAGNOSED + REMEDIATED** (T1 `cov_foe_both` team redesign, T2 shared `candidate_identity`, T3 same-candidate I8-D-PASS gate, 4 independent review rounds hardening the I8-D-verdict guard to the full real 25-field schema) and **MERGED via PR #42 @ `f2bb818`** (full suite 2971 passed/18 pre-existing unrelated failed/1/1) — safety/provenance/defect-fix only, no live gate ran; next = a separately-authorized I8-D rerun on the fresh candidate identity for `f2bb818`, then (only if PASS) a separately-authorized coverage-gate rerun with the repaired team · Strength NO-GO — pending both gates on the new candidate** | P0–P4 on main; I4 calc pin + speed gen-0 merged `f192aff`; I5 @ `4da007b`: **5/94** random-legal degradation, worst p95 **3235 ms** (also contained state-degradation; no causal p95 link); HP fix merged `62117b5`; revalidation @ `62117b5` (`suffix-evidence.json`): **0/99** degraded; this-run p95 **429 ms** (observational only); **I6 @ `3bcd4b3`**: gen-0 damage wired through heuristic/`max_damage`/export; 2-battle smoke **SAFETY-PASS**, worst p95 **331 ms** (`reports/champions-panel-v0-i6-smoke.md`); **protocol differential audit @ `fc4f251`**: `reports/champions-pkmn-protocol-differential-audit.md`; **I7 Mega design spec rev. 10 APPROVED** (`docs/projects/champions/specs/2026-07-14-champions-mega-i7-design.md`); **I7a-A/I7a-B/I7a-C merged to `main`** (candidate identity/trace-v3/own-Mega safety smoke, config_hash `e137fce925f25bd8`, git_sha `5690de75a4f7bc627b8d4be4fddb2074c6b586fc`, worst p95 **588 ms**); **I7b-A merged via PR #12 @ `cdc55c2`** (limited-view eligibility, response identities, fail-closed click-rate parsing, coverage-preserving cap/truncation; focused gate **106 passed**; full suite **2132 passed, 2 skipped, 1 xfailed**); **I7b-B Tasks 1-6 merged via PR #13 @ `755b144`** (Codex verdict: PASS, no merge blockers) — `mega_activation_order_key`; side-aware `project_mega` + fail-closed `MegaProjectionSpeciesMismatchError`; `compose_mega_projection_branches` (unequal speed → 1 branch @ 1.0, exact tie → 2 @ 0.5, no RNG, never mutates input); three-phase scoring integration (build+enqueue → **one shared oracle flush per world** → evaluate at `world_weight × response_weight × branch_weight`); the `decision.py::_choose_best_mega` caller gate (`foe_mega_eligibility()` called ONLY when `format_config is not None and format_config.mega` — it has no `format_config` parameter of its own, and `opp_mega_click_rate()` defaults to `0.35` when unset, so this gate is the entire Reg-I guarantee); and per-diagnostic-index depth-2 context binding with **zero `search.py` changes**. **A P1 caught in review and fixed before merge:** `aggregate_scores`' `MUST_REACT` operator takes `min(scores)` WITHOUT weights, so a weight-0 sample cannot move the weighted mean but DOES move the aggregate (`[10]` w=`[1]` → `10.0` vs `[10,-100]` w=`[1,0]` → `-56.0` at λ=0.6) — zero-weight responses are now excluded from enqueue/evaluation/`score_vector` on the active path, and zero-weight Mega classes compose no branches at all (`NEUTRAL`/`AHEAD` were unaffected). Full suite **2169 passed, 2 skipped, 1 xfailed** (no new skip/xfail); `battle/baselines.py` and `battle/search.py` byte-identical across the whole slice; foe-Mega modeling LIVE for `format_config.mega`, byte-identical for Reg-I/`None`. **I7b-C PRE-SMOKE REVIEW-PASS + LIVE SMOKE PASS · NARROW EXPOSURE** (`docs/projects/champions/audits/2026-07-16-champions-opponent-mega-i7b-audit.md`, `docs/projects/champions/plans/2026-07-16-champions-opponent-mega-i7b.md` Rev. 9; verdict `reports/champions-panel-v0-i7b-mega-smoke.md`) — off-by-default `eval/opp_mega_trace.py` sidecar (raw components only, LF-only bytes, `raw_score` = the FINAL post-depth-2 `score_vector` value), reachable end-to-end `run_schedule → run_local_gauntlet → hero _Client → agent_choose → decision core`, sink forwarded on **both** heuristic agents, and rows stamped with the client's shared **request sequence** rather than a written-row counter. **Two P1s caught in review and fixed before the smoke:** (a) evidence kept the superseded 1-ply `detail.score` while depth-2 overwrote `score_vector[i]` in place and `aggregate_score` read the final vector — the sidecar attributed to the decision a number it never used; (b) `decision_index` drifted against decision-trace, because team preview writes a trace row but no sidecar row, so the first REAL decision was trace 1 / sidecar 0. **2-battle live smoke @ git_sha `3d23e654a29689b68f3c936653726d6a36a6934d`, config_hash `b3cb6ea1a4836060` (LF-stable, platform-independent), run_id `d074ce1c8a69a2e1`**: 2/2 normal, 0 crashes, 0 invalid, **19/19 standard gates PASS**, worst p95 **672 ms** (budget 1000, unchanged); 19/19 trace-v3 rows valid; 17/17 sidecar rows valid and LF-only; every sidecar `(battle_id, decision_index)` resolves to exactly one trace row, with gaps **only** at the two `team_preview` rows — the live confirmation of the [P1] fix. **NARROW EXPOSURE, part of the verdict:** only **1 of 17** scored decisions ever exposed a foe-Mega hypothesis (battle `242a0c3ec6d0e79c`, decision 4: `required = retained = scored = {"1","none"}`, twin `response_ids` `aggro->a|mega=1` + `aggro->a|mega=none`, 41 distinct hero candidates scored against both) — **slot 1 only; slot 0, dual-Mega and activation ordering were never exercised live**. Evidence the mechanism works, NOT broad opponent-Mega validation, and **no Strength or latency claim** | **1)** The measurement-only Champions latency **machinery (I8-A–C) is built and merged offline** (PR #20 @ `32cdd4e`) — instrumentation, sidecar, both validator tiers, manifest producer, arm matrix/harness and all six arms, proven against a production-topology session, with **no run taken and no latency claim**. D0 and its Kaggle D0-K calibration have run (cost data only, scratch, no verdict), closing the execution decisions: **`reps` = 30 timed reps/arm** (warmups unchanged → 15 arms × 30 = 450 rows), **`MAX_BATTLES` = 200 / `MAX_SCORED_DECISIONS` = 2000**, and the **fixed Windows machine** as the measurement host for the microprofile run and I8-D. **Kaggle is reserved for later coverage/outcome/Strength as its own hardware stratum; platforms are never pooled** (its CPU changes between sessions, so a Kaggle p95 is not reproducibly comparable, and the gate needs exposure and latency from the same run). The 450-row microprofile RAN CLEAN and is FROZEN (`data/eval/champions-panel-v0/i8-microprofile/`, `reports/champions-panel-v0-i8-microprofile.md`) — cost-mechanism localization only (oneshot scales with process starts/batches; persistent ≈144 ms cold / ≈10 ms warm), **no live-latency and no Strength verdict**. **The I8-D live-latency HARNESS is merged (PR #23 @ `3b6070c`, code + tests only, two blocking review rounds resolved / final PASS, full suite 2777 passed); after a team-path wiring fix (PR #26 @ `9fc0f36`) the live-gate RUN then EXECUTED once and returned `FAIL`** — active foe-Mega p95 **1110.213 ms > 1000 ms**, exposure floor met (60 active-valid from 45 distinct battles), `stop_reason=exposure_floor_met`, 75 battles / 679 decisions, FROZEN (`data/eval/champions-panel-v0/i8d-live/`, `reports/champions-panel-v0-i8d-live.md`). This is a **load-bearing latency FAIL** — the pinned 1000 ms budget is **not** moved. The **latency-reduction slice (Lever A) is MERGED via PR #30 @ `6b2f955`** (a behavior-neutral fold of the game-mode incoming classification into the decision's single shared `DamageOracle` scoring flush, plus hardened counterproofs; full suite 2799/1/1). The **UNCHANGED post-Lever-A I8-D live-gate rerun then RAN once on `9d915f2` → FAIL** — active foe-Mega p95 **1160.515 ms > 1000 ms**, exposure floor met (60 active-valid from 45 distinct battles), `stop_reason=exposure_floor_met`, 75 battles / 679 decisions, evidence frozen LOCALLY at `1262e36` under `data/eval/champions-panel-v0/i8d-live-post-lever-a/` + verdict report `fe05054`. The 968.513 ms model projection **did not materialize empirically**; the **+50.302 ms** vs the pre-Lever-A FAIL is **descriptive only — no causal Lever-A latency effect is derivable**. That evidence/docs PR is now MERGED (PR #32 @ `34b088e`), and the **offline latency diagnosis + Lever B (B2) design + implementation are MERGED via PR #33 @ `b192825`** (a behavior-neutral decision-start `mixed_batch` pre-pass; golden byte-identical; full suite 2835 passed; CI 8/8; it engages on the gauntlet live path); the **UNCHANGED I8-D live-gate rerun then RAN once on `3db4ac7` and returned a valid PASS** (active foe-Mega p95 850.245 ms ≤ 1000 ms; exposure floor met 60/44; 72 battles/651 decisions; stop=exposure_floor_met; seed_log_verified; evidence `4b4be54`, report `062b6d0`); the drop vs the FAILs is descriptive only (no causal Lever-B or run-to-run-variance claim); the **1000 ms latency blocker is now CLOSED for this run**; the opponent-Mega coverage-gate design + implementation (Plan A) is MERGED via PR #37 @ `10f9adf` (code + tests only, no run); because it touches the LIVE decision-profile v3 write path, the prior I8-D PASS does not carry over — the UNCHANGED rerun then RAN once on `bd590c1` and returned **PASS** (active foe-Mega p95 864.94 ms ≤ 1000 ms; exposure floor met 60/45; 75 battles/679 decisions; stop=exposure_floor_met; seed_log_verified; evidence + report MERGED via PR #39 @ cbaa4b9; comparisons to prior runs descriptive only, no causal/variance claim); the latency precondition for `bd590c1` is CLOSED (NOT `cbaa4b9` — identity gap, no transfer). The coverage gate then ran once on `cbaa4b9` (after one technical-abort first attempt, excluded from the verdict population) → **FAIL** (`schedule_exhausted`; 200 battles/1956 decisions; safety violations 0; `slot0`/`slot1`/`order_tie` floors met; **`both_foe_slots` 0/0 floor NOT met**; evidence frozen locally `4109abd` + report `e08412e`); Strength is now blocked on this coverage-gate FAIL AND on the unestablished latency precondition for `cbaa4b9` (candidate-identity gap vs `bd590c1`'s PASS — see item 1); next = review+merge this evidence/report/docs, then a separately-authorized diagnosis/design slice for the zero-exposure (no identical rerun, no schedule/threshold change); do not reinterpret that LIVE budget as a per-arm microprofile threshold. **2)** The opponent-Mega coverage gate has now run once and FAILed on `both_foe_slots` zero-exposure; a diagnosis/design slice and its own rerun are required before a fresh coverage PASS, and only then does independent-holdout design proceed before any Strength run; the I7b-C smoke's 1/17 slot-1-only exposure is not broad validation. **3)** Strength remains **NO-GO** until both gates pass. **4)** Run the I7a CRLF/config-hash impact audit in parallel as provenance housekeeping; do not cite its historical config hash as cross-platform evidence before classification. |
| Champions Gate B — Independent Strength Holdout | **RAN once → SAFETY-FAIL** (candidate `bc2d6df`, identity `32f79b8e52444aa3`); evidence FROZEN + MERGED (PR #57 @ `cccfb30`, freeze `48558aa`). Harness built + merged earlier (PR #52 @ `7a9685c`); live-run harness fixes PR #54 @ `a7d5330` + PR #55 @ `bc2d6df`. Disjointness review ACCEPTED + MERGED (PR #56 @ `7412f27`) | Tasks 1–13 (spec `2026-07-20-champions-coverage-strength-holdout-design.md` + Amendment A1; plan Rev. 25): 180-key schedule; six sealed blind-curated `validate-team`-legal `gen9championsvgc2026regma` holdout teams (opaque `gbh_*`, mapping only in the holdout manifest, A1.1); panel + **additive** closed-schema Gate B baseline (generic T6 byte-identical, A1.3); leakage/disjointness/near-duplicate/strata/ledger guards; McNemar verdict; `champions-strength-holdout-arm`/`-combine` CLI. Full offline suite **3582 passed / 3 skipped / 1 xfailed** at merge; baseline manifest a single immutable commit (owner-authorized rewrite; SHA-map `docs/projects/champions/audits/2026-07-23-gate-b-baseline-immutability-rewrite-sha-map.md`) | **SAFETY-FAIL, no Strength claim.** Cause: `invalid_choices` A(heuristic)=**1** / B(max_damage)=**0** — one illegal action across the 180 held-out matchups (`Can't switch: The active Pokémon is trapped`), battle `9ccc312c51d95bfe`; fail-closed regardless of margin. Root cause **PLAUSIBLE, not CONFIRMED** (one slot `trapped`, the other `maybeTrapped` upgraded on re-request; the chosen slot is not settleable from the frozen room-log — needs the `/choose` string or DecisionTrace). All three gates on ONE identity, no commits between: I8-D PASS (p95 **873.762 ms**) + coverage PASS (0 violations) — **both EXTERNAL and UNFROZEN, not citable as frozen evidence** — then combine SAFETY-FAIL. Descriptive only, NOT strength: 180 total / 100 discordant / delta **+0.044444** / 89 vs 81 / `exact_p: null`. Ledger budget for `config_hash 594295543f13a55d` **CONSUMED** (`justification: null`) → next attempt needs a justified repeat or a new independent holdout, **decision not yet made**. The trapped-switch defect is now FIXED and merged (PR #60 @ `7dafde8` production+tests, PR #61 @ `a9475e5` pin anchor): ActiveSlot gained `maybe_trapped` (alias `maybeTrapped`) -- the field the server sends and pydantic was silently dropping -- and `_voluntary_switches` returns [] when either `trapped` or `maybe_trapped` is truthy, while the FORCED replacement path stays untouched (still legal while trapped, pinned by regression tests). The new field carries `exclude_if` so it is omitted when absent: without it, `model_dump(exclude_none=False)` -- which decision_profile HASHES -- moved the pinned C3-proof fixture_input_hash 3d246b21910204ec -> 1a15d8ded702c464; that was fixed at source, NOT by re-pinning the proof. Two fail-closed guards were added: a schema-coverage test for request slot fields that are neither modelled nor allowlisted-with-reason, and an anchor binding that hand-transcribed set to `showdown_commit` in config/eval/provenance.yaml. No gate run, no evidence freeze, no ledger change, no strength claim; the fix yields a NEW git_sha hence a NEW candidate identity and does NOT authorize a Gate B rerun. Next, separately authorized and NOT started: the ledger re-run decision (now the gating item); runtime detection of unmodelled request keys for a server no pin governs (NOT via extra="allow", which would re-break the serialization hashes); the un-pinned Node version; and the local suite's pre-existing 115 failures / 21 errors from missing `npm ci --prefix tools/calc` in fresh worktrees. **Champions Strength NO-GO.** |

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
FAIL (← taken) → latency-reduction slice (Lever A) MERGED via PR #30 @ 6b2f955 (behavior-neutral fold + hardened counterproofs); the UNCHANGED post-Lever-A I8-D gate rerun RAN once on 9d915f2 → FAIL (active foe-Mega p95 1160.515 ms > 1000 ms; 60 active-valid/45 battles; 75 battles/679 decisions; evidence frozen locally 1262e36 + report fe05054; 968.513 ms projection NOT materialized; +50.302 ms descriptive only, no causal Lever-A effect); evidence/docs PR MERGED (PR #32 @ 34b088e); offline diagnosis + Lever B (B2) MERGED via PR #33 @ b192825 (behavior-neutral decision-start mixed_batch pre-pass, golden byte-identical, full suite 2835/1/1, CI 8/8, engages on the live path); the UNCHANGED I8-D live-gate rerun RAN once on 3db4ac7 → PASS (active foe-Mega p95 850.245 ms ≤ 1000 ms; 60 active-valid/44 battles; 72 battles/651 decisions; exposure_floor_met; evidence 4b4be54, report 062b6d0); drop descriptive only, no causal/variance claim; latency blocker CLOSED (this run's evidence)
        ↓
opponent-Mega coverage-gate design + implementation (Plan A) MERGED via PR #37 @ 10f9adf
   → code + tests only (2 ultrareview rounds resolved, 6 P1s + 2 follow-ups); NO server/battle/coverage-gate run
   → touches the LIVE decision-profile v3 write path (foe_mega_slots/foe_mega_order_tie stamped on every live decision) → the 3db4ac7 I8-D PASS does NOT carry over to this merge SHA
        ↓
I8-D latency RERUN (separately authorized): fresh worktree @ bd590c1, preflight (two geometry
mistakes in the run commands caught and fixed before any live action), then an unchanged run
   → RAN once on bd590c1 → PASS: active foe-Mega p95 864.94 ms ≤ 1000 ms; exposure floor met
     (60 active-valid from 45 distinct battles); 75 battles/679 decisions; stop=exposure_floor_met;
     seed_log_verified; evidence + report MERGED via PR #39 @ cbaa4b9 under
     data/eval/champions-panel-v0/i8d-live-post-coverage-harness/ + report f0d42dd; kept strictly
     separate from every prior I8-D run, comparisons descriptive only (no causal/variance claim);
     latency precondition for candidate bd590c1 CLOSED
        ↓
champions-coverage-gate (separately authorized): preflight on the new merge SHA cbaa4b9, then a
first attempt aborted technically (missing env var, no battle, no verdict, excluded from the
verdict population), then a fresh attempt with a fresh output path
   → RAN once on cbaa4b9 → FAIL: stop=schedule_exhausted; 200 battles/1956 decisions; safety
     violations 0; slot0 82/50, slot1 298/173, order_tie 100/100 (floor met); both_foe_slots 0/0
     (floor 15/6 NOT met — the verdict driver); evidence frozen LOCALLY (not yet merged) at
     4109abd + report e08412e
        ↓
both_foe_slots zero-exposure DIAGNOSED (root cause: the real preview picker never led with both
Mega holders, so the cell was structurally unreachable) + REMEDIATED (T1 cov_foe_both team
redesign + T2 shared candidate_identity helper + T3 same-candidate I8-D-PASS gate + four
independent review rounds hardening the I8-D-verdict guard to the full real 25-field schema +
cross-field consistency + NaN/negative/±∞ p95_ms rejection; final re-review PASS, no remaining
findings) → MERGED via PR #42 @ f2bb818 (full suite 2971 passed / 18 pre-existing unrelated
failed / 1 skipped / 1 xfailed, zero new failures) — safety/provenance/defect-fix work only, no
live gate ran, no Strength claim
        ↓
I8-D latency RERUN (separately authorized): fresh worktree, candidate identity for f2bb818 (a new
git_sha → a new identity; bd590c1/cbaa4b9 do not transfer, same identity-gap pattern as every
prior merge)
        ↓
PASS → champions-coverage-gate (separately authorized), with the repaired both_foe_slots team, to
test whether the fix actually restores exposure (this IS the fix, not an identical rerun; no
post-hoc threshold/schedule change)
FAIL (← would block the coverage rerun) → diagnose the regression before proceeding
        ↓
only on a fresh coverage PASS does independent Strength-holdout design (six new blind-curated
teams, leakage protection, paired holdout) follow → its run separately authorized
        ↓
Strength run only after latency + coverage-gate + Strength-holdout gates all pass
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
   `docs/projects/accuracy/specs/2026-07-14-accuracy-default-on-design.md`. Decision note:
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
