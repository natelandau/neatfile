"""Test the strings utility functions."""

import pytest

from neatfile import settings
from neatfile.constants import Separator, TransformCase
from neatfile.utils.strings import (
    guess_separator,
    match_case,
    split_camel_case,
    strip_special_chars,
    strip_stopwords,
    tokenize_string,
    transform_case,
)


@pytest.mark.parametrize(
    ("input_tokens", "match_list", "expected"),
    [
        (["FooBar", "BAZ"], (), ["FooBar", "BAZ"]),
        (["foobar", "baz"], ["FOOBAR", "BAZ"], ["FOOBAR", "BAZ"]),
        (["foobar", "baz"], ["FooBar"], ["FooBar", "baz"]),
    ],
)
def test_match_case(
    input_tokens: list[str], match_list: tuple[str, ...], expected: list[str]
) -> None:
    """Verify match_case() preserves case based on match list."""
    assert match_case(input_tokens, match_list) == expected


@pytest.mark.parametrize(
    ("input_strings", "match_list", "expected"),
    [
        (["foo", "bar", "baz"], (), ["foo", "bar", "baz"]),
        (["fooBarBaz"], (), ["foo", "Bar", "Baz"]),
        (["fooBarBaz"], ("fooBarBaz",), ["fooBarBaz"]),
        (["fooBarBaz", "CEO"], ("BarBaz",), ["foo", "Bar", "Baz", "CEO"]),
    ],
)
def test_split_camel_case(
    input_strings: list[str], match_list: tuple[str, ...], expected: list[str]
) -> None:
    """Verify splitting camelCase strings into separate words."""
    # Given: Various strings with camelCase and regular words
    # When: Calling split_camel_case
    # Then: Words are correctly split on camelCase boundaries
    assert split_camel_case(input_strings, match_case_list=match_list) == expected


@pytest.mark.parametrize(
    ("input_string", "expected"),
    [
        ("foo bar baz", ["foo", " ", "bar", " ", "baz"]),
        (
            "---99_ _9foo-b9ar_baz9 9f9oo9",
            ["-", "-", "-", "99", "_", " ", "_", "9foo", "-", "b9ar", "_", "baz9", " ", "9f9oo9"],
        ),
        ("123 a 456 B 789 c", ["123", " ", "a", " ", "456", " ", "B", " ", "789", " ", "c"]),
    ],
)
def test_tokenize_string(input_string: str, expected: list[str]) -> None:
    """Verify splitting strings into tokens preserving separators."""
    assert tokenize_string(input_string) == expected


@pytest.mark.parametrize(
    ("input_tokens", "expected"),
    [
        (["foo", " ", "bar", "-", ".", "baz_123"], ["foo", "bar", "baz123"]),
        (["%foo~!@#$%^bar", "_", "b.az:123"], ["foobar", "baz123"]),
    ],
)
def test_strip_special_chars(input_tokens: list[str], expected: list[str]) -> None:
    """Verify removing special characters from strings."""
    assert strip_special_chars(input_tokens) == expected


@pytest.mark.parametrize(
    ("input_tokens", "stopwords", "expected"),
    [
        (["foo", "bar", "baz"], (), ["foo", "bar", "baz"]),
        (["foo", "bar", "baz"], ("bar",), ["foo", "baz"]),
        (["foo", "bar", "bar1", "baz"], ("bar", "baz"), ["foo", "bar1"]),
        (["foo", "bar", "baz"], ("foo", "bar", "baz"), []),
        (
            ["the", "Quick", "brown", "fox", "jumps", "Over", "the", "lazy", "dog"],
            (),
            ["Quick", "brown", "fox", "jumps", "lazy", "dog"],
        ),
        (
            ["the", "Quick", "brown", "fox", "jumps", "Over", "the", "lazy", "dog"],
            ("fox",),
            ["Quick", "brown", "jumps", "lazy", "dog"],
        ),
    ],
)
def test_strip_stopwords(
    input_tokens: list[str], stopwords: tuple[str, ...], expected: list[str]
) -> None:
    """Verify removing stopwords from token lists."""
    # Given: Settings enabled for stopword removal
    settings.update({"strip_stopwords": True})

    # When: Calling strip_stopwords with various inputs
    # Then: Stopwords are correctly removed
    assert strip_stopwords(input_tokens, stopwords=stopwords) == expected


@pytest.mark.parametrize(
    ("input_tokens", "case_format", "expected"),
    [
        (["Foo", "BAR", "baz"], TransformCase.CAMELCASE, ["fooBarBaz"]),
        (["Foo", "BAR", "baz"], TransformCase.LOWER, ["foo", "bar", "baz"]),
        (["Foo", "BAR", "baz"], TransformCase.UPPER, ["FOO", "BAR", "BAZ"]),
        (["Foo", "BAR", "baz"], TransformCase.SENTENCE, ["Foo", "bar", "baz"]),
        (["Foo", "BAR", "baz"], TransformCase.TITLE, ["Foo", "Bar", "Baz"]),
        (["Foo", "BAR", "baz"], TransformCase.IGNORE, ["Foo", "BAR", "baz"]),
    ],
)
def test_transform_case(input_tokens: list[str], case_format, expected: list[str]) -> None:
    """Verify transforming string case according to specified format."""
    assert transform_case(input_tokens, case_format) == expected


@pytest.mark.parametrize(
    ("input_string", "expected"),
    [
        # Single separator cases
        ("foo bar baz", Separator.SPACE),
        ("foo-bar-baz", Separator.DASH),
        ("foo_bar_baz", Separator.UNDERSCORE),
        ("foo.bar.baz", Separator.PERIOD),
        # Multiple separators - should return most frequent
        ("foo-bar_baz-qux-", Separator.DASH),
        ("foo bar.baz bar test", Separator.SPACE),
        # Edge cases
        ("foo.bar-baz", Separator.DASH),
        ("", Separator.UNDERSCORE),
        ("foobar", Separator.UNDERSCORE),
        ("FooBarBaz", Separator.UNDERSCORE),
        # Mixed frequency - should return most common
        ("foo.bar.baz_qux", Separator.PERIOD),
        ("test-case.test_case-final", Separator.DASH),
    ],
)
def test_guess_separator(input_string: str, expected: Separator | None) -> None:
    """Verify guessing the most common separator in a string."""
    # When: Guessing the separator for the input string
    # Then: The correct separator or None is returned
    assert guess_separator(input_string) == expected
