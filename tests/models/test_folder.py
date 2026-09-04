"""Tests for the Folder model."""

import pytest

from neatfile.constants import NEATFILE_NAME, FolderType
from neatfile.models.folder import Folder


def test_read_neatfile(tmp_path) -> None:
    """Test that the read_neatfile method returns the correct folder."""
    # Given: A folder with a .neatfile file
    directory = tmp_path / "the_test_folder"
    directory.mkdir()
    (directory / NEATFILE_NAME).write_text("koala\nfoo\n# bar")

    folder = Folder(directory, FolderType.OTHER)
    assert folder.terms == {"folder", "foo", "koala", "test"}
    assert folder.number is None


def test_keep_stopwords_if_empty_terms(tmp_path) -> None:
    """Test that the read_neatfile method returns the correct folder."""
    # Given: A folder with a .neatfile file
    directory = tmp_path / "the_two"
    directory.mkdir()

    folder = Folder(directory, FolderType.OTHER)
    assert folder.terms == {"the", "two"}
    assert folder.number is None


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

    folder = Folder(directory, folder_type)

    assert folder.name == expected_name
    assert folder.number == expected_number
