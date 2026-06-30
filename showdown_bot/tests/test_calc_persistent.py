# tests/test_calc_persistent.py
import json
import os
import subprocess
import tempfile
import textwrap
import threading
import time
from pathlib import Path

import pytest

from showdown_bot.engine.calc.client import (
    DEFAULT_CALC_DIR,
    CalcError,
    SubprocessCalcBackend,
)
from showdown_bot.engine.calc.models import CalcMon, DamageRequest


def _types_line(species):
    return (
        json.dumps(
            [{"id": "t0", "kind": "types", "gen": 9, "species": species}],
            separators=(",", ":"),
        )
        + "\n"
    )


def test_calc_mjs_server_mode_roundtrips_two_lines():
    proc = subprocess.Popen(
        ["node", "calc.mjs", "--server"],
        cwd=str(DEFAULT_CALC_DIR),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        bufsize=1,
    )
    try:
        proc.stdin.write(_types_line("Incineroar"))
        proc.stdin.flush()
        line1 = proc.stdout.readline()
        proc.stdin.write(_types_line("Flutter Mane"))
        proc.stdin.flush()
        line2 = proc.stdout.readline()
        r1, r2 = json.loads(line1), json.loads(line2)
        assert isinstance(r1, list) and isinstance(r2, list)  # each line is a JSON array
        assert r1[0]["types"] == ["Fire", "Dark"]
        assert set(r2[0]["types"]) == {"Ghost", "Fairy"}
        assert proc.poll() is None  # alive after 2 requests
    finally:
        proc.stdin.close()
        rest = proc.stdout.read()  # everything after line2
        assert rest == "", f"unexpected extra stdout (banner/log breaks the protocol): {rest!r}"
        assert proc.wait(timeout=5) == 0  # clean EOF exit, code 0


# ---------------------------------------------------------------------------
# Task 2a-2 tests: PersistentCalcBackend
# ---------------------------------------------------------------------------

# Import here so FAIL is "ImportError" until implemented
try:
    from showdown_bot.engine.calc.client import PersistentCalcBackend
except ImportError:
    PersistentCalcBackend = None  # type: ignore[assignment,misc]


@pytest.fixture
def sample_damage_requests():
    """Two real DamageRequests with explicit ids for ordering check."""
    req1 = DamageRequest(
        id="r0",
        attacker=CalcMon(
            species="Incineroar",
            level=50,
            nature="Adamant",
            evs={"atk": 252},
            ability="Intimidate",
        ),
        defender=CalcMon(
            species="Flutter Mane",
            level=50,
            nature="Timid",
            evs={"hp": 252, "spd": 252},
        ),
        move="Knock Off",
        field={"gameType": "Doubles"},
        gen=9,
    )
    req2 = DamageRequest(
        id="r1",
        attacker=CalcMon(
            species="Flutter Mane",
            level=50,
            nature="Timid",
            evs={"spa": 252, "spe": 252},
            ability="Protosynthesis",
        ),
        defender=CalcMon(
            species="Incineroar",
            level=50,
            nature="Adamant",
            evs={"hp": 252, "spd": 4},
        ),
        move="Shadow Ball",
        field={"gameType": "Doubles"},
        gen=9,
    )
    return [req1, req2]


# ---------------------------------------------------------------------------
# Golden tests
# ---------------------------------------------------------------------------


def test_persistent_matches_oneshot_types_and_stats():
    """PersistentCalcBackend must return byte-for-byte identical results for types + stats."""
    assert PersistentCalcBackend is not None, "PersistentCalcBackend not yet implemented"
    one = SubprocessCalcBackend()
    persistent = PersistentCalcBackend()
    try:
        species = ["Incineroar", "Flutter Mane"]
        assert persistent.types_batch(species) == one.types_batch(species)

        # stats: two realistic CalcMon specs
        specs = [
            CalcMon(species="Incineroar", level=50, nature="Adamant", evs={"hp": 252, "atk": 4}),
            CalcMon(species="Flutter Mane", level=50, nature="Timid", evs={"spa": 252, "spe": 252}),
        ]
        one_stats = one.stats_batch(specs)
        pers_stats = persistent.stats_batch(specs)
        assert pers_stats == one_stats, f"stats mismatch:\none_shot={one_stats}\npersistent={pers_stats}"
    finally:
        persistent.close()


def test_persistent_matches_oneshot_damage_batch(sample_damage_requests):
    """Golden: same ids, order, count, and (min, max, max_hp) values."""
    assert PersistentCalcBackend is not None, "PersistentCalcBackend not yet implemented"
    one = SubprocessCalcBackend()
    persistent = PersistentCalcBackend()
    try:
        a = one.calc_batch(sample_damage_requests)
        b = persistent.calc_batch(sample_damage_requests)
        assert [r.id for r in a] == [r.id for r in b], "ids/order mismatch"
        assert len(a) == len(b), "count mismatch"
        one_triples = [(r.min_damage, r.max_damage, r.max_hp) for r in a]
        per_triples = [(r.min_damage, r.max_damage, r.max_hp) for r in b]
        assert one_triples == per_triples, (
            f"damage values differ:\none_shot={one_triples}\npersistent={per_triples}"
        )
    finally:
        persistent.close()


def test_close_is_idempotent():
    assert PersistentCalcBackend is not None, "PersistentCalcBackend not yet implemented"
    b = PersistentCalcBackend()
    b.types_batch(["Incineroar"])
    b.close()
    b.close()  # must not raise


# ---------------------------------------------------------------------------
# Recovery / fault-injection tests (fake servers)
# ---------------------------------------------------------------------------

def _write_fake_server(path: Path, script: str) -> None:
    """Write a tiny fake Node server script."""
    path.write_text(textwrap.dedent(script), encoding="utf-8")


def _make_backend(script_path: Path, timeout_ms: int = 1000) -> "PersistentCalcBackend":
    return PersistentCalcBackend(
        calc_dir=script_path.parent,
        script=script_path.name,
        timeout_ms=timeout_ms,
    )


def _simple_payload() -> list:
    return [{"id": "t0", "kind": "types", "gen": 9, "species": "Incineroar"}]


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


def test_recovery_crash_before_response(tmp_dir):
    """Process exits before responding → backend restarts and succeeds on retry."""
    assert PersistentCalcBackend is not None, "PersistentCalcBackend not yet implemented"

    # marker file: if present, the SECOND generation, respond normally
    marker = tmp_dir / "gen2.marker"
    script = tmp_dir / "fake_crash.mjs"
    _write_fake_server(
        script,
        f"""\
        import {{ createInterface }} from 'node:readline';
        import {{ existsSync, writeFileSync }} from 'node:fs';
        const markerPath = {json.dumps(str(marker).replace(chr(92), '/'))};
        const rl = createInterface({{ input: process.stdin, crlfDelay: Infinity }});
        rl.on('line', (raw) => {{
          if (existsSync(markerPath)) {{
            // second generation: respond normally
            const reqs = JSON.parse(raw);
            const result = reqs.map(r => ({{ id: r.id, types: ['Fire', 'Dark'] }}));
            process.stdout.write(JSON.stringify(result) + '\\n');
          }} else {{
            // first generation: write marker then exit without responding
            writeFileSync(markerPath, '');
            process.exit(1);
          }}
        }});
        rl.on('close', () => process.exit(0));
        """,
    )

    b = _make_backend(script)
    try:
        result = b._run(_simple_payload())
        assert result[0]["types"] == ["Fire", "Dark"]
        assert b.spawn_count == 2  # first spawn + one restart
    finally:
        b.close()


def test_recovery_timeout_hang(tmp_dir):
    """Process hangs forever → timeout → kill + restart + retry succeeds."""
    assert PersistentCalcBackend is not None, "PersistentCalcBackend not yet implemented"

    marker = tmp_dir / "gen2.marker"
    script = tmp_dir / "fake_hang.mjs"
    _write_fake_server(
        script,
        f"""\
        import {{ createInterface }} from 'node:readline';
        import {{ existsSync, writeFileSync }} from 'node:fs';
        const markerPath = {json.dumps(str(marker).replace(chr(92), '/'))};
        const rl = createInterface({{ input: process.stdin, crlfDelay: Infinity }});
        rl.on('line', (raw) => {{
          if (existsSync(markerPath)) {{
            const reqs = JSON.parse(raw);
            const result = reqs.map(r => ({{ id: r.id, types: ['Fire', 'Dark'] }}));
            process.stdout.write(JSON.stringify(result) + '\\n');
          }} else {{
            writeFileSync(markerPath, '');
            // hang: do nothing, don't respond
          }}
        }});
        rl.on('close', () => process.exit(0));
        """,
    )

    b = _make_backend(script, timeout_ms=500)
    try:
        result = b._run(_simple_payload())
        assert result[0]["types"] == ["Fire", "Dark"]
        assert b.spawn_count == 2
    finally:
        b.close()


def test_recovery_malformed_json(tmp_dir):
    """Process writes malformed JSON → restart + retry succeeds."""
    assert PersistentCalcBackend is not None, "PersistentCalcBackend not yet implemented"

    marker = tmp_dir / "gen2.marker"
    script = tmp_dir / "fake_malformed.mjs"
    _write_fake_server(
        script,
        f"""\
        import {{ createInterface }} from 'node:readline';
        import {{ existsSync, writeFileSync }} from 'node:fs';
        const markerPath = {json.dumps(str(marker).replace(chr(92), '/'))};
        const rl = createInterface({{ input: process.stdin, crlfDelay: Infinity }});
        rl.on('line', (raw) => {{
          if (existsSync(markerPath)) {{
            const reqs = JSON.parse(raw);
            const result = reqs.map(r => ({{ id: r.id, types: ['Fire', 'Dark'] }}));
            process.stdout.write(JSON.stringify(result) + '\\n');
          }} else {{
            writeFileSync(markerPath, '');
            process.stdout.write('not valid json {{\\n');
          }}
        }});
        rl.on('close', () => process.exit(0));
        """,
    )

    b = _make_backend(script)
    try:
        result = b._run(_simple_payload())
        assert result[0]["types"] == ["Fire", "Dark"]
        assert b.spawn_count == 2
    finally:
        b.close()


def test_recovery_non_list_response(tmp_dir):
    """Process writes a JSON object (not a list) → restart + retry succeeds."""
    assert PersistentCalcBackend is not None, "PersistentCalcBackend not yet implemented"

    marker = tmp_dir / "gen2.marker"
    script = tmp_dir / "fake_nonlist.mjs"
    _write_fake_server(
        script,
        f"""\
        import {{ createInterface }} from 'node:readline';
        import {{ existsSync, writeFileSync }} from 'node:fs';
        const markerPath = {json.dumps(str(marker).replace(chr(92), '/'))};
        const rl = createInterface({{ input: process.stdin, crlfDelay: Infinity }});
        rl.on('line', (raw) => {{
          if (existsSync(markerPath)) {{
            const reqs = JSON.parse(raw);
            const result = reqs.map(r => ({{ id: r.id, types: ['Fire', 'Dark'] }}));
            process.stdout.write(JSON.stringify(result) + '\\n');
          }} else {{
            writeFileSync(markerPath, '');
            process.stdout.write(JSON.stringify({{ error: 'global error' }}) + '\\n');
          }}
        }});
        rl.on('close', () => process.exit(0));
        """,
    )

    b = _make_backend(script)
    try:
        result = b._run(_simple_payload())
        assert result[0]["types"] == ["Fire", "Dark"]
        assert b.spawn_count == 2
    finally:
        b.close()


def test_recovery_retry_also_fails(tmp_dir):
    """Both generations fail → CalcError raised."""
    assert PersistentCalcBackend is not None, "PersistentCalcBackend not yet implemented"

    script = tmp_dir / "fake_always_crash.mjs"
    _write_fake_server(
        script,
        """\
        import { createInterface } from 'node:readline';
        const rl = createInterface({ input: process.stdin, crlfDelay: Infinity });
        rl.on('line', () => { process.exit(1); });
        rl.on('close', () => process.exit(0));
        """,
    )

    b = _make_backend(script)
    try:
        with pytest.raises(CalcError):
            b._run(_simple_payload())
    finally:
        b.close()


def test_semantic_per_item_error_no_restart(tmp_dir):
    """Per-item {id,error} in the LIST is SEMANTIC → no restart (spawn_count unchanged)."""
    assert PersistentCalcBackend is not None, "PersistentCalcBackend not yet implemented"

    script = tmp_dir / "fake_semantic_error.mjs"
    _write_fake_server(
        script,
        """\
        import { createInterface } from 'node:readline';
        const rl = createInterface({ input: process.stdin, crlfDelay: Infinity });
        rl.on('line', (raw) => {
          const reqs = JSON.parse(raw);
          // Return a list with per-item errors (semantic)
          const result = reqs.map(r => ({ id: r.id, error: 'unknown species' }));
          process.stdout.write(JSON.stringify(result) + '\\n');
        });
        rl.on('close', () => process.exit(0));
        """,
    )

    b = _make_backend(script)
    try:
        # _run should succeed (returns a list with per-item errors); spawn_count stays at 1
        b.types_batch(["Incineroar"])  # prime first spawn
        initial_spawn_count = b.spawn_count
        # _run returns the list; per-item errors surface via DamageResult.from_json at the caller
        payload = [{"id": "t0", "kind": "types", "gen": 9, "species": "Incineroar"}]
        data = b._run(payload)
        # The list was returned successfully - no restart
        assert b.spawn_count == initial_spawn_count, (
            f"spawn_count changed from {initial_spawn_count} to {b.spawn_count} — "
            f"semantic error triggered an unwanted restart"
        )
        # The per-item error is present in the returned data
        assert data[0].get("error") is not None
    finally:
        b.close()


def test_concurrency_two_threads_get_correct_results():
    """Two threads call types_batch with DIFFERENT species; both get non-swapped results."""
    assert PersistentCalcBackend is not None, "PersistentCalcBackend not yet implemented"

    b = PersistentCalcBackend()
    results = {}
    errors = {}

    def call_types(species, key):
        try:
            results[key] = b.types_batch([species])
        except Exception as e:
            errors[key] = e

    t1 = threading.Thread(target=call_types, args=("Incineroar", "incineroar"))
    t2 = threading.Thread(target=call_types, args=("Flutter Mane", "flutter_mane"))
    t1.start()
    t2.start()
    t1.join(timeout=30)
    t2.join(timeout=30)

    try:
        assert not errors, f"Thread errors: {errors}"
        assert "incineroar" in results and "flutter_mane" in results
        assert results["incineroar"] == [["Fire", "Dark"]], (
            f"Incineroar types wrong: {results['incineroar']}"
        )
        assert set(results["flutter_mane"][0]) == {"Ghost", "Fairy"}, (
            f"Flutter Mane types wrong: {results['flutter_mane']}"
        )
    finally:
        b.close()
