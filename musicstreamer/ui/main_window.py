import os
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Pango", "1.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk, Adw, Pango, GdkPixbuf, GLib
from musicstreamer.cover_art import fetch_cover_art, is_junk_title
from musicstreamer.repo import Repo
from musicstreamer.models import Station
from musicstreamer.player import Player
from musicstreamer.ui.station_row import StationRow
from musicstreamer.ui.edit_dialog import EditStationDialog
from musicstreamer.filter_utils import normalize_tags, matches_filter
from musicstreamer.constants import DATA_DIR


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app, repo: Repo):
        super().__init__(application=app, title="MusicStreamer")
        self.repo = repo
        self.set_default_size(900, 650)

        shell = Adw.ToolbarView()
        header = Adw.HeaderBar()

        # --- Playback engine ---
        self.player = Player()

        # --- Search entry in header center (only content in HeaderBar) ---
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search stations\u2026")
        self.search_entry.connect("search-changed", self._on_filter_changed)
        header.set_title_widget(self.search_entry)

        shell.add_top_bar(header)

        # --- Now-playing panel ---
        panel = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        panel.set_margin_top(4)
        panel.set_margin_bottom(4)
        panel.set_margin_start(8)
        panel.set_margin_end(8)
        panel.set_size_request(-1, 160)
        panel.set_vexpand(False)

        # Left slot -- station logo with Gtk.Stack for fallback swap
        self.logo_image = Gtk.Image()
        self.logo_image.set_pixel_size(160)
        self.logo_image.set_size_request(160, 160)
        self.logo_image.set_vexpand(False)
        self.logo_image.set_hexpand(False)

        self.logo_fallback = Gtk.Image.new_from_icon_name("audio-x-generic-symbolic")
        self.logo_fallback.set_pixel_size(160)

        self.logo_stack = Gtk.Stack()
        self.logo_stack.set_size_request(160, 160)
        self.logo_stack.set_vexpand(False)
        self.logo_stack.set_hexpand(False)
        self.logo_stack.add_named(self.logo_fallback, "fallback")
        self.logo_stack.add_named(self.logo_image, "logo")
        self.logo_stack.set_visible_child_name("fallback")

        panel.append(self.logo_stack)

        # Center column -- track title + station name + stop button
        center = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        center.set_hexpand(True)
        center.set_valign(Gtk.Align.CENTER)

        self.title_label = Gtk.Label(label="Nothing playing")
        self.title_label.add_css_class("dim-label")
        self.title_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.title_label.set_xalign(0)
        center.append(self.title_label)

        self.station_name_label = Gtk.Label()
        self.station_name_label.add_css_class("dim-label")
        self.station_name_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.station_name_label.set_xalign(0)
        self.station_name_label.set_visible(False)
        center.append(self.station_name_label)

        self.stop_btn = Gtk.Button(label="Stop")
        self.stop_btn.add_css_class("suggested-action")
        self.stop_btn.set_sensitive(False)
        self.stop_btn.set_halign(Gtk.Align.START)
        self.stop_btn.connect("clicked", lambda *_: self._stop())
        center.append(self.stop_btn)

        panel.append(center)

        # Right slot -- cover art with Gtk.Stack for fallback swap
        self.cover_image = Gtk.Image()
        self.cover_image.set_pixel_size(160)
        self.cover_image.set_size_request(160, 160)
        self.cover_image.set_vexpand(False)
        self.cover_image.set_hexpand(False)

        self.cover_fallback = Gtk.Image.new_from_icon_name("audio-x-generic-symbolic")
        self.cover_fallback.set_pixel_size(160)

        self.cover_stack = Gtk.Stack()
        self.cover_stack.set_size_request(160, 160)
        self.cover_stack.set_vexpand(False)
        self.cover_stack.set_hexpand(False)
        self.cover_stack.add_named(self.cover_fallback, "fallback")
        self.cover_stack.add_named(self.cover_image, "art")
        self.cover_stack.set_visible_child_name("fallback")

        panel.append(self.cover_stack)

        shell.add_top_bar(panel)

        # --- Filter strip ---
        filter_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        filter_box.set_margin_top(4)
        filter_box.set_margin_bottom(4)
        filter_box.set_margin_start(8)
        filter_box.set_margin_end(8)

        add_btn = Gtk.Button(label="Add Station")
        add_btn.connect("clicked", self._add_station)

        edit_btn = Gtk.Button(label="Edit")
        edit_btn.connect("clicked", self._edit_selected)

        self._provider_items = ["All Providers"]
        self.provider_dropdown = Gtk.DropDown.new(Gtk.StringList.new(self._provider_items), None)
        self.provider_dropdown.set_size_request(160, -1)
        self.provider_dropdown.connect("notify::selected", self._on_filter_changed)

        self._tag_items = ["All Tags"]
        self.tag_dropdown = Gtk.DropDown.new(Gtk.StringList.new(self._tag_items), None)
        self.tag_dropdown.set_size_request(160, -1)
        self.tag_dropdown.connect("notify::selected", self._on_filter_changed)

        self.clear_btn = Gtk.Button(label="Clear")
        self.clear_btn.set_visible(False)
        self.clear_btn.connect("clicked", self._on_clear)

        filter_box.append(add_btn)
        filter_box.append(edit_btn)
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
        self._last_cover_icy = None

        # Wire filter func
        self.listbox.set_filter_func(self._filter_func)

        shell.set_content(scroller)
        self.set_content(shell)
        self.connect("close-request", self._on_close)

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

    def _on_cover_art(self, icy_string: str):
        """Called when a TAG message provides a new ICY title. Fetches cover art."""
        if icy_string == self._last_cover_icy:
            return  # dedup — same title, skip API call
        if is_junk_title(icy_string):
            self._last_cover_icy = None
            self.cover_stack.set_visible_child_name("fallback")
            return
        self._last_cover_icy = icy_string

        def _on_art_fetched(temp_path):
            """Callback from background thread — must use GLib.idle_add."""
            def _update_ui():
                if temp_path is None:
                    self.cover_stack.set_visible_child_name("fallback")
                else:
                    try:
                        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(temp_path, 160, 160, False)
                        self.cover_image.set_from_pixbuf(pixbuf)
                        self.cover_stack.set_visible_child_name("art")
                    except Exception:
                        self.cover_stack.set_visible_child_name("fallback")
                    finally:
                        import os
                        try:
                            os.unlink(temp_path)
                        except OSError:
                            pass
                return False  # GLib.idle_add: do not repeat
            GLib.idle_add(_update_ui)

        fetch_cover_art(icy_string, _on_art_fetched)

    def _on_close(self, *_):
        self.player.stop()
        return False

    def _stop(self):
        self.player.stop()
        self.title_label.set_text("Nothing playing")
        self.title_label.remove_css_class("title-3")
        self.title_label.add_css_class("dim-label")
        self.station_name_label.set_visible(False)
        self.logo_stack.set_visible_child_name("fallback")
        self.cover_stack.set_visible_child_name("fallback")
        self._last_cover_icy = None
        self.stop_btn.set_sensitive(False)

    def _play_row(self, _listbox, row):
        station_id = row.station_id
        st = self.repo.get_station(station_id)
        self._play_station(st)

    def _play_station(self, st: Station):
        # Set station name label
        self.station_name_label.set_text(st.name)
        self.station_name_label.set_visible(True)

        # Set title to station name initially (overwritten by TAG for ICY streams)
        self.title_label.set_text(st.name)
        self.title_label.remove_css_class("dim-label")
        self.title_label.add_css_class("title-3")

        # Load station logo scaled to 96x96 to prevent panel from expanding
        if st.station_art_path:
            abs_path = os.path.join(DATA_DIR, st.station_art_path)
            if os.path.exists(abs_path):
                try:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(abs_path, 160, 160, False)
                    self.logo_image.set_from_pixbuf(pixbuf)
                    self.logo_stack.set_visible_child_name("logo")
                except Exception:
                    self.logo_stack.set_visible_child_name("fallback")
            else:
                self.logo_stack.set_visible_child_name("fallback")
        else:
            self.logo_stack.set_visible_child_name("fallback")

        # Enable stop button
        self.stop_btn.set_sensitive(True)

        # Start playback -- on_title callback updates title_label and cover art
        def _on_title(title):
            self.title_label.set_text(title)
            self._on_cover_art(title)
        self.player.play(st, on_title=_on_title)

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
