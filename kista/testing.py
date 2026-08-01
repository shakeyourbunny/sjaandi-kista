# This file is part of the kista Project.
# License: GPL-3.0-or-later. Contact: kista-project@trinity2k.net
#
# Corpus adapted from the dosbox-automation project's
# test_traversal_contract.py (GPL-2.0-or-later, same household).

"""Hostile input corpora for test parametrization.

Import these in any house project's tests instead of hand-rolling a
subset: `@pytest.mark.parametrize("label,path", HOSTILE_URL_PATHS)`.
Each corpus is a list of (label, value) pairs.
"""

# Path components as they might reach filesystem code (form fields,
# config values, scraped names).
HOSTILE_PATH_COMPONENTS = [
    ("dot-dot", ".."),
    ("dot-dot-slash", "../"),
    ("nested-traversal", "a/../../../../etc"),
    ("null-byte", "normal\x00hidden"),
    ("control-char", "file\x1fname"),
    ("backslash-traversal", "..\\..\\etc"),
    ("long-traversal", "../" * 20 + "etc/passwd"),
    ("dot-space", ". "),
]

# URL request paths for web-facing servers (encoded variants matter
# at this layer; the server decodes before path handling).
HOSTILE_URL_PATHS = [
    ("dot-dot-slash", "/../../../etc/passwd"),
    ("encoded-dot-dot", "/%2e%2e/%2e%2e/%2e%2e/etc/passwd"),
    ("encoded-slash", "/..%2f..%2f..%2f/etc/passwd"),
    ("double-encoded", "/%252e%252e/%252e%252e/etc/passwd"),
    ("backslash", "/..\\..\\..\\etc\\passwd"),
    ("encoded-backslash", "/..%5c..%5c..%5cetc%5cpasswd"),
    ("null-byte", "/%00/../etc/passwd"),
    ("long-traversal", "/" + "../" * 20 + "etc/passwd"),
    ("unix-absolute", "/etc/passwd"),
    ("proc-self", "/proc/self/environ"),
]

# Full filesystem paths as they might reach file-open or archive code.
HOSTILE_FILE_PATHS = [
    ("unix-etc", "/etc/passwd"),
    ("unix-shadow", "/etc/shadow"),
    ("traversal", "../../../../../../etc/passwd"),
    ("unc-path", "\\\\127.0.0.1\\c$\\windows\\system32"),
    ("windows-abs", "C:\\Windows\\System32\\config\\SAM"),
    ("null-in-path", "/tmp/normal.img\x00/etc/passwd"),
    ("dev-null", "/dev/null"),
    ("proc-environ", "/proc/self/environ"),
]
