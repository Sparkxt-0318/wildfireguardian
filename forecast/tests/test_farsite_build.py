import subprocess

import pytest

from wildfire.farsite_build import (
    _apply_validated_patches,
    _macos_copy_patch,
    _pointer_syntax_patch,
    build_engine,
)


SOURCE = """#include <sys/sendfile.h>
void CopyFile(char *in, char *out, bool unused)
{
    sendfile(write_fd, read_fd, &offset, stat_buf.st_size);
}
#endif
double physical_spread(double r) { return r * 1.2345; }
double* AllocPerimeter1(long NumFire)
{
    if (perimeter1[NumFire] && perimeter1[NumFire] > 0)
        FreePerimeter1(NumFire);
}
long* Farsite5::GetElevAddress(long Num)
{
\tif (!GroundElev)
\t\treturn (long) NULL;
    return &GroundElev[Num];
}
"""


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_portability_changes_are_idempotent_and_preserve_model_and_newlines(tmp_path, newline):
    (tmp_path / "src").mkdir()
    source = tmp_path / "src" / "Farsite5.cpp"
    source.write_bytes(SOURCE.replace("\n", newline).encode())
    _macos_copy_patch(tmp_path)
    _pointer_syntax_patch(tmp_path)
    first = source.read_bytes()
    _macos_copy_patch(tmp_path)
    _pointer_syntax_patch(tmp_path)
    assert source.read_bytes() == first
    assert b"physical_spread(double r) { return r * 1.2345; }" in first
    assert b"copyfile(in, out, NULL, COPYFILE_DATA | COPYFILE_STAT)" in first
    assert b"sendfile(write_fd, read_fd, &offset, stat_buf.st_size)" in first
    assert b"if (perimeter1[NumFire] != NULL)" in first
    assert b"return (long) NULL;" not in first
    if newline == "\r\n":
        assert b"\n" not in first.replace(b"\r\n", b"")


def test_copy_shim_rejects_unexpected_source(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "Farsite5.cpp").write_text("unrelated source")
    with pytest.raises(RuntimeError, match="exactly once"):
        _macos_copy_patch(tmp_path)


@pytest.mark.parametrize("jobs", [0, -1, True, 1.5])
def test_invalid_jobs_rejected_before_acquisition(tmp_path, jobs):
    directory = tmp_path / "never_created"
    with pytest.raises(ValueError, match="positive integer"):
        build_engine(directory, jobs=jobs)
    assert not directory.exists()


@pytest.fixture
def pinned_source(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "Farsite5.cpp").write_bytes(SOURCE.encode())
    (tmp_path / "src" / "spread.cpp").write_text("double spread = 7.0;\n")
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True)
    subprocess.run(["git", "add", "src"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                    "commit", "--quiet", "-m", "Pinned fixture"], cwd=tmp_path, check=True)
    return tmp_path


def test_validated_patches_allow_only_documented_idempotent_changes(pinned_source):
    assert _apply_validated_patches(pinned_source, "Darwin") is True
    first = (pinned_source / "src" / "Farsite5.cpp").read_bytes()
    assert _apply_validated_patches(pinned_source, "Darwin") is True
    assert (pinned_source / "src" / "Farsite5.cpp").read_bytes() == first


def test_validated_patches_reject_model_change_in_patched_file(pinned_source):
    source = pinned_source / "src" / "Farsite5.cpp"
    source.write_text(source.read_text().replace("r * 1.2345", "r * 9.0"))
    with pytest.raises(RuntimeError, match="differs from the pinned"):
        _apply_validated_patches(pinned_source, "Darwin")


def test_validated_patches_reject_model_change_in_other_file(pinned_source):
    (pinned_source / "src" / "spread.cpp").write_text("double spread = 99.0;\n")
    with pytest.raises(RuntimeError, match="unrelated tracked edits"):
        _apply_validated_patches(pinned_source, "Darwin")


def test_linux_pointer_fixes_preserve_upstream_copy_api(pinned_source):
    assert _apply_validated_patches(pinned_source, "Linux") is False
    source = (pinned_source / "src" / "Farsite5.cpp").read_text()
    assert "copyfile(" not in source
    assert "sendfile(write_fd, read_fd, &offset, stat_buf.st_size)" in source
    assert "if (perimeter1[NumFire] != NULL)" in source
