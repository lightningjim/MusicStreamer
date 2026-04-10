# Phase 22: Import YT Cookies - Context

**Gathered:** 2026-04-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Let users provide YouTube cookies directly (file, paste, or Google login) instead of yt-dlp auto-extracting from the browser on every call. Eliminates the GNOME desktop keyring extraction issue. Cookies are stored in the app data directory and passed to yt-dlp/mpv on all YouTube operations.

</domain>

<decisions>
## Implementation Decisions

### Cookie Input Methods
- **D-01:** Support three input methods: file picker (primary), paste textarea, and Google login flow
- **D-02:** File picker is the primary/prominent method; paste and Google login are under an "Other methods" expander in the dialog
- **D-03:** Google login opens a browser window for the user to sign into Google, then captures the resulting YouTube cookies and saves them as cookies.txt

### Cookie Storage & Lifecycle
- **D-04:** Cookie file stored at `~/.local/share/musicstreamer/cookies.txt` — alongside DB and assets, app-owned
- **D-05:** Manual lifecycle only — user re-imports when things stop working; no automatic expiry detection or auth failure prompts
- **D-06:** Show "last imported" date in the cookie dialog UI

### Settings UI
- **D-07:** Add a hamburger/primary menu to the header bar with "YouTube Cookies..." menu item
- **D-08:** Cookie dialog is an Adw.Dialog with file picker prominent at top, "Other methods" expander below containing paste textarea and Google login button
- **D-09:** Dialog has Import and Clear buttons — Clear removes the stored cookies.txt

### yt-dlp/mpv Integration
- **D-10:** If cookies.txt exists, pass it to EVERY yt-dlp and mpv call — no conditional logic
- **D-11:** yt-dlp: `--cookies <path>` flag on all subprocess calls (playlist scan in yt_import.py)
- **D-12:** mpv: `--ytdl-raw-options=cookies=<path>` flag on playback subprocess calls (player.py)
- **D-13:** Disable yt-dlp's default browser cookie extraction (`--no-cookies-from-browser` or equivalent) to eliminate the GNOME keyring issue at the source

### Claude's Discretion
- Exact Adw widget choices for the dialog layout
- Google login implementation approach (selenium, playwright, webkitgtk, or other)
- Validation of pasted cookie content format
- Error handling for failed Google login flow

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing YouTube integration
- `musicstreamer/player.py` — YouTube playback via mpv subprocess (line 83-96), where `--cookies` and `--no-cookies-from-browser` flags need adding
- `musicstreamer/yt_import.py` — YouTube playlist scan via yt-dlp subprocess (line 29-34), where `--cookies` flag needs adding
- `musicstreamer/ui/import_dialog.py` — Existing import dialog with YouTube and AudioAddict tabs (pattern reference for dialog structure)
- `musicstreamer/ui/main_window.py` — Header bar setup where hamburger menu needs adding

### Data directory
- `musicstreamer/constants.py` — App data directory path definition (`~/.local/share/musicstreamer/`)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `import_dialog.py` — Existing tabbed dialog pattern (YouTube + AudioAddict) for reference on dialog structure and GTK4/Adwaita patterns
- `edit_dialog.py` — File picker implementation for station art that can be adapted for cookies.txt file selection
- `constants.py` — DATA_DIR constant for consistent path to `~/.local/share/musicstreamer/`

### Established Patterns
- Subprocess calls to external tools (yt-dlp, mpv) with `subprocess.run`/`subprocess.Popen`
- GTK4/Libadwaita dialog patterns with `Adw.Dialog` or `Adw.Window`
- File operations using `os.path` and `shutil` for asset management

### Integration Points
- `player.py:_play_youtube()` — mpv Popen call needs `--ytdl-raw-options=cookies=...` added
- `yt_import.py:scan_playlist()` — yt-dlp subprocess.run call needs `--cookies` and `--no-cookies-from-browser` added
- `main_window.py` header bar — needs hamburger menu with "YouTube Cookies..." item
- `constants.py` — may need `COOKIES_PATH` constant

</code_context>

<specifics>
## Specific Ideas

- Google login flow: open a controlled browser window, let user sign into Google, capture YouTube cookies from that session, save to cookies.txt format
- "Get cookies.txt LOCALLY" browser extension is the expected primary workflow for file-based import
- The GNOME issue is specifically about yt-dlp's default `--cookies-from-browser` behavior triggering keyring access prompts or failures

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 22-import-yt-cookies-separately-from-extracting-from-browser-ev*
*Context gathered: 2026-04-06*
