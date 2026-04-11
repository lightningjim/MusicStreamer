from musicstreamer.url_helpers import _is_aa_url, _aa_channel_key_from_url


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

def test_channel_key_strips_quality_suffix():
    # DI.fm/RadioTunes stream URLs append _hi quality tier — must be stripped
    assert _aa_channel_key_from_url("http://prem2.di.fm:80/ambient_hi?listen_key=abc", "di") == "ambient"

def test_channel_key_strips_med_suffix():
    assert _aa_channel_key_from_url("http://prem2.di.fm:80/trance_med?listen_key=abc", "di") == "trance"

def test_channel_key_strips_low_suffix():
    assert _aa_channel_key_from_url("http://prem2.di.fm:80/house_low", "di") == "house"

def test_channel_key_strips_zenradio_prefix():
    # ZenRadio stream URLs use 'zr' prefix — must be stripped to match API key
    assert _aa_channel_key_from_url("http://prem1.zenradio.com:80/zrambient", "zenradio") == "ambient"

def test_channel_key_no_transform_needed():
    # JazzRadio/RockRadio/ClassicalRadio use bare keys matching the API directly
    assert _aa_channel_key_from_url("http://prem1.jazzradio.com:80/afrojazz", "jazzradio") == "afrojazz"

def test_channel_key_extraction_no_path():
    assert _aa_channel_key_from_url("http://di.fm") is None

def test_channel_key_extraction_empty():
    assert _aa_channel_key_from_url("") is None

# test_fetch_aa_logo_success / _failure removed in Phase 36 plan 02.
# fetch_aa_logo() used GLib.idle_add and is deleted with musicstreamer/ui/edit_dialog.py
# in plan 36-03. A Qt-signal-based replacement will be added in Phase 39 when
# EditStationDialog is rebuilt in PySide6.
