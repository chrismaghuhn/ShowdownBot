"""T5 pairing validator: turns two per-battle-row runs into validated `Pair`s (review §2).

Fail-fast, never warn-and-continue: every violation raises its own `PairingError`
subclass. `pair_runs` is the only entry point; it re-derives everything it needs from
the rows themselves (no trust in caller-supplied ordering or completeness).

Checks run in this fixed order (spec §1.2 / plan Task 2 Step 3):
  1. per-run row-identity duplicates            -> DuplicateRowError
  2. per-run constant provenance fields          -> RunMismatchError
  3. cross-run pairability (four fields equal;
     config_hash MUST differ)                    -> RunMismatchError / SelfComparisonError
  4. row counts (== expected_rows, if given)      -> RowCountError
  5. row counts equal across runs / battle_id
     sets equal                                   -> MissingPairError
  6. per-pair seed equality                       -> PairSeedMismatchError
  7. build sorted `Pair` list
"""
from __future__ import annotations

from dataclasses import dataclass

# The five fields that identify "the same evaluation conditions"; each must be a single
# constant value within one run. config_hash is included here (per-run constancy) but is
# handled separately across runs (it must DIFFER, not match — see SelfComparisonError).
_CONSTANT_FIELDS = ("schedule_hash", "seed_base", "panel_hash", "format_id", "config_hash")
# The subset that must be EQUAL across the two runs for a comparison to be meaningful.
_CROSS_RUN_MATCH_FIELDS = ("schedule_hash", "seed_base", "panel_hash", "format_id")


class PairingError(ValueError):
    """Base class for all pairing-validation failures."""


class SelfComparisonError(PairingError):
    """config_hash is identical across run A and run B.

    WHY refused rather than reported: pairing a run against itself drives n_discordant
    toward 0, which reads as "perfectly safe" in the McNemar output — but it is just
    self-agreement, not evidence of anything. Reporting it would let a config look safe
    by comparing it to a copy of itself (review §2, §10).
    """


class RunMismatchError(PairingError):
    """A provenance field (schedule_hash/seed_base/panel_hash/format_id/config_hash) is
    not constant within one run, or (for the first four) differs between run A and run B.
    These fields identify the exact evaluation conditions; a paired comparison is only
    meaningful when they hold constant and match across both runs.
    """


class PairSeedMismatchError(PairingError):
    """Two rows sharing a battle_id do not share the same seed.

    By construction the same battle slot must reuse the identical seed across runs; a
    mismatch means the input data is corrupted, not that the seed diverged in-battle.
    """


class DuplicateRowError(PairingError):
    """(battle_id, config_hash) is not unique within a single run."""


class MissingPairError(PairingError):
    """A battle_id is present in only one run, or the two runs have different row counts.

    WHY refused rather than dropped: silently dropping unmatched rows is selection bias,
    and in practice missingness correlates with crashes — exactly the failures the
    analysis exists to catch. Dropping them would hide the worst outcomes instead of
    surfacing them (review §2, §10).
    """


class RowCountError(PairingError):
    """`expected_rows` was given and a run's row count does not match it (e.g. the
    schedule's row count)."""


@dataclass(frozen=True)
class Pair:
    battle_id: str
    seed_index: int
    cell: tuple[str, str]
    hero_win_a: bool
    hero_win_b: bool
    row_a: dict
    row_b: dict


def _check_no_duplicates(rows: list[dict], *, which: str) -> None:
    seen: set[tuple] = set()
    for row in rows:
        key = (row["battle_id"], row["config_hash"])
        if key in seen:
            raise DuplicateRowError(
                f"run {which}: duplicate row for (battle_id={key[0]!r}, "
                f"config_hash={key[1]!r})"
            )
        seen.add(key)


def _check_constant_fields(rows: list[dict], *, which: str) -> dict[str, object]:
    values: dict[str, object] = {}
    for field in _CONSTANT_FIELDS:
        distinct = {row[field] for row in rows}
        if len(distinct) > 1:
            raise RunMismatchError(
                f"run {which}: field {field!r} is not constant within the run "
                f"(found {sorted(map(str, distinct))})"
            )
        values[field] = rows[0][field] if rows else None
    return values


def pair_runs(rows_a: list[dict], rows_b: list[dict], *, expected_rows: int | None = None
              ) -> list[Pair]:
    """Validate and pair two runs' battle rows. See module docstring for check order."""
    # 1. per-run duplicates
    _check_no_duplicates(rows_a, which="A")
    _check_no_duplicates(rows_b, which="B")

    # 2. per-run constant provenance fields
    const_a = _check_constant_fields(rows_a, which="A")
    const_b = _check_constant_fields(rows_b, which="B")

    # 3. cross-run pairability
    for field in _CROSS_RUN_MATCH_FIELDS:
        if const_a[field] != const_b[field]:
            raise RunMismatchError(
                f"field {field!r} differs across runs: A={const_a[field]!r} "
                f"B={const_b[field]!r}"
            )
    if const_a["config_hash"] == const_b["config_hash"]:
        raise SelfComparisonError(
            f"run A and run B share config_hash={const_a['config_hash']!r} "
            "-- refusing to pair a run against itself"
        )

    # 4. expected_rows enforcement
    if expected_rows is not None:
        if len(rows_a) != expected_rows:
            raise RowCountError(
                f"run A has {len(rows_a)} rows, expected {expected_rows}"
            )
        if len(rows_b) != expected_rows:
            raise RowCountError(
                f"run B has {len(rows_b)} rows, expected {expected_rows}"
            )

    # 5. row counts equal across runs / battle_id sets equal
    if len(rows_a) != len(rows_b):
        raise MissingPairError(
            f"row counts differ: run A has {len(rows_a)}, run B has {len(rows_b)}"
        )
    ids_a = {row["battle_id"] for row in rows_a}
    ids_b = {row["battle_id"] for row in rows_b}
    if ids_a != ids_b:
        only_a = sorted(ids_a - ids_b)
        only_b = sorted(ids_b - ids_a)
        raise MissingPairError(
            f"battle_id sets differ: only in A={only_a}, only in B={only_b}"
        )

    # 6. per-pair seed equality, 7. build pairs
    by_id_a = {row["battle_id"]: row for row in rows_a}
    by_id_b = {row["battle_id"]: row for row in rows_b}
    pairs = []
    for battle_id in ids_a:
        row_a = by_id_a[battle_id]
        row_b = by_id_b[battle_id]
        if row_a["seed"] != row_b["seed"]:
            raise PairSeedMismatchError(
                f"battle_id={battle_id!r}: seed mismatch A={row_a['seed']!r} "
                f"B={row_b['seed']!r}"
            )
        pairs.append(Pair(
            battle_id=battle_id,
            seed_index=row_a["seed_index"],
            cell=(row_a["opp_policy"], row_a["opp_team_hash"]),
            hero_win_a=(row_a["winner"] == "hero"),
            hero_win_b=(row_b["winner"] == "hero"),
            row_a=row_a,
            row_b=row_b,
        ))
    pairs.sort(key=lambda p: p.seed_index)
    return pairs
