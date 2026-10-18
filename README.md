<!-- This file is part of the kista Project.
     License: GPL-3.0-or-later. Contact: kista-project@trinity2k.net -->

# kista

Reusable Python modules for file operations, HTTP identity, path
safety, and platform detection. Small, well-scoped building blocks
so the same user agent handling, sanitizing and file routines stop
getting rewritten per project.

Kista is Icelandic for chest - verkfaerakista is the toolchest.

## Modules

- `kista.http` - HTTP request identity: consistent header profiles
  (an honest tool profile and a complete browser ensemble), never
  random user agents. The browser profile exists so automated
  downloads can reach hosts that block generic user agents while
  still identifying the actual client in the profile comment.
- `kista.sanitize` - filename and path component sanitizing.
- `kista.fileops` - atomic writes and timestamp-preserving copy/move.
- `kista.paths` - containment guard (`resolve_within`) and archive
  entry normalization for hostile input.
- `kista.testing` - hostile-input corpora for test parametrization.
- `kista.netfilter` - junk host/path filtering (ads, trackers, crash
  reporters) with bundled pattern lists and whitelist.
- `kista.hashing` - streaming file digests.
- `kista.fmt` - human-readable formatting (byte sizes).
- `kista.platforminfo` - Linux distro detection with derivative
  mapping via ID_LIKE.
- `kista.urls` - scraped-URL normalization.
- `kista.dt` - timezone-aware UTC helpers.
- `kista.arch` - AppImage architecture detection from filenames.
- `kista.checkreqs` - system dependency checker from TOML manifests.

## Install

From PyPI:

    pip install sjaandi-kista

From source:

    pip install .

The import name is `kista`:

```python
from kista.sanitize import sanitize_filename
from kista.http import browser_headers
```

## License

GPL-3.0-or-later. See LICENSE for the full text and
THIRD_PARTY_LICENSES.txt for dependencies. Product number SJ-PKG-0020.

---
kista has been written with the help of tooled assistance, but has been
designed, reviewed and thoroughly tested and signed off by its developer.
