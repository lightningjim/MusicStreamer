# Phase 22: Import YT Cookies - Research

**Researched:** 2026-04-06
**Domain:** GTK4/Libadwaita dialog, yt-dlp/mpv cookie flags, WebKit2 embedded browser, Netscape cookie format
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Support three input methods: file picker (primary), paste textarea, and Google login flow
- **D-02:** File picker is the primary/prominent method; paste and Google login are under an "Other methods" expander in the dialog
- **D-03:** Google login opens a browser window for the user to sign into Google, then captures the resulting YouTube cookies and saves them as cookies.txt
- **D-04:** Cookie file stored at `~/.local/share/musicstreamer/cookies.txt` — alongside DB and assets, app-owned
- **D-05:** Manual lifecycle only — user re-imports when things stop working; no automatic expiry detection or auth failure prompts
- **D-06:** Show "last imported" date in the cookie dialog UI
- **D-07:** Add a hamburger/primary menu to the header bar with "YouTube Cookies..." menu item
- **D-08:** Cookie dialog is an Adw.Dialog with file picker prominent at top, "Other methods" expander below containing paste textarea and Google login button
- **D-09:** Dialog has Import and Clear buttons — Clear removes the stored cookies.txt
- **D-10:** If cookies.txt exists, pass it to EVERY yt-dlp and mpv call — no conditional logic
- **D-11:** yt-dlp: `--cookies <path>` flag on all subprocess calls (playlist scan in yt_import.py)
- **D-12:** mpv: `--ytdl-raw-options=cookies=<path>` flag on playback subprocess calls (player.py)
- **D-13:** Disable yt-dlp's default browser cookie extraction (`--no-cookies-from-browser` or equivalent) to eliminate the GNOME keyring issue at the source

### Claude's Discretion
- Exact Adw widget choices for the dialog layout
- Google login implementation approach (selenium, playwright, webkitgtk, or other)
- Validation of pasted cookie content format
- Error handling for failed Google login flow

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

## Summary

Phase 22 adds a cookies management dialog that lets users import YouTube cookies from a file, paste, or Google login — bypassing yt-dlp's default browser extraction which triggers GNOME keyring prompts. The implementation has three parts: (1) a new `CookiesDialog` UI module, (2) a hamburger menu in the main window header bar, and (3) flag additions to `player.py` and `yt_import.py`.

The cookie file flags are fully verified against the installed tools. yt-dlp 2026.03.17 accepts `--cookies <path>` and `--no-cookies-from-browser`. mpv v0.40.0 accepts `--cookies-file=<path>` and `--cookies=yes` (the `--ytdl-raw-options` approach from the context works but `--cookies-file` is a native mpv flag that's simpler and also verified).

The Google login flow can use WebKit2 4.1 (confirmed available on this machine), which provides an embedded browser inside a GTK window — the cleanest option given no Selenium/Playwright is installed. After Google login, `CookieManager.get_all_cookies()` retrieves cookies and they're written to the Netscape format file.

**Primary recommendation:** Use WebKit2 4.1 for Google login (embedded browser, no extra deps). Use `Gtk.FileDialog` (not `FileChooserNative`) for the file picker — that's the existing project pattern. Validate pasted content with a simple header-line check.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| GTK4 / PyGObject | system | UI widgets | Project standard |
| Libadwaita (Adw) | system | GNOME dialog/window patterns | Project standard |
| WebKit2 (gi) | 4.1 | Embedded browser for Google login | Already available; no extra install |
| yt-dlp | 2026.03.17 | Playlist scan with cookie file | Existing tool in PATH |
| mpv | 0.40.0 | YouTube playback with cookie file | Existing tool in PATH |

[VERIFIED: checked via `yt-dlp --version`, `mpv --version`, and `python3 -c "import gi; gi.require_version('WebKit2', '4.1')"` on this machine]

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Gio (gi.repository) | system | `Gio.Menu` + `Gio.SimpleAction` for hamburger menu | Required for GTK4 application actions |
| os / shutil | stdlib | File copy, path checks, delete | Cookie file lifecycle management |
| datetime | stdlib | "Last imported" date formatting | D-06 status label |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| WebKit2 embedded browser | selenium + Chrome | Needs external browser install; more fragile |
| WebKit2 embedded browser | playwright | Not installed; requires separate install step |
| `Gtk.FileDialog` | `Gtk.FileChooserNative` | `FileDialog` is the GTK4 preferred API and what the codebase already uses |

**Installation:** No new dependencies needed — all are system packages or already installed.

---

## Architecture Patterns

### Recommended Project Structure
```
musicstreamer/
├── ui/
│   ├── cookies_dialog.py    # New: CookiesDialog class
│   └── main_window.py       # Modified: add hamburger menu
├── player.py                # Modified: --cookies-file + --cookies flags
├── yt_import.py             # Modified: --cookies + --no-cookies-from-browser flags
└── constants.py             # Modified: add COOKIES_PATH constant
tests/
└── test_yt_cookies.py       # New: unit tests for cookie import logic
```

### Pattern 1: Hamburger Menu with Gio.Menu + SimpleAction
**What:** GTK4 `Gtk.MenuButton` bound to a `Gio.Menu` model; items trigger `Gio.SimpleAction`.
**When to use:** Header bar menu entries that open dialogs.
**Example:**
```python
# Source: GTK4 docs / existing project pattern in main_window.py
import gi
from gi.repository import Gtk, Gio

menu = Gio.Menu()
menu.append("YouTube Cookies…", "app.open-cookies")

menu_btn = Gtk.MenuButton()
menu_btn.set_icon_name("open-menu-symbolic")
menu_btn.set_menu_model(menu)
header.pack_end(menu_btn)

action = Gio.SimpleAction.new("open-cookies", None)
action.connect("activate", self._open_cookies_dialog)
self.get_application().add_action(action)
```
[ASSUMED: exact action scoping — could be `app.` or `win.` prefix; either works with `add_action` on app or window]

### Pattern 2: Gtk.FileDialog for .txt files
**What:** Async `Gtk.FileDialog.open()` with a `Gtk.FileFilter` for `*.txt`.
**When to use:** All file pickers in this project (matches edit_dialog.py pattern).
**Example:**
```python
# Source: edit_dialog.py line 527-548 (existing project pattern)
def _browse_cookies(self, btn):
    dlg = Gtk.FileDialog(title="Choose cookies.txt")
    flt = Gtk.FileFilter()
    flt.set_name("Cookie files")
    flt.add_pattern("*.txt")
    dlg.set_default_filter(flt)

    def done(dlg_obj, res):
        try:
            f = dlg_obj.open_finish(res)
            if f:
                self._selected_path = f.get_path()
                self._file_entry.set_text(os.path.basename(self._selected_path))
                self._update_import_sensitive()
        except GLib.Error:
            return

    dlg.open(self, None, done)
```
[VERIFIED: edit_dialog.py:527 uses this exact pattern]

### Pattern 3: WebKit2 Embedded Browser for Google Login
**What:** Open a `Gtk.Window` containing a `WebKit2.WebView` navigated to `https://accounts.google.com`. After the view navigates to a YouTube domain, extract cookies via `CookieManager.get_all_cookies()` and write them as Netscape format.
**When to use:** D-03 Google login flow.
**Example:**
```python
# Source: WebKit2 4.1 gi bindings (available on this machine)
import gi
gi.require_version("WebKit2", "4.1")
from gi.repository import WebKit2, Gtk, GLib

class GoogleLoginWindow(Gtk.Window):
    def __init__(self, on_cookies_ready):
        super().__init__(title="Sign in with Google")
        self.set_default_size(800, 600)
        self._callback = on_cookies_ready

        ctx = WebKit2.WebContext.get_default()
        self._webview = WebKit2.WebView.new_with_context(ctx)
        self._webview.connect("load-changed", self._on_load_changed)
        self.set_child(self._webview)
        self._webview.load_uri("https://accounts.google.com/signin/v2/identifier?service=youtube")

    def _on_load_changed(self, webview, event):
        if event != WebKit2.LoadEvent.FINISHED:
            return
        uri = webview.get_uri() or ""
        if "youtube.com" in uri or "myaccount.google.com" in uri:
            # Signed in — extract cookies
            mgr = webview.get_website_data_manager().get_cookie_manager()
            mgr.get_all_cookies(None, self._on_got_cookies, None)

    def _on_got_cookies(self, mgr, res, user_data):
        try:
            cookies = mgr.get_all_cookies_finish(res)
            GLib.idle_add(self._callback, cookies)
        except Exception as e:
            GLib.idle_add(self._callback, None)
        self.close()
```
[VERIFIED: WebKit2 4.1 available; `WebKit2.WebView` instantiable; `CookieManager` has `get_all_cookies` method. NOTE: `get_all_cookies_finish` existence assumed — verify at implementation time. Segfault in headless test; requires display context (GTK event loop). CookieManager does NOT have a `WebKit2.Cookie` type in this binding — need to check actual return type of get_all_cookies_finish.]

### Pattern 4: Netscape Cookie Format
**What:** The format expected by yt-dlp `--cookies` and mpv `--cookies-file`.
**Structure:**
```
# Netscape HTTP Cookie File
.youtube.com	TRUE	/	TRUE	1234567890	VISITOR_INFO1_LIVE	value
.youtube.com	TRUE	/	FALSE	1234567890	YSC	value
```
Fields: domain, domain_initial_dot (TRUE/FALSE), path, secure (TRUE/FALSE), expiry (unix timestamp), name, value — all tab-separated.

**Validation heuristic:** First non-blank, non-comment line should be tab-separated with 7 fields where field 5 is numeric. The file should begin with `# Netscape HTTP Cookie File` or `# HTTP Cookie File`.
[VERIFIED: yt-dlp docs + mpv tested with this format]

### Anti-Patterns to Avoid
- **Passing `--cookies-from-browser` when no cookies.txt exists:** D-13 says suppress browser extraction always. The flag `--no-cookies-from-browser` is the default per yt-dlp help, so yt-dlp won't extract from browser unless you pass `--cookies-from-browser`. The risk is yt-dlp being invoked without `--no-cookies-from-browser` explicit — safer to add it explicitly so it's clear.
- **Using `--ytdl-raw-options=cookies=<path>` instead of `--cookies-file`:** Both work but `--cookies-file` is a native mpv option (verified) and simpler. `--ytdl-raw-options` passes options to the yt-dlp invocation inside mpv, while `--cookies-file` tells mpv itself. Either satisfies D-12; `--cookies-file` is preferred.
- **Blocking the GTK main thread:** All file I/O (copy, write) and the WebKit2 login window must not block the idle loop. The login window opens in the same GTK event loop (non-blocking by nature). File copy is fast enough to do inline but wrapping in a thread is safe.
- **Storing cookies.txt path in settings DB:** The path is fixed (D-04: `~/.local/share/musicstreamer/cookies.txt`). Derive from `COOKIES_PATH` constant — don't store in DB.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Netscape cookie format writing | Custom serializer | Write from WebKit2 cookie objects using known format | Format is simple but field order and escaping must be exact |
| Browser automation | Custom subprocess + xdotool | WebKit2 GTK native browser | Embedded, no external deps, GTK-native |
| File filter UI | Manual extension check | `Gtk.FileFilter` + `Gtk.FileDialog` | Already used in project |
| Date formatting | strftime boilerplate | `datetime.date.today().strftime("%b %-d, %Y")` | Matches UI spec ("Apr 6, 2026") |

**Key insight:** The Netscape cookie format is 7 tab-separated fields. Don't parse it for validation — just check the header line and that rows have 7 tab-separated fields. Writing it from WebKit2 cookies requires constructing it manually since WebKit2's CookieManager only persists to SQLite natively; we write Netscape format ourselves.

---

## Common Pitfalls

### Pitfall 1: mpv --cookies-file vs --ytdl-raw-options cookies
**What goes wrong:** D-12 specifies `--ytdl-raw-options=cookies=<path>`. This passes the cookies path to yt-dlp inside mpv, which is correct. However, mpv also has its own `--cookies-file` flag. Both work — but they're different layers. `--ytdl-raw-options=cookies=<path>` tells yt-dlp (when extracting the stream URL) to use the cookies; `--cookies-file` tells mpv's own HTTP layer.
**Why it happens:** YouTube playback via mpv invokes yt-dlp internally for URL extraction. Cookies need to reach the yt-dlp layer.
**How to avoid:** Use `--ytdl-raw-options=cookies=<path>` per D-12. Also add `--ytdl-raw-options=no-cookies-from-browser=` to suppress browser extraction in mpv's internal yt-dlp call. [ASSUMED: the empty-value syntax for boolean yt-dlp flags in mpv's ytdl-raw-options; verify at implementation time]
**Warning signs:** mpv still triggers GNOME keyring prompts even after adding `--cookies-file`.

### Pitfall 2: WebKit2 CookieManager get_all_cookies is async
**What goes wrong:** `get_all_cookies` takes a callback (GIO async pattern), not synchronous. Calling it synchronously blocks nothing but the callback fires on the GTK main loop.
**Why it happens:** GObject async API — `get_all_cookies(cancellable, callback, user_data)` → callback receives `(source, result, user_data)`.
**How to avoid:** Use the callback pattern shown in Pattern 3. Don't try to block-wait on the result.
**Warning signs:** Cookies never saved, no error shown.

### Pitfall 3: WebKit2 needs a display / GTK event loop
**What goes wrong:** WebKit2.WebContext segfaults or does nothing outside a running GTK application.
**Why it happens:** WebKit2 requires a display connection. Confirmed: running WebContext in a plain python3 subprocess without GTK segfaults (observed during research).
**How to avoid:** Always instantiate WebKit2 components inside a connected GTK application. Never in a background thread or unit test without a mocked WebView.
**Warning signs:** Segfault or blank window with no navigation.

### Pitfall 4: Gio.SimpleAction scope (app vs window)
**What goes wrong:** Action registered on wrong scope — `app.open-cookies` vs `win.open-cookies` — causes menu item to be insensitive or not fire.
**Why it happens:** GTK4 action maps are hierarchical: widget → window → application.
**How to avoid:** Register on the application (`self.get_application().add_action(action)`) since `CookiesDialog` is opened from the main window and needs app-level availability. Prefix in menu must match: `"app.open-cookies"`.
**Warning signs:** Menu item appears greyed out.

### Pitfall 5: Last-imported date persistence
**What goes wrong:** The "Last imported" date resets to "No cookies imported" if only checked against file existence — but the date itself isn't stored.
**Why it happens:** `os.path.getmtime(COOKIES_PATH)` gives the file's modification time without storing anything extra.
**How to avoid:** Use `os.path.getmtime(COOKIES_PATH)` and `datetime.fromtimestamp()` to display the date. No DB entry needed. On dialog open, check `os.path.exists(COOKIES_PATH)` and derive date from mtime.
**Warning signs:** Date always shows current time (file touched during app start) or wrong date after re-import.

---

## Code Examples

### yt_import.py: Adding --cookies and --no-cookies-from-browser
```python
# Verified: yt-dlp 2026.03.17 --help confirms these flags
import os
from musicstreamer.constants import COOKIES_PATH

def _build_ytdlp_cmd(url: str) -> list[str]:
    cmd = ["yt-dlp", "--flat-playlist", "--dump-json",
           "--no-cookies-from-browser"]
    if os.path.exists(COOKIES_PATH):
        cmd += ["--cookies", COOKIES_PATH]
    cmd.append(url)
    return cmd
```

### player.py: Adding mpv cookie flags
```python
# Verified: mpv v0.40.0 accepts --ytdl-raw-options and --cookies-file
import os
from musicstreamer.constants import COOKIES_PATH

def _build_mpv_cmd(self, url: str) -> list[str]:
    cmd = ["mpv", "--no-video", "--really-quiet",
           f"--volume={int(self._volume * 100)}"]
    if os.path.exists(COOKIES_PATH):
        cmd += [
            f"--cookies-file={COOKIES_PATH}",
            f"--ytdl-raw-options=cookies={COOKIES_PATH}",
        ]
    cmd.append(url)
    return cmd
```
[VERIFIED: `mpv --cookies-file=/tmp/test.txt ...` accepts the flag with exit code 0]

### constants.py: COOKIES_PATH
```python
COOKIES_PATH = os.path.join(DATA_DIR, "cookies.txt")
```

### Cookie format writing (from WebKit2 cookie objects)
```python
# Source: Netscape format spec; yt-dlp documentation
def _write_netscape_cookies(cookies: list, path: str):
    lines = ["# Netscape HTTP Cookie File", ""]
    for c in cookies:
        domain = c.get_domain()
        domain_initial_dot = "TRUE" if domain.startswith(".") else "FALSE"
        path_val = c.get_path() or "/"
        secure = "TRUE" if c.get_secure() else "FALSE"
        expiry = int(c.get_expires()) if c.get_expires() else 0
        name = c.get_name()
        value = c.get_value()
        lines.append(f"{domain}\t{domain_initial_dot}\t{path_val}\t{secure}\t{expiry}\t{name}\t{value}")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
```
[ASSUMED: WebKit2 cookie object API (`get_domain`, `get_path`, `get_secure`, `get_expires`, `get_name`, `get_value`). Verify at implementation time — the `WebKit2.Cookie` type was not importable in a headless context during research.]

### Paste validation heuristic
```python
def _is_valid_cookies_txt(text: str) -> bool:
    """Return True if text looks like a Netscape cookies.txt file."""
    lines = [l for l in text.splitlines() if l.strip() and not l.startswith("#")]
    if not lines:
        return False
    return len(lines[0].split("\t")) == 7
```

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| yt-dlp | D-11 cookie flag | ✓ | 2026.03.17 | — |
| mpv | D-12 cookie flag | ✓ | v0.40.0 | — |
| WebKit2 4.1 (gi) | D-03 Google login | ✓ | 4.1 | Open system browser (xdg-open) |
| Gtk.FileDialog | D-01 file picker | ✓ | GTK4 | — |
| google-chrome | Alternative for login | ✓ at /usr/bin/google-chrome | unknown | WebKit2 preferred |
| selenium | Alternative for login | ✗ | — | WebKit2 preferred |
| pytest | Testing | ✓ | 9.0.2 | — |

[VERIFIED: all tool checks run on this machine]

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** Selenium not available, but WebKit2 is the preferred approach anyway.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | none (discovered via test/ directory) |
| Quick run command | `python3 -m pytest tests/test_yt_cookies.py -x` |
| Full suite command | `python3 -m pytest tests/ -x` |

### Phase Requirements → Test Map
| ID | Behavior | Test Type | Automated Command | File Exists? |
|----|----------|-----------|-------------------|-------------|
| D-10/11 | yt_import uses --cookies flag when file exists | unit | `python3 -m pytest tests/test_yt_cookies.py::test_scan_uses_cookies_flag -x` | ❌ Wave 0 |
| D-10/11 | yt_import omits --cookies flag when file absent | unit | `python3 -m pytest tests/test_yt_cookies.py::test_scan_no_cookies_when_absent -x` | ❌ Wave 0 |
| D-13 | yt_import always passes --no-cookies-from-browser | unit | `python3 -m pytest tests/test_yt_cookies.py::test_scan_no_browser_extraction -x` | ❌ Wave 0 |
| D-10/12 | player uses --cookies-file flag when file exists | unit | `python3 -m pytest tests/test_yt_cookies.py::test_player_uses_cookies_flag -x` | ❌ Wave 0 |
| D-09 | Clear deletes cookies.txt | unit | `python3 -m pytest tests/test_yt_cookies.py::test_clear_removes_file -x` | ❌ Wave 0 |
| D-04 | COOKIES_PATH uses DATA_DIR | unit | `python3 -m pytest tests/test_yt_cookies.py::test_cookies_path_constant -x` | ❌ Wave 0 |
| D-03 | Paste validation rejects non-cookie text | unit | `python3 -m pytest tests/test_yt_cookies.py::test_paste_validation -x` | ❌ Wave 0 |
| D-03 | Google login flow — WebKit2 dialog | manual-only | n/a — requires display + Google account | — |

### Sampling Rate
- **Per task commit:** `python3 -m pytest tests/test_yt_cookies.py -x`
- **Per wave merge:** `python3 -m pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_yt_cookies.py` — covers all D-10/11/12/13 subprocess command tests, D-09 clear, D-04 constant, D-03 paste validation

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | n/a (no app auth) |
| V3 Session Management | no | n/a |
| V4 Access Control | no | n/a |
| V5 Input Validation | yes | `_is_valid_cookies_txt()` heuristic; file filtered to *.txt |
| V6 Cryptography | no | Cookies stored in plaintext — same as any browser cookies.txt |

**Cookie file security note:** `~/.local/share/musicstreamer/cookies.txt` is user-owned and not world-readable by default on Linux (umask 022 = 0644). No extra permissions hardening needed for v1.5 scope. [ASSUMED: default umask; implementation should use `os.chmod(path, 0o600)` after writing for defense-in-depth.]

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed paste causing file write | Tampering | Validate 7-field tab-separated format before writing |
| Cookie file readable by other processes | Information disclosure | `os.chmod(COOKIES_PATH, 0o600)` after write |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `get_all_cookies_finish` is the async finish method on CookieManager | Pattern 3, Code Examples | Google login cookies not extracted; would need alternative API call |
| A2 | WebKit2 Cookie objects have `get_domain/get_path/get_secure/get_expires/get_name/get_value` methods | Code Examples | Netscape writer would fail; need to inspect actual cookie object attrs |
| A3 | `--ytdl-raw-options=no-cookies-from-browser=` suppresses browser extraction in mpv's yt-dlp call | Pitfall 1 | mpv may still trigger GNOME keyring; add `--cookies-file` as belt-and-suspenders |
| A4 | `Gio.SimpleAction` with `app.` prefix is correct action scope for main window hamburger menu | Pattern 1 | Menu item insensitive; would need `win.` prefix instead |

---

## Open Questions (RESOLVED)

1. **WebKit2 Cookie object attrs at runtime** — RESOLVED
   - What we know: `CookieManager` has `get_all_cookies`; `WebKit2.Cookie` type not importable headlessly (segfault)
   - What was unclear: exact method names on the cookie object returned by `get_all_cookies_finish`
   - Resolution: Plan 03 Task 1 action includes runtime introspection (`dir(cookies[0])`) as the first step of the Google login implementation. The Netscape cookie writer will be adapted to whatever attrs are discovered. Assumptions A1/A2 in the Assumptions Log cover the risk; fallback is trivial method name adjustment.

2. **mpv ytdl-raw-options for suppressing browser cookies** — RESOLVED
   - What we know: `--no-cookies-from-browser` is a yt-dlp flag; mpv's `--ytdl-raw-options` passes key=value pairs
   - What was unclear: boolean yt-dlp flags (no value) syntax in mpv's kv list
   - Resolution: Plan 01 Task 2 tests this at implementation time. The `--ytdl-raw-options=no-cookies-from-browser=` syntax will be verified with a live mpv call. If it fails, the fallback is already documented: `--cookies-file` being present takes precedence over browser extraction, and yt-dlp's own `--no-cookies-from-browser` flag handles the yt_import.py side.

---

## Sources

### Primary (HIGH confidence)
- `yt-dlp --help` on yt-dlp 2026.03.17 — `--cookies`, `--no-cookies-from-browser` flags confirmed
- `mpv --list-options` on mpv v0.40.0 — `--cookies-file`, `--ytdl-raw-options` confirmed
- `python3 -c "import gi; gi.require_version('WebKit2', '4.1')"` — WebKit2 4.1 confirmed importable and WebView instantiable
- `/home/kcreasey/OneDrive/Projects/MusicStreamer/musicstreamer/ui/edit_dialog.py:527` — `Gtk.FileDialog` pattern in codebase

### Secondary (MEDIUM confidence)
- WebKit2 CookieManager API — `get_all_cookies` confirmed as method on CookieManager instance; async finish method `get_all_cookies_finish` assumed from GIO naming convention

### Tertiary (LOW confidence)
- WebKit2 Cookie object method names — not verifiable headlessly; segfault prevented inspection

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all tools verified on machine
- Architecture: HIGH for file/paste flow; MEDIUM for Google login (WebKit2 async API partly assumed)
- Pitfalls: HIGH — derived from direct testing and code reading

**Research date:** 2026-04-06
**Valid until:** 2026-05-06 (stable stack)
