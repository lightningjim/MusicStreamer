# MusicStreamer Release Notes

## v2.2

### Windows: Unpin from taskbar before upgrading

If you previously pinned MusicStreamer to the Windows taskbar, **unpin it before
running the v2.2 installer**, then re-pin after the upgrade completes.

**Why:** A taskbar-pinned shortcut caches the AppUserModelID
(`org.lightningjim.MusicStreamer`) at the moment it is pinned. Even though the
v2.2 installer now explicitly removes and recreates the Start-Menu shortcut via
an Inno Setup `[InstallDelete]` step (WIN-02-A / Pitfall 6), the installer cannot
reach a shortcut that has already been promoted to the taskbar by the user. A stale
taskbar pin retaining the old shortcut path can break the SMTC "MusicStreamer"
media-overlay identity — system media controls may show "Unknown app" — even after
the Start-Menu shortcut is correctly replaced.

**Steps:**
1. Right-click the MusicStreamer taskbar button and choose **Unpin from taskbar**.
2. Run the v2.2 installer (`MusicStreamer-2.2.x-win64-setup.exe`).
3. Launch MusicStreamer once from the Start Menu.
4. Right-click the taskbar button and choose **Pin to taskbar**.
