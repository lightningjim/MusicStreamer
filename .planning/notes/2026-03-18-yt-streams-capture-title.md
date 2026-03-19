---
date: "2026-03-18 00:00"
promoted: false
---

For YT streams, capture title from yt-dlp --get-title at resolve time and pass through on_title callback immediately — so Now Playing shows the stream title from playback start (GStreamer TAG messages won't fire for YT)
