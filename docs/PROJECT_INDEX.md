# Project Index

**Orientation card for new Cursor / Claude / Codex sessions.**
This file is an entry map — not a replacement for [`docs/ROADMAP.md`](ROADMAP.md), which remains
the authoritative status matrix and next-decision source. When they disagree, trust the roadmap
and git history; update this index if it drifts.

Last reconciled: 2026-07-17 (**I8-A–C offline latency machinery MERGED via PR #20 @ `32cdd4e` — measurement machine built and proven offline, NO runs, no latency/Strength claim; D0 next, separately authorized; `reps` and D-2 open and dependent on D0**; **I7a own-Mega SAFETY PASS, merged to `main` @ `1053cf1`**; **I7b-A MERGED via PR #12 @ `cdc55c2`**; **I7b-B Tasks 1-6 REVIEW-PASS · MERGED via PR #13 @ `755b144`**, full suite **2169 passed, 2 skipped, 1 xfailed**, foe-Mega modeling now LIVE for `format_config.mega` and byte-identical for Reg-I/`None`; **I7b-C PRE-SMOKE REVIEW-PASS + 2-battle opponent-Mega SAFETY SMOKE PASS · NARROW EXPOSURE, merged via PR #17 @ `8942232`** (1/17 scored decisions, slot 1 only; `reports/champions-panel-v0-i7b-mega-smoke.md`) — safety/telemetry evidence only; **Strength still NO-GO** — the dedicated latency gate is the load-bearing blocker, followed by an explicit coverage/independent-holdout gate before any Strength run; I7 Mega design spec rev. 10 **APPROVED**, implementation plan **Rev. 9 / execution complete**; protocol audit @ `fc4f251`; I6 @ `3bcd4b3` on `main`).

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

Ordered front-track work as of **2026-07-17** (I8-A–C offline latency machinery merged, PR #20 @ `32cdd4e`; D0 next, separately authorized):

1. **Champions latency — offline machinery built and merged (I8-A–C, PR #20 @ `32cdd4e`); D0
   is the next, separately-authorized step.** The measurement-only latency machinery is now on
   `main`: instrumentation of the calc cost drivers, the decision-profile sidecar + both
   validator tiers, the manifest producer, the microprofile arm matrix/harness and all six
   previously-unconstructible arms (P-1…P-5), built and proven **offline** against a
   production-topology session (full suite at merge **2615 passed, 2 skipped, 1 xfailed**).
   **No run has been taken and no latency claim exists.** The next step is **D0**: a small
   **live** timing run to cost the cap — a **new live run, authorized separately** — which
   fixes `reps` (no default anywhere) and **D-2** (`MAX_BATTLES` / `MAX_SCORED_DECISIONS`),
   both **open and dependent on D0**. Context, measured not assumed (I7b-B): the genuinely
   ACTIVE foe-Mega path costs ≈2.4× the inactive decision on a synthetic tie fixture (16 vs 6
   calc batches); prior safety smokes ran at worst p95 331/588/672 ms against the unchanged
   1000 ms budget, **none a dedicated profile** — so the profile is still owed, and D0 is how
   it starts.
2. **Champions coverage + Strength design** — starts only after the dedicated latency gate
   passes. The design must pre-register a broader opponent-Mega exposure requirement (including
   both foe slots and dual-Mega/activation-ordering cases) and a genuinely independent Strength
   holdout. I7b-B/I7b-C prove the mechanism end-to-end on two battles, but the smoke exposed a
   foe-Mega hypothesis in only **1 of 17** scored decisions and only in slot 1. The
   `rain_offense` panel team is not an independent Strength holdout (reused across
   parser/I5/I6/I7a safety work). **Strength remains NO-GO** until both gates are designed and
   satisfied; a latency PASS alone does not authorize a Strength run.
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
| **Status** | P0–P4 on main; I5 mixed @ `4da007b`; **HP-suffix PASS** @ `62117b5`; **I6 PASS** @ `3bcd4b3`; audit @ `fc4f251`; **I7 Mega design APPROVED rev. 10** (plan Rev. 9); **I7a own-Mega SAFETY PASS, merged to `main`** @ `1053cf1`; **I7b-A MERGED** @ `cdc55c2`; **I7b-B Tasks 1-6 REVIEW-PASS/MERGED** @ `755b144` (PR #13); **I7b-C PRE-SMOKE REVIEW-PASS + opponent-Mega SAFETY SMOKE PASS · NARROW EXPOSURE** (1/17 decisions, slot 1 only) @ `3d23e654`; **I8-A–C offline latency machinery MERGED via PR #20 @ `32cdd4e`** (measurement machine built & proven offline, no runs) — **D0 next (separately authorized)**, `reps`/D-2 open & dependent on D0 — no Strength/latency claim. |
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
| I7b-A opponent-Mega foundation | **IMPLEMENTED · CODE-REVIEWED · MERGED via PR #12 @ `cdc55c2`** (focused gate 106 passed; full suite 2132 passed, 2 skipped, 1 xfailed) · additive/inert until I7b-B | `docs/superpowers/specs/2026-07-16-champions-opponent-mega-i7b-audit.md`, `docs/superpowers/plans/2026-07-16-champions-opponent-mega-i7b.md` |
| I7b-B dual projection + scoring | **REVIEW-PASS · MERGED via PR #13 @ `755b144`** (Tasks 1-6; full suite 2169 passed, 2 skipped, 1 xfailed, no new skip/xfail) · foe-Mega modeling LIVE for `format_config.mega`, byte-identical for Reg-I/`None` · `baselines.py`/`search.py` byte-identical across the slice | plan Rev. 7 (`docs/superpowers/plans/2026-07-16-champions-opponent-mega-i7b.md`); no report — no live run, no Strength claim |
| I7b-C telemetry + opponent-Mega smoke | **PRE-SMOKE REVIEW-PASS + LIVE SMOKE PASS · NARROW EXPOSURE** @ `3d23e654` (`dirty=false`; 19/19 standard gates PASS, worst p95 672 ms; 19/19 trace-v3 rows, 17/17 sidecar rows LF-only; every sidecar `(battle_id, decision_index)` → exactly one trace row, gaps only at `team_preview`) · **1 of 17** decisions exposed a foe-Mega hypothesis, **slot 1 only** — slot 0/dual-Mega/activation-ordering never exercised live · **no Strength claim, no latency claim** | `reports/champions-panel-v0-i7b-mega-smoke.md`, `data/eval/champions-panel-v0/smoke-i7b-mega/` (incl. `opp_mega_trace.jsonl`, `results.jsonl.config-manifest.json`); plan Rev. 9 |
| I8 offline latency machinery (A–C) | **MERGED via PR #20 @ `32cdd4e`** — instrumentation, decision-profile sidecar + both validator tiers, manifest producer, microprofile arm matrix/harness, and all six previously-blocked arms (P-1…P-5), built & proven **offline** against a production-topology session (full suite **2615 passed, 2 skipped, 1 xfailed**) · **no live battle, microprofile, benchmark or frozen evidence; no latency or Strength claim** · **D0 next (separately authorized)**; `reps` (no default) and D-2 (`MAX_BATTLES`/`MAX_SCORED_DECISIONS`) open & dependent on D0 | `docs/superpowers/specs/2026-07-16-champions-i8-latency-design.md` (Errata 1–2, §4.2 C3 status), `docs/superpowers/plans/2026-07-17-champions-i8-latency.md`; **no report — no run** |

**Open blockers**

- **Latency gate:** the measurement-only **machinery is built and merged offline (I8-A–C, PR #20
  @ `32cdd4e`)** — no run taken, no latency claim. Context: I5 pre-fix worst p95 **3235 ms** vs
  the pinned **1000 ms** budget (that run also contained state-degradation; no causal link);
  I6/I7a-C/I7b-C safety smokes measured 331/588/672 ms, none a dedicated profile; the active
  foe-Mega path still measures about **2.4×** the inactive decision on the synthetic tie fixture.
  The next step is **D0**, a small **live** timing run — a new live run **authorized separately**
  — which fixes `reps` (no default) and **D-2** (`MAX_BATTLES` / `MAX_SCORED_DECISIONS`), both
  open and dependent on D0. Do not optimize, lower the click rate, or change the budget before
  that profile runs.
- **Opponent-Mega live coverage:** I7b-C is merged and its telemetry chain is live, but the
  frozen smoke exposed a hypothesis in only **1/17** scored decisions and only for foe slot 1.
  Slot 0, dual-Mega, and activation ordering still need a pre-registered coverage gate before
  any Strength result can be interpreted broadly.
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
- Design: `docs/superpowers/specs/2026-07-14-champions-panel-v0-design.md`
- I7 Mega design: `docs/superpowers/specs/2026-07-14-champions-mega-i7-design.md`

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
- Spec: `docs/superpowers/specs/2026-07-14-accuracy-default-on-design.md`
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

- Spec: `docs/superpowers/specs/2026-07-14-vgc-battle-logs-import-audit.md` (PROPOSED @ `1251dd6`)
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
| **Status** | **Spec Revision 2 committed** (`docs/superpowers/specs/2026-07-12-value-calibration-design.md` @ `8e4c47f`); **implementation not started** — awaits explicit sign-off → plan → run. |
| **Role** | Diagnostic: does action carry signal beyond board state? Positive outcome = **GO for counterfactual data collection**, not proof a value-head is justified. |

**Authoritative artifacts**

- Spec: `docs/superpowers/specs/2026-07-12-value-calibration-design.md`
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
