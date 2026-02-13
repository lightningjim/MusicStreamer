#!/usr/bin/env python3
import gi, json, subprocess, threading, os
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gst", "1.0")

from gi.repository import Gtk, Adw, Gst, Gio, GLib

CONFIG_PATH = os.path.expanduser("~/.config/gnome-streamer")
STATIONS_FILE = os.path.join(CONFIG_PATH, ".venv/stations.json")

Gst.init(None)


class StreamerApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="org.example.Streamer")
        self.player = Gst.ElementFactory.make("playbin", "player")
        fake_video = Gst.ElementFactory.make("fakesink", "fake-video")
        self.player.set_property("video-sink", fake_video)
        self.current_uri = None
        self.stations = []
        bus = self.player.get_bus()
        bus.add_signal_watch()
        bus.connect("message::tag", self.on_tag_message)



    def do_activate(self):
        win = Adw.ApplicationWindow(application=self, title="GNOME Streamer")
        win.set_default_size(420, 300)

        self.load_stations()

        # Main UI containers
        self.station_list = Gtk.ListBox()
        self.refresh_station_list()

        add_button = Gtk.Button(label="Add Station")
        add_button.connect("clicked", self.on_add_station)

        stop_button = Gtk.Button(label="Stop")
        stop_button.connect("clicked", lambda *_: self.stop())

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        controls.append(add_button)
        controls.append(stop_button)
        self.now_playing_label = Gtk.Label(label="Now Playing: —", xalign=0)


        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6,
            margin_top=12,
            margin_bottom=12,
            margin_start=12,
            margin_end=12)
        box.append(self.now_playing_label)
        box.append(self.station_list)
        box.append(controls)

        win.set_content(box)
        win.present()

    # Load and save stations
    def load_stations(self):
        os.makedirs(CONFIG_PATH, exist_ok=True)
        if not os.path.exists(STATIONS_FILE):
            default = [
                {"name": "Chillhop", "url": "https://streams.chillhop.com/live?type=.mp3"},
                {"name": "Lo-Fi Girl (YouTube)", "url": "https://www.youtube.com/watch?v=jfKfPfyJRdk"}
            ]
            with open(STATIONS_FILE, "w") as f:
                json.dump(default, f, indent=2)
        with open(STATIONS_FILE) as f:
            self.stations = json.load(f)

    def save_stations(self):
        with open(STATIONS_FILE, "w") as f:
            json.dump(self.stations, f, indent=2)

    def refresh_station_list(self):
        # Remove all existing rows first
        child = self.station_list.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.station_list.remove(child)
            child = next_child

        # Rebuild the list
        for st in self.stations:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            label = Gtk.Label(label=st["name"], xalign=0)
            btn = Gtk.Button(label="Play")
            btn.connect("clicked", self.on_play_clicked, st)
            row.append(label)
            row.append(btn)

            listrow = Gtk.ListBoxRow()
            listrow.set_child(row)
            self.station_list.append(listrow)

    # Playback
    def on_play_clicked(self, btn, station):
        threading.Thread(target=self.start_stream, args=(station,), daemon=True).start()

    from yt_dlp import YoutubeDL

    def resolve_youtube_url(self, url):
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'noplaylist': True,
            'extract_flat': False,
            'format': 'best[protocol^=m3u8]/best',
            'cachedir': False
        }
        with self.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            # Choose the direct stream URL
            if 'url' in info:
                return info['url']
            elif 'entries' in info:
                return info['entries'][0]['url']
            else:
                return None

    def start_stream(self, station):
        url = station["url"]
        print(f"Resolving: {url}")

        if "youtube.com" in url or "youtu.be" in url:
            stream_url = self.resolve_youtube_url(url)
            if not stream_url:
                print("Could not extract stream URL.")
                return
        else:
            stream_url = url

        print(f"Playing: {stream_url}")
        self.player.set_state(Gst.State.NULL)
        self.player.set_property("uri", stream_url)
        self.player.set_state(Gst.State.PLAYING)

    def stop(self):
        self.player.set_state(Gst.State.NULL)
        self.current_uri = None
        print("Stopped playback")

    # Add station dialog
    def on_add_station(self, *_):
        dialog = Adw.MessageDialog(
            heading="Add New Station",
            body="Enter the name and stream/YouTube URL:"
        )

        name_entry = Gtk.Entry(placeholder_text="Station Name")
        url_entry = Gtk.Entry(placeholder_text="Stream or YouTube URL")

        grid = Gtk.Grid(row_spacing=6, column_spacing=6)
        grid.attach(Gtk.Label(label="Name:"), 0, 0, 1, 1)
        grid.attach(name_entry, 1, 0, 1, 1)
        grid.attach(Gtk.Label(label="URL:"), 0, 1, 1, 1)
        grid.attach(url_entry, 1, 1, 1, 1)

        dialog.set_extra_child(grid)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("add", "Add")
        dialog.set_response_appearance("add", Adw.ResponseAppearance.SUGGESTED)

    def on_response(dlg, response):
        if response == "add":
            name = name_entry.get_text().strip()
            url = url_entry.get_text().strip()
            if name and url:
                self.stations.append({"name": name, "url": url})
                self.save_stations()
                self.refresh_station_list()
                print(f"Added station: {name} → {url}")
        dlg.close()

        dialog.connect("response", on_response)
        dialog.set_transient_for(self.get_active_window())
        dialog.present()

    def on_tag_message(self, bus, message):
        tag_list = message.parse_tag()

        title = artist = album = station = None

        # Safely extract known tags
        title_val = tag_list.get_string("title")
        if title_val and title_val[0]:
            title = title_val[1]

        artist_val = tag_list.get_string("artist")
        if artist_val and artist_val[0]:
            artist = artist_val[1]

        album_val = tag_list.get_string("album")
        if album_val and album_val[0]:
            album = album_val[1]

        org_val = tag_list.get_string("organization")
        if org_val and org_val[0]:
            station = org_val[1]

        # Build display text
        parts = []
        if artist:
            parts.append(artist)
        if title:
            parts.append(f"– {title}")
        if album:
            parts.append(f"({album})")
        if station:
            parts.append(f"[{station}]")

        text = "Now Playing: " + " ".join(parts) if parts else "Now Playing: —"

        GLib.idle_add(self.now_playing_label.set_text, text)
        for i in range(tag_list.n_tags()):
            name = tag_list.nth_tag_name(i)
            val = tag_list.get_value_index(name, 0)
            print(f"{name}: {val}")


if __name__ == "__main__":
    app = StreamerApp()
    app.run()
