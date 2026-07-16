# Viewer v0 mockup dossier

**Status:** accepted design input; not an implementation plan

**Frozen:** 2026-07-16

This directory preserves the user-supplied ShowdownBot Studio Viewer v0 mockup package as a
reviewable design artifact. The HTML, print view, support script, and thumbnail are frozen source
material. Product requirements remain authoritative in
[`../../specs/viewer-v0-design.md`](../../specs/viewer-v0-design.md),
[`../../MASTER_SPEC.md`](../../MASTER_SPEC.md), and
[`../../architecture/PROJECT_BOUNDARIES.md`](../../architecture/PROJECT_BOUNDARIES.md).

![Viewer v0 dossier preview](thumbnail.webp)

## Contents

| File | Purpose |
|---|---|
| [`viewer-v0-design-dossier.html`](viewer-v0-design-dossier.html) | Interactive design dossier with six desktop mockups, state gallery, component inventory, tokens, keyboard model, and compliance matrix |
| [`viewer-v0-design-dossier-print.html`](viewer-v0-design-dossier-print.html) | Print-oriented rendering of the same dossier |
| [`support.js`](support.js) | Runtime helper required by the two preserved HTML artifacts |
| [`thumbnail.webp`](thumbnail.webp) | Package preview supplied with the dossier |

The HTML files are reference artifacts, not Studio runtime code. They must not be imported into the
Godot application or treated as an implementation template.

## Review verdict

The dossier is accepted as the visual direction for the Phase 0 analysis workbench. Its strongest
decisions align with the approved product boundaries:

- one offline replay and DecisionTrace bundle at a time;
- an abstract, sprite-independent doubles board;
- explicit `known`, `suspected`, `unknown`, and `not recorded` information states;
- structural candidate identity instead of table-position identity;
- prominent fail-closed, degradation, and missing-data states;
- a dense but resizable analysis workbench instead of a Showdown-client clone;
- keyboard-first navigation, bounded rendering, compact/comfortable density, and dark/light themes.

The dossier does not authorize implementation and does not resolve missing exporter or schema
contracts. Those remain separate design inputs.

## Binding corrections before implementation

### 1. Offline fonts

The preserved HTML references IBM Plex through Google Fonts. That is acceptable only for this
external mockup artifact. The Studio application must not make that network request. A future
implementation must either bundle a reviewed, license-compliant local font with its notices or use
an approved system-font stack. The Viewer v0 offline guarantee remains unchanged.

### 2. Platform-aware shortcuts

The mockups primarily display macOS-style shortcut labels such as `Cmd+O`. The initial desktop
target is Windows. Shortcut presentation must therefore come from a platform-aware label layer:
`Ctrl` on Windows/Linux and `Cmd` on macOS. The underlying actions and keyboard-first navigation
remain the same.

### 3. Missing data contracts

The following mockup values are design placeholders until the Python exporter and versioned bundle
schemas define them:

- decision latency;
- structured fallback reason;
- warning object shape and severity vocabulary;
- belief snapshot schema and the source of `suspected` information;
- `selection_stage` vocabulary;
- score components beyond fields already present in the recorded trace;
- state-summary fields not already represented by an approved DTO.

Godot must show `not recorded` or a degraded state when these values are absent. It must not infer
them from `config_hash`, synthesize defaults, or copy the illustrative values from the mockup.

## Additional implementation clarification

Candidate sorting and filtering may change presentation order, but never recorded identity or the
chosen candidate. The chosen row is always resolved by structural `candidate_key`; no sort mode may
rewrite or reinterpret the recorded selection.

## Provenance

The source archive was supplied by the user as `ShowdownBot mockups.zip`. Files were extracted and
renamed only for stable repository paths; their bytes were not edited.

| Artifact | SHA-256 |
|---|---|
| Source archive `ShowdownBot mockups.zip` | `63c7babd5305c4e3d9b834677d477f0518220d2d32bb8b9ff0d48be0a8cc2daf` |
| `viewer-v0-design-dossier.html` | `9270d0ccbf91658d97f1ed3f7be814aa9a2da28ce5436bf3633d7aee38599838` |
| `viewer-v0-design-dossier-print.html` | `2a94de687224d5d0ca67bc65d03fbe2009bfc3d0ac667c7dc882b605e7cb4f19` |
| `support.js` | `ae4f0ac8449655e17cca1e3b179effcb6817a3b0d8dc47f112a9c39c25c39fd7` |
| `thumbnail.webp` | `ea9d5b51414cb9268494cb5a2cfde2e982a16a31eaf9a6d4f6468f6b1e3121cb` |

Opening the preserved HTML may contact Google Fonts. This behavior belongs only to the external
design artifact and is explicitly forbidden for the offline Viewer implementation.
