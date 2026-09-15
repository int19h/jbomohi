from __future__ import annotations

import pytest
from jbomohi_tools.project.rcs import RcsParseError, parse

FIXTURE = b"""head 1.2;
access;
symbols;
locks; strict;
comment @# @;

1.2
date 2020.01.02.03.04.05; author tester; state Exp;
branches;
next 1.1;

1.1
date 2020.01.01.03.04.05; author tester; state Exp;
branches;
next ;

desc
@description@

1.2
log
@second@@log@
text
@a
B
c
@

1.1
log
@first@
text
@d2 1
a2 1
b
@
"""


def test_parse_rcs_reconstructs_reverse_deltas_and_at_escapes() -> None:
    revisions = parse(FIXTURE)
    assert [item.revision for item in revisions] == ["1.1", "1.2"]
    assert [item.content for item in revisions] == [b"a\nb\nc\n", b"a\nB\nc\n"]
    assert revisions[1].log == "second@log"
    assert revisions[0].author == "tester"
    assert revisions[0].timestamp.isoformat() == "2020-01-01T03:04:05+00:00"


@pytest.mark.parametrize(
    ("payload", "message"),
    (
        (FIXTURE.replace(b"next 1.1;", b"next 1.3;"), "missing revision"),
        (FIXTURE.replace(b"d2 1", b"d9 1"), "deletes outside"),
        (FIXTURE[:-2], "unterminated"),
        (FIXTURE.replace(b"date 2020.01.01", b"date bad"), "unexpected RCS deltatext"),
    ),
)
def test_parse_rcs_rejects_invalid_archives(payload: bytes, message: str) -> None:
    with pytest.raises(RcsParseError, match=message):
        parse(payload)
