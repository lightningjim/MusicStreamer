import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from musicstreamer.repo import Repo


class ManageStreamsDialog(Adw.Window):
    """Sub-dialog for adding, editing, removing, and reordering streams per station."""

    def __init__(self, app, repo: Repo, station_id: int, on_changed=None):
        super().__init__(application=app, title="Manage Streams")
        self.repo = repo
        self.station_id = station_id
        self.on_changed = on_changed

        self._editing_stream_id = None  # None = adding, int = editing

        self.set_default_size(520, 560)
        self.set_modal(True)

        root = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_title_widget(Adw.WindowTitle(title="Streams"))
        root.add_top_bar(header)

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        body.set_margin_top(12)
        body.set_margin_bottom(12)
        body.set_margin_start(12)
        body.set_margin_end(12)

        # Stream list
        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self._list_box.add_css_class("boxed-list")

        list_scroll = Gtk.ScrolledWindow()
        list_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        list_scroll.set_min_content_height(100)
        list_scroll.set_max_content_height(240)
        list_scroll.set_propagate_natural_height(True)
        list_scroll.set_child(self._list_box)
        body.append(list_scroll)

        # Add Stream button
        add_btn = Gtk.Button(label="Add Stream")
        add_btn.set_halign(Gtk.Align.START)
        add_btn.connect("clicked", self._on_add_clicked)
        body.append(add_btn)

        # Edit form (inline at bottom)
        self._form_frame = Gtk.Frame(label="Stream Details")
        form_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        form_box.set_margin_top(8)
        form_box.set_margin_bottom(8)
        form_box.set_margin_start(8)
        form_box.set_margin_end(8)

        # URL entry
        self._url_entry = Gtk.Entry()
        self._url_entry.set_placeholder_text("Stream URL\u2026")
        self._url_entry.set_hexpand(True)
        url_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        url_label = Gtk.Label(label="URL", xalign=0)
        url_label.set_width_chars(10)
        url_row.append(url_label)
        url_row.append(self._url_entry)
        form_box.append(url_row)

        # Label entry
        self._label_entry = Gtk.Entry()
        self._label_entry.set_placeholder_text("Label (optional)\u2026")
        self._label_entry.set_hexpand(True)
        label_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_label = Gtk.Label(label="Label", xalign=0)
        lbl_label.set_width_chars(10)
        label_row.append(lbl_label)
        label_row.append(self._label_entry)
        form_box.append(label_row)

        # Quality dropdown
        quality_options = Gtk.StringList()
        for q in ("", "hi", "med", "low", "custom"):
            quality_options.append(q)
        self._quality_dropdown = Gtk.DropDown(model=quality_options)
        self._quality_dropdown.connect("notify::selected", self._on_quality_changed)

        self._custom_quality_entry = Gtk.Entry()
        self._custom_quality_entry.set_placeholder_text("Custom quality (e.g. 320kbps)\u2026")
        self._custom_quality_entry.set_hexpand(True)
        self._custom_quality_entry.set_visible(False)

        quality_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        quality_label = Gtk.Label(label="Quality", xalign=0)
        quality_label.set_width_chars(10)
        quality_box.append(quality_label)
        quality_box.append(self._quality_dropdown)
        quality_box.append(self._custom_quality_entry)
        form_box.append(quality_box)

        # Stream type dropdown
        type_options = Gtk.StringList()
        for t in ("", "shoutcast", "youtube", "hls"):
            type_options.append(t)
        self._type_dropdown = Gtk.DropDown(model=type_options)

        type_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        type_label = Gtk.Label(label="Type", xalign=0)
        type_label.set_width_chars(10)
        type_row.append(type_label)
        type_row.append(self._type_dropdown)
        form_box.append(type_row)

        # Codec entry
        self._codec_entry = Gtk.Entry()
        self._codec_entry.set_placeholder_text("Codec (MP3, AAC\u2026)")
        self._codec_entry.set_hexpand(True)
        codec_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        codec_label = Gtk.Label(label="Codec", xalign=0)
        codec_label.set_width_chars(10)
        codec_row.append(codec_label)
        codec_row.append(self._codec_entry)
        form_box.append(codec_row)

        # Save / Cancel buttons
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_halign(Gtk.Align.END)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", self._on_form_cancel)

        save_btn = Gtk.Button(label="Save")
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", self._on_form_save)

        btn_row.append(cancel_btn)
        btn_row.append(save_btn)
        form_box.append(btn_row)

        self._form_frame.set_child(form_box)
        self._form_frame.set_visible(False)
        body.append(self._form_frame)

        root.set_content(body)
        self.set_content(root)

        self.connect("close-request", self._on_close_request)
        self._refresh_list()

    # ------------------------------------------------------------------
    # List management
    # ------------------------------------------------------------------

    def _refresh_list(self):
        """Rebuild the stream list from DB."""
        # Remove all existing rows
        while True:
            child = self._list_box.get_first_child()
            if child is None:
                break
            self._list_box.remove(child)

        streams = self.repo.list_streams(self.station_id)

        for idx, stream in enumerate(streams):
            row = self._build_stream_row(stream, idx, len(streams))
            self._list_box.append(row)

    def _build_stream_row(self, stream, idx: int, total: int) -> Adw.ActionRow:
        """Build an ActionRow for a single stream."""
        # Title: label if set, else truncated URL
        if stream.label:
            title = stream.label
        else:
            title = stream.url[:60] + ("…" if len(stream.url) > 60 else "")

        # Subtitle: quality + codec
        parts = []
        if stream.quality:
            parts.append(stream.quality)
        if stream.codec:
            parts.append(stream.codec)
        subtitle = " / ".join(parts) if parts else ""

        row = Adw.ActionRow(title=GLib.markup_escape_text(title))
        if subtitle:
            row.set_subtitle(GLib.markup_escape_text(subtitle))

        # Suffix buttons box
        suffix_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        suffix_box.set_valign(Gtk.Align.CENTER)

        up_btn = Gtk.Button()
        up_btn.set_icon_name("go-up-symbolic")
        up_btn.set_sensitive(idx > 0)
        up_btn.add_css_class("flat")
        up_btn.connect("clicked", self._on_move_up, stream)

        down_btn = Gtk.Button()
        down_btn.set_icon_name("go-down-symbolic")
        down_btn.set_sensitive(idx < total - 1)
        down_btn.add_css_class("flat")
        down_btn.connect("clicked", self._on_move_down, stream)

        edit_btn = Gtk.Button()
        edit_btn.set_icon_name("document-edit-symbolic")
        edit_btn.add_css_class("flat")
        edit_btn.connect("clicked", self._on_edit_stream, stream)

        delete_btn = Gtk.Button()
        delete_btn.set_icon_name("user-trash-symbolic")
        delete_btn.add_css_class("flat")
        delete_btn.add_css_class("destructive-action")
        delete_btn.connect("clicked", self._on_delete_stream, stream)

        suffix_box.append(up_btn)
        suffix_box.append(down_btn)
        suffix_box.append(edit_btn)
        suffix_box.append(delete_btn)

        row.add_suffix(suffix_box)
        return row

    # ------------------------------------------------------------------
    # Reorder
    # ------------------------------------------------------------------

    def _on_move_up(self, _btn, stream):
        streams = self.repo.list_streams(self.station_id)
        ids = [s.id for s in streams]
        idx = ids.index(stream.id)
        if idx > 0:
            ids[idx], ids[idx - 1] = ids[idx - 1], ids[idx]
            self.repo.reorder_streams(self.station_id, ids)
        self._refresh_list()

    def _on_move_down(self, _btn, stream):
        streams = self.repo.list_streams(self.station_id)
        ids = [s.id for s in streams]
        idx = ids.index(stream.id)
        if idx < len(ids) - 1:
            ids[idx], ids[idx + 1] = ids[idx + 1], ids[idx]
            self.repo.reorder_streams(self.station_id, ids)
        self._refresh_list()

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def _on_delete_stream(self, _btn, stream):
        self.repo.delete_stream(stream.id)
        # If we were editing this stream, cancel the form
        if self._editing_stream_id == stream.id:
            self._clear_form()
        self._refresh_list()

    # ------------------------------------------------------------------
    # Edit / Add form
    # ------------------------------------------------------------------

    def _on_add_clicked(self, *_):
        self._editing_stream_id = None
        self._clear_form()
        self._form_frame.set_visible(True)

    def _on_edit_stream(self, _btn, stream):
        self._editing_stream_id = stream.id
        self._url_entry.set_text(stream.url)
        self._label_entry.set_text(stream.label)
        self._set_quality_dropdown(stream.quality)
        self._set_type_dropdown(stream.stream_type)
        self._codec_entry.set_text(stream.codec)
        self._form_frame.set_visible(True)

    def _on_form_cancel(self, *_):
        self._clear_form()
        self._form_frame.set_visible(False)

    def _on_form_save(self, *_):
        url = self._url_entry.get_text().strip()
        if not url:
            return  # URL is required

        label = self._label_entry.get_text().strip()
        quality = self._get_quality_value()
        stream_type = self._get_type_value()
        codec = self._codec_entry.get_text().strip()

        if self._editing_stream_id is None:
            # Insert new stream — position = max existing + 1
            streams = self.repo.list_streams(self.station_id)
            position = max((s.position for s in streams), default=0) + 1
            self.repo.insert_stream(
                self.station_id, url, label=label, quality=quality,
                position=position, stream_type=stream_type, codec=codec,
            )
        else:
            # Update existing
            streams = self.repo.list_streams(self.station_id)
            existing = next((s for s in streams if s.id == self._editing_stream_id), None)
            position = existing.position if existing else 1
            self.repo.update_stream(
                self._editing_stream_id, url, label, quality, position, stream_type, codec
            )

        self._clear_form()
        self._form_frame.set_visible(False)
        self._refresh_list()

        if self.on_changed:
            self.on_changed()

    # ------------------------------------------------------------------
    # Quality helpers
    # ------------------------------------------------------------------

    def _on_quality_changed(self, dropdown, _param):
        idx = dropdown.get_selected()
        item = dropdown.get_model().get_item(idx)
        val = item.get_string() if item else ""
        self._custom_quality_entry.set_visible(val == "custom")

    def _set_quality_dropdown(self, quality: str):
        """Set dropdown to the matching option, or 'custom' for unknown values."""
        model = self._quality_dropdown.get_model()
        preset_map = {"": 0, "hi": 1, "med": 2, "low": 3, "custom": 4}
        if quality in preset_map:
            self._quality_dropdown.set_selected(preset_map[quality])
            self._custom_quality_entry.set_visible(quality == "custom")
            self._custom_quality_entry.set_text("")
        else:
            # Non-preset custom quality
            self._quality_dropdown.set_selected(4)  # "custom"
            self._custom_quality_entry.set_visible(True)
            self._custom_quality_entry.set_text(quality)

    def _get_quality_value(self) -> str:
        idx = self._quality_dropdown.get_selected()
        item = self._quality_dropdown.get_model().get_item(idx)
        val = item.get_string() if item else ""
        if val == "custom":
            return self._custom_quality_entry.get_text().strip()
        return val

    # ------------------------------------------------------------------
    # Stream type helpers
    # ------------------------------------------------------------------

    def _set_type_dropdown(self, stream_type: str):
        type_map = {"": 0, "shoutcast": 1, "youtube": 2, "hls": 3}
        idx = type_map.get(stream_type, 0)
        self._type_dropdown.set_selected(idx)

    def _get_type_value(self) -> str:
        idx = self._type_dropdown.get_selected()
        item = self._type_dropdown.get_model().get_item(idx)
        return item.get_string() if item else ""

    # ------------------------------------------------------------------
    # Form clear
    # ------------------------------------------------------------------

    def _clear_form(self):
        self._editing_stream_id = None
        self._url_entry.set_text("")
        self._label_entry.set_text("")
        self._quality_dropdown.set_selected(0)
        self._custom_quality_entry.set_visible(False)
        self._custom_quality_entry.set_text("")
        self._type_dropdown.set_selected(0)
        self._codec_entry.set_text("")

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------

    def _on_close_request(self, *_):
        if self.on_changed:
            self.on_changed()
        return False
