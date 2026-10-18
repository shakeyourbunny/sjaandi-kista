# This file is part of the kista Project.
# License: GPL-3.0-or-later. Contact: kista-project@trinity2k.net
#
# Header engine adapted from webfetch.py in the gamefaq-collector
# project (same author, same license).

from __future__ import annotations

import http.cookiejar
import importlib.util
import logging
import math
import os
import random
import tempfile
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

import requests

from kista import fileops

logger = logging.getLogger(__name__)

# One pinned browser identity. Bumping this constant moves the UA
# string and Sec-Ch-Ua together; nothing else may hardcode a version.
CHROME_VERSION = "152"

# GREASE brand for Chromium 152 (captured from Vivaldi 8.2, Linux,
# 2026-10-04). The brand string and v= change with CHROME_VERSION -
# update both together.
_SEC_CH_UA = f'"Not?A_Brand";v="24", "Chromium";v="{CHROME_VERSION}"'

_UA_BROWSER = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    f"(KHTML, like Gecko) Chrome/{CHROME_VERSION}.0.0.0 Safari/537.36"
)

KINDS = ("document", "feed", "image", "style", "script", "api")

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".svg", ".avif"}
_STYLE_EXTS = {".css"}
_SCRIPT_EXTS = {".js", ".mjs"}

_ACCEPT = {
    "document": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,"
        "application/signed-exchange;v=b3;q=0.7"
    ),
    "feed": (
        "application/rss+xml,application/atom+xml,"
        "application/feed+json,application/xml;q=0.9,*/*;q=0.8"
    ),
    "image": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    "style": "text/css,*/*;q=0.1",
    "script": "*/*",
    "api": "application/json",
}


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def supported_encodings() -> str:
    """Accept-Encoding value listing only what the runtime can decode.

    br is included only if a decoder is importable.
    zstd omitted: urllib3 needs compression.zstd, not zstandard.
    """
    encodings = ["gzip", "deflate"]
    if _module_available("brotli") or _module_available("brotlicffi"):
        encodings.append("br")
    return ", ".join(encodings)


def _guess_kind(url: str) -> str:
    ext = PurePosixPath(urlparse(url).path).suffix.lower()
    if ext in _IMAGE_EXTS:
        return "image"
    if ext in _STYLE_EXTS:
        return "style"
    if ext in _SCRIPT_EXTS:
        return "script"
    return "document"


def _registrable_domain(netloc: str) -> str:
    # Last two labels as a cheap eTLD+1; sufficient for same-site decisions.
    return ".".join(netloc.rsplit(".", 2)[-2:])


_DEFAULT_PORTS = {"http": 80, "https": 443, "ftp": 21}


def _effective_port(parsed) -> int | None:
    try:
        if parsed.port is not None:
            return parsed.port
    except ValueError:
        return None
    return _DEFAULT_PORTS.get(parsed.scheme)


def _sec_fetch_site(url: str, referer: str | None) -> str:
    if not referer:
        return "none"
    target, source = urlparse(url), urlparse(referer)
    t_host = target.hostname or ""
    s_host = source.hostname or ""
    if (target.scheme == source.scheme
            and t_host == s_host
            and _effective_port(target) == _effective_port(source)):
        return "same-origin"
    if (target.scheme == source.scheme
            and _registrable_domain(t_host) == _registrable_domain(s_host)):
        return "same-site"
    return "cross-site"


def _validate(url: str, kind: str | None) -> str:
    if not url or not url.strip():
        raise ValueError("url must not be empty")
    if kind is None:
        return _guess_kind(url)
    if kind not in KINDS:
        raise ValueError(f"unknown request kind: {kind!r} (known: {', '.join(KINDS)})")
    return kind


class Profile(ABC):
    """A complete, internally consistent HTTP request identity."""

    @abstractmethod
    def identity_headers(self) -> dict[str, str]:
        """Static headers that identify the client, for session defaults."""

    @abstractmethod
    def headers_for(
        self, url: str, kind: str | None = None, referer: str | None = None
    ) -> dict[str, str]:
        """Full header set for one request; kind is guessed from the URL if omitted."""


@dataclass(frozen=True)
class BrowserProfile(Profile):
    """Pinned Chrome-on-Linux ensemble: UA, client hints and Sec-Fetch
    headers all agree with each other and vary by resource kind."""

    def identity_headers(self) -> dict[str, str]:
        return {
            "User-Agent": _UA_BROWSER,
            "Sec-Ch-Ua": _SEC_CH_UA,
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Linux"',
            "Accept-Language": "en",
            "Accept-Encoding": supported_encodings(),
        }

    def headers_for(
        self, url: str, kind: str | None = None, referer: str | None = None
    ) -> dict[str, str]:
        kind = _validate(url, kind)
        headers = self.identity_headers()
        headers["Accept"] = _ACCEPT[kind]
        if kind in ("document", "feed"):
            headers["Sec-Fetch-Dest"] = "document"
            headers["Sec-Fetch-Mode"] = "navigate"
            headers["Sec-Fetch-User"] = "?1"
            headers["Upgrade-Insecure-Requests"] = "1"
        elif kind == "api":
            headers["Sec-Fetch-Dest"] = "empty"
            headers["Sec-Fetch-Mode"] = "cors"
        else:
            headers["Sec-Fetch-Dest"] = kind
            headers["Sec-Fetch-Mode"] = "no-cors"
        headers["Sec-Fetch-Site"] = _sec_fetch_site(url, referer)
        if referer:
            headers["Referer"] = referer
        return headers


@dataclass(frozen=True)
class ToolProfile(Profile):
    """Honest tool identity: name/version, optional contact, no
    browser theater. The right choice for APIs like GitHub or pkgforge."""

    tool_name: str
    version: str
    contact: str | None = None

    def __post_init__(self):
        if not self.tool_name or not self.tool_name.strip():
            raise ValueError("tool_name must not be empty")
        if not self.version or not self.version.strip():
            raise ValueError("version must not be empty")

    def identity_headers(self) -> dict[str, str]:
        ua = f"{self.tool_name}/{self.version}"
        if self.contact:
            ua += f" ({self.contact})"
        return {
            "User-Agent": ua,
            "Accept-Encoding": supported_encodings(),
        }

    def headers_for(
        self, url: str, kind: str | None = None, referer: str | None = None
    ) -> dict[str, str]:
        kind = _validate(url, kind)
        headers = self.identity_headers()
        headers["Accept"] = _ACCEPT[kind] if kind == "api" else "*/*"
        if referer:
            headers["Referer"] = referer
        return headers


def browser_profile() -> BrowserProfile:
    return BrowserProfile()


def tool_profile(name: str, version: str, contact: str | None = None) -> ToolProfile:
    return ToolProfile(tool_name=name, version=version, contact=contact)


def session_for(profile: Profile) -> requests.Session:
    """A requests.Session preloaded with the profile's identity headers.

    Retries and timeouts stay caller policy - pass a timeout on every
    request; this deliberately configures none.
    """
    if not isinstance(profile, Profile):
        raise TypeError(f"expected a Profile, got {type(profile).__name__}")
    session = requests.Session()
    session.headers.update(profile.identity_headers())
    return session


def cached_session_for(
    profile: Profile,
    cache_name: str,
    *,
    expire_after: float | timedelta,
    cache_dir: str | Path | None = None,
) -> requests.Session:
    """Backed by requests-cache (SQLite). The caller's expire_after is
    authoritative - server Cache-Control is ignored, because API hosts
    like GitHub send max-age=60 and would gut the cache (measured:
    915 of 924 entries stale). After the TTL, entries with ETag or
    Last-Modified revalidate conditionally; a GitHub 304 costs no
    rate-limit quota. Needs the optional requests-cache dependency
    (install kista[cache]).

    cache_dir defaults to the platform user cache dir for cache_name.
    Timeouts stay caller policy, same as session_for.
    """
    if not isinstance(profile, Profile):
        raise TypeError(f"expected a Profile, got {type(profile).__name__}")
    if not cache_name or not cache_name.strip():
        raise ValueError("cache_name must not be empty")

    try:
        import requests_cache  # optional dependency, deferred
    except ImportError as e:
        raise ImportError(
            "requests-cache is not installed - install the kista[cache] extra"
        ) from e

    if cache_dir is None:
        # platformdirs comes in transitively with requests-cache
        from platformdirs import user_cache_dir
        cache_dir = Path(user_cache_dir(cache_name))
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    session = requests_cache.CachedSession(
        str(cache_dir / "http-cache.sqlite"),
        backend="sqlite",
        expire_after=expire_after,
        cache_control=False,
        allowable_methods=("GET", "HEAD"),
    )
    session.headers.update(profile.identity_headers())
    return session


@dataclass(frozen=True, slots=True)
class DownloadResult:
    path: Path
    size_bytes: int
    last_modified: datetime | None


def download(
    session,
    url: str,
    dest: str | Path,
    *,
    timeout: float,
    headers: dict[str, str] | None = None,
    chunk_size: int = 65536,
    on_progress: callable | None = None,
) -> DownloadResult:
    """Stream url to dest: temp file + atomic rename, mtime stamped
    from Last-Modified. Refuses to overwrite; a failed transfer leaves
    nothing behind.

    on_progress(received_bytes, total_bytes_or_none) is called after
    each chunk when provided.
    """
    if not url or not url.strip():
        raise ValueError("url must not be empty")
    dest = Path(dest)
    if dest.exists():
        raise FileExistsError(f"target already exists: {dest}")

    response = session.get(url, headers=headers, timeout=timeout, stream=True)
    try:
        response.raise_for_status()
        size = 0
        total = None
        length = response.headers.get("Content-Length")
        if length is not None:
            try:
                total = int(length)
            except ValueError:
                pass
        fd, tmp_name = tempfile.mkstemp(dir=dest.parent, prefix=f".{dest.name}.")
        try:
            with os.fdopen(fd, "wb") as f:
                for chunk in response.iter_content(chunk_size):
                    f.write(chunk)
                    size += len(chunk)
                    if on_progress:
                        on_progress(size, total)
                f.flush()
                os.fsync(f.fileno())
            os.chmod(tmp_name, 0o644)
            os.replace(tmp_name, dest)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
    finally:
        response.close()

    last_modified = fileops.stamp_http_mtime(dest, response.headers.get("Last-Modified", ""))
    return DownloadResult(path=dest, size_bytes=size, last_modified=last_modified)


@dataclass(frozen=True, slots=True)
class RemoteInfo:
    size_bytes: int | None
    last_modified: datetime | None
    etag: str | None


def head_info(session, url: str, *, timeout: float,
              headers: dict[str, str] | None = None) -> RemoteInfo:
    """Size, mtime and ETag of a remote file via HEAD request."""
    if not url or not url.strip():
        raise ValueError("url must not be empty")
    response = session.head(url, headers=headers, timeout=timeout, allow_redirects=True)
    response.raise_for_status()

    size = None
    length_header = response.headers.get("Content-Length")
    if length_header is not None:
        try:
            size = int(length_header)
        except ValueError:
            logger.warning("Non-numeric Content-Length %r for %s", length_header, url)

    last_modified = None
    lm_header = response.headers.get("Last-Modified")
    if lm_header:
        try:
            last_modified = parsedate_to_datetime(lm_header)
        except (ValueError, TypeError):
            logger.warning("Unparseable Last-Modified %r for %s", lm_header, url)
    return RemoteInfo(
        size_bytes=size,
        last_modified=last_modified,
        etag=response.headers.get("ETag"),
    )


def parse_delay(spec: str) -> tuple[float, float]:
    """Parse a politeness delay spec: "3" or a "2-5" range, seconds."""
    if not spec or not spec.strip():
        raise ValueError("delay spec must not be empty")
    spec = spec.strip()
    try:
        # A dash past position 0 is a range separator; at position 0
        # it is a (rejected) negative sign.
        if "-" in spec[1:]:
            low_raw, high_raw = spec[1:].split("-", 1)
            low, high = float(spec[0] + low_raw), float(high_raw)
        else:
            low = high = float(spec)
    except ValueError:
        raise ValueError(f"invalid delay spec: {spec!r}") from None
    if not (math.isfinite(low) and math.isfinite(high)):
        raise ValueError(f"delay must be finite: {spec!r}")
    if low < 0 or high < 0:
        raise ValueError(f"delay must not be negative: {spec!r}")
    if high < low:
        raise ValueError(f"delay range is reversed: {spec!r}")
    return low, high


def sleep_jitter(delay: tuple[float, float]) -> None:
    low, high = delay
    wait = random.uniform(low, high)  # nosec B311 - politeness jitter, not crypto
    if wait > 1:
        logger.debug("politeness delay: %.1fs", wait)
    time.sleep(wait)


def load_cookies(session: requests.Session, path: str | Path) -> None:
    """Load a Mozilla-format cookie jar into the session; missing
    file fails loudly."""
    jar = http.cookiejar.MozillaCookieJar(str(path))
    jar.load(ignore_discard=True, ignore_expires=True)
    session.cookies.update(jar)


def save_cookies(session: requests.Session, path: str | Path) -> None:
    jar = http.cookiejar.MozillaCookieJar(str(path))
    for cookie in session.cookies:
        jar.set_cookie(cookie)
    jar.save(ignore_discard=True, ignore_expires=True)
