"""String utilities."""

import re

from neatfile.constants import (
    SEPARATOR_CHARACTERS,
    Separator,
    TransformCase,
)


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
    return [case_mapping.get(token.lower(), token) for token in tokens]


def _split_on_case_boundaries(word: str) -> list[str]:
    """Split a single word before each uppercase letter that starts a new camelCase segment.

    A boundary sits before an uppercase letter that follows a lowercase letter or digit, or that ends an uppercase run and is followed by a lowercase letter (so 'HTMLParser' becomes ['HTML', 'Parser']). Character-level checks are used instead of a regex because the re module has no Unicode-aware uppercase class.

    Args:
        word (str): The word to split.

    Returns:
        list[str]: The camelCase segments, or the whole word when it has no boundaries.
    """
    words: list[str] = []
    current = ""
    for i, char in enumerate(word):
        prev = word[i - 1] if i else ""
        nxt = word[i + 1] if i + 1 < len(word) else ""
        starts_segment = char.isupper() and (
            prev.islower() or prev.isdigit() or (prev.isupper() and nxt.islower())
        )
        if current and starts_segment:
            words.append(current)
            current = ""
        current += char
    words.append(current)
    return words


def split_camel_case(string_list: list[str], match_case_list: tuple[str, ...] = ()) -> list[str]:
    """Split strings containing camelCase words into separate words.

    Split each string in the input list into separate words based on camelCase boundaries. Preserve acronyms and any strings specified in match_case_list. For example, 'camelCase' becomes ['camel', 'Case'] but 'CEO' remains intact.

    Args:
        string_list (list[str]): List of strings to split on camelCase boundaries.
        match_case_list (tuple[str, ...], optional): Strings that should not be split. Defaults to ().

    Returns:
        list[str]: List of strings with camelCase words split into separate components.
    """
    result: list[str] = []
    for item in string_list:
        if item in match_case_list or item.isupper():
            result.append(item)
        else:
            result.extend(_split_on_case_boundaries(item))

    return result


def remove_inner_apostrophes(text: str) -> str:
    """Drop apostrophes inside words so possessives and contractions stay one word.

    Without this, tokenizing splits "John's" into "John" and "s". Straight and curly apostrophes
    are removed only after a letter or digit and before a letter, so quotes around a word and
    numbers such as "5'10" or "Q3'23" are left alone.

    Args:
        text (str): The text to edit.

    Returns:
        str: The text with inner apostrophes removed, as in "Johns", "dont", and "80s".
    """
    return re.sub(pattern=r"(?<=[^\W_])['\u2019](?=[^\W\d_])", repl="", string=text)


def tokenize_string(string: str) -> list[str]:
    """Split a string into word tokens and single separator tokens.

    Return each run of letters and digits as one token, and each other character, underscore included, as its own token. Joining the tokens reproduces the input.

    Args:
        string (str): The input string to tokenize.

    Returns:
        list[str]: A list of non-empty tokens extracted from the input string.
    """
    return re.findall(r"[^\W_]+|[\W_]", string)


def strip_special_chars(tokens: list[str]) -> list[str]:
    """Strip every character that is not a letter or digit, underscores included, from each token.

    Drop tokens left empty, so separator-only tokens vanish from the cleaned name.

    Args:
        tokens (list[str]): Tokens to strip.

    Returns:
        list[str]: The stripped, non-empty tokens.
    """
    return [cleaned for token in tokens if (cleaned := re.sub(r"[\W_]", "", token))]


def strip_stopwords(
    tokens: list[str], *, stopwords: frozenset[str], protected_words: frozenset[str] = frozenset()
) -> list[str]:
    """Drop stopword tokens so names and search terms keep only meaningful words.

    Match `stopwords` ignoring case. Match `protected_words` with case, so an abbreviation such as
    "IT" survives while the word "it" is removed.

    Args:
        tokens (list[str]): Tokens to filter.
        stopwords (frozenset[str]): Lowercase words to remove.
        protected_words (frozenset[str], optional): Exact tokens to keep even when they are stopwords. Defaults to an empty set.

    Returns:
        list[str]: The tokens that are not stopwords. Empty when every token is a stopword.
    """
    return [token for token in tokens if token in protected_words or token.lower() not in stopwords]


def _title_word(word: str) -> str:
    """Capitalize a word for title case without changing letters that follow a digit.

    str.title() turns "1st" into "1St" and str.capitalize() turns "3D" into "3d", so letters after
    a digit keep the case the user typed.

    Args:
        word (str): The word to capitalize.

    Returns:
        str: The word with its first character uppercased and later letters lowercased, except
            letters directly after a digit.
    """
    return "".join(
        char.upper() if i == 0 else char if word[i - 1].isdigit() else char.lower()
        for i, char in enumerate(word)
    )


def transform_case(tokens: list[str], case_style: TransformCase) -> list[str]:
    """Change the case of each token according to the configured case style.

    For camelcase, lowercase the first token and capitalize the rest. Join the result with
    `join_tokens`, which drops the separator for camelcase.

    Args:
        tokens (list[str]): Tokens to transform.
        case_style (TransformCase): The case transformation to apply.

    Returns:
        list[str]: The transformed tokens. Empty when `tokens` is empty.
    """
    match case_style:
        case TransformCase.LOWER:
            return [token.lower() for token in tokens]
        case TransformCase.UPPER:
            return [token.upper() for token in tokens]
        case TransformCase.TITLE:
            return [_title_word(token) for token in tokens]
        case TransformCase.CAMELCASE:
            return [
                token.lower() if i == 0 else token.capitalize() for i, token in enumerate(tokens)
            ]
        case TransformCase.SENTENCE:
            return [
                token.capitalize() if i == 0 else token.lower() for i, token in enumerate(tokens)
            ]
        case _:
            return tokens


def join_tokens(tokens: list[str], *, case_style: TransformCase, separator: str) -> str:
    """Join cleaned tokens into a stem, so every case style is joined the way it expects.

    Args:
        tokens (list[str]): Tokens returned by `transform_case`.
        case_style (TransformCase): The case transformation applied to the tokens.
        separator (str): Text placed between words.

    Returns:
        str: The joined stem. Camelcase words are joined without a separator.
    """
    return ("" if case_style == TransformCase.CAMELCASE else separator).join(tokens)


def guess_separator(stem: str) -> Separator:
    """Analyze a string to determine the most commonly used word separator.

    Count occurrences of common separator characters (space, hyphen, underscore, period) and return the most frequently used one. Ties go to the earlier character in that list. If no separators are found, return underscore.

    Args:
        stem (str): The string to analyze for separators.

    Returns:
        Separator: The most common separator, or underscore if the string contains none.
    """
    most_common: str = max(SEPARATOR_CHARACTERS, key=stem.count)
    return Separator(most_common) if stem.count(most_common) else Separator.UNDERSCORE
