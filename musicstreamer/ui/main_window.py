import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw
from musicstreamer.repo import Repo
from musicstreamer.models import Station
from musicstreamer.player import Player
from musicstreamer.ui.station_row import StationRow
from musicstreamer.ui.edit_dialog import EditStationDialog
from musicstreamer.filter_utils import normalize_tags, matches_filter


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app, repo: Repo):
        super().__init__(application=app, title="MusicStreamer")
        self.repo = repo
        self.set_default_size(900, 650)

        shell = Adw.ToolbarView()
        header = Adw.HeaderBar()

        # --- Playback engine ---
        self.player = Player()

        # --- Now-playing label (kept as instance var; used by _stop and _play_station) ---
        self.now_label = Gtk.Label(label="Now Playing: —", xalign=0)
        stop_btn = Gtk.Button(label="Stop")
        stop_btn.connect("clicked", lambda *_: self._stop())

        add_btn = Gtk.Button(label="Add Station")
        add_btn.connect("clicked", self._add_station)
        header.pack_start(add_btn)

        edit_btn = Gtk.Button(label="Edit")
        edit_btn.connect("clicked", self._edit_selected)
        header.pack_start(edit_btn)

        header.pack_end(stop_btn)

        # --- Search entry in header center ---
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search stations\u2026")
        self.search_entry.connect("search-changed", self._on_filter_changed)
        header.set_title_widget(self.search_entry)

        shell.add_top_bar(header)

        # --- Filter strip ---
        filter_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        filter_box.set_margin_top(4)
        filter_box.set_margin_bottom(4)
        filter_box.set_margin_start(8)
        filter_box.set_margin_end(8)

        self._provider_items = ["All Providers"]
        self.provider_dropdown = Gtk.DropDown.new(Gtk.StringList.new(self._provider_items), None)
        self.provider_dropdown.set_size_request(120, -1)
        self.provider_dropdown.connect("notify::selected", self._on_filter_changed)

        self._tag_items = ["All Tags"]
        self.tag_dropdown = Gtk.DropDown.new(Gtk.StringList.new(self._tag_items), None)
        self.tag_dropdown.set_size_request(120, -1)
        self.tag_dropdown.connect("notify::selected", self._on_filter_changed)

        self.clear_btn = Gtk.Button(label="Clear")
        self.clear_btn.set_visible(False)
        self.clear_btn.connect("clicked", self._on_clear)

        filter_box.append(self.provider_dropdown)
        filter_box.append(self.tag_dropdown)
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        filter_box.append(spacer)
        filter_box.append(self.clear_btn)
        shell.add_top_bar(filter_box)

        # --- Station list ---
        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.listbox.connect("row-activated", self._play_row)

        scroller = Gtk.ScrolledWindow()
        scroller.set_child(self.listbox)

        # Store for empty-state swapping
        self.shell = shell
        self.scroller = scroller

        # --- Empty state ---
        self.empty_page = Adw.StatusPage()
        self.empty_page.set_title("No stations match your filters")
        self.empty_page.set_description("Try different search terms or clear your filters.")
        clear_all_btn = Gtk.Button(label="Clear Filters")
        clear_all_btn.set_halign(Gtk.Align.CENTER)
        clear_all_btn.connect("clicked", self._on_clear)
        self.empty_page.set_child(clear_all_btn)

        # Guard flag for dropdown model rebuilds
        self._rebuilding = False
        self._visible_count = 0

        # Wire filter func
        self.listbox.set_filter_func(self._filter_func)

        shell.set_content(scroller)
        self.set_content(shell)

        self.reload_list()

    # ------------------------------------------------------------------ #
    # Filter logic
    # ------------------------------------------------------------------ #

    def _filter_func(self, row):
        station = row.station
        search_text = self.search_entry.get_text()
        prov_idx = self.provider_dropdown.get_selected()
        provider_filter = self._provider_items[prov_idx] if prov_idx > 0 else None
        tag_idx = self.tag_dropdown.get_selected()
        tag_filter = self._tag_items[tag_idx] if tag_idx > 0 else None
        result = matches_filter(station, search_text, provider_filter, tag_filter)
        if result:
            self._visible_count += 1
        return result

    def _on_filter_changed(self, *_):
        if self._rebuilding:
            return
        self._visible_count = 0
        self.listbox.invalidate_filter()
        self._update_clear_button()
        self._update_empty_state()

    def _any_filter_active(self) -> bool:
        return (
            bool(self.search_entry.get_text())
            or self.provider_dropdown.get_selected() > 0
            or self.tag_dropdown.get_selected() > 0
        )

    def _update_clear_button(self):
        self.clear_btn.set_visible(self._any_filter_active())

    def _update_empty_state(self):
        if self._visible_count == 0 and self._any_filter_active():
            self.shell.set_content(self.empty_page)
        else:
            self.shell.set_content(self.scroller)

    def _on_clear(self, *_):
        self.search_entry.set_text("")
        self.provider_dropdown.set_selected(0)
        self.tag_dropdown.set_selected(0)
        self._on_filter_changed()

    def _rebuild_filter_state(self):
        self._rebuilding = True
        stations = self.repo.list_stations()

        providers = sorted({s.provider_name for s in stations if s.provider_name})
        self._provider_items = ["All Providers"] + providers
        self.provider_dropdown.set_model(Gtk.StringList.new(self._provider_items))

        all_tags: dict[str, str] = {}
        for s in stations:
            for t in normalize_tags(s.tags):
                key = t.casefold()
                if key not in all_tags:
                    all_tags[key] = t
        self._tag_items = ["All Tags"] + sorted(all_tags.values(), key=str.casefold)
        self.tag_dropdown.set_model(Gtk.StringList.new(self._tag_items))

        self._rebuilding = False

    # ------------------------------------------------------------------ #
    # Playback
    # ------------------------------------------------------------------ #

    def _stop(self):
        self.player.stop()
        self.now_label.set_text("Now Playing: —")

    def _play_row(self, _listbox, row):
        station_id = row.station_id
        st = self.repo.get_station(station_id)
        self._play_station(st)

    def _play_station(self, st: Station):
        self.player.play(st, on_title=lambda t: self.now_label.set_text(f"Now Playing: {t}"))

    # ------------------------------------------------------------------ #
    # Station list
    # ------------------------------------------------------------------ #

    def reload_list(self):
        child = self.listbox.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self.listbox.remove(child)
            child = nxt

        for st in self.repo.list_stations():
            row = StationRow(st)
            self.listbox.append(row)

        self._rebuild_filter_state()

    # ------------------------------------------------------------------ #
    # Station edit
    # ------------------------------------------------------------------ #

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
