"""Extract real (state, request) decision points from committed room_raw protocol logs.

Mirrors client/gauntlet.py's own BattleState.from_log_text / merge_request /
BattleRequest.model_validate chain exactly -- this module adds no new resolution logic,
only offline replay of what the live client already does per-request.

One deliberate divergence from gauntlet.py's ``_state_for``: gauntlet.py wraps the
state-build chain in try/except and degrades to ``state=None`` per-decision on failure
(a live client must stay resilient to keep playing). This module does NOT catch that
exception -- it is an offline correctness gate, and silently dropping a decision on a
swallowed exception would undermine the statistical rigor the gate depends on. A
malformed line propagates as a hard failure for the whole file instead of a silent
partial result.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from showdown_bot.engine.state import BattleState, merge_request
from showdown_bot.eval.room_dump import read_room_log_frames
from showdown_bot.models.request import BattleRequest


class RequestKind(Enum):
    TEAM_PREVIEW = "team_preview"
    FORCE_SWITCH = "force_switch"
    MOVE = "move"


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ExtractedDecision:
    # hash=False: state/request are unhashable objects; excluding them from hash
    # computation is required for frozen dataclass instances to actually be hashable.
    # Equality (__eq__) still compares every field, including these two, unchanged.
    state: BattleState | None = field(hash=False)  # None for team-preview (see gauntlet._state_for)
    request: BattleRequest = field(hash=False)
    kind: RequestKind
    side: str  # "p1" | "p2"
    turn: int  # 0 if no |turn| line has been seen yet (team preview)
    request_hash: str
    log_prefix_hash: str
    _debug_prefix_line_count: int  # test-only introspection, not used by any consumer


def _request_kind(req: BattleRequest) -> RequestKind:
    if req.team_preview:
        return RequestKind.TEAM_PREVIEW
    if req.force_switch and any(req.force_switch):
        return RequestKind.FORCE_SWITCH
    return RequestKind.MOVE


def _hero_side(req: BattleRequest) -> str:
    side_id = (req.side.id or "").strip()
    if side_id in ("p1", "p2"):
        return side_id
    raise ValueError(f"request carries no resolvable side.id: {req.side!r}")


def extract_decisions_from_log(path: str | Path) -> list[ExtractedDecision]:
    frames = read_room_log_frames(path)
    full_text = frames[0] if frames else ""
    lines = full_text.split("\n")

    decisions: list[ExtractedDecision] = []
    seen_rqids: set[int] = set()
    current_turn = 0

    for i, line in enumerate(lines):
        if line.startswith("|turn|"):
            try:
                current_turn = int(line.split("|", 2)[2])
            except (IndexError, ValueError):
                pass
            continue
        if not line.startswith("|request|"):
            continue

        payload = line[len("|request|"):]
        req = BattleRequest.model_validate(json.loads(payload))

        if req.rqid in seen_rqids:
            continue  # reconnect resend of an already-processed request
        seen_rqids.add(req.rqid)

        if req.wait:
            continue  # opponent's turn -- nothing was chosen here, not a decision point

        prefix_lines = lines[: i + 1]  # up to AND including this line -- matches gauntlet.py
        prefix_text = "\n".join(prefix_lines)

        state: BattleState | None = None
        if not req.team_preview:
            # Intentionally NOT wrapped in try/except (unlike gauntlet.py's _state_for):
            # a malformed line should fail this offline gate loudly, not silently drop
            # a decision and undercount the statistics the gate is built to guarantee.
            state = BattleState.from_log_text(prefix_text)
            merge_request(req, state)

        decisions.append(ExtractedDecision(
            state=state,
            request=req,
            kind=_request_kind(req),
            side=_hero_side(req),
            turn=current_turn,
            request_hash=_sha256(_canonical_json(
                req.model_dump(mode="json", by_alias=True, exclude_none=False)
            )),
            log_prefix_hash=_sha256(prefix_text),
            _debug_prefix_line_count=len(prefix_lines),
        ))

    return decisions


class AmbiguousManifestMatchError(Exception):
    """Raised when a file's basename matches manifest rows with conflicting identities --
    fail closed rather than silently picking one (spec §6 item 5's fail-closed requirement)."""


class SeedIdentityConflictError(Exception):
    """Raised when files sharing a (seed_base, seed_index) manifest identity do NOT agree on
    the full seed value or normalized room-log content. (seed_base, seed_index) is a verified
    valid replicate key for the specific, frozen corpus this module was built against (85
    groups, sizes {2, 4}, zero conflicts -- checked directly) -- it is NOT assumed universally
    sufficient without this content-agreement check for any future/different corpus."""


@dataclass(frozen=True)
class SeedIdentity:
    seed_base: str
    seed_index: int
    schedule_hash: str  # provenance detail only -- NOT part of equality/grouping
    seed: str           # the full seed value -- used ONLY for the fail-closed invariant check
    # below, NOT part of equality/grouping either (grouping is (seed_base, seed_index) alone;
    # `seed` and `schedule_hash` are verified to AGREE within a group, not used to form it).

    def __hash__(self) -> int:
        return hash((self.seed_base, self.seed_index))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SeedIdentity):
            return NotImplemented
        return (self.seed_base, self.seed_index) == (other.seed_base, other.seed_index)


@dataclass(frozen=True)
class ExcludedBattle:
    source_file: Path
    reason: str  # "duplicate_seed_identity" | "duplicate_content_hash" | "excluded_diagnostic_artifact"
    duplicate_of: Path | None  # None for excluded_diagnostic_artifact (excluded a-priori, not vs. a specific file)


@dataclass(frozen=True)
class DedupReport:
    files_found: int
    kept: list[Path]
    kept_identities: list[SeedIdentity]  # parallel-ish, only for files with a manifest match
    excluded: list[ExcludedBattle]
    final_g: int


_DIVERGENT_DIR_NAME = "room_raw_divergent"


def _is_diagnostic_artifact(path: Path) -> bool:
    return any(part == _DIVERGENT_DIR_NAME for part in path.parts)


def _load_manifest_rows(manifest_files: list[Path]) -> dict[str, SeedIdentity]:
    """basename (with .log, no .gz) -> SeedIdentity, across all given manifest files.
    Fails closed (AmbiguousManifestMatchError) if two manifests disagree about one file's
    (seed_base, seed_index) identity."""
    by_basename: dict[str, SeedIdentity] = {}
    for manifest_path in manifest_files:
        if not manifest_path.exists():
            continue
        with open(manifest_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                raw_path = row["room_raw_path"].replace("\\", "/")
                basename = raw_path.rsplit("/", 1)[-1]
                identity = SeedIdentity(
                    seed_base=row["seed_base"], seed_index=row["seed_index"],
                    schedule_hash=row["schedule_hash"], seed=row["seed"],
                )
                existing = by_basename.get(basename)
                if existing is not None and (existing.seed_base, existing.seed_index) != (
                    identity.seed_base, identity.seed_index,
                ):
                    raise AmbiguousManifestMatchError(
                        f"{basename} matches conflicting identities: "
                        f"{(existing.seed_base, existing.seed_index)} vs "
                        f"{(identity.seed_base, identity.seed_index)}"
                    )
                by_basename[basename] = identity
    return by_basename


def _content_hash(path: Path) -> str:
    from showdown_bot.eval.room_dump import normalized_room_log_sha256
    frames = read_room_log_frames(path)
    return normalized_room_log_sha256(frames)


def _source_priority(path: Path, keep_priority: list[str]) -> int:
    parts = {p.lower() for p in path.parts}
    for rank, name in enumerate(keep_priority):
        if name.lower() in parts:
            return rank
    return len(keep_priority)  # unknown source -- lowest priority


def _verify_seed_identity_invariant(
    key: tuple[str, int], entries: list[tuple[Path, SeedIdentity]],
    content_hash_cache: dict[Path, str],
) -> None:
    """Fail-closed check: every file claiming this (seed_base, seed_index) identity must agree
    on BOTH the full seed value AND the normalized room-log content hash. Verified to hold for
    every one of the real corpus's 85 groups before this check was added -- this function is
    what ENFORCES that fact stays true on every future run, rather than trusting it silently."""
    seeds = {identity.seed for _p, identity in entries}
    if len(seeds) > 1:
        raise SeedIdentityConflictError(
            f"{key}: files claim the same (seed_base, seed_index) but disagree on the full "
            f"seed value: {sorted((str(p), i.seed) for p, i in entries)}"
        )
    hashes: dict[Path, str] = {}
    for path, _identity in entries:
        if path not in content_hash_cache:
            content_hash_cache[path] = _content_hash(path)
        hashes[path] = content_hash_cache[path]
    if len(set(hashes.values())) > 1:
        raise SeedIdentityConflictError(
            f"{key}: files share (seed_base, seed_index) and seed value, but normalized room-log "
            f"content differs -- refusing to treat them as duplicates: "
            f"{sorted((str(p), h) for p, h in hashes.items())}"
        )


def deduplicate_battle_logs(
    *, log_files: list[Path], manifest_files: list[Path], keep_priority: list[str],
) -> DedupReport:
    manifest_by_basename = _load_manifest_rows(manifest_files)

    # Step 0: a-priori exclusion, before either matching path runs.
    diagnostic_files = [p for p in log_files if _is_diagnostic_artifact(p)]
    remaining_files = [p for p in log_files if not _is_diagnostic_artifact(p)]
    excluded: list[ExcludedBattle] = [
        ExcludedBattle(p, "excluded_diagnostic_artifact", None) for p in diagnostic_files
    ]

    # Step 1: manifest join, grouped on the RAW (seed_base, seed_index) tuple -- each file's
    # OWN full SeedIdentity (with its own seed/schedule_hash) is kept alongside it, not
    # collapsed into whichever identity object happened to be inserted first, so the fail-closed
    # invariant check below can see every member's real seed/content, not just one.
    groups: dict[tuple[str, int], list[tuple[Path, SeedIdentity]]] = {}
    unmatched: list[Path] = []
    for path in remaining_files:
        basename = path.name
        if basename.endswith(".gz"):
            basename = basename[: -len(".gz")]
        identity = manifest_by_basename.get(basename)
        if identity is None:
            unmatched.append(path)
        else:
            key = (identity.seed_base, identity.seed_index)
            groups.setdefault(key, []).append((path, identity))

    kept: list[Path] = []
    kept_identities: list[SeedIdentity] = []
    content_hash_cache: dict[Path, str] = {}

    for key, entries in groups.items():
        _verify_seed_identity_invariant(key, entries, content_hash_cache)
        paths_sorted = sorted(
            (p for p, _i in entries), key=lambda p: (_source_priority(p, keep_priority), str(p))
        )
        winner = paths_sorted[0]
        winner_identity = next(i for p, i in entries if p == winner)
        kept.append(winner)
        kept_identities.append(winner_identity)
        for loser in paths_sorted[1:]:
            excluded.append(ExcludedBattle(loser, "duplicate_seed_identity", winner))

    # Step 2: content-hash fallback, defense-in-depth for files with no manifest row at all.
    # Reuses content_hash_cache where the invariant check above already computed a kept file's
    # hash, avoiding a redundant re-read.
    hash_to_kept: dict[str, Path] = {}
    for k in kept:
        if k not in content_hash_cache:
            content_hash_cache[k] = _content_hash(k)
        hash_to_kept[content_hash_cache[k]] = k

    unmatched_sorted = sorted(unmatched, key=lambda p: (_source_priority(p, keep_priority), str(p)))
    for path in unmatched_sorted:
        h = _content_hash(path)
        if h in hash_to_kept:
            excluded.append(ExcludedBattle(path, "duplicate_content_hash", hash_to_kept[h]))
            continue
        hash_to_kept[h] = path
        kept.append(path)

    return DedupReport(
        files_found=len(log_files),
        kept=kept,
        kept_identities=kept_identities,
        excluded=excluded,
        final_g=len(kept),
    )
