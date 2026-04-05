import sqlite3
import pytest
from musicstreamer.accent_utils import _is_valid_hex, build_accent_css
from musicstreamer.constants import ACCENT_COLOR_DEFAULT, ACCENT_PRESETS
from musicstreamer.repo import Repo, db_init


@pytest.fixture
def repo(tmp_path):
    con = sqlite3.connect(str(tmp_path / "test.db"))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    db_init(con)
    return Repo(con)


# --- hex validation ---

def test_valid_hex_6digit():
    assert _is_valid_hex("#3584e4") is True


def test_valid_hex_3digit():
    assert _is_valid_hex("#fff") is True


def test_valid_hex_uppercase():
    assert _is_valid_hex("#3584E4") is True


def test_invalid_hex_no_hash():
    assert _is_valid_hex("3584e4") is False


def test_invalid_hex_bad_chars():
    assert _is_valid_hex("#gggggg") is False


def test_invalid_hex_empty():
    assert _is_valid_hex("") is False


def test_invalid_hex_too_short():
    assert _is_valid_hex("#ff") is False


def test_invalid_hex_too_long():
    assert _is_valid_hex("#1234567") is False


# --- CSS builder ---

def test_css_string_format():
    css = build_accent_css("#3584e4")
    assert "button.suggested-action" in css
    assert "background-color: #3584e4" in css
    assert "scale trough highlight" in css


def test_css_string_format_other():
    css = build_accent_css("#e62d42")
    assert "background-color: #e62d42" in css


# --- settings roundtrip ---

def test_settings_roundtrip(repo):
    repo.set_setting("accent_color", "#e62d42")
    assert repo.get_setting("accent_color", "#3584e4") == "#e62d42"


def test_settings_default(repo):
    assert repo.get_setting("accent_color", "#3584e4") == "#3584e4"


# --- presets ---

def test_presets_all_valid():
    for hex_val in ACCENT_PRESETS:
        assert _is_valid_hex(hex_val), f"Invalid hex in ACCENT_PRESETS: {hex_val!r}"


def test_default_in_presets():
    assert ACCENT_COLOR_DEFAULT in ACCENT_PRESETS
