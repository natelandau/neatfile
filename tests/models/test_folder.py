"""Tests for the Folder model."""

from neatfile.constants import FolderType
from neatfile.models.folder import Folder


def test_read_neatfile(tmp_path):
    """Test that the read_neatfile method returns the correct folder."""
    # Given: A folder with a .neatfile file
    directory = tmp_path / "the_test_folder"
    directory.mkdir()
    (directory / ".neatfile").write_text("koala\nfoo\n# bar")

    folder = Folder(directory, FolderType.OTHER)
    assert folder.terms == {"folder", "foo", "koala", "test"}
    assert folder.number is None


def test_keep_stopwords_if_empty_terms(tmp_path):
    """Test that the read_neatfile method returns the correct folder."""
    # Given: A folder with a .neatfile file
    directory = tmp_path / "the_two"
    directory.mkdir()

    folder = Folder(directory, FolderType.OTHER)
    assert folder.terms == {"the", "two"}
    assert folder.number is None
