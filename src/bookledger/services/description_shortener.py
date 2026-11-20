"""Deterministic, extractive shortening for book descriptions."""

import re


TARGET_CHARACTERS = 300
_NON_TERMINAL_ABBREVIATIONS = {
    "dr.", "mr.", "mrs.", "ms.", "prof.", "rev.", "jr.", "sr.",
    "e.g.", "i.e.", "u.s.", "u.k.", "u.n.", "jan.", "feb.", "mar.",
    "apr.", "jun.", "jul.", "aug.", "sep.", "sept.", "oct.", "nov.",
    "dec.",
}
_TOKEN_BEFORE_PERIOD = re.compile(r"(?:[A-Za-z]+\.)+$|(?:[A-Za-z]+\.)*[A-Za-z]+\.$")
_RETAIL_SECTION = re.compile(
    r"^\s*(?:about the author|industry reviews|shipping and returns|frequently asked questions|"
    r"you may also like|you might also like|readers also enjoyed|buy\b.{0,300}?\bfrom booktopia)\b",
    re.IGNORECASE,
)
# shortcut: English cues cannot resolve every reference; extend them for demonstrated failures.
_PROMOTION = re.compile(
    r"\b(?:best[ -]?selling|bestseller|acclaimed|award[ -]winning|celebrated|masterpiece|"
    r"stunning|propulsive|unputdownable|must[ -]read|brilliant|compelling|thought-provoking)\b",
    re.IGNORECASE,
)
_SUBJECT = re.compile(
    r"\b(?:explor\w*|examin\w*|investigat\w*|argues?|traces?|recounts?|discuss\w*|"
    r"discover\w*|reveals?|follows?|research|evidence|history|evolution\w*|ancestors?|"
    r"intelligence|superintelligen\w*|consciousness|conflict|murder|disappear\w*|"
    r"threat\w*|targeted|hunted|travels?|returns? to|set in|must|forced to)\b",
    re.IGNORECASE,
)
_CONTEXT_START = re.compile(
    r"^[\"'“‘(]*(?:he|she|it|they|his|her|their|its|such|but|yet|"
    r"so|however|therefore|instead|then|the discovery|"
    r"(?:this|these|those)\s+(?:is|are|was|were|means?|leads?|reveals?|changes?))\b", re.IGNORECASE,
)


def _sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    sentences: list[str] = []
    start = 0
    index = 0
    while index < len(normalized):
        if normalized[index] not in ".!?":
            index += 1
            continue
        ellipsis = re.match(r"\.(?:\s*\.)+", normalized[index:])
        if ellipsis:
            index += ellipsis.end()
            continue
        punctuation_end = index + 1
        while punctuation_end < len(normalized) and normalized[punctuation_end] in ".!?":
            punctuation_end += 1
        while punctuation_end < len(normalized) and normalized[punctuation_end] in '\"\'”’)]}':
            punctuation_end += 1
        if (
            normalized[index] == "."
            and index > 0
            and punctuation_end < len(normalized)
            and normalized[index - 1].isdigit()
            and normalized[punctuation_end].isdigit()
        ):
            index = punctuation_end
            continue
        if punctuation_end < len(normalized) and normalized[punctuation_end].isspace():
            token_start = max(normalized.rfind(" ", start, index), normalized.rfind("\t", start, index)) + 1
            token = normalized[token_start:index + 1].casefold().lstrip("([{\"'“‘")
            abbreviation = _TOKEN_BEFORE_PERIOD.fullmatch(token)
            next_text = normalized[punctuation_end:].lstrip().lstrip('\"\'“‘(')
            if (abbreviation and token in _NON_TERMINAL_ABBREVIATIONS) or re.fullmatch(r"[a-z]\.", token):
                index = punctuation_end + 1
                continue
            # Quoted questions, ellipses and parenthetical clauses can continue the same sentence.
            prefix = normalized[start:punctuation_end]
            if (next_text and next_text[0].islower()) or prefix.count("(") > prefix.count(")"):
                index = punctuation_end + 1
                continue
            sentence = normalized[start:punctuation_end].strip()
            if sentence:
                sentences.append(sentence)
            start = punctuation_end
            while start < len(normalized) and normalized[start].isspace():
                start += 1
            index = start
            continue
        index = punctuation_end
    tail = normalized[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences


def _relevance(sentence: str) -> int:
    subject = min(3, len(_SUBJECT.findall(sentence)))
    promotion = len(_PROMOTION.findall(sentence))
    scope = bool(re.search(
        r"\b(?:discover how|(?:book|account|study) (?:explores?|examines?|traces?|argues?))\b",
        sentence, re.IGNORECASE,
    ))
    # Mixed factual/promotion sentences stay eligible; praise alone gets a negative weight.
    promotion_penalty = min(6, promotion * (1 if subject else 3))
    question_penalty = bool(subject and sentence.endswith("?"))
    return 1 + subject * 2 + scope * 2 - promotion_penalty - question_penalty


def shorten_description(text: str | None, *, target: int = TARGET_CHARACTERS) -> str | None:
    """Select informative source sentences, or None when no useful shortening is safe."""
    if not isinstance(text, str) or target < 1:
        return None
    source_length = len(" ".join(text.split()))
    if source_length <= target:
        return None
    sentences = []
    for sentence in _sentences(text):
        if _RETAIL_SECTION.search(sentence):
            break
        sentences.append(sentence)
    selected: set[int] = set()
    scores = [_relevance(sentence) for sentence in sentences]
    words = [set(re.findall(r"\w+", sentence.casefold())) for sentence in sentences]
    for index in sorted(range(len(sentences)), key=lambda i: (-scores[i], i)):
        if scores[index] <= 0 or index in selected:
            continue
        group = {index}
        context = index
        while context > 0 and _CONTEXT_START.search(sentences[context]):
            context -= 1
            group.add(context)
        if context == 0 and _CONTEXT_START.search(sentences[0]):
            continue
        # Near-identical sentences add length without adding useful content.
        if any(
            len(words[index] & words[other]) / max(1, len(words[index] | words[other])) >= 0.85
            for other in selected
        ):
            continue
        candidate = " ".join(sentences[i] for i in sorted(selected | group))
        if not all(re.search(r'[.!?][\"\'”’)\]}]*$', sentences[i]) for i in group):
            continue
        allow_over_target = not selected or scores[index] > 1
        if len(candidate) <= target or (allow_over_target and len(candidate) <= target + 50):
            selected.update(group)
    shortened = " ".join(sentences[i] for i in sorted(selected))
    if not shortened or len(shortened) >= source_length:
        return None
    if source_length - len(shortened) < max(20, int(source_length * 0.1)):
        return None
    return shortened
