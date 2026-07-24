# Viewer v0 — Plan E Manual Evidence (Screen-reader + Mixed-DPI)

Not a gdUnit gate (plan §0.10 / §5.7). These are honest, best-effort manual checks
filed as evidence for Plan F, not automated pass/fail.

## Mixed-DPI checklist (Task E5 draft — unfilled, filled at E5/F acceptance)

Move the `AppShell` window across two Windows monitors with different display
scaling (e.g. 100% and 150%), and record:

- [ ] Scale readability: at each monitor's native scaling, is text in the state
      banner, decision header, and provenance/hash surfaces legible without
      manual zoom?
- [ ] Control reachability: after moving the window, are the PathRow /Open
      button, timeline transport (`ReplayWorkspace`), and `DiagnosticsDock`
      still reachable (visible, not clipped, not off-screen)?
- [ ] Selected timeline entry preserved: select a timeline entry, drag the
      window to the other monitor, confirm the selection (and the decision
      workspace's synced row) is unchanged.
- [ ] Min window (1280×720, `WorkspaceLayout.MIN_WINDOW_SIZE`) still enforced
      after moving between monitors.

Result: _(unfilled)_

Notes: _(unfilled)_

## Screen-reader checklist (Task E6 draft — unfilled, filled at acceptance)

Best effort only (plan §0.10). Report what worked / failed; this checklist
**must not** be used to claim screen-reader completeness. Godot 4.5.2 has no
dedicated accessibility/SR backend in this branch — expect partial or no
support and record that honestly rather than skip the attempt.

Try Godot 4.5.2 (`AppShell`, fixture-01 loaded) with one OS screen reader
(Windows: Narrator, `Win+Ctrl+Enter` to start; or NVDA if installed) and
record:

- [ ] Launch: does the screen reader announce anything when the `AppShell`
      window gains focus (window title, any control)?
- [ ] State banner: moving focus to/near the `StateBanner`, is its text
      (e.g. `TEAM PREVIEW`, `DECISION RECORDED`) announced?
- [ ] Keyboard navigation: using Tab / Shift+Tab, does focus move between
      controls (PathRow / Open, timeline transport, candidate table,
      filter `LineEdit`, `DiagnosticsDock` tabs) in a sensible order, and is
      each focused control announced (name/role/value)?
- [ ] Candidate table: selecting a row via keyboard, is the selection or its
      content announced?
- [ ] Provenance/diagnostics tabs: switching `DiagnosticsDock` tabs via
      keyboard, is the active tab announced?
- [ ] Live updates: after a keyboard action changes the state banner or
      selected decision, is the change announced without manually re-focusing?

Result: _(unfilled)_

Notes: _(unfilled — record engine/SR versions used, and any controls found
completely silent or unreachable by keyboard)_
