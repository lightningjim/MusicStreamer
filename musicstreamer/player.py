import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst, GLib
from yt_dlp import YoutubeDL
from musicstreamer.models import Station


class Player:
    def __init__(self):
        self._pipeline = Gst.ElementFactory.make("playbin", "player")
        self._pipeline.set_property(
            "video-sink", Gst.ElementFactory.make("fakesink", "fake-video")
        )
        audio_sink = Gst.ElementFactory.make("pulsesink", "audio-output")
        if audio_sink:
            self._pipeline.set_property("audio-sink", audio_sink)

    def play(self, station: Station, on_title: callable):
        url = (station.url or "").strip()
        if not url:
            on_title("(no URL set)")
            return
        if "youtube.com" in url or "youtu.be" in url:
            self._play_youtube(url, station.name, on_title)
        else:
            self._set_uri(url, station.name, on_title)

    def stop(self):
        self._pipeline.set_state(Gst.State.NULL)

    def _play_youtube(self, url: str, fallback_name: str, on_title: callable):
        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "noplaylist": True,
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "cachedir": False,
        }
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                acodec = info.get("acodec", "none")
                if acodec == "none":
                    print(f"yt-dlp: selected format has no audio codec (acodec={acodec})")
                    on_title("(no audio track)")
                    return
                stream_url = info.get("url")
                title = info.get("title") or fallback_name
        except Exception as e:
            print("yt-dlp error:", e)
            on_title("yt-dlp error")
            return
        if stream_url:
            self._set_uri(stream_url, title, on_title)

    def _set_uri(self, uri: str, title: str, on_title: callable):
        self._pipeline.set_state(Gst.State.NULL)
        self._pipeline.set_property("uri", uri)
        self._pipeline.set_state(Gst.State.PLAYING)
        on_title(title)
