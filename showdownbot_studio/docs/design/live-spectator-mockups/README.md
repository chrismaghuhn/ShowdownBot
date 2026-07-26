# Live Spectator mockup set

**Status:** target picture (Zielbild) for discussion — **not** an approved design, **not** an
implementation plan, and in part **not authorized scope at all**. See the scope boundary below
before citing anything from it.

**Frozen:** 2026-07-26

This directory preserves a four-artboard mockup set for the Phase 3 Live Spectator workspace,
produced after M1 closed and after the four UX decisions in
[`../../research/2026-07-showdown-client-user-research.md`](../../research/2026-07-showdown-client-user-research.md)
§8.3.2 were taken. Product requirements remain authoritative in
[`../../specs/2026-07-25-phase3-client-design.md`](../../specs/2026-07-25-phase3-client-design.md),
[`../../MASTER_SPEC.md`](../../MASTER_SPEC.md) and
[`../../architecture/PROJECT_BOUNDARIES.md`](../../architecture/PROJECT_BOUNDARIES.md).

## Scope boundary — read this first

| Artboard | Status |
|---|---|
| **01 Standardlayout** | Shows what M1 already delivers (battle board, log, connection, room controls, diagnostics) in a target visual treatment. The *capabilities* are built and merged; the *styling and layout* are proposals |
| **02 Layout bearbeiten** | A widget library, drag/resize handles and a docking editor. **No approved spec contains a layout editor.** Pure exploration |
| **03 Appearance Editor** | Theme gallery, colour tokens, background image, per-widget overrides. Themes and customisation are **Phase-4 territory** per `MASTER_SPEC.md` §4. Pure exploration |
| **04 Komponentenblatt** | Component states. The eight room-control states are **not proposals**: they are the rows of the binding `RoomState` table in [`../../architecture/LIVE_STATE_MACHINES.md`](../../architecture/LIVE_STATE_MACHINES.md), reproduced with their exact English wording. Everything else on the sheet is proposal |

A polished picture of unbuilt functionality creates pull toward building it. That is why the scope
line is stated here, in the artboard's own banner, and in the plate under artboards 02 and 03.
Nothing in this set authorizes work; each of Phases 2, 4 and 5 still needs its own approved design.

Deliberately absent, per the brief and per the Phase-3 spec's own v1 scope: **login, chat and
`/choose`**.

## Contents

| File | Purpose |
|---|---|
| [`live-spectator-mockups.html`](live-spectator-mockups.html) | Four artboards (1600 px each) on a zoom canvas, with annotation and docking-grid toggles |

## Provenance

- **Style DNA:** the owner-supplied clean-desktop prototype (`ShowdownBot Studio UX` package,
  supplied 2026-07-26). Its token values are reproduced verbatim — surfaces `#f8f9fa`/`#dfe3e6`,
  lines `#c3c9ce`/`#9aa4ab`, text `#22282d`/`#5f6a72`, accent `#4c789c`, semantic
  `#579164`/`#b28734`/`#b65d57`, top bar `#2f3c46`, radius 6 px, Arial for the app surface. The
  prototype itself is not redistributed here.
- **Battle data is real, not placeholder.** The four-slot board reproduces the frozen golden
  fixture at [`../../../fixtures/live-protocol-v0/local-spectate-01/`](../../../fixtures/live-protocol-v0/local-spectate-01/)
  — a real `gen9randomdoublesbattle` captured from the pinned local server: Brambleghast and Emboar
  against Scream Tail and Poliwrath, with Electric Terrain.
- **Room-control wording** is copied from `LIVE_STATE_MACHINES.md`, including the two send-failure
  states that came out of owner review during the M1 hardening slice.
- **Diagnostics reasons** shown on artboard 01 are the reasons the implementation actually emits
  (`unhandled_type`, `inconsistent_state`, `room_not_confirmed`), not invented labels.

### Byte identity

`live-spectator-mockups.html` is pinned by content hash so a later edit is visible rather than
silent:

```text
sha256  657538c8dd42016636235cd48ac5382cc2f0763d9ba3e584faddb233684c8381
bytes   58948
```

The repository's `.gitattributes` forces LF for this directory so the hash survives a checkout on
any platform, the same rule the Viewer v0 mockups and the protocol fixtures already use.

## Design decisions visible in the set

Three of the four UX decisions taken on 2026-07-26 are shown rather than described:

- **Diagnostics have their own widget** (artboard 01, lower right). The battle log carries battle
  history only — the decision that came out of the M1 live gate, where roughly four in five log
  lines turned out to be diagnostics.
- **State is never colour alone.** Terrain carries a square, Tailwind a triangle, connection a dot,
  each with text, per `MASTER_SPEC.md` §5's redundant-encoding requirement.
- **The motif is shown at 30 % and 70 % dimming side by side** (artboard 04), which is what makes
  the 70 % default arguable instead of arbitrary.

The fourth decision — direct send versus a two-step choice review — is **not** depicted, because it
belongs to M2's choice UI and this set contains no move selection.
