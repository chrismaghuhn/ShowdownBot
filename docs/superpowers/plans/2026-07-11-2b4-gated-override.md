# 2b-4 Gated Reranker Override — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.
> Steps use checkbox (`- [ ]`) syntax.

**Goal:** A fail-safe reranker-override agent, PROVEN byte-reproducible (Channel-A double-run),
then a dev-panel paired strength verdict (override vs baseline paired with heuristic vs
baseline). Held-out spend is explicitly deferred + user-gated.

**Architecture:** One new production seam — an override agent that reuses the existing heuristic
trace + the committed reranker model to re-pick among the heuristic's own candidates, fail-safe
to the heuristic. Everything else reuses T4 (identity), T5 (paired stats), T4c (log sha),
2b-2.5a Kaggle path (battle execution). Spec:
`docs/superpowers/specs/2026-07-11-2b4-gated-override-design.md`.

**Tech stack:** existing repo; LightGBM inference (committed model
`models/reranker/2026-07-11-2b25a-attack-lgbm.txt` + manifest). **Hard constraint:** NO local
battles (user CPU busy) — battle runs go on Kaggle, controller-orchestrated. Per task: run only
touched test files; full suite once at closeout (1 strict-xfail known).

---

### Task 1: reranker-override choice core (Sonnet, NO battles)

**Files:** Create `showdown_bot/src/showdown_bot/learning/reranker_override.py`; test
`showdown_bot/tests/test_reranker_override.py`.

- [ ] Study `learning/reranker_shadow.py` (how it scores candidates → `reranker_choice_index`:
  extract_features → vectorize → booster.predict → argmax; the feature-context mode; the
  manifest/schema-hash guards) and `client/gauntlet.py::agent_choose` (how a trace is built +
  how the heuristic's `choose` string is produced via `choose_with_fallback`).
- [ ] `RerankerOverride` (constructed from a booster + manifest, like RerankerShadowRuntime but
  INLINE + deterministic — NO wall-clock timeout branch): method
  `override_choice(*, trace, state, request, heuristic_choose, our_side) -> str` that:
  scores `trace.candidates` with the model; picks argmax with an EXPLICIT stable tie-break
  (lowest candidate_index on equal score); resolves that candidate's JointAction to a legal
  `choose` string (reuse the exact encoder the heuristic uses — find it: `encode_choose`
  /`_label_ja`→choose mapping in decision.py/actions.py); returns it. On ANY failure
  (feature/schema mismatch, predict error, argmax→choose not resolvable, empty candidates,
  schema-hash guard trips) returns `heuristic_choose` unchanged. NEVER raises.
- [ ] Failing tests (stub booster with fixed scores):
  - override returns the choose string of the argmax candidate (score-forced to a non-heuristic
    index) — assert it differs from heuristic_choose and equals the expected candidate encoding.
  - stable tie-break: equal scores → lowest candidate_index chosen, deterministic across calls.
  - fail-safe: booster.predict raises → returns heuristic_choose exactly; schema-hash mismatch →
    heuristic_choose; empty trace.candidates → heuristic_choose.
  - determinism: two calls with identical inputs return identical strings (no RNG, no clock).
- [ ] Run touched tests. Commit `feat(2b-4): fail-safe reranker override choice core`.

### Task 2: wire override into the agent dispatch (Sonnet, NO battles)

**Files:** Modify `client/gauntlet.py` (`agent_choose` + `_Client`); test the dispatch file
(`test_gauntlet_dispatch.py`).

- [ ] New agent value `"heuristic_reranker"`: runs the heuristic path (produces trace + the
  heuristic choose exactly as today), then if a `RerankerOverride` is available on the client,
  returns `override.override_choice(...)`, else the heuristic choose (fail-safe). The client
  builds the override from env (`SHOWDOWN_RERANKER_OVERRIDE` + MODEL_PATH/MANIFEST_PATH, mirror
  the shadow's from_env gating) ONCE per client, reusing the client-owned dex/move_meta from
  the 2b-2.5a decision-deps bundle so features match the shadow's context mode.
- [ ] The heuristic branch and all other agents are byte-unchanged when the override env is off
  (assert: existing dispatch tests stay green untouched).
- [ ] Tests: agent_choose("heuristic_reranker") with a stub override returns the override's
  string; with override unavailable returns the heuristic string; the override is built once
  (not per decision) and reuses the decision dex/move_meta.
- [ ] Run touched tests. Commit `feat(2b-4): heuristic_reranker override agent in dispatch`.

### Task 3: determinism-gate + dev-strength schedules + kernel wiring (Sonnet, NO battles)

**Files:** `config/eval/schedules/` new schedules; extend the Kaggle kernel path
(`tools/kaggle/kernel_payload.py` / a new kernel entry) to run the override agent + a
double-run identity check; tests for schedule integrity + the identity-compare helper.

- [ ] `2b4_determinism_v001.yaml`: a small seeded schedule (e.g. 20-30 battles, override agent
  vs a fixed villain, panel_v001 dev teams) for the double-run identity check. Pin its hash.
- [ ] `2b4_devstrength_v001.yaml`: the paired strength schedule — override-vs-baseline AND
  heuristic-vs-baseline over the dev panel on the SAME seeds (enough games for power; ≥150
  per the T5/PokéAgent discipline — the controller may scale). Pin its hash.
- [ ] A pure `compare_identity(results_a, results_b) -> IdentityReport` helper (reuse T4/T4c:
  winner+turns+normalized_room_log_sha256 per battle must match; list any diffs) with unit
  tests on committed fixtures (fabricate two tiny identical + one-diff result sets).
- [ ] Kernel entry (mirror `datagen_kernel.py`/`repro_validation.py`): run a schedule with
  `SHOWDOWN_RERANKER_OVERRIDE` on, twice, compare identity; and a mode that runs the paired
  strength schedule and emits result JSONLs for local T5 report generation. Verdict line
  `2B4-DETERMINISM: PASS/FAIL` + `2B4-STRENGTH: DONE`. Unit-test the pure pieces; the battle run
  is controller-orchestrated.
- [ ] Run touched tests. Commit `feat(2b-4): determinism + dev-strength schedules and kernel`.

### Task 4 (controller-orchestrated, NOT a subagent): Kaggle runs + verdicts

- [ ] Push branch; run the determinism kernel on Kaggle. Pull → assert `2B4-DETERMINISM: PASS`
  (byte-identical double run). If FAIL: diagnose the nondeterminism source BEFORE any strength
  run — do not proceed.
- [ ] On PASS: run the dev-strength kernel; pull the two result JSONLs; generate the T5 paired
  report (`eval-report` paired mode) → GO / NO-GO / UNDERPOWERED. Commit evidence under
  `data/eval/2b4/` (determinism proof + strength results + paired report) with sha256 pinning.

### Task 5: closeout

- [ ] Full suite once: all green + 1 xfailed (known). Report `reports/2026-07-11-2b4-gated-
  override.md`: determinism PASS evidence, the dev-strength verdict + paired stats, the fail-
  safe contract, and the explicit note that held-out confirmation is deferred + user-gated.
- [ ] `git diff main --stat` scope → controller → merge decision. Held-out spend is a SEPARATE
  future slice requiring explicit user approval.

## Self-review (writing-plans)

- Ordering enforced structurally: Task 4 runs determinism BEFORE strength and hard-stops on
  FAIL — matches the spec's "identity before strength". ✓
- No held-out spend anywhere; dev panel only. ✓
- No local battles: all battle runs are Kaggle kernel entries; unit tests use stub boosters +
  fabricated result fixtures. ✓
- Fail-safe contract makes the override never worse-behaved than the heuristic on errors, and
  the fallback path is RNG-free (determinism-safe). ✓
- Types: `override_choice` returns a choose string (same type as agent_choose); RerankerOverride
  built once per client like RerankerShadowRuntime. ✓
