"""Pure MediaWiki revision parsing and projection."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import unicodedata
from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from dataclasses import field as dataclass_field
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from ..archive.manifest import ArchiveManifest, object_path
from ..git import Event, Identity


class WikiParseError(ValueError):
    """A wiki response or projection invariant failed closed."""


NAMESPACE_DIRS = {
    0: "main",
    1: "talk",
    2: "user",
    3: "user_talk",
    4: "lojban",
    5: "lojban_talk",
    6: "file",
    7: "file_talk",
    8: "mediawiki",
    9: "mediawiki_talk",
    10: "template",
    11: "template_talk",
    12: "help",
    13: "help_talk",
    14: "category",
    15: "category_talk",
    200: "userwiki",
    201: "userwiki_talk",
    202: "user_profile",
    203: "user_profile_talk",
    828: "module",
    829: "module_talk",
}
SAFE_SLUG = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'_,-"
)
PAGE_COLUMNS = (
    "pageid",
    "ns",
    "title",
    "path",
    "is_redirect",
    "first_rev",
    "last_rev",
    "revisions",
)
REVISION_COLUMNS = (
    "revid",
    "pageid",
    "parentid",
    "timestamp",
    "user",
    "size",
    "sha1",
    "comment",
)
GAP_COLUMNS = ("revid", "logid", "pageid", "title", "timestamp", "reason")
ERROR_COLUMNS = ("pageid", "ns", "title", "error")
MEDIA_COLUMNS = (
    "pageid",
    "title",
    "url",
    "sha1",
    "size",
    "mime",
    "uploaded",
    "uploader",
)


@dataclass(frozen=True, slots=True)
class WikiRevision:
    revid: int
    parentid: int
    timestamp: datetime
    user: str | None
    comment: str
    size: int | None
    sha1: str | None
    content: str | None
    text_hidden: bool = False
    text_missing: bool = False
    user_hidden: bool = False
    comment_hidden: bool = False
    # The source records no author at all, which SPEC.md 2.5 keeps distinct
    # from a suppressed one: `unrecorded@` rather than `anonymous@`.
    author_unrecorded: bool = False
    # Why the content could not be resolved, for the gaps.csv row. Each input
    # can only say what it itself could not resolve — the API knows the blob is
    # gone, the export knows which `text` row is missing — so this explanation
    # is deliberately outside the revision's identity: the two paths agree that
    # the text is unresolvable, and the export's more specific cause wins when
    # both are loaded.
    text_cause: str = dataclass_field(default="", compare=False)


@dataclass(frozen=True, slots=True)
class WikiPageFragment:
    pageid: int
    namespace: int
    title: str
    is_redirect: bool
    revisions: tuple[WikiRevision, ...]


@dataclass(frozen=True, slots=True)
class WikiPage:
    pageid: int
    namespace: int
    title: str
    is_redirect: bool
    revisions: tuple[WikiRevision, ...]

    @property
    def path(self) -> str:
        return wiki_path(self.namespace, self.title)


@dataclass(frozen=True, slots=True)
class WikiLogEvent:
    logid: int
    log_type: str
    pageid: int
    namespace: int
    title: str
    timestamp: datetime
    user: str | None
    comment: str
    target_namespace: int | None = None
    target_title: str | None = None
    suppress_redirect: bool = False
    move_redir: bool = False


@dataclass(frozen=True, slots=True)
class WikiMedia:
    pageid: int
    title: str
    url: str
    sha1: str
    size: int
    mime: str
    uploaded: datetime
    uploader: str | None


def slug(title: str) -> str:
    """Apply SPEC §3.1.5 to one canonical source title."""

    if not isinstance(title, str) or not title:
        raise WikiParseError("slug title must be non-empty text")
    normalized = unicodedata.normalize("NFC", title)
    tokens: list[str] = []
    for char in normalized:
        if char == " ":
            tokens.append("_")
        elif char in SAFE_SLUG:
            tokens.append(char)
        else:
            tokens.extend(f"%{byte:02X}" for byte in char.encode("utf-8"))
    if normalized.startswith("-"):
        tokens[0] = "%2D"
    encoded = "".join(tokens)
    if len(encoded.encode("ascii")) <= 200:
        return encoded
    suffix = "-" + hashlib.sha1(normalized.encode()).hexdigest()[:8]
    kept: list[str] = []
    length = 0
    for token in tokens:
        if length + len(token) + len(suffix) > 200:
            break
        kept.append(token)
        length += len(token)
    return "".join(kept) + suffix


def _page_title(namespace: int, title: str) -> str:
    if namespace == 0:
        return title
    prefix, separator, remainder = title.partition(":")
    if not separator or not prefix or not remainder:
        raise WikiParseError(f"namespace {namespace} title lacks a prefix: {title!r}")
    return remainder


def wiki_path(namespace: int, title: str) -> str:
    try:
        directory = NAMESPACE_DIRS[namespace]
    except KeyError as exc:
        raise WikiParseError(f"unsupported wiki namespace: {namespace}") from exc
    return f"wiki/{directory}/{slug(_page_title(namespace, title))}.wiki"


def verify_slug_injectivity(pages: Iterable[tuple[int, str]]) -> None:
    seen: dict[tuple[int, str], str] = {}
    for namespace, title in pages:
        path = wiki_path(namespace, title)
        key = (namespace, path)
        previous = seen.get(key)
        if previous is not None and previous != title:
            raise WikiParseError(
                f"wiki slug collision in namespace {namespace}: {previous!r} and {title!r} -> {path}"
            )
        seen[key] = title


def _integer(value: object, label: str, *, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise WikiParseError(f"{label} must be an integer >= {minimum}")
    return value


def _optional_integer(value: object, label: str) -> int | None:
    if value is None:
        return None
    return _integer(value, label)


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise WikiParseError("wiki revision timestamp must be UTC ISO text")
    try:
        parsed = datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError as exc:
        raise WikiParseError(f"invalid wiki revision timestamp: {value!r}") from exc
    if parsed.tzinfo != UTC or parsed.microsecond:
        raise WikiParseError(f"invalid wiki revision timestamp: {value!r}")
    return parsed


def _revision(raw: object, pageid: int) -> WikiRevision:
    if not isinstance(raw, dict):
        raise WikiParseError(f"page {pageid}: revision must be an object")
    revid = _integer(raw.get("revid"), "revid", minimum=1)
    parentid = _integer(raw.get("parentid", 0), "parentid")
    timestamp = _timestamp(raw.get("timestamp"))
    user_hidden = bool(raw.get("userhidden"))
    comment_hidden = bool(raw.get("commenthidden"))
    text_hidden = bool(raw.get("texthidden"))
    user_value = raw.get("user")
    user = None if user_hidden else user_value
    if user is not None and (not isinstance(user, str) or not user):
        raise WikiParseError(f"revision {revid}: user must be non-empty text")
    comment_value = "" if comment_hidden else raw.get("comment", "")
    if not isinstance(comment_value, str):
        raise WikiParseError(f"revision {revid}: comment must be text")
    size = _optional_integer(raw.get("size"), "revision size")
    sha1 = raw.get("sha1")
    if sha1 is not None and (
        not isinstance(sha1, str) or not re.fullmatch(r"[0-9a-f]{40}", sha1)
    ):
        raise WikiParseError(f"revision {revid}: sha1 must be 40 lowercase hex digits")
    slots = raw.get("slots")
    main_slot = slots.get("main") if isinstance(slots, dict) else None
    text_missing = False
    if isinstance(main_slot, dict) and "textmissing" in main_slot:
        if main_slot["textmissing"] is not True:
            raise WikiParseError(f"revision {revid}: invalid textmissing marker")
        text_missing = True
    content: str | None = None
    text_cause = "text missing" if text_missing else ""
    if not text_hidden:
        if not isinstance(main_slot, dict):
            raise WikiParseError(f"revision {revid}: main content slot is missing")
        content_value = main_slot.get("content")
        if text_missing and "content" in main_slot:
            raise WikiParseError(
                f"revision {revid}: textmissing marker conflicts with content"
            )
        if not text_missing and not isinstance(content_value, str):
            raise WikiParseError(f"revision {revid}: main content is missing")
        if not text_missing:
            content = content_value
    if content is not None:
        # SPEC.md 3.2: content that disagrees with the source's declared size or
        # SHA-1 is a missing blob, not text. MediaWiki serves an empty string
        # for a revision whose `text` row is gone while still declaring the
        # original length, and publishing that as an empty page would be a lie.
        payload = content.encode("utf-8")
        if size is not None and len(payload) != size:
            content, text_missing = None, True
            text_cause = f"declared size {size} but served {len(payload)} bytes"
        elif sha1 is not None and hashlib.sha1(payload).hexdigest() != sha1:
            content, text_missing = None, True
            text_cause = "served content does not match the declared SHA-1"
    return WikiRevision(
        revid=revid,
        parentid=parentid,
        timestamp=timestamp,
        user=user,
        comment=comment_value,
        size=size,
        sha1=sha1,
        content=content,
        text_hidden=text_hidden,
        text_missing=text_missing,
        user_hidden=user_hidden,
        comment_hidden=comment_hidden,
        text_cause=text_cause,
    )


def parse_revision_response(payload: bytes) -> list[WikiPageFragment]:
    """Parse one formatversion=2 MediaWiki revisions response."""

    try:
        document = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WikiParseError(f"invalid MediaWiki JSON: {exc}") from exc
    if not isinstance(document, dict):
        raise WikiParseError("MediaWiki response must be an object")
    if "error" in document:
        raise WikiParseError(f"MediaWiki API error: {document['error']!r}")
    query = document.get("query")
    pages = query.get("pages") if isinstance(query, dict) else None
    if not isinstance(pages, list):
        raise WikiParseError("MediaWiki response has no query.pages list")
    fragments: list[WikiPageFragment] = []
    for raw_page in pages:
        if not isinstance(raw_page, dict):
            raise WikiParseError("MediaWiki page must be an object")
        pageid = _integer(raw_page.get("pageid"), "pageid", minimum=1)
        namespace = _integer(raw_page.get("ns"), "namespace")
        title = raw_page.get("title")
        if not isinstance(title, str) or not title:
            raise WikiParseError(f"page {pageid}: title must be non-empty text")
        raw_revisions = raw_page.get("revisions", [])
        if not isinstance(raw_revisions, list):
            raise WikiParseError(f"page {pageid}: revisions must be a list")
        revisions = tuple(_revision(item, pageid) for item in raw_revisions)
        fragments.append(
            WikiPageFragment(
                pageid=pageid,
                namespace=namespace,
                title=title,
                is_redirect=bool(raw_page.get("redirect")),
                revisions=revisions,
            )
        )
    return fragments


def parse_log_response(payload: bytes) -> list[WikiLogEvent]:
    """Parse move/delete entries from one formatversion=2 logevents response."""

    try:
        document = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WikiParseError(f"invalid MediaWiki log JSON: {exc}") from exc
    if not isinstance(document, dict):
        raise WikiParseError("MediaWiki log response must be an object")
    if "error" in document:
        raise WikiParseError(f"MediaWiki API error: {document['error']!r}")
    query = document.get("query")
    entries = query.get("logevents") if isinstance(query, dict) else None
    if not isinstance(entries, list):
        raise WikiParseError("MediaWiki response has no query.logevents list")
    events: list[WikiLogEvent] = []
    for raw in entries:
        if not isinstance(raw, dict):
            raise WikiParseError("MediaWiki log event must be an object")
        log_type = raw.get("type")
        action = raw.get("action")
        if (log_type, action) not in {
            ("move", "move"),
            ("move", "move_redir"),
            ("delete", "delete"),
        }:
            continue
        logid = _integer(raw.get("logid"), "logid", minimum=1)
        namespace = _integer(raw.get("ns"), "log namespace")
        pageid = _integer(raw.get("pageid", 0), "log pageid")
        title = raw.get("title")
        if not isinstance(title, str) or not title:
            raise WikiParseError(f"log event {logid}: title must be non-empty text")
        user_value = raw.get("user")
        user = None if raw.get("userhidden") else user_value
        if user is not None and (not isinstance(user, str) or not user):
            raise WikiParseError(f"log event {logid}: invalid user")
        comment = "" if raw.get("commenthidden") else raw.get("comment", "")
        if not isinstance(comment, str):
            raise WikiParseError(f"log event {logid}: invalid comment")
        params = raw.get("params", {})
        if not isinstance(params, dict):
            raise WikiParseError(f"log event {logid}: params must be an object")
        target_namespace = None
        target_title = None
        suppress_redirect = False
        if log_type == "move":
            target_namespace = _integer(
                params.get("target_ns"), "move target namespace"
            )
            target_title_value = params.get("target_title")
            if not isinstance(target_title_value, str) or not target_title_value:
                raise WikiParseError(f"log event {logid}: move target is missing")
            target_title = target_title_value
            suppress_redirect = bool(params.get("suppressredirect"))
        events.append(
            WikiLogEvent(
                logid=logid,
                log_type=log_type,
                pageid=pageid,
                namespace=namespace,
                title=title,
                timestamp=_timestamp(raw.get("timestamp")),
                user=user,
                comment=comment,
                target_namespace=target_namespace,
                target_title=target_title,
                suppress_redirect=suppress_redirect,
                move_redir=action == "move_redir",
            )
        )
    return events


def parse_media_response(payload: bytes) -> list[WikiMedia]:
    """Parse manifest-only file metadata from an allimages response."""

    try:
        document = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WikiParseError(f"invalid MediaWiki media JSON: {exc}") from exc
    if isinstance(document, dict) and "error" in document:
        raise WikiParseError(f"MediaWiki API error: {document['error']!r}")
    query = document.get("query") if isinstance(document, dict) else None
    images = query.get("allimages") if isinstance(query, dict) else None
    if not isinstance(images, list):
        raise WikiParseError("MediaWiki response has no query.allimages list")
    media: list[WikiMedia] = []
    for raw in images:
        if not isinstance(raw, dict):
            raise WikiParseError("MediaWiki allimages entry must be an object")
        short_url = raw.get("descriptionshorturl")
        if not isinstance(short_url, str):
            raise WikiParseError("MediaWiki image lacks descriptionshorturl")
        values = parse_qs(urlsplit(short_url).query).get("curid", [])
        try:
            pageid = int(values[0])
        except (IndexError, ValueError) as exc:
            raise WikiParseError("MediaWiki image lacks a numeric curid") from exc
        title = raw.get("title")
        url = raw.get("url")
        sha1 = raw.get("sha1")
        mime = raw.get("mime")
        user_value = None if raw.get("userhidden") else raw.get("user")
        if not all(isinstance(value, str) and value for value in (title, url, mime)):
            raise WikiParseError(f"MediaWiki image {pageid} lacks title/url/mime")
        if not isinstance(sha1, str) or not re.fullmatch(r"[0-9a-f]{40}", sha1):
            raise WikiParseError(f"MediaWiki image {pageid} has invalid sha1")
        size = _integer(raw.get("size"), "media size")
        user = user_value if isinstance(user_value, str) and user_value else None
        media.append(
            WikiMedia(
                pageid,
                title,
                url,
                sha1,
                size,
                mime,
                _timestamp(raw.get("timestamp")),
                user,
            )
        )
    return media


def load_archive(archive: Path) -> list[WikiPageFragment]:
    """Load and verify the newest archived response for each revision query."""

    root = archive / "manifests" / "wiki" / "revisions"
    if not root.exists():
        return []
    selected: dict[str, ArchiveManifest] = {}
    for path in sorted(root.glob("*.toml")):
        if path.is_symlink():
            raise WikiParseError(f"wiki manifest must not be a symlink: {path}")
        manifest = ArchiveManifest.load(path)
        previous = selected.get(manifest.origin)
        if previous is None or (manifest.fetched_at, manifest.sha256) > (
            previous.fetched_at,
            previous.sha256,
        ):
            selected[manifest.origin] = manifest
    fragments: list[WikiPageFragment] = []
    for origin, manifest in sorted(selected.items()):
        parsed = urlsplit(origin)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "mw.lojban.org"
            or parsed.path != "/api.php"
        ):
            raise WikiParseError(f"wiki manifest has invalid origin: {origin!r}")
        obj = object_path(archive, manifest.sha256)
        if obj.is_symlink():
            raise WikiParseError(f"wiki archive object must not be a symlink: {obj}")
        try:
            payload = obj.read_bytes()
        except OSError as exc:
            raise WikiParseError(f"wiki archive object is unreadable: {obj}") from exc
        if (
            len(payload) != manifest.bytes
            or hashlib.sha256(payload).hexdigest() != manifest.sha256
        ):
            raise WikiParseError(f"wiki archive object does not match manifest: {obj}")
        fragments.extend(parse_revision_response(payload))
    return fragments


def load_log_archive(archive: Path) -> list[WikiLogEvent]:
    """Load, verify, and deduplicate archived move/delete log batches."""

    root = archive / "manifests" / "wiki" / "logevents"
    if not root.exists():
        return []
    selected: dict[str, ArchiveManifest] = {}
    for path in sorted(root.glob("*.toml")):
        if path.is_symlink():
            raise WikiParseError(f"wiki log manifest must not be a symlink: {path}")
        manifest = ArchiveManifest.load(path)
        previous = selected.get(manifest.origin)
        if previous is None or (manifest.fetched_at, manifest.sha256) > (
            previous.fetched_at,
            previous.sha256,
        ):
            selected[manifest.origin] = manifest
    events: dict[int, WikiLogEvent] = {}
    for origin, manifest in sorted(selected.items()):
        parsed = urlsplit(origin)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "mw.lojban.org"
            or parsed.path != "/api.php"
        ):
            raise WikiParseError(f"wiki log manifest has invalid origin: {origin!r}")
        obj = object_path(archive, manifest.sha256)
        if obj.is_symlink():
            raise WikiParseError(f"wiki log object must not be a symlink: {obj}")
        try:
            payload = obj.read_bytes()
        except OSError as exc:
            raise WikiParseError(
                f"wiki log archive object is unreadable: {obj}"
            ) from exc
        if (
            len(payload) != manifest.bytes
            or hashlib.sha256(payload).hexdigest() != manifest.sha256
        ):
            raise WikiParseError(f"wiki log object does not match manifest: {obj}")
        for event in parse_log_response(payload):
            previous = events.get(event.logid)
            if previous is not None and previous != event:
                raise WikiParseError(f"log event {event.logid}: inconsistent duplicate")
            events[event.logid] = event
    return [events[logid] for logid in sorted(events)]


def load_media_archive(archive: Path) -> list[WikiMedia]:
    """Load and verify archived allimages metadata batches."""

    root = archive / "manifests" / "wiki" / "media"
    if not root.exists():
        return []
    selected: dict[str, ArchiveManifest] = {}
    for path in sorted(root.glob("*.toml")):
        if path.is_symlink():
            raise WikiParseError(f"wiki media manifest must not be a symlink: {path}")
        manifest = ArchiveManifest.load(path)
        previous = selected.get(manifest.origin)
        if previous is None or (manifest.fetched_at, manifest.sha256) > (
            previous.fetched_at,
            previous.sha256,
        ):
            selected[manifest.origin] = manifest
    media: dict[int, WikiMedia] = {}
    for origin, manifest in sorted(selected.items()):
        parsed = urlsplit(origin)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "mw.lojban.org"
            or parsed.path != "/api.php"
        ):
            raise WikiParseError(f"wiki media manifest has invalid origin: {origin!r}")
        obj = object_path(archive, manifest.sha256)
        if obj.is_symlink():
            raise WikiParseError(f"wiki media object must not be a symlink: {obj}")
        try:
            payload = obj.read_bytes()
        except OSError as exc:
            raise WikiParseError(f"wiki media object is unreadable: {obj}") from exc
        if (
            len(payload) != manifest.bytes
            or hashlib.sha256(payload).hexdigest() != manifest.sha256
        ):
            raise WikiParseError(f"wiki media object does not match manifest: {obj}")
        for item in parse_media_response(payload):
            previous = media.get(item.pageid)
            if previous is not None and previous != item:
                raise WikiParseError(
                    f"media page {item.pageid}: inconsistent duplicate"
                )
            media[item.pageid] = item
    return [media[pageid] for pageid in sorted(media)]


def merge_fragments(fragments: Iterable[WikiPageFragment]) -> list[WikiPage]:
    grouped: dict[int, list[WikiPageFragment]] = defaultdict(list)
    for fragment in fragments:
        grouped[fragment.pageid].append(fragment)
    pages: list[WikiPage] = []
    for pageid, parts in sorted(grouped.items()):
        identities = {(part.namespace, part.title, part.is_redirect) for part in parts}
        if len(identities) != 1:
            raise WikiParseError(f"page {pageid}: inconsistent response fragments")
        namespace, title, is_redirect = next(iter(identities))
        revisions: dict[int, WikiRevision] = {}
        for part in parts:
            for revision in part.revisions:
                previous = revisions.get(revision.revid)
                if previous is not None and previous != revision:
                    raise WikiParseError(
                        f"revision {revision.revid}: inconsistent duplicate response"
                    )
                revisions[revision.revid] = revision
        ordered = tuple(sorted(revisions.values(), key=lambda item: item.revid))
        pages.append(WikiPage(pageid, namespace, title, is_redirect, ordered))
    verify_slug_injectivity((page.namespace, page.title) for page in pages)
    return pages


def _anonymous(user: str | None) -> bool:
    return user is None


def _summary(title: str, revid: int, comment: str) -> str:
    cleaned_comment = " ".join(comment.split())[:40].rstrip()
    suffix = f" (rev {revid})"
    comment_suffix = f" {cleaned_comment}" if cleaned_comment else ""
    budget = 72 - len("wiki: ") - len(suffix) - len(comment_suffix)
    if budget < 1:
        comment_suffix = ""
        budget = 72 - len("wiki: ") - len(suffix)
    shown_title = title if len(title) <= budget else title[: max(1, budget - 1)] + "…"
    return f"{shown_title}{suffix}{comment_suffix}"


def _log_summary(title: str, logid: int, comment: str) -> str:
    cleaned_comment = " ".join(comment.split())[:40].rstrip()
    suffix = f" (log {logid})"
    comment_suffix = f" {cleaned_comment}" if cleaned_comment else ""
    budget = 72 - len("wiki: ") - len(suffix) - len(comment_suffix)
    if budget < 1:
        comment_suffix = ""
        budget = 72 - len("wiki: ") - len(suffix)
    shown_title = title if len(title) <= budget else title[: max(1, budget - 1)] + "…"
    return f"{shown_title}{suffix}{comment_suffix}"


def _toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _coverage_toml(additive: Sequence[tuple[str, int, str]]) -> str:
    """Render the additive coverage classes SPEC.md 3.2 requires.

    Each class is a kind of row one input holds and the other structurally
    cannot, so a reader can tell coverage apart from disagreement.
    """

    lines = [
        "# Rows one input holds and the other cannot serve (SPEC.md 3.2).",
        "# Written by jbomohi build; do not edit.",
        "",
    ]
    for name, count, cause in additive:
        if not re.fullmatch(r"[A-Za-z0-9_]+", name):
            raise WikiParseError(f"invalid coverage class name: {name!r}")
        lines.append(f"[additive.{name}]")
        lines.append(f"count = {count}")
        lines.append(f"cause = {_toml_string(cause)}")
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def _csv(columns: Sequence[str], rows: Iterable[dict[str, object]]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


@dataclass(frozen=True, slots=True)
class _WikiPlacementPlan:
    chains: dict[int, tuple[WikiLogEvent, ...]]
    move_owner: dict[int, int]
    current_revisions: frozenset[int]
    merged_revisions: frozenset[int]
    components: dict[int, tuple[tuple[WikiRevision, ...], ...]]
    current_start: dict[int, datetime]
    gap_rows: tuple[dict[str, object], ...]
    ambiguous_logids: frozenset[int]


def _revision_components(page: WikiPage) -> tuple[tuple[WikiRevision, ...], ...]:
    """Partition one API page response into its parent-linked lineages."""

    revisions = {item.revid: item for item in page.revisions}
    unassigned = set(revisions)
    components: list[tuple[WikiRevision, ...]] = []
    while unassigned:
        parents = {
            revisions[revid].parentid
            for revid in unassigned
            if revisions[revid].parentid in unassigned
        }
        leaves = unassigned - parents
        if not leaves:
            raise WikiParseError(
                f"page {page.pageid}: revision parent chain contains a cycle"
            )
        cursor = revisions[max(leaves)]
        reverse: list[WikiRevision] = []
        while cursor.revid in unassigned:
            reverse.append(cursor)
            unassigned.remove(cursor.revid)
            if cursor.parentid not in unassigned:
                break
            cursor = revisions[cursor.parentid]
        components.append(tuple(reversed(reverse)))
    return tuple(components)


def _page_move_chains(
    pages: Sequence[WikiPage],
    log_events: Sequence[WikiLogEvent],
    ended_at: Mapping[int, tuple[datetime, int]] = {},
) -> _WikiPlacementPlan:
    """Recover each current revision lineage without trusting log page IDs.

    `ended_at` bounds a lineage that no longer exists, as the `(timestamp,
    logid)` of the deletion that ended it. A deleted page holds its title only
    up to that point, so a later move into the title belongs to whichever page
    took it afterwards; MediaWiki logs the deletion and the move that reuses
    the title in the same second, which is why the bound needs the log id and
    not the timestamp alone. Without it a reused title makes one move log fit
    two lineages and placement fails closed.
    """

    moves_by_target: dict[tuple[int, str], list[WikiLogEvent]] = defaultdict(list)
    for item in log_events:
        if item.log_type != "move":
            continue
        assert item.target_namespace is not None and item.target_title is not None
        moves_by_target[(item.target_namespace, item.target_title)].append(item)

    chains: dict[int, tuple[WikiLogEvent, ...]] = {}
    owner_by_logid: dict[int, int] = {}
    current_revisions: set[int] = set()
    merged_revisions: set[int] = set()
    components_by_page: dict[int, tuple[tuple[WikiRevision, ...], ...]] = {}
    current_start: dict[int, datetime] = {}
    gap_rows: list[dict[str, object]] = []
    ambiguous_logids: set[int] = set()
    for page in pages:
        if not page.revisions:
            chains[page.pageid] = ()
            components_by_page[page.pageid] = ()
            continue
        components = _revision_components(page)
        components_by_page[page.pageid] = components
        current_component = next(
            values for values in components if page.revisions[-1] in values
        )
        current_ids = {item.revid for item in current_component}
        current_revisions.update(current_ids)
        merged_revisions.update(
            item.revid
            for values in components
            for item in values
            if item.revid not in current_ids
        )
        lineage_start = current_component[0]
        current_start[page.pageid] = lineage_start.timestamp
        target = (page.namespace, page.title)
        before: tuple[datetime, int] | None = ended_at.get(page.pageid)
        reverse_chain: list[WikiLogEvent] = []
        while True:
            candidates = [
                item
                for item in moves_by_target.get(target, ())
                if (before is None or (item.timestamp, item.logid) < before)
                and item.timestamp >= lineage_start.timestamp
                and item.namespace in NAMESPACE_DIRS
            ]
            if not candidates:
                break
            latest_time = max(item.timestamp for item in candidates)
            latest = [item for item in candidates if item.timestamp == latest_time]
            if len(latest) != 1:
                ids = sorted(item.logid for item in latest)
                ambiguous_logids.update(ids)
                gap_rows.append(
                    {
                        "revid": "",
                        "logid": "",
                        "pageid": page.pageid,
                        "title": target[1],
                        "timestamp": latest_time.isoformat().replace("+00:00", "Z"),
                        "reason": "move ambiguous: "
                        + ",".join(f"logid={value}" for value in ids),
                    }
                )
                break
            item = latest[0]
            previous_owner = owner_by_logid.get(item.logid)
            if previous_owner is not None and previous_owner != page.pageid:
                raise WikiParseError(
                    f"move log {item.logid} belongs to both page {previous_owner} "
                    f"and page {page.pageid}"
                )
            owner_by_logid[item.logid] = page.pageid
            reverse_chain.append(item)
            target = (item.namespace, item.title)
            before = (item.timestamp, item.logid)

        chain = tuple(reversed(reverse_chain))
        chains[page.pageid] = chain
    return _WikiPlacementPlan(
        chains,
        owner_by_logid,
        frozenset(current_revisions),
        frozenset(merged_revisions),
        components_by_page,
        current_start,
        tuple(gap_rows),
        frozenset(ambiguous_logids),
    )


def _position_at(
    page: WikiPage,
    chain: Sequence[WikiLogEvent],
    timestamp: datetime,
    move_times: dict[int, datetime] | None = None,
) -> tuple[int, str]:
    if chain:
        namespace = chain[0].namespace
        title = chain[0].title
    else:
        namespace = page.namespace
        title = page.title
    for move in chain:
        effective = move.timestamp if move_times is None else move_times[move.logid]
        if effective > timestamp:
            break
        assert move.target_namespace is not None and move.target_title is not None
        namespace = move.target_namespace
        title = move.target_title
    return namespace, title


def _revision_positions(
    pages: Sequence[WikiPage],
    plan: _WikiPlacementPlan,
    move_times: dict[int, datetime],
) -> tuple[dict[int, tuple[int, str]], list[dict[str, object]]]:
    positions: dict[int, tuple[int, str]] = {}
    gaps: list[dict[str, object]] = []
    for page in pages:
        chain = plan.chains[page.pageid]
        earliest = (
            (chain[0].namespace, chain[0].title)
            if chain
            else (page.namespace, page.title)
        )
        start = plan.current_start.get(page.pageid)
        for component in plan.components[page.pageid]:
            merged = component[0].revid not in plan.current_revisions
            fallback = merged and start is not None and component[-1].timestamp < start
            if fallback:
                path = wiki_path(*earliest)
                first = component[0]
                gaps.append(
                    {
                        "revid": first.revid,
                        "logid": "",
                        "pageid": page.pageid,
                        "title": page.title,
                        "timestamp": first.timestamp.isoformat().replace("+00:00", "Z"),
                        "reason": f"pre-merge title unknown; placed at {path}",
                    }
                )
            for revision in component:
                if fallback or (
                    merged and start is not None and revision.timestamp < start
                ):
                    positions[revision.revid] = earliest
                else:
                    positions[revision.revid] = _position_at(
                        page, chain, revision.timestamp, move_times
                    )
    return positions, gaps


def _forced_move_times(
    pages: Sequence[WikiPage],
    plan: _WikiPlacementPlan,
    positions: dict[int, tuple[int, str]],
) -> dict[int, datetime]:
    """Move migration-skewed marker/redirect revisions behind their rename."""

    effective = {
        move.logid: move.timestamp for chain in plan.chains.values() for move in chain
    }
    moves_by_id = {move.logid: move for chain in plan.chains.values() for move in chain}
    revisions_by_page = {
        page.pageid: {revision.revid: revision for revision in page.revisions}
        for page in pages
    }
    roots = {
        component[0].revid
        for components in plan.components.values()
        for component in components
    }
    redirect_roots: dict[tuple[int, str], list[WikiRevision]] = defaultdict(list)
    for page in pages:
        if not page.is_redirect:
            continue
        for revision in page.revisions:
            if (
                revision.revid in roots
                and revision.content is not None
                and revision.content.lstrip().upper().startswith("#REDIRECT")
            ):
                redirect_roots[positions[revision.revid]].append(revision)
    for logid, owner in sorted(plan.move_owner.items()):
        move = moves_by_id[logid]
        old_position = (move.namespace, move.title)
        assert move.target_title is not None
        candidates: list[datetime] = []
        for revision in revisions_by_page[owner].values():
            skew = (move.timestamp - revision.timestamp).total_seconds()
            if (
                0 < skew <= 60
                and positions[revision.revid] == old_position
                and move.title in revision.comment
                and move.target_title in revision.comment
            ):
                candidates.append(revision.timestamp)
        for revision in redirect_roots.get(old_position, ()):
            skew = (move.timestamp - revision.timestamp).total_seconds()
            if 0 < skew <= 60:
                candidates.append(revision.timestamp)
        if candidates:
            forced = min(candidates)
            # A page moved away and back between the same two titles gives both
            # moves a null revision whose comment names both titles, so rule 4's
            # test fits the second move as well as the first. A move can never
            # be ordered at or before the move that precedes it in its own
            # page's chain, so that pair is left alone.
            chain = plan.chains[owner]
            position = [move.logid for move in chain].index(logid)
            if position and forced <= effective[chain[position - 1].logid]:
                continue
            effective[logid] = forced
    return effective


def project(
    fragments: Iterable[WikiPageFragment],
    logs: Iterable[WikiLogEvent] = (),
    media: Iterable[WikiMedia] = (),
    extra_gaps: Iterable[Mapping[str, object]] = (),
    ended_at: Mapping[int, tuple[datetime, int]] = {},
    unaccounted: Iterable[int] = (),
    additive: Sequence[tuple[str, int, str]] = (),
) -> Iterator[Event]:
    """Project API- or dump-derived revisions and log events identically.

    `extra_gaps` carries rows an input recorded before projection began, such as
    the rows of the SQL export that name no projectable page (SPEC.md 3.2).
    They are appended to `_meta/wiki/gaps.csv` in the order given. `ended_at`
    gives, per backfilled deleted lineage, the `(timestamp, logid)` of the
    deletion after which it no longer holds its title.
    """

    pages = merge_fragments(fragments)
    page_by_id = {page.pageid: page for page in pages}
    log_events = sorted(logs, key=lambda item: (item.timestamp, item.logid))
    placement = _page_move_chains(pages, log_events, dict(ended_at))
    actual_move_times = {
        move.logid: move.timestamp
        for chain in placement.chains.values()
        for move in chain
    }
    revision_positions, merged_gaps = _revision_positions(
        pages, placement, actual_move_times
    )
    move_times = _forced_move_times(pages, placement, revision_positions)
    revision_positions, merged_gaps = _revision_positions(pages, placement, move_times)
    state_content: dict[int, bytes | None] = {}
    held_by_path: dict[str, int] = {}
    placeholder_paths: set[str] = set()
    # Why a path is a placeholder, so the release is reported in the right
    # words: a merged pre-move chain, or a deleted lineage nothing accounts for.
    placeholder_reason: dict[str, str] = {}
    unaccounted_pages = set(unaccounted)
    for page in pages:
        state_content[page.pageid] = None

    revision_pages = [(revision, page) for page in pages for revision in page.revisions]
    page_rows = [
        {
            "pageid": page.pageid,
            "ns": page.namespace,
            "title": page.title,
            "path": page.path,
            "is_redirect": str(page.is_redirect).lower(),
            "first_rev": page.revisions[0].revid if page.revisions else "",
            "last_rev": page.revisions[-1].revid if page.revisions else "",
            "revisions": len(page.revisions),
        }
        for page in pages
    ]
    error_rows = [
        {
            "pageid": page.pageid,
            "ns": page.namespace,
            "title": page.title,
            "error": "no public revisions returned",
        }
        for page in pages
        if not page.revisions
    ]
    media_rows = [
        {
            "pageid": item.pageid,
            "title": item.title,
            "url": item.url,
            "sha1": item.sha1,
            "size": item.size,
            "mime": item.mime,
            "uploaded": item.uploaded.isoformat().replace("+00:00", "Z"),
            "uploader": "anonymous" if _anonymous(item.uploader) else item.uploader,
        }
        for item in sorted(media, key=lambda value: value.pageid)
    ]
    revision_rows: list[dict[str, object]] = []
    gap_rows: list[dict[str, object]] = [
        *placement.gap_rows,
        *merged_gaps,
        *(dict(row) for row in extra_gaps),
    ]
    for revision, page in revision_pages:
        anonymous = _anonymous(revision.user) or revision.user_hidden
        user = "unrecorded" if revision.author_unrecorded else revision.user
        if user is None or (anonymous and not revision.author_unrecorded):
            user = "anonymous"
        revision_rows.append(
            {
                "revid": revision.revid,
                "pageid": page.pageid,
                "parentid": revision.parentid,
                "timestamp": revision.timestamp.isoformat().replace("+00:00", "Z"),
                "user": user,
                "size": revision.size if revision.size is not None else "",
                "sha1": revision.sha1 or "",
                "comment": "" if revision.comment_hidden else revision.comment,
            }
        )
        reasons: list[str] = []
        if revision.text_hidden:
            reasons.append("text suppressed")
        if revision.text_missing:
            reasons.append(
                f"text unresolvable: {revision.text_cause or 'text missing'}"
            )
        if revision.user_hidden:
            reasons.append("user suppressed")
        if revision.comment_hidden:
            reasons.append("comment suppressed")
        if reasons:
            gap_rows.append(
                {
                    "revid": revision.revid,
                    "logid": "",
                    "pageid": page.pageid,
                    "title": page.title,
                    "timestamp": revision.timestamp.isoformat().replace("+00:00", "Z"),
                    "reason": "; ".join(reasons),
                }
            )

    timeline = [
        (revision.timestamp, 1, revision.revid, "revision", revision, page)
        for revision, page in revision_pages
    ]
    timeline.extend(
        (
            move_times.get(log.logid, log.timestamp),
            0,
            log.logid,
            "log",
            log,
            None,
        )
        for log in log_events
    )
    timeline.sort(key=lambda item: (item[0], item[1], item[2]))
    pending_event: Event | None = None
    for _timestamp_value, _kind_order, _stable_id, kind, item, page in timeline:
        if kind == "revision":
            assert isinstance(item, WikiRevision) and isinstance(page, WikiPage)
            anonymous = _anonymous(item.user) or item.user_hidden
            if item.author_unrecorded:
                author = Identity.unrecorded("mw.lojban.org")
            elif anonymous:
                author = Identity.anonymous("mw.lojban.org")
            else:
                author = Identity.namespaced("mw.lojban.org", item.user or "")
            position = revision_positions[item.revid]
            path = wiki_path(*position)
            merged = item.revid in placement.merged_revisions
            yielding = merged or page.pageid in unaccounted_pages
            changes: dict[str, str | bytes] = {}
            if item.content is not None:
                content = item.content.encode("utf-8")
                other_page = held_by_path.get(path)
                taken = other_page is not None and other_page != page.pageid
                if taken and not yielding:
                    if path not in placeholder_paths:
                        raise WikiParseError(
                            f"revision {item.revid}: path already held by page "
                            f"{other_page}: {path}"
                        )
                    assert other_page is not None
                    released = placeholder_reason.pop(path, "placeholder")
                    gap_rows.append(
                        {
                            "revid": item.revid,
                            "logid": "",
                            "pageid": other_page,
                            "title": position[1],
                            "timestamp": item.timestamp.isoformat().replace(
                                "+00:00", "Z"
                            ),
                            "reason": (
                                f"{released}; path {path} released to page "
                                f"{page.pageid}"
                            ),
                        }
                    )
                    state_content[other_page] = None
                if taken and yielding:
                    gap_rows.append(
                        {
                            "revid": item.revid,
                            "logid": "",
                            "pageid": page.pageid,
                            "title": position[1],
                            "timestamp": item.timestamp.isoformat().replace(
                                "+00:00", "Z"
                            ),
                            "reason": (
                                f"pre-merge title unknown; path {path} held by page "
                                f"{other_page}; not projected"
                            )
                            if merged
                            else (
                                f"deleted lineage unaccounted; path {path} held by "
                                f"page {other_page}; not projected"
                            ),
                        }
                    )
                else:
                    changes[path] = content
                    state_content[page.pageid] = content
                    held_by_path[path] = page.pageid
                    if yielding:
                        placeholder_paths.add(path)
                        placeholder_reason[path] = (
                            "pre-merge title unknown"
                            if merged
                            else "deleted lineage unaccounted"
                        )
                    else:
                        placeholder_paths.discard(path)
                        placeholder_reason.pop(path, None)
            trailers = {
                "Page-Id": str(page.pageid),
                "Parent-Rev": str(item.parentid),
            }
            if merged:
                trailers["Lineage"] = "merged"
            event = Event(
                source="wiki",
                source_id=f"revid={item.revid}",
                event="created" if item.parentid == 0 else "edited",
                time_confidence="exact",
                source_time=item.timestamp,
                summary=_summary(position[1], item.revid, item.comment),
                author=author,
                changes=changes,
                trailers=trailers,
            )
            if pending_event is not None:
                yield pending_event
            pending_event = event
            continue

        assert isinstance(item, WikiLogEvent)
        if item.logid in placement.ambiguous_logids:
            continue
        if item.namespace not in NAMESPACE_DIRS:
            gap_rows.append(
                {
                    "revid": "",
                    "logid": item.logid,
                    "pageid": item.pageid,
                    "title": item.title,
                    "timestamp": item.timestamp.isoformat().replace("+00:00", "Z"),
                    "reason": (
                        f"{item.log_type}; unsupported historical namespace "
                        f"{item.namespace}"
                    ),
                }
            )
            continue
        old_path = wiki_path(item.namespace, item.title)
        if item.log_type == "move":
            assert item.target_namespace is not None and item.target_title is not None
            if item.target_namespace not in NAMESPACE_DIRS:
                raise WikiParseError(
                    f"log event {item.logid}: unsupported move target namespace "
                    f"{item.target_namespace}"
                )
            target_path = wiki_path(item.target_namespace, item.target_title)
            resolved_pageid = placement.move_owner.get(item.logid)
            if resolved_pageid is None:
                gap_rows.append(
                    {
                        "revid": "",
                        "logid": item.logid,
                        "pageid": item.pageid,
                        "title": item.title,
                        "timestamp": item.timestamp.isoformat().replace("+00:00", "Z"),
                        "reason": "move; history not API-accessible",
                    }
                )
                continue
            content = state_content[resolved_pageid]
            if content is None:
                gap_rows.append(
                    {
                        "revid": "",
                        "logid": item.logid,
                        "pageid": resolved_pageid,
                        "title": item.title,
                        "timestamp": item.timestamp.isoformat().replace("+00:00", "Z"),
                        "reason": "move; history not API-accessible",
                    }
                )
                continue
            old_holder = held_by_path.get(old_path)
            if old_holder is None:
                gap_rows.append(
                    {
                        "revid": "",
                        "logid": item.logid,
                        "pageid": resolved_pageid,
                        "title": item.title,
                        "timestamp": item.timestamp.isoformat().replace("+00:00", "Z"),
                        "reason": "move; history not API-accessible",
                    }
                )
                continue
            if old_holder != resolved_pageid:
                if old_path not in placeholder_paths:
                    raise WikiParseError(
                        f"log event {item.logid}: source path held by page {old_holder}: "
                        f"{old_path}"
                    )
                state_content[old_holder] = None
            target_holder = held_by_path.get(target_path)
            overwritten_pageid = None
            if target_holder is not None and target_holder != resolved_pageid:
                if not item.move_redir and target_path not in placeholder_paths:
                    raise WikiParseError(
                        f"log event {item.logid}: target path held by page "
                        f"{target_holder}: {target_path}"
                    )
                if item.move_redir:
                    overwritten_pageid = target_holder
                state_content[target_holder] = None
            held_by_path.pop(old_path)
            placeholder_paths.discard(old_path)
            placeholder_reason.pop(old_path, None)
            held_by_path[target_path] = resolved_pageid
            placeholder_paths.discard(target_path)
            placeholder_reason.pop(target_path, None)
            author = (
                Identity.anonymous("mw.lojban.org")
                if _anonymous(item.user)
                else Identity.namespaced("mw.lojban.org", item.user or "")
            )
            trailers = {
                "Log-Type": "move_redir" if item.move_redir else "move",
                "Moved-From": old_path,
                "Page-Id": str(resolved_pageid),
            }
            if move_times.get(item.logid) != item.timestamp:
                trailers["Ordering"] = "forced-before"
            if overwritten_pageid is not None:
                trailers["Overwritten-Page-Id"] = str(overwritten_pageid)
                overwritten = page_by_id[overwritten_pageid]
                if overwritten.revisions:
                    trailers["Overwritten-Last-Rev"] = str(
                        overwritten.revisions[-1].revid
                    )
            event = Event(
                source="wiki",
                source_id=f"logid={item.logid}",
                event="moved",
                time_confidence="exact",
                source_time=item.timestamp,
                summary=_log_summary(item.title, item.logid, item.comment),
                author=author,
                changes={target_path: content},
                deletions=(old_path,),
                trailers=trailers,
            )
            if pending_event is not None:
                yield pending_event
            pending_event = event
            continue

        resolved_pageid = held_by_path.get(old_path)
        if resolved_pageid is None:
            gap_rows.append(
                {
                    "revid": "",
                    "logid": item.logid,
                    "pageid": item.pageid,
                    "title": item.title,
                    "timestamp": item.timestamp.isoformat().replace("+00:00", "Z"),
                    "reason": "deleted; history not API-accessible",
                }
            )
            continue
        held_by_path.pop(old_path)
        placeholder_paths.discard(old_path)
        placeholder_reason.pop(old_path, None)
        state_content[resolved_pageid] = None
        author = (
            Identity.anonymous("mw.lojban.org")
            if _anonymous(item.user)
            else Identity.namespaced("mw.lojban.org", item.user or "")
        )
        event = Event(
            source="wiki",
            source_id=f"logid={item.logid}",
            event="deleted",
            time_confidence="exact",
            source_time=item.timestamp,
            summary=_log_summary(item.title, item.logid, item.comment),
            author=author,
            changes={},
            deletions=(old_path,),
            trailers={
                "Log-Type": "delete",
                "Page-Id": str(resolved_pageid),
            },
        )
        if pending_event is not None:
            yield pending_event
        pending_event = event

    if pending_event is not None:
        final_changes = dict(pending_event.changes)
        final_changes["_meta/wiki/pages.csv"] = _csv(PAGE_COLUMNS, page_rows)
        final_changes["_meta/wiki/revisions.csv"] = _csv(
            REVISION_COLUMNS, revision_rows
        )
        final_changes["_meta/wiki/media.csv"] = _csv(MEDIA_COLUMNS, media_rows)
        if error_rows:
            final_changes["_meta/wiki/errors.csv"] = _csv(ERROR_COLUMNS, error_rows)
        if gap_rows:
            final_changes["_meta/wiki/gaps.csv"] = _csv(GAP_COLUMNS, gap_rows)
        if additive:
            final_changes["_meta/wiki/coverage.toml"] = _coverage_toml(additive)
        pending_event = replace(pending_event, changes=final_changes)
        yield pending_event
