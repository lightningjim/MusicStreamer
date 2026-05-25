# Phase 75: Extend theme coloring to include toast colors - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-14
**Phase:** 75-extend-theme-coloring-to-include-toast-colors-phase-66-intro
**Areas discussed:** Color derivation strategy, Severity tiers, Custom theme editor expansion, System-theme toast behavior

---

## Color derivation strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Per-preset hex in THEME_PRESETS | Add 'ToastBg' + 'ToastText' keys to each entry in musicstreamer/theme.py:THEME_PRESETS. Most control, parallels Phase 66 D-05 idiom. | |
| Stock palette roles (ToolTipBase/ToolTipText) | Set Qt's existing ToolTipBase + ToolTipText roles per preset. Toast widget reads palette() instead of hardcoded QSS. Auto-tracks via changeEvent(PaletteChange). | ✓ |
| Algorithmic derivation from Window/Text | Toast computes colors at paint time from existing palette roles (e.g. Window darkened by 60%). No new presets/keys but pastel themes risk washed-out toasts. | |

**User's choice:** Stock palette roles (ToolTipBase/ToolTipText)
**Notes:** Idiomatic Qt approach — ToolTipBase/ToolTipText are exactly the roles Qt designed for floaty notification widgets. Smaller new surface than per-preset hex; auto-tracks via PaletteChange.

### Follow-up: Opacity behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Keep 80% translucent (alpha=220) | Preserve current see-through-ish look. Append alpha=220 when interpolating ToolTipBase into setStyleSheet. No regression. | ✓ |
| Fully opaque | Drop the 220 alpha — toast becomes a flat solid block in ToolTipBase color. | |
| Per-preset alpha | Each preset gets its own opacity — more knobs. | |

**User's choice:** Keep 80% translucent

### Follow-up: Live retint timing

| Option | Description | Selected |
|--------|-------------|----------|
| Instant retint via PaletteChange | Install changeEvent(QEvent.PaletteChange) on ToastOverlay (mirrors now_playing_panel.py:194-197). Free correctness with palette-driven choice. | ✓ |
| Restart required | Toast keeps initial colors until next launch. Simpler implementation but inconsistent with rest of app. | |

**User's choice:** Instant retint via PaletteChange

---

## Severity tiers (info/success/error)

| Option | Description | Selected |
|--------|-------------|----------|
| Single style, just retinted | One ToolTipBase/ToolTipText color per theme. Zero call-site churn (28 show_toast() calls stay as-is). Matches roadmap intent. | ✓ |
| Two tiers: default + error | Add show_toast(text, kind='default'\|'error'). Error toasts use ERROR_COLOR_HEX (#c0392b). ~5 of 28 call sites classify as 'error'. | |
| Three tiers: info / success / error | Full split with kind='info'\|'success'\|'error'. Most call-site churn. Larger Custom-editor surface (3 bg/text pairs). | |

**User's choice:** Single style, just retinted
**Notes:** Roadmap intent is "extend theme coloring to include toast colors" — adding tiers is its own future phase if daily use surfaces a need.

---

## Custom theme editor expansion

| Option | Description | Selected |
|--------|-------------|----------|
| Add 2 rows: ToolTipBase + ToolTipText | Custom editor grows to 11 rows. theme_custom JSON gains 2 keys. Symmetric with how the 7 presets get explicit ToolTipBase/ToolTipText hex. | ✓ |
| Keep 9 rows, auto-derive toast for Custom | Custom uses Window+WindowText (or other derivation). Smaller surface but Custom becomes the only theme where the user can't tune toast directly. | |
| Add 1 unified 'Toast' row | One color picker for toast bg; toast text auto-derived (white if luminance < 0.5 else black). Less control but smaller surface. | |

**User's choice:** Add 2 rows: ToolTipBase + ToolTipText
**Notes:** Editor scroll area already accommodates more rows; minor UI lift only. Maintains symmetry across all 7 presets and Custom.

---

## System-theme toast behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Preserve legacy dark-grey overlay | When theme='system', toast keeps original rgba(40,40,40,220) bg + white text. ToastOverlay branches on active theme: system → hardcoded legacy QSS; everything else → palette-driven. No regression for default-theme users. | ✓ |
| Follow Qt ToolTipBase even for system | Toast always reads palette() regardless of theme. On Linux GNOME, likely produces a pale-yellow tooltip-style toast. Cleanly consistent rule but visible regression vs today's dark overlay. | |
| System gets a synthetic dark overlay matching current look | Set ToolTipBase=#282828 + ToolTipText=#ffffff explicitly for system. Same code path as other themes (always palette-driven), but system-theme colors pinned to today's look. | |

**User's choice:** Preserve legacy dark-grey overlay
**Notes:** Default-theme experience (theme='system' is day-one default and likely most common state on Linux GNOME/Wayland) stays pixel-identical to today. The "theme tracking" kicks in only once user picks a non-system theme.

---

## Claude's Discretion

- **Per-preset toast hex values for the 6 non-system presets.** Constraints: WCAG AA contrast ≥ 4.5:1 between ToolTipText and ToolTipBase; aesthetic cohesion with each preset. Planner samples + locks hex in PLAN.md before execution.
- **Branching mechanism for theme = 'system' (D-10 a vs b).** Recommended: `QApplication.property("theme_name")` (option b) for decoupling. Planner picks based on whether other widgets will need to branch on theme name in the near term.
- **Whether `apply_theme_palette()` should `setProperty("theme_name", theme_name)` on `QApplication`.** Recommended YES (enables D-10 path b cleanly).
- **Whether the empty Custom slot pre-populates `ToolTipBase`/`ToolTipText` from the source preset on first editor-open.** Recommended YES — Phase 66 D-09 already specifies "duplicate-and-edit only" with source-preset pre-fill.
- **Documentation updates** — `theme.py` docstring "9 QPalette primary roles" wording updates to "11 QPalette primary roles". `EDITABLE_ROLES` count comment (if any) updates. Phase 66 D-08 cross-reference updates.

## Deferred Ideas

(See `<deferred>` section in 75-CONTEXT.md for the full list. Highlights:)

- Severity tiers (info/success/error) — own future phase if surfaced.
- Per-call-site toast tinting — own future phase.
- Animated color transition on retint — cosmetic polish.
- `ERROR_COLOR_HEX` / `WARNING_COLOR_HEX` / `STATION_ICON_SIZE` migration into theme system — partial Phase 66 deferred item; remaining halves stay deferred.
- `BrightText` / `Mid` / `Dark` / `Shadow` palette role additions — Phase 66 RESEARCH 1020-1023 candidate; add only if a consumer surfaces visible clash.
- GTK/Adwaita color-scheme dynamic detection on Linux for theme='system' — preserved legacy is intentional.
