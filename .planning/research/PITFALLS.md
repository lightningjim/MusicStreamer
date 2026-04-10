# Pitfalls Research — MusicStreamer v2.0 OS-Agnostic Port

**Domain:** Qt/PySide6 port of a Linux GNOME Python desktop app (GTK4/Libadwaita + GStreamer) to Linux + Windows
**Researched:** 2026-04-10
**Confidence:** HIGH (GStreamer/Qt threading patterns, subprocess Windows flags, PyInstaller AV) | MEDIUM (WebEngine cookie store, Windows ACL, souphttpsrc SSL bundling specifics)

---

## Critical Pitfalls

### Pitfall 1: GStreamer Bus Callbacks Delivered on Wrong Thread

**What goes wrong:**
v1.5 uses `GLib.idle_add()` to marshal GStreamer bus messages to the GTK main thread. When GTK is gone, there is no GMainLoop to pump. `bus.add_signal_watch()` — which hooks into the GLib main context — silently delivers nothing. ICY track titles and EOS/ERROR events stop working with no crash or error log.

**Why it happens:**
`bus.add_signal_watch()` attaches to the default GLib main context. The Qt event loop does not pump that context. The Qt event loop does not pump a GMainLoop.

**How to avoid:**
Use `bus.enable_sync_message_emission()` + connect to the `sync-message` signal, then immediately re-emit as a Qt signal across a queued connection. The GStreamer sync handler runs on the streaming thread; a queued Qt signal delivers to the main thread slot automatically.

```python
self._bus = self._pipeline.get_bus()
self._bus.enable_sync_message_emission()
self._bus.connect("sync-message", self._on_gst_message)

def _on_gst_message(self, bus, msg):
    # Runs on GStreamer streaming thread — emit Qt signal only, no widget access
    self.gst_message.emit(msg)  # auto-queued to main thread

# In main window (main thread slot):
@Slot(object)
def _handle_gst_message(self, msg): ...
```

Do NOT call any `QWidget` method directly from inside `_on_gst_message`.

**Warning signs:**
- ICY track titles never update after porting
- Stream errors and EOS events not caught; app hangs at stream end
- Works with a dummy GMainLoop running but not in production

**Phase to address:** scaffold — establish this pattern in the player module before any UI code touches the bus.

---

### Pitfall 2: GStreamer Plugin Path Not Set in PyInstaller Bundle (Windows)

**What goes wrong:**
On Windows, GStreamer looks for plugins under `%GSTREAMER_ROOT%\lib\gstreamer-1.0`. When bundled with PyInstaller, that path does not exist relative to the exe. Result: `gst.parse_launch()` finds zero elements and pipelines fail immediately with cryptic errors like `no element "playbin3"`.

**Why it happens:**
On Linux, GStreamer is a system package with compile-time plugin paths baked in. On Windows, the GStreamer installer sets `GST_PLUGIN_PATH` in the system environment, but that variable is absent in a PyInstaller bundle unless explicitly set at app startup.

**How to avoid:**
At app startup, before `Gst.init()`, detect a PyInstaller bundle and set the environment:

```python
import sys, os
if getattr(sys, 'frozen', False):
    bundle_dir = sys._MEIPASS
    os.environ['GST_PLUGIN_PATH'] = os.path.join(bundle_dir, 'gst-plugins')
    os.environ['GST_PLUGIN_SCANNER'] = ''   # disable scanner; all plugins collected
    os.environ['GST_REGISTRY'] = os.path.join(bundle_dir, 'registry.bin')
```

In the `.spec` file, add a `Tree()` block collecting the required plugin DLLs: `playback`, `soup`, `libav`, `audioconvert`, `autodetect`, `volume`, `typefindfunctions`.

**Warning signs:**
- `no element "playbin3"` on Windows packaged build
- Works in development (system GStreamer installed) but fails after packaging
- First launch fails; second launch works (registry rebuilt) — classic registry race

**Phase to address:** packaging — required quality gate before calling the Windows bundle done.

---

### Pitfall 3: souphttpsrc SSL Failure on Windows (Missing glib-networking)

**What goes wrong:**
HTTPS radio stream URLs fail silently or with `TLS/SSL support not available; install glib-networking`. The `souphttpsrc` element delegates TLS to `glib-networking` (`libgiognutls.dll` on Windows). This DLL is not auto-collected by PyInstaller hooks and may be absent from minimal GStreamer runtime installations.

**Why it happens:**
On Linux, `glib-networking` is a system package installed alongside GLib. On Windows, it ships in the GStreamer MSVC runtime as a separate DLL. PyInstaller's GStreamer hook does not scan it as a Python import dependency.

**How to avoid:**
- Use the GStreamer MSVC runtime installer — it includes `libgiognutls.dll` and the CA cert bundle.
- In the PyInstaller `.spec`, explicitly add `libgiognutls.dll` and `lib\gio\modules\` to `binaries`.
- Test an HTTPS stream URL (e.g., a `https://` SomaFM endpoint) on the freshly packaged build as an explicit quality gate.
- Fallback: per-station `ssl-strict=false` property on `souphttpsrc` as a last resort for debugging — never as a production default.

**Warning signs:**
- HTTP `http://` streams work; HTTPS `https://` streams fail immediately
- Error log: `TLS/SSL support not available`

**Phase to address:** packaging.

---

### Pitfall 4: subprocess Console Window Flash on Windows (yt-dlp, streamlink, mpv)

**What goes wrong:**
Every call to `yt-dlp`, `streamlink`, or `mpv` as a subprocess pops a CMD window for a fraction of a second. Highly visible and makes the app look broken.

**Why it happens:**
On Windows, `subprocess.Popen` creates a console window for console-subsystem executables unless `creationflags=subprocess.CREATE_NO_WINDOW` is passed.

**How to avoid:**
Centralize all subprocess calls behind a helper:

```python
import subprocess, sys

def _popen(args, **kwargs):
    if sys.platform == "win32":
        kwargs.setdefault("creationflags", subprocess.CREATE_NO_WINDOW)
    return subprocess.Popen(args, **kwargs)
```

Also set `stdin=subprocess.DEVNULL` on all fire-and-forget subprocesses to prevent the child from blocking on stdin.

Never use `shell=True` on Windows with any user-controlled content — use list args and the helper.

**Warning signs:**
- Black CMD window flashes during stream start on Windows
- No crash, no error — purely a UX artifact

**Phase to address:** platform — part of the Windows subprocess compatibility layer, built before the first YouTube/Twitch playback test.

---

### Pitfall 5: Subprocess Pipe Deadlock (yt-dlp stdout + stderr)

**What goes wrong:**
`subprocess.Popen` with `stdout=PIPE, stderr=PIPE` deadlocks when the child writes enough to fill the OS pipe buffer (~64 KB on Windows) before the parent reads it. yt-dlp with `--verbose` or cookie auth can produce megabytes of stderr. The calling thread hangs indefinitely.

**Why it happens:**
Child fills `stderr`, blocks. Parent is blocked on `stdout.read()`. Neither makes progress. This is a known, documented Python subprocess issue on Windows specifically.

**How to avoid:**
Use `subprocess.run(capture_output=True, timeout=30)` for all one-shot yt-dlp URL extractions. For long-running processes (mpv), redirect stderr to `subprocess.DEVNULL` or a rotating log file — never pipe it unless actively consuming it in a separate thread.

```python
result = subprocess.run(
    ["yt-dlp", "--get-url", url],
    capture_output=True, text=True, timeout=30,
    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
)
```

**Warning signs:**
- App freezes during YouTube stream resolution on Windows
- Works with short URLs, hangs with authenticated/playlist URLs
- No timeout fires (no timeout was set)

**Phase to address:** platform — audit all subprocess calls during Windows compatibility phase.

---

### Pitfall 6: Hard-Coded `~/.local/share/musicstreamer` Path Breaks on Windows

**What goes wrong:**
Every module that constructs `~/.local/share/musicstreamer/` puts data in a non-standard Windows location that users can't find via Explorer. Worse: `os.makedirs` may fail if the intermediate `.local/share` path doesn't exist on Windows by default.

**Why it happens:**
XDG base directory conventions are Linux-only. `os.path.expanduser("~/.local/...")` technically works on Windows but produces a non-conventional path.

**How to avoid:**
Compute `DATA_DIR` once at startup using `QStandardPaths`:

```python
from PySide6.QtCore import QStandardPaths, QCoreApplication
QCoreApplication.setOrganizationName("")
QCoreApplication.setApplicationName("MusicStreamer")
DATA_DIR = QStandardPaths.writableLocation(
    QStandardPaths.StandardLocation.AppLocalDataLocation
)
# Linux: ~/.local/share/MusicStreamer
# Windows: C:\Users\<user>\AppData\Roaming\MusicStreamer
```

Store this in `constants.py` and use `DATA_DIR` everywhere — never construct the path inline. On Linux, if the old `~/.local/share/musicstreamer` exists and the QStandardPaths location is new/empty, migrate it on first run.

Note: `QCoreApplication` must be constructed before `QStandardPaths.writableLocation` is called.

**Warning signs:**
- Cookie file not found by yt-dlp on Windows (absolute path baked into the call)
- Database created at wrong path; settings not persisted between sessions

**Phase to address:** scaffold — zero-day decision; every file path in the codebase must use `DATA_DIR`.

---

### Pitfall 7: QObject C++ Lifetime vs. Python GC (`RuntimeError: Internal C++ object already deleted`)

**What goes wrong:**
Qt destroys the C++ object (e.g., when a dialog closes and destroys its children) while Python still holds a reference. Any subsequent attribute access raises `RuntimeError: Internal C++ object already deleted`. This is the most common PySide6 crash and has no GTK equivalent — GTK widgets are Python-owned; Qt widgets are C++-owned.

**Why it happens:**
When a `QDialog` closes without `exec()` keeping it alive, Qt can delete it and all children. A GStreamer callback that was running while the dialog was open may try to update a now-dead label.

**How to avoid:**
- Always give every widget a parent (`parent=` constructor arg) or store as `self.widget`. Never create widgets in local scope without parenting.
- Dialogs: use `dialog.exec()` (blocks) or store as `self._dialog` on the parent window.
- Connect to `dialog.finished` or `dialog.destroyed` to clear the Python reference.
- GStreamer callbacks that update UI: check `sip.isdeleted(widget)` or use a `try/except RuntimeError` guard. Better: the callback only emits a Qt signal; the slot in the main window checks whether the widget is still live.

**Warning signs:**
- `RuntimeError: Internal C++ object already deleted` in stderr
- Crash when re-opening a dialog after it was previously dismissed
- Crash after a dialog is dismissed while a background thread is still running

**Phase to address:** port — apply as a code review gate on every dialog and every GStreamer callback that references UI widgets.

---

### Pitfall 8: GTK CSS → QSS — Semantics Are Completely Different

**What goes wrong:**
The v1.5 accent color system writes GTK CSS via `Gtk.CssProvider` at `PRIORITY_USER`. QSS looks syntactically similar but behaves differently in ways that matter:

- QSS selectors use Qt widget class names (`QLabel`, `QPushButton`) not element names (`label`, `button`).
- No cascade priority system — `QApplication.setStyleSheet()` is global; setting it on a widget overrides global for that widget's subtree only.
- No CSS custom properties (`--accent-bg-color`). Every accent token must be string-interpolated at generation time.
- No `@define-color`. No `:root`. Selectors map to widget types, not DOM elements.
- `border-radius` on a `QWidget` requires `background-color` also set — otherwise no visual effect.

**How to avoid:**
Re-implement the accent system from scratch for Qt. Do not port the GTK CSS string. Generate a minimal QSS snippet with hardcoded hex values. Use Qt's `QPalette` API for semantic color roles where possible — palette changes propagate correctly; QSS string patches do not.

**Warning signs:**
- QSS applied but no visible change
- `border-radius` works on some widgets, not others
- Accent color leaks into unintended widgets

**Phase to address:** port — accent color is a re-implement, not a translate.

---

### Pitfall 9: Libadwaita Compound Widgets Have No Qt Equivalent — Map First

**What goes wrong:**
`Adw.ExpanderRow`, `Adw.ActionRow`, `Adw.SwitchRow`, `Adw.ComboRow`, and `Adw.ToggleGroup` are compound Libadwaita widgets with built-in spacing, icon slots, subtitles, and activation semantics. Developers look for 1:1 Qt replacements, find none, and bolt together `QFrame` + `QHBoxLayout` + `QLabel` combos that don't match the interaction model.

**How to avoid:**
Establish the widget mapping table before writing a line of Qt UI code:

| Libadwaita | Qt replacement |
|-----------|----------------|
| `Adw.ExpanderRow` (provider groups) | Custom `QWidget` with expand/collapse toggle + hidden child `QListWidget` |
| `Adw.ActionRow` (station rows) | Custom `QWidget` set via `QListWidget.setItemWidget` |
| `Adw.SwitchRow` | `QWidget` + `QCheckBox` in a form layout |
| `Adw.ComboRow` | `QComboBox` |
| `Adw.ToggleGroup` (Stations/Favorites) | Exclusive `QButtonGroup` with `QPushButton` |
| `Adw.Toast` | Custom overlay `QLabel` with `QTimer` auto-dismiss, or `QStatusBar` |
| `Adw.FlowBox` chip strip | Qt's `FlowLayout` example, or `QScrollArea` with wrapping `QWidget` |
| `Adw.Dialog` | `QDialog` |
| `Adw.HeaderBar` | `QMenuBar` + `QToolBar` or just `QMenuBar` |

Accept that visual output will look different from v1.5 on GNOME. This is expected for a cross-platform port.

**Warning signs:**
- Nested `QFrame` soup trying to replicate `Adw.ActionRow`
- Expand/collapse state not persisting across filter changes (re-learned the v1.2 lesson)

**Phase to address:** port — decide the mapping table during scaffold; implement during port.

---

### Pitfall 10: Daemon Thread + `GLib.idle_add` — Wrong Migration to QThread

**What goes wrong:**
v1.5 uses `threading.Thread(daemon=True)` + `GLib.idle_add(callback)` for all background I/O. The naive Qt port subclasses `QThread` and calls `QWidget` methods from `run()` — crash. A slightly less naive port uses `moveToThread` but puts the worker in the wrong thread (QThread lives in the spawning thread, not the thread it manages).

**How to avoid:**
Use the **worker-object + `moveToThread`** pattern:

```python
class FetchWorker(QObject):
    result_ready = Signal(str)

    def fetch(self, url):        # runs in worker thread via Signal invocation
        data = do_blocking_work(url)
        self.result_ready.emit(data)  # queued to main thread slot

# Setup:
self._worker = FetchWorker()       # no parent — required for moveToThread
self._thread = QThread()
self._worker.moveToThread(self._thread)
self._thread.start()
self._worker.result_ready.connect(self._on_result)  # queued connection
```

Key rules:
- `moveToThread` fails if the worker has a parent — never set parent before moving.
- The `QThread` object lives in the spawning thread; do not access worker attributes directly from the main thread after moving.
- `GLib.idle_add` is replaced by emitting a Qt signal — queued connection delivers to the main thread slot.
- For one-shot tasks, `QThreadPool` + `QRunnable` is simpler and avoids lifetime management.

**Warning signs:**
- `QObject: Cannot move to target thread` warning in stderr
- Random crashes during import or thumbnail fetch
- UI updates that work 90% of the time and crash 10%

**Phase to address:** scaffold — establish the threading pattern before any feature porting. Every background worker must use it.

---

### Pitfall 11: WebKit2Gtk → QtWebEngine for Twitch OAuth — Different Cookie API

**What goes wrong:**
v1.5 captures the Twitch auth token by spawning a WebKit2 subprocess, intercepting the `access_token` cookie from the WebKit2 cookie store, and writing it to `TWITCH_TOKEN_PATH`. QtWebEngine uses a Chromium-based `QWebEngineCookieStore` with an async API — cookies are delivered via the `cookieAdded` signal, not synchronously readable after navigation.

Additionally, QtWebEngine adds ~150MB to a packaged build and requires a separate `QtWebEngineProcess.exe` bundled alongside the app.

**How to avoid:**
Keep the subprocess isolation pattern. Spawn a minimal Qt script (`oauth_helper.py`) that embeds `QWebEngineView`, connects to `profile.cookieStore().cookieAdded`, filters for `access_token`, writes the token to a temp file, and exits. The main app reads the temp file. This isolates the QtWebEngine weight to a subprocess rather than importing it into the main process.

If QtWebEngine size is prohibitive: explore the `webbrowser.open()` + local redirect server pattern (OAuth PKCE flow) as an alternative that requires no embedded browser.

**Warning signs:**
- OAuth window opens but token is never captured
- `QtWebEngineProcess.exe` not found in packaged build
- Main process imports `QtWebEngineWidgets` and takes 3 seconds to start

**Phase to address:** platform — Twitch OAuth is platform-specific. Address as a dedicated task in the Windows auth/cookies phase.

---

### Pitfall 12: `os.chmod(0o600)` Is a No-Op on Windows

**What goes wrong:**
v1.5 sets `0o600` permissions on `cookies.txt` and `TWITCH_TOKEN_PATH` via `os.chmod()`. On Windows, `os.chmod()` is silently ignored for all permission bits except read-only. The files are created but are readable by any local user — no exception is raised.

**Why it happens:**
Windows uses ACLs, not POSIX permission bits. Python's `os.chmod()` on Windows only honors the "read-only" attribute.

**How to avoid:**
Wrap in a platform check:

```python
import sys, os, stat
def set_private_permissions(path: str) -> None:
    if sys.platform != "win32":
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    # Windows: os.chmod is a no-op for ownership; document gap explicitly
    # For a single-user personal app this is acceptable risk
```

Do not add a `pywin32` ACL dependency for a personal single-user app. Document the gap in a code comment and move on.

**Warning signs:**
- Security scanner flags world-readable credential files on Windows

**Phase to address:** platform — document during Windows compatibility review.

---

### Pitfall 13: PyInstaller GStreamer Hook Does Not Auto-Collect Native Plugin DLLs

**What goes wrong:**
PyInstaller's `gi.repository.Gst` hook collects Python bindings but does NOT auto-collect native GStreamer plugin DLLs. The packaged exe starts but has no audio — `playbin3` has no elements available.

**Why it happens:**
GStreamer plugins are native DLLs in `gstreamer-1.0/` that PyInstaller does not discover as Python imports. The hook (PyInstaller 5.6+) provides `include_plugins` / `exclude_plugins` but requires explicit enumeration.

**How to avoid:**
In `.spec`, explicitly collect the required plugin DLLs:

```python
gst_plugins = r"C:\gstreamer\1.0\msvc_x86_64\lib\gstreamer-1.0"
a.datas += Tree(gst_plugins, prefix='gst-plugins')
```

Required plugins: `playback`, `soup`, `libav`, `audioconvert`, `autodetect`, `volume`, `typefindfunctions`. Test the packaged build against both HTTP and HTTPS streams before declaring packaging done.

**Warning signs:**
- Packaged exe starts, UI appears, but audio never plays
- `gst-inspect-1.0 playbin3` returns nothing inside the bundle

**Phase to address:** packaging — explicit quality gate.

---

### Pitfall 14: Antivirus False Positives and SmartScreen on Unsigned PyInstaller Exe

**What goes wrong:**
PyInstaller bundles the interpreter and extracts to a temp dir at runtime — behavior matching common malware packers. Windows Defender and third-party AV products flag unsigned PyInstaller executables as `Trojan.GenericKD`. SmartScreen blocks launch with "Windows protected your PC."

**How to avoid:**
- Use `--onedir` mode, not `--onefile`. The extraction behavior that triggers AV heuristics is `--onefile` only.
- Do NOT use UPX compression (`--no-upx`). UPX-compressed Python exes have extremely high AV false-positive rates.
- For personal use: document that users must click "Run Anyway" on first launch. For distribution: get a code-signing certificate (EV cert = immediate SmartScreen reputation).
- Build the PyInstaller bootloader from source — different binary hash reduces detection rate.

**Warning signs:**
- Windows Defender quarantines the exe on first launch on a clean VM
- SmartScreen "unknown publisher" dialog on first run

**Phase to address:** packaging — test on a clean Windows VM with Defender enabled before declaring packaging done.

---

### Pitfall 15: "Improve While Porting" Scope Creep Causes Feature Drift

**What goes wrong:**
Every widget re-implementation is a temptation: "while I'm rewriting the station list, I'll also restructure to use `QAbstractListModel`" or "Qt's model/view is more elegant so I'll refactor the data layer too." These improvements compound, the port takes 3x as long, bugs are introduced in areas that weren't broken, and v1.5 behavior is no longer the baseline.

**Why it happens:**
Port work touches every UI file. Qt idioms (model/view, `QAbstractListModel`) suggest architectural refactors not needed with GTK. Developers naturally improve as they touch code.

**How to avoid:**
- Establish a written "port-only" rule before the first phase: every plan must reference a specific v1.5 behavior as the target and say "match this exactly."
- Create a feature-parity checklist from v1.5 requirements before writing a line of Qt code. Each checkbox maps to a testable behavior.
- New improvements, architecture changes, Qt-idiomatic refactors go into a labeled backlog — not into port phases.
- Phase plans during the port must include: "No new behavior introduced in this phase."
- The only new behavior in v2.0 is: `QStandardPaths` path migration, manual settings export/import, cross-platform media keys, and Windows installer.

**Warning signs:**
- Phase plan descriptions contain "also improved" or "also refactored"
- Test count drops (old behavior tests deleted rather than adapted)
- Phase estimates doubling mid-execution

**Phase to address:** all phases — process rule, not a code fix. Enforce at the plan-writing stage.

---

### Pitfall 16: pytest Tests That Use Xvfb Won't Run on Windows CI

**What goes wrong:**
GTK widget tests require a display — handled on Linux CI via Xvfb. On Windows there is no X11. Any test that imports GTK (even indirectly) crashes the test suite at import time. When Qt widget tests are added naively (without `pytest-qt`), they fail on headless CI too.

**How to avoid:**
- Use `pytest-qt` for all Qt widget tests. It automatically sets `QT_QPA_PLATFORM=offscreen` when no display is available — headless and cross-platform.
- Set `QT_QPA_PLATFORM=offscreen` in CI environment config as belt-and-suspenders.
- All GStreamer and subprocess calls in tests remain monkeypatched — no real media pipeline in tests.
- Do not create real widget objects in tests without `qtbot` — use `qtbot.addWidget()` for lifecycle management.

**Warning signs:**
- `could not connect to display` on Windows CI
- Tests pass on Linux dev machine, import-error on Windows

**Phase to address:** scaffold — establish `pytest-qt` + offscreen before writing any Qt widget test.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Keep `threading.Thread` alongside `QThread` | Avoids full threading refactor | Two threading systems; non-Qt threads can't emit Qt signals safely | Never — pick one |
| `shell=True` on Windows subprocess | Avoids path lookup complexity | Security risk; hides `CREATE_NO_WINDOW` | Never |
| Hardcode plugin list in PyInstaller spec | Fast to ship | Breaks when GStreamer version changes | Acceptable if version-pinned in requirements |
| Skip `os.chmod` on Windows with a comment | Avoids `pywin32` dependency | Credential files world-readable | Acceptable for single-user personal app |
| Keep subprocess OAuth pattern (no in-process WebEngine) | Avoids 150MB WebEngine dep in main process | Subprocess spawning is fragile | Acceptable — isolation is good architecture |
| Port to `QListWidget` + `setItemWidget` instead of `QAbstractListModel` | Faster to implement, matches GTK flat-list mental model | Harder to filter/sort at scale | Acceptable for 50–200 station library |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| GStreamer + Qt event loop | `bus.add_signal_watch()` with no GMainLoop | `enable_sync_message_emission()` + emit Qt signal from sync handler |
| GStreamer + PyInstaller | Rely on auto-collection for native plugin DLLs | Explicit `Tree()` in spec + `GST_PLUGIN_PATH` at startup |
| GStreamer + Windows SSL | No `libgiognutls.dll` in bundle | Explicitly collect DLL + test HTTPS stream on packaged build |
| yt-dlp subprocess | `stdout=PIPE, stderr=PIPE` no timeout | `subprocess.run(capture_output=True, timeout=30)` |
| mpv subprocess | stderr piped for logging | Redirect to `DEVNULL` or rotating log file |
| `QStandardPaths` | Called before `QCoreApplication` constructed | Construct app with org/name first; then call `writableLocation` |
| Twitch OAuth + WebEngine | Import `QtWebEngineWidgets` in main process | Subprocess isolation — spawn `oauth_helper.py` |

---

## "Looks Done But Isn't" Checklist

- [ ] **GStreamer bus:** ICY titles update after port — not just "pipeline plays"
- [ ] **Windows subprocess:** No CMD flash on yt-dlp, streamlink, mpv calls
- [ ] **HTTPS streams:** HTTPS URL plays in packaged build (not just HTTP)
- [ ] **Data paths:** `DATA_DIR` used in every file path — no `~/.local` literals remain
- [ ] **QStandardPaths migration:** Old Linux path migrated on upgrade if it exists and new path is empty
- [ ] **Threading:** No `QObject: Cannot move to target thread` warnings in stderr during import
- [ ] **Widget lifetime:** 10-minute smoke test with no `RuntimeError: Internal C++ object deleted`
- [ ] **AV false positive:** Packaged exe runs on clean Windows VM with Defender enabled
- [ ] **Accent color:** Changes apply to all targeted widgets, not just some
- [ ] **pytest-qt:** All tests pass headless on both Linux and Windows

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| GStreamer bus on wrong thread | scaffold | ICY titles update; EOS caught in integration test |
| GST_PLUGIN_PATH missing | packaging | Fresh Windows VM: stream plays within 10s |
| souphttpsrc SSL missing | packaging | HTTPS SomaFM stream plays in packaged build |
| Console window flash | platform | No CMD flash during stream start (manual test) |
| Pipe deadlock | platform | yt-dlp `--verbose` call does not hang; 30s timeout fires |
| Hard-coded data paths | scaffold | `DATA_DIR` constant; no `~/.local` literals; `grep` clean |
| C++ object deleted crash | port | No RuntimeError in 10-min smoke; dialog open/close cycle passes |
| GTK CSS vs QSS | port | Accent color applies to all targeted widget types |
| Libadwaita widget mapping | port | Mapping table reviewed before first UI file written |
| Thread migration | scaffold | No `Cannot move to target thread` warnings; no import crash |
| WebEngine OAuth | platform | Twitch token captured on Windows without in-process WebEngine |
| chmod no-op | platform | Documented in code comment; no exception on Windows |
| PyInstaller plugins missing | packaging | Packaged exe plays audio (HTTP + HTTPS) |
| AV false positives | packaging | Clean VM with Defender: exe runs without quarantine |
| Scope creep | all phases | Phase plans state "no new behavior"; parity checklist gates each phase |
| Xvfb/display in tests | scaffold | `pytest-qt` + offscreen; full suite passes on Windows CI |

---

## Sources

- [GStreamer GstBus documentation](https://gstreamer.freedesktop.org/documentation/gstreamer/gstbus.html)
- [Qt Forum: Howto push GST thread into Qt Main Thread](https://forum.qt.io/topic/132596/howto-push-gst-thread-into-qt-main-thread)
- [GStreamer Discourse: Qt GStreamer Event Loop Woes](https://discourse.gstreamer.org/t/qt-gstreamer-event-loop-woes/5766)
- [GStreamer souphttpsrc SSL issue #451](https://gitlab.freedesktop.org/gstreamer/gst-plugins-good/-/issues/451)
- [GStreamer installing on Windows](https://gstreamer.freedesktop.org/documentation/installing/on-windows.html)
- [PyInstaller/Kivy GStreamer bundling issue #6126](https://github.com/kivy/kivy/issues/6126)
- [yt-dlp Windows GUI console window issue #1251](https://github.com/yt-dlp/yt-dlp/issues/1251)
- [Python subprocess deadlock CPython issue #14872](https://bugs.python.org/issue14872)
- [PyInstaller AV false positives guide](https://www.pythonguis.com/faq/problems-with-antivirus-software-and-pyinstaller/)
- [PyInstaller SmartScreen signing issue #6747](https://github.com/pyinstaller/pyinstaller/issues/6747)
- [QStandardPaths Qt for Python docs](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QStandardPaths.html)
- [PySide6 QThread multithreading guide](https://www.pythonguis.com/tutorials/multithreading-pyside6-applications-qthreadpool/)
- [QThread correct usage](https://www.haccks.com/posts/how-to-use-qthread-correctly-p1/)
- [QWebEngineCookieStore Qt for Python docs](https://doc.qt.io/qtforpython-6/PySide6/QtWebEngineCore/QWebEngineCookieStore.html)
- [Porting from Qt WebKit to Qt WebEngine](https://doc.qt.io/qtforpython-6.5/overviews/qtwebenginewidgets-qtwebkitportingguide.html)
- [oschmod — cross-platform chmod alternative](https://pypi.org/project/oschmod/)
- [pytest-qt troubleshooting / offscreen platform](https://pytest-qt.readthedocs.io/en/latest/troubleshooting.html)

---

## Archived — v1.4 Pitfalls (GTK4/GStreamer)

Prior pitfall research for v1.4 (GStreamer buffer tuning, AudioAddict art, accent color) is archived below for reference. These pitfalls are already addressed in v1.5 shipped code.

<details>
<summary>Expand v1.4 pitfalls (archived)</summary>

### P1: Buffer Tuning Delays ICY Metadata Delivery
Set `buffer-duration` ≤5s. Prefer `buffer-duration` over `buffer-size`. Validate time-to-first-TAG-message.

### P2: `souphttpsrc` Properties Not Accessible at Pipeline Construction
Connect to `source-setup` signal on `playbin3`. Do not call `get_by_name("source")` before `READY` state.

### P3: AA Logo Fetch Blocks Import Worker
Decouple logo fetch from insert loop. Use `ThreadPoolExecutor` post-insert pass.

### P4: AA API Logo URL Format Undocumented
Inspect raw JSON first. Normalize URLs. Treat missing logos as non-fatal.

### P5: AA URL Detection False Positives
Gate detection on explicit `NETWORKS` domain list from `aa_import.py`.

### P6: 16:9 Slot Breaks Square iTunes Art
Use `ContentFit.CONTAIN`; keep slot `160x160`. Adaptive slot complicates the panel layout.

### P7: Changing `cover_stack` Size Reflows Panel
Test at min window size after any dimension change.

### P8: CSS Variable Scope — `--accent-bg-color` Must Be on `:root`
Use `:root` selector + `PRIORITY_APPLICATION`.

### P9: Invalid Hex Silent No-Op
Validate hex in Python (`re.fullmatch`) before passing to GTK CSS provider.

### P10: GNOME 47+ System Accent Overwrites App Override
Use `PRIORITY_APPLICATION` (600). Reload provider on every change, not just startup.

</details>

---

*Pitfalls research for: MusicStreamer v2.0 Qt/PySide6 port to Linux + Windows*
*Researched: 2026-04-10*
