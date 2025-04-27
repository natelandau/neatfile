"""Matches filenames with project folders."""

import re
from pathlib import Path

import cappa
import spacy

from neatfile import settings
from neatfile.constants import ProjectType
from neatfile.models import File, Folder, MatchResult
from neatfile.utils import pp
from neatfile.utils.nlp import nlp
from neatfile.utils.strings import strip_special_chars, strip_stopwords, tokenize_string
from neatfile.views import select_folder


def _calculate_token_similarity(
    file_doc: spacy.tokens.doc.Doc,
    file_lemma: str,
    folder_doc: spacy.tokens.doc.Doc,
    folder_lemma: str,
) -> float:
    """Calculate semantic similarity between two tokens by comparing lemmas and word vectors.

    Compare tokens first by exact lemma matching, then by vector similarity if no exact match is found. This provides a similarity score between 0.0 and 1.0, where 1.0 indicates an exact match.

    Args:
        file_doc (spacy.tokens.doc.Doc): spaCy Doc object containing the file token
        file_lemma (str): Lemmatized form of the file token
        folder_doc (spacy.tokens.doc.Doc): spaCy Doc object containing the folder token
        folder_lemma (str): Lemmatized form of the folder token

    Returns:
        float: Similarity score between 0.0 and 1.0, where 1.0 is an exact match
    """
    # Check for lemma match first (exact lemma match = 1.0)
    if file_lemma == folder_lemma:
        return 1.0

    # Otherwise use vector similarity if vectors exist
    if file_doc[0].has_vector and folder_doc[0].has_vector:
        return file_doc[0].similarity(folder_doc[0])

    return 0.0


def _find_best_match_for_token(
    file_doc: spacy.tokens.doc.Doc,
    file_lemma: str,
    folder_docs: list[spacy.tokens.doc.Doc],
    folder_lemmas: list[str],
    folder_tokens: list[str],
    token_match_threshold: float,
) -> tuple[str | None, float]:
    """Compare a filename token against folder tokens to find the best semantic match.

    Iterate through folder tokens and calculate semantic similarity scores using spaCy word vectors and lemmatization. Return the highest scoring folder token that exceeds the threshold.

    Args:
        file_doc (spacy.tokens.doc.Doc): spaCy Doc object for the filename token
        file_lemma (str): Lemmatized form of the filename token
        folder_docs (list[spacy.tokens.doc.Doc]): List of spaCy Doc objects for folder tokens
        folder_lemmas (list[str]): List of lemmatized folder tokens
        folder_tokens (list[str]): Original folder token strings
        token_match_threshold (float): Minimum similarity score required for a match

    Returns:
        tuple[str | None, float]: Best matching folder token and its similarity score, or (None, 0.0) if no match found
    """
    best_token_score = 0.0
    best_matching_term = None

    for folder_idx, folder_doc in enumerate(folder_docs):
        folder_term = folder_tokens[folder_idx]
        similarity = _calculate_token_similarity(
            file_doc, file_lemma, folder_doc, folder_lemmas[folder_idx]
        )

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


def _process_tokens_with_digits(
    tokens: list[str],
) -> tuple[list[spacy.tokens.doc.Doc], list[str], list[str]]:
    """Process tokens and create additional versions for those containing digits.

    For each token, create spaCy docs and lemmas. If a token contains digits, create an additional
    version with digits stripped. This helps improve matching for tokens that differ only by numbers.

    Args:
        tokens (list[str]): List of tokens to process

    Returns:
        tuple[list[spacy.tokens.doc.Doc], list[str], list[str]]: Tuple containing:
            - List of spaCy Doc objects
            - List of lemmatized forms
            - List of processed tokens (including stripped versions)
    """
    docs = []
    lemmas = []
    processed_tokens = []

    for token in tokens:
        docs.append(nlp(token))
        lemmas.append(docs[-1][0].lemma_)
        processed_tokens.append(token)

        # If token contains digits, add a stripped version
        if any(c.isdigit() for c in token):
            stripped_token = re.sub(r"\d+", "", token)
            if stripped_token:  # Only add if there are remaining characters
                docs.append(nlp(stripped_token))
                lemmas.append(docs[-1][0].lemma_)
                processed_tokens.append(stripped_token)

    return docs, lemmas, processed_tokens


def _process_folder_matches(
    folder: Folder,
    filename_docs: list[spacy.tokens.doc.Doc],
    filename_lemmas: list[str],
    token_match_threshold: float,
    filename_token_count: int,
    threshold: float,
) -> MatchResult | None:
    """Process a single folder to find matches with the filename tokens.

    Calculate similarity scores between filename tokens and folder tokens, tracking matches
    and computing an overall score for the folder.

    Args:
        folder (Folder): The folder to evaluate for matches
        filename_docs (list[spacy.tokens.doc.Doc]): List of spaCy docs for filename tokens
        filename_lemmas (list[str]): List of lemmatized filename tokens
        token_match_threshold (float): Minimum similarity score for individual token matches
        filename_token_count (int): Total number of original filename tokens
        threshold (float): Minimum overall score required for a folder match

    Returns:
        MatchResult | None: A MatchResult if the folder matches above the threshold, None otherwise
    """
    folder_tokens = list(folder.terms)
    if not folder_tokens:
        return None

    # Process folder tokens and create lemmas, including stripped versions for tokens with digits
    folder_docs, folder_lemmas, processed_folder_tokens = _process_tokens_with_digits(folder_tokens)

    total_score = 0.0
    match_count = 0
    matched_terms = set()

    # Compare each filename token against all folder tokens to find best matches
    for file_idx, file_doc in enumerate(filename_docs):
        best_term, score = _find_best_match_for_token(
            file_doc,
            filename_lemmas[file_idx],
            folder_docs,
            folder_lemmas,
            processed_folder_tokens,
            token_match_threshold,
        )

        if best_term:
            total_score += score
            match_count += 1
            # Add the original token (not stripped version) to matched terms
            original_term = next(
                (t for t in folder_tokens if re.sub(r"\d+", "", t) == best_term or t == best_term),
                best_term,
            )
            matched_terms.add(original_term)

    # Calculate weighted folder score based on match quality and coverage
    folder_score = _calculate_folder_score(total_score, match_count, filename_token_count)

    if folder_score >= threshold:
        return MatchResult(folder, folder_score, matched_terms)

    return None


def _find_matching_folders(
    filename_tokens: list[str], folders: list["Folder"], threshold: float = 0.6
) -> list[MatchResult]:
    """Compare filename tokens against folder names using semantic similarity to find matching folders.

    Process each filename token using spaCy lemmatization and word vectors to calculate semantic similarity scores against folder names. Return folders that exceed the similarity threshold, sorted by match quality.

    Args:
        filename_tokens (list[str]): Tokens extracted from the filename to match against folders
        folders (list[Folder]): Collection of folders to evaluate for matches
        threshold (float, optional): Minimum semantic similarity score required for a match. Defaults to 0.6.

    Returns:
        list[MatchResult]: Matching folders sorted by similarity score
    """
    # Lower threshold for individual token matches to allow for partial matches while maintaining overall quality
    token_match_threshold = threshold * 0.83

    # Process filename tokens and create lemmas, including stripped versions for tokens with digits
    filename_docs, filename_lemmas, _ = _process_tokens_with_digits(filename_tokens)
    pp.trace(f"SORT: {filename_lemmas=}")

    matches = []
    for folder in folders:
        match_result = _process_folder_matches(
            folder,
            filename_docs,
            filename_lemmas,
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


def sort_file(file: File) -> Path:
    """Find the best matching folder for a file based on name similarity.

    Process the file name into searchable tokens and match against project folders. First attempt to match by Johnny Decimal number if using a JD project. Then find matching folders based on semantic similarity between tokens.

    Args:
        file (File): The file object to find a matching folder for.

    Returns:
        Path: The path of the best matching folder
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
        pp.error(f"No matching directories found for `{file.name}`")
        raise cappa.Exit(code=1)

    if len(matching_dirs) > 1:
        return select_folder(
            matching_dirs=matching_dirs,
            file=file,
        )

    return matching_dirs[0].folder.path
