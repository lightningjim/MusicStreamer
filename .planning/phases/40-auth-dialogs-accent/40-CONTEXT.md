# Phase 40: Auth Dialogs + Accent - Context

**Gathered:** 2026-04-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire the hamburger menu with real actions and build the remaining dialogs: AccountsDialog (Twitch OAuth via subprocess QWebEngineView), CookieImportDialog (YouTube cookies via file/paste/Google login), and AccentColorDialog (8 presets + hex entry with live QSS). Phase 40 also wires the Phase 39 DiscoveryDialog and ImportDialog into the hamburger menu — those classes exist but had no launch point.

Out of scope for Phase 40 (explicit cut-lines — DO NOT PULL FORWARD):
- Platform media keys → Phase 41 (MEDIA-01..05)
- Settings export/import → Phase 42 (SYNC-01..05) — menu entries added as disabled placeholders
- GStreamer Windows spike → Phase 43

</domain>

<decisions>
## Implementation Decisions

### Twitch OAuth (AccountsDialog)
- **D-01:** `AccountsDialog(QDialog)` with a Twitch section showing connection status ("Connected" / "Not connected") and a "Connect Twitch" / "Disconnect" button depending on state. Connection status checked via `os.path.exists(paths.twitch_token_path())`.
- **D-02:** "Connect Twitch" launches a subprocess Python helper (`oauth_helper.py`) that opens a `QWebEngineView` to the Twitch OAuth URL. The helper captures the token from the redirect and writes it to `paths.twitch_token_path()` with `0o600` permissions. Subprocess isolation avoids loading 130MB QtWebEngine into the main process.
- **D-03:** "Disconnect" deletes `twitch_token_path()` and updates the status display to "Not connected". Confirmation prompt before deletion.
- **D-04:** The subprocess helper communicates the token back via stdout (print the token) or a temp file. Main process polls/reads the result after the subprocess exits.

### YouTube Cookie Import (CookieImportDialog)
- **D-05:** Dedicated `CookieImportDialog(QDialog)` with three sections or tabs: "File" (QFileDialog picker for Netscape cookie file), "Paste" (QTextEdit for pasting cookie text), "Google Login" (launches subprocess QWebEngineView to google.com, extracts cookies after login).
- **D-06:** All three paths write to `paths.cookies_path()` with `0o600` permissions. Existing cookies are overwritten (no merge).
- **D-07:** Google Login uses the same subprocess helper pattern as Twitch OAuth — `oauth_helper.py` with a different URL/mode. The helper extracts cookies from `QWebEngineCookieStore.cookieAdded` and writes them in Netscape format.
- **D-08:** Validation: after import, check the file is non-empty and contains at least one `.youtube.com` domain line. Show success/error toast.

### Accent Color Picker (AccentColorDialog)
- **D-09:** `AccentColorDialog(QDialog)` with 8 color preset buttons in a grid (clickable swatches) + a `QLineEdit` for hex entry. Clicking a preset or entering a valid hex immediately previews the accent via live QSS on the parent app.
- **D-10:** "Apply" saves the hex value to `repo.set_setting("accent_color", hex_value)` and writes QSS to `paths.accent_css_path()`. "Reset" clears the setting and removes the QSS override, returning to system default palette.
- **D-11:** `accent_utils.py` needs a new `build_accent_qss(hex_value)` function that generates Qt QSS (not GTK CSS). Target selectors: `QPushButton` highlight states, `QSlider::sub-page`, chip selected states, segmented control active state — the same elements currently using `palette(highlight)`.
- **D-12:** On app startup, `MainWindow.__init__` checks for a saved accent color and applies the QSS if one exists. This ensures accent persists across restarts.

### Hamburger Menu (UI-10)
- **D-13:** Replace the `menubar.addMenu("≡")` placeholder with a real `QMenu` containing flat action entries separated by `QMenu.addSeparator()` for visual grouping:
  - Group 1: "Discover Stations", "Import Stations"
  - Separator
  - Group 2: "Accent Color", "YouTube Cookies", "Accounts"
  - Separator
  - Group 3: "Export Settings" (disabled), "Import Settings" (disabled)
- **D-14:** "Discover Stations" → opens `DiscoveryDialog` (from Phase 39)
- **D-15:** "Import Stations" → opens `ImportDialog` (from Phase 39)
- **D-16:** "Accent Color" → opens `AccentColorDialog` (new this phase)
- **D-17:** "YouTube Cookies" → opens `CookieImportDialog` (new this phase)
- **D-18:** "Accounts" → opens `AccountsDialog` (new this phase)
- **D-19:** "Export Settings" and "Import Settings" are disabled placeholder actions with tooltip "Coming in a future update" — Phase 42 (SYNC) enables them.

### Claude's Discretion
- Exact 8 accent color presets (suggest matching v1.5's palette)
- AccentColorDialog dimensions and swatch button sizes
- Whether the subprocess helper is a single `oauth_helper.py` with mode flags or two separate scripts
- QSS selector specificity for accent override
- CookieImportDialog tab vs stacked section layout
- Whether AccountsDialog is modal or non-modal

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap + Requirements
- `.planning/ROADMAP.md` § "Phase 40: Auth Dialogs + Accent" — goal, success criteria
- `.planning/REQUIREMENTS.md` § UI-08 (AccountsDialog), UI-09 (YouTube cookies), UI-10 (hamburger menu), UI-11 (accent color)

### Phase 39 output to build on
- `musicstreamer/ui_qt/main_window.py` — hamburger placeholder at line 61, dialog wiring patterns from Phase 39
- `musicstreamer/ui_qt/discovery_dialog.py` — DiscoveryDialog class (wire into menu)
- `musicstreamer/ui_qt/import_dialog.py` — ImportDialog class (wire into menu)
- `musicstreamer/ui_qt/toast.py` — ToastOverlay for feedback

### Backend modules (stable, reuse as-is)
- `musicstreamer/paths.py` — `cookies_path()`, `twitch_token_path()`, `accent_css_path()` all ready
- `musicstreamer/accent_utils.py` — `_is_valid_hex()` reusable; `build_accent_css()` is GTK-era, needs Qt QSS companion
- `musicstreamer/repo.py` — `get_setting()`, `set_setting()` for accent color persistence

### v1.5 Key Decisions (behavioral guidance)
- Subprocess-isolated QWebEngineView for OAuth (avoids 130MB in main process)
- Cookies stored with 0o600 permissions
- 8 accent presets + hex entry
- `--no-cookies-from-browser` always passed to yt-dlp

### STATE.md decisions
- "OAuth: subprocess-isolated QWebEngineView (oauth_helper.py)"
- "Phase 40 (OAuth): QWebEngineCookieStore.cookieAdded in subprocess context needs proof-of-concept before planning"

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`paths.py`** — all three file paths ready (`cookies_path`, `twitch_token_path`, `accent_css_path`)
- **`accent_utils._is_valid_hex()`** — hex color validation, reuse directly
- **`repo.get_setting()` / `repo.set_setting()`** — SQLite key-value for accent persistence
- **`ToastOverlay`** — feedback toasts for cookie import success/failure
- **Phase 39 dialogs** — DiscoveryDialog and ImportDialog ready for menu wiring

### Established Patterns
- Qt signals + queued connections for subprocess communication
- `QIcon.fromTheme` fallback for bundled icons
- Dialog wiring in MainWindow: `action.triggered.connect(self._open_xxx_dialog)`
- Bound-method signal slots (QA-05)

### Integration Points
- `MainWindow.menuBar()` — replace placeholder menu
- `MainWindow.__init__` — accent QSS load on startup
- `QApplication.instance().setStyleSheet()` — global QSS for accent override

</code_context>

<specifics>
## Specific Ideas

- User wants hamburger menu with separator-grouped flat actions (not submenus)
- Subprocess OAuth helper pattern shared between Twitch and Google login
- Export/Import Settings menu entries present but disabled as Phase 42 placeholders
- `accent_utils.build_accent_css()` is GTK — needs `build_accent_qss()` for Qt

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 40-auth-dialogs-accent*
*Context gathered: 2026-04-13*
