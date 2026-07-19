# External Battle-Logs Import Audit — Human-Replay Feasibility Slice

**Status:** PROPOSED — pending review (read-only import audit only; **no bot code**, **no gate touch**;
implementation/execution **not** approved)
**Date:** 2026-07-14
**Builds on:** [`2026-07-11-2b5a-vgc-bench-ingest-partA-design.md`](../../learning/specs/2026-07-11-2b5a-vgc-bench-ingest-partA-design.md)
(Part A foundation: `load_raw`, `parse_battle`, `gate_format`, `build_sample_manifest`)
**Implements:** bounded audit of whether external HuggingFace human-replay logs can be translated
into our decision/legality schema before any downstream use (BC, human prior, generalization panels).

## 0. What this slice does

Run a **fail-closed, read-only import audit** across three **independent tracks** with distinct
trust levels. VGC-Bench (Tracks A/B) is the primary curated path; HolidayOugi Showdown Replays
(Track C) is an **optional, lower-trust** supplement — **not** a VGC-Bench replacement.

**Track A (VGC-Bench active)** — sequential:

1. **Phase 0a** — plumbing smoke on `cameronangliss/vgc-battle-logs` only (20–50 logs).
2. **Phase 0b** — stratified active MA/MB audit (200 logs) for parser / BO3 / OOD stress.

**Track B (VGC-Bench archive)** — after 0a PASS + explicit approval:

3. **Phase 0c** — Reg-I human-prior feasibility from `cameronangliss/vgc-battle-logs-sv` (200 logs).

**Track C (HolidayOugi Showdown Replays)** — optional, lower trust; independent of 0a/0b/0c timing:

4. **Phase 0d** — filtered VGC 2025/2026 smoke (20–50 logs) from `HolidayOugi/pokemon-showdown-replays`.

Measure replay compatibility with our parsing chain, outcome re-derivation, perspective/action
reconstruction, and legal candidate matching. Produce deterministic audit reports under
`data/research/vgc-bench-import-audit/`.

This slice answers:

> Can external human-replay logs be ingested into our schema with acceptable dropout, without
> polluting self-play / gate corpora, and with correct format/regulation separation?

This is **not** a strength claim, **not** training, and **not** a gate artifact update.

### 0.1 Track trust levels

| Track | Source | Trust | Primary role |
|-------|--------|-------|--------------|
| **A** | `cameronangliss/vgc-battle-logs` | **High** (OTS-curated Champions MA/MB) | Parser / BO3 / OOD stress |
| **B** | `cameronangliss/vgc-battle-logs-sv` | **High** (OTS-curated Reg I archive) | Reg-I human-prior feasibility |
| **C** | `HolidayOugi/pokemon-showdown-replays` | **Lower** (bulk API scrape, unverified OTS/reg/provenance) | Parser stress, format mining, coverage discovery; large-sample **candidate only** |

Track C PASS authorizes further **audit/expansion** only. BC / human-prior / training use from
Track C requires a **separate** license/terms review (§4.4) even after technical PASS.

## 1. Explicit non-goals

- **No mixing** with the running `accuracy-default-on-devstrength-ab` measurement
  (`data/eval/accuracy-default-on/`). That run stays isolated: Candidate `{}` vs explicit
  `SHOWDOWN_ACCURACY_MODE=0`, same commit/seed-base, no external human-replay material.
- **No treating Track C as a VGC-Bench substitute** — curated OTS/regulation provenance from
  Tracks A/B remains the primary path for human-prior work.
- **No edit** to `data/eval/accuracy-gate/`, cap-derisk gate JSON, or any frozen eval reference.
- **No import** of `research/vgc_bench_ingest` from live path (`battle/decision`, `learning/*`,
  `client/gauntlet`) — INV-1 unchanged.
- **No training**, reranker export, teacher mix, or policy change.
- **No commit** of full HF downloads (~630 MB VGC-Bench active; ~6.78 GB VGC-Bench archive;
  ~69.8 GB HolidayOugi Parquet). Only manifests + small audit artifacts (reports, optional
  ≤50-log hand-trimmed smoke fixtures).
- **No downstream dataset.jsonl.gz** export in this slice — audit metrics only.
- **No value-head / strength claim** from observational win/loss labels (no counterfactual outcomes).
- **No BC / human-prior build from Track C** until technical PASS **and** explicit license/terms
  review (§4.4).
- **No measurement runs from a dirty worktree** — see §2.3.

## 2. Isolation and workspace hygiene

### 2.1 Separate research slice

External replay audit work is a **distinct research slice**, not an eval-gate extension.

**Preferred:** dedicated git worktree (e.g. `vgc-bench-import-audit`) so untracked eval artifacts
in the main worktree cannot collide.

**Minimum:** all audit artefacts live only under:

```
data/research/vgc-bench-import-audit/
```

**Forbidden paths for audit artefacts:**

- `data/eval/accuracy-default-on/` (running default-on strength measurement)
- `data/eval/accuracy-gate/` (frozen gate references)
- `data/datasets/` (teacher / reranker corpora)
- any `data/eval/*/results.jsonl` self-play run bundle

### 2.2 Artefact layout (committed vs local-only)

```
data/research/vgc-bench-import-audit/
  active-ma-mb/                    # Track A — cameronangliss/vgc-battle-logs
    sample-manifest.json           # COMMIT
    reports/
      phase-0a-smoke-report.json   # COMMIT
      phase-0a-smoke-report.md     # COMMIT
      phase-0b-audit-report.json   # COMMIT (after 0a PASS)
      phase-0b-audit-report.md     # COMMIT
    raw/                           # LOCAL ONLY — gitignored
      phase-0a-smoke.json
      phase-0b-stratified-200.json
  archive-reg-i/                   # Track B — cameronangliss/vgc-battle-logs-sv
    sample-manifest.json           # COMMIT
    reports/
      phase-0c-audit-report.json   # COMMIT (after 0a PASS + explicit 0c approval)
      phase-0c-audit-report.md     # COMMIT
    raw/                           # LOCAL ONLY
      phase-0c-stratified-200.json
  showdown-replays/                # Track C — HolidayOugi/pokemon-showdown-replays
    sample-manifest.json           # COMMIT
    reports/
      phase-0d-smoke-report.json   # COMMIT
      phase-0d-smoke-report.md     # COMMIT
    raw/                           # LOCAL ONLY — never commit Parquet or large extracts
      phase-0d-smoke.parquet       # or equivalent small local slice
```

Add `data/research/vgc-bench-import-audit/**/raw/` to `.gitignore` if not already covered by a
broader research-raw ignore rule.

### 2.3 Dirty worktree prohibition

**Do not start eval measurement runs or audit execution from a worktree where unrelated untracked
files are present** (e.g. untracked specs plus `data/eval/accuracy-default-on/` artefacts in the
same tree). The accuracy-default-on strength measurement requires `git status --porcelain` empty
per its own spec; audit execution should follow the same discipline:

- use a **clean checkout or dedicated worktree** before running any phase;
- never co-locate audit `raw/` downloads with in-progress eval run bundles under
  `data/eval/accuracy-default-on/`;
- committing this spec does not authorize execution — human approval of PROPOSED → APPROVED required
  first.

## 3. Dataset sources and format nuance (verified 2026-07-14)

| Track | HF id | Size (card) | Schema / formats | `gate_format` expectation | Audit phase |
|-------|-------|-------------|------------------|---------------------------|-------------|
| **A** | `cameronangliss/vgc-battle-logs` | ~630 MB | JSON wrapper; Champions Reg M-A / M-B (OTS), incl. BO3 | `MECHANICALLY_SIMILAR_BUT_NOT_TARGET` | **0a + 0b** |
| **B** | `cameronangliss/vgc-battle-logs-sv` | ~6.78 GB | JSON wrapper; Scarlet/Violet regs incl. Reg I 2025/2026 (OTS) | Reg I → `TARGET_COMPATIBLE` | **0c** (not in minimal smoke) |
| **C** | `HolidayOugi/pokemon-showdown-replays` | ~69.8 GB | **Parquet**; ~33M replays (card: 32,686,498 total, June 2026); fields incl. `id`, `format`, `players`, `log`, `uploadtime`, `views`, `formatid`, `rating`; date range 2005–2026 | Per-row via `format` / `formatid` + `gate_format`; OTS **not** guaranteed | **0d** (optional) |

**VGC volume in Track C (card, Gen 9):** VGC 2025 ~1,070,772; VGC 2026 ~654,340; Champions VGC
2026 ~296,331. Phase 0d filters to **VGC 2025 / VGC 2026** only (not Champions, not legacy gens).

**Hard rule (load-bearing):** Reg M-A / M-B must **never** be treated as Reg I. Enforced by
`research/vgc_bench_ingest/format_gate.py`. Track C rows must be gated per-row — bulk `formatid`
filter quality is itself an audit metric.

**Wrapper difference:** Tracks A/B use JSON `battle-id -> [epoch, log]`. Track C stores `log` in
Parquet rows — requires a thin **row adapter** (not `load_raw`) before `parse_battle`. Inner
protocol remains Showdown `|`-delimited text (`eval/battle_parse`, `eval/room_dump` family).

**Key structural difference vs our `room_raw` dumps:** all external sources are spectator/replay
logs without bot-side `|request|` injection. Perspective reconstruction and chosen-action
extraction are the hard checks (Part B logic; measured minimally for audit only).

## 4. Audit phases

### Phase 0a — Track A plumbing smoke (active VGC-Bench only, 20–50 logs)

**Goal:** prove HF download plumbing, `load_raw` strictness, `parse_battle`, `gate_format`, and
report generation on the **smallest viable VGC-Bench pull** before any stratified 200-log download.

| Source | Sample size | Notes |
|--------|-------------|-------|
| `cameronangliss/vgc-battle-logs` (**active only**) | 20–50 logs | Rough mix across MA BO1, MA BO3, MB; streaming subset, not full 630 MB |

**Explicitly out of 0a:** `vgc-battle-logs-sv` (6.78 GB) and `HolidayOugi/pokemon-showdown-replays`
(69.8 GB Parquet). Both deferred to 0c / 0d respectively.

**Per-log checks (0a):**

1. `load_raw` succeeds or raises `VgcBenchParseError` naming battle id (no silent skip).
2. `parse_battle` → `VgcBenchRawBattle`; `winner` / `turns` / `end_reason` re-derived via
   `eval/battle_parse.parse_battle_result` (no external field trusted).
3. `gate_format(format_name)` → `MECHANICALLY_SIMILAR_BUT_NOT_TARGET` for MA/MB (never
   `TARGET_COMPATIBLE`).
4. Raw + normalized log sha256 stable across re-parse.

**0a exit:** tooling completes without infrastructure failure; parse-fail rate measured (need not
meet final Go thresholds yet). If plumbing breaks, stop — do not proceed to 0b or 0c.

### Phase 0b — Track A stratified audit (active MA/MB, 200 logs, after 0a PASS)

**Goal:** measure coverage metrics on the active Champions dataset for parser / BO3 / OOD stress.

| Source | Sample size | Stratification (target) |
|--------|-------------|-------------------------|
| `cameronangliss/vgc-battle-logs` | 200 logs | 50 MA BO1, 50 MA BO3, 50 MB BO1, 50 MB BO3 (adjust if bucket sparse; document actual counts in manifest) |

**Per-battle checks (0b / 0c / 0d):**

| # | Check | Method | Metric |
|---|-------|--------|--------|
| 1 | Protocol parse | `parse_battle` (± row adapter for Track C) | `parse_fail_rate` |
| 2 | Outcome agreement | `parse_battle_result` vs `\|win\|` / `\|tie\|` | `outcome_mismatch_rate` (must be 0%) |
| 3 | Request/decision points | Adapted offline extractor (spectator-aware) | `turns_total`, `turns_with_reconstructed_state` |
| 4 | Chosen action uniqueness | Match observed protocol action(s) to one joint action | `ambiguous_action_match_rate` |
| 5 | Legal candidate match | `enumerate_slot_pairs` / action enumerator on reconstructed state | `no_legal_match_rate` |
| 6 | BO3 tagging | `gate_format.is_bo3` + game-index within series | `bo3_game1_tagged_rate` |
| 7 | Format provenance | `format_name` / `formatid` + `gate_format` on every audit row | `format_id` present on 100% of rows |
| 8 | OTS rule presence | rules tuple contains Open Team Sheets marker | `ots_rule_present_rate` |
| 9 | Rating bucket | `rating` field (Track C) or log metadata (Tracks A/B) | distribution table; `unrated_fraction` |

**Dropout definition:** a turn counts as dropped when `no_legal_match` or unrecoverable perspective
failure prevents binding a chosen human action to our enumerator output.

**0b exit:** report with GO/NO-GO against §6 thresholds for Track A. A 0b PASS is sufficient for
parser-stress / OOD-panel recommendations; it does **not** authorize Reg-I BC or human-prior export.

### Phase 0c — Track B: Reg-I human-prior feasibility (archive, after 0a PASS + explicit approval)

**Goal:** assess whether Reg-I logs from the VGC-Bench archive can support human-prior / BC
feasibility on our target format (`gen9vgc2025regi`).

| Source | Sample size | Stratification (target) |
|--------|-------------|-------------------------|
| `cameronangliss/vgc-battle-logs-sv` | 200 logs | Reg I 2025: 50 BO1 + 150 BO3 (or proportional; **never** mix MA/MB rows) |

**Prerequisites:** 0a PASS; explicit approval for 6.78 GB archive; clean worktree per §2.3.

Runs per-battle checks table above. §6 thresholds apply independently. 0c PASS required before
any Reg-I human-prior downstream spec.

### Phase 0d — Track C: HolidayOugi smoke (optional, lower trust, 20–50 logs)

**Goal:** assess whether bulk Showdown replays can supplement Tracks A/B for parser stress, format
mining, and coverage discovery — **without** assuming VGC-Bench-level curation.

| Source | Sample size | Filter |
|--------|-------------|--------|
| `HolidayOugi/pokemon-showdown-replays` | 20–50 rows | `formatid` / `format` ∈ {VGC 2025, VGC 2026} only; streaming Parquet slice, not full 69.8 GB |

**Track C-specific checks (in addition to per-battle table where applicable):**

| # | Check | Metric / output |
|---|-------|-----------------|
| C1 | License / terms | Dataset card license field + stated terms recorded in manifest; `license_status: verified \| unclear \| missing` |
| C2 | `formatid` filter quality | `formatid_filter_precision` — fraction of sampled rows that `gate_format` classifies as expected gen9 VGC after parse |
| C3 | Parquet → log adapter | `adapter_fail_rate` — rows where `log` field cannot be fed to `parse_battle` |
| C4 | OTS availability | `ots_rule_present_rate` (expected **lower** than Tracks A/B; report honestly) |
| C5 | Rating availability | `rating_present_rate`, bucket distribution |
| C6 | Provenance | `uploadtime` range, `id` uniqueness, no duplicate `log` hashes in sample |

**0d exit:** smoke report with technical metrics. Track C uses §6 thresholds where applicable, but
a 0d technical PASS is **necessary not sufficient** for any training downstream (§4.4).

### 4.4 Track C license gate (separate from technical PASS)

Before any BC / human-prior / training use of Track C data:

1. Record license field and terms from the HuggingFace dataset card in `sample-manifest.json`.
2. Human review: confirm training/derivatives allowed under those terms.
3. Document decision in audit report (`license_review: approved \| deferred \| rejected`).

Technical 0d PASS + `license_review: approved` required before a separate downstream spec may
reference Track C for BC. Default stance: **deferred** until explicitly reviewed.

### Phase 1 — Report synthesis (no new download)

Aggregate phase metrics into `audit-report.json` + `audit-report.md` per completed phase/track.
Include:

- provenance block (dataset id, revision/sha if known, sample manifest sha256, tool git sha)
- per-track trust level and format breakdown
- top failure exemplars (ids + reason codes; no full log bodies in committed report)
- explicit **GO / NO-GO** verdict per track against §6 thresholds
- Track C: license status and `formatid` filter precision
- downstream recommendation — qualitative only; Track C never auto-authorizes BC

## 5. Relationship to existing packages

| Package | Role in this slice |
|---------|-------------------|
| `research/vgc_bench_ingest` (Part A) | `load_raw`, `parse_battle`, `gate_format`, `build_sample_manifest` — Tracks A/B; `parse_battle` reused for Track C after row adapter |
| `eval/battle_parse` | Outcome re-derivation (trusted) |
| `eval/room_dump` | Normalization recipe for log hashes |
| `eval/room_raw_replay` | Reference comparator for bot-side `|request|` extraction; **not** drop-in for spectator logs |
| `battle/legal_actions` | Legal candidate enumeration for match-rate audit |
| `learning/audit` | **Separate concern** — audits our `dataset.jsonl.gz` rows downstream; this slice is upstream feasibility |

New audit orchestration code (if any) lives under `research/vgc_bench_ingest/` or
`research/vgc_bench_import_audit/` — never under `eval/` gate paths or `learning/` export paths.
Track C Parquet adapter lives in the research audit package only.

## 6. Go / No-Go criteria (0b, 0c, 0d — per track)

Audit **PASS** for a track only if **all** hold (where the check applies to that track):

| Metric | Threshold |
|--------|-----------|
| `parse_fail_rate` | < 1% |
| `outcome_mismatch_rate` | 0% |
| `no_legal_match_rate` | < 5% of reconstructed decision turns |
| `ambiguous_action_match_rate` | < 2% of reconstructed decision turns |
| BO3 game-1 tagging | 100% of BO3 battles carry `is_bo3=true` and `bo3_game_index` (≥1) |
| `format_id` on export rows | 100% |
| MA/MB → Reg I laundering | 0 rows classified `TARGET_COMPATIBLE` in Track A (0b) |
| Track C: `formatid_filter_precision` | ≥ 95% (smoke sample matches intended VGC 2025/2026 filter) |
| Track C: `license_status` | Not required for technical smoke PASS; **required** `license_review: approved` for any BC downstream |

**NO-GO** does not block the accuracy-default-on strength measurement. It only blocks downstream
human-data use until gaps are addressed.

## 7. Downstream implications (post-audit, out of scope here)

| Use case | Tracks A/B | Track C (lower trust) |
|----------|------------|----------------------|
| Behavior cloning / human policy prior | B (0c PASS) → `data/research/` | Only after 0d PASS **+ license review**; never substitute for B |
| Parser / protocol stress test | A (0b) sufficient | 0d sufficient; good for volume/format edge cases |
| Format mining / coverage discovery | Limited (MA/MB or Reg I only) | Primary Track C strength |
| Large VGC samples | B archive for curated Reg I | Candidate pool only; verify OTS/reg per row |
| Generalization panel v2 | MA/MB OOD (A) or Reg I (B) | Optional OOD supplement; separate `format_id` |
| Value head | Observational only — no counterfactual proof | Same; bulk data does not fix causal gap |

## 8. Manifest contract

Each phase writes `sample-manifest.json` via `build_sample_manifest` (or parallel schema for
Track C) with overrides.

**Track A (0a / 0b):** `source: cameronangliss/vgc-battle-logs`, `format_filter:
gen9vgc2025regma|gen9vgc2025regmb`, `license: MIT`, `purpose: import_audit_only`.

**Track B (0c):** `source: cameronangliss/vgc-battle-logs-sv`, `format_filter: gen9vgc2025regi`,
`phase: "0c"`.

**Track C (0d):**

```json
{
  "purpose": "import_audit_only",
  "source": "HolidayOugi/pokemon-showdown-replays",
  "source_revision": "<hf-revision-or-null>",
  "dataset_file": "phase-0d-smoke.parquet",
  "dataset_file_sha256": "<sha256-of-local-slice>",
  "format_filter": "vgc-2025|vgc-2026",
  "sample_size": 50,
  "license": "<from-dataset-card>",
  "license_status": "verified|unclear|missing",
  "license_review": "deferred",
  "trust_level": "lower",
  "phase": "0d",
  "created_at": "<injected-iso8601>",
  "git_sha": "<audit-runner-commit>"
}
```

Local raw/Parquet slices referenced by hash only; never committed.

## 9. Implementation notes (minimal code surface)

Expected new surface (bounded):

1. **Download helper** — streaming subset from HF (`huggingface_hub`), writing only to `raw/` local path.
2. **Parquet row adapter (Track C only)** — map `id`, `format`, `formatid`, `log`, `rating`,
   `uploadtime` → audit row; no full dataset scan.
3. **Audit runner** — per-track iteration, Part A parsers + reconstruction + legality checks.
4. **Report writer** — deterministic JSON + Markdown (mirror `learning/audit/report.py` style).

Tests: hand-trimmed fixtures (≤5 battles/rows) under `research/vgc_bench_import_audit/fixtures/`;
live-path import guard unchanged.

## 10. Execution order relative to other work

```
[parallel, isolated]  accuracy-default-on-devstrength-ab  (data/eval/accuracy-default-on/)
                      → clean worktree only

[sequential, Track A/B]  0a (VGC-Bench active, 20–50)
                      → 0b (VGC-Bench active, 200)
                      → 0c (VGC-Bench archive Reg-I, 200, explicit approval)

[optional, Track C]      0d (HolidayOugi VGC 2025/2026, 20–50)
                      → independent timing; never blocks A/B
                      → data/research/vgc-bench-import-audit/showdown-replays/ only
```

No shared artefacts, no shared seeds, no shared manifests. PROPOSED → APPROVED and per-phase
PASS/NO-GO (plus Track C license review for BC) precede any Part B implementation.

## 11. Deliverables

| Path | Commit? |
|------|---------|
| `docs/projects/evaluation/audits/2026-07-14-vgc-battle-logs-import-audit.md` | Yes (this spec, PROPOSED) |
| `data/research/vgc-bench-import-audit/*/sample-manifest.json` | Yes (after execution) |
| `data/research/vgc-bench-import-audit/*/reports/*.json` | Yes (after execution) |
| `data/research/vgc-bench-import-audit/*/reports/*.md` | Yes (after execution) |
| `data/research/vgc-bench-import-audit/*/raw/*` | **No** (local/gitignored) |
| `data/eval/accuracy-default-on/**` | Untouched by this slice |

**Summary:** Three-track fail-closed import audit — A: VGC-Bench active (0a smoke, 0b stratified);
B: VGC-Bench archive Reg-I (0c, explicit approval); C: HolidayOugi Showdown Replays (0d optional
smoke, **lower trust**, not a VGC-Bench replacement). Strict isolation from accuracy-default-on
strength gate; no large raw commits; Go/No-Go + Track C license review before downstream human-data
use.
