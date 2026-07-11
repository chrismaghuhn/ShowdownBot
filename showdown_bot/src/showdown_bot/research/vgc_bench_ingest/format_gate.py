"""Format/regulation gate for VGC-Bench raw battles (2b-5a Part A Task 2).

``gate_format`` classifies a Showdown format/tier string against the target
regulation (gen9 VGC Reg I) *without* trusting the dataset's own labelling --
everything is re-derived from the format string itself, same fail-closed
philosophy as the winner/turns re-derivation in ``parse_log``.

Accepted input forms (both are normalized identically):

1. The raw human tier string as it appears in a Showdown ``|tier|`` protocol
   line / on ``VgcBenchRawBattle.format_name`` -- e.g. ``"[Gen 9] VGC 2025
   Reg I"``, ``"[Gen 9] VGC 2025 Reg M-A"``.
2. A machine format id -- e.g. ``"gen9vgc2025regi"``, ``"gen9vgc2025regma"``.

Normalization lowercases the input and strips every non-alphanumeric
character, so both forms above collapse to the same token
(``"gen9vgc2025regi"`` / ``"gen9vgc2025regma"``) before matching.

**HARD RULE:** Regulation M-A / M-B (``regma`` / ``regmb``) is gen9 VGC and
mechanically similar to Reg I, but it is NEVER classified as
``TARGET_COMPATIBLE`` -- the MA/MB slice of VGC-Bench has zero Reg I data,
and silently treating it as Reg I would poison any downstream sample. This
is enforced structurally below (MA/MB is special-cased ahead of the generic
"other regulation" branch) and covered by an explicit test.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Compatibility = Literal[
    "TARGET_COMPATIBLE",
    "MECHANICALLY_SIMILAR_BUT_NOT_TARGET",
    "REJECT_FORMAT_MISMATCH",
    "REJECT_UNKNOWN_FORMAT",
]

# Reg I is the only target; only these two years are verified to carry Reg I
# VGC-Bench data (see the README / dataset-card note in Part A's spec).
_TARGET_REG_LETTER = "i"
_TARGET_YEARS = ("2025", "2026")

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
# Anchored full match of a (bo3-marker-stripped) gen9 VGC token, e.g.
# "gen9vgc2025regi" or "gen9vgc2025regma". The reg-letter group is
# non-greedy + fullmatch-anchored so it captures exactly the reg token (never
# a prefix of it) -- this is what makes the Reg-I-vs-MA/MB distinction exact.
_GEN9VGC_RE = re.compile(r"^gen9vgc(\d{4})reg([a-z]+?)$")
# Generic "this at least looks like *some* Showdown format id" prefix, used
# only to distinguish a recognized-but-wrong format (REJECT_FORMAT_MISMATCH)
# from truly unparseable input (REJECT_UNKNOWN_FORMAT).
_GEN_PREFIX_RE = re.compile(r"^gen\d+")


@dataclass(frozen=True)
class FormatGateResult:
    """Result of gating one format/tier string against the target regulation.

    ``inferred_regulation`` is a short normalized label ("I", "M-A", "M-B",
    "G", "H", ...) or ``None`` if no regulation could be inferred.
    ``is_bo3`` is ``True``/``False`` whenever the input parsed as *some* gen9
    VGC format (a definite BO1 is ``False``, never ``None``), and ``None``
    only when ``compatibility == "REJECT_UNKNOWN_FORMAT"`` (nothing could be
    inferred at all).
    """

    source_format: str
    inferred_regulation: str | None
    is_bo3: bool | None
    compatibility: Compatibility
    reason: str


def _normalize(format_name: str) -> str:
    return _NON_ALNUM_RE.sub("", (format_name or "").lower())


def _split_bo3(normalized: str) -> tuple[str, bool]:
    """Strip a trailing 'bo3' marker; return (stripped, is_bo3)."""
    if normalized.endswith("bo3"):
        return normalized[:-3], True
    return normalized, False


def _reg_label(reg_letters: str) -> str:
    """Map a raw reg token ("i", "ma", "mb", "h", ...) to a display label."""
    if len(reg_letters) == 1:
        return reg_letters.upper()
    if len(reg_letters) == 2 and reg_letters[0] == "m":
        return f"M-{reg_letters[1].upper()}"
    return reg_letters.upper()


def gate_format(format_name: str) -> FormatGateResult:
    """Classify ``format_name`` against the target regulation (gen9 VGC Reg I).

    Accepts either the raw human tier string (``"[Gen 9] VGC 2025 Reg I"``)
    or a machine format id (``"gen9vgc2025regi"``) -- see module docstring.
    Never raises: unparseable input is reported via
    ``compatibility="REJECT_UNKNOWN_FORMAT"``, not an exception, since this
    is a classification gate rather than a strict loader.
    """
    source = format_name
    normalized = _normalize(format_name)

    if not normalized:
        return FormatGateResult(
            source_format=source,
            inferred_regulation=None,
            is_bo3=None,
            compatibility="REJECT_UNKNOWN_FORMAT",
            reason="empty or unparseable format string",
        )

    stripped, is_bo3 = _split_bo3(normalized)
    match = _GEN9VGC_RE.fullmatch(stripped)

    if match:
        year, reg = match.group(1), match.group(2)
        label = _reg_label(reg)
        bo3_note = " (BO3)" if is_bo3 else ""

        if reg == _TARGET_REG_LETTER and year in _TARGET_YEARS:
            return FormatGateResult(
                source_format=source,
                inferred_regulation=label,
                is_bo3=is_bo3,
                compatibility="TARGET_COMPATIBLE",
                reason=f"gen9 VGC {year} Reg {label}{bo3_note} -- target regulation",
            )

        if reg == _TARGET_REG_LETTER:
            # Reg I, but not a verified-Reg-I-data year -- still Reg I
            # mechanically, but not confirmed target data, so do not
            # auto-promote to TARGET_COMPATIBLE.
            return FormatGateResult(
                source_format=source,
                inferred_regulation=label,
                is_bo3=is_bo3,
                compatibility="MECHANICALLY_SIMILAR_BUT_NOT_TARGET",
                reason=(
                    f"gen9 VGC {year} Reg {label}{bo3_note} -- Reg I but an "
                    f"unverified year ({year} not in {_TARGET_YEARS})"
                ),
            )

        if reg in ("ma", "mb"):
            # HARD RULE: MA/MB is gen9 VGC and mechanically similar to Reg I,
            # but has zero Reg I data -- NEVER TARGET_COMPATIBLE.
            return FormatGateResult(
                source_format=source,
                inferred_regulation=label,
                is_bo3=is_bo3,
                compatibility="MECHANICALLY_SIMILAR_BUT_NOT_TARGET",
                reason=(
                    f"gen9 VGC {year} Reg {label}{bo3_note} -- mechanically "
                    f"similar to Reg I but NOT the target regulation "
                    f"(Reg {label} has zero Reg I data)"
                ),
            )

        return FormatGateResult(
            source_format=source,
            inferred_regulation=label,
            is_bo3=is_bo3,
            compatibility="MECHANICALLY_SIMILAR_BUT_NOT_TARGET",
            reason=(
                f"gen9 VGC {year} Reg {label}{bo3_note} -- mechanically "
                f"similar to Reg I but not the target regulation"
            ),
        )

    if "gen9vgc" in stripped:
        # Looks like gen9 VGC but the year/reg token didn't fully parse --
        # ambiguous, treat as unparseable rather than guessing.
        return FormatGateResult(
            source_format=source,
            inferred_regulation=None,
            is_bo3=None,
            compatibility="REJECT_UNKNOWN_FORMAT",
            reason=f"looks like gen9 VGC but could not parse year/regulation from {source!r}",
        )

    if _GEN_PREFIX_RE.match(stripped):
        return FormatGateResult(
            source_format=source,
            inferred_regulation=None,
            is_bo3=is_bo3,
            compatibility="REJECT_FORMAT_MISMATCH",
            reason=f"not a gen9 VGC format (parsed tier {stripped!r})",
        )

    return FormatGateResult(
        source_format=source,
        inferred_regulation=None,
        is_bo3=None,
        compatibility="REJECT_UNKNOWN_FORMAT",
        reason=f"could not parse a Pokémon Showdown format id from {source!r}",
    )
