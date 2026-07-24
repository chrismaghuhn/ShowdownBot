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

## Screen-reader checklist (Task E6 scope — placeholder only)

`ponytail:` Task E6 owns adding the actual SR steps to this file (plan §6 Task
E6 / §0.10) — this section is a placeholder heading only, left unfilled by
Task E5.

Result: _(unfilled — Task E6)_
