"""Checks on the test suite itself, for failures that look like successes.

Two have already happened here. A skip guard defaulted to the real archive, so
it never skipped where it mattered and the module it guarded was never proved
to skip at all. A test function was defined twice in one module, so Python kept
the second and the first never ran, while `pytest -q` reported the file green.
Both were invisible in the place anyone looks: the pass count.
"""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

TESTS = Path(__file__).resolve().parent


def module_paths() -> list[Path]:
    return sorted(TESTS.glob("test_*.py"))


def test_no_test_module_defines_a_name_twice() -> None:
    """A shadowed definition is a test that silently stops running."""

    duplicates: list[str] = []
    for path in module_paths():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = Counter(
            node.name
            for node in tree.body
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        )
        duplicates.extend(
            f"{path.name}:{name} defined {count} times"
            for name, count in sorted(names.items())
            if count > 1
        )
    assert not duplicates, "; ".join(duplicates)


def test_every_module_has_at_least_one_test() -> None:
    """A module whose tests were all renamed away still collects as green."""

    empty = [
        path.name
        for path in module_paths()
        if not any(
            isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
            and node.name.startswith("test_")
            for node in ast.parse(path.read_text(encoding="utf-8")).body
        )
    ]
    assert not empty, f"test modules with no tests: {', '.join(empty)}"
