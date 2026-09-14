from __future__ import annotations

from pathlib import Path

import pytest
from jbomohi_tools.render import RenderContext, render_main

OBJECT_ID = "a" * 40


def template_repo(tmp_path: Path, content: bytes) -> Path:
    root = tmp_path / "tools-checkout"
    templates = root / "tools/templates/main"
    templates.mkdir(parents=True)
    (templates / "README.md").write_bytes(content)
    return root


def test_render_rejects_an_unknown_template_token(tmp_path: Path) -> None:
    root = template_repo(tmp_path, b"{{unknown}}\n")
    with pytest.raises(ValueError, match="unknown template token"):
        render_main(root, RenderContext(tools_commit=OBJECT_ID))


def test_render_rejects_a_token_introduced_by_context(tmp_path: Path) -> None:
    root = template_repo(tmp_path, b"{{coverage_tables}}\n")
    context = RenderContext(tools_commit=OBJECT_ID, coverage_tables="{{snapshot}}")
    with pytest.raises(ValueError, match="unresolved template token"):
        render_main(root, context)


def test_render_rejects_a_non_object_id_tools_commit(tmp_path: Path) -> None:
    root = template_repo(tmp_path, b"plain text\n")
    with pytest.raises(ValueError, match="must be a git object id"):
        render_main(root, RenderContext(tools_commit="not-an-object-id"))


def test_render_preserves_literal_double_braces_outside_token_grammar(
    tmp_path: Path,
) -> None:
    literal = b"Use {{Like this}} and {{BPFK Section from tiki|example}}.\n"
    root = template_repo(tmp_path, literal)
    rendered = render_main(root, RenderContext(tools_commit=OBJECT_ID))
    assert rendered["README.md"] == literal


@pytest.mark.parametrize("content", [b"\xef\xbb\xbftext\n", b"text\r\n"])
def test_render_rejects_bom_and_crlf_templates(tmp_path: Path, content: bytes) -> None:
    root = template_repo(tmp_path, content)
    with pytest.raises(ValueError, match="UTF-8/LF without BOM"):
        render_main(root, RenderContext(tools_commit=OBJECT_ID))
