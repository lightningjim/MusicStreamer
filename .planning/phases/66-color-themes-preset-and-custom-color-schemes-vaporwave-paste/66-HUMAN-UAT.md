---
status: partial
phase: 66-color-themes-preset-and-custom-color-schemes-vaporwave-paste
source: [66-VERIFICATION.md]
started: 2026-05-09T15:30:00Z
updated: 2026-05-09T15:30:00Z
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
result: [pending]

### 2. Layered Highlight contract preserved end-to-end
expected: Set accent_color via existing "Accent Color" picker to a vivid color (e.g., #ff77ff hot pink). Switch theme to Overrun. Verify selection Highlight stays #ff77ff (your accent override), NOT the Overrun magenta. Reset accent (clear). Verify selection Highlight becomes Overrun's baseline (#ff2dd1). Switch to Vaporwave; Highlight should be Vaporwave's baseline #ff77ff. Switch to Dark or Light without an accent set; Highlight should be neutral blue (#3584e4 ACCENT_COLOR_DEFAULT).
result: [pending]

### 3. Custom theme persistence + Reset behavior
expected: Open Theme picker → click Customize… (with Vaporwave selected). Editor opens with all 9 Vaporwave colors pre-filled. Change Window background to a unique color (e.g., #aabbcc). Live preview should update. Click Save. Editor closes; main app palette stays on the new look; picker (now closed) would mark Custom as active. Quit the app. Relaunch. Custom theme should be active, Window = #aabbcc. Re-open editor (from Custom tile + Customize…). Click Reset. Should revert all 9 colors to the **source preset Vaporwave** values, but selection Highlight stays unchanged (per D-08 invariant).
result: [pending]

### 4. Settings export/import round-trip carries Custom
expected: With Custom theme active and a saved palette, run Export Settings (hamburger menu) to a ZIP. Quit the app. Delete the SQLite settings via `rm ~/.local/share/musicstreamer/musicstreamer.sqlite3`. Relaunch (fresh DB, default theme=system). Run Import Settings, choose the ZIP. After import, Theme picker should show Custom as active with the previously-saved palette intact.
result: [pending]

### 5. WR-01 edge case decision
expected: A code-review warning was raised — picker Cancel after sequence (editor-Save → tile-click preview → Cancel) leaves the displayed palette out of sync with the persisted theme until next mutation or restart. Decide:
- (a) Accept current behavior (the next palette mutation re-syncs; restart re-syncs)
- (b) File a follow-up phase to fix (plan to re-arm `_save_committed`'s baseline after Save)
result: [pending]

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps
