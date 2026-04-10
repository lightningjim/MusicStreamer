import threading
import subprocess
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib
from musicstreamer.repo import Repo, db_connect
from musicstreamer.yt_import import scan_playlist, import_stations, is_yt_playlist_url


class ImportDialog(Adw.Window):
    def __init__(self, app, repo: Repo, main_window):
        super().__init__(application=app, title="Import YouTube Playlist")
        self.repo = repo
        self.main_window = main_window
        self._checklist_items: list[tuple[Gtk.CheckButton, dict]] = []
        self._import_handler_id = None

        self.set_default_size(700, 560)
        self.set_transient_for(main_window)
        self.set_modal(True)

        # Root layout
        root = Adw.ToolbarView()
        header = Adw.HeaderBar()
        root.add_top_bar(header)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)

        # URL entry row
        url_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        self._url_entry = Gtk.Entry()
        self._url_entry.set_placeholder_text("Paste YouTube playlist URL\u2026")
        self._url_entry.set_hexpand(True)
        self._url_entry.connect("changed", self._on_url_changed)
        url_row.append(self._url_entry)

        self._scan_btn = Gtk.Button(label="Scan Playlist")
        self._scan_btn.set_sensitive(False)
        self._scan_btn.connect("clicked", self._on_scan_clicked)
        url_row.append(self._scan_btn)

        content.append(url_row)

        # Stack with 4 named pages
        self._stack = Gtk.Stack()
        self._stack.set_vexpand(True)

        # Page: prompt
        prompt_page = Adw.StatusPage(
            title="Paste a playlist URL",
            description="Enter a public YouTube playlist URL above and tap Scan Playlist.",
        )
        self._stack.add_named(prompt_page, "prompt")

        # Page: scanning
        scanning_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        scanning_box.set_halign(Gtk.Align.CENTER)
        scanning_box.set_valign(Gtk.Align.CENTER)
        spinner = Gtk.Spinner()
        spinner.set_size_request(32, 32)
        spinner.start()
        scanning_box.append(spinner)
        self._stack.add_named(scanning_box, "scanning")

        # Page: error
        self._error_page = Adw.StatusPage()
        self._stack.add_named(self._error_page, "error")

        # Page: checklist
        checklist_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        self._listbox = Gtk.ListBox()
        self._listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        scroll.set_child(self._listbox)
        checklist_box.append(scroll)

        self._progress_label = Gtk.Label(label="")
        self._progress_label.set_visible(False)
        checklist_box.append(self._progress_label)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._count_label = Gtk.Label()
        self._count_label.set_hexpand(True)
        self._count_label.set_xalign(0)
        footer.append(self._count_label)

        self._import_btn = Gtk.Button(label="Import Selected")
        self._import_btn.add_css_class("suggested-action")
        self._import_handler_id = self._import_btn.connect("clicked", self._on_import_clicked)
        footer.append(self._import_btn)

        checklist_box.append(footer)
        self._stack.add_named(checklist_box, "checklist")

        self._stack.set_visible_child_name("prompt")
        content.append(self._stack)

        root.set_content(content)
        self.set_content(root)

    # ------------------------------------------------------------------
    # URL entry
    # ------------------------------------------------------------------

    def _on_url_changed(self, entry):
        self._scan_btn.set_sensitive(bool(entry.get_text().strip()))

    # ------------------------------------------------------------------
    # Scan
    # ------------------------------------------------------------------

    def _on_scan_clicked(self, btn):
        url = self._url_entry.get_text().strip()
        if not is_yt_playlist_url(url):
            self._show_error(
                "Invalid URL",
                "That doesn't look like a YouTube playlist URL. Check the link and try again.",
            )
            return
        self._stack.set_visible_child_name("scanning")
        self._url_entry.set_sensitive(False)
        self._scan_btn.set_sensitive(False)
        threading.Thread(target=self._scan_worker, args=(url,), daemon=True).start()

    def _scan_worker(self, url: str):
        try:
            entries = scan_playlist(url)
            GLib.idle_add(self._on_scan_complete, entries)
        except ValueError:
            GLib.idle_add(
                self._on_scan_error,
                "Playlist Not Accessible",
                "This playlist may be private or unavailable. Try a public playlist URL.",
            )
        except (RuntimeError, subprocess.TimeoutExpired):
            GLib.idle_add(
                self._on_scan_error,
                "Could Not Reach YouTube",
                "Check your internet connection and try again.",
            )
        except Exception as e:
            GLib.idle_add(self._on_scan_error, "Scan Failed", str(e))

    def _on_scan_complete(self, entries: list[dict]):
        self._url_entry.set_sensitive(True)
        self._scan_btn.set_sensitive(True)

        if not entries:
            self._show_error(
                "No Live Streams Found",
                "This playlist has no live streams. Only live broadcasts can be imported as stations.",
            )
            return

        # Clear existing checklist
        while (child := self._listbox.get_first_child()):
            self._listbox.remove(child)
        self._checklist_items = []

        for entry in entries:
            row = Adw.ActionRow()
            row.set_title(GLib.markup_escape_text(entry["title"]))
            row.set_subtitle(GLib.markup_escape_text(entry["provider"]))

            check = Gtk.CheckButton()
            check.set_active(True)
            row.add_prefix(check)

            self._checklist_items.append((check, entry))
            self._listbox.append(row)

        n = len(entries)
        self._count_label.set_text(f"{n} live stream{'s' if n != 1 else ''} found")
        self._stack.set_visible_child_name("checklist")

    def _on_scan_error(self, title: str, description: str):
        self._show_error(title, description)
        self._url_entry.set_sensitive(True)
        self._scan_btn.set_sensitive(bool(self._url_entry.get_text().strip()))

    def _show_error(self, title: str, description: str):
        self._error_page.set_title(title)
        self._error_page.set_description(description)
        self._stack.set_visible_child_name("error")

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------

    def _on_import_clicked(self, btn):
        selected = [entry for (check, entry) in self._checklist_items if check.get_active()]
        if not selected:
            return
        self._import_btn.set_sensitive(False)
        self._scan_btn.set_sensitive(False)
        self._url_entry.set_sensitive(False)
        self._progress_label.set_text("0 imported, 0 skipped")
        self._progress_label.set_visible(True)
        threading.Thread(target=self._import_worker, args=(selected,), daemon=True).start()

    def _import_worker(self, selected: list[dict]):
        def on_progress(imp: int, skip: int):
            GLib.idle_add(self._update_progress, imp, skip)
        con = db_connect()
        try:
            thread_repo = Repo(con)
            imported, skipped = import_stations(selected, thread_repo, on_progress=on_progress)
        finally:
            con.close()
        GLib.idle_add(self._on_import_done, imported, skipped)

    def _update_progress(self, imported: int, skipped: int):
        self._progress_label.set_text(f"{imported} imported, {skipped} skipped")

    def _on_import_done(self, imported: int, skipped: int):
        self._update_progress(imported, skipped)
        # Disconnect old handler and wire "Done"
        if self._import_handler_id is not None:
            self._import_btn.disconnect(self._import_handler_id)
            self._import_handler_id = None
        self._import_btn.set_label("Done")
        self._import_btn.set_sensitive(True)
        self._import_handler_id = self._import_btn.connect("clicked", self._on_done_clicked)

    def _on_done_clicked(self, btn):
        self.main_window.reload_list()
        self.close()
