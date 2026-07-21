# Gate B (Independent Strength Holdout) — Grounding Report

**Status:** PROPOSED — supporting evidence for `docs/projects/champions/plans/2026-07-21-gate-b-independent-strength-holdout.md`
**Author:** Claude, 2026-07-21, in worktree `design/champions-independent-strength-holdout` @ `1b0be1d`
**Purpose:** trace every claim the implementation plan relies on to a file:line or a verified code excerpt, and name explicitly what is *not* pinned anywhere so the plan doesn't silently invent it.

**Verification method:** four parallel research agents each read a disjoint set of documents/code in full inside this worktree and reported back with file:line citations. I then personally re-read the highest-load-bearing sources myself against those reports before writing the plan: the full text of DESIGN §3 (lines 224–342), the full `eval/stats.py` (77 lines), the `_paired_verdict`/`VERDICT_*` block in `eval/report.py` (lines 61-67, 854-877), and `coverage_runner.py` lines 300-370 (the I8-D-verdict cross-check block). Those are marked **[verified]** below. Everything else is marked **[reported]** — read in full by a subagent, not re-read line-by-line by me, but in most cases independently cross-confirmed by a second agent from a different document.

---

## 1. The approved spec already exists — this is not a from-scratch design

**[verified]** `docs/projects/champions/specs/2026-07-20-champions-coverage-strength-holdout-design.md` (439 lines), status line declares it **APPROVED (2026-07-20)**. It defines Gate A (Opponent-Mega Coverage) and Gate B (Independent Strength Holdout) together as one combined spec, one day before this planning session. Gate B is §3 (lines 224-342).

**[verified]** DESIGN §8 (its own sequencing, ~lines 430-433, quoted by the research agent and spot-checked in context around §3.2/§3.5): *"Approve this spec → write the TDD implementation plan (coverage telemetry + validator … independent strength-holdout schedule + verdict; new Champions baseline manifest; repo-wide leakage guard…) → build offline, full suite, review, PR, merge (no live runs) → re-run the I8-D latency gate … → coverage run …; if PASS → strength-holdout run."*

**Consequence:** this plan is not proposing Gate B's design — it is the next authorized step the spec itself names. The plan's job is to turn an approved contract into TDD tasks, not to invent requirements.

**Known tension, not mine to resolve silently:** `docs/ROADMAP.md` (last reconciled 2026-07-21, per two independent agents) has prose reading as if holdout *design* only starts after a fresh coverage PASS. Read against DESIGN §8 above, the better reading is: only the **live holdout run** is gated on a fresh coverage PASS; writing/building the plan is not. I am proceeding on that reading because it is DESIGN's own explicit text, DESIGN postdates and supersedes the ROADMAP prose in question, and it is the only reading under which this planning task is authorized at all. Flagging for Codex review rather than treating it as settled.

---

## 2. Gate A vs. Gate B — verdict vocabularies do not match

**[verified]** DESIGN:8-11 (purpose): both gates must pass before any Champions Strength claim; *"A latency PASS alone does not authorize a Strength run."*

**[verified]** Gate A verdicts: **PASS / FAIL / INCONCLUSIVE** (DESIGN §2.6, lines 186-220 — full dedicated section).
**[verified]** Gate B verdicts: **GO / NO-GO / UNDERPOWERED** (DESIGN §3.2/§3, lines 226-227, 264-269).

**Gap (load-bearing for the plan's Task on abort/verdict rules):** Gate A has a full dedicated §2.6 enumerating PASS/FAIL/INCONCLUSIVE and a separate abort/void list (dirty tree, seed-log mismatch, provenance/hash mismatch, server/battle infra failure, parser crash, zero battles created ⇒ void, not a verdict). **Gate B has no equivalent section.** Its verdict rule is stated compactly in §3.2 only, and its only named abort trigger is a "missing pair" in the McNemar analysis (§3.2, also DESIGN:274-276). "SAFETY-FAIL" is used as a precedence label in §3.2 but never defined in DESIGN — it turns out to already be defined in code (`eval/report.py`, see §5 below), not in this spec.

**Plan decision (mine, stated not hidden):** the plan's abort/void task explicitly ports Gate A's §2.6 abort taxonomy to Gate B by name (same six trigger categories), since nothing in Gate B's text suggests a narrower or different list was intended, and the two gates share every other provenance/atomicity/dirty-tree rule verbatim (DESIGN §4, "shared rules"). Codex should confirm or correct this inference — it is filling a real spec gap, not reading an explicit instruction.

---

## 3. The 180 paired battle-keys — exact decomposition

**[verified]** DESIGN:260-263: *"Schedule = the 6 fresh holdout teams (§3.1) as the opponent-team axis × 2 opponent policies × 15 seeds = 180 paired battle-keys per configuration. A and B play the identical 180 battle-keys — the same `(holdout_team, opponent_policy, seed)` triples and matchups."*

6 × 2 × 15 = 180. Confirmed by direct arithmetic, not just quoted.

**[verified]** DESIGN:256-259 — the two orthogonal axes, easy to conflate, kept separate here:
- **Hero** = the bot's own **team**, byte-identical in both arms. **Candidate A** = current Champions heuristic agent; **Baseline B** = hero-agent `max_damage` — the two things McNemar actually compares, both piloting the same fixed hero team.
- **Opponent policies** `{heuristic, max_damage}` — a *different* axis, crossed with the 6 holdout teams to build the 180-key schedule. Not what's being compared; part of what generates the paired matchup set.

**Not pinned anywhere in DESIGN:** the exact hero **team file** for Gate B. Gate A's coverage plan names `showdown_bot/teams/fixed_champions_v0.txt` as *its* hero explicitly (COVPLAN:322-324, reported); DESIGN never re-pins a filename for Gate B, only "the identical (fixed, standard Champions) hero team." The plan proposes reusing `fixed_champions_v0.txt` (it is the one standing "Champions hero" team already used by both I8-D and Coverage) and marks this PROPOSED, following DESIGN's own convention (§0, "where a number or identity is not pinned by the repo it is marked PROPOSED") rather than presenting it as already-decided.

---

## 4. McNemar evaluation — reused unchanged, not reimplemented

**[verified directly against source]** `showdown_bot/src/showdown_bot/eval/stats.py` (full file read):
```python
N_DISCORDANT_MATH_FLOOR = 6    # below: p<0.05 mathematically unreachable
N_DISCORDANT_CLAIM_MIN = 10    # below: no claim in any verdict line (UNDERPOWERED)
LOSING_CELL_WILSON_UPPER = 0.5
TIE_FLAG_RATE = 0.02
```
plus `wilson_interval()`, `exact_binom_two_sided_p()` (exact two-sided binomial via `math.comb`), and the frozen `McnemarCounts` dataclass (`n11/n00/n10/n01`, with `.n_discordant`, `.total`, `.delta` properties) built by `mcnemar_counts(pairs)`.

**[verified directly against source]** `showdown_bot/src/showdown_bot/eval/report.py`:
```python
VERDICT_SAFETY_FAIL = "SAFETY-FAIL"
VERDICT_UNDERPOWERED = "UNDERPOWERED"
VERDICT_GO = "GO"
VERDICT_NOGO = "NO-GO"

def _paired_verdict(counts, exact_p, cell_flips, strength_delta, safety_pass):
    if not safety_pass:
        return VERDICT_SAFETY_FAIL, []
    if counts.n_discordant < N_DISCORDANT_CLAIM_MIN:
        return VERDICT_UNDERPOWERED, []
    reasons: list = []
    if counts.delta <= 0:
        ...  # (not fully re-quoted here; positive-evidence-only NO-GO reasons)
    if reasons:
        return VERDICT_NOGO, reasons
    return VERDICT_GO, []
```
This is the **entire** decision-rule contract DESIGN:264-269 refers to as *"the existing positive McNemar contract, unchanged."* **Gate B's implementation task is to call this function with Gate-B pairs, not to rewrite any part of it.**

**[verified]** Baseline manifest: DESIGN:270-273 — a **new** Champions-specific baseline manifest must be frozen; `config/eval/baselines/heuristic-v1.json` is explicitly **not reused**. `eval/baseline.py`'s `BaselineDriftError` re-hash guard applies to it unchanged. No filename is pinned in DESIGN for this new manifest — open, and named as a PROPOSED path in the plan.

**[verified]** Pairing integrity: DESIGN:274-276 — A and B share `schedule_hash`/`seed_base`/`panel_hash`/`format_id`, differ only in `config_hash`; a missing pair aborts (technical abort, not a verdict), via `eval/pairing.py` (not independently re-read by me; reported only).

---

## 5. Candidate Identity — already built, not something to invent

**[verified against source]** `showdown_bot/src/showdown_bot/learning/provenance.py:35-41`:
```python
def make_candidate_identity(*, hero_agent: str, git_sha: str, config_hash: str) -> str:
    return _sha16(json.dumps(
        {"hero_agent": hero_agent, "git_sha": git_sha, "config_hash": config_hash},
        sort_keys=True, separators=(",", ":")))
```
(`_sha16` = first 16 hex chars of a sha1 hexdigest.) Already wired into both `i8d_runner.py` and `coverage_runner.py`.

**[verified against source]** The verification pattern Gate B must extend to **two** upstream gates (currently Coverage checks only I8-D) — `coverage_runner.py:300-370`, confirmed directly: it does **not** trust the opaque `candidate_identity` token alone. It re-derives its own `git_sha`/`config_hash`/`hero_agent`/`calc_backend` and checks each field individually against the upstream verdict file, plus re-derives the upstream's canonical `schedule_hash` from the pinned panel rather than trusting the artifact's own claim:
```python
if i8d_verdict_data["git_sha"] != git_sha: raise CoverageRunError(...)
if i8d_verdict_data["config_hash"] != config_hash: raise CoverageRunError(...)
if i8d_verdict_data["hero_agent"] != hero_agent: raise CoverageRunError(...)
i8d_identity = i8d_verdict_data["candidate_identity"]
if i8d_identity != candidate_identity: raise CoverageRunError(...)
i8d_calc_backend = i8d_verdict_data["calc_backend"]
if i8d_calc_backend != calc_backend: raise CoverageRunError(...)
i8d_canonical = build_i8d_canonical_schedule(teams_root=teams_root)
if i8d_verdict_data["schedule_hash"] != i8d_canonical.schedule_hash: raise CoverageRunError(...)
```
The code comment explains why (review round 6, P1): *"`candidate_identity` is a PUBLIC, locally-computable hash … a hand-crafted artifact can carry the CORRECT `candidate_identity` alongside a COMPLETELY UNRELATED `git_sha`/`config_hash`/`hero_agent`."* This is the exact forgery class Gate B's own dual check (against **both** the I8-D verdict and the Coverage verdict) must close, since REMPLAN explicitly deferred it: *"No Strength-holdout runner exists yet … so its symmetric identity hardening is deferred until that runner exists — not built speculatively here"* (**[reported]**, REMPLAN:48-50). Building it now is this plan's job, confirmed by that deferral note, not an invention.

**[verified]** DESIGN §5 (candidate-identity contract, lines 367-388, spot-read alongside §3): coverage PASS licenses a strength run *only* for the same candidate identity; Champions Strength stays NO-GO until, for **one and the same** candidate identity, latency PASS **and** coverage PASS **and** holdout GO all hold.

**Naming collision flagged by two independent agents, worth stating once clearly:** `showdown_bot/src/showdown_bot/battle/candidate_identity.py` is an unrelated, older module (per-decision structural identity for `DecisionTrace`, from the I7 Mega design). Do not confuse it with `learning/provenance.py::make_candidate_identity`, which is the cross-gate build-identity function Gate B actually needs.

---

## 6. Evidence publication — atomic pattern to reuse, one anti-pattern to avoid

**[reported, function shown]** `_write_json_atomic()` (`i8d_runner.py:106-112`): temp file, sorted-key JSON, `os.replace`. Reused (imported) by `coverage_runner.py`, not reimplemented.

**[reported]** Whole-run atomic publish: both runners build under `f"{out_dir}.staging"` and call `os.replace(staging_dir, out_dir)` once at the very end (`i8d_runner.py:402`, `coverage_runner.py:625`).

**Anti-pattern to avoid, named explicitly so the plan doesn't accidentally copy it:** `run_manifest.py::write_run_manifest()` does a plain non-atomic `open(path, "w")`, and `result_jsonl.py::BattleResultWriter.write()` is append-only. Fine for logs/manifests-of-record; **not** the pattern for a gate verdict file. Gate B's runner must follow the i8d_runner/coverage_runner staging+replace pattern, not these.

---

## 7. Windows/Kaggle strata — real gap, nothing to reuse

**[reported, independently significant]** Repo-wide case-insensitive search for `stratum|strata` in code: **zero hits**. The "never pooled" rule (DESIGN:335-339, DESIGN:358, ROADMAP.md:36-38, PROJECT_INDEX.md:46-47) is real and repeatedly stated, but today it is enforced **only by operational discipline** — separate output directories, separate `seed_base`/`config_hash` per run — never by an automated check. `collect_environment()` (`run_manifest.py:95-107`) records platform info but is **deliberately excluded** from `config_hash` ("environment differences must not fork config lineage") and is never compared or gated anywhere.

**Consequence for the plan:** this is not a "reuse existing code" task like the others — it is new code with no prior art to mirror. The plan's strata-guard task says so explicitly rather than pretending a pattern exists.

---

## 8. Frozen coverage team hashes — exact reference set for the disjointness check

**[reported, file contents shown directly]** `config/eval/coverage/champions_coverage_v0_manifest.json`, `team_content_hashes`:
```json
{
  "fixed_champions_v0": "1d3a4cf5a4042532",
  "cov_foe_slot0": "5bd94d4b1558ba28",
  "cov_foe_slot1": "8b68400f463fe581",
  "cov_foe_both": "232261b652d13605",
  "cov_foe_tie": "b7077a81e579aa72"
}
```
Hash recipe (`coverage_schedule.py:80-82`, reported): `sha1(json.dumps(data, sort_keys=True, separators=(",",":"))).hexdigest()[:16]` — i.e. the exact same recipe family as `make_candidate_identity`, applied to team content instead of identity fields.

Constant pattern to mirror (`coverage_schedule.py:31-36`, reported):
```python
COVERAGE_PANEL_PATH = "config/eval/panels/panel_champions_coverage_v0.yaml"
COVERAGE_MANIFEST_PATH = "config/eval/coverage/champions_coverage_v0_manifest.json"
COVERAGE_EXPECTED_PANEL_HASH = "6f4c98537a320bed"
COVERAGE_EXPECTED_MANIFEST_HASH = "6278dc41907cf63c"
```
Gate B needs its own `STRENGTH_HOLDOUT_PANEL_PATH` / `STRENGTH_HOLDOUT_MANIFEST_PATH` / `STRENGTH_HOLDOUT_EXPECTED_*_HASH` constants, same module-constant-frozen-hash-reverified-at-runtime pattern, in a new sibling module.

**DESIGN's disjointness requirement is explicit** (§3.3, verified): *"must additionally be disjoint from the engineered coverage panel (§2.4) by hash."* — this is a check against exactly the 5 hashes above.

---

## 9. Team pools and contamination — why the firewall must cover nine teams, not four

**[reported, independently corroborated by two agents reading different documents]** `showdown_bot/teams/`:
- `panel_champions_v0/`: `goodstuff`, `tailwind_offense`, `trick_room` (dev) + `rain_offense`, `disruption` (nominally "held-out")
- `panel_champions_coverage_v0/`: `cov_foe_slot0`, `cov_foe_slot1` (dev) + `cov_foe_both`, `cov_foe_tie` (heldout, coverage-internal)

**[verified]** DESIGN §3.1 (contamination finding, lines 230-244, read in full): *"No untouched team set exists anywhere in the repo."* `rain_offense` is *"the most-contaminated team: the foe-Mega exposure vehicle across the entire Champions I-series (dedicated parser validation, I5, I6, I7a, I7b)."* `disruption` was used in the I5 smoke. The three "dev" teams are the I8-D live-gate matchups. All nine committed Champions M-A teams across both pools are therefore excluded, not just the four nominally "held-out"-labeled ones — the plan's firewall task names all nine explicitly rather than only the ones labeled "held-out," since the label turned out not to track actual contamination.

**[reported]** `panel_champions_coverage_v0`'s two dev teams are themselves edited copies of `panel_champions_v0` teams (commit `50fd16e`: *"validated rain_offense"* / *"validated goodstuff"* byte-copies with edited movesets) — reinforcing that the coverage pool cannot double as an independent source either.

**[reported]** Existing sourcing methodology precedent: `showdown_bot/teams/panel_champions_v0/PROVENANCE.md` (commit `7660d44`, 2026-07-14) cites a real, named tournament per team (Limitless TCG, "Crown Fight Bo3 #66"), player URL, `source_date`, `validate-team` exit code, and a fidelity label (`tournament-exact` / `composite — NOT tournament-exact` / `synthetic — NOT tournament-exact`). This is a real, reusable **documentation template** for the new six teams' provenance file. It is **not** a precedent for blindness — no prior pool in this repo's history was ever curated blind to bot results, because no prior pool needed to be (see §10).

---

## 10. Team sourcing — the fail-closed stop

**[reported, cross-confirmed independently by two agents from different angles — a docs-tree grep and a ledger/history read]**

- **No already-vetted, not-yet-used, blind-to-bot-results team source exists anywhere in this repository.**
- **VGC-Bench** ("72 holdout teams") is the only externally-vetted pool ever discussed in this repo. It is explicitly excluded for Gate B v0 by the approved spec itself — DESIGN:246-250, D-1a: *"VGC-Bench is out of scope for v0 … no existing repo team and no VGC-Bench import for Gate v0."* Independently, `docs/PROJECT_INDEX.md` (§5, reported) lists it as **PROPOSED, execution not approved**, a read-only compat study, with no team files actually in the repo.
- **HolidayOugi** replay data exists as a *lower-trust*, also **unapproved-for-execution** track (PROPOSED status, PROJECT_INDEX §5) — and is replay data, not a standalone curated team-list source in the first place.
- **Blindness itself is a brand-new discipline.** Grepped across all champions docs and the full git history of every team-pool commit: the word "blind" in a sourcing sense appears **only** in the 2026-07-20 DESIGN spec. No commit message for any existing team pool documents a bot-results-blind process, because no earlier pool was ever required to be independent in that sense.

**This confirms the plan cannot resolve team sourcing itself.** Doing so would require either fabricating team content (explicitly forbidden) or unilaterally picking a real external data source and asserting its blindness without the human decision the spec's own D-1a ruling implies is still open (*a* source/curation process must be chosen — DESIGN never names which one). Per your instructions, this is documented as an explicit open decision (D-1b) with source options in the plan itself, and Task "Source, seal, and register the six holdout teams" is written but marked BLOCKED pending that decision — no team names, archetypes, or content are invented anywhere in this plan or its code examples.

---

## 11. Confirmed merge/status timeline (cross-checked against git log + ROADMAP.md, not just doc self-labels)

**[reported, git log + `gh pr view` shown directly]**
- Gate A implementation: merged PR #37 @ `10f9adf`.
- First live coverage run (broken `both_foe_slots` team): ran on `cbaa4b9` → FAIL; evidence merged PR #40 @ `cb05fca`.
- `both_foe_slots` diagnosis + remediation plan: approved `a55ab4d` / `78a2274`.
- Remediation + candidate-identity hardening: **merged PR #42 @ `f2bb818`** (confirmed via `gh pr view 42`: title "fix(champions): both_foe_slots remediation + I8-D verdict hardening", state MERGED), full suite reported 2971 passed / 18 pre-existing-unrelated failed / 1 skipped / 1 xfailed, zero new failures — **reported only, not independently re-run by me**.
- ROADMAP/PROJECT_INDEX reconciliation: merged PR #43 @ `b121548`.
- DESIGN spec itself: merged to `main` at `50601d7`.
- **Not yet run, per ROADMAP.md (reported, lines ~134-142):** I8-D latency rerun on the post-remediation candidate; coverage-gate rerun (only if I8-D PASSes); the holdout's live run (only after a fresh coverage PASS). **Champions Strength remains NO-GO.**

None of these historical runs or their pass/fail outcomes are re-verified by me in this session — I did not execute anything. They are cited from ROADMAP.md/git history as reported context for why this plan exists and what it is blocked behind.

---

## 12. Explicit non-goals carried into the plan

**[verified]** DESIGN §6 (lines 392-398, read directly): *"No code, test code, server, battle, run, evidence, benchmark, push, PR, or merge. No reuse of any dev/parser/I5/I6/I7 team as the strength holdout. No change to the I8-D latency gate, its budget, or its frozen evidence. No pooling of coverage and strength data, or of Windows and Kaggle data."*

This grounding report and the implementation plan comply with the first sentence by construction: nothing here is executable code written to `showdown_bot/src`, no server/battle/benchmark was run, and nothing is committed.
