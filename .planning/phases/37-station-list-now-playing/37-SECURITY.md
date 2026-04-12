---
phase: 37
slug: station-list-now-playing
status: verified
threats_open: 0
asvs_level: 1
created: 2026-04-12
---

# Phase 37 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| ICY metadata → UI | Untrusted stream metadata displayed in NowPlayingPanel | String (artist/title from remote stream servers) |
| GStreamer errors → UI | Pipeline error messages displayed via toast | String (GStreamer error text) |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-37-01 | Spoofing | NowPlayingPanel.icy_label | mitigate | Qt.PlainText format on all ICY-sourced labels prevents rich-text/HTML injection | closed |
| T-37-02 | Tampering | NowPlayingPanel.name_provider_label | mitigate | Qt.PlainText format on station name/provider label | closed |
| T-37-03 | Information Disclosure | MainWindow._on_playback_error | mitigate | 80-char truncation on error message before display | closed |

*Status: open / closed*
*Disposition: mitigate (implementation required) / accept (documented risk) / transfer (third-party)*

---

## Accepted Risks Log

No accepted risks.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-04-12 | 3 | 3 | 0 | Claude (gsd-secure-phase) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-04-12

---

## Notes

Phase 37 introduces no new network surfaces, authentication paths, or trust boundary crossings. All widgets consume existing backend signals (Player, Repo) via in-process Qt signal connections. The primary security surface is untrusted ICY metadata from remote stream servers, which is locked down via `Qt.PlainText` on all display labels. The `cover_art.fetch_cover_art` network call was already present in the v1.5 GTK UI and is only re-wired here.
