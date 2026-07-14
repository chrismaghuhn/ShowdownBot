# Project Index

**Orientation card for new Cursor / Claude / Codex sessions.**
This file is an entry map — not a replacement for [`docs/ROADMAP.md`](ROADMAP.md), which remains
the authoritative status matrix and next-decision source. When they disagree, trust the roadmap
and git history; update this index if it drifts.

Last reconciled: 2026-07-14 (I5 mixed verdict on `feat/champions-i5-smoke`).

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

Ordered front-track work as of 2026-07-14 (post-I5):

1. **Champions HP-suffix state parser** — `100y`/`100g` HP tokens break state build → random-legal
   `choose_for_request` degradation (5/94 non-preview decisions in I5 trace). Hard blocker before
   strength or decision-quality claims.
2. **Live damage → calc gen-0** — speed oracle is gen-0 (I4); live damage scoring can still use
   gen-9 mechanics until threaded through Champions `CalcProfile`.
3. **Mega overlay** — not modeled; blocks honest strength interpretation.
4. **Champions latency** — worst p95 **3235 ms** vs **1000 ms** Reg-I gate (I5 STANDARD SAFETY-FAIL);
   profile or adopt a pre-justified Champions budget before Strength.
5. **Accuracy larger follow-up** — user-gated only; not front track unless reprioritized.
6. **poke-env** — reference-only for parser diffs (`reports/champions-poke-env-reference-audit.md`).

---

## Active Tracks

### 1. Champions Panel v0

| | |
|---|---|
| **Status** | P0–P4 on main; **I5 mixed verdict** on `feat/champions-i5-smoke` @ `4da007b`: CONFIG/PROVENANCE PASS · STANDARD SAFETY FAIL (latency) · STATE-DEGRADATION FOUND. |
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

**Open blockers**

- **HP-suffix state parser (`100y`/`100g`):** state build fails → random-legal degradation (5 degraded hero decisions in I5 trace). **Hard blocker** before strength/decision-quality.
- **Live damage path:** speed oracle uses calc gen-0 (I4); live damage scoring can still use gen-9 mechanics.
- **Mega overlay:** not modeled.
- **Latency gate:** worst p95 **3235 ms** vs **1000 ms** Reg-I budget — official `eval-report` SAFETY-FAIL; profile or set Champions budget before Strength.

**Explicit non-claims**

- I5 proves **config/provenance wiring + harness completion** on a 10-row panel — not strength, not full safety pass, not full heuristic fidelity.
- Hero win counts (P4 2/6, I5 3/10) are **not** interpreted.

**Related**

- poke-env audit (reference): `reports/champions-poke-env-reference-audit.md` @ `75bbb4b`
- Design: `docs/superpowers/specs/2026-07-14-champions-panel-v0-design.md`

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
   - Champions: `reports/champions-panel-v0-i5-smoke.md` (I5), `reports/champions-panel-v0-pilot-smoke.md` (P4)
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
| Eval provenance pattern | `data/eval/champions-panel-v0/smoke-i5/` (`config-manifest.json`, `dirty=false`) |
| Accuracy env knobs | `SHOWDOWN_ACCURACY_MODE`, `SHOWDOWN_ACCURACY_BRANCH_CAP` |
