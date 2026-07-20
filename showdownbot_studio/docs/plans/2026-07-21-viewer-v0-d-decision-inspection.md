# Viewer v0 — Plan D: Decision Inspection (Sketch)

**Status:** DRAFT — sketch only; **implementation not authorized**
**Date:** 2026-07-21
**Depends on:** Plan B DTOs, Plan C timeline selection, fixtures 1, 3, 16
**Unblocks:** Plan E (banner coupling), Plan F (deep-link E2E)

**Authority:** [`../specs/viewer-v0-design.md`](../specs/viewer-v0-design.md) §3.2 / §6.5 / §7,
bundle contract §9 / §10.2 / §10.4 / §11.2 / §11.4 / §16

## Goal

Inspect recorded decisions: candidate table with structural chosen-key emphasis, detail views for
recorded fields only, exporter navigation values, and fail-closed deep-link launch.

## Non-goals

- No re-ranking or score recomputation
- No `suspected` state (§16.3 missing)
- No score-component breakdown beyond `aggregate_score` (§16.5)
- No score-over-time graph (v0.1)
- No inference of aggregation mode from `config_hash`

## Architecture

```text
Selected decision DTO
  → DecisionPresenter
      → CandidateTable (sort/filter presentation only)
      → CandidateDetail / StateSummary tabs
      → Navigation: next close / fallback / warning using derived fields
  → Deep link --decision battle_id:decision_index
```

## Proposed files

| Path | Responsibility |
|---|---|
| `godot/src/decision/decision_presenter.gd` | Selection binding |
| `godot/src/decision/candidate_table.tscn` | Bounded table |
| `godot/src/decision/candidate_detail.tscn` | Recorded fields |
| `godot/src/decision/state_summary_view.tscn` | Recorded summary only |
| `godot/src/decision/navigation.gd` | margin / fallback / warning jumps |
| `godot/src/app/deep_link.gd` | CLI `--decision` parse + resolve |

## Task sketch

### D1 — Chosen-key resolution (presentation)

- [ ] Highlight exactly one row when `chosen_candidate_key` resolves
- [ ] Empty candidates: no table / no chosen row — not an error (fixture 16)
- [ ] Unresolvable key on non-empty set: mark decision invalid; never label-match
- [ ] Sorting/filtering never changes recorded `rank` or chosen identity

### D2 — Candidate table

- [ ] Columns from recorded fields: chosen, label, key, stage, aggregate score, mega/tera, fallback
- [ ] Bounded rendering proven against 104-candidate fixture row (from Plan A fixture 1 lineage)
- [ ] Open vocabularies (`selection_stage`, `fallback_reason`): render unknown values verbatim

### D3 — Detail + aggregation honesty

- [ ] Always show `aggregation` object; at schema 1.0 all null → label `aggregation mode not recorded`
- [ ] Optional nulls → `not recorded` (never invent 0/false/[])
- [ ] Do not render `suspected`
- [ ] Latency shown as recorded mandatory `decision_latency_ms` (not a degradation chip)

### D4 — Navigation fields

- [ ] Use exporter `top1_top2_margin`, `fallback_used`, `warning_count` only
- [ ] No universal close-decision threshold
- [ ] Jump next close / fallback / warning

### D5 — Deep link

- [ ] `--decision <battle_id>:<decision_index>`
- [ ] Bundle is single-battle single-side → unambiguous
- [ ] Invalid/missing target → diagnostic fail; never silent substitute

## Acceptance (Plan D done)

- Fixture 1: turn nav and decision nav land on same decision; chosen key unique
- Fixture 3: fallback + aggregation degradation visible without raw JSON
- Fixture 16: empty candidates clean
- Deep link success + failure paths covered by gdUnit4 or CLI integration test
- Candidate sort modes do not move the chosen highlight to another identity
