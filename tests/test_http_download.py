# This file is part of the kista Project.
# License: GPL-3.0-or-later. Contact: kista-project@trinity2k.net
#

import time
from datetime import UTC, datetime

import pytest
import requests

from kista import http


class FakeResponse:
    def __init__(self, chunks, headers=None, status=200):
        self._chunks = chunks
        self.headers = headers or {}
        self.status_code = status
        self.closed = False

    def iter_content(self, chunk_size):
        yield from self._chunks

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def close(self):
        self.closed = True


class FakeSession:
    def __init__(self, response):
        self._response = response
        self.last_kwargs = None

    def get(self, url, **kwargs):
        self.last_kwargs = kwargs
        return self._response


class TestDownload:
    def test_writes_streamed_content(self, tmp_path):
        resp = FakeResponse([b"abc", b"def"])
        dest = tmp_path / "file.bin"
        result = http.download(FakeSession(resp), "https://x.example/f", dest, timeout=5)
        assert dest.read_bytes() == b"abcdef"
        assert result.path == dest
        assert result.size_bytes == 6
        assert resp.closed

    def test_stamps_last_modified(self, tmp_path):
        resp = FakeResponse(
            [b"x"], headers={"Last-Modified": "Wed, 21 Oct 2015 07:28:00 GMT"}
        )
        dest = tmp_path / "file.bin"
        result = http.download(FakeSession(resp), "https://x.example/f", dest, timeout=5)
        expected = datetime(2015, 10, 21, 7, 28, tzinfo=UTC)
        assert result.last_modified == expected
        assert int(dest.stat().st_mtime) == int(expected.timestamp())

    def test_no_last_modified_keeps_result_none(self, tmp_path):
        dest = tmp_path / "f"
        result = http.download(FakeSession(FakeResponse([b"x"])), "https://x/f", dest, timeout=5)
        assert result.last_modified is None

    def test_http_error_leaves_no_file(self, tmp_path):
        resp = FakeResponse([b"nope"], status=503)
        dest = tmp_path / "file.bin"
        with pytest.raises(requests.HTTPError):
            http.download(FakeSession(resp), "https://x.example/f", dest, timeout=5)
        assert list(tmp_path.iterdir()) == []

    def test_mid_stream_failure_leaves_no_partial(self, tmp_path):
        def broken():
            yield b"start"
            raise requests.ConnectionError("died")

        resp = FakeResponse(broken())
        dest = tmp_path / "file.bin"
        with pytest.raises(requests.ConnectionError):
            http.download(FakeSession(resp), "https://x.example/f", dest, timeout=5)
        assert list(tmp_path.iterdir()) == []

    def test_refuses_overwrite(self, tmp_path):
        dest = tmp_path / "file.bin"
        dest.write_bytes(b"old")
        with pytest.raises(FileExistsError):
            http.download(FakeSession(FakeResponse([b"new"])), "https://x/f", dest, timeout=5)
        assert dest.read_bytes() == b"old"

    def test_timeout_is_mandatory_and_forwarded(self, tmp_path):
        session = FakeSession(FakeResponse([b"x"]))
        http.download(session, "https://x/f", tmp_path / "f", timeout=7)
        assert session.last_kwargs["timeout"] == 7
        assert session.last_kwargs["stream"] is True

    def test_identity_encoding_sent(self, tmp_path):
        session = FakeSession(FakeResponse([b"x"]))
        http.download(session, "https://x/f", tmp_path / "f", timeout=5)
        assert session.last_kwargs["headers"]["Accept-Encoding"] == "identity"

    def test_caller_headers_cannot_override_identity(self, tmp_path):
        session = FakeSession(FakeResponse([b"x"]))
        http.download(
            session, "https://x/f", tmp_path / "f", timeout=5,
            headers={"Accept-Encoding": "gzip, deflate, br"},
        )
        assert session.last_kwargs["headers"]["Accept-Encoding"] == "identity"

    def test_dangling_symlink_refused(self, tmp_path):
        dest = tmp_path / "link"
        dest.symlink_to(tmp_path / "nonexistent")
        with pytest.raises(FileExistsError):
            http.download(FakeSession(FakeResponse([b"x"])), "https://x/f", dest, timeout=5)


class TestDelay:
    def test_single_value(self):
        assert http.parse_delay("3") == (3.0, 3.0)

    def test_range(self):
        assert http.parse_delay("2-5") == (2.0, 5.0)

    def test_reversed_range_rejected(self):
        with pytest.raises(ValueError):
            http.parse_delay("5-2")

    def test_negative_rejected(self):
        with pytest.raises(ValueError):
            http.parse_delay("-3")

    def test_garbage_rejected(self):
        with pytest.raises(ValueError):
            http.parse_delay("soon")

    @pytest.mark.parametrize("spec", ["nan", "inf", "-inf", "0-inf"])
    def test_nan_inf_rejected(self, spec):
        with pytest.raises(ValueError):
            http.parse_delay(spec)

    def test_sleep_jitter_within_range(self, monkeypatch):
        slept = []
        monkeypatch.setattr(time, "sleep", lambda s: slept.append(s))
        http.sleep_jitter((1.0, 2.0))
        assert len(slept) == 1
        assert 1.0 <= slept[0] <= 2.0


class FakeHeadSession:
    def __init__(self, headers, status=200):
        self._headers = headers
        self._status = status
        self.last_kwargs = None

    def head(self, url, **kwargs):
        self.last_kwargs = kwargs
        resp = FakeResponse([], headers=self._headers, status=self._status)
        return resp


class TestHeadInfo:
    def test_reads_size_mtime_etag(self):
        session = FakeHeadSession({
            "Content-Length": "1234",
            "Last-Modified": "Wed, 21 Oct 2015 07:28:00 GMT",
            "ETag": '"abc"',
        })
        info = http.head_info(session, "https://x.example/f", timeout=5)
        assert info.size_bytes == 1234
        assert info.last_modified is not None
        assert info.etag == '"abc"'
        assert session.last_kwargs["allow_redirects"] is True

    def test_missing_headers_are_none(self):
        info = http.head_info(FakeHeadSession({}), "https://x/f", timeout=5)
        assert info.size_bytes is None
        assert info.last_modified is None
        assert info.etag is None

    def test_last_modified_is_always_tz_aware(self):
        session = FakeHeadSession({
            "Last-Modified": "Wed, 21 Oct 2015 07:28:00 GMT",
        })
        info = http.head_info(session, "https://x/f", timeout=5)
        assert info.last_modified is not None
        assert info.last_modified.tzinfo is not None

    def test_error_status_raises(self):
        with pytest.raises(requests.HTTPError):
            http.head_info(FakeHeadSession({}, status=404), "https://x/f", timeout=5)


class TestCookies:
    def test_roundtrip(self, tmp_path):
        jar_path = tmp_path / "cookies.txt"
        session = requests.Session()
        session.cookies.set("token", "abc123", domain="example.com", path="/")
        http.save_cookies(session, jar_path)

        fresh = requests.Session()
        http.load_cookies(fresh, jar_path)
        assert fresh.cookies.get("token", domain="example.com") == "abc123"

    def test_load_missing_file_fails_loudly(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            http.load_cookies(requests.Session(), tmp_path / "ghost.txt")
