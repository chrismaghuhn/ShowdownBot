# Viewer v0 — Plan F: End-to-End Acceptance (Sketch)

**Status:** DRAFT — sketch only; **implementation not authorized**
**Date:** 2026-07-21
**Depends on:** Plans A–E complete and green
**Unblocks:** Viewer v0 merge readiness review (separate user decision)

**Authority:** bundle contract §14–§15, [`../specs/viewer-v0-design.md`](../specs/viewer-v0-design.md) §9,
[`../MASTER_SPEC.md`](../MASTER_SPEC.md) §11

## Goal

Close the Phase 0 acceptance matrix: complete fixture catalogue, CI gates (pytest + headless
gdUnit4), manual desktop checks, and documentation status bump — without authorizing Phase 1+.

## Non-goals

- No live network tests
- No strength claims
- No public release license inventory (pre-release gate in license audit §6 — track separately)
- No bot-side producer changes for §16 open inputs

## Fixture completion matrix

Complete any fixtures not shipped in Plan A. Each must prove its contract row:

| # | Fixture | Owner check |
|---|---|---|
| 1 | normal analysis | A+B+C+D |
| 2 | close decision (margin) | A+D |
| 3 | fallback / aggregation degradation | A+D+E |
| 4 | replay-only | A+B+C+E |
| 5 | trace-only | A+B+C+E |
| 6 | invalid hash | A+B |
| 7 | unsupported major | A+B |
| 8 | missing mandatory file | A+B |
| 9 | duplicate decision identity | A+B |
| 10 | privacy counterexample | A |
| 11 | non-finite value | A |
| 12 | unknown required capability | A+B |
| 13 | legacy trace-v1 → refuse trace / replay-only | A |
| 14 | chosen-candidate desync refuse | A |
| 15 | `git_sha == "unknown"` → dirty null | A+E |
| 16 | team-preview empty candidates | A+D |
| 17 | filtered protocol lines / sparse index | A+C |
| 18 | request skip rules | A |
| 19 | unjoinable decision | A+C |
| 20 | replay-only nullability | A |
| 21 | provenance disagreement | A |
| 22a/22b | mode key required!=present | A+B |
| 23 | optional key required:true | A+B |

## Task sketch

### F1 — Automated gate suite

- [ ] Map every exporter gate in §15 to a named pytest
- [ ] Map viewer §9.2 items to gdUnit4 tests where automatable
- [ ] CI script: Python tests + Godot headless gdUnit4 with JUnit output
- [ ] Representative 104-candidate bounded-render test must be automated

### F2 — Manual desktop checklist (record evidence in PR / review note)

- [ ] Mixed-DPI: window across two scale factors
- [ ] Scale 75/100/150/200 reachability at min window
- [ ] Compact vs Comfortable same selection
- [ ] Keyboard-only full inspection path
- [ ] Abstract board understandable with artwork disabled
- [ ] Deep link success + diagnostic failure

### F3 — Honesty / non-claim audit

- [ ] UI copy never implies strength/safety/correctness of the bot
- [ ] Aggregation degradation visible
- [ ] `suspected` not rendered
- [ ] Completeness of candidate set neither claimed nor denied (§16.1)

### F4 — Docs closeout

- [ ] Flip plan statuses A–F from DRAFT→APPROVED only if already approved earlier; else leave history
- [ ] Update [`../README.md`](../README.md) Studio status lines (exporter/Godot exist after merge)
- [ ] Update [`README.md`](README.md) plans index
- [ ] Explicitly state Phase 1+ still unauthorized

### F5 — Merge readiness packet

Produce a short review note listing:

1. Specs implemented (A–E scope)
2. Fixture digests / paths
3. CI command + last green counts
4. Manual checklist results
5. Known §16 gaps still open
6. Residual privacy linkability reminder (bundle contract §12.6)

## Acceptance (Viewer v0 program done)

- All fixtures 1–23 green in automated or documented manual form as required
- No Studio writes into frozen eval sources
- No network in runtime paths
- User review before merge; user review before any Phase 1 design kickoff

## Explicit stop line

After Plan F, **stop**. Live Spectator, Team Analyzer, full client, add-ons, and external bots each
require their own approved design + plan. This document must not grow those tasks.
