# This file is part of the kista Project.
# License: GPL-3.0-or-later. Contact: kista-project@trinity2k.net
#

import pytest

from kista import paths, testing


class TestResolveWithin:
    def test_normal_child_resolves(self, tmp_path):
        result = paths.resolve_within(tmp_path, "sub", "file.txt")
        assert result == (tmp_path / "sub" / "file.txt").resolve()

    def test_traversal_escape_rejected(self, tmp_path):
        with pytest.raises(ValueError):
            paths.resolve_within(tmp_path, "..", "escape.txt")

    def test_deep_traversal_rejected(self, tmp_path):
        with pytest.raises(ValueError):
            paths.resolve_within(tmp_path, "a/../../../../etc", "passwd")

    def test_absolute_part_rejected(self, tmp_path):
        with pytest.raises(ValueError):
            paths.resolve_within(tmp_path, "/etc/passwd")

    def test_null_byte_rejected(self, tmp_path):
        with pytest.raises(ValueError):
            paths.resolve_within(tmp_path, "normal\x00hidden")

    def test_symlink_escape_rejected(self, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        outside = tmp_path / "outside-target"
        outside.mkdir()
        link = root / "link"
        link.symlink_to(outside)
        with pytest.raises(ValueError):
            paths.resolve_within(root, "link", "file.txt")

    def test_corpus_components_all_contained_or_rejected(self, tmp_path):
        for label, component in testing.HOSTILE_PATH_COMPONENTS:
            try:
                result = paths.resolve_within(tmp_path, component)
            except ValueError:
                continue
            assert result.is_relative_to(tmp_path.resolve()), label


class TestNormalizeArchiveEntry:
    def test_plain_relative_kept(self):
        assert paths.normalize_archive_entry("dir/file.txt") == "dir/file.txt"

    def test_backslashes_become_slashes(self):
        assert paths.normalize_archive_entry("dir\\sub\\file.txt") == "dir/sub/file.txt"

    def test_absolute_rejected(self):
        with pytest.raises(ValueError):
            paths.normalize_archive_entry("/etc/passwd")

    def test_drive_letter_rejected(self):
        with pytest.raises(ValueError):
            paths.normalize_archive_entry("C:\\Windows\\System32\\evil.dll")

    def test_traversal_rejected(self):
        with pytest.raises(ValueError):
            paths.normalize_archive_entry("../../outside.txt")

    def test_inner_dotdot_rejected(self):
        with pytest.raises(ValueError):
            paths.normalize_archive_entry("ok/../../../etc/passwd")

    def test_null_byte_rejected(self):
        with pytest.raises(ValueError):
            paths.normalize_archive_entry("file\x00.txt")

    def test_control_chars_rejected(self):
        with pytest.raises(ValueError):
            paths.normalize_archive_entry("file\x1f.txt")

    def test_empty_rejected(self):
        with pytest.raises(ValueError):
            paths.normalize_archive_entry("")

    def test_dot_segments_collapsed(self):
        assert paths.normalize_archive_entry("./dir/./file.txt") == "dir/file.txt"

    def test_unc_rejected(self):
        with pytest.raises(ValueError):
            paths.normalize_archive_entry("\\\\server\\share\\file")


class TestCorpus:
    def test_corpora_are_labeled_pairs(self):
        for corpus in (
            testing.HOSTILE_PATH_COMPONENTS,
            testing.HOSTILE_URL_PATHS,
            testing.HOSTILE_FILE_PATHS,
        ):
            assert len(corpus) >= 5
            for item in corpus:
                label, value = item
                assert isinstance(label, str) and isinstance(value, str)

    def test_archive_normalizer_survives_file_corpus(self):
        for label, value in testing.HOSTILE_FILE_PATHS:
            try:
                result = paths.normalize_archive_entry(value)
            except ValueError:
                continue
            assert ".." not in result.split("/"), label
            assert not result.startswith("/"), label
