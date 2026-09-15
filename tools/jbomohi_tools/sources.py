"""Archive-to-event wiring for merged source projectors."""

from __future__ import annotations

import tempfile
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from itertools import chain
from pathlib import Path

from .archive import (
    MAILDIR_LISTS,
    MHONARC_LISTS,
    extract_maildir_zip,
    load_jbosnu_manifestations,
    load_mbox_manifestations,
    load_mhonarc_manifestations,
    load_old_lojban_manifestations,
)
from .archive.manifest import ArchiveManifest, object_path
from .build import EventFactory
from .config import Config
from .git import Event
from .project.cll import project as project_cll
from .project.dictionary import (
    load_dictionary_dump,
    load_jbovlaste_dump,
)
from .project.dictionary import project as project_dictionary
from .project.grammars import project as project_grammars
from .project.irc import load_archive as load_irc_archive
from .project.irc import project as project_irc
from .project.mail import DEFAULT_ARCHIVE_GAPS, load_maildir
from .project.mail import project as project_mail
from .project.tiki import (
    decode_character_text,
    load_tiki_dump,
    load_tiki_users,
    migrated_title_map,
)
from .project.tiki import project as project_tiki
from .project.wiki import WikiLogEvent, WikiMedia, WikiPageFragment
from .project.wiki import load_archive as load_wiki_archive
from .project.wiki import load_log_archive as load_wiki_log_archive
from .project.wiki import load_media_archive as load_wiki_media_archive
from .project.wiki import merge_fragments as merge_wiki_fragments
from .project.wiki import project as project_wiki
from .project.wiki_sql import (
    WikiProjectorInputs,
    WikiSqlDump,
    combine_inputs,
    load_dump_archive,
)


class SourceWiringError(RuntimeError):
    """Required archive inputs for a projector are absent or ambiguous."""


# Complete page inventories recorded in SPEC.md section 3.3.
OLD_LOJBAN_LIST_PAGE_COUNT = 19_674
LOJBAN_BEGINNERS_MHONARC_PAGE_COUNT = 20_910
LOJBAN_BEGINNERS_MHONARC_KNOWN_MISSING = frozenset({5_411, 5_412})


def mediawiki_pages_from_archive(
    config: Config, fragments: Iterable[WikiPageFragment] | None = None
) -> dict[str, str]:
    """Build Tiki's migration map from the same archived wiki projection input."""

    result: dict[str, str] = {}
    source_fragments = (
        load_wiki_archive(config.archive) if fragments is None else fragments
    )
    for page in merge_wiki_fragments(source_fragments):
        if not page.revisions or page.revisions[-1].content is None:
            continue
        previous = result.get(page.title)
        content = page.revisions[-1].content
        if previous is not None and previous != content:
            raise SourceWiringError(f"duplicate wiki title in archive: {page.title!r}")
        result[page.title] = content
    return result


class _Unset:
    """Distinguishes "no export is ingested" from "the caller did not say"."""


UNSET = _Unset()


def wiki_inputs(
    config: Config,
    *,
    fragments: Sequence[WikiPageFragment] | None = None,
    logs: Sequence[WikiLogEvent] | None = None,
    dump: WikiSqlDump | None | _Unset = UNSET,
) -> WikiProjectorInputs:
    """Union the archived API crawl with the operator export, if one is held.

    SPEC.md 3.2 gives the wiki both inputs and defines them as equal over their
    intersection, so the build projects the union: the export supplies the
    deleted lineages and the actor-less revisions `api.php` cannot serve, and
    `_meta/wiki/coverage.toml` names every such class.
    """

    api_fragments = (
        load_wiki_archive(config.archive) if fragments is None else list(fragments)
    )
    api_logs = load_wiki_log_archive(config.archive) if logs is None else list(logs)
    export = load_dump_archive(config.archive) if isinstance(dump, _Unset) else dump
    return combine_inputs(export, api_fragments, api_logs)


def wiki_events(
    config: Config,
    *,
    inputs: WikiProjectorInputs | None = None,
    media: Iterable[WikiMedia] | None = None,
) -> Iterable[Event]:
    resolved = wiki_inputs(config) if inputs is None else inputs
    return project_wiki(
        resolved.fragments,
        resolved.logs,
        load_wiki_media_archive(config.archive) if media is None else media,
        resolved.extra_gaps,
        resolved.ended_at,
        resolved.unaccounted,
        resolved.additive,
    )


def cll_events(config: Config) -> Iterable[Event]:
    return project_cll(config.archive)


def grammar_events(config: Config) -> Iterable[Event]:
    return project_grammars(config.archive)


def _component(archive: Path, root: Path, prefix: str) -> Path:
    matches = sorted(root.glob(prefix + "-*.toml"))
    if len(matches) != 1:
        raise SourceWiringError(
            f"expected one archive manifest beginning {prefix!r} under {root}, "
            f"found {len(matches)}"
        )
    manifest = ArchiveManifest.load(matches[0])
    obj = object_path(archive, manifest.sha256)
    if not obj.is_file() or obj.stat().st_size != manifest.bytes:
        raise SourceWiringError(f"archive object missing or wrong-sized: {obj}")
    return obj


def dictionary_events(config: Config) -> Iterable[Event]:
    root = config.archive / "manifests" / "dict" / "db-export"
    current = load_dictionary_dump(
        _component(config.archive, root, "lensisku-public-data.sanitized-v3.sql"),
        _component(config.archive, root, "lensisku-users-public.csv"),
        _component(config.archive, root, "lensisku-definition-scores.csv"),
    )
    older = load_jbovlaste_dump(
        _component(config.archive, root, "jbovlaste-public.sanitized.sql.gz"),
        _component(config.archive, root, "jbovlaste-users-public.csv"),
        _component(config.archive, root, "jbovlaste-definition-scores.csv"),
    )
    manifests = sorted(root.glob("*.toml"))
    if not manifests:
        raise SourceWiringError("dictionary export manifests are absent")
    origins = {ArchiveManifest.load(path).origin for path in manifests}
    if len(origins) != 1:
        raise SourceWiringError("dictionary export manifests disagree on origin")
    origin = origins.pop()
    try:
        export_date = date.fromisoformat(origin.removeprefix("operator export "))
    except ValueError as exc:
        raise SourceWiringError(
            f"dictionary export origin has no ISO date: {origin}"
        ) from exc
    return project_dictionary(
        current,
        export_date=export_date.isoformat(),
        older=older,
    )


def _tiki_titles(data, character_encoding: str) -> list[str]:
    return sorted(
        {
            decode_character_text(
                row["pageName"] or b"",
                "Tiki title",
                character_encoding,
                allow_nul=True,
            )[0]
            for table in ("tiki_pages", "tiki_history")
            for row in data.tables[table]
        }
    )


def tiki_events(
    config: Config, mediawiki_pages: Mapping[str, str] | None = None
) -> Iterable[Event]:
    root = config.archive / "manifests" / "tiki" / "db-export"
    manifests = sorted(root.glob("*.toml"))
    if len(manifests) != 3:
        raise SourceWiringError(
            f"expected three Tiki db-export manifests, found {len(manifests)}"
        )
    encodings = {
        ArchiveManifest.load(path).coverage.get("character_encoding")
        for path in manifests
    }
    if len(encodings) != 1 or None in encodings:
        raise SourceWiringError("Tiki export manifests disagree on character_encoding")
    character_encoding = encodings.pop()
    if character_encoding not in {"latin1-transcoded", "utf8"}:
        raise SourceWiringError(
            f"unsupported Tiki character_encoding: {character_encoding!r}"
        )
    assert isinstance(character_encoding, str)
    data = load_tiki_dump(
        _component(config.archive, root, "tiki-content.sanitized.sql.gz")
    )
    users = load_tiki_users(
        _component(config.archive, root, "tiki-users.tsv.gz"),
        _component(config.archive, root, "tiki-user-preferences.tsv.gz"),
        character_encoding=character_encoding,
    )
    migrated = (
        migrated_title_map(_tiki_titles(data, character_encoding), mediawiki_pages)
        if mediawiki_pages is not None
        else {}
    )
    return project_tiki(
        data,
        users,
        character_encoding=character_encoding,
        migrated_titles=migrated,
    )


def irc_events(config: Config) -> Iterable[Event]:
    return project_irc(load_irc_archive(config.archive))


def _maildir_manifest(config: Config, list_name: str) -> Path:
    root = config.archive / "manifests" / "mail" / list_name / "maildir-zip"
    matches = sorted(root.glob("*.toml"))
    if len(matches) != 1:
        raise SourceWiringError(
            f"expected one Maildir manifest for {list_name}, found {len(matches)}"
        )
    manifest = ArchiveManifest.load(matches[0])
    return object_path(config.archive, manifest.sha256)


def mail_events(config: Config) -> Iterable[Event]:
    temporary_root = config.tmp
    temporary_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="jbomohi-mail-", dir=temporary_root
    ) as temporary:
        root = Path(temporary)
        maildirs = []
        for list_name in MAILDIR_LISTS:
            destination = root / list_name
            extract_maildir_zip(_maildir_manifest(config, list_name), destination)
            maildirs.append(
                load_maildir(
                    destination / "maildir",
                    list_name=list_name,
                    provenance_prefix=f"maildir-zip/{list_name}",
                )
            )
        mhonarc = [
            load_mhonarc_manifestations(config.archive, list_name)
            for list_name in MHONARC_LISTS
        ]
        beginners_root = (
            config.archive / "manifests" / "mail" / "lojban-beginners" / "mhonarc"
        )
        if beginners_root.exists() and any(beginners_root.glob("msg*.toml")):
            mhonarc.append(
                load_mhonarc_manifestations(config.archive, "lojban-beginners")
            )
        sources = chain(
            *maildirs,
            load_mbox_manifestations(config.archive),
            *mhonarc,
            load_jbosnu_manifestations(config.archive),
            load_old_lojban_manifestations(config.archive),
        )
        gaps = {
            list_name: dict(values)
            for list_name, values in DEFAULT_ARCHIVE_GAPS.items()
        }
        old_count = sum(
            1
            for _path in (
                config.archive
                / "manifests"
                / "mail"
                / "lojban-list"
                / "old-lojban-list"
            ).glob("msg*.toml")
        )
        if old_count >= OLD_LOJBAN_LIST_PAGE_COUNT:
            gaps["lojban-list"].pop("old_lojban_list", None)
        beginners_ids = {
            int(path.name[3:8])
            for path in beginners_root.glob("msg*.toml")
            if len(path.name) > 8 and path.name[3:8].isdigit()
        }
        missing_beginners = (
            set(range(LOJBAN_BEGINNERS_MHONARC_PAGE_COUNT)) - beginners_ids
        )
        if missing_beginners == set(LOJBAN_BEGINNERS_MHONARC_KNOWN_MISSING):
            if LOJBAN_BEGINNERS_MHONARC_KNOWN_MISSING:
                pages = ", ".join(
                    f"msg{value:05d}.html"
                    for value in sorted(LOJBAN_BEGINNERS_MHONARC_KNOWN_MISSING)
                )
                gaps["lojban-beginners"] = {
                    "mhonarc_missing_pages": (
                        f"numbered pages unavailable (HTTP 404): {pages}"
                    )
                }
            else:
                gaps.pop("lojban-beginners", None)
        yield from project_mail(sources, archive_gaps=gaps)


def source_factories(
    config: Config,
    names: Sequence[str] | None = None,
    *,
    mediawiki_pages: Mapping[str, str] | None = None,
) -> dict[str, EventFactory]:
    """Resolve requested merged projectors and their same-build dependencies."""

    available = {"wiki", "irc", "dict", "tiki", "mail", "cll", "grammars"}
    selected = tuple(names or sorted(available))
    wants_wiki = bool({"wiki", "tiki"} & set(selected))
    wiki_api_fragments = load_wiki_archive(config.archive) if wants_wiki else None
    wiki_dump = load_dump_archive(config.archive) if wants_wiki else None
    if "tiki" in selected and mediawiki_pages is None:
        assert wiki_api_fragments is not None
        # Tiki's migration map needs the wiki's *current* pages, so it sees the
        # live fragments of both inputs and not the deleted lineages the export
        # lets the build rebuild.
        live = [
            *(wiki_dump.fragments if wiki_dump is not None else ()),
            *wiki_api_fragments,
        ]
        mediawiki_pages = mediawiki_pages_from_archive(config, live)
    unknown = set(selected) - available
    if unknown:
        raise SourceWiringError(
            f"unknown source projector: {', '.join(sorted(unknown))}"
        )
    factories: dict[str, EventFactory] = {}
    if "wiki" in selected:
        assert wiki_api_fragments is not None
        wiki_media = load_wiki_media_archive(config.archive)
        combined = wiki_inputs(
            config,
            fragments=wiki_api_fragments,
            logs=load_wiki_log_archive(config.archive),
            dump=wiki_dump,
        )
        factories["wiki"] = lambda: wiki_events(
            config, inputs=combined, media=wiki_media
        )
    if "irc" in selected:
        factories["irc"] = lambda: irc_events(config)
    if "dict" in selected:
        factories["dict"] = lambda: dictionary_events(config)
    if "tiki" in selected:
        factories["tiki"] = lambda: tiki_events(config, mediawiki_pages)
    if "mail" in selected:
        factories["mail"] = lambda: mail_events(config)
    if "cll" in selected:
        factories["cll"] = lambda: cll_events(config)
    if "grammars" in selected:
        factories["grammars"] = lambda: grammar_events(config)
    return factories
