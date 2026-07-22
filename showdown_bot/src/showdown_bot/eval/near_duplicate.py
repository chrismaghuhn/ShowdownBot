"""Species-overlap near-duplicate flag (DESIGN sec 3.3): "a content-overlap check at sealing
flags any holdout team whose species set substantially overlaps a touched or coverage team for
manual disjointness review (near-duplicates are not independent)." Diagnostic ONLY -- a flag is
never an auto-reject; every flag this module can produce is a normal return value, never a raised
exception. Species normalization matches this codebase's own established convention exactly: the
same Showdown `toID` transform already duplicated in `engine.state.to_id` / `engine.items.to_id`
/ `engine.moves.to_id` and wrapped as `battle.opponent.SpeciesDex.to_id` -- lowercase, strip
everything outside a-z0-9, no forme merging (`Giratina` and `Giratina-Origin` stay distinct).

Every public function in this module validates its argument TYPES strictly, not merely
emptiness, and raises ONLY `ValueError` for any invalid input -- never a caller-input-triggered
`TypeError`/`AttributeError`/`FileNotFoundError` escaping uncaught. `load_team_species` derives a
team's species from its REAL sealed packed content rather than accepting a caller's bare
assertion -- the same "prove it from the real bound data, don't trust the caller" discipline this
whole plan applies everywhere else (arm manifests bound to their own rows, stratum bound to each
arm's own manifest)."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

NEAR_DUPLICATE_REVIEW_THRESHOLD = 0.5


def _to_id(name: str) -> str:
    """Same one-line rule as engine.state.to_id / engine.items.to_id / engine.moves.to_id /
    battle.opponent.SpeciesDex.to_id -- duplicated here rather than imported so this eval-side
    module has no dependency on engine/, matching how those three are already independent
    duplicates of the same rule rather than a single shared import site."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def species_set(species: list[str]) -> frozenset[str]:
    """Normalizes a raw list of species name strings into a canonical, hashable set. Duplicate
    entries collapse naturally via set construction (illegal under Showdown's own species clause
    for a real team, but this is a generic utility, not a team validator). Fails closed on a
    non-list, an empty list, or non-string elements -- a bare string would otherwise iterate as
    individual characters rather than being rejected as the wrong type."""
    if not isinstance(species, list):
        raise ValueError(f"species must be a list, got {type(species).__name__}")
    if not species:
        raise ValueError("species must be non-empty -- an empty list is not a valid team")
    if not all(isinstance(name, str) for name in species):
        raise ValueError(f"species must contain only strings, got {species!r}")
    normalized = frozenset(_to_id(name) for name in species)
    if "" in normalized:
        raise ValueError(f"species contains a name that normalizes to the empty string: {species!r}")
    return normalized


def overlap_fraction(a: frozenset[str], b: frozenset[str]) -> float:
    """Jaccard similarity, |A intersect B| / |A union B| -- symmetric in a/b (this function does
    not itself distinguish "candidate" from "reference"; that framing exists only in
    find_near_duplicate_flags below). Chosen over the overlap coefficient
    (|A intersect B| / min(|A|, |B|)) because, for two 6-species teams, Jaccard >= 0.5 requires
    at least 4 of 6 species shared, while the overlap coefficient's >= 0.5 requires only 3 of 6 --
    ordinary shared-meta-staple overlap between unrelated competent teams, not a near-duplicate.
    Fails closed on a non-frozenset or empty input -- defense in depth independent of
    species_set's own guard, since this function is public and may be called directly."""
    if not isinstance(a, frozenset) or not isinstance(b, frozenset):
        raise ValueError(
            f"overlap_fraction requires two frozensets, got {type(a).__name__} and {type(b).__name__}"
        )
    if not a or not b:
        raise ValueError("overlap_fraction requires two non-empty sets")
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union


@dataclass(frozen=True)
class NearDuplicateFlag:
    candidate_team_id: str
    reference_team_id: str
    overlap_fraction: float
    shared_species: tuple[str, ...]


def find_near_duplicate_flags(
    *, candidate_team_id: str, candidate_species: list[str], reference_teams: dict[str, list[str]],
) -> list[NearDuplicateFlag]:
    """Compares ONE candidate team's species set against every team in reference_teams, flagging
    (never rejecting -- DESIGN sec 3.3, manual-review only) any reference team whose Jaccard
    overlap with the candidate is >= NEAR_DUPLICATE_REVIEW_THRESHOLD (inclusive: an exact-
    threshold case is exactly what a human should see, not what should silently pass because the
    bar is exclusive). candidate_team_id is skipped if it also appears in reference_teams -- a
    team must never be flagged against itself. Results are sorted by reference_team_id for a
    deterministic return order regardless of reference_teams' own dict construction order."""
    if not isinstance(candidate_team_id, str):
        raise ValueError(f"candidate_team_id must be a string, got {type(candidate_team_id).__name__}")
    if not candidate_team_id:
        raise ValueError("candidate_team_id must be non-empty")
    if not isinstance(reference_teams, dict):
        raise ValueError(f"reference_teams must be a dict, got {type(reference_teams).__name__}")
    if not reference_teams:
        raise ValueError("reference_teams must be non-empty -- an empty mapping makes this check vacuous")
    if not all(isinstance(team_id, str) for team_id in reference_teams):
        raise ValueError(f"reference_teams keys must all be strings, got {reference_teams!r}")
    candidate_set = species_set(candidate_species)
    flags = []
    for reference_team_id in sorted(reference_teams):
        if reference_team_id == candidate_team_id:
            continue
        reference_set = species_set(reference_teams[reference_team_id])
        fraction = overlap_fraction(candidate_set, reference_set)
        if fraction >= NEAR_DUPLICATE_REVIEW_THRESHOLD:
            shared = tuple(sorted(candidate_set & reference_set))
            flags.append(NearDuplicateFlag(
                candidate_team_id=candidate_team_id, reference_team_id=reference_team_id,
                overlap_fraction=fraction, shared_species=shared,
            ))
    return flags


def load_team_species(team_path: str, *, teams_root: str = ".") -> list[str]:
    """Derives a team's species list from its REAL sealed packed content -- never a caller's bare
    assertion. Reuses this codebase's existing packed-format parsing convention
    (team.spreads.our_spreads_from_packed: split on "]" for per-mon blocks, then "|" for fields,
    species = field[1] or field[0] when blank) rather than inventing a second one, and
    team.pack.load_packed_team for the actual file read (the same function Task 9's own
    run_strength_holdout_arm uses to load hero/opponent teams). Wraps every failure --
    FileNotFoundError, a malformed multi-line packed file (both from load_packed_team), or a
    malformed per-mon block -- as ValueError, matching this module's own single-exception-type
    contract; no other exception type ever escapes this function."""
    if not isinstance(team_path, str) or not team_path:
        raise ValueError(f"team_path must be a non-empty string, got {team_path!r}")
    if not isinstance(teams_root, str):
        raise ValueError(f"teams_root must be a string, got {type(teams_root).__name__}")
    from showdown_bot.team.pack import load_packed_team
    try:
        packed = load_packed_team(os.path.join(teams_root, team_path))
    except (FileNotFoundError, ValueError) as exc:
        raise ValueError(
            f"could not load packed team at {team_path!r} under teams_root={teams_root!r}: {exc}"
        ) from exc
    species = []
    for block in packed.split("]"):
        block = block.strip()
        if not block:
            continue
        fields = block.split("|")
        if len(fields) < 2:
            raise ValueError(f"malformed packed team block (expected at least 2 fields): {block!r}")
        name = (fields[1] or fields[0]).strip()
        if not name:
            raise ValueError(f"packed team block has no species/nickname: {block!r}")
        species.append(name)
    if not species:
        raise ValueError(f"packed team at {team_path!r} contains no Pokemon")
    return species
