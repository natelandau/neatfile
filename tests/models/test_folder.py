"""Tests for the Folder model."""

from pathlib import Path

import pytest

from neatfile.constants import NEATFILE_NAME, FolderType
from neatfile.models.folder import Folder


def test_read_neatfile(tmp_path) -> None:
    """Test that the read_neatfile method returns the correct folder."""
    # Given: A folder with a .neatfile file
    directory = tmp_path / "the_test_folder"
    directory.mkdir()
    (directory / NEATFILE_NAME).write_text("koala\nfoo\n# bar\n  # baz")

    folder = Folder(directory, FolderType.OTHER, strip_stopwords=True)
    assert folder.terms == {"folder", "foo", "koala", "test"}
    assert folder.number is None


def test_keep_stopwords_if_empty_terms(tmp_path) -> None:
    """Test that the read_neatfile method returns the correct folder."""
    # Given: A folder with a .neatfile file
    directory = tmp_path / "the_two"
    directory.mkdir()

    folder = Folder(directory, FolderType.OTHER, strip_stopwords=True)
    assert folder.terms == {"the", "two"}
    assert folder.number is None


def test_folder_terms_drop_matching_stopwords(tmp_path) -> None:
    """Verify folder names still lose broad stopwords such as ordinals and numbers."""
    directory = tmp_path / "part_two_invoices"
    directory.mkdir()

    folder = Folder(directory, FolderType.OTHER, strip_stopwords=True)

    assert folder.terms == {"invoices"}


def test_folder_terms_keep_possessives_whole(tmp_path) -> None:
    """Verify a possessive folder name yields the same term as a cleaned filename."""
    directory = tmp_path / "John's Invoices"
    directory.mkdir()

    folder = Folder(directory, FolderType.OTHER, strip_stopwords=True)

    assert folder.terms == {"johns", "invoices"}


@pytest.mark.parametrize(
    ("dirname", "folder_type", "expected_name", "expected_number"),
    [
        ("10-19 Finance", FolderType.AREA, "Finance", "10-19"),
        ("10-19_Finance", FolderType.AREA, "Finance", "10-19"),
        ("10-19-Finance", FolderType.AREA, "Finance", "10-19"),
        ("11 Bank Accounts", FolderType.CATEGORY, "Bank Accounts", "11"),
        ("11_Bank", FolderType.CATEGORY, "Bank", "11"),
        ("11.01 Checking", FolderType.SUBCATEGORY, "Checking", "11.01"),
        ("11.01-Checking", FolderType.SUBCATEGORY, "Checking", "11.01"),
        ("plain folder", FolderType.OTHER, "plain folder", None),
    ],
)
def test_name_and_number_strip_jd_prefix(
    tmp_path, dirname, folder_type, expected_name, expected_number
) -> None:
    """Verify the JD prefix is split into number and name for each folder type."""
    directory = tmp_path / dirname
    directory.mkdir()

    folder = Folder(directory, folder_type, strip_stopwords=True)

    assert folder.name == expected_name
    assert folder.number == expected_number


def test_number_is_none_when_jd_prefix_missing(tmp_path) -> None:
    """Verify a JD-typed folder without a JD prefix reports no number instead of raising."""
    directory = tmp_path / "Finance"
    directory.mkdir()

    folder = Folder(directory, FolderType.AREA, strip_stopwords=True)

    assert folder.number is None
    assert folder.name == "Finance"


def test_unreadable_neatfile_adds_no_terms(tmp_path) -> None:
    """Verify a .neatfile that is not UTF-8 text is skipped instead of stopping the run."""
    directory = tmp_path / "invoices"
    directory.mkdir()
    (directory / NEATFILE_NAME).write_bytes(b"\xff\xfe\x00koala")

    folder = Folder(directory, FolderType.OTHER, strip_stopwords=True)

    assert folder.terms == {"invoices"}


def test_symlinked_folder_keeps_its_project_path(tmp_path) -> None:
    """Verify a symbolic link to a folder elsewhere stays inside the project, so paths shown relative to the project work."""
    target = tmp_path / "elsewhere" / "invoices"
    target.mkdir(parents=True)
    link = tmp_path / "linked_project" / "invoices"
    link.parent.mkdir()
    link.symlink_to(target, target_is_directory=True)

    folder = Folder(link, FolderType.OTHER, strip_stopwords=True)

    assert folder.path.relative_to(tmp_path / "linked_project") == Path("invoices")
