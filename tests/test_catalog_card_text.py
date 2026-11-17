from bookledger.ui.catalog_text import catalog_display_title, combined_title, truncate_to_two_lines


def measure(text):
    return len(text)


def test_title_and_subtitle_join_without_empty_separators():
    assert combined_title(" Main title ", " Subtitle ") == "Main title: Subtitle"
    assert combined_title("Main title", "  ") == "Main title"
    assert combined_title("Main title", None) == "Main title"


def test_catalog_subtitle_threshold_counts_separator_and_falls_back_to_main_title():
    title = "A" * 20
    assert catalog_display_title(title, "B" * 37) == f"{title}: {'B' * 37}"
    assert len(combined_title(title, "B" * 38)) == 60
    assert catalog_display_title(title, "B" * 38) == title
    assert catalog_display_title(title, "B" * 39) == title
    assert catalog_display_title(title, None) == title


def test_catalog_subtitle_selection_precedes_existing_two_line_truncation():
    title = "Main title"
    displayed = catalog_display_title(title, "A short subtitle")
    assert truncate_to_two_lines(displayed, 12, measure) == "Main title:\nA short…"


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
