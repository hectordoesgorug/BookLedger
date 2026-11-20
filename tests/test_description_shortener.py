from bookledger.services.description_shortener import shorten_description


def test_short_descriptions_and_missing_input_are_unchanged():
    assert shorten_description(None) is None
    assert shorten_description("  ") is None
    assert shorten_description("A brief synopsis.") is None


def test_selects_a_deterministic_prefix_of_complete_sentences():
    first = "Mara returns to the coastal village where she grew up and catalogs her grandfather's letters."
    second = "The discovery reveals a family history shaped by migration, loss, and a dispute over the lighthouse."
    third = "The final chapters follow Mara as she decides what to preserve for the next generation."
    source = f"{first}\n\n{second} {third} " + (third + " ") * 5

    result = shorten_description(source)

    assert result == shorten_description(source)
    assert result.startswith(first)
    assert second in result
    assert third in result
    assert len(source) > 300
    assert result.count(third) == 1
    assert len(result) < len(source)


def test_allows_a_complete_sentence_slightly_over_the_preferred_target():
    first = "A long sentence " + ("about evidence and context " * 11) + "is preserved."
    source = first + " This additional sentence makes the description longer than the preferred target."

    assert 300 < len(first) <= 350
    assert shorten_description(source) == first


def test_does_not_cut_a_single_long_sentence_or_unterminated_text():
    source = "A continuous account " + ("describes events and evidence " * 20) + "without an early stop."

    assert len(source) > 500
    assert shorten_description(source) is None
    assert shorten_description(source.rstrip(".")) is None


def test_common_abbreviations_and_dates_do_not_split_sentences():
    first = "Prof. Ana discusses U.S. history in Jan. 2020, including Dr. Rivera's research."
    second = "Their evidence changes how the town understands its past."
    third = "Later chapters follow the archive into a multilingual community."
    source = f"{first} {second} {third} " + ("Additional context remains available. " * 5)

    result = shorten_description(source)

    assert result is not None
    assert result.startswith(first)
    assert second in result


def test_clear_retail_recommendation_section_is_excluded():
    first = "A historian traces the letters across several generations and connects them to the town's changing shoreline."
    second = "The account follows how local families preserved their records through migration and economic change."
    source = "\n\n".join((
        first,
        second,
        "You may also like these other books from the same collection.",
        "Later chapters examine the archive and its place in regional history. " * 4,
    ))

    result = shorten_description(source)

    assert result is not None
    assert result == f"{first} {second}"
    assert "You may also like" not in result


def test_unicode_and_quoted_sentence_punctuation_are_preserved():
    first = 'The author asks, “What remains?” before visiting a bilingual archive with 日本語 records.'
    second = "A careful reading connects the documents without adding claims."
    source = f"{first} {second} " + ("Further context follows from the collection. " * 6)

    result = shorten_description(source)

    assert result is not None
    assert result.startswith(first)
    assert second in result
