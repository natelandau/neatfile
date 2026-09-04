"""Matches filenames with project folders."""

import re
from functools import cache
from pathlib import Path
from typing import NamedTuple

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


def _calculate_token_similarity(file_term: Term, folder_term: Term) -> float:
    """Calculate semantic similarity between two terms by comparing lemmas and embeddings.

    Compare terms first by exact lemma matching, then by vector similarity if no exact match is found.

    Args:
        file_term (Term): Term from the filename
        folder_term (Term): Term from the folder name

    Returns:
        float: Similarity score between 0.0 and 1.0, where 1.0 is an exact match
    """
    # Imported lazily so commands that never sort do not load the embedding stack.
    from neatfile.utils import nlp  # noqa: PLC0415

    if file_term.lemma == folder_term.lemma:
        return 1.0

    return nlp.similarity(file_term.token, folder_term.token)


def _find_best_match_for_token(
    file_term: Term, folder_terms: tuple[Term, ...], token_match_threshold: float
) -> tuple[Term | None, float]:
    """Compare a filename term against folder terms to find the best semantic match.

    Args:
        file_term (Term): Term from the filename
        folder_terms (tuple[Term, ...]): Terms from the folder name
        token_match_threshold (float): Minimum similarity score required for a match

    Returns:
        tuple[Term | None, float]: Best matching folder term and its similarity score, or (None, 0.0) if no match found
    """
    best_token_score = 0.0
    best_matching_term = None

    for folder_term in folder_terms:
        similarity = _calculate_token_similarity(file_term, folder_term)

        if similarity > best_token_score:
            best_token_score = similarity
            best_matching_term = folder_term

    if best_token_score > token_match_threshold:
        return best_matching_term, best_token_score

    return None, 0.0


def _calculate_folder_score(total_score: float, match_count: int, total_tokens: int) -> float:
    """Calculate a weighted score balancing match quality and coverage for folder matching.

    Combine average similarity score with coverage ratio to determine overall folder match score. Coverage is weighted less (10%) than average similarity (90%) to prevent longer filenames from being penalized too heavily.

    Args:
        total_score (float): Sum of individual token match similarity scores
        match_count (int): Number of tokens that matched above threshold
        total_tokens (int): Total number of tokens being matched

    Returns:
        float: Combined weighted score between 0.0 and 1.0
    """
    if match_count == 0:
        return 0.0

    avg_similarity = total_score / match_count
    coverage = match_count / total_tokens

    # Balance between quality of matches and quantity of matches, favoring quality
    return avg_similarity * (0.9 + 0.1 * coverage)


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


def _process_folder_matches(
    folder: Folder,
    filename_terms: tuple[Term, ...],
    token_match_threshold: float,
    filename_token_count: int,
    threshold: float,
) -> MatchResult | None:
    """Process a single folder to find matches with the filename terms.

    Calculate similarity scores between filename terms and folder terms, tracking matches and computing an overall score for the folder.

    Args:
        folder (Folder): The folder to evaluate for matches
        filename_terms (tuple[Term, ...]): Filename terms, including digit-stripped variants
        token_match_threshold (float): Minimum similarity score for individual token matches
        filename_token_count (int): Total number of original filename tokens
        threshold (float): Minimum overall score required for a folder match

    Returns:
        MatchResult | None: A MatchResult if the folder matches above the threshold, None otherwise
    """
    folder_tokens = tuple(sorted(folder.terms))
    if not folder_tokens:
        return None

    folder_terms = _process_tokens_with_digits(folder_tokens)

    total_score = 0.0
    match_count = 0
    matched_terms = set()

    for file_term in filename_terms:
        best_term, score = _find_best_match_for_token(
            file_term, folder_terms, token_match_threshold
        )

        if best_term is not None:
            total_score += score
            match_count += 1
            matched_terms.add(best_term.original)

    # Calculate weighted folder score based on match quality and coverage
    folder_score = _calculate_folder_score(total_score, match_count, filename_token_count)

    if folder_score >= threshold:
        pp.trace(f"SORT: {folder.path} matched with score {folder_score} and terms {matched_terms}")
        return MatchResult(folder, folder_score, matched_terms)

    return None


def _find_matching_folders(
    filename_tokens: list[str], folders: list["Folder"], threshold: float = MATCH_THRESHOLD
) -> list[MatchResult]:
    """Compare filename tokens against folder names using semantic similarity to find matching folders.

    Process each filename token to calculate semantic similarity scores against folder names. Return folders that exceed the similarity threshold, sorted by match quality.

    Args:
        filename_tokens (list[str]): Tokens extracted from the filename to match against folders
        folders (list[Folder]): Collection of folders to evaluate for matches
        threshold (float, optional): Minimum semantic similarity score required for a match. Defaults to MATCH_THRESHOLD.

    Returns:
        list[MatchResult]: Matching folders sorted by similarity score
    """
    token_match_threshold = threshold * TOKEN_THRESHOLD_FACTOR

    filename_terms = _process_tokens_with_digits(tuple(filename_tokens))
    pp.trace(f"SORT: filename_lemmas={[term.lemma for term in filename_terms]}")

    matches = []
    for folder in [x for x in folders if not x.is_ignored]:
        match_result = _process_folder_matches(
            folder,
            filename_terms,
            token_match_threshold,
            len(filename_tokens),
            threshold,
        )
        if match_result:
            matches.append(match_result)

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
