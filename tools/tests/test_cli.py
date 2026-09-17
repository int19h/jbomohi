from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

from jbomohi_tools.archive.irc import FetchReport
from jbomohi_tools.archive.wiki import FetchReport as WikiFetchReport
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
    assert main(["notes", "lint"]) == 2


def test_build_update_verify_cli_wiring(monkeypatch, tmp_path: Path, capsys) -> None:
    config = SimpleNamespace(corpus=tmp_path / "corpus")
    factories = {"wiki": lambda: iter(())}
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr("jbomohi_tools.cli.Config.from_env", lambda: config)
    monkeypatch.setattr(
        "jbomohi_tools.cli.source_factories",
        lambda _config, names: calls.append(("sources", names)) or factories,
    )
    monkeypatch.setattr(
        "jbomohi_tools.cli.build_corpus",
        lambda _config, sources, *, until, backend: (
            calls.append(("build", (sources, until, backend)))
            or SimpleNamespace(
                head="a" * 40, commits=4, events=2, snapshot="snapshot/x"
            )
        ),
    )
    assert main(["build", "--sources", "wiki"]) == 0
    assert calls[0] == ("sources", ["wiki"])
    assert calls[1][1][2] == "fast-import"
    assert calls[1][0] == "build"
    assert "events=2" in capsys.readouterr().out

    assert main(["build", "--sources", "wiki", "--until", "2000-01-01"]) == 1

    monkeypatch.setattr(
        "jbomohi_tools.cli.update_corpus",
        lambda _config, sources: SimpleNamespace(
            head="b" * 40,
            commits=6,
            events=1,
            snapshot="snapshot/y",
            events_by_source={"wiki": 1},
            refreshed=True,
            tagged=True,
        ),
    )
    assert main(["update", "wiki"]) == 0
    printed = capsys.readouterr().out
    assert "events=1 (wiki=1)" in printed
    assert "instructions=refreshed" in printed
    assert "tag=minted" in printed

    monkeypatch.setattr(
        "jbomohi_tools.cli.verify_corpus",
        lambda _corpus: SimpleNamespace(
            commits=6, files=10, sources=2, csv_indexes=1, mail_messages=3
        ),
    )
    assert main(["verify"]) == 0
    assert "mail_messages=3" in capsys.readouterr().out


def test_corpus_status_runs_through_real_cli_configuration(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    root = tmp_path / "tools-checkout"
    corpus = tmp_path / "corpus"
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
    monkeypatch.setenv("JBOMOHI_CORPUS", str(corpus))
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


def test_archive_fetch_cll_cli_wiring(monkeypatch, tmp_path: Path, capsys) -> None:
    config = type("Config", (), {"archive": tmp_path})()
    monkeypatch.setattr("jbomohi_tools.cli.Config.from_env", lambda: config)
    monkeypatch.setattr(
        "jbomohi_tools.cli.fetch_cll",
        lambda archive: type(
            "Report",
            (),
            {
                "refs": {"refs/tags/v1.3.2": "a" * 40},
                "reused_manifest": False,
                "manifest": archive / "manifest.toml",
            },
        )(),
    )
    assert main(["archive", "fetch", "cll"]) == 0
    assert "refs=1 reused=false" in capsys.readouterr().out


def test_archive_fetch_grammars_cli_wiring(monkeypatch, tmp_path: Path, capsys) -> None:
    config = type("Config", (), {"archive": tmp_path})()
    monkeypatch.setattr("jbomohi_tools.cli.Config.from_env", lambda: config)
    monkeypatch.setattr(
        "jbomohi_tools.cli.fetch_grammars",
        lambda _archive, **_kwargs: type(
            "Report",
            (),
            {
                "mirrors": (
                    type("Mirror", (), {"reused_manifest": False})(),
                    type("Mirror", (), {"reused_manifest": True})(),
                ),
                "vendor_manifests": (tmp_path / "camxes.toml",),
            },
        )(),
    )
    assert main(["archive", "fetch", "grammars"]) == 0
    assert "mirrors=2 reused=1 vendor_manifests=1" in capsys.readouterr().out


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


def test_archive_fetch_mail_cli_wiring(monkeypatch, tmp_path: Path, capsys) -> None:
    config = SimpleNamespace(archive=tmp_path)
    calls: list[tuple[Path, str]] = []

    def fake_fetch(archive: Path, list_name: str):
        calls.append((archive, list_name))
        return SimpleNamespace(
            inventory=SimpleNamespace(messages=7),
            manifest=tmp_path / "manifest.toml",
        )

    monkeypatch.setattr("jbomohi_tools.cli.Config.from_env", lambda: config)
    monkeypatch.setattr("jbomohi_tools.cli.fetch_maildir_zip", fake_fetch)
    assert main(["archive", "fetch", "mail", "--list", "lojban-list"]) == 0
    assert calls == [(tmp_path, "lojban-list")]
    assert "list=lojban-list messages=7" in capsys.readouterr().out


def test_archive_fetch_mhonarc_cli_wiring(monkeypatch, tmp_path: Path, capsys) -> None:
    config = SimpleNamespace(archive=tmp_path)
    calls: list[tuple[Path, str, int, int | None]] = []

    def fake_fetch(
        archive: Path,
        list_name: str,
        *,
        start: int,
        max_pages: int | None,
    ):
        calls.append((archive, list_name, start, max_pages))
        return SimpleNamespace(downloaded=2, reused=3, next_missing=5)

    monkeypatch.setattr("jbomohi_tools.cli.Config.from_env", lambda: config)
    monkeypatch.setattr("jbomohi_tools.cli.fetch_mhonarc", fake_fetch)
    assert (
        main(
            [
                "archive",
                "fetch",
                "mhonarc",
                "--list",
                "announce",
                "--start",
                "7",
                "--max-pages",
                "5",
            ]
        )
        == 0
    )
    assert calls == [(tmp_path, "announce", 7, 5)]
    assert "downloaded=2 reused=3 next_missing=5" in capsys.readouterr().out


def test_archive_fetch_jbosnu_raw_cli_wiring(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    config = SimpleNamespace(archive=tmp_path)
    calls: list[Path] = []

    def fake_fetch(archive: Path):
        calls.append(archive)
        return SimpleNamespace(messages=489, manifest=tmp_path / "manifest.toml")

    monkeypatch.setattr("jbomohi_tools.cli.Config.from_env", lambda: config)
    monkeypatch.setattr("jbomohi_tools.cli.fetch_jbosnu_raw", fake_fetch)
    assert main(["archive", "fetch", "jbosnu-raw"]) == 0
    assert calls == [tmp_path]
    assert "messages=489" in capsys.readouterr().out


def test_archive_fetch_old_lojban_list_cli_wiring(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    config = SimpleNamespace(archive=tmp_path)
    calls: list[tuple[Path, int | None]] = []

    def fake_fetch(archive: Path, *, max_pages: int | None):
        calls.append((archive, max_pages))
        return SimpleNamespace(downloaded=2, reused=3, next_missing=6)

    monkeypatch.setattr("jbomohi_tools.cli.Config.from_env", lambda: config)
    monkeypatch.setattr("jbomohi_tools.cli.fetch_old_lojban_list", fake_fetch)
    assert main(["archive", "fetch", "old-lojban-list", "--max-pages", "5"]) == 0
    assert calls == [(tmp_path, 5)]
    assert "downloaded=2 reused=3 next_missing=6" in capsys.readouterr().out


def test_archive_fetch_mail_mboxes_cli_wiring(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    config = SimpleNamespace(archive=tmp_path)
    calls: list[Path] = []

    def fake_fetch(archive: Path):
        calls.append(archive)
        return SimpleNamespace(downloaded=2, reused=3, messages=100)

    monkeypatch.setattr("jbomohi_tools.cli.Config.from_env", lambda: config)
    monkeypatch.setattr("jbomohi_tools.cli.fetch_mail_mboxes", fake_fetch)
    assert main(["archive", "fetch", "mail-mboxes"]) == 0
    assert calls == [tmp_path]
    assert "downloaded=2 reused=3 messages=100" in capsys.readouterr().out


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


def test_archive_ingest_tiki_cli_wiring(monkeypatch, tmp_path: Path, capsys) -> None:
    config = SimpleNamespace(archive=tmp_path / "archive")
    calls: list[tuple[Path, Path, str, str]] = []

    def fake_ingest(
        archive: Path,
        directory: Path,
        export_date: str,
        *,
        character_encoding: str,
    ):
        calls.append((archive, directory, export_date, character_encoding))
        return SimpleNamespace(
            manifests=(tmp_path / "manifest.toml",),
            data=SimpleNamespace(tables={"tiki_pages": (1, 2)}),
            events=3,
        )

    monkeypatch.setattr("jbomohi_tools.cli.Config.from_env", lambda: config)
    monkeypatch.setattr("jbomohi_tools.cli.ingest_tiki_export", fake_ingest)
    assert (
        main(
            [
                "archive",
                "ingest",
                "tiki",
                str(tmp_path / "export"),
                "--export-date",
                "2026-09-13",
            ]
        )
        == 0
    )
    assert calls == [
        (
            config.archive,
            tmp_path / "export",
            "2026-09-13",
            "latin1-transcoded",
        )
    ]
    assert "manifests=1 pages=2 events=3" in capsys.readouterr().out


def test_archive_ingest_wiki_cli_wiring(monkeypatch, tmp_path: Path, capsys) -> None:
    config = SimpleNamespace(archive=tmp_path / "archive")
    calls: list[tuple[Path, Path, str]] = []

    def fake_ingest(archive: Path, directory: Path, export_date: str):
        calls.append((archive, directory, export_date))
        return SimpleNamespace(
            manifests=(tmp_path / "manifest-a.toml", tmp_path / "manifest-b.toml"),
            inventory=SimpleNamespace(
                table_rows={"page": 14_486, "revision": 53_279, "archive": 1_291},
                users=418,
            ),
        )

    monkeypatch.setattr("jbomohi_tools.cli.Config.from_env", lambda: config)
    monkeypatch.setattr("jbomohi_tools.cli.ingest_wiki_sql_export", fake_ingest)
    assert (
        main(
            [
                "archive",
                "ingest",
                "wiki",
                str(tmp_path / "export"),
                "--export-date",
                "2026-09-15",
            ]
        )
        == 0
    )
    assert calls == [(config.archive, tmp_path / "export", "2026-09-15")]
    assert (
        "manifests=2 tables=3 pages=14486 revisions=53279 archive=1291 users=418"
        in capsys.readouterr().out
    )


def test_cll_render_commits_missing_editions_through_the_target(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    config = type(
        "Config", (), {"archive": tmp_path / "archive", "corpus": tmp_path / "corpus"}
    )()
    events = [
        type("Event", (), {"source_id": "cll=one"})(),
        type("Event", (), {"source_id": "cll=two"})(),
        type("Event", (), {"source_id": "cll=three"})(),
    ]
    committed = []
    monkeypatch.setattr("jbomohi_tools.cli.Config.from_env", lambda: config)
    monkeypatch.setattr(
        "jbomohi_tools.cli.init_corpus",
        lambda _config: (type("Status", (), {"head": "a" * 40})(), False),
    )
    monkeypatch.setattr("jbomohi_tools.cli.project_cll", lambda _archive: iter(events))
    monkeypatch.setattr(
        "jbomohi_tools.cli.git_output",
        lambda _corpus, _args: "Source-Id: cll=one\n",
    )
    monkeypatch.setattr(
        "jbomohi_tools.cli.commit_event",
        lambda event, corpus: committed.append((event.source_id, corpus)) or "b" * 40,
    )
    assert main(["cll", "render", "two"]) == 0
    assert committed == [("cll=two", config.corpus)]
    assert "edition=two commits=1" in capsys.readouterr().out


def test_cll_render_rejects_a_nonprefix_existing_edition(
    monkeypatch, tmp_path: Path
) -> None:
    config = type(
        "Config", (), {"archive": tmp_path / "archive", "corpus": tmp_path / "corpus"}
    )()
    events = [
        type("Event", (), {"source_id": "cll=one"})(),
        type("Event", (), {"source_id": "cll=two"})(),
    ]
    monkeypatch.setattr("jbomohi_tools.cli.Config.from_env", lambda: config)
    monkeypatch.setattr(
        "jbomohi_tools.cli.init_corpus",
        lambda _config: (type("Status", (), {"head": "a" * 40})(), False),
    )
    monkeypatch.setattr("jbomohi_tools.cli.project_cll", lambda _archive: iter(events))
    monkeypatch.setattr(
        "jbomohi_tools.cli.git_output",
        lambda _corpus, _args: "Source-Id: cll=two\n",
    )
    assert main(["cll", "render", "two"]) == 1


def test_archive_fetch_wiki_cli_wiring(monkeypatch, tmp_path: Path, capsys) -> None:
    config = SimpleNamespace(archive=tmp_path)
    calls: list[tuple[Path, str | None]] = []

    def fake_fetch(archive: Path, since: str | None) -> WikiFetchReport:
        calls.append((archive, since))
        return WikiFetchReport((tmp_path / "manifest.toml",), 2, 3, 4, 5, 6)

    monkeypatch.setattr("jbomohi_tools.cli.Config.from_env", lambda: config)
    monkeypatch.setattr("jbomohi_tools.cli.fetch_wiki", fake_fetch)
    assert main(["archive", "fetch", "wiki", "--since", "2026-01-01T00:00:00Z"]) == 0
    assert calls == [(tmp_path, "2026-01-01T00:00:00Z")]
    assert (
        "pages=2 revision_batches=3 log_batches=4 media_batches=5 reused=6 manifests=1"
        in capsys.readouterr().out
    )
