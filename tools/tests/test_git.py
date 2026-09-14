from __future__ import annotations

import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from jbomohi_tools.git import (
    Event,
    EventError,
    GitError,
    Identity,
    commit_event,
    run_git,
)


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def unborn_worktree(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "--initial-branch=main")
    return repo


def base_event(**changes: object) -> Event:
    fields: dict[str, object] = {
        "source": "wiki",
        "source_id": "revid=1",
        "event": "created",
        "time_confidence": "exact",
        "source_time": datetime(2004, 1, 2, 3, 4, 5, tzinfo=UTC),
        "summary": "create Test (rev 1)",
        "author": Identity.namespaced("mw.lojban.org", "test user"),
        "changes": {"wiki/main/Test.wiki": "first\n"},
        "trailers": {"Page-Id": "7"},
    }
    fields.update(changes)
    return Event(**fields)  # type: ignore[arg-type]


def test_commit_event_sets_source_identity_date_message_and_tree(
    tmp_path: Path,
) -> None:
    corpus = unborn_worktree(tmp_path)
    commit = commit_event(base_event(), corpus)
    assert commit == git(corpus, "rev-parse", "HEAD")
    assert (corpus / "wiki/main/Test.wiki").read_text() == "first\n"
    assert git(corpus, "status", "--porcelain") == ""
    metadata = git(corpus, "show", "-s", "--format=%an%n%ae%n%aI%n%cn%n%ce%n%cI%n%B")
    lines = metadata.splitlines()
    assert lines[:6] == [
        "test user",
        "test%20user@mw.lojban.org",
        "2004-01-02T03:04:05Z",
        "test user",
        "test%20user@mw.lojban.org",
        "2004-01-02T03:04:05Z",
    ]
    assert "wiki: create Test (rev 1)" in metadata
    assert "Source: wiki" in metadata
    assert "Source-Id: revid=1" in metadata
    assert "Event: created" in metadata
    assert "Time-Confidence: exact" in metadata
    assert "Page-Id: 7" in metadata


def test_commit_event_uses_the_configured_corpus_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus = unborn_worktree(tmp_path)
    monkeypatch.setenv("JBOMOHI_CORPUS", str(corpus))
    commit = commit_event(base_event())
    assert commit == git(corpus, "rev-parse", "HEAD")


def test_pre_epoch_event_clamps_git_date_and_keeps_source_date(tmp_path: Path) -> None:
    corpus = unborn_worktree(tmp_path)
    event = base_event(
        source="llg",
        source_id="llg=paper-1960",
        event="import",
        time_confidence="pre-epoch",
        source_time=datetime(1960, 5, 1, tzinfo=UTC),
        source_date="1960-05-01",
        summary="import paper-1960",
        author=Identity.tool(),
        changes={"llg/paper.txt": "historical text\n"},
    )
    commit_event(event, corpus)
    assert git(corpus, "show", "-s", "--format=%aI") == "1970-01-01T00:00:00Z"
    assert "Source-Date: 1960-05-01" in git(corpus, "show", "-s", "--format=%B")


def test_window_event_preserves_bounds_and_source_time(tmp_path: Path) -> None:
    corpus = unborn_worktree(tmp_path)
    event = base_event(
        time_confidence="window",
        event_window="2004-01-01..2004-01-03",
    )
    commit_event(event, corpus)
    message = git(corpus, "show", "-s", "--format=%B")
    assert "Event-Window: 2004-01-01..2004-01-03" in message
    assert git(corpus, "show", "-s", "--format=%aI") == "2004-01-02T03:04:05Z"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"summary": "x" * 80}, "maximum is 72"),
        ({"source_time": datetime(2000, 1, 1)}, "UTC offset"),  # noqa: DTZ001
        (
            {"source_time": datetime(2000, 1, 1, 0, 0, 0, 1, tzinfo=UTC)},
            "whole-second precision",
        ),
        (
            {"source_time": datetime(1960, 1, 1, tzinfo=UTC)},
            "dates before the epoch",
        ),
        (
            {
                "time_confidence": "pre-epoch",
                "source_date": "2000-01-01",
                "source_time": datetime(2000, 1, 1, tzinfo=UTC),
            },
            "pre-epoch confidence",
        ),
        ({"time_confidence": "window"}, "require Event-Window"),
        (
            {"time_confidence": "window", "event_window": "2004-01-03..2004-01-01"},
            "start must not be after",
        ),
        (
            {"time_confidence": "window", "event_window": "2004-01-01..not-a-date"},
            "ISO date",
        ),
        ({"changes": {"../escape": "bad"}}, "unsafe corpus path"),
        ({"trailers": {"Source": "other"}}, "reserved event trailer"),
    ],
)
def test_invalid_events_are_rejected(
    tmp_path: Path, change: dict[str, object], message: str
) -> None:
    corpus = unborn_worktree(tmp_path)
    with pytest.raises(EventError, match=message):
        commit_event(base_event(**change), corpus)


def test_commit_refuses_to_absorb_unrelated_worktree_changes(tmp_path: Path) -> None:
    corpus = unborn_worktree(tmp_path)
    (corpus / "unrelated.txt").write_text("human work\n")
    with pytest.raises(GitError, match="not clean"):
        commit_event(base_event(), corpus)


def test_identity_constructor_enforces_the_namespace_email() -> None:
    with pytest.raises(EventError, match="namespaced identity email"):
        Identity("user", "user@wrong.invalid", "mw.lojban.org")


def test_all_identity_variants_and_mail_name_normalisation() -> None:
    assert Identity.mail("local@example.org") == Identity(
        "local", "local@example.org", "mail"
    )
    assert Identity.mail("john@example.org", "John Cowan") == Identity(
        "John Cowan", "john@example.org", "mail"
    )
    assert Identity.mail("john@example.org", ".John <jc>%.").name == (
        "%2EJohn %3Cjc%3E%25%2E"
    )
    assert Identity.anonymous("mw.lojban.org") == Identity(
        "anonymous", "anonymous@mw.lojban.org", "anonymous:mw.lojban.org"
    )
    assert Identity.irc() == Identity(
        "irclogs", "irclogs@irc.lojban.org", "irc.lojban.org"
    )
    assert Identity.tool() == Identity("jbomohi", "tools@jbomohi.invalid", "jbomohi")
    assert Identity.contributed("Contributor", "person@example.org") == Identity(
        "Contributor", "person@example.org", "contributed"
    )
    assert Identity.namespaced("mw.lojban.org", "gúskant") == Identity(
        "gúskant", "g%C3%BAskant@mw.lojban.org", "mw.lojban.org"
    )


def test_mail_name_normalisation_is_preserved_in_the_commit(tmp_path: Path) -> None:
    corpus = unborn_worktree(tmp_path)
    event = base_event(author=Identity.mail("john@example.org", ".John <jc>%."))
    commit_event(event, corpus)
    assert git(corpus, "show", "-s", "--format=%an") == "%2EJohn %3Cjc%3E%25%2E"


def test_mail_name_edge_whitespace_is_encoded_injectively() -> None:
    assert Identity.mail("john@example.org", " John ").name == "%20John%20"
    assert Identity.mail("john@example.org", "%20John%20").name == "%2520John%2520"


def test_maildir_cur_file_is_materialized_read_only_but_git_mode_is_portable(
    tmp_path: Path,
) -> None:
    corpus = unborn_worktree(tmp_path)
    path = "mail/lojban-list/cur/946684800.0123456789abcdef.jbomohi:2,S"
    event = base_event(
        source="mail/lojban-list",
        source_id="message@example.org",
        summary="message",
        author=Identity.mail("sender@example.org", "Sender"),
        changes={path: b"From: sender@example.org\r\n\r\nbody\r\n"},
        trailers={"Message-Id": "message@example.org", "Thread": "thread"},
    )
    commit_event(event, corpus)
    assert (corpus / path).stat().st_mode & 0o222 == 0
    assert git(corpus, "ls-tree", "HEAD", path).split()[0] == "100644"


def test_namespaced_git_name_and_email_escape_edge_dots() -> None:
    assert Identity.namespaced("mw.lojban.org", ".i.") == Identity(
        "%2Ei%2E", "%2Ei%2E@mw.lojban.org", "mw.lojban.org"
    )
    assert Identity.namespaced("mw.lojban.org", ".i..j.").email == (
        "%2Ei%2E%2Ej%2E@mw.lojban.org"
    )


def test_source_name_encoding_is_injective_for_percent_escapes() -> None:
    punctuation = Identity.namespaced("mw.lojban.org", "<x>")
    literal_escape = Identity.namespaced("mw.lojban.org", "%3Cx%3E")
    assert punctuation.name == "%3Cx%3E"
    assert literal_escape.name == "%253Cx%253E"
    assert punctuation.email == "%3Cx%3E@mw.lojban.org"
    assert literal_escape.email == "%253Cx%253E@mw.lojban.org"
    assert punctuation != literal_escape


def test_namespaced_name_encoding_survives_in_the_commit(tmp_path: Path) -> None:
    corpus = unborn_worktree(tmp_path)
    event = base_event(author=Identity.namespaced("mw.lojban.org", ".i."))
    commit_event(event, corpus)
    assert git(corpus, "show", "-s", "--format=%an%n%ae").splitlines() == [
        "%2Ei%2E",
        "%2Ei%2E@mw.lojban.org",
    ]


def test_contributed_name_uses_the_same_git_safe_encoding() -> None:
    assert Identity.contributed(".Contributor%", "person@example.org").name == (
        "%2EContributor%25"
    )


def test_run_git_strips_repository_and_config_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus = unborn_worktree(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    git(other, "init", "--initial-branch=other")
    fake_index = tmp_path / "redirected-index"
    fake_config = tmp_path / "global.gitconfig"
    fake_config.write_text("[core]\n\tautocrlf = true\n")
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(other))
    monkeypatch.setenv("GIT_INDEX_FILE", str(fake_index))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(fake_config))
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.safecrlf")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "true")

    result = run_git(corpus, ["rev-parse", "--show-toplevel"])
    assert Path(result.stdout.strip()) == corpus
    assert (
        run_git(corpus, ["config", "--get", "core.autocrlf"]).stdout.strip() == "false"
    )
    assert (
        run_git(corpus, ["config", "--get", "core.safecrlf"]).stdout.strip() == "false"
    )
    assert not fake_index.exists()


def test_commit_paths_are_literal_git_pathspecs(tmp_path: Path) -> None:
    corpus = unborn_worktree(tmp_path)
    event = base_event(changes={"wiki/main/[ab].wiki": "literal\n"})
    commit_event(event, corpus)
    assert git(corpus, "ls-tree", "-r", "--name-only", "HEAD") == (
        "wiki/main/[ab].wiki"
    )


def test_moved_event_deletes_the_old_path_and_writes_the_new_one(
    tmp_path: Path,
) -> None:
    corpus = unborn_worktree(tmp_path)
    first = base_event()
    commit_event(first, corpus)
    moved = base_event(
        source_id="revid=2",
        event="moved",
        source_time=first.source_time + timedelta(days=1),
        summary="move Test to Renamed (rev 2)",
        changes={"wiki/main/Renamed.wiki": "first\n"},
        deletions=("wiki/main/Test.wiki",),
    )
    commit_event(moved, corpus)
    assert not (corpus / "wiki/main/Test.wiki").exists()
    assert (corpus / "wiki/main/Renamed.wiki").read_text() == "first\n"
    tree = git(corpus, "ls-tree", "-r", "--name-only", "HEAD")
    assert "wiki/main/Test.wiki" not in tree
    assert "wiki/main/Renamed.wiki" in tree


def test_deletion_rejects_a_path_not_tracked_by_head(tmp_path: Path) -> None:
    corpus = unborn_worktree(tmp_path)
    event = base_event(
        source_id="revid=2",
        event="deleted",
        summary="delete Missing (rev 2)",
        changes={},
        deletions=("wiki/main/Missing.wiki",),
    )
    with pytest.raises(EventError, match="deletion names an untracked path"):
        commit_event(event, corpus)


def test_commit_refuses_to_traverse_a_tracked_symlink(tmp_path: Path) -> None:
    corpus = unborn_worktree(tmp_path)
    outside = tmp_path / "outside"
    (corpus / "wiki").symlink_to(outside, target_is_directory=True)
    git(corpus, "add", "wiki")
    git(
        corpus,
        "-c",
        "user.name=fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-m",
        "fixture symlink",
    )
    with pytest.raises(EventError, match="refusing to traverse symlink"):
        commit_event(base_event(), corpus)
    assert not outside.exists()
