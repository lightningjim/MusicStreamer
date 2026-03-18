# External Integrations

**Analysis Date:** 2026-03-18

## APIs & External Services

**Media Extraction:**
- YouTube (youtube.com, youtu.be URLs)
  - SDK/Client: `yt-dlp` package
  - Auth: None (public streams)
  - Purpose: Extract playable stream URLs from YouTube videos and livestreams
  - Implementation: `main.py` lines 418-435, uses HLS format preference (`m3u8`)

**Streaming Services:**
- Generic HTTP/HLS streams
  - Protocol: HTTP/HTTPS URLs with m3u8 playlist support
  - Auth: None (public streams assumed)
  - Example: Chillhop (`https://streams.chillhop.com/live?type=.mp3`)

## Data Storage

**Databases:**
- SQLite3 (`sqlite3` module)
  - Location: `~/.local/share/musicstreamer/musicstreamer.sqlite3`
  - Client: Built-in Python `sqlite3` module
  - Connection: Direct filesystem access via `db_connect()` in `main.py` (lines 32-36)
  - Schema: Two tables - `providers` and `stations` (lines 42-58)
  - Foreign key constraints enabled via PRAGMA

**File Storage:**
- Local filesystem only
  - Asset storage: `~/.local/share/musicstreamer/assets/`
  - Station art: Per-station subdirectories under assets
  - Album fallback art: Same storage structure
  - Implementation: `copy_asset_for_station()` in `main.py` (lines 182-197)

**Caching:**
- yt-dlp: Cache disabled (`"cachedir": False` in line 425)
- No application-level caching configured

## Authentication & Identity

**Auth Provider:**
- None - application uses local user filesystem
- No API keys or OAuth tokens required
- Anonymous access to public streaming URLs

## Monitoring & Observability

**Error Tracking:**
- None detected

**Logs:**
- Console output only (`print()` statements)
- yt-dlp errors logged to stderr in `main.py` line 434
- No persistent logging framework

## CI/CD & Deployment

**Hosting:**
- Desktop application (runs locally on user's machine)
- No server/cloud deployment

**CI Pipeline:**
- None detected

**Distribution:**
- Direct Python script execution
- .desktop file present for GNOME integration (`org.example.Streamer.desktop`)

## Environment Configuration

**Required env vars:**
- None explicitly required
- Uses XDG Base Directory spec: `~/.local/share/` and `~/.local/config/`

**Secrets location:**
- No secrets management (public APIs only)
- No .env files or credential storage

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

## URL Patterns

**Stream URL Requirements:**
- Direct HTTP/HTTPS URLs (any format)
- YouTube URLs (youtube.com, youtu.be)
- HLS m3u8 streams (livestreams)

**Supported Formats:**
- YouTube videos and livestreams
- HTTP progressive download streams
- HLS playlists (m3u8)
- Audio streams (MP3, AAC, etc.)

## GStreamer Audio Backend

**Output Sink:**
- Primary: `pulsesink` (PulseAudio/PipeWire compatible)
- Fallback: Auto-detection if pulsesink unavailable
- Video sink: `fakesink` (suppresses video output for audio-only streams)

**Stream Resolution:**
- Uses GStreamer `playbin` element for automatic codec selection
- Supports mixed muxed formats (audio+video in single stream)

---

*Integration audit: 2026-03-18*
