from __future__ import annotations

from jbomohi_tools.cli import main, parser


def test_complete_command_skeleton_is_registered() -> None:
    help_text = parser().format_help()
    for command in (
        "corpus",
        "archive",
        "build",
        "update",
        "verify",
        "cll",
        "who",
        "notes",
        "cite",
    ):
        assert command in help_text


def test_unimplemented_command_is_explicit(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "jbomohi_tools.cli.Config.from_env",
        lambda: object(),
    )
    assert main(["build"]) == 2
