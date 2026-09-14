"""Archive-to-event wiring for merged source projectors."""

from __future__ import annotations

import csv
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
from .project.dictionary import (
    load_dictionary_dump,
    load_jbovlaste_dump,
)
from .project.dictionary import project as project_dictionary
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


class SourceWiringError(RuntimeError):
    """Required archive inputs for a projector are absent or ambiguous."""


def mediawiki_pages_from_corpus(corpus: Path) -> dict[str, str]:
    """Read the prior verified wiki title/path index for Tiki migration mapping."""

    index = corpus / "_meta" / "wiki" / "pages.csv"
    if not index.is_file():
        return {}
    result: dict[str, str] = {}
    with index.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not {"title", "path"} <= set(reader.fieldnames):
            raise SourceWiringError(f"wiki pages index has unexpected columns: {index}")
        for row_number, row in enumerate(reader, 2):
            title = row.get("title") or ""
            relative = row.get("path") or ""
            path = corpus / relative
            if not title or not relative or not path.is_file():
                raise SourceWiringError(
                    f"wiki pages index row is incomplete at {index}:{row_number}"
                )
            content = path.read_text(encoding="utf-8")
            previous = result.get(title)
            if previous is not None and previous != content:
                raise SourceWiringError(f"duplicate wiki title in index: {title!r}")
            result[title] = content
    return result


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


def _tiki_titles(data) -> list[str]:
    return sorted(
        {
            decode_character_text(
                row["pageName"] or b"",
                "Tiki title",
                "latin1-transcoded",
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
    data = load_tiki_dump(
        _component(config.archive, root, "tiki-content.sanitized.sql.gz")
    )
    users = load_tiki_users(
        _component(config.archive, root, "tiki-users.tsv.gz"),
        _component(config.archive, root, "tiki-user-preferences.tsv.gz"),
        character_encoding="latin1-transcoded",
    )
    migrated = (
        migrated_title_map(_tiki_titles(data), mediawiki_pages)
        if mediawiki_pages is not None
        else {}
    )
    return project_tiki(
        data,
        users,
        character_encoding="latin1-transcoded",
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
    with tempfile.TemporaryDirectory(
        prefix="jbomohi-mail-", dir=config.repo_root.parent
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
        old = list(load_old_lojban_manifestations(config.archive))
        sources = chain(
            *maildirs,
            load_mbox_manifestations(config.archive),
            *mhonarc,
            load_jbosnu_manifestations(config.archive),
            old,
        )
        gaps = {
            list_name: dict(values)
            for list_name, values in DEFAULT_ARCHIVE_GAPS.items()
        }
        old_count = len(
            list(
                (
                    config.archive
                    / "manifests"
                    / "mail"
                    / "lojban-list"
                    / "old-lojban-list"
                ).glob("msg*.toml")
            )
        )
        if old_count >= 19_674:
            gaps["lojban-list"].pop("old_lojban_list", None)
        beginners_count = len(list(beginners_root.glob("msg*.toml")))
        if beginners_count >= 20_910:
            gaps.pop("lojban-beginners", None)
        yield from project_mail(sources, archive_gaps=gaps)


def source_factories(
    config: Config,
    names: Sequence[str] | None = None,
    *,
    mediawiki_pages: Mapping[str, str] | None = None,
) -> dict[str, EventFactory]:
    """Resolve requested merged projectors without importing unmerged wiki code."""

    selected = tuple(names or ("irc", "dict", "tiki", "mail"))
    if mediawiki_pages is None:
        mediawiki_pages = mediawiki_pages_from_corpus(config.corpus)
    unknown = set(selected) - {"irc", "dict", "tiki", "mail"}
    if unknown:
        raise SourceWiringError(
            f"source projector is not merged: {', '.join(sorted(unknown))}"
        )
    factories: dict[str, EventFactory] = {}
    if "irc" in selected:
        factories["irc"] = lambda: irc_events(config)
    if "dict" in selected:
        factories["dict"] = lambda: dictionary_events(config)
    if "tiki" in selected:
        factories["tiki"] = lambda: tiki_events(config, mediawiki_pages)
    if "mail" in selected:
        factories["mail"] = lambda: mail_events(config)
    return factories
