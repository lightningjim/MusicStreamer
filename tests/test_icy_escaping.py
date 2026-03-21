"""Unit tests for ICY title escaping using GLib.markup_escape_text."""
import gi
gi.require_version("GLib", "2.0")
from gi.repository import GLib


def _escape(s: str) -> str:
    return GLib.markup_escape_text(s, -1)


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
