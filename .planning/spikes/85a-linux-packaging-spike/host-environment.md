# Phase 85a Host Environment

Captured: 2026-05-26

## OS

```
lsb_release -a
```

```
Distributor ID:	Ubuntu
Description:	Ubuntu 26.04 LTS
Release:	26.04
Codename:	resolute
```

## Kernel

```
uname -r
```

```
7.0.0-15-generic
```

## GLIBC

```
ldd --version | head -1
```

```
ldd (Ubuntu GLIBC 2.43-2ubuntu2) 2.43
```

## podman

```
podman --version
```

```
podman version 5.7.0
```

## docker

```
docker --version
```

```
Docker version 29.5.2, build 79eb04c
```

## distrobox

```
distrobox --version
```

```
distrobox: 1.8.2.4
```

## gnome-screenshot

```
gnome-screenshot --version
```

```
gnome-screenshot 41.0
```

## grim

```
grim -h 2>&1 | head -1
```

```
Usage: grim [options...] [output-file]
```

## Session

```
echo "$WAYLAND_DISPLAY $XDG_SESSION_TYPE $XDG_CURRENT_DESKTOP"
```

```
wayland-0 wayland ubuntu:GNOME
```

## Notes

No fallbacks required — distrobox, gnome-screenshot, and grim all installed cleanly from Ubuntu 26.04 apt repos.
