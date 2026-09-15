"""Command-line interface for the jbomo'i corpus tools."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path

from .archive import (
    GRAMMAR_VENDOR_FILES,
    ArchiveError,
    fetch_changes,
    fetch_cll,
    fetch_grammars,
    fetch_irc,
    fetch_jbosnu_raw,
    fetch_mail_mboxes,
    fetch_maildir_zip,
    fetch_mhonarc,
    fetch_old_lojban_list,
    fetch_wiki,
    ingest_dictionary_exports,
    ingest_tiki_export,
    ingest_wiki_sql_export,
    verify_archive,
    verify_manifests,
)
from .build import (
    audit_events,
    build_corpus,
    push_main_ranges,
    update_corpus,
    verify_corpus,
)
from .config import Config, ConfigError
from .corpus import CorpusError, corpus_status, init_corpus
from .git import EventError, GitError, commit_event, git_output
from .project.cll import project as project_cll
from .sources import SourceWiringError, source_factories

LOG = logging.getLogger("jbomohi")
Handler = Callable[[argparse.Namespace, Config], int]


def _not_implemented(name: str) -> Handler:
    def handler(_args: argparse.Namespace, _config: Config) -> int:
        LOG.error("%s is scaffolded but not implemented in M0", name)
        return 2

    return handler


def _corpus_init(_args: argparse.Namespace, config: Config) -> int:
    status, created = init_corpus(config)
    action = "created" if created else "exists"
    print(
        f"corpus {action}: path={status.path} branch={status.branch} "
        f"head={status.head or 'unborn'} commits={status.commits}"
    )
    return 0


def _corpus_status(_args: argparse.Namespace, config: Config) -> int:
    status = corpus_status(config.corpus)
    if not status.exists:
        print(f"corpus missing: path={status.path}")
        return 1
    print(
        f"corpus ready: path={status.path} branch={status.branch or 'detached'} "
        f"head={status.head or 'unborn'} commits={status.commits}"
    )
    return 0


def _archive_verify(_args: argparse.Namespace, config: Config) -> int:
    status = corpus_status(config.corpus)
    manifests = verify_manifests(config.archive / "manifests", config.archive)
    if status.exists:
        manifests.extend(verify_archive(config.corpus, config.archive))
    print(f"archive verify: ok ({len(manifests)} manifests)")
    return 0


def _archive_fetch(args: argparse.Namespace, config: Config) -> int:
    if args.source == "cll":
        report = fetch_cll(config.archive)
        print(
            f"archive fetch cll: refs={len(report.refs)} "
            f"reused={str(report.reused_manifest).lower()} "
            f"manifest={report.manifest}"
        )
        return 0
    if args.source == "grammars":
        report = fetch_grammars(
            config.archive,
            vendor_sources=GRAMMAR_VENDOR_FILES,
            camxes_backup=(config.archive / "teddyb" / "hlg_backup__2011-01-11.tgz"),
        )
        print(
            f"archive fetch grammars: mirrors={len(report.mirrors)} "
            f"reused={sum(item.reused_manifest for item in report.mirrors)} "
            f"vendor_manifests={len(report.vendor_manifests)}"
        )
        return 0
    if args.source == "irc":
        report = fetch_irc(config.archive, args.since)
        print(
            f"archive fetch irc: downloaded={report.downloaded_logs} "
            f"reused={report.reused_logs} manifests={len(report.manifests)}"
        )
        return 0
    if args.source == "wiki":
        wiki = fetch_wiki(config.archive, args.since)
        print(
            f"archive fetch wiki: pages={wiki.pages} "
            f"revision_batches={wiki.revision_batches} "
            f"log_batches={wiki.log_batches} media_batches={wiki.media_batches} "
            f"reused={wiki.reused_responses} "
            f"manifests={len(wiki.manifests)}"
        )
        return 0
    if args.source == "dict":
        report = fetch_changes(config.archive, args.since)
        print(
            f"archive fetch dict: pages={report.pages} changes={report.changes} "
            f"next_cursor={report.next_cursor or 'none'}"
        )
        return 0
    if args.source == "mail":
        if not args.list_name:
            raise ArchiveError("archive fetch mail requires --list")
        report = fetch_maildir_zip(config.archive, args.list_name)
        print(
            f"archive fetch mail: list={args.list_name} "
            f"messages={report.inventory.messages} manifest={report.manifest}"
        )
        return 0
    if args.source == "mhonarc":
        if not args.list_name:
            raise ArchiveError("archive fetch mhonarc requires --list")
        report = fetch_mhonarc(
            config.archive,
            args.list_name,
            start=args.start,
            max_pages=args.max_pages,
        )
        print(
            f"archive fetch mhonarc: list={args.list_name} "
            f"downloaded={report.downloaded} reused={report.reused} "
            f"next_missing={report.next_missing if report.next_missing is not None else 'unknown'}"
        )
        return 0
    if args.source == "jbosnu-raw":
        report = fetch_jbosnu_raw(config.archive)
        print(
            f"archive fetch jbosnu-raw: messages={report.messages} "
            f"manifest={report.manifest}"
        )
        return 0
    if args.source == "old-lojban-list":
        report = fetch_old_lojban_list(config.archive, max_pages=args.max_pages)
        print(
            f"archive fetch old-lojban-list: downloaded={report.downloaded} "
            f"reused={report.reused} "
            f"next_missing={report.next_missing if report.next_missing is not None else 'unknown'}"
        )
        return 0
    if args.source == "mail-mboxes":
        report = fetch_mail_mboxes(config.archive)
        print(
            f"archive fetch mail-mboxes: downloaded={report.downloaded} "
            f"reused={report.reused} messages={report.messages}"
        )
        return 0
    return _not_implemented(f"archive fetch {args.source}")(args, config)


def _archive_ingest_dictionary(args: argparse.Namespace, config: Config) -> int:
    report = ingest_dictionary_exports(
        config.archive, Path(args.directory), args.export_date
    )
    print(
        f"archive ingest dictionary: manifests={len(report.manifests)} "
        f"lensisku_words={len(report.lensisku.tables['valsi'])} "
        f"jbovlaste_words={len(report.jbovlaste.tables['valsi'])}"
    )
    return 0


def _archive_ingest_tiki(args: argparse.Namespace, config: Config) -> int:
    report = ingest_tiki_export(
        config.archive,
        Path(args.directory),
        args.export_date,
        character_encoding=args.character_encoding,
    )
    print(
        f"archive ingest tiki: manifests={len(report.manifests)} "
        f"pages={len(report.data.tables['tiki_pages'])} events={report.events}"
    )
    return 0


def _archive_ingest_wiki(args: argparse.Namespace, config: Config) -> int:
    report = ingest_wiki_sql_export(
        config.archive, Path(args.directory), args.export_date
    )
    print(
        f"archive ingest wiki: manifests={len(report.manifests)} "
        f"tables={len(report.inventory.table_rows)} "
        f"pages={report.inventory.table_rows['page']} "
        f"revisions={report.inventory.table_rows['revision']} "
        f"archive={report.inventory.table_rows['archive']} "
        f"users={report.inventory.users}"
    )
    return 0


def _cll_render(args: argparse.Namespace, config: Config) -> int:
    status, _created = init_corpus(config)
    events = list(project_cll(config.archive))
    target = f"cll={args.edition}"
    try:
        stop = next(
            index for index, event in enumerate(events) if event.source_id == target
        )
    except StopIteration as exc:
        available = ", ".join(event.source_id.removeprefix("cll=") for event in events)
        raise ValueError(
            f"unknown CLL edition {args.edition!r}; available: {available}"
        ) from exc
    bodies = git_output(config.corpus, ["log", "--format=%B"]) if status.head else ""
    known = {
        line.removeprefix("Source-Id: ")
        for line in bodies.splitlines()
        if line.startswith("Source-Id: cll=")
    }
    ordered_ids = [event.source_id for event in events]
    unknown = known - set(ordered_ids)
    prefix = 0
    while prefix < len(ordered_ids) and ordered_ids[prefix] in known:
        prefix += 1
    if unknown or any(source_id in known for source_id in ordered_ids[prefix:]):
        raise ValueError(
            "existing CLL render commits are not a chronological edition prefix"
        )
    commits = 0
    head = status.head
    for event in events[: stop + 1]:
        if event.source_id in known:
            continue
        head = commit_event(event, config.corpus)
        known.add(event.source_id)
        commits += 1
    print(f"cll render: edition={args.edition} commits={commits} head={head}")
    return 0


def _until(value: str | None) -> datetime | None:
    if value is None:
        return None
    raise ValueError(
        "--until is not supported until every selected projector accepts a cut-off"
    )


def _build(args: argparse.Namespace, config: Config) -> int:
    report = build_corpus(
        config,
        source_factories(config, args.sources),
        until=_until(args.until),
    )
    print(
        f"build: head={report.head} commits={report.commits} events={report.events} "
        f"snapshot={report.snapshot}"
    )
    if args.push:
        pushed = push_main_ranges(config.corpus, report.snapshot)
        print(f"push: main_updates={pushed.main_updates} snapshot={pushed.snapshot}")
    return 0


def _update(args: argparse.Namespace, config: Config) -> int:
    report = update_corpus(config, source_factories(config, args.sources or None))
    if report is None:
        print("update: no new source events")
    else:
        print(
            f"update: head={report.head} commits={report.commits} "
            f"events={report.events} snapshot={report.snapshot}"
        )
        if args.push:
            pushed = push_main_ranges(config.corpus, report.snapshot)
            print(
                f"push: main_updates={pushed.main_updates} snapshot={pushed.snapshot}"
            )
    return 0


def _verify(args: argparse.Namespace, config: Config) -> int:
    if args.events:
        audit = audit_events(source_factories(config, args.sources or None))
        for source, source_id, problem in audit.invalid:
            print(f"invalid event: {source} {source_id}: {problem}")
        print(f"verify events: events={audit.events} invalid={len(audit.invalid)}")
        return 1 if audit.invalid else 0
    report = verify_corpus(config.corpus)
    print(
        f"verify: commits={report.commits} files={report.files} "
        f"sources={report.sources} csv_indexes={report.csv_indexes} "
        f"mail_messages={report.mail_messages}"
    )
    return 0


def _leaf(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
    handler: Handler,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(name)
    parser.set_defaults(handler=handler)
    return parser


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="jbomohi", description=__doc__)
    root.add_argument("-v", "--verbose", action="count", default=0)
    commands = root.add_subparsers(dest="command", required=True)

    corpus = commands.add_parser("corpus", help="manage the corpus repository")
    corpus_commands = corpus.add_subparsers(dest="corpus_command", required=True)
    _leaf(corpus_commands, "init", _corpus_init)
    _leaf(corpus_commands, "status", _corpus_status)

    archive = commands.add_parser(
        "archive", help="manage content-addressed raw archives"
    )
    archive_commands = archive.add_subparsers(dest="archive_command", required=True)
    fetch = _leaf(archive_commands, "fetch", _archive_fetch)
    fetch.add_argument("source")
    fetch.add_argument(
        "--since",
        help=(
            "UTC ISO timestamp for incremental acquisition; also refreshes cached "
            "page discovery and revision responses"
        ),
    )
    fetch.add_argument("--list", dest="list_name")
    fetch.add_argument("--max-pages", type=int)
    fetch.add_argument("--start", type=int, default=0)
    ingest = archive_commands.add_parser("ingest")
    ingest_commands = ingest.add_subparsers(dest="ingest_source", required=True)
    dictionary = _leaf(ingest_commands, "dictionary", _archive_ingest_dictionary)
    dictionary.add_argument("directory")
    dictionary.add_argument("--export-date", required=True)
    tiki = _leaf(ingest_commands, "tiki", _archive_ingest_tiki)
    tiki.add_argument("directory")
    tiki.add_argument("--export-date", required=True)
    tiki.add_argument(
        "--character-encoding",
        choices=("latin1-transcoded", "utf8"),
        default="latin1-transcoded",
    )
    wiki = _leaf(ingest_commands, "wiki", _archive_ingest_wiki)
    wiki.add_argument("directory")
    wiki.add_argument("--export-date", required=True)
    _leaf(archive_commands, "verify", _archive_verify)

    build = _leaf(commands, "build", _build)
    build.add_argument("--sources", nargs="+")
    build.add_argument("--until")
    build.add_argument("--push", action="store_true")

    update = _leaf(commands, "update", _update)
    update.add_argument("sources", nargs="*")
    update.add_argument("--push", action="store_true")
    verify = _leaf(commands, "verify", _verify)
    verify.add_argument(
        "--events",
        action="store_true",
        help="validate every event the sources would commit, and commit none",
    )
    verify.add_argument("--sources", nargs="+")

    cll = commands.add_parser("cll", help="CLL rendering commands")
    cll_commands = cll.add_subparsers(dest="cll_command", required=True)
    render = _leaf(cll_commands, "render", _cll_render)
    render.add_argument("edition")

    who = commands.add_parser("who", help="identity attestation helpers")
    who_commands = who.add_subparsers(dest="who_command", required=True)
    _leaf(who_commands, "propose", _not_implemented("who propose"))
    _leaf(who_commands, "promote", _not_implemented("who promote"))

    notes = commands.add_parser("notes", help="research note helpers")
    notes_commands = notes.add_subparsers(dest="notes_command", required=True)
    _leaf(notes_commands, "lint", _not_implemented("notes lint"))

    cite = commands.add_parser("cite", help="stable citation helpers")
    cite_commands = cite.add_subparsers(dest="cite_command", required=True)
    resolve = _leaf(cite_commands, "resolve", _not_implemented("cite resolve"))
    resolve.add_argument("citation")
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    try:
        config = Config.from_env()
        return args.handler(args, config)
    except (
        ArchiveError,
        ConfigError,
        CorpusError,
        EventError,
        GitError,
        SourceWiringError,
        OSError,
        ValueError,
    ) as exc:
        LOG.error("%s", exc)
        return 1
