"""Matches filenames with project folders."""

import re
from functools import cache
from pathlib import Path
from typing import NamedTuple

import numpy as np
from nclutils import pp

from neatfile import settings
from neatfile.constants import ProjectType
from neatfile.models import File, Folder, MatchResult
from neatfile.utils.strings import strip_special_chars, strip_stopwords, tokenize_string
from neatfile.views import select_folder

# Minimum weighted folder score for a folder to be offered as a destination. Static embeddings
# score true synonyms around 0.35 to 0.8 and unrelated words at or below 0.2.
MATCH_THRESHOLD = 0.30
# Individual tokens may match more loosely than the folder as a whole so partial matches contribute.
TOKEN_THRESHOLD_FACTOR = 0.9


class Term(NamedTuple):
    """A token prepared for matching."""

    token: str
    lemma: str
    original: str
    """The token as it appeared in the name, before any digit stripping."""


class FolderIndex(NamedTuple):
    """Folder terms laid out for batched scoring."""

    folders: tuple[Folder, ...]
    """Folders that expose at least one term, in scoring order."""
    terms: tuple[Term, ...]
    """Every folder's terms, concatenated so each folder occupies one contiguous block."""
    lemmas: np.ndarray
    """Lemma of each entry in `terms`."""
    matrix: np.ndarray
    """Unit embedding of each entry in `terms`, one row per term."""
    starts: np.ndarray
    """Offset into `terms` where each folder's block begins."""


@cache
def _folder_index(folders: tuple[Folder, ...]) -> FolderIndex:
    """Prepare and embed every folder's terms once so each file is scored with one matrix product.

    Args:
        folders (tuple[Folder, ...]): Candidate folders. Folders with no terms are dropped.

    Returns:
        FolderIndex: The concatenated terms, their embeddings, and each folder's block offset.
    """
    # Imported lazily so commands that never sort do not load the embedding stack.
    from neatfile.utils import nlp  # noqa: PLC0415

    kept: list[Folder] = []
    terms: list[Term] = []
    starts: list[int] = []
    for folder in folders:
        folder_terms = _process_tokens_with_digits(tuple(sorted(folder.terms)))
        if not folder_terms:
            continue
        kept.append(folder)
        starts.append(len(terms))
        terms.extend(folder_terms)

    return FolderIndex(
        folders=tuple(kept),
        terms=tuple(terms),
        lemmas=np.array([t.lemma for t in terms], dtype=str),
        matrix=nlp.embed([t.token for t in terms]),
        starts=np.array(starts, dtype=int),
    )


def _similarity_matrix(
    file_terms: tuple[Term, ...],
    folder_terms: tuple[Term, ...],
    folder_matrix: np.ndarray | None = None,
    folder_lemmas: np.ndarray | None = None,
) -> np.ndarray:
    """Score every filename term against every folder term in one matrix product.

    A shared lemma counts as an exact match and overrides the embedding score.

    Args:
        file_terms (tuple[Term, ...]): Terms from the filename.
        folder_terms (tuple[Term, ...]): Terms from the folders.
        folder_matrix (np.ndarray | None, optional): Precomputed unit embeddings of `folder_terms`. Embedded on demand when omitted.
        folder_lemmas (np.ndarray | None, optional): Precomputed lemmas of `folder_terms`. Built on demand when omitted.

    Returns:
        np.ndarray: Scores in the range 0.0 to 1.0, shaped (len(file_terms), len(folder_terms)).
    """
    from neatfile.utils import nlp  # noqa: PLC0415

    if folder_matrix is None:
        folder_matrix = nlp.embed([t.token for t in folder_terms])
    if folder_lemmas is None:
        folder_lemmas = np.array([t.lemma for t in folder_terms], dtype=str)

    file_matrix = nlp.embed([t.token for t in file_terms])
    scores = np.clip(file_matrix @ folder_matrix.T, 0.0, 1.0)

    file_lemmas = np.array([t.lemma for t in file_terms], dtype=str)
    scores[file_lemmas[:, None] == folder_lemmas[None, :]] = 1.0
    return scores


def _calculate_folder_score(
    total_score: float | np.ndarray, match_count: int | np.ndarray, total_tokens: int
) -> np.ndarray:
    """Calculate a weighted score balancing match quality and coverage for folder matching.

    Combine average similarity score with coverage ratio to determine overall folder match score. Coverage is weighted less (10%) than average similarity (90%) to prevent longer filenames from being penalized too heavily. Accepts one folder's numbers or arrays holding every folder's numbers.

    Args:
        total_score (float | np.ndarray): Sum of individual token match similarity scores
        match_count (int | np.ndarray): Number of tokens that matched above threshold
        total_tokens (int): Total number of tokens being matched

    Returns:
        np.ndarray: Combined weighted score between 0.0 and 1.0, 0.0 where nothing matched
    """
    total_score = np.asarray(total_score, dtype=float)
    match_count = np.asarray(match_count, dtype=float)
    matched = match_count > 0
    avg_similarity = np.divide(
        total_score, match_count, out=np.zeros_like(total_score), where=matched
    )
    coverage = np.divide(match_count, total_tokens, out=np.zeros_like(total_score), where=matched)

    # Balance between quality of matches and quantity of matches, favoring quality
    return np.where(matched, avg_similarity * (0.9 + 0.1 * coverage), 0.0)


@cache
def _process_tokens_with_digits(tokens: tuple[str, ...]) -> tuple[Term, ...]:
    """Lemmatize tokens and add digit-stripped variants for tokens containing digits.

    Tokens that differ only by a number (`invoice2024` vs `invoice`) should still match, so each token with digits also contributes a stripped copy. Cached because the same folder terms are matched against every file sorted.

    Args:
        tokens (tuple[str, ...]): Tokens to process

    Returns:
        tuple[Term, ...]: Prepared terms, with stripped variants following their source token
    """
    from neatfile.utils import nlp  # noqa: PLC0415

    terms = []

    for token in tokens:
        terms.append(Term(token, nlp.lemmatize(token), token))

        if any(c.isdigit() for c in token):
            stripped_token = re.sub(r"\d+", "", token)
            if stripped_token:
                terms.append(Term(stripped_token, nlp.lemmatize(stripped_token), token))

    return tuple(terms)


def _find_matching_folders(
    filename_tokens: list[str], folders: list["Folder"], threshold: float = MATCH_THRESHOLD
) -> list[MatchResult]:
    """Compare filename tokens against folder names using semantic similarity to find matching folders.

    Score every filename term against every folder term in one matrix product, keep each filename term's best folder term when it clears the token threshold, and weight each folder by match quality and coverage. Return folders that exceed the similarity threshold, sorted by match quality.

    Args:
        filename_tokens (list[str]): Tokens extracted from the filename to match against folders
        folders (list[Folder]): Collection of folders to evaluate for matches
        threshold (float, optional): Minimum semantic similarity score required for a match. Defaults to MATCH_THRESHOLD.

    Returns:
        list[MatchResult]: Matching folders sorted by similarity score
    """
    token_match_threshold = threshold * TOKEN_THRESHOLD_FACTOR

    index = _folder_index(tuple(folder for folder in folders if not folder.is_ignored))
    filename_terms = _process_tokens_with_digits(tuple(filename_tokens))
    pp.trace(f"SORT: filename_lemmas={[term.lemma for term in filename_terms]}")
    if not index.folders or not filename_terms:
        return []

    scores = _similarity_matrix(filename_terms, index.terms, index.matrix, index.lemmas)
    # Best folder term for each filename term, one column per folder
    best = np.maximum.reduceat(scores, index.starts, axis=1)
    matched = best > token_match_threshold
    folder_scores = _calculate_folder_score(
        np.where(matched, best, 0.0).sum(axis=0), matched.sum(axis=0), len(filename_tokens)
    )

    block_ends = np.append(index.starts[1:], len(index.terms))
    matches = []
    for folder_pos in np.flatnonzero(folder_scores >= threshold):
        folder = index.folders[folder_pos]
        block = slice(index.starts[folder_pos], block_ends[folder_pos])
        # argmax picks the first of equal scores, so earlier folder terms win ties
        best_terms = scores[:, block].argmax(axis=1) + block.start
        matched_terms = {
            index.terms[term_pos].original for term_pos in best_terms[matched[:, folder_pos]]
        }
        folder_score = float(folder_scores[folder_pos])
        pp.trace(f"SORT: {folder.path} matched with score {folder_score} and terms {matched_terms}")
        matches.append(MatchResult(folder, folder_score, matched_terms))

    matches.sort(key=lambda x: x.score, reverse=True)
    return matches


def _match_by_jd_number(terms: list[str]) -> Path | None:
    """Find a matching folder by looking for Johnny Decimal numbers in the provided terms.

    Search through the terms for strings matching JD number patterns (e.g. '12-34', '12.34', or '12'). If a match is found, return the path of the first folder with a matching JD number.

    Args:
        terms (list[str]): List of terms to search for JD numbers

    Returns:
        Path | None: Path of the matching folder if found, None otherwise
    """
    if settings.project.project_type != ProjectType.JD:
        return None

    for term in terms:
        if re.match(r"^(\d{2}-\d{2}|\d{2}\.\d{2}|\d{2})$", term):
            for folder in settings.project.usable_folders:
                if folder.number == term:
                    return folder.path

    return None


def sort_file(file: File) -> Path | None:
    """Find the best matching folder for a file based on name similarity.

    Process the file name into searchable tokens and match against project folders. First attempt to match by Johnny Decimal number if using a JD project. Then find matching folders based on semantic similarity between tokens.

    Args:
        file (File): The file object to find a matching folder for.

    Returns:
        Path | None: The path of the best matching folder, or None when no folder matches.
    """
    if jd_match := _match_by_jd_number(settings.user_terms):
        pp.trace(f"SORT: '{file.stem}' matched by jd number: {jd_match}")
        return jd_match

    tokens_to_match = tokenize_string(file.new_stem) + settings.user_terms
    tokens_to_match = strip_special_chars(tokens_to_match)
    tokens_to_match = strip_stopwords(tokens_to_match)

    pp.trace(f"SORT: '{file.new_name}' tokens to match: {tokens_to_match}")

    matching_dirs = _find_matching_folders(tokens_to_match, settings.project.usable_folders)

    if not matching_dirs:
        pp.warning(f"No matching directories found for `{file.name}`")
        return None

    if len(matching_dirs) > 1:
        return select_folder(
            matching_dirs=matching_dirs,
            file=file,
        )

    return matching_dirs[0].folder.path
