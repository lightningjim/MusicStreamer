"""Phase 60 / GBS-01a..f: gbs_api unit + integration tests.

Fixture sources:
  tests/fixtures/gbs/*.{json,html,txt} — captured in 60-01 via
  scripts/gbs_capture_fixtures.sh (or hand-crafted from RESEARCH §Capability examples).

Pattern: monkey-patch urllib.request.urlopen / opener.open at the gbs_api
module level (mirrors tests/test_aa_import.py:45-48). Real network calls
are forbidden in this test module.
"""
from __future__ import annotations

import http.client
import http.cookiejar
import io
import json
import os
import urllib.error
import urllib.request
from unittest.mock import MagicMock, patch

import pytest

from musicstreamer import gbs_api
from musicstreamer.gbs_api import (
    GbsApiError,
    GbsAuthExpiredError,
    _decode_django_messages,
    _validate_gbs_cookies,
    fetch_active_playlist,
    fetch_station_metadata,
    fetch_streams,
    import_station,
    search,
    submit,
    vote_now_playing,
)


# ---------- helpers ----------

def _urlopen_factory(data: bytes, content_type: str = "application/json", status: int = 200):
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=cm)
    cm.__exit__ = MagicMock(return_value=False)
    cm.read = MagicMock(return_value=data)
    cm.status = status
    headers = MagicMock()
    headers.get = MagicMock(side_effect=lambda k, *_: {"Content-Type": content_type}.get(k))
    headers.get_all = MagicMock(return_value=[])
    cm.headers = headers
    cm.close = MagicMock()
    return cm


def _http_error_redirect(location: str = "/accounts/login/?next=/ajax"):
    headers = MagicMock()
    headers.get = MagicMock(return_value=location)
    return urllib.error.HTTPError(url="https://gbs.fm/ajax", code=302, msg="redirect",
                                  hdrs=headers, fp=None)


# ---------- GBS-01a: streams + metadata + import ----------

def test_fetch_streams_returns_six_qualities():
    streams = fetch_streams()
    assert len(streams) == 6
    qualities = {s["quality"] for s in streams}
    assert qualities == {"96", "128", "192", "256", "320", "flac"}
    flac = [s for s in streams if s["quality"] == "flac"][0]
    assert flac["codec"] == "FLAC"
    assert flac["bitrate_kbps"] == 1411  # CD-baseline sentinel (RESEARCH Q1)


def test_fetch_station_metadata():
    meta = fetch_station_metadata()
    assert meta["name"] == "GBS.FM"
    assert meta["logo_url"].startswith("https://gbs.fm/")
    assert meta["logo_url"].endswith(".png")
    assert "homepage" in meta


def test_import_idempotent(fake_repo):
    """First call inserts; second call updates in place; station_id stable."""
    with patch("musicstreamer.gbs_api._download_logo", return_value=None):
        inserted_1, updated_1 = import_station(fake_repo)
    assert (inserted_1, updated_1) == (1, 0)
    stations_1 = fake_repo.list_stations()
    assert len(stations_1) == 1
    sid_1 = stations_1[0].id
    streams_1 = fake_repo.list_streams(sid_1)
    assert len(streams_1) == 6
    qualities_1 = sorted(s.quality for s in streams_1)
    assert qualities_1 == sorted(["96", "128", "192", "256", "320", "flac"])

    with patch("musicstreamer.gbs_api._download_logo", return_value=None):
        inserted_2, updated_2 = import_station(fake_repo)
    # 60-08 / T6 (Plan 60-08 revision 2): after field-level dirty-check, an
    # idempotent re-import (no field changes anywhere) returns (0, 0). The
    # "(0, 1) on real refresh" path is separately covered by
    # test_import_one_field_changes_returns_one_updated.
    assert (inserted_2, updated_2) == (0, 0)
    stations_2 = fake_repo.list_stations()
    assert len(stations_2) == 1
    assert stations_2[0].id == sid_1, "station_id MUST be preserved across re-import"
    streams_2 = fake_repo.list_streams(sid_1)
    assert len(streams_2) == 6


def test_logo_download(fake_repo, monkeypatch):
    """copy_asset_for_station + update_station_art are called when logo fetch succeeds."""
    fake_tmp_path = "/tmp/fake_gbs_logo.png"
    monkeypatch.setattr(gbs_api, "_download_logo", lambda url: fake_tmp_path)
    art_path_holder = {}
    def fake_copy(station_id, src, kind):
        art_path_holder["station_id"] = station_id
        art_path_holder["src"] = src
        art_path_holder["kind"] = kind
        return f"/fake/assets/{station_id}_logo.png"
    monkeypatch.setattr(gbs_api, "copy_asset_for_station", fake_copy)
    monkeypatch.setattr("os.unlink", lambda p: None)
    import_station(fake_repo)
    assert art_path_holder["src"] == fake_tmp_path
    assert art_path_holder["kind"] == "station_art"
    sid = fake_repo.list_stations()[0].id
    # HIGH 1: matches canonical Station.station_art_path attribute
    assert fake_repo.get_station(sid).station_art_path is not None


# ---------- GBS-01b: cookie validator ----------

def test_validate_cookies_accept(gbs_fixtures_dir):
    text = (gbs_fixtures_dir / "cookies_valid.txt").read_text()
    assert _validate_gbs_cookies(text) is True


def test_validate_cookies_reject(gbs_fixtures_dir):
    no_session = (gbs_fixtures_dir / "cookies_invalid_no_sessionid.txt").read_text()
    wrong_domain = (gbs_fixtures_dir / "cookies_invalid_wrong_domain.txt").read_text()
    assert _validate_gbs_cookies(no_session) is False
    assert _validate_gbs_cookies(wrong_domain) is False
    assert _validate_gbs_cookies("") is False
    assert _validate_gbs_cookies("# garbage\n") is False


# ---------- GBS-01c: active playlist parser ----------

def test_fetch_playlist_cold_start(gbs_fixtures_dir, fake_cookies_jar, monkeypatch):
    payload = (gbs_fixtures_dir / "ajax_cold_start.json").read_bytes()
    monkeypatch.setattr(
        gbs_api, "_open_with_cookies",
        lambda url, cookies, timeout=10: _urlopen_factory(payload),
    )
    state = fetch_active_playlist(fake_cookies_jar)
    assert "now_playing_entryid" in state
    assert "icy_title" in state
    assert state["user_vote"] == 0
    assert "score" in state
    # Cold-start fixture has at least one removal event
    assert isinstance(state["removed_ids"], list)
    assert len(state["removed_ids"]) > 0


def test_fetch_playlist_steady_state(gbs_fixtures_dir, fake_cookies_jar, monkeypatch):
    payload = (gbs_fixtures_dir / "ajax_steady_state.json").read_bytes()
    monkeypatch.setattr(
        gbs_api, "_open_with_cookies",
        lambda url, cookies, timeout=10: _urlopen_factory(payload),
    )
    state = fetch_active_playlist(fake_cookies_jar, cursor={"position": 200})
    # Steady state has score and removed_ids
    assert "score" in state
    assert isinstance(state["removed_ids"], list)


def test_fetch_playlist_auth_expired(fake_cookies_jar, monkeypatch):
    """Mocking _open_with_cookies to raise GbsAuthExpiredError directly —
    since _open_with_cookies is the conversion layer, replacing it means
    raising the already-converted exception."""
    def _raise(url, cookies, timeout=10):
        raise GbsAuthExpiredError("Session expired (302→login)")
    monkeypatch.setattr(gbs_api, "_open_with_cookies", _raise)
    with pytest.raises(GbsAuthExpiredError):
        fetch_active_playlist(fake_cookies_jar)


# ---------- GBS-01d: vote_now_playing ----------

def test_vote_now_playing_success(gbs_fixtures_dir, fake_cookies_jar, monkeypatch):
    payload = (gbs_fixtures_dir / "ajax_vote_set.json").read_bytes()
    monkeypatch.setattr(
        gbs_api, "_open_with_cookies",
        lambda url, cookies, timeout=15: _urlopen_factory(payload),
    )
    result = vote_now_playing(1810737, 3, fake_cookies_jar)
    assert result["user_vote"] == 3
    assert "score" in result


def test_vote_now_playing_invalid_value(fake_cookies_jar):
    with pytest.raises(ValueError):
        vote_now_playing(123, 6, fake_cookies_jar)
    with pytest.raises(ValueError):
        vote_now_playing(123, -1, fake_cookies_jar)


# ---------- GBS-01e: search + submit ----------

def test_search_parses_results(gbs_fixtures_dir, fake_cookies_jar, monkeypatch):
    payload = (gbs_fixtures_dir / "search_test_p1.html").read_bytes()
    monkeypatch.setattr(
        gbs_api, "_open_with_cookies",
        lambda url, cookies, timeout=10: _urlopen_factory(payload, content_type="text/html"),
    )
    out = search("test", 1, fake_cookies_jar)
    assert out["page"] == 1
    assert isinstance(out["results"], list)
    assert len(out["results"]) >= 1
    r0 = out["results"][0]
    assert "songid" in r0 and isinstance(r0["songid"], int)
    assert "artist" in r0 and r0["artist"]
    assert "title" in r0 and r0["title"]
    assert r0["add_url"].startswith("/add/")


def test_search_pagination(gbs_fixtures_dir, fake_cookies_jar, monkeypatch):
    payload = (gbs_fixtures_dir / "search_test_p1.html").read_bytes()
    monkeypatch.setattr(
        gbs_api, "_open_with_cookies",
        lambda url, cookies, timeout=10: _urlopen_factory(payload, content_type="text/html"),
    )
    out = search("test", 1, fake_cookies_jar)
    assert out["total_pages"] >= 1


def test_search_empty(gbs_fixtures_dir, fake_cookies_jar, monkeypatch):
    payload = (gbs_fixtures_dir / "search_empty.html").read_bytes()
    monkeypatch.setattr(
        gbs_api, "_open_with_cookies",
        lambda url, cookies, timeout=10: _urlopen_factory(payload, content_type="text/html"),
    )
    out = search("zzzzzzzzznoresults", 1, fake_cookies_jar)
    assert out["results"] == []
    assert out["page"] == 1


def test_submit_success_decodes_messages(gbs_fixtures_dir, fake_cookies_jar, monkeypatch):
    """submit() returns the decoded messages cookie text."""
    raw_response = (gbs_fixtures_dir / "add_redirect_response.txt").read_text()
    # Simulate the 302 response with the messages cookie in Set-Cookie header.
    def fake_open(url, cookies, timeout=15):
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=cm)
        cm.__exit__ = MagicMock(return_value=False)
        # Find Set-Cookie line(s) in the captured response
        cookie_lines = [l for l in raw_response.splitlines()
                       if l.lower().startswith("set-cookie:") and "messages=" in l]
        # Strip the "set-cookie: " prefix
        cookie_values = [l.split(":", 1)[1].strip() for l in cookie_lines]
        location_lines = [l for l in raw_response.splitlines() if l.lower().startswith("location:")]
        location = location_lines[0].split(":", 1)[1].strip() if location_lines else "/playlist"
        headers = MagicMock()
        headers.get = MagicMock(side_effect=lambda k, *_: {"Location": location}.get(k))
        headers.get_all = MagicMock(return_value=cookie_values)
        cm.headers = headers
        cm.close = MagicMock()
        return cm
    monkeypatch.setattr(gbs_api, "_open_no_redirect", fake_open)
    result = submit(88135, fake_cookies_jar)
    # Must decode to "Track added successfully!" or similar non-empty string
    assert result, f"submit returned empty string; expected decoded messages text"
    assert "added" in result.lower() or "track" in result.lower()


def test_submit_auth_expired(fake_cookies_jar, monkeypatch):
    def fake_open(url, cookies, timeout=15):
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=cm)
        cm.__exit__ = MagicMock(return_value=False)
        headers = MagicMock()
        headers.get = MagicMock(return_value="/accounts/login/?next=/add/123")
        headers.get_all = MagicMock(return_value=[])
        cm.headers = headers
        cm.close = MagicMock()
        return cm
    monkeypatch.setattr(gbs_api, "_open_no_redirect", fake_open)
    with pytest.raises(GbsAuthExpiredError):
        submit(123, fake_cookies_jar)


def test_decode_django_messages(gbs_fixtures_dir):
    text = (gbs_fixtures_dir / "messages_cookie_track_added.txt").read_text().strip()
    msgs = _decode_django_messages(text)
    assert len(msgs) >= 1
    assert "added" in msgs[0].lower() or "track" in msgs[0].lower()


def test_decode_django_messages_garbage_returns_empty():
    """Pitfall 8: graceful fallback if decode fails."""
    assert _decode_django_messages("") == []
    assert _decode_django_messages("not-base64") == []
    assert _decode_django_messages("###:::") == []


# ---------- Plan 60-08 regression tests (T13 + T6) ----------
# These tests use the real urllib opener chain — patching at the lowest
# sensible transport layer (AbstractHTTPHandler.do_open) so that
# _NoRedirect.http_error_302 (and the CPython HTTPDefaultErrorHandler chain)
# run for real. This is intentionally deeper than the existing
# test_submit_success_decodes_messages, which patches _open_no_redirect
# directly and therefore cannot detect the T13 regression.

def _make_fake_302_response(location: str, set_cookie: str | None = None,
                            body: bytes = b"") -> http.client.HTTPResponse:
    """Build an http.client.HTTPResponse-shaped object for a fake 302.

    We construct it from a synthetic raw-HTTP byte stream parsed back through
    http.client so the resulting object exposes the same .status / .headers /
    .read() surface that AbstractHTTPHandler.do_open would produce.
    """
    raw = b"HTTP/1.1 302 Found\r\n"
    raw += f"Location: {location}\r\n".encode()
    if set_cookie:
        raw += f"Set-Cookie: {set_cookie}\r\n".encode()
    raw += b"Content-Length: " + str(len(body)).encode() + b"\r\n"
    raw += b"\r\n"
    raw += body

    class _FakeSock:
        def __init__(self, data: bytes):
            self._buf = io.BytesIO(data)
        def makefile(self, *a, **kw):
            return self._buf
        def sendall(self, *a, **kw):
            pass
        def close(self):
            pass

    sock = _FakeSock(raw)
    resp = http.client.HTTPResponse(sock)
    resp.begin()
    return resp


def test_open_no_redirect_returns_302_response_not_raises(monkeypatch, fake_cookies_jar):
    """T13 RED: real _NoRedirect chain returns the response, never raises.

    Patches the LOW-level transport so the entire opener chain (including
    _NoRedirect.http_error_302) runs against real CPython code paths.
    Currently FAILS: the broken redirect_request-returns-None pattern causes
    HTTPError(302) to bubble up before this assertion can be reached.
    """
    fake_resp = _make_fake_302_response(
        location="/playlist",
        set_cookie="messages=eyJfX2pzb25fbWVzc2FnZXNfXyI6W119; Path=/",
    )
    def _fake_do_open(self, http_class, req, **kwargs):
        return fake_resp
    monkeypatch.setattr(
        urllib.request.AbstractHTTPHandler, "do_open", _fake_do_open
    )
    resp = gbs_api._open_no_redirect("https://gbs.fm/add/123", fake_cookies_jar)
    assert resp.headers.get("Location") == "/playlist"
    assert resp.headers.get_all("Set-Cookie")  # non-empty


def test_submit_success_via_real_redirect_handler(monkeypatch, fake_cookies_jar, gbs_fixtures_dir):
    """T13 RED: submit() returns decoded messages text, not HTTPError(302).

    Reads the canonical Set-Cookie value from the fixture and embeds it in a
    real http.client.HTTPResponse so _NoRedirect.http_error_302 must handle it.
    """
    cookie_path = os.path.join(str(gbs_fixtures_dir), "messages_cookie_track_added.txt")
    with open(cookie_path) as f:
        cookie_value = f.read().strip()
    fake_resp = _make_fake_302_response(
        location="/playlist",
        set_cookie=f"messages={cookie_value}:sig1:sig2; Path=/",
    )
    def _fake_do_open(self, http_class, req, **kwargs):
        return fake_resp
    monkeypatch.setattr(urllib.request.AbstractHTTPHandler, "do_open", _fake_do_open)
    text = gbs_api.submit(123, fake_cookies_jar)
    assert "Track added successfully!" in text


def test_submit_auth_expired_still_raises(monkeypatch, fake_cookies_jar):
    """T13 must-not-regress: 302 -> /accounts/login/ still raises GbsAuthExpiredError.

    This test verifies the auth-expired path continues to work after the
    http_error_302 override is added in Task 2. Expected to PASS now (pre-existing
    correct behavior), and MUST NOT regress after the GREEN fix.
    """
    fake_resp = _make_fake_302_response(location="/accounts/login/?next=/add/123")
    def _fake_do_open(self, http_class, req, **kwargs):
        return fake_resp
    monkeypatch.setattr(urllib.request.AbstractHTTPHandler, "do_open", _fake_do_open)
    with pytest.raises(gbs_api.GbsAuthExpiredError):
        gbs_api.submit(123, fake_cookies_jar)


def test_import_no_field_changes_returns_zero_updated(fake_repo):
    """T6 RED: idempotent re-import (no field changes) must return (0, 0).

    Pre-populates the repo with exactly the canonical GBS quality tier data
    by running import_station once, then asserts a second call returns (0, 0).
    Currently FAILS: import_station unconditionally returns (0, 1) on the
    update path regardless of actual field changes.
    """
    with patch("musicstreamer.gbs_api._download_logo", return_value=None):
        import_station(fake_repo)  # first call: inserts
        inserted, updated = import_station(fake_repo)  # second call: no-op
    assert (inserted, updated) == (0, 0), (
        f"Expected (0, 0) for idempotent re-import, got ({inserted}, {updated})"
    )


def test_import_one_field_changes_returns_one_updated(fake_repo):
    """T6 must-not-regress: when a real field changes, return (0, 1).

    Pre-populates via first import_station call (canonical state), then
    mutates one stream's bitrate_kbps by +1 to simulate an upstream change,
    then asserts the second import returns (0, 1).
    Expected to PASS now (new functionality verified after GREEN).
    """
    with patch("musicstreamer.gbs_api._download_logo", return_value=None):
        import_station(fake_repo)  # first call: inserts canonical state
    # Mutate one stream field to simulate an upstream change
    sid = fake_repo.list_stations()[0].id
    streams = fake_repo.list_streams(sid)
    assert streams, "Expected 6 streams after first import"
    first_stream = streams[0]
    # Corrupt bitrate_kbps by +1 so the dirty-check detects a change
    fake_repo.update_stream(
        first_stream.id, first_stream.url, first_stream.label or "",
        first_stream.quality, first_stream.position,
        first_stream.stream_type or "shoutcast", first_stream.codec,
        bitrate_kbps=first_stream.bitrate_kbps + 1,
    )
    with patch("musicstreamer.gbs_api._download_logo", return_value=None):
        inserted, updated = import_station(fake_repo)
    assert (inserted, updated) == (0, 1), (
        f"Expected (0, 1) when one field changed, got ({inserted}, {updated})"
    )


def test_import_fresh_insert_returns_one_zero(fake_repo):
    """T6 must-not-regress: fresh insert still returns (1, 0).

    Expected to PASS both before and after the GREEN fix.
    """
    with patch("musicstreamer.gbs_api._download_logo", return_value=None):
        inserted, updated = import_station(fake_repo)
    assert (inserted, updated) == (1, 0)


# ---------- Plan 60-10: queue enumeration parser tests (T8) ----------

def test_fetch_playlist_enumerates_queue(gbs_fixtures_dir, fake_cookies_jar, monkeypatch):
    """60-10 / T8 (RED): fetch_active_playlist must return queue_rows as a list[dict].

    Uses the canonical ajax_cold_start.json fixture which has one 'adds' event
    containing 4 <tr> rows: one with class='playing' (entryid 1810809) and three
    upcoming rows (no-play/no-history class: 1810810, 1810811, 1810812).

    Currently FAILS: _fold_ajax_events does not populate state['queue_rows'].
    Fix (Task 2): add _QueueRowParser + state['queue_rows'] = [] + extend on 'adds'.
    """
    payload = (gbs_fixtures_dir / "ajax_cold_start.json").read_bytes()
    monkeypatch.setattr(
        gbs_api, "_open_with_cookies",
        lambda url, cookies, timeout=10: _urlopen_factory(payload),
    )
    state = fetch_active_playlist(fake_cookies_jar)
    # queue_rows must exist and be a non-empty list
    assert "queue_rows" in state, "state must have 'queue_rows' key (missing — T8 parser not implemented)"
    rows = state["queue_rows"]
    assert isinstance(rows, list) and len(rows) >= 1, (
        f"queue_rows must be a non-empty list; got: {rows!r}"
    )
    # Each row must have all required keys
    required_keys = {"entryid", "songid", "artist", "title", "duration"}
    for row in rows:
        missing = required_keys - set(row.keys())
        assert not missing, f"row {row!r} missing keys: {missing}"
    # No upcoming row should be the now-playing row (class='playing')
    # The now-playing entryid from the fixture is 1810809 (only row with class='playing').
    now_playing_entryid = state.get("now_playing_entryid")
    if now_playing_entryid is not None:
        queue_entryids = [r["entryid"] for r in rows]
        assert now_playing_entryid not in queue_entryids, (
            f"now-playing entryid {now_playing_entryid} must NOT appear in queue_rows; "
            f"got: {queue_entryids}"
        )


def test_queue_parser_skips_playing_and_history(monkeypatch):
    """60-10 / T8 (RED): _parse_adds_html must skip class='playing'/'history' rows.

    Constructs a minimal HTML snippet with 4 <tr> rows:
      - class='playing' (should be skipped)
      - class='history' (should be skipped)
      - class='odd' (should be included)
      - no class (should be included)

    Currently FAILS: _parse_adds_html does not exist yet.
    Fix (Task 2): add _QueueRowParser + _parse_adds_html helper in gbs_api.py.
    """
    from musicstreamer.gbs_api import _parse_adds_html
    html = """
    <tr id="100" class="playing odd">
        <td class="artistry"><a href='/artist/1'>PlayingArtist</a></td>
        <td><a href='/song/101'>PlayingTitle</a></td>
        <td class="time">3:00</td>
    </tr>
    <tr id="200" class="history even">
        <td class="artistry"><a href='/artist/2'>HistoryArtist</a></td>
        <td><a href='/song/201'>HistoryTitle</a></td>
        <td class="time">4:30</td>
    </tr>
    <tr id="300" class="odd">
        <td class="artistry"><a href='/artist/3'>OddArtist</a></td>
        <td><a href='/song/301'>OddTitle</a></td>
        <td class="time">2:15</td>
    </tr>
    <tr id="400">
        <td class="artistry"><a href='/artist/4'>NoClassArtist</a></td>
        <td><a href='/song/401'>NoClassTitle</a></td>
        <td class="time">5:10</td>
    </tr>
    """
    rows = _parse_adds_html(html)
    assert len(rows) == 2, f"Expected 2 upcoming rows (odd + no-class); got {len(rows)}: {rows!r}"
    entryids = [r["entryid"] for r in rows]
    assert 300 in entryids, "odd-class row (id=300) must be included"
    assert 400 in entryids, "no-class row (id=400) must be included"
    assert 100 not in entryids, "playing row (id=100) must be skipped"
    assert 200 not in entryids, "history row (id=200) must be skipped"
    # Each row has all required keys
    for row in rows:
        assert set(row.keys()) >= {"entryid", "songid", "artist", "title", "duration"}


# ---------- Plan 60-11: artist/album parser tests (T12) ----------

def test_search_returns_artist_links(gbs_fixtures_dir, fake_cookies_jar, monkeypatch):
    """60-11 / T12 (RED): search() must return artist_links as non-empty list on page 1.

    Uses search_test_p1.html which contains <p class="artists">Artists: block with
    Testament (/artist/4803) among others (diagnosis §2a, §4).

    Currently FAILS: search() dict has no 'artist_links' key.
    Fix (Task 2): add _ArtistAlbumParser + artist_links key to search() return dict.
    """
    payload = (gbs_fixtures_dir / "search_test_p1.html").read_bytes()
    monkeypatch.setattr(
        gbs_api, "_open_with_cookies",
        lambda url, cookies, timeout=10: _urlopen_factory(payload, content_type="text/html"),
    )
    out = search("test", 1, fake_cookies_jar)
    assert "artist_links" in out, "search() must return 'artist_links' key"
    links = out["artist_links"]
    assert isinstance(links, list), f"artist_links must be a list; got {type(links)}"
    assert len(links) >= 1, f"artist_links must be non-empty on page 1 with matches; got {links!r}"
    for entry in links:
        assert "text" in entry and "url" in entry, f"Each artist_links entry must have 'text' and 'url': {entry!r}"
        assert isinstance(entry["text"], str), f"entry['text'] must be str: {entry!r}"
        assert isinstance(entry["url"], str), f"entry['url'] must be str: {entry!r}"
    # Testament is present in search_test_p1.html at /artist/4803 (diagnosis §2a)
    urls = [e["url"] for e in links]
    assert "/artist/4803" in urls, (
        f"Expected /artist/4803 (Testament) in artist_links urls; got: {urls}"
    )


def test_search_returns_album_links(gbs_fixtures_dir, fake_cookies_jar, monkeypatch):
    """60-11 / T12 (RED): search() must return album_links as non-empty list on page 1.

    Uses search_test_p1.html which contains <p class="artists">Albums: block with
    /album/1488 (#gbs-fm's greatest shits) (diagnosis §2a, §4).

    Currently FAILS: search() dict has no 'album_links' key.
    """
    payload = (gbs_fixtures_dir / "search_test_p1.html").read_bytes()
    monkeypatch.setattr(
        gbs_api, "_open_with_cookies",
        lambda url, cookies, timeout=10: _urlopen_factory(payload, content_type="text/html"),
    )
    out = search("test", 1, fake_cookies_jar)
    assert "album_links" in out, "search() must return 'album_links' key"
    links = out["album_links"]
    assert isinstance(links, list), f"album_links must be a list; got {type(links)}"
    assert len(links) >= 1, f"album_links must be non-empty on page 1 with matches; got {links!r}"
    for entry in links:
        assert "text" in entry and "url" in entry, f"Each album_links entry must have 'text' and 'url': {entry!r}"
    urls = [e["url"] for e in links]
    assert "/album/1488" in urls, (
        f"Expected /album/1488 in album_links urls; got: {urls}"
    )


def test_search_page2_has_no_artist_album_links(gbs_fixtures_dir, fake_cookies_jar, monkeypatch):
    """60-11 / T12 (RED): search() must return empty artist_links + album_links on page 2.

    search_test_p2.html has no <p class="artists"> blocks (diagnosis §2a — page 2+ omits them).

    Currently FAILS: search() dict has no 'artist_links'/'album_links' keys.
    """
    payload = (gbs_fixtures_dir / "search_test_p2.html").read_bytes()
    monkeypatch.setattr(
        gbs_api, "_open_with_cookies",
        lambda url, cookies, timeout=10: _urlopen_factory(payload, content_type="text/html"),
    )
    out = search("test", 2, fake_cookies_jar)
    assert "artist_links" in out, "search() must return 'artist_links' key even on page 2"
    assert "album_links" in out, "search() must return 'album_links' key even on page 2"
    assert out["artist_links"] == [], (
        f"artist_links must be [] on page 2 (no blocks in p2 fixture); got {out['artist_links']!r}"
    )
    assert out["album_links"] == [], (
        f"album_links must be [] on page 2 (no blocks in p2 fixture); got {out['album_links']!r}"
    )


# ---------- Phase 60.1 / GBS-01e Wave 0 RED tests (drill-down + multi-word) ----------
# Plan 60.1-01 RED: 6 new tests pinning multi-word search, _ArtistPageParser,
# _AlbumPageParser (incl. D-02 belt-and-suspenders regression), and the two new
# fetch helpers. Plan 60.1-02 turns these GREEN by adding the missing parsers /
# helpers + the multi-word fix to musicstreamer/gbs_api.py.


def test_search_returns_artist_links_multiword(gbs_fixtures_dir, fake_cookies_jar, monkeypatch):
    """Phase 60.1 / GBS-01e Issue A (RED): multi-word query must populate artist_links.

    Per CONTEXT.md D-03, the multi-word fixture is captured first (foo+fighters) and this
    RED test pins the contract: a multi-word /search response with matches must yield
    non-empty artist_links from search().

    FAILS BEFORE Plan 02 lands (root cause unconfirmed — RESEARCH §Pitfall 1 hypotheses
    2 or 3 most likely; Plan 02 inspects the captured HTML and applies the minimal patch).

    If after fixture inspection it turns out hypothesis 1 holds (server omits the panel
    entirely for multi-word), Plan 02 relaxes this assertion to `len(...) == 0` and
    documents the server-side limitation in CONTEXT.md.
    """
    from musicstreamer.gbs_api import search
    payload = (gbs_fixtures_dir / "search_multiword_p1.html").read_bytes()
    monkeypatch.setattr(
        gbs_api, "_open_with_cookies",
        lambda url, cookies, timeout=10: _urlopen_factory(payload, content_type="text/html"),
    )
    out = search("foo fighters", 1, fake_cookies_jar)
    assert "artist_links" in out, "search() must return 'artist_links' key"
    links = out["artist_links"]
    assert isinstance(links, list), f"artist_links must be a list; got {type(links)}"
    assert len(links) >= 1, (
        f"Multi-word query 'foo fighters' must yield at least one artist_links entry; "
        f"got {links!r}. If the captured fixture has no Artists block (hypothesis 1), "
        f"Plan 02 must relax this assertion AND document the server-side limitation."
    )


def test_artist_page_parses(gbs_fixtures_dir):
    """Phase 60.1 / GBS-01e (RED): _ArtistPageParser extracts >=1 song from artist_4803.html.

    Pins:
      - Class is gated on <table width="620" class="artist"> (NOT class="songs")
      - Rows tagged class="albumTitle" are skipped (Pitfall 5 — album-separator rows)
      - <th>-only header row is skipped
      - Each result has the same dict shape as _SongRowParser output:
        {songid: int, artist: str, title: str, duration: str, add_url: str}
      - artist field is the page-title artist ("Testament"), populated per-row

    FAILS BEFORE Plan 02 lands: AttributeError: module 'musicstreamer.gbs_api' has no
    attribute '_ArtistPageParser'.
    """
    from musicstreamer import gbs_api as _gbs
    payload = (gbs_fixtures_dir / "artist_4803.html").read_text(encoding="utf-8", errors="replace")
    parser = _gbs._ArtistPageParser()
    parser.feed(payload)
    parser.close()
    results = parser.results
    assert len(results) > 0, f"_ArtistPageParser must extract >=1 song from Testament fixture; got {len(results)} rows"
    for row in results:
        assert isinstance(row.get("songid"), int), f"songid must be int; got {row!r}"
        assert row.get("artist") == "Testament", f"artist must be 'Testament' (page title); got {row.get('artist')!r}"
        assert row.get("title"), f"title must be non-empty; got {row.get('title')!r}"
        assert row.get("duration"), f"duration must be non-empty; got {row.get('duration')!r}"
        add_url = row.get("add_url", "")
        assert add_url.startswith("/add/"), f"add_url must start with /add/; got {add_url!r}"
    # Spot-check one canonical row from the Brotherhood of the Snake album section
    # (artist_4803.html lines 384-486 — songid 563811 is the album's title track)
    songids = [r["songid"] for r in results]
    assert 563811 in songids, (
        f"Expected songid 563811 (Brotherhood of the Snake) in Testament catalog; got songids {songids[:10]}..."
    )


def test_album_page_parses(gbs_fixtures_dir):
    """Phase 60.1 / GBS-01e (RED): _AlbumPageParser extracts the song row from album_1488.html.

    Pins (per CONTEXT.md D-02 belt-and-suspenders + RESEARCH §Pitfall 6):
      - Locks onto the FIRST <table width="620"> inside <div class="playlist">
      - REJECTS class="artist" and class="songs" (D-02 belt-and-suspenders)
      - Row shape is 6 columns: [artist_link, song_link, codec, bitrate, duration, add_link]
      - Per-row artist comes from <a href="/artist/Y"> in column 0 (NOT a page-title)

    FAILS BEFORE Plan 02 lands: AttributeError: module 'musicstreamer.gbs_api' has no
    attribute '_AlbumPageParser'.
    """
    from musicstreamer import gbs_api as _gbs
    payload = (gbs_fixtures_dir / "album_1488.html").read_text(encoding="utf-8", errors="replace")
    parser = _gbs._AlbumPageParser()
    parser.feed(payload)
    parser.close()
    results = parser.results
    assert len(results) >= 1, f"_AlbumPageParser must extract >=1 song from album_1488 fixture; got {len(results)} rows"
    # The album fixture is sparse (1 row per RESEARCH §Pitfall 6). Spot-check the canonical row.
    first = results[0]
    assert first.get("songid") == 5406, f"first row songid must be 5406; got {first.get('songid')!r}"
    assert first.get("artist") == "Ice Traigh & woodch", (
        f"first row artist must be 'Ice Traigh & woodch' (per-row artist from td 0); "
        f"got {first.get('artist')!r}"
    )
    assert first.get("title") == "The Ballad of JohnVonBunghole", (
        f"first row title must match album fixture; got {first.get('title')!r}"
    )
    assert first.get("duration") == "4:57", f"first row duration must be '4:57'; got {first.get('duration')!r}"
    assert first.get("add_url") == "/add/5406", f"first row add_url must be '/add/5406'; got {first.get('add_url')!r}"


def test_album_parser_rejects_artist_page_table(gbs_fixtures_dir):
    """Phase 60.1 / GBS-01e (RED): _AlbumPageParser MUST return [] for an artist page.

    D-02 belt-and-suspenders: explicitly reject class="artist" tables even when they
    match the width="620" + <div class="playlist"> container gate. Without this guard,
    a router bug or future markup change could feed _AlbumPageParser an artist page
    and silently return garbage rows.

    FAILS BEFORE Plan 02 lands: AttributeError on _AlbumPageParser.
    After Plan 02 lands: must remain GREEN (regression guard).
    """
    from musicstreamer import gbs_api as _gbs
    payload = (gbs_fixtures_dir / "artist_4803.html").read_text(encoding="utf-8", errors="replace")
    parser = _gbs._AlbumPageParser()
    parser.feed(payload)
    parser.close()
    assert parser.results == [], (
        f"_AlbumPageParser MUST reject class='artist' tables (D-02 belt-and-suspenders); "
        f"got {len(parser.results)} rows from artist fixture"
    )


def test_fetch_artist_songs_returns_results(gbs_fixtures_dir, fake_cookies_jar, monkeypatch):
    """Phase 60.1 / GBS-01e (RED): gbs_api.fetch_artist_songs(id, cookies) returns dict.

    Pins:
      - URL is f"{GBS_BASE}/artist/{artist_id}"
      - Returns {"results": list[dict]} with same shape as search() results entries
      - Reuses _open_with_cookies (auto-handles 302→login via GbsAuthExpiredError)

    FAILS BEFORE Plan 02 lands: AttributeError: ...has no attribute 'fetch_artist_songs'.
    """
    from musicstreamer import gbs_api as _gbs
    payload = (gbs_fixtures_dir / "artist_4803.html").read_bytes()
    monkeypatch.setattr(
        _gbs, "_open_with_cookies",
        lambda url, cookies, timeout=10: _urlopen_factory(payload, content_type="text/html"),
    )
    out = _gbs.fetch_artist_songs(4803, fake_cookies_jar)
    assert isinstance(out, dict), f"fetch_artist_songs must return dict; got {type(out)}"
    assert "results" in out, f"fetch_artist_songs must return 'results' key; got {list(out)}"
    assert isinstance(out["results"], list), f"results must be list; got {type(out['results'])}"
    assert len(out["results"]) > 0, f"results must be non-empty for Testament artist; got {len(out['results'])}"


def test_fetch_album_songs_returns_results(gbs_fixtures_dir, fake_cookies_jar, monkeypatch):
    """Phase 60.1 / GBS-01e (RED): gbs_api.fetch_album_songs(id, cookies) returns dict.

    FAILS BEFORE Plan 02 lands: AttributeError on fetch_album_songs.
    """
    from musicstreamer import gbs_api as _gbs
    payload = (gbs_fixtures_dir / "album_1488.html").read_bytes()
    monkeypatch.setattr(
        _gbs, "_open_with_cookies",
        lambda url, cookies, timeout=10: _urlopen_factory(payload, content_type="text/html"),
    )
    out = _gbs.fetch_album_songs(1488, fake_cookies_jar)
    assert isinstance(out, dict), f"fetch_album_songs must return dict; got {type(out)}"
    assert "results" in out
    assert isinstance(out["results"], list)
    assert len(out["results"]) >= 1, f"album_1488 fixture has at least 1 row; got {len(out['results'])}"


# ---------- Phase 60.2 / GBS-01e (Wave 0 RED) ----------

def test_artist_page_parses_emits_album_field(gbs_fixtures_dir):
    """Phase 60.2 / GBS-01e (RED): _ArtistPageParser must emit per-row 'album' field
    and group consecutive song rows by album (CONTEXT.md D-01..D-03 + D-10).

    Pins:
      - Every result row has 'album' as a str (possibly empty).
      - Consecutive rows with the same album form a group (preserve fixture order).
      - Brotherhood of the Snake appears in the album set (Testament fixture's first album).
      - Transition count is 13 or 14 (14 albumTitle rows in fixture; 13 transitions if no
        pre-first-albumTitle rows, 14 if pre-first rows exist with album=='').

    FAILS BEFORE Wave 1 parser change lands: rows lack the 'album' field entirely
    (current _ArtistPageParser at gbs_api.py:619 SKIPS albumTitle rows).
    """
    from musicstreamer import gbs_api as _gbs
    payload = (gbs_fixtures_dir / "artist_4803.html").read_text(
        encoding="utf-8", errors="replace",
    )
    parser = _gbs._ArtistPageParser()
    parser.feed(payload)
    parser.close()
    rows = parser.results
    assert len(rows) > 0, "must extract >=1 row"
    # Every row has 'album' as a str
    for row in rows:
        assert "album" in row, f"row missing 'album' field: {row!r}"
        assert isinstance(row["album"], str), (
            f"album must be str; got {type(row['album'])} ({row!r})"
        )
    # At least one known album group is present (Brotherhood of the Snake — first album in fixture)
    albums = {row["album"] for row in rows}
    assert "Brotherhood of the Snake" in albums, (
        f"expected 'Brotherhood of the Snake' album group; got albums {sorted(albums)}"
    )
    # Consecutive rows with same album form a contiguous group: count distinct
    # album-transitions and assert it matches the # of <tr class='albumTitle'> in fixture.
    transitions = sum(
        1 for i in range(1, len(rows)) if rows[i]["album"] != rows[i - 1]["album"]
    )
    # 14 albumTitle rows in artist_4803.html [VERIFIED via grep 2026-05-06].
    # Transitions = (number_of_groups - 1); groups = albumTitle_count if no pre-first rows,
    # else albumTitle_count + 1. Assertion accommodates both cases.
    assert transitions in (13, 14), (
        f"expected 13 or 14 album transitions; got {transitions} "
        f"(14 albumTitle rows in fixture; 13 transitions if no pre-first rows, "
        f"14 if pre-first-albumTitle rows exist with album=='')"
    )


def test_artist_page_pre_first_albumTitle_rows_have_empty_album(gbs_fixtures_dir):
    """Phase 60.2 / GBS-01e (RED): rows before the first <tr class='albumTitle'> must
    carry album == '' per CONTEXT.md D-10.

    For the Testament fixture specifically, there are no SONG rows in that gap, so the
    first emitted row's album is the FIRST albumTitle's text ('Brotherhood of the Snake').
    Defensive assertion: any row with album=='' must be at indices 0..N (contiguous prefix).

    FAILS BEFORE Wave 1 parser change lands: 'album' key does not exist on rows.
    """
    from musicstreamer import gbs_api as _gbs
    payload = (gbs_fixtures_dir / "artist_4803.html").read_text(
        encoding="utf-8", errors="replace",
    )
    parser = _gbs._ArtistPageParser()
    parser.feed(payload)
    parser.close()
    rows = parser.results
    assert len(rows) > 0, "must extract >=1 row"
    # First emitted row must have album == "Brotherhood of the Snake" (first albumTitle in fixture).
    assert rows[0]["album"] == "Brotherhood of the Snake", (
        f"first row's album must be the first albumTitle's text; got {rows[0]['album']!r}"
    )
    # Defensive: any row with album=='' must be at the start (contiguous prefix).
    empty_album_indices = [i for i, r in enumerate(rows) if r["album"] == ""]
    if empty_album_indices:
        assert empty_album_indices == list(range(len(empty_album_indices))), (
            f"empty-album rows must form a contiguous prefix (D-10); "
            f"got indices {empty_album_indices}"
        )


@pytest.mark.parametrize(
    "fixture, expected_artists_count, expected_albums_count, expected_songs_count",
    [
        # Per .planning/.../60.2-01-TRIAGE.md §"Test Parametrize Values":
        # POST-FIX (D-06) expected counts. RED until Wave 1 parser fix lands at gbs_api.py:542-548.
        ("search_bad_religion_p1.html", 1, 1, 8),
        ("search_bad_company_p1.html", 2, 1, 11),
        ("search_iron_maiden_p1.html", 1, 9, 20),
        ("search_black_sabbath_p1.html", 1, 7, 47),
        ("search_death_cab_for_cutie_p1.html", 1, 1, 3),
    ],
)
def test_search_response_shape_pinned(
    gbs_fixtures_dir,
    fixture,
    expected_artists_count,
    expected_albums_count,
    expected_songs_count,
):
    """Phase 60.2 / GBS-01e regression baseline: pin the captured shape of each probe fixture.

    Triage (60.2-01-TRIAGE.md) confirmed H2: _ArtistAlbumParser drops singular-form
    discriminator blocks ('Artist:'/'Album:') because the gate at gbs_api.py:542-548 keys
    on plural startswith('artists')/'albums'. After Wave 1 fix, all 5 entries turn GREEN
    simultaneously.

    Currently RED for all 5 entries (parser returns 0 artists or 0 albums for any fixture
    whose discriminator is singular).

    Pitfall 8: ONE parametrized test, not 5 separate tests. The 4 probe fixtures are triage
    evidence + permanent regression coverage, not separate defect-repro test functions.
    """
    from musicstreamer.gbs_api import _parse_artist_album_html, _SongRowParser

    payload = (gbs_fixtures_dir / fixture).read_text(
        encoding="utf-8", errors="replace",
    )
    artists, albums = _parse_artist_album_html(payload)
    assert len(artists) == expected_artists_count, (
        f"{fixture}: got {len(artists)} artists; expected {expected_artists_count}"
    )
    assert len(albums) == expected_albums_count, (
        f"{fixture}: got {len(albums)} albums; expected {expected_albums_count}"
    )
    sp = _SongRowParser()
    sp.feed(payload)
    sp.close()
    assert len(sp.results) == expected_songs_count, (
        f"{fixture}: got {len(sp.results)} songs; expected {expected_songs_count}"
    )
