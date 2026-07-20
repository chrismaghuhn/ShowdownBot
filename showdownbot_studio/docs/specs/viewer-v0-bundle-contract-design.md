# ShowdownBot Studio Viewer v0 — Bundle and Exporter Contract

**Status:** APPROVED — implementation planning allowed; implementation not started.
**Amendment A (2026-07-21):** §14.1 synthetic-coherent fixture exception, including `git_sha:
"unknown"` → bundle `dirty: null` (§8.4 honesty). Schema 1.0 bytes contract otherwise unchanged.
**Date:** 2026-07-16
**Applies to:** viewer bundle schema 1.0 and the Python exporter that produces it
**Slice spec:** [`viewer-v0-design.md`](viewer-v0-design.md)
**Master spec:** [`../MASTER_SPEC.md`](../MASTER_SPEC.md)
**Boundaries:** [`../architecture/PROJECT_BOUNDARIES.md`](../architecture/PROJECT_BOUNDARIES.md)
**UI decision:** [`../decisions/ADR-001-godot-ui-technology.md`](../decisions/ADR-001-godot-ui-technology.md)
**Design input:** [`../design/viewer-v0-mockups/README.md`](../design/viewer-v0-mockups/README.md)
**License/privacy gate:** [`../research/2026-07-license-data-audit.md`](../research/2026-07-license-data-audit.md)

## 1. Purpose and non-goals

### 1.1 Purpose

[`viewer-v0-design.md`](viewer-v0-design.md) §5.2 declares a bundle manifest and calls its logical
names binding for schema 1.0. It does not establish which of those fields a real producer can
actually emit. This spec closes that gap. It audits the repository's real trace, result, manifest,
and log producers and pins the exporter contract to what those producers demonstrably write.

This document is the authority for:

- which bundle files exist and what each contains;
- the manifest shape, versioning, and capability rules;
- canonical serialization and the float policy;
- the hash and provenance contract, including its fail-open sources;
- which fields are mandatory, optional, degraded, or absent;
- privacy transformations the exporter must perform;
- the fail-closed error matrix;
- the fixture catalogue and acceptance gates for a later implementation plan.

### 1.2 Non-goals

This spec does not:

- authorize Godot code, Python production code, or fixtures. Implementation **planning** is
  authorized by this spec's status; writing any of the artifacts it plans is not. The plan is a
  separate reviewed deliverable, and no code or fixture may be produced until that plan is approved
  in its own right;
- change bot behaviour, trace production, or any artifact under `showdown_bot/`, `config/eval/`,
  `data/eval/`, or `reports/`;
- define the live-spectator, analyzer, plugin, or external-bot contracts;
- define a ZIP or other transport archive;
- make any strength, safety, or correctness claim about the bot;
- re-open the product decisions already fixed in [`../MASTER_SPEC.md`](../MASTER_SPEC.md) and
  [`viewer-v0-design.md`](viewer-v0-design.md).

Where this spec contradicts an earlier document, §2.7 records the contradiction and its evidence.
No earlier decision is silently overridden.

## 2. Audit of the real current state

Every claim below was verified by reading the cited code or committed artifact at
`origin/main` = `b0513f9`. Line numbers refer to that commit.

### 2.1 There are two different things called "DecisionTrace"

| | In-memory DTO | On-disk JSONL row |
|---|---|---|
| Type | `@dataclass DecisionTrace` | plain `dict` |
| Defined | `showdown_bot/src/showdown_bot/battle/decision_trace.py:117` | built by `build_trace_row`, `showdown_bot/src/showdown_bot/eval/decision_capture.py:592` |
| Version field | none | `trace_schema_version` |
| Validator | none | `validate_trace_row`, `decision_capture.py:561` |

The row is a **lossy projection** of the DTO. The exporter can only ever see the row. This
distinction is load-bearing for §10: several fields the mockups display exist on the DTO and never
reach disk.

### 2.2 The real trace row — exactly 26 keys

`build_trace_row` (`decision_capture.py:631-660`) writes exactly these keys, confirmed against the
real committed row in `data/eval/champions-panel-v0/smoke-i7a-mega/decision_trace.jsonl`:

`trace_schema_version`, `battle_id`, `seed_index`, `decision_index`, `turn_number`, `our_side`,
`config_id`, `config_hash`, `schedule_hash`, `format_id`, `git_sha`, `observable_state_hash`,
`request_hash`, `decision_phase`, `state_summary`, `actual_choose_string`, `normalized_action`,
`chosen_candidate_id`, `chosen_candidate_key`, `chosen_tera_slot`, `chosen_mega_slot`,
`chosen_rank`, `candidates`, `selection_stage`, `fallback_reason`, `decision_latency_ms`.

Each candidate carries exactly four keys (`decision_capture.py:621-629`): `candidate_id`,
`candidate_key`, `rank`, `aggregate_score`.

`validate_trace_row` is **closed-world** (`decision_capture.py:570-573`): any key outside the
required and version-nullable sets raises. Adding a field to the row is therefore a breaking
producer change, not an additive one.

### 2.3 Supported trace versions

`decision_capture.py:21-27`:

```python
TRACE_SCHEMA_VERSION_V1 = "decision-trace-v1"
TRACE_SCHEMA_VERSION_V2 = "decision-trace-v2"
TRACE_SCHEMA_VERSION_V3 = "decision-trace-v3"
TRACE_SCHEMA_VERSION = TRACE_SCHEMA_VERSION_V3
SUPPORTED_TRACE_SCHEMA_VERSIONS = frozenset({
    TRACE_SCHEMA_VERSION_V1, TRACE_SCHEMA_VERSION_V2, TRACE_SCHEMA_VERSION_V3,
})
```

All new writes are v3. All three versions remain readable by the bot. `chosen_candidate_key` is
nullable only on v2/v3 (`decision_capture.py:553-558`); a v1 row has no structural candidate key at
all. The candidate key carries its **own** integer `version` (1 or 2) inside its JSON payload
(`showdown_bot/src/showdown_bot/battle/candidate_identity.py:38`, `:56`) — this is not
`trace_schema_version`, and trace-v3 requires key-version 2 (`decision_capture.py:393`).

### 2.4 Fields that exist in memory but never reach disk

Verified absent from both `_REQUIRED_TRACE_FIELDS` (`decision_capture.py:544-558`) and
`build_trace_row`:

| DTO field | Defined | In trace row |
|---|---|---|
| `aggregation_mode` | `decision_trace.py:138` | no |
| `risk_lambda` | `decision_trace.py:139` | no |
| `must_react_lambda` | `decision_trace.py:140` | no |
| `score_vector` | `decision_trace.py:108` | no |
| `outcome_breakdowns` | `decision_trace.py:109` | no |
| `aggregate_breakdown` | `decision_trace.py:110` | no |
| `tempo_features` | `decision_trace.py:128` | no |
| `model_features` | `decision_trace.py:111` | no |
| `accuracy_details` | `decision_trace.py:112` | no |

This **confirms** [`viewer-v0-design.md`](viewer-v0-design.md) §6.5: the in-memory trace carries the
aggregation fields and the committed v3 row writer does not persist them.

### 2.5 The candidate set is partial and mode-dependent

`showdown_bot/src/showdown_bot/battle/decision.py:34` sets `TOP_K_TRACE_CANDIDATES = 6`.

- The non-Mega branch truncates: `scored[:TOP_K_TRACE_CANDIDATES]` (`decision.py:1165`).
- The Mega branch does not truncate: `for rank, rec in enumerate(ranked_records)` (`decision.py:966`),
  documented at `decision.py:860` as "no `TOP_K_TRACE_CANDIDATES` truncation".

The real committed Mega fixture bears this out — candidate counts per row are
`[0, 104, 45, 45, 2, 41, 41, 2, 5, 5, 5, 0, 104, 45, 45, 2, 41, 41, 1, 25]`. A single decision
carries **104** candidates.

Two consequences. The candidate table is never provably the complete considered set, and it is
unbounded in size, which independently confirms the bounded-rendering mandate in
[`../decisions/ADR-001-godot-ui-technology.md`](../decisions/ADR-001-godot-ui-technology.md).

The row does not record whether truncation was applied. A count below 6 proves no truncation and a
count above 6 proves the non-truncating branch, but a count of exactly 6 is ambiguous. Completeness
is therefore not derivable — see §16.1.

### 2.6 Candidate identity resolves structurally and fails closed

`resolve_chosen_candidate` (`candidate_identity.py:127-165`) matches `chosen_candidate_key` exactly
and raises `ChosenCandidateResolutionError` on zero or multiple matches. It never first-matches.
`assert_unique_candidate_identities` (`candidate_identity.py:108-117`) rejects duplicate identities
before the row is built. The key is canonical JSON and its canonicality is re-verified on read
(`decision_capture.py:384-388`).

A real key, verbatim from the committed fixture:

```text
{"slots":[{"kind":"move","mega_evolve":false,"move_index":2,"target":2,"target_ident":null,"terastallize":false},{"kind":"move","mega_evolve":true,"move_index":2,"target":2,"target_ident":null,"terastallize":false}],"version":2}
```

Two overlay asymmetries are load-bearing. `chosen_candidate_key` is always the **pre-Tera** key,
with the Tera overlay recorded separately in `chosen_tera_slot`. Mega is the opposite: Mega
candidates keep their full key with `mega_evolve` in place (`decision_capture.py:440-442`).

### 2.7 Contradictions found against the approved documents

Each is stated with evidence. None is resolved by preference.

**(a) The mockups README overstates the missing data.**
[`../design/viewer-v0-mockups/README.md`](../design/viewer-v0-mockups/README.md) §3 lists "decision
latency", "structured fallback reason", and "`selection_stage` vocabulary" as design placeholders
with no contract. In fact:

- `decision_latency_ms` is a **required** row field (`decision_capture.py:548`), validated finite
  (`decision_capture.py:582-583`), measured at
  `showdown_bot/src/showdown_bot/client/gauntlet.py:583`. The real fixture carries
  `0.08520000119460747`.
- `fallback_reason` is persisted (`decision_capture.py:657-658`) with real literal values including
  `heuristic_timeout`, `heuristic_error`, `max_damage_error`, `agent_exception`,
  `reranker_schema_mismatch`, `reranker_exception`.
- `selection_stage` is persisted (`decision_capture.py:655-656`) with real literal values including
  `team_preview`, `heuristic`, `max_damage_fallback`, `deterministic_default_pair`, `server_default`,
  `reranker_override`.

The README is right about the qualifiers and wrong about the fields. There is no *structured*
fallback object — it is a flat nullable string. There is no closed `selection_stage` *vocabulary* —
`validate_trace_row` enum-checks only `decision_phase` (`decision_capture.py:574`), so both strings
are open sets a viewer must not exhaustively switch on. This spec treats latency as mandatory
(§10) and the two vocabularies as open.

**(b) `decision_index` alone does not identify a decision.**
[`viewer-v0-design.md`](viewer-v0-design.md) §5.3 states "`decision_index` must be unique within the
battle". The writer's enforced uniqueness key is the **triple**
`(battle_id, decision_index, our_side)` (`decision_capture.py:685-687`). Within a single side the
design's claim holds, but it is not what the producer guarantees. The deep link
`--decision <battle_id>:<decision_index>` (§3.2) is ambiguous if a bundle ever contains more than one
side. §11.2 resolves this by pinning `our_side` per bundle and validating it.

**(c) The dossier's rank claim is inverted for the trace row.**
The dossier states rank is a derived sort position rather than a stored field. `rank` **is** stored
on `CandidateTrace` (`decision_trace.py:106`) and in the row (`decision_capture.py:625`). The
dossier's claim is true of the separate agg-trace schema, not of the trace row.

**(d) `sha256.txt` is not a verification mechanism.**
Committed `sha256.txt` files exist under `data/eval/`. No Python file in the repository reads them —
there is no writer and no verifier. They are hand-produced. They cannot be cited as fail-closed
hashing, and the bundle contract must not model itself on them.

**(e) Provenance has a real fail-open.**
`showdown_bot/src/showdown_bot/learning/provenance.py:18-28`:

```python
def git_sha_and_dirty() -> tuple[str, bool]:
    """Current commit + dirty flag; ('unknown', False) if git is unavailable.
    Call ONCE at run start (not per decision)."""
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                             check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], capture_output=True,
                                    text=True).stdout.strip())
        return sha or "unknown", dirty
    except Exception:  # noqa: BLE001
        return "unknown", False
```

On any failure this records `dirty=False` — it claims **clean**. [`viewer-v0-design.md`](viewer-v0-design.md)
§8 requires the viewer to never hide dirty provenance; a source that silently reports clean defeats
that. §8.4 makes `dirty` tri-state to close this.

**(f) Bundle byte-identity and source reproducibility are different claims.**
`run_id` is `sha1(canonical([seed_base, schedule_hash, config_hash, start_ts]))[:16]`
(`showdown_bot/src/showdown_bot/eval/run_manifest.py:110-113`), and its own module docstring states
"`start_ts` is captured once per run — so repeating a run yields a new `run_id`". Result rows and
run manifests are therefore **not** byte-reproducible across runs. This does not contradict
[`viewer-v0-design.md`](viewer-v0-design.md) §9.1, which requires two exports of one **frozen**
input to be byte-identical. §7.4 keeps those claims separate and excludes the non-deterministic
source fields from the bundle.

### 2.8 Real committed artifacts used as evidence

| Artifact | Use |
|---|---|
| `data/eval/champions-panel-v0/smoke-i7a-mega/decision_trace.jsonl` | 20 real trace-v3 rows; all three decision phases; candidate counts 0–104 |
| `data/eval/champions-panel-v0/smoke-i7a-mega/results.jsonl.config-manifest.json` | the committed `config_hash` pre-image |
| `data/eval/2b4/determinism/run1/results.jsonl.manifest.json` | a real run manifest |
| `data/eval/kaggle-validation/room_raw/` | real gzipped room logs with real protocol lines |

## 3. Source-to-presentation data flow

```text
showdown_bot artifacts (frozen, never modified)
  decision_trace.jsonl   trace-v1/v2/v3 rows      decision_capture.py:592
  room_raw/*.log[.gz]    verbatim protocol lines  room_dump.py:97
  results.jsonl          battle result rows       result_jsonl.py:101
  *.manifest.json        run provenance           run_manifest.py:155
  *.config-manifest.json config_hash pre-image    config_manifest_freeze.py
                  |
                  v
Studio Python exporter
  1. read + validate source rows against their own producer contracts
  2. reject unsupported/ambiguous/non-finite input (fail closed, §13)
  3. normalize legacy trace versions to one presentation shape
  4. apply the privacy transformation (§12) - drops raw bytes and identities
  5. derive presentation-only navigation values (§10.4)
  6. serialize canonically (§7) and hash every emitted file (§8)
                  |
                  v
viewer bundle directory (canonical, self-describing, offline)
                  |
                  v
Godot viewer (read-only presentation DTOs)
```

The exporter **re-serializes**; it never copies source bytes into the bundle. Source bytes are
recorded only as `source_hashes` (§8.2). Source artifacts are read-only, per
[`../architecture/PROJECT_BOUNDARIES.md`](../architecture/PROJECT_BOUNDARIES.md) §3 and
[`../research/2026-07-license-data-audit.md`](../research/2026-07-license-data-audit.md) §4.1.

## 4. Bundle directory structure

The bundle is a directory. It is not an archive. This follows
[`../architecture/PROJECT_BOUNDARIES.md`](../architecture/PROJECT_BOUNDARIES.md) §3 ("The bundle is a
canonical directory with no archive timestamps or export-time metadata") and
[`viewer-v0-design.md`](viewer-v0-design.md) §5.2. The audit found no evidence against it: an
archive would add container metadata and a compression level to the byte-identity claim without
serving any v0 requirement. The direction is kept.

```text
<bundle-root>/
  manifest.json          required   bundle identity, versions, capabilities, files, provenance
  battle.jsonl           required   normalized battle events, one JSON object per line
  decisions.jsonl        required   presentation decision rows, one JSON object per line
  warnings.json          optional   exporter-emitted bundle/degradation warnings
  config-manifest.json   optional   the committed config_hash pre-image
```

Rules:

- every path in `manifest.json` is bundle-relative, contains no `..` segment, no drive letter, and no
  leading separator;
- the directory contains no file not listed in `manifest.files`, and no subdirectories in schema 1.0;
- no sprites, fonts, images, HTML, or executable payload of any kind;
- no network reference; no URL field exists anywhere in the bundle;
- `manifest.json` is the only file excluded from the per-file hash rule, because self-hashing is
  recursive ([`viewer-v0-design.md`](viewer-v0-design.md) §5.2).

The logical keys `battle_log`, `decision_trace`, and `warnings` are fixed by
[`viewer-v0-design.md`](viewer-v0-design.md) §5.2 and are reused unchanged. `config_manifest` is a
new **optional** key, which §5.2 permits ("may add optional entries"). It exists so a reviewer can
read the real config pre-image instead of trying to interpret a hash — see §8.5.

## 5. Complete manifest example

The digests below are illustrative: the exporter computes each one from the bytes it writes. The
example is otherwise real. `battle_id`, `format_id`, `config_hash`, `git_sha`, `our_side`,
`config_id`, and `schedule_hash` are the true recorded values of the committed fixture
`data/eval/champions-panel-v0/smoke-i7a-mega/decision_trace.jsonl`, and
`source_hashes.decision_trace` is that file's real SHA-256.

```json
{
  "battle_id": "3e6a178b0900195e",
  "config_hash": "e137fce925f25bd8",
  "exporter": {
    "name": "showdownbot-studio-exporter",
    "version": "0.1.0"
  },
  "files": {
    "battle_log": {
      "path": "battle.jsonl",
      "present": true,
      "required": true,
      "sha256": "3b1f2c0a5d8e47b96af0c1d2e3f405162738495a6b7c8d9e0f1a2b3c4d5e6f70"
    },
    "config_manifest": {
      "path": "config-manifest.json",
      "present": true,
      "required": false,
      "sha256": "9c8b7a6950413e2d1c0b9a8877665544332211ffeeddccbbaa99887766554433"
    },
    "decision_trace": {
      "path": "decisions.jsonl",
      "present": true,
      "required": true,
      "sha256": "5e4d3c2b1a09f8e7d6c5b4a3928170695847362514039a8b7c6d5e4f3a2b1c0d"
    },
    "warnings": {
      "path": "warnings.json",
      "present": true,
      "required": false,
      "sha256": "0a1b2c3d4e5f60718293a4b5c6d7e8f9012345678998765432100fedcba98765"
    }
  },
  "format_id": "gen9championsvgc2026regma",
  "git_sha": "5690de75a4f7bc627b8d4be4fddb2074c6b586fc",
  "privacy": {
    "chat": "excluded",
    "player_names": "seat-pseudonyms",
    "private_messages": "excluded",
    "profile": "portable-pseudonymous-v1",
    "raw_source_included": false,
    "source_url": "excluded"
  },
  "required_capabilities": [],
  "source_hashes": {
    "battle_log": "6cbe5079bcd2522bc76f8d9563f4fb8ca0703fdb630b9a00525ccb99f6759285",
    "decision_trace": "7070338b77425621b6c3720e1f5cea651dff832dc6a0a8884de047c6647ff197"
  },
  "source_provenance": {
    "config_id": "heuristic",
    "dirty": false,
    "our_side": "p1",
    "schedule_hash": "1638a2d9034eb0f3",
    "seed_index": 0,
    "server_patch_hash": "86e31891547e87da",
    "showdown_commit": "f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5"
  },
  "trace_schema_version": "decision-trace-v3",
  "viewer_bundle_schema": {
    "major": 1,
    "minor": 0
  }
}
```

The example satisfies its own contract: keys are sorted, every logical key in `files` names a
distinct bundle-relative path with its own distinct digest, every declared file is `present: true`,
`exporter.version` is present, there is no wall-clock value, no absolute path, no URL, and no
`created_at`.

`source_provenance` is the additive optional object introduced by this spec. `git_sha` and
`config_hash` stay at the top level because [`viewer-v0-design.md`](viewer-v0-design.md) §5.2 binds
them there; `source_provenance` carries only the source-run fields that document has no slot for.
Every one of its keys has a real producer: `config_id`, `our_side`, `schedule_hash`, and `seed_index`
come from the trace row (`decision_capture.py:637-641`); `dirty`, `showdown_commit`, and
`server_patch_hash` come from the run manifest (`run_manifest.py:144-151`).

## 6. Versioning and capability rules

These follow [`../MASTER_SPEC.md`](../MASTER_SPEC.md) §3.3 and are restated here as the bundle's
binding form.

- `viewer_bundle_schema.major` and `.minor` are integers, never strings.
- **Unknown major → refuse.** The reader names the majors it supports.
- **Higher minor, same major → open only if** every entry in `required_capabilities` is known **and**
  every required field validates. A minor bump may only add optional fields or optional capabilities.
  It may never change the meaning, type, or nullability of an existing field, and may never add a
  required field.
- **Unknown entry in `required_capabilities` → refuse**, naming the unsupported capability.
- Unknown *optional* fields on a supported major are preserved for raw display and never
  reinterpreted ([`viewer-v0-design.md`](viewer-v0-design.md) §7).
- `trace_schema_version` is versioned **independently** of `viewer_bundle_schema`. The bundle
  declares the source trace version it was built from; the reader must not infer one from the other.
- `exporter.version` is informational provenance. It must never gate parsing — two exporter versions
  emitting the same bundle schema are interchangeable to the reader.

Schema 1.0 defines `required_capabilities: []`. Capability names are reserved, not implemented:
a future bundle that carries belief data would declare `belief_v2`, which a schema-1.0 reader does
not know and must therefore refuse. That refusal is the intended behaviour and is exactly what the
dossier illustrates.

**No data may be derived from `config_hash`.** It is a SHA-1 digest truncated to its first 16 hex
characters (`showdown_bot/src/showdown_bot/eval/result_jsonl.py:61-69`) — 64 retained bits over a
purpose-built subset manifest, not the whole config. It is an identity tag only. No reverse-lookup
table exists in the repository, and none may be added to Studio. Where the config is genuinely
needed, ship the pre-image (§8.5).

## 7. Canonical serialization

### 7.1 The profile

Every JSON document and every JSONL record in the bundle uses:

- UTF-8, no BOM;
- **RFC 8785 JSON Canonicalization Scheme (JCS)** for object member ordering, string escaping, and
  number formatting;
- no insignificant whitespace;
- exactly one JCS record per JSONL line, each line terminated by a single `\n`, including the last
  line; no `\r`; no blank lines;
- no `NaN`, `Infinity`, or `-Infinity` anywhere;
- record order defined per file by §7.5, never by filesystem enumeration;
- no `created_at`, export timestamp, host name, absolute path, or user name.

This keeps [`viewer-v0-design.md`](viewer-v0-design.md) §5.2.1 unchanged. RFC 8785 is a real
interoperable standard, which matters because the writer is Python and the reader is GDScript.

### 7.2 The producers are not JCS — this is measured, not assumed

The repository's canonical helper (`decision_capture.py:46-47`) is:

```python
def _canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
```

Measured divergences from JCS:

| Case | Producer emits | JCS requires |
|---|---|---|
| integral float `1.0` | `{"aggregate_score":1.0}` | `{"aggregate_score":1}` |
| negative zero `-0.0` | `{"x":-0.0}` | `{"x":0}` |
| `float('inf')` | `{"x":Infinity}` | forbidden; also invalid JSON |
| `float('nan')` | `{"x":NaN}` | forbidden; also invalid JSON |

The helper does not pass `allow_nan=False`, so a non-finite value serializes to invalid JSON
silently. The row validators check finiteness for `aggregate_score` (`decision_capture.py:540-541`)
and `decision_latency_ms` (`decision_capture.py:582-583`), but not for every nested numeric.

There is also a divergence **between producers**: `result_jsonl.py:97-98` omits
`ensure_ascii=False`, so the same logical string is written two different ways across artifacts.
Measured, for the input `{"team": "Flutter Maneé"}`:

| Producer | kwargs | Emitted bytes |
|---|---|---|
| `decision_capture.py:46-47` (trace rows) | `ensure_ascii=False` | `{"team":"Flutter Maneé"}` |
| `result_jsonl.py:97-98` (result rows) | `ensure_ascii` defaults to `True` | `{"team":"Flutter Mane\u00e9"}` |

The two rows are not the same bytes: the trace row emits the raw two-byte UTF-8 character `é`,
the result row emits the six-ASCII-character escape `\u00e9`. JCS mandates the first form.
Because §11.1.3 lets a bundle read the same provenance field from either artifact, the exporter must
compare **decoded strings**, never raw bytes, when cross-checking a field both sources carry.

The real committed fixture contains **no** integral-float byte pattern, so the float divergence is
latent rather than currently triggered. It is still a correctness requirement: the exporter must not
inherit it.

### 7.3 Consequences the exporter must honour

1. **Re-serialize, never copy.** Source bytes are Python-canonical and must not be pasted into a
   JCS document.
2. **`candidate_key` is an opaque string.** It is a JSON *string value* whose bytes are byte-pinned
   by the producer, which re-serializes and byte-compares it on read
   (`decision_capture.py:384-388`). The exporter must carry it through verbatim, as a string. It
   must never parse and re-emit its inner JSON — that would rewrite `1.0` to `1` inside the key and
   destroy candidate identity. JCS string escaping applies to the outer string, which is safe and
   lossless.
3. **Reject non-finite input at export.** Any `NaN` or infinity found in a source row fails the
   export closed (§13). JCS cannot represent them and the producer can emit them.
4. **Never re-hash a source with the bundle's serializer.** `source_hashes` are digests of the
   original bytes (§8.2); a JCS re-serialization would not reproduce them.

### 7.4 Float policy

- All numbers are JSON numbers; no numeric is ever stringified.
- Non-finite values are rejected at export, never emitted, never coerced to `null` or `0`.
- Recorded floats are carried at full `float64` precision and are never rounded, truncated, or
  reformatted for display. Rounding is a Godot presentation concern and must not enter the bundle.
- Numbers are formatted per JCS, which is shortest round-trip. A value read back as `float64`
  equals the recorded value exactly.
- The exporter must not "clean up" `-0.0`; JCS already normalizes it to `0`.

### 7.5 Record ordering

- `decisions.jsonl` is ordered by ascending `decision_index`. The order is total, because
  `decision_index` is unique per `(battle_id, our_side)` and `our_side` is pinned per bundle (§11.2).
- `battle.jsonl` preserves the source protocol order exactly. Protocol order is the evidence; it is
  never sorted, deduplicated, or reordered.
- `manifest.files` and all JSON objects are key-sorted by JCS; the `files` map is therefore
  deterministic regardless of the order in which the exporter happened to write the files.

### 7.6 Byte-identity claim, stated precisely

> Two exports of the **same frozen source artifacts** by the **same exporter version** produce the
> same relative file list and byte-identical file contents.

This is narrower than "re-running the battle reproduces the bundle", and deliberately so: §2.7(f)
shows the source pipeline is not byte-reproducible across runs. Anything that would import that
non-determinism into the bundle is excluded by §8.3.

## 8. Hash and provenance contract

### 8.1 Bundle file hashes

- Every entry in `manifest.files` with `present: true` carries `sha256`: the lowercase hex SHA-256
  of that file's exact bytes as written.
- An absent optional file is still declared, with `present: false`, `path: null`, `sha256: null`
  ([`viewer-v0-design.md`](viewer-v0-design.md) §5.2). Absence is declared, never inferred.
- `manifest.json` itself is not hashed in `files`.

### 8.2 Source hashes

`source_hashes` describe the **source artifacts**, computed over their original on-disk bytes.
`files.*.sha256` describe the **exported bundle files**. They are different values over different
bytes and must never be compared to one another. The example in §5 shows this: the real source trace
digest `7070338b…` has no relationship to the emitted `decisions.jsonl` digest.

Where a source already carries its own digest the exporter records it rather than inventing one:
`decision_trace_sha256` (`decision_capture.py:704-707`, a SHA-256 over the concatenated raw trace
line bytes) and `normalized_room_log_sha256` (a full SHA-256, validated as `[0-9a-f]{64}` at
`result_jsonl.py:93`).

### 8.3 Fields excluded from the bundle

Excluded because they are non-deterministic, machine-local, or identifying. Each is a real,
verified value in a committed artifact:

| Field | Source | Why excluded |
|---|---|---|
| `run_id` | `run_manifest.py:113` | derived from `start_ts`; changes every run |
| `start_ts` | `run_manifest.py:141` | wall clock, microsecond precision |
| `cli_invocation` | `cli.py:146` (`list(sys.argv)`) | absolute machine paths and user name |
| `environment` | `run_manifest.py:151` | host OS build, interpreter and dep versions |
| `room_raw_path` | `gauntlet.py:960` | absolute machine path |
| `decision_latency_p95_ms` | `gauntlet.py:959` | run-level wall-clock aggregate |

Per-decision `decision_latency_ms` is **not** in this list. It is a recorded measurement frozen in
the source row, so re-exporting the same row twice yields identical bytes. It is evidence, not
export-time metadata, and §7.6 is not weakened by carrying it.

### 8.4 `dirty` is tri-state

Because `git_sha_and_dirty()` fails open (§2.7(e)), a boolean `dirty` cannot distinguish "verified
clean" from "git failed and we guessed clean". The bundle therefore encodes:

- `dirty: true` — the source recorded a dirty worktree;
- `dirty: false` — the source recorded a clean worktree **and** `git_sha` is a real 40-hex SHA;
- `dirty: null` — unknown. **Required** whenever `git_sha == "unknown"`, because the recorded
  `false` is not trustworthy in that case.

The viewer renders `null` as `dirty state not recorded`, never as clean. This satisfies
[`viewer-v0-design.md`](viewer-v0-design.md) §8 without asking the exporter to re-run git.

### 8.5 The config pre-image, not the hash

`config_hash` is opaque (§6). The repository already commits its pre-image beside the results, e.g.
`data/eval/champions-panel-v0/smoke-i7a-mega/results.jsonl.config-manifest.json`:

```json
{
  "config_hash": "e137fce925f25bd8",
  "manifest": {
    "agent": "heuristic",
    "calc_pin_hash": "79a4877538c8740f",
    "env": {},
    "format_config_hash": "cb7a785e79283ffa",
    "format_id": "gen9championsvgc2026regma",
    "itemdata_hash": "c5b00bfb5f093e98",
    "movedata_hash": "099f6716ac48c5a8",
    "priors_hash": "62ab845d0dd64ff4",
    "speciesdata_hash": "b6e121e58c592056",
    "spreads_hash": "ba6488a6d05a9975"
  }
}
```

When that sidecar exists the exporter copies it to the optional `config_manifest` file and verifies
`manifest.config_hash` equals the row `config_hash`; a mismatch fails closed. When it is absent the
optional file is declared `present: false` and the viewer shows the hash alone. `env: {}` in the real
sidecar is itself evidence that credential variables are excluded upstream (§12.4).

### 8.6 Fail-closed verification

On open, in order, before any presentation:

1. `manifest.json` parses and validates structurally.
2. `viewer_bundle_schema.major` is supported, else refuse.
3. Every `required_capabilities` entry is known, else refuse naming it.
4. The `files` combination is legal per the §11.1.1 truth table, else refuse. This covers
   `required: true` with `present: false`, and a bundle carrying neither `battle_log` nor
   `decision_trace`.
5. Every `present: true` entry's file exists, else refuse naming it.
6. Every present file's recomputed SHA-256 equals its declared `sha256`, else refuse naming the
   mismatching file.
7. No file exists in the directory that is not declared in `files`, else refuse.
8. Field nullability matches the derived mode per §11.1.2, else refuse. A `trace_schema_version`
   that is `null` while `decision_trace` is present, or non-null while it is absent, is malformed.
9. When `decision_trace` is present, `trace_schema_version` is one the exporter normalized from,
   else refuse trace inspection. When it is absent, `trace_schema_version` is `null` and this step
   does not apply.
10. Decision identities are unique (§11.2), else refuse decision synchronization.

Refuse means: do not enter trusted mode, state the reason, name the offending file or capability.
There is no "continue anyway" path and no partial-trust mode. A failure at any step is terminal for
the affected surface.

This is a genuinely new mechanism, not an adoption of the existing `sha256.txt` convention, which
has no reader (§2.7(d)). The fail-closed precedents this follows are the pinned-calc verifier
(`showdown_bot/src/showdown_bot/engine/calc/pin.py:39-45`) and `verify_embedded_data_hash`
(`showdown_bot/src/showdown_bot/engine/generated_data_hash.py:20-34`).

## 9. DTO boundaries

Godot receives versioned presentation DTOs and nothing else.

**Godot must never recompute or guess:**

- Pokémon mechanics of any kind — damage, accuracy, speed order, type effectiveness, priority;
- any score, aggregate score, score component, or ranking;
- beliefs, hypotheses, priors, or any `suspected` classification;
- the chosen candidate, by any means other than the recorded `candidate_key` (§11.4);
- a replay/decision join beyond the recorded `protocol_index` mapping (§11.3);
- whether the candidate set is complete (§2.5);
- an aggregation mode, `risk_lambda`, or `must_react_lambda` — and never from `config_hash`
  ([`../MASTER_SPEC.md`](../MASTER_SPEC.md) §6);
- a legacy trace migration — normalization is Python's, and Godot carries no migration code
  ([`viewer-v0-design.md`](viewer-v0-design.md) §9.1);
- whether malformed source material is recoverable — the exporter classifies, Godot obeys.

**Godot may compute:** layout, sort order, filtering, truncation for display, scaling, colours,
focus, and the mapping from a recorded enum to a label.

**Sorting never changes identity.** Candidate sorting and filtering may reorder rows for
presentation only. The chosen row is resolved by structural `candidate_key` under every sort mode,
and `rank` remains the recorded value regardless of display position
([`../design/viewer-v0-mockups/README.md`](../design/viewer-v0-mockups/README.md), "Additional
implementation clarification").

## 10. Field matrix: mandatory, optional, degraded, missing

Status values: **mandatory** — the key is always present and its value is never `null` in any mode.
**mode-dependent** — the key is always present, and whether the value may be `null` is fixed by the
§11.1.2 table; it is never omitted. **optional** — real producer, may be `null`; renders as
`not recorded`. **derived** — computed by the exporter from recorded data. **missing** — no producer;
DESIGN INPUT MISSING.

Every key in this section is always present. Only values vary. Nothing is ever omitted, and absence
is always declared (§11.1.2).

### 10.1 Manifest

Per-mode nullability is in §11.1.2; the source each field is resolved from, in precedence order, is
in §11.1.3. The "Real producer" column below names the **first** source only.

| Field | Status | Real producer |
|---|---|---|
| `viewer_bundle_schema.major` / `.minor` | mandatory | exporter constant |
| `required_capabilities` | mandatory | exporter constant (`[]` at 1.0) |
| `exporter.name` / `.version` | mandatory | exporter constant |
| `battle_id` | mandatory | trace row (`decision_capture.py:633`) or result row |
| `format_id` | mandatory | trace row (`decision_capture.py:641`) or result row |
| `git_sha` | mandatory | trace row (`decision_capture.py:642`) or result row / run manifest |
| `config_hash` | mandatory | trace row (`decision_capture.py:639`) or result row / run manifest |
| `trace_schema_version` | mode-dependent; `null` in replay-only | trace row (`decision_capture.py:632`) |
| `privacy.*` | mandatory | exporter constant, profile `portable-pseudonymous-v1` |
| `source_hashes.battle_log` | mode-dependent; `null` in trace-only | SHA-256 over source bytes |
| `source_hashes.decision_trace` | mode-dependent; `null` in replay-only | SHA-256 over source bytes |
| `files.*` | mandatory | exporter; legal combinations per §11.1.1 |
| `source_provenance.dirty` | mandatory, tri-state | result row / run manifest; `null` if `git_sha == "unknown"` or neither source is available (§8.4). **Not on the trace row** |
| `source_provenance.our_side` | mode-dependent; `null` in replay-only | trace row (`decision_capture.py:637`); absent from result rows |
| `source_provenance.config_id` | mandatory | trace row (`decision_capture.py:638`) or result row |
| `source_provenance.schedule_hash` | mandatory | trace row (`decision_capture.py:640`) or result row / run manifest |
| `source_provenance.seed_index` | mandatory | trace row (`decision_capture.py:634`) or result row |
| `source_provenance.showdown_commit` | optional | run manifest (`run_manifest.py:144`) |
| `source_provenance.server_patch_hash` | optional | run manifest (`run_manifest.py:148`) |

### 10.2 Decision row (`decisions.jsonl`)

| Field | Status | Real producer / note |
|---|---|---|
| `decision_index` | mandatory | `decision_capture.py:635` |
| `turn_number` | mandatory | `decision_capture.py:636`; locates, does not identify |
| `request_protocol_index` | derived; `null` in trace-only | joined from the raw log on `request_hash` (§11.3.2); `null` when no raw request matches or no log exists |
| `decision_phase` | mandatory | `decision_capture.py:645`; closed enum `team_preview` / `forced_replacement` / `regular_turn`, validated at `:574` |
| `decision_latency_ms` | mandatory | `decision_capture.py:659`; required and finite-checked at `:548`, `:582` |
| `observable_state_hash` | mandatory | `decision_capture.py:643`; 64-hex, validated `:579-581` |
| `request_hash` | mandatory | `decision_capture.py:644`; 64-hex |
| `state_summary` | mandatory, transformed | `decision_capture.py:646`; nickname stripped per §12.2 |
| `normalized_action` | mandatory | `decision_capture.py:648` |
| `actual_choose_string` | mandatory | `decision_capture.py:647` |
| `candidates[]` | mandatory, possibly empty | `decision_capture.py:654`; empty on team preview in the real fixture |
| `candidates[].candidate_key` | optional | `decision_capture.py:624`; `null` on trace-v1 |
| `candidates[].candidate_id` | mandatory | `decision_capture.py:623`; lossy label, never an identity |
| `candidates[].rank` | mandatory | `decision_capture.py:625`; recorded, not derived (§2.7(c)) |
| `candidates[].aggregate_score` | mandatory | `decision_capture.py:626`; finite-checked at `:540` |
| `chosen_candidate_key` | optional | `decision_capture.py:650`; absent on v1 |
| `chosen_candidate_id` | optional | `decision_capture.py:649` |
| `chosen_rank` | optional | `decision_capture.py:653` |
| `chosen_tera_slot` | optional | `decision_capture.py:651`; `null` or `0`/`1` |
| `chosen_mega_slot` | optional | `decision_capture.py:652`; mutually exclusive with Tera, enforced `:431` |
| `selection_stage` | optional, **open vocabulary** | `decision_capture.py:655`; not enum-validated |
| `fallback_reason` | optional, **open vocabulary** | `decision_capture.py:657`; flat string, not structured |
| `aggregation.mode` | **null at 1.0** + degradation | not persisted (§2.4); `null` is mandatory-with-warning per [`../MASTER_SPEC.md`](../MASTER_SPEC.md) §6 |
| `aggregation.risk_lambda` | **null at 1.0** | not persisted (§2.4) |
| `aggregation.must_react_lambda` | **null at 1.0** | not persisted (§2.4) |
| `score_vector` | missing | in-memory only (`decision_trace.py:108`) |
| `score_breakdown` | missing | `OutcomeBreakdown` in-memory only (`decision_trace.py:109-110`) |
| `beliefs` | missing | no field on DTO or row |
| `warnings` (per decision) | missing | no field on DTO or row |

The `aggregation` object is always present with all three keys, per
[`viewer-v0-design.md`](viewer-v0-design.md) §6.5. At schema 1.0 all three are `null` and the row
carries the degradation warning `aggregation_mode_not_recorded`. The viewer labels the score
`aggregation mode not recorded`. It must not infer the mode from `config_hash`.

### 10.3 Battle event row (`battle.jsonl`)

Derived from `LogEvent` (`showdown_bot/src/showdown_bot/engine/log_parser.py:75-86`).

| Field | Status | Note |
|---|---|---|
| `protocol_index` | mandatory | index of the source protocol line that produced this event (§11.3.1); sparse and strictly increasing, never renumbered |
| `type` | mandatory | `LogEvent.type` |
| `pokemon.side` / `.slot` | optional | from `PokemonId` |
| `pokemon.species` | optional | species details, not the nickname |
| `target.side` / `.slot` | optional | from `PokemonId` |
| `details` | optional | species details or move name |
| `hp.current` / `.maximum` / `.fainted` / `.status` | optional | from `HpStatus` |
| `value` | optional | weather / terrain / status / item / stat |
| `amount` | optional | boost stages, turn number |
| `side` | optional | `p1` / `p2` |
| `tags` | optional | trailing protocol tags |
| `raw` | **excluded** | `LogEvent.raw` is the verbatim protocol line — see §12.2 |
| `pokemon.name` | **excluded or pseudonymized** | this is the nickname — see §12.2 |

### 10.4 Exporter-derived navigation values

[`viewer-v0-design.md`](viewer-v0-design.md) §6.5 requires three navigation values that Godot does
not recompute.

| Field | Derivation | Degradation |
|---|---|---|
| `top1_top2_margin` | `candidates[0].aggregate_score - candidates[1].aggregate_score` on the rank-sorted set | `null` when fewer than two candidates; the real fixture has rows with 0, 1, and 2 |
| `fallback_used` | `fallback_reason is not null` | never null; `false` is a real answer |
| `warning_count` | count of this decision's entries in `warnings.json` | never null; `0` is a real answer |

`warning_count` counts **exporter-emitted** warnings. There is no bot-side per-decision warning
producer (§10.2), so it cannot mean anything else without inventing a source. v0 defines no
close-decision threshold and draws no score graph
([`viewer-v0-design.md`](viewer-v0-design.md) §6.5).

### 10.5 Information states

The dossier's four states map to real evidence as follows.

| State | Belastbar? | Real basis |
|---|---|---|
| `known` | yes | `state_summary` fields the bot actually observed; `item_known: true` (`decision_capture.py:64-65`) is a real per-item discriminator |
| `not recorded` | yes | an optional field that is `null`, or a declared absent optional file |
| `unknown` | partly | `item: null` with `item_known: false` is a real "not revealed". There is no general unknown marker for other fields |
| `suspected` | **no** | requires a belief snapshot. No producer exists (§2.4). DESIGN INPUT MISSING |

`suspected` must not be rendered at schema 1.0. The dossier's own compliance matrix already flags
the belief schema and the `suspected` source as open.

## 11. Replay and trace synchronization

### 11.1 The three supported modes

All three are honest, first-class modes. The bundle declares which one it is by which optional files
are present, never by inference from a parse failure.

The mode is **derived** from the `present` flags. It is not a stored field, because a stored mode
could disagree with the flags and there would be no rule for which one wins.

#### 11.1.1 File truth table

`required` in a `files` entry means "this bundle's mode requires this file". It is an assertion the
reader checks, not a constant.

**For the two mode-defining keys, `required` and `present` must be equal.** `battle_log` and
`decision_trace` are what *define* the mode: if a bundle carries one, that bundle's mode requires it;
if it does not carry it, that bundle's mode does not require it. There is no third state. A
`required: false, present: true` entry would assert "this bundle contains a file its own mode does
not require" — which no mode in §11.1.2 describes, and which would leave the reader with no rule for
what that file means or whether its absence would have mattered. It is refused.

The complete set of legal combinations for schema 1.0 is therefore exactly three:

| `battle_log` | `decision_trace` | Derived mode | Legal? |
|---|---|---|---|
| `required: true`, `present: true` | `required: true`, `present: true` | replay + trace | yes |
| `required: true`, `present: true` | `required: false`, `present: false` | replay-only | yes |
| `required: false`, `present: false` | `required: true`, `present: true` | trace-only | yes |
| `required: false`, `present: false` | `required: false`, `present: false` | none | **refuse** — a bundle must carry at least one |
| `required != present` on either key | any | none | **refuse** — malformed |

Invariants, checked in this order:

1. For `battle_log` and `decision_trace`: **`required == present`**. Every other combination —
   including `required: false, present: true` and `required: true, present: false` — is malformed →
   refuse.
2. For every other logical key: `required` is `false` at schema 1.0. `warnings` and `config_manifest`
   are optional in every mode, so `required: true` on either is malformed → refuse. Their `present`
   flag is free and may be `true` or `false`.
3. `present: false` implies `path: null` and `sha256: null`
   ([`viewer-v0-design.md`](viewer-v0-design.md) §5.2).
4. At least one of `battle_log` and `decision_trace` has `present: true` → else refuse.
5. A file whose logical key is `present: true` must exist on disk and match its `sha256` (§8.6).

The two key classes are deliberately asymmetric: for the mode keys the two flags are locked to each
other, while for the optional keys `required` is pinned to `false` and `present` varies freely. That
asymmetry is what makes the mode derivable from the manifest alone.

This is the one place this contract departs from [`viewer-v0-design.md`](viewer-v0-design.md) §5.2,
whose example marks both `battle_log` and `decision_trace` `required: true`. Those two flags cannot
both be unconditionally `true` while §7 of the same document mandates replay-only and trace-only
modes. Making `required` mode-dependent resolves the contradiction without renaming any logical key.

`warnings` and `config_manifest` are `required: false` in every mode and may be `present` either way.

#### 11.1.2 Field nullability per mode

Every manifest key is **always present**; only its value varies. A field is never omitted, mirroring
the "declare absence, never infer it" rule of [`viewer-v0-design.md`](viewer-v0-design.md) §5.2.

| Field | replay + trace | replay-only | trace-only |
|---|---|---|---|
| `battle_id` | value | value | value |
| `format_id` | value | value | value |
| `git_sha` | value | value | value |
| `config_hash` | value | value | value |
| `trace_schema_version` | value | **null** | value |
| `source_hashes.battle_log` | value | value | **null** |
| `source_hashes.decision_trace` | value | **null** | value |
| `source_provenance.our_side` | value | **null** | value |
| `source_provenance.config_id` | value | value | value |
| `source_provenance.schedule_hash` | value | value | value |
| `source_provenance.seed_index` | value | value | value |
| `source_provenance.dirty` | tri-state (§8.4) | tri-state | tri-state |
| `source_provenance.showdown_commit` | value or null | value or null | value or null |
| `source_provenance.server_patch_hash` | value or null | value or null | value or null |

`trace_schema_version: null` in replay-only is the honest encoding: there is no trace, so there is no
trace schema. A reader must not treat `null` as "some default version".

`our_side: null` in replay-only is forced by the producers: `our_side` exists on the trace row
(`decision_capture.py:637`) and **not** in `REQUIRED_FIELDS` or `NULLABLE_FIELDS` of the result row
(`result_jsonl.py:17-30`) — verified, it appears nowhere in that module. Nothing is lost: `our_side`
exists to pin decision identity (§11.2), and a replay-only bundle has no decisions to identify.

#### 11.1.3 Source precedence for the shared fields

Several fields have more than one real producer. That is what makes replay-only possible at all. The
exporter resolves each in this fixed order and records the first hit:

| Field | 1st source | 2nd source | 3rd source | If none |
|---|---|---|---|---|
| `battle_id` | trace row `:633` | result row `battle_id` | — | refuse |
| `format_id` | trace row `:641` | result row `format_id` | — | refuse |
| `git_sha` | trace row `:642` | result row `git_sha` | run manifest `git_sha` | refuse |
| `config_hash` | trace row `:639` | result row `config_hash` | run manifest `config_hash` | refuse |
| `config_id` | trace row `:638` | result row `config_id` | — | refuse |
| `schedule_hash` | trace row `:640` | result row `schedule_hash` | run manifest `schedule_hash` | refuse |
| `seed_index` | trace row `:634` | result row `seed_index` | — | refuse |
| `our_side` | trace row `:637` | — | — | `null` |
| `dirty` | result row `dirty` | run manifest `dirty` | — | `null` (§8.4) |
| `showdown_commit` | run manifest `:144` | — | — | `null` |
| `server_patch_hash` | run manifest `:148` | — | — | `null` |
| `trace_schema_version` | trace row `:632` | — | — | `null` |

Two rules govern this table:

- **Agreement is mandatory.** Where a field is available from more than one source, all available
  sources must agree; a disagreement refuses the export. This mirrors the existing `manifest_match`
  cross-check (`showdown_bot/src/showdown_bot/eval/report.py:469-475`), which already reconciles
  rows against the run manifest on `run_id`, `config_hash`, `schedule_hash`, `seed_base`,
  `panel_hash`, `git_sha`, and `dirty` — except that check is soft and this one is not.
  Comparison is on decoded strings, never raw bytes (§7.2).
- **`refuse` means the bundle cannot be built.** These fields identify the evidence; a bundle that
  cannot name its own battle, format, or config is not evidence.

`dirty` deserves its own note: it is **not** on the trace row (§2.2 lists all 26 keys). A trace-only
bundle with no accessible result row or run manifest therefore reports `dirty: null` — correctly
"unknown", never `false`, per §8.4.

trace-only is not a degraded replay. `battle.jsonl` is evidence, and a missing replay is never
simulated — [`../architecture/PROJECT_BOUNDARIES.md`](../architecture/PROJECT_BOUNDARIES.md) §7 is
explicit that a protocol log is structured evidence, not a resumable simulator snapshot.

### 11.2 Decision identity

The enforced producer key is the triple `(battle_id, decision_index, our_side)`
(`decision_capture.py:685-687`), not the pair assumed in
[`viewer-v0-design.md`](viewer-v0-design.md) §5.3.

Schema 1.0 therefore pins a bundle to **one battle and one side**:

- `manifest.battle_id` and `manifest.source_provenance.our_side` are single scalars;
- every row in `decisions.jsonl` must carry that same `battle_id` and `our_side`, else refuse;
- `decision_index` is then unique within the bundle, and the deep link
  `--decision <battle_id>:<decision_index>` ([`viewer-v0-design.md`](viewer-v0-design.md) §3.2) is
  unambiguous;
- a duplicate `decision_index` refuses decision synchronization.

Pinning the side is what makes the design's identity claim true rather than merely usually true. The
real fixture is single-side (`our_side: "p1"`; the producer default is `p1`,
`decision_capture.py:202`).

### 11.3 Joining events to decisions

`turn_number` **locates** a decision on the replay timeline; it does not identify one. It is not
unique: the real fixture shows `team_preview` at turn 0, and `forced_replacement` shares a turn with
the `regular_turn` that preceded it. Capture is per **request**, not per turn — `decision_index`
increments per write (`gauntlet.py:605`).

**A `|request|` is not a battle event.** `parse_log_line`
(`showdown_bot/src/showdown_bot/engine/log_parser.py:105-252`) branches only on battle-state
prefixes — `move`, `switch`, `turn`, `faint`, `-damage`, `-heal`, `-status`, `-weather`, `-mega`,
and their siblings — and returns `None` for every other prefix, including `request`. There is
therefore no `LogEvent` for a request, and a decision cannot point at "the event index of its
request": that index does not exist in the exported event stream. The join must be anchored in the
**raw protocol line space** instead.

#### 11.3.1 The index space

`protocol_index` is the 0-based index of a line in the raw source log's line sequence, defined
exactly as the existing offline replay defines it (`room_raw_replay.py:75-83`): read the log with
`read_room_log_frames(path)`, take `frames[0]`, split on `"\n"`, and enumerate. This space is the
**source** line sequence, not the exported event sequence.

Two fields carry it:

| Field | On | Type | Meaning |
|---|---|---|---|
| `protocol_index` | every row of `battle.jsonl` | int | index of the source protocol line that produced this event |
| `request_protocol_index` | every row of `decisions.jsonl` | int or null | `protocol_index` of the `\|request\|` line that produced this decision |

Rules:

- `protocol_index` is **sparse and strictly increasing** across `battle.jsonl`. Filtered lines — chat,
  `|player|`, `|j|`, `|t:|`, `|title|`, and every prefix `parse_log_line` does not handle — produce no
  row and simply leave a gap.
- It is **never renumbered or densified**. Renumbering would silently break the join and destroy the
  ability to say which source line an event came from. A gap is information, not a defect.
- It indexes the source log, so it is stable under the privacy transformation: §12.2 drops the
  *content* of identifying lines, never their *positions*.

#### 11.3.2 How the exporter derives `request_protocol_index`

The live trace row records no line index and no `log_prefix_hash`, so the index cannot be read off
the trace. It is recovered by joining the trace to the raw log on `request_hash`, which is the only
field that provably joins them. Both paths compute it with byte-identical recipes — live at
`decision_capture.py:46-51`, `:97`, `:131`; offline at `room_raw_replay.py:35-40`, `:119-121` — and
both reduce to
`sha256(json.dumps(request.model_dump(mode="json", by_alias=True, exclude_none=False), sort_keys=True, separators=(",",":"), ensure_ascii=False))`.
`rqid` is part of the request payload, so `request_hash` distinguishes two structurally identical
requests at different points in the battle. This equivalence is load-bearing and is undocumented in
`showdown_bot/`; a test must pin it (§15, gate 30).

The exporter walks the raw lines and, for each `|request|` line, mirroring
`room_raw_replay.py:88-100` exactly:

1. parses the payload;
2. **skips** it if its `rqid` was already seen — a reconnect resend, not a new decision;
3. **skips** it if `req.wait` is set — the opponent's turn, where nothing was chosen;
4. otherwise computes `request_hash` and records the line's index `i`.

Each surviving `(request_hash, i)` is matched against the trace rows:

| Matches | Behaviour |
|---|---|
| exactly one trace row | `request_protocol_index = i` |
| no trace row | that request produced no captured decision; no decision row is invented |
| more than one trace row | **refuse the export** — an ambiguous join must never be guessed |

A decision whose `request_hash` matches no raw request gets `request_protocol_index: null` and is
marked as having no replay event. It remains a distinct timeline entry
([`viewer-v0-design.md`](viewer-v0-design.md) §5.3, "decisions without a replay event all remain
distinct timeline entries"), is never dropped, and is never attached to a neighbouring turn.

In **trace-only** mode there is no log and therefore no index space: `request_protocol_index` is
`null` on every decision, and that is the mode's normal state rather than a degradation of the join.
In **replay-only** mode there are no decisions to join.

#### 11.3.3 What the viewer does with it

The viewer orders the timeline by `protocol_index` and places a decision immediately after the last
event whose `protocol_index` is less than that decision's `request_protocol_index` — the decision was
made on the state those events had already established. `turn_number` and `decision_phase` remain
display information. The viewer performs no other join and infers nothing from row adjacency.

### 11.4 Chosen-candidate integrity must be cross-checked

`resolve_chosen_candidate` fails closed (§2.6), but it validates the trace against itself. One real
path can desynchronize the trace from the action actually sent:
`showdown_bot/src/showdown_bot/learning/reranker_override.py:110-119` selects a different candidate,
re-encodes the `/choose` string, and sets only `selection_stage` and `fallback_reason` — it never
updates `chosen_candidate_key`, `chosen_candidate_id`, or `chosen_rank`. Under
`agent="heuristic_reranker"` the row's `chosen_*` fields describe the heuristic's pick while
`actual_choose_string` and `normalized_action` describe the reranker's. Default `agent="heuristic"`
runs are unaffected.

A viewer that trusted `chosen_candidate_key` alone would silently highlight the wrong row. The
checks below therefore run at **export**, and their outcome is refusal, not a marked-invalid row.

**An empty candidate set is legal and is not an error.** `build_trace_row` sets every `chosen_*`
field to `null` when `trace is None or not trace.candidates` (`decision_capture.py:603-609`), and
`chosen_candidate_key` is nullable on v2/v3 (`decision_capture.py:553-558`). In the real committed
v3 fixture **2 of 20 rows** have `chosen_candidate_key: null` — both `team_preview` with
`candidates: []`. Any rule that refuses on a null key would reject every legitimate team-preview
row. The rules are therefore scoped by version *and* by whether the candidate set is empty.

| Trace version | `candidates` | Rule at export |
|---|---|---|
| v3 / v2 | non-empty | `chosen_candidate_key` must be non-null and resolve to **exactly one** candidate; `chosen_rank` must equal that candidate's `rank`; the resolved candidate must agree with `normalized_action`. Any failure → **refuse the export** and name the decision |
| v3 / v2 | empty | `chosen_candidate_key`, `chosen_candidate_id`, and `chosen_rank` must all be `null`. The decision exports with an empty candidate set and no chosen row. A non-null `chosen_*` alongside an empty `candidates` is impossible for this producer → **refuse** |
| v1 | any | no validated structural candidate identity exists → **refuse trace export** (see below) |

Agreement with `normalized_action` compares kind, `move_index`, and target per slot, applying the
pre-Tera and full-Mega key conventions of §2.6.

**v1 is rejected, not migrated.** [`viewer-v0-design.md`](viewer-v0-design.md) §9.1 allows either a
deterministic Python migration or a rejection with a precise explanation. Rejection is the correct
branch here, on evidence: `_validate_v1_row` (`decision_capture.py:205-209`) checks only that
`aggregate_score` is finite, so a v1 row carries no validated `candidate_key`. Migrating would mean
resolving the chosen candidate through `chosen_candidate_id`, which is `_label_ja` output and is
**provably lossy** — every switch renders as the bare string `switch` regardless of its target
(`decision.py:276`), which is the documented reason the structural key exists at all, and a real
historical collision (`tests/test_gauntlet_dispatch.py:818`). A migration that can silently bind the
wrong candidate is not deterministic in the sense §9.1 requires.

A v1 source therefore yields no trace in the bundle. If a room log exists it may still be exported
as a **replay-only** bundle (§11.1); otherwise the export refuses. Godot holds no migration logic
either way.

These are bundle-integrity checks, not bot fixes; none of them modifies `showdown_bot/`.

## 12. Privacy and redaction rules

The binding profile is `portable-pseudonymous-v1`
([`../research/2026-07-license-data-audit.md`](../research/2026-07-license-data-audit.md) §4.2). It
is currently **specification text with zero implementation** — a repository-wide search for
`portable-pseudonymous`, `seat-pseudonym`, and `seat_pseudonym` finds no Python, JSON, or GDScript
producer. The exporter implements it; nothing exists to reuse.

### 12.1 What the real sources actually contain

Verbatim from the committed `data/eval/kaggle-validation/room_raw/`:

```text
>battle-gen9vgc2025regi-5
|init|battle
|title|HeuristicBot1410 vs. BaselineBot1410
|j|☆HeuristicBot1410
|t:|1783701531
|player|p1|HeuristicBot1410|266|
|request|{"teamPreview":true,"side":{"name":"HeuristicBot1410","id":"p1",
```

Present: player names, avatar ids (`266`), unix wall-clock (`|t:|`), names inside the `|request|`
JSON, and names in the **file name** itself (`HeuristicBot1410__battle-gen9vgc2025regi-5.log.gz`,
from `room_dump.py:101`). Chat lines and IPs are absent from this corpus, but the exclusion is a
contract, not an observation.

Verified from the **committed** manifest blob on `origin/main`
(`data/eval/champions-panel-v0/smoke-i5/results.jsonl.manifest.json`). The literal user name is
redacted here as `<user>` rather than reproduced, because copying it into a new document would
repeat the leak this section exists to prevent:

```text
cli_invocation[0]: "C:\\Users\\<user>\\Documents\\SHowdown BOt\\showdown_bot\\src\\showdown_bot\\cli.py"
environment.platform: "Windows-11-<build>-SP0"
start_ts:             "2026-07-14T19:13:26.516373+00:00"
```

The real blob carries the operating-system account name in place of `<user>` and the exact OS build
in place of `<build>`. A survey of tracked files under `data/` finds 21 committed artifacts
containing that account name, reachable via `cli_invocation` (`cli.py:146`), `room_raw_path`
(`gauntlet.py:960`), and `source_file` in the frozen `data/eval/accuracy-cap-derisk/` manifest.
This is the concrete reason §8.3 excludes `cli_invocation`, `environment`, and `room_raw_path`
rather than treating them as harmless provenance.

This spec does not propose changing those committed artifacts. They are frozen evidence, and §12.5
explains why rewriting them would break `decision_id` lineage. The contract's obligation is that
none of it reaches a bundle.

### 12.2 Required transformations

| Datum | Rule |
|---|---|
| Player display names, user IDs | replaced by seat labels `p1` / `p2`, consistently in **every** exported file |
| Names inside `|request|` payloads | same replacement; the payload is parsed, not regex-patched |
| `LogEvent.raw` | **dropped**; it is the verbatim protocol line and re-leaks names and `\|t:\|` |
| Pokémon nickname | dropped, or replaced by species. Present at `_pokemon_payload` (`decision_capture.py:57`, `"nickname": mon.nickname`) and as `PokemonId.name`. It is user-supplied free text |
| Avatar id | excluded; presentation-irrelevant identity metadata |
| `\|t:\|`, `\|inactive\|` | excluded; wall-clock |
| Chat, PM, join/leave, rename, `\|title\|`, HTML/UI frames | excluded |
| Source URL, raw HTML | excluded; no URL field exists in the bundle |
| Absolute paths (`cli_invocation`, `room_raw_path`, `source_file`) | excluded entirely |
| Host/OS/interpreter (`environment`) | excluded |
| Reversible name map | **never** written to the bundle |
| `winner` | taken from the result row, which already records `hero` / `villain` / `tie` (`result_jsonl.py:30`), never from `battle_parse`'s `winner_name`, which is a user name |

The seat mapping is deterministic and one-way. The bundle contains no artifact from which a display
name can be recovered.

### 12.3 Filtering happens at export, never in place

The source is never edited. The exporter reads it and writes a separate normalized artifact
([`../research/2026-07-license-data-audit.md`](../research/2026-07-license-data-audit.md) §4.1). The
untouched source stays in user-controlled local storage outside the bundle. `raw_source_included` is
`false` at schema 1.0, and no schema-1.0 bundle may set it `true`.

### 12.4 What is already safe upstream

`SHOWDOWN_USERNAME` and `SHOWDOWN_PASSWORD` are classified non-behavioural and the `SHOWDOWN_AUTH_`
prefix family is excluded (`showdown_bot/src/showdown_bot/eval/config_env.py:122-123`, `:131`), so
they never reach `config_hash` or a manifest. The committed config-manifest sidecar shows `"env": {}`
(§8.5), which is the empirical confirmation. The exporter still asserts that no bundle field matches
a credential-shaped key rather than relying on that upstream behaviour.

### 12.5 A redaction constraint the implementation must respect

Redacting the **persisted source logs** is out of scope and must not be attempted, because three
committed mechanisms depend on their exact bytes:

- `log_prefix_hash` hashes the raw log prefix including `|player|`, `|j|`, and `|t:|`
  (`room_raw_replay.py:102-103`, `:122`), and `decision_id` is built from it
  (`showdown_bot/src/showdown_bot/eval/accuracy_cap_derisk.py:33-37`). Rewriting the logs changes
  every `decision_id` and breaks the frozen 944-row manifest under `data/eval/accuracy-cap-derisk/`.
- `classify_room_log` resolves the hero side by regex-matching the user name
  (`showdown_bot/src/showdown_bot/analysis/generalisation/log_features.py:10-11`, `:92-95`);
  renaming collapses its features to `unavailable`.
- `winner` in `battle_parse` is a user name (`battle_parse.py:96-97`).

This is exactly why the profile filters at the export boundary. It also means the exporter must not
"helpfully" clean the source corpus.

### 12.6 Residual linkability — what this profile does not promise

`portable-pseudonymous-v1` is **pseudonymous**. It is not anonymous, and it does not make a bundle
unlinkable. The name is accurate, and the contract must not be read as promising more than it says.
The following linkage vectors survive the transformation **by design**. Each is a deliberate trade
against the product's purpose, which is verifiable evidence.

| Vector | Why it survives |
|---|---|
| `source_hashes.battle_log` / `.decision_trace` | Digests of the **original** source bytes (§8.2). Anyone holding the original artifact can recompute the digest and confirm the bundle derives from it. This is a known-plaintext linkage, and it is precisely the property that makes the hash useful as integrity evidence |
| `battle_id`, `config_hash`, `schedule_hash`, `seed_index`, `git_sha` | Stable identifiers shared with the repository's committed eval artifacts; they link a bundle to its run and to every other bundle from that run |
| `observable_state_hash`, `request_hash` | Deterministic digests of game state — two bundles of the same position yield the same value |
| Seat labels | Deterministic and stable across every file (§12.2). Stability is *required* for cross-file joins, and it means anyone with side knowledge of who occupied `p1` re-identifies that seat immediately |
| Battle content | Team composition, move sequence, and turn structure are themselves a fingerprint. No name substitution removes them |

The consequence is a sharing rule, not a hash removal: **a bundle is safe to share only under the
same trust assumptions as the source it was built from.** Dropping `source_hashes` would reduce
linkability but destroy the integrity contract in §8, so this contract keeps them and documents the
residual risk here instead.

Public distribution, a cleartext-name mode, and private or hidden replay sharing stay outside v0,
pending the separate authorization UX and legal review that
[`../research/2026-07-license-data-audit.md`](../research/2026-07-license-data-audit.md) §4.2 already
requires. §3.4 of that audit is directly on point: Studio must not rely on a private-household
exemption, and re-identification risk, retention, and data-subject rights remain external
legal-review topics. No manifest field asserts anonymity, and none may be added that does.

## 13. Fail-closed error matrix

Extends [`viewer-v0-design.md`](viewer-v0-design.md) §7 with the export side. **Refuse** = do not
enter trusted mode, state the reason, name the offender.

The two stages are separate and are never merged into one row. **Export refuses** means the bundle is
never produced. **Reader refuses** means an already-produced bundle is rejected or a surface is
disabled — the reader must still defend itself, because a bundle may be hand-made, corrupted, or
written by a different exporter version. A condition that the export refuses can therefore still have
a distinct, non-contradictory reader rule.

### 13.1 Export stage

| Condition | Behaviour |
|---|---|
| Unknown `trace_schema_version` | refuse; Godot holds no migration logic |
| Trace is `decision-trace-v1` | refuse the trace export; §11.4. A replay-only bundle may still be produced |
| v2/v3, `candidates` non-empty, `chosen_candidate_key` null or unresolvable | refuse; name the decision (§11.4) |
| v2/v3, `chosen_candidate_key` matches more than one candidate | refuse; ambiguous identity |
| v2/v3, `candidates` empty but any `chosen_*` non-null | refuse; impossible for this producer |
| `chosen_rank` disagrees with the resolved candidate's `rank` | refuse |
| Resolved chosen candidate disagrees with `normalized_action` | refuse; §11.4 desync |
| Duplicate `candidate_key` within a decision | refuse |
| Non-canonical `candidate_key` | refuse; canonicality is byte-checked |
| Duplicate `(battle_id, decision_index, our_side)` | refuse |
| Row `battle_id` or `our_side` differs from the manifest | refuse; the bundle is single-battle single-side |
| One `request_hash` matches more than one trace row | refuse; an ambiguous join is never guessed (§11.3.2) |
| Two sources disagree on a shared provenance field | refuse; §11.1.3 |
| `config-manifest.json` hash disagrees with row `config_hash` | refuse |
| `NaN` / `Infinity` in any source numeric | refuse; JCS cannot represent it |
| Absolute path, URL, or user name in any bundle value | refuse |
| Any wall-clock or export timestamp in the bundle | refuse |
| Neither `battle_log` nor `decision_trace` available | refuse; a bundle must carry at least one |
| `git_sha == "unknown"` | not an error; emit `dirty: null`, never `false` (§8.4) |
| Decision `request_hash` matches no raw request | not an error; `request_protocol_index: null`, marked as having no replay event |
| `candidates` empty on a team-preview row | not an error; export with an empty candidate set (§11.4) |
| Malformed protocol event | exporter classifies recoverable or not; the classification is recorded |

### 13.2 Reader stage

| Condition | Behaviour |
|---|---|
| Unknown `viewer_bundle_schema.major` | refuse; list supported majors |
| Higher minor, all capabilities known | open; preserve unknown optional fields for raw display |
| Unknown entry in `required_capabilities` | refuse; name the capability |
| Hash mismatch on any present file | refuse; name the file |
| File on disk not declared in `files` | refuse; name the file |
| `required != present` on `battle_log` or `decision_trace` | refuse; malformed manifest (§11.1.1 invariant 1). Covers both `required: true, present: false` and `required: false, present: true` |
| `required: true` on `warnings` or `config_manifest` | refuse; malformed manifest (§11.1.1 invariant 2) |
| Both `battle_log` and `decision_trace` absent | refuse; a bundle must carry at least one |
| Field nullability disagrees with the derived mode | refuse; malformed manifest (§11.1.2) |
| Optional file absent | open degraded; persistent warning; render `not recorded` |
| Replay present, trace absent | replay-only mode; no candidate panel; no decision claims |
| Trace present, replay absent | trace-only mode; no board; no simulated state |
| Duplicate `decision_index` within the bundle | refuse decision synchronization |
| `chosen_candidate_key` absent from `candidates[]` on a non-empty candidate set | mark that decision invalid; never choose by label. A conforming exporter cannot emit this, so the bundle is untrusted — but the reader must not fall back to label matching ([`viewer-v0-design.md`](viewer-v0-design.md) §7) |
| `candidates` empty | no candidate table; not an error, not a degradation |
| `request_protocol_index` null | show the decision as a timeline entry with no replay event |
| Unsupported candidate field on a supported bundle | preserve for raw display; never reinterpret |

The exporter, not Godot, decides recoverability
([`viewer-v0-design.md`](viewer-v0-design.md) §7).

## 14. Fixture catalogue

Fixtures are **not created by this spec**. This is the catalogue a later implementation plan must
build. Each is small and provenance-clean. The default rule is derivation from committed producer
evidence — preferably from
`data/eval/champions-panel-v0/smoke-i7a-mega/decision_trace.jsonl`, which already exercises all
three decision phases and candidate counts from 0 to 104.

### 14.1 Synthetic-coherent fixture exception (Amendment A — 2026-07-21)

**Problem.** A replay+trace fixture requires a battle log whose `|request|` payloads hash to the
trace rows’ `request_hash` values **and** results/manifests that agree on provenance. As of
2026-07-21, no committed Champions smoke (or surveyed `data/eval` corpus) ships a non-null
`room_raw_path` beside a `decision_trace.jsonl`. Inventing a log that merely “joins” an unrelated
real smoke trace/results pair is forbidden: it would misrepresent a producer run.

**Exception.** A catalogue fixture MAY be a Studio-authored **synthetic-coherent** set when all of
the following hold:

1. **Label.** `SOURCES.md` (or equivalent fixture index) records
   `source_kind: synthetic-coherent-v1` for that fixture. The label is mandatory and must not be
   omitted.
2. **Internal coherence.** Every exported decision’s `request_hash` matches a surviving `|request|`
   line in the companion battle log (after the exporter’s skip rules); all provenance fields that
   the bundle carries agree across the synthetic inputs.
3. **No false producer claim.** The fixture must not present itself as an export of a real
   committed eval run. It must not reuse a real `battle_id` / `run_id` / `config_hash` /
   `schedule_hash` (or other run-identity field) from anywhere under `data/eval/` as if the
   synthetic log were that run’s missing room dump. Synthetic provenance uses **documented
   sentinel values** listed in `SOURCES.md` for that fixture.
4. **`git_sha` / `dirty` honesty (§8.4).** Synthetic sources must set `git_sha` to the literal
   `"unknown"`. They must **not** invent a 40-hex SHA. A synthetic source row/manifest may still
   carry legacy boolean `dirty: false` (producer fail-open shape). The exporter **must** then emit
   `source_provenance.dirty: null` in the bundle — never `dirty: false` — because §8.4 requires
   `null` whenever `git_sha == "unknown"`. Emitting `dirty: false` with a non-commit SHA (or with
   `"unknown"`) is a false cleanliness claim and is forbidden.
5. **Privacy.** Portable-bundle privacy rules (§12) still apply; synthetic inputs used for privacy
   counterexamples may contain deliberate leak substrings, which the exporter must strip.
6. **Separation.** Gates that require real producer row shape (for example chosen-key integrity on
   committed Mega candidate sets) continue to use read-only committed evidence in a **separate**
   suite that does not claim a joined synthetic replay.

This exception authorizes Fixture 1 (normal analysis) to be synthetic-coherent when no committed
pair exists. It does **not** authorize mixing synthetic battle logs with real smoke
results/manifests/traces.

| # | Fixture | Must prove |
|---|---|---|
| 1 | normal analysis | replay + trace; all phases; chosen key resolves to exactly one candidate; two exports byte-identical; may be `synthetic-coherent-v1` under §14.1 |
| 2 | close decision | `top1_top2_margin` small and correct; no threshold implied; margin `null` when fewer than two candidates |
| 3 | fallback / degradation | `fallback_reason` non-null; `fallback_used: true`; `aggregation.mode: null` with its degradation warning visible without opening raw JSON |
| 4 | replay-only | `decision_trace` absent and declared; no candidate claims; persistent degraded banner |
| 5 | trace-only | `battle_log` absent and declared; no board; no simulated state |
| 6 | invalid hash | one byte mutated in a data file; refuse; the mismatching file is named |
| 7 | unsupported major | `viewer_bundle_schema.major` above the supported set; refuse; supported majors listed |
| 8 | missing mandatory file | a `required: true` file declared `present: true` but absent; refuse |
| 9 | duplicate decision identity | two rows with the same `(battle_id, decision_index, our_side)`; refuse synchronization |

Additional counterexample fixtures required by the contract above:

| # | Fixture | Must prove |
|---|---|---|
| 10 | privacy counterexample | input containing chat, a PM, player names, an avatar id, a nickname, a replay URL, and an absolute path; the bundle contains **none** of those literal values; the input file remains byte-identical |
| 11 | non-finite value | a source row with `NaN` or `Infinity`; export refuses |
| 12 | unknown required capability | `required_capabilities: ["belief_v2"]`; refuse; name it |
| 13 | legacy trace-v1 | no validated `candidate_key`; the trace export is **rejected with a precise reason** (§11.4 — migration is not an option, `candidate_id` is provably lossy); a **replay-only** bundle is still produced when a room log exists; Godot holds no migration logic |
| 14 | chosen-candidate desync | `chosen_*` disagreeing with `normalized_action` (§11.4); export refuses |
| 15 | `git_sha == "unknown"` | `dirty` is `null`, never `false`; the viewer shows `dirty state not recorded` |
| 16 | team-preview empty candidate set | a v3 row with `candidates: []` and all `chosen_*` null exports cleanly; no candidate table; **not** flagged as degraded (§11.4). Derivable from rows 0 and 11 of the real committed fixture |
| 17 | filtered protocol lines | a log containing `\|player\|`, `\|j\|`, `\|t:\|`, and chat; `protocol_index` in `battle.jsonl` is sparse and strictly increasing, and the gaps land exactly on the filtered lines (§11.3.1) |
| 18 | `\|request\|` skip rules | a log with an `rqid` resend and a `req.wait` request; neither produces a decision, and the surviving joins still resolve (§11.3.2) |
| 19 | unjoinable decision | a trace row whose `request_hash` matches no raw request; `request_protocol_index: null`; the decision remains a distinct timeline entry, never dropped, never attached to a neighbouring turn |
| 20 | replay-only nullability | `trace_schema_version`, `our_side`, and `source_hashes.decision_trace` are all `null`; `config_hash`/`git_sha`/`config_id`/`schedule_hash`/`seed_index` resolve from the result row (§11.1.3) |
| 21 | provenance disagreement | a trace row and a result row disagreeing on `config_hash`; export refuses (§11.1.3) |
| 22 | mode key `required != present` | §11.1.1 **invariant 1**. Two named variants, each asserted separately so one cannot mask the other: **22a** `battle_log` declared `required: false, present: true`; **22b** `battle_log` declared `required: true, present: false`. Both refuse as malformed. 22b is distinct from fixture 8, where the file *is* declared present and is merely missing on disk (invariant 5) |
| 23 | optional key `required: true` | §11.1.1 **invariant 2**. `warnings` declared `required: true`; refuse as malformed. `warnings` and `config_manifest` are optional in every mode, so neither may ever declare itself required |

## 15. Test and acceptance gates

Binding for the later implementation plan. Each maps to a check that can fail.

**Determinism**

1. Two exports of one frozen source produce the same relative file list and identical SHA-256 per
   file (§7.6).
2. The comparison uses the file list and per-file digests, never directory or archive metadata
   ([`viewer-v0-design.md`](viewer-v0-design.md) §9.1).
3. A one-byte source mutation changes the bundle digest.
4. No bundle file contains an absolute path, URL, user name, host name, or wall-clock value.
5. Re-running the export in a different directory, under a different user, on a different OS
   produces identical bytes. This is the real test of §8.3, given §12.1.

**Canonical form**

6. Every emitted file is valid RFC 8785 JCS; a conformance vector suite runs against the serializer.
7. Every JSONL file ends with exactly one `\n` and contains no `\r`.
8. A non-finite input fails export (fixture 11).
9. `candidate_key` round-trips byte-identically from source row to bundle; a test asserts the
   exporter never re-serializes its inner JSON (§7.3).

**Identity and integrity**

10. Every **non-null** `chosen_candidate_key` **on a row with a non-empty candidate set** resolves to
    exactly one candidate, on the real committed v3 fixture. Rows with `candidates: []` are excluded
    by construction — they carry `chosen_candidate_key: null` and are covered by gate 36 instead.
11. `chosen_rank` equals the resolved candidate's `rank` on every row **that has a resolved
    candidate**. Rows with an empty candidate set carry `chosen_rank: null`.
12. The resolved chosen candidate agrees with `normalized_action` on every row **that has a resolved
    candidate** (§11.4).
13. Duplicate identity and duplicate candidate keys refuse (fixtures 9, 14).
14. Sorting the candidate table by every supported column never changes which row is chosen and
    never changes `rank`.

**Versioning**

15. Unknown major refuses; unknown required capability refuses naming it (fixtures 7, 12).
16. A higher minor with only known capabilities opens and preserves unknown optional fields.
17. A minor bump that adds a required field is rejected by a schema test — the rule is enforced, not
    documented.

**Privacy**

18. The privacy counterexample fixture exports none of the literal values, and the input remains
    byte-identical (fixture 10). This is also gate 4 of
    [`../research/2026-07-license-data-audit.md`](../research/2026-07-license-data-audit.md) §6.
19. Every exported file uses the same seat pseudonyms; no reversible map is present.
20. No bundle field matches a credential-shaped key (§12.4).
21. No nickname and no `LogEvent.raw` appears in any bundle file.

**Provenance**

22. `git_sha == "unknown"` yields `dirty: null` (fixture 15).
23. `source_hashes` equal the real source digests and are never compared to `files.*.sha256`.
24. When present, `config-manifest.json`'s `config_hash` equals the row `config_hash`; a mismatch
    refuses.
25. Nothing in the bundle is derived from `config_hash`. A test asserts no reverse-lookup exists.

**Degradation**

26. All three modes are reachable and visually distinct (fixtures 1, 4, 5).
27. Absent optional data renders `not recorded`, never `0`, `false`, or `[]`.
28. `aggregation.mode: null` is visibly degraded without opening raw JSON.
29. `suspected` is not rendered at schema 1.0 (§10.5).

**Modes, join, and identity**

30. `request_hash` is byte-identical between the live and offline recipes, asserted on the real
    committed fixture. This pins the §11.3.2 join, which no test in `showdown_bot/` currently covers.
31. All three legal `required`/`present` combinations in the §11.1.1 truth table are exercised
    (fixtures 4, 5, 20), and every malformed one refuses: a mode key with `required != present` in
    both directions (fixture 22, variants 22a and 22b — invariant 1), and an optional key declaring
    `required: true` (fixture 23 — invariant 2). Each variant is asserted separately, so one passing
    case cannot mask another.
32. Replay-only nullability matches §11.1.2 exactly; no field is omitted rather than nulled
    (fixture 20).
33. A provenance disagreement between two sources refuses (fixture 21).
34. `protocol_index` is sparse, strictly increasing, and never renumbered; gaps correspond to
    filtered lines (fixture 17).
35. `rqid` resends and `wait` requests produce no decision (fixture 18).
36. An empty candidate set exports cleanly, carries `chosen_candidate_key: null` and
    `chosen_rank: null`, and is not reported as degraded (fixture 16).
37. A trace-v1 source is rejected for trace export with a precise reason, and still yields a
    replay-only bundle when a room log exists (fixture 13).

Godot-side gates (bounded rendering for the 104-candidate row, mixed-DPI, 75–200% scale,
keyboard-only, headless gdUnit4) remain as specified in
[`viewer-v0-design.md`](viewer-v0-design.md) §9.2–9.3 and
[`../decisions/ADR-001-godot-ui-technology.md`](../decisions/ADR-001-godot-ui-technology.md). They
are not restated here.

## 16. Open design inputs

Explicitly DESIGN INPUT MISSING. None may be invented, defaulted, or inferred. Each blocks only its
own feature; none blocks schema 1.0.

### 16.1 Candidate-set completeness

No producer records whether `TOP_K_TRACE_CANDIDATES` truncation was applied (§2.5). A count of
exactly 6 is ambiguous. Closing this needs a producer-side flag on the trace row, which is a
breaking change to a closed-world validator (§2.2). Until then the viewer must not claim the
candidate list is complete, and must not claim it is truncated either.

### 16.2 Aggregation mode, `risk_lambda`, `must_react_lambda`

Not persisted in any trace version (§2.4). Schema 1.0 emits `null` plus a degradation warning.

A join is structurally possible but not adopted: `research/aggregation_trace.py` defines a separate
`agg-trace-v1` schema whose required fields include `battle_id`, `seed_index`, `decision_index`, and
`our_side`, and whose nullable fields include `aggregation_mode`, `risk_lambda`, and
`must_react_lambda`. Its `candidates[].action_key` uses the same candidate-key namespace as the trace
row. Three facts argue against relying on it for schema 1.0: no agg-trace artifact is committed
anywhere under `data/`; it is a separate opt-in research output; and its `selected_action_key` is in
the normalized-`/choose` namespace and does **not** join to `action_key`, so a naive join by string
equality yields zero matches. [`viewer-v0-design.md`](viewer-v0-design.md) §6.5 already directs that
the gap be closed by a tested, backward-compatible trace/export contract. That remains the path; the
agg-trace join is recorded here only so it is not rediscovered as a shortcut.

### 16.3 Belief snapshot and the source of `suspected`

No belief field exists on the DTO or any row. The belief subsystem
(`showdown_bot/src/showdown_bot/learning/belief_builder.py`) never enters the trace. Reserved
capability name: `belief_v2`. Blocks the `suspected` information state (§10.5).

### 16.4 Per-decision warning objects and a severity vocabulary

No bot-side producer. `warnings` exists only in the unrelated eval report. Schema 1.0's
`warnings.json` therefore carries **exporter** warnings only, and `warning_count` counts exactly
those (§10.4). A bot-side warning contract, its object shape, and its severity vocabulary are open.

### 16.5 Score components

`OutcomeBreakdown` (`showdown_bot/src/showdown_bot/battle/evaluate.py:94`) carries nine real
component fields in memory, and `score_vector` carries a per-response score. Neither reaches the
trace row. A candidate-detail view of score components requires a producer change. Until then the
candidate detail can show only `aggregate_score`.

### 16.6 `selection_stage` and `fallback_reason` vocabularies

Both are persisted, real, and **unvalidated** — no closed enum exists (§2.7(a)). The literal values
observed in code are listed in §2.7(a), but the sets are open. The viewer must render an unknown
value verbatim rather than mapping it to `unknown` or dropping it. Whether to close these enums is a
producer decision, not a bundle decision.

### 16.7 State-summary fields beyond the recorded payload

`observable_state_payload` (`decision_capture.py:78-93`) and `_pokemon_payload`
(`decision_capture.py:54-75`) define exactly what is recorded. Any mockup state field outside that
set has no producer. The dossier's own compliance matrix already flags this.

### 16.8 Not carried into schema 1.0

`seed`, `seed_base`, `run_id`, and `start_ts` are excluded (§8.3). If a future exact-takeover or
reproduction feature needs the seed
([`../architecture/PROJECT_BOUNDARIES.md`](../architecture/PROJECT_BOUNDARIES.md) §7), it requires
its own design decision and its own capability, not a silent addition.

## 17. Boundary to the later Godot slice

This spec ends at the bundle. It authorizes planning, not building, and it does not extend to the
Godot slice's own design.

**In this contract:** the bundle directory layout; `manifest.json`; the canonical byte profile; the
hash and provenance contract; the privacy transformation; the fail-closed export and reader rules;
the field matrix; the fixture catalogue; the acceptance gates.

**Not in this contract, and owned by the Godot slice** ([`viewer-v0-design.md`](viewer-v0-design.md)
§5.4, §6): component decomposition (`BundleLoader`, `BattleTimeline`, `ReplayPresenter`,
`DecisionPresenter`, `DiagnosticsPresenter`, `ProvenancePresenter`, `WorkspaceLayout`); the abstract
board; docks, scale, density, theming; keyboard bindings; the state banner; bounded rendering and
virtualization; background loading, progress, and cancellation; mixed-DPI behaviour; gdUnit4 setup.

The single hard rule across that boundary: **Godot consumes the DTOs in §10 and computes no
Pokémon mechanic, score, belief, ranking, or identity of its own** (§9). Any Godot task that needs a
value not in §10 is blocked by §16 and requires a producer change first — not a workaround in
GDScript.

Sequencing is unchanged from [`viewer-v0-design.md`](viewer-v0-design.md) §11: this contract governs
step 1 (bundle contract and deterministic Python exporter) and step 2 (exporter fixtures and
validation tests). With this spec approved, an implementation plan covering those steps may now be
written. Building them — and steps 3–7 — stays unauthorized until that plan is reviewed and approved
in its own right.
