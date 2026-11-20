# This file is part of the kista Project.
# License: GPL-3.0-or-later. Contact: kista-project@trinity2k.net
#

from typing import ClassVar

import pytest
import requests

from kista import http


class TestBrowserProfile:
    def test_ua_and_client_hints_agree_on_version(self):
        profile = http.browser_profile()
        headers = profile.headers_for("https://example.com/")
        ua = headers["User-Agent"]
        assert f"Chrome/{http.CHROME_VERSION}.0.0.0" in ua
        assert f'"Chromium";v="{http.CHROME_VERSION}"' in headers["sec-ch-ua"]

    def test_platform_consistent_linux(self):
        headers = http.browser_profile().headers_for("https://example.com/")
        assert "X11; Linux x86_64" in headers["User-Agent"]
        assert headers["sec-ch-ua-platform"] == '"Linux"'
        assert headers["sec-ch-ua-mobile"] == "?0"

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
        assert headers["Accept"].startswith("image/jxl")

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

    def test_sec_fetch_site_same_origin_default_port(self):
        headers = http.browser_profile().headers_for(
            "https://example.com:443/b", referer="https://example.com/a"
        )
        assert headers["Sec-Fetch-Site"] == "same-origin"

    def test_sec_fetch_site_different_port_is_same_site(self):
        headers = http.browser_profile().headers_for(
            "https://example.com:8443/b", referer="https://example.com/a"
        )
        assert headers["Sec-Fetch-Site"] == "same-site"

    def test_sec_fetch_site_scheme_mismatch_is_cross_site(self):
        headers = http.browser_profile().headers_for(
            "https://example.com/", referer="http://example.com/"
        )
        assert headers["Sec-Fetch-Site"] == "cross-site"


class TestReferenceCapture:
    # The document comes from Chrome 158 on myip.ch over HTTP/1.1 (Copy as cURL, 2026-11-20);
    # the other kinds come from Chrome 157 over HTTP/2 (2026-11-12), and we assume 158 sends
    # them alike.
    UA_158: ClassVar[str] = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                             "(KHTML, like Gecko) Chrome/158.0.0.0 Safari/537.36")
    CLIENT_HINTS: ClassVar[dict[str, str]] = {
        "sec-ch-ua": '"Chromium";v="158", "Not.A/Brand";v="24", "Google Chrome";v="158"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Linux"',
    }
    DOCUMENT: ClassVar[dict[str, str]] = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/jxl,"
                  "image/avif,image/webp,image/apng,*/*;q=0.8,"
                  "application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": UA_158,
        **CLIENT_HINTS,
    }
    IMAGE: ClassVar[dict[str, str]] = {
        "Accept": "image/jxl,image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://orf.at/",
        "Sec-Fetch-Dest": "image",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "same-site",
        "User-Agent": UA_158,
        **CLIENT_HINTS,
    }

    # The capture omits Cache-Control and Pragma, which DevTools "Disable cache" adds;
    # Sec-Fetch-Storage-Access describes the browser's own cookie state, not Chrome.
    STYLE: ClassVar[dict[str, str]] = {
        "Accept": "text/css,*/*;q=0.1",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.osnews.com/",
        "Sec-Fetch-Dest": "style",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "cross-site",
        "User-Agent": UA_158,
        **CLIENT_HINTS,
    }

    SCRIPT: ClassVar[dict[str, str]] = {
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.osnews.com/",
        "Sec-Fetch-Dest": "script",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "cross-site",
        "User-Agent": UA_158,
        **CLIENT_HINTS,
    }

    # A page's own fetch(). Chrome sent Accept */* because the script set none;
    # kista's api kind asks for JSON on purpose, as a page script calling an API would.
    API: ClassVar[dict[str, str]] = {
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.zoom-platform.com/product/x",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": UA_158,
        **CLIENT_HINTS,
    }

    @staticmethod
    def _sent(url, **kwargs):
        headers = requests.structures.CaseInsensitiveDict(
            http.browser_profile().headers_for(url, **kwargs))
        assert headers.pop("Accept-Encoding") == http.supported_encodings()
        return headers

    def test_a_document_request_matches_the_capture(self):
        sent = self._sent("https://www.dosbox-automation.org/")
        assert dict(sent) == requests.structures.CaseInsensitiveDict(self.DOCUMENT)

    def test_a_style_request_matches_the_capture(self):
        sent = self._sent(
            "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.7.1/css/all.min.css",
            referer="https://www.osnews.com/")
        assert dict(sent) == requests.structures.CaseInsensitiveDict(self.STYLE)

    def test_a_script_request_matches_the_capture(self):
        sent = self._sent("https://www.googletagmanager.com/gtag/js?id=x",
                          kind="script", referer="https://www.osnews.com/")
        assert dict(sent) == requests.structures.CaseInsensitiveDict(self.SCRIPT)

    def test_an_api_request_matches_the_capture(self):
        sent = self._sent("https://www.zoom-platform.com/public/user", kind="api",
                          referer="https://www.zoom-platform.com/product/x")
        assert dict(sent) == requests.structures.CaseInsensitiveDict(self.API)

    def test_an_image_request_matches_the_capture(self):
        sent = self._sent("https://soph-assets.orf.at/sis/image/x/teaser.webp",
                          referer="https://orf.at/")
        assert dict(sent) == requests.structures.CaseInsensitiveDict(self.IMAGE)

    def test_no_priority_over_http11(self):
        for kind in http.KINDS:
            sent = http.browser_profile().headers_for("https://example.com/", kind=kind)
            assert "priority" not in {name.lower() for name in sent}

    def test_header_names_are_spelled_as_captured(self):
        sent = self._sent("https://www.dosbox-automation.org/")
        assert sorted(sent) == sorted(self.DOCUMENT)

    def test_no_cache_headers_absent(self):
        headers = http.browser_profile().headers_for("https://example.com/")
        assert "Cache-Control" not in headers
        assert "Pragma" not in headers

    def test_brotli_advertised_zstd_not(self):
        enc = http.supported_encodings()
        assert "br" in enc
        assert "zstd" not in enc


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
        names = {name.lower() for name in headers}
        assert "sec-ch-ua" not in names
        assert "sec-fetch-dest" not in names

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

    def test_zstd_never_advertised(self, monkeypatch):
        monkeypatch.setattr(http, "_module_available", lambda name: True)
        assert "zstd" not in http.supported_encodings()

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

    def test_browser_profile_does_not_poison_cache(self, tmp_path):
        session = http.cached_session_for(
            http.browser_profile(), "browser-test",
            expire_after=300, cache_dir=tmp_path,
        )
        adapter = _CannedAdapter()
        session.mount("http://", adapter)

        session.get("http://cache.test/page", timeout=5)
        second = session.get("http://cache.test/page", timeout=5)

        assert adapter.calls == 1
        assert getattr(second, "from_cache", False)

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
