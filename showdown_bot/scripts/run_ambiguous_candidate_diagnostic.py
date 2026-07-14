"""Real run: classify every ambiguous/excluded decision at cap=4 (historical 63), cap=6, and
cap=8 (spec Sec.3.3), via a small targeted re-run (only the ambiguous decision_ids, not the full
944) to get a live trace to inspect. Also writes the fix-feasibility investigation (spec Sec.3.2)
into the same report -- investigation only, no decision.py code change.

Joins on decision_id throughout (never bare request_hash) and classifies each re-run's ACTUAL
resolution outcome rather than assuming every historical exception is a label-collision/missing-
match case -- a re-run that resolves to exactly one match, or raises a different exception, is
routed to other_pipeline_error with a concrete rationale, not force-classified as ambiguous. A
structural ambiguity classification is ADDITIONALLY gated on the ORIGINAL exception being
confirmed to come from accuracy_gate_b._chosen_candidate's own ambiguous/no-match RuntimeError
paths -- a live re-run that coincidentally looks ambiguous does not, by itself, prove that was the
original decision's actual exclusion cause.

Usage (from showdown_bot/): PYTHONPATH="$(pwd)/src" python scripts/run_ambiguous_candidate_diagnostic.py
"""
from __future__ import annotations

import copy
import glob
import json
import os
import sys
from pathlib import Path

os.environ["SHOWDOWN_CALC_BACKEND"] = "persistent"

SCRIPT_DIR = Path(__file__).resolve().parent
SHOWDOWN_BOT_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SHOWDOWN_BOT_ROOT.parent
sys.path.insert(0, str(SHOWDOWN_BOT_ROOT / "src"))

DATA_EVAL = REPO_ROOT / "data" / "eval"
OUT_DIR = DATA_EVAL / "accuracy-cap-derisk"
FORMAT_ID = "gen9vgc2025regi"


def _original_exception_is_chosen_candidate_ambiguity(original_message: str) -> bool:
    """True only if the ORIGINAL gate exception is confirmed to come from
    accuracy_gate_b._chosen_candidate's own ambiguous/no-match RuntimeError paths -- both raise
    RuntimeError with a fixed, distinctive message prefix (verified directly against
    accuracy_gate_b.py this session: "ambiguous chosen_candidate_id=..." / "no candidate matches
    chosen_candidate_id=..."), and run_gate_b records exceptions as f"{type(exc).__name__}:
    {exc}" (verified against run_gate_b's own exception-recording line: `exceptions.append((
    d.request_hash, f"{type(exc).__name__}: {exc}"))`). Any other exception type/message -- a
    calc timeout, a NaN, an unrelated crash that happens to ALSO be a RuntimeError with a
    different message -- must not be treated as a reproducible structural ambiguity, even if a
    live re-run happens to produce an ambiguous-looking trace by coincidence."""
    return original_message.startswith("RuntimeError: ambiguous chosen_candidate_id=") or \
        original_message.startswith("RuntimeError: no candidate matches chosen_candidate_id=")


def _classify_from_trace(trace):
    """Bridges a real DecisionTrace to classify_ambiguous_case's structural inputs. Returns
    (classification, is_genuinely_ambiguous) -- the caller decides other_pipeline_error routing
    when is_genuinely_ambiguous is False (exactly one match -- did not reproduce as an ambiguity).

    CORRECTED (post-Task-10/10b): supplies the now-required chosen_candidate_missing_subreason
    when routing to that primary cause, and guards len(ja_list) >= 2 before calling any
    structural-collision helper (rather than trusting len(matches) >= 2 transitively, since
    CandidateTrace.joint_action is typed Any and can legitimately be None for some candidates)."""
    from showdown_bot.battle.decision import TOP_K_TRACE_CANDIDATES
    from showdown_bot.eval.accuracy_cap_derisk import (
        _strip_tera, classify_ambiguous_case, distinct_move_or_targets,
        distinct_switch_targets, distinct_tera_states,
    )

    chosen_id = trace.chosen_candidate_id
    exact = [c for c in trace.candidates if c.candidate_id == chosen_id]
    matches = exact
    if not matches:
        stripped = _strip_tera(chosen_id) if chosen_id else None
        matches = [c for c in trace.candidates if stripped and _strip_tera(c.candidate_id) == stripped]

    if len(matches) == 1:
        return None, False  # resolves cleanly on re-run -- NOT a reproduced ambiguity

    if len(matches) == 0:
        # chosen_candidate_missing path -- classify_ambiguous_case REQUIRES a concrete
        # sub-reason (spec Sec.3.1, enforced since Task 10's fix). Distinguish "the trace's own
        # candidate list is already at the top-K cap, so truncation is plausible" from "the full
        # untruncated set was returned and the chosen one still isn't in it" -- a genuinely
        # different loss mechanism. This is diagnostic phrasing, not a proof of mechanism.
        top_k_truncated = len(trace.candidates) >= TOP_K_TRACE_CANDIDATES
        subreason = (
            "top_k_truncation_plausible" if top_k_truncated
            else "chosen_candidate_absent_from_full_candidate_set"
        )
        classification = classify_ambiguous_case(
            chosen_candidate_id=chosen_id or "<none>",
            matching_candidate_ids=[],
            matching_joint_actions_distinct_switch_targets=False,
            matching_joint_actions_distinct_tera=False,
            matching_joint_actions_distinct_move_or_target=False,
            exact_score_tie=False, collision_spans_nonzero_rank=False,
            top_k_truncated=top_k_truncated,
            chosen_candidate_missing_subreason=subreason,
        )
        return classification, True

    # len(matches) >= 2 -- genuine label collision
    ja_list = [c.joint_action for c in matches if c.joint_action is not None]
    if len(ja_list) < 2:
        # Fewer than 2 real JointAction objects survived the None-filter -- the structural-
        # collision helpers require >=2 real joint actions for a meaningful distinctness
        # comparison (Task 10b's review: distinct_switch_targets can report True from a SINGLE
        # double-switch candidate alone, since slot_index alone differentiates the two slots'
        # targets). Report conservatively (no distinctness claims) rather than risk a spurious
        # True from an under-populated comparison set.
        distinct_switch = distinct_tera = distinct_move = False
    else:
        distinct_switch = distinct_switch_targets(ja_list)
        distinct_tera = distinct_tera_states(ja_list)
        distinct_move = distinct_move_or_targets(ja_list)

    scores = {c.aggregate_score for c in matches}
    exact_tie = len(scores) == 1 and len(matches) > 1
    ranks = {c.rank for c in matches}
    collision_spans_nonzero_rank = any(r != 0 for r in ranks) if matches else False

    classification = classify_ambiguous_case(
        chosen_candidate_id=chosen_id or "<none>",
        matching_candidate_ids=[c.candidate_id for c in matches],
        matching_joint_actions_distinct_switch_targets=distinct_switch,
        matching_joint_actions_distinct_tera=distinct_tera,
        matching_joint_actions_distinct_move_or_target=distinct_move,
        exact_score_tie=exact_tie, collision_spans_nonzero_rank=collision_spans_nonzero_rank,
    )
    return classification, True


def _decisions_by_decision_id(target_decision_ids: set[str]):
    """Full per-file SeedIdentity + decision_id extraction (same pattern as Task 4/5) -- joins on
    decision_id, never bare request_hash, so a request_hash collision (even though empirically
    absent from this corpus per Task 7 of the accuracy-offline-gate plan) can never silently
    overwrite one decision with another here."""
    from showdown_bot.eval.accuracy_cap_derisk import DecisionIdComponents, compute_decision_id
    from showdown_bot.eval.room_raw_replay import (
        RequestKind, deduplicate_battle_logs, extract_decisions_from_log,
    )
    glob_dirs = [
        DATA_EVAL / "t4" / "rerun" / "room_raw", DATA_EVAL / "t4" / "room_raw_divergent",
        DATA_EVAL / "t6" / "room_raw", DATA_EVAL / "kaggle-validation" / "room_raw",
    ]
    log_files: list[Path] = []
    for d in glob_dirs:
        log_files += [Path(p) for p in glob.glob(str(d / "**" / "*.log.gz"), recursive=True)]
    manifest_files = [
        DATA_EVAL / "t4" / "rerun" / "t4rerun-run1.jsonl", DATA_EVAL / "t4" / "rerun" / "t4rerun-run2.jsonl",
        DATA_EVAL / "t4" / "rerun" / "t4rerun-prefix.jsonl", DATA_EVAL / "t6" / "t6-run1.jsonl",
        DATA_EVAL / "t6" / "t6-run2.jsonl", DATA_EVAL / "kaggle-validation" / "results.jsonl",
    ]
    dedup_report = deduplicate_battle_logs(
        log_files=sorted(set(log_files), key=str), manifest_files=manifest_files,
        keep_priority=["run1", "run2", "prefix", "kaggle-validation"],
    )
    found: dict[str, object] = {}
    for p in sorted(dedup_report.kept, key=str):
        identity = dedup_report.kept_identities[p]
        for d in extract_decisions_from_log(p):
            if d.kind != RequestKind.MOVE:
                continue
            did = compute_decision_id(DecisionIdComponents(
                seed_base=identity.seed_base, seed_index=identity.seed_index,
                request_hash=d.request_hash, log_prefix_hash=d.log_prefix_hash,
                side=d.side, rqid=d.request.rqid, turn=d.turn,
            ))
            if did in target_decision_ids:
                found[did] = d
    return found


def main() -> None:
    out_path = OUT_DIR / "ambiguous-candidate-diagnostic.json"
    if out_path.exists():
        raise SystemExit(f"BLOCKED: {out_path} already exists -- delete it explicitly first if a genuine re-run is intended.")

    from showdown_bot.battle.decision import heuristic_choose_for_request
    from showdown_bot.battle.decision_trace import DecisionTrace
    from showdown_bot.battle.oracle import DamageOracle
    from showdown_bot.battle.opponent import SpeciesDex
    from showdown_bot.engine.belief.hypotheses import load_spread_book
    from showdown_bot.engine.calc.client import CalcClient
    from showdown_bot.engine.format_config import load_format_config
    from showdown_bot.engine.speed import SpeedOracle
    from showdown_bot.eval.accuracy_cap_derisk import build_request_hash_index

    gate_b_cap4 = json.loads((DATA_EVAL / "accuracy-gate" / "gate-b-report.json").read_text(encoding="utf-8"))
    cap6 = json.loads((OUT_DIR / "cap6-report.json").read_text(encoding="utf-8"))
    cap8 = json.loads((OUT_DIR / "cap8-report.json").read_text(encoding="utf-8"))
    manifest_rows = [
        json.loads(l) for l in (OUT_DIR / "decision-id-manifest.jsonl").read_text(encoding="utf-8").splitlines() if l
    ]
    # fail-closed request_hash -> manifest-row index (same helper as Task 6, same reason: a bare
    # dict comprehension here would silently collapse a duplicated request_hash to one row).
    manifest_by_request_hash = build_request_hash_index(manifest_rows)

    per_cap_exceptions = {
        "cap4": gate_b_cap4["acceptance"]["exceptions"],
        "cap6": cap6["acceptance"]["exceptions"],
        "cap8": cap8["acceptance"]["exceptions"],
    }
    per_cap_target_decision_ids = {
        cap: {manifest_by_request_hash[e["request_hash"]]["decision_id"] for e in exceptions}
        for cap, exceptions in per_cap_exceptions.items()
    }
    per_cap_original_message_by_decision_id = {
        cap: {
            manifest_by_request_hash[e["request_hash"]]["decision_id"]: e["exception"]
            for e in exceptions
        }
        for cap, exceptions in per_cap_exceptions.items()
    }
    all_target_decision_ids = set().union(*per_cap_target_decision_ids.values())
    print(f"re-running {len(all_target_decision_ids)} distinct ambiguous decisions across cap4/6/8 for classification...")
    decisions_by_did = _decisions_by_decision_id(all_target_decision_ids)

    book = load_spread_book(load_format_config(FORMAT_ID).meta_path("default_spreads"))
    calc = CalcClient()
    speed_oracle = SpeedOracle(stats_backend=calc.backend)
    dex = SpeciesDex(calc.backend)

    report: dict = {"per_cap": {}}
    for cap_label, cap_value in [("cap4", 4), ("cap6", 6), ("cap8", 8)]:
        os.environ["SHOWDOWN_ACCURACY_MODE"] = "1"
        os.environ["SHOWDOWN_ACCURACY_BRANCH_CAP"] = str(cap_value)
        cases = []
        for did in sorted(per_cap_target_decision_ids[cap_label]):
            d = decisions_by_did.get(did)
            original_message = per_cap_original_message_by_decision_id[cap_label][did]
            if d is None:
                cases.append({
                    "decision_id": did, "primary_cause": "other_pipeline_error",
                    "label_collision_subtype": None, "companion_flags": [],
                    "rationale": f"decision_id not found in re-extraction; original exception: {original_message}",
                })
                continue

            # Always attempt the live re-run first, regardless of the original exception's type --
            # both branches below need "the new observation" for their rationale (Correction 3).
            classification, is_ambiguous, new_observation = None, False, None
            try:
                trace = DecisionTrace()
                heuristic_choose_for_request(
                    d.request, state=copy.deepcopy(d.state), book=book, our_side=d.side,
                    calc=calc, oracle=DamageOracle(calc), speed_oracle=speed_oracle, dex=dex, trace=trace,
                )
                classification, is_ambiguous = _classify_from_trace(trace)
                new_observation = (
                    f"re-run produced a genuinely ambiguous trace (would classify as "
                    f"{classification.primary_cause})" if is_ambiguous
                    else "re-run resolved to exactly ONE match"
                )
            except Exception as exc:  # noqa: BLE001
                new_observation = f"re-run raised {type(exc).__name__}: {exc}"

            # Correction 3: a structural ambiguity classification is only permitted when the
            # ORIGINAL exception is confirmed to come from _chosen_candidate's own ambiguous/
            # no-match RuntimeError paths -- a re-run that coincidentally looks ambiguous does
            # not, by itself, prove that was the original decision's real exclusion cause.
            if not _original_exception_is_chosen_candidate_ambiguity(original_message):
                cases.append({
                    "decision_id": did, "primary_cause": "other_pipeline_error",
                    "label_collision_subtype": None, "companion_flags": [],
                    "rationale": f"original exception is not a _chosen_candidate ambiguity/"
                                 f"no-match RuntimeError (original: {original_message!r}); "
                                 f"{new_observation} -- not treated as a reproducible structural "
                                 f"ambiguity regardless of the re-run's own outcome.",
                })
                continue

            if not is_ambiguous:
                cases.append({
                    "decision_id": did, "primary_cause": "other_pipeline_error",
                    "label_collision_subtype": None, "companion_flags": [],
                    "rationale": f"original exception confirmed as a _chosen_candidate ambiguity/"
                                 f"no-match RuntimeError, but did not reproduce on re-run "
                                 f"({new_observation}); original exception: {original_message}",
                })
                continue

            cases.append({
                "decision_id": did,
                "primary_cause": classification.primary_cause,
                "label_collision_subtype": classification.label_collision_subtype,
                "chosen_candidate_missing_subreason": classification.chosen_candidate_missing_subreason,
                "companion_flags": sorted(classification.companion_flags),
            })
        os.environ.pop("SHOWDOWN_ACCURACY_MODE", None)
        os.environ.pop("SHOWDOWN_ACCURACY_BRANCH_CAP", None)
        report["per_cap"][cap_label] = {"count": len(cases), "cases": cases}
        primary_causes = {}
        for c in cases:
            primary_causes[c["primary_cause"]] = primary_causes.get(c["primary_cause"], 0) + 1
        print(f"{cap_label}: classified {len(cases)} cases -- primary_cause breakdown: {primary_causes}")

    try:
        calc.close()
    except Exception:  # noqa: BLE001
        pass

    # --- overlap by decision_id across caps ---
    ids_by_cap = {
        cap: {c["decision_id"] for c in report["per_cap"][cap]["cases"]}
        for cap in ("cap4", "cap6", "cap8")
    }
    report["overlap"] = {
        "cap4_only": sorted(ids_by_cap["cap4"] - ids_by_cap["cap6"] - ids_by_cap["cap8"]),
        "cap6_only": sorted(ids_by_cap["cap6"] - ids_by_cap["cap4"] - ids_by_cap["cap8"]),
        "cap8_only": sorted(ids_by_cap["cap8"] - ids_by_cap["cap4"] - ids_by_cap["cap6"]),
        "all_three": sorted(ids_by_cap["cap4"] & ids_by_cap["cap6"] & ids_by_cap["cap8"]),
    }

    out_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
