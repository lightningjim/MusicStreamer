# Technology Stack

**Analysis Date:** 2026-04-28

## Languages

**Primary:**
- Python 3.10+ - Core application language; supports desktop app, media backends, and utilities

**Secondary:**
- PowerShell - Windows installer and packaging scripts (Phase 44+)
- Inno Setup Script - Windows executable installer configuration (`packaging/windows/`)

## Runtime

**Environment:**
- CPython 3.10+ (development and standalone bundles)
- GStreamer 1.0 (system library; provides media playback pipeline)
- Node.js (required on PATH for yt-dlp n-challenge solver during YouTube playback)

**Package Manager:**
- pip (via setuptools)
- Lockfile: `pyproject.toml` (declarative, no separate lock file)

## Frameworks

**Core UI:**
- PySide6 (Qt 6) v6.11+ - Desktop GUI framework for desktop music streaming app
  - `PySide6.QtWidgets` - Main window, dialogs, widgets (accounts, discovery, settings, EQ)
  - `PySide6.QtCore` - Event loop, signals/slots, threading (QThread, QTimer)
  - `PySide6.QtGui` - Palette, icons, pixmaps (dark mode support)
  - `PySide6.QtWebEngineWidgets` - OAuth authentication UI (separate apt package on Linux)
  - `PySide6.QtDBus` - Linux MPRIS2 media-session integration (D-Bus)
  - `PySide6.QtNetwork` - Cookie handling for OAuth

**Media Playback:**
- GStreamer 1.0 (via PyGObject) - Audio/video pipeline, playback state, buffering
  - Initialized via `gi.require_version("Gst", "1.0")`
  - Used in `musicstreamer.player.Player` for stream decoding and playback control
  - Module-level `_BUS_BRIDGE` singleton spawns `GstBusLoopThread` daemon for signal dispatch

**Stream Resolution:**
- yt-dlp - YouTube/livestream URL extraction and format selection (Plan 35-06)
  - Direct library API (not subprocess) in `musicstreamer.player._play_youtube()`
  - Cookiefile support for authenticated YouTube access
  - HLS format preference for resolved YouTube URLs
- streamlink v8.3+ - Twitch stream resolution via private GQL endpoint
  - Requires `auth-token` cookie from Twitch login (stored in `twitch-token.txt`)
  - OAuth helper subprocess handles Twitch cookie harvest (Phase 999.3)

**Testing:**
- pytest v9+ - Test runner
- pytest-qt v4+ - Qt integration for GUI tests
  - Qt platform plugin set to `offscreen` in `tests/conftest.py` for headless CI

## Key Dependencies

**Critical:**
- `yt-dlp` - YouTube/livestream format extraction; resolves to HLS URLs fed to GStreamer playbin3
- `streamlink>=8.3` - Twitch stream resolution; requires cookies for authentication
- `platformdirs>=4.3` - Cross-platform config/data dir resolution
  - Data: `~/.local/share/musicstreamer` (Linux), OS-appropriate on Windows/macOS
  - Cache: `~/.cache/musicstreamer`
- `PySide6>=6.11` - Qt 6 bindings for GUI, event loop, D-Bus (Linux), WebEngine (OAuth)

**Encoding & HTTP:**
- `chardet>=5.2,<6` - Character encoding detection; pure-Python implementation required by PyInstaller
  - Pin <6 because requests rejects chardet >= 6.0.0
  - Preferred over charset_normalizer (mypyc-compiled .pyd, Phase 44 UATissue)
- `requests` (transitive via streamlink/yt-dlp) - HTTP client

**Windows (Conditional):**
- `winrt-Windows.Media.Playback>=3.2,<4` - Windows SMTC (System Media Transport Controls)
- `winrt-Windows.Media>=3.2,<4` - Metadata/display info for SMTC
- `winrt-Windows.Storage.Streams>=3.2,<4` - Stream I/O for cover art
- `winrt-Windows.Foundation>=3.2,<4` - Base WinRT foundation types
  - Pinned to 3.2.x after Phase 43.1 UAT (namespace stability concern)

**Linux (Conditional):**
- PyGObject (system package: `python3-gi`, `gir1.2-gtk-4.0`, `gir1.2-adw-1`, `gir1.2-gst-1.0`)
  - Not in pip dependencies — installed via apt
  - Provides `gi.repository` bindings for GStreamer, D-Bus, GTK

## Configuration

**Environment:**
- QT_QPA_PLATFORM=offscreen (tests only; set in `tests/conftest.py`)
- QTWEBENGINE_CHROMIUM_FLAGS (set in `oauth_helper.py` to override Chrome UA for Twitch login)

**Build:**
- `pyproject.toml` - Package metadata, dependencies, entry points, test config
- `[build-system]` - Requires setuptools>=68; backend is setuptools.build_meta
- Entry point: `musicstreamer = "musicstreamer.__main__:main"`

**Packaging (Windows):**
- `packaging/windows/build.ps1` - PowerShell build script for PyInstaller bundling
- `packaging/windows/*.iss` - Inno Setup installer definitions
- Version passed from pyproject.toml to iscc.exe

**Packaging (Linux):**
- `packaging/linux/` - GNOME/Flatpak integration (deferred to future phases)

## Platform Requirements

**Development:**
- Python 3.10+ with pip/setuptools
- GStreamer 1.0 dev headers (on Linux: `libgstreamer1.0-dev`)
- PySide6 dependencies (Qt libraries)
- Node.js on PATH (for yt-dlp JS runtime)

**Linux Production:**
- GStreamer 1.0 libraries and codecs
- GObject Introspection for PyGObject bindings
- D-Bus session (for MPRIS2 media controls)
- PySide6 WebEngine (optional, for OAuth; falls back silently)

**Windows Production:**
- Python 3.10+ runtime or PyInstaller bundle
- GStreamer 1.0 (bundled by PyInstaller)
- VC++ redistributable (Windows 10+)
- Node.js on PATH (for yt-dlp JS runtime)

**macOS Production:**
- Not yet ported (v2.0 targets Windows/Linux only)

---

*Stack analysis: 2026-04-28*
