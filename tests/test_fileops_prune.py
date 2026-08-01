# This file is part of the kista Project.
# License: GPL-3.0-or-later. Contact: kista-project@trinity2k.net
#

import os
import time

import pytest

from kista import fileops


def _aged_file(directory, name, age_days):
    path = directory / name
    path.write_bytes(b"x")
    stamp = time.time() - age_days * 86400
    os.utime(path, (stamp, stamp))
    return path


class TestPruneCandidates:
    def test_older_than_max_age_selected(self, tmp_path):
        old = _aged_file(tmp_path, "old.log", 40)
        _aged_file(tmp_path, "new.log", 1)
        result = fileops.prune_candidates(tmp_path, max_age_days=30)
        assert result == [old]

    def test_keep_newest_selects_overflow(self, tmp_path):
        _aged_file(tmp_path, "v3", 1)
        _aged_file(tmp_path, "v2", 2)
        old1 = _aged_file(tmp_path, "v1", 3)
        old0 = _aged_file(tmp_path, "v0", 4)
        result = fileops.prune_candidates(tmp_path, keep_newest=2)
        assert sorted(result) == sorted([old1, old0])

    def test_pattern_filters(self, tmp_path):
        old_log = _aged_file(tmp_path, "a.log", 40)
        _aged_file(tmp_path, "a.db", 40)
        result = fileops.prune_candidates(tmp_path, pattern="*.log", max_age_days=30)
        assert result == [old_log]

    def test_no_criteria_rejected(self, tmp_path):
        with pytest.raises(ValueError):
            fileops.prune_candidates(tmp_path)

    def test_missing_directory_is_empty(self, tmp_path):
        assert fileops.prune_candidates(tmp_path / "ghost", keep_newest=1) == []

    def test_nothing_deleted(self, tmp_path):
        _aged_file(tmp_path, "old.log", 40)
        fileops.prune_candidates(tmp_path, max_age_days=30)
        assert (tmp_path / "old.log").exists()

    def test_directories_ignored(self, tmp_path):
        (tmp_path / "subdir").mkdir()
        _aged_file(tmp_path, "f", 40)
        result = fileops.prune_candidates(tmp_path, max_age_days=30)
        assert all(p.is_file() for p in result)


class TestAvailableName:
    def test_free_path_returned_as_is(self, tmp_path):
        target = tmp_path / "file.txt"
        assert fileops.available_name(target) == target

    def test_collision_gets_numbered(self, tmp_path):
        (tmp_path / "file.txt").write_bytes(b"x")
        assert fileops.available_name(tmp_path / "file.txt") == tmp_path / "file_1.txt"

    def test_counter_advances(self, tmp_path):
        (tmp_path / "file.txt").write_bytes(b"x")
        (tmp_path / "file_1.txt").write_bytes(b"x")
        assert fileops.available_name(tmp_path / "file.txt") == tmp_path / "file_2.txt"
