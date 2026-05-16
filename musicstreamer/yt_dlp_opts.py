"""Single source of truth for yt-dlp js_runtimes opts (Phase 79 / BUG-11).

Provides:
  - build_js_runtimes(node_runtime: NodeRuntime | None) -> dict
      Returns the js_runtimes dict for yt_dlp.YoutubeDL constructor opts.
      When node_runtime is not None, threads node_runtime.path (which may
      itself be None) into the dict so yt-dlp receives an explicit path
      instead of performing its own PATH lookup.

Phase 79 / BUG-11 — single source of truth used by both yt-dlp call sites:
  - musicstreamer/player.py::_youtube_resolve_worker
  - musicstreamer/yt_import.py::scan_playlist

Why a module:
  Prior to Phase 79, both call sites used the inline literal
  {"node": {"path": None}}. This was the Phase 999.9 baseline that worked
  when shutil.which("node") succeeded (PATH-carrying terminal launches). When
  MusicStreamer is launched via the GNOME .desktop entry (Exec=musicstreamer),
  the systemd-session-inherited PATH does NOT include version-manager shims
  (fnm/nvm/volta/asdf). runtime_check.check_node() correctly resolves the
  absolute path via $HOME-rooted fallback (commit a06549f, 2026-04-25) — but
  the resolved path was never threaded into yt-dlp, which then fell back to
  its own PATH lookup, failed, and returned "No video formats found!".

  This module is the second half of that fix: it takes the already-resolved
  NodeRuntime.path and places it in the js_runtimes dict so yt-dlp receives
  an explicit absolute path, bypassing its own (broken-under-.desktop) lookup.

Reference: yt_dlp/utils/_jsruntime.py::_determine_runtime_path (yt-dlp 2026.03.17)
"""
from __future__ import annotations

from musicstreamer.runtime_check import NodeRuntime


def build_js_runtimes(node_runtime: NodeRuntime | None) -> dict:
    """Return js_runtimes opts dict for yt_dlp.YoutubeDL.

    Args:
        node_runtime: The result of runtime_check.check_node(), or None when
            not available. When None, returns {"node": {"path": None}} which
            preserves yt-dlp's own PATH-lookup fallback (D-02: some YouTube
            streams resolve without invoking the JS runtime at all — live HLS
            manifests, unauthenticated paths — so short-circuiting on None
            would regress those cases).

    Returns:
        dict of the form {"node": {"path": <abs_path_or_None>}}. When
        node_runtime is not None, node_runtime.path is threaded through
        regardless of node_runtime.available (only .path is read, per D-02).
    """
    path = node_runtime.path if node_runtime is not None else None
    return {"node": {"path": path}}
