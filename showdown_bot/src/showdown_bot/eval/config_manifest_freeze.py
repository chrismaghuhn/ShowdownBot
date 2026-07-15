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
    """Fail-closed: refuses to write a sidecar that can't be verified against the
    results file it is supposed to describe."""


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

    out_path = results_path.with_name(results_path.name + ".config-manifest.json")
    if out_path.exists():
        raise ConfigManifestFreezeError(
            f"{out_path} already exists -- refusing to silently overwrite a frozen sidecar"
        )

    out_path.write_text(
        json.dumps({"config_hash": computed_hash, "manifest": manifest}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return out_path
