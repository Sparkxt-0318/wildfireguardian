import subprocess

import pytest

from wildfire.farsite_observed_build import (
    _apply_validated_observed_patches, _clock_assignments_patch, build_observed_engine,
)


SOURCE = """#include <sys/sendfile.h>
void CopyFile(char *in, char *out, bool unused)
{
    sendfile(write_fd, read_fd, &offset, stat_buf.st_size);
}
#endif
double physical_spread(double r) { return r * 1.2345; }
void load_clocks() {
   SetStartHour  (icf.i_FarsiteStartHour);
   SetEndHour    (icf.i_FarsiteEndHour);
}
"""


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_clock_patch_is_idempotent_and_preserves_physics_and_newlines(tmp_path, newline):
    (tmp_path / "src").mkdir()
    source = tmp_path / "src" / "Farsite5.cpp"
    source.write_bytes(SOURCE.replace("\n", newline).encode())
    _clock_assignments_patch(tmp_path)
    first = source.read_bytes()
    _clock_assignments_patch(tmp_path)
    assert source.read_bytes() == first
    assert b"physical_spread(double r) { return r * 1.2345; }" in first
    for endpoint in (b"Start", b"End"):
        space = b"  " if endpoint == b"Start" else b"    "
        assert b"Set" + endpoint + b"Hour" + space + b"((icf.i_Farsite" + endpoint + b"Hour / 100) * 100);" in first
        assert b"Set" + endpoint + b"Min   (icf.i_Farsite" + endpoint + b"Hour % 100);" in first
    if newline == "\r\n":
        assert b"\n" not in first.replace(b"\r\n", b"")


def test_clock_patch_rejects_unexpected_or_duplicate_assignments(tmp_path):
    (tmp_path / "src").mkdir()
    source = tmp_path / "src" / "Farsite5.cpp"
    source.write_text(SOURCE + "\nSetStartHour  (icf.i_FarsiteStartHour);\n")
    with pytest.raises(RuntimeError, match="exactly once"):
        _clock_assignments_patch(tmp_path)


@pytest.fixture
def pinned_source(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "Farsite5.cpp").write_text(SOURCE)
    (tmp_path / "src" / "spread.cpp").write_text("double spread = 7.0;\n")
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True)
    subprocess.run(["git", "add", "src"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                    "commit", "--quiet", "-m", "Pinned fixture"], cwd=tmp_path, check=True)
    return tmp_path


def test_validated_observed_patch_accepts_only_documented_idempotent_changes(pinned_source):
    _apply_validated_observed_patches(pinned_source, "Darwin")
    first = (pinned_source / "src" / "Farsite5.cpp").read_bytes()
    _apply_validated_observed_patches(pinned_source, "Darwin")
    assert (pinned_source / "src" / "Farsite5.cpp").read_bytes() == first


def test_validated_observed_patch_rejects_unrelated_model_edit(pinned_source):
    source = pinned_source / "src" / "Farsite5.cpp"
    source.write_text(source.read_text().replace("r * 1.2345", "r * 9.0"))
    with pytest.raises(RuntimeError, match="differs from the pinned"):
        _apply_validated_observed_patches(pinned_source, "Darwin")


def test_validated_observed_patch_rejects_other_tracked_edits(pinned_source):
    (pinned_source / "src" / "spread.cpp").write_text("double spread = 99.0;\n")
    with pytest.raises(RuntimeError, match="unrelated tracked edits"):
        _apply_validated_observed_patches(pinned_source, "Darwin")


@pytest.mark.parametrize("jobs", [0, -1, True, 1.5])
def test_invalid_jobs_rejected_before_copy(tmp_path, jobs):
    directory = tmp_path / "never_created"
    with pytest.raises(ValueError, match="positive integer"):
        build_observed_engine(directory, original_source_dir=tmp_path / "original", jobs=jobs)
    assert not directory.exists()


@pytest.mark.parametrize("relative", ["original", "original/nested", "."])
def test_original_or_nested_directories_are_rejected(tmp_path, relative):
    with pytest.raises(ValueError, match="separate directory"):
        build_observed_engine(tmp_path / relative, original_source_dir=tmp_path / "original")


def test_exact_hhmm_split_corrects_nonintegral_clock_arithmetic():
    # Native ConvertActualTimeToSimtime uses HH00 / 100 * 60 + minute.
    def native_minutes(hhmm):
        hour = (hhmm // 100) * 100
        minute = hhmm % 100
        return hour / 100 * 60 + minute

    assert 1440 + native_minutes(214) - native_minutes(802) == 1092
    assert 1440 + 214 / 100 * 60 - 802 / 100 * 60 != 1092
