# Stack Research — v2.2 Packaging and QOL

**Project:** MusicStreamer v2.2
**Researched:** 2026-05-25
**Scope:** Stack additions/changes for the new v2.2 features ONLY. Existing v2.1 stack (Python 3.11+, PySide6 6.10+, GStreamer 1.28, conda-forge build env, PyInstaller + Inno Setup, yt-dlp library API with `extractor_args={'youtubepot-jsruntime': {'remote_components': ['ejs:github']}}`, streamlink, urllib, winrt-Windows.Media.* 3.2.x, chardet>=5,<6, Node.js runtime) is documented in `.planning/codebase/STACK.md` and intentionally not duplicated here.
**Confidence:** HIGH (existing v2.1 stack stays untouched; new tooling cross-verified against official docs and Flathub maintainer-maintained recipes)

---

## Recommended Stack — Additions for v2.2

### Core Technologies (NEW)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **linuxdeploy** | continuous (download `linuxdeploy-x86_64.AppImage` at build time, SHA-pinned in CI) | AppDir maintenance + AppImage assembly | The canonical, actively-maintained tool for building AppImages. AppImageKit's `appimagetool` only packs an AppDir; linuxdeploy *also* discovers + bundles binary deps (Qt, libgstreamer-1.0.so.0, etc.) via its plugin system. Used in production by KDE, Subsurface, FreeCAD, Krita. |
| **linuxdeploy-plugin-gstreamer** | continuous (download `linuxdeploy-plugin-gstreamer.sh` at build time) | Bundles GStreamer plugin .so files + `gst-plugin-scanner` into the AppDir; installs the AppRun hook that sets `GST_PLUGIN_PATH` / `GST_PLUGIN_SCANNER` / `GIO_EXTRA_MODULES` at launch | Direct Linux analogue of our existing `packaging/windows/runtime_hook.py`. Without it the AppImage launches but every codec fails — `playbin3` finds no decoders. **Caveat:** plugin is officially "experimental"; budget time for hand-curating `GSTREAMER_PLUGINS_DIR` / `GSTREAMER_HELPERS_DIR` env vars if the conda-forge plugin layout differs from Debian. |
| **linuxdeploy-plugin-conda** | continuous (download `linuxdeploy-plugin-conda.sh` at build time) | Sets up a miniconda env inside the AppDir and installs packages from `CONDA_PACKAGES` / `CONDA_CHANNELS` | **Critical integration point.** Lets the AppImage build consume the *same conda-forge recipe* the Windows build proves out (`pyside6`, `gstreamer=1.28`, `gst-libav`, `gst-plugins-{base,good,bad,ugly}`, `chardet>=5,<6`, `nodejs`). One source of truth across Linux + Windows packaging; no PyInstaller-vs-AppImage divergence. |
| **flatpak-builder** | 1.4.x (Debian/Fedora package; or `org.flatpak.Builder` from Flathub) | Builds Flatpak bundles from a YAML/JSON manifest | The only official Flatpak build tool. Required for Flathub submission. |
| **`io.qt.PySide.BaseApp`** (Flatpak base) | branch `6.8` (`base-version: '6.8'`) | Pre-built PySide6 + Qt 6.8 layered on top of `org.kde.Platform//6.8` | Saves ~30 min of build time per CI run vs. building PySide6 from source. **Maintained branches as of 2026-05: 6.8, 6.9, 6.10.** Pick 6.8 for LTS stability — matches the conda-forge pyside6 6.10 feature surface we already validated, and KDE runtime 6.8 is mature on Flathub. |
| **`org.kde.Platform` / `org.kde.Sdk`** (Flatpak runtime) | `6.8` | KDE Platform runtime (extends `org.freedesktop.Platform`) — Qt 6.8, QtWebEngine, GStreamer 1.x base | Required when using the PySide BaseApp. GStreamer base libs ship in the runtime; codec extensions layer on via `add-extensions`. |
| **`org.freedesktop.Platform.ffmpeg-full`** (Flatpak extension) | `24.08` (matches the 24.08-based KDE 6.8 runtime) | Provides FFmpeg libs for GStreamer's `gst-libav` (`avdec_aac` / `avdec_h264` / etc.) inside the sandbox | **Direct analogue of `gst-libav` in our conda recipe.** Without this, AAC playback (DI.fm / AudioAddict / SomaFM AAC tier) silently fails inside the sandbox — same failure mode Phase 69 closed on Windows. Mount via `add-extensions` to `/app/lib/ffmpeg` with `add-ld-path: "."`. |
| **pywin32** | `>=308` ; pin explicitly in `pyproject.toml`'s `optional-dependencies.windows` | `IShellLink` + `IPropertyStore` + `PKEY_AppUserModel_ID` to write AUMID onto a `.lnk` Start-Menu shortcut from Python at runtime | The path that lets us **self-heal the AUMID shortcut from Python at first launch** if the Inno installer's shortcut got removed/replaced by an upgrade, AV software, or imaging tool. The existing Inno `AppUserModelID:` clause stays the *primary* mechanism — pywin32 is the runtime fallback. |

### Supporting Libraries (NEW)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **`flatpak-pip-generator`** | latest from `flatpak/flatpak-builder-tools` repo | Resolves `pip` deps into a build-manifest fragment (URL + sha256 per wheel) — required because Flathub builds run **offline** | Run once whenever `pyproject.toml`'s dependency set changes. Generates `python3-modules.yaml` committed to the Flathub manifest repo. **Do NOT** re-run on every build — the generated file is checked in. |
| **`appstreamcli`** | from system `appstream` package | Validates AppStream metadata (`org.lightningjim.MusicStreamer.metainfo.xml`) required by both AppImage (desktop-integration tools consume it) and Flathub (mandatory). | Pre-flight check in CI: `appstreamcli validate org.lightningjim.MusicStreamer.metainfo.xml`. |
| **`desktop-file-validate`** | from `desktop-file-utils` system package | Validates the `.desktop` launcher entry shipped with the AppImage + Flatpak | Pre-flight check in CI. Same `.desktop` template feeds both packaging targets. |
| **`http.cookiejar` (stdlib)** | stdlib | Convert `QNetworkCookie` objects emitted by `QWebEngineCookieStore.cookieAdded` into Mozilla-format cookie file for urllib reuse (GBS.FM marquee fetch) | Bridge layer between Phase 76's QtWebEngine login subprocess and the new urllib scraper. No new dep; mirrors the v1.5 Phase 23 / v2.0 Phase 999.7 YouTube cookie pattern. |

### Development Tools (NEW)

| Tool | Purpose | Notes |
|------|---------|-------|
| **`appstream-util` (from `appstream-glib`)** | Alt validator for AppStream XML | Use as a secondary cross-check if `appstreamcli` flags ambiguities. |
| **`shellcheck`** | Lint the new `packaging/linux/build-appimage.sh` driver | Mirror of how `build.ps1` is hand-audited for PowerShell gotchas (the userMemory `reference_gsd_sdk_wrapper`-style lessons apply). |
| **`yamllint`** | Lint Flatpak manifest YAML pre-submission | Flathub CI runs its own validation but local lint shortens iteration. |

---

## v2.2 Feature-by-Feature Integration Plan

### 1. Linux AppImage packaging (NEW packaging target)

**Recommended approach:** conda-plugin-driven, **NOT** PyInstaller-driven.

```bash
# packaging/linux/build-appimage.sh (sketch)
export CONDA_CHANNELS=conda-forge
export CONDA_PACKAGES="python=3.12 pyside6 gstreamer=1.28 gst-libav \
                      gst-plugins-base gst-plugins-good gst-plugins-bad gst-plugins-ugly \
                      chardet>=5,<6 nodejs"
export PIP_REQUIREMENTS="yt-dlp streamlink platformdirs"

./linuxdeploy-x86_64.AppImage --appdir AppDir \
    --plugin conda \
    --plugin gstreamer \
    --desktop-file packaging/linux/org.lightningjim.MusicStreamer.desktop \
    --icon-file packaging/linux/icons/org.lightningjim.MusicStreamer.png \
    --output appimage
```

**Why conda-plugin not PyInstaller:**

- Reuses the **exact** conda recipe the Windows build proves out. Eliminates a divergence risk: AppImage shipping a different GStreamer plugin set than the Windows installer would create platform-specific bug classes (cf. Phase 69 WIN-05 — that bug existed precisely because the Windows env didn't match Linux). Single conda source of truth eliminates this category.
- PyInstaller-into-AppImage works (the AppImage wiki documents it) but means maintaining two PyInstaller specs (Windows + Linux variants) for the same Python codebase, doubling the surface area for bundling regressions.
- conda-plugin handles Node.js bundling automatically (`nodejs` is a conda-forge package) — solves the RUNTIME-01 "Node on PATH" prerequisite by shipping Node *inside* the AppImage. AppImage portability promise is preserved.

**What NOT to add:**

- ~~PyInstaller for Linux~~ — duplicates conda-plugin work, no benefit.
- ~~`appimage-builder` (the YAML-recipe tool)~~ — competitor to linuxdeploy with weaker GStreamer plugin support; community momentum is on linuxdeploy.
- ~~`python-appimage`~~ — useful for shipping bare Python interpreters; doesn't bundle Qt/GStreamer/PySide6, would still need linuxdeploy on top.

**Build host requirement:** Build the AppImage on the **oldest supported glibc** (Ubuntu 22.04 or a manylinux_2_28 container) for max forward compatibility. AppImage links against host glibc — building on Arch/Fedora-rawhide produces AppImages that won't run on Ubuntu LTS users' machines.

### 2. Linux Flatpak packaging (NEW packaging target)

**Recommended manifest skeleton** (`packaging/linux/org.lightningjim.MusicStreamer.yaml`):

```yaml
id: org.lightningjim.MusicStreamer
runtime: org.kde.Platform
runtime-version: '6.8'
sdk: org.kde.Sdk
base: io.qt.PySide.BaseApp
base-version: '6.8'
command: musicstreamer

finish-args:
  - --share=network
  - --share=ipc
  - --socket=wayland
  - --socket=fallback-x11
  - --socket=pulseaudio
  - --device=dri
  - --filesystem=xdg-music:ro
  # MPRIS2 (Linux media-key integration via existing QtDBus service)
  - --own-name=org.mpris.MediaPlayer2.MusicStreamer
  # Required for QtWebEngine (GBS.FM login + YouTube cookie login) to persist cookies via libsecret
  - --talk-name=org.freedesktop.secrets

add-extensions:
  org.freedesktop.Platform.ffmpeg-full:
    directory: lib/ffmpeg
    version: '24.08'
    add-ld-path: '.'
    autodownload: true
    autodelete: false

cleanup-commands:
  - mkdir -p /app/lib/ffmpeg
  - /app/cleanup-BaseApp.sh

modules:
  - python3-modules.yaml   # generated via flatpak-pip-generator, checked in
  - name: musicstreamer
    buildsystem: simple
    build-commands:
      - pip3 install --prefix=/app --no-deps .
      - install -Dm644 packaging/linux/org.lightningjim.MusicStreamer.desktop \
          /app/share/applications/org.lightningjim.MusicStreamer.desktop
      - install -Dm644 packaging/linux/icons/org.lightningjim.MusicStreamer.png \
          /app/share/icons/hicolor/256x256/apps/org.lightningjim.MusicStreamer.png
      - install -Dm644 packaging/linux/org.lightningjim.MusicStreamer.metainfo.xml \
          /app/share/metainfo/org.lightningjim.MusicStreamer.metainfo.xml
    sources:
      - type: dir
        path: ../..
```

**Why these specific choices:**

- **`io.qt.PySide.BaseApp` branch 6.8** over a from-source PySide6 build: cuts CI time from ~45min to ~8min. Branch 6.8 is the stable current; 6.9/6.10 are available but KDE runtime 6.8 is the LTS-track on Flathub.
- **`org.freedesktop.Platform.ffmpeg-full` 24.08** for `gst-libav`: this is the Phase 69 lesson applied to Linux. AAC/AAC+/H.264 codecs require FFmpeg under the hood; the base GStreamer in the freedesktop runtime *intentionally* omits patent-encumbered codecs. **Without this extension, DI.fm/AudioAddict/SomaFM AAC streams will silently fail inside the sandbox.**
- **`--share=network`**: required for HTTP streaming + Helix/iTunes/MB/AA APIs.
- **`--socket=pulseaudio`**: PipeWire on modern hosts handles this transparently; PulseAudio socket is the portable contract Flathub expects.
- **`--socket=wayland` + `--socket=fallback-x11`**: aligned with the userMemory deployment-target note (Wayland-first, never X11 on the dev rig — but Flathub expects fallback for compatibility).
- **`--filesystem=xdg-music:ro`**: future-proofs a "scan local Music dir for cover art" feature without re-submitting permissions.
- **`--own-name=org.mpris.MediaPlayer2.MusicStreamer`**: required for OS media keys to bind via the existing QtDBus MPRIS2 service. Without this `finish-args` line, MPRIS2 silently no-ops inside the sandbox.
- **`--talk-name=org.freedesktop.secrets`**: lets QtWebEngine's session cookies persist via libsecret (used for both GBS.FM login state and YouTube cookies).

**Flatpak does NOT use conda.** This is the one departure from the AppImage path: Flathub's reproducible-build policy forbids conda. Use `flatpak-pip-generator` to lock pip deps into a manifest fragment.

**Submission target:** Flathub. PR against `flathub/flathub`; on acceptance the manifest moves to a dedicated `github.com/flathub/org.lightningjim.MusicStreamer` repo.

### 3. yt-dlp channel-avatar fetch (NEW field extraction)

**Verified behavior (yt-dlp current as of 2026-05):** `yt_dlp.YoutubeDL().extract_info(video_url, download=False)` returns:

- `thumbnail` — the *video* thumbnail (what we use today)
- `thumbnails` — array of every available thumbnail variant
- `uploader_url` — channel handle URL (`https://www.youtube.com/@LofiGirl`); **NULL for auto-generated topic channels** (Auto-generated by YouTube — yt-dlp issue #7521)
- `channel_url` — channel ID URL (`https://www.youtube.com/channel/UCSJ4gkVC6NrvII8umztf0Ow`); always present
- `channel_id`, `channel` — IDs and display name

**The video-level `info_dict` does NOT include the channel `avatar_url` directly.** Two known-current paths:

**Path A — second `extract_info` call against the channel URL** (recommended):

```python
import yt_dlp

with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': 'in_playlist'}) as ydl:
    info = ydl.extract_info(channel_url, download=False)
    # thumbnails[].id values from YoutubeChannel extractor:
    #   'avatar_uncropped', 'banner_uncropped', 'tv_banner', ...
    avatar = next(
        (t['url'] for t in info.get('thumbnails', []) if t.get('id') == 'avatar_uncropped'),
        None,
    )
```

`alexwlchan`'s 2025 yt-dlp wrapper documents this exact pattern; yt-dlp issue #10090 confirms the `avatar_uncropped` field name is current for the YoutubeChannel extractor.

**Path B — InnerTube `channel/about` page** (advanced; defer unless Path A misses cases):

```python
ydl.extract_info(f'https://www.youtube.com/channel/{channel_id}/about', ...)
```

Often returns more thumbnail variants but is heavier (additional InnerTube roundtrip).

**Recommendation:** Path A. One additional `extract_info` call against `channel_url` (which we already have from the original video extraction). Cache the result by `channel_id` for the session — channel avatars change rarely. **No new library deps.**

**Caveat (HIGH confidence on field names, MEDIUM on permanence):** yt-dlp's `thumbnails[].id` schema has survived multiple releases but is not a contract — YouTube can change InnerTube responses at any time. Wrap the extraction in `try/except` and fall back to the existing video thumbnail.

### 4. Twitch Helix channel image (NEW endpoint)

**Endpoint:** `GET https://api.twitch.tv/helix/users?login=<channel_login>`

**Auth (verified against Twitch official docs):**

- Accepts **either** app access token OR user access token
- **No scopes required** for `profile_image_url` (it's public profile data)
- **The Phase 32 TAUTH user OAuth token can be reused as-is** — no new auth flow needed

**Required headers:**

- `Client-ID: <your_twitch_client_id>` (same client ID we use for `streamlink`)
- `Authorization: Bearer <oauth_token>` (the TAUTH-stored token)

**Response fields** (per official Twitch docs, verified):

- `id`, `login`, `display_name`, `type`, `broadcaster_type`, `description`
- `profile_image_url` — **this is what we want** (typically `https://static-cdn.jtvnw.net/jtv_user_pictures/<hash>-profile_image-300x300.png`)
- `offline_image_url`, `view_count`, `created_at`
- `email` — only returned if `user:read:email` scope present (we don't request it)

**Implementation:** Add a small helper to `musicstreamer/cover_art.py` or a new `musicstreamer/twitch_meta.py`:

```python
def fetch_twitch_channel_image(login: str, client_id: str, oauth_token: str) -> str | None:
    req = urllib.request.Request(
        f"https://api.twitch.tv/helix/users?login={login}",
        headers={"Client-ID": client_id, "Authorization": f"Bearer {oauth_token}"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
        users = data.get("data", [])
        return users[0]["profile_image_url"] if users else None
```

**Rate limit:** Twitch Helix is 800 points/min for app token (higher for user tokens). Get Users costs 1 point per call. Negligible at our scale — one call per Twitch station at edit/add time, then cached.

**No new library deps.** Uses existing `urllib` per project convention.

### 5. Windows SMTC AUMID Start-Menu shortcut (NEW Python code path)

**Two layers — Inno (primary) + pywin32 (fallback / self-heal):**

**Primary (already working in v2.0/v2.1):** Inno Setup writes the AUMID directly onto the `.lnk` via the `AppUserModelID:` clause in `MusicStreamer.iss` (already present at line 71). This is the canonical Microsoft pattern.

**NEW for v2.2 — `pywin32` self-heal on first launch:** If the shortcut is missing or the AUMID was stripped (Windows imaging tools, AV software, manual user copy), the app recreates it on launch.

**Library:** `pywin32` — confirmed approach via `win32com.shell.shellcon`, `win32com.propsys.propsys`, `pscon.PKEY_AppUserModel_ID`. Verified Python recipe (from Microsoft Win32 docs + the `Robertof/make-shortcut-with-appusermodelid` reference repo):

```python
from win32com.shell import shellcon
from win32com.propsys import propsys, pscon
import pythoncom

shortcut_path = os.path.expandvars(
    r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\MusicStreamer.lnk"
)
# 1. Create the .lnk via the existing pywin32 IShellLink path (well-documented pattern).
# 2. Then set the AUMID via IPropertyStore:
store = propsys.SHGetPropertyStoreFromParsingName(
    shortcut_path, None, shellcon.GPS_READWRITE, propsys.IID_IPropertyStore,
)
store.SetValue(
    pscon.PKEY_AppUserModel_ID,
    propsys.PROPVARIANTType('org.lightningjim.MusicStreamer', pythoncom.VT_LPWSTR),
)
store.Commit()
```

**Why pywin32 not comtypes or winrt:**

- `winrt` (already in our stack for SMTC *playback*) does **not** expose `IPropertyStore` / `PKEY_AppUserModel_ID`. Those are classic Win32 Shell APIs, not WinRT projections.
- `comtypes` would work but requires us to declare the COM interface signatures by hand. pywin32 ships them prebuilt as `propsys.IID_IPropertyStore` + `pscon.PKEY_AppUserModel_ID` constants.
- pywin32 is *already* a transitive dependency in the bundle (multiple Windows-only Python packages pull it). No new install footprint.

**Dependency addition:** Add `pywin32 ; sys_platform == 'win32'` explicitly to `pyproject.toml`'s `optional-dependencies.windows` so we control the version pin instead of relying on transitive inclusion. Recommend `pywin32>=308`.

**AUMID string parity guard (existing test extension):** `tests/test_aumid_string_parity.py` enforces lockstep between `musicstreamer/__main__.py::_set_windows_aumid` default arg and the Inno `.iss` clause. Extend the existing test to also grep the new pywin32 self-heal module for the same AUMID literal — drift across three sites breaks SMTC binding silently with no build error.

### 6. GBS.FM authenticated session reuse (QtWebEngine -> urllib)

**The interop problem:** Phase 76 established the GBS login via a QtWebEngine subprocess that ends up with valid session cookies in Chromium's cookie store. The v2.2 marquee + themed-logo scrapers want to fetch authenticated HTML using `urllib` (project convention) — but the cookies are inside `QWebEngineCookieStore`, not on disk in Mozilla format.

**Recommended approach (HIGH confidence — Qt API directly supports it):**

```python
# In the QtWebEngine login subprocess, after successful login:
import http.cookiejar
from PySide6.QtWebEngineCore import QWebEngineProfile
from PySide6.QtNetwork import QNetworkCookie

cookie_jar = http.cookiejar.MozillaCookieJar()

def _on_cookie_added(c: QNetworkCookie):
    if 'gbs.fm' not in bytes(c.domain()).decode():
        return
    ck = http.cookiejar.Cookie(
        version=0,
        name=bytes(c.name()).decode(), value=bytes(c.value()).decode(),
        port=None, port_specified=False,
        domain=bytes(c.domain()).decode(), domain_specified=True, domain_initial_dot=False,
        path=bytes(c.path()).decode(), path_specified=True,
        secure=c.isSecure(),
        expires=int(c.expirationDate().toSecsSinceEpoch()) if not c.isSessionCookie() else None,
        discard=c.isSessionCookie(),
        comment=None, comment_url=None, rest={},
    )
    cookie_jar.set_cookie(ck)

# IMPORTANT — use a named profile with persistent storage, NOT defaultProfile():
profile = QWebEngineProfile("MusicStreamer-GBS", parent)
profile.setPersistentCookiesPolicy(QWebEngineProfile.AllowPersistentCookies)
profile.setPersistentStoragePath(str(GBS_PROFILE_DIR))
store = profile.cookieStore()
store.cookieAdded.connect(_on_cookie_added)
store.loadAllCookies()  # triggers cookieAdded for every persistent cookie

# Then serialize for the urllib scraper:
cookie_jar.save(str(GBS_COOKIES_PATH), ignore_discard=True, ignore_expires=False)
```

Then the in-process marquee scraper (running in the main MusicStreamer process, not the QtWebEngine subprocess) uses:

```python
jar = http.cookiejar.MozillaCookieJar(str(GBS_COOKIES_PATH))
jar.load(ignore_discard=True, ignore_expires=False)
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
opener.open('https://gbs.fm/whatever-authed-endpoint')
```

**Why this approach:**

- **No new library deps.** Uses `http.cookiejar` (stdlib) + existing PySide6 `QtWebEngineCore`.
- Reuses the **same temp-cookies-file pattern** established for YouTube cookies in `musicstreamer/cookie_utils.py` (v2.0 Phase 999.7) — single cookie-handling idiom across both YouTube and GBS.
- `loadAllCookies()` emitting `cookieAdded` for every loaded cookie is **documented Qt behavior** (verified against current Qt 6.10 official docs).

**Critical gotcha — cookie persistence scope:** `QWebEngineProfile.defaultProfile()` defaults to **off-the-record** (no persistence between subprocess runs). For session cookies to survive, the login subprocess MUST use an *explicit non-default named profile* with persistent storage (see snippet above — `setPersistentCookiesPolicy` + `setPersistentStoragePath`). Many third-party tutorials skip this and silently lose session cookies on subprocess restart.

**Alternative considered and rejected:** Running the scrape inside QtWebEngine via `runJavaScript()`. Works but heavier (full Chromium per fetch) and harder to test. The cookie-export path keeps the scraper as a pure-Python urllib call, testable in isolation against fixture HTML.

---

## Installation

The v2.2 additions are split across three install surfaces:

```bash
# 1. Linux AppImage build host (one-time)
sudo apt install fuse libfuse2 wget appstream desktop-file-utils
wget -O linuxdeploy-x86_64.AppImage \
    https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage
wget -O linuxdeploy-plugin-conda.sh \
    https://raw.githubusercontent.com/linuxdeploy/linuxdeploy-plugin-conda/master/linuxdeploy-plugin-conda.sh
wget -O linuxdeploy-plugin-gstreamer.sh \
    https://raw.githubusercontent.com/linuxdeploy/linuxdeploy-plugin-gstreamer/master/linuxdeploy-plugin-gstreamer.sh
chmod +x linuxdeploy-*

# 2. Linux Flatpak build host (one-time)
sudo apt install flatpak flatpak-builder
flatpak remote-add --user --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak install --user flathub org.kde.Platform//6.8 org.kde.Sdk//6.8 io.qt.PySide.BaseApp//6.8

# 3. Windows runtime (pyproject.toml `optional-dependencies.windows`)
# Add: pywin32 >= 308  (already in transitive scope; pin explicitly for v2.2)
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| linuxdeploy + conda-plugin (AppImage) | `appimage-builder` (YAML recipe tool) | If we *don't* want to share the Windows conda recipe and prefer pure Debian/Ubuntu apt sources. We do share, so linuxdeploy wins. |
| linuxdeploy + conda-plugin (AppImage) | PyInstaller → appimagetool | If we already had a stable Linux PyInstaller spec. We don't (Windows-only spec), and creating one would double the PyInstaller maintenance surface. |
| `io.qt.PySide.BaseApp` (Flatpak) | Build PySide6 from source in the manifest | If we needed a PySide6 version newer than BaseApp's 6.10 branch. We don't (6.8 covers all v2.1 surface). |
| `org.freedesktop.Platform.ffmpeg-full` (Flatpak) | `org.freedesktop.Platform.codecs-extra` | When targeting Freedesktop SDK 25.08+. The KDE 6.8 runtime is still on 24.08, so `ffmpeg-full` is correct *for our chosen base*. Revisit when we move to KDE 6.10/6.11. |
| pywin32 (AUMID shortcut self-heal) | `comtypes` | If we wanted zero pywin32 surface. pywin32 is too well-established and *already in our bundle* — abandoning it for one use case is net-negative. |
| pywin32 (AUMID shortcut self-heal) | A separate C# helper EXE shipped in the installer | Overkill — installer is already Inno Setup, and the `.iss` `AppUserModelID:` clause is the primary path. pywin32 is only the self-heal fallback. |
| `http.cookiejar` cookie export (GBS) | Run scrape inside QtWebEngine via `runJavaScript` | If GBS pages depend on JS that urllib can't run. Phase 76 confirmed the marquee + logo URL endpoints are server-rendered HTML, so urllib suffices. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `pyfladesk` / `cefpython3` for GBS auth | Both unmaintained as of 2024+; pyfladesk last release 2019. We already have QtWebEngine working in Phase 76. | Existing PySide6 QtWebEngine subprocess (Phase 76 baseline). |
| `python-appimage` standalone | Bundles only the Python interpreter — no Qt, no GStreamer. Would still need linuxdeploy on top. Adds complexity for zero benefit. | `linuxdeploy-plugin-conda` end-to-end. |
| `winshell` for AUMID shortcut creation | winshell is a thin wrapper over pywin32 IShellLink but does **not** wrap IPropertyStore — can't set AUMID. | pywin32 directly (`propsys.SHGetPropertyStoreFromParsingName`). |
| `org.gnome.Platform` runtime for Flatpak | Our app is Qt-based; GNOME Platform doesn't ship Qt and would duplicate everything BaseApp gives us. | `org.kde.Platform` + `io.qt.PySide.BaseApp`. |
| Twitch's deprecated v5 Kraken `users/<id>` endpoint | Sunset 2022. Returns 404 today. | Helix `GET /helix/users?login=<name>`. |
| `--socket=x11` only in Flatpak | Breaks Wayland (our deployment target per MEMORY). | `--socket=wayland` + `--socket=fallback-x11`. |
| Default `QWebEngineProfile.defaultProfile()` for GBS login | Off-the-record by default — session cookies vanish between subprocess runs. | Named profile + `setPersistentCookiesPolicy(AllowPersistentCookies)` + explicit `setPersistentStoragePath`. |
| `requests` library for Twitch Helix call | Project convention is `urllib` (existing `Key Decisions` row in PROJECT.md). | `urllib.request.Request` with `Client-ID` + `Authorization` headers. |

## Stack Patterns by Variant

**If shipping to Flathub (recommended for v2.2 distribution path):**

- Use `io.qt.PySide.BaseApp` (cheap CI, vetted base)
- Submit AppStream metadata + screenshots — Flathub *requires* both
- Manifest repo lives at `github.com/flathub/org.lightningjim.MusicStreamer` (separate from main project repo, post-acceptance)
- Auto-update is handled by the Flathub infra — no in-app updater work

**If shipping AppImage outside any store:**

- linuxdeploy + conda-plugin + gstreamer-plugin
- Host the `.AppImage` on GitHub Releases (auto-update via [AppImageUpdate](https://github.com/AppImage/AppImageUpdate) is *optional*; per PROJECT.md v2.2 expectation is manual download)
- Sign the `.AppImage` with a GPG key if/when we have one; not blocking for v2.2

**If user wants Windows SMTC binding without launching via Start Menu shortcut:**

- The Inno `.lnk` AUMID is the primary path. The pywin32 self-heal is the **only** alternative; there is no "set AUMID without a shortcut" Win32 API for non-MSIX apps. `SetCurrentProcessExplicitAppUserModelID` alone is necessary-but-not-sufficient — the shortcut still has to carry the matching AUMID for SMTC overlay binding (this lesson is already documented in `packaging/windows/README.md` "Launching MusicStreamer (SMTC overlay binding)").

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `io.qt.PySide.BaseApp` `6.8` | `org.kde.Platform` `6.8`, `org.kde.Sdk` `6.8` | All three branch versions MUST match. Mixing `6.8` BaseApp with `6.10` runtime crashes at startup with unhelpful symbol-mismatch errors. |
| `org.freedesktop.Platform.ffmpeg-full` `24.08` | KDE Platform `6.8` (built on FDO `24.08`) | Pin to the FDO version under the chosen KDE runtime, NOT the KDE version. |
| linuxdeploy-plugin-conda | linuxdeploy `continuous` | The plugin tracks linuxdeploy's bleeding edge. Pin both by SHA in CI for reproducibility. |
| linuxdeploy-plugin-gstreamer | linuxdeploy `continuous`, GStreamer `>=1.20` | Plugin is officially experimental; budget time for manual `GSTREAMER_PLUGINS_DIR` override if auto-detection fails on conda layout. |
| pywin32 `>=308` | Python `>=3.10`, Windows `>=10` | `pscon.PKEY_AppUserModel_ID` and `propsys` modules require pywin32 ≥225. Modern (308+) gives us bug-fixed `PROPVARIANTType` constructor. |
| QtWebEngine cookie store (cookieAdded + loadAllCookies) | PySide6 `>=6.8` (matches v2.1 6.10 floor) | API stable since Qt 5.11. No upgrade pressure. |
| yt-dlp channel-URL `thumbnails[].id == 'avatar_uncropped'` | yt-dlp `>=2024.x` | Field name appears stable in YoutubeChannel extractor since at least 2024. Wrap in try/except — InnerTube responses change without notice. |
| Twitch Helix `GET /users` | TAUTH OAuth token (Phase 32) OR Twitch app access token | Either works for `profile_image_url`. No new scope. |

---

## Sources

- [linuxdeploy GitHub](https://github.com/linuxdeploy/linuxdeploy) — HIGH (canonical tool repo, actively maintained)
- [linuxdeploy-plugin-conda](https://github.com/linuxdeploy/linuxdeploy-plugin-conda) — HIGH (conda integration pattern verified)
- [linuxdeploy-plugin-gstreamer](https://github.com/linuxdeploy/linuxdeploy-plugin-gstreamer) — MEDIUM (experimental marker noted by maintainer; GST_PLUGIN_PATH wiring confirmed)
- [niess/linuxdeploy-plugin-python](https://github.com/niess/linuxdeploy-plugin-python) — MEDIUM (alternative considered + rejected)
- [Bundling Python apps · AppImage/AppImageKit Wiki](https://github.com/AppImage/AppImageKit/wiki/Bundling-Python-apps) — HIGH
- [Flatpak docs — Manifests](https://docs.flatpak.org/en/latest/manifests.html) — HIGH
- [Flatpak docs — Extensions](https://docs.flatpak.org/en/latest/extension.html) — HIGH
- [Flatpak docs — Python](https://docs.flatpak.org/en/latest/python.html) — HIGH
- [Flatpak docs — Available Runtimes](https://docs.flatpak.org/en/latest/available-runtimes.html) — HIGH
- [flathub/io.qt.PySide.BaseApp](https://github.com/flathub/io.qt.PySide.BaseApp) — HIGH (current branches 6.8/6.9/6.10 verified; cleanup-BaseApp.sh pattern documented)
- [develop.kde.org — Publishing your Python app as a Flatpak](https://develop.kde.org/docs/getting-started/python/python-flatpak/) — HIGH
- [flathub/org.freedesktop.Platform.ffmpeg](https://github.com/flathub/org.freedesktop.Platform.ffmpeg) — HIGH
- [Twitch Helix Reference — Get Users](https://dev.twitch.tv/docs/api/reference/) — HIGH (`profile_image_url` field + no-scope requirement confirmed)
- [Twitch Authentication — Scopes](https://dev.twitch.tv/docs/authentication/scopes/) — HIGH
- [yt-dlp issue #10090 — channel thumbnails & avatar_uncropped](https://github.com/yt-dlp/yt-dlp/issues/10090) — MEDIUM (field-name confirmation)
- [yt-dlp issue #7521 — uploader_url null for topic channels](https://github.com/yt-dlp/yt-dlp/issues/7521) — MEDIUM
- [alexwlchan — Creating a personal wrapper around yt-dlp (2025)](https://alexwlchan.net/2025/yt-dlp-wrapper/) — MEDIUM (reproducible Python recipe)
- [yt-dlp DeepWiki — Information Extraction Pipeline](https://deepwiki.com/yt-dlp/yt-dlp/2.2-information-extraction-pipeline) — MEDIUM
- [Qt 6.10 — QWebEngineCookieStore](https://doc.qt.io/qt-6/qwebenginecookiestore.html) — HIGH
- [Qt for Python 6 — QWebEngineCookieStore](https://doc.qt.io/qtforpython-6/PySide6/QtWebEngineCore/QWebEngineCookieStore.html) — HIGH
- [Qt for Python 6 — QWebEngineProfile (setPersistentCookiesPolicy)](https://doc.qt.io/qtforpython-6/PySide6/QtWebEngineCore/QWebEngineProfile.html) — HIGH
- [Microsoft Learn — Application User Model IDs (AppUserModelIDs)](https://learn.microsoft.com/en-us/windows/win32/shell/appids) — HIGH (authoritative AUMID + IPropertyStore docs)
- [Robertof/make-shortcut-with-appusermodelid](https://github.com/Robertof/make-shortcut-with-appusermodelid) — MEDIUM (pywin32 recipe pattern)
- [Tim Golden's pywin32 docs — SetCurrentProcessExplicitAppUserModelID](https://timgolden.me.uk/pywin32-docs/shell__SetCurrentProcessExplicitAppUserModelID_meth.html) — HIGH
- Existing project: `/home/kcreasey/OneDrive/Projects/MusicStreamer/packaging/windows/MusicStreamer.iss` — HIGH (current Inno installer with AUMID clause at line 71)
- Existing project: `/home/kcreasey/OneDrive/Projects/MusicStreamer/packaging/windows/MusicStreamer.spec` — HIGH (current PyInstaller spec)
- Existing project: `/home/kcreasey/OneDrive/Projects/MusicStreamer/packaging/windows/README.md` — HIGH (conda-forge recipe documented; SMTC overlay binding documented)
- Existing project: `/home/kcreasey/OneDrive/Projects/MusicStreamer/.planning/codebase/STACK.md` — HIGH (v2.1 validated baseline)

---

*Stack research for: MusicStreamer v2.2 packaging + UI polish (Linux AppImage + Linux Flatpak + YouTube channel-avatar fetch + Twitch Helix channel image + Windows SMTC AUMID self-heal shortcut + GBS.FM authenticated session reuse)*
*Researched: 2026-05-25*
