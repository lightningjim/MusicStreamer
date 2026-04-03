---
date: "2026-04-03 16:30"
promoted: false
---

Extend station art fetching beyond YouTube thumbnails: (1) AudioAddict import — fetch channel image from AA API at import time and store as station_art_path; (2) URL import — detect when imported station is a radio stream (not YouTube) and attempt to fetch art (ICY metadata, favicon, or provider logo). Both tie into the same image pipeline. Relates to phase 15 AudioAddict import.
