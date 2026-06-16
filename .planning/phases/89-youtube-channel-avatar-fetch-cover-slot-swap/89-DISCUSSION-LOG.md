# Phase 89: YouTube Channel-Avatar Fetch + Cover-Slot Swap - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-15
**Phase:** 89-youtube-channel-avatar-fetch-cover-slot-swap
**Areas discussed:** Fetch timing & dialog feedback, Circular-crop look, Empty/failure fallback, Refresh avatar behavior

---

## Fetch timing & dialog feedback

### Fetch trigger
| Option | Description | Selected |
|--------|-------------|----------|
| On paste, debounced | ~600ms after URL settles; Phase 6/17 precedent | ✓ |
| On Save/OK only | Background on confirm; no in-dialog preview | |
| On paste, immediate | Fires every edit; redundant yt-dlp calls | |

**User's choice:** On paste, debounced → **D-01**

### Dialog UX
| Option | Description | Selected |
|--------|-------------|----------|
| Inline preview + status | Thumbnail preview + Fetching…/Avatar found line | ✓ |
| Status text only | Status line, no preview | |
| Silent background fetch | No feedback | |

**User's choice:** Inline preview + status → **D-02**

### Fetch fail
| Option | Description | Selected |
|--------|-------------|----------|
| Inline message, save still allowed | Non-blocking note; save proceeds | ✓ |
| Silent | No message; column stays NULL | |
| Warning toast on save | Toast in main window after close | |

**User's choice:** Inline message, save still allowed → **D-03**

### Provider gate
| Option | Description | Selected |
|--------|-------------|----------|
| YT-gated now, structured for reuse | Per-provider hook; 89b plugs in | ✓ |
| Strictly YouTube-only | Hardcode; 89b refactors later | |
| Provider-agnostic dispatch already | Build full registry now | |

**User's choice:** YT-gated now, structured for reuse → **D-04**

---

## Circular-crop look

### Circle fit
| Option | Description | Selected |
|--------|-------------|----------|
| Full-bleed circle | Diameter = slot, center-crop to square | |
| Inset circle with padding | Smaller circle, badge look | |
| You decide | Claude's discretion on diameter/padding | ✓ |

**User's choice:** You decide → **D-07 (Claude's discretion)**

### Border ring
| Option | Description | Selected |
|--------|-------------|----------|
| No border, antialiased edge | Clean circular clip, no ring | ✓ |
| Subtle 1px ring | Thin neutral ring | |
| You decide | Claude picks if ring helps | |

**User's choice:** No border, just antialiased edge → **D-06**

### Crop scope
| Option | Description | Selected |
|--------|-------------|----------|
| Yes — avatars only | Circle on avatar path only; covers/thumbnails stay square | ✓ |
| Circular for all cover-slot images | Apply to everything (scope creep) | |

**User's choice:** Yes — avatars only → **D-05**

---

## Empty/failure fallback

### Fallback
| Option | Description | Selected |
|--------|-------------|----------|
| Station thumbnail (current behavior) | No regression, no placeholder asset | ✓ |
| Generic placeholder | Neutral art, changes current behavior | |

**User's choice:** Station thumbnail (current behavior) → **D-08**

### Transient (<1s load)
| Option | Description | Selected |
|--------|-------------|----------|
| Station thumbnail until avatar ready | Show thumbnail, swap to avatar; no blank | ✓ |
| Blank/neutral until avatar ready | Visible blank moment each bind | |
| You decide | Leave to Claude | |

**User's choice:** Station thumbnail until avatar ready → **D-09**

---

## Refresh avatar behavior

### Button visibility
| Option | Description | Selected |
|--------|-------------|----------|
| Enabled only for avatar-capable URLs | Detected-YT only; 89b enables Twitch | ✓ |
| Always visible/enabled | No-op for non-avatar stations | |
| You decide | Leave gating to Claude | |

**User's choice:** Enabled only for avatar-capable URLs → **D-10**

### Refresh action
| Option | Description | Selected |
|--------|-------------|----------|
| Async + inline status + preview update | Refreshing… state, preview updates, keep old on fail | ✓ |
| Async, silent until done | Preview updates, no explicit state | |
| You decide | Leave feedback to Claude | |

**User's choice:** Async + inline status + preview update → **D-11**

### Cache write
| Option | Description | Selected |
|--------|-------------|----------|
| Overwrite in place atomically | Temp file + atomic rename; same path | ✓ |
| Overwrite directly | Simple; crash-mid-write risk | |
| You decide | Follow assets.py convention | |

**User's choice:** Overwrite in place atomically → **D-12**

---

## Claude's Discretion

- Exact circle diameter/inset within the square slot (D-07).
- Debounce interval (≈600ms suggested).
- Inline status/preview widget layout in EditStationDialog.
- Whether the avatar render path needs its own `_last_avatar_path`-style tracked state for `_apply_art_tier` resize replay.

## Deferred Ideas

- Twitch Helix `profile_image_url` fetch — Phase 89b (registers into the per-provider hook from D-04).
- Channel avatar in the logo slot — rejected (anti-goal: cover slot only).
- Per-play avatar refresh — rejected (one-time fetch + manual refresh only).
