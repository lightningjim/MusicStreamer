import os
import shutil
import subprocess
import tempfile
import threading
from datetime import datetime
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib
from musicstreamer.constants import COOKIES_PATH, clear_cookies, TWITCH_TOKEN_PATH, clear_twitch_token


def _is_valid_cookies_txt(text: str) -> bool:
    lines = [l for l in text.splitlines() if l.strip() and not l.startswith("#")]
    if not lines:
        return False
    return len(lines[0].split("\t")) == 7


class AccountsDialog(Adw.Window):
    def __init__(self, app, main_window):
        super().__init__(application=app, title="Accounts")
        self.set_default_size(480, 460)
        self.set_transient_for(main_window)
        self.set_modal(True)

        self._selected_file_path = None

        root = Adw.ToolbarView()
        header = Adw.HeaderBar()
        root.add_top_bar(header)

        # Gtk.Notebook with YouTube and Twitch tabs
        notebook = Gtk.Notebook()

        # ------------------------------------------------------------------
        # YouTube tab (existing CookiesDialog content)
        # ------------------------------------------------------------------

        yt_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        yt_page.set_margin_top(16)
        yt_page.set_margin_bottom(16)
        yt_page.set_margin_start(16)
        yt_page.set_margin_end(16)

        # 1. Status label
        self._status_label = Gtk.Label()
        self._status_label.add_css_class("dim-label")
        self._status_label.set_xalign(0)
        if os.path.exists(COOKIES_PATH):
            mtime = os.path.getmtime(COOKIES_PATH)
            dt_str = datetime.fromtimestamp(mtime).strftime("%-d %b %Y")
            self._status_label.set_text(f"Last imported: {dt_str}")
        else:
            self._status_label.set_text("No cookies imported")
        yt_page.append(self._status_label)

        # 2. File picker row
        file_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        file_label = Gtk.Label(label="Cookie file")
        file_label.set_hexpand(False)
        file_row.append(file_label)

        self._file_entry = Gtk.Entry()
        self._file_entry.set_editable(False)
        self._file_entry.set_placeholder_text("No file selected")
        self._file_entry.set_hexpand(True)
        file_row.append(self._file_entry)

        browse_btn = Gtk.Button(label="Browse\u2026")
        browse_btn.connect("clicked", self._on_browse)
        file_row.append(browse_btn)
        yt_page.append(file_row)

        # 3. "Other methods" expander
        expander = Gtk.Expander(label="Other methods")
        expander_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        expander_inner.set_margin_top(8)

        # Paste section
        paste_frame = Gtk.Frame()
        paste_scroll = Gtk.ScrolledWindow()
        paste_scroll.set_min_content_height(80)
        self._paste_view = Gtk.TextView()
        self._paste_view.add_css_class("monospace")
        self._paste_view.set_wrap_mode(Gtk.WrapMode.NONE)
        paste_scroll.set_child(self._paste_view)
        paste_frame.set_child(paste_scroll)
        expander_inner.append(paste_frame)

        # Google login section
        self._google_btn = Gtk.Button(label="Sign in with Google")
        self._google_btn.connect("clicked", self._on_google_login)
        expander_inner.append(self._google_btn)

        self._google_status = Gtk.Label()
        self._google_status.set_visible(False)
        expander_inner.append(self._google_status)

        expander.set_child(expander_inner)
        yt_page.append(expander)

        # 4. Error label
        self._error_label = Gtk.Label()
        self._error_label.add_css_class("error")
        self._error_label.set_xalign(0)
        self._error_label.set_visible(False)
        self._error_label.set_wrap(True)
        yt_page.append(self._error_label)

        # 5. Footer row
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        self._clear_btn = Gtk.Button(label="Clear Cookies")
        self._clear_btn.add_css_class("destructive-action")
        self._clear_btn.set_sensitive(os.path.exists(COOKIES_PATH))
        self._clear_btn.connect("clicked", self._on_clear)
        footer.append(self._clear_btn)

        spacer = Gtk.Box(hexpand=True)
        footer.append(spacer)

        self._import_btn = Gtk.Button(label="Import Cookies")
        self._import_btn.add_css_class("suggested-action")
        self._import_btn.set_sensitive(False)
        self._import_btn.connect("clicked", self._on_import)
        footer.append(self._import_btn)

        yt_page.append(footer)

        notebook.append_page(yt_page, Gtk.Label(label="YouTube"))

        # Connect paste buffer changes to update import sensitivity
        self._paste_view.get_buffer().connect("changed", lambda buf: self._update_import_sensitive())

        # ------------------------------------------------------------------
        # Twitch tab
        # ------------------------------------------------------------------

        twitch_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        twitch_page.set_margin_top(16)
        twitch_page.set_margin_bottom(16)
        twitch_page.set_margin_start(16)
        twitch_page.set_margin_end(16)

        self._twitch_status = Gtk.Label()
        self._twitch_status.add_css_class("dim-label")
        self._twitch_status.set_xalign(0)
        if os.path.exists(TWITCH_TOKEN_PATH):
            self._twitch_status.set_text("Logged in")
        else:
            self._twitch_status.set_text("Not logged in")
        twitch_page.append(self._twitch_status)

        self._twitch_login_btn = Gtk.Button(label="Log in to Twitch")
        self._twitch_login_btn.connect("clicked", self._on_twitch_login)
        twitch_page.append(self._twitch_login_btn)

        self._twitch_logout_btn = Gtk.Button(label="Log out")
        self._twitch_logout_btn.add_css_class("destructive-action")
        self._twitch_logout_btn.set_sensitive(os.path.exists(TWITCH_TOKEN_PATH))
        self._twitch_logout_btn.connect("clicked", self._on_twitch_logout)
        twitch_page.append(self._twitch_logout_btn)

        self._twitch_error_label = Gtk.Label()
        self._twitch_error_label.add_css_class("error")
        self._twitch_error_label.set_xalign(0)
        self._twitch_error_label.set_visible(False)
        self._twitch_error_label.set_wrap(True)
        twitch_page.append(self._twitch_error_label)

        notebook.append_page(twitch_page, Gtk.Label(label="Twitch"))
        self._twitch_page = twitch_page

        root.set_content(notebook)
        self.set_content(root)

    # ------------------------------------------------------------------
    # File picker
    # ------------------------------------------------------------------

    def _on_browse(self, btn):
        dlg = Gtk.FileDialog(title="Choose cookies.txt")
        flt = Gtk.FileFilter()
        flt.set_name("Cookie files")
        flt.add_pattern("*.txt")
        dlg.set_default_filter(flt)
        dlg.open(self, None, self._on_file_chosen)

    def _on_file_chosen(self, dlg, res):
        try:
            f = dlg.open_finish(res)
        except GLib.Error:
            return
        if not f:
            return
        self._selected_file_path = f.get_path()
        self._file_entry.set_text(os.path.basename(self._selected_file_path))
        self._update_import_sensitive()

    # ------------------------------------------------------------------
    # Sensitivity helpers
    # ------------------------------------------------------------------

    def _update_import_sensitive(self):
        buf = self._paste_view.get_buffer()
        text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
        has_content = bool(self._selected_file_path) or bool(text.strip())
        self._import_btn.set_sensitive(has_content)

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------

    def _on_import(self, btn):
        self._error_label.set_visible(False)
        if self._selected_file_path:
            self._import_from_file(self._selected_file_path)
        else:
            buf = self._paste_view.get_buffer()
            text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
            if text.strip():
                self._import_from_paste(text)

    def _import_from_file(self, path):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError as e:
            self._show_error(f"Could not read file: {e}")
            return
        if not _is_valid_cookies_txt(text):
            self._show_error(
                "File does not appear to be a valid cookies.txt. "
                "Try exporting again with the Get cookies.txt LOCALLY extension."
            )
            return
        os.makedirs(os.path.dirname(COOKIES_PATH), exist_ok=True)
        shutil.copy2(path, COOKIES_PATH)
        os.chmod(COOKIES_PATH, 0o600)
        self._update_status()
        self._selected_file_path = None
        self._file_entry.set_text("")
        self._update_import_sensitive()

    def _import_from_paste(self, text):
        if not _is_valid_cookies_txt(text):
            self._show_error(
                "Pasted content does not appear to be valid cookies. "
                "Check the format and try again."
            )
            return
        os.makedirs(os.path.dirname(COOKIES_PATH), exist_ok=True)
        with open(COOKIES_PATH, "w", encoding="utf-8") as f:
            f.write(text)
        os.chmod(COOKIES_PATH, 0o600)
        self._update_status()
        self._paste_view.get_buffer().set_text("")
        self._update_import_sensitive()

    # ------------------------------------------------------------------
    # Clear
    # ------------------------------------------------------------------

    def _on_clear(self, btn):
        clear_cookies()
        self._status_label.set_text("No cookies imported")
        self._clear_btn.set_sensitive(False)
        self._update_import_sensitive()

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def _update_status(self):
        if os.path.exists(COOKIES_PATH):
            mtime = os.path.getmtime(COOKIES_PATH)
            dt_str = datetime.fromtimestamp(mtime).strftime("%-d %b %Y")
            self._status_label.set_text(f"Last imported: {dt_str}")
        else:
            self._status_label.set_text("No cookies imported")
        self._clear_btn.set_sensitive(os.path.exists(COOKIES_PATH))

    # ------------------------------------------------------------------
    # Google login — launches WebKit2 subprocess (GTK3-based, separate process)
    # ------------------------------------------------------------------

    def _on_google_login(self, btn):
        self._google_btn.set_sensitive(False)
        self._google_status.set_text("Signing in\u2026")
        self._google_status.set_visible(True)
        self._error_label.set_visible(False)

        # Run WebKit2 login in a background thread — subprocess writes cookies to a
        # temp file and exits, then we pick them up on the GTK main thread.
        with tempfile.NamedTemporaryFile(suffix="-ms-yt-cookies.txt", delete=False) as tf:
            tmp = tf.name
        t = threading.Thread(
            target=self._run_webkit_subprocess,
            args=(tmp,),
            daemon=True,
        )
        t.start()

    def _run_webkit_subprocess(self, tmp_path: str):
        """Run the WebKit2 GTK3 login subprocess and deliver result on main thread."""
        script = _WEBKIT2_SUBPROCESS_SCRIPT.format(output_path=tmp_path)
        try:
            proc = subprocess.run(
                ["python3", "-c", script],
                timeout=300,  # 5-minute timeout for the sign-in flow
            )
            if proc.returncode == 0 and os.path.exists(tmp_path):
                with open(tmp_path, "r", encoding="utf-8") as f:
                    netscape_text = f.read()
                GLib.idle_add(self._on_google_cookies_ready, netscape_text)
            else:
                GLib.idle_add(self._on_google_cookies_ready, None)
        except subprocess.TimeoutExpired:
            GLib.idle_add(self._on_google_cookies_ready, None)
        except Exception:
            GLib.idle_add(self._on_google_cookies_ready, None)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def _on_google_cookies_ready(self, netscape_text):
        self._google_btn.set_sensitive(True)
        self._google_status.set_visible(False)
        if not netscape_text:
            self._show_error("Sign-in failed or was cancelled. Try again or use the file method.")
            return
        try:
            os.makedirs(os.path.dirname(COOKIES_PATH), exist_ok=True)
            with open(COOKIES_PATH, "w", encoding="utf-8") as f:
                f.write(netscape_text)
            os.chmod(COOKIES_PATH, 0o600)
            self._update_status()
            self._error_label.set_visible(False)
        except Exception:
            self._show_error("Could not save cookies. Check disk space and try again.")

    # ------------------------------------------------------------------
    # Error display
    # ------------------------------------------------------------------

    def _show_error(self, msg):
        self._error_label.set_text(msg)
        self._error_label.set_visible(True)

    # ------------------------------------------------------------------
    # Twitch login/logout
    # ------------------------------------------------------------------

    def _on_twitch_login(self, btn):
        self._twitch_login_btn.set_sensitive(False)
        self._twitch_error_label.set_visible(False)
        with tempfile.NamedTemporaryFile(suffix="-ms-twitch-token.txt", delete=False) as tf:
            tmp = tf.name
        t = threading.Thread(
            target=self._run_twitch_webkit_subprocess,
            args=(tmp,),
            daemon=True,
        )
        t.start()

    def _run_twitch_webkit_subprocess(self, tmp_path: str):
        """Run the WebKit2 GTK3 Twitch login subprocess and deliver result on main thread."""
        script = _TWITCH_WEBKIT2_SUBPROCESS_SCRIPT.format(output_path=tmp_path)
        try:
            proc = subprocess.run(
                ["python3", "-c", script],
                timeout=300,
            )
            if proc.returncode == 0 and os.path.exists(tmp_path):
                with open(tmp_path, "r") as f:
                    token = f.read().strip()
                GLib.idle_add(self._on_twitch_token_ready, token)
            else:
                GLib.idle_add(self._on_twitch_token_ready, None)
        except subprocess.TimeoutExpired:
            GLib.idle_add(self._on_twitch_token_ready, None)
        except Exception:
            GLib.idle_add(self._on_twitch_token_ready, None)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def _on_twitch_token_ready(self, token):
        self._twitch_login_btn.set_sensitive(True)
        if not token:
            self._twitch_error_label.set_text("Sign-in failed or was cancelled. Try again.")
            self._twitch_error_label.set_visible(True)
            return False
        try:
            os.makedirs(os.path.dirname(TWITCH_TOKEN_PATH), exist_ok=True)
            fd = os.open(TWITCH_TOKEN_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(token)
            self._update_twitch_status()
            self._twitch_error_label.set_visible(False)
        except Exception:
            self._twitch_error_label.set_text("Could not save token. Check disk space and try again.")
            self._twitch_error_label.set_visible(True)
        return False

    def _on_twitch_logout(self, btn):
        clear_twitch_token()
        self._twitch_status.set_text("Not logged in")
        self._twitch_logout_btn.set_sensitive(False)

    def _update_twitch_status(self):
        if os.path.exists(TWITCH_TOKEN_PATH):
            self._twitch_status.set_text("Logged in")
        else:
            self._twitch_status.set_text("Not logged in")
        self._twitch_logout_btn.set_sensitive(os.path.exists(TWITCH_TOKEN_PATH))


# ---------------------------------------------------------------------------
# Netscape cookie writer (used by subprocess script and importable for tests)
# ---------------------------------------------------------------------------

def _write_netscape_cookies(cookies, path: str):
    """Write WebKit2 cookie objects to Netscape format file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = ["# Netscape HTTP Cookie File", ""]
    for c in cookies:
        domain = c.get_domain() or ""
        domain_dot = "TRUE" if domain.startswith(".") else "FALSE"
        path_val = c.get_path() or "/"
        secure = "TRUE" if c.get_secure() else "FALSE"
        expires = c.get_expires()
        if expires is not None:
            # get_expires() may return GLib.DateTime (to_unix) or Soup.Date (to_time_t)
            if hasattr(expires, "to_unix"):
                expiry = int(expires.to_unix())
            elif hasattr(expires, "to_time_t"):
                expiry = int(expires.to_time_t())
            else:
                expiry = 0
        else:
            expiry = 0
        name = c.get_name() or ""
        value = c.get_value() or ""
        lines.append(f"{domain}\t{domain_dot}\t{path_val}\t{secure}\t{expiry}\t{name}\t{value}")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# _GoogleLoginWindow: stub class for import compatibility.
# The actual browser window runs inside _WEBKIT2_SUBPROCESS_SCRIPT (below)
# in a separate process to avoid GTK3/GTK4 namespace conflicts.
# ---------------------------------------------------------------------------

class _GoogleLoginWindow:
    """Stub — real implementation lives in _WEBKIT2_SUBPROCESS_SCRIPT subprocess."""
    def __init__(self, on_cookies_ready):
        pass  # Not instantiated directly; see AccountsDialog._run_webkit_subprocess


# ---------------------------------------------------------------------------
# WebKit2 subprocess script (runs in its own Python/GTK3 process)
# ---------------------------------------------------------------------------

# This script is executed as a subprocess so that WebKit2 (which requires GTK3)
# does not conflict with the parent app's GTK4 namespace. The script opens an
# embedded browser window, waits for the user to sign in to Google, extracts
# YouTube/Google cookies, writes them to {output_path} in Netscape format, then
# exits with code 0. On cancellation or error it exits with code 1.

_WEBKIT2_SUBPROCESS_SCRIPT = r"""
import sys
import os

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import Gtk, GLib, WebKit2

OUTPUT_PATH = {output_path!r}
_cookies_extracted = False


def write_netscape_cookies(cookies, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = ["# Netscape HTTP Cookie File", ""]
    for c in cookies:
        domain = c.get_domain() or ""
        domain_dot = "TRUE" if domain.startswith(".") else "FALSE"
        path_val = c.get_path() or "/"
        secure = "TRUE" if c.get_secure() else "FALSE"
        expires = c.get_expires()
        if expires is not None:
            if hasattr(expires, "to_unix"):
                expiry = int(expires.to_unix())
            elif hasattr(expires, "to_time_t"):
                expiry = int(expires.to_time_t())
            else:
                expiry = 0
        else:
            expiry = 0
        name = c.get_name() or ""
        value = c.get_value() or ""
        lines.append(f"{{domain}}\t{{domain_dot}}\t{{path_val}}\t{{secure}}\t{{expiry}}\t{{name}}\t{{value}}")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def on_got_cookies(mgr, res, user_data):
    try:
        cookies = mgr.get_all_cookies_finish(res)
    except Exception as e:
        print(f"get_all_cookies_finish failed: {{e}}", file=sys.stderr)
        Gtk.main_quit()
        sys.exit(1)
    yt_cookies = [
        c for c in (cookies or [])
        if any(
            d in (c.get_domain() or "")
            for d in [".youtube.com", ".google.com", "youtube.com", "google.com"]
        )
    ]
    if yt_cookies:
        write_netscape_cookies(yt_cookies, OUTPUT_PATH)
        Gtk.main_quit()
        sys.exit(0)
    else:
        print("No YouTube/Google cookies found after login", file=sys.stderr)
        Gtk.main_quit()
        sys.exit(1)


def on_load_changed(webview, event):
    global _cookies_extracted
    if event != WebKit2.LoadEvent.FINISHED:
        return
    uri = webview.get_uri() or ""
    if ("youtube.com" in uri and "accounts.google" not in uri) or "myaccount.google.com" in uri:
        if not _cookies_extracted:
            _cookies_extracted = True
            mgr = webview.get_website_data_manager().get_cookie_manager()
            mgr.get_all_cookies(None, on_got_cookies, None)


def on_delete_event(win, event):
    if not _cookies_extracted:
        Gtk.main_quit()
        sys.exit(1)
    return False


win = Gtk.Window(title="Sign in with Google")
win.set_default_size(800, 600)

ctx = WebKit2.WebContext.get_default()
webview = WebKit2.WebView.new_with_context(ctx)
settings = webview.get_settings()
settings.set_enable_javascript(True)
webview.connect("load-changed", on_load_changed)
win.add(webview)

webview.load_uri(
    "https://accounts.google.com/signin/v2/identifier"
    "?service=youtube&continue=https%3A%2F%2Fwww.youtube.com%2F"
)

win.connect("delete-event", on_delete_event)
win.show_all()
Gtk.main()
sys.exit(1)
"""


# ---------------------------------------------------------------------------
# Twitch WebKit2 subprocess script (runs in its own Python/GTK3 process)
# ---------------------------------------------------------------------------

# This script navigates to twitch.tv/login, detects when the user has logged in
# (URL no longer contains "login" or "passport"), extracts the auth-token cookie
# from .twitch.tv domain, writes the raw token string to {output_path}, and exits
# with code 0. On cancellation or error it exits with code 1.

_TWITCH_WEBKIT2_SUBPROCESS_SCRIPT = r"""
import sys
import os

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import Gtk, GLib, WebKit2

OUTPUT_PATH = {output_path!r}
_token_extracted = False


def on_got_cookies(mgr, res, user_data):
    try:
        cookies = mgr.get_all_cookies_finish(res)
    except Exception as e:
        print(f"get_all_cookies_finish failed: {{e}}", file=sys.stderr)
        Gtk.main_quit()
        sys.exit(1)
    twitch_cookies = [
        c for c in (cookies or [])
        if ".twitch.tv" in (c.get_domain() or "")
    ]
    token = None
    for c in twitch_cookies:
        if c.get_name() == "auth-token":
            token = c.get_value()
            break
    if token:
        with open(OUTPUT_PATH, "w") as f:
            f.write(token)
        Gtk.main_quit()
        sys.exit(0)
    else:
        print("No auth-token cookie found after login", file=sys.stderr)
        Gtk.main_quit()
        sys.exit(1)


def on_load_changed(webview, event):
    global _token_extracted
    if event != WebKit2.LoadEvent.FINISHED:
        return
    uri = webview.get_uri() or ""
    if "twitch.tv" in uri and "login" not in uri and "passport" not in uri:
        if not _token_extracted:
            _token_extracted = True
            mgr = webview.get_website_data_manager().get_cookie_manager()
            mgr.get_all_cookies(None, on_got_cookies, None)


def on_delete_event(win, event):
    if not _token_extracted:
        Gtk.main_quit()
        sys.exit(1)
    return False


win = Gtk.Window(title="Sign in to Twitch")
win.set_default_size(800, 600)

ctx = WebKit2.WebContext.get_default()
webview = WebKit2.WebView.new_with_context(ctx)
settings = webview.get_settings()
settings.set_enable_javascript(True)
webview.connect("load-changed", on_load_changed)
win.add(webview)

webview.load_uri("https://www.twitch.tv/login")

win.connect("delete-event", on_delete_event)
win.show_all()
Gtk.main()
sys.exit(1)
"""
