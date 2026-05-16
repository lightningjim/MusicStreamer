"""Tests for musicstreamer.yt_dlp_opts — js_runtimes opts builder (Phase 79 / BUG-11).

Three-input matrix locks the helper's contract: None / NodeRuntime-available /
NodeRuntime-unavailable. Downstream integration tests in
tests/test_player.py / tests/test_player_node_runtime.py and
tests/test_yt_import_library.py assert the helper's output threads through to
yt_dlp.YoutubeDL opts at both call sites.
"""
from __future__ import annotations

from musicstreamer.runtime_check import NodeRuntime
from musicstreamer.yt_dlp_opts import build_js_runtimes


def test_build_js_runtimes_none_input():
    """B-79-01 / D-02: None NodeRuntime → {"node": {"path": None}}.

    Preserves yt-dlp's own PATH-lookup fallback for the absent-Node branch.
    """
    assert build_js_runtimes(None) == {"node": {"path": None}}


def test_build_js_runtimes_available_path():
    """B-79-02 / D-01 / D-04: resolved abs path threads through to yt-dlp opts.

    This is the fix for BUG-11: the .desktop-stripped PATH launch no longer
    fails JS-requiring YouTube streams because the resolved path is explicit.
    """
    nr = NodeRuntime(available=True, path="/fake/node")
    assert build_js_runtimes(nr) == {"node": {"path": "/fake/node"}}


def test_build_js_runtimes_unavailable_none_path():
    """B-79-03 / D-02: genuinely-absent Node case → {"node": {"path": None}}.

    NodeRuntime.available is NOT consulted — only .path is read. Preserves
    yt-dlp's own PATH-lookup fallback (may still resolve JS-free streams).
    """
    nr = NodeRuntime(available=False, path=None)
    assert build_js_runtimes(nr) == {"node": {"path": None}}
