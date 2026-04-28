# External Integrations

**Analysis Date:** 2026-04-28

## APIs & External Services

**Radio Station Discovery:**
- Radio-Browser.info API (`https://all.api.radio-browser.info/json`)
  - Client: `musicstreamer.radio_browser` (pure urllib, no SDK)
  - Functions: `search_stations()`, `fetch_tags()`, `fetch_countries()`
  - Uses: Station search by name/tag, genre/tag discovery, country filtering
  - No authentication required
  - Network timeout: 10s per call

**YouTube/Livestream Resolution:**
- YouTube (via yt-dlp library API)
  - SDK/Client: `yt-dlp` (direct library, no subprocess)
  - Auth: Cookie-based authentication via `cookiefile` parameter
  - Used by: `musicstreamer.player._play_youtube()`, `musicstreamer.yt_import.scan_playlist()`
  - Flow: Extracts HLS URL from YouTube playlist/channel tabs using `extract_flat` mode
  - Cookie handling: Managed via `musicstreamer.cookie_utils.temp_cookies_copy()` (Phase 999.7)
  - Corruption detection: `cookie_utils.is_cookie_file_corrupted()` checks for yt-dlp marker header

**Twitch Stream Resolution:**
- Twitch (via streamlink)
  - SDK/Client: `streamlink>=8.3`
  - Auth: `auth-token` cookie (harvested via OAuth, stored at `paths.twitch_token_path()`)
  - Used by: `musicstreamer.player._play_twitch()` (uses streamlink.session.Streamlink API)
  - Flow: Cookie passed to streamlink for private GQL endpoint access; resolves HLS URL
  - Error handling: Catches `NoPluginError` (channel not found), `PluginError` (playback errors)
  - Note: Piggyback OAuth not feasible due to Twitch server-side redirect_uri restrictions (Phase 999.3)

## Data Storage

**Databases:**
- SQLite 3 (local filesystem)
  - Connection: `musicstreamer.repo.db_connect()` via sqlite3 module
  - Path: `platforms.db_path()` → `~/.local/share/musicstreamer/musicstreamer.sqlite3`
  - Client: Python's built-in sqlite3 module; `Row` factory for dict-like access
  - Initialization: `db_init()` creates schema and applies migrations
  - Schema includes:
    - `providers` - Station provider metadata
    - `stations` - Station definitions with provider FK, tags, art paths
    - `station_streams` - Multiple playback URLs per station (quality variants, failover)
    - `favorites` - User-saved track recordings (station + track title unique constraint)
    - `settings` - Key-value store for app configuration
  - Migrations: Incremental ALTER TABLE for backwards compatibility

**File Storage:**
- Local filesystem only
  - Station art: `~/.local/share/musicstreamer/assets/` (relative paths in DB)
  - Album fallback art: Same directory
  - Cookies: `~/.local/share/musicstreamer/cookies.txt` (yt-dlp format after Phase 999.7)
  - Twitch auth token: `~/.local/share/musicstreamer/twitch-token.txt`
  - OAuth diagnostics: `~/.local/share/musicstreamer/oauth.log` (Phase 999.3 D-10)
  - Accent CSS: `~/.local/share/musicstreamer/accent.css` (custom theme colors)
  - AutoEQ profiles: `~/.local/share/musicstreamer/eq-profiles/` (imported equalizer presets, Phase 47.2)

**Caching:**
- GStreamer internal buffering (no explicit cache beyond pipeline)
  - Buffer config: `BUFFER_SIZE_BYTES` and `BUFFER_DURATION_S` constants in `musicstreamer.player`
  - URL cache: yt-dlp caches format lookups in-process (no persistent cache)
- Album art cache: `musicstreamer.media_keys._art_cache.write_cover_png()` writes to temp for MPRIS2

## Authentication & Identity

**Twitch OAuth:**
- Implementation: Subprocess-isolated QWebEngineView in `musicstreamer.oauth_helper`
  - Entry point: `python -m musicstreamer.oauth_helper --mode twitch`
  - Harvests `auth-token` cookie from twitch.tv login page
  - User-Agent spoofing: Chrome UA set via `QTWEBENGINE_CHROMIUM_FLAGS` (Phase 999.3 workaround for Twitch browser detection)
  - Timeout: 120s login deadline; exits on window close or timeout
  - Output: Token printed to stdout (captured by parent process)
  - Diagnostics: Structured JSON events on stderr (ts, category, detail)
  - Signature: Cookie domain validation in `_cookie_domain_matches()` to prevent lookalikes

**YouTube OAuth:**
- Implementation: Subprocess-isolated QWebEngineView in `musicstreamer.oauth_helper`
  - Entry point: `python -m musicstreamer.oauth_helper --mode google`
  - Uses Qt WebEngine cookie store for Google authentication (deferred implementation, not yet active)
  - Separate from Twitch flow; decoupled process communication

**Stored Tokens:**
- Twitch: `~/.local/share/musicstreamer/twitch-token.txt` (auth-token cookie value)
- YouTube: `~/.local/share/musicstreamer/cookies.txt` (yt-dlp format; managed by yt-dlp)
- No centralized OAuth token store; each provider uses its own file

## Monitoring & Observability

**Error Tracking:**
- None (no external error reporting; local logging only)

**Logs:**
- Standard Python logging to stderr/file
  - Entry point: `musicstreamer.__main__.logging.basicConfig(level=logging.WARNING)`
  - GStreamer bus errors logged via `Player.playback_error` signal
  - OAuth diagnostics: JSON-line format to `oauth.log` (Phase 999.3 D-10)
  - Structured logging: `_emit_event()` in oauth_helper for OAuth events

## CI/CD & Deployment

**Hosting:**
- Desktop application; no server deployment
- Packaged for Windows (PyInstaller + Inno Setup installer) and Linux (direct pip install)

**CI Pipeline:**
- None detected (local development only at time of analysis)
- Test execution: `pytest` or `pytest-qt` (headless via conftest.py `offscreen` platform)
- Packaging: Manual PowerShell script (`build.ps1`) for Windows; no CI automation visible

**Installer/Packaging:**
- Windows: Inno Setup (`.iss` files in `packaging/windows/`)
  - Bundles PyInstaller dist/ output
  - Sets AppUserModelID for Windows taskbar/SMTC identity
  - Registers Start Menu shortcut with AUMID for friendly display name
- Linux: Direct pip/setuptools install (deferred Flatpak/AppImage to future phases)

## Environment Configuration

**Required env vars:**
- None mandatory for runtime (all paths use platformdirs defaults)
- Optional:
  - `QT_QPA_PLATFORM=offscreen` - Forces headless Qt (used in tests)
  - `QTWEBENGINE_CHROMIUM_FLAGS` - Sets Chrome UA for oauth_helper

**Secrets location:**
- Twitch token: `~/.local/share/musicstreamer/twitch-token.txt` (plain text, single line)
- Cookies: `~/.local/share/musicstreamer/cookies.txt` (Netscape format, yt-dlp generated)
- NOTE: Both stored unencrypted on disk (platform's user data dir); suitable for personal desktop app

## Webhooks & Callbacks

**Incoming:**
- None (desktop app; no server-side webhooks)

**Outgoing:**
- None (read-only API integration with Radio-Browser, YouTube, Twitch)

**Signal-based Callbacks (Internal):**
- GStreamer bus signals → Qt signals via `GstBusLoopThread` (cross-thread marshaling)
- Player signals: `title_changed`, `failover`, `offline`, `playback_error`, `buffer_percent`, `elapsed_updated`
- UI dialogs: Progress callbacks for import (`toast_callback` in `yt_import.scan_playlist()`)

## Cross-Platform Considerations

**Linux:**
- GStreamer and PyGObject bundled via system packages (apt)
- D-Bus integration via `PySide6.QtDBus` for MPRIS2 media controls
- XDG Base Directory paths via platformdirs
- Optional: PySide6.QtWebEngineWidgets (separate apt package for oauth_helper)

**Windows:**
- GStreamer and all dependencies bundled via PyInstaller
- WinRT APIs (SMTC) via winrt packages v3.2.x (platform media transport controls)
- All paths resolved via platformdirs (AppData roaming/local dirs)
- VC++ redistributable required for GStreamer runtime

**Common:**
- platformdirs handles all OS-specific path resolution
- QTimer and QThread abstractions hide OS threading differences
- Qt palette/color scheme automatically adapts to OS dark/light mode (explicit Fusion style on Windows)

---

*Integration audit: 2026-04-28*
