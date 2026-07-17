"""I8-B Task B4 — ONE encoder, used by both the manifest hash and the fixture hash.

Design §2.7. The rules are not stylistic; each pins a defect the design shipped and had to
withdraw (§9 entries 33-37):

  sort only what has NO order
      set/frozenset -> sorted, because a set has no order to preserve and sorting is the
          only deterministic option;
      list/tuple    -> ORDER PRESERVED, because order is either meaningful or at minimum
          not ours to discard;
      dict          -> key-sorted, because every dict here is a keyed lookup;
      dataclass     -> fields name-sorted, values recursed;
      BaseModel     -> model_dump with pinned options, then recursed;
      anything else -> raise. Fail closed on the TYPE, never on a forgotten field name.

The asymmetry that justifies it: for a fixture IDENTITY, over-discrimination costs a
comparison; under-discrimination corrupts every claim built on it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from showdown_bot.eval.decision_profile import (
    DecisionProfileError,
    encode,
    fixture_input_hash,
    profile_manifest_hash,
)
from showdown_bot.engine.belief.hypotheses import SpeciesSpreads, SpreadBook, SpreadPreset


# ==========================================================================
# ordering: sort only what has no order
# ==========================================================================


def test_a_set_is_sorted_because_it_has_no_order_to_preserve():
    # moves/move_names are genuinely set[str] (engine/state.py:66-67). json.dumps cannot
    # serialise a set at all, and any str() fallback is iteration-order dependent.
    assert encode({"m": {"b", "a"}}) == encode({"m": {"a", "b"}}) == {"m": ["a", "b"]}


def test_a_list_keeps_its_order():
    # THE Rev. 8 defect: sorting a list destroys meaning. items[0] is the default
    # assumption; legal_actions order is the first-wins tie-break.
    assert encode(["b", "a"]) == ["b", "a"]
    assert encode(["b", "a"]) != encode(["a", "b"])


def test_a_tuple_keeps_its_order_and_encodes_like_a_list():
    assert encode(("b", "a")) == ["b", "a"]


def test_a_dict_is_key_sorted():
    assert list(encode({"z": 1, "a": 2})) == ["a", "z"]


def test_dict_key_order_does_not_change_the_encoding():
    assert encode({"z": 1, "a": 2}) == encode({"a": 2, "z": 1})


# ==========================================================================
# types
# ==========================================================================


def test_none_is_preserved_never_elided():
    # An absent key and a null key are different states.
    assert encode({"x": None}) == {"x": None}


def test_a_float_keeps_full_precision():
    assert encode(0.1 + 0.2) == repr(0.1 + 0.2)


def test_bool_is_not_silently_an_int():
    assert encode({"b": True}) == {"b": True}


def test_an_unhandled_type_fails_closed():
    with pytest.raises(DecisionProfileError):
        encode(object())


def test_a_nested_unhandled_type_fails_closed():
    with pytest.raises(DecisionProfileError):
        encode({"ok": 1, "bad": [1, object()]})


# ==========================================================================
# dataclasses: every field, recursively -- never a hand-written list
# ==========================================================================


@dataclass
class _Leaf:
    b: int
    a: str


@dataclass
class _Nest:
    leaf: _Leaf
    items: list[str] = field(default_factory=list)


def test_a_dataclass_encodes_every_field_name_sorted():
    assert encode(_Leaf(b=1, a="x")) == {"a": "x", "b": 1}


def test_a_dataclass_recurses():
    assert encode(_Nest(leaf=_Leaf(b=1, a="x"), items=["z", "y"])) == {
        "items": ["z", "y"],  # order preserved
        "leaf": {"a": "x", "b": 1},
    }


def test_a_new_dataclass_field_is_picked_up_automatically():
    # "derived, not transcribed": the encoder enumerates dataclasses.fields(), so a field
    # added later cannot be silently dropped the way a hand-written list drops one.
    @dataclass
    class _Grown:
        a: int
        surprise: str = "new"

    assert encode(_Grown(a=1)) == {"a": 1, "surprise": "new"}


# ==========================================================================
# the real spread DTOs -- the shapes §9 entries 33/34 got wrong
# ==========================================================================


def _preset(items):
    return SpreadPreset(nature="Jolly", evs={"spe": 252}, items=items)


def test_items_order_changes_the_encoding():
    # default_spreads.yaml:12 -- "items: candidate held items (first is the default
    # assumption)" -- and production reads preset.items[0] (hypotheses.py:109,
    # team/spreads.py:91). Sorting [Life Orb, Choice Specs, Focus Sash] silently changes
    # the assumed item to Choice Specs.
    a = encode(_preset(["Choice Scarf", "Life Orb"]))
    b = encode(_preset(["Life Orb", "Choice Scarf"]))
    assert a != b
    assert a["items"] == ["Choice Scarf", "Life Orb"]


def test_offense_and_defense_are_not_collapsed():
    # SpeciesSpreads carries BOTH (hypotheses.py:27-33): offense drives Mega speed
    # (engine/speed.py:176), defense drives our own item truth (team/spreads.py:89-91).
    o, d = _preset(["Life Orb"]), _preset(["Leftovers"])
    assert encode(SpeciesSpreads(offense=o, defense=d)) != encode(
        SpeciesSpreads(offense=d, defense=o)
    )


def test_a_spread_book_encodes_default_and_species():
    book = SpreadBook(default=SpeciesSpreads(offense=_preset(["Life Orb"]), defense=_preset([])))
    out = encode(book)
    assert set(out) == {"default", "species"}
    assert out["default"]["offense"]["items"] == ["Life Orb"]


# ==========================================================================
# ONE encoder: the manifest hash and the fixture hash share it
# ==========================================================================


def test_the_manifest_hash_uses_the_same_encoder():
    m = {"arms": {"a": {"warmup": 0, "items": ["b", "a"]}}}
    # A second canonicalisation would be free to disagree; there is only one.
    import hashlib
    import json as _json

    expected = hashlib.sha1(
        _json.dumps(encode(m), separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:16]
    assert profile_manifest_hash(m) == expected


def test_the_fixture_hash_uses_the_same_encoder():
    inputs = {"legal_actions": ["a", "b"], "book": _preset(["Life Orb"])}
    import hashlib
    import json as _json

    expected = hashlib.sha1(
        _json.dumps(encode(inputs), separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:16]
    assert fixture_input_hash(inputs) == expected


def test_the_fixture_hash_is_order_sensitive_where_order_means_something():
    # legal_actions order IS the first-wins tie-break (mega_scoring.py:184-198, a prior
    # Codex I7a-B merge-blocker): two enumerations with equal membership and different
    # order choose DIFFERENT actions, so they must not share a hash.
    assert fixture_input_hash({"legal_actions": ["a", "b"]}) != fixture_input_hash(
        {"legal_actions": ["b", "a"]}
    )


def test_the_fixture_hash_is_order_insensitive_where_order_means_nothing():
    assert fixture_input_hash({"moves": {"a", "b"}}) == fixture_input_hash({"moves": {"b", "a"}})


def test_both_hashes_are_16_hex_chars():
    # make_config_hash's convention (eval/result_jsonl.py:69).
    for h in (profile_manifest_hash({"arms": {}}), fixture_input_hash({"x": 1})):
        assert len(h) == 16 and all(c in "0123456789abcdef" for c in h)
