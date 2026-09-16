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


def test_document_identity_uses_an_attested_author_slug() -> None:
    identity = Identity.document("lojban.org", "Logical Language Group", "llg")
    assert identity.name == "Logical Language Group"
    assert identity.email == "llg@lojban.org"
    with pytest.raises(EventError, match="invalid document author"):
        Identity.document("lojban.org", "Name", "Not A Slug")


def test_commit_event_writes_and_updates_a_gitlink(tmp_path: Path) -> None:
    corpus = unborn_worktree(tmp_path)
    first_id = "1" * 40
    second_id = "2" * 40
    first = base_event(
        source="cll",
        source_id="cll=1.0",
        event="render",
        summary="render 1.0",
        author=Identity.tool(),
        changes={},
        gitlinks={"cll/src": first_id},
        submodules={"cll/src": "https://github.com/int19h/cll"},
        trailers={"Edition": "1.0", "Renderer": "cll/1"},
    )
    commit_event(first, corpus)
    assert git(corpus, "ls-tree", "HEAD", "cll/src") == (
        f"160000 commit {first_id}\tcll/src"
    )
    second = base_event(
        source="cll",
        source_id="cll=1.1",
        event="render",
        summary="render 1.1",
        author=Identity.tool(),
        changes={"cll/editions/1.1/01-about.txt": "rendered\n"},
        gitlinks={"cll/src": second_id},
        submodules={"cll/src": "https://github.com/int19h/cll"},
        trailers={"Edition": "1.1", "Renderer": "cll/1"},
    )
    commit_event(second, corpus)
    assert git(corpus, "ls-tree", "HEAD", "cll/src") == (
        f"160000 commit {second_id}\tcll/src"
    )


def test_interleaved_gitlink_events_preserve_every_submodule_entry(
    tmp_path: Path,
) -> None:
    corpus = unborn_worktree(tmp_path)
    cll = base_event(
        source="cll",
        source_id="cll=one",
        event="render",
        summary="render one",
        author=Identity.tool(),
        changes={},
        gitlinks={"cll/src": "1" * 40},
        submodules={"cll/src": "https://example.invalid/cll"},
    )
    grammar = base_event(
        source="grammars",
        source_id="grammars/parser=" + "2" * 40,
        event="created",
        summary="pin parser",
        author=Identity.tool(),
        changes={},
        gitlinks={"grammars/parser/src": "2" * 40},
        submodules={"grammars/parser/src": "https://example.invalid/parser"},
    )
    commit_event(cll, corpus)
    commit_event(grammar, corpus)
    commit_event(
        base_event(
            source="cll",
            source_id="cll=two",
            event="render",
            summary="render two",
            author=Identity.tool(),
            changes={},
            gitlinks={"cll/src": "3" * 40},
            submodules={"cll/src": "https://example.invalid/cll"},
        ),
        corpus,
    )
    assert (corpus / ".gitmodules").read_text() == (
        '[submodule "cll/src"]\n'
        "\tpath = cll/src\n"
        "\turl = https://example.invalid/cll\n"
        '[submodule "grammars/parser/src"]\n'
        "\tpath = grammars/parser/src\n"
        "\turl = https://example.invalid/parser\n"
    )
    assert git(corpus, "ls-tree", "HEAD", "cll/src").startswith(
        "160000 commit " + "3" * 40
    )
    assert git(corpus, "ls-tree", "HEAD", "grammars/parser/src").startswith(
        "160000 commit " + "2" * 40
    )


@pytest.mark.parametrize(
    "gitlinks",
    (
        {"../outside": "1" * 40},
        {"cll/src": "not-an-object"},
        {"wiki/main/Test.wiki": "1" * 40},
    ),
)
def test_event_rejects_unsafe_invalid_or_overlapping_gitlinks(
    gitlinks: dict[str, str],
) -> None:
    with pytest.raises(EventError, match="unsafe corpus path|40-digit|same path"):
        base_event(gitlinks=gitlinks).validate()


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


@pytest.mark.parametrize("source_date", ("1997", "2016-08", "2016-08-26"))
def test_exact_event_accepts_an_independently_evidenced_source_date(
    source_date: str,
) -> None:
    base_event(source_date=source_date).validate()


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
        ({"source_date": "0000"}, "Source-Date must be"),
        ({"source_date": "2016-13"}, "Source-Date must be"),
        (
            {
                "time_confidence": "window",
                "event_window": "2004-01-01..2004-01-03",
                "source_date": "2004",
            },
            "pre-epoch or exact",
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
    assert Identity.mail('"Mike A"@example.org').email == '"Mike%20A"@example.org'
    assert Identity.mail('"Mike%20A"@example.org').email == ('"Mike%2520A"@example.org')


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


def _fresh(tmp_path: Path, name: str) -> Path:
    root = tmp_path / name
    root.mkdir()
    return unborn_worktree(root)


def _sequence(count: int) -> list[Event]:
    """A run of events touching writes, rewrites, deletions and a submodule."""

    start = datetime(2004, 1, 2, 3, 4, 5, tzinfo=UTC)
    events: list[Event] = []
    for index in range(count):
        changes: dict[str, str | bytes] = {
            f"wiki/main/Page{index}.wiki": f"body {index}\n",
            # Rewrite a shared index file every time, as the projectors do.
            "_meta/wiki/pages.csv": f"pageid\n{index}\n",
        }
        deletions: tuple[str, ...] = ()
        if index and index % 5 == 0:
            deletions = (f"wiki/main/Page{index - 1}.wiki",)
        events.append(
            base_event(
                source_id=f"revid={index + 1}",
                source_time=start + timedelta(minutes=index),
                summary=f"create Page{index} (rev {index + 1})",
                changes=changes,
                deletions=deletions,
                event="created" if index == 0 else "edited",
            )
        )
    return events


def test_build_session_commits_are_identical_to_the_per_event_path(
    tmp_path: Path,
) -> None:
    """The fast build path must produce the same history, commit for commit.

    It skips the clean check and keeps one index alive, so nothing about the
    resulting objects may change: same trees, same commits, same head.
    """

    from jbomohi_tools.git import BuildCommitSession

    events = _sequence(12)

    careful = _fresh(tmp_path, "careful")
    careful_heads = [commit_event(event, careful) for event in events]

    fast = _fresh(tmp_path, "fast")
    with BuildCommitSession(fast) as session:
        fast_heads = [session.commit(event) for event in events]

    assert fast_heads == careful_heads
    assert git(fast, "rev-parse", "HEAD") == git(careful, "rev-parse", "HEAD")
    assert git(fast, "rev-list", "--count", "HEAD") == git(
        careful, "rev-list", "--count", "HEAD"
    )
    # The worktree the session leaves behind must match the careful path too,
    # since `verify` reads files and their modes, not only the trees.
    assert git(fast, "status", "--porcelain=v1", "--untracked-files=all") == ""
    for name in ("wiki/main/Page11.wiki", "_meta/wiki/pages.csv"):
        assert (fast / name).read_bytes() == (careful / name).read_bytes()


def test_build_session_refuses_a_dirty_corpus(tmp_path: Path) -> None:
    from jbomohi_tools.git import BuildCommitSession

    corpus = _fresh(tmp_path, "dirty")
    commit_event(base_event(), corpus)
    (corpus / "stray").write_text("unexpected\n")
    with pytest.raises(GitError, match="refusing to build into it"):
        BuildCommitSession(corpus)


def test_build_session_carries_submodules_and_gitlinks(tmp_path: Path) -> None:
    """The .gitmodules merge must still accumulate across session commits."""

    from jbomohi_tools.git import BuildCommitSession

    first = base_event(
        source="cll",
        source_id="cll=1",
        changes={"cll/README": "one\n"},
        submodules={"cll/src": "https://example.invalid/cll.git"},
        gitlinks={"cll/src": "1" * 40},
    )
    second = base_event(
        source="grammars",
        source_id="grammars=1",
        source_time=datetime(2005, 1, 2, 3, 4, 5, tzinfo=UTC),
        changes={"grammars/README": "two\n"},
        submodules={"grammars/src": "https://example.invalid/g.git"},
        gitlinks={"grammars/src": "2" * 40},
    )
    careful = _fresh(tmp_path, "careful")
    for event in (first, second):
        commit_event(event, careful)
    fast = _fresh(tmp_path, "fast")
    with BuildCommitSession(fast) as session:
        for event in (first, second):
            session.commit(event)
    assert git(fast, "rev-parse", "HEAD") == git(careful, "rev-parse", "HEAD")
    assert git(fast, "show", "HEAD:.gitmodules") == git(
        careful, "show", "HEAD:.gitmodules"
    )


def test_fast_import_history_is_identical_to_both_other_paths(tmp_path: Path) -> None:
    """Three backends, one history: the objects must be the same objects.

    fast-import writes commits directly instead of staging an index, so this
    pins every part the plumbing path decides: author and committer identity,
    the raw date, the message and its trailers, the tree, and the worktree the
    build leaves for `verify` to read.
    """

    from jbomohi_tools.git import BuildCommitSession, FastImportSession

    events = _sequence(12)

    careful = _fresh(tmp_path, "careful")
    for event in events:
        commit_event(event, careful)

    session = _fresh(tmp_path, "session")
    with BuildCommitSession(session) as live:
        for event in events:
            live.commit(event)

    imported = _fresh(tmp_path, "imported")
    with FastImportSession(imported) as stream:
        for event in events:
            stream.commit(event)

    expected = git(careful, "rev-parse", "HEAD")
    assert git(session, "rev-parse", "HEAD") == expected
    assert git(imported, "rev-parse", "HEAD") == expected
    assert git(imported, "rev-list", "--count", "HEAD") == git(
        careful, "rev-list", "--count", "HEAD"
    )
    assert git(imported, "status", "--porcelain=v1", "--untracked-files=all") == ""
    for name in ("wiki/main/Page11.wiki", "_meta/wiki/pages.csv"):
        assert (imported / name).read_bytes() == (careful / name).read_bytes()


def test_fast_import_keeps_submodules_gitlinks_and_empty_trees(tmp_path: Path) -> None:
    """The .gitmodules merge, gitlink modes and unchanged-tree events survive."""

    from jbomohi_tools.git import FastImportSession

    first = base_event(
        source="cll",
        source_id="cll=1",
        changes={"cll/README": "one\n"},
        submodules={"cll/src": "https://example.invalid/cll.git"},
        gitlinks={"cll/src": "1" * 40},
    )
    second = base_event(
        source="grammars",
        source_id="grammars=1",
        source_time=datetime(2005, 1, 2, 3, 4, 5, tzinfo=UTC),
        changes={"grammars/README": "two\n"},
        submodules={"grammars/src": "https://example.invalid/g.git"},
        gitlinks={"grammars/src": "2" * 40},
    )
    # An event that changes nothing is still an event, and still a commit.
    third = base_event(
        source="tiki",
        source_id="tiki=page@current",
        source_time=datetime(2006, 1, 2, 3, 4, 5, tzinfo=UTC),
        changes={},
    )
    events = (first, second, third)

    careful = _fresh(tmp_path, "careful")
    for event in events:
        commit_event(event, careful)
    imported = _fresh(tmp_path, "imported")
    with FastImportSession(imported) as stream:
        for event in events:
            stream.commit(event)

    assert git(imported, "rev-parse", "HEAD") == git(careful, "rev-parse", "HEAD")
    assert git(imported, "show", "HEAD:.gitmodules") == git(
        careful, "show", "HEAD:.gitmodules"
    )
    assert git(imported, "rev-list", "--count", "HEAD") == "3"
    # The last event changed nothing, so its tree is its parent's.
    assert git(imported, "rev-parse", "HEAD^{tree}") == git(
        imported, "rev-parse", "HEAD~1^{tree}"
    )


def test_fast_import_refuses_a_deletion_of_an_untracked_path(tmp_path: Path) -> None:
    from jbomohi_tools.git import FastImportSession

    imported = _fresh(tmp_path, "imported")
    with (
        pytest.raises(EventError, match="untracked path"),
        FastImportSession(imported) as stream,
    ):
        stream.commit(base_event())
        stream.commit(
            base_event(
                source_id="revid=2",
                source_time=datetime(2004, 1, 3, tzinfo=UTC),
                changes={"wiki/main/Other.wiki": "x\n"},
                deletions=("wiki/main/Absent.wiki",),
            )
        )


def test_fast_import_continues_an_existing_history(tmp_path: Path) -> None:
    """A build starts from the deterministic root commit, not an empty branch."""

    from jbomohi_tools.git import FastImportSession

    corpus = _fresh(tmp_path, "corpus")
    root = commit_event(base_event(), corpus)
    follow = base_event(
        source_id="revid=2",
        source_time=datetime(2004, 1, 3, tzinfo=UTC),
        changes={"wiki/main/Test.wiki": "second\n"},
        event="edited",
    )
    with FastImportSession(corpus) as stream:
        stream.commit(follow)
    assert git(corpus, "rev-parse", "HEAD~1") == root
    assert (corpus / "wiki/main/Test.wiki").read_text() == "second\n"


def _three_ways(tmp_path: Path, events: tuple[Event, ...]) -> str:
    """Run one history through all three backends and return the shared head."""

    from jbomohi_tools.git import BuildCommitSession, FastImportSession

    careful = _fresh(tmp_path, "careful")
    for event in events:
        commit_event(event, careful)

    session = _fresh(tmp_path, "session")
    with BuildCommitSession(session) as live:
        for event in events:
            live.commit(event)

    imported = _fresh(tmp_path, "imported")
    with FastImportSession(imported) as stream:
        for event in events:
            stream.commit(event)

    expected = git(careful, "rev-parse", "HEAD")
    assert git(session, "rev-parse", "HEAD") == expected
    assert git(imported, "rev-parse", "HEAD") == expected
    return expected


def test_pre_epoch_events_are_dated_alike_by_every_backend(tmp_path: Path) -> None:
    """A pre-1970 document commits at the epoch with its true date recorded.

    `_git_date` clamps to the epoch and the fast-import stream computes its own
    raw timestamp; nothing else pins them to the same instant.
    """

    event = base_event(
        source="loglan",
        source_id="loglan=1",
        time_confidence="pre-epoch",
        source_time=datetime(1960, 5, 1, tzinfo=UTC),
        source_date="1960-05-01",
        changes={"loglan/notebook.txt": "before the fork\n"},
    )
    _three_ways(tmp_path, (event,))
    careful = tmp_path / "careful" / "repo"
    assert git(careful, "log", "-1", "--format=%ad", "--date=iso-strict") == (
        "1970-01-01T00:00:00Z"
    )
    assert "Source-Date: 1960-05-01" in git(careful, "log", "-1", "--format=%B")


def test_paths_needing_quoting_are_written_alike_by_every_backend(
    tmp_path: Path,
) -> None:
    """fast-import reads one path per line, so odd paths must survive quoting.

    `_safe_repo_path` refuses a backslash, so the cases that can actually occur
    are spaces, quotes and non-ASCII — all of which `ls-tree` would C-quote on
    the way back in, which is why the tracked set is read NUL-separated.
    """

    odd = 'mail/lojban-list/cur/caf é "quoted" name:2,S'
    first = base_event(changes={odd: "body\n", "wiki/main/Plain.wiki": "x\n"})
    second = base_event(
        source_id="revid=2",
        source_time=datetime(2004, 1, 3, tzinfo=UTC),
        event="edited",
        changes={"wiki/main/Plain.wiki": "y\n"},
        deletions=(odd,),
    )
    _three_ways(tmp_path, (first, second))
    for name in ("careful", "session", "imported"):
        repo = tmp_path / name / "repo"
        assert not (repo / odd).exists()
        assert git(repo, "rev-list", "--count", "HEAD") == "2"
    # The deletion had to be recognised as tracked, not refused as unknown:
    # the path is in the first commit's tree and gone from the second. Read it
    # NUL-separated, because git quotes such a path in ordinary output.
    imported = tmp_path / "imported" / "repo"
    before = git(imported, "ls-tree", "-r", "-z", "--name-only", "HEAD~1").split("\0")
    after = git(imported, "ls-tree", "-r", "-z", "--name-only", "HEAD").split("\0")
    assert odd in before
    assert odd not in after


def test_a_session_resuming_history_knows_its_quoted_paths(tmp_path: Path) -> None:
    """A session reads the paths it inherits, and git quotes those by default.

    Within one session a path is tracked because the session itself wrote it,
    so the inherited set only matters when a build continues existing history —
    which is exactly when `ls-tree` would hand back a C-quoted name that
    matches nothing, and a legitimate deletion would be refused as untracked.
    """

    from jbomohi_tools.git import FastImportSession

    odd = 'mail/lojban-list/cur/caf é "quoted" name:2,S'
    corpus = _fresh(tmp_path, "corpus")
    commit_event(base_event(changes={odd: "body\n"}), corpus)

    removal = base_event(
        source_id="revid=2",
        source_time=datetime(2004, 1, 3, tzinfo=UTC),
        event="edited",
        changes={"wiki/main/Plain.wiki": "x\n"},
        deletions=(odd,),
    )
    with FastImportSession(corpus) as stream:
        stream.commit(removal)

    assert git(corpus, "rev-list", "--count", "HEAD") == "2"
    assert odd not in git(corpus, "ls-tree", "-r", "-z", "--name-only", "HEAD").split(
        "\0"
    )
    assert not (corpus / odd).exists()


def test_encoded_author_names_are_identical_in_every_backend(tmp_path: Path) -> None:
    """`commit-tree` sanitises idents; fast-import takes them literally.

    What keeps the two equal is `_git_safe_name`, which encodes the syntax git
    cannot retain before either backend sees it.
    """

    author = Identity.namespaced("mw.lojban.org", "odd <name> with %")
    event = base_event(author=author, changes={"wiki/main/Odd.wiki": "x\n"})
    _three_ways(tmp_path, (event,))
    careful = tmp_path / "careful" / "repo"
    recorded = git(careful, "log", "-1", "--format=%an <%ae>")
    assert "<" not in recorded.split(" <")[0]
    assert recorded == f"{author.name} <{author.email}>"


def test_an_event_with_more_paths_than_a_command_line_holds(tmp_path: Path) -> None:
    """One `git add` per event met ARG_MAX when IRC arrived.

    A refresh commit carries every archive manifest, and the IRC fetch took the
    archive past 70,000 of them. The whole build died after 65 minutes with
    `[Errno 7] Argument list too long: 'git'` — a failure no fixture with a
    handful of files can produce, so the test has to be large enough to fail.
    """

    corpus = unborn_worktree(tmp_path)
    # Comfortably past a typical 2 MiB ARG_MAX once the paths are joined.
    changes = {
        f"_meta/archive/bulk/{index:06d}-{'x' * 60}.toml": b"k = 1\n"
        for index in range(40_000)
    }
    event = Event(
        source="meta",
        source_id="bulk@1",
        event="refresh",
        time_confidence="exact",
        source_time=datetime(2026, 9, 16, tzinfo=UTC),
        summary="many paths in one event",
        author=Identity.tool(),
        changes=changes,
    )

    head = commit_event(event, corpus)

    listed = run_git(corpus, ["ls-tree", "-r", "--name-only", head]).stdout.split()
    assert len(listed) == len(changes)
