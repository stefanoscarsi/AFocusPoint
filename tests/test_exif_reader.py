import pytest

from core import exif_reader


def _no_exiftool_on_path(monkeypatch):
    monkeypatch.setattr(exif_reader.shutil, "which", lambda name: None)


def test_find_exiftool_prefers_the_path(monkeypatch):
    monkeypatch.setattr(exif_reader.shutil, "which", lambda name: "/some/where/exiftool")
    assert exif_reader.find_exiftool() == "/some/where/exiftool"


def test_find_exiftool_falls_back_to_homebrew_on_macos(monkeypatch, tmp_path):
    # An app launched from Finder only gets /usr/bin:/bin:/usr/sbin:/sbin,
    # so ExifTool installed by Homebrew is not on its PATH.
    _no_exiftool_on_path(monkeypatch)
    fake_exe = tmp_path / "exiftool"
    fake_exe.write_text("")
    monkeypatch.setattr(exif_reader.sys, "platform", "darwin")
    monkeypatch.setattr(exif_reader, "_MACOS_FALLBACK_DIRS", ("/nonexistent", str(tmp_path)))
    assert exif_reader.find_exiftool() == str(fake_exe)


def test_find_exiftool_does_not_use_macos_fallbacks_on_windows(monkeypatch, tmp_path):
    _no_exiftool_on_path(monkeypatch)
    (tmp_path / "exiftool").write_text("")
    monkeypatch.setattr(exif_reader.sys, "platform", "win32")
    monkeypatch.setattr(exif_reader, "_MACOS_FALLBACK_DIRS", (str(tmp_path),))
    with pytest.raises(exif_reader.ExifToolNotFoundError):
        exif_reader.find_exiftool()


def test_find_exiftool_raises_when_missing_everywhere(monkeypatch):
    _no_exiftool_on_path(monkeypatch)
    monkeypatch.setattr(exif_reader.sys, "platform", "darwin")
    monkeypatch.setattr(exif_reader, "_MACOS_FALLBACK_DIRS", ("/nonexistent",))
    with pytest.raises(exif_reader.ExifToolNotFoundError):
        exif_reader.find_exiftool()


def test_find_exiftool_disables_current_directory_search_on_windows(monkeypatch):
    # Otherwise Windows looks for exiftool.exe in the current folder before
    # the PATH, so a stray one next to the photos would run instead.
    monkeypatch.delenv("NoDefaultCurrentDirectoryInExePath", raising=False)
    monkeypatch.setattr(exif_reader.shutil, "which", lambda name: r"C:\Tools\exiftool.exe")
    monkeypatch.setattr(exif_reader.sys, "platform", "win32")
    exif_reader.find_exiftool()
    assert exif_reader.os.environ["NoDefaultCurrentDirectoryInExePath"] == "1"


def test_safe_path_is_always_absolute(tmp_path, monkeypatch):
    # An absolute path can never start with "-", which ExifTool would read
    # as an option.
    monkeypatch.chdir(tmp_path)
    assert exif_reader._safe_path("-foto.CR3") == str(tmp_path / "-foto.CR3")


@pytest.mark.parametrize("name", ["foto\nx.CR3", "foto\rx.CR3", "foto\x00x.CR3", "foto\tx.CR3"])
def test_safe_path_rejects_control_characters(tmp_path, name):
    with pytest.raises(ValueError):
        exif_reader._safe_path(tmp_path / name)


def test_metadata_is_never_requested_for_a_rejected_file_name(monkeypatch, tmp_path):
    def must_not_start(*args, **kwargs):
        raise AssertionError("ExifTool must not be started for an invalid file name")

    monkeypatch.setattr(exif_reader.exiftool, "ExifToolHelper", must_not_start)
    monkeypatch.setattr(exif_reader.subprocess, "run", must_not_start)
    with pytest.raises(ValueError):
        exif_reader.read_all_metadata(tmp_path / "foto\nx.CR3")
    with pytest.raises(ValueError):
        exif_reader.extract_binary_tag(tmp_path / "foto\nx.CR3", "PreviewImage")
