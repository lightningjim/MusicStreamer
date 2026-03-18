import sys
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gst", "1.0")
from gi.repository import Adw, Gst

from musicstreamer.constants import APP_ID
from musicstreamer.repo import db_connect, db_init, Repo
from musicstreamer.assets import ensure_dirs
from musicstreamer.ui.main_window import MainWindow

Gst.init(None)  # MUST be here, before any Player instantiation


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)

    def do_activate(self):
        ensure_dirs()  # MUST be first — creates DATA_DIR before db_connect
        con = db_connect()
        db_init(con)
        repo = Repo(con)
        win = MainWindow(self, repo)
        win.present()


if __name__ == "__main__":
    app = App()
    app.run(sys.argv)
