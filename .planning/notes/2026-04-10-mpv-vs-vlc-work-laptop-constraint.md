# Constraint: mpv vs VLC on work laptop

**Date:** 2026-04-10
**Related:** v2.0 Phase 35 (mpv-drop spike), PKG-05

Work laptop may not permit installing `mpv.exe` (IT restrictions uncertain), but **VLC is already installed** on it.

**Implication for Phase 35 spike:**
- If GStreamer can handle yt-dlp library-resolved URLs → mpv goes away entirely, no constraint issue.
- If GStreamer can't → reconsider the "keep mpv, bundle mpv.exe" fallback. Options:
  1. Depend on a system-installed VLC via `python-vlc` (no bundling, but requires VLC preinstalled — acceptable on work laptop, blocker elsewhere)
  2. Bundle mpv.exe anyway and hope IT allows user-local binaries
  3. Bundle libvlc DLLs + plugin tree alongside the app (large, same bundling pain as libmpv)

**Preferred outcome:** spike succeeds, mpv disappears, question becomes moot.

**If spike fails:** revisit this note — the work-laptop constraint probably tips the decision toward python-vlc-with-system-VLC over bundled mpv.
