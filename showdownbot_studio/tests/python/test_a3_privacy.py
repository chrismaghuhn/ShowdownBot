from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import pytest

from conftest import STUDIO_ROOT, SYNTHETIC, read_normalized_bytes

from showdownbot_studio_exporter.export_battle import export_battle_jsonl, read_battle_log
from showdownbot_studio_exporter.privacy import PRIVACY_PROFILE, pseudonymize_request_payload


PRIVACY_LOG = SYNTHETIC / "privacy_leak.log"
FIXTURE10_LOG = STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources" / "fixture-10" / "battle.log"
FIXTURE01_BUNDLE = STUDIO_ROOT / "fixtures" / "viewer-v0" / "bundles" / "fixture-01"


def test_privacy_profile_constant():
    assert PRIVACY_PROFILE["profile"] == "portable-pseudonymous-v1"


def test_fixture10_request_payload_is_json_parsed():
    from showdownbot_studio_exporter.privacy import parse_request_line

    lines = read_battle_log(FIXTURE10_LOG)
    req_lines = [ln for ln in lines if ln.startswith("|request|")]
    assert req_lines
    payload = parse_request_line(req_lines[0])
    assert isinstance(payload, dict)
    assert payload["side"]["name"] == "LeakPlayerOne"


def test_fixture10_request_side_name_pseudonymized():
    from showdownbot_studio_exporter.privacy import parse_request_line

    lines = read_battle_log(FIXTURE10_LOG)
    payload = parse_request_line(next(ln for ln in lines if ln.startswith("|request|")))
    cleaned = pseudonymize_request_payload(payload)
    assert cleaned["side"]["name"] == "p1"
    battle_bytes = export_battle_jsonl(lines)
    assert b"LeakPlayerOne" not in battle_bytes


def test_fixture10_request_nickname_stripped_or_pseudonymized():
    lines = read_battle_log(FIXTURE10_LOG)
    battle_bytes = export_battle_jsonl(lines)
    assert b"NickLeak" not in battle_bytes


def test_fixture10_other_literals_absent():
    lines = read_battle_log(FIXTURE10_LOG)
    battle_bytes = export_battle_jsonl(lines)
    for needle in (b"http://", b"LeakPlayerTwo", b"999", b"C:\\Users\\fixture\\leak.log"):
        assert needle not in battle_bytes


def test_fixture10_source_unchanged():
    before = hashlib.sha256(FIXTURE10_LOG.read_bytes()).hexdigest()
    export_battle_jsonl(read_battle_log(FIXTURE10_LOG))
    after = hashlib.sha256(FIXTURE10_LOG.read_bytes()).hexdigest()
    assert before == after


def test_privacy_leak_matches_fixture10_source():
    # Normalize line endings: PRIVACY_LOG lives under tests/python/synthetic/, which
    # .gitattributes does not force to eol=lf (unlike fixtures/viewer-v0/**), so
    # core.autocrlf can check it out as CRLF while FIXTURE10_LOG stays LF on the same
    # machine. Same content, checkout-dependent bytes -- compare normalized.
    assert read_normalized_bytes(PRIVACY_LOG) == read_normalized_bytes(FIXTURE10_LOG)


def test_fixture01_no_real_player_name_leaks_in_any_bundle_file():
    """Bundle contract §15 gate 19 (second half) / §12.2: "Reversible name map: never
    written to the bundle." The audit found this checked only for battle.jsonl, one file,
    for fixture-10. fixture-01's own source carries a real synthetic player name
    ("SyntheticP1", the |player| line) that gate 19 requires stays out of EVERY exported
    file, not just battle.jsonl -- extends the scope across all files of the real,
    already-committed bundle/fixture-01 export.
    """
    leaking = []
    for path in sorted(FIXTURE01_BUNDLE.iterdir()):
        if b"SyntheticP1" in path.read_bytes():
            leaking.append(path.name)
    assert leaking == []


def test_fixture01_seat_pseudonyms_consistent_across_bundle_files():
    """Bundle contract §15 gate 19 (first half): "Every exported file uses the same seat
    pseudonyms." battle.jsonl's per-event side labels and manifest.json's own
    source_provenance.our_side are drawn from the identical {"p1", "p2"} pseudonym set, and
    our_side (the side the bot played) is one of the labels battle.jsonl actually uses --
    proven by cross-referencing both real, already-committed files of the same bundle
    rather than checking either file in isolation.
    """
    manifest = json.loads((FIXTURE01_BUNDLE / "manifest.json").read_text(encoding="utf-8"))
    our_side = manifest["source_provenance"]["our_side"]
    assert our_side in ("p1", "p2")

    battle_sides: set[str] = set()
    for line in (FIXTURE01_BUNDLE / "battle.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row.get("side"):
            battle_sides.add(row["side"])
        for nested in ("pokemon", "target"):
            if row.get(nested) and row[nested].get("side"):
                battle_sides.add(row[nested]["side"])
    assert battle_sides, "battle.jsonl carried no side identifiers to compare"
    assert battle_sides <= {"p1", "p2"}
    assert our_side in battle_sides  # same pseudonym set names the same real side


def test_log_event_raw_field_never_emitted_though_it_is_populated():
    """Bundle contract §15 gate 21 (second half) / §12.2: "LogEvent.raw: dropped; it is the
    verbatim protocol line and re-leaks names." The audit found this half of gate 21 had
    zero coverage anywhere (only the nickname half was checked). Proven both ways: the
    LogEvent the real parser produces for fixture-10's leaking |switch| line DOES carry a
    populated .raw (so excluding it downstream is a deliberate omission, not a field that
    never existed), and export_battle_jsonl's own output never emits a "raw" key for any
    row, nor does the verbatim line (with its leaking nickname) ever appear byte-for-byte
    in the exported bytes.
    """
    from showdown_bot.engine.log_parser import parse_log_line
    from showdown_bot.protocol.messages import parse_message

    lines = read_battle_log(FIXTURE10_LOG)
    switch_line = next(ln for ln in lines if ln.startswith("|switch|"))
    msg = parse_message(switch_line)
    event = parse_log_line(msg.prefix, msg.args, raw=switch_line)
    assert event.raw == switch_line  # the field exists and is populated

    battle_bytes = export_battle_jsonl(lines)
    for line in battle_bytes.decode("utf-8").splitlines():
        row = json.loads(line)
        assert "raw" not in row
    assert switch_line.encode("utf-8") not in battle_bytes
