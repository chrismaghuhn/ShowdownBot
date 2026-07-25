"""Bundle contract §15 gate 9 — `candidate_key` byte round-trip and non-reserialization.

The Plan F coverage audit found gate 9 **MISSING** while the plan claimed it "existing",
citing `test_a1_canonicalize.py`. That file only tests the generic `dumps()` serializer
against the JCS vectors and has no relation to `candidate_key` at all. Nothing anywhere
compared a source row's key bytes to the exported row's, or asserted non-reserialization.

Gate 9 has two halves and they need different tests:

1. Byte round-trip on real data -> `test_candidate_key_bytes_round_trip_from_source_to_bundle`.
2. "the exporter never re-serializes its inner JSON" (§7.3.2) -> that half is
   **invisible on the committed fixtures**: every real key holds only strings, ints,
   nulls and bools with already-sorted member names, so a JCS re-serialization would
   reproduce them byte-for-byte and test 1 would stay green through the very defect the
   gate exists to catch. `test_exporter_never_reserializes_candidate_key_inner_json`
   supplies the discriminating case instead.
"""

# ruff: noqa: S101 -- pytest assertion rewriting needs bare `assert`, matches every
# sibling file under tests/python/.
from __future__ import annotations

import copy
import json

from conftest import STUDIO_ROOT  # type: ignore[import-not-found]

from showdownbot_studio_exporter.canonicalize import dumps  # type: ignore[import-not-found]
from showdownbot_studio_exporter.export_decisions import (  # type: ignore[import-not-found]
    _is_canonical_candidate_key,
    export_decisions_jsonl,
    load_trace_rows,
)


FIX01_TRACE = STUDIO_ROOT / "fixtures" / "viewer-v0" / "sources" / "fixture-01" / "decision_trace.jsonl"


def _exported_rows(trace_rows: list[dict]) -> list[dict]:
    blob, _, _ = export_decisions_jsonl(trace_rows)
    return [json.loads(line) for line in blob.decode("utf-8").splitlines()]


def test_candidate_key_bytes_round_trip_from_source_to_bundle():
    """Gate 9, first half: every `candidate_key` reaches the bundle byte-identically.

    Compares UTF-8 bytes, not `==` on str, and pins the per-decision/per-rank position of
    each key so a key that survives intact but lands on the wrong candidate still fails.
    """
    source_rows = load_trace_rows(FIX01_TRACE)
    exported = {row["decision_index"]: row for row in _exported_rows(source_rows)}

    compared = 0
    for src in source_rows:
        out = exported[src["decision_index"]]
        src_cands = src.get("candidates") or []
        assert len(out["candidates"]) == len(src_cands)

        for src_cand, out_cand in zip(src_cands, out["candidates"], strict=True):
            src_key = src_cand.get("candidate_key")
            out_key = out_cand.get("candidate_key")
            if src_key is None:
                assert out_key is None
                continue
            assert out_key is not None
            assert out_key.encode("utf-8") == src_key.encode("utf-8")
            assert out_cand["rank"] == src_cand["rank"]
            compared += 1

        src_chosen = src.get("chosen_candidate_key")
        out_chosen = out.get("chosen_candidate_key")
        if src_chosen is None:
            assert out_chosen is None
        else:
            assert out_chosen is not None
            assert out_chosen.encode("utf-8") == src_chosen.encode("utf-8")
            compared += 1

    # Guard against a silently empty sweep: fixture-01 carries 3 candidate keys plus the
    # chosen key on its one regular_turn row. A refactor that drops keys from the fixture
    # must fail here rather than turn this test into a no-op.
    assert compared >= 4


def test_exporter_never_reserializes_candidate_key_inner_json():
    """Gate 9, second half (§7.3.2): the inner JSON is carried verbatim, never re-emitted.

    `candidate_key` is an opaque string whose *content* is itself JSON. The bundle is
    canonicalized with RFC 8785, whose number formatting is shortest-round-trip: as a JSON
    **number** `1.0` becomes `1`. So an exporter that ever parsed the key and re-emitted it
    through the bundle serializer would rewrite `1.0` -> `1` inside the key and destroy
    candidate identity, which the producer byte-compares on read.

    The committed fixtures cannot show this -- their keys hold no floats. This test injects
    one into an otherwise-real row and asserts the float survives.
    """
    rows = load_trace_rows(FIX01_TRACE)
    target = next(r for r in rows if (r.get("candidates") or []))

    # Canonical per the exporter's own check (Python renders float 1.0 as "1.0"), member
    # names already sorted -- so the row passes `non_canonical_candidate_key` and the test
    # exercises serialization rather than the canonicality guard.
    float_key = '{"slots":[{"kind":"move","target":1.0}],"version":2}'
    assert _is_canonical_candidate_key(float_key)

    # The discriminating premise, asserted rather than assumed: re-serializing this key's
    # inner JSON through the bundle serializer DOES change its bytes. If a future rfc8785
    # or policy change made JCS preserve `1.0`, this test would silently stop discriminating
    # -- so it fails loudly here instead.
    assert dumps(json.loads(float_key)) != float_key.encode("utf-8")

    mutated = copy.deepcopy(target)
    mutated["candidates"] = [dict(mutated["candidates"][0], candidate_key=float_key)]
    mutated["chosen_candidate_key"] = float_key
    mutated["chosen_candidate_id"] = mutated["candidates"][0]["candidate_id"]
    mutated["chosen_rank"] = mutated["candidates"][0]["rank"]

    blob, _, _ = export_decisions_jsonl([mutated])

    # Assert on the raw bundle bytes, not on a json.loads() round-trip: decoding would hide
    # the very rewrite under test if it happened at the string level.
    assert b'{\\"slots\\":[{\\"kind\\":\\"move\\",\\"target\\":1.0}],\\"version\\":2}' in blob

    out = json.loads(blob.decode("utf-8").splitlines()[0])
    assert out["candidates"][0]["candidate_key"].encode("utf-8") == float_key.encode("utf-8")
    assert out["chosen_candidate_key"].encode("utf-8") == float_key.encode("utf-8")
