# Gate A Report -- Smoke Test

**This is a smoke test. Per spec Sec.1, Gate A cannot license anything on its own** (it sweeps a small, fixed number of hand-built boards across field-bucket variants, no real corpus, no statistics) -- it is a fast connectivity/no-crash/no-diff sanity check that Gate B's real corpus run is worth doing, not evidence of correctness or strength by itself.

- report schema version: `gate-a-report-v1`
- source commit: `d21f30a760c8b9b147fe85002fe90fbb281c6b93`
- boards swept: 2 (`primary`, `single_target`)
- field variants swept: neutral, tailwind_both, tailwind_p1, tailwind_p2, trick_room, sun, rain (7 variants)
- total rows (boards x variants): 14
- elapsed seconds: 46.5
- **exception count: 0**
- **diff count (action changed off vs on): 0**

## Result

Zero exceptions, zero action diffs across all 14 (board x field-variant) combinations -- `SHOWDOWN_ACCURACY_MODE=1` runs cleanly and does not change the chosen action on any of the 2 boards swept under any of the 7 field variants swept. This is a necessary precondition for a real Gate B run, not a substitute for one.

## All rows

| board | field_variant | action_changed | exception | off_chosen_action | on_chosen_action |
| --- | --- | --- | --- | --- | --- |
| primary | neutral | False |  | `/choose move 3, move 3|2` | `/choose move 3, move 3|2` |
| primary | tailwind_both | False |  | `/choose move 3, move 3|2` | `/choose move 3, move 3|2` |
| primary | tailwind_p1 | False |  | `/choose move 3, move 3|2` | `/choose move 3, move 3|2` |
| primary | tailwind_p2 | False |  | `/choose move 3, move 3|2` | `/choose move 3, move 3|2` |
| primary | trick_room | False |  | `/choose move 3, move 3|2` | `/choose move 3, move 3|2` |
| primary | sun | False |  | `/choose move 3, move 3|2` | `/choose move 3, move 3|2` |
| primary | rain | False |  | `/choose move 3, move 3|2` | `/choose move 3, move 3|2` |
| single_target | neutral | False |  | `/choose move 1 2, move 2 2|2` | `/choose move 1 2, move 2 2|2` |
| single_target | tailwind_both | False |  | `/choose move 1 2, move 2 2|2` | `/choose move 1 2, move 2 2|2` |
| single_target | tailwind_p1 | False |  | `/choose move 3, move 3|2` | `/choose move 3, move 3|2` |
| single_target | tailwind_p2 | False |  | `/choose move 1 2, move 2 2|2` | `/choose move 1 2, move 2 2|2` |
| single_target | trick_room | False |  | `/choose move 1 2, move 2 2|2` | `/choose move 1 2, move 2 2|2` |
| single_target | sun | False |  | `/choose move 1 2, move 2 2|2` | `/choose move 1 2, move 2 2|2` |
| single_target | rain | False |  | `/choose move 1 2, move 2 2|2` | `/choose move 1 2, move 2 2|2` |

## Provenance note

This report was rendered from the already-real Gate A sweep committed in Task 9 (commit `57b7f36`) -- the sweep itself was NOT re-run for this report (per the accuracy-offline-gate plan's Task 11 instructions).

