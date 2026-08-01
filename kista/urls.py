# This file is part of the kista Project.
# License: GPL-3.0-or-later. Contact: kista-project@trinity2k.net
#
# Generic core of rssmailfeedr's fixup_domain (same author, same
# license); the domain-specific hacks stayed there.

from __future__ import annotations

from urllib.parse import urljoin, urlparse

# Schemes passed through untouched once cleaned.
_KNOWN_SCHEMES = ("http://", "https://", "ftp://", "magnet:")


def clean_scraped_url(url: str, base: str | None = None) -> str:
    """Normalize a URL as found in scraped HTML or feed payloads.

    Strips wrapping junk (quotes, brackets, whitespace), drops the
    fragment, encodes bare spaces, upgrades protocol-relative URLs to
    https, and resolves relative URLs against base. Relative input
    without a base is an error, not a guess.
    """
    if not url or not url.strip():
        raise ValueError("url must not be empty")
    url = url.strip().strip("\"'")
    url = url.removeprefix("[")
    url = url.removesuffix("]")
    url = url.split("#")[0]
    url = url.replace(" ", "%20")

    # Scraped hrefs sometimes carry an entity-encoded scheme colon
    if url[:9].lower() in ("http%3a//", "https%3a/"):
        url = url.replace("%3A", ":", 1).replace("%3a", ":", 1)

    if url.startswith("//"):
        url = f"https:{url}"

    if url.lower().startswith(_KNOWN_SCHEMES):
        return url

    if urlparse(url).scheme:
        return url

    if base is None:
        raise ValueError(f"relative url needs a base: {url!r}")
    return urljoin(base, url)
