# Feature Research

**Domain:** Cross-platform (Linux + Windows) desktop audio-stream player — Qt/PySide6 port of GTK MusicStreamer v1.5
**Researched:** 2026-04-10
**Confidence:** MEDIUM-HIGH (Windows integration verified via official docs + community; packaging verified via multiple sources)

---

## Scope

This file covers NEW capabilities needed for v2.0. All v1.5 features (station library, now-playing,
failover, discovery, import, Twitch, cookies, MPRIS2, accent color) are pre-validated and ported
as-is. This document does not re-list them.

---

## Feature Landscape

### Table Stakes (Users Expect These)

| Feature | Platform | Why Expected | Complexity | Notes |
|---------|----------|--------------|------------|-------|
| Qt/PySide6 UI at v1.5 feature parity | Both | Without this nothing else exists | HIGH | Core milestone deliverable; GTK retired entirely |
| Platform-correct user data paths | Both | Windows apps that write to their own install folder break under UAC and antivirus heuristics | LOW | `%LOCALAPPDATA%\MusicStreamer` on Windows; `~/.local/share/musicstreamer` on Linux unchanged. `platformdirs` library resolves both. |
| Windows SMTC (SystemMediaTransportControls) | Windows-only | Keyboard media keys, taskbar thumbnail transport, and lock-screen Now Playing all route through SMTC on Win10/11 | MEDIUM | `pywinrt` / `winsdk` packages provide Python bindings. Replaces dbus-python MPRIS2 on Windows. Linux keeps MPRIS2. Implement via platform-dispatch shim (`sys.platform` guard). |
| MPRIS2 retained on Linux | Linux-only | Current behavior; Linux users expect media-key passthrough via D-Bus | LOW | Keep existing `mpris.py`; guard with `sys.platform == 'linux'` |
| High-DPI scaling | Both (critical Windows) | Windows 10/11 defaults to 125–150% scaling; unscaled Qt app looks tiny or blurry | LOW | Qt 6 handles automatically when `QApplication.setHighDpiScaleFactorRoundingPolicy(PassThrough)` is set. Porting checklist: confirm no hardcoded pixel sizes survive the GTK port. |
| Dark-mode respect on Windows | Windows-only | Windows 11 users with system dark mode expect apps to follow it | MEDIUM | Qt 6.5+ reads Windows color scheme via `QStyleHints.colorScheme`. The default Windows style does NOT reliably respect it — only Fusion does. Recommendation: ship Fusion style with manual palette override on Windows. `pyqtdarktheme` library provides a consistent palette as a fallback. Known bug in PySide 6.8.0.1 — test carefully. |
| Windows Defender SmartScreen — signed executable | Windows-only | Unsigned EXE shows "Windows protected your PC" block dialog; many users won't know the bypass | HIGH | As of 2024, EV certs no longer bypass SmartScreen instantly — reputation builds over time regardless of cert type. For personal/small distribution: self-signed is acceptable if users are trusted. For wider distribution: OV code-signing cert (~$100–300/yr) reduces friction. Hardware token required by CA/B Forum since June 2023. |
| Single-instance enforcement | Both | Second instance would start a second GStreamer pipeline; on Windows there is no session D-Bus to arbitrate | LOW | Windows: named mutex via `ctypes.windll.kernel32.CreateMutexW`. Linux: lock file in XDG runtime dir. On second launch, raise the existing window. |
| Bundled SVG icon set (replace GNOME symbolic icons) | Both | `QIcon.fromTheme()` returns nothing on Windows; GNOME symbolic icons don't exist there | MEDIUM | Use Material Symbols or Fluent System Icons (both Apache 2.0); subset to ~20 icons. Compile into Qt resources (`.qrc`). Pattern: `QIcon.fromTheme("media-playback-start", QIcon(":/icons/play.svg"))` — Linux themes win when present, bundled SVGs everywhere else. `QtSvg` plugin must be included in the PyInstaller bundle. |
| System font on Windows (Segoe UI) | Windows-only | Qt defaults to Segoe UI on Windows automatically. No action needed, but the Adwaita Sans assumption must not be hardcoded anywhere in the Qt UI code | LOW | Porting checklist item: confirm no `setFont("Adwaita Sans")` calls survive the port. |
| Manual settings export/import | Both | Stated v2.0 milestone requirement for cross-machine moves | MEDIUM | See dedicated section below. |
| Windows installer / distributable binary | Windows-only | Windows users expect an installer EXE; a raw folder is not an acceptable deliverable | MEDIUM | See packaging section below. |

### Differentiators (Nice-to-Haves)

| Feature | Platform | Value Proposition | Complexity | Notes |
|---------|----------|-------------------|------------|-------|
| Minimize-to-tray | Both (more relevant Windows) | Music player running in background with no taskbar clutter; standard for media players | LOW | `QSystemTrayIcon` + `QMenu` is well-supported on both platforms. Hide window on minimize, show tray icon, left-click restores. First close should offer "minimize to tray" vs "quit". |
| Windows accent color seed on first run | Windows-only | App accent matches user's Windows color, replacing the custom GNOME accent picker for that platform | MEDIUM | `QPalette::Accent` via `QGuiApplication.palette()` reads Windows accent. Broken in PySide 6.8.0.1 (showed gray). Registry fallback: `HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Accent`. Decision: keep custom accent picker as primary; optionally seed it from Windows accent on first launch only. |
| Toast replacement via QSystemTrayIcon.showMessage | Both | Current Adw.Toast has no Qt equivalent; failover and "Connecting…" toasts need a cross-platform replacement | LOW | `QSystemTrayIcon.showMessage()` is the correct baseline — it works on both platforms, has no additional dependencies, and covers the non-blocking notification use case adequately. |
| Global media hotkeys beyond SMTC | Windows-only | Some users remap media keys or use global shortcuts outside SMTC | MEDIUM | SMTC covers standard media keys natively. Global hotkeys beyond that (e.g., `Ctrl+Alt+P`) require `RegisterHotKey` Win32 API or the `keyboard` PyPI package. Defer unless SMTC proves insufficient in practice. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| MSIX packaging | Modern Microsoft format, avoids SmartScreen | Requires Microsoft Store submission or sideloading config, mandatory signing with hardware token, complex build pipeline. Overkill for a personal app. | PyInstaller + NSIS EXE installer |
| Auto-update | Nice for end-users | Single-user personal app. Auto-update infrastructure adds ~50 LOC of error-prone code (GitHub Releases API check, download, re-exec, signature verify) for zero real benefit. | Manual download when a new build is wanted |
| Native Windows toast (Windows.UI.Notifications / winrt) | Native feel | Requires AUMID registration, COM machinery, significantly more setup than the value justifies. Broken in some Python WinRT versions. | `QSystemTrayIcon.showMessage()` covers the need completely |
| Cookie export in settings bundle | Completeness | Cookies contain live session tokens; exporting them in a portable ZIP creates a credential exposure risk. Google session cookies especially sensitive. | Document: cookies must be re-imported manually on a new machine |
| Twitch token export in settings bundle | Completeness | Same credential exposure risk as cookies | Document: re-auth manually on new machine |
| adwaita-qt pixel-perfect theming | Match GNOME look on Linux | `adwaita-qt` gives approximate parity; chasing pixel-perfection means maintaining a custom style engine. GNOME users understand Qt apps look slightly different from native GTK apps. | Ship Fusion + adwaita-qt, accept the visual delta |
| Windows Jump List | Recently-played stations in taskbar right-click | Very high complexity (`winrt` Jump List API), fragile, and the station library is always one click away in the app. Marginal value. | In-app recently-played section (already v1.5) |
| Taskbar thumbnail toolbar (play/pause buttons on hover) | Convenience | `ITaskbarList3::ThumbBarAddButtons` Win32 COM; high complexity. SMTC already covers this use case for Windows. | SMTC lock-screen / taskbar integration |
| File association (.pls / .m3u double-click opens app) | Standard player behavior | Requires registry writes at install time, a URL handler protocol, and a CLI entry point that imports/plays a file — significant cross-cutting scope. This app's workflow is library-first, not file-first. | Defer to v2.1 if requested |

---

## Settings Export/Import — Feature Shape

**What the bundle contains:**

| Data | Include | Rationale |
|------|---------|-----------|
| Stations (name, provider, tags, logo path, ICY disabled) | YES | Core library |
| Station streams (URL, quality, label, position) | YES | Multi-stream model |
| Favorites (track titles with station/provider/genre) | YES | User data |
| App settings (volume, accent color) | YES | Preferences |
| Logo image files | YES — embedded in archive | Without logos, import looks broken |
| cookies.txt | NO | Live session tokens; credential risk |
| Twitch OAuth token | NO | Live credential; credential risk |

**Format:** Zip archive (`.musicstreamer` extension or `.zip`) containing:
- `export.json` — all station/stream/favorites/settings data with a `schema_version` field
- `logos/` — image files referenced by station records by relative path

Rationale over alternatives: A SQLite snapshot is binary-diff-unfriendly and couples the export format to internal schema migrations. A flat JSON + images zip is human-inspectable, version-tolerant, trivially implemented with stdlib (`zipfile`, `json`), and easy to validate on import.

**Import conflict resolution:** Replace-on-URL-match. If an existing station has the same primary stream URL, update its metadata. Otherwise insert. Do not silently discard. Surface a summary dialog ("3 updated, 12 added") after import completes.

---

## Windows Packaging — Recommendation

**Toolchain:** PyInstaller 6.x → NSIS installer EXE

- PyInstaller bundles Python + GStreamer + PySide6 into a single-folder dist. Well-documented for PySide6 (pythonguis.com tutorial current 2025, PyInstaller 6.19 on PyPI).
- NSIS wraps the dist folder into a standard Windows installer EXE. Generates uninstaller, Start Menu shortcut, optional desktop shortcut. Small footprint, scriptable, widely used.
- Pipeline: `pyinstaller musicstreamer.spec` → `makensis installer.nsi` → distributable `MusicStreamer-Setup.exe`.
- **Highest-complexity packaging concern:** GStreamer on Windows requires the GStreamer Windows runtime installer or bundled GStreamer plugins. This is non-trivial and needs its own phase-level research before implementation.
- User data location: `%LOCALAPPDATA%\MusicStreamer` (not `%APPDATA%` — avoid roaming profile replication of large logo image files).
- Auto-update: none. Personal app, one user.
- SmartScreen: for personal use, unsigned or self-signed is acceptable (user clicks "More info → Run anyway"). For distribution to others, OV cert removes the block after reputation builds.

---

## Cross-Platform Icon Strategy

**Recommendation:** Bundle a custom SVG icon set as Qt resources.

- Source: Material Symbols (Google, Apache 2.0) or Fluent System Icons (Microsoft, MIT). Subset to ~20 icons actually used.
- Compile into a `.qrc` resource file so icons are embedded in the binary — no external asset files at runtime.
- Call pattern: `QIcon.fromTheme("media-playback-start", QIcon(":/icons/play.svg"))` — Linux GNOME icon themes win when present; bundled SVGs are the universal fallback.
- The `QtSvg` plugin must be included in the PyInstaller bundle via `--collect-all PySide6.QtSvg`.
- GNOME symbolic icons (current v1.5 approach via GTK) are entirely unavailable in Qt; do not attempt to reuse them.

---

## Feature Dependencies

```
Qt/PySide6 port (all UI)
    └──required by──> SMTC integration (Windows media keys)
    └──required by──> Tray icon / minimize-to-tray (QSystemTrayIcon)
    └──required by──> Dark mode palette
    └──required by──> Windows accent color seed
    └──required by──> Toast replacement (QSystemTrayIcon.showMessage)
    └──required by──> Bundled icon set (Qt resources)

Platform data paths (%LOCALAPPDATA% / ~/.local/share)
    └──required by──> Settings export/import (knows where DB lives)
    └──required by──> Windows installer NSIS script

Settings export/import
    └──enhances──> Cross-machine workflow (stated v2.0 goal)
    └──must exclude──> cookies.txt, Twitch token (credential risk)

PyInstaller bundle
    └──required by──> NSIS installer
    └──GStreamer Windows runtime──> needs phase-specific research

Single-instance enforcement
    └──enhances──> Tray icon (second launch raises existing window rather than refusing)
```

### Dependency Notes

- SMTC requires the port to be functionally complete so the Now Playing metadata (station name, track title, art) is available to push into SMTC.
- The bundled icon set must be decided before UI implementation begins so icons are not hardcoded as theme-only references.
- GStreamer Windows runtime bundling is a hard dependency for the installer to produce a working binary; it must be resolved in the early packaging phase, not deferred to the end.

---

## MVP Definition

### Launch With (v2.0)

- [ ] Qt/PySide6 UI at v1.5 feature parity — without this nothing else functions
- [ ] Platform-correct user data paths (`%LOCALAPPDATA%` on Windows, unchanged on Linux)
- [ ] Cross-platform media keys shim (SMTC on Windows, MPRIS2 on Linux)
- [ ] Bundled SVG icon set replacing GNOME symbolic icons
- [ ] Dark mode on Windows via Fusion + palette (imperfect but functional)
- [ ] Single-instance enforcement
- [ ] Settings export/import (stated v2.0 milestone requirement)
- [ ] Windows installer (PyInstaller + NSIS)
- [ ] High-DPI scaling (Qt 6 default; porting checklist to catch hardcoded pixel sizes)
- [ ] Toast replacement via `QSystemTrayIcon.showMessage`

### Add After Port Stabilizes (v2.1)

- [ ] Minimize-to-tray — low complexity, high UX value once port is stable
- [ ] Windows accent color seed on first run — differentiator, low risk

### Future Consideration (v2.2+)

- [ ] File association for .pls / .m3u — high complexity, niche benefit for a library-first app
- [ ] Windows Jump List — very high complexity, marginal value
- [ ] Taskbar thumbnail toolbar — very high complexity, covered by SMTC

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Qt/PySide6 port (parity) | HIGH | HIGH | P1 |
| Platform data paths | HIGH | LOW | P1 |
| SMTC (Windows media keys) | HIGH | MEDIUM | P1 |
| Bundled SVG icons | HIGH | MEDIUM | P1 |
| Windows installer | HIGH | MEDIUM | P1 |
| Settings export/import | HIGH | MEDIUM | P1 |
| Single-instance enforcement | MEDIUM | LOW | P1 |
| High-DPI scaling | HIGH | LOW | P1 |
| Dark mode (Windows) | MEDIUM | MEDIUM | P1 |
| Toast via QSystemTrayIcon | MEDIUM | LOW | P1 |
| Minimize-to-tray | MEDIUM | LOW | P2 |
| Windows accent color seed | LOW | MEDIUM | P2 |
| File association .pls/.m3u | LOW | HIGH | P3 |
| Jump List | LOW | HIGH | P3 |

---

## Sources

- Qt High DPI docs: https://doc.qt.io/qtforpython-6/overviews/qtdoc-highdpi.html
- QSystemTrayIcon docs + example: https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QSystemTrayIcon.html
- Qt Dark Mode on Windows 11 (Qt blog, Qt 6.5): https://www.qt.io/blog/dark-mode-on-windows-11-with-qt-6.5
- QStyleHints.colorScheme docs: https://doc.qt.io/qtforpython-6/PySide6/QtGui/QStyleHints.html
- PySide6 accent color bug (6.8.0.1): https://github.com/TagStudioDev/TagStudio/issues/668
- PyWinRT / python-winsdk (SMTC bindings): https://github.com/pywinrt/python-winsdk
- winsdk on PyPI: https://pypi.org/project/winsdk/
- SMTC Microsoft docs: https://learn.microsoft.com/en-us/windows/apps/develop/media-playback/system-media-transport-controls
- Windows SmartScreen / OV vs EV (2024 change): https://learn.microsoft.com/en-us/answers/questions/417016/reputation-with-ov-certificates-and-are-ev-certifi
- Packaging PySide6 with PyInstaller + InstallForge: https://www.pythonguis.com/tutorials/packaging-pyside6-applications-windows-pyinstaller-installforge/
- MSIX + PyInstaller (2025): https://82phil.github.io/python/2025/04/24/msix_pyinstaller.html
- Qt icon themes cross-platform guide: https://openapplibrary.org/dev-tutorials/qt-icon-themes
- QIcon fromTheme docs: https://doc.qt.io/qt-6/qicon.html
- SingleApplication (Qt6 single-instance): https://github.com/itay-grudev/SingleApplication

---

*Feature research for: MusicStreamer v2.0 OS-Agnostic Qt/PySide6 port*
*Researched: 2026-04-10*
