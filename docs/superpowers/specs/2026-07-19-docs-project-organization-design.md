# Documentation Project Organization Design

**Status:** APPROVED

**Date:** 2026-07-19

**Scope:** Repository documentation paths and navigation only

## 1. Problem

The repository's top-level `docs/` directory is small, but almost all detailed
documentation is stored in three flat workflow-oriented directories:

- `docs/superpowers/specs/` — 53 files
- `docs/superpowers/plans/` — 59 files
- `docs/superpowers/reviews/` — 2 files

This makes a project's design, implementation plan, audit, and review difficult
to discover together. The workflow name (`superpowers`) is also not a useful
subject classification for readers.

The migration is not a cosmetic file move. Exact documentation paths appear in
code comments, tests, reports, README files, ROADMAP/PROJECT_INDEX, and other
documents. Some historical evidence is byte-frozen and must not be rewritten.

## 2. Goals

1. Organize documentation primarily by project or domain.
2. Keep each project's specs, plans, audits, and reviews close together.
3. Preserve every existing document and its Git history.
4. Give humans and agents one obvious place to create future documents.
5. Update live references without mutating byte-frozen evidence.
6. Make old paths auditable through an explicit migration map.

## 3. Non-goals

- Rewriting, summarizing, merging, or deleting historical documents.
- Renaming existing document filenames.
- Changing production behavior, configuration, tests, or evidence semantics.
- Editing frozen `data/eval/**` artifacts.
- Reorganizing `reports/`, `data/`, or source-code directories.
- Modifying any of the eight protected worktrees from the cleanup pass.

## 4. Target structure

```text
docs/
├── README.md
├── ROADMAP.md
├── PROJECT_INDEX.md
├── PATH_MIGRATION.md
├── architecture/
│   └── brain-v1-northstar.md
├── guides/
│   └── heuristic-bot/
└── projects/
    ├── champions/
    │   ├── specs/
    │   ├── plans/
    │   └── audits/
    ├── accuracy/
    │   ├── specs/
    │   ├── plans/
    │   └── audits/
    ├── evaluation/
    │   ├── specs/
    │   ├── plans/
    │   ├── audits/
    │   └── reviews/
    ├── learning/
    │   ├── specs/
    │   ├── plans/
    │   └── audits/
    ├── core-bot/
    │   ├── specs/
    │   └── plans/
    └── operations/
        ├── specs/
        └── plans/
```

Only directories that receive files are created. `ROADMAP.md` and
`PROJECT_INDEX.md` stay directly under `docs/` because they are the two global
status surfaces.

## 5. Classification rules

Classification is by subject, not by date or original workflow phase.

### 5.1 Champions

Champions FormatConfig, panel, Mega I7/I7b, I8 latency, latency reduction,
opponent-Mega, and their status/audit documents.

### 5.2 Accuracy

Hit probability, cap derisking, offline accuracy gates, default-on work, and
accuracy-specific strength measurement.

### 5.3 Evaluation

Gauntlet/evaluation harnesses, schedules and seeds, result JSONL, reporting,
heldout gates, provenance, diagnostics, candidate-versus-baseline comparison,
forced replacement determinism, and evaluation reviews.

### 5.4 Learning

Reranker data and features, datagen/retraining, shadow and gated override work,
feature ablation, dataset/reranker audits, teacher disagreement, sampling,
aggregation, benchmark ingestion, and value calibration.

### 5.5 Core bot

The initial VGC bot/client/engine phases, heuristic move and condition support,
opponent sets and speed, own-team speed truth, simulator/decision adapter/hloop,
opponent belief, export integration, persistent calc, and core decision-policy
mechanics such as fast-board Protect discipline.

### 5.6 Operations

Repository-operational documentation such as root instruction restoration.

### 5.7 Ambiguous documents

The implementation plan must contain a complete old-path to new-path manifest
covering every source file before any move occurs. A document that spans domains
is assigned to the domain that owns its acceptance gate; cross-domain discovery
is provided by links in `docs/README.md`, not by duplicate copies.

## 6. Migration mechanics

1. Capture the complete source inventory and file hashes.
2. Build and review a one-to-one path manifest.
3. Move files with `git mv`; preserve every filename.
4. Move `docs/heuristic_bot/*` to `docs/guides/heuristic-bot/`.
5. Update references in mutable repository files.
6. Add `docs/README.md` and `docs/PATH_MIGRATION.md`.
7. Remove the empty `docs/superpowers/` and `docs/heuristic_bot/` directories.

The migration is one atomic branch/PR so the rename set and all live reference
updates cannot land separately.

## 7. Reference policy

### 7.1 Mutable references

Update exact old paths in:

- repository README and instruction files;
- ROADMAP and PROJECT_INDEX;
- source comments/docstrings;
- tests, including tests that open a documentation file;
- documentation and non-frozen reports;
- scripts and tooling.

### 7.2 Immutable historical evidence

Do not edit byte-frozen `data/eval/**` artifacts. Any old documentation path
inside such an artifact remains a historical statement about the path that
existed when it was produced.

Before updating a report, check whether its bytes are pinned by a manifest,
hash, or frozen evidence contract. A pinned report is treated like immutable
evidence and is not rewritten.

`docs/PATH_MIGRATION.md` records every old and new path so historical references
remain resolvable by a reader without retaining redirect stubs or duplicate
documents.

## 8. Future placement rules

`docs/README.md` defines the reader-facing convention:

- new specs: `docs/projects/<project>/specs/`
- new plans: `docs/projects/<project>/plans/`
- audits: `docs/projects/<project>/audits/`
- reviews: `docs/projects/<project>/reviews/`
- user guides: `docs/guides/<topic>/`
- cross-project architecture: `docs/architecture/`

`CLAUDE.md` receives the same concise placement rule so the removed
`docs/superpowers/` hierarchy is not recreated by the next agent task. The root
`README.md` documentation table is updated to point readers to `docs/README.md`
and `docs/projects/`.

Protected worktrees keep their current contents. Before any of their branches is
merged later, its documentation paths must be rebased or translated to the new
layout; it must not reintroduce `docs/superpowers/`.

## 9. Validation contract

The migration is complete only when all of the following pass:

1. Every source document appears exactly once in the path manifest.
2. Pre-move and post-move content inventory accounts for every document.
3. No duplicate destination path exists.
4. `docs/superpowers/` and `docs/heuristic_bot/` are absent.
5. No stale `docs/superpowers` or `docs/heuristic_bot` reference remains in a
   mutable file.
6. Frozen evidence hashes are byte-identical to `main`.
7. All relative Markdown links resolve.
8. Tests that read documentation paths pass.
9. The full repository suite and CI pass.
10. `git diff --check` is clean and committed blobs are LF-stable.

The stale-reference scan explicitly excludes protected worktrees and immutable
historical evidence; findings in those locations are reported, not rewritten.

## 10. Delivery boundaries

The implementation changes paths and references only. It performs no server,
battle, benchmark, latency gate, Strength run, or evidence generation. Champions
Strength remains governed by its existing gates and is unrelated to this docs
organization migration.
