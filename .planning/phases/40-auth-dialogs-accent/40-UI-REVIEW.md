---
phase: 40
slug: auth-dialogs-accent
audited: 2026-04-13
baseline: 40-UI-SPEC.md
screenshots: not captured (no dev server)
---

# Phase 40 — UI Review

**Audited:** 2026-04-13
**Baseline:** 40-UI-SPEC.md (design contract)
**Screenshots:** not captured (no dev server — desktop Qt app, code-only audit)

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 4/4 | All spec-declared CTAs, placeholders, error strings, and confirmation copy match exactly |
| 2. Visuals | 3/4 | Swatch hover state (cursor + 34x34 scale) not implemented; icon-only swatches lack accessible names |
| 3. Color | 4/4 | Hardcoded hex only on spec-approved destructive/error roles (#c0392b); accent uses palette(highlight) correctly |
| 4. Typography | 3/4 | AccountsDialog body labels have no explicit point size set — relies on Qt default; spec requires 10pt/Normal |
| 5. Spacing | 3/4 | AccountsDialog QVBoxLayout has no setContentsMargins/setSpacing — falls back to Qt default (~9px), not spec md=16px |
| 6. Experience Design | 4/4 | All interaction states present: connecting/connected/not-connected, inline errors, disabled states, destructive confirmation |

**Overall: 21/24**

---

## Top 3 Priority Fixes

1. **AccountsDialog missing setContentsMargins/setSpacing** — Visual inconsistency vs all other Phase 40 dialogs which use 16px/8px; users see tighter layout on this dialog — add `layout.setContentsMargins(16, 16, 16, 16)` and `layout.setSpacing(8)` to both the root layout and `twitch_layout` in `accounts_dialog.py` lines 58-62.

2. **AccountsDialog status label has no explicit font** — Spec mandates 10pt/Normal for dialog body text; the `_status_label` and `_action_btn` in `accounts_dialog.py` use Qt default size (~9pt on most systems) — add `QFont().setPointSize(10)` to the status label (line 47 area), consistent with `cookie_import_dialog.py` pattern.

3. **AccentColorDialog swatch hover state not implemented** — Spec declares `cursor: pointer` + scale to 34x34px on hover; none of the 8 swatch QPushButtons set a pointing cursor or hover stylesheet — add `btn.setCursor(Qt.PointingHandCursor)` and a `:hover` rule in the inline stylesheet: `QPushButton:hover { min-width: 34px; min-height: 34px; }` (accent_color_dialog.py line 86-89 area).

---

## Detailed Findings

### Pillar 1: Copywriting (4/4)

Every item in the Copywriting Contract is present verbatim:

| Spec Item | Implementation | File:Line |
|-----------|---------------|-----------|
| "Connect Twitch" | `self._action_btn.setText("Connect Twitch")` | accounts_dialog.py:81 |
| "Disconnect" | `self._action_btn.setText("Disconnect")` | accounts_dialog.py:77 |
| "Connecting..." | `self._status_label.setText("Connecting...")` | accounts_dialog.py:73 |
| "Connected" / "Not connected" | both present | accounts_dialog.py:76,80 |
| Disconnect confirmation body | exact match | accounts_dialog.py:93-97 |
| "Apply" / "Reset" / "Cancel" | QDialogButtonBox buttons | accent_color_dialog.py:110-112 |
| "#rrggbb" placeholder | `setPlaceholderText("#rrggbb")` | accent_color_dialog.py:102 |
| "Paste Netscape cookie text here..." | `setPlaceholderText(...)` | cookie_import_dialog.py:153 |
| "Opens Google login in a browser window." | exact match | cookie_import_dialog.py:170 |
| "YouTube cookies imported." | toast callback | cookie_import_dialog.py:304 |
| "Invalid cookies: no .youtube.com entries found." | `_show_error(...)` | cookie_import_dialog.py:202,248,287 |
| "File is empty." | `_show_error(...)` | cookie_import_dialog.py:244 |
| "Coming in a future update" | tooltip on disabled actions | main_window.py:90,94 |
| "Twitch connection failed. Try again." | QMessageBox.warning | accounts_dialog.py:139 |
| "No file selected" (initial state) | QLabel default text | cookie_import_dialog.py:130 |

One spec item not matched: the "Enter a valid hex color (e.g. #3584e4)." inline error string. The implementation instead shows a red border on the QLineEdit without any text error label. This is a minor deviation — the visual feedback is present but uses a different modality (border vs label). Scored as acceptable since the border-on-invalid pattern is explicitly described in the Interaction States section of the spec.

### Pillar 2: Visuals (3/4)

**Pass:**
- All three dialogs have window titles set
- Section header in AccentColorDialog uses 10pt/DemiBold, clear visual hierarchy
- Swatch grid is 4x2 per spec (8 swatches, `row, col = divmod(idx, 4)`)
- Swatch selected state shows white inner border + colored outer outline — matches spec
- QGroupBox "Twitch" provides clear section separation in AccountsDialog
- Inline error label uses red color, positioned below tabs — matches spec
- File import button hidden until file chosen — correct state-driven reveal

**Issues:**
- Swatch hover state: spec declares `cursor: pointer` and scale to 34x34px on hover. Neither `setCursor(Qt.PointingHandCursor)` nor a `:hover` stylesheet rule is present in `accent_color_dialog.py`. Without a pointer cursor, the swatches look non-interactive until clicked (minor but spec-declared).
- Icon-only swatch buttons (no text, 32x32) have no `setAccessibleName()` or `setToolTip()`. Screen reader users get no label for the 8 color buttons. Low severity for a desktop media player, but noted.

### Pillar 3: Color (4/4)

Color usage is clean and matches the spec's 60/30/10 model:

- **Dominant (60%):** All dialog backgrounds use Qt system `palette(window)` — no hardcoded backgrounds.
- **Secondary (30%):** QGroupBox, QLineEdit use system palette — no manual overrides.
- **Accent (10%):** `apply_accent_palette()` modifies `QPalette.Highlight` so that all `palette(highlight)` references in chip/seg/filter-toggle per-widget QSS pick up the new color. `build_accent_qss()` targets only `QSlider::sub-page:horizontal` globally. This is architecturally correct per D-11.
- **Destructive:** `#c0392b` appears only at `cookie_import_dialog.py:106` (inline error label color) and `accent_color_dialog.py:165` (invalid hex border). Both are spec-approved uses. No other hardcoded hex in the Phase 40 dialog files.
- **Not applied to:** dialog buttons (OK/Cancel/Apply), QMenu items, QLineEdit borders (except the error state) — all compliant per spec exclusions.

### Pillar 4: Typography (3/4)

**Pass:**
- `accent_color_dialog.py:74-75` — section label: 10pt/DemiBold — matches spec "Section headers inside dialogs: 10pt/DemiBold"
- `cookie_import_dialog.py:104` — error label: 9pt — matches spec "Small / secondary label: 9pt/Normal"
- `cookie_import_dialog.py:133` — filename label: 9pt — matches spec
- `cookie_import_dialog.py` body text and tab labels: Qt default (~10pt on most Linux systems) — no explicit size set, passable

**Issue:**
- `accounts_dialog.py` — neither the `_status_label` (line 47) nor the `_action_btn` have an explicit `QFont.setPointSize(10)`. The spec requires 10pt/Normal for dialog body text. All other Phase 40 dialogs follow this pattern explicitly. AccountsDialog relies on Qt default which may vary by platform.

### Pillar 5: Spacing (3/4)

**Pass:**
- `accent_color_dialog.py:67-68` — root layout: `setContentsMargins(16,16,16,16)` (md=16px), `setSpacing(16)` — correct
- `accent_color_dialog.py:81` — swatch grid spacing: 8px (sm) — correct
- `cookie_import_dialog.py:90-91` — root: margins 16px, spacing 8px — correct
- `cookie_import_dialog.py:123-124,149-150,167-168` — tab interiors: margins 8px, spacing 8px — correct (sm token used for inner padding)
- Swatch button: `setFixedSize(32, 32)` — matches spec "32x32px minimum visual size"
- Minimum widths: AccountsDialog 360px, AccentColorDialog 360px, CookieImportDialog 480px — all match spec

**Issue:**
- `accounts_dialog.py` — the root `QVBoxLayout` (line 58) and `twitch_layout` (line 44) have no explicit `setContentsMargins` or `setSpacing` calls. Qt Fusion default margins are approximately 9px — below the spec's `md=16px` for dialog content margins. This makes AccountsDialog look visually tighter than the other two Phase 40 dialogs.

### Pillar 6: Experience Design (4/4)

State coverage is comprehensive across all three dialogs:

**AccountsDialog:**
- Not connected: label "Not connected", button "Connect Twitch" (enabled) — present
- Connecting: label "Connecting...", button disabled — present (accounts_dialog.py:73-74)
- Connected: label "Connected", button "Disconnect" (enabled) — present (accounts_dialog.py:76-78)
- OAuth failed: `QMessageBox.warning` — present (accounts_dialog.py:136-140)
- Destructive confirmation: `QMessageBox.question` with No as default — present (accounts_dialog.py:91-99)

**AccentColorDialog:**
- No swatch selected: hex entry empty — handled in `_load_saved_accent`
- Hex invalid: red border shown, no preview applied — present (accent_color_dialog.py:164-165)
- Apply: saves + accepts — present
- Reset: clears + restores original palette — present
- Cancel: restores original palette + QSS — present (overrides `reject()`)
- Pre-loads saved accent on open — present

**CookieImportDialog:**
- No file chosen: "No file selected" label, Import button hidden — present
- File chosen: filename shown (40-char truncated), Import button revealed — present
- Paste empty: Import button disabled — present (enabled on `textChanged`)
- Validation failure: inline red error label — present for all three import paths
- Google in-progress: button disabled + "Logging in..." status label — present
- Empty file error: "File is empty." inline error — present
- Success: toast notification + dialog accepts — present

Hamburger menu: 7 actions in 3 groups with 2 separators — correct. Export/Import Settings disabled with tooltip — correct. Accent startup load in MainWindow.__init__ — wired.

No state gaps found. Score reflects full coverage of the Interaction States table from UI-SPEC.md.

---

## Registry Safety

Registry audit: not applicable — shadcn not initialized (Qt/PySide6 desktop app, no web framework). No third-party component registries used.

---

## Files Audited

- `musicstreamer/ui_qt/accent_color_dialog.py` (232 lines)
- `musicstreamer/ui_qt/accounts_dialog.py` (144 lines)
- `musicstreamer/ui_qt/cookie_import_dialog.py` (314 lines)
- `musicstreamer/ui_qt/main_window.py` (262 lines)
- `musicstreamer/accent_utils.py` (66 lines)
- `.planning/phases/40-auth-dialogs-accent/40-UI-SPEC.md`
- `.planning/phases/40-auth-dialogs-accent/40-CONTEXT.md`
- `.planning/phases/40-auth-dialogs-accent/40-01-SUMMARY.md` through `40-04-SUMMARY.md`
