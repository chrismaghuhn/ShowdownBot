# Project Index

**Orientation card for new Cursor / Claude / Codex sessions.**
This file is an entry map — not a replacement for [`docs/ROADMAP.md`](ROADMAP.md), which remains
the authoritative status matrix and next-decision source. When they disagree, trust the roadmap
and git history; update this index if it drifts.

Last reconciled: 2026-07-16 (**I7a own-Mega SAFETY PASS, merged to `main` @ `1053cf1`**; **I7b PLAN APPROVED · I7b-A implementation authorized · NOT IMPLEMENTED** — `docs/superpowers/specs/2026-07-16-champions-opponent-mega-i7b-audit.md`, `docs/superpowers/plans/2026-07-16-champions-opponent-mega-i7b.md`; I7 Mega design spec rev. 10 **APPROVED**; protocol audit @ `fc4f251`; I6 @ `3bcd4b3` on `main`).

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

Ordered front-track work as of **2026-07-16** (post I6; protocol audit @ `fc4f251`):

1. **I7a own Mega — SAFETY PASS, merged to `main`** (`reports/champions-panel-v0-i7a-mega-smoke.md`
   @ `1053cf1`) — real Mega click + protocol-bound state rebuild proven; next: **I7b PLAN APPROVED ·
   I7b-A implementation authorized · NOT IMPLEMENTED** (`docs/superpowers/specs/2026-07-16-champions-opponent-mega-i7b-audit.md`,
   `docs/superpowers/plans/2026-07-16-champions-opponent-mega-i7b.md`).
2. **Champions latency** — I5 pre-fix worst p95 **3235 ms** vs **1000 ms** Reg-I gate (that run also
   contained state-degradation; no causal link to p95 established); I6 2-battle smoke measured
   **331 ms** worst p95; I7a-C 2-battle smoke measured **588 ms** worst p95 (all safety passes,
   not a dedicated profile or causal improvement claim).
3. **Champions Strength** — **NO-GO until I7b + latency** (`Champions Strength NO-GO — opponent Mega response modeling missing`); the `rain_offense` panel team is not an independent Strength holdout (reused across parser/I5/I6/I7a safety work).
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
| **Status** | P0–P4 on main; I5 mixed @ `4da007b`; **HP-suffix PASS** @ `62117b5`; **I6 PASS** @ `3bcd4b3`; audit @ `fc4f251`; **I7 Mega design APPROVED rev. 10**; **I7a own-Mega SAFETY PASS, merged to `main`** @ `1053cf1`; **I7b PLAN APPROVED · I7b-A implementation authorized · NOT IMPLEMENTED**. |
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
| I7b opponent-Mega audit + plan | **I7b PLAN APPROVED · I7b-A implementation authorized · NOT IMPLEMENTED** | `docs/superpowers/specs/2026-07-16-champions-opponent-mega-i7b-audit.md`, `docs/superpowers/plans/2026-07-16-champions-opponent-mega-i7b.md` |

**Open blockers**

- **Mega overlay:** **I7a own-Mega SAFETY PASS**, merged to `main`; **I7b (opponent Mega) PLAN APPROVED · I7b-A implementation authorized · NOT IMPLEMENTED** — spec: `docs/superpowers/specs/2026-07-14-champions-mega-i7-design.md`; audit+plan: `docs/superpowers/specs/2026-07-16-champions-opponent-mega-i7b-audit.md`, `docs/superpowers/plans/2026-07-16-champions-opponent-mega-i7b.md`.
- **Opponent Mega response model (I7b):** missing — **Strength NO-GO** until implemented.
- **Latency gate:** I5 pre-fix worst p95 **3235 ms** vs **1000 ms** Reg-I budget (that run also
  contained state-degradation; no causal link established); I6 2-battle smoke **331 ms** worst p95
  (safety pass only) — dedicated profile/budget still needed before Strength.

**Closed blockers**

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
| Eval provenance pattern | `data/eval/champions-panel-v0/smoke-i5/` (I5 baseline), `smoke-i5-hpfix-validation/` (HP-fix revalidation @ `62117b5`), `smoke-i6-damage-gen0/` (I6 @ `3bcd4b3`) |
| Accuracy env knobs | `SHOWDOWN_ACCURACY_MODE`, `SHOWDOWN_ACCURACY_BRANCH_CAP` |
