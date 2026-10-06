# This file is part of the kista Project.
# License: GPL-3.0-or-later. Contact: kista-project@trinity2k.net
#

import pytest

from kista import sanitize


class TestSlugify:
    @pytest.mark.parametrize("raw,expected", [
        ("Hello World", "hello_world"),
        ("Träume & Schäume!", "traume_schaume"),
        ("  spaced  out  ", "spaced_out"),
        ("under_scores_too", "under_scores_too"),
        ("multi---dash", "multi_dash"),
        ("Already-Fine", "already_fine"),
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

    def test_pure_dot_name_neutralized(self):
        result = sanitize.sanitize_path_component("..")
        assert result != ".."
        assert not result.startswith(".")
        assert "_" in result

    def test_windows_reserved_names_defused(self):
        for name in ("CON", "con", "NUL", "COM1", "lpt9"):
            result = sanitize.sanitize_path_component(name)
            assert result.upper().split(".")[0] not in (
                "CON", "PRN", "AUX", "NUL", "COM1", "LPT9",
            ), name

    def test_empty_rejected(self):
        with pytest.raises(ValueError):
            sanitize.sanitize_path_component("")

    def test_only_hostile_chars_get_hash_placeholder(self):
        result = sanitize.sanitize_path_component("///")
        assert result.startswith("_-")
        assert len(result) == 10

    def test_nfkc_identical_inputs_get_different_hashes(self):
        # fi ligature normalizes to "fi" under NFKC
        a = sanitize.sanitize_path_component("ﬁle")
        b = sanitize.sanitize_path_component("file")
        assert a != b

    def test_zero_width_joiner_distinguished(self):
        a = sanitize.sanitize_path_component("adm‍in")
        b = sanitize.sanitize_path_component("admin")
        assert a != b

    def test_hash_stable_on_reapply(self):
        result = sanitize.sanitize_path_component("foo:bar")
        assert sanitize.sanitize_path_component(result) == result

    def test_control_char_only_gets_hash_placeholder(self):
        result = sanitize.sanitize_path_component("\t")
        assert result.startswith("_-")
        assert len(result) == 10


class TestWindowsSafe:
    @pytest.mark.parametrize("raw,expected", [
        ('a<b>c:d"e', "a_b_c_d_e"),
        ("normal-name.txt", "normal-name.txt"),
        ("trailing. ", "trailing"),
        ("ctrl\x01char", "ctrl_char"),
    ])
    def test_replacements(self, raw, expected):
        assert sanitize.windows_safe(raw) == expected

    def test_dotfiles_defused(self):
        assert not sanitize.windows_safe(".htaccess").startswith(".")
        assert not sanitize.windows_safe(".git").startswith(".")

    def test_no_trailing_spaces(self):
        result = sanitize.windows_safe("foo ..")
        assert not result.endswith(" ")

    @pytest.mark.parametrize("raw", [
        "hello...", "name. ", "test . .", "dots..spaces  ..",
    ])
    def test_no_trailing_dots_or_spaces(self, raw):
        result = sanitize.windows_safe(raw)
        assert not result.endswith(".")
        assert not result.endswith(" ")

    def test_never_empty(self):
        assert sanitize.windows_safe("...") == "_"


class TestSanitizeFilename:
    def test_hostile_chars_removed(self):
        result = sanitize.sanitize_filename('Game: The "Sequel" <2>?')
        assert ":" not in result
        assert "?" not in result
        assert "<" not in result

    def test_reserved_name_defused(self):
        assert sanitize.sanitize_filename("CON").upper() != "CON"

    def test_dotfiles_defused(self):
        assert not sanitize.sanitize_filename(".htaccess").startswith(".")

    def test_trailing_dots_spaces_stripped(self):
        assert not sanitize.sanitize_filename("name. ").endswith((".", " "))

    def test_no_trailing_spaces(self):
        result = sanitize.sanitize_filename("foo ..")
        assert not result.endswith(" ")

    def test_replacement_semantics(self):
        assert sanitize.sanitize_filename("???") == "_"

    def test_never_empty(self):
        assert sanitize.sanitize_filename(". ") == "_"

    def test_normal_name_untouched(self):
        assert sanitize.sanitize_filename("normal-file 1.2.txt") == "normal-file 1.2.txt"


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

    @pytest.mark.parametrize("raw,expected", [
        (".htaccess", "_htaccess"),
        (".git", "_git"),
        (".env", "_env"),
        (".gitignore", "_gitignore"),
        (".svn", "_svn"),
    ])
    def test_dotfiles_defused(self, raw, expected):
        assert sanitize._dedevice(raw) == expected

    @pytest.mark.parametrize("raw", ["normal.txt", "CONTENT", "COM", "COM10", "readme"])
    def test_ordinary_names_untouched(self, raw):
        assert sanitize._dedevice(raw) == raw

    def test_idempotent(self):
        once = sanitize._dedevice("CON")
        assert sanitize._dedevice(once) == once
