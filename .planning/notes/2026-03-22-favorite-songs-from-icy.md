---
date: "2026-03-22 00:00"
promoted: false
---

For stations with ICY metadata, add ability to favorite songs and store in DB. 

UI: star icon (leaning star over heart). Favorites should be a separate view in the bottom half (same area as station list).

DB: store the song title, stream/station it came from (for context — e.g. same song name can appear on different DI.FM vs Zen Radio streams). Also store any metadata found: GraceNote genre tags if iTunes API provides them.

Goal: be able to review favorited songs and look further into artists/songs. Storing which stream it came from is important for disambiguation (e.g. two "Ambient" stations from different providers).
