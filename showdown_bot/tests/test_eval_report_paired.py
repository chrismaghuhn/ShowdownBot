"""Tests for eval/report.py part 2 — paired McNemar mode + positive-evidence verdicts (T5 Task 4).

Spec: docs/superpowers/specs/2026-07-10-t5-report-generator-design.md §1.2/§1.3 (verdict
vocabulary + order, verbatim texts, paired section between Aggregates and Warnings).
Decision-tree semantics: docs/superpowers/reviews/2026-07-01-fable-t5-t6-eval-architecture-
review.md §3 (power floor / underpowered), §9 (block-even-when-aggregate-looks-fine: cell
flip, weak-policy-only), §10 (zero-discordant ambiguity, no unpaired side-by-side CIs).

Seam choice (documented): these tests build ``RunBundle`` objects DIRECTLY with synthetic
row dicts — the exact seam Task 3's dev-mode tests use (``_synthetic_row``/``_synthetic_bundle``
in test_eval_report.py). No files are touched; ``run_safety_gates`` + the paired builders read
only the row/manifest fields, so a hand-built bundle exercises the whole verdict tree. The
paired flow additionally needs ``seed`` (pairing key) and ``turns``/``end_hp_diff`` (discordant
list), which the helper below supplies.

A = candidate (run A), B = baseline (run B); delta = winrate_A - winrate_B (candidate ahead
when > 0). Strength cells = heuristic + max_damage (the only policies that measure strength).
"""
from __future__ import annotations

import json

import pytest

from showdown_bot.eval.report import (
    UNDERPOWERED_TEXT,
    ZERO_DISCORDANT_TEXT,
    RunBundle,
    generate_report,
)
from showdown_bot.eval.stats import exact_binom_two_sided_p


# --- synthetic bundle helpers (direct RunBundle construction, no files) -----------------

def _row(seed_index, *, config_hash, run_id, policy, team_hash, winner,
         turns=12, end_hp_diff=100, crashes=0, invalid=0, latency=100,
         end_reason="normal", dirty=False, panel_split="dev"):
    return {
        "battle_id": f"b{seed_index}", "config_hash": config_hash, "config_id": "cand",
        "schedule_hash": "schX", "seed_base": "baseX", "panel_hash": "panX", "run_id": run_id,
        "git_sha": "gitX", "format_id": "gen9vgc2025regi", "seed_index": seed_index,
        "seed": f"sodium,{seed_index:032x}",
        "opp_policy": policy, "opp_team_hash": team_hash, "hero_team_hash": "hero1",
        "panel_split": panel_split, "winner": winner, "invalid_choices": invalid,
        "crashes": crashes, "decision_latency_p95_ms": latency, "end_reason": end_reason,
        "dirty": dirty, "turns": turns, "end_hp_diff": end_hp_diff,
    }


def _bundle(rows, *, run_id, config_hash, budget=1000):
    team_hashes = {r["opp_team_hash"] for r in rows}
    manifest = {
        "run_id": run_id, "config_hash": config_hash, "schedule_hash": "schX",
        "seed_base": "baseX", "panel_hash": "panX", "git_sha": "gitX",
        "dirty": rows[0]["dirty"], "start_ts": "2026-07-10T00:00:00+00:00",
        "cli_invocation": ["cli.py", "gauntlet"], "pythonhashseed": "0",
    }
    return RunBundle(
        rows=rows, manifest=manifest, recomputed_panel_hash="panX",
        panel_dev_hashes=frozenset(team_hashes), panel_held_hashes=frozenset(),
        team_path_by_hash={h: f"teams/{h}.txt" for h in team_hashes},
        schedule_row_count=len(rows), schedule_reproducible=True,
        alignment_ok=True, alignment_detail=f"{len(rows)} contiguous, derived",
        latency_budget_ms=budget, git_sha="gitX",
        input_sha256={r: "0" * 64 for r in ("results", "seedlog", "schedule", "panel", "manifest")},
        input_basenames={r: f"{r}.x" for r in ("results", "seedlog", "schedule", "panel", "manifest")},
    )


def _make_pair(specs, *, budget=1000, a_overrides=None):
    """specs: list of (opp_policy, opp_team_hash, a_winner, b_winner). One battle per entry;
    seed_index/battle_id/seed shared across A and B (pairable), config_hash differs."""
    a_overrides = a_overrides or {}
    rows_a, rows_b = [], []
    for i, (policy, team, aw, bw) in enumerate(specs):
        rows_a.append(_row(i, config_hash="cfgA", run_id="runA", policy=policy,
                           team_hash=team, winner=aw, **a_overrides.get(i, {})))
        rows_b.append(_row(i, config_hash="cfgB", run_id="runB", policy=policy,
                           team_hash=team, winner=bw))
    return (_bundle(rows_a, run_id="runA", config_hash="cfgA", budget=budget),
            _bundle(rows_b, run_id="runB", config_hash="cfgB", budget=budget))


def _paired(bundle_a, bundle_b, mode="gate"):
    return generate_report(bundle_a, bundle_b, mode=mode)


# --- 1. GO -----------------------------------------------------------------------------

def _go_specs():
    # 10 heuristic + 10 max_damage cells; A always wins; B loses 12, ties none, wins 8
    specs = [("heuristic", "h1", "hero", "villain") for _ in range(10)]
    specs += [("max_damage", "m1", "hero", "villain") for _ in range(2)]
    specs += [("max_damage", "m1", "hero", "hero") for _ in range(8)]
    return specs                                     # n10=12, n11=8, n01=0, N=20


def test_paired_go_verdict():
    a, b = _make_pair(_go_specs())
    md, obj = _paired(a, b)
    first = md.splitlines()[0]
    assert first.startswith("# VERDICT: GO")
    assert "worst cell" in first                     # worst-cell callout always on verdict line
    assert obj["verdict"] == "GO"
    p = obj["paired"]
    assert (p["n11"], p["n00"], p["n10"], p["n01"]) == (8, 0, 12, 0)
    assert p["n_discordant"] == 12
    assert p["delta"] == pytest.approx(0.6)
    assert p["exact_p"] == pytest.approx(exact_binom_two_sided_p(12, 12))
    assert p["exact_p"] < 0.05
    assert p["cell_flips"] == []
    assert p["strength_delta"] > 0
    # both delta forms present and equal in the rendered md
    assert "winrate_A - winrate_B" in md


# --- 2. NO-GO (p too high) --------------------------------------------------------------

def test_paired_nogo_p_too_high():
    specs = [("heuristic", "h1", "hero", "villain") for _ in range(6)]      # n10=6
    specs += [("max_damage", "m1", "hero", "hero") for _ in range(6)]       # n11=6
    specs += [("max_damage", "m1", "villain", "hero") for _ in range(5)]    # n01=5
    a, b = _make_pair(specs)
    md, obj = _paired(a, b)
    first = md.splitlines()[0]
    assert obj["verdict"] == "NO-GO"
    assert first.startswith("# VERDICT: NO-GO")
    assert "p too high" in first
    p = obj["paired"]
    assert p["n_discordant"] == 11 and p["n10"] == 6 and p["n01"] == 5
    assert p["exact_p"] >= 0.05
    assert p["delta"] > 0                              # not blocked by delta — only by p
    assert p["cell_flips"] == []
    assert p["strength_delta"] > 0


# --- 3. NO-GO (cell flip, cell named) ---------------------------------------------------

def test_paired_nogo_cell_flip_names_cell():
    specs = [("heuristic", "h1", "hero", "villain") for _ in range(6)]      # n10=6
    specs += [("max_damage", "m1", "hero", "villain") for _ in range(6)]    # n10=6
    specs += [("greedy_protect", "g1", "villain", "hero") for _ in range(3)]  # n01=3, FLIP
    a, b = _make_pair(specs)
    md, obj = _paired(a, b)
    first = md.splitlines()[0]
    assert obj["verdict"] == "NO-GO"
    assert "cell flip" in first
    assert "greedy_protect" in first and "g1" in first     # the flipped cell is named
    p = obj["paired"]
    assert ["greedy_protect", "g1"] in p["cell_flips"]
    assert p["delta"] > 0 and p["exact_p"] < 0.05          # aggregate would otherwise be GO


# --- 4. NO-GO (weak-policy-only improvement) --------------------------------------------

def test_paired_nogo_weak_policy_only():
    # strength cells regress (A loses) but stay winning (concordant wins keep win_rate>0.5 -> no flip);
    # the aggregate gain is entirely on greedy_protect + scripted_vgc.
    specs = []
    specs += [("heuristic", "h1", "hero", "hero") for _ in range(5)]        # n11
    specs += [("heuristic", "h1", "villain", "hero") for _ in range(3)]     # n01 strength
    specs += [("max_damage", "m1", "hero", "hero") for _ in range(5)]       # n11
    specs += [("max_damage", "m1", "villain", "hero") for _ in range(3)]    # n01 strength
    specs += [("greedy_protect", "g1", "hero", "villain") for _ in range(9)]   # n10 weak
    specs += [("scripted_vgc", "s1", "hero", "villain") for _ in range(9)]     # n10 weak
    a, b = _make_pair(specs)
    md, obj = _paired(a, b)
    first = md.splitlines()[0]
    assert obj["verdict"] == "NO-GO"
    assert "weak-policy-only" in first
    p = obj["paired"]
    assert p["delta"] > 0 and p["exact_p"] < 0.05          # aggregate looks fine
    assert p["strength_delta"] <= 0                        # ...but strength cells are flat/negative
    assert p["cell_flips"] == []                           # no flip: strength win_rate stays > 0.5


# --- 5. UNDERPOWERED (verbatim banner, no p on verdict line, discordant list) ----------

def test_paired_underpowered():
    specs = [("heuristic", "h1", "hero", "hero") for _ in range(6)]         # n11=6 concordant
    specs += [("max_damage", "m1", "hero", "villain") for _ in range(4)]    # n10=4 discordant
    a, b = _make_pair(specs)
    md, obj = _paired(a, b)
    first = md.splitlines()[0]
    assert obj["verdict"] == "UNDERPOWERED"
    assert first.startswith("# VERDICT: UNDERPOWERED")
    assert "worst cell" in first
    # NO p-value on the verdict line
    assert "p=" not in first and "p-value" not in first and "p <" not in first
    # verbatim banner with k substituted
    assert UNDERPOWERED_TEXT.format(k=4) in md
    p = obj["paired"]
    assert p["n_discordant"] == 4
    # discordant-battle list present (0 < n_discordant <= 12) with the required fields
    assert len(p["discordant_battles"]) == 4
    d0 = p["discordant_battles"][0]
    for key in ("battle_id", "cell", "turns_a", "turns_b", "end_hp_diff_a", "end_hp_diff_b"):
        assert key in d0
    # p-value MAY appear in the detail section (allowed), just not on the verdict line
    assert p["exact_p"] is not None


# --- 6. SAFETY-FAIL dominates -----------------------------------------------------------

def test_paired_safety_fail_dominates_go_stats():
    # GO-worthy stats, but one crash row in run A -> SAFETY-FAIL, no strength text
    a, b = _make_pair(_go_specs(), a_overrides={0: {"crashes": 1}})
    md, obj = _paired(a, b)
    assert obj["verdict"] == "SAFETY-FAIL"
    assert obj["safety_pass"] is False
    assert md.splitlines()[0].startswith("# VERDICT: SAFETY-FAIL")
    assert "# VERDICT: GO" not in md
    # no strength text: no p-value emitted anywhere in the SAFETY-FAIL report
    assert obj["paired"]["exact_p"] is None
    assert "exact two-sided binomial p" not in md


# --- 7. Zero-discordant ambiguity -------------------------------------------------------

def test_paired_zero_discordant_ambiguity():
    specs = [("heuristic", "h1", "hero", "hero") for _ in range(5)]
    specs += [("max_damage", "m1", "hero", "hero") for _ in range(5)]       # all concordant
    a, b = _make_pair(specs)
    md, obj = _paired(a, b)
    assert obj["paired"]["n_discordant"] == 0
    assert obj["verdict"] == "UNDERPOWERED"
    # the ambiguity verbatim text, never "stable"
    assert ZERO_DISCORDANT_TEXT in md
    assert "behaviorally identical OR" in md
    assert "stable" not in md
    # no discordant list when n_discordant == 0
    assert obj["paired"]["discordant_battles"] == []


# --- 8. Tie flag ------------------------------------------------------------------------

def test_paired_tie_flag():
    specs = [("heuristic", "h1", "tie", "villain") for _ in range(2)]       # 2 ties in A
    specs += [("heuristic", "h1", "hero", "villain") for _ in range(8)]
    specs += [("max_damage", "m1", "hero", "villain") for _ in range(10)]
    a, b = _make_pair(specs)                                                 # tie share A = 2/20 = 10%
    md, obj = _paired(a, b)
    assert obj["paired"]["tie_flag"] is True
    assert obj["paired"]["tie_rate_a"] == pytest.approx(0.10)
    assert "TIE FLAG" in md


# --- 9. Paired-section adjacency (no unpaired side-by-side A-vs-B CIs) ------------------

def test_paired_section_adjacency():
    a, b = _make_pair(_go_specs())
    md, _ = _paired(a, b)
    order = ["## Provenance", "## Safety Gates", "## Per-Cell Results",
             "## Aggregates", "## Paired McNemar", "## Warnings", "## Reproduction"]
    positions = [md.index(h) for h in order]
    assert positions == sorted(positions), positions
    # exactly one per-cell table (the candidate's) — B's cells are NOT shown as a rival CI table
    assert md.count("## Per-Cell Results") == 1
    # the A-vs-B comparison (delta, n10/n01) lives ONLY in the paired section
    before = md[: md.index("## Paired McNemar")]
    paired_section = md[md.index("## Paired McNemar"): md.index("## Warnings")]
    assert "n10" not in before and "n10" in paired_section
    assert "delta" not in before and "delta" in paired_section


# --- 10. Determinism --------------------------------------------------------------------

def test_paired_report_is_deterministic():
    a, b = _make_pair(_go_specs())
    md1, obj1 = _paired(a, b)
    md2, obj2 = _paired(a, b)
    assert md1 == md2
    assert json.dumps(obj1, sort_keys=True) == json.dumps(obj2, sort_keys=True)


# --- 11. Reproduction block lists BOTH runs (Task-4 flagged gap, fixed in T5 Task 5) -----

def test_paired_reproduction_lists_both_runs():
    """The paired report's Reproduction block previously showed only run A's regenerate
    inputs (a Task-4 flagged gap). It must now show both runs' recorded invocations AND a
    single 'regenerate this report' CLI line that carries both --run-a/--seedlog-a AND
    --run-b/--seedlog-b."""
    a, b = _make_pair(_go_specs())
    md, obj = _paired(a, b)
    rep = obj["reproduction"]

    # both runs' run_command/env/showdown_commit/server_patch_hash/input_sha256 present
    assert rep["run_command_a"] and rep["run_command_b"]
    assert "showdown_bot.cli" in rep["run_command_a"]
    assert "showdown_bot.cli" in rep["run_command_b"]
    assert rep["env_a"] and rep["env_b"]
    assert rep["input_sha256_a"] and rep["input_sha256_b"]

    # the regenerate line is a SINGLE eval-report invocation carrying both runs
    assert rep["report_command"].count("eval-report") == 1
    assert "--run-a" in rep["report_command"] and "--run-b" in rep["report_command"]
    assert "--seedlog-a" in rep["report_command"] and "--seedlog-b" in rep["report_command"]

    # md: both "Run A" and "Run B" labelled sections in Reproduction, and the combined command
    reproduction_section = md[md.index("## Reproduction"):]
    assert "Run A" in reproduction_section and "Run B" in reproduction_section
    assert reproduction_section.count("eval-report") == 1
    assert "--run-a" in reproduction_section and "--run-b" in reproduction_section
