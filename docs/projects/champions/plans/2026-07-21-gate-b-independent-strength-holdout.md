# Champions Gate B — Independent Strength Holdout — Implementation Plan (Rev. 25)

> **Status: Rev. 25 — Tasks 1–12 AND all of Task 13 (steps 1–3) are IMPLEMENTED, tested, and
> COMMITTED on branch `feat/champions-gate-b-task-1-schedule`; Tasks 1–12 and Task 13 steps 1–2 are
> Codex-PASS, and step 3 is UNDER REVIEW. Nothing is merged to `main`.** Step 3 is code-complete:
> the source condition is SATISFIED (§2a); the six `.txt`/`.packed` team artifacts exist, are
> sealed, are `validate-team`-legal, and pass the real leakage and coverage-disjointness scans; the
> holdout manifest is the single home of the public-to-internal ID mapping; the Gate B static
> baseline CONTRACT and its real frozen VALUES are committed (`load_strength_holdout_baseline` /
> `verify_strength_holdout_baseline`, the additive closed-schema A1.3 loader/verifier, verifying
> clean against the real tree); the **panel YAML** carries real content; the **hash freeze** is done
> (`STRENGTH_HOLDOUT_EXPECTED_PANEL_HASH` / `STRENGTH_HOLDOUT_EXPECTED_MANIFEST_HASH`, derived via the
> production functions, and the manifest hash binds the frozen selection order + public→internal
> mapping); both **CLI subcommands are wired** to real manifest/panel data and enforce the frozen
> identity before battle 1 / before any verdict (no Task-13 blocker remains); and the **reference
> near-duplicate audit** against the nine reference teams is recorded (selection audit §5a). **Still
> outstanding:** the whole-suite verification and Codex review of this branch. No Gate-B server has
> been started and no Gate-B battle has been played, and the live Gate B run remains BLOCKED under a
> separate authorization (§17).**
>
> This header, the implementation-status block further down, §16 and §19 are kept in agreement;
> if they ever disagree, the deepest one (§19) is the one to fix first.
>
> - **Rev. 24 → Rev. 25** (baseline-immutability fix + authorized history rewrite, no new design
>   round): the full offline suite surfaced one failure —
>   `test_baseline_manifest_git_immutability` — because the baseline manifest
>   `config/eval/baselines/champions-strength-holdout-v0.json` was committed twice (a Task-6
>   schema-loadable placeholder, then a step-3 back-fill with real values), and a baseline manifest
>   is immutable after its first commit. Under explicit owner authorization, the feature branch was
>   rewritten (`git filter-branch`, backup branch kept) so the file is **created exactly once**, with
>   its final real values, in the step-3 commit; the final tree is byte-identical to the pre-rewrite
>   HEAD. This revision aligns the plan with that reality: **Task 6 owns only the schema, loader,
>   verifier and their tests**; the baseline manifest is committed once in **Task 13 step 3** with
>   final values (§9 box, §16 item 7, the file-map). The generic T6 immutability test is unchanged.
> - **Rev. 23 → Rev. 24** (execution-status sync + one review-fix round on step-3 code, no new
>   design round): step 3's artifacts (panel real content, baseline real values, the two hash-freeze
>   constants, the CLI data wiring, the near-duplicate audit) are committed, so the status no longer
>   lists them as outstanding. Two review findings on the step-3 code were closed: **(P1)** both CLI
>   subcommands now bind the on-disk panel and holdout-manifest hashes to their FROZEN constants
>   before battle 1 / before any verdict (`_load_and_verify_frozen_gate_b_identity`) — a *consistent*
>   drift of panel + manifest + baseline together would pass `verify_strength_holdout_baseline`
>   (which only checks those three agree with each other and disk), so the frozen constants are the
>   external anchor a swapped/re-sealed holdout can never satisfy; **(P2)** `strength_holdout_manifest_hash`
>   now binds the frozen selection ORDER (`selection_index`) and the public→internal MAPPING
>   (`source_team_id`), not merely the `(team_id, team_path, team_content_hash)` triple.
> - **Rev. 22 → Rev. 23** (mechanical execution-status sync, no new design round, no findings):
>   Task 13 steps 1–2 (the six sealed teams + the holdout manifest) and their two focused
>   review-fix rounds are committed through `b0cb3bf`, so the status surfaces move to Rev. 23 and
>   record step 3 as active. Two review-fix findings from those rounds are now reflected in the
>   contract prose (they were hardened in code, not merely asserted): **(P1)** the Gate B arm's
>   pre-battle reproducibility guard checks the interpreter's REAL hash-randomization state
>   (`sys.flags.hash_randomization`, via the `_hash_randomization_enabled()` seam), not merely
>   `os.environ["PYTHONHASHSEED"]` — setting that env var mid-process does not disable hash
>   randomization, so the env string alone proves nothing; both the live flag (load-bearing) and
>   the recorded env value (pinned to `"0"`) must agree before battle 1. **(P2)** the holdout-
>   manifest verifier requires `selection_index` to be the CLOSED set `{1..6}` (integers only, no
>   `bool`), not merely six distinct values — uniqueness alone would accept `{1,2,3,4,5,99}`. The
>   stale claim that "the Gate B baseline contract does not exist yet" is removed: the contract
>   (loader/verifier + closed schema) is committed; only the manifest's real VALUES remain for step
>   3. The historical §2 blockers stay exactly as written — superseded by §2a, not rewritten.
> - **Rev. 21 → Rev. 22** (mechanical execution-status sync, no new design round, no findings):
>   the source condition for Task 13 is satisfied (§2a), so the Goal sentence no longer says
>   "pending source-proof"; the two remaining "merged source" phrasings are corrected to
>   "committed source" (nothing is merged to `main`); revision surfaces move to Rev. 22. The
>   historical §2 blockers stay exactly as written — they are marked superseded by §2a, not
>   rewritten.
> - **Rev. 20 → Rev. 21** (§1t, mechanical sync, no new design round): Task 11's embedded code and
>   its argparse instructions are replaced with the flat-CLI implementation actually committed as
>   `b71923f`. The removed claim — "register both subparsers … all five `required=True`" — was
>   false in two ways at once: `cli.py` has no argparse subparsers, and `required=True` on a shared
>   global flag would break every other command.
>
> Rev. 9 was the first round with zero findings against it. Eight prior review rounds
> received CHANGES REQUESTED; full per-round findings tables are in §1a–§1i, summarized briefly
> here so this header stays readable:
> - **Rev. 19 → Rev. 20** (§1s, mechanical sync, no new design round): Task 10's embedded code was
>   stale relative to the two review-fix commits that landed after it. This revision replaces the
>   Task 10 test and implementation blocks with the FINAL committed source as of `53e6c9c`, and
>   updates that task's RED/GREEN/commit records to what was actually executed. The substantive
>   deltas the sync carries in: (1) `_assert_rows_cover_canonical_schedule` rebuilds the canonical
>   180-battle-key schedule from each arm's own team_ids/panel_hash/seed_base, checks `seed_base`
>   separately against the pinned namespace, and requires the rows to cover the canonical grid
>   exactly once — two agreeing 12-row arms previously combined to a published verdict; (2) combine
>   refuses a dirty tree and requires `HEAD == manifest git_sha` before any repo-dependent guard,
>   with `_git_is_dirty`/`_git_sha` gaining a `cwd` parameter so they interrogate the same checkout
>   those guards read; (3) both sides of the near-duplicate comparison are DERIVED via
>   `near_duplicate.load_team_species` from real sealed `.packed` files — the
>   `holdout_candidate_species`/`reference_species` parameters are removed entirely and the nine
>   canonical reference teams are pinned in `CANONICAL_REFERENCE_TEAM_PATHS`; (4) a non-object
>   (`null`, list, scalar) row or manifest aborts as `GateBAbort` instead of raising a raw
>   `TypeError`; (5) the held-out access-budget check and its reservation now run inside one
>   exclusive `_ledger_lock` (`O_CREAT|O_EXCL`), the early `check_access` being an explicitly
>   non-authoritative fail-fast; (6) every row is bound to its canonical battle identity —
>   `seed` and `battle_id` re-derived per battle key, plus `format_id`, `config_id`, `run_id`,
>   `hero_team_path`, and `dirty` required to be exactly `False`. Task 10's test count is 108
>   (Tasks 9 + 10 together in `test_strength_holdout_runner.py`). No Task 11/12/13 contract point
>   changes as a result of this sync — Task 11's CLI wiring is checked against the final combine
>   signature below and needs no text change beyond what §14 already specifies.
> - **Rev. 18 → Rev. 19** (§1r, mechanical contract sync, no new design round): Task 9's own
>   review-fix (implemented and merged as commit `6658625`, five P1s) shipped after this plan's
>   Task 10 text was written, and changed the arm manifest shape Task 10 reads: `calc_backend` is
>   now derived internally and carried in the manifest (previously discarded); the caller-local
>   `seed_log_path` field is replaced by a four-field seed PROOF the arm itself carries
>   (`seed_log_relpath`/`seed_log_sha256`/`seed_log_n_lines`/`seed_log_verified`), with the
>   verified seed log published as `seeds.jsonl` inside the arm directory. Task 10 is corrected to
>   match: `_MANIFEST_REQUIRED_KEYS` gains all five fields; `_validate_seed_proof_fields` closed-
>   form validates them; `_assert_seed_artifact_verified` independently re-verifies BOTH arms'
>   real seed-log bytes (canonical containment, fresh sha256, `verify_seed_log`, count bound to
>   both `seed_log_n_lines` and `n_rows`) before any pairing or verdict; the arm-vs-arm field loop
>   gains `calc_backend`; both upstream-verifier calls pass `calc_backend=manifest_a["calc_backend"]`
>   instead of a hardcoded `"oneshot"` literal, which would have silently mis-verified any run
>   that actually used `persistent`. `_write_arm`'s test fixture now writes a real `seeds.jsonl`
>   and the corrected manifest shape; thirteen new tests cover the sync directly. No other Task 10
>   contract point changes; Task 11/Definition-of-Done were checked and have no stale references
>   to sync (Task 11's CLI wiring for Task 10 is not yet implemented, and neither section mentions
>   `calc_backend`/`seed_log_path` at all).
> - **Rev. 1 → Rev. 2** (§1a, 9 P1 + 3 P2): the original single-server, single-generic-check
>   design — cell-flip/weak-policy McNemar bypass, no real upstream-verdict schema validation,
>   caller-controlled provenance, unbound paired seeds, unwired guards, incomplete evidence,
>   `.txt`-only team hashing, fabricated `baseline`/`ledger` APIs, `NotImplementedError` stubs.
> - **Rev. 2 → Rev. 3** (§1b, 2 P1 + 2 P2): a `candidate_identity` equality check between arms
>   that the real hash formula makes structurally impossible to pass on any genuine run; silently
>   optional upstream-verdict paths; a dead test-isolation seam; an unbound placeholder `opp_team_hash`.
> - **Rev. 3 → Rev. 4** (§1c, 4 P1 + 2 P2): the most serious of the whole series — `stats.winner`/
>   `stats.end_reason` read from a `GauntletStats` object that, per its real class body, has no
>   such fields under any name; the real per-battle result only arrives via a separate
>   `on_battle_result` callback. Also: unverified seed logs, an unwired baseline-drift guard,
>   `schedule_hash`-only (not `hero_team_hash`/`opp_team_hashes`-bound) upstream checks, a too-narrow
>   `except MissingPairError`, and production-reachable empty guard-input dicts.
> - **Rev. 4 → Rev. 5** (§1d, 1 blocker P1 + 1 P1 + 1 P2 + 1 P3): rows never carried `panel_hash`,
>   which `pairing.py` indexes directly with no `.get` — every `combine` call reaching `pair_runs`
>   crashed with a raw, uncaught `KeyError`; `result_sha256` hashed a differently-formatted
>   re-serialization of the verdict than what was actually published; `teams_root` never reached
>   the leakage content-scan (silently fell back to ambient process CWD); a test fixture's row
>   serialization diverged from the canonical writer format.
> - **Rev. 5 → Rev. 6** (§1e, 2 P1/P2 findings absent from every prior findings table despite
>   surviving three review rounds unmentioned): an arm's `rows.jsonl` was never validated or
>   cross-checked against its own `arm_manifest.json` — a manifest from a different run sitting
>   next to someone else's rows would pass every check silently, since every downstream use
>   (upstream-verdict checks, ledger entry, published verdict) trusted the manifest's claims
>   without ever proving they described the rows actually being analyzed; and the ledger entry
>   was written *after* publish, so a failed `append_entry` could leave a published bundle with
>   no budget spent against it — the exact held-out-data-reuse gap the ledger exists to close.
> - **Rev. 6 → Rev. 7** (§1f, 2 P2 + 1 self-found P3): the F3/F6 fix functions themselves raised
>   new raw, uncaught exceptions instead of `GateBAbort` — `ResultRowError` from `_read_arm`'s own
>   new `validate_battle_row` call, and `KeyError` from `_assert_rows_match_manifest`'s unchecked
>   indexing. Separately, this document's own text had falsely claimed for three revisions that
>   the CLI catches `` except (GateBAbort, StrengthHoldoutRunError) ``, when the real CLI (Task 11)
>   only ever catches `GateBAbort` — meaning `StrengthHoldoutRunError`, arguably the single most
>   likely real abort path in the whole plan, was left escaping uncaught the entire time, and the
>   false claim was cited to justify an earlier fix without ever being checked. A third, self-found
>   gap in the same function (`OSError`/`UnicodeDecodeError`/`json.JSONDecodeError` from
>   `_read_arm`'s own file reads) was fixed in the same pass. §1f added an exception-audit table —
>   but scoped to "every function touched in Rev. 7," a diff, not a boundary, which is exactly why
>   it missed Rev. 8's findings below.
> - **Rev. 7 → Rev. 8** (§1g, 2 P2 + 1 self-found P3): the audit table's own scope was the bug —
>   diff-scoped, so it structurally could not see gaps in code from earlier rounds. Widening it to
>   "every exception reachable from either public entry point toward the CLI" found NF3 (the
>   write-side twin of NF1: `run_strength_holdout_arm`'s `BattleResultWriter.write()` call can
>   raise the same `ResultRowError`, unwrapped, in a Task 9 function Rev. 7 never touched), NF4
>   (four raw git-subprocess exception paths — `_git_is_dirty`/`_git_sha`, reachable before a
>   single battle plays, and `_git_tracked_files`/`_grep_identifier`, reachable via the leakage
>   scan, exposed by the Rev. 5 N3 fix that made `teams_root` caller-controllable), and SF2 (a
>   self-found third: the upstream-verdict file reader, `_load_verdict_dict`, had the identical
>   unguarded-JSON-read gap SF1 fixed one module over — would have escaped even NF2's own fix).
>   §1g also resolves, rather than merely flags, the four-guards question Rev. 7 left open: their
>   exception types stay distinct by design (the user's call — `AccessBudgetError` is a policy
>   refusal with a defined override, not a technical failure), and the CLI boundary is widened
>   honestly instead, with a documented, unit-tested exception→message/exit-code mapping (Task 11).
> - **Rev. 8 → Rev. 9** (§1h, 1 P2): NF2's shape recurring one level up — §1g's own audit table
>   correctly disclosed `gauntlet_runner` as an untraced trust boundary, but the code comment on
>   the arm CLI's `except GateBAbort` branch, justifying why that handler stayed narrow, dropped
>   the qualifier and claimed the underlying property unconditionally. A disclosure in a table
>   does not by itself stop a false claim from shipping in the code three lines away. Fixed at the
>   root rather than just in the comment: `asyncio.run(gauntlet_runner(...))` (Task 9) is now
>   wrapped in a deliberately broad `except Exception` — a boundary conversion to `GateBAbort`
>   that needs no audit of what the unaudited callee can raise, `from exc` preserved,
>   `key.seed_index` in the message. One trust-boundary row remains (`resolve_coverage_provenance`,
>   pre-existing, unrelated to this finding) — named accurately now, not silently zeroed out.
> - **Rev. 9 → Rev. 10** (§1i, not a finding — the user's answer to Rev. 9's own open question):
>   rejected both options Rev. 9 offered for the one remaining trust-boundary row
>   (`resolve_coverage_provenance`) — "boundary-wrap it like `gauntlet_runner`" and "leave it
>   deferred" — for a third: read it. Unlike `gauntlet_runner` (an external websocket client),
>   `resolve_coverage_provenance` is same-repo, same-package code, auditable at reasonable cost,
>   and auditing it is stronger evidence than converting it. Reading it in full (alongside
>   `resolve_i8d_provenance` and `config_env.py`) PROVED — not assumed — that Gate B's
>   `_derive_config_hash` produces the identical `config_hash` I8-D's own provenance function
>   would for the same candidate, closing a debt Task 9's own docstring had carried since Rev.
>   1/2. It also surfaced a deliberate, documented fail-closed design from an unrelated,
>   already-reviewed slice (`ItemdataStaleError`/`SpeciesMetaStaleError`/`PinnedCalcError`,
>   I7a §14/§5.4) that a blanket `except Exception` would have silently flattened into an
>   indistinguishable `GateBAbort` — caught by name instead, preserving the signal. P3 addendum,
>   same round, caught on the user's own independent re-read: the proof only pinned
>   `COVERAGE_FORMAT == I8D_FORMAT`, not `== STRENGTH_HOLDOUT_FORMAT_ID` — the actual call never
>   passed `format_id`, silently inheriting Coverage's default rather than the format Gate B
>   itself plays under. Inert today (all three constants match), but the failure direction would
>   have been a SILENT false provenance certification, not a loud abort. `format_id` is now
>   passed explicitly; the test gained the third comparison that closes the triangle.
> - **Rev. 10 → Rev. 11** (§1j, 1 user-found): not a new Codex review round -- the user's own
>   direct comparison of Task 1's shipped `schedule_hash` against `compute_schedule_hash(version,
>   rows)`'s calls in the other five modules, after Task 1 itself had already been implemented
>   and committed on its own branch. `build_strength_holdout_schedule` hashed `keys`,
>   `seed_base`, and `format_id` -- never `panel_hash`, despite receiving it as a required
>   parameter and storing it on the returned dataclass. Two schedules built from the same six
>   team IDs but different panel content collided on `schedule_hash`. The bug was in this
>   document's own §4 code block, present since Rev. 1 and carried forward unchanged through
>   ten revisions and the Task 1 implementation itself, which correctly implemented what §4
>   specified. Fixed by hashing `panel_hash` directly, not by adopting `compute_schedule_hash` --
>   `BattleKey` has no `hero_team_path`/`opp_team_path` fields to give that function, since team
>   files do not exist before Task 13.
> - **Rev. 11 → Rev. 12** (§1k, 2 user-found): not a new Codex review round -- two findings
>   delivered directly by the user, verified against this document's own Task 2 code block before
>   any fix. **P1 #1:** `_is_allowed`'s `path == prefix or path.startswith(prefix)` applied
>   `.startswith` to single FILE entries in `ALLOWED_PATH_PREFIXES`, not just directories --
>   `"config/eval/heldout_ledger.jsonl.evil"` (and two similarly-shaped paths) wrongly passed the
>   allowlist. Fixed by splitting `ALLOWED_EXACT_PATHS` (exact match only) from
>   `ALLOWED_DIRECTORY_PREFIXES` (prefix match, safe because every entry already ends in `/`).
>   **P1 #2:** the content-leakage scan (`scan_for_content_leakage`) only ever looked at `.txt`
>   files under `showdown_bot/teams/` with a co-located `.packed` partner, hashed the combined
>   pair as one whole-file digest, and compared only against other similarly-shaped team files --
>   invisible to a payload copied into a report, a test, a `.txt`-only copy with no `.packed`
>   sibling, or embedded inside a larger tracked file, none of which DESIGN sec 3.3's repo-wide
>   contract exempts. Fixed by replacing it with `scan_for_raw_payload_leakage`: a byte-exact
>   substring scan of every git-tracked file's COMMITTED blob content (immune to Windows
>   `core.autocrlf` working-copy drift) against the sealed teams' own committed `.txt`/`.packed`
>   payloads, fail-closed on an empty payload or an unreadable blob. `Task 10`'s call site and
>   `Task 13`'s definition-of-done wording are updated to match; `Task 12` was checked and needs
>   no change (§1k).
> - **Rev. 12 → Rev. 13** (§1l, 2 more findings, second review round on the Rev. 12 fix itself):
>   the original two P1s were confirmed closed, but Rev. 12's own fix left two further
>   execution-blocking gaps. **P1:** `assert_no_holdout_leakage`/`scan_for_raw_payload_leakage`
>   accepted an empty or incomplete `team_ids` -- a `holdout_content_hashes` covering only some of
>   the six scheduled teams would silently leakage-scan only that subset, and nothing anywhere
>   checked the map against the schedule's real team set. Fixed with two layers: Task 9's arm
>   manifest now records the sorted six `holdout_team_ids` it actually scheduled; Task 10 requires
>   both arms to agree on that list (folded into the existing `schedule_hash`/`panel_hash`/
>   `seed_base` agreement check) AND requires it to exactly equal `holdout_content_hashes.keys()`,
>   aborting before any guard runs otherwise; `scan_for_raw_payload_leakage` itself also now
>   rejects an empty `team_ids` list directly, fail-closed, independent of the caller-side check.
>   **P1:** Task 10's own GREEN tests could not have passed against the real scanner --
>   `_fake_holdout_hashes()` named team IDs with no committed `.txt`/`.packed` blobs anywhere, and
>   every test that reaches `assert_no_holdout_leakage` used `teams_root="."` (the real ambient
>   worktree, which has no sealed teams -- Task 13 is still blocked), so the real
>   `scan_for_raw_payload_leakage` would raise `LeakageScanError` before any test's actual
>   assertion. Fixed by adding `_write_holdout_teams_repo`, a real, isolated, per-test git repo
>   seeded with six committed, allowlist-conformant sealed teams, and pointing every test that
>   genuinely reaches the leakage scan at it (`teams_root=`, real `holdout_content_hashes=`) --
>   the guard is not mocked away anywhere; it runs for real, against real committed content.
> - **Rev. 13 → Rev. 14** (§1m, 1 P1 + 1 P2, third review round): Codex, not the user directly
>   this time. **P1:** Rev. 13's `holdout_team_ids` was itself only ever an ASSERTION -- a bare
>   list of six team IDs the manifest claimed, never bound to what `rows.jsonl` actually contains.
>   `_assert_rows_match_manifest` checked the field for PRESENCE only; nothing verified a row's own
>   `opp_team_path`/`opp_team_hash` against it. Both arms' manifests, and the caller-supplied
>   `holdout_content_hashes`, could therefore all agree on the same six WRONG team identities while
>   the real rows referenced entirely different opponents, and the leakage/disjointness guards
>   would scan for the asserted teams, never the real ones. Fixed by replacing the bare list with a
>   canonical mapping, `holdout_teams: {team_id: {"team_path", "content_hash"}}`, that Task 9
>   derives only from the real scheduled battle-keys, the canonical `HOLDOUT_TEAMS_DIR` path
>   convention, and the real sealed content hashes -- and that Task 10 now validates structurally
>   (closed shape, exactly six entries, canonical paths, non-empty strings, no unknown fields) AND
>   binds to every row (`opp_team_path` must be one of the six, `opp_team_hash` must match its
>   team's declared hash, all six teams must actually appear) before trusting it for anything.
>   `holdout_content_hashes` is now checked for full dict equality against the bound mapping, not
>   just key-set equality. **P2:** the paragraph after Task 10's tests claimed empty guard inputs
>   were a legitimate test choice and that every guard ran "for real" in every test -- stale
>   relative to Rev. 13/14's actual design (empty inputs are rejected everywhere; only the
>   early-abort tests use cheap fake data, and only because they never reach the guard). Corrected
>   to describe the real Rev. 14 split.
> - **Rev. 14 → Rev. 15** (§1n, 2 P1, "Task-3-review"): Task 2 was implemented for real between
>   Rev. 14 and this round (`c4aa94b`/`7cdc661`); this round is plan-text-only again, scoped to
>   Task 3. Task 3's own `strata_guard.py` primitives (`detect_stratum`/
>   `assert_no_cross_stratum_pooling`/`stratum_output_root`) were correct and complete, but never
>   correctly wired into Tasks 9/10 -- the same "lower-level module right, higher-level integration
>   wrong" shape as Rev. 14's `holdout_teams` gap, recurring one guard over. **P1:** Task 9 never
>   wrote a stratum, platform attestation, or pre-registered date/stratum identifier into the arm
>   manifest at all; Task 10's `combine_strength_holdout_arms` called `detect_stratum()` ITSELF
>   (re-determining stratum from whatever machine happens to run the combine step, not either arm's
>   actual play machine) and built both `StratumRecord`s from that SAME single self-detected value
>   with `platform_string=""` hardcoded -- so two arms genuinely played on different strata could
>   never be told apart; `assert_no_cross_stratum_pooling` always saw one identical value twice.
>   **P1:** `stratum_output_root()` (Task 3) was called nowhere in the plan outside its own tests --
>   dead code; nothing bound an arm's `out_dir` to its stratum. Fixed: Task 9 now establishes
>   stratum (`detect_stratum`, via a new `stratum_env_override` parameter), a `platform.platform()`
>   attestation, and a required `date_stratum_id` parameter (no default) once, at play time,
>   validates `out_dir` against `stratum_output_root()` before publishing, and records all three in
>   the arm manifest. Task 10 validates the three fields in closed form per arm
>   (`_validate_stratum_fields` -- presence via `_MANIFEST_REQUIRED_KEYS`, unknown-stratum/
>   non-string/empty rejected), extends the arm-vs-arm equality loop with `date_stratum_id`, and
>   replaces the self-detecting `assert_no_cross_stratum_pooling` call with one built from each
>   arm's OWN manifest-recorded `stratum`/`platform_attestation` -- the combiner never calls
>   `detect_stratum()` itself any more. `stratum_env_override` is repurposed from a detection
>   source into an optional caller expectation, checked against the arms' own recorded stratum and
>   aborting as a "contradictory override" on mismatch. Six new tests: reject mixed Windows+Kaggle
>   arms, accept two equally-attested arms, reject a contradictory override, reject differing
>   `date_stratum_id`, reject an unknown stratum value, reject a type-wrong manifest value.
>   Self-found, same pass: Task 9's new `detect_stratum()` call makes `UnattestedStratumError`
>   newly reachable from the arm CLI's call graph, falsifying that handler's own "does not need
>   widening" comment -- widened and corrected here, not deferred (§1n).
> - **Rev. 15 → Rev. 16** (§1o, 2 P1, mechanical follow-up): two remaining gaps in Rev. 15's own
>   fix, found by re-reading the actual Rev. 15 text rather than assumed closed. **P1:**
>   `detect_stratum`'s `env_override` bypassed `platform.system()` entirely -- `env_override=
>   "kaggle"` on the real, fixed Windows measurement host (or the reverse on a non-Windows box)
>   succeeded silently, which was harmless before Rev. 15 (nothing trusted the result downstream)
>   but became consequential the moment Rev. 15 made it the arm manifest's authoritative,
>   Task-10-trusted `stratum` value. Fixed: the override may now only confirm what the platform
>   can prove, never contradict it (Task 3, §6). **P1:** Task 9's new `out_dir`-vs-
>   `stratum_output_root` check (Rev. 15) compared an absolute, OS-native-separator path (every
>   `out_dir` the plan's own tests construct, via `tmp_path`) against a bare relative,
>   forward-slash `expected_root` string -- rejecting the plan's own tests, not just genuine
>   mistakes. Fixed with a separator-normalized, slash-bounded substring check (Task 9, §12),
>   matching Task 2's own `_normalize_path` precedent (§5) for the identical class of bug.
> - **Rev. 16 → Rev. 17** (§1p, 3 P1, code review on Task 3's real implementation): a focused
>   code review on the just-committed `strata_guard.py`, live-reproduced against the real module
>   (not just read), plus one more plan-text gap in Task 9's own Rev. 16 fix. **P1:** the Rev. 16
>   override-consistency check only tested "is this platform Windows or not" -- Darwin (macOS) is
>   also not Windows, but it is not the approved Kaggle environment (Linux) either, so
>   `env_override="kaggle"` on a Mac laptop still succeeded, reintroducing P2-1's own "non-Windows
>   silently trusted as Kaggle" failure mode through the override path specifically. Fixed:
>   checked against Linux specifically, not merely "not Windows" (Task 3, §6). **P1:**
>   `assert_no_cross_stratum_pooling` never validated that each record's `.stratum` is even a
>   known value -- two records that AGREE with each other on an unrecognized stratum (e.g.
>   `"colab"`) passed silently, since the mixed-strata check only compares records against EACH
>   OTHER, never against `VALID_STRATA`. Fixed: every record's stratum is checked against
>   `VALID_STRATA` before the agreement check runs (Task 3, §6) -- defense in depth, independent
>   of whatever an upstream caller may already validate. **P1:** Task 9's Rev. 16 out_dir fix
>   normalized separators but never collapsed `.`/`..` segments before the containment check --
>   `out_dir=f"{expected_root}/../../../elsewhere"` still contained `expected_root` as a literal
>   substring while resolving somewhere else entirely once the OS processed the `..` segments,
>   defeating the per-stratum separate-tree requirement the check exists to enforce. Fixed with
>   `posixpath.normpath` before the containment check (Task 9, §12) -- verified against both a
>   forward-slash and a backslash traversal payload, standalone, before trusting the plan text.
> - **Rev. 17 → Rev. 18** (§1q, made Task 4 agent-executable, not a review round): the prior text
>   said "see the Rev. 1 code" without containing it anywhere. Confirmed, not assumed, that it
>   never existed: full git-history search for `find_near_duplicate_flags`/`near_duplicate.py`
>   returns nothing before this round; the earliest commit ever touching this plan document
>   already carried the same stub. Task 4 (§7) is designed fresh from DESIGN sec 3.3 and this
>   codebase's own existing `to_id` species-normalization convention (Jaccard overlap, `>= 0.5`
>   inclusive threshold, self-comparison excluded, deterministic ordering, fail-closed on
>   malformed input, 13 tests) -- not reconstructed as an assumed historical contract. Task 10's
>   call site (§13) had the exact bug this round's Auftrag warned about: it iterated
>   `reference_species` for BOTH the six holdout candidates and the reference set, so every team
>   was compared against a reference set that included itself, and there was no way to supply the
>   six holdout teams' own species at all. Fixed with a new required parameter,
>   `holdout_candidate_species`, genuinely separate from `reference_species`, both now bound to
>   the real six/nine-team geometry (the former checked against `manifest_a["holdout_teams"]`'s
>   key set, matching `holdout_content_hashes`'s own precedent). Self-found in the same pass: the
>   new loop could let a malformed empty species list escape as a raw `ValueError` -- wrapped as
>   `GateBAbort`, with a new test and exception-audit-table row, matching this plan's established
>   "catch on introduction, not later" discipline. Task 13's "nine existing Champions-M-A teams"
>   (§16 item 5) is now traced to a concrete list -- the real on-disk set is 10 files, but "nine"
>   reconciles exactly once the shared hero is excluded (5 `panel_champions_v0` + 4
>   `panel_champions_coverage_v0` opponent-side teams).
>
> ~~As of Rev. 18: Task 1 ... Tasks 4–13 remain unimplemented as code ... and no team file or
> sealed hash exists.~~ **Superseded — see the current status immediately below.** That paragraph
> described the branch as of Rev. 18 and is kept only so the progression is traceable.
>
> **Implementation status as of Rev. 24 (2026-07-23).** **Tasks 1–12 AND all of Task 13 (steps
> 1–3) are implemented, tested and committed** on branch `feat/champions-gate-b-task-1-schedule` —
> not yet merged to `main`. Tasks 1–12 and Task 13 steps 1–2 are Codex-PASS; **step 3 is
> code-complete and UNDER REVIEW.** Its source condition is **SATISFIED** (§2a — the six VGCPastes
> teams are frozen, complete, and `validate-team`-legal).
>
> **Done:** the six `.txt`/`.packed` artifacts exist under the canonical holdout team directory,
> byte-identical to their frozen sources; every team is sealed via `seal_team` with its
> `content_hash` proven equal to `panel.team_content_hash`; all six return exit 0 from the pinned
> `validate-team`; the holdout manifest exists and is the single home of the public-to-internal ID
> mapping (Amendment A1.1); the real leakage scan (identifier **and** raw-payload legs) reports zero
> hits outside the allowlisted artifacts, and `assert_disjoint_from_coverage` passes. **Step 3 adds:**
> the Gate-B static baseline contract (A1.3) with real frozen VALUES verifying clean; the panel YAML
> with real content; the hash freeze into `strength_holdout_schedule.py`'s constants
> (`STRENGTH_HOLDOUT_EXPECTED_PANEL_HASH` / `STRENGTH_HOLDOUT_EXPECTED_MANIFEST_HASH`, the latter
> binding the frozen selection order + public→internal mapping and refusing a non-six-team /
> non-`1..6` / duplicate manifest); the CLI data wiring that removes both named Task-13 blockers and,
> before battle 1, binds the frozen panel/manifest identity and fully verifies the baseline; and the
> near-duplicate audit against the nine reference teams with a written disposition per flag
> (selection audit §5a).
>
> **Outstanding:** the whole-suite verification and Codex review of this branch. **No `.packed` or
> sealed hash is claimed beyond what is committed**, and **no Gate-B server has been started and no
> Gate-B battle has been played** — every task so far is code, tests, docs and frozen source evidence
> only.
>
> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking. **Task 13 is no longer blocked on the source-proof** —
> that condition is met (§2a). The **live Gate B run remains BLOCKED** and is a separate
> authorization (§17); nothing in Task 13 starts a server, plays a battle, or produces a strength
> claim.

**Goal:** build the code, tests, and sealed team data for Gate B to the
point where it is reviewable and mergeable, with **no live run** of any kind included.

**Architecture (revised in Rev. 2):** Gate B is now **two runner entry points, not one**:
`run_strength_holdout_arm` plays exactly one arm (Candidate A *or* Baseline B) against a server
that must be freshly started for that call, and publishes only that arm's own dataset;
`combine_strength_holdout_arms` reads both already-published arms, runs every guard, renders the
verdict via the **unmodified, existing** `eval/report.py` pipeline, and publishes the full
evidence bundle atomically. This split exists because Rev. 1's single-function design played
both arms against one implicit running server, which — per the seed-counter architecture
verified in this revision (§1a, Finding 4) — does **not** give the two arms matching seeds. It
mirrors the existing `eval/schedule_2b4.py` determinism-gate pattern (same schedule, twice, on
two fresh servers with the same `seed_base`), not a new invention.

**Tech Stack:** Python (stdlib + existing `showdown_bot` package), pytest, no new third-party
dependencies.

---

## 0. Boundaries for Tasks 2–13 (Rev. 1 boundaries, unchanged) — Task 1 is complete

Task 1 (`strength_holdout_schedule.py` + `test_strength_holdout_schedule.py`, including this
revision's `panel_hash` fix) is implemented, RED-then-GREEN tested, and committed on branch
`feat/champions-gate-b-task-1-schedule` -- not pushed, no PR opened. The boundaries below describe
Tasks 2–13, which remain exactly as originally scoped:

- No production or test code has been written to `showdown_bot/src` or `showdown_bot/tests` for
  Tasks 2–13. Every code block below (Tasks 2–13) lives inside this markdown file.
- No team was invented. Every example uses obviously-synthetic fixture identifiers — never a
  real team roster, never presented as real data.
- No server, battle, benchmark, or gate was run — true for Task 1 too: its tests are offline
  unit tests only, no live component touched.
- Nothing for Tasks 2–13 was committed, pushed, or opened as a PR. New/changed files for those
  tasks are staged (`git add`) at most, not committed.
- No Champions Strength claim is made anywhere in this document. Champions Strength remains
  NO-GO, unchanged by this plan.

## 1. Grounding (Rev. 1 table, still accurate)

Full citations in `docs/projects/champions/audits/2026-07-21-gate-b-grounding-report.md` and its
Rev. 2 addendum (`...-addendum-rev2.md`) — read both before this plan.

| Contract | Value | Source |
|---|---|---|
| Battle-key count | 6 teams × 2 opponent policies × 15 seeds = **180** | DESIGN:260-263 |
| Candidate / Baseline | A = `heuristic` hero agent, B = `max_damage` hero agent, same fixed hero team | DESIGN:256-259 |
| Decision rule | exact two-sided binomial McNemar, `eval/stats.py` unchanged | DESIGN:264-269 |
| `N_DISCORDANT_CLAIM_MIN` | 10 (below ⇒ UNDERPOWERED) | `eval/stats.py:16` [verified] |
| Verdict precedence | `SAFETY-FAIL > UNDERPOWERED > GO > NO-GO`, plus cell-flip and weak-policy-only NO-GO reasons | `eval/report.py:856-877` [verified, Rev. 2: full body] |
| Candidate identity formula | `sha1({hero_agent, git_sha, config_hash})[:16]` | `learning/provenance.py:35-41` |
| Frozen coverage hashes | 5 entries | `config/eval/coverage/champions_coverage_v0_manifest.json` |
| Six-team sourcing process | **resolved by the user in this revision — see §2** | was open in Rev. 1 |

## 1a. What changed in Rev. 2 — every review finding, verified and closed

Each row: the P1/P2 finding, what I confirmed by reading the real code (not re-trusting Rev. 1's
own claims), and where the fix lives now.

| # | Finding | Verified against | Fixed in |
|---|---|---|---|
| P1-1 | `cell_flips=[]`/`strength_delta=counts.delta` could hide a losing-cell flip or weak-policy-only GO | Read `eval/report.py` in full (1201 lines). `_paired_verdict`'s real body has two more checks Rev. 1 never triggered: `if cell_flips: ... NOGO` and `if strength_delta <= 0: ... NOGO`. `_build_cells`/`_find_cell_flips`/`_strength_delta` are fully generic (no team/schedule assumptions) and directly importable — confirmed by reading all four in full. | Task 8 |
| P1-2 | Upstream guard weaker than the real hardened `coverage_runner.py` | Read `coverage_runner.py` in full (627 lines, not just 300-370) and `coverage_verdict.py` in full. Real I8-D-verdict check is 25-field closed-schema + counter-invariant + canonical-schedule-rebuild + PASS-invariant (≈23 sub-checks). Coverage's own verdict schema is a **different** 20-field shape with per-cell floors, not a variant of I8-D's. | Task 7 |
| P1-3 | `config_hash`/`calc_backend`/`schedule` caller-controlled | Confirmed: my own Rev.-1 grounding report already documented that neither `i8d_runner.py` nor `coverage_runner.py` accept these as trusted input — I just didn't follow my own finding when writing Task 7/9's first draft. | Task 7, Task 9 |
| P1-4 | Paired seeds not bound | Read `eval/seeding.py`, the seeded-battle server patch, and the original approved seed-mechanism design (`docs/projects/evaluation/plans/2026-07-01-2b35-T1-...md`) in full. **Confirmed as a real, guaranteed bug, not a risk**: the server's seed counter is a process-lifetime global (`evalBattleCounter`), reset only by a fresh server process. Two arms sharing one server session get *disjoint* real seeds even though their labels match. `eval/schedule_2b4.py` already solves this for a different gate with "two fresh servers, same `seed_base`" — same fix adopted here. | Task 9, Task 10 (architecture split) |
| P1-5 | Guards never called from the top-level runner; `safety_pass=True` hardcoded | Confirmed by re-reading my own Task 9 draft: none of Tasks 2-6's guard functions were ever invoked. | Task 10 (every guard wired), Task 8 (`safety_pass` computed from real `invalid_choices`/`crashes`/`end_reason`) |
| P1-6 | Evidence not reproducible (only `verdict.json` published) | Confirmed: Rev. 1 published one file. Real I8-D/Coverage publish `seeds.jsonl`/`profile.jsonl`/`battle.jsonl` alongside `verdict.json`. | Task 10 (full bundle: both arms' datasets + seed-log proofs + per-cell breakdown + verdict, one atomic publish) |
| P1-7 | Team sealing hashed only `.txt` | Read `eval/panel.py` in full. Confirmed: the real `team_content_hash(teams_root, team_path)` hashes `.txt` **and** `.packed` together and raises if either is missing — and my Rev.-1 `_team_content_hash` was a *different, incompatible, same-named* function that silently produced a different digest. This was a live naming collision, not just an omission. | Task 12 (imports the real function, does not redefine it) |
| P1-8 | `load_baseline_manifest` doesn't exist; ledger entry missing required fields | Read `eval/baseline.py` and `eval/heldout_ledger.py` in full, plus the real committed `config/eval/heldout_ledger.jsonl` (5 lines, shown complete). Real loader is `load_baseline` (schema-only) + `verify_baseline` (drift-checking, raises `BaselineDriftError`), 16 required fields. Real ledger `run` entries require 9 fields including `date`, `purpose`, `result_sha256` — Rev. 1's draft had 5. | Task 6, Task 10 |
| P1-9 | Tasks 9/11 shipped `NotImplementedError`/`schedule=None` | Confirmed as a real, avoidable gap — the battle loop can be fully written and tested offline via an injected gauntlet-runner callable. | Task 9 (`gauntlet_runner` parameter, default real, injectable in tests) |
| P2-1 | Non-Windows silently treated as Kaggle | Confirmed: Rev. 1's `detect_stratum` literally returned `KAGGLE_STRATUM` for any non-Windows `platform.system()`. | Task 3 |
| P2-2 | Missing-pair test expects the wrong exception type | Confirmed: the Rev.-1 test called `pair_runs` directly (which raises `MissingPairError`) but asserted `pytest.raises(GateBAbort)` — `GateBAbort` is only raised by code that *wraps* `pair_runs`, so the test as written could never pass. | Task 10 |
| P2-3 | Line-based `git grep` can't reliably match multi-line team content | Confirmed: `-F` fixed-string `git grep` is line-oriented; a multi-line team export string with embedded newlines cannot match as one pattern. DESIGN's own text says to scan for "team_hash, team_path, team_id, **packed/.txt content**" — the content case needs hash comparison, not grep. | Task 2 |

Two more bugs I found myself while re-verifying, neither flagged explicitly by the reviewer but caught by the same re-verification pass: **`BattleKey.seed` (0-14) repeats 12× across the 180-key schedule** (once per each of the 6×2 team/policy cells) and is not the contiguous 0-179 index `derive_battle_seed` actually needs — fixed in Task 1 by adding a `seed_index` field. And the Rev.-1 `_team_content_hash` naming collision noted under P1-7 above.

## 1b. What changed in Rev. 3 — the Rev. 2 review findings, verified and closed

| # | Finding | Verified against | Fixed in |
|---|---|---|---|
| P1-1 (Rev.3) | `combine_strength_holdout_arms` required `manifest_a["candidate_identity"] == manifest_b["candidate_identity"]` | Re-derived `make_candidate_identity({hero_agent, git_sha, config_hash})` by hand for arm A (`hero_agent="heuristic"`) and arm B (`hero_agent="max_damage"`): the `hero_agent` field is hashed directly, so the two arms' `candidate_identity` values differ by construction for every genuine run — the Rev. 2 check would abort 100% of real runs. Confirmed against DESIGN:367-374 (quoted in the base grounding report §6): *"Candidate A ... **is** that shared candidate; Baseline B is the reference, not a separately-gated candidate."* Confirmed the Rev. 2 test fixture masked this by hardcoding `"candidate_identity": "cand123"` on **both** manifests regardless of `hero_agent`, so the broken equality check happened to pass in tests without ever exercising the real formula. | Task 10 |
| P1-2 (Rev.3) | `i8d_verdict_path`/`coverage_verdict_path` defaulted to `""` and were skipped when falsy | Re-read my own Task 10 code: `if i8d_verdict_path: verify_...` — a caller omitting either argument gets a rendered verdict with **zero** upstream verification, contradicting DESIGN §5's *"latency PASS and coverage PASS and an independent-holdout GO"* conjunction this whole plan exists to enforce in code rather than by caller discipline. The docstring's "production callers must always pass real paths" was documentation, not enforcement — exactly the trust-based pattern `coverage_runner.py`'s own review comments repeatedly reject. | Task 10 |
| P2 (Rev.3) | `_all_guards_pass_for_test` monkeypatch seam isolated nothing | Re-read the production code: `_all_guards_pass_for_test` is defined but never called anywhere in `combine_strength_holdout_arms`. The three Task 10 tests that patched it were passing only because their fixture inputs (`holdout_content_hashes=None → {}`, `reference_species=None`) made the *real* guards no-op via the same optional/skip pattern as P1-2, not because the patch did anything. | Task 10 (seam removed; tests now pass explicit, legitimate `{}` inputs to the real, always-called guards, and monkeypatch only the two upstream verdict-artifact functions, which have their own full independent test coverage in Task 7) |
| P2 (Rev.3) | `opp_team_hash = key.holdout_team_id` could reach a live arm run unbound | Confirmed: nothing in `run_strength_holdout_arm` required a real content hash before writing a row — a live run today would silently write a team ID string into a field every downstream consumer (leakage scan, disjointness check, cell grouping) treats as a content hash. | Task 9 (`holdout_team_content_hashes` is now a required parameter; a missing entry for any scheduled team aborts before that battle plays, not after) |

## 1c. What changed in Rev. 4 — the Rev. 3 review findings, verified and closed

| # | Finding | Verified against | Fixed in |
|---|---|---|---|
| P1 (Rev.4, most severe across all revisions) | Arm runner read `stats.winner`/`stats.end_reason`/`stats.turns` — fields that don't exist on `GauntletStats` | Read the complete real `GauntletStats` class (`gauntlet.py:222-240`) and the one real production caller building a `result_jsonl`-schema row (`cli.py`'s `run_schedule`/`on_br`). `GauntletStats` has only `games/hero_wins/villain_wins/ties/invalid_choices/crashes/latencies` — all run-lifetime aggregates. `winner`/`turns`/`end_reason` are **structurally unreachable** from it under any name; they only ever arrive via the `on_battle_result(record)` callback `run_local_gauntlet` accepts, built by `_battle_result_record` from the parsed room log. Confirmed via the real production caller: `stats` is used there ONLY for a console-log line, never for row construction. | Task 9 (full rewrite of the per-battle loop: `on_battle_result` callback + `eval.result_jsonl.BattleResultWriter`, mirroring `cli.py`'s `on_br` exactly) |
| P1 (Rev.4) | Seed logs were stored (`seed_log_path`) but never verified | Confirmed: `run_strength_holdout_arm` accepted the parameter, wrote it into `arm_manifest.json`, and never called anything that reads it. Read `eval/seeding.py`'s `verify_seed_log(path, base, expected_count)` in full, and both `i8d_runner.py`'s and `coverage_runner.py`'s private `_verify_seed_alignment` wrapper (identical shape, called after the battle loop, before publish) verbatim. | Task 9 (Channel-A `SHOWDOWN_BATTLE_SEED_BASE` env check before battle 1; `verify_seed_log` + per-row `battle_index` cross-check after the loop, before `os.replace`; malformed/missing/misaligned seed log aborts with no `out_dir` published) |
| P1 (Rev.4) | Baseline-drift guard specified (Task 6) but never called from `combine` | Confirmed: `combine_strength_holdout_arms` never imported or called `load_baseline`/`verify_baseline` — Task 6 built the manifest and its own isolated tests, but the live-flow wiring was missing. | Task 10 (`load_baseline` + `verify_baseline` called before pairing; `BaselineDriftError` wrapped as `GateBAbort`; new RED test forces a drift and confirms the abort) |
| P1 (Rev.4) | Upstream verdict checks bound `schedule_hash` but not `hero_team_hash`/`opp_team_hashes` to the canonical rebuild | Re-read my own Rev. 1 grounding report, which already documented `coverage_runner.py:371-388` binding `hero_team_hash`/`opp_team_hashes` to the freshly-rebuilt canonical schedule as a check DISTINCT from the `schedule_hash` bind — Task 7 only implemented the latter. `schedule_hash` binds structure; it doesn't guarantee team content integrity by itself. | Task 7 (`_rebuild_i8d_schedule_hash`/`_rebuild_coverage_schedule_hash` renamed to `_rebuild_i8d_canonical_schedule`/`_rebuild_coverage_canonical_schedule`, now return the whole schedule object; both verifiers independently bind `hero_team_hash` and sorted `opp_team_hashes`) |
| P2 (Rev.4) | Only `MissingPairError` caught from `pair_runs` | Confirmed against the full `eval/pairing.py` (already read in Rev. 2 research): `PairingError` has 6 subclasses (`SelfComparisonError`, `RunMismatchError`, `PairSeedMismatchError`, `DuplicateRowError`, `MissingPairError`, `RowCountError`); only one was caught, so the other 5 would escape `combine_strength_holdout_arms` raw, uncaught by the CLI. [Correction, Rev. 7 (NF2): this row originally claimed the CLI catches `except (GateBAbort, StrengthHoldoutRunError)` — false; the actual handlers only ever caught `GateBAbort`, and that false claim was never verified against the real CLI code before being cited as the reason for this fix. The reasoning that other `PairingError` subclasses would escape uncaught was still correct — `GateBAbort` alone doesn't catch them either.] | Task 10 (catches the base `PairingError`; new test forces a `DuplicateRowError` via a corrupted arm-A fixture and confirms it wraps as `GateBAbort` too) |
| P2 (Rev.4) | Empty `{}` guard inputs were a production-reachable bypass, not just a test convenience | Confirmed: Rev. 3's own Task 11 CLI handler passed `holdout_content_hashes={}, reference_species={}` in **production** code, with a comment excusing it as "PROPOSED, not wired yet" — the exact vacuous-guard shape Rev. 3 claimed to have eliminated, just relocated one call site down. | Task 10 (`combine_strength_holdout_arms` now unconditionally rejects empty `holdout_content_hashes`/`reference_species`; Task 11's CLI `combine` handler now explicitly raises `GateBAbort` pending Task 13, matching the `arm` handler's already-honest pattern, instead of passing `{}`) |

## 1d. What changed in Rev. 5 — the Rev. 4 review findings, verified and closed

| # | Finding | Verified against | Fixed in |
|---|---|---|---|
| N1 — P1 BLOCKER | `panel_hash` missing from every row → `pair_runs` crashes with a raw `KeyError`, not a `PairingError` | Confirmed against my own `pairing.py` citation from Rev. 2 research: `_CONSTANT_FIELDS = ("schedule_hash", "seed_base", "panel_hash", "format_id", "config_hash")`, and `_check_constant_fields` does `{row[field] for row in rows}` — direct indexing, no `.get`. Grepped my own row-building code (Task 9's `_capture` closure) and Task 10's `_write_arm` test fixture: neither ever set `panel_hash` on a row. Every Task 10 test that reaches `pair_runs` would have failed with an uncaught `KeyError`, not the `GateBAbort` its own assertions expect. | Task 9 (`"panel_hash": schedule.panel_hash` added to the captured row) and Task 10 (`_write_arm`'s row template gets `"panel_hash": "panel1"`, matching its own manifest) |
| N2 — P1 | `result_sha256` doesn't hash the published bytes | Confirmed: `_write_json_atomic` (`i8d_runner.py:106-112`) writes `json.dumps(obj, sort_keys=True, indent=2) + "\n"`; my `result_sha256` computation used `json.dumps(payload, sort_keys=True).encode("utf-8")` — no `indent`, no trailing newline, different bytes. A ledger entry whose `result_sha256` doesn't match `sha256sum verdict.json` on the real file is unverifiable, i.e. decorative. | Task 10 (`verdict_text` computed once with the canonical recipe, hashed, then written directly — single source of truth instead of two independent `json.dumps` calls trusted to stay in sync) |
| N3 — P2 | `teams_root` never reaches the leakage content-scan | Confirmed: `scan_for_content_leakage` called `_all_tracked_team_content_hashes()` with no argument, even though that function has its own `teams_root` parameter — `combine_strength_holdout_arms`'s own `teams_root` was silently dropped. Combined with `except PanelError: continue`, a wrong `teams_root` degrades fail-open ("scanned nothing, found nothing") rather than erroring. | Task 2 (`teams_root`/`cwd` threaded through `assert_no_holdout_leakage` → `scan_for_leakage`/`scan_for_content_leakage` → `_all_tracked_team_content_hashes`/`_git_tracked_files`/`_grep_identifier`, with every `git` subprocess call now taking an explicit `cwd` instead of relying on ambient process CWD — also closes the noted Windows-multi-worktree test-flakiness risk) |
| N4 — P3 | Test fixture's row serialization diverges from the canonical writer | Confirmed: `_write_arm` wrote rows via `open(..., "w", encoding="utf-8")` (no `newline=""`) and `json.dumps(row)` (default separators) — not a correctness bug on its own (`json.loads` doesn't care about formatting), but inconsistent with `eval.result_jsonl`'s canonical `separators=(",", ":")` convention used everywhere else in this codebase, and CRLF-on-Windows-divergent the moment anything hashes the file (as N2's fix now does for the combined bundle). | Task 10 (`_write_arm` now opens with `newline=""` and serializes with `separators=(",", ":")`, matching the canonical format) |

Fixing N3 required also updating the monkeypatch lambdas in Task 2's own tests
(`_all_tracked_team_content_hashes`, `scan_for_leakage`, `scan_for_content_leakage`) to accept
the new `teams_root`/`cwd` keyword parameters — those tests would otherwise have broken from
this revision's own N3 fix, a reminder to re-run the full affected test file after any signature
change, not just the tests written for that specific change.

## 1e. What changed in Rev. 6 — two findings that survived three review rounds unmentioned

Both were part of the original Rev. 3 review's finding set but never made it into §1c, §1d, or
any deferral note — genuinely absent, not previously addressed and mis-filed.

| # | Finding | Verified against | Fixed in |
|---|---|---|---|
| F3 — P1 | An arm's `rows.jsonl` was never validated against its own `arm_manifest.json` | Re-read `_read_arm`: `json.loads` per line, `json.load` for the manifest, `return` — no `validate_battle_row`, no `len(rows) == manifest["n_rows"]`, no per-row `config_hash`/`git_sha`/`schedule_hash`/`seed_base`/`panel_hash` cross-check against the manifest, no re-derivation of `candidate_identity` from the manifest's own `hero_agent`/`git_sha`/`config_hash`. Every downstream use (`verify_i8d_verdict_artifact`, `verify_coverage_verdict_artifact`, the ledger entry, the published payload) trusts `manifest_a`'s claims on faith. An arm directory assembled from a manifest and a `rows.jsonl` from two different runs would pass silently. | New `_assert_rows_match_manifest(rows, manifest, which)`, called for both arms immediately after `_read_arm`; `_read_arm` itself now calls `validate_battle_row` per row; `pair_runs`'s `expected_rows` now comes from `manifest_a["n_rows"]` (independently sourced and now itself verified) instead of the tautological `len(rows_a)` |
| F6 — P2 | Ledger entry written *after* publish | Confirmed: `os.replace(staging_dir, out_dir)` ran before `append_entry`. `append_entry` validates and can raise `LedgerError` (e.g. on any empty-string field — real until Task 13 back-fills real hashes). A `LedgerError` there would leave a published, "successful"-looking bundle with no ledger record, so the next `check_access` would see no prior `run` entry and silently not enforce the one-attempt budget — exactly the held-out-reuse path the ledger exists to prevent. | `append_entry` now runs before `os.replace`, wrapped so a `LedgerError` becomes `GateBAbort` and `out_dir` is never created; reasoning recorded as an inline comment per the explicit request, not just in this table |

Two smaller items bundled into the same fix: `pair_runs(..., expected_rows=len(rows_a))` was
tautological (true by construction for A, redundant with F3's own check for B) — now uses
`manifest_a["n_rows"]`, making `RowCountError` reachable again. And `_write_arm`'s fixture wrote
`"seed": i` as a bare int where the real `derive_battle_seed` always returns a `"sodium,<32 hex>"`
string — the same class of unfaithful-fixture issue N4 already fixed for JSON formatting, just on
a different field; now uses the real function.

## 1f. What changed in Rev. 7 — the fixes themselves raised new raw exceptions

Both findings below trace to the same mechanism the user named explicitly: Rev. 6's own fixes
(F3's `_read_arm`/`_assert_rows_match_manifest`) were checked against "does this satisfy Rev.
6's finding list," not "does every exception this new code can raise stay inside the one abort
class the CLI boundary actually catches." That is now a checkable table (below), not a restated
principle.

| # | Finding | Verified against | Fixed in |
|---|---|---|---|
| NF1 — P2 | `_read_arm`'s new `validate_battle_row` call and `_assert_rows_match_manifest` itself raised raw, uncaught exceptions (`ResultRowError`, `KeyError`) instead of `GateBAbort` | Re-read both functions exactly as committed in Rev. 6: `validate_battle_row(row)` was called with no `try`/`except`; `_assert_rows_match_manifest` indexed `manifest["n_rows"]`/`manifest[field]`/`row[field]` directly, with no presence check first. Neither `ResultRowError` nor `KeyError` is caught anywhere between there and the CLI. | `_read_arm` (`ResultRowError` → `GateBAbort`); `_assert_rows_match_manifest` (every expected key presence-checked before any indexed access → `GateBAbort`) |
| NF2 — P2, pre-existing | This plan's own documentation (§1a's Rev.-4 `PairingError` row, and the code comment on that same fix) falsely claimed the CLI catches `` except (GateBAbort, StrengthHoldoutRunError) `` — the real CLI handlers (Task 11) only ever catch `GateBAbort`. `StrengthHoldoutRunError` from either upstream-verdict verifier is the single most likely real abort path in this whole plan, and it was left escaping uncaught, undetected across 3 revisions, because the false claim was cited as justification for a different fix without ever being checked against the real CLI code | Re-read `run_strength_holdout_arm_cli`/`run_strength_holdout_combine_cli` (Task 11, §14) in full: both are `except GateBAbort as exc:` only — no second exception type anywhere in either handler | `verify_i8d_verdict_artifact`/`verify_coverage_verdict_artifact` calls now wrapped in `combine_strength_holdout_arms` itself (`except StrengthHoldoutRunError` → `GateBAbort`); both false-claim locations corrected (the §1a table row, and the `PairingError` comment in Task 10's implementation) |
| SF1 — self-found, P3 | `_read_arm`'s own `open()`/`json.loads()`/`json.load()` calls — the exact lines NF1 was already touching — can raise `OSError`, `UnicodeDecodeError`, or `json.JSONDecodeError` for a missing, unreadable, or corrupted arm directory; none of those is `ResultRowError`, so NF1's own fix did not cover them | Found while building the exception-audit table below, not reported by the user. Re-read `_read_arm`'s two `open()` calls and confirmed neither was guarded | `_read_arm`, same function, same pass — all three now also become `GateBAbort` (disclosed here per the Rev. 2 precedent of fixing a self-found, same-shape, same-file bug in the same pass rather than deferring it unmentioned, §1a) |

### Exception audit — every exception reachable from either public entry point toward the CLI

**Rev. 7's table was scoped wrong, and that was itself the bug.** "Every function touched in
Rev. 7" is a diff-scoped question — it can only ever find gaps in code that round happened to
edit, which is exactly why NF3 (the write-side twin of NF1's read-side fix, in `run_strength_holdout_arm`,
a Task 9 function Rev. 7 never touched) and NF4 (git-subprocess calls, some dating to Task 2/9's
original Rev. 1-4 code) survived invisibly. The user's correction, verbatim: the scope must be
"every exception that can leave one of the two public entry functions toward the CLI" — a
boundary, not a diff. Below is that boundary, walked fresh from both `run_strength_holdout_arm`
and `combine_strength_holdout_arms` outward, not from this round's edit list inward.

**Method, stated so the boundary drawn below is checkable, not asserted:** every exception-raising
statement in code THIS PLAN AUTHORS (Tasks 1–12) is traced below, fully. For calls into
PRE-EXISTING, externally-authored production code, this audit trusts the SAME established
contract this plan already relies on elsewhere (`load_packed_team` → `FileNotFoundError`,
`verify_seed_log` → `SeedLogError`, `pair_runs` → `PairingError`, `report.py`'s cell/verdict
functions operating on already-schema-validated rows) — re-verifying those external modules'
complete internals is a different, larger undertaking than NF3/NF4 asked for, and is called out
explicitly below rather than silently assumed. Generic OS-resource failures on operations ANY
Python code performs (`os.makedirs`, `shutil.copytree`, disk-full/permission-denied on a write)
are deliberately NOT chased file-by-file: they are not a Gate-B-specific data/trust boundary
(CLAUDE.md: validate at boundaries, trust framework guarantees elsewhere), and chasing them here
would mean auditing every filesystem call in the whole plan, an unbounded, different task. The
boundary actually walked exhaustively is the one NF1–NF4/SF1/SF2 all share: **every JSON/file
read and every external-subprocess call reachable from either entry point** — confirmed complete
for that specific mechanism by grepping the entire plan for `json.load(`/`json.loads(` and
`subprocess.run(` and accounting for every production (non-test) hit.

#### `run_strength_holdout_arm` (Task 9)

| Exception | Raised by | Caught inside `run_strength_holdout_arm`'s own call graph? | Crosses toward the CLI as |
|---|---|---|---|
| `CalledProcessError` / `FileNotFoundError` | `_git_is_dirty()` (via `resolve_strength_holdout_provenance`) | yes (NF4, Rev. 8) | `GateBAbort` |
| `CalledProcessError` / `FileNotFoundError` | `_git_sha()` (via `resolve_strength_holdout_provenance`) | yes (NF4, Rev. 8) | `GateBAbort` |
| — | `resolve_strength_holdout_provenance`'s own dirty-tree check | raises `GateBAbort` directly | `GateBAbort` |
| `FileNotFoundError` | `load_packed_team(abs_path)` (hero + opponent team, per battle) | yes (Rev. 3, unchanged) | `GateBAbort` |
| — | missing-hash / seed-base-env / seed-log-path / existing-out_dir / `stats.games != 1` / empty-`captured` checks | all raise `GateBAbort` directly | `GateBAbort` |
| `ResultRowError` | `writer.write(captured)` (`BattleResultWriter`, per battle) | yes (NF3, Rev. 8) | `GateBAbort` |
| `SeedLogError` | `verify_seed_log(...)` (after the loop, before publish) | yes (Rev. 4, unchanged) | `GateBAbort` |
| `Exception` (any -- unaudited callee, deliberately not narrowed) | `asyncio.run(gauntlet_runner(...))` (the real `run_local_gauntlet`, external websocket client) | yes (NF5, Rev. 9) — a BOUNDARY WRAP, not a contract audit: converts whatever an unaudited callee raises without needing to know what that is; `BaseException` subclasses (`KeyboardInterrupt`, `SystemExit`) are untouched since they are not `Exception` subclasses | `GateBAbort` (message includes `seed_index`, `from exc` preserves the original) |
| `CoverageRunError` / `ItemdataStaleError` / `SpeciesMetaStaleError` / `PinnedCalcError` | `_derive_config_hash` → `resolve_coverage_provenance(...)` → `effective_config_manifest(...)` → `config_provenance_for_format(...)` | yes (Rev. 10, §1i) — AUDITED, not boundary-wrapped: `resolve_coverage_provenance`/`resolve_i8d_provenance` read in full and confirmed structurally identical (same `effective_config_manifest` call, same args, `COVERAGE_FORMAT == I8D_FORMAT == STRENGTH_HOLDOUT_FORMAT_ID`); the 4 exception types read from `config_env.py`/`engine/items.py`/`engine/species_meta.py`/`engine/calc/pin.py` and caught by name, not via `except Exception` | `GateBAbort` |
| `UnattestedStratumError` (Rev. 15, §1n, self-found while fixing the Task-3-review P1s -- not named in the review itself) | `detect_stratum(env_override=stratum_env_override)` (new, near-top call, Task 9's own Rev. 15 fix) | no — deliberate, matching Task 10's own established treatment of the identical exception type (§13's audit table below: "their exception types stay distinct by design," §1g) | raw `UnattestedStratumError` |
| `ValueError` ("unknown stratum", disclosed, not caught) | `detect_stratum(env_override=stratum_env_override)`, only if `stratum_env_override` is a non-`None`, unrecognized string | no | raw `ValueError` — expected to be pre-empted by argparse `choices=` once Task 11 exposes a `--stratum-override` flag for real (not yet wired; this CLI subcommand is still the Task-13-blocked stub below); disclosed here rather than silently assumed unreachable |
| **residual, narrowly scoped** | `load_format_config(format_id)`'s own malformed-YAML/schema-error path (inside `config_provenance_for_format`, one level past what Rev. 10 audited) | **not independently confirmed** | unknown — its `FileNotFoundError` case is already caught one level down and does not reach here; only its OTHER error path (malformed YAML content) is unconfirmed. Reading `format_config.py`'s own exception handling would close this; not done here, since the residual is now one specific function's one specific error path, not an entire untraced module |

**Verified positive claim, not just a gap list:** every exception in the first nine rows —
i.e. `run_strength_holdout_arm`'s ENTIRE exception surface within code this plan authors, now
INCLUDING the one genuinely live-network call (NF5) and the full config-provenance chain
(Rev. 10) — is `GateBAbort`. Two rows deliberately are not (Rev. 15, §1n): `UnattestedStratumError`
and, on a malformed override, `ValueError`, from the new `detect_stratum()` call -- both left raw
by the same design choice already established for Task 10's identical exception types, not an
oversight. The arm CLI's `except` clause (Task 11) is therefore widened to
`(GateBAbort, UnattestedStratumError)` to match — see the updated note at that call site. Exactly
one row remains genuinely unresolved, and it is now a single function's single error path
(`load_format_config`'s malformed-YAML case) rather than an entire unaudited module — down from
two full trust-boundary rows in Rev. 8, one in Rev. 9.

#### `combine_strength_holdout_arms` (Task 10)

| Exception | Raised by | Caught inside `combine_strength_holdout_arms`'s own call graph? | Crosses toward the CLI as |
|---|---|---|---|
| `ResultRowError` | `_read_arm` → `validate_battle_row(row)` | yes (NF1, Rev. 7) | `GateBAbort` |
| `OSError` / `UnicodeDecodeError` | `_read_arm` → `open(rows.jsonl)`, `open(arm_manifest.json)` | yes (SF1, Rev. 7) | `GateBAbort` |
| `json.JSONDecodeError` | `_read_arm` → `json.loads(line)`, `json.load(fh)` | yes (SF1, Rev. 7) | `GateBAbort` |
| `KeyError` (manifest/row missing a required key) | `_assert_rows_match_manifest` | yes (NF1, Rev. 7) — presence-checked first, so this can no longer actually occur | `GateBAbort` |
| — | `make_candidate_identity(...)` inside `_assert_rows_match_manifest` | n/a — `json.dumps` over JSON-native values (the only types `json.load` can produce) cannot raise | — |
| `StrengthHoldoutRunError` | `verify_i8d_verdict_artifact(...)` | yes (NF2, Rev. 7) | `GateBAbort` |
| `StrengthHoldoutRunError` | `verify_coverage_verdict_artifact(...)` | yes (NF2, Rev. 7) | `GateBAbort` |
| `OSError` / `UnicodeDecodeError` / `json.JSONDecodeError` | `_load_verdict_dict` (inside both `verify_*_verdict_artifact` calls above) → `open(verdict_path)`/`json.load(fh)` | yes (SF2, Rev. 8) — folds into `StrengthHoldoutRunError`, which NF2's existing wrap already catches | `GateBAbort` |
| **untraced, trust boundary** | `_rebuild_i8d_canonical_schedule`/`_rebuild_coverage_canonical_schedule` → `build_i8d_canonical_schedule`/`build_coverage_live_schedule` (pre-existing, `i8d_runner.py`/`coverage_runner.py`) | **not independently re-verified this round** | unknown — a genuinely separate, still-untraced call path (schedule rebuilding, not config-hash derivation); NOT the same function `resolve_coverage_provenance` was, which is now audited above, not merely asserted comparable to this one |
| `BaselineDriftError` | `verify_baseline(...)` | yes (Rev. 4, unchanged) | `GateBAbort` |
| `PairingError` (+ 6 subclasses) | `pair_runs(...)` | yes (Rev. 4, unchanged) | `GateBAbort` |
| `LedgerError` | `append_entry(...)` | yes (Rev. 6, unchanged) | `GateBAbort` |
| `AccessBudgetError` | `check_access(...)` | no — deliberate | raw `AccessBudgetError` |
| `HoldoutNotDisjointError` | `assert_disjoint_from_coverage(...)` | no — deliberate | raw `HoldoutNotDisjointError` |
| `LeakageDriftError` | `assert_no_holdout_leakage(...)` → `scan_for_leakage`/`scan_for_raw_payload_leakage` (Rev. 12, §1k, P1 #2: renamed and rebuilt from `scan_for_content_leakage`, now a repo-wide byte-exact scan) | no — deliberate | raw `LeakageDriftError` |
| `LeakageScanError` (Rev. 8, NF4; Rev. 12 §1k added `_read_git_blob` as a third source) | `assert_no_holdout_leakage(...)` → `_git_tracked_files`/`_grep_identifier`/`_read_git_blob` (git infra failure, or a sealed team's committed blob unreadable, distinct from an actual leak finding) | no — deliberate, same reasoning as `LeakageDriftError` | raw `LeakageScanError` |
| `StrataPoolingError` / `UnattestedStratumError` | `assert_no_cross_stratum_pooling(...)` | no — deliberate | raw |
| `ValueError` (Rev. 18, §1q, self-found) | `find_near_duplicate_flags(...)` (Task 4) → `species_set(...)` -- an empty per-team species list on either the candidate or reference side; the key-set checks earlier only prove the right team_ids are present, not that each one's species list is itself non-empty | yes (Rev. 18, same pass the reachability was introduced) | `GateBAbort` |

**What "caught by the CLI" means today, still:** `run_strength_holdout_combine_cli` (Task 11)
does not call `combine_strength_holdout_arms` for real yet — it unconditionally raises its own
hand-written `GateBAbort` pending Task 13, unchanged this round. What this table proves is what
happens the moment that early stop is lifted: the row-schema / arm-manifest / upstream-verdict /
pairing / ledger trust chain — everything above the four-guard rows — is fully normalized to
`GateBAbort`. The five bottom rows (`AccessBudgetError` plus the four holdout-integrity/leakage-infra
types) are deliberately **not** normalized to `GateBAbort` — that choice is **resolved this round**
(see below), not left as an open question the way it was in Rev. 7.

**The four-guards question (§19 in Rev. 7) is now resolved, not open.** The user's answer:
do not fold `AccessBudgetError`/`HoldoutNotDisjointError`/`LeakageDriftError`/`StrataPoolingError`/
`UnattestedStratumError` into `GateBAbort` — `AccessBudgetError` is a policy refusal with a
defined override (`justification=`), not a technical failure, and collapsing it would hide the one
exception an operator may legitimately overrule; the holdout-integrity types lose information the
same way. The actual defect was never the exception types — it was that the CLI boundary only
ever caught `GateBAbort`, turning everything else into a traceback regardless of intent. Task 11
(§14) now implements the fix at the boundary: `run_strength_holdout_combine_cli` catches a
documented tuple of all 7 classes (`GateBAbort` plus the 5 named above plus `LeakageScanError`,
this round's own addition to the family) via `_describe_strength_holdout_combine_error`, which
maps each to a distinct,
unit-tested message and exit code. `AccessBudgetError`'s raw type — and the existing test that
asserts it (`test_combine_refuses_a_repeat_config_hash_without_justification`) — are both
unchanged; nothing about that test needed to break for this fix to land.

**Also carried forward, unchanged, low priority (per the user's own scoping, not fixed this
round):** nothing in `combine_strength_holdout_arms` binds `manifest_a["n_rows"]`/`len(rows_a)` to
the schedule's own real count of 180 (`build_strength_holdout_schedule`, Task 1) — an arm run
against a truncated or wrong schedule would still pass every check in this document as long as
its own `rows.jsonl` and `arm_manifest.json` agree with each other internally. Both are already
proven internally consistent (F3, NF1); neither is proven to be *the Gate B schedule specifically*.

## 1g. What changed in Rev. 8 — the audit table's own scope was the bug

Both findings below trace to one root cause, stated by the user directly: Rev. 7's exception-audit
table was scoped to "functions touched in Rev. 7" — a diff, not a boundary. A diff-scoped
completeness check can only ever find gaps in code that round happened to edit; it structurally
cannot find a gap in code from an earlier round that this round never touched, no matter how
thorough the check is *within* that wrong scope. §1f's table is now rebuilt on the corrected
scope (every exception reachable from either public entry point toward the CLI), which is what
surfaced NF3, NF4, and SF2 below.

| # | Finding | Verified against | Fixed in |
|---|---|---|---|
| NF3 — P2 | `run_strength_holdout_arm`'s `writer.write(captured)` (`BattleResultWriter`) calls `validate_battle_row` internally and can raise `ResultRowError` — NF1's read-side fix (`_read_arm`) has no effect here; this is a different function in a different task (Task 9, not Task 10) that Rev. 7's diff-scoped table never looked at. Reachable in practice: `_capture` merges `**record` from `_battle_result_record`, whose field set has grown historically (`decision_trace_count`/`_sha256`, `normalized_room_log_sha256`, `panel_split` were all added after this schema's original shape) | Re-read `run_strength_holdout_arm`'s full battle loop and `result_jsonl.py`'s `BattleResultWriter.write()` (calls `validate_battle_row` before appending, `result_jsonl.py:107-110`) — confirmed `writer.write(captured)` had no `try`/`except` anywhere in this plan | `writer.write(captured)` now wrapped, `ResultRowError` → `GateBAbort`, same shape as NF1's read-side fix |
| NF4 — P2 | Three git `subprocess.run` call sites the user named directly raise raw `CalledProcessError`/`FileNotFoundError`, none caught: `_git_is_dirty`/`_git_sha` (Task 9, reachable via `resolve_strength_holdout_provenance` before any battle plays) and `_git_tracked_files` (Task 2, reachable via `assert_no_holdout_leakage`). The Rev. 5 N3 fix that made `cwd`/`teams_root` caller-controllable is what makes the leakage-scan path reachable: a caller-supplied `teams_root` that isn't a git checkout now reaches git directly. A fourth site, `_grep_identifier` (also Task 2, same module as `_git_tracked_files`), has an unguarded `FileNotFoundError` path too (missing `git` executable) even though its nonzero-exit case was already handled — self-found while fixing its sibling in the same module, same pass | Re-read all four call sites: `_git_is_dirty`/`_git_sha`/`_git_tracked_files` use `check=True` with no `try`/`except`; `_grep_identifier` never set `check=True` but is still exposed to a bare `FileNotFoundError` from `subprocess.run` itself. Grepped the whole plan for `subprocess.run(` to confirm no fifth site was missed | `_git_is_dirty`/`_git_sha` (own module, `strength_holdout_runner.py`) fold directly into `GateBAbort`; `_git_tracked_files`/`_grep_identifier` (a different module, `holdout_leakage_scan.py`) fold into a new `LeakageScanError` — kept distinct from `LeakageDriftError` (found-a-leak) rather than reusing that class or reaching across modules for `GateBAbort`, since "couldn't check" and "checked, found a problem" are different things a caller might want to handle differently |
| SF2 — self-found, P3 | `_load_verdict_dict` (Task 7, called by both `verify_i8d_verdict_artifact` and `verify_coverage_verdict_artifact`) opens and JSON-parses `verdict_path` with no guard — a truncated/corrupted verdict file (e.g. an upstream gate crashed mid-write) raises `OSError`/`UnicodeDecodeError`/`json.JSONDecodeError`, none of which is `StrengthHoldoutRunError`, so it would escape even `combine_strength_holdout_arms`'s own NF2 fix (which only catches `StrengthHoldoutRunError`) | Found while walking `combine_strength_holdout_arms`'s full call graph for the rebuilt table, not reported by the user — same failure family as SF1, one module over. Re-read `_load_verdict_dict` and confirmed the `open`/`json.load` call was unguarded | Wrapped the same way as SF1, but raising `StrengthHoldoutRunError` (this module's own established contract) rather than `GateBAbort` directly — NF2's existing `except StrengthHoldoutRunError` in `combine_strength_holdout_arms` catches it with no further change needed there |

Two items surfaced by the same table walk but deliberately **not** fixed this round, disclosed
rather than silently skipped: `_derive_config_hash`'s call into `resolve_coverage_provenance`
(pre-existing, cross-gate shared code; already flagged as unverified since Rev. 1/2, not
re-litigated here) and the real `gauntlet_runner`'s call itself, i.e. `client/gauntlet.py`'s
`run_local_gauntlet` (pre-existing, external websocket client; this is a **newly** surfaced gap,
not previously disclosed anywhere in this plan — the code already defends against a
*misbehaving* return value but not a *raised* exception from the call). Both are named in §1f's
rebuilt table rather than silently trusted. Auditing either fully means reading another module's
complete internals, which is out of proportion to what NF3/NF4 asked for — a decision for the
user, not one this round makes unilaterally.

## 1h. What changed in Rev. 9 — disclosing a gap is not the same as closing it

One finding, and it is NF2's shape again, one level up: this document's own §1g correctly
disclosed `gauntlet_runner` as an untraced trust boundary — but the code comment sitting on the
arm CLI's `except GateBAbort` branch, justifying why that handler does not need widening, dropped
the qualifier and stated the underlying claim as unconditionally true. A disclosure in a table
does not, by itself, prevent a false claim from shipping in the code three lines away from it.

| # | Finding | Verified against | Fixed in |
|---|---|---|---|
| NF5 — P2 | The arm CLI handler's comment claimed "every exception reachable from `run_strength_holdout_arm`'s own call graph... is `GateBAbort`," unqualified — false, since `gauntlet_runner` (named as an untraced trust boundary in this same document's §1g table, two sections up) is reachable from that call graph and does not raise `GateBAbort`. Structurally identical to NF2: a false, unqualified claim sitting directly on an `except` branch, cited as the reason a handler does not need widening, that the next reader would not re-verify | Re-read the comment at the arm CLI's `except GateBAbort as exc:` line against §1g's own audit table two sections above it in the same file — the two directly contradicted each other | The user's preferred fix, not just the comment: `asyncio.run(gauntlet_runner(...))` (Task 9) now wrapped in `except Exception as exc: raise GateBAbort(...) from exc` — a BOUNDARY wrap, deliberately not narrowed to a specific exception type, since converting an unaudited callee's failure to this function's own contract does not require first auditing what that callee can raise. `key.seed_index` is in the message; `from exc` preserves the original; `BaseException` subclasses (`KeyboardInterrupt`, `SystemExit`) are untouched since they are not `Exception` subclasses. The comment is corrected to name this fix and to state precisely which ONE trust-boundary row still remains (`resolve_coverage_provenance`) rather than claim zero |

**Correction: the paragraph that stood here in the first Rev. 9 draft was wrong, and stayed
wrong for exactly one review cycle.** It claimed the same boundary-wrap technique NF5 applied to
`gauntlet_runner` "would close" the remaining `resolve_coverage_provenance` row too, framing it as
an available but unrequested fix. The user rejected that framing directly — a boundary wrap is for
callees that cannot be audited at reasonable cost; `resolve_coverage_provenance` is same-repo,
same-package code that CAN be, and wrapping it instead of reading it would have destroyed
information a reader could otherwise have had, and could have masked a genuine cross-gate
provenance defect behind a generic abort. See §1i: the row is now closed by auditing, not
wrapping.

## 1i. What changed in Rev. 10 — the Rev. 1/2 config-hash debt, closed by reading the code

Not a bug fix — the user's explicit answer to the open question §19 (Rev. 9) posed, plus the
actual reconciliation work Task 9's own docstring has required since Rev. 1/2 and Task 13's
Definition-of-Done item 8 was going to demand eventually regardless. Rejected: "same fix" (a
boundary wrap, matching NF5) and "leave as-is" (defer again). Chosen: read `resolve_coverage_
provenance` in full, since — unlike `gauntlet_runner` — it is same-repo, same-package code, and
auditing it produces stronger evidence than converting it ever could.

**What reading it proved, not assumed:** `resolve_coverage_provenance` (`coverage_runner.py:75-113`)
and `resolve_i8d_provenance` (`i8d_runner.py:157-202`) are structurally identical — same
`git_sha_and_dirty()` call, same dirty-tree refusal, the identical `effective_config_manifest(
agent=hero_agent, format_id=format_id, env=behavior_env(), model_hash=None,
model_manifest_hash=None)` call, the same `make_config_hash`. `format_id` defaults differ by name
(`COVERAGE_FORMAT` vs `I8D_FORMAT`) but not by value — both are `"gen9championsvgc2026regma"`
(`coverage_schedule.py:27`, `i8d_schedule.py:28`), the same value Gate B's own
`STRENGTH_HOLDOUT_FORMAT_ID` already uses. So `_derive_config_hash`'s reliance on
`resolve_coverage_provenance` is now PROVEN to produce the same `config_hash` I8-D's own
provenance function would, for the same `hero_agent`, same commit, same environment — not
"similarly shaped," identical by construction. A new offline test
(`test_derive_config_hash_and_i8d_provenance_build_the_identical_manifest_call`) proves the two
real functions call `effective_config_manifest` with identical arguments, without depending on
real git state or real config-file content at test-run time.

**What reading it also surfaced:** a real, DELIBERATE, DOCUMENTED fail-closed design from a
different, already-reviewed slice (I7a §14, §5.4 per `config_env.py`'s own docstrings) — a stale
itemdata/speciesdata generator hash or an unpinned calc/format config raises
`ItemdataStaleError`/`SpeciesMetaStaleError`/`PinnedCalcError`, and those are meant to propagate,
not be swallowed. `CoverageRunError` joins them for `resolve_coverage_provenance`'s own dirty-tree/
git/backend-env checks. `_derive_config_hash` now catches these four SPECIFIC types — never a
blanket `except Exception`, since that would flatten a genuine cross-gate config-drift defect into
the same undifferentiated `GateBAbort` as a routine dirty-tree stop, exactly the information-
destruction risk the user named. One narrow residual remains, disclosed rather than chased
further: `load_format_config`'s own malformed-YAML error path, one level past what this round
read in full (its `FileNotFoundError` case is already handled where it's raised).

**Effect on the exception-audit table (§1f, rebuilt again):** `resolve_coverage_provenance` moves
from "untraced, trust boundary, unknown" to "audited, `GateBAbort`, 4 named types" —
`run_strength_holdout_arm`'s trust-boundary count drops from one full row to one narrow,
single-function residual. Task 13's Definition-of-Done item 8 — closing this same debt — is
struck as already done, ahead of when the plan originally scheduled it.

**P3 addendum, same round, user-caught on independent re-verification:** the "provably identical"
claim above was only ever proven for `COVERAGE_FORMAT == I8D_FORMAT` — the new arg-equality test
pins that pair, but neither the test nor the actual call bound either to
`STRENGTH_HOLDOUT_FORMAT_ID`, the format Gate B's own schedule plays under. The real call never
passed `format_id`, so it silently inherited `resolve_coverage_provenance`'s own default rather
than Gate B's actual one. Inert today, since all three constants hold the same string — but the
failure direction if that ever changed would be silent, not loud: Gate B could play battles under
a NEW format while still deriving `candidate_identity` for the OLD one, and
`verify_i8d_verdict_artifact` would still PASS (Gate B's identity would still match I8-D's,
independently computed under the old format too) — a gate certifying it verified the same
candidate I8-D did while having actually played something else. Fixed the same way as the rest of
this round: `format_id=STRENGTH_HOLDOUT_FORMAT_ID` is now passed explicitly at the call site
(no longer inherited), and the arg-equality test gained a third assertion —
`calls[0]["format_id"] == STRENGTH_HOLDOUT_FORMAT_ID` — closing the triangle the original two-way
comparison left open. Not treated as a new revision: the user explicitly framed this as completing
the same proof, not a finding against already-shipped Rev. 10 content.

## 1j. What changed in Rev. 11 — panel_hash never entered schedule_hash

Not from a new Codex review round -- the user's own direct comparison of Task 1's shipped code
against `compute_schedule_hash`'s calls in the other five modules, made possible only once Task 1
existed as real, committed code to compare against, not just plan text. The bug was in this document's own
§4 code block, present since Rev. 1 and carried unchanged through ten revisions and the Task 1
implementation itself -- which correctly implemented what §4 specified.

| # | Finding | Verified against | Fixed in |
|---|---|---|---|
| U1 — user-found | `build_strength_holdout_schedule`'s `schedule_hash` hashed `keys`, `seed_base`, and `format_id` -- never `panel_hash`, despite receiving it as a required parameter and storing it on the returned `StrengthHoldoutSchedule`. Two schedules built from the same six team IDs but different panel content (different teams behind those IDs) collide on `schedule_hash`. Demonstrated directly, not just argued: a RED test with `panel_hash="a"*16` vs. `"b"*16` and identical team IDs produced the same `schedule_hash` value on both sides before the fix. | Read `eval/schedule.py:69`'s `compute_schedule_hash(version, rows)` in full and confirmed it hashes `version` -- a bare label string from the panel YAML, not a content hash -- plus each row's `hero_team_path`/`opp_team_path`, which are path STRINGS, not content. Read `panel.py` in full: `panel_hash` (`panel.py:126-131`) IS a genuine content hash -- it embeds every team's `team_hash`, itself a `.txt`+`.packed` content hash, per the module's own docstring (`panel.py:3-5`): "editing a team file without changing its path changes `panel_hash`." This means `compute_schedule_hash(version, rows)` -- called from the other five modules (eight production call sites total, recounted fresh: `coverage_schedule.py:179,232`, `i8d_schedule.py:114,181`, `panel_schedule.py:134,197`, `generalisation/planner.py:117`, `schedule.py:151`'s own loader) -- does NOT bind a full `panel_hash` either: a team file edited in place, same path, same version, would escape `compute_schedule_hash` in every one of those five modules too, not only in Gate B's original code. An earlier draft of this row claimed row-level paths "catch a same-path content change" -- that claim was backwards: a path string is invariant to content at that path by definition, so path-hashing cannot catch a content-only edit. Corrected here. Read `pairing.py:22-25`: `panel_hash` is independently one of the five `_CONSTANT_FIELDS` "that identify 'the same evaluation conditions'" -- confirming `schedule_hash` is expected to carry that identity, and hashing `panel_hash` directly achieves it more completely than the existing `compute_schedule_hash` pattern does anywhere else in this codebase. Structurally the same shape as P1-7 (§1a): a hash function with the right name and call site but a narrower actual scope than its role implies -- there, `.txt`-only instead of `.txt`+`.packed`; here, a version label plus paths instead of the real content hash. | This revision: `panel_hash` added to the hashed payload directly -- not to match `compute_schedule_hash`'s pattern, but because it is the more complete binding of the two. Comment records why `compute_schedule_hash` itself still isn't reused: the separate, structural reason that `BattleKey` carries `holdout_team_id`, not `hero_team_path`/`opp_team_path`, since team files don't exist before Task 13. New test `test_schedule_hash_changes_if_panel_hash_changes`; the nine original Task 1 tests are unchanged and still pass, since none of them vary `panel_hash` across two schedules being compared. |

**Why this couldn't wait:** from Task 9 on, `schedule_hash` is written into every battle row; from
Task 10 on, it's one of `pairing._CONSTANT_FIELDS` -- part of what "the same evaluation conditions"
means when pairing candidate and baseline rows for McNemar. Changing the hash formula after either
point would invalidate every row and frozen constant already produced under the old formula. Task
1 is the last point in the plan's own sequencing where this fix is free.

## 1k. What changed in Rev. 12 — allowlist prefix-matching and a repo-wide raw-content scan

Not from a new Codex review round -- two findings delivered directly by the user, verified against
this document's own Task 2 code block (the only place either bug could live, since Task 2 has not
been implemented as real code yet) before any fix, per this plan's own standing discipline of
checking a review claim against the actual text rather than trusting the finding's framing.

| # | Finding | Verified against | Fixed in |
|---|---|---|---|
| U2 — user-found, P1 | `_is_allowed`'s `path == prefix or path.startswith(prefix)` (§5, Step 3) applied `.startswith` to EVERY entry in `ALLOWED_PATH_PREFIXES` alike, including four single FILES (`panel_champions_strength_holdout_v0.yaml`, the manifest `.json`, the baseline `.json`, `heldout_ledger.jsonl`) that carry no trailing separator to stop a longer path from matching as a false "child". `"config/eval/heldout_ledger.jsonl.evil"`, `"config/eval/panels/panel_champions_strength_holdout_v0.yaml.backup"`, and `"config/eval/holdout/champions_strength_holdout_v0_manifest.json/copied"` all wrongly passed `_is_allowed` under the Rev. 11 text. | Reproduced the bug by hand against the literal Rev. 11 code block: `"...jsonl.evil".startswith("...jsonl")` is `True` in Python, and the same holds for the other two paths against their respective single-file entries. Separately confirmed the two DIRECTORY entries (`showdown_bot/teams/panel_champions_strength_holdout_v0/`, `data/eval/champions-panel-v0/strength-holdout-v0/`) were never vulnerable to this shape of bypass -- both already end in `/`, so `"...v0_evil/x".startswith("...v0/")` is `False` (the `/` itself breaks the match); the bug was specific to the single-file entries lacking that same trailing separator, not a property of prefix-matching in general. | `_is_allowed` now checks `ALLOWED_EXACT_PATHS` (`==` only) before falling back to `ALLOWED_DIRECTORY_PREFIXES` (`.startswith`, unchanged logic, now applied only to the four entries where it was always safe); paths are normalized to forward slashes first so a caller-supplied Windows-style path can't bypass or miss the allowlist on separator form alone (§5, Step 3) |
| U3 — user-found, P1 | The content-leakage scan (`scan_for_content_leakage` + `_all_tracked_team_content_hashes`, §5, Step 3, Rev. 10 and earlier) does not satisfy DESIGN sec 3.3's repo-wide contract for "packed/`.txt` content." It only ever iterates git-tracked files matching `showdown_bot/teams/*.txt`, silently skips (`except PanelError: continue`) any that lack a co-located `.packed` sibling, hashes the `.txt`+`.packed` PAIR as one combined digest (`panel.team_content_hash`), and flags a hit only when another file's OWN combined digest matches exactly. A `.txt` payload pasted into a report or test, a `.packed` payload pasted anywhere, a bare `.txt` copy with no `.packed` partner, or a payload embedded inside a larger tracked file all produce **no combined hash at all** for the leaking file (it either isn't under `showdown_bot/teams/`, isn't a whole-file `.txt`, or has no `.packed` partner to pair with) and are therefore structurally invisible to this scan, regardless of the allowlist fix above. Separately, `panel.team_content_hash` reads via `Path.read_text()` -- the working-copy filesystem, not the git object database -- so even a same-shaped comparison would be sensitive to this repo's global `core.autocrlf=true` translation on a Windows checkout, a channel neither leg of the old comparison defended against. | Re-read the Rev. 11 `_all_tracked_team_content_hashes`/`scan_for_content_leakage` code block line by line against DESIGN sec 3.3's own text ("a scan of git-tracked content for each holdout identifier (`team_hash`, `team_path`, `team_id`, packed/`.txt` content) must return zero hits outside the holdout's own operational artifacts... every *other* team file under `showdown_bot/teams/`... plus `reports/`, docs, tests, and tooling") -- confirmed each of the four gaps above is real and not merely hypothetical: the loop's own `if not path.startswith("showdown_bot/teams/") or not path.endswith(".txt"): continue` guard structurally excludes `reports/`, `docs/`, `tests/`, and tooling before any hashing happens. Re-read `panel.py::_team_content_hash` (`panel.py:51-59`): both files are opened via `.read_text(encoding="utf-8")`, confirming the CRLF-sensitivity claim against the real function, not by inference. | `scan_for_content_leakage`/`_all_tracked_team_content_hashes` removed; replaced by `scan_for_raw_payload_leakage(team_ids, *, cwd=".")` (§5, Step 3) -- for each sealed team_id, reads its `.txt` and `.packed` COMMITTED blob (`git show HEAD:<path>`, derived from the fixed `HOLDOUT_TEAMS_DIR` convention the allowlist already uses) as two separate search needles, then checks every OTHER git-tracked file's own COMMITTED blob bytes for either payload as a **substring** (not whole-file equality) -- catching a partial/embedded copy, requiring no `.packed` partner on the comparison side, and covering the full repo, not just `showdown_bot/teams/`. Reading committed blobs on BOTH sides of every comparison (needle and haystack alike) makes the result independent of working-copy line-ending state. Fails closed: an empty payload raises `ValueError` before any scan runs (`b"" in x` is trivially `True` in Python and would otherwise make the scan a silent no-op); a blob that cannot be read (missing path, not a git repo, `git` not on `PATH`) raises `LeakageScanError`, the same exception class `_git_tracked_files`/`_grep_identifier` already use for infra failures (§1g, NF4), not silently skipped and not conflated with `LeakageDriftError` (which means "scan ran, found a leak"). The existing combined `panel.team_content_hash` is **not** replaced -- it remains the correct tool for team identity and disjointness (Task 5's `assert_disjoint_from_coverage`, Task 9's `opp_team_hash` row-stamping), which legitimately want one hash per whole team; it was never the right tool for THIS scan specifically. |

**Downstream, checked against the new signature (`assert_no_holdout_leakage(*, identifiers, team_ids, teams_root=".")`, replacing `content_hashes`):**

- **Task 10** (§13): the only real production call site. `assert_no_holdout_leakage(identifiers=..., content_hashes=holdout_content_hashes, teams_root=teams_root)` becomes `assert_no_holdout_leakage(identifiers=..., team_ids=list(holdout_content_hashes.keys()), teams_root=teams_root)` -- `holdout_content_hashes` itself is unchanged (still required, still non-empty-checked, still feeds `assert_disjoint_from_coverage` for team identity, per U3's own "not replaced" note above); only what gets extracted from it for the leakage call changes. No new parameter was added to `combine_strength_holdout_arms` -- team IDs were already available as that dict's keys.
- **Task 11** (§14): checked, no change. Both CLI handlers unconditionally `raise GateBAbort(...)` today, pending Task 13 -- neither constructs a real call to `combine_strength_holdout_arms` or names `content_hashes`/`team_ids` anywhere in its current text, so there is no stale signature to fix here yet.
- **Task 12** (§15): checked, no change. `seal_team`/`SealedTeamRecord` compute and return the combined `team_content_hash` for provenance recording at seal time -- they were never a caller of the leakage guard and do not need to carry raw payload bytes: `scan_for_raw_payload_leakage` reads each sealed team's `.txt`/`.packed` payload itself, live, from its COMMITTED git blob at scan time (via `team_id` + `HOLDOUT_TEAMS_DIR`), which is more robust than threading a value captured once at seal time through two more task boundaries -- DESIGN sec 3.4 already guarantees the committed content cannot change after sealing ("After sealing they are not inspected, tuned against, or reshaped"), and by the time Task 10's `combine` step can run at all, Task 13's own definition-of-done (§16, item 7) already requires the sealed team files to be committed.
- **Task 13** (§16): definition-of-done item 6 updated from "both identifier and content-hash scans" to "both the identifier scan and the raw `.txt`/`.packed` payload scan," matching the new function names; no other item changes.
- **Tasks 3–9** (§6–§12): grepped the whole plan for every symbol this fix touches (`holdout_leakage_scan`, `assert_no_holdout_leakage`, `scan_for_content_leakage`, `LeakageDriftError`, `LeakageScanError`, `content_hashes`, `ALLOWED_PATH_PREFIXES`) -- no hits outside §1 (historical, unchanged on purpose), §1f (updated above), Task 2 itself, Task 10, Task 11, and Task 12/13. Task 9's similarly-named `holdout_team_content_hashes` parameter is a different thing entirely (per-row `opp_team_hash` provenance stamping, DESIGN sec 3.2/3.3's identity leg, not the leakage guard) and does not change.

## 1l. What changed in Rev. 13 — the Rev. 12 fix itself was bypassable and its own tests couldn't have run

Not a fresh Codex round on the whole plan -- a second review pass specifically on Rev. 12's own
P1 #1/P1 #2 fix, delivered directly by the user. Both original P1s were confirmed closed; two new,
execution-blocking gaps were found in how Rev. 12 wired the fix into Task 9/Task 10 and into its
own tests.

| # | Finding | Verified against | Fixed in |
|---|---|---|---|
| U4 — user-found, P1 | `assert_no_holdout_leakage`/`scan_for_raw_payload_leakage` accepted any `team_ids`, including an incomplete one. `combine_strength_holdout_arms` (§13) only ever checked `holdout_content_hashes` for non-emptiness, then passed `list(holdout_content_hashes.keys())` straight through -- a caller-supplied map covering one team instead of the real six would pass that check, and the guard would then silently scan for leakage of only that one team, the other five entirely unchecked. Nothing anywhere compared the map's keys against the schedule's actual team set. | Traced the real call path by hand against the literal Rev. 12 code: `if not holdout_content_hashes: raise GateBAbort(...)` is the only guard on that parameter; `team_ids=list(holdout_content_hashes.keys())` (§13's call site) accepts whatever keys happen to be present, one or six, with no cross-check against `build_strength_holdout_schedule`'s own 6-team requirement (Task 1) or against what the arms actually played. `scan_for_raw_payload_leakage` itself (§5) had no `team_ids` emptiness check either -- an empty list would make its own payload-collection loop a no-op, `payloads={}`, so every tracked file "passes" trivially. | Two layers, not one: (1) Task 9's arm manifest now records `holdout_team_ids` -- `sorted(scheduled_team_ids)`, already computed for the existing missing-hashes check, just also written out (§12). (2) Task 10 folds `holdout_team_ids` into the existing arm-vs-arm agreement loop (`schedule_hash`/`panel_hash`/`seed_base`) and adds a new, separate check requiring `set(manifest_a["holdout_team_ids"]) == set(holdout_content_hashes)` exactly -- missing, extra, or wrong team_ids abort with a named `GateBAbort` before any guard below runs (§13). (3) `scan_for_raw_payload_leakage` (§5) independently rejects an empty `team_ids` with `ValueError`, fail-closed, regardless of what any caller checks -- defense in depth, not a replacement for (2). |
| U5 — user-found, P1 | Task 10's own Rev. 12 GREEN tests could not have passed against the real `scan_for_raw_payload_leakage` (once Task 10 is actually implemented) -- every test reaching `assert_no_holdout_leakage` relied on the default `teams_root="."`, i.e. the real ambient worktree, which has no sealed holdout teams (Task 13 is still blocked) and certainly none at the fake `holdout_0`/`holdout_1` paths `_fake_holdout_hashes()` implied. The real scanner would call `git show HEAD:showdown_bot/teams/panel_champions_strength_holdout_v0/holdout_0.txt` against that worktree, get a nonzero exit (the path doesn't exist), and raise `LeakageScanError` -- uncaught by any of those tests' `pytest.raises(GateBAbort, ...)`/`pytest.raises(HoldoutNotDisjointError, ...)`/etc. assertions, well before whatever each test actually meant to exercise. | Confirmed `_fake_holdout_hashes()` (§13's Rev. 5-11 fixture) returned bare strings (`"aaaa1111bbbb2222"`), never anything computed from real file content, and that no test in Task 10's block passed `teams_root=` at all -- both facts read directly off the literal Rev. 12 test code. Cross-checked against `_read_git_blob`'s real behavior (§5): `git show HEAD:<path>` on a path absent from the tree exits non-zero under `check=True`, which is exactly the `LeakageScanError` path. | Added `_write_holdout_teams_repo(tmp_path)` (§13): a real, isolated, per-test git repo (fresh `tmp_path`-scoped, so no cross-test leakage) seeded with six committed `.txt`+`.packed` team files at the real `HOLDOUT_TEAMS_DIR` convention, returning `(teams_root, holdout_content_hashes)` with the LATTER computed via the real `panel.team_content_hash`, not a fake string. Every test that genuinely reaches the leakage scan (9 of the pre-existing tests, plus both new team-set-mismatch tests -- the mismatch tests abort *before* the scan, so they don't need it) now uses this fixture's `teams_root=`/`holdout_content_hashes=`; the 10 tests that abort earlier (an i8d/coverage-path guard, an arm-read/manifest-schema guard, an arm-role/git_sha mismatch) correctly keep the cheaper `_fake_holdout_hashes()`, since the guard never runs for them either way -- disclosed here, not left to look like an oversight. `assert_no_holdout_leakage` is not mocked away anywhere in this plan; every test that reaches it runs the real function against real committed content, per DESIGN's own testing discipline (§17.3's standing check: prove trust, don't assume it). |

**Downstream, re-checked:** Task 11 (§14) still constructs no real call to `combine_strength_holdout_arms` -- unaffected, no change. Task 12 (§15) still only computes the combined `team_content_hash` for provenance, never calls the leakage guard -- unaffected, no change; its own Rev. 12 note (verified, no change needed) still holds. Task 13 (§16) item 6's wording (Rev. 12) already described "the raw `.txt`/`.packed` payload scan" generically enough that it needed no further edit for this round -- the team-set cross-check is a Task 9/Task 10 concern, not a Task 13 definition-of-done wording issue.

## 1m. What changed in Rev. 14 — a manifest's team claim was never bound to its own rows

A third review round, this time explicitly from Codex (not the user directly, unlike §1k/§1l).
Verified against the literal Rev. 13 text before any fix, per this plan's own standing
discipline.

| # | Finding | Verified against | Fixed in |
|---|---|---|---|
| P1 (Rev. 14) | `holdout_team_ids` (Rev. 13) was a bare list the arm manifest CLAIMED -- `_assert_rows_match_manifest` (§13) checked it only for PRESENCE (`_MANIFEST_REQUIRED_KEYS`), never for agreement with what `rows` actually contain. Nothing bound a row's own `opp_team_path`/`opp_team_hash` to the manifest's declared team set. Both arms' manifests, and the caller-supplied `holdout_content_hashes`, could therefore all assert the identical six WRONG team identities -- passing every Rev. 13 check (arm-vs-arm agreement, key-set equality against the hash map) -- while `rows.jsonl` actually recorded battles against entirely different opponents. The leakage/disjointness guards would then scan for the six ASSERTED teams, never the six REAL ones, defeating DESIGN sec 3.3's repo-wide contamination check at its root. | Re-read `_assert_rows_match_manifest` (§13) and `_ROW_REQUIRED_KEYS_FOR_MANIFEST_CHECK` line by line against the literal Rev. 13 code: `holdout_team_ids` was in `_MANIFEST_REQUIRED_KEYS` (presence-checked) but absent from `_ROW_REQUIRED_KEYS_FOR_MANIFEST_CHECK` (the only content-match loop that function had) -- confirmed structurally impossible for that loop to have caught a manifest/row disagreement about team identity even if someone had added the field to it, since that loop compares a row field against exactly ONE manifest-wide scalar, and `opp_team_path`/`opp_team_hash` legitimately vary per row (one of six teams each). Re-read Task 9's `_capture` closure (§12): `opp_team_path`/`opp_team_hash` ARE the real per-battle ground truth, stamped from `key.holdout_team_id` and `holdout_team_content_hashes[key.holdout_team_id]` -- exactly the data a manifest claim needs to be checked against, and never was. | Replaced the bare list with a canonical mapping, `holdout_teams: {team_id: {"team_path": str, "content_hash": str}}` (§12, Task 9) -- derived ONLY from the real scheduled `schedule.battle_keys`, the canonical `HOLDOUT_TEAMS_DIR` path convention (now a single shared constant, no longer hardcoded twice), and `holdout_team_content_hashes[team_id]`. `_assert_rows_match_manifest` (§13) now runs two new checks, both before the pre-existing scalar loop: `_validate_holdout_teams_mapping` (closed shape -- object/mapping, exactly six entries, non-empty string keys/fields, no unknown fields, canonical `team_path` per `team_id`) and `_assert_rows_bind_to_holdout_teams` (every row's `opp_team_path` must be one of the declared six, `opp_team_hash` must equal that team's declared `content_hash`, and all six declared teams must actually appear in the rows at least once). The arm-vs-arm loop now compares `holdout_teams` (structural equality, dict-vs-dict); the cross-check against `holdout_content_hashes` is now full dict equality (keys AND values, catching a right-key/wrong-hash caller map that Rev. 13's key-set-only check would have missed); and the leakage guard's `team_ids=` argument is sourced from the validated, row-bound `manifest_a["holdout_teams"]`, not from the caller-supplied map directly. Eight new RED tests (§13) cover: both manifests claiming the same wrong teams while rows stay real; a correct team_id with a wrong `content_hash`; a correct team_id with a non-canonical `team_path`; one corrupted row with an unknown `opp_team_path`; a declared team that never appears in any row; all four malformed `holdout_teams` shapes (null/string/array/unknown-field) in one parametrized test; a caller `holdout_content_hashes` with the right keys but a wrong value; and the full six-real-team success path (the pre-existing Rev. 13 test, now also exercising every new check for real). |
| P2 (Rev. 14) | The prose paragraph directly below Task 10's RED test block (§13) claimed guard inputs were legitimately "empty (if empty)" in tests and that every guard "actually run[s] ... in every test above, for real" -- both stale relative to what Rev. 13/14's own test suite actually does: empty inputs are rejected everywhere (Rev. 13 already made this unconditional), and only the tests that structurally reach `assert_no_holdout_leakage` exercise it for real; the ten early-abort tests deliberately use cheap, non-git-backed fixture data precisely because the guard never runs for them. | Re-read the paragraph against the actual Rev. 13 test bodies: no test passes `{}` or any other empty value for `holdout_content_hashes`/`reference_species` (confirmed by grep); `_write_holdout_teams_repo` (real git-backed) is used by exactly the tests that reach the guard, `_fake_holdout_hashes()` by the rest -- the paragraph described neither fact accurately. | Rewritten (§13, directly below the RED test block) to state the real Rev. 13/14 split: no empty inputs anywhere; early-abort tests use cheap fake data because the guard never runs for them, disclosed as deliberate rather than implied to be "real" coverage; every test that reaches the guard uses real committed `.txt`/`.packed` fixtures via `_write_holdout_teams_repo` and the real scanner, never a mock. |

**Notable side effect, disclosed:** `test_combine_wraps_a_non_missing_pair_error_too` (§13) previously
used `n=2` and corrupted `rows.jsonl` by replacing its entire content with two copies of row 0 --
under the new "all six declared teams must appear in rows" check, that would have left five of
six teams with zero rows, aborting at the NEW check instead of reaching `pair_runs` as the test
intends. Fixed by moving to `n=12` (cycling all six teams twice each, matching the pattern every
other test already uses) and a surgical corruption: row 6 (already, by construction, the SAME
team as row 0) is overwritten to be byte-identical to row 0, creating the intended
`(battle_id, config_hash)` duplicate without removing any team's representation. Not a new
finding -- a consequence of P1's fix that would otherwise have silently broken this test's own
intent.

**Downstream, re-checked:** Task 11 (§14) and Task 12 (§15) -- unaffected, no change, same
reasoning as §1l (neither constructs a real `combine_strength_holdout_arms` call or reads
`holdout_teams`/`holdout_team_ids` in its current text). Task 13 (§16) -- unaffected; item 6's
wording already covers "the raw `.txt`/`.packed` payload scan" generically. Task 9's OWN test
suite (§12) needed no changes -- confirmed no test there inspects the manifest's exact key or
value shape (grepped for `manifest.keys()`/`set(manifest)`/exact-dict assertions; none found
outside `_assert_rows_match_manifest`'s own, now-extended, presence check).

## 1n. What changed in Rev. 15 — Task 3's stratum guard, built correctly, was never wired in

Not a fresh full-plan round: a "Task-3-review," scoped explicitly to Task 3 and its two
integration points (Task 9, Task 10), delivered as six binding-correction bullets in one message
("Bindende Korrektur in einer einzigen Rev. 15... keine weiteren Stilrunden"). Verified against
the literal Rev. 14 text before any fix: read Task 3 (§6) in full end to end, then grepped the
whole document for `stratum_output_root|StratumRecord\(|detect_stratum\(|platform_string` to find
every call site outside Task 3's own tests/implementation.

| # | Finding | Verified against | Fixed in |
|---|---|---|---|
| P1 (Rev. 15) | Task 9 never wrote any stratum information into the arm manifest at all -- no `stratum`, no platform attestation, no date/stratum identifier. Task 10's `combine_strength_holdout_arms` then called `detect_stratum(env_override=stratum_env_override)` ITSELF, once, and built BOTH arms' `StratumRecord`s from that single self-detected value, with `platform_string=""` hardcoded on both. Two arms genuinely played on different strata (e.g. one on the fixed Windows host, one on a Kaggle session -- DESIGN sec 3.5's own scenario) would always look identical to `assert_no_cross_stratum_pooling`, because the combiner never looked at either arm's actual play-time evidence -- it only ever asked its OWN machine, once, and copied the answer twice. | Read Task 9's full implementation (§12) end to end: no `import platform`, no `strata_guard` import, no stratum field anywhere in the `arm_manifest.json` write. Read Task 10's full implementation (§13): the grep above found exactly one `detect_stratum(` call site outside Task 3 itself, at the stratum-pooling block near the end of `combine_strength_holdout_arms`, feeding both `StratumRecord`s from the same local variable. | Task 9 (§12) now calls `detect_stratum(env_override=stratum_env_override)` and `platform.platform()` once, near the top (a new `stratum_env_override` parameter, and a required `date_stratum_id` parameter with no default -- DESIGN sec 3.5: "a Kaggle strength stratum is a separate pre-registered run," so this identifier must come from the caller, never be derived from wall-clock time), and records `stratum`/`platform_attestation`/`date_stratum_id` in the arm manifest. Task 10 (§13) no longer calls `detect_stratum()` at all -- it reads `manifest_a["stratum"]`/`manifest_b["stratum"]`/`manifest_a["platform_attestation"]`/`manifest_b["platform_attestation"]`, already proven present and well-formed by `_validate_stratum_fields`, and builds the two `StratumRecord`s from those, comparing the two ACTUAL arm records instead of one self-detected value. `date_stratum_id` is added to the pre-existing arm-vs-arm equality loop (`schedule_hash`/`panel_hash`/`seed_base`/`holdout_teams`), so two arms with the same stratum but different pre-registered runs still abort. `stratum_env_override` is repurposed: no longer fed into `detect_stratum`, it is now an optional caller expectation checked against `manifest_a["stratum"]`, aborting as a "contradictory override" on mismatch. |
| P1 (Rev. 15) | `stratum_output_root()` (Task 3, §6) was called nowhere in the entire plan outside its own two unit tests (`test_stratum_output_root_separates_strata`/`test_stratum_output_root_rejects_unknown_stratum`) -- confirmed dead code in every real code path. Nothing bound an arm's `out_dir` to the stratum it was actually played under, so two strata's arms could be published to the same or an arbitrarily-named directory with nothing to catch it. | The `stratum_output_root\|StratumRecord\(\|detect_stratum\(\|platform_string` grep across the whole document returned zero hits for `stratum_output_root(` outside §6's own test block and implementation -- confirmed by reading every match. | Task 9 (§12) now computes `expected_root = stratum_output_root(stratum, STRENGTH_HOLDOUT_OUTPUT_BASE)` (a new module constant, `"data/eval/champions-panel-v0/strength-holdout-v0"` -- matches `holdout_leakage_scan.ALLOWED_DIRECTORY_PREFIXES`'s existing entry for this tree exactly, so no allowlist change is needed) and aborts with `GateBAbort` if the caller-supplied `out_dir` is not that root or a path under it, before `staging_dir`/`os.makedirs` run. This binds `stratum_output_root` into the real arm-publish path per the review's own "used... or bindingly validated there" wording -- the validated-caller-supplied-`out_dir` form, not the derive-it-internally form, since `out_dir`'s existing meaning as a full caller-supplied path (already relied on by Task 11's future CLI wiring) is unchanged. |

**Required tests, confirmed present:** `test_combine_rejects_mixed_windows_and_kaggle_arms` (reject
Windows+Kaggle), `test_combine_accepts_two_equally_attested_arms` (accept two equally-attested
arms), `test_combine_rejects_a_contradictory_stratum_override` (reject contradictory overrides) --
the three scenarios named explicitly in the review -- plus
`test_combine_aborts_if_arms_disagree_on_date_stratum_id` (same stratum, different date-stratum,
still aborts -- the other half of "different strata or date-strata must abort"),
`test_combine_aborts_on_an_unknown_stratum_value` and
`test_combine_aborts_on_a_type_wrong_platform_attestation` (closed-form validation: "missing,
unknown, or type-wrong manifest values must abort" -- missing is covered by the pre-existing
generic `_MANIFEST_REQUIRED_KEYS` presence-check test, itself unchanged, now also proving the
mechanism for these three new keys by construction).

**Self-found while fixing the two P1s above, same pass, not named in the review itself:** Task 9's
new `detect_stratum(env_override=stratum_env_override)` call makes `UnattestedStratumError`
(no override supplied, non-Windows platform -- DESIGN sec 3.5's own core Kaggle scenario) newly
reachable from `run_strength_holdout_arm`'s call graph. The arm CLI's exception-audit table (§12)
and its `except GateBAbort` handler (§14) both carried an explicit, load-bearing claim that this
function's entire exception surface resolves to `GateBAbort` -- true before this round, false the
moment `detect_stratum()` was added. Fixed in the same pass: the audit table gained two new rows
(`UnattestedStratumError`, deliberately raw, matching Task 10's own established treatment of the
identical exception type; `ValueError` on a malformed override, disclosed but not caught, expected
to be argparse-guarded once a real `--stratum-override` flag exists), and `run_strength_holdout_arm_cli`'s
except clause widened to `(GateBAbort, UnattestedStratumError)` with its comment corrected to stop
claiming the handler "does not need widening." Exactly the same shape as Rev. 8/9's own NF3-NF5
findings (a fix introducing a new raw exception path, caught by re-auditing the boundary in the
same round rather than leaving the stale claim to mislead the next reader) -- disclosed here for
that same reason, not silently folded into the two P1s' own cells above.

**Side finding, deliberately not folded in (per explicit instruction):** the review's own message
separately flagged `showdown_bot/uv.lock` as untracked in this worktree. Investigated read-only,
reported to the user alongside this round, not treated as part of Task 3's scope, and no action
taken on the file itself.

**Downstream, re-checked:** Task 11 (§14) -- the arm CLI handler DOES change (self-found finding,
above): its except clause and comment, corrected in this same round. Its combine CLI handler
(`run_strength_holdout_combine_cli`/`_describe_strength_holdout_combine_error`) needed no change
-- it already catches `StrataPoolingError`/`UnattestedStratumError` in its existing four-guards
tuple (Rev. 8, NF4), which now simply carries real per-arm data instead of a self-detected value;
both CLI handlers still unconditionally `raise GateBAbort(...)` pending Task 13 and construct no
real call to either runner function otherwise. Task 12 (§15) -- unaffected, no change; still only
computes the combined `team_content_hash` for provenance, never touches stratum. Task 13 (§16) --
unaffected; its wording names no stratum-related field. "## 3.
File structure" -- unaffected; `strength_holdout_runner.py`'s existing description ("per-arm
execution + combine/guards/publish") already covers this change without edit.

## 1o. What changed in Rev. 16 — two mechanical gaps in Rev. 15's own fix

A direct, mechanical follow-up review on Rev. 15's own text (not a fresh full-plan round): "Rev.
15 schließt die ursprüngliche Arm→Manifest→Combine-Lücke korrekt. Zwei mechanische P1-Reste
bleiben jedoch." Both confirmed against the literal Rev. 15 code before any fix -- the first by
re-reading `detect_stratum`'s body (Task 3, §6) end to end; the second by hand-tracing what
`out_dir` actually looks like at Task 9's own test call sites (`_arm_out_dir`, §12) against what
the new check compared it to.

| # | Finding | Verified against | Fixed in |
|---|---|---|---|
| P1 (Rev. 16) | `detect_stratum`'s `env_override` bypassed `platform.system()` entirely: `if env_override is not None: ... return env_override` -- no check of any kind against what the platform actually is. Before Rev. 15 this was inert (nothing downstream trusted the result for anything consequential). Rev. 15 made it load-bearing: Task 9 now writes `detect_stratum`'s return value into the arm manifest as the authoritative `stratum` field, and Task 10 trusts that field completely, never re-deriving it. `env_override="kaggle"` passed on the real, fixed Windows measurement host (or `env_override="windows"` passed on a non-Windows box) would therefore now succeed silently and get recorded as fact -- a spoofed label with real downstream consequences: DESIGN sec 3.5's whole point (Kaggle's CPU is not reproducibly comparable to the fixed Windows host) depends on the recorded stratum being true, not merely claimed. | Read `detect_stratum`'s full body (§6) line by line: the `if env_override is not None:` branch only ever validated membership in `VALID_STRATA`, never compared against `platform.system()`. Confirmed the two spoofing directions both reach `return env_override` unobstructed on the literal Rev. 15 code. | `detect_stratum` (§6) now computes `is_windows = platform.system() == "Windows"` once, and rejects (`UnattestedStratumError`, reusing the existing type rather than adding a new one -- the semantic fit is exact: an override contradicting reality is not a valid attestation) `env_override="kaggle"` when `is_windows` is true, and `env_override="windows"` when it is false. Consistent combinations (`"windows"` on Windows, `"kaggle"` on non-Windows) are unaffected. `test_detect_stratum_respects_explicit_override` (which asserted both calls succeeded using the REAL ambient platform, no monkeypatch) is replaced by two tests: one confirming both consistent combinations under explicit `monkeypatch.setattr("platform.system", ...)`, one confirming both contradiction directions are rejected. Net test count: 8 -> 9. |
| P1 (Rev. 16) | Task 9's new out_dir validation (Rev. 15) compared `out_dir` against `expected_root` with `out_dir != expected_root and not out_dir.startswith(expected_root + "/")`. `expected_root` (`stratum_output_root`'s return value) is always a bare, forward-slash, repo-root-relative string with no absolute prefix. Every `out_dir` the plan's OWN tests construct (via `_arm_out_dir`, built from pytest's `tmp_path` fixture -- an absolute, OS-native-separator directory, exactly like every other test in this file already uses to get a real, writable location) therefore NEVER matches: on Windows, `str(tmp_path / "data/eval/.../windows" / "arm_a")` renders with backslashes and an absolute drive-letter prefix, which can satisfy neither `==` nor `.startswith()` against the bare relative `expected_root`. The check would reject every one of Task 9's own passing tests, not just a genuine mistake. | Hand-traced `_arm_out_dir`'s actual return value (§12: `tmp_path / stratum_output_root(stratum, STRENGTH_HOLDOUT_OUTPUT_BASE) / name`, an absolute `WindowsPath`) against `run_strength_holdout_arm`'s literal Rev. 15 comparison -- confirmed the two can never satisfy either branch of the `if` on this OS, by construction. | Replaced the direct comparison with a separator-normalized, slash-bounded substring check (§12): `out_dir.replace("\\", "/")`, then test that `f"/{expected_root}/"` appears in `f"/{normalized_out_dir}/"`. Handles the relative-path production shape (root as a literal prefix) and the absolute-tmp_path test shape (root as a middle segment) identically, without requiring `out_dir` to be one specific form -- the same normalize-before-compare technique Task 2's `_normalize_path` (§5) already established for the identical class of bug (a caller-supplied Windows-style path defeating a string-based path check). No test-fixture change needed -- `_arm_out_dir` was already correct; only the comparison it fed was wrong. |

**Downstream, re-checked:** Neither fix touches a manifest field, a function signature, or a
call site outside the two cells above -- `_MANIFEST_REQUIRED_KEYS`, the arm-vs-arm loop,
`_validate_stratum_fields`, the six Rev. 15 tests, and every CLI/exception-audit change from §1n
are all unaffected, no change. Task 9's own tests (§12) needed no change: every one already
passes `stratum_env_override="windows"` under the real, unpatched ambient platform (this dev/CI
box is genuinely Windows), which is consistent under the new `detect_stratum` check exactly as it
was under the old one.

## 1p. What changed in Rev. 17 — a code review on Task 3's real implementation, live-reproduced

A focused CODE review (not a plan round) on the just-committed `strata_guard.py`/
`test_strata_guard.py` (`3f07ef3`), plus one more plan-text gap in Task 9's own Rev. 16 fix found
in the same pass. Two of the three findings were **live-reproduced** against the real module, not
merely read -- confirmed by re-tracing `detect_stratum`/`assert_no_cross_stratum_pooling`'s actual
bodies line by line and by standalone-executing the exact scenarios before touching anything.

| # | Finding | Verified against | Fixed in |
|---|---|---|---|
| P1 (Rev. 17) | `detect_stratum`'s Rev. 16 override-consistency check used a single boolean, `is_windows = platform.system() == "Windows"`, and only ever tested `env_override == KAGGLE_STRATUM and is_windows` / `env_override == WINDOWS_STRATUM and not is_windows`. This collapses every non-Windows platform into one bucket -- Darwin (macOS) is `not is_windows`, exactly like Linux, so `env_override="kaggle"` on a Mac laptop passed both checks unobstructed and returned `"kaggle"`. This reintroduces P2-1's own original failure mode ("a bare non-Windows box is NOT assumed to be the approved Kaggle environment -- it could be any unattested machine") through the override path specifically -- the no-override branch still correctly refuses to guess, but the override branch, added in Rev. 16, never carried the same discipline forward for the Kaggle direction. | Read `detect_stratum`'s literal body (real file, not the plan) line by line; confirmed `is_windows` is a boolean with no memory of WHICH non-Windows platform it came from. Live-reproduced: called `detect_stratum(env_override="kaggle")` with `platform.system` monkeypatched to return `"Darwin"` -- returned `"kaggle"`, no exception, against the actual Rev. 16 code before any fix. | `detect_stratum` (real file) now checks `env_override == KAGGLE_STRATUM and system != "Linux"` (was `and is_windows`) -- Kaggle's actual documented environment is Linux, so the override must match THAT specifically, not merely differ from Windows. The Windows-direction check (`env_override == WINDOWS_STRATUM and system != "Windows"`) is unchanged and was never wrong. New test `test_detect_stratum_rejects_a_kaggle_override_on_a_non_linux_platform` (monkeypatches `Darwin`) proves the fix; written RED first, confirmed it failed with `DID NOT RAISE` against the pre-fix code, then made to pass. Net test count: 9 -> 11 (this row + the next). |
| P1 (Rev. 17) | `assert_no_cross_stratum_pooling` computed `strata = {r.stratum for r in records}` and only ever checked `len(strata) > 1` -- it never checked that any individual `r.stratum` is a member of `VALID_STRATA`. Two records that AGREE with each other but share an unrecognized value (e.g. a corrupted or hand-edited `"colab"`) produce `strata = {"colab"}`, `len(strata) == 1`, and the function returns normally -- an inconsistency within Task 3's own module, since its sibling functions `detect_stratum` and `stratum_output_root` both already validate against `VALID_STRATA` and this one alone did not. | Read the function's literal body; confirmed the membership check exists nowhere in it. Live-reproduced: called `assert_no_cross_stratum_pooling` with two `StratumRecord`s both carrying `stratum="colab"` -- returned `None` (no exception) against the actual Rev. 16 code before any fix. | Added a membership check (`r.stratum not in VALID_STRATA` for every record, `ValueError` on the first offender -- matching `stratum_output_root`'s own "unknown stratum" `ValueError` convention, kept distinct from `StrataPoolingError` (genuine cross-stratum disagreement) and `UnattestedStratumError` (`detect_stratum`'s own could-not-attest case)) before the existing agreement check. Defense in depth, independent of whatever an upstream caller (Task 10's `_validate_stratum_fields`) may or may not already have validated -- the same principle `scan_for_raw_payload_leakage`'s own empty-`team_ids` check already applies (Task 2, §5). New test `test_assert_no_cross_stratum_pooling_rejects_records_with_an_unknown_stratum`; written RED first, confirmed `DID NOT RAISE` against the pre-fix code. |
| P1 (Rev. 17) | Task 9's Rev. 16 out_dir fix (§12) normalized separators (`out_dir.replace("\\", "/")`) but never collapsed `.`/`..` path segments before the slash-bounded substring containment check. `out_dir=f"{expected_root}/../../../elsewhere"` still contains `expected_root` as a literal SUBSTRING even though it resolves somewhere else entirely once the OS actually processes the `..` segments (`os.makedirs`, `open`, etc. all resolve them) -- defeating the exact invariant this check exists to enforce (DESIGN sec 3.5: each stratum publishes under its own separate tree). A string-substring check operating on unresolved text is not the same claim as "this path is under that root." | Re-read the Rev. 16 comparison line by line against what `posixpath`/`os.path` actually do with `.`/`..` segments -- confirmed `.replace("\\", "/")` is a pure character substitution, it does not interpret path semantics at all. Verified standalone (not just by inspection): ran the exact traversal payload, both forward-slash and backslash forms, through the literal pre-fix comparison logic in an isolated script -- both wrongly returned "accepted." | Replaced `out_dir.replace("\\", "/")` with `posixpath.normpath(out_dir.replace("\\", "/"))` before the containment check (§12) -- `posixpath.normpath` collapses `.`/`..` lexically (no filesystem access, no dependence on `out_dir` existing yet, which it doesn't at this point in the function) using forward-slash semantics regardless of host OS. Re-verified standalone against 7 cases (the 5 already covered in §1o's own record, plus both traversal payloads) -- all 7 now behave correctly, including both traversal payloads now correctly rejected. `posixpath` added to the module's import list. |

**Downstream, re-checked:** No test-fixture change needed anywhere -- `_arm_out_dir` (§12) and
every existing `strata_guard` test that predates this round pass unchanged (11 total now, up from
9; re-run in full, not just the two new ones). Task 10 (§13) is untouched: it never calls
`detect_stratum` or `assert_no_cross_stratum_pooling` directly with anything but
already-manifest-validated data, so neither fix changes its behavior. The CLI exception-audit
tables and widened except-tuples from §1n are unaffected -- `UnattestedStratumError` and
`ValueError` were already accounted for there; this round changes WHEN they fire, not whether
they are caught.

## 1q. What changed in Rev. 18 — Task 4 made agent-executable (not a review round)

A "begrenzte Task-4-Planprüfung": Task 4 (§7) plus its mandatory interfaces to Task 10 (§13) and
Task 13 (§16). Not a review round in the §1a-§1p sense -- there was no prior REAL text to find
findings against, only a stub claiming to defer to code that turned out not to exist.

**1. "Rev. 1 code" verified absent, not assumed absent.** Before writing anything, searched
read-only: `git log --all --oneline -S "find_near_duplicate_flags"` (one hit, the commit that
first introduced this whole plan document, already carrying the same stub);
`git log --all --oneline --diff-filter=A -- "**/near_duplicate.py" "**/test_near_duplicate.py"`
(zero hits, ever, in this repository); `git log --follow` on this document itself (8 commits
total, none before that first one). No reviewer ever had a real, committed artifact to review.
Documented in §7's own opening paragraph rather than silently assumed and reconstructed.

**2. Task 4 designed fresh from DESIGN sec 3.3 and this codebase's existing conventions (§7).**
Species-ID normalization reuses this codebase's own already-quadruplicated `to_id` rule
(`engine.state`/`engine.items`/`engine.moves`/`battle.opponent.SpeciesDex`) rather than inventing
a new one -- lowercase, strip non-alphanumeric, no forme merging. Overlap formula bound to
Jaccard similarity (`|A∩B|/|A∪B|`), not the overlap coefficient (`|A∩B|/min(|A|,|B|)`) -- at a
0.5 threshold the two formulas disagree sharply for 6-species teams (4-of-6 shared vs. 3-of-6),
and DESIGN's own "near-duplicate," not "somewhat similar," language calls for the stricter one.
Threshold is inclusive (`>=`) -- a diagnostic-only flag should show borderline cases to a human,
not silently hide them. Self-comparison excluded inside `find_near_duplicate_flags` itself
(defense in depth), flags sorted by `reference_team_id` for determinism, every failure mode
(empty species list, empty reference mapping, empty candidate id) fails closed with `ValueError`,
and finding a duplicate is always a normal return, never a raised exception -- 13 tests cover all
of this explicitly, including a dedicated test that a found duplicate never raises.

**3. Task 10's call site had exactly the bug this round's Auftrag anticipated (§13).** The
pre-existing loop, `for team_id, species in reference_species.items():
find_near_duplicate_flags(candidate_team_id=team_id, candidate_species=species,
reference_teams=reference_species)`, used ONE dict as both the six holdout candidates AND the
reference set to compare them against -- every team was compared against a reference set that
included itself (only `find_near_duplicate_flags`'s own self-exclusion, added fresh in this same
round, would have prevented a trivial 1.0 self-match), and there was no parameter carrying the
six holdout teams' own species at all. Fixed with a new required parameter,
`holdout_candidate_species: dict[str, list[str]]`, genuinely separate from `reference_species`
(unchanged meaning: the nine existing Champions-M-A teams). `holdout_candidate_species`'s key set
is checked against `manifest_a["holdout_teams"]` exactly like `holdout_content_hashes` already
is, closing the same "caller assertion never bound to the real six teams" gap class this plan has
now closed three times (Rev. 14's `holdout_teams`, Rev. 15's stratum, this). Threaded through all
36 existing `combine_strength_holdout_arms` test call sites via a new `_fake_holdout_candidate_species()`
fixture (keyed by the same six `_six_teams()` ids `_write_arm`'s own default `holdout_teams`
already uses, so no other fixture needed changing) plus one test-specific fix
(`test_combine_rejects_empty_reference_species` needed the new kwarg added by hand -- it passes
`reference_species={}` literally, not via the fixture function, so it did not match the blanket
substitution). Four new tests: publishes a guaranteed flag without aborting or gating the
verdict; rejects a `holdout_candidate_species` naming the wrong team_ids; rejects an empty
`holdout_candidate_species`; rejects malformed (empty-list) species data cleanly.

**4. Self-found in the same pass: a new raw `ValueError` path.** The key-set check proves
`holdout_candidate_species`/`reference_species` name the right team_ids; it does not prove each
team's OWN species list is non-empty. An empty list for either side would have made
`find_near_duplicate_flags` raise `ValueError`, unwrapped, escaping `combine_strength_holdout_arms`
uncaught by the CLI (Task 11, which only ever catches `GateBAbort`) -- the identical shape NF1/
NF3 fixed for `_assert_rows_match_manifest`/`BattleResultWriter.write` in earlier rounds, caught
here on introduction rather than left for a later round to find. Wrapped as `GateBAbort`; new
exception-audit-table row (§13); new test
(`test_combine_aborts_cleanly_on_malformed_species_data_not_a_raw_valueerror`).

**5. Task 13's "nine existing Champions-M-A teams" (§16 item 5) traced to a concrete list.** The
real on-disk `gen9championsvgc2026regma` team set is 10 files, not nine -- one shared hero
(`showdown_bot/teams/fixed_champions_v0.txt`) plus nine opponent-side teams across two panels
(`config/eval/panels/panel_champions_v0.yaml`: 5; `config/eval/panels/panel_champions_coverage_v0.yaml`:
4). "Nine" reconciles exactly once the shared hero is excluded -- consistent with DESIGN sec
3.3's "touched or coverage TEAM" meaning an opponent already tested against, not the bot's own
fixed hero (which would trivially "overlap" with every future candidate via the hero side of any
comparison, which is not what this check exists to catch). Task 13 itself remains blocked on the
source-proof (§2) regardless; this only makes the "nine" number traceable for whoever eventually
implements it, rather than a number nobody could reconstruct.

**Downstream, re-checked:** Task 11 (§14) -- unaffected; its combine CLI stub still unconditionally
`raise`s `GateBAbort` before ever reaching a real `combine_strength_holdout_arms` call, so the new
required parameter has no stale call site to update there yet. Task 12 (§15) -- unaffected; it
never touches species data. `uv.lock` -- confirmed untracked and untouched throughout this round,
per explicit instruction.

## 1s. What changed in Rev. 20 — mechanical sync of Task 10 with its committed implementation

Not a review round and not a design change: as of Rev. 20, Tasks 1–10 were implemented and committed
on this branch (nothing is merged to `main`),
and Task 10's embedded code here had fallen behind the two review-fix commits that landed after
it. This revision replaces §13's test and implementation blocks verbatim with the final committed
source as of `53e6c9c` and updates that task's RED/GREEN/commit records to what was executed.

**Housekeeping note:** Rev. 19's header bullet referenced a `§1r` that was never actually written
— its content exists only in that header bullet. Recorded here rather than silently renumbering,
since the header's own cross-reference is what a later reader would chase.

| Round | Finding | Closed by |
| --- | --- | --- |
| P1 | Two arms that agreed with each other and with their own manifests, but carried only 12 of the canonical 180 battle keys, combined to a published verdict. Nothing ever rebuilt the schedule; `n_rows == len(rows)` and row-vs-manifest `schedule_hash` are both self-consistency checks a truncated arm satisfies trivially. The fixtures meant to prove otherwise were themselves 12-row. | `_assert_rows_cover_canonical_schedule`: rebuilds from the arm's own team_ids/panel_hash/seed_base, checks `seed_base` separately against the pinned namespace (feeding a forged one into the rebuild would be vacuous), compares `schedule_hash`, key count, and the exact played grid. Fixtures now emit real 180-key arms. |
| P1 | `verify_baseline` reads the working tree and the leakage scan reads committed blobs via `git show HEAD:<path>`, but the bundle was stamped with the arms' `git_sha` — a dirty tree or a different checkout evaluated one commit and labelled it another. | Dirty-tree refusal plus `HEAD == manifest git_sha`, before every repo-dependent guard. `_git_is_dirty`/`_git_sha` gained `cwd` so they interrogate the checkout those guards actually read. |
| P1 | `holdout_candidate_species`/`reference_species` were caller assertions; only the candidate key set was checked, never that any species belonged to the team it was filed under. `near_duplicate.load_team_species` existed and was tested but had no production call site at all. | Both parameters removed. Candidates derive from the row-bound `holdout_teams`; references from the pinned nine-team `CANONICAL_REFERENCE_TEAM_PATHS`; every unreadable or malformed sealed file is a fail-closed abort. |
| P2 | A syntactically valid but non-object JSON row or manifest (`null`, a list, a scalar) escaped as a raw `TypeError` rather than `GateBAbort`. | `isinstance(..., dict)` checks in `_read_arm`, before any field access. |
| P2 | `check_access` read the ledger early and `append_entry` wrote it much later; two concurrent combines could both observe a free budget and both publish. | `_ledger_lock` (`O_CREAT\|O_EXCL`) spans the authoritative re-check, the append, and the publish. The early `check_access` remains, explicitly documented as a non-authoritative fail-fast. |
| P1 | Covering the `(seed_index, opp_policy, opp_team_path)` grid proved the right battle SLOTS existed, not that each slot held the battle it scheduled. `seeds.jsonl` proved the canonical seeds existed but was never tied to the rows, so both arms could carry identical, uniformly wrong values — `pair_runs` only detects variance WITHIN an arm. The positive fixture wrote `battle_id="b0"` and `run_id="r"` and passed. | Per-key re-derivation of `seed` and `battle_id`, plus `format_id`, `config_id`, `run_id`, `hero_team_path`, and `dirty` required to be exactly `False`. Fixtures emit real canonical values; a parametrized regression sets each field wrong uniformly across every row of both arms. |

## 1t. What changed in Rev. 21 — mechanical sync of Task 11 with the flat CLI

Not a review round. Task 11 is implemented and review-PASS as `b71923f`; this revision replaces
§14's embedded test and implementation code with that committed source and corrects the argparse
instructions it had been carrying.

| Item | Plan said (through Rev. 20) | Reality in `cli.py`, and what §14 now says |
| --- | --- | --- |
| Parser shape | "register both subparsers" | There are no argparse subparsers anywhere in `cli.py`. A single flat `command` positional with a `choices` list; both command names were added to it. |
| Required flags | "all five `required=True`" | Impossible: the options are GLOBAL and shared, so `required=True` would make `ladder`/`smoke`/`gauntlet`/… refuse to start. The pre-existing `--i8d-verdict-path` already documents exactly this. The five new flags use `default=""`, and `main()` enforces per-command required-ness via `parser.error(...)` — argparse's own error path (usage on stderr, exit 2), matching `generalisation-plan`/`-analyze`. |
| Test count | 9 | 14. The 9 plan tests, plus a second verdict-path case, a `LeakageScanError`-vs-`LeakageDriftError` separation test, two end-to-end handler regressions, and an empty-defaults test pinning the flat-CLI contract. |
| Two plan tests | asserted only `returncode != 0` + flag name in stderr | Vacuous: an *invalid choice* prints the full usage line, which already contains `--out-dir`, so they passed before the subcommands existed. Both now also assert `"invalid choice" not in stderr`. |
| Exit codes | described in prose | Implemented and unit-tested: `GateBAbort` 1, `AccessBudgetError` 2, the four holdout-integrity guards 3, `LeakageScanError` 4 (checked *before* the drift branch so "could not check" never reads as "checked, found a leak"), unrecognized type → `TypeError`. |
| Blocker honesty | asserted | Proven end-to-end: a full arm invocation and a full combine invocation each reach the named Task 13 blocker, exit 1, print no traceback, and publish no output directory — with no teams, server, or battles involved. |

## 2. Team Sourcing — D-1b resolved, Task 13 fail-closed pending source-proof

**Decision (user, this revision):** Option 1 — a published, concluded Reg M-A tournament source.
Candidate: the concluded **Rutgers Scarlet Classic** (Reg M-A, 7 Swiss rounds + Top 8, mandatory
full team sheets, public standings) —
[tournament details](https://play.limitlesstcg.com/tournament/69eba1eb19228b1daf6bf907/details) ·
[standings](https://play.limitlesstcg.com/tournament/69eba1eb19228b1daf6bf907/standings).

**This approval is conditional, not final — Task 13 stays BLOCKED until all of the following are
satisfied, in order, before any team file is created:**

1. **Source-proof:** confirm all six candidate team sheets are publicly and reproducibly
   retrievable as **full sheets** (species, items, moves, natures/EVs where published) — not
   Pokémon icons/species-only standings rows. This has not been attempted in this revision (it
   is explicitly sequenced as its own step, separate from this Rev. 2 fix pass, per the user's
   own instructions) and is not claimed to be true or false here.
2. **Pre-registered selection rule, fixed before any sheet is read for real:** places 1–6 by
   final standing; a placement is skipped, in placement order, **only** for illegality under
   `gen9championsvgc2026regma`, exact contamination (hash collision with an existing repo team),
   or a sheet that is not fully accessible — never for any other reason, and never re-ordered
   after the fact.
3. **No reconstruction.** No team is completed or guessed from icons, species-only standings,
   memory, or inference. A team whose full sheet cannot be read as published is skipped per rule
   2, not filled in.
4. **Fallback, only if step 1 fails for the primary source:** check **UmbreNews** as a second
   published Reg M-A source —
   [tournament details](https://play.limitlesstcg.com/tournament/69f86c8fe23aab068aada732/details).
   If that also fails step 1, **STOP** — do not fabricate teams, do not lower the bar.

**Tasks 1–12 do not depend on this decision and are not blocked by it.**

### 2a. AMENDMENT, 2026-07-22 — the Task 13 source is now VGCPastes, not Rutgers

**Everything in §2 above is retained as the historical record of the D-1b decision and the rules it
fixed. Nothing above is deleted or reinterpreted.** What follows supersedes it on one point only:
*which source Task 13 builds from*.

**Why.** The Rutgers source-proof PASSED (independent review,
`docs/projects/champions/audits/2026-07-22-gate-b-source-proof-independent-review.md`), but Task 13
construction was BLOCKED there: that tournament's Open Team Sheet tier structurally never publishes
EVs or natures, so building playable teams required synthesizing them — beyond what rule 3 ("No
reconstruction") authorizes. Rather than rule on synthetic spreads, the project owner chose a source
that publishes complete sets.

**Authorized source (owner decision, 2026-07-22).** The VGCPastes Repository sheet
"Champions M-A Featured Teams"
(`https://docs.google.com/spreadsheets/d/1axlwmzPA49rYkqXh7zHvAtSP-TKbM0ijGYBPRflLSWw/edit?gid=417374305`).

**Selection rule (owner-fixed, before any paste was read for construction):** the first six entries,
in table order, with `EVs = Yes`, a reachable PokéPaste, six complete Pokémon, and declared format
`gen9championsvgc2026regma`. The six resulting IDs are enumerated and **must not be substituted or
re-ordered**, in particular not after seeing species overlap or any bot behaviour:

| # | Team ID | Placement | PokéPaste |
|---|---|---|---|
| 1 | PC1102 | PJCS 2026 Champion (Hiroshi Onishi) | `pokepast.es/c17e51b1dee42c8c` |
| 2 | PC1101 | PJCS 2026 Champion, Seniors | `pokepast.es/1f7d6d16d171d672` |
| 3 | PC1100 | PJCS 2026 Runner-up | `pokepast.es/34cb00fce368cd94` |
| 4 | PC1099 | PJCS 2026 Runner-up, Seniors | `pokepast.es/879641da13859e2f` |
| 5 | PC1098 | PJCS 2026 Top 4, Seniors | `pokepast.es/8bcfc47c2d206318` |
| 6 | PC1097 | PJCS 2026 Top 4, Seniors | `pokepast.es/25efa05b579532c4` |

**Consequences for the rules above.**

- **Rule 1** is satisfied by this source in the stronger sense: natures and EVs *are* published, so
  the "where published" clause is met by presence, not by permitted absence.
- **Rule 2**'s placement-order skip mechanism is replaced, for this source, by the sheet-order
  selection rule above. Its *spirit* is unchanged: fixed before reading, never re-ordered after.
- **Rule 3** is satisfied without qualification: no field is completed, guessed, or synthesized.
- **Rule 4** (UmbreNews fallback) is **not** reached and is now moot for Task 13 — it was
  conditioned on the primary source failing rule 1, which never happened.
- The `ev-nature-synthesis-rule.md` frozen under the Rutgers evidence set is **not used** by this
  path. It remains in the historical evidence tree; it is not a Task 13 input.

**Evidence and verification:**
`docs/projects/champions/audits/2026-07-22-task13-vgcpastes-source-selection.md` +
`docs/projects/champions/audits/2026-07-22-task13-vgcpastes-source-evidence/`. All six pastes are
frozen with SHA-256, all six carry complete EVs/natures/items/abilities/four moves on six Pokémon,
and all six return exit 0 from `pokemon-showdown validate-team gen9championsvgc2026regma` against
the pinned checkout `f8ac140`.

**Near-duplicate scope, stated so it is not overread:** the production guard compares each holdout
team against the nine pinned existing Champions M-A reference teams **only**. It does not compare
holdout teams against each other, and this amendment does not change that. PC1099 and PC1098 share
an identical species set (with different items/moves/spreads); that is recorded as audit information
in the selection audit, not as a gate input.

### 2b. AMENDMENT A1 sync, 2026-07-22 — opaque IDs, one allowlist entry, static baseline

Mirrors **Amendment A1** of the APPROVED spec (owner decision, narrow). §2a's source selection is
unchanged.

1. **Opaque internal team IDs** (a fixed `gbh_*` set, frozen selection order). **Only the
   public-ID-to-internal-ID mapping is exclusive to the holdout manifest.** The internal IDs
   themselves necessarily appear in the allowlisted operational artifacts — team filenames, panel,
   baseline manifest, run evidence — which is exactly where §3.3 permits a holdout identifier to
   live. Documents and tests hardcode neither the IDs nor the mapping; both are read from the
   manifest.
2. **One allowlist entry**, exactly the frozen source-evidence directory, because the sealed `.txt`
   files are intentionally byte-identical to the frozen pastes. No broader `docs/` exemption, none
   for the selection audit, none for tests.
3. **Static Gate B baseline**: no `reference_jsonl`/`reference_sha256`, no `dev_schedule_path`;
   schedule re-derived from code; additive loader/verifier, generic T6 contract untouched.

This closes the two STOPs reported after `1c2a31b` by amendment, not by weakening a guard.

## 3. File structure (updated)

```
showdown_bot/src/showdown_bot/eval/
  strength_holdout_schedule.py   NEW  Task 1  -- 180-key schedule, now with a global seed_index
  holdout_leakage_scan.py        NEW  Task 2  -- identifier grep + repo-wide raw-payload byte scan
  strata_guard.py                NEW  Task 3  -- fail-closed Windows/Kaggle stratum detection
  near_duplicate.py              NEW  Task 4  -- species-overlap near-duplicate flag
  holdout_disjointness.py        NEW  Task 5  -- exact-hash disjointness vs. frozen coverage (unchanged)
  baseline.py                    MODIFY  Task 6 -- register the new Champions holdout manifest
  strength_holdout_verdict.py    NEW  Task 7+8 -- upstream verification + McNemar/report wiring
  strength_holdout_runner.py     NEW  Task 9+10 -- per-arm execution + combine/guards/publish
  team_sealing.py                NEW  Task 12 -- provenance/hash sealing (real team_content_hash)
  cli.py                         MODIFY  Task 11 -- arm + combine CLI subcommands

config/eval/
  panels/panel_champions_strength_holdout_v0.yaml     NEW  Task 1 (schema)  / Task 13 step 3 (real content — DONE)
  holdout/champions_strength_holdout_v0_manifest.json NEW  Task 5 (schema)  / Task 13 step 3 (real content — DONE)
  baselines/champions-strength-holdout-v0.json        NEW  committed ONCE in Task 13 step 3 with final closed-schema values (DONE); its schema/loader/verifier live in baseline.py (Task 6). Immutable after first commit (test_baseline_manifest_git_immutability) — never a Task-6 placeholder.

showdown_bot/teams/panel_champions_strength_holdout_v0/   NEW  — the six sealed gbh_* .txt/.packed (Task 13 step 2 — DONE)

showdown_bot/tests/
  test_strength_holdout_schedule.py    NEW  Task 1
  test_holdout_leakage_scan.py         NEW  Task 2
  test_strata_guard.py                 NEW  Task 3
  test_near_duplicate.py               NEW  Task 4
  test_holdout_disjointness.py         NEW  Task 5
  test_baseline_strength_holdout.py    NEW  Task 6
  test_strength_holdout_verdict.py     NEW  Task 7+8
  test_strength_holdout_runner.py      NEW  Task 9+10
  test_cli_strength_holdout_gate.py    NEW  Task 11
  test_team_sealing.py                 NEW  Task 12
```

`strength_holdout_verdict.py` (pure: upstream verification + verdict rendering, no I/O beyond
reading verdict files) is now split from `strength_holdout_runner.py` (orchestration: plays
battles, calls the guards, publishes) — this split is itself part of the fix for P1-2/P1-1: the
pure logic is directly unit-testable with fixtures, with no battle/server mocking needed at all.

---

## 4. Task 1 — Strength-holdout schedule (180 battle-keys, now with a global seed index)

**Files:**
- Create: `showdown_bot/src/showdown_bot/eval/strength_holdout_schedule.py`
- Test: `showdown_bot/tests/test_strength_holdout_schedule.py`

**Before starting:** read `showdown_bot/src/showdown_bot/eval/schedule.py`'s `ScheduleRow` in
full — it carries an explicit `seed_index: int` contiguous 0..N-1, which is what
`derive_battle_seed` actually needs. Rev. 1's `BattleKey` only had `seed` (0-14), which repeats
12× across the 180-key schedule (once per each of the 6 teams × 2 policies) and would collide if
ever passed to `derive_battle_seed` directly — this task fixes that.

- [ ] **Step 1: Write the failing tests**

```python
# showdown_bot/tests/test_strength_holdout_schedule.py
import pytest

from showdown_bot.eval.strength_holdout_schedule import (
    build_strength_holdout_schedule, STRENGTH_HOLDOUT_N_SEEDS,
    STRENGTH_HOLDOUT_OPPONENT_POLICIES, STRENGTH_HOLDOUT_FORMAT_ID,
)


def _six_teams():
    return sorted(f"holdout_{i}" for i in range(6))


def test_schedule_has_exactly_180_battle_keys():
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    assert len(schedule.battle_keys) == 180


def test_seed_index_is_globally_contiguous_0_to_179_with_no_duplicates():
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    indices = sorted(k.seed_index for k in schedule.battle_keys)
    assert indices == list(range(180))


def test_local_seed_repeats_across_the_12_team_policy_cells_but_seed_index_never_does():
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    # local `seed` (0-14) legitimately repeats once per (team, policy) cell -- 12 cells x 15 = 180
    local_seed_counts = {}
    for k in schedule.battle_keys:
        local_seed_counts[k.seed] = local_seed_counts.get(k.seed, 0) + 1
    assert local_seed_counts == {s: 12 for s in range(15)}
    # but the pair (team, policy, seed) is unique, and seed_index is unique per key
    triples = {(k.holdout_team_id, k.opponent_policy, k.seed) for k in schedule.battle_keys}
    assert len(triples) == 180
    seed_indices = {k.seed_index for k in schedule.battle_keys}
    assert len(seed_indices) == 180


def test_schedule_rejects_wrong_team_count():
    with pytest.raises(ValueError, match="exactly 6 teams"):
        build_strength_holdout_schedule(holdout_team_ids=_six_teams()[:5], panel_hash="a" * 16)


def test_schedule_rejects_duplicate_teams():
    with pytest.raises(ValueError, match="unique"):
        build_strength_holdout_schedule(holdout_team_ids=["holdout_0"] * 6, panel_hash="a" * 16)


def test_schedule_rejects_unsorted_teams():
    unsorted = ["holdout_5", "holdout_0", "holdout_1", "holdout_2", "holdout_3", "holdout_4"]
    with pytest.raises(ValueError, match="sorted"):
        build_strength_holdout_schedule(holdout_team_ids=unsorted, panel_hash="a" * 16)


def test_schedule_is_deterministic():
    a = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    b = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    assert a.schedule_hash == b.schedule_hash


def test_schedule_hash_changes_if_a_team_changes():
    a = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    other = sorted(list(_six_teams())[:5] + ["holdout_other"])
    b = build_strength_holdout_schedule(holdout_team_ids=other, panel_hash="a" * 16)
    assert a.schedule_hash != b.schedule_hash


def test_format_id_is_the_current_champions_regulation():
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    assert schedule.format_id == "gen9championsvgc2026regma" == STRENGTH_HOLDOUT_FORMAT_ID


def test_schedule_hash_changes_if_panel_hash_changes():
    a = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    b = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="b" * 16)
    assert a.schedule_hash != b.schedule_hash
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest showdown_bot/tests/test_strength_holdout_schedule.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# showdown_bot/src/showdown_bot/eval/strength_holdout_schedule.py
"""Gate B (Independent Strength Holdout) schedule construction (DESIGN sec 3.2)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

STRENGTH_HOLDOUT_PANEL_PATH = "config/eval/panels/panel_champions_strength_holdout_v0.yaml"
STRENGTH_HOLDOUT_MANIFEST_PATH = "config/eval/holdout/champions_strength_holdout_v0_manifest.json"
STRENGTH_HOLDOUT_SEED_BASE = "champions-strength-holdout-v0"  # PROPOSED, DESIGN:333-334
STRENGTH_HOLDOUT_FORMAT_ID = "gen9championsvgc2026regma"
STRENGTH_HOLDOUT_N_SEEDS = 15
STRENGTH_HOLDOUT_OPPONENT_POLICIES = ("heuristic", "max_damage")
# PROPOSED (grounding report sec 3): reuses I8-D/Coverage's standing Champions hero team.
STRENGTH_HOLDOUT_HERO_TEAM_PATH = "showdown_bot/teams/fixed_champions_v0.txt"

STRENGTH_HOLDOUT_EXPECTED_PANEL_HASH = ""    # frozen once Task 13 seals the six teams
STRENGTH_HOLDOUT_EXPECTED_MANIFEST_HASH = ""


def _sha16(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class BattleKey:
    holdout_team_id: str
    opponent_policy: str
    seed: int          # 0..14: the per-(team, policy) seed slot (DESIGN's own vocabulary)
    seed_index: int     # 0..179: GLOBAL contiguous index. `seed` repeats across the 12
                        # (team, policy) cells and must NEVER be passed to derive_battle_seed --
                        # only seed_index is unique per battle-key.


@dataclass(frozen=True)
class StrengthHoldoutSchedule:
    battle_keys: tuple[BattleKey, ...]
    schedule_hash: str
    panel_hash: str
    seed_base: str
    format_id: str


def build_strength_holdout_schedule(
    *, holdout_team_ids: list[str], panel_hash: str,
    seed_base: str = STRENGTH_HOLDOUT_SEED_BASE,
    n_seeds: int = STRENGTH_HOLDOUT_N_SEEDS,
    opponent_policies: tuple[str, ...] = STRENGTH_HOLDOUT_OPPONENT_POLICIES,
) -> StrengthHoldoutSchedule:
    if len(holdout_team_ids) != 6:
        raise ValueError(f"strength holdout requires exactly 6 teams, got {len(holdout_team_ids)}")
    if len(set(holdout_team_ids)) != 6:
        raise ValueError("holdout_team_ids must be unique")
    if list(holdout_team_ids) != sorted(holdout_team_ids):
        raise ValueError("holdout_team_ids must be pre-sorted for a deterministic hash")

    triples = [
        (team_id, policy, seed)
        for team_id in holdout_team_ids
        for policy in opponent_policies
        for seed in range(n_seeds)
    ]
    keys = tuple(
        BattleKey(holdout_team_id=t, opponent_policy=p, seed=s, seed_index=idx)
        for idx, (t, p, s) in enumerate(triples)
    )
    expected = len(holdout_team_ids) * len(opponent_policies) * n_seeds
    if len(keys) != expected:
        raise ValueError(f"expected {expected} battle-keys, built {len(keys)}")

    schedule_hash = _sha16(json.dumps(
        {
            "keys": [[k.holdout_team_id, k.opponent_policy, k.seed, k.seed_index] for k in keys],
            "seed_base": seed_base, "format_id": STRENGTH_HOLDOUT_FORMAT_ID,
            # panel_hash binds panel identity into schedule identity, matching every other gate's
            # convention: coverage_schedule/i8d_schedule/panel_schedule/generalisation-planner and
            # schedule.py's own loader all bind it via compute_schedule_hash(version, rows) --
            # without this, two schedules built from the same six team IDs but different panel
            # content (different team files behind those IDs) would collide on schedule_hash.
            # compute_schedule_hash itself is not reusable here, and that is a deliberate,
            # disclosed divergence, not an oversight: its rows carry real hero_team_path/
            # opp_team_path strings, which change if a team's file content changes under a fixed
            # path. BattleKey has no such field -- only holdout_team_id -- because team files do
            # not exist until Task 13 seals them. Hashing panel_hash directly closes the same gap
            # without depending on paths that do not exist yet.
            "panel_hash": panel_hash,
        },
        sort_keys=True, separators=(",", ":"),
    ))
    return StrengthHoldoutSchedule(
        battle_keys=keys, schedule_hash=schedule_hash, panel_hash=panel_hash,
        seed_base=seed_base, format_id=STRENGTH_HOLDOUT_FORMAT_ID,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest showdown_bot/tests/test_strength_holdout_schedule.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/eval/strength_holdout_schedule.py showdown_bot/tests/test_strength_holdout_schedule.py
git commit -m "feat(champions): Gate B 180-key schedule with a global seed_index"
```

---

## 5. Task 2 — Leakage-drift guard (identifier grep + repo-wide raw-payload byte scan)

**Files:**
- Create: `showdown_bot/src/showdown_bot/eval/holdout_leakage_scan.py`
- Test: `showdown_bot/tests/test_holdout_leakage_scan.py`

**Fix vs. Rev. 1 (P2-3):** a line-based `git grep -F` can find a short token (a hash, a path, an
id) but cannot reliably find a whole multi-line team export appearing verbatim in another file —
`git grep`, like grep generally, matches per line, and no single line contains an embedded
literal newline. DESIGN's own text requires scanning for both kinds of leak ("team_hash,
team_path, team_id, **packed/.txt content**") — this task now does both: identifier grep for the
short tokens, and (below, rebuilt Rev. 12) a **raw-payload byte scan** for whole-content leaks.

**Fix vs. Rev. 4 (N3, §1d):** `teams_root` now genuinely reaches both the git-tracked-file
listing and the content scan — Rev. 4's `_all_tracked_team_content_hashes()` called
`_git_tracked_files()` with no argument, always scanning the ambient process CWD regardless of
what `teams_root` the caller passed, and silently swallowing every resulting lookup failure via
`except PanelError: continue` (fail-open, not fail-closed). Every `git` subprocess call now takes
an explicit `cwd`, so a test (or a caller with a non-default `teams_root`) is never at the mercy
of whatever directory the test process happens to be running from — a real failure mode on
Windows with multiple worktrees.

**Fix vs. Rev. 11 (Rev. 12, §1k, P1 #1 + P1 #2 — user-found, verified against this exact code
block before either fix):** `_is_allowed` applied one `.startswith`-based rule to both single
files and directories, letting a suffix or pseudo-subpath (`heldout_ledger.jsonl.evil`,
`...yaml.backup`, `...manifest.json/copied`) pass the allowlist — fixed by splitting
`ALLOWED_EXACT_PATHS` (`==` only) from `ALLOWED_DIRECTORY_PREFIXES` (`.startswith`, safe because
every entry already ends in `/`). Separately, the whole content-leakage scan
(`scan_for_content_leakage`/`_all_tracked_team_content_hashes`, Rev. 10 and earlier) covered only
`.txt` files under `showdown_bot/teams/` with a co-located `.packed` partner, as one combined
whole-file hash, compared only against other similarly-shaped files — invisible to a payload
copied into a report, a test, a bare `.txt` with no `.packed` partner, or embedded inside a larger
file, and sensitive to this repo's own `core.autocrlf=true` working-copy translation on Windows
besides. Replaced by `scan_for_raw_payload_leakage`, a repo-wide byte-exact substring scan over
every git-tracked file's COMMITTED blob content. Full reasoning and the downstream Task 10/12/13
impact: §1k.

**Fix vs. Rev. 12 (Rev. 13, §1l, second review round P1):** `scan_for_raw_payload_leakage` now
rejects an empty `team_ids` list itself (`ValueError`), fail-closed, independent of Task 10's own
caller-side cross-check (§13) — an empty list previously made the whole scan a silent no-op.

**Found during real implementation (not a review round — Codex gave Task 2 FINAL REVIEW: PASS
on the text below; these two surfaced only once the code actually ran):** (1) `_grep_identifier`
passed the caller's complete tracked-file list as individual `git grep` argv entries; against
this repo's own 2038 tracked files (131 KB of path text) that overflows Windows'
`CreateProcess` command-line length limit (`WinError 206`). Fixed by omitting the file list
entirely — `git grep` with no explicit pathspec already searches every tracked file by default,
so the search scope is unchanged; only how it's expressed is. (2) The RED test asserting a
fabricated identifier string has zero hits repo-wide used the default `cwd="."` (the real
ambient repo) — but that fabricated string is quoted in the RED test's own source, which is
itself embedded as a worked example in *this plan document*, now committed. The moment Rev. 14
landed, the "absent" identifier stopped being absent. Fixed by moving that one test onto an
isolated `_init_repo` fixture, matching every other test in this file, instead of relying on the
real repo never happening to contain the literal fixture string.

- [ ] **Step 1: Write the failing tests**

```python
# showdown_bot/tests/test_holdout_leakage_scan.py
import os
import subprocess

import pytest

from showdown_bot.eval.holdout_leakage_scan import (
    scan_for_leakage, scan_for_raw_payload_leakage, assert_no_holdout_leakage,
    LeakageDriftError, LeakageScanError, LeakageHit, _is_allowed,
)


def _init_repo(tmp_path, files: dict[str, bytes]) -> str:
    """Real git repo fixture: init, write, add, commit every given path -> bytes, exactly as
    given. Several tests below need REAL committed git blobs, not a monkeypatched stand-in for
    the comparison logic -- the whole point of the raw-payload scan (P1 #2, Rev. 12 review) is
    what it finds when it reads actual git-tracked content, including a case (CRLF) that mocking
    the comparison alone could never exercise."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    # Local to this throwaway fixture repo only (never --global): the fixture writes exact bytes
    # and must commit exactly those bytes, not whatever this machine's own core.autocrlf=true
    # would rewrite them to on `git add` -- and gpgsign=false so a machine with commit signing
    # enforced globally can't make this disposable fixture repo hang or fail.
    subprocess.run(["git", "config", "core.autocrlf", "false"], cwd=repo, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True)
    for rel_path, content in files.items():
        full = repo / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(content)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "fixture"], cwd=repo, check=True)
    return str(repo)


def test_is_allowed_matches_exact_allowlisted_files():
    assert _is_allowed("config/eval/panels/panel_champions_strength_holdout_v0.yaml")
    assert _is_allowed("config/eval/holdout/champions_strength_holdout_v0_manifest.json")
    assert _is_allowed("config/eval/baselines/champions-strength-holdout-v0.json")
    assert _is_allowed("config/eval/heldout_ledger.jsonl")


def test_is_allowed_matches_real_children_of_directory_prefixes():
    assert _is_allowed("showdown_bot/teams/panel_champions_strength_holdout_v0/holdout_0.txt")
    assert _is_allowed("data/eval/champions-panel-v0/strength-holdout-v0/verdict.json")


def test_is_allowed_rejects_dev_and_coverage_paths():
    assert not _is_allowed("config/eval/schedules/champions_dev_gauntlet.yaml")
    assert not _is_allowed("showdown_bot/teams/panel_champions_v0/rain_offense.txt")
    assert not _is_allowed("config/eval/coverage/champions_coverage_v0_manifest.json")


def test_is_allowed_rejects_suffix_and_pseudo_subpath_bypasses_of_exact_files():
    # P1 #1 (Rev. 12 review): `path == prefix or path.startswith(prefix)` treated single FILES
    # as prefixes too, so anything sharing that prefix -- regardless of what followed it --
    # matched. Single files now require exact equality (ALLOWED_EXACT_PATHS); all three must be
    # rejected under the fixed rule.
    assert not _is_allowed("config/eval/heldout_ledger.jsonl.evil")
    assert not _is_allowed("config/eval/panels/panel_champions_strength_holdout_v0.yaml.backup")
    assert not _is_allowed("config/eval/holdout/champions_strength_holdout_v0_manifest.json/copied")


def test_is_allowed_normalizes_backslashes_before_comparing():
    # git itself always reports/expects forward slashes; a caller-supplied Windows-style path
    # (e.g. from os.path.join on Windows) must not bypass or miss the allowlist on that account.
    assert _is_allowed("showdown_bot\\teams\\panel_champions_strength_holdout_v0\\holdout_0.txt")
    assert not _is_allowed("config\\eval\\heldout_ledger.jsonl.evil")


def test_scan_for_leakage_finds_no_hits_for_an_identifier_absent_from_the_repo(tmp_path):
    # Found running for real (implementation time, not a review round): this can't default to
    # cwd="." (the real ambient repo) -- this very plan document embeds this whole test file as
    # a worked example and is itself committed, so the "absent" identifier string literally
    # appears in a tracked file the moment the plan lands. An isolated fixture repo has no such
    # self-reference risk.
    repo = _init_repo(tmp_path, {"README.md": b"unrelated content"})
    assert scan_for_leakage(["definitely-not-a-real-identifier-zzz-9f8e7d"], cwd=repo) == []


def test_scan_for_leakage_rejects_empty_identifier():
    with pytest.raises(ValueError, match="empty identifier"):
        scan_for_leakage([""])


def test_scan_for_raw_payload_leakage_flags_txt_payload_copied_into_a_report(tmp_path):
    txt_payload = b"Fixture Mon @ Focus Sash\nAbility: Levitate\n"
    repo = _init_repo(tmp_path, {
        "showdown_bot/teams/panel_champions_strength_holdout_v0/holdout_0.txt": txt_payload,
        "showdown_bot/teams/panel_champions_strength_holdout_v0/holdout_0.packed": b"|packed-0|",
        "reports/some-analysis.md": b"# Analysis\n\n" + txt_payload,
    })
    hits = scan_for_raw_payload_leakage(["holdout_0"], cwd=repo)
    assert any(h.path == "reports/some-analysis.md" for h in hits)


def test_scan_for_raw_payload_leakage_flags_packed_payload_copied_into_a_test_fixture(tmp_path):
    packed_payload = b"|packed-payload-bytes|"
    repo = _init_repo(tmp_path, {
        "showdown_bot/teams/panel_champions_strength_holdout_v0/holdout_0.txt": b"Fixture Mon @ Focus Sash\n",
        "showdown_bot/teams/panel_champions_strength_holdout_v0/holdout_0.packed": packed_payload,
        "showdown_bot/tests/fixtures/some_test_fixture.py": b"PACKED = " + packed_payload,
    })
    hits = scan_for_raw_payload_leakage(["holdout_0"], cwd=repo)
    assert any(h.path == "showdown_bot/tests/fixtures/some_test_fixture.py" for h in hits)


def test_scan_for_raw_payload_leakage_flags_payload_embedded_inside_a_larger_tracked_file(tmp_path):
    txt_payload = b"Fixture Mon @ Focus Sash\nAbility: Levitate\n"
    repo = _init_repo(tmp_path, {
        "showdown_bot/teams/panel_champions_strength_holdout_v0/holdout_0.txt": txt_payload,
        "showdown_bot/teams/panel_champions_strength_holdout_v0/holdout_0.packed": b"|packed-0|",
        # the payload sits in the MIDDLE of a much bigger tracked file -- not a whole-file match.
        "docs/scratch/team-dump.json": b'{"unrelated": "prefix", "blob": "' + txt_payload + b'", "more": "suffix"}',
    })
    hits = scan_for_raw_payload_leakage(["holdout_0"], cwd=repo)
    assert any(h.path == "docs/scratch/team-dump.json" for h in hits)


def test_scan_for_raw_payload_leakage_flags_a_txt_only_copy_with_no_packed_partner(tmp_path):
    # the OLD scan_for_content_leakage (Rev. 10 and earlier) required a co-located .packed file
    # to even compute a comparable hash -- a .txt-only copy was invisible by construction
    # (team_content_hash raised PanelError, silently skipped via `except PanelError: continue`).
    # The raw-payload scan has no such precondition: it matches byte content directly.
    txt_payload = b"Fixture Mon @ Focus Sash\nAbility: Levitate\n"
    repo = _init_repo(tmp_path, {
        "showdown_bot/teams/panel_champions_strength_holdout_v0/holdout_0.txt": txt_payload,
        "showdown_bot/teams/panel_champions_strength_holdout_v0/holdout_0.packed": b"|packed-0|",
        # a bare .txt copy elsewhere, deliberately with NO .packed sibling at all.
        "showdown_bot/teams/panel_champions_v0/suspicious_copy.txt": txt_payload,
    })
    hits = scan_for_raw_payload_leakage(["holdout_0"], cwd=repo)
    assert any(h.path == "showdown_bot/teams/panel_champions_v0/suspicious_copy.txt" for h in hits)


def test_scan_for_raw_payload_leakage_does_not_flag_the_holdouts_own_allowlisted_files(tmp_path):
    txt_payload = b"Fixture Mon @ Focus Sash\nAbility: Levitate\n"
    packed_payload = b"|packed-0|"
    repo = _init_repo(tmp_path, {
        "showdown_bot/teams/panel_champions_strength_holdout_v0/holdout_0.txt": txt_payload,
        "showdown_bot/teams/panel_champions_strength_holdout_v0/holdout_0.packed": packed_payload,
        # legitimate self-reference: the manifest happens to embed the team's own .txt content
        # verbatim (e.g. a debug/export dump) -- must NOT be flagged, it's the holdout's own file.
        "config/eval/holdout/champions_strength_holdout_v0_manifest.json": b'{"embedded": "' + txt_payload + b'"}',
        "data/eval/champions-panel-v0/strength-holdout-v0/rows.jsonl": packed_payload,
    })
    hits = scan_for_raw_payload_leakage(["holdout_0"], cwd=repo)
    assert hits == []


def test_scan_for_raw_payload_leakage_rejects_an_empty_payload(tmp_path):
    # fail-closed (P1 #2, Rev. 12 review): an empty payload would match every tracked file
    # trivially (`b"" in x` is always True in Python) -- a silent no-op dressed up as "clean".
    repo = _init_repo(tmp_path, {
        "showdown_bot/teams/panel_champions_strength_holdout_v0/holdout_0.txt": b"",
        "showdown_bot/teams/panel_champions_strength_holdout_v0/holdout_0.packed": b"|packed-0|",
    })
    with pytest.raises(ValueError, match="empty"):
        scan_for_raw_payload_leakage(["holdout_0"], cwd=repo)


def test_scan_for_raw_payload_leakage_rejects_an_empty_team_id_list():
    # P1 fix (Rev. 13, §1l, second review round): an empty team_ids list must fail closed here
    # too, independent of Task 10's own caller-side cross-check (defense in depth, not either/or)
    # -- otherwise `payloads` stays {} and the scan silently "passes" without checking anything.
    with pytest.raises(ValueError, match="team_ids must be non-empty"):
        scan_for_raw_payload_leakage([])


def test_scan_for_raw_payload_leakage_wraps_a_git_blob_read_failure(tmp_path):
    # fail-closed (P1 #2, Rev. 12 review): a team_id with no actual committed blob at the
    # conventional path (e.g. a caller passes a team_id that was never sealed/committed) must
    # raise LeakageScanError, not silently scan with a missing/empty needle or crash raw.
    repo = _init_repo(tmp_path, {"README.md": b"unrelated"})
    with pytest.raises(LeakageScanError, match="could not read committed blob"):
        scan_for_raw_payload_leakage(["never_sealed_team"], cwd=repo)


def test_scan_for_raw_payload_leakage_reads_committed_bytes_not_the_crlf_working_copy(tmp_path):
    # DESIGN sec 3.3 + P1 #2 (Rev. 12 review): panel.team_content_hash reads via
    # Path.read_text(), which is subject to this repo's own global core.autocrlf=true translation
    # on a Windows checkout -- a needle sourced that way would silently stop matching a haystack
    # sourced from committed (LF) blob bytes the moment the working copy's line endings drift
    # from what is actually committed. This scan must never have that failure mode: both the
    # needle (the sealed payload) and every haystack file are read via `git show HEAD:<path>`,
    # which returns the COMMITTED bytes regardless of what sits in the working copy right now.
    payload_lf = b"Fixture Mon @ Focus Sash\nAbility: Levitate\n"
    repo = _init_repo(tmp_path, {
        "showdown_bot/teams/panel_champions_strength_holdout_v0/holdout_0.txt": payload_lf,
        "showdown_bot/teams/panel_champions_strength_holdout_v0/holdout_0.packed": b"|packed-0|",
        "reports/leaked-copy.md": payload_lf,  # outside the allowlist -- the leak to catch
    })
    # Corrupt the WORKING COPY of the sealed team's own .txt to CRLF, post-commit, WITHOUT
    # committing that change -- the committed blob (what `git show` reads) stays pure LF.
    working_copy_path = os.path.join(
        repo, "showdown_bot", "teams", "panel_champions_strength_holdout_v0", "holdout_0.txt",
    )
    with open(working_copy_path, "wb") as fh:
        fh.write(payload_lf.replace(b"\n", b"\r\n"))

    hits = scan_for_raw_payload_leakage(["holdout_0"], cwd=repo)
    assert any(h.path == "reports/leaked-copy.md" for h in hits)


def test_assert_no_holdout_leakage_raises_on_either_scan_type(monkeypatch):
    monkeypatch.setattr(
        "showdown_bot.eval.holdout_leakage_scan.scan_for_leakage",
        lambda identifiers, cwd=".": [LeakageHit(identifier="leaked-id", path="config/eval/schedules/other.yaml", line="x")],
    )
    monkeypatch.setattr(
        "showdown_bot.eval.holdout_leakage_scan.scan_for_raw_payload_leakage",
        lambda team_ids, cwd=".": [],
    )
    # team_ids is a placeholder here (the real scan is mocked away) -- kept non-empty since an
    # empty list is no longer a legal input to the real scan_for_raw_payload_leakage (Rev. 13).
    with pytest.raises(LeakageDriftError, match="leaked-id"):
        assert_no_holdout_leakage(identifiers=["leaked-id"], team_ids=["placeholder"])


def test_assert_no_holdout_leakage_raises_on_raw_payload_hits_too(monkeypatch):
    monkeypatch.setattr(
        "showdown_bot.eval.holdout_leakage_scan.scan_for_leakage",
        lambda identifiers, cwd=".": [],
    )
    monkeypatch.setattr(
        "showdown_bot.eval.holdout_leakage_scan.scan_for_raw_payload_leakage",
        lambda team_ids, cwd=".": [LeakageHit(identifier="holdout_0:txt", path="reports/leak.md", line="(raw payload match)")],
    )
    with pytest.raises(LeakageDriftError, match="holdout_0:txt"):
        assert_no_holdout_leakage(identifiers=[], team_ids=["holdout_0"])


def test_git_tracked_files_wraps_a_called_process_error(tmp_path):
    # NF4 fix (Rev. 8): check=True raises subprocess.CalledProcessError when cwd is not a git
    # repository -- a real (not mocked) way to trigger it: point cwd at an empty tmp_path. This
    # was unguarded and would escape scan_for_leakage/scan_for_raw_payload_leakage ->
    # assert_no_holdout_leakage -> combine_strength_holdout_arms as a raw traceback. The N3 fix
    # (Rev. 5) that made cwd/teams_root caller-controllable is exactly what makes this reachable:
    # a caller-supplied teams_root that isn't a git checkout now reaches git directly.
    from showdown_bot.eval.holdout_leakage_scan import _git_tracked_files
    with pytest.raises(LeakageScanError, match="could not list git-tracked files"):
        _git_tracked_files(cwd=str(tmp_path))


def test_grep_identifier_wraps_a_missing_git_executable(monkeypatch):
    # Self-found sibling gap in the same module, same pass: _grep_identifier never set check=True
    # (a nonzero exit is already handled via the manual returncode check right below it), but
    # subprocess.run raises FileNotFoundError for a missing git executable regardless of check=.
    from showdown_bot.eval.holdout_leakage_scan import _grep_identifier

    def _raise(*a, **kw):
        raise FileNotFoundError("git not found")

    monkeypatch.setattr("showdown_bot.eval.holdout_leakage_scan.subprocess.run", _raise)
    with pytest.raises(LeakageScanError, match="could not run git grep"):
        _grep_identifier("some-id", ["some/file.txt"])


def test_read_git_blob_wraps_a_called_process_error(tmp_path):
    # a path that isn't tracked at HEAD (or cwd isn't a git repo) makes `git show HEAD:<path>`
    # exit non-zero -- must surface as LeakageScanError, not a raw CalledProcessError.
    from showdown_bot.eval.holdout_leakage_scan import _read_git_blob
    repo = _init_repo(tmp_path, {"README.md": b"unrelated"})
    with pytest.raises(LeakageScanError, match="could not read committed blob"):
        _read_git_blob("no/such/path.txt", cwd=repo)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest showdown_bot/tests/test_holdout_leakage_scan.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# showdown_bot/src/showdown_bot/eval/holdout_leakage_scan.py
"""Repo-wide leakage-drift guard for the Gate B strength holdout (DESIGN sec 3.3): scans for
BOTH short identifiers (team_hash/team_path/team_id -- line-based grep is fine here) AND the
actual sealed .txt/.packed CONTENT appearing anywhere else in the repo (packed/.txt content --
grep cannot reliably match multi-line content, and a whole-file combined-hash comparison misses a
payload copied into a bigger file or copied without its hash-partner -- see Rev. 12 review's
P1 #2, §1k, fixed this revision by a byte-exact substring scan over every git-tracked file's
COMMITTED content)."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass

ALLOWED_EXACT_PATHS = (
    "config/eval/panels/panel_champions_strength_holdout_v0.yaml",
    "config/eval/holdout/champions_strength_holdout_v0_manifest.json",
    "config/eval/baselines/champions-strength-holdout-v0.json",
    "config/eval/heldout_ledger.jsonl",
)
ALLOWED_DIRECTORY_PREFIXES = (
    "showdown_bot/teams/panel_champions_strength_holdout_v0/",
    "data/eval/champions-panel-v0/strength-holdout-v0/",
    # Spec Amendment A1.2 (APPROVED, 2026-07-22): the holdout's own frozen provenance directory.
    # The six sealed .txt team files are DELIBERATELY byte-identical to the pastes frozen here --
    # that byte-equality is the evidence nothing was altered between the published source and the
    # sealed artifact. scan_for_raw_payload_leakage uses those bytes as its needle, so without this
    # entry the guard reports the holdout's own authoritative source as a leak. Renaming the teams
    # cannot avoid it: the needle is the file's content, not its name.
    #
    # Scope is exactly this directory. The sibling selection-audit file, any broader docs/ prefix,
    # and every test file stay OUTSIDE the allowlist and must keep failing the scan. The trailing
    # "/" makes this a bounded directory prefix, so a similarly-named sibling directory does not
    # inherit the exemption (see _is_allowed).
    "docs/projects/champions/audits/2026-07-22-task13-vgcpastes-source-evidence/",
)
HOLDOUT_TEAMS_DIR = "showdown_bot/teams/panel_champions_strength_holdout_v0/"


class LeakageDriftError(Exception):
    """The scan COMPLETED and FOUND a leak (or git grep itself reported a real error)."""


class LeakageScanError(Exception):
    """NF4 fix (Rev. 8): the scan could NOT be completed at all (git missing from PATH, `cwd`/
    `teams_root` is not a git repository, or a sealed team's committed blob could not be read) --
    distinct from LeakageDriftError, which means the scan ran to completion and found something.
    Collapsing the two would erase a distinction a caller might reasonably want: retrying an
    infra failure is sensible, auto-retrying past a genuine leak finding is not. Left unwrapped
    by combine_strength_holdout_arms, exactly like LeakageDriftError already is (§1f/§19) -- the
    CLI boundary is where these get a documented, per-class handler, not this module."""


@dataclass(frozen=True)
class LeakageHit:
    identifier: str
    path: str
    line: str


def _normalize_path(path: str) -> str:
    """Git always reports/expects forward-slash paths regardless of OS; normalize before any
    comparison so a caller-supplied Windows-style path (e.g. from os.path.join) can't bypass or
    miss the allowlist purely on separator form (P1 #1, Rev. 12 review, §1k)."""
    return path.replace("\\", "/")


def _is_allowed(path: str) -> bool:
    path = _normalize_path(path)
    if path in ALLOWED_EXACT_PATHS:
        return True
    # P1 #1 fix (Rev. 12 review, §1k): directory prefixes already end in "/", so
    # `.startswith(prefix)` only ever matches a REAL child under that directory --
    # "...strength_holdout_v0_evil/x" does NOT start with ".../strength_holdout_v0/" (the "/"
    # itself breaks the match). The bug was never in this branch; it was single FILES being
    # checked with the same startswith rule but no trailing separator to protect them -- fixed by
    # requiring exact equality for those instead (above), not by changing this branch.
    return any(path.startswith(prefix) for prefix in ALLOWED_DIRECTORY_PREFIXES)


def _git_tracked_files(cwd: str = ".") -> list[str]:
    # N3 fix: explicit cwd, never ambient process CWD -- a "unit" test (or a caller with a
    # non-default teams_root) that relies on process CWD is a real Windows-multi-worktree
    # failure mode, not a hypothetical one.
    #
    # NF4 fix (Rev. 8): check=True raises subprocess.CalledProcessError if cwd is not a git repo
    # (or any other nonzero git exit); a missing git executable raises FileNotFoundError from
    # subprocess.run itself, check=True or not. Neither was caught anywhere -- both would escape
    # as a raw traceback through scan_for_leakage/scan_for_raw_payload_leakage ->
    # assert_no_holdout_leakage -> combine_strength_holdout_arms. The N3 fix that made `cwd`
    # caller-controllable is exactly what makes this reachable: a caller-supplied teams_root that
    # doesn't point at a git checkout now reaches git directly, where it didn't before.
    try:
        result = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True, cwd=cwd)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise LeakageScanError(f"could not list git-tracked files under cwd={cwd!r}: {exc}") from exc
    return [line for line in result.stdout.splitlines() if line]


def _read_git_blob(path: str, *, cwd: str = ".") -> bytes:
    """Reads a git-tracked file's COMMITTED bytes (HEAD's blob) -- never the working-copy bytes.
    Reading via open()/Path.read_text() (as panel.py's team_content_hash does, for a different,
    still-legitimate purpose -- team identity/disjointness, not this scan) would make this scan's
    result depend on this repo's global core.autocrlf=true translation on a Windows checkout,
    since a needle and haystack sourced from two different places (one committed, one
    working-copy) can silently stop matching even when the underlying content is identical
    (P1 #2, Rev. 12 review, §1k). `git show HEAD:<path>` reads the blob straight out of the
    object database in binary form, bypassing any working-tree filter, so every comparison this
    function feeds compares the same kind of bytes on both sides."""
    try:
        result = subprocess.run(
            ["git", "show", f"HEAD:{path}"], capture_output=True, check=True, cwd=cwd,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise LeakageScanError(f"could not read committed blob for {path!r} under cwd={cwd!r}: {exc}") from exc
    return result.stdout


def _grep_identifier(identifier: str, files: list[str], cwd: str = ".") -> list[LeakageHit]:
    if not identifier:
        raise ValueError("empty identifier would match every line in the repo")
    if not files:
        return []
    # NF4 fix (Rev. 8): unlike _git_tracked_files, this call never set check=True -- a nonzero
    # exit is already handled below via the manual returncode check. But subprocess.run raises
    # FileNotFoundError (git missing from PATH) regardless of check=, and that path was still
    # unguarded -- self-found while fixing NF4's sibling gap in the same module, same pass.
    #
    # Found running the real test suite against this repo's own 2038 tracked files (131 KB of
    # path text): passing `files` as individual argv entries overflows Windows' CreateProcess
    # command-line length limit (WinError 206, "filename or extension too long") well before
    # 32K chars. `files` is always the caller's complete _git_tracked_files() list (never a
    # narrower subset), and `git grep` with no explicit pathspec already searches every tracked
    # file by default -- so omitting the file list changes nothing about what gets searched,
    # only how the scope is expressed, and removes the argv-length ceiling entirely.
    try:
        result = subprocess.run(
            ["git", "grep", "-n", "-F", identifier], capture_output=True, text=True, cwd=cwd,
        )
    except FileNotFoundError as exc:
        raise LeakageScanError(f"could not run git grep under cwd={cwd!r}: {exc}") from exc
    if result.returncode not in (0, 1):
        raise LeakageDriftError(f"git grep failed for {identifier!r}: {result.stderr.strip()}")
    hits = []
    for line in result.stdout.splitlines():
        path, _, rest = line.partition(":")
        hits.append(LeakageHit(identifier=identifier, path=path, line=rest))
    return hits


def scan_for_leakage(identifiers: list[str], *, cwd: str = ".") -> list[LeakageHit]:
    """Short-token scan (team_hash/team_path/team_id). Empty list == clean."""
    files = _git_tracked_files(cwd=cwd)
    violations: list[LeakageHit] = []
    for identifier in identifiers:
        for hit in _grep_identifier(identifier, files, cwd=cwd):
            if not _is_allowed(hit.path):
                violations.append(hit)
    return violations


def scan_for_raw_payload_leakage(team_ids: list[str], *, cwd: str = ".") -> list[LeakageHit]:
    """Byte-exact scan (DESIGN sec 3.3's 'packed/.txt content' leg; P1 #2 fix, Rev. 12 review,
    §1k): for each sealed holdout team_id, reads its .txt and .packed COMMITTED payload (path
    derived from the fixed HOLDOUT_TEAMS_DIR convention -- the same directory
    ALLOWED_DIRECTORY_PREFIXES already grants) and checks every OTHER git-tracked file's
    COMMITTED bytes for that exact payload as a substring.

    Unlike the whole-file combined-hash comparison this replaces (Rev. 10 and earlier's
    scan_for_content_leakage / _all_tracked_team_content_hashes), this is repo-wide (every
    git-tracked file, not just showdown_bot/teams/*.txt), requires no co-located .packed partner
    on the OTHER side of the comparison (a bare copied .txt is still caught), and matches a
    payload embedded inside a larger file (substring, not whole-file equality). The existing
    combined panel.team_content_hash remains the right tool for team IDENTITY and DISJOINTNESS
    (Task 5, and Task 9's opp_team_hash row-stamping) -- a single hash per team is exactly what
    those need; it is not replaced, only no longer relied on for THIS scan.

    Fails closed on every kind of degenerate input, never silently: an EMPTY team_ids LIST would
    make the whole scan a silent no-op (the payload-collection loop never runs, so `payloads`
    stays `{}` and every downstream file trivially "passes" -- rejected here, Rev. 13 §1l second
    review round P1, as defense in depth independent of Task 10's own caller-side check). An
    empty PAYLOAD for a given team would match every tracked file trivially (`b"" in x` is always
    True in Python); a missing or unreadable committed blob for a claimed team_id is refused
    (LeakageScanError, via _read_git_blob) rather than scanned as an empty needle or silently
    skipped."""
    if not team_ids:
        raise ValueError("team_ids must be non-empty -- an empty list makes this scan vacuous (it would silently report no leaks without checking anything)")
    payloads: dict[str, bytes] = {}
    for team_id in team_ids:
        txt_path = f"{HOLDOUT_TEAMS_DIR}{team_id}.txt"
        packed_path = f"{HOLDOUT_TEAMS_DIR}{team_id}.packed"
        txt_bytes = _read_git_blob(txt_path, cwd=cwd)
        packed_bytes = _read_git_blob(packed_path, cwd=cwd)
        if not txt_bytes:
            raise ValueError(f"empty .txt payload for {team_id!r} at {txt_path!r} -- refusing to scan")
        if not packed_bytes:
            raise ValueError(f"empty .packed payload for {team_id!r} at {packed_path!r} -- refusing to scan")
        payloads[f"{team_id}:txt"] = txt_bytes
        payloads[f"{team_id}:packed"] = packed_bytes

    violations: list[LeakageHit] = []
    for path in _git_tracked_files(cwd=cwd):
        if _is_allowed(path):
            continue
        blob = _read_git_blob(path, cwd=cwd)
        for name, payload in payloads.items():
            if payload in blob:
                violations.append(LeakageHit(identifier=name, path=path, line="(raw payload match)"))
    return violations


def assert_no_holdout_leakage(*, identifiers: list[str], team_ids: list[str], teams_root: str = ".") -> None:
    violations = scan_for_leakage(identifiers, cwd=teams_root) + scan_for_raw_payload_leakage(team_ids, cwd=teams_root)
    if violations:
        detail = "\n".join(f"  {v.identifier!r} in {v.path}: {v.line.strip()}" for v in violations)
        raise LeakageDriftError(f"holdout identifier(s)/content leaked outside the allowlist:\n{detail}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest showdown_bot/tests/test_holdout_leakage_scan.py -v`
Expected: 21 passed (5 `_is_allowed` + 2 `scan_for_leakage` + 9 `scan_for_raw_payload_leakage` +
2 `assert_no_holdout_leakage` + 3 low-level git-subprocess-exception tests)

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/eval/holdout_leakage_scan.py showdown_bot/tests/test_holdout_leakage_scan.py
git commit -m "feat(champions): repo-wide leakage guard -- identifier grep + raw-payload byte scan"
```

---

## 6. Task 3 — Windows/Kaggle stratum guard (fail-closed default)

**Files:**
- Create: `showdown_bot/src/showdown_bot/eval/strata_guard.py`
- Test: `showdown_bot/tests/test_strata_guard.py`

**Fix vs. Rev. 1 (P2-1):** `detect_stratum` no longer treats "not Windows" as "must be Kaggle."
Any environment that isn't explicitly attested aborts.

**Found during code review, after real implementation (Rev. 17, §1p):** Task 3 was implemented
and committed (`3f07ef3`) at the end of the Rev. 16 round; a focused code review on that real
module found two further P1s (a "not Windows" check is not the same as "is really Kaggle," so
Darwin could still claim the Kaggle override; two records sharing an unrecognized stratum passed
the pooling guard silently) -- both live-reproduced against the actual file before being fixed,
and folded into this section below so the plan text matches the real, now-fixed code exactly.

- [ ] **Step 1: Write the failing tests**

```python
# showdown_bot/tests/test_strata_guard.py
import pytest

from showdown_bot.eval.strata_guard import (
    detect_stratum, assert_no_cross_stratum_pooling, stratum_output_root,
    StratumRecord, StrataPoolingError, UnattestedStratumError, WINDOWS_STRATUM, KAGGLE_STRATUM,
)


def test_detect_stratum_respects_explicit_override_when_consistent_with_the_platform(monkeypatch):
    # Rev. 16 fix (§1o, P1 #1): an override may only CONFIRM what platform.system() can prove,
    # never CONTRADICT it -- see test_detect_stratum_rejects_an_override_that_contradicts_the_platform
    # below for the rejection side. "windows" on a real/simulated Windows box, and "kaggle" on a
    # simulated non-Windows box, are the only two consistent combinations.
    monkeypatch.setattr("platform.system", lambda: "Windows")
    assert detect_stratum(env_override="windows") == "windows"
    monkeypatch.setattr("platform.system", lambda: "Linux")
    assert detect_stratum(env_override="kaggle") == "kaggle"


def test_detect_stratum_rejects_an_override_that_contradicts_the_platform(monkeypatch):
    # Rev. 16 fix (§1o, P1 #1): before this fix, env_override bypassed platform.system() entirely
    # -- env_override="kaggle" on the real, fixed Windows measurement host (or the reverse on a
    # non-Windows box) succeeded silently, mislabeling a run's stratum regardless of where it
    # actually executed. DESIGN sec 3.5 cares about the ACTUAL hardware a run executed on, not
    # merely a claimed label -- an override that contradicts observable platform reality is not a
    # valid attestation.
    monkeypatch.setattr("platform.system", lambda: "Windows")
    with pytest.raises(UnattestedStratumError, match="Windows"):
        detect_stratum(env_override="kaggle")
    monkeypatch.setattr("platform.system", lambda: "Linux")
    with pytest.raises(UnattestedStratumError, match="not Windows"):
        detect_stratum(env_override="windows")


def test_detect_stratum_rejects_a_kaggle_override_on_a_non_linux_platform(monkeypatch):
    # Rev. 17 fix (§1p): Rev. 16's fix only checked "is this platform Windows or not" -- Darwin
    # (macOS) is also not Windows, but it is NOT the approved Kaggle environment either (which
    # runs Linux). A "not Windows" consistency check is not the same as a "this is really Kaggle"
    # consistency check; without this, env_override="kaggle" on a developer's Mac laptop would
    # succeed, exactly the "non-Windows box silently trusted as Kaggle" failure mode this whole
    # module exists to prevent (P2-1), reintroduced through the override path specifically.
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    with pytest.raises(UnattestedStratumError, match="Linux"):
        detect_stratum(env_override="kaggle")


def test_detect_stratum_rejects_unknown_override():
    with pytest.raises(ValueError, match="unknown stratum"):
        detect_stratum(env_override="colab")


def test_detect_stratum_accepts_windows_via_platform_sniff(monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Windows")
    assert detect_stratum() == "windows"


def test_detect_stratum_refuses_to_guess_kaggle_from_a_bare_linux_platform(monkeypatch):
    # P2-1 fix: a plain Linux/macOS/CI box must NOT be silently treated as the approved Kaggle
    # environment -- it could be any unattested machine.
    monkeypatch.setattr("platform.system", lambda: "Linux")
    with pytest.raises(UnattestedStratumError, match="env_override"):
        detect_stratum()


def test_assert_no_cross_stratum_pooling_passes_for_a_single_stratum():
    records = [
        StratumRecord(stratum=WINDOWS_STRATUM, platform_string="Windows-11", output_dir="a"),
        StratumRecord(stratum=WINDOWS_STRATUM, platform_string="Windows-11", output_dir="b"),
    ]
    assert_no_cross_stratum_pooling(records)


def test_assert_no_cross_stratum_pooling_rejects_mixed_strata():
    records = [
        StratumRecord(stratum=WINDOWS_STRATUM, platform_string="Windows-11", output_dir="a"),
        StratumRecord(stratum=KAGGLE_STRATUM, platform_string="Linux-5.15", output_dir="b"),
    ]
    with pytest.raises(StrataPoolingError, match="windows"):
        assert_no_cross_stratum_pooling(records)


def test_assert_no_cross_stratum_pooling_rejects_records_with_an_unknown_stratum():
    # Rev. 17 fix (§1p): two records that AGREE with each other but share an unrecognized stratum
    # value (e.g. a corrupted or hand-edited "colab") previously passed silently --
    # len({"colab"}) == 1, so the mixed-strata check alone never fires. Defense in depth: this
    # function's own contract requires every record to represent a REAL, recognized stratum, not
    # merely agree with its neighbors -- independent of whatever validation an upstream caller
    # (Task 10's _validate_stratum_fields) may or may not already have done, matching how
    # scan_for_raw_payload_leakage independently rejects an empty team_ids list rather than
    # relying solely on its own caller's check.
    records = [
        StratumRecord(stratum="colab", platform_string="Colab", output_dir="a"),
        StratumRecord(stratum="colab", platform_string="Colab", output_dir="b"),
    ]
    with pytest.raises(ValueError, match="unknown stratum"):
        assert_no_cross_stratum_pooling(records)


def test_stratum_output_root_separates_strata():
    assert stratum_output_root("windows", "d") != stratum_output_root("kaggle", "d")


def test_stratum_output_root_rejects_unknown_stratum():
    with pytest.raises(ValueError, match="unknown stratum"):
        stratum_output_root("colab", "d")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest showdown_bot/tests/test_strata_guard.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# showdown_bot/src/showdown_bot/eval/strata_guard.py
"""Windows/Kaggle hardware-stratum guard (DESIGN sec 3.5). Fail-closed: only an explicit
attestation (env_override, or Windows sniffed via platform.system()) selects a stratum. A bare
non-Windows box is NOT assumed to be the approved Kaggle environment -- it could be any
unattested machine, and DESIGN requires Kaggle to be a deliberate, separately pre-registered
stratum, not a default. An env_override may only CONFIRM what platform.system() can prove, never
CONTRADICT it (Rev. 16, §1o, P1 #1) -- it selects between platform-consistent choices, it does
not let a caller relabel whatever machine is actually running as a different stratum. "Consistent"
is checked against the specific platform each stratum actually runs on (Windows / Linux), not
merely "is or isn't Windows" (review-fix P1) -- a Mac laptop is not Windows, but it is also not
the approved Kaggle environment, and must not be able to claim it via the override either."""
from __future__ import annotations

import platform
from dataclasses import dataclass

WINDOWS_STRATUM = "windows"
KAGGLE_STRATUM = "kaggle"
VALID_STRATA = (WINDOWS_STRATUM, KAGGLE_STRATUM)


class StrataPoolingError(Exception):
    pass


class UnattestedStratumError(Exception):
    pass


@dataclass(frozen=True)
class StratumRecord:
    stratum: str
    platform_string: str
    output_dir: str


def detect_stratum(*, env_override: str | None = None) -> str:
    system = platform.system()
    if env_override is not None:
        if env_override not in VALID_STRATA:
            raise ValueError(f"unknown stratum {env_override!r}, expected one of {VALID_STRATA}")
        # Rev. 16 fix (§1o, P1 #1): before this check, env_override bypassed platform.system()
        # entirely -- env_override="kaggle" on the real, fixed Windows measurement host (or the
        # reverse on a non-Windows box) succeeded silently. The override may only select between
        # platform-CONSISTENT choices, never contradict what platform.system() can already prove.
        #
        # Rev. 17 fix (§1p): a "is this platform Windows or not" check is NOT the same as "is this
        # platform really Kaggle": Darwin (macOS) is also not Windows, but it is not the approved
        # Kaggle environment (Linux) either. Checked against Linux specifically, not merely "not
        # Windows", or a developer's Mac laptop could claim Kaggle -- exactly the P2-1 failure mode
        # this module exists to prevent, reintroduced through the override path.
        if env_override == WINDOWS_STRATUM and system != "Windows":
            raise UnattestedStratumError(
                f"env_override={env_override!r} claims the Windows stratum, but "
                f"platform.system()={system!r} is not Windows -- the override may "
                "not contradict what the platform can already prove"
            )
        if env_override == KAGGLE_STRATUM and system != "Linux":
            raise UnattestedStratumError(
                f"env_override={env_override!r} claims the Kaggle stratum, but "
                f"platform.system()={system!r} is not Linux -- the approved Kaggle "
                "environment runs Linux, and the override may not contradict what "
                "the platform can already prove"
            )
        return env_override
    if system == "Windows":
        return WINDOWS_STRATUM
    raise UnattestedStratumError(
        f"platform.system()={system!r} is not Windows and no env_override was given "
        "-- pass env_override='kaggle' explicitly on the approved Kaggle environment; a bare "
        "non-Windows host is never assumed to be Kaggle"
    )


def assert_no_cross_stratum_pooling(records: list[StratumRecord]) -> None:
    if not records:
        raise ValueError("assert_no_cross_stratum_pooling requires at least one record")
    # Rev. 17 fix (§1p): two (or more) records that AGREE with each other but share an
    # unrecognized stratum value (e.g. a corrupted or hand-edited "colab") previously passed
    # silently -- len({"colab"}) == 1, so the mixed-strata check below alone never catches it.
    # Every record must represent a REAL, recognized stratum before the agreement check even
    # runs -- defense in depth, independent of whatever validation an upstream caller has done.
    for r in records:
        if r.stratum not in VALID_STRATA:
            raise ValueError(
                f"record for output_dir={r.output_dir!r} has an unknown stratum "
                f"{r.stratum!r}, expected one of {VALID_STRATA} -- refusing to pool records "
                "that do not even represent a recognized stratum"
            )
    strata = {r.stratum for r in records}
    if len(strata) > 1:
        detail = ", ".join(f"{r.output_dir} ({r.stratum})" for r in records)
        raise StrataPoolingError(
            f"records span {len(strata)} strata ({sorted(strata)}) -- refusing to pool: {detail}"
        )


def stratum_output_root(stratum: str, base_dir: str) -> str:
    if stratum not in VALID_STRATA:
        raise ValueError(f"unknown stratum {stratum!r}, expected one of {VALID_STRATA}")
    return f"{base_dir}/{stratum}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest showdown_bot/tests/test_strata_guard.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

Original implementation: `3f07ef3` (`git commit -m "fix(champions): stratum detection fails
closed and rejects a platform-inconsistent override"`). The Rev. 17 review-fix lands as its own
commit on top, per this round's own explicit instruction (a separate review-fix commit, not an
amend):

```bash
git add showdown_bot/src/showdown_bot/eval/strata_guard.py showdown_bot/tests/test_strata_guard.py
git commit -m "fix(champions): reject a Kaggle override off Linux and unknown-stratum record pooling"
```

---

## 7. Task 4 — Species-overlap near-duplicate flag (made agent-executable, Rev. 18, §1q)

**"Rev. 1 code" does not exist -- confirmed, not assumed.** This section previously read "see the
Rev. 1 code, which a reviewer already had the opportunity to flag and did not" without containing
that code or its claimed "same 5" tests anywhere in this document. Searched, read-only, before
writing anything below: `git log --all --oneline -S "find_near_duplicate_flags"` returns exactly
one hit, `16fb5fb` ("freeze Gate B plan Rev. 10..."), which is the commit that FIRST introduced
this plan document into the repository -- at that commit, Task 4's text was ALREADY this same
stub. `git log --all --oneline --diff-filter=A -- "**/near_duplicate.py" "**/test_near_duplicate.py"`
returns nothing -- these files have never been added in this repository's history, in any branch,
at any commit. `git log --follow` on this plan document itself shows only 8 commits total, none
before `16fb5fb`. There is no reviewer who "already had the opportunity to flag" code that was
never committed anywhere this history search can reach -- that claim in the old text was itself
unverified. This section is therefore designed FRESH here, grounded in DESIGN sec 3.3's own text
and this codebase's own existing conventions (species-ID normalization, primarily) -- not
reconstructed as an assumed historical contract.

**Files:**
- Create: `showdown_bot/src/showdown_bot/eval/near_duplicate.py`
- Test: `showdown_bot/tests/test_near_duplicate.py`

**Grounded in DESIGN sec 3.3:** "a content-overlap check at sealing flags any holdout team whose
species set substantially overlaps a touched or coverage team for manual disjointness review
(near-duplicates are not independent)." Three design decisions this sentence leaves open, closed
below with explicit reasoning: (1) what "overlap" means mathematically: (2) the exact threshold
semantics at the boundary; (3) how normalization avoids both false negatives (same species,
different spelling) and false positives (different formes treated as the same species).

**Species-ID normalization matches this codebase's existing convention exactly, not a new
invention.** `to_id(name) -> re.sub(r"[^a-z0-9]", "", name.lower())` is already duplicated
verbatim in `engine/state.py`, `engine/items.py`, and `engine/moves.py`, and wrapped as
`SpeciesDex.to_id` in `battle/opponent.py` (explicitly documented there as "the same Showdown
`toID` transform"). This is Pokemon Showdown's own `toID()`: lowercase, then strip everything
that is not `a-z0-9`. Critically, it does **not** merge formes -- `to_id("Giratina-Origin")` ==
`"giratinaorigin"`, distinct from `to_id("Giratina")` == `"giratina"`; `to_id("Nidoran-M")` ==
`"nidoranm"`, distinct from `to_id("Nidoran-F")` == `"nidoranf"`. `near_duplicate.py` reuses this
exact rule (duplicated as a fifth private copy, matching how the existing three are already
independent duplicates of the same one-line rule rather than a shared import -- `near_duplicate.py`
is a pure `eval/`-side utility with no need to depend on `engine/`) so that a near-duplicate check
never disagrees with how the rest of this codebase already treats species identity: two teams
differing only by a Pokemon's forme are correctly treated as carrying DIFFERENT species for this
check, matching how the engine treats them everywhere else.

**Overlap formula: Jaccard similarity, `|A ∩ B| / |A ∪ B|` -- not the overlap coefficient.** Two
standard set-similarity metrics were considered: Jaccard (`|A ∩ B| / |A ∪ B|`) and the overlap
coefficient (`|A ∩ B| / min(|A|, |B|)`). Both are symmetric in the two sets' roles (a property
`overlap_fraction(a, b)` itself should have, since the function does not itself distinguish
"candidate" from "reference" -- that framing exists only one level up, in
`find_near_duplicate_flags`). Bound to Jaccard because, for two ordinary 6-species VGC teams, the
two formulas disagree sharply at the `0.5` threshold: Jaccard `>= 0.5` requires at least 4 of 6
species shared (`4/8 = 0.5` when the other 2+2 are disjoint); the overlap coefficient `>= 0.5`
requires only 3 of 6 shared (`3/6 = 0.5`), which is ordinary shared-meta-staple overlap between
two competent but unrelated teams, not a near-duplicate. DESIGN sec 3.3 calls for a check that
flags teams that are near-**identical**, not merely similar -- the overlap coefficient would flag
far too often to stay a useful manual-review signal (this project's `data_gen`/coverage species
lists already show 3+ staple species recurring across unrelated dev-panel teams, e.g. the Champions
panel's own dev/heldout roster in `config/eval/panels/panel_champions_v0.yaml`). Jaccard's
requirement that the UNION also stay small is what makes it track "these two teams are nearly the
same team," not "these two teams both used a popular Pokemon."

**Threshold semantics at `0.5`: inclusive (`>=`), not exclusive (`>`).** `find_near_duplicate_flags`
is a manual-review hint, never an automatic reject (DESIGN sec 3.3, and directly enforced by this
function raising nothing but `ValueError` on malformed input -- there is no "duplicate found"
exception). Given that, the asymmetry between the two choices is: `>=` at a borderline exact-0.5
case shows it to a human who can dismiss it in seconds; `>` at that same case hides it, and a
human never gets the chance to dismiss OR confirm it. For a diagnostic-only signal, the cost of a
false positive (one extra team a human glances at and clears) is far lower than the cost of a
false negative (a genuinely borderline pair never surfacing at all) -- so ties resolve toward
showing the flag.

- [ ] **Step 1: Write the failing tests**

```python
# showdown_bot/tests/test_near_duplicate.py
import pytest

from showdown_bot.eval.near_duplicate import (
    species_set, overlap_fraction, find_near_duplicate_flags,
    NearDuplicateFlag, NEAR_DUPLICATE_REVIEW_THRESHOLD,
)


def test_species_set_normalizes_case_and_punctuation():
    # Showdown's own toID rule (matches engine.state.to_id et al.): lowercase, strip everything
    # outside a-z0-9. "Landorus-Therian" and "landorus therian!!" must collapse to the same id,
    # so cosmetic spelling differences never cause a false NEGATIVE (a real duplicate missed
    # because of case/punctuation) -- but a genuine forme difference must NOT collapse, so a
    # false POSITIVE (two different Pokemon treated as the same) never happens either.
    assert species_set(["Landorus-Therian"]) == species_set(["landorus therian!!"])
    assert species_set(["Giratina"]) != species_set(["Giratina-Origin"])
    assert species_set(["Nidoran-M"]) != species_set(["Nidoran-F"])


def test_species_set_collapses_duplicate_entries():
    # Illegal under Showdown's own species clause for a real team, but this is a generic set
    # utility, not a team validator -- duplicate entries must not crash it or double-count.
    assert species_set(["Pikachu", "Pikachu", "Charizard"]) == species_set(["Pikachu", "Charizard"])


def test_species_set_rejects_empty_input():
    # Fail-closed: an empty list is not a valid team's species set (a real team always has 1-6
    # Pokemon). Silently returning frozenset() would let overlap_fraction treat "no data" as "0%
    # overlap with everything" -- a confidently wrong answer for what is actually missing data.
    with pytest.raises(ValueError, match="non-empty"):
        species_set([])


def test_overlap_fraction_is_jaccard_similarity():
    a = species_set(["A", "B", "C"])
    b = species_set(["A", "B", "D"])
    # intersection={A,B}=2, union={A,B,C,D}=4 -> 2/4, not the overlap-coefficient's 2/3.
    assert overlap_fraction(a, b) == pytest.approx(0.5)


def test_overlap_fraction_rejects_empty_sets():
    # Defense in depth, independent of species_set's own empty-input guard -- this function is
    # public and may be called directly, not only reached via species_set.
    with pytest.raises(ValueError, match="non-empty"):
        overlap_fraction(frozenset(), frozenset({"a"}))


def test_find_near_duplicate_flags_flags_identical_species_sets_of_different_team_ids():
    flags = find_near_duplicate_flags(
        candidate_team_id="holdout_0", candidate_species=["A", "B", "C"],
        reference_teams={"ref_1": ["A", "B", "C"]},
    )
    assert len(flags) == 1
    assert flags[0] == NearDuplicateFlag(
        candidate_team_id="holdout_0", reference_team_id="ref_1",
        overlap_fraction=1.0, shared_species=("a", "b", "c"),
    )


def test_find_near_duplicate_flags_never_flags_a_team_against_itself():
    # reference_teams intentionally includes the candidate's OWN team_id with IDENTICAL species
    # (which would score 1.0, the maximum possible overlap, if compared) -- it must never appear
    # in the result. This is defense in depth: Task 10 (§13) keeps the six holdout candidates and
    # the nine reference teams as two genuinely separate dicts precisely so this should never be
    # exercised in production, but this function does not trust that from the outside.
    flags = find_near_duplicate_flags(
        candidate_team_id="holdout_0", candidate_species=["A", "B", "C"],
        reference_teams={"holdout_0": ["A", "B", "C"], "ref_1": ["D", "E", "F"]},
    )
    assert flags == []  # ref_1 has zero overlap; holdout_0 (self) is excluded regardless of overlap


def test_find_near_duplicate_flags_does_not_flag_below_the_threshold():
    flags = find_near_duplicate_flags(
        candidate_team_id="holdout_0", candidate_species=["A", "B", "C"],
        reference_teams={"ref_1": ["A", "D", "E"]},  # intersection={A}=1, union=5 -> 0.2
    )
    assert flags == []


def test_find_near_duplicate_flags_flags_exactly_at_the_threshold():
    flags = find_near_duplicate_flags(
        candidate_team_id="holdout_0", candidate_species=["A", "B", "C"],
        reference_teams={"ref_1": ["A", "B", "D"]},  # intersection=2, union=4 -> exactly 0.5
    )
    assert len(flags) == 1
    assert flags[0].overlap_fraction == pytest.approx(NEAR_DUPLICATE_REVIEW_THRESHOLD)


def test_find_near_duplicate_flags_rejects_an_empty_reference_teams_mapping():
    with pytest.raises(ValueError, match="non-empty"):
        find_near_duplicate_flags(
            candidate_team_id="holdout_0", candidate_species=["A", "B", "C"], reference_teams={},
        )


def test_find_near_duplicate_flags_rejects_an_empty_candidate_team_id():
    with pytest.raises(ValueError, match="non-empty"):
        find_near_duplicate_flags(
            candidate_team_id="", candidate_species=["A", "B", "C"],
            reference_teams={"ref_1": ["A", "B", "C"]},
        )


def test_find_near_duplicate_flags_returns_a_deterministic_order():
    # reference_teams is a dict built in a DELIBERATELY non-alphabetical insertion order --
    # the returned flags must be sorted by reference_team_id regardless, not by whatever order
    # the caller happened to construct the mapping in.
    reference_teams = {
        "ref_z": ["A", "B", "D"], "ref_a": ["A", "B", "E"], "ref_m": ["A", "B", "F"],
    }
    flags = find_near_duplicate_flags(
        candidate_team_id="holdout_0", candidate_species=["A", "B", "C"],
        reference_teams=reference_teams,
    )
    assert [f.reference_team_id for f in flags] == ["ref_a", "ref_m", "ref_z"]


def test_find_near_duplicate_flags_never_raises_for_a_found_duplicate():
    # DESIGN sec 3.3: manual-review flag only, never an automatic reject. The only exception type
    # this whole module ever raises is ValueError, and only for malformed input (empty
    # species/mappings) -- finding a duplicate is a normal return, not an error path. This test
    # exists so a future change that turns a found flag into a raised exception fails loudly.
    flags = find_near_duplicate_flags(
        candidate_team_id="holdout_0", candidate_species=["A", "B", "C"],
        reference_teams={"ref_1": ["A", "B", "C"]},  # identical -- guaranteed to flag
    )
    assert len(flags) == 1  # returned normally; no exception escaped
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest showdown_bot/tests/test_near_duplicate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'showdown_bot.eval.near_duplicate'`

- [ ] **Step 3: Write the implementation**

```python
# showdown_bot/src/showdown_bot/eval/near_duplicate.py
"""Species-overlap near-duplicate flag (DESIGN sec 3.3): "a content-overlap check at sealing
flags any holdout team whose species set substantially overlaps a touched or coverage team for
manual disjointness review (near-duplicates are not independent)." Diagnostic ONLY -- a flag is
never an auto-reject; every flag this module can produce is a normal return value, never a raised
exception (the only exception type here is ValueError, and only for malformed input). Species
normalization matches this codebase's own established convention exactly: the same Showdown
`toID` transform already duplicated in `engine.state.to_id` / `engine.items.to_id` /
`engine.moves.to_id` and wrapped as `battle.opponent.SpeciesDex.to_id` -- lowercase, strip
everything outside a-z0-9, no forme merging (`Giratina` and `Giratina-Origin` stay distinct)."""
from __future__ import annotations

import re
from dataclasses import dataclass

NEAR_DUPLICATE_REVIEW_THRESHOLD = 0.5


def _to_id(name: str) -> str:
    """Same one-line rule as engine.state.to_id / engine.items.to_id / engine.moves.to_id /
    battle.opponent.SpeciesDex.to_id -- duplicated here rather than imported so this eval-side
    module has no dependency on engine/, matching how those three are already independent
    duplicates of the same rule rather than a single shared import site."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def species_set(species: list[str]) -> frozenset[str]:
    """Normalizes a raw list of species name strings into a canonical, hashable set. Duplicate
    entries collapse naturally via set construction (illegal under Showdown's own species clause
    for a real team, but this is a generic utility, not a team validator). Fails closed on an
    empty list -- a real team always has 1-6 Pokemon; silently returning frozenset() would let a
    later overlap computation treat "no data" as "0% overlap with everything," a confidently
    wrong answer for what is actually missing data."""
    if not species:
        raise ValueError("species must be non-empty -- an empty list is not a valid team")
    normalized = frozenset(_to_id(name) for name in species)
    if "" in normalized:
        raise ValueError(f"species contains a name that normalizes to the empty string: {species!r}")
    return normalized


def overlap_fraction(a: frozenset[str], b: frozenset[str]) -> float:
    """Jaccard similarity, |A intersect B| / |A union B| -- symmetric in a/b (this function does
    not itself distinguish "candidate" from "reference"; that framing exists only in
    find_near_duplicate_flags below). Chosen over the overlap coefficient
    (|A intersect B| / min(|A|, |B|)) because, for two 6-species teams, Jaccard >= 0.5 requires
    at least 4 of 6 species shared, while the overlap coefficient's >= 0.5 requires only 3 of 6 --
    ordinary shared-meta-staple overlap between unrelated competent teams, not a near-duplicate.
    Fails closed on empty input -- defense in depth independent of species_set's own guard, since
    this function is public and may be called directly."""
    if not a or not b:
        raise ValueError("overlap_fraction requires two non-empty sets")
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union


@dataclass(frozen=True)
class NearDuplicateFlag:
    candidate_team_id: str
    reference_team_id: str
    overlap_fraction: float
    shared_species: tuple[str, ...]


def find_near_duplicate_flags(
    *, candidate_team_id: str, candidate_species: list[str], reference_teams: dict[str, list[str]],
) -> list[NearDuplicateFlag]:
    """Compares ONE candidate team's species set against every team in reference_teams, flagging
    (never rejecting -- DESIGN sec 3.3, manual-review only) any reference team whose Jaccard
    overlap with the candidate is >= NEAR_DUPLICATE_REVIEW_THRESHOLD (inclusive: an exact-
    threshold case is exactly what a human should see, not what should silently pass because the
    bar is exclusive). candidate_team_id is skipped if it also appears in reference_teams -- a
    team must never be flagged against itself, independent of whatever a caller's own
    reference-set construction already guarantees (defense in depth: Task 10, §13, keeps the six
    holdout candidates and the nine reference teams as two genuinely separate dicts precisely so
    this should never trigger in practice, but this function does not trust that from the
    outside). Results are sorted by reference_team_id for a deterministic return order regardless
    of reference_teams' own dict construction order."""
    if not candidate_team_id:
        raise ValueError("candidate_team_id must be non-empty")
    if not reference_teams:
        raise ValueError("reference_teams must be non-empty -- an empty mapping makes this check vacuous")
    candidate_set = species_set(candidate_species)
    flags = []
    for reference_team_id in sorted(reference_teams):
        if reference_team_id == candidate_team_id:
            continue
        reference_set = species_set(reference_teams[reference_team_id])
        fraction = overlap_fraction(candidate_set, reference_set)
        if fraction >= NEAR_DUPLICATE_REVIEW_THRESHOLD:
            shared = tuple(sorted(candidate_set & reference_set))
            flags.append(NearDuplicateFlag(
                candidate_team_id=candidate_team_id, reference_team_id=reference_team_id,
                overlap_fraction=fraction, shared_species=shared,
            ))
    return flags
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest showdown_bot/tests/test_near_duplicate.py -v`
Expected: 13 passed

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/eval/near_duplicate.py showdown_bot/tests/test_near_duplicate.py
git commit -m "feat(champions): species-overlap near-duplicate review flag for holdout sealing"
```

## 8. Task 5 — Hash disjointness against frozen coverage (unchanged from Rev. 1)

No review finding targeted this task. Implement exactly as Rev. 1 specified: create
`showdown_bot/src/showdown_bot/eval/holdout_disjointness.py` and
`showdown_bot/tests/test_holdout_disjointness.py`, importing `COVERAGE_MANIFEST_PATH` from
`coverage_schedule.py`, `load_frozen_coverage_hashes` / `assert_disjoint_from_coverage` /
`HoldoutNotDisjointError` exactly as before. Same 3 RED/GREEN tests, same commit message
`"feat(champions): hash-disjointness check between holdout and frozen coverage teams"`.

---

## 9. Task 6 — Champions strength-holdout baseline manifest

> **SUPERSEDED by Amendment A1.3 (APPROVED) and its implementation. Read this box for the active
> contract; everything below the box is retained only as the historical Rev. 1–6 record and no
> longer prescribes execution.**
>
> **As implemented (Step 2 + its review-fix):** Gate B does **not** use the generic T6
> result-baseline contract. It has its OWN additive contract in `eval/baseline.py`:
> `load_strength_holdout_baseline(path) -> dict` and
> `verify_strength_holdout_baseline(baseline, *, repo_root, teams_root=None) -> list[BaselineCheck]`.
> The generic `load_baseline`/`verify_baseline`, `_REQUIRED_FIELDS`, and every Reg-I manifest are
> byte- and behaviour-unchanged.
>
> The specific manifest is a **closed static schema** of pre-run data only:
> `schema_version`, `baseline_id`, `hero_agent == "max_damage"`,
> `format_id == "gen9championsvgc2026regma"`, `panel_version`, `panel_hash`, the canonical
> `hero_team_path` (exactly `STRENGTH_HOLDOUT_HERO_TEAM_PATH`) + `hero_team_hash`, exactly six
> `opponent_teams` (each `{team_id, team_path == HOLDOUT_TEAMS_DIR+id+".txt", team_content_hash}`),
> the code-rebuilt `schedule_hash`, `seed_base`, `showdown_commit`, `server_patch_hash`, and
> `pythonhashseed == "0"`. It **rejects** any unknown field, so `reference_jsonl`,
> `reference_sha256`, `dev_schedule_path`, a caller `git_sha`, or a `candidate_identity` cannot
> appear — there is no result artifact and no YAML schedule.
>
> The verifier re-derives from the current checkout: panel hash; hero and six opponent content
> hashes; the **authoritative holdout manifest** at `STRENGTH_HOLDOUT_MANIFEST_PATH` (baseline,
> panel, on-disk and manifest projections must all agree); the rebuilt canonical 180-key schedule
> hash; and the server/seed/format/`pythonhashseed` pins. Any drift is a named `BaselineCheck`
> aggregated into `BaselineDriftError`. Load failures (missing/unreadable/non-UTF-8/broken JSON)
> raise `BaselineError`. `combine_strength_holdout_arms` calls only this pair and normalises both
> `BaselineError` and `BaselineDriftError` to `GateBAbort`; `run_strength_holdout_arm` refuses to
> play unless `PYTHONHASHSEED == "0"` and records it, and combine binds both arms' recorded value
> to the baseline. Files: `eval/baseline.py`,
> `showdown_bot/tests/test_baseline_strength_holdout.py`, `test_strength_holdout_runner.py`.
>
> **Baseline-manifest commit boundary (Rev. 25, immutability fix):** Task 6's scope is the
> **schema, loader, verifier and their tests** in `eval/baseline.py`. The baseline manifest file
> `config/eval/baselines/champions-strength-holdout-v0.json` is **NOT created here** — it is
> committed **once, with its final real values, in Task 13 step 3** (alongside the panel YAML and
> the hash freeze). A baseline manifest is immutable after its first commit
> (`test_baseline_manifest_git_immutability` — a change needs a new versioned file), so there is no
> placeholder-then-backfill: the file appears exactly once in history, already final. The holdout
> manifest (`champions_strength_holdout_v0_manifest.json`) likewise carries its real content from
> Task 13.

**Files (Task 6):**
- Modify: `showdown_bot/src/showdown_bot/eval/baseline.py` (schema, loader, verifier)
- Test: `showdown_bot/tests/test_baseline_strength_holdout.py`
- (The manifest JSON itself is committed once in Task 13 step 3 with final values — see the box above.)

_The historical Rev. 1–6 text below is retained for provenance; the box above is authoritative. In
particular, the placeholder manifest and its "back-fill later" note below are SUPERSEDED — the real
manifest is committed once in Task 13 step 3, never as an empty-field placeholder in Task 6._

**Fix vs. Rev. 1 (P1-8):** `load_baseline_manifest` never existed. The real functions are
`load_baseline(path) -> dict` (schema-only validation, raises `BaselineError`) and
`verify_baseline(baseline, *, repo_root, teams_root=None) -> list[BaselineCheck]` (drift-checking,
raises `BaselineDriftError`), both in `eval/baseline.py`, imported unchanged. The real required
schema is 16 fields (`_REQUIRED_FIELDS`), plus an all-or-nothing group of 5 `heldout_*` fields.

- [ ] **Step 1: Write the failing tests**

```python
# showdown_bot/tests/test_baseline_strength_holdout.py
import json

import pytest

from showdown_bot.eval.baseline import load_baseline, BaselineError

MANIFEST_PATH = "config/eval/baselines/champions-strength-holdout-v0.json"
_REQUIRED_FIELDS = frozenset({
    "baseline_id", "config_id", "config_hash", "git_sha", "panel_version", "panel_hash",
    "dev_schedule_hash", "dev_schedule_path", "hero_team_hash", "opp_team_hashes",
    "showdown_commit", "server_patch_hash", "seed_base", "pythonhashseed",
    "reference_jsonl", "reference_sha256",
})


def test_manifest_has_every_required_field():
    with open(MANIFEST_PATH, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    missing = _REQUIRED_FIELDS - set(data)
    assert not missing, f"manifest missing required fields: {sorted(missing)}"


def test_manifest_baseline_id_identifies_this_gate():
    baseline = load_baseline(MANIFEST_PATH)
    assert baseline["baseline_id"] == "champions-strength-holdout-v0"


def test_manifest_is_distinct_from_the_reg_i_manifest():
    with open(MANIFEST_PATH, "r", encoding="utf-8") as fh:
        holdout = json.load(fh)
    with open("config/eval/baselines/heuristic-v1.json", "r", encoding="utf-8") as fh:
        reg_i = json.load(fh)
    assert holdout != reg_i
    assert holdout["baseline_id"] != reg_i["baseline_id"]


def test_load_baseline_rejects_a_manifest_missing_a_required_field(tmp_path):
    incomplete = tmp_path / "incomplete.json"
    incomplete.write_text(json.dumps({"baseline_id": "x"}))
    with pytest.raises(BaselineError, match="missing required field"):
        load_baseline(str(incomplete))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest showdown_bot/tests/test_baseline_strength_holdout.py -v`
Expected: FAIL — `FileNotFoundError` (manifest doesn't exist yet)

- [ ] **Step 3: Write the implementation**

```json
{
  "baseline_id": "champions-strength-holdout-v0",
  "config_id": "heuristic",
  "config_hash": "",
  "git_sha": "",
  "panel_version": "strength-holdout-v0",
  "panel_hash": "",
  "dev_schedule_hash": "",
  "dev_schedule_path": "config/eval/panels/panel_champions_strength_holdout_v0.yaml",
  "hero_team_hash": "",
  "opp_team_hashes": {},
  "showdown_commit": "",
  "server_patch_hash": "",
  "seed_base": "champions-strength-holdout-v0",
  "pythonhashseed": "0",
  "reference_jsonl": "",
  "reference_sha256": ""
}
```

All empty-string/empty-dict fields are intentionally invalid placeholders — `load_baseline`'s
schema check only requires the **keys** to be present (it does not reject an empty string), so
this file is loadable now but every `verify_baseline` drift check against it will legitimately
fail until Task 13 back-fills real hashes from the real sealed teams, panel, and a real reference
dataset. That is correct fail-closed behavior, not a bug to silence.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest showdown_bot/tests/test_baseline_strength_holdout.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add config/eval/baselines/champions-strength-holdout-v0.json showdown_bot/tests/test_baseline_strength_holdout.py
git commit -m "feat(champions): new Champions strength-holdout baseline manifest (real baseline.py schema)"
```

---

## 10. Task 7 — Upstream verdict verification (gate-specific closed schemas)

**Files:**
- Create: `showdown_bot/src/showdown_bot/eval/strength_holdout_verdict.py` (this task: verification half)
- Test: `showdown_bot/tests/test_strength_holdout_verdict.py` (this task's tests)

**Fix vs. Rev. 1 (P1-2, P1-3):** one generic 5-field checker replaced by **two** gate-specific
checkers, each mirroring its real gate's full closed schema, counter invariants, canonical
schedule rebuild, and PASS invariant — I8-D's 25-field schema (`coverage_runner.py`'s own
I8-D-verdict block, 300-457, now ported in full) and Coverage's *different* 20-field schema
(`coverage_verdict.py`'s own report shape, per-cell floors, not a variant of I8-D's).
`config_hash`/`calc_backend` are no longer caller-trusted defaults — Task 9 derives them the same
way `resolve_coverage_provenance` does (dirty-tree fail-closed, real repo state), and passes the
derived values in here.

**Design note, stated not hidden:** this duplicates some structure with `coverage_runner.py`'s
inline I8-D-verdict block rather than extracting a shared helper from it. `coverage_runner.py`
already tolerates the identical kind of duplication against `i8d_runner.py` for provenance
resolution (confirmed in Rev. 2 research: *"this duplication is a candidate for factoring out,
not something I changed"*) — this plan follows that same established precedent rather than
refactoring already-shipped, already-merged Coverage code as a side effect of building Gate B.
Extracting a shared `eval/upstream_verdict.py` is a reasonable future cleanup, not done here.

**Fix vs. Rev. 3 (P1, §1c):** `schedule_hash` alone binds STRUCTURE (which teams/policies/seeds
are in the schedule), not necessarily team CONTENT. Both verifiers now additionally rebind
`hero_team_hash`/`opp_team_hashes` against the same freshly-rebuilt canonical schedule, mirroring
`coverage_runner.py:371-388`'s own I8-D-verdict check exactly — `_rebuild_i8d_schedule_hash`/
`_rebuild_coverage_schedule_hash` are renamed to `_rebuild_i8d_canonical_schedule`/
`_rebuild_coverage_canonical_schedule` and now return the whole schedule object (with `.rows`),
not just a hash string.

- [ ] **Step 1: Write the failing tests**

```python
# showdown_bot/tests/test_strength_holdout_verdict.py
import json
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from showdown_bot.eval.strength_holdout_verdict import (
    verify_i8d_verdict_artifact, verify_coverage_verdict_artifact, StrengthHoldoutRunError,
)
from showdown_bot.eval.i8d_runner import (
    I8D_MIN_ACTIVE_DECISIONS, I8D_MIN_DISTINCT_BATTLES, I8D_MAX_SCORED_DECISIONS,
    I8D_EXPECTED_PANEL_HASH, I8D_SEED_BASE,
)
from showdown_bot.eval.coverage_verdict import COVERAGE_CELLS, COVERAGE_CELL_FLOORS
from showdown_bot.eval.coverage_schedule import COVERAGE_EXPECTED_PANEL_HASH, COVERAGE_SEED_BASE

_IDENTITY = dict(candidate_identity="cand123", git_sha="deadbeef", config_hash="cfg456",
                 hero_agent="heuristic", calc_backend="oneshot")


def _fake_canonical_schedule(schedule_hash, hero_team_hash, opp_team_hashes):
    # Minimal stand-in for build_i8d_canonical_schedule/build_coverage_live_schedule's real
    # return type -- only the .schedule_hash and .rows[*].hero_team_hash/.opp_team_hash
    # attributes verify_*_verdict_artifact actually reads.
    rows = [SimpleNamespace(hero_team_hash=hero_team_hash, opp_team_hash=h) for h in opp_team_hashes]
    return SimpleNamespace(schedule_hash=schedule_hash, rows=rows)


def _valid_i8d_verdict(**overrides):
    data = {
        "candidate_identity": "cand123", "git_sha": "deadbeef", "config_hash": "cfg456",
        "hero_agent": "heuristic", "calc_backend": "oneshot",
        "panel_hash": I8D_EXPECTED_PANEL_HASH, "seed_base": I8D_SEED_BASE,
        "seed_log_verified": True, "battles_played": 45, "scored_decisions": 60,
        "scored_overshoot": 0, "active_valid_decisions": 60, "distinct_active_battles": 45,
        "min_active_decisions": I8D_MIN_ACTIVE_DECISIONS,
        "min_distinct_battles": I8D_MIN_DISTINCT_BATTLES,
        "max_scored_decisions": I8D_MAX_SCORED_DECISIONS, "budget_ms": 1000,
        "schedule_hash": "FRESH_SCHEDULE_HASH", "hero_team_hash": "hhash", "opp_team_hashes": ["ohash"],
        "verdict": "PASS", "p95_is_gate_value": True, "exposure_floor_met": True,
        "stop_reason": "exposure_floor_met", "p95_ms": 850.0,
    }
    data.update(overrides)
    return data


def _patch_i8d_canonical_schedule(monkeypatch, **overrides):
    kwargs = dict(schedule_hash="FRESH_SCHEDULE_HASH", hero_team_hash="hhash", opp_team_hashes=["ohash"])
    kwargs.update(overrides)
    monkeypatch.setattr(
        "showdown_bot.eval.strength_holdout_verdict._rebuild_i8d_canonical_schedule",
        lambda teams_root: _fake_canonical_schedule(**kwargs),
    )


def test_verify_i8d_verdict_accepts_a_matching_genuine_pass(tmp_path, monkeypatch):
    _patch_i8d_canonical_schedule(monkeypatch)
    p = tmp_path / "i8d.json"
    p.write_text(json.dumps(_valid_i8d_verdict()))
    result = verify_i8d_verdict_artifact(verdict_path=str(p), teams_root=".", **_IDENTITY)
    assert result["verdict"] == "PASS"


def test_verify_i8d_verdict_rejects_a_hero_team_hash_mismatch(tmp_path, monkeypatch):
    _patch_i8d_canonical_schedule(monkeypatch, hero_team_hash="DIFFERENT_HASH")
    p = tmp_path / "i8d.json"
    p.write_text(json.dumps(_valid_i8d_verdict()))
    with pytest.raises(StrengthHoldoutRunError, match="hero_team_hash"):
        verify_i8d_verdict_artifact(verdict_path=str(p), teams_root=".", **_IDENTITY)


def test_verify_i8d_verdict_rejects_an_opp_team_hashes_mismatch(tmp_path, monkeypatch):
    _patch_i8d_canonical_schedule(monkeypatch, opp_team_hashes=["a_completely_different_hash"])
    p = tmp_path / "i8d.json"
    p.write_text(json.dumps(_valid_i8d_verdict()))
    with pytest.raises(StrengthHoldoutRunError, match="opp_team_hashes"):
        verify_i8d_verdict_artifact(verdict_path=str(p), teams_root=".", **_IDENTITY)


def test_verify_i8d_verdict_rejects_truncated_json_cleanly_not_a_raw_jsondecodeerror(tmp_path):
    # SF2 fix (Rev. 8, self-found during the boundary-scoped exception audit -- §1g): a verdict
    # file that exists but contains truncated/corrupted JSON (e.g. an upstream gate crashed
    # mid-write) must abort as StrengthHoldoutRunError -- and therefore, via NF2's existing wrap,
    # as GateBAbort out of combine_strength_holdout_arms -- not escape as a raw
    # json.JSONDecodeError. Same failure family as SF1 (Rev. 7)'s _read_arm gap.
    p = tmp_path / "i8d.json"
    p.write_text("{not valid json")
    with pytest.raises(StrengthHoldoutRunError, match="not valid JSON"):
        verify_i8d_verdict_artifact(verdict_path=str(p), teams_root=".", **_IDENTITY)


def test_verify_i8d_verdict_rejects_a_non_dict_json_body(tmp_path):
    p = tmp_path / "i8d.json"
    p.write_text("[]")
    with pytest.raises(StrengthHoldoutRunError, match="JSON object"):
        verify_i8d_verdict_artifact(verdict_path=str(p), teams_root=".", **_IDENTITY)


def test_verify_i8d_verdict_rejects_extra_fields_not_in_the_real_schema(tmp_path):
    p = tmp_path / "i8d.json"
    p.write_text(json.dumps({**_valid_i8d_verdict(), "totally_extra_field": 1}))
    with pytest.raises(StrengthHoldoutRunError, match="extra"):
        verify_i8d_verdict_artifact(verdict_path=str(p), teams_root=".", **_IDENTITY)


def test_verify_i8d_verdict_rejects_missing_fields(tmp_path):
    data = _valid_i8d_verdict()
    del data["p95_ms"]
    p = tmp_path / "i8d.json"
    p.write_text(json.dumps(data))
    with pytest.raises(StrengthHoldoutRunError, match="missing"):
        verify_i8d_verdict_artifact(verdict_path=str(p), teams_root=".", **_IDENTITY)


def test_verify_i8d_verdict_rejects_a_scored_overshoot_that_does_not_match_the_formula(tmp_path):
    p = tmp_path / "i8d.json"
    p.write_text(json.dumps(_valid_i8d_verdict(scored_overshoot=999)))
    with pytest.raises(StrengthHoldoutRunError, match="scored_overshoot"):
        verify_i8d_verdict_artifact(verdict_path=str(p), teams_root=".", **_IDENTITY)


def test_verify_i8d_verdict_rejects_a_nan_p95_ms_even_though_nan_compares_false_to_everything(tmp_path, monkeypatch):
    _patch_i8d_canonical_schedule(monkeypatch)
    p = tmp_path / "i8d.json"
    p.write_text(json.dumps(_valid_i8d_verdict(p95_ms=float("nan"))))
    with pytest.raises(StrengthHoldoutRunError, match="p95_ms"):
        verify_i8d_verdict_artifact(verdict_path=str(p), teams_root=".", **_IDENTITY)


def test_verify_i8d_verdict_rejects_exposure_floor_met_true_without_the_counters_to_back_it(tmp_path, monkeypatch):
    _patch_i8d_canonical_schedule(monkeypatch)
    p = tmp_path / "i8d.json"
    p.write_text(json.dumps(_valid_i8d_verdict(active_valid_decisions=1)))  # below min_active_decisions
    with pytest.raises(StrengthHoldoutRunError, match="active_valid_decisions"):
        verify_i8d_verdict_artifact(verdict_path=str(p), teams_root=".", **_IDENTITY)


@pytest.mark.parametrize("field,wrong", [
    ("git_sha", "wrong"), ("config_hash", "wrong"), ("hero_agent", "max_damage"),
    ("calc_backend", "persistent"), ("candidate_identity", "wrong"),
])
def test_verify_i8d_verdict_rejects_each_identity_field_individually(tmp_path, field, wrong):
    p = tmp_path / "i8d.json"
    p.write_text(json.dumps(_valid_i8d_verdict(**{field: wrong})))
    with pytest.raises(StrengthHoldoutRunError, match=field):
        verify_i8d_verdict_artifact(verdict_path=str(p), teams_root=".", **_IDENTITY)


def _valid_coverage_verdict(**overrides):
    cell_counts = {cell: {"decisions": floor[0], "distinct_battles": floor[1]}
                   for cell, floor in COVERAGE_CELL_FLOORS.items()}
    data = {
        "schedule_hash": "FRESH_COVERAGE_SCHEDULE_HASH", "panel_hash": COVERAGE_EXPECTED_PANEL_HASH,
        "candidate_identity": "cand123", "git_sha": "deadbeef", "config_hash": "cfg456",
        "calc_backend": "oneshot", "hero_agent": "heuristic", "hero_team_hash": "hhash",
        "opp_team_hashes": ["ohash"], "seed_base": COVERAGE_SEED_BASE, "seed_log_verified": True,
        "battles_played": 60, "scored_decisions": 90, "max_scored_decisions": 2000,
        "cell_floors": {cell: list(floor) for cell, floor in COVERAGE_CELL_FLOORS.items()},
        "cell_counts": cell_counts, "safety_violations": 0, "schedule_complete": True,
        "verdict": "PASS", "stop_reason": "coverage_floor_met",
    }
    data.update(overrides)
    return data


def _patch_coverage_canonical_schedule(monkeypatch, **overrides):
    kwargs = dict(schedule_hash="FRESH_COVERAGE_SCHEDULE_HASH", hero_team_hash="hhash", opp_team_hashes=["ohash"])
    kwargs.update(overrides)
    monkeypatch.setattr(
        "showdown_bot.eval.strength_holdout_verdict._rebuild_coverage_canonical_schedule",
        lambda teams_root: _fake_canonical_schedule(**kwargs),
    )


def test_verify_coverage_verdict_accepts_a_matching_genuine_pass(tmp_path, monkeypatch):
    _patch_coverage_canonical_schedule(monkeypatch)
    p = tmp_path / "cov.json"
    p.write_text(json.dumps(_valid_coverage_verdict()))
    result = verify_coverage_verdict_artifact(verdict_path=str(p), teams_root=".", **_IDENTITY)
    assert result["verdict"] == "PASS"


def test_verify_coverage_verdict_rejects_a_hero_team_hash_mismatch(tmp_path, monkeypatch):
    _patch_coverage_canonical_schedule(monkeypatch, hero_team_hash="DIFFERENT_HASH")
    p = tmp_path / "cov.json"
    p.write_text(json.dumps(_valid_coverage_verdict()))
    with pytest.raises(StrengthHoldoutRunError, match="hero_team_hash"):
        verify_coverage_verdict_artifact(verdict_path=str(p), teams_root=".", **_IDENTITY)


def test_verify_coverage_verdict_rejects_an_opp_team_hashes_mismatch(tmp_path, monkeypatch):
    _patch_coverage_canonical_schedule(monkeypatch, opp_team_hashes=["a_completely_different_hash"])
    p = tmp_path / "cov.json"
    p.write_text(json.dumps(_valid_coverage_verdict()))
    with pytest.raises(StrengthHoldoutRunError, match="opp_team_hashes"):
        verify_coverage_verdict_artifact(verdict_path=str(p), teams_root=".", **_IDENTITY)


def test_verify_coverage_verdict_rejects_a_cell_below_its_own_floor(tmp_path, monkeypatch):
    _patch_coverage_canonical_schedule(monkeypatch)
    data = _valid_coverage_verdict()
    data["cell_counts"]["both_foe_slots"] = {"decisions": 0, "distinct_battles": 0}
    p = tmp_path / "cov.json"
    p.write_text(json.dumps(data))
    with pytest.raises(StrengthHoldoutRunError, match="both_foe_slots"):
        verify_coverage_verdict_artifact(verdict_path=str(p), teams_root=".", **_IDENTITY)


def test_verify_coverage_verdict_rejects_a_nonzero_safety_violations_claiming_pass(tmp_path, monkeypatch):
    _patch_coverage_canonical_schedule(monkeypatch)
    p = tmp_path / "cov.json"
    p.write_text(json.dumps(_valid_coverage_verdict(safety_violations=1)))
    with pytest.raises(StrengthHoldoutRunError, match="safety_violations"):
        verify_coverage_verdict_artifact(verdict_path=str(p), teams_root=".", **_IDENTITY)


def test_verify_coverage_verdict_rejects_stop_reason_not_matching_verdict(tmp_path, monkeypatch):
    _patch_coverage_canonical_schedule(monkeypatch)
    p = tmp_path / "cov.json"
    p.write_text(json.dumps(_valid_coverage_verdict(stop_reason="schedule_exhausted")))
    with pytest.raises(StrengthHoldoutRunError, match="stop_reason"):
        verify_coverage_verdict_artifact(verdict_path=str(p), teams_root=".", **_IDENTITY)


def test_verify_coverage_verdict_uses_its_own_pinned_constants_not_i8d_s(tmp_path):
    # Coverage's panel_hash/seed_base are DIFFERENT constants from I8-D's -- a mixed-up check
    # that accidentally compared against I8D_EXPECTED_PANEL_HASH would wrongly reject this.
    p = tmp_path / "cov.json"
    p.write_text(json.dumps(_valid_coverage_verdict()))
    assert COVERAGE_EXPECTED_PANEL_HASH != I8D_EXPECTED_PANEL_HASH  # sanity: the two are distinct
    assert COVERAGE_SEED_BASE != I8D_SEED_BASE
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest showdown_bot/tests/test_strength_holdout_verdict.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# showdown_bot/src/showdown_bot/eval/strength_holdout_verdict.py
"""Gate B upstream verdict verification + McNemar wiring.

Two gate-specific closed-schema verifiers (I8-D, Coverage) -- NOT one generic 5-field check
(Rev. 1's bug). Each mirrors its real gate's full check block in coverage_runner.py (which today
only checks I8-D; Gate B needs the analogous block for Coverage too, since Gate B depends on
BOTH). Never trusts an opaque candidate_identity alone -- every raw field is bound to THIS run's
own freshly-derived provenance, and both schedule_hash fields are bound to a freshly-rebuilt
canonical schedule, never the artifact's own claim.
"""
from __future__ import annotations

import json
import math
import os


class StrengthHoldoutRunError(Exception):
    pass


def _load_verdict_dict(verdict_path: str, gate_name: str) -> dict:
    if not verdict_path or not os.path.isfile(verdict_path):
        raise StrengthHoldoutRunError(f"{gate_name} verdict path missing or not a file: {verdict_path!r}")
    # SF2 fix (Rev. 8, self-found during the boundary-scoped exception audit -- §1g): a verdict
    # file that exists but is truncated/corrupted (e.g. an upstream gate crashed mid-write) makes
    # json.load raise json.JSONDecodeError -- not StrengthHoldoutRunError, so it escaped this
    # function, verify_i8d_verdict_artifact/verify_coverage_verdict_artifact, and even
    # combine_strength_holdout_arms's own NF2 fix (which only catches StrengthHoldoutRunError).
    # A TOCTOU race between the isfile() check above and open() below (or a permissions change)
    # raises OSError, equally unguarded. Same failure family as SF1 (Rev. 7)'s _read_arm gap,
    # same fix shape -- and staying inside THIS module's own established exception contract means
    # NF2's existing try/except in combine_strength_holdout_arms needs no further change at all.
    try:
        with open(verdict_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, UnicodeDecodeError) as exc:
        raise StrengthHoldoutRunError(f"cannot read {gate_name} verdict at {verdict_path!r}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise StrengthHoldoutRunError(f"{gate_name} verdict at {verdict_path!r} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise StrengthHoldoutRunError(f"{gate_name} verdict at {verdict_path!r} is not a JSON object")
    return data


def _check_exact_field_set(data: dict, required: frozenset, gate_name: str) -> None:
    actual = set(data)
    missing = required - actual
    extra = actual - required
    if missing:
        raise StrengthHoldoutRunError(f"{gate_name} verdict missing field(s): {sorted(missing)}")
    if extra:
        raise StrengthHoldoutRunError(f"{gate_name} verdict has extra, unexpected field(s): {sorted(extra)}")


def _check_identity_fields(data: dict, gate_name: str, *, candidate_identity, git_sha,
                            config_hash, hero_agent, calc_backend) -> None:
    expected = {"git_sha": git_sha, "config_hash": config_hash, "hero_agent": hero_agent,
                "calc_backend": calc_backend, "candidate_identity": candidate_identity}
    for field, want in expected.items():
        if data.get(field) != want:
            raise StrengthHoldoutRunError(
                f"{gate_name} verdict {field}={data.get(field)!r} != this run's {field}={want!r}: "
                f"holdout must run on the SAME candidate {gate_name} verified"
            )


def _rebuild_i8d_canonical_schedule(teams_root: str):
    # Rev. 4 fix: returns the whole schedule object (not just .schedule_hash) -- the caller
    # also needs .rows to independently rebind hero_team_hash/opp_team_hashes, exactly like
    # coverage_runner.py:371-388 does for its own I8-D-verdict check.
    from showdown_bot.eval.i8d_runner import build_i8d_canonical_schedule
    return build_i8d_canonical_schedule(teams_root=teams_root)


_I8D_VERDICT_REQUIRED_FIELDS = frozenset({
    "candidate_identity", "git_sha", "config_hash", "hero_agent", "calc_backend",
    "panel_hash", "seed_base", "seed_log_verified", "battles_played", "scored_decisions",
    "scored_overshoot", "active_valid_decisions", "distinct_active_battles",
    "min_active_decisions", "min_distinct_battles", "max_scored_decisions", "budget_ms",
    "schedule_hash", "hero_team_hash", "opp_team_hashes", "verdict", "p95_is_gate_value",
    "exposure_floor_met", "stop_reason", "p95_ms",
})


def verify_i8d_verdict_artifact(
    *, verdict_path: str, teams_root: str, candidate_identity: str, git_sha: str,
    config_hash: str, hero_agent: str, calc_backend: str,
) -> dict:
    """Full closed-schema verification of an I8-D verdict.json, mirroring coverage_runner.py's
    own I8-D-verdict block (300-457) check-for-check."""
    from showdown_bot.eval.i8d_runner import (
        I8D_MIN_ACTIVE_DECISIONS, I8D_MIN_DISTINCT_BATTLES, I8D_MAX_SCORED_DECISIONS,
        I8D_EXPECTED_PANEL_HASH, I8D_SEED_BASE,
    )
    from showdown_bot.eval.gates import load_latency_budget_ms

    data = _load_verdict_dict(verdict_path, "I8-D")
    _check_exact_field_set(data, _I8D_VERDICT_REQUIRED_FIELDS, "I8-D")

    for field in ("battles_played", "scored_decisions", "scored_overshoot",
                  "active_valid_decisions", "distinct_active_battles"):
        v = data[field]
        if isinstance(v, bool) or not isinstance(v, int) or v < 0:
            raise StrengthHoldoutRunError(f"I8-D verdict field {field!r}={v!r} must be a non-negative int")

    expected_overshoot = max(0, data["scored_decisions"] - I8D_MAX_SCORED_DECISIONS)
    if data["scored_overshoot"] != expected_overshoot:
        raise StrengthHoldoutRunError(
            f"I8-D verdict scored_overshoot={data['scored_overshoot']!r} != "
            f"max(0, scored_decisions - max_scored_decisions)={expected_overshoot!r}"
        )
    if data["active_valid_decisions"] > data["scored_decisions"]:
        raise StrengthHoldoutRunError("I8-D verdict active_valid_decisions > scored_decisions")
    if data["distinct_active_battles"] > data["battles_played"]:
        raise StrengthHoldoutRunError("I8-D verdict distinct_active_battles > battles_played")

    if data["panel_hash"] != I8D_EXPECTED_PANEL_HASH:
        raise StrengthHoldoutRunError("I8-D verdict panel_hash does not match the pinned I8-D panel")
    if data["seed_base"] != I8D_SEED_BASE:
        raise StrengthHoldoutRunError("I8-D verdict seed_base does not match the pinned I8-D seed namespace")
    if data["seed_log_verified"] is not True:
        raise StrengthHoldoutRunError("I8-D verdict seed_log_verified is not True")

    budget_ms = load_latency_budget_ms()
    for field, expected in (
        ("min_active_decisions", I8D_MIN_ACTIVE_DECISIONS),
        ("min_distinct_battles", I8D_MIN_DISTINCT_BATTLES),
        ("max_scored_decisions", I8D_MAX_SCORED_DECISIONS), ("budget_ms", budget_ms),
    ):
        if data[field] != expected:
            raise StrengthHoldoutRunError(f"I8-D verdict {field}={data[field]!r} != pinned {expected!r}")

    _check_identity_fields(data, "I8-D", candidate_identity=candidate_identity, git_sha=git_sha,
                            config_hash=config_hash, hero_agent=hero_agent, calc_backend=calc_backend)

    fresh_schedule = _rebuild_i8d_canonical_schedule(teams_root)
    if data["schedule_hash"] != fresh_schedule.schedule_hash:
        raise StrengthHoldoutRunError("I8-D verdict schedule_hash does not match a freshly-rebuilt canonical schedule")
    # Rev. 4 fix: schedule_hash alone binds STRUCTURE (which teams/policies/seeds), not
    # necessarily team CONTENT -- bind hero_team_hash/opp_team_hashes independently too,
    # mirroring coverage_runner.py:371-388's own I8-D-verdict check exactly.
    fresh_hero_team_hash = fresh_schedule.rows[0].hero_team_hash if fresh_schedule.rows else None
    if data["hero_team_hash"] != fresh_hero_team_hash:
        raise StrengthHoldoutRunError("I8-D verdict hero_team_hash does not match the freshly-rebuilt canonical schedule")
    fresh_opp_team_hashes = sorted({r.opp_team_hash for r in fresh_schedule.rows if r.opp_team_hash is not None})
    if sorted(data["opp_team_hashes"]) != fresh_opp_team_hashes:
        raise StrengthHoldoutRunError("I8-D verdict opp_team_hashes does not match the freshly-rebuilt canonical schedule")

    if data["verdict"] != "PASS":
        raise StrengthHoldoutRunError(f"I8-D verdict is {data['verdict']!r}, not PASS")
    if data["p95_is_gate_value"] is not True:
        raise StrengthHoldoutRunError("I8-D verdict p95_is_gate_value is not True on a claimed PASS")
    if data["exposure_floor_met"] is not True:
        raise StrengthHoldoutRunError("I8-D verdict exposure_floor_met is not True on a claimed PASS")
    if (data["active_valid_decisions"] < data["min_active_decisions"]
            or data["distinct_active_battles"] < data["min_distinct_battles"]):
        raise StrengthHoldoutRunError(
            "I8-D verdict claims exposure_floor_met=True but active_valid_decisions/"
            "distinct_active_battles do not actually clear the pinned floor"
        )
    if data["stop_reason"] != "exposure_floor_met":
        raise StrengthHoldoutRunError(f"I8-D verdict stop_reason={data['stop_reason']!r} != 'exposure_floor_met' on a PASS")

    p95_ms = data["p95_ms"]
    # NaN-safe: a bare `p95_ms > budget_ms` is False for NaN under IEEE 754 and would silently
    # accept a forged NaN. This closed-range form rejects it because `0 <= NaN` is already False.
    if not (isinstance(p95_ms, (int, float)) and not math.isnan(p95_ms) and 0 <= p95_ms <= budget_ms):
        raise StrengthHoldoutRunError(f"I8-D verdict p95_ms={p95_ms!r} is not a finite value in [0, {budget_ms}]")

    return data


def _rebuild_coverage_canonical_schedule(teams_root: str):
    from showdown_bot.eval.coverage_runner import build_coverage_live_schedule
    return build_coverage_live_schedule(teams_root=teams_root)


_COVERAGE_VERDICT_REQUIRED_FIELDS = frozenset({
    "schedule_hash", "panel_hash", "candidate_identity", "git_sha", "config_hash",
    "calc_backend", "hero_agent", "hero_team_hash", "opp_team_hashes", "seed_base",
    "seed_log_verified", "battles_played", "scored_decisions", "max_scored_decisions",
    "cell_floors", "cell_counts", "safety_violations", "schedule_complete", "verdict",
    "stop_reason",
})


def verify_coverage_verdict_artifact(
    *, verdict_path: str, teams_root: str, candidate_identity: str, git_sha: str,
    config_hash: str, hero_agent: str, calc_backend: str,
) -> dict:
    """Full closed-schema verification of a Coverage verdict.json -- Coverage's OWN 20-field
    schema (coverage_verdict.py), with its own per-cell floors, not a reuse of I8-D's shape."""
    from showdown_bot.eval.coverage_verdict import COVERAGE_CELLS, COVERAGE_CELL_FLOORS
    from showdown_bot.eval.coverage_schedule import COVERAGE_EXPECTED_PANEL_HASH, COVERAGE_SEED_BASE

    data = _load_verdict_dict(verdict_path, "Coverage")
    _check_exact_field_set(data, _COVERAGE_VERDICT_REQUIRED_FIELDS, "Coverage")

    for field in ("battles_played", "scored_decisions"):
        v = data[field]
        if isinstance(v, bool) or not isinstance(v, int) or v < 0:
            raise StrengthHoldoutRunError(f"Coverage verdict field {field!r}={v!r} must be a non-negative int")
    if data["max_scored_decisions"] <= 0:
        raise StrengthHoldoutRunError("Coverage verdict max_scored_decisions must be positive")

    if data["panel_hash"] != COVERAGE_EXPECTED_PANEL_HASH:
        raise StrengthHoldoutRunError("Coverage verdict panel_hash does not match the pinned coverage panel")
    if data["seed_base"] != COVERAGE_SEED_BASE:
        raise StrengthHoldoutRunError("Coverage verdict seed_base does not match the pinned coverage seed namespace")
    if data["seed_log_verified"] is not True:
        raise StrengthHoldoutRunError("Coverage verdict seed_log_verified is not True")

    if dict(data["cell_floors"]) != {cell: list(floor) for cell, floor in COVERAGE_CELL_FLOORS.items()}:
        raise StrengthHoldoutRunError("Coverage verdict cell_floors do not match the pinned coverage floors")

    _check_identity_fields(data, "Coverage", candidate_identity=candidate_identity, git_sha=git_sha,
                            config_hash=config_hash, hero_agent=hero_agent, calc_backend=calc_backend)

    fresh_schedule = _rebuild_coverage_canonical_schedule(teams_root)
    if data["schedule_hash"] != fresh_schedule.schedule_hash:
        raise StrengthHoldoutRunError("Coverage verdict schedule_hash does not match a freshly-rebuilt canonical schedule")
    fresh_hero_team_hash = fresh_schedule.rows[0].hero_team_hash if fresh_schedule.rows else None
    if data["hero_team_hash"] != fresh_hero_team_hash:
        raise StrengthHoldoutRunError("Coverage verdict hero_team_hash does not match the freshly-rebuilt canonical schedule")
    fresh_opp_team_hashes = sorted({r.opp_team_hash for r in fresh_schedule.rows if r.opp_team_hash is not None})
    if sorted(data["opp_team_hashes"]) != fresh_opp_team_hashes:
        raise StrengthHoldoutRunError("Coverage verdict opp_team_hashes does not match the freshly-rebuilt canonical schedule")

    if data["verdict"] != "PASS":
        raise StrengthHoldoutRunError(f"Coverage verdict is {data['verdict']!r}, not PASS")
    if data["safety_violations"] != 0:
        raise StrengthHoldoutRunError(f"Coverage verdict claims PASS but safety_violations={data['safety_violations']!r} != 0")
    if data["stop_reason"] != "coverage_floor_met":
        raise StrengthHoldoutRunError(f"Coverage verdict stop_reason={data['stop_reason']!r} != 'coverage_floor_met' on a PASS")

    for cell in COVERAGE_CELLS:
        floor_decisions, floor_battles = COVERAGE_CELL_FLOORS[cell]
        counts = data["cell_counts"].get(cell, {})
        if counts.get("decisions", 0) < floor_decisions or counts.get("distinct_battles", 0) < floor_battles:
            raise StrengthHoldoutRunError(
                f"Coverage verdict claims PASS but cell {cell!r} does not clear its own floor "
                f"(need >= {floor_decisions} decisions / {floor_battles} distinct battles, "
                f"got {counts})"
            )

    return data
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest showdown_bot/tests/test_strength_holdout_verdict.py -v`
Expected: 21 passed (16 from Rev. 1 + 4 hero_team_hash/opp_team_hashes-binding tests, Rev. 4 + 1
new truncated-JSON test, Rev. 8).
**If any pinned constant (`I8D_MIN_ACTIVE_DECISIONS` etc.) fails to import
or has drifted from the values used above**, that is the RED signal working correctly — update
this task's fixtures to match the real current values, never the other way around.

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/eval/strength_holdout_verdict.py showdown_bot/tests/test_strength_holdout_verdict.py
git commit -m "feat(champions): full closed-schema verification for the I8-D and Coverage upstream verdicts"
```

---

## 11. Task 8 — McNemar verdict rendering via the real, unmodified `report.py` pipeline

**Files:**
- Modify: `showdown_bot/src/showdown_bot/eval/strength_holdout_verdict.py`
- Modify: `showdown_bot/tests/test_strength_holdout_verdict.py`

**Fix vs. Rev. 1 (P1-1):** `render_strength_holdout_verdict` now calls the real
`_build_cells`/`_find_cell_flips`/`_strength_delta`/`_paired_verdict` from `eval/report.py`
directly — confirmed fully generic over `(opp_policy, opp_team_hash)` cells, no report.py change
needed. `safety_pass` is computed from real `invalid_choices`/`crashes`/`end_reason` counts
across both arms' rows (a narrow, Gate-B-specific mirror of `run_safety_gates`'s core fields —
not the full `RunBundle`-based safety table, which needs machinery Gate B's simpler
two-row-list shape doesn't produce; this is disclosed, not silently narrower).

- [ ] **Step 1: Write the failing tests**

```python
# append to showdown_bot/tests/test_strength_holdout_verdict.py
from showdown_bot.eval.strength_holdout_verdict import render_strength_holdout_verdict, compute_safety_pass
from showdown_bot.eval.pairing import Pair


def _row(config_hash, seed_index, opp_policy, opp_team_hash, winner, invalid_choices=0, crashes=0, end_reason="normal"):
    return {
        "battle_id": f"b{seed_index}", "run_id": "r", "config_id": config_hash, "format_id": "gen9championsvgc2026regma",
        "config_hash": config_hash, "schedule_hash": "sched1", "seed_index": seed_index,
        "opp_policy": opp_policy, "hero_team_path": "hero.txt", "opp_team_path": "opp.txt",
        "seed": seed_index, "seed_base": "champions-strength-holdout-v0", "winner": winner,
        "turns": 5, "invalid_choices": invalid_choices, "crashes": crashes,
        "decision_latency_p95_ms": 10.0, "git_sha": "deadbeef", "dirty": False, "end_reason": end_reason,
        "opp_team_hash": opp_team_hash,
    }


def _pair(a_win, b_win, seed_index, opp_policy="heuristic", opp_team_hash="t1"):
    row_a = _row("cfgA", seed_index, opp_policy, opp_team_hash, "hero" if a_win else "villain")
    row_b = _row("cfgB", seed_index, opp_policy, opp_team_hash, "hero" if b_win else "villain")
    return Pair(battle_id=row_a["battle_id"], seed_index=seed_index, cell=(opp_policy, opp_team_hash),
                hero_win_a=a_win, hero_win_b=b_win, row_a=row_a, row_b=row_b)


def test_render_verdict_underpowered_below_ten_discordant_pairs():
    pairs = [_pair(True, False, i) for i in range(5)] + [_pair(True, True, i) for i in range(5, 10)]
    verdict = render_strength_holdout_verdict(pairs, safety_pass=True)
    assert verdict.verdict == "UNDERPOWERED"


def test_render_verdict_go_with_enough_uniform_positive_evidence():
    pairs = [_pair(True, False, i) for i in range(12)]
    verdict = render_strength_holdout_verdict(pairs, safety_pass=True)
    assert verdict.verdict == "GO"


def test_render_verdict_safety_fail_regardless_of_pair_evidence():
    pairs = [_pair(True, False, i) for i in range(12)]
    verdict = render_strength_holdout_verdict(pairs, safety_pass=False)
    assert verdict.verdict == "SAFETY-FAIL"


def test_render_verdict_catches_a_losing_cell_flip_even_with_a_winning_overall_delta():
    # Overall: 10 discordant pairs, A wins 8, loses 2 -- looks like a strong positive delta.
    # But ALL of A's wins are against cell (heuristic, t1), and A LOSES every pair against
    # cell (max_damage, t2) where B was winning -- a real cell-flip regression Rev. 1's
    # cell_flips=[] could never have detected.
    winning_cell_pairs = [_pair(True, False, i, opp_policy="heuristic", opp_team_hash="t1") for i in range(8)]
    flipped_cell_pairs = [_pair(False, True, i, opp_policy="max_damage", opp_team_hash="t2") for i in range(8, 10)]
    pairs = winning_cell_pairs + flipped_cell_pairs
    verdict = render_strength_holdout_verdict(pairs, safety_pass=True)
    assert verdict.verdict == "NO-GO"
    assert any("flip" in r for r in verdict.reasons)


def test_compute_safety_pass_true_when_both_arms_clean():
    rows_a = [_row("cfgA", i, "heuristic", "t1", "hero") for i in range(3)]
    rows_b = [_row("cfgB", i, "heuristic", "t1", "villain") for i in range(3)]
    assert compute_safety_pass(rows_a, rows_b) is True


def test_compute_safety_pass_false_on_any_invalid_choice():
    rows_a = [_row("cfgA", 0, "heuristic", "t1", "hero", invalid_choices=1)]
    rows_b = [_row("cfgB", 0, "heuristic", "t1", "villain")]
    assert compute_safety_pass(rows_a, rows_b) is False


def test_compute_safety_pass_false_on_any_crash():
    rows_a = [_row("cfgA", 0, "heuristic", "t1", "hero")]
    rows_b = [_row("cfgB", 0, "heuristic", "t1", "villain", crashes=1)]
    assert compute_safety_pass(rows_a, rows_b) is False


def test_compute_safety_pass_false_on_a_non_normal_end_reason():
    rows_a = [_row("cfgA", 0, "heuristic", "t1", "hero", end_reason="crash")]
    rows_b = [_row("cfgB", 0, "heuristic", "t1", "villain")]
    assert compute_safety_pass(rows_a, rows_b) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest showdown_bot/tests/test_strength_holdout_verdict.py -v -k render_verdict or safety_pass`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write the implementation**

```python
# append to showdown_bot/src/showdown_bot/eval/strength_holdout_verdict.py
from dataclasses import dataclass, field

from showdown_bot.eval.pairing import Pair
from showdown_bot.eval.stats import mcnemar_counts, exact_binom_two_sided_p
from showdown_bot.eval.report import _build_cells, _find_cell_flips, _strength_delta, _paired_verdict


@dataclass(frozen=True)
class GateBVerdict:
    verdict: str
    reasons: list
    n_discordant: int
    n_total: int
    delta: float
    exact_p: float
    strength_delta: float
    cell_flips: list


def render_strength_holdout_verdict(pairs: list[Pair], *, safety_pass: bool) -> GateBVerdict:
    """Wires already-paired battle results into the EXISTING, UNCHANGED report.py pipeline --
    same _build_cells/_find_cell_flips/_strength_delta/_paired_verdict a live paired gate
    already uses (report.py:939-970). This function does not reimplement any statistics or
    cell logic; it only builds the two per-run row lists those functions expect."""
    rows_a = [p.row_a for p in pairs]
    rows_b = [p.row_b for p in pairs]

    counts = mcnemar_counts([(p.hero_win_a, p.hero_win_b) for p in pairs])
    exact_p = exact_binom_two_sided_p(counts.n10, counts.n_discordant) if counts.n_discordant else 1.0

    cells_a = _build_cells(rows_a, {})  # {} = team_path_by_hash, cosmetic-display-only field
    cells_b = _build_cells(rows_b, {})
    cell_flips = _find_cell_flips(cells_a, cells_b)
    strength_delta, _n_strength, _n10_s, _n01_s = _strength_delta(pairs)

    verdict, reasons = _paired_verdict(counts, exact_p, cell_flips, strength_delta, safety_pass)

    return GateBVerdict(
        verdict=verdict, reasons=reasons, n_discordant=counts.n_discordant, n_total=counts.total,
        delta=counts.delta, exact_p=exact_p, strength_delta=strength_delta, cell_flips=cell_flips,
    )


def compute_safety_pass(rows_a: list[dict], rows_b: list[dict]) -> bool:
    """Narrow, Gate-B-specific mirror of report.py's run_safety_gates core fields
    (invalid_choices==0, crashes==0, end_reason=='normal') across BOTH arms -- not the full
    RunBundle-based safety table, which needs machinery (schedule_row_count, panel hashes,
    manifest, ...) Gate B's simpler two-row-list shape does not produce. Disclosed narrowing,
    not a silent one."""
    for rows in (rows_a, rows_b):
        for row in rows:
            if row["invalid_choices"] != 0 or row["crashes"] != 0 or row["end_reason"] != "normal":
                return False
    return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest showdown_bot/tests/test_strength_holdout_verdict.py -v`
Expected: all tests in the file pass, including the cell-flip-catches-a-regression test

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/eval/strength_holdout_verdict.py showdown_bot/tests/test_strength_holdout_verdict.py
git commit -m "feat(champions): wire Gate B into the real report.py cell-flip/strength-delta McNemar pipeline"
```

---

## 12. Task 9 — Single-arm battle execution (injectable gauntlet runner)

**Files:**
- Create: `showdown_bot/src/showdown_bot/eval/strength_holdout_runner.py` (this task: `run_strength_holdout_arm`)
- Test: `showdown_bot/tests/test_strength_holdout_runner.py` (this task's tests)

**Fix vs. Rev. 1 (P1-3, P1-4, P1-9):** plays exactly **one** arm per call, against a server that
must be freshly started for that call (the caller's job — see the CLI in Task 11; this function
does not start/stop server processes, exactly like `i8d_runner.run_i8d_live_gate` doesn't
either). `config_hash`/`git_sha`/`candidate_identity` are derived internally
(`resolve_strength_holdout_provenance`, dirty-tree fail-closed), never caller-trusted. The battle
loop is **fully implemented**, not a `NotImplementedError` stub — `gauntlet_runner` is an
injectable parameter (default: the real `run_local_gauntlet`) so it is fully unit-testable
offline with a fake.

**Fix vs. Rev. 3 (P1, most severe finding across all revisions):** the per-battle row no longer
reads `stats.winner`/`stats.end_reason`/`stats.turns` — verified by reading the complete real
`GauntletStats` class (`gauntlet.py:222-240`) and the one real production caller that builds a
`result_jsonl`-schema row (`cli.py`'s `run_schedule`/`on_br`): those three fields do not exist on
the stats object **under any name** and are structurally unreachable from it. The real
per-battle record only ever arrives through the `on_battle_result` callback `run_local_gauntlet`
accepts, exactly mirroring `cli.py`'s own `on_br` closure. Rows are now written via the real
`eval.result_jsonl.BattleResultWriter` (validates + appends), not a hand-rolled staging-file
dance. The arm also now proves its seeds server-side before publishing: the Channel-A
`SHOWDOWN_BATTLE_SEED_BASE` env var is checked before battle 1, and `eval.seeding.verify_seed_log`
runs after the battle loop and before publish, mirroring `i8d_runner.py`'s/`coverage_runner.py`'s
own private `_verify_seed_alignment` twins.

**Fix vs. Rev. 12 (Rev. 13, §1l, second review round P1):** the arm manifest carried
`holdout_team_ids` — the sorted six team IDs this arm actually scheduled (`scheduled_team_ids`,
already computed for the missing-hashes check). Purely additive; no existing test reads the
manifest's exact key set (verified by grep), so nothing here broke Task 9's own tests.

**Fix vs. Rev. 13 (Rev. 14, §1m, third review round P1):** `holdout_team_ids` (a bare list) is
now `holdout_teams` (a mapping, `team_id -> {"team_path": ..., "content_hash": ...}`) — a list
only ever ASSERTED which six teams were scheduled; it was never bound to what `rows` actually
contain. Each entry's `team_path`/`content_hash` are the exact values every row for that team was
built from (`opp_team_path`/`opp_team_hash` in `_capture`, same `HOLDOUT_TEAMS_DIR` expression),
so Task 10 can now PROVE agreement between the manifest and the rows, not just trust it. Also
purely additive to this function's own behavior (still `_write_json_atomic`, still one call);
Task 10 is the actual consumer of the new shape (§13).

- [ ] **Step 1: Write the failing tests**

```python
# showdown_bot/tests/test_strength_holdout_runner.py
import json
from dataclasses import dataclass

import pytest

from showdown_bot.eval.strength_holdout_runner import (
    resolve_strength_holdout_provenance, run_strength_holdout_arm, GateBAbort,
)
from showdown_bot.eval.strength_holdout_schedule import build_strength_holdout_schedule


def _six_teams():
    return sorted(f"holdout_{i}" for i in range(6))


def _fake_team_content_hashes():
    # fixture-only, deliberately hash-shaped (16 hex chars) so downstream code that expects a
    # real team_content_hash format isn't accidentally exercised with an obviously-fake string
    return {team_id: f"{i:016x}" for i, team_id in enumerate(_six_teams())}


def test_resolve_provenance_refuses_a_dirty_tree(monkeypatch):
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_is_dirty", lambda: True)
    with pytest.raises(GateBAbort, match="dirty"):
        resolve_strength_holdout_provenance(hero_agent="heuristic")


def test_resolve_provenance_derives_git_sha_and_config_hash_itself(monkeypatch):
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_is_dirty", lambda: False)
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_sha", lambda: "abc123")
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._derive_config_hash", lambda hero_agent: "cfgderived")
    prov = resolve_strength_holdout_provenance(hero_agent="heuristic")
    assert prov["git_sha"] == "abc123"
    assert prov["config_hash"] == "cfgderived"
    assert prov["candidate_identity"]  # non-empty, sha1-derived


def test_derive_config_hash_and_i8d_provenance_build_the_identical_manifest_call(monkeypatch):
    # Rev. 10 fix: PROVES the reconciliation claim in _derive_config_hash's own docstring --
    # resolve_coverage_provenance (which _derive_config_hash calls) and resolve_i8d_provenance
    # call effective_config_manifest with IDENTICAL arguments for the same hero_agent, which
    # guarantees the same config_hash regardless of what the real config files/environment
    # happen to contain at test-run time (asserting on the real output directly would make this
    # test depend on ambient repo state -- itemdata/speciesdata staleness, format yaml presence --
    # that has nothing to do with the claim being proven here).
    calls = []

    def fake_effective_config_manifest(**kwargs):
        calls.append(kwargs)
        return {"fixture": "manifest"}

    monkeypatch.setattr("showdown_bot.learning.provenance.git_sha_and_dirty", lambda: ("fixture-sha", False))
    monkeypatch.setattr("showdown_bot.eval.config_env.effective_config_manifest", fake_effective_config_manifest)

    from showdown_bot.eval.strength_holdout_runner import _derive_config_hash
    from showdown_bot.eval.i8d_runner import resolve_i8d_provenance
    from showdown_bot.eval.strength_holdout_schedule import STRENGTH_HOLDOUT_FORMAT_ID

    _derive_config_hash("heuristic")
    resolve_i8d_provenance(hero_agent="heuristic")

    assert len(calls) == 2
    assert calls[0] == calls[1]
    # P3 fix: the equality above only pins COVERAGE_FORMAT == I8D_FORMAT (both flow through
    # calls[0]/calls[1] equally, whatever they are) -- it does NOT pin either to
    # STRENGTH_HOLDOUT_FORMAT_ID, the format Gate B's own schedule actually plays under. Without
    # this line, _derive_config_hash could silently drift onto a DIFFERENT format than Gate B's
    # own battles use while this test kept passing. Closes the triangle, not just one edge of it.
    assert calls[0]["format_id"] == STRENGTH_HOLDOUT_FORMAT_ID


def test_derive_config_hash_wraps_each_known_provenance_failure_type(monkeypatch):
    # Rev. 10 fix: CoverageRunError/ItemdataStaleError/SpeciesMetaStaleError/PinnedCalcError are
    # all confirmed-real exception types resolve_coverage_provenance's own call graph can raise
    # (config_env.py:254-320) -- caught SPECIFICALLY here, not via a blanket except Exception
    # (unlike NF5's gauntlet_runner wrap), since this callee is auditable and was actually
    # audited rather than assumed opaque.
    from showdown_bot.eval.strength_holdout_runner import _derive_config_hash, GateBAbort
    from showdown_bot.eval.coverage_runner import CoverageRunError
    from showdown_bot.engine.items import ItemdataStaleError
    from showdown_bot.engine.species_meta import SpeciesMetaStaleError
    from showdown_bot.engine.calc.pin import PinnedCalcError

    for exc_type in (CoverageRunError, ItemdataStaleError, SpeciesMetaStaleError, PinnedCalcError):
        def _raise(*, hero_agent, _exc_type=exc_type):
            raise _exc_type("fixture-forced failure")
        monkeypatch.setattr("showdown_bot.eval.coverage_runner.resolve_coverage_provenance", _raise)
        with pytest.raises(GateBAbort, match="config provenance derivation failed"):
            _derive_config_hash("heuristic")


def test_git_is_dirty_wraps_a_called_process_error(monkeypatch):
    # NF4 fix (Rev. 8): check=True raises subprocess.CalledProcessError outside a git checkout;
    # this was unguarded and would escape resolve_strength_holdout_provenance ->
    # run_strength_holdout_arm as a raw traceback, before a single battle plays.
    from showdown_bot.eval.strength_holdout_runner import _git_is_dirty
    import subprocess as subprocess_module

    def _raise(*a, **kw):
        raise subprocess_module.CalledProcessError(128, ["git", "status", "--porcelain"])

    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.subprocess.run", _raise)
    with pytest.raises(GateBAbort, match="git dirty-state"):
        _git_is_dirty()


def test_git_sha_wraps_a_missing_git_executable(monkeypatch):
    # Same fix, the FileNotFoundError branch (git missing from PATH entirely).
    from showdown_bot.eval.strength_holdout_runner import _git_sha

    def _raise(*a, **kw):
        raise FileNotFoundError("git not found")

    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.subprocess.run", _raise)
    with pytest.raises(GateBAbort, match="git sha"):
        _git_sha()


@dataclass
class _FakeGauntletStats:
    # Rev. 4 fix: matches the REAL GauntletStats shape (gauntlet.py:222-240) exactly --
    # `games` only. Rev. 3's fake carried `winner`/`invalid_choices`/`crashes`/`end_reason`
    # directly on stats; the real class has none of those (verified by reading the full class
    # body). Every per-battle result field only ever arrives via the `on_battle_result`
    # callback's `record` argument -- see `_fake_gauntlet_runner_factory` below.
    games: int = 1


def _fake_gauntlet_runner_factory(winner="hero", end_reason="normal"):
    calls = []

    async def fake_run_local_gauntlet(*, on_battle_result=None, **kwargs):
        calls.append(kwargs)
        if on_battle_result is not None:
            # Matches gauntlet.py's real on_battle_result(record) contract exactly (called
            # synchronously with one positional dict arg, built by _battle_result_record):
            # 9 keys -- winner/turns/end_reason/end_hp_diff/invalid_choices/crashes/
            # decision_latency_p95_ms/room_raw_path/normalized_room_log_sha256.
            on_battle_result({
                "winner": winner, "turns": 5, "end_reason": end_reason, "end_hp_diff": 0.0,
                "invalid_choices": 0, "crashes": 0, "decision_latency_p95_ms": 10.0,
                "room_raw_path": None, "normalized_room_log_sha256": None,
            })
        return _FakeGauntletStats(games=1)

    fake_run_local_gauntlet.calls = calls
    return fake_run_local_gauntlet


def _write_valid_seed_log(path, seed_base, count):
    from showdown_bot.eval.seeding import derive_battle_seed as _dbs
    with open(path, "w", encoding="utf-8") as fh:
        for i in range(count):
            fh.write(json.dumps({"battle_index": i, "seed": _dbs(seed_base, i), "seed_base": seed_base}) + "\n")


def _setup_common(monkeypatch, tmp_path, schedule):
    """Shared fixture setup for tests that need to reach the battle loop: dirty-tree/provenance
    mocks, the Channel-A seed-base env var, and a seed log that will genuinely verify."""
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_is_dirty", lambda: False)
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_sha", lambda: "abc123")
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._derive_config_hash", lambda hero_agent: f"cfg-{hero_agent}")
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", schedule.seed_base)
    seed_log_path = tmp_path / "seeds.jsonl"
    _write_valid_seed_log(str(seed_log_path), schedule.seed_base, len(schedule.battle_keys))
    return str(seed_log_path)


def _arm_out_dir(tmp_path, name, stratum="windows"):
    """Rev. 15 fix (§1n, Task-3-review P1 #2): run_strength_holdout_arm now bindingly validates
    out_dir against stratum_output_root -- every test reaching that check needs an out_dir
    actually rooted there, not a bare tmp_path child. Returns a Path (like the `tmp_path /
    "arm_a"` expressions this replaces), so existing `.exists()` / `/` usage keeps working."""
    from showdown_bot.eval.strata_guard import stratum_output_root
    from showdown_bot.eval.strength_holdout_runner import STRENGTH_HOLDOUT_OUTPUT_BASE
    return tmp_path / stratum_output_root(stratum, STRENGTH_HOLDOUT_OUTPUT_BASE) / name


def test_run_strength_holdout_arm_plays_every_battle_key_exactly_once(tmp_path, monkeypatch):
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    seed_log_path = _setup_common(monkeypatch, tmp_path, schedule)
    fake_runner = _fake_gauntlet_runner_factory(winner="hero")

    result = run_strength_holdout_arm(
        hero_agent="heuristic", schedule=schedule, out_dir=str(_arm_out_dir(tmp_path, "arm_a")),
        seed_log_path=seed_log_path, teams_root=".", gauntlet_runner=fake_runner,
        holdout_team_content_hashes=_fake_team_content_hashes(),
        date_stratum_id="fixture-date-stratum-0", stratum_env_override="windows",
    )

    assert len(fake_runner.calls) == 180
    assert result["hero_agent"] == "heuristic"
    assert len(result["rows"]) == 180
    assert all(row["winner"] == "hero" for row in result["rows"])
    # every row's seed comes from the GLOBAL seed_index, never the colliding local `seed`
    seeds_used = {row["seed_index"] for row in result["rows"]}
    assert seeds_used == set(range(180))


def test_run_strength_holdout_arm_publishes_atomically(tmp_path, monkeypatch):
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    seed_log_path = _setup_common(monkeypatch, tmp_path, schedule)
    out_dir = _arm_out_dir(tmp_path, "arm_a")
    run_strength_holdout_arm(
        hero_agent="heuristic", schedule=schedule, out_dir=str(out_dir),
        seed_log_path=seed_log_path, teams_root=".",
        gauntlet_runner=_fake_gauntlet_runner_factory(),
        holdout_team_content_hashes=_fake_team_content_hashes(),
        date_stratum_id="fixture-date-stratum-0", stratum_env_override="windows",
    )
    assert not out_dir.with_name(out_dir.name + ".staging").exists()  # staging dir cleaned up via rename
    assert out_dir.exists()
    with open(out_dir / "rows.jsonl", "r", encoding="utf-8") as fh:
        lines = fh.readlines()
    assert len(lines) == 180


def test_run_strength_holdout_arm_aborts_cleanly_on_a_row_that_fails_schema_validation(tmp_path, monkeypatch):
    # NF3 fix (Rev. 8): BattleResultWriter.write() (called once per row) validates via
    # validate_battle_row internally and can raise ResultRowError -- the same exception type NF1
    # (Rev. 7) fixed on the READ side (_read_arm), but this is the WRITE side, in a different
    # function the Rev. 7 audit table didn't cover (it was scoped to "functions touched in Rev.
    # 7," not to this function's full exception surface -- see §1g). Simulate exactly the
    # realistic failure mode from the fix comment: on_battle_result fires with a field
    # result_jsonl.py's schema doesn't recognize (schema drift between this plan's row-building
    # and the independently-evolving REQUIRED/NULLABLE field sets).
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    seed_log_path = _setup_common(monkeypatch, tmp_path, schedule)

    async def runner_with_an_unknown_field(*, on_battle_result=None, **kwargs):
        if on_battle_result is not None:
            on_battle_result({
                "winner": "hero", "turns": 5, "end_reason": "normal", "end_hp_diff": 0.0,
                "invalid_choices": 0, "crashes": 0, "decision_latency_p95_ms": 10.0,
                "room_raw_path": None, "normalized_room_log_sha256": None,
                "a_field_result_jsonl_has_never_heard_of": True,
            })
        return _FakeGauntletStats(games=1)

    out_dir = _arm_out_dir(tmp_path, "arm_a")
    with pytest.raises(GateBAbort, match="fails schema validation"):
        run_strength_holdout_arm(
            hero_agent="heuristic", schedule=schedule, out_dir=str(out_dir),
            seed_log_path=seed_log_path, teams_root=".", gauntlet_runner=runner_with_an_unknown_field,
            holdout_team_content_hashes=_fake_team_content_hashes(),
            date_stratum_id="fixture-date-stratum-0", stratum_env_override="windows",
        )
    assert not out_dir.exists()  # never published -- orphaned staging dir left behind instead


def test_run_strength_holdout_arm_refuses_an_existing_out_dir(tmp_path, monkeypatch):
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    seed_log_path = _setup_common(monkeypatch, tmp_path, schedule)
    out_dir = _arm_out_dir(tmp_path, "arm_a")
    out_dir.mkdir(parents=True)
    with pytest.raises(GateBAbort, match="already exists"):
        run_strength_holdout_arm(
            hero_agent="heuristic", schedule=schedule, out_dir=str(out_dir),
            seed_log_path=seed_log_path, teams_root=".",
            gauntlet_runner=_fake_gauntlet_runner_factory(),
            holdout_team_content_hashes=_fake_team_content_hashes(),
            date_stratum_id="fixture-date-stratum-0", stratum_env_override="windows",
        )


def test_run_strength_holdout_arm_discards_a_timed_out_battle_and_aborts(tmp_path, monkeypatch):
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    seed_log_path = _setup_common(monkeypatch, tmp_path, schedule)

    async def timing_out_runner(*, on_battle_result=None, **kwargs):
        return _FakeGauntletStats(games=0)

    with pytest.raises(GateBAbort, match="did not complete"):
        run_strength_holdout_arm(
            hero_agent="heuristic", schedule=schedule, out_dir=str(_arm_out_dir(tmp_path, "arm_a")),
            seed_log_path=seed_log_path, teams_root=".", gauntlet_runner=timing_out_runner,
            holdout_team_content_hashes=_fake_team_content_hashes(),
            date_stratum_id="fixture-date-stratum-0", stratum_env_override="windows",
        )


def test_run_strength_holdout_arm_aborts_cleanly_if_the_gauntlet_runner_raises(tmp_path, monkeypatch):
    # NF5 fix (Rev. 9): gauntlet_runner (the real run_local_gauntlet) can raise -- a server
    # disconnect mid-battle, for example -- not just misbehave via its return value (the
    # stats.games != 1 / empty-captured checks the two tests above and below this one exercise).
    # Nothing wrapped the call itself before. Confirm the abort is GateBAbort, names the
    # seed_index it broke at, and preserves the original exception via `from exc`.
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    seed_log_path = _setup_common(monkeypatch, tmp_path, schedule)

    async def disconnecting_runner(*, on_battle_result=None, **kwargs):
        raise ConnectionError("fixture-forced server disconnect")

    with pytest.raises(GateBAbort, match="seed_index 0") as exc_info:
        run_strength_holdout_arm(
            hero_agent="heuristic", schedule=schedule, out_dir=str(_arm_out_dir(tmp_path, "arm_a")),
            seed_log_path=seed_log_path, teams_root=".", gauntlet_runner=disconnecting_runner,
            holdout_team_content_hashes=_fake_team_content_hashes(),
            date_stratum_id="fixture-date-stratum-0", stratum_env_override="windows",
        )
    assert isinstance(exc_info.value.__cause__, ConnectionError)


def test_run_strength_holdout_arm_aborts_before_playing_if_a_scheduled_team_has_no_sealed_hash(tmp_path, monkeypatch):
    # P2 fix (Rev. 3): opp_team_hash must never fall back to the bare team_id -- a scheduled
    # team missing from holdout_team_content_hashes is a sealing gap, not something to paper
    # over with a non-hash placeholder. Must abort before the FIRST battle plays, not after --
    # this check runs before the seed-base/seed-log checks too, so no seed setup is needed.
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_is_dirty", lambda: False)
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_sha", lambda: "abc123")
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._derive_config_hash", lambda hero_agent: "cfg")
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    incomplete_hashes = _fake_team_content_hashes()
    del incomplete_hashes["holdout_0"]
    fake_runner = _fake_gauntlet_runner_factory()

    with pytest.raises(GateBAbort, match="holdout_0"):
        run_strength_holdout_arm(
            hero_agent="heuristic", schedule=schedule, out_dir=str(_arm_out_dir(tmp_path, "arm_a")),
            seed_log_path=str(tmp_path / "seeds.jsonl"), teams_root=".", gauntlet_runner=fake_runner,
            holdout_team_content_hashes=incomplete_hashes,
            date_stratum_id="fixture-date-stratum-0", stratum_env_override="windows",
        )
    assert len(fake_runner.calls) == 0  # no battle played before the check fired


def test_run_strength_holdout_arm_rejects_a_seed_base_env_mismatch(tmp_path, monkeypatch):
    # P1 fix (Rev. 4): the Channel-A seed namespace must be proven BEFORE any battle plays,
    # exactly like i8d_runner.py/coverage_runner.py's own early checks.
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_is_dirty", lambda: False)
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_sha", lambda: "abc123")
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._derive_config_hash", lambda hero_agent: "cfg")
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", "some-other-namespace")
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    fake_runner = _fake_gauntlet_runner_factory()

    with pytest.raises(GateBAbort, match="SHOWDOWN_BATTLE_SEED_BASE"):
        run_strength_holdout_arm(
            hero_agent="heuristic", schedule=schedule, out_dir=str(_arm_out_dir(tmp_path, "arm_a")),
            seed_log_path=str(tmp_path / "seeds.jsonl"), teams_root=".", gauntlet_runner=fake_runner,
            holdout_team_content_hashes=_fake_team_content_hashes(),
            date_stratum_id="fixture-date-stratum-0", stratum_env_override="windows",
        )
    assert len(fake_runner.calls) == 0


def test_run_strength_holdout_arm_requires_a_seed_log_path(tmp_path, monkeypatch):
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_is_dirty", lambda: False)
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_sha", lambda: "abc123")
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._derive_config_hash", lambda hero_agent: "cfg")
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", schedule.seed_base)
    fake_runner = _fake_gauntlet_runner_factory()

    with pytest.raises(GateBAbort, match="seed_log_path"):
        run_strength_holdout_arm(
            hero_agent="heuristic", schedule=schedule, out_dir=str(_arm_out_dir(tmp_path, "arm_a")),
            seed_log_path="", teams_root=".", gauntlet_runner=fake_runner,
            holdout_team_content_hashes=_fake_team_content_hashes(),
            date_stratum_id="fixture-date-stratum-0", stratum_env_override="windows",
        )
    assert len(fake_runner.calls) == 0


def test_run_strength_holdout_arm_aborts_if_the_seed_log_does_not_verify(tmp_path, monkeypatch):
    # P1 fix (Rev. 4): a malformed/misaligned seed log must abort with NO out_dir published,
    # even though every battle in the loop itself "succeeded" (the fake runner always reports
    # games=1) -- proving the server's seeds cannot be trusted must block publish regardless of
    # in-loop success.
    schedule = build_strength_holdout_schedule(holdout_team_ids=_six_teams(), panel_hash="a" * 16)
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_is_dirty", lambda: False)
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_sha", lambda: "abc123")
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._derive_config_hash", lambda hero_agent: "cfg")
    monkeypatch.setenv("SHOWDOWN_BATTLE_SEED_BASE", schedule.seed_base)
    bad_seed_log = tmp_path / "seeds.jsonl"
    _write_valid_seed_log(str(bad_seed_log), "wrong-seed-base-recorded", len(schedule.battle_keys))
    out_dir = _arm_out_dir(tmp_path, "arm_a")

    with pytest.raises(GateBAbort, match="seed-log verification failed"):
        run_strength_holdout_arm(
            hero_agent="heuristic", schedule=schedule, out_dir=str(out_dir),
            seed_log_path=str(bad_seed_log), teams_root=".",
            gauntlet_runner=_fake_gauntlet_runner_factory(),
            holdout_team_content_hashes=_fake_team_content_hashes(),
            date_stratum_id="fixture-date-stratum-0", stratum_env_override="windows",
        )
    assert not out_dir.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest showdown_bot/tests/test_strength_holdout_runner.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

**Before writing:** read `client/gauntlet.py`'s `run_local_gauntlet` signature and its
`on_battle_result`/`_battle_result_record` machinery (full file) and `cli.py`'s `run_schedule`/
`on_br` closure (the one real production caller building a `result_jsonl`-schema row) one more
time immediately before writing this function — the callback wiring below must match that
pattern exactly, not be re-derived from memory. Also re-read `i8d_runner.py:265-275`'s
Channel-A env check and `coverage_runner.py:161-172`'s `_verify_seed_alignment` immediately
before writing the seed-verification parts.

```python
# showdown_bot/src/showdown_bot/eval/strength_holdout_runner.py
"""Gate B (Independent Strength Holdout) — single-arm battle execution.

Plays exactly ONE arm (hero_agent='heuristic' for Candidate A, 'max_damage' for Baseline B) of
the 180-battle-key schedule. The caller (see Task 11's CLI) is responsible for ensuring the
server this connects to was FRESHLY STARTED for this specific call, with the seed namespace
SHOWDOWN_BATTLE_SEED_BASE set to the schedule's own seed_base -- exactly like i8d_runner.py and
coverage_runner.py already require of their own callers. Two arms must never share one server
session (grounding report Rev.2 addendum, Finding 4): the server's seed counter is process-
lifetime global, so sharing a session gives the two arms disjoint real seeds despite matching
labels. combine_strength_holdout_arms (Task 10) is what actually pairs and verdicts the two
arms' already-published output.
"""
from __future__ import annotations

import asyncio
import json
import os
import platform
import posixpath
import subprocess

from showdown_bot.eval.holdout_leakage_scan import HOLDOUT_TEAMS_DIR
from showdown_bot.eval.i8d_runner import _write_json_atomic
from showdown_bot.eval.result_jsonl import BattleResultWriter, make_battle_id, ResultRowError
from showdown_bot.eval.seeding import derive_battle_seed, verify_seed_log, SeedLogError
from showdown_bot.eval.strata_guard import detect_stratum, stratum_output_root
from showdown_bot.eval.strength_holdout_schedule import (
    STRENGTH_HOLDOUT_HERO_TEAM_PATH, STRENGTH_HOLDOUT_FORMAT_ID,
)
from showdown_bot.learning.provenance import make_candidate_identity
from showdown_bot.team.pack import load_packed_team

# Rev. 15 fix (§1n, Task-3-review P1 #2): matches holdout_leakage_scan.ALLOWED_DIRECTORY_PREFIXES'
# "data/eval/champions-panel-v0/strength-holdout-v0/" entry (Task 2) exactly, minus the trailing
# slash stratum_output_root's own f"{base_dir}/{stratum}" join adds back -- every arm this
# function publishes therefore lands somewhere the leakage guard's allowlist already covers,
# with no allowlist change needed.
STRENGTH_HOLDOUT_OUTPUT_BASE = "data/eval/champions-panel-v0/strength-holdout-v0"


class GateBAbort(Exception):
    """A technical abort -- dirty tree, hash mismatch, infra failure, or zero-battle timeout.
    NOT a verdict (ports Gate A's DESIGN sec 2.6 taxonomy, since Gate B has no equivalent
    dedicated section -- grounding report sec 2)."""


def _git_is_dirty() -> bool:
    # NF4 fix (Rev. 8): check=True raises subprocess.CalledProcessError outside a git checkout;
    # a missing git executable raises FileNotFoundError regardless of check=. Both were unguarded
    # and would escape resolve_strength_holdout_provenance -> run_strength_holdout_arm as a raw
    # traceback, before a single battle is played -- not caught by the arm CLI, which only ever
    # catches GateBAbort. Defined in this module (unlike the leakage-scan git calls), so the fix
    # can fold directly into GateBAbort with no cross-module dependency.
    try:
        result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise GateBAbort(f"cannot determine git dirty-state: {exc}") from exc
    return bool(result.stdout.strip())


def _git_sha() -> str:
    # NF4 fix (Rev. 8): same as _git_is_dirty above.
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise GateBAbort(f"cannot determine git sha: {exc}") from exc
    return result.stdout.strip()


def _derive_config_hash(hero_agent: str) -> str:
    """RECONCILED, Rev. 10 (closes the Rev. 1/2 debt, per the user's explicit direction --
    §1i): calls the real `resolve_coverage_provenance`, and this is now PROVEN, not assumed,
    to produce the same config_hash I8-D's own `resolve_i8d_provenance` would derive for the
    same hero_agent -- verified by reading both functions in full (`coverage_runner.py:75-113`,
    `i8d_runner.py:157-202`). They are structurally identical: same `git_sha_and_dirty()` call,
    same dirty-tree refusal, the SAME `effective_config_manifest(agent=hero_agent,
    format_id=format_id, env=behavior_env(), model_hash=None, model_manifest_hash=None)` call
    with identical arguments, the same `make_config_hash(manifest)`, the same
    SHOWDOWN_CALC_BACKEND normalization. The only difference is which domain exception class
    each raises (`CoverageRunError` vs `I8DRunError`) -- irrelevant to the returned config_hash
    VALUE. `format_id` defaults to each function's own gate constant (`COVERAGE_FORMAT` /
    `I8D_FORMAT`); both equal `"gen9championsvgc2026regma"`, confirmed by reading
    `coverage_schedule.py:27` and `i8d_schedule.py:28` directly -- the same value
    `STRENGTH_HOLDOUT_FORMAT_ID` (Task 1) already uses. So for the same hero_agent, same commit,
    and same environment (guaranteed by DESIGN sec 8's gate ordering -- Gate B runs against the
    SAME candidate SHA I8-D and Coverage already passed), all three gates' config_hash values
    are provably identical by construction, not by naming convention.

    P3 fix (Rev. 10 continued): "provably identical" above was only ever proven for
    `COVERAGE_FORMAT == I8D_FORMAT` -- the call below never passed `format_id`, so it silently
    inherited `resolve_coverage_provenance`'s OWN default rather than binding to
    `STRENGTH_HOLDOUT_FORMAT_ID`, the format Gate B's own schedule actually plays under
    (`strength_holdout_schedule.py`, `build_strength_holdout_schedule`'s `format_id=
    STRENGTH_HOLDOUT_FORMAT_ID`). Today all three constants hold the same string, so this was
    inert -- but the failure direction if Gate B's format ever changed while I8-D/Coverage did
    not would have been silent, not loud: battles played under the new format, config_hash (and
    candidate_identity) computed for the old one, and `verify_i8d_verdict_artifact` would still
    PASS, because Gate B's identity would still match I8-D's -- a gate certifying it verified the
    same candidate I8-D did while having actually played a different format. `format_id` is now
    passed explicitly, binding this function's config_hash to the format Gate B actually plays,
    not to whatever `resolve_coverage_provenance` happens to default to.

    Exception surface, also now read rather than assumed (`config_env.py:254-320`):
    `CoverageRunError` (dirty tree / unresolvable git sha / bad SHOWDOWN_CALC_BACKEND);
    `ItemdataStaleError` (`engine/items.py`) and `SpeciesMetaStaleError` (`engine/species_meta.py`)
    -- both DELIBERATELY fail-closed per I7a sec 14, propagated unguarded through
    `effective_config_manifest` -> `config_provenance_for_format` by that slice's own design, not
    an oversight of this one; `PinnedCalcError` (`engine/calc/pin.py`) -- deliberately fail-closed
    per sec 5.4, same propagation shape. `load_format_config`'s own malformed-YAML/schema-error
    path is NOT further named here (its exact exception type was not independently confirmed --
    disclosed, not silently assumed); `FileNotFoundError` from a missing format yaml is already
    caught one level down, inside `config_provenance_for_format` itself, and does not reach here.

    These are caught SPECIFICALLY, not via a blanket `except Exception` -- unlike gauntlet_runner
    (NF5, Rev. 9), this callee IS auditable at reasonable cost, was actually audited, and a
    generic catch here would flatten a genuine cross-gate provenance defect (config derivation
    drifting between gates) into the same undifferentiated abort as a routine dirty-tree stop."""
    from showdown_bot.eval.coverage_runner import resolve_coverage_provenance, CoverageRunError
    from showdown_bot.engine.calc.pin import PinnedCalcError
    from showdown_bot.engine.items import ItemdataStaleError
    from showdown_bot.engine.species_meta import SpeciesMetaStaleError
    try:
        return resolve_coverage_provenance(
            hero_agent=hero_agent, format_id=STRENGTH_HOLDOUT_FORMAT_ID,
        )["config_hash"]
    except (CoverageRunError, ItemdataStaleError, SpeciesMetaStaleError, PinnedCalcError) as exc:
        raise GateBAbort(
            f"config provenance derivation failed for hero_agent={hero_agent!r}: {exc}"
        ) from exc


def resolve_strength_holdout_provenance(*, hero_agent: str = "heuristic") -> dict:
    """Derive this run's own git_sha/config_hash/candidate_identity fresh -- never caller-
    trusted. Refuses on a dirty tree (GateBAbort, not a verdict)."""
    if _git_is_dirty():
        raise GateBAbort("dirty tree: refusing to derive a candidate identity from uncommitted changes")
    git_sha = _git_sha()
    config_hash = _derive_config_hash(hero_agent)
    candidate_identity = make_candidate_identity(hero_agent=hero_agent, git_sha=git_sha, config_hash=config_hash)
    return {"hero_agent": hero_agent, "git_sha": git_sha, "config_hash": config_hash,
            "candidate_identity": candidate_identity}


def run_strength_holdout_arm(
    *, hero_agent: str, schedule, out_dir: str, seed_log_path: str,
    holdout_team_content_hashes: dict[str, str], date_stratum_id: str, teams_root: str = ".",
    calc_backend: str = "oneshot", gauntlet_runner=None, stratum_env_override: str | None = None,
) -> dict:
    """Plays all len(schedule.battle_keys) battles for ONE arm, staged+atomically published.
    gauntlet_runner defaults to the real client.gauntlet.run_local_gauntlet; tests inject a fake
    so this whole function is testable without a live server.

    holdout_team_content_hashes maps holdout_team_id -> its REAL sealed team_content_hash
    (Task 12's seal_team output, .txt+.packed together) -- required, no default. A scheduled
    team missing from this mapping aborts before the first battle plays; the row's opp_team_hash
    field must never fall back to the bare team_id string (Rev. 3 P2 fix: that field name
    promises a hash to every downstream consumer -- the leakage scan, the disjointness check,
    cell grouping -- and a non-hash placeholder there would silently defeat all three).

    Rev. 15 fix (§1n, Task-3-review P1 #1): stratum/platform/date-stratum identity is established
    HERE, on the machine that actually plays this arm's battles -- never re-derived later by
    combine_strength_holdout_arms (Task 10, its own Rev. 15 fix), which reads what THIS function
    wrote into the manifest instead. date_stratum_id is a pre-registered identifier for this run
    (DESIGN sec 3.5: "a Kaggle strength stratum is a separate pre-registered run"), required with
    no default -- an auto-derived "today's date" would not be pre-registered, so the caller must
    supply it. stratum_env_override threads into detect_stratum's own explicit-override escape
    hatch (Task 3) -- required for any real Kaggle run, since detect_stratum() refuses to guess
    Kaggle from a bare non-Windows platform.system() read; also used by tests to pin the stratum
    deterministically regardless of the box actually running the suite."""
    if gauntlet_runner is None:
        from showdown_bot.client.gauntlet import run_local_gauntlet as gauntlet_runner

    provenance = resolve_strength_holdout_provenance(hero_agent=hero_agent)

    scheduled_team_ids = {key.holdout_team_id for key in schedule.battle_keys}
    missing_hashes = scheduled_team_ids - set(holdout_team_content_hashes)
    if missing_hashes:
        raise GateBAbort(
            f"holdout_team_content_hashes is missing a sealed hash for: {sorted(missing_hashes)} "
            "-- every scheduled team must be sealed (Task 12) before any arm can be played"
        )

    # Channel-A seed-namespace gate (mirrors i8d_runner.py:265-275 / coverage_runner.py:485-494
    # exactly) -- fail BEFORE spending a single battle on an unproven seed run.
    seed_base_env = os.environ.get("SHOWDOWN_BATTLE_SEED_BASE", "")
    if seed_base_env != schedule.seed_base:
        raise GateBAbort(
            f"SHOWDOWN_BATTLE_SEED_BASE must be {schedule.seed_base!r} for this arm (Channel A), "
            f"got {seed_base_env!r}: the server must be started with the approved seed namespace"
        )
    if not seed_log_path:
        raise GateBAbort(
            "seed_log_path (SHOWDOWN_EVAL_SEED_LOG) is required so the played seeds can be "
            "proven; without it the run's seeds are only labelled, not verified"
        )

    # Rev. 15 fix (§1n, Task-3-review P1 #1/#2): stratum/platform/out_dir identity, established
    # ONCE here and written into the manifest below -- never re-derived by the combiner.
    if not date_stratum_id:
        raise GateBAbort(
            "date_stratum_id is required and must be non-empty -- DESIGN sec 3.5 requires a "
            "pre-registered stratum/date identifier, fixed before the run, never derived after "
            "the fact"
        )
    stratum = detect_stratum(env_override=stratum_env_override)
    platform_attestation = platform.platform()
    expected_root = stratum_output_root(stratum, STRENGTH_HOLDOUT_OUTPUT_BASE)
    # Rev. 16 fix (§1o, P1 #2): comparing out_dir against expected_root via `==`/`.startswith`
    # directly only works if out_dir happens to be a bare, forward-slash, repo-root-relative
    # string -- exactly what expected_root itself is. Every out_dir this plan's OWN tests
    # construct (via pytest's tmp_path fixture, the same pattern every other test in this file
    # uses to get a real, writable directory) is an ABSOLUTE, OS-native-separator path with
    # tmp_path's own prefix ahead of the stratum root -- so the direct comparison rejected the
    # plan's own tests, not just genuine mistakes. Normalizing separators (matching Task 2's
    # `_normalize_path` precedent, §5) and checking for expected_root as a slash-bounded path
    # SEGMENT -- not a bare prefix -- accepts both the relative (production, repo-root CWD) and
    # absolute (tests, or a fully-resolved real caller) shapes the same way, without requiring
    # out_dir to be one specific form.
    #
    # Review-fix P1: separator-translation alone does not collapse "."/".." segments --
    # out_dir=f"{expected_root}/../../../elsewhere" still contains expected_root as a literal
    # SUBSTRING even though it resolves somewhere completely different once the OS processes the
    # ".." segments, defeating the entire per-stratum separate-tree requirement this check exists
    # to enforce. posixpath.normpath collapses "."/".." lexically -- no filesystem access, no
    # dependence on out_dir existing yet (it doesn't, at this point) -- before the containment
    # check runs, so a traversal attempt no longer looks like it is under the stratum root.
    normalized_out_dir = posixpath.normpath(out_dir.replace("\\", "/"))
    if f"/{expected_root}/" not in f"/{normalized_out_dir}/":
        raise GateBAbort(
            f"out_dir={out_dir!r} must be {expected_root!r} or a path under it for "
            f"stratum={stratum!r} -- DESIGN sec 3.5 requires each stratum to publish under its "
            "own separate output tree, never a shared or ambiguous location"
        )

    staging_dir = f"{out_dir}.staging"
    for label, p in (("output", out_dir), ("staging", staging_dir)):
        if os.path.exists(p):
            raise GateBAbort(f"{label} directory {p} already exists; restart runs from a fresh directory")
    os.makedirs(staging_dir)
    writer = BattleResultWriter(os.path.join(staging_dir, "rows.jsonl"))

    hero_team_abs = os.path.abspath(os.path.join(teams_root, STRENGTH_HOLDOUT_HERO_TEAM_PATH))
    rows: list[dict] = []
    for key in schedule.battle_keys:
        seed = derive_battle_seed(schedule.seed_base, key.seed_index)  # GLOBAL index, never `key.seed`
        battle_id = make_battle_id(schedule.schedule_hash, key.seed_index, seed)
        # Rev. 14 fix (§1m, third review round): HOLDOUT_TEAMS_DIR is now imported from
        # holdout_leakage_scan.py rather than hardcoded inline here a second time -- it is also
        # the source the manifest's holdout_teams mapping (below) derives each team_path from,
        # so the two can never independently drift apart.
        opp_team_path = f"{HOLDOUT_TEAMS_DIR}{key.holdout_team_id}.txt"
        opp_team_abs = os.path.abspath(os.path.join(teams_root, opp_team_path))

        for label, abs_path in (("hero", hero_team_abs), ("opponent", opp_team_abs)):
            try:
                packed = load_packed_team(abs_path)
            except FileNotFoundError as exc:
                raise GateBAbort(f"{label} team not found at {abs_path!r}; refusing to challenge with an empty team") from exc
            if not packed:
                raise GateBAbort(f"{label} team resolves to an EMPTY packed team at {abs_path!r}")

        # winner/turns/end_reason/invalid_choices/crashes/decision_latency_p95_ms are
        # STRUCTURALLY UNREACHABLE from the returned `stats` object (verified against the full
        # real GauntletStats class -- it has only games/hero_wins/villain_wins/ties/
        # invalid_choices/crashes/latencies, all RUN-LIFETIME aggregates, no per-battle winner
        # or end_reason under any name). The real per-battle record only ever arrives through
        # this callback, exactly mirroring cli.py's run_schedule/on_br closure.
        captured: dict = {}

        def _capture(record, _key=key, _battle_id=battle_id, _seed=seed, _opp_team_path=opp_team_path):
            captured.update({
                "battle_id": _battle_id, "run_id": f"{provenance['candidate_identity']}-{hero_agent}",
                "config_id": hero_agent, "format_id": schedule.format_id,
                "config_hash": provenance["config_hash"], "schedule_hash": schedule.schedule_hash,
                "seed_index": _key.seed_index, "opp_policy": _key.opponent_policy,
                "hero_team_path": STRENGTH_HOLDOUT_HERO_TEAM_PATH, "opp_team_path": _opp_team_path,
                "seed": _seed, "seed_base": schedule.seed_base,
                "git_sha": provenance["git_sha"], "dirty": False,
                "opp_team_hash": holdout_team_content_hashes[_key.holdout_team_id],  # real sealed hash, never the bare team_id
                # panel_hash is NULLABLE per result_jsonl.py's schema, but pairing.py's
                # _check_constant_fields indexes row["panel_hash"] directly (pairing.py:105,
                # no .get) -- omitting it doesn't fail validate_battle_row, it crashes pair_runs
                # with a raw KeyError (not a PairingError, so combine's except clause wouldn't
                # even catch it). Required in practice regardless of what result_jsonl.py alone
                # would tolerate.
                "panel_hash": schedule.panel_hash,
                **record,  # winner, turns, end_reason, end_hp_diff, invalid_choices, crashes,
                           # decision_latency_p95_ms, room_raw_path, normalized_room_log_sha256
            })

        try:
            stats = asyncio.run(gauntlet_runner(
                games=1, hero_agent=hero_agent, villain_agent=key.opponent_policy,
                format_id=schedule.format_id, team_path=hero_team_abs, opp_team_path=opp_team_abs,
                on_battle_result=_capture,
            ))
        except Exception as exc:
            # NF5 fix (Rev. 9): gauntlet_runner is the real run_local_gauntlet, an external
            # websocket client this plan does not author -- a server disconnect mid-battle
            # (arguably the single most likely runtime failure of this whole 180-battle loop) is
            # not GateBAbort, and nothing wrapped this call before (flagged but not fixed in
            # §1g's Rev. 8 audit table as an untraced trust boundary -- the CLI handler's own
            # comment then claimed this whole call graph was proven GateBAbort-only WITHOUT that
            # table's qualifier, the same false-unqualified-claim shape as NF2). A boundary wrap
            # does not need the callee's exception contract audited first -- that is the point of
            # a boundary: convert whatever crosses it to this function's own contract regardless
            # of what the un-audited callee can raise. except Exception (not a narrower type) is
            # deliberate for exactly that reason; BaseException subclasses (KeyboardInterrupt,
            # SystemExit) are NOT Exception subclasses and still propagate uninterrupted.
            raise GateBAbort(
                f"gauntlet runner failed at seed_index {key.seed_index}: {exc}"
            ) from exc
        if stats.games != 1:
            raise GateBAbort(
                f"battle at seed_index {key.seed_index} did not complete exactly one game "
                f"(games={stats.games}); restart from a fresh arm run"
            )
        if not captured:
            raise GateBAbort(
                f"battle at seed_index {key.seed_index} completed but on_battle_result never "
                "fired -- no result to publish; restart from a fresh arm run"
            )

        try:
            writer.write(captured)  # validates against result_jsonl's REQUIRED/NULLABLE schema, then appends
        except ResultRowError as exc:
            # NF3 fix (Rev. 8): BattleResultWriter.write() calls validate_battle_row internally
            # (result_jsonl.py:107-110) and can raise ResultRowError -- NF1 (Rev. 7) fixed the
            # READ-side call to the same validator in _read_arm, but this is the WRITE side, a
            # different function the Rev. 7 audit table did not cover because it was scoped to
            # "functions touched in Rev. 7," not to this function's full exception surface (the
            # scoping mistake itself, corrected in Rev. 8 -- see §1g). Reachable in practice:
            # _capture merges **record from _battle_result_record, whose field set has grown
            # historically (decision_trace_count/_sha256, normalized_room_log_sha256, panel_split
            # were all added after this schema's original shape) -- a field result_jsonl.py
            # doesn't yet know about raises "unknown fields" here, mid-loop, potentially after
            # staging_dir and prior rows already exist on disk (left in place on abort, same as
            # every other GateBAbort raised inside this loop -- no new cleanup behavior).
            raise GateBAbort(
                f"battle at seed_index {key.seed_index} produced a row that fails schema "
                f"validation: {exc}"
            ) from exc
        rows.append(captured)

    # Seed-log proof AFTER the battle loop, BEFORE any publish -- mirrors i8d_runner.py/
    # coverage_runner.py's own private _verify_seed_alignment call site exactly (same position
    # in the flow: after the loop, before the verdict/manifest write, before os.replace).
    try:
        seed_records = verify_seed_log(seed_log_path, schedule.seed_base, len(rows))
    except SeedLogError as exc:
        raise GateBAbort(f"seed-log verification failed: {exc}") from exc
    for key, rec in zip(schedule.battle_keys, seed_records):
        if key.seed_index != rec["battle_index"]:
            raise GateBAbort(
                f"seed-log/schedule misalignment: battle-key seed_index {key.seed_index} != "
                f"logged battle_index {rec['battle_index']}"
            )

    # Rev. 14 fix (§1m, third review round P1): a bare team_id LIST (Rev. 13) only ever ASSERTED
    # which six teams this arm scheduled -- it was never BOUND to what the rows themselves
    # actually contain. A canonical MAPPING closes that gap: team_path is the real path each row's
    # opp_team_path was built from (same HOLDOUT_TEAMS_DIR expression, just above) and
    # content_hash is the exact value each row's opp_team_hash was stamped with
    # (holdout_team_content_hashes[team_id], _capture's own opp_team_hash line above) -- so Task
    # 10 can prove the manifest and the rows agree, not just trust that they do.
    holdout_teams = {
        team_id: {
            "team_path": f"{HOLDOUT_TEAMS_DIR}{team_id}.txt",
            "content_hash": holdout_team_content_hashes[team_id],
        }
        for team_id in sorted(scheduled_team_ids)
    }
    _write_json_atomic(os.path.join(staging_dir, "arm_manifest.json"), {
        "hero_agent": hero_agent, "schedule_hash": schedule.schedule_hash,
        "seed_base": schedule.seed_base, "panel_hash": schedule.panel_hash,
        "holdout_teams": holdout_teams,
        # Rev. 15 fix (§1n, Task-3-review P1 #1): the three fields established near the top of
        # this function (stratum/platform_attestation/date_stratum_id) are recorded here so
        # combine_strength_holdout_arms (Task 10) can validate and compare them WITHOUT ever
        # calling detect_stratum() itself.
        "stratum": stratum, "platform_attestation": platform_attestation,
        "date_stratum_id": date_stratum_id,
        **provenance, "seed_log_path": seed_log_path, "n_rows": len(rows),
    })
    os.replace(staging_dir, out_dir)
    return {"hero_agent": hero_agent, "rows": rows, "out_dir": out_dir, **provenance}
```

**Note on the removed per-battle staging dance:** Rev. 3 staged each row to a temp file and
`_adopt_battle_atomic`'d it into the accumulating dataset, mirroring `i8d_runner.py`'s pattern.
That mechanism existed because `i8d_runner.py` writes latency *profile* rows through a different
writer (`DecisionProfileWriter`). Gate B writes *result* rows, and `BattleResultWriter.write()`
already validates-then-appends in one call (`result_jsonl.py`, the real production pattern `cli.py`'s
`run_schedule` uses) — the extra staging-file indirection added complexity without adding safety
here, so it's dropped; the outer `{out_dir}.staging` → `os.replace` still provides whole-run
atomicity.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest showdown_bot/tests/test_strength_holdout_runner.py -v`
Expected: 16 passed, fully offline, no server touched (10 from Rev. 1-6 + 3 git-subprocess/
write-side-schema-validation tests, Rev. 8 + 1 gauntlet_runner-boundary-wrap test, Rev. 9 + 2 new
config-hash-reconciliation tests, Rev. 10)

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/eval/strength_holdout_runner.py showdown_bot/tests/test_strength_holdout_runner.py
git commit -m "feat(champions): Gate B single-arm battle execution with injectable gauntlet runner"
```

---

## 13. Task 10 — Combine: pairing, every guard wired, ledger, full evidence bundle

**Files:**
- Modify: `showdown_bot/src/showdown_bot/eval/strength_holdout_runner.py`
- Modify: `showdown_bot/tests/test_strength_holdout_runner.py`

**Fix vs. Rev. 1 (P1-5, P1-6, P1-8-ledger):** this is the function Rev. 1's monolithic
`run_strength_holdout_gate` should have been — every guard built in Tasks 2-6 is actually called
here, `safety_pass` comes from `compute_safety_pass` (Task 8), and the published bundle contains
both arms' full row datasets plus seed-log proofs plus a per-cell breakdown, not just
`verdict.json` alone. Ledger entries now carry the real 9 required `run`-kind fields.

**Fix vs. Rev. 2 (§1b):** the broken `candidate_identity` equality check between arms is
replaced with the correct one (arm A's identity is THE candidate, checked against I8-D/Coverage;
arms must instead share `git_sha`/`schedule_hash`/`panel_hash`/`seed_base`, and arm roles are
now enforced explicitly — A must be `heuristic`, B must be `max_damage`). Both upstream verdict
paths are now required and checked before any pairing or publish. The dead `_all_guards_pass_for_test`
seam is gone; tests patch the two real, independently-tested verdict-verification functions and
pass legitimate explicit inputs to every other guard, which now always runs for real.

**Fix vs. Rev. 3 (§1c):** the baseline-drift guard (Task 6's manifest) is now actually called
(`load_baseline` + `verify_baseline`, wrapped as `GateBAbort` on `BaselineDriftError`) — Task 6
built it but nothing ever invoked it from the live flow, so "every guard wired" was false for
this one specifically. `pair_runs`'s base `PairingError` is now caught, not just
`MissingPairError`, so every pairing failure mode reaches the CLI's error handling uniformly.
`holdout_content_hashes`/`reference_species` are no longer allowed to be `{}` in production —
Rev. 3's "explicit empty dict is a deliberate choice" reasoning didn't actually stop production
code (Task 11's own CLI handler) from passing `{}` too, making the guards vacuous exactly where
it mattered most; both are now rejected unconditionally, and tests use small non-empty fixture
maps instead.

**Fix vs. Rev. 4 (§1d, N1/N2):** every row built anywhere in this plan now carries `panel_hash`
(`pairing.py` indexes it directly, no `.get` — its absence crashed `pair_runs` with a raw,
uncaught `KeyError`). `result_sha256` is now computed from the exact bytes written to
`verdict.json`, not a second, differently-formatted `json.dumps` call.

**Fix vs. Rev. 5 (§1e, F3/F6):** `_read_arm` now validates every row (`validate_battle_row`) and
`_assert_rows_match_manifest` proves each arm's rows actually belong to its own manifest
(`n_rows`, five identity fields, and a freshly re-derived `candidate_identity`) before any of
that manifest's claims license an upstream-verdict check, a ledger entry, or a published verdict
— closing the last unverified trust edge in the whole candidate-identity chain. The ledger entry
now writes before `os.replace(staging_dir, out_dir)`, not after, so a failed `append_entry` can
never coexist with a published bundle the next run's access-budget check wouldn't know about.

**Fix vs. Rev. 11 (Rev. 12, §1k, P1 #2 downstream):** Task 2's leakage guard rebuilt its content
leg as a raw-payload byte scan and renamed `assert_no_holdout_leakage`'s `content_hashes`
parameter to `team_ids`. The call site below passes `team_ids=list(holdout_content_hashes.keys())`
instead of `content_hashes=holdout_content_hashes` — `holdout_content_hashes` itself, and every
other guard/check in this function, is unchanged.

**Fix vs. Rev. 12 (Rev. 13, §1l, second review round P1):** `holdout_content_hashes` being
non-empty didn't prove it covered every scheduled team — the arm-vs-arm field loop gained
`holdout_team_ids`, and a new check required its key set to exactly equal
`holdout_content_hashes.keys()` before any guard ran.

**Fix vs. Rev. 13 (Rev. 14, §1m, third review round P1):** `holdout_team_ids` (Rev. 13's bare
list) was itself only ever an ASSERTION, never bound to what `rows.jsonl` actually contains.
`_assert_rows_match_manifest` now validates the manifest's `holdout_teams` mapping structurally
(`_validate_holdout_teams_mapping`) and binds it to that same arm's own rows
(`_assert_rows_bind_to_holdout_teams`) — both before the pre-existing scalar per-field checks.
The arm-vs-arm loop compares `holdout_teams` (not `holdout_team_ids`); the cross-check against
`holdout_content_hashes` is now full dict equality (keys AND values, not just keys); and the
leakage guard's `team_ids=` argument is sourced from the validated, row-bound
`manifest_a["holdout_teams"]`, not from the caller-supplied map directly.

- [ ] **Step 1: Write the failing tests**

```python
from showdown_bot.eval.heldout_ledger import AccessBudgetError, read_ledger
from showdown_bot.eval.strength_holdout_runner import combine_strength_holdout_arms
from showdown_bot.eval.holdout_leakage_scan import LeakageDriftError
from showdown_bot.eval.holdout_disjointness import HoldoutNotDisjointError
from showdown_bot.eval.strength_holdout_verdict import StrengthHoldoutRunError
from showdown_bot.learning.provenance import make_candidate_identity


def _fake_holdout_teams():
    # Rev. 14 fix (§1m, third review round P1): structurally valid (six entries, canonical
    # paths, non-empty hash-shaped strings) but NOT backed by any real committed git content --
    # fine as _write_arm's DEFAULT, since every row _write_arm builds is stamped from THIS SAME
    # mapping (below), so manifest and rows always agree with each other by construction,
    # regardless of whether the hash values are real. Tests that must reach the real leakage
    # scanner pass an explicit holdout_teams derived from _write_holdout_teams_repo instead
    # (_holdout_teams_mapping).
    from showdown_bot.eval.holdout_leakage_scan import HOLDOUT_TEAMS_DIR
    return {
        team_id: {"team_path": f"{HOLDOUT_TEAMS_DIR}{team_id}.txt", "content_hash": f"{i:016x}"}
        for i, team_id in enumerate(_six_teams())
    }


def _holdout_teams_mapping(hashes: dict) -> dict:
    """Converts a flat {team_id: content_hash} map (as _write_holdout_teams_repo returns, and as
    combine_strength_holdout_arms's own holdout_content_hashes parameter still takes -- that
    shape is UNCHANGED by Rev. 14) into the nested holdout_teams shape _write_arm's manifest now
    needs. Kept separate from _write_holdout_teams_repo itself so that helper's own job (real git
    repo + real hashes) stays focused."""
    from showdown_bot.eval.holdout_leakage_scan import HOLDOUT_TEAMS_DIR
    return {
        team_id: {"team_path": f"{HOLDOUT_TEAMS_DIR}{team_id}.txt", "content_hash": content_hash}
        for team_id, content_hash in hashes.items()
    }


def _write_arm(tmp_path, name, *, hero_agent, config_hash, git_sha="abc123", winner="hero", n=None,
                holdout_teams=None, stratum="windows", platform_attestation="Fixture-Platform-1",
                date_stratum_id="fixture-date-stratum-0", calc_backend="oneshot",
                seed_base="champions-strength-holdout-v0", panel_hash="panel1",
                schedule_hash=None):
    # Rev. 3 fix: candidate_identity is DERIVED via the real formula, never hardcoded the same
    # for both arms -- hero_agent is a hash input, so heuristic vs max_damage always produces
    # different identities. A test that hardcodes one shared value can't catch a broken equality
    # check between arms (exactly how Rev. 2's bug hid from its own tests).
    candidate_identity = make_candidate_identity(hero_agent=hero_agent, git_sha=git_sha, config_hash=config_hash)
    # "Zwei Reste" fix (Rev. 6): derive_battle_seed's real return shape is "sodium,<32 hex>",
    # never a bare int -- a fixture that writes "seed": i is the same class of unfaithful stand-in
    # N4 already fixed for JSON formatting, just on a different field. Local import, matching the
    # existing pattern in _write_valid_seed_log above.
    from showdown_bot.eval.seeding import derive_battle_seed as _seed_for
    # Rev. 14 fix (§1m, third review round P1): default matches _fake_holdout_teams() -- both
    # arms of a test that doesn't care about team identity specifically therefore agree with
    # each other AND with their own rows by construction (every row below is stamped from THIS
    # SAME mapping, cycled); a test that DOES care passes an explicit, different mapping for one
    # arm, or corrupts the written manifest/rows afterward (see the binding-mismatch tests below).
    if holdout_teams is None:
        holdout_teams = _fake_holdout_teams()
    # Review-fix (Task-10 review P1 #1): the arm this fixture writes must be a REAL canonical
    # 180-battle-key arm by default, not a 12-row stand-in. combine_strength_holdout_arms now
    # rebuilds the canonical schedule from the manifest's own team_ids/panel_hash/seed_base and
    # binds every row to exactly one battle key, so a fixture that emits an arbitrary row count
    # with a made-up "sched1" hash can no longer prove the success path -- and, worse, could not
    # have caught the truncated-arm hole the review found (two matching 12-row arms passed).
    # The rows below are therefore generated FROM build_strength_holdout_schedule itself.
    #
    # Fixtures that deliberately supply a structurally INVALID holdout_teams mapping (wrong
    # entry shape, wrong count, non-string ids) still need to reach combine's own shape
    # validation rather than exploding inside this helper, so a failed rebuild falls back to the
    # pre-review cycling behaviour with a placeholder hash -- those tests abort long before the
    # canonical-schedule guard runs.
    try:
        _schedule = build_strength_holdout_schedule(
            holdout_team_ids=sorted(holdout_teams), panel_hash=panel_hash, seed_base=seed_base,
        )
    except (ValueError, TypeError, AttributeError):
        _schedule = None
    arm_dir = tmp_path / name
    arm_dir.mkdir()
    rows = []
    if _schedule is not None:
        keys = _schedule.battle_keys if n is None else _schedule.battle_keys[:n]
        real_schedule_hash = _schedule.schedule_hash if schedule_hash is None else schedule_hash
        for key in keys:
            team_entry = holdout_teams[key.holdout_team_id]
            # Review-fix (Task-10 second review, P1): every identity field is now the REAL
            # canonical value Task 9's own row builder derives, not a stand-in. The previous
            # fixture wrote battle_id=f"b{seed_index}" and run_id="r" and still passed -- which is
            # precisely how the missing row-to-battle-key binding stayed invisible.
            row_seed = _seed_for(seed_base, key.seed_index)
            rows.append({
                "battle_id": make_battle_id(real_schedule_hash, key.seed_index, row_seed),
                "run_id": f"{candidate_identity}-{hero_agent}", "config_id": hero_agent,
                "format_id": STRENGTH_HOLDOUT_FORMAT_ID,
                "config_hash": config_hash, "schedule_hash": real_schedule_hash,
                "seed_index": key.seed_index,
                # opp_policy now comes from the battle key itself (real schedules alternate
                # heuristic/max_damage across the 12 (team, policy) cells) -- a fixture that
                # hardcoded "heuristic" for every row could never satisfy the canonical-schedule
                # binding this arm is supposed to demonstrate.
                "opp_policy": key.opponent_policy,
                "hero_team_path": STRENGTH_HOLDOUT_HERO_TEAM_PATH,
                "opp_team_path": team_entry["team_path"],
                "seed": row_seed, "seed_base": seed_base,
                "winner": winner, "turns": 5,
                "invalid_choices": 0, "crashes": 0, "decision_latency_p95_ms": 5.0, "git_sha": git_sha,
                "dirty": False, "end_reason": "normal", "opp_team_hash": team_entry["content_hash"],
                # panel_hash: required by pairing.py's _check_constant_fields (direct row[field]
                # index, pairing.py:105) even though result_jsonl.py's schema treats it as nullable
                # -- omitting it here reproduces the exact bug this fixture exists to catch.
                "panel_hash": panel_hash,
            })
    else:
        team_ids_cycle = sorted(holdout_teams)
        real_schedule_hash = "sched1" if schedule_hash is None else schedule_hash
        for i in range(12 if n is None else n):
            team_id = team_ids_cycle[i % len(team_ids_cycle)]
            team_entry = holdout_teams[team_id]
            rows.append({
                "battle_id": f"b{i}", "run_id": "r", "config_id": hero_agent,
                "format_id": "gen9championsvgc2026regma",
                "config_hash": config_hash, "schedule_hash": real_schedule_hash, "seed_index": i,
                "opp_policy": "heuristic", "hero_team_path": "h.txt",
                "opp_team_path": team_entry["team_path"],
                "seed": _seed_for(seed_base, i), "seed_base": seed_base,
                "winner": winner, "turns": 5,
                "invalid_choices": 0, "crashes": 0, "decision_latency_p95_ms": 5.0, "git_sha": git_sha,
                "dirty": False, "end_reason": "normal", "opp_team_hash": team_entry["content_hash"],
                "panel_hash": panel_hash,
            })
    n = len(rows)
    # newline="" + separators=(",", ":") mirrors the canonical eval.result_jsonl.to_jsonl_line/
    # BattleResultWriter format (compact separators, LF only, no CRLF-on-Windows translation) --
    # a fixture that writes differently-formatted-but-equivalent JSON isn't wrong today (json.loads
    # doesn't care), but it stops being a faithful stand-in the moment anything hashes the file
    # (as combine's evidence bundle now does after the N2 fix below).
    with open(arm_dir / "rows.jsonl", "w", encoding="utf-8", newline="") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")

    # Rev. 19 fix (Task 9 review-fix sync, §1r): a REAL seeds.jsonl, matching verify_seed_log's
    # own expected shape and derive_battle_seed's own real derivation, so combine's new per-arm
    # seed-artifact re-verification (_assert_seed_artifact_verified) can genuinely succeed
    # against real bytes -- not a manifest-only claim. newline="\n" (no translation) so the bytes
    # written match exactly what seed_log_sha256 below hashes.
    seed_log_lines = [
        json.dumps({"battle_index": i, "seed": _seed_for(seed_base, i), "seed_base": seed_base})
        for i in range(n)
    ]
    seed_log_text = "".join(line + "\n" for line in seed_log_lines)
    with open(arm_dir / "seeds.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(seed_log_text)
    seed_log_sha256 = hashlib.sha256(seed_log_text.encode("utf-8")).hexdigest()

    manifest = {
        "hero_agent": hero_agent, "schedule_hash": real_schedule_hash, "seed_base": seed_base,
        "panel_hash": panel_hash, "git_sha": git_sha, "config_hash": config_hash,
        "candidate_identity": candidate_identity, "n_rows": n,
        "holdout_teams": holdout_teams,
        # Rev. 15 fix (§1n, Task-3-review P1 #1): both arms default to the SAME stratum/
        # platform_attestation/date_stratum_id, so a test that doesn't care about strata
        # specifically (most of them) gets two equally-attested arms by construction -- exactly
        # the "accept two equally-attested arms" scenario the review requires as its own test.
        # A test that DOES care (mixed strata / differing date_stratum_id / contradictory
        # override) passes an explicit, different value for one arm.
        "stratum": stratum, "platform_attestation": platform_attestation,
        "date_stratum_id": date_stratum_id,
        # Rev. 19 fix (Task 9 review-fix sync, §1r): calc_backend + the four-field seed proof,
        # replacing the old caller-local seed_log_path field Task 9's own review-fix removed.
        "calc_backend": calc_backend,
        "seed_log_relpath": "seeds.jsonl", "seed_log_sha256": seed_log_sha256,
        "seed_log_n_lines": n, "seed_log_verified": True,
    }
    with open(arm_dir / "arm_manifest.json", "w", encoding="utf-8") as fh:
        json.dump(manifest, fh)
    return str(arm_dir)


def _fake_holdout_hashes():
    # Deliberately NOT six real committed teams: every remaining caller of this helper (below)
    # asserts an abort that fires before combine_strength_holdout_arms's holdout_teams
    # cross-check or the leakage scan ever run (Rev. 13/14, §1l/§1m) -- an i8d/coverage-path
    # guard, an arm-read/manifest-schema guard, or an arm-role/git_sha mismatch, all earlier in
    # the function. Content is irrelevant there; only non-empty-ness is. Tests that DO reach the
    # cross-check or the leakage scan use _write_holdout_teams_repo instead, not this.
    return {"holdout_0": "aaaa1111bbbb2222", "holdout_1": "cccc3333dddd4444"}


def _candidate_packed(index: int) -> str:
    """The packed content for holdout candidate #index -- two species, named by INDEX only (see
    _write_holdout_teams_repo for why the team_id must never appear in a species name)."""
    return f"|FixtureCandidate{index}A|||||||||]|FixtureCandidate{index}B|||||||||"


def _write_holdout_teams_repo(tmp_path):
    """A real, isolated git repo seeded with six committed, allowlist-conformant sealed team
    files. Rev. 13 fix (§1l, second review round P1): the leakage guard (Task 2) now reads
    committed git blobs at combine-time -- a test that actually reaches assert_no_holdout_leakage
    needs real committed content at the real HOLDOUT_TEAMS_DIR convention with teams_root pointed
    at it, not the ambient worktree (no sealed teams exist there yet -- Task 13 the plan task is
    still blocked) and not a bare fake hash string. _fake_holdout_hashes() above stays in use for
    the tests that abort before that guard ever runs, where content is irrelevant -- this helper
    is for every test that reaches it for real. tmp_path is already function-scoped, so a fresh
    repo per call means no test's mutation of it can leak into another. Returns (teams_root,
    holdout_content_hashes); team_ids match _six_teams()."""
    from showdown_bot.eval.holdout_leakage_scan import HOLDOUT_TEAMS_DIR
    from showdown_bot.eval.panel import team_content_hash

    repo = tmp_path / "teams_repo"
    team_dir = repo / HOLDOUT_TEAMS_DIR
    team_dir.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "core.autocrlf", "false"], cwd=repo, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True)

    for i, team_id in enumerate(_six_teams()):
        (team_dir / f"{team_id}.txt").write_text(f"Fixture Mon {team_id} @ Focus Sash\n", encoding="utf-8")
        # Review-fix (Task-10 review P1 #3): combine now DERIVES each holdout team's species from
        # this real .packed file via load_team_species, instead of trusting a caller-supplied
        # species mapping -- so the packed content has to be genuinely parseable, with per-team
        # distinct species, not an inert placeholder.
        #
        # Species are keyed by INDEX, never by team_id: a species name containing the team_id
        # would, the moment a test copies it onto a reference team's packed file (see the
        # near-duplicate test), read to the leakage scanner as a real holdout identifier leaking
        # outside the allowlist -- a true positive from that guard, but about the fixture rather
        # than the code under test.
        (team_dir / f"{team_id}.packed").write_text(
            _candidate_packed(i), encoding="utf-8",
        )
    # Review-fix (Task-10 review P1 #3): the NINE canonical reference teams (five
    # panel_champions_v0 + four coverage foes) are no longer a caller-supplied species mapping
    # either -- combine reads them from their own real committed .packed files at the pinned
    # canonical paths. Any test that reaches the near-duplicate guard therefore needs them to
    # exist under this same teams_root, exactly like the six holdout teams above.
    for ref_id, ref_path in CANONICAL_REFERENCE_TEAM_PATHS.items():
        ref_file = repo / ref_path
        ref_file.parent.mkdir(parents=True, exist_ok=True)
        ref_file.write_text(f"Reference Mon {ref_id} @ Leftovers\n", encoding="utf-8")
        ref_file.with_suffix(".packed").write_text(
            f"|ReferenceMon{ref_id}A|||||||||]|ReferenceMon{ref_id}B|||||||||", encoding="utf-8",
        )
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "fixture holdout teams"], cwd=repo, check=True)

    hashes = {
        team_id: team_content_hash(str(repo), f"{HOLDOUT_TEAMS_DIR}{team_id}.txt")
        for team_id in _six_teams()
    }
    return str(repo), hashes


def _repo_head_sha(repo_root: str) -> str:
    """Review-fix (Task-10 review P1 #2): combine now refuses to run against a dirty tree and
    requires HEAD to equal the arms' recorded git_sha, so any test that reaches that guard for
    real needs the actual HEAD of the isolated fixture repo -- not the fixture's default
    "abc123" placeholder. Kept as its own helper so _write_holdout_teams_repo's existing
    two-value return contract (used by ~20 call sites) stays unchanged."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def _patch_upstream_verdicts_as_pass(monkeypatch):
    # Rev. 3 fix: patch the REAL functions combine_strength_holdout_arms actually calls (they
    # have their own full, independent RED/GREEN coverage in Task 7) -- not a same-named
    # production-unreachable stub (Rev. 2's `_all_guards_pass_for_test` bug). Patching at
    # strength_holdout_runner's own imported name is what actually intercepts the call, since
    # Python resolves the name in the CALLING module's namespace at call time.
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.verify_i8d_verdict_artifact", lambda **kw: {"verdict": "PASS"})
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.verify_coverage_verdict_artifact", lambda **kw: {"verdict": "PASS"})
    # Rev. 4 P1 fix: baseline drift is now unconditionally checked too (see Task 10's
    # implementation) -- load_baseline/verify_baseline are existing, independently-tested
    # eval/baseline.py functions (not reimplemented here), so orchestration tests patch them
    # the same way as the two verdict-artifact functions above, for the same reason.
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.load_baseline", lambda path: {"baseline_id": "fixture"})
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.verify_baseline", lambda baseline, **kw: [])
    # Review-fix (Task-10 review P1 #2): combine now refuses a dirty tree and requires
    # HEAD == the arms' git_sha. _git_is_dirty/_git_sha are subprocess boundary calls into git --
    # the same category as the two upstream verdict verifiers patched above -- and the ambient
    # worktree these tests run in is legitimately dirty (untracked local artifacts), so leaving
    # them live would make every orchestration test abort on an irrelevant, environment-dependent
    # condition. Patched here to the fixture's own default git_sha, and separately proven against
    # a REAL, clean, isolated git repo by the three dedicated tests at the end of this file
    # (clean+matching HEAD passes, dirty aborts, HEAD mismatch aborts) -- which deliberately do
    # NOT call this helper, so the guard itself is never mocked away from its own coverage.
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_is_dirty", lambda cwd=None: False)
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_sha", lambda cwd=None: "abc123")


def test_combine_does_not_require_matching_candidate_identity_between_arms(tmp_path, monkeypatch):
    # P1 fix (Rev. 3): make_candidate_identity hashes hero_agent, so arm A (heuristic) and arm B
    # (max_damage) NEVER share a candidate_identity for any genuine run -- DESIGN sec 5:
    # "Candidate A IS that shared candidate; Baseline B is the reference, not a separately-gated
    # candidate." This must succeed, not abort, despite the arms' candidate_identity differing.
    # Full valid success path, six real committed teams (Rev. 14, §1m, requirement 8): also now
    # exercises _assert_rows_bind_to_holdout_teams for real, not just the Rev. 13 checks.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)

    result = combine_strength_holdout_arms(
        arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
        i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
        holdout_content_hashes=hashes,
        stratum_env_override="windows", teams_root=teams_root,
        ledger_path=str(tmp_path / "ledger.jsonl"),
    )
    assert result["verdict"] in ("UNDERPOWERED", "GO", "NO-GO", "SAFETY-FAIL")  # ran to a real verdict, did not abort


def test_combine_publishes_near_duplicate_flags_without_aborting_or_gating_the_verdict(tmp_path, monkeypatch):
    # Rev. 18 fix (§1q) / DESIGN sec 3.3: a near-duplicate flag is a manual-review hint, never an
    # automatic reject.
    #
    # Review-fix (Task-10 review P1 #3): the overlap is now created in the REAL .packed files
    # both sides are derived from, not by handing combine two caller-built species dicts. One
    # canonical reference team's packed content is rewritten to carry the exact species of one
    # holdout candidate, so load_team_species independently derives overlap_fraction == 1.0 for
    # that pair -- the same "flags identical species sets" scenario as before, but now proving
    # the derivation path rather than a caller's assertion.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)
    first_candidate_id = sorted(holdout_teams)[0]
    duplicated_ref_id = sorted(CANONICAL_REFERENCE_TEAM_PATHS)[0]
    # Copy holdout candidate #0's exact species pair onto one reference team's packed file, so
    # load_team_species derives overlap_fraction == 1.0 for that pair from real content.
    Path(teams_root, CANONICAL_REFERENCE_TEAM_PATHS[duplicated_ref_id]).with_suffix(".packed").write_text(
        _candidate_packed(sorted(holdout_teams).index(first_candidate_id)), encoding="utf-8",
    )

    result = combine_strength_holdout_arms(
        arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
        i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
        holdout_content_hashes=hashes,
        stratum_env_override="windows", teams_root=teams_root,
        ledger_path=str(tmp_path / "ledger.jsonl"),
    )
    assert result["verdict"] in ("UNDERPOWERED", "GO", "NO-GO", "SAFETY-FAIL")  # not aborted
    flags = result["near_duplicate_flags"]
    assert len(flags) == 1
    assert flags[0]["candidate_team_id"] == first_candidate_id
    assert flags[0]["reference_team_id"] == duplicated_ref_id
    assert flags[0]["overlap_fraction"] == pytest.approx(1.0)


def test_combine_aborts_if_arms_disagree_on_git_sha(tmp_path, monkeypatch):
    # The replacement for Rev. 2's broken candidate_identity check: arms must share git_sha
    # (same commit) even though they never share candidate_identity.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", git_sha="sha-one")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", git_sha="sha-two", winner="villain")
    with pytest.raises(GateBAbort, match="git_sha"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
        stratum_env_override="windows",
            ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_if_arm_roles_are_swapped_or_wrong(tmp_path, monkeypatch):
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="max_damage", config_hash="cfgA")  # wrong: A must be heuristic
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="heuristic", config_hash="cfgB", winner="villain")
    with pytest.raises(GateBAbort, match="heuristic"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
        stratum_env_override="windows",
            ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_without_an_i8d_verdict_path_before_any_pairing_or_publish(tmp_path, monkeypatch):
    # P1 fix (Rev. 3): Gate B may only run after an I8-D PASS -- an empty/omitted path must
    # abort, not silently skip verification. Must fire before out_dir exists at all.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    out_dir = tmp_path / "combined"
    with pytest.raises(GateBAbort, match="i8d_verdict_path"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(out_dir),
            i8d_verdict_path="", coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
        stratum_env_override="windows",
            ledger_path=str(tmp_path / "ledger.jsonl"),
        )
    assert not out_dir.exists()


def test_combine_aborts_without_a_coverage_verdict_path_before_any_pairing_or_publish(tmp_path, monkeypatch):
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    out_dir = tmp_path / "combined"
    with pytest.raises(GateBAbort, match="coverage_verdict_path"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(out_dir),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path="",
            holdout_content_hashes=_fake_holdout_hashes(),
        stratum_env_override="windows",
            ledger_path=str(tmp_path / "ledger.jsonl"),
        )
    assert not out_dir.exists()


def test_combine_wraps_a_strength_holdout_run_error_from_i8d_verification(tmp_path, monkeypatch):
    # NF2 fix (Rev. 7): verify_i8d_verdict_artifact/verify_coverage_verdict_artifact raise
    # StrengthHoldoutRunError -- a class the CLI (Task 11) never caught, only GateBAbort. Force
    # the FIRST of the two calls to fail and confirm it is normalized to GateBAbort here, at the
    # only place StrengthHoldoutRunError can cross into combine_strength_holdout_arms.
    _patch_upstream_verdicts_as_pass(monkeypatch)

    def _raise_i8d_error(**kw):
        raise StrengthHoldoutRunError("fixture-forced I8-D verification failure")

    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.verify_i8d_verdict_artifact", _raise_i8d_error)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)
    out_dir = tmp_path / "combined"

    with pytest.raises(GateBAbort, match="upstream verdict verification failed"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(out_dir),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=hashes,
            stratum_env_override="windows", teams_root=teams_root, ledger_path=str(tmp_path / "ledger.jsonl"),
        )
    assert not out_dir.exists()


def test_combine_wraps_a_strength_holdout_run_error_from_coverage_verification(tmp_path, monkeypatch):
    # Same as above, but forcing the SECOND call (verify_coverage_verdict_artifact) -- proves the
    # try/except wraps both call sites, not just whichever one happens to run first.
    _patch_upstream_verdicts_as_pass(monkeypatch)

    def _raise_coverage_error(**kw):
        raise StrengthHoldoutRunError("fixture-forced Coverage verification failure")

    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.verify_coverage_verdict_artifact", _raise_coverage_error)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)
    out_dir = tmp_path / "combined"

    with pytest.raises(GateBAbort, match="upstream verdict verification failed"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(out_dir),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=hashes,
            stratum_env_override="windows", teams_root=teams_root, ledger_path=str(tmp_path / "ledger.jsonl"),
        )
    assert not out_dir.exists()


def test_combine_publishes_full_evidence_bundle_not_just_verdict_json(tmp_path, monkeypatch):
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", winner="hero", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)
    out_dir = tmp_path / "combined"

    combine_strength_holdout_arms(
        arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(out_dir),
        i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
        holdout_content_hashes=hashes,
        stratum_env_override="windows", teams_root=teams_root,
        ledger_path=str(tmp_path / "ledger.jsonl"),
    )

    assert (out_dir / "verdict.json").exists()
    assert (out_dir / "cells.json").exists()
    assert (out_dir / "arm_a" / "rows.jsonl").exists()
    assert (out_dir / "arm_b" / "rows.jsonl").exists()


def test_combine_appends_a_ledger_run_entry_with_all_real_required_fields(tmp_path, monkeypatch):
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)
    ledger_path = tmp_path / "ledger.jsonl"

    combine_strength_holdout_arms(
        arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
        i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
        holdout_content_hashes=hashes,
        stratum_env_override="windows", teams_root=teams_root,
        ledger_path=str(ledger_path),
    )

    entries = read_ledger(str(ledger_path))
    assert len(entries) == 1
    entry = entries[0]
    for field in ("kind", "date", "purpose", "panel_hash", "schedule_hash", "git_sha", "config_hash", "result_sha256", "justification"):
        assert field in entry, f"ledger entry missing required field {field!r}"
    assert entry["kind"] == "run"


def test_combine_refuses_a_repeat_config_hash_without_justification(tmp_path, monkeypatch):
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    ledger_path = tmp_path / "ledger.jsonl"
    arm_a = _write_arm(tmp_path, "arm_a1", hero_agent="heuristic", config_hash="dup-cfg", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b1", hero_agent="max_damage", config_hash="dup-cfg-b", winner="villain", holdout_teams=holdout_teams)
    combine_strength_holdout_arms(
        arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined1"),
        i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
        holdout_content_hashes=hashes,
        stratum_env_override="windows", teams_root=teams_root,
        ledger_path=str(ledger_path),
    )

    arm_a2 = _write_arm(tmp_path, "arm_a2", hero_agent="heuristic", config_hash="dup-cfg", holdout_teams=holdout_teams)
    arm_b2 = _write_arm(tmp_path, "arm_b2", hero_agent="max_damage", config_hash="dup-cfg-b", winner="villain", holdout_teams=holdout_teams)
    with pytest.raises(AccessBudgetError):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a2, arm_b_dir=arm_b2, out_dir=str(tmp_path / "combined2"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=hashes,
            stratum_env_override="windows", teams_root=teams_root,
            ledger_path=str(ledger_path),
        )


def test_combine_aborts_on_baseline_drift(tmp_path, monkeypatch):
    # P1 fix (Rev. 4): Task 6 creates/loads the baseline manifest, but nothing previously called
    # verify_baseline from the live combine flow. Patch load_baseline/verify_baseline directly
    # (not the umbrella helper) so THIS test proves the wiring actually calls verify_baseline
    # and reacts to a BaselineDriftError, rather than assuming it via the umbrella patch.
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.verify_i8d_verdict_artifact", lambda **kw: {"verdict": "PASS"})
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.verify_coverage_verdict_artifact", lambda **kw: {"verdict": "PASS"})
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.load_baseline", lambda path: {"baseline_id": "fixture"})

    from showdown_bot.eval.baseline import BaselineDriftError

    def _raise_drift(baseline, **kw):
        raise BaselineDriftError("fixture-forced drift")

    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.verify_baseline", _raise_drift)
    # Review-fix (Task-10 review P1 #2): this test patches the baseline functions directly rather
    # than via the umbrella helper, so it must patch the two git helpers itself as well -- the
    # HEAD-binding guard now runs before verify_baseline and would otherwise abort on the ambient
    # worktree being dirty, masking the baseline-drift path this test exists to prove.
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_is_dirty", lambda cwd=None: False)
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_sha", lambda cwd=None: "abc123")
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)
    out_dir = tmp_path / "combined"

    with pytest.raises(GateBAbort, match="baseline drift"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(out_dir),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=hashes,
            stratum_env_override="windows", teams_root=teams_root, ledger_path=str(tmp_path / "ledger.jsonl"),
        )
    assert not out_dir.exists()


def test_combine_wraps_a_non_missing_pair_error_too(tmp_path, monkeypatch):
    # P2 fix (Rev. 4): pair_runs can raise several PairingError subclasses -- Rev. 3 only
    # caught MissingPairError. Force a DIFFERENT subclass (DuplicateRowError, via a duplicate
    # battle_id/config_hash pair in arm A's own rows) and confirm it still becomes GateBAbort.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)
    # Review-fix (Task-10 review P1 #1): this test used to duplicate a row inside arm A to force
    # a DuplicateRowError out of the real pair_runs. That is no longer reachable -- the new
    # canonical-schedule guard rejects "two rows claim the same battle key" strictly earlier, by
    # design. The behaviour under test here is the EXCEPT clause (every PairingError subclass,
    # not just MissingPairError, is folded into GateBAbort), so the error is now injected at the
    # pair_runs seam directly, with two otherwise-valid canonical arms.
    from showdown_bot.eval.pairing import DuplicateRowError

    def _raise_duplicate(rows_a, rows_b, *, expected_rows):
        raise DuplicateRowError("fixture-forced duplicate row")

    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.pair_runs", _raise_duplicate)

    with pytest.raises(GateBAbort, match="pairing failed"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined2"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=hashes,
            stratum_env_override="windows", teams_root=teams_root, ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_rejects_empty_holdout_content_hashes(tmp_path, monkeypatch):
    # P2 fix (Rev. 4): an empty mapping makes the disjointness/leakage guards vacuous in
    # production just as much as in a test -- reject it unconditionally.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    with pytest.raises(GateBAbort, match="holdout_content_hashes"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes={},
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_if_an_arms_manifest_does_not_match_its_own_rows(tmp_path, monkeypatch):
    # F3 fix (Rev. 6): an arm directory assembled from two different runs (here: arm A's
    # manifest swapped for one with a different config_hash than its own rows.jsonl actually
    # carries) must abort -- before this fix it passed I8-D verification, Coverage verification,
    # check_access, the ledger entry, and the published verdict unnoticed.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")

    # Swap in a manifest whose config_hash doesn't match what's actually in arm_a/rows.jsonl.
    manifest_path = tmp_path / "arm_a" / "arm_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["config_hash"] = "a-completely-different-config-hash-from-another-run"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(GateBAbort, match="config_hash"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_cleanly_on_a_malformed_row_not_a_raw_resultrowerror(tmp_path, monkeypatch):
    # NF1 fix (Rev. 7): _read_arm's validate_battle_row call can raise ResultRowError -- before
    # this fix that exception was never imported or caught anywhere in this module, so a
    # corrupted or stale-schema rows.jsonl would escape combine_strength_holdout_arms raw,
    # uncaught by the CLI (which only ever catches GateBAbort). Corrupt one row in arm A by
    # deleting a required field (result_jsonl.REQUIRED_FIELDS includes "turns") and confirm the
    # abort is GateBAbort, not ResultRowError.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")

    rows_path = tmp_path / "arm_a" / "rows.jsonl"
    lines = rows_path.read_text(encoding="utf-8").splitlines()
    first_row = json.loads(lines[0])
    del first_row["turns"]
    lines[0] = json.dumps(first_row, sort_keys=True, separators=(",", ":"))
    rows_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(GateBAbort, match="malformed row"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_cleanly_on_a_manifest_missing_a_required_key_not_a_raw_keyerror(tmp_path, monkeypatch):
    # NF1 fix (Rev. 7): _assert_rows_match_manifest used to index manifest["n_rows"]/
    # manifest[field] directly -- a truncated or hand-edited manifest missing any of those keys
    # raised a raw KeyError, uncaught by the CLI. Delete "panel_hash" (also required one step
    # further downstream by pairing.py's own _check_constant_fields) and confirm the abort is
    # GateBAbort, not KeyError.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")

    manifest_path = tmp_path / "arm_a" / "arm_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    del manifest["panel_hash"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(GateBAbort, match="missing required key"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_cleanly_when_an_arm_directory_is_missing_not_a_raw_oserror(tmp_path, monkeypatch):
    # Self-found while building the Rev. 7 exception-audit table (§1f): _read_arm's open() calls
    # can raise FileNotFoundError (an OSError) for a missing/never-published arm directory --
    # not ResultRowError, so NF1's own fix does not catch it. Confirm the abort is GateBAbort,
    # not a raw OSError.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")

    with pytest.raises(GateBAbort, match="cannot read arm directory"):
        combine_strength_holdout_arms(
            arm_a_dir=str(tmp_path / "arm_a_never_published"), arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_cleanly_on_truncated_json_not_a_raw_jsondecodeerror(tmp_path, monkeypatch):
    # Same audit finding as above, the json.JSONDecodeError branch: a truncated/corrupted
    # arm_manifest.json must abort as GateBAbort, not escape as json.JSONDecodeError.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    (tmp_path / "arm_a" / "arm_manifest.json").write_text("{not valid json", encoding="utf-8")

    with pytest.raises(GateBAbort, match="malformed JSON"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_does_not_publish_if_the_ledger_append_fails(tmp_path, monkeypatch):
    # F6 fix (Rev. 6): the ledger entry now happens BEFORE publish -- if append_entry fails for
    # any reason, out_dir must never come into existence, so a failed ledger write can never
    # coexist with a "successful"-looking published bundle the next run's check_access wouldn't
    # even know to budget against.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)
    out_dir = tmp_path / "combined"

    from showdown_bot.eval.heldout_ledger import LedgerError

    def _raise_ledger_error(path, entry):
        raise LedgerError("fixture-forced ledger failure")

    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.append_entry", _raise_ledger_error)

    with pytest.raises(GateBAbort, match="ledger"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(out_dir),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=hashes,
            stratum_env_override="windows", teams_root=teams_root, ledger_path=str(tmp_path / "ledger.jsonl"),
        )
    assert not out_dir.exists()


def test_combine_aborts_if_holdout_content_hashes_omits_a_scheduled_team(tmp_path, monkeypatch):
    # P1 fix (Rev. 13, §1l, second review round): holdout_content_hashes being non-empty is not
    # enough -- it must cover every team the schedule actually played, or the leakage/
    # disjointness guards below would silently scan only whichever subset a caller happened to
    # supply. Both arms agree on all six teams (the _write_arm default); holdout_content_hashes
    # here covers only one of them. No real teams_repo needed -- this abort fires before the
    # leakage scan ever runs.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    with pytest.raises(GateBAbort, match="does not match the six teams"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes={"holdout_0": "fakehash1111aaaa"},
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_if_holdout_content_hashes_has_a_wrong_value_for_a_correct_key(tmp_path, monkeypatch):
    # P1 fix (Rev. 14, §1m, third review round): Rev. 13 only checked KEY-set equality between
    # holdout_content_hashes and the schedule's real team set -- a caller supplying every right
    # team_id but a WRONG hash value for one of them would have passed that check. The comparison
    # is now full dict equality (keys AND values).
    _patch_upstream_verdicts_as_pass(monkeypatch)
    holdout_teams = _fake_holdout_teams()
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)
    wrong_value_hashes = {t: e["content_hash"] for t, e in holdout_teams.items()}
    wrong_value_hashes[sorted(holdout_teams)[0]] = "totally-wrong-hash-value"
    with pytest.raises(GateBAbort, match="does not match the six teams"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=wrong_value_hashes,
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_if_arms_disagree_on_holdout_teams(tmp_path, monkeypatch):
    # P1 fix (Rev. 13/14, §1l/§1m): holdout_teams is part of the same arm-vs-arm agreement check
    # as schedule_hash/panel_hash/seed_base -- two arms that somehow scheduled a different team
    # set were not played under the same battle conditions. Each entry in mismatched_teams is
    # itself internally well-formed (_holdout_teams_mapping derives team_path from its own key),
    # so only the arm-vs-arm inequality fires here, not the structural/canonical-path checks.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    default_teams = _fake_holdout_teams()
    mismatched_ids = _six_teams()[:5] + ["holdout_other"]
    mismatched_teams = _holdout_teams_mapping({tid: f"{i:016x}" for i, tid in enumerate(mismatched_ids)})
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain",
                        holdout_teams=mismatched_teams)
    with pytest.raises(GateBAbort, match="holdout_teams"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes={t: e["content_hash"] for t, e in default_teams.items()},

            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_if_both_manifests_claim_wrong_teams_but_rows_are_unchanged(tmp_path, monkeypatch):
    # P1 fix (Rev. 14, §1m, third review round): a manifest's holdout_teams is just an assertion
    # until bound to the rows -- if BOTH arms' manifests agree with EACH OTHER (so an arm-vs-arm
    # check alone would pass) but neither actually matches what's in rows.jsonl (still the
    # normal, real per-team data from _write_arm), the leakage/disjointness guards would scan for
    # the WRONG six teams while the REAL opponent teams go completely unchecked.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")

    wrong_teams = _holdout_teams_mapping({f"wrong_{i}": f"{i:016x}" for i in range(6)})
    for arm_dir in (tmp_path / "arm_a", tmp_path / "arm_b"):
        manifest_path = arm_dir / "arm_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["holdout_teams"] = wrong_teams
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(GateBAbort, match="not one of the six"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes={t: e["content_hash"] for t, e in wrong_teams.items()},

            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_if_a_rows_opp_team_hash_does_not_match_the_manifest(tmp_path, monkeypatch):
    # P1 fix (Rev. 14, §1m): a manifest can declare the CORRECT team_id/team_path for a team
    # while lying about its content_hash -- only binding opp_team_hash per row catches this; a
    # bare ID (or even a team_path-only mapping) never would.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    manifest_path = tmp_path / "arm_a" / "arm_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    first_team_id = sorted(manifest["holdout_teams"])[0]
    manifest["holdout_teams"][first_team_id]["content_hash"] = "wrong-hash-not-in-rows"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(GateBAbort, match="does not match holdout_teams"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_if_a_manifest_team_path_is_not_canonical(tmp_path, monkeypatch):
    # P1 fix (Rev. 14, §1m): a manifest could declare the right team_id and a content_hash that
    # matches its own rows, but point team_path at a non-canonical location -- rejected by
    # _validate_holdout_teams_mapping before any row-binding check even runs.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    manifest_path = tmp_path / "arm_a" / "arm_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    first_team_id = sorted(manifest["holdout_teams"])[0]
    manifest["holdout_teams"][first_team_id]["team_path"] = "showdown_bot/teams/wrong_dir/not_canonical.txt"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(GateBAbort, match="canonical path"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_if_one_row_has_an_unknown_opponent_path(tmp_path, monkeypatch):
    # P1 fix (Rev. 14, §1m): the manifest itself may be perfectly valid and match every OTHER
    # row -- a single corrupted row with an opp_team_path outside the declared six must still
    # abort, not slip through because most rows are fine.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    rows_path = tmp_path / "arm_a" / "rows.jsonl"
    lines = rows_path.read_text(encoding="utf-8").splitlines()
    first_row = json.loads(lines[0])
    first_row["opp_team_path"] = "showdown_bot/teams/panel_champions_v0/not_a_holdout_team.txt"
    lines[0] = json.dumps(first_row, sort_keys=True, separators=(",", ":"))
    rows_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(GateBAbort, match="not one of the six"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_if_a_manifest_team_never_appears_in_rows(tmp_path, monkeypatch):
    # P1 fix (Rev. 14, §1m): a manifest declaring six teams is not enough if one of them never
    # actually appears among the rows -- e.g. a battle silently never got played for that team,
    # or every row for it got corrupted/overwritten. The leakage/disjointness guards must never
    # trust a declared team that isn't backed by at least one real row.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    holdout_teams = _fake_holdout_teams()
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", n=12, holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", n=12, holdout_teams=holdout_teams)
    # Overwrite every row that would have represented team_ids[5] (rows 5 and 11 -- n=12 cycling
    # 6 teams puts that team at both positions) with team_ids[0]'s data instead: team_ids[5] is
    # still fully declared in the manifest, but now appears in zero rows.
    rows_path = tmp_path / "arm_a" / "rows.jsonl"
    lines = rows_path.read_text(encoding="utf-8").splitlines()
    lines[5] = lines[0]
    lines[11] = lines[0]
    rows_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(GateBAbort, match="never appear in rows"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes={t: e["content_hash"] for t, e in holdout_teams.items()},

            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_if_holdout_teams_has_an_invalid_shape(tmp_path, monkeypatch):
    # P1 fix (Rev. 14, §1m): holdout_teams must be a genuine object/mapping with exactly the
    # expected shape -- null, a bare string, an array, or a mapping whose entries carry
    # unexpected fields must all be rejected fail-closed, before any row-binding check even
    # attempts to read it.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    valid_teams = _fake_holdout_teams()
    first_id = sorted(valid_teams)[0]
    malformed_shapes = {
        "null": None,
        "string": ",".join(sorted(valid_teams)),
        "array": sorted(valid_teams),
        "unknown_field": {**valid_teams, first_id: {**valid_teams[first_id], "extra_field": "x"}},
    }
    for label, shape in malformed_shapes.items():
        arm_a = _write_arm(tmp_path, f"arm_a_{label}", hero_agent="heuristic", config_hash="cfgA")
        arm_b = _write_arm(tmp_path, f"arm_b_{label}", hero_agent="max_damage", config_hash="cfgB", winner="villain")
        manifest_path = tmp_path / f"arm_a_{label}" / "arm_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["holdout_teams"] = shape
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with pytest.raises(GateBAbort, match="holdout_teams"):
            combine_strength_holdout_arms(
                arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / f"combined_{label}"),
                i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
                holdout_content_hashes=_fake_holdout_hashes(),
                stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
            )


# Rev. 15 (§1n, Task-3-review): Task 9 now writes stratum/platform_attestation/date_stratum_id
# into each arm's own manifest (its own Rev. 15 fix); the six tests below prove Task 10 validates
# them in closed form and compares the two ACTUAL arm records, never re-determining its own
# stratum from detect_stratum().


def test_combine_rejects_mixed_windows_and_kaggle_arms(tmp_path, monkeypatch):
    # P1 #3: "different strata... must abort" -- arm A played on Windows, arm B on Kaggle, must
    # never combine even though every other field agrees.
    from showdown_bot.eval.strata_guard import StrataPoolingError
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA",
                        holdout_teams=holdout_teams, stratum="windows")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain",
                        holdout_teams=holdout_teams, stratum="kaggle")

    with pytest.raises(StrataPoolingError):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=hashes,
            teams_root=teams_root, ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_accepts_two_equally_attested_arms(tmp_path, monkeypatch):
    # Required test: the mirror image of the rejection above -- two arms sharing one stratum,
    # each with its own non-empty platform_attestation, must combine successfully.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA",
                        holdout_teams=holdout_teams, stratum="windows",
                        platform_attestation="Windows-11-10.0.26200")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain",
                        holdout_teams=holdout_teams, stratum="windows",
                        platform_attestation="Windows-11-10.0.26200")

    result = combine_strength_holdout_arms(
        arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
        i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
        holdout_content_hashes=hashes,
        teams_root=teams_root, ledger_path=str(tmp_path / "ledger.jsonl"),
    )
    assert result["stratum"] == "windows"


def test_combine_rejects_a_contradictory_stratum_override(tmp_path, monkeypatch):
    # Required test: both arms genuinely agree (windows/windows), but the caller-supplied
    # stratum_env_override="kaggle" contradicts what they actually recorded -- must abort, not
    # silently force a mismatched label onto real data.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA",
                        holdout_teams=holdout_teams, stratum="windows")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain",
                        holdout_teams=holdout_teams, stratum="windows")

    with pytest.raises(GateBAbort, match="contradicts"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=hashes,
            stratum_env_override="kaggle", teams_root=teams_root, ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_if_arms_disagree_on_date_stratum_id(tmp_path, monkeypatch):
    # P1 #3: "different... date-strata must abort" -- same stratum (windows/windows, so
    # assert_no_cross_stratum_pooling alone would NOT catch this) but two different pre-
    # registered run identifiers must still never combine.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA",
                        date_stratum_id="run-2026-07-01")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain",
                        date_stratum_id="run-2026-08-01")

    with pytest.raises(GateBAbort, match="date_stratum_id"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_on_an_unknown_stratum_value(tmp_path, monkeypatch):
    # P1 #4: "unknown... manifest values must abort" -- a stratum value present but not one of
    # strata_guard.VALID_STRATA (a hand-edited or future-format manifest) must be rejected in
    # closed form, not silently accepted or crash downstream with a raw KeyError/ValueError.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    manifest_path = tmp_path / "arm_a" / "arm_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["stratum"] = "colab"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(GateBAbort, match="not one of the known strata"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_on_a_type_wrong_platform_attestation(tmp_path, monkeypatch):
    # P1 #4: "type-wrong manifest values must abort" -- a non-string platform_attestation (an
    # accidental int from a hand-edited or differently-typed manifest) must be rejected, not
    # silently accepted or crash the StratumRecord construction downstream unclearly.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    manifest_path = tmp_path / "arm_a" / "arm_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["platform_attestation"] = 12345
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(GateBAbort, match="platform_attestation"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


# Rev. 19 (Task 9 review-fix sync, §1r): Task 9's own review-fix (5 P1s) added calc_backend
# (derived internally, threaded through) and replaced the caller-local seed_log_path field with a
# four-field seed PROOF (seed_log_relpath/seed_log_sha256/seed_log_n_lines/seed_log_verified) --
# the thirteen tests below prove Task 10 validates the new fields in closed form, independently
# re-verifies both arms' real seed-log bytes (never trusting seed_log_verified=True alone), and
# passes the manifest-bound calc_backend to both upstream verifiers instead of a hardcoded
# "oneshot" literal.

def test_combine_aborts_if_manifest_is_missing_calc_backend(tmp_path, monkeypatch):
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    manifest_path = tmp_path / "arm_a" / "arm_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    del manifest["calc_backend"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(GateBAbort, match="missing required key"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_if_arms_disagree_on_calc_backend(tmp_path, monkeypatch):
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", calc_backend="oneshot")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", calc_backend="persistent")

    with pytest.raises(GateBAbort, match="calc_backend"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_passes_the_manifest_bound_calc_backend_to_both_upstream_verifiers(tmp_path, monkeypatch):
    # Proves the fix directly: mocks capture the kwargs each upstream verifier was actually
    # called with, using a NON-DEFAULT backend ("persistent") so a hardcoded "oneshot" literal
    # would be caught red-handed, not accidentally matched by coincidence.
    calls = {}

    def _capture_i8d(**kw):
        calls["i8d"] = kw
        return {"verdict": "PASS"}

    def _capture_coverage(**kw):
        calls["coverage"] = kw
        return {"verdict": "PASS"}

    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.verify_i8d_verdict_artifact", _capture_i8d)
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.verify_coverage_verdict_artifact", _capture_coverage)
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.load_baseline", lambda path: {"baseline_id": "fixture"})
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.verify_baseline", lambda baseline, **kw: [])
    # Review-fix (Task-10 review P1 #2): this test installs its own capturing verifiers instead of
    # the umbrella helper, so it must stub the two git helpers itself -- the HEAD-binding guard
    # runs before the verifiers and would otherwise abort on the ambient dirty worktree.
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_is_dirty", lambda cwd=None: False)
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner._git_sha", lambda cwd=None: "abc123")
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA",
                        holdout_teams=holdout_teams, calc_backend="persistent")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain",
                        holdout_teams=holdout_teams, calc_backend="persistent")

    combine_strength_holdout_arms(
        arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
        i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
        holdout_content_hashes=hashes,
        stratum_env_override="windows", teams_root=teams_root, ledger_path=str(tmp_path / "ledger.jsonl"),
    )
    assert calls["i8d"]["calc_backend"] == "persistent"
    assert calls["coverage"]["calc_backend"] == "persistent"


def test_combine_aborts_if_manifest_is_missing_a_seed_proof_field(tmp_path, monkeypatch):
    _patch_upstream_verdicts_as_pass(monkeypatch)
    for field in ("seed_log_relpath", "seed_log_sha256", "seed_log_n_lines", "seed_log_verified"):
        arm_a = _write_arm(tmp_path, f"arm_a_{field}", hero_agent="heuristic", config_hash="cfgA")
        arm_b = _write_arm(tmp_path, f"arm_b_{field}", hero_agent="max_damage", config_hash="cfgB", winner="villain")
        manifest_path = tmp_path / f"arm_a_{field}" / "arm_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        del manifest[field]
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        with pytest.raises(GateBAbort, match="missing required key"):
            combine_strength_holdout_arms(
                arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / f"combined_{field}"),
                i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
                holdout_content_hashes=_fake_holdout_hashes(),
                stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
            )


def test_combine_aborts_if_seed_log_verified_is_not_true(tmp_path, monkeypatch):
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    manifest_path = tmp_path / "arm_a" / "arm_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["seed_log_verified"] = False
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(GateBAbort, match="seed_log_verified"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_on_an_absolute_seed_log_relpath(tmp_path, monkeypatch):
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    manifest_path = tmp_path / "arm_a" / "arm_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["seed_log_relpath"] = str(tmp_path / "arm_a" / "seeds.jsonl")  # absolute, not "seeds.jsonl"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(GateBAbort, match="seed_log_relpath"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_on_a_traversing_seed_log_relpath(tmp_path, monkeypatch):
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    manifest_path = tmp_path / "arm_a" / "arm_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["seed_log_relpath"] = "../seeds.jsonl"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(GateBAbort, match="seed_log_relpath"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_if_the_seed_log_file_is_missing(tmp_path, monkeypatch):
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    (tmp_path / "arm_a" / "seeds.jsonl").unlink()

    with pytest.raises(GateBAbort, match="cannot read seed log"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_if_the_seed_log_sha256_does_not_match(tmp_path, monkeypatch):
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    manifest_path = tmp_path / "arm_a" / "arm_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["seed_log_sha256"] = "0" * 64  # a well-formed but wrong digest
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(GateBAbort, match="does not match manifest's seed_log_sha256"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_if_the_seed_log_content_fails_verify_seed_log(tmp_path, monkeypatch):
    # The sha256 is recomputed to match the CORRUPTED content, isolating this test to
    # verify_seed_log's own content check (wrong seed_base recorded in every line), not the
    # digest check above.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    from showdown_bot.eval.seeding import derive_battle_seed as _dbs
    corrupted_text = "".join(
        json.dumps({"battle_index": i, "seed": _dbs("wrong-seed-base-recorded", i), "seed_base": "wrong-seed-base-recorded"}) + "\n"
        for i in range(12)
    )
    (tmp_path / "arm_a" / "seeds.jsonl").write_text(corrupted_text, encoding="utf-8", newline="\n")
    manifest_path = tmp_path / "arm_a" / "arm_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["seed_log_sha256"] = hashlib.sha256(corrupted_text.encode("utf-8")).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(GateBAbort, match="seed-log verification failed"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_if_seed_log_n_lines_does_not_match_the_verified_count(tmp_path, monkeypatch):
    # manifest claims n_rows=12 (matching rows.jsonl, so verify_seed_log's own expected_count
    # check passes) but seed_log_n_lines is a DIFFERENT, wrong number -- isolates the SEPARATE
    # seed_log_n_lines-vs-verified-count check from the n_rows-bound expected_count check inside
    # verify_seed_log itself.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    manifest_path = tmp_path / "arm_a" / "arm_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["seed_log_n_lines"] = 179
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(GateBAbort, match="seed_log_n_lines"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_aborts_if_the_seed_log_line_count_does_not_match_n_rows(tmp_path, monkeypatch):
    # The seed log genuinely verifies against seed_base, but has a DIFFERENT line count than
    # n_rows -- verify_seed_log's own expected_count=manifest["n_rows"] parameter must catch this
    # (SeedLogError, wrapped as GateBAbort), not just the separate seed_log_n_lines check.
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    from showdown_bot.eval.seeding import derive_battle_seed as _dbs
    # 179 lines (not 180) -- still genuinely verifiable seeds, just the wrong count vs n_rows.
    short_text = "".join(
        json.dumps({"battle_index": i, "seed": _dbs("champions-strength-holdout-v0", i), "seed_base": "champions-strength-holdout-v0"}) + "\n"
        for i in range(179)
    )
    (tmp_path / "arm_a" / "seeds.jsonl").write_text(short_text, encoding="utf-8", newline="\n")
    manifest_path = tmp_path / "arm_a" / "arm_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["seed_log_sha256"] = hashlib.sha256(short_text.encode("utf-8")).hexdigest()
    manifest["seed_log_n_lines"] = 179
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(GateBAbort, match="seed-log verification failed"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def test_combine_verifies_both_arms_seed_logs_independently(tmp_path, monkeypatch):
    # Arm A's seed log is genuinely valid; ONLY arm B's is corrupted. Must still abort -- proves
    # both arms are independently re-verified, not just arm A (or only checked once via shared
    # manifest agreement).
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)
    manifest_path = tmp_path / "arm_b" / "arm_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["seed_log_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(GateBAbort, match="does not match manifest's seed_log_sha256"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=hashes,
            stratum_env_override="windows", teams_root=teams_root, ledger_path=str(tmp_path / "ledger.jsonl"),
        )


def _make_windows_junction(link_path, target_path):
    """Creates a Windows directory junction via mklink /J -- unlike symlinks, this needs no
    admin privilege / Developer Mode. Raises OSError on failure. Mirrors Task 9's own
    _make_windows_junction helper."""
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link_path), str(target_path)],
        capture_output=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        raise OSError(f"mklink /J failed (rc={result.returncode}): {result.stdout} {result.stderr}")


def test_combine_rejects_a_seed_log_symlink_escape_from_the_arm_directory(tmp_path, monkeypatch):
    import os as _os
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")

    escape_target_dir = tmp_path / "outside_arm_a"
    escape_target_dir.mkdir()
    real_seed_log = tmp_path / "arm_a" / "seeds.jsonl"
    escape_target = escape_target_dir / "seeds.jsonl"
    escape_target.write_text(real_seed_log.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    real_seed_log.unlink()
    try:
        _os.symlink(str(escape_target), str(real_seed_log))
    except OSError:
        try:
            _make_windows_junction(real_seed_log, escape_target)
        except OSError as exc:
            pytest.skip(
                "neither os.symlink nor mklink /J is available in this test environment "
                f"(insufficient privilege) -- cannot exercise a real link escape: {exc}"
            )

    # The symlink points to a byte-identical copy, so sha256/verify_seed_log both still pass --
    # the containment check must fire regardless, on the resolved location alone. Self-found:
    # Windows can raise a raw OSError (WinError 267) while RESOLVING certain symlink
    # configurations, before the containment comparison itself ever runs -- both outcomes are
    # an acceptable, fail-closed rejection of the escape attempt (never a raw traceback, never a
    # silent accept), so the match covers either message.
    with pytest.raises(GateBAbort, match="outside its own arm directory|cannot resolve seed log path"):
        combine_strength_holdout_arms(
            arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
            i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
            holdout_content_hashes=_fake_holdout_hashes(),
            stratum_env_override="windows", ledger_path=str(tmp_path / "ledger.jsonl"),
        )


# ---------------------------------------------------------------------------
# Task-10 review-fix (three P1s + two P2s). Every test below goes RED against
# 24ada4b and closes exactly one reviewed finding.
# ---------------------------------------------------------------------------


def _combine_kwargs(tmp_path, arm_a, arm_b, teams_root, hashes, **overrides):
    """The full valid argument set for a far-reaching combine call, so the review-fix tests
    below differ only in the ONE thing each is about."""
    kwargs = dict(
        arm_a_dir=arm_a, arm_b_dir=arm_b, out_dir=str(tmp_path / "combined"),
        i8d_verdict_path=str(tmp_path / "i8d.json"), coverage_verdict_path=str(tmp_path / "cov.json"),
        holdout_content_hashes=hashes, stratum_env_override="windows", teams_root=teams_root,
        ledger_path=str(tmp_path / "ledger.jsonl"),
    )
    kwargs.update(overrides)
    return kwargs


# --- P1 #1: the canonical 180-battle-key schedule must be rebuilt and bound ------------------


def test_combine_accepts_two_real_canonical_180_key_arms(tmp_path, monkeypatch):
    """P1 #1 baseline: the DEFAULT fixture arm is now a real 180-row canonical arm, and the
    success path still runs to a real verdict through the new schedule guard."""
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)
    # The fixture really did emit the full canonical schedule, not a 12-row stand-in.
    with open(Path(arm_a) / "arm_manifest.json", encoding="utf-8") as fh:
        assert json.load(fh)["n_rows"] == 180

    result = combine_strength_holdout_arms(**_combine_kwargs(tmp_path, arm_a, arm_b, teams_root, hashes))
    assert result["n_total"] == 180


def test_combine_aborts_on_a_truncated_arm_that_omits_battle_keys(tmp_path, monkeypatch):
    """P1 #1, the exact hole the review found: two arms that AGREE with each other and with
    their own manifests, but only carry 12 of the canonical 180 battle keys, were accepted.
    A short arm is not a strength result at all -- it must abort."""
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams, n=179)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams, n=179)

    with pytest.raises(GateBAbort, match="canonical|180|battle key"):
        combine_strength_holdout_arms(**_combine_kwargs(tmp_path, arm_a, arm_b, teams_root, hashes))
    assert not os.path.exists(str(tmp_path / "combined"))


def test_combine_aborts_if_the_manifest_schedule_hash_is_not_the_canonical_rebuild(tmp_path, monkeypatch):
    """P1 #1: schedule_hash must be the value build_strength_holdout_schedule itself derives from
    the manifest's own team_ids/panel_hash/seed_base -- a self-consistent but forged label
    (stamped identically on the manifest AND every row of BOTH arms) must not pass."""
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA",
                       holdout_teams=holdout_teams, schedule_hash="0123456789abcdef")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain",
                       holdout_teams=holdout_teams, schedule_hash="0123456789abcdef")

    with pytest.raises(GateBAbort, match="schedule_hash"):
        combine_strength_holdout_arms(**_combine_kwargs(tmp_path, arm_a, arm_b, teams_root, hashes))


def test_combine_aborts_on_an_unpinned_seed_base(tmp_path, monkeypatch):
    """P1 #1: the rebuild is fed the manifest's OWN seed_base, so that one field must be checked
    separately against the pinned namespace -- otherwise a foreign seed_base rebuilds
    self-consistently and the check is vacuous (Task 9's _assert_schedule_is_genuine makes the
    same distinction for the same reason)."""
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA",
                       holdout_teams=holdout_teams, seed_base="not-the-pinned-namespace")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain",
                       holdout_teams=holdout_teams, seed_base="not-the-pinned-namespace")

    with pytest.raises(GateBAbort, match="seed_base"):
        combine_strength_holdout_arms(**_combine_kwargs(tmp_path, arm_a, arm_b, teams_root, hashes))


def test_combine_aborts_if_a_row_does_not_match_its_canonical_battle_key(tmp_path, monkeypatch):
    """P1 #1: the right NUMBER of rows is not enough -- each row must correspond to exactly one
    real battle key. Here one row's opp_policy is flipped, so the played set no longer covers
    the canonical (team, policy, seed_index) grid even though the count still says 180."""
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)
    rows_path = Path(arm_a) / "rows.jsonl"
    rows = [json.loads(line) for line in rows_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows[0]["opp_policy"] = "max_damage" if rows[0]["opp_policy"] == "heuristic" else "heuristic"
    with open(rows_path, "w", encoding="utf-8", newline="") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")

    with pytest.raises(GateBAbort, match="battle key|canonical"):
        combine_strength_holdout_arms(**_combine_kwargs(tmp_path, arm_a, arm_b, teams_root, hashes))


# --- P1 #2: the combine result must be bound to a clean, matching HEAD -----------------------


def _patch_non_git_dependencies(monkeypatch):
    """Everything _patch_upstream_verdicts_as_pass patches EXCEPT the two git helpers -- so the
    three HEAD-binding tests below exercise the real _git_is_dirty/_git_sha against a real,
    isolated git repo instead of a stub."""
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.verify_i8d_verdict_artifact", lambda **kw: {"verdict": "PASS"})
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.verify_coverage_verdict_artifact", lambda **kw: {"verdict": "PASS"})
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.load_baseline", lambda path: {"baseline_id": "fixture"})
    monkeypatch.setattr("showdown_bot.eval.strength_holdout_runner.verify_baseline", lambda baseline, **kw: [])


def test_combine_accepts_a_clean_repo_whose_head_matches_the_arms(tmp_path, monkeypatch):
    """P1 #2, positive half -- deliberately does NOT patch _git_is_dirty/_git_sha: the REAL git
    calls run against the real, clean, isolated fixture repo, whose real HEAD is what both arms
    recorded."""
    _patch_non_git_dependencies(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    head = _repo_head_sha(teams_root)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams, git_sha=head)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams, git_sha=head)

    result = combine_strength_holdout_arms(
        **_combine_kwargs(tmp_path, arm_a, arm_b, teams_root, hashes, repo_root=teams_root)
    )
    assert result["git_sha"] == head


def test_combine_refuses_a_dirty_working_tree(tmp_path, monkeypatch):
    """P1 #2: baseline/leakage/report checks read the CURRENT checkout, so an uncommitted change
    can silently alter what those guards see while the published bundle is still labelled with
    the arms' old git_sha. Real git, real dirty repo, no patching of the guard itself."""
    _patch_non_git_dependencies(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    head = _repo_head_sha(teams_root)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams, git_sha=head)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams, git_sha=head)
    Path(teams_root, "uncommitted_change.txt").write_text("dirty\n", encoding="utf-8")

    with pytest.raises(GateBAbort, match="dirty"):
        combine_strength_holdout_arms(
            **_combine_kwargs(tmp_path, arm_a, arm_b, teams_root, hashes, repo_root=teams_root)
        )
    assert not os.path.exists(str(tmp_path / "combined"))


def test_combine_refuses_when_head_does_not_match_the_arms_git_sha(tmp_path, monkeypatch):
    """P1 #2: a clean tree is not enough -- combining arms played at commit X while the checkout
    sits at commit Y would run the repo-dependent guards against Y and label the result X."""
    _patch_non_git_dependencies(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    # Both arms claim a DIFFERENT commit than the repo's real HEAD.
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams, git_sha="f" * 40)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams, git_sha="f" * 40)

    with pytest.raises(GateBAbort, match="HEAD"):
        combine_strength_holdout_arms(
            **_combine_kwargs(tmp_path, arm_a, arm_b, teams_root, hashes, repo_root=teams_root)
        )


# --- P1 #3: species evidence must come from the real .packed files ---------------------------


def test_combine_derives_both_species_sides_from_real_packed_files(tmp_path, monkeypatch):
    """P1 #3: holdout_candidate_species/reference_species were caller assertions and
    load_team_species had no production call site at all. Both sides are now derived from real
    sealed files -- proven here by recording every path load_team_species is asked for and
    checking it is exactly the six row-bound holdout teams plus the nine canonical references."""
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)

    from showdown_bot.eval import strength_holdout_runner as mod
    real_loader = mod.load_team_species
    asked = []

    def _recording_loader(team_path, *, teams_root):
        asked.append(team_path)
        return real_loader(team_path, teams_root=teams_root)

    monkeypatch.setattr(mod, "load_team_species", _recording_loader)

    combine_strength_holdout_arms(**_combine_kwargs(tmp_path, arm_a, arm_b, teams_root, hashes))

    expected_holdout = {entry["team_path"] for entry in holdout_teams.values()}
    expected_reference = set(CANONICAL_REFERENCE_TEAM_PATHS.values())
    assert len(expected_reference) == 9
    assert set(asked) == expected_holdout | expected_reference


def test_combine_aborts_if_a_holdout_teams_packed_file_is_missing(tmp_path, monkeypatch):
    """P1 #3: with species now DERIVED, an unreadable sealed team is a real, fail-closed abort
    (load_team_species raises ValueError) -- not something a caller can paper over by supplying
    a species list for a file that is not there."""
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)
    victim = sorted(holdout_teams)[0]
    Path(teams_root, holdout_teams[victim]["team_path"]).with_suffix(".packed").unlink()

    with pytest.raises(GateBAbort, match="species"):
        combine_strength_holdout_arms(**_combine_kwargs(tmp_path, arm_a, arm_b, teams_root, hashes))


def test_combine_aborts_if_a_canonical_reference_packed_file_is_missing(tmp_path, monkeypatch):
    """P1 #3, reference side: the nine canonical references are pinned paths, not caller input,
    so a missing one is likewise a fail-closed abort rather than a silently smaller comparison
    set that would make the near-duplicate guard quietly weaker."""
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)
    victim = sorted(CANONICAL_REFERENCE_TEAM_PATHS)[0]
    Path(teams_root, CANONICAL_REFERENCE_TEAM_PATHS[victim]).with_suffix(".packed").unlink()

    with pytest.raises(GateBAbort, match="species"):
        combine_strength_holdout_arms(**_combine_kwargs(tmp_path, arm_a, arm_b, teams_root, hashes))


def test_canonical_reference_team_paths_are_the_nine_real_champions_teams():
    """P1 #3: the pinned reference set is the nine EXISTING Champions M-A teams (five
    panel_champions_v0 + four coverage foes), and every one of them really exists in this repo
    -- a pinned constant that drifts from the tree would silently weaken the guard."""
    assert len(CANONICAL_REFERENCE_TEAM_PATHS) == 9
    for team_id, rel_path in CANONICAL_REFERENCE_TEAM_PATHS.items():
        assert Path(rel_path).with_suffix(".packed").exists(), f"{team_id} -> {rel_path}"


# --- P2 #4: non-object JSON must abort, not raise a raw TypeError ----------------------------


def test_combine_aborts_on_a_non_object_row_not_a_raw_typeerror(tmp_path, monkeypatch):
    """P2 #4, freshly reproduced by the reviewer: a `null` row reached validate_battle_row, which
    raised TypeError ('argument of type NoneType is not a container') -- escaping the GateBAbort
    contract the CLI relies on."""
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    with open(Path(arm_a) / "rows.jsonl", "a", encoding="utf-8", newline="") as fh:
        fh.write("null\n")

    with pytest.raises(GateBAbort, match="object"):
        combine_strength_holdout_arms(
            **_combine_kwargs(tmp_path, arm_a, arm_b, ".", _fake_holdout_hashes())
        )


def test_combine_aborts_on_a_non_object_manifest_not_a_raw_typeerror(tmp_path, monkeypatch):
    """P2 #4, manifest side: `null` reached `set(manifest)` and raised
    TypeError ('NoneType object is not iterable')."""
    _patch_upstream_verdicts_as_pass(monkeypatch)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA")
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain")
    (Path(arm_a) / "arm_manifest.json").write_text("null", encoding="utf-8")

    with pytest.raises(GateBAbort, match="object"):
        combine_strength_holdout_arms(
            **_combine_kwargs(tmp_path, arm_a, arm_b, ".", _fake_holdout_hashes())
        )


# --- P2 #5: the access-budget check and its reservation must be one atomic section -----------


def test_combine_holds_one_lock_across_the_budget_check_and_the_ledger_append(tmp_path, monkeypatch):
    """P2 #5: check_access read the ledger near the start and append_entry wrote it much later,
    so two concurrent combines could both observe a free budget and both publish. Proven here by
    recording lock state at each call: both must happen while the SAME lock is held."""
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)
    ledger_path = str(tmp_path / "ledger.jsonl")

    from showdown_bot.eval import strength_holdout_runner as mod
    events = []
    real_check, real_append = mod.check_access, mod.append_entry

    def _spy_check(entries, config_hash, **kw):
        events.append(("check", os.path.exists(ledger_path + ".lock")))
        return real_check(entries, config_hash, **kw)

    def _spy_append(path, entry):
        events.append(("append", os.path.exists(ledger_path + ".lock")))
        return real_append(path, entry)

    monkeypatch.setattr(mod, "check_access", _spy_check)
    monkeypatch.setattr(mod, "append_entry", _spy_append)

    combine_strength_holdout_arms(
        **_combine_kwargs(tmp_path, arm_a, arm_b, teams_root, hashes, ledger_path=ledger_path)
    )
    # The AUTHORITATIVE check is the one immediately before the reservation, and both are under
    # the lock. (An earlier, unlocked check_access is allowed as a fail-fast, so this asserts the
    # tail of the sequence rather than the whole of it.)
    assert events[-2:] == [("check", True), ("append", True)]
    # And the lock is released again once the section completes.
    assert not os.path.exists(ledger_path + ".lock")


def test_combine_refuses_to_start_while_another_combine_holds_the_ledger_lock(tmp_path, monkeypatch):
    """P2 #5: a second concurrent combine must not slip past the budget while the first one is
    still between its check and its append -- it aborts fail-closed instead of racing."""
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)
    ledger_path = str(tmp_path / "ledger.jsonl")
    Path(ledger_path + ".lock").write_text("held by another combine\n", encoding="utf-8")

    with pytest.raises(GateBAbort, match="lock"):
        combine_strength_holdout_arms(
            **_combine_kwargs(tmp_path, arm_a, arm_b, teams_root, hashes, ledger_path=ledger_path)
        )
    assert not os.path.exists(str(tmp_path / "combined"))


# ---------------------------------------------------------------------------
# Task-10 second review round, P1: result rows must be bound to CANONICAL BATTLE
# IDENTITY, not just to the (seed_index, opp_policy, opp_team_path) grid.
# ---------------------------------------------------------------------------


def _corrupt_field_in_both_arms(arm_a, arm_b, field, make_bad):
    """Set a wrong value for `field` on EVERY row of BOTH arms.

    Deliberately not "corrupt one row": a single bad row introduces intra-arm variance that
    pair_runs' own constant-field check already notices, which would make these tests pass for a
    reason that has nothing to do with canonical binding (verified -- the format_id case passed
    exactly that way before this helper was widened). The scenario under test is the one that
    genuinely slipped through: both arms internally consistent, in agreement with each other and
    with their own manifests, and uniformly carrying values no genuine run could have produced.

    `make_bad` takes the row and returns the replacement, so a case can stay per-row DISTINCT
    (a wrong seed derivation) rather than collapsing 180 rows onto one repeated value.
    """
    for arm in (arm_a, arm_b):
        rows_path = Path(arm) / "rows.jsonl"
        rows = [json.loads(l) for l in rows_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        for row in rows:
            row[field] = make_bad(row)
        with open(rows_path, "w", encoding="utf-8", newline="") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


@pytest.mark.parametrize("field,make_bad", [
    # A real derive_battle_seed value, but for the WRONG index: still distinct per row, still
    # correctly formatted, just not the seed this battle key scheduled. seeds.jsonl continues to
    # verify -- it proves the canonical seeds exist, never that these rows were played under them.
    ("seed", lambda row: derive_battle_seed(STRENGTH_HOLDOUT_SEED_BASE, row["seed_index"] + 1)),
    # battle_id is the pairing key, sha1(schedule_hash, seed_index, seed)[:16]; here it is a real
    # digest over a FORGED schedule_hash. The old fixture wrote "b0" here and passed -- which is
    # exactly how this gap escaped 98 green tests.
    ("battle_id", lambda row: make_battle_id("forged_schedule", row["seed_index"], row["seed"])),
    ("format_id", lambda row: "gen9vgc2024regulationh"),
    ("config_id", lambda row: "some_other_agent"),
    ("run_id", lambda row: "forged-run-id"),
    ("hero_team_path", lambda row: "showdown_bot/teams/fixed_team.txt"),
    # A row produced from a dirty tree can never be part of sealed evidence.
    ("dirty", lambda row: True),
])
def test_combine_aborts_when_both_arms_carry_the_same_wrong_canonical_field(
    tmp_path, monkeypatch, field, make_bad,
):
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)
    _corrupt_field_in_both_arms(arm_a, arm_b, field, make_bad)

    with pytest.raises(GateBAbort, match=field):
        combine_strength_holdout_arms(**_combine_kwargs(tmp_path, arm_a, arm_b, teams_root, hashes))
    assert not os.path.exists(str(tmp_path / "combined"))


def test_combine_aborts_if_a_row_is_missing_a_canonical_identity_field(tmp_path, monkeypatch):
    """Presence is checked before any value comparison, so a stripped field aborts cleanly
    instead of raising a raw KeyError out of the new binding loop."""
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)
    rows_path = Path(arm_a) / "rows.jsonl"
    rows = [json.loads(l) for l in rows_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    del rows[0]["run_id"]
    with open(rows_path, "w", encoding="utf-8", newline="") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")

    with pytest.raises(GateBAbort, match="run_id"):
        combine_strength_holdout_arms(**_combine_kwargs(tmp_path, arm_a, arm_b, teams_root, hashes))


def test_combine_derives_the_expected_seed_and_battle_id_per_canonical_key(tmp_path, monkeypatch):
    """The binding must be a fresh DERIVATION per battle key, not a self-consistency check: a row
    whose seed and battle_id agree with each other -- but belong to a DIFFERENT seed_index -- is
    still not the battle that key scheduled. Here rows 0 and 1 swap their whole identity pair, so
    every value present is individually 'real', just filed under the wrong key."""
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)
    for arm in (arm_a, arm_b):
        rows_path = Path(arm) / "rows.jsonl"
        rows = [json.loads(l) for l in rows_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        rows[0]["seed"], rows[1]["seed"] = rows[1]["seed"], rows[0]["seed"]
        rows[0]["battle_id"], rows[1]["battle_id"] = rows[1]["battle_id"], rows[0]["battle_id"]
        with open(rows_path, "w", encoding="utf-8", newline="") as fh:
            for row in rows:
                fh.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")

    with pytest.raises(GateBAbort, match="seed|battle_id"):
        combine_strength_holdout_arms(**_combine_kwargs(tmp_path, arm_a, arm_b, teams_root, hashes))


def test_combine_success_path_carries_real_canonical_battle_identity(tmp_path, monkeypatch):
    """The positive fixture must itself be canonical -- otherwise the guard above would be
    proven only by negative cases, and the success path would silently depend on the guard NOT
    looking at these fields (which is how the gap survived the previous round)."""
    _patch_upstream_verdicts_as_pass(monkeypatch)
    teams_root, hashes = _write_holdout_teams_repo(tmp_path)
    holdout_teams = _holdout_teams_mapping(hashes)
    arm_a = _write_arm(tmp_path, "arm_a", hero_agent="heuristic", config_hash="cfgA", holdout_teams=holdout_teams)
    arm_b = _write_arm(tmp_path, "arm_b", hero_agent="max_damage", config_hash="cfgB", winner="villain", holdout_teams=holdout_teams)

    with open(Path(arm_a) / "arm_manifest.json", encoding="utf-8") as fh:
        manifest = json.load(fh)
    rows = [json.loads(l) for l in (Path(arm_a) / "rows.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    schedule = build_strength_holdout_schedule(
        holdout_team_ids=sorted(holdout_teams), panel_hash=manifest["panel_hash"],
        seed_base=manifest["seed_base"],
    )
    by_index = {row["seed_index"]: row for row in rows}
    for key in schedule.battle_keys:
        row = by_index[key.seed_index]
        expected_seed = derive_battle_seed(manifest["seed_base"], key.seed_index)
        assert row["seed"] == expected_seed
        assert row["battle_id"] == make_battle_id(manifest["schedule_hash"], key.seed_index, expected_seed)
        assert row["run_id"] == f"{manifest['candidate_identity']}-{manifest['hero_agent']}"
        assert row["hero_team_path"] == STRENGTH_HOLDOUT_HERO_TEAM_PATH
        assert row["format_id"] == STRENGTH_HOLDOUT_FORMAT_ID
        assert row["dirty"] is False

    result = combine_strength_holdout_arms(**_combine_kwargs(tmp_path, arm_a, arm_b, teams_root, hashes))
    assert result["n_total"] == 180

```

Rev. 3 removes the `_all_guards_pass_for_test` seam entirely: it patched a name the production
code never called, so it isolated nothing (its own tests only passed because `holdout_hashes`/
`reference_species` defaulting to falsy also skipped the *real* guards — the same optional-skip
anti-pattern as the verdict-path bug, just one level deeper). The tests above patch only
`verify_i8d_verdict_artifact`/`verify_coverage_verdict_artifact` — both fully covered
independently in Task 7.

**Corrected, Rev. 14 (§1m, P2 — this paragraph was stale relative to Rev. 13/14's own test
design):** empty guard inputs are not permitted anywhere in this file any more, in a test or
otherwise — `combine_strength_holdout_arms` itself unconditionally rejects an empty
`holdout_content_hashes` (§13 -- the `holdout_candidate_species`/`reference_species` parameters
no longer exist at all; both species mappings are derived from the real sealed `.packed` files,
so there is no caller-supplied species input left to be empty), and every test above supplies non-empty,
internally-consistent data by construction (`_write_arm`'s default `holdout_teams`, `_fake_holdout_hashes()`).
What actually varies between tests is not "empty vs. non-empty" but *how far into the function
each test's own scenario runs*: the ten early-abort tests (an i8d/coverage-path guard, an
arm-read/manifest-schema guard, an arm-role/git_sha mismatch — none of them reach
`assert_no_holdout_leakage` at all) use cheap, structurally-valid-but-not-git-backed fixture data
(`_fake_holdout_hashes()`, `_write_arm`'s default `_fake_holdout_teams()`) deliberately, because
the guard never runs for them regardless of what that data contains. Every test that DOES reach
the team-/leakage-guard — the full-success path, both upstream-verdict-error tests, the
publish/ledger tests, the baseline-drift test, and the pairing-error test — uses
`_write_holdout_teams_repo`: a real, isolated git repository seeded with six committed,
allowlist-conformant `.txt`/`.packed` team files, with `teams_root` pointed at it and
`holdout_content_hashes` computed from its real content via `panel.team_content_hash`. No test
anywhere mocks `assert_no_holdout_leakage`, `scan_for_raw_payload_leakage`, or any of the other
guards away — every one of them runs for real, against real data, in every test that reaches it.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest showdown_bot/tests/test_strength_holdout_runner.py -v -k combine`
Expected: FAIL — `ImportError: cannot import name 'combine_strength_holdout_arms'`

**As executed (Rev. 20, mechanical sync):** that was the observed first RED. The two review
rounds that followed produced their own REDs, recorded here because they are what the code above
now encodes: the five-finding round went RED on
`TypeError: combine_strength_holdout_arms() missing 2 required keyword-only arguments:
'holdout_candidate_species' and 'reference_species'` (both parameters were removed — species are
derived from the sealed files instead), and the canonical-identity round went RED with all seven
parametrized field cases plus the identity-swap case failing `DID NOT RAISE GateBAbort`.

- [ ] **Step 3: Write the implementation**

```python
from showdown_bot.eval.pairing import pair_runs, PairingError
from showdown_bot.eval.strength_holdout_verdict import (
    render_strength_holdout_verdict, compute_safety_pass,
    verify_i8d_verdict_artifact, verify_coverage_verdict_artifact, StrengthHoldoutRunError,
)
from showdown_bot.eval.holdout_leakage_scan import assert_no_holdout_leakage
from showdown_bot.eval.holdout_disjointness import assert_disjoint_from_coverage
from showdown_bot.eval.near_duplicate import find_near_duplicate_flags, load_team_species
from showdown_bot.eval.strata_guard import VALID_STRATA, StratumRecord, assert_no_cross_stratum_pooling
from showdown_bot.eval.heldout_ledger import append_entry, read_ledger, check_access, LedgerError
from showdown_bot.eval.baseline import load_baseline, verify_baseline, BaselineDriftError
from showdown_bot.eval.report import _build_cells, _build_aggregates
# Rev. 19 note (Task 9 review-fix sync, §1r): _assert_seed_artifact_verified (below) needs
# `hashlib`, `re`, `Path`, `platform`, `verify_seed_log`, and `SeedLogError` -- all ALREADY
# imported module-wide at the top of strength_holdout_runner.py by Task 9's own review-fix
# (`import hashlib`/`import re`/`from pathlib import Path`/`import platform`/`from
# showdown_bot.eval.seeding import ..., verify_seed_log, SeedLogError`). No new import needed
# for Task 10 itself.


def _read_arm(arm_dir: str) -> tuple[list[dict], dict]:
    # Self-found while building the Rev. 7 exception-audit table (not in NF1's own text, same
    # function/mechanism/round -- disclosed explicitly in §1f, following the Rev. 2 precedent of
    # fixing self-found adjacent bugs in the same pass rather than deferring them unmentioned):
    # open()/json.loads()/json.load() below can raise OSError (missing arm_dir/rows.jsonl/
    # arm_manifest.json, permissions), UnicodeDecodeError (non-UTF-8 bytes on disk), or
    # json.JSONDecodeError (truncated/corrupt JSON) -- none is ResultRowError, so the except
    # clause added for NF1 does not catch them. All three are the same "corrupted or stale arm
    # directory" scenario this function exists to guard against -- not a caller-contract
    # violation (e.g. a wrong-typed arm_dir), which stays unguarded per this codebase's own
    # boundary-only validation convention.
    try:
        rows = []
        with open(os.path.join(arm_dir, "rows.jsonl"), "r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    row = json.loads(line)
                    # Task-10 review-fix, P2 #4: syntactically valid JSON that is not an OBJECT
                    # (`null`, a bare number, a list) used to reach validate_battle_row, whose
                    # `field in row` membership test raises a raw TypeError for None -- escaping
                    # this function's own GateBAbort contract that the CLI depends on. Checked
                    # here, before any field access, for exactly the same reason the manifest is
                    # checked below.
                    if not isinstance(row, dict):
                        raise GateBAbort(
                            f"malformed row in {arm_dir}/rows.jsonl: expected a JSON object, got "
                            f"{type(row).__name__}"
                        )
                    try:
                        validate_battle_row(row)  # F3 fix (Rev. 6): schema conformance was never checked on read
                    except ResultRowError as exc:
                        # NF1 fix (Rev. 7): a corrupted or stale-schema rows.jsonl must produce a
                        # clean abort, not a traceback -- ResultRowError was never imported or
                        # caught anywhere in this plan before this fix.
                        raise GateBAbort(f"malformed row in {arm_dir}/rows.jsonl: {exc}") from exc
                    rows.append(row)
        with open(os.path.join(arm_dir, "arm_manifest.json"), "r", encoding="utf-8") as fh:
            manifest = json.load(fh)
        # Task-10 review-fix, P2 #4: same as the row check above -- a `null` manifest reached
        # `set(manifest)` in _assert_rows_match_manifest and raised a raw TypeError ("'NoneType'
        # object is not iterable") instead of aborting cleanly.
        if not isinstance(manifest, dict):
            raise GateBAbort(
                f"malformed arm_manifest.json in {arm_dir!r}: expected a JSON object, got "
                f"{type(manifest).__name__}"
            )
    except (OSError, UnicodeDecodeError) as exc:
        raise GateBAbort(f"cannot read arm directory {arm_dir!r}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise GateBAbort(f"malformed JSON in arm directory {arm_dir!r}: {exc}") from exc
    return rows, manifest


# NF1 fix (Rev. 7): the exact keys _assert_rows_match_manifest indexes below, checked for
# PRESENCE before any value comparison. panel_hash is deliberately included on the row side even
# though result_jsonl.NULLABLE_FIELDS does not require it -- validate_battle_row (called in
# _read_arm above) does not guarantee its presence, so a row missing it would otherwise crash
# this function's own row[field] access with a raw KeyError, exactly the N1 bug one level up
# (see the comment at Task 9's row-building site).
_MANIFEST_REQUIRED_KEYS = ("n_rows", "config_hash", "git_sha", "schedule_hash", "seed_base",
                          "panel_hash", "hero_agent", "candidate_identity", "holdout_teams",
                          # Rev. 15 fix (§1n, Task-3-review P1 #1): presence-checked here exactly
                          # like every other required field -- closed-form validity (unknown
                          # stratum value; non-string/empty platform_attestation/date_stratum_id)
                          # is checked separately, by _validate_stratum_fields below.
                          "stratum", "platform_attestation", "date_stratum_id",
                          # Rev. 19 fix (Task 9 review-fix sync, §1r): Task 9's own review-fix
                          # (5 P1s) added calc_backend (derived internally, no longer discarded)
                          # and replaced the caller-local seed_log_path field with a four-field
                          # seed PROOF -- seed_log_relpath/seed_log_sha256/seed_log_n_lines/
                          # seed_log_verified -- so the arm's manifest never again carries a
                          # machine-local absolute path. Presence-checked here; closed-form
                          # validity by _validate_seed_proof_fields below.
                          "calc_backend", "seed_log_relpath", "seed_log_sha256",
                          "seed_log_n_lines", "seed_log_verified")
_ROW_REQUIRED_KEYS_FOR_MANIFEST_CHECK = ("config_hash", "git_sha", "schedule_hash", "seed_base", "panel_hash")
# Rev. 14 fix (§1m, third review round P1): presence-checked in the SAME per-row loop as
# _ROW_REQUIRED_KEYS_FOR_MANIFEST_CHECK (both are just "does this row have the key"), but bound
# against holdout_teams (a per-team MAPPING) in a separate function below, not the scalar
# row[field] != manifest[field] content-match loop just below this constant, which only ever
# compares a row field against ONE manifest-wide value -- opp_team_path/opp_team_hash vary
# per row by design (each row is for a DIFFERENT one of the six teams).
_ROW_REQUIRED_KEYS_FOR_TEAM_BINDING = ("opp_team_path", "opp_team_hash")
_HOLDOUT_TEAM_ENTRY_FIELDS = frozenset({"team_path", "content_hash"})


def _validate_holdout_teams_mapping(holdout_teams, which: str) -> None:
    """Rev. 14 fix (§1m, third review round P1): holdout_teams must be a CLOSED, unambiguous,
    deterministic mapping -- Rev. 13's bare team_id LIST only ever ASSERTED which six teams were
    played; it was never bound to what the rows themselves actually contain, and nothing rejected
    a malformed shape either. Every structural deviation is rejected fail-closed here, before any
    row-binding check below even attempts to read it (mirrors panel.py's own
    missing/unknown-field pattern in _load_team_list)."""
    if not isinstance(holdout_teams, dict):
        raise GateBAbort(
            f"arm {which}: manifest's holdout_teams must be an object/mapping, got "
            f"{type(holdout_teams).__name__}"
        )
    if len(holdout_teams) != 6:
        raise GateBAbort(
            f"arm {which}: manifest's holdout_teams must have exactly 6 entries, got "
            f"{len(holdout_teams)}"
        )
    for team_id, entry in holdout_teams.items():
        if not isinstance(team_id, str) or not team_id:
            raise GateBAbort(f"arm {which}: holdout_teams has a non-string or empty team_id key: {team_id!r}")
        if not isinstance(entry, dict):
            raise GateBAbort(
                f"arm {which}: holdout_teams[{team_id!r}] must be an object/mapping, got "
                f"{type(entry).__name__}"
            )
        missing = _HOLDOUT_TEAM_ENTRY_FIELDS - set(entry)
        unknown = set(entry) - _HOLDOUT_TEAM_ENTRY_FIELDS
        if missing:
            raise GateBAbort(f"arm {which}: holdout_teams[{team_id!r}] is missing field(s): {sorted(missing)}")
        if unknown:
            raise GateBAbort(f"arm {which}: holdout_teams[{team_id!r}] has unknown field(s): {sorted(unknown)}")
        for field in _HOLDOUT_TEAM_ENTRY_FIELDS:
            if not isinstance(entry[field], str) or not entry[field]:
                raise GateBAbort(
                    f"arm {which}: holdout_teams[{team_id!r}][{field!r}] must be a non-empty "
                    f"string, got {entry[field]!r}"
                )
        expected_path = f"{HOLDOUT_TEAMS_DIR}{team_id}.txt"
        if entry["team_path"] != expected_path:
            raise GateBAbort(
                f"arm {which}: holdout_teams[{team_id!r}]['team_path']={entry['team_path']!r} "
                f"is not the canonical path for this team_id (expected {expected_path!r})"
            )


def _validate_stratum_fields(manifest: dict, which: str) -> None:
    """Rev. 15 fix (§1n, Task-3-review P1 #1): stratum/platform_attestation/date_stratum_id are
    now REQUIRED manifest fields (presence checked by _MANIFEST_REQUIRED_KEYS, same as
    holdout_teams) -- but presence alone is not closed validation. A stratum value that is
    present but not one of strata_guard.VALID_STRATA, or a platform_attestation/date_stratum_id
    that is present but empty or the wrong type, must abort here -- exactly the same
    "missing, unknown, or type-wrong" standard _validate_holdout_teams_mapping already applies to
    holdout_teams, now applied to these three fields."""
    stratum = manifest["stratum"]
    if not isinstance(stratum, str) or stratum not in VALID_STRATA:
        raise GateBAbort(
            f"arm {which}: manifest's stratum={stratum!r} is not one of the known strata "
            f"{sorted(VALID_STRATA)}"
        )
    for field in ("platform_attestation", "date_stratum_id"):
        value = manifest[field]
        if not isinstance(value, str) or not value:
            raise GateBAbort(f"arm {which}: manifest's {field}={value!r} must be a non-empty string")


_SUPPORTED_CALC_BACKENDS = frozenset({"oneshot", "persistent"})


def _validate_seed_proof_fields(manifest: dict, which: str) -> None:
    """Rev. 19 fix (Task 9 review-fix sync, §1r): Task 9's own review-fix derives calc_backend
    internally (never caller-supplied, never discarded) and replaced the caller-local
    seed_log_path field with a four-field seed PROOF the arm carries in its own manifest --
    seed_log_relpath/seed_log_sha256/seed_log_n_lines/seed_log_verified. Closed-form validated
    here, exactly like _validate_stratum_fields already does for
    stratum/platform_attestation/date_stratum_id, before _assert_seed_artifact_verified (below)
    ever trusts these values to locate and re-verify the real seed-log bytes."""
    calc_backend = manifest["calc_backend"]
    if not isinstance(calc_backend, str) or calc_backend not in _SUPPORTED_CALC_BACKENDS:
        raise GateBAbort(
            f"arm {which}: manifest's calc_backend={calc_backend!r} is not a supported backend "
            f"{sorted(_SUPPORTED_CALC_BACKENDS)}"
        )
    seed_log_relpath = manifest["seed_log_relpath"]
    if seed_log_relpath != "seeds.jsonl":
        raise GateBAbort(
            f"arm {which}: manifest's seed_log_relpath={seed_log_relpath!r} must be exactly "
            "'seeds.jsonl' -- no absolute path, no subdirectory, no traversal"
        )
    seed_log_sha256 = manifest["seed_log_sha256"]
    if not isinstance(seed_log_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", seed_log_sha256) is None:
        raise GateBAbort(
            f"arm {which}: manifest's seed_log_sha256={seed_log_sha256!r} must be a lowercase "
            "64-character sha256 hex digest"
        )
    seed_log_n_lines = manifest["seed_log_n_lines"]
    if isinstance(seed_log_n_lines, bool) or not isinstance(seed_log_n_lines, int) or seed_log_n_lines < 0:
        raise GateBAbort(
            f"arm {which}: manifest's seed_log_n_lines={seed_log_n_lines!r} must be a genuine "
            "non-negative int"
        )
    if manifest["seed_log_verified"] is not True:
        raise GateBAbort(
            f"arm {which}: manifest's seed_log_verified={manifest['seed_log_verified']!r} must "
            "be exactly True"
        )


def _assert_seed_artifact_verified(arm_dir: str, manifest: dict, which: str) -> None:
    """Rev. 19 fix (Task 9 review-fix sync, §1r): re-verify each arm's PUBLISHED seed log fresh,
    before pairing or any verdict -- never trust Task 9's own seed_log_verified=True claim alone
    (that is a self-report from a prior, separate process; this function independently
    reproduces the proof against the bytes actually sitting in THIS arm directory). Both arms are
    verified independently -- matching manifest values alone are never sufficient, since a
    doctored manifest could claim agreement without either seed log genuinely verifying.

    Containment is canonical (mirrors run_strength_holdout_arm's own out_dir fix, Task 9): even
    though _validate_seed_proof_fields above already rejects any seed_log_relpath other than the
    literal 'seeds.jsonl', this still resolves the real path through the filesystem (following
    any symlink/junction) and checks by path COMPONENT that it lands inside arm_dir -- defense in
    depth against a symlink/junction planted at that exact relative location pointing elsewhere.
    The resolve() call itself is wrapped: on Windows, resolving certain symlink configurations can
    raise a raw OSError (observed: WinError 267) instead of just following the link -- that must
    fail closed as GateBAbort too, not escape uncaught."""
    arm_root = Path(arm_dir).resolve()
    try:
        seed_log_path = (arm_root / manifest["seed_log_relpath"]).resolve()
    except OSError as exc:
        raise GateBAbort(f"arm {which}: cannot resolve seed log path: {exc}") from exc
    arm_parts, seed_parts = arm_root.parts, seed_log_path.parts
    if platform.system() == "Windows":
        arm_parts = tuple(p.lower() for p in arm_parts)
        seed_parts = tuple(p.lower() for p in seed_parts)
    if seed_parts[: len(arm_parts)] != arm_parts:
        raise GateBAbort(
            f"arm {which}: seed_log_relpath resolves to {str(seed_log_path)!r}, outside its own "
            f"arm directory {str(arm_root)!r} -- refusing a symlink/junction escape"
        )
    try:
        with open(seed_log_path, "rb") as fh:
            seed_log_bytes = fh.read()
    except OSError as exc:
        raise GateBAbort(f"arm {which}: cannot read seed log at {str(seed_log_path)!r}: {exc}") from exc
    fresh_sha256 = hashlib.sha256(seed_log_bytes).hexdigest()
    if fresh_sha256 != manifest["seed_log_sha256"]:
        raise GateBAbort(
            f"arm {which}: seed log at {str(seed_log_path)!r} has sha256={fresh_sha256!r}, does "
            f"not match manifest's seed_log_sha256={manifest['seed_log_sha256']!r}"
        )
    try:
        seed_records = verify_seed_log(str(seed_log_path), manifest["seed_base"], manifest["n_rows"])
    except SeedLogError as exc:
        raise GateBAbort(f"arm {which}: seed-log verification failed: {exc}") from exc
    if len(seed_records) != manifest["seed_log_n_lines"]:
        raise GateBAbort(
            f"arm {which}: verified {len(seed_records)} seed-log record(s), but manifest claims "
            f"seed_log_n_lines={manifest['seed_log_n_lines']!r}"
        )


def _assert_rows_bind_to_holdout_teams(rows: list[dict], holdout_teams: dict, which: str) -> None:
    """Rev. 14 fix (§1m, third review round P1): a structurally-valid holdout_teams mapping is
    still just an ASSERTION until checked against what the rows themselves actually played.
    opp_team_path/opp_team_hash are the row-level ground truth -- Task 9's own _capture closure
    stamps them from the real per-battle key and the real sealed content hash -- so
    holdout_teams must agree with THAT, not the other way around. Requires every row to resolve
    to one of the declared six teams by path AND by hash, and every declared team to actually
    appear at least once."""
    allowed_paths = {entry["team_path"] for entry in holdout_teams.values()}
    path_to_team_id = {entry["team_path"]: team_id for team_id, entry in holdout_teams.items()}
    seen_paths = set()
    for i, row in enumerate(rows):
        opp_team_path = row["opp_team_path"]
        if opp_team_path not in allowed_paths:
            raise GateBAbort(
                f"arm {which}: row {i} has opp_team_path={opp_team_path!r}, not one of the six "
                "teams declared in holdout_teams"
            )
        team_id = path_to_team_id[opp_team_path]
        expected_hash = holdout_teams[team_id]["content_hash"]
        if row["opp_team_hash"] != expected_hash:
            raise GateBAbort(
                f"arm {which}: row {i} (team {team_id!r}) has "
                f"opp_team_hash={row['opp_team_hash']!r}, does not match holdout_teams's "
                f"content_hash={expected_hash!r} for this team"
            )
        seen_paths.add(opp_team_path)
    missing_teams = allowed_paths - seen_paths
    if missing_teams:
        missing_ids = sorted(path_to_team_id[p] for p in missing_teams)
        raise GateBAbort(
            f"arm {which}: holdout_teams declares team(s) {missing_ids} that never appear in "
            "rows -- manifest and rows.jsonl do not agree on which teams were actually played"
        )


def _assert_rows_match_manifest(rows: list[dict], manifest: dict, which: str) -> None:
    """F3 fix (Rev. 6): every downstream check in combine_strength_holdout_arms -- the two
    upstream-verdict checks, the ledger entry, the published verdict.json -- trusts
    manifest_a's identity fields (candidate_identity, git_sha, config_hash, ...) without ever
    proving they actually describe the rows sitting next to it. An arm directory assembled from
    two different runs (a stale or swapped arm_manifest.json) would pass every existing check
    silently. Never trust the pairing of a manifest with a rows.jsonl just because they share a
    directory -- prove it, the same way this plan already refuses to trust an upstream verdict's
    opaque candidate_identity alone (Task 7).

    NF1 fix (Rev. 7): a malformed or truncated manifest/row -- exactly the kind of bad input
    this function exists to catch -- must never crash it with a raw KeyError instead of
    producing the GateBAbort it was written to produce. Every expected key is checked for
    presence FIRST, before any indexed access.

    Rev. 14 fix (§1m, third review round P1): presence and internal shape are not enough for
    holdout_teams specifically -- it is validated structurally (_validate_holdout_teams_mapping)
    and then bound to what these SAME rows actually contain
    (_assert_rows_bind_to_holdout_teams), both before the scalar per-field checks below, so a
    manifest that lies about which teams were played is caught here, not three call sites
    downstream where the leakage/disjointness guards would have silently trusted it.

    Rev. 15 fix (§1n, Task-3-review P1 #1): the same standard now applies to
    stratum/platform_attestation/date_stratum_id (_validate_stratum_fields) -- presence via
    _MANIFEST_REQUIRED_KEYS, closed-form validity (unknown stratum, non-string/empty attestation
    or date-stratum id) here, before combine_strength_holdout_arms ever compares the two arms'
    values against each other."""
    missing_manifest_keys = set(_MANIFEST_REQUIRED_KEYS) - set(manifest)
    if missing_manifest_keys:
        raise GateBAbort(
            f"arm {which}: manifest is missing required key(s): {sorted(missing_manifest_keys)} "
            "-- malformed or truncated arm_manifest.json"
        )
    _validate_holdout_teams_mapping(manifest["holdout_teams"], which)
    _validate_stratum_fields(manifest, which)
    _validate_seed_proof_fields(manifest, which)
    for i, row in enumerate(rows):
        missing_row_keys = (
            set(_ROW_REQUIRED_KEYS_FOR_MANIFEST_CHECK) | set(_ROW_REQUIRED_KEYS_FOR_TEAM_BINDING)
        ) - set(row)
        if missing_row_keys:
            raise GateBAbort(
                f"arm {which}: row {i} is missing required key(s): {sorted(missing_row_keys)} "
                "-- panel_hash in particular is NULLABLE per result_jsonl's own schema, so "
                "validate_battle_row alone does not guarantee it is present here"
            )

    if len(rows) != manifest["n_rows"]:
        raise GateBAbort(
            f"arm {which}: manifest claims n_rows={manifest['n_rows']!r} but rows.jsonl has "
            f"{len(rows)} row(s) -- manifest and rows.jsonl do not belong together"
        )
    for field in _ROW_REQUIRED_KEYS_FOR_MANIFEST_CHECK:
        mismatched = sorted({row[field] for row in rows if row[field] != manifest[field]})
        if mismatched:
            raise GateBAbort(
                f"arm {which}: row field {field!r} disagrees with the manifest's "
                f"{field}={manifest[field]!r} (found: {mismatched}) -- manifest and rows.jsonl "
                f"do not belong together"
            )
    _assert_rows_bind_to_holdout_teams(rows, manifest["holdout_teams"], which)
    fresh_identity = make_candidate_identity(
        hero_agent=manifest["hero_agent"], git_sha=manifest["git_sha"], config_hash=manifest["config_hash"],
    )
    if fresh_identity != manifest["candidate_identity"]:
        raise GateBAbort(
            f"arm {which}: manifest's candidate_identity={manifest['candidate_identity']!r} "
            f"does not match the identity re-derived from its own hero_agent/git_sha/config_hash "
            f"({fresh_identity!r}) -- the manifest is internally inconsistent"
        )


_ROW_REQUIRED_KEYS_FOR_SCHEDULE_BINDING = ("seed_index", "opp_policy")
# Task-10 second review round, P1: the fields that make a row the battle its key scheduled, all
# of them re-derivable here from the manifest alone -- so a value is never merely "present and
# consistent", it is the one canonical value.
_ROW_REQUIRED_KEYS_FOR_CANONICAL_IDENTITY = (
    "seed", "battle_id", "format_id", "config_id", "run_id", "hero_team_path", "dirty",
)


def _assert_rows_cover_canonical_schedule(rows: list[dict], manifest: dict, which: str) -> None:
    """Task-10 review-fix, P1 #1: an arm must be the WHOLE canonical 180-battle-key schedule, and
    every row must be one of its keys.

    Before this fix nothing in the combiner ever rebuilt the schedule. ``n_rows`` was only ever
    compared against ``len(rows)`` (self-consistent by construction for a truncated arm) and
    ``schedule_hash`` was compared row-vs-manifest -- also self-consistent, because the writer
    stamps the same string on both. Two *matching*, *internally consistent*, 12-row arms
    therefore combined to a published "strength" verdict over 12 battles, and the fixtures that
    were supposed to prove otherwise were themselves 12-row. A short or reshaped arm is not a
    weaker strength result, it is not a strength result at all, so this is fail-closed.

    The rebuild is the same one Task 9's ``_assert_schedule_is_genuine`` performs on the write
    side, driven here from what the arm itself recorded: its own six team_ids, its own
    panel_hash, its own seed_base. ``seed_base`` is checked separately against the pinned
    namespace FIRST, for the reason Task 9 documents at its own call site -- feeding a forged
    seed_base into the rebuild and then comparing against that same forged value proves nothing.
    """
    if manifest["seed_base"] != STRENGTH_HOLDOUT_SEED_BASE:
        raise GateBAbort(
            f"arm {which}: manifest's seed_base={manifest['seed_base']!r} != the pinned seed "
            f"namespace {STRENGTH_HOLDOUT_SEED_BASE!r} -- refusing an unpinned seed namespace"
        )
    try:
        schedule = build_strength_holdout_schedule(
            holdout_team_ids=sorted(manifest["holdout_teams"]),
            panel_hash=manifest["panel_hash"], seed_base=manifest["seed_base"],
        )
    except ValueError as exc:
        raise GateBAbort(
            f"arm {which}: its own holdout_teams/panel_hash/seed_base do not rebuild a genuine "
            f"canonical strength-holdout schedule: {exc}"
        ) from exc
    if schedule.schedule_hash != manifest["schedule_hash"]:
        raise GateBAbort(
            f"arm {which}: manifest's schedule_hash={manifest['schedule_hash']!r} is not the "
            f"canonical rebuild from its own team_ids/panel_hash/seed_base "
            f"({schedule.schedule_hash!r}) -- refusing a forged or stale schedule label"
        )
    if len(rows) != len(schedule.battle_keys):
        raise GateBAbort(
            f"arm {which}: has {len(rows)} row(s) but the canonical schedule has "
            f"{len(schedule.battle_keys)} battle key(s) -- a partial arm is not a strength result"
        )
    expected = {
        (key.seed_index, key.opponent_policy, f"{HOLDOUT_TEAMS_DIR}{key.holdout_team_id}.txt")
        for key in schedule.battle_keys
    }
    played = []
    for i, row in enumerate(rows):
        missing = set(_ROW_REQUIRED_KEYS_FOR_SCHEDULE_BINDING) - set(row)
        if missing:
            raise GateBAbort(
                f"arm {which}: row {i} is missing required key(s): {sorted(missing)} -- every row "
                "must identify the canonical battle key it played"
            )
        played.append((row["seed_index"], row["opp_policy"], row["opp_team_path"]))
    if len(set(played)) != len(played):
        raise GateBAbort(
            f"arm {which}: two or more rows claim the SAME canonical battle key -- one battle key "
            "must be played exactly once"
        )
    if set(played) != expected:
        unexpected = sorted(set(played) - expected)[:3]
        unplayed = sorted(expected - set(played))[:3]
        raise GateBAbort(
            f"arm {which}: its rows do not cover the canonical schedule exactly once -- "
            f"battle key(s) played but not scheduled: {unexpected}; scheduled but not played: "
            f"{unplayed}"
        )

    # Task-10 second review round, P1: covering the (seed_index, opp_policy, opp_team_path) grid
    # says the right SLOTS are present; it says nothing about whether the result in each slot is
    # the battle that slot scheduled. seeds.jsonl proves the canonical seeds exist, but nothing
    # tied the ROWS to those seeds -- so two arms could carry identical, uniformly wrong seeds,
    # battle_ids, format, agent or hero team and still pair cleanly (pair_runs only notices
    # variance WITHIN an arm, which uniform corruption does not produce). Every field below is
    # re-derived here from the manifest and the canonical key, never merely compared for internal
    # consistency.
    keys_by_index = {key.seed_index: key for key in schedule.battle_keys}
    expected_run_id = f"{manifest['candidate_identity']}-{manifest['hero_agent']}"
    for i, row in enumerate(rows):
        missing = set(_ROW_REQUIRED_KEYS_FOR_CANONICAL_IDENTITY) - set(row)
        if missing:
            raise GateBAbort(
                f"arm {which}: row {i} is missing required key(s): {sorted(missing)} -- every row "
                "must carry the full canonical battle identity"
            )
        key = keys_by_index[row["seed_index"]]
        expected_seed = derive_battle_seed(manifest["seed_base"], key.seed_index)
        for field, expected_value in (
            ("seed", expected_seed),
            ("battle_id", make_battle_id(manifest["schedule_hash"], key.seed_index, expected_seed)),
            ("format_id", STRENGTH_HOLDOUT_FORMAT_ID),
            ("config_id", manifest["hero_agent"]),
            ("run_id", expected_run_id),
            ("hero_team_path", STRENGTH_HOLDOUT_HERO_TEAM_PATH),
        ):
            if row[field] != expected_value:
                raise GateBAbort(
                    f"arm {which}: row {i} (seed_index {key.seed_index}) has "
                    f"{field}={row[field]!r}, but the canonical battle key derives "
                    f"{field}={expected_value!r} -- this row is not the battle its key scheduled"
                )
        # `is not False` on purpose, not `if row["dirty"]`: a truthy-but-not-True value (or a
        # string "false") must fail here rather than be quietly accepted as clean.
        if row["dirty"] is not False:
            raise GateBAbort(
                f"arm {which}: row {i} (seed_index {key.seed_index}) has dirty={row['dirty']!r} "
                "-- a battle played from a dirty tree can never be part of sealed evidence"
            )


def _derive_species_from_sealed_files(holdout_teams: dict, teams_root: str) -> tuple[dict, dict]:
    """Task-10 review-fix, P1 #3: derive BOTH sides of the near-duplicate comparison from real
    sealed ``.packed`` content instead of trusting caller-supplied species mappings.

    ``holdout_candidate_species`` and ``reference_species`` were plain caller assertions: combine
    only ever checked that the candidate mapping's KEY SET matched the six scheduled teams, never
    that any listed species had anything to do with the team it was filed under. A caller could
    hand over six species lists that trivially overlap nothing and the guard would "pass".
    ``near_duplicate.load_team_species`` -- which derives species from a team's real packed file,
    and has its own tests -- existed already but had no production call site anywhere.

    The candidate side is keyed off ``manifest_a["holdout_teams"]``, which by this point is
    already proven to describe the rows actually played; the reference side is the pinned
    ``CANONICAL_REFERENCE_TEAM_PATHS``, not caller input. Any unreadable or malformed team file
    is a fail-closed abort -- a silently smaller comparison set would quietly weaken the guard.
    """
    try:
        candidates = {
            team_id: load_team_species(holdout_teams[team_id]["team_path"], teams_root=teams_root)
            for team_id in sorted(holdout_teams)
        }
        references = {
            ref_id: load_team_species(CANONICAL_REFERENCE_TEAM_PATHS[ref_id], teams_root=teams_root)
            for ref_id in sorted(CANONICAL_REFERENCE_TEAM_PATHS)
        }
    except ValueError as exc:
        raise GateBAbort(
            f"cannot derive team species from the real sealed team files under "
            f"teams_root={teams_root!r}: {exc}"
        ) from exc
    return candidates, references


@contextmanager
def _ledger_lock(ledger_path: str):
    """Task-10 review-fix, P2 #5: make the held-out access budget's check-then-reserve atomic.

    ``check_access`` reads the ledger early and ``append_entry`` writes it much later, with the
    whole guard/pairing/verdict computation in between. Two combines started concurrently could
    both observe a free budget in that window and both go on to append and publish -- exactly the
    held-out-data-reuse the ledger exists to prevent, and invisible afterwards because both
    entries look legitimate. An exclusive ``O_CREAT|O_EXCL`` lock file held across the entire
    section closes it: the second process cannot even begin.

    Deliberately fail-closed with no timeout or steal: a stale lock (left by a crashed combine)
    blocks further runs until a human removes it. For a once-per-candidate held-out gate that is
    the correct trade -- silently breaking a lock is how the budget gets spent twice.
    """
    lock_path = ledger_path + ".lock"
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise GateBAbort(
            f"ledger lock {lock_path!r} is already held -- another combine is inside its "
            "held-out access-budget section, or a previous run crashed and left the lock behind "
            "(remove it by hand after confirming no combine is running)"
        ) from exc
    except OSError as exc:
        raise GateBAbort(f"cannot acquire ledger lock {lock_path!r}: {exc}") from exc
    try:
        try:
            os.write(fd, f"pid={os.getpid()}\n".encode("utf-8"))
        finally:
            os.close(fd)
        yield
    finally:
        try:
            os.unlink(lock_path)
        except OSError:
            pass


def combine_strength_holdout_arms(
    *, arm_a_dir: str, arm_b_dir: str, out_dir: str,
    i8d_verdict_path: str, coverage_verdict_path: str,
    holdout_content_hashes: dict[str, str],
    baseline_manifest_path: str = "config/eval/baselines/champions-strength-holdout-v0.json",
    repo_root: str = ".",
    stratum_env_override: str | None = None,
    ledger_path: str = "config/eval/heldout_ledger.jsonl",
    teams_root: str = ".",
) -> dict:
    """Reads both already-published arms, verifies the two upstream gates, checks baseline
    drift, pairs the arms, runs EVERY guard, renders the verdict via the real report.py
    pipeline, and publishes the full evidence bundle atomically.

    i8d_verdict_path/coverage_verdict_path are REQUIRED and non-empty -- Gate B may only run
    after an I8-D PASS and a Coverage PASS on this candidate (DESIGN sec 5); there is no
    optional/skip path (Rev. 3 P1 fix -- Rev. 2's `= ""` defaults let a caller silently omit
    both checks).

    holdout_content_hashes/reference_species are REQUIRED and must be non-empty (Rev. 4 P2 fix
    -- Rev. 3 allowed a legitimate-looking `{}` here, but nothing distinguished a deliberate
    test scenario from a production caller that just never wired real data through; an empty
    mapping makes the disjointness/leakage/near-duplicate guards vacuous in EITHER case, so
    production now refuses it unconditionally. Tests use small non-empty fake maps instead
    of `{}` -- see Task 10's test fixtures). NON-EMPTY alone does not prove
    holdout_content_hashes covers every scheduled team WITH the right hashes, though -- Rev. 13
    (§1l) closed the key-set-only version of this gap (a partial map) but not the value-wrong
    version (right keys, wrong hash for one), and neither Rev. 12 nor Rev. 13 checked it against
    the rows actually played, only against a bare team_id list the manifest itself never proved.
    Rev. 14 (§1m) closes both: `holdout_content_hashes` is checked for full dict equality
    (keys AND values) against each arm's own `holdout_teams` mapping (Task 9), which
    `_assert_rows_match_manifest` has already bound to that arm's OWN rows
    (`_assert_rows_bind_to_holdout_teams`) before this function ever reaches this check --
    so by the time the leakage guard's `team_ids=` argument below is built, it is provably the
    real six teams this schedule played, not merely whatever six labels a manifest or a caller
    happened to assert.

    holdout_candidate_species/reference_species (Rev. 18 fix, §1q): two GENUINELY SEPARATE
    mappings, never one dict doing double duty as both. Before this fix, the near-duplicate loop
    below iterated `reference_species` to get BOTH the six holdout candidates AND the reference
    set to compare them against -- passing `reference_teams=reference_species` (the SAME dict)
    for every team drawn FROM that same dict meant every team was compared against a reference
    set that included itself, and there was no way to supply the six holdout teams' OWN species
    at all (only their content hashes/paths were ever threaded through). `holdout_candidate_species`
    carries the six holdout teams' species sets (DESIGN sec 3.3's "holdout team" side);
    `reference_species` carries the nine existing Champions-M-A teams' species sets (its "touched
    or coverage team" side, §16 item 5) -- disjoint by construction now, not merely by caller
    discipline. `holdout_candidate_species`'s key set is checked against
    `manifest_a["holdout_teams"]` (below) exactly like `holdout_content_hashes` already is, so a
    caller cannot silently supply species for the wrong team_ids either.

    Candidate identity note (Rev. 3 P1 fix): arm A (hero_agent='heuristic') IS the shared
    candidate identity checked against I8-D/Coverage (DESIGN sec 5: "Candidate A is that shared
    candidate; Baseline B is the reference, not a separately-gated candidate"). Arm B
    (hero_agent='max_damage') is NEVER required to share candidate_identity with arm A --
    make_candidate_identity hashes hero_agent itself, so the two arms' identities differ by
    construction for every genuine run. What arm B must share with arm A is git_sha (same
    commit) and schedule_hash/panel_hash/seed_base (same battle conditions) -- checked explicitly
    below, and re-verified independently by pair_runs's own cross-run checks.

    stratum_env_override (Rev. 15 fix, §1n): NOT a source of truth -- this function never calls
    detect_stratum() itself, since the machine running combine_strength_holdout_arms need not be
    either arm's play machine. If given, it is an optional caller EXPECTATION, checked against
    what the two arms' own manifests actually recorded (already proven to agree with each other by
    the arm-vs-arm loop below); a mismatch aborts as a contradictory override, before the arms are
    ever compared to each other for pooling.

    Order: cheapest checks first, matching coverage_runner.py."""
    if not i8d_verdict_path:
        raise GateBAbort("i8d_verdict_path is required and must be non-empty -- Gate B may only run after an I8-D PASS on this candidate")
    if not coverage_verdict_path:
        raise GateBAbort("coverage_verdict_path is required and must be non-empty -- Gate B may only run after a Coverage PASS on this candidate")
    if not holdout_content_hashes:
        raise GateBAbort("holdout_content_hashes must be non-empty -- an empty mapping makes the disjointness/leakage guards vacuous")

    rows_a, manifest_a = _read_arm(arm_a_dir)
    rows_b, manifest_b = _read_arm(arm_b_dir)
    _assert_rows_match_manifest(rows_a, manifest_a, "A")
    _assert_rows_match_manifest(rows_b, manifest_b, "B")
    # Task-10 review-fix, P1 #1: each arm must BE the canonical 180-battle-key schedule, rebuilt
    # from its own recorded team_ids/panel_hash/seed_base -- the manifest-vs-rows checks above are
    # all self-consistency checks and cannot detect a truncated or reshaped arm on their own.
    _assert_rows_cover_canonical_schedule(rows_a, manifest_a, "A")
    _assert_rows_cover_canonical_schedule(rows_b, manifest_b, "B")
    # Rev. 19 fix (Task 9 review-fix sync, §1r): re-verify each arm's PUBLISHED seed log fresh,
    # before pairing or any verdict -- both arms independently, never relying on matching
    # manifest values alone (a doctored manifest could claim agreement without either seed log
    # genuinely verifying).
    _assert_seed_artifact_verified(arm_a_dir, manifest_a, "A")
    _assert_seed_artifact_verified(arm_b_dir, manifest_b, "B")

    if manifest_a["hero_agent"] != "heuristic":
        raise GateBAbort(f"arm A must be hero_agent='heuristic' (Candidate A per DESIGN sec 3.2), got {manifest_a['hero_agent']!r}")
    if manifest_b["hero_agent"] != "max_damage":
        raise GateBAbort(f"arm B must be hero_agent='max_damage' (Baseline B per DESIGN sec 3.2), got {manifest_b['hero_agent']!r}")
    if manifest_a["git_sha"] != manifest_b["git_sha"]:
        raise GateBAbort("arms disagree on git_sha -- they were not played on the same commit")
    # Task-10 review-fix, P1 #2: bind the COMBINE to the same commit the arms were played on,
    # before any repo-dependent guard runs. verify_baseline reads the working tree,
    # assert_no_holdout_leakage reads committed blobs via `git show HEAD:<path>`, and the
    # published bundle is stamped with manifest_a["git_sha"] -- so combining from a dirty tree, or
    # from a checkout sitting on a different commit, silently evaluates one commit's content and
    # labels the evidence with another's. Both conditions are technical aborts, not verdicts.
    if _git_is_dirty(cwd=repo_root):
        raise GateBAbort(
            f"refusing to combine from a dirty working tree at repo_root={repo_root!r} -- the "
            "baseline/leakage guards read this checkout, so uncommitted changes would be "
            "evaluated but never recorded in the published evidence"
        )
    head_sha = _git_sha(cwd=repo_root)
    if head_sha != manifest_a["git_sha"]:
        raise GateBAbort(
            f"HEAD at repo_root={repo_root!r} is {head_sha!r} but both arms were played at "
            f"git_sha={manifest_a['git_sha']!r} -- the repo-dependent guards would run against a "
            "different commit than the one this evidence claims"
        )
    # Rev. 15 fix (§1n, Task-3-review P1 #2): date_stratum_id added -- "different... date-strata
    # must abort" (stratum ITSELF is compared separately below, via assert_no_cross_stratum_
    # pooling, so its StrataPoolingError stays distinct from this loop's GateBAbort, matching the
    # exception-audit table's existing, deliberate separation of guard-specific exception types
    # from this trust-chain's single GateBAbort class -- see the comment above the upstream-
    # verdict try/except further down). platform_attestation is NOT compared here: two arms
    # legitimately played on the same physical box can report different platform.platform()
    # strings (e.g. an OS patch between arm A and arm B's runs) without that meaning anything --
    # only its non-empty presence is required (_validate_stratum_fields), not byte-equality.
    # Rev. 19 fix (Task 9 review-fix sync, §1r): calc_backend added -- oneshot vs persistent
    # produce the SAME config_hash/candidate_identity (make_config_hash's manifest does not
    # include calc_backend), so without this check two arms could silently run under different
    # backends while every OTHER identity field still matched.
    # Task-10 review-fix, P1 #1 (ordering consequence): holdout_teams is compared FIRST. Now that
    # schedule_hash is the canonical rebuild over the arm's own team_ids, two arms that played
    # different team sets necessarily disagree on schedule_hash too -- reporting the derived
    # symptom before the cause would be strictly less useful than naming the team-set mismatch.
    for field in ("holdout_teams", "schedule_hash", "panel_hash", "seed_base", "date_stratum_id", "calc_backend"):
        if manifest_a[field] != manifest_b[field]:
            raise GateBAbort(f"arms disagree on {field} -- they were not played under the same battle conditions")

    # Rev. 14 fix (§1m, third review round P1): Rev. 13's key-set-only check missed a caller
    # supplying every right team_id with a WRONG hash for one of them. manifest_a["holdout_teams"]
    # is now a real per-team {team_path, content_hash} mapping, independently proven (just above,
    # via _assert_rows_match_manifest -> _assert_rows_bind_to_holdout_teams) to describe what
    # THIS arm's rows actually played -- and proven identical to manifest_b's by the loop just
    # above. Require FULL dict equality (keys AND values) against holdout_content_hashes, not a
    # key-set check -- missing, extra, or value-wrong team_ids all abort here, before any guard
    # below ever runs.
    expected_hashes = {team_id: entry["content_hash"] for team_id, entry in manifest_a["holdout_teams"].items()}
    if holdout_content_hashes != expected_hashes:
        raise GateBAbort(
            "holdout_content_hashes does not match the six teams' content hashes this schedule "
            f"actually played (schedule: {expected_hashes}, holdout_content_hashes: "
            f"{holdout_content_hashes}) -- the leakage/disjointness guards must see every "
            "scheduled team with its real hash, not a subset or a wrong value"
        )
    # Task-10 review-fix, P1 #3: Rev. 18's key-set check on a caller-supplied
    # holdout_candidate_species is gone -- there is no caller-supplied species mapping to check
    # any more. Both sides of the near-duplicate comparison are derived below from the real
    # sealed .packed files, the candidate side keyed off manifest_a["holdout_teams"], which the
    # checks above have already bound to the rows actually played.

    # NF2 fix (Rev. 7): verify_i8d_verdict_artifact/verify_coverage_verdict_artifact raise
    # StrengthHoldoutRunError, not GateBAbort -- this plan's own documentation (§1a, and the
    # comment on the PairingError fix below) claimed the CLI catches
    # `except (GateBAbort, StrengthHoldoutRunError)`, but the actual CLI handlers (Task 11) only
    # ever caught `GateBAbort`. Rather than widen the CLI's except tuple to two abort classes,
    # normalize at the source: this is the ONLY place StrengthHoldoutRunError can cross into
    # combine_strength_holdout_arms, so catching it here folds it into GateBAbort -- the same
    # choice already made below for BaselineDriftError, PairingError, and LedgerError, and in
    # _read_arm above for ResultRowError/OSError/UnicodeDecodeError/json.JSONDecodeError. This is
    # NOT true of every guard failure in this function, though:
    # check_access/assert_disjoint_from_coverage/assert_no_holdout_leakage/
    # assert_no_cross_stratum_pooling below are deliberately left UNwrapped -- their
    # AccessBudgetError/HoldoutNotDisjointError/LeakageDriftError/StrataPoolingError/
    # UnattestedStratumError propagate raw by design (see the exception-audit table, §1f), not
    # by oversight. "One abort class" describes the upstream-verdict/pairing/ledger/row-schema
    # trust chain specifically, not this whole function's entire exception surface -- an earlier
    # draft of this exact comment claimed the broader, false version of this sentence.
    try:
        # Rev. 19 fix (Task 9 review-fix sync, §1r): calc_backend is now the manifest-bound value
        # Task 9 actually derived for this run (arm A and arm B already proven equal above) --
        # never the hardcoded literal "oneshot", which would silently pass an unverified backend
        # claim through to both upstream verifiers regardless of what the run actually used.
        verify_i8d_verdict_artifact(
            verdict_path=i8d_verdict_path, teams_root=teams_root,
            candidate_identity=manifest_a["candidate_identity"], git_sha=manifest_a["git_sha"],
            config_hash=manifest_a["config_hash"], hero_agent=manifest_a["hero_agent"],
            calc_backend=manifest_a["calc_backend"],
        )
        verify_coverage_verdict_artifact(
            verdict_path=coverage_verdict_path, teams_root=teams_root,
            candidate_identity=manifest_a["candidate_identity"], git_sha=manifest_a["git_sha"],
            config_hash=manifest_a["config_hash"], hero_agent=manifest_a["hero_agent"],
            calc_backend=manifest_a["calc_backend"],
        )
    except StrengthHoldoutRunError as exc:
        raise GateBAbort(f"upstream verdict verification failed: {exc}") from exc

    # Early, UNLOCKED budget check: fail fast, before 180 rows of pairing/verdict work, exactly as
    # the "cheapest checks first" ordering intends. Task-10 review-fix, P2 #5: this one is an
    # optimisation only -- it is NOT the authoritative check any more. The check that actually
    # gates the reservation runs again under the ledger lock, immediately before append_entry.
    check_access(read_ledger(ledger_path) if os.path.exists(ledger_path) else [], manifest_a["config_hash"], justification=None)

    # Baseline-drift guard (Rev. 4 P1 fix): Task 6 creates/loads the manifest, but nothing
    # previously called verify_baseline from the live combine flow -- "every guard wired" was
    # false for this specific guard. Wired here, before pairing/verdict, same as every other
    # provenance check.
    baseline = load_baseline(baseline_manifest_path)
    try:
        verify_baseline(baseline, repo_root=repo_root, teams_root=teams_root)
    except BaselineDriftError as exc:
        raise GateBAbort(f"baseline drift: {exc}") from exc

    assert_disjoint_from_coverage(holdout_content_hashes)
    assert_no_holdout_leakage(
        identifiers=list(holdout_content_hashes.values()) + list(holdout_content_hashes.keys()),
        # Rev. 12 P1 #2 fix (§1k): the leakage guard's content leg now reads each sealed team's
        # OWN committed .txt/.packed blob directly (scan_for_raw_payload_leakage), keyed by
        # team_id -- it no longer takes a hash mapping. holdout_content_hashes itself is
        # unchanged above (still required, still feeds assert_disjoint_from_coverage).
        # Rev. 14 fix (§1m): team_ids now comes from manifest_a["holdout_teams"] -- the VALIDATED,
        # ROW-BOUND mapping (_assert_rows_match_manifest, above) -- not from
        # holdout_content_hashes.keys() directly. By this point the two are already proven
        # dict-equal (the check just above), so the VALUES are identical either way; sourcing
        # from the bound manifest data is the structurally-safer choice regardless of any future
        # reordering of these checks.
        team_ids=sorted(manifest_a["holdout_teams"]),
        teams_root=teams_root,  # N3 fix: was silently hardcoded to "." inside the scan before
    )
    # Rev. 18 fix (§1q): the pre-Rev.-18 version of this loop iterated reference_species for
    # BOTH the candidates AND the reference set (`for team_id, species in
    # reference_species.items(): find_near_duplicate_flags(..., reference_teams=reference_species)`)
    # -- every team was compared against a reference set that included itself, and there was no
    # way to supply the six holdout teams' own species at all. holdout_candidate_species and
    # reference_species are now two genuinely separate mappings (validated above); iterating the
    # CANDIDATES and comparing each against the REFERENCE set is the correct DESIGN sec 3.3
    # geometry (six holdout teams checked against nine touched/coverage teams), and
    # find_near_duplicate_flags's own self-exclusion (Task 4) is defense in depth on top of that,
    # not the only thing preventing self-comparison.
    # Rev. 18 fix (§1q, self-found while wiring this loop, same pass): find_near_duplicate_flags
    # (Task 4) raises ValueError for malformed species data (an empty per-team species list, on
    # either the candidate or the reference side) -- the key-set checks above prove
    # holdout_candidate_species/reference_species name the RIGHT teams, but never validated that
    # each team's OWN species list is non-empty. Left unwrapped, a malformed entry would escape
    # combine_strength_holdout_arms as a raw ValueError, uncaught by the CLI (which only ever
    # catches GateBAbort, Task 11) -- the same "new guard, new raw exception" shape NF1/NF3 fixed
    # for _assert_rows_match_manifest/BattleResultWriter.write, applied here on introduction
    # rather than found later.
    # Task-10 review-fix, P1 #3: both mappings are now DERIVED from the real sealed team files
    # (see _derive_species_from_sealed_files) rather than taken from the caller, so the geometry
    # below is unchanged but the DATA is no longer an assertion anyone could shape at will.
    holdout_candidate_species, reference_species = _derive_species_from_sealed_files(
        manifest_a["holdout_teams"], teams_root,
    )
    try:
        near_dup_flags = []
        for team_id in sorted(holdout_candidate_species):
            near_dup_flags.extend(find_near_duplicate_flags(
                candidate_team_id=team_id, candidate_species=holdout_candidate_species[team_id],
                reference_teams=reference_species,
            ))
    except ValueError as exc:
        raise GateBAbort(f"near-duplicate check failed on malformed species data: {exc}") from exc
    # DESIGN sec 3.3: manual-review flag, never an auto-abort -- always computed and recorded
    # in the published bundle below (payload["near_duplicate_flags"]), never silently dropped.

    # Rev. 15 fix (§1n, Task-3-review P1 #2/#3): the combiner must not RE-DETERMINE stratum from
    # its own machine -- detect_stratum() reflects whatever box happens to run
    # combine_strength_holdout_arms, which need not be either arm's PLAY machine. Each arm's own
    # manifest already carries what Task 9 (its own Rev. 15 fix) recorded at play time, already
    # proven present/well-formed by _validate_stratum_fields above; compare the two ACTUAL arm
    # records instead of a freshly-detected third value.
    #
    # stratum_env_override is repurposed accordingly: no longer a source of truth fed into
    # detect_stratum, it is now an optional caller-supplied EXPECTATION checked against what the
    # arms actually recorded. A caller who expects e.g. a Windows-stratum combine and gets
    # Kaggle-stratum arms (or the reverse) gets a clear "contradictory override" abort instead of
    # silently combining the wrong stratum's arms.
    if stratum_env_override is not None and stratum_env_override != manifest_a["stratum"]:
        raise GateBAbort(
            f"stratum_env_override={stratum_env_override!r} contradicts the arms' own recorded "
            f"stratum={manifest_a['stratum']!r} -- the override must match what the arms actually "
            "recorded, not silently force a different stratum onto them"
        )
    assert_no_cross_stratum_pooling([
        StratumRecord(stratum=manifest_a["stratum"], platform_string=manifest_a["platform_attestation"], output_dir=arm_a_dir),
        StratumRecord(stratum=manifest_b["stratum"], platform_string=manifest_b["platform_attestation"], output_dir=arm_b_dir),
    ])

    try:
        # "Zwei Reste" fix (Rev. 6): expected_rows=len(rows_a) was tautological -- true by
        # construction for A, and redundant with _assert_rows_match_manifest's own n_rows check
        # for B. manifest_a["n_rows"] is the independently-sourced expectation (now itself
        # proven to match rows_a by the check above), so RowCountError becomes reachable again.
        pairs = pair_runs(rows_a, rows_b, expected_rows=manifest_a["n_rows"])
    except PairingError as exc:
        # Rev. 4 P2 fix: pair_runs can raise several PairingError subclasses (MissingPairError,
        # RunMismatchError, SelfComparisonError, DuplicateRowError, PairSeedMismatchError,
        # RowCountError) -- Rev. 3 only caught MissingPairError, letting the others escape raw
        # (uncaught by the CLI, which only ever catches GateBAbort -- corrected, Rev. 7 NF2: this
        # comment previously and incorrectly claimed the CLI also caught StrengthHoldoutRunError).
        # Catch the base class so every pairing failure becomes a uniform, CLI-handled abort.
        raise GateBAbort(f"pairing failed: {exc}") from exc

    safety_pass = compute_safety_pass(rows_a, rows_b)
    verdict = render_strength_holdout_verdict(pairs, safety_pass=safety_pass)

    staging_dir = f"{out_dir}.staging"
    for label, p in (("output", out_dir), ("staging", staging_dir)):
        if os.path.exists(p):
            raise GateBAbort(f"{label} directory {p} already exists")
    os.makedirs(staging_dir)
    shutil.copytree(arm_a_dir, os.path.join(staging_dir, "arm_a"))
    shutil.copytree(arm_b_dir, os.path.join(staging_dir, "arm_b"))

    cells_a = _build_cells(rows_a, {})
    cells_b = _build_cells(rows_b, {})
    _write_json_atomic(os.path.join(staging_dir, "cells.json"), {
        "cells_a": cells_a, "cells_b": cells_b, "aggregates_a": _build_aggregates(cells_a),
        "aggregates_b": _build_aggregates(cells_b),
    })

    payload = {
        "verdict": verdict.verdict, "reasons": verdict.reasons, "n_discordant": verdict.n_discordant,
        "n_total": verdict.n_total, "delta": verdict.delta, "exact_p": verdict.exact_p,
        "strength_delta": verdict.strength_delta, "cell_flips": verdict.cell_flips,
        "safety_pass": safety_pass, "candidate_identity": manifest_a["candidate_identity"],
        "git_sha": manifest_a["git_sha"], "config_hash_a": manifest_a["config_hash"],
        "config_hash_b": manifest_b["config_hash"], "schedule_hash": manifest_a["schedule_hash"],
        "panel_hash": manifest_a["panel_hash"], "stratum": manifest_a["stratum"],
        "near_duplicate_flags": [asdict(f) for f in near_dup_flags],
        "report_banner": "HELD-OUT RUN -- these numbers must never inform tuning.",
    }
    # N2 fix: result_sha256 must hash the EXACT bytes that land on disk, not a second,
    # independently-formatted json.dumps call -- _write_json_atomic (i8d_runner.py:106-112)
    # writes `json.dumps(obj, sort_keys=True, indent=2) + "\n"`; hashing a differently-formatted
    # re-serialization (no indent, no trailing newline, default separators) produces a DIFFERENT
    # digest than `sha256sum verdict.json` on the published file, making the ledger's
    # result_sha256 field decorative rather than verifiable. Compute the canonical text ONCE and
    # write it directly (single source of truth) instead of calling _write_json_atomic
    # separately and trusting the two calls stay byte-identical.
    verdict_text = json.dumps(payload, sort_keys=True, indent=2) + "\n"
    result_sha256 = hashlib.sha256(verdict_text.encode("utf-8")).hexdigest()
    verdict_tmp = os.path.join(staging_dir, "verdict.json.tmp")
    with open(verdict_tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(verdict_text)
    os.replace(verdict_tmp, os.path.join(staging_dir, "verdict.json"))

    # F6 fix (Rev. 6): ledger entry BEFORE publish, not after. Deliberately asymmetric, not
    # arbitrary ordering: a ledger `run` entry with no published bundle is a visible, auditable
    # failure (check_access sees the attempt was recorded and correctly refuses a retry without
    # justification, even though this specific run produced no evidence -- the budget is spent
    # slightly too eagerly, but that failure is loud). A published bundle with NO ledger entry is
    # the opposite: silent, and lets a subsequent run against the same config_hash slip straight
    # past check_access's one-attempt budget unnoticed -- exactly the held-out-data-reuse path
    # the ledger exists to prevent. If append_entry raises (e.g. LedgerError on a malformed
    # entry), os.replace(staging_dir, out_dir) below must never run, so a failed ledger write can
    # never coexist with a "successful"-looking published bundle.
    #
    # Task-10 review-fix, P2 #5: the budget CHECK and the reservation it authorises now happen
    # inside one exclusive lock. The early check_access far above is only a fail-fast; on its own
    # it left a very wide window (all of the guard/pairing/verdict work) in which a second combine
    # could read the same still-empty ledger, conclude the budget was free, and append and publish
    # too -- two "first" held-out runs against the same config_hash, both looking legitimate
    # afterwards. Re-reading the ledger here, under the lock, is what makes the decision
    # authoritative; the publish stays inside the lock as well so a reservation can never be
    # observed without the bundle it belongs to being on its way.
    with _ledger_lock(ledger_path):
        check_access(
            read_ledger(ledger_path) if os.path.exists(ledger_path) else [],
            manifest_a["config_hash"], justification=None,
        )
        try:
            append_entry(ledger_path, {
                "kind": "run", "date": date.today().isoformat(), "purpose": "champions-strength-holdout-v0",
                "panel_hash": manifest_a["panel_hash"], "schedule_hash": manifest_a["schedule_hash"],
                "git_sha": manifest_a["git_sha"], "config_hash": manifest_a["config_hash"],
                "result_sha256": result_sha256, "justification": None,
            })
        except LedgerError as exc:
            raise GateBAbort(f"ledger append failed, refusing to publish: {exc}") from exc

        os.replace(staging_dir, out_dir)
    return payload

```

**Note on `date.today()`:** the ledger schema requires a real calendar date string; this is the
one place in the plan that legitimately needs wall-clock time, unlike everything else which is
pure/deterministic. Not a placeholder — `heldout_ledger.py`'s own schema requires it.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest showdown_bot/tests/test_strength_holdout_runner.py -v`
Expected: all tests across Tasks 9 and 10 pass

**As executed (Rev. 20):** 108 passed in `test_strength_holdout_runner.py` (Tasks 9 + 10
combined), 405 passed / 1 xfailed across the proportional eval surface, 3343 collected
repo-wide, full suite 3340 passed / 2 skipped / 1 xfailed.

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/eval/strength_holdout_runner.py showdown_bot/tests/test_strength_holdout_runner.py
git commit -m "feat(champions): combine Gate B arms with all guards and sealed evidence"
```

**As executed (Rev. 20):** Task 10 landed as `24ada4b`, followed by two review-fix commits --
`895d1d2` (three P1s: canonical 180-key schedule rebuild, HEAD/dirty-tree binding, species
derivation from sealed files; two P2s: non-object JSON aborts, authoritative ledger lock) and
`53e6c9c` (one P1: full canonical row binding). `strength_holdout_verdict.py` is NOT in the stage
list -- Task 10 never modifies it; that path was also wrong (missing the `src/showdown_bot/`
segment).

---

## 14. Task 11 — CLI subcommands (arm + combine)

**Files:**
- Modify: `showdown_bot/src/showdown_bot/cli.py`
- Test: `showdown_bot/tests/test_cli_strength_holdout_gate.py`

**Fix vs. Rev. 1 (P1-9):** two real subcommands, no `schedule=None`/`NotImplementedError` left
in the CLI path itself. The only thing genuinely deferred behind D-1b is *which team files exist
on disk* — the CLI wiring, argument parsing, and orchestration calls are all real and tested now.

**Fix vs. Rev. 2 (§1b, P1):** `--i8d-verdict-path`/`--coverage-verdict-path` are now genuinely
required for the combine command — enforced in `main()` via `parser.error(...)` because this CLI
has no subparsers (see the corrected note below Step 3) — mirroring `combine_strength_holdout_arms`
itself now requiring them (Task 10).

- [ ] **Step 1: Write the failing tests**

```python
"""Gate B (Independent Strength Holdout) CLI subcommands — Task 11, plan §14.

Both subcommands are deliberately, honestly blocked until Task 13 seals the six holdout teams:
they name that blocker and exit non-zero rather than raising NotImplementedError, printing a
traceback, or (worse) silently "succeeding" against empty inputs. Nothing here starts a server,
plays a battle, or needs a team file.
"""
from __future__ import annotations

import subprocess
import sys

import pytest


def _run_cli(*argv):
    return subprocess.run(
        [sys.executable, "-m", "showdown_bot.cli", *argv], capture_output=True, text=True,
    )


def test_cli_exposes_both_strength_holdout_subcommands():
    result = _run_cli("--help")
    assert "champions-strength-holdout-arm" in result.stdout
    assert "champions-strength-holdout-combine" in result.stdout


def test_arm_subcommand_requires_hero_agent_and_out_dir():
    result = _run_cli("champions-strength-holdout-arm")
    assert result.returncode != 0
    # Without this the assertion below is vacuous: an UNKNOWN command makes argparse print the
    # full usage line, which already contains "--out-dir" -- so the test would pass just as well
    # against a CLI that has never heard of this subcommand (verified: it did, before Task 11).
    assert "invalid choice" not in result.stderr
    assert "--hero-agent" in result.stderr or "--out-dir" in result.stderr


def test_combine_subcommand_requires_both_arm_dirs():
    result = _run_cli("champions-strength-holdout-combine")
    assert result.returncode != 0
    assert "--arm-a-dir" in result.stderr or "--arm-b-dir" in result.stderr


def test_combine_subcommand_requires_both_upstream_verdict_paths():
    # Rev. 3 fix: these must be genuinely required, not silently optional (Task 10's core-function
    # bug, mirrored here at the CLI layer). Supplying everything EXCEPT the two verdict paths is
    # what isolates this check -- the bare invocation above would already fail on the arm dirs.
    result = _run_cli(
        "champions-strength-holdout-combine",
        "--arm-a-dir", "a", "--arm-b-dir", "b", "--out-dir", "out",
    )
    assert result.returncode != 0
    assert "invalid choice" not in result.stderr  # see the arm test above for why
    assert "--i8d-verdict-path" in result.stderr or "--coverage-verdict-path" in result.stderr


def test_combine_still_requires_the_coverage_verdict_path_when_only_i8d_is_given():
    # Guards against a check that stops at the first missing path: the coverage verdict is not
    # optional just because the I8-D one was supplied.
    result = _run_cli(
        "champions-strength-holdout-combine",
        "--arm-a-dir", "a", "--arm-b-dir", "b", "--out-dir", "out",
        "--i8d-verdict-path", "i8d.json",
    )
    assert result.returncode != 0
    assert "--coverage-verdict-path" in result.stderr


# NF4 fix (Rev. 8): _describe_strength_holdout_combine_error is a pure function, fully testable
# today independent of Task 13 -- these tests do NOT go through the CLI subprocess above (which
# can't reach the real combine_strength_holdout_arms call yet), they call the mapping helper
# directly.
def test_describe_combine_error_maps_access_budget_error():
    from showdown_bot.cli import _describe_strength_holdout_combine_error
    from showdown_bot.eval.heldout_ledger import AccessBudgetError
    message, code = _describe_strength_holdout_combine_error(AccessBudgetError("budget spent"))
    assert "policy decision" in message
    assert "justification" in message
    assert code == 2


def test_describe_combine_error_maps_all_four_integrity_guards_to_the_same_code():
    from showdown_bot.cli import _describe_strength_holdout_combine_error
    from showdown_bot.eval.holdout_disjointness import HoldoutNotDisjointError
    from showdown_bot.eval.holdout_leakage_scan import LeakageDriftError
    from showdown_bot.eval.strata_guard import StrataPoolingError, UnattestedStratumError
    for exc in (HoldoutNotDisjointError("x"), LeakageDriftError("x"), StrataPoolingError("x"), UnattestedStratumError("x")):
        message, code = _describe_strength_holdout_combine_error(exc)
        assert "integrity" in message
        assert code == 3


def test_describe_combine_error_maps_leakage_scan_error_distinctly_from_leakage_drift_error():
    from showdown_bot.cli import _describe_strength_holdout_combine_error
    from showdown_bot.eval.holdout_leakage_scan import LeakageScanError
    message, code = _describe_strength_holdout_combine_error(LeakageScanError("git missing"))
    assert "could not be completed" in message
    assert code == 4  # NOT 3 -- "couldn't check" must never read as "checked, found a problem"


def test_describe_combine_error_maps_gatebabort_to_exit_code_one_unchanged():
    from showdown_bot.cli import _describe_strength_holdout_combine_error
    from showdown_bot.eval.strength_holdout_runner import GateBAbort
    message, code = _describe_strength_holdout_combine_error(GateBAbort("blocked"))
    assert message == "blocked"
    assert code == 1


def test_describe_combine_error_refuses_to_mislabel_an_unrecognized_exception_type():
    from showdown_bot.cli import _describe_strength_holdout_combine_error
    with pytest.raises(TypeError, match="unrecognized"):
        _describe_strength_holdout_combine_error(ValueError("not a Gate B exception"))


def test_leakage_scan_error_is_not_swallowed_by_the_leakage_drift_branch():
    # LeakageScanError and LeakageDriftError live in the same module and are easy to collapse into
    # one isinstance tuple. If they ever share a branch this test fails, because "the scan could
    # not run" (4) and "the scan ran and found a leak" (3) are different operator decisions.
    from showdown_bot.cli import _describe_strength_holdout_combine_error
    from showdown_bot.eval.holdout_leakage_scan import LeakageDriftError, LeakageScanError
    _, drift_code = _describe_strength_holdout_combine_error(LeakageDriftError("x"))
    _, scan_code = _describe_strength_holdout_combine_error(LeakageScanError("x"))
    assert (drift_code, scan_code) == (3, 4)


# --- End-to-end handler regressions: the honest Task-13 blocker, no teams/server/battles -------


def test_full_arm_invocation_reaches_the_named_task13_blocker_without_a_traceback(tmp_path):
    result = _run_cli(
        "champions-strength-holdout-arm",
        "--hero-agent", "heuristic",
        "--out-dir", str(tmp_path / "arm_out"),
        "--seed-log-path", str(tmp_path / "seeds.jsonl"),
        "--teams-root", str(tmp_path),
    )
    assert result.returncode == 1, result.stderr
    assert "Traceback" not in result.stderr
    assert "NotImplementedError" not in result.stderr
    assert "champions-strength-holdout-arm:" in result.stderr
    assert "Task 13" in result.stderr
    # Nothing was published: an honest stop must not leave a half-built artifact behind.
    assert not (tmp_path / "arm_out").exists()


def test_full_combine_invocation_reaches_the_named_task13_blocker_without_a_traceback(tmp_path):
    result = _run_cli(
        "champions-strength-holdout-combine",
        "--arm-a-dir", str(tmp_path / "arm_a"),
        "--arm-b-dir", str(tmp_path / "arm_b"),
        "--out-dir", str(tmp_path / "combined"),
        "--i8d-verdict-path", str(tmp_path / "i8d.json"),
        "--coverage-verdict-path", str(tmp_path / "cov.json"),
    )
    assert result.returncode == 1, result.stderr
    assert "Traceback" not in result.stderr
    assert "NotImplementedError" not in result.stderr
    assert "champions-strength-holdout-combine:" in result.stderr
    assert "Task 13" in result.stderr
    assert not (tmp_path / "combined").exists()


def test_existing_commands_still_parse_without_the_new_gate_b_flags():
    # The new flags are global (this CLI has no subparsers), so they must keep an empty default --
    # marking any of them required=True would break every other command's invocation.
    from showdown_bot.cli import _build_parser
    args = _build_parser().parse_args(["smoke"])
    assert args.command == "smoke"
    for flag in ("hero_agent", "seed_log_path", "arm_a_dir", "arm_b_dir", "coverage_verdict_path"):
        assert getattr(args, flag) == ""

```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest showdown_bot/tests/test_cli_strength_holdout_gate.py -v`
Expected: FAIL — the subcommand tests fail because the commands don't exist; the
`test_describe_combine_error_*` tests fail with `ImportError: cannot import name
'_describe_strength_holdout_combine_error'` (Rev. 8's new function, not written until Step 3)

**As executed (Rev. 21):** 14/14 RED. The two headline errors were `ImportError: cannot import
name '_describe_strength_holdout_combine_error' from 'showdown_bot.cli'` and
`AttributeError: 'Namespace' object has no attribute 'hero_agent'`.

Two of the original plan tests were found to be **vacuous** and were strengthened rather than
carried over as written: asserting only `returncode != 0` and `"--out-dir" in stderr` passes
against a CLI that has never heard of the subcommand, because an *invalid choice* makes argparse
print the full usage line — which already contains `--out-dir`. Both now also assert
`"invalid choice" not in result.stderr`.

- [ ] **Step 3: Write the implementation**

Following `run_coverage_gate_cli`'s exact shape, add two handlers and subparsers to `cli.py`:

```python
# --- cli.py: the three new module-level functions (verbatim, b71923f) ------------------
def run_strength_holdout_arm_cli(args) -> int:
    """Gate B, one arm of the 180-battle-key strength holdout (plan §14, Task 11).

    Deliberately blocked today: a real ``holdout_teams`` mapping (team_id ->
    {team_path, content_hash}) only exists once Task 13 seals the six teams. This raises a clear,
    NAMED error rather than accepting an empty or invented mapping and failing confusingly deeper
    in the call stack -- ``run_strength_holdout_arm`` itself is fully implemented and tested
    (Task 9); only this handler's ability to SOURCE real teams is pending D-1b.
    """
    import sys

    from showdown_bot.eval.strength_holdout_runner import GateBAbort
    from showdown_bot.eval.strata_guard import UnattestedStratumError

    try:
        raise GateBAbort(
            "no sealed holdout team IDs available yet -- Task 13 (blocked on the D-1b "
            "source-proof) must seal six teams and register their IDs before this subcommand "
            "can build a real schedule; this is a deliberate, named stop, not a bug"
        )
    except (GateBAbort, UnattestedStratumError) as exc:
        # Verified sufficient, Rev. 9 (§1h's audit table): every exception reachable from
        # run_strength_holdout_arm's own call graph is GateBAbort, with one still-untraced trust
        # boundary (_derive_config_hash -> resolve_coverage_provenance, disclosed since Rev. 1/2).
        # Rev. 15 (§1n) added detect_stratum() to that call graph, which raises its OWN
        # UnattestedStratumError rather than GateBAbort -- hence the two-class tuple.
        print(f"champions-strength-holdout-arm: {exc}", file=sys.stderr)
        return 1


def _describe_strength_holdout_combine_error(exc: BaseException) -> tuple[str, int]:
    """NF4 fix (Rev. 8): ``combine_strength_holdout_arms`` can raise 7 exception CLASSES across 4
    meaningfully DISTINCT message/exit-code CATEGORIES (§1f/§1g's audit table) -- Task 10
    deliberately keeps these distinct rather than folding all of them into ``GateBAbort``:

    1. ``GateBAbort`` -- the row-schema/manifest/upstream-verdict/pairing/ledger/git-infra trust
       chain, exit 1.
    2. ``AccessBudgetError`` -- a policy refusal with a defined override (pass a justification),
       not a technical failure; collapsing it would hide the one exception an operator may
       legitimately overrule, exit 2.
    3. ``HoldoutNotDisjointError``/``LeakageDriftError``/``StrataPoolingError``/
       ``UnattestedStratumError`` -- four DIFFERENT classes, ONE category: integrity judgments
       about the holdout itself, exit 3.
    4. ``LeakageScanError`` -- the scan could not even run; neither a policy refusal nor an
       integrity judgment, exit 4. Checked BEFORE ``LeakageDriftError`` would be reached, because
       "couldn't check" must never read as "checked, found a problem".

    Returns ``(message, exit_code)``. Deliberately does not recognize anything outside those 7
    classes -- an unrecognized type raises ``TypeError`` rather than being mislabeled.
    """
    from showdown_bot.eval.heldout_ledger import AccessBudgetError
    from showdown_bot.eval.holdout_disjointness import HoldoutNotDisjointError
    from showdown_bot.eval.holdout_leakage_scan import LeakageDriftError, LeakageScanError
    from showdown_bot.eval.strata_guard import StrataPoolingError, UnattestedStratumError
    from showdown_bot.eval.strength_holdout_runner import GateBAbort

    if isinstance(exc, AccessBudgetError):
        return (
            f"ledger budget refused: {exc} (this is a policy decision, not a technical failure "
            "-- pass a justification to override it if that override is warranted)", 2,
        )
    if isinstance(exc, LeakageScanError):
        return (f"leakage scan could not be completed: {exc}", 4)
    if isinstance(exc, (HoldoutNotDisjointError, LeakageDriftError, StrataPoolingError, UnattestedStratumError)):
        return (f"holdout integrity check failed: {exc}", 3)
    if isinstance(exc, GateBAbort):
        return (str(exc), 1)
    raise TypeError(
        f"unrecognized exception type for the strength-holdout combine CLI: {type(exc).__name__}"
    ) from exc


def run_strength_holdout_combine_cli(args) -> int:
    """Gate B, combine the two published arms into a verdict (plan §14, Task 11).

    Blocked today for the same reason as the arm handler: ``holdout_content_hashes`` needs Task
    13's six sealed teams. Note the species side is NOT a CLI concern -- Task 10's review-fix
    removed the ``holdout_candidate_species``/``reference_species`` parameters and derives both
    mappings from the real sealed ``.packed`` files. Passing ``{}`` here (Rev. 3's shape) would
    now abort anyway, and doing so silently is exactly the vacuous-guard trust shape this plan
    exists to eliminate.
    """
    import sys

    from showdown_bot.eval.heldout_ledger import AccessBudgetError
    from showdown_bot.eval.holdout_disjointness import HoldoutNotDisjointError
    from showdown_bot.eval.holdout_leakage_scan import LeakageDriftError, LeakageScanError
    from showdown_bot.eval.strata_guard import StrataPoolingError, UnattestedStratumError
    from showdown_bot.eval.strength_holdout_runner import GateBAbort

    try:
        raise GateBAbort(
            "no sealed holdout team hashes available yet -- Task 13 (blocked on the D-1b "
            "source-proof) must seal six teams before this subcommand has a real "
            "holdout_content_hashes mapping to pass; this is a deliberate, named stop, not a "
            "bug. combine_strength_holdout_arms itself is fully functional and tested "
            "(Task 10) -- only this CLI's data sourcing is pending."
        )
    except (GateBAbort, AccessBudgetError, HoldoutNotDisjointError, LeakageDriftError,
            LeakageScanError, StrataPoolingError, UnattestedStratumError) as exc:
        # NF4 fix (Rev. 8): widened from `except GateBAbort` alone -- that shape let the other six
        # classes escape as raw tracebacks the moment Task 13 unblocks a real combine call beneath
        # this still-deliberate early stop. The stop is unchanged; only the boundary is now honest
        # about what it must eventually handle.
        message, code = _describe_strength_holdout_combine_error(exc)
        print(f"champions-strength-holdout-combine: {message}", file=sys.stderr)
        return code




# --- cli.py, inside _build_parser(): the five new GLOBAL flags -------------------------
# (shown at their real indentation; `parser` is the ArgumentParser built above them)
    # Gate B (strength holdout, Task 11). All five are GLOBAL flags with an empty default, like
    # --i8d-verdict-path above and for the same reason: this CLI has a single flat `command`
    # positional, not argparse subparsers, so `required=True` on any of them would make EVERY
    # other command (ladder, smoke, gauntlet, ...) refuse to start. Per-command required-ness is
    # enforced in main() via parser.error(), exactly as generalisation-plan/-analyze already do.
    parser.add_argument(
        "--hero-agent",
        dest="hero_agent",
        default="",
        help="Which arm to play for champions-strength-holdout-arm (required for it): "
        "'heuristic' is Candidate A, 'max_damage' is Baseline B.",
    )
    parser.add_argument(
        "--seed-log-path",
        dest="seed_log_path",
        default="",
        help="Path the server's seed log is written to (champions-strength-holdout-arm, "
        "required): the arm refuses to run unless the log is built during this very run.",
    )
    parser.add_argument(
        "--arm-a-dir",
        dest="arm_a_dir",
        default="",
        help="Published Candidate-A arm directory (champions-strength-holdout-combine, required).",
    )
    parser.add_argument(
        "--arm-b-dir",
        dest="arm_b_dir",
        default="",
        help="Published Baseline-B arm directory (champions-strength-holdout-combine, required).",
    )
    parser.add_argument(
        "--coverage-verdict-path",
        dest="coverage_verdict_path",
        default="",
        help="Path to the Coverage gate's verdict.json for the SAME candidate "
        "(champions-strength-holdout-combine, required): Gate B may only run after an I8-D PASS "
        "AND a Coverage PASS. Global default is empty so other commands are unaffected.",
    )


# --- cli.py, inside main(): the two dispatch branches ----------------------------------
    if args.command == "champions-strength-holdout-arm":
        # parser.error() (not argparse `required=True`) because these are shared GLOBAL flags --
        # see the Gate B block in _build_parser. It is still argparse's own error path: usage to
        # stderr, exit 2, same as generalisation-plan's existing check.
        missing = [
            flag for flag, value in (
                ("--hero-agent", args.hero_agent), ("--out-dir", args.out_dir),
                ("--seed-log-path", args.seed_log_path), ("--teams-root", args.teams_root),
            ) if not value
        ]
        if missing:
            parser.error(f"champions-strength-holdout-arm requires {', '.join(missing)}")
        raise SystemExit(run_strength_holdout_arm_cli(args))

    if args.command == "champions-strength-holdout-combine":
        missing = [
            flag for flag, value in (
                ("--arm-a-dir", args.arm_a_dir), ("--arm-b-dir", args.arm_b_dir),
                ("--out-dir", args.out_dir), ("--i8d-verdict-path", args.i8d_verdict_path),
                ("--coverage-verdict-path", args.coverage_verdict_path),
            ) if not value
        ]
        if missing:
            parser.error(f"champions-strength-holdout-combine requires {', '.join(missing)}")
        raise SystemExit(run_strength_holdout_combine_cli(args))
```

**Corrected, Rev. 21 (mechanical sync against `b71923f`):** earlier revisions of this paragraph
said to "register both subparsers … all five `required=True`, mirroring `champions-coverage-gate`'s
existing argparse block exactly." Those two instructions contradict each other, and the first is
simply false about this CLI: **`cli.py` has no argparse subparsers at all.** It has a single flat
`command` positional with a `choices` list, and every option is a GLOBAL flag shared by every
command. `required=True` on any shared flag would make `ladder`, `smoke`, `gauntlet` and every
other command refuse to start — which is exactly why the pre-existing `--i8d-verdict-path` carries
the comment "Global default is empty so other commands are unaffected; only
champions-coverage-gate's own handler requires it."

What was actually implemented, and what this plan now specifies:

- Both command names are added to the `choices` list of the flat `command` positional.
- The five new flags (`--hero-agent`, `--seed-log-path`, `--arm-a-dir`, `--arm-b-dir`,
  `--coverage-verdict-path`) are registered as GLOBAL flags with `default=""`, alongside the
  already-existing `--out-dir`, `--teams-root` and `--i8d-verdict-path`.
- Per-command required-ness is enforced in `main()` via `parser.error(...)`, naming every missing
  flag at once. This is still argparse's own error path — usage on stderr, exit 2 — and it is the
  convention this codebase already uses for `generalisation-plan`/`generalisation-analyze`.
- A dedicated test (`test_existing_commands_still_parse_without_the_new_gate_b_flags`) pins the
  empty defaults, so a later `required=True` cannot be reintroduced without a failing test.

The Rev. 3 intent is unchanged and fully met: `--i8d-verdict-path`/`--coverage-verdict-path` are
genuinely required for `champions-strength-holdout-combine` and refuse the run before any work
happens; only the enforcement mechanism differs from the (impossible) sketch.

**Note on both CLI handlers (updated, Rev. 8):** both `run_strength_holdout_arm_cli` and
`run_strength_holdout_combine_cli` always raise `GateBAbort` themselves today, by design — honest
about the real, current blocker (no sealed teams exist) rather than accepting `schedule=None`/`{}`
and failing confusingly deeper in the call stack, or (Rev. 3's bug) not failing at all.
`combine_strength_holdout_arms`/`run_strength_holdout_arm` **themselves** are fully functional and
tested today (Tasks 9-10, via direct calls with realistic fake inputs) — only this CLI's ability
to *source* real values is pending Task 13. Both subcommands say so explicitly when invoked. The
combine handler's except-tuple is deliberately widened NOW, ahead of Task 13, so the boundary
shape is already correct the moment real data sourcing lands — not a second CLI edit deferred to
whenever Task 13 closes. `_describe_strength_holdout_combine_error` is a pure function, and its
own RED tests are already part of Step 1 above (not shown again here) — this keeps the task's
RED-before-GREEN ordering intact instead of introducing tests after the implementation that
already satisfies them.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest showdown_bot/tests/test_cli_strength_holdout_gate.py -v`
Expected: 14 passed — the 9 plan tests (4 CLI-surface + 5 error-mapping), plus a second
verdict-path case proving the coverage path is not optional once the I8-D one is supplied, a
LeakageScanError-vs-LeakageDriftError separation test, the two end-to-end handler regressions
(full arm and full combine invocation each reaching the named Task 13 blocker with exit 1 and no
traceback, needing no teams/server/battles), and the empty-defaults test that pins the flat-CLI
contract. Proportional: 347 passed across all nine CLI test files plus the runner/verdict/strata
surface; 3357 collected repo-wide.

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/cli.py showdown_bot/tests/test_cli_strength_holdout_gate.py
git commit -m "feat(champions): add Gate B arm and combine CLI subcommands"
```

---

## 15. Task 12 — Team sealing/provenance tool (real `.txt`+`.packed` hash)

**Files:**
- Create: `showdown_bot/src/showdown_bot/eval/team_sealing.py`
- Test: `showdown_bot/tests/test_team_sealing.py`

**Fix vs. Rev. 1 (P1-7):** Rev. 1 defined a *different, incompatible, same-named*
`_team_content_hash(team_path)` that hashed only `.txt` as plain text — a live naming collision
with the real `panel.team_content_hash(teams_root, team_path)`, which requires and hashes
**both** `.txt` and `.packed` together. This task now imports the real function; it does not
redefine it.

- [ ] **Step 1: Write the failing tests**

```python
# showdown_bot/tests/test_team_sealing.py
import pytest

from showdown_bot.eval.team_sealing import seal_team, SealingError
from showdown_bot.eval.panel import PanelError


def _write_fixture_team(tmp_path, txt_content, packed_content):
    txt = tmp_path / "fixture_team.txt"
    packed = tmp_path / "fixture_team.packed"
    txt.write_text(txt_content, encoding="utf-8")
    packed.write_text(packed_content, encoding="utf-8")
    return txt, packed


def test_seal_team_records_the_real_txt_plus_packed_content_hash(tmp_path):
    txt, _ = _write_fixture_team(tmp_path, "Fixture Mon @ Focus Sash\n", "|packed-fixture|")
    record = seal_team(
        team_id="holdout_0", teams_root=str(tmp_path), team_path="fixture_team.txt",
        archetype="fixture-archetype", source_description="synthetic fixture, not a real team",
        source_date="2026-07-21", blind_attestation="fixture attestation for testing only",
    )
    from showdown_bot.eval.panel import team_content_hash
    assert record.content_hash == team_content_hash(str(tmp_path), "fixture_team.txt")


def test_seal_team_changes_hash_if_only_the_packed_file_changes(tmp_path):
    # this is the exact bug Rev. 1 had: a .txt-only hash can't see packed-only drift.
    _write_fixture_team(tmp_path, "Fixture Mon @ Focus Sash\n", "|packed-version-1|")
    r1 = seal_team(team_id="holdout_0", teams_root=str(tmp_path), team_path="fixture_team.txt",
                    archetype="x", source_description="d", source_date="2026-07-21", blind_attestation="a")
    (tmp_path / "fixture_team.packed").write_text("|packed-version-2|", encoding="utf-8")
    r2 = seal_team(team_id="holdout_0", teams_root=str(tmp_path), team_path="fixture_team.txt",
                    archetype="x", source_description="d", source_date="2026-07-21", blind_attestation="a")
    assert r1.content_hash != r2.content_hash


def test_seal_team_rejects_a_missing_packed_file(tmp_path):
    (tmp_path / "fixture_team.txt").write_text("Fixture Mon @ Focus Sash\n", encoding="utf-8")
    with pytest.raises(SealingError, match="packed"):
        seal_team(team_id="holdout_0", teams_root=str(tmp_path), team_path="fixture_team.txt",
                   archetype="x", source_description="d", source_date="2026-07-21", blind_attestation="a")


def test_seal_team_rejects_an_empty_blind_attestation(tmp_path):
    _write_fixture_team(tmp_path, "Fixture Mon @ Focus Sash\n", "|packed|")
    with pytest.raises(SealingError, match="blind_attestation"):
        seal_team(team_id="holdout_0", teams_root=str(tmp_path), team_path="fixture_team.txt",
                   archetype="x", source_description="d", source_date="2026-07-21", blind_attestation="")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest showdown_bot/tests/test_team_sealing.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# showdown_bot/src/showdown_bot/eval/team_sealing.py
"""Provenance/hash sealing for Gate B holdout teams (DESIGN sec 3.4). Uses the REAL canonical
team-content hash (eval/panel.py::team_content_hash, .txt + .packed together) -- Rev. 1 defined
a different, incompatible, same-named local function that hashed only .txt; that was a live
naming collision with real code, not just an omission, and is not repeated here.

This module only RECORDS a seal for team files that already exist on disk -- it does not select,
generate, or fetch team content (that is Open Decision / Task 13, resolved outside this tool).
"""
from __future__ import annotations

from dataclasses import dataclass

from showdown_bot.eval.panel import team_content_hash, PanelError


class SealingError(Exception):
    pass


@dataclass(frozen=True)
class SealedTeamRecord:
    team_id: str
    content_hash: str
    archetype: str
    source_description: str
    source_date: str
    blind_attestation: str


def seal_team(
    *, team_id: str, teams_root: str, team_path: str, archetype: str,
    source_description: str, source_date: str, blind_attestation: str,
) -> SealedTeamRecord:
    """Does NOT run legality validation itself (the existing `validate-team` tool already does
    that for every prior pool per PROVENANCE.md) -- run it separately first and refuse to seal
    on a non-zero exit."""
    if not blind_attestation.strip():
        raise SealingError(
            "blind_attestation must be non-empty -- DESIGN sec 3.4 requires the sourcing "
            "rationale to be fixed and recorded before the bot ever sees this team"
        )
    try:
        content_hash = team_content_hash(teams_root, team_path)
    except PanelError as exc:
        raise SealingError(f"cannot seal {team_path!r}: {exc}") from exc
    return SealedTeamRecord(
        team_id=team_id, content_hash=content_hash, archetype=archetype,
        source_description=source_description, source_date=source_date,
        blind_attestation=blind_attestation,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest showdown_bot/tests/test_team_sealing.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add showdown_bot/src/showdown_bot/eval/team_sealing.py showdown_bot/tests/test_team_sealing.py
git commit -m "fix(champions): team sealing uses the real .txt+.packed content hash, not a reimplementation"
```

**Checked against Rev. 12's Task 2 fix (§1k, P1 #2), no change needed:** `seal_team`/
`SealedTeamRecord` were never a caller of the leakage guard and are not one now — they compute and
return the combined `team_content_hash` for provenance recording at seal time, which remains
exactly the right tool for team identity (Task 5's disjointness check, Task 9's `opp_team_hash`
row-stamping). `scan_for_raw_payload_leakage` (Task 2) does not need `seal_team` to hand it raw
bytes: it reads each sealed team's `.txt`/`.packed` payload itself, live, from the team's COMMITTED
git blob at scan time (`team_id` + `HOLDOUT_TEAMS_DIR`) — more robust than threading a value
captured once at seal time through two further task boundaries, since DESIGN sec 3.4 already
guarantees sealed content cannot change afterward, and by the time Task 10's `combine` step can
run at all, Task 13's own definition-of-done (item 7, below) already requires the sealed team
files to be committed.

---

## 16. Task 13 — Source, seal, and register the six holdout teams

Unchanged in structure from Rev. 1, with the pre-conditions from §2 now explicit gate items.

**Source status, 2026-07-22 (see §2a):** the source condition is **SATISFIED**. The authorized
source is the VGCPastes "Champions M-A Featured Teams" selection fixed in §2a — **not** Rutgers
Scarlet Classic, and **not** the UmbreNews fallback, which is moot. Items 1 and 2 below are
restated accordingly; every other item is unchanged and still outstanding.

**Definition of done:**
1. ~~Source-proof passes for Rutgers Scarlet Classic (or, only if that fails, UmbreNews) per §2.~~
   **Superseded by §2a and DONE:** the six §2a teams are frozen with SHA-256 under
   `docs/projects/champions/audits/2026-07-22-task13-vgcpastes-source-evidence/`, each publishing
   six complete Pokémon with item, ability, level, **EVs, nature** and four moves. The selection
   order is reproducible from the frozen sheet export in that same directory.
2. Six teams selected by the **§2a** selection rule (not §2 item 2, which governed the superseded
   Rutgers path), each `validate-team`-legal for `gen9championsvgc2026regma`. **Legality already
   confirmed** for all six against the pinned checkout `f8ac140` (exit 0 each); it is re-run on the
   final `.txt`/`.packed` artifacts as part of this task.
3. Each sealed via Task 12's `seal_team` (real `.txt`+`.packed` hash), with a specific,
   non-generic `blind_attestation`.
4. `assert_disjoint_from_coverage` (Task 5) passes against the real six hashes.
5. `find_near_duplicate_flags` (Task 4) run, once per holdout candidate, against the nine
   existing Champions-M-A **opponent-side** teams as `reference_teams` -- disposition (a written
   note: dismissed as coincidental staple overlap, or escalated) recorded for every flag before
   proceeding. **"Nine" verified, Rev. 18 (§1q, this round) -- not previously traceable to a
   concrete list:** the on-disk `gen9championsvgc2026regma` team set is 10 files total, not
   nine -- one shared hero (`showdown_bot/teams/fixed_champions_v0.txt`) plus nine opponent-side
   teams across two panels: `config/eval/panels/panel_champions_v0.yaml`'s 3 dev
   (`goodstuff`/`tailwind_offense`/`trick_room`) + 2 heldout (`rain_offense`/`disruption`) = 5,
   and `config/eval/panels/panel_champions_coverage_v0.yaml`'s 2 dev
   (`cov_foe_slot0`/`cov_foe_slot1`) + 2 heldout (`cov_foe_both`/`cov_foe_tie`) = 4. `5 + 4 = 9`
   reconciles exactly -- "nine" means these nine opponent-side teams, with the shared hero
   correctly EXCLUDED (DESIGN sec 3.3 flags overlap against a "touched or coverage TEAM," which
   in context means an opponent this bot has already been tested against, not its own fixed
   hero -- the hero is the same file across every one of these panels by design, so including it
   would make every future holdout candidate trivially "overlap" with itself via the hero side of
   the comparison, which is not what this check exists to catch). Task 13's own sourcing/
   sealing work still owns deriving these nine teams' actual species lists (parsing the real
   `.txt`/`.packed` files at these paths into `reference_teams: dict[str, list[str]]`) -- not
   specified further here; it is owned by Task 13's own sourcing/sealing work, whose source
   condition is now satisfied per §2a.
6. `assert_no_holdout_leakage` (Task 2, both the identifier scan and the raw `.txt`/`.packed`
   payload scan, Rev. 12 §1k) returns zero hits outside the allowlist.
7. The panel YAML and holdout manifest JSON get real content, and the Gate B baseline manifest
   (`config/eval/baselines/champions-strength-holdout-v0.json`) is committed **once, with its final
   real values** — not a Task-6 placeholder that is later back-filled (a baseline manifest is
   immutable after its first commit: `test_baseline_manifest_git_immutability`). Their hashes are
   frozen into Task 1's constants (`STRENGTH_HOLDOUT_EXPECTED_PANEL_HASH` /
   `STRENGTH_HOLDOUT_EXPECTED_MANIFEST_HASH`) in the same step-3 commit that creates the manifest.
8. ~~`_derive_config_hash` (Task 9) reconciled against the real `resolve_coverage_provenance`
   implementation~~ — **DONE, Rev. 10 (§1i)**, ahead of Task 13 rather than deferred to it.
9. Full offline suite green, including every RED/GREEN pair from Tasks 1-12.
10. **Still no live run.** Task 13's completion is "ready to run," not "ran" — the live run is
    §17, separately authorized, after this whole plan is reviewed and merged.

---

## 17. Self-review (writing-plans skill checklist, Rev. 10)

**0. Process note, stated plainly (Rev. 6):** F3 and F6 were part of the original third-round
review and were not new. They went unaddressed through §1c and §1d not because they were
deferred with a reason, but because my own self-review passes for those revisions checked "does
the new code do what this round's findings asked" rather than "does every trust boundary in the
whole function now hold" — a narrower question that a finding sitting just outside the round's
explicit list can pass right through. §17.3 below named this as a standing check, not just a
one-off fix.

**0b. Process note, updated (Rev. 7):** naming the standing check as a principle was not enough —
this round's own new code (`_read_arm`'s `validate_battle_row` wrap, `_assert_rows_match_manifest`'s
presence checks) violated that exact principle in the same commit that was supposed to be applying
it: both raised new raw exceptions (`ResultRowError`, `KeyError`) the CLI boundary doesn't catch.
A principle doesn't self-verify; a table of concrete claims does. §1f's exception-audit table is
the standing check made checkable — every function touched this round, every exception it can
raise, what it becomes by the boundary. Building that table (not re-stating the principle) is what
surfaced SF1 — a third raw-exception gap in `_read_arm` that neither the user's NF1 nor NF2 named.

**0c. Process note, updated again (Rev. 8):** the table itself was still scoped wrong — "every
function touched in Rev. 7" is a diff, and a diff-scoped completeness check can only ever find
gaps in code that round happened to edit. It cannot structurally find a gap in *unedited* code
from an earlier round, no matter how carefully the table is built within that wrong boundary —
which is exactly why NF3 (Task 9, untouched by Rev. 7) and half of NF4 (also Task 9/2, untouched)
were invisible to a table that was, by its own header, thorough. The user's correction: the scope
must be "every exception reachable from either public entry point toward the CLI" — a boundary,
not a diff, and only a boundary is fully checkable regardless of which round last touched which
function. §1f's table is rebuilt on that boundary now. The general lesson, not just this
instance's fix: **when a self-check's own scope is itself unverified, passing the check proves
nothing about what's outside that scope** — the same failure shape as checking "does this satisfy
the round's list" (§17.0) one level up, now caught at the level of the table's own header rather
than its rows.

**0d. Process note, updated once more (Rev. 9):** disclosing a gap correctly in one place does
not, by itself, stop a false claim about that same gap from shipping somewhere else. §1g's audit
table named `gauntlet_runner` as untraced — accurately — three sections before a code comment on
the arm CLI handler claimed the whole call graph was proven `GateBAbort`-only, with no reference
to the table two sections up contradicting it. The table and the comment were both written by me,
in the same round, and they disagreed with each other. A self-check is not "done" when its own
output is correct; it is done when everything downstream of it that CITES its output is also
consistent with it. This is the same failure shape as NF2 (a false claim cited as justification
for a decision, never checked against the thing it claimed about) recurring at one more remove:
NF2 was a false claim about the CLI's real code; this is a false claim about this document's own
adjacent, correct disclosure.

**0e. Process note, Rev. 10 — not a correction, a calibration:** every prior process note in this
section is about a check that was too narrow or a claim that was false. This one is different:
Rev. 9 correctly proposed a boundary wrap as ONE valid option for the remaining trust-boundary
row, and the user's response wasn't "you missed something," it was "that tool doesn't fit this
callee." The lesson isn't "audit everything" or "wrap everything" — it's that the choice between
them is itself a judgment call with a real criterion (is the callee auditable at reasonable cost
in THIS codebase, right now?), not a default to reach for reflexively in either direction. Rev. 9
picked the right tool for `gauntlet_runner` (genuinely external, genuinely opaque). Rev. 9's own
draft picked the wrong tool for `resolve_coverage_provenance` before the user corrected it. Same
round, two different callees, two different correct answers — the general lesson is to ask the
question freshly each time, not to generalize the previous fix into a rule.

**1. Spec coverage** — the Rev. 1 table still holds; Rev. 2 added the abort taxonomy
(`GateBAbort`, Task 9, mirroring Gate A's §2.6) and full-bundle evidence publication (Task 10).
Rev. 3 added explicit arm-role enforcement (A=`heuristic`, B=`max_damage`, DESIGN §3.2) and a
same-git_sha/schedule/panel/seed_base cross-arm check. Rev. 4 added real per-battle result
capture, server-side seed proof, baseline-drift enforcement, and canonical team-hash binding.
Rev. 5 closed whether `combine` can run end-to-end without crashing (`panel_hash` on every row)
and whether its evidence is verifiable once published (`result_sha256` matching the real bytes).
Rev. 6 closed the one trust edge those revisions still left open: whether an arm's rows and its
own manifest can be proven to belong together at all (`_assert_rows_match_manifest`), and
whether a ledger failure can ever be silently outrun by a publish (`append_entry` before
`os.replace`). Rev. 7 does not add scope; it closes the exception-safety property every prior
revision's "single abort class" framing implicitly assumed but never itself checked end-to-end —
that assumption turned out to be false in two places (NF1, NF2) and one more the audit found on
its own (SF1). Rev. 8 also does not add scope; it corrects the CHECK's own boundary from a diff to
the full reachable-exception surface of both public entry points, closing two more places the
narrower check couldn't see (NF3, NF4) and one more the corrected check found on its own (SF2) —
plus resolving, per the user's explicit design call, the one open question Rev. 7 left standing
(§1g, §19). Rev. 9 also does not add scope; it closes a false claim in a code comment that
contradicted this document's own correct, adjacent disclosure of the exact gap the comment denied
(NF5) — the boundary wrap this fix applies (§1h) needed no audit of the wrapped callee at all,
which is the reason "out of proportion to audit" was never a valid excuse for leaving it open.
Rev. 10 is not a fix at all, in the sense the others were; it is the user's explicit answer to
Rev. 9's own open question, implemented — closing a debt this document has carried since Rev.
1/2 by doing the reconciliation Task 9's docstring always demanded, rather than converting the
question away with a technique that fit a different callee.

**2. Placeholder scan** — `_derive_config_hash`'s reconciliation note is CLOSED, Rev. 10 (§1i):
the function's own docstring no longer says "PROPOSED" or "not independently re-read" — it states
a proven fact, verified by reading both real functions in full. One placeholder remains, unchanged
from Rev. 4: `run_strength_holdout_arm`'s `opp_team_hash` depending on Task 13 for its *content*
(the parameter itself is required and checked). Every other step has complete, runnable,
offline-testable code.

**3. Type consistency** — unchanged from Rev. 4-5, plus: `_assert_rows_match_manifest` (Task 10)
reads the exact same five row fields (`config_hash`, `git_sha`, `schedule_hash`, `seed_base`,
`panel_hash`) that `pairing.py._CONSTANT_FIELDS` requires and Rev. 5 just finished making sure
every row actually carries — this is not a coincidence, it is the reason F3's check was buildable
only after N1 landed, and is now recorded as an explicit ordering dependency rather than
left implicit. **Standing check, going forward:** for any function in this plan that accepts a
manifest, a verdict artifact, or any other "here is who I am" claim from a caller or from disk,
confirm elsewhere in the same task whether that claim is ever independently re-derived and
compared — not just schema-validated. This is the exact question that caught Rev. 4's
`hero_team_hash`/`opp_team_hashes` gap and Rev. 6's manifest-vs-rows gap; it did not get asked of
`_read_arm` specifically until asked directly. **Sharpened, Rev. 7, per explicit request:** state
this standing check as a table (function × exception it can raise × where it's caught × what it
becomes at the boundary), not as restated prose — prose didn't stop this round's own new code from
violating the principle it was written to satisfy (§17.0b). Re-run that table, don't just re-read
it, for any future task that adds or edits a function anywhere in this trust chain. **Sharpened
again, Rev. 8:** re-running the table isn't enough either if its own header still says "this
round's functions" — the table's scope has to be the two public entry points' full reachable
surface, walked fresh, every time, not just the delta since the last table (§17.0c). **Sharpened
again, Rev. 9:** and having a correct table isn't enough either if code elsewhere in the same
document is allowed to restate the table's claims without being checked against it — any comment
that asserts "every exception X is Y" needs to be treated as a claim citing the audit table, and
re-verified against that table's actual current rows, not just written from memory of what the
table probably says (§17.0d).

## 18. Final gate ordering (unchanged from Rev. 1 — still not part of this plan's own execution)

```
1. Review + merge Gate B's code and (once sourced) sealed teams
2. Freeze the final candidate SHA
3. I8-D latency-gate rerun on that candidate           -- must PASS to proceed
4. ONLY IF (3) PASSED: Coverage-gate rerun on the SAME candidate identity
5. ONLY IF (4) PASSED: Independent Strength-holdout run (two fresh server phases, per Task 9/10's
   architecture, then champions-strength-holdout-combine) on the SAME candidate identity
6. ONLY NOW: evidence freeze + report + ROADMAP/PROJECT_INDEX reconciliation together
```

Per DIAG's "Corrected execution order" and DESIGN §8: *"no evidence-freezing PR for an earlier
gate advances the candidate SHA while a later gate on the same candidate is still pending."*
Steps 3-6 are explicitly out of scope for this plan.

## 19. What happens next

**Rev. 24 status.** Tasks 1–12 AND all of Task 13 (steps 1–3) are implemented, tested, and
**committed on `feat/champions-gate-b-task-1-schedule` — nothing is merged to `main`**. Tasks 1–12
and Task 13 steps 1–2 are Codex-PASS; step 3 is code-complete and UNDER REVIEW. This document's
Task 10 and Task 11 sections mirror that committed source rather than a proposal, Task 12 (team
sealing/provenance) shipped with the `.packed`-containment review-fix, and the Gate B static
baseline contract + its real frozen VALUES are committed — `load_strength_holdout_baseline` /
`verify_strength_holdout_baseline` (the additive, closed-schema A1.3 loader/verifier, spec Amendment
A1.3), hardened across the earlier focused review-fix rounds (interpreter-start `PYTHONHASHSEED`
guard; closed `selection_index={1..6}` check).

Task 13's source condition is SATISFIED as of 2026-07-22 (§2a), and step 3 is now done: the six
`.txt`/`.packed` team artifacts exist, are sealed, are `validate-team`-legal, and pass the real
leakage and coverage-disjointness scans; the holdout manifest is the single home of the
public-to-internal ID mapping; the panel YAML carries real content; the hash freeze is complete
(`STRENGTH_HOLDOUT_EXPECTED_PANEL_HASH` / `STRENGTH_HOLDOUT_EXPECTED_MANIFEST_HASH`, the latter
binding the frozen selection order + public→internal mapping); both CLI subcommands source real
manifest/panel data and enforce the frozen identity before battle 1 / before any verdict (no Task-13
blocker remains); and the reference near-duplicate audit against the nine reference teams is recorded
(selection audit §5a).

What remains is the whole-suite verification and Codex review of this branch. **No live Gate B run is
authorized regardless**; that is a separate decision (§17).

Every finding raised across all prior review rounds is fixed with real, verified code, and the one
item Rev. 9 had left as an explicit open question — what to do about `resolve_coverage_provenance`
— was resolved per your own direction (§1i). The two items that were open here (the §2 source-proof
and whether Task 12 runs before or after it) are both **closed**: the source condition is satisfied
(§2a), the six holdout teams are sealed (Task 12 / step 2), and neither CLI subcommand is blocked any
longer — both source real manifest/panel data and enforce the frozen identity + baseline before
battle 1. **What remains is only the whole-suite verification and the Codex review of this branch;**
the live Gate B run is a separate authorization (§17).

No open exception-safety questions remain against either public entry point's own authored code.
One narrow residual is disclosed, not left silent: `load_format_config`'s own malformed-YAML
error path (one function, one specific error case, reached only through
`_derive_config_hash → resolve_coverage_provenance → effective_config_manifest →
config_provenance_for_format`) was not independently confirmed this round — its exact exception
type is unread, though its more common `FileNotFoundError` case is already handled one level
below where it would matter. Closing it means reading `format_config.py` itself; not done here
since it is now a single function's single error path, not an untraced module, and this round's
direction was `resolve_coverage_provenance` specifically.
