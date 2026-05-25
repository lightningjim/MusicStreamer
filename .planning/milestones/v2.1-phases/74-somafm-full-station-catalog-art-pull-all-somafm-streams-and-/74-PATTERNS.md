# Phase 74: SomaFM full station catalog + art — Pattern Map

**Mapped:** 2026-05-14
**Files analyzed:** 7 (3 NEW source/test, 2 NEW fixtures, 2 MODIFY)
**Analogs found:** 7 / 7 (all 1:1 exact analogs)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `musicstreamer/soma_import.py` (NEW) | service/importer | request-response + batch + file-I/O | `musicstreamer/aa_import.py` | exact (multi-quality + logo + dedup) |
| `tests/test_soma_import.py` (NEW) | test (unit) | request-response (mocked) | `tests/test_aa_import.py` | exact (`_urlopen_factory` / `_make_http_error`) |
| `tests/test_main_window_soma.py` (NEW) | test (qtbot) | event-driven (QThread signal) | `tests/test_main_window_gbs.py` | exact (`_FakePlayer` / `_FakeRepo` / `_find_action`) |
| `tests/fixtures/soma_channels_3ch.json` (NEW) | fixture (JSON) | data | `tests/fixtures/mb_recording_search_*.json` | partial (same dir convention) |
| `tests/fixtures/soma_channels_with_dedup_hit.json` (NEW) | fixture (JSON) | data | `tests/fixtures/mb_recording_search_*.json` | partial (same dir convention) |
| `musicstreamer/ui_qt/main_window.py` (MODIFY) | controller (Qt) | event-driven | self (`_GbsImportWorker` + `_on_gbs_add_clicked` block, lines 124-150 / 1419-1454 / 205-206) | exact (in-file copy-paste-modify) |
| `musicstreamer/__main__.py` (MODIFY) | config (logger setup) | n/a | self (line 235) | exact (one-line append) |
| `tests/test_constants_drift.py` (MODIFY) | test (source-grep drift guard) | n/a | self + `tests/test_cover_art_mb.py::test_user_agent_string_literals_present` | partial (extend existing) |

## Pattern Assignments

### `musicstreamer/soma_import.py` (NEW — service/importer, request-response + batch)

**Analog:** `musicstreamer/aa_import.py` (290 lines)

**Imports pattern** (`aa_import.py:1-20`):
```python
"""AudioAddict network import backend.

Public API:
  fetch_channels_multi(listen_key) -> list[dict]
  import_stations_multi(channels, repo, on_progress=None, on_logo_progress=None) -> (imported, skipped)
"""

import json
import logging
import os
import re
import tempfile
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from musicstreamer.assets import copy_asset_for_station
from musicstreamer.repo import db_connect, Repo

_log = logging.getLogger(__name__)
```

**SomaFM adaptation:** Drop `re` (no AA-CDN URL templating to strip). Add `from importlib.metadata import version as _pkg_version` for the UA literal (see `cover_art_mb.py:62`).

---

**Module-level tier constants pattern** (`aa_import.py:120-128`):
```python
# IN-02: module-scope constants for AA quality tier metadata
# (were redefined on every network × tier iteration).
_POSITION_MAP = {"hi": 1, "med": 2, "low": 3}
_BITRATE_MAP = {"hi": 320, "med": 128, "low": 64}  # D-10: DI.fm tier -> kbps
# gap-07: ground-truth paid-AA codec mapping (user-verified from AA hardware-player
# settings UI — consistent across all paid AA networks): hi=MP3, med=AAC, low=AAC.
_CODEC_MAP = {"hi": "MP3", "med": "AAC", "low": "AAC"}
```

**SomaFM adaptation (per CONTEXT D-03 LOCKED 4-tier × 5-relay scheme):**
```python
# Phase 74 D-03 LOCKED 2026-05-13: 4 tiers × 5 ICE relays = 20 streams/station.
# Tier→quality mapping (LOCKED by user 2026-05-13):
#   tier 0 (mp3, highest)  -> quality="hi",  codec="MP3", bitrate=128
#   tier 1 (aac, highest)  -> quality="hi2", codec="AAC", bitrate=128
#   tier 2 (aacp, high)    -> quality="med", codec="AAC", bitrate=64
#   tier 3 (aacp, low)     -> quality="low", codec="AAC", bitrate=32
# Position scheme (mirrors aa_import._POSITION_MAP): tier_base * 10 + relay_index
# where tier_base = {hi: 1, hi2: 2, med: 3, low: 4}, relay_index = 1..5.
_TIER_BY_FORMAT_QUALITY = {
    ("mp3",  "highest"): {"quality": "hi",  "tier_base": 1, "codec": "MP3", "bitrate_kbps": 128},
    ("aac",  "highest"): {"quality": "hi2", "tier_base": 2, "codec": "AAC", "bitrate_kbps": 128},
    ("aacp", "high"):    {"quality": "med", "tier_base": 3, "codec": "AAC", "bitrate_kbps": 64},
    ("aacp", "low"):     {"quality": "low", "tier_base": 4, "codec": "AAC", "bitrate_kbps": 32},
}
```

> **Note for planner:** CONTEXT.md D-03 surfaces an Open Question — `hi2` (128 AAC) actually outranks `hi` (128 MP3) under `stream_ordering._CODEC_RANK` (AAC=2 > MP3=1). Optional rename: `hi=AAC-128, med=MP3-128, med2=AAC-64, low=AAC-32`. Planner decides; this PATTERNS.md uses the LOCKED labels verbatim.

---

**PLS resolution helper pattern** (`aa_import.py:23-47`):
```python
def _resolve_pls(pls_url: str) -> list[str]:
    """Fetch a PLS playlist and return ALL stream URLs in file order."""
    try:
        with urllib.request.urlopen(pls_url, timeout=10) as resp:
            content_type = resp.headers.get("Content-Type", "")
            body = resp.read().decode("utf-8", errors="replace")
        from musicstreamer.playlist_parser import parse_playlist
        entries = parse_playlist(body, content_type=content_type, url_hint=pls_url)
        if entries:
            return [e["url"] for e in entries]
    except Exception:  # noqa: BLE001
        pass
    return [pls_url]
```

**SomaFM adaptation:** Mirror verbatim. SomaFM PLS returns 5 File= entries (vs AA's 2). Per D-03 LOCKED, take **all 5** as separate stream rows with relay_index 1..5 — this matches the AA gap-06 "primary + fallback" pattern, just with N=5 instead of N=2.

---

**User-Agent constant pattern** (`cover_art_mb.py:68-83`):
```python
# D-18 (locked): UA literal MUST contain "MusicStreamer/" and the GitHub URL.
# ART-MB-15 source-grep gate asserts both substrings are present in this file.
# VER-02 convention: pull the version via importlib.metadata (auto-bumps via
# phase-complete hook). Do NOT hardcode the version literal like gbs_api.py:77.
try:
    _MS_VERSION = _pkg_version("musicstreamer")
except Exception:
    _MS_VERSION = "0.0.0"
_USER_AGENT = (
    f"MusicStreamer/{_MS_VERSION} "
    f"(https://github.com/lightningjim/MusicStreamer)"
)
```

**SomaFM adaptation:** Lift verbatim. Use `urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})` on all outbound GETs (channels.json + each PLS + each logo). Mirrors `cover_art_mb.py:288` / `gbs_api.py:154`. Source-grep test (#15) requires both `MusicStreamer/` and `https://github.com/lightningjim/MusicStreamer` literals in `soma_import.py`.

---

**Catalog fetch pattern** (`aa_import.py:131-186`):
```python
def fetch_channels_multi(listen_key: str) -> list[dict]:
    """Fetch all channels across all 6 AA networks with hi/med/low quality streams.

    Returns list of dicts:
      {"title": str, "provider": str, "image_url": str|None,
       "streams": [{"url": str, "quality": str, "position": int, "codec": str}]}
    Raises ValueError("invalid_key") on 401/403.
    Raises ValueError("no_channels") when zero channels returned.
    """
    channels_by_net_key = {}

    for net in NETWORKS:
        img_map = _fetch_image_map(net["slug"])
        for quality, tier in QUALITY_TIERS.items():
            url = f"https://{net['domain']}/{tier}?listen_key={listen_key}"
            try:
                with urllib.request.urlopen(url, timeout=15) as resp:
                    data = json.loads(resp.read())
            except urllib.error.HTTPError as e:
                if e.code in (401, 403):
                    raise ValueError("invalid_key")
                continue
            except Exception:
                continue
            # ... build channels_by_net_key dict ...
    results = list(channels_by_net_key.values())
    if not results:
        raise ValueError("no_channels")
    return results
```

**SomaFM adaptation:** Drop the network × tier loop (one HTTPS call). Drop `listen_key`. Drop `_fetch_image_map` (image URL is inline in each channel dict). Drop `invalid_key` branch (public API). Keep `ValueError("no_channels")`. Iterate `data["channels"]` (note SomaFM wraps in `{"channels": [...]}` whereas AA returns a bare list). Per D-15, wrap the per-channel loop in `try/except` and `continue` on per-channel exception with `_log.warning("Skipping SomaFM channel %s: %s", ch.get("id"), exc)` — this is **explicitly missing** from AA's pattern (see Pitfall 2 in RESEARCH.md).

Position computation (mirror `aa_import.py:173-181`):
```python
tier_base = tier_meta["tier_base"]  # 1=hi, 2=hi2, 3=med, 4=low
for relay_index, relay_url in enumerate(_resolve_pls(pls_url), start=1):
    streams.append({
        "url": relay_url,
        "quality": tier_meta["quality"],
        "position": tier_base * 10 + relay_index,
        "codec": tier_meta["codec"],
        "bitrate_kbps": tier_meta["bitrate_kbps"],
    })
```

---

**Importer pattern (dedup-by-URL + atomic per-channel insert)** (`aa_import.py:189-251`):
```python
def import_stations_multi(channels: list[dict], repo, on_progress=None, on_logo_progress=None) -> tuple[int, int]:
    """Import multi-quality AA channels. Creates one station per channel with multiple streams.
    Skips channel if ANY of its stream URLs already exist in library.
    """
    imported = 0
    skipped = 0
    logo_targets = []

    for ch in channels:
        if not ch.get("streams"):
            skipped += 1
            _log.warning("Skipping AA channel with no streams: %s", ch.get("title", "<unnamed>"))
            if on_progress:
                on_progress(imported, skipped)
            continue
        any_exists = any(repo.station_exists_by_url(s["url"]) for s in ch["streams"])
        if any_exists:
            skipped += 1
        else:
            first_url = ch["streams"][0]["url"]
            station_id = repo.insert_station(
                name=ch["title"], url=first_url,
                provider_name=ch["provider"], tags="",
            )
            # insert_station already created a stream for first_url at position=1
            # Update the auto-created stream with quality/codec metadata, then insert remaining
            for s in ch["streams"]:
                if s["url"] == first_url:
                    streams = repo.list_streams(station_id)
                    if streams:
                        repo.update_stream(
                            streams[0].id, s["url"], s.get("label", ""),
                            s["quality"], s["position"],
                            "shoutcast", s.get("codec", ""),
                            bitrate_kbps=s.get("bitrate_kbps", 0),
                        )
                else:
                    repo.insert_stream(
                        station_id, s["url"], label="",
                        quality=s["quality"], position=s["position"],
                        stream_type="shoutcast", codec=s.get("codec", ""),
                        bitrate_kbps=s.get("bitrate_kbps", 0),
                    )
            imported += 1
            image_url = ch.get("image_url")
            if image_url:
                logo_targets.append((station_id, image_url))
        if on_progress:
            on_progress(imported, skipped)
```

**SomaFM adaptation:**
- Function name: `import_stations(channels, repo, on_progress=None) -> tuple[int, int]` — drop `on_logo_progress` (no progress dialog per D-08).
- Provider name: hard-code `provider_name="SomaFM"` per D-02 (CamelCase, no space, no period).
- Per-channel try/except wrap (D-15 — Pitfall 2): wrap each `for ch in channels:` iteration body in `try/except Exception as exc:` → `skipped += 1; _log.warning(...)`. AA does NOT do this; Phase 74 MUST add it.

---

**Logo download pattern (best-effort, ThreadPoolExecutor)** (`aa_import.py:252-288`):
```python
    if logo_targets:
        if on_logo_progress:
            on_logo_progress(0, len(logo_targets))

        def _download_logo(station_id: int, image_url: str) -> None:
            try:
                with urllib.request.urlopen(image_url, timeout=15) as resp:
                    data = resp.read()
                suffix = os.path.splitext(image_url.split("?")[0])[1] or ".png"
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                    tmp.write(data)
                    tmp_path = tmp.name
                try:
                    art_path = copy_asset_for_station(station_id, tmp_path, "station_art")
                    thread_repo = Repo(db_connect())
                    thread_repo.update_station_art(station_id, art_path)
                finally:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
            except Exception:
                pass

        total = len(logo_targets)
        completed = 0
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(_download_logo, sid, url): (sid, url) for sid, url in logo_targets}
            for future in as_completed(futures):
                future.result()
                completed += 1
                if on_logo_progress:
                    on_logo_progress(completed, total)

    return imported, skipped
```

**SomaFM adaptation:** Lift verbatim (it's already the AA pattern Pattern-2 / D-11 mandates). Drop the `on_logo_progress` callback path (no progress bar per D-08). Keep `ThreadPoolExecutor(max_workers=8)` for ~46 logos (~1-2 sec parallel vs ~8 sec sequential — keeps total under D-08's implicit 5-sec UAT threshold).

---

### `tests/test_soma_import.py` (NEW — unit tests with mocked urlopen)

**Analog:** `tests/test_aa_import.py` (687 lines)

**Helper pattern** (`test_aa_import.py:19-34`):
```python
def _urlopen_factory(data: bytes, content_type: str = "audio/x-scpls"):
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=cm)
    cm.__exit__ = MagicMock(return_value=False)
    cm.read = MagicMock(return_value=data)
    # Provide a real headers.get so _resolve_pls can extract Content-Type
    # without receiving a MagicMock string that breaks parse_playlist dispatch.
    headers_mock = MagicMock()
    headers_mock.get = MagicMock(return_value=content_type)
    cm.headers = headers_mock
    return cm


def _make_http_error(code: int):
    return urllib.error.HTTPError(url="http://test", code=code, msg="err", hdrs=None, fp=None)
```

**Lift verbatim** — both helpers apply directly to SomaFM tests.

---

**Mocked urlopen + _resolve_pls patch pattern** (`test_aa_import.py:203-204`):
```python
with patch("musicstreamer.aa_import.urllib.request.urlopen", side_effect=urlopen_side), \
     patch("musicstreamer.aa_import._resolve_pls", side_effect=lambda url: [url]):
    result = fetch_channels_multi("testkey123")
```

**SomaFM adaptation:** Patch `musicstreamer.soma_import.urllib.request.urlopen` and `musicstreamer.soma_import._resolve_pls` (or `_resolve_pls_first` per RESEARCH Pattern 2 — note PATTERNS.md uses `_resolve_pls` matching AA naming verbatim per D-03 LOCKED multi-relay scheme).

---

**Dedup-by-URL skip test pattern** (`test_aa_import.py:299-311`):
```python
def test_import_multi_skips_existing():
    """import_stations_multi skips channel if any stream URL already exists."""
    mock_repo = MagicMock()
    mock_repo.station_exists_by_url.return_value = True

    channels = [{
        "title": "Ambient", "provider": "DI.fm", "image_url": None,
        "streams": [{"url": "http://hi.stream", "quality": "hi", "position": 1, "codec": "AAC"}],
    }]
    imported, skipped = import_stations_multi(channels, mock_repo)
    assert imported == 0
    assert skipped == 1
    mock_repo.insert_station.assert_not_called()
```

**SomaFM adaptation:** Rename to `test_import_skips_when_url_exists` (RESEARCH test #5). Use `provider_name="SomaFM"` to match D-02.

---

**Multi-stream insertion test pattern** (`test_aa_import.py:274-296`):
```python
def test_import_multi_creates_streams():
    """import_stations_multi creates one station with 3 stream rows."""
    mock_repo = MagicMock()
    mock_repo.station_exists_by_url.return_value = False
    mock_repo.insert_station.return_value = 42
    mock_repo.list_streams.return_value = [MagicMock(id=100)]

    channels = [{
        "title": "Ambient", "provider": "DI.fm", "image_url": None,
        "streams": [
            {"url": "http://hi.stream", "quality": "hi", "position": 1, "codec": "AAC"},
            {"url": "http://med.stream", "quality": "med", "position": 2, "codec": "MP3"},
            {"url": "http://low.stream", "quality": "low", "position": 3, "codec": "MP3"},
        ],
    }]
    imported, skipped = import_stations_multi(channels, mock_repo)
    assert imported == 1
    assert skipped == 0
    mock_repo.insert_station.assert_called_once()
    assert mock_repo.insert_stream.call_count == 2  # first was auto-created
```

**SomaFM adaptation:** Expand to 20 streams (4 tiers × 5 relays). Expect `mock_repo.insert_stream.call_count == 19` (one auto-created + 19 explicit inserts). Provider name `"SomaFM"`.

---

**Logo failure non-fatal test pattern** (`test_aa_import.py:385-414`):
```python
def test_import_multi_logo_failure_silent():
    """When logo download fails, station is still imported, no exception, update_station_art not called."""
    mock_repo = MagicMock()
    mock_repo.station_exists_by_url.return_value = False
    mock_repo.insert_station.return_value = 99
    mock_repo.list_streams.return_value = [MagicMock(id=200)]

    channels = [{
        "title": "Ambient", "provider": "DI.fm",
        "image_url": "https://cdn-images.audioaddict.com/abc/file.png",
        "streams": [{"url": "http://hi.stream", "quality": "hi", "position": 11, "codec": "MP3"}],
    }]

    with patch("musicstreamer.aa_import.urllib.request.urlopen", side_effect=Exception("network error")), \
         patch("musicstreamer.aa_import.db_connect"), \
         patch("musicstreamer.aa_import.Repo") as mock_repo_cls:
        mock_thread_repo = MagicMock()
        mock_repo_cls.return_value = mock_thread_repo
        imported, skipped = import_stations_multi(channels, mock_repo)

    assert imported == 1
    assert skipped == 0
    mock_thread_repo.update_station_art.assert_not_called()
```

**SomaFM adaptation:** Lift verbatim with module rename. Validates D-11.

---

**Logo success test pattern** (`test_aa_import.py:336-382`):
```python
def test_import_multi_calls_update_art_on_logo_success():
    """When channel has image_url and download succeeds, update_station_art is called."""
    # ... mocks omitted; png_bytes payload ...
    with patch("musicstreamer.aa_import.urllib.request.urlopen", return_value=mock_resp), \
         patch("musicstreamer.aa_import.copy_asset_for_station", return_value="assets/42/station_art.png"), \
         patch("musicstreamer.aa_import.db_connect"), \
         patch("musicstreamer.aa_import.Repo") as mock_repo_cls:
        mock_thread_repo = MagicMock()
        mock_repo_cls.return_value = mock_thread_repo
        imported, skipped = import_stations_multi(channels, mock_repo, on_logo_progress=...)
    mock_thread_repo.update_station_art.assert_called_once()
```

**SomaFM adaptation:** Lift verbatim with module rename. Drop the `on_logo_progress` arg (Soma doesn't accept it). Per D-13, `cover_art_source` stays at default `"auto"` — no Soma test needs to touch it.

---

**Bitrate threading test pattern** (`test_aa_import.py:441-470`):
```python
def test_import_multi_threads_bitrate_kbps():
    """PB-12: import_stations_multi passes bitrate_kbps kwarg to insert_stream and update_stream."""
    # ... mocks ...
    bitrates_seen = {call.kwargs.get("bitrate_kbps") for call in mock_repo.insert_stream.call_args_list}
    assert bitrates_seen == {128, 64}
```

**SomaFM adaptation:** Expected bitrate set is `{128, 128, 64, 32}` per D-03 (one duplicate 128 across hi/hi2). Use a set + count assertion.

---

**User-Agent source-grep test pattern** (`tests/test_cover_art_mb.py:342-355`):
```python
def test_user_agent_string_literals_present():
    """ART-MB-15: D-18 — source-grep guarantees the literal strings exist."""
    import importlib.resources
    src = importlib.resources.files("musicstreamer").joinpath("cover_art_mb.py").read_text()
    assert "MusicStreamer/" in src, "UA literal 'MusicStreamer/' must appear in source"
    assert "https://github.com/lightningjim/MusicStreamer" in src, (
        "UA contact URL must appear in source verbatim per D-18"
    )
```

**SomaFM adaptation:** Add `test_user_agent_literal_present` in `tests/test_soma_import.py` reading `soma_import.py` instead. Test #14 in the RESEARCH validation matrix; closes the `feedback_gstreamer_mock_blind_spot.md` rule.

Add a parallel `test_no_aacplus_codec_literal` (Test #14a per RESEARCH): assert `"AAC+"` and `"aacp"` do NOT appear as STORED codec field values in the file (the format key `"aacp"` may appear as a dict key — write the assertion against the values dict `_TIER_BY_FORMAT_QUALITY` post-import, not bare string-in-source).

---

### `tests/test_main_window_soma.py` (NEW — qtbot tests)

**Analog:** `tests/test_main_window_gbs.py` (242 lines)

**Fake doubles pattern** (`test_main_window_gbs.py:25-117`):
```python
class _FakePlayer(QObject):
    title_changed = Signal(str)
    failover = Signal(object)
    offline = Signal(str)
    playback_error = Signal(str)
    cookies_cleared = Signal(str)
    elapsed_updated = Signal(int)
    buffer_percent = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.volume: Optional[float] = None

    def set_volume(self, value: float) -> None: ...
    def play(self, station, **kwargs) -> None: ...
    def pause(self) -> None: ...
    def stop(self) -> None: ...
    def restore_eq_from_settings(self, repo) -> None: ...
    def set_eq_enabled(self, enabled: bool) -> None: ...
    def set_eq_profile(self, profile) -> None: ...
    def set_eq_preamp(self, db: float) -> None: ...


class _FakeRepo:
    def __init__(self) -> None:
        self._settings: dict = {}
    def list_stations(self) -> list: return []
    def list_recently_played(self, n: int = 3) -> list: return []
    def get_setting(self, key: str, default=None): return self._settings.get(key, default)
    def set_setting(self, key: str, value) -> None: self._settings[key] = value
    # ... 12 more no-op methods ...
```

**Lift verbatim.** SomaFM workers don't touch the player or session state, so these doubles work as-is.

---

**Helper + fixture pattern** (`test_main_window_gbs.py:123-139`):
```python
@pytest.fixture
def main_window(qtbot):
    """Construct a MainWindow with FakePlayer + FakeRepo doubles."""
    w = MainWindow(_FakePlayer(), _FakeRepo())
    qtbot.addWidget(w)
    return w


def _find_action(window, text: str):
    for action in window._menu.actions():
        if action.text() == text:
            return action
    return None
```

**Lift verbatim.**

---

**Menu-entry-exists test pattern** (`test_main_window_gbs.py:146-150`):
```python
def test_add_gbs_menu_entry_exists(main_window):
    """D-02: 'Add GBS.FM' menu entry is rendered in the hamburger menu."""
    action = _find_action(main_window, "Add GBS.FM")
    assert action is not None, "Expected 'Add GBS.FM' menu entry"
    assert action.isEnabled(), "D-02b: menu entry must always be enabled"
```

**SomaFM adaptation:** Rename `Add GBS.FM` → `Import SomaFM`. Per CONTEXT D-06 verbatim spec.

---

**Worker-start test pattern** (`test_main_window_gbs.py:153-168`):
```python
def test_add_gbs_triggers_worker_start(main_window, monkeypatch):
    """D-02: click should start a _GbsImportWorker."""
    started = {"flag": False}
    real_init = _GbsImportWorker.__init__

    def fake_init(self, parent=None):
        real_init(self, parent=parent)

    def fake_start(self):
        started["flag"] = True

    monkeypatch.setattr(_GbsImportWorker, "__init__", fake_init)
    monkeypatch.setattr(_GbsImportWorker, "start", fake_start)
    main_window._on_gbs_add_clicked()
    assert started["flag"] is True
    assert main_window._gbs_import_worker is not None
```

**SomaFM adaptation:** Rename to `test_import_soma_triggers_worker_start`. Patch `_SomaImportWorker.start`. Assert `main_window._soma_import_worker is not None` post-click (validates SYNC-05 retention, Test #11 in RESEARCH).

---

**Toast assertions test pattern** (`test_main_window_gbs.py:171-227`):
```python
def test_import_finished_toasts_added_on_first_call(main_window, monkeypatch):
    """D-02a: finished(1, 0) -> 'GBS.FM added' toast."""
    captured = {}
    monkeypatch.setattr(main_window, "show_toast",
                        lambda text, *a, **kw: captured.setdefault("text", text))
    monkeypatch.setattr(main_window, "_refresh_station_list", lambda: None)
    main_window._gbs_import_worker = MagicMock()
    main_window._on_gbs_import_finished(1, 0)
    assert captured["text"] == "GBS.FM added"
    assert main_window._gbs_import_worker is None
```

**SomaFM adaptation (CONTEXT D-06 verbatim strings):**
- `_on_soma_import_done(5, 0)` → assert `"SomaFM import: 5 stations added"`
- `_on_soma_import_done(0, 46)` → assert `"SomaFM import: no changes"`
- `_on_soma_import_error("connection refused")` → assert text contains `"SomaFM import failed"` + `"connection refused"`
- `_on_soma_import_error("x" * 100)` → assert `"…"` in text (truncation per Test #12)
- Click handler invokes `show_toast("Importing SomaFM…")` (note U+2026 ellipsis)
- Post-finished and post-error: `main_window._soma_import_worker is None`

---

**QA-05 lambda-ban source-grep test pattern** (`test_main_window_gbs.py:230-242`):
```python
def test_no_self_capturing_lambda_in_gbs_action():
    """QA-05 / Pitfall 10: act_gbs_add must use a bound method, not a lambda."""
    src = open("musicstreamer/ui_qt/main_window.py", encoding="utf-8").read()
    matches = re.findall(r"act_gbs_add\.triggered\.connect\(([^)]+)\)", src)
    assert matches, "Expected act_gbs_add.triggered.connect(...) line"
    for m in matches:
        assert "lambda" not in m, f"QA-05 violation: {m!r}"
        assert m.strip().startswith("self."), \
            f"QA-05 expects bound method starting with 'self.', got: {m!r}"
```

**SomaFM adaptation:** Rename to `test_no_self_capturing_lambda_in_soma_action`. Pattern: `r"act_soma_import\.triggered\.connect\(([^)]+)\)"`. Test #16 in RESEARCH.

---

### `tests/fixtures/soma_channels_3ch.json` + `soma_channels_with_dedup_hit.json` (NEW)

**Analog:** `tests/fixtures/mb_recording_search_clean_album_hit.json` (existing JSON-fixture convention)

**Shape to mirror (verbatim from live probe — RESEARCH §"Operation 1"):**
```json
{
  "channels": [
    {
      "id":           "groovesalad",
      "title":        "Groove Salad",
      "description":  "A nicely chilled plate of ambient/downtempo beats and grooves.",
      "dj":           "Rusty Hodge",
      "genre":        "ambient|electronic",
      "image":        "https://api.somafm.com/img/groovesalad120.png",
      "largeimage":   "https://api.somafm.com/logos/256/groovesalad256.png",
      "xlimage":      "https://api.somafm.com/logos/512/groovesalad512.png",
      "playlists": [
        {"url": "https://api.somafm.com/groovesalad256.pls", "format": "mp3",  "quality": "highest"},
        {"url": "https://api.somafm.com/groovesalad130.pls", "format": "aac",  "quality": "highest"},
        {"url": "https://api.somafm.com/groovesalad64.pls",  "format": "aacp", "quality": "high"},
        {"url": "https://api.somafm.com/groovesalad32.pls",  "format": "aacp", "quality": "low"}
      ],
      "listeners":    "1444",
      "lastPlaying":  "Sine - Take Me Higher"
    },
    ... (2 more channels for 3ch fixture; 1 more channel for dedup_hit fixture)
  ]
}
```

**Adaptation for `soma_channels_3ch.json`:** Three discrete channels with distinct `id` / `title` / 4 playlists each. Used by Tests #1, #2, #6, #8.

**Adaptation for `soma_channels_with_dedup_hit.json`:** One channel whose first resolved stream URL (e.g., `https://ice1.somafm.com/groovesalad-128-mp3`) is configured to match a stub repo's `station_exists_by_url` return. Used by Test #5. Mirror `test_aa_import.py:299-311` skip-existing assertion shape.

---

### `musicstreamer/ui_qt/main_window.py` (MODIFY — controller, event-driven)

**Analog:** Self (`_GbsImportWorker` + `_on_gbs_add_clicked` + `act_gbs_add` — already in the same file). This is a copy-paste-modify of the existing block.

**QThread worker class pattern** (`main_window.py:124-150`):
```python
class _GbsImportWorker(QThread):
    """Phase 60 D-02 / GBS-01a: kick gbs_api.import_station() off the UI thread.

    Mirrors _ExportWorker shape (main_window.py:64-79). Pitfall 3 — emits the
    sentinel string ``"auth_expired"`` via the error signal when the gbs_api
    raises GbsAuthExpiredError so the UI surfaces a re-auth prompt instead
    of the raw exception text.
    """
    finished = Signal(int, int)   # (inserted, updated) per import_station signature
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        try:
            from musicstreamer.repo import Repo
            from musicstreamer import gbs_api
            repo = Repo(db_connect())
            inserted, updated = gbs_api.import_station(repo)
            self.finished.emit(int(inserted), int(updated))
        except Exception as exc:
            from musicstreamer import gbs_api
            if isinstance(exc, gbs_api.GbsAuthExpiredError):
                self.error.emit("auth_expired")
            else:
                self.error.emit(str(exc))
```

**SomaFM adaptation — add right after `_GbsImportWorker` at ~line 151:**
```python
class _SomaImportWorker(QThread):
    """Phase 74 D-07 / SOMA-NN: kick soma_import.import_stations() off the UI thread.

    Mirrors _GbsImportWorker shape (main_window.py:124-150). SYNC-05 retention
    on MainWindow._soma_import_worker prevents mid-run GC (Phase 60 D-02 precedent).
    """
    finished = Signal(int, int)   # (inserted, skipped) per import_stations signature
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        try:
            from musicstreamer.repo import Repo
            from musicstreamer import soma_import
            channels = soma_import.fetch_channels()
            repo = Repo(db_connect())
            inserted, skipped = soma_import.import_stations(channels, repo)
            self.finished.emit(int(inserted), int(skipped))
        except Exception as exc:
            self.error.emit(str(exc))
```

> **Note:** SomaFM has no auth, so no `auth_expired` sentinel branch (per CONTEXT D-14: bare `str(exc)`).

---

**Hamburger menu action wire-up pattern** (`main_window.py:204-206`):
```python
# Phase 60 D-02 / GBS-01a: idempotent multi-quality GBS.FM import
act_gbs_add = self._menu.addAction("Add GBS.FM")
act_gbs_add.triggered.connect(self._on_gbs_add_clicked)  # QA-05 bound method
```

**SomaFM adaptation — insert right after `act_gbs_add` block (~line 207):**
```python
# Phase 74 D-06 / SOMA-NN: SomaFM bulk-catalog import
act_soma_import = self._menu.addAction("Import SomaFM")
act_soma_import.triggered.connect(self._on_soma_import_clicked)  # QA-05 bound method
```

---

**Handler methods pattern** (`main_window.py:1419-1454`):
```python
# ------------------------------------------------------------------
# Phase 60 D-02 / GBS-01a: GBS.FM import handlers
# ------------------------------------------------------------------

def _on_gbs_add_clicked(self) -> None:
    """Phase 60 D-02 / D-02a: kick the GBS.FM import on a worker thread."""
    self.show_toast("Importing GBS.FM…")
    self._gbs_import_worker = _GbsImportWorker(parent=self)  # SYNC-05 retain
    self._gbs_import_worker.finished.connect(self._on_gbs_import_finished)  # QA-05
    self._gbs_import_worker.error.connect(self._on_gbs_import_error)        # QA-05
    self._gbs_import_worker.start()

def _on_gbs_import_finished(self, inserted: int, updated: int) -> None:
    """D-02a: distinct toast for fresh insert vs in-place refresh."""
    if inserted:
        self.show_toast("GBS.FM added")
    elif updated:
        self.show_toast("GBS.FM streams updated")
    else:
        self.show_toast("GBS.FM import: no changes")
    self._refresh_station_list()
    self._gbs_import_worker = None

def _on_gbs_import_error(self, msg: str) -> None:
    """Pitfall 3: auth_expired sentinel → reconnect prompt; else generic."""
    if msg == "auth_expired":
        self.show_toast("GBS.FM session expired — reconnect via Accounts")
    else:
        truncated = (msg[:80] + "…") if len(msg) > 80 else msg
        self.show_toast(f"GBS.FM import failed: {truncated}")
    self._gbs_import_worker = None
```

**SomaFM adaptation — add right after the GBS handler block (~line 1455):**
```python
# ------------------------------------------------------------------
# Phase 74 D-06 / SOMA-NN: SomaFM bulk import handlers
# ------------------------------------------------------------------

def _on_soma_import_clicked(self) -> None:
    """Phase 74 D-06 / D-07: kick the SomaFM bulk import on a worker thread."""
    self.show_toast("Importing SomaFM…")
    self._soma_import_worker = _SomaImportWorker(parent=self)  # SYNC-05 retain
    self._soma_import_worker.finished.connect(self._on_soma_import_done)  # QA-05
    self._soma_import_worker.error.connect(self._on_soma_import_error)    # QA-05
    self._soma_import_worker.start()

def _on_soma_import_done(self, inserted: int, skipped: int) -> None:
    """D-06: 'N stations added' (or 'no changes' when all dedup-skipped)."""
    if inserted:
        self.show_toast(f"SomaFM import: {inserted} stations added")
    else:
        self.show_toast("SomaFM import: no changes")
    self._refresh_station_list()
    self._soma_import_worker = None

def _on_soma_import_error(self, msg: str) -> None:
    """D-14: full abort with truncated message."""
    truncated = (msg[:80] + "…") if len(msg) > 80 else msg
    self.show_toast(f"SomaFM import failed: {truncated}")
    self._soma_import_worker = None
```

> **Note:** SomaFM has no `auth_expired` branch (public API). The `…` truncation literal at 80 chars matches the GBS pattern exactly (Test #12c).

---

### `musicstreamer/__main__.py` (MODIFY — config, single-line append)

**Analog:** Self (line 235 — existing per-logger registration).

**Existing pattern** (`__main__.py:230-235`):
```python
def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING)
    # Phase 62 / BUG-09 / Pitfall 5: per-logger INFO level for musicstreamer.player
    # so buffer-underrun cycle close lines surface to stderr without bumping the
    # GLOBAL level (which would surface chatter from aa_import / gbs_api / mpris2).
    logging.getLogger("musicstreamer.player").setLevel(logging.INFO)
```

> **Note:** RESEARCH/CONTEXT reference "line 234 lists aa_import / gbs_api / mpris2" — that turns out to be the comment text (line 234), not actual `setLevel` calls. The active per-logger registration is only line 235 (`musicstreamer.player`). The other modules use the global `WARNING` level via `logging.basicConfig`.

**SomaFM adaptation — append after line 235 (Test #17):**
```python
logging.getLogger("musicstreamer.soma_import").setLevel(logging.INFO)
```

> **Open question for planner (per D-16 wording vs source reality):** D-16 says "same INFO-level treatment as aa_import, gbs_api, mpris2" — but those modules do NOT currently have `setLevel(INFO)` lines in `__main__.py`. The planner can either (a) interpret D-16 literally and add a single `soma_import` `setLevel` line; OR (b) interpret D-16 holistically and also add the missing `aa_import` / `gbs_api` / `mpris2` lines that the existing comment implies should exist. RESEARCH suggests (a) — be conservative; closing the inconsistency between comment and code is a separate phase. Test #17 source-greps for `musicstreamer.soma_import` literal so it passes either way.

---

### `tests/test_constants_drift.py` (MODIFY — drift guard extension)

**Analog:** Self (Phase 71 / T-40-04 invariant pattern at lines 82-108).

**Existing source-grep invariant pattern** (`test_constants_drift.py:82-108`):
```python
def test_richtext_baseline_unchanged_by_phase_71():
    """T-40-04 / Phase 71 invariant: count of setTextFormat(Qt.RichText)
    across musicstreamer/ must match EXPECTED_RICHTEXT_COUNT (3).
    """
    pkg_root = Path(__file__).parent.parent / "musicstreamer"
    needle = "setTextFormat(Qt.RichText)"
    count = 0
    for py in pkg_root.rglob("*.py"):
        try:
            text = py.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        count += text.count(needle)
    assert count == EXPECTED_RICHTEXT_COUNT, (...)
```

**SomaFM adaptation — Test #17 (logger registration drift):**
```python
def test_soma_import_logger_registered():
    """D-16 / SOMA-NN: __main__.py wires soma_import per-logger INFO level."""
    main_path = Path(__file__).parent.parent / "musicstreamer" / "__main__.py"
    text = main_path.read_text(encoding="utf-8")
    needle = 'logging.getLogger("musicstreamer.soma_import").setLevel(logging.INFO)'
    assert needle in text, (
        "D-16: __main__.py must register musicstreamer.soma_import logger at INFO. "
        f"Looked for literal: {needle!r}"
    )
```

> **Note:** The user-facing test pulled out a `tests/test_requirements_coverage.py` filename, but no such file exists in tree (verified via `ls` at the start of this mapping). Per RESEARCH, the existing drift-guard module is `test_constants_drift.py` (Phase 61's precedent). Planner picks: (a) extend `test_constants_drift.py` (recommended — already establishes the drift-guard pattern); or (b) create `tests/test_soma_requirements_registered.py` (greenfield).

For SOMA-NN requirement-ID registration drift (Test #13 in RESEARCH), mirror the read-then-assert pattern:
```python
def test_soma_nn_requirements_registered():
    """SOMA-NN: REQUIREMENTS.md contains the planner-issued IDs."""
    req_path = Path(__file__).parent.parent / ".planning" / "REQUIREMENTS.md"
    text = req_path.read_text(encoding="utf-8")
    # Planner fills in the actual SOMA-NN list at plan time:
    for req_id in ["SOMA-01", "SOMA-02", ...]:
        assert req_id in text, f"REQUIREMENTS.md must contain {req_id}"
```

---

## Shared Patterns

### Cross-thread DB writes (Phase 60 precedent)

**Source:** `aa_import.py:267`
**Apply to:** `soma_import._download_logo` inner function + `_SomaImportWorker.run` (both already covered by lifting the AA pattern verbatim).

```python
thread_repo = Repo(db_connect())
thread_repo.update_station_art(station_id, art_path)
```

**Rationale:** SQLite forbids cross-thread connection sharing. Each worker / thread constructs its own `Repo(db_connect())`.

### SYNC-05 worker retention (Phase 60 D-02)

**Source:** `main_window.py:1431`, `_on_gbs_add_clicked` pattern.
**Apply to:** `_on_soma_import_clicked`, `_on_soma_import_done`, `_on_soma_import_error`.

```python
# Set on click:
self._soma_import_worker = _SomaImportWorker(parent=self)

# Clear in both done and error slots:
self._soma_import_worker = None
```

**Rationale:** Without the attribute store, the QThread is GC'd as soon as `_on_soma_import_clicked` returns, before `run()` completes. Phase 60 D-02 hit this exact bug; the `parent=self` arg is a belt-and-suspenders Qt parent-child retention.

### QA-05 bound-method connect (no self-capturing lambda)

**Source:** `main_window.py:206`, `:1432-1433`, `tests/test_main_window_gbs.py:230-242`.
**Apply to:** All three SomaFM signal connections:
```python
act_soma_import.triggered.connect(self._on_soma_import_clicked)        # menu action
self._soma_import_worker.finished.connect(self._on_soma_import_done)    # worker signal
self._soma_import_worker.error.connect(self._on_soma_import_error)      # worker signal
```

**Rationale:** Lambdas that capture `self` form a cycle with the lambda's `__closure__` cell. Bound methods don't (`self.method` resolves at call time). Phase 60 closed three QA-05 violations across the GBS handlers; Phase 74 inherits the discipline.

### Source-grep gate for protocol literals (feedback_gstreamer_mock_blind_spot.md)

**Source:** `tests/test_cover_art_mb.py::test_user_agent_string_literals_present` (lines 342-355).
**Apply to:** `tests/test_soma_import.py::test_user_agent_literal_present` (Test #15) AND `tests/test_main_window_soma.py::test_no_self_capturing_lambda_in_soma_action` (Test #16).

**Rationale:** Mocked `urlopen` happily passes ANY UA header value, so behavioral tests can't catch a UA literal regression. Source-grep tests on the .py file are the only way. Same logic for QA-05 lambda ban: the connection is functionally fine at runtime but breaks on Qt re-parenting.

### Per-channel try/except wrap (D-15 — new for Phase 74)

**Source:** **NONE — Phase 74 must ADD this**. The AA equivalent (`aa_import.py:189-251`) does not have per-channel try/except. This is the only place Phase 74 deviates from AA.

**Apply to:** The `for ch in channels:` loop body in `soma_import.import_stations`.

```python
for ch in channels:
    try:
        # ... existing AA pattern: dedup, insert station, insert streams, queue logo ...
        imported += 1
    except Exception as exc:   # D-15: per-channel best-effort
        _log.warning("SomaFM channel %s import skipped: %s", ch.get("id"), exc)
        skipped += 1
    if on_progress:
        on_progress(imported, skipped)
```

**Rationale:** RESEARCH Pitfall 2. Without the inner try/except, one channel with a malformed `playlists` field crashes the entire import. CONTEXT D-15 mandates per-channel best-effort once the catalog fetch succeeds.

## No Analog Found

All files have a strong analog. Phase 74 is, per RESEARCH §"Key insight", a recombination — not a new architectural shape.

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| *(none)* | | | |

## Metadata

**Analog search scope:**
- `musicstreamer/` (29 .py files; primary analog `aa_import.py` is exact)
- `musicstreamer/ui_qt/` (main_window.py is self-analog — same-file copy-paste-modify)
- `tests/` (test_aa_import.py + test_main_window_gbs.py + test_cover_art_mb.py + test_constants_drift.py)
- `tests/fixtures/` (mb_recording_search_*.json — JSON fixture dir convention)

**Files scanned (read into context):**
- `musicstreamer/aa_import.py` (290 lines, full)
- `musicstreamer/__main__.py` (lines 220-259)
- `musicstreamer/ui_qt/main_window.py` (lines 1-90 imports, 120-210 worker + menu, 1410-1467 GBS handlers)
- `musicstreamer/cover_art_mb.py` (lines 60-95 UA constant)
- `musicstreamer/repo.py` (lines 223-260 stream primitives)
- `tests/test_aa_import.py` (lines 1-120 helpers, 195-470 test patterns)
- `tests/test_main_window_gbs.py` (242 lines, full)
- `tests/test_cover_art_mb.py` (lines 340-360 UA source-grep)
- `tests/test_constants_drift.py` (108 lines, full)
- `.planning/REQUIREMENTS.md` (lines 140-162 Coverage block)

**Pattern extraction date:** 2026-05-14

**Project conventions respected:**
- `CLAUDE.md` Skill routing — `Skill("spike-findings-musicstreamer")` not load-bearing for Phase 74 (no GStreamer/PyInstaller/PowerShell work).
- `feedback_gstreamer_mock_blind_spot.md` — applied via Tests #14 + #15 + #16 source-grep gates.
- `feedback_mirror_decisions_cite_source.md` — every "Source:" claim cites a file path + line numbers; no paraphrasing of decisions without source pin.
