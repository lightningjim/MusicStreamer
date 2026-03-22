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
from musicstreamer.filter_utils import normalize_tags, matches_filter_multi
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

        # Chip strip container (vertical — two rows of chips)
        chip_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        chip_container.set_hexpand(True)

        # Provider chip row
        self._provider_scroll = Gtk.ScrolledWindow()
        self._provider_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self._provider_scroll.set_margin_top(4)
        self._provider_scroll.set_margin_bottom(4)
        self._provider_scroll.set_margin_start(8)
        self._provider_scroll.set_margin_end(8)
        self._provider_chip_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._provider_scroll.set_child(self._provider_chip_box)
        chip_container.append(self._provider_scroll)

        # Tag chip row
        self._tag_scroll = Gtk.ScrolledWindow()
        self._tag_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self._tag_scroll.set_margin_top(4)
        self._tag_scroll.set_margin_bottom(4)
        self._tag_scroll.set_margin_start(8)
        self._tag_scroll.set_margin_end(8)
        self._tag_chip_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._tag_scroll.set_child(self._tag_chip_box)
        chip_container.append(self._tag_scroll)

        self.clear_btn = Gtk.Button(label="Clear")
        self.clear_btn.set_visible(False)
        self.clear_btn.connect("clicked", self._on_clear)

        filter_box.append(add_btn)
        filter_box.append(edit_btn)
        filter_box.append(chip_container)
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

        # Guard flag for chip strip rebuilds
        self._rebuilding = False
        self._rp_rows: list = []  # recently played row refs (Plan 03 will populate)
        self._last_cover_icy = None
        self._current_station = None
        self._selected_providers: set[str] = set()
        self._selected_tags: set[str] = set()
        self._provider_chip_btns: list[Gtk.ToggleButton] = []
        self._tag_chip_btns: list[Gtk.ToggleButton] = []

        shell.set_content(scroller)
        self.set_content(shell)
        self.connect("close-request", self._on_close)

        self.reload_list()

    # ------------------------------------------------------------------ #
    # Filter logic
    # ------------------------------------------------------------------ #

    def _on_filter_changed(self, *_):
        if self._rebuilding:
            return
        self._render_list()
        self._update_clear_button()

    def _any_filter_active(self) -> bool:
        return (
            bool(self.search_entry.get_text())
            or bool(self._selected_providers)
            or bool(self._selected_tags)
        )

    def _update_clear_button(self):
        self.clear_btn.set_visible(self._any_filter_active())

    def _on_clear(self, *_):
        self.search_entry.set_text("")
        self._rebuilding = True
        for btn in self._provider_chip_btns:
            btn.set_active(False)
        for btn in self._tag_chip_btns:
            btn.set_active(False)
        self._selected_providers.clear()
        self._selected_tags.clear()
        self._rebuilding = False
        self._on_filter_changed()

    def _make_chip(self, label: str, toggle_cb) -> tuple[Gtk.Box, Gtk.ToggleButton]:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        btn = Gtk.ToggleButton(label=label)
        btn.connect("toggled", toggle_cb)
        dismiss = Gtk.Button()
        dismiss.set_icon_name("window-close-symbolic")
        dismiss.add_css_class("flat")
        dismiss.connect("clicked", lambda *_: btn.set_active(False))
        box.append(btn)
        box.append(dismiss)
        return box, btn

    def _make_provider_toggle_cb(self, provider_name: str):
        def _cb(btn):
            if self._rebuilding:
                return
            if btn.get_active():
                self._selected_providers.add(provider_name)
            else:
                self._selected_providers.discard(provider_name)
            self._on_filter_changed()
        return _cb

    def _make_tag_toggle_cb(self, tag_name: str):
        def _cb(btn):
            if self._rebuilding:
                return
            if btn.get_active():
                self._selected_tags.add(tag_name)
            else:
                self._selected_tags.discard(tag_name)
            self._on_filter_changed()
        return _cb

    def _rebuild_filter_state(self):
        self._rebuilding = True
        stations = self.repo.list_stations()

        # --- Provider chips ---
        # Clear existing chips
        child = self._provider_chip_box.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self._provider_chip_box.remove(child)
            child = nxt
        self._provider_chip_btns = []

        providers = sorted({s.provider_name for s in stations if s.provider_name})
        for pname in providers:
            chip_box, btn = self._make_chip(pname, self._make_provider_toggle_cb(pname))
            if pname in self._selected_providers:
                btn.set_active(True)
            self._provider_chip_box.append(chip_box)
            self._provider_chip_btns.append(btn)

        # --- Tag chips ---
        child = self._tag_chip_box.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self._tag_chip_box.remove(child)
            child = nxt
        self._tag_chip_btns = []

        all_tags: dict[str, str] = {}
        for s in stations:
            for t in normalize_tags(s.tags):
                key = t.casefold()
                if key not in all_tags:
                    all_tags[key] = t
        for tag_display in sorted(all_tags.values(), key=str.casefold):
            chip_box, btn = self._make_chip(tag_display, self._make_tag_toggle_cb(tag_display))
            if tag_display in self._selected_tags:
                btn.set_active(True)
            self._tag_chip_box.append(chip_box)
            self._tag_chip_btns.append(btn)

        # Remove stale selections (provider/tag no longer exists)
        current_providers = set(providers)
        self._selected_providers &= current_providers
        current_tag_displays = set(all_tags.values())
        self._selected_tags &= current_tag_displays

        self._rebuilding = False

    # ------------------------------------------------------------------ #
    # List rendering
    # ------------------------------------------------------------------ #

    def _clear_listbox(self):
        child = self.listbox.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self.listbox.remove(child)
            child = nxt

    def _render_list(self):
        stations = self.repo.list_stations()
        search_text = self.search_entry.get_text().strip()
        tag_set = {t.casefold() for t in self._selected_tags}

        # Tag filter applies in both modes (D-07)
        if tag_set:
            stations = [s for s in stations if matches_filter_multi(s, "", set(), tag_set)]

        # Provider filter active -> flat mode (D-05, D-06)
        if self._selected_providers:
            filtered = [s for s in stations
                        if matches_filter_multi(s, search_text, self._selected_providers, set())]
            self._rebuild_flat(filtered)
        else:
            self._rebuild_grouped(stations, search_text)

    def _rebuild_grouped(self, stations, search_text=""):
        self._clear_listbox()
        self._rp_rows = []

        # Recently Played section (per D-06, D-07, D-15)
        # Only show when no filter is active and there are recently played stations
        if not search_text and not self._any_filter_active():
            rp_count = int(self.repo.get_setting("recently_played_count", "3"))
            recently_played = self.repo.list_recently_played(rp_count)
            if recently_played:
                # Header label row (non-interactive)
                label = Gtk.Label(label="Recently Played")
                label.set_margin_top(8)
                label.set_margin_bottom(4)
                label.set_margin_start(12)
                label.set_margin_end(8)
                label.set_xalign(0.0)
                header_row = Gtk.ListBoxRow()
                header_row.set_activatable(False)
                header_row.set_selectable(False)
                header_row.set_child(label)
                self.listbox.append(header_row)
                self._rp_rows.append(header_row)

                # Station rows (StationRow — direct listbox children, playable via row-activated)
                for st in recently_played:
                    row = StationRow(st)
                    self.listbox.append(row)
                    self._rp_rows.append(row)

        # Group stations by provider name
        groups: dict[str, list] = {}
        uncategorized: list = []
        for st in stations:
            if search_text and search_text.casefold() not in st.name.casefold():
                continue
            if st.provider_name:
                groups.setdefault(st.provider_name, []).append(st)
            else:
                uncategorized.append(st)

        # Add provider groups alphabetically (per D-01, D-02)
        for provider_name in sorted(groups.keys()):
            provider_stations = groups[provider_name]
            group = Adw.ExpanderRow()
            group.set_title(GLib.markup_escape_text(provider_name, -1))
            group.set_expanded(False)  # D-02: collapsed by default

            for st in provider_stations:
                row = self._make_action_row(st)
                group.add_row(row)

            self.listbox.append(group)

        # Uncategorized group at bottom (per D-04, D-05)
        if uncategorized:
            group = Adw.ExpanderRow()
            group.set_title("Uncategorized")
            group.set_expanded(False)  # D-05

            for st in uncategorized:
                row = self._make_action_row(st)
                group.add_row(row)

            self.listbox.append(group)

        # Empty state check
        total_stations = sum(len(v) for v in groups.values()) + len(uncategorized)
        if total_stations == 0 and self._any_filter_active():
            self.shell.set_content(self.empty_page)
        else:
            self.shell.set_content(self.scroller)

    def _rebuild_flat(self, stations):
        self._clear_listbox()
        self._rp_rows = []

        for st in stations:
            row = StationRow(st)
            self.listbox.append(row)

        if not stations and self._any_filter_active():
            self.shell.set_content(self.empty_page)
        else:
            self.shell.set_content(self.scroller)

    def _make_action_row(self, st: Station) -> Adw.ActionRow:
        provider = st.provider_name or "Unknown"
        subtitle = provider
        if st.tags:
            subtitle += f" \u2022 {st.tags}"

        ar = Adw.ActionRow(
            title=GLib.markup_escape_text(st.name, -1),
            subtitle=GLib.markup_escape_text(subtitle, -1),
        )
        ar.set_activatable(True)

        # Station art prefix (same pattern as StationRow)
        has_art = False
        if st.station_art_path:
            abs_path = os.path.join(DATA_DIR, st.station_art_path)
            if os.path.exists(abs_path):
                pic = Gtk.Picture.new_for_filename(abs_path)
                pic.set_size_request(48, 48)
                pic.set_content_fit(Gtk.ContentFit.COVER)
                ar.add_prefix(pic)
                has_art = True
        if not has_art:
            placeholder = Gtk.Image.new_from_icon_name("audio-x-generic-symbolic")
            placeholder.set_pixel_size(48)
            ar.add_prefix(placeholder)

        # Connect activated signal — ExpanderRow children don't trigger listbox row-activated
        # (per RESEARCH.md Pitfall 2)
        ar.connect("activated", lambda r, _sid=st.id: self._play_by_id(_sid))
        return ar

    def _refresh_recently_played(self):
        """Replace Recently Played rows in-place without rebuilding the full list.

        Preserves ExpanderRow expand/collapse state (Pitfall 3).
        Only operates in grouped mode (RP is hidden in flat mode).
        """
        # If any filter is active, RP is hidden — nothing to refresh
        if self._any_filter_active():
            return

        # Remove existing RP rows
        for row in self._rp_rows:
            self.listbox.remove(row)
        self._rp_rows = []

        # Get fresh RP data
        rp_count = int(self.repo.get_setting("recently_played_count", "3"))
        recently_played = self.repo.list_recently_played(rp_count)
        if not recently_played:
            return

        # Insert at the top of listbox (before first ExpanderRow)
        # Header label row
        label = Gtk.Label(label="Recently Played")
        label.set_margin_top(8)
        label.set_margin_bottom(4)
        label.set_margin_start(12)
        label.set_margin_end(8)
        label.set_xalign(0.0)
        header_row = Gtk.ListBoxRow()
        header_row.set_activatable(False)
        header_row.set_selectable(False)
        header_row.set_child(label)
        self.listbox.insert(header_row, 0)
        self._rp_rows.append(header_row)

        # Station rows — insert after header, before ExpanderRows
        for i, st in enumerate(recently_played):
            row = StationRow(st)
            # insert at position i+1 (after header which is at 0)
            self.listbox.insert(row, i + 1)
            self._rp_rows.append(row)

    def _play_by_id(self, station_id: int):
        st = self.repo.get_station(station_id)
        self._play_station(st)

    # ------------------------------------------------------------------ #
    # Playback
    # ------------------------------------------------------------------ #

    def _on_cover_art(self, icy_string: str):
        """Called when a TAG message provides a new ICY title. Fetches cover art."""
        if icy_string == self._last_cover_icy:
            return  # dedup — same title, skip API call
        if is_junk_title(icy_string):
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
        self._current_station = None
        self.stop_btn.set_sensitive(False)

    def _play_row(self, _listbox, row):
        station_id = row.station_id
        st = self.repo.get_station(station_id)
        self._play_station(st)

    def _play_station(self, st: Station):
        self.repo.update_last_played(st.id)
        self._refresh_recently_played()
        self._current_station = st

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

        # Default cover art to station logo until ICY-driven art replaces it
        if st.station_art_path:
            abs_path = os.path.join(DATA_DIR, st.station_art_path)
            if os.path.exists(abs_path):
                try:
                    cover_pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(abs_path, 160, 160, False)
                    self.cover_image.set_from_pixbuf(cover_pb)
                    self.cover_stack.set_visible_child_name("art")
                except Exception:
                    self.cover_stack.set_visible_child_name("fallback")
            else:
                self.cover_stack.set_visible_child_name("fallback")
        else:
            self.cover_stack.set_visible_child_name("fallback")

        # Enable stop button
        self.stop_btn.set_sensitive(True)

        # Start playback -- on_title callback updates title_label and cover art
        def _on_title(title):
            if self._current_station and self._current_station.icy_disabled:
                return  # suppress ICY metadata per user setting
            self.title_label.set_text(title)
            self._on_cover_art(title)  # pass RAW title to cover art (iTunes needs real chars)
        self.player.play(st, on_title=_on_title)

    # ------------------------------------------------------------------ #
    # Station list
    # ------------------------------------------------------------------ #

    def reload_list(self):
        self._rebuild_filter_state()
        self._render_list()

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
        dlg = EditStationDialog(
            self.get_application(),
            self.repo,
            station_id,
            on_saved=self.reload_list,
            is_playing=lambda: (self._current_station is not None
                                and self._current_station.id == station_id),
        )
        dlg.set_transient_for(self)
        dlg.present()
