# Phase 73: MusicBrainz album-cover lookup — Pattern Map

**Mapped:** 2026-05-13
**Files analyzed:** 13 (4 new + 9 modified)
**Analogs found:** 13 / 13 (all in-tree; zero "no analog")

> Pre-flight clarification: `musicstreamer/migration.py` is a one-shot **file-copy / platformdirs** migration; it is **NOT** where schema migrations live. Schema migrations live in `musicstreamer/repo.py:db_init` (lines 78-112), each as an `ALTER TABLE ... ADD COLUMN` wrapped in a `try / except sqlite3.OperationalError: pass` block. The planner should add the `cover_art_source` column there, NOT in `migration.py`.

## File Classification

| New / Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `musicstreamer/cover_art_mb.py` (NEW) | service / worker | request-response (HTTP GET → callback) | `musicstreamer/cover_art.py` | exact (same shape, different host) |
| `musicstreamer/cover_art.py` (modified) | service / router | request-response | self (existing iTunes worker becomes one of two branches) | exact |
| `musicstreamer/models.py` (modified) | model / dataclass | n/a (data definition) | `Station.icy_disabled` field at `models.py:35` | exact |
| `musicstreamer/repo.py` (modified) | data-access / migration + CRUD | CRUD | `icy_disabled` ALTER + row-mapping at `repo.py:79, 318, 353, 372-383` | exact |
| `musicstreamer/ui_qt/edit_station_dialog.py` (modified) | UI / form widget | request-response (form → repo) | `icy_checkbox` at `edit_station_dialog.py:403, 533, 1382-1400` | exact |
| `musicstreamer/ui_qt/now_playing_panel.py` (modified) | UI / Qt slot | event-driven (Signal/slot) | self — `_fetch_cover_art_async` at `now_playing_panel.py:1176-1212` | exact (widen signature only) |
| `musicstreamer/settings_export.py` (modified) | service / serialization | transform (dataclass ⇄ dict ⇄ ZIP) | `icy_disabled` round-trip at `settings_export.py:114, 502-511` | exact |
| `tests/test_cover_art_mb.py` (NEW) | test / unit | request-response | `tests/test_cover_art.py` (monkeypatch `urlopen`, inline JSON) | exact (same domain, expanded scope) |
| `tests/test_cover_art_routing.py` (NEW) | test / integration | event-driven | `tests/test_now_playing_panel.py::test_icy_disabled_suppresses_itunes_call` lines 561-581 | exact |
| `tests/fixtures/mb_recording_search_*.json` (NEW) | test / fixture | n/a | `tests/fixtures/aa_live/events_*.json` (only existing fixture-dir precedent) | role-match (different domain, same naming idiom) |
| `tests/test_cover_art.py` (extended) | test / unit | request-response | self | exact |
| `tests/test_repo.py` (extended) | test / unit | CRUD | `test_icy_disabled_*` at `test_repo.py:124-154` | exact |
| `tests/test_settings_export.py` (extended) | test / unit | transform | `icy_disabled` round-trip at `test_settings_export.py:176, 363, 384` | exact |
| `tests/test_edit_station_dialog.py` (extended) | test / qtbot | event-driven | `test_icy_checkbox_maps_to_icy_disabled` at `test_edit_station_dialog.py:237-252` | exact |
| `tests/test_now_playing_panel.py` (extended) | test / qtbot | event-driven | `test_icy_disabled_suppresses_itunes_call` at `test_now_playing_panel.py:561-581` | exact |

---

## Pattern Assignments

### `musicstreamer/cover_art_mb.py` (NEW — service/worker)

**Analog:** `musicstreamer/cover_art.py` (the whole file is the worker-shape template). The new module mirrors imports, the bare-`except Exception` failure mode, and the `tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)` write pattern; it **adds** a module-level `_MbGate` (Pattern 1 from RESEARCH §"Persistent worker") and a Lucene-escape helper. `gbs_api.py:77` is the secondary analog for the User-Agent **constant** shape.

**Imports pattern** (copy structure from `cover_art.py:1-6`, add `time` + `importlib.metadata.version`):
```python
"""Cover art fetching via MusicBrainz + Cover Art Archive (D-07..D-20)."""
import json
import logging
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from importlib.metadata import version as _pkg_version
```

**User-Agent constant** (mirrors `gbs_api.py:77` shape **but** must use `importlib.metadata` per D-18 + STATE.md VER-02 — do NOT hardcode `2.1` like gbs_api.py:77 did):
```python
# Source pattern: gbs_api.py:77 (constant) + __main__.py:9 / main_window.py:25, 281 (importlib.metadata.version)
# D-18 locks the exact format; do not paraphrase.
_USER_AGENT = (
    f"MusicStreamer/{_pkg_version('musicstreamer')} "
    f"(https://github.com/lightningjim/MusicStreamer)"
)
```

**Request pattern** (mirrors `gbs_api.py:154` Request-with-headers shape + `cover_art.py:84` timeout):
```python
# Source: gbs_api.py:154 — headers via Request; cover_art.py:84 — timeout=5
req = urllib.request.Request(query_url, headers={"User-Agent": _USER_AGENT})
with urllib.request.urlopen(req, timeout=5) as resp:
    json_bytes = resp.read()
```

**Worker / failure pattern** (mirror `cover_art.py:81-101` exactly, including bare `except Exception` per D-20):
```python
# Source: cover_art.py:81-101 (the canonical worker shape)
def _worker():
    try:
        # MB API call (rate-gated), CAA call (not gated, D-19), tempfile write
        ...
        callback(temp_path)
    except Exception:
        # D-20: never raise out of worker; mirrors cover_art.py:98
        callback(None)

threading.Thread(target=_worker, daemon=True).start()
```

**Tempfile pattern** (verbatim from `cover_art.py:94-96`):
```python
# Source: cover_art.py:94-96 — cross-platform mkstemp idiom verified Phase 999.7
with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
    tmp.write(image_bytes)
    temp_path = tmp.name
```

**`last_itunes_result` write** (genre handoff per D-15; same module global shape as `cover_art.py:37, 87`):
```python
# Source: cover_art.py:37, 87 — the established genre handoff channel.
# Importing the module by name (not `from cover_art import last_itunes_result`)
# is required to write a new dict reference; see cover_art.py:82 for the idiom.
import musicstreamer.cover_art as _cover_art_module
_cover_art_module.last_itunes_result = {"artwork_url": caa_url, "genre": mb_tag}
```

**Rate-gate pattern** (NEW — no in-tree analog for an MB-style gate; closest precedent is the `time.monotonic` cooldown in `player.py` per RESEARCH Pattern 1; planner implements per RESEARCH lines 213-232):
```python
# Source: project pattern (Phase 62 monotonic discipline; see STATE.md Phase 62-03);
# RESEARCH.md §"Pattern 1: Persistent worker with monotonic-floor gate" lines 213-232.
class _MbGate:
    """1-req/sec gate for musicbrainz.org/ws/2/* (D-13, D-14, D-19)."""
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._next_allowed_at = 0.0  # time.monotonic()

    def wait_then_mark(self) -> None:
        with self._lock:
            now = time.monotonic()
            if now < self._next_allowed_at:
                time.sleep(self._next_allowed_at - now)
            self._next_allowed_at = time.monotonic() + 1.0
```

---

### `musicstreamer/cover_art.py` (modified — service/router)

**Analog:** self (lines 67-101 are the existing worker; lines 17-19 are the `is_junk_title` gate that applies to both paths per CONTEXT "Reusable Assets").

**Public-API signature widening** (extend the current `cover_art.py:67` signature with a `source: str = "auto"` keyword to keep iTunes-only callers source-compatible during the rollout):
```python
# Existing signature at cover_art.py:67 — keep callback shape, add source param.
def fetch_cover_art(icy_string: str, callback: callable, source: str = "auto") -> None:
    """Dispatch to iTunes, MB, or both per `source` (D-01..D-04)."""
    if is_junk_title(icy_string):  # cover_art.py:75-77 — same gate, both paths
        callback(None)
        return
    # ... dispatch on source ...
```

**iTunes path: leave intact.** The existing thread-per-call shape at `cover_art.py:101` is fine for iTunes (RESEARCH "Alternatives Considered" line 114: *"keep per-request thread for iTunes to minimize churn"*).

**Auto-mode fallback** (D-02 — iTunes first, then MB on miss): wrap the iTunes worker's `callback(None)` branch so that instead of calling the outer callback, it dispatches to MB. Pattern derived from existing `cover_art.py:89-91` "no artwork_url" branch.

---

### `musicstreamer/models.py` (modified — model/dataclass)

**Analog:** `Station.icy_disabled: bool = False` at `models.py:35`.

**Field-add pattern** (copy the boolean-default-with-comment idiom; widen to `Literal` type for the 3-mode enum):
```python
# Source: models.py:35 (icy_disabled) — same dataclass, same default-value style.
# Phase 73 D-01 / D-05: per-station cover-art routing preference.
from typing import Literal

@dataclass
class Station:
    id: int
    name: str
    # ... existing fields ...
    icy_disabled: bool = False
    cover_art_source: Literal["auto", "itunes_only", "mb_only"] = "auto"  # Phase 73 D-01/D-05
    streams: List[StationStream] = field(default_factory=list)
    last_played_at: Optional[str] = None
    is_favorite: bool = False
```

**Ordering caveat:** Place `cover_art_source` between `icy_disabled` and `streams` (mirrors `icy_disabled`'s slot as a per-station scalar before list fields). Several call-sites use positional args (e.g., `test_edit_station_dialog.py:252` indexes `args[6]` for `icy_disabled`) — adding the new field as a **keyword-default** rather than positional keeps those tests passing.

---

### `musicstreamer/repo.py` (modified — data-access / migration + CRUD)

**Analog:** `icy_disabled` precedent at `repo.py:79-82` (migration), `repo.py:318, 353` (row → dataclass mapping in `list_stations` / `get_station`), `repo.py:372-383` (`update_station` SQL).

**Schema migration** (copy the exact try/except idiom from `repo.py:79-82` — BEFORE the legacy-URL rebuild block at `repo.py:122-179`, per RESEARCH Pitfall 8):
```python
# Source: repo.py:79-82 (icy_disabled), 85-88 (last_played_at), 91-94 (is_favorite).
# RESEARCH Pitfall 8: must appear BEFORE the legacy-URL rebuild (repo.py:122-179)
# so the rebuild's SELECT positional list does not need to know about it.
try:
    con.execute(
        "ALTER TABLE stations ADD COLUMN cover_art_source TEXT NOT NULL DEFAULT 'auto'"
    )
    con.commit()
except sqlite3.OperationalError:
    pass  # column already exists — idempotent on re-run (D-05 backfill via DEFAULT)
```

**Row → dataclass mapping** (extend `list_stations` at `repo.py:298-324`, `get_station` at `repo.py:333-357`, `list_recently_played` at `repo.py:392-419`, `list_favorite_stations` at `repo.py:505-530` — four sites, all the same `Station(...)` constructor block):
```python
# Source: repo.py:318 (icy_disabled mapping) — copy pattern, add new field.
Station(
    id=r["id"],
    name=r["name"],
    # ... existing fields ...
    icy_disabled=bool(r["icy_disabled"]),
    cover_art_source=r["cover_art_source"] or "auto",  # Phase 73 — defensive default
    last_played_at=r["last_played_at"],
    is_favorite=bool(r["is_favorite"]),
    streams=self.list_streams(r["id"]),
)
```

**`update_station` extension** (mirror `repo.py:363-383` — add `cover_art_source` to the SQL UPDATE list and the function signature; preserve positional-arg compatibility by appending as a keyword default like `icy_disabled`):
```python
# Source: repo.py:363-383 — UPDATE SQL + positional + bool/int coercion.
def update_station(
    self,
    station_id: int,
    name: str,
    provider_id: Optional[int],
    tags: str,
    station_art_path: Optional[str],
    album_fallback_path: Optional[str],
    icy_disabled: bool = False,
    cover_art_source: str = "auto",  # Phase 73 — keyword default per D-05
):
    self.con.execute(
        """
        UPDATE stations
        SET name = ?, provider_id = ?, tags = ?,
            station_art_path = ?, album_fallback_path = ?, icy_disabled = ?,
            cover_art_source = ?
        WHERE id = ?
        """,
        (name, provider_id, tags, station_art_path, album_fallback_path,
         int(icy_disabled), cover_art_source, station_id),
    )
    self.con.commit()
```

---

### `musicstreamer/ui_qt/edit_station_dialog.py` (modified — UI / form widget)

**Analog:** `icy_checkbox` at `edit_station_dialog.py:402-404` (widget creation), `edit_station_dialog.py:533` (populate from station), `edit_station_dialog.py:1381-1382, 1400` (read on save).

**Per CONTEXT D-06 + RESEARCH A6:** prefer `QComboBox` (matches `provider_combo` at `edit_station_dialog.py:374-376` — the existing dialog idiom for enum-like fields). `provider_combo` is `setEditable(True)` for free-text providers; the cover-art selector must use the default `setEditable(False)` since the 3 values are fixed.

**Widget creation** (right after the `icy_checkbox` block at `edit_station_dialog.py:402-404`):
```python
# Source: edit_station_dialog.py:374-376 (QComboBox shape) + 402-404 (form.addRow idiom).
# D-06: placement near icy_checkbox is "natural" per CONTEXT.
self.cover_art_source_combo = QComboBox()  # setEditable=False is the default
self.cover_art_source_combo.addItem("Auto (iTunes → MusicBrainz fallback)", "auto")
self.cover_art_source_combo.addItem("iTunes only",                          "itunes_only")
self.cover_art_source_combo.addItem("MusicBrainz only",                     "mb_only")
form.addRow("Cover art source:", self.cover_art_source_combo)
```

**Populate from station** (mirror `edit_station_dialog.py:533`):
```python
# Source: edit_station_dialog.py:533 — set state from Station; same _populate section.
# itemData lookup by Station.cover_art_source value
for idx in range(self.cover_art_source_combo.count()):
    if self.cover_art_source_combo.itemData(idx) == (station.cover_art_source or "auto"):
        self.cover_art_source_combo.setCurrentIndex(idx)
        break
```

**Read on save** (extend the block at `edit_station_dialog.py:1381-1400` — read AND pass to `repo.update_station`):
```python
# Source: edit_station_dialog.py:1382, 1400 — read widget, pass positionally / by keyword.
icy_disabled = self.icy_checkbox.isChecked()
cover_art_source = self.cover_art_source_combo.currentData()  # returns "auto" | "itunes_only" | "mb_only"
# ...
repo.update_station(
    station.id, name, provider_id, tags_csv,
    self._logo_path, station.album_fallback_path,
    icy_disabled,
    cover_art_source=cover_art_source,  # keyword to preserve positional compat
)
```

**Dirty-snapshot inclusion** (extend `_form_snapshot` at `edit_station_dialog.py:585-602` so the Save button enables on cover-art-source changes):
```python
# Source: edit_station_dialog.py:595-602 — snapshot dict for dirty detection.
return {
    "name": self.name_edit.text(),
    "url": self.url_edit.text(),
    "provider": self.provider_combo.currentText(),
    "icy": self.icy_checkbox.isChecked(),
    "cover_art_source": self.cover_art_source_combo.currentData(),  # Phase 73
    "tags": tag_state,
    "streams": tuple(streams_snapshot),
}
```

---

### `musicstreamer/ui_qt/now_playing_panel.py` (modified — UI / Qt slot)

**Analog:** self — `cover_art_ready` Signal at `now_playing_panel.py:227`, queued connect at `:749-751`, `_fetch_cover_art_async` at `:1176-1187`, `_on_cover_art_ready` at `:1189-1202`, on_title_changed integration at `:875-883`.

**Signal stays `Signal(str)`.** Per RESEARCH Open Question 3 line 581-584, do **NOT** widen to `Signal(dict)` for Phase 73 — `last_itunes_result` is already the genre channel and matches existing iTunes flow.

**`_fetch_cover_art_async` widening** (lines 1176-1187 — add source pass-through, no other changes):
```python
# Source: now_playing_panel.py:1176-1187 — keep token-guard logic verbatim; only
# the fetch_cover_art() call widens to pass the station's source preference.
def _fetch_cover_art_async(self, icy_title: str) -> None:
    self._cover_fetch_token += 1
    token = self._cover_fetch_token

    emit = self.cover_art_ready.emit  # bound Signal.emit — no self-capture

    def _cb(path_or_none):
        # Runs on worker thread — emit only, no widget access.
        emit(f"{token}:{path_or_none or ''}")

    # Phase 73 D-01..D-04: route per station preference; default 'auto' for legacy stations.
    source = getattr(self._station, "cover_art_source", "auto") if self._station else "auto"
    fetch_cover_art(icy_title, _cb, source=source)
```

**`_on_cover_art_ready` UNCHANGED** (`now_playing_panel.py:1189-1202`). Same token check, same payload shape `"<token>:<path>"`, same `_show_station_logo_in_cover_slot()` on miss — D-02's "fall through to station-logo placeholder" reuses this miss branch directly.

**`on_title_changed` integration** (`now_playing_panel.py:825-896` — **no signature change needed**; the source is read inside `_fetch_cover_art_async` from `self._station`). Pre-existing guards at `:875-881` (junk + bridge-window + dedup) already short-circuit before `_fetch_cover_art_async` is called.

---

### `musicstreamer/settings_export.py` (modified — service / serialization)

**Analog:** `icy_disabled` round-trip — `settings_export.py:114` (dict export), `settings_export.py:502-511` (dict import / INSERT). RESEARCH Pitfall 9 documents the forward-compat default pattern.

**Export side** (extend `_station_to_dict` at `settings_export.py:108-134`, immediately after `"icy_disabled": station.icy_disabled,` at line 114):
```python
# Source: settings_export.py:114 — same dict-key idiom.
def _station_to_dict(station: Station) -> dict:
    return {
        "name": station.name,
        "provider": station.provider_name or "",
        "tags": station.tags or "",
        "icy_disabled": station.icy_disabled,
        "cover_art_source": station.cover_art_source,  # Phase 73 D-06
        "is_favorite": station.is_favorite,
        # ... rest unchanged ...
    }
```

**Import side — INSERT** (extend `_insert_station` at `settings_export.py:498-533`; mirror the `int(stream.get('bitrate_kbps', 0) or 0)` forward-compat pattern at line 528 — RESEARCH Pitfall 9):
```python
# Source: settings_export.py:502-511 — same INSERT shape, add cover_art_source column.
# Pitfall 9: old ZIPs lack the field; default 'auto' per D-05.
cur = repo.con.execute(
    "INSERT INTO stations"
    "(name, provider_id, tags, icy_disabled, last_played_at, is_favorite, cover_art_source) "
    "VALUES (?,?,?,?,?,?,?)",
    (
        data.get("name", ""),
        provider_id,
        data.get("tags", ""),
        int(bool(data.get("icy_disabled", False))),
        data.get("last_played_at"),
        int(bool(data.get("is_favorite", False))),
        data.get("cover_art_source") or "auto",  # forward-compat default
    ),
)
```

**Import side — REPLACE** (line ~536 onwards, `_replace_station`): apply the same `.get('cover_art_source') or 'auto'` default when updating the matched station.

---

### `tests/test_cover_art_mb.py` (NEW — test / unit)

**Analog:** `tests/test_cover_art.py` (entire file is 55 lines; the inline-JSON + `monkeypatch urlopen` pattern is canonical per RESEARCH "Don't Hand-Roll" line 282).

**Imports + structure** (copy from `test_cover_art.py:1-7`, expand):
```python
# Source: test_cover_art.py:1-7 — unittest + module-under-test imports
"""Unit tests for musicstreamer.cover_art_mb module."""
import json
import unittest
from unittest.mock import MagicMock
```

**User-Agent assertion test** (RESEARCH §"Code Examples" lines 510-523 + Pitfall 6 on header case):
```python
# Source: RESEARCH lines 510-523; Pitfall 6 — req.get_header('User-agent') NOT 'User-Agent'.
def test_mb_request_carries_user_agent(monkeypatch):
    from musicstreamer import cover_art_mb
    captured = {}
    def fake_urlopen(req, timeout=None):
        captured["req"] = req
        resp = MagicMock()
        resp.read.return_value = b'{"recordings": []}'
        resp.__enter__ = lambda s: s
        resp.__exit__ = lambda *a: None
        return resp
    monkeypatch.setattr("musicstreamer.cover_art_mb.urllib.request.urlopen", fake_urlopen)
    cover_art_mb._do_mb_search("Daft Punk", "One More Time")
    ua = captured["req"].get_header("User-agent")  # Pitfall 6
    assert ua.startswith("MusicStreamer/")
    assert "https://github.com/lightningjim/MusicStreamer" in ua
```

**Rate-gate test** (RESEARCH §"Code Examples" lines 527-540 — mock both `monotonic` and `sleep`):
```python
# Source: RESEARCH lines 527-540; pattern verified Phase 62 _BufferUnderrunTracker.
def test_mb_gate_serializes_with_1s_floor(monkeypatch):
    from musicstreamer import cover_art_mb
    fake_now = [0.0]
    sleeps = []
    monkeypatch.setattr(cover_art_mb.time, "monotonic", lambda: fake_now[0])
    monkeypatch.setattr(cover_art_mb.time, "sleep", lambda s: sleeps.append(s))
    gate = cover_art_mb._MbGate()
    gate.wait_then_mark()
    fake_now[0] = 0.3
    gate.wait_then_mark()
    assert sleeps == [pytest.approx(0.7)]
```

**Source-grep gates** (ART-MB-15/16 from RESEARCH lines 640-642 — mirror the memory `feedback_gstreamer_mock_blind_spot.md` lesson):
```python
# Source: RESEARCH lines 640-642 + memory feedback_gstreamer_mock_blind_spot.md.
def test_user_agent_string_literals_present():
    import importlib.resources
    src = importlib.resources.files("musicstreamer").joinpath("cover_art_mb.py").read_text()
    assert "MusicStreamer/" in src
    assert "https://github.com/lightningjim/MusicStreamer" in src

def test_rate_gate_uses_monotonic():
    import importlib.resources
    src = importlib.resources.files("musicstreamer").joinpath("cover_art_mb.py").read_text()
    assert "time.monotonic" in src  # not just a comment claiming rate-limit
```

---

### `tests/test_cover_art_routing.py` (NEW — test / integration)

**Analog:** `tests/test_now_playing_panel.py::test_icy_disabled_suppresses_itunes_call` at `test_now_playing_panel.py:561-581`. Same monkeypatch-on-both-module-and-panel idiom.

**Critical idiom** (line 567-570 — must patch the symbol in BOTH places, because the panel does `from musicstreamer.cover_art import fetch_cover_art`):
```python
# Source: test_now_playing_panel.py:563-570 — double-patch idiom for re-exported symbols.
import musicstreamer.cover_art as cover_art_mod
fetch_spy = MagicMock()
monkeypatch.setattr(cover_art_mod, "fetch_cover_art", fetch_spy)
import musicstreamer.ui_qt.now_playing_panel as npp_mod
monkeypatch.setattr(npp_mod, "fetch_cover_art", fetch_spy)
```

**ART-MB-07 / 08** (MB-only must not call iTunes urlopen; iTunes-only must not call MB urlopen): combine the above double-patch with a separate spy on `cover_art_mb._do_mb_search` (or the module's `urlopen`) to assert call counts.

---

### `tests/fixtures/mb_recording_search_*.json` (NEW — fixtures)

**Analog:** `tests/fixtures/aa_live/events_*.json` (only existing fixture-dir precedent — naming idiom is `<scope>_<variant>.json`).

**Fixture file list** (per RESEARCH lines 651-653):
- `mb_recording_search_clean_album_hit.json` — Official + Album + clean date
- `mb_recording_search_bootleg_only.json` — top-5 are all Bootleg (Pitfall 1: Hey Jude case)
- `mb_recording_search_score_79.json` — must be rejected
- `mb_recording_search_score_85.json` — must be accepted
- `mb_recording_search_no_tags.json` — `recordings[0]` has no `tags` key (Pitfall 3)
- `mb_recording_search_503_body.json` — MB rate-limit response

**Fixture shape** (verbatim from RESEARCH §"Code Examples" lines 354-391 — live-probed JSON shape).

---

### `tests/test_cover_art.py` (extended)

**Analog:** self (lines 8-55). Add ART-MB-07/08 routing tests for the new `source` keyword on `fetch_cover_art`.

**Extension pattern** (copy `test_build_itunes_query_artist_title` at lines 20-24 as the unittest.TestCase shape; new tests should monkeypatch `urlopen` since they assert side-effect-free routing).

---

### `tests/test_repo.py` (extended)

**Analog:** `test_icy_disabled_*` block at `test_repo.py:124-154`.

**Extension pattern** (verbatim shape — copy these four tests, swap `icy_disabled` → `cover_art_source`):
```python
# Source: test_repo.py:124-154 — same four-test shape (default, round-trip, migration, preserve).
def test_cover_art_source_default(repo):
    sid = repo.create_station()
    st = repo.get_station(sid)
    assert st.cover_art_source == "auto"  # D-05

def test_cover_art_source_round_trip(repo):
    sid = repo.create_station()
    repo.update_station(sid, "Radio", None, "", None, None,
                        icy_disabled=False, cover_art_source="mb_only")
    st = repo.get_station(sid)
    assert st.cover_art_source == "mb_only"

def test_cover_art_source_migration_idempotent(repo):
    # Source: test_repo.py:139-143 — second db_init must not raise.
    db_init(repo.con)
    assert len(repo.list_stations()) >= 0
```

---

### `tests/test_settings_export.py` (extended)

**Analog:** `icy_disabled` round-trip assertions at `test_settings_export.py:176, 363, 384, 415`.

**Round-trip assertion pattern** (copy line 176 + 384):
```python
# Source: test_settings_export.py:176 (export side) + :384 (import side).
# Export side — payload field present:
assert "cover_art_source" in groove

# Import side — INSERT applied correctly:
assert s.cover_art_source == "mb_only"  # or "auto" for missing-field forward-compat
```

**Forward-compat test** (per RESEARCH Pitfall 9 — old ZIP missing the field defaults to `"auto"`):
```python
# Source: settings_export.py:528 pattern — `data.get(field) or default`.
payload = _default_payload(stations=[{
    "name": "Legacy", "provider": "X", "tags": "",
    "icy_disabled": False,
    # NOTE: no "cover_art_source" key (simulates pre-Phase-73 ZIP)
    "streams": [{"url": "http://x.example/s", "position": 1}],
}])
# ... commit_import ...
assert stations[0].cover_art_source == "auto"
```

---

### `tests/test_edit_station_dialog.py` (extended)

**Analog:** `test_icy_checkbox_maps_to_icy_disabled` at `test_edit_station_dialog.py:237-252`.

**Extension pattern** (mirror lines 237-252, swap checkbox → combo):
```python
# Source: test_edit_station_dialog.py:237-252 — set widget, emit accepted, read call_args.
def test_cover_art_source_selector_maps_to_update_station(qtbot, dialog, repo, station):
    # Set combo to MB-only via setCurrentIndex (the value in the dialog's combo)
    for idx in range(dialog.cover_art_source_combo.count()):
        if dialog.cover_art_source_combo.itemData(idx) == "mb_only":
            dialog.cover_art_source_combo.setCurrentIndex(idx)
            break
    dialog.button_box.accepted.emit()
    # cover_art_source is keyword arg per Phase 73 patterns
    kwargs = repo.update_station.call_args[1]
    assert kwargs.get("cover_art_source") == "mb_only"
```

**Station fixture update needed:** `test_edit_station_dialog.py:20-30` (the `station` fixture) builds a Station without `cover_art_source` — relies on the dataclass default. No change needed there since `cover_art_source` has a default value.

---

### `tests/test_now_playing_panel.py` (extended)

**Analog:** `test_icy_disabled_suppresses_itunes_call` at `test_now_playing_panel.py:561-581` (whole test is the template).

**ART-MB-09 (auto-mode fallthrough integration test)**: mirror the double-patch idiom and assert the second worker is called when the first returns `None`. The `cover_art_ready` Signal emission can be observed via `qtbot.waitSignal(panel.cover_art_ready, timeout=200)`.

---

## Shared Patterns

### User-Agent literal (D-18) — all MB / CAA HTTP code
**Source:** `gbs_api.py:77` (constant shape) + `__main__.py:9` / `main_window.py:281` (importlib.metadata idiom)
**Apply to:** `cover_art_mb.py` only; cover_art.py iTunes path keeps existing default UA.
**Pattern:** `f"MusicStreamer/{_pkg_version('musicstreamer')} (https://github.com/lightningjim/MusicStreamer)"` — must be a single literal string in source (ART-MB-15 source-grep gate enforces this).

### Worker-thread shape (cross-cutting)
**Source:** `cover_art.py:81-101`
**Apply to:** `cover_art_mb.py`
**Pattern:** Inner `_worker()` function + `threading.Thread(target=..., daemon=True).start()` + bare `except Exception` → `callback(None)`.

### Token-guard at Qt slot (D-13)
**Source:** `now_playing_panel.py:1180-1198`
**Apply to:** ALL cover-art paths (iTunes, MB, Auto) — they all funnel through the same `_on_cover_art_ready` slot. No new wiring required.
**Pattern:** Bound `cover_art_ready.emit` captured outside the closure; emit `f"{token}:{path or ''}"`; the slot at `now_playing_panel.py:1189-1198` discards on token mismatch.

### Idempotent `ALTER TABLE ... ADD COLUMN`
**Source:** `repo.py:79-94` (six existing examples of this idiom)
**Apply to:** `repo.py` schema migration block for `cover_art_source`.
**Pattern:** `try: con.execute("ALTER TABLE ...") + con.commit() / except sqlite3.OperationalError: pass`.

### Forward-compat `data.get(field) or default` for missing ZIP fields
**Source:** `settings_export.py:528` (bitrate_kbps), RESEARCH Pitfall 9
**Apply to:** `settings_export.py` import side for `cover_art_source`.
**Pattern:** `data.get("cover_art_source") or "auto"` — covers both missing key (old ZIP) and explicit `None`.

### Lucene-escape (D-08 + Pitfall 10) — single-pass character iteration
**Source:** RESEARCH lines 421-446 (the escape helper sketch)
**Apply to:** `cover_art_mb.py` only.
**Pattern:** Iterate `s` character-by-character; handle two-char operators (`&&`, `||`) first; never two-pass `.replace()`.

### Bare `except Exception` → `callback(None)` (D-20)
**Source:** `cover_art.py:98-99`
**Apply to:** `cover_art_mb.py` worker.
**Pattern:** Bare `except Exception:` — log via `logging.getLogger(__name__)`, then `callback(None)`.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| — | — | — | — |

All files have at least a role-match analog. The MB rate gate has no exact in-tree analog (closest is the `time.monotonic` cooldown pattern in `player.py` per RESEARCH §"Pattern 1"), but the RESEARCH document provides a verified sketch and Phase 62 STATE.md entries document the project-canonical monotonic-clock discipline.

---

## Metadata

**Analog search scope:**
- `musicstreamer/cover_art.py`, `musicstreamer/models.py`, `musicstreamer/repo.py`, `musicstreamer/migration.py`
- `musicstreamer/ui_qt/edit_station_dialog.py`, `musicstreamer/ui_qt/now_playing_panel.py`
- `musicstreamer/settings_export.py`, `musicstreamer/gbs_api.py`, `musicstreamer/__main__.py`, `musicstreamer/ui_qt/main_window.py`
- `tests/test_cover_art.py`, `tests/test_repo.py`, `tests/test_settings_export.py`
- `tests/test_edit_station_dialog.py`, `tests/test_now_playing_panel.py`
- `tests/fixtures/` (top-level directory listing)

**Files scanned:** 15
**Pattern extraction date:** 2026-05-13
