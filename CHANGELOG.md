# Changelog

## 0.8.3 (2026-10-19)

Fix 12 findings from macOS review (Python 3.14). write_atomic and
download handle long filenames. download requests identity encoding
to prevent Content-Encoding decompression. arch detection: word
boundaries on macOS patterns, armv8l correctly mapped to armhf.
netfilter: removed overly broad path patterns. move_preserving:
atomic non-overwrite via link, symlink preservation on cross-device.
head_info returns timezone-aware datetime. Mount table read on
macOS/FreeBSD. platformdirs declared, setuptools bumped for PEP 639.

## 0.8.2 (2026-10-05)

Fix 32 review findings across sanitize, http, fileops, netfilter
and urls modules. First published release.

Product number SJ-PKG-0020.

## 0.8.1

CIFS/mergerfs settle delay in file operations.

## 0.8.0

Distro family detection and system dependency checker from TOML
manifests (checkreqs module).

## 0.7.0

Retention pruning and collision-free names in fileops.

## 0.6.0

Scraped-URL normalization (urls module).

## 0.5.0

Junk host/path filtering (netfilter), streaming file digests
(hashing), filename sanitizing (sanitize).

## 0.4.0

Human-readable formatting (fmt), Linux distro detection
(platforminfo), remote HEAD info and file listing in http.

## 0.3.0

Streaming download with progress callbacks, politeness delays
and cookie jar support in http.

## 0.2.0

Path containment guard (resolve_within), archive entry
normalization, hostile-input test corpora.

## 0.1.0

Initial release: sanitize, fileops and dt modules.
