"""I8-B Task B1 — the decision-profile sidecar: bytes, field set, off by default.

Design `docs/superpowers/specs/2026-07-16-champions-i8-latency-design.md` (Rev. 11) §2.4.
B1 owns the WRITER and the exact-closed field set. The semantic rules on top of it are
B2's `validate_decision_profile_row`.

Mirrors `eval/opp_mega_trace.py`'s proven byte contract exactly:
  open(..., "a", encoding="utf-8", newline="") + json.dumps(sort_keys=True,
  separators=(",", ":")) + "\\n"

The raw-bytes assertion is not pedantry. The I7b-C slice shipped a "determinism" test
that passed on the very platform producing CRLF, because it read the file back in text
mode and universal newlines translated "\\r\\n" -> "\\n" before the assertion ever saw it.
"""

from __future__ import annotations

import json
import pathlib
import re

import pytest

from showdown_bot.eval.decision_profile import (
    PROFILE_ROW_FIELDS,
    SCHEMA_VERSION,
    DecisionProfileError,
    DecisionProfileWriter,
    profile_manifest_hash,
    writer_from_env,
)


ARM = "arm-01"
CFG_HASH = "0123456789abcdef"


def _manifest() -> dict:
    """The run's profile manifest. B1 reads only what the per-row validator needs;
    C1 builds the full thing.

    It does NOT state its own hash: a manifest carrying a digest of itself cannot be
    hashed consistently. The row's profile_manifest_hash is computed FROM this (§2.7).
    """
    return {
        "arms": {
            ARM: {
                "effective_config_hash": CFG_HASH,
                "warmup": 0,
                "lifecycle": {
                    "calc_backend": "per_rep",
                    "damage_oracle": "per_rep",
                    "speed_oracle": "per_rep",
                    "species_dex": "per_rep",
                    "contexts_and_variants": "per_rep",
                },
            }
        },
    }


def _writer(path) -> DecisionProfileWriter:
    return DecisionProfileWriter(str(path), manifest=_manifest())


def _row(**over) -> dict:
    """A structurally complete AND semantically valid row: the writer runs the full
    per-row validator, so a row that is merely field-complete is not enough."""
    row = {
        "schema_version": SCHEMA_VERSION,
        "source": "microprofile",
        "battle_id": None,
        "decision_index": None,
        "arm_id": ARM,
        "rep": 0,
        "config_id": "cfg",
        "format_id": "gen9championsvgc2026regma",
        "git_sha": "deadbeef",
        "config_hash": CFG_HASH,
        "schedule_hash": None,
        "profile_manifest_hash": profile_manifest_hash(_manifest()),
        "calc_backend": "persistent",
        "backend_class": "clean_cold",
        "cache_class": "cold",
        "damage_cache_size_at_rep_start": 0,
        "speed_cache_size_at_rep_start": 0,
        "dex_cache_size_at_rep_start": 0,
        "spawn_count_before": 0,
        "transport_retried": False,
        "timer_scope": "score_evaluated_variants",
        "measured_ms": 12.5,
        "damage_batch_calls": 1,
        "planned_damage_batches": 1,
        "implicit_damage_batches": 0,
        "stats_batch_calls": 0,
        "types_batch_calls": 0,
        "transport_calls": 1,
        "transport_attempts": 1,
        "spawn_calls": 1,
        "requests_total": 4,
        "requests_unique": 4,
        "cache_hits": 0,
        "n_candidates": 12,
        "n_responses": 3,
        "n_mega_twins": 2,
        "n_branches": 2,
        "n_worlds": 1,
        "depth2_frontier": 0,
        "foe_mega_active": True,
        "outcome": "ok",
    }
    row.update(over)
    return row


# --------------------------------------------------------------------------
# the field set is the design's, exactly
# --------------------------------------------------------------------------


def test_the_field_set_is_exactly_the_designs_41_fields():
    # 41. Two earlier counts were wrong for the same reason a level apart: the design
    # declares config_id, format_id and git_sha on ONE table row, and a parse that took
    # the first backticked name per row silently dropped two mandatory provenance fields
    # -- in the module AND in the test that was meant to catch it.
    assert len(PROFILE_ROW_FIELDS) == 41
    for f in ("config_id", "format_id", "git_sha"):
        assert f in PROFILE_ROW_FIELDS


def _design_field_table() -> list[str]:
    """The field names of design §2.4's table, read from the design itself."""
    spec = (
        pathlib.Path(__file__).resolve().parents[2]
        / "docs/superpowers/specs/2026-07-16-champions-i8-latency-design.md"
    )
    lines = spec.read_text(encoding="utf-8").split("\n")
    start = next(i for i, l in enumerate(lines) if "Field set (exact, closed)" in l)
    end = next(i for i, l in enumerate(lines) if l.startswith("**Emission point"))
    # EVERY backticked name in the FIELD cell, not just the first. The design declares
    # three fields on one row -- "| `config_id`, `format_id`, `git_sha` | str | ..." -- and
    # a first-name-only parse dropped two of them. The guard originally shared that bug
    # with the code it was guarding, so it certified the wrong field set.
    names: list[str] = []
    for i in range(start, end):
        if not lines[i].startswith("| `"):
            continue
        names.extend(re.findall(r"`([a-z_0-9]+)`", lines[i].split("|")[1]))
    return names


def test_the_field_set_matches_the_design_table_exactly():
    """The module's field set is the DESIGN's, membership and order.

    The design is the contract and this is the executable form of "derived, not
    transcribed". Hand-transcription is what dropped config_id above, and what the
    design's own §9 records four separate revisions doing to four different lists.
    If this test ever fails, the module and the approved design disagree about what a
    row is -- which is a defect in one of them, never a reason to loosen the test.
    """
    design = _design_field_table()
    assert list(PROFILE_ROW_FIELDS) == design


def test_a_structurally_complete_row_round_trips():
    assert set(_row()) == set(PROFILE_ROW_FIELDS)


# --------------------------------------------------------------------------
# off by default
# --------------------------------------------------------------------------


def test_writer_is_off_by_default():
    # Unset env -> no writer, no file, byte-identical to every prior run.
    assert writer_from_env({}) is None


def test_writer_is_off_when_the_var_is_empty():
    assert writer_from_env({"SHOWDOWN_DECISION_PROFILE_OUT": ""}) is None


def test_writer_is_on_only_when_the_var_names_a_path(tmp_path):
    out = tmp_path / "profile.jsonl"
    w = writer_from_env({"SHOWDOWN_DECISION_PROFILE_OUT": str(out)})
    assert isinstance(w, DecisionProfileWriter)
    assert not out.exists(), "constructing a writer must not create the file"


def test_enabling_it_refuses_to_append_onto_an_existing_runs_rows(tmp_path):
    # Same fail-closed rule the opp-mega sidecar uses: interleaving two runs into one
    # file that later reads as a single run is a provenance defect, and this file is
    # provenance.
    out = tmp_path / "profile.jsonl"
    out.write_bytes(b'{"schema_version":1}\n')
    with pytest.raises(DecisionProfileError):
        writer_from_env({"SHOWDOWN_DECISION_PROFILE_OUT": str(out)})


def test_an_existing_but_empty_file_is_accepted(tmp_path):
    out = tmp_path / "profile.jsonl"
    out.write_bytes(b"")
    assert writer_from_env({"SHOWDOWN_DECISION_PROFILE_OUT": str(out)}) is not None


# --------------------------------------------------------------------------
# bytes
# --------------------------------------------------------------------------


def test_rows_are_LF_only_as_raw_bytes(tmp_path):
    out = tmp_path / "profile.jsonl"
    w = _writer(out)
    w.write(_row())
    w.write(_row(rep=1, cache_class="cold"))

    raw = out.read_bytes()  # BYTES: a text-mode read hides CRLF on the platform that writes it
    assert b"\r\n" not in raw
    assert raw.endswith(b"}\n")
    assert raw.count(b"\n") == 2


def test_rows_are_key_sorted_and_compact(tmp_path):
    out = tmp_path / "profile.jsonl"
    _writer(out).write(_row())

    line = out.read_bytes().decode("utf-8").rstrip("\n")
    assert line == json.dumps(json.loads(line), sort_keys=True, separators=(",", ":"))
    assert ", " not in line and '": ' not in line


def test_the_same_row_serialises_byte_identically_regardless_of_insertion_order(tmp_path):
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    forward = _row()
    reversed_order = {k: forward[k] for k in reversed(list(forward))}

    _writer(a).write(forward)
    _writer(b).write(reversed_order)

    assert a.read_bytes() == b.read_bytes()


def test_writes_append_rather_than_truncate(tmp_path):
    out = tmp_path / "profile.jsonl"
    w = _writer(out)
    w.write(_row(rep=0))
    w.write(_row(rep=1))
    assert len(out.read_bytes().splitlines()) == 2


# --------------------------------------------------------------------------
# the exact-closed field set is enforced ON WRITE
# --------------------------------------------------------------------------


def test_a_missing_field_is_rejected(tmp_path):
    row = _row()
    del row["spawn_count_before"]
    with pytest.raises(DecisionProfileError):
        _writer(tmp_path / "p.jsonl").write(row)


def test_an_unknown_field_is_rejected(tmp_path):
    # Exact-closed, not merely "required": an unknown key means the writer and the
    # reader disagree about the schema, which is how a sidecar silently grows a
    # field nothing validates.
    with pytest.raises(DecisionProfileError):
        _writer(tmp_path / "p.jsonl").write(_row(surprise=1))


def test_a_rejected_row_writes_no_bytes(tmp_path):
    out = tmp_path / "p.jsonl"
    with pytest.raises(DecisionProfileError):
        _writer(out).write(_row(surprise=1))
    assert not out.exists() or out.read_bytes() == b""


def test_the_writer_runs_the_FULL_validator_not_just_the_field_check(tmp_path):
    """A field-complete but semantically invalid row must never reach the file.

    The design makes this the per-row tier's contract: the validator runs at every write,
    inside the writer, and an invalid row raises rather than being emitted. B1's first cut
    called only the field check, which would have left every rule in
    validate_decision_profile_row enforced by nobody at write time -- the same defect as a
    validation tier nobody invokes (§9 entry 52).

    This row has all 39 fields and a broken arithmetic invariant.
    """
    out = tmp_path / "p.jsonl"
    row = _row(damage_batch_calls=9)  # != planned + implicit

    with pytest.raises(DecisionProfileError):
        _writer(out).write(row)
    assert not out.exists() or out.read_bytes() == b""


def test_a_live_writer_needs_no_manifest(tmp_path):
    # A live row has no arm and no manifest to resolve against, so a live run's writer is
    # constructed without one -- and its rows must still be fully validated.
    out = tmp_path / "p.jsonl"
    live = _row(
        source="live", battle_id="b0", decision_index=4, arm_id=None, rep=None,
        schedule_hash="aabbccdd11223344", profile_manifest_hash=None,
        timer_scope="agent_choose", cache_class=None,
        damage_cache_size_at_rep_start=None, speed_cache_size_at_rep_start=None,
        dex_cache_size_at_rep_start=None,
    )
    DecisionProfileWriter(str(out), manifest=None).write(live)
    assert out.read_bytes().endswith(b"}\n")
