from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from jbomohi_tools.archive.manifest import ArchiveManifest
from jbomohi_tools.build import (
    _archive_manifest_changes,
    build_corpus,
    push_main_ranges,
    update_corpus,
    verify_corpus,
)
from jbomohi_tools.config import Config
from jbomohi_tools.corpus import CorpusError
from jbomohi_tools.git import Event, EventError, GitError, Identity

HERE = Path(__file__).resolve()
WORKSPACE = HERE.parents[2]
TEMPLATES = WORKSPACE / "tools/templates/main"


def run(cwd: Path, *args: str, env: dict[str, str] | None = None) -> str:
    actual_env = dict(os.environ)
    if env:
        actual_env.update(env)
    result = subprocess.run(
        list(args), cwd=cwd, env=actual_env, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def git(cwd: Path, *args: str) -> str:
    return run(cwd, "git", *args)


def commit_fixture(corpus: Path, message: str) -> None:
    git(corpus, "add", "-A")
    run(
        corpus,
        "git",
        "commit",
        "--allow-empty",
        "-m",
        message,
        env={
            "GIT_AUTHOR_NAME": "fixture",
            "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
            "GIT_AUTHOR_DATE": "2000-01-02T00:00:00+00:00",
            "GIT_COMMITTER_NAME": "fixture",
            "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
            "GIT_COMMITTER_DATE": "2000-01-02T00:00:00+00:00",
        },
    )


def valid_message(source_id: str, *, source: str = "meta") -> str:
    return (
        "fixture\n\n"
        f"Source: {source}\n"
        f"Source-Id: {source_id}\n"
        "Event: updated\n"
        "Time-Confidence: exact"
    )


def tools_repo(path: Path) -> tuple[Config, str]:
    path.mkdir()
    git(path, "init", "--initial-branch=tools")
    shutil.copytree(TEMPLATES, path / "tools/templates/main")
    (path / ".gitignore").write_text("corpus/\narchive/\n")
    (path / "README.md").write_text("tools\n")
    git(path, "add", ".")
    env = {
        "GIT_AUTHOR_NAME": "fixture",
        "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_AUTHOR_DATE": "2000-01-01T00:00:00+00:00",
        "GIT_COMMITTER_NAME": "fixture",
        "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_DATE": "2000-01-01T00:00:00+00:00",
    }
    run(path, "git", "commit", "-m", "tools", env=env)
    commit = git(path, "rev-parse", "HEAD")
    state = path.parent / f"{path.name}-state"
    return Config(path, state / "corpus", state / "archive", state / "tmp"), commit


def event(identifier: str, second: int, path: str) -> Event:
    return Event(
        source="wiki",
        source_id=identifier,
        event="created",
        time_confidence="exact",
        source_time=datetime(2000, 1, 1, 0, 0, second, tzinfo=UTC),
        summary=identifier,
        author=Identity.namespaced("mw.lojban.org", "tester"),
        changes={path: identifier + "\n"},
        trailers={"Page-Id": identifier.removeprefix("rev=")},
    )


def test_build_is_transactional_chronological_and_deterministic(tmp_path: Path) -> None:
    config, tools_commit = tools_repo(tmp_path / "repo")
    (config.archive / "manifests/wiki").mkdir(parents=True)
    (config.archive / "manifests/wiki/source.toml").write_text(
        'source = "wiki"\n'
        'kind = "fixture"\n'
        'origin = "https://example.invalid/wiki"\n'
        "fetched_at = 2026-01-01T00:00:00Z\n"
        f'sha256 = "{"a" * 64}"\n'
        "bytes = 1\n"
        'notes = "fixture"\n'
        'coverage = { from = "2000-01-01", to = "2000-01-01", '
        "counts = { events = 1 } }\n"
    )
    sources = {
        "late": lambda: iter((event("rev=2", 2, "wiki/main/Two.wiki"),)),
        "early": lambda: iter((event("rev=1", 1, "wiki/main/One.wiki"),)),
    }
    first = build_corpus(config, sources)
    assert first.events == 2
    assert first.commits == 4
    assert first.snapshot == "snapshot/20000101T000002Z"
    messages = git(config.corpus, "log", "--reverse", "--format=%s").splitlines()
    assert messages[1:3] == ["wiki: rev=1", "wiki: rev=2"]
    assert git(config.corpus, "rev-parse", "HEAD") == first.head
    assert tools_commit in (config.corpus / "_meta/schema.toml").read_text()
    assert (config.corpus / "_meta/archive/wiki/source.toml").is_file()
    assert git(config.repo_root, "rev-parse", f"{first.snapshot}^{{}}") == first.head
    assert config.tmp.is_dir()
    assert not (config.repo_root / "tmp").exists()

    second = build_corpus(config, sources)
    assert second.head == first.head
    assert verify_corpus(config.corpus).commits == 4


def test_build_ignores_hostile_global_git_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, _commit = tools_repo(tmp_path / "repo")
    sources = {"one": lambda: iter((event("rev=1", 1, "wiki/main/One.wiki"),))}
    expected = build_corpus(config, sources).head
    hostile = tmp_path / "hostile.gitconfig"
    hostile.write_text(
        "[core]\n\tautocrlf = true\n\tsafecrlf = true\n\thooksPath = /nonexistent\n"
    )
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(hostile))
    assert build_corpus(config, sources).head == expected


def test_verify_accepts_an_event_with_no_changed_paths(tmp_path: Path) -> None:
    config, _commit = tools_repo(tmp_path / "repo")
    empty = replace(event("rev=1", 1, "unused"), changes={})
    report = build_corpus(config, {"wiki": lambda: iter((empty,))})
    verified = verify_corpus(config.corpus)
    assert report.events == 1
    assert verified.commits == 3


def test_build_rejects_dirty_tools_before_replacing_main(tmp_path: Path) -> None:
    config, _commit = tools_repo(tmp_path / "repo")
    original = build_corpus(config, {}).head
    (config.repo_root / "dirty.txt").write_text("uncommitted\n")
    with pytest.raises(CorpusError, match="tools worktree is dirty"):
        build_corpus(config, {})
    assert git(config.corpus, "rev-parse", "HEAD") == original


def test_failed_scratch_projection_leaves_existing_main_unchanged(
    tmp_path: Path,
) -> None:
    config, _commit = tools_repo(tmp_path / "repo")
    original = build_corpus(
        config,
        {"wiki": lambda: iter((event("rev=1", 1, "wiki/main/One.wiki"),))},
    ).head

    def failing():
        yield event("rev=2", 2, "wiki/main/Two.wiki")
        raise RuntimeError("projector failed")

    with pytest.raises(RuntimeError, match="projector failed"):
        build_corpus(config, {"wiki": failing})
    assert git(config.corpus, "rev-parse", "HEAD") == original


def test_update_appends_only_new_source_ids_and_refreshes(tmp_path: Path) -> None:
    config, _commit = tools_repo(tmp_path / "repo")
    first_event = event("rev=1", 1, "wiki/main/One.wiki")
    build_corpus(config, {"wiki": lambda: iter((first_event,))})
    before = int(git(config.corpus, "rev-list", "--count", "HEAD"))
    second_event = event("rev=2", 2, "wiki/main/Two.wiki")
    report = update_corpus(
        config,
        {"wiki": lambda: iter((first_event, second_event))},
    )
    assert report is not None
    assert report.events == 1
    assert int(git(config.corpus, "rev-list", "--count", "HEAD")) == before + 2
    assert (
        update_corpus(config, {"wiki": lambda: iter((first_event, second_event))})
        is None
    )


def test_update_folds_final_stream_metadata_into_refresh(tmp_path: Path) -> None:
    config, _commit = tools_repo(tmp_path / "repo")
    first = event("rev=1", 1, "wiki/main/One.wiki")
    old_final = event("rev=3", 3, "wiki/main/Three.wiki")
    old_final = replace(
        old_final,
        changes={
            **old_final.changes,
            "_meta/wiki/index.csv": "path\nwiki/main/One.wiki\n",
        },
    )
    build_corpus(config, {"wiki": lambda: iter((first, old_final))})

    second = event("rev=2", 2, "wiki/main/Two.wiki")
    new_final = replace(
        old_final,
        changes={
            **old_final.changes,
            "_meta/wiki/index.csv": (
                "path\nwiki/main/One.wiki\nwiki/main/Two.wiki\nwiki/main/Three.wiki\n"
            ),
        },
    )
    report = update_corpus(config, {"wiki": lambda: iter((first, second, new_final))})
    assert report is not None
    assert (config.corpus / "_meta/wiki/index.csv").read_text() == (
        "path\nwiki/main/One.wiki\nwiki/main/Two.wiki\nwiki/main/Three.wiki\n"
    )


def test_push_main_uses_commit_ranges_then_snapshot_tag(tmp_path: Path) -> None:
    config, _commit = tools_repo(tmp_path / "repo")
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "--bare", str(remote))
    git(config.repo_root, "remote", "add", "origin", str(remote))
    events = tuple(
        event(f"rev={number}", number, f"wiki/main/{number}.wiki")
        for number in range(1, 6)
    )
    report = build_corpus(config, {"wiki": lambda: iter(events)})
    pushed = push_main_ranges(config.repo_root, report.snapshot, commits_per_push=2)
    assert pushed.main_updates == 4
    assert git(remote, "rev-parse", "refs/heads/main") == report.head
    assert git(remote, "rev-parse", f"refs/tags/{report.snapshot}^{{}}") == report.head


def test_push_main_rejects_a_nonancestor_remote(tmp_path: Path) -> None:
    config, _commit = tools_repo(tmp_path / "repo")
    report = build_corpus(config, {})
    remote = tmp_path / "remote.git"
    seed = tmp_path / "seed"
    git(tmp_path, "init", "--bare", str(remote))
    seed.mkdir()
    git(seed, "init", "--initial-branch=main")
    (seed / "README").write_text("unrelated\n")
    commit_fixture(seed, valid_message("unrelated"))
    git(seed, "remote", "add", "origin", str(remote))
    git(seed, "push", "origin", "main")
    git(config.repo_root, "remote", "add", "origin", str(remote))
    with pytest.raises(GitError, match="not an ancestor"):
        push_main_ranges(config.repo_root, report.snapshot)


def test_page_manifests_are_consolidated_for_main_projection(tmp_path: Path) -> None:
    root = tmp_path / "archive/manifests/mail/announce/mhonarc"
    for index in (1, 0):
        manifest = ArchiveManifest(
            source="mail/announce",
            kind="mhonarc-page",
            origin=f"https://mail.example/msg{index:05d}.html",
            fetched_at=datetime(2026, 9, 14, tzinfo=UTC),
            sha256=f"{index + 1:064x}",
            bytes=index + 1,
            coverage={
                "from": "unknown",
                "to": "unknown",
                "counts": {"messages": 1},
            },
            notes="fixture",
        )
        manifest.write(root / f"msg{index:05d}.toml")
    changes = _archive_manifest_changes(tmp_path / "archive")
    assert set(changes) == {"_meta/archive/mail/announce/mhonarc-page.toml"}
    parsed = __import__("tomllib").loads(
        changes["_meta/archive/mail/announce/mhonarc-page.toml"].decode()
    )
    assert [item["origin"] for item in parsed["objects"]] == [
        "https://mail.example/msg00000.html",
        "https://mail.example/msg00001.html",
    ]


def test_verify_rejects_a_commit_with_missing_trailers(tmp_path: Path) -> None:
    config, _commit = tools_repo(tmp_path / "repo")
    build_corpus(config, {})
    (config.corpus / "bad.txt").write_text("bad\n")
    commit_fixture(
        config.corpus,
        "bad\n\nSource: wiki\nSource-Id: rev=bad",
    )
    with pytest.raises(CorpusError, match="missing trailers: Event, Time-Confidence"):
        verify_corpus(config.corpus)


def test_verify_rejects_duplicate_source_path_id(tmp_path: Path) -> None:
    config, _commit = tools_repo(tmp_path / "repo")
    build_corpus(
        config,
        {"wiki": lambda: iter((event("rev=1", 1, "wiki/main/One.wiki"),))},
    )
    (config.corpus / "wiki/main/One.wiki").write_text("changed\n")
    commit_fixture(config.corpus, valid_message("rev=1", source="wiki"))
    with pytest.raises(CorpusError, match="duplicate Source-Id for source/path"):
        verify_corpus(config.corpus)


def test_verify_rejects_a_dangling_csv_path(tmp_path: Path) -> None:
    config, _commit = tools_repo(tmp_path / "repo")
    build_corpus(config, {})
    index = config.corpus / "_meta/fixture/index.csv"
    index.parent.mkdir(parents=True)
    index.write_text("path\nmissing.txt\n")
    commit_fixture(config.corpus, valid_message("dangling"))
    with pytest.raises(CorpusError, match="CSV path missing"):
        verify_corpus(config.corpus)


def maildir_fixture(corpus: Path) -> Path:
    root = corpus / "mail/test"
    for name in ("cur", "new", "tmp", "threads"):
        (root / name).mkdir(parents=True, exist_ok=True)
    for name in ("new", "tmp"):
        (root / name / ".keep").write_text("")
    return root


def test_verify_rejects_a_bad_maildir_filename(tmp_path: Path) -> None:
    config, _commit = tools_repo(tmp_path / "repo")
    build_corpus(config, {})
    root = maildir_fixture(config.corpus)
    (root / "cur/bad").write_text("message\n")
    commit_fixture(config.corpus, valid_message("bad-maildir"))
    with pytest.raises(CorpusError, match="invalid Maildir filename"):
        verify_corpus(config.corpus)


def test_verify_rejects_nonempty_maildir_new(tmp_path: Path) -> None:
    config, _commit = tools_repo(tmp_path / "repo")
    build_corpus(config, {})
    root = maildir_fixture(config.corpus)
    (root / "new/message").write_text("message\n")
    commit_fixture(config.corpus, valid_message("nonempty-new"))
    with pytest.raises(CorpusError, match="Maildir new/ is not empty"):
        verify_corpus(config.corpus)


def test_verify_checks_mail_mode_and_thread_membership(tmp_path: Path) -> None:
    config, _commit = tools_repo(tmp_path / "repo")
    build_corpus(config, {})
    root = maildir_fixture(config.corpus)
    name = "946684800.0123456789abcdef.jbomohi:2,S"
    message_path = root / "cur" / name
    message_path.write_text("message\n")
    thread = root / "threads/2000/key.txt"
    thread.parent.mkdir(parents=True)
    thread.write_text("# thread without the message\n")
    meta = config.corpus / "_meta/mail/test"
    meta.mkdir(parents=True)
    relative_message = f"mail/test/cur/{name}"
    relative_thread = "mail/test/threads/2000/key.txt"
    (meta / "messages.csv").write_text(
        f'message_id,thread_key,file\n<id@example>,key,"{relative_message}"\n'
    )
    (meta / "threads.csv").write_text(
        "thread_key,messages,path\nkey,1," + relative_thread + "\n"
    )
    commit_fixture(config.corpus, valid_message("mail-thread"))
    with pytest.raises(CorpusError, match="expected mode 0444"):
        verify_corpus(config.corpus)
    message_path.chmod(0o444)
    with pytest.raises(CorpusError, match="no thread-view entry"):
        verify_corpus(config.corpus)


def test_verify_parses_irc_and_checks_its_year(tmp_path: Path) -> None:
    config, _commit = tools_repo(tmp_path / "repo")
    build_corpus(config, {})
    path = config.corpus / "irc/lojban/2014/2015-06-02.txt"
    path.parent.mkdir(parents=True)
    path.write_text(
        "# irc #lojban 2015-06-02 tz=+0000 source=fixture format=iso\n"
        "12:00:00 <jbob> coi\n"
    )
    commit_fixture(config.corpus, valid_message("irc-year", source="irc/lojban"))
    with pytest.raises(CorpusError, match="wrong channel/year"):
        verify_corpus(config.corpus)


def test_verify_validates_dictionary_front_matter(tmp_path: Path) -> None:
    config, _commit = tools_repo(tmp_path / "repo")
    build_corpus(config, {})
    path = config.corpus / "dict/coi/en-1.md"
    path.parent.mkdir(parents=True)
    path.write_text("+++\nid = 1\n+++\n\ncoi\n")
    commit_fixture(config.corpus, valid_message("dict-front", source="dict"))
    with pytest.raises(CorpusError, match="front matter is missing"):
        verify_corpus(config.corpus)


def test_audit_events_reports_every_invalid_event(tmp_path: Path) -> None:
    """A build stops at the first bad event; the audit names them all.

    Finding a corpus-wide problem one build at a time costs a full build per
    instance, which is how two of them were found the slow way.
    """

    from jbomohi_tools.build import audit_events

    def event(source_id: str, **changes: object) -> Event:
        fields: dict[str, object] = {
            "source": "wiki",
            "source_id": source_id,
            "event": "created",
            "time_confidence": "exact",
            "source_time": datetime(2004, 1, 1, tzinfo=UTC),
            "summary": "a page (rev 1)",
            "author": Identity.namespaced("mw.lojban.org", "someone"),
            "changes": {"wiki/main/A.wiki": "x\n"},
        }
        fields.update(changes)
        return Event(**fields)  # type: ignore[arg-type]

    good = event("revid=1")
    overlapping = event(
        "revid=3",
        changes={"wiki/main/B.wiki": "y\n"},
        deletions=("wiki/main/B.wiki",),
    )
    audit = audit_events({"wiki": lambda: iter((good, overlapping))})
    assert audit.events == 2
    assert [source_id for _s, source_id, _p in audit.invalid] == ["revid=3"]
    assert "delete the same path" in audit.invalid[0][2]

    # A blank summary is caught by validation, with its own id.
    audit = audit_events(
        {"wiki": lambda: iter((good, event("revid=2", summary="   ")))}
    )
    assert [source_id for _s, source_id, _p in audit.invalid] == ["revid=2"]
    assert "summary" in audit.invalid[0][2]

    # A projector that cannot build an event at all raises out of its stream,
    # which ends that source; the audit says where it stopped and still checks
    # the others, so one bad source cannot hide the rest.
    def broken() -> Iterator[Event]:
        yield good
        raise EventError("projector gave up")

    audit = audit_events({"wiki": broken, "irc": lambda: iter((good,))})
    assert audit.events == 2
    assert [source for source, _i, _p in audit.invalid] == ["wiki"]
    assert "after 1 events" in audit.invalid[0][1]
    assert "projector gave up" in audit.invalid[0][2]

    clean = audit_events({"wiki": lambda: iter((good,))})
    assert clean.events == 1 and clean.invalid == ()


def test_verify_does_not_require_gap_paths_to_exist(tmp_path: Path) -> None:
    """A gaps file names what could not be projected, not an index of files.

    The first complete production build tripped on this: Tiki's gaps.csv has
    180 rows carrying a `path`, of which 178 name a page kept from its history
    alone — those files exist — and 2 name the NUL-byte page that SPEC.md
    3.2.5(d) deliberately does not project. Requiring either would be wrong.
    """

    config, _commit = tools_repo(tmp_path / "repo")
    build_corpus(config, {})
    kept = config.corpus / "tiki/kept.tiki"
    kept.parent.mkdir(parents=True, exist_ok=True)
    kept.write_text("body\n")
    gaps = config.corpus / "_meta/tiki/gaps.csv"
    gaps.parent.mkdir(parents=True, exist_ok=True)
    gaps.write_text(
        "source_id,title,path,reason\n"
        ",kept,tiki/kept.tiki,no current row; rename/deletion undocumented\n"
        ",gone,tiki/gone.tiki,non-text page content (NUL bytes)\n"
    )
    commit_fixture(config.corpus, valid_message("gaps"))
    verify_corpus(config.corpus)

    # An ordinary index still has to name files that are there.
    index = config.corpus / "_meta/tiki/pages.csv"
    index.write_text("title,path\nabsent,tiki/absent.tiki\n")
    commit_fixture(config.corpus, valid_message("pages"))
    with pytest.raises(CorpusError, match="CSV path missing"):
        verify_corpus(config.corpus)


def test_a_tools_commit_does_not_rewrite_the_corpus(tmp_path: Path) -> None:
    """SPEC.md 3.11/§5: the root is build-invariant, so history is stable.

    Before this, the root rendered the tools commit into `_meta/schema.toml`
    and README, so every change to the tools branch changed the root hash and
    therefore every commit beneath it. Two builds of the same events from two
    different tools commits must now agree on every event commit, and differ
    only in the tip refresh that names the build.
    """

    config, _first = tools_repo(tmp_path / "repo")
    events = {
        "wiki": lambda: iter(
            (
                event("rev=1", 1, "wiki/main/One.wiki"),
                event("rev=2", 2, "wiki/main/Two.wiki"),
            )
        )
    }
    first = build_corpus(config, events)
    first_ids = git(config.corpus, "rev-list", "--reverse", "HEAD").splitlines()

    # Any commit on the tools branch: a doc tweak is enough to move HEAD.
    (config.repo_root / "NOTES.md").write_text("a later tools commit\n")
    git(config.repo_root, "add", ".")
    git(
        config.repo_root,
        "-c",
        "user.name=fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-m",
        "tools: a later commit",
    )
    assert git(config.repo_root, "rev-parse", "HEAD") != _first

    # The snapshot name comes from the last event time, so a rebuild wants the
    # same tag for a different tip; `_tag_snapshot` refuses to move one, which
    # is right for a published citation and means a deliberate rebuild has to
    # retire the old tag first.
    git(config.repo_root, "tag", "-d", first.snapshot)

    second = build_corpus(config, events)
    second_ids = git(config.corpus, "rev-list", "--reverse", "HEAD").splitlines()

    assert len(first_ids) == len(second_ids)
    # Root and both event commits identical; only the tip refresh differs.
    assert first_ids[:-1] == second_ids[:-1]
    assert first_ids[-1] != second_ids[-1]
    assert first.head != second.head
    # And the tip is where the tools commit is recorded.
    schema = git(config.corpus, "show", "HEAD:_meta/schema.toml")
    assert git(config.repo_root, "rev-parse", "HEAD") in schema


def test_verify_requires_a_path_exactly_when_the_state_says_current(
    tmp_path: Path,
) -> None:
    """SPEC.md 4.4: an index says whether a row still has a file.

    297 rows of the first complete corpus named files that were not there —
    292 deleted wiki pages and the Tiki page that is never projected — so a
    path is now carried exactly when there is one to carry.
    """

    config, _commit = tools_repo(tmp_path / "repo")
    build_corpus(config, {})
    kept = config.corpus / "wiki/main/Kept.wiki"
    kept.parent.mkdir(parents=True, exist_ok=True)
    kept.write_text("body\n")
    index = config.corpus / "_meta/wiki/pages.csv"
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text(
        "title,state,path\n"
        "Kept,current,wiki/main/Kept.wiki\n"
        "Gone,deleted,\n"
        "Never,not-projected,\n"
    )
    commit_fixture(config.corpus, valid_message("index"))
    verify_corpus(config.corpus)

    index.write_text("title,state,path\nGone,deleted,wiki/main/Gone.wiki\n")
    commit_fixture(config.corpus, valid_message("index-with-path"))
    with pytest.raises(CorpusError, match="state and path disagree"):
        verify_corpus(config.corpus)

    index.write_text("title,state,path\nKept,current,\n")
    commit_fixture(config.corpus, valid_message("index-without-path"))
    with pytest.raises(CorpusError, match="state and path disagree"):
        verify_corpus(config.corpus)

    index.write_text("title,state,path\nKept,elsewhere,wiki/main/Kept.wiki\n")
    commit_fixture(config.corpus, valid_message("index-bad-state"))
    with pytest.raises(CorpusError, match="unknown index state"):
        verify_corpus(config.corpus)
