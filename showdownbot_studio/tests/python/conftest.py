from __future__ import annotations

import sys
from pathlib import Path

STUDIO_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = STUDIO_ROOT.parent
BOT_SRC = REPO_ROOT / "showdown_bot" / "src"
if BOT_SRC.is_dir() and str(BOT_SRC) not in sys.path:
    sys.path.insert(0, str(BOT_SRC))

FIXTURES = STUDIO_ROOT / "fixtures" / "viewer-v0"
SYNTHETIC = STUDIO_ROOT / "tests" / "python" / "synthetic"
SMOKE = REPO_ROOT / "data" / "eval" / "champions-panel-v0" / "smoke-i7a-mega"
