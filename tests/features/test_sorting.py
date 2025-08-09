"""Tests for the file organizer controller."""

from pathlib import Path

import pytest

from neatfile.constants import NEATFILE_IGNORE_NAME, ProjectType
from neatfile.features.sorting import (
    _calculate_folder_score,
    _calculate_token_similarity,
    _find_best_match_for_token,
    _find_matching_folders,
    _process_folder_matches,
    _process_tokens_with_digits,
)
from neatfile.models import Folder, MatchResult
from neatfile.utils import nlp


@pytest.fixture
def mock_folder(tmp_path: Path):
    """Create a mock folder for testing.

    Returns:
        Folder: A mock folder for testing.
    """
    test_dir = tmp_path / "test_folder"
    test_dir.mkdir()
    return Folder(path=test_dir, folder_type=ProjectType.FOLDER)


# Tests for _calculate_token_similarity
def test_calculate_token_similarity_exact_match() -> None:
    """Verify exact lemma matches return similarity score of 1.0."""
    # Given: Two identical tokens
    file_doc = nlp("testing")
    folder_doc = nlp("testing")
    file_lemma = file_doc[0].lemma_
    folder_lemma = folder_doc[0].lemma_

    # When: Calculating similarity
    similarity = _calculate_token_similarity(file_doc, file_lemma, folder_doc, folder_lemma)

    # Then: Score should be 1.0 for exact match
    assert similarity == 1.0


def test_calculate_token_similarity_vector_similarity() -> None:
    """Verify vector similarity calculation for non-exact matches."""
    # Given: Two similar but different tokens
    file_doc = nlp("run")
    folder_doc = nlp("running")
    file_lemma = file_doc[0].lemma_
    folder_lemma = folder_doc[0].lemma_

    # When: Calculating similarity
    similarity = _calculate_token_similarity(file_doc, file_lemma, folder_doc, folder_lemma)

    # Then: Score should be between 0 and 1
    assert 0 <= similarity <= 1


# Tests for _find_best_match_for_token
def test_find_best_match_for_token_exact_match() -> None:
    """Verify finding best match when exact match exists."""
    # Given: A token and list of folder tokens including an exact match
    file_doc = nlp("test")
    file_lemma = file_doc[0].lemma_
    folder_docs = [nlp("other"), nlp("test"), nlp("folder")]
    folder_lemmas = [doc[0].lemma_ for doc in folder_docs]
    folder_tokens = ["other", "test", "folder"]
    threshold = 0.5

    # When: Finding best match
    best_match, score = _find_best_match_for_token(
        file_doc, file_lemma, folder_docs, folder_lemmas, folder_tokens, threshold
    )

    # Then: Should return exact match with score 1.0
    assert best_match == "test"
    assert score == 1.0


# Tests for _calculate_folder_score
def test_calculate_folder_score_perfect_match() -> None:
    """Verify score calculation for perfect matches."""
    # Given: Perfect match parameters
    total_score = 3.0
    match_count = 3
    total_tokens = 3

    # When: Calculating folder score
    score = _calculate_folder_score(total_score, match_count, total_tokens)

    # Then: Score should be 1.0 for perfect match
    assert score == 1.0


def test_calculate_folder_score_no_matches() -> None:
    """Verify score calculation when no matches found."""
    # Given: No match parameters
    total_score = 0.0
    match_count = 0
    total_tokens = 3

    # When: Calculating folder score
    score = _calculate_folder_score(total_score, match_count, total_tokens)

    # Then: Score should be 0.0 for no matches
    assert score == 0.0


# Tests for _process_tokens_with_digits
def test_process_tokens_with_digits_no_digits() -> None:
    """Verify processing tokens without digits."""
    # Given: Tokens without digits
    tokens = ["test", "folder"]

    # When: Processing tokens
    docs, lemmas, processed_tokens = _process_tokens_with_digits(tokens)

    # Then: Should return same number of items as input
    assert len(docs) == len(tokens)
    assert len(lemmas) == len(tokens)
    assert processed_tokens == tokens


def test_process_tokens_with_digits_with_digits() -> None:
    """Verify processing tokens containing digits."""
    # Given: Tokens with digits
    tokens = ["test123", "folder"]

    # When: Processing tokens
    _, _, processed_tokens = _process_tokens_with_digits(tokens)

    # Then: Should include additional processed versions
    assert len(processed_tokens) == 3  # Original tokens plus stripped version
    assert "test" in processed_tokens  # Stripped version should be included


# Tests for _process_folder_matches
def test_process_folder_matches_empty_folder(tmp_path: Path) -> None:
    """Verify handling of empty folder terms."""
    # Given: Empty folder and filename tokens
    empty_dir = tmp_path / "empty_folder"
    empty_dir.mkdir()
    empty_folder = Folder(path=empty_dir, folder_type=ProjectType.FOLDER)
    filename_docs = [nlp("test")]
    filename_lemmas = [doc[0].lemma_ for doc in filename_docs]
    token_match_threshold = 0.5
    filename_token_count = 1
    threshold = 0.6

    # When: Processing folder matches
    result = _process_folder_matches(
        empty_folder,
        filename_docs,
        filename_lemmas,
        token_match_threshold,
        filename_token_count,
        threshold,
    )

    # Then: Should return None for empty folder
    assert result is None


def test_process_folder_matches_good_match(mock_folder) -> None:
    """Verify matching process for good folder match."""
    # Given: Folder and matching filename tokens
    filename_docs = [nlp("test")]
    filename_lemmas = [doc[0].lemma_ for doc in filename_docs]
    token_match_threshold = 0.5
    filename_token_count = 1
    threshold = 0.6

    # When: Processing folder matches
    result = _process_folder_matches(
        mock_folder,
        filename_docs,
        filename_lemmas,
        token_match_threshold,
        filename_token_count,
        threshold,
    )

    # Then: Should return MatchResult with good score
    assert isinstance(result, MatchResult)
    assert result.score >= threshold
    assert mock_folder.path.exists()  # Verify the folder actually exists


# Tests for _find_matching_folders
def test_find_matching_folders_no_matches(tmp_path: Path) -> None:
    """Verify behavior when no matching folders found."""
    # Given: Filename tokens and non-matching folders
    test_dir = tmp_path / "different_folder"
    test_dir.mkdir()
    filename_tokens = ["unique"]
    folders = [Folder(path=test_dir, folder_type=ProjectType.FOLDER)]
    threshold = 0.6

    # When: Finding matching folders
    matches = _find_matching_folders(filename_tokens, folders, threshold)

    # Then: Should return empty list
    assert len(matches) == 0
    assert test_dir.exists()  # Verify the folder actually exists


def test_find_matching_folders_with_matches(tmp_path: Path) -> None:
    """Verify finding and sorting matching folders."""
    # Given: Filename tokens and matching folders
    path1 = tmp_path / "test_folder1"
    path2 = tmp_path / "test_folder2"
    path1.mkdir()
    path2.mkdir()

    filename_tokens = ["test"]
    folders = [
        Folder(path=path1, folder_type=ProjectType.FOLDER),
        Folder(path=path2, folder_type=ProjectType.FOLDER),
    ]
    threshold = 0.6

    # When: Finding matching folders
    matches = _find_matching_folders(filename_tokens, folders, threshold)

    # Then: Should return sorted list of matches
    assert len(matches) > 0
    assert all(isinstance(match, MatchResult) for match in matches)
    assert all(match.score >= threshold for match in matches)
    # Verify matches are sorted by score in descending order
    assert all(matches[i].score >= matches[i + 1].score for i in range(len(matches) - 1))
    # Verify the folders actually exist
    assert all(match.folder.path.exists() for match in matches)


def test_find_matching_folders_with_ignored_folders(tmp_path: Path) -> None:
    """Verify finding matching folders with ignored folders."""
    # Given: Filename tokens and matching folders
    path1 = tmp_path / "test_folder1"
    path2 = tmp_path / "test_folder2"
    path1.mkdir()
    path2.mkdir()
    (path2 / NEATFILE_IGNORE_NAME).touch()

    filename_tokens = ["test"]
    folders = [
        Folder(path=path1, folder_type=ProjectType.FOLDER),
        Folder(path=path2, folder_type=ProjectType.FOLDER),
    ]
    threshold = 0.6

    # When: Finding matching folders
    matches = _find_matching_folders(filename_tokens, folders, threshold)

    # Then: Should return one match
    assert len(matches) == 1
    assert matches[0].folder.path == path1
