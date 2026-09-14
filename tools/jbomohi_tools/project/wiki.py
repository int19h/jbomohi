"""Pure MediaWiki revision parsing and projection."""

from __future__ import annotations

import csv
import hashlib
import io
import ipaddress
import json
import re
import unicodedata
from collections import defaultdict
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

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
GAP_COLUMNS = ("revid", "pageid", "reason")


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
    user_hidden: bool = False
    comment_hidden: bool = False


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
    content: str | None = None
    if not text_hidden:
        if not isinstance(slots, dict) or not isinstance(slots.get("main"), dict):
            raise WikiParseError(f"revision {revid}: main content slot is missing")
        content_value = slots["main"].get("content")
        if not isinstance(content_value, str):
            raise WikiParseError(f"revision {revid}: main content is missing")
        content = content_value
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
        user_hidden=user_hidden,
        comment_hidden=comment_hidden,
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
    if user is None:
        return True
    try:
        ipaddress.ip_address(user)
    except ValueError:
        return False
    return True


def _summary(title: str, revid: int, comment: str) -> str:
    cleaned_comment = " ".join(comment.split())[:40]
    suffix = f" (rev {revid})"
    comment_suffix = f" {cleaned_comment}" if cleaned_comment else ""
    budget = 72 - len("wiki: ") - len(suffix) - len(comment_suffix)
    if budget < 1:
        comment_suffix = ""
        budget = 72 - len("wiki: ") - len(suffix)
    shown_title = title if len(title) <= budget else title[: max(1, budget - 1)] + "…"
    return f"{shown_title}{suffix}{comment_suffix}"


def _csv(columns: Sequence[str], rows: Iterable[dict[str, object]]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def project(fragments: Iterable[WikiPageFragment]) -> Iterator[Event]:
    """Project API- or dump-derived page fragments into identical events."""

    pages = merge_fragments(fragments)
    revision_pages = [(revision, page) for page in pages for revision in page.revisions]
    revision_pages.sort(key=lambda item: (item[0].timestamp, item[0].revid))
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
    revision_rows: list[dict[str, object]] = []
    gap_rows: list[dict[str, object]] = []
    for revision, page in revision_pages:
        anonymous = _anonymous(revision.user) or revision.user_hidden
        user = "anonymous" if anonymous else revision.user
        assert user is not None
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
        if revision.user_hidden:
            reasons.append("user suppressed")
        if revision.comment_hidden:
            reasons.append("comment suppressed")
        if reasons:
            gap_rows.append(
                {
                    "revid": revision.revid,
                    "pageid": page.pageid,
                    "reason": "; ".join(reasons),
                }
            )

    last_index = len(revision_pages) - 1
    for index, (revision, page) in enumerate(revision_pages):
        anonymous = _anonymous(revision.user) or revision.user_hidden
        author = (
            Identity.anonymous("mw.lojban.org")
            if anonymous
            else Identity.namespaced("mw.lojban.org", revision.user or "")
        )
        changes: dict[str, str | bytes] = {}
        if revision.content is not None:
            changes[page.path] = revision.content.encode("utf-8")
        if index == last_index:
            changes["_meta/wiki/pages.csv"] = _csv(PAGE_COLUMNS, page_rows)
            changes["_meta/wiki/revisions.csv"] = _csv(REVISION_COLUMNS, revision_rows)
            if gap_rows:
                changes["_meta/wiki/gaps.csv"] = _csv(GAP_COLUMNS, gap_rows)
        yield Event(
            source="wiki",
            source_id=f"revid={revision.revid}",
            event="created" if revision.parentid == 0 else "edited",
            time_confidence="exact",
            source_time=revision.timestamp,
            summary=_summary(page.title, revision.revid, revision.comment),
            author=author,
            changes=changes,
            trailers={
                "Page-Id": str(page.pageid),
                "Parent-Rev": str(revision.parentid),
            },
        )
