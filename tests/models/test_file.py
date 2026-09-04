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
    ],
)
def test_file_splits_compound_extensions(tmp_path: Path, name: str, stem: str, suffix: str) -> None:
    """Verify the stem and suffix keep compound extensions together."""
    file = File(tmp_path / name)
    assert file.stem == stem
    assert file.suffix == suffix
    assert file.new_name == name
