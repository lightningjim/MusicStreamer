# Phase 40: Auth Dialogs + Accent - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-13
**Phase:** 40-auth-dialogs-accent
**Areas discussed:** Twitch OAuth flow, YouTube cookie import, Accent color picker, Hamburger menu wiring

---

## Twitch OAuth Flow

### AccountsDialog Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Button + status | Twitch section with Connect/Disconnect button + status. Subprocess QWebEngineView for OAuth. | ✓ |
| Inline WebView | Embed QWebEngineView directly in dialog. Simpler but loads 130MB into main process. | |

**User's choice:** Button + status
**Notes:** None

### Disconnect Option

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, disconnect button | When connected, show Disconnect that deletes token file. | ✓ |
| No, connect only | Only Connect. Manual file deletion to disconnect. | |

**User's choice:** Yes, disconnect button
**Notes:** None

---

## YouTube Cookie Import

### Dialog Approach

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated dialog | CookieImportDialog with File/Paste/Google Login sections. | ✓ |
| Section in AccountsDialog | Add cookie import as second section in AccountsDialog. | |

**User's choice:** Dedicated dialog
**Notes:** None

---

## Accent Color Picker

### Dialog Approach

| Option | Description | Selected |
|--------|-------------|----------|
| Grid + hex entry | 8 color swatches in grid + QLineEdit for hex. Live QSS preview. Apply/Reset buttons. | ✓ |
| Simple combo | QComboBox with preset names + Custom option opening QColorDialog. | |

**User's choice:** Grid + hex entry
**Notes:** None

---

## Hamburger Menu Wiring

### Menu Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Flat action list with separators | Single menu, all actions top-level, separators between groups. | ✓ |
| Grouped submenus | Submenus like Stations → Discover/Import, Settings → Accent/Cookies/etc. | |

**User's choice:** Flat action list with separators
**Notes:** User specifically requested horizontal rules/separators to visually group items within the dropdown.

---

## Claude's Discretion

- Exact 8 accent color presets, dialog dimensions, swatch sizes
- Whether oauth_helper.py is shared or split
- QSS selector specificity, CookieImportDialog tab/section layout
- AccountsDialog modality

## Deferred Ideas

None — discussion stayed within phase scope.
