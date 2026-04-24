"""Tests for musicstreamer.oauth_log — rotating OAuth diagnostic log.

Phase 999.3 D-10/D-11. Verifies:
- 0o600 permissions after first write (T-40-03 parity).
- JSON-line format with fixed schema.
- Scrub rules: URLs, access_token, state=/code=/token= prefixes, >200 chars.
- RotatingFileHandler with maxBytes=64KB, backupCount=2.
- No backup 3 ever created.
"""
from __future__ import annotations

import json
import os

import pytest

from musicstreamer.oauth_log import OAuthLogger, _scrub


# ---------------------------------------------------------------------------
# File creation + permissions
# ---------------------------------------------------------------------------


def test_log_event_creates_file_with_0o600(tmp_path):
    """First log_event creates oauth.log with 0o600 permissions."""
    log_path = str(tmp_path / "oauth.log")
    logger = OAuthLogger(log_path)
    logger.log_event(
        {"ts": 1.0, "category": "Success", "detail": "", "provider": "twitch"}
    )
    assert os.path.exists(log_path)
    perms = os.stat(log_path).st_mode & 0o777
    assert perms == 0o600, f"expected 0o600, got {oct(perms)}"


def test_log_event_writes_json_line(tmp_path):
    """Each log_event writes exactly one JSON line with fixed schema."""
    log_path = str(tmp_path / "oauth.log")
    logger = OAuthLogger(log_path)
    logger.log_event(
        {"ts": 1.5, "category": "LoginTimeout", "detail": "120s", "provider": "twitch"}
    )
    with open(log_path) as fh:
        lines = fh.readlines()
    assert len(lines) == 1
    obj = json.loads(lines[0])
    assert set(obj.keys()) == {"ts", "category", "detail", "provider"}
    assert obj["category"] == "LoginTimeout"
    assert obj["detail"] == "120s"
    assert obj["provider"] == "twitch"
    assert isinstance(obj["ts"], float)


# ---------------------------------------------------------------------------
# Scrub rules (T-999.3-03)
# ---------------------------------------------------------------------------


def test_log_scrubs_url_in_detail(tmp_path):
    """detail containing '://' is replaced with '<scrubbed>'."""
    log_path = str(tmp_path / "oauth.log")
    logger = OAuthLogger(log_path)
    logger.log_event(
        {
            "ts": 1.0,
            "category": "TwitchRejectedRequest",
            "detail": "https://id.twitch.tv/oauth2/token?access_token=abc",
            "provider": "twitch",
        }
    )
    with open(log_path) as fh:
        obj = json.loads(fh.readline())
    assert obj["detail"] == "<scrubbed>"


def test_log_scrubs_access_token_substring(tmp_path):
    """detail containing 'access_token' is scrubbed."""
    log_path = str(tmp_path / "oauth.log")
    logger = OAuthLogger(log_path)
    logger.log_event(
        {
            "ts": 1.0,
            "category": "InvalidTokenResponse",
            "detail": "access_token=xyz",
            "provider": "twitch",
        }
    )
    with open(log_path) as fh:
        obj = json.loads(fh.readline())
    assert obj["detail"] == "<scrubbed>"


def test_log_scrubs_state_prefix(tmp_path):
    """detail starting with 'state=' is scrubbed."""
    log_path = str(tmp_path / "oauth.log")
    logger = OAuthLogger(log_path)
    logger.log_event(
        {
            "ts": 1.0,
            "category": "InvalidTokenResponse",
            "detail": "state=abc123",
            "provider": "twitch",
        }
    )
    with open(log_path) as fh:
        obj = json.loads(fh.readline())
    assert obj["detail"] == "<scrubbed>"


def test_log_scrubs_code_prefix(tmp_path):
    log_path = str(tmp_path / "oauth.log")
    logger = OAuthLogger(log_path)
    logger.log_event(
        {"ts": 1.0, "category": "X", "detail": "code=deadbeef", "provider": "twitch"}
    )
    with open(log_path) as fh:
        obj = json.loads(fh.readline())
    assert obj["detail"] == "<scrubbed>"


def test_log_scrubs_token_prefix(tmp_path):
    log_path = str(tmp_path / "oauth.log")
    logger = OAuthLogger(log_path)
    logger.log_event(
        {"ts": 1.0, "category": "X", "detail": "token=deadbeef", "provider": "twitch"}
    )
    with open(log_path) as fh:
        obj = json.loads(fh.readline())
    assert obj["detail"] == "<scrubbed>"


def test_log_scrubs_oversize_detail(tmp_path):
    """detail longer than 200 chars is scrubbed."""
    log_path = str(tmp_path / "oauth.log")
    logger = OAuthLogger(log_path)
    logger.log_event(
        {
            "ts": 1.0,
            "category": "SubprocessCrash",
            "detail": "x" * 250,
            "provider": "twitch",
        }
    )
    with open(log_path) as fh:
        obj = json.loads(fh.readline())
    assert obj["detail"] == "<scrubbed>"


def test_log_passes_short_category_detail(tmp_path):
    """Short benign detail (no URL, no banned prefix) is NOT scrubbed."""
    log_path = str(tmp_path / "oauth.log")
    logger = OAuthLogger(log_path)
    logger.log_event(
        {
            "ts": 1.0,
            "category": "TwitchRejectedRequest",
            "detail": "access_denied",
            "provider": "twitch",
        }
    )
    with open(log_path) as fh:
        obj = json.loads(fh.readline())
    assert obj["detail"] == "access_denied"


def test_scrub_helper_rejects_non_string():
    """_scrub returns '<scrubbed>' for non-str input (defensive)."""
    assert _scrub(None) == "<scrubbed>"  # type: ignore[arg-type]
    assert _scrub(123) == "<scrubbed>"  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Rotation (D-10)
# ---------------------------------------------------------------------------


def test_log_rotation_at_64kb(tmp_path):
    """After enough writes to exceed 64KB, oauth.log.1 exists."""
    log_path = str(tmp_path / "oauth.log")
    logger = OAuthLogger(log_path)
    # Each event JSON is ~200 bytes incl. newline. Write 500 → ~100KB → rotates.
    payload = "a" * 150  # scrub-safe (no banned tokens, < 200 chars)
    for i in range(500):
        logger.log_event(
            {"ts": float(i), "category": "X", "detail": payload, "provider": "twitch"}
        )
    assert os.path.exists(log_path + ".1"), "rotation should have produced oauth.log.1"
    # Active log file should be < 2 * maxBytes
    assert os.path.getsize(log_path) < 128 * 1024


def test_log_never_creates_backup_3(tmp_path):
    """backupCount=2 means oauth.log.3 never exists."""
    log_path = str(tmp_path / "oauth.log")
    logger = OAuthLogger(log_path)
    payload = "a" * 150
    # Write ~400KB — forces multiple rotations.
    for i in range(2000):
        logger.log_event(
            {"ts": float(i), "category": "X", "detail": payload, "provider": "twitch"}
        )
    assert not os.path.exists(log_path + ".3"), "backupCount=2 must cap at .2"


# ---------------------------------------------------------------------------
# Validation tolerance
# ---------------------------------------------------------------------------


def test_log_accepts_unknown_category(tmp_path):
    """Logger does not validate category — parent is authoritative."""
    log_path = str(tmp_path / "oauth.log")
    logger = OAuthLogger(log_path)
    logger.log_event(
        {"ts": 1.0, "category": "BrandNewCategory", "detail": "", "provider": "twitch"}
    )
    with open(log_path) as fh:
        obj = json.loads(fh.readline())
    assert obj["category"] == "BrandNewCategory"
