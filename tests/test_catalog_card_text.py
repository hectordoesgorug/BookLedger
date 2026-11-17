from bookledger.ui.catalog_text import truncate_to_two_lines


def measure(text):
    return len(text)


def test_one_line_and_exactly_two_lines_keep_their_full_display_text():
    assert truncate_to_two_lines("Short title", 20, measure) == "Short title"
    assert truncate_to_two_lines("One Two", 5, measure) == "One\nTwo"


def test_text_beyond_two_lines_gets_an_ellipsis():
    assert truncate_to_two_lines("One Two Three", 5, measure) == "One\nTwo…"


def test_long_unbroken_text_wraps_and_truncates_without_exceeding_width():
    result = truncate_to_two_lines("abcdefghijk", 4, measure)

    assert result == "abcd\nefg…"
    assert all(measure(line) <= 4 for line in result.splitlines())


def test_empty_text_and_nonpositive_width_are_safe():
    assert truncate_to_two_lines("  ", 10, measure) == ""
    assert truncate_to_two_lines("Title", 0, measure) == ""
