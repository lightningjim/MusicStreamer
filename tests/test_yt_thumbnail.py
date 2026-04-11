"""Tests for the YouTube URL detection helper.

Phase 36 plan 02 moved _is_youtube_url from musicstreamer/ui/edit_dialog.py to
musicstreamer/url_helpers.py. The three test_fetch_yt_thumbnail_* tests that
previously lived here were deleted — fetch_yt_thumbnail used subprocess.run(['yt-dlp', ...])
which is a Phase 35 PORT-09 bleed, and it will be re-implemented in Phase 37 using the
yt_dlp.YoutubeDL library API plus Qt signals instead of GLib.idle_add. The new
implementation will get its own tests at that time.
"""
from musicstreamer.url_helpers import _is_youtube_url


def test_is_youtube_url():
    assert _is_youtube_url("https://www.youtube.com/watch?v=abc")
    assert _is_youtube_url("https://youtu.be/abc")
    assert not _is_youtube_url("https://radio.example.com")
