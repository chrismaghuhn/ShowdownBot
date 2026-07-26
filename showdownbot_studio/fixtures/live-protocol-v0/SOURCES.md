# Live protocol fixtures — sources

## `local-spectate-01/transcript.jsonl` + `local-spectate-01/golden_events.jsonl`

- Captured from the repository's pinned local `pokemon-showdown` checkout
  (`~/.cache/showdownbot/pokemon-showdown`, commit `f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5`,
  `--no-security`, port 8000).
- Two throwaway local-only accounts (`studiobota`/`studiobotb`) battled each other in
  `gen9randomdoublesbattle` (random teams, no packed team needed); every decision was answered
  with `/choose default|<rqid>`, the server's own `autoChoose()` (no `showdown_bot` decision
  logic in the loop). A third throwaway account (`studiowatcher`) joined the created battle room
  as a pure spectator (`|/join battle-...`) partway through and recorded every raw WebSocket
  message it received, verbatim, until the battle's own `|win|` line.
- `transcript.jsonl`: one JSON object per **frame** (`{"sequence", "raw_frame"}`), raw and
  unmodified, exact multi-line frame boundaries preserved as JSON string escapes. No chat content,
  no credentials. 26 frames, one full battle (turn 1 through `|win|studiobotb`).
- `golden_events.jsonl`: the exact expected `DECODED_STATE_EVENT` sequence (153 events),
  hand-verified line by line against the raw frames before being frozen, and captured/reviewed
  *before* `protocol/protocol_decoder.gd` existed at all (spec section 8.1; Tasks 13–15 implement
  against this file, not the reverse). Includes multiple real slash-less `"0 fnt"` cases (Task 14's
  regression fix) and a real `-fieldstart`/`-fieldend` (Electric Terrain) pair — both genuine
  artifacts of the captured battle, not constructed test data. The 9 real `"0 fnt"` `-damage`
  events (coordinator code-quality review) additionally assert `"hp_fainted": true` plus explicit
  `"hp_maximum": null`/`"hp_status": null` for full-field parity — not just `hp_current`, so the
  golden comparison proves the fainted flag itself on the real-transcript path, not only on the
  synthetic case in `test_protocol_decoder_battle_state.gd`. Re-confirmed green against the
  enriched golden with no decoder change required.
- Captured for M1b (`docs/plans/2026-07-25-phase3-m1-connect-spectate.md`) on 2026-07-25.

## `local-noinit-nonexistent-01/transcript.jsonl` + `local-noinit-nonexistent-01/golden_events.jsonl`

- Captured from the same repository-pinned local `pokemon-showdown` checkout
  (`~/.cache/showdownbot/pokemon-showdown`, commit `f8ac14003a5f27e1bdc8d8c59608a773c1cb96e5`,
  `--no-security`, port 8000) as `local-spectate-01`, started via
  `godot/tools/start_local_showdown_server.ps1`.
- A single throwaway, unauthenticated WebSocket connection sent `|/join
  battle-studio-nonexistent-room-capture` for a room ID that does not exist on the server, and the
  server's own rejection frame was recorded verbatim. No chat content, no credentials, no named
  account.
- `transcript.jsonl`: one frame (`{"sequence": 0, "raw_frame"}`) -- the server's real
  `tryJoinRoom()` rejection (`server/users.ts` ~1305, verified directly against the pinned
  checkout's own source): `>battle-studio-nonexistent-room-capture\n|noinit|nonexistent|The room
  "battle-studio-nonexistent-room-capture" does not exist.` -- never `|error|`, which is what
  `protocol/protocol_decoder.gd` incorrectly assumed before this fixture was captured (owner
  finding 3, M1 hardening, 2026-07-26).
- `golden_events.jsonl`: the single expected `DECODED_STATE_EVENT` (`event_type: "noinit"`,
  `noinit_subtype: "nonexistent"`, `error_reason` carrying the server's own message verbatim).
- The sibling `joinfailed` subtype (`server/users.ts` ~1310-1335: invite-only room, tournament
  join rejection, room ban, groupchat ban) is real and documented in the same pinned server source
  but was not captured live for this fixture set -- reproducing it requires a trusted/authenticated
  connection and a pre-existing private room, both out of this finding's scope. Its decode path is
  covered by a non-transcript unit test
  (`test_noinit_joinfailed_line_decodes_with_subtype_and_reason`,
  `godot/tests/protocol/test_protocol_decoder_room_lifecycle.gd`) using the exact wire shape from
  that source, not a live capture.
- Captured for the M1 hardening slice (owner finding 3, `docs/plans/2026-07-25-phase3-m1-implementation-watchlist.md`) on 2026-07-26.

## Bounded-vocabulary note

The real battle naturally produced several genuine, valid Showdown protocol message types beyond
the illustrative list in the M1b plan's Task 13 code sample (`-ability`, `-unboost`, `-boost`,
`-resisted`, `-crit`, `-supereffective`, `-singleturn`, `-fail`, `-activate`, `-enditem`,
`upkeep`), plus the empty-body separator line (`|`) Showdown emits between event batches. These
are real, valid, and recognized -- never silently dropped, never mistaken for a genuinely
unrecognized line (this plan's own stated intent for `KNOWN_IGNORED_EVENT`). `ProtocolDecoder`'s
`_KNOWN_IGNORED_TYPES` (Task 13) is widened to name all of them explicitly, each a candidate for
later, deliberate promotion to `DECODED_STATE_EVENT`. `golden_events.jsonl` records only what
`event_decoded` fires for (unchanged in shape from the plan); everything else in the real
transcript is `KNOWN_IGNORED_EVENT`, never `UNKNOWN_EVENT` -- the contract test's own
`assert_int(unrecognized.size()).is_equal(0)` requires exactly this.

## Official-server capture — NOT included in this fixture set

Requires separate owner approval under `AGENTS.md`'s controlled-live-test rule; not performed for
M1 (owner decision recorded 2026-07-25, reaffirmed at both review passes).
