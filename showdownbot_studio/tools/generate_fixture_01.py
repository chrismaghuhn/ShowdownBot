"""Generate synthetic-coherent fixture-01 sources."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

STUDIO = Path(__file__).resolve().parents[1]
OUT = STUDIO / "fixtures" / "viewer-v0" / "sources" / "fixture-01"


def _canon(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _req_hash(payload: dict) -> str:
    return hashlib.sha256(_canon(payload).encode()).hexdigest()


def _obs_hash(state: dict, req: dict) -> str:
    return hashlib.sha256(_canon({"state": state, "request": req}).encode()).hexdigest()


S = {
    "battle_id": "synthetic00000001",
    "run_id": "syntheticrun00001",
    "git_sha": "unknown",
    "config_hash": "bbbbbbbbbbbbbbbb",
    "schedule_hash": "cccccccccccccccc",
    "config_id": "synthetic_fixture",
    "format_id": "gen9championsvgc2026regma",
    "seed_index": 0,
    "our_side": "p1",
}

TRACE_FIELDS = {k: S[k] for k in (
    "battle_id", "git_sha", "config_hash", "schedule_hash", "config_id", "format_id", "seed_index", "our_side",
)}

CAND_KEY = (
    '{"slots":[{"kind":"move","mega_evolve":false,"move_index":1,"target":1,'
    '"target_ident":null,"terastallize":false},{"kind":"pass","mega_evolve":false,'
    '"move_index":null,"target":null,"target_ident":null,"terastallize":false}],'
    '"version":2}'
)

REQ0 = {"teamPreview": True, "side": {"name": "p1", "id": "p1", "pokemon": []}, "rqid": 1}
REQ1 = {
    "forceSwitch": [True, False],
    "side": {"name": "p1", "id": "p1", "pokemon": []},
    "rqid": 2,
    "wait": False,
}
REQ2 = {
    "active": [
        {
            "moves": [
                {"move": "Tackle", "id": "tackle", "pp": 35, "maxpp": 35, "target": "normal", "disabled": False}
            ]
        },
        {},
    ],
    "side": {"name": "p1", "id": "p1", "pokemon": []},
    "rqid": 3,
}

ROWS = [
    {
        "trace_schema_version": "decision-trace-v3",
        **TRACE_FIELDS,
        "decision_index": 0,
        "turn_number": 0,
        "decision_phase": "team_preview",
        "observable_state_hash": _obs_hash({"turn": 0, "field": {}, "sides": {}}, REQ0),
        "request_hash": _req_hash(REQ0),
        "state_summary": {"turn": 0, "field": {}, "sides": {}},
        "actual_choose_string": "/choose team 1234",
        "normalized_action": {"kind": "team_preview", "order": [1, 2, 3, 4]},
        "candidates": [],
        "chosen_candidate_key": None,
        "chosen_candidate_id": None,
        "chosen_rank": None,
        "chosen_tera_slot": None,
        "chosen_mega_slot": None,
        "selection_stage": "team_preview",
        "fallback_reason": None,
        "decision_latency_ms": 1.0,
    },
    {
        "trace_schema_version": "decision-trace-v3",
        **TRACE_FIELDS,
        "decision_index": 1,
        "turn_number": 1,
        "decision_phase": "forced_replacement",
        "observable_state_hash": _obs_hash({"turn": 1, "field": {}, "sides": {}}, REQ1),
        "request_hash": _req_hash(REQ1),
        "state_summary": {"turn": 1, "field": {}, "sides": {}},
        "actual_choose_string": "/choose switch 3, pass",
        "normalized_action": {
            "kind": "joint",
            "slots": [
                {"kind": "switch", "switch_target": "p1pikachu"},
                {"kind": "pass"},
            ],
        },
        "candidates": [
            {
                "candidate_id": "switch",
                "candidate_key": (
                    '{"slots":[{"kind":"switch","mega_evolve":false,"move_index":null,'
                    '"target":null,"target_ident":"p1: Pikachu","terastallize":false},'
                    '{"kind":"pass","mega_evolve":false,"move_index":null,"target":null,'
                    '"target_ident":null,"terastallize":false}],"version":2}'
                ),
                "rank": 0,
                "aggregate_score": 1.0,
            }
        ],
        "chosen_candidate_key": (
            '{"slots":[{"kind":"switch","mega_evolve":false,"move_index":null,'
            '"target":null,"target_ident":"p1: Pikachu","terastallize":false},'
            '{"kind":"pass","mega_evolve":false,"move_index":null,"target":null,'
            '"target_ident":null,"terastallize":false}],"version":2}'
        ),
        "chosen_candidate_id": "switch",
        "chosen_rank": 0,
        "chosen_tera_slot": None,
        "chosen_mega_slot": None,
        "selection_stage": "heuristic",
        "fallback_reason": None,
        "decision_latency_ms": 2.0,
    },
    {
        "trace_schema_version": "decision-trace-v3",
        **TRACE_FIELDS,
        "decision_index": 2,
        "turn_number": 2,
        "decision_phase": "regular_turn",
        "observable_state_hash": _obs_hash({"turn": 2, "field": {}, "sides": {}}, REQ2),
        "request_hash": _req_hash(REQ2),
        "state_summary": {"turn": 2, "field": {}, "sides": {}},
        "actual_choose_string": "/choose move 1 1, pass",
        "normalized_action": {
            "kind": "joint",
            "slots": [
                {
                    "kind": "move",
                    "move_index": 1,
                    "target": 1,
                    "move_id": "tackle",
                    "mega": False,
                    "tera": False,
                    "is_protect": False,
                },
                {"kind": "pass"},
            ],
        },
        "candidates": [
            {
                "candidate_id": "move",
                "candidate_key": CAND_KEY,
                "rank": 0,
                "aggregate_score": 3.5,
            },
            {
                "candidate_id": "pass",
                "candidate_key": (
                    '{"slots":[{"kind":"pass","mega_evolve":false,"move_index":null,'
                    '"target":null,"target_ident":null,"terastallize":false},'
                    '{"kind":"pass","mega_evolve":false,"move_index":null,"target":null,'
                    '"target_ident":null,"terastallize":false}],"version":2}'
                ),
                "rank": 1,
                "aggregate_score": 0.5,
            },
        ],
        "chosen_candidate_key": CAND_KEY,
        "chosen_candidate_id": "move",
        "chosen_rank": 0,
        "chosen_tera_slot": None,
        "chosen_mega_slot": None,
        "selection_stage": "heuristic",
        "fallback_reason": None,
        "decision_latency_ms": 3.0,
    },
]

LOG = [
    ">battle-gen9test",
    "|init|battle",
    "|player|p1|SyntheticP1|1|",
    "|request|" + json.dumps(REQ0, separators=(",", ":"), ensure_ascii=False),
    "|turn|1",
    "|switch|p1a: Pikachu|Pikachu, L50|35/35",
    "|request|" + json.dumps(REQ1, separators=(",", ":"), ensure_ascii=False),
    "|turn|2",
    "|move|p1a: Pikachu|Tackle|p2a: Bulbasaur",
    "|request|" + json.dumps(REQ2, separators=(",", ":"), ensure_ascii=False),
]

RESULT = {
    **{k: S[k] for k in ("battle_id", "config_hash", "schedule_hash", "format_id", "git_sha", "seed_index", "config_id")},
    "run_id": S["run_id"],
    "winner": "hero",
    "dirty": False,
}

MANIFEST = {
    "run_id": S["run_id"],
    "git_sha": S["git_sha"],
    "config_hash": S["config_hash"],
    "schedule_hash": S["schedule_hash"],
    "dirty": False,
    "seed_base": "synthetic_base",
    "panel_hash": "dddddddddddddddd",
}

CONFIG_MANIFEST = {
    "config_hash": S["config_hash"],
    "manifest": {
        "agent": S["config_id"],
        "format_id": S["format_id"],
        "env": {},
    },
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "battle.log").write_text("\n".join(LOG) + "\n", encoding="utf-8", newline="\n")
    trace_lines = [_canon(r) + "\n" for r in ROWS]
    (OUT / "decision_trace.jsonl").write_bytes("".join(trace_lines).encode("utf-8"))
    (OUT / "results.jsonl").write_text(_canon(RESULT) + "\n", encoding="utf-8", newline="\n")
    (OUT / "results.manifest.json").write_text(_canon(MANIFEST) + "\n", encoding="utf-8", newline="\n")
    (OUT / "results.config-manifest.json").write_text(_canon(CONFIG_MANIFEST) + "\n", encoding="utf-8", newline="\n")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
