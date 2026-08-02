# This file is part of the kista Project.
# License: GPL-3.0-or-later. Contact: kista-project@trinity2k.net
#

import pytest
import requests

from kista import http


class TestBrowserProfile:
    def test_ua_and_client_hints_agree_on_version(self):
        profile = http.browser_profile()
        headers = profile.headers_for("https://example.com/")
        ua = headers["User-Agent"]
        assert f"Chrome/{http.CHROME_VERSION}.0.0.0" in ua
        assert f'"Chromium";v="{http.CHROME_VERSION}"' in headers["Sec-Ch-Ua"]

    def test_platform_consistent_linux(self):
        headers = http.browser_profile().headers_for("https://example.com/")
        assert "X11; Linux x86_64" in headers["User-Agent"]
        assert headers["Sec-Ch-Ua-Platform"] == '"Linux"'
        assert headers["Sec-Ch-Ua-Mobile"] == "?0"

    def test_document_kind_headers(self):
        headers = http.browser_profile().headers_for("https://example.com/page")
        assert headers["Sec-Fetch-Dest"] == "document"
        assert headers["Sec-Fetch-Mode"] == "navigate"
        assert headers["Sec-Fetch-User"] == "?1"
        assert headers["Accept"].startswith("text/html")
        assert headers["Upgrade-Insecure-Requests"] == "1"

    def test_style_kind_from_extension(self):
        headers = http.browser_profile().headers_for("https://example.com/a/index.css")
        assert headers["Sec-Fetch-Dest"] == "style"
        assert headers["Sec-Fetch-Mode"] == "no-cors"
        assert headers["Accept"] == "text/css,*/*;q=0.1"
        assert "Upgrade-Insecure-Requests" not in headers

    def test_image_kind_from_extension(self):
        headers = http.browser_profile().headers_for("https://example.com/logo.png")
        assert headers["Sec-Fetch-Dest"] == "image"
        assert headers["Accept"].startswith("image/avif")

    def test_explicit_kind_overrides_extension(self):
        headers = http.browser_profile().headers_for(
            "https://example.com/logo.png", kind="document"
        )
        assert headers["Sec-Fetch-Dest"] == "document"

    def test_feed_kind_accept(self):
        headers = http.browser_profile().headers_for(
            "https://example.com/feed", kind="feed"
        )
        assert "application/rss+xml" in headers["Accept"]
        assert "application/atom+xml" in headers["Accept"]

    def test_sec_fetch_site_none_without_referer(self):
        headers = http.browser_profile().headers_for("https://example.com/")
        assert headers["Sec-Fetch-Site"] == "none"
        assert "Referer" not in headers

    def test_sec_fetch_site_same_origin(self):
        headers = http.browser_profile().headers_for(
            "https://example.com/b", referer="https://example.com/a"
        )
        assert headers["Sec-Fetch-Site"] == "same-origin"
        assert headers["Referer"] == "https://example.com/a"

    def test_sec_fetch_site_same_site(self):
        headers = http.browser_profile().headers_for(
            "https://speedy.example.com/x.css", referer="https://www.example.com/"
        )
        assert headers["Sec-Fetch-Site"] == "same-site"

    def test_sec_fetch_site_cross_site(self):
        headers = http.browser_profile().headers_for(
            "https://other.net/", referer="https://example.com/"
        )
        assert headers["Sec-Fetch-Site"] == "cross-site"


class TestToolProfile:
    def test_ua_with_contact(self):
        profile = http.tool_profile("appskap", "0.1.0", contact="kista-project@trinity2k.net")
        headers = profile.headers_for("https://api.github.com/repos", kind="api")
        assert headers["User-Agent"] == "appskap/0.1.0 (kista-project@trinity2k.net)"

    def test_ua_without_contact(self):
        profile = http.tool_profile("mytool", "2.0")
        headers = profile.headers_for("https://example.com/")
        assert headers["User-Agent"] == "mytool/2.0"

    def test_api_kind_accepts_json(self):
        headers = http.tool_profile("t", "1").headers_for(
            "https://api.example.com/v1", kind="api"
        )
        assert headers["Accept"] == "application/json"

    def test_no_browser_theater(self):
        headers = http.tool_profile("t", "1").headers_for("https://example.com/")
        assert "Sec-Ch-Ua" not in headers
        assert "Sec-Fetch-Dest" not in headers

    def test_empty_name_rejected(self):
        with pytest.raises(ValueError):
            http.tool_profile("", "1.0")


class TestEncodings:
    def test_gzip_always_advertised(self):
        assert "gzip" in http.supported_encodings()

    def test_only_decodable_encodings(self, monkeypatch):
        monkeypatch.setattr(http, "_module_available", lambda name: False)
        encs = http.supported_encodings()
        assert "br" not in encs
        assert "zstd" not in encs
        assert "gzip" in encs

    def test_zstd_advertised_when_available(self, monkeypatch):
        monkeypatch.setattr(http, "_module_available", lambda name: True)
        assert "zstd" in http.supported_encodings()

    def test_profiles_use_supported_encodings(self):
        headers = http.browser_profile().headers_for("https://example.com/")
        assert headers["Accept-Encoding"] == http.supported_encodings()


class TestValidation:
    def test_empty_url_rejected(self):
        with pytest.raises(ValueError):
            http.browser_profile().headers_for("")

    def test_unknown_kind_rejected(self):
        with pytest.raises(ValueError):
            http.browser_profile().headers_for("https://example.com/", kind="dance")


class TestSession:
    def test_session_carries_identity(self):
        session = http.session_for(http.browser_profile())
        assert f"Chrome/{http.CHROME_VERSION}.0.0.0" in session.headers["User-Agent"]

    def test_tool_session_carries_identity(self):
        session = http.session_for(http.tool_profile("t", "1.0"))
        assert session.headers["User-Agent"] == "t/1.0"


class _CannedAdapter(requests.adapters.HTTPAdapter):

    def __init__(self):
        super().__init__()
        self.calls = 0

    def send(self, request, **kwargs):
        import io

        import urllib3

        self.calls += 1
        raw = urllib3.HTTPResponse(
            body=io.BytesIO(b"hello"),
            status=200,
            headers={"Cache-Control": "max-age=300"},
            preload_content=False,
        )
        return self.build_response(request, raw)


class TestCachedSession:
    def test_rejects_non_profile(self, tmp_path):
        with pytest.raises(TypeError):
            http.cached_session_for("no", "t", expire_after=60, cache_dir=tmp_path)

    def test_rejects_empty_cache_name(self, tmp_path):
        with pytest.raises(ValueError):
            http.cached_session_for(
                http.tool_profile("t", "1.0"), "  ",
                expire_after=60, cache_dir=tmp_path,
            )

    def test_carries_identity_headers(self, tmp_path):
        session = http.cached_session_for(
            http.tool_profile("t", "1.0"), "t",
            expire_after=60, cache_dir=tmp_path,
        )
        assert session.headers["User-Agent"] == "t/1.0"

    def test_cache_file_lives_in_cache_dir(self, tmp_path):
        http.cached_session_for(
            http.tool_profile("t", "1.0"), "t",
            expire_after=60, cache_dir=tmp_path,
        )
        assert (tmp_path / "http-cache.sqlite").is_file()

    def test_second_get_served_from_cache(self, tmp_path):
        session = http.cached_session_for(
            http.tool_profile("t", "1.0"), "t",
            expire_after=300, cache_dir=tmp_path,
        )
        adapter = _CannedAdapter()
        session.mount("http://", adapter)

        first = session.get("http://cache.test/data", timeout=5)
        second = session.get("http://cache.test/data", timeout=5)

        assert first.content == b"hello"
        assert second.content == b"hello"
        assert adapter.calls == 1
        assert getattr(second, "from_cache", False)

    def test_server_max_age_does_not_override_ttl(self, tmp_path):
        # GitHub sends max-age=60; the caller's expire_after must win
        # or the cache is useless for API crawls
        import io

        import urllib3

        class ShortMaxAgeAdapter(requests.adapters.HTTPAdapter):
            def __init__(self):
                super().__init__()
                self.calls = 0

            def send(self, request, **kwargs):
                self.calls += 1
                raw = urllib3.HTTPResponse(
                    body=io.BytesIO(b"data"),
                    status=200,
                    headers={"Cache-Control": "private, max-age=0"},
                    preload_content=False,
                )
                return self.build_response(request, raw)

        session = http.cached_session_for(
            http.tool_profile("t", "1.0"), "t",
            expire_after=300, cache_dir=tmp_path,
        )
        adapter = ShortMaxAgeAdapter()
        session.mount("http://", adapter)

        session.get("http://cache.test/api", timeout=5)
        second = session.get("http://cache.test/api", timeout=5)
        assert adapter.calls == 1
        assert getattr(second, "from_cache", False)
