# Phase 66: Color Themes — preset and custom color schemes - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-09
**Phase:** 66-color-themes-preset-and-custom-color-schemes-vaporwave-paste
**Areas discussed:** Theme scope & accent relationship, Preset bundle, Custom theme authoring UX, Picker location & dialog shape, Additional preset (GBS.FM)

---

## Theme scope & accent relationship

(Resumed from checkpoint — original session 2026-05-03.)

**Decisions captured:**

- Theme owns 9 QPalette primary roles (Window, WindowText, Base, AlternateBase, Text, Button, ButtonText, Highlight, HighlightedText, Link). Hardcoded QSS (toast bg, ERROR_COLOR_HEX) NOT touched.
- Theme owns Highlight by default; existing `accent_color` setting (and Phase 59's visual picker) layers on top to override Highlight when non-empty.
- Accent dialog Reset only clears `accent_color` override; theme's Highlight stays in effect.
- Theme overrides `_apply_windows_palette` when a non-default theme is set. When theme = System default, existing Fusion + dark-palette branch runs verbatim.

**Notes:** Phase 59's CONTEXT.md already locks the layering contract — Phase 66 implements the theme half.

---

## Preset bundle

(Resumed from checkpoint — original session 2026-05-03.)

**Decisions captured:**

- Five initial presets locked: System default, Vaporwave, Overrun, Dark, Light. (GBS.FM added in a later area, see below.)
- Vaporwave mood: lavender base + pink/cyan accents (light theme).
- Overrun mood: neon pink/magenta on near-black (dark theme), pairs with Vaporwave.
- Dark/Light: neutral palettes; no Highlight lock — accent_color override drives Highlight, fallback is `ACCENT_COLOR_DEFAULT` blue.

---

## Custom theme authoring UX

| Question | Options Presented | User's Choice |
|----------|-------------------|---------------|
| Edit surface | All 9 roles raw / Reduced 4-color set / All 9 + Highlight | All 9 roles raw |
| Authoring flow | Duplicate-and-edit preset / Blank slate only / Both | Duplicate-and-edit preset |
| Storage | One overwrite slot / Named unbounded list / Fixed N slots | One overwrite slot |
| Portability | None this phase / Copy-as-JSON / Export-to-file | None this phase |
| Live preview | Yes, snapshot-restore on Cancel / Live, no restore / Apply-only-on-Save | Yes, snapshot-restore on Cancel |
| Custom name field | Always 'Custom' / User-editable | Always 'Custom' |
| Save behavior | Save+apply+switch picker / Save without switch | Save + apply + switch picker to Custom |
| Editor Reset | Reset to source preset / Reset to saved Custom / No Reset | Reset to source preset |

**Notes:** All 8 questions resolved with the recommended option. Highlight intentionally absent from the editor because the layered accent_color path owns it.

---

## Picker location & dialog shape

| Question | Options Presented | User's Choice |
|----------|-------------------|---------------|
| Menu home | New 'Theme' above 'Accent Color' / 'Appearance' combined dialog / Submenu | New 'Theme' above 'Accent Color' |
| Picker shape | Tile/swatch grid with preview / Radio list with names / Combobox + Customize | Tile/swatch grid with preview |
| Live preview on click | Yes, snapshot-restore on Cancel / Apply-only-on-OK | Yes, snapshot-restore on Cancel |
| Editor access | 'Customize…' button on picker / Right-click Custom tile / Separate menu entry | 'Customize…' button on picker |
| Tile content | Mini-palette swatch + name + active check / Color blocks only / Name only | Mini-palette swatch + name + active check |
| Empty Custom tile | Visible but disabled with hint / Hidden until exists / Visible-and-enabled-opens-editor | Visible but disabled with hint |
| Persistence | Single 'theme' enum + JSON 'theme_custom' / Per-role flat keys | Single 'theme' enum + JSON 'theme_custom' |
| Startup application order | Theme first then accent override / Custom early-init helper | Theme first then accent override |

**Notes:** All 8 questions resolved with the recommended option.

---

## Additional preset — GBS.FM

| Question | Options Presented | User's Choice |
|----------|-------------------|---------------|
| GBS mood | Dark: deep green base + bright accent / Light: mint base + forest accent / Neutral with green Highlight only | Both 1 and 2 — ship as **GBS.FM** (light) and **GBS.FM After Dark** (dark) |
| Hex source | Propose values, refine in plan-phase / Lock specific hex now | "Use the cookies I have to grab current exact values from gbs.fm" |
| Theme name | 'GBS.FM' / Generic name | 'GBS.FM' (and 'GBS.FM After Dark' for the dark variant) |
| Tile order | After Vaporwave/Overrun before Dark/Light / Last before Custom / First mood theme | After Vaporwave/Overrun, before Dark/Light |
| Lock GBS.FM hex now? | Lock sampled Light, planner tunes Dark / Lock both / Both as proposed (planner refines) | Lock sampled Light mappings; planner tunes 'After Dark' |

**Notes:** During this area, the live `https://gbs.fm/images/style.css` was fetched using the user's cookies at `~/.local/share/musicstreamer/gbs-cookies.txt`. Sampled brand colors (mint `#D8E9D6`, sage `#A1D29D`, lime `#B1D07C`, kelly green `#5AB253`, forest `#448F3F`, lighter mint `#E7F1E6`) were mapped to the 9 QPalette roles and locked in CONTEXT.md D-05. The "After Dark" interpretation uses the same brand greens against a near-black base — proposed mapping captured for planner refinement.

---

## Claude's Discretion

(Captured in CONTEXT.md `<decisions>` "Claude's Discretion" subsection.)

- Vaporwave / Overrun exact hex per role — directional palette locked, planner refines
- GBS.FM After Dark exact hex per role — proposed mapping in D-05, planner refines
- Tile size / grid columns — UI auditor's call
- Editor color-row UX shape (button-opens-modal-QColorDialog vs inline) — recommended button-opens-modal
- Disabled-Custom-tile visual treatment (opacity, border-dash, hint text) — UI auditor's call
- Theme-derived QSS file analogous to `paths.accent_css_path()` — recommended NO
- System default on Linux calling `app.setStyle("Fusion")` — recommended NO
- `migration.run_migration()` step backfilling `theme = 'system'` — recommended NO

## Deferred Ideas

(Captured in CONTEXT.md `<deferred>` section.)

- Multiple named custom themes
- Theme import/export to `.json` file or paste-as-JSON
- Per-widget theme variants
- Hover-preview on tiles
- Theme submenu (inline radio items)
- Editing Highlight from theme editor
- Hardcoded QSS migration into the theme system
- Theme-change keyboard shortcut
- System-default-theme detection on Linux (GTK theme bridge)
- Migration of existing accent_color users
