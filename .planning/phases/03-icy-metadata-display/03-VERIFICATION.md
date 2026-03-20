---
phase: 03-icy-metadata-display
verified: 2026-03-19T00:00:00Z
status: human_needed
score: 13/13 must-haves verified
human_verification:
  - test: "Idle state — launch app, inspect now-playing panel"
    expected: "Panel visible at top with fallback icon left, 'Nothing playing' dim text center, Stop button grayed out, fallback icon right"
    why_human: "Visual layout and CSS dim-label rendering cannot be confirmed programmatically"
  - test: "Play a ShoutCast/AAC station with ICY metadata (e.g. SomaFM)"
    expected: "Station logo appears left, track title updates from ICY TAG in real time, station name shows below title, Stop button active (accent color)"
    why_human: "Real-time ICY TAG bus dispatch requires live stream; visual confirmation of label updates"
  - test: "Stop playback via the Stop button in the panel center"
    expected: "Title resets to 'Nothing playing' (dim style), station name hidden, logo reverts to fallback icon, Stop button grays out"
    why_human: "State transition correctness requires visual inspection; already passed at checkpoint 2026-03-20"
  - test: "Play a YouTube station"
    expected: "Station name shown as track title (on_title called immediately by _play_youtube with fallback_name)"
    why_human: "Requires live YouTube URL and mpv; logic verified in code but runtime behavior needs human"
  - test: "Filter strip layout — confirm Add Station and Edit buttons appear left of provider/tag dropdowns"
    expected: "Add Station, Edit, provider dropdown, tag dropdown, spacer, Clear — left to right"
    why_human: "Visual layout order; already confirmed at checkpoint 2026-03-20"
  - test: "HeaderBar contains only search entry"
    expected: "No Add/Edit/Stop buttons in the HeaderBar; only search box"
    why_human: "Visual inspection; already confirmed at checkpoint 2026-03-20"
---

# Phase 3: ICY Metadata Display Verification Report

**Phase Goal:** The now-playing area reflects what is actually playing — current track title and station identity
**Verified:** 2026-03-19
**Status:** human_needed (all automated checks pass; visual/runtime items need human)
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths — Plan 01 (Player TAG pipeline)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `_on_gst_tag` extracts `Gst.TAG_TITLE` and calls stored on_title callback | VERIFIED | `player.py:38-43` — `taglist.get_string(Gst.TAG_TITLE)` + `GLib.idle_add(self._on_title, title)` |
| 2 | Multiple TAG messages each invoke on_title with the new title value | VERIFIED | `test_on_gst_tag_multiple_updates` passes; code path is stateless per call |
| 3 | `_fix_icy_encoding` corrects latin-1 mojibake back to UTF-8 | VERIFIED | `player.py:8-13` — encode latin-1, decode utf-8, except passthrough |
| 4 | `on_title` callback cleared to None on `stop()` preventing stale updates | VERIFIED | `player.py:58` — `self._on_title = None` first line of `stop()` |
| 5 | TAG messages without `Gst.TAG_TITLE` are silently ignored | VERIFIED | `player.py:39-40` — `if not found: return` |

### Observable Truths — Plan 02 (UI now-playing panel)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 6 | Now-playing panel is visible at the top with three columns | VERIFIED | `main_window.py:38-99` — `Gtk.Box` with logo_stack, center column, cover_placeholder; `shell.add_top_bar(panel)` at line 99 (2nd of 3 top bars) |
| 7 | Station logo appears in left slot when station has art; fallback when not | VERIFIED | `main_window.py:270-282` — `os.path.join(DATA_DIR, st.station_art_path)` → GdkPixbuf pre-scale → `logo_stack.set_visible_child_name("logo"/"fallback")` |
| 8 | Track title label updates when on_title callback fires from TAG bus | VERIFIED | `main_window.py:288` — `on_title=lambda t: self.title_label.set_text(t)` passed to `player.play()` |
| 9 | Station name label appears below track title when playing | VERIFIED | `main_window.py:261-262` — `station_name_label.set_text(st.name)` + `set_visible(True)` in `_play_station` |
| 10 | Stop button is in center column of now-playing panel | VERIFIED | `main_window.py:84-89` — `self.stop_btn` appended to `center` box inside `panel` |
| 11 | Add Station and Edit buttons are in the filter strip | VERIFIED | `main_window.py:108-129` — `add_btn`, `edit_btn` appended to `filter_box` before dropdowns; no `header.pack_start(add_btn/edit_btn)` present |
| 12 | Cover art placeholder right slot shows symbolic icon | VERIFIED | `main_window.py:94-97` — `Gtk.Image.new_from_icon_name("audio-x-generic-symbolic")` at 160x160 |
| 13 | Idle state shows 'Nothing playing' with dim styling, insensitive Stop button | VERIFIED | `main_window.py:71-72,86` — `Gtk.Label(label="Nothing playing")` + `add_css_class("dim-label")` + `stop_btn.set_sensitive(False)` |

**Score:** 13/13 truths verified (automated)

---

## Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `musicstreamer/player.py` | VERIFIED | `_fix_icy_encoding` (line 8), `_on_gst_tag` (line 36), `_on_title` attr (line 30), `message::tag` bus connection (line 28) |
| `tests/test_player_tag.py` | VERIFIED | 10 test functions; all 10 pass; covers encoding, TAG handler, idle_add, callback lifecycle |
| `musicstreamer/ui/main_window.py` | VERIFIED | `logo_stack` (line 56), three-column panel, TAG-driven title callback, logo loading, state transitions |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `player.py` | `GLib.idle_add` | `_on_gst_tag` marshals on_title to main loop | WIRED | `player.py:43` — `GLib.idle_add(self._on_title, title)` |
| `player.py` | `_fix_icy_encoding` | TAG handler applies encoding fix before callback | WIRED | `player.py:41` — `title = _fix_icy_encoding(value)` |
| `main_window.py` | `player.py` | on_title lambda updates title_label via set_text | WIRED | `main_window.py:288` — `on_title=lambda t: self.title_label.set_text(t)` |
| `main_window.py` | `station.station_art_path` | `_play_station` loads logo from art path | WIRED | `main_window.py:270-282` — full path + pixbuf + fallback logic |
| `main_window.py` | `Adw.ToolbarView.add_top_bar` | panel inserted as second top bar | WIRED | `main_window.py:35,99,136` — header, panel, filter_box in order |

---

## Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|----------------|-------------|--------|----------|
| NOW-01 | 03-01, 03-02 | User sees currently playing track title from ICY metadata | SATISFIED | `_on_gst_tag` extracts TAG_TITLE; `on_title` lambda updates `title_label` |
| NOW-02 | 03-01, 03-02 | Track title display updates automatically when ICY metadata changes | SATISFIED | Stateless TAG handler fires on every bus TAG message; no deduplication |
| NOW-03 | 03-01, 03-02 | YouTube streams show station name when no ICY metadata available | SATISFIED | `player.py:75` — `_play_youtube` calls `on_title(fallback_name)` directly; `_play_station` sets `title_label` to `st.name` initially |
| NOW-04 | 03-02 | Station brand logo displayed top-left | SATISFIED | `logo_stack` in left slot; GdkPixbuf pre-scaled to 160x160; fallback to `audio-x-generic-symbolic` |

No orphaned requirements: REQUIREMENTS.md traceability table maps NOW-01 through NOW-04 to Phase 3. All four appear in plan frontmatter. No Phase 3 requirements missing from plans.

---

## Deviations from Plan (Intentional, User-Verified)

| Item | Plan Spec | Actual | Resolution |
|------|-----------|--------|------------|
| Panel height | `set_size_request(-1, 120)` | `set_size_request(-1, 160)` | Auto-fixed during checkpoint: larger size needed for 160px logo |
| Logo widget | `Gtk.Picture` / `logo_picture` / `set_filename` | `Gtk.Image` / `logo_image` / `set_from_pixbuf` | Auto-fixed: GdkPixbuf pre-scale (commit 975fce7) prevents GTK downscale artifacts |
| Plan spec `logo_picture.set_content_fit` | Required | Not present | Superseded by GdkPixbuf approach; not needed with `Gtk.Image.set_from_pixbuf` |

Both deviations were discovered at the human-verify checkpoint and confirmed working by the user (2026-03-20).

---

## Anti-Patterns Found

None. Scanned `musicstreamer/player.py`, `tests/test_player_tag.py`, `musicstreamer/ui/main_window.py` for TODO/FIXME, empty implementations, placeholder returns, and stub handlers. No blockers or warnings found.

The `# Phase 4 will fill` comment at `main_window.py:93` is a forward-reference note, not a placeholder stub — the cover_placeholder widget is fully constructed and visible.

---

## Human Verification Required

These items cannot be confirmed programmatically. Items 3, 5, 6 were confirmed by the user at the Plan 02 visual checkpoint (2026-03-20T03:48:29Z). Items 1, 2, 4 require a live run.

### 1. Idle State Visual Layout

**Test:** Launch the app without playing anything. Inspect the now-playing panel.
**Expected:** Panel visible between HeaderBar and filter strip; left slot shows generic audio icon; center shows "Nothing playing" in muted (dim-label) text with no station name; Stop button present but grayed out; right slot shows generic audio icon.
**Why human:** CSS class rendering and visual layout require display server.

### 2. Real-Time ICY Title Updates

**Test:** Play a ShoutCast or AAC station known to carry ICY metadata (e.g., any SomaFM station).
**Expected:** Track title in center column updates automatically when the track changes, without user interaction.
**Why human:** Requires live stream connection and real GStreamer TAG bus messages.

### 3. Stop State Transition (checkpoint-confirmed)

**Test:** Press Stop button in the panel center column while a station is playing.
**Expected:** Title resets to "Nothing playing" with dim styling; station name hidden; logo reverts to fallback icon; Stop button grays out.
**Why human:** Visual state transition; confirmed at checkpoint 2026-03-20.

### 4. YouTube Station Fallback Title

**Test:** Play a station with a YouTube URL.
**Expected:** Station name appears as track title immediately (not blank); no ICY metadata expected.
**Why human:** Requires mpv + yt-dlp available and a valid YouTube station in the DB.

### 5. Filter Strip Button Order (checkpoint-confirmed)

**Test:** Look at the filter strip below the now-playing panel.
**Expected:** Left-to-right order: Add Station, Edit, provider dropdown, tag dropdown, spacer, Clear button.
**Why human:** Visual order confirmed at checkpoint 2026-03-20.

### 6. HeaderBar Contains Only Search (checkpoint-confirmed)

**Test:** Look at the HeaderBar (topmost bar).
**Expected:** Only the search entry is present. No Add, Edit, or Stop buttons visible in the HeaderBar.
**Why human:** Visual confirmation; confirmed at checkpoint 2026-03-20.

---

## Summary

Phase 3 goal is structurally achieved. All 13 observable truths are verified in the codebase. The TAG pipeline (`_fix_icy_encoding` → `_on_gst_tag` → `GLib.idle_add` → `title_label.set_text`) is fully wired end-to-end. All four requirements (NOW-01 through NOW-04) have implementation evidence. The full 38-test suite passes with no regressions.

Three visual/runtime items (idle layout, live ICY updates, YouTube fallback) need human confirmation for a complete pass. Three additional items were already confirmed at the Phase 02 checkpoint on 2026-03-20.

---

_Verified: 2026-03-19_
_Verifier: Claude (gsd-verifier)_
