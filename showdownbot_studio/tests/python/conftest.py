from __future__ import annotations

import sys
from pathlib import Path

STUDIO_ROOT = Path(__file__).resolve().parents[2]


def read_normalized_bytes(path: Path) -> bytes:
    """Read a file's bytes with CRLF normalized to LF.

    `core.autocrlf` on Windows checks the same git blob out as either LF or CRLF
    depending on the local machine's git config and this repo's `.gitattributes`
    coverage at checkout time (retroactive attribute changes do not renormalize an
    existing working copy). Raw `path.read_bytes()` hashes are therefore
    checkout-dependent for any file outside an `eol=lf`-enforced path. Fixtures
    compared or hashed against a pinned/recorded digest must normalize line endings
    first so the digest is identical on a CRLF and an LF checkout of the same commit.
    """
    return path.read_bytes().replace(b"\r\n", b"\n")
REPO_ROOT = STUDIO_ROOT.parent
BOT_SRC = REPO_ROOT / "showdown_bot" / "src"
if BOT_SRC.is_dir() and str(BOT_SRC) not in sys.path:
    sys.path.insert(0, str(BOT_SRC))

FIXTURES = STUDIO_ROOT / "fixtures" / "viewer-v0"
SYNTHETIC = STUDIO_ROOT / "tests" / "python" / "synthetic"
SMOKE = REPO_ROOT / "data" / "eval" / "champions-panel-v0" / "smoke-i7a-mega"
