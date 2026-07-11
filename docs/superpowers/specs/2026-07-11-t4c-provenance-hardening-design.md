# T4c — Provenance Hardening (row↔log binding + report re-parse + environment block)

**Status:** approved scope (external harness review 2026-07-10, 8.5/10, accepted by user with
two design corrections recorded below). Mini-slice, queued after 2b-2.5a (merged `afb9708`).

## Problem

The eval harness's result rows carry parsed outcomes (winner/turns/end_reason/end_hp_diff,
parsed from room_raw at write time since T3f), and room logs are committed as evidence — but
nothing **binds** a row to its log, and `eval-report` never re-derives outcomes from the logs.
The T5 pin test `winner_flip_is_undetectable` documents the gap: a corrupted/forged
results.jsonl is undetectable by the report alone.

## Design corrections vs the external reviewer's proposal (recorded 2026-07-10)

1. **No `parsed_*` field duplication in rows** — the row fields ARE the parse output already
   (T3f writes them from `parse_battle_result`). The missing piece is only the row↔log
   BINDING plus report-side RE-derivation.
2. Channel-B seeding (explicit per-battle seed protocol channel) stays out of scope.

## Requirements

**R1 — Row↔log binding.** Result rows gain `normalized_room_log_sha256`: sha256 hex over the
byte output of the EXISTING canonical normalization (`eval/room_dump.normalize_battle_log`,
with the same `name_subs` convention the T4 identity checks use), computed in-process from the
frames at write time (same place the T3f parse runs — no re-read from disk). Legacy rows
lack the field (null/absent); every consumer tolerates that.

**R2 — Report-side re-parse.** `eval-report` gains an optional `--room-raw <dir>` input
(explicit flag, no auto-magic). When given, fail-closed integrity checking runs for EVERY row:
- the row's log file must exist in the dir (resolved via the row's `room_raw_path` basename);
  missing file = hard error (house pattern: raise, like the pairing validators).
- re-parse via `eval/battle_parse.parse_battle_result` → winner/turns/end_reason/end_hp_diff
  must equal the row's fields;
- recompute the normalized sha → must equal `normalized_room_log_sha256` (skipped for legacy
  rows with null sha; the parse cross-check still runs);
- any mismatch → `LogIntegrityError` listing every offending row (fail-closed; no soft
  section, no partial GO verdict on corrupted evidence).
When the flag is absent, behavior is byte-identical to today (golden reports unchanged).

**R3 — Winner-flip pin inversion.** The T5 pin `winner_flip_is_undetectable` stays for the
no-logs path. New test: with the committed `data/eval/t4/rerun/` fixtures (results + room_raw),
a flipped winner in a copied results.jsonl IS detected (`LogIntegrityError`).

**R4 — Environment block.** Run manifests gain an `environment` section: python version, node
version (`node --version`, null if unavailable), OS/platform string, and versions of key deps
(pydantic, websockets, lightgbm if importable). **Explicitly NOT part of `config_hash`** —
environment differences must not fork the config lineage; byte-reproduction remains the
arbiter of equivalence. The report renders the block informationally in provenance.

## Non-goals

Backfilling legacy evidence; Channel-B; row-side parsed_* duplication; any battle-running
(all tests use committed fixtures — hard constraint: no local battles).

## Testing strategy

Everything offline: unit fixtures for the sha (known frames → known sha), committed
`data/eval/t4/rerun/room_raw/{prefix,run1,run2}` for the report re-parse path (R2, R3),
config_hash-unchanged pin for R4.
