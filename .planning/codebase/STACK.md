# Technology Stack

**Analysis Date:** 2026-03-18

## Languages

**Primary:**
- Python 3.x - Application source code in `main.py`

## Runtime

**Environment:**
- Python 3 (requires `python3` in PATH)

**Package Manager:**
- pip (system Python packages)
- Not explicitly configured via requirements.txt or pyproject.toml

## Frameworks

**Core:**
- GTK 4.0 - GUI framework (imported via gi.require_version)
- Libadwaita (Adw) 1 - GNOME design system library
- GStreamer 1.0 - Multimedia playback framework

**Multimedia:**
- GStreamer 1.0 - Audio/video streaming and playback
- yt-dlp - YouTube/media extraction

**Audio Output:**
- PulseAudio/PipeWire - Audio backend via Gst pulsesink

## Key Dependencies

**Critical:**
- `yt-dlp` - Extracts stream URLs from YouTube and other media sources
  - Used in `main.py` line 16, enabled for YouTube stream resolution (lines 418-435)
  - Configuration: quiet mode, skip download, no playlist, m3u8 format preference

**Infrastructure:**
- `sqlite3` - Built-in Python database library
  - Database file: `~/.local/share/musicstreamer/musicstreamer.sqlite3`
  - Foreign key constraints enabled (line 35)

**System Libraries (via GObject introspection):**
- `gi` (PyGObject) - GObject introspection bindings
- `Gtk` (GTK 4.0) - GUI toolkit
- `Adw` (Libadwaita) - Modern GNOME widgets
- `Gio` - GObject-based I/O
- `GLib` - Core library
- `Gst` (GStreamer) - Multimedia framework

## Configuration

**Environment:**
- No explicit environment variables required for basic operation
- Uses XDG Base Directory: `~/.local/share/musicstreamer/`

**Build:**
- No build configuration file present
- Direct Python execution: `python3 main.py` or via shebang `#!/usr/bin/env python3`

**Desktop Integration:**
- Desktop file: `org.example.Streamer.desktop` (present but empty)
- Application ID: `org.example.MusicStreamer` (line 18)

## Platform Requirements

**Development:**
- Python 3 interpreter
- Python GObject introspection (`python3-gi`)
- GTK 4 development files (`libgtk-4-dev`)
- Libadwaita development files (`libadwaita-1-dev`)
- GStreamer development files (`libgstreamer1.0-dev`)
- yt-dlp package

**Production:**
- Python 3 runtime
- GTK 4 library
- Libadwaita library
- GStreamer library
- Audio server: PulseAudio or PipeWire
- Linux desktop environment (GNOME-based recommended due to Adwaita)

**Audio Support:**
- PulseAudio daemon or PipeWire (for audio output via pulsesink in GStreamer)

## Data Storage

**Local Database:**
- SQLite3 file at `~/.local/share/musicstreamer/musicstreamer.sqlite3`
- Tables: `providers`, `stations`
- Asset storage: `~/.local/share/musicstreamer/assets/`

---

*Stack analysis: 2026-03-18*
