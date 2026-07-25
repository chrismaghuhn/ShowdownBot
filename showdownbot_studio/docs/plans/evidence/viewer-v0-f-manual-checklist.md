# Viewer v0 — Plan F Manual Checklist (F2)

Produced per [`2026-07-21-viewer-v0-f-e2e-acceptance.md`](../2026-07-21-viewer-v0-f-e2e-acceptance.md)
§4 F2, following the §0.7 capture recipe. Extends
[`viewer-v0-e-manual-checks.md`](viewer-v0-e-manual-checks.md) (Plan E's SR/DPI templates,
reproduced and filled below, not duplicated as a second document) rather than replacing it.

**Build under test:** `studio/plan-f-acceptance` @ `fd0e5176d03443fa248ce43b9e057382b8cfdbf8`.
**Engine:** pinned `Godot_v4.5.2-stable_win64_console.exe`
(`showdownbot_studio/godot/tools/engine/`). **Date:** 2026-07-24.
**Fixture:** `fixture-01` (`fixtures/viewer-v0/bundles/fixture-01`).

## 0.5 Headless blind spot (binding limitation — documented per §4 F2)

A throwaway `SceneTree` probe run against the pinned engine (plan §0.5) found that under
`--headless`, `DisplayServer.window_get_min_size()` reads back `(0, 0)` regardless of what
`WorkspaceLayout._ready()` sets it to, while the same call under a real (non-headless) run reads
back the true `(1280, 720)`. Godot's headless `DisplayServer` stub does not model window geometry
at all. Consequently:

- `run_gdunit_headless.ps1` (always `--headless`) **cannot** verify that `WorkspaceLayout`'s
  `window_set_min_size` call has any real on-screen effect — `godot/tests/workspace/test_workspace_layout.gd`'s
  `test_min_window_set` can only assert the setter was *called*, never that geometry actually
  took effect.
- The same blind spot applies to anything else that depends on real window/viewport
  dimensions: primary-control reachability at 1280×720, text overflow, and the scale/density
  visual effects captured below. None of this is observable through the headless API at all —
  it is not merely untested, it is *unobservable* by any gdUnit suite as currently invoked.
- This is why the captures below (produced by launching the engine **without** `--headless`,
  per §0.7 step 2) are load-bearing evidence, not a redundant manual re-check of something
  gdUnit already proves. No amount of additional headless gdUnit test-writing can close this
  gap; only a real (non-headless) capture can.

## Captures

All three PNGs below are fresh captures from this session against the build/commit above, using
the throwaway `showdownbot_studio/godot/_shot.gd` script (§0.7; deleted before commit, never
shipped). Command shape:

```powershell
& "<engine>\Godot_v4.5.2-stable_win64_console.exe" --path <project> -s res://_shot.gd `
  --resolution <W>x<H> -- "--out=<png>" "--w=<W>" "--h=<H>" ["--scale=<factor>"]
```

Each run printed `SHOT status: Loaded | declared=REPLAY_TRACE | effective=REPLAY_TRACE`,
`SHOT loaded: true`, `SHOT save_png err: 0` — fixture-01 loaded successfully and the PNG was
written without error in all three runs.

| # | File | Size | Notes |
|---|---|---|---|
| 1 | [`fixture-01-1280x720-2026-07-24.png`](viewer-v0-f-visual-capture/fixture-01-1280x720-2026-07-24.png) | 1280×720 | spec minimum, 100% scale, Comfortable density |
| 2 | [`fixture-01-1400x900-2026-07-24.png`](viewer-v0-f-visual-capture/fixture-01-1400x900-2026-07-24.png) | 1400×900 | larger size per §0.7 step 3, 100% scale |
| 3 | [`fixture-01-1280x720-scale200-2026-07-24.png`](viewer-v0-f-visual-capture/fixture-01-1280x720-scale200-2026-07-24.png) | 1280×720 | `set_ui_scale(2.0)` applied post-load, to check the named 200%-scale limitation |

Each was opened and visually inspected (not just checked for "file exists") before writing the
rows below.

## Acceptance rows

### Primary-control reachability at 1280×720 (§0.8) — **PASS, verified against fresh capture**

Checked directly in capture #1, cropped and re-inspected at native resolution (not inferred from
the changelog):

- **Timeline transport row** (`Prev`/`Next`/`Start`/`End`/`Play`): fully visible at the bottom-left
  of the window, no clipping, all five buttons legible and unobstructed.
- **PathRow / Open row**: fully visible at the top of the window (`Open` button flush against the
  right edge, not clipped).
- **DiagnosticsDock** (Provenance/Warnings/Raw tabs, right column): the dock frame and its tab bar
  are fully inside the window; the content list inside it (schema/trace_schema_version/format_id/…)
  is taller than the visible area and scrolls internally — that is normal dock behavior, not an
  overflow/clipping defect, and the dock's own scrollbar is visible and reachable.

**This reverses the §0.8 note.** §0.8 (citing a gap analysis against `studio/plan-e-layout-shell`
tip `0cd93f2`, a branch not present in this worktree) reported the transport row and lower
provenance rows **unreachable** at 1280×720, with "a fix reported in flight." This capture — taken
against the now-merged `main @ 5feaa7c` (Plan E fully merged via PR #71) — shows the fix landed:
all three control groups the plan asked about are reachable. Not carrying forward the old note as
evidence; this row is decided by the fresh capture alone.

### Monospace hash surfaces — **PASS, verified against fresh capture**

Cropped capture #1 and #2 at the Provenance tab. `request_hash`, `observable_state_hash`,
`config_hash`, `source_hashes_battle_log`, `source_hashes_decision_trace`, and `git_sha` all render
in a visibly fixed-width face (uniform per-glyph width, distinct from the proportional face used
for their labels and for surrounding chrome such as button/tab text). `StudioMonoFont.apply_to()`
is wired into `diagnostics_dock.gd` (confirmed by reading the merged source, not just the plan
text — the "value/text controls... do NOT call `StudioMonoFont.apply_to()` yet" deferral comment
cited by Plan F §0.9 is no longer present at `diagnostics_dock.gd:27,84`), consistent with what
the capture shows.

### Scale controls (§0.8) — **PASS: reachable and wired, NOT "not yet wireable"**

§0.8 said UI scale had "no visible effect, no reachable control, no keyboard shortcut." That no
longer holds at F2 time — verified, not inferred:

- The `Scale:` `OptionButton` (75/100/150/200%) and `Density:` toggle button are both visible and
  reachable at the top of the window in every capture.
- Calling `WorkspaceLayout.set_ui_scale(2.0)` (capture #3) produces a large, unmistakable visible
  effect — see the known defect below.

**Known limitation, verified by capture, not assumed:** at 1280×720 with scale = 200%, capture #3
shows severe overlap — the enlarged `PathRow`, `ScaleRow`, `StateBanner`, and `StatusLabel` text
draw on top of one another (e.g. "decision #0" is superimposed directly over "Scale: 100% ...
Density: Comfortable"), the timeline transport row and the decision-list column are pushed
entirely off-frame, and no scrollbar or reflow recovers any of it. This matches the task's named
hypothesis: `WorkspaceLayout extends Control` (`godot/src/workspace/workspace_layout.gd:2`), not
`Container`, so it does not propagate its children's minimum size when the runtime theme's
`default_font_size` grows — the parent `VBoxContainer` never learns the rows got taller and does
not reflow around them. **This is a real, reproduced defect, not a hypothetical** — filed here,
not fixed (out of scope per Plan F §0.4, "Plan F records these as named, checkable acceptance
rows, it does not implement UI fixes").

### Density controls (§0.8) — **PASS: reachable and produces a small but real visible effect**

Same-region crops of the Comfortable (capture #1) and a scratch Compact-density capture (not
filed as evidence, same commit, same fixture, same window size) show Compact tightening the
gap between rows (`BoxContainer`/`GridContainer` `separation` constants, per
`workspace_layout.gd:102-106`) — subtle (a few px per row) but consistently present across the
button row, filter row, and Overview text block. The density toggle button label also updates
("Density: Comfortable" ↔ "Density: Compact"). Recording as **wireable**, not "not yet wireable" —
§0.8's gap analysis does not still hold for density either at F2 time.

## SR smoke-note (Plan E §0.10 template, Choice Point 4 = J2: filed, not required to pass)

**PERFORMED by the owner, 2026-07-25, against `main` @ `9a76507`** (Windows Narrator, real
interactive desktop session, fixture-01 loaded). This supersedes the earlier "not performed"
marker, which was accurate when written — the agent session driving the engine from PowerShell had
no screen reader attached.

**Owner's reported observation, verbatim in substance:** the screen reader **did read content out**.

**Scope of what that establishes — read this before citing it.** The owner reported the outcome at
the level of "it actually read things out". The six template rows below are therefore recorded as
**not separately itemised**: it is established that announcements happen and carry content, and it
is *not* established which specific surfaces (banner vs tab titles vs table rows vs live updates)
were each announced. Ticking all six from a single summary observation would be exactly the
over-claim Plan F's honesty rules forbid. If per-row detail is ever needed, the run must be
repeated with each row observed individually.

The template (from [`viewer-v0-e-manual-checks.md`](viewer-v0-e-manual-checks.md)) is kept below
so F5 can point at one place:

- [ ] Launch: does the screen reader announce anything when the `AppShell` window gains focus?
- [ ] State banner: is `StateBanner` text announced?
- [ ] Keyboard navigation: sensible Tab order, each control announced?
- [ ] Candidate table: row selection announced?
- [ ] Provenance/diagnostics tabs: active tab announced on switch?
- [ ] Live updates: state-banner/selection changes announced without re-focusing?

**Result:** performed; the screen reader announces content. Better than the pre-run expectation,
which was that a non-native UI toolkit would announce little or nothing — Godot 4.5 ships
AccessKit-based accessibility, which is the plausible reason, though the owner's observation is the
evidence here, not that attribution.

**Still not a "pass" claim.** Per Choice Point 4 (§0.11, CLOSED: J2) this section is *filed and
signed off*, never *passed*, and Plan E §1 keeps screen-reader completeness an explicit non-goal.
Nothing here asserts the viewer is accessible — only that announcements were heard.

## Mixed-DPI checklist (Plan E §0.10 template, Choice Point 4 = J2: filed, not required to pass)

**PERFORMED by the owner, 2026-07-25, against `main` @ `9a76507`.** Supersedes the earlier
"not performed" marker, which was accurate when written.

**Owner's reported result:** clicked through the application including density switching, and
reported it "looks clean" — no layout shift, nothing cut off, no visible breakage across the checks
below.

**Obstacle encountered and worked around, recorded because it is itself a defect:** the window
could not be dragged to the second monitor at all, because PR #77 had set the default window size
to exactly 1920×1080 on a 1920×1080 screen — the title bar lands off-screen and there is nothing to
grab. Worked around with `Win + Shift + ←/→`, which moves a window between monitors without the
mouse. Fixed separately (default reduced to 1600×900); see that change for the reasoning.

- [ ] Scale readability across monitors at native scaling
- [ ] Control reachability preserved after moving the window
- [ ] Selected timeline entry preserved across the move
- [ ] Min window (1280×720) still enforced after moving between monitors

**Result:** performed; reported clean. Recorded at the granularity the owner reported it — a
whole-application click-through including density switching, not four independently observed rows.
The rows are left unticked for the same reason as the SR section: a single summary observation does
not license ticking each row individually.

## Owner sign-off (Choice Point 4, §0.11 CLOSED: J2)

J2 requires this checkbox in addition to filing — it attests the evidence above was **produced
and reviewed**, not that every row **passed**.

Both the SR and mixed-DPI sections have now been **performed** by the owner (2026-07-25, against
`main` @ `9a76507`) and are no longer the unfilled gaps an earlier revision of this paragraph
described. What they are *not* is a pass claim: each is recorded at the granularity the owner
actually observed, with its template rows deliberately left unticked and marked "not separately
itemised". Plan E §1 keeps screen-reader completeness an explicit non-goal, and Choice Point 4
(§0.11, CLOSED: J2) asks for filed-and-signed-off, never passed.

- [X] Owner has reviewed this checklist and its three captures.

## Findings that disagree with prior notes (report per plan §0.7 honesty boundary)

1. **§0.8's reachability note was stale, not current.** It cited a different, unmerged branch
   (`studio/plan-e-layout-shell` @ `0cd93f2`) and explicitly warned "a fix is reported in flight...
   Plan F must not describe this as fixed." That warning no longer applies: Plan E fully merged
   (`main @ 5feaa7c`, PR #71) before this capture, and the fresh capture shows all three named
   control groups reachable. Flipped to **PASS**, not carried forward as "fix in flight."
2. **§0.8's scale/density "not yet wireable" framing was also stale.** Both controls are reachable
   and both produce a real, verified visible effect as of this build — scale severely (to the point
   of an overlap defect at 200%/1280×720), density subtly. Recorded as wireable-with-a-known-defect,
   not "not yet wireable."
3. The 200%-scale overlap defect the task asked to verify (`WorkspaceLayout extends Control` not
   `Container`) **is real and reproduced**, not merely hypothesized — see capture #3.
