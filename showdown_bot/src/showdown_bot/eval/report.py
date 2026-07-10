"""T5 deterministic report generator — part 1: RunBundle audit + safety gates + single-run
report (review §5/§8; spec §1.3).

The generator NEVER trusts result rows: ``RunBundle.load`` re-derives everything it can and
refuses (``ReportInputError``) on any structural/provenance tampering it can prove, while the
"soft" safety checks surface as a gate TABLE whose failures flip the verdict to SAFETY-FAIL.
Safety gates come FIRST: any FAIL means no strength claim is emitted anywhere. A single run can
only ever produce ``SINGLE-RUN SAFETY-PASS`` / ``SINGLE-RUN SAFETY-FAIL`` — never GO/NO-GO
(non-comparative by construction).

Structure (so Task 4 can extend to paired mode): ``RunBundle`` (load + audit) → ``run_safety_gates``
→ cell/aggregate builders → a single shared "report data" dict → ``_render_md`` + ``_render_json``.
No wall-clock timestamps in the body — the only time printed is the manifest's ``start_ts``.

R6 documented deviation: a *pure winner flip* in a result row is undetectable by any input-hash
cross-check (the manifest carries no per-row integrity hash and the audit does not re-parse
``room_raw``). This slice recomputes ``battle_id`` and the deterministic per-row ``seed`` instead,
catching seed/index/schedule tampering; the "edited result row" R6 case is exercised via a seed
edit. See tests/test_eval_report.py for the pinned limitation.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from showdown_bot.eval.gates import load_latency_budget_ms
from showdown_bot.eval.panel import PanelError, load_panel
from showdown_bot.eval.policies import is_reproducible
from showdown_bot.eval.result_jsonl import (
    ResultRowError,
    make_battle_id,
    validate_battle_row,
)
from showdown_bot.eval.run_manifest import manifest_path_for
from showdown_bot.eval.schedule import ScheduleError, load_schedule, verify_schedule_alignment
from showdown_bot.eval.seeding import SeedLogError, derive_battle_seed
from showdown_bot.eval.stats import (
    LOSING_CELL_WILSON_UPPER,
    TIE_FLAG_RATE,
    wilson_interval,
)

SCHEMA_VERSION = 1

VERDICT_SINGLE_PASS = "SINGLE-RUN SAFETY-PASS"
VERDICT_SINGLE_FAIL = "SINGLE-RUN SAFETY-FAIL"

# --- Mandatory verbatim texts (spec §1.3) — code constants so the wording is pinned. --------
# The UNDERPOWERED phrasing and the HELD-OUT banner are quoted verbatim from the spec; the
# remaining caveats are authored here and pinned byte-exactly by the Task 6 golden report.
UNDERPOWERED_TEXT = (
    "UNDERPOWERED: only {k} discordant pairs. No conclusion is possible in either direction. "
    "This is not evidence of equivalence and must not be cited to unblock 2b-4."
)
HELDOUT_BANNER = "HELD-OUT RUN — these numbers must never inform tuning decisions."
ZERO_DISCORDANT_TEXT = (
    "n_discordant == 0: the two configs are either behaviorally identical OR one is a mislabeled "
    "duplicate of the other. This is NOT evidence of stability and must never be cited as such."
)
CEILING_EFFECT_CAVEAT = (
    "Ceiling/floor effect: cells at 0% or 100% win rate sit against a hard bound, so their Wilson "
    "interval understates uncertainty at these sample sizes. Small-n cells carry no strength claim."
)
SCRIPTED_VGC_CAVEAT = (
    "scripted_vgc cells measure coverage, not strength: the scripted opponent is a fixed policy "
    "used to exercise pipeline paths, so a high win rate against it is not evidence of skill."
)
PAIRED_SEED_DIVERGENCE_CAVEAT = (
    "Paired seeds share luck only up to the first differing choice: after the two configs diverge, "
    "the battles are no longer luck-matched, so per-turn comparisons past that point are not paired."
)
SINGLE_RUN_NONCOMPARATIVE_CAVEAT = (
    "This is a single-run safety readout, not a comparison. A single run cannot establish "
    "improvement over any baseline — it can only pass or fail the safety gates. Any strength claim "
    "requires a paired run against a pinned baseline (T6) with the positive-evidence rule."
)


class ReportInputError(ValueError):
    """An input file is unreadable, missing its manifest sidecar, or fails a hard provenance
    audit (a row that does not validate, or a recomputed ``battle_id`` / ``seed`` that does not
    match the row — i.e. a tampered result row). These make the bundle un-loadable; the softer
    safety checks surface as gate FAILs (SAFETY-FAIL) instead of raising here."""


@dataclass(frozen=True)
class SafetyGate:
    gate: str
    status: str      # "PASS" | "FAIL" | "WARN"
    measured: str


@dataclass
class RunBundle:
    """A loaded + audited single run: rows, manifest, recomputed panel provenance, alignment
    result, per-file sha256s, and the derived primitives the gates read. Build via
    ``RunBundle.load``; tests may construct it directly with synthetic fields."""
    rows: list
    manifest: dict
    recomputed_panel_hash: str | None
    panel_dev_hashes: frozenset
    panel_held_hashes: frozenset
    team_path_by_hash: dict
    schedule_row_count: int
    schedule_reproducible: bool
    alignment_ok: bool
    alignment_detail: str
    latency_budget_ms: int
    git_sha: str
    input_sha256: dict
    input_basenames: dict

    @classmethod
    def load(cls, results_path, seedlog_path, schedule_path, panel_path, *, teams_root,
             manifest_path=None) -> "RunBundle":
        rows = _read_rows(results_path)
        for r in rows:
            try:
                validate_battle_row(r)
            except ResultRowError as exc:
                raise ReportInputError(f"invalid result row: {exc}") from exc
        # Hard tamper audit: recompute the pairing key and the deterministic seed for each row.
        for r in rows:
            expect_bid = make_battle_id(r["schedule_hash"], r["seed_index"], r["seed"])
            if expect_bid != r["battle_id"]:
                raise ReportInputError(
                    f"battle_id mismatch at seed_index {r['seed_index']}: row "
                    f"{r['battle_id']!r} != recomputed {expect_bid!r} (result row tampered?)"
                )
            expect_seed = derive_battle_seed(r["seed_base"], r["seed_index"])
            if expect_seed != r["seed"]:
                raise ReportInputError(
                    f"seed derivation mismatch at seed_index {r['seed_index']}: row "
                    f"{r['seed']!r} != derive_battle_seed {expect_seed!r} (result row tampered?)"
                )

        mpath = manifest_path if manifest_path is not None else manifest_path_for(results_path)
        try:
            manifest = json.loads(Path(mpath).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ReportInputError(f"cannot read manifest sidecar {mpath}: {exc}") from exc

        try:
            schedule = load_schedule(schedule_path)
        except (ScheduleError, OSError) as exc:
            raise ReportInputError(f"cannot load schedule {schedule_path}: {exc}") from exc
        try:
            panel = load_panel(panel_path, teams_root=str(teams_root))
        except (PanelError, OSError) as exc:
            raise ReportInputError(f"cannot load panel {panel_path}: {exc}") from exc

        base = rows[0]["seed_base"]
        try:
            verify_schedule_alignment(schedule, seedlog_path, base)
            alignment_ok = True
            alignment_detail = f"{len(schedule.rows)} contiguous, derived"
        except (SeedLogError, ScheduleError) as exc:
            alignment_ok = False
            alignment_detail = f"MISALIGNED: {type(exc).__name__}"

        input_sha256 = {
            "results": _sha256_file(results_path),
            "seedlog": _sha256_file(seedlog_path),
            "schedule": _sha256_file(schedule_path),
            "panel": _sha256_file(panel_path),
            "manifest": _sha256_file(mpath),
        }
        input_basenames = {
            "results": Path(results_path).name, "seedlog": Path(seedlog_path).name,
            "schedule": Path(schedule_path).name, "panel": Path(panel_path).name,
            "manifest": Path(mpath).name,
        }
        return cls(
            rows=rows, manifest=manifest,
            recomputed_panel_hash=panel.panel_hash,
            panel_dev_hashes=frozenset(t.team_hash for t in panel.dev_teams),
            panel_held_hashes=frozenset(t.team_hash for t in panel.heldout_teams),
            team_path_by_hash={t.team_hash: t.team_path
                               for t in (*panel.dev_teams, *panel.heldout_teams)},
            schedule_row_count=len(schedule.rows),
            schedule_reproducible=schedule.reproducible,
            alignment_ok=alignment_ok, alignment_detail=alignment_detail,
            latency_budget_ms=load_latency_budget_ms(),
            git_sha=rows[0]["git_sha"],
            input_sha256=input_sha256, input_basenames=input_basenames,
        )


def _read_rows(results_path) -> list:
    try:
        text = Path(results_path).read_text(encoding="utf-8")
    except OSError as exc:
        raise ReportInputError(f"cannot read results {results_path}: {exc}") from exc
    rows = []
    for lineno, line in enumerate(text.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ReportInputError(f"{results_path}:{lineno}: malformed JSON: {exc}") from exc
    if not rows:
        raise ReportInputError(f"no rows in {results_path}")
    return rows


def _sha256_file(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _const(rows, field):
    """Return (value_of_row0, is_constant_across_rows)."""
    distinct = {r[field] for r in rows}
    return rows[0][field], len(distinct) == 1


# --- Safety gates -----------------------------------------------------------------------

def run_safety_gates(bundle: RunBundle, mode: str = "gate") -> list:
    """The spec §1.3 gate table. ``mode`` only changes latency + dirty (FAIL in ``gate``,
    WARN in ``dev``); every other failure is a hard FAIL in both modes."""
    rows = bundle.rows
    gates: list = []

    def add(name, ok, measured, *, soft=False):
        if ok:
            status = "PASS"
        elif soft and mode == "dev":
            status = "WARN"
        else:
            status = "FAIL"
        gates.append(SafetyGate(name, status, measured))

    n = len(rows)
    add("rows_match_schedule", n == bundle.schedule_row_count,
        f"{n} == {bundle.schedule_row_count}")

    tot_inv = sum(int(r["invalid_choices"]) for r in rows)
    add("invalid_choices", tot_inv == 0, str(tot_inv))

    tot_cr = sum(int(r["crashes"]) for r in rows)
    add("crashes", tot_cr == 0, str(tot_cr))

    nonnormal = sorted({r["end_reason"] for r in rows if r["end_reason"] != "normal"})
    add("end_reason_normal", not nonnormal,
        "all normal" if not nonnormal else f"non-normal: {nonnormal}")

    worst = max((int(r["decision_latency_p95_ms"]) for r in rows), default=0)
    add("latency_p95", worst <= bundle.latency_budget_ms,
        f"worst={worst} (budget {bundle.latency_budget_ms})", soft=True)

    add("seed_log_alignment", bundle.alignment_ok, bundle.alignment_detail)

    seen: set = set()
    dup = None
    for r in rows:
        key = (r["battle_id"], r["config_hash"])
        if key in seen:
            dup = key
            break
        seen.add(key)
    add("no_duplicate_rows", dup is None, "none" if dup is None else f"dup {dup}")

    row_ph, ph_const = _const(rows, "panel_hash")
    ph_ok = bundle.recomputed_panel_hash is not None and ph_const \
        and row_ph == bundle.recomputed_panel_hash
    add("panel_hash_match", ph_ok,
        str(bundle.recomputed_panel_hash) if ph_ok
        else f"mismatch: rows={row_ph!r} file={bundle.recomputed_panel_hash!r}")

    dirty_rows = [r for r in rows if r["dirty"]]
    add("dirty", not dirty_rows, "none" if not dirty_rows else f"{len(dirty_rows)} dirty",
        soft=True)

    missing_th = [r["seed_index"] for r in rows
                  if not r.get("opp_team_hash") or not r.get("hero_team_hash")]
    add("team_hashes_present", not missing_th,
        "present" if not missing_th else f"missing at {missing_th[:5]}")

    panel_all = bundle.panel_dev_hashes | bundle.panel_held_hashes
    not_in_panel = sorted({r["opp_team_hash"] for r in rows if r["opp_team_hash"] not in panel_all})
    add("opp_hashes_subset_panel", not not_in_panel,
        "subset" if not not_in_panel else f"not in panel: {not_in_panel}")

    split_bad = []
    for r in rows:
        ps, oh = r.get("panel_split"), r["opp_team_hash"]
        if ps == "dev" and oh in bundle.panel_held_hashes:
            split_bad.append((r["seed_index"], "heldout-in-dev"))
        elif ps == "heldout" and oh in bundle.panel_dev_hashes:
            split_bad.append((r["seed_index"], "dev-in-heldout"))
    add("split_integrity", not split_bad,
        "consistent" if not split_bad else f"{split_bad[:5]}")

    nonrepro = sorted({r["opp_policy"] for r in rows if not is_reproducible(r["opp_policy"])})
    add("reproducible_policies", not nonrepro,
        "all reproducible" if not nonrepro else f"non-reproducible: {nonrepro}")

    for field, name in [("config_hash", "one_config_hash"), ("schedule_hash", "one_schedule_hash"),
                        ("seed_base", "one_seed_base"), ("run_id", "one_run_id"),
                        ("git_sha", "one_git_sha")]:
        val, const = _const(rows, field)
        add(name, const,
            str(val) if const else f"NON-CONSTANT: {sorted({str(r[field]) for r in rows})}")

    mm = []
    for field in ("run_id", "config_hash", "schedule_hash", "seed_base", "panel_hash",
                  "git_sha", "dirty"):
        rv, const = _const(rows, field)
        if not const or rv != bundle.manifest.get(field):
            mm.append(field)
    add("manifest_match", not mm, "ok" if not mm else f"mismatch: {mm}")

    return gates


# --- Cell / aggregate builders ----------------------------------------------------------

def _build_cells(rows, team_path_by_hash) -> list:
    groups: dict = {}
    for r in rows:
        key = (r["opp_policy"], r["opp_team_hash"])
        g = groups.setdefault(key, {"wins": 0, "losses": 0, "ties": 0})
        w = r["winner"]
        if w == "hero":
            g["wins"] += 1
        elif w == "tie":
            g["ties"] += 1
        else:
            g["losses"] += 1
    cells = []
    for (policy, thash) in sorted(groups):
        g = groups[(policy, thash)]
        n = g["wins"] + g["losses"] + g["ties"]
        lo, hi = wilson_interval(g["wins"], n)
        cells.append({
            "opp_policy": policy, "opp_team_hash": thash,
            "opp_team_path": team_path_by_hash.get(thash, ""),
            "n": n, "wins": g["wins"], "losses": g["losses"], "ties": g["ties"],
            "win_rate": (g["wins"] / n) if n else 0.0,
            "wilson_lo": lo, "wilson_hi": hi,
            "losing": hi < LOSING_CELL_WILSON_UPPER,
        })
    return cells


def _build_aggregates(cells) -> dict:
    pol: dict = {}
    for c in cells:
        p = pol.setdefault(c["opp_policy"], {"wins": 0, "n": 0})
        p["wins"] += c["wins"]
        p["n"] += c["n"]
    per_policy = []
    for name in sorted(pol):
        w, nn = pol[name]["wins"], pol[name]["n"]
        lo, hi = wilson_interval(w, nn)
        per_policy.append({"opp_policy": name, "n": nn, "wins": w,
                           "win_rate": (w / nn) if nn else 0.0, "wilson_lo": lo, "wilson_hi": hi})
    total_w = sum(c["wins"] for c in cells)
    total_n = sum(c["n"] for c in cells)
    total_t = sum(c["ties"] for c in cells)
    lo, hi = wilson_interval(total_w, total_n)
    overall = {"n": total_n, "wins": total_w,
               "win_rate": (total_w / total_n) if total_n else 0.0,
               "wilson_lo": lo, "wilson_hi": hi}
    unweighted = (sum(c["win_rate"] for c in cells) / len(cells)) if cells else 0.0
    losing_cells = [[c["opp_policy"], c["opp_team_hash"]] for c in cells if c["losing"]]
    worst = min(
        cells,
        key=lambda c: (c["wilson_hi"], c["win_rate"], c["opp_policy"], c["opp_team_hash"]),
    ) if cells else None
    tie_rate = (total_t / total_n) if total_n else 0.0
    return {
        "per_policy": per_policy, "overall_pooled": overall,
        "unweighted_cell_mean": unweighted, "losing_cells": losing_cells,
        "worst_cell": None if worst is None else {
            "opp_policy": worst["opp_policy"], "opp_team_hash": worst["opp_team_hash"],
            "win_rate": worst["win_rate"], "wilson_lo": worst["wilson_lo"],
            "wilson_hi": worst["wilson_hi"], "n": worst["n"],
        },
        "tie_rate": tie_rate, "tie_flag": tie_rate > TIE_FLAG_RATE,
    }


def _build_warnings(cells, heldout) -> list:
    w = [SINGLE_RUN_NONCOMPARATIVE_CAVEAT, CEILING_EFFECT_CAVEAT]
    if any(c["opp_policy"] == "scripted_vgc" for c in cells):
        w.append(SCRIPTED_VGC_CAVEAT)
    if heldout:
        w.append(HELDOUT_BANNER)
    return w


def _build_reproduction(bundle: RunBundle) -> dict:
    m = bundle.manifest
    cli = list(m.get("cli_invocation") or [])
    run_command = ("python -m showdown_bot.cli " + " ".join(str(x) for x in cli[1:])) if cli else ""
    bn = bundle.input_basenames
    report_command = (
        "python -m showdown_bot.cli eval-report "
        f"--run-a {bn.get('results')} --seedlog-a {bn.get('seedlog')} "
        f"--schedule {bn.get('schedule')} --panel {bn.get('panel')} --out <dir> --mode gate"
    )
    return {
        "run_command": run_command,
        "env": {"PYTHONHASHSEED": m.get("pythonhashseed"),
                "SHOWDOWN_BATTLE_SEED_BASE": m.get("seed_base")},
        "showdown_commit": m.get("showdown_commit"),
        "server_patch_hash": m.get("server_patch_hash"),
        "report_command": report_command,
        "input_sha256": dict(bundle.input_sha256),
    }


# --- Report assembly --------------------------------------------------------------------

def _build_data(bundle, mode, verdict, safety_pass, gates, cells, aggregates, warnings, heldout):
    row0, m = bundle.rows[0], bundle.manifest
    provenance = {
        "run_id": m.get("run_id"), "config_id": row0.get("config_id"),
        "config_hash": m.get("config_hash"), "format_id": row0.get("format_id"),
        "schedule_hash": m.get("schedule_hash"), "seed_base": m.get("seed_base"),
        "panel_hash": m.get("panel_hash"), "recomputed_panel_hash": bundle.recomputed_panel_hash,
        "git_sha": m.get("git_sha"), "dirty": m.get("dirty"), "row_count": len(bundle.rows),
        "start_ts": m.get("start_ts"), "showdown_commit": m.get("showdown_commit"),
        "server_patch_hash": m.get("server_patch_hash"), "pythonhashseed": m.get("pythonhashseed"),
        "input_sha256": dict(bundle.input_sha256),
    }
    return {
        "schema_version": SCHEMA_VERSION, "mode": mode, "paired": False,
        "verdict": verdict, "safety_pass": safety_pass, "heldout": heldout,
        "provenance": provenance,
        "safety_gates": [{"gate": g.gate, "status": g.status, "measured": g.measured}
                         for g in gates],
        "cells": cells, "aggregates": aggregates,
        "warnings": warnings, "reproduction": _build_reproduction(bundle),
    }


def generate_report(bundle: RunBundle, mode: str = "gate"):
    """Return ``(report_md: str, report_json: dict)`` for a single run. Safety gates first:
    any FAIL yields ``SINGLE-RUN SAFETY-FAIL`` and no GO/NO-GO text anywhere. Deterministic:
    same inputs → byte-identical outputs."""
    gates = run_safety_gates(bundle, mode)
    safety_pass = all(g.status != "FAIL" for g in gates)
    verdict = VERDICT_SINGLE_PASS if safety_pass else VERDICT_SINGLE_FAIL
    cells = _build_cells(bundle.rows, bundle.team_path_by_hash)
    aggregates = _build_aggregates(cells)
    heldout = any(r.get("panel_split") == "heldout" for r in bundle.rows)
    warnings = _build_warnings(cells, heldout)
    data = _build_data(bundle, mode, verdict, safety_pass, gates, cells, aggregates,
                       warnings, heldout)
    return _render_md(data), _render_json(data)


def _f(x) -> str:
    return f"{x:.4f}"


def _render_md(data) -> str:
    p = data["provenance"]
    agg = data["aggregates"]
    out: list = []
    out.append(f"# VERDICT: {data['verdict']}")
    out.append("")
    out.append(f"Mode: {data['mode']} · schema_version {data['schema_version']} · "
               f"paired: {str(data['paired']).lower()}")
    out.append("")

    out.append("## Provenance")
    out.append("")
    out.append("| field | value |")
    out.append("|---|---|")
    for k in ["run_id", "config_id", "config_hash", "format_id", "schedule_hash", "seed_base",
              "panel_hash", "recomputed_panel_hash", "git_sha", "dirty", "row_count", "start_ts",
              "showdown_commit", "server_patch_hash", "pythonhashseed"]:
        out.append(f"| {k} | {p.get(k)} |")
    out.append("")
    out.append("| input file | sha256 |")
    out.append("|---|---|")
    for role in ["results", "seedlog", "schedule", "panel", "manifest"]:
        out.append(f"| {role} | {p['input_sha256'].get(role)} |")
    out.append("")

    out.append("## Safety Gates")
    out.append("")
    out.append(f"Result: {'SAFETY-PASS' if data['safety_pass'] else 'SAFETY-FAIL'}")
    out.append("")
    out.append("| gate | status | measured |")
    out.append("|---|---|---|")
    for g in data["safety_gates"]:
        out.append(f"| {g['gate']} | {g['status']} | {g['measured']} |")
    out.append("")

    out.append("## Per-Cell Results")
    out.append("")
    out.append("Hero is the evaluated config in every cell; the opponent policy and team vary.")
    out.append("")
    out.append("| opp_policy | opp_team_hash | team_path | n | W/L/T | win_rate | "
               "wilson_lo | wilson_hi | losing |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    for c in data["cells"]:
        wlt = f"{c['wins']}/{c['losses']}/{c['ties']}"
        out.append(f"| {c['opp_policy']} | {c['opp_team_hash']} | {c['opp_team_path']} | "
                   f"{c['n']} | {wlt} | {_f(c['win_rate'])} | {_f(c['wilson_lo'])} | "
                   f"{_f(c['wilson_hi'])} | {'yes' if c['losing'] else 'no'} |")
    out.append("")

    out.append("## Aggregates")
    out.append("")
    out.append("Per-policy pooled:")
    out.append("")
    out.append("| opp_policy | n | wins | win_rate | wilson_lo | wilson_hi |")
    out.append("|---|---|---|---|---|---|")
    for pp in agg["per_policy"]:
        out.append(f"| {pp['opp_policy']} | {pp['n']} | {pp['wins']} | {_f(pp['win_rate'])} | "
                   f"{_f(pp['wilson_lo'])} | {_f(pp['wilson_hi'])} |")
    out.append("")
    op = agg["overall_pooled"]
    out.append(f"Overall pooled: n={op['n']} wins={op['wins']} win_rate={_f(op['win_rate'])} "
               f"wilson=[{_f(op['wilson_lo'])}, {_f(op['wilson_hi'])}]")
    out.append("")
    out.append(f"Unweighted cell mean win rate: {_f(agg['unweighted_cell_mean'])}")
    out.append("")
    if agg["worst_cell"]:
        wc = agg["worst_cell"]
        out.append(f"Worst cell: {wc['opp_policy']} x {wc['opp_team_hash']} — "
                   f"win_rate {_f(wc['win_rate'])}, wilson upper {_f(wc['wilson_hi'])} "
                   f"(n={wc['n']})")
        out.append("")
    if agg["losing_cells"]:
        out.append("Losing cells (Wilson upper < 0.5):")
        for lc in agg["losing_cells"]:
            out.append(f"- {lc[0]} x {lc[1]}")
    else:
        out.append("Losing cells (Wilson upper < 0.5): none")
    out.append("")
    if agg["tie_flag"]:
        out.append(f"TIE FLAG: tie share {_f(agg['tie_rate'])} exceeds {TIE_FLAG_RATE} — "
                   "check for degeneracy.")
        out.append("")

    out.append("## Warnings")
    out.append("")
    for wtext in data["warnings"]:
        out.append(f"> {wtext}")
        out.append("")

    rep = data["reproduction"]
    out.append("## Reproduction")
    out.append("")
    out.append("Run (from the manifest's recorded invocation):")
    out.append("")
    out.append("```")
    out.append(f"PYTHONHASHSEED={rep['env'].get('PYTHONHASHSEED')} "
               f"SHOWDOWN_BATTLE_SEED_BASE={rep['env'].get('SHOWDOWN_BATTLE_SEED_BASE')} \\")
    out.append(f"  {rep['run_command']}")
    out.append("```")
    out.append("")
    out.append(f"showdown_commit {rep['showdown_commit']} · "
               f"server_patch_hash {rep['server_patch_hash']}")
    out.append("")
    out.append("Regenerate this report:")
    out.append("")
    out.append("```")
    out.append(rep["report_command"])
    out.append("```")
    out.append("")
    return "\n".join(out) + "\n"


def _render_json(data) -> dict:
    """The JSON report IS the shared data dict (already json-serializable)."""
    return data
