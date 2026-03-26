# Phase 11 — UI Review

**Audited:** 2026-03-26
**Baseline:** 11-UI-SPEC.md (approved design contract)
**Screenshots:** Not captured (no dev server — GTK4 desktop app)

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 4/4 | All copy matches contract; no generic labels introduced |
| 2. Visuals | 4/4 | Panel rounding, gradient, and art rounding all implemented correctly |
| 3. Color | 4/4 | Semantic tokens only; accent confined to Stop button; no hardcoded hex |
| 4. Typography | 4/4 | No typography changes; Adwaita classes used correctly throughout |
| 5. Spacing | 3/4 | Panel and row spacing matches spec; filter strip uses 4px outside declared scale |
| 6. Experience Design | 3/4 | GStreamer errors printed to stdout only — no in-window error recovery for playback failures |

**Overall: 22/24**

---

## Top 3 Priority Fixes

1. **GStreamer playback errors silently swallowed in UI** — If a stream URL fails after playback starts, `_on_gst_error` prints to stdout (`player.py:40`) but the UI stays in a "playing" state with the Stop button active. The user has no signal that playback has stopped. Fix: connect `_on_gst_error` result to a GLib.idle_add callback that calls `self._stop()` and optionally sets `title_label` to a brief error string like "Stream unavailable".

2. **Filter strip spacing is off-scale** — `filter_box`, `_provider_scroll`, and `_tag_scroll` all use `set_margin_start/end(8)` and `set_margin_top/bottom(4)` (`main_window.py:136-168`). The 4px vertical margin is in the spec as `xs`, but the two ScrolledWindows add a second 4px inside an already 4px-margined container — effectively stacking 8px of whitespace vertically with inconsistent rhythm. These inner scroll margins are redundant; removing `set_margin_top/bottom` from the two ScrolledWindows and keeping only the `filter_box` margins would clean up the stacking.

3. **Edit button in station rows has no accessible label** — `_make_action_row` at `main_window.py:485` creates an icon-only `Gtk.Button` with `document-edit-symbolic` and no `set_tooltip_text` or accessible label. Screen readers and keyboard navigators have no description for the action. Fix: add `edit_btn.set_tooltip_text("Edit station")`.

---

## Detailed Findings

### Pillar 1: Copywriting (4/4)

All copy declared in the UI-SPEC Copywriting Contract is present and matches exactly:

| Declared | Actual | File:Line | Status |
|----------|--------|-----------|--------|
| "No stations match your filters" | Matches | `main_window.py:197` | PASS |
| "Try different search terms or clear your filters." | Matches | `main_window.py:198` | PASS |
| "Clear Filters" | Matches | `main_window.py:199` | PASS |
| "Stop" | Matches | `main_window.py:88` | PASS |
| "Add Station" | Matches | `main_window.py:141` | PASS |
| "Edit" | Matches | `main_window.py:144` | PASS |
| "Clear" | Matches | `main_window.py:173` | PASS |
| "Nothing playing" | Matches | `main_window.py:75` | PASS |

One generic label found in `edit_dialog.py:266` (`"OK"` in an Adw.AlertDialog response) and `edit_dialog.py:97` (`"Save"`). Both are outside Phase 11 scope and pre-existing. No new generic labels introduced by this phase.

### Pillar 2: Visuals (4/4)

All four UI-SPEC requirements implemented correctly:

- **UI-01 Rounded corners:** `border-radius: 12px` on `.now-playing-panel` in `_APP_CSS` (`__main__.py:22`). Matches spec exactly.
- **UI-02 Gradient background:** `linear-gradient(to bottom, shade(@card_bg_color, 1.04), shade(@card_bg_color, 0.97))` — direction, color stops, and shade values all match spec (`__main__.py:16-23`).
- **UI-03 Station row padding:** `.station-list-row { padding-top: 4px; padding-bottom: 4px }` applied to both `StationRow` (`station_row.py:26`) and `_make_action_row` (`main_window.py:467`). Coverage is complete — Recently Played rows and grouped rows both covered.
- **Art rounding (bonus fix):** `.now-playing-art { border-radius: 5px }` applied to `logo_stack` (`main_window.py:65`) and `cover_stack` (`main_window.py:128`). CSS correctly targets the `Gtk.Stack` container, which is the clip boundary.

CSS class applied to the `Gtk.Stack` (not the inner `Gtk.Image`) is the right approach — the Stack owns the background that makes border-radius visible.

Icon-only edit button in station rows lacks a tooltip (see Priority Fix 3).

### Pillar 3: Color (4/4)

No hardcoded hex or RGB values found anywhere in the codebase. All colors use Adwaita semantic tokens:

- `@card_bg_color` — now-playing panel gradient (`__main__.py:19-20`)
- `.suggested-action` — Stop button only (`main_window.py:89`); also Save button in edit dialog (`edit_dialog.py:98`) which is correct usage
- `.destructive-action` — Delete button in edit dialog only (`edit_dialog.py:93`) — appropriate

60/30/10 split is maintained: window background (dominant), card surface on panel (secondary), accent only on primary action buttons (10%).

Registry audit: not applicable (no component registry).

### Pillar 4: Typography (4/4)

This phase made no typography changes, consistent with spec. Existing classes in use:

| Class | Usage | Appropriate |
|-------|-------|-------------|
| `.title-3` | Active station name in panel | Yes — Adwaita heading scale |
| `.dim-label` | Idle state label, station name label | Yes — Adwaita secondary text |
| No custom font-size | Anywhere | Correct — Adwaita-managed |

`Pango.EllipsizeMode.END` applied to both panel labels (`main_window.py:77`, `83`) — prevents overflow in long station names. This is correct overflow handling.

No arbitrary font sizes or weights introduced.

### Pillar 5: Spacing (3/4)

Panel spacing matches spec precisely:

| Widget | Property | Spec | Actual | Status |
|--------|----------|------|--------|--------|
| `panel` | `margin_top` | 16px | 16px | PASS |
| `panel` | `margin_bottom` | 16px | 16px | PASS |
| `panel` | `margin_start` | 24px | 24px | PASS |
| `panel` | `margin_end` | 24px | 24px | PASS |
| `center` | `margin_start` | 12px | 12px | PASS |
| `.station-list-row` | `padding-top/bottom` | +4px | 4px | PASS |

Minor issue (deducting 1): The filter strip stacks redundant 4px margins. `filter_box` has `margin_top/bottom=4` and `margin_start/end=8`, but `_provider_scroll` and `_tag_scroll` each independently add `margin_top/bottom=4` and `margin_start/end=8` on top of that (`main_window.py:154-168`). This doubles vertical padding between the header bar and the chip rows, and creates 16px of horizontal margin (8 + 8) on the chips. Not a spec violation since the filter strip was not covered by Phase 11's spacing prescription, but it is inconsistent with the 4/8/16/24 scale the rest of the UI uses.

`label.set_margin_start(12)` on "Recently Played" header (`main_window.py:384`, `523`) is slightly off — the 12px value sits between `sm` (8px) and `lg` (16px) in the declared scale. Minor; visually acceptable.

### Pillar 6: Experience Design (3/4)

Strong state coverage overall:

- **Empty state:** `Adw.StatusPage` with title, description, and CTA button (`main_window.py:196-202`). Triggered in both `_rebuild_grouped` and `_rebuild_flat`. Full coverage.
- **Disabled state:** Stop button `set_sensitive(False)` on init (`main_window.py:90`) and after stop (`main_window.py:593`), enabled on play (`main_window.py:653`). Correct.
- **Loading indicator:** `Gtk.Spinner` present in edit dialog for art fetch (`edit_dialog.py:197-312`). Appropriate scope.
- **Error handling (image load):** `except Exception` fallback to generic icon on all pixbuf loads (`main_window.py:566`, `630`, `645`). Silently degrades — acceptable for art.

Gap (deducting 1): **GStreamer playback errors are not surfaced to the user.** `_on_gst_error` in `player.py:38-40` parses the error and prints it, but no callback reaches the UI. The window stays in "playing" state indefinitely. There is no "stream unavailable" or equivalent feedback. This is the most impactful UX gap remaining in the codebase.

No confirmation dialog for destructive actions — the Delete button in edit_dialog fires immediately. Pre-existing; outside Phase 11 scope.

---

## Files Audited

- `/home/kcreasey/OneDrive/Projects/MusicStreamer/musicstreamer/__main__.py`
- `/home/kcreasey/OneDrive/Projects/MusicStreamer/musicstreamer/ui/main_window.py`
- `/home/kcreasey/OneDrive/Projects/MusicStreamer/musicstreamer/ui/station_row.py`
- `/home/kcreasey/OneDrive/Projects/MusicStreamer/musicstreamer/ui/edit_dialog.py`
- `/home/kcreasey/OneDrive/Projects/MusicStreamer/musicstreamer/player.py`
- `/home/kcreasey/OneDrive/Projects/MusicStreamer/musicstreamer/cover_art.py`
- `/home/kcreasey/OneDrive/Projects/MusicStreamer/.planning/milestones/v1.2-phases/11-ui-polish/11-UI-SPEC.md`
- `/home/kcreasey/OneDrive/Projects/MusicStreamer/.planning/milestones/v1.2-phases/11-ui-polish/11-01-SUMMARY.md`
