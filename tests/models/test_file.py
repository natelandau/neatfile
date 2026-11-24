"""Tests for the File model."""

from pathlib import Path

import pytest

from neatfile.models.file import File


@pytest.mark.parametrize(
    ("name", "stem", "suffix"),
    [
        ("report.pdf", "report", ".pdf"),
        ("archive.tar.gz", "archive", ".tar.gz"),
        ("archive.tar.bz2", "archive", ".tar.bz2"),
        ("archive.tar.xz", "archive", ".tar.xz"),
        ("Archive.TAR.GZ", "Archive", ".TAR.GZ"),
        ("types.d.ts", "types", ".d.ts"),
        ("app.min.js", "app", ".min.js"),
        ("2024.01.report.pdf", "2024.01.report", ".pdf"),
        (".bashrc", ".bashrc", ""),
        (".hidden.tar.gz", ".hidden", ".tar.gz"),
        (".tar.gz", ".tar", ".gz"),
        ("noext", "noext", ""),
        ("Report v1.2 final", "Report v1.2 final", ""),
        ("meeting notes 3.5 2024", "meeting notes 3.5 2024", ""),
        ("notes 3.5 2024.txt", "notes 3.5 2024", ".txt"),
    ],
)
def test_file_splits_compound_extensions(tmp_path: Path, name: str, stem: str, suffix: str) -> None:
    """Verify the stem and suffix keep compound extensions together."""
    file = File(tmp_path / name)
    assert file.stem == stem
    assert file.suffix == suffix
    assert file.new_name == name


def test_file_same_folder_through_symlink_is_not_a_move(tmp_path: Path) -> None:
    """Verify a planned parent that resolves to the current folder does not count as a move."""
    real_folder = tmp_path / "real"
    real_folder.mkdir()
    linked_folder = tmp_path / "linked"
    linked_folder.symlink_to(real_folder)
    file = File(linked_folder / "x.txt")

    file.new_parent = real_folder

    assert not file.has_new_parent
    assert not file.has_changes
