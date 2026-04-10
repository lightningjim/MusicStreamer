# Technology Stack — v2.0 OS-Agnostic Qt/PySide6 Port

**Project:** MusicStreamer v2.0
**Researched:** 2026-04-10
**Scope:** New stack additions/changes only. Existing validated stack (Python, GStreamer playbin3, yt-dlp, streamlink, mpv, SQLite, urllib) is unchanged and not re-researched.

---

## Q1: PySide6 Version and Licensing

**Target:** PySide6 6.8.x (LTS) or 6.11.0 (current)

Current PyPI release is **6.11.0** (released 2026-03-23). Requires Python 3.10–3.14.

**Licensing for a personal app:** PySide6 is LGPL v3. Python apps that `import PySide6` as a separate installed package satisfy the LGPL "dynamic linking" requirement automatically — you do not need to open-source your own code. No commercial license needed. This is a straightforward personal-app case.

**Version recommendation:** Start with 6.8.x (last LTS point release) if stability matters, or 6.11.0 if you want current APIs. The project is a port with no novel Qt features, so either works. Pin to a minor version in `pyproject.toml` to avoid breaking API changes mid-development.

**Confidence:** HIGH — verified against PyPI page and official Qt licensing docs.

---

## Q2: GStreamer ↔ Qt Event Loop Integration

This is the most critical decision for the port. The answer is nuanced.

### How the v1.5 GTK code works

`dbus-python` sets `DBusGMainLoop(set_as_default=True)`, which installs GLib's main context as the default. GStreamer's `bus.add_watch()` and `bus.add_signal_watch()` both require a running GLib main loop — and GTK runs one implicitly. That is why `GLib.idle_add()` works: the GTK main loop drives the GLib main context, which drains bus watches and idles on each iteration.

### What changes with PySide6

Qt on Linux is compiled with **QEventDispatcherGlib** by default. This means Qt's event loop drives GLib's `g_main_context_default` instead of `g_main_loop_run`. On Linux this is sufficient: `bus.add_signal_watch()` + `bus.connect('message', handler)` will work because Qt's main loop is already iterating the GLib default context. You do **not** need a separate `GLib.MainLoop` thread on Linux.

On Windows, Qt does not use QEventDispatcherGlib (GLib is not available). This is where the integration breaks:

- `bus.add_signal_watch()` / `bus.add_watch()` require a running GLib main context, which Qt's Win32 event loop does not provide.
- `GLib.idle_add()` similarly has no effect without a GLib context being iterated.

### Recommended integration pattern

**QTimer-based bus polling** — works on both Linux and Windows, avoids the GLib loop dependency:

```python
# In Player.__init__(), after creating the pipeline:
self._bus = self._pipeline.get_bus()
# Do NOT call bus.add_signal_watch() — this requires GLib main context
self._bus_timer = QTimer()
self._bus_timer.setInterval(50)  # 50ms polling — low latency, low CPU
self._bus_timer.timeout.connect(self._drain_bus)
self._bus_timer.start()

def _drain_bus(self):
    while True:
        msg = self._bus.timed_pop(0)  # non-blocking
        if msg is None:
            break
        self._on_bus_message(msg)
```

`timed_pop(0)` returns immediately with `None` if no message is waiting — safe to call in a 50ms timer. The callback `_on_bus_message` runs on the Qt main thread, so Qt UI calls (`setText`, `QPixmap`, etc.) are safe inside it.

**Replace `GLib.idle_add()` with `QMetaObject.invokeMethod()` or signals for cross-thread UI updates.** In v1.5, GStreamer bus callbacks fire in GStreamer's streaming thread and use `GLib.idle_add()` to marshal to the GTK main thread. With PySide6, the equivalent is:
- For worker threads: `QTimer.singleShot(0, callback)` or emit a Qt signal connected to the main-thread slot.
- Do not use `GLib.idle_add()` — it will silently do nothing on Windows.

**Qt Multimedia is NOT a viable replacement for GStreamer.** It lacks ICY metadata, does not handle HLS/RTMP/Twitch, cannot be driven by yt-dlp URLs, and has no equivalent to `playbin3`'s multi-protocol support. Keep GStreamer directly.

**Confidence:** HIGH (Linux QEventDispatcherGlib behavior) / MEDIUM (Windows polling approach — well-documented pattern, but the specific 50ms QTimer approach requires integration testing).

**Sources:**
- https://discourse.gstreamer.org/t/qt-gstreamer-event-loop-woes/5766
- https://gstreamer.freedesktop.org/documentation/gstreamer/gstbus.html
- https://forum.qt.io/topic/104299/integration-with-glib-event-loop

---

## Q3: Windows Availability of Backend Tools

### GStreamer on Windows

**Two viable options; the official MSI installer is preferred for app distribution:**

| Approach | Pros | Cons |
|----------|------|------|
| Official GStreamer MSI (gstreamer.freedesktop.org) | Prebuilt, complete, includes all plugin sets, MSI installer for runtime | PyGObject Python bindings NOT included — must install separately |
| MSYS2 (mingw-w64 packages) | One-step install includes GStreamer + PyGObject + Python | MSYS2 environment dependency is hard to bundle in a distributable app |

**For development:** MSYS2 UCRT64 is the fastest path — `pacman -S mingw-w64-ucrt-x86_64-gstreamer mingw-w64-ucrt-x86_64-gst-plugins-{base,good,bad} mingw-w64-ucrt-x86_64-python3-gobject`.

**For distribution:** Official GStreamer Windows MSI runtime + `pip install PyGObject` (which finds GStreamer DLLs via `GSTREAMER_ROOT_X86_64` env var). PyInstaller has a GStreamer-aware gi hook that bundles discovered DLLs and plugins. See Q7.

**PyGObject on Windows:** Available via pip (`pip install PyGObject`) but requires GStreamer DLLs to be resolvable at runtime. The GSTREAMER_ROOT_X86_64 environment variable or PATH pointing to GStreamer's `bin/` makes this work. Not a dealbreaker, but setup is manual.

**Confidence:** MEDIUM — official installer path is documented, but bundling GStreamer DLLs into a distributable PyInstaller build requires phase-specific testing.

### yt-dlp on Windows

**Not a dealbreaker.** Official Windows `.exe` builds available from GitHub releases. Can also be installed via `pip install yt-dlp`. No MSYS2 or special environment required.

### streamlink on Windows

**Not a dealbreaker.** Official Windows installer and portable `.exe` available. Also installable via `pip install streamlink`. Native Windows binary.

### mpv on Windows

**Not a dealbreaker.** Official Windows builds at mpv.io. Used in MusicStreamer as a subprocess for cookie-retry path. Works natively on Windows.

**Summary: No backend tools are dealbreakers on Windows.** GStreamer setup is the most complex but is well-trodden with official tooling.

---

## Q4: Cross-Platform Media Keys

**No single Python library bridges MPRIS2 and SMTC.** Two separate implementations are required.

### Linux: Replace dbus-python with PySide6.QtDBus

`dbus-python` can stay for the interim but requires `GDBusGMainLoop` which conflicts with the Qt-only loop goal. The clean replacement is **PySide6.QtDBus**.

QtDBus can expose a D-Bus service object (server mode) via `QDBusConnection.registerObject()` and `QDBusConnection.registerService()`. This is sufficient for MPRIS2. The existing `mpris.py` module will need rewriting using `QDBusAbstractAdaptor` rather than `dbus.service.Object`, but the interface is analogous.

**Alternatively:** Keep `dbus-python` on Linux only, initialized before Qt starts, and avoid the GLib loop conflict by not calling `DBusGMainLoop(set_as_default=True)` — instead, use `dbus.mainloop.glib` only for the D-Bus service thread. This is a lower-risk interim approach for the port.

**Recommendation:** Rewrite MPRIS2 in PySide6.QtDBus. It removes the dbus-python dependency entirely and is the correct long-term architecture.

**Libraries:**
- `PySide6.QtDBus` — part of the PySide6 package, no extra install needed

### Windows: SMTC via winrt packages

The `winrt` package family (modular, one package per Windows SDK namespace) provides Python bindings for WinRT APIs including SMTC.

```
pip install winrt-runtime winrt-Windows.Media winrt-Windows.Media.Playback
```

`winrt-Windows.Media.Control` is for reading media sessions from other apps. To **register** as a media provider (to receive play/pause/stop key presses), you use `winrt-Windows.Media.Playback` — specifically `SystemMediaTransportControls` obtained via `MediaPlayer.system_media_transport_controls`.

**Pattern:**
```python
# Windows only — import guarded by sys.platform == 'win32'
from winrt.windows.media.playback import MediaPlayer
mp = MediaPlayer()
smtc = mp.system_media_transport_controls
smtc.is_play_enabled = True
smtc.is_pause_enabled = True
smtc.is_stop_enabled = True
smtc.button_pressed += lambda sender, args: _handle_button(args.button)
```

**Requires:** Windows 10+ (winrt APIs). Python 3.9+. Windows-only.

**Confidence:** MEDIUM — winrt package is the correct mechanism, SMTC registration via MediaPlayer is documented in Microsoft docs. The specific Python async pattern may need testing (winrt uses asyncio-style async for some APIs).

**Sources:**
- https://pypi.org/project/winrt-Windows.Media.Control/
- https://learn.microsoft.com/en-us/uwp/api/windows.media.systemmediatransportcontrols

---

## Q5: Replacement for WebKit2Gtk (OAuth Cookie Capture)

**Use `PySide6.QtWebEngineWidgets`.** This is the direct functional equivalent of WebKit2Gtk — an embedded Chromium browser that can navigate to OAuth pages, capture cookies, and be driven from Python.

```
pip install PySide6-WebEngine
```

`QWebEngineView` + `QWebEngineProfile` provides cookie access via `QNetworkCookie` and `QWebEngineCookieStore`. The existing WebKit2 subprocess pattern can be replaced with an in-process `QWebEngineView` dialog (preferred) or kept as a subprocess using a minimal PySide6 WebEngine script.

### Windows bundle size

QtWebEngine bundles Chromium — the `QtWebEngineCore` DLL is ~130 MB. This is unavoidable if the OAuth login dialog is in-process. The total distributable will be significantly larger on Windows than a bare Qt app.

**Mitigation options:**
1. Keep the OAuth capture as a **subprocess** (spawn a minimal helper script that uses `PySide6.QtWebEngineWidgets`). The subprocess DLLs still get bundled by PyInstaller but are isolated from the main binary.
2. Use a system browser + local redirect server for OAuth instead of embedded WebView. This avoids QtWebEngine entirely. For Twitch OAuth specifically, this is the cleaner UX pattern.
3. Accept the size. For a personal app, 200-300 MB distributable is acceptable.

**Gotcha on Windows:** QtWebEngine requires a helper process (`QtWebEngineProcess.exe`) and a `qt.conf` file pointing to it. PyInstaller's QtWebEngine hook handles this automatically in recent versions (6.x) but must be verified. Frozen apps that ship QtWebEngine without correct `qt.conf` fail silently.

**Confidence:** HIGH (QtWebEngineWidgets capability) / MEDIUM (bundle size numbers — 130MB for QtWebEngineCore is from a 2023 PyInstaller discussion and directionally accurate).

**Sources:**
- https://doc.qt.io/qtforpython-6/PySide6/QtWebEngineWidgets/index.html
- https://doc.qt.io/qt-6/qtwebengine-platform-notes.html

---

## Q6: D-Bus / MPRIS2 on Linux — dbus-python vs QtDBus

**Recommendation: Migrate to `PySide6.QtDBus`.** Drop `dbus-python`.

Rationale:
- `dbus-python` requires `DBusGMainLoop(set_as_default=True)` to function properly as a D-Bus service. This integrates the GLib main context, which works under GTK but creates friction under Qt's event loop on Linux and is entirely broken on Windows.
- `PySide6.QtDBus` is already in the dependency set (part of PySide6), requires no additional package, and integrates natively with Qt's event loop.
- `QDBusAbstractAdaptor` is the correct mechanism for exposing a D-Bus service (MPRIS2 player interface). `QDBusConnection.sessionBus().registerService("org.mpris.MediaPlayer2.musicstreamer")` and `registerObject("/org/mpris/MediaPlayer2", adaptor)` are the call sites.

**Implementation note:** `QDBusAbstractAdaptor` is a C++ class, but PySide6 exposes it. Implementing MPRIS2 requires declaring the interface XML or using `Q_CLASSINFO("D-Bus Interface", "org.mpris.MediaPlayer2.Player")`. This is more boilerplate than `dbus-python`'s decorator-based approach, but is fully supported.

**On Windows:** QtDBus is a no-op on Windows (Qt builds without D-Bus support on Win32). The MPRIS2 code path must be runtime-guarded with `sys.platform == 'linux'`.

**Confidence:** MEDIUM — QtDBus server-mode capability is documented in Qt docs; the MPRIS2 adaptor pattern requires implementation verification.

**Sources:**
- https://doc.qt.io/qtforpython-6/PySide6/QtDBus/index.html
- https://wiki.qt.io/Qt_for_Python_DBusIntegration

---

## Q7: Packaging — PyInstaller vs Briefcase vs Nuitka

**Recommendation: PyInstaller 6.x.**

| Tool | GStreamer DLL Support | PySide6 Support | Maturity |
|------|----------------------|-----------------|---------|
| PyInstaller 6.x | YES — dedicated gi/gstreamer hook with `include_plugins`/`exclude_plugins` in `.spec` | YES — official hook in `pyinstaller-hooks-contrib` | HIGH |
| Briefcase | NO native GStreamer handling — would require manual `binaries` entries | YES | MEDIUM |
| Nuitka | Known issues with GStreamer + PyGObject (open GitHub issue #2762) | YES | LOW for this use case |

### PyInstaller GStreamer hook

PyInstaller's gi hook auto-discovers GStreamer plugins from the build environment and bundles them. Control via `.spec` `hooksconfig`:

```python
hooksconfig={
    "gstreamer": {
        "include_plugins": [
            "coreelements",   # required
            "playback",       # playbin3
            "soup",           # HTTP source
            "typefindfunctions",
            "audioconvert", "audioresample", "autodetect",
            "id3demux", "icydemux",  # ICY metadata
        ],
        "exclude_plugins": [
            "opencv", "vulkan", "qt",  # not needed
        ],
    },
}
```

This keeps the bundle size manageable. Default (no config) includes all installed plugins — too large.

**Windows GStreamer DLL bundling:** PyInstaller follows DLL dependencies and collects them. With GStreamer installed via official MSI (DLLs in `%GSTREAMER_ROOT_X86_64%\bin\`), PyInstaller finds and bundles them if that directory is on PATH at build time. The `GST_PLUGIN_PATH` env var must be set in the frozen app via `os.environ` before `Gst.init()`.

**Distributable size estimate:** PySide6 base ~80MB + GStreamer runtime + selected plugins ~100-150MB + QtWebEngine (if included) ~130MB. Without WebEngine: ~200-250MB total. With WebEngine: ~350MB.

**Installer tooling:** PyInstaller produces a directory or single-file EXE. Wrap with **NSIS** or **Inno Setup** for a proper Windows installer. Both are free and well-integrated with PyInstaller workflows.

**Confidence:** MEDIUM — PyInstaller GStreamer hook capability confirmed in docs; actual bundle size and DLL resolution on Windows requires build-time verification.

**Sources:**
- https://pyinstaller.org/en/v6.11.0/hooks-config.html
- https://www.pythonguis.com/tutorials/packaging-pyside6-applications-windows-pyinstaller-installforge/
- https://doc.qt.io/qtforpython-6.7/deployment/deployment-pyside6-deploy.html

---

## Q8: Cross-Platform Path Handling

**Use `platformdirs` (not `QStandardPaths`).** 

`platformdirs` is a pure-Python library that returns correct platform-specific directories:
- Linux: `~/.local/share/musicstreamer/` (XDG_DATA_HOME)
- Windows: `%APPDATA%\musicstreamer\` (CSIDL_APPDATA)

```
pip install platformdirs
```

```python
from platformdirs import user_data_dir
DATA_DIR = Path(user_data_dir("musicstreamer", appauthor=False))
```

`QStandardPaths` is an alternative but introduces a Qt dependency in the non-UI modules (constants.py, repo.py) — coupling that will cause pain in tests and anywhere the backend is used standalone. `platformdirs` is pure Python, well-maintained, and is exactly what the existing `~/.local/share/musicstreamer/` hardcoding should become.

**Migration:** v1.5 uses a hardcoded `Path.home() / ".local/share/musicstreamer"`. Replace with `user_data_dir()` call in `constants.py`. The path resolves identically on Linux, correctly to AppData on Windows.

**Confidence:** HIGH — platformdirs is the de facto standard for this use case, actively maintained, used widely across the Python ecosystem.

**Sources:**
- https://github.com/tox-dev/platformdirs
- https://pypi.org/project/platformdirs/

---

## New Dependencies Summary

| Package | Version | Platform | Purpose | Install |
|---------|---------|----------|---------|---------|
| `PySide6` | >=6.8,<7 | Both | Qt UI framework | `pip install PySide6` |
| `PySide6-WebEngine` | (matches PySide6) | Both | OAuth cookie capture (replaces WebKit2) | `pip install PySide6-WebEngine` |
| `platformdirs` | >=4.0 | Both | Cross-platform data/config paths | `pip install platformdirs` |
| `winrt-runtime` | >=2.3 | Windows only | WinRT base for SMTC | `pip install winrt-runtime` |
| `winrt-Windows.Media` | >=3.2 | Windows only | SMTC type definitions | `pip install winrt-Windows.Media` |
| `winrt-Windows.Media.Playback` | >=3.2 | Windows only | SMTC registration | `pip install winrt-Windows.Media.Playback` |

## Packages Leaving the Stack

| Package | Why Removed | Replacement |
|---------|-------------|-------------|
| `PyGObject` (GTK4/Libadwaita) | UI replaced by Qt | PySide6 |
| `dbus-python` | GTK/GLib loop dependent | PySide6.QtDBus |
| WebKit2Gtk | GTK-specific | PySide6-WebEngine |

## What NOT to Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Qt Multimedia | Lacks ICY metadata, HLS, yt-dlp URL support | Keep GStreamer directly |
| `requests` | Stdlib urllib still sufficient | urllib |
| `asyncio` for GStreamer bridge | Adds complexity; QTimer polling is simpler and sufficient | QTimer + `timed_pop(0)` |
| `appdirs` | Superseded and unmaintained | `platformdirs` |
| Briefcase | No GStreamer DLL handling | PyInstaller |
| Nuitka | Open issue with GStreamer/PyGObject | PyInstaller |
| `GLib.MainLoop` background thread | Fragile on Windows; not needed with QTimer bus poll | QTimer |

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| PySide6 6.8+ | Python 3.10-3.14 | Pin minor version in pyproject.toml |
| PyGObject 3.x | GStreamer 1.x via gi.repository | Must match installed GStreamer runtime version |
| winrt 3.x | Windows 10+ | Python 3.9+; requires Win10 build 1607+ for SMTC |
| PyInstaller 6.x | PySide6 6.x | Use pyinstaller-hooks-contrib for latest Qt hooks |

---

## Key Integration Points for Phase Planning

1. **Player.py rewrite is the critical path.** The GLib.idle_add → Qt signal migration and bus.add_signal_watch → QTimer polling change touches all playback feedback: ICY titles, EOS, errors, buffering. Phase this first.

2. **mpris.py becomes platform-conditional.** Linux: rewrite using PySide6.QtDBus. Windows: implement SMTC via winrt. Guard all D-Bus code with `if sys.platform == 'linux'`.

3. **constants.py path migration is low risk.** Replace hardcoded `~/.local/share/musicstreamer` with `platformdirs.user_data_dir()` before anything else — downstream code uses `DATA_DIR` consistently.

4. **WebEngine OAuth is deferrable.** The Twitch and Google OAuth dialogs can be ported last. Consider system-browser redirect as a simpler alternative that avoids the 130MB WebEngine dependency.

5. **Windows CI must have GStreamer on PATH.** Any automated Windows build/test must install GStreamer MSI and set `GSTREAMER_ROOT_X86_64` before running pytest or PyInstaller.

---

## Sources

| Source | Topic | Confidence |
|--------|-------|-----------|
| https://pypi.org/project/PySide6/ | Version 6.11.0, Python requirements | HIGH |
| https://www.pythonguis.com/faq/licensing-differences-between-pyqt6-and-pyside6/ | LGPL licensing personal app | HIGH |
| https://discourse.gstreamer.org/t/qt-gstreamer-event-loop-woes/5766 | Qt+GStreamer event loop | MEDIUM |
| https://gstreamer.freedesktop.org/documentation/gstreamer/gstbus.html | bus.timed_pop, add_signal_watch | HIGH |
| https://forum.qt.io/topic/104299/integration-with-glib-event-loop | QEventDispatcherGlib Linux behavior | MEDIUM |
| https://dev.to/liberifatali/setup-gstreamer-with-python-on-windows-59n3 | GStreamer Windows MSYS2 setup | MEDIUM |
| https://pyinstaller.org/en/v6.11.0/hooks-config.html | GStreamer hook include/exclude_plugins | HIGH |
| https://doc.qt.io/qtforpython-6/PySide6/QtWebEngineWidgets/index.html | QtWebEngineWidgets capability | HIGH |
| https://doc.qt.io/qt-6/qtwebengine-platform-notes.html | Windows WebEngine qt.conf requirement | HIGH |
| https://doc.qt.io/qtforpython-6/PySide6/QtDBus/index.html | QtDBus server mode | MEDIUM |
| https://pypi.org/project/winrt-Windows.Media.Control/ | winrt package Python bindings | MEDIUM |
| https://learn.microsoft.com/en-us/uwp/api/windows.media.systemmediatransportcontrols | SMTC API | HIGH |
| https://github.com/tox-dev/platformdirs | platformdirs cross-platform paths | HIGH |

---

*Stack research for: MusicStreamer v2.0 OS-Agnostic Qt/PySide6 Port*
*Researched: 2026-04-10*
