# Champions Mega I7a Split Execution Index

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement these plans in order. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver own-side Champions Mega support through three reviewable, sequential slices without mixing metadata, decision ranking, trace migration, state reconciliation, and frozen smoke evidence in one implementation plan.

**Architecture:** I7a-A creates format-neutral Mega metadata, state projection, protocol actions, and a single variant-expansion owner. I7a-B consumes that foundation in every live scoring path and performs the atomic candidate-key-v2/decision-trace-v3 migration. I7a-C adds protocol reconciliation, provenance, and a clean-tree safety smoke.

**Tech Stack:** Python 3.11+, Pydantic, pytest, Node.js with `@pkmn/dex` 0.10.11, pinned `@smogon/calc`, Pokemon Showdown local server for the final smoke only.

---

**Status:** APPROVED split plan — sequential implementation is allowed after the plan documents are committed; no production implementation or push has started.

**Approved design:** `docs/projects/champions/specs/2026-07-14-champions-mega-i7-design.md` rev. 9 at `d3dde25`.

## Mandatory execution order

1. [`2026-07-15-champions-mega-i7a-a-foundation.md`](2026-07-15-champions-mega-i7a-a-foundation.md)
2. [`2026-07-15-champions-mega-i7a-b-decision-trace.md`](2026-07-15-champions-mega-i7a-b-decision-trace.md)
3. [`2026-07-15-champions-mega-i7a-c-reconcile-smoke.md`](2026-07-15-champions-mega-i7a-c-reconcile-smoke.md)

Each plan starts from the green, reviewed tip produced by the preceding plan. Do not execute them concurrently.

## Slice contracts

| Slice | Produces working software | Explicitly excludes |
|---|---|---|
| I7a-A Foundation | Request parsing, `/choose ... mega`, deterministic metadata/form lookup, pure own-side projection, spread identity, protocol legality, one variant-expansion owner | `_choose_best`, `max_damage_choice`, trace schema changes, log reconciliation, manifests, battles |
| I7a-B Decision/Trace | Mega-aware heuristic, K-world/depth-2/max-damage/export consumers, first-class Mega candidates, key-v2 and trace-v3 | Opponent Mega hypotheses, log reconciliation, run artifacts, Strength claims |
| I7a-C Reconcile/Smoke | Atomic `detailschange` + `-mega` state reconciliation, metadata provenance, clean 2-battle safety evidence | I7b, latency budget changes, Strength claims |

## Cross-slice stop gates

- Do not start I7a-B unless every I7a-A focused test and the existing action/request/state suites pass.
- Do not start I7a-C unless I7a-B proves Reg-I chosen `/choose` byte identity and v1/v2 trace loader compatibility.
- Do not run the smoke from a dirty tree. The smoke commit SHA must already contain all production and schedule changes.
- A failure at any gate stops the next slice; do not weaken a test or silently exclude a Mega form.

## Approved-spec coverage map

| Plan | Rev.-9 test ownership |
|---|---|
| I7a-A | T1–T13, T18, T23–T24, T27, T30, T38–T40, raw/projectable half of T50 |
| I7a-B | T14–T17, T20–T22, T25, T28, T31, T33–T37, T47–T49, ranking/trace half of T50, T52–T54 |
| I7a-C | T41–T46 plus provenance, full-suite, and clean safety-smoke gates |

Together these rows cover every I7a test assigned by approved spec rev. 9. T19, T26, T29, T32, and T51 are deliberately absent because they belong to I7b.

## I7b reservation

Tests T19, T26, T29, T32, and T51 remain I7b-only. In particular, this index does not authorize opponent Mega hypothesis expansion, dual-side activation ordering, or a Champions Strength run.
