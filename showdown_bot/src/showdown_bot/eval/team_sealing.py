"""Provenance/hash sealing for Gate B holdout teams (DESIGN sec 3.4, plan §15 / Task 12).

Uses the REAL canonical team-content hash (``eval/panel.py::team_content_hash``, ``.txt`` and
``.packed`` hashed together). Rev. 1 of the plan defined a different, incompatible, same-named
local function that hashed only ``.txt`` -- a live naming collision with real code, not merely an
omission, and a hash that could not see packed-only drift. It is not repeated here.

Scope, deliberately narrow: this module only RECORDS a seal for team files that ALREADY EXIST on
disk. It does not select, generate, download, legalise, modify, or play a team, and it never
writes anything -- sealing is strictly read-only.

It also makes NO legality claim. ``seal_team`` deliberately does not run ``validate-team``: a
seal is a provenance and content-identity record, and a record that also carried a legality field
would invite treating "sealed" as "legal". Task 13 must prove legality separately, BEFORE sealing,
and refuse to seal on a non-zero exit.
"""
from __future__ import annotations

import platform
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from showdown_bot.eval.panel import PanelError, team_content_hash


class SealingError(Exception):
    """A team could not be sealed: malformed metadata, a rejected path, or unreadable files.

    Single exception type by design. Everything reachable from ``seal_team`` -- ``PanelError``
    from the canonical hash, plus the ``OSError``/``UnicodeDecodeError``/``ValueError`` that
    ``panel._team_content_hash``'s own ``read_text`` calls can raise and does NOT convert -- is
    folded into this one class, so a caller never has to catch a union to seal a team safely.
    """


@dataclass(frozen=True)
class SealedTeamRecord:
    """An immutable seal. Frozen so a record cannot be edited after the fact -- a mutable seal is
    not a seal. Deliberately carries no legality/validity field (see the module docstring)."""

    team_id: str
    team_path: str
    content_hash: str
    archetype: str
    source_description: str
    source_date: str
    blind_attestation: str


_REQUIRED_TEXT_FIELDS = (
    "team_id", "teams_root", "team_path", "archetype", "source_description", "source_date",
    "blind_attestation",
)


def _require_text(name: str, value) -> str:
    """Every metadata field must be a real, non-blank string.

    ``isinstance`` first, before ``.strip()``: a non-string (``None``, an int, ``bytes``, a list)
    would otherwise raise a raw ``AttributeError``/``TypeError`` out of this module, exactly the
    kind of unwrapped boundary failure the rest of this gate refuses to ship. Whitespace-only is
    rejected as well -- DESIGN sec 3.4 wants a recorded rationale, and `"   "` records nothing.
    """
    if not isinstance(value, str):
        raise SealingError(
            f"{name} must be a non-empty string, got {type(value).__name__}: {value!r}"
        )
    if not value.strip():
        raise SealingError(
            f"{name} must be a non-empty string -- blank or whitespace-only is refused "
            f"(got {value!r})"
        )
    return value


def _assert_contained(teams_root: str, team_path: str) -> None:
    """``team_path`` must be a relative ``.txt`` path that really resolves inside ``teams_root``.

    This has to happen BEFORE ``team_content_hash``, because ``panel._team_content_hash`` builds
    its path as ``Path(teams_root) / team_path`` -- and ``/`` DISCARDS the left operand entirely
    when the right one is absolute. An absolute ``team_path`` would therefore silently seal a file
    from anywhere on the filesystem while the record still claimed this ``teams_root``.

    Containment is checked on the RESOLVED real paths, compared component-wise (never as a string
    prefix, which would accept a sibling directory whose name merely starts with the root's), and
    case-folded on Windows only -- the same canonical comparison Tasks 9 and 10 already use. That
    also closes symlink/junction escapes, which a purely lexical ``..`` check cannot see.
    """
    pure = PurePosixPath(team_path.replace("\\", "/"))
    if pure.is_absolute() or Path(team_path).is_absolute() or (len(team_path) > 1 and team_path[1] == ":"):
        raise SealingError(
            f"team_path must be relative to teams_root, got the absolute path {team_path!r}"
        )
    if ".." in pure.parts:
        raise SealingError(
            f"team_path must not contain '..' traversal, got {team_path!r}"
        )
    if pure.suffix != ".txt":
        raise SealingError(
            f"team_path must be the team's .txt file (its .packed sibling is bound by the "
            f"canonical panel hash), got {team_path!r}"
        )
    try:
        root = Path(teams_root).resolve()
        target = (root / team_path).resolve()
    except OSError as exc:
        raise SealingError(
            f"cannot resolve team_path {team_path!r} under teams_root {teams_root!r}: {exc}"
        ) from exc
    root_parts, target_parts = root.parts, target.parts
    if platform.system() == "Windows":
        root_parts = tuple(p.lower() for p in root_parts)
        target_parts = tuple(p.lower() for p in target_parts)
    if target_parts[: len(root_parts)] != root_parts:
        raise SealingError(
            f"team_path {team_path!r} resolves to {str(target)!r}, outside teams_root "
            f"{str(root)!r} -- refusing to seal a file from outside the team root"
        )


def seal_team(
    *,
    team_id: str,
    teams_root: str,
    team_path: str,
    archetype: str,
    source_description: str,
    source_date: str,
    blind_attestation: str,
) -> SealedTeamRecord:
    """Seal an already-existing team: record its provenance and its real content hash.

    Fail-closed throughout. Does NOT run legality validation (see the module docstring) and does
    not modify, create, or delete any file.
    """
    values = {
        "team_id": team_id, "teams_root": teams_root, "team_path": team_path,
        "archetype": archetype, "source_description": source_description,
        "source_date": source_date, "blind_attestation": blind_attestation,
    }
    for name in _REQUIRED_TEXT_FIELDS:
        _require_text(name, values[name])

    _assert_contained(teams_root, team_path)

    try:
        content_hash = team_content_hash(teams_root, team_path)
    except PanelError as exc:
        # The documented case: one or both of .txt/.packed is missing.
        raise SealingError(f"cannot seal {team_path!r}: {exc}") from exc
    except UnicodeDecodeError as exc:
        # Verified against panel.py's real body, not its docstring: _team_content_hash calls
        # read_text(encoding="utf-8") on both files and converts NOTHING but the missing-file
        # case, so non-UTF-8 bytes on disk escape as a raw UnicodeDecodeError.
        raise SealingError(
            f"cannot seal {team_path!r}: its .txt/.packed content is not valid utf-8 "
            f"(cannot decode: {exc})"
        ) from exc
    except OSError as exc:
        # Same reasoning: a permission failure, an unreadable file, or a directory standing where
        # a team file should be (IsADirectoryError/PermissionError are both OSError) all reach
        # read_text unguarded.
        raise SealingError(
            f"cannot seal {team_path!r}: could not read its .txt/.packed content under "
            f"teams_root {teams_root!r} ({exc})"
        ) from exc
    except ValueError as exc:
        # Path.with_suffix raises ValueError for a pathological name; PanelError is itself a
        # ValueError subclass and is already handled above, so this only catches the rest.
        raise SealingError(f"cannot seal {team_path!r}: {exc}") from exc

    return SealedTeamRecord(
        team_id=team_id,
        team_path=team_path,
        content_hash=content_hash,
        archetype=archetype,
        source_description=source_description,
        source_date=source_date,
        blind_attestation=blind_attestation,
    )
