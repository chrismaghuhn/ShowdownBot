"""No cross-module public interface may expose an untyped Variant/Array/Dictionary
(AGENTS.md rule 9, amended 2026-07-25 PR-88 review; spec docs/specs/2026-07-25-phase3-client-design.md
section 10). See the two allowlist files in architecture_allowlists/ for the concrete,
deliberately-scoped exceptions this guard accepts.

Design notes (read before touching the gating logic):

- Field checks (bare `Array`/`Dictionary`, and fully untyped/uninferred `var x = ...`) scan
  every `.gd` file under godot/src/, unconditionally: a value object's fields are its public
  interface regardless of whether the type currently crosses a module boundary. Exempted only
  by the audited-boundary allowlist (`untyped_boundary_allowlist.txt`).
- Signal parameter-list checks scan every file the same way, same exemption.
- Func/static-func checks apply only once a class is used from *outside* its own top-level
  godot/src/ directory (comment-stripped, whole-tree search) -- i.e. once it is genuinely a
  cross-module public interface, not merely public-by-spelling. This is the pre-existing
  cross-module-class mechanism this file has always used, extended to also match
  `static func` (the previous regex only matched bare `func`).
- The `Variant` func/static-func rule has NO allowlist escape hatch at all, by design (AGENTS.md
  rule 9 amendment: "never as a parameter or return type on a cross-module public interface").
  To keep it meaningful without retroactively failing pre-existing Phase-0 utility code that
  predates the Phase-3 module map (bundle/, decision/, diagnostics/, timeline/ -- none of which
  appear in docs/architecture/MODULE_CATALOG.md), this rule additionally requires the declaring
  file to live inside one of the seven catalogued Phase-3 module directories (spec section 4.1):
  net/, protocol/, session/, battle/, ui/, replay/, workspace/. A pre-existing Phase-0 utility
  module is not a "module" in the sense this specific rule governs; a *new* Phase-3 module is
  exactly what F0 is building this guard to protect before net/, protocol/, session/, battle/,
  and ui/ have any production code in them.
- The `Variant` FIELD rule is unconditional on cross-module status (a documented nullable
  scalar field is either compliant or not, regardless of whether anything reaches across a
  boundary to read it today) but IS scoped to the same seven catalogued directories, and is
  exempted only by the new named-value-object allowlist
  (`named_value_object_allowlist.txt`).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from conftest import STUDIO_ROOT  # type: ignore[import-not-found]

_GODOT_SRC = STUDIO_ROOT / "godot" / "src"
_ALLOWLIST_DIR = Path(__file__).parent / "architecture_allowlists"
_AUDITED_BOUNDARY_ALLOWLIST_FILE = _ALLOWLIST_DIR / "untyped_boundary_allowlist.txt"
_VALUE_OBJECT_ALLOWLIST_FILE = _ALLOWLIST_DIR / "named_value_object_allowlist.txt"

# The seven modules named in spec section 4.1 / docs/architecture/MODULE_CATALOG.md. Only
# these top-level godot/src/ directories are "modules" for the func/static-func Variant rule
# and the Variant-field rule; see the module docstring above for why.
_GOVERNED_MODULES = frozenset({"net", "protocol", "session", "battle", "ui", "replay", "workspace"})

_CLASS_NAME_RE = re.compile(r"^class_name\s+(\w+)", re.MULTILINE)
_FUNC_SIG_RE = re.compile(
    r"^(?:static\s+)?func\s+([a-zA-Z_]\w*)\s*\((.*?)\)\s*(?:->\s*([^:]+))?:",
    re.MULTILINE | re.DOTALL,
)
_SIGNAL_RE = re.compile(r"^signal\s+([a-zA-Z_]\w*)\s*(?:\((.*?)\))?", re.MULTILINE)
_FIELD_DECL_RE = re.compile(r"^var\s+([a-zA-Z_]\w*)\s*(:=|:)?\s*(.*)$", re.MULTILINE)
_BARE_CONTAINER_RE = re.compile(r"\b(Array|Dictionary)\b(?!\[)")
_VARIANT_RE = re.compile(r"\bVariant\b")


def _module_dir(path: Path) -> str:
    return path.relative_to(_GODOT_SRC).parts[0]


def _rel(path: Path) -> str:
    return path.relative_to(_GODOT_SRC).as_posix()


def _is_governed(path: Path) -> bool:
    return _module_dir(path) in _GOVERNED_MODULES


def _all_gd_files() -> list[Path]:
    return sorted(_GODOT_SRC.rglob("*.gd"))


def _strip_comments(text: str) -> str:
    # A "#" inside a string literal would be mis-truncated by this, but no file under
    # godot/src/ currently puts a class-name/identifier reference after a "#" inside a
    # string on the same line as other code -- this is solely to stop a comment (e.g. an
    # aside like "# see DiagnosticsPresenter.present") from being misread as a real
    # cross-module usage.
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


def _load_allowlist(path: Path) -> list[str]:
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        entries.append(line)
    return entries


def _is_allowlisted(path: Path, allowlist: list[str]) -> bool:
    rel = _rel(path)
    for entry in allowlist:
        if entry.endswith("/"):
            if rel.startswith(entry):
                return True
        elif rel == entry:
            return True
    return False


def _class_names_by_file(texts: dict[Path, str]) -> dict[Path, str]:
    mapping: dict[Path, str] = {}
    for path, text in texts.items():
        match = _CLASS_NAME_RE.search(text)
        if match:
            mapping[path] = match.group(1)
    return mapping


def _cross_module_classes(class_by_file: dict[Path, str], stripped: dict[Path, str]) -> set[str]:
    cross_module: set[str] = set()
    for decl_path, class_name in class_by_file.items():
        decl_module = _module_dir(decl_path)
        pattern = re.compile(rf"\b{re.escape(class_name)}\b")
        for other_path, text in stripped.items():
            if other_path == decl_path or _module_dir(other_path) == decl_module:
                continue
            if pattern.search(text):
                cross_module.add(class_name)
                break
    return cross_module


def _func_signatures(text: str):
    for match in _FUNC_SIG_RE.finditer(text):
        name, params, ret = match.group(1), match.group(2), match.group(3) or ""
        if name.startswith("_"):
            continue
        yield name, params, ret


def _signal_param_lists(text: str):
    for match in _SIGNAL_RE.finditer(text):
        name, params = match.group(1), match.group(2) or ""
        yield name, params


def _field_kind(colon_op: str | None, rest: str) -> str | None:
    """Classify a `var` field declaration. Returns "container", "variant",
    "untyped_bare", or None (properly typed, non-Variant, non-container)."""
    if colon_op == ":=":
        # Type-inferred shorthand -- statically typed by the compiler, not the untyped
        # container/Variant shape this guard is about.
        return None
    if colon_op == ":":
        type_expr = rest.split("=", 1)[0].strip()
        if type_expr.endswith(":"):
            type_expr = type_expr[:-1].strip()
        if _BARE_CONTAINER_RE.search(type_expr):
            return "container"
        if _VARIANT_RE.search(type_expr):
            return "variant"
        return None
    # No ":" and no ":=" at all -- no type annotation and no inference marker.
    return "untyped_bare"


def _public_field_decls(text: str):
    for match in _FIELD_DECL_RE.finditer(text):
        name, colon_op, rest = match.group(1), match.group(2), match.group(3) or ""
        if name.startswith("_"):
            continue
        kind = _field_kind(colon_op, rest)
        if kind is not None:
            yield name, kind


@pytest.mark.architecture
def test_cross_module_class_scan_finds_at_least_one_cross_module_class():
    # A scan that finds zero cross-module classes has a broken module-dir/identifier match,
    # not a codebase with no shared types -- BundleDTO alone is already used from replay/,
    # decision/, diagnostics/, and workspace/ today.
    texts = {p: p.read_text(encoding="utf-8") for p in _all_gd_files()}
    stripped = {p: _strip_comments(t) for p, t in texts.items()}
    class_by_file = _class_names_by_file(texts)
    found = _cross_module_classes(class_by_file, stripped)
    assert "BundleDTO" in found, found


@pytest.mark.architecture
def test_no_untyped_container_in_cross_module_public_function_signature():
    allowlist = _load_allowlist(_AUDITED_BOUNDARY_ALLOWLIST_FILE)
    texts = {p: p.read_text(encoding="utf-8") for p in _all_gd_files()}
    stripped = {p: _strip_comments(t) for p, t in texts.items()}
    class_by_file = _class_names_by_file(texts)
    cross_module = _cross_module_classes(class_by_file, stripped)
    violations: list[str] = []
    for path, class_name in class_by_file.items():
        if class_name not in cross_module or _is_allowlisted(path, allowlist):
            continue
        for name, params, ret in _func_signatures(texts[path]):
            if _BARE_CONTAINER_RE.search(params) or _BARE_CONTAINER_RE.search(ret):
                violations.append(f"{_rel(path)}::{name}")
    assert not violations, f"untyped container in cross-module public function signature: {violations}"


@pytest.mark.architecture
def test_no_variant_in_cross_module_public_function_signature():
    # No allowlist for this rule by design (AGENTS.md rule 9 amendment) -- see module
    # docstring for why this is scoped to the seven governed module directories instead.
    texts = {p: p.read_text(encoding="utf-8") for p in _all_gd_files()}
    stripped = {p: _strip_comments(t) for p, t in texts.items()}
    class_by_file = _class_names_by_file(texts)
    cross_module = _cross_module_classes(class_by_file, stripped)
    violations: list[str] = []
    for path, class_name in class_by_file.items():
        if class_name not in cross_module or not _is_governed(path):
            continue
        for name, params, ret in _func_signatures(texts[path]):
            if _VARIANT_RE.search(params) or _VARIANT_RE.search(ret):
                violations.append(f"{_rel(path)}::{name}")
    assert not violations, (
        f"Variant on a cross-module public function signature (no allowlist permitted): {violations}"
    )


@pytest.mark.architecture
def test_no_untyped_container_or_untyped_bare_public_field_anywhere():
    allowlist = _load_allowlist(_AUDITED_BOUNDARY_ALLOWLIST_FILE)
    violations: list[str] = []
    for path in _all_gd_files():
        if _is_allowlisted(path, allowlist):
            continue
        text = path.read_text(encoding="utf-8")
        for name, kind in _public_field_decls(text):
            if kind in ("container", "untyped_bare"):
                violations.append(f"{_rel(path)}::{name} ({kind})")
    assert not violations, f"untyped container or untyped bare public field: {violations}"


@pytest.mark.architecture
def test_no_bare_container_in_public_signal_parameter_list():
    allowlist = _load_allowlist(_AUDITED_BOUNDARY_ALLOWLIST_FILE)
    violations: list[str] = []
    for path in _all_gd_files():
        if _is_allowlisted(path, allowlist):
            continue
        text = path.read_text(encoding="utf-8")
        for name, params in _signal_param_lists(text):
            if _BARE_CONTAINER_RE.search(params):
                violations.append(f"{_rel(path)}::signal {name}")
    assert not violations, f"untyped container in signal parameter list: {violations}"


@pytest.mark.architecture
def test_variant_public_field_requires_named_value_object_allowlist():
    allowlist = _load_allowlist(_VALUE_OBJECT_ALLOWLIST_FILE)
    violations: list[str] = []
    for path in _all_gd_files():
        if not _is_governed(path) or _is_allowlisted(path, allowlist):
            continue
        text = path.read_text(encoding="utf-8")
        for name, kind in _public_field_decls(text):
            if kind == "variant":
                violations.append(f"{_rel(path)}::{name}")
    assert not violations, (
        f"Variant public field outside the named-value-object allowlist: {violations}"
    )
