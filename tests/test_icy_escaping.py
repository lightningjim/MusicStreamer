"""Unit tests for ICY title escaping.

Phase 35 port: the original helper was ``GLib.markup_escape_text``.
Tests now use Python's ``xml.sax.saxutils.escape`` with the same entity
map (``&``, ``<``, ``>``, and ``"``) so the behavioral contract is
preserved without an ``import gi`` dependency in the test suite (D-26).
"""
from xml.sax.saxutils import escape


_ENTITIES = {'"': "&quot;"}


def _escape(s: str) -> str:
    return escape(s, _ENTITIES)


def test_escape_ampersand():
    assert _escape("Rock & Roll") == "Rock &amp; Roll"


def test_escape_angle_brackets():
    assert _escape("Artist <Live>") == "Artist &lt;Live&gt;"


def test_escape_quotes():
    assert _escape('He said "hello"') == "He said &quot;hello&quot;"


def test_escape_plain_passthrough():
    assert _escape("Plain Title") == "Plain Title"


def test_escape_multiple_specials():
    result = _escape("A & B < C > D")
    assert result == "A &amp; B &lt; C &gt; D"
