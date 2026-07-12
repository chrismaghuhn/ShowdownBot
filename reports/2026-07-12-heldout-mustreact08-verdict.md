# Held-out gate — `must_react_lambda` 0.8 vs 0.6 — Verdict

**Date:** 2026-07-12 (user-authorized held-out spend) · **Branch:** `feat/slice-2c-1-mustreact` · **Kaggle:** `sb-heldout-mustreact08` @ `REPO_SHA d728324`

## TL;DR — NO-GO for shipping 0.8; keep the 0.6 default

The dev-strength A/B found `must_react_lambda=0.8` beats 0.6 by **+11.3pp vs `max_damage`** (p=0.0002), but that gain was concentrated in the **sun** cell against a worst-case attacker. The **held-out gate** — the real generality test on **varied opponents** (heuristic, max_damage, simple_heuristic, greedy_protect, scripted_vgc) and **different team archetypes** (balance + tailwind) — does **NOT confirm it**:

- **UNDERPOWERED, `n_discordant = 0`**: 0.8 and 0.6 produced **identical win/loss on all 34 held-out games** (both **7/34 = 20.6%**). delta = 0.0, exact p = 1.0.
- **Not a bug:** the two arms have **distinct config_hashes** (0.8 → `13abaf72`, 0.6 → `ced31adc`) and **distinct results sha256** → `must_react_lambda` *did* change in-battle decisions (different battle logs) but **flipped zero game outcomes**.

**=> The held-out gate gives zero positive evidence of a general improvement. Do NOT change the default; keep `SHOWDOWN_MUST_REACT_LAMBDA=0.6`.** The dev gain was a narrow sun+`max_damage` effect; the gate caught it before it shipped — exactly its job.

## Numbers (HELD-OUT — must never inform tuning; the verdict is methodological, not the win rates)

| metric | candidate 0.8 | baseline 0.6 |
|---|---|---|
| overall win rate | 7/34 = 20.6% | 7/34 = 20.6% |
| McNemar | n11=7, n00=27, **n10=0, n01=0, n_disc=0**, p=1.0 | |

Per-policy (both arms identical): heuristic 2/10, max_damage 0/10, simple_heuristic 0/6, greedy_protect 1/4, scripted_vgc 4/4. Safety: SAFETY-PASS both arms (latency p95 worst 399 ms, 0 crashes/invalid, byte-repro, HELD-OUT banner present).

## Why it's inert on held-out (mechanistic, not just small-n)

`must_react_lambda` only affects MUST_REACT-mode aggregation (it up-weights the worst-case opponent response). The dev +11.3pp came almost entirely from the **sun** cell vs `max_damage` (a worst-case attacker). The held-out panel has **no sun team** (balance + tailwind archetypes) and **varied opponents**, so the worst-case-heavy boards the knob helps on are **not exercised** → outcome-inert. Many held-out cells are also floor/ceiling blowouts (max_damage 0/10, scripted_vgc 4/4) that no aggregation knob can flip.

The gate is **statistically weak by design** (34 games/arm; `n_discordant=0` gives literally zero power — the report forbids citing it as stability). But combined with the sun-specificity of the dev gain, the total evidence is coherent: **a fixed global `must_react_lambda` is not a general improvement.**

## Constructive takeaway

A fixed global scalar cannot capture a benefit that is board- and opponent-specific. The right vehicle for worst-case-sensitive play is **per-position** worst-case aggregation — the **CVaR term in the 2c search** (`02-decision-engine §3`), which adapts to the actual board/opponent distribution instead of a single hard-coded λ. This null result further motivates the search spine over fixed-scalar tuning. See `next-slice-1ply-ceiling` memory.

## Held-out budget

Two append-only `run` ledger entries added (`config/eval/heldout_ledger.jsonl`), one per arm's config_hash, purpose `heldout-ab-mustreact-0.6v0.8-v1`, both first-look (no justification). Budget for these two config lineages is now spent.

## Provenance

- Kaggle `sb-heldout-mustreact08`, `REPO_SHA d7283242`, both arms `config/eval/schedules/t6_heldout_v001.yaml` + seed_base `t6heldout2026`, `server_patch 86e31891`, `showdown f8ac1400`, PYTHONHASHSEED=0.
- Candidate config_hash `13abaf725512ef8e` (results sha `bc840139…`); baseline `ced31adc69f89f5d` (results sha `4c5e6eef…`).
- Both arms run fresh on the SAME kernel/git_sha/server → the only difference is `SHOWDOWN_MUST_REACT_LAMBDA` (clean 1-variable pairing; Strategy B).
- Artifacts: `data/eval/t6/heldout-ab-mustreact08/` (results, seeds, manifests, paired report).
- Tooling: retargetable env-A/B kernel (`SCHEDULE_RELPATH`/`SEED_BASE` header fields), commit `d728324`, +8 tests.
