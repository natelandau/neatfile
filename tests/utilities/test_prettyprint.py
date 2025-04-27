# type: ignore
"""This module contains the tests for the prettyprint module."""

from textwrap import dedent

import pytest

from neatfile.utils.pretty_print import PrettyPrinter, PrintStyle, pp


def test_default_styles(clean_stdout):
    """Test that the default styles are correctly defined."""
    pp.trace("trace")
    pp.debug("debug")
    pp.info("info")
    pp.warning("warning")
    pp.error("error")
    pp.critical("critical")
    pp.success("success")
    pp.dryrun("dryrun")
    pp.notice("notice")
    pp.secondary("secondary")
    assert clean_stdout() == dedent("""\
        info
        🚧 Warning: warning
        ❌ Error: error
        💀 Critical: critical
        ✅ Success: success
        👉 Dry run: dryrun
        notice
        secondary
        """)


def test_dict_in_message(clean_stdout):
    """Test that dicts in messages are correctly formatted."""
    pp.info({"key": "value", "key2": ["value2", "value3"]})
    assert clean_stdout() == dedent("""\
        {
          "key": "value",
          "key2": [
            "value2",
            "value3"
          ]
        }
    """)


def test_code_highlighting(clean_stdout):
    """Test that code highlighting works."""
    pp.info("there is inline `code` in this message")
    assert clean_stdout() == "there is inline code in this message\n"


@pytest.mark.parametrize(
    ("debug_switch", "trace_switch"),
    [
        (False, False),
        (True, False),
        (False, True),
        (True, True),
    ],
)
def test_trace_and_debug(clean_stdout, debug, debug_switch, trace_switch):
    """Test that trace and debug are correctly defined."""
    pp.configure(debug=debug_switch, trace=trace_switch)
    pp.debug("debug")
    pp.trace("trace")

    output = clean_stdout()

    if debug_switch:
        assert "🐛 debug" in output
    else:
        assert "🐛 debug" not in output

    if trace_switch:
        assert "🔍 trace" in output
    else:
        assert "🔍 trace" not in output


def test_custom_styles(clean_stdout):
    """Test that custom styles are correctly defined."""
    new_style = PrintStyle(name="new_style", prefix=":smile: ", suffix=" :rocket:")
    new_dryrun = PrintStyle(name="dryrun", style="bold green")

    pp.configure(styles=[new_style, new_dryrun])
    pp.new_style("I am new style")
    pp.dryrun("dryrun no longer has an emoji")
    assert clean_stdout() == "😄 I am new style 🚀\ndryrun no longer has an emoji\n"


def test_rule_without_message(clean_stdout):
    """Print a horizontal rule without a message."""
    # When: Printing a rule without a message
    pp.rule()

    # Then: A horizontal rule is printed
    assert "──────" in clean_stdout()


def test_rule_with_message(clean_stdout):
    """Print a horizontal rule with a message."""
    # When: Printing a rule with a message
    pp.rule("Test Message")

    # Then: A horizontal rule with message is printed
    output = clean_stdout()
    assert "────── Test Message ──────" in output
    assert "─" in output


def test_all_styles_displays_styles(capsys) -> None:
    """Display all available print styles."""
    # Given: A configured pretty print instance
    pp.configure(debug=True, trace=True)

    # When: Displaying all styles
    pp.all_styles()

    # Then: Output contains style information
    captured = capsys.readouterr()
    assert "Available styles" in captured.out
    assert "info" in captured.out
    assert "debug" in captured.out
    assert "trace" in captured.out
    assert "success" in captured.out
    assert "warning" in captured.out
    assert "error" in captured.out


def test_all_styles_with_custom_style(capsys) -> None:
    """Display all styles including custom styles."""
    # Given: A pretty print instance with custom style

    custom_style = PrintStyle(name="custom", prefix=">> ", style="bold magenta")
    pp.configure(styles=[custom_style])

    # When: Displaying all styles
    pp.all_styles()

    # Then: Output includes custom style
    captured = capsys.readouterr()
    assert "custom" in captured.out
    assert ">> The quick brown fox jumps over the lazy dog" in captured.out


def test_initialization_happens_once() -> None:
    """Test that PrettyPrinter follows a singleton pattern."""
    # Given: Initial PrettyPrinter instance with modified settings
    instance1 = PrettyPrinter()
    instance1.debug_enabled = True
    instance1.trace_enabled = True

    # When: Creating a new instance
    instance2 = PrettyPrinter()

    # Then: Settings should persist as initialization should not happen again
    assert instance2.debug_enabled is True
    assert instance2.trace_enabled is True
    assert instance1 is instance2
