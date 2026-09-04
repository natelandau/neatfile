"""Tests for the identify_files controller."""

from pathlib import Path

import cappa
import pytest
from nclutils import pp

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
        tmp_path / ".hidden",
        tmp_path / "two" / ".hidden",
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
        tmp_path / ".hidden" / "file1.txt",
        tmp_path / "two" / ".hidden" / "file1.txt",
    ]
    for file in files:
        file.touch()

    tmp_path.joinpath("file3.txt").symlink_to(tmp_path.joinpath("file2.txt"))
    tmp_path.joinpath("two", "linked_dir").symlink_to(tmp_path.joinpath("one"))

    return tmp_path


def test_respect_ignore_file_regex(mock_files, debug):
    """Verify ignore_file_regex is respected."""
    # Given: ignore_file_regex is configured to ignore file2.txt
    settings.update({"ignore_file_regex": "^file2.txt$"})

    # When: Finding processable files
    files = find_processable_files([mock_files])

    # Then: Only file1.txt is found, file2.txt is ignored
    assert len(files) == 1
    assert files == [mock_files / "file1.txt"]
    assert mock_files / "file2.txt" not in files


def test_respect_ignore_files(mock_files, debug):
    """Verify ignore_files is respected."""
    # Given: ignored_files is configured to ignore file2.txt
    settings.update({"ignored_files": ["file2.txt"]})

    # When: Finding processable files
    files = find_processable_files([mock_files])

    # Then: Only file1.txt is found, file2.txt is ignored
    assert len(files) == 1
    assert files == [mock_files / "file1.txt"]
    assert mock_files / "file2.txt" not in files


def test_dont_find_symlink(mock_files, capsys, debug):
    """Verify symlinks are skipped and not processed."""
    # Given: A symlink file path
    args = ["clean", "-v", f"{mock_files}/file3.txt"]

    # When: Attempting to process the symlink
    with pytest.raises(cappa.Exit):
        cappa.invoke(obj=NeatFile, argv=args, deps=[config_subcommand])

    # Then: Warning is shown and no files are found
    _, stderr = capsys.readouterr()
    assert "Symlink: `file3.txt`" in stderr
    assert "No files found" in stderr


def test_dont_find_dotfiles(mock_files, capsys, debug):
    """Verify dotfiles are ignored and not processed."""
    # Given: A dotfile path
    args = ["clean", "-v", f"{mock_files}/.dotfile"]

    # When: Attempting to process the dotfile
    with pytest.raises(cappa.Exit):
        cappa.invoke(obj=NeatFile, argv=args, deps=[config_subcommand])

    # Then: File is ignored and no files are found
    stdout, stderr = capsys.readouterr()
    assert "Ignored: `.dotfile`" in stdout
    assert "No files found" in stderr


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


def test_walk_explicit_dot_directory(mock_files, debug):
    """Verify a dot-directory named on the command line is walked even when ignore_dotfiles is true."""
    files = find_processable_files([mock_files / ".hidden"])
    assert files == [mock_files / ".hidden" / "file1.txt"]


def test_prune_dot_directories_during_walk(mock_files, debug):
    """Verify dot-directories met below the start path are skipped when ignore_dotfiles is true."""
    settings.update({"file_search_depth": 2})
    files = find_processable_files([mock_files / "two"])
    assert mock_files / "two" / ".hidden" / "file1.txt" not in files
    assert len(files) == 3


def test_walk_dot_directories_when_dotfiles_allowed(mock_files, debug):
    """Verify dot-directories below the start path are walked when ignore_dotfiles is false."""
    settings.update({"file_search_depth": 2, "ignore_dotfiles": False})
    files = find_processable_files([mock_files / "two"])
    assert mock_files / "two" / ".hidden" / "file1.txt" in files
    assert len(files) == 4


def test_dont_descend_symlinked_directory(mock_files, capsys, debug):
    """Verify a symlinked directory met during the walk is reported and not entered."""
    settings.update({"file_search_depth": 3})
    pp.configure(verbosity=1)
    files = find_processable_files([mock_files / "two"])
    _, stderr = capsys.readouterr()
    assert "Symlink: `" in stderr
    assert "linked_dir" in stderr
    assert not any("linked_dir" in str(f) for f in files)
    assert len(files) == 4
