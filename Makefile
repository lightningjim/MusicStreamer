PREFIX ?= $(HOME)/.local
DESKTOP_DIR = $(PREFIX)/share/applications
ICON_DIR    = $(PREFIX)/share/icons/hicolor/scalable/apps

DESKTOP_FILE = org.example.MusicStreamer.desktop
ICON_FILE    = musicstreamer/assets/org.example.MusicStreamer.svg

HAS_PIPX := $(shell command -v pipx 2>/dev/null)

.PHONY: deps install uninstall run

deps:
	sudo apt install -y \
		python3-gi \
		python3-gi-cairo \
		gir1.2-gtk-4.0 \
		gir1.2-adw-1 \
		gir1.2-gst-plugins-base-1.0 \
		gstreamer1.0-plugins-good \
		gstreamer1.0-plugins-bad \
		gstreamer1.0-libav \
		pipx

install:
	@if [ -n "$(HAS_PIPX)" ]; then \
		pipx install --editable . --system-site-packages; \
	else \
		pip install --user -e . --break-system-packages; \
	fi
	install -Dm644 $(DESKTOP_FILE) $(DESKTOP_DIR)/$(DESKTOP_FILE)
	@if [ -f "$(ICON_FILE)" ]; then \
		install -Dm644 $(ICON_FILE) $(ICON_DIR)/org.example.MusicStreamer.svg; \
	fi
	update-desktop-database $(DESKTOP_DIR) 2>/dev/null || true

uninstall:
	@if [ -n "$(HAS_PIPX)" ]; then \
		pipx uninstall musicstreamer; \
	else \
		pip uninstall -y musicstreamer; \
	fi
	rm -f $(DESKTOP_DIR)/$(DESKTOP_FILE)
	rm -f $(ICON_DIR)/org.example.MusicStreamer.svg
	update-desktop-database $(DESKTOP_DIR) 2>/dev/null || true

run:
	python3 -m musicstreamer
