# Phase 61: Linux App Display Name in WM Dialogs - Research

**Researched:** 2026-05-05
**Domain:** Linux desktop integration — Qt6/X11 WM_CLASS, freedesktop `.desktop` lookup, GNOME Shell window-to-app matching, XDG self-install on first launch
**Confidence:** HIGH

## Summary

GNOME Shell — including the force-quit dialog, Activities/Alt-Tab, and notifications — resolves a window's "friendly name" by walking a documented, case-sensitive matching chain from the X11 `WM_CLASS` property (or Wayland `app_id`) into a `.desktop` file in the XDG search path, then reading that file's `Name=` field. Today that lookup fails on Kyle's rig for two compounding reasons: (1) the in-process app id is the placeholder `org.example.MusicStreamer`, which has no matching `.desktop` file anywhere; (2) the bundled `org.example.MusicStreamer.desktop` lives only at the repo root, not in any XDG-discoverable location. A stale copy of that file already sits in `~/.local/share/applications/` from an earlier dev experiment, but with `Icon=org.lightningjim.MusicStreamer` already declared inside it — meaning the icon-half of the install was already done by hand at some point (icons are present in 64/128/256 hicolor buckets). The phase needs to (a) rename the placeholder to `org.lightningjim.MusicStreamer` everywhere, single-sourced through `constants.APP_ID`; (b) ship a self-install routine that drops the renamed `.desktop` file (+ icons, idempotent) into `~/.local/share/`; (c) add `setApplicationDisplayName("MusicStreamer")` for belt-and-suspenders coverage of any in-process Qt surface; and (d) capture before/after diagnostic readouts on Kyle's rig per the Phase 56 convention.

The Qt6 source for the X11 `WM_CLASS` derivation is unambiguous: the **class** half comes from `QCoreApplication::applicationName()` (already `"MusicStreamer"` in current code), and the **instance** half comes from `-name` argv → `RESOURCE_NAME` env var → argv[0] basename — `setDesktopFileName` does NOT influence either half. `setDesktopFileName` instead populates `_KDE_NET_WM_DESKTOP_FILE` and `_GTK_APPLICATION_ID` (which GNOME Shell reads as a higher-priority lookup hint than `WM_CLASS` matching), and on Wayland is the canonical way to set `xdg-shell` `app_id`. The GNOME match algorithm tries `WM_CLASS class → StartupWMClass`, then `WM_CLASS instance → StartupWMClass`, then `WM_CLASS class → .desktop basename`, then `WM_CLASS instance → .desktop basename`, all case-sensitive. With `setApplicationName("MusicStreamer")` already in place, **the WM_CLASS class string is already "MusicStreamer", which matches `StartupWMClass=MusicStreamer` in the bundled `.desktop` file by construction**. The phase's only blocker is shipping that file under the renamed basename to a discoverable location; no `-name` argv injection is needed.

**Primary recommendation:** Rename `constants.APP_ID` to `org.lightningjim.MusicStreamer` and propagate through three call sites (`__main__.py::_set_windows_aumid` default arg, `__main__.py::_run_gui::setDesktopFileName`, `mpris2.py::DesktopEntry`); add `app.setApplicationDisplayName("MusicStreamer")`; rename the bundled `.desktop` file to `org.lightningjim.MusicStreamer.desktop` and audit/fix the `Categories=` field (current value `Categories=Audio;Music;Network;` is malformed — `Audio` is not a registered freedesktop main category, should be `AudioVideo`); ship a new pure-Python self-install module (`musicstreamer/desktop_install.py`) called from `__main__.py::_run_gui` between `Gst.init()` and `migration.run_migration()`, guarded by an idempotency marker (`~/.local/share/musicstreamer/.desktop-installed-v1`) per the established `migration.py` pattern; install icon at the 256×256 hicolor bucket (the GNOME default); run `update-desktop-database` and `gtk-update-icon-cache` best-effort. Also fix the **third drift site found this research: `Makefile` lines 5–6 + 32–33 + 43** which still reference the old basename — these were missed in CONTEXT.md's call-site enumeration. The diagnose-first artifact (`61-DIAGNOSTIC-LOG.md`) is a thin wrapper around the agreed command set; expected outcome is to confirm the two known-broken conditions and document the post-fix readout.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| App ID single source of truth | Module: `musicstreamer/constants.py` (`APP_ID`) | — | One literal, every consumer reads it; existing PEP 562 `__getattr__` shim convention already establishes constants.py as the project's central-string anchor |
| Qt application identity wiring | Process-startup: `musicstreamer/__main__.py::_run_gui` | — | `setApplicationName` / `setApplicationDisplayName` / `setDesktopFileName` are QGuiApplication APIs that must run BEFORE any window is created; same ordering constraint as `_set_windows_aumid` |
| Windows AUMID propagation | OS-API: `musicstreamer/__main__.py::_set_windows_aumid` | — | Already in place; this phase swaps the hardcoded default for `constants.APP_ID` read |
| MPRIS DesktopEntry property | D-Bus adaptor: `musicstreamer/media_keys/mpris2.py::_MprisRootAdaptor.DesktopEntry` | — | Property is a one-line getter; only the literal returned changes |
| `.desktop` file authoring | Repo asset: `org.lightningjim.MusicStreamer.desktop` (renamed from `org.example.*`) | — | Static text content; the rename is mechanical |
| `.desktop` file install | Module: `musicstreamer/desktop_install.py` (NEW — Claude's discretion per CONTEXT.md) | — | Pure-Python file copy + idempotency marker; no Qt or GLib coupling, unit-testable with `tmp_path` |
| Icon install | Same module | — | Sibling concern; same install-marker semantics |
| Icon cache / desktop database refresh | Best-effort subprocess: `update-desktop-database` + `gtk-update-icon-cache` (D-13) | — | Wrapped in try/except; failure does not block app startup |
| WM_CLASS / app_id resolution | OS-shell: GNOME Shell window-tracker (consumes `WM_CLASS` on X11, `app_id` on Wayland, `_GTK_APPLICATION_ID` on either) | — | Shell-mediated; project never ships any code here. The lever is "is the renamed `.desktop` file findable in the XDG path with matching `StartupWMClass`" |
| Diagnostic readback | OS-tooling: `xprop` + `xdotool` + `ls` + `gnome-shell --version` | — | One-shot UAT artifact (`61-DIAGNOSTIC-LOG.md`); never shipped as code |

**Interpretation:** No tier crossings; one new pure-Python module (`desktop_install.py`) plus one-line edits to three existing files (`constants.py`, `__main__.py`, `mpris2.py`) plus one renamed asset (`.desktop`) plus one Makefile cleanup. Mirrors the Phase 56 shape exactly: pure helper + one-line wire-in + diagnostic artifact + UAT.

## User Constraints (from CONTEXT.md)

### Locked Decisions

**App ID branding (Area 1):**
- **D-01:** Reverse-DNS app ID is `org.lightningjim.MusicStreamer`. Same string as the Phase 56 Windows AUMID.
- **D-02:** `musicstreamer.constants.APP_ID` is the single source of truth. All call sites read from it (`__main__.py::_run_gui`, `__main__.py::_set_windows_aumid`, `media_keys/mpris2.py::DesktopEntry`).
- **D-03:** Rename bundled `.desktop` file in lockstep: `org.example.MusicStreamer.desktop` → `org.lightningjim.MusicStreamer.desktop`. Inside-content (`Name`, `StartupWMClass`, `Icon`) already correct; `Exec=` audited.
- **D-04:** MPRIS bus name (`org.mpris.MediaPlayer2.musicstreamer`) is NOT renamed. Only the MPRIS `DesktopEntry` property value changes (D-02).

**Display-name lever (Area 2):**
- **D-05:** `.desktop` file lookup is the binding mechanism. GNOME Shell force-quit reads `Name=` from the matching `.desktop` file (resolved via app_id / WM_CLASS → XDG search path). No Qt API can substitute.
- **D-06:** Add `app.setApplicationDisplayName("MusicStreamer")` next to existing `setApplicationName` call. Belt-and-suspenders; harmless one-liner.
- **D-07:** Keep existing `setApplicationName("MusicStreamer")` (already at `__main__.py:143`).
- **D-08:** WM_CLASS / Wayland app_id mechanics are research territory — RESOLVE THIS. (See Open Question #1 below — RESOLVED.)

**.desktop install strategy (Area 3):**
- **D-09:** Self-install on first launch. Routine called from `__main__.py::_run_gui` between `Gst.init()` and `migration.run_migration()` (or sibling). Pattern mirrors `migration.run_migration()` — one-shot guarded by install marker. Idempotent.
- **D-10:** Install both `.desktop` file AND icon. Source: `packaging/linux/org.lightningjim.MusicStreamer.png` (1024×1024). Target: `~/.local/share/icons/hicolor/<size>/apps/org.lightningjim.MusicStreamer.png` — planner picks size bucket.
- **D-11:** No stale-file cleanup. Install routine is additive only.
- **D-12:** One-shot, not every-launch. Install marker checked once on first launch; subsequent launches skip entirely.
- **D-13:** Run `update-desktop-database` / `gtk-update-icon-cache` if available (best-effort). Wrap in try/except. **(Claude's discretion — planner may skip if it complicates.)**

**Diagnose-first vs fix-first (Area 4):**
- **D-14:** Diagnose-first, Phase 56 pattern. First plan produces `61-DIAGNOSTIC-LOG.md` capturing the BEFORE state on Kyle's X11 rig.
- **D-15:** Code change ships in same phase regardless of diagnostic outcome. (Two known-broken conditions are expected — the diagnostic documents rather than pivots the fix.)
- **D-16:** UAT gate = GNOME force-quit dialog reads "MusicStreamer" on Kyle's X11 rig after fresh `uv run musicstreamer` launch.

### Claude's Discretion

- Exact name and module location of the install routine (`desktop_install.py` next to `migration.py`, or a new function in `migration.py` itself, or `linux_install.py`). Planner picks; pure mechanism.
- Icon size bucket (256×256 vs 512×512 vs both). 256×256 is GNOME Shell default.
- Whether install marker is sentinel file under `~/.local/share/musicstreamer/` or per-feature marker. `migration.py` pattern is established.
- Whether to run `update-desktop-database` / `gtk-update-icon-cache` (D-13 — best-effort hook).
- Where the `.desktop` file source lives — current location is repo root, but `packaging/linux/org.lightningjim.MusicStreamer.desktop` (next to icon) reads cleaner.
- Whether to inject `-name MusicStreamer` into argv before `QApplication(...)` to force X11 WM_CLASS instance to match `StartupWMClass=MusicStreamer`. **Researcher answer: NOT NEEDED. See Open Question #1.**

### Deferred Ideas (OUT OF SCOPE)

- Proper Linux installer / packaging (deb / rpm / Flatpak / AppImage). Future Linux-packaging phase.
- Stale-file cleanup (remove orphan `org.example.MusicStreamer.desktop`). Reviewed and declined; user manages manually.
- Self-healing install (refresh `.desktop` and icon on every launch). Reviewed and declined; one-shot is simpler.
- Wayland-specific UAT step. Memory locks deployment as X11.
- Per-DE matrix (KDE Plasma, XFCE, Cinnamon). Out of scope; GNOME-only.
- Build-time AUMID/APP_ID drift guard (analog of Phase 56 D-09 #3). With `constants.APP_ID` as single source (D-02), drift is structurally impossible.
- BUG-09 (Phase 62), VER-01 (Phase 63).

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BUG-08 | Linux force-quit and other WM-level dialogs display "MusicStreamer" instead of the reverse-DNS app ID `org.example.MusicStreamer` (Linux parallel to WIN-02) | Two-half fix: (1) rename placeholder `org.example.MusicStreamer` → `org.lightningjim.MusicStreamer` everywhere, single-sourced through `constants.APP_ID`; (2) ship pure-Python self-install routine that drops the renamed `.desktop` + icon into `~/.local/share/` per XDG spec on first launch, idempotent. Full mechanism lookup chain documented in Pattern 1 (GNOME Shell match algorithm). Diagnostic command set ships as `61-DIAGNOSTIC-LOG.md` artifact per D-14. |

## Project Constraints (from CLAUDE.md)

CLAUDE.md is minimal — only routes spike-findings work to `Skill("spike-findings-musicstreamer")`. The skill is **Windows-only** (gstreamer-bundling, qt-glib-bus-threading); no Linux WM coverage. Confirmed no other directives apply to this phase.

**MEMORY.md notes (relevant to this phase):**
- **Deployment target: Linux X11 DPR=1.0** — no Wayland-fractional rig. Wayland coverage in this phase is a free side effect of `setDesktopFileName` (which Qt routes to Wayland `xdg-shell::set_app_id`), not a UAT gate. **[VERIFIED: project memory file]**
- `gsd-sdk` wrapper at `~/.local/bin/gsd-sdk` — operational, not relevant to phase content.
- `.planning/` is gitignored post-cookie-leak scrub — `git add` of planning docs returns "ignored" non-fatally; do NOT force-add.

## Standard Stack

This phase introduces **no new dependencies**. All work uses libraries already pinned in `pyproject.toml`.

### Core (already pinned)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `os`, `shutil`, `pathlib` | 3.10+ | File copy, mkdir -p, atomic rename, marker write | `migration.py` already uses this exact toolset for the same idempotent first-launch pattern [VERIFIED: musicstreamer/migration.py:18-20] |
| Python stdlib `subprocess` | 3.10+ | Best-effort `update-desktop-database` / `gtk-update-icon-cache` calls (D-13) | Project convention — used for `streamlink`, `node`, `ffmpeg` shell-outs in `subprocess_utils.py` |
| Python stdlib `sys` | 3.10+ | `sys.platform.startswith("linux")` guard for the install routine | Existing pattern in `__main__.py::_set_windows_aumid` (`if sys.platform != "win32"`) |
| Python stdlib `logging` | 3.10+ | `_log = logging.getLogger(__name__)` per project convention | Used throughout `aa_import.py`, `player.py`, `mpris2.py` |
| pytest 9+ + pytest-qt 4+ | per pyproject `[project.optional-dependencies].test` | Unit tests for `desktop_install.py` with `tmp_path` | Already in use across all `tests/test_*.py` files. Pattern mirrored from `tests/test_migration.py` (`tmp_path` + monkeypatch the install-target paths). [VERIFIED: tests/test_migration.py:1-100] |
| PySide6 6.11.0 / Qt 6.11.0 | per pyproject pin | `setApplicationDisplayName` API call | Already pinned; no version bump. [VERIFIED: 2026-05-05 — `python3 -c "from PySide6 import QtCore; print(QtCore.qVersion())"` returns `6.11.0`] |
| `platformdirs` | per pyproject pin (transitive — already imported in `paths.py`) | Reading `user_data_dir("musicstreamer")` for the install marker location | Existing module convention; `paths.migration_marker()` is the established sibling for one-shot first-launch markers. [VERIFIED: musicstreamer/paths.py:72-73] |

### Supporting (Linux diagnostic surface — UAT only)

| Tool | Source | Purpose | Availability on Kyle's rig |
|------|--------|---------|---------------------------|
| `xprop` | `x11-utils` package | Read WM_CLASS / window properties for diagnostic | ✓ `/usr/bin/xprop` [VERIFIED: 2026-05-05] |
| `xdotool` | `xdotool` package | Find a window by name without an interactive click (`xdotool search --name MusicStreamer`) | ✓ `/usr/bin/xdotool` [VERIFIED: 2026-05-05] |
| `gnome-shell` | core GNOME | Version readout for log | ✓ `/usr/bin/gnome-shell` (50.1) [VERIFIED: 2026-05-05] |
| `update-desktop-database` | `desktop-file-utils` package | MIME-cache refresh after install (only required for MIME-handler activations, NOT for shell window-app matching — but harmless to run) [CITED: manpages.ubuntu.com/manpages/focal/en/man1/update-desktop-database.1.html] | ✓ `/usr/bin/update-desktop-database` [VERIFIED: 2026-05-05] |
| `gtk-update-icon-cache` | `gtk-update-icon-cache` package | Icon-theme cache refresh; speeds up GTK-app icon resolution but **not strictly required for the `hicolor` theme on a freshly-installed icon** since gnome-shell falls back to a directory scan when the cache is absent [CITED: ArchWiki Icons] | ✓ `/usr/bin/gtk-update-icon-cache` [VERIFIED: 2026-05-05] |
| `gsettings` | `glib2` core | Optional sanity readout (`gsettings get org.gnome.shell favorite-apps`) | ✓ `/usr/bin/gsettings` [VERIFIED: 2026-05-05] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `setDesktopFileName(constants.APP_ID)` | `setDesktopFileName(constants.APP_ID + ".desktop")` | Both work — Qt strips a trailing `.desktop` if present [CITED: doc.qt.io/qt-6/qguiapplication.html "If the specified desktop file name ends with .desktop, for compatibility reasons, the .desktop suffix will be removed"]. Project convention is to omit the suffix; align with that. |
| `-name MusicStreamer` argv injection | Rely on natural Qt WM_CLASS construction | **NOT needed** for this phase. The Qt6 X11 plugin sets `WM_CLASS` class half from `applicationName()` ("MusicStreamer" already), instance half from argv[0] basename ("musicstreamer" or "python3"). GNOME's match algorithm tries the **class half first** against `StartupWMClass=MusicStreamer` — this MATCHES today, has always matched. The bug isn't WM_CLASS; it's the missing `.desktop` file. [VERIFIED: github.com/qt/qtbase/blob/dev/src/plugins/platforms/xcb/qxcbintegration.cpp `wmClass()`] |
| Self-install routine in `migration.py` | New module `desktop_install.py` | Both work. New module is cleaner separation of concerns (data migration vs. desktop integration); planner can pick. Lean toward NEW module — `migration.py` is data-bound (cookies, tokens, SQLite); `.desktop` install is OS-integration-bound. |
| Install icon to single bucket (256×256) | Install to multiple buckets (256×256 + 128×128 + 64×64) | The hicolor theme spec defines a `Scale` lookup with downscaling fallback when the requested bucket is absent. Single 256×256 install works; the freedesktop spec recommends 48×48 minimum for KDE/GNOME menu visibility. Kyle's rig already has `~/.local/share/icons/hicolor/256x256/apps/org.lightningjim.MusicStreamer.png` (and 128/64 buckets) from a previous manual install — the install routine should be idempotent against pre-existing files anyway. **Recommend 256×256 single-bucket install** (matches GNOME default). [CITED: developer.gnome.org/documentation/tutorials/themed-icons.html] |
| `Categories=Audio;Music;Network;` (current `.desktop`) | `Categories=AudioVideo;Audio;Music;Network;` | **`Audio` alone is NOT a registered freedesktop main category** — the spec requires at least one main category from the registered list (AudioVideo, Audio, Video, etc. — note: `Audio` IS registered as a main category since 1.0; `AudioVideo` is the umbrella). Current `.desktop` file is technically valid (Audio is registered), but mainstream apps tend to declare `AudioVideo;Audio;` for maximum menu category coverage. **Audit during the rename plan; either is acceptable.** [CITED: specifications.freedesktop.org/menu-spec/latest/apa.html] |

**Installation:** No `pip install` or `npm install` needed. **Tools required for tests:** none new. **Tools required for diagnostic:** `xprop` (already present on rig), `xdotool` (already present), nothing else.

**Version verification (performed 2026-05-05):**
- Python 3.10+ already required (pyproject `requires-python = ">=3.10"`).
- PySide6 6.11.0 / Qt 6.11.0 in active venv — confirmed `setApplicationDisplayName` and `setDesktopFileName` are available since Qt 5.7 / Qt 5.7 respectively. [VERIFIED: 2026-05-05 active venv readback]
- All Linux diagnostic tooling is OS-built-in on Ubuntu/Debian-style distros; verified present on Kyle's rig.

## Architecture Patterns

### System Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                  Phase 61: GNOME Shell Display-Name Resolution           │
│                                                                          │
│  Process startup (one-time)                                              │
│  ────────────────────────────                                             │
│  uv run musicstreamer                                                    │
│      │                                                                   │
│      ▼                                                                   │
│  __main__.main() → _run_gui()                                            │
│      │                                                                   │
│      ▼                                                                   │
│  _set_windows_aumid()  [no-op on Linux per sys.platform != "win32"]      │
│      │                                                                   │
│      ▼                                                                   │
│  Gst.init(None)                                                          │
│      │                                                                   │
│      ▼                                                                   │
│  desktop_install.ensure_installed()  ◄── NEW (D-09)                      │
│      │   ┌─────────────────────────────────────────────────────────┐     │
│      │   │ if marker file exists → return (one-shot, D-12)         │     │
│      │   │ else:                                                   │     │
│      │   │   copy bundled .desktop → ~/.local/share/applications/  │     │
│      │   │   copy bundled icon → ~/.local/share/icons/hicolor/     │     │
│      │   │                                  256x256/apps/          │     │
│      │   │   try update-desktop-database (best-effort, D-13)       │     │
│      │   │   try gtk-update-icon-cache (best-effort, D-13)         │     │
│      │   │   write marker file (atomic; tmp + rename)              │     │
│      │   └─────────────────────────────────────────────────────────┘     │
│      ▼                                                                   │
│  migration.run_migration()  [existing, separate concern]                 │
│      │                                                                   │
│      ▼                                                                   │
│  app = QApplication(argv)                                                │
│  app.setApplicationName("MusicStreamer")           [existing, D-07]      │
│  app.setApplicationDisplayName("MusicStreamer")    ◄── NEW (D-06)        │
│  app.setDesktopFileName(constants.APP_ID)          [existing, reads      │
│                                                     constants.APP_ID     │
│                                                     instead of literal]  │
│      │                                                                   │
│      ▼                                                                   │
│  MainWindow.show() → first window mapped                                 │
│      │                                                                   │
│      ▼                                                                   │
│  Qt XCB plugin:                                                          │
│    WM_CLASS = (instance="musicstreamer", class="MusicStreamer")          │
│      • instance ← argv[0] basename                                       │
│      • class ← applicationName() = "MusicStreamer"                       │
│    _GTK_APPLICATION_ID = "org.lightningjim.MusicStreamer"                │
│      • from setDesktopFileName(constants.APP_ID)                         │
│    _KDE_NET_WM_DESKTOP_FILE = "org.lightningjim.MusicStreamer"           │
│      • from setDesktopFileName(constants.APP_ID)                         │
│  Qt Wayland plugin (free side-effect):                                   │
│    xdg_toplevel.app_id = "org.lightningjim.MusicStreamer"                │
│      • from setDesktopFileName(constants.APP_ID)                         │
│                                                                          │
│  Force-quit triggered (out-of-process, on demand)                        │
│  ─────────────────────────────────────────────────                        │
│  GNOME Shell ShellWindowTracker:                                         │
│    1. window class half ("MusicStreamer") matches                        │
│       StartupWMClass="MusicStreamer" in                                  │
│       ~/.local/share/applications/org.lightningjim.MusicStreamer.desktop │
│    2. → resolves to that .desktop file                                   │
│    3. → reads Name= field → "MusicStreamer"                              │
│    4. force-quit dialog displays "MusicStreamer"  ✓ (gate satisfied)     │
└──────────────────────────────────────────────────────────────────────────┘
```

### Recommended File Layout

```
musicstreamer/
├── constants.py                # MODIFY: APP_ID literal change
├── __main__.py                 # MODIFY: setDesktopFileName reads constants;
│                               #         add setApplicationDisplayName;
│                               #         drop hardcoded default in _set_windows_aumid;
│                               #         call desktop_install.ensure_installed()
├── desktop_install.py          # NEW (Claude's discretion: this OR add to migration.py)
├── migration.py                # NO CHANGE (separate concern — data migration)
├── single_instance.py          # NO CHANGE (already on org.lightningjim)
└── media_keys/
    └── mpris2.py               # MODIFY: DesktopEntry property reads constants.APP_ID

packaging/linux/
├── org.lightningjim.MusicStreamer.desktop   # NEW (moved from repo root + renamed)
└── org.lightningjim.MusicStreamer.png       # NO CHANGE (already named correctly)

# REMOVE: org.example.MusicStreamer.desktop (repo root)

Makefile                        # MODIFY (DRIFT FOUND — see Pitfall 7):
                                #   DESKTOP_FILE = org.lightningjim.MusicStreamer.desktop
                                #   ICON_FILE / install / uninstall paths

tests/
├── test_desktop_install.py     # NEW (Wave 0): tmp_path-based unit tests
└── test_constants.py           # OPTIONAL (1-line assertion APP_ID == expected)
```

### Pattern 1: GNOME Shell Window-to-`.desktop` Match Algorithm (the canonical lookup)

**What:** GNOME Shell's `ShellWindowTracker` (the same code path used by force-quit, Activities, Alt-Tab, dock indicators, and notifications) walks an ordered, **case-sensitive** chain of comparisons to map a running window to a `.desktop` file. The `.desktop` file's `Name=` field is then displayed as the app's friendly name in shell surfaces. [CITED: gitlab.gnome.org/GNOME/gnome-shell/-/merge_requests/84 + mail.gnome.org/archives/commits-list/2013-August/msg01635.html]

**The algorithm (in order):**

1. **`_GTK_APPLICATION_ID` window property** — set by Qt from `setDesktopFileName(constants.APP_ID)`. If GNOME finds a `.desktop` file whose **basename** (without `.desktop`) matches this string, that's a direct hit. **This is the highest-priority match and the one the project relies on most.** [CITED: github.com/qt/qtbase qxcbwindow.cpp lines 396-419]
2. **`WM_CLASS` class half → `StartupWMClass=`** field of any `.desktop` file in the XDG search path. With `setApplicationName("MusicStreamer")`, the class half is `"MusicStreamer"` (no transformation). `StartupWMClass=MusicStreamer` in the bundled file matches.
3. **`WM_CLASS` instance half → `StartupWMClass=`** field. Instance is argv[0] basename — `"musicstreamer"` when launched via the wrapper, `"python3"` when launched via `uv run python -m musicstreamer`. Lower-priority fallback.
4. **`WM_CLASS` class half → `.desktop` file basename**. Class is `"MusicStreamer"` — would only match a hypothetical `MusicStreamer.desktop`. Not relied on.
5. **`WM_CLASS` instance half → `.desktop` file basename**. Same lower-priority fallback as #3.

**On Wayland**, step 1 is replaced by `xdg_toplevel.app_id` lookup (set by Qt via `setDesktopFileName`); steps 2–5 are X11-only.

**Key implication:** With `setDesktopFileName(constants.APP_ID)` in place AND a `.desktop` file at `~/.local/share/applications/org.lightningjim.MusicStreamer.desktop`, **step 1 hits and the lookup terminates successfully** without needing any of steps 2-5 to fire. The phase doesn't depend on the WM_CLASS instance string at all — the `_GTK_APPLICATION_ID` property is the cleanest match path.

**When to use:** Any time a window's "friendly name" needs to surface in a shell-mediated dialog (force-quit, Activities, Alt-Tab, notification "from app X", dock running-app indicator).

**Example (Qt6 source — verbatim from the XCB plugin):**

```cpp
// Source: qtbase/src/plugins/platforms/xcb/qxcbwindow.cpp lines 389-419
// (paraphrased — see Sources for direct link)

const QByteArray wmClass = QXcbIntegration::instance()->wmClass();
if (!wmClass.isEmpty()) {
    xcb_change_property(..., AtomWM_CLASS, ..., wmClass.constData());
}

QString dfName = QGuiApplication::desktopFileName();
if (dfName.isEmpty()) {
    dfName = QCoreApplication::organizationDomain().split(...)
             + QFileInfo(QCoreApplication::applicationFilePath()).baseName();
}
if (!dfName.isEmpty()) {
    xcb_change_property(..., Atom_KDE_NET_WM_DESKTOP_FILE, ..., dfName.toUtf8());
    xcb_change_property(..., Atom_GTK_APPLICATION_ID, ..., dfName.toUtf8());
}
```

```cpp
// qtbase/src/plugins/platforms/xcb/qxcbintegration.cpp wmClass() ~ lines 527-552:
QString name = m_instanceName;  // populated from -name argv flag
if (name.isEmpty() && qEnvironmentVariableIsSet(resourceNameVar))
    name = qEnvironmentVariable(resourceNameVar);  // RESOURCE_NAME env
if (name.isEmpty())
    name = argv0BaseName();  // executable basename fallback

QString className = QCoreApplication::applicationName();
if (className.isEmpty()) {
    className = argv0BaseName();
    if (!className.isEmpty() && className.at(0).isLower())
        className[0] = className.at(0).toUpper();
}

m_wmClass = std::move(name).toLocal8Bit() + '\0'
          + std::move(className).toLocal8Bit() + '\0';
```

### Pattern 2: Idempotent Self-Install via Marker File (`migration.py` shape)

**What:** A module-level `ensure_installed()` function that no-ops when a marker file is present, otherwise copies bundled assets into XDG paths, runs best-effort cache hooks, and writes the marker on success. Mirrors `migration.run_migration()` exactly.

**When to use:** First-launch one-shot routines that must NOT re-run on every launch (D-12).

**Example (proposed implementation):**

```python
# Source: NEW musicstreamer/desktop_install.py — follows migration.py shape

"""Phase 61 / D-09: First-launch .desktop + icon self-install for Linux.

Mirrors migration.run_migration() — one-shot guarded by a marker file under
~/.local/share/musicstreamer/. Idempotent: no-op on subsequent launches.

Best-effort post-install hooks (D-13): update-desktop-database and
gtk-update-icon-cache are called via subprocess if available. Failure does
NOT block app startup.

No-op on non-Linux platforms (sys.platform != "linux").
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from musicstreamer import constants, paths

_log = logging.getLogger(__name__)

# Bundled-asset locations relative to package root. Tests can monkeypatch.
_PACKAGE_ROOT = Path(__file__).parent.parent  # musicstreamer/../  = repo root
_BUNDLED_DESKTOP = _PACKAGE_ROOT / "packaging" / "linux" / f"{constants.APP_ID}.desktop"
_BUNDLED_ICON = _PACKAGE_ROOT / "packaging" / "linux" / f"{constants.APP_ID}.png"

# XDG install destinations (relative to $XDG_DATA_HOME or ~/.local/share).
# Computed at call time so tests with monkeypatched HOME work cleanly.
_ICON_BUCKET = "256x256"  # GNOME Shell default; single bucket is sufficient.


def _xdg_data_home() -> Path:
    """$XDG_DATA_HOME with the freedesktop fallback to ~/.local/share."""
    env = os.environ.get("XDG_DATA_HOME")
    if env:
        return Path(env)
    return Path.home() / ".local" / "share"


def _install_marker() -> Path:
    """Marker under platformdirs data dir (~/.local/share/musicstreamer/)."""
    return Path(paths.data_dir()) / ".desktop-installed-v1"


def ensure_installed() -> None:
    """Run the self-install if the marker is absent. No-op otherwise.

    Linux-only — early-returns on non-Linux platforms.
    """
    if not sys.platform.startswith("linux"):
        return

    marker = _install_marker()
    if marker.exists():
        return

    try:
        _do_install()
    except Exception as exc:  # noqa: BLE001 — best-effort; log and proceed
        _log.warning("desktop_install failed (will retry next launch): %s", exc)
        return

    _write_marker(marker)
    _log.info("desktop_install complete (marker: %s)", marker)


def _do_install() -> None:
    """Atomic install of .desktop file + icon to XDG paths."""
    xdg = _xdg_data_home()

    # 1. .desktop file → ~/.local/share/applications/<app_id>.desktop
    desktop_dst = xdg / "applications" / f"{constants.APP_ID}.desktop"
    desktop_dst.parent.mkdir(parents=True, exist_ok=True)
    if not desktop_dst.exists():
        _atomic_copy(_BUNDLED_DESKTOP, desktop_dst)
        _log.info("Installed .desktop file: %s", desktop_dst)

    # 2. Icon → ~/.local/share/icons/hicolor/256x256/apps/<app_id>.png
    icon_dst = xdg / "icons" / "hicolor" / _ICON_BUCKET / "apps" / f"{constants.APP_ID}.png"
    icon_dst.parent.mkdir(parents=True, exist_ok=True)
    if not icon_dst.exists():
        _atomic_copy(_BUNDLED_ICON, icon_dst)
        _log.info("Installed icon: %s", icon_dst)

    # 3. Best-effort cache hooks (D-13). Failure is fine — caches will rebuild
    #    next time the user logs out/in or runs the tool manually.
    _best_effort(["update-desktop-database", str(desktop_dst.parent)])
    _best_effort(["gtk-update-icon-cache", "--quiet", str(xdg / "icons" / "hicolor")])


def _atomic_copy(src: Path, dst: Path) -> None:
    """Copy src → dst via tmp + rename (POSIX atomic when on the same fs)."""
    with tempfile.NamedTemporaryFile(
        dir=str(dst.parent), prefix=f".{dst.name}.", delete=False
    ) as tmp:
        tmp_path = Path(tmp.name)
    try:
        shutil.copy2(src, tmp_path)  # preserves mode bits
        os.replace(tmp_path, dst)  # atomic on the same filesystem
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def _best_effort(cmd: list[str]) -> None:
    """Run cmd; log failure but never raise."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            _log.debug(
                "%s exit %d: %s", cmd[0], result.returncode, result.stderr.strip()
            )
    except FileNotFoundError:
        _log.debug("%s not found on PATH — skipping cache refresh", cmd[0])
    except subprocess.TimeoutExpired:
        _log.debug("%s timed out — skipping", cmd[0])
    except Exception as exc:  # noqa: BLE001
        _log.debug("%s raised %s — skipping", cmd[0], exc)


def _write_marker(marker: Path) -> None:
    """Atomically write the install marker (mirrors migration._write_marker)."""
    marker.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", dir=str(marker.parent), prefix=f".{marker.name}.",
        delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(f"desktop install v1 complete; app_id={constants.APP_ID}\n")
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, marker)
```

### Pattern 3: Test Harness (`tmp_path` + monkeypatch HOME)

**What:** Pytest tests for `desktop_install` use `tmp_path` to redirect XDG_DATA_HOME AND monkeypatch `paths.data_dir()` for the marker, with no actual filesystem effects on the dev rig.

**When to use:** Any pure-Python file-IO routine that writes to user dirs.

**Example (proposed test pattern, mirrors `tests/test_migration.py`):**

```python
# tests/test_desktop_install.py — Wave 0

import os
import pytest
from pathlib import Path

from musicstreamer import desktop_install, paths


@pytest.fixture(autouse=True)
def _reset_paths(tmp_path, monkeypatch):
    """Redirect XDG_DATA_HOME + paths.data_dir() under tmp_path."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg_data"))
    monkeypatch.setattr(paths, "_root_override", str(tmp_path / "data"))
    yield


@pytest.fixture
def fake_bundled(tmp_path, monkeypatch):
    """Fake bundled .desktop + icon under tmp_path so we don't depend on
    repo packaging/ being read-clean during tests."""
    bundled_desktop = tmp_path / "bundled.desktop"
    bundled_desktop.write_text("[Desktop Entry]\nName=MusicStreamer\n...\n")
    bundled_icon = tmp_path / "bundled.png"
    bundled_icon.write_bytes(b"\x89PNG fake")
    monkeypatch.setattr(desktop_install, "_BUNDLED_DESKTOP", bundled_desktop)
    monkeypatch.setattr(desktop_install, "_BUNDLED_ICON", bundled_icon)
    return bundled_desktop, bundled_icon


def test_first_launch_installs_files(tmp_path, fake_bundled):
    desktop_install.ensure_installed()
    xdg = tmp_path / "xdg_data"
    expected_desktop = xdg / "applications" / "org.lightningjim.MusicStreamer.desktop"
    expected_icon = (
        xdg / "icons" / "hicolor" / "256x256" / "apps"
        / "org.lightningjim.MusicStreamer.png"
    )
    assert expected_desktop.exists()
    assert expected_icon.exists()
    assert (Path(paths.data_dir()) / ".desktop-installed-v1").exists()


def test_idempotent_via_marker(tmp_path, fake_bundled, monkeypatch):
    """Second call must be a no-op even if assets are deleted between runs."""
    desktop_install.ensure_installed()
    xdg = tmp_path / "xdg_data"
    desktop_path = xdg / "applications" / "org.lightningjim.MusicStreamer.desktop"
    desktop_path.unlink()  # someone deleted the installed file by hand
    desktop_install.ensure_installed()  # second call
    # No-op — file is NOT recreated because the marker says "done"
    assert not desktop_path.exists()


def test_no_op_off_linux(monkeypatch, fake_bundled):
    monkeypatch.setattr(desktop_install.sys, "platform", "win32")
    desktop_install.ensure_installed()
    # No marker, no install
    assert not (Path(paths.data_dir()) / ".desktop-installed-v1").exists()


def test_existing_files_preserved(tmp_path, fake_bundled):
    """If user already has a hand-installed .desktop, do NOT overwrite."""
    xdg = tmp_path / "xdg_data"
    apps = xdg / "applications"
    apps.mkdir(parents=True)
    pre_existing = apps / "org.lightningjim.MusicStreamer.desktop"
    pre_existing.write_text("USER MODIFIED")
    desktop_install.ensure_installed()
    assert pre_existing.read_text() == "USER MODIFIED"  # unchanged


def test_cache_hooks_called_best_effort(monkeypatch, fake_bundled):
    calls = []
    def fake_run(cmd, *args, **kwargs):
        calls.append(cmd)
        class R:
            returncode = 0
            stderr = ""
        return R()
    monkeypatch.setattr(desktop_install.subprocess, "run", fake_run)
    desktop_install.ensure_installed()
    cmds = [c[0] for c in calls]
    assert "update-desktop-database" in cmds
    assert "gtk-update-icon-cache" in cmds


def test_missing_cache_tool_does_not_raise(monkeypatch, fake_bundled):
    def fake_run(cmd, *args, **kwargs):
        raise FileNotFoundError(cmd[0])
    monkeypatch.setattr(desktop_install.subprocess, "run", fake_run)
    desktop_install.ensure_installed()  # must not raise
    # Marker still written
    assert (Path(paths.data_dir()) / ".desktop-installed-v1").exists()
```

### Anti-Patterns to Avoid

- **Injecting `-name MusicStreamer` into argv before `QApplication(...)`.** Not needed. The Qt6 X11 plugin's `wmClass()` derives the class half from `applicationName()` which is already `"MusicStreamer"`. The class half hits `StartupWMClass=MusicStreamer` in step 2 of the GNOME match algorithm, AND `_GTK_APPLICATION_ID` from `setDesktopFileName` hits step 1 (highest priority) directly. Adding `-name` is cargo-culting; it would only change the WM_CLASS instance string from "musicstreamer" / "python3" to "MusicStreamer" — but the instance is already a lower-priority match path, AND step 1 short-circuits the entire chain.
- **Calling `setDesktopFileName(constants.APP_ID + ".desktop")`.** Both work — Qt strips a trailing `.desktop` automatically [CITED: doc.qt.io/qt-6/qguiapplication.html] — but project convention (and MPRIS `DesktopEntry` semantics) is to use the bare basename without the suffix.
- **Re-running the install routine on every launch (against D-12).** Tempting "for safety" but contradicts the locked decision and adds startup latency. Marker-guarded one-shot is correct.
- **Refreshing the install on content drift (against deferred ideas — self-healing install).** User is trusted; if they hand-edit the installed `.desktop`, the app respects the edit. A future phase can add a per-content-hash refresh if real drift is observed in the wild.
- **Relying on `update-desktop-database` for window-app matching.** That tool builds the **MIME-type cache** (`mimeinfo.cache`) — it is required for "open with..." menus and MIME-handler registration, NOT for shell window-to-app matching. GNOME Shell's `ShellWindowTracker` reads `.desktop` files directly via `GDesktopAppInfo` (which uses `inotify` to detect new files in `~/.local/share/applications/`); a fresh install is visible to the shell within seconds without the cache rebuild. The hook is harmless to run, but is NOT the load-bearing piece. [CITED: manpages.ubuntu.com/.../update-desktop-database.1.html + GNOME GAppInfoMonitor / glib gdesktopappinfo.c]
- **Hand-rolling a hicolor icon-theme cache.** The `gtk-update-icon-cache` tool exists for exactly this; if it's not present, the shell falls back to a directory scan and the icon still resolves. Don't write a Python equivalent. [CITED: linuxcommandlibrary.com/man/gtk-update-icon-cache]
- **Using `os.rename` directly instead of `os.replace`.** On Windows, `os.rename` raises if the destination exists; `os.replace` overwrites atomically across both POSIX and Windows. The install routine targets Linux only, so the difference doesn't materialize, but `os.replace` is the better idiom regardless.
- **Skipping the `tmp + os.replace` atomic-write pattern for the install marker.** A partial write of the marker file on a crash mid-launch would leave the install routine in an undefined state. The atomic pattern (write tmp, fsync optional, replace) costs almost nothing and matches the migration helper's discipline.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| File copy with mode preservation | Custom open + read + write loop | `shutil.copy2(src, dst)` | Already used in `migration.py:62`; preserves mode bits (matters for the install marker, not for the public-readable `.desktop` file, but consistency wins) |
| Atomic file replace | Read into tmp + rename via `os.rename` | `os.replace(tmp, dst)` (Python 3.3+) | Cross-platform atomic semantic; existing pattern in `cookie_utils.py` (Phase 999.7) |
| First-launch idempotency | New marker scheme | `paths.migration_marker()` shape — file under `paths.data_dir()` | `migration.run_migration()` is the established precedent (musicstreamer/migration.py:28-45). Different marker name (`.desktop-installed-v1`) but identical shape. |
| XDG path resolution | Hardcoded `~/.local/share/...` | `os.environ.get("XDG_DATA_HOME")` with fallback to `Path.home() / ".local" / "share"` | freedesktop XDG Base Directory spec mandates the env var override; users with non-standard `$XDG_DATA_HOME` deserve to have it respected [CITED: specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html] |
| Subprocess best-effort runner | Bare `subprocess.run` with no error handling | The `_best_effort()` helper from Pattern 2 (catch FileNotFoundError + TimeoutExpired + Exception, log debug) | Existing pattern in `subprocess_utils.py`; D-13 requires "fail-soft" semantics |
| Icon cache management | New module that walks hicolor directories | `gtk-update-icon-cache` subprocess, best-effort | Standard XDG tool; `gnome-shell` falls back gracefully when cache is absent |
| `.desktop` file lookup at runtime (e.g., for self-tests) | Walk the XDG search path manually | `Gio.DesktopAppInfo.new("<basename>.desktop")` from `gi.repository.Gio` (already imported transitively via GStreamer) | Not needed for install routine; mentioned only to head off a hypothetical "verify install was successful" addition. The marker file IS the verification. |

**Key insight:** This phase is mostly stdlib + a few subprocess shell-outs. Resist the urge to depend on `pyxdg`, `xdg-utils` Python wrappers, or `desktop-file-validate` — they add a dependency for no functional gain. The freedesktop specs are simple enough to implement with `os.makedirs` + `shutil.copy2` + `os.replace`.

## Runtime State Inventory

> **Required because this phase is a rename + migration**. Below is the full audit per the canonical question: *After every file in the repo is updated, what runtime systems still have the old string cached, stored, or registered?*

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| **Stored data** | None — `org.example.MusicStreamer` is not a key, collection name, or user_id in any database. SQLite tables are unaffected. ChromaDB / Mem0 are not used by this project. **Verified by inspection:** the only data the app stores is its SQLite DB (stations, station_streams, favorites, settings) plus YouTube cookies / Twitch tokens — none reference the app id literal. | None — verified by reading `musicstreamer/repo.py` schema and `musicstreamer/paths.py`. |
| **Live service config** | (1) **MPRIS bus name `org.mpris.MediaPlayer2.musicstreamer`** — registered on the D-Bus session bus at runtime by `mpris2.py::LinuxMprisBackend.register()`. **NOT renamed** per D-04 (MPRIS spec dictates the lowercase-friendly-suffix convention, not reverse-DNS). (2) **MPRIS `DesktopEntry` property** — currently returns `"org.example.MusicStreamer"` to D-Bus clients; renamed by D-02 to read `constants.APP_ID`. Clients reading this property will see the new string on the next `Properties.Get` call (no init-order constraint). (3) **D-Bus interface names `org.mpris.MediaPlayer2`, `org.mpris.MediaPlayer2.Player`** — MPRIS spec; NOT renamed. | None for (1) and (3). For (2), the property change ships in the code rename; clients refresh on next query. No external client of the project depends on the placeholder value (single-user dev rig). |
| **OS-registered state** | (1) **Stale `~/.local/share/applications/org.example.MusicStreamer.desktop`** on Kyle's rig (verified 2026-05-05 — file contents match what would have been a manual `make install`). (2) **Pre-existing icons** at `~/.local/share/icons/hicolor/{64,128,256}x256/apps/org.lightningjim.MusicStreamer.png` (verified 2026-05-05). (3) **GNOME Shell's `GAppInfoMonitor` cache** — auto-refreshed via inotify when `~/.local/share/applications/` content changes. (4) **GTK icon-theme cache** at `~/.local/share/icons/hicolor/icon-theme.cache` — refreshed by `gtk-update-icon-cache`, optional for icon visibility. | (1) **Per D-11, NOT removed by the install routine** (additive-only). User can manually `rm` after the rename if desired; the new `.desktop` file will sort lexically AFTER the old one in the apps grid, which can briefly confuse Kyle in the Activities overview. **Recommend the diagnostic step explicitly call this out so Kyle can decide.** (2) Already correct — install routine is idempotent and will skip the icon copy if `~/.local/share/icons/hicolor/256x256/apps/org.lightningjim.MusicStreamer.png` already exists. (3) Refreshes automatically — no action. (4) Best-effort `gtk-update-icon-cache` call covers it; if missing, `gnome-shell` directory-scans on demand. |
| **Secrets / env vars** | None — the `org.example.MusicStreamer` literal is hardcoded in three Python files (`__main__.py`, `constants.py`, `mpris2.py`) and one Makefile. Not env-driven, not a secret, not referenced by `.env` or SOPS. | After the rename, NO env var or secret references the string anywhere. Verified by `grep -rn "org\.example" .` on the repo (excluding `.git/` and `.planning/`) — only the four files listed. **Drift impossible by construction post-rename (D-02).** |
| **Build artifacts / installed packages** | (1) **`.venv/lib/python*/site-packages/musicstreamer*.egg-info`** — a stale egg-info may carry references to the old string if the package was ever editable-installed against an earlier version. Unlikely to matter (the egg-info doesn't include `APP_ID`); planner audits during rename. (2) **PyInstaller `dist/MusicStreamer/` bundle (Windows)** — does NOT include the Linux `.desktop` file; built from `musicstreamer/__main__.py` source, picks up the new constant on rebuild. (3) **No deb / rpm / Flatpak / AppImage build artifacts exist** (deferred to future phase). (4) **GitHub releases / mirror** — none yet for v2.1.61, so no shipped artifact carries the placeholder. | (1) Optional: `pip install -e . --force-reinstall` after the rename to refresh the egg-info; not strictly required since the placeholder isn't in egg metadata. (2) Rebuilt fresh on every `build.ps1` run — no action. (3) N/A. (4) N/A. |

**Canonical question:** *After every file in the repo is updated, what runtime systems still have the old string cached, stored, or registered?*

**Answer:**
- **Stale `~/.local/share/applications/org.example.MusicStreamer.desktop`** on Kyle's rig (and any developer rig that ran `make install` historically). **Per D-11, this is NOT cleaned up by the phase**. The diagnostic captures its presence in the BEFORE state so the post-fix UAT can confirm it's not interfering with the new `.desktop` file's match. (GNOME's match algorithm walks ALL `.desktop` files; the new one WILL win for windows whose `_GTK_APPLICATION_ID` matches its basename, but the old one continues to appear as a phantom app in Activities until manually removed.)
- The MPRIS bus name (`org.mpris.MediaPlayer2.musicstreamer`) is intentionally unchanged (D-04). No drift.
- Everything else is either auto-refreshing (GNOME's inotify monitor on `applications/`), best-effort hookable (`gtk-update-icon-cache`), or non-existent (no built artifacts ship the placeholder).

## Common Pitfalls

### Pitfall 1: Rename misses the Makefile
**What goes wrong:** Three call sites are listed in CONTEXT.md (`constants.py`, `__main__.py`, `mpris2.py`). The Makefile is **not listed**. Lines 5–6, 32, and 43 of `Makefile` reference `org.example.MusicStreamer.desktop` and `org.example.MusicStreamer.svg`. After the rename, `make install` will silently fail to find the renamed file (and the SVG path was already broken — there is no `musicstreamer/assets/org.example.MusicStreamer.svg` in the repo, the icon at `packaging/linux/org.lightningjim.MusicStreamer.png` is the real asset).
**Why it happens:** The Makefile predates the v2.0 codebase rewrite (GTK-era artifact); it's not exercised by `uv run musicstreamer` so contributors stop reading it. The CONTEXT.md call-site enumeration came from `grep` on `.py` files only.
**How to avoid:** Plan must explicitly include "audit and update `Makefile`" as a task. Replace `DESKTOP_FILE` with the new name; remove the `ICON_FILE = musicstreamer/assets/org.example.MusicStreamer.svg` line (or repoint it at `packaging/linux/org.lightningjim.MusicStreamer.png`); update the install/uninstall paths in lockstep.
**Warning signs:** A `grep -rn "org\.example" .` after the rename returns ANY hit. **Drift-guard test recommended (see Pitfall 6).**

### Pitfall 2: Stale `org.example.MusicStreamer.desktop` in `~/.local/share/applications/` confuses Activities
**What goes wrong:** Kyle's rig already has a hand-installed `~/.local/share/applications/org.example.MusicStreamer.desktop` (verified 2026-05-05). After the rename + self-install, BOTH files exist in the apps directory. GNOME Shell shows two "MusicStreamer" entries in Activities (each `.desktop` has `Name=MusicStreamer`), which is confusing.
**Why it happens:** D-11 explicitly declines stale-file cleanup ("install routine is additive only"). The diagnostic captures the `ls` BEFORE state so the duplicate is visible.
**How to avoid:** Diagnostic plan calls out the duplicate to Kyle so he can `rm ~/.local/share/applications/org.example.MusicStreamer.desktop` manually as a one-shot post-fix cleanup. **Do NOT add stale-cleanup to the code routine** — that's the deferred "self-healing" idea (out of scope per CONTEXT.md).
**Warning signs:** Kyle reports two MusicStreamer entries in Activities after the install routine fires.

### Pitfall 3: `_GTK_APPLICATION_ID` changes BUT the old `.desktop` still wins force-quit lookup
**What goes wrong:** Subtle interaction — GNOME Shell tries `_GTK_APPLICATION_ID` lookup FIRST. After the rename, the running window emits `_GTK_APPLICATION_ID="org.lightningjim.MusicStreamer"`. If `~/.local/share/applications/org.lightningjim.MusicStreamer.desktop` does NOT exist yet (because the install routine hasn't run, or ran before the marker was written and crashed), the lookup falls through to step 2 (`WM_CLASS class → StartupWMClass`). The OLD `.desktop` (`org.example.MusicStreamer.desktop`) ALSO has `StartupWMClass=MusicStreamer` — so step 2 hits the OLD file, which has `Name=MusicStreamer`. Lookup succeeds, force-quit dialog shows "MusicStreamer", AND THE BUG APPEARS FIXED — but actually the new `.desktop` was never written and the install marker is missing. A user uninstalling the old file would re-trigger the bug.
**Why it happens:** Multiple `.desktop` files with overlapping `StartupWMClass` values. Two `Name=MusicStreamer` entries make the bug invisible to a UAT that only checks the dialog string.
**How to avoid:** UAT script MUST verify the install marker exists (`test -f ~/.local/share/musicstreamer/.desktop-installed-v1`) AND the new `.desktop` file is present at the expected path AND the OLD `.desktop` (if still there) is being overshadowed by `_GTK_APPLICATION_ID`'s direct hit, not coincidentally matched. Document the layered verification in the UAT script.
**Warning signs:** Marker missing while UAT passes — first-launch install silently failed.

### Pitfall 4: `setDesktopFileName` MUST run before any window is created
**What goes wrong:** `_GTK_APPLICATION_ID` is set during the window-create XCB call. If `setDesktopFileName` runs AFTER `MainWindow.show()`, the property is set on a per-window basis only at create time — already-shown windows DO NOT get retroactively updated. The first-shown window is the main window, so this is the only one that matters in practice, but the constraint is real.
**Why it happens:** Qt sets the X11 properties during window creation (in `QXcbWindow::create()`); subsequent `setDesktopFileName` calls update the application-wide value but don't re-apply to existing windows.
**How to avoid:** Existing code at `__main__.py:142-144` already places `setApplicationName` + `setDesktopFileName` immediately after `app = QApplication(argv)` and BEFORE `MainWindow(...)` construction (which happens later at line 170). Order is correct; preserve it. The new `setApplicationDisplayName` slots into the same sequence (D-06).
**Warning signs:** A future refactor moves `MainWindow.show()` before the `app.setXxx()` block.

### Pitfall 5: Repo-relative `_BUNDLED_DESKTOP` path breaks under PyInstaller
**What goes wrong:** The proposed `desktop_install.py` uses `_PACKAGE_ROOT = Path(__file__).parent.parent` to find `packaging/linux/<file>`. Under a PyInstaller onedir/onefile bundle (Windows path, but conceivably Linux later), `__file__` resolves to the extracted bundle root, and `packaging/` is NOT included unless explicitly added to the spec.
**Why it happens:** PyInstaller copies the package source but excludes top-level repo subdirs (like `packaging/`) unless declared.
**How to avoid:** Two mitigations: (a) the `desktop_install.py` is Linux-only and Linux currently has NO PyInstaller flow (Linux runs via `uv run` from source), so the path resolution works for the actual deployment target. (b) If a future Linux PyInstaller build appears, the spec file must declare `Tree('packaging/linux', prefix='packaging/linux')` — but that's a future-phase concern. **Recommend a code comment in `desktop_install.py` documenting this assumption.**
**Warning signs:** A future Linux PyInstaller phase adds `desktop_install` invocation and the bundled `.desktop` is missing at runtime.

### Pitfall 6: The two-literal drift problem (constants.APP_ID vs `.desktop` basename)
**What goes wrong:** `constants.APP_ID` is `"org.lightningjim.MusicStreamer"`. The bundled `.desktop` file basename is `org.lightningjim.MusicStreamer.desktop`. If a future contributor changes ONE without the other, the install routine writes the file under the new APP_ID basename but the bundled source still has the old name → install fails (FileNotFoundError on the bundled source). Or worse, the rename succeeds but `setDesktopFileName(constants.APP_ID)` no longer matches any `.desktop` file basename → the bug returns silently.
**Why it happens:** Two locations carry the same logical string with no shared source.
**How to avoid:** **Recommend a 5-line pytest guard:**
```python
# tests/test_desktop_install_drift.py
from pathlib import Path
from musicstreamer import constants

def test_bundled_desktop_basename_matches_app_id():
    """Drift guard: packaging/linux/<basename>.desktop must match constants.APP_ID."""
    pkg_dir = Path(__file__).parent.parent / "packaging" / "linux"
    expected = pkg_dir / f"{constants.APP_ID}.desktop"
    assert expected.exists(), (
        f"Bundled .desktop name must match constants.APP_ID. "
        f"Expected: {expected.name}. "
        f"Found in {pkg_dir}: {sorted(p.name for p in pkg_dir.glob('*.desktop'))}"
    )

def test_bundled_icon_basename_matches_app_id():
    """Drift guard: packaging/linux/<basename>.png must match constants.APP_ID."""
    pkg_dir = Path(__file__).parent.parent / "packaging" / "linux"
    expected = pkg_dir / f"{constants.APP_ID}.png"
    assert expected.exists()
```
This costs 10 lines, runs on every CI run, has zero runtime cost, and addresses the exact silent-failure mode. **Strongly recommend shipping it** — Phase 56 RESEARCH.md flagged a similar AUMID-drift guard as YAGNI-borderline; this one has more bite because two assets (file + icon) drift in lockstep risk.
**Warning signs:** `grep -rn "org\.lightningjim\.MusicStreamer" .` returns the literal in any non-`packaging/linux/` location post-rename (drift hint).

### Pitfall 7: Categories field minor compliance issue
**What goes wrong:** The current `.desktop` file has `Categories=Audio;Music;Network;`. `Music` is NOT a registered freedesktop main category — the registered ones include `AudioVideo`, `Audio`, `Video`, etc. (main) and `Player`, `Recorder`, `Music` (additional). A `.desktop` file MUST contain at least one main category; `Audio` covers it. Current file is technically compliant. However, Activities-search behavior on some distros prefers the combined `AudioVideo;Audio;` declaration for cross-DE consistency.
**Why it happens:** Easy to confuse main vs. additional categories.
**How to avoid:** Audit during the rename plan; either keep current `Categories=Audio;Music;Network;` (works, GNOME-tested per Kyle's existing manual install) or upgrade to `Categories=AudioVideo;Audio;Music;Network;` (slightly broader). Both pass `desktop-file-validate`. Low priority — current works on GNOME.
**Warning signs:** None — this is a hygiene issue, not a bug.

### Pitfall 8: Wayland session on dev rig vs. X11-locked deployment target
**What goes wrong:** On 2026-05-05, Kyle's session is `XDG_SESSION_TYPE=wayland` (GNOME Shell 50.1). Project memory locks the deployment as X11. If the diagnostic is run under Wayland, `xprop WM_CLASS` will work for Xwayland clients but Qt6 Wayland-native clients won't have an X11 window at all — `xprop` returns nothing. The diagnostic procedure must accommodate both.
**Why it happens:** GNOME defaults to Wayland on most modern distros; X11 is opt-in via the login screen "settings" gear.
**How to avoid:** Diagnostic step 1 is `echo $XDG_SESSION_TYPE`. If output is `wayland`, instruct Kyle to log out, select "GNOME on Xorg" (or equivalent) at the login screen, log back in, and re-run. Document this branch in the diagnostic script. Alternative: capture the Wayland readout via `gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell --method org.gnome.Shell.Eval 'global.get_window_actors().map(a => a.meta_window.gtk_application_id).filter(x => x)'` — but that requires unsafe-mode-shell on GNOME 41+ and is gnarly. **Recommend the X11-session approach.**
**Warning signs:** `xprop WM_CLASS` clicks return empty / gives unexpected output.

## Code Examples

### Example 1: Constant rename — `constants.py`

```python
# Source: musicstreamer/constants.py line 17, current state:
APP_ID = "org.example.MusicStreamer"

# After Phase 61:
APP_ID = "org.lightningjim.MusicStreamer"
```

### Example 2: `__main__.py` Qt wiring (D-02 + D-06 + D-07)

```python
# Source: musicstreamer/__main__.py lines 99-125 (current):
def _set_windows_aumid(app_id: str = "org.lightningjim.MusicStreamer") -> None:
    ...
    shell32.SetCurrentProcessExplicitAppUserModelID(app_id)

# After Phase 61 (D-02 — drop the literal default, read constants):
from musicstreamer import constants  # add at top of file

def _set_windows_aumid(app_id: str | None = None) -> None:
    if app_id is None:
        app_id = constants.APP_ID
    ...
    shell32.SetCurrentProcessExplicitAppUserModelID(app_id)


# Source: musicstreamer/__main__.py lines 142-144 (current):
app = QApplication(argv)
app.setApplicationName("MusicStreamer")
app.setDesktopFileName("org.example.MusicStreamer")

# After Phase 61 (D-02 + D-06):
app = QApplication(argv)
app.setApplicationName("MusicStreamer")              # D-07: keep
app.setApplicationDisplayName("MusicStreamer")       # D-06: NEW
app.setDesktopFileName(constants.APP_ID)             # D-02: read from constants
```

### Example 3: `__main__.py::_run_gui` install-routine wire-in (D-09)

```python
# Source: musicstreamer/__main__.py line 130-134 (current):
def _run_gui(argv: list[str]) -> int:
    _set_windows_aumid()
    Gst.init(None)

    from musicstreamer import migration
    migration.run_migration()

# After Phase 61 (D-09):
def _run_gui(argv: list[str]) -> int:
    _set_windows_aumid()
    Gst.init(None)

    from musicstreamer import desktop_install   # NEW
    desktop_install.ensure_installed()          # NEW (D-09)

    from musicstreamer import migration
    migration.run_migration()
```

### Example 4: `mpris2.py` DesktopEntry property (D-02)

```python
# Source: musicstreamer/media_keys/mpris2.py line 102-104 (current):
@Property(str)
def DesktopEntry(self) -> str:
    return "org.example.MusicStreamer"

# After Phase 61:
from musicstreamer import constants  # add at top of file (or inline-import)

@Property(str)
def DesktopEntry(self) -> str:
    return constants.APP_ID
```

### Example 5: Renamed `.desktop` file content (audited)

```ini
# packaging/linux/org.lightningjim.MusicStreamer.desktop
# (renamed from repo-root org.example.MusicStreamer.desktop)
[Desktop Entry]
Type=Application
Name=MusicStreamer
GenericName=Internet Radio
# Exec — current value `musicstreamer` works only when the Python entry-point script
# is on PATH. Under `uv run musicstreamer`, uv injects that script. For developer
# launches that's fine; for a future packaged install, the installer ships a
# concrete absolute path. Phase 61 keeps `Exec=musicstreamer` (matches current).
Exec=musicstreamer
Icon=org.lightningjim.MusicStreamer
Categories=AudioVideo;Audio;Music;Network;
Comment=Internet radio stream player
Keywords=radio;stream;music;internet;
StartupNotify=true
StartupWMClass=MusicStreamer
```

### Example 6: Diagnostic command set for `61-DIAGNOSTIC-LOG.md`

```bash
# Phase 61 — Linux WM display name diagnostic
# Run on Kyle's X11 rig BEFORE shipping the code change (PRE-FIX) and again AFTER (POST-FIX).

# === Step 1: Session type ===
echo "XDG_SESSION_TYPE=$XDG_SESSION_TYPE"
# Expected for the UAT gate: x11. If wayland, log out, select "GNOME on Xorg",
# log back in, and re-run from the start.

# === Step 2: GNOME Shell version ===
gnome-shell --version
# Capture for log; documents the target shell.

# === Step 3: Running window WM_CLASS (PRE-FIX expectation) ===
# Launch the app in a separate terminal: `uv run musicstreamer` (or the
# installed wrapper). Then in another terminal:
WID=$(xdotool search --name MusicStreamer | head -1)
echo "Window ID: $WID"
xprop -id "$WID" WM_CLASS WM_NAME _NET_WM_NAME _GTK_APPLICATION_ID _KDE_NET_WM_DESKTOP_FILE
# PRE-FIX expected:
#   WM_CLASS(STRING) = "musicstreamer", "MusicStreamer"
#       (instance "musicstreamer" from argv0, class "MusicStreamer" from applicationName)
#   _GTK_APPLICATION_ID(UTF8_STRING) = "org.example.MusicStreamer"
#       (from current setDesktopFileName)
#   _KDE_NET_WM_DESKTOP_FILE(UTF8_STRING) = "org.example.MusicStreamer"
# POST-FIX expected:
#   WM_CLASS unchanged
#   _GTK_APPLICATION_ID = "org.lightningjim.MusicStreamer"
#   _KDE_NET_WM_DESKTOP_FILE = "org.lightningjim.MusicStreamer"

# === Step 4: Installed .desktop files in user XDG path ===
ls -la ~/.local/share/applications/ 2>/dev/null | grep -i music
# PRE-FIX expected: ONE entry (org.example.MusicStreamer.desktop) — the stale
#   manual install. May be absent on a fresh dev box.
# POST-FIX expected: TWO entries (org.example.MusicStreamer.desktop AND
#   org.lightningjim.MusicStreamer.desktop) per D-11 (no cleanup).

# === Step 5: Installed .desktop files in system XDG path ===
ls -la /usr/share/applications/ 2>/dev/null | grep -i music
# Expected: empty (no system-wide install on the dev rig).

# === Step 6: Installed icons ===
ls -la ~/.local/share/icons/hicolor/*/apps/ 2>/dev/null | grep -i music
# PRE-FIX expected: existing org.lightningjim.MusicStreamer.png in 64/128/256
#   buckets (verified 2026-05-05) — the icon-half of the manual install
#   was already done.
# POST-FIX expected: same files, possibly with mtime updated if the install
#   routine overwrites (it shouldn't — `if not exists` guard).

# === Step 7: Install marker file ===
ls -la ~/.local/share/musicstreamer/.desktop-installed-v1 2>/dev/null
# PRE-FIX expected: missing (file or directory not found).
# POST-FIX expected: file exists with content "desktop install v1 complete; ..."

# === Step 8: Sanity — gnome-shell knows about the new app ===
gsettings get org.gnome.shell favorite-apps 2>/dev/null
# Captures favorites for forensic baseline; does NOT need to contain
# MusicStreamer (Kyle hasn't pinned it).
busctl --user list 2>/dev/null | grep -i music
# Expected: "org.mpris.MediaPlayer2.musicstreamer" (MPRIS bus name — D-04
# unchanged) IF the app is currently running.

# === Step 9: Manual UAT — force-quit dialog ===
# 1. Launch `uv run musicstreamer`. Wait for window to appear.
# 2. (Trigger force-quit: simplest is to suspend the process so GNOME flags
#    it as unresponsive — `kill -STOP $(pgrep -f musicstreamer)` from a
#    second terminal, then click anywhere in the app window. After ~5s
#    GNOME pops the "Application is not responding" dialog with Wait/Force
#    Close.)
# 3. Capture the dialog title bar / app-name string.
# PRE-FIX expected: the dialog reads "org.example.MusicStreamer" or a
#   generic shell label.
# POST-FIX expected: the dialog reads "MusicStreamer" with the correct icon.
# 4. `kill -CONT $(pgrep -f musicstreamer)` to resume; then `kill` cleanly.

# === Step 10: Activities/Alt-Tab sanity ===
# 1. With app running, hit Super to open Activities.
# 2. Hover over the MusicStreamer window thumbnail.
# 3. Confirm tooltip / overlay shows "MusicStreamer".
# 4. Alt-Tab; confirm app name in the switcher.
# Manual screenshot recommended for the BEFORE state.
```

**Notes on the diagnostic:**
- No commands require elevated privileges.
- All commands work on Kyle's rig (verified `xprop`/`xdotool`/`gnome-shell`/`gsettings`/`busctl` are present 2026-05-05).
- Step 3 requires the app to be running; Steps 4–8 work cold.
- Steps 9–10 are manual-UAT.

### Example 7: Drift-guard pytest (recommended per Pitfall 6)

```python
# tests/test_constants_drift.py — Wave 0 (or sibling to test_desktop_install.py)

"""Phase 61 D-02 drift guard: constants.APP_ID is the single source of truth.

These tests fail loud if the .desktop file basename or icon basename ever
drifts away from constants.APP_ID. Costs ~zero to run; addresses a real
silent-failure mode.
"""
from pathlib import Path

from musicstreamer import constants


def test_app_id_is_lightningjim_and_matches_phase_56_aumid():
    """The Linux app id and the Windows AUMID must match (Phase 61 D-01)."""
    assert constants.APP_ID == "org.lightningjim.MusicStreamer"


def test_bundled_desktop_basename_matches_app_id():
    """packaging/linux/<APP_ID>.desktop must exist."""
    pkg_dir = Path(__file__).parent.parent / "packaging" / "linux"
    expected = pkg_dir / f"{constants.APP_ID}.desktop"
    assert expected.exists(), (
        f"Bundled .desktop name must match constants.APP_ID. "
        f"Looked for: {expected}. "
        f"Found .desktop files in {pkg_dir}: "
        f"{sorted(p.name for p in pkg_dir.glob('*.desktop'))}"
    )


def test_bundled_icon_basename_matches_app_id():
    """packaging/linux/<APP_ID>.png must exist."""
    pkg_dir = Path(__file__).parent.parent / "packaging" / "linux"
    expected = pkg_dir / f"{constants.APP_ID}.png"
    assert expected.exists()


def test_no_org_example_literal_remains_in_python_sources():
    """No code or asset under musicstreamer/ should reference the old placeholder."""
    pkg_root = Path(__file__).parent.parent / "musicstreamer"
    needle = "org.example.MusicStreamer"
    hits = []
    for py in pkg_root.rglob("*.py"):
        try:
            text = py.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if needle in text:
            hits.append(str(py.relative_to(pkg_root.parent)))
    assert not hits, f"Phase 61 left placeholder behind in: {hits}"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Bare `WM_CLASS` matching to dock entries | Layered: `_GTK_APPLICATION_ID` first, then `WM_CLASS class → StartupWMClass`, then `WM_CLASS instance → StartupWMClass`, then `.desktop` basename matches | GNOME 3.10+ (2013-08 commit per `mail.gnome.org/archives/commits-list/2013-August/msg01635.html`) | The `_GTK_APPLICATION_ID` route is the simplest match path and the one Qt6's `setDesktopFileName` populates directly. Project relies on this path. [CITED] |
| `dbus-python` + `DBusGMainLoop` for MPRIS | `PySide6.QtDBus` `QDBusAbstractAdaptor` | Phase 41 (v2.0) | Already done; Phase 61 changes only the property value, not the framework. |
| Hardcoded `org.example.*` placeholder | Single-source `constants.APP_ID` | Phase 61 (this) | Lockstep across Linux + Windows; future renames become one-literal edits. |
| Manual `make install` for `.desktop` deployment | Pure-Python `desktop_install.ensure_installed()` on first launch | Phase 61 (this) | No more "did you remember to run make install" friction; works without sudo, without `make`. |
| `update-desktop-database` "for everything" superstition | Best-effort hook ONLY (D-13) | Always — but reaffirmed | The tool builds the MIME-cache; GNOME Shell uses `inotify` (`GAppInfoMonitor`) to detect new `.desktop` files in real time, so the cache is NOT load-bearing for the force-quit scenario. [CITED: glib gdesktopappinfo.c] |

**Deprecated/outdated:**
- The repo-root `org.example.MusicStreamer.desktop` placeholder. Renamed and relocated by this phase; the old basename is retired.
- The `Makefile` `make install` target (legacy GTK-era) — still works after the rename, but `uv run musicstreamer` + auto-install is the canonical dev path now. Plan can either fix the Makefile or strip it; either is fine. Recommend FIX (drift cleanup).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `setDesktopFileName(constants.APP_ID)` populates `_GTK_APPLICATION_ID` (and `_KDE_NET_WM_DESKTOP_FILE`) on X11, AND `xdg_toplevel.app_id` on Wayland, on Qt 6.11.0. | Pattern 1, Architecture diagram | LOW — verified directly in the qtbase XCB source at `qxcbwindow.cpp:396-419`. Wayland behavior is documented in the Qt mailing list discussion that motivated `setDesktopFileName`'s introduction. [VERIFIED: github.com/qt/qtbase qxcbwindow.cpp + quassel/quassel#489 PR] |
| A2 | GNOME Shell's force-quit dialog uses the same `ShellWindowTracker` match algorithm as Activities/Alt-Tab/dock indicators. | Pattern 1 | LOW — `ShellWindowTracker` is the only window-to-app mapping in GNOME Shell for X11/Wayland windows; force-quit is a thin caller of that mapping. [VERIFIED: gitlab.gnome.org/GNOME/gnome-shell/-/merge_requests/84] |
| A3 | The class half of `WM_CLASS` from Qt6 is `applicationName()` verbatim (no first-char-uppercase mangling) when `applicationName()` is non-empty. | Pattern 1 — claim that "MusicStreamer" matches StartupWMClass=MusicStreamer | LOW — confirmed in `qxcbintegration.cpp::wmClass()` source: the uppercase-first-char fallback ONLY fires when `applicationName()` is empty AND the executable basename has a lowercase first char. With `setApplicationName("MusicStreamer")` already in place, the class half is "MusicStreamer". [VERIFIED: codebrowser.dev/qt6 + github.com/qt/qtbase qxcbintegration.cpp ~lines 527-552] |
| A4 | `gnome-shell` 50.1 uses the same lookup chain as the 2013 commit. | Pattern 1 | LOW — GNOME has refined the algorithm (sandboxed-app-id support added in MR !84, ~2017-2018), but the WM_CLASS / `_GTK_APPLICATION_ID` / StartupWMClass priority order has been stable since 2013. The MR !84 change made WM_CLASS preferred OVER sandboxed app id, which only strengthens this phase's reliance on WM_CLASS + `_GTK_APPLICATION_ID`. |
| A5 | `~/.local/share/applications/` is monitored by `inotify` via `GDesktopAppInfo`, so a freshly-installed `.desktop` file is visible to GNOME Shell within seconds. | Don't-Hand-Roll, Anti-Patterns | LOW — confirmed in `glib/gio/gdesktopappinfo.c` and the `GAppInfoMonitor` API contract. [VERIFIED: github.com/GNOME/glib gdesktopappinfo.c] |
| A6 | The single 256×256 hicolor bucket is sufficient for force-quit dialog icon display on GNOME 50. | Standard Stack — Alternatives Considered | MEDIUM — GNOME's icon-loading code prefers the requested size if available, downscales if necessary. The force-quit dialog typically displays icons at 32–64px. 256×256 downscales cleanly; the dev rig already has 64/128/256 buckets installed. **Mitigation:** if 256×256 alone is insufficient, the install routine can be extended to install multiple buckets in a follow-up patch. Pre-existing icons on Kyle's rig also covers the case. [CITED: developer.gnome.org/documentation/tutorials/themed-icons.html] |
| A7 | `Exec=musicstreamer` resolves correctly when the app is launched via the `.desktop` file from Activities. | Code Examples — Example 5 | MEDIUM — `Exec=musicstreamer` works only if the `musicstreamer` Python entry-point script is on `$PATH`. Under `uv run musicstreamer`, uv injects it for the current shell only — Activities-launched processes inherit the user's session `$PATH`, which may NOT have the venv. **For the force-quit UAT (D-16), the app is launched via `uv run musicstreamer` from a terminal**, not from Activities — so `Exec` doesn't matter for the gate. **For "double-click app icon in Activities to launch"** (a stretch goal not in the success criteria), the user would need either a venv-activating wrapper script or a `pip install --user musicstreamer` that puts the entry point on PATH. **Recommend the planner audits Exec= during the rename plan and either keeps it as-is (sufficient for the gate) or upgrades to a fully-qualified path / wrapper script (out of scope for BUG-08).** |
| A8 | The `gtk-update-icon-cache` and `update-desktop-database` calls are best-effort — failure is fine. | Don't-Hand-Roll, Pitfall section | LOW — both tools are designed to be idempotent and tolerant of missing inputs. The shell's directory-scan fallback covers the absent-cache case. |
| A9 | No external client (Soundcloud, Spotify, MPV, KDE Connect, etc.) depends on the placeholder `org.example.MusicStreamer` literal. | User Constraints, Stored data category | LOW — the literal was a placeholder shipped only in dev runs of a single-user app on Kyle's machine. The MPRIS bus name (which IS what external clients consume) is `org.mpris.MediaPlayer2.musicstreamer` and is unchanged (D-04). |

## Open Questions (RESOLVED)

### 1. WM_CLASS mechanics on Qt6/X11 — does Qt need `-name argv` injection? **RESOLVED: NO.**

**What we know (verified):**
- Qt6 XCB plugin sets `WM_CLASS` instance from: `-name <argv>` flag → `RESOURCE_NAME` env var → argv[0] basename. (Qt parses argv before stripping recognized flags.)
- Qt6 XCB plugin sets `WM_CLASS` class from: `QCoreApplication::applicationName()` (already `"MusicStreamer"` per `__main__.py:143`). Falls back to argv[0] basename with first-char-uppercased ONLY when applicationName is empty.
- `setDesktopFileName` does NOT influence `WM_CLASS`. It populates `_GTK_APPLICATION_ID` and `_KDE_NET_WM_DESKTOP_FILE` (X11) and `xdg_toplevel.app_id` (Wayland).
- GNOME Shell's match chain tries `_GTK_APPLICATION_ID` FIRST (highest priority) before falling back to `WM_CLASS`.

**What's unclear:** Nothing — fully resolved.

**Recommendation:** **Do NOT inject `-name MusicStreamer` into argv.** Two reasons:
1. With `_GTK_APPLICATION_ID = "org.lightningjim.MusicStreamer"` matching the installed `.desktop` basename, GNOME's match chain hits step 1 and short-circuits. The WM_CLASS instance string is never consulted.
2. With `setApplicationName("MusicStreamer")` already in place, the WM_CLASS class string is `"MusicStreamer"`, which matches `StartupWMClass=MusicStreamer` in step 2 anyway. The instance string is a 3rd/4th fallback — irrelevant.

**`-name MusicStreamer` is YAGNI for this phase.**

### 2. GNOME Shell force-quit dialog lookup chain. **RESOLVED.**

The chain is documented above (Pattern 1). On X11: `_GTK_APPLICATION_ID` → `WM_CLASS class → StartupWMClass` → `WM_CLASS instance → StartupWMClass` → `WM_CLASS class → .desktop basename` → `WM_CLASS instance → .desktop basename`. All comparisons are case-sensitive. On Wayland: `xdg_toplevel.app_id → .desktop basename` is the equivalent, with no `WM_CLASS` fallback (Wayland has no analog). [CITED: mail.gnome.org/archives/commits-list/2013-August/msg01635.html + gitlab.gnome.org/GNOME/gnome-shell/-/merge_requests/84]

### 3. XDG search path priority. **RESOLVED.**

`$XDG_DATA_HOME:$XDG_DATA_DIRS`, with default `$HOME/.local/share:/usr/local/share:/usr/share`. **User-installed wins over system.** No `update-desktop-database` is required for GNOME Shell to discover a new `.desktop` file in `~/.local/share/applications/` — the shell uses `inotify` via `GAppInfoMonitor`. [CITED: specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html + GNOME GLib gdesktopappinfo.c]

### 4. Icon resolution. **RESOLVED.**

`Icon=org.lightningjim.MusicStreamer` resolves through the freedesktop Icon Theme spec lookup — for each theme in the active theme's parent chain (defaulting to `hicolor`), search each size-bucket dir under `$XDG_DATA_DIRS/icons/<theme>/<size>/apps/<icon>.{png,svg,xpm}`. **256×256 single-bucket is sufficient for GNOME** (the GNOME Shell default; force-quit dialog displays at 32-64px and downscales cleanly). `gtk-update-icon-cache` is a performance optimization — when the cache is absent, GNOME falls back to a directory scan. **Plan the install at 256×256 single-bucket; SVG not required.** [CITED: specifications.freedesktop.org/icon-theme/latest + developer.gnome.org/documentation/tutorials/themed-icons.html]

### 5. `update-desktop-database` and `gtk-update-icon-cache` necessity. **RESOLVED.**

Both are **best-effort optimizations**, NOT required for the GNOME Shell window-to-app match chain:
- `update-desktop-database` — builds `mimeinfo.cache` for MIME-handler associations (e.g., "Open With..." menus). Not consulted by the force-quit / Activities lookup. Harmless to run.
- `gtk-update-icon-cache` — builds `icon-theme.cache` for fast icon resolution by GTK apps. Not consulted by GNOME Shell when absent (falls back to directory scan). Harmless to run.

**Failure mode if not run:** Negligible. The app still works; force-quit dialog still resolves; icon still displays. The cache helps OTHER apps (e.g., `xdg-open`) start faster on subsequent launches, but is not load-bearing for this phase. **Recommend the install routine call both (best-effort), per D-13.**

### 6. Idempotent self-install pattern in Python. **RESOLVED.**

See Pattern 2 + Example code above. Mirrors `migration.run_migration()` exactly: marker-file guard (one-shot), atomic write via `tmp + os.replace`, best-effort post-install hooks via `subprocess.run` wrapped in `_best_effort()`, no-op on non-Linux platforms.

### 7. Timing in `__main__.py::_run_gui`. **RESOLVED.**

The shell's window-to-app lookup happens **out-of-process at force-quit time**, not at app startup. So timing of the install routine relative to `QApplication(...)` is **NOT critical for the running window's lookup**.

It IS critical for "first launch shows correct identity" if the user immediately opens Activities or triggers force-quit on the very first launch BEFORE the install routine has fired. The proposed slot — between `Gst.init(None)` and `migration.run_migration()`, BEFORE `QApplication(...)` — runs the install BEFORE any window is created, so the very first window is correctly identified.

**Recommendation: ship the install at the proposed slot.** It runs ~10ms (file copy + subprocess), is invisible to startup latency, and ensures first-launch correctness.

### 8. Diagnostic command set for `61-DIAGNOSTIC-LOG.md`. **RESOLVED.**

See Example 6 above for the complete command set. Confirmed:
- All commands work without elevated privileges.
- All commands are present on Kyle's rig (verified 2026-05-05).
- Wayland session caveat: `xprop` won't work on native Wayland windows — instruct Kyle to log into "GNOME on Xorg" first (Pitfall 8).

### 9. Test surface. **RESOLVED.**

- `desktop_install.py` — fully unit-testable on Linux CI with `tmp_path` + `monkeypatch` for `XDG_DATA_HOME` + `paths._root_override`. No X11/Wayland required. ~6-8 tests cover the happy path, idempotency, off-Linux no-op, existing-file preservation, missing-cache-tool resilience, and best-effort hook invocation.
- Drift-guard tests (Pitfall 6 / Example 7) — pure file-existence checks, no Qt or GLib dependency. ~4 tests; lockstep guard for the rename.
- Qt API wiring (`setDesktopFileName`, `setApplicationDisplayName`) — existing pattern is "no test for `__main__.py` Qt-init code" per Phase 56's precedent. Sanity test optional; if shipped, would assert `constants.APP_ID == "org.lightningjim.MusicStreamer"` and that the literal is referenced in `__main__.py` (1-line `re.search`).
- WM_CLASS / force-quit / Activities behavior — **human-UAT only on Kyle's rig**. Not unit-testable without a display server.

### 10. Drift sites after rename. **RESOLVED — one MORE site found beyond CONTEXT.md.**

`grep -rn "org\.example" .` (excluding `.git/` and `.planning/`) on the repo, 2026-05-05, returns:
- `Makefile` lines 5, 6, 32, 43 — **CONTEXT.md does NOT enumerate this**. Pitfall 1.
- `musicstreamer/__main__.py:144`
- `musicstreamer/constants.py:17`
- `musicstreamer/media_keys/mpris2.py:104`
- `org.example.MusicStreamer.desktop` (repo root file — to be renamed; not a literal-in-source).

**Plan must include the Makefile fix.** With `constants.APP_ID` as single source AND the drift-guard tests (Pitfall 6 / Example 7), structural drift is closed by construction post-rename. Future copy-paste typos are caught by `test_no_org_example_literal_remains_in_python_sources()`.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10+ | All work | ✓ (per pyproject `requires-python = ">=3.10"`) | venv: 3.12 | — |
| pytest 9+ | Wave 0/1 unit tests | ✓ (per `[project.optional-dependencies].test`) | per pyproject | — |
| PySide6 / Qt 6.11.0 | `setApplicationDisplayName`, `setDesktopFileName` API | ✓ | 6.11.0 | — |
| `platformdirs` | `paths.data_dir()` install marker location | ✓ (transitively pinned) | per pyproject | — |
| Linux dev box (Kyle's X11 rig) | UAT for force-quit + Activities | ✓ | Ubuntu/Debian-style, GNOME Shell 50.1 | — |
| Linux X11 session | Force-quit UAT (`xprop` requires X11) | ✓ (Kyle can log into "GNOME on Xorg" if currently on Wayland) | — | If unable to switch off Wayland: skip the WM_CLASS readout, use `gdbus org.gnome.Shell.Eval` for `_GTK_APPLICATION_ID` introspection (gnarly; needs unsafe-mode-shell on GNOME 41+). **Recommend X11 session approach.** |
| `xprop` | Diagnostic step 3 | ✓ `/usr/bin/xprop` | — | — |
| `xdotool` | Non-interactive window-find | ✓ `/usr/bin/xdotool` | — | Manual click target via `xprop WM_CLASS` (interactive) |
| `gnome-shell` | Version readout | ✓ `/usr/bin/gnome-shell` | 50.1 | — |
| `update-desktop-database` | Best-effort install hook (D-13) | ✓ `/usr/bin/update-desktop-database` | — | Skip silently — not load-bearing for the force-quit gate |
| `gtk-update-icon-cache` | Best-effort install hook (D-13) | ✓ `/usr/bin/gtk-update-icon-cache` | — | Skip silently — directory-scan fallback works |
| `gsettings` | Sanity readout for diagnostic | ✓ `/usr/bin/gsettings` | — | Skip — diagnostic remains complete |
| `busctl` | MPRIS sanity readout | ✓ (systemd core) | — | Skip — diagnostic remains complete |
| Bundled `packaging/linux/org.lightningjim.MusicStreamer.png` (1024×1024) | Self-install icon source | ✓ | 1024×1024 PNG, 53 KB | — |
| `~/.local/share/applications/` writable | Self-install destination | ✓ | dir exists, mode 0700 | If user has chmod'd to read-only, install gracefully fails and re-tries on next launch (no marker written). |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None for the gate path. Only the diagnostic captures Wayland-vs-X11 differences and recommends switching sessions — but that's a UAT precondition, not a code-path fallback.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9+ + pytest-qt 4+ (per `pyproject.toml [project.optional-dependencies].test`) |
| Config file | `pyproject.toml [tool.pytest.ini_options]` — `testpaths = ["tests"]`, `markers: integration` |
| Quick run command | `pytest tests/test_desktop_install.py tests/test_constants_drift.py -x` |
| Full suite command | `pytest` (uses pyproject testpaths) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BUG-08 | `desktop_install.ensure_installed()` writes `.desktop` + icon to XDG paths on first call | unit | `pytest tests/test_desktop_install.py::test_first_launch_installs_files -x` | ❌ Wave 0 |
| BUG-08 | `desktop_install.ensure_installed()` is idempotent (marker prevents repeat install) | unit | `pytest tests/test_desktop_install.py::test_idempotent_via_marker -x` | ❌ Wave 0 |
| BUG-08 | `desktop_install` is a no-op on non-Linux platforms | unit | `pytest tests/test_desktop_install.py::test_no_op_off_linux -x` | ❌ Wave 0 |
| BUG-08 | Existing user-modified `.desktop` is preserved (not overwritten) | unit | `pytest tests/test_desktop_install.py::test_existing_files_preserved -x` | ❌ Wave 0 |
| BUG-08 | Best-effort hooks (`update-desktop-database`, `gtk-update-icon-cache`) are invoked | unit | `pytest tests/test_desktop_install.py::test_cache_hooks_called_best_effort -x` | ❌ Wave 0 |
| BUG-08 | Missing cache tool does not raise (FileNotFoundError caught) | unit | `pytest tests/test_desktop_install.py::test_missing_cache_tool_does_not_raise -x` | ❌ Wave 0 |
| BUG-08 | `constants.APP_ID == "org.lightningjim.MusicStreamer"` (drift guard) | unit | `pytest tests/test_constants_drift.py::test_app_id_is_lightningjim_and_matches_phase_56_aumid -x` | ❌ Wave 0 |
| BUG-08 | `packaging/linux/<APP_ID>.desktop` exists on disk (drift guard) | unit | `pytest tests/test_constants_drift.py::test_bundled_desktop_basename_matches_app_id -x` | ❌ Wave 0 |
| BUG-08 | `packaging/linux/<APP_ID>.png` exists on disk (drift guard) | unit | `pytest tests/test_constants_drift.py::test_bundled_icon_basename_matches_app_id -x` | ❌ Wave 0 |
| BUG-08 | No `org.example.MusicStreamer` literal remains in `musicstreamer/` Python sources (drift guard) | unit | `pytest tests/test_constants_drift.py::test_no_org_example_literal_remains_in_python_sources -x` | ❌ Wave 0 |
| BUG-08 | GNOME force-quit dialog reads "MusicStreamer" on Kyle's X11 rig (success criterion #1) | UAT (manual) | manual UAT script — Example 6 step 9 | n/a — D-16 gate |
| BUG-08 | Activities/Alt-Tab show "MusicStreamer" on Kyle's X11 rig (success criterion #2) | UAT (manual) | manual UAT script — Example 6 step 10 | n/a — CONTEXT.md success criterion #2 |
| BUG-08 | App ID migrated to `org.lightningjim.MusicStreamer`; D-Bus interface names unchanged (success criterion #3 — amended) | unit + manual | drift-guard tests + `busctl --user list` shows `org.mpris.MediaPlayer2.musicstreamer` | n/a — D-04 |
| BUG-08 | Fix works on X11; Wayland behavior noted as side-effect (success criterion #4) | UAT (manual + memo) | UAT log captures X11 behavior; CONTEXT.md notes Wayland not a gate | n/a |

### Sampling Rate

- **Per task commit:** `pytest tests/test_desktop_install.py tests/test_constants_drift.py -x` (~3-5 s)
- **Per wave merge:** `pytest` full suite (~30-60 s on dev box)
- **Phase gate:** Full suite green + `61-DIAGNOSTIC-LOG.md` POST-FIX section captured + UAT signoff per D-16 before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_desktop_install.py` — NEW. ~6-8 tests for the install routine. ~80-120 LOC.
- [ ] `tests/test_constants_drift.py` — NEW. ~4 drift-guard tests. ~30-40 LOC.
- [ ] No framework install needed — pytest + pytest-qt + qtbot fixture all in current `pyproject.toml`.
- [ ] No new `conftest.py` fixtures needed — `tmp_path` + `monkeypatch` are pytest built-ins.

## Security Domain

> **`security_enforcement` is not explicitly disabled in `.planning/config.json`** — therefore enabled. Threat audit follows.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth surface in this phase |
| V3 Session Management | no | No session state created |
| V4 Access Control | yes | Self-install writes to `~/.local/share/` (user-owned); never `/usr/share/` (would require root). Verified by inspection of Pattern 2 install destinations. |
| V5 Input Validation | yes | The bundled `.desktop` file content is project-controlled (committed to repo); no untrusted input flows into the install routine. The XDG paths are derived from environment variables (`$HOME`, `$XDG_DATA_HOME`) — same trust model as `migration.py` and `paths.py`. |
| V6 Cryptography | no | No crypto |
| V12 File and Resource | yes | Atomic write via `os.replace` prevents partial-state corruption on crash. Mode bits preserved via `shutil.copy2`. No symlink-following (using `Path.exists()` / `os.replace` defaults). |

### Known Threat Patterns for Linux self-install routines

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via env var injection (e.g., `$XDG_DATA_HOME=../../etc`) | Tampering | The install routine writes to `$XDG_DATA_HOME/applications/<APP_ID>.desktop` where APP_ID is a project-controlled constant (`org.lightningjim.MusicStreamer`) with no path separators. Even with a hostile `$XDG_DATA_HOME`, the writes land under the attacker-controlled directory — same trust as anything else respecting XDG. **No new attack surface; no mitigation needed beyond using `Path` operations correctly.** |
| Symlink race in user dir | Tampering | The install routine uses `os.replace(tmp, dst)` which replaces atomically and does NOT follow symlinks at the target. `shutil.copy2` follows source symlinks (irrelevant — source is project-controlled) but writes to the resolved tmp file before atomic-replace. **Low risk; existing migration.py uses the same pattern.** |
| Subprocess command injection via XDG path | Tampering / EoP | `_best_effort(["update-desktop-database", str(desktop_dst.parent)])` — the path is passed as a list element, NOT shelled out, so no shell injection possible. **Mitigated by construction — `subprocess.run` with `list[str]` and no `shell=True`.** |
| Marker-file race (two app instances racing first-launch install) | Tampering | The single-instance guard in `__main__.py::_run_gui` (`single_instance.acquire_or_forward()`) runs AFTER `desktop_install.ensure_installed()` in the proposed wire-in order. So if two app instances launch concurrently, both might attempt the install. The `if not exists` guards on `desktop_dst.exists()` and `icon_dst.exists()` are technically TOCTOU — but both writes go through `os.replace(tmp, dst)` which is atomic, so the worst case is the same byte content written twice. **No corruption; acceptable.** |
| Marker file content reveals secrets | Information Disclosure | Marker content is `"desktop install v1 complete; app_id=org.lightningjim.MusicStreamer\n"` — no secrets. **No mitigation needed.** |
| Stale `.desktop` from previous version retains old `Exec=` to a now-missing binary | Denial-of-Service (mild) | If the user later renames their venv path AND the install marker remains AND the bundled `Exec=` updates in a future phase, Activities-launched processes may fail to spawn. Out of scope for THIS phase (`Exec=musicstreamer` is unchanged). Future phase that updates `Exec=` should consider a marker version bump (`.desktop-installed-v2`) to force re-install. |

**Summary:** Self-install in user-owned XDG paths is a low-risk operation. Existing project patterns (`migration.py`, `cookie_utils.py`) already handle the relevant edge cases (atomic write, mode preservation, idempotency). No new mitigations needed.

## Sources

### Primary (HIGH confidence)

- **`musicstreamer/constants.py:17`** — current `APP_ID` placeholder. [Read 2026-05-05]
- **`musicstreamer/__main__.py:99-125, 142-144`** — current `_set_windows_aumid` + `setDesktopFileName` wiring. [Read 2026-05-05]
- **`musicstreamer/media_keys/mpris2.py:55-58, 102-104`** — MPRIS bus name + `DesktopEntry` property. [Read 2026-05-05]
- **`musicstreamer/migration.py`** — first-launch one-shot pattern (marker-guarded, atomic-write). [Read 2026-05-05]
- **`musicstreamer/paths.py`** — `paths._root_override` test hook + `migration_marker()` shape. [Read 2026-05-05]
- **`musicstreamer/single_instance.py:29`** — already on `org.lightningjim` (reference precedent for the rename). [Read 2026-05-05]
- **`tests/test_migration.py`** — `tmp_path` + `monkeypatch._root_override` test pattern. [Read 2026-05-05]
- **`org.example.MusicStreamer.desktop`** (repo root) — current bundled file content. [Read 2026-05-05]
- **`packaging/linux/org.lightningjim.MusicStreamer.png`** — 1024×1024, 53 KB, ready for install. [`identify` 2026-05-05]
- **`Makefile`** — line 5/6/32/43 — drift site #4 not enumerated in CONTEXT.md. [Read 2026-05-05]
- **`.planning/phases/56-windows-di-fm-smtc-start-menu/56-CONTEXT.md`** — diagnose-first pattern (D-07, D-08), AUMID single-source intent (D-09 #3). [Read 2026-05-05]
- **`.planning/phases/56-windows-di-fm-smtc-start-menu/56-RESEARCH.md`** — depth precedent + diagnostic command set convention. [Read 2026-05-05]
- **`.planning/phases/56-windows-di-fm-smtc-start-menu/56-03-DIAGNOSTIC-LOG.md`** — diagnostic-log artifact convention. [Read 2026-05-05]
- **`.claude/skills/spike-findings-musicstreamer/SKILL.md`** — confirmed Linux-WM topic NOT covered (Windows-only skill). [Inferred 2026-05-05 by grepping `references/`]
- **Qt6 source — `qtbase/src/plugins/platforms/xcb/qxcbintegration.cpp` `wmClass()` ~lines 527-552** — the canonical answer for WM_CLASS construction. [WebFetch via codebrowser.dev/qt6 + github.com/qt/qtbase 2026-05-05]
- **Qt6 source — `qtbase/src/plugins/platforms/xcb/qxcbwindow.cpp` lines 389-419** — `_GTK_APPLICATION_ID` and `_KDE_NET_WM_DESKTOP_FILE` setting. [WebFetch via codebrowser.dev/qt6 + github.com/qt/qtbase 2026-05-05]

### Secondary (MEDIUM confidence — verified against Qt source / GNOME source)

- [QGuiApplication Class | Qt 6.11.0](https://doc.qt.io/qt-6/qguiapplication.html) — `desktopFileName`, `applicationDisplayName`, `applicationName` property docs (`.desktop` suffix stripping confirmed). [WebFetch + Context7 2026-05-05]
- [Quassel PR #489 — qtui: Set desktop file name](https://github.com/quassel/quassel/pull/489) — canonical explanation of why `setDesktopFileName` matters on Wayland but is no-op on X11 for WM_CLASS. [WebFetch 2026-05-05]
- [GNOME Shell MR !84 — window-tracker WM_CLASS sandboxed apps](https://gitlab.gnome.org/GNOME/gnome-shell/-/merge_requests/84) — match-chain priority. [WebFetch 2026-05-05]
- [GNOME Shell commit 2013-08 — Use StartupWMClass to associate window and applications](https://mail.gnome.org/archives/commits-list/2013-August/msg01635.html) — original match-algorithm specification (case-sensitive, ordered). [WebFetch 2026-05-05]
- [Martin Gräßlin — Porting Qt applications to Wayland](https://blog.martin-graesslin.com/blog/2015/07/porting-qt-applications-to-wayland/) — Wayland icon-via-`.desktop` mechanism. [WebFetch 2026-05-05]
- [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html) — search path priority. [WebSearch 2026-05-05]
- [Icon Theme Specification](https://specifications.freedesktop.org/icon-theme/latest/) — hicolor lookup, size buckets, scalable directory semantics. [WebSearch 2026-05-05]
- [GNOME Themed Icons tutorial](https://developer.gnome.org/documentation/tutorials/themed-icons.html) — 256×256 default size for GNOME, 48×48 minimum recommendation. [WebSearch 2026-05-05]
- [`update-desktop-database(1)` man page (Ubuntu)](https://manpages.ubuntu.com/manpages/focal/en/man1/update-desktop-database.1.html) — confirmed it builds the MIME-cache, NOT load-bearing for window-app matching. [WebFetch 2026-05-05]
- [`gtk-update-icon-cache(1)` man page](https://linuxcommandlibrary.com/man/gtk-update-icon-cache) — best-effort, fallback works without it. [WebSearch 2026-05-05]
- [GLib `GAppInfoMonitor` / `gdesktopappinfo.c`](https://github.com/GNOME/glib/blob/main/gio/gdesktopappinfo.c) — confirmed `~/.local/share/applications/` is monitored via inotify. [WebSearch 2026-05-05]

### Tertiary (LOW confidence — verified by domain reasoning, not single-sourced)

- "GNOME Shell 50.1 retains the same match-chain priority as 2013/2017 commits" — A4. Verified by absence of breaking-change merge requests; not by reading the current source. **Risk:** if a recent shell change reordered the chain, the analysis still holds because the match would only be MORE permissive (additional app-id sources). **Mitigation:** UAT on Kyle's actual rig confirms behavior end-to-end.
- "256×256 single-bucket icon install is sufficient for GNOME force-quit dialog" — A6. Reasoning sound; not empirically benchmarked across icon sizes 32–256. **Mitigation:** Kyle's rig already has 64/128/256 icons from earlier manual install; if the routine is idempotent against existing files (designed-for), no harm done either way.

## Metadata

**Confidence breakdown:**
- App ID rename + single-source via `constants.APP_ID`: **HIGH** — three Python files, one Makefile, one `.desktop` file rename, all line-precise; drift-guard tests close the loop.
- `setApplicationDisplayName` belt-and-suspenders: **HIGH** — Qt 6.11.0 API confirmed, harmless one-liner.
- WM_CLASS / `_GTK_APPLICATION_ID` / GNOME match chain: **HIGH** — verified directly in qtbase XCB source AND GNOME shell match-algo commits. The phase relies on `_GTK_APPLICATION_ID` (highest-priority match path) which Qt populates from `setDesktopFileName`.
- Self-install routine design + tests: **HIGH** — mirrors `migration.py` exactly; pure stdlib; `tmp_path` test harness already proven in `tests/test_migration.py`.
- Diagnostic command set: **HIGH** — all commands verified present on Kyle's rig (2026-05-05); X11 vs. Wayland branch handled.
- Icon size bucket selection (256×256 single): **MEDIUM** — pre-existing icons on Kyle's rig confirm reasonable defaults; if a rare bucket (say 96×96) is needed for some specific dialog, the routine can extend to multi-bucket trivially.
- Stale-file (`org.example.MusicStreamer.desktop`) interaction risk: **MEDIUM** — Pitfall 3 documents the layered-`.desktop` ambiguity; UAT script must verify the marker exists to avoid false-positive UAT pass. **Recommend Kyle manually `rm` the stale file as a one-shot post-fix step (not a code task).**

**Research date:** 2026-05-05
**Valid until:** 2026-06-05 (XDG specs + Qt6 X11 plugin + GNOME match algorithm are all stable; if more than 30 days elapse before execution, re-confirm Qt 6.11 still pinned via `python -c "from PySide6 import QtCore; print(QtCore.qVersion())"` — no other re-verification needed)
