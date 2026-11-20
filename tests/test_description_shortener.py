import ast
import inspect

import pytest

from bookledger.services import description_shortener
from bookledger.services.description_shortener import shorten_description


# Transcribed from the supplied comparison screenshots; lengths match their Original counts.
SCREENSHOT_DESCRIPTIONS = {
    "human_origins": (
        "Where did we come from? Where are we going? Homo sapiens is the most successful, the most widespread and the most influential species ever to walk the Earth. "
        "In the blink of an evolutionary eye we have spread around the globe, taken control of Earth's biological and mineral resources, transformed the environment, discovered the secrets of the universe and travelled into space. "
        "Yet just 7 million years ago, we were just another species of great ape making a quiet living in the forests of East Africa. "
        "We do not know exactly what this ancestor was like, but it was no more likely than a chimpanzee or gorilla to sail across the ocean, write a symphony, invent a steam engine or ponder the meaning of existence. "
        "How did we get from there to here? The Story of Human Origins recounts the most astonishing evolutionary tale ever told. "
        "Discover how our ancestors made the first tentative steps towards becoming human, how we lost our fur but gained language, fire and tools, how we strode out of Africa, invented farming and cities and ultimately created modern civilization - perhaps the only one of its kind in the Universe. "
        "Meet your long-lost ancestors, the other humans who once shared the planet with us, and learn where the story might end."
    ),
    "thriller": (
        "The world's most celebrated thriller writer returns with his most stunning novel yet--a propulsive, twisty, thought-provoking masterpiece that will entertain readers as only Dan Brown can do. "
        "Robert Langdon, esteemed professor of symbology, travels to Prague to attend a groundbreaking lecture by Katherine Solomon--a prominent noetic scientist with whom he has recently begun a relationship. "
        "Katherine is on the verge of publishing an explosive book that contains startling discoveries about the nature of human consciousness and threatens to disrupt centuries of established belief. "
        "But a brutal murder catapults the trip into chaos, and Katherine suddenly disappears along with her manuscript. "
        "Langdon finds himself targeted by a powerful organization and hunted by a chilling assailant sprung from Prague's most ancient mythology. "
        "As the plot expands into London and New York, Langdon desperately searches for Katherine . . . and for answers. "
        "In a thrilling race through the dual worlds of futuristic science and mystical lore, he uncovers a shocking truth about a secret project that will forever change the way we think about the human mind."
    ),
    "artificial_intelligence": (
        "How did artificial intelligence become the most powerful technology on the planet? "
        "Sometime in the future the intelligence of machines will exceed that of human brain power. "
        "So are we on the edge of an AI-pocalypse, with superintelligent devices superseding humanity, as predicted by Stephen Hawking? "
        "Or will this herald a kind of Utopia, with machines doing a far better job at complex tasks than us? "
        "You might not realize it, but you interact with AIs every day. They route your phone calls, approve your credit card transactions and help your doctor interpret results. "
        "Driverless cars will soon be on the roads with a decision-making computer in charge. But how do machines actually think and learn? "
        "In Machines That Think, AI experts and New Scientist explore how artificial intelligence helps us understand human intelligence, machines that compose music and write stories - and ask if AI is really a threat."
    ),
}


@pytest.mark.parametrize("name,length", [("human_origins", 1246), ("thriller", 1147), ("artificial_intelligence", 913)])
def test_screenshot_transcription_lengths(name, length):
    assert len(SCREENSHOT_DESCRIPTIONS[name]) == length


@pytest.mark.parametrize("name,expected", [
    ("human_origins", "ancestors"),
    ("thriller", "Katherine"),
    ("artificial_intelligence", "Machines That Think"),
])
def test_screenshot_results_prioritize_the_subject(name, expected):
    source = SCREENSHOT_DESCRIPTIONS[name]
    result = shorten_description(source)
    assert result is not None
    assert expected in result
    assert result == shorten_description(source)
    assert len(result) < len(source)
    if name == "thriller":
        assert "most celebrated" not in result
        assert "murder" in result and "disappears" in result
    if name == "human_origins":
        assert not result.startswith("Where did we come from?")
        assert "language, fire and tools" in result
    if name == "artificial_intelligence":
        assert "intelligence of machines will exceed" in result


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


def test_promotion_is_weighted_without_discarding_mixed_factual_sentences():
    praise = "An internationally acclaimed, stunning masterpiece by a bestselling author."
    subject = "This acclaimed study examines how volcanic eruptions changed farming in Iceland during the eighteenth century."
    detail = "Farmers rebuild their villages while researchers trace the evidence preserved in the soil."
    source = " ".join((praise, subject, detail, praise, praise))
    result = shorten_description(source)
    assert result == f"{subject} {detail}"


def test_informative_question_and_quote_remain_eligible():
    question = "How did volcanic eruptions change farming and trade in eighteenth-century Iceland?"
    quote = 'The historian asks, “Who kept the records?” before examining the archive (including its missing pages).'
    source = f"{question} {quote} " + "An acclaimed, stunning masterpiece. " * 8
    assert shorten_description(source) == f"{question} {quote}"


def test_redundant_sentences_are_not_repeated_and_source_order_is_preserved():
    first = "A historian examines the evidence from a coastal archive."
    repeat = "A historian examines evidence from a coastal archive."
    last = "The records reveal how fishing communities adapted to changing sea levels."
    source = " ".join((first, first, repeat, last, first, last))
    assert shorten_description(source) == f"{first} {last}"


def test_dependent_sentence_keeps_preceding_context():
    intro = "Mara inherits an archive in a remote coastal village."
    dependent = "She discovers evidence of a murder that threatens the village."
    source = "An acclaimed masterpiece. " * 10 + intro + " " + dependent
    result = shorten_description(source)
    assert result == f"{intro} {dependent}"


def test_initials_decimals_parentheses_and_ellipses_do_not_create_fragments():
    first = "Dr. A. B. Rivera examines U.S. history (including events in Jan. 2020) using a 3.14 scale."
    second = "The evidence reveals gaps . . . and questions that remain unresolved."
    source = f"{first} {second} " + "A stunning masterpiece. " * 8
    assert shorten_description(source) == f"{first} {second}"


@pytest.mark.parametrize("source", [
    "A stunning masterpiece. " * 20,
    "An acclaimed masterpiece. " * 10 + "An unfinished description about the archive without sentence punctuation",
    "She investigates the evidence. " * 20,
    123,
    {"description": "Unexpected mapping"},
    "A short synopsis." + "\n " * 200 + "Another brief sentence.",
])
def test_no_safe_improvement_returns_no_change(source):
    assert shorten_description(source) is None


def test_service_only_imports_the_standard_library_regex_module():
    tree = ast.parse(inspect.getsource(description_shortener))
    imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
    assert len(imports) == 1
    assert isinstance(imports[0], ast.Import)
    assert [alias.name for alias in imports[0].names] == ["re"]
