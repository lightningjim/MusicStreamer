---
status: resolved
phase: 66-color-themes-preset-and-custom-color-schemes-vaporwave-paste
source: [66-VERIFICATION.md]
started: 2026-05-09T15:30:00Z
updated: 2026-05-09T16:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Visual mood validation per preset
expected: Open the running app on Linux Wayland (DPR=1.0). Open hamburger menu → "Theme". For each of the 8 tiles (System default, Vaporwave, Overrun, GBS.FM, GBS.FM After Dark, Dark, Light, Custom), click the tile and visually confirm:
- Vaporwave reads as light pastel + pink/cyan accents — not muddy or washed out
- Overrun reads as near-black + neon pink/cyan — bright but not eye-strain
- GBS.FM matches the brand sage/mint look from gbs.fm (verifiable side-by-side)
- GBS.FM After Dark uses GBS brand greens against deep background; readable
- Dark / Light look neutral and selection (Highlight) uses your accent_color
- Active tile shows checkmark + 3px Highlight border
- Custom tile is grayed out with "Click Customize…" hint until you save a custom theme
result: pass

### 2. Layered Highlight contract preserved end-to-end
expected: Set accent_color via existing "Accent Color" picker to a vivid color (e.g., #ff77ff hot pink). Switch theme to Overrun. Verify selection Highlight stays #ff77ff (your accent override), NOT the Overrun magenta. Reset accent (clear). Verify selection Highlight becomes Overrun's baseline (#ff2dd1). Switch to Vaporwave; Highlight should be Vaporwave's baseline #ff77ff. Switch to Dark or Light without an accent set; Highlight should be neutral blue (#3584e4 ACCENT_COLOR_DEFAULT).
result: pass

### 3. Custom theme persistence + Reset behavior
expected: Open Theme picker → click Customize… (with Vaporwave selected). Editor opens with all 9 Vaporwave colors pre-filled. Change Window background to a unique color (e.g., #aabbcc). Live preview should update. Click Save. Editor closes; main app palette stays on the new look; picker (now closed) would mark Custom as active. Quit the app. Relaunch. Custom theme should be active, Window = #aabbcc. Re-open editor (from Custom tile + Customize…). Click Reset. Should revert all 9 colors to the **source preset Vaporwave** values, but selection Highlight stays unchanged (per D-08 invariant).
result: pass

### 4. Settings export/import round-trip carries Custom
expected: With Custom theme active and a saved palette, run Export Settings (hamburger menu) to a ZIP. Quit the app. Delete the SQLite settings via `rm ~/.local/share/musicstreamer/musicstreamer.sqlite3`. Relaunch (fresh DB, default theme=system). Run Import Settings, choose the ZIP. After import, Theme picker should show Custom as active with the previously-saved palette intact.
result: pass-with-observation
note: Theme + theme_custom round-trip through the ZIP correctly. **Live re-apply on import requires a restart** — this is pre-existing app behavior matching accent_color (main_window.py:733-758 `_on_import_preview_ready` only connects to `_refresh_station_list`, not to `apply_accent_palette` / `apply_theme_palette`). NOT a Phase 66 regression. Candidate follow-up: add theme + accent live re-apply to the import-complete signal handler.

### 5. WR-01 edge case decision
expected: A code-review warning was raised — picker Cancel after sequence (editor-Save → tile-click preview → Cancel) leaves the displayed palette out of sync with the persisted theme until next mutation or restart. Decide:
- (a) Accept current behavior (the next palette mutation re-syncs; restart re-syncs)
- (b) File a follow-up phase to fix (plan to re-arm `_save_committed`'s baseline after Save)
result: accept-current
note: Edge case is rare and self-corrects on next palette mutation or app restart. No follow-up phase scheduled.

## Summary

total: 5
passed: 5
issues: 0
pending: 0
skipped: 0
blocked: 0
notes: items 4 and 5 passed with observations; 2 pre-existing-pattern gaps logged below as candidate follow-up backlog (G-1 accent Reset UX, G-2 settings-import live re-apply)

## Gaps

(All gaps below are pre-existing app behavior surfaced during Phase 66 UAT — none are Phase 66 regressions. Listed for backlog candidacy.)

### G-1 — Accent dialog Reset → Apply disabled (Phase 59 D-15 UX)
phase: 59 (origin), surfaced 66 UAT
status: observation
detail: Clicking "Reset" in the existing Accent Color dialog (`accent_color_dialog.py:_on_reset` at lines 133-153) immediately writes `accent_color=""` to the repo and sets `_current_hex = ""`. Apply (`_on_apply` at line 116-131) then no-ops because `_current_hex` is empty. Workaround: pick any color then pick default, which re-emits `currentColorChanged` and re-populates `_current_hex`. Reproducible. Phase 59 D-15 explicitly documented this as intended (Reset already saves the empty state). Polish opportunity: disable Apply visually post-Reset, OR auto-close the dialog post-Reset, OR re-arm `_current_hex` to ACCENT_COLOR_DEFAULT after Reset so Apply re-saves the default explicitly.

### G-2 — Settings import does not live-re-apply theme / accent
phase: 19/40 (origin pattern), surfaced 66 UAT
status: observation
detail: `main_window.py:733-758` `_on_import_preview_ready` connects only to `_refresh_station_list` after Settings ZIP import. The new theme + theme_custom keys (Phase 66) and existing accent_color key (Phase 19/40/59) all require a process restart for live effect post-import. SQLite round-trip is correct in all cases; only the live-re-apply is missing. Backlog candidate: add `apply_theme_palette(QApplication.instance(), repo)` + `apply_accent_palette(...)` calls to the post-import signal so the running app re-tints without a restart.
