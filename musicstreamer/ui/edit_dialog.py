import os
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


class EditStationDialog(Adw.Window):
    def __init__(self, app, repo: Repo, station_id: int, on_saved, is_playing=None):
        super().__init__(application=app, title="Edit Station")
        self.repo = repo
        self.station_id = station_id
        self.on_saved = on_saved
        self.is_playing = is_playing

        self.set_default_size(560, 420)

        self.station = repo.get_station(station_id)

        # Keep current paths
        self.station_art_rel = self.station.station_art_path
        self.album_art_rel = self.station.album_fallback_path

        root = Adw.ToolbarView()
        header = Adw.HeaderBar()

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
        self.provider_entry = Gtk.Entry(text=self.station.provider_name or "")
        self.tags_entry = Gtk.Entry(text=self.station.tags)
        self.tags_entry.set_placeholder_text("Comma-separated tags (e.g. Chillout, Ambient)")

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

        album_art_btn = Gtk.Button(label="Choose Default Album Art…")
        album_art_btn.connect("clicked", self._choose_album_art)

        form = Gtk.Grid(column_spacing=12, row_spacing=12)
        form.attach(Gtk.Label(label="Name", xalign=0), 0, 0, 1, 1)
        form.attach(self.name_entry, 1, 0, 1, 1)

        form.attach(Gtk.Label(label="URL", xalign=0), 0, 1, 1, 1)
        form.attach(self.url_entry, 1, 1, 1, 1)

        form.attach(Gtk.Label(label="Provider", xalign=0), 0, 2, 1, 1)
        form.attach(self.provider_entry, 1, 2, 1, 1)

        form.attach(Gtk.Label(label="Tags", xalign=0), 0, 3, 1, 1)
        form.attach(self.tags_entry, 1, 3, 1, 1)

        arts = Gtk.Grid(column_spacing=12, row_spacing=12)
        arts.attach(Gtk.Label(label="Station Art", xalign=0), 0, 0, 1, 1)
        arts.attach(self.station_pic, 0, 1, 1, 1)
        arts.attach(station_art_btn, 0, 2, 1, 1)

        arts.attach(Gtk.Label(label="Default Album Art", xalign=0), 1, 0, 1, 1)
        arts.attach(self.album_pic, 1, 1, 1, 1)
        arts.attach(album_art_btn, 1, 2, 1, 1)

        content.append(form)
        content.append(Gtk.Separator())
        content.append(arts)

        root.set_content(content)
        self.set_content(root)

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

    def _save(self, *_):
        name = self.name_entry.get_text().strip() or "Unnamed"
        url = self.url_entry.get_text().strip()
        provider_name = self.provider_entry.get_text().strip()
        tags = self.tags_entry.get_text().strip()

        provider_id = self.repo.ensure_provider(provider_name) if provider_name else None

        self.repo.update_station(
            station_id=self.station_id,
            name=name,
            url=url,
            provider_id=provider_id,
            tags=tags,
            station_art_path=self.station_art_rel,
            album_fallback_path=self.album_art_rel,
        )

        if self.on_saved:
            self.on_saved()
        self.close()
