# This file is part of the kista Project.
# License: GPL-3.0-or-later. Contact: kista-project@trinity2k.net
#

import pytest

from kista.arch import detect_arch, is_macos


class TestDetectArch:
    @pytest.mark.parametrize("filename, expected", [
        ("FreeTube-0.25.1-linux-amd64.AppImage", "x86_64"),
        ("86Box-Linux-x86_64-b8200.AppImage", "x86_64"),
        ("luducat-0.8.4c-x86_64-anylinux.AppImage", "x86_64"),
        ("Something-x86-64.AppImage", "x86_64"),
        ("app-x64.AppImage", "x86_64"),
    ])
    def test_x86_64(self, filename, expected):
        assert detect_arch(filename) == expected

    @pytest.mark.parametrize("filename, expected", [
        ("app-aarch64.AppImage", "aarch64"),
        ("app-arm64.AppImage", "aarch64"),
    ])
    def test_aarch64(self, filename, expected):
        assert detect_arch(filename) == expected

    @pytest.mark.parametrize("filename, expected", [
        ("app-i686.AppImage", "i686"),
        ("app-i386.AppImage", "i686"),
    ])
    def test_i686(self, filename, expected):
        assert detect_arch(filename) == expected

    @pytest.mark.parametrize("filename, expected", [
        ("app-armhf.AppImage", "armhf"),
        ("app-armv7l.AppImage", "armhf"),
    ])
    def test_armhf(self, filename, expected):
        assert detect_arch(filename) == expected

    @pytest.mark.parametrize("filename", [
        "alarm-clock-1.2.AppImage",
        "charm-3.0.AppImage",
        "swarm-manager.AppImage",
        "garmin-connect.AppImage",
        "farming-sim.AppImage",
    ])
    def test_false_positives_rejected(self, filename):
        assert detect_arch(filename) is None

    def test_empty_string(self):
        assert detect_arch("") is None

    def test_no_arch(self):
        assert detect_arch("pCloud.AppImage") is None


class TestIsMacos:
    @pytest.mark.parametrize("filename", [
        "app-macos.zip",
        "app-osx.tar.gz",
        "app-darwin-x64.tar.gz",
        "app-mac-universal.dmg",
        "app-apple-silicon.tar.gz",
        "app.dmg",
        "app.sit",
        "app.hqx",
    ])
    def test_macos_detected(self, filename):
        assert is_macos(filename) is True

    @pytest.mark.parametrize("filename", [
        "app-linux-x86_64.AppImage",
        "app-windows.exe",
        "machine-learning.tar.gz",
    ])
    def test_non_macos(self, filename):
        assert is_macos(filename) is False
