from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

from jbomohi_tools.archive.irc import FetchReport
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


def test_corpus_status_runs_through_real_cli_configuration(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    root = tmp_path / "tools-checkout"
    corpus = root / "corpus"
    subprocess.run(
        ["git", "init", "--initial-branch=tools", str(root)],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "init", "--initial-branch=main", str(corpus)],
        check=True,
        capture_output=True,
        text=True,
    )
    monkeypatch.chdir(root)
    assert main(["corpus", "status"]) == 0
    assert f"corpus ready: path={corpus}" in capsys.readouterr().out


def test_archive_fetch_irc_cli_wiring(monkeypatch, tmp_path: Path, capsys) -> None:
    config = SimpleNamespace(archive=tmp_path)
    calls: list[tuple[Path, str | None]] = []

    def fake_fetch(archive: Path, since: str | None) -> FetchReport:
        calls.append((archive, since))
        return FetchReport((tmp_path / "manifest.toml",), 3, 4)

    monkeypatch.setattr("jbomohi_tools.cli.Config.from_env", lambda: config)
    monkeypatch.setattr("jbomohi_tools.cli.fetch_irc", fake_fetch)
    assert main(["archive", "fetch", "irc", "--since", "2026-01-01"]) == 0
    assert calls == [(tmp_path, "2026-01-01")]
    assert "downloaded=3 reused=4 manifests=1" in capsys.readouterr().out


def test_archive_fetch_dictionary_cli_wiring(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    config = SimpleNamespace(archive=tmp_path)
    calls: list[tuple[Path, str | None]] = []

    def fake_fetch(archive: Path, since: str | None):
        calls.append((archive, since))
        return SimpleNamespace(pages=2, changes=3, next_cursor="next")

    monkeypatch.setattr("jbomohi_tools.cli.Config.from_env", lambda: config)
    monkeypatch.setattr("jbomohi_tools.cli.fetch_changes", fake_fetch)
    assert main(["archive", "fetch", "dict", "--since", "cursor"]) == 0
    assert calls == [(tmp_path, "cursor")]
    assert "pages=2 changes=3 next_cursor=next" in capsys.readouterr().out


def test_archive_ingest_dictionary_cli_wiring(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    config = SimpleNamespace(archive=tmp_path / "archive")
    calls: list[tuple[Path, Path, str]] = []

    def fake_ingest(archive: Path, directory: Path, export_date: str):
        calls.append((archive, directory, export_date))
        return SimpleNamespace(
            manifests=(tmp_path / "manifest.toml",),
            lensisku=SimpleNamespace(tables={"valsi": (1, 2)}),
            jbovlaste=SimpleNamespace(tables={"valsi": (1,)}),
        )

    monkeypatch.setattr("jbomohi_tools.cli.Config.from_env", lambda: config)
    monkeypatch.setattr("jbomohi_tools.cli.ingest_dictionary_exports", fake_ingest)
    assert (
        main(
            [
                "archive",
                "ingest",
                "dictionary",
                str(tmp_path / "export"),
                "--export-date",
                "2026-09-13",
            ]
        )
        == 0
    )
    assert calls == [(config.archive, tmp_path / "export", "2026-09-13")]
    assert "manifests=1 lensisku_words=2 jbovlaste_words=1" in capsys.readouterr().out
