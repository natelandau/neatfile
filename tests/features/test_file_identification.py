"""Tests for the identify_files controller."""

from pathlib import Path

import cappa
import pytest

from neatfile import settings
from neatfile.cli import NeatFile, config_subcommand
from neatfile.features import find_processable_files


@pytest.fixture
def mock_files(tmp_path: Path) -> Path:
    """Create a test directory with a few files and directories.

    Returns:
        The path to the test directory.
    """
    dirs = [
        tmp_path / "one",
        tmp_path / "two",
        tmp_path / "two" / "three",
        tmp_path / "two" / "four",
        tmp_path / "two" / "four" / "five",
    ]

    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    files = [
        tmp_path / "file1.txt",
        tmp_path / "file2.txt",
        tmp_path / ".dotfile",
        tmp_path / "one" / "file1.txt",
        tmp_path / "one" / "file2.txt",
        tmp_path / "two" / "file1.txt",
        tmp_path / "two" / "three" / "file1.txt",
        tmp_path / "two" / "four" / "file1.txt",
        tmp_path / "two" / "four" / "five" / "file1.txt",
    ]
    for file in files:
        file.touch()

    tmp_path.joinpath("file3.txt").symlink_to(tmp_path.joinpath("file2.txt"))

    return tmp_path


def test_respect_ignore_file_regex(mock_files, clean_stdout, debug):
    """Verify ignore_file_regex is respected."""
    # Given: ignore_file_regex is configured to ignore file2.txt
    settings.update({"ignore_file_regex": "^file2.txt$"})

    # When: Finding processable files
    files = find_processable_files([mock_files])

    # Then: Only file1.txt is found, file2.txt is ignored
    assert len(files) == 1
    assert files == [mock_files / "file1.txt"]
    assert mock_files / "file2.txt" not in files


def test_respect_ignore_files(mock_files, clean_stdout, debug):
    """Verify ignore_files is respected."""
    # Given: ignored_files is configured to ignore file2.txt
    settings.update({"ignored_files": ["file2.txt"]})

    # When: Finding processable files
    files = find_processable_files([mock_files])

    # Then: Only file1.txt is found, file2.txt is ignored
    assert len(files) == 1
    assert files == [mock_files / "file1.txt"]
    assert mock_files / "file2.txt" not in files


def test_dont_find_symlink(mock_files, clean_stdout, debug):
    """Verify symlinks are skipped and not processed."""
    # Given: A symlink file path
    args = ["clean", "-v", f"{mock_files}/file3.txt"]

    # When: Attempting to process the symlink
    with pytest.raises(cappa.Exit):
        cappa.invoke(obj=NeatFile, argv=args, deps=[config_subcommand])

    # Then: Warning is shown and no files are found
    output = clean_stdout()
    assert "Warning: Symlink" in output
    assert "No files found" in output


def test_dont_find_dotfiles(mock_files, clean_stdout, debug):
    """Verify dotfiles are ignored and not processed."""
    # Given: A dotfile path
    args = ["clean", "-v", f"{mock_files}/.dotfile"]

    # When: Attempting to process the dotfile
    with pytest.raises(cappa.Exit):
        cappa.invoke(obj=NeatFile, argv=args, deps=[config_subcommand])

    # Then: File is ignored and no files are found
    output = clean_stdout()
    assert "Ignored:" in output
    assert "No files found" in output


def test_find_multiple_files_in_directory_path(mock_files, debug):
    """Verify multiple files in a directory are found and processed."""
    files = find_processable_files([mock_files / "one"])
    # debug(settings.to_dict())
    # debug(mock_files / "one")
    # debug(files)
    assert len(files) == 2
    assert files == [mock_files / "one" / "file1.txt", mock_files / "one" / "file2.txt"]


def test_find_files_in_directory_path(mock_files, debug):
    """Verify files in a directory are found and processed."""
    files = find_processable_files([mock_files / "two"])
    # debug(files)
    assert len(files) == 1
    assert files == [mock_files / "two" / "file1.txt"]


def test_exit_if_path_does_not_exist(mock_files, debug):
    """Verify files in a directory are found and processed."""
    with pytest.raises(cappa.Exit):
        find_processable_files([mock_files / "two" / "does_not_exist"])


def test_find_files_in_directory_path_with_depth_2(mock_files, debug):
    """Verify files in a directory are found and processed."""
    settings.update({"file_search_depth": 2})
    files = find_processable_files([mock_files / "two"])
    # debug(files)
    assert len(files) == 3
    assert files == [
        mock_files / "two" / "file1.txt",
        mock_files / "two" / "four" / "file1.txt",
        mock_files / "two" / "three" / "file1.txt",
    ]


def test_find_files_in_directory_path_with_depth_3(mock_files, debug):
    """Verify files in a directory are found and processed."""
    settings.update({"file_search_depth": 3})
    files = find_processable_files([mock_files / "two"])
    # debug(files)
    assert len(files) == 4
    assert files == [
        mock_files / "two" / "file1.txt",
        mock_files / "two" / "four" / "file1.txt",
        mock_files / "two" / "four" / "five" / "file1.txt",
        mock_files / "two" / "three" / "file1.txt",
    ]
