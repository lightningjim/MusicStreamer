import os
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib
from musicstreamer.models import Station
from musicstreamer.constants import DATA_DIR


class StationRow(Gtk.ListBoxRow):
    def __init__(self, station: Station):
        super().__init__()
        self.station = station          # full object for Phase 2 filter_func
        self.station_id = station.id   # backward compat

        provider = station.provider_name or "Unknown"
        subtitle = provider
        if station.tags:
            subtitle += f" • {station.tags}"

        row = Adw.ActionRow(
            title=GLib.markup_escape_text(station.name, -1),
            subtitle=GLib.markup_escape_text(subtitle, -1),
        )
        row.set_activatable(False)

        has_art = False
        if station.station_art_path:
            abs_path = os.path.join(DATA_DIR, station.station_art_path)
            if os.path.exists(abs_path):
                pic = Gtk.Picture.new_for_filename(abs_path)
                pic.set_size_request(48, 48)
                pic.set_content_fit(Gtk.ContentFit.COVER)
                row.add_prefix(pic)
                has_art = True

        if not has_art:
            placeholder = Gtk.Image.new_from_icon_name("audio-x-generic-symbolic")
            placeholder.set_pixel_size(48)
            row.add_prefix(placeholder)

        self.set_child(row)
