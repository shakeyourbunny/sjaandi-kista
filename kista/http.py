# This file is part of the kista Project.
# License: GPL-3.0-or-later. Contact: kista-project@trinity2k.net
#
# Header engine adapted from webfetch.py in the gamefaq-collector
# project (same author, same license).

from __future__ import annotations

import importlib.util
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import urlparse

import requests

# One pinned browser identity. Bumping this constant moves the UA
# string and Sec-Ch-Ua together; nothing else may hardcode a version.
CHROME_VERSION = "150"

# GREASE brand as captured from a real Chrome 150 on Linux
# (DevTools reference capture, 2026-08-01).
_SEC_CH_UA = f'"Not:A-Brand";v="8", "Chromium";v="{CHROME_VERSION}"'

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

    Advertising an encoding and choking on the response is worse than
    omitting it - br and zstd are included only if their decoders are
    importable.
    """
    encodings = ["gzip", "deflate"]
    if _module_available("brotli") or _module_available("brotlicffi"):
        encodings.append("br")
    if _module_available("zstandard"):
        encodings.append("zstd")
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
    # Last two labels as a cheap eTLD+1; good enough for the
    # same-site decision on the sites the house actually fetches.
    return ".".join(netloc.rsplit(".", 2)[-2:])


def _sec_fetch_site(url: str, referer: str | None) -> str:
    if not referer:
        return "none"
    target, source = urlparse(url), urlparse(referer)
    if target.netloc == source.netloc:
        return "same-origin"
    if _registrable_domain(target.netloc) == _registrable_domain(source.netloc):
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
