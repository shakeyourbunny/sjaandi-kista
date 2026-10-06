# This file is part of the kista Project.
# License: GPL-3.0-or-later. Contact: kista-project@trinity2k.net
#

import pytest

from kista import urls


class TestCleanScrapedUrl:
    def test_quotes_and_whitespace_stripped(self):
        assert urls.clean_scraped_url(' "https://example.com/a" ') == "https://example.com/a"

    def test_brackets_stripped(self):
        assert urls.clean_scraped_url("[https://example.com/a]") == "https://example.com/a"

    def test_fragment_dropped(self):
        assert urls.clean_scraped_url("https://example.com/a#section") == "https://example.com/a"

    def test_unencoded_spaces_encoded(self):
        assert urls.clean_scraped_url("https://example.com/a b") == "https://example.com/a%20b"

    def test_protocol_relative_becomes_https(self):
        assert urls.clean_scraped_url("//cdn.example.com/x.js") == "https://cdn.example.com/x.js"

    def test_encoded_scheme_colon_fixed(self):
        assert urls.clean_scraped_url("https%3A//example.com/a") == "https://example.com/a"

    def test_relative_resolved_against_base(self):
        assert urls.clean_scraped_url(
            "sub/page.html", base="https://example.com/dir/"
        ) == "https://example.com/dir/sub/page.html"

    def test_root_relative_resolved_against_base(self):
        assert urls.clean_scraped_url(
            "/about", base="https://example.com/dir/page"
        ) == "https://example.com/about"

    def test_absolute_ignores_base(self):
        assert urls.clean_scraped_url(
            "https://other.net/x", base="https://example.com/"
        ) == "https://other.net/x"

    def test_magnet_passthrough(self):
        magnet = "magnet:?xt=urn:btih:abc"
        assert urls.clean_scraped_url(magnet) == magnet

    def test_ftp_passthrough(self):
        assert urls.clean_scraped_url("ftp://ftp.example.com/f") == "ftp://ftp.example.com/f"

    def test_relative_without_base_rejected(self):
        with pytest.raises(ValueError):
            urls.clean_scraped_url("sub/page.html")

    def test_empty_rejected(self):
        with pytest.raises(ValueError):
            urls.clean_scraped_url("   ")

    @pytest.mark.parametrize("url", [
        "javascript:alert(1)",
        "data:text/html,<h1>hi</h1>",
        "vbscript:MsgBox",
        "file:///etc/passwd",
        "blob:https://x/1",
    ])
    def test_disallowed_schemes_rejected(self, url):
        with pytest.raises(ValueError, match="scheme not allowed"):
            urls.clean_scraped_url(url)

    def test_encoded_scheme_does_not_decode_path(self):
        result = urls.clean_scraped_url("http%3a//example.com/path%3amore")
        assert result == "http://example.com/path%3amore"

    def test_file_base_does_not_leak(self):
        with pytest.raises(ValueError, match="disallowed scheme"):
            urls.clean_scraped_url("passwd", base="file:///etc/")