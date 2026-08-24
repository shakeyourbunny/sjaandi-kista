# This file is part of the kista Project.
# License: GPL-3.0-or-later. Contact: kista-project@trinity2k.net
#

import textwrap

from kista.checkreqs import check_deps, format_install_instructions, load_manifest


def _write_manifest(tmp_path, content):
    p = tmp_path / "deps.toml"
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


class TestLoadManifest:
    def test_basic(self, tmp_path):
        m = _write_manifest(tmp_path, """\
            [deps.ghostscript]
            binary = "gs"
            description = "PDF optimization"
            [deps.ghostscript.packages]
            apt = "ghostscript"
            dnf = "ghostscript"
        """)
        deps = load_manifest(m)
        assert len(deps) == 1
        assert deps[0].name == "ghostscript"
        assert deps[0].binary == "gs"
        assert deps[0].packages["apt"] == "ghostscript"
        assert deps[0].optional is False

    def test_optional_flag(self, tmp_path):
        m = _write_manifest(tmp_path, """\
            [deps.pngquant]
            binary = "pngquant"
            optional = true
            description = "PNG compression"
            [deps.pngquant.packages]
            apt = "pngquant"
        """)
        deps = load_manifest(m)
        assert deps[0].optional is True

    def test_check_command(self, tmp_path):
        m = _write_manifest(tmp_path, """\
            [deps.tessdata-eng]
            binary = ""
            check_command = "tesseract --list-langs 2>&1 | grep -q eng"
            description = "English tessdata"
            [deps.tessdata-eng.packages]
            apt = "tesseract-ocr-eng"
        """)
        deps = load_manifest(m)
        assert deps[0].binary == ""
        assert "tesseract" in deps[0].check_command

    def test_repo_prerequisites(self, tmp_path):
        m = _write_manifest(tmp_path, """\
            [deps.tool]
            binary = "tool"
            description = "needs EPEL"
            [deps.tool.packages]
            dnf = "tool-pkg"
            [deps.tool.repo]
            dnf = "epel-release"
        """)
        deps = load_manifest(m)
        assert deps[0].repo["dnf"] == "epel-release"

    def test_multiple_deps(self, tmp_path):
        m = _write_manifest(tmp_path, """\
            [deps.gs]
            binary = "gs"
            description = "ghostscript"
            [deps.gs.packages]
            apt = "ghostscript"

            [deps.qpdf]
            binary = "qpdf"
            description = "qpdf"
            [deps.qpdf.packages]
            apt = "qpdf"
        """)
        deps = load_manifest(m)
        assert len(deps) == 2

    def test_empty_manifest(self, tmp_path):
        m = _write_manifest(tmp_path, "# nothing here\n")
        deps = load_manifest(m)
        assert deps == []


class TestCheckDeps:
    def test_all_found(self, tmp_path):
        m = _write_manifest(tmp_path, """\
            [deps.python3]
            binary = "python3"
            description = "Python"
            [deps.python3.packages]
            apt = "python3"
        """)
        deps = load_manifest(m)
        result = check_deps(deps)
        assert len(result.missing) == 0
        assert len(result.found) == 1

    def test_missing_binary(self, tmp_path):
        m = _write_manifest(tmp_path, """\
            [deps.nonexistent]
            binary = "definitely_not_installed_xyz_42"
            description = "not real"
            [deps.nonexistent.packages]
            apt = "nonexistent-pkg"
        """)
        deps = load_manifest(m)
        result = check_deps(deps)
        assert len(result.missing) == 1
        assert result.missing[0].name == "nonexistent"

    def test_optional_missing_separate(self, tmp_path):
        m = _write_manifest(tmp_path, """\
            [deps.nonexistent]
            binary = "definitely_not_installed_xyz_42"
            optional = true
            description = "not real"
            [deps.nonexistent.packages]
            apt = "nonexistent-pkg"
        """)
        deps = load_manifest(m)
        result = check_deps(deps)
        assert len(result.missing) == 0
        assert len(result.optional_missing) == 1

    def test_no_binary_no_check_command_is_available(self, tmp_path):
        m = _write_manifest(tmp_path, """\
            [deps.meta]
            binary = ""
            description = "no check"
            [deps.meta.packages]
            apt = "meta-pkg"
        """)
        deps = load_manifest(m)
        result = check_deps(deps)
        assert len(result.found) == 1
        assert len(result.missing) == 0

    def test_check_command_true(self, tmp_path):
        m = _write_manifest(tmp_path, """\
            [deps.truecmd]
            binary = ""
            check_command = "true"
            description = "always succeeds"
            [deps.truecmd.packages]
            apt = "truecmd"
        """)
        deps = load_manifest(m)
        result = check_deps(deps)
        assert len(result.found) == 1

    def test_check_command_false(self, tmp_path):
        m = _write_manifest(tmp_path, """\
            [deps.falsecmd]
            binary = ""
            check_command = "false"
            description = "always fails"
            [deps.falsecmd.packages]
            apt = "falsecmd"
        """)
        deps = load_manifest(m)
        result = check_deps(deps)
        assert len(result.missing) == 1


class TestFormatInstallInstructions:
    def test_apt_output(self, tmp_path):
        m = _write_manifest(tmp_path, """\
            [deps.ghostscript]
            binary = "definitely_not_gs_xyz_42"
            description = "PDF optimization"
            [deps.ghostscript.packages]
            apt = "ghostscript"
            dnf = "ghostscript"
        """)
        deps = load_manifest(m)
        result = check_deps(deps)
        lines = format_install_instructions(result, "apt")
        text = "\n".join(lines)
        assert "sudo apt install" in text
        assert "ghostscript" in text

    def test_dnf_output(self, tmp_path):
        m = _write_manifest(tmp_path, """\
            [deps.ghostscript]
            binary = "definitely_not_gs_xyz_42"
            description = "PDF optimization"
            [deps.ghostscript.packages]
            dnf = "ghostscript"
        """)
        deps = load_manifest(m)
        result = check_deps(deps)
        lines = format_install_instructions(result, "dnf")
        text = "\n".join(lines)
        assert "sudo dnf install" in text

    def test_pacman_output(self, tmp_path):
        m = _write_manifest(tmp_path, """\
            [deps.ghostscript]
            binary = "definitely_not_gs_xyz_42"
            description = "PDF optimization"
            [deps.ghostscript.packages]
            pacman = "ghostscript"
        """)
        deps = load_manifest(m)
        result = check_deps(deps)
        lines = format_install_instructions(result, "pacman")
        text = "\n".join(lines)
        assert "sudo pacman -S" in text

    def test_zypper_output(self, tmp_path):
        m = _write_manifest(tmp_path, """\
            [deps.ghostscript]
            binary = "definitely_not_gs_xyz_42"
            description = "PDF optimization"
            [deps.ghostscript.packages]
            zypper = "ghostscript"
        """)
        deps = load_manifest(m)
        result = check_deps(deps)
        lines = format_install_instructions(result, "zypper")
        text = "\n".join(lines)
        assert "sudo zypper install" in text

    def test_unknown_family_lists_generically(self, tmp_path):
        m = _write_manifest(tmp_path, """\
            [deps.ghostscript]
            binary = "definitely_not_gs_xyz_42"
            description = "PDF optimization"
            [deps.ghostscript.packages]
            apt = "ghostscript"
        """)
        deps = load_manifest(m)
        result = check_deps(deps)
        lines = format_install_instructions(result, "unknown")
        text = "\n".join(lines)
        assert "ghostscript" in text
        assert "sudo" not in text

    def test_repo_prerequisite_shown(self, tmp_path):
        m = _write_manifest(tmp_path, """\
            [deps.tool]
            binary = "definitely_not_tool_xyz_42"
            description = "needs EPEL"
            [deps.tool.packages]
            dnf = "tool-pkg"
            [deps.tool.repo]
            dnf = "epel-release"
        """)
        deps = load_manifest(m)
        result = check_deps(deps)
        lines = format_install_instructions(result, "dnf")
        text = "\n".join(lines)
        assert "epel-release" in text
        assert "tool-pkg" in text

    def test_nothing_missing_returns_empty(self, tmp_path):
        m = _write_manifest(tmp_path, """\
            [deps.python3]
            binary = "python3"
            description = "Python"
            [deps.python3.packages]
            apt = "python3"
        """)
        deps = load_manifest(m)
        result = check_deps(deps)
        lines = format_install_instructions(result, "apt")
        assert lines == []

    def test_optional_and_required_separated(self, tmp_path):
        m = _write_manifest(tmp_path, """\
            [deps.required]
            binary = "definitely_not_xyz_42"
            description = "required tool"
            [deps.required.packages]
            apt = "required-pkg"

            [deps.optional]
            binary = "definitely_not_xyz_43"
            optional = true
            description = "optional tool"
            [deps.optional.packages]
            apt = "optional-pkg"
        """)
        deps = load_manifest(m)
        result = check_deps(deps)
        lines = format_install_instructions(result, "apt")
        text = "\n".join(lines)
        assert "Required tools missing" in text
        assert "Optional tools" in text
        assert "required-pkg" in text
        assert "optional-pkg" in text
