# This file is part of the kista Project.
# License: GPL-3.0-or-later. Contact: kista-project@trinity2k.net
#
# Generalized from litcollect's mirror.py (same author, same license).
#
# Two distinct jobs:
#   slugify()               -> ASCII machine key ([a-z0-9_]), e.g. GOG slugs.
#                              Transliterates everything down; NOT a filename.
#   sanitize_filename()     -> human-readable name, native script PRESERVED,
#   sanitize_path_component()  but every Unicode *hazard* neutralized.
#   windows_safe()          -> stdlib-only fast path, same invariants,
#                              no pathvalidate / no transliteration.
#
# "Prevent the Unicode games, don't force ASCII" means, for the filename
# side: NFKC fold, strip the invisible/format/control/surrogate/private/
# unassigned classes, fold exotic whitespace to a plain space, map visible
# symbols/emoji and the exploit-surface punctuation to "_", then hand the
# result to pathvalidate (universal) for the fs-invalid set, reserved
# device names, and length. Legitimate letters in any script survive.

from __future__ import annotations

import hashlib
import re
import unicodedata

# Windows device stems, reserved regardless of extension (checked on the
# part before the first dot). NFKC folds the superscript COM1/LPT1 variants
# down to COM1/LPT1 before we look, and the superscript forms stay in the
# list anyway for callers that reach _dedevice without normalizing first.
_WIN_DEVICE = (
    ["CON", "PRN", "AUX", "NUL"]
    + [f"COM{i}" for i in range(1, 10)]
    + [f"LPT{i}" for i in range(1, 10)]
    + [f"COM{c}" for c in "\u00b9\u00b2\u00b3"]
    + [f"LPT{c}" for c in "\u00b9\u00b2\u00b3"]
)
# The actual Linux "reserved" names. pathvalidate does NOT touch these
# (verified: "." and ".." pass through unchanged), so we handle them.
_POSIX_RESERVED = {".", ".."}

# Exploit-surface characters, mapped to "_" wherever they survive
# normalization. "." and "/" and "\" belong to the extension/component logic,
# so they are deliberately absent here.
_EXPLOIT_CHARS = re.compile(r"""[%$!&?*"'\u00a7=#~`:;,<>|@^]""")

# German transliteration overrides applied before unidecode in slugify().
# "ss" is what GOG's own slugs use, which matters when slugifying in order
# to match against them.
_TRANSLIT_OVERRIDES = {
    "\u00df": "ss",
    # Umlaut expansion stays off: unidecode gives a->a, which matches GOG.
}

_MAX_BYTES = 255           # Linux per-component limit (UTF-8 bytes)
_MAX_UTF16_UNITS = 255     # Windows per-component limit (UTF-16 code units)


def _strip_hazards(name: str) -> str:
    """NFKC-normalize, then remove/neutralize the Unicode classes used for
    spoofing and breakage while KEEPING legitimate letters and digits."""
    name = unicodedata.normalize("NFKC", name)
    out = []
    for ch in name:
        cat = unicodedata.category(ch)
        if cat in ("Cc", "Cf", "Cs", "Co", "Cn"):
            continue                      # invisible / dangerous -> drop
        if cat in ("Zs", "Zl", "Zp"):
            out.append(" ")               # any space-like -> plain space
        elif cat in ("So", "Sk"):
            out.append("_")               # emoji & modifier symbols -> _
        else:
            out.append(ch)
    return "".join(out)


def _collapse(name: str) -> str:
    name = re.sub(r"_+", "_", name)
    name = re.sub(r" {2,}", " ", name)
    return name


def _split_ext(name: str):
    stem, dot, tail = name.rpartition(".")
    if dot and stem and re.fullmatch(r"[A-Za-z0-9]{1,15}", tail):
        return stem, "." + tail
    return name, ""


def _truncate(name: str) -> str:
    def fits(s: str) -> bool:
        return (len(s.encode("utf-8")) <= _MAX_BYTES
                and len(s.encode("utf-16-le")) // 2 <= _MAX_UTF16_UNITS)
    if fits(name):
        return name
    stem, ext = _split_ext(name)
    chars = list(stem)
    while chars and not fits("".join(chars) + ext):
        chars.pop()
    return ("".join(chars).rstrip(". ") + ext) or "_"


def _dedevice(name: str) -> str:
    """Sole owner of reserved-name defusing. pathvalidate is handed
    ReservedNameHandler.as_is so it detects but never rewrites, which keeps
    the rule here where it can be tested rather than inherited from a library
    default that can change under us."""
    if name in _POSIX_RESERVED:
        return "_"
    head, dot, tail = name.partition(".")
    if head.upper() in _WIN_DEVICE:
        return f"{head}_{dot}{tail}"
    return name


def _apply_charclass(name: str) -> str:
    stem, ext = _split_ext(name)
    stem = _EXPLOIT_CHARS.sub("_", stem).replace(".", "_")
    return stem + ext


_READABLE_REPLACEMENTS = {
    "&": "and",
    "@": "at",
    "+": "and",
}


def humanize(text: str) -> str:
    """Replace symbols with their English word equivalents before
    sanitizing. Call this on titles or display names where '&' means
    'and', not on hostile input where it means trouble."""
    for src, dst in _READABLE_REPLACEMENTS.items():
        text = text.replace(src, f" {dst} ")
    return " ".join(text.split())


def slugify(name: str) -> str:
    """ASCII machine slug: transliterate down (unidecode), keep [a-z0-9_],
    fold every other run to a single '_'. For GOG slugs and similar keys."""
    if not name:
        raise ValueError("name must not be empty")
    for src, dst in _TRANSLIT_OVERRIDES.items():
        name = name.replace(src, dst)
    try:
        from unidecode import unidecode
        name = unidecode(name)
    except ImportError:
        name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = name.lower()
    name = re.sub(r"[^a-z0-9_]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    if not name:
        raise ValueError("name slugified to empty")
    return name


def windows_safe(name: str) -> str:
    """Stdlib-only fast path (no pathvalidate, no transliteration)."""
    if not name:
        raise ValueError("name must not be empty")
    name = _strip_hazards(name)
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = _apply_charclass(name)
    name = _collapse(name).strip(" ").rstrip(".")
    name = _dedevice(name)
    return _truncate(name) or "_"


def sanitize_filename(name: str) -> str:
    """Human-readable display name; native script preserved, hazards gone."""
    if not name:
        raise ValueError("name must not be empty")
    from pathvalidate import sanitize_filename as _pv
    from pathvalidate.handler import ReservedNameHandler
    name = _strip_hazards(name)
    name = _apply_charclass(name)
    name = _collapse(name).strip(" ").rstrip(".")
    name = str(_pv(name, platform="universal", replacement_text="_",
                   max_len=_MAX_BYTES,
                   reserved_name_handler=ReservedNameHandler.as_is))
    name = _dedevice(name)
    return _truncate(name) or "_"


def sanitize_path_component(name: str) -> str:
    """Hostile-input variant with collision-resistant hashing when lossy."""
    if not name:
        raise ValueError("path component must not be empty")
    from pathvalidate import sanitize_filename as _pv
    from pathvalidate.handler import ReservedNameHandler
    basis = _collapse(_strip_hazards(name)).strip(" ").rstrip(". ")
    if not basis:
        # dot/space-only input (".", "..", "..." , NBSP-only): pure garbage /
        # POSIX traversal tokens. Neutralize to "_" but keep them distinct.
        digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]
        return f"_-{digest}"
    cleaned = _apply_charclass(basis)
    cleaned = str(_pv(cleaned, platform="universal", replacement_text="_",
                      max_len=_MAX_BYTES,
                      reserved_name_handler=ReservedNameHandler.as_is))
    cleaned = _dedevice(cleaned)
    if not cleaned.strip("_-. "):
        raise ValueError("path component sanitized to empty")
    if cleaned != basis:
        digest = hashlib.sha1(basis.encode("utf-8")).hexdigest()[:8]
        stem, ext = _split_ext(cleaned)
        cleaned = f"{stem}-{digest}{ext}"
    return _truncate(cleaned) or "_"