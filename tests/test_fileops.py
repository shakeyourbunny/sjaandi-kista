# This file is part of the kista Project.
# License: GPL-3.0-or-later. Contact: kista-project@trinity2k.net
#

import errno
import os
import shutil
from pathlib import Path

import pytest

from kista import fileops


class TestWriteAtomic:
    def test_writes_content(self, tmp_path):
        target = tmp_path / "out.txt"
        fileops.write_atomic(target, b"payload")
        assert target.read_bytes() == b"payload"

    def test_overwrites_existing(self, tmp_path):
        target = tmp_path / "out.txt"
        target.write_bytes(b"old")
        fileops.write_atomic(target, b"new")
        assert target.read_bytes() == b"new"

    def test_no_temp_leftover(self, tmp_path):
        target = tmp_path / "out.txt"
        fileops.write_atomic(target, b"x")
        assert [p.name for p in tmp_path.iterdir()] == ["out.txt"]

    def test_mode_applied(self, tmp_path):
        target = tmp_path / "out.txt"
        fileops.write_atomic(target, b"x")
        assert oct(target.stat().st_mode & 0o777) == oct(0o644)

    def test_rejects_str_payload(self, tmp_path):
        with pytest.raises(TypeError):
            fileops.write_atomic(tmp_path / "out.txt", "not bytes")

    def test_missing_parent_fails_loudly(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            fileops.write_atomic(tmp_path / "no" / "dir" / "out.txt", b"x")

    def test_long_filename_no_enametoolong(self, tmp_path):
        long_name = "a" * 245 + ".txt"
        target = tmp_path / long_name
        fileops.write_atomic(target, b"payload")
        assert target.read_bytes() == b"payload"


class TestTempPrefix:
    def test_short_name_unchanged(self):
        assert fileops.temp_prefix("file.txt") == ".file.txt."

    def test_long_name_truncated(self):
        prefix = fileops.temp_prefix("a" * 250)
        assert len(prefix.encode("utf-8")) + 8 <= 255

    def test_surrogateescape_name(self):
        name = b"caf\xe9.txt".decode("utf-8", "surrogateescape")
        prefix = fileops.temp_prefix(name)
        assert len(os.fsencode(prefix)) + 8 <= 255


class TestCopyPreserving:
    def test_content_and_mtime_preserved(self, tmp_path):
        src = tmp_path / "src.bin"
        src.write_bytes(b"data")
        os.utime(src, (1000000000, 1000000000))
        dst = tmp_path / "dst.bin"
        fileops.copy_preserving(src, dst)
        assert dst.read_bytes() == b"data"
        assert dst.stat().st_mtime == src.stat().st_mtime

    def test_source_must_exist(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            fileops.copy_preserving(tmp_path / "ghost", tmp_path / "dst")


class TestMovePreserving:
    def test_moves_and_preserves_mtime(self, tmp_path):
        src = tmp_path / "src.bin"
        src.write_bytes(b"data")
        os.utime(src, (1000000000, 1000000000))
        dst = tmp_path / "sub"
        dst.mkdir()
        target = dst / "moved.bin"
        fileops.move_preserving(src, target)
        assert not src.exists()
        assert target.read_bytes() == b"data"
        assert int(target.stat().st_mtime) == 1000000000

    def test_refuses_overwrite(self, tmp_path):
        src = tmp_path / "src"
        src.write_bytes(b"a")
        dst = tmp_path / "dst"
        dst.write_bytes(b"b")
        with pytest.raises(FileExistsError):
            fileops.move_preserving(src, dst)
        assert src.exists()
        assert dst.read_bytes() == b"b"

    def test_source_must_be_file_or_symlink(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            fileops.move_preserving(tmp_path / "ghost", tmp_path / "dst")


def _corrupting_copy2(real_copy2):
    """Corrupts a copy in a way that mtime and size checks cannot see."""
    def copy2(src, dst, *, follow_symlinks=True):
        real_copy2(src, dst, follow_symlinks=follow_symlinks)
        st = os.stat(src)
        with open(dst, "r+b") as f:
            first = f.read(1)
            f.seek(0)
            f.write(bytes([first[0] ^ 0xFF]))
        os.utime(dst, ns=(st.st_atime_ns, st.st_mtime_ns))
        return dst
    return copy2


def _no_rename(monkeypatch):
    def no_rename(a, b):
        raise OSError(errno.EXDEV, "cross-device link")
    monkeypatch.setattr(fileops.os, "replace", no_rename)


def _cross_device(monkeypatch):
    def no_link(*a, **k):
        raise OSError(errno.EXDEV, "cross-device link")
    monkeypatch.setattr(fileops.os, "link", no_link)


class TestVerifyContent:
    def test_copy_with_verification_passes_a_good_copy(self, tmp_path):
        src = tmp_path / "src.bin"
        src.write_bytes(b"data" * 1000)
        fileops.copy_preserving(src, tmp_path / "dst.bin", verify_content=True)
        assert (tmp_path / "dst.bin").read_bytes() == src.read_bytes()

    def test_copy_with_verification_refuses_a_corrupt_copy(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fileops.shutil, "copy2", _corrupting_copy2(shutil.copy2))
        src = tmp_path / "src.bin"
        src.write_bytes(b"data")
        with pytest.raises(OSError, match="content"):
            fileops.copy_preserving(src, tmp_path / "dst.bin", verify_content=True)
        assert sorted(x.name for x in tmp_path.iterdir()) == ["src.bin"]
        assert src.read_bytes() == b"data"

    def test_cross_device_move_with_verification_keeps_the_source_of_a_corrupt_copy(
            self, tmp_path, monkeypatch):
        _cross_device(monkeypatch)
        monkeypatch.setattr(fileops.shutil, "copy2", _corrupting_copy2(shutil.copy2))
        src = tmp_path / "src.bin"
        src.write_bytes(b"data")
        with pytest.raises(OSError, match="content"):
            fileops.move_preserving(src, tmp_path / "dst.bin", verify_content=True)
        assert src.read_bytes() == b"data"
        assert not (tmp_path / "dst.bin").exists()

    def test_cross_device_move_with_verification_moves_a_good_copy(self, tmp_path, monkeypatch):
        _cross_device(monkeypatch)
        src = tmp_path / "src.bin"
        src.write_bytes(b"data")
        os.utime(src, (1000000000, 1000000000))
        fileops.move_preserving(src, tmp_path / "dst.bin", verify_content=True)
        assert not src.exists()
        assert (tmp_path / "dst.bin").read_bytes() == b"data"
        assert int((tmp_path / "dst.bin").stat().st_mtime) == 1000000000

    def test_a_move_done_as_a_hard_link_needs_no_compare(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fileops, "_same_bytes", lambda *a: pytest.fail("compared a link"))
        src = tmp_path / "src.bin"
        src.write_bytes(b"data")
        fileops.move_preserving(src, tmp_path / "dst.bin", verify_content=True)
        assert (tmp_path / "dst.bin").read_bytes() == b"data"

    def test_a_second_corrupt_copy_to_the_same_path_is_not_passed_from_a_cache(
            self, tmp_path, monkeypatch):
        # filecmp.cmp caches outcomes by path, size and mtime even with shallow=False
        src = tmp_path / "src.bin"
        src.write_bytes(b"data")
        dst = tmp_path / "dst.bin"
        fileops.copy_preserving(src, dst, verify_content=True)
        dst.unlink()
        monkeypatch.setattr(fileops.shutil, "copy2", _corrupting_copy2(shutil.copy2))
        with pytest.raises(OSError, match="content"):
            fileops.copy_preserving(src, dst, verify_content=True)


class TestVerifyContentEdges:
    def test_an_error_during_the_compare_removes_the_unchecked_copy(self, tmp_path, monkeypatch):
        def broken(*a):
            raise OSError(errno.EIO, "read error")
        monkeypatch.setattr(fileops, "_same_bytes", broken)
        src = tmp_path / "src.bin"
        src.write_bytes(b"data")
        with pytest.raises(OSError, match="read error"):
            fileops.copy_preserving(src, tmp_path / "dst.bin", verify_content=True)
        assert sorted(x.name for x in tmp_path.iterdir()) == ["src.bin"]

    def test_an_error_during_a_move_compare_keeps_the_source_and_drops_the_copy(
            self, tmp_path, monkeypatch):
        _cross_device(monkeypatch)
        def interrupted(*a):
            raise KeyboardInterrupt
        monkeypatch.setattr(fileops, "_same_bytes", interrupted)
        src = tmp_path / "src.bin"
        src.write_bytes(b"data")
        with pytest.raises(KeyboardInterrupt):
            fileops.move_preserving(src, tmp_path / "dst.bin", verify_content=True)
        assert src.read_bytes() == b"data"
        assert not (tmp_path / "dst.bin").exists()

    def test_a_directory_target_is_verified_on_the_copied_file(self, tmp_path):
        src = tmp_path / "src.bin"
        src.write_bytes(b"data")
        out = tmp_path / "out"
        out.mkdir()
        fileops.copy_preserving(src, out, verify_content=True)
        assert (out / "src.bin").read_bytes() == b"data"

    def test_a_symlinked_target_is_refused_before_anything_is_written(self, tmp_path):
        src = tmp_path / "src.bin"
        src.write_bytes(b"new!")
        real = tmp_path / "real.bin"
        real.write_bytes(b"old!")
        link = tmp_path / "link.bin"
        link.symlink_to(real)
        with pytest.raises(ValueError, match="symlink"):
            fileops.copy_preserving(src, link, verify_content=True)
        assert real.read_bytes() == b"old!"
        assert link.is_symlink()

    def test_the_copy_is_flushed_before_it_is_compared(self, tmp_path, monkeypatch):
        calls = []
        real_fsync, real_same = os.fsync, fileops._same_bytes
        monkeypatch.setattr(fileops.os, "fsync", lambda fd: calls.append("fsync") or real_fsync(fd))
        monkeypatch.setattr(fileops, "_same_bytes",
                            lambda a, b: calls.append("compare") or real_same(a, b))
        src = tmp_path / "src.bin"
        src.write_bytes(b"data")
        fileops.copy_preserving(src, tmp_path / "dst.bin", verify_content=True)
        assert calls == ["fsync", "compare"]

    def test_a_read_only_copy_can_be_verified(self, tmp_path):
        src = tmp_path / "src.bin"
        src.write_bytes(b"data")
        src.chmod(0o444)
        fileops.copy_preserving(src, tmp_path / "dst.bin", verify_content=True)
        assert (tmp_path / "dst.bin").read_bytes() == b"data"

    def test_a_read_only_file_can_be_moved_across_devices_with_verification(
            self, tmp_path, monkeypatch):
        _cross_device(monkeypatch)
        src = tmp_path / "src.bin"
        src.write_bytes(b"data")
        src.chmod(0o444)
        fileops.move_preserving(src, tmp_path / "dst.bin", verify_content=True)
        assert not src.exists()
        assert (tmp_path / "dst.bin").read_bytes() == b"data"

    def test_a_symlink_inside_a_directory_target_is_refused(self, tmp_path):
        src = tmp_path / "f.bin"
        src.write_bytes(b"new!")
        real = tmp_path / "real.bin"
        real.write_bytes(b"old!")
        out = tmp_path / "out"
        out.mkdir()
        (out / "f.bin").symlink_to(real)
        with pytest.raises(ValueError, match="symlink"):
            fileops.copy_preserving(src, out, verify_content=True)
        assert real.read_bytes() == b"old!"

    def test_a_hard_linked_target_is_refused(self, tmp_path):
        src = tmp_path / "src.bin"
        src.write_bytes(b"new!")
        dst = tmp_path / "dst.bin"
        dst.write_bytes(b"old!")
        other = tmp_path / "other.bin"
        os.link(dst, other)
        with pytest.raises(ValueError, match="hard link"):
            fileops.copy_preserving(src, dst, verify_content=True)
        assert other.read_bytes() == b"old!"

    def test_an_interrupt_during_the_copy_leaves_no_unchecked_copy(self, tmp_path, monkeypatch):
        def interrupted_copy(s, d, *, follow_symlinks=True):
            shutil.copyfile(s, d)
            raise KeyboardInterrupt
        monkeypatch.setattr(fileops.shutil, "copy2", interrupted_copy)
        src = tmp_path / "src.bin"
        src.write_bytes(b"data")
        with pytest.raises(KeyboardInterrupt):
            fileops.copy_preserving(src, tmp_path / "dst.bin", verify_content=True)
        assert sorted(x.name for x in tmp_path.iterdir()) == ["src.bin"]


@pytest.mark.parametrize("a, b, same", [
    pytest.param(b"", b"", True, id="empty"),
    pytest.param(b"", b"x", False, id="empty-vs-byte"),
    pytest.param(b"x" * (2 << 20), b"x" * (2 << 20), True, id="two-chunks-equal"),
    pytest.param(b"x" * (1 << 20) + b"a", b"x" * (1 << 20) + b"b", False, id="second-chunk-start"),
    pytest.param(b"x" * (2 << 20), b"x" * (1 << 20), False, id="truncated-at-chunk"),
    pytest.param(b"abc", b"aXc", False, id="middle-byte"),
    pytest.param(b"x" * (1 << 20), b"x" * ((1 << 20) - 1) + b"y", False, id="last-byte-of-chunk"),
    pytest.param(b"x" * (3 << 19), b"x" * (1 << 19) + b"y" + b"x" * ((1 << 20) - 1), False,
                 id="middle-of-chunk"),
])
def test_same_bytes_compares_across_chunks(tmp_path, a, b, same):
    pa, pb = tmp_path / "a", tmp_path / "b"
    pa.write_bytes(a)
    pb.write_bytes(b)
    assert fileops._same_bytes(pa, pb) is same


class TestVerifiedCopyTouchesOnlyItsOwnFiles:
    def test_the_same_path_is_refused_and_the_source_kept(self, tmp_path):
        src = tmp_path / "book.pdf"
        src.write_bytes(b"data")
        with pytest.raises(ValueError, match="same file"):
            fileops.copy_preserving(src, src, verify_content=True)
        assert src.read_bytes() == b"data"

    def test_the_source_directory_as_target_is_refused(self, tmp_path):
        src = tmp_path / "book.pdf"
        src.write_bytes(b"data")
        with pytest.raises(ValueError, match="same file"):
            fileops.copy_preserving(src, tmp_path, verify_content=True)
        assert src.read_bytes() == b"data"

    def test_the_source_through_a_symlinked_folder_is_refused(self, tmp_path):
        real = tmp_path / "real"
        real.mkdir()
        src = real / "book.pdf"
        src.write_bytes(b"data")
        alias = tmp_path / "alias"
        alias.symlink_to(real)
        with pytest.raises(ValueError, match="same file"):
            fileops.copy_preserving(src, alias / "book.pdf", verify_content=True)
        assert src.read_bytes() == b"data"

    @pytest.mark.skipif(os.name == "nt", reason="os.replace refuses a read-only target on Windows")
    def test_a_read_only_earlier_copy_is_replaced_not_lost(self, tmp_path):
        src = tmp_path / "src.bin"
        src.write_bytes(b"new!")
        dst = tmp_path / "dst.bin"
        dst.write_bytes(b"old!")
        dst.chmod(0o444)
        fileops.copy_preserving(src, dst, verify_content=True)
        assert dst.read_bytes() == b"new!"

    @pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root reads anything")
    def test_an_unreadable_source_leaves_the_existing_target_alone(self, tmp_path):
        src = tmp_path / "src.bin"
        src.write_bytes(b"new!")
        src.chmod(0o000)
        dst = tmp_path / "dst.bin"
        dst.write_bytes(b"old!")
        try:
            with pytest.raises(PermissionError):
                fileops.copy_preserving(src, dst, verify_content=True)
        finally:
            src.chmod(0o644)
        assert dst.read_bytes() == b"old!"
        assert sorted(x.name for x in tmp_path.iterdir()) == ["dst.bin", "src.bin"]

    def test_a_failed_compare_keeps_the_old_target_and_leaves_no_temp(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fileops.shutil, "copy2", _corrupting_copy2(shutil.copy2))
        src = tmp_path / "src.bin"
        src.write_bytes(b"new!")
        dst = tmp_path / "dst.bin"
        dst.write_bytes(b"old!")
        with pytest.raises(OSError, match="content"):
            fileops.copy_preserving(src, dst, verify_content=True)
        assert dst.read_bytes() == b"old!"
        assert sorted(x.name for x in tmp_path.iterdir()) == ["dst.bin", "src.bin"]

    def test_an_interrupted_move_settle_keeps_the_source_and_drops_the_copy(
            self, tmp_path, monkeypatch):
        _cross_device(monkeypatch)
        monkeypatch.setattr(fileops, "_needs_settle", lambda p: True)
        def interrupted(seconds):
            raise KeyboardInterrupt
        monkeypatch.setattr(fileops.time, "sleep", interrupted)
        src = tmp_path / "src.bin"
        src.write_bytes(b"data")
        with pytest.raises(KeyboardInterrupt):
            fileops.move_preserving(src, tmp_path / "dst.bin", verify_content=True)
        assert src.read_bytes() == b"data"
        assert not (tmp_path / "dst.bin").exists()

    def test_the_mergerfs_rename_fallback_creates_a_new_target_verified(
            self, tmp_path, monkeypatch):
        _no_rename(monkeypatch)
        src = tmp_path / "src.bin"
        src.write_bytes(b"new!")
        compared = []
        real_same = fileops._same_bytes
        monkeypatch.setattr(fileops, "_same_bytes", lambda a, b: compared.append(b) or real_same(a, b))
        fileops.copy_preserving(src, tmp_path / "dst.bin", verify_content=True)
        assert (tmp_path / "dst.bin").read_bytes() == b"new!"
        assert compared[-1] == tmp_path / "dst.bin"
        assert sorted(x.name for x in tmp_path.iterdir()) == ["dst.bin", "src.bin"]

    @pytest.mark.parametrize("mode", [0o644, 0o444], ids=["writable", "read-only"])
    def test_the_mergerfs_fallback_refuses_to_overwrite_and_keeps_the_old_target(
            self, tmp_path, monkeypatch, mode):
        _no_rename(monkeypatch)
        src = tmp_path / "src.bin"
        src.write_bytes(b"new!")
        dst = tmp_path / "dst.bin"
        dst.write_bytes(b"old!")
        dst.chmod(mode)
        with pytest.raises(OSError, match="cannot replace"):
            fileops.copy_preserving(src, dst, verify_content=True)
        assert dst.read_bytes() == b"old!"
        assert sorted(x.name for x in tmp_path.iterdir()) == ["dst.bin", "src.bin"]

    def test_an_interrupted_mergerfs_fallback_leaves_nothing_behind(self, tmp_path, monkeypatch):
        _no_rename(monkeypatch)
        real_copyfileobj = shutil.copyfileobj
        def copyfileobj(fin, fout, *a, **k):
            if Path(fin.name).name.startswith(".dst.bin."):
                fout.write(b"ne")
                raise KeyboardInterrupt
            return real_copyfileobj(fin, fout, *a, **k)
        monkeypatch.setattr(fileops.shutil, "copyfileobj", copyfileobj)
        src = tmp_path / "src.bin"
        src.write_bytes(b"new!")
        with pytest.raises(KeyboardInterrupt):
            fileops.copy_preserving(src, tmp_path / "dst.bin", verify_content=True)
        assert sorted(x.name for x in tmp_path.iterdir()) == ["src.bin"]

    def test_the_mergerfs_fallback_settles_before_it_compares(self, tmp_path, monkeypatch):
        _no_rename(monkeypatch)
        events = []
        monkeypatch.setattr(fileops, "_needs_settle", lambda p: True)
        monkeypatch.setattr(fileops.time, "sleep", lambda s: events.append(("sleep",)))
        real_same = fileops._same_bytes
        monkeypatch.setattr(fileops, "_same_bytes",
                            lambda a, b: events.append(("compare", Path(b).name)) or real_same(a, b))
        src = tmp_path / "src.bin"
        src.write_bytes(b"new!")
        fileops.copy_preserving(src, tmp_path / "dst.bin", verify_content=True)
        assert events[-2:] == [("sleep",), ("compare", "dst.bin")]

    @pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="no FIFOs here")
    def test_a_target_that_is_no_regular_file_is_refused(self, tmp_path):
        src = tmp_path / "src.bin"
        src.write_bytes(b"data")
        fifo = tmp_path / "pipe"
        os.mkfifo(fifo)
        with pytest.raises(ValueError, match="regular file"):
            fileops.copy_preserving(src, fifo, verify_content=True)
        assert fifo.exists() and not fifo.is_file()

    def test_the_mergerfs_fallback_never_writes_through_a_name_that_appeared_late(
            self, tmp_path, monkeypatch):
        _no_rename(monkeypatch)
        src = tmp_path / "src.bin"
        src.write_bytes(b"new!")
        victim = tmp_path / "victim.bin"
        victim.write_bytes(b"precious")
        dst = tmp_path / "dst.bin"
        real_open = os.open
        def open_after_plant(path, flags, mode=0o777, **kw):
            if Path(path) == dst and not dst.is_symlink():
                dst.symlink_to(victim)
            return real_open(path, flags, mode, **kw)
        monkeypatch.setattr(fileops.os, "open", open_after_plant)
        with pytest.raises(OSError, match="cannot replace"):
            fileops.copy_preserving(src, dst, verify_content=True)
        assert victim.read_bytes() == b"precious"
        assert dst.is_symlink()
        assert sorted(x.name for x in tmp_path.iterdir()) == ["dst.bin", "src.bin", "victim.bin"]
