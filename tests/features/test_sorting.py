"""Tests for the file organizer controller."""

from pathlib import Path

import pytest

from neatfile.constants import NEATFILE_IGNORE_NAME, ProjectType
from neatfile.features.sorting import (
    MATCH_THRESHOLD,
    TOKEN_THRESHOLD_FACTOR,
    Term,
    _calculate_folder_score,
    _calculate_token_similarity,
    _find_best_match_for_token,
    _find_matching_folders,
    _process_folder_matches,
    _process_tokens_with_digits,
)
from neatfile.models import Folder, MatchResult
from neatfile.utils import nlp


def term(token: str) -> Term:
    """Build a Term for a token as the matcher would.

    Returns:
        Term: The token, its lemma, and itself as the original.
    """
    return Term(token, nlp.lemmatize(token), token)


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
    # Given: Two tokens sharing a lemma
    # When: Calculating similarity
    similarity = _calculate_token_similarity(term("tests"), term("testing"))

    # Then: Score should be 1.0 for exact match
    assert similarity == 1.0


def test_calculate_token_similarity_vector_similarity() -> None:
    """Verify vector similarity is used when lemmas differ."""
    # Given: Two related tokens with different lemmas
    similarity = _calculate_token_similarity(term("photo"), term("pictures"))

    # Then: Score is a real similarity, not an exact-match sentinel
    assert 0 < similarity < 1


# Tests for _find_best_match_for_token
def test_find_best_match_for_token_exact_match() -> None:
    """Verify finding best match when exact match exists."""
    # Given: A token and list of folder tokens including an exact match
    folder_terms = (term("other"), term("test"), term("folder"))

    # When: Finding best match
    best_match, score = _find_best_match_for_token(term("test"), folder_terms, 0.5)

    # Then: Should return exact match with score 1.0
    assert best_match == term("test")
    assert score == 1.0


def test_find_best_match_for_token_below_threshold() -> None:
    """Verify no match is returned when nothing clears the token threshold."""
    # Given: Unrelated folder tokens
    folder_terms = (term("finance"), term("taxes"))

    # When: Finding best match for an unrelated token
    best_match, score = _find_best_match_for_token(term("dog"), folder_terms, 0.5)

    # Then: Nothing matched
    assert best_match is None
    assert score == 0.0


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
    tokens = ("test", "folders")

    # When: Processing tokens
    terms = _process_tokens_with_digits(tokens)

    # Then: One term per token, lemmatized, original unchanged
    assert terms == (Term("test", "test", "test"), Term("folders", "folder", "folders"))


def test_process_tokens_with_digits_with_digits() -> None:
    """Verify processing tokens containing digits."""
    # Given: Tokens with digits
    tokens = ("test123", "folder")

    # When: Processing tokens
    terms = _process_tokens_with_digits(tokens)

    # Then: The stripped variant follows its source and remembers the original
    assert [t.token for t in terms] == ["test123", "test", "folder"]
    assert terms[1] == Term("test", "test", "test123")


# Tests for _process_folder_matches
def test_process_folder_matches_empty_folder(tmp_path: Path, mocker) -> None:
    """Verify handling of empty folder terms."""
    # Given: A folder that exposes no searchable terms
    empty_dir = tmp_path / "empty_folder"
    empty_dir.mkdir()
    empty_folder = Folder(path=empty_dir, folder_type=ProjectType.FOLDER)
    mocker.patch.object(Folder, "terms", new_callable=mocker.PropertyMock, return_value=set())

    # When: Processing folder matches
    result = _process_folder_matches(empty_folder, (term("test"),), 0.5, 1, MATCH_THRESHOLD)

    # Then: Should return None for empty folder
    assert result is None


def test_process_folder_matches_good_match(mock_folder) -> None:
    """Verify matching process for good folder match."""
    # When: Processing folder matches for a token in the folder name
    result = _process_folder_matches(mock_folder, (term("test"),), 0.5, 1, MATCH_THRESHOLD)

    # Then: Should return MatchResult with good score
    assert isinstance(result, MatchResult)
    assert result.score >= MATCH_THRESHOLD
    assert "test" in result.matched_terms


def test_process_folder_matches_reports_original_folder_term(tmp_path: Path) -> None:
    """Verify a match against a digit-stripped variant reports the folder's real term."""
    # Given: A folder whose only term contains digits
    folder_dir = tmp_path / "invoices2024"
    folder_dir.mkdir()
    folder = Folder(path=folder_dir, folder_type=ProjectType.FOLDER)

    # When: Matching a token that only matches the stripped variant
    result = _process_folder_matches(folder, (term("invoice"),), 0.5, 1, MATCH_THRESHOLD)

    # Then: The original folder term is reported
    assert result is not None
    assert result.matched_terms == {"invoices2024"}


def test_find_matching_folders_ignores_blank_neatfile_lines(tmp_path: Path) -> None:
    """Verify whitespace-only lines in a .neatfile do not break matching."""
    # Given: A folder whose .neatfile has a whitespace-only line
    folder_dir = tmp_path / "finance"
    folder_dir.mkdir()
    (folder_dir / ".neatfile").write_text("budget\n   \n", encoding="utf-8")
    folders = [Folder(path=folder_dir, folder_type=ProjectType.FOLDER)]

    # When: Matching a token from the .neatfile
    matches = _find_matching_folders(["budget"], folders)

    # Then: The folder is proposed and the blank line is not a term
    assert [match.folder.path for match in matches] == [folder_dir]
    assert "" not in folders[0].terms


# Tests for _find_matching_folders
def test_find_matching_folders_no_matches(tmp_path: Path) -> None:
    """Verify behavior when no matching folders found."""
    # Given: Filename tokens and an unrelated folder
    test_dir = tmp_path / "finance"
    test_dir.mkdir()
    filename_tokens = ["dog"]
    folders = [Folder(path=test_dir, folder_type=ProjectType.FOLDER)]

    # When: Finding matching folders
    matches = _find_matching_folders(filename_tokens, folders)

    # Then: Should return empty list
    assert len(matches) == 0


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

    # When: Finding matching folders
    matches = _find_matching_folders(filename_tokens, folders)

    # Then: Should return sorted list of matches
    assert len(matches) > 0
    assert all(isinstance(match, MatchResult) for match in matches)
    assert all(match.score >= MATCH_THRESHOLD for match in matches)
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

    # When: Finding matching folders
    matches = _find_matching_folders(filename_tokens, folders)

    # Then: Should return one match
    assert len(matches) == 1
    assert matches[0].folder.path == path1


TOKEN_THRESHOLD = MATCH_THRESHOLD * TOKEN_THRESHOLD_FACTOR


@pytest.mark.parametrize(
    ("file_token", "folder_token"),
    [
        ("run", "running"),
        ("tax", "taxes"),
        ("mockups", "mockup"),
        ("photo", "pictures"),
        ("dog", "pets"),
        ("car", "vehicle"),
        ("recipe", "cooking"),
        ("school", "education"),
        ("medical", "health"),
        ("vet", "pets"),
        ("tax", "irs"),
        ("flight", "travel"),
        ("resume", "career"),
        ("lease", "apartment"),
        ("tuition", "education"),
        ("payslip", "salary"),
        ("passport", "travel"),
        ("bank", "finance"),
        ("doctor", "health"),
        ("insurance", "policy"),
        ("budget", "finance"),
        ("invoice", "receipts"),
    ],
)
def test_calibration_pairs_that_must_match(file_token: str, folder_token: str) -> None:
    """Verify realistic filing vocabulary clears the token threshold."""
    score = _calculate_token_similarity(term(file_token), term(folder_token))
    assert score > TOKEN_THRESHOLD, f"{file_token}/{folder_token} scored {score:.2f}"


@pytest.mark.parametrize(
    ("file_token", "folder_token"),
    [
        ("mortgage", "recipes"),
        ("passport", "cooking"),
        ("flight", "insurance"),
        ("koala", "foo"),
        ("school", "bank"),
        ("test", "folder"),
        ("dog", "finance"),
        ("photo", "taxes"),
        ("invoice", "pets"),
        ("resume", "house"),
        ("contract", "photos"),
        ("lease", "finance"),
        ("plan", "insurance"),
        ("report", "invoices"),
        ("list", "recipes"),
        ("notes", "invoices"),
    ],
)
def test_calibration_pairs_that_must_not_match(file_token: str, folder_token: str) -> None:
    """Verify unrelated vocabulary stays below the token threshold."""
    score = _calculate_token_similarity(term(file_token), term(folder_token))
    assert score <= TOKEN_THRESHOLD, f"{file_token}/{folder_token} scored {score:.2f}"


def test_single_similar_token_carries_a_folder(tmp_path: Path) -> None:
    """Verify one non-exact but related token is enough to propose a folder."""
    # Given: A folder named for a topic and a filename token related to it
    finance_dir = tmp_path / "finance"
    finance_dir.mkdir()
    folders = [Folder(path=finance_dir, folder_type=ProjectType.FOLDER)]

    # When: Matching a single related token
    matches = _find_matching_folders(["budget"], folders)

    # Then: The folder is proposed
    assert [match.folder.path for match in matches] == [finance_dir]
