# This file is part of the kista Project.
# License: GPL-3.0-or-later. Contact: kista-project@trinity2k.net
#

import pytest

from kista import sanitize


class TestSlugify:
    @pytest.mark.parametrize("raw,expected", [
        ("Hello World", "hello-world"),
        ("Träume & Schäume!", "träume-schäume"),
        ("  spaced  out  ", "spaced-out"),
        ("under_scores_too", "under-scores-too"),
        ("multi---dash", "multi-dash"),
        ("Already-Fine", "already-fine"),
    ])
    def test_slugs(self, raw, expected):
        assert sanitize.slugify(raw) == expected

    def test_empty_rejected(self):
        with pytest.raises(ValueError):
            sanitize.slugify("")

    def test_sanitized_to_empty_rejected(self):
        with pytest.raises(ValueError):
            sanitize.slugify("!!!")


class TestPathComponent:
    def test_traversal_neutralized(self):
        result = sanitize.sanitize_path_component("../../etc/passwd")
        assert "/" not in result
        assert not result.startswith(".")

    def test_backslash_neutralized(self):
        assert "\\" not in sanitize.sanitize_path_component("a\\b\\c")

    def test_control_chars_neutralized(self):
        result = sanitize.sanitize_path_component("evil\x00name\x1f")
        assert "\x00" not in result
        assert "\x1f" not in result

    def test_case_preserved(self):
        assert sanitize.sanitize_path_component("UserName") == "UserName"

    def test_pure_dot_name_rejected(self):
        with pytest.raises(ValueError):
            sanitize.sanitize_path_component("..")

    def test_windows_reserved_names_defused(self):
        for name in ("CON", "con", "NUL", "COM1", "lpt9"):
            result = sanitize.sanitize_path_component(name)
            assert result.upper().split(".")[0] not in (
                "CON", "PRN", "AUX", "NUL", "COM1", "LPT9",
            ), name

    def test_empty_rejected(self):
        with pytest.raises(ValueError):
            sanitize.sanitize_path_component("")

    def test_only_hostile_chars_rejected(self):
        with pytest.raises(ValueError):
            sanitize.sanitize_path_component("///")


class TestHumanize:
    def test_ampersand_to_and(self):
        assert sanitize.humanize("IBM PC & XT") == "IBM PC and XT"

    def test_at_to_at(self):
        assert sanitize.humanize("user@host") == "user at host"

    def test_plus_to_and(self):
        assert sanitize.humanize("C + D") == "C and D"

    def test_no_double_spaces(self):
        assert sanitize.humanize("A  &  B") == "A and B"

    def test_passthrough(self):
        assert sanitize.humanize("plain text") == "plain text"

    def test_combined_with_sanitize(self):
        result = sanitize.sanitize_filename(sanitize.humanize("DOS & BIOS"))
        assert "and" in result
        assert "&" not in result


class TestDedevice:
    """_dedevice owns reserved-name defusing; pathvalidate is told to keep its
    hands off it, so these assertions must hold without the library helping."""

    @pytest.mark.parametrize("raw,expected", [
        ("CON", "CON_"),
        ("con", "con_"),
        ("NUL", "NUL_"),
        ("COM1", "COM1_"),
        ("lpt9", "lpt9_"),
        ("con.txt", "con_.txt"),
        ("NUL.tar.gz", "NUL_.tar.gz"),
    ])
    def test_reserved_stems_get_trailing_underscore(self, raw, expected):
        assert sanitize._dedevice(raw) == expected

    @pytest.mark.parametrize("raw", [".", ".."])
    def test_posix_reserved_collapse_to_underscore(self, raw):
        assert sanitize._dedevice(raw) == "_"

    @pytest.mark.parametrize("raw", ["normal.txt", "CONTENT", "COM", "COM10", "readme"])
    def test_ordinary_names_untouched(self, raw):
        assert sanitize._dedevice(raw) == raw

    def test_idempotent(self):
        once = sanitize._dedevice("CON")
        assert sanitize._dedevice(once) == once
