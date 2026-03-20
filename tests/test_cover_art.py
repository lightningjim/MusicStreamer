"""Unit tests for musicstreamer.cover_art module."""
import json
import unittest

from musicstreamer.cover_art import is_junk_title, _build_itunes_query, _parse_artwork_url


class TestIsJunkTitle(unittest.TestCase):
    def test_is_junk_title(self):
        self.assertTrue(is_junk_title(""))
        self.assertTrue(is_junk_title("   "))
        self.assertTrue(is_junk_title("Advertisement"))
        self.assertTrue(is_junk_title("commercial break"))
        self.assertTrue(is_junk_title("Advert"))
        self.assertTrue(is_junk_title("Commercial"))
        self.assertFalse(is_junk_title("Bohemian Rhapsody"))


class TestBuildItunesQuery(unittest.TestCase):
    def test_build_itunes_query_artist_title(self):
        url = _build_itunes_query("Queen - Bohemian Rhapsody")
        self.assertIn("term=Queen+Bohemian+Rhapsody", url)
        self.assertIn("media=music", url)
        self.assertIn("limit=1", url)

    def test_build_itunes_query_title_only(self):
        url = _build_itunes_query("Bohemian Rhapsody")
        self.assertIn("term=Bohemian+Rhapsody", url)
        self.assertIn("media=music", url)
        self.assertIn("limit=1", url)


class TestParseArtworkUrl(unittest.TestCase):
    def test_parse_artwork_url(self):
        sample = {
            "resultCount": 1,
            "results": [
                {
                    "artworkUrl100": "https://is1-ssl.mzstatic.com/image/thumb/abc/100x100bb.jpg"
                }
            ]
        }
        result = _parse_artwork_url(json.dumps(sample).encode())
        self.assertIsNotNone(result)
        self.assertIn("160x160", result)
        self.assertNotIn("100x100", result)

    def test_parse_artwork_url_empty(self):
        sample = {"resultCount": 0, "results": []}
        result = _parse_artwork_url(json.dumps(sample).encode())
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
