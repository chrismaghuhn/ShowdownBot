import ast, pathlib

SRC = pathlib.Path(__file__).resolve().parents[1] / "src" / "showdown_bot"
GUARDED = ("battle", "client", "engine")

def _imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            yield node.module
        elif isinstance(node, ast.Import):
            for n in node.names:
                yield n.name

def test_no_live_path_imports_outcome_join():
    offenders = []
    for pkg in GUARDED:
        for py in (SRC / pkg).rglob("*.py"):
            if any("outcome_join" in m for m in _imports(py)):
                offenders.append(str(py))
    # live learning export/reranker paths must not import it either
    for py in (SRC / "learning").glob("*.py"):
        if any("outcome_join" in m for m in _imports(py)):
            offenders.append(str(py))
    assert offenders == [], f"outcome_join imported by live path: {offenders}"
