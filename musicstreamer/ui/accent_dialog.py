import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gdk
from musicstreamer.repo import Repo
from musicstreamer.accent_utils import _is_valid_hex, build_accent_css
from musicstreamer.constants import ACCENT_COLOR_DEFAULT, ACCENT_PRESETS


class AccentDialog(Adw.Window):
    def __init__(self, app, repo: Repo, accent_provider: Gtk.CssProvider, main_window):
        super().__init__(application=app, title="Accent Color")
        self.set_transient_for(main_window)
        self.set_modal(True)
        self.set_default_size(320, -1)

        self.repo = repo
        self.accent_provider = accent_provider
        self._selected_btn = None
        self._swatch_map = {}
        self._current_hex = repo.get_setting("accent_color", ACCENT_COLOR_DEFAULT).lower()

        self._build_ui()

    def _build_ui(self):
        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(16)
        content.set_margin_end(16)

        # Swatch grid
        flow = Gtk.FlowBox()
        flow.set_max_children_per_line(8)
        flow.set_min_children_per_line(4)
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_row_spacing(8)
        flow.set_column_spacing(8)

        for hex_color in ACCENT_PRESETS:
            btn = Gtk.Button()
            btn.set_size_request(40, 40)
            btn.set_halign(Gtk.Align.CENTER)
            btn.set_valign(Gtk.Align.CENTER)

            provider = Gtk.CssProvider()
            provider.load_from_string(
                f"button {{ background: {hex_color}; border-radius: 50%; "
                f"min-width: 40px; min-height: 40px; padding: 0; }}"
            )
            btn.get_style_context().add_provider(
                provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

            self._swatch_map[hex_color] = btn
            btn.connect("clicked", self._on_swatch_clicked, hex_color)

            if hex_color == self._current_hex:
                btn.add_css_class("suggested-action")
                self._selected_btn = btn

            flow.append(btn)

        content.append(flow)

        # Separator
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_margin_top(12)
        sep.set_margin_bottom(12)
        content.append(sep)

        # Hex entry row
        entry_row = Adw.EntryRow(title="Hex color")
        entry_row.set_text(self._current_hex)
        entry_row.connect("notify::text", self._on_text_changed)
        entry_row.connect("entry-activated", self._on_hex_submitted)

        focus_controller = Gtk.EventControllerFocus()
        focus_controller.connect("leave", self._on_hex_focus_out)
        entry_row.add_controller(focus_controller)

        self._hex_entry = entry_row
        content.append(entry_row)

        toolbar_view.set_content(content)
        self.set_content(toolbar_view)

    def _on_swatch_clicked(self, btn, hex_value):
        self._apply_color(hex_value)
        self._hex_entry.set_text(hex_value)

    def _on_hex_submitted(self, entry_row):
        text = entry_row.get_text().strip().lower()
        if not text.startswith("#"):
            text = "#" + text
        if _is_valid_hex(text):
            self._apply_color(text)
        else:
            entry_row.add_css_class("error")

    def _on_hex_focus_out(self, controller):
        entry_row = self._hex_entry
        text = entry_row.get_text().strip().lower()
        if not text.startswith("#"):
            text = "#" + text
        if _is_valid_hex(text):
            self._apply_color(text)
        else:
            entry_row.add_css_class("error")

    def _on_text_changed(self, entry_row, *_):
        entry_row.remove_css_class("error")

    def _apply_color(self, hex_value):
        hex_value = hex_value.lower()
        display = Gdk.Display.get_default()
        Gtk.StyleContext.remove_provider_for_display(display, self.accent_provider)
        self.accent_provider.load_from_string(build_accent_css(hex_value))
        Gtk.StyleContext.add_provider_for_display(
            display, self.accent_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER
        )
        self.repo.set_setting("accent_color", hex_value)
        self._current_hex = hex_value

        if self._selected_btn is not None:
            self._selected_btn.remove_css_class("suggested-action")
            self._selected_btn = None

        if hex_value in self._swatch_map:
            btn = self._swatch_map[hex_value]
            btn.add_css_class("suggested-action")
            self._selected_btn = btn
