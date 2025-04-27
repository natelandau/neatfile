"""String utilities."""

import re

from neatfile.constants import Separator, TransformCase
from neatfile.utils.nlp import nlp


def match_case(tokens: list[str], match_case_list: tuple[str, ...] = ()) -> list[str]:
    """Match the case of tokens against a reference list of properly cased words.

    Compare each token against match_case_list and update its case to match if found. Preserve original case for unmatched tokens.

    Args:
        tokens (list[str]): List of tokens to process for case matching
        match_case_list (tuple[str, ...], optional): Reference list of properly cased words. Defaults to ().

    Returns:
        list[str]: List of tokens with case adjusted to match reference list where applicable
    """
    case_mapping = {word.lower(): word for word in match_case_list}

    # Process each token
    result = []
    for token in tokens:
        # Check if the lowercase version of the token exists in our mapping
        if token.lower() in case_mapping:
            # Replace with the properly cased version from match_case_list
            result.append(case_mapping[token.lower()])
        else:
            # Keep the original token
            result.append(token)

    return result


def split_camel_case(string_list: list[str], match_case_list: tuple[str, ...] = ()) -> list[str]:
    """Split strings containing camelCase words into separate words.

    Split each string in the input list into separate words based on camelCase boundaries. Preserve acronyms and any strings specified in match_case_list. For example, 'camelCase' becomes ['camel', 'Case'] but 'CEO' remains intact.

    Args:
        string_list (list[str]): List of strings to split on camelCase boundaries.
        match_case_list (tuple[str, ...], optional): Strings that should not be split. Defaults to ().

    Returns:
        list[str]: List of strings with camelCase words split into separate components.
    """
    result = []
    for item in string_list:
        if item in match_case_list:
            result.append(item)
            continue

        if item.isupper():
            result.append(item)
            continue

        words = re.findall(
            r"[A-Z]{2,}(?=[A-Z][a-z]+|$|[^a-zA-Z])|[A-Z]?[a-z]+|[A-Z](?=[^A-Z]|$)", item
        )

        if len(words) > 1:
            result.extend(words)
        else:
            result.append(item)

    return result


def tokenize_string(
    string: str,
) -> list[str]:
    """Split a string into individual tokens based on alphanumeric and non-alphanumeric boundaries.

    Split the input string into tokens by finding sequences of alphanumeric characters or individual non-alphanumeric characters. Filter out any empty tokens from the result.

    Args:
        string (str): The input string to tokenize.

    Returns:
        list[str]: A list of non-empty tokens extracted from the input string.
    """
    tokens = re.findall(r"[a-zA-Z0-9]+|[^a-zA-Z0-9]", string)
    return [token for token in tokens if token]


def strip_special_chars(tokens: list[str]) -> list[str]:
    """Remove all non-alphanumeric characters from each string in a list.

    Process each string in the input list by removing any characters that are not letters, numbers, or underscores. Empty strings are filtered out of the final result.

    Args:
        tokens (list[str]): List of strings to process and remove special characters from.

    Returns:
        list[str]: List of processed strings with special characters removed.
    """
    parsed_tokens = [re.sub(r"[^[a-zA-Z0-9]", "", token).strip() for token in tokens if token]
    return [token for token in parsed_tokens if token]


def strip_stopwords(tokens: list[str], stopwords: tuple[str, ...] = ()) -> list[str]:
    """Remove common English stopwords and any additional specified stopwords from a list of tokens.

    Process the input string by removing both standard English stopwords (using spaCy's default list) and any custom stopwords provided. Maintain word boundaries and case-insensitive matching.

    Args:
        tokens (list[str]): List of tokens to process and remove stopwords from.
        stopwords (tuple[str, ...], optional): Additional custom stopwords to remove. Defaults to ().

    Returns:
        list[str]: List of tokens with stopwords removed and excess whitespace/separators stripped.
    """
    spacy_stopwords = nlp.Defaults.stop_words | {x.lower() for x in stopwords}

    return [token for token in tokens if token.lower() not in spacy_stopwords]


def transform_case(tokens: list[str], transform_case: TransformCase) -> list[str]:
    """Transform the case of each token in a list according to the specified case style.

    Apply case transformations like lowercase, uppercase, title case, camelcase, or sentence case to a list of tokens. For camelcase, joins all tokens into a single string with the first token lowercase and subsequent tokens capitalized.

    Args:
        tokens (list[str]): List of string tokens to transform.
        transform_case (TransformCase): The case transformation to apply.

    Returns:
        list[str]: List of transformed tokens. For camelcase, returns a single-item list with the joined string.
    """
    match transform_case:
        case TransformCase.LOWER:
            return [token.lower() for token in tokens]
        case TransformCase.UPPER:
            return [token.upper() for token in tokens]
        case TransformCase.TITLE:
            return [token.title() for token in tokens]
        case TransformCase.CAMELCASE:
            tokens = [
                token.lower() if i == 0 else token.capitalize() for i, token in enumerate(tokens)
            ]
            return ["".join(tokens)]
        case TransformCase.SENTENCE:
            return [tokens[0].capitalize()] + [token.lower() for token in tokens[1:]]
        case _:
            return tokens


def guess_separator(stem: str) -> Separator:
    """Analyze a string to determine the most commonly used word separator.

    Count occurrences of common separator characters (space, hyphen, underscore, period) and return the most frequently used one. If no separators are found, return None.

    Args:
        stem (str): The string to analyze for separators.

    Returns:
        Separator | None: The most common separator found as a Separator enum value, or None if no separators are present.
    """
    separators = [" ", "-", "_", "."]

    # Count occurrences of each separator
    separator_counts = {}
    for sep in separators:
        count = stem.count(sep)
        if count > 0:
            separator_counts[sep] = count

    # Return the most common separator
    try:
        best_guess = max(separator_counts, key=separator_counts.get)
        return Separator(best_guess)
    except ValueError:
        return Separator.UNDERSCORE
