import re
import subprocess
import tempfile
import threading
import urllib.request
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib
from musicstreamer.repo import Repo
from musicstreamer.assets import copy_asset_for_station
from musicstreamer.constants import DATA_DIR


def _is_youtube_url(url: str) -> bool:
    """Return True if url is a YouTube URL."""
    return "youtube.com" in url or "youtu.be" in url


def fetch_yt_thumbnail(url: str, callback: callable) -> None:
    """Fetch YouTube thumbnail via yt-dlp in a daemon thread.

    callback receives temp_path (str) on success, None on failure.
    The callback is invoked via GLib.idle_add so widget updates inside it are safe.
    """
    def _worker():
        try:
            result = subprocess.run(
                ["yt-dlp", "--print", "thumbnail", "--no-playlist", url],
                capture_output=True, text=True, timeout=15,
            )
            thumb_url = result.stdout.strip()
            if not thumb_url:
                GLib.idle_add(callback, None)
                return
            with urllib.request.urlopen(thumb_url, timeout=10) as resp:
                data = resp.read()
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                tmp.write(data)
                GLib.idle_add(callback, tmp.name)
        except Exception:
            GLib.idle_add(callback, None)

    threading.Thread(target=_worker, daemon=True).start()


def fetch_yt_title(url: str, callback: callable) -> None:
    """Fetch YouTube stream title via yt-dlp in a daemon thread.

    callback receives title (str) on success, None on failure.
    The callback is invoked via GLib.idle_add so widget updates inside it are safe.
    """
    def _worker():
        try:
            result = subprocess.run(
                ["yt-dlp", "--print", "title", "--no-playlist", url],
                capture_output=True, text=True, timeout=15,
            )
            title = result.stdout.strip()
            GLib.idle_add(callback, title or None)
        except Exception:
            GLib.idle_add(callback, None)

    threading.Thread(target=_worker, daemon=True).start()


class EditStationDialog(Adw.Window):
    def __init__(self, app, repo: Repo, station_id: int, on_saved, is_playing=None):
        super().__init__(application=app, title="Edit Station")
        self.repo = repo
        self.station_id = station_id
        self.on_saved = on_saved
        self.is_playing = is_playing

        # Fetch state
        self._thumb_fetch_in_progress = False
        self._title_fetch_in_progress = False
        self._fetch_cancelled = False

        self.set_default_size(560, 480)

        self.station = repo.get_station(station_id)

        # Keep current paths
        self.station_art_rel = self.station.station_art_path
        self.album_art_rel = self.station.album_fallback_path

        root = Adw.ToolbarView()
        header = Adw.HeaderBar()

        # Delete Station button (destructive, packed start)
        delete_btn = Gtk.Button(label="Delete Station")
        delete_btn.add_css_class("destructive-action")
        delete_btn.connect("clicked", self._on_delete_clicked)
        header.pack_start(delete_btn)

        save_btn = Gtk.Button(label="Save")
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", self._save)

        header.pack_end(save_btn)
        root.add_top_bar(header)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)

        # Fields
        self.name_entry = Gtk.Entry(text=self.station.name)
        self.url_entry = Gtk.Entry(text=self.station.url)

        # Provider picker: ComboRow of existing providers + entry for new ones
        providers = repo.list_providers()
        provider_model = Gtk.StringList()
        provider_model.append("")  # blank = no provider (index 0)
        for p in providers:
            provider_model.append(p.name)

        self.provider_combo = Gtk.DropDown(model=provider_model)
        self.provider_combo.set_enable_search(True)

        current_prov = self.station.provider_name or ""
        for i, pname in enumerate([""] + [p.name for p in providers]):
            if pname == current_prov:
                self.provider_combo.set_selected(i)
                break

        self.new_provider_entry = Gtk.Entry()
        self.new_provider_entry.set_placeholder_text("Or type new provider name\u2026")

        provider_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        provider_box.append(self.provider_combo)
        provider_box.append(self.new_provider_entry)

        # Tag chip panel: toggleable chips for existing tags + entry for new ones
        all_tags = sorted({t.strip() for s in repo.list_stations()
                           for t in s.tags.split(",") if t.strip()})
        current_tags = {t.strip() for t in self.station.tags.split(",") if t.strip()}
        self._selected_tags = set(current_tags)
        self._tag_chip_btns = []
        self._rebuilding = False

        self._chip_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        chip_scroll = Gtk.ScrolledWindow()
        chip_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        chip_scroll.set_min_content_height(36)
        chip_scroll.set_margin_top(4)
        chip_scroll.set_margin_bottom(4)
        chip_scroll.set_margin_start(8)
        chip_scroll.set_margin_end(8)
        chip_scroll.set_child(self._chip_box)

        self._rebuilding = True
        for tag in all_tags:
            btn = Gtk.ToggleButton(label=tag)
            btn.set_active(tag in self._selected_tags)
            btn.connect("toggled", self._on_tag_chip_toggled, tag)
            self._chip_box.append(btn)
            self._tag_chip_btns.append(btn)
        self._rebuilding = False

        self.new_tag_entry = Gtk.Entry()
        self.new_tag_entry.set_placeholder_text("New tag\u2026")

        tags_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        tags_box.append(chip_scroll)
        tags_box.append(self.new_tag_entry)

        # URL focus-out controller for auto-fetch
        focus_controller = Gtk.EventControllerFocus()
        focus_controller.connect("leave", self._on_url_focus_out)
        self.url_entry.add_controller(focus_controller)

        # Art previews
        self.station_pic = Gtk.Picture()
        self.station_pic.set_size_request(128, 128)
        self.station_pic.set_content_fit(Gtk.ContentFit.COVER)

        self.album_pic = Gtk.Picture()
        self.album_pic.set_size_request(128, 128)
        self.album_pic.set_content_fit(Gtk.ContentFit.COVER)

        self._refresh_pictures()

        station_art_btn = Gtk.Button(label="Choose Station Art…")
        station_art_btn.connect("clicked", self._choose_station_art)

        fetch_btn = Gtk.Button(label="Fetch from URL")
        fetch_btn.connect("clicked", self._on_fetch_clicked)

        album_art_btn = Gtk.Button(label="Choose Default Album Art…")
        album_art_btn.connect("clicked", self._choose_album_art)

        # Spinner for thumbnail fetch (shown in place of station_pic)
        self._art_spinner = Gtk.Spinner()
        self._art_spinner.set_size_request(128, 128)

        self._art_stack = Gtk.Stack()
        self._art_stack.add_named(self.station_pic, "pic")
        self._art_stack.add_named(self._art_spinner, "spinner")
        self._art_stack.set_visible_child_name("pic")

        form = Gtk.Grid(column_spacing=12, row_spacing=12)
        form.attach(Gtk.Label(label="Name", xalign=0), 0, 0, 1, 1)
        form.attach(self.name_entry, 1, 0, 1, 1)

        form.attach(Gtk.Label(label="URL", xalign=0), 0, 1, 1, 1)
        form.attach(self.url_entry, 1, 1, 1, 1)

        form.attach(Gtk.Label(label="Provider", xalign=0), 0, 2, 1, 1)
        form.attach(provider_box, 1, 2, 1, 1)

        form.attach(Gtk.Label(label="Tags", xalign=0), 0, 3, 1, 1)
        form.attach(tags_box, 1, 3, 1, 1)

        # ICY metadata toggle (SwitchRow, between form and arts section)
        self.icy_switch = Adw.SwitchRow(title="Disable ICY metadata")
        self.icy_switch.set_active(self.station.icy_disabled)

        arts = Gtk.Grid(column_spacing=12, row_spacing=12)
        arts.attach(Gtk.Label(label="Station Art", xalign=0), 0, 0, 1, 1)
        arts.attach(self._art_stack, 0, 1, 1, 1)
        arts.attach(station_art_btn, 0, 2, 1, 1)
        arts.attach(fetch_btn, 0, 3, 1, 1)

        arts.attach(Gtk.Label(label="Default Album Art", xalign=0), 1, 0, 1, 1)
        arts.attach(self.album_pic, 1, 1, 1, 1)
        arts.attach(album_art_btn, 1, 2, 1, 1)

        content.append(form)
        content.append(self.icy_switch)
        content.append(Gtk.Separator())
        content.append(arts)

        root.set_content(content)
        self.set_content(root)

        # Guard against post-destroy widget updates
        self.connect("close-request", self._on_close_request)

    # ------------------------------------------------------------------
    # Tag chip toggle
    # ------------------------------------------------------------------

    def _on_tag_chip_toggled(self, btn, tag_name):
        if self._rebuilding:
            return
        if btn.get_active():
            self._selected_tags.add(tag_name)
        else:
            self._selected_tags.discard(tag_name)

    # ------------------------------------------------------------------
    # Delete Station
    # ------------------------------------------------------------------

    def _on_delete_clicked(self, *_):
        if self.is_playing and self.is_playing():
            dlg = Adw.MessageDialog(
                transient_for=self,
                heading="Cannot Delete Station",
                body="Stop playback before deleting this station.",
            )
            dlg.add_response("ok", "OK")
            dlg.set_default_response("ok")
            dlg.set_close_response("ok")
            dlg.present()
            return

        dlg = Adw.MessageDialog(
            transient_for=self,
            heading=f"Delete {self.station.name}?",
            body="This station will be permanently removed.",
        )
        dlg.add_response("cancel", "Keep Station")
        dlg.add_response("delete", "Delete")
        dlg.set_default_response("cancel")
        dlg.set_close_response("cancel")
        dlg.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dlg.connect("response", self._on_delete_response)
        dlg.present()

    def _on_delete_response(self, dialog, response):
        if response == "delete":
            self.repo.delete_station(self.station_id)
            if self.on_saved:
                self.on_saved()  # reload list to reflect deletion
            self.close()

    # ------------------------------------------------------------------
    # YouTube thumbnail fetch
    # ------------------------------------------------------------------

    def _on_url_focus_out(self, *_):
        url = self.url_entry.get_text().strip()
        if _is_youtube_url(url):
            self._start_thumbnail_fetch(url)
            self._start_title_fetch(url)

    def _on_fetch_clicked(self, *_):
        url = self.url_entry.get_text().strip()
        if _is_youtube_url(url):
            self._start_thumbnail_fetch(url)

    def _start_thumbnail_fetch(self, url: str):
        if self._thumb_fetch_in_progress:
            return  # race guard — skip if already fetching
        self._thumb_fetch_in_progress = True
        self._art_stack.set_visible_child_name("spinner")
        self._art_spinner.start()
        fetch_yt_thumbnail(url, self._on_thumbnail_fetched)

    def _on_thumbnail_fetched(self, temp_path):
        """Called via GLib.idle_add from fetch_yt_thumbnail — runs on main thread."""
        self._thumb_fetch_in_progress = False
        self._art_spinner.stop()
        if self._fetch_cancelled:
            return  # dialog was closed mid-fetch
        if temp_path:
            self.station_art_rel = copy_asset_for_station(
                self.station_id, temp_path, "station_art"
            )
            self._refresh_pictures()
            try:
                os.unlink(temp_path)
            except OSError:
                pass
        self._art_stack.set_visible_child_name("pic")

    def _on_close_request(self, *_):
        self._fetch_cancelled = True
        return False  # allow close to proceed

    def _start_title_fetch(self, url: str):
        if self._title_fetch_in_progress:
            return
        self._title_fetch_in_progress = True
        fetch_yt_title(url, self._on_title_fetched)

    def _on_title_fetched(self, title):
        self._title_fetch_in_progress = False
        if self._fetch_cancelled:
            return
        if title:
            title = re.sub(r'\s*\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2}(?::\d{2})?)?\s*$', '', title).strip()
            current = self.name_entry.get_text().strip()
            if current in ("", "New Station"):
                self.name_entry.set_text(title)

    # ------------------------------------------------------------------
    # Art helpers
    # ------------------------------------------------------------------

    def _refresh_pictures(self):
        # Use local files if set; otherwise empty
        if self.station_art_rel:
            abs_path = os.path.join(DATA_DIR, self.station_art_rel)
            if os.path.exists(abs_path):
                self.station_pic.set_filename(abs_path)
        else:
            self.station_pic.set_paintable(None)

        if self.album_art_rel:
            abs_path = os.path.join(DATA_DIR, self.album_art_rel)
            if os.path.exists(abs_path):
                self.album_pic.set_filename(abs_path)
        else:
            self.album_pic.set_paintable(None)

    def _choose_file(self, callback):
        dlg = Gtk.FileDialog(title="Choose image")
        # Add filters (png/jpg/webp)
        flt = Gtk.FileFilter()
        flt.set_name("Images")
        flt.add_mime_type("image/png")
        flt.add_mime_type("image/jpeg")
        flt.add_mime_type("image/webp")
        dlg.set_default_filter(flt)

        def done(dlg_obj, res):
            try:
                f = dlg_obj.open_finish(res)
                if not f:
                    return
                path = f.get_path()
                if path:
                    callback(path)
            except GLib.Error:
                return

        dlg.open(self, None, done)

    def _choose_station_art(self, *_):
        def set_art(path: str):
            self.station_art_rel = copy_asset_for_station(self.station_id, path, "station_art")
            self._refresh_pictures()
        self._choose_file(set_art)

    def _choose_album_art(self, *_):
        def set_art(path: str):
            self.album_art_rel = copy_asset_for_station(self.station_id, path, "album_fallback")
            self._refresh_pictures()
        self._choose_file(set_art)

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _save(self, *_):
        name = self.name_entry.get_text().strip() or "Unnamed"
        url = self.url_entry.get_text().strip()

        new_prov = self.new_provider_entry.get_text().strip()
        if new_prov:
            # Case-insensitive match against existing providers to avoid duplicates
            providers = self.repo.list_providers()
            match = next((p.name for p in providers if p.name.casefold() == new_prov.casefold()), None)
            provider_name = match if match else new_prov
        else:
            idx = self.provider_combo.get_selected()
            item = self.provider_combo.get_model().get_item(idx)
            provider_name = item.get_string() if item else ""

        new_tag = self.new_tag_entry.get_text().strip()
        all_selected = self._selected_tags | ({new_tag} if new_tag else set())
        tags = ", ".join(sorted(all_selected))

        provider_id = self.repo.ensure_provider(provider_name) if provider_name else None

        self.repo.update_station(
            station_id=self.station_id,
            name=name,
            url=url,
            provider_id=provider_id,
            tags=tags,
            station_art_path=self.station_art_rel,
            album_fallback_path=self.album_art_rel,
            icy_disabled=self.icy_switch.get_active(),
        )

        if self.on_saved:
            self.on_saved()
        self.close()
