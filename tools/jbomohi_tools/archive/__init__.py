"""Content-addressed raw archive support."""

from .cll import CllFetchError, CllFetchReport
from .cll import fetch as fetch_cll
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
    MHONARC_GAP_LISTS,
    MHONARC_LISTS,
    MaildirZipInventory,
    MailFetchError,
    MailFetchReport,
    MboxFetchReport,
    MhFetchReport,
    MhonarcFetchReport,
    NumberedFetchReport,
    extract_maildir_zip,
    fetch_jbosnu_raw,
    fetch_mail_mboxes,
    fetch_maildir_zip,
    fetch_mhonarc,
    fetch_old_lojban_list,
    inspect_maildir_zip,
    load_jbosnu_manifestations,
    load_mbox_manifestations,
    load_mhonarc_manifestations,
    load_old_lojban_manifestations,
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
from .wiki import FetchReport as WikiFetchReport
from .wiki import WikiFetchError
from .wiki import fetch as fetch_wiki

__all__ = [
    "MAILDIR_LISTS",
    "MHONARC_GAP_LISTS",
    "MHONARC_LISTS",
    "ArchiveError",
    "ArchiveManifest",
    "ArchiveObject",
    "CllFetchError",
    "CllFetchReport",
    "DictionaryFetchError",
    "DictionaryFetchReport",
    "DictionaryIngestReport",
    "IrcFetchError",
    "IrcFetchReport",
    "MailFetchError",
    "MailFetchReport",
    "MaildirZipInventory",
    "MboxFetchReport",
    "MhFetchReport",
    "MhonarcFetchReport",
    "NumberedFetchReport",
    "TikiIngestReport",
    "WikiFetchError",
    "WikiFetchReport",
    "extract_maildir_zip",
    "fetch_changes",
    "fetch_cll",
    "fetch_irc",
    "fetch_jbosnu_raw",
    "fetch_mail_mboxes",
    "fetch_maildir_zip",
    "fetch_mhonarc",
    "fetch_old_lojban_list",
    "fetch_wiki",
    "ingest_dictionary_exports",
    "ingest_tiki_export",
    "inspect_maildir_zip",
    "load_jbosnu_manifestations",
    "load_mbox_manifestations",
    "load_mhonarc_manifestations",
    "load_old_lojban_manifestations",
    "object_path",
    "store_file",
    "store_object",
    "verify_archive",
    "verify_manifests",
]
