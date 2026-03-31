import sys
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gst", "1.0")
from gi.repository import Adw, Gst, Gtk, Gdk

from musicstreamer.constants import APP_ID
from musicstreamer.repo import db_connect, db_init, Repo
from musicstreamer.assets import ensure_dirs
from musicstreamer.ui.main_window import MainWindow

Gst.init(None)  # MUST be here, before any Player instantiation

_APP_CSS = """
.now-playing-panel {
    background: linear-gradient(
        to bottom,
        shade(@card_bg_color, 1.04),
        shade(@card_bg_color, 0.97)
    );
    border-radius: 12px;
}

.station-list-row {
    padding-top: 4px;
    padding-bottom: 4px;
}

.now-playing-art {
    border-radius: 5px;
    background-color: transparent;
    overflow: hidden;
}

.favorites-list-row {
    padding-top: 4px;
    padding-bottom: 4px;
}
"""


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)

    def do_activate(self):
        ensure_dirs()  # MUST be first — creates DATA_DIR before db_connect
        con = db_connect()
        db_init(con)
        repo = Repo(con)
        win = MainWindow(self, repo)
        css_provider = Gtk.CssProvider()
        css_provider.load_from_string(_APP_CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
        win.present()


def main():
    app = App()
    app.run(sys.argv)


if __name__ == "__main__":
    main()
