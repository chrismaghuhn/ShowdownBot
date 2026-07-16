# SUPERSEDED — I7b-C opponent-Mega smoke with a Windows-byte-specific `config_hash`

**Do not cite this run's `config_hash`. Do not re-hash these rows.**

This is a real, complete 2-battle I7b-C opponent-Mega safety smoke (run once,
`run_id f61212da239c9ee6`, `git_sha 96671cb31f3eaece9ff3b9544803d5bd2f1f76f7`,
2/2 normal, 0 crashes, 0 invalid choices, 19/19 standard gates PASS). Its
telemetry, decision-index join and evidence gate were all valid.

It is superseded for exactly one reason: its recorded **`config_hash`
`5fb04622afebd59f` is a Windows-byte-specific value**.

At the time of this run, `config_hash` was built from raw file bytes
(`format_config_hash` = `sha1(source_path.read_bytes())`, `file_content_hash` =
`sha1(path.read_bytes())`) over files that `core.autocrlf` checked out as CRLF on
Windows and LF on Linux. The identical configuration therefore hashed to
`5fb04622afebd59f` on Windows and `b3cb6ea1a4836060` on Linux. `config_hash` was
not an identity of the configuration; it was an identity of the configuration
*plus the host's line endings*.

That defect is fixed on `main` (`text eol=lf` for every raw-byte-hashed
provenance input, plus a `provenance-bytes` CI job that asserts both platforms
reach the same hash). The smoke was re-run with an **identical schedule and seed
base** under the LF-stable `config_hash` `b3cb6ea1a4836060`; that run is the
active evidence at `../smoke-i7b-mega/`.

## Why this is kept rather than deleted or re-hashed

The rows record what the run that actually happened computed. Rewriting
`config_hash` to the LF value would falsify it: no run ever produced that
combination of bytes. The honest options are to mark the run as historical or to
re-validate it with an unchanged schedule/seed — the latter was done, and this
directory is the former.

## What remains valid here

Everything except the `config_hash`'s cross-platform meaning: the battles, seeds,
decision traces, opponent-Mega sidecar rows, the decision-index join, and the
19/19 standard safety gates. `config_hash` is internally consistent within this
run (all rows agree, and the config-manifest sidecar rehashes to it **on
Windows**); it simply cannot be reproduced on another platform, which is why it
must not be compared against, or joined with, any post-fix run.

The verdict report for the active, LF-stable run is
`reports/champions-panel-v0-i7b-mega-smoke.md`.
