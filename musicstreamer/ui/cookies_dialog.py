import os
import shutil
from datetime import datetime
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib
from musicstreamer.constants import COOKIES_PATH, clear_cookies


def _is_valid_cookies_txt(text: str) -> bool:
    lines = [l for l in text.splitlines() if l.strip() and not l.startswith("#")]
    if not lines:
        return False
    return len(lines[0].split("\t")) == 7


class CookiesDialog(Adw.Window):
    def __init__(self, app, main_window):
        super().__init__(application=app, title="YouTube Cookies")
        self.set_default_size(480, 400)
        self.set_transient_for(main_window)
        self.set_modal(True)

        self._selected_file_path = None

        root = Adw.ToolbarView()
        header = Adw.HeaderBar()
        root.add_top_bar(header)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(16)
        content.set_margin_end(16)

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
        content.append(self._status_label)

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
        content.append(file_row)

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
        content.append(expander)

        # 4. Error label
        self._error_label = Gtk.Label()
        self._error_label.add_css_class("error")
        self._error_label.set_xalign(0)
        self._error_label.set_visible(False)
        self._error_label.set_wrap(True)
        content.append(self._error_label)

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

        content.append(footer)

        root.set_content(content)
        self.set_content(root)

        # Connect paste buffer changes to update import sensitivity
        self._paste_view.get_buffer().connect("changed", lambda buf: self._update_import_sensitive())

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
    # Google login (placeholder for Plan 03)
    # ------------------------------------------------------------------

    def _on_google_login(self, btn):
        self._google_status.set_text("Google login coming soon")
        self._google_status.set_visible(True)

    # ------------------------------------------------------------------
    # Error display
    # ------------------------------------------------------------------

    def _show_error(self, msg):
        self._error_label.set_text(msg)
        self._error_label.set_visible(True)
