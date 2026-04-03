import os
import tempfile
from unittest.mock import MagicMock, patch

from musicstreamer.ui.edit_dialog import _is_aa_url, _aa_channel_key_from_url


def test_is_aa_url_di():
    assert _is_aa_url("http://prem2.di.fm:80/di_house?listen_key=abc") is True

def test_is_aa_url_radiotunes():
    assert _is_aa_url("http://prem1.radiotunes.com:80/ambient?listen_key=x") is True

def test_is_aa_url_jazzradio():
    assert _is_aa_url("http://prem1.jazzradio.com:80/jazz?listen_key=x") is True

def test_is_aa_url_rockradio():
    assert _is_aa_url("http://prem1.rockradio.com:80/rock?listen_key=x") is True

def test_is_aa_url_classicalradio():
    assert _is_aa_url("http://prem1.classicalradio.com:80/classical?listen_key=x") is True

def test_is_aa_url_zenradio():
    assert _is_aa_url("http://prem1.zenradio.com:80/zen?listen_key=x") is True

def test_is_aa_url_false_youtube():
    assert _is_aa_url("https://www.youtube.com/watch?v=abc") is False

def test_is_aa_url_false_generic():
    assert _is_aa_url("http://example.com/stream") is False

def test_channel_key_extraction_with_query():
    # Stream URL path is 'di_house'; slug 'di' prefix is stripped -> 'house'
    assert _aa_channel_key_from_url("http://prem2.di.fm:80/di_house?listen_key=abc", "di") == "house"

def test_channel_key_extraction_no_prefix():
    # Some networks don't prefix; without slug arg key is returned as-is
    assert _aa_channel_key_from_url("http://prem1.di.fm:80/ambient") == "ambient"

def test_channel_key_extraction_no_query():
    # Bare key with no network prefix (e.g. ambient has no 'di_' prefix)
    assert _aa_channel_key_from_url("http://prem1.di.fm:80/ambient", "di") == "ambient"

def test_channel_key_extraction_no_path():
    assert _aa_channel_key_from_url("http://di.fm") is None

def test_channel_key_extraction_empty():
    assert _aa_channel_key_from_url("") is None

def test_fetch_aa_logo_success():
    """fetch_aa_logo calls callback with temp_path when API and CDN succeed."""
    from musicstreamer.ui.edit_dialog import fetch_aa_logo
    results = []
    with patch("musicstreamer.ui.edit_dialog.GLib") as mock_glib, \
         patch("musicstreamer.ui.edit_dialog._fetch_image_map", return_value={"trance": "https://cdn/img.png"}), \
         patch("musicstreamer.ui.edit_dialog.urllib.request.urlopen") as mock_urlopen:
        mock_glib.idle_add.side_effect = lambda fn, *args: results.append(args)
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=cm)
        cm.__exit__ = MagicMock(return_value=False)
        cm.read.return_value = b"\x89PNG fake image data"
        mock_urlopen.return_value = cm
        fetch_aa_logo("di", "trance", lambda path: None)
        import time; time.sleep(0.5)
    assert len(results) == 1
    assert results[0][0] is not None  # temp_path
    # Clean up temp file
    if results[0][0] and os.path.exists(results[0][0]):
        os.unlink(results[0][0])

def test_fetch_aa_logo_failure():
    """fetch_aa_logo calls callback with None when _fetch_image_map returns empty."""
    from musicstreamer.ui.edit_dialog import fetch_aa_logo
    results = []
    with patch("musicstreamer.ui.edit_dialog.GLib") as mock_glib, \
         patch("musicstreamer.ui.edit_dialog._fetch_image_map", return_value={}):
        mock_glib.idle_add.side_effect = lambda fn, *args: results.append(args)
        fetch_aa_logo("di", "nonexistent", lambda path: None)
        import time; time.sleep(0.5)
    assert len(results) == 1
    assert results[0][0] is None
