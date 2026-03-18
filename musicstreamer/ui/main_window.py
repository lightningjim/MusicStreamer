import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw
from musicstreamer.repo import Repo
from musicstreamer.models import Station
from musicstreamer.player import Player
from musicstreamer.ui.station_row import StationRow
from musicstreamer.ui.edit_dialog import EditStationDialog


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app, repo: Repo):
        super().__init__(application=app, title="MusicStreamer")
        self.repo = repo
        self.set_default_size(900, 650)

        shell = Adw.ToolbarView()
        header = Adw.HeaderBar()

        # --- Playback engine ---
        self.player = Player()

        # --- Minimal controls (for testing) ---
        self.now_label = Gtk.Label(label="Now Playing: —", xalign=0)
        stop_btn = Gtk.Button(label="Stop")
        stop_btn.connect("clicked", lambda *_: self._stop())

        add_btn = Gtk.Button(label="Add Station")
        add_btn.connect("clicked", self._add_station)
        header.pack_start(add_btn)
        header.pack_start(self.now_label)
        header.pack_end(stop_btn)

        shell.add_top_bar(header)

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        # Double-click a station row to play (for testing)
        self.listbox.connect("row-activated", self._play_row)

        scroller = Gtk.ScrolledWindow()
        scroller.set_child(self.listbox)

        shell.set_content(scroller)
        self.set_content(shell)

        self.reload_list()

    def _stop(self):
        self.player.stop()
        self.now_label.set_text("Now Playing: —")

    def _play_row(self, _listbox, row):
        station_id = row.station_id
        st = self.repo.get_station(station_id)
        self._play_station(st)

    def _play_station(self, st: Station):
        self.player.play(st, on_title=lambda t: self.now_label.set_text(f"Now Playing: {t}"))

    def reload_list(self):
        # Clear listbox (GTK4 child traversal)
        child = self.listbox.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self.listbox.remove(child)
            child = nxt

        for st in self.repo.list_stations():
            row = StationRow(st)
            self.listbox.append(row)

    def _add_station(self, *_):
        station_id = self.repo.create_station()
        self._open_editor(station_id)

    def _edit_selected(self, *_):
        row = self.listbox.get_selected_row()
        if row:
            self._open_editor(row.station_id)

    def _open_editor(self, station_id: int):
        dlg = EditStationDialog(self.get_application(), self.repo, station_id, on_saved=self.reload_list)
        dlg.set_transient_for(self)
        dlg.present()
