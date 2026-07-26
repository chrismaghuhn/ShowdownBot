# Phase 3 M1 (Connect + Spectate) — milestone gate-evidence packet

**Date:** 2026-07-26. **Base:** `main @ f5d88b0` (verified: `git log -1 --format="%H" main` ==
`f5d88b0f7ea584d564104a73585bd5162c6d1b56`, which is also PR #96's own `headRefOid` — the hardening
PR is the current tip of `main`).

This document records the evidence state of Phase 3 Milestone M1 (Connect + Spectate) as of
2026-07-26. **It does not itself close the milestone.** Per `docs/ROADMAP.md`'s own current wording
and per §9 gate 16 of the design spec, closing M1 requires an owner review-and-approval step this
document cannot perform on its own behalf, plus a manual live gate (gate 6) that has not been
attempted. Everything below is either directly verified in this session (commands run, output
quoted) or explicitly marked unverified/pending with the reason.

---

## 1. What M1 delivered

Five sub-slices plus a hardening slice, each its own PR, each verified against GitHub directly
(`gh pr view <n> --json number,title,state,mergedAt,headRefOid`), not copied from a commit message
or an earlier doc:

| Slice | PR | State | Merged (UTC) | `headRefOid` | Branch | Contribution |
|---|---|---|---|---|---|---|
| Phase 3 design + F0 | #88 | MERGED | 2026-07-25T11:30:39Z | `dcdc612f` | — | Approved client-design spec; `StudioRoot`/`WorkspaceRouter` boundary; `BattleBoardSnapshot`/`bind()` extraction; the four state machines fixed and published; the six required `docs/security/*.md` docs plus `docs/architecture/{LIVE_STATE_MACHINES,MODULE_CATALOG}.md`; `studio-security-invariants` CI lane |
| M1 plan approval | #90 | MERGED | 2026-07-25T13:58:23Z | `10888650` | — | Approves the M1 connect+spectate implementation plan and the binding watchlist that governs every M1 PR |
| M1a — transport | #91 | MERGED | 2026-07-25T14:43:31Z | `e3716ee1` | `feat/studio-m1a-transport` | `net/WebSocketTransport`, `ConnectionStateMachine` (12-row `ConnectionState`), `SocketPeerPort` seam, `connection_epoch`, `CONNECTING` timeout + cancel, reconnect backoff + `EXHAUSTED` |
| M1b — protocol | #92 | MERGED | 2026-07-25T19:45:41Z | `fade81be` | `feat/studio-m1b-protocol` | `protocol/ProtocolDecoder` (golden-fixture-first), `protocol/dto/ProtocolEventDTO`, `RoomStateMachine` (11-row `RoomState`), `ProtocolCommandEncoder` (join/leave only), `studio-protocol-contract` CI lane |
| M1c — derived state | #93 | MERGED | 2026-07-25T20:57:52Z | `ec494499` | `feat/studio-m1c-battle` | `battle/dto/LiveBattleSnapshot` (structurally immutable), `LiveBattleReducer`, `LiveBattleProjection` (sole owner of current snapshot + timeline), fail-closed handling of inconsistent events |
| M1d — spectating | #94 | MERGED | 2026-07-26T00:05:51Z | `6df03727` | `feat/studio-m1d-spectator-ui` | `ObservationEventBus`, `ui/panels/` (board, connection status, log), `RoomEntryPanel`, `SpectatorRoomGateway`, `LiveClientWorkspace`, reachable `StudioRoot` navigation, `studio-live-local-e2e` CI lane against the pinned local server |
| M1e — reconnect | #95 | MERGED | 2026-07-26T00:48:53Z | `38c35b42` | `feat/studio-m1e-reconnect` | `RoomStateMachine` emits `automatic_rejoin_requested`; `LiveBattleProjection` resets and rebuilds from scratch on repeat `init`, proven against a poisoned pre-state; full ten-step reconnect chain test through the real net/+protocol/+battle/ wiring |
| Hardening | #96 | MERGED | 2026-07-26T03:24:30Z | `f5d88b0f` | `feat/studio-m1-hardening` | Closes owner-review findings across all five sub-slices (§5 below); this is the commit at the tip of `main` |

All seven `headRefOid` values above were fetched live from GitHub in this session, not read from a
document. `git log --merges` shows no merge-commit marker for PRs #91–#96 (they were merged as
linear history, not `Merge pull request` commits) — confirmed by their branch names existing as
`headRefName` on GitHub and by each `headRefOid` landing exactly where the corresponding commit
range in `git log` says it should.

---

## 2. Gate-by-gate table against spec §9

Quoted from `showdownbot_studio/docs/specs/2026-07-25-phase3-client-design.md` §9, which is a
**whole-phase** closure list (F0 through M3), not an M1-only list — several gates are necessarily
PARTIAL or PENDING because M2/M3 work they depend on has not started. That is expected at this
point in the phase, not a defect in M1.

| # | Gate (quoted) | Verdict | Evidence |
|---|---|---|---|
| 1 | "The architecture-foundation slice (§3.3) is merged... forbidden-dependency architecture tests are green in the `studio-security-invariants` CI lane." | **SATISFIED** | PR #88 merged; `docs/security/{THREAT_MODEL,DATA_CLASSIFICATION,CREDENTIAL_LIFECYCLE,LOGGING_AND_REDACTION,UNTRUSTED_SERVER_CONTENT,HUMAN_COMMAND_INVARIANTS}.md` and `docs/architecture/{LIVE_STATE_MACHINES,MODULE_CATALOG}.md` all present on disk (verified with `ls`); architecture lane green, 13 passed (§4 below) |
| 2 | "reviewed implementation plan for this design, split at minimum along F0 / M1a–M1e / M2a–M2f / M3a–M3c, each with its own PR and gate evidence" | **PARTIAL** | F0's plan approved in PR #88 (commit `4fe99c2`); M1's plan + binding watchlist approved in PR #90. `showdownbot_studio/docs/plans/` has no M2 or M3 plan document yet (verified with `ls`) — expected, since M2/M3 are not authorized to start |
| 3 | "isolated branch or worktree per the project's existing workflow" | **SATISFIED** (for F0/M1) | Each of PR #91–#96 has its own `headRefName` (`feat/studio-m1a-transport` … `feat/studio-m1-hardening`), verified via `gh pr view` |
| 4 | "protocol contract tests, battle-state tests, reconnect/resync tests (§6.2), and choice-lifecycle/`/choose`-family encoder tests (§7, §7.1) green in the `studio-protocol-contract` CI lane" | **PARTIAL** | Protocol/battle-state/reconnect tests green (§4 below; lane green at current `main` HEAD). §6.2's own required scenario list includes "reconnect during team preview" and "reconnect during a forced switch" — neither exists in `godot/tests/battle/` or `godot/tests/e2e/` (checked directory listing); only "reconnect after the battle has already ended" is covered (M1e + hardening's post-battle reconnect test). Choice-lifecycle/`/choose` encoder tests do not exist — `ProtocolCommandEncoder` only encodes room join/leave (M1b scope); `/choose` is M2d |
| 5 | "E2E tests green in the `studio-live-local-e2e` CI lane, covering the required reconnect scenarios (§6.2) and the required VGC/doubles fixture cases (§7.1)" | **PARTIAL** | Lane green (§4 below); same §6.2 gap as gate 4 (team-preview/forced-switch reconnect scenarios not covered); §7.1's VGC/doubles fixture cases are entirely M2/M2e scope — no choice UI exists in M1 to test against them |
| 6 | "one manual live gate battle against the official server, with filed evidence" | **PENDING — not performed** | Explicitly requires separate owner authorization per `MASTER_SPEC.md` and this project's own working agreement; not run in this session or any prior one (no evidence file exists for it) |
| 7 | "credential-handling review (§5.1)... confirming no credential path reaches disk, logs, crash reports, event payloads, or exports" | **PENDING (N/A yet)** | M1 introduces no credential code at all: no `session/` directory exists, no `CredentialProvider`/`LoginHttpTransport` (verified: `find . -iname "session*"` under `showdownbot_studio` returns nothing outside `.uid` noise). The review gate itself is M2a's to satisfy once that code exists — nothing to review yet, which is a different state from "reviewed and clean" |
| 8 | "chat-trust-boundary review (§5.2)" | **PENDING (N/A yet)** | Chat is M2f scope; no chat rendering path exists in M1 to review |
| 9 | "`TeamBundleV1` review (§3.4)" | **PENDING (N/A yet)** | Team bundle acquisition is M2b scope; not built |
| 10 | "`ReplayExportGateway` review (§4.5.1)" | **PENDING (N/A yet)** | Replay export is M3 scope; not built |
| 11 | "rate-limit behavior review... before the live gate is attempted" | **PENDING — not performed** | No rate-limit review document exists anywhere under `showdownbot_studio/docs/` (checked); required before gate 6, which also has not run |
| 12 | "licensing review: client code is self-written... no sprite or other official/community asset is introduced" | **PARTIAL** | Verified directly: every file M1 added under `godot/src/{net,protocol,battle,ui,workspace}/` is original `.gd` source (`git diff --dirstat` shows only `.gd`/`.gd.uid`/`README.md` churn, no binary/asset additions); no dedicated Phase-3 licensing-review artifact exists yet (the repo's `docs/research/2026-07-license-data-audit.md` predates Phase 3 and covers the exporter/bundle track, not this client code) |
| 13 | "human/bot separation review... `HumanBattleCommandGateway`... is the only path to an outbound battle command" | **PARTIAL** | `HumanBattleCommandGateway` itself does not exist until M2d — nothing to review yet at the level the gate names. What does exist and is green: the `studio-security-invariants` architecture tests (`test_f0_gateway_import_guard.py` et al., part of the 13 architecture passes) enforcing the forbidden-dependency rules those invariants require, and M1's own `SpectatorRoomGateway` sends only join/leave, never a battle choice (verified: `grep -rln "/choose" godot/src/` matches only two comments explicitly noting M1 sends none) |
| 14 | "accessibility and layout checks proportional to the new UI surface... per `MASTER_SPEC.md` §5" | **PARTIAL** | No formal manual checklist/capture packet exists for M1's UI (unlike Viewer v0's `viewer-v0-f-manual-checklist.md`). What does exist: real geometry-probe tests introduced during hardening caught and fixed two genuine layout defects — `RoomEntryPanel`'s controls all rendering at `(0,0)` (fixed in `32dde42`) and three of the live workspace's five panels rendering at `0x0` (fixed in `6e5edbc`) — see §5 below. Proportional but ad hoc, not a checklist audit |
| 15 | "maintainer acceptance-question gate... a maintainer can answer all five questions in `AGENTS.md`'s Acceptance questions section unambiguously" | **PENDING** | No artifact recording this Q&A exists for M1 specifically; not attempted in this session |
| 16 | "explicit owner review and approval before merge, and before any later phase... may be proposed" | **PARTIAL** | Per-PR owner review plainly happened and is the direct source of the 17 hardening findings (§5) — every hardening commit message is dated and attributed to a specific owner review pass. What has **not** happened is an owner sign-off on the **milestone** as a whole (the thing this document is evidence for); `docs/ROADMAP.md`'s own current text still describes the milestone gate as OPEN |

**Summary: 2 SATISFIED (gates 1, 3) / 7 PARTIAL (gates 2, 4, 5, 12, 13, 14, 16) / 7 PENDING (gates 6, 7, 8, 9, 10, 11, 15)**, of 16 gates. Read this as "on track for a phase still mid-flight," not as a completion score — several of the PENDING gates (7, 8, 9, 10) are N/A-until-built rather than attempted-and-failed: the code those reviews would examine (credentials, chat, team bundles, replay export) does not exist yet because it is M2/M3 scope.

---

## 3. Test evidence

All commands run fresh in this session from a clean `showdownbot_studio` tree (`git status --short`
showed no pending changes inside `showdownbot_studio/` before these runs). Exit codes are the only
trustworthy signal per this project's standing rule — `2>&1` is never applied to a native process,
and the `ERROR: Dictionary is in read-only state`-style lines that appear during the gdUnit run are
expected `push_error`/sealed-DTO assertions the tests themselves trigger on purpose, not failures.

**gdUnit4** (from `showdownbot_studio/godot/`):

```
.\tools\run_gdunit_headless.ps1 -a "res://tests/"
```

```
Overall Summary: 536 test cases | 0 errors | 0 failures | 0 flaky | 2 skipped | 0 orphans |
Executed test suites: (68/68)
Executed test cases : (534/536), 2 skipped
Exit code: 0
```
`EXITCODE=0` confirmed from `$LASTEXITCODE` after the call.

**Truncation guard:**

```
.\tools\check_gdunit_truncation.ps1
```

```
Truncation guard OK: 68 suites, executed+skipped test cases match gdUnit's own discovery count and the source's declared 'func test_' count.
```
Exit code 0.

**The 2 gdUnit skips, identified by name, not just by count:**

1. `tests/bundle/test_bundle_validator.gd::test_refuse_symlink_or_junction_payload` — self-skips at
   runtime with reason `"Plan F: mklink requires privilege — re-run elevated"` when the file-symlink
   `mklink` call fails (verified by reading the test source, `godot/tests/bundle/test_bundle_validator.gd`
   lines 223–244). This machine account lacks `SeCreateSymbolicLinkPrivilege`/Developer Mode. The
   companion junction test (`test_junction_named_battle_jsonl_is_reparse_not_subdir`, unprivileged)
   ran and passed, so the underlying guard is not unproven, only this one variant.
2. `tests/e2e/test_live_client_workspace_spectate_e2e.gd::test_spectating_a_real_local_battle_observes_real_content_not_just_room_state`
   — self-skips with reason `"no local pokemon-showdown server reachable on 127.0.0.1:8000 -- run
   showdownbot_studio/godot/tools/start_local_showdown_server.ps1 first (the studio-live-local-e2e CI
   lane always starts one before this runs)"`, confirmed from the run's own console output. This is
   the *default*, non-required lane behavior; the dedicated CI lane sets `STUDIO_E2E_REQUIRED=1` and
   fails instead of skipping (hardening commit `3afa69e`) — not exercised here since no local server
   was started for this evidence run.

**Studio pytest** (from `showdownbot_studio/python`, no path argument — `testpaths`/`pythonpath` are
set in `pyproject.toml`):

```
python -m pytest -q
```

```
........................................................................ [ 52%]
.......ss......................................................... [100%]
135 passed, 2 skipped in 1.74s
```
Exit code 0.

**The 2 pytest skips**, with `-rs`:

```
SKIPPED [1] ..\tests\python\test_a7_pathsafety.py:34: cannot create symlink: [WinError 1314]
Dem Client fehlt ein erforderliches Recht: ...
SKIPPED [1] ..\tests\python\test_a7_pathsafety.py:47: cannot create symlink: [WinError 1314] ...
```
Same root cause as the Godot symlink skip above — this account has no symlink-creation privilege on
Windows. Both are pre-existing Phase-0 tests, not something M1 introduced or is responsible for.

**Architecture lane** (from `showdownbot_studio/python`):

```
python -m pytest -q -m architecture
```

```
.............                                                            [100%]
13 passed, 124 deselected in 0.84s
```
Exit code 0.

**CI lanes, current `main` HEAD (`f5d88b0`), via `gh run list --branch main`:** all five lanes
report `conclusion: success` at this exact SHA:

| Lane (workflow file) | Covers |
|---|---|
| `studio-windows.yml` ("studio windows lane") | The full Studio pytest suite + full gdUnit suite in one job, Windows-only (per Plan F's closed K1 decision — this is the only lane that installs the pinned Godot engine and runs everything) |
| `studio-security-invariants.yml` | Only the `@pytest.mark.architecture` forbidden-dependency/typed-boundary tests (`test_f0_gateway_import_guard.py`, `test_f0_untyped_boundary_guard.py`, `test_f0_live_dto_bundle_guard.py`), kept fast and separate so it never downloads the Godot engine |
| `studio-protocol-contract.yml` | Introduced with M1b: the frozen-transcript golden-comparison decoder test plus the fixture-presence pytest guard |
| `studio-live-local-e2e.yml` | Introduced with M1d: provisions the pinned local `pokemon-showdown` server, runs the background gauntlet seeder, and drives the real spectate E2E test end-to-end in one step (the multi-step split was abandoned after PR #94 CI showed `windows-latest` kills a step's background processes at step end) |
| `pytest.yml` ("pytest slice smoke") | The bot's own unrelated lane (`working-directory: showdown_bot`); listed only because it also reports green at this SHA, confirming nothing in the hardening slice broke the bot's own suite |

---

## 4. Watchlist compliance

Against `showdownbot_studio/docs/plans/2026-07-25-phase3-m1-implementation-watchlist.md`, binding
for every M1 PR:

| Section | Satisfied? | Where the proof lives |
|---|---|---|
| M1a — transport | Yes, directly | `godot/tests/net/test_connection_state_machine.gd`, `test_web_socket_transport*.gd` cover single-peer-per-backoff, epoch discipline, the null-peer guard (hardening commit `0f043f2` added the missing reconnect-handshake timeout the watchlist's own "do not busy-loop"/state-and-epoch rules implied but the original M1a PR had not fully closed) |
| M1b — protocol | Yes, directly | `godot/tests/protocol/test_protocol_decoder_*.gd` — frame-boundary preservation, the three-way classification (decoded/known-ignored/unknown), the pinned `0 fnt` regression test, and (hardening) exact-not-prefix slot-identity matching (`91490c8`) all have named tests |
| Room lifecycle and commands | Yes, but the "gateway must inspect the send result" / failed-join/leave transitions were incomplete until hardening | `godot/tests/protocol/test_room_state_machine.gd` plus `28f456f` (RoomEntryPanel gained Leave/Dismiss — the watchlist's room-lifecycle rules were only reachable from real UI after this) and `298dfc5`/`f5d88b0` (view-reset-on-leave/dismiss, not on server-close) |
| M1c — derived state | Yes, directly | `godot/tests/battle/test_live_battle_reducer_*.gd`, `test_live_battle_snapshot.gd` (no public mutation path; new-value returns) — the fail-closed "unknown events remain diagnostically visible" bullet is `event_not_applied` signal coverage, extended in hardening (`649c951`, `7a49021`) |
| M1d — composition and UI | Partially indirect | `LiveClientWorkspace` tests cover `configure_transport_for_test()` wiring exactly once (`0a7c62c`) and single-render-path discipline, but the watchlist's "keep transport wiring separate from one-time domain/UI wiring" and "the live workspace must remain reachable through real navigation" bullets were only *behaviorally* proven, not geometrically — the two layout defects in §5 below (controls at `(0,0)`, three panels at `0x0`) show the pre-hardening tests exercised wiring and signals correctly while never once measuring real screen geometry |
| Local E2E | Yes, directly | `run_live_e2e_ci.ps1` (single-step provisioning, `npm ci`, readiness poll, `127.0.0.1` IPv6-first fix, marker-line parsing) and the required-vs-skip split (hardening `3afa69e`) |
| M1e — reconnect and rebuild | Yes, directly | `godot/tests/e2e/test_reconnect_full_rebuild_real_decode_path.gd` follows the exact ten-step sequence the watchlist specifies (poisoned-state test with `FakeMon`/turn 99/`OLD_ONLY_EVENT` before the second `init`); timeline-assertion (not snapshot-only) discipline is explicit in the test |
| Slice-boundary checks | Yes, per PR | Each PR's own description states file-list scope; `git diff --check` clean was part of hardening's own stated verification (PR #96 body) |

The honest gap in this table is M1d: the watchlist's UI-composition rules were tested at the
signal/wiring level from the start, but nothing tested real Control geometry until the owner's
manual review found it broken — covered further in §5.

---

## 5. Review history and what it says about test blindness

The owner ran (at minimum) five identifiable review passes against the merged M1 surface between
2026-07-26's early and late hours (each hardening commit message is dated and numbered against a
specific pass — "third pass", "fourth pass", "fifth pass" appear verbatim in commit bodies).
**17 distinct findings were closed across those passes**, not the 9 that PR #96's own top-level
description names — that description was written after the first pass and never updated as three
more passes landed further commits on the same branch before merge. This count was reconstructed
directly from `git log`, not asserted from the PR text:

- **9** from the pass PR #96 documents by name: retry-budget reset after `EXHAUSTED` (`7bdce31`),
  reconnect-handshake timeout (`0f043f2`), real `noinit` rejection decoding (`050feff`), fail-closed
  turn/slot parsing (`35b8a14`), terrain-field semantics (`e345cc4`), `battle_completed` transition
  timing (`0d59026`), reconnect-success poll completeness (`f7e0fa7`), the E2E lane's
  fail-instead-of-skip mode (`3afa69e`), and the stale-docs finding (`3f6056e`).
- **8** more from later passes, each commit's own message explicitly attributing it to a numbered
  review pass, not folded into the nine: `2ae8068` (minor, duplicated test-doc comment), `91490c8`
  (prefix-only identifier matching — a regression found *inside* finding 4's own fix), `28f456f`
  (`RoomEntryPanel` missing Leave/Dismiss — attributed to review of PR #94, not #96), `32dde42`
  ("P1 finding 1" of a first hardening-review pass), `298dfc5` ("second pass, P1 finding 2"),
  `6e5edbc` ("third pass, P1"), `7a49021` ("fourth pass, P1"), and `f5d88b0` ("fifth pass, P2").

**Three concrete examples, with what they say about the test suite's blind spots:**

1. **Prefix-only identifier validation (`91490c8`).** `_parse_pokemon_identifier()`'s guard was
   `colon_index < 3` — a minimum-length check, not an exact-match check. `"p1abc: Whoever"` (a
   longer string with a valid two-char-side + one-char-slot *prefix* followed by garbage before the
   colon) still passed, silently truncating to `side="p1"`/`slot="a"`. Every committed fixture only
   ever contains exact `p1a`/`p1b`/`p2a`/`p2b` identifiers, so no existing test — including the ones
   written specifically to close the *previous* finding about exact-match slot identities — could
   have caught it. **Lesson:** a fixture corpus that never contains an adversarial-length variant of
   a string it validates cannot discover a boundary-condition bug in that validator, no matter how
   many well-formed cases it covers.
2. **The `0x0` workspace layout (`6e5edbc`, plus the related `32dde42`).** `live_client_workspace.tscn`'s
   root was a bare `Control` with five children at `layout_mode = 1` and no anchors — a plain
   `Control` never aggregates a child's minimum size the way a `Container` does, so three of five
   panels measured `0x0` in the real instantiated scene. Every prior M1d test drove
   `LiveClientWorkspace` through direct method calls and signal assertions, never through
   `get_global_rect()` on the actual scene tree. **Lesson:** behavior-only tests (call the handler,
   assert the resulting state) can be 100% green while the UI they claim to cover is geometrically
   invisible — signal wiring and screen layout are different claims, and only one of them was tested.
3. **Pre-init poisoning (`7a49021`).** After leaving battle-1 and joining battle-2, an event for
   battle-2 arriving *before* battle-2's own `|init|battle` (e.g. a premature `|win|`) was forwarded
   straight to `LiveBattleProjection` regardless of `RoomState`, so `battle_completed` could go true
   and gain a timeline entry attributed to the wrong room, and — critically — that poisoned state
   **survived** the real `init` that followed, because `apply_event()`'s own repeat-init reset only
   fires once `_has_seen_init` is false, and the premature event had already flipped it true. The
   existing reconnect/rebuild tests (M1e) never tested a *room switch*, only reconnect-to-the-same-room;
   the existing room-lifecycle tests never fed an out-of-order event before `init`. **Lesson:** a
   test suite built around "reconnect resets and rebuilds" and a separate suite built around "leaving
   a room resets the view" can each pass in isolation while the *composition* of the two — leave, join
   a new room, race an event against that new room's init — was never a scenario either suite modeled.

**What this says about where the suite was blind, stated plainly:** every one of these three classes
is a fixture/scenario gap, not a broken assertion — the tests that existed asserted correctly on the
inputs they were given. The corpus never contained an adversarial-length identifier, no test ever
measured real Control geometry, and no test modeled the specific interleaving of room-switch and
late event delivery. This is the same failure mode `viewer-v0-gate-coverage-recheck.md` documented
for the Phase-0 track (a docstring naming a gate is not evidence of coverage; only a fail-check
proves it) — M1's hardening slice is further, independent evidence for that same standing lesson,
found by human review rather than a deliberate fail-check pass this time.

---

## 6. What is explicitly NOT claimed

- **No strength, safety, or quality claim about the bot.** There is no bot in this client at all —
  M1 is a spectator that renders another party's battle. Nothing here should be read as commentary
  on `showdown_bot`'s play quality.
- **The client is spectator-only.** No login exists (`session/` does not exist as a directory), no
  `/choose` or any other battle-command path exists (`ProtocolCommandEncoder` encodes only room
  join/leave), no `session/` state, and no credential handling of any kind — verified directly in
  §2 gates 7 and 13 above.
- **Phase 2, 4, and 5 are unauthorized.** This document says nothing about them and does not imply
  readiness for any of them.
- **M2 has not started.** No `session/`, no `HumanBattleCommandGateway`, no team-bundle acquisition,
  no challenge/ladder, no move selection exist anywhere in this tree (verified by directory listing
  and by the credential/gateway greps in §2). The three UX decisions pinned in
  `docs/research/2026-07-showdown-client-user-research.md` §8.3.1 (two-step choice review, input
  routing/shortcut layer, panel/layout model) are recorded as **required before the M2 plan is
  written**, not as work already done.
- **The M1 milestone gate is OPEN.** Per gates 6, 11, 15, and 16 above (manual live gate, rate-limit
  review, maintainer acceptance-question gate, and milestone-level owner sign-off), M1 is not
  closed. `docs/ROADMAP.md`'s own current text agrees, though see the stale-docs item in §7 below.

---

## 7. Open follow-ups

Each item below was checked against the current tree; none is invented.

1. **`docs/ROADMAP.md` and `docs/PROJECT_INDEX.md` are already stale relative to `main`'s own tip.**
   Both were updated by hardening commit `3f6056e`, which was itself written mid-pass — they
   currently read "M1 hardening slice **in progress**... owner findings **1–9**... **not yet
   merged**" (verified by reading both files at their current committed text). In fact PR #96 is
   merged (its `headRefOid` **is** `main`'s current HEAD) and 17 findings were closed, not 9 (§5).
   This is a real, small, easily-fixed documentation gap, distinct from the milestone-evidence gap
   this document exists to fill.
2. **The three UX decisions pinned in `docs/research/2026-07-showdown-client-user-research.md`
   §8.3.1** (two-step choice review; input routing/shortcut layer; panel/layout model) are flagged
   there as binding owner sign-off items for the M2 plan round — not yet decided, per that section's
   own text.
3. **Gates 6, 7 (deferred, not a gap), 8 (deferred), 9 (deferred), 10 (deferred), 11, 15, and 16**
   from §2 remain open, as detailed there. Gates 6 and 11 in particular are the ones that block
   further M2 work from being treated as complete against a "live-verified" bar, though they do not
   block M2 development from starting once authorized.
4. **§6.2's required reconnect scenarios are only one-third covered.** "Reconnect during team
   preview" and "reconnect during a forced switch" have no corresponding test anywhere in
   `godot/tests/battle/` or `godot/tests/e2e/` (checked directly) — both require choice-state
   concepts that are M2 scope, so this is expected, not a defect, but it is a concrete item the M2
   plan (or a follow-up M1 test) needs to pick up.
5. **A one-time CI flake in `test_bundle_switch_resets_cursor` — confirmed directly against the
   GitHub Actions job, correcting this document's own earlier "could not verify" note.** An initial
   pass over this document found no in-repo reference to this specific test as flaky and left it
   unverified. On a further check pointed at a specific job, `gh api
   repos/chrismaghuhn/ShowdownBot/actions/jobs/89694389159/logs` (PR #92, `studio-windows` lane, run
   `30164221116`, **attempt 1**, `conclusion: failure`) shows, verbatim:
   `res://tests/workspace/test_app_shell_replay.gd > test_bundle_switch_resets_cursor FAILED 57ms` /
   `line 180: Expecting: '0' but was '-1'`, with the suite-level `Overall Summary: 410 test cases |
   0 errors | 1 failures`, gdUnit `Exit code: 100`. **Caution on the lookup mechanics:** `gh run view
   --job 89694389159 --log-failed` (no `--attempt`) silently returned **attempt 2**'s log instead (the
   same job ID is reused across reruns; attempt 2, `conclusion: success`, completed 15:49:15Z, shows
   this same test PASSED and the suite green at 410/410) — the job-ID-scoped `gh api .../jobs/<id>/logs`
   endpoint was what actually pinned attempt 1. **Confirmed:** a rerun of the same commit (attempt 2)
   went green with no code change between attempts. Not documented in-repo anywhere, and cause not
   diagnosed here — plausibly the same class of async bundle-switch/loader timing race as the
   historical `test_fixture06_refuse_clears_replay` flake below, but that is a hypothesis, not a
   verified shared root cause. **Keep both entries** — this one (observed once in CI, PR #92, not
   locally reproduced in this session's own clean 536/536 run) and the next (a different,
   previously-diagnosed Phase-0 flake) are distinct, both genuinely open:
   `test_fixture06_refuse_clears_replay`, root-caused and partially fixed via `AppShell.is_settled()`
   per `viewer-v0-gate-coverage-recheck.md` ("The flake") — which that document itself says has **no
   test covering the fix** ("removed rather than committed"). That one is on the Phase-0 side,
   unrelated to M1's own scope, but still open.
6. **No formal manual accessibility/layout checklist packet exists for M1's UI** (gate 14, §2) —
   unlike Viewer v0's `viewer-v0-f-manual-checklist.md`. The geometry-probe tests added during
   hardening are real and did catch real defects (§5), but they are targeted regression tests for
   specific found bugs, not a systematic capture-and-review pass across the new UI surface at
   multiple resolutions/scales the way Plan E/F's packet was for Viewer v0.
7. **A third layout defect of the same class, found by the owner running the real app, not yet
   committed.** `godot/src/workspace/studio_root.tscn` at the current `main` HEAD (`f5d88b0`,
   verified via `git diff` against the working tree) has `StudioRoot` as a bare `Control` (not a
   `Container`) with `NavBar` at `layout_mode = 1` and no anchors, sitting beside `WorkspaceRouter`
   at `anchors_preset = 15` (full rect) — the router visually covers the whole window including the
   nav bar. Worse, the committed `LiveClientWorkspace` instance node inside the router carries only
   `layout_mode = 1` and **no anchor properties at all** (confirmed by reading the committed file:
   its node block ends after `layout_mode = 1` with nothing following, unlike
   `OfflineViewerWorkspace`'s sibling node, which has the full `anchors_preset = 15` block) — so it
   would render collapsed. A fix already exists as **uncommitted local changes** in this checkout
   (not yet on `main`): `StudioRoot` becomes a `VBoxContainer` (`NavBar` and `WorkspaceRouter` as
   `layout_mode = 2` children, `WorkspaceRouter` at `size_flags_vertical = 3`), and both workspace
   instances inside the router get explicit `anchors_preset = 15`. This is not this document's fix
   to make or claim — recorded here as an open, owner-found defect against the already-merged M1
   surface, still pending commit and its own PR/review.
   **The pattern across all three layout defects (§5's `0x0` workspace and `(0,0)` room-entry-panel
   controls, plus this one) is the same and worth stating plainly:** the geometry-probe test for
   `LiveClientWorkspace` instantiates it **standalone** as the scene root and measures its own
   internal children's rects — and passes. Nothing in the suite ever instantiated the **composed**
   scene (`StudioRoot`, with `LiveClientWorkspace` as a grandchild reached through
   `WorkspaceRouter`) and measured real geometry there. Three separate layout defects, at three
   different levels of composition, were each found only by a human running the app or reading the
   scene file — never once by the automated suite, which was geometry-blind at every composition
   boundary it didn't happen to probe directly.
