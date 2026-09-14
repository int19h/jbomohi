"""Content-addressed raw archive support."""

from .dictionary import (
    DictionaryFetchError,
    DictionaryFetchReport,
    DictionaryIngestReport,
    fetch_changes,
    ingest_dictionary_exports,
)
from .irc import FetchReport as IrcFetchReport
from .irc import IrcFetchError
from .irc import fetch as fetch_irc
from .mail import (
    MAILDIR_LISTS,
    MaildirZipInventory,
    MailFetchError,
    MailFetchReport,
    extract_maildir_zip,
    fetch_maildir_zip,
    inspect_maildir_zip,
)
from .manifest import (
    ArchiveError,
    ArchiveManifest,
    ArchiveObject,
    object_path,
    store_file,
    store_object,
    verify_archive,
    verify_manifests,
)
from .tiki import TikiIngestReport, ingest_tiki_export

__all__ = [
    "MAILDIR_LISTS",
    "ArchiveError",
    "ArchiveManifest",
    "ArchiveObject",
    "DictionaryFetchError",
    "DictionaryFetchReport",
    "DictionaryIngestReport",
    "IrcFetchError",
    "IrcFetchReport",
    "MailFetchError",
    "MailFetchReport",
    "MaildirZipInventory",
    "TikiIngestReport",
    "extract_maildir_zip",
    "fetch_changes",
    "fetch_irc",
    "fetch_maildir_zip",
    "ingest_dictionary_exports",
    "ingest_tiki_export",
    "inspect_maildir_zip",
    "object_path",
    "store_file",
    "store_object",
    "verify_archive",
    "verify_manifests",
]
