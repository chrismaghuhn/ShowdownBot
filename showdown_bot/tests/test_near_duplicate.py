# showdown_bot/tests/test_near_duplicate.py
import pytest

from showdown_bot.eval.near_duplicate import (
    species_set, overlap_fraction, find_near_duplicate_flags, load_team_species,
    NearDuplicateFlag, NEAR_DUPLICATE_REVIEW_THRESHOLD,
)


def _packed_mon(species):
    # Minimal but real Showdown packed-format single-mon block: nickname(blank)|species|item|
    # ability|moves|nature|evs -- 7 fields, matching team.spreads._parse_mon's own
    # `len(f) < 7: return None` requirement exactly.
    return f"|{species}|Focus Sash|Levitate|Protect|Careful|0,0,0,0,0,0"


def _packed_team(species_list):
    return "]".join(_packed_mon(s) for s in species_list)


def test_species_set_normalizes_case_and_punctuation():
    # Showdown's own toID rule (matches engine.state.to_id et al.): lowercase, strip everything
    # outside a-z0-9. "Landorus-Therian" and "landorus therian!!" must collapse to the same id,
    # so cosmetic spelling differences never cause a false NEGATIVE (a real duplicate missed
    # because of case/punctuation) -- but a genuine forme difference must NOT collapse, so a
    # false POSITIVE (two different Pokemon treated as the same) never happens either.
    assert species_set(["Landorus-Therian"]) == species_set(["landorus therian!!"])
    assert species_set(["Giratina"]) != species_set(["Giratina-Origin"])
    assert species_set(["Nidoran-M"]) != species_set(["Nidoran-F"])


def test_species_set_collapses_duplicate_entries():
    # Illegal under Showdown's own species clause for a real team, but this is a generic set
    # utility, not a team validator -- duplicate entries must not crash it or double-count.
    assert species_set(["Pikachu", "Pikachu", "Charizard"]) == species_set(["Pikachu", "Charizard"])


def test_species_set_rejects_empty_input():
    # Fail-closed: an empty list is not a valid team's species set (a real team always has 1-6
    # Pokemon). Silently returning frozenset() would let overlap_fraction treat "no data" as "0%
    # overlap with everything" -- a confidently wrong answer for what is actually missing data.
    with pytest.raises(ValueError, match="non-empty"):
        species_set([])


def test_species_set_rejects_a_non_list_input():
    # Type-strictness: a bare string is iterable, so species_set("Pikachu") would otherwise
    # silently iterate its CHARACTERS ('P', 'i', 'k', ...) instead of being rejected as the wrong
    # type entirely -- a real, sneaky bug class this check exists to close.
    with pytest.raises(ValueError, match="must be a list"):
        species_set("Pikachu")
    with pytest.raises(ValueError, match="must be a list"):
        species_set({"Pikachu": 1})
    with pytest.raises(ValueError, match="must be a list"):
        species_set(None)


def test_species_set_rejects_non_string_elements():
    with pytest.raises(ValueError, match="only strings"):
        species_set(["Pikachu", 123])


def test_overlap_fraction_is_jaccard_similarity():
    a = species_set(["A", "B", "C"])
    b = species_set(["A", "B", "D"])
    # intersection={A,B}=2, union={A,B,C,D}=4 -> 2/4, not the overlap-coefficient's 2/3.
    assert overlap_fraction(a, b) == pytest.approx(0.5)


def test_overlap_fraction_rejects_empty_sets():
    # Defense in depth, independent of species_set's own empty-input guard -- this function is
    # public and may be called directly, not only reached via species_set.
    with pytest.raises(ValueError, match="non-empty"):
        overlap_fraction(frozenset(), frozenset({"a"}))


def test_overlap_fraction_rejects_a_non_frozenset_input():
    # Type-strictness: a plain set/list "looks" set-like (supports & and |) but is not the
    # frozenset this function's own contract promises -- reject explicitly rather than silently
    # accepting a mutable set that could be mutated out from under a caller holding a reference.
    with pytest.raises(ValueError, match="frozensets"):
        overlap_fraction({"a", "b"}, frozenset({"a"}))
    with pytest.raises(ValueError, match="frozensets"):
        overlap_fraction(["a", "b"], frozenset({"a"}))


def test_overlap_fraction_rejects_frozensets_containing_non_string_or_empty_elements():
    # Review-fix P1: overlap_fraction only checked that a/b were frozensets, never that their
    # ELEMENTS were strings -- overlap_fraction(frozenset({1}), frozenset({"a"})) silently
    # computed a numeric answer (0.0) over the wrong element type instead of rejecting it.
    with pytest.raises(ValueError, match="non-empty strings"):
        overlap_fraction(frozenset({1}), frozenset({"a"}))
    with pytest.raises(ValueError, match="non-empty strings"):
        overlap_fraction(frozenset({"a", ""}), frozenset({"b"}))


def test_find_near_duplicate_flags_flags_identical_species_sets_of_different_team_ids():
    flags = find_near_duplicate_flags(
        candidate_team_id="holdout_0", candidate_species=["A", "B", "C"],
        reference_teams={"ref_1": ["A", "B", "C"]},
    )
    assert len(flags) == 1
    assert flags[0] == NearDuplicateFlag(
        candidate_team_id="holdout_0", reference_team_id="ref_1",
        overlap_fraction=1.0, shared_species=("a", "b", "c"),
    )


def test_find_near_duplicate_flags_never_flags_a_team_against_itself():
    # reference_teams intentionally includes the candidate's OWN team_id with IDENTICAL species
    # (which would score 1.0, the maximum possible overlap, if compared) -- it must never appear
    # in the result. This is defense in depth: Task 10 keeps the six holdout candidates and the
    # nine reference teams as two genuinely separate dicts precisely so this should never be
    # exercised in production, but this function does not trust that from the outside.
    flags = find_near_duplicate_flags(
        candidate_team_id="holdout_0", candidate_species=["A", "B", "C"],
        reference_teams={"holdout_0": ["A", "B", "C"], "ref_1": ["D", "E", "F"]},
    )
    assert flags == []  # ref_1 has zero overlap; holdout_0 (self) is excluded regardless of overlap


def test_find_near_duplicate_flags_does_not_flag_below_the_threshold():
    flags = find_near_duplicate_flags(
        candidate_team_id="holdout_0", candidate_species=["A", "B", "C"],
        reference_teams={"ref_1": ["A", "D", "E"]},  # intersection={A}=1, union=5 -> 0.2
    )
    assert flags == []


def test_find_near_duplicate_flags_flags_exactly_at_the_threshold():
    flags = find_near_duplicate_flags(
        candidate_team_id="holdout_0", candidate_species=["A", "B", "C"],
        reference_teams={"ref_1": ["A", "B", "D"]},  # intersection=2, union=4 -> exactly 0.5
    )
    assert len(flags) == 1
    assert flags[0].overlap_fraction == pytest.approx(NEAR_DUPLICATE_REVIEW_THRESHOLD)


def test_find_near_duplicate_flags_rejects_an_empty_reference_teams_mapping():
    with pytest.raises(ValueError, match="non-empty"):
        find_near_duplicate_flags(
            candidate_team_id="holdout_0", candidate_species=["A", "B", "C"], reference_teams={},
        )


def test_find_near_duplicate_flags_rejects_an_empty_candidate_team_id():
    with pytest.raises(ValueError, match="non-empty"):
        find_near_duplicate_flags(
            candidate_team_id="", candidate_species=["A", "B", "C"],
            reference_teams={"ref_1": ["A", "B", "C"]},
        )


def test_find_near_duplicate_flags_rejects_a_non_string_candidate_team_id():
    with pytest.raises(ValueError, match="must be a string"):
        find_near_duplicate_flags(
            candidate_team_id=123, candidate_species=["A", "B", "C"],
            reference_teams={"ref_1": ["A", "B", "C"]},
        )


def test_find_near_duplicate_flags_rejects_empty_or_whitespace_only_team_ids():
    # Review-fix P1: candidate_team_id was only checked with bare `not candidate_team_id`
    # (whitespace-only strings are truthy, so "   " slipped through) and reference_teams' keys
    # were only checked for STRING TYPE, never for being non-empty/non-whitespace --
    # reference_teams={"": [...]} passed every existing check and, if its species crossed the
    # threshold, was published as a NearDuplicateFlag with reference_team_id="".
    with pytest.raises(ValueError, match="non-empty and not whitespace-only"):
        find_near_duplicate_flags(
            candidate_team_id="   ", candidate_species=["A", "B", "C"],
            reference_teams={"ref_1": ["A", "B", "C"]},
        )
    with pytest.raises(ValueError, match="non-empty, non-whitespace"):
        find_near_duplicate_flags(
            candidate_team_id="holdout_0", candidate_species=["A", "B", "C"],
            reference_teams={"": ["A", "B", "C"], "  ": ["D", "E", "F"]},
        )


def test_find_near_duplicate_flags_rejects_a_non_dict_reference_teams():
    with pytest.raises(ValueError, match="must be a dict"):
        find_near_duplicate_flags(
            candidate_team_id="holdout_0", candidate_species=["A", "B", "C"],
            reference_teams=["ref_1"],
        )


def test_find_near_duplicate_flags_rejects_reference_teams_with_a_non_string_key():
    with pytest.raises(ValueError, match="must all be non-empty"):
        find_near_duplicate_flags(
            candidate_team_id="holdout_0", candidate_species=["A", "B", "C"],
            reference_teams={123: ["A", "B", "C"]},
        )


def test_find_near_duplicate_flags_returns_a_deterministic_order():
    # reference_teams is a dict built in a DELIBERATELY non-alphabetical insertion order --
    # the returned flags must be sorted by reference_team_id regardless, not by whatever order
    # the caller happened to construct the mapping in.
    reference_teams = {
        "ref_z": ["A", "B", "D"], "ref_a": ["A", "B", "E"], "ref_m": ["A", "B", "F"],
    }
    flags = find_near_duplicate_flags(
        candidate_team_id="holdout_0", candidate_species=["A", "B", "C"],
        reference_teams=reference_teams,
    )
    assert [f.reference_team_id for f in flags] == ["ref_a", "ref_m", "ref_z"]


def test_find_near_duplicate_flags_never_raises_for_a_found_duplicate():
    # DESIGN sec 3.3: manual-review flag only, never an automatic reject. The only exception type
    # this whole module ever raises is ValueError, and only for malformed input (empty/wrong-type
    # species/mappings) -- finding a duplicate is a normal return, not an error path. This test
    # exists so a future change that turns a found flag into a raised exception fails loudly.
    flags = find_near_duplicate_flags(
        candidate_team_id="holdout_0", candidate_species=["A", "B", "C"],
        reference_teams={"ref_1": ["A", "B", "C"]},  # identical -- guaranteed to flag
    )
    assert len(flags) == 1  # returned normally; no exception escaped


def test_load_team_species_parses_a_real_packed_team(tmp_path):
    # Derives species from the REAL sealed packed content, not a caller's bare assertion --
    # reuses this codebase's existing packed-format parsing convention
    # (team.spreads.our_spreads_from_packed), not a new one.
    team_path = tmp_path / "holdout_0.txt"
    team_path.write_text("(export-format .txt content is irrelevant here; only .packed is read)\n", encoding="utf-8")
    packed_path = tmp_path / "holdout_0.packed"
    packed_path.write_text(_packed_team(["Pikachu", "Charizard", "Snorlax"]), encoding="utf-8")

    species = load_team_species(str(team_path), teams_root=".")
    assert species == ["Pikachu", "Charizard", "Snorlax"]


def test_load_team_species_rejects_a_missing_team_file(tmp_path):
    # team.pack.load_packed_team raises FileNotFoundError for a missing .packed sibling --
    # wrapped here as ValueError, matching this module's own single-exception-type contract; no
    # other exception type is ever allowed to escape a public function in this module.
    with pytest.raises(ValueError, match="could not load"):
        load_team_species(str(tmp_path / "does_not_exist.txt"), teams_root=".")


def test_load_team_species_wraps_a_malformed_multiline_packed_file(tmp_path):
    # team.pack.load_packed_team itself raises ValueError for a multi-line packed file -- still
    # re-wrapped here (not left to propagate as-is) so every failure from this function carries
    # the same "could not load packed team at <path>" context, not two different message shapes
    # for what is, from this module's perspective, the same kind of failure.
    team_path = tmp_path / "holdout_0.txt"
    team_path.write_text("irrelevant\n", encoding="utf-8")
    packed_path = tmp_path / "holdout_0.packed"
    packed_path.write_text("line one\nline two\n", encoding="utf-8")

    with pytest.raises(ValueError, match="could not load"):
        load_team_species(str(team_path), teams_root=".")


def test_load_team_species_rejects_a_packed_file_with_no_pokemon(tmp_path):
    team_path = tmp_path / "holdout_0.txt"
    team_path.write_text("irrelevant\n", encoding="utf-8")
    packed_path = tmp_path / "holdout_0.packed"
    packed_path.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="contains no Pokemon"):
        load_team_species(str(team_path), teams_root=".")


def test_load_team_species_rejects_a_non_string_team_path():
    with pytest.raises(ValueError, match="must be a non-empty string"):
        load_team_species(123, teams_root=".")


def test_load_team_species_wraps_a_permission_error_as_valueerror(tmp_path, monkeypatch):
    # Review-fix P1: only FileNotFoundError/ValueError were wrapped -- an unreadable (but
    # existing) .packed file raises PermissionError, a sibling OSError subclass, which escaped
    # this module's "exclusively ValueError" contract entirely. Wrapping OSError (not just
    # FileNotFoundError) closes this for every OSError subclass, not just the one this test
    # happens to simulate.
    team_path = tmp_path / "holdout_0.txt"
    team_path.write_text("irrelevant\n", encoding="utf-8")
    packed_path = tmp_path / "holdout_0.packed"
    packed_path.write_text(_packed_team(["Pikachu"]), encoding="utf-8")

    def _raise_permission_error(self, *a, **kw):
        raise PermissionError(f"fixture-forced permission denial: {self}")

    monkeypatch.setattr("pathlib.Path.read_text", _raise_permission_error)

    with pytest.raises(ValueError, match="could not load"):
        load_team_species(str(team_path), teams_root=".")
