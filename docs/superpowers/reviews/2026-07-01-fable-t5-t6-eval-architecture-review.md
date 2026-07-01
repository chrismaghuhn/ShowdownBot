> Independent architecture review by Fable 5. Non-binding review artifact; accepted findings are promoted into implementation plans separately.

T5/T6 Architecture Review & Design
Verdict up front: The row schema after the T3e amendments is almost sufficient — but T5 as scoped will be structurally underpowered for the claim 2b-4 actually needs, and that's the central design constraint, not a footnote. With ~50 games against mostly-weak opponents, McNemar will usually return "no significant difference," and the single most dangerous failure mode of this whole harness is reading that as safety evidence. T5/T6 must therefore be designed around one asymmetric rule: the override needs positive evidence of improvement; absence of evidence never unblocks anything. Everything below is shaped by that.

1. Result schema readiness
The listed fields cover Wilson and the safety gates. Missing or under-specified for T5/T6:

Missing	Why T5/T6 breaks without it
seed_base (per row)	The pairing precondition is "same schedule_hash AND same seed_base." Recoverable from seed, but the pairing validator should check it explicitly per row, not re-derive.
run_id + run manifest	One JSONL = one run today, but T5 consumes two files. A run_id (hash of seed_base + schedule_hash + config_hash + start time) plus a small run-level manifest (Showdown commit, server patch hash, PYTHONHASHSEED, timestamp, CLI invocation) makes each input self-describing. Server/patch provenance was already flagged last review (P5b) — this is where it lands.
panel_split: dev | heldout (per row)	T6's leakage checks must not re-derive split membership by joining team hashes against a panel file that may have changed since the run. Stamp it at write time.
end_reason: normal | timeout | forfeit | crash	A timeout-forced loss counted as a real loss silently corrupts win rates. T5 must be able to distinguish "lost the game" from "the game didn't complete."
Real config_hash semantics	Currently hash(config_id, format_id) — two behaviorally different bots can share it. Before T5, config_hash must cover the effective config manifest: agent name, model + manifest hashes when the reranker is on, priors/spreads-book content hashes, relevant env flags. This is a hard precondition (see §10).
battle_id semantics documented	Keep it as the pairing key; row identity = (battle_id, config_hash). See §2.
opp_policy, hero_team_path, opp_team_path already exist from T2 — keep them; the cell definition (§4) depends on opp_policy + opp_team_hash.

2. Pairing model
Pair key = (schedule_hash, seed_base, seed_index). Two runs are pairable iff schedule_hash, seed_base, panel_hash, and format_id all match and config_hash differs. The validator additionally checks seed_A == seed_B per pair (must hold by construction; mismatch = corrupted data, fail-fast).

battle_id is the pairing key, not a row ID. Row uniqueness within an analysis = (battle_id, config_hash); a duplicate is a fail-fast error, never a silent dedupe.
Fail if config_hash_A == config_hash_B. This is not pedantry — comparing a config to itself yields n_discordant ≈ 0, which reads as "perfectly safe." See §10.
Ties: define hero_win = (winner == "hero"); tie counts as not-a-win for both Wilson and McNemar. Report tie counts separately; if ties exceed ~2% of games, flag it (something degenerate is happening).
Missing pairs: refuse, don't drop. Each input run already carries a row-count == schedule-rows gate, so a missing pair means one run is invalid. Dropping incomplete pairs silently introduces selection bias correlated with exactly the failures you care about (crashes in losing positions). No partial paired analysis, ever.
Crashes/invalid/timeouts: safety gates run before statistics. Any crash, invalid choice, or non-normal end_reason in either run → the whole paired analysis is non-evidentiary (report still generates, with a SAFETY FAIL banner and no GO verdict). Since the standing target is 0/0, this is enforceable and simpler than any per-battle exclusion rule — and per-battle exclusion is statistically wrong anyway.
3. McNemar
Per pair: a = hero_win(config_A), b = hero_win(config_B).

n_11 = both won · n_00 = both lost (ties count here) · n_10 = A won, B lost · n_01 = B won, A lost · n_discordant = n_10 + n_01
delta_winrate = (n_10 − n_01) / N where N = total pairs (identical to winrate_A − winrate_B; report both forms).
Use the exact binomial test (two-sided, n_10 successes out of n_discordant, p = 0.5). At T4 scale the chi-square approximation is flatly invalid — this is the one place where "no math library choice needed" has an exception worth stating.
Power floor: the exact test cannot reach p < 0.05 until n_discordant ≥ 6 (6/6 one-sided split gives p ≈ 0.031). So: n_discordant < 6 → mathematically no claim possible; 6–9 → "weak evidence at best"; ≥ 10 → minimum for any claim in a verdict line. These thresholds go in the report generator as code, not prose.
Underpowered phrasing (mandatory, verbatim-class): "UNDERPOWERED: only k discordant pairs. No conclusion is possible in either direction. This is not evidence of equivalence and must not be cited to unblock 2b-4." The p-value may appear in the detail table but never in the verdict line when underpowered.
Bonus that pure statistics can't give you: when n_discordant ≤ ~12, the report must list every discordant battle (battle_id, cell, turns, end_hp_diff). At this scale a human reviewing 8 discordant games is worth more than any p-value — and it catches "wins via opponent degeneracy" that the numbers hide.
4. Wilson CI
Cell = (opp_policy, opp_team_hash). Hero team is fixed; if it ever varies, it joins the cell key.
Per-cell Wilson 95% CI on hero win proportion (tie = loss). With ~3–6 games per cell the intervals will be enormous — report them anyway; wide honest intervals are the point.
Aggregates: per-policy pooled Wilson, plus overall pooled. Both the pooled estimate and the unweighted mean of cell win rates must be shown — divergence between them signals imbalanced cells doing the hiding.
Anti-hiding rules (mandatory): (a) the verdict must include a "worst cell" line: the cell with the lowest win rate, named, with its CI; (b) any cell whose Wilson upper bound < 0.5 is a "losing cell" and must be listed in the verdict, not just the table; (c) no grand headline number may appear without the per-policy breakdown adjacent — improvement concentrated against greedy_protect/scripted_vgc while flat against heuristic/max_damage is not improvement (§9).
5. Safety gates (checked first; any FAIL → no strength claims)
Gate	Condition	Action
Invalid choices	total > 0	FAIL
Crashes	total > 0	FAIL
Timeouts / end_reason ≠ normal	any	FAIL
p95 decision latency	> pinned budget (pin one number now, e.g. 1000 ms — current baseline is ~200 ms)	FAIL for gate runs, WARN for dev smokes
Dirty git tree	any row flagged	FAIL for gate runs, WARN for dev smokes
panel_hash	null, or ≠ the panel file the report was invoked with	FAIL
Seed-log	report generator re-runs verify_schedule_alignment itself — it must consume the seed log, never trust rows	FAIL on mismatch
Non-reproducible policy	any random row in a paired/gate run	FAIL
Row integrity	count ≠ schedule rows; duplicate (battle_id, config_hash); paired seed mismatch; non-constant config_hash/schedule_hash/panel_hash within a run	FAIL
Split integrity	any held-out team_hash in a dev-labeled run (and vice versa)	FAIL
6. Held-out discipline (T6)
You cannot technically stop a solo dev with root on his own machine from touching held-out teams. The achievable goal is making every access visible, auditable, and budgeted — say this honestly in the T6 spec.

Yes, a ledger: append-only, committed, e.g. config/eval/heldout_ledger.jsonl. generate_heldout_schedule appends automatically (it already has the confirm_heldout choke point): {date, purpose, panel_hash, schedule_hash, config_hash, git_sha}; the gate runner appends the result summary hash after the run.
Access budget: one held-out gate attempt per candidate config_hash lineage. A second attempt for the "same" candidate requires either a panel version bump (new held-out teams) or an explicit justification entry. This is the defense against the actual overfitting mechanism: iterating a candidate until held-out happens to pass.
Runner refusals: the T6 gate runner refuses if (a) the ledger has a prior entry for this config_hash without a justification, (b) any held-out team_hash appears in any committed dev schedule, (c) the ledger file's history shows edits to prior lines (append-only enforced by a test that replays git history of the file).
Report banner on every held-out report: "HELD-OUT RUN — these numbers must never inform tuning decisions."
7. Baseline freezing
Commit a baseline manifest, e.g. config/eval/baselines/heuristic-v1.json: clean git_sha, config_id, full config_hash (per §1's strengthened semantics), panel version + panel_hash, dev + held-out schedule_hashes, hero_team_hash, all opp team_hashes, Showdown commit + server patch hash, seed_base, PYTHONHASHSEED, and the sha256 of the baseline's reference result JSONL.

Immutable after T6: the manifest file (a change = a new versioned file, never an edit), the referenced team file contents, the panel version, the server patch, and the reference JSONL. Verified, not assumed: before any comparison run, the gate runner re-checks every hash in the manifest against the working tree ("baseline drift" → refuse), and performs a baseline reproduction spot-check — re-run a small subset (e.g. 6 battles) of the baseline schedule and require the winner sequence to match the reference rows. A pinned baseline that can't be re-reproduced is a label, not a baseline.

8. Report artifact
One generator, two outputs from identical data: report.md (human) + report.json (machine, schema_versioned, for future gate automation). The generator must be deterministic: same input JSONLs → byte-identical outputs, so reports can be committed and diffed.

Mandatory sections, in order:

Verdict line (first line): GO / NO-GO / UNDERPOWERED / SAFETY-FAIL, plus worst-cell callout.
Provenance block: every hash — schedule, panel, both config_hashes, git shas + dirty flags, team hashes, server patch, seed_base, PYTHONHASHSEED, run_ids, row counts, input JSONL sha256s.
Safety gates table: each gate from §5 with PASS/FAIL and the measured value.
Per-cell table: n, W/L/T, win rate, Wilson CI, per cell.
Aggregates: per-policy pooled + overall pooled + unweighted cell mean, losing-cell list.
Paired section (two-config reports): n_11/n_00/n_10/n_01, delta, exact p, underpowered banner where applicable, discordant-battle list.
Mandatory warnings: ceiling-effect caveat (weak panel), scripted_vgc = coverage-not-strength, paired-seeds-diverge-after-first-differing-choice caveat, not-evidence-of-equivalence when underpowered, DEV vs HELD-OUT banner.
Reproduction block: exact CLI + env to regenerate both runs and the report.
9. 2b-4 unblock criteria
GO requires all of:

T4 green: all safety gates pass, cross-server reproduction spot-check passes.
T5 merged with fixture tests (known count tables → known p-values; golden byte-identical reports).
T6 in place: baseline manifest committed + reproduction-verified; ledger active; a baseline held-out run recorded.
For the candidate config itself: paired McNemar vs the pinned baseline on dev with n_discordant ≥ 10, delta > 0, exact p < 0.05; no safety-gate regression; then a single budgeted held-out run with no directional reversal (point delta ≥ 0, or clearly within noise).
Block even when the aggregate looks fine:

Any cell flips from winning to losing vs baseline (archetype regression).
Improvement concentrated against greedy_protect/scripted_vgc with flat-or-negative delta on heuristic/max_damage cells — the only cells that measure strength.
Dev positive but held-out negative (overfitting signature).
Manual review of discordant battles shows wins via opponent degeneracy (e.g. Protect-stall exploitation).
Any latency/invalid/crash regression, dirty tree, or hash mismatch anywhere in the chain.
10. Adversarial: the smallest mistake that produces misleading confidence
Three candidates, ranked:

The winner — "no significant difference" read as safety. Weak opponents + 50 games ⇒ n_discordant will naturally be tiny ⇒ p will almost always be large ⇒ a careless reader concludes "no regression detected, ship the override." The harness would then be systematically biased toward waving through worse models — the exact opposite of its purpose — while looking rigorous. Every countermeasure in §3/§9 (power floor, mandatory underpowered phrasing, positive-evidence-only unblocking) exists because of this one failure mode.
Config self-comparison. With config_hash currently hashing only (config_id, format_id), an env-flag mistake can pair a config against itself: n_discordant = 0, which reads as "perfectly stable." Hence the config_hash_A ≠ config_hash_B fail-fast and the strengthened config_hash semantics — note that 0 discordant pairs is always ambiguous between "behaviorally identical" and "mislabeled duplicate" and the report should say so.
Unpaired eyeballing. Computing separate Wilson CIs for A and B and comparing overlap discards the pairing and roughly doubles the effective noise. The report must never present two-config results as side-by-side independent CIs without the paired section adjacent.
Mandatory preconditions before T5 implementation
T3e merged with its four amendments (P0 counters, P1 panel v002, P2 activation evidence, P4 provenance) — T5 consumes those exact fields.
Schema additions from §1 landed in T2's writer: seed_base, run_id + run manifest, panel_split, end_reason; battle_id semantics documented.
config_hash redefined over the effective config manifest, with a test that flipping a behavior-affecting env flag changes it.
Latency budget pinned as a number in config, not prose.
The three verdict thresholds (n_discordant 6 / 10, losing-cell rule) written into the T5 spec as constants with the rationale, so the implementer codes gates rather than re-deriving statistics.
Decision recorded that the report generator independently re-verifies seed-log alignment and panel/team hashes (it audits its inputs; it does not trust rows).
One closing calibration: T5's most valuable output at this scale is not the p-value — it's the provenance audit plus the discordant-battle list a human can actually read. Design the report so those two things are impossible to skip, and the statistics can mature later as N grows.

I've also updated my project memory with the key T5/T6 design decisions (pair key, exact-test power floor, ledger + budget, baseline manifest with reproduction check) so the implementer session can pick them up.


Gespeichert eine Erinnerung
Here is the complete T5/T6 architecture design (memory has been updated with the key decisions for the implementer session).

T5/T6 Architecture Design
Verdict: The row schema after the T3e amendments is almost sufficient — but T5 as scoped will be structurally underpowered for the claim 2b-4 actually needs, and that is the central design constraint, not a footnote. With ~50 games against mostly-weak opponents, McNemar will usually return "no significant difference," and the single most dangerous failure mode of this harness is reading that as safety evidence. T5/T6 must be designed around one asymmetric rule: the override needs positive evidence of improvement; absence of evidence never unblocks anything.

1. Result schema readiness — what's still missing
Missing	Why T5/T6 breaks without it
seed_base per row	Pairing precondition is "same schedule_hash AND same seed_base" — the validator should check it explicitly, not re-derive from seed.
run_id + run manifest	T5 consumes two JSONL files. Each needs a run_id plus a run-level manifest: Showdown commit, server patch hash, PYTHONHASHSEED, timestamp, CLI invocation. This is where the unrecorded-server-provenance gap (P5b from my last review) gets closed.
panel_split: dev | heldout per row	T6 leakage checks must not re-derive split membership against a panel file that may have changed since the run. Stamp at write time.
end_reason: normal | timeout | forfeit | crash	A timeout-forced loss counted as a real loss silently corrupts win rates.
Real config_hash semantics	Currently hash(config_id, format_id). Must cover the effective config manifest: agent, model + manifest hashes when reranker is on, priors/spreads content hashes, behavior-affecting env flags. Hard precondition.
battle_id semantics documented	It is the pairing key; row identity = (battle_id, config_hash).
opp_policy / team paths already exist from T2 — keep them; the cell definition depends on them.

2. Pairing model
Pair key = (schedule_hash, seed_base, seed_index). Runs pairable iff schedule_hash, seed_base, panel_hash, format_id match and config_hash differs. Cross-check seed_A == seed_B per pair; mismatch = fail-fast.
battle_id = pairing key, not row ID. Row uniqueness = (battle_id, config_hash); duplicates fail-fast, never silent dedupe.
Fail if config_hash_A == config_hash_B — self-comparison yields n_discordant ≈ 0, which reads as "perfectly safe" (see §10).
Ties: hero_win = (winner == "hero"); tie = not-a-win for both Wilson and McNemar. Report tie counts; flag if > ~2%.
Missing pairs: refuse the whole paired analysis, never drop pairs. Dropping introduces selection bias correlated with exactly the failures that matter (crashes in losing positions). Each run's own row-count gate makes missing pairs a hard error anyway.
Crashes/invalid/timeouts: safety gates run before statistics. Any crash, invalid choice, or non-normal end_reason in either run → the paired analysis is non-evidentiary (report generates with a SAFETY FAIL banner, no GO verdict). Per-battle exclusion rules are statistically wrong and unnecessary given the 0/0 target.
3. McNemar
n_11 both won · n_00 both lost (ties here) · n_10 A won/B lost · n_01 B won/A lost · n_discordant = n_10 + n_01.
delta_winrate = (n_10 − n_01) / N, N = total pairs (= winrate_A − winrate_B; report both forms).
Exact binomial test (two-sided, n_10 out of n_discordant, p = 0.5). At this scale the chi-square approximation is invalid — the one justified exception to "no library talk."
Power floor: exact test cannot reach p < 0.05 until n_discordant ≥ 6 (6/6 split → p ≈ 0.031). Thresholds as code, not prose: < 6 → no claim mathematically possible; 6–9 → "weak evidence at best"; ≥ 10 → minimum for any verdict claim.
Mandatory underpowered phrasing: "UNDERPOWERED: only k discordant pairs. No conclusion is possible in either direction. This is not evidence of equivalence and must not be cited to unblock 2b-4." No p-value in the verdict line when underpowered.
Discordant-battle list: when n_discordant ≤ ~12, list every discordant battle (battle_id, cell, turns, end_hp_diff). At this scale a human reviewing 8 games is worth more than any p-value, and it catches degeneracy wins the numbers hide.
4. Wilson CI
Cell = (opp_policy, opp_team_hash). Per-cell Wilson 95% CI on hero win proportion (tie = loss). Intervals will be huge at n = 3–6 per cell — report them anyway; wide honest intervals are the point.
Aggregates: per-policy pooled + overall pooled + unweighted mean of cell win rates (divergence between pooled and unweighted signals imbalanced cells doing the hiding).
Anti-hiding rules: verdict must name the worst cell with its CI; any cell with Wilson upper bound < 0.5 is a "losing cell" and must appear in the verdict; no headline number without the per-policy breakdown adjacent — improvement concentrated on greedy_protect/scripted_vgc while flat on heuristic/max_damage is not improvement.
5. Safety gates (checked first; any FAIL → no strength claims)
Gate	Condition	Action
Invalid choices	> 0	FAIL
Crashes	> 0	FAIL
end_reason ≠ normal	any	FAIL
p95 latency	> pinned budget (pin a number now, e.g. 1000 ms; baseline ~200 ms)	FAIL gate runs / WARN dev
Dirty git tree	any row	FAIL gate runs / WARN dev
panel_hash	null or ≠ invoked panel	FAIL
Seed-log	report generator re-runs alignment verification itself — it audits inputs, never trusts rows	FAIL
Non-reproducible policy	any random row in paired/gate run	FAIL
Row integrity	count ≠ schedule rows; duplicate (battle_id, config_hash); paired seed mismatch; non-constant hashes within a run	FAIL
Split integrity	held-out team_hash in a dev-labeled run (or vice versa)	FAIL
6. Held-out discipline (T6)
You cannot technically stop a solo dev with root on his own machine. The achievable goal — state it honestly in the spec — is visible, auditable, budgeted access:

Ledger: yes. Append-only, committed (config/eval/heldout_ledger.jsonl). generate_heldout_schedule appends automatically at its existing confirm_heldout choke point: {date, purpose, panel_hash, schedule_hash, config_hash, git_sha}; gate runner appends the result summary hash afterward.
Access budget: one held-out gate attempt per config_hash lineage. A second attempt requires a panel version bump (fresh held-out teams) or an explicit justification entry. This targets the real overfitting mechanism: iterating a candidate until held-out happens to pass.
Runner refusals: prior ledger entry for this config_hash without justification; any held-out team_hash in a committed dev schedule; ledger history shows edited prior lines (append-only enforced by replaying the file's git history in a test).
Banner on every held-out report: "HELD-OUT RUN — these numbers must never inform tuning decisions."
7. Baseline freezing
Commit a baseline manifest (config/eval/baselines/heuristic-v1.json): clean git_sha, config_id, full config_hash (strengthened semantics), panel version + panel_hash, dev + held-out schedule_hashes, hero_team_hash, all opp team_hashes, Showdown commit + server patch hash, seed_base, PYTHONHASHSEED, sha256 of the reference result JSONL.

Immutable after T6: the manifest (changes = new versioned file, never edits), referenced team contents, panel version, server patch, reference JSONL. Verified, not assumed: before any comparison, the gate runner re-checks every manifest hash against the tree ("baseline drift" → refuse) and runs a baseline reproduction spot-check — re-run ~6 battles of the baseline schedule and require the winner sequence to match. A baseline that can't be re-reproduced is a label, not a baseline.

8. Report artifact
One deterministic generator, two outputs from identical data: report.md + report.json (schema_versioned, for later gate automation). Same input JSONLs → byte-identical outputs, so reports can be committed and diffed. Mandatory sections, in order:

Verdict line (first line): GO / NO-GO / UNDERPOWERED / SAFETY-FAIL + worst-cell callout.
Provenance block: all hashes — schedule, panel, both configs, git shas + dirty flags, team hashes, server patch, seed_base, PYTHONHASHSEED, run_ids, row counts, input sha256s.
Safety gates table with measured values.
Per-cell table: n, W/L/T, win rate, Wilson CI.
Aggregates: per-policy + overall pooled + unweighted cell mean, losing-cell list.
Paired section: n_11/n_00/n_10/n_01, delta, exact p, underpowered banner, discordant-battle list.
Mandatory warnings: ceiling-effect caveat, scripted_vgc = coverage-not-strength, paired-seeds-diverge-after-first-differing-choice, not-evidence-of-equivalence when underpowered, DEV vs HELD-OUT banner.
Reproduction block: exact CLI + env to regenerate everything.
9. 2b-4 unblock criteria
GO requires all of: T4 green (all safety gates + cross-server reproduction spot-check); T5 merged with fixture tests (known count tables → known p; golden byte-identical reports); T6 in place (manifest committed + reproduction-verified, ledger active, baseline held-out run recorded); and for the candidate config: paired McNemar vs pinned baseline on dev with n_discordant ≥ 10, delta > 0, exact p < 0.05, no safety regression, then a single budgeted held-out run with no directional reversal.

Block even when the aggregate looks fine: any cell flips from winning to losing vs baseline; improvement concentrated on weak policies with flat/negative delta on heuristic/max_damage cells; dev positive but held-out negative (overfitting signature); discordant-battle review shows degeneracy wins (e.g. Protect-stall exploitation); any latency/invalid/crash regression, dirty tree, or hash mismatch.

10. Adversarial: smallest mistake producing misleading confidence
The winner — "no significant difference" read as safety. Weak opponents + 50 games ⇒ n_discordant naturally tiny ⇒ p almost always large ⇒ careless read: "no regression, ship it." The harness would be systematically biased toward waving worse models through while looking rigorous. Every countermeasure in §3/§9 exists for this.
Config self-comparison. With today's thin config_hash, an env-flag mistake pairs a config against itself: 0 discordant reads as "perfectly stable." Hence the config_hash inequality fail-fast — and note 0 discordant is always ambiguous between "behaviorally identical" and "mislabeled duplicate"; the report should say so.
Unpaired eyeballing. Side-by-side independent Wilson CIs for A and B discard the pairing and roughly double the effective noise. Never present two-config results without the paired section adjacent.
Mandatory preconditions before T5 implementation
T3e merged with its four amendments (P0 counters, P1 panel v002, P2 activation evidence, P4 provenance).
Schema additions landed in T2's writer: seed_base, run_id + run manifest, panel_split, end_reason; battle_id semantics documented.
config_hash redefined over the effective config manifest, with a test that flipping a behavior-affecting env flag changes it.
Latency budget pinned as a number in config.
The verdict thresholds (n_discordant 6 / 10, losing-cell rule) written into the T5 spec as constants with rationale.
Decision recorded that the report generator independently re-verifies seed-log alignment and panel/team hashes.
One closing calibration: T5's most valuable output at this scale is not the p-value — it's the provenance audit plus a discordant-battle list a human actually reads. Design the report so those two are impossible to skip; the statistics can mature as N grows.