"""Held-out access ledger: append-only trace + access budget (T6 Task 1, spec §1).

A solo dev with root cannot be technically stopped from touching held-out teams
(honesty clause, review §6/§9). This module makes every held-out access visible and
auditable instead: two entry kinds are appended to a committed JSONL ledger --

  - ``schedule`` -- appended when a held-out schedule is generated:
    ``{kind, date, purpose, panel_hash, schedule_hash, git_sha, justification}``.
  - ``run`` -- appended after a held-out run, same fields plus ``config_hash`` and
    ``result_sha256``: ``{kind, date, purpose, panel_hash, schedule_hash, config_hash,
    git_sha, result_sha256, justification}``.

``justification`` is always present and is ``None`` or a non-empty explanation string.

``check_access`` enforces the budget: **one held-out gate attempt per config_hash
lineage**. The mechanism it targets is not "looking at held-out data" per se -- it is
iterating a candidate config until a held-out run happens to pass, then keeping that
lucky run (review §6). A single recorded ``run`` entry for a given ``config_hash`` is
fine; a SECOND one without an explicit, committed justification is refused. Generating
or rehearsing a schedule never touches held-out results, so ``schedule`` entries never
consume budget. A justification (recorded on the new entry, e.g. a deliberate
reproduction re-run) or a panel version bump (which changes ``panel_hash`` and what a
"held-out run" even means) resets the budget -- by design, so the exception is visible
and auditable rather than silently allowed.

Append-only discipline is enforced two ways: this module's single write choke-point
(``append_entry`` only ever opens the file in append-mode), plus a git-history test
(``test_heldout_ledger.py::test_ledger_git_history_append_only``) that replays
``git log --follow -p -- config/eval/heldout_ledger.jsonl`` and fails if any committed
line is ever removed or edited.
"""
from __future__ import annotations

import json
from pathlib import Path

_COMMON_STR_FIELDS = ("date", "purpose", "panel_hash", "schedule_hash", "git_sha")
_RUN_ONLY_STR_FIELDS = ("config_hash", "result_sha256")
_FIELDS_BY_KIND = {
    "schedule": frozenset({"kind", *_COMMON_STR_FIELDS, "justification"}),
    "run": frozenset({"kind", *_COMMON_STR_FIELDS, *_RUN_ONLY_STR_FIELDS, "justification"}),
}
_STR_FIELDS_BY_KIND = {
    "schedule": _COMMON_STR_FIELDS,
    "run": _COMMON_STR_FIELDS + _RUN_ONLY_STR_FIELDS,
}


class LedgerError(ValueError):
    """A ledger entry has an invalid shape, or the ledger file content is malformed."""


class AccessBudgetError(LedgerError):
    """A held-out access would exceed the one-attempt-per-config_hash budget.

    Raised by ``check_access`` when a prior ``run`` entry already exists for the same
    ``config_hash`` and no ``justification`` was given for this access. See the module
    docstring / spec §1 / review §6 for the rationale: the budget exists to catch
    iterate-until-held-out-passes overfitting, not to forbid held-out access outright.
    """


def _validate_entry(entry: dict) -> None:
    if not isinstance(entry, dict):
        raise LedgerError(f"ledger entry must be a dict, got {type(entry).__name__}")
    kind = entry.get("kind")
    if kind not in _FIELDS_BY_KIND:
        raise LedgerError(f"unknown ledger entry kind: {kind!r} (expected 'schedule' or 'run')")
    expected = _FIELDS_BY_KIND[kind]
    actual = set(entry)
    missing = expected - actual
    if missing:
        raise LedgerError(f"{kind} entry missing required field(s): {sorted(missing)}")
    unknown = actual - expected
    if unknown:
        raise LedgerError(f"{kind} entry has unknown field(s): {sorted(unknown)}")
    for field in _STR_FIELDS_BY_KIND[kind]:
        value = entry[field]
        if not isinstance(value, str) or not value:
            raise LedgerError(
                f"{kind} entry field {field!r} must be a non-empty str, got {value!r}"
            )
    justification = entry["justification"]
    if justification is not None and not isinstance(justification, str):
        raise LedgerError(
            f"{kind} entry field 'justification' must be None or str, "
            f"got {type(justification).__name__}"
        )


def append_entry(path, entry: dict) -> None:
    """Validate ``entry``'s shape and append it as one JSON line to ``path``.

    Validation happens BEFORE the file is touched (fail fast -- never a half-written
    ledger, mirroring ``eval.result_jsonl.BattleResultWriter``). The write itself is a
    literal append: utf-8, LF-only (``newline="\\n"``), mode ``"a"`` -- existing bytes
    are never read, rewritten, or truncated. This is the ledger's one write choke-point;
    append-only-ness in git history is verified separately (see module docstring).
    """
    _validate_entry(entry)
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n")


def read_ledger(path) -> list[dict]:
    """Read all entries from the ledger at ``path``, in file order.

    A missing file returns ``[]``, NOT an error: the ledger legitimately does not exist
    before the first held-out access (T6 births it), so "file not found" is a documented
    empty ledger rather than a corruption signal. A malformed *line* inside an existing
    file is the opposite situation -- the file is present but its content is broken --
    and is fail-fast per this codebase's philosophy: raises ``LedgerError`` immediately
    rather than skipping the bad line and silently returning a partial ledger.
    """
    p = Path(path)
    if not p.exists():
        return []
    entries: list[dict] = []
    with open(p, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise LedgerError(f"{path}:{lineno}: malformed JSON: {exc}") from exc
    return entries


def check_access(entries: list[dict], config_hash: str, *, justification: str | None = None) -> None:
    """Enforce the held-out access budget: one gate attempt per ``config_hash`` lineage.

    Raises ``AccessBudgetError`` iff a prior entry with ``kind == "run"`` and the same
    ``config_hash`` exists in ``entries`` AND ``justification`` is ``None``. ``schedule``
    entries never consume budget. Passing a non-``None`` ``justification`` always
    succeeds (the caller is expected to record that same string on the ledger entry it
    then appends -- this function only checks/refuses, it never writes). Returns ``None``
    on success. See the module docstring / spec §1 / review §6 for why this specific
    mechanism (iterate-until-held-out-passes) is the target, not held-out access itself.
    """
    if justification is not None:
        return
    for e in entries:
        if e.get("kind") == "run" and e.get("config_hash") == config_hash:
            raise AccessBudgetError(
                f"held-out access budget exceeded for config_hash={config_hash!r}: a prior "
                f"'run' entry already exists for this config; pass justification=<reason> to "
                f"proceed anyway (the reason is recorded on the new ledger entry)"
            )
