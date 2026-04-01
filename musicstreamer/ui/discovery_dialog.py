import threading
from urllib.parse import urlparse
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib
from musicstreamer.repo import Repo
from musicstreamer.models import Station
import musicstreamer.radio_browser as radio_browser


class DiscoveryDialog(Adw.Window):
    def __init__(self, app, repo: Repo, main_window):
        super().__init__(application=app, title="Discover Stations")
        self.repo = repo
        self.main_window = main_window
        self.set_default_size(700, 560)
        self.set_transient_for(main_window)
        self.set_modal(True)

        # State
        self._debounce_id = None
        self._cancelled = False
        self._preview_station = None
        self._prior_station = main_window._current_station
        self._saved_urls = set()
        self._current_results = []
        self._country_codes = [""]  # parallel list to country StringList; index 0 = "Any country"

        # Build UI
        root = Adw.ToolbarView()
        header = Adw.HeaderBar()
        root.add_top_bar(header)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)

        # Search row
        search_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        self._search_entry = Gtk.SearchEntry()
        self._search_entry.set_placeholder_text("Search by name\u2026")
        self._search_entry.set_hexpand(True)
        self._search_entry.connect("search-changed", self._on_search_changed)
        search_row.append(self._search_entry)

        # Tag dropdown
        self._tag_model = Gtk.StringList()
        self._tag_model.append("Any genre")
        self._tag_dropdown = Gtk.DropDown(model=self._tag_model)
        self._tag_dropdown.set_width_request(140)
        self._tag_dropdown.connect("notify::selected", self._on_filter_changed)
        search_row.append(self._tag_dropdown)

        # Country dropdown
        self._country_model = Gtk.StringList()
        self._country_model.append("Any country")
        self._country_dropdown = Gtk.DropDown(model=self._country_model)
        self._country_dropdown.set_width_request(140)
        self._country_dropdown.connect("notify::selected", self._on_filter_changed)
        search_row.append(self._country_dropdown)

        content.append(search_row)

        # Stack for result states
        self._stack = Gtk.Stack()
        self._stack.set_vexpand(True)

        # Prompt state
        prompt_page = Adw.StatusPage(
            title="Search for stations",
            description="Type a name above to search Radio-Browser.info",
        )
        self._stack.add_named(prompt_page, "prompt")

        # Loading state
        spinner_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        spinner_box.set_halign(Gtk.Align.CENTER)
        spinner_box.set_valign(Gtk.Align.CENTER)
        spinner = Gtk.Spinner()
        spinner.set_size_request(32, 32)
        spinner.start()
        spinner_box.append(spinner)
        self._stack.add_named(spinner_box, "loading")

        # Results state
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        self._listbox = Gtk.ListBox()
        self._listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        scroll.set_child(self._listbox)
        self._stack.add_named(scroll, "results")

        # Empty state
        empty_page = Adw.StatusPage(
            title="No stations found",
            description="Try different search terms or remove filters.",
        )
        self._stack.add_named(empty_page, "empty")

        # Error state
        error_page = Adw.StatusPage(
            title="Could not reach Radio-Browser",
            description="Check your internet connection and try again.",
        )
        retry_btn = Gtk.Button(label="Retry Search")
        retry_btn.set_halign(Gtk.Align.CENTER)
        retry_btn.connect("clicked", lambda _: self._do_search())
        error_page.set_child(retry_btn)
        self._stack.add_named(error_page, "error")

        self._stack.set_visible_child_name("prompt")
        content.append(self._stack)

        root.set_content(content)
        self.set_content(root)

        self.connect("close-request", self._on_close_request)

        # Populate filter dropdowns in background threads
        threading.Thread(target=self._load_tags, daemon=True).start()
        threading.Thread(target=self._load_countries, daemon=True).start()

    # ------------------------------------------------------------------
    # Filter population
    # ------------------------------------------------------------------

    def _load_tags(self):
        try:
            tags = radio_browser.fetch_tags(200)
            GLib.idle_add(self._on_tags_loaded, tags)
        except Exception:
            pass  # non-fatal — dropdown stays at "Any genre"

    def _on_tags_loaded(self, tags: list[str]):
        if self._cancelled:
            return
        for tag in tags:
            self._tag_model.append(tag)

    def _load_countries(self):
        try:
            countries = radio_browser.fetch_countries()
            GLib.idle_add(self._on_countries_loaded, countries)
        except Exception:
            pass  # non-fatal — dropdown stays at "Any country"

    def _on_countries_loaded(self, countries: list[tuple[str, str]]):
        if self._cancelled:
            return
        for iso, name in countries:
            self._country_model.append(name)
            self._country_codes.append(iso)

    # ------------------------------------------------------------------
    # Search debounce
    # ------------------------------------------------------------------

    def _on_search_changed(self, *_):
        if self._debounce_id is not None:
            GLib.source_remove(self._debounce_id)
        self._debounce_id = GLib.timeout_add(500, self._fire_search)

    def _fire_search(self):
        self._debounce_id = None
        self._do_search()
        return False

    def _on_filter_changed(self, *_):
        self._do_search()

    # ------------------------------------------------------------------
    # Search execution
    # ------------------------------------------------------------------

    def _do_search(self):
        text = self._search_entry.get_text().strip()
        tag_idx = self._tag_dropdown.get_selected()
        country_idx = self._country_dropdown.get_selected()

        # Don't search with nothing specified
        if not text and tag_idx == 0 and country_idx == 0:
            self._stack.set_visible_child_name("prompt")
            return

        self._stack.set_visible_child_name("loading")

        tag = ""
        if tag_idx > 0:
            item = self._tag_model.get_item(tag_idx)
            tag = item.get_string() if item else ""

        countrycode = ""
        if country_idx > 0 and country_idx < len(self._country_codes):
            countrycode = self._country_codes[country_idx]

        def _worker():
            try:
                results = radio_browser.search_stations(text, tag, countrycode)
                GLib.idle_add(self._on_results, results)
            except Exception as e:
                GLib.idle_add(self._on_error, str(e))

        threading.Thread(target=_worker, daemon=True).start()

    # ------------------------------------------------------------------
    # Results handling
    # ------------------------------------------------------------------

    def _on_results(self, results: list[dict]):
        if self._cancelled:
            return

        # Clear existing rows
        while (child := self._listbox.get_first_child()):
            self._listbox.remove(child)

        if not results:
            self._stack.set_visible_child_name("empty")
            return

        for s in results:
            row = Adw.ActionRow()
            row.set_title(s.get("name", ""))
            row.set_subtitle(self._make_subtitle(s))

            prefix = Gtk.Image.new_from_icon_name("audio-x-generic-symbolic")
            prefix.set_pixel_size(32)
            row.add_prefix(prefix)

            suffix_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            suffix_box.set_valign(Gtk.Align.CENTER)

            play_btn = Gtk.Button.new_from_icon_name("media-playback-start-symbolic")
            play_btn.set_tooltip_text("Preview")
            play_btn.set_valign(Gtk.Align.CENTER)
            play_btn.connect("clicked", self._on_preview_clicked, s, play_btn)
            suffix_box.append(play_btn)

            save_btn = Gtk.Button.new_from_icon_name("list-add-symbolic")
            save_btn.set_tooltip_text("Save to library")
            save_btn.add_css_class("suggested-action")
            save_btn.set_valign(Gtk.Align.CENTER)
            save_btn.connect("clicked", self._on_save_clicked, s, save_btn)
            if s.get("url", "") in self._saved_urls:
                save_btn.set_sensitive(False)
                save_btn.set_tooltip_text("Saved")
            suffix_box.append(save_btn)

            row.add_suffix(suffix_box)
            self._listbox.append(row)

        self._stack.set_visible_child_name("results")
        self._current_results = results

    def _on_error(self, err: str):
        if self._cancelled:
            return
        self._stack.set_visible_child_name("error")

    def _make_subtitle(self, s: dict) -> str:
        parts = []
        if s.get("countrycode"):
            parts.append(s["countrycode"])
        if s.get("tags"):
            tag_parts = [t.strip() for t in s["tags"].split(",") if t.strip()]
            if tag_parts:
                parts.append(", ".join(tag_parts[:3]))
        if s.get("bitrate"):
            parts.append(f"{s['bitrate']}kbps")
        return " \u00b7 ".join(parts)

    # ------------------------------------------------------------------
    # Preview playback
    # ------------------------------------------------------------------

    def _on_preview_clicked(self, btn, station_dict: dict, play_btn: Gtk.Button):
        station = Station(
            id=0,
            name=station_dict.get("name", ""),
            url=station_dict.get("url", ""),
            provider_id=None,
            provider_name=self._extract_provider(station_dict),
            tags=station_dict.get("tags", ""),
            station_art_path=None,
            album_fallback_path=None,
            icy_disabled=False,
        )

        # Toggle off if same station
        if self._preview_station and self._preview_station.url == station_dict.get("url", ""):
            self.main_window.player.stop()
            self._preview_station = None
            play_btn.set_icon_name("media-playback-start-symbolic")
            play_btn.set_tooltip_text("Preview")
            return

        # Stop any current preview and reset all play buttons
        self.main_window.player.stop()
        self._reset_play_buttons()

        self._preview_station = station
        self.main_window.player.play(station, on_title=lambda t: None)
        play_btn.set_icon_name("media-playback-stop-symbolic")
        play_btn.set_tooltip_text("Stop preview")

    def _reset_play_buttons(self):
        """Reset all play/stop buttons in the listbox back to play state."""
        child = self._listbox.get_first_child()
        while child is not None:
            if isinstance(child, Adw.ActionRow):
                suffix = None
                # Walk the action row to find the suffix box
                widget = child.get_first_child()
                while widget is not None:
                    if isinstance(widget, Gtk.Box) and widget.get_orientation() == Gtk.Orientation.HORIZONTAL:
                        # Check if this is the suffix box with buttons
                        btn = widget.get_first_child()
                        if isinstance(btn, Gtk.Button):
                            btn.set_icon_name("media-playback-start-symbolic")
                            btn.set_tooltip_text("Preview")
                    widget = widget.get_next_sibling()
            child = child.get_next_sibling()

    # ------------------------------------------------------------------
    # Save to library
    # ------------------------------------------------------------------

    def _on_save_clicked(self, btn, station_dict: dict, save_btn: Gtk.Button):
        url = station_dict.get("url", "")

        if self.repo.station_exists_by_url(url):
            dlg = Adw.MessageDialog(
                transient_for=self,
                heading="Station Already in Library",
                body=f'"{station_dict.get("name", "")}" is already saved. No changes were made.',
            )
            dlg.add_response("ok", "Got It")
            dlg.set_default_response("ok")
            dlg.set_close_response("ok")
            dlg.present()
            return

        provider_name = self._extract_provider(station_dict)
        tags = station_dict.get("tags", "").replace(",", ", ")
        # Normalize multiple spaces in tags
        import re
        tags = re.sub(r",\s*", ", ", tags).strip(", ")

        self.repo.insert_station(station_dict.get("name", ""), url, provider_name, tags)
        self._saved_urls.add(url)
        save_btn.set_sensitive(False)
        save_btn.set_tooltip_text("Saved")
        self.main_window.reload_list()

    # ------------------------------------------------------------------
    # Provider extraction
    # ------------------------------------------------------------------

    def _extract_provider(self, station_dict: dict) -> str:
        network = (station_dict.get("network") or "").strip()
        if network:
            return network
        homepage = (station_dict.get("homepage") or "").strip()
        if homepage:
            domain = urlparse(homepage).netloc
            return domain.replace("www.", "") or ""
        return ""

    # ------------------------------------------------------------------
    # Close handling
    # ------------------------------------------------------------------

    def _on_close_request(self, *_):
        self._cancelled = True
        if self._debounce_id is not None:
            GLib.source_remove(self._debounce_id)
            self._debounce_id = None
        if self._preview_station is not None:
            self.main_window.player.stop()
        if self._prior_station is not None:
            self.main_window._play_station(self._prior_station)
        return False
