# This file is part of the kista Project.
# License: GPL-3.0-or-later. Contact: kista-project@trinity2k.net
#
# Generic core of rssmailfeedr's fixup_domain (same author, same
# license); the domain-specific hacks stayed there.

from __future__ import annotations

from urllib.parse import urljoin, urlparse

# Schemes passed through untouched once cleaned.
_KNOWN_SCHEMES = ("http://", "https://", "ftp://", "magnet:")
_ALLOWED_SCHEMES = frozenset({"http", "https", "ftp", "magnet"})


def clean_scraped_url(url: str, base: str | None = None) -> str:
    """Normalize a URL as found in scraped HTML or feed payloads.

    Strips wrapping junk (quotes, brackets, whitespace), drops the
    fragment, encodes bare spaces, upgrades protocol-relative URLs to
    https, and resolves relative URLs against base. Relative input
    without a base is an error, not a guess. Only http, https, ftp
    and magnet schemes are accepted.
    """
    if not url or not url.strip():
        raise ValueError("url must not be empty")
    url = url.strip().strip("\"'")
    url = url.removeprefix("[")
    url = url.removesuffix("]")
    url = url.split("#")[0]
    url = url.replace(" ", "%20")

    # Scraped hrefs sometimes carry an entity-encoded scheme colon;
    # only fix it at the actual scheme position, not deeper in the URL.
    lower9 = url[:9].lower()
    if lower9.startswith("http%3a//"):
        url = url[:4] + ":" + url[7:]
    elif lower9.startswith("https%3a/"):
        url = url[:5] + ":" + url[8:]

    if url.startswith("//"):
        url = f"https:{url}"

    if url.lower().startswith(_KNOWN_SCHEMES):
        return url

    scheme = urlparse(url).scheme.lower()
    if scheme and scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"scheme not allowed: {scheme}:")
    if scheme:
        return url

    if base is None:
        raise ValueError(f"relative url needs a base: {url!r}")
    base_scheme = urlparse(base).scheme.lower()
    if base_scheme and base_scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"base has disallowed scheme: {base_scheme}:")
    result = urljoin(base, url)
    result_scheme = urlparse(result).scheme.lower()
    if not result_scheme or result_scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"resolved URL has no allowed scheme: {result!r}")
    return result
