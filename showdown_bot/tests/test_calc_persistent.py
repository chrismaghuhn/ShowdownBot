# tests/test_calc_persistent.py
import json, subprocess
from showdown_bot.engine.calc.client import DEFAULT_CALC_DIR


def _types_line(species):
    return json.dumps([{"id": "t0", "kind": "types", "gen": 9, "species": species}],
                      separators=(",", ":")) + "\n"


def test_calc_mjs_server_mode_roundtrips_two_lines():
    proc = subprocess.Popen(["node", "calc.mjs", "--server"], cwd=str(DEFAULT_CALC_DIR),
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1)
    try:
        proc.stdin.write(_types_line("Incineroar")); proc.stdin.flush()
        line1 = proc.stdout.readline()
        proc.stdin.write(_types_line("Flutter Mane")); proc.stdin.flush()
        line2 = proc.stdout.readline()
        r1, r2 = json.loads(line1), json.loads(line2)
        assert isinstance(r1, list) and isinstance(r2, list)     # each line is a JSON array
        assert r1[0]["types"] == ["Fire", "Dark"]
        assert set(r2[0]["types"]) == {"Ghost", "Fairy"}
        assert proc.poll() is None                               # alive after 2 requests
    finally:
        proc.stdin.close()
        rest = proc.stdout.read()                                # everything after line2
        assert rest == "", f"unexpected extra stdout (banner/log breaks the protocol): {rest!r}"
        assert proc.wait(timeout=5) == 0                         # clean EOF exit, code 0
