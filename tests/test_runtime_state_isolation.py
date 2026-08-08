"""AST guard: DiscoveryPipelineConfig persist calls must pin durable paths.

Catches the mutation where a test constructs DiscoveryPipelineConfig that
persists (default, or any non-literal-False persist) but omits pool_path /
queue_path / atoms_path, or binds them to obvious data/state defaults,
allowing fallback writes into the active repo data/state/ tree.
"""

from __future__ import annotations

import ast
from pathlib import Path

REQUIRED_PATH_KEYS = ("pool_path", "queue_path", "atoms_path")
UNSAFE_DEFAULT_PATH_NAMES = frozenset(
    {
        "DEFAULT_POOL_PATH",
        "DEFAULT_QUEUE_PATH",
        "DEFAULT_ATOMS_PATH",
    }
)
TESTS_DIR = Path(__file__).resolve().parent


def _literal_persist_false(node: ast.Call) -> bool:
    for kw in node.keywords:
        if kw.arg != "persist":
            continue
        return isinstance(kw.value, ast.Constant) and kw.value.value is False
    return False


def _keyword_map(node: ast.Call) -> dict[str, ast.AST]:
    return {kw.arg: kw.value for kw in node.keywords if kw.arg is not None}


def _is_discovery_pipeline_config_call(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id == "DiscoveryPipelineConfig"
    if isinstance(func, ast.Attribute):
        return func.attr == "DiscoveryPipelineConfig"
    return False


def _contains_data_state(text: str) -> bool:
    return "data/state" in text.replace("\\", "/")


def _is_default_path_name(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return node.id in UNSAFE_DEFAULT_PATH_NAMES
    if isinstance(node, ast.Attribute):
        return node.attr in UNSAFE_DEFAULT_PATH_NAMES
    return False


def _is_obviously_unsafe_path_expr(node: ast.AST) -> bool:
    """Heuristic only: literals / f-string fragments / known default names."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return _contains_data_state(node.value)
    if isinstance(node, ast.JoinedStr):
        return any(
            isinstance(part, ast.Constant)
            and isinstance(part.value, str)
            and _contains_data_state(part.value)
            for part in node.values
        )
    if _is_default_path_name(node):
        return True
    if isinstance(node, ast.Call):
        return any(_is_obviously_unsafe_path_expr(arg) for arg in node.args)
    return False


def _scan_file(path: Path) -> list[tuple[str, int, str, list[str]]]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    violations: list[tuple[str, int, str, list[str]]] = []
    rel = path.name
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not _is_discovery_pipeline_config_call(node):
            continue
        if _literal_persist_false(node):
            continue
        keywords = _keyword_map(node)
        missing = [key for key in REQUIRED_PATH_KEYS if key not in keywords]
        unsafe = [
            key
            for key in REQUIRED_PATH_KEYS
            if key in keywords and _is_obviously_unsafe_path_expr(keywords[key])
        ]
        if missing:
            violations.append((rel, node.lineno, "missing", missing))
        if unsafe:
            violations.append((rel, node.lineno, "unsafe", unsafe))
    return violations


def _discovery_test_files() -> list[Path]:
    return sorted(TESTS_DIR.glob("test_discovery*.py"))


def test_persist_true_discovery_pipeline_config_requires_explicit_paths():
    files = _discovery_test_files()
    assert files, "expected tests/test_discovery*.py to exist for AST scan"

    violations: list[tuple[str, int, str, list[str]]] = []
    for path in files:
        violations.extend(_scan_file(path))

    if not violations:
        return

    lines = [
        f"{filename}:{lineno} {kind} keys: {', '.join(keys)}"
        for filename, lineno, kind, keys in violations
    ]
    raise AssertionError(
        "DiscoveryPipelineConfig persist calls must pass explicit "
        "pool_path, queue_path, and atoms_path keyword args without "
        "obvious data/state defaults; "
        "violations:\n" + "\n".join(lines)
    )


def _write_synth(tmp_path: Path, name: str, source: str) -> Path:
    path = tmp_path / name
    path.write_text(source, encoding="utf-8")
    return path


def test_scan_omitted_persist_is_violation(tmp_path: Path):
    """persist defaults True; omitting it with no durable paths must violate."""
    path = _write_synth(
        tmp_path,
        "omit_persist.py",
        "DiscoveryPipelineConfig(fetch=False)\n",
    )
    assert _scan_file(path), (
        "omitted persist defaults to True and must be reported as a violation"
    )


def test_scan_persist_false_may_omit_paths(tmp_path: Path):
    path = _write_synth(
        tmp_path,
        "persist_false.py",
        "DiscoveryPipelineConfig(persist=False)\n",
    )
    assert _scan_file(path) == []


def test_scan_literal_data_state_path_is_violation(tmp_path: Path):
    """All keys present is not enough if any path is a literal under data/state."""
    path = _write_synth(
        tmp_path,
        "literal_state.py",
        (
            "DiscoveryPipelineConfig(\n"
            "    persist=True,\n"
            '    pool_path="data/state/candidate_pool.json",\n'
            '    queue_path="data/state/research_review_queue.json",\n'
            '    atoms_path="data/state/research_atoms.json",\n'
            ")\n"
        ),
    )
    assert _scan_file(path), (
        "literal data/state paths must be violations even when all keys exist"
    )


def test_scan_tmp_path_expressions_are_safe(tmp_path: Path):
    """All three durable path kwargs derived from tmp_path must be allowed."""
    path = _write_synth(
        tmp_path,
        "tmp_safe.py",
        (
            "DiscoveryPipelineConfig(\n"
            "    persist=True,\n"
            '    pool_path=str(tmp_path / "pool.json"),\n'
            '    queue_path=str(tmp_path / "queue.json"),\n'
            '    atoms_path=str(tmp_path / "atoms.json"),\n'
            ")\n"
        ),
    )
    assert _scan_file(path) == []
