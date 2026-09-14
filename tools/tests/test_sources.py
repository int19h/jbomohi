from __future__ import annotations

from pathlib import Path

import pytest
from jbomohi_tools.config import Config
from jbomohi_tools.sources import (
    SourceWiringError,
    mediawiki_pages_from_corpus,
    source_factories,
)


def test_mediawiki_pages_from_corpus_supplies_tiki_mapping_input(
    tmp_path: Path,
) -> None:
    corpus = tmp_path / "corpus"
    page = corpus / "wiki/main/New.wiki"
    page.parent.mkdir(parents=True)
    page.write_text("{{BPFK Section from tiki|Old|1}}\n")
    index = corpus / "_meta/wiki/pages.csv"
    index.parent.mkdir(parents=True)
    index.write_text("title,path\nNew,wiki/main/New.wiki\n")
    assert mediawiki_pages_from_corpus(corpus) == {
        "New": "{{BPFK Section from tiki|Old|1}}\n"
    }


def test_source_factories_rejects_unmerged_source(tmp_path: Path) -> None:
    config = Config(tmp_path, tmp_path / "corpus", tmp_path / "archive")
    with pytest.raises(SourceWiringError, match="not merged: wiki"):
        source_factories(config, ("wiki",))
    assert set(source_factories(config, ("irc",))) == {"irc"}
