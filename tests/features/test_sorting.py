"""Tests for the file organizer controller."""

from pathlib import Path

import numpy as np
import pytest

from neatfile.constants import NEATFILE_IGNORE_NAME, FolderType
from neatfile.features.sorting import (
    MATCH_THRESHOLD,
    TOKEN_THRESHOLD_FACTOR,
    Term,
    _calculate_folder_score,
    _find_matching_folders,
    _folder_index,
    _process_tokens_with_digits,
    _similarity_matrix,
)
from neatfile.models import Folder, MatchResult
from neatfile.utils import nlp


def term(token: str) -> Term:
    """Build a Term for a token as the matcher would.

    Returns:
        Term: The token, its lemma, and itself as the original.
    """
    return Term(token, nlp.lemmatize(token), token)


def pair_score(file_token: str, folder_token: str) -> float:
    """Score one filename token against one folder token through the matrix path.

    Returns:
        float: The similarity the matcher would use for the pair.
    """
    return float(_similarity_matrix((term(file_token),), (term(folder_token),))[0, 0])


@pytest.fixture
def mock_folder(tmp_path: Path):
    """Create a mock folder for testing.

    Returns:
        Folder: A mock folder for testing.
    """
    test_dir = tmp_path / "test_folder"
    test_dir.mkdir()
    return Folder(path=test_dir, folder_type=FolderType.OTHER)


# Tests for _similarity_matrix
def test_similarity_matrix_exact_lemma_match_scores_one() -> None:
    """Verify tokens sharing a lemma score 1.0 regardless of their embeddings."""
    assert pair_score("tests", "testing") == 1.0


def test_similarity_matrix_uses_embeddings_when_lemmas_differ() -> None:
    """Verify related tokens with different lemmas get a real similarity, not a sentinel."""
    assert 0 < pair_score("photo", "pictures") < 1


def test_similarity_matrix_matches_pairwise_similarity() -> None:
    """Verify every cell equals the single-pair similarity for the same tokens."""
    # Given: Filename and folder terms with no shared lemmas
    file_terms = (term("photo"), term("budget"), term("dog"))
    folder_terms = (term("pictures"), term("finance"))

    # When: Scoring the whole grid at once
    scores = _similarity_matrix(file_terms, folder_terms)

    # Then: Each cell is the pairwise cosine similarity
    assert scores.shape == (3, 2)
    for row, file_term in enumerate(file_terms):
        for col, folder_term in enumerate(folder_terms):
            assert scores[row, col] == pytest.approx(
                nlp.similarity(file_term.token, folder_term.token), abs=1e-6
            )


def test_similarity_matrix_empty_file_terms() -> None:
    """Verify an empty filename term set yields a zero-row matrix."""
    scores = _similarity_matrix((), (term("finance"),))

    assert scores.shape == (0, 1)


# Tests for _folder_index
def test_folder_index_lays_out_terms_in_folder_blocks(tmp_path: Path) -> None:
    """Verify the index keeps each folder's terms contiguous and records where each block starts."""
    # Given: A folder with a digit term and a folder with a plain term
    invoices = tmp_path / "invoices2024"
    photos = tmp_path / "photos"
    invoices.mkdir()
    photos.mkdir()
    folders = (
        Folder(path=invoices, folder_type=FolderType.OTHER),
        Folder(path=photos, folder_type=FolderType.OTHER),
    )

    # When: Building the index
    index = _folder_index(folders)

    # Then: Terms follow folder order with stripped variants inside their folder's block
    assert [t.token for t in index.terms] == ["invoices2024", "invoices", "photos"]
    assert index.starts.tolist() == [0, 2]
    assert index.matrix.shape == (3, nlp._model().dim)
    assert np.linalg.norm(index.matrix, axis=1) == pytest.approx([1.0, 1.0, 1.0])
    assert index.folders == folders


def test_folder_index_skips_folders_without_terms(tmp_path: Path, mocker) -> None:
    """Verify a folder that exposes no terms is left out of the index."""
    # Given: A folder whose terms are empty
    empty_dir = tmp_path / "empty_folder"
    empty_dir.mkdir()
    mocker.patch.object(Folder, "terms", new_callable=mocker.PropertyMock, return_value=set())
    folders = (Folder(path=empty_dir, folder_type=FolderType.OTHER),)

    # When: Building the index
    index = _folder_index(folders)

    # Then: Nothing is indexed
    assert index.folders == ()
    assert index.terms == ()
    assert index.matrix.shape == (0, nlp._model().dim)


def test_folder_index_is_built_once_per_folder_set(tmp_path: Path) -> None:
    """Verify the same folder tuple reuses the index instead of re-embedding."""
    finance = tmp_path / "finance"
    finance.mkdir()
    folders = (Folder(path=finance, folder_type=FolderType.OTHER),)

    assert _folder_index(folders) is _folder_index(folders)


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


# Tests for _find_matching_folders
def test_find_matching_folders_skips_folder_without_terms(tmp_path: Path, mocker) -> None:
    """Verify a folder that exposes no searchable terms is never proposed."""
    # Given: A folder with no terms
    empty_dir = tmp_path / "empty_folder"
    empty_dir.mkdir()
    mocker.patch.object(Folder, "terms", new_callable=mocker.PropertyMock, return_value=set())
    folders = [Folder(path=empty_dir, folder_type=FolderType.OTHER)]

    # When: Matching
    matches = _find_matching_folders(["test"], folders)

    # Then: Nothing is proposed
    assert matches == []


def test_find_matching_folders_reports_matched_terms(mock_folder) -> None:
    """Verify a matching folder carries its score and the folder terms that matched."""
    # When: Matching a token in the folder name
    matches = _find_matching_folders(["test"], [mock_folder])

    # Then: One MatchResult above the threshold naming the matched term
    assert len(matches) == 1
    assert isinstance(matches[0], MatchResult)
    assert matches[0].score >= MATCH_THRESHOLD
    assert "test" in matches[0].matched_terms


def test_find_matching_folders_reports_original_folder_term(tmp_path: Path) -> None:
    """Verify a match against a digit-stripped variant reports the folder's real term."""
    # Given: A folder whose only term contains digits
    folder_dir = tmp_path / "invoices2024"
    folder_dir.mkdir()
    folders = [Folder(path=folder_dir, folder_type=FolderType.OTHER)]

    # When: Matching a token that only matches the stripped variant
    matches = _find_matching_folders(["invoice"], folders)

    # Then: The original folder term is reported
    assert len(matches) == 1
    assert matches[0].matched_terms == {"invoices2024"}


def test_find_matching_folders_empty_tokens_returns_nothing(tmp_path: Path) -> None:
    """Verify a filename with no tokens left after filtering matches no folder."""
    finance = tmp_path / "finance"
    finance.mkdir()
    folders = [Folder(path=finance, folder_type=FolderType.OTHER)]

    assert _find_matching_folders([], folders) == []


def test_find_matching_folders_scores_match_pairwise_reference(tmp_path: Path) -> None:
    """Verify the batched scorer reproduces a plain per-pair best-match computation."""
    # Given: Several folders and a multi-token filename with a digit token
    names = ["finance-taxes", "photos", "travel-flight", "pets", "invoices2024"]
    folders = []
    for name in names:
        (tmp_path / name).mkdir()
        folders.append(Folder(path=tmp_path / name, folder_type=FolderType.OTHER))
    tokens = ["budget", "receipt2023", "dog", "passport"]
    token_threshold = MATCH_THRESHOLD * TOKEN_THRESHOLD_FACTOR

    # And: A reference computed one pair at a time
    expected = {}
    file_terms = _process_tokens_with_digits(tuple(tokens))
    for folder in folders:
        folder_terms = _process_tokens_with_digits(tuple(sorted(folder.terms)))
        total, count, matched = 0.0, 0, set()
        for file_term in file_terms:
            best_score, best_term = 0.0, None
            for folder_term in folder_terms:
                score = (
                    1.0
                    if file_term.lemma == folder_term.lemma
                    else nlp.similarity(file_term.token, folder_term.token)
                )
                if score > best_score:
                    best_score, best_term = score, folder_term
            if best_score > token_threshold:
                total += best_score
                count += 1
                matched.add(best_term.original)
        folder_score = _calculate_folder_score(total, count, len(tokens))
        if folder_score >= MATCH_THRESHOLD:
            expected[folder.path] = (float(folder_score), matched)

    # When: Scoring with the batched matcher
    matches = _find_matching_folders(tokens, folders)

    # Then: Same folders, scores, and matched terms
    assert expected, "fixture must produce at least one match"
    assert {m.folder.path: (pytest.approx(m.score), m.matched_terms) for m in matches} == expected


def test_find_matching_folders_ignores_blank_neatfile_lines(tmp_path: Path) -> None:
    """Verify whitespace-only lines in a .neatfile do not break matching."""
    # Given: A folder whose .neatfile has a whitespace-only line
    folder_dir = tmp_path / "finance"
    folder_dir.mkdir()
    (folder_dir / ".neatfile").write_text("budget\n   \n", encoding="utf-8")
    folders = [Folder(path=folder_dir, folder_type=FolderType.OTHER)]

    # When: Matching a token from the .neatfile
    matches = _find_matching_folders(["budget"], folders)

    # Then: The folder is proposed and the blank line is not a term
    assert [match.folder.path for match in matches] == [folder_dir]
    assert "" not in folders[0].terms


def test_find_matching_folders_no_matches(tmp_path: Path) -> None:
    """Verify behavior when no matching folders found."""
    # Given: Filename tokens and an unrelated folder
    test_dir = tmp_path / "finance"
    test_dir.mkdir()
    filename_tokens = ["dog"]
    folders = [Folder(path=test_dir, folder_type=FolderType.OTHER)]

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
        Folder(path=path1, folder_type=FolderType.OTHER),
        Folder(path=path2, folder_type=FolderType.OTHER),
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
        Folder(path=path1, folder_type=FolderType.OTHER),
        Folder(path=path2, folder_type=FolderType.OTHER),
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
    score = pair_score(file_token, folder_token)
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
    score = pair_score(file_token, folder_token)
    assert score <= TOKEN_THRESHOLD, f"{file_token}/{folder_token} scored {score:.2f}"


def test_single_similar_token_carries_a_folder(tmp_path: Path) -> None:
    """Verify one non-exact but related token is enough to propose a folder."""
    # Given: A folder named for a topic and a filename token related to it
    finance_dir = tmp_path / "finance"
    finance_dir.mkdir()
    folders = [Folder(path=finance_dir, folder_type=FolderType.OTHER)]

    # When: Matching a single related token
    matches = _find_matching_folders(["budget"], folders)

    # Then: The folder is proposed
    assert [match.folder.path for match in matches] == [finance_dir]
