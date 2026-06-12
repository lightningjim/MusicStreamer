"""Spike 001 Stage A — minimal QtWebEngine smoke (kill-test for B1).

The fastest possible proof that the isolated pip-PySide6-Addons env produces a
PyInstaller bundle whose QtWebEngine actually LOADS and RENDERS on Win11 — with
no conda Qt6Core on PATH to shadow it (the Phase 88.3 G6 failure mode).

This is intentionally ~1 file with zero MusicStreamer dependencies so that a
failure here means "WebEngine won't bundle/launch from this env", not "something
in oauth_helper.py is wrong". Stage B then freezes the REAL oauth_helper.

Modes:
  --probe   Headless-ish: load a benign page (about:blank by default, or --url),
            emit load_finished, exit 0 on success / 1 on timeout. Deterministic,
            no human judgement needed — good for Stage A and the Stage C
            isolation run (launch with conda Library\\bin on PATH; it must STILL
            exit 0).
  (default) Interactive: open a visible window so the operator can SEE WebEngine
            rendering a real page. Close button or window-close exits 0.

All diagnostics are JSON-line events on stderr (mirrors oauth_helper._emit_event)
so the operator can copy/paste the stderr block back as spike evidence.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

_T0 = time.time()


def emit(category: str, detail: str = "", **extra) -> None:
    """One JSON object per line on stderr. ISO-ish elapsed-ms timestamp."""
    rec = {
        "t_ms": int((time.time() - _T0) * 1000),
        "category": category,
        "detail": detail,
    }
    rec.update(extra)
    print(json.dumps(rec), file=sys.stderr, flush=True)


# Faithful to oauth_helper.py: advertise Chrome UA from the browser process
# start (set BEFORE any QtWebEngine import / QApplication construction).
_CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
    os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "") + f' --user-agent="{_CHROME_UA}"'
).strip()


def _report_environment() -> None:
    """Decisive isolation evidence: where is THIS process loading Qt from?

    If adjacency won (B1 correct) the bundled QtWebEngineProcess.exe lives next
    to the frozen module under sys._MEIPASS\\PySide6, and PATH (which may carry
    conda's Library\\bin in the Stage C run) is irrelevant. We print both so the
    operator can confirm conda is on PATH yet the bundle still loaded.
    """
    frozen = getattr(sys, "frozen", False)
    meipass = getattr(sys, "_MEIPASS", None)
    emit("frozen", str(frozen), meipass=meipass)

    # Is conda visibly on PATH for this process? (Stage C wants this to be True
    # AND the WebEngine load to still succeed.)
    path_entries = os.environ.get("PATH", "").split(os.pathsep)
    conda_on_path = [p for p in path_entries if "conda" in p.lower() or "library\\bin" in p.lower()]
    emit("path_audit", f"{len(conda_on_path)} conda-ish PATH entries",
         conda_on_path=conda_on_path[:5])

    try:
        import PySide6
        from PySide6.QtCore import QLibraryInfo
        emit("pyside6_loc", os.path.dirname(PySide6.__file__))
        # LibraryExecutablesPath is where QtWebEngineProcess.exe is resolved from.
        emit("qt_exec_path", str(QLibraryInfo.path(QLibraryInfo.LibraryPath.LibraryExecutablesPath)))
        # If frozen, the bundled QtWebEngineProcess.exe should be present.
        if meipass:
            cand = os.path.join(meipass, "PySide6", "QtWebEngineProcess.exe")
            emit("qtwebengineprocess_present", str(os.path.isfile(cand)), path=cand)
            core = os.path.join(meipass, "PySide6", "Qt6WebEngineCore.dll")
            emit("qt6webenginecore_present", str(os.path.isfile(core)), path=core)
    except Exception as exc:  # pragma: no cover - diagnostic only
        emit("env_report_error", repr(exc))


def main() -> int:
    parser = argparse.ArgumentParser(description="Spike 001 WebEngine smoke")
    parser.add_argument("--probe", action="store_true",
                        help="headless-ish auto-close on loadFinished; exit 0/1")
    parser.add_argument("--url", default="about:blank",
                        help="page to load (probe default about:blank; "
                             "interactive default is GBS login)")
    parser.add_argument("--timeout", type=int, default=25,
                        help="probe timeout seconds (default 25)")
    args = parser.parse_args()

    emit("start", "webengine_smoke", argv=sys.argv[1:])

    # The kill-test: does the WebEngine import even resolve in this bundle?
    try:
        from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
    except ImportError as exc:
        emit("webengine_import_failed", repr(exc), severity="blocker")
        # exit 2 mirrors oauth_helper's missing-WebEngine contract.
        return 2
    emit("webengine_import_ok", "PySide6.QtWebEngineWidgets imported")

    from PySide6.QtCore import QTimer, QUrl
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget,
    )

    app = QApplication(sys.argv)
    emit("qapp_created")
    _report_environment()

    url = args.url
    if not args.probe and url == "about:blank":
        # Interactive default: a real login page exercises the actual TLS +
        # Chromium render path the operator wants to SEE working.
        url = "https://accounts.google.com/ServiceLogin"

    win = QMainWindow()
    win.setWindowTitle("Spike 001 — WebEngine smoke (isolated pip bundle)")
    win.resize(900, 700)
    central = QWidget()
    layout = QVBoxLayout(central)
    view = QWebEngineView()
    layout.addWidget(view)
    btn = QPushButton("Close (PASS — I saw the page render)")
    btn.clicked.connect(app.quit)
    layout.addWidget(btn)
    win.setCentralWidget(central)

    result = {"load_ok": None}

    def on_load_finished(ok: bool) -> None:
        result["load_ok"] = ok
        emit("load_finished", f"ok={ok}", url=view.url().toString())
        if args.probe:
            # Deterministic exit: success iff the page reported a clean load.
            app.exit(0 if ok else 3)

    view.loadFinished.connect(on_load_finished)
    emit("load_started", url)
    view.load(QUrl(url))
    win.show()

    if args.probe:
        # Hard timeout guard so the VM run can never hang.
        def on_timeout() -> None:
            emit("probe_timeout", f"no loadFinished in {args.timeout}s",
                 severity="blocker")
            app.exit(1)
        QTimer.singleShot(args.timeout * 1000, on_timeout)

    code = app.exec()
    emit("exit", f"code={code}", load_ok=result["load_ok"])
    return code


if __name__ == "__main__":
    sys.exit(main())
