"""Reproducible ``<results>.config-manifest.json`` freeze (I7a-C P1.4).

A prior slice (I5) hand-froze a config-manifest sidecar with no reproducible generation
command. This module is the single, fail-closed writer for that sidecar: it calls
``config_env.effective_config_manifest`` -- the exact same assembly the CLI's live
``config_hash`` computation uses -- verifies the resulting hash matches every row's
``config_hash`` in the target results file, and refuses to overwrite an existing sidecar.

This is a dedicated, explicit freeze step, NOT automatic global behavior: nothing in
``cli.py``'s ``gauntlet``/``run_schedule`` calls this on every run. A slice that wants a
reproducible sidecar for one specific frozen eval-run artifact calls this directly (or via
a thin script), the same way I5/I7a-C smoke evidence is frozen deliberately, not silently.
"""
from __future__ import annotations

import json
from pathlib import Path

from showdown_bot.eval.config_env import effective_config_manifest
from showdown_bot.eval.result_jsonl import make_config_hash


class ConfigManifestFreezeError(Exception):
    """Fail-closed: refuses to write or verify a sidecar that can't be reconciled against
    the results file it is supposed to describe."""


def _sidecar_path(results_path: Path) -> Path:
    return results_path.with_name(results_path.name + ".config-manifest.json")


def _single_recorded_config_hash(results_path: Path) -> str:
    """The one ``config_hash`` shared by every row in ``results_path``.

    Fails closed if the file is missing/empty, any row lacks ``config_hash``, or rows
    carry more than one distinct value (including a value later mutated to disagree)."""
    if not results_path.is_file() or results_path.stat().st_size == 0:
        raise ConfigManifestFreezeError(
            f"results file does not exist or is empty: {results_path}"
        )

    row_hashes: set[str] = set()
    n_rows = 0
    for line in results_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        n_rows += 1
        if "config_hash" not in row or not row["config_hash"]:
            raise ConfigManifestFreezeError(
                f"row {n_rows} in {results_path} is missing config_hash"
            )
        row_hashes.add(row["config_hash"])

    if n_rows == 0:
        raise ConfigManifestFreezeError(f"results file has no rows: {results_path}")
    if len(row_hashes) != 1:
        raise ConfigManifestFreezeError(
            f"{results_path} carries inconsistent/multiple config_hash values: "
            f"{sorted(row_hashes)} -- a frozen sidecar must describe exactly one config lineage"
        )
    (recorded_hash,) = row_hashes
    return recorded_hash


def write_config_manifest_sidecar(
    results_path: str | Path, *, agent: str, format_id: str,
    env: dict[str, str] | None = None,
    model_hash: str | None = None, model_manifest_hash: str | None = None,
) -> Path:
    """Write ``<results_path>.config-manifest.json`` and return its path.

    Fails closed (raises ``ConfigManifestFreezeError``, writes nothing) if:
    - ``results_path`` does not exist or has no rows;
    - any row is missing ``config_hash``;
    - rows carry more than one distinct ``config_hash`` value;
    - the ``effective_config_manifest`` hash for ``(agent, format_id, env, ...)`` does not
      match the results file's single ``config_hash`` (drift between the frozen run and the
      inputs passed here);
    - a sidecar already exists at the target path (never silently overwritten).
    """
    results_path = Path(results_path)
    recorded_hash = _single_recorded_config_hash(results_path)

    manifest = effective_config_manifest(
        agent=agent, format_id=format_id, env=env,
        model_hash=model_hash, model_manifest_hash=model_manifest_hash,
    )
    computed_hash = make_config_hash(manifest)
    if computed_hash != recorded_hash:
        raise ConfigManifestFreezeError(
            f"config_hash mismatch: results file recorded {recorded_hash!r}, but "
            f"effective_config_manifest(agent={agent!r}, format_id={format_id!r}, ...) "
            f"hashes to {computed_hash!r} -- refusing to freeze a sidecar that would not "
            f"rehash to the run it claims to describe (inputs likely differ from the actual run)"
        )

    out_path = _sidecar_path(results_path)
    if out_path.exists():
        raise ConfigManifestFreezeError(
            f"{out_path} already exists -- refusing to silently overwrite a frozen sidecar"
        )

    # newline="\n": this sidecar is provenance and is pinned by sha256 in the eval reports,
    # so the same manifest must serialise to the same BYTES on every platform. Without it
    # write_text applies the platform default and emits CRLF on Windows, so a Windows-frozen
    # sidecar and a Linux-frozen one disagree byte-for-byte for identical inputs -- and the
    # recorded digest is reproducible on only one of them. Mirrors BattleResultWriter and
    # eval-report, which both already pass newline="\n".
    #
    # This is the only guarantee that holds for EVERY caller. .gitattributes protects the
    # committed bytes of specific evidence trees only -- `data/eval/t4|t6|2b4|
    # champions-panel-v0/**` are marked `-text`; other paths under `data/eval/` (e.g.
    # accuracy-cap-derisk) have no rule at all. Those rules also only stop git from rewriting
    # bytes on checkout; nothing there stops this function from producing CRLF in the first
    # place, and a sidecar written outside a pinned tree would inherit the platform default.
    #
    # Deliberately NO trailing newline: json.dumps' output ends at `}` and the already-frozen
    # I7a-C/I7b-C sidecars end there too. Appending one would change their bytes, break the
    # sha256 their verdict reports pin, and make that committed evidence underivable from
    # this function -- see test_config_manifest_sidecar_has_no_trailing_newline.
    out_path.write_text(
        json.dumps({"config_hash": computed_hash, "manifest": manifest}, indent=2, sort_keys=True),
        encoding="utf-8",
        newline="\n",
    )
    return out_path


def verify_config_manifest_sidecar(
    results_path: str | Path, *, agent: str, format_id: str,
    env: dict[str, str] | None = None,
    model_hash: str | None = None, model_manifest_hash: str | None = None,
) -> None:
    """Re-verify an already-written ``<results_path>.config-manifest.json`` sidecar.

    Intended for the plan's "after any post-hoc mutation of a frozen result row (e.g.
    ``room_raw_path=null``), re-verify the manifest/config_hash binding before committing"
    step -- call this again after such a mutation instead of trusting the original freeze.

    Fails closed (raises ``ConfigManifestFreezeError``) if:
    - the results file itself no longer has one consistent recorded ``config_hash``
      (``_single_recorded_config_hash`` -- the same checks as ``write_config_manifest_sidecar``);
    - the sidecar file does not exist;
    - the sidecar's stored ``manifest`` no longer rehashes (``make_config_hash``) to its own
      stored ``config_hash`` (the sidecar itself was edited/corrupted);
    - re-deriving ``effective_config_manifest`` for the given ``(agent, format_id, env, ...)``
      now produces a different hash than the sidecar records (drift since the freeze);
    - the results file's recorded ``config_hash`` no longer matches the sidecar's.
    Returns ``None`` (no exception) when every check passes.
    """
    results_path = Path(results_path)
    recorded_hash = _single_recorded_config_hash(results_path)

    sidecar_path = _sidecar_path(results_path)
    if not sidecar_path.is_file():
        raise ConfigManifestFreezeError(f"sidecar does not exist: {sidecar_path}")

    payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
    stored_hash = payload.get("config_hash")
    stored_manifest = payload.get("manifest")
    rehash = make_config_hash(stored_manifest) if stored_manifest is not None else None
    if stored_hash != rehash:
        raise ConfigManifestFreezeError(
            f"{sidecar_path}: stored manifest does not rehash to its own stored config_hash "
            f"(stored={stored_hash!r}, rehash={rehash!r}) -- the sidecar was edited/corrupted"
        )

    manifest = effective_config_manifest(
        agent=agent, format_id=format_id, env=env,
        model_hash=model_hash, model_manifest_hash=model_manifest_hash,
    )
    computed_hash = make_config_hash(manifest)
    if computed_hash != stored_hash:
        raise ConfigManifestFreezeError(
            f"config_hash mismatch: {sidecar_path} records {stored_hash!r}, but "
            f"effective_config_manifest(agent={agent!r}, format_id={format_id!r}, ...) now "
            f"hashes to {computed_hash!r}"
        )
    if recorded_hash != stored_hash:
        raise ConfigManifestFreezeError(
            f"{results_path}'s recorded config_hash {recorded_hash!r} no longer matches the "
            f"frozen sidecar's config_hash {stored_hash!r}"
        )
