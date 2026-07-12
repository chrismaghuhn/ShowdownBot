import ast
from pathlib import Path


def test_planner_has_no_result_or_analyzer_imports():
    source = (Path(__file__).parents[2] / "src/showdown_bot/analysis/generalisation/planner.py").read_text(
        encoding="utf-8")
    modules = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.append(node.module or "")
    forbidden = (".observations", ".coverage", ".metrics", ".compare", ".runner",
                 "eval.result_jsonl", "eval.report")
    assert not any(token in module for module in modules for token in forbidden)
