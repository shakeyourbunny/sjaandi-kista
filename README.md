# kista

House toolchest. Small, well-scoped Python modules shared across the
Projects family, so the same user agent handling, sanitizing and file
routines stop getting rewritten per project.

Kista is Icelandic for chest - verkfaerakista is the toolchest.

## Modules

- `kista.http` - HTTP request identity: consistent header profiles
  (an honest tool profile and a complete browser ensemble), never
  random user agents.
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

## Usage

Install editable into a consumer project's venv:

    .venv/bin/pip install -e ~/Projects/kista

License: GPL-3.0-or-later.

---
This project is developed with tooled assistance, but tested, reviewed and
signed off by a human developer.
